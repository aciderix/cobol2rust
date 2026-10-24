// Shared COBOL storage. Views preserve group/element/REDEFINES aliasing.
use std::cell::RefCell;
use std::rc::Rc;
use num_bigint::{BigInt, Sign};
use crate::runtime::{Value, Number, SizeError, fail, absolute, power};

pub type Memory = Rc<RefCell<Vec<u8>>>;
pub fn memory(size: usize) -> Memory { Rc::new(RefCell::new(vec![0; size])) }

#[derive(Clone, Copy, Debug)]
pub enum Usage {
    Display, Packed, Binary, Index,
    /// Signed DISPLAY with a SIGN clause: overpunched first digit, or a
    /// separate '+'/'-' byte before or after the digits.
    SignLeading, SignLeadingSeparate, SignTrailingSeparate,
}
impl Usage {
    pub fn is_display(self) -> bool {
        matches!(self, Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate)
    }
}

/// The digits of DISPLAY storage and its sign, as cob_real_get_sign reads
/// them: an overpunch 'p'..'y' on the sign digit, or a separate byte where
/// only '-' is negative. Unsigned items have no sign position.
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
        self.memory.borrow()[self.offset..self.offset + self.size].to_vec()
    }
    fn number(&self) -> Result<Value, &'static str> {
        let (digits, scale, signed, usage) = match self.kind {
            Kind::Numeric { digits, scale, signed, usage } => (digits, scale, signed, usage),
            _ => return Err("numeric view required"),
        };
        let bytes = self.raw();
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
            // An index is a native int: little endian on x86-64.
            Usage::Index => BigInt::from_signed_bytes_le(&bytes),
            Usage::Binary => {
                if signed { BigInt::from_signed_bytes_be(&bytes) }
                else { BigInt::from_bytes_be(Sign::Plus, &bytes) }
            },
        };
        Ok(Value::Num(Number::scaled(coefficient, scale), Some((digits, scale, signed, matches!(usage, Usage::SignTrailingSeparate)))))
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
        if comparison && (scale < 0 || scale as u32 > digits) { fail("alphanumeric comparison of a P-scaled item not modelled"); }
        if !comparison && scale > 0 { fail("numeric MOVE to alphanumeric requires an integer source"); }
        if scale < 0 && !usage.is_display() { fail("P-scaled binary or packed MOVE to alphanumeric not modelled"); }
        let bytes = match usage {
            Usage::Display | Usage::SignLeading | Usage::SignLeadingSeparate | Usage::SignTrailingSeparate => {
                let mut bytes = self.raw();
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
                bytes.extend(std::iter::repeat(b'0').take((-scale).max(0) as usize));
                bytes
            },
            Usage::Packed | Usage::Binary | Usage::Index => {
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
        if raw_group {
            // Group category wins over the receiver's elementary category.
            // Copy storage bytes and spaces, without numeric interpretation.
            let mut result = bytes;
            result.resize(self.size, b' ');
            result.truncate(self.size);
            self.memory.borrow_mut()[self.offset..self.offset + self.size].copy_from_slice(&result);
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
                self.memory.borrow_mut()[self.offset..self.offset + self.size].copy_from_slice(&result);
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
        self.memory.borrow_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
    }
    /// Numeric MOVE: excess decimals are truncated, the magnitude is reduced
    /// modulo the PICTURE capacity (binary included) without SIZE ERROR, and an
    /// unsigned receiver drops the sign. A signed DISPLAY or packed receiver
    /// keeps a negative zero, as GnuCOBOL does for -1000 TO S999.
    pub fn move_number(&mut self, source: &Value) {
        self.resolved();
        let (digits, scale, signed, usage) = match self.kind {
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
        if let Kind::Numeric { digits, scale, usage: Usage::Packed, .. } = self.kind {
            let units = source.num().units(scale, false);
            let fits = units >= BigInt::from(i32::MIN) && units <= BigInt::from(i32::MAX);
            if fits && digits % 2 == 0 && (absolute(&units) / power(digits)) % BigInt::from(10) != BigInt::from(0) {
                fail("binary MOVE would fill the packed pad nibble; native semantics not modelled");
            }
        }
        self.move_number(source)
    }
    fn mark_negative_zero(&mut self) {
        let (usage, signed) = match self.kind { Kind::Numeric { usage, signed, .. } => (usage, signed), _ => return };
        let mut bytes = match usage {
            Usage::Packed => { let mut raw = self.raw(); let last = raw.last_mut().unwrap(); *last = (*last & 0xf0) | 0x0d; raw },
            Usage::Binary | Usage::Index => return,
            _ => display_bytes(display_digits(&self.raw(), usage, signed).0, true, usage, signed),
        };
        self.memory.borrow_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
    }
    pub fn assign(&mut self, source: &Value, rounded: bool) {
        self.resolved();
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
            Kind::Numeric { digits, scale, signed, usage } => {
                let mut units = source.num().units(scale, rounded);
                // An unsigned receiver stores the absolute value (cob_decimal_get_field).
                if !signed && !matches!(usage, Usage::Index) { units = absolute(&units); }
                if matches!(usage, Usage::Index) {
                    if units < BigInt::from(i32::MIN) || units > BigInt::from(i32::MAX) { fail("native index capacity exceeded"); }
                } else if absolute(&units) >= power(digits) {
                    fail("destination PICTURE overflow without SIZE ERROR; native truncation not modelled");
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
                }
            },
        };
        self.memory.borrow_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
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
                self.memory.borrow_mut()[self.offset..self.offset + self.size].swap_with_slice(&mut bytes);
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
        let mut units = source.num().units(scale, rounded);
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
                                      kind: initializer.kind, dimensions: vec![], initializers: vec![] };
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
pub fn rebind(argument: &Value, delta: usize, item: &Value) -> Value {
    let (source, template) = match (argument, item) {
        (Value::View(source), Value::View(template)) => (source, template),
        _ => crate::runtime::fail("CALL argument and LINKAGE item require storage"),
    };
    let offset = source.offset + delta;
    let extent = template.dimensions.iter().map(|(stride, count)| stride * count.saturating_sub(1)).sum::<usize>() + template.size;
    // GnuCOBOL passes only an address: a LINKAGE item longer than its
    // argument would address the caller's neighbouring storage.
    if delta + extent > source.size {
        crate::runtime::fail("LINKAGE item extends beyond the storage of its CALL argument; not modelled");
    }
    Value::View(View { memory: source.memory.clone(), offset, size: template.size, kind: template.kind,
                       dimensions: template.dimensions.clone(), initializers: template.initializers.clone() })
}

/// BY CONTENT: the called program receives a copy of the argument's bytes.
pub fn content_copy(argument: &Value) -> Value {
    match argument {
        Value::View(source) => {
            let bytes = source.memory.borrow()[source.offset..source.offset + source.size].to_vec();
            Value::View(View { memory: Rc::new(RefCell::new(bytes)), offset: 0, size: source.size, kind: source.kind,
                               dimensions: vec![], initializers: source.initializers.clone() })
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
        let view = match target { Value::View(view) => view, _ => fail("INSPECT requires a data item") };
        view.resolved();
        let mut sign = None;
        if let Kind::Numeric { signed: true, usage, .. } = view.kind {
            match usage {
                Usage::Display | Usage::SignLeading => {
                    let position = view.offset + if matches!(usage, Usage::SignLeading) { 0 } else { view.size - 1 };
                    let mut memory = view.memory.borrow_mut();
                    let byte = memory[position];
                    let value = if byte.is_ascii_digit() || byte == b' ' { 1 }
                        else if (b'p'..=b'y').contains(&byte) { memory[position] = byte & !0x40; -1 }
                        else { memory[position] = b'0'; 1 };
                    sign = Some((position, value));
                },
                Usage::SignLeadingSeparate | Usage::SignTrailingSeparate => {},
                _ => fail("INSPECT of a binary or packed item not modelled"),
            }
        } else if let Kind::Numeric { usage: Usage::Packed | Usage::Binary | Usage::Index, .. } = view.kind {
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
    fn data(&self) -> Vec<u8> { self.memory.borrow()[self.offset..self.offset + self.size].to_vec() }
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
            if !to.all { return; } // EC-RANGE-INSPECT-SIZE, not checked
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
        if let Some((position, -1)) = self.sign { self.memory.borrow_mut()[position] |= 0x40; }
    }
    /// cob_inspect_converting; it restores the sign itself, unless it returns early.
    pub fn convert(&mut self, from: &Operand, to: &Operand) {
        let len = self.end - self.start;
        if len == 0 { return; }
        let f2: Vec<u8> = if from.data.len() != to.data.len() {
            if !to.all { return; } // EC-RANGE-INSPECT-SIZE
            to.data.iter().cycle().take(from.data.len()).copied().collect()
        } else { to.data.clone() };
        let mut table = [None; 256];
        for (&a, &b) in from.data.iter().zip(&f2) { if table[a as usize].is_none() { table[a as usize] = Some(b); } }
        {
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
        let mut s = StringInto { memory: view.memory.clone(), offset: view.offset, size: view.size, position: 0, overflow: false, delimiter: None };
        if let Some(p) = pointer {
            if p < i32::MIN as i128 || p > i32::MAX as i128 { fail("STRING POINTER outside the C int range"); }
            s.position = p as i64 - 1;
            if s.position < 0 || s.position >= s.size as i64 { s.overflow = true; }
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
        let mut memory = self.memory.borrow_mut();
        let start = self.offset + self.position as usize;
        if size as i64 <= room {
            memory[start..start + size].copy_from_slice(&data[..size]);
            self.position += size as i64;
        } else {
            memory[start..start + room as usize].copy_from_slice(&data[..room as usize]);
            self.position += room;
            self.overflow = true;
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
        let mut u = Unstring { source: source.clone(), position: 0, count: 0, exception: false, delimiters: vec![] };
        if let Some(p) = pointer {
            if p < i32::MIN as i128 || p > i32::MAX as i128 { fail("UNSTRING POINTER outside the C int range"); }
            u.position = p as i64 - 1;
            if u.position < 0 || u.position >= u.data().len() as i64 { u.exception = true; }
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
        let overflow = self.exception || self.position < self.data().len() as i64;
        (overflow, overflow || size_exception, self.position + 1)
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
            view.memory.borrow_mut()[view.offset..view.offset + view.size].iter_mut().for_each(|b| *b = b' ');
        },
        _ => fail("DELIMITER IN requires a data item"),
    }
}
