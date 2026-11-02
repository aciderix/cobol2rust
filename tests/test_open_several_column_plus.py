from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def report(items):
    return ("identification division.\nprogram-id. plus-case.\nenvironment division.\ninput-output section.\n"
            "file-control.\nselect f assign 'r.txt' organization line sequential.\ndata division.\nfile section.\n"
            "fd f report is r.\nreport section.\nrd r page limit 10.\n01 d type detail.\n 05 line plus 1.\n"
            f"{items}\nprocedure division.\nstop run.\n")


class ColumnPlusTests(unittest.TestCase):
    def test_columns_follow_output_report_data(self):
        items = ("  10 col plus 4 pic x(3) value 'A'.\n  10 col plus 2 pic x value 'B'.\n"
                 "  10 pic x value 'C'.\n  10 col plus 0 pic x value 'D'.\n  10 col 20 pic x value 'E'.\n")
        spec = Parser(report(items)).parse().reports["R"]
        fields = spec.report_lines[1].fields if len(spec.report_lines) > 1 else spec.report_lines[0].fields
        # PLUS on the first item of a LINE is ignored (col_or_plus): column 4.
        self.assertEqual([f.column for f in fields], [4, 8, 9, 10, 20])

    def test_plus_with_alignment_stays_refused(self):
        with self.assertRaises(CobolError):
            Parser(report("  10 col right plus 2 pic x value 'A'.\n")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NativeTests(unittest.TestCase):
    def test_open_of_several_files_checks_after_every_open(self):
        # open_file_entry: the checks follow all cob_open calls, last file
        # first, each testing the cob_exception_code left by the last one.
        report_ = verify(ROOT / "tests" / "fixtures" / "open_several.cob", fmt="free")
        self.assertTrue(report_["match"], report_)
        self.assertEqual(report_["cobol_stdout"], "use c\n")
        self.assertEqual(report_["cobol_exit"], 1)

    def test_open_entries_nest_their_checks(self):
        # The entries after the first are children of the last file of the
        # previous one: OPEN OUTPUT b INPUT a c checks a, c, then b.
        report_ = verify(ROOT / "tests" / "fixtures" / "open_entries.cob", fmt="free")
        self.assertTrue(report_["match"], report_)
        self.assertEqual(report_["cobol_exit"], 1)

    def test_column_plus_and_report_errors_match_native(self):
        report_ = verify(ROOT / "tests" / "fixtures" / "report_column_plus.cob", fmt="free")
        self.assertTrue(report_["match"], report_)
        # cob_report_initiate: a second INITIATE is an error message only.
        self.assertEqual(report_["cobol_stderr"], "libcob: error: INITIATE plus-report was already done\n")


if __name__ == "__main__":
    unittest.main()
