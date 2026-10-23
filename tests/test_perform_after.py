from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class PerformAfterTests(unittest.TestCase):
    def test_levels_and_default_step(self):
        parsed = Parser(program("01 i pic 9. 01 j pic 9.",
                                "perform varying i from 1 until i > 2 after j from 1 by 2 until j > 3 "
                                "continue end-perform stop run.")).parse()
        levels, test_after = parsed.entry[0].args[1]
        self.assertEqual(len(levels), 2)
        self.assertEqual(levels[0][2].args, ("1",))
        self.assertFalse(test_after)
        Emitter(parsed).generate()

    def test_non_numeric_levels_are_refused(self):
        for body in ("perform varying i from 1 until i > 2 after t from 1 until t > 1 continue end-perform.",
                     "perform varying i from 1 by t until i > 2 continue end-perform."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program("01 i pic 9. 01 t pic x.", body + " stop run.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class PerformAfterNativeTests(unittest.TestCase):
    def test_fixture_matches_cobc_loop_structure(self):
        report = verify(ROOT / "tests" / "fixtures" / "perform_after.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # The inner variable is reset before the outer test, so it ends at 1.
        self.assertIn("END-B +04 +01", lines)
        # TEST AFTER tests the outer condition after the inner loop: 3 x 3 runs.
        self.assertEqual(sum(line.startswith("A ") for line in lines), 9)
        self.assertIn("THREE 010 +03 +01 +03", lines)


if __name__ == "__main__":
    unittest.main()
