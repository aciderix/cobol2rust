from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(header, data="", body="goback."):
    return (f"identification division.\nprogram-id. {header}.\ndata division.\nworking-storage section.\n"
            f"01 w pic x.\n{data}procedure division.\n{body}\n")


def in_cobol85(function):
    previous, frontend.STD = frontend.STD, "cobol85"
    try:
        return function()
    finally:
        frontend.STD = previous


class RecursiveParseTests(unittest.TestCase):
    def test_program_type_clause(self):
        # _program_type: COMMON | init_or_recurse [COMMON] | COMMON init_or_recurse.
        for header, recursive in [("p is recursive", True), ("p recursive program", True),
                                  ("p is initial", False), ("p", False)]:
            with self.subTest(header=header):
                self.assertEqual(Parser(program(header)).parse().recursive, recursive)
        nested = ("identification division.\nprogram-id. outer.\nprocedure division.\ngoback.\n"
                  "identification division.\nprogram-id. inner is common recursive.\nprocedure division.\ngoback.\n"
                  "end program inner.\nend program outer.\n")
        self.assertTrue(Parser(nested).parse().nested[0].recursive)
        for header in ("p is initial recursive", "p is", "p recursive recursive"):
            with self.subTest(header=header), self.assertRaises(CobolError):
                Parser(program(header)).parse()

    def test_recursive_is_no_cobol85_word(self):
        with self.assertRaises(CobolError):
            in_cobol85(lambda: Parser(program("p is recursive", body="exit program.")).parse())

    def test_call_of_own_program_id_assumes_recursive(self):
        # is_recursive_call: the literal as written, case included;
        # self-call-recursive is skip in cobol85.
        self.assertTrue(Parser(program("selfc", body='call "selfc". goback.')).parse().recursive)
        self.assertFalse(Parser(program("selfc", body='call "SELFC". goback.')).parse().recursive)
        self.assertFalse(in_cobol85(lambda: Parser(program("selfc", body='call "selfc". exit program.')).parse()).recursive)

    def test_static_state_refused(self):
        for header, data, body in [("p is recursive", "01 b pic x based.\n", "goback."),
                                   ("p is recursive", "", "a. go to b. b. alter a to proceed to b. goback."),
                                   ("p is initial", "", 'call "p". goback.')]:
            with self.subTest(data=data, body=body), self.assertRaisesRegex(CobolError, "RECURSIVE"):
                Emitter(Parser(program(header, data, body)).parse()).generate()
        linkage = program("p is recursive").replace("procedure division.", "linkage section.\n01 l pic x.\nprocedure division.")
        with self.assertRaisesRegex(CobolError, "LINKAGE item|LINKAGE hors"):
            Emitter(Parser(linkage).parse()).generate()

    def test_end_program_of_the_outermost_may_be_missing(self):
        # parser.y: _end_program_list may be empty at depth 1, not deeper.
        text = ("identification division.\nprogram-id. outer.\nprocedure division.\ngoback.\n"
                "identification division.\nprogram-id. inner.\nprocedure division.\ngoback.\n")
        with self.assertRaisesRegex(CobolError, "without matching END PROGRAM"):
            Parser(text).parse()
        self.assertEqual(Parser(text + "end program inner.\n").parse().nested[0].entry_name, "inner")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class RecursiveNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "recursive_calls.cob", fmt="fixed", call_paths=[FIXTURES / "recursive_calls"])
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # LOCAL-STORAGE and NUMBER-OF-CALL-PARAMETERS per activation,
        # WORKING-STORAGE shared.
        self.assertIn("leave 05 mine 01 args 2 calls 05", lines)
        self.assertIn("enter 04 depth 02 mine 02 args 3", lines)
        self.assertIn("inner out 1", lines)
        self.assertEqual(lines[-3:], ["main pass 2 params +000000000", "main inner 2", "main back 1 passes 2"])

    def test_cancel_of_an_active_recursive_program_is_a_named_stop(self):
        report = verify(FIXTURES / "recursive_cancel.cob", fmt="fixed")
        self.assertEqual(report["cobol_exit"], 0)
        self.assertEqual(report["rust_exit"], 70)
        self.assertIn("CANCEL of an active RECURSIVE program", report["rust_stderr"])


if __name__ == "__main__":
    unittest.main()
