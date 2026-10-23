// Shared COBOL storage. Views preserve group/element/REDEFINES aliasing.
use std::cell::RefCell;
use std::rc::Rc;
use num_bigint::{BigInt, Sign};
use crate::runtime::{Value, Number, SizeError, fail, absolute, power};

pub type Memory = Rc<RefCell<Vec<u8>>>;
pub fn memory(size: usize) -> Memory { Rc::new(RefCell::new(vec![0; size])) }

#[derive(Clone, Copy, Debug)]
pub enum Usage { Display, Packed, Binary, Index }
#[derive(Clone, Copy, Debug)]
pub enum Kind {
    Text,
    Numeric { digits: u32, scale: u32, signed: bool, usage: Usage },
    Edited { picture: &'static str, digits: u32, scale: u32 },
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
        let mut bytes = self.raw();
        let coefficient = match usage {
            Usage::Display => {
                let last = bytes.last_mut().ok_or("empty numeric field")?;
                let negative = signed && (b'p'..=b'y').contains(last);
                if negative { *last = b'0' + (*last - b'p'); }
                if !bytes.iter().all(u8::is_ascii_digit) { return Err("invalid DISPLAY numeric data"); }
                let n = BigInt::parse_bytes(&bytes, 10).ok_or("invalid DISPLAY data")?;
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
            Usage::Binary | Usage::Index => {
                if signed { BigInt::from_signed_bytes_be(&bytes) }
                else { BigInt::from_bytes_be(Sign::Plus, &bytes) }
            },
        };
        Ok(Value::Num(Number::new(coefficient, scale), Some((digits, scale, signed))))
    }
    pub fn value(&self) -> Value {
        match self.kind {
            Kind::Text | Kind::Edited { .. } => Value::Bytes(self.raw()),
            _ => self.number().unwrap_or_else(|error| fail(error)),
        }
    }
    pub fn is_numeric(&self) -> bool {
        match self.kind {
            Kind::Text | Kind::Edited { .. } => self.raw().iter().all(u8::is_ascii_digit),
            _ => self.number().is_ok(),
        }
    }
    pub fn numeric_move_text(&self, group: bool) -> Value {
        self.resolved();
        if group {
            // A group receiver requests storage bytes, including a DISPLAY
            // overpunch or the original COMP/COMP-3 representation.
            match self.kind {
                Kind::Numeric { usage: Usage::Index, .. } => fail("MOVE of an index to a group requires native index storage"),
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
        if !comparison && scale != 0 { fail("numeric MOVE to alphanumeric requires an integer source"); }
        let bytes = match usage {
            Usage::Display => {
                let mut bytes = self.raw();
                if signed {
                    // GnuCOBOL normalizes some malformed sign encodings and
                    // can mutate the sender. Keep those cases outside this
                    // profile rather than silently changing their behavior.
                    if self.number().is_err() { fail("invalid signed DISPLAY numeric MOVE"); }
                    if let Some(last) = bytes.last_mut() {
                        if (b'p'..=b'y').contains(last) { *last = b'0' + (*last - b'p'); }
                    }
                }
                // An unsigned DISPLAY sender is copied as bytes even when
                // its storage is not valid numeric data.
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
        if let Kind::Numeric { digits, scale, signed, usage: Usage::Display } = self.kind {
            let (mut result, negative, _) = text_move_digits(&bytes, digits as usize, scale as usize);
            if signed && negative {
                let last = result.last_mut().unwrap();
                *last = b'p' + (*last - b'0');
            }
            if result.len() != self.size { fail("unsupported DISPLAY storage for text MOVE"); }
            self.memory.borrow_mut()[self.offset..self.offset + self.size].copy_from_slice(&result);
            return;
        }
        // Other numeric usages and edited receivers pass through a signed
        // DISPLAY buffer of 76 positions and 38 fractional positions.
        let (result, source_negative, valid) = text_move_digits(&bytes, 76, 38);
        let coefficient = BigInt::parse_bytes(&result, 10).unwrap();
        let negative = source_negative && valid;
        let number = Number::new(if negative { -coefficient } else { coefficient }, 38);
        match self.kind {
            Kind::Edited { .. } => self.assign(&Value::Num(number, None), false),
            Kind::Numeric { digits, scale, signed, usage } => {
                let magnitude = absolute(&number.units(scale, false)) % power(digits);
                let units = if signed && negative { -magnitude } else { magnitude };
                self.assign(&Value::Num(Number::new(units, scale), None), false);
                // BigInt has no negative zero, but a signed packed MOVE keeps
                // its D nibble even when scaling or truncation leaves zero.
                if signed && negative && matches!(usage, Usage::Packed) {
                    self.mark_negative_zero();
                }
            },
            _ => fail("text MOVE requires a numeric or edited receiver"),
        }
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
        self.assign(&Value::Num(Number::new(if negative { -magnitude } else { magnitude }, scale), None), false);
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
        let usage = match self.kind { Kind::Numeric { usage, .. } => usage, _ => return };
        let mut memory = self.memory.borrow_mut();
        let last = &mut memory[self.offset + self.size - 1];
        match usage {
            Usage::Display => *last = b'p' + (*last - b'0'),
            Usage::Packed => *last = (*last & 0xf0) | 0x0d,
            Usage::Binary | Usage::Index => {},
        }
    }
    pub fn assign(&mut self, source: &Value, rounded: bool) {
        self.resolved();
        let mut bytes = match self.kind {
            Kind::Text => {
                if !source.is_text() { fail("numeric/text MOVE unsupported"); }
                let mut bytes = source.bytes();
                bytes.resize(self.size, b' ');
                bytes.truncate(self.size);
                bytes
            },
            Kind::Edited { picture, digits, scale } => {
                if source.is_text() { fail("numeric-edited assignment requires a numeric source; de-editing is unsupported"); }
                let units = source.num().units(scale, rounded);
                // Determine the sign after scaling, before discarding excess high digits.
                let negative = units.sign() == Sign::Minus;
                let coefficient = absolute(&units) % power(digits);
                let ascii = format!("{:0>width$}", coefficient.to_string(), width = digits as usize);
                let mut positions = ascii.bytes();
                let mut suppress = true;
                let mut bytes = Vec::with_capacity(self.size);
                for symbol in picture.bytes() {
                    bytes.push(match symbol {
                        b'+' => if negative { b'-' } else { b'+' },
                        b'-' => if negative { b'-' } else { b' ' },
                        b'.' => b'.',
                        b'9' | b'Z' => {
                            let digit = positions.next().unwrap_or_else(|| fail("invalid numeric-edited picture capacity"));
                            if symbol == b'Z' && suppress && digit == b'0' { b' ' }
                            else { suppress = false; digit }
                        },
                        _ => fail("unsupported numeric-edited picture symbol"),
                    });
                }
                if bytes.len() != self.size || positions.next().is_some() {
                    fail("invalid numeric-edited picture layout");
                }
                bytes
            },
            Kind::Numeric { digits, scale, signed, usage } => {
                let units = source.num().units(scale, rounded);
                if matches!(usage, Usage::Index) {
                    if units < BigInt::from(i32::MIN) || units > BigInt::from(i32::MAX) { fail("native index capacity exceeded"); }
                } else if absolute(&units) >= power(digits) || (!signed && units.sign() == Sign::Minus) {
                    fail("destination PICTURE overflow or negative unsigned value");
                }
                let negative = units.sign() == Sign::Minus;
                let ascii = format!("{:0>width$}", absolute(&units).to_string(), width = digits as usize).into_bytes();
                match usage {
                    Usage::Display => {
                        let mut bytes = ascii;
                        if negative { let last = bytes.last_mut().unwrap(); *last = b'p' + (*last - b'0'); }
                        bytes
                    },
                    Usage::Packed => {
                        let mut nibbles: Vec<u8> = ascii.iter().map(|b| b - b'0').collect();
                        nibbles.push(if !signed { 15 } else if negative { 13 } else { 12 });
                        if nibbles.len() % 2 != 0 { nibbles.insert(0, 0); }
                        nibbles.chunks_exact(2).map(|n| (n[0] << 4) | n[1]).collect()
                    },
                    Usage::Binary | Usage::Index => {
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
    pub fn checked_assign(&mut self, source: &Value, rounded: bool) -> Result<(), SizeError> {
        self.resolved();
        let (digits, scale, signed, usage) = match self.kind {
            Kind::Numeric { digits, scale, signed, usage } => (digits, scale, signed, usage),
            _ => fail("checked arithmetic destination requires numeric storage"),
        };
        let mut units = source.num().units(scale, rounded);
        if !matches!(usage, Usage::Index) && absolute(&units) >= power(digits) { return Err(SizeError); }
        // COBOL discards the sign for an unsigned receiver. This is not SIZE ERROR.
        if !signed { units = absolute(&units); }
        self.assign(&Value::Num(Number::new(units, scale), None), false);
        Ok(())
    }
    pub fn initialize(&mut self, with_filler: bool) {
        self.resolved();
        for initializer in &self.initializers {
            if initializer.filler && !with_filler { continue; }
            offsets(&initializer.dimensions, self.offset + initializer.offset, &mut |offset| {
                let mut leaf = Self { memory: self.memory.clone(), offset, size: initializer.size,
                                      kind: initializer.kind, dimensions: vec![], initializers: vec![] };
                let value = match initializer.kind { Kind::Text => Value::text(""), _ => Value::number("0") };
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
            if matches!(item.kind, Kind::Edited { .. }) && source.is_text() {
                item.kind = Kind::Text;
            }
            item.assign(source, false);
        });
    }
}
