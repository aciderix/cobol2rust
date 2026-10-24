from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def source(selects: str, fds: str, body: str, special: str = "") -> str:
    return ("identification division.\nprogram-id. linage-test.\nenvironment division.\n"
            "configuration section.\nspecial-names.\n" + (special or "    console is screen") + ".\n"
            "input-output section.\nfile-control.\n" + selects + "\ndata division.\nfile section.\n"
            + fds + "\nworking-storage section.\n01 n pic 99.\nprocedure division.\n" + body + "\nstop run.\n")


PAGED = ('    select paged assign to "P.TXT".', "fd paged linage 10 footing 8 top 1.\n01 paged-line pic x(10).")


class LinageTests(unittest.TestCase):
    def test_linage_clause_makes_the_file_line_sequential(self):
        parsed = Parser(source(*PAGED, "open output paged. close paged.")).parse()
        spec = parsed.files["PAGED"]
        self.assertEqual(spec.organization, "LINE SEQUENTIAL")
        self.assertEqual(spec.linage, {"lines": ("literal", 10), "footing": ("literal", 8), "top": ("literal", 1)})

    def test_linage_phrases_accept_data_names_and_the_scanner_forms(self):
        fds = ("fd paged linage is n lines with footing at n lines at top 2 bottom n.\n"
               "01 paged-line pic x(10).")
        spec = Parser(source(PAGED[0], fds, "open output paged.")).parse().files["PAGED"]
        self.assertEqual(spec.linage["lines"], ("field", "N"))
        self.assertEqual(spec.linage["bottom"], ("field", "N"))
        self.assertEqual(spec.linage["top"], ("literal", 2))

    def test_cobc_errors_are_refused(self):
        relative = ('    select paged assign to "P.TXT" organization relative.',
                    "fd paged linage 10.\n01 paged-line pic x(10).")
        two = (PAGED[0] + '\n    select other assign to "O.TXT".',
               PAGED[1] + "\nfd other linage 5.\n01 other-line pic x(10).")
        plain = (PAGED[0], "fd paged.\n01 paged-line pic x(10).")
        cases = [
            (relative, "open output paged."),
            (plain, "move linage-counter to n."),
            (two, "move linage-counter to n."),
            (PAGED, "write paged-line after advancing screen."),
            (PAGED, "write paged-line after advancing -1 lines."),
            (PAGED, "write paged-line invalid key display 'x'."),
            (PAGED, "write paged-line at end-of-page continue at eop continue."),
        ]
        for (selects, fds), body in cases:
            with self.subTest(body=body, fds=fds), self.assertRaises(CobolError):
                Emitter(Parser(source(selects, fds, body)).parse()).generate()

    def test_linage_counter_is_read_only_in_the_profile(self):
        with self.assertRaises(CobolError):
            Emitter(Parser(source(*PAGED, "move 3 to linage-counter.")).parse()).generate()
        rust = Emitter(Parser(source(*PAGED, "move linage-counter of paged to n. display linage-counter.")).parse()).generate()[0]
        self.assertIn("linage_counter()", rust)
        self.assertIn("linage_display()", rust)

    def test_end_of_page_bodies_end_at_an_enclosing_terminator(self):
        body = ("perform 3 times write paged-line at eop display 'e' "
                "not at end-of-page display 'n' end-perform.")
        Emitter(Parser(source(*PAGED, body)).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class LinageNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "linage.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertTrue(report["files_match"], report)
        self.assertEqual(sorted(report["cobol_files"]), ["PAGED.TXT", "PLAIN.TXT", "SIZED.TXT"])
        self.assertIn("eop 04 0000000005\n", report["cobol_stdout"])
        self.assertIn("sized 57 0000000000\n", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
