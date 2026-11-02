from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body, storage=""):
    return ("identification division.\nprogram-id. routine-case.\ndata division.\nworking-storage section.\n"
            f"01 a pic x(4).\n01 n pic 9(4).\n{storage}procedure division.\n{body}\nstop run.\n")


class CallFormTests(unittest.TestCase):
    def test_returning_giving_and_omitted(self):
        for body, expected in [("call 'x' using a returning n.", "N"), ("call 'x' giving n.", "N"),
                               ("call 'x' returning omitted.", "omitted")]:
            with self.subTest(body=body):
                stmt = next(s for s in Parser(program(body)).parse().entry if s.op == "call_program")
                returning = stmt.returning
                self.assertEqual(returning if isinstance(returning, str) else returning.name, expected)

    def test_returning_needs_a_numeric_item(self):
        with self.assertRaisesRegex(CobolError, "non numérique"):
            Parser(program("call 'x' returning a.")).parse()

    def test_function_arguments(self):
        Emitter(Parser(program("call 'C$JUSTIFY' using function trim(a) by content function upper-case(a).")).parse()).generate()
        with self.assertRaisesRegex(CobolError, "FUNCTION numérique"):
            Emitter(Parser(program("call 'C$JUSTIFY' using function integer(n).")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class LibraryRoutineNativeTests(unittest.TestCase):
    def test_routines_and_call_forms_match_native(self):
        # cob_set_int of CALL RETURNING (RETURN-CODE kept), C$NARG,
        # C$PARAMSIZE, C$CALLEDBY, C$JUSTIFY, C$PRINTABLE, C$SLEEP and SYSTEM
        # (raw status, one-byte command not run).
        directory = ROOT / "tests" / "fixtures" / "library_routines"
        report = verify(directory / "library-main.cob", fmt="free", call_paths=[directory])
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        self.assertIn("returning +0000000042 +000000007\n", stdout)
        self.assertIn("size1 0004\nsize2 0000\nsize3 0000\ncalledby +000000001 [library-main    ]\nomitted +000000007\n", stdout)
        self.assertTrue(stdout.endswith("before\nchild\nsystem +000000768\none +000000001\n"))


if __name__ == "__main__":
    unittest.main()
