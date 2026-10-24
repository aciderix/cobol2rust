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
    /// cob_trim_decimal: drop trailing fractional zeros.
    fn trimmed(mut self) -> Self {
        if self.n == BigInt::from(0) { self.scale = 0; return self; }
        while self.scale > 0 && (&self.n % 10u8) == BigInt::from(0) {
            self.n /= 10u8;
            self.scale -= 1;
        }
        self
    }
    /// cob_decimal_pow for integer exponents; a fractional exponent goes
    /// through GMP floating point in libcob and is not modelled.
    fn power(self, exponent: Self) -> Self {
        if exponent.n == BigInt::from(0) {
            if self.n == BigInt::from(0) { fail("0 ** 0 raises EC-SIZE-EXPONENTIATION; not modelled"); }
            return Self::new(BigInt::from(1), 0);
        }
        if self.n == BigInt::from(0) { return Self::new(BigInt::from(0), 0); }
        let exponent = exponent.trimmed();
        if exponent.scale != 0 { fail("non-integer exponent (floating point in libcob) not modelled"); }
        let base = self.trimmed();
        if exponent.n == BigInt::from(1) { return base; }
        let negative = exponent.n.sign() == Sign::Minus;
        let n: u32 = absolute(&exponent.n).try_into().unwrap_or_else(|_| fail("exponent too large"));
        if (base.n.bits() as u64) * (n as u64) > 16000 || base.scale as u64 * n as u64 > 1024 { fail("intermediate decimal capacity exceeded"); }
        let raised = Self::new(base.n.pow(n), base.scale * n).trimmed();
        if negative { Self::new(BigInt::from(1), 0).divide(raised).trimmed() } else { raised }
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
    /// A number, with the PICTURE of the item it was read from: digits,
    /// scale, signed, and whether DISPLAY shows the sign after the digits.
    Num(Number, Option<(u32, i32, bool, bool)>),
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
        let mut result = Self::Num(Number::scaled(BigInt::from(0), scale), Some((digits, scale, signed, false)));
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
    pub fn power(&self, b: &Self) -> Self { Self::Num(self.num().power(b.num()), None) }
    pub fn checked_divide(&self, b: &Self) -> Result<Self, SizeError> {
        let left = self.num(); let right = b.num();
        if right.n == BigInt::from(0) { return Err(SizeError); }
        Ok(Self::Num(left.divide(right), None))
    }
    pub fn neg(&self) -> Self { Self::Num(self.num().neg(), None) }
    /// cob_div_remainder: the dividend less the divisor times the quotient
    /// truncated to the quotient item's scale (not its stored, rounded value).
    pub fn remainder_after(&self, divisor: &Self, quotient_scale: i32) -> Self {
        let (dividend, divisor) = (self.num(), divisor.num());
        let units = dividend.clone().divide(divisor.clone()).units(quotient_scale, false);
        let product = Number::scaled(units, quotient_scale).times(divisor);
        Self::Num(dividend.plus(product.neg()), None)
    }
    pub fn checked_remainder(&self, divisor: &Self, quotient_scale: i32) -> Result<Self, SizeError> {
        if divisor.num().n == BigInt::from(0) { return Err(SizeError); }
        Ok(self.remainder_after(divisor, quotient_scale))
    }
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
    /// cob_decimal_get_field without COB_STORE_KEEP_ON_OVERFLOW (cob_add_int's opt 0).
    pub fn move_deedited(&mut self, source: &Self) {
        match self { Self::View(view) => view.move_deedited(source), _ => fail("de-editing MOVE requires storage") }
    }
    /// A signed DISPLAY receiver of the literal -0 keeps the minus sign.
    pub fn negative_zero(&mut self) {
        match self { Self::View(view) => view.mark_negative_zero(), _ => fail("negative zero requires storage") }
    }
        pub fn store_truncated(&mut self, source: &Self) -> bool {
        match self {
            Self::View(view) => view.store_truncated(source),
            _ => fail("store requires a storage destination"),
        }
    }
    pub fn assign(&mut self, source: &Self, rounded: bool) {
        match self {
            Self::View(view) => view.assign(source, rounded),
            Self::Num(n, Some((digits, scale, signed, _))) => {
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
    /// cb_build_cast_llint for PERFORM TIMES: cob_get_llint truncates the
    /// fraction; the loop `n > 0` runs a negative count zero times.
    pub fn count(&self) -> i128 {
        let n = self.num();
        let units = &n.n / power(n.scale);
        units.to_string().parse::<i64>().unwrap_or_else(|_| fail("PERFORM TIMES count beyond 64 bits not modelled")) as i128
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
            Self::Num(n, Some((digits, scale, signed, trailing_sign))) => {
                // pretty_display_numeric: trailing P positions print as zero
                // digits; leading ones widen the fraction (PIC PP9 -> .ddd).
                let (units, width) = if *scale < 0 { (n.units(0, false), (*digits as i32 - *scale) as usize) }
                                     else { (n.units(*scale, false), (*digits).max(*scale as u32) as usize) };
                let mut s = format!("{:0>width$}", absolute(&units).to_string(), width = width);
                if *scale > 0 { s.insert(s.len() - *scale as usize, '.'); }
                if *signed {
                    let sign = if units.sign() == Sign::Minus { '-' } else { '+' };
                    if *trailing_sign { s.push(sign); } else { s.insert(0, sign); }
                }
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
    /// cob_accept: a line up to '\n' (a CR is data), one space at end of
    /// input; a DISPLAY numeric receiver keeps only its size of input; then
    /// an alphanumeric MOVE of the line.
    pub fn accept(&mut self) {
        io::stdout().flush().unwrap_or_else(|_| fail("stdout flush failed"));
        let mut line = Vec::new();
        let stdin = io::stdin();
        let mut input = stdin.lock();
        let mut byte = [0u8; 1];
        let mut end = false;
        while line.len() < 8191 {
            match io::Read::read(&mut input, &mut byte) {
                Ok(0) => { end = true; break; },
                Ok(_) if byte[0] == b'\n' => break,
                Ok(_) => line.push(byte[0]),
                Err(_) => fail("stdin read failed"),
            }
        }
        if end && line.is_empty() { line.push(b' '); }
        match self {
            Self::View(view) => match view.kind {
                crate::storage_runtime::Kind::Numeric { usage, .. } => {
                    if usage.is_display() { line.truncate(view.size); }
                    view.assign_text_move(&Self::Bytes(line), false);
                },
                crate::storage_runtime::Kind::Edited { .. } => view.assign_text_move(&Self::Bytes(line), false),
                _ => view.assign(&Self::Bytes(line), false),
            },
            _ => fail("ACCEPT requires a storage receiver"),
        }
    }
}
/// DISPLAY UPON SYSERR.
/// cob_accept (NULL), the ACCEPT of STOP literal: input up to '\n' or end
/// of input is discarded; character 03 raises SIGINT, which is not modelled.
pub fn accept_omitted() {
    io::stdout().flush().unwrap_or_else(|_| fail("stdout flush failed"));
    let stdin = io::stdin();
    let mut input = stdin.lock();
    let mut byte = [0u8; 1];
    loop {
        match io::Read::read(&mut input, &mut byte) {
            Ok(0) => break,
            Ok(_) if byte[0] == b'\n' => break,
            Ok(_) if byte[0] == 3 => fail("ACCEPT of STOP literal read character 03 (SIGINT) not modelled"),
            Ok(_) => {},
            Err(_) => fail("stdin read failed"),
        }
    }
}

pub fn display_error(values: &[Value], newline: bool) {
    let mut out = io::stderr().lock();
    for v in values { out.write_all(&v.bytes()).unwrap_or_else(|_| fail("stderr write failed")); }
    if newline {
        let ending = if cfg!(windows) { "\r\n" } else { "\n" };
        write!(out, "{ending}").unwrap_or_else(|_| fail("stderr write failed"));
    }
}

static SWITCHES: std::sync::Mutex<Option<[bool; 37]>> = std::sync::Mutex::new(None);

fn switches() -> std::sync::MutexGuard<'static, Option<[bool; 37]>> {
    let mut guard = SWITCHES.lock().unwrap();
    if guard.is_none() {
        // cob_init: COB_SWITCH_n set to a value starting with '1' or to ON (any case).
        let mut state = [false; 37];
        for (n, slot) in state.iter_mut().enumerate() {
            if let Ok(value) = std::env::var(format!("COB_SWITCH_{n}")) {
                *slot = value.starts_with('1') || value.eq_ignore_ascii_case("ON");
            }
        }
        *guard = Some(state);
    }
    guard
}
pub fn switch_on(n: usize) -> bool { switches().unwrap()[n] }
pub fn set_switch(n: usize, on: bool) { switches().as_mut().unwrap()[n] = on; }

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

// Intrinsic functions, ported from GnuCOBOL 3.2 libcob/intrinsic.c. Numeric
// results are exact decimals (cob_alloc_field sizes them to fit).
pub mod intrinsic {
    use super::{fail, power, absolute, Number, Value};
    use num_bigint::{BigInt, Sign};

    fn trimmed(n: Number) -> Number { n.trimmed() }
    fn value(n: Number) -> Value { Value::Num(n, None) }
    fn int_of(n: i128) -> Value { Value::Num(Number::new(BigInt::from(n), 0), None) }
    /// cob_get_int: the integer part, which must fit a C int.
    fn get_int(v: &Value) -> i64 {
        let units = v.num().units(0, false);
        let n: i64 = units.to_string().parse().unwrap_or_else(|_| fail("function argument outside the C int range"));
        if n < i32::MIN as i64 || n > i32::MAX as i64 { fail("function argument outside the C int range"); }
        n
    }
    fn argument_error(name: &str) -> ! {
        fail(&format!("FUNCTION {name}: argument outside its domain (EC-ARGUMENT-FUNCTION) not modelled"))
    }
    /// FUNCTION INTEGER: the greatest integer not above the argument.
    pub fn integer(v: &Value) -> Value {
        let n = v.num();
        let divisor = power(n.scale);
        let (q, r) = (&n.n / &divisor, &n.n % &divisor);
        value(Number::new(if n.n.sign() == Sign::Minus && r != BigInt::from(0) { q - 1 } else { q }, 0))
    }
    pub fn integer_part(v: &Value) -> Value {
        let n = v.num();
        value(Number::new(&n.n / power(n.scale), 0))
    }
    /// cob_mod_or_rem: f1 - f2 * INTEGER (MOD) or INTEGER-PART (REM) of f1 / f2.
    pub fn mod_or_rem(f1: &Value, f2: &Value, rem: bool) -> Value {
        if f2.num().n == BigInt::from(0) { argument_error(if rem { "REM" } else { "MOD" }); }
        let quotient = value(f1.num().divide(f2.num()));
        let whole = if rem { integer_part(&quotient) } else { integer(&quotient) };
        value(f1.num().plus(whole.num().times(f2.num()).neg()))
    }
    pub fn factorial(v: &Value) -> Value {
        let n = get_int(v);
        if n < 0 { argument_error("FACTORIAL"); }
        if n > 2000 { fail("FACTORIAL argument too large for this runtime"); }
        let mut result = BigInt::from(1);
        for i in 2..=n { result *= i; }
        value(Number::new(result, 0))
    }
    pub fn sum(args: &[Value]) -> Value {
        let mut total = Number::new(BigInt::from(0), 0);
        for a in args { total = total.plus(a.num()); }
        value(total)
    }
    pub fn mean(args: &[Value]) -> Value {
        if args.len() == 1 { return args[0].snapshot(); }
        value(sum(args).num().divide(Number::new(BigInt::from(args.len()), 0)))
    }
    fn select(args: &[Value], want: std::cmp::Ordering) -> (usize, Value) {
        let mut best = 0;
        for (i, a) in args.iter().enumerate().skip(1) {
            if a.compare(&args[best]) == want { best = i; }
        }
        (best, args[best].snapshot())
    }
    pub fn max(args: &[Value]) -> Value { select(args, std::cmp::Ordering::Greater).1 }
    pub fn min(args: &[Value]) -> Value { select(args, std::cmp::Ordering::Less).1 }
    pub fn ord_max(args: &[Value]) -> Value { int_of(select(args, std::cmp::Ordering::Greater).0 as i128 + 1) }
    pub fn ord_min(args: &[Value]) -> Value { int_of(select(args, std::cmp::Ordering::Less).0 as i128 + 1) }
    /// get_min_and_max_of_args: the first minimum and the first maximum.
    fn min_and_max(args: &[Value]) -> (Value, Value) {
        let (mut low, mut high) = (0, 0);
        for i in 1..args.len() {
            if args[i].compare(&args[low]) == std::cmp::Ordering::Less { low = i; }
            if args[i].compare(&args[high]) == std::cmp::Ordering::Greater { high = i; }
        }
        (args[low].snapshot(), args[high].snapshot())
    }
    pub fn range(args: &[Value]) -> Value {
        let (low, high) = min_and_max(args);
        value(high.num().plus(low.num().neg()))
    }
    pub fn midrange(args: &[Value]) -> Value {
        let (low, high) = min_and_max(args);
        value(low.num().plus(high.num()).divide(Number::new(BigInt::from(2), 0)))
    }
    pub fn median(args: &[Value]) -> Value {
        if args.len() == 1 { return args[0].snapshot(); }
        let mut sorted: Vec<Value> = args.iter().map(|a| a.snapshot()).collect();
        sorted.sort_by(|a, b| a.compare(b));
        let i = sorted.len() / 2;
        if sorted.len() % 2 == 1 { return sorted[i].clone(); }
        value(sorted[i - 1].num().plus(sorted[i].num()).divide(Number::new(BigInt::from(2), 0)))
    }
    /// GET_VARIANCE: mean, then the mean of the squared differences.
    pub fn variance(args: &[Value]) -> Value {
        if args.len() == 1 { return value(Number::new(BigInt::from(0), 0)); }
        let n = Number::new(BigInt::from(args.len()), 0);
        let mut total = Number::new(BigInt::from(0), 0);
        for a in args { total = total.plus(a.num()); }
        let mean = total.divide(n.clone());
        let mut squares = Number::new(BigInt::from(0), 0);
        for a in args {
            let d = a.num().plus(mean.clone().neg());
            squares = squares.plus(d.clone().times(d));
        }
        value(squares.divide(n))
    }
    pub fn annuity(rate: &Value, periods: &Value) -> Value {
        let (r, p) = (rate.num(), periods.num());
        if r.n.sign() == Sign::Minus || p.n.sign() != Sign::Plus || p.scale != 0 { argument_error("ANNUITY"); }
        if r.n == BigInt::from(0) { return value(Number::new(BigInt::from(1), 0).divide(p)); }
        let base = trimmed(r.clone().plus(Number::new(BigInt::from(1), 0)));
        let raised = base.power(trimmed(p.neg()));
        let denominator = trimmed(Number::new(BigInt::from(1), 0).plus(raised.neg()));
        value(trimmed(r).divide(denominator))
    }
    pub fn present_value(args: &[Value]) -> Value {
        let rate = args[0].num().plus(Number::new(BigInt::from(1), 0));
        let mut total = Number::new(BigInt::from(0), 0);
        for (i, a) in args.iter().enumerate().skip(1) {
            let mut d3 = rate.clone();
            if i > 1 { d3 = Number::new(d3.n.pow(i as u32), d3.scale * i as u32); }
            total = total.plus(a.num().divide(d3));
        }
        value(total)
    }
    pub fn char_of(v: &Value) -> Value {
        let i = get_int(v);
        Value::Bytes(vec![if (1..=256).contains(&i) { (i - 1) as u8 } else { 0 }])
    }
    pub fn ord(v: &Value) -> Value {
        let b = v.bytes();
        int_of(*b.first().unwrap_or_else(|| fail("FUNCTION ORD of an empty item")) as i128 + 1)
    }
    fn ascii_only(bytes: &[u8], name: &str) {
        if bytes.iter().any(|b| *b >= 128) { fail(&format!("FUNCTION {name}: case of a non-ASCII byte depends on the locale")); }
    }
    pub fn upper_case(v: &Value) -> Value { let b = v.bytes(); ascii_only(&b, "UPPER-CASE"); Value::Bytes(b.to_ascii_uppercase()) }
    pub fn lower_case(v: &Value) -> Value { let b = v.bytes(); ascii_only(&b, "LOWER-CASE"); Value::Bytes(b.to_ascii_lowercase()) }
    pub fn reverse(v: &Value) -> Value { let mut b = v.bytes(); b.reverse(); Value::Bytes(b) }

    const NORMAL_DAYS: [i64; 13] = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365];
    const LEAP_DAYS: [i64; 13] = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366];
    const NORMAL_MONTH: [i64; 13] = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    const LEAP_MONTH: [i64; 13] = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    fn leap(y: i64) -> bool { (y % 4 == 0 && y % 100 != 0) || y % 400 == 0 }
    fn days_in_year(y: i64) -> i64 { 365 + leap(y) as i64 }
    fn days_up_to_year(y: i64) -> i64 { (1601..y).map(days_in_year).sum() }
    pub fn integer_of_date(v: &Value) -> Value {
        let date = get_int(v);
        let (year, month, day) = (date / 10000, date % 10000 / 100, date % 100);
        if !(1601..=9999).contains(&year) || !(1..=12).contains(&month) { argument_error("INTEGER-OF-DATE"); }
        let limit = if leap(year) { LEAP_MONTH[month as usize] } else { NORMAL_MONTH[month as usize] };
        if !(1..=limit).contains(&day) { argument_error("INTEGER-OF-DATE"); }
        let before = if leap(year) { LEAP_DAYS[month as usize - 1] } else { NORMAL_DAYS[month as usize - 1] };
        int_of((days_up_to_year(year) + before + day) as i128)
    }
    pub fn integer_of_day(v: &Value) -> Value {
        let date = get_int(v);
        let (year, day) = (date / 1000, date % 1000);
        if !(1601..=9999).contains(&year) || !(1..=days_in_year(year)).contains(&day) { argument_error("INTEGER-OF-DAY"); }
        int_of((days_up_to_year(year) + day) as i128)
    }
    fn year_of(days: i64) -> (i64, i64) {
        let (mut days, mut year, mut length) = (days, 1601, 365);
        while days > length { days -= length; year += 1; length = days_in_year(year); }
        (year, days)
    }
    pub fn date_of_integer(v: &Value) -> Value {
        let n = get_int(v);
        if !(1..=3067671).contains(&n) { argument_error("DATE-OF-INTEGER"); }
        let (year, mut days) = year_of(n);
        let table = if leap(year) { &LEAP_DAYS } else { &NORMAL_DAYS };
        let mut month = 13;
        for i in 1..13 { if days <= table[i] { days -= table[i - 1]; month = i as i64; break; } }
        int_of((year * 10000 + month * 100 + days) as i128)
    }
    pub fn day_of_integer(v: &Value) -> Value {
        let n = get_int(v);
        if !(1..=3067671).contains(&n) { argument_error("DAY-OF-INTEGER"); }
        let (year, days) = year_of(n);
        int_of((year * 1000 + days) as i128)
    }
    /// numval: the digits, sign and decimal point of a NUMVAL/NUMVAL-C argument.
    pub fn length(v: &Value) -> Value { int_of(v.bytes().len() as i128) }
    pub fn numval(v: &Value, currency_sign: bool, currency: Option<Vec<u8>>) -> Value {
        let data = v.bytes();
        if data.is_empty() { return int_of(0); }
        let mut end = data.len() - 1;
        while end > 0 && (data[end] == b' ' || data[end] == 0) { end -= 1; }
        let mut p = 0;
        while p != end && (data[p] == b' ' || data[p] == b'0') { p += 1; }
        let (mut digits, mut decimals, mut sign, mut point, mut exception) = (Vec::new(), 0u32, 0i32, false, false);
        let mut currency_seen = false;
        // A currency argument counts only when it is shorter than the data.
        let currency = currency.filter(|c| c.len() < (end - p + 1).min(38));
        while p <= end {
            if end - p + 1 >= 2 && matches!((data[p].to_ascii_uppercase(), data[p + 1].to_ascii_uppercase()), (b'C', b'R') | (b'D', b'B')) {
                if sign != 0 { exception = true; }
                else if data[p + 2..=end].iter().any(|b| *b != b' ') { exception = true; }
                sign = -1;
                break;
            }
            if let Some(symbol) = &currency {
                if end - p + 1 >= symbol.len() && data[p..p + symbol.len()] == symbol[..] {
                    if currency_seen || !digits.is_empty() || point { exception = true; }
                    currency_seen = true;
                    p += symbol.len();
                    continue;
                }
            } else if currency_sign && data[p] == b'$' {
                if currency_seen { exception = true; } else { currency_seen = true; }
                p += 1;
                continue;
            }
            match data[p] {
                b'0' if digits.is_empty() && !point => {},
                b'0'..=b'9' => {
                    if point { decimals += 1; }
                    digits.push(data[p]);
                    if digits.len() > 38 { exception = true; break; }
                },
                b'+' => if sign != 0 { exception = true } else { sign = 1 },
                b'-' => if sign != 0 { exception = true } else { sign = -1 },
                b' ' => {},
                b'.' => { if point { exception = true; } point = true; },
                b',' if currency_sign => {},
                _ => exception = true,
            }
            p += 1;
        }
        if exception { fail("FUNCTION NUMVAL: invalid argument (EC-ARGUMENT-FUNCTION) not modelled"); }
        let mut n = if digits.is_empty() { BigInt::from(0) } else { BigInt::parse_bytes(&digits, 10).unwrap() };
        if sign == -1 { n = -n; }
        value(Number::new(n, decimals))
    }
    #[allow(dead_code)]
    fn unused(_: &BigInt) -> BigInt { absolute(&BigInt::from(0)) }
}
