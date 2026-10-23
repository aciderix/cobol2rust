// Decimal integer coefficients with GnuCOBOL 3.2's 38-digit division shift.
// No floating point. num-bigint is statically linked into the Rust executable.
use num_bigint::{BigInt, Sign};
use std::io::{self, Write};
use std::sync::atomic::{AtomicUsize, Ordering};

static COBOL_LINE: AtomicUsize = AtomicUsize::new(0);
pub fn set_line(line: usize) { COBOL_LINE.store(line, Ordering::Relaxed); }

#[derive(Clone, Debug)]
pub struct Number { pub(crate) n: BigInt, pub(crate) scale: u32 }

#[derive(Clone, Copy, Debug)]
pub struct SizeError;

/// How a called program ends: GOBACK/EXIT PROGRAM return to the caller,
/// STOP RUN ends the whole run unit.
#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Outcome { Return, Stop }

/// cob_add_int on a receiver with trailing P positions: the int operand is
/// first truncated to whole units of 10^positions, and a zero result leaves
/// the receiver unstored. cob_sub_int adds the negated operand.
pub fn cob_add_int_operand(operand: &Value, positions: u32, negate: bool) -> Option<Value> {
    let n = operand.integer("ADD/SUBTRACT operand");
    if n < i32::MIN as i128 || n > i32::MAX as i128 { fail("cob_add_int operand outside the C int range"); }
    let mut units = if positions < 10 { n / 10i128.pow(positions) } else { 0 };
    if negate { units = -units; }
    if units == 0 { return None; }
    Some(Value::Num(Number::new(BigInt::from(units) * power(positions), 0), None))
}

/// GnuCOBOL resolves a CALL name to a loaded or loadable module, a libcob
/// system routine or any symbol of the process. Only a plain upper-case COBOL
/// word that names no program of the call path is surely not found.
pub fn surely_absent(name: &str, present: &[&str]) -> bool {
    !name.is_empty() && name.bytes().all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'-')
        && name != "SYSTEM" && name != "EXTFH" && !present.contains(&name)
}

pub fn fail(message: &str) -> ! {
    eprintln!("cobol2rust: COBOL line {}: {}", COBOL_LINE.load(Ordering::Relaxed), message);
    std::process::exit(70)
}
pub(crate) fn power(scale: u32) -> BigInt {
    if scale > 1024 { fail("intermediate decimal scale exceeds 1024"); }
    BigInt::from(10u8).pow(scale)
}
pub(crate) fn absolute(n: &BigInt) -> BigInt {
    if n.sign() == Sign::Minus { -n } else { n.clone() }
}
impl Number {
    pub(crate) fn new(n: BigInt, scale: u32) -> Self {
        if scale > 1024 || n.to_str_radix(10).len() > 4096 { fail("intermediate decimal capacity exceeded"); }
        Self { n, scale }
    }
    /// A stored coefficient at a signed PICTURE scale.
    pub(crate) fn scaled(n: BigInt, scale: i32) -> Self {
        if scale >= 0 { Self::new(n, scale as u32) } else { Self::new(n * power((-scale) as u32), 0) }
    }
    fn parse(text: &str) -> Self {
        let s = text.trim();
        let unsigned = s.strip_prefix('-').or_else(|| s.strip_prefix('+')).unwrap_or(s);
        let pieces: Vec<_> = unsigned.split('.').collect();
        if pieces.len() > 2 || pieces[0].is_empty() || pieces.iter().any(|x| x.is_empty() || !x.bytes().all(|c| c.is_ascii_digit())) {
            fail("invalid numeric input");
        }
        let scale = if pieces.len() == 2 { pieces[1].len() as u32 } else { 0 };
        if unsigned.len() > 4096 { fail("numeric input overflow"); }
        let n = BigInt::parse_bytes(pieces.concat().as_bytes(), 10).unwrap_or_else(|| fail("invalid numeric input"));
        Self::new(if s.starts_with('-') { -n } else { n }, scale)
    }
    fn plus(self, other: Self) -> Self {
        let scale = self.scale.max(other.scale);
        Self::new(self.n * power(scale - self.scale) + other.n * power(scale - other.scale), scale)
    }
    fn neg(self) -> Self {
        Self::new(-self.n, self.scale)
    }
    fn times(self, other: Self) -> Self {
        Self::new(self.n * other.n, self.scale + other.scale)
    }
    fn divide(self, other: Self) -> Self {
        if other.n == BigInt::from(0) { fail("division by zero"); }
        if self.n == BigInt::from(0) { return Self::new(BigInt::from(0), 0); }
        let shift = 38 + other.scale.saturating_sub(self.scale);
        let scale = 38 + self.scale.saturating_sub(other.scale);
        Self::new((self.n * power(shift)) / other.n, scale)
    }
    /// The value at a PICTURE scale, as libcob's scale: negative for
    /// trailing P positions (units of 10^-scale), above the digit count for
    /// leading P positions. Excess digits are truncated or ROUNDED.
    pub(crate) fn units(&self, scale: i32, rounded: bool) -> BigInt {
        let own = self.scale as i32;
        if scale >= own { return &self.n * power((scale - own) as u32); }
        let divisor = power((own - scale) as u32);
        let q = &self.n / &divisor;
        let r = &self.n % &divisor;
        if rounded && absolute(&r) * 2 >= divisor {
            q + if self.n.sign() == Sign::Minus { -1 } else { 1 }
        } else { q }
    }
}

#[derive(Clone, Debug)]
pub enum Value {
    Num(Number, Option<(u32, i32, bool)>),
    Text(String),
    Bytes(Vec<u8>),
    View(crate::storage_runtime::View),
}

impl Value {
    pub fn is_text(&self) -> bool {
        match self { Self::View(view) => matches!(view.kind, crate::storage_runtime::Kind::Text | crate::storage_runtime::Kind::Justified | crate::storage_runtime::Kind::Edited { .. } | crate::storage_runtime::Kind::AlnumEdited { .. }), Self::Text(_) | Self::Bytes(_) => true, _ => false }
    }
    pub fn snapshot(&self) -> Self { match self { Self::View(view) => view.value(), _ => self.clone() } }
    pub fn at(&self, indices: &[Value]) -> Self {
        match self { Self::View(view) => Self::View(view.at(indices)), _ => fail("subscript requires storage view") }
    }
    pub fn active_count(&self, dimension: usize, controller: &Value, minimum: usize, maximum: usize) -> Self {
        let count = controller.occurrences(minimum, maximum);
        match self {
            Self::View(view) => { let mut view = view.clone(); view.dimensions[dimension].1 = count; Self::View(view) },
            _ => fail("OCCURS DEPENDING ON requires storage view"),
        }
    }
    pub fn active_size(&self, controller: &Value, minimum: usize, maximum: usize, prefix: usize, stride: usize) -> Self {
        let count = controller.occurrences(minimum, maximum);
        match self {
            Self::View(view) => { let mut view = view.clone(); view.size = prefix + stride * count; Self::View(view) },
            _ => fail("OCCURS DEPENDING ON requires group view"),
        }
    }
    fn occurrences(&self, minimum: usize, maximum: usize) -> usize {
        let count = self.integer("OCCURS DEPENDING ON");
        if count < minimum as i128 || count > maximum as i128 { fail("OCCURS DEPENDING ON count out of bounds"); }
        count as usize
    }
    pub fn slice(&self, start: &Value, length: Option<&Value>) -> Self {
        match self { Self::View(view) => Self::View(view.slice(start, length)), _ => fail("reference modification requires storage view") }
    }
    pub fn bytes(&self) -> Vec<u8> {
        match self { Self::View(view) => view.value().bytes(), Self::Bytes(b) => b.clone(), _ => self.show().into_bytes() }
    }
    pub fn numeric_move_text(&self, group: bool) -> Self {
        match self {
            Self::View(view) => view.numeric_move_text(group),
            _ => fail("numeric MOVE to text requires a source storage view"),
        }
    }
    pub fn comparison_text(&self) -> Self {
        match self {
            Self::View(view) => view.comparison_text(),
            _ => fail("mixed comparison requires a numeric storage view"),
        }
    }
    pub fn compare_zero(&self) -> std::cmp::Ordering {
        if !self.is_text() { fail("figurative ZERO comparison requires text"); }
        let bytes = self.bytes();
        bytes.cmp(&vec![b'0'; bytes.len()])
    }
    pub fn assign_text_move(&mut self, source: &Self, raw_group: bool) {
        match self {
            Self::View(view) => view.assign_text_move(source, raw_group),
            _ => fail("text MOVE requires a storage destination"),
        }
    }
    pub fn is_numeric(&self) -> bool {
        match self { Self::View(view) => view.is_numeric(), Self::Num(..) => true, _ => self.bytes().iter().all(u8::is_ascii_digit) }
    }
    pub fn declare(&mut self, source: &Self) {
        match self { Self::View(view) => view.declare(source), _ => self.assign(source, false) }
    }
    pub fn text_size(&self) -> usize {
        match self { Self::Text(s) => s.len(), Self::Bytes(b) => b.len(), Self::View(view) if self.is_text() => { view.resolved(); view.size }, _ => fail("text record required") }
    }
    pub fn number(text: &str) -> Self { Self::Num(Number::parse(text), None) }
    pub fn text(text: &str) -> Self {
        if !text.is_ascii() { fail("only ASCII text is supported"); }
        Self::Text(text.to_string())
    }
    pub fn numeric_field(digits: u32, scale: i32, signed: bool, initial: &str) -> Self {
        let mut result = Self::Num(Number::scaled(BigInt::from(0), scale), Some((digits, scale, signed)));
        result.assign(&Self::number(initial), false);
        result
    }
    pub fn text_field(size: usize, initial: &str) -> Self {
        let mut result = Self::Text(" ".repeat(size));
        result.assign(&Self::text(initial), false);
        result
    }
    pub(crate) fn num(&self) -> Number {
        match self { Self::Num(n, _) => n.clone(), Self::View(view) => view.value().num(), _ => fail("numeric operation on text") }
    }
    pub fn plus(&self, b: &Self) -> Self { Self::Num(self.num().plus(b.num()), None) }
    pub fn minus(&self, b: &Self) -> Self { Self::Num(self.num().plus(b.num().neg()), None) }
    pub fn times(&self, b: &Self) -> Self { Self::Num(self.num().times(b.num()), None) }
    pub fn divide(&self, b: &Self) -> Self { Self::Num(self.num().divide(b.num()), None) }
    pub fn checked_divide(&self, b: &Self) -> Result<Self, SizeError> {
        let left = self.num(); let right = b.num();
        if right.n == BigInt::from(0) { return Err(SizeError); }
        Ok(Self::Num(left.divide(right), None))
    }
    pub fn neg(&self) -> Self { Self::Num(self.num().neg(), None) }
    pub fn checked_assign(&mut self, source: &Self, rounded: bool) -> Result<(), SizeError> {
        match self {
            Self::View(view) => view.checked_assign(source, rounded),
            _ => fail("checked arithmetic destination requires numeric storage"),
        }
    }
    pub fn move_number(&mut self, source: &Self) {
        match self {
            Self::View(view) => view.move_number(source),
            _ => self.assign(source, false),
        }
    }
    pub fn move_edited(&mut self, source: &Self) {
        match self {
            Self::View(view) => view.move_edited(source),
            _ => fail("numeric-edited MOVE requires storage"),
        }
    }
    pub fn move_binary_to_packed(&mut self, source: &Self) {
        match self {
            Self::View(view) => view.move_binary_to_packed(source),
            _ => self.move_number(source),
        }
    }
    pub fn assign(&mut self, source: &Self, rounded: bool) {
        match self {
            Self::View(view) => view.assign(source, rounded),
            Self::Num(n, Some((digits, scale, signed))) => {
                let units = source.num().units(*scale, rounded);
                if absolute(&units) >= power(*digits) || (!*signed && units.sign() == Sign::Minus) {
                    fail("destination PICTURE overflow or negative unsigned value");
                }
                *n = Number::scaled(units, *scale);
            },
            Self::Text(current) => {
                let source = match source { Self::Text(s) => s, _ => fail("numeric/text MOVE unsupported") };
                let size = current.len();
                *current = source.chars().take(size).collect();
                current.push_str(&" ".repeat(size - current.len()));
            },
            _ => fail("assignment destination is not a field"),
        }
    }
    pub fn initialize(&mut self) {
        self.initialize_with_filler(false);
    }
    pub fn initialize_with_filler(&mut self, with_filler: bool) {
        match self {
            Self::View(view) => view.initialize(with_filler),
            Self::Num(n, _) => n.n = BigInt::from(0),
            Self::Text(s) => *s = " ".repeat(s.len()),
            Self::Bytes(b) => b.fill(b' '),
        }
    }
    pub fn compare(&self, other: &Self) -> std::cmp::Ordering {
        if matches!(self, Self::View(_)) || matches!(other, Self::View(_)) { return self.snapshot().compare(&other.snapshot()); }
        if self.is_text() && other.is_text() {
            let mut a = self.bytes(); let mut b = other.bytes();
            let size = a.len().max(b.len()); a.resize(size, b' '); b.resize(size, b' ');
            return a.cmp(&b);
        }
        match (self, other) {
            (Self::Num(a, _), Self::Num(b, _)) => {
                let scale = a.scale.max(b.scale);
                (&a.n * power(scale - a.scale)).cmp(&(&b.n * power(scale - b.scale)))
            },
            (Self::Text(a), Self::Text(b)) => {
                let len = a.len().max(b.len());
                format!("{a:<len$}").cmp(&format!("{b:<len$}"))
            },
            _ => fail("mixed numeric/text comparison unsupported"),
        }
    }
    pub fn count(&self) -> i128 {
        let result = self.integer("PERFORM TIMES");
        if result < 0 { fail("PERFORM TIMES requires a nonnegative integer"); }
        result
    }
    pub fn integer(&self, context: &str) -> i128 {
        let n = self.num();
        if &n.n % power(n.scale) != BigInt::from(0) {
            fail(&format!("integer required for {context}"));
        }
        n.units(0, false).to_string().parse::<i128>().unwrap_or_else(|_| fail("integer overflow"))
    }
    pub fn show(&self) -> String {
        match self {
            Self::View(view) => view.value().show(),
            Self::Bytes(b) => String::from_utf8(b.clone()).unwrap_or_else(|_| fail("binary group requires raw byte output")),
            Self::Text(s) => s.clone(),
            Self::Num(n, Some((digits, scale, signed))) => {
                // pretty_display_numeric: trailing P positions print as zero
                // digits; leading ones widen the fraction (PIC PP9 -> .ddd).
                let (units, width) = if *scale < 0 { (n.units(0, false), (*digits as i32 - *scale) as usize) }
                                     else { (n.units(*scale, false), (*digits).max(*scale as u32) as usize) };
                let mut s = format!("{:0>width$}", absolute(&units).to_string(), width = width);
                if *scale > 0 { s.insert(s.len() - *scale as usize, '.'); }
                if *signed { s.insert(0, if units.sign() == Sign::Minus { '-' } else { '+' }); }
                s
            },
            Self::Num(n, None) => {
                let scale = n.scale;
                let units = n.units(scale as i32, false);
                let mut s = format!("{:0>width$}", absolute(&units).to_string(), width = scale as usize + 1);
                if scale > 0 { s.insert(s.len() - scale as usize, '.'); }
                if units.sign() == Sign::Minus { s.insert(0, '-'); }
                s
            }
        }
    }
    pub fn accept(&mut self) {
        let mut line = String::new();
        io::stdin().read_line(&mut line).unwrap_or_else(|_| fail("stdin read failed"));
        let line = line.trim_end_matches(['\r', '\n']);
        let value = if self.is_text() { Self::text(line) } else { Self::number(line) };
        self.assign(&value, false);
    }
}
pub fn display(values: &[Value], newline: bool) {
    let mut out = io::stdout().lock();
    for v in values { out.write_all(&v.bytes()).unwrap_or_else(|_| fail("stdout write failed")); }
    if newline {
        let ending = if cfg!(windows) { "\r\n" } else { "\n" };
        write!(out, "{ending}").unwrap_or_else(|_| fail("stdout write failed"));
    }
    out.flush().unwrap_or_else(|_| fail("stdout flush failed"));
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_decimal_and_rounding() {
        let a = Value::number("0.1").plus(&Value::number("0.2"));
        assert_eq!(a.compare(&Value::number("0.3")), std::cmp::Ordering::Equal);
        let mut field = Value::numeric_field(5, 2, true, "0");
        field.assign(&Value::number("-1.235"), true);
        assert_eq!(field.show(), "-001.24");
        field.assign(&Value::number("-1.239"), false);
        assert_eq!(field.show(), "-001.23");
        field.assign(&Value::number("1").divide(&Value::number("3")), true);
        assert_eq!(field.show(), "+000.33");
    }
    #[test]
    fn alpha_padding_and_comparison() {
        let mut field = Value::text_field(4, "AB");
        assert_eq!(field.show(), "AB  ");
        assert_eq!(field.compare(&Value::text("AB")), std::cmp::Ordering::Equal);
        field.assign(&Value::text("123456"), false);
        assert_eq!(field.show(), "1234");
    }
    #[test]
    fn intermediate_division_retains_truncation() {
        let value = Value::number("1").divide(&Value::number("3")).times(&Value::number("3"));
        let mut field = Value::numeric_field(7, 6, false, "0");
        field.assign(&value, false);
        assert_eq!(field.show(), "0.999999");
        field.assign(&value, true);
        assert_eq!(field.show(), "1.000000");
    }
}
