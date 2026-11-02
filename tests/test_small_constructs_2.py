from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(data, body):
    return ("identification division.\nprogram-id. small2.\ndata division.\nworking-storage section.\n"
            f"01 x pic x(16).\n01 n pic 9.\n{data}procedure division.\n{body}\nstop run.\n")


def in_cobol85(function):
    previous, frontend.STD = frontend.STD, "cobol85"
    try:
        return function()
    finally:
        frontend.STD = previous


class SmallConstructTests(unittest.TestCase):
    def test_cobol85_refusals(self):
        # stop-identifier-statement: unconformable; MICROSECOND-TIME and the
        # WHEN-COMPILED register are no cobol85 words.
        for body in ("stop n.", "accept x from microsecond-time.", "move when-compiled to x."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                in_cobol85(lambda: Parser(program("", body.replace("stop run", ""))).parse())

    def test_homonymous_conditions_are_ambiguous_when_used(self):
        data = "01 c pic x.\n  88 a value 'A'.\n  88 a value 'B'.\n"
        Parser(program(data, "display c.")).parse()
        with self.assertRaisesRegex(CobolError, "ambigu"):
            Parser(program(data, "set a to true.")).parse()

    def test_partial_evaluate_object_rejects_thru(self):
        with self.assertRaisesRegex(CobolError, "invalid THROUGH usage"):
            Parser(program("", "evaluate n when > 1 thru 5 continue end-evaluate.")).parse()

    def test_same_as_an_ancestor_is_refused(self):
        # The item itself or one of its parents only (cobc's p->parent loop).
        with self.assertRaisesRegex(CobolError, "may not reference itself"):
            Parser(program("01 g.\n  02 h same as g.\n", "goback.")).parse()
        Parser(program("01 g.\n  02 a pic x(3).\n  02 b same as a.\n", "goback.")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SmallConstructNativeTests(unittest.TestCase):
    def test_fixtures_match_gnucobol(self):
        for name, stdin in [("small_constructs_2.cob", b"\n"), ("read_handler_class.cob", b""),
                            ("value_literals.cob", b""), ("sort_qualified_procedures.cob", b"")]:
            with self.subTest(fixture=name):
                report = verify(FIXTURES / name, fmt="fixed", stdin=stdin)
                self.assertTrue(report["match"], report)
        report = verify(FIXTURES / "small_constructs_2.cob", fmt="fixed", stdin=b"\n")
        self.assertIn("+0007 not < 4\n+0010 >= 10\n", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
