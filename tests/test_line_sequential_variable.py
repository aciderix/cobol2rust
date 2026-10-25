from __future__ import annotations

import unittest

from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class LineSequentialVariableTests(unittest.TestCase):
    def test_records_of_several_sizes_match_libcob(self):
        report = verify(ROOT / "tests" / "fixtures" / "line_sequential_variable.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertTrue(report["files_match"], report)
        # READ INTO moves the bytes stored by lineseq_read (record->size = i).
        self.assertIn("r 00 [LONGREC1  ] [LONGREC1] [LON]\n", report["cobol_stdout"])
        # A LINE SEQUENTIAL record_min is 0: a 2-byte record below FROM 5 is written.
        self.assertIn("g 00 02 [AB        ]", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
