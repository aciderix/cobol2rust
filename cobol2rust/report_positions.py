"""Native integer expression preparation for Report Writer SOURCE positions."""

from dataclasses import dataclass


@dataclass
class _Literal:
    coefficient: int
    scale: int
    size: int


@dataclass
class _Operation:
    op: str
    left: object
    right: object


def normalize(p, expr):
    """Return the prepared expression and cb_get_int of an actual literal.

    Keep decimal coefficients until cb_build_binary_op has finished folding.
    output_integer then reads literal coefficients without their scale and
    evaluates remaining arithmetic as integer operations, node by node.
    """
    from .frontend import Expr

    def fail(reason):
        p.error(f"position de SOURCE de rapport non prise en charge: {reason}")

    def signed64(value):
        if not -(1 << 63) <= value < (1 << 63):
            fail("dépassement entier signé 64 bits lors du pliage constant")
        return value

    def literal(value, scale=0):
        return _Literal(value, scale, len(str(abs(value))))

    def quotient(x, y):
        # C signed division truncates towards zero, without float conversion.
        return (abs(x) // abs(y)) * (-1 if (x < 0) != (y < 0) else 1)

    def operation(op, x, y):
        # cobc/tree.c cb_build_binary_op: the identity branch is an ELSE of
        # the two-literal branch, including when its size/scale guard fails.
        if isinstance(x, _Literal) and isinstance(y, _Literal):
            if x.size >= x.scale and y.size >= y.scale:
                # atoll reads unsigned digit text before applying literal
                # signs, so even LLONG_MIN cannot enter this fold safely.
                if abs(x.coefficient) >= (1 << 63) or abs(y.coefficient) >= (1 << 63):
                    fail("littéral hors de la plage atoll 64 bits lors du pliage constant")
                xv, yv = signed64(x.coefficient), signed64(y.coefficient)
                xs, ys, scale, result, folded = x.scale, y.scale, 0, 0, False
                if op in {"+", "-"}:
                    while xs < ys:
                        xv, xs = signed64(xv * 10), xs + 1
                    while ys < xs:
                        yv, ys = signed64(yv * 10), ys + 1
                    scale = xs
                    result = signed64(xv + yv if op == "+" else xv - yv)
                    folded = True
                elif op == "*":
                    scale, result, folded = xs + ys, signed64(xv * yv), True
                elif op == "/" and yv:
                    while ys > 0:
                        xv, ys = signed64(xv * 10), ys - 1
                    scale = xs
                    q = signed64(quotient(xv, yv))
                    if xv == q * yv:
                        result = q
                        folded = q != 0 or (x.scale == 0 and y.scale == 0)
                elif op == "**" and xs == 0 and ys == 0 and yv >= 0:
                    # cb_build_binary_op multiplies in signed64. Check each
                    # product, but avoid its linear loop for huge exponents.
                    if yv == 0 or xv == 1:
                        result = 1
                    elif xv in {0, -1}:
                        result = 0 if xv == 0 else (-1 if yv % 2 else 1)
                    else:
                        if yv > 63:
                            fail("dépassement entier signé 64 bits lors du pliage constant")
                        result = xv
                        for _ in range(yv - 1):
                            result = signed64(result * xv)
                    folded = True
                if folded:
                    while scale > 0 and result != 0 and result % 10 == 0:
                        result, scale = quotient(result, 10), scale - 1
                    return literal(result, scale)
        elif isinstance(y, _Literal) and y.scale == 0:
            if op in {"+", "-"} and y.coefficient == 0:
                return x
            if op in {"*", "/"} and y.coefficient == 1:
                return x
            if op == "*" and y.coefficient == 0:
                return literal(0)
        return _Operation(op, x, y)

    def prepare(node):
        if node.op == "number" and not node.figurative_zero:
            text = node.args[0]
            scale = len(text.partition(".")[2])
            digits = text.replace(".", "").lstrip("+-")
            return _Literal(int(text.replace(".", "")), scale, len(digits))
        if node.op in {"unary+", "unary-"}:
            child = prepare(node.args[0])
            if node.op == "unary+":
                return child
            if node.signed_literal and isinstance(child, _Literal):
                return _Literal(-child.coefficient, child.scale, child.size)
            # parser.y exp_unary: a separate minus is cb_zero - exp_atom.
            # cb_zero is a figurative CONST, not a foldable numeric literal.
            return operation("-", Expr("number", ("0",), figurative_zero=True), child)
        if node.op in {"+", "-", "*", "/", "**"}:
            return operation(node.op, prepare(node.args[0]), prepare(node.args[1]))
        return node

    def emit(node, operand=False):
        if isinstance(node, _Literal):
            # tree.c cb_get_int: positive scale is deliberately ignored.
            if not -(1 << 31) <= node.coefficient < (1 << 31):
                fail("littéral hors de la plage cb_get_int 32 bits")
            return Expr("number", (str(node.coefficient),))
        if isinstance(node, _Operation):
            if node.op == "**":
                fail("exponentiation entière non pliée (cob_s32_pow)")
            if node.op == "/" and ((isinstance(node.right, _Literal) and node.right.coefficient == 0)
                                    or (isinstance(node.right, Expr) and node.right.figurative_zero)):
                fail("division entière par zéro")
            inner = Expr(node.op, (emit(node.left, True), emit(node.right, True)))
            return Expr("report_integer", (inner,))
        # output_integer converts field/intrinsic leaves before parent math.
        return Expr("report_integer", (node,)) if operand else node

    prepared = prepare(expr)
    return emit(prepared, True), prepared.coefficient if isinstance(prepared, _Literal) else None
