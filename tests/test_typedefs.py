from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(data):
    return ("identification division.\nprogram-id. typedef-unit.\ndata division.\nworking-storage section.\n"
            f"01 t is typedef pic x(3).\n01 g is typedef. 05 a pic 9. 05 b pic x.\n01 w pic x.\n{data}"
            "procedure division.\nstop run.\n")


class TypedefTests(unittest.TestCase):
    def test_copies_and_no_storage_for_the_type(self):
        fields = Parser(program("01 c type to g occurs 2.\n01 d usage t.\n")).parse().fields
        self.assertNotIn("T", fields)
        self.assertNotIn("G", fields)
        self.assertEqual((fields["C"].occurs, fields["C.A"].size, fields["D"].size), (2, 1, 3))

    def test_cobc_errors(self):
        for data, message in [("01 c pic x type to t.\n", "illegal combination of TYPE TO"),
                              ("01 c. 05 d is typedef pic x.\n", "only allowed at 01/77 level"),
                              ("01 c type to w.\n", "is not a TYPEDEF name"),
                              ("01 c same as t.\n", "TYPEDEF item cannot be used here"),
                              ("77 c type to g.\n", "elementary item expected"),
                              ("01 c type to t.\n 05 d pic x.\n", "may not be subordinate"),
                              ("01 c usage t value 'a' .\n01 e usage c.\n", "")]:
            with self.subTest(data=data), self.assertRaisesRegex(CobolError, message):
                Parser(program(data)).parse()

    def test_unconformable_in_cobol85(self):
        previous, frontend.STD = frontend.STD, "cobol85"
        try:
            with self.assertRaises(CobolError):
                Parser("identification division.\nprogram-id. p.\ndata division.\nworking-storage section.\n"
                       "01 t is typedef pic x.\nprocedure division.\nstop run.\n").parse()
        finally:
            frontend.STD = previous


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class TypedefNativeTests(unittest.TestCase):
    def test_typedefs_match_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "typedefs.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertIn("[0700y0703n|] 03\non\n[0700n] [-001.50] [0700n0700n|]\n", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
