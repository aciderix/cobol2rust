"""FUNCTION-ID: user-defined functions (cobc parser.y function_id_paragraph,
codegen.c output_function_entry_function, libcob cob_save_func)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cobol2rust.cli import emit_unit
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"

FUNCTION = ("identification division.\nfunction-id. twice.\ndata division.\nlinkage section.\n"
            "01 a pic 99.\n01 r pic 99.\nprocedure division using a{returning}.\n{body}\n"
            "end function {end}.\n")
CALLER = ("identification division.\nprogram-id. prog.\nenvironment division.\nconfiguration section.\n"
          "repository.\n    function twice.\ndata division.\nworking-storage section.\n01 n pic 99 value 4.\n"
          "procedure division.\n{body}\nstop run.\nend program prog.\n")


def unit(function_body="compute r = a * 2.", caller_body="display twice (n).", returning=" returning r", end="twice"):
    return FUNCTION.format(returning=returning, body=function_body, end=end) + CALLER.format(body=caller_body)


def emit(source):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "prog.cob"
        path.write_text(source, encoding="utf-8")
        return emit_unit(path, fmt="free", call_paths=[directory])


class UserFunctionTests(unittest.TestCase):
    def test_parser_follows_cobc(self):
        program = Parser(unit()).parse()
        function, caller = program, program.siblings[0]
        self.assertTrue(function.function and function.recursive)
        self.assertEqual((function.entry_name, function.returning), ("TWICE", "R"))
        self.assertEqual(caller.function_calls, ["TWICE"])

    def test_refusals_follow_cobc(self):
        cases = {"RETURNING clause is required for a FUNCTION": unit(returning=""),
                 "END FUNCTION 'other' is different from FUNCTION-ID 'twice'": unit(end="other"),
                 "RETURNING clause cannot be OMITTED": unit(returning=" returning omitted"),
                 "has invalid reference modification": unit(caller_body="display twice (n) (0:1).")}
        for message, source in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(CobolError, message):
                Parser(source).parse()

    def test_main_program_and_unconverted_refusals(self):
        _, _, _, subprograms, rust, _ = emit(unit())
        self.assertEqual([sub.entry_name for _, sub, _, _ in subprograms], ["TWICE"])
        self.assertIn('unit.function("TWICE"', rust)
        with self.assertRaisesRegex(CobolError, "executable requested but no program found"):
            emit(FUNCTION.format(returning=" returning r", body="move a to r.", end="twice"))
        with self.assertRaisesRegex(CobolError, "CALL d'une FUNCTION-ID"):
            emit(unit(caller_body='call "TWICE" using n.'))
        # A prototype only matters through its calls: an unconverted function
        # is refused where it is called.
        absent = CALLER.replace("function twice.", "function other.").format(body="display other (n).")
        with self.assertRaisesRegex(CobolError, "fonction utilisateur non convertie"):
            emit(absent)

    def test_recursive_call_beside_an_activation_item_is_refused(self):
        # run_functions-126: the inner activation re-points the static field.
        recursive = "if a > 0 subtract 1 from a move twice (a) to r else move 0 to r end-if."
        with self.assertRaisesRegex(CobolError, "champs statiques de cobc"):
            emit(unit(function_body=recursive))
        emit(unit(function_body="if a > 0 subtract 1 from a end-if move a to r."))


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class UserFunctionNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "user_functions.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        # The reference modification of a user function result is ignored.
        self.assertIn("[abc]000000012[hello world ]", report["rust_stdout"].splitlines())


if __name__ == "__main__":
    unittest.main()
