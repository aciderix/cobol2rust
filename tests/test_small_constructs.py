from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body, data="01 a pic x(4). 01 b pic x(4).\n"):
    return ("identification division.\nprogram-id. small-unit.\ndata division.\nworking-storage section.\n"
            f"{data}procedure division.\n{body}\nstop run.\n")


class SmallConstructTests(unittest.TestCase):
    def test_static_call_drops_on_exception(self):
        # "ON EXCEPTION ignored because of STATIC CALL"; NOT ON EXCEPTION stays.
        stmt = Parser(program("call static 'x' on exception display 'e' end-display end-call.")).parse().entry[0]
        self.assertTrue(stmt.static)
        self.assertEqual(stmt.args[2], [])

    def test_cobc_errors_and_named_refusals(self):
        for body, message in [("call static a.", "requires a literal program name"),
                              ("call c 'x'.", "convention d'appel"),
                              ("unstring 12 into a.", "littéral numérique"),
                              ("inspect a replacing characters by null.", "CHARACTERS BY NULL"),
                              ("inspect a tallying a for all 'x' before null.", "BEFORE NULL")]:
            with self.subTest(body=body), self.assertRaisesRegex(CobolError, message):
                Parser(program(body, "01 a pic x(4).\n" if "tallying" not in body else "01 a pic 9.\n")).parse()
        with self.assertRaisesRegex(CobolError, "OCCURS UNBOUNDED"):
            Parser(program("goback.", "01 g. 05 n pic 9. 05 t occurs unbounded depending n pic x.\n")).parse()
        with self.assertRaisesRegex(CobolError, "édition de liens statique"):
            Emitter(Parser(program("call static 'absent-program'.")).parse()).generate()

    def test_call_convention_does_not_conform_to_cobol85(self):
        previous, frontend.STD = frontend.STD, "cobol85"
        try:
            with self.assertRaisesRegex(CobolError, "does not conform to COBOL 85"):
                Parser(program("call static 'x'.")).parse()
        finally:
            frontend.STD = previous


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SmallConstructNativeTests(unittest.TestCase):
    def test_constructs_match_native(self):
        fixture = ROOT / "tests" / "fixtures" / "small_constructs.cob"
        report = verify(fixture, fmt="free", stdin=fixture.with_suffix(".txt").read_bytes())
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "[ab    cd    ef    ]\n[GH    IJ    ef    ]\nin callee\nin callee\n"
                                                 "after static\n03 [.A.B.]\nomitted\nend\n")


if __name__ == "__main__":
    unittest.main()
