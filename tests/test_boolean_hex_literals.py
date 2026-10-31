from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.frontend import CobolError, Parser, lex
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(value):
    return ("identification division.\nprogram-id. literal-case.\ndata division.\nworking-storage section.\n"
            f"01 x pic 9(18) value {value}.\nprocedure division.\nstop run.\n")


class BooleanHexLiteralTests(unittest.TestCase):
    def test_scan_b_and_scan_h_build_numeric_literals(self):
        self.assertEqual([t.text for t in lex('b"010101" H\'ff\' B"0"')[:3]], ["21", "255", "0"])
        self.assertFalse(any(t.string for t in lex('b"1" h"1"')))

    def test_cobc_errors(self):
        for value, message in [('h"0G"', "invalid character 'G'"), ('h"12345678901234567"', "exceeds 16"),
                               ('b"012"', "invalid character '2'"), ('h""', "at least one character")]:
            with self.subTest(value=value), self.assertRaisesRegex(CobolError, message):
                Parser(program(value)).parse()

    def test_numeric_boolean_is_unconformable_in_cobol85(self):
        previous, frontend.STD = frontend.STD, "cobol85"
        try:
            with self.assertRaisesRegex(CobolError, "does not conform to COBOL 85"):
                Parser(program('b"01"')).parse()
            Parser(program('h"01"')).parse()
        finally:
            frontend.STD = previous


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class BooleanHexLiteralNativeTests(unittest.TestCase):
    def test_values_moves_and_arithmetic_match_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "boolean_hex_literals.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "21 00074565 152921504606846975\n00007\n00256\neq\n")


if __name__ == "__main__":
    unittest.main()
