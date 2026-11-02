from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(data, linkage=""):
    return ("identification division.\nprogram-id. constant-unit.\ndata division.\nworking-storage section.\n"
            f"01 w. 05 wa pic x(3) occurs 2. 05 wb pic 9.\n{data}"
            + (f"linkage section.\n{linkage}" if linkage else "") + "procedure division.\nstop run.\n")


class ConstantLengthTests(unittest.TestCase):
    def constant(self, data, name, linkage=""):
        parser = Parser(program(data, linkage))
        parser.parse()
        return parser.constants[name][0].text

    def test_lengths_and_positions(self):
        # cb_build_const_length: memory_size (size by occurrences);
        # cb_build_const_next: after the first element of a table.
        self.assertEqual(self.constant("78 k value length of wa.\n", "K"), "6")
        self.assertEqual(self.constant("01 k constant as byte-length of w + length of binary-short.\n", "K"), "9")
        self.assertEqual(self.constant("", "N", "01 l. 05 la pic x(4) occurs 3.\n 78 n value next.\n"), "4")
        self.assertEqual(self.constant("", "S", "01 l. 05 la pic x(4). 05 lb pic x.\n78 s value start of lb.\n"), "4")

    def test_cobc_errors(self):
        for data, linkage, message in [
                ("78 k value start of wb.\n", "", "must be in FILE SECTION or LINKAGE SECTION"),
                ("", "01 l. 05 la pic x occurs 2.\n78 k value start of la.\n", "requires one subscript"),
                ("78 k value byte-length of w.\n", "", "littéral attendu"),
                ("01 k constant as byte-length of w + byte-length of w.\n", "", ""),
                ("01 k constant from nowhere.\n", "", "has not been DEFINEd"),
                ("01 k constant as length of float-binary-64.\n", "", "isn't supported"),
                ("01 v. 05 n pic 9. 05 t pic x occurs 1 to 3 depending n.\n78 k value length of v.\n", "",
                 "variable length item not allowed here")]:
            with self.subTest(data=data, linkage=linkage), self.assertRaisesRegex(CobolError, message):
                Parser(program(data, linkage)).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ConstantLengthNativeTests(unittest.TestCase):
    def test_constant_lengths_match_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "constant_lengths.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "15 3 16\n1 4 4 5 46\n6 8 0 3 14\n35 6 6\n")


if __name__ == "__main__":
    unittest.main()
