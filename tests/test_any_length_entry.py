"""Descripteurs ANY LENGTH persistants et ordre des paramètres ENTRY de cobc."""
from __future__ import annotations

import unittest

from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


FIXTURE = ROOT / "tests" / "fixtures" / "any_length_entry.cob"
EXPECTED_STDOUT = (
    "main|000000001|000000001|\n"
    "second|000000004|000000001|\n"
    "main|000000006|000000003|\n"
    "second|000000004|000000003|\n"
    "swap|000000003|000000006|\n"
    "main|000000003|000000006|\n"
    "main|000000003|000000006|\n"
    "main|000000004|000000003|\n"
    "initial|000000001|\n"
    "initial|000000006|\n"
    "initial|000000006|\n"
    "initial|000000003|\n"
    "initial|000000003|\n"
)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class AnyLengthEntryNativeTests(unittest.TestCase):
    def test_entry_parameter_order_and_cached_lengths_match_gnucobol(self):
        # codegen.c preserves field sizes across CANCEL/INITIAL and uses the
        # union's parameter ranks for ENTRY, including its documented bug #902.
        report = verify(FIXTURE, fmt="free")
        self.assertTrue(report["match"], report)
        self.assertEqual(report["cobol_stdout"], EXPECTED_STDOUT, report)
        self.assertEqual(report["rust_stdout"], EXPECTED_STDOUT, report)


if __name__ == "__main__":
    unittest.main()
