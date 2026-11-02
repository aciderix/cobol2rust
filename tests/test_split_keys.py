from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(keys, body="stop run.", data=""):
    return ("identification division.\nprogram-id. sk.\nenvironment division.\ninput-output section.\n"
            f"file-control.\nselect f assign 'k.dat' organization indexed access dynamic\n{keys}.\n"
            "data division.\nfile section.\nfd f.\n01 r.\n 03 a pic x(2).\n 03 b pic 9(2).\n 03 c pic x(2).\n"
            f"working-storage section.\n{data}procedure division.\n{body}\n")


class SplitKeyTests(unittest.TestCase):
    def test_components_and_composite_item(self):
        parsed = Parser(program("record key is pk source is b, a alternate record key ak = c a with duplicates "
                                "suppress when all '*'")).parse()
        spec = parsed.files["F"]
        self.assertEqual(spec.key_parts, {0: [(2, 2), (0, 2)], 1: [(4, 2), (0, 2)]})
        self.assertEqual(spec.key_suppress, {1: ord("*")})
        self.assertEqual(parsed.fields["PK"].size, 4)
        rust, _ = Emitter(parsed).generate()
        self.assertIn("parts: vec![(2, 2), (0, 2)]", rust)

    def test_suppress_characters(self):
        # cb_literal_value: a numeric literal is an ordinal (n - 1).
        for clause, char in [("suppress when space", 32), ("suppress when zero", 48), ("suppress when all 43", 42)]:
            with self.subTest(clause=clause):
                spec = Parser(program(f"record key is a alternate record key is c {clause}")).parse().files["F"]
                self.assertEqual(spec.key_suppress, {1: char})

    def test_start_key_must_be_a_key_item(self):
        # check_valid_key: the composite item or a record item at a key's
        # offset (0 for a split key's WORKING-STORAGE item).
        keys = "record key is pk source is b a"
        with self.assertRaisesRegex(CobolError, "invalid key item"):
            Parser(program(keys, "start f key >= b. stop run.")).parse()
        Parser(program(keys, "start f key >= pk. start f key >= a. stop run.")).parse()

    def test_components_belong_to_the_record(self):
        with self.assertRaises(CobolError):
            Parser(program("record key is pk source is w", data="01 w pic x(2).\n")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SplitKeyNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "split_keys.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertEqual(lines[0], "dup write 22")
        self.assertEqual(lines[-1], "ak AA01XXone ")


if __name__ == "__main__":
    unittest.main()
