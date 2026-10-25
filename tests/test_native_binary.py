"""COMP-5, BINARY-CHAR/SHORT/LONG/DOUBLE (real binary) and RETURN-CODE."""
from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(data, procedure="stop run."):
    return ("identification division.\nprogram-id. a.\ndata division.\nworking-storage section.\n"
            f"{data}\nprocedure division.\n    {procedure}\n")


class ParseTests(unittest.TestCase):
    def test_fixed_binary_usages_are_comp5(self):
        fields = Parser(program("01 c binary-char unsigned.\n01 s binary-short.\n01 l binary-long signed.\n"
                                "01 d binary-double.\n01 f pic s9(3)v9 comp-5.")).parse().fields
        self.assertEqual([(fields[k].usage, fields[k].digits, fields[k].signed, fields[k].size) for k in "CSLDF"],
                         [("COMP-5", 2, False, 1), ("COMP-5", 4, True, 2), ("COMP-5", 9, True, 4),
                          ("COMP-5", 18, True, 8), ("COMP-5", 4, True, 2)])
        with self.assertRaises(CobolError):
            Parser(program("01 l pic 9(4) binary-long.")).parse()

    def test_return_code_is_a_register_outside_the_program_storage(self):
        parsed = Parser(program("01 x pic x(3).", "move 4 to return-code stop run.")).parse()
        register = parsed.fields["RETURN-CODE"]
        self.assertTrue(register.register and register.is_global)
        self.assertEqual((register.usage, register.digits, register.size, parsed.memory_size), ("COMP-5", 9, 4, 3))

    def test_not_on_size_error_alone_on_comp5_is_refused(self):
        # cobc keeps a COMP-5 receiver only with ON SIZE ERROR (ex_handler).
        with self.assertRaises(CobolError):
            Emitter(Parser(program("01 x pic s9(4) comp-5.",
                                   "add 1 to x not on size error display 'ok' end-add stop run.")).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NativeTests(unittest.TestCase):
    def test_comp5_storage_arithmetic_and_display(self):
        report = verify(FIXTURES / "comp5.cob", fmt="free")
        self.assertTrue(report["match"], report)

    def test_return_code_through_calls_cancel_and_exit_status(self):
        report = verify(FIXTURES / "return_code.cob", fmt="free", call_paths=[FIXTURES / "return_code_calls"])
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_exit"], 300 % 256)

    def test_contained_program_shares_return_code(self):
        report = verify(FIXTURES / "return_code_nested.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_exit"], 23)


if __name__ == "__main__":
    unittest.main()
