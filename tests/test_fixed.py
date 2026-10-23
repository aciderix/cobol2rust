from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.frontend import CobolError, lex, load_source, normalize
from cobol2rust.toolchain import find_tool
from cobol2rust.verification import verify


def fixed(body, data=()):
    return "\n".join([
        "       identification division.", "       program-id. fixed-continuation.",
        "       data division.", "       working-storage section.", *data,
        "       procedure division.", *body, "       stop run.",
    ]) + "\n"


class FixedContinuationTests(unittest.TestCase):
    def test_debugging_lines_are_comments_without_debugging_mode(self):
        text = normalize('000100D    display "debug".\n000200     display "kept".', "fixed")
        self.assertEqual(text.splitlines(), ["", '    display "kept".'])
        self.assertEqual(normalize('000100d    display "debug".', "fixed"), "")
        # GnuCOBOL activates them on WITH DEBUGGING MODE: not modelled.
        with self.assertRaises(CobolError):
            normalize('       source-computer. x with debugging mode.\n000100D    display "x".', "fixed")

    def test_words_numbers_and_pictures_continue_without_spaces(self):
        text = normalize("       DISPL   \n      -    AY 12\n      -    34.", "fixed")
        self.assertEqual([token.text for token in lex(text)], ["DISPLAY", "1234", ".", "<EOF>"])
        picture = normalize("       01 n PIC S9(\n      -    4)V99.", "fixed")
        self.assertIn("S9(4)V99", picture)
        self.assertEqual(text.count("\n"), 2)

    def test_open_literal_includes_padding_and_continuation_spaces(self):
        first = '           display "AB'
        text = normalize(first + '\n      -    " CD".', "fixed")
        token = next(token for token in lex(text) if token.string)
        self.assertEqual(token.text, "AB" + " " * (72 - len(first)) + " CD")
        self.assertEqual(token.line, 1)

    def test_comments_and_blank_lines_preserve_continuation(self):
        text = normalize('       DISPL *> quote " in comment\n'
                         '000100* ignored\n000200/ ignored\n\n'
                         '      -     \n      -AY "OK".', "fixed")
        self.assertEqual([token.text for token in lex(text)], ["DISPLAY", "OK", ".", "<EOF>"])
        self.assertEqual(text.count("\n"), 5)
        first = '           display "AB'
        literal = normalize(first + '\n000100* ignored\n\n      -\n      -    "CD".', "fixed")
        self.assertEqual(next(token.text for token in lex(literal) if token.string),
                         "AB" + " " * (72 - len(first)) + "CD")

    def test_closed_literals_remain_separate_tokens(self):
        text = normalize('           display "AB"\n      -    "CD".', "fixed")
        self.assertEqual([token.text for token in lex(text) if token.string], ["AB", "CD"])

    def test_tabs_expand_before_source_columns_and_literal_padding(self):
        text = normalize('           display "A\tB".', "fixed")
        self.assertEqual(next(token.text for token in lex(text) if token.string), "A   B")
        text = normalize('       DISPL\n      -\tAY "OK".', "fixed")
        self.assertEqual([token.text for token in lex(text)], ["DISPLAY", "OK", ".", "<EOF>"])
        first = '           display "A\tB'
        text = normalize(first + '\n      -\t"CD".', "fixed")
        self.assertEqual(next(token.text for token in lex(text) if token.string),
                         "A   B" + " " * (72 - len(first.expandtabs(8))) + "CD")

    def test_quote_at_column_72_and_split_escaped_quote(self):
        prefix = '           display "'
        closed_at_72 = prefix + "A" * (71 - len(prefix)) + '"'
        self.assertEqual(len(closed_at_72), 72)
        continued = normalize(closed_at_72 + '\n      -    ""B".', "fixed")
        self.assertEqual(next(token.text for token in lex(continued) if token.string),
                         "A" * (71 - len(prefix)) + '"B')
        ordinary = normalize(closed_at_72 + '\n           stop run.', "fixed")
        self.assertEqual(next(token.text for token in lex(ordinary) if token.string),
                         "A" * (71 - len(prefix)))
        escaped_at_boundary = prefix + "A" * (70 - len(prefix)) + '""'
        continued = normalize(escaped_at_boundary + '\n      -    "B".', "fixed")
        self.assertEqual(next(token.text for token in lex(continued) if token.string),
                         "A" * (70 - len(prefix)) + '"B')
        with self.assertRaisesRegex(CobolError, "délimiteur"):
            normalize(closed_at_72 + '\n      -    "B".', "fixed")

    def test_bad_continuations_and_semantic_indicators_are_rejected(self):
        cases = [
            "      -    orphan",
            '           display "open\n      -    no-quote',
            '           display "open\n      -    \'wrong-quote\'',
            '           display "open\n           stop run.',
            '           DISPL\n       >>source format fixed\n      -    AY "bad".',
            '           display "open\n       >>source format free\ndisplay "bad".',
            '           display "open\n      -    >>source format free',
        ]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(CobolError):
                normalize(text, "fixed")

    def test_multisegment_literal_and_sequence_area(self):
        first = '000100     display "first'
        second = '000200-    "second'
        last = '000300-    "last".'
        text = normalize("\n".join([first, second, last]), "fixed")
        self.assertEqual(next(token.text for token in lex(text) if token.string),
                         "first" + " " * (72 - len(first)) +
                         "second" + " " * (72 - len(second)) + "last")

    def test_continued_copy_name_is_expanded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, copy = root / "source.cob", root / "values.cpy"
            source.write_text('       COPY val\n      -    ues.', encoding="utf-8")
            copy.write_text('       01 n pic 9 value 2.', encoding="utf-8")
            text, copies = load_source(source, [], "fixed")
            self.assertIn("01 n pic 9 value 2", text)
            self.assertEqual(copies, [str(copy.resolve())])


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class FixedContinuationNativeTests(unittest.TestCase):
    def test_debugging_line_is_dropped_like_gnucobol(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "debugging-line.cob"
            source.write_text(fixed(['000100D    display "debug"', '           display "kept"']), encoding="utf-8")
            report = verify(source, fmt="fixed")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "kept\n")

    def test_continued_sources_match_gnucobol(self):
        prefix = '           display "'
        first = '           display "AB'
        cases = [
            (fixed(['           DISPL *> quote " in comment', '000100* ignored',
                    '      -AY n "AB"', '      -    "CD"'],
                   ['       01 n pic 9(4) value 12', '      -    34.']), b"1234ABCD\n"),
            (fixed([first, '000100/ ignored', '      -', '      -    " CD"']),
             ("AB" + " " * (72 - len(first)) + " CD\n").encode()),
            (fixed([prefix + "A" * (71 - len(prefix)) + '"', '      -    ""B"']),
             ("A" * (71 - len(prefix)) + '"B\n').encode()),
            (fixed([prefix + "A" * (70 - len(prefix)) + '""', '      -    "B"']),
             ("A" * (70 - len(prefix)) + '"B\n').encode()),
            (fixed(['           DISPL', '      -\tAY "A\tB"']), b"A   B\n"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            for number, (contents, expected) in enumerate(cases):
                with self.subTest(case=number):
                    source = Path(temporary) / f"case{number}.cob"
                    source.write_text(contents, encoding="utf-8")
                    report = verify(source, "fixed")
                    self.assertTrue(report["match"], report)
                    self.assertEqual(report["cobol_stdout"].encode("ascii"), expected)


if __name__ == "__main__":
    unittest.main()
