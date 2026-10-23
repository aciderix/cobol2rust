from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class DataClauseTests(unittest.TestCase):
    def test_sign_clause_storage(self):
        fields = Parser(program("01 a pic s9(3) sign leading. 01 b pic s9(3) trailing separate. "
                                "01 g sign leading separate. 05 c pic s99. 05 d pic 99.")).parse().fields
        self.assertEqual([(fields[n].sign_leading, fields[n].sign_separate, fields[n].size) for n in ("A", "B", "G.C", "G.D")],
                         [(True, False, 3), (False, True, 4), (True, True, 3), (False, False, 2)])
        with self.assertRaises(CobolError):
            Parser(program("01 a pic 9(3) sign leading.")).parse()

    def test_synchronized_without_padding_only(self):
        Emitter(Parser(program("01 g. 05 a pic x(4). 05 b pic s9(9) comp sync.")).parse()).generate()
        Emitter(Parser(program("01 a pic x(3) sync.")).parse()).generate()
        with self.assertRaises(CobolError):
            Parser(program("01 g. 05 a pic x. 05 b pic s9(9) comp sync.")).parse()

    def test_implicit_filler_and_negative_zero_literal(self):
        fields = Parser(program("01 g. 05 pic x value 'A'. 05 n pic 9.")).parse().fields
        self.assertTrue(any(f.filler for f in fields.values()))
        with self.assertRaises(CobolError):
            Emitter(Parser(program("01 n pic s9.", "move -0 to n. stop run.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class DataClauseNativeTests(unittest.TestCase):
    def test_sign_clause_matches_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "sign_clause.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertEqual(lines[0], "[p12012-+034-1500][-0506]")
        # pretty display puts a trailing separate sign after the digits.
        self.assertEqual(lines[1], "-012 012- +034 -1.50 -007 -05 06")

    def test_condition_figuratives_match_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "condition_figuratives.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"].splitlines(), ["[XYZ004][000]", "d1", "not d2", "q"])


if __name__ == "__main__":
    unittest.main()
