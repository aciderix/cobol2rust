"""Forms of the real corpora that cobc accepts: SORT of a table
(cob_table_sort), INSPECT of a literal or function, reference modification
of a function result, an IF ended by an enclosing scope terminator, comment
entries without IDENTIFICATION DIVISION, CLASS with figurative constants, an
FD with a numeric record, CBL/PROCESS lines, EXIT SECTION of the implicit
MAIN SECTION, LOCAL-STORAGE, READ KEY of an item no key starts at, STOP RUN
RETURNING and Z literals, configuration paragraphs in any order, DISPLAY
clauses, FUNCTION TRIM, level 78 and 01 CONSTANT, 38 digits, ROUNDED MODE,
DELETE FILE, C type usages and reserved aliases, REPOSITORY intrinsics,
DISPLAY of numeric function results and more intrinsic functions."""
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

    def test_refusals_of_the_gnucobol_testsuite(self):
        # Sources cobc 3.2 refuses that cobol2rust used to accept.
        cases = {
            "out of bounds": program("01 t. 02 e occurs 3 pic x.", "display e(4) t(3:2). stop run."),
            "not signed": program("01 n pic 9 value -1.", "stop run."),
            "original definition": program("01 a pic x. 01 b redefines a pic x. 01 c redefines b pic x.",
                                           "stop run."),
            "INDEXED should follow": program("01 t. 02 e occurs 3 indexed by i ascending key k. 03 k pic x.",
                                             "stop run."),
            "WHEN without imperative": program("01 n pic 9.",
                                               "evaluate n when 1 when other display n end-evaluate. stop run."),
            "is not defined": program("01 n pic 9.", "stop run\nnext-para. stop run."),
            "invalid PROGRAM-ID": "identification division. program-id. cob_x.\nprocedure division. stop run.",
            "literal length": program("01 n pic 9.", 'display "' + "x" * 8192 + '". stop run.'),
            "binary field cannot be larger than 18 digits": program("01 n pic 9(19) comp.", "stop run."),
            "cannot be larger than 38 digits": program("01 n pic 9(39).", "stop run."),
        }
        for message, source in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(CobolError, message):
                Parser(source).parse()

    def test_intrinsic_argument_counts_and_empty_literal(self):
        from cobol2rust import frontend
        for source in (program("01 x pic x(9).", 'move function substitute(x "a") to x. stop run.'),
                       program("01 n pic 9(4).", "move function year-to-yyyy(1 2 3 4) to n. stop run."),
                       program("01 n pic 9(4).", "move function abs(1 2) to n. stop run.")):
            with self.subTest(source=source), self.assertRaisesRegex(CobolError, "wrong number of arguments"):
                Parser(source).parse()
        cases = {"has invalid date/time format": 'move function formatted-date("YYMMDD", 1) to x. stop run.',
                 "SYSTEM-OFFSET at the same time":
                     'move function formatted-time("hhmmss", 1, 0, system-offset) to x. stop run.'}
        for message, body in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(CobolError, message):
                Parser(program("01 x pic x(9).", body)).parse()
        self.assertEqual(frontend.lex('""')[0].text, " ")
        previous, frontend.STD = frontend.STD, "cobol85"
        try:
            with self.assertRaisesRegex(CobolError, "zero-length literal does not conform"):
                frontend.lex('""')
        finally:
            frontend.STD = previous

    def test_constant_refusals_follow_cobc(self):
        cases = {
            "a constant may not be used here": program("78 c value 1. 01 c pic x.", "stop run."),
            "not an unsigned positive integer": program("78 c value -1. 01 x pic x(c).", "stop run."),
            "CONSTANT item not at 01 level": program("01 g. 05 c constant 1.", "stop run."),
            "Divide by ZERO": program("78 c value 1 / 0.", "stop run."),
            "invalid operator": program('78 c value "a" "b".', "stop run."),
        }
        for message, source in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(CobolError, message):
                Parser(source).parse()

    def test_directive_errors_follow_cobc(self):
        from cobol2rust.frontend import normalize
        cases = {"without matching IF": ">>END-IF\n", "duplicate DEFINE": ">>DEFINE A AS 1\n>>DEFINE A AS 2\n",
                 "invalid IF directive": ">>IF A\n>>END-IF\n", "sans >>END-IF": ">>IF A DEFINED\n"}
        for message, text in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(CobolError, message):
                normalize(text, "free")

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
                     "exit_implicit_section", "indexed_missing_key", "stop_run_status",
                     "evaluate_literal_when", "display_clauses", "function_trim", "constants_78",
                     "digits_38", "rounded_modes", "delete_file", "c_type_usages", "repository_intrinsic",
                     "comp6", "directives", "value_negative_zero", "picture_p_usages",
                     "mf_directives", "program_header_forms", "line_advancing_file", "packed_truncation",
                     "function_display", "function_more",
                     "function_iso8601"):
            with self.subTest(name=name):
                report = verify(FIXTURES / f"{name}.cob")
                self.assertTrue(report["match"], report)

    def test_copy_replacing_leading_trailing(self):
        report = verify(FIXTURES / "copy_partial.cob", includes=[FIXTURES / "copy_partial"])
        self.assertTrue(report["match"], report)

    def test_literal_call_arguments(self):
        report = verify(FIXTURES / "call_literals.cob", call_paths=[FIXTURES / "call_literals_calls"])
        self.assertTrue(report["match"], report)

    def test_local_storage_is_initialized_at_each_call(self):
        report = verify(FIXTURES / "local_storage.cob", call_paths=[FIXTURES / "local_storage_calls"])
        self.assertTrue(report["match"], report)
        self.assertIn("persisting 3 fresh 6", report["rust_stdout"])


if __name__ == "__main__":
    unittest.main()
