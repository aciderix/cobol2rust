from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.cli import emit_unit
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def unit(text: str):
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "nested.cob"
        source.write_text(text, encoding="utf-8")
        return emit_unit(source, "free")


MAIN = """identification division.
program-id. outer.
data division.
working-storage section.
01 g global pic 9 value 1.
01 h pic 9 value 2.
procedure division.
    call "{first}".
    stop run.
identification division.
program-id. first-in{common}.
data division.
working-storage section.
01 h pic 9 value 3.
procedure division.
    move h to g.
    call "{second}".
    goback.
end program first-in.
identification division.
program-id. second-in{common2}.
procedure division.
    {body}
    goback.
end program second-in.
end program outer.
"""


def fill(**values):
    values.setdefault("common2", "")
    return MAIN.format(**values)


class NestedProgramTests(unittest.TestCase):
    def test_contained_programs_and_their_global_items(self):
        main = Parser(fill(first="FIRST-IN", common="", second="X", body="continue.")).parse()
        self.assertEqual([p.entry_name for p in main.nested], ["first-in", "second-in"])
        self.assertTrue(all(p.parent == "outer" for p in main.nested))
        first = main.nested[0]
        # The program's own H hides nothing global; G comes from OUTER.
        self.assertEqual(first.fields["H"].label, "H")
        self.assertEqual(first.fields["^outer^G"].global_owner, "outer")

    def test_call_visibility_follows_contained_and_common_programs(self):
        # first-in may call its sibling second-in only if second-in is COMMON.
        unit(fill(first="first-in", common="", second="second-in", common2=" is common", body="continue."))
        with self.assertRaises(CobolError):
            unit(fill(first="first-in", common="", second="second-in", body="continue."))

    def test_unmodelled_forms_are_refused(self):
        sources = [
            fill(first="first-in", common="", second="X", body="continue.").replace(
                "01 g global pic 9 value 1.", "01 g external pic 9 value 1."),
        ]
        for text in sources:
            with self.subTest(text=text[:80]), self.assertRaises(CobolError):
                unit(text)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NestedProgramNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "nested_programs.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertIn("in c 16\nafter b 16 b-in\nafter sibling 07 sibl\n", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
