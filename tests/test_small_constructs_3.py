from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


class SmallConstructTests(unittest.TestCase):
    def test_special_names_sentences_follow_the_paragraph(self):
        # configuration_paragraph: special_names_sentence after its period.
        program = Parser("identification division.\nprogram-id. sn.\nenvironment division.\nconfiguration section.\n"
                         "special-names.\nclass a is 'A'.\nclass b is 'B'.\ndata division.\n"
                         "working-storage section.\n01 x pic x.\nprocedure division.\nstop run.\n").parse()
        self.assertTrue(program)
        with self.assertRaises(CobolError):
            Parser("identification division.\nprogram-id. sn.\nenvironment division.\nconfiguration section.\n"
                   "special-names.\nclass a is 'A'.\nbogus b.\nprocedure division.\nstop run.\n").parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SmallConstructNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "small_constructs_3.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"].splitlines()[-3:], ["outer", "inner", "leaf inner"])


if __name__ == "__main__":
    unittest.main()
