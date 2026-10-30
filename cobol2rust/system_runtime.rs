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

pub fn known(name: &str) -> bool { operation(name).is_some() }

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

fn byte(view: &View, offset: usize) -> u8 { view.memory.borrow()[view.offset + offset] }

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

/// System routines receive raw addresses, not COBOL field descriptions.
/// The final consumed argument is the C int already prepared by BY VALUE.
pub fn call(name: &str, arguments: &[Value], modes: &[&str]) -> Option<i32> {
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
