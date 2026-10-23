from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import compiler_env, find_tool
from cobol2rust.verification import verify


def program(data, body="stop run."):
    return ("identification division.\nprogram-id. numeric-edited-test.\n"
            "data division.\nworking-storage section.\n" + data +
            "\nprocedure division.\n" + body + "\n")


class EditedPictureTests(unittest.TestCase):
    def test_decimal_picture_point_is_distinct_from_declaration_terminator(self):
        parsed = Parser(program("""
01 first-a pic -9(9).9(9).
01 second-a pic +9.99 value 1.23.
01 table-a.
   9 first-cell pic 9.
   9 second-cell pic 9.
""")).parse()
        self.assertEqual(parsed.fields["FIRST-A"].picture, "-9(9).9(9)")
        self.assertEqual(parsed.fields["FIRST-A"].editing, "-999999999.999999999")
        self.assertEqual(parsed.fields["SECOND-A"].picture, "+9.99")
        self.assertEqual(parsed.fields["SECOND-A"].initial.text, "1.23")
        self.assertEqual(parsed.fields["TABLE-A.FIRST-CELL"].picture, "9")
        self.assertEqual(parsed.fields["TABLE-A.SECOND-CELL"].picture, "9")

    def test_edited_size_counts_sign_and_point_separately_from_digit_capacity(self):
        parsed = Parser(program("""
01 nist-a pic -9(9).9(9).
01 fractional-a pic -.9(18).
01 suppressed-a pic Z(2)9.99.
""")).parse()
        nist = parsed.fields["NIST-A"]
        self.assertEqual((nist.kind, nist.digits, nist.scale, nist.size), ("edited", 18, 9, 20))
        fractional = parsed.fields["FRACTIONAL-A"]
        self.assertEqual((fractional.digits, fractional.scale, fractional.size), (18, 18, 20))
        suppressed = parsed.fields["SUPPRESSED-A"]
        self.assertEqual((suppressed.editing, suppressed.digits, suppressed.scale, suppressed.size),
                         ("ZZ9.99", 5, 2, 6))

    def test_unsupported_editing_and_capacities_are_rejected(self):
        # Order errors follow cobc's precedence table; S, capacities and
        # non-DISPLAY usages stay outside the edited subset.
        for picture in ("ZZ9.9Z", "+9+", "9.Z9", "$9$", "+99CR", "PPZZ", "-.--", "9-9",
                        "S9.99", "+9(19)", "-.9(19)", "Z(0)9", "Z9 comp", "**9 blank when zero",
                        "s99 blank when zero", "9v9 blank when zero"):
            with self.subTest(picture=picture), self.assertRaises(CobolError):
                Emitter(Parser(program(f"01 edited-a pic {picture}.")).parse()).generate()

    def test_unimplemented_conversions_and_numeric_operands_are_rejected(self):
        data = "01 edited-a pic -9(3).99. 01 other-a pic +9(3).99. 01 number-a pic s9(4)v99."
        for body in (
            "move spaces to edited-a.",
            "move edited-a to number-a.",
            "move edited-a to other-a.",
            "compute number-a = edited-a + 1.",
            "add edited-a to number-a.",
            "add 1 to edited-a.",
            "accept edited-a.",
            "perform varying edited-a from 1 by 1 until number-a > 3 continue end-perform.",
        ):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(data, body)).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class EditedPictureNativeTests(unittest.TestCase):
    def test_rendering_rounding_storage_and_initialization_match_expected_bytes(self):
        data = """
01 source-a pic s9(12)v9(4).
01 integer-a pic -9(9).
01 minus-a pic -9(3).99.
01 plus-a pic +9(3).99.
01 unsigned-a pic 9.99.
01 fraction-a pic -.9(18).
01 nist-a pic -9(9).9(9).
01 suppressed-a pic Z(2)9.99.
01 class-a pic Z9.
01 class-bytes redefines class-a pic xx.
01 numeric-initial pic -9(3).99 value -12.34.
01 text-initial pic -9(3).99 value "12.3".
01 arbitrary-initial pic -9(3).99 value "ABCDEFG".
01 bytes-a pic x(7).
01 edited-view redefines bytes-a pic -9(3).99.
01 text-a pic x(12).
"""
        body = """
display "INIT:[" minus-a "][" plus-a "][" suppressed-a "][" fraction-a "]"
display "VALUE:[" numeric-initial "][" text-initial "][" arbitrary-initial "]"
move -0.9999 to source-a move source-a to integer-a
display "SCALE-ZERO:[" integer-a "]"
move -1000000000 to source-a move source-a to integer-a
display "LEFT-ZERO:[" integer-a "]"
move -12345678901.2345 to source-a move source-a to integer-a
display "LEFT:[" integer-a "]"
move -123.4567 to source-a move source-a to nist-a
display "NIST:[" nist-a "]"
move -0.123456789012345678 to fraction-a
display "FRACTION:[" fraction-a "]"
compute minus-a rounded = 1.245
display "ROUND-POS:[" minus-a "]"
compute minus-a rounded = -1.245
display "ROUND-NEG:[" minus-a "]"
move minus-a to text-a
display "TO-TEXT:[" text-a "]"
move 1.24 to source-a add 0.005 to source-a giving plus-a rounded
display "GIVING:[" plus-a "]"
compute minus-a rounded = 1234.995
display "ROUND-LEFT:[" minus-a "]"
move -1.239 to unsigned-a
display "UNSIGNED:[" unsigned-a "]"
move -12.345 to suppressed-a
display "SUPPRESS:[" suppressed-a "]"
initialize minus-a suppressed-a
display "INITIALIZE:[" minus-a "][" suppressed-a "]"
move 12 to class-a
if class-a is numeric display "CLASS:NUM" else display "CLASS:NOT" end-if
move 2 to class-a
if class-a is numeric display "CLASS:NUM" else display "CLASS:NOT" end-if
move "34" to class-bytes
if class-a is numeric display "ALIAS:NUM" else display "ALIAS:NOT" end-if
display "ALIAS:[" class-a "]"
move "1234567" to bytes-a
if edited-view is numeric display "RAW:NUM" else display "RAW:NOT" end-if
display "RAW:[" edited-view "]"
if edited-view(1:7) = "1234567" display "SLICE-COMPARE:RAW" else display "SLICE-COMPARE:BAD" end-if
evaluate edited-view(1:7)
when "1234567" display "SLICE-EVALUATE:RAW"
when other display "SLICE-EVALUATE:BAD"
end-evaluate
stop run.
"""
        expected = "\n".join([
            "INIT:[ 000.00][+000.00][  0.00][ .000000000000000000]",
            "VALUE:[-012.34][12.3   ][ABCDEFG]",
            "SCALE-ZERO:[ 000000000]",
            "LEFT-ZERO:[-000000000]",
            "LEFT:[-345678901]",
            "NIST:[-000000123.456700000]",
            "FRACTION:[-.123456789012345678]",
            "ROUND-POS:[ 001.25]",
            "ROUND-NEG:[-001.25]",
            "TO-TEXT:[-001.25     ]",
            "GIVING:[+001.25]",
            "ROUND-LEFT:[ 235.00]",
            "UNSIGNED:[1.23]",
            "SUPPRESS:[ 12.34]",
            "INITIALIZE:[ 000.00][  0.00]",
            "CLASS:NUM",
            "CLASS:NOT",
            "ALIAS:NUM",
            "ALIAS:[34]",
            "RAW:NUM",
            "RAW:[1234567]",
            "SLICE-COMPARE:RAW",
            "SLICE-EVALUATE:RAW",
        ]) + "\n"
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "edited.cob"
            source.write_text(program(data, body), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], expected)
        self.assertEqual(report["rust_stdout"], expected)
        self.assertEqual((report["cobol_exit"], report["rust_exit"]), (0, 0))

    def test_native_edited_comparison_cannot_be_replaced_with_raw_text_comparison(self):
        contents = program('01 bytes-a pic x(7). 01 edited-a redefines bytes-a pic -9(3).99.', '''
move "1234567" to bytes-a
display edited-a
if edited-a = "1234567" display "COMPARE:RAW" else display "COMPARE:BAD" end-if
evaluate edited-a
when "1234567" display "EVALUATE:RAW"
when other display "EVALUATE:BAD"
end-evaluate stop run.
''')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, binary = root / "comparison.cob", root / "comparison"
            source.write_text(contents, encoding="utf-8")
            cobc = find_tool("cobc")
            compilation = subprocess.run([cobc, "-free", "-x", str(source), "-o", str(binary)],
                                         capture_output=True, env=compiler_env(cobc), timeout=60)
            self.assertEqual(compilation.returncode, 0, compilation.stderr.decode(errors="replace"))
            native = subprocess.run([str(binary)], capture_output=True, env=compiler_env(cobc), timeout=10)
            self.assertEqual(native.returncode, 0, native.stderr.decode(errors="replace"))
            self.assertEqual(native.stdout, b"1234567\nCOMPARE:BAD\nEVALUATE:BAD\n")
        # cobc folds the comparison: the literal has more digits than the
        # edited item (compare_field_literal), so it is always FALSE.
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "comparison.cob"
            source.write_text(contents, encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["rust_stdout"], "1234567\nCOMPARE:BAD\nEVALUATE:BAD\n")


if __name__ == "__main__":
    unittest.main()
