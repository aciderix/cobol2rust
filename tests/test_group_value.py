from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_files import file_program
from tests.test_numeric_move import program


def parse(data: str):
    return Parser(program(data, "stop run.")).parse()


class GroupValueTests(unittest.TestCase):
    def test_group_value_and_usage_metadata(self):
        parsed = parse("01 g value 'AB'. 02 a pic x(3). 01 z value zeros. 02 n pic 99. "
                       "01 s value space. 02 n2 pic 9. 01 u comp. 02 h. 03 b pic 9(4). 03 d pic 9 display.")
        self.assertEqual(parsed.fields["G"].group_value, ("AB", None))
        self.assertEqual(parsed.fields["Z"].group_value[1], "0")
        self.assertEqual(parsed.fields["S"].group_value[1], " ")
        self.assertEqual(parsed.fields["U.H.B"].usage, "COMP")
        # GnuCOBOL lets an explicit subordinate USAGE take precedence.
        self.assertEqual(parsed.fields["U.H.D"].usage, "DISPLAY")
        self.assertEqual(parsed.fields["U"].usage, "DISPLAY")
        self.assertEqual(parsed.fields["U.H.B"].size, 2)

    def test_unmodelled_group_values_are_refused(self):
        cases = [
            "01 g value 'AB'. 02 a pic xx value 'CD'.",  # native: the group overrides it
            "01 g value 'AB'. 02 h value 'C'. 03 a pic x.",
            "01 g value 12. 02 a pic 99.",
            "01 g value all 'AB'. 02 a pic x(5).",
            "01 g value high-values. 02 a pic xx.",
            "01 g comp. 02 a pic x.",
            "01 r pic x(4). 01 g redefines r value 'AB'. 02 a pic x(4).",
            "01 r pic x(4). 01 t redefines r. 02 g value 'AB'. 03 a pic x(4).",
        ]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(CobolError):
                Emitter(parse(data)).generate()
        with self.assertRaises(CobolError):
            Parser(file_program(fd="fd f. 01 rec value 'AB'. 02 a pic x(8).")).parse()

    def test_group_value_with_variable_occurrences_is_refused(self):
        with self.assertRaises(CobolError):
            Emitter(parse("01 n pic 9 value 2. 01 g value 'ABC'. "
                          "02 e occurs 1 to 3 depending on n. 03 a pic x.")).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class GroupValueNativeTests(unittest.TestCase):
    def test_fixture_matches_native_bytes(self):
        report = verify(ROOT / "tests" / "fixtures" / "group_value.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertTrue(report["cobol_stdout"].startswith(
            "[40537][AB   ][   ][000][XYZ][12][ABABAB][0000]\n0\n"))
        self.assertTrue(report["cobol_stdout"].endswith("-0012 -005 0042\n[00000][   00]\n"))


if __name__ == "__main__":
    unittest.main()
