from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from cobol2rust import frontend
from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, find_tool
from cobol2rust.verification import verify


def program(body, storage=""):
    return ("identification division.\nprogram-id. exception-case.\ndata division.\nworking-storage section.\n"
            f"01 x pic 9 value 4.\n01 y pic 9.\n{storage}\nprocedure division.\n{body}\nstop run.\n")


class ExceptionFrontendTests(unittest.TestCase):
    def test_functions_and_set_last_exception(self):
        parsed = Parser(program("display function exception-status function exception-location\n"
                                "function exception-statement function exception-file.\n"
                                "set last exception to off.")).parse()
        self.assertTrue(parsed.uses_exceptions)
        self.assertIn("exception_off", [s.op for s in parsed.entry])
        rust = Emitter(parsed).generate()[0]
        self.assertIn("runtime::exception::status()", rust)
        self.assertIn("runtime::exception::off();", rust)

    def test_untracked_programs_are_unchanged(self):
        rust = Emitter(Parser(program("compute y = function sqrt (x).")).parse()).generate()[0]
        self.assertNotIn("runtime::exception::unknown", rust)
        self.assertNotIn("runtime::exception::module", rust)

    def test_location_and_statement_need_the_default_profile(self):
        # -debug sets module->statement and the section and paragraph names.
        previous = frontend.RUNTIME_CHECKS
        frontend.RUNTIME_CHECKS = True
        try:
            for name in ("exception-location", "exception-statement"):
                with self.subTest(name=name), self.assertRaisesRegex(CobolError, "contrôles d'exécution"):
                    Parser(program(f"display function {name}.")).parse()
            Parser(program("display function exception-status function exception-file.")).parse()
        finally:
            frontend.RUNTIME_CHECKS = previous


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ExceptionNativeTests(unittest.TestCase):
    def test_ported_exceptions_match_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "exceptions.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        # save_status: cob_error_file is the last file, shown while the last
        # exception is an I-O one.
        self.assertIn("[35missing]\nafter other file [00scratch]\n", stdout)
        self.assertIn("[EC-SIZE-TRUNCATION ", stdout)
        self.assertIn("mod [+00]\n[EC-ARGUMENT-FUNCTION ", stdout)
        self.assertTrue(stdout.endswith("not found\n[EC-PROGRAM-NOT-FOUND           ][exceptions; ; 0]"
                                        "[                               ][00]\n"))

    def test_recursive_call_with_on_exception_returns(self):
        # cob_module_global_enter: EC-PROGRAM-RECURSIVE-CALL and -1 for a CALL
        # with ON EXCEPTION; NOT ON EXCEPTION is skipped.
        report = verify(ROOT / "tests" / "fixtures" / "exception_recursive_call.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_exit"], 255)
        self.assertTrue(report["cobol_stdout"].startswith(
            "exception -000000001 EC-PROGRAM-RECURSIVE-CALL      \nafter -000000001 recursive-second; ; 0\n"))

    def test_unported_exceptions_are_named_stops(self):
        cases = [
            ("compute y = function sqrt (x). display function exception-status.", b"after FUNCTION SQRT"),
            ("compute y = x ** 1. display function exception-status.", b"after exponentiation"),
            ("compute z = 9. display function exception-status.", b"after arithmetic store into a binary"),
        ]
        for body, message in cases:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "case.cob"
                source.write_text(program(body, "01 z pic 9 comp-5."), encoding="utf-8")
                convert(source, root / "rust", fmt="free")
                result = subprocess.run([str(build_rust(root / "rust"))], capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 70, result)
                self.assertIn(message, result.stderr)


if __name__ == "__main__":
    unittest.main()
