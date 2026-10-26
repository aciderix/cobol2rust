from __future__ import annotations

import re

from .frontend import CobolError, Program, ProcedureBlock, DataRef, Expr
from .layout import leaves
from .control import ControlGraph


def numeric_text(text):
    """A numeric literal may start with its decimal point (.5): runtime needs 0.5."""
    return re.sub(r"^([+-]?)\.", r"\g<1>0.", text)


def quoted(text):
    escapes = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return '"' + ''.join(escapes.get(c, f"\\x{ord(c):02x}" if ord(c) < 32 or ord(c) == 127 else c) for c in text) + '"'


def text_value(text):
    """A Rust Value for COBOL text; HIGH-VALUE/LOW-VALUE bytes are not ASCII."""
    if all(ord(c) < 128 for c in text):
        return f"Value::text({quoted(text)})"
    return "Value::Bytes(vec![" + ", ".join(str(ord(c)) for c in text) + "])"


def byte_pattern(text):
    return "[" + ", ".join(f"{ord(c)}u8" for c in text) + "]"


def byte_pattern_bytes(text):
    return [ord(c) for c in text]


class Emitter:
    def __init__(self, program: Program, struct="Program", subprogram=False, called=None, present=(), entries=()):
        self.program = program
        from .frontend import Parser
        self.program_functions = Parser.FUNCTIONS
        self.struct = struct
        self.subprogram = subprogram
        # A main program with PROCEDURE DIVISION USING is a module (cobc
        # refuses -x): it runs as cobcrun calls it, without arguments.
        self.module = not subprogram and bool(program.using)
        # CALL targets converted with this run unit (literal names).
        self.called = set(called or ())
        # ENTRY names of the run unit: unresolved until their program is loaded.
        self.entry_names = set(entries)
        self.called |= self.entry_names
        # Programs of the call path left unconverted: a CALL of one cannot be modelled.
        self.present = sorted(set(present) - self.called)
        self.names = {name: f"f{i}" for i, name in enumerate(program.fields)}
        self.blocks = program.blocks or [ProcedureBlock(None, None, program.entry),
                                        *(ProcedureBlock(name, None, body) for name, body in program.paragraphs.items())]
        self.files = {name: f"file{i}" for i, name in enumerate(program.files)}
        # Files whose handle is an Rc<RefCell<..>>: EXTERNAL, GLOBAL with
        # contained programs, inherited GLOBAL, and every file of a program
        # with USE GLOBAL (its alias runs the procedure with the same files).
        self.shared_files = {name for name, spec in program.files.items()
                             if spec.external or spec.global_owner or getattr(program, "global_uses", None)
                             or (spec.is_global and getattr(program, "nested", None))}
        self.reports = {name: f"report{i}" for i, name in enumerate(getattr(program, "reports", {}))}
        # The report whose ReportEvent is being answered: its counters are
        # the event's arguments while the report is out of the program.
        self.report_context = None
        self.lines = []
        self.mapping = []
        self.indent = 0
        self.counter = 0
        self.variable_groups = {}
        self.variable_dimensions = {}
        for field in program.fields.values():
            if not field.depending:
                continue
            dim = len(field.dimensions) - 1
            for leaf in program.fields.values():
                if leaf.name == field.name or leaf.name.startswith(field.name + "."):
                    self.variable_dimensions[leaf.name] = (field, dim)
            parent = field.parent
            while parent:
                self.variable_groups[parent] = field
                parent = program.fields[parent].parent

    def write(self, text=""):
        self.lines.append("    " * self.indent + text)

    def unique(self):
        self.counter += 1
        return f"temp{self.counter}"

    def kind(self, e):
        if e.op == "function":
            name, args = e.args
            result = self.program_functions[name][1]
            if result == "args":
                kinds = {"text" if self.kind(a) in {"text", "edited"} else self.kind(a) for a in args}
                if len(kinds) != 1:
                    raise CobolError(f"FUNCTION {name}: arguments numériques et alphanumériques mêlés non pris en charge")
                return kinds.pop()
            return result
        if e.op == "var":
            return "text" if e.args[0].start is not None else self.program.fields[e.args[0].name].kind
        if e.op in {"number", "text"}:
            return e.op
        if e.op in {"all", "refmod"}:
            return "text"
        if e.op.startswith("cmp") or e.op in {"and", "or", "not", "condition", "bool", "numeric_class", "switch", "user_class", "alpha_class"}:
            return "bool"
        return "number"

    def reference(self, ref, active=True):
        if isinstance(ref, str):
            ref = DataRef(ref)
        result = f"self.{self.names[ref.name]}"
        if ref.name in self.variable_groups and active:
            f = self.variable_groups[ref.name]
            prefix = self.program.fields[ref.name].size - f.size * f.occurs
            result += f".active_size(&self.{self.names[f.depending]}, {f.occurs_min}, {f.occurs}, {prefix}, {f.size})"
        if ref.name in self.variable_dimensions:
            f, dim = self.variable_dimensions[ref.name]
            result += f".active_count({dim}, &self.{self.names[f.depending]}, {f.occurs_min}, {f.occurs})"
        if ref.indices:
            if any(self.kind(index) != "number" for index in ref.indices):
                raise CobolError("sous-script numérique requis")
            result += f".at(&[{', '.join(self.expression(i) for i in ref.indices)}])"
        if ref.start is not None:
            if self.kind(ref.start) != "number" or (ref.length is not None and self.kind(ref.length) != "number"):
                raise CobolError("position et longueur numériques requises")
            length = f"Some(&({self.expression(ref.length)}))" if ref.length is not None else "None"
            result += f".slice(&({self.expression(ref.start)}), {length})"
        return result

    def record_size(self, record):
        """The record passed to cob_write/cob_rewrite: output_size gives a
        record with OCCURS DEPENDING its current length."""
        if record in self.variable_groups:
            return f"storage_runtime::field_size(&{self.reference(DataRef(record))})"
        return str(self.program.fields[record].size)

    def category(self, f):
        """CB_TREE_CATEGORY of an elementary item."""
        if f.alnum_edit:
            return "ALPHANUMERIC-EDITED"
        if f.kind == "edited":
            return "NUMERIC-EDITED"
        if f.kind == "number":
            return None if f.usage == "INDEX" else "NUMERIC"
        return "ALPHABETIC" if self.is_alphabetic(f) else "ALPHANUMERIC"

    def initialize_replacing(self, ref, with_filler, replacing):
        """output_initialize_one with REPLACING and no DEFAULT: a MOVE of the
        value to each elementary item of a listed category, occurrence by
        occurrence; FILLER only WITH FILLER, REDEFINES below the item skipped."""
        root = self.program.fields[ref.name]
        if ref.start is not None or ref.name in self.variable_groups or ref.name in self.variable_dimensions:
            raise CobolError("INITIALIZE REPLACING d'une sous-chaîne ou d'une table variable non pris en charge")
        values = dict(replacing)
        moves = []
        # The item itself may be a REDEFINES (topfield); those below it are skipped.
        items = [root] if root.picture else [leaf for child in root.children for leaf in leaves(self.program.fields, child)]
        for leaf in items:
            if (leaf.filler and not with_filler) or self.category(leaf) not in values:
                continue
            dims = leaf.dimensions[len(ref.indices):]
            combos = [()]
            for _, count in [(None, d[1]) for d in dims]:
                combos = [c + (n,) for c in combos for n in range(1, count + 1)]
            moves += [(leaf, combo) for combo in combos]
        if len(moves) > 4096:
            raise CobolError("INITIALIZE REPLACING de plus de 4096 occurrences non pris en charge")
        for leaf, combo in moves:
            indices = tuple(ref.indices) + tuple(Expr("number", (str(n),)) for n in combo)
            self.assignment(values[self.category(leaf)], [DataRef(leaf.name, indices)], False, move=True)

    @property
    def register(self):
        """RETURN-CODE of this program: its own, or its container's GLOBAL one."""
        name = next((name for name, field in self.program.fields.items() if getattr(field, "register", False)), None)
        return None if name is None else f"self.{self.names[name]}"

    def exit_code(self):
        """cob_stop_run (RETURN-CODE): the process exit status."""
        if self.register:
            self.write(f"unit.exit_code = {self.register}.integer(\"RETURN-CODE\") as i32;")

    def shared_block(self, name):
        """(root item, block name, initialized here) of an item stored outside
        the program: EXTERNAL (cob_external_addr) or GLOBAL in a program with
        contained programs, which see the same storage."""
        field = self.program.fields[name]
        while field.parent:
            field = self.program.fields[field.parent]
        if getattr(field, "fd_file", None):
            # The records of a FD share its record area, held by the first.
            while field.redefines:
                field = self.program.fields[field.redefines]
            if field.fd_external:
                # cob_external_addr ("<file>_Record", record_max).
                return field.name, f"{field.fd_file.replace('-', '_')}_Record", False
        if field.external:
            return field.name, field.label, False
        owner = getattr(field, "global_owner", None)
        if owner:
            return field.name, f"GLOBAL {owner} {field.label}", False
        if field.is_global and getattr(self.program, "nested", None):
            return field.name, f"GLOBAL {self.program.entry_name} {field.label}", True
        return None

    def external_root(self, name):
        """The item holding `name` when its storage is not initialized here."""
        block = self.shared_block(name)
        return None if block is None or block[2] else block[0]

    def receiver(self, ref):
        """A MOVE receiver (cb_build_move's flag_receiving): output_size takes
        the maximum length of a variable group that contains its own
        DEPENDING ON item, the current length otherwise."""
        f = self.variable_groups.get(ref.name)
        whole = f is not None and ref.start is None and f.depending.startswith(ref.name + ".")
        return self.reference(ref, active=not whole)

    def literal(self, token):
        return Expr("text" if token.string else "number", (token.text,))

    def expression(self, e):
        op, args = e.op, e.args
        if op == "var":
            # An operand of a computation, condition or subscript: invalid
            # numeric data is read like libcob without runtime checks.
            return self.reference(args[0]) + ".operand()"
        if op == "shared":
            return f"{self.shared}.clone()"
        if op == "linage":
            return f"{self.handle(args[0], True)}.linage_counter()"
        if op == "clock":
            return f"runtime::clock_value({quoted(args[0])})"
        if op == "report_counter":
            report, which = args
            if report == self.report_context:
                return f"Value::number(&{'line' if which == 'LINE-COUNTER' else 'page'}_counter.to_string())"
            return f"self.{self.reports[report]}.counter({quoted(which)})"
        if op == "all":
            raise CobolError("ALL littéral limité au MOVE vers texte, groupe ou sous-chaîne")
        if op == "remainder":
            dividend, divisor, scale = args
            return f"({self.expression(dividend)}).remainder_after(&({self.expression(divisor)}), {scale})"
        if op == "bool":
            return str(args[0]).lower()
        if op == "switch":
            number, on = args
            return f"(runtime::switch_on({number}) == {str(on).lower()})"
        if op == "user_class":
            item, members = args
            table = "[" + ", ".join(f"{m}u8" for m in members) + "]"
            return f"({self.expression(item)}).bytes().iter().all(|byte| {table}.contains(byte))"
        if op == "function":
            return self.function(*args)
        if op == "refmod":
            value, start, length = args
            length = f"Some(&({self.expression(length)}))" if length is not None else "None"
            return f"runtime::refmod(&({self.expression(value)}), &({self.expression(start)}), {length})"
        if op == "alpha_class":
            # cob_is_alpha/upper/lower: spaces and letters of the C library's
            # classification; bytes above 127 depend on the locale.
            item, kind = args
            test = {"ALPHABETIC": "is_ascii_alphabetic", "ALPHABETIC-UPPER": "is_ascii_uppercase",
                    "ALPHABETIC-LOWER": "is_ascii_lowercase"}[kind]
            return (f"({self.expression(item)}).bytes().iter().all(|byte| if *byte >= 128 {{ runtime::fail(\"alphabetic test of a non-ASCII byte depends on the locale\") }} "
                    f"else {{ *byte == b' ' || byte.{test}() }})")
        if op == "numeric_class":
            return f"({self.expression(args[0])}).is_numeric()" if args[0].op != "var" else self.reference(args[0].args[0]) + ".is_numeric()"
        if op == "condition":
            ref = args[0]
            condition = self.program.conditions[ref.name]
            value = Expr("var", (DataRef(condition.parent, ref.indices),))
            terms = []
            for low, high in condition.values:
                left, right = self.literal(low), self.literal(high)
                if self.kind(value) != self.kind(left) or self.kind(value) != self.kind(right):
                    raise CobolError("valeurs de niveau 88 de catégorie différente du parent non prises en charge")
                if low == high:
                    terms.append(self.expression(Expr("cmp=", (value, left))))
                else:
                    terms.append(f"({self.expression(Expr('cmp>=', (value, left)))} && {self.expression(Expr('cmp<=', (value, right)))})")
            return "(" + " || ".join(terms) + ")"
        if op == "text":
            return text_value(args[0])
        if op == "number":
            return f"Value::number({quoted(numeric_text(args[0]))})"
        if op in {"unary+", "unary-"}:
            if self.kind(args[0]) != "number":
                raise CobolError("opérateur numérique sur un champ texte")
            result = self.expression(args[0])
            return result if op == "unary+" else f"({result}).neg()"
        if op in {"+", "-", "*", "/", "**"}:
            if any(self.kind(x) != "number" for x in args):
                raise CobolError("arithmétique sur champ texte non prise en charge")
            if op == "**" and args[1].op == "unary-" and args[1].args[0].op == "number":
                # cob_decimal_pow overwrites a negative exponent with the power;
                # cobc shares that decimal constant among uses of the literal.
                raise CobolError("exposant littéral négatif non pris en charge (constante décimale de cobc modifiée par cob_decimal_pow)")
            method = {"+": "plus", "-": "minus", "*": "times", "/": "divide", "**": "power"}[op]
            return f"({self.expression(args[0])}).{method}(&({self.expression(args[1])}))"
        if op in {"and", "or"}:
            return f"({self.expression(args[0])} {'&&' if op == 'and' else '||'} {self.expression(args[1])})"
        if op == "not":
            return f"!({self.expression(args[0])})"
        if op.startswith("cmp"):
            folded = self.folded_comparison(op[3:], *args)
            if folded is not None:
                return str(folded).lower()
            operator = {"=": "==", "<>": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}[op[3:]]
            return f"({self.comparison_order(*args)}) {operator} std::cmp::Ordering::Equal"
        raise CobolError(f"expression inconnue: {op}")

    def function(self, name, args):
        """A call into runtime::intrinsic (libcob intrinsic.c)."""
        textual = name in {"UPPER-CASE", "LOWER-CASE", "REVERSE", "ORD", "NUMVAL", "NUMVAL-C", "LENGTH", "TRIM"}
        values = []
        direction = "0"
        if name == "TRIM" and len(args) == 2:
            args, direction = args[:1], args[1].args[0]
        for a in args:
            if textual:
                if a.op == "var":
                    # The function sees the argument's storage bytes.
                    values.append(f"Value::Bytes(storage_runtime::Operand::of(&{self.reference(a.args[0])}).data)")
                elif a.op == "text":
                    values.append(text_value(a.args[0]))
                elif a.op == "function" and self.kind(a) == "text":
                    values.append(self.expression(a))
                else:
                    raise CobolError(f"FUNCTION {name}: argument alphanumérique attendu")
            else:
                if self.kind(a) not in {"number"} and name not in {"MAX", "MIN", "ORD-MAX", "ORD-MIN"}:
                    raise CobolError(f"FUNCTION {name}: argument numérique attendu")
                if a.op == "all":
                    raise CobolError(f"FUNCTION {name}: argument figuratif non pris en charge")
                values.append(self.expression(a))
        rust = {"INTEGER": "integer", "INTEGER-PART": "integer_part", "FACTORIAL": "factorial",
                "CHAR": "char_of", "ORD": "ord", "UPPER-CASE": "upper_case", "LOWER-CASE": "lower_case",
                "REVERSE": "reverse", "INTEGER-OF-DATE": "integer_of_date", "INTEGER-OF-DAY": "integer_of_day",
                "DATE-OF-INTEGER": "date_of_integer", "DAY-OF-INTEGER": "day_of_integer",
                "SQRT": "sqrt_of", "LOG": "log", "LOG10": "log10", "EXP": "exp_of", "SIN": "sin",
                "COS": "cos", "TAN": "tan", "ASIN": "asin", "ACOS": "acos", "ATAN": "atan_of"}
        listed = {"SUM": "sum", "MEAN": "mean", "MEDIAN": "median", "MIDRANGE": "midrange", "RANGE": "range",
                  "VARIANCE": "variance", "ORD-MAX": "ord_max", "ORD-MIN": "ord_min", "MAX": "max", "MIN": "min",
                  "PRESENT-VALUE": "present_value", "STANDARD-DEVIATION": "standard_deviation"}
        if name == "CURRENT-DATE":
            return "runtime::intrinsic::current_date()"
        if name == "RANDOM":
            return f"runtime::intrinsic::random({'Some(&' + values[0] + ')' if values else 'None'})"
        if name in {"PI", "E"}:
            return f"runtime::intrinsic::{'pi_value' if name == 'PI' else 'e'}()"
        if name in rust:
            return f"runtime::intrinsic::{rust[name]}(&{values[0]})"
        if name in listed:
            return f"runtime::intrinsic::{listed[name]}(&[{', '.join(values)}])"
        if name in {"MOD", "REM"}:
            return f"runtime::intrinsic::mod_or_rem(&{values[0]}, &{values[1]}, {str(name == 'REM').lower()})"
        if name == "ANNUITY":
            return f"runtime::intrinsic::annuity(&{values[0]}, &{values[1]})"
        if name in {"NUMVAL", "NUMVAL-C"}:
            currency = f"Some({values[1]}.bytes())" if len(values) > 1 else "None"
            return f"runtime::intrinsic::numval(&{values[0]}, {str(name == 'NUMVAL-C').lower()}, {currency})"
        if name == "LENGTH":
            return f"runtime::intrinsic::length(&{values[0]})"
        if name == "TRIM":
            return f"runtime::intrinsic::trim(&{values[0]}, {direction})"
        raise CobolError(f"FUNCTION {name} non prise en charge")

    def occurs(self, table):
        """output_occurs: the maximum, or the current ODO value."""
        field = self.program.fields[table]
        if field.depending:
            return f"{self.reference(DataRef(field.depending))}.integer(\"OCCURS DEPENDING\")"
        return str(field.occurs)

    def folded_comparison(self, op, left, right):
        """cobc's compare_field_literal constant folding (tree.c), or None.

        A DISPLAY numeric or numeric-edited item compared with an all-digit
        literal having more decimals, or more integer digits than the item's
        size minus scale, is never equal; for a numeric item cobc also makes
        > and >= FALSE and < and <= TRUE, whatever the literal's sign.
        Alphanumeric items fold only when the literal is longer than the item,
        where a runtime comparison gives the same result.
        Two alphanumeric literals fold for = and <> by their bytes, space
        padded, even under a PROGRAM COLLATING SEQUENCE.
        """
        if (left.op == "text" and right.op == "text" and op in {"=", "<>"}
                and not left.figurative_space and not right.figurative_space):
            size = max(len(left.args[0]), len(right.args[0]))
            equal = left.args[0].ljust(size) == right.args[0].ljust(size)
            return equal if op == "=" else not equal
        for swapped, field_expr, literal in ((True, right, left), (False, left, right)):
            if field_expr.op != "var" or field_expr.args[0].start is not None:
                continue
            field = self.program.fields[field_expr.args[0].name]
            if field.usage != "DISPLAY" or field.kind not in {"number", "edited"}:
                continue
            if literal.op in {"unary+", "unary-"} and literal.args[0].op == "number":
                literal = literal.args[0]
            if literal.op == "number":
                text = literal.args[0]
                data, scale = text.replace(".", ""), len(text.split(".")[1]) if "." in text else 0
            elif literal.op == "text":
                # The digit test reads the whole literal, trailing spaces included.
                data, scale = literal.args[0], 0
            else:
                continue
            if field.scale < 0 or not data or not data.isascii() or not data.isdigit():
                return None
            if set(data) == {"0"}:
                return None
            digits = data.lstrip("0")
            count = len(digits)
            while scale > 0 and digits and digits[-1] == "0":
                digits, scale, count = digits[:-1], scale - 1, count - 1
            if scale > 0 and field.scale < scale and op in {"=", "<>"}:
                return op == "<>"
            if swapped:
                op = {">": "<", ">=": "<=", "<": ">", "<=": ">="}.get(op, op)
            if count - scale > 0 and field.size - field.scale >= 0 and count - scale > field.size - field.scale:
                if op in {"=", "<>"}:
                    return op == "<>"
                if field.kind == "number":
                    return op in {"<", "<="}
            return None
        return None

    @staticmethod
    def is_alphabetic(field):
        """PIC A only (with B for alphabetic-edited); mixed with X or 9 it is alphanumeric."""
        picture = re.sub(r"\(\d+\)", "", field.picture.upper())
        return bool(picture) and set(picture) <= {"A", "B"} and "A" in picture

    def numeric_comparison(self, left, right):
        """The libcob routine cobc chooses (cb_build_cond_default,
        cb_check_num_cond, cb_build_optim_cond, cob_numeric_cmp): they agree
        on valid data but read invalid DISPLAY data as a decimal or as an
        integer."""
        def field(e):
            if e.op == "var" and e.args[0].start is None:
                f = self.program.fields[e.args[0].name]
                return f if f.kind == "number" else None
            return None

        def literal(e):
            e = e.args[0] if e.op in {"unary+", "unary-"} else e
            return e.args[0] if e.op == "number" else None

        def fits_long_long(e, f):  # cb_fits_long_long
            if f is not None:
                usage = self.storage_usage(f)
                if f.usage == "INDEX":
                    return True
                if usage in {"Binary", "Native", "Register"}:
                    return f.scale <= 0 and f.size <= 8
                if usage == "Packed":
                    return f.scale <= 0 and f.digits < 19
                return usage == "Display" and f.scale <= 0 and f.size < 19
            text = literal(e)
            if text is None or "." in text:
                return False
            digits = text.lstrip("+-").lstrip("0")
            return len(digits) < 19 or (len(digits) == 19 and digits <= (
                "9223372036854775808" if e.op == "unary-" else "9223372036854775807"))

        def shape(e, f):
            if f is not None:
                return f.digits, f.scale
            text = literal(e)
            if text is None:
                return None
            return len(text.lstrip("+-").replace(".", "")), len(text.split(".")[1]) if "." in text else 0

        def operand(e, integer):
            if integer and field(e) is not None:
                return f"{self.reference(e.args[0])}.operand_integer()"
            return self.expression(e)

        def compare(left_integer, right_integer):
            return f"({operand(left, left_integer)}).compare(&({operand(right, right_integer)}))"
        if any(e.op not in {"var", "number"} and literal(e) is None for e in (left, right)):
            return compare(False, False)  # cob_decimal_cmp
        lf, rf = field(left), field(right)
        if not getattr(self.program, "debugging_mode", False):
            if (lf is not None and rf is not None and lf.usage == rf.usage == "DISPLAY" and not lf.signed and not rf.signed
                    and (lf.digits, lf.scale) == (rf.digits, rf.scale)):
                data = [f"storage_runtime::Operand::of(&{self.reference(e.args[0])}).data" for e in (left, right)]
                return f"runtime::memcmp(&{data[0]}, &{data[1]})"
            if fits_long_long(right, rf):
                if lf is None or lf.scale or self.storage_usage(lf) != "Display":
                    return compare(False, True)  # cob_cmp_llint, cob_cmp_packed, cob_cmp_s32…
                if not lf.sign_leading and not lf.sign_separate and fits_long_long(left, lf):
                    return compare(True, True)  # cob_cmp_numdisp
                return compare(False, True)
        shapes = shape(left, lf), shape(right, rf)
        integer = (None not in shapes and shapes[0][1] == shapes[1][1]
                   and shapes[0][0] < 19 and shapes[1][0] < 19)
        return compare(integer, integer)  # cob_numeric_cmp

    def comparison_order(self, left, right):
        # A numeric-edited item is not numeric for libcob's cob_cmp: it
        # compares as alphanumeric, by its edited bytes.
        kinds = tuple("text" if kind == "edited" else kind for kind in (self.kind(left), self.kind(right)))
        # A number against SPACE is cob_cmp_all with the figurative, like ALL " ".
        if "number" in kinds:
            left, right = (Expr("all", (" ",)) if e.op == "text" and e.figurative_space else e for e in (left, right))
        if left.op == "all" or right.op == "all":
            # cob_cmp_all: each position against the repeated figurative.
            other, figurative = (right, left) if left.op == "all" else (left, right)
            raw_number = (other.op == "var" and other.args[0].start is None and self.kind(other) == "number"
                          and self.program.fields[other.args[0].name].usage == "DISPLAY"
                          and not self.program.fields[other.args[0].name].signed
                          and self.program.fields[other.args[0].name].scale >= 0
                          and figurative.args[0] != "0")
            if other.op == "all" or (self.kind(other) not in {"text", "edited"} and not raw_number):
                raise CobolError("comparaison avec ALL/figurative limitée aux champs alphanumériques")
            # cob_cmp_all on an unsigned DISPLAY item compares its digit bytes.
            value = (f"Value::Bytes(storage_runtime::Operand::of(&{self.reference(other.args[0])}).data)"
                     if raw_number else self.expression(other))
            pattern = f"Value::Bytes({byte_pattern(figurative.args[0])}.iter().cycle().take(({value}).text_size()).copied().collect())"
            result = f"({value}).compare(&{pattern})"
            return result if left is other else result + ".reverse()"
        if kinds == ("number", "number"):
            return self.numeric_comparison(left, right)
        if kinds[0] == kinds[1]:
            return f"({self.expression(left)}).compare(&({self.expression(right)}))"
        if set(kinds) != {"number", "text"}:
            raise CobolError("comparaison entre catégories non prise en charge")
        number, text = (left, right) if kinds[0] == "number" else (right, left)
        # cob_cmp compares a PIC A item with a number like PIC X (checked
        # against cobc 3.2, default and cobol85).
        # GnuCOBOL treats an empty alphanumeric literal as one SPACE.
        text_value = 'Value::text(" ")' if text.op == "text" and not text.args[0] else self.expression(text)
        if number.figurative_zero:
            result = f"({text_value}).compare_zero()"
            return result + ".reverse()" if kinds[0] == "number" else result
        if number.op == "var":
            ref = number.args[0]
            descriptor = self.program.fields[ref.name]
            if descriptor.usage == "INDEX":
                raise CobolError("comparaison mixte d'index non prise en charge")
            # cob_cmp: cob_cmp_alnum of the item's digits (COB_FIELD_DATA, an
            # overpunched sign removed) with the literal, unless
            # compare_field_literal folded the condition (folded_comparison).
            number_value = self.reference(ref) + ".comparison_text()"
        elif number.op == "number":
            number_value = f"Value::text({quoted(number.args[0].replace('.', ''))})"
        else:
            raise CobolError("comparaison mixte limitée aux champs numériques, littéraux non signés et ZERO; signes explicites et calculs non modélisés")
        a, b = (number_value, text_value) if kinds[0] == "number" else (text_value, number_value)
        return f"({a}).compare(&({b}))"

    def move_literal_digits(self, expr):
        if expr.op == "number" and not expr.figurative_zero:
            return expr.args[0].replace(".", "")
        if expr.op in {"unary+", "unary-"} and expr.args[0].op == "number":
            return self.move_literal_digits(expr.args[0])
        return None

    def assignment(self, expr, targets, rounded, move=False):
        targets = [DataRef(r) if isinstance(r, str) else r for r in targets]
        if expr.op == "report_counter" and any(self.program.fields[r.name].kind not in {"number", "edited"} or r.start is not None
                                               for r in targets):
            raise CobolError(f"{expr.args[1]} (entier binaire non signé) vers une donnée non numérique non pris en charge")
        source_kind = self.kind(expr)
        conversions = []
        for ref in targets:
            conversions.append(None)
            field = self.program.fields[ref.name]
            destination = "text" if ref.start is not None else field.kind
            if ref.start is None and self.is_alphabetic(field) and source_kind in {"number", "edited"}:
                raise CobolError("MOVE numérique vers alphabétique (PIC A) invalide, comme pour GnuCOBOL")
            if move and self.move_copy(expr, ref):
                conversions[-1] = "copy"
                continue
            if move and source_kind == "text" and destination in {"number", "edited"}:
                if expr.figurative_space:
                    raise CobolError("MOVE de la constante figurative SPACE vers nombre ou champ édité non pris en charge")
                if destination == "number" and field.usage == "INDEX":
                    raise CobolError("MOVE texte vers index non pris en charge")
                if destination == "number" and expr.op == "all" and expr.memset:
                    # cb_build_move_high / cb_build_move_low: memset of the item.
                    conversions[-1] = ("bytes", expr.args[0].encode("latin-1") * field.size)
                    continue
                # A function result or its reference modification is an
                # alphanumeric temporary: cob_move as from an item.
                if destination == "number" and expr.op not in {"var", "refmod", "function"}:
                    usage = self.storage_usage(field)
                    if usage in {"Display", "SignLeading"} and field.scale == 0 and expr.op == "text":
                        # cb_build_move_literal: the literal's bytes, right
                        # aligned and zero filled, copied at compile time.
                        data = expr.args[0].encode("latin-1")
                        data = data[len(data) - field.size:] if len(data) >= field.size else b"0" * (field.size - len(data)) + data
                        if field.blank_zero and set(data) == {ord("0")}:
                            data = b" " * field.size
                        conversions[-1] = ("bytes", data)
                        continue
                    if not usage.startswith(("Display", "Sign")) or expr.op != "text":
                        raise CobolError("MOVE littéral texte vers nombre binaire ou packé non pris en charge; optimisations natives de cobc")
                    # Otherwise cob_move, as from an alphanumeric item.
                    conversions[-1] = "parsed_text"
                    continue
                source_ref = expr.args[0] if expr.op == "var" else None
                raw_group = (source_ref is not None and source_ref.start is None and
                             not self.program.fields[source_ref.name].picture)
                conversions[-1] = "raw_text" if raw_group else "parsed_text"
                continue
            edited_text = ref.start is None and bool(field.alnum_edit)
            if edited_text and expr.op == "all" and expr.literal_all:
                # cb_build_move_literal: memset/memcpy of the repeated literal,
                # without editing; cob_move (editing) beyond 128 bytes.
                pattern = byte_pattern_bytes(expr.args[0])
                if field.size > 128 and len(set(pattern)) > 1:
                    raise CobolError("MOVE ALL vers alphanumérique édité de plus de 128 octets non pris en charge")
                conversions[-1] = ("bytes", bytes(pattern[i % len(pattern)] for i in range(field.size)))
                continue
            if edited_text and expr.op == "var" and expr.args[0].start is None and not self.program.fields[expr.args[0].name].picture:
                # A group sender is a group move: bytes are copied unedited.
                conversions[-1] = "raw_text"
                continue
            if expr.op == "all":
                if not move or destination != "text":
                    raise CobolError("ALL littéral limité au MOVE vers texte, groupe ou sous-chaîne")
                conversions[-1] = "all"
                continue
            if move and destination == "text" and source_kind == "number":
                group = not field.picture and ref.start is None
                if expr.figurative_zero:
                    conversion = "zero"
                elif self.move_literal_digits(expr) is not None:
                    conversion = "literal"
                elif expr.op == "var":
                    source_field = self.program.fields[expr.args[0].name]
                    if not group and source_field.scale > 0:
                        raise CobolError("MOVE numérique non entier vers PIC X ou sous-chaîne invalide; utiliser un groupe pour copier le stockage brut")
                    conversion = "group" if group else "integer"
                else:
                    raise CobolError("MOVE numérique vers texte requiert un champ ou un littéral simple")
                conversions[-1] = conversion
                continue
            if destination == "edited" and source_kind == "number":
                continue
            if move and destination in {"number", "edited"} and source_kind == "edited" and expr.op == "var":
                if field.usage == "INDEX":
                    raise CobolError("MOVE édité vers index non pris en charge")
                conversions[-1] = "deedit"
                continue
            if destination == "text" and source_kind == "edited":
                continue
            if destination == "edited" or destination != source_kind:
                raise CobolError(f"conversion implicite numérique/texte non prise en charge: {ref.name}")
        negative_zero = []
        if (move and expr.op == "unary-" and expr.args[0].op == "number"
                and not expr.args[0].args[0].replace(".", "").strip("0")):
            # cobc keeps the literal's sign: a signed DISPLAY receiver gets a
            # negative zero; packed and binary receivers get a plain zero.
            for ref in targets:
                field = self.program.fields[ref.name]
                if ref.start is None and field.kind == "number" and field.signed and field.usage == "DISPLAY":
                    negative_zero.append(ref)
        # A numeric MOVE truncates instead of raising SIZE ERROR. Index senders
        # keep the stricter assignment: their native transfer is not modelled.
        truncating = (move and source_kind == "number" and not
                      (expr.op == "var" and self.program.fields[expr.args[0].name].usage == "INDEX"))
        temp = self.unique()
        # COBOL resolves a variable's source address once, but each receiver reads
        # that storage again. This matters when group/redefine receivers overlap it.
        if expr.op != "all":
            source = self.reference(expr.args[0]) + ".clone()" if expr.op == "var" else self.expression(expr)
            self.write(f"let {temp} = {source};")
        for ref, conversion in zip(targets, conversions):
            if isinstance(conversion, tuple):
                self.write(f"{self.receiver(ref)}.assign_text_move(&Value::Bytes(vec![{', '.join(str(b) for b in conversion[1])}]), true);")
            elif conversion == "copy":
                self.write(f"{self.receiver(ref)}.assign_text_move(&Value::Bytes(storage_runtime::Operand::of(&{temp}).data), true);")
            elif conversion == "deedit":
                self.write(f"{self.receiver(ref)}.move_deedited(&{temp});")
            elif conversion in {"raw_text", "parsed_text"}:
                self.write(f"{self.receiver(ref)}.assign_text_move(&{temp}, {str(conversion == 'raw_text').lower()});")
            elif conversion == "all":
                receiver = self.unique()
                self.write(f"let mut {receiver} = {self.receiver(ref)}.clone();")
                self.write(f"let all = Value::Bytes({byte_pattern(expr.args[0])}.iter().cycle().take({receiver}.text_size()).copied().collect());")
                self.write(f"{receiver}.assign(&all, false);")
            elif conversion == "zero":
                receiver = self.unique()
                self.write(f"let mut {receiver} = {self.receiver(ref)}.clone();")
                self.write(f"let zeros = Value::Bytes(vec![b'0'; {receiver}.text_size()]);")
                self.write(f"{receiver}.assign(&zeros, false);")
            else:
                value = (f"{temp}.numeric_move_text({str(conversion == 'group').lower()})"
                         if conversion in {"group", "integer"} else
                         f"Value::text({quoted(self.move_literal_digits(expr))})" if conversion == "literal" else temp)
                field = self.program.fields[ref.name]
                if conversion is None and truncating and ref.start is None and field.kind == "edited":
                    self.write(f"{self.receiver(ref)}.move_edited(&{value});")
                elif conversion is None and truncating and ref.start is None and field.kind == "number":
                    method = "move_number"
                    if self.storage_usage(field) == "Packed":
                        self.check_packed_literal_move(expr, field)
                        if (expr.op == "var" and
                                self.storage_usage(self.program.fields[expr.args[0].name]) in {"Binary", "Native", "Register"}):
                            method = "move_binary_to_packed"
                    self.write(f"{self.receiver(ref)}.{method}(&{value});")
                else:
                    self.write(f"{self.receiver(ref)}.assign(&{value}, {str(rounded).lower()});")
            if ref in negative_zero:
                self.write(f"{self.receiver(ref)}.negative_zero();")

    def move_copy(self, expr, ref):
        """cb_build_move_field: a numeric sender at least as long as its
        receiver is copied byte for byte (cb_build_move_copy), without
        reading its digits, to a numeric item of the same description or to
        an alphanumeric item when it is unsigned DISPLAY."""
        if expr.op != "var" or expr.args[0].start is not None or ref.start is not None:
            return False
        src, dst = self.program.fields[expr.args[0].name], self.program.fields[ref.name]
        def variable(f):  # cb_field_variable_size
            return bool(f.depending) or any(variable(self.program.fields[c]) for c in f.children)
        if src.kind != "number" or src.size < dst.size or variable(src) or variable(dst):
            return False
        if dst.kind == "number":
            return (src.usage != "INDEX" and self.storage_usage(src) == self.storage_usage(dst)
                    and (src.size, src.digits, src.scale, src.signed) == (dst.size, dst.digits, dst.scale, dst.signed))
        alphanumeric = (dst.kind == "text" and not dst.alnum_edit and not dst.justified
                        and not (dst.picture and self.is_alphabetic(dst)))
        # validate_move refuses a non-integer sender to an elementary item.
        return (alphanumeric and self.storage_usage(src) == "Display" and not src.signed
                and (src.scale <= 0 or not dst.picture))

    def check_packed_literal_move(self, expr, field):
        """cobc stores a small integer literal with cob_set_packed_int, which
        fills every physical nibble. Refuse a digit landing in the pad nibble."""
        digits = self.move_literal_digits(expr)
        if digits is None:
            return
        number = expr if expr.op == "number" else expr.args[0]
        if "." in number.args[0] or len(digits) + field.scale > 9 or field.digits % 2:
            return
        if (int(digits) * 10 ** field.scale // 10 ** field.digits) % 10:
            raise CobolError("MOVE littéral vers COMP-3 à nombre pair de chiffres remplissant le quartet "
                             "de tête natif non pris en charge")

    def checked_expression(self, expr):
        if self.kind(expr) != "number":
            raise CobolError("calcul avec SIZE ERROR requiert des nombres")
        op, args = expr.op, expr.args
        if op == "shared":
            return f"{self.shared}.clone()"
        if op in {"+", "-", "*", "/", "**"}:
            if op == "**" and args[1].op == "unary-" and args[1].args[0].op == "number":
                raise CobolError("exposant littéral négatif non pris en charge (constante décimale de cobc modifiée par cob_decimal_pow)")
            left, right = (f"({self.checked_expression(arg)}?)" for arg in args)
            if op == "/":
                return f"{left}.checked_divide(&{right})"
            method = {"+": "plus", "-": "minus", "*": "times", "**": "power"}[op]
            return f"Ok::<Value, runtime::SizeError>({left}.{method}(&{right}))"
        if op == "remainder":
            dividend, divisor, scale = args
            return (f"({self.checked_expression(dividend)}?).checked_remainder(&({self.checked_expression(divisor)}?), {scale})")
        if op in {"unary+", "unary-"}:
            value = self.checked_expression(args[0])
            return value if op == "unary+" else f"Ok::<Value, runtime::SizeError>(({value}?).neg())"
        return f"Ok::<Value, runtime::SizeError>({self.expression(expr)})"

    def file_kind(self, file_name):
        organization = self.program.files[file_name].organization
        return {"RELATIVE": "RelativeFile", "INDEXED": "IndexedFile", "SORT": "SortFile"}.get(organization, "CobolFile")

    def file_registry(self, file_name):
        """The run unit's name of a file shared with other programs."""
        spec = self.program.files[file_name]
        if spec.external:
            return f"EXTERNAL {file_name}"
        if spec.global_owner:
            return f"GLOBAL {spec.global_owner} {file_name}"
        if spec.is_global and getattr(self.program, "nested", None):
            return f"GLOBAL {self.program.entry_name} {file_name}"
        return None

    def handle(self, file_name, read=False):
        """The file's runtime object, borrowed when it is shared."""
        rust = f"self.{self.files[file_name]}"
        if file_name not in self.shared_files:
            return rust
        return f"{rust}.{'borrow' if read else 'borrow_mut'}()"

    def depending(self, file_name, mutable):
        name = self.program.files[file_name].depending
        return f"Some(&{'mut ' if mutable else ''}self.{self.names[name]})" if name else "None"

    def relative_key(self, file_name, mutable):
        key = self.program.files[file_name].relative_key
        if key is None:
            return "None"
        return f"Some(&{'mut ' if mutable else ''}self.{self.names[key]})"

    @staticmethod
    def assign_literal(spec):
        # ASSIGN data-name: the name is read from the item before each OPEN.
        return quoted(spec.path.text) if spec.path else '""'

    def assign_name(self, file_name):
        """cob_pre_open: an ASSIGN data item gives the file name at each OPEN."""
        key = self.program.files[file_name].assign_field
        if key:
            name = self.unique()
            # cob_field_to_string reads the item's storage bytes, even numeric.
            self.write(f"let {name} = storage_runtime::Operand::of(&{self.reference(DataRef(key))}).data;")
            self.write(f"{self.handle(file_name)}.assign(&{name});")

    def file_status(self, file_name, status, eof_handled=False):
        name = self.program.files[file_name].status
        destination = f"Some(&mut self.{self.names[name]})" if name else "None"
        # The applicable USE procedure, chosen by file or by its last OPEN mode.
        handlers = getattr(self, "io_handlers", None)
        if handlers is None:
            handler = "None"
        elif handlers[0] == "file":
            handler = f"Some({handlers[1]})"
        else:
            cases = " ".join(f"{quoted(mode)} => Some({target}),"
                             for mode, target in sorted(handlers[1].items()))
            handler = f"match {self.handle(file_name, True)}.last_open_mode() {{ {cases} _ => None }}"
        self.write(f"let handler: Option<usize> = {handler};")
        invalid = str(getattr(self, "io_invalid", False)).lower()
        result = "let eop = " if getattr(self, "io_eop", None) else ""
        name = f"&|| {self.handle(file_name, True)}.error_name()" if self.program.files[file_name].organization != "SORT" else "&|| Vec::new()"
        self.write(f"{result}file_runtime::file_status({status}, {destination}, {str(eof_handled).lower()}, {invalid}, handler.is_some(), {name});")

    def linage_values(self, file_name):
        """The LINAGE phrases as cob_get_int reads them at OPEN and WRITE."""
        linage = self.program.files[file_name].linage
        if not linage:
            return
        values = []
        for part in ("lines", "footing", "top", "bottom"):
            value = linage.get(part)
            if value is None:
                values.append("None")
            elif value[0] == "literal":
                values.append(f"Some({value[1]})")
            else:
                values.append(f"Some(self.{self.names[value[1]]}.snapshot().count())")
        self.write(f"{self.handle(file_name)}.linage_values([{', '.join(values)}]);")

    def statement(self, stmt):
        op, a = stmt.op, stmt.args
        if op == "set_index":
            refs, mode, expr = a
            if self.kind(expr) != "number":
                raise CobolError("SET d'index requiert un entier")
            for ref in refs:
                # SET ... UP/DOWN evaluates its operand for each receiver.
                # An earlier index receiver can itself be that operand.
                temp = self.unique()
                self.write(f"let {temp} = {self.expression(expr)};")
                self.write(f'{temp}.integer("SET index");')
                name = self.reference(ref)
                source = temp if mode == "to" else f"{name}.{'plus' if mode == 'up' else 'minus'}(&{temp})"
                self.write(f"{name}.assign(&{source}, false);")
        elif op == "set_condition":
            for ref in a[0]:
                condition = self.program.conditions[ref.name]
                token = condition.values[0][0] if a[1] else condition.false_value
                if token is None:
                    raise CobolError("SET TO FALSE requiert WHEN SET TO FALSE dans le niveau 88")
                self.assignment(self.literal(token), [DataRef(condition.parent, ref.indices)], False)
        elif op == "open":
            for mode, name in a[0]:
                self.linage_values(name)
                self.assign_name(name)
                self.write(f"let status = {self.handle(name)}.open({quoted(mode)});")
                self.file_status(name, "status")
        elif op == "close":
            for name, mode in a[0]:
                if mode in {"reel", "no_rewind"}:
                    self.write(f"let status = {self.handle(name)}.close_unit({str(mode == 'no_rewind').lower()});")
                else:
                    self.write(f"let status = {self.handle(name)}.close({str(mode == 'lock').lower()});")
                self.file_status(name, "status")
        elif op == "rewrite":
            name, record, value, _, _ = a
            if value:
                self.assignment(value, [record], False)
            organization = self.program.files[name].organization
            key = f"{self.relative_key(name, False)}, " if organization == "RELATIVE" else ""
            size = self.record_size(record)
            self.write(f"let status = {self.handle(name)}.rewrite(&self.{self.files[name]}_area, {size}, {key}{self.depending(name, False)});")
            self.file_status(name, "status")
        elif op == "delete":
            name = a[0]
            if self.program.files[name].organization == "INDEXED":
                self.write(f"let status = {self.handle(name)}.delete(&self.{self.files[name]}_area);")
            else:
                self.write(f"let status = {self.handle(name)}.delete({self.relative_key(name, False)});")
            self.file_status(name, "status")
        elif op == "start":
            name, index, condition, _, _ = a
            if index is not None:
                key = "file_runtime::NO_KEY" if index[0] < 0 else index[0]
                self.write(f"let status = {self.handle(name)}.start(file_runtime::StartCondition::{condition}, {key}, {index[1]}, &self.{self.files[name]}_area);")
            else:
                key = self.names[self.program.files[name].relative_key]
                self.write(f"let status = {self.handle(name)}.start(file_runtime::StartCondition::{condition}, &self.{key});")
            self.file_status(name, "status")
        elif op == "write":
            name, record, value, advancing, _, _ = a
            if value:
                self.assignment(value, [record], False)
            control = "None"
            if advancing is not None:
                direction, count = advancing
                variant = direction.title() + ("Page" if count is None else "Lines")
                if isinstance(count, Expr):
                    # cb_build_write_advancing_lines: cob_get_int of the item.
                    argument = f"(file_runtime::advance_lines(&{self.expression(count)}))"
                else:
                    argument = "" if count is None else f"({count})"
                control = f"Some(file_runtime::Advance::{variant}{argument})"
            self.linage_values(name)
            if self.program.files[name].organization == "RELATIVE":
                control = self.relative_key(name, True)
            size = self.record_size(record)
            if self.program.files[name].organization == "INDEXED":
                if advancing is not None:
                    raise CobolError("WRITE ADVANCING sur un fichier INDEXED")
                self.write(f"let status = {self.handle(name)}.write(&self.{self.files[name]}_area, {size}, {self.depending(name, False)});")
            elif self.program.files[name].organization in {"SEQUENTIAL", "LINE SEQUENTIAL"} and getattr(self, "io_eop", None):
                # cb_emit_write: check_eop only with an AT END-OF-PAGE phrase.
                check = str(self.io_eop[0]).lower()
                self.write(f"let status = {self.handle(name)}.write_checked(&self.{self.files[name]}_area, {size}, {control}, {self.depending(name, False)}, {check});")
            else:
                self.write(f"let status = {self.handle(name)}.write(&self.{self.files[name]}_area, {size}, {control}, {self.depending(name, False)});")
            self.file_status(name, "status")
        elif op == "display":
            values = []
            for e in a[0]:
                if e.op == "all":
                    # DISPLAY shows an ALL literal or a figurative constant once.
                    values.append("Value::Bytes(vec![" + ", ".join(str(ord(c)) for c in e.args[0]) + "])")
                    continue
                if e.op == "linage":
                    values.append(f"{self.handle(e.args[0], True)}.linage_display()")
                    continue
                if e.op == "report_counter":
                    values.append(f"self.{self.reports[e.args[0]]}.counter_display({quoted(e.args[1])})")
                    continue
                if e.op in {"function", "refmod"} and self.kind(e) == "text":
                    # cob_display of the alphanumeric result field, as stored.
                    values.append(f"Value::Bytes(({self.expression(e)}).bytes())")
                    continue
                if e.op == "function":
                    raise CobolError(f"DISPLAY de FUNCTION {e.args[0]} numérique non pris en charge")
                if e.op in {"unary-", "unary+"} and e.args[0].op == "number":
                    # A signed numeric literal is shown with its sign.
                    literal = ("-" if e.op == "unary-" else "+") + e.args[0].args[0]
                    if getattr(self.program, "decimal_comma", False):
                        literal = literal.replace(".", ",")
                    values.append(f"Value::text({quoted(literal)})")
                    continue
                if e.op not in {"text", "number", "var"}:
                    raise CobolError("DISPLAY accepte uniquement champs et littéraux simples")
                # Preserve the spelling of numeric literals (leading zeros, trailing fractional zeros).
                if e.op == "number":
                    literal = e.args[0].replace(".", ",") if getattr(self.program, "decimal_comma", False) else e.args[0]
                    values.append(f"Value::text({quoted(literal)})")
                elif (e.op == "var" and e.args[0].start is None
                      and self.storage_usage(self.program.fields[e.args[0].name]) in {"Native", "Register", "Display"}):
                    # cob_print_realbin reads the stored integer of the item
                    # itself; an invalid DISPLAY item is shown as it is stored.
                    values.append(f"{self.reference(e.args[0])}.clone()")
                elif e.op == "var":
                    # DISPLAY moves the item as it is stored (no invalid-data reading).
                    values.append(f"{self.reference(e.args[0])}.snapshot()")
                else:
                    values.append(self.expression(e))
            function = "runtime::display_error" if len(a) > 2 and a[2] == "stderr" else "display"
            self.write(f"{function}(&[{', '.join(values)}], {str(a[1]).lower()});")
        elif op == "table_sort":
            # cob_table_sort_init_key per key, then cob_table_sort of the
            # active occurrences.
            table, keys = a
            entries = ", ".join(f"({offset}, {self.program.fields[name].size}, {self.storage_kind(self.program.fields[name])}, "
                                f"{str(self.program.fields[name].kind == 'number').lower()}, {str(descending).lower()})"
                                for descending, name, offset in keys)
            self.write(f"storage_runtime::table_sort(&{self.reference(DataRef(table))}, &[{entries}]);")
        elif op in {"assign", "move"}:
            self.assignment(*a, move=op == "move")
        elif op == "compute":
            shared, items = a
            opened = 0
            if shared is not None:
                if self.kind(shared) != "number":
                    raise CobolError("calcul arithmétique requiert des nombres")
                self.shared = self.unique()
                if divides(shared):
                    self.write(f"if let Some({self.shared}) = runtime::decimal_nan(|| {self.expression(shared)}) {{")
                    self.indent += 1
                    opened += 1
                else:
                    self.write(f"let {self.shared} = {self.expression(shared)};")
            # Each receiver is computed and stored in turn: its subscripts and
            # a single re-read operand see the receivers already stored.
            for ref, expr, rounded in items:
                if expr.op == "p_int_add":
                    _, operand, positions, negate = expr.args
                    delta, shared = self.unique(), getattr(self, "shared", None)
                    self.write(f"if let Some({delta}) = runtime::cob_add_int_operand(&{self.expression(operand)}, {positions}, {str(negate).lower()}) {{")
                    self.indent += 1
                    self.shared = delta
                    self.assignment(Expr("+", (Expr("var", (ref,)), Expr("shared", ()))), [ref], rounded)
                    self.shared = shared
                    self.indent -= 1
                    self.write("}")
                    continue
                if divides(expr):
                    # A division by zero leaves this receiver unchanged.
                    value, shared = self.unique(), getattr(self, "shared", None)
                    self.write(f"if let Some({value}) = runtime::decimal_nan(|| {self.expression(expr)}) {{")
                    self.indent += 1
                    self.shared = value
                    self.assignment(Expr("shared", ()), [ref], rounded)
                    self.shared = shared
                    self.indent -= 1
                    self.write("}")
                    continue
                self.assignment(expr, [ref], rounded)
            for _ in range(opened):
                self.indent -= 1
                self.write("}")
        elif op == "accept":
            self.write(f"{self.reference(a[0])}.accept();")
        elif op == "accept_clock":
            ref, kind = a
            field = self.program.fields[ref.name]
            if ref.start is not None:
                raise CobolError(f"ACCEPT FROM {kind} vers une sous-chaîne non pris en charge")
            if field.kind == "text":
                # cob_move to an alphanumeric field (cob_move_to_group_as_alnum for a group).
                self.alphanumeric_move(ref, f"runtime::clock_digits({quoted(kind)})")
            else:
                self.assignment(Expr("clock", (kind,)), [ref], False, move=True)
        elif op == "accept_omitted":
            self.write("runtime::accept_omitted();")
        elif op == "initialize" and a[2]:
            for ref in a[0]:
                self.initialize_replacing(ref, a[1], a[2])
        elif op == "initialize":
            for ref in a[0]:
                if ref.name in self.variable_groups and ref.start is None:
                    # GnuCOBOL 3.2's compound ODO initialization depends on its
                    # codegen strategy (including cob_init_table edge cases).
                    # Only the verified uniform-text case is supported here.
                    fields = leaves(self.program.fields, ref.name)
                    if self.variable_groups[ref.name].children or any(f.kind != "text" or (f.filler and not a[1]) for f in fields):
                        raise CobolError("INITIALIZE de groupe variable limité aux champs texte uniformes; initialiser les occurrences explicitement")
                self.write(f"{self.reference(ref)}.initialize_with_filler({str(a[1]).lower()});")
        elif op == "release":
            name, record, value = a
            if value is not None:
                self.assignment(value, [record], False, move=True)
            self.write(f"{self.handle(name)}.release(&self.{self.files[name]}_area);")
        elif op == "set_switch":
            for number in a[0]:
                self.write(f"runtime::set_switch({number}, {str(a[1]).lower()});")
        elif op == "initiate":
            for name in a[0]:
                rust = self.reports[name]
                self.write(f"let mut report = std::mem::take(&mut self.{rust});")
                self.write(f"report.initiate(&mut |event| self.{rust}_event(event));")
                self.write(f"self.{rust} = report;")
        elif op in {"generate", "terminate"}:
            for name in ([a[0]] if op == "generate" else a[0]):
                rust = self.reports[name]
                # The report leaves the program while libcob's routine runs:
                # its events reach the program's SOURCE items and file.
                self.write(f"let mut report = std::mem::take(&mut self.{rust});")
                group = "" if op == "terminate" else (f"Some({a[1]}), " if a[1] is not None else "None, ")
                self.write(f"report.{op}({group}&mut |event| self.{rust}_event(event));")
                self.write(f"self.{rust} = report;")
        elif op == "cancel":
            for kind, target in a[0]:
                if kind == "literal":
                    self.write(f"unit.cancel({quoted(target)});")
                else:
                    self.write(f"unit.cancel(String::from_utf8_lossy(&{self.reference(target)}.bytes()).trim_end_matches(' '));")
        elif op == "inspect":
            self.inspect(*a)
        elif op == "continue":
            self.write("{}")
        else:
            raise CobolError(f"instruction inconnue: {op}")

    def string_operand(self, e):
        if e.op == "var":
            return f"storage_runtime::Operand::of(&{self.reference(e.args[0])})"
        if e.op in {"function", "refmod"}:
            return f"storage_runtime::Operand::new(({self.expression(e)}).bytes(), false)"
        data = "vec![" + ", ".join(f"{ord(c)}u8" for c in e.args[0]) + "]"
        return f"storage_runtime::Operand::new({data}, {str(e.op == 'all').lower()})"

    def set_int(self, ref, value):
        """cob_set_int: a MOVE from a native int."""
        field = self.program.fields[ref.name]
        method = "move_binary_to_packed" if self.storage_usage(field) == "Packed" else "move_number"
        self.write(f"{self.reference(ref)}.{method}(&Value::number(&{value}.to_string()));")

    def debug_item(self, label):
        """A DEBUG-ITEM subfield built by Parser.debug_item."""
        key = next(key for key, f in self.program.fields.items()
                   if f.label == label and key.split(".")[0] == "DEBUG-ITEM")
        return DataRef(key)

    @staticmethod
    def byte_vector(text):
        return "vec![" + ", ".join(str(b) for b in text.encode("latin-1")) + "]"

    def alphanumeric_move(self, ref, bytes_expr):
        """cob_str_memcpy: a MOVE from an alphanumeric temporary."""
        field = self.program.fields[ref.name]
        if ref.start is None and field.kind in {"number", "edited"}:
            if field.usage == "INDEX":
                raise CobolError("UNSTRING vers un index non pris en charge")
            self.write(f"{self.reference(ref)}.assign_text_move(&Value::Bytes({bytes_expr}), false);")
        else:
            self.write(f"{self.reference(ref)}.assign(&Value::Bytes({bytes_expr}), false);")

    def string_node(self, stmt, overflow, success):
        groups, target, pointer, _, _ = stmt.args
        pointer_value = f"Some({self.reference(pointer)}.snapshot().integer(\"POINTER\"))" if pointer else "None"
        s = self.unique()
        self.write(f"let mut {s} = storage_runtime::StringInto::init(&{self.reference(target)}, {pointer_value});")
        for items, delimiter in groups:
            self.write(f"{s}.delimited({'None' if delimiter is None else 'Some(' + self.string_operand(delimiter) + ')'});")
            for item in items:
                self.write(f"{s}.append(&{self.string_operand(item)});")
        flag, position = self.unique(), self.unique()
        self.write(f"let ({flag}, {position}) = {s}.finish();")
        if pointer:
            self.set_int(pointer, position)
        self.write(f"pc = if {flag} {{ {overflow} }} else {{ {success} }};")

    def unstring_node(self, stmt, overflow, success, after):
        source, delimiters, targets, pointer, tallying, _, _ = stmt.args
        pointer_value = f"Some({self.reference(pointer)}.snapshot().integer(\"POINTER\"))" if pointer else "None"
        u = self.unique()
        self.write(f"let mut {u} = storage_runtime::Unstring::init(&{self.reference(source)}, {pointer_value});")
        for operand, all_flag in delimiters:
            self.write(f"{u}.delimited({self.string_operand(operand)}, {str(all_flag).lower()});")
        for target, delimiter, count in targets:
            data, found, size = self.unique(), self.unique(), self.unique()
            self.write(f"if let Some(({data}, {found}, {size})) = {u}.next_into(storage_runtime::field_size(&{self.reference(target)})) {{")
            self.indent += 1
            self.write(f"let _ = (&{found}, {size});")
            self.alphanumeric_move(target, data)
            if delimiter is not None:
                f = self.program.fields[delimiter.name]
                self.write(f"match {found} {{")
                self.indent += 1
                self.write("Some(found) => {")
                self.indent += 1
                self.alphanumeric_move(delimiter, "found")
                self.indent -= 1
                self.write("},")
                if delimiter.start is None and f.kind == "number":
                    self.write("None => {")
                    self.indent += 1
                    self.set_int(delimiter, "0")
                    self.indent -= 1
                    self.write("},")
                else:
                    self.write(f"None => storage_runtime::fill_spaces(&{self.reference(delimiter)}),")
                self.indent -= 1
                self.write("}")
            if count is not None:
                self.set_int(count, size)
            self.indent -= 1
            self.write("}")
        size_exception = self.unique()
        self.write(f"let mut {size_exception} = false;")
        if tallying is not None:
            positions = max(0, -self.program.fields[tallying.name].scale)
            delta = self.unique()
            self.write(f"if {u}.count() != 0 {{ if let Some({delta}) = runtime::cob_add_int_operand(&Value::number(&{u}.count().to_string()), {positions}, false) {{")
            self.indent += 1
            counter = self.reference(tallying)
            self.write(f"let {delta} = {counter}.snapshot().plus(&{delta});")
            self.write(f"{size_exception} = {counter}.store_truncated(&{delta});")
            self.indent -= 1
            self.write("} }")
        flag, exception, position = self.unique(), self.unique(), self.unique()
        self.write(f"let ({flag}, {exception}, {position}) = {u}.finish({size_exception});")
        if pointer:
            self.set_int(pointer, position)
        self.write(f"pc = if {flag} {{ {overflow} }} else if !{exception} {{ {success} }} else {{ {after} }};")

    def inspect_operand(self, e):
        if e.op == "var":
            return f"storage_runtime::Operand::of(&{self.reference(e.args[0])})"
        data = "vec![" + ", ".join(f"{ord(c)}u8" for c in e.args[0]) + "]"
        return f"storage_runtime::Operand::new({data}, {str(e.op == 'all').lower()})"

    def inspect(self, target, clauses):
        """cb_emit_inspect: init, then per item cob_inspect_start, BEFORE/AFTER
        in source order and the operation; TALLYING and REPLACING each finish."""
        if isinstance(target, Expr):
            # A literal or a function: TALLYING over a temporary field.
            subject = self.unique()
            self.write(f"let {subject} = storage_runtime::temporary(&({self.expression(target)}));")
        else:
            field = self.program.fields[target.name]
            if target.start is None and field.kind == "number" and field.usage != "DISPLAY":
                raise CobolError("INSPECT d'un champ binaire, packé ou index non pris en charge")
            subject = self.reference(target)
        modes = {"all": "All", "leading": "Leading", "first": "First", "trailing": "Trailing"}
        for clause in clauses:
            self.write("{")
            self.indent += 1
            if clause[0] == "converting":
                _, source, to, region = clause
                self.write(f"let mut inspect = storage_runtime::Inspect::init_converting(&{subject});")
                items = [("convert", source, to, region)]
            else:
                replacing = clause[0] == "replacing"
                self.write(f"let mut inspect = storage_runtime::Inspect::init(&{subject}, {str(replacing).lower()});")
                items = clause[1]
            for item in items:
                region = item[3]
                self.write("inspect.start();")
                for word, operand in region:
                    self.write(f"inspect.{word}(&{self.inspect_operand(operand)});")
                if clause[0] == "tallying":
                    counter, mode, value, _ = item
                    call = "inspect.tally_characters()" if mode == "characters" else \
                        f"inspect.tally(storage_runtime::InspectMode::{modes[mode]}, &{self.inspect_operand(value)})"
                    count, delta = self.unique(), self.unique()
                    positions = max(0, -self.program.fields[counter.name].scale)
                    self.write(f"let {count} = {call};")
                    # cob_add_int: P positions truncate the count first.
                    self.write(f"if {count} != 0 {{ if let Some({delta}) = runtime::cob_add_int_operand(&Value::number(&{count}.to_string()), {positions}, false) {{")
                    self.indent += 1
                    target_counter = self.reference(counter)
                    self.write(f"let {delta} = {target_counter}.snapshot().plus(&{delta});")
                    self.write(f"{target_counter}.store_truncated(&{delta});")
                    self.indent -= 1
                    self.write("} }")
                elif clause[0] == "replacing":
                    mode, source, to, _ = item
                    if mode == "characters":
                        self.write(f"inspect.replace_characters(&{self.inspect_operand(to)});")
                    else:
                        self.write(f"inspect.replace(storage_runtime::InspectMode::{modes[mode]}, &{self.inspect_operand(to)}, &{self.inspect_operand(source)});")
                else:
                    _, source, to, _ = item
                    self.write(f"inspect.convert(&{self.inspect_operand(source)}, &{self.inspect_operand(to)});")
            if clause[0] != "converting":
                self.write("inspect.finish();")
            self.indent -= 1
            self.write("}")

    def control_node(self, index, node):
        op, a = node.op, node.args
        if op == "end":
            # Falling off the end: STOP RUN in a main program, GOBACK in a subprogram.
            if not self.subprogram:
                self.exit_code()
            self.write("return runtime::Outcome::Return;" if self.subprogram else "return runtime::Outcome::Stop;")
        elif op == "stop_run":
            if a and a[0] is not None:
                # cob_stop_run (cob_get_int (x)).
                if self.kind(a[0]) != "number":
                    raise CobolError("STOP RUN RETURNING alphanumérique non pris en charge")
                self.write(f"unit.exit_code = runtime::stop_status(&({self.expression(a[0])}));")
            else:
                self.exit_code()
            self.write("return runtime::Outcome::Stop;")
        elif op == "use_return":
            self.write("return runtime::Outcome::Return;")
        elif op == "global_use":
            owner, section, continuation = a
            self.write(f"if let runtime::Outcome::Stop = unit.global_use({quoted(owner)}, {quoted(section)}) {{ return runtime::Outcome::Stop; }}")
            self.write(f"pc = {continuation};")
        elif op == "goback":
            if not self.subprogram:
                self.exit_code()
            self.write("return runtime::Outcome::Return;" if self.subprogram else "return runtime::Outcome::Stop;")
        elif op == "exit_program":
            if self.module:
                self.exit_code()
                self.write("return runtime::Outcome::Stop;")
            else:
                self.write("return runtime::Outcome::Return;" if self.subprogram else f"pc = {a[0]};")
        elif op == "call_program":
            target, arguments, continuation, exception, success = a
            values = []
            for mode, ref in arguments:
                if ref is None:
                    values.append("storage_runtime::omitted()")
                    continue
                if isinstance(ref, Expr):
                    # BY CONTENT: a fresh copy at each CALL; BY REFERENCE: the
                    # program's constant itself.
                    data = self.byte_vector(ref.args[0])
                    values.append(f"storage_runtime::temporary(&Value::Bytes({data}))" if mode == "CONTENT" else
                                  f"storage_runtime::literal_argument({quoted(self.struct + ':' + ref.args[0])}, &{data})")
                    continue
                # BY REFERENCE passes an address: a variable group's LINKAGE
                # item may address its whole allocation, not only the active part.
                view = self.reference(ref, active=mode == "CONTENT" or ref.start is not None) + ".clone()"
                values.append(f"storage_runtime::content_copy(&{view})" if mode == "CONTENT" else view)
            # A program not found raises EC-PROGRAM-NOT-FOUND, handled by
            # ON EXCEPTION; without it GnuCOBOL stops the run unit.
            # cob_call_error without ON EXCEPTION: "module 'X' not found", exit 1.
            not_found = (f"pc = {exception};" if exception is not None
                         else "runtime::module_not_found({});")
            if target[0] == "literal" and target[1] not in self.called:
                if not surely_absent(target[1], self.present):
                    raise CobolError(f"CALL {target[1]}: programme non converti ou routine système non pris en charge")
                self.write(not_found.format(f"b{quoted(target[1])}"))
                return
            name = quoted(target[1]) if target[0] == "literal" else f"{self.reference(target[1])}.bytes()"
            if target[0] == "dynamic":
                self.write(f"let name = String::from_utf8_lossy(&{name}).trim_end_matches(' ').to_string();")
                name = "&name"
            self.write(f"match unit.call({name}, vec![{', '.join(values)}]) {{")
            self.indent += 1
            self.write("Some(runtime::Outcome::Stop) => return runtime::Outcome::Stop,")
            if self.register:
                # The callee's return value (its RETURN-CODE) becomes ours.
                self.write(f"Some(runtime::Outcome::Return) => {{ if let Some(code) = unit.returned {{ "
                           f"{self.register}.assign(&Value::number(&code.to_string()), false); }} pc = {success}; }}")
            else:
                self.write(f"Some(runtime::Outcome::Return) => pc = {success},")
            if target[0] == "dynamic":
                present = ", ".join(quoted(name) for name in [*self.present, *sorted(self.called - self.entry_names)])
                self.write(f"None if runtime::surely_absent(&name, &[{present}]) => {{ {not_found.format('name.as_bytes()')} }}")
            elif target[1] in self.entry_names:
                self.write(f"None => {{ {not_found.format(f'b{quoted(target[1])}')} }}")
            self.write("None => runtime::fail(\"CALL of a program absent from the conversion or recursive; not modelled\"),")
            self.indent -= 1
            self.write("}")
        elif op == "search_test":
            table, index, ending, whens = a
            self.write(f"if {self.reference(DataRef(index))}.integer(\"SEARCH\") > {self.occurs(table)} {{ pc = {ending}; }} else {{ pc = {whens}; }}")
        elif op == "search_step":
            index, varying, test = a
            name = self.reference(DataRef(index))
            self.write(f"let step = {name}.plus(&Value::number(\"1\"));")
            self.write(f"{name}.assign(&step, false);")
            if varying is not None and varying.name != index:
                self.write(f"let value = {name}.snapshot();")
                self.write(f"{self.reference(varying)}.assign(&value, false);")
            self.write(f"pc = {test};")
        elif op == "search_all":
            # output_search_all: head 0, tail max + 1, index (head + tail) / 2;
            # ret is the comparison of the first unequal key, as cobc's (ret = ...).
            table, index, keys, body, ending = a
            name = self.reference(DataRef(index))
            for left, right in keys:
                if self.folded_comparison("=", left, right) is not None:
                    raise CobolError("SEARCH ALL avec une comparaison de clé résolue à la compilation non pris en charge")
            self.write(f"let mut head: i128 = 0; let mut tail: i128 = {self.occurs(table)} + 1; let mut found = false;")
            self.write("loop {")
            self.indent += 1
            self.write("if head >= tail - 1 { break; }")
            self.write("let mid = (head + tail) / 2;")
            self.write(f"{name}.assign(&Value::number(&mid.to_string()), false);")
            self.write("let mut ret = std::cmp::Ordering::Equal;")
            for left, right in keys:
                self.write(f"if ret == std::cmp::Ordering::Equal {{ ret = {self.comparison_order(left, right)}; }}")
            self.write("if ret == std::cmp::Ordering::Equal { found = true; break; }")
            self.write("if ret == std::cmp::Ordering::Less { head = mid; } else { tail = mid; }")
            self.indent -= 1
            self.write("}")
            self.write(f"pc = if found {{ {body} }} else {{ {ending} }};")
        elif op == "sort_init":
            name, keys, following = a
            spec = self.program.files[name]
            base = self.program.fields[spec.record].offset
            specs = []
            for descending, ref in keys:
                field = self.program.fields[ref.name]
                specs.append(f"file_runtime::SortKey {{ offset: {field.offset - base}, size: {field.size}, "
                             f"kind: {self.storage_kind(field)}, descending: {str(descending).lower()} }}")
            self.write(f"{self.handle(name)}.init(vec![{', '.join(specs)}]);")
            self.write(f"pc = {following};")
        elif op == "sort_using":
            # cob_file_sort_using: OPEN INPUT, READ each record into the SD
            # area (cob_copy_check) and release it, CLOSE. The user's FILE
            # STATUS is not updated; a file that fails to open is skipped.
            name, files, following = a
            sort, sorter = self.files[name], self.handle(name)
            for using in files:
                rust, handle = self.files[using], self.handle(using)
                self.assign_name(using)
                self.write(f"if {handle}.open(\"INPUT\") < 10 {{")
                self.indent += 1
                self.write(f"while {handle}.read(&mut self.{rust}_area, None) < 10 {{")
                if self.program.files[using].record_min != self.program.files[using].record_max:
                    # The record's size is the size read (sequential_read).
                    self.write(f"    let record = Value::Bytes(self.{rust}_area.bytes()[..{self.handle(using, True)}.last_read_size()].to_vec());")
                    self.write(f"    {sorter}.release_from(&record, &mut self.{sort}_area);")
                else:
                    self.write(f"    {sorter}.release_from(&self.{rust}_area, &mut self.{sort}_area);")
                self.write("}")
                self.write(f"{handle}.close(false);")
                self.indent -= 1
                self.write("}")
            self.write(f"pc = {following};")
        elif op == "sort_giving":
            # cob_file_sort_giving: OPEN OUTPUT each file, WRITE every record to
            # each one opened (record area at its maximum size), CLOSE them.
            name, files, following = a
            sort, sorter = self.files[name], self.handle(name)
            opened = self.unique()
            self.write(f"let mut {opened} = vec![false; {len(files)}];")
            for index, giving in enumerate(files):
                self.assign_name(giving)
                self.write(f"{opened}[{index}] = {self.handle(giving)}.open(\"OUTPUT\") < 10;")
            initially = self.unique()
            self.write(f"let {initially} = {opened}.clone();")
            self.write(f"while {sorter}.retrieve(&mut self.{sort}_area) == 0 {{")
            self.indent += 1
            for index, giving in enumerate(files):
                rust, spec, handle = self.files[giving], self.program.files[giving], self.handle(giving)
                self.write(f"if {opened}[{index}] {{")
                self.write(f"    self.{rust}_area.assign(&Value::Bytes(self.{sort}_area.bytes()), false);")
                self.write(f"    if {handle}.write(&self.{rust}_area, {spec.record_max}, None, None) >= 30 {{ {opened}[{index}] = false; }}")
                self.write("}")
            self.indent -= 1
            self.write("}")
            for index, giving in enumerate(files):
                self.write(f"if {initially}[{index}] {{ {self.handle(giving)}.close(false); }}")
            self.write(f"pc = {following};")
        elif op == "sort_close":
            self.write(f"{self.handle(a[0])}.close();")
            self.write(f"pc = {a[1]};")
        elif op == "return_sort":
            name, into, at_end, not_at_end, = a
            sort, sorter = self.files[name], self.handle(name)
            self.write(f"if {sorter}.retrieve(&mut self.{sort}_area) == 0 {{")
            self.indent += 1
            if into:
                record = self.names[self.program.files[name].record]
                self.write(f"let record = self.{record}.snapshot();")
                self.write(f"{self.receiver(into)}.assign(&record, false);")
            self.write(f"pc = {not_at_end};")
            self.indent -= 1
            self.write(f"}} else {{ pc = {at_end}; }}")
        elif op == "jump":
            self.write(f"pc = {a[0]};")
        elif op == "alter_check":
            # The ALTER target if one was executed, else the paragraph body.
            self.write(f"pc = if self.alter[{a[0]}] != 0 {{ self.alter[{a[0]}] }} else {{ {a[1]} }};")
        elif op == "alter":
            self.write(f"self.alter[{a[0]}] = {a[1]};")
            self.write(f"pc = {a[2]};")
        elif op in {"alter_zap", "alter_save", "alter_restore"}:
            for slot in a[0]:
                self.write({"alter_zap": f"self.alter[{slot}] = 0;",
                            "alter_save": f"self.alter_saved[{slot}] = self.alter[{slot}];",
                            "alter_restore": f"self.alter[{slot}] = self.alter_saved[{slot}];"}[op])
            self.write(f"pc = {a[1]};")
        elif op == "checkpoint":
            # A jump may leave PERFORM frames dormant. Only the top frame's
            # exact paragraph/section checkpoint can resume its continuation.
            self.write(f"pc = if stack.last().is_some_and(|frame| frame.through == {index}) {{")
            self.indent += 1
            self.write("stack.pop().unwrap().return_pc")
            self.indent -= 1
            self.write(f"}} else {{ {a[0]} }};")
        elif op == "execute":
            self.statement(a[0])
            self.write(f"pc = {a[1]};")
        elif op == "io":
            stmt, continuation, self.io_handlers, invalid, valid, debug = a
            eop = (stmt.op == "write" and (invalid is not None or valid is not None)
                   and self.program.files[stmt.args[0]].organization in {"SEQUENTIAL", "LINE SEQUENTIAL"})
            # AT END-OF-PAGE / NOT AT END-OF-PAGE hold the INVALID KEY slots.
            self.io_eop = (invalid is not None,) if eop else None
            self.io_invalid = invalid is not None and not eop
            self.statement(stmt)
            self.io_handlers, self.io_invalid, self.io_eop = None, False, None
            success = continuation if valid is None else valid
            if eop:
                # output_ferror_stmt: an exception other than EOP is a file
                # error; EOP runs AT END-OF-PAGE, no exception NOT AT END-OF-PAGE.
                exception = continuation if invalid is None else invalid
                dispatch = f"if status >= 10 {{ handler.unwrap_or({continuation}) }} else if eop {{ {exception} }} else {{ {success} }}"
            else:
                # INVALID KEY takes 2x; any other status outside 0x runs its USE procedure.
                prefix = f"if status / 10 == 2 {{ {invalid} }} else " if invalid is not None else ""
                dispatch = f"{prefix}if status >= 10 {{ handler.unwrap_or({continuation}) }} else {{ {success} }}"
            if debug is None:
                self.write(f"pc = {dispatch};")
            else:
                # The file's debugging section runs before the status handling.
                self.write(f"debug_resume = {dispatch};")
                self.write(f"pc = {debug};")
        elif op == "debug_resume":
            self.write("pc = debug_resume;")
        elif op == "debug_gate":
            self.write(f"pc = if runtime::debugging_mode() {{ {a[0]} }} else {{ {a[1]} }};")
        elif op == "debug_name":
            self.alphanumeric_move(self.debug_item("DEBUG-NAME"), self.byte_vector(a[0]))
            self.write(f"pc = {a[1]};")
        elif op == "debug_blank":
            self.write(f"storage_runtime::fill_spaces(&{self.reference(a[0])});")
            self.write(f"pc = {a[1]};")
        elif op == "debug_line":
            self.alphanumeric_move(self.debug_item("DEBUG-LINE"), self.byte_vector(f"{a[0]:6d}"[-6:]))
            self.write(f"pc = {a[1]};")
        elif op == "debug_contents":
            contents, continuation = a
            if isinstance(contents, tuple) and contents[0] == "field":
                # output_debug_item: the item's bytes, or MOVE of a record.
                source = f"{self.reference(contents[1])}.bytes()"
            elif isinstance(contents, tuple):
                record = self.names[self.program.files[contents[1]].record]
                source = f"self.{record}.bytes()"
            else:
                source = self.byte_vector(contents or "")
            self.alphanumeric_move(self.debug_item("DEBUG-CONTENTS"), source)
            self.write(f"pc = {continuation};")
        elif op == "branch":
            self.write(f"pc = if {self.expression(a[0])} {{ {a[1]} }} else {{ {a[2]} }};")
        elif op == "call":
            target, through, continuation = a
            self.write(f"stack.push(PerformFrame {{ through: {through}, return_pc: {continuation} }});")
            self.write(f"pc = {target};")
        elif op == "goto":
            targets, controller, continuation = a
            if controller is None:
                self.write(f"pc = {targets[0]};")
            else:
                self.write(f'pc = match {self.reference(controller)}.integer("GO TO DEPENDING ON") {{')
                self.indent += 1
                for choice, target in enumerate(targets, 1):
                    self.write(f"{choice} => {target},")
                self.write(f"_ => {continuation},")
                self.indent -= 1
                self.write("};")
        elif op == "times_init":
            slot, expr, continuation = a
            if self.kind(expr) != "number":
                raise CobolError("TIMES requiert un nombre")
            self.write(f"times[{slot}] = ({self.expression(expr)}).count();")
            self.write(f"pc = {continuation};")
        elif op == "times_test":
            slot, body, continuation = a
            self.write(f"pc = if times[{slot}] > 0 {{ {body} }} else {{ {continuation} }};")
        elif op == "times_step":
            slot, continuation = a
            self.write(f"times[{slot}] -= 1;")
            self.write(f"pc = {continuation};")
        elif op == "varying_step":
            var, step, continuation = a
            if self.kind(step) != "number":
                raise CobolError("BY requiert un nombre")
            name = self.reference(var)
            self.write(f"let step = {name}.plus(&({self.expression(step)}));")
            self.write(f"{name}.assign(&step, false);")
            self.write(f"pc = {continuation};")
        elif op == "evaluate":
            _, branches, otherwise = a
            for i, (condition, target) in enumerate(branches):
                if self.kind(condition) != "bool":
                    raise CobolError("EVALUATE: condition attendue")
                self.write(f"{'if' if i == 0 else '} else if'} {self.expression(condition)} {{")
                self.indent += 1
                self.write(f"pc = {target};")
                self.indent -= 1
            if branches:
                self.write("} else {")
                self.indent += 1
            self.write(f"pc = {otherwise};")
            if branches:
                self.indent -= 1
                self.write("}")
        elif op == "read":
            name, into, success, eof, continuation, self.io_handlers = a
            spec = self.program.files[name]
            record = self.names[spec.record]
            status = self.unique()
            handled = bool(node.stmt.args[2])
            random = node.stmt.args[4]
            # INDEXED: (key index, compared length) of the keyed READ.
            keyed = bool(random)
            # AT END takes every 1x status of a sequential read, INVALID KEY every 2x.
            exception_class = 2 if random else 1
            area, depending = f"self.{self.files[name]}_area", self.depending(name, True)
            if spec.organization == "INDEXED":
                if random:
                    key = "file_runtime::NO_KEY" if random[0] < 0 else random[0]
                    self.write(f"let {status} = {self.handle(name)}.read_key(&mut {area}, {key}, {random[1]}, {depending});")
                else:
                    self.write(f"let {status} = {self.handle(name)}.read_next(&mut {area}, {depending});")
            elif spec.organization != "RELATIVE":
                self.write(f"let {status} = {self.handle(name)}.read(&mut {area}, {depending});")
            elif random:
                self.write(f"let {status} = {self.handle(name)}.read_key(&mut {area}, &self.{self.names[spec.relative_key]}, {depending});")
            else:
                self.write(f"let {status} = {self.handle(name)}.read_next(&mut {area}, {self.relative_key(name, True)}, {depending});")
            self.io_invalid = handled and keyed
            self.file_status(name, status, handled and not keyed)
            self.io_handlers, self.io_invalid = None, False
            self.write(f"if matches!({status}, 0 | 4 | 6 | 9) {{")
            self.indent += 1
            if into:
                if spec.organization in {"SEQUENTIAL", "RELATIVE", "INDEXED"} or spec.record_min != spec.record_max:
                    # READ INTO moves the record as read: its size is the size
                    # read (lineseq_read sets it to the bytes stored).
                    self.write(f"let record = Value::Bytes(self.{self.files[name]}_area.bytes()[..{self.handle(name, True)}.last_read_size()].to_vec());")
                else:
                    self.write(f"let record = self.{record}.snapshot();")
                self.write(f"{self.receiver(into)}.assign(&record, false);")
            self.write(f"pc = {success};")
            self.indent -= 1
            if handled:
                self.write(f"}} else if {status} / 10 == {exception_class} {{")
                self.indent += 1
                self.write(f"pc = {eof};")
                self.indent -= 1
            self.write(f"}} else if {status} >= 10 {{ pc = handler.unwrap_or({continuation}); }} else {{ pc = {continuation}; }}")
        elif op == "string":
            self.string_node(node.stmt, *a)
        elif op == "unstring":
            self.unstring_node(node.stmt, *a)
        elif op == "arithmetic":
            shared, items, error, success = a
            if any(ref.start is not None or self.program.fields[ref.name].kind not in {"number", "edited"} for ref, _, _ in items):
                raise CobolError("destination numérique requise pour SIZE ERROR")
            if (node.stmt is not None and not node.stmt.args[2]
                    and any(self.storage_usage(self.program.fields[ref.name]) in {"Native", "Register"} for ref, _, _ in items)):
                # cobc keeps a COMP-5 receiver only with ON SIZE ERROR
                # (ex_handler); NOT ON SIZE ERROR alone stores the residue.
                raise CobolError("NOT ON SIZE ERROR sans ON SIZE ERROR vers COMP-5 non modélisé")
            if shared is not None:
                self.shared = self.unique()
                self.write(f"let {self.shared}: Result<Value, runtime::SizeError> = (|| {self.checked_expression(shared)})();")
            # A receiver in error keeps its value; the others are still stored,
            # then the handler runs once, as GnuCOBOL does.
            failed = self.unique()
            self.write(f"let mut {failed} = false;")
            for ref, expr, rounded in items:
                self.write(f"if (|| -> Result<(), runtime::SizeError> {{")
                self.indent += 1
                self.write(f"let value: Value = {self.checked_expression(expr)}?;")
                self.write(f"{self.reference(ref)}.checked_assign(&value, {str(rounded).lower()})")
                self.indent -= 1
                self.write(f"}})().is_err() {{ {failed} = true; }}")
            self.write(f"pc = if {failed} {{ {error} }} else {{ {success} }};")
        else:
            raise CobolError(f"nœud de contrôle inconnu: {op}")

    @staticmethod
    def storage_usage(f):
        if f.usage == "DISPLAY" and f.sign_leading:
            return "SignLeadingSeparate" if f.sign_separate else "SignLeading"
        if f.usage == "DISPLAY" and f.sign_separate:
            return "SignTrailingSeparate"
        if f.usage in {"INDEX", "DISPLAY"}:
            return f.usage.capitalize()
        if f.usage == "COMP-5":
            return "Register" if getattr(f, "register", False) else "Native"
        return "Packed" if f.usage in {"COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL"} else "Binary"

    def storage_kind(self, f):
        if f.kind == "text":
            if f.alnum_edit:
                return f"storage_runtime::Kind::AlnumEdited {{ symbols: b{quoted(f.alnum_edit)} }}"
            if f.justified:
                return "storage_runtime::Kind::Justified"
            return "storage_runtime::Kind::Text"
        if f.kind == "edited":
            symbols = ", ".join(f"(b'{c}', {n})" for c, n in f.edit_symbols)
            return (f"storage_runtime::Kind::Edited {{ symbols: &[{symbols}], digits: {f.digits}, scale: {f.scale}, "
                    f"blank_zero: {str(f.blank_zero).lower()} }}")
        usage = self.storage_usage(f)
        return f"storage_runtime::Kind::Numeric {{ digits: {f.digits}, scale: {f.scale}, signed: {str(f.signed).lower()}, usage: storage_runtime::Usage::{usage} }}"

    def dimensions(self, dimensions):
        return "vec![" + ", ".join(f"({stride}, {count})" for stride, count in dimensions) + "]"

    def initializers(self, f):
        items = [f] if f.picture else [leaf for child in f.children for leaf in leaves(self.program.fields, child)]
        return "vec![" + ", ".join(
            f"storage_runtime::Initializer {{ offset: {leaf.offset - f.offset}, size: {leaf.size}, kind: {self.storage_kind(leaf)}, dimensions: {self.dimensions(leaf.dimensions[len(f.dimensions):])}, filler: {str(leaf.filler).lower()} }}"
            for leaf in items) + "]"

    def generate(self):
        return generate_unit([self])

    def program_lines(self):
        """Struct and impl of this program; `generate_unit` adds the run unit."""
        graph = ControlGraph(self.program, self.blocks)
        self.write(f"struct {self.struct} {{")
        self.indent += 1
        for name in self.names:
            self.write(f"{self.names[name]}: Value, // {name} PIC {self.program.fields[name].picture}")
        for name, rust_name in self.files.items():
            kind = f"file_runtime::{self.file_kind(name)}"
            if name in self.shared_files:
                kind = f"file_runtime::Shared<{kind}>"
            self.write(f"{rust_name}: {kind}, // {name}")
            self.write(f"{rust_name}_area: Value, // FD area of {name}, largest record")
        for name, rust_name in self.reports.items():
            self.write(f"{rust_name}: file_runtime::Report, // RD {name}")
        # cobc's static label_N (and save_label_N) of the ALTERed paragraphs:
        # kept between CALLs, cleared by CANCEL with the program instance.
        self.write("alter: Vec<usize>,")
        self.write("alter_saved: Vec<usize>,")
        self.indent -= 1
        self.write("}")
        self.write(f"impl {self.struct} {{")
        self.indent += 1
        self.write("fn new() -> Self {")
        self.indent += 1
        self.write(f"let memory = storage_runtime::memory({self.program.memory_size});")
        # EXTERNAL items: cob_external_addr storage shared by name in the run unit.
        externals = {}
        for name, field in self.program.fields.items():
            block = self.shared_block(name)
            if block is not None and block[0] == name:
                externals[name] = f"external{len(externals)}"
                # The declaring program's instance starts from fresh storage.
                function = "owned_block" if block[2] else "external"
                size = self.program.files[field.fd_file].record_max if getattr(field, "fd_file", None) else field.size
                self.write(f"let {externals[name]} = storage_runtime::{function}({quoted(block[1])}, {size});")
        self.write("let mut result = Self {")
        self.indent += 1
        for name, field in self.program.fields.items():
            root = (self.shared_block(name) or (None,))[0]
            memory, offset = ("memory", field.offset) if root is None else \
                (externals[root], field.offset - self.program.fields[root].offset)
            if root is None and getattr(field, "register", False):
                # A register is not in the program's storage.
                memory = f"storage_runtime::memory({field.size})"
            value = f"Value::View(storage_runtime::View {{ memory: {memory}.clone(), offset: {offset}, size: {field.size}, kind: {self.storage_kind(field)}, dimensions: {self.dimensions(field.dimensions)}, initializers: {self.initializers(field)} }})"
            self.write(f"{self.names[name]}: {value},")
        for name, rust_name in self.files.items():
            spec = self.program.files[name]
            limits = f"{spec.record_min}, {spec.record_max}"
            if spec.sort:
                created = f"file_runtime::SortFile::new({spec.record_max})"
            elif spec.organization == "RELATIVE":
                created = f"file_runtime::RelativeFile::new({self.assign_literal(spec)}, {str(spec.optional).lower()}, {quoted(spec.access)}, {limits}).named({quoted(spec.select_text or name)})"
            elif spec.organization == "INDEXED":
                keys = ", ".join(f"file_runtime::IndexKey {{ offset: {offset}, size: {size}, duplicates: {str(duplicates).lower()} }}"
                                 for _, offset, size, duplicates in [spec.record_key, *spec.alternate_keys])
                created = f"file_runtime::IndexedFile::new({self.assign_literal(spec)}, {str(spec.optional).lower()}, {quoted(spec.access)}, {limits}, vec![{keys}]).named({quoted(spec.select_text or name)})"
            else:
                linage = ".with_linage()" if spec.linage else ""
                if spec.organization == "LINE SEQUENTIAL":
                    # finalize_file: a LINE SEQUENTIAL record_min is 0.
                    limits = f"0, {spec.record_max}"
                created = f"file_runtime::CobolFile::new({self.assign_literal(spec)}, {str(spec.optional).lower()}, {quoted(spec.organization)}, {limits}){linage}.named({quoted(spec.select_text or name)})"
            registry = self.file_registry(name)
            if spec.external:
                # cob_file_external_addr: the first program creates the file.
                created = f"file_runtime::external_file({quoted(registry)}, || {created})"
            elif spec.global_owner:
                created = f"file_runtime::global_file::<file_runtime::{self.file_kind(name)}>({quoted(registry)})"
            elif registry:
                # A new instance of the declaring program has a new file.
                created = f"file_runtime::owned_file({quoted(registry)}, {created})"
            elif name in self.shared_files:
                created = f"std::rc::Rc::new(std::cell::RefCell::new({created}))"
            self.write(f"{rust_name}: {created},")
            block = self.shared_block(spec.record)
            memory, offset = (externals[block[0]], 0) if block else ("memory", self.program.fields[spec.record].offset)
            self.write(f"{rust_name}_area: Value::View(storage_runtime::View {{ memory: {memory}.clone(), offset: {offset}, size: {spec.record_max}, kind: storage_runtime::Kind::Text, dimensions: vec![], initializers: vec![] }}),")
        for name, rust_name in self.reports.items():
            self.write(f"{rust_name}: {self.report_definition(self.program.reports[name])},")
        alters = len(self.program.alters)
        self.write(f"alter: vec![0; {alters}],")
        self.write(f"alter_saved: vec![0; {alters}],")
        self.indent -= 1
        self.write("};")
        for name, field in self.program.fields.items():
            if field.linkage:
                # No address until a CALL passes the item (NULL for cobc).
                self.write(f"result.{self.names[name]} = storage_runtime::unbind(&result.{self.names[name]});")
        self.initialize("result", lambda field: True)
        self.write("result")
        self.indent -= 1
        self.write("}")
        if self.subprogram or self.module:
            self.call_method(graph)
        for name in self.reports:
            self.report_events(self.program.reports[name])
        uses = getattr(self.program, "global_uses", None)
        if uses or graph.entry_points:
            self.write("fn run(&mut self, unit: &mut RunUnit) -> runtime::Outcome {")
            self.write(f"    self.run_at(unit, {graph.entry})")
            self.write("}")
            self.write("fn run_at(&mut self, unit: &mut RunUnit, start: usize) -> runtime::Outcome {")
            if uses:
                # While the program runs, its contained programs reach its GLOBAL
                # USE procedures through an alias sharing its storage and files.
                self.write(f"    unit.uses.push(({quoted(self.program.entry_name)}, Some(Box::new(self.alias()))));")
            self.write("    let outcome = self.run_from(unit, start);")
            if uses:
                self.write("    unit.uses.pop();")
            self.write("    outcome")
            self.write("}")
            self.write("fn run_from(&mut self, unit: &mut RunUnit, start: usize) -> runtime::Outcome {")
        else:
            self.write("fn run(&mut self, unit: &mut RunUnit) -> runtime::Outcome {")
        self.indent += 1
        collating = getattr(self.program, "collating", None)
        if collating:
            # OBJECT-COMPUTER PROGRAM COLLATING SEQUENCE: the alphabet's weights.
            self.write(f"static COLLATING: [u8; 256] = [{', '.join(str(w) for w in collating)}];")
        self.write(f"let _collating = runtime::CollatingGuard::new({'Some(&COLLATING)' if collating else 'None'});")
        decimal_comma, currency = getattr(self.program, "decimal_comma", False), getattr(self.program, "currency", "$")
        if decimal_comma or currency != "$":
            # COB_MODULE_PTR->decimal_point, numeric_separator, currency_symbol.
            separators = "b',', b'.'" if decimal_comma else "b'.', b','"
            self.write(f"let _symbols = runtime::SymbolGuard::new({separators}, {ord(currency)});")
        self.write(f"let mut pc: usize = {'start' if uses or graph.entry_points else graph.entry};")
        self.write("let mut stack: Vec<PerformFrame> = Vec::new();")
        # Like GnuCOBOL's n0/n1 counters, TIMES state belongs to its source
        # site, including when PERFORM re-enters that site recursively.
        self.write(f"let mut times = vec![0i128; {graph.times_slots}];")
        # Status handling resumed after a file's debugging section.
        self.write("let mut debug_resume: usize = 0;")
        self.write("loop {")
        self.indent += 1
        self.write("match pc {")
        self.indent += 1
        for index, node in enumerate(graph.nodes):
            self.write(f"{index} => {{")
            self.indent += 1
            stmt = node.stmt
            if stmt is not None:
                self.mapping.append({"cobol_line": stmt.line, "rust_line": len(self.lines) + 1,
                                     "operation": stmt.op})
                self.write(f"// COBOL line {stmt.line}: {stmt.op}")
                self.write(f"runtime::set_line({stmt.line});")
            try:
                self.control_node(index, node)
            except CobolError as exc:
                if stmt is not None:
                    raise CobolError(f"ligne {stmt.line}: {exc}") from exc
                raise
            self.indent -= 1
            self.write("}")
        self.write('_ => unreachable!("invalid procedure position"),')
        self.indent -= 1
        self.write("}")
        self.indent -= 1
        self.write("}")
        self.indent -= 1
        self.write("}")
        if uses:
            fields = [*self.names.values(), *self.files.values(), *(f"{rust}_area" for rust in self.files.values()),
                      "alter", "alter_saved"]
            self.write("fn alias(&self) -> Self {")
            self.write("    Self { " + " ".join(f"{name}: self.{name}.clone()," for name in fields) + " }")
            self.write("}")
        cancelled = [name for name in self.files if self.file_registry(name) and not self.program.files[name].global_owner]
        if cancelled:
            # The cancel entry closes the EXTERNAL and GLOBAL files left open.
            self.write("fn cancel_files(&self) {")
            for name in cancelled:
                self.write(f"    {self.handle(name)}.cancel_close();")
            self.write("}")
        self.indent -= 1
        self.write("}")
        if uses:
            self.write(f"impl GlobalUse for {self.struct} {{")
            self.write("    fn global_use(&mut self, unit: &mut RunUnit, section: &str) -> runtime::Outcome {")
            cases = " ".join(f"{quoted(section)} => {position}," for section, position in graph.global_entries.items())
            self.write(f'        let start = match section {{ {cases} _ => unreachable!("USE GLOBAL section") }};')
            self.write("        self.run_from(unit, start)")
            self.write("    }")
            self.write("}")
        return self.lines, self.mapping

    def report_definition(self, report):
        """cob_report and its cob_report_line/cob_report_field tables."""
        lines = []
        sources = 0
        for line in report.report_lines:
            fields = []
            for f in line.fields:
                literal = "None" if f.literal is None else "Some(b" + quoted(f.literal.decode("latin-1")) + " as &[u8])"
                source = "None"
                if f.source is not None:
                    source = f"Some({sources})"
                    sources += 1
                fields.append(f"file_runtime::ReportField {{ column: {f.column}, literal: {literal}, source: {source}, "
                              f"indicate: {str(f.indicate).lower()}, indicated: false }}")
            option = lambda v: "None" if v is None else f"Some({v})"
            lines.append(f"file_runtime::ReportLine {{ flags: {line.flags}, line: {line.line}, fields: vec![{', '.join(fields)}], "
                         f"child: {option(line.child)}, sister: {option(line.sister)}, next_group: {line.next_group} }}")
        limits = f"[{report.lines}, {report.heading}, {report.first_detail}, {report.last_detail}]"
        error = getattr(report, "initiate_error", None)
        checked = f".with_initiate_error({quoted(error)})" if error else ""
        if report.controls or report.sums:
            # output_report_control: each control's lines, last declared
            # first, and its sequence in cobc's list.
            ids = self.report_field_ids(report)
            controls = []
            for sequence, key in enumerate(report.controls, 1):
                refs = [index for index, line in enumerate(report.report_lines) if line.control == key][::-1]
                controls.append(f"file_runtime::ReportControl::new({ids.index(key)}, vec![{', '.join(map(str, refs))}], {sequence})")
            sums = []
            for counter, sources, control, final, subtotal in report.sums:
                control_index = "None" if control is None or control not in report.controls else f"Some({report.controls.index(control)})"
                sums.append(f"file_runtime::ReportSum {{ counter: {ids.index(counter)}, sources: vec![{', '.join(str(ids.index(k)) for k in sources)}], "
                            f"control: {control_index}, control_final: {str(final).lower()}, subtotal: {str(subtotal).lower()} }}")
            checked += f".with_controls(vec![{', '.join(controls)}], vec![{', '.join(sums)}])"
        return f"file_runtime::Report::new({quoted(report.name)}, {limits}, {report.size}, vec![{', '.join(lines)}]){checked}"

    @staticmethod
    def report_field_ids(report):
        """The numbered fields of ReportEvent Get/Put/Differs/Add/Zero."""
        ids = []
        for key in [*report.controls, *(k for counter, sources, *_ in report.sums for k in (counter, *sources))]:
            if key not in ids:
                ids.append(key)
        return ids

    def report_events(self, report):
        """The program's answer to the report routines: cob_move of each
        SOURCE into its report item, and cob_write on the report file."""
        rust = self.reports[report.name]
        self.write(f"fn {rust}_event(&mut self, event: file_runtime::ReportEvent) -> Vec<u8> {{")
        self.indent += 1
        self.write("match event {")
        self.indent += 1
        self.write("file_runtime::ReportEvent::Source(index, line_counter, page_counter) => match index {")
        self.indent += 1
        self.report_context = report.name
        number = 0
        for line in report.report_lines:
            for f in line.fields:
                if f.source is None:
                    continue
                self.write(f"{number} => {{")
                self.indent += 1
                self.assignment(f.source, [DataRef(f.item)], False, move=True)
                self.write(f"{self.reference(DataRef(f.item))}.bytes().to_vec()")
                self.indent -= 1
                self.write("}")
                number += 1
        self.report_context = None
        self.write('_ => unreachable!("report SOURCE"),')
        self.indent -= 1
        self.write("},")
        if report.controls or report.sums:
            ids = self.report_field_ids(report)
            refs = [self.reference(DataRef(key)) for key in ids]
            data = lambda r: f"storage_runtime::Operand::of(&{r}).data"
            self.write("file_runtime::ReportEvent::Get(field) => match field {")
            for number, r in enumerate(refs):
                self.write(f"    {number} => {data(r)},")
            self.write('    _ => unreachable!("report field"),')
            self.write("},")
            # cob_move of a copy with the same attributes: its bytes.
            self.write("file_runtime::ReportEvent::Put(field, bytes) => { match field {")
            for number, r in enumerate(refs):
                self.write(f"    {number} => {r}.assign_text_move(&Value::Bytes(bytes.to_vec()), true),")
            self.write('    _ => unreachable!("report field"),')
            self.write("} Vec::new() }")
            # cob_cmp of the control item and its saved copy (cob_field_dup).
            self.write("file_runtime::ReportEvent::Differs(field, bytes) => { let differs = match field {")
            for number, r in enumerate(refs):
                f = self.program.fields[ids[number]]
                # cob_numeric_cmp of two items of one description: as
                # integers below 19 digits (invalid data read as libcob does).
                read = (".operand_integer()" if f.digits < 19 else ".operand()") if f.kind == "number" else ""
                self.write(f"    {number} => {r}{read}.compare(&storage_runtime::copy_of(&{r}, bytes){read}) != std::cmp::Ordering::Equal,")
            self.write('    _ => unreachable!("report field"),')
            self.write("}; vec![differs as u8] }")
            # cob_add_fields: counter = counter + operand, truncated (cob_add, opt 0).
            self.write("file_runtime::ReportEvent::Add(counter, operand) => {")
            self.write("    let value = match operand {")
            for number, r in enumerate(refs):
                self.write(f"        {number} => {r}.operand(),")
            self.write('        _ => unreachable!("report field"),')
            self.write("    };")
            self.write("    match counter {")
            for number, r in enumerate(refs):
                if ids[number] in {c for c, *_ in report.sums}:
                    self.write(f"        {number} => {{ let sum = {r}.operand().plus(&value); {r}.store_truncated(&sum); }}")
            self.write('        _ => unreachable!("report counter"),')
            self.write("    }")
            self.write("    Vec::new()")
            self.write("}")
            # cob_field_init: MOVE ZERO to the counter.
            self.write("file_runtime::ReportEvent::Zero(counter) => { match counter {")
            for number, r in enumerate(refs):
                if ids[number] in {c for c, *_ in report.sums}:
                    self.write(f"    {number} => {r}.assign(&Value::number(\"0\"), false),")
            self.write('    _ => unreachable!("report counter"),')
            self.write("} Vec::new() }")

        self.write("file_runtime::ReportEvent::Write(bytes, lines) => {")
        self.indent += 1
        file = self.files[report.file]
        self.write(f"let status = self.{file}.write_report(bytes, lines);")
        self.write(f'if status != 0 {{ runtime::fail(&format!("report WRITE status {{status:02}} not modelled")); }}')
        status = self.program.files[report.file].status
        destination = f"Some(&mut self.{self.names[status]})" if status else "None"
        self.write(f"file_runtime::file_status(status, {destination}, false, false, false, &|| self.{file}.error_name());")
        self.write("Vec::new()")
        self.indent -= 1
        self.write("}")
        if not (report.controls or report.sums):
            self.write('_ => unreachable!("report event"),')
        self.indent -= 1
        self.write("}")
        self.indent -= 1
        self.write("}")

    def initialize(self, receiver, selected):
        """The VALUE or PICTURE initialization of the selected items."""
        for name, field in self.program.fields.items():
            if not field.picture or field.file_record or field.linkage or not selected(field):
                continue
            if self.external_root(name) is not None:
                # cob_external_addr storage is not initialized (cob_malloc);
                # an inherited GLOBAL item is initialized by its program.
                if getattr(field, "explicit_value", False) and self.program.fields[self.external_root(name)].external:
                    raise CobolError(f"VALUE d'un article EXTERNAL non pris en charge: {field.label}")
                continue
            if not getattr(self.program, "default_byte_init", True) and not getattr(field, "explicit_value", True):
                continue
            cursor = field
            while cursor and not cursor.redefines:
                cursor = self.program.fields.get(cursor.parent)
            if cursor:
                continue
            constructor = "text" if field.initial.string else "number"
            initial = field.initial.text if field.initial.string else numeric_text(field.initial.text)
            value = text_value(initial) if constructor == "text" else f"Value::{constructor}({quoted(initial)})"
            self.write(f"{receiver}.{self.names[name]}.declare(&{value});")
        # A group VALUE fills the whole group as alphanumeric data after its
        # leaves, on every occurrence: GnuCOBOL gives it precedence.
        for name, field in self.program.fields.items():
            if field.group_value is None or not selected(field):
                continue
            if self.external_root(name) is not None:
                if self.program.fields[self.external_root(name)].external:
                    raise CobolError(f"VALUE d'un article EXTERNAL non pris en charge: {field.label}")
                continue
            if any(other.depending for key, other in self.program.fields.items()
                   if key == name or key.startswith(name + ".")):
                raise CobolError(f"VALUE de groupe contenant OCCURS DEPENDING non pris en charge: {field.label}")
            text, fill = field.group_value
            if isinstance(fill, tuple):
                text = (fill[1] * field.size)[:field.size]
            elif fill in {"0", '"', "\xff", "\x00"}:
                text = fill * field.size
            self.write(f"{receiver}.{self.names[name]}.declare(&{text_value(text)});")

    def call_method(self, graph):
        """Bind each USING item of the entry and its subordinates to the CALL
        arguments (output_entry_function); an item the entry or the CALL does
        not pass has no storage (a NULL address for GnuCOBOL)."""
        self.write("fn call(&mut self, unit: &mut RunUnit, arguments: Vec<Value>) -> runtime::Outcome {")
        self.write("    self.call_entry(unit, arguments, 0)")
        self.write("}")
        self.write("fn call_entry(&mut self, unit: &mut RunUnit, arguments: Vec<Value>, entry: usize) -> runtime::Outcome {")
        self.indent += 1
        entries = [(graph.entry, self.program.using)] + [(graph.entry_points[name], using)
                                                         for name, using in getattr(self.program, "entries", [])]
        fields = self.program.fields
        for number, (_, using) in enumerate(entries):
            self.write(f"if entry == {number} {{")
            self.indent += 1
            for name, field in fields.items():
                if not field.linkage:
                    continue
                root = field
                while root.parent:
                    root = fields[root.parent]
                while root.redefines:
                    root = fields[root.redefines]
                rust = self.names[name]
                if root.name not in using:
                    self.write(f"self.{rust} = storage_runtime::unbind(&self.{rust});")
                    continue
                index = using.index(root.name)
                self.write(f"self.{rust} = if arguments.len() > {index} {{ storage_runtime::rebind(&arguments[{index}], "
                           f"{field.offset - root.offset}, &self.{rust}) }} else {{ storage_runtime::unbind(&self.{rust}) }};")
            self.indent -= 1
            self.write("}")
        local = [name for name, field in fields.items() if getattr(field, "local", False) and field.parent is None]
        for name in local:
            # LOCAL-STORAGE: fresh storage (zeroed) initialized at each entry.
            size = fields[name].size
            self.write(f"self.{self.names[name]}.assign_text_move(&Value::Bytes(vec![0; {size}]), true);")
        if local:
            self.initialize("self", lambda field: getattr(field, "local", False))
        # RETURN-CODE keeps its value between CALLs: codegen.c clears it with
        # the program's first initialization only (VALUE ZERO here).
        if len(entries) > 1:
            starts = ", ".join(str(position) for position, _ in entries)
            self.write(f"self.run_at(unit, [{starts}][entry])")
        else:
            self.write("self.run(unit)")
        self.indent -= 1
        self.write("}")
        self.write("/// The program's return value: its RETURN-CODE.")
        self.write("fn return_code(&self) -> Option<i64> {")
        self.write(f"    {'Some(' + self.register + '.integer(' + chr(34) + 'RETURN-CODE' + chr(34) + ') as i64)' if self.register else 'None'}")
        self.write("}")


def divides(expr):
    """Whether an arithmetic expression contains a division."""
    if not isinstance(expr, Expr):
        return False
    return expr.op in {"/", "**"} or any(divides(arg) for arg in expr.args if isinstance(arg, Expr))


def surely_absent(name, present):
    """Same rule as runtime::surely_absent, for a CALL literal."""
    return (bool(name) and all(c.isascii() and (c.isupper() or c.isdigit() or c == "-") for c in name)
            and name not in {"SYSTEM", "EXTFH"} and name not in present)


def generate_unit(emitters):
    """One Rust program for a run unit: main program first, then subprograms.

    A subprogram keeps its storage between CALLs (one instance per program)
    until CANCEL, which closes its open files (dropping the instance) like
    GnuCOBOL's cancel entry; an active program cannot be called or cancelled.
    """
    bodies = []
    for emitter in emitters:
        lines, mapping = emitter.program_lines()
        bodies.append((emitter, lines, mapping))
    head = ["// Generated by cobol2rust. Edit the COBOL input and regenerate.",
            "#![allow(unreachable_code, dead_code, unused_parens, unused_variables, unused_mut)]",
            "mod runtime;", "mod storage_runtime;"]
    if any(emitter.files for emitter in emitters):
        head.append("mod file_runtime;")
    head += ["use runtime::{Value, display};", "struct PerformFrame { through: usize, return_pc: usize }"]
    subprograms = emitters[1:]
    global_uses = any(getattr(emitter.program, "global_uses", None) for emitter in emitters)
    shared = any(emitter.file_registry(name) for emitter in emitters for name in emitter.files)
    unit = ["struct RunUnit {", "    returned: Option<i64>, // return value of the last CALL", "    exit_code: i32, // cob_stop_run status",
            "    callers: Vec<&'static str>, // module names of the active programs, innermost last"]
    for index, emitter in enumerate(subprograms, 1):
        unit += [f"    p{index}: Option<Box<{emitter.struct}>>, // {emitter.program.entry_name}", f"    p{index}_active: bool,"]
        if getattr(emitter.program, "entries", None):
            # Its ENTRY names resolve once its module is loaded (by a CALL).
            unit.append(f"    p{index}_loaded: bool,")
    if global_uses:
        # The active programs with USE GLOBAL, innermost last.
        unit.append("    uses: Vec<(&'static str, Option<Box<dyn GlobalUse>>)>,")
    main_name = quoted(emitters[0].program.entry_name)
    unit += ["}", "impl RunUnit {", "    fn new() -> Self {", "        Self {",
             f"            returned: None, exit_code: 0, callers: vec![{main_name}],"]
    for index, emitter in enumerate(subprograms, 1):
        loaded = f" p{index}_loaded: false," if getattr(emitter.program, "entries", None) else ""
        unit.append(f"            p{index}: None, p{index}_active: false,{loaded}")
    if global_uses:
        unit.append("            uses: Vec::new(),")
    unit += ["        }", "    }",
             "    /// None: no such program was converted with this run unit.",
             "    fn call(&mut self, name: &str, arguments: Vec<Value>) -> Option<runtime::Outcome> {",
             "        match name {"]
    def cancels_files(emitter):
        return any(emitter.file_registry(name) and not emitter.program.files[name].global_owner for name in emitter.files)
    for index, emitter in enumerate(subprograms, 1):
        if getattr(emitter.program, "initial", False):
            # INITIAL: the program is cancelled when it returns.
            kept = "program.cancel_files();" if cancels_files(emitter) else "drop(program);"
        else:
            kept = f"self.p{index} = Some(program);"
        entries = getattr(emitter.program, "entries", [])
        for number, name in enumerate([emitter.program.entry_name, *(entry for entry, _ in entries)]):
            guard = f" if self.p{index}_loaded" if number else ""
            unit += [f"            {quoted(name)}{guard} => {{",
                     f"                if self.p{index}_active {{ self.recursive({quoted(emitter.program.entry_name)}); }}",
                     f"                let mut program = self.p{index}.take().unwrap_or_else(|| Box::new({emitter.struct}::new()));",
                     f"                self.p{index}_active = true;",
                     f"                self.callers.push({quoted(emitter.program.entry_name)});",
                     *([f"                self.p{index}_loaded = true;"] if entries else []),
                     f"                let outcome = program.call_entry(self, arguments, {number});",
                     "                self.returned = program.return_code();",
                     f"                self.p{index}_active = false;",
                     "                self.callers.pop();",
                     f"                {kept}",
                     "                Some(outcome)",
                     "            }"]
    # The main program is active for the whole run: calling it is recursive.
    if emitters[0].program.entry_name not in {e.program.entry_name for e in subprograms}:
        unit.append(f"            {main_name} => self.recursive({main_name}),")
    for name, _ in getattr(emitters[0].program, "entries", []):
        unit.append(f"            {quoted(name)} => self.recursive({main_name}),")
    unit += ["            _ => None,", "        }", "    }",
             "    /// cob_fatal_error (COB_FERROR_RECURSIVE): a program without RECURSIVE called while active.",
             "    fn recursive(&self, callee: &str) -> ! {",
             "        let caller = self.callers.last().copied().unwrap_or(\"\");",
             "        runtime::fatal_error(format!(\"recursive CALL from '{caller}' to '{callee}' which is NOT RECURSIVE\").as_bytes())",
             "    }",
             "    /// CANCEL: the next CALL finds the program in its initial state.",
             "    fn cancel(&mut self, name: &str) {",
             "        match name {"]
    # P_cancel of codegen.c: cob_fatal_error (COB_FERROR_CANCEL) for an
    # active module, the main program included.
    active = 'runtime::fatal_error(b"attempt to CANCEL active program")'
    if emitters[0].program.entry_name not in {e.program.entry_name for e in subprograms}:
        unit.append(f"            {quoted(emitters[0].program.entry_name)} => {active},")
    for index, emitter in enumerate(subprograms, 1):
        cancel = f"if let Some(program) = self.p{index}.take() {{ program.cancel_files(); }}" \
            if cancels_files(emitter) else f"self.p{index} = None;"
        unit.append(f"            {quoted(emitter.program.entry_name)} => {{ if self.p{index}_active {{ {active}; }} {cancel} }},")
    unit += ["            _ => {}", "        }", "    }"]
    if global_uses:
        unit += ["    /// <owner>_ (section label): a GLOBAL USE procedure of an active program.",
                 "    fn global_use(&mut self, owner: &str, section: &str) -> runtime::Outcome {",
                 "        let index = self.uses.iter().rposition(|(name, _)| *name == owner).unwrap_or_else(|| runtime::fail(\"USE GLOBAL of an inactive program\"));",
                 "        let mut program = self.uses[index].1.take().unwrap_or_else(|| runtime::fail(\"USE GLOBAL procedure re-entered not modelled\"));",
                 "        let outcome = program.global_use(self, section);",
                 "        self.uses[index].1 = Some(program);",
                 "        outcome",
                 "    }"]
    unit.append("}")
    if global_uses:
        unit += ["trait GlobalUse { fn global_use(&mut self, unit: &mut RunUnit, section: &str) -> runtime::Outcome; }"]
    lines = head + unit
    main_mapping = []
    for position, (emitter, body, mapping) in enumerate(bodies):
        offset = len(lines)
        if position == 0:
            main_mapping = [{**item, "rust_line": item["rust_line"] + offset} for item in mapping]
        lines += body
    unchecked = "storage_runtime::set_unchecked_data(); " if getattr(emitters[0].program, "unchecked_data", False) else ""
    if getattr(emitters[0].program, "runtime_checks", False):
        unchecked += "storage_runtime::set_runtime_checks(); "
    # A module runs as cobcrun calls it: its main entry, no arguments.
    start = "program.call(&mut unit, Vec::new());" if emitters[0].module else "program.run(&mut unit);"
    run = f"let mut unit = RunUnit::new(); let mut program = {emitters[0].struct}::new(); {start}"
    # cob_terminate_routines: the warnings for files left open, then the files
    # closed (dropped with the program), also after a fatal runtime error.
    files = any(emitter.files for emitter in emitters)
    messages = " file_runtime::exit_messages();" if files else ""
    released = " file_runtime::release_shared();" if shared else ""
    lines.append(f"fn main() {{ {unchecked}let code = match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {{ {run}{messages} "
                 "unit.exit_code })) { Ok(code) => code, "
                 "Err(payload) if payload.is::<runtime::FatalExit>() => 1, Err(payload) => std::panic::resume_unwind(payload) };"
                 f"{released} if code != 0 {{ std::process::exit(code); }} }}")
    return "\n".join(lines) + "\n", main_mapping
