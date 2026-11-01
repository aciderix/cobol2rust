from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(data, body):
    return ("identification division.\nprogram-id. fns.\ndata division.\nworking-storage section.\n"
            f"01 p usage pointer.\n01 x pic x(4).\n{data}procedure division.\n{body}\nstop run.\n")


class ModuleFunctionTests(unittest.TestCase):
    def test_content_functions_require_a_data_pointer(self):
        # cb_build_intrinsic: CB_CATEGORY_DATA_POINTER.
        for body in ("display function content-length (x).", "display function content-of (x).",
                     "display function content-of (p, 1, 2)."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program("", body)).parse()

    def test_module_date_and_time_are_compile_time_fields(self):
        rust, _ = Emitter(Parser(program("", "display function module-date function module-time.")).parse()).generate()
        self.assertRegex(rust, r'display_field\(Value::number\("\d{8}"\), 8\)')
        self.assertRegex(rust, r'display_field\(Value::number\("\d{6}"\), 6\)')

    def test_exception_status_beside_a_raising_function_is_refused(self):
        # cob_display's arguments: an evaluation order C does not specify.
        for body in ("display function content-of (p) function exception-status.",
                     "display function concatenate (function exception-status, function content-of (p)).",
                     "display function combined-datetime (1, 1) function exception-status."):
            with self.subTest(body=body), self.assertRaisesRegex(CobolError, "ordre d'évaluation"):
                Emitter(Parser(program("", body)).parse()).generate()
        Emitter(Parser(program("", "display function module-id function exception-status.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ModuleFunctionNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "module_functions.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertEqual(lines[:3], ["000000001 -000000001 000000000 -000000001 000000000", "987.003456", "000001.864"])
        self.assertIn("000000005 [HELLO] [HEL] [ELL]", lines)
        self.assertIn("INNER [module-functions]", lines)
        self.assertIn("clock ok", lines)


if __name__ == "__main__":
    unittest.main()
