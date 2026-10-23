from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class ComparisonFoldingTests(unittest.TestCase):
    def folded(self, data, condition):
        parsed = Parser(program(data, f"if {condition} continue end-if. stop run.")).parse()
        emitter = Emitter(parsed)
        stmt = parsed.entry[0]
        left, right = stmt.args[0].args
        return emitter.folded_comparison(stmt.args[0].op[3:], left, right)

    def test_rules_of_compare_field_literal(self):
        self.assertIs(self.folded("01 n pic s99.", "n > -100"), False)
        self.assertIs(self.folded("01 n pic s99.", "-100 < n"), False)
        self.assertIs(self.folded("01 n pic 99.", "n <= 100"), True)
        self.assertIs(self.folded("01 d pic 9v9.", "d = 1.55"), False)
        self.assertIsNone(self.folded("01 d pic 9v9.", "d = 1.50"))
        self.assertIsNone(self.folded("01 n pic 99.", "n = 0099"))
        self.assertIs(self.folded("01 e pic -9(3).99.", 'e = "1234567"'), False)
        # Edited items fold only = and <>: < and > stay alphanumeric comparisons.
        self.assertIsNone(self.folded("01 e pic -9(3).99.", 'e > "1234567"'))
        self.assertIsNone(self.folded("01 x pic xx.", 'x = "ABC"'))
        self.assertIsNone(self.folded("01 n pic 99 comp.", "n > 100"))


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ComparisonFoldingNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "comparison_folding.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertIn("c3 false", lines)
        self.assertIn("c18 false", lines)


if __name__ == "__main__":
    unittest.main()
