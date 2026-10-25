from __future__ import annotations

import hashlib
import unittest

from cobol2rust.emitter import Emitter
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_files import file_program

SEQUENTIAL = 'select f assign to "data.bin" organization sequential file status fs.'


class SequentialIoTests(unittest.TestCase):
    def test_open_i_o_and_rewrite_are_parsed(self):
        parsed = Parser(file_program("open i-o f read f rewrite rec from 'AB' end-rewrite "
                                     "rewrite rec close f stop run.", select=SEQUENTIAL)).parse()
        self.assertEqual([s.op for s in parsed.entry[:4]], ["open", "read", "rewrite", "rewrite"])
        self.assertEqual(parsed.entry[0].args[0], [("I-O", "F")])
        Emitter(parsed).generate()

    def test_unmodelled_rewrites_are_refused(self):
        cases = [
            file_program("open i-o f stop run."),  # LINE SEQUENTIAL rewrites shift lines
            file_program("open i-o f rewrite rec invalid key display 'x' stop run.", select=SEQUENTIAL),
            file_program("rewrite fs stop run.", select=SEQUENTIAL),
        ]
        for source in cases:
            with self.subTest(source=source[-60:]), self.assertRaises(CobolError):
                Parser(source).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SequentialIoNativeTests(unittest.TestCase):
    def test_fixture_matches_native_statuses_and_bytes(self):
        report = verify(ROOT / "tests" / "fixtures" / "sequential_io.cob", fmt="free")
        self.assertTrue(report["match"], report)
        for line in ("G-IO 35", "H-IO 05", "RW-NOREAD 43", "RW-TWICE 43", "WRITE-IO 48",
                     "RW-EOF 43", "RW-INPUT 49"):
            self.assertIn(line, report["cobol_stdout"].splitlines())
        expected = b"aaabbbCCC"
        self.assertEqual(report["cobol_files"]["seq.dat"],
                         {"bytes": 9, "sha256": hashlib.sha256(expected).hexdigest()})
        # A missing OPTIONAL file opened I-O is created empty, as natively.
        self.assertEqual(report["rust_files"]["optional.dat"]["bytes"], 0)


if __name__ == "__main__":
    unittest.main()
