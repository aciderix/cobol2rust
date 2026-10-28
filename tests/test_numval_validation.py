from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.emitter import Emitter
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


FIXTURE = ROOT / "tests" / "fixtures" / "numval_validation.cob"
FIXTURE_STDOUT = (
    "VALID:000000000\nPOSITION:000000004:000000003\n"
    "CURRENCY:000000000:000000000:000000002\n"
    "EXPONENT:000000000:000000003:000000008\n"
    "SUM:+000000125.012500\nCONVERT:+000000120.000000\nDIRECT:000000125\n"
)


def program(body, storage="", configuration=""):
    return ("identification division. program-id. numval-case.\n" + configuration +
            "data division. working-storage section.\n" + storage +
            "\nprocedure division.\n" + body + "\nstop run.\n")


def quoted(text):
    return '"' + text.replace('"', '""') + '"'


class NumvalValidationFrontendTests(unittest.TestCase):
    def test_native_argument_counts(self):
        for name in ("NUMVAL-F", "TEST-NUMVAL", "TEST-NUMVAL-F", "TEST-NUMVAL-C"):
            for arguments in ('("12")', '(12)', '(digits-a)', '(group-a)'):
                with self.subTest(name=name, arguments=arguments):
                    Parser(program("display function " + name + arguments + ".",
                                   "01 digits-a pic 99 value 12.\n"
                                   "01 group-a. 05 item-a pic xx value '12'.")).parse()
        for currency in ('"$"', '12'):
            Parser(program('display function test-numval-c("1", ' + currency + ').')).parse()

    def test_wrong_argument_counts_are_rejected(self):
        for name in ("NUMVAL-F", "TEST-NUMVAL", "TEST-NUMVAL-F", "TEST-NUMVAL-C"):
            invalid = ["", "()", '("1", "X", "Y")']
            if name != "TEST-NUMVAL-C":
                invalid.append('("1", "$")')
            for arguments in invalid:
                with self.subTest(name=name, arguments=arguments), self.assertRaises(CobolError):
                    Parser(program("display function " + name + arguments + ".")).parse()

    def test_numeric_results_do_not_allow_reference_modification(self):
        for name in ("NUMVAL-F", "TEST-NUMVAL", "TEST-NUMVAL-C", "TEST-NUMVAL-F"):
            with self.subTest(name=name), self.assertRaises(CobolError):
                Parser(program('display function ' + name + '("12")(1:1).')).parse()

    def test_calculated_storage_is_not_treated_as_literal_digits(self):
        for name in ("NUMVAL-F", "TEST-NUMVAL", "TEST-NUMVAL-C", "TEST-NUMVAL-F"):
            for operand in ("-(1)", "+(1)", "1 + 2", "function integer(49.9)"):
                with self.subTest(name=name, operand=operand), self.assertRaisesRegex(CobolError, "stockage"):
                    Emitter(Parser(program("display function " + name + "(" + operand + ").")).parse()).generate()
            for operand in ("-12.30", "+0012.30"):
                with self.subTest(name=name, operand=operand):
                    Emitter(Parser(program("display function " + name + "(" + operand + ").")).parse()).generate()

    def test_repository_intrinsics_resolve_the_four_names(self):
        configuration = ("environment division. configuration section. repository.\n"
                         "function numval-f test-numval test-numval-c test-numval-f intrinsic.\n")
        Parser(program('display numval-f("1E+2") test-numval("12") '
                       'test-numval-c("$12") test-numval-f("1E+2").',
                       configuration=configuration)).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NumvalValidationNativeTests(unittest.TestCase):
    def assert_matches(self, source_text, expected):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "numval-case.cob"
            source.write_text(source_text, encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], expected, report)
        self.assertEqual(report["rust_stdout"], expected, report)

    def test_fixture_matches_independent_expected_values_and_display_shapes(self):
        report = verify(FIXTURE, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], FIXTURE_STDOUT, report)
        self.assertEqual(report["rust_stdout"], FIXTURE_STDOUT, report)

    def test_validation_returns_native_byte_positions(self):
        # Measured independently with GnuCOBOL 3.2, including end+1 errors.
        cases = [
            ("TEST-NUMVAL", ["123"], 0),
            ("TEST-NUMVAL", ["  +12.30 "], 0),
            ("TEST-NUMVAL", ["12.30-"], 0),
            ("TEST-NUMVAL", ["12CR"], 0),
            ("TEST-NUMVAL", ["12DB"], 0),
            ("TEST-NUMVAL", ["12cr"], 3),
            ("TEST-NUMVAL", ["1,234.50"], 2),
            ("TEST-NUMVAL", ["1.2.3"], 4),
            ("TEST-NUMVAL", ["12 34"], 4),
            ("TEST-NUMVAL", ["  "], 3),
            ("TEST-NUMVAL", ["+"], 2),
            ("TEST-NUMVAL", ["12.3E+2"], 5),
            ("TEST-NUMVAL", ["$12"], 1),
            ("TEST-NUMVAL", ["12+"], 0),
            ("TEST-NUMVAL", ["1" * 38], 0),
            ("TEST-NUMVAL", ["1" * 39], 39),
            ("TEST-NUMVAL-F", ["12"], 0),
            ("TEST-NUMVAL-F", ["1.25E+2"], 0),
            ("TEST-NUMVAL-F", ["-3.125E-2"], 0),
            ("TEST-NUMVAL-F", ["1E2"], 3),
            ("TEST-NUMVAL-F", ["1e+2"], 0),
            ("TEST-NUMVAL-F", ["1 E+2"], 0),
            ("TEST-NUMVAL-F", ["1.2E+"], 6),
            ("TEST-NUMVAL-F", ["1.2E+12345"], 10),
            ("TEST-NUMVAL-F", ["1E +2"], 0),
            ("TEST-NUMVAL-F", ["1E+ 2"], 0),
            ("TEST-NUMVAL-F", ["1E"], 3),
            ("TEST-NUMVAL-F", ["E+2"], 1),
            ("TEST-NUMVAL-F", ["1.2.3E+2"], 4),
            ("TEST-NUMVAL-F", ["1E+2X"], 5),
            ("TEST-NUMVAL-F", ["1E+00002"], 8),
            ("TEST-NUMVAL-C", ["$12.30"], 0),
            ("TEST-NUMVAL-C", ["$12.30CR"], 0),
            ("TEST-NUMVAL-C", ["EUR12.30", "EUR"], 2),
            ("TEST-NUMVAL-C", ["12.30 EUR", "EUR"], 7),
            ("TEST-NUMVAL-C", ["USD12.30", "$"], 1),
            ("TEST-NUMVAL-C", ["**12", "**"], 1),
            ("TEST-NUMVAL-C", ["E12.30", "E"], 0),
            ("TEST-NUMVAL-C", ["12.30$"], 6),
            ("TEST-NUMVAL-C", ["12,345.67"], 0),
        ]
        body = []
        expected = []
        for index, (name, arguments, position) in enumerate(cases):
            args = ", ".join(quoted(argument) for argument in arguments)
            body.append(f'display "{index}:" function {name}({args})')
            expected.append(f"{index}:{position:09d}\n")
        self.assert_matches(program("\n".join(body)), "".join(expected))

    def test_numval_f_conversion_does_not_reuse_the_validation_result(self):
        cases = [
            ("1E2", "+000000100.000000"),
            ("1x2E+1", "+000000120.000000"),
            ("1.2.3E+1", "+000000012.300000"),
            ("-1.25E+2", "-000000125.000000"),
            ("1.25E-2", "+000000000.012500"),
            ("1e+2", "+000000100.000000"),
            ("  +  123.45  ", "+000000123.450000"),
            ("123-", "-000000123.000000"),
            ("1E+", "+000000001.000000"),
            ("X", "+000000000.000000"),
        ]
        body = []
        expected = []
        for index, (text, result) in enumerate(cases):
            body.extend([f"move function numval-f({quoted(text)}) to amount-a",
                         f'display "{index}:" amount-a'])
            expected.append(f"{index}:{result}\n")
        self.assert_matches(program("\n".join(body), "01 amount-a pic s9(9)v9(6)."), "".join(expected))

    def test_decimal_comma_and_module_currency_control_validation(self):
        configuration = ("environment division. configuration section.\n"
                         'special-names. currency sign is "W" decimal-point is comma.\n')
        body = ('display function test-numval("12,30") ":" function test-numval("12.30")\n'
                'display function test-numval-c("W1.234,50") ":" function test-numval-c("$1.234,50")\n'
                'display function test-numval-c("E12,30", "E") ":" '
                'function test-numval-c("EUR12,30", "EUR")\n'
                'display function test-numval-f("1,25E+2") ":" function test-numval-f("1.25E+2")\n'
                'move function numval-f("1,25E-2") to amount-a\ndisplay amount-a')
        expected = ("000000000:000000003\n000000000:000000001\n000000000:000000002\n"
                    "000000000:000000002\n+000000000,012500\n")
        self.assert_matches(program(body, "01 amount-a pic s9(9)v9(6).", configuration), expected)

    def test_numeric_group_reference_modified_and_raw_byte_operands(self):
        storage = ('01 digits-a pic 99 value 12.\n01 signed-a pic s99 value -12.\n'
                   '01 group-a. 05 prefix-a pic xx value "12". 05 bad-a pic x value "X".\n'
                   '01 text-a pic x(7) value "??1E+2!".')
        body = ('display "NUMBER:" function test-numval(digits-a) ":" function numval-f(digits-a)\n'
                'display "LITERAL:" function test-numval(12) ":" function numval-f(12)\n'
                'display "LEXICAL:" function test-numval(-12.30) ":" function numval-f(-12.30)\n'
                '    ":" function test-numval(+0012.30) ":" function numval-f(+0012.30)\n'
                'display "SIGNED:" function test-numval(signed-a) ":" function numval-f(signed-a)\n'
                'display "GROUP:" function test-numval(group-a) ":" function test-numval(group-a(1:2))\n'
                'display "BYTES:" function test-numval(x"31320033") ":" function test-numval-f(x"3145FF32")\n'
                'display "SLICE:" function test-numval-f(text-a(3:4)) ":" function numval-f(text-a(3:4))\n'
                'display "CURRENCY:" function test-numval-c("1", 12)')
        expected = ("NUMBER:000000000:000000012\nLITERAL:000000000:000000012\n"
                    "LEXICAL:000000000:-000001230:000000000:000001230\n"
                    "SIGNED:000000002:000000001\nGROUP:000000003:000000000\n"
                    "BYTES:000000003:000000003\nSLICE:000000000:000000100\nCURRENCY:000000001\n")
        self.assert_matches(program(body, storage), expected)


if __name__ == "__main__":
    unittest.main()
