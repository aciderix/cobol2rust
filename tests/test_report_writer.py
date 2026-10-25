from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.report_parser import DETAIL, LINE, LINE_PLUS, PAGE_HEADING
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_nested_programs import unit


def program(rd, groups, procedure="stop run.", fd="report is r", working=""):
    return ("identification division.\nprogram-id. rw.\nenvironment division.\ninput-output section.\n"
            'file-control.\n    select out-file assign to "OUT.TXT".\ndata division.\nfile section.\n'
            f"fd out-file {fd}.\nworking-storage section.\n01 w pic x(4) value \"ABCD\".\n01 n pic 99.\n"
            f"{working}\nreport section.\nrd r {rd}.\n{groups}\nprocedure division.\n{procedure}\n")


DETAIL_GROUP = "01 d type detail line plus 1.\n    03 column 3 pic x(4) source w.\n    03 column 9 pic x(2) value \"OK\"."


class ReportParseTests(unittest.TestCase):
    def test_page_limit_defaults_follow_the_page_clause(self):
        report = Parser(program("page limit is 20 lines", DETAIL_GROUP)).parse().reports["R"]
        self.assertEqual((report.lines, report.heading, report.first_detail, report.last_detail, report.footing),
                         (20, 1, 1, 20, 20))
        report = Parser(program("page 30 heading 2 first detail 6 footing 28", DETAIL_GROUP)).parse().reports["R"]
        self.assertEqual((report.first_detail, report.last_detail, report.footing), (6, 28, 28))

    def test_lines_fields_and_record_size(self):
        groups = ("01 type page heading line 1.\n    03 column 70 pic 9 source page-counter.\n"
                  "01 g type de.\n    03 line plus 2.\n        05 column 5 pic x(6) value \"FIRST \".\n"
                  "    03 line plus 1 column 7 pic x(4) source w.\n" + DETAIL_GROUP)
        parsed = Parser(program("page 20", groups)).parse()
        report = parsed.reports["R"]
        heading, group, first, second, detail = report.report_lines
        self.assertEqual((heading.flags, heading.line, heading.sister), (PAGE_HEADING | LINE, 1, 1))
        self.assertEqual((group.flags, group.fields, group.child, group.sister), (DETAIL, [], 2, 4))
        self.assertEqual((first.flags, first.line, first.sister, second.sister), (LINE | LINE_PLUS, 2, 3, None))
        self.assertEqual([f.column for f in detail.fields], [3, 9])
        self.assertEqual(detail.fields[1].literal, b"OK")
        self.assertEqual(report.groups, {"G": 1, "D": 4})
        # rcsz: column 70 of the heading item.
        self.assertEqual(report.size, 70)
        spec = parsed.files["OUT-FILE"]
        self.assertEqual((spec.organization, spec.record_min, spec.record_max), ("LINE SEQUENTIAL", 70, 70))

    def test_counters_and_statements(self):
        procedure = ("initiate r. generate d. generate r. move line-counter to n. "
                     "display page-counter of r. terminate r.")
        entry = Parser(program("page 20", DETAIL_GROUP, procedure)).parse().entry
        self.assertEqual([s.op for s in entry if s.op != "sentence_end"][:3], ["initiate", "generate", "generate"])
        generates = [s for s in entry if s.op == "generate"]
        self.assertEqual([s.args for s in generates], [("R", 0), ("R", None)])

    def test_unmodelled_forms_are_refused(self):
        cases = [
            program("controls are w page 20", DETAIL_GROUP),
            program("page 20", DETAIL_GROUP.replace("source w", "sum n")),
            program("page 20", DETAIL_GROUP.replace('pic x(2) value "OK"', 'pic 9(2) value "12"')),
            program("page 20", DETAIL_GROUP.replace("column 9", "column plus 2")),
            program("page 20", DETAIL_GROUP.replace("type detail", "type control heading w")),
            program("page 20", DETAIL_GROUP.replace("line plus 1", "line next page")),
            program("page 20", DETAIL_GROUP.replace("source w", "source w group indicate")),
            program("page 20", DETAIL_GROUP.replace("line plus 1", "line 21")),
            program("page 20 heading 5 first detail 3", DETAIL_GROUP),
            program("page 20 last detail 10 footing 8", DETAIL_GROUP),
            # Without PAGE, a field's LINE exceeds the limit 0 at INITIATE
            # (cob_report_initiate does not guard rf->line with def_lines > 0).
            program("", "01 d type detail.\n    03 line 1 column 3 pic x(4) source w.").replace("rd r .", "rd r."),
            program("page 20", DETAIL_GROUP, "write out-file."),
            program("page 20", DETAIL_GROUP, "read out-file."),
            program("page 20", DETAIL_GROUP, fd="report is r q"),
            program("page 20", DETAIL_GROUP, "move line-counter to w."),
            program("page 20", DETAIL_GROUP.replace("column 3 pic x(4) source w", "column 3 pic x(4)")),
        ]
        for text in cases:
            with self.subTest(text=text[text.index("rd "):text.index("rd ") + 140]), self.assertRaises(CobolError):
                unit(text)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ReportNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "report_writer.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertTrue(report["files_match"], report)
        self.assertIn("03 line 10 page 0000000001\n", report["cobol_stdout"])
        self.assertEqual(report["cobol_files"]["SUMMARY.TXT"]["bytes"], 77)

    def test_report_without_page_clause(self):
        # Limits 0 with FIRST DETAIL 1: every line passes LAST DETAIL 0, so
        # reportio.c changes page before each one.
        report = verify(ROOT / "tests" / "fixtures" / "report_no_page.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertTrue(report["files_match"], report)
        self.assertEqual(report["cobol_stdout"], "line 0000000000 page 0000000007\n")


if __name__ == "__main__":
    unittest.main()
