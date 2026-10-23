// GnuCOBOL 3.2 default file profile: LINE SEQUENTIAL, fixed SEQUENTIAL and RELATIVE.
use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, BufReader, Read, Seek, SeekFrom, Write};
use crate::runtime::{Value, fail};

enum State { Closed, Locked, Input(BufReader<File>), Output(File), InputOutput(File), Missing }

#[derive(Clone, Copy)]
pub enum Advance { BeforeLines(u32), AfterLines(u32), BeforePage, AfterPage }

#[derive(Clone, Copy, PartialEq)]
enum Organization { LineSequential, Sequential }

pub struct CobolFile {
    path: String,
    optional: bool,
    organization: Organization,
    state: State,
    eof: bool,
    fixed: bool,
    split: bool,
    needs_nl: bool,
    last_read_size: usize,
    last_open_mode: &'static str,
    read_done: bool,
}

thread_local! {
    static OPEN_PATHS: std::cell::RefCell<std::collections::HashSet<String>> = Default::default();
}

/// Several SELECTs may name one path, but sharing it while both are open
/// depends on native locking and buffering: stop instead of guessing.
fn claim_path(path: &str) {
    if !OPEN_PATHS.with(|paths| paths.borrow_mut().insert(path.to_string())) {
        fail("simultaneous OPEN of one path by several files not modelled");
    }
}

fn release_path(path: &str) {
    OPEN_PATHS.with(|paths| { paths.borrow_mut().remove(path); });
}

fn setting(name: &str, default: bool) -> bool {
    match std::env::var(name) {
        Err(std::env::VarError::NotPresent) => default,
        Ok(value) => match value.to_ascii_lowercase().as_str() {
            "1" | "y" | "yes" | "on" | "true" => true,
            "0" | "n" | "no" | "off" | "false" => false,
            _ => fail(&format!("invalid boolean runtime setting: {name}")),
        },
        _ => fail(&format!("invalid runtime setting: {name}")),
    }
}

fn write_advance(file: &mut File, advance: Advance) {
    let bytes = match advance {
        Advance::BeforeLines(count) | Advance::AfterLines(count) => {
            if count > u16::MAX as u32 { fail("ADVANCING count exceeds supported range 0..65535"); }
            if count == 0 { vec![b'\r'] } else { vec![b'\n'; count as usize] }
        },
        Advance::BeforePage | Advance::AfterPage => vec![b'\x0c'],
    };
    file.write_all(&bytes).unwrap_or_else(|e| fail(&format!("file advancing failed: {e}")));
}

impl CobolFile {
    pub fn new(path: &str, optional: bool, organization: &str) -> Self {
        let organization = match organization {
            "LINE SEQUENTIAL" => Organization::LineSequential,
            "SEQUENTIAL" => Organization::Sequential,
            _ => fail("unsupported file organization"),
        };
        // Unknown profile/remapping settings must not silently change the reference behavior.
        for key in ["COB_RUNTIME_CONFIG", "COB_FILE_PATH", "COB_UNIX_LF"] {
            if std::env::var_os(key).is_some() { fail(&format!("file runtime setting not supported: {key}")); }
        }
        if organization == Organization::LineSequential {
            for key in ["COB_LS_NULLS", "COB_LS_USES_CR"] {
                if std::env::var_os(key).is_some() { fail(&format!("file runtime setting not supported: {key}")); }
            }
        } else {
            for key in ["COB_SEQ_CONCAT_NAME", "COB_SEQ_CONCAT_SEP"] {
                if std::env::var_os(key).is_some() { fail(&format!("file runtime setting not supported: {key}")); }
            }
        }
        for key in [path.to_string(), format!("DD_{path}"), format!("dd_{path}")] {
            if std::env::var_os(&key).is_some() { fail("file name environment remapping not supported"); }
        }
        let line = organization == Organization::LineSequential;
        Self { path: path.into(), optional, organization, state: State::Closed, eof: false,
               fixed: line && setting("COB_LS_FIXED", false), split: line && setting("COB_LS_SPLIT", true),
               needs_nl: false, last_read_size: 0, last_open_mode: "", read_done: false }
    }

    /// Mode of the last OPEN attempt, kept by an OPEN rejected as already open.
    pub fn last_open_mode(&self) -> &'static str { self.last_open_mode }

    pub fn open(&mut self, mode: &str) -> u8 {
        let status = self.open_file(mode);
        if status < 10 { claim_path(&self.path); }
        status
    }

    fn open_file(&mut self, mode: &str) -> u8 {
        // CLOSE WITH LOCK forbids any later OPEN in the run unit.
        if matches!(self.state, State::Locked) { return 38; }
        if !matches!(self.state, State::Closed) { return 41; }
        self.last_open_mode = match mode {
            "INPUT" => "INPUT", "OUTPUT" => "OUTPUT", "EXTEND" => "EXTEND", "I-O" => "I-O",
            _ => fail("unsupported file open mode"),
        };
        self.read_done = false;
        if mode == "I-O" {
            if self.organization != Organization::Sequential { fail("OPEN I-O limited to SEQUENTIAL files"); }
            self.needs_nl = false;
            self.last_read_size = 0;
            // GnuCOBOL opens "r+"; a missing OPTIONAL file is created empty (05).
            return match OpenOptions::new().read(true).write(true).open(&self.path) {
                Ok(file) => { self.state = State::InputOutput(file); self.eof = false; 0 },
                Err(error) if error.kind() == io::ErrorKind::NotFound && self.optional => {
                    match OpenOptions::new().read(true).write(true).create(true).open(&self.path) {
                        Ok(file) => { self.state = State::InputOutput(file); self.eof = false; 5 },
                        Err(error) if error.kind() == io::ErrorKind::PermissionDenied => 37,
                        Err(error) => fail(&format!("unmodelled OPEN I-O failure: {error}")),
                    }
                },
                Err(error) if error.kind() == io::ErrorKind::NotFound => 35,
                Err(error) if error.kind() == io::ErrorKind::PermissionDenied => 37,
                Err(error) => fail(&format!("unmodelled OPEN I-O failure: {error}")),
            };
        }
        self.needs_nl = false;
        self.last_read_size = 0;
        let result = match mode {
            "INPUT" => File::open(&self.path).map(|f| State::Input(BufReader::new(f))),
            "OUTPUT" => OpenOptions::new().write(true).create(true).truncate(true).open(&self.path).map(State::Output),
            "EXTEND" => OpenOptions::new().append(true).open(&self.path).map(State::Output),
            _ => fail("unsupported file open mode"),
        };
        match result {
            Ok(state) => { self.state = state; self.eof = false; 0 },
            Err(error) if error.kind() == io::ErrorKind::NotFound && mode == "INPUT" && self.optional => {
                self.state = State::Missing; self.eof = false; 5
            },
            Err(error) if error.kind() == io::ErrorKind::NotFound && mode == "EXTEND" && self.optional => {
                match OpenOptions::new().append(true).create(true).open(&self.path) {
                    Ok(file) => { self.state = State::Output(file); self.eof = false; 5 },
                    Err(error) if error.kind() == io::ErrorKind::NotFound => 30,
                    Err(error) if error.kind() == io::ErrorKind::PermissionDenied => 37,
                    Err(error) => fail(&format!("unmodelled OPEN EXTEND failure: {error}")),
                }
            },
            Err(error) if error.kind() == io::ErrorKind::NotFound && mode == "OUTPUT" => 30,
            Err(error) if error.kind() == io::ErrorKind::NotFound => 35,
            Err(error) if error.kind() == io::ErrorKind::PermissionDenied => 37,
            Err(error) => fail(&format!("unmodelled OPEN failure: {error}")),
        }
    }

    pub fn close(&mut self, lock: bool) -> u8 {
        if matches!(self.state, State::Closed) { return 42; }
        if matches!(self.state, State::Locked) { fail("CLOSE of a file closed WITH LOCK not modelled"); }
        self.read_done = false;
        if let State::InputOutput(file) = &mut self.state {
            file.flush().unwrap_or_else(|e| fail(&format!("file flush failed: {e}")));
        }
        if let State::Output(file) = &mut self.state {
            if self.needs_nl {
                file.write_all(b"\n").unwrap_or_else(|e| fail(&format!("file closing newline failed: {e}")));
            }
            file.flush().unwrap_or_else(|e| fail(&format!("file flush failed: {e}")));
        }
        self.state = if lock { State::Locked } else { State::Closed };
        release_path(&self.path);
        self.eof = false;
        self.needs_nl = false;
        self.last_read_size = 0;
        0
    }

    pub fn last_read_size(&self) -> usize { self.last_read_size }

    pub fn read(&mut self, record: &mut Value) -> u8 {
        let status = self.read_record(record);
        // Like cob_read, any 0x status enables a following REWRITE.
        self.read_done = status < 10;
        status
    }

    fn read_record(&mut self, record: &mut Value) -> u8 {
        self.last_read_size = 0;
        self.read_done = false;
        if !matches!(self.state, State::Input(_) | State::InputOutput(_) | State::Missing) { return 47; }
        if self.eof { return 46; }
        if matches!(self.state, State::Missing) { self.eof = true; return 10; }
        let size = record.text_size();
        if self.organization == Organization::Sequential {
            // I-O reads are unbuffered so that REWRITE seeks from the true position.
            let reader: &mut dyn Read = match &mut self.state {
                State::Input(reader) => reader,
                State::InputOutput(file) => file,
                _ => unreachable!(),
            };
            // A short final fixed record replaces only the bytes physically read.
            let mut bytes = record.bytes();
            let mut count = 0;
            while count < size {
                match reader.read(&mut bytes[count..size]) {
                    Ok(0) => break,
                    Ok(read) => count += read,
                    Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
                    Err(error) => fail(&format!("file read failed: {error}")),
                }
            }
            if count == 0 { self.eof = true; return 10; }
            self.last_read_size = count;
            record.assign(&Value::Bytes(bytes), false);
            return 0;
        }
        let reader = match &mut self.state { State::Input(reader) => reader, _ => unreachable!() };
        let mut line = Vec::new();
        // Keep memory bounded even for an input with no record delimiter.
        loop {
            let available = reader.fill_buf().unwrap_or_else(|e| fail(&format!("file read failed: {e}")));
            if available.is_empty() { break; }
            let count = available.iter().position(|&b| b == b'\n').map(|p| p + 1).unwrap_or(available.len());
            let ended = available[count - 1] == b'\n';
            line.extend_from_slice(&available[..count]);
            reader.consume(count);
            if line.len() > 1024 * 1024 { fail("LINE SEQUENTIAL physical line exceeds 1 MiB"); }
            if ended { break; }
        }
        if line.is_empty() { self.eof = true; return 10; }
        let terminated = line.last() == Some(&b'\n');
        if terminated {
            line.pop();
            if line.last() == Some(&b'\r') { line.pop(); }
        }
        if !line.iter().all(|b| (32..=126).contains(b)) {
            fail("LINE SEQUENTIAL requires printable ASCII records");
        }
        if self.split && (line.len() > size || (!terminated && line.len() == size)) {
            fail("split/unterminated full records unsupported; use COB_LS_SPLIT=0 for truncation semantics");
        }
        let status = if line.len() > size { 4 } else { 0 };
        self.last_read_size = line.len().min(size);
        let text = std::str::from_utf8(&line[..line.len().min(size)]).unwrap();
        record.assign(&Value::text(text), false);
        status
    }

    /// SEQUENTIAL REWRITE of the record just read, as sequential_rewrite does:
    /// seek back one record size from the current position and overwrite it.
    pub fn rewrite(&mut self, record: &Value) -> u8 {
        let read_done = self.read_done;
        self.read_done = false;
        let file = match &mut self.state { State::InputOutput(file) => file, _ => return 49 };
        if !read_done { return 43; }
        let bytes = record.bytes();
        if self.last_read_size != bytes.len() { fail("REWRITE after a partial SEQUENTIAL record not modelled"); }
        file.seek(SeekFrom::Current(-(bytes.len() as i64))).unwrap_or_else(|e| fail(&format!("file seek failed: {e}")));
        file.write_all(&bytes).unwrap_or_else(|e| fail(&format!("file write failed: {e}")));
        0
    }

    pub fn write(&mut self, record: &Value, advancing: Option<Advance>) -> u8 {
        self.read_done = false;
        if self.organization == Organization::LineSequential && advancing.is_some() {
            fail("ADVANCING on LINE SEQUENTIAL is not supported");
        }
        let file = match &mut self.state { State::Output(file) => file, _ => return 48 };
        let bytes = record.bytes();
        if self.organization == Organization::Sequential {
            if let Some(advance @ (Advance::AfterLines(_) | Advance::AfterPage)) = advancing {
                write_advance(file, advance);
                self.needs_nl = true;
            }
            file.write_all(&bytes).unwrap_or_else(|e| fail(&format!("file write failed: {e}")));
            if let Some(advance @ (Advance::BeforeLines(_) | Advance::BeforePage)) = advancing {
                write_advance(file, advance);
                self.needs_nl = false;
            }
            return 0;
        }
        if !bytes.iter().all(|b| (32..=126).contains(b)) {
            fail("LINE SEQUENTIAL requires printable ASCII records");
        }
        let text = std::str::from_utf8(&bytes).unwrap();
        let text = if self.fixed { text } else { text.trim_end_matches(' ') };
        file.write_all(text.as_bytes()).unwrap_or_else(|e| fail(&format!("file write failed: {e}")));
        file.write_all(if cfg!(windows) { b"\r\n" } else { b"\n" }).unwrap_or_else(|e| fail(&format!("file write failed: {e}")));
        0
    }
}

impl Drop for CobolFile {
    fn drop(&mut self) {
        // STOP RUN closes open files too, including a pending AFTER newline.
        if !matches!(self.state, State::Closed | State::Locked) { self.close(false); }
    }
}

/// Store FILE STATUS. Without it, an exception (status 1x..9x) that no AT END
/// phrase or USE procedure handles is fatal, like GnuCOBOL's standard handler.
/// AT END covers every 1x status and INVALID KEY every 2x, like cobc's handlers.
pub fn file_status(status: u8, destination: Option<&mut Value>, eof_handled: bool, invalid_handled: bool, declarative: bool) {
    if let Some(field) = destination {
        let status = format!("{status:02}");
        if field.is_text() { field.assign(&Value::text(&status), false); }
        else { field.assign(&Value::number(&status), false); }
    } else if status >= 10 && !(status / 10 == 1 && eof_handled) && !(status / 10 == 2 && invalid_handled) && !declarative {
        fail(&format!("unhandled file status {status:02}"));
    }
}

#[derive(Clone, Copy, PartialEq)]
enum Access { Sequential, Random, Dynamic }

#[derive(Clone, Copy)]
pub enum StartCondition { Equal, Greater, NotLess }

/// GnuCOBOL 3.2 RELATIVE file on Linux x86-64: each slot is a native size_t
/// (8 bytes, little endian) holding the record size, then `record_max` bytes.
/// A zero size, including a hole read as zeros, marks an empty slot.
pub struct RelativeFile {
    path: String,
    optional: bool,
    access: Access,
    record_max: usize,
    file: Option<File>,
    open_mode: &'static str,
    locked: bool,
    last_open_mode: &'static str,
    nonexistent: bool,
    end_of_file: bool,
    first_read: u8,
    read_done: bool,
}

fn read_full(file: &mut File, buffer: &mut [u8]) -> usize {
    let mut count = 0;
    while count < buffer.len() {
        match file.read(&mut buffer[count..]) {
            Ok(0) => break,
            Ok(read) => count += read,
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(error) => fail(&format!("file read failed: {error}")),
        }
    }
    count
}

fn seek(file: &mut File, position: SeekFrom) -> u64 {
    file.seek(position).unwrap_or_else(|e| fail(&format!("file seek failed: {e}")))
}

fn put(file: &mut File, bytes: &[u8]) {
    file.write_all(bytes).unwrap_or_else(|e| fail(&format!("file write failed: {e}")));
}

/// cob_get_int on the RELATIVE KEY, limited by the frontend to 9 digits.
fn key_number(key: &Value) -> i64 {
    key.integer("RELATIVE KEY") as i64
}

impl RelativeFile {
    pub fn new(path: &str, optional: bool, access: &str, record_max: usize) -> Self {
        for key in ["COB_RUNTIME_CONFIG", "COB_FILE_PATH"] {
            if std::env::var_os(key).is_some() { fail(&format!("file runtime setting not supported: {key}")); }
        }
        for key in [path.to_string(), format!("DD_{path}"), format!("dd_{path}")] {
            if std::env::var_os(&key).is_some() { fail("file name environment remapping not supported"); }
        }
        let access = match access {
            "SEQUENTIAL" => Access::Sequential, "RANDOM" => Access::Random, "DYNAMIC" => Access::Dynamic,
            _ => fail("unsupported RELATIVE access mode"),
        };
        Self { path: path.into(), optional, access, record_max, file: None, open_mode: "", locked: false,
               last_open_mode: "", nonexistent: false, end_of_file: false, first_read: 0, read_done: false }
    }

    pub fn last_open_mode(&self) -> &'static str { self.last_open_mode }

    fn slot_size(&self) -> u64 { self.record_max as u64 + 8 }

    pub fn open(&mut self, mode: &str) -> u8 {
        let status = self.open_file(mode);
        if status < 10 { claim_path(&self.path); }
        status
    }

    fn open_file(&mut self, mode: &str) -> u8 {
        if self.locked { return 38; }
        if !self.open_mode.is_empty() { return 41; }
        self.last_open_mode = match mode {
            "INPUT" => "INPUT", "OUTPUT" => "OUTPUT", "EXTEND" => "EXTEND", "I-O" => "I-O",
            _ => fail("unsupported file open mode"),
        };
        self.read_done = false;
        self.nonexistent = false;
        self.end_of_file = false;
        self.first_read = 2;
        let exists = std::path::Path::new(&self.path).exists();
        if !exists && mode != "OUTPUT" && !self.optional { return 35; }
        let mut options = OpenOptions::new();
        match mode {
            "INPUT" => { options.read(true); },
            "OUTPUT" => { options.read(true).write(true).create(true).truncate(true); },
            "I-O" => { options.read(true).write(true).create(!exists); },
            _ => { options.read(true).append(true).create(true); },
        }
        if mode == "INPUT" && !exists {
            // cob_fd_file_open: a missing OPTIONAL input is opened as nonexistent.
            self.nonexistent = true;
            self.open_mode = "INPUT";
            return 5;
        }
        match options.open(&self.path) {
            Ok(mut file) => {
                if mode == "EXTEND" { seek(&mut file, SeekFrom::End(0)); }
                self.file = Some(file);
                self.open_mode = self.last_open_mode;
                if !exists && mode != "OUTPUT" { 5 } else { 0 }
            },
            Err(error) if error.kind() == io::ErrorKind::PermissionDenied => 37,
            Err(error) => fail(&format!("unmodelled RELATIVE OPEN failure: {error}")),
        }
    }

    pub fn close(&mut self, lock: bool) -> u8 {
        self.read_done = false;
        if self.open_mode.is_empty() {
            if self.locked { fail("CLOSE of a file closed WITH LOCK not modelled"); }
            return 42;
        }
        if let Some(file) = self.file.as_mut() {
            file.flush().unwrap_or_else(|e| fail(&format!("file flush failed: {e}")));
        }
        self.file = None;
        self.open_mode = "";
        self.locked = lock;
        release_path(&self.path);
        0
    }

    /// cob_read_next followed by relative_read_next.
    pub fn read_next(&mut self, record: &mut Value, key: Option<&mut Value>) -> u8 {
        self.read_done = false;
        if !matches!(self.open_mode, "INPUT" | "I-O") { return 47; }
        if self.nonexistent {
            if self.first_read == 0 { return 46; }
            self.first_read = 0;
            return 10;
        }
        if self.end_of_file { return 46; }
        let status = self.relative_read_next(record, key);
        if status < 10 {
            self.first_read = 0;
            self.read_done = true;
            self.end_of_file = false;
        } else if status == 10 {
            self.end_of_file = true;
        }
        status
    }

    fn relative_read_next(&mut self, record: &mut Value, key: Option<&mut Value>) -> u8 {
        let slot = self.slot_size();
        let record_max = self.record_max;
        let file = self.file.as_mut().unwrap();
        let length = file.metadata().unwrap_or_else(|e| fail(&format!("file stat failed: {e}"))).len();
        if length == 0 { return 10; }
        if length < slot { return 30; }
        let mut offset = seek(file, SeekFrom::Current(0));
        loop {
            let mut size = [0u8; 8];
            let count = read_full(file, &mut size);
            if count != 8 {
                if count != 0 { return 30; }
                return 10;
            }
            if u64::from_le_bytes(size) > 0 {
                let mut data = vec![0u8; record_max];
                if read_full(file, &mut data) != record_max { return 30; }
                record.assign(&Value::Bytes(data), false);
                if let Some(key) = key {
                    let number = offset / slot + 1;
                    key.move_number(&Value::number("0"));
                    if key.checked_assign(&Value::number(&number.to_string()), false).is_err() {
                        seek(file, SeekFrom::Start(offset));
                        return 14;
                    }
                }
                return 0;
            }
            offset = seek(file, SeekFrom::Current(record_max as i64));
        }
    }

    /// cob_read with a key, then relative_read.
    pub fn read_key(&mut self, record: &mut Value, key: &Value) -> u8 {
        self.read_done = false;
        if !matches!(self.open_mode, "INPUT" | "I-O") { return 47; }
        if self.nonexistent {
            if self.first_read == 0 { return 23; }
            self.first_read = 0;
            return 10;
        }
        let slot = self.slot_size();
        let record_max = self.record_max;
        let number = key_number(key) - 1;
        if number < 0 { return 23; }
        let file = self.file.as_mut().unwrap();
        let offset = number as u64 * slot;
        seek(file, SeekFrom::Start(offset));
        let mut size = [0u8; 8];
        if read_full(file, &mut size) != 8 { return 23; }
        if u64::from_le_bytes(size) == 0 {
            seek(file, SeekFrom::Start(offset));
            return 23;
        }
        let mut data = vec![0u8; record_max];
        if read_full(file, &mut data) != record_max { return 30; }
        record.assign(&Value::Bytes(data), false);
        self.first_read = 0;
        self.read_done = true;
        self.end_of_file = false;
        0
    }

    /// cob_write then relative_write.
    pub fn write(&mut self, record: &Value, key: Option<&mut Value>) -> u8 {
        self.read_done = false;
        let allowed = if self.access == Access::Sequential { ["OUTPUT", "EXTEND"] } else { ["OUTPUT", "I-O"] };
        if !allowed.contains(&self.open_mode) { return 48; }
        let bytes = record.bytes();
        if bytes.len() != self.record_max { fail("RELATIVE record size differs from the file record"); }
        let slot = self.slot_size();
        let sequential = self.access == Access::Sequential;
        let file = self.file.as_mut().unwrap();
        let offset = if sequential {
            seek(file, SeekFrom::Current(0))
        } else {
            let number = key_number(key.as_deref().unwrap_or_else(|| fail("RELATIVE KEY required"))) - 1;
            if number < 0 { return 24; }
            let offset = number as u64 * slot;
            seek(file, SeekFrom::Start(offset));
            let mut size = [0u8; 8];
            if read_full(file, &mut size) > 0 && u64::from_le_bytes(size) > 0 { return 22; }
            offset
        };
        seek(file, SeekFrom::Start(offset));
        put(file, &(bytes.len() as u64).to_le_bytes());
        put(file, &bytes);
        if sequential {
            if let Some(key) = key {
                let number = (offset + slot) / slot;
                key.move_number(&Value::number(&number.to_string()));
            }
        }
        0
    }

    /// cob_rewrite then relative_rewrite. A random rewrite of an empty slot
    /// inside the file writes the data, keeps the zero size and returns 00.
    pub fn rewrite(&mut self, record: &Value, key: Option<&Value>) -> u8 {
        let read_done = self.read_done;
        self.read_done = false;
        if self.open_mode != "I-O" { return 49; }
        if self.access == Access::Sequential && !read_done { return 43; }
        let bytes = record.bytes();
        if bytes.len() != self.record_max { fail("RELATIVE record size differs from the file record"); }
        let slot = self.slot_size();
        let sequential = self.access == Access::Sequential;
        let file = self.file.as_mut().unwrap();
        if sequential {
            seek(file, SeekFrom::Current(-(bytes.len() as i64)));
        } else {
            let number = key_number(key.unwrap_or_else(|| fail("RELATIVE KEY required"))) - 1;
            if number < 0 { return 24; }
            seek(file, SeekFrom::Start(number as u64 * slot));
            let mut size = [0u8; 8];
            if read_full(file, &mut size) != 8 { return 23; }
        }
        put(file, &bytes);
        0
    }

    /// cob_delete then relative_delete; an already empty slot returns 00.
    pub fn delete(&mut self, key: Option<&Value>) -> u8 {
        let read_done = self.read_done;
        self.read_done = false;
        if self.open_mode != "I-O" { return 49; }
        if self.access == Access::Sequential && !read_done { return 43; }
        let slot = self.slot_size();
        let record_max = self.record_max;
        let number = key_number(key.unwrap_or_else(|| fail("DELETE without RELATIVE KEY not modelled"))) - 1;
        if number < 0 { return 24; }
        let file = self.file.as_mut().unwrap();
        let offset = number as u64 * slot;
        seek(file, SeekFrom::Start(offset));
        let mut size = [0u8; 8];
        if read_full(file, &mut size) != 8 { return 23; }
        seek(file, SeekFrom::Start(offset));
        put(file, &0u64.to_le_bytes());
        seek(file, SeekFrom::Current(record_max as i64));
        0
    }

    /// cob_start then relative_start for EQUAL, GREATER and NOT LESS.
    pub fn start(&mut self, condition: StartCondition, key: &Value) -> u8 {
        self.read_done = false;
        self.first_read = 0;
        if !matches!(self.open_mode, "INPUT" | "I-O") { return 47; }
        if self.access == Access::Random { return 47; }
        if self.nonexistent { return 23; }
        let status = self.relative_start(condition, key);
        self.end_of_file = status != 0;
        self.first_read = 1;
        status
    }

    fn relative_start(&mut self, condition: StartCondition, key: &Value) -> u8 {
        let slot = self.slot_size();
        let file = self.file.as_mut().unwrap();
        let length = file.metadata().unwrap_or_else(|e| fail(&format!("file stat failed: {e}"))).len();
        if length == 0 { return 23; }
        let mut index = key_number(key) - 1;
        if index < 0 {
            index = match condition {
                StartCondition::NotLess => 0,
                StartCondition::Greater => -1,
                StartCondition::Equal => return 23,
            };
        }
        if matches!(condition, StartCondition::Greater) { index += 1; }
        loop {
            if index < 0 { return 23; }
            let offset = index as u64 * slot;
            if offset >= length { return 23; }
            seek(file, SeekFrom::Start(offset));
            let mut size = [0u8; 8];
            if read_full(file, &mut size) == 8 && u64::from_le_bytes(size) > 0 {
                seek(file, SeekFrom::Start(offset));
                return 0;
            }
            match condition {
                StartCondition::Equal => return 23,
                _ => index += 1,
            }
        }
    }
}

impl Drop for RelativeFile {
    fn drop(&mut self) {
        if !self.open_mode.is_empty() { self.close(false); }
    }
}
