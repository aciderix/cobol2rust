from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, compiler_env, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


def generate(data: str, body: str) -> str:
    code, _ = Emitter(Parser(program(data, body)).parse()).generate()
    return code


class NumericTruncationTests(unittest.TestCase):
    def test_numeric_move_truncates_but_arithmetic_keeps_its_stop(self):
        code = generate("01 wide pic 9(4) value 1000. 01 narrow pic 999.",
                        "move wide to narrow compute narrow = wide stop run.")
        self.assertIn("move_number(", code)
        self.assertIn(".assign(", code)

    def test_index_sender_keeps_the_strict_assignment(self):
        code = generate("01 table-a. 02 item-a pic x occurs 2 indexed by idx. 01 narrow pic 9.",
                        "move idx to narrow stop run.")
        self.assertNotIn("move_number(", code.split("struct Program", 1)[1])

    def test_binary_sender_to_packed_uses_the_guarded_native_path(self):
        code = generate("01 b pic s9(4) comp. 01 p pic 99 comp-3. 01 d pic 99.",
                        "move b to p d stop run.")
        self.assertIn("move_binary_to_packed(", code)
        self.assertIn("move_number(", code)

    def test_integer_literal_filling_the_packed_pad_nibble_is_refused(self):
        data = "01 p2 pic 99 comp-3. 01 p3 pic s999 comp-3. 01 v2 pic s9v9 comp-3."
        for body in ("move 1234 to p2.", "move -100 to p2.", "move 1034 to v2.", "move 12 to v2."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                generate(data, body + " stop run.")
        # Odd digits, a zero pad digit, decimal literals and literals beyond nine
        # positions follow cob_move, whose truncation is modelled.
        for body in ("move 1234 to p3.", "move 1004 to p2.", "move 1004 to v2.",
                     "move 12.34 to p2.", "move 1234567890 to p2.", "move zero to p2."):
            with self.subTest(body=body):
                generate(data, body + " stop run.")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NumericTruncationNativeTests(unittest.TestCase):
    def test_fixture_matches_native_bytes(self):
        report = verify(ROOT / "tests" / "fixtures" / "numeric_truncation.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["rust_stdout"], report["cobol_stdout"])
        # Native negative zeros: "00p" in DISPLAY and a D sign nibble in COMP-3.
        self.assertIn("S4Z   00000p\x00", report["cobol_stdout"])
        self.assertIn("+000 +000 +0.0\n", report["cobol_stdout"])
        self.assertIn("-45 45 -2345\n", report["cobol_stdout"])
        self.assertIn("ZB    00p\x00\r\x00\r\x000p\n", report["cobol_stdout"])
        self.assertIn("ZD    00p\x00\r\x00\r\x000u\n", report["cobol_stdout"])

    def test_binary_sender_filling_the_pad_nibble_stops_with_named_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "pad-nibble.cob"
            source.write_text(program("01 b pic s9(4) comp value 1234. 01 p pic 99 comp-3.",
                                      'move b to p display "AFTER" stop run.'), encoding="utf-8")
            convert(source, root / "rust")
            binary = build_rust(root / "rust")
            result = subprocess.run([str(binary)], capture_output=True,
                                    env=compiler_env(find_tool("cargo")), timeout=10)
        self.assertEqual(result.returncode, 70)
        self.assertEqual(result.stdout, b"")
        self.assertIn("pad nibble", result.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main()
