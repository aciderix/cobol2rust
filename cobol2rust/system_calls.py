"""Scalar ABI and signatures of the supported libcob byte routines."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .frontend import Expr


# system.def: pointer arguments followed by an int byte count.
CATALOG = {
    "CBL_AND": ("and", 3),
    "CBL_OR": ("or", 3),
    "CBL_NOR": ("nor", 3),
    "CBL_XOR": ("xor", 3),
    "CBL_IMP": ("imp", 3),
    "CBL_NIMP": ("nimp", 3),
    "CBL_EQ": ("eq", 3),
    "CBL_NOT": ("not", 2),
    "CBL_TOUPPER": ("upper", 2),
    "C$TOUPPER": ("upper", 2),
    "CBL_TOLOWER": ("lower", 2),
    "C$TOLOWER": ("lower", 2),
}


# fileio.c byte-stream file and directory routines (file_runtime::routines).
FILE_ROUTINES = {"CBL_OPEN_FILE", "CBL_CREATE_FILE", "CBL_READ_FILE", "CBL_WRITE_FILE", "CBL_CLOSE_FILE",
                 "CBL_FLUSH_FILE", "CBL_DELETE_FILE", "CBL_COPY_FILE", "CBL_CHECK_FILE_EXIST", "CBL_RENAME_FILE",
                 "CBL_GET_CURRENT_DIR", "CBL_CREATE_DIR", "CBL_CHANGE_DIR", "CBL_DELETE_DIR", "C$MAKEDIR",
                 "C$CHDIR", "C$COPY", "C$FILEINFO", "C$DELETE"}
# common.c routines: without module state (system_runtime) or reading the
# current module (RunUnit::module_routine).
LIBRARY_ROUTINES = {"CBL_GC_GETOPT", "SYSTEM", "C$SLEEP", "C$GETPID", "C$JUSTIFY", "C$PRINTABLE", "C$NARG", "C$PARAMSIZE",
                    "C$CALLEDBY"}
# Routines whose C parameters are ints passed BY VALUE.
VALUE_ROUTINES = {"CBL_GET_CURRENT_DIR", "CBL_GC_GETOPT"}
SYSTEM_ROUTINES = set(CATALOG) | FILE_ROUTINES | LIBRARY_ROUTINES


@dataclass(frozen=True)
class Scalar:
    operand: Expr
    size: int | str = 8
    unsigned: bool = False


def scalar_expression(emitter, scalar):
    """output_call_by_value_args, then the system routine's C int parameter.

    Preserve get_size_parameter_type's inverted sign argument in its callers;
    a narrow unsigned C value promotes differently from a narrow signed one.
    """
    from .frontend import CobolError

    def fail(reason):
        raise CobolError(f"argument scalaire d'appel système non pris en charge: {reason}")

    size = 4 if scalar.size == "DEFAULT" else scalar.size
    if size not in {1, 2, 4, 8, "AUTO"}:
        fail(f"SIZE {scalar.size}")
    operand, sign = scalar.operand, 1
    if operand.op in {"unary+", "unary-"}:
        if not operand.signed_literal or operand.args[0].op != "number":
            fail("signe séparé d'un littéral numérique")
        sign = -1 if operand.op == "unary-" else 1
        operand = operand.args[0]
    if operand.op == "number":
        text = operand.args[0]
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", text):
            fail("littéral numérique")
        # cb_get_long_long / cb_get_u_long_long deliberately ignore scale.
        digits = text.replace(".", "").lstrip("+-")
        value = sign * int(text.replace(".", ""))
        if scalar.unsigned and (sign < 0 or text.startswith("-")):
            fail("littéral négatif avec UNSIGNED")
        if size in {8, "AUTO"} and len(digits) > (20 if scalar.unsigned else 19):
            # cb_emit_call checks the untrimmed literal size before the
            # cb_get_[u_]long_long conversion, including leading zeroes.
            fail("littéral hors des bornes de SIZE")
        lower, upper = (0, (1 << 64) - 1) if scalar.unsigned else (-(1 << 63), (1 << 63) - 1)
        if not lower <= value <= upper:
            fail("littéral hors de la plage 64 bits native")
        if size in {1, 2, 4}:
            bits = 8 * size
            lower, upper = ((0, (1 << bits) - 1) if scalar.unsigned else
                            (-(1 << (bits - 1)), (1 << (bits - 1)) - 1))
            if not lower <= value <= upper:
                fail("littéral hors des bornes de SIZE")
        elif size == "AUTO":
            # The signed branch only checks the upper bound, even for a
            # negative literal whose magnitude needs more than 32 bits.
            limit = (1 << 32) - 1 if scalar.unsigned else (1 << 31) - 1
            size = 8 if value > limit else 4
        source = f"({value}i128)"
        cast_unsigned = not scalar.unsigned
    elif operand.op == "var":
        ref = operand.args[0]
        field = emitter.program.fields[ref.name]
        if ref.start is not None or field.kind not in {"number", "edited"} or field.children:
            fail("longueur BY VALUE requise sous forme numérique")
        reader = "system_integer_unoptimized" if field.sign_clause else "system_integer"
        source = f"storage_runtime::{reader}(&{emitter.reference(ref)})"
        if field.usage == "INDEX":
            # INDEX / LENGTH bypass the SIZE cast in codegen.c.
            return f"(({source}) as i32)"
        if field.usage not in {"DISPLAY", "BINARY", "COMP-5", "COMP-3", "COMP-6"}:
            fail(f"USAGE {field.usage}")
        if size == "AUTO":
            native_digits = field.digits + (max(0, -field.scale) if field.kind == "number" else 0)
            width = native_digits - field.scale if field.usage in {"DISPLAY", "COMP-3", "COMP-6"} else field.size
            size = 8 if width == 0 else 1 if width == 1 else 2 if width == 2 else 4 if width in {3, 4} else 8
            cast_unsigned = field.signed
        else:
            cast_unsigned = not scalar.unsigned
    elif operand.op == "function":
        if emitter.kind(operand) != "number":
            fail("FUNCTION numérique requise")
        name, args = operand.args
        if name in {"ABS", "MAX", "MIN", "MEDIAN"} or (name == "MEAN" and len(args) == 1):
            fail(f"description conservée du résultat de FUNCTION {name}")
        # A numeric intrinsic always uses cob_get_int; SIZE is ignored.
        return f"((storage_runtime::system_integer(&({emitter.expression(operand)}))) as i32)"
    else:
        fail("opérande limité à un littéral, champ ou FUNCTION numérique")
    cast = ("u" if cast_unsigned else "i") + str(8 * size)
    return f"((({source}) as {cast}) as i32)"
