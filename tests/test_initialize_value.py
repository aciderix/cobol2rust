from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body):
    return ("identification division.\nprogram-id. init-case.\ndata division.\nworking-storage section.\n"
            "01 g.\n 05 a pic x value 'a'.\n 05 n pic 9.\n 05 t occurs 2.\n  10 v pic x value 'v'.\n"
            f"procedure division.\n{body}\nstop run.\n")


class InitializeValueFrontendTests(unittest.TestCase):
    def test_value_and_default_phrases(self):
        # cb_emit_initialize: DEFAULT applies without VALUE and REPLACING.
        cases = {"initialize g.": (None, True), "initialize g default.": (None, True),
                 "initialize g all value.": ("ALL", False), "initialize g numeric to value.": ("NUMERIC", False),
                 "initialize g all to value then to default.": ("ALL", True),
                 "initialize g replacing numeric by 1 then default.": (None, True),
                 "initialize g replacing numeric by 1.": (None, False)}
        for body, expected in cases.items():
            with self.subTest(body=body):
                stmt = next(s for s in Parser(program(body)).parse().entry if s.op == "initialize")
                self.assertEqual(stmt.args[3:], expected)
        rust = Emitter(Parser(program("initialize g all to value.")).parse()).generate()[0]
        self.assertIn("storage_runtime::propagate_table(", rust)

    def test_reference_modification_is_refused(self):
        with self.assertRaises(CobolError):
            Emitter(Parser(program("initialize g (1:2) all to value.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class InitializeValueNativeTests(unittest.TestCase):
    def test_value_default_and_replacing_match_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "initialize_value.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        # The category of "category TO VALUE" is not checked by codegen.c.
        self.assertIn("2 [abc012fl## 1.50\x00}GV]\n", stdout)
        # propagate_table copies the whole first occurrence, untouched bytes included.
        self.assertIn("6 [vvx2x3vvx2x3vvx2x3]\n", stdout)


if __name__ == "__main__":
    unittest.main()
