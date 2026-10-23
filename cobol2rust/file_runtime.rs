// GnuCOBOL 3.2 default file profile: LINE SEQUENTIAL and fixed SEQUENTIAL.
use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, BufReader, Read, Write};
use crate::runtime::{Value, fail};

enum State { Closed, Locked, Input(BufReader<File>), Output(File), Missing }

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
               needs_nl: false, last_read_size: 0, last_open_mode: "" }
    }

    /// Mode of the last OPEN attempt, kept by an OPEN rejected as already open.
    pub fn last_open_mode(&self) -> &'static str { self.last_open_mode }

    pub fn open(&mut self, mode: &str) -> u8 {
        // CLOSE WITH LOCK forbids any later OPEN in the run unit.
        if matches!(self.state, State::Locked) { return 38; }
        if !matches!(self.state, State::Closed) { return 41; }
        self.last_open_mode = match mode {
            "INPUT" => "INPUT", "OUTPUT" => "OUTPUT", "EXTEND" => "EXTEND",
            _ => fail("unsupported file open mode"),
        };
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
        if let State::Output(file) = &mut self.state {
            if self.needs_nl {
                file.write_all(b"\n").unwrap_or_else(|e| fail(&format!("file closing newline failed: {e}")));
            }
            file.flush().unwrap_or_else(|e| fail(&format!("file flush failed: {e}")));
        }
        self.state = if lock { State::Locked } else { State::Closed };
        self.eof = false;
        self.needs_nl = false;
        self.last_read_size = 0;
        0
    }

    pub fn last_read_size(&self) -> usize { self.last_read_size }

    pub fn read(&mut self, record: &mut Value) -> u8 {
        self.last_read_size = 0;
        if !matches!(self.state, State::Input(_) | State::Missing) { return 47; }
        if self.eof { return 46; }
        if matches!(self.state, State::Missing) { self.eof = true; return 10; }
        let size = record.text_size();
        let reader = match &mut self.state { State::Input(reader) => reader, _ => unreachable!() };
        if self.organization == Organization::Sequential {
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

    pub fn write(&mut self, record: &Value, advancing: Option<Advance>) -> u8 {
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
pub fn file_status(status: u8, destination: Option<&mut Value>, eof_handled: bool, declarative: bool) {
    if let Some(field) = destination {
        let status = format!("{status:02}");
        if field.is_text() { field.assign(&Value::text(&status), false); }
        else { field.assign(&Value::number(&status), false); }
    } else if !matches!(status, 0 | 5) && !(status == 10 && eof_handled) && !(status >= 10 && declarative) {
        fail(&format!("unhandled file status {status:02}"));
    }
}
