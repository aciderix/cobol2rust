"""libcob behaviours seen by real programs: NaN after a division by zero,
cob_fatal_error and cob_call_error, exit-time warnings, LINE SEQUENTIAL
validation and splitting, literals as source bytes, invalid numeric data
read without runtime checks."""
from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import Parser
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

    def test_invalid_numeric_data_without_runtime_checks(self):
        # COB_D2I digits, X"FF"/X"00" first bytes as decimals, the comparison
        # routine cobc picks, byte copies of cb_build_move_field, DISPLAY as
        # stored and SORT keys through cob_numeric_cmp.
        for name in ("invalid_numeric_data", "invalid_numeric_compare", "invalid_numeric_move"):
            with self.subTest(name=name):
                report = verify(FIXTURES / f"{name}.cob", fmt="free")
                self.assertTrue(report["match"], report)


class ComparisonEmissionTests(unittest.TestCase):
    def test_debugging_mode_bypasses_the_inline_comparisons(self):
        # cb_build_cond_default: WITH DEBUGGING MODE calls cob_cmp.
        source = ("identification division. program-id. cmp.\n"
                  "environment division. configuration section. source-computer. x{mode}.\n"
                  "data division. working-storage section. 01 a pic 9(4). 01 b pic 9(4).\n"
                  "procedure division. if a = b display 'same' end-if stop run.")
        fast = Emitter(Parser(source.format(mode="")).parse()).generate()[0]
        debug = Emitter(Parser(source.format(mode=" with debugging mode")).parse()).generate()[0]
        self.assertIn("runtime::memcmp", fast)
        self.assertNotIn("runtime::memcmp", debug)
        self.assertIn("operand_integer()", debug)


if __name__ == "__main__":
    unittest.main()
