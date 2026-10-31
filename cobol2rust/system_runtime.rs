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
        "SYSTEM" | "C$SLEEP" | "C$GETPID" | "C$JUSTIFY" | "C$PRINTABLE")
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
