from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(storage):
    return ("identification division.\nprogram-id. comp-x-case.\ndata division.\nworking-storage section.\n"
            f"{storage}procedure division.\nstop run.\n")


class CompXDeclarationTests(unittest.TestCase):
    def test_pic_x_digits_and_compute_size_table(self):
        # field.c: PIC X(n) is 9(pic_digits[n - 1]) on n bytes; a numeric
        # PICTURE takes compute_size's bytes (9(5) on 3 bytes).
        cases = {"pic x comp-x": (2, 1), "pic xx comp-x": (4, 2), "pic x(3) comp-x": (7, 3),
                 "pic x(8) comp-n": (18, 8), "pic 9(3) comp-x": (3, 2), "pic 9(5) comp-n": (5, 3),
                 "pic s9(4) comp-x": (4, 2), "pic 9(19) computational-x": (19, 8)}
        for clause, (digits, size) in cases.items():
            with self.subTest(clause=clause):
                field = Parser(program(f"01 x {clause}.\n")).parse().fields["X"]
                usage = "COMP-X" if clause.endswith("x") else "COMP-N"
                self.assertEqual((field.usage, field.digits, field.size), (usage, digits, size))

    def test_cobc_refusals(self):
        for storage, message in [("01 x comp-x.\n", "PICTURE clause required"),
                                 ("01 x pic a comp-x.\n", "not compatible with USAGE COMP-X"),
                                 ("01 x pic x(9) comp-x.\n", "plus de 8 octets"),
                                 ("01 x pic 9(20) comp-n.\n", "plus de 8 octets")]:
            with self.subTest(storage=storage), self.assertRaisesRegex(CobolError, message):
                Parser(program(storage)).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class CompXNativeTests(unittest.TestCase):
    def test_real_binary_big_endian_matches_native(self):
        # Bounded by the size, not the PICTURE: MOVE 300 to one byte gives
        # 44, SIZE ERROR on the bit capacity, big-endian storage, DISPLAY on
        # the PICTURE digits.
        report = verify(ROOT / "tests" / "fixtures" / "comp_x.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        self.assertTrue(stdout.startswith("00 5535 999 12345 -1234 99\n1 2 3 2 3 2 1\n44\n"))
        self.assertIn("010201020102FFFE\n5534\nt size\n5535\n", stdout)


if __name__ == "__main__":
    unittest.main()
