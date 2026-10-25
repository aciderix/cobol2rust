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
        collated_cmp(&bytes, &vec![b'0'; bytes.len()])
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
            return collated_cmp(&a, &b);
        }
        match (self, other) {
            (Self::Num(a, _), Self::Num(b, _)) => {
                let scale = a.scale.max(b.scale);
                (&a.n * power(scale - a.scale)).cmp(&(&b.n * power(scale - b.scale)))
            },
            (Self::Text(a), Self::Text(b)) => {
                let len = a.len().max(b.len());
                collated_cmp(format!("{a:<len$}").as_bytes(), format!("{b:<len$}").as_bytes())
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
                if *scale > 0 { s.insert(s.len() - *scale as usize, module_symbols().0 as char); }
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
                Ok(_) if byte[0] == 3 => interrupt(),
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
/// Files open in the run unit (file_runtime's open paths).
pub static OPEN_FILES: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);

/// cob_raise (SIGINT) from cob_accept on character 03: cob_sig_handler
/// writes its message, cob_terminate_routines leaves the open files as they
/// are (cob_exit_fileio_msg_only) and the signal is raised again with its
/// default action. The stdio buffers of files still open would be lost
/// there, which is not modelled.
fn interrupt() -> ! {
    if OPEN_FILES.load(std::sync::atomic::Ordering::Relaxed) > 0 {
        fail("SIGINT (character 03 read by ACCEPT) with open files not modelled");
    }
    io::stdout().flush().unwrap_or_else(|_| fail("stdout flush failed"));
    eprintln!("\nlibcob: interrupt from keyboard (signal SIGINT)\n");
    extern "C" { fn raise(signal: i32) -> i32; }
    // SAFETY: raise(3) of SIGINT, whose default action ends the process.
    unsafe { raise(2); }
    std::process::exit(130)
}

/// cob_accept (NULL), the ACCEPT of STOP literal: input up to '\n' or end
/// of input is discarded; character 03 raises SIGINT.
pub fn accept_omitted() {
    io::stdout().flush().unwrap_or_else(|_| fail("stdout flush failed"));
    let stdin = io::stdin();
    let mut input = stdin.lock();
    let mut byte = [0u8; 1];
    loop {
        match io::Read::read(&mut input, &mut byte) {
            Ok(0) => break,
            Ok(_) if byte[0] == b'\n' => break,
            Ok(_) if byte[0] == 3 => interrupt(),
            Ok(_) => {},
            Err(_) => fail("stdin read failed"),
        }
    }
}

/// DISPLAY UPON SYSERR.
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
thread_local! {
    static COLLATING: std::cell::Cell<Option<&'static [u8; 256]>> = const { std::cell::Cell::new(None) };
}

/// COB_MODULE_PTR->collating_sequence of the running program, restored
/// when it returns to its caller.
pub struct CollatingGuard(Option<&'static [u8; 256]>);
impl CollatingGuard {
    pub fn new(table: Option<&'static [u8; 256]>) -> Self { CollatingGuard(COLLATING.with(|c| c.replace(table))) }
}
impl Drop for CollatingGuard {
    fn drop(&mut self) { COLLATING.with(|c| c.set(self.0)); }
}

thread_local! {
    static SYMBOLS: std::cell::Cell<(u8, u8, u8)> = const { std::cell::Cell::new((b'.', b',', b'$')) };
}

/// COB_MODULE_PTR->decimal_point, numeric_separator and currency_symbol of
/// the running program (DECIMAL-POINT IS COMMA, CURRENCY SIGN).
pub struct SymbolGuard((u8, u8, u8));
impl SymbolGuard {
    pub fn new(decimal_point: u8, separator: u8, currency: u8) -> Self {
        SymbolGuard(SYMBOLS.with(|s| s.replace((decimal_point, separator, currency))))
    }
}
impl Drop for SymbolGuard {
    fn drop(&mut self) { SYMBOLS.with(|s| s.set(self.0)); }
}

/// (decimal point, numeric separator, currency sign) of the module.
pub fn module_symbols() -> (u8, u8, u8) { SYMBOLS.with(|s| s.get()) }

/// Bytes written with the module symbols, read in the internal ones:
/// '.' decimal point, ',' separator, '$' currency (another '$' is no sign).
pub fn internal_symbols(bytes: &[u8], currency: bool) -> Vec<u8> {
    let (point, separator, sign) = module_symbols();
    bytes.iter().map(|&b| if b == point { b'.' } else if b == separator { b',' }
                          else if currency && b == sign { b'$' } else if currency && b == b'$' { 0 } else { b }).collect()
}

/// The inverse mapping, for edited output.
pub fn module_text(bytes: Vec<u8>) -> Vec<u8> {
    let (point, separator, sign) = module_symbols();
    if (point, separator, sign) == (b'.', b',', b'$') { return bytes; }
    bytes.into_iter().map(|b| match b { b'.' => point, b',' => separator, b'$' => sign, _ => b }).collect()
}

/// common_cmps: bytes compared by their weight in the program collating
/// sequence, or as memcmp without one.
pub fn collated_cmp(a: &[u8], b: &[u8]) -> std::cmp::Ordering {
    match COLLATING.with(|c| c.get()) {
        None => a.cmp(b),
        Some(table) => a.iter().map(|&x| table[x as usize]).cmp(b.iter().map(|&x| table[x as usize])),
    }
}

/// cob_debugging_mode: COB_SET_DEBUG read once (ENV_BOOL, default off).
pub fn debugging_mode() -> bool {
    static MODE: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *MODE.get_or_init(|| match std::env::var("COB_SET_DEBUG") {
        Err(_) => false,
        Ok(value) => match value.to_ascii_lowercase().as_str() {
            "1" | "true" | "t" | "on" | "yes" | "y" => true,
            "0" | "false" | "f" | "off" | "no" | "n" => false,
            _ => fail("COB_SET_DEBUG value outside true/false not modelled"),
        },
    })
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
    /// GMP floats in libcob (2048 bits) are converted back with mpf_get_str
    /// to 96 significant digits, rounded to nearest (cob_decimal_set_mpf).
    /// The functions below compute with `PRECISION` decimal digits, far
    /// beyond those 96, then round the same way.
    const PRECISION: i64 = 150;
    const DIGITS: i64 = 96;

    /// m * 10^e, the mantissa kept to PRECISION significant digits.
    #[derive(Clone)]
    struct Float { m: BigInt, e: i64 }

    fn digit_count(n: &BigInt) -> i64 { if n.sign() == Sign::NoSign { 0 } else { absolute(n).to_string().len() as i64 } }

    impl Float {
        fn int(n: i64) -> Float { Float { m: BigInt::from(n), e: 0 } }
        fn of(n: &Number) -> Float { Float { m: n.n.clone(), e: -(n.scale as i64) }.norm() }
        fn norm(mut self) -> Float {
            let extra = digit_count(&self.m) - PRECISION;
            if extra > 0 { self.m = &self.m / power(extra as u32); self.e += extra; }
            self
        }
        fn is_zero(&self) -> bool { self.m.sign() == Sign::NoSign }
        fn neg(&self) -> Float { Float { m: -self.m.clone(), e: self.e } }
        fn add(&self, other: &Float) -> Float {
            if self.is_zero() { return other.clone(); }
            if other.is_zero() { return self.clone(); }
            let e = self.e.min(other.e);
            // Terms far below the precision of the larger one do not count.
            let top = (self.e + digit_count(&self.m)).max(other.e + digit_count(&other.m));
            let e = e.max(top - PRECISION - 10);
            let align = |f: &Float| -> BigInt {
                if f.e >= e { &f.m * power((f.e - e) as u32) } else { &f.m / power((e - f.e) as u32) }
            };
            Float { m: align(self) + align(other), e }.norm()
        }
        fn sub(&self, other: &Float) -> Float { self.add(&other.neg()) }
        fn mul(&self, other: &Float) -> Float { Float { m: &self.m * &other.m, e: self.e + other.e }.norm() }
        fn div(&self, other: &Float) -> Float {
            if other.is_zero() { fail("division by zero in a mathematical function"); }
            let shift = PRECISION + 5 + digit_count(&other.m) - digit_count(&self.m);
            let shift = shift.max(0);
            Float { m: (&self.m * power(shift as u32)) / &other.m, e: self.e - other.e - shift }.norm()
        }
        fn half(&self) -> Float { self.div(&Float::int(2)) }
        /// The greatest integer not above the value.
        fn floor(&self) -> BigInt {
            if self.e >= 0 { return &self.m * power(self.e as u32); }
            let divisor = power((-self.e) as u32);
            let q = &self.m / &divisor;
            if self.negative() && &q * &divisor != self.m { q - 1 } else { q }
        }
        fn round(&self) -> BigInt { self.add(&Float { m: BigInt::from(5), e: -1 }).floor() }
        fn negative(&self) -> bool { self.m.sign() == Sign::Minus }
        fn magnitude_below(&self, exponent: i64) -> bool { self.is_zero() || digit_count(&self.m) + self.e <= exponent }
        /// cob_decimal_set_mpf: 96 significant digits, rounded to nearest.
        fn number(&self) -> Number {
            if self.is_zero() { return Number::new(BigInt::from(0), 0); }
            let negative = self.negative();
            let mut m = absolute(&self.m);
            let mut e = self.e;
            let extra = digit_count(&m) - DIGITS;
            if extra > 0 {
                let divisor = power(extra as u32);
                let (q, r) = (&m / &divisor, &m % &divisor);
                m = if r * 2 >= divisor { q + 1 } else { q };
                e += extra;
            }
            if negative { m = -m; }
            let n = if e >= 0 { Number::new(m * power(e as u32), 0) } else { Number::new(m, (-e) as u32) };
            n.trimmed()
        }
    }

    /// Series for atan(1/k) to PRECISION digits (Machin's formula for pi).
    fn atan_inverse(k: i64) -> Float {
        let x = Float::int(1).div(&Float::int(k));
        let x2 = x.mul(&x);
        let (mut term, mut sum, mut n) = (x.clone(), x, 1i64);
        loop {
            term = term.mul(&x2).neg();
            n += 2;
            let piece = term.div(&Float::int(n));
            if piece.magnitude_below(-PRECISION - 5) { return sum; }
            sum = sum.add(&piece);
        }
    }
    fn pi() -> Float { atan_inverse(5).mul(&Float::int(16)).sub(&atan_inverse(239).mul(&Float::int(4))) }

    /// 2 atanh(z) = ln((1+z)/(1-z)).
    fn atanh2(z: &Float) -> Float {
        let z2 = z.mul(z);
        let (mut term, mut sum, mut n) = (z.clone(), z.clone(), 1i64);
        loop {
            term = term.mul(&z2);
            n += 2;
            let piece = term.div(&Float::int(n));
            if piece.magnitude_below(-PRECISION - 5) { return sum.mul(&Float::int(2)); }
            sum = sum.add(&piece);
        }
    }
    fn ln2() -> Float { atanh2(&Float::int(1).div(&Float::int(3))) }
    fn ln10() -> Float { ln2().mul(&Float::int(3)).add(&atanh2(&Float::int(1).div(&Float::int(9)))) }

    fn ln(x: &Float) -> Float {
        // x = y * 10^k with y in [1, 10), then y halved into [1, 2).
        let k = digit_count(&x.m) - 1 + x.e;
        let mut y = Float { m: x.m.clone(), e: x.e - k };
        let mut halvings = 0i64;
        while !y.sub(&Float::int(2)).negative() { y = y.half(); halvings += 1; }
        let z = y.sub(&Float::int(1)).div(&y.add(&Float::int(1)));
        atanh2(&z).add(&ln2().mul(&Float::int(halvings))).add(&ln10().mul(&Float::int(k)))
    }

    fn exp(x: &Float) -> Float {
        if !x.magnitude_below(7) { fail("FUNCTION EXP of an argument beyond 10^6 not modelled"); }
        let l2 = ln2();
        let q: i64 = x.div(&l2).round().to_string().parse().unwrap();
        let r = x.sub(&l2.mul(&Float::int(q)));
        let (mut term, mut sum, mut n) = (Float::int(1), Float::int(1), 0i64);
        loop {
            n += 1;
            term = term.mul(&r).div(&Float::int(n));
            if term.magnitude_below(-PRECISION - 5) { break; }
            sum = sum.add(&term);
        }
        let two = Float { m: BigInt::from(2).pow(q.unsigned_abs() as u32), e: 0 };
        if q >= 0 { sum.mul(&two) } else { sum.div(&two) }
    }

    /// sin or cos of a reduced argument |r| <= pi/4.
    fn sin_series(r: &Float) -> Float {
        let r2 = r.mul(r);
        let (mut term, mut sum, mut n) = (r.clone(), r.clone(), 1i64);
        loop {
            term = term.mul(&r2).div(&Float::int((n + 1) * (n + 2))).neg();
            n += 2;
            if term.magnitude_below(-PRECISION - 5) { return sum; }
            sum = sum.add(&term);
        }
    }
    fn cos_series(r: &Float) -> Float {
        let r2 = r.mul(r);
        let (mut term, mut sum, mut n) = (Float::int(1), Float::int(1), 0i64);
        loop {
            term = term.mul(&r2).div(&Float::int((n + 1) * (n + 2))).neg();
            n += 2;
            if term.magnitude_below(-PRECISION - 5) { return sum; }
            sum = sum.add(&term);
        }
    }
    /// (sin x, cos x) by reduction to an octant.
    fn sin_cos(x: &Float) -> (Float, Float) {
        if !x.magnitude_below(40) { fail("trigonometric argument beyond 10^40 not modelled"); }
        let half_pi = pi().half();
        // x = q pi/2 + r with |r| <= pi/4.
        let q_int = x.div(&half_pi).round();
        let r = x.sub(&half_pi.mul(&Float { m: q_int.clone(), e: 0 }));
        let (s, c) = (sin_series(&r), cos_series(&r));
        let octant = ((q_int % BigInt::from(4)) + BigInt::from(4)) % BigInt::from(4);
        match octant.to_string().as_str() {
            "0" => (s, c),
            "1" => (c, s.neg()),
            "2" => (s.neg(), c.neg()),
            _ => (c.neg(), s),
        }
    }
    /// atan for |x| <= 1: halve the angle until small, then the series.
    fn atan_small(x: &Float) -> Float {
        let mut y = x.clone();
        let mut doublings = 0u32;
        while !y.magnitude_below(-1) {
            // atan(y) = 2 atan(y / (1 + sqrt(1 + y^2)))
            y = y.div(&Float::int(1).add(&sqrt(&Float::int(1).add(&y.mul(&y)))));
            doublings += 1;
        }
        let y2 = y.mul(&y);
        let (mut term, mut sum, mut n) = (y.clone(), y.clone(), 1i64);
        loop {
            term = term.mul(&y2).neg();
            n += 2;
            let piece = term.div(&Float::int(n));
            if piece.magnitude_below(-PRECISION - 5) { break; }
            sum = sum.add(&piece);
        }
        sum.mul(&Float { m: BigInt::from(2).pow(doublings), e: 0 })
    }
    fn sqrt(x: &Float) -> Float {
        if x.is_zero() { return x.clone(); }
        // An even exponent and enough digits for PRECISION digits of root.
        let mut m = x.m.clone();
        let mut e = x.e;
        let want = 2 * PRECISION + 10 - digit_count(&m);
        let mut shift = want.max(0);
        if (e - shift) % 2 != 0 { shift += 1; }
        m *= power(shift as u32);
        e -= shift;
        Float { m: m.sqrt(), e: e / 2 }.norm()
    }

    fn result(f: Float) -> Value { value(f.number()) }

    pub fn sqrt_of(v: &Value) -> Value {
        let n = v.num();
        if n.n.sign() == Sign::Minus { argument_error("SQRT"); }
        result(sqrt(&Float::of(&n.trimmed())))
    }
    pub fn standard_deviation(args: &[Value]) -> Value {
        let variance = variance(args).num();
        if variance.n.sign() == Sign::NoSign { return value(Number::new(BigInt::from(0), 0)); }
        result(sqrt(&Float::of(&variance.trimmed())))
    }
    pub fn log(v: &Value) -> Value {
        let n = v.num().trimmed();
        if n.n.sign() != Sign::Plus { argument_error("LOG"); }
        if n.scale == 0 && n.n == BigInt::from(1) { return int_of(0); }
        result(ln(&Float::of(&n)))
    }
    pub fn log10(v: &Value) -> Value {
        let n = v.num().trimmed();
        if n.n.sign() != Sign::Plus { argument_error("LOG10"); }
        if n.scale == 0 && n.n == BigInt::from(1) { return int_of(0); }
        result(ln(&Float::of(&n)).div(&ln10()))
    }
    pub fn exp_of(v: &Value) -> Value {
        let n = v.num();
        if n.n.sign() == Sign::NoSign { return int_of(1); }
        result(exp(&Float::of(&n)))
    }
    pub fn e() -> Value { result(exp(&Float::int(1))) }
    pub fn pi_value() -> Value { result(pi()) }

    /// cob_intr_current_date: YYYYMMDDhhmmsscc and the UTC offset.
    pub fn current_date() -> Value {
        let t = super::current_datetime();
        let (hours, minutes) = (t.utc_offset / 60, t.utc_offset.abs() % 60);
        Value::text(&format!("{:04}{:02}{:02}{:02}{:02}{:02}{:02}{}{:02}{:02}", t.year, t.month, t.day, t.hour, t.minute,
                             t.second, t.nanosecond / 10_000_000, if t.utc_offset < 0 { '-' } else { '+' }, hours.abs(), minutes))
    }
    /// cob_intr_random with GMP's Mersenne Twister (gmp_randinit_mt,
    /// gmp_randseed_ui, mpf_urandomb of 63 bits, mpf_get_d), the double
    /// converted exactly by cob_decimal_set_double.
    pub fn random(seed: Option<&Value>) -> Value {
        thread_local! {
            static STATE: std::cell::RefCell<(i32, Option<super::MersenneTwister>)> = const { std::cell::RefCell::new((1, None)) };
        }
        let mut value = 0u64;
        STATE.with(|state| {
            let (needs_seeding, generator) = &mut *state.borrow_mut();
            let mut seeded = 0u64;
            if let Some(seed) = seed {
                // cob_get_llint; a negative seed sets EC-ARGUMENT-FUNCTION and seeds 0.
                let n = seed.num().units(0, false);
                if n.sign() != Sign::Minus {
                    seeded = u64::try_from(&n).unwrap_or_else(|_| fail("RANDOM seed beyond 64 bits not modelled"));
                }
                *needs_seeding += 1;
            } else if *needs_seeding != 0 {
                // First call without a seed: libcob uses the seconds past
                // midnight times bits of the module's address, a value no
                // run can reproduce; any such seed is a native outcome.
                let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
                let address = (&*state as *const _ as u64) & 0xFFFFF;
                seeded = (now % 86400).wrapping_mul(address);
                *needs_seeding = 2;
            }
            if *needs_seeding != 0 {
                let mut mt = generator.take().unwrap_or_default();
                mt.seed(seeded);
                *generator = Some(mt);
                *needs_seeding = 0;
            }
            let mt = generator.as_mut().unwrap();
            // _gmp_rand of 63 bits in a 64-bit limb, then shifted up one bit.
            let low = mt.next() as u64;
            let high = (mt.next() as u64) & 0x7FFF_FFFF;
            value = (low | high << 32) << 1;
        });
        if value == 0 { return int_of(0); }
        // mpn_get_d truncates to the 53 bits of a double: value / 2^64.
        let mantissa = value & !((1u64 << (64 - value.leading_zeros()).saturating_sub(53)) - 1);
        let exact = BigInt::from(mantissa) * BigInt::from(5u32).pow(64);
        let digits = format!("{:0>64}", exact.to_string());
        let fraction = digits.trim_end_matches('0');
        Value::number(&format!("0.{fraction}"))
    }
    pub fn sin(v: &Value) -> Value { result(sin_cos(&Float::of(&v.num())).0) }
    pub fn cos(v: &Value) -> Value { result(sin_cos(&Float::of(&v.num())).1) }
    pub fn tan(v: &Value) -> Value {
        let (s, c) = sin_cos(&Float::of(&v.num()));
        result(s.div(&c))
    }
    fn unit_interval(v: &Value, name: &str) -> Float {
        let x = Float::of(&v.num());
        let one = Float::int(1);
        if x.sub(&one).m.sign() == Sign::Plus || x.add(&one).negative() { argument_error(name); }
        x
    }
    fn asin_of(x: &Float) -> Float {
        let one = Float::int(1);
        let rest = one.sub(&x.mul(x));
        if rest.is_zero() { return if x.negative() { pi().half().neg() } else { pi().half() }; }
        atan_small_or_large(&x.div(&sqrt(&rest)))
    }
    fn atan_small_or_large(x: &Float) -> Float {
        let one = Float::int(1);
        if x.sub(&one).m.sign() == Sign::Plus || x.add(&one).negative() {
            let inner = atan_small(&one.div(x));
            let quarter = pi().half();
            return if x.negative() { quarter.neg().sub(&inner) } else { quarter.sub(&inner) };
        }
        atan_small(x)
    }
    pub fn asin(v: &Value) -> Value {
        let x = unit_interval(v, "ASIN");
        if x.is_zero() { return int_of(0); }
        result(asin_of(&x))
    }
    pub fn acos(v: &Value) -> Value {
        let x = unit_interval(v, "ACOS");
        result(pi().half().sub(&asin_of(&x)))
    }
    pub fn atan_of(v: &Value) -> Value {
        let x = Float::of(&v.num());
        if x.is_zero() { return int_of(0); }
        result(atan_small_or_large(&x))
    }

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
        // cob_intr_numval: the module's decimal point and currency sign.
        let data = crate::runtime::internal_symbols(&v.bytes(), currency_sign && currency.is_none());
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

/// struct cob_time of cob_get_current_datetime.
#[derive(Clone, Copy)]
pub struct CobTime {
    pub year: i64, pub month: i64, pub day: i64, pub hour: i64, pub minute: i64, pub second: i64,
    pub nanosecond: i64, pub day_of_week: i64, pub day_of_year: i64, pub utc_offset: i64,
}

/// Days from 1970-01-01 of a proleptic Gregorian date (month 1..12, any day).
fn days_from_civil(year: i64, month: i64, day: i64) -> i64 {
    let y = if month <= 2 { year - 1 } else { year };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let mp = (month + 9) % 12;
    let doy = (153 * mp + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

/// The broken-down UTC time of a second count (gmtime, which is localtime in UTC).
fn broken_down(seconds: i64) -> CobTime {
    let (days, rest) = (seconds.div_euclid(86400), seconds.rem_euclid(86400));
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = yoe + era * 400 + if month <= 2 { 1 } else { 0 };
    CobTime { year, month, day, hour: rest / 3600, minute: rest % 3600 / 60, second: rest % 60, nanosecond: 0,
              // 1970-01-01 was a Thursday; libcob counts Monday as 1.
              day_of_week: (days + 3).rem_euclid(7) + 1, day_of_year: days - days_from_civil(year, 1, 1) + 1, utc_offset: 0 }
}

/// mktime in UTC: normalize the fields (30 Feb is 2 March, second 60 the next minute).
fn normalized(t: &CobTime) -> CobTime {
    let months = t.year * 12 + t.month - 1;
    let seconds = (days_from_civil(months.div_euclid(12), months.rem_euclid(12) + 1, 1) + t.day - 1) * 86400
        + t.hour * 3600 + t.minute * 60 + t.second;
    broken_down(seconds)
}

/// The local time zone, modelled only when it is UTC.
fn utc_only(what: &str) {
    let utc = match std::env::var("TZ") {
        Ok(tz) => matches!(tz.trim_start_matches(':'), "UTC" | "UTC0" | "GMT" | "GMT0" | "Etc/UTC" | "Etc/GMT" | "UCT" | "Zulu" | ""),
        Err(_) => match std::fs::read("/etc/localtime") {
            Err(_) => true,
            // A TZif file without transitions and with one offset 0 type.
            Ok(data) => data.len() >= 50 && &data[..4] == b"TZif"
                && data[32..36] == [0, 0, 0, 0] && data[36..40] == [0, 0, 0, 1] && data[44..48] == [0, 0, 0, 0],
        },
    };
    if !utc { fail(&format!("{what} in a local time zone other than UTC not modelled")); }
}

/// cob_time_constant: the parts COB_CURRENT_DATE fixes (None: from the clock),
/// with the day of week and of year when the whole date is given.
#[derive(Clone, Copy, Default)]
struct TimeConstant {
    year: Option<i64>, month: Option<i64>, day: Option<i64>, hour: Option<i64>, minute: Option<i64>,
    second: Option<i64>, nanosecond: Option<i64>, calculated: Option<(i64, i64)>, offset: Option<i64>,
}

/// check_current_date: COB_CURRENT_DATE "YYYY/MM/DD hh:mm:ss.nnnnnnnnn+hhmm",
/// each part optional from the right or written as a template (YYYY, MM, ...).
fn check_current_date(text: &str, now: &CobTime) -> TimeConstant {
    let p: Vec<u8> = text.bytes().collect();
    let mut i = 0;
    while i < p.len() && (p[i] == b'\'' || p[i] == b'"' || p[i].is_ascii_whitespace()) { i += 1; }
    if p.get(i) == Some(&b'@') { fail("COB_CURRENT_DATE as seconds since the epoch not modelled"); }
    let at = |i: usize| p.get(i).copied().unwrap_or(0);
    let mut invalid = false;
    // One numeric part of `width` digits (or 2 or 4 for the year), else a template letter.
    let mut part = |i: &mut usize, width: usize, letter: u8, invalid: &mut bool, year: bool| -> Option<i64> {
        let mut value = 0;
        let mut count = 0;
        while at(*i) != 0 && at(*i).is_ascii_digit() {
            value = value * 10 + (at(*i) - b'0') as i64;
            *i += 1;
            count += 1;
            if count == width { break; }
        }
        if count == width || (year && count == 2) {
            return Some(if year && value < 100 { value + 2000 } else { value });
        }
        if at(*i) == letter { while at(*i) == letter { *i += 1; } } else { *invalid = true; }
        None
    };
    let (mut yr, mut mm, mut dd, mut hh, mut mi, mut ss, mut ns) = (None, None, None, None, None, None, None);
    if at(i) != 0 {
        yr = part(&mut i, 4, b'Y', &mut invalid, true);
        if at(i) == b'/' || at(i) == b'-' { i += 1; }
    }
    if at(i) != 0 {
        mm = part(&mut i, 2, b'M', &mut invalid, false);
        if mm.is_some_and(|m| !(1..=12).contains(&m)) { invalid = true; }
        if at(i) == b'/' || at(i) == b'-' { i += 1; }
    }
    if at(i) != 0 {
        dd = part(&mut i, 2, b'D', &mut invalid, false);
        if dd.is_some_and(|d| !(1..=31).contains(&d)) { invalid = true; }
    }
    if at(i) != 0 {
        while at(i).is_ascii_whitespace() { i += 1; }
        hh = part(&mut i, 2, b'H', &mut invalid, false);
        if hh.is_some_and(|h| h > 23) { invalid = true; }
        if at(i) == b':' || at(i) == b'-' { i += 1; }
    }
    if at(i) != 0 {
        mi = part(&mut i, 2, b'M', &mut invalid, false);
        if mi.is_some_and(|m| m > 59) { invalid = true; }
        if at(i) == b':' || at(i) == b'-' { i += 1; }
    }
    if !matches!(at(i), 0 | b'Z' | b'+' | b'-') {
        ss = part(&mut i, 2, b'S', &mut invalid, false);
        if ss.is_some_and(|s| s > 60) { invalid = true; }
    }
    if !matches!(at(i), 0 | b'Z' | b'+' | b'-') {
        if at(i) == b'.' || at(i) == b':' { i += 1; }
        let mut value = 0;
        let mut count = 0;
        while at(i).is_ascii_digit() && count < 9 { value = value * 10 + (at(i) - b'0') as i64; i += 1; count += 1; }
        ns = Some(value);
    }
    let mut offset = None;
    if at(i) == b'Z' {
        offset = Some(0);
    } else if at(i) == b'+' || at(i) == b'-' {
        // snprintf into a 7-byte buffer, its result being the full length.
        let rest = &p[i..];
        let mut length = rest.len();
        let mut zone: Vec<u8> = rest.iter().copied().take(6).collect();
        if length == 3 {
            zone.extend(b"00");
        } else if length >= 5 && zone[3] == b':' {
            zone.truncate(3);
            zone.extend(rest[4..].iter().take(2));
            length -= 1;
        }
        let digits: Vec<i64> = zone[1..].iter().take(4).take_while(|b| b.is_ascii_digit()).map(|b| (*b - b'0') as i64).collect();
        if length > 5 || digits.len() != 4 {
            invalid = true;
        } else {
            let minutes = digits[0] * 600 + digits[1] * 60 + digits[2] * 10 + digits[3];
            offset = Some(if zone[0] == b'-' { -minutes } else { minutes });
        }
    }
    if invalid { fail(&format!("invalid COB_CURRENT_DATE '{text}' (libcob warns and ignores it) not modelled")); }
    let mut tm = *now;
    if let Some(v) = ss { tm.second = v; }
    if let Some(v) = mi { tm.minute = v; }
    if let Some(v) = hh { tm.hour = v; }
    if let Some(v) = yr { tm.year = v; }
    if let Some(v) = mm { tm.month = v; }
    if let Some(v) = dd { tm.day = v; }
    let tm = normalized(&tm);
    TimeConstant {
        year: yr.map(|_| tm.year), month: mm.map(|_| tm.month), day: dd.map(|_| tm.day),
        hour: hh.map(|_| tm.hour), minute: mi.map(|_| tm.minute), second: ss.map(|_| tm.second), nanosecond: ns,
        calculated: (yr.is_some() && mm.is_some() && dd.is_some()).then_some((tm.day_of_week, tm.day_of_year)),
        offset,
    }
}

/// cob_get_current_datetime: the local time (UTC only) with its nanoseconds
/// (on Linux clock_gettime gives them whatever the resolution asked: only
/// the Windows branch drops them), then the parts COB_CURRENT_DATE fixes.
pub fn current_datetime() -> CobTime {
    utc_only("the current date and time");
    let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_else(|_| fail("system clock before 1970"));
    let mut t = broken_down(now.as_secs() as i64);
    t.nanosecond = now.subsec_nanos() as i64;
    // cob_init reads COB_CURRENT_DATE once.
    static CONSTANT: std::sync::OnceLock<Option<TimeConstant>> = std::sync::OnceLock::new();
    let constant = *CONSTANT.get_or_init(|| std::env::var("COB_CURRENT_DATE").ok().map(|text| check_current_date(&text, &t)));
    if let Some(c) = constant {
        if let Some(v) = c.hour { t.hour = v; }
        if let Some(v) = c.minute { t.minute = v; }
        if let Some(v) = c.second { t.second = v; }
        if let Some(v) = c.nanosecond { t.nanosecond = v; }
        if let Some(v) = c.offset { t.utc_offset = v; }
        if let Some((day_of_week, day_of_year)) = c.calculated {
            (t.year, t.month, t.day, t.day_of_week, t.day_of_year) = (c.year.unwrap(), c.month.unwrap(), c.day.unwrap(), day_of_week, day_of_year);
        } else if c.year.is_some() || c.month.is_some() || c.day.is_some() {
            if let Some(v) = c.year { t.year = v; }
            if let Some(v) = c.month { t.month = v; }
            if let Some(v) = c.day { t.day = v; }
            // mktime of the mixed date: day of week and of year.
            let n = normalized(&t);
            (t.day_of_week, t.day_of_year) = (n.day_of_week, n.day_of_year);
        }
    }
    t
}

/// cob_accept_date/_yyyymmdd, cob_accept_day/_yyyyddd, cob_accept_day_of_week
/// and cob_accept_time: the value and the digits of the binary field moved
/// (DAY-OF-WEEK is a one-character alphanumeric source).
fn clock(kind: &str) -> (i64, usize) {
    match kind {
        "DATE" => { let t = current_datetime(); (t.day + t.month * 100 + t.year % 100 * 10000, 6) },
        "DATE YYYYMMDD" => { let t = current_datetime(); (t.day + t.month * 100 + t.year * 10000, 8) },
        "DAY" => { let t = current_datetime(); (t.day_of_year + t.year % 100 * 1000, 5) },
        "DAY YYYYDDD" => { let t = current_datetime(); (t.day_of_year + t.year * 1000, 7) },
        "DAY-OF-WEEK" => (current_datetime().day_of_week, 1),
        "TIME" => {
            let t = current_datetime();
            (t.nanosecond / 10_000_000 + t.second * 100 + t.minute * 10000 + t.hour * 1000000, 8)
        },
        _ => fail("ACCEPT FROM clock register not modelled"),
    }
}

/// The clock register moved to a numeric receiver.
pub fn clock_value(kind: &str) -> Value { Value::number(&clock(kind).0.to_string()) }

/// The clock register moved to an alphanumeric or group receiver: its digits.
pub fn clock_digits(kind: &str) -> Vec<u8> {
    let (value, digits) = clock(kind);
    format!("{value:0digits$}").into_bytes()
}

/// GMP 6.3 rand/randmt.c and randmts.c: the Mersenne Twister state.
pub struct MersenneTwister { mt: [u32; 624], mti: usize }

impl Default for MersenneTwister {
    fn default() -> Self { Self { mt: [0; 624], mti: 0 } }
}

impl MersenneTwister {
    fn recalc(&mut self) {
        const N: usize = 624;
        const M: usize = 397;
        let twist = |y: u32| (y >> 1) ^ if y & 1 != 0 { 0x9908_B0DF } else { 0 };
        let mt = &mut self.mt;
        for kk in 0..N - M {
            let y = (mt[kk] & 0x8000_0000) | (mt[kk + 1] & 0x7FFF_FFFF);
            mt[kk] = mt[kk + M] ^ twist(y);
        }
        for kk in N - M..N - 1 {
            let y = (mt[kk] & 0x8000_0000) | (mt[kk + 1] & 0x7FFF_FFFF);
            mt[kk] = mt[kk - (N - M)] ^ twist(y);
        }
        let y = (mt[N - 1] & 0x8000_0000) | (mt[0] & 0x7FFF_FFFF);
        mt[N - 1] = mt[M - 1] ^ twist(y);
    }

    /// randseed_mt: seed mod (2^19937-20027) + 2, mangle_seed's power
    /// 1074888996 reduced the way GMP does (by 2^19937 = 20023), then the
    /// result split in 32-bit words, warmed up by WARM_UP = 2000 outputs.
    fn seed(&mut self, seed: u64) {
        let modulus = (BigInt::from(1) << 19937u32) - 20027;
        let mut r: BigInt = BigInt::from(seed) % &modulus + 2;
        let base = r.clone();
        let mask = (BigInt::from(1) << 19937u32) - 1;
        let reduce = |r: &mut BigInt| loop {
            let t: BigInt = &*r >> 19937u32;
            if t.sign() == Sign::NoSign { break; }
            *r = (&*r & &mask) + t * 20023;
        };
        let mut e: u64 = 0x4011_8124;
        let mut bit: u64 = 0x2000_0000;
        while bit != 0 {
            r = &r * &r;
            reduce(&mut r);
            if e & bit != 0 {
                e ^= bit;
                r = &r * &base;
                reduce(&mut r);
            }
            bit >>= 1;
        }
        let top: BigInt = (BigInt::from(1) << 19936u32) & &r;
        self.mt = [0; 624];
        self.mt[0] = if top.sign() != Sign::NoSign { 0x8000_0000 } else { 0 };
        let r: BigInt = r & ((BigInt::from(1) << 19936u32) - 1);
        let (_, words) = r.to_u32_digits();
        for (slot, word) in self.mt[1..].iter_mut().zip(words) { *slot = word; }
        for _ in 0..2000 / 624 { self.recalc(); }
        self.mti = 2000 % 624;
    }

    /// NEXT_RANDOM: one tempered output.
    fn next(&mut self) -> u32 {
        if self.mti >= 624 { self.recalc(); self.mti = 0; }
        let mut y = self.mt[self.mti];
        self.mti += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9D2C_5680;
        y ^= (y << 15) & 0xEFC6_0000;
        y ^= y >> 18;
        y
    }
}
