"""Forms of the real corpora that cobc accepts: SORT of a table
(cob_table_sort), INSPECT of a literal or function, reference modification
of a function result, an IF ended by an enclosing scope terminator, comment
entries without IDENTIFICATION DIVISION, CLASS with figurative constants, an
FD with a numeric record."""
from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(storage, body):
    return ("identification division. program-id. forms.\ndata division. working-storage section.\n"
            + storage + "\nprocedure division.\n" + body)


class RealFormsFrontendTests(unittest.TestCase):
    def test_refusals_follow_cobc(self):
        table = "01 t. 02 e occurs 3 pic x. 01 n pic 9."
        cases = [program(table, 'inspect "abc" replacing all "a" by "b". stop run.'),
                 program(table, 'inspect function upper-case(t) converting "a" to "b". stop run.'),
                 program(table, "sort e. stop run."),                       # no KEY, no OCCURS KEY
                 program(table, "sort e on ascending key n. stop run."),    # key outside the element
                 program(table, "move function random(1:2) to n. stop run.")]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                Parser(source).parse()

    def test_table_sort_keys_use_the_offset_in_their_parent(self):
        source = program("01 t. 02 e occurs 3. 03 m pic x. 03 g. 04 l pic x. 04 d pic 9.",
                         "sort e on ascending key d. stop run.")
        stmt = Parser(source).parse().entry[0]
        self.assertEqual(stmt.op, "table_sort")
        self.assertEqual([(descending, offset) for descending, _, offset in stmt.args[1]], [(False, 1)])


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class RealFormsNativeTests(unittest.TestCase):
    def test_fixtures_match_cobc(self):
        for name in ("table_sort", "scope_and_function_forms", "numeric_record"):
            with self.subTest(name=name):
                report = verify(FIXTURES / f"{name}.cob")
                self.assertTrue(report["match"], report)


if __name__ == "__main__":
    unittest.main()
