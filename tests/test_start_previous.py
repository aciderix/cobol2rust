from __future__ import annotations

import unittest

from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body, organization="indexed"):
    key = "record key k" if organization == "indexed" else "relative key n"
    return ("identification division.\nprogram-id. start-case.\nenvironment division.\ninput-output section.\n"
            f"file-control.\nselect f assign 'f.dat' organization {organization} access dynamic {key}.\n"
            "select s assign 's.dat'.\n"
            "data division.\nfile section.\nfd f.\n01 r.\n 05 k pic x(3).\nfd s.\n01 sr pic x.\n"
            "working-storage section.\n01 n pic 99.\nprocedure division.\n"
            f"{body}\nstop run.\n")


class StartFrontendTests(unittest.TestCase):
    def test_start_operators_follow_start_op(self):
        cases = {"key < k": "Less", "key <= k": "NotGreater", "key not > k": "NotGreater",
                 "key not >= k": "Less", "key is less than or equal to k": "NotGreater",
                 "key not <= k": "Greater", "key not < k": "NotLess", "key greater or equal k": "NotLess",
                 "first": "First", "last": "Last", "key = k": "Equal"}
        for phrase, condition in cases.items():
            with self.subTest(phrase=phrase):
                stmt = next(s for s in Parser(program(f"start f {phrase}.")).parse().entry if s.op == "start")
                self.assertEqual(stmt.args[2], condition)

    def test_cobc_errors(self):
        for body, organization in [("start f key not = k.", "indexed"),
                                   ("start f with size 2.", "indexed"),
                                   ("start f key < n with length 2.", "relative"),
                                   ("read s previous.", "indexed")]:
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program(body, organization)).parse()
        stmt = next(s for s in Parser(program("read f previous.")).parse().entry if s.op == "read")
        self.assertTrue(stmt.args[5])


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class StartNativeTests(unittest.TestCase):
    def test_start_conditions_and_read_previous_match_native(self):
        # indexed_start_internal and relative_start (LT, LE, FIRST, LAST,
        # WITH LENGTH), then indexed_read_next / relative_read_next PREVIOUS.
        report = verify(ROOT / "tests" / "fixtures" / "start_previous.cob", fmt="free")
        self.assertTrue(report["match"], report)
        stdout = report["cobol_stdout"]
        self.assertTrue(stdout.startswith("after open 10\n"))
        # relative_read_next steps back two slots after a READ PREVIOUS.
        self.assertTrue(stdout.endswith("00 [09] 09\n00 [08] 08\n00 [05] 05\n00 [02] 02\n10 [02] 02\n46 [02] 02\n"))


if __name__ == "__main__":
    unittest.main()
