"""Port of GnuCOBOL 3.2 cb_build_expr (cobc/typeck.c).

The parser turns an expression into the token list of parser.y's
expr_tokens; this module reduces it with the same priority stack, which
gives cobc's precedence, NOT placement and abbreviated combined relation
conditions ("A = 1 OR 2", "A NOT = B AND > C").
"""
from __future__ import annotations

from .frontend import CobolError, Expr

PRIO = {"x": 0, "^": 1, "*": 2, "/": 2, "+": 3, "-": 3,
        "=": 4, "~": 4, "<": 4, ">": 4, "[": 4, "]": 4,
        "!": 5, "&": 6, "|": 7, ")": 8, "(": 9, 0: 10}
RELATIONAL = {"=", "~", "<", ">", "[", "]"}
# cobc's '[' is <=, ']' is >=, '~' is not equal.
COMPARISON = {"=": "cmp=", "~": "cmp<>", "<": "cmp<", ">": "cmp>", "[": "cmp<=", "]": "cmp>="}
NEGATED = {"=": "~", "~": "=", "<": "]", ">": "[", "[": ">", "]": "<"}
BOOLEAN = {"and", "or", "not", "condition", "bool", "numeric_class", "user_class", "switch", "alpha_class"}
TOPSTACK = 3


def is_boolean(e):
    while e is not None and e.op == "paren":
        e = e.args[0]
    return e is not None and (e.op in BOOLEAN or e.op.startswith("cmp"))


def is_zero(e):
    return e is not None and e.op == "number" and e.figurative_zero


def binary(x, op, y):
    if op in RELATIONAL:
        return Expr(COMPARISON[op], (x, y))
    if op in {"&", "|"}:
        return Expr("and" if op == "&" else "or", (x, y))
    if op == "^":
        raise CobolError("exponentiation non prise en charge")
    return Expr(op, (x, y))


def negation(x):
    return Expr("not", (x,))


def expand(e):
    """build_expr_expand: drop the parentheses markers."""
    while e.op == "paren":
        e = e.args[0]
    if e.op in {"and", "or", "not", "+", "-", "*", "/", "unary-", "unary+"} or e.op.startswith("cmp"):
        return Expr(e.op, tuple(expand(a) for a in e.args), e.figurative_zero, e.figurative_space, e.literal_all)
    return e


class Builder:
    def __init__(self, error):
        self.error = error
        self.stack = [[0, None] for _ in range(TOPSTACK)]
        self.index = TOPSTACK
        self.op = 0
        self.lh = None

    def _slot(self, offset):
        i = self.index + offset
        while len(self.stack) <= i:
            self.stack.append([0, None])
        return self.stack[i]

    def token(self, offset):
        return self._slot(offset)[0] if self.index + offset >= 0 else 0

    def value(self, offset):
        return self._slot(offset)[1]

    def set(self, offset, token=None, value=None):
        slot = self._slot(offset)
        if token is not None:
            slot[0] = token
        slot[1] = value

    def check_condition(self, lh, rhs):
        # expr_chk_cond: an 88 level cannot be a relation operand.
        if lh.op == "condition" or rhs.op == "condition":
            self.error("condition de niveau 88 comme opérande d'une relation")

    def reduce(self, token):
        """build_expr_reduce; its -1 results (nothing to reduce) are plain returns."""
        while PRIO[self.token(-2)] <= PRIO[token]:
            op = self.token(-2)
            if op in {"x", "(", ")"}:
                return
            if op in {"+", "-", "*", "/", "^"}:
                if self.token(-1) != "x" or self.token(-3) != "x":
                    return  # -1: nothing reducible, as in cobc
                self.set(-3, "x", binary(self.value(-3), op, self.value(-1)))
                self.index -= 2
            elif op == "!":
                if self.token(-1) != "x":
                    return  # -1: nothing reducible, as in cobc
                if self.lh is not None and not is_boolean(self.value(-1)):
                    self.set(-1, value=binary(self.lh, self.op, self.value(-1)))
                self.set(-2, "x", negation(self.value(-1)))
                self.index -= 1
            elif op in {"&", "|"}:
                if self.token(-1) != "x" or self.token(-3) != "x":
                    return  # -1: nothing reducible, as in cobc
                if self.lh is not None:
                    if not is_boolean(self.value(-1)):
                        self.set(-1, value=binary(self.lh, self.op, self.value(-1)))
                    if not is_boolean(self.value(-3)):
                        self.set(-3, value=binary(self.lh, self.op, self.value(-3)))
                self.set(-3, "x", binary(self.value(-3), op, self.value(-1)))
                self.index -= 2
            else:
                # Relational operators.
                if self.token(-1) != "x":
                    return  # -1: nothing reducible, as in cobc
                lhs = self.value(-1)
                if self.token(-3) == "!":
                    op = NEGATED[op]
                    self.index -= 1
                if self.token(-3) == "x":
                    # Simple condition: 'x' op 'x'
                    self.lh = self.value(-3)
                    self.check_condition(self.lh, lhs)
                    self.op = op
                    self.set(-3, "x", binary(self.lh, op, lhs) if not is_boolean(lhs) else lhs)
                    self.index -= 2
                elif self.token(-3) in {"&", "|"}:
                    # Abbreviated: 'x' '=' 'x' '|' op 'x'
                    self.op = op
                    self.set(-2, "x", binary(self.lh, op, lhs) if not is_boolean(lhs) and self.lh is not None else lhs)
                    self.index -= 1
                else:
                    return  # -1: nothing reducible, as in cobc
        # Special case "op OR x AND"
        if token == "&" and self.token(-2) == "|" and not is_boolean(self.value(-1)):
            if self.lh is None:
                self.error("expression invalide")
            self.set(-1, "x", binary(self.lh, self.op, self.value(-1)))

    def shift_sign(self, op):
        have_not = self.token(-1) == "!"
        if have_not:
            self.index -= 1
        self.reduce("=")
        if self.token(-1) == "x":
            result = binary(self.value(-1), op, Expr("number", ("0",), figurative_zero=True))
            self.set(-1, value=negation(result) if have_not else result)

    def shift_class(self, make):
        have_not = self.token(-1) == "!"
        if have_not:
            self.index -= 1
        self.reduce("=")
        if self.token(-1) == "x":
            result = make(self.value(-1))
            self.set(-1, value=negation(result) if have_not else result)

    def shift(self, token, value=None):
        if token == "x":
            # Sign ZERO condition
            if is_zero(value) and self.token(-1) in {"x", "!"}:
                self.shift_sign("=")
                return
            # Unary sign
            if self.token(-1) in {"+", "-"} and self.token(-2) != "x":
                if self.token(-1) == "-":
                    value = Expr("unary-", (value,))
                self.index -= 1
        elif token == "(":
            if self.token(-1) in RELATIONAL:
                self.op = self.token(-1)
                if self.token(-2) == "x":
                    self.lh = self.value(-2)
        elif token == ")":
            self.reduce(token)
            inner = self.value(-1)
            if inner is not None and inner.op in COMPARISON.values():
                # A parenthesized relation cannot start an abbreviated condition.
                self.lh = None
            if self.token(-2) == "(":
                value = Expr("paren", (inner,)) if inner is not None else None
                self.index -= 2
                self.shift("x", value)
                return
        self.reduce(token)
        slot = self._slot(0)
        slot[0], slot[1] = token, value
        self.index += 1

    def finish(self):
        self.reduce(0)
        if self.index != TOPSTACK + 1 or self.stack[TOPSTACK][1] is None or self.stack[TOPSTACK][0] != "x":
            self.error("invalid expression: unfinished expression")
        return expand(self.stack[TOPSTACK][1])


def build(tokens, error):
    """cb_build_expr over (op, value) tokens; class tokens carry a builder."""
    b = Builder(error)
    has_rel = has_con = has_var = bad_cond = False
    for op, value in tokens:
        if op == "class":
            b.shift_class(value)
            has_rel = True
            continue
        if op in {"P", "N"}:
            b.shift_sign(">" if op == "P" else "<")
            has_rel = True
            continue
        if b.token(-1) == "!" and op in RELATIONAL:
            # NOT followed by a relation is the negated relation.
            b.set(-1, token=NEGATED[op], value=None)
            continue
        if op == "x":
            if has_var and is_zero(value):
                has_rel = True
            has_var = True
            if value.op in {"condition", "switch"} or value.op.startswith("cmp"):
                has_rel = True
        elif op in {"|", "&"}:
            has_con = True
            if has_var and not has_rel:
                bad_cond = True
        elif op in RELATIONAL or op == "!":
            has_rel = True
        b.shift(op, value)
    if bad_cond:
        error("invalid conditional expression")
    return b.finish()
