from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class PScalingTests(unittest.TestCase):
    def test_scale_follows_cobc_picture_analysis(self):
        parsed = Parser(program("01 a pic s99p. 01 b pic 9(3)p(4). 01 c pic pp99. 01 d pic svp9. 01 e pic 9ppv.")).parse()
        fields = parsed.fields
        self.assertEqual([(fields[n].digits, fields[n].scale) for n in "ABCDE"],
                         [(2, -1), (3, -4), (2, 4), (1, 2), (1, -2)])
        # Only the 9 positions are stored.
        self.assertEqual([fields[n].size for n in "ABCDE"], [2, 3, 2, 1, 1])

    def test_add_int_truncates_operand_like_cob_add_int(self):
        rust = Emitter(Parser(program("01 a pic s99p.", "add 15 to a. add 15 to a rounded. stop run.")).parse()).generate()[0]
        self.assertEqual(rust.count("cob_add_int_operand"), 1)

    def test_refusals(self):
        for data, body in [("01 a pic 99p comp.", "stop run."), ("01 a pic 9p9.", "stop run."),
                           ("01 a pic 99p. 01 x pic xx.", "move a to x. stop run."),
                           ("01 a pic 99p. 01 x pic xx.", "if a = '12' stop run end-if.")]:
            with self.subTest(data=data, body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(data, body)).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class PScalingNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "p_scaling.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertEqual(lines[1], "+990 7000 .0012 -.05 +.0003")
        # ADD 15 TO S99P (-230): cob_add_int adds 15 truncated to tens.
        self.assertEqual(lines[11], "-220")


if __name__ == "__main__":
    unittest.main()
