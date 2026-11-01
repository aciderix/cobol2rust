from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser, load_source
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


class GlobalFileItemTests(unittest.TestCase):
    def test_file_items_are_hidden_from_contained_programs(self):
        # A FILE STATUS item not GLOBAL is shared (tests/test_global_files.py
        # no longer refuses it).
        text, _ = load_source(FIXTURES / "global_file_status.cob", [], "fixed")
        program = Parser(text).parse()
        hidden = [f for f in program.nested[0].fields.values() if getattr(f, "hidden", False)]
        self.assertEqual(sorted(f.label for f in hidden), ["FS", "KEYS", "RK"])
        changed = text.replace("READ REL-FILE", "DISPLAY FS READ REL-FILE")
        self.assertNotEqual(changed, text)
        with self.assertRaises(CobolError):
            Parser(changed).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class GlobalFileItemNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "global_file_status.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        self.assertIn("after missing 23 0009", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
