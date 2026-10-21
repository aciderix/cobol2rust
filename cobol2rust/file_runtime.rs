// LINE SEQUENTIAL, printable ASCII records. File errors are visible as COBOL statuses.
use std::fs::{File, OpenOptions};
use std::io::{self, BufRead, BufReader, Write};
use crate::runtime::{Value, fail};

enum State { Closed, Input(BufReader<File>), Output(File), Missing }

pub struct LineFile {
    path: String,
    optional: bool,
    state: State,
    eof: bool,
    fixed: bool,
    split: bool,
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

impl LineFile {
    pub fn new(path: &str, optional: bool) -> Self {
        // Unknown profile/remapping settings must not silently change the reference behavior.
        for key in ["COB_RUNTIME_CONFIG", "COB_FILE_PATH", "COB_UNIX_LF", "COB_LS_NULLS", "COB_LS_USES_CR"] {
            if std::env::var_os(key).is_some() { fail(&format!("file runtime setting not supported: {key}")); }
        }
        for key in [path.to_string(), format!("DD_{path}"), format!("dd_{path}")] {
            if std::env::var_os(&key).is_some() { fail("file name environment remapping not supported"); }
        }
        Self { path: path.into(), optional, state: State::Closed, eof: false,
               fixed: setting("COB_LS_FIXED", false), split: setting("COB_LS_SPLIT", true) }
    }

    pub fn open(&mut self, mode: &str) -> u8 {
        if !matches!(self.state, State::Closed) { return 41; }
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

    pub fn close(&mut self) -> u8 {
        if matches!(self.state, State::Closed) { return 42; }
        if let State::Output(file) = &mut self.state {
            file.flush().unwrap_or_else(|e| fail(&format!("file flush failed: {e}")));
        }
        self.state = State::Closed;
        self.eof = false;
        0
    }

    pub fn read(&mut self, record: &mut Value) -> u8 {
        if !matches!(self.state, State::Input(_) | State::Missing) { return 47; }
        if self.eof { return 46; }
        if matches!(self.state, State::Missing) { self.eof = true; return 10; }
        let size = record.text_size();
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
        let text = std::str::from_utf8(&line[..line.len().min(size)]).unwrap();
        record.assign(&Value::text(text), false);
        status
    }

    pub fn write(&mut self, record: &Value) -> u8 {
        let file = match &mut self.state { State::Output(file) => file, _ => return 48 };
        let bytes = record.bytes();
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

pub fn file_status(status: u8, destination: Option<&mut Value>, eof_handled: bool) {
    if let Some(field) = destination {
        let status = format!("{status:02}");
        if field.is_text() { field.assign(&Value::text(&status), false); }
        else { field.assign(&Value::number(&status), false); }
    } else if !matches!(status, 0 | 5) && !(status == 10 && eof_handled) {
        fail(&format!("unhandled file status {status:02}"));
    }
}
