from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_nested_programs import unit


def source(fd="fd f global.", select='select optional f assign to "F.TXT".', working="",
           declaratives="", body="call \"inner\".", inner="open input f. read f. close f.", nested=""):
    procedure = f"declaratives.\n{declaratives}\nend declaratives.\nmain-line section.\nm.\n" if declaratives else ""
    return ("identification division.\nprogram-id. outer.\nenvironment division.\ninput-output section.\n"
            f"file-control.\n    {select}\ndata division.\nfile section.\n{fd}\n01 r pic x(4).\n"
            f"working-storage section.\n01 n pic 9 value 0 global.\n{working}\nprocedure division.\n{procedure}"
            f"    {body}\n    stop run.\nidentification division.\nprogram-id. inner.\nprocedure division.\n"
            f"    {inner}\n    exit program.\n{nested}end program inner.\nend program outer.\n")


GLOBAL_USE = "u section.\n    use global after error procedure on input.\nu-1.\n    add 1 to n."


class ParseTests(unittest.TestCase):
    def test_fd_clauses_and_records(self):
        parsed = Parser(source(fd="fd f is external.", inner="continue.")).parse()
        spec, record = parsed.files["F"], parsed.fields["R"]
        self.assertTrue(spec.external and not spec.is_global)
        self.assertEqual((record.fd_file, record.fd_external), ("F", True))
        parsed = Parser(source()).parse()
        self.assertTrue(parsed.files["F"].is_global and parsed.fields["R"].is_global)
        # The contained program sees the file and its record under the
        # names of global_items' copies.
        inner = parsed.nested[0]
        self.assertEqual((inner.files["F"].global_owner, inner.files["F"].record), ("outer", "^outer^R"))

    def test_use_global_inherited_by_open_mode(self):
        parsed = Parser(source(declaratives=GLOBAL_USE)).parse()
        self.assertEqual(parsed.global_uses, {"INPUT": "U"})
        self.assertEqual(parsed.nested[0].inherited_uses, {"INPUT": ("outer", "U")})
        # A USE of its own for the mode, even not GLOBAL, wins.
        own = ("identification division.\nprogram-id. inner.\nprocedure division.\ndeclaratives.\n"
               "v section.\n    use after error procedure on input.\nv-1.\n    continue.\nend declaratives.\n"
               "w section.\nw-1.\n")
        parsed = Parser(source(declaratives=GLOBAL_USE).replace(
            "identification division.\nprogram-id. inner.\nprocedure division.\n", own)).parse()
        self.assertEqual(parsed.nested[0].inherited_uses, {})

    def test_unmodelled_forms_are_refused(self):
        cases = [
            source(declaratives="u section.\n    use global after error procedure on f.\nu-1.\n    continue."),
            source(declaratives=GLOBAL_USE + "\n    goback."),
            source(declaratives=GLOBAL_USE, body="alter p1 to proceed to p2. go to p1.\np1. go to p2.\np2. continue."),
            source(select='select optional f assign to "F.TXT" file status is fs.', working="01 fs pic xx."),
            source(fd="fd f.\n01 q pic x(4) global."),
            source(fd="sd f global.", select='select f assign to "F.TXT".', inner="continue."),
            source(fd="fd f external global."),
            source(fd="fd f external linage 10."),
            # The cobc.c walk would take the GLOBAL USE of aunt, which does
            # not contain niece.
            source(inner="call \"niece\".", nested=(
                "identification division.\nprogram-id. niece.\nprocedure division.\n"
                "    open input f. read f.\n    exit program.\nend program niece.\n")).replace(
                "identification division.\nprogram-id. inner.",
                "identification division.\nprogram-id. aunt.\nprocedure division.\ndeclaratives.\n"
                + GLOBAL_USE + "\nend declaratives.\nmain-a section.\na.\n    exit program.\nend program aunt.\n"
                "identification division.\nprogram-id. inner."),
        ]
        for text in cases:
            with self.subTest(text=text[text.index("file section"):][:160]), self.assertRaises(CobolError):
                unit(text)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NativeTests(unittest.TestCase):
    def fixture(self, name):
        report = verify(ROOT / "tests" / "fixtures" / f"{name}.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertTrue(report["files_match"], report)
        return report

    def test_external_file_shared_by_name(self):
        report = self.fixture("external_files")
        # Each program has its FILE STATUS; CANCEL closes the file it left open.
        self.assertIn("sub close 00\nmain fs 00\n", report["cobol_stdout"])
        self.assertIn("after cancel 47\n", report["cobol_stdout"])
        # The first program's ASSIGN names the file.
        self.assertEqual(list(report["cobol_files"]), ["SHARED.TXT"])

    def test_global_file_and_use_global(self):
        report = self.fixture("global_files")
        self.assertIn("back 1 1 [SECOND  ] [SEC]\n", report["cobol_stdout"])
        self.assertIn("child-2 global output handler 2 2\n", report["cobol_stdout"])
        self.assertTrue(report["cobol_stdout"].endswith("main output handler\n"))

    def test_initial_program_is_cancelled_when_it_returns(self):
        report = self.fixture("initial_program")
        self.assertEqual(report["cobol_stdout"].count("init-sub 1 INIT"), 4)
        self.assertIn("keep-sub 3\n", report["cobol_stdout"])
        # The implicit CANCEL closes the file left open by each CALL.
        self.assertEqual(report["cobol_files"]["INITIAL.TXT"]["bytes"], 32)


if __name__ == "__main__":
    unittest.main()
