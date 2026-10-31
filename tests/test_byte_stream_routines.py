from __future__ import annotations

import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser, call_content
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body):
    return ("identification division.\nprogram-id. routine-case.\ndata division.\nworking-storage section.\n"
            "01 fname pic x(8) value 'a.dat'.\n01 fh pic x(4) comp-x.\n01 cwd pic x(64).\n"
            f"procedure division.\n{body}\nstop run.\n")


class CallContentTests(unittest.TestCase):
    def test_output_call_content_bytes(self):
        # cb_fits_int: a native int; otherwise cb_get_[u_]long_long of the
        # digits without the decimal point, in 8 bytes.
        cases = {"55": (55).to_bytes(4, "little"), "-3": (-3).to_bytes(4, "little", signed=True),
                 "2147483647": (2147483647).to_bytes(4, "little"),
                 "2147483648": (2147483648).to_bytes(8, "little"), "1.5": (15).to_bytes(8, "little"),
                 "-12345678901": (-12345678901).to_bytes(8, "little", signed=True)}
        for text, data in cases.items():
            with self.subTest(text=text):
                self.assertEqual(call_content(text).encode("latin-1"), data)

    def test_literals_become_content_arguments(self):
        stmt = next(s for s in Parser(program("call 'CBL_OPEN_FILE' using fname 1 0 0 fh.")).parse().entry
                    if s.op == "call_program")
        self.assertEqual([mode for mode, _ in stmt.args[1]], ["REFERENCE", "CONTENT", "CONTENT", "CONTENT", "REFERENCE"])

    def test_current_dir_needs_c_ints_by_value(self):
        rust = Emitter(Parser(program("call 'CBL_GET_CURRENT_DIR' using by value 0 by value 64 cwd.")).parse()).generate()[0]
        self.assertIn("file_runtime::routines::call", rust)
        self.assertIn("mod file_runtime;", rust)


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class ByteStreamNativeTests(unittest.TestCase):
    def test_routines_match_native(self):
        # fileio.c: open_cbl_file, CBL_READ_FILE size flag and end of file,
        # errno_cob_sts, wrong access mode warning, copy, rename, check,
        # directories, CBL_GET_CURRENT_DIR return codes.
        report = verify(ROOT / "tests" / "fixtures" / "byte_stream_routines.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        self.assertIn("read +000000000 [3456      ]\nsize +000000000 000000000000000015\nend +000000010\n", stdout)
        self.assertIn("missing +000000035 294967295\nmode -000000001\n", stdout)
        self.assertEqual(report["cobol_stderr"], "libcob: warning: call to CBL_OPEN_FILE with wrong access mode: 9\n")


if __name__ == "__main__":
    unittest.main()
