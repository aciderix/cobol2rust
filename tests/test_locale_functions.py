from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify

FIXTURES = ROOT / "tests" / "fixtures"


def program(body):
    return ("identification division.\nprogram-id. loc.\ndata division.\nworking-storage section.\n"
            f"01 l pic x(8) value 'C'.\nprocedure division.\n{body}\nstop run.\n")


class LocaleFunctionTests(unittest.TestCase):
    def test_locale_argument_is_a_reference(self):
        # locale_dt_args: exp [_e_sep reference]; LOCALE-COMPARE takes any expression.
        with self.assertRaisesRegex(CobolError, "expecting Identifier"):
            Parser(program('display function locale-date ("19630302", "C").')).parse()
        Parser(program('display function locale-date ("19630302", l) function locale-compare ("a", "b", "C").')).parse()

    def test_cob_init_locale_only_when_used(self):
        # cob_init's setlocale (LC_ALL, "") matters to these functions alone.
        with_locale, _ = Emitter(Parser(program("display function currency-symbol.")).parse()).generate()
        without, _ = Emitter(Parser(program("display 'x'.")).parse()).generate()
        self.assertIn("runtime::locale::init();", with_locale)
        self.assertNotIn("runtime::locale::init();", without)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class LocaleFunctionNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(FIXTURES / "locale_functions.cob", fmt="fixed")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertEqual(lines[:3], ["[][.][][][]", "<>=>>", "03/02/63 11/01/26 03/02/63 03"])
        self.assertIn("23:30:12 24:00:00 09:10:12 24:00:00", lines)


if __name__ == "__main__":
    unittest.main()
