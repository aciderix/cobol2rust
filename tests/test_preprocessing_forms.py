from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cobol2rust import frontend
from cobol2rust.copy_replace import replace_statements
from cobol2rust.frontend import CobolError, Parser, lex, load_source, normalize
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


def replaced(text: str) -> str:
    return replace_statements(text, lex(text))


class ReplaceStatementTests(unittest.TestCase):
    def test_replace_applies_until_off_and_keeps_line_numbers(self):
        text = "replace ==a b== by ==c==.\nmove a\n  b to x.\nreplace off.\nmove a b to y.\n"
        result = replaced(text)
        self.assertEqual(result.count("\n"), text.count("\n"))
        self.assertIn("move c", result)
        self.assertIn("move a b to y.", result)
        self.assertNotIn("replace", result.lower())

    def test_a_new_replace_replaces_the_active_list(self):
        result = replaced("replace ==x== by ==y==. x. replace ==z== by ==w==. x z.")
        self.assertIn("y.", result)
        self.assertIn("x w.", result)

    def test_unmodelled_forms_are_refused(self):
        for text in ("replace also ==a== by ==b==.", "replace last off.", "replace ==a== by ==b=="):
            with self.subTest(text=text), self.assertRaises(CobolError):
                replaced(text)

    def test_copy_of_library_prefers_the_library_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lib").mkdir()
            (root / "lib" / "TEXT.cpy").write_text("display 'library'.\n", encoding="utf-8")
            (root / "TEXT.cpy").write_text("display 'plain'.\n", encoding="utf-8")
            source = root / "main.cob"
            source.write_text("procedure division.\ncopy TEXT of lib.\ncopy TEXT in 'missing'.\n", encoding="utf-8")
            expanded, copies = load_source(source, [], "free")
            self.assertIn("'library'", expanded)
            self.assertIn("'plain'", expanded)
            self.assertEqual(len(copies), 2)


class SyntaxFormTests(unittest.TestCase):
    def test_fixed_sequence_area_is_ignored(self):
        source = ("ABCDEF identification division.\n005900\n000300 program-id. seq-case.\n"
                  "000400 procedure division.\nXXXXXX     stop run.\n")
        self.assertEqual(Parser(normalize(source, "fixed")).parse().entry[0].op, "stop")

    def test_test_before_without_with_and_set_switch_groups(self):
        Parser(program("01 n pic 9.", "perform test before until n > 3 add 1 to n end-perform.")).parse()

    def test_homonymous_siblings_are_ambiguous_only_when_referenced(self):
        data = "01 g. 02 a pic x. 02 a pic x. 01 b pic xx."
        Parser(program(data, "move g to b.")).parse()
        with self.assertRaises(CobolError):
            Parser(program(data, "move a to b.")).parse()

    def test_reserved_words_follow_the_dialect(self):
        source = program("01 nothing pic x.", "move 'A' to nothing.")
        with self.assertRaises(CobolError):
            Parser(source).parse()
        previous = frontend.STD
        frontend.STD = "cobol85"
        try:
            Parser(source).parse()
            with self.assertRaises(CobolError):
                Parser(program("01 author pic x.", "move 'A' to author.")).parse()
        finally:
            frontend.STD = previous


class DecimalCommaTests(unittest.TestCase):
    SPECIAL = ("identification division. program-id. dc.\nenvironment division.\nconfiguration section.\n"
               "special-names. {}.\ndata division.\nworking-storage section.\n{}\nprocedure division.\n{}\n")

    def test_literals_and_pictures_take_the_comma(self):
        parsed = Parser(self.SPECIAL.format("decimal-point is comma", "01 e pic z.zz9,99. 01 n pic 9v9.",
                                            "move 1,5 to n.")).parse()
        self.assertEqual(parsed.entry[0].args[0].args[0], "1.5")
        self.assertEqual(parsed.fields["E"].picture, "Z,ZZ9.99")

    def test_currency_sign_replaces_the_dollar(self):
        parsed = Parser(self.SPECIAL.format('currency sign is "W"', "01 c pic ww9.", "stop run.")).parse()
        self.assertEqual(parsed.fields["C"].picture, "$$9")
        for special, data in (('currency sign is "W"', "01 c pic $9."), ('currency sign is "AB"', "01 c pic 9."),
                              ('currency sign is "Z"', "01 c pic 9."), ('currency "W" picture symbol "W"', "01 c pic 9.")):
            with self.subTest(special=special), self.assertRaises(CobolError):
                Parser(self.SPECIAL.format(special, data, "stop run.")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class PreprocessingNativeTests(unittest.TestCase):
    def test_decimal_comma_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "decimal_comma.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertIn("[1.234,50]\n[W234,50]\n", report["cobol_stdout"])

    def test_fixture_matches_native(self):
        report = verify(ROOT / "tests" / "fixtures" / "preprocessing.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertIn("from library 06\nfrom source directory\n", report["cobol_stdout"])
        self.assertIn("now E\n", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
