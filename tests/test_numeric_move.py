from __future__ import annotations

import hashlib
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
    return ("identification division.\nprogram-id. numeric-move-case.\n"
            "data division. working-storage section.\n" + data +
            "\nprocedure division.\n" + body + "\n")


class NumericMoveTests(unittest.TestCase):
    def test_move_is_distinct_from_arithmetic_assignment(self):
        parsed = Parser(program("01 n pic 999. 01 output-a pic xxx.",
                                "move n to output-a compute n = 1 stop run.")).parse()
        self.assertEqual(parsed.entry[0].op, "move")
        self.assertEqual(parsed.entry[1].op, "assign")

    def test_figurative_zero_is_distinct_from_numeric_literal_zero(self):
        parsed = Parser(program("01 output-a pic xxx.",
                                "move zero to output-a move 0 to output-a "
                                "move zeros to output-a move zeroes to output-a stop run.")).parse()
        sources = [stmt.args[0] for stmt in parsed.entry[:-1]]
        self.assertEqual([source.figurative_zero for source in sources], [True, False, True, True])
        self.assertEqual([source.args[0] for source in sources], ["0"] * 4)

    def test_arithmetic_still_rejects_text_receivers(self):
        for body in ("compute output-a = 1.", "compute output-a rounded = 1.2.",
                     "add 1 to n giving output-a.", "subtract 1 from n giving output-a.",
                     "multiply 2 by n giving output-a.", "divide 2 into n giving output-a."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program("01 n pic 999. 01 output-a pic xxx.", body)).parse()).generate()

    def test_noninteger_fields_reject_elementary_and_reference_modified_receivers(self):
        for receiver in ("output-a", "group-a(1:3)", "output-a(1:3)"):
            for usage in ("", "comp", "comp-3"):
                with self.subTest(receiver=receiver, usage=usage), self.assertRaises(CobolError):
                    Emitter(Parser(program(f"01 n pic s99v99 {usage}. "
                                           "01 output-a pic x(6). 01 group-a. 02 cell-a pic x(6).",
                                           f"move n to {receiver}.")).parse()).generate()

    def test_noninteger_fields_allow_raw_group_receiver(self):
        for usage in ("", "comp", "comp-3"):
            with self.subTest(usage=usage):
                Emitter(Parser(program(f"01 n pic s99v99 {usage}. "
                                       "01 group-a. 02 cell-a pic x(6).",
                                       "move n to group-a.")).parse()).generate()

    def test_unmodelled_sources_remain_rejected(self):
        for body in ("move edited-a to n.",
                     "move edited-a to edited-b.", "move n + 1 to output-a."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program("01 n pic 999. 01 output-a pic xxx. "
                                       "01 edited-a pic +999. 01 edited-b pic +999.", body)).parse()).generate()

    def test_implicit_index_cannot_be_copied_to_raw_group(self):
        with self.assertRaises(CobolError):
            Emitter(Parser(program("01 table-a. 02 item-a pic x occurs 2 indexed by idx. "
                                   "01 group-a. 02 cell-a pic x(8).",
                                   "move idx to group-a.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NumericMoveNativeTests(unittest.TestCase):
    def assert_matches(self, data: str, body: str, expected: str):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "numeric-transfer.cob"
            source.write_text(program(data, body), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertEqual(report["cobol_stdout"], expected, report)
        self.assertEqual(report["rust_stdout"], expected, report)
        self.assertTrue(report["match"], report)

    def test_display_digits_drop_sign_and_preserve_picture_width(self):
        self.assert_matches("01 unsigned-a pic 9(4) value 12. 01 signed-a pic s9(4) value -12. "
                            "01 short-a pic xx. 01 long-a pic x(6). 01 same-a pic x(4).", '''
move unsigned-a to short-a same-a long-a
display "U:[" short-a "][" same-a "][" long-a "]"
move signed-a to short-a same-a long-a
display "S:[" short-a "][" same-a "][" long-a "]"
move 0 to signed-a move signed-a to long-a
display "Z:[" long-a "]"
stop run.
''', "U:[00][0012][0012  ]\nS:[00][0012][0012  ]\nZ:[0000  ]\n")

    def test_binary_packed_and_index_values_use_picture_capacity(self):
        self.assert_matches("01 binary-a pic s9(4) comp value -12. "
                            "01 packed-a pic s9(4) comp-3 value -12. "
                            "01 long-packed pic 9(18) comp-3 value 123456789012345678. "
                            "01 narrow-binary pic s999 comp. "
                            "01 wide-binary redefines narrow-binary pic s9(4) comp. "
                            "01 table-a. 02 item-a pic x occurs 2 indexed by idx. "
                            "01 output-a pic x(20).", '''
move binary-a to output-a display "B:[" output-a "]"
move packed-a to output-a display "P:[" output-a "]"
move long-packed to output-a display "L:[" output-a "]"
move 1234 to wide-binary move narrow-binary to output-a display "CAP:[" output-a "]"
set idx to -12 move idx to output-a display "I:[" output-a "]"
set idx to 1234567890 move idx to output-a display "ICAP:[" output-a "]"
stop run.
''', "B:[0012                ]\nP:[0012                ]\nL:[123456789012345678  ]\n"
            "CAP:[234                 ]\nI:[000000012           ]\nICAP:[234567890           ]\n")

    def test_literal_spelling_and_figurative_zero_have_distinct_padding(self):
        self.assert_matches("01 output-a pic x(7).", '''
move 0012 to output-a display "A:[" output-a "]"
move +0012 to output-a display "B:[" output-a "]"
move -0012 to output-a display "C:[" output-a "]"
move 12.30 to output-a display "D:[" output-a "]"
move -12.30 to output-a display "E:[" output-a "]"
move 0.001 to output-a display "F:[" output-a "]"
move 000.0010 to output-a display "G:[" output-a "]"
move 0 to output-a display "H:[" output-a "]"
move -0 to output-a display "I:[" output-a "]"
move zero to output-a display "J:[" output-a "]"
move zeros to output-a display "K:[" output-a "]"
move zeroes to output-a display "L:[" output-a "]"
stop run.
''', "A:[0012   ]\nB:[0012   ]\nC:[0012   ]\nD:[1230   ]\nE:[1230   ]\nF:[0001   ]\n"
            "G:[0000010]\nH:[0      ]\nI:[0      ]\nJ:[0000000]\nK:[0000000]\nL:[0000000]\n")

    def test_group_receivers_copy_storage_bytes_instead_of_rendering_digits(self):
        self.assert_matches("01 display-a pic s9(4) value -12. "
                            "01 decimal-a pic s9(3)v99 value -12.30. "
                            "01 binary-a pic s9(4) comp value -12. "
                            "01 packed-a pic s9(4) comp-3 value -12. "
                            "01 group-a. 02 first-a pic xx. 02 tail-a pic x(5).", '''
move display-a to group-a display "D:[" group-a "]"
move decimal-a to group-a display "V:[" group-a "]"
move binary-a to group-a display "B:[" group-a "]"
move packed-a to group-a display "P:[" group-a "]"
move 0012 to group-a display "L:[" group-a "]"
move zero to group-a display "Z:[" group-a "]"
stop run.
''', "D:[001r   ]\nV:[0123p  ]\nB:[\\xff\\xf4     ]\nP:[\x00\x01-    ]\nL:[0012   ]\nZ:[0000000]\n")

    def test_reference_modified_receiver_is_an_elementary_text_destination(self):
        self.assert_matches("01 n pic s9(4) value -1234. "
                            "01 group-a. 02 first-a pic xx value 'AB'. "
                            "02 middle-a pic x(6) value 'CDEFGH'. 02 last-a pic x value 'I'.", '''
move n to group-a(3:6)
display "R:[" group-a "]"
stop run.
''', "R:[AB1234  I]\n")

    def test_each_receiver_rereads_the_shared_source_storage(self):
        self.assert_matches("01 unsigned-a pic 9(4) value 1234. "
                            "01 raw-u redefines unsigned-a pic x(4). "
                            "01 signed-a pic s9(4) value -1234. "
                            "01 raw-s redefines signed-a pic x(4). "
                            "01 output-a pic x(8).", '''
move unsigned-a to raw-u(2:2) output-a
display "U:[" raw-u "][" output-a "]"
move signed-a to raw-s(2:2) output-a
display "S:[" raw-s "][" output-a "]"
stop run.
''', "U:[1124][1124    ]\nS:[112t][1124    ]\n")

    def test_source_subscript_address_is_resolved_once(self):
        self.assert_matches("01 chosen pic 9 value 1. 01 table-a. "
                            "02 cell-a pic 9 occurs 2. 01 output-a pic x(3).", '''
move 2 to cell-a(1) move 9 to cell-a(2)
move cell-a(chosen) to chosen output-a
display "A:[" chosen "][" output-a "]"
stop run.
''', "A:[2][2  ]\n")

    def test_unsigned_display_does_not_parse_digits_before_copying_to_text(self):
        self.assert_matches("01 source-a pic 9(4). 01 raw-a redefines source-a pic x(4). "
                            "01 output-a pic x(6).", '''
move "12A3" to raw-a move source-a to output-a
display "U:[" output-a "][" raw-a "]"
stop run.
''', "U:[12A3  ][12A3]\n")

    def test_report_fixture_has_independently_expected_file_bytes(self):
        report = verify(ROOT / "tests" / "fixtures" / "numeric_move_report.cob", fmt="free")
        expected = b"007/000|000\n0  |0012  |1230\n"
        file_info = {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()}
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"],
                         "COUNTS:[007/000|000]\nLITERALS:[0  |0012  |1230  ]\n"
                         "TEXT:[012  ]RAW:[01r  ]\n")
        self.assertEqual(report["rust_stdout"], report["cobol_stdout"])
        self.assertEqual(report["cobol_files"], {"numeric-report.txt": file_info})
        self.assertEqual(report["rust_files"], {"numeric-report.txt": file_info})

    def test_invalid_signed_display_source_stops_with_named_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "invalid-numeric.cob"
            source.write_text(program("01 source-a pic s9(4). "
                                      "01 raw-a redefines source-a pic x(4). 01 output-a pic x(6).",
                                      'move "ABCD" to raw-a move source-a to output-a stop run.'),
                              encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            result = subprocess.run([str(binary)], capture_output=True,
                                    env=compiler_env(find_tool("cargo")), timeout=10)
        self.assertEqual(result.returncode, 70)
        self.assertIn("invalid", result.stderr.decode(errors="replace").lower())


if __name__ == "__main__":
    unittest.main()
