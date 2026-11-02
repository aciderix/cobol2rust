from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(storage, body="stop run."):
    return ("identification division.\nprogram-id. picture-l-case.\ndata division.\nworking-storage section.\n"
            f"{storage}01 lg pic 99 value 3.\nprocedure division.\n{body}\n")


class PictureLDeclarationTests(unittest.TestCase):
    def test_item_becomes_a_group_with_an_implicit_odo_filler(self):
        # parser.y picture_clause: PIC Lc... DEPENDING n is a group whose
        # FILLER is PIC c OCCURS 1 TO size - 1 DEPENDING n, not flag_filler.
        fields = Parser(program("01 g.\n 05 x picture lx(7) depending on lg.\n 05 y pic x.\n")).parse().fields
        x = fields["G.X"]
        child = fields[x.children[0]]
        self.assertTrue(x.picture_l and not x.picture)
        self.assertEqual((child.picture, child.occurs_min, child.occurs, child.depending, child.filler),
                         ("X", 1, 7, "LG", False))
        self.assertEqual((x.size, fields["G"].size, fields["G.Y"].offset), (7, 8, 7))

    def test_cobc_errors(self):
        for storage, message in [("01 x picture lx(3).\n", "requires DEPENDING clause"),
                                 ("01 x picture l9(3) depending lg.\n", "only USAGE DISPLAY"),
                                 ("01 x picture lx(3) depending lg value 'a'.\n", "mutually exclusive"),
                                 ("01 x picture lx(3) depending lg justified.\n", "JUSTIFIED"),
                                 ("01 x picture lx(3) depending lg.\n 05 y pic x.\n", "PICTURE L")]:
            with self.subTest(storage=storage), self.assertRaisesRegex(CobolError, message):
                Parser(program(storage)).parse()

    def test_unconformable_in_cobol85(self):
        previous, frontend.STD = frontend.STD, "cobol85"
        try:
            with self.assertRaisesRegex(CobolError, "does not conform to COBOL 85"):
                Parser(program("01 x picture lx(3) depending lg.\n")).parse()
        finally:
            frontend.STD = previous

    def test_length_of_is_the_picture_size(self):
        # typeck.c cb_build_length: flag_picture_l gives a literal.
        stmt = Parser(program("01 x picture lx(5) depending lg.\n01 n pic 99.\n", "move length of x to n.")).parse().entry[0]
        self.assertEqual(stmt.args[0].args, ("5",))


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class PictureLNativeTests(unittest.TestCase):
    def test_variable_length_items_match_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "picture_l.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        self.assertIn("[1r ] [<1r ***QRS >]\n", stdout)
        self.assertIn("[###AB####] [AB#] [###]\n[LLL  m1] [LLL  m1]\n", stdout)


if __name__ == "__main__":
    unittest.main()
