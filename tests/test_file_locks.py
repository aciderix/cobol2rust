from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(select, body):
    return ("identification division.\nprogram-id. lock-unit.\nenvironment division.\ninput-output section.\n"
            f"file-control.\n    select f assign 'f.dat' organization sequential {select}.\n"
            "data division.\nfile section.\nfd f. 01 r pic x(4).\nprocedure division.\n" f"{body}\nstop run.\n")


class LockGrammarTests(unittest.TestCase):
    def test_clauses_and_open_options(self):
        parsed = Parser(program("lock mode is manual with lock on multiple records sharing with no other",
                                "open input sharing with all other retry 3 times f with no rewind.\n"
                                "open exclusive i-o f. open output f with lock. open extend f allowing readers.\n"
                                "read f with ignore lock end-read. unlock f records.")).parse()
        spec = parsed.files["F"]
        self.assertEqual((spec.lock_mode, spec.sharing), (2 | 8, True))
        opens = [s for s in parsed.entry if s.op == "open"]
        # cb_emit_open: the OPEN's option, else the SELECT's SHARING.
        self.assertEqual([s.sharings for s in opens], [[True], [True], [True], [True]])
        self.assertIn("unlock", [s.op for s in parsed.entry])

    def test_cobc_errors(self):
        for select, body, message in [
                ("lock mode automatic", "read f with lock end-read.", "invalid with file LOCK AUTOMATIC"),
                ("lock mode automatic", "write r with no lock.", "invalid with file LOCK AUTOMATIC"),
                ("", "write r before advancing 1 line with lock.", "LOCK clause invalid here"),
                ("", "open input sharing with no other f with lock.", "mutually exclusive"),
                ("lock mode exclusive with mass-update", "stop run.", "only valid with ORGANIZATION INDEXED"),
                ("lock mode manual lock mode manual", "stop run.", "duplicate LOCK"),
                ("", "open input f with no rewind f.", "")]:
            with self.subTest(select=select, body=body), self.assertRaisesRegex(CobolError, message):
                Parser(program(select, body)).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class LockNativeTests(unittest.TestCase):
    def test_whole_file_locks_match_native_across_processes(self):
        directory = ROOT / "tests" / "fixtures" / "file_locks"
        report = verify(directory / "lock-main.cob", fmt="free", companions=[directory / "lock-probe.cob"])
        self.assertTrue(report["match"] and report["stderr_match"], report)
        self.assertEqual(report["cobol_stdout"].split("\n")[:6],
                         ["writers", "probe 61 61 61 00 61", "unlocked 00 00 00", "probe 00 61 00 00 61",
                          "readers", "probe 00 61 61 00 00"])


if __name__ == "__main__":
    unittest.main()
