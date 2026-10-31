// GnuCOBOL 3.2 common.c cob_sys_{and,or,nor,xor,imp,nimp,eq,not,to{upper,lower}}.
use crate::runtime::{fail, Value};
use crate::storage_runtime::{Kind, View};

#[derive(Clone, Copy)]
enum Operation { And, Or, Nor, Xor, Imp, Nimp, Eq, Not, Upper, Lower }

fn operation(name: &str) -> Option<(Operation, usize)> {
    use Operation::*;
    let name = name.rsplit(['/', '\\']).next().unwrap_or(name);
    Some(match name {
        "CBL_AND" => (And, 3),
        "CBL_OR" => (Or, 3),
        "CBL_NOR" => (Nor, 3),
        "CBL_XOR" => (Xor, 3),
        "CBL_IMP" => (Imp, 3),
        "CBL_NIMP" => (Nimp, 3),
        "CBL_EQ" => (Eq, 3),
        "CBL_NOT" => (Not, 2),
        "CBL_TOUPPER" | "C$TOUPPER" => (Upper, 2),
        "CBL_TOLOWER" | "C$TOLOWER" => (Lower, 2),
        _ => return None,
    })
}

pub fn known(name: &str) -> bool {
    operation(name).is_some() || matches!(name.rsplit(['/', '\\']).next().unwrap_or(name),
        "SYSTEM" | "C$SLEEP" | "C$GETPID" | "C$JUSTIFY" | "C$PRINTABLE" | "CBL_GC_GETOPT")
}

fn unsupported(name: &str, reason: &str) -> ! {
    fail(&format!("routine système {name}: {reason}"))
}

fn address<'a>(name: &str, argument: &'a Value, count: usize) -> &'a View {
    let Value::View(view) = argument else {
        unsupported(name, "adresse de stockage requise pour les octets");
    };
    if view.memory.borrow().is_empty() {
        unsupported(name, "adresse NULL ou LINKAGE non transmise");
    }
    let end = view.offset.checked_add(count)
        .unwrap_or_else(|| unsupported(name, "dépassement de l'adresse de stockage"));
    if end > view.memory.borrow().len() || view.limit.is_some_and(|limit| end > limit) {
        unsupported(name, "accès au-delà de l'allocation de stockage non modélisé");
    }
    view
}

fn byte(view: &View, offset: usize) -> u8 {
    crate::storage_runtime::check_defined(&view.memory, view.offset + offset, 1);
    view.memory.borrow()[view.offset + offset]
}

fn put(view: &View, offset: usize, value: u8) {
    // Keep mem_mut's protection of literal arguments, without PICTURE conversion.
    let mut target = View { memory: view.memory.clone(), offset: view.offset + offset, size: 1,
        kind: Kind::Text, dimensions: vec![], initializers: vec![], limit: view.limit };
    target.assign_text_move(&Value::Bytes(vec![value]), true);
}

#[cfg(target_os = "linux")]
fn case_table(upper: bool) -> &'static [u8; 256] {
    use std::ffi::{c_char, c_int, c_void};
    extern "C" {
        fn newlocale(mask: c_int, name: *const c_char, base: *mut c_void) -> *mut c_void;
        fn freelocale(locale: *mut c_void);
        fn toupper_l(byte: c_int, locale: *mut c_void) -> c_int;
        fn tolower_l(byte: c_int, locale: *mut c_void) -> c_int;
    }
    static TABLES: std::sync::OnceLock<([u8; 256], [u8; 256])> = std::sync::OnceLock::new();
    let tables = TABLES.get_or_init(|| {
        // cob_init: LC_CTYPE is reset to C after reading the user's locale.
        // Linux's LC_CTYPE is category 0, hence LC_CTYPE_MASK = 1.
        let locale = unsafe { newlocale(1, b"C\0".as_ptr().cast(), std::ptr::null_mut()) };
        if locale.is_null() { fail("routine système: impossible de créer la locale C de LC_CTYPE"); }
        let mut upper = [0; 256];
        let mut lower = [0; 256];
        for n in 0..256 {
            upper[n] = unsafe { toupper_l(n as c_int, locale) as u8 };
            lower[n] = unsafe { tolower_l(n as c_int, locale) as u8 };
        }
        unsafe { freelocale(locale); }
        (upper, lower)
    });
    if upper { &tables.0 } else { &tables.1 }
}

#[cfg(not(target_os = "linux"))]
fn case_table(_upper: bool) -> &'static [u8; 256] {
    fail("routines système de casse: profil LC_CTYPE natif hors Linux non pris en charge")
}

/// common.c routines without module state: SYSTEM, C$SLEEP, C$GETPID,
/// C$JUSTIFY and C$PRINTABLE (cob_procedure_params[0]->size is the size).
fn library_routine(name: &str, arguments: &[Value]) -> Option<i32> {
    use crate::storage_runtime::{descriptor_size, parameter_bytes, store_parameter};
    let name = name.rsplit(['/', '\\']).next().unwrap_or(name);
    if !matches!(name, "SYSTEM" | "C$SLEEP" | "C$GETPID" | "C$JUSTIFY" | "C$PRINTABLE") { return None; }
    if name == "C$GETPID" { return Some(std::process::id() as i32); }
    let Some(first) = arguments.first() else { unsupported(name, "argument absent (pas de COB_PARAM_CHECK)") };
    let Some(mut data) = parameter_bytes(first) else { return Some(0) };
    let size = descriptor_size(first);
    Some(match name {
        "SYSTEM" => {
            // cob_sys_system: trailing spaces and NULs dropped down to index 1;
            // a command whose last significant byte is the first is not run.
            if size == 0 { unsupported(name, "commande vide"); }
            let mut i = size - 1;
            loop {
                if data[i] != b' ' && data[i] != 0 { break; }
                i -= 1;
                if i == 0 { break; }
            }
            if i == 0 { return Some(1); }
            if i > 8191 { unsupported(name, "commande au-delà de COB_MEDIUM_MAX"); }
            let command = std::ffi::CString::new(data[..=i].to_vec()).unwrap_or_else(|_| unsupported(name, "commande avec NUL interne"));
            extern "C" { fn system(command: *const std::ffi::c_char) -> std::ffi::c_int; }
            let status = unsafe { system(command.as_ptr()) };
            if status & 0x7f != 0 && status & 0x7f != 0x7f {
                unsupported(name, "processus externe terminé par un signal (avertissement de libcob non modélisé)");
            }
            status
        },
        "C$SLEEP" => {
            // get_sleep_nanoseconds_from_seconds: cob_get_llint, then the
            // seconds moved to nanoseconds; one week at most.
            let seconds = first.integer("C$SLEEP");
            if seconds < 0 { return Some(-1); }
            let nanoseconds = if seconds >= 3600 * 24 * 7 { 3600 * 24 * 7 * 1_000_000_000 }
                              else { first.num().units(9, false).to_string().parse::<i128>().unwrap_or(0) };
            if nanoseconds > 0 { std::thread::sleep(std::time::Duration::from_nanos(nanoseconds as u64)); }
            0
        },
        "C$JUSTIFY" => {
            if size < 2 || (data[0] != b' ' && data[size - 1] != b' ') { return Some(0); }
            let left = data.iter().take_while(|&&b| b == b' ').count();
            if left == size { return Some(0); }
            let right = data.iter().rev().take_while(|&&b| b == b' ').count();
            let movelen = size - left - right;
            let direction = if arguments.len() > 1 { parameter_bytes(&arguments[1]).and_then(|d| d.first().copied()) } else { None };
            let word = data[left..left + movelen].to_vec();
            let mut result = vec![b' '; size];
            match direction {
                Some(b'L') => result[..movelen].copy_from_slice(&word),
                Some(b'C') => { let centre = (left + right) / 2; result[centre..centre + movelen].copy_from_slice(&word); },
                _ => result[left + right..].copy_from_slice(&word),
            }
            store_parameter(first, 0, &result);
            0
        },
        _ => {
            // C$PRINTABLE: isprint in the user's LC_CTYPE (cob_locale_ctype).
            let replacement = if arguments.len() > 1 {
                parameter_bytes(&arguments[1]).and_then(|d| d.first().copied()).unwrap_or_else(|| unsupported(name, "remplacement à une adresse NULL"))
            } else { b'.' };
            let table = printable_table();
            for byte in data.iter_mut() { if !table[*byte as usize] { *byte = replacement; } }
            store_parameter(first, 0, &data);
            0
        },
    })
}

#[cfg(target_os = "linux")]
fn printable_table() -> &'static [bool; 256] {
    use std::ffi::{c_char, c_int, c_void};
    extern "C" {
        fn newlocale(mask: c_int, name: *const c_char, base: *mut c_void) -> *mut c_void;
        fn isprint_l(byte: c_int, locale: *mut c_void) -> c_int;
    }
    static TABLE: std::sync::OnceLock<[bool; 256]> = std::sync::OnceLock::new();
    TABLE.get_or_init(|| {
        // cob_init saves setlocale (LC_CTYPE, "") as cob_locale_ctype.
        let locale = unsafe { newlocale(1, b"\0".as_ptr().cast(), std::ptr::null_mut()) };
        if locale.is_null() { fail("C$PRINTABLE: locale LC_CTYPE de l'utilisateur indisponible"); }
        let mut table = [false; 256];
        for (n, entry) in table.iter_mut().enumerate() { *entry = unsafe { isprint_l(n as c_int, locale) } != 0; }
        table
    })
}

#[cfg(not(target_os = "linux"))]
fn printable_table() -> &'static [bool; 256] {
    fail("C$PRINTABLE: profil LC_CTYPE natif hors Linux non pris en charge")
}

/// System routines receive raw addresses, not COBOL field descriptions.
/// The final consumed argument is the C int already prepared by BY VALUE.
pub fn call(name: &str, arguments: &[Value], modes: &[&str]) -> Option<i32> {
    if name.rsplit(['/', '\\']).next() == Some("CBL_GC_GETOPT") { return Some(getopt::call(arguments, modes)); }
    if let Some(code) = library_routine(name, arguments) { return Some(code); }
    let (operation, arity) = operation(name)?;
    if !cfg!(all(target_os = "linux", target_arch = "x86_64")) {
        unsupported(name, "profil ABI scalaire Linux x86_64 requis");
    }
    if arguments.len() < arity {
        unsupported(name, &format!("{arity} arguments requis"));
    }
    if modes.len() != arguments.len() {
        unsupported(name, "modes de passage incohérents avec les arguments");
    }
    let length_index = arity - 1;
    if modes[length_index] != "VALUE" {
        unsupported(name, "longueur requise BY VALUE en entier C");
    }
    let Value::Num(_, _) = arguments[length_index] else {
        unsupported(name, "longueur BY VALUE non préparée comme entier C");
    };
    let length = arguments[length_index].integer("system routine C int length");
    if length < i32::MIN as i128 || length > i32::MAX as i128 {
        unsupported(name, "longueur hors de la plage C int");
    }
    if length <= 0 { return Some(0); }
    let count = length as usize;
    for mode in &modes[..length_index] {
        if !matches!(*mode, "REFERENCE" | "CONTENT") {
            unsupported(name, "adresse requise BY REFERENCE ou BY CONTENT");
        }
    }
    let first = address(name, &arguments[0], count);
    let second = if arity == 3 { Some(address(name, &arguments[1], count)) } else { None };
    let casing = match operation {
        Operation::Upper => Some(case_table(true)),
        Operation::Lower => Some(case_table(false)),
        _ => None,
    };
    for n in 0..count {
        // Read each source byte after the previous write, preserving aliases.
        let a = byte(first, n);
        if let Some(second) = second {
            let b = byte(second, n);
            let result = match operation {
                Operation::And => a & b,
                Operation::Or => a | b,
                Operation::Nor => !(a | b),
                Operation::Xor => a ^ b,
                Operation::Imp => !a | b,
                Operation::Nimp => a & !b,
                Operation::Eq => !(a ^ b),
                _ => unreachable!(),
            };
            put(second, n, result);
        } else {
            put(first, n, casing.map_or(!a, |table| table[a as usize]));
        }
    }
    Some(0)
}

/// common.c cob_sys_getopt_long_long over cobgetopt.c cob_getopt_long_long:
/// the static scan state (optind, nextchar, the permutation of argv) lives
/// for the run unit, as in libcob.
pub mod getopt {
    use crate::runtime::{fail, fatal_error, Value};
    use crate::storage_runtime::{descriptor_size, parameter_bytes, store_at_address, store_parameter};
    use std::cell::RefCell;
    use std::io::Write;

    #[derive(Clone, Copy, PartialEq)]
    enum Ordering { Require, Permute, ReturnInOrder }

    struct LongOption { name: Vec<u8>, has_arg: i32, flag: u64, val: i32 }

    /// A `char *` into an argv string: (string, offset). The strings keep
    /// their identity while `exchange` permutes argv, as the C pointers do.
    type Pointer = (usize, usize);

    struct State {
        strings: Vec<Vec<u8>>,
        argv: Vec<usize>,
        initialized: bool,
        nextchar: Option<Pointer>,
        ordering: Ordering,
        first_nonopt: usize,
        last_nonopt: usize,
        optind: usize,
        optarg: Option<Pointer>,
        optopt: i32,
    }

    thread_local! {
        static STATE: RefCell<Option<State>> = const { RefCell::new(None) };
    }

    fn unsupported(reason: &str) -> ! { fail(&format!("routine système CBL_GC_GETOPT: {reason}")) }

    /// strchr: the terminating NUL is found too.
    fn strchr(s: &[u8], c: u8) -> Option<usize> { s.iter().position(|&b| b == c || b == 0).filter(|&i| s[i] == c) }

    impl State {
        fn new() -> Self {
            use std::os::unix::ffi::OsStringExt;
            let strings: Vec<Vec<u8>> = std::env::args_os().map(|a| { let mut s = a.into_vec(); s.push(0); s }).collect();
            let argv = (0..strings.len()).collect();
            State { strings, argv, initialized: false, nextchar: None, ordering: Ordering::Permute,
                    first_nonopt: 1, last_nonopt: 1, optind: 1, optarg: None, optopt: b'?' as i32 }
        }
        fn byte(&self, p: Pointer) -> u8 { self.strings[p.0][p.1] }
        fn cstr(&self, p: Pointer) -> Vec<u8> {
            let s = &self.strings[p.0][p.1..];
            s[..s.iter().position(|&b| b == 0).unwrap()].to_vec()
        }
        fn arg(&self, index: usize) -> &[u8] { &self.strings[self.argv[index]] }
        fn nonoption(&self) -> bool { let s = self.arg(self.optind); s[0] != b'-' || s[1] == 0 }
        fn error(&self, text: &[u8]) {
            let mut err = std::io::stderr().lock();
            let _ = err.write_all(&self.cstr((self.argv[0], 0)));
            let _ = err.write_all(b": ");
            let _ = err.write_all(text);
            let _ = err.write_all(b"\n");
        }

        fn exchange(&mut self) {
            let (mut bottom, middle, mut top) = (self.first_nonopt, self.last_nonopt, self.optind);
            while top > middle && middle > bottom {
                if top - middle > middle - bottom {
                    let len = middle - bottom;
                    for i in 0..len { self.argv.swap(bottom + i, top - (middle - bottom) + i); }
                    top -= len;
                } else {
                    let len = top - middle;
                    for i in 0..len { self.argv.swap(bottom + i, middle + i); }
                    bottom += len;
                }
            }
            self.first_nonopt += self.optind - self.last_nonopt;
            self.last_nonopt = self.optind;
        }

        #[allow(clippy::too_many_arguments)]
        fn process_long_option(&mut self, optstring: &[u8], longopts: &[LongOption], longind: &mut i32,
                               long_only: bool, print_errors: bool, prefix: &[u8]) -> i32 {
            let argc = self.argv.len();
            let start = self.nextchar.unwrap();
            let rest = self.cstr(start);
            let namelen = rest.iter().position(|&b| b == b'=').unwrap_or(rest.len());
            let name = &rest[..namelen];
            let mut pfound = longopts.iter().position(|p| p.name == name);
            let mut option_index = pfound.unwrap_or(0);
            if pfound.is_none() {
                let mut ambig_set: Option<Vec<bool>> = None;
                let mut ambig_fallback = false;
                let mut indfound = 0;
                for (index, p) in longopts.iter().enumerate() {
                    if !p.name.starts_with(name) { continue; }
                    match pfound {
                        None => { pfound = Some(index); indfound = index; },
                        Some(found) => {
                            let f = &longopts[found];
                            if (long_only || f.has_arg != p.has_arg || f.flag != p.flag || f.val != p.val) && !ambig_fallback {
                                if !print_errors {
                                    ambig_fallback = true;
                                } else if ambig_set.is_none() {
                                    let mut set = vec![false; longopts.len()];
                                    set[indfound] = true;
                                    ambig_set = Some(set);
                                }
                                if let Some(set) = ambig_set.as_mut() { set[index] = true; }
                            }
                        },
                    }
                }
                if ambig_set.is_some() || ambig_fallback {
                    if print_errors {
                        let mut text = [&b"option '"[..], prefix, &rest, b"' is ambiguous"].concat();
                        if let Some(set) = &ambig_set {
                            text.extend_from_slice(b"; possibilities:");
                            for (index, p) in longopts.iter().enumerate() {
                                if set[index] { text.extend([&b" '"[..], prefix, &p.name, b"'"].concat()); }
                            }
                        }
                        self.error(&text);
                    }
                    self.nextchar = Some((start.0, start.1 + rest.len()));
                    self.optind += 1;
                    self.optopt = 0;
                    return b'?' as i32;
                }
                option_index = indfound;
            }
            let Some(found) = pfound else {
                if !long_only || self.arg(self.optind)[1] == b'-' || strchr(optstring, self.byte(start)).is_none() {
                    if print_errors { self.error(&[&b"unrecognized option '"[..], prefix, &rest, b"'"].concat()); }
                    self.nextchar = None;
                    self.optind += 1;
                    self.optopt = 0;
                    return b'?' as i32;
                }
                return -1;
            };
            let p = &longopts[found];
            self.optind += 1;
            self.nextchar = None;
            if namelen < rest.len() {
                if p.has_arg != 0 {
                    self.optarg = Some((start.0, start.1 + namelen + 1));
                } else {
                    if print_errors { self.error(&[&b"option '"[..], prefix, &p.name, b"' doesn't allow an argument"].concat()); }
                    self.optopt = p.val;
                    return b'?' as i32;
                }
            } else if p.has_arg == 1 {
                if self.optind < argc {
                    self.optarg = Some((self.argv[self.optind], 0));
                    self.optind += 1;
                } else {
                    if print_errors { self.error(&[&b"option '"[..], prefix, &p.name, b"' requires an argument"].concat()); }
                    self.optopt = p.val;
                    return if optstring[0] == b':' { b':' as i32 } else { b'?' as i32 };
                }
            }
            *longind = option_index as i32;
            if p.flag != 0 {
                store_at_address(p.flag, &p.val.to_le_bytes());
                return 0;
            }
            p.val
        }

        /// cob_getopt_long_long; `optstring` ends with its NUL.
        fn getopt(&mut self, mut optstring: &[u8], longopts: &[LongOption], longind: &mut i32, long_only: bool) -> i32 {
            let argc = self.argv.len();
            if argc < 1 { return -1; }
            self.optarg = None;
            if self.optind == 0 || !self.initialized {
                // _getopt_initialize
                if self.optind == 0 { self.optind = 1; }
                self.first_nonopt = self.optind;
                self.last_nonopt = self.optind;
                self.nextchar = None;
                if optstring[0] == b'-' {
                    self.ordering = Ordering::ReturnInOrder;
                    optstring = &optstring[1..];
                } else if optstring[0] == b'+' {
                    self.ordering = Ordering::Require;
                    optstring = &optstring[1..];
                } else if std::env::var_os("POSIXLY_CORRECT").is_some() {
                    self.ordering = Ordering::Require;
                } else {
                    self.ordering = Ordering::Permute;
                }
                self.initialized = true;
            } else if optstring[0] == b'-' || optstring[0] == b'+' {
                optstring = &optstring[1..];
            }
            let print_errors = optstring[0] != b':';
            if self.nextchar.is_none_or(|p| self.byte(p) == 0) {
                if self.last_nonopt > self.optind { self.last_nonopt = self.optind; }
                if self.first_nonopt > self.optind { self.first_nonopt = self.optind; }
                if self.ordering == Ordering::Permute {
                    if self.first_nonopt != self.last_nonopt && self.last_nonopt != self.optind {
                        self.exchange();
                    } else if self.last_nonopt != self.optind {
                        self.first_nonopt = self.optind;
                    }
                    while self.optind < argc && self.nonoption() { self.optind += 1; }
                    self.last_nonopt = self.optind;
                }
                if self.optind != argc && self.cstr((self.argv[self.optind], 0)) == b"--" {
                    self.optind += 1;
                    if self.first_nonopt != self.last_nonopt && self.last_nonopt != self.optind {
                        self.exchange();
                    } else if self.first_nonopt == self.last_nonopt {
                        self.first_nonopt = self.optind;
                    }
                    self.last_nonopt = argc;
                    self.optind = argc;
                }
                if self.optind == argc {
                    if self.first_nonopt != self.last_nonopt { self.optind = self.first_nonopt; }
                    return -1;
                }
                if self.nonoption() {
                    if self.ordering == Ordering::Require { return -1; }
                    self.optarg = Some((self.argv[self.optind], 0));
                    self.optind += 1;
                    return 1;
                }
                let current = self.argv[self.optind];
                let (second, third) = (self.strings[current][1], self.strings[current].get(2).copied().unwrap_or(0));
                if second == b'-' {
                    self.nextchar = Some((current, 2));
                    return self.process_long_option(optstring, longopts, longind, long_only, print_errors, b"--");
                }
                if long_only && (third != 0 || strchr(optstring, second).is_none()) {
                    self.nextchar = Some((current, 1));
                    let code = self.process_long_option(optstring, longopts, longind, long_only, print_errors, b"-");
                    if code != -1 { return code; }
                }
                self.nextchar = Some((current, 1));
            }
            let (id, offset) = self.nextchar.unwrap();
            let c = self.strings[id][offset];
            let signed = c as i8 as i32;
            self.nextchar = Some((id, offset + 1));
            if self.strings[id][offset + 1] == 0 { self.optind += 1; }
            let temp = strchr(optstring, c);
            let Some(temp) = temp.filter(|_| c != b':' && c != b';') else {
                if print_errors { self.error(&[&b"invalid option -- '"[..], &[c], b"'"].concat()); }
                self.optopt = signed;
                return b'?' as i32;
            };
            let missing = if optstring[0] == b':' { b':' as i32 } else { b'?' as i32 };
            if optstring[temp] == b'W' && optstring[temp + 1] == b';' {
                let next = self.nextchar.unwrap();
                if self.byte(next) != 0 {
                    self.optarg = Some(next);
                } else if self.optind == argc {
                    if print_errors { self.error(&[&b"option requires an argument -- '"[..], &[c], b"'"].concat()); }
                    self.optopt = signed;
                    return missing;
                } else {
                    self.optarg = Some((self.argv[self.optind], 0));
                }
                self.nextchar = self.optarg;
                self.optarg = None;
                return self.process_long_option(optstring, longopts, longind, false, print_errors, b"-W ");
            }
            if optstring[temp + 1] == b':' {
                let next = self.nextchar.unwrap();
                if optstring[temp + 2] == b':' {
                    if self.byte(next) != 0 {
                        self.optarg = Some(next);
                        self.optind += 1;
                    } else {
                        self.optarg = None;
                    }
                } else if self.byte(next) != 0 {
                    self.optarg = Some(next);
                    self.optind += 1;
                } else if self.optind == argc {
                    if print_errors { self.error(&[&b"option requires an argument -- '"[..], &[c], b"'"].concat()); }
                    self.optopt = signed;
                    self.nextchar = None;
                    return missing;
                } else {
                    self.optarg = Some((self.argv[self.optind], 0));
                    self.optind += 1;
                }
                self.nextchar = None;
            }
            signed
        }
    }

    /// cob_field_to_string: trailing spaces and NULs dropped (the first
    /// byte kept), then the C string up to its first NUL.
    fn field_string(data: &[u8]) -> Vec<u8> {
        if data.is_empty() { return vec![0]; }
        let mut end = data.len() - 1;
        while end > 0 && (data[end] == b' ' || data[end] == 0) { end -= 1; }
        if data[end] == b' ' || data[end] == 0 { return vec![0]; }
        let mut s: Vec<u8> = data[..=end].iter().copied().take_while(|&b| b != 0).collect();
        s.push(0);
        s
    }

    /// The bytes behind a parameter: None for a NULL cob_field (OMITTED),
    /// a stop for a field without storage (its data would be NULL).
    fn data(argument: &Value) -> Option<Vec<u8>> {
        let bytes = parameter_bytes(argument);
        if bytes.is_none() && descriptor_size(argument) != 0 { unsupported("paramètre sans adresse (pointeur NULL)"); }
        bytes
    }

    pub fn call(arguments: &[Value], modes: &[&str]) -> i32 {
        const DEF: usize = 25 + 1 + 8 + 4; // longoption_def
        if arguments.len() < 6 { unsupported("moins de six arguments (pas de COB_PARAM_CHECK)"); }
        if modes.len() != arguments.len() { unsupported("modes de passage incohérents avec les arguments"); }
        if modes[3] != "VALUE" { unsupported("long-only requis BY VALUE (entier C)"); }
        if [0, 1, 2, 4, 5].iter().any(|&i| modes[i] == "VALUE") { unsupported("argument d'adresse passé BY VALUE"); }
        let so = data(&arguments[0]);
        let lo = data(&arguments[1]);
        let lo_size = lo.as_ref().map_or(0, |bytes| bytes.len());
        if lo_size % DEF != 0 { fatal_error(b"call to CBL_GC_GETOPT with wrong longoption size"); }
        if data(&arguments[2]).is_none() { fatal_error(b"call to CBL_GC_GETOPT with missing longind"); }
        let mut longind = arguments[2].integer("CBL_GC_GETOPT") as i32;
        let long_only = arguments[3].integer("CBL_GC_GETOPT") as i32 != 0;
        let shortoptions = so.as_deref().map_or(vec![0], field_string);
        let mut longoptions = Vec::new();
        if let Some(mut bytes) = lo {
            for base in (0..lo_size).step_by(DEF) {
                let mut j = 24;
                while bytes[base + j] == b' ' {
                    bytes[base + j] = 0;
                    if j == 0 { break; }
                    j -= 1;
                }
                let Some(length) = bytes[base..].iter().position(|&b| b == 0) else {
                    unsupported("nom d'option longue sans NUL dans la zone des options (lecture au-delà)");
                };
                longoptions.push(LongOption {
                    name: bytes[base..base + length].to_vec(),
                    has_arg: (bytes[base + 25] & 0x0F) as i32,
                    flag: u64::from_le_bytes(bytes[base + 26..base + 34].try_into().unwrap()),
                    val: i32::from_le_bytes(bytes[base + 34..base + 38].try_into().unwrap()),
                });
            }
            store_parameter(&arguments[1], 0, &bytes);
        }
        let (return_value, optarg) = STATE.with(|state| {
            let mut state = state.borrow_mut();
            let state = state.get_or_insert_with(State::new);
            let value = state.getopt(&shortoptions, &longoptions, &mut longind, long_only);
            (value, state.optarg.map(|p| state.cstr(p)))
        });
        let mut temp = return_value.to_le_bytes();
        let mut exit_status = if matches!(temp[0], b'?' | b':' | b'W' | 0xFF | 0) { return_value } else { 3 };
        for i in (1..=3).rev() {
            if temp[i] == 0 { temp[i] = b' '; } else { break; }
        }
        arguments[2].clone().move_number(&Value::number(&longind.to_string()));
        store_parameter(&arguments[4], 0, &temp);
        if let Some(optarg) = optarg {
            let opt_val = data(&arguments[5]);
            let size = opt_val.as_ref().map_or(0, |bytes| bytes.len());
            if opt_val.is_some() { store_parameter(&arguments[5], 0, &vec![0; size]); }
            let length = if optarg.len() > size { exit_status = 2; size } else { optarg.len() };
            if length > 0 { store_parameter(&arguments[5], 0, &optarg[..length]); }
        }
        exit_status
    }
}
