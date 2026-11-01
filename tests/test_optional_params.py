from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def callee(using, body="goback.", data=""):
    return ("identification division.\nprogram-id. callee.\ndata division.\nworking-storage section.\n"
            f"01 w pic x.\n{data}linkage section.\n01 a pic x.\n01 b pic x(2).\n01 t. 05 e pic x occurs 2.\n"
            f"procedure division using {using}.\n{body}\n")


def in_cobol85(function):
    previous, frontend.STD = frontend.STD, "cobol85"
    try:
        return function()
    finally:
        frontend.STD = previous


class OptionalParameterTests(unittest.TestCase):
    def test_optional_marks_only_its_parameter(self):
        fields = Parser(callee("a optional b by reference optional t")).parse().fields
        self.assertEqual((fields["A"].optional, fields["B"].optional, fields["T"].optional), (False, True, True))

    def test_entry_check_only_for_required_parameters(self):
        # output_entry_function: cob_check_linkage_size under -debug only.
        rust, _ = Emitter(Parser(callee("a optional b")).parse()).generate()
        self.assertIn("storage_runtime::runtime_checks()", rust)
        self.assertIn("LINKAGE item A not passed by caller", rust)
        self.assertNotIn("LINKAGE item B not passed", rust)

    def test_cobol85_refuses_optional_and_checks_no_parameter(self):
        # cobol85.conf: using-optional unconformable, so cb_using_optional
        # != CB_OK exempts every parameter from the entry check.
        with self.assertRaisesRegex(CobolError, "USING OPTIONAL does not conform to COBOL 85"):
            in_cobol85(lambda: Parser(callee("a optional b")).parse())
        program = in_cobol85(lambda: Parser(callee("a b")).parse())
        self.assertTrue(program.fields["A"].optional)

    def test_refusals(self):
        for using in ("by value a", "a returning b"):
            with self.subTest(using=using), self.assertRaises(CobolError):
                Parser(callee(using)).parse()
        for condition in ("b (2:1) omitted", "e (1) omitted", "'x' omitted"):
            with self.subTest(condition=condition), self.assertRaisesRegex(CobolError, "OMITTED limité"):
                Emitter(Parser(callee("a optional b optional t",
                                      f"if {condition} display 'o' end-if. goback.")).parse()).generate()


class CallParameterRegisterTests(unittest.TestCase):
    def test_register_is_an_index_outside_the_storage(self):
        program = Parser(callee("a", "display number-of-call-parameters. goback.")).parse()
        field = program.fields["NUMBER-OF-CALL-PARAMETERS"]
        self.assertEqual((field.usage, field.size, field.register), ("INDEX", 4, True))
        rust, _ = Emitter(program).generate()
        self.assertIn("unit.params.last().map_or(0, |p| p.len())", rust)

    def test_built_only_when_referenced(self):
        self.assertNotIn("NUMBER-OF-CALL-PARAMETERS", Parser(callee("a")).parse().fields)

    def test_declared_homonym_is_ambiguous(self):
        with self.assertRaises(CobolError):
            Parser(callee("a", "display number-of-call-parameters. goback.",
                          "01 number-of-call-parameters pic 9.\n")).parse()

    def test_cobol85_has_no_register(self):
        # cobol85.words: not-register DIALECT-ALL.
        program = in_cobol85(lambda: Parser(callee("a", "display number-of-call-parameters. goback.",
                                                   "01 number-of-call-parameters pic 9 value 7.\n")).parse())
        self.assertFalse(getattr(program.fields["NUMBER-OF-CALL-PARAMETERS"], "register", False))


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class OptionalParameterNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        for checks in (False, True):
            with self.subTest(runtime_checks=checks):
                report = verify(FIXTURES / "optional_params.cob", fmt="fixed", runtime_checks=checks,
                                call_paths=[FIXTURES / "optional_params_calls"])
                self.assertTrue(report["match"], report)
                lines = report["cobol_stdout"].splitlines()
                self.assertIn("main +000000000", lines)
                self.assertIn("sub +000000003 AAA L2 omitted 14.", lines)
                self.assertIn("sub +000000001 AAA L2 omitted none.", lines)
                self.assertIn("ent +000000001 AAA ZZZ", lines)
                self.assertIn("inner 15", lines)


if __name__ == "__main__":
    unittest.main()
