from __future__ import annotations

import unittest

from cobol2rust.control import ControlGraph
from cobol2rust.frontend import CobolError, Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify


def program(body, select="", fd=""):
    return ("identification division.\nprogram-id. sort-case.\nenvironment division.\ninput-output section.\n"
            "file-control.\n select s assign to 'W'.\n select f assign to 'F' organization sequential.\n" + select +
            "data division.\nfile section.\nsd s.\n01 s-rec.\n 05 k pic 99.\n 05 t pic x(3).\n"
            "fd f.\n01 f-rec pic x(5).\n" + fd + "working-storage section.\n01 w pic x(5).\n"
            "procedure division.\n" + body + "\n")


class SortTests(unittest.TestCase):
    def test_sort_is_lowered_like_cobc(self):
        parsed = Parser(program("sort s on descending key k ascending t using f giving f. stop run.")).parse()
        graph = ControlGraph(parsed, parsed.blocks)
        ops = [node.op for node in graph.nodes]
        for op in ("sort_init", "sort_using", "sort_giving", "sort_close"):
            self.assertIn(op, ops)
        self.assertTrue(parsed.files["S"].sort)

    def test_refusals(self):
        for body in ("sort s on ascending key w using f giving f.",
                     "sort s on ascending key k collating sequence is x using f giving f.",
                     "merge s on ascending key k using f giving f.",
                     "open input s.",
                     "release f-rec."):
            with self.subTest(body=body), self.assertRaises(CobolError):
                Parser(program(body + " stop run.")).parse()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class SortNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "sort_merge.cob", fmt="free")
        self.assertTrue(report["match"], report)
        lines = report["cobol_stdout"].splitlines()
        # After GIVING the SD area holds the last record returned.
        self.assertEqual(lines[0], "s-rec after using/giving [05AAA000A3]")
        # MERGE behaves as a stable sort of the USING files in order.
        self.assertEqual(lines[-1], "merged [05BBB00r]")


if __name__ == "__main__":
    unittest.main()
