from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(targets, statements, data="01 x pic 99. 01 y pic 99. 01 t. 02 e pic x occurs 3 indexed by i."):
    return ("identification division.\nprogram-id. t.\nenvironment division.\nconfiguration section.\n"
            "source-computer. c with debugging mode.\ndata division. working-storage section.\n" + data +
            "\nprocedure division.\ndeclaratives. d section. use for debugging on " + targets +
            ". p. display debug-name. end declaratives.\nm section. a.\n" + statements + "\n stop run.\n")


def body(parsed):
    return [s for s in next(b for b in parsed.blocks if b.name == "A").body if s.op != "sentence_end"]


def checks(stmt):
    # DEBUG-NAME keeps the spelling of each name's first occurrence.
    return [(name, ref.name) for name, ref, _ in getattr(stmt, "debug_checks", [])]


class DebuggingItemTests(unittest.TestCase):
    def test_receiving_operands_and_all_references(self):
        entry = body(Parser(program("x all y", "move x to y. move y to x. add x y to x giving y. "
                                    "if y = 1 move 1 to x end-if. display x.")).parse())
        # x is debugged as a receiver only, y at every reference; each once.
        self.assertEqual([checks(s) for s in entry], [
            [("y", "Y")], [("y", "Y"), ("x", "X")], [("y", "Y")], [("y", "Y")], [], []])

    def test_subscripts_and_qualifiers_go_to_debug_name_and_subs(self):
        source = program("e c of b", "set i to 2. move 'Z' to e (i). move 'Q' to c of b.",
                         "01 t. 02 e pic x occurs 3 indexed by i. 01 b. 02 c pic x. 01 g. 02 c pic x.")
        debugged = [s for s in body(Parser(source).parse()) if hasattr(s, "debug_checks")]
        (name, ref, _), = debugged[0].debug_checks
        self.assertEqual((name, len(ref.indices)), ("e", 1))
        self.assertEqual(debugged[1].debug_checks[0][0], "c OF b")

    def test_statements_that_suspend_field_debugging(self):
        # GO, PERFORM, WRITE and REWRITE are debugged by their own code
        # generation; the inline statements of a PERFORM are debugged again.
        parsed = Parser(program("all x", "perform varying x from 1 by 1 until x > 2 move x to y end-perform. "
                                "go to b depending on x. b.")).parse()
        perform = next(s for s in body(parsed) if s.op == "loop")
        self.assertFalse(hasattr(perform, "debug_checks"))
        self.assertEqual(checks(perform.args[2][0]), [("x", "X")])
        Emitter(parsed).generate()

    def test_unmodelled_forms_are_refused(self):
        for targets, statements in (("x", "initialize x."), ("all x", "string x delimited size into e (1)."),
                                    ("x", "add 1 to x on size error display 'e' end-add."),
                                    ("all x", "move x(1:1) to y."), ("e (1)", "continue."),
                                    ("all x", "perform until x + 1 > 3 move 9 to x end-perform.")):
            with self.subTest(statements=statements), self.assertRaises(CobolError):
                Emitter(Parser(program(targets, statements)).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class DebuggingItemNativeTests(unittest.TestCase):
    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "debugging_items.cob", fmt="free", runtime_env={"COB_SET_DEBUG": "Y"})
        self.assertTrue(report["match"], report)
        self.assertIn("dbg     51 [n ", report["cobol_stdout"])
        self.assertIn("[+0002 +0001      ]", report["cobol_stdout"])

    def test_unchecked_separate_sign_move(self):
        # -fno-ec=data-incompatible: the digits of an invalid separate-sign
        # item are copied as they are and its sign byte becomes '+'.
        source = ROOT / "build" / "unchecked_sign.cob"
        source.parent.mkdir(exist_ok=True)
        source.write_text("identification division.\nprogram-id. u.\ndata division.\nworking-storage section.\n"
                          "01 g. 02 s pic s9(3) sign leading separate. 01 a pic x(4).\nprocedure division.\n"
                          "    move '- 1x' to g. move s to a. display '[' a '][' g ']'.\n"
                          "    move '*7 2' to g. move s to a. display '[' a '][' g ']'.\n    stop run.\n", encoding="utf-8")
        report = verify(source, fmt="free", no_ec_data_incompatible=True)
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "[ 1x ][- 1x]\n[7 2 ][+7 2]\n")


if __name__ == "__main__":
    unittest.main()
