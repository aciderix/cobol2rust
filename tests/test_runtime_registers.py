from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class ParseTests(unittest.TestCase):
    def test_accept_from_clock_registers(self):
        entry = Parser(program("01 d pic 9(8). 01 x pic x(4).",
                               "accept d from date yyyymmdd. accept x from day-of-week. accept d from time.")).parse().entry
        clocks = [s.args[1] for s in entry if s.op == "accept_clock"]
        self.assertEqual(clocks, ["DATE YYYYMMDD", "DAY-OF-WEEK", "TIME"])

    def test_random_takes_zero_or_one_argument(self):
        Emitter(Parser(program("01 v pic 9v9(5).", "compute v = function random. compute v = function random(3).")).parse()).generate()
        with self.assertRaises(CobolError):
            Parser(program("01 v pic 9v9(5).", "compute v = function random(1 2).")).parse()

    def test_mixed_literal_comparison_folds_like_compare_field_literal(self):
        source = program("01 d pic 9v9.", "if d = \"22\" display \"x\" end-if. if d = \"22 \" display \"y\" end-if.")
        emitter = Emitter(Parser(source).parse())
        rust = "\n".join(emitter.program_lines()[0])
        # "22" has more integer digits than 9V9: FALSE; "22 " is alphanumeric: cob_cmp.
        self.assertIn("pc = if false", rust)
        self.assertIn("comparison_text()", rust)

    def test_sort_record_with_odo_only_for_using_and_giving(self):
        def source(statement):
            return ("identification division.\nprogram-id. s.\nenvironment division.\ninput-output section.\n"
                    "file-control.\n    select w assign to \"W\".\ndata division.\nfile section.\n"
                    "sd w.\n01 r. 02 k pic x. 02 t pic x occurs 1 to 3 depending on n.\n"
                    "working-storage section.\n01 n pic 9 value 3.\nprocedure division.\n" + statement + "\n stop run.\n")
        Parser(source("continue.")).parse()
        for statement in ("release r.", "return w at end continue end-return."):
            with self.subTest(statement=statement), self.assertRaises(CobolError):
                Parser(source(statement)).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NativeTests(unittest.TestCase):
    def fixture(self, name, **options):
        source = ROOT / "tests" / "fixtures" / f"{name}.cob"
        config = source.with_suffix(".json")
        if config.exists():
            options.setdefault("runtime_env", json.loads(config.read_text(encoding="utf-8"))["runtime_env"])
        report = verify(source, fmt="free", **options)
        self.assertTrue(report["match"], report)
        return report

    def test_clock_registers_follow_cob_current_date(self):
        report = self.fixture("clock_accept")
        # 30 February 2026 is normalized to 2 March by mktime; ".99" is read
        # as 99 nanoseconds, so the hundredths are 00.
        self.assertIn("260302 20260302 26061 2026061 1 [1 ]\n", report["cobol_stdout"])
        self.assertIn("2026030210111200-0500\n", report["cobol_stdout"])
        for value in ("2024/02/29 13:45:07.123456789", "YYYY/MM/15 01:02:03.04", "24/03/01 01:02:03.5+0130"):
            with self.subTest(value=value):
                self.fixture("clock_accept", runtime_env={"COB_CURRENT_DATE": value})

    def test_random_matches_gmp_mersenne_twister(self):
        report = self.fixture("random_function")
        self.assertTrue(report["cobol_stdout"].startswith("0.65712178890805361\n0.55413637240866164\n"))

    def test_character_03_raises_sigint_like_cob_accept(self):
        source = ROOT / "tests" / "fixtures" / "stop_literal.cob"
        # STOP literal: the line is discarded; 03 kills both runs with SIGINT.
        report = verify(source, fmt="free", stdin=b"YES\nok\x03\n")
        self.assertTrue(report["match"], report)
        self.assertEqual((report["cobol_exit"], report["rust_exit"]), (-2, -2))
        self.assertEqual(report["cobol_stdout"], "first\nanswer [YES ]\nOPERATOR\n")
        report = verify(source, fmt="free", stdin=b"YES\n\nab\x03cd\n")
        self.assertTrue(report["match"], report)
        self.assertTrue(report["cobol_stdout"].endswith("after stop\n"))
        report = verify(source, fmt="free", stdin=b"Y\x03\n")
        self.assertTrue(report["match"], report)
        # libcob would lose the stdio buffers of a file still open: named stop.
        with tempfile.TemporaryDirectory() as directory:
            opened = Path(directory) / "stop_open.cob"
            opened.write_text(source.read_text(encoding="utf-8").replace("    close out-file.\n", "")
                              .replace("    stop run.", "    close out-file.\n    stop run."), encoding="utf-8")
            report = verify(opened, fmt="free", stdin=b"YES\n\x03\n")
            self.assertEqual((report["cobol_exit"], report["rust_exit"]), (-2, 70))
            self.assertIn("SIGINT (character 03 read by ACCEPT) with open files not modelled", report["rust_stderr"])

    def test_mixed_literal_comparisons(self):
        report = self.fixture("mixed_literal_compare")
        self.assertIn("2 ne\n", report["cobol_stdout"])
        self.assertIn("b4 eq\n", report["cobol_stdout"])
        # P-scaled items compare their stored digits (99P 120: "12").
        self.assertIn("d1 eq\nd2 ne\nd3 lt\nd4 eq\nd5 ne\n", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
