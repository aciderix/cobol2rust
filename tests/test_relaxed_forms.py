"""Forms cobc 3.2 accepts in real programs: optional headers and divisions,
level 88 of a group with figurative values, EXIT PERFORM and PERFORM UNTIL EXIT."""
from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


class ParseTests(unittest.TestCase):
    def test_select_needs_its_file_control_header(self):
        # cobc: "FILE-CONTROL header missing" is an error.
        with self.assertRaises(CobolError):
            Parser("identification division.\nprogram-id. a.\nenvironment division.\ninput-output section.\n"
                   "    select f assign to 'f'.\ndata division.\nfile section.\nfd f.\n01 r pic x.\n"
                   "procedure division.\n    stop run.\n").parse()

    def test_exit_perform_only_inside_an_inline_perform(self):
        base = "identification division.\nprogram-id. a.\nprocedure division.\n"
        for body in ("    exit perform.\n", "    perform p.\n    stop run.\np.\n    exit perform cycle.\n"):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(base + body).parse()
        Parser(base + "    perform until exit\n        exit perform\n    end-perform.\n").parse()

    def test_group_condition_takes_its_size_after_layout(self):
        program = Parser("identification division.\nprogram-id. a.\ndata division.\nworking-storage section.\n"
                         "01 g.\n   88 g-high value high-values.\n   88 g-stars value all '*'.\n"
                         "   02 a pic x(3).\n   02 b pic 9(2).\nprocedure division.\n    stop run.\n").parse()
        self.assertEqual(program.conditions["G.G-HIGH"].values[0][0].text, "\xff" * 5)
        self.assertEqual(program.conditions["G.G-STARS"].values[0][0].text, "*****")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NativeTests(unittest.TestCase):
    def check(self, name, **options):
        data = FIXTURES / f"{name}.data"
        report = verify(FIXTURES / f"{name}.cob", fmt="free", data_dir=data if data.is_dir() else None, **options)
        self.assertTrue(report["match"], report)
        return report

    def test_optional_headers_and_divisions(self):
        for name in ("no_identification_header", "no_procedure_division", "empty_input_output"):
            with self.subTest(name=name):
                self.check(name)

    def test_group_condition_with_figurative_values(self):
        self.check("group_condition_figurative")

    def test_exit_perform_forms(self):
        self.check("exit_perform")


if __name__ == "__main__":
    unittest.main()
