from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program

DATA = "01 x pic x(8). 01 n pic 99. 01 p pic s9(3) comp-3. 01 b pic 9(4) comp. 01 e pic z9."


class InspectSyntaxTests(unittest.TestCase):
    def test_accepted_forms(self):
        for body in ('inspect x tallying n for characters before initial "A" after "B".',
                     'inspect x tallying n for all "A" "B" leading space n for characters.',
                     'inspect x replacing characters by "." all "A" by "B" "C" by "D" first "E" by zero.',
                     'inspect x tallying n for all "A" replacing leading "A" by "B" after "C".',
                     'inspect x converting "AB" to "CD" before "Z".',
                     'inspect x(2:3) converting "AB" to quote.',
                     'inspect x replacing all "AB" by all "CD".',
                     'inspect x tallying n for all characters.'):
            with self.subTest(body=body):
                Emitter(Parser(program(DATA, body)).parse()).generate()

    def test_cobc_errors_are_refused(self):
        for body in ('inspect x tallying n for first "A".',
                     'inspect x tallying for all "A".',
                     'inspect x tallying n for all.',
                     'inspect x replacing "A" by "B".',
                     'inspect x replacing all "AB" by "C".',
                     'inspect x replacing all "A" by all "BC".',
                     'inspect x replacing characters by "AB".',
                     'inspect x converting "AB" to all "C".',
                     'inspect x tallying n for all 5.',
                     'inspect x tallying n for all p.',
                     'inspect x tallying e for characters.',
                     'inspect "ABC" tallying n for characters.',
                     'inspect backward x tallying n for characters.'):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(DATA, body)).parse()).generate()

    def test_binary_and_packed_targets_are_refused(self):
        # cobc accepts them; their sign handling is not modelled here.
        for body in ('inspect p tallying n for all "1".', 'inspect b replacing all "1" by "2".'):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Emitter(Parser(program(DATA, body)).parse()).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class InspectNativeTests(unittest.TestCase):
    def test_inspect_matches_libcob(self):
        report = verify(ROOT / "tests" / "fixtures" / "inspect_statement.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # LEADING counts AA but marks only its first byte: ALL counts it again.
        self.assertIn("leading-quirk 07", lines)
        # A tally counter overflow keeps the low-order digits (cob_add_int, opt 0).
        self.assertIn("m 0", lines)

    def test_static_markers_persist_between_statements(self):
        report = verify(ROOT / "tests" / "fixtures" / "inspect_markers.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"].splitlines(), ["03", "06", "08", "3000", "08"])


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class EvaluateNativeTests(unittest.TestCase):
    def test_evaluate_forms_match_cobc(self):
        report = verify(ROOT / "tests" / "fixtures" / "evaluate_forms.cob", fmt="free")
        self.assertTrue(report["match"], report)
        # Consecutive WHEN lines share the statements that follow them.
        self.assertTrue(report["cobol_stdout"].startswith("01 one or two\n"))

    def test_nested_if_group_conditions_and_mixed_set(self):
        report = verify(ROOT / "tests" / "fixtures" / "nested_conditions.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"].splitlines()[:3], ["a1", "b2", "c3"])

    def test_abbreviated_sign_and_class_conditions(self):
        # cb_build_expr: abbreviated relations, NOT placement, POSITIVE/NEGATIVE/ZERO.
        report = verify(ROOT / "tests" / "fixtures" / "abbreviated_conditions.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertEqual((lines[2], lines[21]), ("3 no", "22 no"))

    def test_string_and_unstring_match_libcob(self):
        report = verify(ROOT / "tests" / "fixtures" / "string_unstring.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertIn("**XYZ12abAB* 12", report["cobol_stdout"].splitlines())

    def test_reserved_words_are_refused_like_cobc(self):
        from tests.test_numeric_move import program
        for data in ("01 nothing pic 9.", "01 g. 05 test pic x."):
            with self.subTest(data=data), self.assertRaises(CobolError):
                Parser(program(data)).parse()

    def test_renames_larger_redefines_and_exponentiation(self):
        for name in ("renames.cob", "exponentiation.cob", "figurative_numeric.cob", "negative_zero.cob",
                     "corresponding.cob", "display_truncation.cob", "deediting.cob", "copy_replacing.cob",
                     "intrinsic_functions.cob"):
            with self.subTest(name=name):
                report = verify(ROOT / "tests" / "fixtures" / name, fmt="free")
                self.assertTrue(report["match"], report)
        from tests.test_numeric_move import program
        from cobol2rust.emitter import Emitter
        with self.assertRaises(CobolError):
            Emitter(Parser(program("01 c pic 9v99.", "compute c = 3 ** -1.")).parse()).generate()
