"""Forms of the real corpora that cobc accepts: SORT of a table
(cob_table_sort), INSPECT of a literal or function, reference modification
of a function result, an IF ended by an enclosing scope terminator, comment
entries without IDENTIFICATION DIVISION, CLASS with figurative constants, an
FD with a numeric record, CBL/PROCESS lines, EXIT SECTION of the implicit
MAIN SECTION, LOCAL-STORAGE, READ KEY of an item no key starts at, STOP RUN
RETURNING and Z literals, configuration paragraphs in any order."""
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

    def test_parser_forms_cobc_accepts(self):
        # Configuration paragraphs in any order or empty, a missing period
        # before the next SELECT, two 01 items of one name (a warning).
        Parser("identification division. program-id. cfg.\nenvironment division. configuration section.\n"
               "special-names. decimal-point is comma. object-computer. x. source-computer.\n"
               "input-output section. file-control. select a assign to 'a' select b assign to 'b'.\n"
               "data division. file section. fd a. 01 r pic x. fd b. 01 r2 pic x.\n"
               "working-storage section. 01 d pic x. 01 d pic x.\nprocedure division. stop run.").parse()
        with self.assertRaises(CobolError):
            Parser(program("01 d pic x. 01 d pic x.", "display d. stop run.")).parse()

    def test_table_sort_keys_use_the_offset_in_their_parent(self):
        source = program("01 t. 02 e occurs 3. 03 m pic x. 03 g. 04 l pic x. 04 d pic 9.",
                         "sort e on ascending key d. stop run.")
        stmt = Parser(source).parse().entry[0]
        self.assertEqual(stmt.op, "table_sort")
        self.assertEqual([(descending, offset) for descending, _, offset in stmt.args[1]], [(False, 1)])


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class RealFormsNativeTests(unittest.TestCase):
    def test_fixtures_match_cobc(self):
        for name in ("table_sort", "scope_and_function_forms", "numeric_record", "compiler_options",
                     "exit_implicit_section", "indexed_missing_key", "stop_run_status"):
            with self.subTest(name=name):
                report = verify(FIXTURES / f"{name}.cob")
                self.assertTrue(report["match"], report)

    def test_local_storage_is_initialized_at_each_call(self):
        report = verify(FIXTURES / "local_storage.cob", call_paths=[FIXTURES / "local_storage_calls"])
        self.assertTrue(report["match"], report)
        self.assertIn("persisting 3 fresh 6", report["rust_stdout"])


if __name__ == "__main__":
    unittest.main()
