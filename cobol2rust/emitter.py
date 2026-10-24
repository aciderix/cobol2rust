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


class Emitter:
    def __init__(self, program: Program, struct="Program", subprogram=False, called=None, present=()):
        self.program = program
        from .frontend import Parser
        self.program_functions = Parser.FUNCTIONS
        self.struct = struct
        self.subprogram = subprogram
        # CALL targets converted with this run unit (literal names).
        self.called = set(called or ())
        # Programs of the call path left unconverted: a CALL of one cannot be modelled.
        self.present = sorted(set(present) - self.called)
        self.names = {name: f"f{i}" for i, name in enumerate(program.fields)}
        self.blocks = program.blocks or [ProcedureBlock(None, None, program.entry),
                                        *(ProcedureBlock(name, None, body) for name, body in program.paragraphs.items())]
        self.files = {name: f"file{i}" for i, name in enumerate(program.files)}
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
        if e.op == "all":
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

    def literal(self, token):
        return Expr("text" if token.string else "number", (token.text,))

    def expression(self, e):
        op, args = e.op, e.args
        if op == "var":
            return self.reference(args[0]) + ".snapshot()"
        if op == "shared":
            return f"{self.shared}.clone()"
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
        textual = name in {"UPPER-CASE", "LOWER-CASE", "REVERSE", "ORD", "NUMVAL", "NUMVAL-C", "LENGTH"}
        values = []
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
                data, scale = literal.args[0].rstrip(" "), 0
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
            if text.op == "text" and (descriptor.scale or not text.args[0].isascii() or
                                      not text.args[0].isdigit() or len(text.args[0]) != descriptor.digits):
                raise CobolError("comparaison mixte avec littéral texte limitée aux entiers et chiffres de même largeur; copier le littéral vers PIC X pour éviter les optimisations natives non modélisées")
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
        source_kind = self.kind(expr)
        conversions = []
        for ref in targets:
            conversions.append(None)
            field = self.program.fields[ref.name]
            destination = "text" if ref.start is not None else field.kind
            if ref.start is None and self.is_alphabetic(field) and source_kind in {"number", "edited"}:
                raise CobolError("MOVE numérique vers alphabétique (PIC A) invalide, comme pour GnuCOBOL")
            if move and source_kind == "text" and destination in {"number", "edited"}:
                if expr.figurative_space:
                    raise CobolError("MOVE de la constante figurative SPACE vers nombre ou champ édité non pris en charge")
                if destination == "number" and field.usage == "INDEX":
                    raise CobolError("MOVE texte vers index non pris en charge")
                if destination == "number" and expr.op != "var":
                    raise CobolError("MOVE littéral texte vers nombre non pris en charge; optimisations natives distinctes des champs PIC X")
                source_ref = expr.args[0] if expr.op == "var" else None
                raw_group = (source_ref is not None and source_ref.start is None and
                             not self.program.fields[source_ref.name].picture)
                conversions[-1] = "raw_text" if raw_group else "parsed_text"
                continue
            edited_text = ref.start is None and bool(field.alnum_edit)
            if edited_text and expr.op == "all":
                raise CobolError("MOVE ALL vers alphanumérique édité non pris en charge (remplissage natif brut)")
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
            if conversion == "deedit":
                self.write(f"{self.reference(ref)}.move_deedited(&{temp});")
            elif conversion in {"raw_text", "parsed_text"}:
                self.write(f"{self.reference(ref)}.assign_text_move(&{temp}, {str(conversion == 'raw_text').lower()});")
            elif conversion == "all":
                receiver = self.unique()
                self.write(f"let mut {receiver} = {self.reference(ref)}.clone();")
                self.write(f"let all = Value::Bytes({byte_pattern(expr.args[0])}.iter().cycle().take({receiver}.text_size()).copied().collect());")
                self.write(f"{receiver}.assign(&all, false);")
            elif conversion == "zero":
                receiver = self.unique()
                self.write(f"let mut {receiver} = {self.reference(ref)}.clone();")
                self.write(f"let zeros = Value::Bytes(vec![b'0'; {receiver}.text_size()]);")
                self.write(f"{receiver}.assign(&zeros, false);")
            else:
                value = (f"{temp}.numeric_move_text({str(conversion == 'group').lower()})"
                         if conversion in {"group", "integer"} else
                         f"Value::text({quoted(self.move_literal_digits(expr))})" if conversion == "literal" else temp)
                field = self.program.fields[ref.name]
                if conversion is None and truncating and ref.start is None and field.kind == "edited":
                    self.write(f"{self.reference(ref)}.move_edited(&{value});")
                elif conversion is None and truncating and ref.start is None and field.kind == "number":
                    method = "move_number"
                    if self.storage_usage(field) == "Packed":
                        self.check_packed_literal_move(expr, field)
                        if (expr.op == "var" and
                                self.storage_usage(self.program.fields[expr.args[0].name]) == "Binary"):
                            method = "move_binary_to_packed"
                    self.write(f"{self.reference(ref)}.{method}(&{value});")
                else:
                    self.write(f"{self.reference(ref)}.assign(&{value}, {str(rounded).lower()});")
            if ref in negative_zero:
                self.write(f"{self.reference(ref)}.negative_zero();")

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

    def depending(self, file_name, mutable):
        name = self.program.files[file_name].depending
        return f"Some(&{'mut ' if mutable else ''}self.{self.names[name]})" if name else "None"

    def relative_key(self, file_name, mutable):
        key = self.program.files[file_name].relative_key
        if key is None:
            return "None"
        return f"Some(&{'mut ' if mutable else ''}self.{self.names[key]})"

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
            handler = f"match self.{self.files[file_name]}.last_open_mode() {{ {cases} _ => None }}"
        self.write(f"let handler: Option<usize> = {handler};")
        invalid = str(getattr(self, "io_invalid", False)).lower()
        self.write(f"file_runtime::file_status({status}, {destination}, {str(eof_handled).lower()}, {invalid}, handler.is_some());")

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
                self.write(f"let status = self.{self.files[name]}.open({quoted(mode)});")
                self.file_status(name, "status")
        elif op == "close":
            for name, mode in a[0]:
                if mode in {"reel", "no_rewind"}:
                    self.write(f"let status = self.{self.files[name]}.close_unit({str(mode == 'no_rewind').lower()});")
                else:
                    self.write(f"let status = self.{self.files[name]}.close({str(mode == 'lock').lower()});")
                self.file_status(name, "status")
        elif op == "rewrite":
            name, record, value, _, _ = a
            if value:
                self.assignment(value, [record], False)
            organization = self.program.files[name].organization
            key = f"{self.relative_key(name, False)}, " if organization == "RELATIVE" else ""
            size = self.program.fields[record].size
            self.write(f"let status = self.{self.files[name]}.rewrite(&self.{self.files[name]}_area, {size}, {key}{self.depending(name, False)});")
            self.file_status(name, "status")
        elif op == "delete":
            name = a[0]
            if self.program.files[name].organization == "INDEXED":
                self.write(f"let status = self.{self.files[name]}.delete(&self.{self.files[name]}_area);")
            else:
                self.write(f"let status = self.{self.files[name]}.delete({self.relative_key(name, False)});")
            self.file_status(name, "status")
        elif op == "start":
            name, index, condition, _, _ = a
            if index is not None:
                self.write(f"let status = self.{self.files[name]}.start(file_runtime::StartCondition::{condition}, {index[0]}, {index[1]}, &self.{self.files[name]}_area);")
            else:
                key = self.names[self.program.files[name].relative_key]
                self.write(f"let status = self.{self.files[name]}.start(file_runtime::StartCondition::{condition}, &self.{key});")
            self.file_status(name, "status")
        elif op == "write":
            name, record, value, advancing, _, _ = a
            if value:
                self.assignment(value, [record], False)
            control = "None"
            if advancing is not None:
                direction, count = advancing
                variant = direction.title() + ("Page" if count is None else "Lines")
                argument = "" if count is None else f"({count})"
                control = f"Some(file_runtime::Advance::{variant}{argument})"
            if self.program.files[name].organization == "RELATIVE":
                control = self.relative_key(name, True)
            size = self.program.fields[record].size
            if self.program.files[name].organization == "INDEXED":
                if advancing is not None:
                    raise CobolError("WRITE ADVANCING sur un fichier INDEXED")
                self.write(f"let status = self.{self.files[name]}.write(&self.{self.files[name]}_area, {size}, {self.depending(name, False)});")
            else:
                self.write(f"let status = self.{self.files[name]}.write(&self.{self.files[name]}_area, {size}, {control}, {self.depending(name, False)});")
            self.file_status(name, "status")
        elif op == "display":
            values = []
            for e in a[0]:
                if e.op == "all":
                    # DISPLAY shows an ALL literal or a figurative constant once.
                    values.append("Value::Bytes(vec![" + ", ".join(str(ord(c)) for c in e.args[0]) + "])")
                    continue
                if e.op not in {"text", "number", "var"}:
                    raise CobolError("DISPLAY accepte uniquement champs et littéraux simples")
                # Preserve the spelling of numeric literals (leading zeros, trailing fractional zeros).
                values.append(f"Value::text({quoted(e.args[0])})" if e.op == "number" else self.expression(e))
            function = "runtime::display_error" if len(a) > 2 and a[2] == "stderr" else "display"
            self.write(f"{function}(&[{', '.join(values)}], {str(a[1]).lower()});")
        elif op in {"assign", "move"}:
            self.assignment(*a, move=op == "move")
        elif op == "compute":
            shared, items = a
            if shared is not None:
                if self.kind(shared) != "number":
                    raise CobolError("calcul arithmétique requiert des nombres")
                self.shared = self.unique()
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
                self.assignment(expr, [ref], rounded)
        elif op == "accept":
            self.write(f"{self.reference(a[0])}.accept();")
        elif op == "accept_omitted":
            self.write("runtime::accept_omitted();")
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
            self.write(f"self.{self.files[name]}.release(&self.{self.files[name]}_area);")
        elif op == "set_switch":
            for number in a[0]:
                self.write(f"runtime::set_switch({number}, {str(a[1]).lower()});")
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
        field = self.program.fields[target.name]
        if target.start is None and field.kind == "number" and field.usage != "DISPLAY":
            raise CobolError("INSPECT d'un champ binaire, packé ou index non pris en charge")
        modes = {"all": "All", "leading": "Leading", "first": "First", "trailing": "Trailing"}
        for clause in clauses:
            self.write("{")
            self.indent += 1
            if clause[0] == "converting":
                _, source, to, region = clause
                self.write(f"let mut inspect = storage_runtime::Inspect::init_converting(&{self.reference(target)});")
                items = [("convert", source, to, region)]
            else:
                replacing = clause[0] == "replacing"
                self.write(f"let mut inspect = storage_runtime::Inspect::init(&{self.reference(target)}, {str(replacing).lower()});")
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
            self.write("return runtime::Outcome::Return;" if self.subprogram else "return runtime::Outcome::Stop;")
        elif op == "stop_run":
            self.write("return runtime::Outcome::Stop;")
        elif op == "goback":
            self.write("return runtime::Outcome::Return;" if self.subprogram else "return runtime::Outcome::Stop;")
        elif op == "exit_program":
            self.write("return runtime::Outcome::Return;" if self.subprogram else f"pc = {a[0]};")
        elif op == "call_program":
            target, arguments, continuation, exception, success = a
            values = []
            for mode, ref in arguments:
                # BY REFERENCE passes an address: a variable group's LINKAGE
                # item may address its whole allocation, not only the active part.
                view = self.reference(ref, active=mode == "CONTENT" or ref.start is not None) + ".clone()"
                values.append(f"storage_runtime::content_copy(&{view})" if mode == "CONTENT" else view)
            # A program not found raises EC-PROGRAM-NOT-FOUND, handled by
            # ON EXCEPTION; without it GnuCOBOL stops the run unit.
            not_found = (f"pc = {exception};" if exception is not None
                         else "runtime::fail(\"CALL of a program not found, without ON EXCEPTION\");")
            if target[0] == "literal" and target[1] not in self.called:
                if not surely_absent(target[1], self.present):
                    raise CobolError(f"CALL {target[1]}: programme non converti ou routine système non pris en charge")
                self.write(not_found)
                return
            name = quoted(target[1]) if target[0] == "literal" else f"{self.reference(target[1])}.bytes()"
            if target[0] == "dynamic":
                self.write(f"let name = String::from_utf8_lossy(&{name}).trim_end_matches(' ').to_string();")
                name = "&name"
            self.write(f"match unit.call({name}, vec![{', '.join(values)}]) {{")
            self.indent += 1
            self.write("Some(runtime::Outcome::Stop) => return runtime::Outcome::Stop,")
            self.write(f"Some(runtime::Outcome::Return) => pc = {success},")
            if target[0] == "dynamic":
                present = ", ".join(quoted(name) for name in [*self.present, *sorted(self.called)])
                self.write(f"None if runtime::surely_absent(&name, &[{present}]) => {{ {not_found} }}")
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
            self.write(f"self.{self.files[name]}.init(vec![{', '.join(specs)}]);")
            self.write(f"pc = {following};")
        elif op == "sort_using":
            # cob_file_sort_using: OPEN INPUT, READ each record into the SD
            # area (cob_copy_check) and release it, CLOSE. The user's FILE
            # STATUS is not updated; a file that fails to open is skipped.
            name, files, following = a
            sort = self.files[name]
            for using in files:
                rust = self.files[using]
                self.write(f"if self.{rust}.open(\"INPUT\") < 10 {{")
                self.indent += 1
                self.write(f"while self.{rust}.read(&mut self.{rust}_area, None) < 10 {{")
                self.write(f"    self.{sort}.release_from(&self.{rust}_area, &mut self.{sort}_area);")
                self.write("}")
                self.write(f"self.{rust}.close(false);")
                self.indent -= 1
                self.write("}")
            self.write(f"pc = {following};")
        elif op == "sort_giving":
            # cob_file_sort_giving: OPEN OUTPUT each file, WRITE every record to
            # each one opened (record area at its maximum size), CLOSE them.
            name, files, following = a
            sort = self.files[name]
            opened = self.unique()
            self.write(f"let mut {opened} = vec![false; {len(files)}];")
            for index, giving in enumerate(files):
                self.write(f"{opened}[{index}] = self.{self.files[giving]}.open(\"OUTPUT\") < 10;")
            initially = self.unique()
            self.write(f"let {initially} = {opened}.clone();")
            self.write(f"while self.{sort}.retrieve(&mut self.{sort}_area) == 0 {{")
            self.indent += 1
            for index, giving in enumerate(files):
                rust, spec = self.files[giving], self.program.files[giving]
                self.write(f"if {opened}[{index}] {{")
                self.write(f"    self.{rust}_area.assign(&Value::Bytes(self.{sort}_area.bytes()), false);")
                self.write(f"    if self.{rust}.write(&self.{rust}_area, {spec.record_max}, None, None) >= 30 {{ {opened}[{index}] = false; }}")
                self.write("}")
            self.indent -= 1
            self.write("}")
            for index, giving in enumerate(files):
                self.write(f"if {initially}[{index}] {{ self.{self.files[giving]}.close(false); }}")
            self.write(f"pc = {following};")
        elif op == "sort_close":
            self.write(f"self.{self.files[a[0]]}.close();")
            self.write(f"pc = {a[1]};")
        elif op == "return_sort":
            name, into, at_end, not_at_end, = a
            sort = self.files[name]
            self.write(f"if self.{sort}.retrieve(&mut self.{sort}_area) == 0 {{")
            self.indent += 1
            if into:
                record = self.names[self.program.files[name].record]
                self.write(f"let record = self.{record}.snapshot();")
                self.write(f"{self.reference(into)}.assign(&record, false);")
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
            self.io_invalid = invalid is not None
            self.statement(stmt)
            self.io_handlers, self.io_invalid = None, False
            success = continuation if valid is None else valid
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
        elif op == "debug_line":
            self.alphanumeric_move(self.debug_item("DEBUG-LINE"), self.byte_vector(f"{a[0]:6d}"[-6:]))
            self.write(f"pc = {a[1]};")
        elif op == "debug_contents":
            contents, continuation = a
            if isinstance(contents, tuple):
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
                    self.write(f"let {status} = self.{self.files[name]}.read_key(&mut {area}, {random[0]}, {random[1]}, {depending});")
                else:
                    self.write(f"let {status} = self.{self.files[name]}.read_next(&mut {area}, {depending});")
            elif spec.organization != "RELATIVE":
                self.write(f"let {status} = self.{self.files[name]}.read(&mut {area}, {depending});")
            elif random:
                self.write(f"let {status} = self.{self.files[name]}.read_key(&mut {area}, &self.{self.names[spec.relative_key]}, {depending});")
            else:
                self.write(f"let {status} = self.{self.files[name]}.read_next(&mut {area}, {self.relative_key(name, True)}, {depending});")
            self.io_invalid = handled and keyed
            self.file_status(name, status, handled and not keyed)
            self.io_handlers, self.io_invalid = None, False
            self.write(f"if matches!({status}, 0 | 4 | 6 | 9) {{")
            self.indent += 1
            if into:
                if spec.organization in {"SEQUENTIAL", "RELATIVE", "INDEXED"}:
                    # READ INTO moves the record as read: its size is the size read.
                    self.write(f"let record = Value::Bytes(self.{self.files[name]}_area.bytes()[..self.{self.files[name]}.last_read_size()].to_vec());")
                else:
                    self.write(f"let record = self.{record}.snapshot();")
                self.write(f"{self.reference(into)}.assign(&record, false);")
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
        if self.program.using and not self.subprogram:
            raise CobolError("programme principal avec PROCEDURE DIVISION USING non pris en charge")
        graph = ControlGraph(self.program, self.blocks)
        self.write(f"struct {self.struct} {{")
        self.indent += 1
        for name in self.names:
            self.write(f"{self.names[name]}: Value, // {name} PIC {self.program.fields[name].picture}")
        for name, rust_name in self.files.items():
            organization = self.program.files[name].organization
            kind = {"RELATIVE": "RelativeFile", "INDEXED": "IndexedFile", "SORT": "SortFile"}.get(organization, "CobolFile")
            self.write(f"{rust_name}: file_runtime::{kind}, // {name}")
            self.write(f"{rust_name}_area: Value, // FD area of {name}, largest record")
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
        self.write("let mut result = Self {")
        self.indent += 1
        for name, field in self.program.fields.items():
            value = f"Value::View(storage_runtime::View {{ memory: memory.clone(), offset: {field.offset}, size: {field.size}, kind: {self.storage_kind(field)}, dimensions: {self.dimensions(field.dimensions)}, initializers: {self.initializers(field)} }})"
            self.write(f"{self.names[name]}: {value},")
        for name, rust_name in self.files.items():
            spec = self.program.files[name]
            limits = f"{spec.record_min}, {spec.record_max}"
            if spec.sort:
                self.write(f"{rust_name}: file_runtime::SortFile::new({spec.record_max}),")
            elif spec.organization == "RELATIVE":
                self.write(f"{rust_name}: file_runtime::RelativeFile::new({quoted(spec.path.text)}, {str(spec.optional).lower()}, {quoted(spec.access)}, {limits}),")
            elif spec.organization == "INDEXED":
                keys = ", ".join(f"file_runtime::IndexKey {{ offset: {offset}, size: {size}, duplicates: {str(duplicates).lower()} }}"
                                 for _, offset, size, duplicates in [spec.record_key, *spec.alternate_keys])
                self.write(f"{rust_name}: file_runtime::IndexedFile::new({quoted(spec.path.text)}, {str(spec.optional).lower()}, {quoted(spec.access)}, {limits}, vec![{keys}]),")
            else:
                self.write(f"{rust_name}: file_runtime::CobolFile::new({quoted(spec.path.text)}, {str(spec.optional).lower()}, {quoted(spec.organization)}, {limits}),")
            offset = self.program.fields[spec.record].offset
            self.write(f"{rust_name}_area: Value::View(storage_runtime::View {{ memory: memory.clone(), offset: {offset}, size: {spec.record_max}, kind: storage_runtime::Kind::Text, dimensions: vec![], initializers: vec![] }}),")
        alters = len(self.program.alters)
        self.write(f"alter: vec![0; {alters}],")
        self.write(f"alter_saved: vec![0; {alters}],")
        self.indent -= 1
        self.write("};")
        for name, field in self.program.fields.items():
            if not field.picture or field.file_record or field.linkage:
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
            self.write(f"result.{self.names[name]}.declare(&{value});")
        # A group VALUE fills the whole group as alphanumeric data after its
        # leaves, on every occurrence: GnuCOBOL gives it precedence.
        for name, field in self.program.fields.items():
            if field.group_value is None:
                continue
            if any(other.depending for key, other in self.program.fields.items()
                   if key == name or key.startswith(name + ".")):
                raise CobolError(f"VALUE de groupe contenant OCCURS DEPENDING non pris en charge: {field.label}")
            text, fill = field.group_value
            if isinstance(fill, tuple):
                text = (fill[1] * field.size)[:field.size]
            elif fill in {"0", '"', "\xff", "\x00"}:
                text = fill * field.size
            self.write(f"result.{self.names[name]}.declare(&{text_value(text)});")
        self.write("result")
        self.indent -= 1
        self.write("}")
        if self.subprogram:
            self.call_method()
        self.write("fn run(&mut self, unit: &mut RunUnit) -> runtime::Outcome {")
        self.indent += 1
        collating = getattr(self.program, "collating", None)
        if collating:
            # OBJECT-COMPUTER PROGRAM COLLATING SEQUENCE: the alphabet's weights.
            self.write(f"static COLLATING: [u8; 256] = [{', '.join(str(w) for w in collating)}];")
        self.write(f"let _collating = runtime::CollatingGuard::new({'Some(&COLLATING)' if collating else 'None'});")
        self.write(f"let mut pc: usize = {graph.entry};")
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
        self.indent -= 1
        self.write("}")
        return self.lines, self.mapping

    def call_method(self):
        """Bind each USING item and its subordinates to the CALL arguments."""
        self.write("fn call(&mut self, unit: &mut RunUnit, arguments: Vec<Value>) -> runtime::Outcome {")
        self.indent += 1
        using = self.program.using
        if using:
            self.write(f"if arguments.len() < {len(using)} {{ runtime::fail(\"CALL with fewer arguments than PROCEDURE DIVISION USING not modelled\"); }}")
        fields = self.program.fields
        for name, field in fields.items():
            if not field.linkage:
                continue
            root = field
            while root.parent:
                root = fields[root.parent]
            while root.redefines:
                root = fields[root.redefines]
            index = using.index(root.name)
            rust = self.names[name]
            self.write(f"self.{rust} = storage_runtime::rebind(&arguments[{index}], {field.offset - root.offset}, &self.{rust});")
        self.write("self.run(unit)")
        self.indent -= 1
        self.write("}")


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
    unit = ["struct RunUnit {"]
    for index, emitter in enumerate(subprograms, 1):
        unit += [f"    p{index}: Option<Box<{emitter.struct}>>, // {emitter.program.entry_name}", f"    p{index}_active: bool,"]
    unit += ["}", "impl RunUnit {", "    fn new() -> Self {", "        Self {"]
    for index, _ in enumerate(subprograms, 1):
        unit.append(f"            p{index}: None, p{index}_active: false,")
    unit += ["        }", "    }",
             "    /// None: no such program was converted with this run unit.",
             "    fn call(&mut self, name: &str, arguments: Vec<Value>) -> Option<runtime::Outcome> {",
             "        match name {"]
    for index, emitter in enumerate(subprograms, 1):
        unit += [f"            {quoted(emitter.program.entry_name)} => {{",
                 f"                if self.p{index}_active {{ runtime::fail(\"CALL of an active program (recursion) not modelled\"); }}",
                 f"                let mut program = self.p{index}.take().unwrap_or_else(|| Box::new({emitter.struct}::new()));",
                 f"                self.p{index}_active = true;",
                 "                let outcome = program.call(self, arguments);",
                 f"                self.p{index}_active = false;",
                 f"                self.p{index} = Some(program);",
                 "                Some(outcome)",
                 "            }"]
    unit += ["            _ => None,", "        }", "    }",
             "    /// CANCEL: the next CALL finds the program in its initial state.",
             "    fn cancel(&mut self, name: &str) {",
             "        match name {"]
    for index, emitter in enumerate(subprograms, 1):
        unit.append(f"            {quoted(emitter.program.entry_name)} => {{ if self.p{index}_active {{ runtime::fail(\"CANCEL of an active program\"); }} self.p{index} = None; }},")
    unit += ["            _ => {}", "        }", "    }", "}"]
    lines = head + unit
    main_mapping = []
    for position, (emitter, body, mapping) in enumerate(bodies):
        offset = len(lines)
        if position == 0:
            main_mapping = [{**item, "rust_line": item["rust_line"] + offset} for item in mapping]
        lines += body
    lines.append(f"fn main() {{ let mut unit = RunUnit::new(); let mut program = {emitters[0].struct}::new(); program.run(&mut unit); }}")
    return "\n".join(lines) + "\n", main_mapping
