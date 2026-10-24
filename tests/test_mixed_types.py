from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, compiler_env, find_tool
from cobol2rust.verification import verify


def program(data: str, body: str = "stop run.") -> str:
    return ("identification division.\nprogram-id. mixed-type-case.\n"
            "data division. working-storage section.\n" + data +
            "\nprocedure division.\n" + body + "\n")


def relations(left: str, right: str) -> str:
    """Print the six relations in both orders, without deriving expectations."""
    result = []
    for first, second in ((left, right), (right, left)):
        for op in ("=", "<>", "<", ">", "<=", ">="):
            result.append(f'if {first} {op} {second} display "1" with no advancing '
                          'else display "0" with no advancing end-if')
        result.append('display "|" with no advancing')
    result.append('display "END"')
    return "\n".join(result) + "\n"


class MixedTypeTests(unittest.TestCase):
    def emit(self, data: str, body: str):
        return Emitter(Parser(program(data, body)).parse()).generate()

    def test_mixed_index_signed_literals_and_arithmetic_are_rejected(self):
        data = ("01 n pic 999. 01 t pic xxx. "
                "01 table-a. 02 cell-a pic x occurs 2 indexed by idx.")
        for condition in ("idx = t", "t = idx", "+12 = t", "t = -12",
                          "n + 1 = t", "t = n * 2"):
            with self.subTest(condition=condition), self.assertRaises(CobolError):
                self.emit(data, f"if {condition} continue end-if.")

    def test_evaluate_uses_the_comparison_profile(self):
        # cb_emit_evaluate builds the same comparisons as IF.
        data = "01 n pic 99. 01 t pic xx. 01 w pic 999."
        for body in ('evaluate n when "12" continue end-evaluate.',
                     "evaluate t when 12 continue end-evaluate.",
                     "evaluate t when zero continue end-evaluate."):
            with self.subTest(body=body):
                self.emit(data, body)
        with self.assertRaises(CobolError):
            self.emit(data, 'evaluate w when "12" continue end-evaluate.')

    def test_direct_text_literals_with_unmodelled_native_optimizations_are_rejected(self):
        # n = "1230" with PIC S99V99 is folded by cobc (comparison_folding.cob).
        for data, condition in (("01 n pic 999.", 'n = "12"'),
                                ("01 n pic 999.", '"0012" = n'),
                                ("01 n pic 999.", 'n = "12A"')):
            with self.subTest(data=data, condition=condition), self.assertRaises(CobolError):
                self.emit(data, f"if {condition} continue end-if.")

    def test_mixed_condition_values_and_direct_edited_comparisons_are_rejected(self):
        for data in ('01 n pic 99. 88 chosen value "12".',
                     '01 t pic xx. 88 chosen value 12.'):
            with self.subTest(data=data), self.assertRaises(CobolError):
                self.emit(data, "if chosen continue end-if.")
        # Edited items compare as alphanumeric (comparison_folding.cob).
        for condition in ('edited-a = "12"', "edited-a = 12"):
            with self.subTest(condition=condition):
                self.emit("01 edited-a pic +99.", f"if {condition} continue end-if.")

    def test_text_literals_to_numeric_and_index_receivers_remain_rejected(self):
        data = ("01 n pic s99v99. 01 t pic x(6). "
                "01 table-a. 02 cell-a pic x occurs 2 indexed by idx.")
        for body in ("move spaces to n.", "move t to idx."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                self.emit(data, body)

    def test_text_literal_to_display_number_follows_cb_build_move_literal(self):
        # Same scale: bytes copied at compile time; else cob_move at run time.
        rust = self.emit("01 n pic 9(4). 01 s pic s99v99. 01 b pic 99 comp.", 'move "12" to n. move "1.5" to s.')[0]
        self.assertIn("vec![48, 48, 49, 50]), true)", rust)
        self.assertIn("assign_text_move(", rust)
        with self.assertRaises(CobolError):
            self.emit("01 b pic 99 comp.", 'move "12" to b.')

    def test_deediting_and_arithmetic_are_not_promoted_by_text_move(self):
        data = "01 n pic 999. 01 t pic xxx. 01 edited-a pic +999."
        for body in (
                     "compute n = t + 1.", "compute t = 1.",
                     "add t to n.", "move spaces to edited-a."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                self.emit(data, body)

    def test_numeric_value_initialization_still_rejects_text_literals(self):
        for picture in ("999", "s999 comp", "s999 comp-3"):
            with self.subTest(picture=picture), self.assertRaises(CobolError):
                Parser(program(f'01 n pic {picture} value "123".')).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class MixedTypeNativeTests(unittest.TestCase):
    def assert_matches(self, data: str, body: str, expected: str):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "mixed-source.cob"
            source.write_text(program(data, body), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], expected, report)
        self.assertEqual(report["rust_stdout"], expected, report)

    def test_all_relations_keep_numeric_picture_width_and_text_padding(self):
        self.assert_matches("01 n pic 999 value 12. 01 t pic xx value '12'.",
                            relations("n", "t") + "stop run.",
                            "011010|010101|END\n")

    def test_signed_scaled_binary_and_packed_fields_compare_their_magnitude_digits(self):
        data = ("01 d pic s999v99 value -12.34. "
                "01 b pic s999v99 comp value -12.34. "
                "01 p pic s999v99 comp-3 value -12.34. "
                "01 t pic x(6) value '01234 '. 01 equal-t pic x(5) value '01234'. "
                "01 next-t pic x(5) value '01235'.")
        self.assert_matches(data, relations("d", "t") + relations("b", "equal-t") +
                            relations("p", "next-t") + "stop run.",
                            "100011|100011|END\n100011|100011|END\n011010|010101|END\n")

    def test_group_refmod_and_binary_alias_comparison_use_the_same_digit_rule(self):
        data = ("01 n pic 999 value 12. 01 g. 02 txt pic xxx value '012'. "
                "01 surrounded pic x(5) value 'X012Y'. "
                "01 small-b pic 999 comp. 01 large-b redefines small-b pic 9(4) comp.")
        body = relations("n", "g") + relations("n", "surrounded(2:3)")
        body += 'move 1234 to large-b\n' + relations("small-b", '"234"') + "stop run."
        self.assert_matches(data, body, "100011|100011|END\n" * 3)

    def test_unsigned_numeric_literals_preserve_spelling_and_zero_repeats(self):
        data = "01 a pic x(4) value '0012'. 01 b pic x(4) value '1230'. 01 z pic xx value '00'."
        body = (relations("0012", "a") + relations("12.30", "b") +
                relations("zero", "z") + relations("0", "z") +
                'if zero = "" display "EMPTY:YES" else display "EMPTY:NO" end-if stop run.')
        self.assert_matches(data, body, "100011|100011|END\n" * 3 + "011010|010101|END\nEMPTY:NO\n")

    def test_unsigned_display_invalid_bytes_are_compared_without_numeric_decoding(self):
        data = "01 n pic 999. 01 raw-n redefines n pic xxx. 01 t pic xxx value '12A'."
        self.assert_matches(data, 'move "12A" to raw-n\n' + relations("n", "t") + "stop run.",
                            "100011|100011|END\n")

    def test_text_fields_parse_sign_scale_overflow_and_invalid_letters(self):
        data = ("01 source-a pic x(8). 01 d pic s9(4). 01 dec-d pic s99v99. "
                "01 b pic s9(4) comp. 01 p pic s9(4) comp-3. 01 e pic -99.99.")
        body = []
        for label, value in (("A", "-12.30"), ("B", "12A3"), ("C", "12345"), ("D", "  +12.3")):
            body.append(f'move "{value}" to source-a\nmove source-a to d dec-d b p e\n'
                        f'display "{label}:[" d "][" dec-d "][" b "][" p "][" e "]"')
        self.assert_matches(data, "\n".join(body) + "\nstop run.",
                            "A:[-0012][-12.30][-0012][-0012][-12.30]\n"
                            "B:[+0000][+00.00][+0000][+0000][ 00.00]\n"
                            "C:[+2345][+45.00][+2345][+2345][ 45.00]\n"
                            "D:[+0012][+12.30][+0012][+0012][ 12.30]\n")

    def test_display_receiver_capacity_can_stop_validation_before_other_usages(self):
        data = ("01 source-a pic x(5). 01 d pic s9(4). 01 b pic s9(4) comp. "
                "01 p pic s9(4) comp-3. 01 e pic -9(4).")
        self.assert_matches(data, '''
move "123-" to source-a move source-a to d b p e
display "A:[" d "][" b "][" p "][" e "]"
move "1.2.3" to source-a move source-a to d b p e
display "B:[" d "][" b "][" p "][" e "]"
stop run.
''', "A:[+0123][+0000][+0000][ 0000]\nB:[+0001][+0000][+0000][ 0000]\n")

    def test_group_source_copies_raw_storage_while_reference_modification_parses(self):
        data = ("01 source-group. 02 text-a pic x(4) value '12.3'. "
                "01 d pic 9(4). 01 raw-d redefines d pic x(4). "
                "01 b pic 9(4) comp. 01 raw-b redefines b pic xx. "
                "01 p pic 9(4) comp-3. 01 raw-p redefines p pic xxx. "
                "01 e pic -9(4).")
        self.assert_matches(data, '''
move source-group to d b p e
display "RAW:[" raw-d "][" raw-b "][" raw-p "][" e "]"
move source-group(1:4) to d b p e
display "REF:[" d "][" b "][" p "][" e "]"
stop run.
''', "RAW:[12.3][12][12.][12.3 ]\nREF:[0012][0012][0012][ 0012]\n")

    def test_text_and_literal_moves_to_edited_preserve_their_numeric_conversion(self):
        data = "01 source-a pic x. 01 e pic -9(18). 01 small-e pic -9(4)."
        self.assert_matches(data, '''
move spaces to source-a move source-a to e display "S:[" e "]"
move "A" to source-a move source-a to e display "A:[" e "]"
move "9" to source-a move source-a to e display "N:[" e "]"
move "-12.30" to small-e display "L:[" small-e "]"
move "123-" to small-e display "T:[" small-e "]"
move " " to small-e display "Z:[" small-e "]"
stop run.
''', "S:[ 000000000000000000]\nA:[ 000000000000000000]\nN:[ 000000000000000009]\n"
            "L:[-0012]\nT:[ 0000]\nZ:[ 0000]\n")

    def test_each_receiver_rereads_the_text_source_after_overlapping_assignment(self):
        data = ("01 source-a pic x(4) value '1234'. "
                "01 first-a redefines source-a pic 99. 01 final-a pic 9(4).")
        self.assert_matches(data, '''
move source-a to first-a final-a
display "A:[" source-a "][" first-a "][" final-a "]"
stop run.
''', "A:[3434][34][3434]\n")

    def test_text_source_address_is_resolved_once_before_receivers_change_its_index(self):
        data = ("01 chosen pic 9 value 1. 01 table-a. 02 cell-a pic x occurs 2. "
                "01 final-a pic 99.")
        self.assert_matches(data, '''
move "2" to cell-a(1) move "9" to cell-a(2)
move cell-a(chosen) to chosen final-a
display "I:[" chosen "][" final-a "]"
stop run.
''', "I:[2][02]\n")

    def test_negative_zero_sign_storage_is_preserved_for_display_and_packed(self):
        data = ("01 source-a pic x(8). 01 d pic s9(4). 01 raw-d redefines d pic x(4). "
                "01 p pic s9(4) comp-3. 01 raw-p redefines p pic xxx. "
                "01 e pic -9(4).")
        body = []
        for label, value in (("Z", "-0"), ("F", "-0.0001"), ("X", "-x")):
            body.append(f'move "{value}" to source-a move source-a to d p e\n'
                        f'display "{label}:[" d "][" raw-d "][" p "][" raw-p "][" e "]"')
        self.assert_matches(data, "\n".join(body) + "\nstop run.",
                            "Z:[+0000][000p][+0000][\x00\x00\r][ 0000]\n"
                            "F:[+0000][000p][+0000][\x00\x00\r][ 0000]\n"
                            "X:[+0000][000p][+0000][\x00\x00\x0c][ 0000]\n")

    def test_fixture_has_independently_expected_stdout_and_file_bytes(self):
        report = verify(ROOT / "tests" / "fixtures" / "mixed_types.cob", fmt="free")
        expected = b"MATCH\n-12.30\n"
        file_info = {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()}
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "MIXED:[MATCH][-12.30][-12.30]\n")
        self.assertEqual(report["rust_stdout"], report["cobol_stdout"])
        self.assertEqual(report["cobol_files"], {"mixed-report.txt": file_info})
        self.assertEqual(report["rust_files"], {"mixed-report.txt": file_info})

    def test_invalid_signed_display_mixed_comparison_stops_with_named_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "invalid-mixed.cob"
            source.write_text(program("01 n pic s999. 01 raw-n redefines n pic xxx. "
                                      "01 t pic xxx value 'AB1'.",
                                      'move "ABq" to raw-n if n = t continue end-if stop run.'),
                              encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            result = subprocess.run([str(binary)], capture_output=True,
                                    env=compiler_env(find_tool("cargo")), timeout=10)
        self.assertEqual(result.returncode, 70)
        self.assertIn("invalid", result.stderr.decode(errors="replace").lower())


@unittest.skipUnless(find_tool("cobc"), "GnuCOBOL required")
class MixedComparisonOptimizationNativeTests(unittest.TestCase):
    def test_scaled_field_literal_can_be_folded_unlike_the_same_text_in_storage(self):
        source_text = program("01 source-a pic x(8) value '-12.30'. "
                              "01 n pic s99v99. 01 t pic x(4) value '1230'.", '''
move source-a to n
if n = "1230" display "DIRECT:TRUE" else display "DIRECT:FALSE" end-if
if n = t display "FIELD:TRUE" else display "FIELD:FALSE" end-if
stop run.
''')
        cobc = find_tool("cobc")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "literal-optimization.cob"
            binary = root / ("original.exe" if os.name == "nt" else "original")
            source.write_text(source_text, encoding="utf-8")
            compiled = subprocess.run([cobc, "-free", "-x", str(source), "-o", str(binary)],
                                      env=compiler_env(cobc), capture_output=True, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr.decode(errors="replace"))
            result = subprocess.run([str(binary)], cwd=root, env=compiler_env(cobc),
                                    capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stdout, b"DIRECT:FALSE\nFIELD:TRUE\n")
        # The direct comparison is folded like cobc's compare_field_literal.
        if find_tool("cargo"):
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "literal-optimization.cob"
                source.write_text(source_text, encoding="utf-8")
                report = verify(source, fmt="free")
            self.assertTrue(report["match"], report)


if __name__ == "__main__":
    unittest.main()
