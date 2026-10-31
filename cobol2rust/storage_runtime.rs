// Shared COBOL storage. Views preserve group/element/REDEFINES aliasing.
use std::cell::RefCell;
use std::rc::Rc;
use num_bigint::{BigInt, Sign};
use crate::runtime::{Value, Number, SizeError, fail, absolute, power};

pub type Memory = Rc<RefCell<Vec<u8>>>;
pub fn memory(size: usize) -> Memory { Rc::new(RefCell::new(vec![0; size])) }

thread_local! {
    static EXTERNALS: RefCell<std::collections::HashMap<String, Memory>> = RefCell::new(std::collections::HashMap::new());
}

/// GLOBAL storage of a program with contained programs: shared with them by
/// name, cleared when the declaring program gets a new instance (CANCEL).
pub fn owned_block(name: &str, size: usize) -> Memory {
    let block = external(name, size);
    block.borrow_mut().fill(0);
    block
}

/// cob_external_addr: the run unit's storage of an EXTERNAL item, created
/// zero-filled by its first program; a different size is not modelled
/// (libcob stops on a larger one and warns on a smaller one).
/// cob_external_addr: the item allocated by its first declaration; a larger
/// one is a runtime error, a smaller one a warning.
pub fn external(name: &str, size: usize) -> Memory {
    let block = EXTERNALS.with(|externals| externals.borrow_mut().entry(name.to_string()).or_insert_with(|| memory(size)).clone());
    let stored = block.borrow().len();
    let message = format!("EXTERNAL item '{name}' previously allocated with size {stored}, requested size is {size}");
    if size > stored { crate::runtime::fatal_error(message.as_bytes()); }
    if size < stored { eprintln!("libcob: warning: {message}"); }
    block
}

#[derive(Clone, Copy, Debug)]
pub enum Usage {
    Display, Packed, Binary, Index,
    /// COMP-6: packed decimal without sign nibble (COB_FLAG_NO_SIGN_NIBBLE).
    PackedNoSign,
    /// COMP-5 (and BINARY-CHAR/SHORT/LONG/DOUBLE): COB_FLAG_REAL_BINARY,
    /// native little-endian storage bounded by its size, not its PICTURE.
    /// Register is an internal register (RETURN-CODE): same storage,
    /// displayed with its PICTURE digits (COB_TYPE_NUMERIC_COMP5).
    Native, Register,
    /// Signed DISPLAY with a SIGN clause: overpunched first digit, or a
    /// separate '+'/'-' byte before or after the digits.
    SignLeading, SignLeadingSeparate, SignTrailingSeparate,
    /// COMP-1 / COMP-2: a native C float or double (COB_TYPE_NUMERIC_FLOAT,
    /// COB_TYPE_NUMERIC_DOUBLE), read and stored through runtime::float.
    Float, Double,
    /// COMP-X / COMP-N: a real binary item bounded by its size, like
    /// COMP-5, but stored big-endian (flag_binary_swap) and displayed on the
    /// digits of its PICTURE.
    Swapped,
}
impl Usage {
    pub fn is_display(self) -> bool {
        matches!(self, Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate)
    }
}

/// cob_decimal_get_binary without COB_STORE_KEEP_ON_OVERFLOW: the value,
/// or on overflow its residue modulo 2^(8 * size), in little-endian bytes.
fn native_bytes(units: &BigInt, size: usize) -> Vec<u8> {
    let modulus = BigInt::from(1) << (8 * size);
    let mut wrapped = units % &modulus;
    if wrapped.sign() == Sign::Minus { wrapped += &modulus; }
    let mut bytes = wrapped.to_bytes_le().1;
    bytes.resize(size, 0);
    bytes
}

/// codegen.c output_integer, for scalar arguments of native system calls.
/// CALL does not insert cob_check_numeric, including in the -debug profile.
pub fn system_integer(value: &Value) -> i128 {
    system_integer_impl(value, true)
}

/// An explicit item SIGN clause disables cob_get_numdisp(s).
pub fn system_integer_unoptimized(value: &Value) -> i128 {
    system_integer_impl(value, false)
}

/// move.c pack_to_bin, including its observable 0x2F -> 25 entry.
const SYSTEM_PACK_TO_BIN: [u8; 256] = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 25,
    30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
    40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
    50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65,
    60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75,
    70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85,
    80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95,
    90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105,
    100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115,
    110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125,
    120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135,
    130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145,
    140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155,
    150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165,
];

/// cob_decimal_get_field for COB_TYPE_NUMERIC_FLOAT / DOUBLE: the native
/// bytes, None when the double is not finite (cob_not_finite).
fn float_bytes(source: &Value, usage: Usage) -> Option<Vec<u8>> {
    let value = crate::runtime::float::to_f64(&source.num())?;
    Some(if matches!(usage, Usage::Float) { (value as f32).to_le_bytes().to_vec() } else { value.to_le_bytes().to_vec() })
}

fn system_integer_impl(value: &Value, optimized_display: bool) -> i128 {
    fn int32(units: &BigInt) -> i128 {
        let bytes: [u8; 4] = native_bytes(units, 4).try_into().unwrap();
        i32::from_le_bytes(bytes) as i128
    }
    let view = match value {
        Value::Num(number, _) => return int32(&number.units(0, false)),
        Value::View(view) => view,
        _ => fail("argument entier BY VALUE non numérique non pris en charge"),
    };
    let (digits, scale, signed, usage) = match view.kind {
        Kind::Numeric { digits, scale, signed, usage } => (digits, scale, signed, usage),
        _ => fail("argument entier BY VALUE édité ou alphanumérique non pris en charge"),
    };
    let mut bytes = view.raw();
    if bytes.is_empty() { fail("argument entier BY VALUE sans stockage"); }
    match usage {
        Usage::Float | Usage::Double => fail("argument entier BY VALUE d'un flottant non pris en charge"),
        Usage::Binary | Usage::Native | Usage::Register | Usage::Index | Usage::Swapped => {
            if !matches!(bytes.len(), 1 | 2 | 4 | 8) {
                fail("taille binaire BY VALUE non prise en charge");
            }
            let signed = signed || matches!(usage, Usage::Index);
            let number = if matches!(usage, Usage::Binary | Usage::Swapped) {
                if signed { BigInt::from_signed_bytes_be(&bytes) } else { BigInt::from_bytes_be(Sign::Plus, &bytes) }
            } else if signed {
                BigInt::from_signed_bytes_le(&bytes)
            } else {
                BigInt::from_bytes_le(Sign::Plus, &bytes)
            };
            number.to_string().parse().unwrap()
        },
        Usage::Packed | Usage::PackedNoSign => {
            // cob_packed_get_int ignores scale. Native metadata counts trailing P.
            let native_digits = digits + (-scale).max(0) as u32;
            let no_sign = matches!(usage, Usage::PackedNoSign);
            let low_first = if no_sign { native_digits % 2 == 1 } else { native_digits % 2 == 0 };
            if !no_sign && low_first && bytes.len() == 1 {
                fail("lecture BY VALUE au-delà du stockage packed natif non prise en charge");
            }
            let mut n = if low_first { (bytes.remove(0) & 15) as i32 } else { 0 };
            let last = if no_sign { None } else { bytes.pop() };
            for byte in bytes {
                n = n.wrapping_mul(100).wrapping_add(SYSTEM_PACK_TO_BIN[byte as usize] as i32);
            }
            if let Some(byte) = last {
                n = n.wrapping_mul(10).wrapping_add((byte >> 4) as i32);
                if byte & 15 == 13 { n = n.wrapping_neg(); }
            }
            n as i128
        },
        Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate
            if optimized_display && scale >= 0 && (1..=9).contains(&(bytes.len() as i32 - scale)) => {
            // cob_get_numdisp(s): sign comes from the last INTEGER byte.
            let prefix = &bytes[..bytes.len() - scale as usize];
            let n = prefix.iter().fold(0i32, |n, byte| n.wrapping_mul(10).wrapping_add((byte & 15) as i32));
            if signed && prefix[prefix.len() - 1] & 0x40 != 0 { n.wrapping_neg() as i128 } else { n as i128 }
        },
        Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate => {
            // cob_display_get_int / cob_real_get_sign with the ASCII profile.
            let mut negative = false;
            if signed {
                let first = matches!(usage, Usage::SignLeading | Usage::SignLeadingSeparate);
                let separate = matches!(usage, Usage::SignLeadingSeparate | Usage::SignTrailingSeparate);
                let position = if first { 0 } else { bytes.len() - 1 };
                negative = if separate { bytes[position] == b'-' } else { bytes[position] & 0xf0 == 0x70 };
                if separate { bytes.remove(position); }
            }
            if scale > bytes.len() as i32 || scale < -9 {
                fail("PICTURE P hors des bornes de cob_display_get_int non prise en charge");
            }
            let count = bytes.len() - scale.max(0) as usize;
            let mut n = bytes[..count].iter().fold(0i32, |n, byte| n.wrapping_mul(10).wrapping_add((byte & 15) as i32));
            if scale < 0 { n = n.wrapping_mul(10i32.pow((-scale) as u32)); }
            if negative { n = n.wrapping_neg(); }
            n as i128
        },
    }
}

/// The digits of DISPLAY storage and its sign, as cob_real_get_sign reads
/// them: an overpunch 'p'..'y' on the sign digit, or a separate byte where
/// only '-' is negative. Unsigned items have no sign position.
static UNCHECKED_DATA: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// The program was compiled with -fno-ec=data-incompatible: no
/// cob_check_numeric before a MOVE from numeric DISPLAY data.
pub fn set_unchecked_data() { UNCHECKED_DATA.store(true, std::sync::atomic::Ordering::Relaxed); }

fn unchecked_data() -> bool { UNCHECKED_DATA.load(std::sync::atomic::Ordering::Relaxed) }

static RUNTIME_CHECKS: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
/// cobc -debug: invalid numeric data stops the run instead of being read.
pub fn set_runtime_checks() { RUNTIME_CHECKS.store(true, std::sync::atomic::Ordering::Relaxed); }
pub(crate) fn runtime_checks() -> bool { RUNTIME_CHECKS.load(std::sync::atomic::Ordering::Relaxed) }

fn display_digits(bytes: &[u8], usage: Usage, signed: bool) -> (Vec<u8>, bool) {
    let mut digits = bytes.to_vec();
    if !signed || digits.is_empty() { return (digits, false); }
    match usage {
        Usage::SignLeadingSeparate => { let sign = digits.remove(0); (digits, sign == b'-') },
        Usage::SignTrailingSeparate => { let sign = digits.pop().unwrap(); (digits, sign == b'-') },
        _ => {
            let position = if matches!(usage, Usage::SignLeading) { 0 } else { digits.len() - 1 };
            let negative = (b'p'..=b'y').contains(&digits[position]);
            if negative { digits[position] -= b'p' - b'0'; }
            (digits, negative)
        },
    }
}

/// DISPLAY storage for digits and a sign (cob_real_put_sign).
fn display_bytes(mut digits: Vec<u8>, negative: bool, usage: Usage, signed: bool) -> Vec<u8> {
    if !signed { return digits; }
    match usage {
        Usage::SignLeadingSeparate => { digits.insert(0, if negative { b'-' } else { b'+' }); digits },
        Usage::SignTrailingSeparate => { digits.push(if negative { b'-' } else { b'+' }); digits },
        _ => {
            if negative && !digits.is_empty() {
                let position = if matches!(usage, Usage::SignLeading) { 0 } else { digits.len() - 1 };
                digits[position] += b'p' - b'0';
            }
            digits
        },
    }
}
#[derive(Clone, Copy, Debug)]
pub enum Kind {
    Text,
    Numeric { digits: u32, scale: i32, signed: bool, usage: Usage },
    Edited { symbols: &'static [(u8, u32)], digits: u32, scale: i32, blank_zero: bool },
    /// Alphanumeric-edited: one byte per position, A/X/9 take the sender's
    /// bytes, B is a space, 0 and / are inserted (cob_move_alphanum_to_edited).
    AlnumEdited { symbols: &'static [u8] },
    /// JUSTIFIED RIGHT alphanumeric: a MOVE keeps the rightmost bytes and pads on the left.
    Justified,
}
#[derive(Clone, Debug)]
pub struct Initializer {
    pub offset: usize,
    pub size: usize,
    pub kind: Kind,
    pub dimensions: Vec<(usize, usize)>,
    pub filler: bool,
}
#[derive(Clone, Debug)]
pub struct View {
    pub memory: Memory,
    pub offset: usize,
    pub size: usize,
    pub kind: Kind,
    pub dimensions: Vec<(usize, usize)>,
    pub initializers: Vec<Initializer>,
    pub limit: Option<usize>,
}

fn offsets(dimensions: &[(usize, usize)], base: usize, action: &mut impl FnMut(usize)) {
    if let Some(((stride, count), tail)) = dimensions.split_first() {
        for index in 0..*count { offsets(tail, base + index * stride, action); }
    } else { action(base); }
}

fn move_whitespace(byte: u8) -> bool {
    matches!(byte, b'\t'..=b'\r' | b' ')
}

// GnuCOBOL's alphanumeric-to-DISPLAY transfer fills a finite digit buffer.
// Leading integer overflow is skipped before validation, and validation stops
// as soon as the buffer is full. This differs from parsing a decimal string.
fn text_move_digits(raw: &[u8], digits: usize, scale: usize) -> (Vec<u8>, bool, bool) {
    // cob_move_alphanum_to_display: the module's decimal point and separator.
    let raw = &crate::runtime::internal_symbols(raw, false)[..];
    let mut result = vec![b'0'; digits];
    let mut position = 0;
    while position < raw.len() && move_whitespace(raw[position]) { position += 1; }
    let mut negative = false;
    if position < raw.len() && matches!(raw[position], b'+' | b'-') {
        negative = raw[position] == b'-';
        position += 1;
    }
    let count = raw[position..].iter().take_while(|&&byte| byte != b'.')
        .filter(|&&byte| byte.is_ascii_digit()).count();
    let integer = digits - scale;
    let mut destination = if count < integer { integer - count } else { 0 };
    for _ in integer..count {
        while !raw[position].is_ascii_digit() { position += 1; }
        position += 1;
    }
    let mut point = false;
    while position < raw.len() && destination < digits {
        let byte = raw[position];
        position += 1;
        if byte.is_ascii_digit() {
            result[destination] = byte;
            destination += 1;
        } else if byte == b'.' && !point {
            point = true;
        } else if !move_whitespace(byte) && byte != b',' {
            result.fill(b'0');
            return (result, negative, false);
        }
    }
    (result, negative, true)
}

fn fetch(digits: &[u8], src: &mut i64) -> u8 {
    let x = if *src >= 0 && (*src as usize) < digits.len() { digits[*src as usize] } else { b'0' };
    *src += 1;
    x
}

/// cob_move_display_to_edited (libcob move.c), symbol for symbol. `digits`
/// are the sender's decimal digits, the last of weight 10^-scale; positions
/// outside them read as '0', so high-order digits beyond the picture are
/// dropped and missing ones are zeros, as with the native sender pointer.
fn edit(symbols: &[(u8, u32)], size: usize, digits: &[u8], scale: i32, neg: bool, blank_zero: bool) -> Vec<u8> {
    // The picture symbols are internal ('.', ',', '$'); the output uses the
    // module's decimal point, separator and currency sign.
    crate::runtime::module_text(edit_internal(symbols, size, digits, scale, neg, blank_zero))
}

fn edit_internal(symbols: &[(u8, u32)], size: usize, digits: &[u8], scale: i32, neg: bool, blank_zero: bool) -> Vec<u8> {
    const CURRENCY: u8 = b'$';
    const DEC_SYMBOL: u8 = b'.';
    let mut out = vec![b' '; size];
    let mut count: i64 = 0;
    let (mut count_sign, mut count_curr, mut p_is_left) = (true, true, false);
    for &(c, repeat) in symbols {
        let repeat = repeat as i64;
        if c == b'9' || c == b'Z' || c == b'*' {
            count += repeat; count_sign = false; count_curr = false;
        } else if count_curr && c == CURRENCY {
            count += repeat;
        } else if count_sign && (c == b'+' || c == b'-') {
            count += repeat;
        } else if c == b'P' {
            if count == 0 { p_is_left = true; break; }
            count += repeat; count_sign = false; count_curr = false;
        } else if c == b'V' || c == DEC_SYMBOL {
            break;
        }
    }
    let mut src = digits.len() as i64 - scale as i64 - count;
    let mut dst: i64 = 0;
    let mut end = size as i64;
    let mut decimal_point: Option<i64> = None;
    let (mut is_zero, mut suppress_zero, mut trailing_sign, mut trailing_curr) = (true, true, false, false);
    let (mut sign_first, mut has_b, mut floating_insertion) = (0, false, false);
    let mut pad = b' ';
    let (mut sign_symbol, mut curr_symbol) = (0u8, 0u8);
    let mut last_fixed: Option<(usize, u8)> = None;
    let put = |out: &mut Vec<u8>, at: i64, byte: u8| {
        if at < 0 || at as usize >= out.len() { fail("invalid numeric-edited picture layout"); }
        out[at as usize] = byte;
    };
    for &(c, repeat) in symbols {
        for n in (1..=repeat).rev() {
            match c {
                b'9' => {
                    let x = fetch(digits, &mut src);
                    if x != b'0' { is_zero = false; }
                    suppress_zero = false; trailing_sign = true; trailing_curr = true;
                    put(&mut out, dst, x);
                },
                b'Z' | b'*' => {
                    let x = fetch(digits, &mut src);
                    if x != b'0' { is_zero = false; suppress_zero = false; }
                    trailing_sign = true; trailing_curr = true;
                    pad = if c == b'*' { b'*' } else { b' ' };
                    put(&mut out, dst, if suppress_zero { pad } else { x });
                },
                b'+' | b'-' | CURRENCY => {
                    let x = fetch(digits, &mut src);
                    if x != b'0' { is_zero = false; suppress_zero = false; }
                    let trailing = if c == CURRENCY { trailing_curr } else { trailing_sign };
                    if trailing {
                        put(&mut out, dst, if c == CURRENCY { CURRENCY } else if neg && !is_zero { b'-' } else if c == b'+' { b'+' } else { b' ' });
                        end -= 1;
                    } else if dst == 0 || suppress_zero {
                        put(&mut out, dst, pad);
                        if c == CURRENCY { curr_symbol = CURRENCY; }
                        else { sign_symbol = c; if curr_symbol == 0 { sign_first += 1; } }
                    } else {
                        put(&mut out, dst, x);
                    }
                    if n > 1 || last_fixed.map(|(_, symbol)| symbol) == Some(c) {
                        floating_insertion = true;
                    } else if !trailing {
                        if let Some((position, symbol)) = last_fixed { out[position] = symbol; }
                        last_fixed = Some((dst as usize, c));
                    }
                },
                b'.' | b',' => {
                    if c == DEC_SYMBOL { put(&mut out, dst, DEC_SYMBOL); decimal_point = Some(dst); }
                    else { put(&mut out, dst, if suppress_zero { pad } else { c }); }
                },
                b'V' => { dst -= 1; decimal_point = Some(dst); },
                b'0' | b'/' => put(&mut out, dst, c),
                b'B' => {
                    if suppress_zero { put(&mut out, dst, pad); } else { put(&mut out, dst, b'B'); has_b = true; }
                },
                b'P' => { if p_is_left { src += 1; dst -= 1; } },
                b'C' | b'D' => {
                    end = dst;
                    let text: &[u8; 2] = if neg && !is_zero { if c == b'C' { b"CR" } else { b"DB" } } else { b"  " };
                    put(&mut out, dst, text[0]);
                    dst += 1;
                    put(&mut out, dst, text[1]);
                },
                _ => fail("unsupported numeric-edited picture symbol"),
            }
            dst += 1;
        }
    }
    if sign_symbol != 0 {
        sign_symbol = if neg && !is_zero { b'-' } else if sign_symbol != b'+' { b' ' } else { b'+' };
    }
    if suppress_zero || (is_zero && blank_zero) {
        if pad == b' ' || blank_zero {
            out.fill(b' ');
        } else {
            for byte in out.iter_mut() { if *byte != DEC_SYMBOL { *byte = pad; } }
        }
        return out;
    }
    if let Some(point) = decimal_point {
        let mut position = point + 1;
        while position < end {
            let byte = out[position as usize];
            if !(byte.is_ascii_digit() || matches!(byte, b',' | b'.' | b'+' | b'-' | b'/' | b'B')) {
                out[position as usize] = b'0';
            }
            position += 1;
        }
    }
    if sign_symbol != 0 || curr_symbol != 0 {
        if floating_insertion {
            let mut position = end - 1;
            while position > 0 && out[position as usize] != b' ' { position -= 1; }
            let symbol = if sign_symbol != 0 && curr_symbol != 0 {
                if sign_first != 0 { curr_symbol } else { sign_symbol }
            } else if sign_symbol != 0 { sign_symbol } else { curr_symbol };
            put(&mut out, position, symbol);
        } else if let Some((position, symbol)) = last_fixed {
            out[position] = if symbol == CURRENCY { curr_symbol } else { sign_symbol };
        }
    }
    if has_b {
        let mut leading = true;
        for position in 0..end.max(0) as usize {
            if out[position] == b'B' { out[position] = if leading { pad } else { b' ' }; }
            else { leading = false; }
        }
    }
    out
}

impl View {
    /// The storage of the item; an unbound LINKAGE item (not passed by the
    /// caller, a NULL address for GnuCOBOL) is a named stop.
    fn mem(&self) -> std::cell::Ref<'_, Vec<u8>> {
        self.check_storage();
        check_defined(&self.memory, self.offset, self.size);
        self.memory.borrow()
    }
    /// The storage of the item, which the caller overwrites in full.
    fn mem_mut(&self) -> std::cell::RefMut<'_, Vec<u8>> {
        check_writable(&self.memory);
        self.check_storage();
        define(&self.memory, self.offset, self.size);
        self.memory.borrow_mut()
    }
    fn check_storage(&self) {
        if self.limit.is_some_and(|limit| self.offset + self.size > limit) {
            fail("item extends beyond the storage at its address (CALL argument, ADDRESS OF or ALLOCATE); not modelled");
        }
        if self.memory.borrow().len() < self.offset + self.size { fail("item without storage (LINKAGE item not passed, NULL or freed address)"); }
    }
    pub fn resolved(&self) {
        if !self.dimensions.is_empty() { fail("array reference requires all subscripts"); }
    }
    pub fn at(&self, indices: &[Value]) -> Self {
        if indices.len() != self.dimensions.len() { fail("wrong number of subscripts"); }
        let mut view = self.clone();
        for (index, (stride, count)) in indices.iter().zip(&self.dimensions) {
            let number = index.integer("subscript");
            if number < 1 || number > *count as i128 { fail("COBOL subscript out of bounds"); }
            view.offset += (number as usize - 1) * stride;
        }
        view.dimensions.clear();
        view
    }
    pub fn slice(&self, start: &Value, length: Option<&Value>) -> Self {
        self.resolved();
        let start = start.integer("reference modification");
        let length = length.map(|v| v.integer("reference modification")).unwrap_or(self.size as i128 - start + 1);
        if start < 1 || length < 1 || start > self.size as i128 || length > self.size as i128 - start + 1 {
            fail("reference modification out of bounds");
        }
        let mut view = self.clone();
        view.offset += start as usize - 1;
        view.size = length as usize;
        view.kind = Kind::Text;
        view.initializers = vec![Initializer { offset: 0, size: view.size, kind: Kind::Text, dimensions: vec![], filler: false }];
        view
    }
    fn raw(&self) -> Vec<u8> {
        self.resolved();
        self.mem()[self.offset..self.offset + self.size].to_vec()
    }
    fn number(&self) -> Result<Value, &'static str> {
        let (digits, scale, signed, usage) = match self.kind {
            Kind::Numeric { digits, scale, signed, usage } => (digits, scale, signed, usage),
            _ => return Err("numeric view required"),
        };
        let bytes = self.raw();
        if let Some(value) = self.float_value() {
            // cob_decimal_set_field: COMP-1 through (double) fval.
            return Ok(Value::Num(crate::runtime::float::from_f64(value), None));
        }
        let coefficient = match usage {
            Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate => {
                if bytes.is_empty() { return Err("empty numeric field"); }
                if matches!(usage, Usage::SignLeadingSeparate) && !matches!(bytes[0], b'+' | b'-')
                    || matches!(usage, Usage::SignTrailingSeparate) && !matches!(bytes[bytes.len() - 1], b'+' | b'-') {
                    return Err("invalid separate sign");
                }
                let (digits, negative) = display_digits(&bytes, usage, signed);
                if digits.is_empty() || !digits.iter().all(u8::is_ascii_digit) { return Err("invalid DISPLAY numeric data"); }
                let n = BigInt::parse_bytes(&digits, 10).ok_or("invalid DISPLAY data")?;
                if negative { -n } else { n }
            },
            Usage::Packed => {
                let mut nibbles: Vec<u8> = bytes.iter().flat_map(|b| [b >> 4, b & 15]).collect();
                let sign = nibbles.pop().ok_or("empty packed decimal")?;
                if !(if signed { sign == 12 || sign == 13 } else { sign == 15 }) {
                    return Err("invalid packed decimal sign");
                }
                let padding = nibbles.len() - digits as usize;
                if nibbles[..padding].iter().any(|n| *n != 0) || nibbles.iter().any(|n| *n > 9) {
                    return Err("invalid packed decimal digits");
                }
                let ascii: Vec<u8> = nibbles.into_iter().map(|n| b'0' + n).collect();
                let n = BigInt::parse_bytes(&ascii, 10).ok_or("invalid packed decimal")?;
                if sign == 13 { -n } else { n }
            },
            Usage::PackedNoSign => {
                let nibbles: Vec<u8> = bytes.iter().flat_map(|b| [b >> 4, b & 15]).collect();
                let padding = nibbles.len() - digits as usize;
                if nibbles[..padding].iter().any(|n| *n != 0) || nibbles.iter().any(|n| *n > 9) {
                    return Err("invalid packed decimal digits");
                }
                let ascii: Vec<u8> = nibbles.into_iter().map(|n| b'0' + n).collect();
                BigInt::parse_bytes(&ascii, 10).ok_or("invalid packed decimal")?
            },
            // An index is a native int: little endian on x86-64.
            Usage::Index => BigInt::from_signed_bytes_le(&bytes),
            // Read above through float_value.
            Usage::Float | Usage::Double => unreachable!(),
            Usage::Native | Usage::Register => {
                if signed { BigInt::from_signed_bytes_le(&bytes) }
                else { BigInt::from_bytes_le(Sign::Plus, &bytes) }
            },
            Usage::Swapped => {
                if signed { BigInt::from_signed_bytes_be(&bytes) }
                else { BigInt::from_bytes_be(Sign::Plus, &bytes) }
            },
            Usage::Binary => {
                if signed { BigInt::from_signed_bytes_be(&bytes) }
                else { BigInt::from_bytes_be(Sign::Plus, &bytes) }
            },
        };
        Ok(Value::Num(Number::scaled(coefficient, scale), Some((digits, scale, signed, matches!(usage, Usage::SignTrailingSeparate)))))
    }
    /// DISPLAY of a real binary item, cob_print_realbin: the stored integer
    /// (no decimal point) on bin_digits[size] digits, or on the PICTURE
    /// digits for an internal register; a sign only when the item has one.
    /// The stored C float (as a double) or double of a COMP-1 / COMP-2 item.
    pub fn float_value(&self) -> Option<f64> {
        match self.kind {
            Kind::Numeric { usage: Usage::Float, .. } => Some(f32::from_le_bytes(self.raw()[..4].try_into().unwrap()) as f64),
            Kind::Numeric { usage: Usage::Double, .. } => Some(f64::from_le_bytes(self.raw()[..8].try_into().unwrap())),
            _ => None,
        }
    }
    pub fn native_display(&self) -> Option<String> {
        if let Kind::Numeric { usage: usage @ (Usage::Float | Usage::Double), .. } = self.kind {
            self.resolved();
            // cob_display_common: "%-.8G" of (double) fval, "%-.16G" of a double.
            let value = self.float_value().unwrap();
            return Some(crate::runtime::float::display(value, if matches!(usage, Usage::Float) { 8 } else { 16 }));
        }
        let (digits, signed, usage) = match self.kind {
            Kind::Numeric { digits, signed, usage: usage @ (Usage::Native | Usage::Register | Usage::Swapped), .. } => (digits, signed, usage),
            _ => return None,
        };
        self.resolved();
        let bytes = self.raw();
        if matches!(usage, Usage::Swapped) {
            // cob_display of a binary item: a DISPLAY copy of its PICTURE
            // digits, so the high-order digits of the stored value are lost.
            let integer = if signed { BigInt::from_signed_bytes_be(&bytes) } else { BigInt::from_bytes_be(Sign::Plus, &bytes) };
            let mut text = format!("{:0>width$}", (absolute(&integer) % power(digits)).to_string(), width = digits as usize);
            if let Kind::Numeric { scale, .. } = self.kind {
                if scale > 0 && (scale as u32) <= digits { text.insert(text.len() - scale as usize, '.'); }
                else if scale != 0 { fail("DISPLAY d'un COMP-X à échelle P non modélisé"); }
            }
            return Some(if signed { format!("{}{text}", if integer.sign() == Sign::Minus { '-' } else { '+' }) } else { text });
        }
        let integer = if signed { BigInt::from_signed_bytes_le(&bytes) } else { BigInt::from_bytes_le(Sign::Plus, &bytes) };
        const BIN_DIGITS: [usize; 9] = [1, 3, 5, 8, 10, 13, 15, 17, 20];
        let width = if matches!(usage, Usage::Register) { digits as usize } else { BIN_DIGITS[self.size.min(8)] };
        let text = format!("{:0>width$}", absolute(&integer).to_string(), width = width);
        Some(if signed { format!("{}{text}", if integer.sign() == Sign::Minus { '-' } else { '+' }) } else { text })
    }
    /// cob_display of an unsigned DISPLAY item holding invalid data, without
    /// runtime checks: pretty_display_numeric moves it to 9(n)[.9(s)] with
    /// cob_move_display_to_edited, which keeps the bytes as they are, except
    /// after the decimal point where other bytes than digits, ".,+-/B" are
    /// zero.
    pub fn invalid_display(&self) -> Option<Vec<u8>> {
        let (digits, scale) = match self.kind {
            Kind::Numeric { digits, scale, signed: false, usage: Usage::Display } if scale >= 0 && scale as u32 <= digits => (digits as usize, scale as usize),
            _ => return None,
        };
        if runtime_checks() || self.number().is_ok() { return None; }
        let bytes = self.raw();
        let mut out = bytes[..digits - scale].to_vec();
        if scale > 0 {
            out.push(crate::runtime::module_symbols().0);
            out.extend(bytes[digits - scale..].iter().map(|&b| if b.is_ascii_digit() || b",.+-/B".contains(&b) { b } else { b'0' }));
        }
        Some(out)
    }
    /// An operand as libcob reads it without runtime checks. An unsigned
    /// DISPLAY item counts COB_D2I (low nibble) of each byte; as a decimal
    /// (cob_decimal_set_display: computations, cob_cmp_llint) a first byte
    /// 0xFF is 10^size and 0x00 is -10^size, as an integer (cob_get_llint,
    /// cob_cmp_numdisp) it is not special. A packed item keeps its digit
    /// nibbles, any sign but D is positive (cob_decimal_set_packed); a digit
    /// nibble above 9 or a signed DISPLAY item is a named stop.
    pub fn operand_value(&self, integer: bool) -> Value {
        let error = match self.kind {
            Kind::Numeric { .. } => match self.number() { Ok(value) => return value, Err(error) => error },
            _ => return self.value(),
        };
        if runtime_checks() { fail(error); }
        let (digits, scale, signed, usage) = match self.kind {
            Kind::Numeric { digits, scale, signed, usage } => (digits, scale, signed, usage), _ => unreachable!(),
        };
        let bytes = self.raw();
        match usage {
            Usage::Display if !signed => {
                let units = if !integer && bytes[0] == 0xff { power(bytes.len() as u32) }
                    else if !integer && bytes[0] == 0 { -power(bytes.len() as u32) }
                    else { bytes.iter().fold(BigInt::from(0), |n, &b| n * 10 + (b & 0x0f)) };
                Value::Num(Number::scaled(units, scale), Some((digits, scale, signed, false)))
            },
            Usage::Packed => {
                let mut nibbles: Vec<u8> = bytes.iter().flat_map(|b| [b >> 4, b & 15]).collect();
                let sign = nibbles.pop().unwrap_or(0);
                let padding = nibbles.len() - digits as usize;
                if nibbles[padding..].iter().any(|&n| n > 9) {
                    fail(&format!("{error} (digit nibble above 9 read differently by libcob's paths)"));
                }
                let units = nibbles[padding..].iter().fold(BigInt::from(0), |n, &d| n * 10 + d);
                let units = if signed && sign == 13 { -units } else { units };
                Value::Num(Number::scaled(units, scale), Some((digits, scale, signed, false)))
            },
            _ => fail(&format!("{error} (signed or binary invalid data without runtime checks not modelled)")),
        }
    }
    pub fn value(&self) -> Value {
        match self.kind {
            Kind::Text | Kind::Justified | Kind::Edited { .. } | Kind::AlnumEdited { .. } => Value::Bytes(self.raw()),
            _ => self.number().unwrap_or_else(|error| fail(error)),
        }
    }
    pub fn is_numeric(&self) -> bool {
        match self.kind {
            Kind::Text | Kind::Justified | Kind::Edited { .. } | Kind::AlnumEdited { .. } => self.raw().iter().all(u8::is_ascii_digit),
            Kind::Numeric { signed, usage: usage @ (Usage::Packed | Usage::PackedNoSign), .. } => {
                // cob_is_numeric: the sign (or last digit) nibble, then every
                // other nibble a digit; the pad nibble is not checked apart.
                let bytes = self.raw();
                let last = bytes[bytes.len() - 1];
                let sign = last & 0x0f;
                let sign_ok = match usage {
                    Usage::PackedNoSign => sign <= 9,
                    _ if signed => sign == 0x0c || sign == 0x0d,
                    _ => sign == 0x0f,
                };
                sign_ok && last >> 4 <= 9 && bytes[..bytes.len() - 1].iter().all(|b| b >> 4 <= 9 && b & 0x0f <= 9)
            },
            _ => self.number().is_ok(),
        }
    }
    pub fn numeric_move_text(&self, group: bool) -> Value {
        self.resolved();
        if group {
            // A group receiver requests storage bytes, including a DISPLAY
            // overpunch or the original COMP/COMP-3 representation.
            match self.kind {
                Kind::Numeric { .. } => return Value::Bytes(self.raw()),
                _ => fail("numeric MOVE to text requires a numeric source"),
            }
        }
        self.numeric_text(false)
    }
    pub fn comparison_text(&self) -> Value {
        self.numeric_text(true)
    }
    fn numeric_text(&self, comparison: bool) -> Value {
        self.resolved();
        let (digits, scale, signed, usage) = match self.kind {
            Kind::Numeric { digits, scale, signed, usage } => (digits, scale, signed, usage),
            _ => fail("numeric text operation requires a numeric source"),
        };
        if comparison && matches!(usage, Usage::Index) { fail("mixed comparison with an index is unsupported"); }
        if matches!(usage, Usage::Float | Usage::Double) {
            fail("MOVE ou comparaison alphanumérique d'un flottant non modélisé");
        }
        // cob_cmp_alnum reads the stored digits of a DISPLAY item, P positions
        // not included; other usages go through a DISPLAY copy of their digits.
        if comparison && (scale < 0 || scale as u32 > digits) && !usage.is_display() { fail("alphanumeric comparison of a P-scaled item not modelled"); }
        if !comparison && scale > 0 { fail("numeric MOVE to alphanumeric requires an integer source"); }
        if scale < 0 && !usage.is_display() { fail("P-scaled binary or packed MOVE to alphanumeric not modelled"); }
        let bytes = match usage {
            Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate => {
                let mut bytes = self.raw();
                let separate = matches!(usage, Usage::SignLeadingSeparate | Usage::SignTrailingSeparate);
                if signed && !comparison && separate && self.number().is_err() && unchecked_data() {
                    // -fno-ec=data-incompatible: no cob_check_numeric, and
                    // cob_move_display_to_alphanum copies the digit bytes as
                    // they are; COB_PUT_SIGN then writes '+' unless the sign
                    // byte read was '-'.
                    let position = if matches!(usage, Usage::SignLeadingSeparate) { 0 } else { bytes.len() - 1 };
                    let sign = if bytes[position] == b'-' { b'-' } else { b'+' };
                    self.mem_mut()[self.offset + position] = sign;
                    bytes.remove(position);
                    return Value::Bytes(bytes);
                }
                if signed {
                    // GnuCOBOL normalizes some malformed sign encodings and
                    // can mutate the sender. Keep those cases outside this
                    // profile rather than silently changing their behavior.
                    if self.number().is_err() { fail("invalid signed DISPLAY numeric MOVE"); }
                    // The data without its sign: a separate sign byte is not part of it.
                    bytes = display_digits(&bytes, usage, signed).0;
                }
                // An unsigned DISPLAY sender is copied as bytes even when
                // its storage is not valid numeric data. Trailing P positions
                // follow as zeros (cob_move_display_to_alphanum).
                let mut bytes = bytes;
                if !comparison { bytes.extend(std::iter::repeat(b'0').take((-scale).max(0) as usize)); }
                bytes
            },
            Usage::Float | Usage::Double => unreachable!(),
            Usage::Packed | Usage::PackedNoSign | Usage::Binary | Usage::Index | Usage::Native | Usage::Register
            | Usage::Swapped => {
                let number = self.number().unwrap_or_else(|error| fail(error));
                let coefficient = absolute(&number.num().units(scale, false)) % power(digits);
                format!("{:0>width$}", coefficient.to_string(), width = digits as usize).into_bytes()
            },
        };
        Value::Bytes(bytes)
    }
    pub fn assign_text_move(&mut self, source: &Value, raw_group: bool) {
        self.resolved();
        if !source.is_text() { fail("text MOVE requires an alphanumeric source"); }
        let bytes = source.bytes();
        if matches!(self.kind, Kind::Numeric { usage: Usage::Index, .. }) {
            fail("MOVE of text to an index requires native index semantics");
        }
        if matches!(self.kind, Kind::Numeric { usage: Usage::Native | Usage::Register | Usage::Swapped, .. }) && !raw_group {
            fail("MOVE of text to a COMP-5 item not modelled");
        }
        if raw_group {
            // Group category wins over the receiver's elementary category.
            // Copy storage bytes and spaces, without numeric interpretation.
            let mut result = bytes;
            result.resize(self.size, b' ');
            result.truncate(self.size);
            self.mem_mut()[self.offset..self.offset + self.size].copy_from_slice(&result);
            return;
        }
        if let Kind::Numeric { scale, digits, .. } = self.kind {
            if scale < 0 || scale as u32 > digits { fail("text MOVE to a P-scaled item not modelled"); }
        }
        if let Kind::Numeric { digits, scale, signed, usage } = self.kind {
            if usage.is_display() {
                let (result, negative, _) = text_move_digits(&bytes, digits as usize, scale as usize);
                let result = display_bytes(result, signed && negative, usage, signed);
                if result.len() != self.size { fail("unsupported DISPLAY storage for text MOVE"); }
                self.mem_mut()[self.offset..self.offset + self.size].copy_from_slice(&result);
                return;
            }
        }
        // Other numeric usages and edited receivers pass through a signed
        // DISPLAY buffer of 76 positions and 38 fractional positions.
        let (result, source_negative, valid) = text_move_digits(&bytes, 76, 38);
        let coefficient = BigInt::parse_bytes(&result, 10).unwrap();
        let negative = source_negative && valid;
        let number = Number::new(if negative { -coefficient } else { coefficient }, 38);
        match self.kind {
            Kind::Edited { .. } => self.move_edited(&Value::Num(number, None)),
            Kind::Numeric { digits, scale, signed, usage } => {
                let magnitude = absolute(&number.units(scale, false)) % power(digits);
                let units = if signed && negative { -magnitude } else { magnitude };
                self.assign(&Value::Num(Number::scaled(units, scale), None), false);
                // BigInt has no negative zero, but a signed packed MOVE keeps
                // its D nibble even when scaling or truncation leaves zero.
                if signed && negative && matches!(usage, Usage::Packed) {
                    self.mark_negative_zero();
                }
            },
            _ => fail("text MOVE requires a numeric or edited receiver"),
        }
    }
    /// MOVE to a numeric-edited item: libcob edits the sender's own digits.
    pub fn move_edited(&mut self, source: &Value) {
        self.resolved();
        let (symbols, blank_zero) = match self.kind {
            Kind::Edited { symbols, blank_zero, .. } => (symbols, blank_zero),
            _ => return self.move_number(source),
        };
        let number = source.num();
        let negative = number.n.sign() == Sign::Minus;
        let digits = absolute(&number.n).to_string();
        let mut bytes = edit(symbols, self.size, digits.as_bytes(), number.scale as i32, negative, blank_zero);
        self.mem_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
    }
    /// Numeric MOVE: excess decimals are truncated, the magnitude is reduced
    /// modulo the PICTURE capacity (binary included) without SIZE ERROR, and an
    /// unsigned receiver drops the sign. A signed DISPLAY or packed receiver
    /// keeps a negative zero, as GnuCOBOL does for -1000 TO S999.
    pub fn move_number(&mut self, source: &Value) {
        self.resolved();
        let (digits, scale, signed, usage) = match self.kind {
            // cob_move_display_to_binary on a real binary receiver keeps the
            // low-order bytes of the value, not its PICTURE digits.
            Kind::Numeric { usage: Usage::Native | Usage::Register | Usage::Swapped, .. } => return self.assign(source, false),
            // cob_move to a float: cob_decimal_get_field of the whole value.
            Kind::Numeric { usage: Usage::Float | Usage::Double, .. } => return self.assign(source, false),
            Kind::Numeric { digits, scale, signed, usage } if !matches!(usage, Usage::Index) => (digits, scale, signed, usage),
            _ => return self.assign(source, false),
        };
        let units = source.num().units(scale, false);
        let negative = signed && units.sign() == Sign::Minus;
        let magnitude = absolute(&units) % power(digits);
        let zero = magnitude == BigInt::from(0);
        self.assign(&Value::Num(Number::scaled(if negative { -magnitude } else { magnitude }, scale), None), false);
        if negative && zero && !matches!(usage, Usage::Binary) {
            self.mark_negative_zero();
        }
    }
    /// Binary senders reach a packed receiver through cob_set_packed_int when
    /// the scaled value fits 32 bits. It fills every physical nibble, so an
    /// even-digit PICTURE would receive the next higher digit in its pad nibble.
    /// Native reads of such a field disagree with each other: stop instead.
    pub fn move_binary_to_packed(&mut self, source: &Value) {
        self.resolved();
        if let Kind::Numeric { digits, scale, usage: usage @ (Usage::Packed | Usage::PackedNoSign), .. } = self.kind {
            let units = source.num().units(scale, false);
            let fits = units >= BigInt::from(i32::MIN) && units <= BigInt::from(i32::MAX);
            let pad = if matches!(usage, Usage::Packed) { digits % 2 == 0 } else { digits % 2 == 1 };
            if fits && pad && (absolute(&units) / power(digits)) % BigInt::from(10) != BigInt::from(0) {
                fail("binary MOVE would fill the packed pad nibble; native semantics not modelled");
            }
        }
        self.move_number(source)
    }
    /// cob_add_packed_int (ADD/SUBTRACT of an int to a COMP-3 item of less
    /// than 19 digits, same sign): the carry of an even-digit item lands in
    /// its pad nibble instead of being dropped.
    pub fn packed_int_add_guard(&self, operand: &Value) {
        if let Kind::Numeric { digits, scale, usage: Usage::Packed, .. } = self.kind {
            if digits % 2 != 0 { return; }
            let Ok(current) = self.number() else { return };
            let current = current.num().units(scale, false);
            let delta = operand.num().units(scale, false);
            let negative = self.raw().last().map_or(false, |b| b & 0x0f == 0x0d);
            if delta.sign() == Sign::NoSign || (delta.sign() == Sign::Minus) != negative { return; }
            if absolute(&(current + delta)) >= power(digits) {
                fail("cob_add_packed_int would carry into the pad nibble; native semantics not modelled");
            }
        }
    }
    pub(crate) fn mark_negative_zero(&mut self) {
        let (usage, signed) = match self.kind { Kind::Numeric { usage, signed, .. } => (usage, signed), _ => return };
        let mut bytes = match usage {
            Usage::Packed => { let mut raw = self.raw(); let last = raw.last_mut().unwrap(); *last = (*last & 0xf0) | 0x0d; raw },
            Usage::Binary | Usage::Index | Usage::Native | Usage::Register | Usage::PackedNoSign
            | Usage::Float | Usage::Double | Usage::Swapped => return,
            _ => display_bytes(display_digits(&self.raw(), usage, signed).0, true, usage, signed),
        };
        self.mem_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
    }
    pub fn assign(&mut self, source: &Value, rounded: bool) {
        self.resolved();
        let mut truncated_negative_zero = false;
        let mut bytes = match self.kind {
            Kind::AlnumEdited { symbols } => {
                if !source.is_text() { fail("numeric/text MOVE unsupported"); }
                let bytes = source.bytes();
                let mut sender = bytes.iter();
                symbols.iter().map(|&symbol| match symbol {
                    b'A' | b'X' | b'9' => *sender.next().unwrap_or(&b' '),
                    b'B' => b' ',
                    other => other,
                }).collect()
            },
            Kind::Justified => {
                if !source.is_text() { fail("numeric/text MOVE unsupported"); }
                let bytes = source.bytes();
                if bytes.len() >= self.size { bytes[bytes.len() - self.size..].to_vec() }
                else { let mut padded = vec![b' '; self.size - bytes.len()]; padded.extend(bytes); padded }
            },
            Kind::Text => {
                if !source.is_text() { fail("numeric/text MOVE unsupported"); }
                let mut bytes = source.bytes();
                bytes.resize(self.size, b' ');
                bytes.truncate(self.size);
                bytes
            },
            Kind::Edited { symbols, digits, scale, blank_zero } => {
                if source.is_text() { fail("numeric-edited assignment requires a numeric source; de-editing is unsupported"); }
                // cob_decimal_get_field: the result goes through a DISPLAY
                // temporary of the edited item's digits and scale.
                let units = source.num().units(scale, rounded);
                let negative = units.sign() == Sign::Minus;
                let coefficient = absolute(&units) % power(digits);
                edit(symbols, self.size, coefficient.to_string().as_bytes(), scale, negative, blank_zero)
            },
            Kind::Numeric { usage: usage @ (Usage::Float | Usage::Double), .. } => {
                // cob_decimal_get_field without COB_STORE_KEEP_ON_OVERFLOW: a
                // non-finite double is stored as 0.0, a float overflow as inf.
                float_bytes(source, usage).unwrap_or_else(|| if matches!(usage, Usage::Float) { 0f32.to_le_bytes().to_vec() }
                                                         else { 0f64.to_le_bytes().to_vec() })
            },
            Kind::Numeric { scale, signed, usage: usage @ (Usage::Native | Usage::Register | Usage::Swapped), .. } => {
                let mut units = source.num().units(scale, rounded);
                if !signed { units = absolute(&units); }
                let mut bytes = native_bytes(&units, self.size);
                if matches!(usage, Usage::Swapped) { bytes.reverse(); }
                bytes
            },
            Kind::Numeric { digits, scale, signed, usage } => {
                let mut units = source.num().units(scale, rounded);
                // An unsigned receiver stores the absolute value (cob_decimal_get_field).
                if !signed && !matches!(usage, Usage::Index) { units = absolute(&units); }
                if matches!(usage, Usage::Index) {
                    if units < BigInt::from(i32::MIN) || units > BigInt::from(i32::MAX) { fail("native index capacity exceeded"); }
                } else if absolute(&units) >= power(digits) {
                    // cob_decimal_get_display without SIZE ERROR keeps the
                    // low-order digits and the sign of the whole result.
                    // Binary and packed receivers reach native or BCD add
                    // routines in cobc with other overflow rules.
                    // cob_decimal_get_packed does the same (cob_set_packed_u64
                    // of the remainder, sign nibble kept); binary receivers
                    // follow other rules.
                    if !usage.is_display() && !matches!(usage, Usage::Packed | Usage::PackedNoSign) {
                        fail("destination PICTURE overflow without SIZE ERROR; native truncation not modelled");
                    }
                    let negative = units.sign() == Sign::Minus;
                    let kept = absolute(&units) % power(digits);
                    truncated_negative_zero = negative && signed && kept == BigInt::from(0);
                    units = if negative { -kept } else { kept };
                }
                let negative = units.sign() == Sign::Minus;
                let ascii = format!("{:0>width$}", absolute(&units).to_string(), width = digits as usize).into_bytes();
                match usage {
                    Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate => display_bytes(ascii, negative, usage, signed),
                    Usage::Packed => {
                        let mut nibbles: Vec<u8> = ascii.iter().map(|b| b - b'0').collect();
                        nibbles.push(if !signed { 15 } else if negative { 13 } else { 12 });
                        if nibbles.len() % 2 != 0 { nibbles.insert(0, 0); }
                        nibbles.chunks_exact(2).map(|n| (n[0] << 4) | n[1]).collect()
                    },
                    Usage::PackedNoSign => {
                        let mut nibbles: Vec<u8> = ascii.iter().map(|b| b - b'0').collect();
                        if nibbles.len() % 2 != 0 { nibbles.insert(0, 0); }
                        nibbles.chunks_exact(2).map(|n| (n[0] << 4) | n[1]).collect()
                    },
                    Usage::Index => {
                        let mut bytes = units.to_signed_bytes_le();
                        if bytes.len() > self.size { fail("native index capacity exceeded"); }
                        bytes.resize(self.size, if negative { 255 } else { 0 });
                        bytes
                    },
                    Usage::Binary => {
                        let mut bytes = if signed { units.to_signed_bytes_be() } else { units.to_bytes_be().1 };
                        if bytes.len() > self.size { fail("binary storage overflow"); }
                        let mut padded = vec![if negative { 255 } else { 0 }; self.size - bytes.len()];
                        padded.append(&mut bytes);
                        padded
                    },
                    // Stored by the real binary and float arms above.
                    Usage::Native | Usage::Register | Usage::Float | Usage::Double | Usage::Swapped => unreachable!(),
                }
            },
        };
        self.mem_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
        if truncated_negative_zero { self.mark_negative_zero(); }
    }
    /// cob_move_edited_to_display: the digits of a numeric-edited sender,
    /// its decimal point (or V/P positions) and a '-' or 'C' for the sign.
    pub fn move_deedited(&mut self, source: &Value) {
        self.resolved();
        let (bytes, symbols) = match source {
            Value::View(view) => match view.kind {
                Kind::Edited { symbols, .. } => (view.raw(), symbols),
                _ => fail("de-editing MOVE requires a numeric-edited sender"),
            },
            _ => fail("de-editing MOVE requires a numeric-edited sender"),
        };
        let (mut digits, mut scale, mut count, mut point, mut negative) = (Vec::new(), 0i32, 0i32, false, false);
        // cob_move_edited_to_display: the module's decimal point.
        let bytes = crate::runtime::internal_symbols(&bytes, false);
        for &byte in &bytes {
            match byte {
                b'0'..=b'9' => { digits.push(byte); if point { scale += 1; } },
                b'.' => point = true,
                b'-' | b'C' => negative = true,
                _ => {},
            }
        }
        if scale == 0 {
            for &(symbol, n) in symbols {
                let n = n as i32;
                match symbol {
                    b'9' | b'0' | b'Z' | b'*' => if point { scale += n } else { count += n },
                    b'P' => if count == 0 { point = true; scale += n } else { scale -= n },
                    b'V' => point = true,
                    _ => {},
                }
            }
        }
        let coefficient = if digits.is_empty() { BigInt::from(0) } else { BigInt::parse_bytes(&digits, 10).unwrap() };
        let value = Number::scaled(coefficient, scale);
        match self.kind {
            Kind::Numeric { digits: places, scale: target, signed, usage } if usage.is_display() => {
                // store_common_region: align on the scales, drop what overflows.
                let units = absolute(&value.units(target, false)) % power(places);
                let ascii = format!("{:0>width$}", units.to_string(), width = places as usize).into_bytes();
                let mut bytes = display_bytes(ascii, negative && signed, usage, signed);
                if bytes.len() != self.size { fail("unsupported DISPLAY storage for de-editing MOVE"); }
                self.mem_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
            },
            _ => {
                // indirect_move through a signed DISPLAY temporary of 76 digits, 38 decimals.
                let units = absolute(&value.units(38, false)) % power(76);
                if negative && units == BigInt::from(0) { fail("de-edited negative zero to a non-DISPLAY receiver not modelled"); }
                let number = Value::Num(Number::new(if negative { -units } else { units }, 38), None);
                if matches!(self.kind, Kind::Edited { .. }) { self.move_edited(&number) } else { self.move_number(&number) }
            },
        }
    }
    /// cob_decimal_get_display with opt 0: an overflow keeps the low-order
    /// digits (mpz_tdiv_r) and the sign of the full result.
    pub fn store_truncated(&mut self, source: &Value) -> bool {
        self.resolved();
        match self.kind {
            Kind::Numeric { digits, scale, signed, usage } if usage.is_display() => {
                let units = source.num().units(scale, false);
                if absolute(&units) < power(digits) { self.assign(source, false); return false; }
                let negative = units.sign() == Sign::Minus;
                let kept = absolute(&units) % power(digits);
                let ascii = format!("{:0>width$}", kept.to_string(), width = digits as usize).into_bytes();
                let mut bytes = display_bytes(ascii, negative && signed, usage, signed);
                self.mem_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
                true
            },
            _ => { self.assign(source, false); false },
        }
    }
    pub fn checked_assign(&mut self, source: &Value, rounded: bool) -> Result<(), SizeError> {
        self.resolved();
        if let Kind::Edited { digits, scale, .. } = self.kind {
            // cob_decimal_get_field keeps the receiver when the result
            // overflows the DISPLAY temporary of the picture's digits.
            if absolute(&source.num().units(scale, rounded)) >= power(digits) { return Err(SizeError); }
            self.assign(source, rounded);
            return Ok(());
        }
        let (digits, scale, signed, usage) = match self.kind {
            Kind::Numeric { digits, scale, signed, usage } => (digits, scale, signed, usage),
            _ => fail("checked arithmetic destination requires numeric storage"),
        };
        if matches!(usage, Usage::Float | Usage::Double) {
            // COB_STORE_KEEP_ON_OVERFLOW: inf, nan or cob_not_finite raise
            // EC-SIZE-OVERFLOW and keep the receiver.
            let bytes = float_bytes(source, usage).ok_or(SizeError)?;
            let finite = if matches!(usage, Usage::Float) { f32::from_le_bytes(bytes[..4].try_into().unwrap()).is_finite() }
                         else { f64::from_le_bytes(bytes[..8].try_into().unwrap()).is_finite() };
            if !finite { return Err(SizeError); }
            self.resolved();
            self.mem_mut()[self.offset..self.offset + self.size].copy_from_slice(&bytes);
            return Ok(());
        }
        let mut units = source.num().units(scale, rounded);
        if matches!(usage, Usage::Native | Usage::Register | Usage::Swapped) {
            // cob_decimal_get_binary: SIZE ERROR beyond size * 8 - sign bits.
            if !signed { units = absolute(&units); }
            if absolute(&units).bits() > (self.size * 8 - signed as usize) as u64 { return Err(SizeError); }
            self.assign(&Value::Num(Number::scaled(units, scale), None), false);
            return Ok(());
        }
        if !matches!(usage, Usage::Index) && absolute(&units) >= power(digits) { return Err(SizeError); }
        // COBOL discards the sign for an unsigned receiver. This is not SIZE ERROR.
        if !signed { units = absolute(&units); }
        self.assign(&Value::Num(Number::scaled(units, scale), None), false);
        Ok(())
    }
    pub fn initialize(&mut self, with_filler: bool) {
        self.resolved();
        for initializer in &self.initializers {
            if initializer.filler && !with_filler { continue; }
            offsets(&initializer.dimensions, self.offset + initializer.offset, &mut |offset| {
                let mut leaf = Self { memory: self.memory.clone(), offset, size: initializer.size,
                                      kind: initializer.kind, dimensions: vec![], initializers: vec![], limit: self.limit };
                let value = match initializer.kind { Kind::Text | Kind::Justified | Kind::AlnumEdited { .. } => Value::text(""), _ => Value::number("0") };
                leaf.assign(&value, false);
            });
        }
    }
    pub fn declare(&mut self, source: &Value) {
        offsets(&self.dimensions, self.offset, &mut |offset| {
            let mut item = self.clone();
            item.offset = offset;
            item.dimensions.clear();
            // Edited VALUE literals describe storage bytes, not a numeric MOVE.
            // So does an explicit VALUE of an alphanumeric-edited item; with
            // no VALUE it starts as edited spaces, as GnuCOBOL initializes it.
            if matches!(item.kind, Kind::Edited { .. }) && source.is_text()
                || matches!(item.kind, Kind::AlnumEdited { .. } | Kind::Justified) && source.text_size() > 0 {
                item.kind = Kind::Text;
            }
            if matches!(item.kind, Kind::Edited { .. }) { item.move_edited(source); } else { item.assign(source, false); }
        });
    }
}

/// Bind a LINKAGE item to a CALL argument: the item keeps its description and
/// addresses the argument's storage `delta` bytes after the argument start.
/// cob_table_sort: glibc's qsort (a merge sort, stable) of the active
/// occurrences; each key (offset in the element, size, kind, numeric,
/// descending) by cob_numeric_cmp, or by memcmp or the program collating
/// sequence (sort_compare, sort_compare_collate).
pub fn table_sort(table: &Value, keys: &[(usize, usize, Kind, bool, bool)]) {
    let view = match table { Value::View(view) => view, _ => fail("SORT requires a table") };
    let (stride, count) = match view.dimensions.as_slice() {
        [(stride, count)] => (*stride, *count),
        _ => fail("SORT of a table with several dimensions not modelled"),
    };
    let size = view.size;
    if stride != size { fail("SORT of a table with a stride unlike its element size not modelled"); }
    let mut elements: Vec<Vec<u8>> = {
        let memory = view.mem();
        (0..count).map(|i| memory[view.offset + i * stride..view.offset + i * stride + size].to_vec()).collect()
    };
    let key = |element: &[u8], offset: usize, length: usize, kind: Kind| View {
        memory: Rc::new(RefCell::new(element[offset..offset + length].to_vec())), offset: 0, size: length, kind,
        dimensions: vec![], initializers: vec![], limit: None };
    elements.sort_by(|a, b| {
        for &(offset, length, kind, numeric, descending) in keys {
            let order = if numeric {
                let integer = matches!(kind, Kind::Numeric { digits, .. } if digits < 19);
                key(a, offset, length, kind).operand_value(integer).compare(&key(b, offset, length, kind).operand_value(integer))
            } else {
                crate::runtime::collated_cmp(&a[offset..offset + length], &b[offset..offset + length])
            };
            if order != std::cmp::Ordering::Equal { return if descending { order.reverse() } else { order }; }
        }
        std::cmp::Ordering::Equal
    });
    let mut memory = view.mem_mut();
    for (i, element) in elements.iter().enumerate() {
        memory[view.offset + i * stride..view.offset + i * stride + size].copy_from_slice(element);
    }
}

/// cob_field_dup holding `bytes`: an item of the same description.
pub fn copy_of(item: &Value, bytes: &[u8]) -> Value {
    match item {
        Value::View(view) => Value::View(View { memory: Rc::new(RefCell::new(bytes.to_vec())), offset: 0, size: bytes.len(),
            kind: view.kind, dimensions: vec![], initializers: vec![], limit: None }),
        _ => fail("report control requires storage"),
    }
}

thread_local! {
    static LITERAL_ARGUMENTS: RefCell<Vec<(String, Memory)>> = const { RefCell::new(Vec::new()) };
}

/// A literal or figurative constant passed BY REFERENCE (output_call): the
/// address of the program's constant, the same at each CALL, in read-only
/// storage for a literal.
pub fn literal_argument(key: &str, bytes: &[u8]) -> Value {
    let memory = LITERAL_ARGUMENTS.with(|literals| {
        let mut literals = literals.borrow_mut();
        if let Some((_, memory)) = literals.iter().find(|(name, _)| name == key) { return memory.clone(); }
        let memory: Memory = Rc::new(RefCell::new(bytes.to_vec()));
        literals.push((key.to_string(), memory.clone()));
        memory
    });
    Value::View(View { memory, offset: 0, size: bytes.len(), kind: Kind::Text, dimensions: vec![], initializers: vec![], limit: None })
}

fn check_writable(memory: &Memory) {
    LITERAL_ARGUMENTS.with(|literals| {
        if literals.borrow().iter().any(|(_, constant)| Rc::ptr_eq(constant, memory)) {
            fail("write into a literal passed BY REFERENCE (SIGSEGV in GnuCOBOL); not modelled");
        }
    })
}

/// The temporary alphanumeric field of a literal or a function result.
pub fn temporary(value: &Value) -> Value {
    let bytes = value.bytes();
    let size = bytes.len();
    Value::View(View { memory: Rc::new(RefCell::new(bytes)), offset: 0, size, kind: Kind::Text, dimensions: vec![], initializers: vec![], limit: None })
}

/// A LINKAGE item that the CALL (or ENTRY) did not pass: no storage.
pub fn unbind(item: &Value) -> Value {
    match item {
        Value::View(template) => Value::View(View { memory: Rc::new(RefCell::new(Vec::new())), offset: 0, size: template.size,
            kind: template.kind, dimensions: template.dimensions.clone(), initializers: template.initializers.clone(), limit: None }),
        _ => crate::runtime::fail("LINKAGE item requires storage"),
    }
}

/// cob_chain_setup: a CHAINING item takes the command-line argument of its
/// rank, space filled or truncated, when it is given.
pub fn chain_setup(item: &Value, parameter: usize) {
    use std::os::unix::ffi::OsStringExt;
    let Some(argument) = std::env::args_os().nth(parameter) else { return };
    match item {
        Value::View(view) => {
            let mut bytes = argument.into_vec();
            bytes.resize(view.size, b' ');
            check_writable(&view.memory);
            define(&view.memory, view.offset, view.size);
            view.memory.borrow_mut()[view.offset..view.offset + view.size].copy_from_slice(&bytes);
        },
        _ => crate::runtime::fail("CHAINING requires a data item"),
    }
}

/// CALL ... USING OMITTED: a NULL address.
/// A system routine's view of a parameter: the bytes behind its data
/// pointer (None for an omitted parameter, a NULL address).
pub fn parameter_bytes(item: &Value) -> Option<Vec<u8>> {
    match item {
        Value::View(view) if view.memory.borrow().is_empty() => None,
        Value::View(view) => { view.resolved(); Some(view.raw()) },
        _ => fail("paramètre de routine système sans stockage"),
    }
}

/// A system routine writing `bytes` at `offset` of a parameter, without
/// PICTURE conversion; a literal passed BY REFERENCE stays protected.
pub fn store_parameter(item: &Value, offset: usize, bytes: &[u8]) {
    let Value::View(view) = item else { fail("paramètre de routine système sans stockage") };
    if view.memory.borrow().is_empty() { fail("écriture d'une routine système à une adresse NULL (SIGSEGV)"); }
    if offset + bytes.len() > view.size { fail("écriture d'une routine système au-delà du paramètre non modélisée"); }
    let mut target = View { memory: view.memory.clone(), offset: view.offset + offset, size: bytes.len(),
        kind: Kind::Text, dimensions: vec![], initializers: vec![], limit: view.limit };
    target.assign_text_move(&Value::Bytes(bytes.to_vec()), true);
}

pub fn omitted() -> Value {
    Value::View(View { memory: Rc::new(RefCell::new(Vec::new())), offset: 0, size: 0, kind: Kind::Text,
                       dimensions: vec![], initializers: vec![], limit: None })
}

/// The cached cob_field size is readable even when LINKAGE has no address.
pub fn descriptor_size(item: &Value) -> usize {
    match item {
        Value::View(view) => view.size,
        _ => fail("LINKAGE descriptor requires a data item"),
    }
}

pub fn set_descriptor_size(item: &mut Value, size: usize) {
    match item {
        Value::View(view) => view.size = size,
        _ => fail("LINKAGE descriptor requires a data item"),
    }
}

/// codegen.c output_entry_function: ANY LENGTH copies only the caller's
/// size, retaining its own attributes and nominal INITIALIZE description.
pub fn update_any_length(item: &mut Value, argument: Option<&Value>) {
    if let Some(Value::View(source)) = argument {
        if source.size != 0 || !source.memory.borrow().is_empty() {
            set_descriptor_size(item, source.size);
        }
    }
}

pub fn rebind(argument: &Value, delta: usize, item: &Value) -> Value {
    bind(argument, delta, item, false)
}

pub fn rebind_any_length(argument: &Value, item: &Value) -> Value {
    bind(argument, 0, item, true)
}

fn bind(argument: &Value, delta: usize, item: &Value, dynamic: bool) -> Value {
    let (source, template) = match (argument, item) {
        (Value::View(source), Value::View(template)) => (source, template),
        _ => crate::runtime::fail("CALL argument and LINKAGE item require storage"),
    };
    if source.size == 0 && source.memory.borrow().is_empty() {
        return unbind(item);
    }
    let offset = source.offset + delta;
    let extent = template.dimensions.iter().map(|(stride, count)| stride * count.saturating_sub(1)).sum::<usize>() + template.size;
    // GnuCOBOL passes only an address: a LINKAGE item longer than its
    // argument would address the caller's neighbouring storage.
    if !dynamic && delta + extent > source.size {
        crate::runtime::fail("LINKAGE item extends beyond the storage of its CALL argument; not modelled");
    }
    Value::View(View { memory: source.memory.clone(), offset, size: template.size, kind: template.kind,
                       dimensions: template.dimensions.clone(), initializers: template.initializers.clone(),
                       limit: Some(source.limit.unwrap_or(source.offset + source.size).min(source.offset + source.size)) })
}

/// BY CONTENT: the called program receives a copy of the argument's bytes.
pub fn content_copy(argument: &Value) -> Value {
    match argument {
        Value::View(source) => {
            let bytes = source.mem()[source.offset..source.offset + source.size].to_vec();
            Value::View(View { memory: Rc::new(RefCell::new(bytes)), offset: 0, size: source.size, kind: source.kind,
                               dimensions: vec![], initializers: source.initializers.clone(), limit: None })
        },
        _ => crate::runtime::fail("BY CONTENT requires a data item"),
    }
}

/// An INSPECT operand as libcob receives it: the field data, and whether it
/// is COB_TYPE_ALPHANUMERIC_ALL (a figurative constant or an ALL literal).
pub struct Operand { pub data: Vec<u8>, pub all: bool }
impl Operand {
    pub fn new(data: Vec<u8>, all: bool) -> Self { Operand { data, all } }
    pub fn of(value: &Value) -> Self {
        match value {
            Value::View(view) => Operand { data: view.raw(), all: false },
            _ => Operand { data: value.bytes(), all: false },
        }
    }
}

#[derive(Clone, Copy, PartialEq)]
pub enum InspectMode { All, Leading, First, Trailing }

/// libcob's static INSPECT buffers. They live across INSPECT statements of
/// the run unit, and cob_inspect_init only clears the marker range it knows.
struct InspectBuffers {
    mark: Vec<u8>, mark_size: usize, mark_min: usize, mark_max: usize,
    repdata: Vec<u8>, repdata_written: Vec<bool>, repdata_size: usize,
}
thread_local! {
    static INSPECT: RefCell<InspectBuffers> = RefCell::new(InspectBuffers {
        mark: vec![], mark_size: 0, mark_min: 0, mark_max: 0,
        repdata: vec![], repdata_written: vec![], repdata_size: 0,
    });
}
const COB_NORMAL_BUFF: usize = 2048;

fn memory_fault() -> ! {
    fail("INSPECT: libcob 3.2 would access memory outside its INSPECT buffers; not modelled")
}
impl InspectBuffers {
    fn mark_at(&self, i: usize) -> u8 { *self.mark.get(i).unwrap_or_else(|| memory_fault()) }
    fn set_mark(&mut self, pos: usize, length: usize) {
        if pos.checked_add(length).map_or(true, |end| end > self.mark.len()) { memory_fault(); }
        self.mark[pos..pos + length].iter_mut().for_each(|m| *m = 1);
        let pos_end = pos.wrapping_add(length).wrapping_sub(1);
        if (self.mark_min == 0 && self.mark_at(self.mark_min) == 0) || pos < self.mark_min { self.mark_min = pos; }
        if pos_end > self.mark_max { self.mark_max = pos_end; }
    }
    fn is_marked(&self, pos: usize, length: usize) -> bool {
        if self.mark_at(self.mark_min) == 0 || self.mark_max < pos || self.mark_min >= pos.wrapping_add(length) {
            return false;
        }
        if self.mark_min >= pos || self.mark_max < pos.wrapping_add(length) { return true; }
        (0..length).any(|i| self.mark_at(pos + i) != 0)
    }
    fn setup_repdata(&mut self, size: usize) {
        if size > self.repdata_size {
            self.repdata_size = if !self.repdata.is_empty() { size }
                                else if size < COB_NORMAL_BUFF { COB_NORMAL_BUFF } else { size };
            // cob_fast_malloc: the content is undefined until written.
            self.repdata = vec![0; self.repdata_size + 1];
            self.repdata_written = vec![false; self.repdata_size + 1];
        }
    }
    fn write_repdata(&mut self, pos: usize, bytes: &[u8]) {
        if pos + bytes.len() > self.repdata.len() { memory_fault(); }
        self.repdata[pos..pos + bytes.len()].copy_from_slice(bytes);
        self.repdata_written[pos..pos + bytes.len()].iter_mut().for_each(|w| *w = true);
    }
}

/// One INSPECT statement (or its TALLYING/REPLACING half), following
/// GnuCOBOL 3.2 strings.c: cob_inspect_init, cob_inspect_start, BEFORE/AFTER,
/// the counting/replacing calls and cob_inspect_finish.
pub struct Inspect {
    memory: Memory, offset: usize, size: usize,
    start: usize, end: usize, replacing: bool,
    /// cob_real_get_sign of an overpunched signed DISPLAY target: the sign
    /// byte's position and the sign, restored by cob_real_put_sign.
    sign: Option<(usize, i32)>,
}
impl Inspect {
    fn common(target: &Value) -> Self {
        crate::runtime::exception::clear_current();
        let view = match target { Value::View(view) => view, _ => fail("INSPECT requires a data item") };
        view.resolved();
        drop(view.mem());
        let mut sign = None;
        if let Kind::Numeric { signed: true, usage, .. } = view.kind {
            match usage {
                Usage::Display | Usage::SignLeading => {
                    let position = view.offset + if matches!(usage, Usage::SignLeading) { 0 } else { view.size - 1 };
                    let mut memory = view.mem_mut();
                    let byte = memory[position];
                    let value = if byte.is_ascii_digit() || byte == b' ' { 1 }
                        else if (b'p'..=b'y').contains(&byte) { memory[position] = byte & !0x40; -1 }
                        else { memory[position] = b'0'; 1 };
                    sign = Some((position, value));
                },
                Usage::SignLeadingSeparate | Usage::SignTrailingSeparate => {},
                _ => fail("INSPECT of a binary or packed item not modelled"),
            }
        } else if let Kind::Numeric { usage: Usage::Packed | Usage::PackedNoSign | Usage::Binary | Usage::Index | Usage::Native | Usage::Register | Usage::Swapped, .. } = view.kind {
            fail("INSPECT of a binary or packed item not modelled");
        }
        // COB_FIELD_DATA/COB_FIELD_SIZE leave a separate sign byte out.
        let (offset, size) = match view.kind {
            Kind::Numeric { signed: true, usage: Usage::SignLeadingSeparate, .. } => (view.offset + 1, view.size - 1),
            Kind::Numeric { signed: true, usage: Usage::SignTrailingSeparate, .. } => (view.offset, view.size - 1),
            _ => (view.offset, view.size),
        };
        Inspect { memory: view.memory.clone(), offset, size, start: 0, end: 0, replacing: false, sign }
    }
    pub fn init(target: &Value, replacing: bool) -> Self {
        let mut inspect = Self::common(target);
        inspect.replacing = replacing;
        let size = inspect.size;
        INSPECT.with(|buffers| {
            let mut b = buffers.borrow_mut();
            if size > b.mark_size {
                b.mark_size = if !b.mark.is_empty() { size } else if size < COB_NORMAL_BUFF { COB_NORMAL_BUFF } else { size };
                b.mark = vec![0; b.mark_size + 1];
            } else if b.mark_size != 0 && b.mark_at(b.mark_min) != 0 {
                let (min, max) = (b.mark_min, b.mark_max);
                let length = max.wrapping_sub(min).wrapping_add(1);
                if min.checked_add(length).map_or(true, |end| end > b.mark.len()) { memory_fault(); }
                b.mark[min..min + length].iter_mut().for_each(|m| *m = 0);
            }
            b.mark_min = 0;
            b.mark_max = 0;
        });
        inspect
    }
    pub fn init_converting(target: &Value) -> Self { Self::common(target) }
    fn data(&self) -> Vec<u8> {
        check_defined(&self.memory, self.offset, self.size);
        self.memory.borrow()[self.offset..self.offset + self.size].to_vec()
    }
    pub fn start(&mut self) { self.start = 0; self.end = self.size; }
    fn find(&self, operand: &Operand) -> Option<usize> {
        let data = self.data();
        let len = operand.data.len();
        let end_p = self.end as isize - len as isize + 1;
        if (self.start as isize) > end_p { return None; }
        (self.start..end_p as usize).find(|&p| data[p..p + len] == operand.data[..])
    }
    pub fn before(&mut self, operand: &Operand) { if let Some(p) = self.find(operand) { self.end = p; } }
    pub fn after(&mut self, operand: &Operand) {
        self.start = match self.find(operand) { Some(p) => p + operand.data.len(), None => self.end };
    }
    /// cob_inspect_characters for TALLYING: the count to cob_add_int.
    pub fn tally_characters(&mut self) -> i64 {
        let (pos, len) = (self.start, self.end - self.start);
        if len == 0 { return 0; }
        INSPECT.with(|buffers| {
            let mut b = buffers.borrow_mut();
            let n = if b.is_marked(pos, len) { (pos..pos + len).filter(|&i| b.mark_at(i) == 0).count() } else { len };
            b.set_mark(pos, len);
            n as i64
        })
    }
    /// cob_inspect_characters for REPLACING CHARACTERS BY operand.
    pub fn replace_characters(&mut self, by: &Operand) {
        let (pos, len) = (self.start, self.end - self.start);
        if len == 0 { return; }
        let byte = *by.data.first().unwrap_or_else(|| memory_fault());
        INSPECT.with(|buffers| {
            let mut b = buffers.borrow_mut();
            b.setup_repdata(self.size);
            if b.is_marked(pos, len) {
                for i in pos..pos + len { if b.mark_at(i) == 0 { b.write_repdata(i, &[byte]); } }
            } else {
                b.write_repdata(pos, &vec![byte; len]);
            }
            b.set_mark(pos, len);
        })
    }
    /// The byte compared at offset i (relative to inspect_start, possibly negative
    /// after libcob's TRAILING step); before the item it is outside the model.
    fn matches(&self, data: &[u8], i: isize, pattern: &[u8]) -> bool {
        let at = self.start as isize + i;
        if at < 0 || at as usize + pattern.len() > data.len() { memory_fault(); }
        data[at as usize..at as usize + pattern.len()] == *pattern
    }
    /// inspect_common for TALLYING: the count to cob_add_int.
    pub fn tally(&mut self, mode: InspectMode, value: &Operand) -> i64 {
        let (pos, len) = (self.start, self.end - self.start);
        let f2 = &value.data[..];
        if len == 0 || f2.len() > len { return 0; }
        let data = self.data();
        INSPECT.with(|buffers| {
            let mut b = buffers.borrow_mut();
            let mut n = 0i64;
            let size = f2.len() as isize;
            match mode {
                InspectMode::Trailing => {
                    let mut i = (len - f2.len()) as isize;
                    let mut first_marker = 0isize;
                    loop {
                        if !self.matches(&data, i, f2) { break; }
                        if !b.is_marked((pos as isize + i) as usize, f2.len()) {
                            n += 1;
                            first_marker = i;
                            i -= size - 1;
                        }
                        if i == 0 { break; }
                        i -= 1;
                    }
                    if n != 0 {
                        b.set_mark((pos as isize + first_marker) as usize, (len as isize - first_marker) as usize);
                    }
                },
                InspectMode::Leading => {
                    let i_max = (len - f2.len() + 1) as isize;
                    let mut last_marker = 0isize;
                    let mut i = 0isize;
                    while i < i_max {
                        if !self.matches(&data, i, f2) { break; }
                        if !b.is_marked(pos + i as usize, f2.len()) {
                            n += 1;
                            i += size - 1;
                            last_marker = i;
                        }
                        i += 1;
                    }
                    // libcob 3.2 marks last_marker positions, not last_marker + 1.
                    if n != 0 { b.set_mark(pos, last_marker as usize); }
                },
                InspectMode::All | InspectMode::First => {
                    let i_max = (len - f2.len() + 1) as isize;
                    let mut i = 0isize;
                    while i < i_max {
                        if self.matches(&data, i, f2) && !b.is_marked(pos + i as usize, f2.len()) {
                            n += 1;
                            b.set_mark(pos + i as usize, f2.len());
                            if mode == InspectMode::First { break; }
                            i += size - 1;
                        }
                        i += 1;
                    }
                },
            }
            n
        })
    }
    /// inspect_common for REPLACING mode `from` BY `to`.
    pub fn replace(&mut self, mode: InspectMode, to: &Operand, from: &Operand) {
        let (pos, len) = (self.start, self.end - self.start);
        if len == 0 { return; }
        let f2 = &from.data[..];
        let f1: Vec<u8> = if to.data.len() != f2.len() {
            if !to.all { crate::runtime::exception::set("EC-RANGE-INSPECT-SIZE"); return; }
            to.data.iter().cycle().take(f2.len()).copied().collect()
        } else { to.data.clone() };
        if f2.len() > len { return; }
        let data = self.data();
        let size = self.size;
        INSPECT.with(|buffers| {
            let mut b = buffers.borrow_mut();
            let mut do_mark = |b: &mut InspectBuffers, at: usize| -> bool {
                if b.is_marked(at, f2.len()) { return false; }
                b.setup_repdata(size);
                b.write_repdata(at, &f1);
                b.set_mark(at, f2.len());
                true
            };
            let step = f2.len() as isize;
            match mode {
                InspectMode::Trailing => {
                    let mut i = (len - f2.len()) as isize;
                    loop {
                        if !self.matches(&data, i, f2) { break; }
                        if do_mark(&mut b, (pos as isize + i) as usize) { i -= step - 1; }
                        if i == 0 { break; }
                        i -= 1;
                    }
                },
                InspectMode::Leading => {
                    let i_max = (len - f2.len() + 1) as isize;
                    let mut i = 0isize;
                    while i < i_max {
                        if !self.matches(&data, i, f2) { break; }
                        if do_mark(&mut b, pos + i as usize) { i += step - 1; }
                        i += 1;
                    }
                },
                InspectMode::All | InspectMode::First => {
                    let i_max = (len - f2.len() + 1) as isize;
                    let mut i = 0isize;
                    while i < i_max {
                        if self.matches(&data, i, f2) && do_mark(&mut b, pos + i as usize) {
                            if mode == InspectMode::First { break; }
                            i += step - 1;
                        }
                        i += 1;
                    }
                },
            }
        })
    }
    fn put_sign(&self) {
        if let Some((position, -1)) = self.sign { check_writable(&self.memory); self.memory.borrow_mut()[position] |= 0x40; }
    }
    /// cob_inspect_converting; it restores the sign itself, unless it returns early.
    pub fn convert(&mut self, from: &Operand, to: &Operand) {
        let len = self.end - self.start;
        if len == 0 { return; }
        let f2: Vec<u8> = if from.data.len() != to.data.len() {
            if !to.all { crate::runtime::exception::set("EC-RANGE-INSPECT-SIZE"); return; }
            to.data.iter().cycle().take(from.data.len()).copied().collect()
        } else { to.data.clone() };
        let mut table = [None; 256];
        for (&a, &b) in from.data.iter().zip(&f2) { if table[a as usize].is_none() { table[a as usize] = Some(b); } }
        {
            check_writable(&self.memory);
            let mut memory = self.memory.borrow_mut();
            for byte in &mut memory[self.offset + self.start..self.offset + self.end] {
                if let Some(b) = table[*byte as usize] { *byte = b; }
            }
        }
        self.put_sign();
    }
    pub fn finish(self) {
        if self.replacing {
            INSPECT.with(|buffers| {
                let b = buffers.borrow();
                if b.repdata_size != 0 && b.mark_at(b.mark_min) != 0 {
                    check_writable(&self.memory);
                    let mut memory = self.memory.borrow_mut();
                    let mut i = b.mark_min;
                    while i <= b.mark_max {
                        if b.mark_at(i) != 0 {
                            if i >= self.size || !b.repdata_written[i] { memory_fault(); }
                            memory[self.offset + i] = b.repdata[i];
                        }
                        if i == usize::MAX { break; }
                        i += 1;
                    }
                }
            });
        }
        self.put_sign();
    }
}

/// STRING (libcob cob_string_init/delimited/append/finish): bytes are copied
/// into the receiver's storage; nothing is padded.
pub struct StringInto { memory: Memory, offset: usize, size: usize, position: i64, overflow: bool, delimiter: Option<Vec<u8>> }
impl StringInto {
    pub fn init(target: &Value, pointer: Option<i128>) -> Self {
        let view = match target { Value::View(view) => view, _ => fail("STRING INTO requires a data item") };
        view.resolved();
        view.check_storage();
        crate::runtime::exception::clear_current();
        let mut s = StringInto { memory: view.memory.clone(), offset: view.offset, size: view.size, position: 0, overflow: false, delimiter: None };
        if let Some(p) = pointer {
            if p < i32::MIN as i128 || p > i32::MAX as i128 { fail("STRING POINTER outside the C int range"); }
            s.position = p as i64 - 1;
            if s.position < 0 || s.position >= s.size as i64 { s.overflow = true; crate::runtime::exception::set("EC-OVERFLOW-STRING"); }
        }
        s
    }
    pub fn delimited(&mut self, delimiter: Option<Operand>) { self.delimiter = delimiter.map(|d| d.data); }
    pub fn append(&mut self, source: &Operand) {
        if self.overflow { return; }
        let data = &source.data;
        let mut size = data.len();
        if size == 0 { return; }
        if let Some(d) = &self.delimiter {
            let limit = data.len() as i64 - d.len() as i64 + 1;
            if let Some(i) = (0..limit.max(0) as usize).find(|&i| data[i..i + d.len()] == d[..]) { size = i; }
        }
        let room = self.size as i64 - self.position;
        check_writable(&self.memory);
        let mut memory = self.memory.borrow_mut();
        let start = self.offset + self.position as usize;
        define(&self.memory, start, (size as i64).min(room) as usize);
        if size as i64 <= room {
            memory[start..start + size].copy_from_slice(&data[..size]);
            self.position += size as i64;
        } else {
            memory[start..start + room as usize].copy_from_slice(&data[..room as usize]);
            self.position += room;
            self.overflow = true;
            crate::runtime::exception::set("EC-OVERFLOW-STRING");
        }
    }
    /// The overflow condition and the value cob_set_int stores in the POINTER.
    pub fn finish(&self) -> (bool, i64) { (self.overflow, self.position + 1) }
}

/// UNSTRING (libcob cob_unstring_*). `into` returns what cob_unstring_into
/// moves: the field bytes, the delimiter found and the count, or None when
/// libcob returns early.
pub struct Unstring { source: Value, position: i64, count: i64, exception: bool, delimiters: Vec<(Vec<u8>, bool)> }
impl Unstring {
    pub fn init(source: &Value, pointer: Option<i128>) -> Self {
        crate::runtime::exception::clear_current();
        let mut u = Unstring { source: source.clone(), position: 0, count: 0, exception: false, delimiters: vec![] };
        if let Some(p) = pointer {
            if p < i32::MIN as i128 || p > i32::MAX as i128 { fail("UNSTRING POINTER outside the C int range"); }
            u.position = p as i64 - 1;
            if u.position < 0 || u.position >= u.data().len() as i64 { u.exception = true; crate::runtime::exception::set("EC-OVERFLOW-UNSTRING"); }
        }
        u
    }
    fn data(&self) -> Vec<u8> {
        match &self.source { Value::View(view) => { view.resolved(); view.raw() }, other => other.bytes() }
    }
    pub fn delimited(&mut self, delimiter: Operand, all: bool) { self.delimiters.push((delimiter.data, all)); }
    pub fn next_into(&mut self, target_size: usize) -> Option<(Vec<u8>, Option<Vec<u8>>, i64)> {
        if self.exception { return None; }
        let data = self.data();
        let srsize = data.len() as i64;
        if self.position >= srsize { return None; }
        let start = self.position as usize;
        let mut found = None;
        let mut match_size: i64 = 0;
        if self.delimiters.is_empty() {
            match_size = (target_size as i64).min(srsize - self.position);
            self.position += match_size;
        } else if self.delimiters.len() == 1 {
            let (d, all) = &self.delimiters[0];
            let dlsize = d.len() as i64;
            let s = srsize - dlsize + 1;
            let mut p = start as i64;
            while p < s {
                if data[p as usize..(p + dlsize) as usize] == d[..] {
                    match_size = p - start as i64;
                    self.position += match_size + dlsize;
                    found = Some(d.clone());
                    if *all {
                        p += dlsize;
                        while p < s {
                            if data[p as usize..(p + dlsize) as usize] != d[..] { break; }
                            self.position += dlsize;
                            p += dlsize;
                        }
                    }
                    break;
                }
                p += 1;
            }
        } else {
            let mut p = start as i64;
            'scan: while p < srsize {
                for (d, all) in &self.delimiters {
                    let dlsize = d.len() as i64;
                    let s2 = srsize - dlsize + 1;
                    if p > s2 { continue; }
                    // libcob compares at p == s2 too, one byte past the item.
                    if p == s2 {
                        if dlsize > 1 && data[p as usize..] == d[..(dlsize - 1) as usize] {
                            fail("UNSTRING: libcob 3.2 compares one byte past the sending item; not modelled");
                        }
                        continue;
                    }
                    if data[p as usize..(p + dlsize) as usize] == d[..] {
                        match_size = p - start as i64;
                        self.position += match_size + dlsize;
                        found = Some(d.clone());
                        if *all {
                            p += dlsize;
                            while p < s2 {
                                if data[p as usize..(p + dlsize) as usize] != d[..] { break; }
                                self.position += dlsize;
                                p += dlsize;
                            }
                        }
                        break 'scan;
                    }
                }
                p += 1;
            }
        }
        if !self.delimiters.is_empty() && found.is_none() {
            match_size = srsize - self.position;
            self.position = srsize;
        }
        self.count += 1;
        Some((data[start..start + match_size as usize].to_vec(), found, match_size))
    }
    pub fn count(&self) -> i64 { self.count }
    /// The overflow condition, whether any exception is set, and the POINTER value.
    pub fn finish(&mut self, size_exception: bool) -> (bool, bool, i64) {
        // cob_unstring_tallying (cob_add_int), then cob_unstring_finish.
        if size_exception { crate::runtime::exception::set("EC-SIZE-OVERFLOW"); }
        if self.position < self.data().len() as i64 { crate::runtime::exception::set("EC-OVERFLOW-UNSTRING"); }
        let overflow = self.exception || self.position < self.data().len() as i64;
        (overflow, overflow || size_exception, self.position + 1)
    }
}

/// cob_decimal_get_display (opt 0), for a DISPLAY receiver or the DISPLAY
/// temporary of an edited one: the result has more digits than the PICTURE.
pub fn display_overflow(item: &Value, source: &Value, rounded: bool) -> bool {
    let Value::View(view) = item else { fail("arithmetic receiver requires storage") };
    match view.kind {
        Kind::Numeric { digits, scale, usage, .. } if usage.is_display() => absolute(&source.num().units(scale, rounded)) >= power(digits),
        Kind::Edited { digits, scale, .. } => absolute(&source.num().units(scale, rounded)) >= power(digits),
        _ => fail("DISPLAY overflow check of another receiver"),
    }
}

/// propagate_table (codegen.c): the bytes of the first occurrence of an
/// OCCURS item copied over its other occurrences, the outer subscripts given.
pub fn propagate_table(table: &Value, outer: &[Value]) {
    let Value::View(view) = table else { fail("OCCURS item requires storage") };
    let Some(&(stride, count)) = view.dimensions.last() else { fail("propagate_table of an item without OCCURS") };
    if outer.len() + 1 != view.dimensions.len() { fail("wrong number of subscripts"); }
    let mut base = view.offset;
    for (index, (step, limit)) in outer.iter().zip(&view.dimensions) {
        let number = index.integer("subscript");
        if number < 1 || number > *limit as i128 { fail("COBOL subscript out of bounds"); }
        base += (number as usize - 1) * step;
    }
    let first = View { memory: view.memory.clone(), offset: base, size: view.size, kind: Kind::Text, dimensions: vec![],
                       initializers: vec![], limit: view.limit };
    let bytes = first.raw();
    for occurrence in 1..count {
        let next = View { offset: base + occurrence * stride, ..first.clone() };
        next.mem_mut()[next.offset..next.offset + next.size].copy_from_slice(&bytes);
    }
}

/// COB_FIELD_SIZE: the storage size without a separate sign byte.
pub fn field_size(item: &Value) -> usize {
    match item {
        Value::View(view) => {
            view.resolved();
            match view.kind {
                Kind::Numeric { signed: true, usage: Usage::SignLeadingSeparate | Usage::SignTrailingSeparate, .. } => view.size - 1,
                _ => view.size,
            }
        },
        _ => fail("UNSTRING INTO requires a data item"),
    }
}

/// memset of spaces over the item's storage (DELIMITER IN without a delimiter).
pub fn fill_spaces(item: &Value) {
    match item {
        Value::View(view) => {
            view.resolved();
            view.mem_mut()[view.offset..view.offset + view.size].iter_mut().for_each(|b| *b = b' ');
        },
        _ => fail("DELIMITER IN requires a data item"),
    }
}

// Addresses: USAGE POINTER, ADDRESS OF, BASED and LINKAGE items, ALLOCATE
// and FREE. A native address is replaced by a region (a 01 record of a
// program, a block without records such as an EXTERNAL item or a BY CONTENT
// copy, an ALLOCATE area) and an offset in it, encoded in the 8 bytes of a
// POINTER (a void * of libcob, x86_64). Addresses inside one region keep the
// native order and differences; the values themselves, like the native ones
// under ASLR, are not reproducible.
const ADDRESS_BASE: u64 = 0x0000_7f00_0000_0000;
const REGION_SPAN: u64 = 1 << 32;
/// common.c COB_MAX_ALLOC_SIZE on Linux x86_64.
const MAX_ALLOC_SIZE: i128 = 2_147_483_646;

struct Region {
    memory: std::rc::Weak<RefCell<Vec<u8>>>,
    start: usize,
    len: usize,
    /// cob_alloc_cache: an ALLOCATE area not yet freed.
    allocated: Option<Memory>,
    freed: bool,
}

thread_local! {
    static REGIONS: RefCell<Vec<Region>> = const { RefCell::new(Vec::new()) };
    static REGION_INDEX: RefCell<std::collections::HashMap<(usize, usize), usize>> = RefCell::new(std::collections::HashMap::new());
    static RECORDS: RefCell<std::collections::HashMap<usize, (std::rc::Weak<RefCell<Vec<u8>>>, Vec<(usize, usize)>)>> =
        RefCell::new(std::collections::HashMap::new());
}

fn memory_key(memory: &Memory) -> usize { Rc::as_ptr(memory) as *const u8 as usize }

fn same_memory(weak: &std::rc::Weak<RefCell<Vec<u8>>>, memory: &Memory) -> bool {
    weak.upgrade().is_some_and(|alive| Rc::ptr_eq(&alive, memory))
}

/// The 01 records (offset, size) of a program's storage: each one is a
/// separate allocation of cobc (its own b_ array).
pub fn records(memory: &Memory, records: &[(usize, usize)]) {
    RECORDS.with(|map| { map.borrow_mut().insert(memory_key(memory), (Rc::downgrade(memory), records.to_vec())); });
}

fn region_id(memory: &Memory, start: usize, len: usize, allocated: Option<Memory>) -> usize {
    let key = (memory_key(memory), start);
    let known = REGION_INDEX.with(|index| index.borrow().get(&key).copied());
    if let Some(id) = known {
        if REGIONS.with(|regions| same_memory(&regions.borrow()[id].memory, memory)) { return id; }
    }
    let id = REGIONS.with(|regions| {
        let mut regions = regions.borrow_mut();
        regions.push(Region { memory: Rc::downgrade(memory), start, len, allocated, freed: false });
        regions.len() - 1
    });
    REGION_INDEX.with(|index| { index.borrow_mut().insert(key, id); });
    id
}

fn encode(id: usize, offset: usize) -> u64 { ADDRESS_BASE + id as u64 * REGION_SPAN + offset as u64 }

/// The region and the offset in it of an address that this run unit made.
fn decode(address: u64) -> (Memory, usize, usize, usize) {
    let relative = address.checked_sub(ADDRESS_BASE)
        .unwrap_or_else(|| fail("address not obtained from ADDRESS OF or ALLOCATE; not modelled"));
    let (id, offset) = ((relative / REGION_SPAN) as usize, (relative % REGION_SPAN) as usize);
    REGIONS.with(|regions| {
        let regions = regions.borrow();
        let region = regions.get(id).unwrap_or_else(|| fail("address not obtained from ADDRESS OF or ALLOCATE; not modelled"));
        let memory = region.memory.upgrade().unwrap_or_else(|| fail(if region.freed {
            "address of storage released by FREE; not modelled"
        } else {
            "address of storage released by CANCEL; not modelled"
        }));
        (memory, region.start, region.len, offset)
    })
}

/// ADDRESS OF: NULL for an item without storage (BASED or LINKAGE item
/// whose address is not set).
pub fn address_of(item: &Value) -> u64 {
    let Value::View(view) = item else { fail("ADDRESS OF requires storage") };
    let key = memory_key(&view.memory);
    if view.memory.borrow().is_empty() {
        // A freed ALLOCATE area keeps its (dangling) address.
        return match REGION_INDEX.with(|index| index.borrow().get(&(key, 0)).copied()) {
            Some(id) if REGIONS.with(|regions| same_memory(&regions.borrow()[id].memory, &view.memory)) => encode(id, view.offset),
            _ => 0,
        };
    }
    let record = RECORDS.with(|map| {
        map.borrow().get(&key).filter(|(weak, _)| same_memory(weak, &view.memory))
            .and_then(|(_, records)| records.iter().find(|(start, size)| *start <= view.offset && view.offset < start + size).copied())
    });
    let (start, len) = record.unwrap_or((0, view.memory.borrow().len()));
    encode(region_id(&view.memory, start, len, None), view.offset - start)
}

/// SET ADDRESS OF: the item (at `delta` in its 01 record) addresses the
/// storage at `address`; accesses beyond the region are named stops.
pub fn bind_address(address: u64, delta: usize, item: &Value) -> Value {
    let Value::View(template) = item else { fail("SET ADDRESS OF requires storage") };
    if address == 0 { return unbind(item); }
    let (memory, start, len, offset) = decode(address);
    let offset = start.checked_add(offset).and_then(|o| o.checked_add(delta))
        .unwrap_or_else(|| fail("address outside its storage; not modelled"));
    Value::View(View { memory, offset, size: template.size, kind: template.kind, dimensions: template.dimensions.clone(),
                       initializers: template.initializers.clone(), limit: Some(start + len) })
}

thread_local! {
    static STATIC_BASES: RefCell<std::collections::HashMap<String, u64>> = RefCell::new(std::collections::HashMap::new());
}

/// The static base pointer of a LINKAGE item of no USING: its address
/// outlives the program instance (CANCEL).
pub fn static_base(key: &str) -> u64 { STATIC_BASES.with(|bases| bases.borrow().get(key).copied().unwrap_or(0)) }

pub fn set_static_base(key: &str, address: u64) {
    STATIC_BASES.with(|bases| { bases.borrow_mut().insert(key.to_string(), address); });
}

/// The value of a USAGE POINTER item (8 bytes, native byte order).
pub fn pointer_value(item: &Value) -> u64 {
    let Value::View(view) = item else { fail("POINTER requires storage") };
    if view.size != 8 { fail("POINTER item of another size than 8"); }
    let memory = view.mem();
    u64::from_le_bytes(memory[view.offset..view.offset + 8].try_into().unwrap())
}

pub fn set_pointer(item: &Value, address: u64) {
    let Value::View(view) = item else { fail("POINTER requires storage") };
    if view.size != 8 { fail("POINTER item of another size than 8"); }
    let mut memory = view.mem_mut();
    memory[view.offset..view.offset + 8].copy_from_slice(&address.to_le_bytes());
}

/// SET pointer UP/DOWN BY n: the address moves by n bytes.
pub fn offset_address(address: u64, delta: i128) -> u64 {
    let moved = address as i128 + delta;
    if !(0..=u64::MAX as i128).contains(&moved) { fail("address arithmetic outside the address space"); }
    moved as u64
}

/// A relation between two addresses as cobc generates it, (int)(a - b)
/// against zero. The order of two different regions depends on the native
/// layout of storage: a named stop.
pub fn compare_addresses(left: u64, right: u64) -> std::cmp::Ordering {
    if left == right { return std::cmp::Ordering::Equal; }
    let region = |address: u64| address.checked_sub(ADDRESS_BASE).map(|relative| relative / REGION_SPAN);
    if left == 0 || right == 0 || region(left).is_none() || region(left) != region(right) {
        fail("order of addresses of different storage areas (native layout); not modelled");
    }
    left.cmp(&right)
}

/// cob_allocate: `size` bytes, NULL when the size is not positive or above
/// COB_MAX_ALLOC_SIZE. calloc for INITIALIZED to low-values; otherwise the
/// malloc area is undetermined until written, and reading it is a named stop.
pub fn allocate(size: i128, zeroed: bool) -> u64 {
    crate::runtime::exception::clear_current();
    if size > MAX_ALLOC_SIZE { crate::runtime::exception::set("EC-STORAGE-IMP"); }
    if size <= 0 || size > MAX_ALLOC_SIZE { return 0; }
    let memory = memory(size as usize);
    if !zeroed {
        UNDEFINED.with(|undefined| undefined.borrow_mut().push((Rc::downgrade(&memory), vec![true; size as usize])));
    }
    encode(region_id(&memory.clone(), 0, size as usize, Some(memory)), 0)
}

/// ALLOCATE n CHARACTERS: cob_get_llint of the size (integer part).
pub fn allocate_value(size: &Value, zeroed: bool) -> u64 {
    allocate(size.num().units(0, false).to_string().parse::<i128>().unwrap_or(i128::MAX), zeroed)
}

thread_local! {
    /// The bytes of malloc areas not yet written.
    static UNDEFINED: RefCell<Vec<(std::rc::Weak<RefCell<Vec<u8>>>, Vec<bool>)>> = RefCell::new(Vec::new());
}

pub fn check_defined(memory: &Memory, offset: usize, size: usize) {
    UNDEFINED.with(|undefined| {
        let undefined = undefined.borrow();
        if undefined.is_empty() { return; }
        let Some((_, mask)) = undefined.iter().find(|(area, _)| area.strong_count() > 0 && std::ptr::eq(area.as_ptr(), Rc::as_ptr(memory))) else { return };
        if mask.get(offset..offset + size).is_some_and(|bytes| bytes.contains(&true)) {
            fail("read of ALLOCATE storage before it is written (undetermined malloc contents in GnuCOBOL); not modelled");
        }
    })
}

fn define(memory: &Memory, offset: usize, size: usize) {
    UNDEFINED.with(|undefined| {
        let mut undefined = undefined.borrow_mut();
        if undefined.is_empty() { return; }
        undefined.retain(|(area, _)| area.strong_count() > 0);
        let Some(index) = undefined.iter().position(|(area, _)| std::ptr::eq(area.as_ptr(), Rc::as_ptr(memory))) else { return };
        let mask = &mut undefined[index].1;
        if let Some(bytes) = mask.get_mut(offset..offset + size) { bytes.fill(false); }
        if !mask.contains(&true) { undefined.remove(index); }
    })
}

/// SET ... UP/DOWN BY n: cob_get_int of the amount (integer part).
pub fn address_delta(amount: &Value) -> i128 { amount.num().units(0, false).to_string().parse::<i128>().unwrap_or_else(|_| fail("SET UP/DOWN BY overflow")) }

/// INITIALIZED TO ALL literal: the literal repeated over the area.
pub fn fill_repeated(area: &Value, pattern: &[u8]) {
    let Value::View(view) = area else { fail("ALLOCATE area requires storage") };
    let mut memory = view.mem_mut();
    for (index, byte) in memory[view.offset..view.offset + view.size].iter_mut().enumerate() { *byte = pattern[index % pattern.len()]; }
}

/// The area of an ALLOCATE as an alphanumeric item (INITIALIZED TO).
pub fn allocated_area(address: u64) -> Value {
    let (memory, start, len, offset) = decode(address);
    Value::View(View { memory, offset: start + offset, size: len - offset, kind: Kind::Text, dimensions: vec![],
                       initializers: vec![], limit: Some(start + len) })
}

/// cob_free_alloc: only the address returned by an ALLOCATE is freed (its
/// storage then has no bytes); any other address leaves EC-STORAGE-NOT-ALLOC.
pub fn free(address: u64) -> bool {
    crate::runtime::exception::clear_current();
    if address == 0 { return false; }
    let freed = address.checked_sub(ADDRESS_BASE).filter(|relative| relative % REGION_SPAN == 0).is_some_and(|relative| {
        REGIONS.with(|regions| {
            let mut regions = regions.borrow_mut();
            let Some(region) = regions.get_mut((relative / REGION_SPAN) as usize) else { return false };
            match region.allocated.take() {
                Some(memory) => { memory.borrow_mut().clear(); region.freed = true; true },
                None => false,
            }
        })
    });
    if !freed { crate::runtime::exception::set("EC-STORAGE-NOT-ALLOC"); }
    freed
}

/// The bytes of an ASSIGN data item; none when it has no address.
pub fn assign_bytes(item: &Value) -> Option<Vec<u8>> {
    if let Value::View(view) = item {
        if view.memory.borrow().len() < view.offset + view.size { return None; }
    }
    Some(Operand::of(item).data)
}

/// DISPLAY of a POINTER: "0x" and 16 hexadecimal digits; a non-NULL value
/// is a native address, different at each run (ASLR).
pub fn pointer_display(address: u64) -> Value {
    if address != 0 { fail("DISPLAY of a non-NULL address (native value, not reproducible); not modelled"); }
    Value::text("0x0000000000000000")
}

/// Output of storage containing POINTER items: their non-NULL values are
/// native addresses.
pub fn check_no_address(item: &Value, offsets: &[usize]) {
    let Value::View(view) = item else { return };
    let memory = view.mem();
    for offset in offsets {
        if memory[view.offset + offset..view.offset + offset + 8].iter().any(|&byte| byte != 0) {
            fail("output of a non-NULL address (native value, not reproducible); not modelled");
        }
    }
}
