from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import find_tool
from cobol2rust.verification import verify


def program(body: str, data: str = "") -> str:
    return ("identification division.\nprogram-id. section-case.\n" + data +
            "procedure division.\n" + body + "\n")


class SectionTests(unittest.TestCase):
    def test_blocks_keep_source_order_and_section_ranges(self):
        parsed = Parser(program('''display "ENTRY".
outside-p. display "OUTSIDE".
area-a section.
display "PREAMBLE".
alpha. display "A".
beta. display "B".
empty-a section.
area-b section.
gamma. display "C".
empty-b section.
''')).parse()
        self.assertEqual([(block.name, block.section) for block in parsed.blocks], [
            (None, None), ("OUTSIDE-P", None), (None, "AREA-A"),
            ("ALPHA", "AREA-A"), ("BETA", "AREA-A"), (None, "EMPTY-A"),
            (None, "AREA-B"), ("GAMMA", "AREA-B"), (None, "EMPTY-B"),
        ])
        self.assertEqual(parsed.sections, {
            "AREA-A": (2, 5), "EMPTY-A": (5, 6),
            "AREA-B": (6, 8), "EMPTY-B": (8, 9),
        })
        self.assertEqual(list(parsed.paragraphs), ["OUTSIDE-P", "ALPHA", "BETA", "GAMMA"])
        self.assertIs(parsed.entry, parsed.blocks[0].body)
        for index in (1, 3, 4, 7):
            block = parsed.blocks[index]
            self.assertIs(parsed.paragraphs[block.name], block.body)
            self.assertEqual(parsed.procedure_range(block.name), (index, index + 1))
        for name, bounds in parsed.sections.items():
            self.assertEqual(parsed.procedure_range(name), bounds)
        for index in (5, 6, 8):
            self.assertEqual(parsed.blocks[index].body, [])

    def test_empty_entry_and_empty_sections_are_distinct_blocks(self):
        parsed = Parser(program("empty-a section.\nempty-b section.\n")).parse()
        self.assertEqual([(block.name, block.section, block.body) for block in parsed.blocks], [
            (None, None, []), (None, "EMPTY-A", []), (None, "EMPTY-B", []),
        ])
        self.assertEqual(parsed.sections, {"EMPTY-A": (1, 2), "EMPTY-B": (2, 3)})

    def test_section_and_paragraph_targets_can_be_mixed(self):
        for target in ("area-a", "alpha", "area-a thru area-b", "beta through area-b",
                       "area-a thru alpha", "alpha thru beta", "alpha thru area-a",
                       "area-a thru area-a", "empty-a", "empty-a thru alpha"):
            with self.subTest(target=target):
                Parser(program(f'''perform {target} stop run.
empty-a section.
area-a section.
alpha. continue.
beta. continue.
area-b section.
gamma. continue.
''')).parse()

    def test_unknown_targets_are_rejected_and_backward_ranges_accepted(self):
        # cobc accepts a THRU end placed before its start: the PERFORM
        # returns whenever control reaches the end of that procedure.
        for target, accepted in (("missing", False), ("area-a thru missing", False), ("missing thru alpha", False),
                                 ("beta thru alpha", True), ("area-b thru area-a", True),
                                 ("area-b thru beta", True), ("gamma thru area-a", True)):
            source = program(f'''perform {target} stop run.
area-a section.
alpha. continue.
beta. continue.
area-b section.
gamma. continue.
''')
            with self.subTest(target=target):
                if accepted:
                    Parser(source).parse()
                else:
                    with self.assertRaises(CobolError):
                        Parser(source).parse()

    def test_calls_are_validated_inside_section_preambles_and_nested_blocks(self):
        for statements in ("perform missing", "if 1 = 1 perform missing end-if",
                           "perform 2 times perform missing end-perform",
                           "evaluate 1 when 1 perform missing end-evaluate"):
            for location in ("", "alpha."):
                with self.subTest(statements=statements, location=location), self.assertRaises(CobolError):
                    Parser(program("stop run.\narea-a section.\n" + location + statements + ".")).parse()

    def test_duplicate_and_qualified_procedure_names_follow_cobc(self):
        # cb_build_section_name and cb_ref, checked against cobc 3.2.
        homonyms = " area-a section. alpha. continue. area-b section. alpha. continue."
        for body in (
            "area-a section. alpha. continue. area-b section. alpha. continue.",
            "perform alpha of area-a stop run. area-a section. alpha. continue.",
            "perform alpha in area-a stop run. area-a section. alpha. continue.",
            "perform alpha thru beta of area-a stop run. area-a section. alpha. continue. beta. continue.",
            "perform alpha of area-b stop run." + homonyms,
        ):
            with self.subTest(body=body):
                Parser(program(body)).parse()
        for body in (
            "area-a section. area-a section.",
            "area-a section. area-a. continue.",
            "area-a. continue. area-a section.",
            "perform alpha stop run." + homonyms,
            "perform area-a of area-b stop run." + homonyms,
        ):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program(body)).parse()

    def test_segmented_sections_and_unsupported_exit_variants_are_rejected(self):
        # Segment numbers only matter to independent ALTERed paragraphs.
        Parser(program("area-a section 1. continue. area-b section 50. continue.")).parse()
        for body in ("area-a section 100. continue.", "exit section.",
                     # EXIT PERFORM is only valid within an inline PERFORM.
                     "exit perform.", "exit perform cycle."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program(body)).parse()
        Parser(program("perform 2 times exit perform end-perform.")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SectionNativeTests(unittest.TestCase):
    def assert_matches(self, body: str, expected: str, data: str = ""):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sections.cob"
            source.write_text(program(body, data), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertEqual(report["cobol_stdout"], expected, report)
        self.assertEqual(report["rust_stdout"], expected, report)
        self.assertTrue(report["match"], report)

    def test_section_paragraph_and_mixed_thru_calls_have_distinct_endpoints(self):
        self.assert_matches('''display "SECTION"
perform area-a
display "PARAGRAPH"
perform alpha
display "SECTION-SECTION"
perform area-a thru area-b
display "PARAGRAPH-SECTION"
perform beta thru area-b
display "SECTION-PARAGRAPH"
perform area-a thru alpha
display "PARAGRAPH-PARAGRAPH"
perform alpha thru beta
display "PARAGRAPH-OWN-SECTION"
perform alpha thru area-a
display "DONE" stop run.
area-a section.
alpha. display "A".
beta. display "B".
area-b section.
gamma. display "C".
''', "SECTION\nA\nB\nPARAGRAPH\nA\nSECTION-SECTION\nA\nB\nC\n"
            "PARAGRAPH-SECTION\nB\nC\nSECTION-PARAGRAPH\nA\nPARAGRAPH-PARAGRAPH\nA\nB\n"
            "PARAGRAPH-OWN-SECTION\nA\nB\nDONE\n")

    def test_sequential_execution_falls_through_paragraph_and_section_boundaries(self):
        self.assert_matches('''display "ENTRY".
outside-p. display "OUTSIDE".
area-a section.
display "PREAMBLE".
alpha. display "A".
beta. display "B".
empty-a section.
area-b section.
gamma. display "C".
''', "ENTRY\nOUTSIDE\nPREAMBLE\nA\nB\nC\n")

    def test_section_preambles_and_empty_endpoints_are_executed_once(self):
        self.assert_matches('''perform empty-start
perform area-a
perform empty-middle
perform empty-start thru alpha
perform beta thru empty-middle
perform area-b
perform empty-last
display "RETURN" stop run.
empty-start section.
area-a section.
display "PRE".
alpha. display "A".
beta. display "B".
empty-middle section.
area-b section.
display "SECOND".
empty-last section.
''', "PRE\nA\nB\nPRE\nA\nB\nSECOND\nRETURN\n")

    def test_perform_loops_call_sections_with_each_existing_loop_mode(self):
        self.assert_matches('''perform area-a 2 times
perform area-a until counter >= 4
perform area-a with test after until counter >= 5
perform area-b varying counter from 1 by 1 until counter > 2
display "RETURN" stop run.
area-a section.
alpha. add 1 to counter display counter.
area-b section.
beta. display "LOOP" counter.
''', "1\n2\n3\n4\n5\nLOOP1\nLOOP2\nRETURN\n",
            "data division. working-storage section. 01 counter pic 9 value 0.\n")

    def test_recursive_section_performs_preserve_each_return(self):
        self.assert_matches('''perform recursive-area
display "DONE" stop run.
recursive-area section.
recur.
add 1 to depth
display "IN" depth
if depth < 3 perform recursive-area end-if
display "OUT" depth
subtract 1 from depth.
tail-p. display "TAIL" depth.
''', "IN1\nIN2\nIN3\nOUT3\nTAIL2\nOUT2\nTAIL1\nOUT1\nTAIL0\nDONE\n",
            "data division. working-storage section. 01 depth pic 9 value 0.\n")

    def test_stop_run_propagates_out_of_nested_section_performs_and_loops(self):
        self.assert_matches('''perform outer-area 2 times
display "UNREACHABLE" stop run.
outer-area section.
alpha. perform inner-area display "UNREACHABLE".
beta. display "UNREACHABLE".
inner-area section.
gamma. display "STOP" stop run.
delta. display "UNREACHABLE".
''', "STOP\n")

    def test_exit_paragraph_leaves_nested_loops_but_continues_the_section(self):
        self.assert_matches('''perform area-a 2 times
display "PARAGRAPH-ONLY"
perform alpha
display "RETURN" stop run.
area-a section.
display "PRE"
perform 2 times
 display "IN"
 exit paragraph
 display "UNREACHABLE"
end-perform
display "UNREACHABLE".
alpha.
display "ALPHA"
perform 2 times
 if 1 = 1 exit paragraph end-if
 display "UNREACHABLE"
end-perform
display "UNREACHABLE".
beta. display "NEXT".
''', "PRE\nIN\nALPHA\nNEXT\nPRE\nIN\nALPHA\nNEXT\nPARAGRAPH-ONLY\nALPHA\nRETURN\n")

    def test_bare_exit_preserves_following_statements(self):
        self.assert_matches('''perform area-a display "RETURN" stop run.
area-a section.
alpha. display "A" exit display "B".
beta. exit. display "C".
''', "A\nB\nC\nRETURN\n")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ExitSectionNativeTests(unittest.TestCase):
    def test_exit_section_can_bypass_a_paragraph_perform_return(self):
        # A paragraph PERFORM does not catch EXIT SECTION at its return point.
        source_text = program('''perform alpha display "RETURN" stop run.
area-a section.
alpha. display "A" exit section display "UNREACHABLE".
beta. display "UNREACHABLE".
area-b section.
gamma. display "C".
''')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "exit-section.cob"
            source.write_text(source_text, encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "A\nC\n")
        self.assertEqual(report["rust_stdout"], "A\nC\n")


if __name__ == "__main__":
    unittest.main()
