from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.frontend import CobolError, Parser, lex, load_source, normalize
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def fixed(*areas: str) -> str:
    return "\n".join("       " + area for area in areas) + "\n"


def free(body: str) -> str:
    return ("identification division.\nprogram-id. documentary-case.\n" + body +
            "\nprocedure division.\ndisplay 'DOCS-OK' stop run.\n")


class DocumentaryTests(unittest.TestCase):
    def test_all_documentary_headers_mask_inline_payload_in_free_format(self):
        for header in ("AUTHOR", "INSTALLATION", "DATE-WRITTEN", "DATE-COMPILED", "SECURITY", "REMARKS"):
            with self.subTest(header=header):
                source = free(header + '. ignored " $ COPY "missing.cpy".')
                normalized = normalize(source, "free")
                self.assertEqual(normalized.splitlines()[2], "")
                self.assertEqual(Parser(normalized).parse().entry[0].op, "display")

    def test_fixed_prose_ignores_quotes_copy_and_header_words_until_area_a(self):
        source = fixed("identification division.", "program-id. documentary-case.",
                       'author. ignored " inline quote',
                       '    COPY "missing.cpy".',
                       '    PROCEDURE DIVISION and compiler"s prose $ ;',
                       "installation.", "    multiple sentences. another sentence.",
                       "procedure division.", "    display 'DOCS-OK' stop run.")
        normalized = normalize(source, "fixed")
        self.assertEqual(normalized.splitlines()[2:7], [""] * 5)
        tokens = lex(normalized)
        display = next(token for token in tokens if token.key == "DISPLAY")
        self.assertEqual(display.line, 9)
        self.assertEqual(Parser(normalized).parse().entry[0].op, "display")

    def test_fixed_header_in_area_b_still_starts_documentary_text(self):
        source = fixed("identification division.", "program-id. documentary-case.",
                       "    security.", '    arbitrary unmatched " and $',
                       "procedure division.", "    stop run.")
        normalized = normalize(source, "fixed")
        self.assertEqual(normalized.splitlines()[2:4], ["", ""])
        self.assertEqual(Parser(normalized).parse().entry[0].op, "stop")

    def test_free_comment_entry_does_not_swallow_the_following_line(self):
        source = free('author. inline prose\n    "not a continued comment')
        with self.assertRaises(CobolError):
            Parser(normalize(source, "free")).parse()

    def test_area_a_code_ends_fixed_comment_entry_instead_of_being_swallowed(self):
        source = fixed("identification division.", "program-id. documentary-case.",
                       "author.", "BOGUS TEXT.",
                       "procedure division.", "    stop run.")
        normalized = normalize(source, "fixed")
        self.assertIn("BOGUS TEXT.", normalized)
        with self.assertRaisesRegex(CobolError, "ligne 4:"):
            Parser(normalized).parse()

    def test_fixed_continuation_inside_a_comment_entry_is_rejected(self):
        prefix = fixed("identification division.", "program-id. documentary-case.", "author.")
        for continued in ("      -    ignored prose\n", "      -\n"):
            with self.subTest(continued=continued), self.assertRaisesRegex(CobolError, "ligne 4:"):
                normalize(prefix + continued + fixed("procedure division.", "    stop run."), "fixed")

    def test_documentary_header_cannot_repair_an_open_normal_literal(self):
        source = fixed("identification division.", 'program-id. documentary-case "open',
                       "author. ignored", "procedure division.", "    stop run.")
        with self.assertRaisesRegex(CobolError, "ligne 3:"):
            normalize(source, "fixed")

    def test_blank_and_fixed_comment_lines_do_not_end_the_entry(self):
        source = (fixed("identification division.", "program-id. documentary-case.", "author.") +
                  '\n000100* "ignored quote\n000200/ ignored page comment\n' +
                  fixed('    "still documentary', "procedure division.", "    stop run."))
        normalized = normalize(source, "fixed")
        self.assertEqual(Parser(normalized).parse().entry[0].op, "stop")
        self.assertEqual(normalized.count("\n"), len(source.splitlines()) - 1)

    def test_separate_format_directives_are_processed_inside_fixed_comments(self):
        prefix = fixed("identification division.", "program-id. documentary-case.", "author.")
        free_source = prefix + fixed("    >>source format free") + "procedure division.\nstop run.\n"
        self.assertEqual(Parser(normalize(free_source, "fixed")).parse().entry[0].op, "stop")
        fixed_source = (prefix + fixed("    >>source format fixed", '    "ignored quote',
                                      "procedure division.", "    stop run."))
        self.assertEqual(Parser(normalize(fixed_source, "fixed")).parse().entry[0].op, "stop")

    def test_inline_format_directive_is_documentary_payload(self):
        source = fixed("identification division.", "program-id. documentary-case.",
                       "author. >>source format free", "procedure division.", "    stop run.")
        self.assertEqual(Parser(normalize(source, "fixed")).parse().entry[0].op, "stop")
        wrong_format = fixed("identification division.", "program-id. documentary-case.",
                             "author. >>source format free") + "procedure division.\nstop run.\n"
        with self.assertRaises(CobolError):
            normalize(wrong_format, "fixed")

    def test_documentary_words_are_not_removed_from_other_contexts(self):
        source = free("")
        source = source.replace("display 'DOCS-OK'", "display 'AUTHOR. SECURITY. COPY missing.'")
        normalized = normalize(source, "free")
        self.assertIn("'AUTHOR. SECURITY. COPY missing.'", normalized)
        quoted_header = free("'AUTHOR'. still ordinary source")
        self.assertIn("'AUTHOR'. still ordinary source", normalize(quoted_header, "free"))
        with self.assertRaises(CobolError):
            Parser(normalize(quoted_header, "free")).parse()
        outside_identification = ("identification division.\nprogram-id. documentary-case.\n"
                                  "procedure division.\nAUTHOR.\n    display 'RETAINED'.\n")
        self.assertIn("AUTHOR.", normalize(outside_identification, "free"))
        self.assertIn("RETAINED", normalize(outside_identification, "free"))

    def test_inline_headers_and_semantic_identification_clauses_are_not_skipped(self):
        for source in (
            "identification division. program-id. documentary-case. AUTHOR. payload\nprocedure division. stop run.",
            'identification division.\nprogram-id. documentary-case as "external-name".\nprocedure division. stop run.',
            "identification division.\nprogram-id. documentary-case.\nAUTHORSHIP. payload\nprocedure division. stop run.",
        ):
            with self.subTest(source=source), self.assertRaises(CobolError):
                Parser(normalize(source, "free")).parse()

    def test_documentary_copy_is_ignored_but_real_copy_is_expanded(self):
        for name, operand in (("value.cpy", '"value.cpy"'), ("PIC", "PIC"), ("PICTURE", "PICTURE")):
            with self.subTest(copybook=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "documentary.cob"
                copy = root / name
                copy.write_text(fixed("01 count-a pic 9 value 3."), encoding="utf-8")
                source.write_text(fixed("identification division.", "program-id. documentary-case.",
                                        "security.", '    COPY "missing.cpy".',
                                        "data division.", "working-storage section.",
                                        f"COPY {operand}.", "procedure division.",
                                        "    display count-a stop run."), encoding="utf-8")
                expanded, copies = load_source(source, [], "fixed")
                self.assertEqual(copies, [str(copy.resolve())])
                self.assertNotIn("missing.cpy", expanded)
                parsed = Parser(expanded).parse()
                self.assertEqual(parsed.fields["COUNT-A"].initial.text, "3")

    def test_free_semantic_code_after_documentary_header_is_preserved(self):
        source = free("author. ignored\nenvironment division.\nconfiguration section.\n"
                      "    source-computer. GNU-Linux with debugging mode.")
        normalized = normalize(source, "free")
        self.assertIn("with debugging mode.", normalized)
        with self.assertRaisesRegex(CobolError, "ligne 6:"):
            Parser(normalized).parse()

    def test_area_a_copy_is_not_hidden_by_documentary_text(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "documentary.cob"
            source.write_text(fixed("identification division.", "program-id. documentary-case.",
                                    "security.", 'COPY "missing.cpy".',
                                    "procedure division.", "    stop run."), encoding="utf-8")
            with self.assertRaisesRegex(CobolError, "ligne 4:.*introuvable"):
                load_source(source, [], "fixed")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class DocumentaryNativeTests(unittest.TestCase):
    def assert_matches(self, source_text: str, fmt: str, expected: str):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "documentary-source.cob"
            source.write_text(source_text, encoding="utf-8")
            report = verify(source, fmt=fmt)
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], expected, report)
        self.assertEqual(report["rust_stdout"], expected, report)

    def test_original_fixed_fixture_ignores_documentary_payload(self):
        report = verify(ROOT / "tests" / "fixtures" / "documentary_fixed.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "DOCS-OK\nAUTHOR. is text\n")
        self.assertEqual(report["rust_stdout"], report["cobol_stdout"])

    def test_free_documentary_headers_ignore_only_their_own_lines(self):
        headers = "\n".join(f'{header}. ignored " $ COPY missing.' for header in
                            ("author", "installation", "date-written", "date-compiled", "security", "remarks"))
        self.assert_matches(free(headers), "free", "DOCS-OK\n")

    def test_fixed_header_in_area_b_and_format_switch_match_native(self):
        source = fixed("identification division.", "program-id. documentary-case.",
                       "    author.", '    COPY "missing.cpy". unmatched "',
                       "    >>source format free") + "procedure division.\ndisplay 'SWITCHED' stop run.\n"
        self.assert_matches(source, "fixed", "SWITCHED\n")


if __name__ == "__main__":
    unittest.main()
