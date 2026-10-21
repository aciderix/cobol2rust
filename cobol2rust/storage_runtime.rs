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
pub enum Kind { Text, Numeric { digits: u32, scale: u32, signed: bool, usage: Usage } }
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
            Kind::Text => Value::Bytes(self.raw()),
            _ => self.number().unwrap_or_else(|error| fail(error)),
        }
    }
    pub fn is_numeric(&self) -> bool {
        match self.kind { Kind::Text => self.raw().iter().all(u8::is_ascii_digit), _ => self.number().is_ok() }
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
            item.assign(source, false);
        });
    }
}
