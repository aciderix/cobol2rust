"""Data division parsing, with explicit storage hierarchy and condition names."""
import re

from .frontend import Condition, ConstantToken, Field, FloatLiteralToken, Token, VERBS

USAGES = {"DISPLAY", "COMP", "COMPUTATIONAL", "BINARY", "COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL", "COMP-4", "COMPUTATIONAL-4",
          "INDEX", "COMP-5", "COMPUTATIONAL-5", "BINARY-CHAR", "BINARY-SHORT", "BINARY-LONG", "BINARY-DOUBLE",
          "BINARY-C-LONG", "SIGNED-SHORT", "UNSIGNED-SHORT", "SIGNED-INT", "UNSIGNED-INT", "SIGNED-LONG",
          "UNSIGNED-LONG", "COMP-6", "COMPUTATIONAL-6", "POINTER",
          "COMP-1", "COMPUTATIONAL-1", "FLOAT-SHORT", "COMP-2", "COMPUTATIONAL-2", "FLOAT-LONG",
          "COMP-X", "COMPUTATIONAL-X", "COMP-N", "COMPUTATIONAL-N"}
# field.c: a PIC X(n) COMP-X / COMP-N item has PIC 9(pic_digits[n - 1]) on n
# bytes; a numeric PICTURE gets the bytes of compute_size's table.
PIC_DIGITS = [2, 4, 7, 9, 12, 14, 16, 18]
COMP_X_BYTES = [(2, 1), (4, 2), (7, 3), (9, 4), (12, 5), (14, 6), (16, 7), (19, 8)]
# Binary floating point: C float and double (field.c, CB_USAGE_FLOAT/DOUBLE),
# with the attribute digits and scale of codegen.c (15/8 and 34/17).
FLOAT_USAGES = {"COMP-1": "COMP-1", "COMPUTATIONAL-1": "COMP-1", "FLOAT-SHORT": "COMP-1",
                "COMP-2": "COMP-2", "COMPUTATIONAL-2": "COMP-2", "FLOAT-LONG": "COMP-2"}
FLOAT_PICTURES = {"COMP-1": "S9(7)V9(8)", "COMP-2": "S9(17)V9(17)"}
# field.c validate_field_1: BINARY-CHAR/SHORT/LONG/DOUBLE are COMP-5 with the
# digits of cb_build_binary_picture, SIGNED unless UNSIGNED follows.
FIXED_BINARY_DIGITS = {"BINARY-CHAR": 2, "BINARY-SHORT": 4, "BINARY-LONG": 9, "BINARY-DOUBLE": 18,
                       "BINARY-C-LONG": 18}
# validate_field_1: C type usages are COMP-5 with the picture of a fixed binary.
C_TYPE_USAGES = {"SIGNED-SHORT": (4, True), "UNSIGNED-SHORT": (4, False), "SIGNED-INT": (9, True),
                 "UNSIGNED-INT": (9, False), "SIGNED-LONG": (18, True), "UNSIGNED-LONG": (18, False)}


def literal(p):
    negative = p.accept("-")
    positive = not negative and p.accept("+")
    # validate_move: an explicit sign needs a signed receiver.
    p.literal_signed = bool(negative or positive)
    token = p.take()
    if token.string:
        if negative:
            p.error("signe sur un littéral texte")
        return token
    if token.key in {"ZERO", "ZEROS", "ZEROES"}:
        token = Token("0", token.line)
    elif token.key in {"SPACE", "SPACES"}:
        token = Token(" ", token.line, True)
    elif token.key in {"QUOTE", "QUOTES"}:
        token = Token('"', token.line, True)
    elif token.key in getattr(p, "symbolic", {}) and not p.candidates(token.key):
        token = Token(chr(p.symbolic[token.key]), token.line, True)
    elif token.key in {"HIGH-VALUE", "HIGH-VALUES"}:
        token = Token(getattr(p, "high_value", "\xff"), token.line, True)
    elif token.key in {"LOW-VALUE", "LOW-VALUES"}:
        token = Token(getattr(p, "low_value", "\x00"), token.line, True)
    elif re.fullmatch(r"[+-](?:\d+(?:\.\d+)?|\.\d+)", token.text) and not (negative or positive):
        # A signed literal token: a level 78 value, or a sign touching digits.
        p.literal_signed = True
        token = Token(token.text.lstrip("+"), token.line)
    elif not re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", token.text):
        p.error("littéral attendu")
    if negative:
        token = Token("-" + token.text, token.line, token.string)
    return token


# cobc tree.c valid_char_order: PRECEDENCE[current][seen] allows the current
# symbol type after a symbol type already seen (standard PICTURE precedence).
PRECEDENCE = [list(map(int, row.split())) for row in """
1 1 1 0 1 0 0 1 0 1 1 1 1 1 1 1 1 0 0 1 0 1 0 1 0
1 1 1 0 1 0 0 1 0 1 1 1 1 1 1 1 0 0 0 1 0 1 0 0 0
1 1 0 0 1 0 0 1 0 1 0 1 0 1 0 1 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 0 0 0 1 1 1 1 0 0 1 1 1 0 0 0 1 1 1 0 0 0
1 1 1 0 0 0 0 1 1 1 1 0 0 1 1 1 0 0 0 1 1 1 0 0 0
0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 1 0 0 0 0 1 1 0 0 0 0 1 0 0 0 1 1 1 0 0 0
1 1 0 0 1 0 0 1 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 1 0 0 1 0 1 1 0 0 0 0 0 0 0 0 1 0 1 0 0 0
1 1 0 0 0 0 0 1 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 0 0 0 1 0 0 0 1 1 0 0 0 0 0 0 1 0 0 0 0 0
1 1 0 0 1 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0
1 1 1 0 1 0 0 0 0 0 0 0 0 1 1 0 0 0 0 1 0 0 0 0 0
1 1 1 1 1 0 0 1 0 1 0 1 0 1 0 1 1 1 1 1 0 1 0 0 1
1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 1 1 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 0 0 1 0 0 1 0 1 0 1 0 1 0 1 0 0 1 0 1 0 0 0 0
1 1 0 0 1 0 0 1 0 1 0 1 0 1 0 1 0 0 1 0 1 0 0 0 0
0 0 0 0 1 0 0 1 0 0 0 0 0 0 0 0 0 0 1 1 0 1 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0
1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0
1 1 1 0 1 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0
""".strip().splitlines()]


def valid_char_order(symbols):
    """cobc's find_floating_insertion_str, char_to_precedence_idx and
    valid_char_order for the default currency $, decimal point . and comma."""
    simple = set("B0/,")
    first = last = None
    previous, floating = None, " "
    index = 0
    while index < len(symbols):
        c, n = symbols[index]
        if first is None and c in "+-$":
            if previous is not None and symbols[previous][0] == c:
                first, floating = previous, c
                index += 1
                continue
            if n > 1:
                first, floating = index, c
                index += 1
                continue
        if first is None and c not in simple:
            previous = index
        elif first is not None and not (c in simple or c == floating):
            last = index - 1
            break
        index += 1
    if index == len(symbols) and first is not None:
        last = index - 1
    elif index < len(symbols) and symbols[index][0] in ".V":
        if all(c in simple or c == floating for c, _ in symbols[index + 1:]):
            last = len(symbols) - 1
    seen, before_point, non_p = set(), True, False
    for position, (c, n) in enumerate(symbols):
        for _ in range(2 if n > 1 else 1):
            floating_here = first is not None and last is not None and first <= position <= last
            if c in "B0/":
                kind = 0
            elif c in ".,":
                kind = 2 if c == "." else 1
            elif c in "+-":
                kind = (11 if before_point else 12) if floating_here else (5 if position == len(symbols) - 1 and position else 4)
            elif c in "CD":
                kind = 6
            elif c in "Z*":
                kind = 9 if before_point else 10
            elif c == "9":
                kind = 15
            elif c == "V":
                kind = 19
            elif c == "P":
                kind = 20 if non_p and before_point else 21
            else:  # currency
                if floating_here:
                    kind = 13 if before_point else 14
                else:
                    kind = 7 if position <= 1 else 8 if position >= len(symbols) - 2 else 7
            if 9 <= kind <= 15:
                non_p = True
            if any(not PRECEDENCE[kind][other] for other in seen):
                return False
            seen.add(kind)
            if c in ".V":
                before_point = False
    return True


def edited_picture(p, picture):
    """Numeric-edited PICTURE as cobc's cb_build_picture: the symbol list
    (identical consecutive symbols grouped, CR/DB as C/D), size, digits, scale.

    The grouping matters at run time: libcob's editing tells a floating
    insertion from a fixed one by the repetition count of each group.
    """
    symbols, i = [], 0
    text = picture.upper()
    while i < len(text):
        c = text[i]
        if c in "CD":
            if text[i + 1:i + 2] != ("R" if c == "C" else "B"):
                p.error(f"PICTURE éditée invalide: {picture}")
            i += 1
        n = 1
        while i + 1 < len(text) and text[i + 1] == c and c not in "CD":
            n += 1
            i += 1
        if i + 1 < len(text) and text[i + 1] == "(":
            close = text.find(")", i + 2)
            if close < 0 or not text[i + 2:close].isdigit() or int(text[i + 2:close]) < 1:
                p.error(f"PICTURE éditée invalide: {picture}")
            n += min(int(text[i + 2:close]), 65536) - 1
            i = close
        symbols.append((c, n))
        i += 1
    if any(c not in "9Z*+-$.,VPB0/CD" for c, _ in symbols):
        p.error(f"PICTURE non prise en charge: {picture}")
    digits = scale = size = v_count = s_edit = c_count = 0
    for index, (c, n) in enumerate(symbols):
        if c in "9Z*":
            digits += n
            scale += n if v_count else 0
        elif c in "+-":
            digits += n - (1 if s_edit == 0 else 0)
            if v_count:
                scale += n - (1 if s_edit == 0 else 0)
            s_edit += 1
        elif c in "CD":
            if n != 1 or index != len(symbols) - 1:
                p.error(f"PICTURE éditée invalide: {picture}")
            s_edit += 1
        elif c == "$":
            digits += n - 1 if c_count == 0 else n
            c_count += n - 1 if c_count == 0 else n
        elif c in ".V":
            v_count += n
        elif c == "P":
            previous = "".join(symbol for symbol, _ in symbols[:index])
            at_end = index == len(symbols) - 1 or (index == len(symbols) - 2 and symbols[-1][0] == "V")
            if previous in {"", "V"}:
                v_count += 1
            elif at_end:
                digits += n
            else:
                p.error(f"PICTURE éditée invalide: {picture}")
            scale += n if v_count else -n
        size += 0 if c in "VP" else 2 * n if c in "CD" else n
    used = {c for c, _ in symbols}
    if v_count > 1 or digits < 1 or {"Z", "*"} <= used or not valid_char_order(symbols):
        p.error(f"PICTURE éditée invalide pour cobc: {picture}")
    return symbols, size, digits, scale, s_edit > 0


FIGURATIVES = {"ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES", "QUOTE", "QUOTES", "HIGH-VALUE", "HIGH-VALUES",
               "LOW-VALUE", "LOW-VALUES", "NULL", "NULLS"}
CONSTANT_OPERATORS = {"(": "(", ")": ")", "+": "+", "-": "-", "*": "*", "/": "/", "AND": "&", "OR": "|", "**": "^"}


def evaluate_constant(p, items, line, normal_prec):
    """cb_evaluate_expr: without normal_prec (78 VALUE) every operator has the
    same precedence; values are integers with a decimal scale and the result
    is truncated to an integer literal."""
    precedence = {"*": 6, "/": 6, "^": 7, "&": 8, "|": 8} if normal_prec else {}
    ops, vals = [], []   # ops: (type, prec); vals: (value, scale)

    def reduce_zeros(value, scale):
        while scale > 0 and value % 10 == 0:
            scale, value = scale - 1, int(value / 10)
        return value, scale

    def eval_op():
        if not ops or len(vals) < 2:
            return
        (rval, rscale), (lval, lscale) = vals.pop(), vals.pop()
        op = ops[-1][0]
        if op in "+-":
            while lscale > rscale:
                rval, rscale = rval * 10, rscale + 1
            while lscale < rscale:
                lval, lscale = lval * 10, lscale + 1
            value, scale = (lval + rval if op == "+" else lval - rval), lscale
        elif op == "*":
            value, scale = lval * rval, lscale + rscale
        elif op == "/":
            while rscale > 0:
                lval, rscale = lval * 10, rscale - 1
            if rval == 0:
                p.error("constant expression has Divide by ZERO")
            value, scale = int(lval / rval), lscale
        elif op == "^":
            while rscale > 0:
                rval, rscale = int(rval / 10), rscale - 1
            if rval == 0 or lval == 1:
                value, scale = 1, 0
            else:
                value, scale = lval, lscale
                for _ in range(rval - 1):
                    scale, value = scale + lscale, value * lval
        elif op == "&":
            value, scale = int(bool(lval and rval)), 0
        elif op == "|":
            value, scale = int(bool(lval or rval)), 0
        else:
            p.error("missing right parenthesis")
        ops.pop()
        vals.append(reduce_zeros(value, scale))

    def push_op(op, prec):
        while ops and len(vals) > 1 and prec > 0 and ops[-1][0] != "(" and prec <= ops[-1][1]:
            eval_op()
        ops.append((op, prec))

    unop = True
    for kind, value in items:
        if kind == "number":
            sign = -1 if value.startswith("-") else (1 if value.startswith("+") else 0)
            digits = value.lstrip("+-")
            scale = len(digits.split(".")[1]) if "." in digits else 0
            number = int(digits.replace(".", "") or "0")
            if unop:
                number = -number if sign < 0 else number
            elif sign:
                push_op("-" if sign < 0 else "+", 4)
            vals.append(reduce_zeros(number, scale))
            unop = False
        elif value == "(":
            push_op("(", 0)
            unop = True
        elif value == ")":
            unop = False
            if not any(op == "(" for op, _ in ops):
                p.error("missing left parenthesis")
            while ops and len(vals) > 0 and ops[-1][0] != "(":
                eval_op()
            if ops and ops[-1][0] == "(":
                ops.pop()
        else:
            push_op(value, precedence.get(value, 4))
            unop = True
    while ops and vals:
        if ops[-1][0] == "(":
            p.error("missing right parenthesis")
        eval_op()
    if ops:
        p.error(f"'{ops[-1][0]}' operator misplaced")
    value, scale = vals[0] if vals else (0, 0)
    while scale > 0:
        scale, value = scale - 1, int(value / 10)
    return [Token(str(value), line)]


# A figurative constant as one character of a concatenated literal.
FIGURATIVE_CHARACTERS = {"ZERO": "0", "ZEROS": "0", "ZEROES": "0", "SPACE": " ", "SPACES": " ", "QUOTE": '"', "QUOTES": '"'}

# con_source usage words (parser.y): their size in bytes on Linux x86_64.
CONSTANT_USAGE_SIZES = {"BINARY-CHAR": 1, "BINARY-SHORT": 2, "BINARY-LONG": 4, "BINARY-DOUBLE": 8, "BINARY-C-LONG": 8,
                        "POINTER": 8, "PROGRAM-POINTER": 8, "COMP-1": 4, "COMPUTATIONAL-1": 4, "FLOAT-SHORT": 4,
                        "COMP-2": 8, "COMPUTATIONAL-2": 8, "FLOAT-LONG": 8, "FLOAT-EXTENDED": 16,
                        "FLOAT-DECIMAL-16": 8, "FLOAT-DECIMAL-34": 16}
# reserved.c: reserved words without a token in GnuCOBOL 3.2.
UNSUPPORTED_RESERVED = {"FLOAT-BINARY-32", "FLOAT-BINARY-64", "FLOAT-BINARY-128"}


def partial_layout(p, root, single=None):
    """cb_validate_field on what is declared so far: a copy of the record
    `root` laid out alone (`single`: an item counted with one occurrence)."""
    import copy
    from .layout import layout_fields
    copies = {key: copy.copy(f) for key, f in p.fields.items() if key == root or key.startswith(root + ".")}
    for f in copies.values():
        f.children = list(f.children)
    copies[root].redefines = None
    copies[root].parent = None
    if single is not None:
        copies[single].occurs = 1
    try:
        layout_fields(copies)
    except CobolError as error:
        p.error(str(error))
    return copies


def remember_sizes(p, copies, top):
    """compute_size leaves the size of `top` and its subordinates in their
    cb_field, read back by a later NEXT after an 01 item."""
    sizes = p.__dict__.setdefault("constant_sizes", {})
    for key, f in copies.items():
        if key == top or key.startswith(top + "."):
            sizes[key] = f.size


def constant_field(p, what):
    """The data item of LENGTH OF / START OF in a constant
    (cb_build_const_length, cb_build_const_start)."""
    label, qualifiers = p.name(), []
    while p.accept("OF") or p.accept("IN"):
        qualifiers.append(p.name())
    if p.at("("):
        p.error(f"{what} d'un article indicé ou d'une sous-chaîne dans une constante non pris en charge")
    if p.candidates(label, True) and not p.candidates(label):
        p.error("88 level item not allowed here")
    f = p.fields[p.resolve(label, tuple(qualifiers))]
    if f.any_length:
        p.error("ANY LENGTH item not allowed here")
    if f.depending or p.variable_size(f):
        p.error("variable length item not allowed here")
    return f


def ancestors(p, f):
    result = []
    while f.parent:
        f = p.fields[f.parent]
        result.append(f)
    return result


def founder(p, f):
    while f.parent:
        f = p.fields[f.parent]
    return f


def constant_length(p):
    """lit_or_length: LENGTH [OF] / BYTE-LENGTH [OF] con_source."""
    p.take()
    p.accept("OF")
    if p.t.string:
        return str(len(p.take().text))
    if p.t.key in UNSUPPORTED_RESERVED:
        p.error(f"'{p.t.text}' is a reserved word, but isn't supported")
    if p.t.key in CONSTANT_USAGE_SIZES and not p.candidates(p.t.key):
        return str(CONSTANT_USAGE_SIZES[p.take().key])
    f = constant_field(p, "LENGTH OF")
    root = founder(p, f)
    copies = partial_layout(p, root.name)
    remember_sizes(p, copies, f.name)
    item = copies[f.name]
    if f.redefines:
        return str(item.size)
    # memory_size of cb_validate_field: the size by the occurrences (a later
    # larger 01 REDEFINES only updates it when that item is validated).
    return str(item.size * item.occurs)


def constant_position(p, name):
    """constant_78_source START OF identifier (cb_build_const_start) and
    NEXT (cb_build_const_next): FILE, LINKAGE or EXTERNAL storage only."""
    def storage_check(f, what, target):
        root = founder(p, f)
        if not (root.external or root.file_record or getattr(root, "linkage", False)):
            p.error(f"VALUE of '{name}': {what} target{target} is invalid; target must be in FILE SECTION "
                    "or LINKAGE SECTION or have the EXTERNAL clause")
        return root
    if p.accept("START"):
        p.accept("OF")
        f = constant_field(p, "START OF")
        # identifier: an item of a table needs its subscripts.
        tables = sum(1 for item in [f, *ancestors(p, f)] if item.table)
        if tables:
            p.error(f"'{f.label}' requires {tables} subscript{'s' if tables > 1 else ''}" if tables > 1
                    else f"'{f.label}' requires one subscript")
        root = storage_check(f, "START OF", f" '{f.label}'")
        copies = partial_layout(p, root.name)
        remember_sizes(p, copies, root.name)
        return str(copies[f.name].offset)
    p.expect("NEXT")
    if not p.last_data:
        p.error(f"VALUE of '{name}': NEXT target is invalid; no previous data-item found")
    previous = p.fields[p.last_data]
    root = storage_check(previous, "NEXT", "")
    if previous.depending or p.variable_size(previous):
        p.error("variable length item not allowed here")
    if previous.level == 1:
        # p->size: 0 until something computed it.
        return str(p.__dict__.get("constant_sizes", {}).get(previous.name, 0))
    copies = partial_layout(p, root.name, single=previous.name)
    sizes = p.__dict__.setdefault("constant_sizes", {})
    for key, f in copies.items():
        sizes[key] = f.size if key != previous.name else copies[key].size
    return str(copies[root.name].size)


def constant_entry(p, level):
    """SEVENTY_EIGHT user_entry_name _global_clause VALUE _is constant_78_source,
    or level_number user_entry_name CONSTANT _const_global constant_source:
    cb_add_78 makes the scanner return the value for each later use of the
    name in the program (and its contained programs when GLOBAL)."""
    line = p.t.line
    if p.t.string:
        p.error("identifiant attendu")
    name = p.name()
    p.user_word(name)
    if level != 78:
        p.expect("CONSTANT")
        if level != 1:
            p.error("CONSTANT item not at 01 level")
    if p.accept("IS"):
        p.expect("GLOBAL")
        is_global = True
    else:
        is_global = bool(p.accept("GLOBAL"))
    items, tokens = [], []
    if level != 78:
        if p.accept("FROM"):
            # cb_build_const_from: the value of a >>DEFINE (or -D).
            from . import frontend
            word = p.take()
            define = frontend.DEFINES.get(word.key) if not word.string else None
            if define is None:
                p.error(f"'{word.text}' has not been DEFINEd")
            if word.key in frontend.CHANGED_DEFINES:
                p.error(f"CONSTANT FROM '{word.text}' redéfini par >>DEFINE OVERRIDE/OFF non pris en charge")
            kind, value = define
            items.append(("literal", value) if kind == "L" else ("number", str(value)))
            tokens = [Token(value, line, True) if kind == "L" else Token(str(value), line)]
        else:
            p.accept("AS")
    elif not p.accept("VALUE"):
        p.error("VALUE is required for level 78 item")
    else:
        p.accept("IS")
        if p.at("START") or p.at("NEXT"):
            value = constant_position(p, name)
            items.append(("number", value))
            tokens = [Token(value, line)]
    # START OF, NEXT and FROM are whole constant sources.
    whole = bool(items)
    # lookup_reserved_word: CONSTANT sets CB_CS_CONSTANT, the first
    # BYTE-LENGTH found in it resets it; elsewhere BYTE-LENGTH is a name.
    byte_length = level != 78
    while not whole and not p.at(".") and not p.at("<EOF>"):
        t = p.t
        if not t.string and (t.key == "LENGTH" and not p.candidates(t.key) or t.key == "BYTE-LENGTH" and byte_length):
            byte_length = byte_length and t.key != "BYTE-LENGTH"
            value = constant_length(p)
            tokens = [Token(value, t.line)]
            items.append(("number", value))
            continue
        if not t.string and t.key == "&" and items and items[-1][0] == "literal" and tokens and tokens[-1].string:
            # basic_literal TOK_AMPER basic_value: cb_concat_literals.
            p.take()
            if not p.t.string and p.t.key not in FIGURATIVES:
                p.error("littéral attendu")
            right = p.take()
            text = tokens[-1].text + (right.text if right.string else FIGURATIVE_CHARACTERS.get(right.key, right.text))
            tokens = [Token(text, tokens[-1].line, True)]
            items[-1] = ("literal", text)
            continue
        if not t.string and t.key in CONSTANT_OPERATORS:
            p.take()
            if t.key in "+-" and p.t.text[:1].isdigit() and (not items or items[-1][0] == "operator"
                                                              and items[-1][1] != ")"):
                number = p.take()
                items.append(("number", t.key + number.text))
                tokens = [Token(t.key + number.text, t.line)]
                continue
            items.append(("operator", CONSTANT_OPERATORS[t.key]))
            continue
        if not t.string and t.key == "ALL":
            p.take()
            if not p.t.string and p.t.key not in FIGURATIVES:
                p.error("littéral attendu")
            tokens = [Token("ALL", t.line), p.take()]
            items.append(("literal", tokens[1].text))
            continue
        if t.string or t.key in FIGURATIVES:
            p.take()
            tokens = [t]
            items.append(("literal", t.text))
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", t.text):
            p.take()
            tokens = [t]
            items.append(("number", t.text))
            continue
        p.error("littéral attendu")
    p.expect(".")
    if not items:
        p.error("VALUE is required for level 78 item")
    if len(items) > 1:
        # cb_is_expr: more than one element, an expression of numeric literals.
        for kind, value in items:
            if kind == "literal":
                p.error(f"invalid operator '{value}' in expression")
        tokens = evaluate_constant(p, items, line, level != 78)
    elif items[0][0] == "operator":
        p.error("littéral attendu")
    key = name.upper()
    if key in p.constants:
        p.error(f"'{name}' constant redefined")   # cb_build_constant: redefinition
    p.constants[key] = tokens
    # Scanner substitution up to the end of the program (cb_reset_78), or of
    # the program and its contained programs for a GLOBAL constant.
    end = p.tokens.scope_end(p.i, is_global)
    if len(tokens) == 1:
        value = tokens[0]
        p.tokens.substitute(key, p.i, end, lambda t: ConstantToken(value.text, t.line, value.string, t.start, t.end,
                                                                   constant=name))
        return None
    replaced = []
    for t in p.tokens[p.i:end]:
        if not t.string and t.key == key:
            replaced.extend(ConstantToken(r.text, t.line, r.string, t.start, t.end, constant=name) for r in tokens)
        else:
            replaced.append(t)
    p.tokens[p.i:end] = replaced
    return None


def picture_constants(p, picture):
    """get_number_in_parentheses: a constant-name between parentheses."""
    def count(match):
        inner = match[1]
        if all(c.isdigit() or c in ".+-" for c in inner):
            return match[0]
        tokens = p.constants.get(inner.upper())
        if tokens is None:
            p.error(f"'{inner}' is not a constant-name" if p.candidates(inner.upper()) else f"'{inner}' is not defined")
        if len(tokens) != 1 or tokens[0].string or not tokens[0].text.isdigit():
            p.error(f"'{inner}' is not an unsigned positive integer")
        return f"({tokens[0].text})"
    return re.sub(r"\(([^()]*)\)", count, picture)


def type_reference(p, word, label, level):
    """setup_external_definition: the TYPEDEF (TYPE TO, USAGE type-name) or
    the data item (SAME AS) whose description is inherited."""
    from . import frontend
    clause = "TYPE TO" if word == "TYPE" else "SAME AS"
    if frontend.STD == "cobol85":
        p.error(f"{clause} clause does not conform to COBOL 85")
    name, qualifiers = p.name(), []
    while p.accept("OF") or p.accept("IN"):
        qualifiers.append(p.name())
    if word == "TYPE":
        key = getattr(p, "typedefs", {}).get(name.upper())
        if key is None or qualifiers:
            p.error(f"'{name}' is not a TYPEDEF name")
        return key
    key = p.resolve(name, tuple(qualifiers))
    source = p.fields[key]
    if source.typedef:
        p.error("TYPEDEF item cannot be used here")
    cursor = source
    while cursor.parent:
        cursor = p.fields[cursor.parent]
        if cursor.group_usage not in {None, "DISPLAY"}:
            p.error("item may not be subordinate to any item with USAGE clause")
        if cursor.group_sign:
            p.error("item may not be subordinate to any item with SIGN clause")
    # The item itself or one of its parents (the current field's ancestors).
    if key in p.data_stack:
        p.error("item may not reference itself")
    return key


def copy_type(p, source_key, target_key, level):
    """copy_into_field / copy_children: the subordinate entries (with their
    level 88) of the type, under the target; a level not above the target's
    becomes the next one (66, 77, 78 and 88 skipped)."""
    import copy
    for key, condition in list(p.conditions.items()):
        if condition.parent == source_key:
            new = copy.copy(condition)
            new.name, new.parent = target_key + key[len(source_key):], target_key
            p.conditions[new.name] = new
    for child in p.fields[source_key].children:
        source = p.fields[child]
        child_level = source.level if source.level > level else level + 1
        if child_level in {66, 78, 88}:
            child_level += 1
        elif child_level == 77:
            child_level = 79
        new_key = target_key + child[len(source_key):]
        new = copy.copy(source)
        new.name, new.parent, new.level, new.children = new_key, target_key, child_level, []
        new.dimensions, new.offset, new.size = list(source.dimensions), 0, 0
        if new.redefines and new.redefines.startswith(source_key + "."):
            new.redefines = target_key + new.redefines[len(source_key):]
        p.fields[new_key] = new
        p.fields[target_key].children.append(new_key)
        copy_type(p, child, new_key, child_level)


def declaration(p, file_record=False):
    if p.t.string or not p.t.key.isdigit():
        if not p.t.string and p.tokens[p.i + 1].key == "SECTION":
            p.error(f"{p.t.key} SECTION non prise en charge à cet endroit")
        p.error("niveau de donnée attendu")
    level = int(p.take().key)
    if isinstance(p.t, ConstantToken):
        # not_const_word: a level number is followed by a defined name.
        p.error(f"a constant may not be used here - '{p.t.constant}'")
    if level == 78 or (not p.t.string and p.tokens[p.i + 1].key == "CONSTANT" and not p.tokens[p.i + 1].string):
        return constant_entry(p, level)
    # A description without a name is an implicit FILLER.
    implicit_filler = level != 88 and not p.t.string and p.t.key in {
        "PIC", "PICTURE", "VALUE", "VALUES", "USAGE", "OCCURS", "REDEFINES", "SIGN", "BLANK", "JUSTIFIED",
        "JUST", "LEADING", "TRAILING", "SYNC", "SYNCHRONIZED", "ANY", "."} | USAGES
    if implicit_filler and p.t.key in {"PIC", "PICTURE"} and p.tokens[p.i + 1].key in {"PIC", "PICTURE"}:
        p.error("nom réservé: " + p.t.key)
    label = "FILLER" if implicit_filler else p.name()
    if label != "FILLER":
        p.user_word(label)
    if level == 88:
        if not p.last_data:
            p.error("niveau 88 requiert une donnée précédente")
        # A group's condition compares its storage as alphanumeric text.
        group_condition = not p.fields[p.last_data].picture and p.fields[p.last_data].usage != "INDEX"
        key = p.last_data + "." + label
        if label in VERBS:
            p.error("condition dupliquée ou réservée")
        if key in p.conditions:
            # Homonymous conditions of one item are valid; a reference to
            # them is ambiguous (cb_ref). Keep their keys distinct.
            duplicate = 2
            while f"{key}${duplicate}" in p.conditions:
                duplicate += 1
            key = f"{key}${duplicate}"
        if not (p.accept("VALUE") or p.accept("VALUES")):
            p.error("VALUE attendu au niveau 88")
        p.accept("IS") or p.accept("ARE")
        values = []
        repeated_values = {}
        while not p.at(".") and not p.at("WHEN") and not p.at("FALSE"):
            parent = p.fields[p.last_data]
            figurative = not p.t.string and p.t.key in {"QUOTE", "QUOTES", "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES"} | (
                {"ZERO", "ZEROS", "ZEROES"} if parent.kind == "text" else set())
            if parent.any_length and not p.t.string:
                figurative = figurative or p.t.key in {"SPACE", "SPACES"} or (
                    p.t.key in getattr(p, "symbolic", {}) and not p.candidates(p.t.key))
            if group_condition and not p.t.string and (p.at("ALL") or p.t.key in {
                    "QUOTE", "QUOTES", "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES", "ZERO", "ZEROS", "ZEROES"}
                    or p.t.key in getattr(p, "symbolic", {})):
                # cob_cmp of the group with a figurative constant or ALL literal
                # repeats it over the group's size, known once it is laid out.
                p.accept("ALL")
                token = literal(p)
                if p.at("THRU") or p.at("THROUGH"):
                    p.error("plage THRU de figuratives au niveau 88 de groupe non prise en charge")
                p.group_fills.append((key, len(values), token.text))
                values.append((None, None))
                p.accept(",")
                continue
            if group_condition and not p.t.string and p.t.key not in {"SPACE", "SPACES"}:
                p.error("niveau 88 de groupe limité aux littéraux alphanumériques")
            if p.accept("ALL") or figurative:
                # ALL literal and figurative constants: repeated over the item.
                token = literal(p)
                if not token.string:
                    token = Token(token.text, token.line, True)
                if not token.string or parent.kind != "text":
                    p.error("VALUE ALL de niveau 88 limité aux PIC X/A")
                if parent.any_length:
                    repeated_values[len(values)] = token.text
                low = Token((token.text * parent.digits)[:parent.digits], token.line, True)
                values.append((low, low))
                p.accept(",")
                continue
            low = literal(p)
            high = literal(p) if p.accept("THRU") or p.accept("THROUGH") else low
            values.append((low, high))
            p.accept(",")
        if not values:
            p.error("VALUE de condition vide")
        false_value = false_repeated = None

        def false_literal():
            repeated = parent.any_length and not p.t.string and (p.t.key in {
                "ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES", "QUOTE", "QUOTES", "HIGH-VALUE", "HIGH-VALUES",
                "LOW-VALUE", "LOW-VALUES"} or p.t.key in getattr(p, "symbolic", {}) and not p.candidates(p.t.key))
            token = literal(p)
            return token, token.text if repeated else None

        if p.accept("WHEN"):
            p.expect("SET"); p.expect("TO"); p.expect("FALSE")
            p.accept("IS")
            false_value, false_repeated = false_literal()
        elif p.accept("FALSE"):
            # _false_is: FALSE [IS] literal, without WHEN SET TO.
            p.accept("IS")
            false_value, false_repeated = false_literal()
        p.expect(".")
        p.conditions[key] = Condition(key, label, p.last_data, values, false_value, repeated_values, false_repeated)
        return key
    if level == 66:
        # renames_entry: the item follows its record and aliases storage
        # once the record is laid out (Parser.apply_renames).
        if not p.data_stack or p.fields[p.data_stack[0]].level != 1:
            p.error("66 RENAMES doit suivre un enregistrement 01")
        founder = p.data_stack[0]
        line = p.t.line
        p.expect("RENAMES")

        def target():
            name, qualifiers = p.name(), []
            while p.accept("OF") or p.accept("IN"):
                qualifiers.append(p.name())
            if p.candidates(name, True) and not p.candidates(name):
                p.error("RENAMES may not reference a level 88")
            return p.resolve(name, qualifiers)
        first = target()
        thru = target() if p.accept("THRU") or p.accept("THROUGH") else None
        p.expect(".")
        key = founder + "." + label
        taken = lambda name: name in p.fields or any(r[0] == name for r in p.renames)
        if taken(key):
            # A homonym of an item of the record: references are ambiguous
            # (cb_ref), keys stay distinct like homonymous siblings.
            duplicate = 2
            while taken(f"{key}${duplicate}"):
                duplicate += 1
            key = f"{key}${duplicate}"
        p.renames.append((key, label, first, thru, founder, line))
        return key
    if level not in {1, 77} and not 2 <= level <= 49:
        p.error("niveaux pris en charge: 01-49, 66, 77 et 88")
    # The implicit FILLER of a PICTURE L item (parser.y picture_clause).
    implicit_child, p.picture_l_child = getattr(p, "picture_l_child", None), None
    if implicit_child:
        pass
    elif level in {1, 77}:
        p.data_stack = []
    else:
        while p.data_stack and p.fields[p.data_stack[-1]].level >= level:
            p.data_stack.pop()
        if not p.data_stack or p.fields[p.data_stack[-1]].level == 77:
            p.error("donnée subordonnée sans groupe parent")
    parent = p.data_stack[-1] if p.data_stack else None
    if parent and p.fields[parent].picture_l and not implicit_child:
        p.error("donnée subordonnée à une PICTURE L non prise en charge")
    if parent and p.fields[parent].picture:
        p.error("un champ élémentaire ne peut pas contenir de sous-champs")
    filler = label == "FILLER"
    if filler:
        p.filler_count += 1
        component = f"$FILLER{p.filler_count}"
    else:
        component = label
    key = (parent + "." if parent else "") + component
    if key in p.fields and label not in VERBS and not getattr(p, "building_register", False):
        # Homonymous siblings, and 01/77 items (only a redefinition warning
        # for cobc), are valid; a reference to them is ambiguous (cb_ref),
        # which resolve() reports. Keep their keys distinct.
        duplicate = 2
        while f"{key}${duplicate}" in p.fields:
            duplicate += 1
        key = f"{key}${duplicate}"
    if key in p.fields or label in VERBS or label in {"ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES"}:
        p.error(f"nom de donnée réservé ou dupliqué: {label}")
    picture, usage, initial = "", "DISPLAY", None
    value_signed = indexed_seen = False
    fixed_binary = None
    has_usage, table, count, redefines = False, False, 1, None
    minimum, depending = 1, None
    figurative = None
    blank_zero = justified = False
    sign_clause = None
    synchronized = False
    search_keys = []
    external = is_global = based = False
    external_as = None
    any_length = False
    variable_picture = depending_tokens = None
    typedef, type_source, type_kind = False, None, None
    if p.accept("REDEFINES"):
        target = p.name()
        siblings = [f for f in p.fields.values() if f.parent == parent]
        matches = [f for f in siblings if f.label == target]
        if not matches or matches[-1].level != level:
            p.error("REDEFINES requiert un champ précédent au même niveau")
        if matches[-1].redefines:
            # indirect-redefines: no (default.conf).
            p.error(f"'{target}' is not the original definition")
        # Restrict to a contiguous redefine family; indirect redefines are dialect-dependent.
        last = siblings[-1]
        if last.name != matches[-1].name and last.redefines != matches[-1].name:
            p.error("REDEFINES indirect non pris en charge")
        redefines = matches[-1].name
        if matches[-1].any_length:
            p.error("REDEFINES d'un article ANY LENGTH invalide")
    while not p.at("."):
        if p.accept("PIC") or p.accept("PICTURE"):
            if picture or variable_picture:
                p.error("PICTURE dupliquée")
            p.accept("IS")
            if p.t.string or p.t.key in {".", "<EOF>", "VALUE", "USAGE", "OCCURS", "INDEXED"} | USAGES:
                p.error("mot PICTURE contigu attendu")
            picture = p.picture_symbols(picture_constants(p, p.take().key))
            if picture.startswith("L"):
                # tree.c cb_build_picture 'L' and parser.y picture_clause:
                # PIC Lc... DEPENDING n is a group whose FILLER is PIC c
                # OCCURS 1 TO size - 1 DEPENDING n.
                from . import frontend
                if frontend.STD == "cobol85":
                    p.error("PICTURE string with 'L' character does not conform to COBOL 85")
                variable_picture, picture = picture[1:], ""
                if not p.accept("DEPENDING"):
                    p.error("variable-length PICTURE requires DEPENDING clause")
                p.accept("ON")
                start = p.i
                p.name()
                while p.accept("OF") or p.accept("IN"):
                    p.name()
                depending_tokens = list(p.tokens[start:p.i])
                written = re.sub(r"([XA9])\((\d+)\)", lambda m: m[1] * min(int(m[2]), 10001), variable_picture)
                if not re.fullmatch(r"[XA9]+", written) or set(written) == {"9"}:
                    p.error("only USAGE DISPLAY may specify a variable-length PICTURE")
                if len(written) > 10000:
                    p.error("OCCURS limité à 1..10000, minimum variable 0..maximum")
        elif p.accept("ANY"):
            if any_length:
                p.error("ANY LENGTH dupliqué")
            if p.accept("NUMERIC"):
                p.error("ANY NUMERIC non pris en charge: descripteur numérique dynamique")
            p.expect("LENGTH")
            any_length = True
        elif p.accept("OCCURS"):
            if not table and (p.at("UNBOUNDED") or p.tokens[p.i + 1].key == "TO" and p.tokens[p.i + 2].key == "UNBOUNDED"):
                p.error("OCCURS UNBOUNDED non pris en charge")
            if table or not p.t.key.isdigit():
                p.error("nombre OCCURS attendu")
            count = int(p.take().key)
            minimum = count
            variable = p.accept("TO")
            if variable:
                if not p.t.key.isdigit():
                    p.error("borne maximale OCCURS attendue")
                count = int(p.take().key)
            if not 1 <= count <= 10000 or not 0 <= minimum <= count or (not variable and minimum == 0):
                p.error("OCCURS limité à 1..10000, minimum variable 0..maximum")
            table = True
            p.accept("TIMES")
            if variable:
                p.expect("DEPENDING"); p.accept("ON")
                depending = p.name()
                while p.accept("OF") or p.accept("IN"):
                    depending += "\0" + p.name()
        elif p.at("ASCENDING") or p.at("DESCENDING"):
            # ASCENDING/DESCENDING KEY: the keys of SEARCH ALL, in order.
            if not table:
                p.error("KEY requiert OCCURS")
            if indexed_seen:
                p.error("INDEXED should follow ASCENDING/DESCENDING")
            descending = p.take().key == "DESCENDING"
            p.accept("KEY"); p.accept("IS")
            search_keys.append((descending, p.name()))
            while not p.t.string and p.t.key not in {"ASCENDING", "DESCENDING", "INDEXED", "PIC", "PICTURE",
                                                     "VALUE", "USAGE", ".", "<EOF>"} | USAGES:
                search_keys.append((descending, p.name()))
        elif p.accept("INDEXED"):
            if not table:
                p.error("INDEXED BY requiert OCCURS")
            indexed_seen = True
            p.accept("BY")
            names = [p.name()]
            while p.t.key not in {"PIC", "PICTURE", "VALUE", "USAGE", "ASCENDING", "DESCENDING", ".", "<EOF>"} | USAGES:
                p.accept(",")
                names.append(p.name())
            for name in names:
                p.user_word(name)
                if name in p.indexes or name in VERBS:
                    p.error(f"index dupliqué ou réservé: {name}")
                p.indexes[name] = key
        elif p.accept("VALUE"):
            if initial is not None:
                p.error("VALUE dupliqué")
            p.accept("IS")
            if p.at("NULL") or p.at("NULLS"):
                # VALUE NULL: only for USAGE POINTER (checked below).
                initial, figurative = Token("0", p.take().line), "NULL"
                continue
            repeated = p.accept("ALL")
            # A group VALUE fills its whole area: keep ZERO distinct from 0.
            figurative = None if p.t.string else (
                "0" if p.t.key in {"ZERO", "ZEROS", "ZEROES"} else " " if p.t.key in {"SPACE", "SPACES"}
                else '"' if p.t.key in {"QUOTE", "QUOTES"} else getattr(p, "high_value", "\xff") if p.t.key in {"HIGH-VALUE", "HIGH-VALUES"}
                else getattr(p, "low_value", "\x00") if p.t.key in {"LOW-VALUE", "LOW-VALUES"}
                else chr(p.symbolic[p.t.key]) if p.t.key in getattr(p, "symbolic", {}) and not p.candidates(p.t.key)
                else None)
            initial = literal(p)
            value_signed = p.literal_signed
            if repeated:
                # VALUE ALL literal repeats the literal over the item.
                if figurative == "0":
                    initial = Token("0", initial.line, True)
                if not initial.string:
                    p.error("VALUE ALL limité aux littéraux alphanumériques et constantes figuratives")
                figurative = ("ALL", initial.text)
        elif p.at("SIGN") or p.at("LEADING") or p.at("TRAILING"):
            # SIGN [IS] LEADING|TRAILING [SEPARATE [CHARACTER]]
            if sign_clause is not None:
                p.error("SIGN dupliqué")
            if p.accept("SIGN"):
                p.accept("IS")
            if not (p.at("LEADING") or p.at("TRAILING")):
                p.error("SIGN requiert LEADING ou TRAILING")
            position = p.take().key
            separate = p.accept("SEPARATE")
            if separate:
                p.accept("CHARACTER")
            sign_clause = (position, separate)
        elif p.at("TYPEDEF") or (p.at("IS") and p.tokens[p.i + 1].key == "TYPEDEF"):
            # typedef_clause: a type, without storage, for TYPE TO / USAGE.
            p.accept("IS")
            p.take()
            if typedef:
                p.error("duplicate TYPEDEF clause")
            from . import frontend
            if frontend.STD == "cobol85":
                p.error("TYPEDEF does not conform to COBOL 85")
            typedef = True
            p.accept("STRONG")  # CB_PENDING ("TYPEDEF STRONG")
            if level not in {1, 77}:
                p.error("TYPEDEF only allowed at 01/77 level")
            if filler:
                p.error("TYPEDEF requires a data name")
        elif (p.at("TYPE") and not p.candidates(p.t.key)) or (p.at("SAME") and not p.candidates(p.t.key)):
            # type_to_clause / same_as_clause (setup_external_definition).
            word = p.take().key
            p.accept("TO" if word == "TYPE" else "AS")
            if type_source is not None:
                p.error("SAME AS and TYPE TO are mutually exclusive" if type_kind != word
                        else f"duplicate {'TYPE TO' if word == 'TYPE' else 'SAME AS'} clause")
            type_kind = word
            type_source = type_reference(p, word, label, level)
        elif p.at("EXTERNAL") or p.at("GLOBAL") or (p.at("IS") and p.tokens[p.i + 1].key in {"EXTERNAL", "GLOBAL"}):
            # external_clause / global_clause: 01 or 77 data names only.
            p.accept("IS")
            clause = p.take().key
            if level not in {1, 77} or filler:
                p.error(f"{clause} only allowed at 01/77 level")
            if clause == "EXTERNAL":
                if file_record or getattr(p, "in_linkage", False):
                    p.error("EXTERNAL not allowed here")
                if redefines:
                    p.error("EXTERNAL and REDEFINES are mutually exclusive")
                if p.accept("AS"):
                    # external_clause: AS literal names the item for the run unit.
                    if not p.t.string:
                        p.error("literal expected after EXTERNAL AS")
                    external_as = p.take().text
                external = True
            else:
                is_global = True
        elif p.accept("BASED"):
            # based_clause: 01/77 items whose address is set at run time.
            if based:
                p.error("BASED dupliqué")
            if level not in {1, 77}:
                p.error("BASED only allowed at the 01 and 77 levels")
            if file_record or external or redefines or getattr(p, "in_communication", False):
                p.error("BASED not allowed here")
            based = True
        elif p.accept("SYNCHRONIZED") or p.accept("SYNC"):
            p.accept("LEFT") or p.accept("RIGHT")
            synchronized = True
        elif p.accept("JUSTIFIED") or p.accept("JUST"):
            if justified:
                p.error("JUSTIFIED dupliqué")
            p.accept("RIGHT")
            justified = True
        elif p.accept("BLANK"):
            p.accept("WHEN")
            if blank_zero or not (p.accept("ZERO") or p.accept("ZEROS") or p.accept("ZEROES")):
                p.error("BLANK WHEN ZERO attendu")
            blank_zero = True
        else:
            if has_usage:
                p.error("clause de donnée non prise en charge")
            has_usage = True
            if p.accept("USAGE"):
                p.accept("IS")
                if not p.t.string and p.t.key not in USAGES and p.t.key in getattr(p, "typedefs", {}):
                    # USAGE type-name: the TYPE TO of the type.
                    if type_source is not None:
                        p.error("USAGE and SAME AS / TYPE TO are mutually exclusive")
                    has_usage = False
                    type_kind = "TYPE"
                    type_source = type_reference(p, "TYPE", label, level)
                    continue
            if p.t.string or p.t.key not in USAGES:
                p.error(f"USAGE/clause non pris en charge: {p.t.text}")
            usage = p.take().key
            if usage in FIXED_BINARY_DIGITS:
                signed_binary = not p.accept("UNSIGNED")
                if signed_binary:
                    p.accept("SIGNED")
                fixed_binary = ("S" if signed_binary else "") + f"9({FIXED_BINARY_DIGITS[usage]})"
                usage = "COMP-5"
            elif usage in C_TYPE_USAGES:
                digits, signed_binary = C_TYPE_USAGES[usage]
                fixed_binary = ("S" if signed_binary else "") + f"9({digits})"
                usage = "COMP-5"
            elif usage == "COMPUTATIONAL-5":
                usage = "COMP-5"
            elif usage == "COMPUTATIONAL-6":
                usage = "COMP-6"
            elif usage in FLOAT_USAGES:
                usage = FLOAT_USAGES[usage]
            elif usage in {"COMPUTATIONAL-X", "COMPUTATIONAL-N"}:
                usage = usage.replace("COMPUTATIONAL", "COMP")
    p.expect(".")
    if type_source is not None:
        # inherit_external_definition: only REDEFINES, EXTERNAL, GLOBAL,
        # OCCURS and VALUE go with SAME AS / TYPE TO.
        clause = "TYPE TO" if type_kind == "TYPE" else "SAME AS"
        if picture or variable_picture is not None or has_usage or sign_clause is not None or justified \
                or synchronized or blank_zero or any_length or based:
            p.error(f"illegal combination of {clause} with other clauses")
        source = p.fields[type_source]
        if source.usage in {"COMP-X", "COMP-N"} or source.picture_l or getattr(source, "comp_x_size", None):
            p.error(f"{clause} d'un article COMP-X/COMP-N ou PICTURE L non pris en charge")
        if any(owner == source.name or owner.startswith(source.name + ".") for owner in p.indexes.values()):
            p.error(f"{clause} d'une table INDEXED BY non pris en charge")
        if level == 77 and source.children:
            p.error("elementary item expected")
        usage = source.usage
        picture = "" if source.children or usage in {"POINTER", "INDEX"} | set(FLOAT_PICTURES) else source.picture
        # copy_into_field: target->usage = source->usage.
        has_usage = not source.children or source.group_usage is not None
        justified = justified or source.justified
        blank_zero = blank_zero or source.blank_zero
        synchronized = synchronized or source.synchronized
        if source.sign_clause:
            sign_clause = ("LEADING" if source.sign_leading else "TRAILING", source.sign_separate)
        any_length = source.any_length
        based = based or source.based
        if level in {1, 77} and source.external:
            external = True
        if source.explicit_value:
            if initial is not None:
                p.error("duplicate VALUE clause")
            initial, figurative = source.initial, None
        if (not p.t.string and p.t.key.isdigit() and int(p.t.key) not in {66, 77, 78, 88}
                and level < int(p.t.key) <= 49 and level != 77):
            p.error(f"entry following {clause} may not be subordinate to it")
    if variable_picture is not None:
        # field.c validate_group / validate_field_value for flag_picture_l.
        if initial is not None:
            p.error("variable-length PICTURE and VALUE are mutually exclusive")
        if justified:
            p.error(f"'{label}' cannot have JUSTIFIED RIGHT clause")
        if blank_zero:
            p.error(f"'{label}' cannot have BLANK WHEN ZERO clause")
        if has_usage or sign_clause is not None or synchronized or fixed_binary:
            p.error("USAGE, SIGN ou SYNCHRONIZED sur une PICTURE L non pris en charge")
    if fixed_binary:
        if picture:
            p.error("PICTURE incompatible avec USAGE BINARY-CHAR/SHORT/LONG/DOUBLE et les types C")
        picture = fixed_binary
    # USAGE INDEX without PICTURE is an elementary index data item, unless
    # subordinate entries follow (a group whose USAGE they inherit).
    has_children = (not p.t.string and p.t.key.isdigit() and level not in {66, 77}
                    and int(p.t.key) not in {66, 77, 88} and level < int(p.t.key) <= 49)
    # Group USAGE applies to subordinate elementary items without their own
    # USAGE; GnuCOBOL lets an explicit subordinate USAGE take precedence.
    ancestors = []
    cursor = parent
    while cursor:
        ancestors.append(p.fields[cursor])
        cursor = p.fields[cursor].parent
    if not has_usage:
        usage = next((a.group_usage for a in ancestors if a.group_usage), usage)
    if any(a.group_value is not None for a in ancestors) and initial is not None:
        p.error("VALUE subordonné à un VALUE de groupe non pris en charge")
    alnum_edit = ""

    def repeat(match):
        count = int(match[2])
        if count < 1:
            p.error("répétition PICTURE strictement positive requise")
        return match[1] * min(count, 65536)

    comp_x_size = None
    if usage in {"COMP-X", "COMP-N"} and not has_children:
        if not picture:
            p.error(f"PICTURE clause required for '{label}'")
        written = re.sub(r"([9XAVSP])\((\d+)\)", repeat, picture.upper())
        if re.fullmatch(r"X+", written):
            comp_x_size = len(written)
            picture = f"9({PIC_DIGITS[comp_x_size - 1] if comp_x_size <= 8 else 36})"
            if comp_x_size > 8:
                comp_x_size = 15
        elif re.fullmatch(r"S?9*V?9*", written) and "9" in written:
            digits_written = written.count("9")
            comp_x_size = next((size for limit, size in COMP_X_BYTES if digits_written <= limit), 9)
        else:
            p.error(f"PICTURE clause not compatible with USAGE {usage}")
        if comp_x_size > 8:
            # libcob overflows its 8-byte binary buffers (native crash).
            p.error(f"USAGE {usage} de plus de 8 octets non pris en charge")
    if usage in FLOAT_PICTURES and not has_children:
        if picture:
            p.error(f"'{label}' cannot have PICTURE clause")
        if justified or blank_zero or sign_clause is not None:
            p.error(f"JUSTIFIED, BLANK WHEN ZERO ou SIGN sur USAGE {usage} non pris en charge")
        if initial is not None and (initial.string or figurative not in {None, "0"}):
            # cobc only warns and copies the literal's bytes into the item.
            p.error(f"VALUE non numérique d'un article USAGE {usage} non pris en charge")
        picture = FLOAT_PICTURES[usage]
    if usage == "POINTER":
        # USAGE POINTER: a native data pointer (void *), 8 bytes on x86_64.
        if picture:
            p.error("PICTURE incompatible avec USAGE POINTER")
        if has_children:
            p.error("USAGE POINTER de groupe non pris en charge")
        if initial is not None and figurative != "NULL":
            p.error("VALUE d'un POINTER limité à NULL")
        picture = "9(18)"
    elif figurative == "NULL":
        p.error("VALUE NULL réservé à USAGE POINTER")
    if usage == "INDEX" and not picture and not has_children:
        if initial is not None:
            p.error("VALUE sur un article USAGE INDEX non pris en charge")
        # cobc: a native signed int (4 bytes), holding an occurrence number.
        picture = "S9(9)"
    elif usage == "INDEX" and picture:
        p.error("USAGE INDEX ne prend pas de PICTURE")
    expanded = re.sub(r"([9XZAP])\((\d+)\)", repeat, picture)
    if any_length:
        # field.c validate_any_length_item: an elementary 01 in LINKAGE.
        if not getattr(p, "in_linkage", False) or level != 1:
            p.error("ANY LENGTH réservé au niveau 01 de LINKAGE SECTION")
        if table or depending or has_children or initial is not None or blank_zero or external:
            p.error("définition ANY LENGTH invalide")
        if is_global:
            p.error("ANY LENGTH GLOBAL non pris en charge: partage du descripteur dynamique")
        if usage != "DISPLAY":
            p.error("ANY LENGTH avec USAGE autre que DISPLAY non pris en charge")
        if picture and (expanded != "X" or usage != "DISPLAY"):
            p.error("ANY LENGTH limité à PIC X DISPLAY; formats national et booléen non pris en charge")
        if not picture:
            picture = expanded = "X"
    def alphanumeric_digits(edit):
        """An unsigned integer VALUE of an alphanumeric item or a group (cobc:
        "alphanumeric value is expected"): cob_move of the literal, its
        digits, through cob_move_alphanum_to_edited for an edited item."""
        if (initial is None or figurative is not None or initial.string or value_signed
                or isinstance(initial, FloatLiteralToken) or not re.fullmatch(r"\d+", initial.text)):
            return initial
        text = initial.text
        if edit:
            source = iter(text)
            text = "".join(next(source, " ") if symbol in "AX9" else " " if symbol == "B" else symbol
                           for symbol in edit)
        return Token(text, initial.line, True)
    if not picture:
        initial = alphanumeric_digits("")
    group_value = group_usage = None
    if not picture:
        kind, digits, scale, signed = "text", 0, 0, False
        if level == 77:
            p.error("niveau 77 requiert une PICTURE")
        if initial is not None:
            if not initial.string and figurative != "0":
                p.error("VALUE de groupe limité à un littéral alphanumérique, ZERO ou SPACE")
            if not getattr(p, "in_communication", False):
                if file_record or redefines or any(a.redefines or a.file_record for a in ancestors):
                    p.error("VALUE de groupe sur FD/REDEFINES non pris en charge")
                group_value = (initial.text, figurative)
            # CD records are static storage that cobc never initializes.
        if has_usage:
            group_usage = usage
            usage = "DISPLAY"
        initial = None
    elif (re.fullmatch(r"[XA9B0/]+", re.sub(r"([XA9B0/])\((\d+)\)", repeat, picture.upper()))
          and set(picture.upper()) & set("XA") and set(re.sub(r"\(\d+\)", "", picture.upper())) & set("B0/")):
        # Alphanumeric-edited: stored and compared as text, edited on MOVE.
        alnum_edit = re.sub(r"([XA9B0/])\((\d+)\)", repeat, picture.upper())
        kind, digits, scale, signed = "text", len(alnum_edit), 0, False
        if digits > 65535 or usage != "DISPLAY":
            p.error("PIC alphanumérique éditée limitée à 65535 caractères DISPLAY")
    elif re.fullmatch(r"X+|A+", expanded) or (re.fullmatch(r"[XA9]+", expanded) and set(expanded) - {"9"}
                                                and len(set(expanded)) > 1):
        # PIC A is alphabetic: stored and compared like PIC X; the emitter
        # refuses the numeric MOVEs that GnuCOBOL rejects for it.
        kind, digits, scale, signed = "text", len(expanded), 0, False
        if digits > 65535 or usage != "DISPLAY":
            p.error("PIC X/A limité à 65535 caractères DISPLAY")
    elif re.fullmatch(r"S?(?:9+(?:V9*)?|V9+)", expanded):
        kind, digits, signed = "number", expanded.count("9"), expanded.startswith("S")
        scale = len(expanded.split("V")[1]) if "V" in expanded else 0
        if digits > 38:
            # cb_build_picture: COB_MAX_DIGITS.
            p.error("numeric field cannot be larger than 38 digits")
    elif re.fullmatch(r"S?9+P+V?|S?V?P+9+", expanded):
        # Scaling positions, as cobc's picture analysis: trailing P give a
        # negative scale (units of 10^n), leading P an implicit V before them.
        # Only the 9 positions are stored; P is limited to USAGE DISPLAY.
        kind, digits, signed = "number", expanded.count("9"), expanded.startswith("S")
        positions = expanded.count("P")
        scale = -positions if expanded.lstrip("S").startswith("9") else positions + digits
        if digits > 18:
            p.error("PICTURE P limitée à 18 chiffres")
    elif (re.fullmatch(r"[9Z*+\-$.,VPB0/()0-9]*(?:CR|DB)?", picture.upper())
          and set(re.sub(r"\(\d+\)", "", picture.upper())) - set("9VP")):
        kind = "edited"
        symbols, edit_size, digits, scale, signed = edited_picture(p, picture)
        if digits > 38 or edit_size > 256 or usage != "DISPLAY":
            p.error("PIC éditée limitée à 38 chiffres, 256 caractères DISPLAY")
    else:
        p.error(f"PICTURE non prise en charge: {picture}")
    if usage == "POINTER":
        kind, signed = "pointer", False
    if picture and kind == "text":
        initial = alphanumeric_digits(alnum_edit)
        if figurative == "0" and initial is not None and set(expanded) <= {"A", "B"} and "A" in expanded:
            # validate_move (is_value): ZERO to an alphabetic item.
            p.error("invalid VALUE clause")
    if kind == "number" and digits > 18 and usage in {"COMP", "COMPUTATIONAL", "BINARY", "COMP-4", "COMPUTATIONAL-4",
                                                       "COMP-5", "COMPUTATIONAL-5"}:
        # compute_size: BINARY and COMP-5 items hold at most 18 digits.
        p.error(f"'{label}' binary field cannot be larger than 18 digits")
    if usage == "COMP-6" and kind == "number" and signed:
        # validate_field_1: "COMP-6 with sign - changing to COMP-3".
        usage = "COMP-3"
    if blank_zero:
        # field.c: a numeric DISPLAY item with BLANK WHEN ZERO becomes
        # numeric-edited with a reconstructed 9(n) picture.
        if kind == "number" and usage == "DISPLAY" and not signed and scale == 0:
            kind, symbols, edit_size = "edited", [("9", digits)], digits
        elif kind != "edited" or any(c == "*" for c, _ in symbols):
            p.error("BLANK WHEN ZERO limité aux PICTURE éditées sans * et aux entiers DISPLAY non signés")
    if figurative == "0" and initial is not None and kind == "text" and picture and not alnum_edit:
        # VALUE ZERO of an alphanumeric item: zeros in every position.
        initial = Token("0" * digits, initial.line, True)
    if isinstance(figurative, tuple) and figurative[1] == "0" and kind == "number":
        # VALUE ALL ZERO of a numeric item is its zero value.
        initial, figurative = Token("0", initial.line), "0"
    if isinstance(figurative, tuple):
        if kind != "text" or alnum_edit:
            p.error("VALUE ALL limité aux PIC X/A et groupes")
        if picture:
            initial = Token((figurative[1] * digits)[:digits], initial.line, True)
    elif isinstance(figurative, str) and figurative not in {"0", " "} and initial is not None and kind == "text":
        # A figurative constant fills every position of the item.
        initial = Token(figurative * digits, initial.line, True)
    explicit_sign_clause = sign_clause is not None
    group_sign = None
    if not picture:
        # A group SIGN clause applies to its signed numeric DISPLAY items.
        group_sign, sign_clause = sign_clause, None
    elif sign_clause is None:
        sign_clause = next((a.group_sign for a in ancestors if a.group_sign), None)
        if sign_clause and not (kind == "number" and signed and usage == "DISPLAY"):
            sign_clause = None
    if sign_clause and not (kind == "number" and signed and usage == "DISPLAY"):
        p.error("SIGN requiert une PICTURE numérique signée USAGE DISPLAY")
    if justified and (kind != "text" or alnum_edit or not picture):
        p.error("JUSTIFIED limité aux PIC X/A élémentaires")
    if initial is not None and getattr(p, "in_communication", False):
        if kind != "edited" and picture and (kind == "text") != initial.string:
            p.error("VALUE incompatible avec la PICTURE")
        initial = None
    explicit_value = initial is not None
    if initial is not None:
        if file_record or redefines:
            p.error("VALUE sur FD/REDEFINES non pris en charge")
        if kind != "edited" and (kind == "text") != initial.string:
            p.error("VALUE incompatible avec la PICTURE")
        if kind == "number" and value_signed and not signed:
            p.error("data item not signed")
    else:
        initial = Token("" if kind == "text" else "0", p.t.line, kind == "text")
    linkage = getattr(p, "in_linkage", False)
    # The VALUE of a BASED item only serves ALLOCATE ... INITIALIZED.
    under_based = based or any(getattr(a, "based", False) for a in ancestors)
    if linkage and not under_based and (explicit_value or group_value is not None):
        p.error("VALUE en LINKAGE SECTION non pris en charge")
    if isinstance(initial, FloatLiteralToken) and kind != "number":
        # Its digits with a negative scale, not its value (see check_floating_literals).
        p.error("VALUE littéral flottant d'un article non numérique non pris en charge")
    descriptor = Field(key, picture, kind, digits, scale, signed, initial, usage,
                       label, level, parent, [], count, table, redefines, filler, file_record)
    if comp_x_size is not None:
        descriptor.comp_x_size = comp_x_size
    descriptor.linkage = linkage
    descriptor.any_length = any_length
    descriptor.explicit_value = explicit_value
    descriptor.occurs_min, descriptor.depending = minimum, depending
    descriptor.search_keys = search_keys
    descriptor.group_value, descriptor.group_usage = group_value, group_usage
    descriptor.editing = expanded if kind == "edited" else ""
    descriptor.alnum_edit = alnum_edit
    descriptor.synchronized = synchronized
    descriptor.group_sign = group_sign
    descriptor.sign_clause = explicit_sign_clause
    descriptor.sign_leading = bool(sign_clause and sign_clause[0] == "LEADING")
    descriptor.sign_separate = bool(sign_clause and sign_clause[1])
    descriptor.justified = justified
    descriptor.external, descriptor.is_global = external, is_global
    # cb_to_cname: the name cob_external_addr looks up.
    descriptor.external_name = (external_as or label).upper().replace("-", "_").replace(" ", "_") if external else None
    descriptor.based = based
    if kind == "edited":
        descriptor.edit_symbols, descriptor.edit_size = symbols, edit_size
        descriptor.blank_zero = blank_zero
    descriptor.picture_l = variable_picture is not None
    descriptor.typedef = typedef
    if type_source is not None:
        source = p.fields[type_source]
        if source.external and level in {1, 77}:
            descriptor.external_name = source.external_name
        if source.children and descriptor.group_value is None:
            descriptor.group_value = source.group_value
        if source.children:
            descriptor.group_usage = source.group_usage
    if implicit_child:
        # cb_build_field (cb_build_filler ()) without flag_filler: INITIALIZE
        # treats it as a named item.
        descriptor.filler = False
    p.fields[key] = descriptor
    if parent:
        p.fields[parent].children.append(key)
    p.data_stack.append(key)
    p.last_data = key
    if typedef:
        p.__dict__.setdefault("typedefs", {})[label.upper()] = key
    if type_source is not None:
        copy_type(p, type_source, key, level)
    if variable_picture is not None:
        if has_children:
            p.error("donnée subordonnée à une PICTURE L non prise en charge")
        line = depending_tokens[0].line
        written = re.sub(r"([XA9])\((\d+)\)", lambda m: m[1] * int(m[2]), variable_picture)
        implicit = [Token(str(min(level + 1, 49)), line), Token("PIC", line), Token(variable_picture[0], line),
                    Token("OCCURS", line), Token("1", line), Token("TO", line), Token(str(len(written)), line),
                    Token("DEPENDING", line), Token("ON", line), *depending_tokens, Token(".", line)]
        p.tokens[p.i:p.i] = implicit
        p.picture_l_child = key
    return key
