from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, FloatLiteralToken, Parser, lex
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body, storage=""):
    return ("identification division.\nprogram-id. float-case.\ndata division.\nworking-storage section.\n"
            f"01 x comp-1 value 1.5.\n01 y comp-2.\n01 n pic s9(5)v99.\n01 a pic x(4).\n{storage}"
            f"procedure division.\n{body}\nstop run.\n")


def expression(text):
    return [s for s in Parser(program(f"compute n = {text}.")).parse().entry if s.op == "compute"][0].args[0]


class FloatDeclarationTests(unittest.TestCase):
    def test_usages_and_attributes(self):
        fields = Parser(program("display x.", "01 f float-short.\n01 g usage computational-2.\n")).parse().fields
        self.assertEqual([(fields[k].usage, fields[k].size, fields[k].digits, fields[k].scale) for k in ("X", "Y", "F", "G")],
                         [("COMP-1", 4, 15, 8), ("COMP-2", 8, 34, 17), ("COMP-1", 4, 15, 8), ("COMP-2", 8, 34, 17)])

    def test_cobc_refusals(self):
        for storage, message in [("01 p pic 9 comp-1.\n", "cannot have PICTURE clause"),
                                 ("01 q comp-2 value 'a'.\n", "VALUE non numérique"),
                                 ("01 r pic x value 1.5E3.\n", "VALUE")]:
            with self.subTest(storage=storage), self.assertRaisesRegex(CobolError, message):
                Parser(program("display x.", storage)).parse()


class FloatingLiteralTests(unittest.TestCase):
    def test_scan_floating_numeric_values(self):
        tokens = lex("1.0E7 2.1E0 .5E+2 1.50E-2 1.E3")[:-1]
        self.assertTrue(all(isinstance(t, FloatLiteralToken) for t in tokens))
        self.assertEqual([t.text for t in tokens], ["10000000", "2.1", "50", "0.0150", "1000"])

    def test_scan_floating_numeric_errors(self):
        for text, message in [("1.5E3.2", "decimal point"), ("1.5E12345", "more than 4 digits"),
                              ("0.0E1", "exponent of 0 must be 0"), ("1." + "1" * 36 + "E1", "more than 36 digits")]:
            with self.subTest(text=text), self.assertRaisesRegex(CobolError, message):
                lex(text)

    def test_only_numeric_uses(self):
        Parser(program("move 1.5E3 to n x. compute n = 1.5E3 / 7. if n > 1.5E-3 continue end-if.")).parse()
        for body in ("display 1.5E3.", "move 1.5E3 to a.", "move 1.5E3 to n a."):
            with self.subTest(body=body), self.assertRaisesRegex(CobolError, "littéral flottant"):
                Parser(program(body)).parse()


class ConstantFoldingTests(unittest.TestCase):
    def show(self, e):
        if e.op == "number":
            return e.args[0]
        if e.op == "var":
            return e.args[0].name
        return "(" + " ".join([e.op] + [self.show(a) for a in e.args]) + ")"

    def test_cb_build_binary_op_folding(self):
        cases = {"3 * 2": "6", "1.5 * 4": "6", "7 / 2": "(/ 7 2)", "6.0 / 2": "3", "1.0 / 3": "(/ 1.0 3)",
                 "n * 1": "N", "n / 1": "N", "n * 0": "0", "n * -1": "(* N (unary- 1))", "2 ** 3": "8",
                 "n + 0": "(+ N 0)", "2 - 5": "(unary- 3)", "1.5 - 2.25": "(unary- 0.75)"}
        for text, folded in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.show(expression(text)), folded)

    def test_zero_adjusted_float_comparison_is_refused(self):
        with self.assertRaisesRegex(CobolError, "rel_bin_op"):
            Emitter(Parser(program("if x + 0 = 1.5 continue end-if.")).parse()).generate()


class FloatEmitterTests(unittest.TestCase):
    def test_alphanumeric_moves_are_refused(self):
        for body, message in [("move x to a.", "invalide, comme pour GnuCOBOL"),
                              ("move a to x.", "alphanumérique vers un flottant"),
                              ("move 'abc' to y.", "alphanumérique vers un flottant")]:
            with self.subTest(body=body), self.assertRaisesRegex(CobolError, message):
                Emitter(Parser(program(body)).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class FloatNativeTests(unittest.TestCase):
    def test_float_binary_matches_native(self):
        # cob_decimal_set_double / get_double (truncation), %G display,
        # cob_cmp_float tolerance against cob_cmp_llint and cob_decimal_cmp,
        # SIZE ERROR on overflow, constant folding of x * 1.
        report = verify(ROOT / "tests" / "fixtures" / "float_binary.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        self.assertTrue(stdout.startswith("values 123.456|0.09999999999999999|0|0\n"))
        self.assertIn("tolerance eq\nfolded eq\ndecimal ne\nllint ne\nfloat eq\nright field ne\nleft field eq\n", stdout)
        self.assertIn("size 127 1.7014118E+38\nno size error 0\n", stdout)


if __name__ == "__main__":
    unittest.main()
