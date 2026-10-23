from __future__ import annotations

import unittest

from cobol2rust.data_parser import valid_char_order
from cobol2rust.frontend import Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class NumericEditingTests(unittest.TestCase):
    def test_symbols_digits_and_scale_follow_cobc(self):
        fields = Parser(program("01 a pic $$$,$$9.99. 01 b pic +++9. 01 c pic zz9.99cr. 01 d pic zzzpp. "
                                "01 e pic 999 blank when zero.")).parse().fields
        self.assertEqual((fields["A"].edit_symbols, fields["A"].digits, fields["A"].scale, fields["A"].size),
                         ([("$", 3), (",", 1), ("$", 2), ("9", 1), (".", 1), ("9", 2)], 7, 2, 10))
        self.assertEqual((fields["B"].digits, fields["B"].size), (3, 4))
        self.assertEqual((fields["C"].edit_symbols[-1], fields["C"].size), (("C", 1), 8))
        self.assertEqual((fields["D"].digits, fields["D"].scale, fields["D"].size), (5, -2, 3))
        self.assertEqual((fields["E"].kind, fields["E"].edit_symbols, fields["E"].blank_zero), ("edited", [("9", 3)], True))

    def test_precedence_table(self):
        self.assertTrue(valid_char_order([("$", 1), ("+", 3), ("9", 1)]))
        self.assertFalse(valid_char_order([("Z", 1), ("9", 1), ("Z", 1)]))
        self.assertFalse(valid_char_order([("+", 1), ("9", 2), ("C", 1)]))


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NumericEditingNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "numeric_editing.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # A fixed sign before floating currency: libcob leaves the sign alone.
        self.assertIn("[-  $0]", lines[14])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class AlnumEditingNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "alnum_editing.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # No VALUE: edited spaces; explicit VALUE: stored as written.
        self.assertEqual(lines[0], "[   0   0 ][  /  /  ][ab c0d ][     ]")
        # A group sender is a group move: no insertion.
        self.assertIn("[GH12     ]", lines)

    def test_alnum_edited_picture_is_text(self):
        field = Parser(program("01 a pic x(2)b0/x.")).parse().fields["A"]
        self.assertEqual((field.kind, field.alnum_edit, field.size), ("text", "XXB0/X", 6))
