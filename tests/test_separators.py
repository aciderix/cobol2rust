from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser, lex, load_source
from cobol2rust.toolchain import find_tool
from cobol2rust.verification import verify


FIXTURE = Path(__file__).parent / "fixtures" / "separators.cob"


def program(data="", body='display "OK" stop run.'):
    return ("identification division.\nprogram-id. separator-case.\n"
            "data division.\nworking-storage section.\n" + data + "\n"
            "procedure division.\n" + body + "\n")


class SeparatorTests(unittest.TestCase):
    def test_ordinary_separators_preserve_literals_comments_and_offsets(self):
        source = 'display "A,B;C";, *> ignored ;, "quote"\n,; display 1,,2;;.\n'
        tokens = lex(source)
        self.assertEqual([token.key for token in tokens],
                         ["DISPLAY", "A,B;C", "DISPLAY", "1", "2", ".", "<EOF>"])
        self.assertEqual([token.line for token in tokens], [1, 1, 2, 2, 2, 2, 3])
        for token in tokens[:-1]:
            with self.subTest(token=token):
                raw = source[token.start:token.end]
                self.assertEqual(raw, '"' + token.text + '"' if token.string else token.text)
                self.assertEqual(token.line, source.count("\n", 0, token.start) + 1)
        self.assertEqual((tokens[-1].start, tokens[-1].end), (len(source), len(source)))

    def test_parenthesized_separators_keep_signed_indices_distinct(self):
        for separator in [",", ";", ",,", ";;"]:
            source = "cell-a(1" + separator + "+2)"
            with self.subTest(separator=separator):
                tokens = lex(source)
                self.assertEqual([token.key for token in tokens],
                                 ["CELL-A", "(", "1", separator[0], "+", "2", ")", "<EOF>"])
                delimiter = tokens[3]
                self.assertEqual(source[delimiter.start:delimiter.end], separator)

    def test_separator_clusters_between_operands_do_not_create_sentences(self):
        for separator in [",", ";", ",,", ";;", ",;", ";,", ", ;", "; ,", ",;,,;;", ",\n;"]:
            body = ('move 2 to n if n = 9 display "BAD"' + separator +
                    'display "ALSO-BAD" end-if display n stop run.')
            with self.subTest(separator=separator):
                plain = body.replace(",", " ").replace(";", " ")
                baseline = Emitter(Parser(program("01 n pic 9.", plain)).parse()).generate()[0]
                generated = Emitter(Parser(program("01 n pic 9.", body)).parse()).generate()[0]
                self.assertEqual(generated, baseline)

    def test_picture_and_decimal_tokens_keep_their_complete_source_spans(self):
        source = "01 amount-a picture is -9(3).99; value 12.34.\n01 text-a pic x(3), value 'ABC'."
        tokens = lex(source)
        self.assertEqual([token.key for token in tokens],
                         ["01", "AMOUNT-A", "PICTURE", "IS", "-9(3).99", "VALUE", "12.34", ".",
                          "01", "TEXT-A", "PIC", "X(3)", "VALUE", "ABC", ".", "<EOF>"])
        for token in tokens[:-1]:
            raw = source[token.start:token.end]
            self.assertEqual(raw, "'ABC'" if token.string else token.text)
            self.assertEqual(token.line, source.count("\n", 0, token.start) + 1)

    def test_picture_trailing_period_is_a_separate_sentence_token(self):
        source = "01 n pic +9(3).99.\n01 m pic 9(3),."
        tokens = lex(source)
        pictures = [tokens[index + 1] for index, token in enumerate(tokens) if token.key == "PIC"]
        self.assertEqual([token.text for token in pictures], ["+9(3).99", "9(3),"])
        for token in pictures:
            self.assertEqual(source[token.start:token.end], token.text)
            self.assertEqual(source[token.end], ".")

    def test_supported_pictures_accept_separators_before_the_next_clause(self):
        data = ('01 first-a pic x(3);value "ABC".\n'
                '01 second-a picture is x(3), value "XYZ".\n'
                '01 number-a pic 99;usage display value 12.\n'
                '01 edited-a pic +9(3).99; value 12.34.')
        parsed = Parser(program(data)).parse()
        self.assertEqual(parsed.fields["FIRST-A"].picture, "X(3)")
        self.assertEqual(parsed.fields["SECOND-A"].picture, "X(3)")
        self.assertEqual(parsed.fields["NUMBER-A"].picture, "99")
        self.assertEqual(parsed.fields["EDITED-A"].picture, "+9(3).99")
        self.assertIn("fn main", Emitter(parsed).generate()[0])

    def test_picture_fragments_are_never_merged_across_whitespace(self):
        for picture in ["S9 (4) V99", "9( 4 )", "9 V99", "9(4)V 99", "X (3)",
                        "9\n(3)", "9(3)\nV99", "9, 999", "9,\n999", "9 ,999", "9;999"]:
            with self.subTest(picture=picture), self.assertRaises(CobolError):
                Emitter(Parser(program("01 n pic " + picture + ".")).parse()).generate()

    def test_picture_can_end_at_an_adjacent_inline_comment(self):
        for picture in ["X(3)", "9(3)", "X(3),", "9(3),"]:
            with self.subTest(picture=picture):
                parsed = Parser(program("01 n pic " + picture + "*> ignored ,;\n.")).parse()
                self.assertEqual(parsed.fields["N"].picture, picture.rstrip(","))

    def test_picture_keywords_cannot_be_data_names(self):
        for name in ["PIC", "PICTURE"]:
            for data in ["01 " + name + " pic 9.",
                         "01 n pic 9. 88 " + name + " value 1.",
                         "01 n pic 9 occurs 2 indexed by " + name + " usage display."]:
                with self.subTest(name=name, data=data), self.assertRaisesRegex(CobolError, "réservé"):
                    Parser(program(data)).parse()

    def test_unsupported_comma_editing_is_not_silently_discarded(self):
        for picture in ["9,999", "9,9", "9(3),", "X(3),"]:
            with self.subTest(picture=picture), self.assertRaises(CobolError):
                Emitter(Parser(program("01 n pic " + picture + ".")).parse()).generate()

    def test_separators_do_not_turn_numeric_lists_into_single_numbers(self):
        for body in ["move 1,2 to n stop run.", "compute n = 1,2 stop run.",
                     "compute n = (1,2) stop run.", "compute n = (1;2) stop run."]:
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program("01 n pic 99.", body)).parse()).generate()

    def test_copy_extra_separators_are_conservatively_rejected(self):
        directives = ['COPY ; "values.cpy".', 'COPY , "values.cpy".',
                      'COPY ,; "values.cpy".', 'COPY "values.cpy";.',
                      'COPY "values.cpy",.', 'COPY "values.cpy", ; .',
                      ', COPY "values.cpy".', 'COPY "values.cpy". ;']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "values.cpy").write_text("01 n pic 9 value 2.\n", encoding="utf-8")
            source = root / "source.cob"
            for directive in directives:
                source.write_text(directive + "\n", encoding="utf-8")
                with self.subTest(directive=directive), self.assertRaises(CobolError):
                    load_source(source, [], "free")

    def test_copy_quoted_punctuation_and_comment_punctuation_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy = root / "values;v1,part.cpy"
            copy.write_text("01 n pic 9 value 2.\n", encoding="utf-8")
            source = root / "source.cob"
            source.write_text('COPY "values;v1,part.cpy". *> ,; comment\n', encoding="utf-8")
            expanded, copies = load_source(source, [], "free")
            self.assertIn("01 n pic 9 value 2.", expanded)
            self.assertEqual(copies, [str(copy.resolve())])

    def test_copy_still_requires_a_whole_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "values.cpy").write_text("01 n pic 9.\n", encoding="utf-8")
            source = root / "source.cob"
            for directive in ['COPY "values.cpy". DISPLAY "BAD".',
                              'DISPLAY "BAD". COPY "values.cpy".']:
                source.write_text(directive + "\n", encoding="utf-8")
                with self.subTest(directive=directive), self.assertRaises(CobolError):
                    load_source(source, [], "free")


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SeparatorNativeTests(unittest.TestCase):
    def test_picture_adjacent_comments_match_native(self):
        data = ('01 text-a pic X(3)*> ignored\n value "ABC".\n'
                '01 number-a pic 9(3),*> ignored\n value 12.')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "picture-comments.cob"
            source.write_text(program(data, "display text-a number-a stop run."), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "ABC012\n")

    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURE, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"],
                         "VALUES:2203\nTEXT:A,B;CABC\nEDITED:+012.34\nINDEX:7\n")

    def test_fixed_original_keeps_separator_scope_and_literal_contents(self):
        contents = "\n".join("       " + line for line in [
            "identification division.", "program-id. fixed-separators.",
            "data division.", "working-storage section.", "01 first-a pic 9.",
            "01 second-a pic 9.", "procedure division.",
            "move 2 to first-a,second-a", "display first-a;second-a",
            'if first-a = 9 display "BAD";display "ALSO-BAD" end-if',
            'display "A,B;C";display 1,2', "stop run.",
        ]) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fixed.cob"
            source.write_text(contents, encoding="utf-8")
            report = verify(source, fmt="fixed")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "22\nA,B;C\n12\n")

    def test_repeated_subscript_separators_keep_the_unary_plus(self):
        data = "01 grid-a. 02 row-a occurs 2. 03 cell-a pic 9 occurs 2."
        body = ('move 7 to cell-a(1,,+2) display cell-a(1;;+2) '
                'move 8 to cell-a(1;+1) display cell-a(1,+1) stop run.')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "indices.cob"
            source.write_text(program(data, body), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "7\n8\n")

    def test_quoted_copy_name_with_punctuation_matches_gnucobol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "values;v1,part.cpy").write_text("01 n pic 9 value 2.\n", encoding="utf-8")
            source = root / "source.cob"
            source.write_text(program('COPY "values;v1,part.cpy".',
                                      "display n stop run."), encoding="utf-8")
            report = verify(source, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], "2\n")


if __name__ == "__main__":
    unittest.main()
