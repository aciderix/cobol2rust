from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_files import file_program


def declarative_program(declaratives: str, body: str = "main section. go-on. stop run."):
    return file_program("declaratives. " + declaratives + " end declaratives. " + body)


class DeclarativeTests(unittest.TestCase):
    def test_use_sections_by_file_and_mode(self):
        parsed = Parser(declarative_program(
            "file-errors section. use after standard error procedure on f. handle-f. display 'F'. "
            "input-errors section. use after exception procedure input. other-p. continue. "
            "extend-errors section. use after error procedure on extend.")).parse()
        self.assertEqual(parsed.file_declaratives, {"F": "FILE-ERRORS"})
        self.assertEqual(parsed.mode_declaratives, {"INPUT": "INPUT-ERRORS", "EXTEND": "EXTEND-ERRORS"})
        # Execution starts after END DECLARATIVES.
        self.assertEqual(parsed.blocks[parsed.main_block].section, None)
        self.assertGreater(parsed.main_block, parsed.sections["EXTEND-ERRORS"][0])
        Emitter(parsed).generate()

    def test_unmodelled_or_malformed_declaratives_are_refused(self):
        cases = [
            "s section. use for debugging.",
            "s section. use global after error procedure on f.",
            "s section. use after error procedure on f. t section. use after error procedure on f.",
            "s section. use after error procedure input. t section. use after error procedure input.",
            "s section. use after error procedure on unknown-file.",
            "s section. use after procedure on f.",
            "display 'x'. s section. use after error procedure on f.",
        ]
        for declaratives in cases:
            with self.subTest(declaratives=declaratives), self.assertRaises(CobolError):
                Parser(declarative_program(declaratives)).parse()
        with self.assertRaises(CobolError):
            Parser(file_program("declaratives. s section. use after error procedure on f. stop run.")).parse()
        with self.assertRaises(CobolError):
            Parser(file_program("main section. use after error procedure on f. stop run.")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class DeclarativeNativeTests(unittest.TestCase):
    def test_fixture_matches_native_dispatch(self):
        report = verify(ROOT / "tests" / "fixtures" / "declaratives.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # 46 after end of file is not AT END: the USE procedure runs instead.
        self.assertIn("DATA-USE 46 02", lines)
        self.assertNotIn("AT-END 46", "\n".join(lines))
        # The first file of OPEN fails alone; the second is still opened.
        self.assertIn("MULTI 35 00", lines)
        self.assertEqual(lines[lines.index("BARE-41") + 1], "INPUT-USE 35 07")
        self.assertEqual(lines[-1], "CALLS 07")


if __name__ == "__main__":
    unittest.main()
