from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body):
    return ("identification division.\nprogram-id. environment-unit.\ndata division.\nworking-storage section.\n"
            "01 v pic x(8).\n01 c pic 9(4) comp.\nprocedure division.\n" f"{body}\nstop run.\n")


class EnvironmentFrontendTests(unittest.TestCase):
    def test_exception_phrases_become_a_handler_check(self):
        stmt = Parser(program("accept v from environment 'X' on exception continue "
                              "not on exception continue end-accept.")).parse().entry[0]
        self.assertEqual(stmt.op, "sequence")
        accept, check = stmt.args[0]
        self.assertEqual((accept.op, accept.args[0], check.op, check.args[0].op),
                         ("environment", "get", "if", "imp_exception"))

    def test_cobc_errors(self):
        # parser.y: simple_display_value and id_or_lit.
        for body, message in [("accept v from environment 12.", "not an alphanumeric literal"),
                              ("accept v from environment c.", "not USAGE DISPLAY"),
                              ("display spaces upon environment-name.", "unexpected UPON"),
                              ("display v 'a' upon environment-value.", "unexpected UPON"),
                              ("accept v from environment-value on exception end-accept.", "without imperative")]:
            with self.subTest(body=body), self.assertRaisesRegex(CobolError, message):
                Parser(program(body)).parse()

    def test_not_exception_first_does_not_conform_to_cobol85(self):
        previous, frontend.STD = frontend.STD, "cobol85"
        try:
            with self.assertRaisesRegex(CobolError, "NOT EXCEPTION before EXCEPTION"):
                Parser(program("accept v from environment-value not on exception continue "
                               "on exception continue end-accept.")).parse()
        finally:
            frontend.STD = previous

    def test_a_libcob_setting_is_a_named_runtime_stop(self):
        rust = Emitter(Parser(program("set environment 'COB_SET_TRACE' to 'Y'.")).parse()).generate()[0]
        self.assertIn("runtime::environment::set(", rust)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class EnvironmentNativeTests(unittest.TestCase):
    def test_environment_arguments_and_command_line_match_native(self):
        fixture = ROOT / "tests" / "fixtures" / "environment.cob"
        report = verify(fixture, fmt="free", arguments=["first", "two words", "3"])
        self.assertTrue(report["match"] and report["stderr_match"], report)
        stdout = report["cobol_stdout"]
        self.assertTrue(stdout.startswith("absent [          ] EC-IMP-ACCEPT"))
        self.assertIn("setenv refused\nno name\nchild:val 1\n03 [000000003 ]\n", stdout)
        self.assertIn("end of arguments 4\nagain [two wo]\nno argument 9\nabsolute [first ]\n", stdout)
        bare = verify(fixture, fmt="free")
        self.assertTrue(bare["match"], bare)
        self.assertIn("00 [000000000 ]\nend of arguments 1\n", bare["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
