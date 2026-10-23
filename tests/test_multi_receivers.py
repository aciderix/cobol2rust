from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


def statements(body: str, data: str = "01 a pic 9. 01 b pic 9. 01 c pic 9."):
    parsed = Parser(program(data, body)).parse()
    Emitter(parsed).generate()
    return parsed.entry


def receivers(stmt):
    return [(ref.name, rounded) for ref, _, rounded in stmt.args[1]]


class MultiReceiverTests(unittest.TestCase):
    def test_every_receiver_is_kept_with_its_own_rounded(self):
        cases = {
            "add 1 to a, b c.": [("A", False), ("B", False), ("C", False)],
            "subtract 1 2 from a rounded b.": [("A", True), ("B", False)],
            "multiply 2 by a b rounded.": [("A", False), ("B", True)],
            "divide 2 into a b.": [("A", False), ("B", False)],
            "compute a rounded b = 1.5.": [("A", True), ("B", False)],
            "add a to b giving c, a rounded.": [("C", False), ("A", True)],
            "divide 2 into 9 giving a b.": [("A", False), ("B", False)],
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                self.assertEqual(receivers(statements(body + " stop run.")[0]), expected)

    def test_single_operand_is_reread_and_several_are_summed_once(self):
        single = statements("add a to a b. stop run.")[0]
        self.assertIsNone(single.args[0])
        several = statements("add a 1 to a b. stop run.")[0]
        self.assertIsNotNone(several.args[0])
        giving = statements("add a to b giving c a. stop run.")[0]
        self.assertEqual(giving.args[1][0][1].op, "shared")

    def test_size_error_handlers_cover_all_receivers(self):
        stmt = statements('add 1 to a b on size error display "E" end-add stop run.')[0]
        self.assertEqual(stmt.op, "arithmetic")
        self.assertEqual(receivers(stmt), [("A", False), ("B", False)])

    def test_malformed_receiver_lists_are_refused(self):
        for body in ("add 1 to a rounded giving b.", "add 1 a to b c giving d.",
                     "add a to 1.", "compute a b 1.", "add 1 to a b. a."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                statements(body + " stop run.", "01 a pic 9. 01 b pic 9. 01 c pic 9. 01 d pic 9.")

    def test_procedure_names_cannot_hide_a_data_receiver(self):
        # Previously "add 1 to a, b." silently made B a paragraph.
        for header in ("b.", "b section.", "e.", "idx."):
            with self.subTest(header=header), self.assertRaises(CobolError):
                statements("add 1 to a. " + header + " stop run.",
                           "01 a pic 9. 01 b pic 9. 01 t. 02 e pic x occurs 2 indexed by idx.")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class MultiReceiverNativeTests(unittest.TestCase):
    def test_fixture_matches_native_semantics(self):
        report = verify(ROOT / "tests" / "fixtures" / "multi_receivers.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # GnuCOBOL re-reads a single operand: ADD X TO X Y gives Y = 12, not 11.
        self.assertEqual(lines[0], "ADD   +02 +12")
        self.assertEqual(lines[1], "ADD2  +04 +13")
        self.assertIn("SIZE  +11 +95 +20", lines)
        self.assertIn("SUBS  2 +00+01+00", lines)


if __name__ == "__main__":
    unittest.main()
