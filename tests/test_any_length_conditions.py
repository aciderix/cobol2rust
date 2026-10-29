from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


FIXTURE = ROOT / "tests" / "fixtures" / "any_length_conditions.cob"


def module(condition, body="goback."):
    return ("identification division. program-id. any-condition.\n"
            "data division. linkage section.\n01 arg pic x any length.\n"
            + condition + "\nprocedure division using arg.\n" + body)


class AnyLengthConditionFrontendTests(unittest.TestCase):
    def test_patterns_retain_the_full_literal_instead_of_the_nominal_picture(self):
        program = Parser(module("88 filled value 'other', all 'AB'.")).parse()
        condition = program.conditions["ARG.FILLED"]
        self.assertEqual(condition.repeated_values, {1: "AB"})
        self.assertEqual(condition.values[0][0].text, "other")

    def test_figuratives_remain_distinct_from_ordinary_literals(self):
        for word, pattern in (("spaces", " "), ("zeros", "0"), ("quotes", '"'),
                              ("high-values", "\xff"), ("low-values", "\0")):
            with self.subTest(word=word):
                condition = Parser(module("88 filled value " + word + ".")).parse().conditions["ARG.FILLED"]
                self.assertEqual(condition.repeated_values, {0: pattern})
        condition = Parser(module("88 filled value '0'.")).parse().conditions["ARG.FILLED"]
        self.assertFalse(condition.repeated_values)

    def test_set_false_keeps_a_figurative_or_an_ordinary_literal(self):
        for clause in ("when set to false", "false is"):
            with self.subTest(clause=clause):
                repeated = Parser(module("88 filled value 'Y' " + clause + " zeros.")).parse()
                ordinary = Parser(module("88 filled value 'Y' " + clause + " '0'.")).parse()
                self.assertEqual(repeated.conditions["ARG.FILLED"].false_repeated, "0")
                self.assertIsNone(ordinary.conditions["ARG.FILLED"].false_repeated)
                Emitter(repeated).generate()

    def test_conditions_and_set_statements_accept_repeated_values(self):
        program = Parser(module("88 filled value all 'AB' when set to false high-values.",
                                "if filled continue end-if set filled to true set filled to false goback.")).parse()
        Emitter(program).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class AnyLengthConditionNativeTests(unittest.TestCase):
    def test_conditions_set_and_initialize_match_native(self):
        report = verify(FIXTURE, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"],
                         "all-ok\nALL:[ABABABA]\nhigh-ok\nlow-ok\nquote-ok\nZERO:[0000000]\n"
                         "space-ok\nFALSE:[Y      ]\nfalse-high-ok\nINIT:[ XXXXXX]\nREPLACE:[ABC    ]\n")


if __name__ == "__main__":
    unittest.main()
