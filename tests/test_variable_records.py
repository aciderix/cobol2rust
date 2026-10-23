from __future__ import annotations

import hashlib
import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_files import file_program


def sequential(fd, storage="01 fs pic xx. 01 len pic 99."):
    return file_program(select='select f assign to "v.dat" organization sequential file status fs.',
                        fd=fd, storage=storage)


class VariableRecordTests(unittest.TestCase):
    def test_limits_follow_cobc_finalize_file(self):
        cases = {
            "fd f record varying from 3 to 10 depending on len. 01 a pic x(5). 01 b pic x(8).": (3, 10, "LEN"),
            "fd f. 01 a pic x(4). 01 b pic x(9).": (4, 9, None),
            "fd f record contains 2 to 6 characters. 01 a pic x(4).": (2, 6, None),
            "fd f record is varying in size to 6. 01 a pic x(4).": (4, 6, None),
            "fd f record varying from 5. 01 a pic x(3). 01 b pic x(7).": (3, 7, None),
        }
        for fd, expected in cases.items():
            with self.subTest(fd=fd):
                spec = Parser(sequential(fd)).parse().files["F"]
                self.assertEqual((spec.record_min, spec.record_max, spec.depending), expected)

    def test_unmodelled_variable_forms_are_refused(self):
        for fd in ("fd f record varying from 3 to 5 depending on a. 01 a pic 9.",
                   "fd f record varying depending on txt. 01 a pic x(5).",
                   "fd f record contains 2 to 6 depending on len. 01 a pic x(4).",
                   "fd f record varying from 6 to 4. 01 a pic x(5)."):
            with self.subTest(fd=fd), self.assertRaises(CobolError):
                Parser(sequential(fd, "01 fs pic xx. 01 len pic 99. 01 txt pic x.")).parse()
        with self.assertRaises(CobolError):
            Parser(file_program(fd="fd f. 01 a pic x(4). 01 b pic x(9).")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class VariableRecordNativeTests(unittest.TestCase):
    def test_fixture_matches_native_headers_and_slots(self):
        report = verify(ROOT / "tests" / "fixtures" / "variable_records.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        self.assertIn("W2 44", lines)
        # READ INTO moves the record as read, 5 bytes, padded with spaces.
        self.assertIn("R3 00 05 [VWXYZ67*] [VWXYZ       ]", lines)
        header = lambda size: size.to_bytes(2, "big") + b"\0\0"
        expected = (header(4) + b"ABCD" + header(7) + b"1234567" + header(5) + b"VWXYZ"
                    + header(8) + b"VWXYZ67 ")
        self.assertEqual(report["cobol_files"]["var.dat"],
                         {"bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest()})


if __name__ == "__main__":
    unittest.main()
