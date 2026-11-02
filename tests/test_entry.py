"""ENTRY (emit_entry, output_entry_function), modules run as cobcrun runs
them, LINKAGE items without an address, LENGTH OF (cb_build_length)."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from cobol2rust.cli import convert
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, build_rust, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def subprogram(body, linkage="01 a pic x(4). 01 b pic x(4).", using="a"):
    return ("identification division. program-id. sub.\ndata division. linkage section.\n" + linkage +
            f"\nprocedure division using {using}.\n" + body)


class EntryFrontendTests(unittest.TestCase):
    def test_entry_records_its_parameters(self):
        program = Parser(subprogram('display a. entry "ALT" using b. display b. goback.')).parse()
        self.assertEqual([(name, using) for name, using in program.entries], [("ALT", ["B"])])

    def test_invalid_entries_are_refused_like_cobc(self):
        cases = [subprogram('entry "sub". goback.'),           # the program-id as written
                 subprogram('entry "ALT". entry "ALT". goback.'),
                 subprogram('entry alt. goback.'),             # not a literal
                 subprogram('entry "ALT" using c. goback.')]   # not a LINKAGE item
        for source in cases:
            with self.subTest(source=source), self.assertRaises(CobolError):
                Parser(source).parse()

    def test_linkage_items_outside_using_are_accepted(self):
        Emitter(Parser(subprogram("goback.")).parse()).generate()


@unittest.skipUnless(find_tool("cargo"), "Cargo required")
class EntryRuntimeTests(unittest.TestCase):
    def test_item_not_passed_is_a_named_stop(self):
        # cobcrun calls the module without arguments: GnuCOBOL reads an
        # undetermined address; the Rust runtime stops on the first access.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.cob"
            source.write_text(subprogram('display "before" display a goback.', using="a"), encoding="utf-8")
            convert(source, root / "rust")
            result = subprocess.run([str(build_rust(root / "rust"))], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 70)
        self.assertEqual(result.stdout, b"before\n")
        self.assertIn(b"item without storage (LINKAGE item not passed", result.stderr)


@unittest.skipUnless(find_tool("cobc") and find_tool("cobcrun") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class EntryNativeTests(unittest.TestCase):
    def test_entry_points_and_their_loading(self):
        for name in ("entry_statement", "entry_not_loaded"):
            with self.subTest(name=name):
                report = verify(FIXTURES / f"{name}.cob", fmt="free", call_paths=[FIXTURES / "entry_calls"])
                self.assertTrue(report["match"], report)

    def test_module_runs_without_arguments(self):
        report = verify(FIXTURES / "module_using.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_exit"], 3)

    def test_length_of(self):
        report = verify(FIXTURES / "length_of.cob", fmt="free")
        self.assertTrue(report["match"], report)


if __name__ == "__main__":
    unittest.main()
