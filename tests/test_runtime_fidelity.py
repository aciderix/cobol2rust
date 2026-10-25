"""libcob behaviours seen by real programs: NaN after a division by zero,
cob_fatal_error and cob_call_error, exit-time warnings, LINE SEQUENTIAL
validation and splitting, literals as source bytes."""
from __future__ import annotations

import unittest

from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NativeTests(unittest.TestCase):
    def test_division_by_zero_leaves_the_receiver(self):
        report = verify(FIXTURES / "divide_by_zero.cob", fmt="free")
        self.assertTrue(report["match"], report)

    def test_fatal_file_error_and_implicit_close_warnings(self):
        report = verify(FIXTURES / "file_exit_messages.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_exit"], 1)
        self.assertTrue(report["stderr_match"])
        self.assertIn("implicit CLOSE of Second-Out ('dd-name')", report["rust_stderr"])

    def test_call_of_a_missing_module(self):
        for name, module in (("call_not_found", "CEE3ABD"), ("call_not_found_dynamic", "DYNPROG")):
            with self.subTest(name=name):
                report = verify(FIXTURES / f"{name}.cob", fmt="free")
                self.assertTrue(report["match"], report)
                self.assertIn(f"module '{module}' not found", report["rust_stderr"])

    def test_line_sequential_read_and_write_validation(self):
        report = verify(FIXTURES / "line_sequential_split.cob", fmt="free",
                        data_dir=FIXTURES / "line_sequential_split.data")
        self.assertTrue(report["match"], report)
        report = verify(FIXTURES / "line_sequential_bad_char.cob", fmt="free")
        self.assertTrue(report["match"], report)

    def test_non_ascii_and_hexadecimal_literals_are_bytes(self):
        for name in ("non_ascii_literals", "literal_concatenation"):
            with self.subTest(name=name):
                report = verify(FIXTURES / f"{name}.cob", fmt="free")
                self.assertTrue(report["match"], report)


if __name__ == "__main__":
    unittest.main()
