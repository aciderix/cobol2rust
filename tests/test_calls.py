from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.cli import emit_unit
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program

FIXTURES = ROOT / "tests" / "fixtures"


def subprogram(name, linkage, using, body):
    return (f"identification division.\nprogram-id. {name}.\ndata division.\n"
            f"linkage section.\n{linkage}\nprocedure division using {using}.\n{body}\n")


class CallTests(unittest.TestCase):
    def write(self, directory, name, text):
        path = Path(directory) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_run_unit_binds_linkage_to_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            main = self.write(directory, "main.cob", program("01 n pic 9.", 'call "SUBA" using n. stop run.'))
            self.write(directory, "SUBA.cob", subprogram("SUBA", "01 l pic 9.", "l", "add 1 to l. goback."))
            _, _, _, subprograms, rust, _ = emit_unit(main, "free", (), [directory])
            self.assertEqual([sub.entry_name for _, sub, _, _ in subprograms], ["SUBA"])
            self.assertIn("storage_runtime::rebind(&arguments[0], 0,", rust)
            self.assertIn('match unit.call("SUBA"', rust)

    def test_literal_not_found_takes_exception_branch(self):
        rust = Emitter(Parser(program("01 n pic 9.", 'call "ABSENT" on exception move 1 to n end-call. stop run.')).parse(),
                       called=["MAIN"]).generate()[0]
        self.assertNotIn("unit.call", rust)
        for name in ("lowercase", "SYSTEM", "CBL_TOUPPER"):
            with self.subTest(name=name), self.assertRaises(CobolError):
                Emitter(Parser(program("01 n pic 9.", f'call "{name}". stop run.')).parse()).generate()

    def test_refusals(self):
        cases = [
            # GnuCOBOL gives this NOT ON EXCEPTION to the DISPLAY, not to the CALL.
            program("01 n pic 9.", 'call "X" on exception display "A" not on exception display "B" end-call. stop run.'),
            subprogram("S", "01 a pic 9 value 1.", "a", "goback."),
            program("01 n pic 9.", 'call "X" using by value n. stop run.'),
            program("01 n pic 9.", 'call "X" returning n. stop run.'),
        ]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(CobolError):
                Parser(text).parse()

    def test_sibling_programs_resolve_before_call_path(self):
        text = (program("01 n pic 9.", 'call "SIB" using n. stop run.').replace("\nprocedure", "\nprocedure", 1)
                + "end program numeric-move-case.\n" + subprogram("SIB", "01 l pic 9.", "l", "add 1 to l. goback.")
                + "end program SIB.\n")
        with tempfile.TemporaryDirectory() as directory:
            main = self.write(directory, "main.cob", text)
            # A same-named source in the call path is not used: the sibling wins.
            self.write(directory, "SIB.cob", "not cobol")
            _, _, _, subprograms, rust, _ = emit_unit(main, "free", (), [directory])
            self.assertEqual([(path, sub.entry_name) for path, sub, _, _ in subprograms], [(main, "SIB")])
            self.assertIn("Program1", rust)
        self.assertEqual([p.entry_name for p in Parser(text).parse().siblings], ["SIB"])
        with self.assertRaises(CobolError):
            Parser(text.replace("end program SIB.", "end program SIB.\n" + text.split("end program")[0])).parse()

    def test_main_program_with_using_is_a_module(self):
        # cobc -x refuses it; it runs as cobcrun runs it (tests/test_entry.py),
        # a LINKAGE item outside USING has no address.
        rust, _ = Emitter(Parser(subprogram("S", "01 a pic 9. 01 b pic 9.", "a", "goback.")).parse()).generate()
        self.assertIn("program.call(&mut unit, Vec::new());", rust)
        self.assertIn("storage_runtime::unbind", rust)

    def test_program_id_must_match_called_name(self):
        with tempfile.TemporaryDirectory() as directory:
            main = self.write(directory, "main.cob", program("01 n pic 9.", 'call "SUBA" using n. stop run.'))
            self.write(directory, "SUBA.cob", subprogram("OTHER", "01 l pic 9.", "l", "goback."))
            with self.assertRaises(CobolError):
                emit_unit(main, "free", (), [directory])


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class CallNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol_modules(self):
        report = verify(FIXTURES / "call_main.cob", fmt="fixed", call_paths=[FIXTURES / "calls"])
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # BY CONTENT leaves the caller's item unchanged; the sub keeps its state.
        self.assertIn("2 015 BETA   -00009.50", lines)
        # CANCEL restores the initial WORKING-STORAGE of the called program.
        self.assertIn("SUB 01 017 BETA  ", lines)
        self.assertIn("DYN MISSING", lines)
        self.assertNotIn("NEVER", lines)

    def test_sibling_programs_match_gnucobol(self):
        report = verify(FIXTURES / "sibling_programs.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertIn("after cancel 0040", report["cobol_stdout"].splitlines())


if __name__ == "__main__":
    unittest.main()
