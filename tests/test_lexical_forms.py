from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter, numeric_text
from cobol2rust.frontend import CobolError, Parser, lex
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class LexicalFormTests(unittest.TestCase):
    def test_digit_leading_words_and_point_leading_literals(self):
        texts = [t.text for t in lex("01 3-DIMENSION-TBL. move .5 to x. compute y = (.5 + 1). 05 2POS-NUM.")]
        self.assertEqual(texts[:3], ["01", "3-DIMENSION-TBL", "."])
        self.assertIn(".5", texts)
        self.assertIn("2POS-NUM", texts)
        # A sentence period stays a period; pure numbers stay numbers.
        self.assertEqual([t.text for t in lex("pic x. 05 a. 12 1.5")][:7],
                         ["pic", "x", ".", "05", "a", ".", "12"])
        self.assertEqual(numeric_text(".5"), "0.5")
        self.assertEqual(numeric_text("-.5"), "-0.5")
        self.assertEqual(numeric_text("12.5"), "12.5")

    def test_v_leading_pictures_and_alphabetic_items(self):
        parsed = Parser(program("77 a pic sv9(5). 77 b pic v99 comp. 77 c pic a(3). 77 d pic 99v.")).parse()
        self.assertEqual((parsed.fields["A"].digits, parsed.fields["A"].scale, parsed.fields["A"].signed), (5, 5, True))
        self.assertEqual((parsed.fields["B"].digits, parsed.fields["B"].scale), (2, 2))
        self.assertEqual((parsed.fields["C"].kind, parsed.fields["C"].digits), ("text", 3))
        self.assertEqual((parsed.fields["D"].digits, parsed.fields["D"].scale), (2, 0))

    def test_alphabetic_numeric_mixes_are_refused(self):
        for body in ("move 12 to c.", "move n to c.", "if c = n display 'x' end-if."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program("77 c pic a(3). 77 n pic 999.", body + " stop run.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class LexicalFormNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "lexical_forms.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"],
                         "42 +.11111 .0625 [tumble]\n+.61111\n[25    ]\n[tumble] Z\nEQ\n")


if __name__ == "__main__":
    unittest.main()


class SetAndAllTests(unittest.TestCase):
    def test_unmodelled_all_and_set_forms_are_refused(self):
        data = "01 t. 02 e pic x occurs 2 indexed by ix. 01 n pic 99. 01 d pic 9v9. 01 x pic x(3)."
        for body in ("move all 'A' to n.", "if x = all 'A' display 'y' end-if.", "set n to x.",
                     "set d to ix.", "compute n = all 'A'."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(data, body + " stop run.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SetAndAllNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "set_all.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "[ABABABAB]\n[XXYZYZX]\n[QQQQQQQQQ]\n03 0003\n04\n")
