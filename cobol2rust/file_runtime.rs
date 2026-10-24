// GnuCOBOL 3.2 default file profile: LINE SEQUENTIAL, fixed SEQUENTIAL, RELATIVE and INDEXED.
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
    record_min: usize,
    record_max: usize,
}

/// cob_write/cob_rewrite record size: DEPENDING ON value capped at the size
/// of the record named in the statement, or that record's size.
fn record_size(record_size: usize, depending: Option<&Value>) -> usize {
    match depending {
        Some(value) => (value.integer("RECORD DEPENDING ON").max(0) as usize).min(record_size),
        None => record_size,
    }
}

fn set_depending(depending: Option<&mut Value>, size: usize) {
    if let Some(value) = depending { value.move_number(&Value::number(&size.to_string())); }
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
    pub fn new(path: &str, optional: bool, organization: &str, record_min: usize, record_max: usize) -> Self {
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
               needs_nl: false, last_read_size: 0, last_open_mode: "", read_done: false, record_min, record_max }
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

    /// CLOSE REEL/UNIT and WITH NO REWIND of a disk file (cob_file_close):
    /// NO REWIND closes and returns 07; REEL and UNIT only synchronize the
    /// file, which stays open, and return 07. A missing OPTIONAL file closes as usual.
    pub fn close_unit(&mut self, no_rewind: bool) -> u8 {
        if matches!(self.state, State::Closed) { return 42; }
        if matches!(self.state, State::Locked) { fail("CLOSE of a file closed WITH LOCK not modelled"); }
        if matches!(self.state, State::Missing) { return self.close(false); }
        if no_rewind { self.close(false); return 7; }
        self.read_done = false;
        if let State::Output(file) | State::InputOutput(file) = &mut self.state {
            file.flush().unwrap_or_else(|e| fail(&format!("file flush failed: {e}")));
        }
        7
    }

    pub fn last_read_size(&self) -> usize { self.last_read_size }

    fn variable(&self) -> bool { self.record_min != self.record_max }

    pub fn read(&mut self, record: &mut Value, depending: Option<&mut Value>) -> u8 {
        let status = self.read_record(record);
        // Like cob_read, any 0x status enables a following REWRITE.
        self.read_done = status < 10;
        if status < 10 { set_depending(depending, self.last_read_size); }
        status
    }

    /// sequential_read of a variable file: a 4-byte header holds the size as
    /// a big-endian u16 followed by two zero bytes (COB_VARSEQ_FORMAT 0).
    fn read_variable(&mut self, record: &mut Value) -> u8 {
        let (minimum, maximum) = (self.record_min, self.record_max);
        let reader: &mut dyn Read = match &mut self.state {
            State::Input(reader) => reader,
            State::InputOutput(file) => file,
            _ => unreachable!(),
        };
        let mut header = [0u8; 4];
        let count = read_into(reader, &mut header);
        if count == 0 { self.eof = true; return 10; }
        if count != 4 || header[2] != 0 || header[3] != 0 { return 39; }
        let mut size = u16::from_be_bytes([header[0], header[1]]) as usize;
        let mut status = 0;
        let mut skip = 0;
        if size < minimum { status = 4; }
        if size > maximum { skip = size - maximum; size = maximum; status = 4; }
        let mut bytes = record.bytes();
        let count = read_into(reader, &mut bytes[..size]);
        if count == 0 && size > 0 { self.last_read_size = 0; return 4; }
        self.last_read_size = count;
        record.assign(&Value::Bytes(bytes), false);
        if skip > 0 {
            let mut rest = vec![0u8; skip];
            read_into(reader, &mut rest);
        }
        status
    }

    fn read_record(&mut self, record: &mut Value) -> u8 {
        self.last_read_size = 0;
        self.read_done = false;
        if !matches!(self.state, State::Input(_) | State::InputOutput(_) | State::Missing) { return 47; }
        if self.eof { return 46; }
        if matches!(self.state, State::Missing) { self.eof = true; return 10; }
        let size = record.text_size();
        if self.organization == Organization::Sequential && self.variable() {
            return self.read_variable(record);
        }
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
    /// cob_rewrite: the size of the record read must equal the size of the
    /// record named (and its DEPENDING ON value), else 44.
    pub fn rewrite(&mut self, area: &Value, size: usize, depending: Option<&Value>) -> u8 {
        let read_done = self.read_done;
        self.read_done = false;
        let last = self.last_read_size;
        let file = match &mut self.state { State::InputOutput(file) => file, _ => return 49 };
        if !read_done { return 43; }
        if last != size { return 44; }
        if let Some(value) = depending {
            if value.integer("RECORD DEPENDING ON") != last as i128 { return 44; }
        }
        let bytes = area.bytes();
        file.seek(SeekFrom::Current(-(last as i64))).unwrap_or_else(|e| fail(&format!("file seek failed: {e}")));
        file.write_all(&bytes[..last]).unwrap_or_else(|e| fail(&format!("file write failed: {e}")));
        0
    }

    pub fn write(&mut self, area: &Value, size: usize, advancing: Option<Advance>, depending: Option<&Value>) -> u8 {
        self.read_done = false;
        if self.organization == Organization::LineSequential && advancing.is_some() {
            fail("ADVANCING on LINE SEQUENTIAL is not supported");
        }
        let variable = self.variable();
        let size = record_size(size, depending);
        let file = match &mut self.state { State::Output(file) => file, _ => return 48 };
        if size < self.record_min || size > self.record_max { return 44; }
        let bytes = area.bytes()[..size].to_vec();
        if self.organization == Organization::Sequential {
            if let Some(advance @ (Advance::AfterLines(_) | Advance::AfterPage)) = advancing {
                write_advance(file, advance);
                self.needs_nl = true;
            }
            if variable {
                let length = u16::try_from(size).unwrap_or_else(|_| fail("variable record exceeds 65535 bytes"));
                let [high, low] = length.to_be_bytes();
                file.write_all(&[high, low, 0, 0]).unwrap_or_else(|e| fail(&format!("file write failed: {e}")));
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
    record_min: usize,
    record_max: usize,
    last_read_size: usize,
    file: Option<File>,
    open_mode: &'static str,
    locked: bool,
    last_open_mode: &'static str,
    nonexistent: bool,
    end_of_file: bool,
    first_read: u8,
    read_done: bool,
}

fn read_full(file: &mut File, buffer: &mut [u8]) -> usize { read_into(file, buffer) }

fn read_into(reader: &mut dyn Read, buffer: &mut [u8]) -> usize {
    let mut count = 0;
    while count < buffer.len() {
        match reader.read(&mut buffer[count..]) {
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
    pub fn new(path: &str, optional: bool, access: &str, record_min: usize, record_max: usize) -> Self {
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
        Self { path: path.into(), optional, access, record_min, record_max, last_read_size: 0, file: None, open_mode: "", locked: false,
               last_open_mode: "", nonexistent: false, end_of_file: false, first_read: 0, read_done: false }
    }

    pub fn last_open_mode(&self) -> &'static str { self.last_open_mode }

    /// Record size of the last READ (the slot's size field), for READ INTO.
    pub fn last_read_size(&self) -> usize { self.last_read_size }

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
    pub fn read_next(&mut self, record: &mut Value, key: Option<&mut Value>, depending: Option<&mut Value>) -> u8 {
        let status = self.cob_read_next(record, key);
        if status < 10 { set_depending(depending, self.last_read_size); }
        status
    }

    fn cob_read_next(&mut self, record: &mut Value, key: Option<&mut Value>) -> u8 {
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
                self.last_read_size = u64::from_le_bytes(size) as usize;
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
    pub fn read_key(&mut self, record: &mut Value, key: &Value, depending: Option<&mut Value>) -> u8 {
        let status = self.cob_read_key(record, key);
        if status < 10 { set_depending(depending, self.last_read_size); }
        status
    }

    fn cob_read_key(&mut self, record: &mut Value, key: &Value) -> u8 {
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
        self.last_read_size = u64::from_le_bytes(size) as usize;
        self.first_read = 0;
        self.read_done = true;
        self.end_of_file = false;
        0
    }

    /// cob_write then relative_write.
    /// relative_write stores the record size in the slot, then the whole area.
    pub fn write(&mut self, area: &Value, size: usize, key: Option<&mut Value>, depending: Option<&Value>) -> u8 {
        self.read_done = false;
        let allowed = if self.access == Access::Sequential { ["OUTPUT", "EXTEND"] } else { ["OUTPUT", "I-O"] };
        if !allowed.contains(&self.open_mode) { return 48; }
        let size = record_size(size, depending);
        if size < self.record_min || size > self.record_max { return 44; }
        let bytes = area.bytes();
        if bytes.len() != self.record_max { fail("RELATIVE record area differs from the file record"); }
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
        put(file, &(size as u64).to_le_bytes());
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
    pub fn rewrite(&mut self, area: &Value, size: usize, key: Option<&Value>, depending: Option<&Value>) -> u8 {
        let read_done = self.read_done;
        self.read_done = false;
        if self.open_mode != "I-O" { return 49; }
        if self.access == Access::Sequential && !read_done { return 43; }
        let size = record_size(size, depending);
        if self.record_min != self.record_max && (size < self.record_min || size > self.record_max) { return 44; }
        let bytes = area.bytes();
        if bytes.len() != self.record_max { fail("RELATIVE record area differs from the file record"); }
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

/// One SORT/MERGE key: its place in the SD record and its description.
pub struct SortKey { pub offset: usize, pub size: usize, pub kind: crate::storage_runtime::Kind, pub descending: bool }

/// An SD file as libcob's cob_file_sort_*: records are kept in RELEASE order
/// and sorted on the first RETURN by cob_file_sort_compare, numeric keys by
/// value and others byte by byte; ties keep their order (unique sequence).
pub struct SortFile { record_max: usize, keys: Vec<SortKey>, records: Vec<Vec<u8>>, sorted: bool, next: usize }

impl SortFile {
    pub fn new(record_max: usize) -> Self {
        Self { record_max, keys: Vec::new(), records: Vec::new(), sorted: false, next: 0 }
    }
    pub fn init(&mut self, keys: Vec<SortKey>) {
        self.keys = keys;
        self.records.clear();
        self.sorted = false;
        self.next = 0;
    }
    /// RELEASE: the SD record area, at its maximum size.
    pub fn release(&mut self, area: &Value) {
        if self.sorted { fail("RELEASE after RETURN is not modelled"); }
        let mut bytes = area.bytes();
        bytes.resize(self.record_max, b' ');
        self.records.push(bytes);
    }
    /// cob_copy_check of a USING record into the SD area, then RELEASE.
    pub fn release_from(&mut self, record: &Value, area: &mut Value) {
        area.assign(&Value::Bytes(record.bytes()), false);
        self.release(area);
    }
    fn key_value(&self, record: &[u8], key: &SortKey) -> Value {
        let bytes = record[key.offset..key.offset + key.size].to_vec();
        match key.kind {
            crate::storage_runtime::Kind::Numeric { .. } => Value::View(crate::storage_runtime::View {
                memory: std::rc::Rc::new(std::cell::RefCell::new(bytes)), offset: 0, size: key.size, kind: key.kind,
                dimensions: vec![], initializers: vec![] }).snapshot(),
            _ => Value::Bytes(bytes),
        }
    }
    fn sort(&mut self) {
        let mut indexed: Vec<(Vec<Value>, Vec<u8>)> = std::mem::take(&mut self.records).into_iter()
            .map(|record| (self.keys.iter().map(|key| self.key_value(&record, key)).collect(), record)).collect();
        let keys = &self.keys;
        indexed.sort_by(|(a, _), (b, _)| {
            for ((x, y), key) in a.iter().zip(b.iter()).zip(keys.iter()) {
                let order = x.compare(y);
                if order != std::cmp::Ordering::Equal { return if key.descending { order.reverse() } else { order }; }
            }
            std::cmp::Ordering::Equal
        });
        self.records = indexed.into_iter().map(|(_, record)| record).collect();
        self.sorted = true;
    }
    /// RETURN: the next record into the SD area, 00, or 10 at the end.
    pub fn retrieve(&mut self, area: &mut Value) -> u8 {
        if !self.sorted { self.sort(); }
        if self.next >= self.records.len() { return 10; }
        area.assign(&Value::Bytes(self.records[self.next].clone()), false);
        self.next += 1;
        0
    }
    pub fn close(&mut self) {
        self.records.clear();
        self.sorted = false;
        self.next = 0;
    }
}

/// One INDEXED key: its place in the record and WITH DUPLICATES.
pub struct IndexKey { pub offset: usize, pub size: usize, pub duplicates: bool }

/// A Berkeley DB btree as libcob 3.2 uses it: keys in memcmp order (a
/// shorter key first), duplicates of a key in insertion order (DB_DUP).
#[derive(Default)]
struct Btree { entries: std::collections::BTreeMap<Vec<u8>, Vec<Vec<u8>>> }

/// A cursor position: key and duplicate index.
type Position = (Vec<u8>, usize);

impl Btree {
    fn get(&self, key: &[u8]) -> Option<&Vec<u8>> { self.entries.get(key).and_then(|d| d.first()) }
    fn at(&self, position: &Position) -> (Vec<u8>, Vec<u8>) {
        (position.0.clone(), self.entries[&position.0][position.1].clone())
    }
    fn first(&self) -> Option<Position> { self.entries.keys().next().map(|k| (k.clone(), 0)) }
    fn last(&self) -> Option<Position> { self.entries.iter().next_back().map(|(k, d)| (k.clone(), d.len() - 1)) }
    fn set(&self, key: &[u8]) -> Option<Position> { self.entries.get(key).map(|_| (key.to_vec(), 0)) }
    fn set_range(&self, key: &[u8]) -> Option<Position> {
        self.entries.range(key.to_vec()..).next().map(|(k, _)| (k.clone(), 0))
    }
    fn next(&self, position: &Position) -> Option<Position> {
        if position.1 + 1 < self.entries[&position.0].len() { return Some((position.0.clone(), position.1 + 1)); }
        self.next_nodup(position)
    }
    fn next_nodup(&self, position: &Position) -> Option<Position> {
        use std::ops::Bound::{Excluded, Unbounded};
        self.entries.range::<Vec<u8>, _>((Excluded(&position.0), Unbounded)).next().map(|(k, _)| (k.clone(), 0))
    }
    fn prev(&self, position: &Position) -> Option<Position> {
        if position.1 > 0 { return Some((position.0.clone(), position.1 - 1)); }
        self.entries.range(..position.0.clone()).next_back().map(|(k, d)| (k.clone(), d.len() - 1))
    }
    /// DB->put: NOOVERWRITE fails on an existing key; with DB_DUP the new
    /// duplicate goes after the existing ones.
    fn put(&mut self, key: &[u8], data: &[u8], no_overwrite: bool, duplicates: bool) -> bool {
        match self.entries.get_mut(key) {
            Some(list) if no_overwrite => { let _ = list; false },
            Some(list) if duplicates => { list.push(data.to_vec()); true },
            Some(list) => { list[0] = data.to_vec(); true },
            None => { self.entries.insert(key.to_vec(), vec![data.to_vec()]); true },
        }
    }
    fn delete(&mut self, position: &Position) {
        let list = self.entries.get_mut(&position.0).unwrap();
        list.remove(position.1);
        if list.is_empty() { self.entries.remove(&position.0); }
    }
    fn delete_key(&mut self, key: &[u8]) { self.entries.remove(key); }

    const MAGIC: &'static [u8] = b"cobol2rust-btree-1\n";

    /// cobol2rust's own INDEXED format (not Berkeley DB): the pairs in btree
    /// order, each length a little-endian u32.
    fn load(path: &str) -> Btree {
        let bytes = std::fs::read(path).unwrap_or_else(|e| fail(&format!("INDEXED file read failed: {e}")));
        if !bytes.starts_with(Self::MAGIC) {
            fail("INDEXED file not in cobol2rust format (Berkeley DB files of GnuCOBOL are not read)");
        }
        let mut tree = Btree::default();
        let mut at = Self::MAGIC.len();
        let mut take = |at: &mut usize| -> Vec<u8> {
            if *at + 4 > bytes.len() { fail("truncated INDEXED file"); }
            let size = u32::from_le_bytes(bytes[*at..*at + 4].try_into().unwrap()) as usize;
            if *at + 4 + size > bytes.len() { fail("truncated INDEXED file"); }
            let value = bytes[*at + 4..*at + 4 + size].to_vec();
            *at += 4 + size;
            value
        };
        while at < bytes.len() {
            let key = take(&mut at);
            let data = take(&mut at);
            tree.entries.entry(key).or_default().push(data);
        }
        tree
    }
    fn save(&self, path: &str) {
        let mut bytes = Self::MAGIC.to_vec();
        for (key, list) in &self.entries {
            for data in list {
                bytes.extend((key.len() as u32).to_le_bytes());
                bytes.extend(key);
                bytes.extend((data.len() as u32).to_le_bytes());
                bytes.extend(data);
            }
        }
        std::fs::write(path, bytes).unwrap_or_else(|e| fail(&format!("INDEXED file write failed: {e}")));
    }
}

/// GnuCOBOL 3.2 INDEXED file with the Berkeley DB handler (fileio.c,
/// WITH_DB): the primary btree maps the prime key to the record, each
/// alternate btree ("name.N") its key to the prime key (and, WITH
/// DUPLICATES, a native little-endian u32 duplicate number).
pub struct IndexedFile {
    path: String,
    optional: bool,
    access: Access,
    record_min: usize,
    record_max: usize,
    keys: Vec<IndexKey>,
    db: Vec<Btree>,
    open_mode: &'static str,
    last_open_mode: &'static str,
    locked: bool,
    nonexistent: bool,
    end_of_file: bool,
    begin_of_file: bool,
    first_read: u8,
    read_done: bool,
    last_read_size: usize,
    // struct indexed_file state
    key: Vec<u8>,
    data: Option<Vec<u8>>,
    key_index: usize,
    last_readkey: Vec<Vec<u8>>,
    last_dupno: Vec<u32>,
    rewrite_sec_key: Vec<bool>,
    last_key: Option<Vec<u8>>,
}

impl IndexedFile {
    pub fn new(path: &str, optional: bool, access: &str, record_min: usize, record_max: usize, keys: Vec<IndexKey>) -> Self {
        for key in ["COB_RUNTIME_CONFIG", "COB_FILE_PATH", "DB_HOME", "COB_BDB_HOME"] {
            if std::env::var_os(key).is_some() { fail(&format!("file runtime setting not supported: {key}")); }
        }
        for key in [path.to_string(), format!("DD_{path}"), format!("dd_{path}")] {
            if std::env::var_os(&key).is_some() { fail("file name environment remapping not supported"); }
        }
        let access = match access {
            "SEQUENTIAL" => Access::Sequential, "RANDOM" => Access::Random, "DYNAMIC" => Access::Dynamic,
            _ => fail("unsupported INDEXED access mode"),
        };
        let n = keys.len();
        Self { path: path.into(), optional, access, record_min, record_max, keys, db: Vec::new(), open_mode: "",
               last_open_mode: "", locked: false, nonexistent: false, end_of_file: false, begin_of_file: false,
               first_read: 0, read_done: false, last_read_size: 0, key: Vec::new(), data: None, key_index: 0,
               last_readkey: vec![Vec::new(); 2 * n], last_dupno: vec![0; n], rewrite_sec_key: vec![false; n],
               last_key: None }
    }

    pub fn last_open_mode(&self) -> &'static str { self.last_open_mode }
    pub fn last_read_size(&self) -> usize { self.last_read_size }

    fn file_name(&self, index: usize) -> String {
        if index == 0 { self.path.clone() } else { format!("{}.{}", self.path, index) }
    }
    fn primekeylen(&self) -> usize { self.keys[0].size }

    /// bdb_savekey: the key of index `idx` in `record`.
    fn savekey(&self, record: &[u8], idx: usize) -> Vec<u8> {
        let k = &self.keys[idx];
        record[k.offset..k.offset + k.size].to_vec()
    }
    /// bdb_cmpkey: compare the first `partlen` (0: whole key) bytes.
    fn cmpkey(&self, keyarea: &[u8], record: &[u8], idx: usize, partlen: usize) -> std::cmp::Ordering {
        let k = &self.keys[idx];
        let length = if partlen == 0 { k.size } else { partlen.min(k.size) };
        keyarea[..length.min(keyarea.len())].cmp(&record[k.offset..k.offset + length])
    }
    fn dupno(data: &[u8], primekeylen: usize) -> u32 {
        u32::from_le_bytes(data[primekeylen..primekeylen + 4].try_into().unwrap())
    }

    pub fn open(&mut self, mode: &str) -> u8 {
        if self.locked { return 38; }
        if !self.open_mode.is_empty() { return 41; }
        self.read_done = false;
        self.last_open_mode = match mode {
            "INPUT" => "INPUT", "OUTPUT" => "OUTPUT", "EXTEND" => "EXTEND", "I-O" => "I-O",
            _ => fail("unsupported file open mode"),
        };
        self.nonexistent = false;
        self.end_of_file = false;
        self.begin_of_file = false;
        self.first_read = 2;
        let status = self.indexed_open(mode);
        if status < 10 { claim_path(&self.path); }
        status
    }

    fn indexed_open(&mut self, mode: &str) -> u8 {
        let path = std::path::Path::new(&self.path);
        if path.is_dir() { return 30; }
        let nonexistent = !path.exists();
        if nonexistent && mode != "OUTPUT" && !self.optional { return 35; }
        let n = self.keys.len();
        if nonexistent && mode == "INPUT" {
            // DB_RDONLY on a missing OPTIONAL file: ENOENT.
            self.open_mode = "INPUT";
            self.nonexistent = true;
            self.end_of_file = true;
            self.begin_of_file = true;
            return 5;
        }
        self.db = (0..n).map(|i| {
            let name = self.file_name(i);
            if mode == "OUTPUT" || !std::path::Path::new(&name).exists() { Btree::default() } else { Btree::load(&name) }
        }).collect();
        self.last_readkey = vec![Vec::new(); 2 * n];
        self.last_dupno = vec![0; n];
        self.rewrite_sec_key = vec![false; n];
        self.key_index = 0;
        self.last_key = None;
        self.key = Vec::new();
        self.data = None;
        // DB_FIRST on the primary btree.
        if let Some(position) = self.db[0].first() {
            let (key, data) = self.db[0].at(&position);
            self.last_readkey[0] = key.clone();
            self.key = key;
            self.data = Some(data);
        }
        self.open_mode = self.last_open_mode;
        if self.optional && nonexistent && mode != "OUTPUT" { 5 } else { 0 }
    }

    pub fn close(&mut self, lock: bool) -> u8 {
        self.read_done = false;
        if self.open_mode.is_empty() {
            if self.locked { fail("CLOSE of a file closed WITH LOCK not modelled"); }
            return 42;
        }
        if !self.nonexistent && self.open_mode != "INPUT" {
            for (i, tree) in self.db.iter().enumerate() { tree.save(&self.file_name(i)); }
        }
        self.db.clear();
        self.open_mode = "";
        self.locked = lock;
        release_path(&self.path);
        0
    }

    /// cob_start then indexed_start_internal. `key` is the key of index
    /// `index` given by the START KEY item, `partlen` that item's size.
    pub fn start(&mut self, condition: StartCondition, index: usize, partlen: usize, area: &Value) -> u8 {
        self.read_done = false;
        self.first_read = 0;
        if !matches!(self.open_mode, "INPUT" | "I-O") { return 47; }
        if self.access == Access::Random { return 47; }
        if self.nonexistent { return 23; }
        let status = self.start_internal(condition, index, partlen, &area.bytes());
        self.end_of_file = status != 0;
        self.begin_of_file = false;
        self.first_read = 1;
        status
    }

    fn start_internal(&mut self, condition: StartCondition, idx: usize, partlen: usize, record: &[u8]) -> u8 {
        self.key_index = idx;
        let primekeylen = self.primekeylen();
        let mut key = self.savekey(record, idx);
        key.truncate(partlen);
        let tree = &self.db[idx];
        let mut found = tree.set_range(&key);
        match condition {
            StartCondition::Equal => {
                if let Some(p) = &found {
                    if self.cmpkey(&p.0, record, idx, partlen) != std::cmp::Ordering::Equal { found = None; }
                }
            },
            StartCondition::Greater => {
                while let Some(p) = found.clone() {
                    if self.cmpkey(&p.0, record, idx, partlen) != std::cmp::Ordering::Equal { break; }
                    found = tree.next(&p);
                }
            },
            StartCondition::NotLess => {},
        }
        let Some(position) = found else { return 23 };
        let (found_key, found_data) = tree.at(&position);
        let mut dupno = 0;
        let mut prime = found_key.clone();
        let mut record_data = found_data.clone();
        if idx > 0 {
            if self.keys[idx].duplicates { dupno = Self::dupno(&found_data, primekeylen); }
            prime = found_data[..primekeylen].to_vec();
            match self.db[0].get(&prime) {
                Some(data) => record_data = data.clone(),
                None => return 23,
            }
        }
        self.key = prime.clone();
        self.data = Some(record_data);
        if idx == 0 {
            self.last_readkey[0] = prime;
        } else {
            let n = self.keys.len();
            self.last_readkey[idx] = found_key;
            self.last_readkey[idx + n] = prime;
            if self.keys[idx].duplicates { self.last_dupno[idx] = dupno; }
        }
        0
    }

    /// cob_read with a key (READ ... KEY IS, or the prime key) then indexed_read.
    pub fn read_key(&mut self, area: &mut Value, index: usize, partlen: usize, depending: Option<&mut Value>) -> u8 {
        self.read_done = false;
        if !matches!(self.open_mode, "INPUT" | "I-O") { return 47; }
        if self.nonexistent {
            if self.first_read == 0 { return 23; }
            self.first_read = 0;
            return 10;
        }
        let record = area.bytes();
        let status = self.start_internal(StartCondition::Equal, index, partlen, &record);
        if status != 0 { return status; }
        let status = self.store_record(area);
        self.first_read = 0;
        self.read_done = true;
        self.end_of_file = false;
        self.begin_of_file = false;
        set_depending(depending, self.last_read_size);
        status
    }

    fn store_record(&mut self, area: &mut Value) -> u8 {
        let data = self.data.clone().unwrap_or_default();
        let mut status = 0;
        let mut size = data.len();
        if size > self.record_max { size = self.record_max; status = 43; }
        let mut bytes = area.bytes();
        bytes[..size].copy_from_slice(&data[..size]);
        area.assign(&Value::Bytes(bytes), false);
        self.last_read_size = size;
        status
    }

    /// cob_read_next then indexed_read_next (NEXT only).
    pub fn read_next(&mut self, area: &mut Value, depending: Option<&mut Value>) -> u8 {
        self.read_done = false;
        if !matches!(self.open_mode, "INPUT" | "I-O") { return 47; }
        if self.nonexistent {
            if self.first_read == 0 { return 46; }
            self.first_read = 0;
            return 10;
        }
        if self.end_of_file { return 46; }
        let status = self.indexed_read_next(area);
        if status < 10 {
            self.first_read = 0;
            self.read_done = true;
            self.end_of_file = false;
            self.begin_of_file = false;
            set_depending(depending, self.last_read_size);
        } else if status == 10 {
            self.end_of_file = true;
        }
        status
    }

    fn indexed_read_next(&mut self, area: &mut Value) -> u8 {
        let idx = self.key_index;
        let n = self.keys.len();
        let primekeylen = self.primekeylen();
        let duplicates = idx > 0 && self.keys[idx].duplicates;
        let first = self.begin_of_file;
        let mut file_changed = false;
        if self.first_read != 0 {
            if self.data.is_none() { return 10; }
            // Check that the record read by OPEN/START still exists.
            let tree = &self.db[idx];
            let mut position = tree.set(&self.last_readkey[idx]);
            if position.is_some() && idx > 0 {
                let mut ok = false;
                if duplicates {
                    let mut p = position.clone().unwrap();
                    let mut dupno = Self::dupno(&tree.at(&p).1, primekeylen);
                    let mut current = Some(p.clone());
                    while current.is_some() && p.0 == self.last_readkey[idx] && dupno < self.last_dupno[idx] {
                        current = tree.next(&p);
                        if let Some(q) = &current { p = q.clone(); dupno = Self::dupno(&tree.at(&p).1, primekeylen); }
                    }
                    if current.is_some() && p.0 == self.last_readkey[idx] && dupno == self.last_dupno[idx] {
                        ok = tree.at(&p).1[..primekeylen] == self.last_readkey[idx + n][..];
                    }
                } else {
                    ok = tree.at(position.as_ref().unwrap()).1[..primekeylen] == self.last_readkey[idx + n][..];
                }
                position = None;
                if ok {
                    match self.db[0].get(&self.last_readkey[idx + n]) {
                        Some(data) => { self.key = self.last_readkey[idx + n].clone(); self.data = Some(data.clone()); position = Some((Vec::new(), 0)); },
                        None => {},
                    }
                }
            } else if let Some(p) = &position {
                let (key, data) = tree.at(p);
                self.key = key;
                self.data = Some(data);
            }
            file_changed = position.is_none();
        }
        if self.first_read == 0 || file_changed {
            let tree = &self.db[idx];
            let target = if first {
                tree.first()
            } else {
                let mut read_next = false;
                let found = tree.set_range(&self.last_readkey[idx]);
                let mut position = match found {
                    None => return 10,
                    Some(p) => p,
                };
                if position.0 == self.last_readkey[idx] {
                    if duplicates {
                        let mut dupno = Self::dupno(&tree.at(&position).1, primekeylen);
                        let mut current = Some(position.clone());
                        while current.is_some() && position.0 == self.last_readkey[idx] && dupno < self.last_dupno[idx] {
                            current = tree.next(&position);
                            if let Some(q) = &current { position = q.clone(); dupno = Self::dupno(&tree.at(&position).1, primekeylen); }
                        }
                        if current.is_none() { return 10; }
                        read_next = position.0 == self.last_readkey[idx] && dupno == self.last_dupno[idx];
                    } else {
                        read_next = true;
                    }
                }
                if read_next { tree.next(&position) } else { Some(position) }
            };
            let Some(position) = target else { return 10 };
            let (found_key, found_data) = tree.at(&position);
            let mut dupno = 0;
            if idx > 0 {
                if duplicates { dupno = Self::dupno(&found_data, primekeylen); }
                let prime = found_data[..primekeylen].to_vec();
                match self.db[0].get(&prime) {
                    Some(data) => { self.data = Some(data.clone()); },
                    None => return 23,
                }
                self.key = prime.clone();
                self.last_readkey[idx] = found_key;
                self.last_readkey[idx + n] = prime;
                if duplicates { self.last_dupno[idx] = dupno; }
            } else {
                self.key = found_key.clone();
                self.data = Some(found_data);
                self.last_readkey[0] = found_key;
            }
        }
        self.store_record(area)
    }

    /// cob_write then indexed_write.
    pub fn write(&mut self, area: &Value, size: usize, depending: Option<&Value>) -> u8 {
        self.read_done = false;
        let allowed = if self.access == Access::Sequential { ["OUTPUT", "EXTEND"] } else { ["OUTPUT", "I-O"] };
        if !allowed.contains(&self.open_mode) { return 48; }
        let size = record_size(size, depending);
        if size < self.record_min || size > self.record_max { return 44; }
        if self.nonexistent { return 48; }
        let record = area.bytes()[..size].to_vec();
        let full = area.bytes();
        let key = self.savekey(&full, 0);
        if let Some(last) = &self.last_key {
            if self.access == Access::Sequential && last[..] > key[..] { return 21; }
        }
        self.last_key = Some(key.clone());
        self.key = key;
        let status = self.write_internal(&full, &record, false);
        if self.access == Access::Sequential && self.open_mode == "OUTPUT" && status == 22 { return 21; }
        status
    }

    /// check_alt_keys: an alternate key without DUPLICATES already used
    /// (by another record, for a REWRITE).
    fn check_alt_keys(&self, full: &[u8], rewrite: bool) -> bool {
        (1..self.keys.len()).any(|i| !self.keys[i].duplicates && match self.db[i].get(&self.savekey(full, i)) {
            Some(prime) => !rewrite || self.cmpkey(prime, full, 0, 0) != std::cmp::Ordering::Equal,
            None => false,
        })
    }

    fn write_internal(&mut self, full: &[u8], record: &[u8], rewrite: bool) -> u8 {
        if self.keys.len() > 1 && !rewrite {
            if self.check_alt_keys(full, false) { return 22; }
            self.key = self.savekey(full, 0);
        }
        if self.db[0].set(&self.key).is_some() { return 22; }
        let prime = self.key.clone();
        self.db[0].put(&prime, record, false, false);
        let primekeylen = self.primekeylen();
        for i in 1..self.keys.len() {
            if rewrite && !self.rewrite_sec_key[i] { continue; }
            let altkey = self.savekey(full, i);
            let mut data = self.savekey(full, 0);
            let duplicates = self.keys[i].duplicates;
            if duplicates {
                // get_dupno: one more than the last duplicate of this key.
                let last = self.db[i].entries.get(&altkey).and_then(|list| list.last())
                    .map(|d| Self::dupno(d, primekeylen)).unwrap_or(0);
                // libcob sets 02 for a duplicate, then overwrites it with the
                // DB_PUT result: the BDB handler never returns 02.
                let dupno = last + 1;
                data.extend(dupno.to_le_bytes());
            }
            if !self.db[i].put(&altkey, &data, !duplicates, duplicates) { return 22; }
        }
        0
    }

    /// cob_delete then indexed_delete.
    pub fn delete(&mut self, area: &Value) -> u8 {
        let read_done = self.read_done;
        self.read_done = false;
        if self.open_mode != "I-O" { return 49; }
        if self.access == Access::Sequential && !read_done { return 43; }
        if self.nonexistent { return 49; }
        self.delete_internal(&area.bytes(), false)
    }

    fn delete_internal(&mut self, full: &[u8], rewrite: bool) -> u8 {
        if self.access != Access::Sequential { self.key = self.savekey(full, 0); }
        let prime = self.key.clone();
        let Some(position) = self.db[0].set(&prime) else {
            if self.access != Access::Sequential { return 23; }
            // A sequential DELETE whose record vanished: DB_CDEL fails silently.
            return 0;
        };
        let saverec = self.db[0].at(&position).1;
        let primekeylen = self.primekeylen();
        for i in 1..self.keys.len() {
            let key = self.savekey(&saverec, i);
            if rewrite {
                self.rewrite_sec_key[i] = self.cmpkey(&key, full, i, 0) != std::cmp::Ordering::Equal;
                if !self.rewrite_sec_key[i] { continue; }
            }
            if !self.keys[i].duplicates {
                self.db[i].delete_key(&key);
            } else if let Some(list) = self.db[i].entries.get(&key) {
                if let Some(at) = list.iter().position(|d| d[..primekeylen] == prime[..]) {
                    self.db[i].delete(&(key.clone(), at));
                }
            }
        }
        self.db[0].delete(&position);
        0
    }

    /// cob_rewrite then indexed_rewrite.
    pub fn rewrite(&mut self, area: &Value, size: usize, depending: Option<&Value>) -> u8 {
        let read_done = self.read_done;
        self.read_done = false;
        if self.open_mode != "I-O" { return 49; }
        if self.access == Access::Sequential && !read_done { return 43; }
        let size = record_size(size, depending);
        if depending.is_some() && (size < self.record_min || size > self.record_max) { return 44; }
        if self.nonexistent { return 49; }
        let full = area.bytes();
        let record = full[..size].to_vec();
        if self.check_alt_keys(&full, true) { return 22; }
        let status = self.delete_internal(&full, true);
        if status != 0 { return if status == 23 { 21 } else { status }; }
        self.key = self.savekey(&full, 0);
        self.write_internal(&full, &record, true)
    }
}

impl Drop for IndexedFile {
    fn drop(&mut self) {
        if !self.open_mode.is_empty() { self.close(false); }
    }
}
