from __future__ import annotations

import unittest

from cobol2rust import frontend
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(cd="cd c for input.\n01 c-rec pic x(87).", body="receive c message into w no data continue.",
            declaratives=""):
    return ("identification division.\nprogram-id. comm.\nenvironment division.\nconfiguration section.\n"
            "source-computer. linux with debugging mode.\ndata division.\nworking-storage section.\n"
            f"01 w pic x(8).\ncommunication section.\n{cd}\nprocedure division.\n{declaratives}"
            f"main section.\nm.\n    {body}\n    stop run.\n")


class CommunicationTests(unittest.TestCase):
    def setUp(self):
        self.previous, frontend.STD = frontend.STD, "cobol85"

    def tearDown(self):
        frontend.STD = self.previous

    def test_cd_records_and_statements_generate_nothing(self):
        cd = "cd c for initial input.\n01 c-rec.\n    02 q pic x(12) value \"QUEUE\".\n01 c-alt pic x(12).\ncd o for output.\n01 o-rec pic x(4)."
        body = ("enable input terminal c with key \"K\". disable output o. purge o.\n"
                "    receive c segment into w with data move \"x\" to w no data move \"y\" to w end-receive.\n"
                "    send o from w with emi before advancing 2 lines replacing line. send o from w.\n"
                "    accept c message count.")
        parsed = Parser(program(cd, body)).parse()
        self.assertEqual([s.op for s in parsed.paragraphs["M"] if s.op != "sentence_end"][:7], ["continue"] * 7)
        record, alternate = parsed.fields["C-REC"], parsed.fields["C-ALT"]
        self.assertEqual((alternate.redefines, alternate.offset), ("C-REC", record.offset))
        # cobc never initializes the static CD storage.
        self.assertFalse(parsed.fields["C-REC.Q"].explicit_value)

    def test_debugging_on_a_cd_sizes_debug_contents(self):
        declaratives = "declaratives.\nd section.\n    use for debugging on c.\nd-1.\n    continue.\nend declaratives.\n"
        parsed = Parser(program(declaratives=declaratives, body="display function length(debug-contents).")).parse()
        contents = next(f for f in parsed.fields.values() if f.label == "DEBUG-CONTENTS")
        self.assertEqual((contents.size, contents.parse_size), (87, 30))

    def test_unmodelled_or_invalid_forms_are_refused(self):
        declaratives = "declaratives.\nd section.\n    use for debugging on c c.\nd-1.\n    continue.\nend declaratives.\n"
        cases = [
            program(cd="cd c for input symbolic queue is w.\n01 c-rec pic x(87)."),
            program(cd="cd c for input."),
            program(cd="cd c for initial output.\n01 c-rec pic x(87)."),
            program(declaratives=declaratives),
            # cobc checks constant positions against the size of 30 it parses with.
            program(declaratives=declaratives.replace("on c c.", "on c."), body="display debug-contents(1:40)."),
            program(body="receive w message into w."),
        ]
        for text in cases:
            with self.subTest(text=text[text.index("communication"):][:120]), self.assertRaises(CobolError):
                Parser(text).parse()
        # cb_verify (CB_UNCONFORMABLE) outside -std=cobol85.
        frontend.STD = "default"
        with self.assertRaises(CobolError):
            Parser(program()).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class CommunicationNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "communication.cob", fmt="free", std="cobol85",
                        runtime_env={"COB_SET_DEBUG": "Y"})
        self.assertTrue(report["match"], report)
        # LENGTH is folded while DEBUG-CONTENTS still has its default size.
        self.assertTrue(report["cobol_stdout"].startswith("len 30 86 87\n"))
        self.assertIn("after receive [WORK", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
