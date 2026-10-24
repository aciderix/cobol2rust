from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import find_tool
from cobol2rust.verification import verify
from tests.test_files import file_program


def program(body: str, data: str = "") -> str:
    return ("identification division.\nprogram-id. goto-case.\n" +
            ("data division. working-storage section.\n" + data + "\n" if data else "") +
            "procedure division.\n" + body + "\n")


class GotoTests(unittest.TestCase):
    def test_simple_goto_and_optional_to_preserve_targets(self):
        for keyword in ("go", "go to"):
            with self.subTest(keyword=keyword):
                parsed = Parser(program(f'{keyword} finish-p. finish-p. stop run.')).parse()
                self.assertEqual(parsed.entry[0].op, "goto")
                self.assertEqual(parsed.entry[0].args, (["FINISH-P"], None))
        parsed = Parser(program('go area-a. area-a section. display "GO" stop run.')).parse()
        self.assertEqual(parsed.entry[0].args, (["AREA-A"], None))

    def test_computed_goto_keeps_order_and_indexed_controller(self):
        parsed = Parser(program('''go alpha beta depending on choices(2).
alpha. stop run.
beta. stop run.
''', '01 choices pic s9 occurs 2 times.')).parse()
        targets, controller = parsed.entry[0].args
        self.assertEqual(targets, ["ALPHA", "BETA"])
        self.assertEqual(controller.name, "CHOICES")
        self.assertEqual(controller.indices[0].args, ("2",))

    def test_unknown_goto_targets_are_validated_in_nested_bodies(self):
        for body in ("go missing", "if 1 = 1 go missing end-if",
                     "perform 2 times go missing end-perform",
                     "evaluate 1 when 1 go missing end-evaluate",
                     "compute n = 10 on size error go missing end-compute",
                     "go alpha missing depending on n"):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program("stop run.\narea-a section.\n" + body +
                               ".\nalpha. continue.", "01 n pic 9.")).parse()

    def test_goto_forms_follow_cobc(self):
        # Checked against cobc 3.2: GO TO without target (obsolete) and
        # section-qualified targets compile; the others are rejected.
        procedures = "\narea-a section.\nalpha. continue.\nbeta. stop run."
        for body in ("go.", "go to.", "go alpha of area-a.", "go alpha in area-a.",
                     "go alpha beta of area-a depending on n."):
            with self.subTest(body=body):
                Emitter(Parser(program(body + procedures, "01 n pic 9.")).parse()).generate()
        for body in ("go alpha beta.", "go alpha beta depending on n + 1.",
                     "go alpha beta depending on 1.",
                     "alter alpha to proceed to beta."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(body + procedures, "01 n pic 9.")).parse()).generate()

    def test_computed_goto_rejects_unmodelled_controllers(self):
        for declaration, controller in (("01 n pic 9v9.", "n"),
                                        ("01 n pic x.", "n"),
                                        ("01 n pic +9.", "n"),
                                        ("01 n pic 99.", "n(1:1)"),
                                        ("01 n pic 9(10).", "n"),
                                        ("01 n pic 9(18) comp-3.", "n")):
            with self.subTest(declaration=declaration), self.assertRaises(CobolError):
                Emitter(Parser(program(f"go alpha beta depending on {controller}.\n"
                                       "alpha. stop run. beta. stop run.", declaration)).parse()).generate()

    def test_exit_section_requires_a_containing_section(self):
        for body in ("exit section.", "alpha. exit section.",
                     "perform 2 times exit section end-perform."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program(body)).parse()
        parsed = Parser(program("stop run. area-a section. exit section.")).parse()
        self.assertEqual(parsed.blocks[1].body[0].op, "exit_section")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class GotoNativeTests(unittest.TestCase):
    def assert_matches(self, contents: str, expected: str, seed: dict[str, bytes] | None = None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "control-flow.cob"
            source.write_text(contents, encoding="utf-8")
            data = None
            if seed is not None:
                data = root / "inputs"
                data.mkdir()
                for name, value in seed.items():
                    (data / name).write_bytes(value)
            report = verify(source, fmt="free", data_dir=data)
        self.assertEqual(report["cobol_stdout"], expected, report)
        self.assertEqual(report["rust_stdout"], expected, report)
        self.assertTrue(report["match"], report)

    def test_forward_backward_goto_and_section_entry(self):
        self.assert_matches(program('''go first-p display "BAD".
skipped-p. display "BAD".
first-p.
add 1 to count-a
if count-a < 3 go to first-p end-if
display count-a
go finish-area display "BAD".
unused-area section. display "BAD".
finish-area section. display "PRE".
last-p. display "END" stop run.
''', "01 count-a pic 9 value 0."), "3\nPRE\nEND\n")

    def test_computed_goto_integer_indices_and_out_of_range_fallthrough(self):
        self.assert_matches(program('''perform dispatch-area varying choice from -1 by 1 until choice > 4
display "DONE" stop run.
dispatch-area section.
dispatch-p.
go to first-p second-p third-p depending on choice
display "FALL" exit section.
first-p. display "FIRST" exit section.
second-p. display "SECOND" exit section.
third-p. display "THIRD" exit section.
''', "01 choice pic s9 value 0."), "FALL\nFALL\nFIRST\nSECOND\nTHIRD\nFALL\nDONE\n")

    def test_computed_goto_uses_subscripted_table_and_implicit_index_controllers(self):
        self.assert_matches(program('''move 1 to choices(1) move 2 to choices(2)
set idx to 2
perform select-row
perform select-index
set idx to 1 perform select-index
set idx to 0 perform select-index
display "DONE" stop run.
select-row section.
go first-row second-row depending choices(idx)
display "BAD" exit section.
first-row. display "ROW1" exit section.
second-row. display "ROW2" exit section.
select-index section.
go first-index second-index depending on idx
display "NONE" exit section.
first-index. display "INDEX1" exit section.
second-index. display "INDEX2" exit section.
''', "01 table-a. 05 choices occurs 2 indexed by idx pic s9."),
                            "ROW2\nINDEX2\nINDEX1\nNONE\nDONE\n")

    def test_computed_goto_decodes_signed_nine_digit_binary_and_packed_controllers(self):
        self.assert_matches(program('''perform binary-dispatch
move 2 to binary-choice perform binary-dispatch
move 999999999 to binary-choice perform binary-dispatch
perform packed-dispatch
move 2 to packed-choice perform packed-dispatch
move 999999999 to packed-choice perform packed-dispatch
display "DONE" stop run.
binary-dispatch section.
go first-binary second-binary depending on binary-choice
display "B-FALL" exit section.
first-binary. display "B-FIRST" exit section.
second-binary. display "B-SECOND" exit section.
packed-dispatch section.
go first-packed second-packed depending on packed-choice
display "P-FALL" exit section.
first-packed. display "P-FIRST" exit section.
second-packed. display "P-SECOND" exit section.
''', "01 binary-choice pic s9(9) comp value -1.\n"
     "01 packed-choice pic s9(9) comp-3 value -1."),
                            "B-FALL\nB-SECOND\nB-FALL\nP-FALL\nP-SECOND\nP-FALL\nDONE\n")


    def test_jump_exits_if_evaluate_and_inline_loop_bodies(self):
        self.assert_matches(program('''perform 3 times
 if 1 = 1 go after-if end-if
 display "BAD"
end-perform.
after-if.
evaluate 1
 when 1 go after-evaluate
 when other display "BAD"
end-evaluate
display "BAD".
after-evaluate.
perform until n = 9
 go after-until
 display "BAD"
end-perform.
after-until.
perform varying n from 1 by 1 until n > 3
 go done-p
 display "BAD"
end-perform
display "BAD".
done-p. display "OK" n stop run.
''', "01 n pic 9 value 0."), "OK1\n")

    def test_jump_from_both_size_error_branches(self):
        self.assert_matches(program('''compute n = 10
 on size error go recovered-p
 not on size error display "BAD"
end-compute
display "BAD".
recovered-p.
compute n = 2
 on size error display "BAD"
 not on size error go done-p
end-compute
display "BAD".
done-p. display "OK" n stop run.
''', "01 n pic 9 value 0."), "OK2\n")

    def test_jump_from_both_read_branches(self):
        contents = file_program('''open input f
read f not at end go got-record end-read
display "BAD" stop run.
got-record.
display rec close f
open input f read f
read f at end go got-end end-read
display "BAD" stop run.
got-end. close f display "END" stop run.
''', fd="fd f. 01 rec pic x(3).")
        self.assert_matches(contents, "ROW\nEND\n", {"data.txt": b"ROW\n"})

    def test_goto_keeps_dormant_perform_frame_until_endpoint_is_reached(self):
        self.assert_matches(program('''perform alpha
display "RETURN" stop run.
alpha. add 1 to count-a display "A" count-a
if count-a = 1 go outside-p end-if
display "END-A".
between-p. display "BAD" stop run.
outside-p. display "OUTSIDE" go alpha.
''', "01 count-a pic 9 value 0."), "A1\nOUTSIDE\nA2\nEND-A\nRETURN\n")

    def test_perform_endpoint_checks_only_top_frame(self):
        self.assert_matches(program('''perform alpha
display "RETURN" stop run.
alpha. display "A"
if count-a = 0 move 1 to count-a perform gamma display "BAD" end-if
display "END-A".
beta. display "B" stop run.
gamma. display "G" go alpha.
''', "01 count-a pic 9 value 0."), "A\nG\nA\nEND-A\nB\n")

    def test_jump_to_last_paragraph_executes_body_before_return(self):
        self.assert_matches(program('''perform alpha thru omega
display "RETURN" stop run.
alpha. display "A" go omega.
middle-p. display "BAD".
omega. display "OMEGA".
after-p. display "BAD" stop run.
'''), "A\nOMEGA\nRETURN\n")

    def test_last_paragraph_and_section_have_separate_return_checkpoints(self):
        self.assert_matches(program('''perform area-a
display "RETURN" stop run.
area-a section.
alpha. perform omega display "AFTER".
omega. display "LAST".
area-b section. display "BAD" stop run.
'''), "LAST\nAFTER\nLAST\nRETURN\n")

    def test_exit_section_uses_section_endpoint_from_anonymous_preamble(self):
        self.assert_matches(program('''perform area-a
display "RETURN" stop run.
area-a section.
display "PRE"
perform 2 times
 if 1 = 1 exit section end-if
 display "BAD"
end-perform
display "BAD".
alpha. display "BAD".
area-b section. display "BAD" stop run.
'''), "PRE\nRETURN\n")

    def test_exit_section_does_not_unwind_nested_paragraph_or_section_calls(self):
        self.assert_matches(program('''perform area-a display "RETURN" stop run.
area-a section.
alpha. display "A" perform beta display "BAD".
beta. display "B" exit section display "BAD".
area-b section. display "C" stop run.
'''), "A\nB\nC\n")

    def test_goto_next_section_bypasses_active_return_checkpoint(self):
        self.assert_matches(program('''perform area-a
display "RETURN" stop run.
area-a section.
alpha. display "A" go area-b.
area-b section. display "B" stop run.
'''), "A\nB\n")

    def test_recursive_times_counter_is_shared_by_its_syntactic_site(self):
        # GnuCOBOL's n0 loop counter is not saved in the PERFORM frame.
        # Recursive re-entry overwrites the outer iteration counter.
        for body in ('''perform alpha display "RETURN" stop run.
alpha.
add 1 to depth
perform 2 times
 display "LOOP" depth
 if depth = 1 perform alpha end-if
end-perform
display "END" depth subtract 1 from depth.
''', '''perform alpha display "RETURN" stop run.
alpha.
add 1 to depth
perform beta 2 times
display "END" depth subtract 1 from depth.
beta.
display "LOOP" depth
if depth = 1 perform alpha end-if.
'''):
            with self.subTest(body=body):
                self.assert_matches(program(body, "01 depth pic 9 value 0."),
                                    "LOOP1\nLOOP2\nLOOP2\nEND2\nEND1\nRETURN\n")


if __name__ == "__main__":
    unittest.main()
