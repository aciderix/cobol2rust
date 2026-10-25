from __future__ import annotations

import unittest

from cobol2rust.control import ControlGraph
from cobol2rust.emitter import Emitter
from cobol2rust.frontend import Parser
from cobol2rust.toolchain import ROOT, find_tool
from cobol2rust.verification import verify
from tests.test_numeric_move import program


class NextSentenceTests(unittest.TestCase):
    def test_jumps_to_statement_after_next_period(self):
        parsed = Parser(program("01 n pic 9.", "if n = 0 next sentence end-if display 'a'. display 'b'. stop run.")).parse()
        self.assertEqual([stmt.op for stmt in parsed.entry],
                         ["if", "display", "sentence_end", "display", "sentence_end", "stop", "sentence_end"])
        graph = ControlGraph(parsed, parsed.blocks)
        jump = next(node for node in graph.nodes if node.stmt is not None and node.stmt.op == "next_sentence")
        target = graph.nodes[jump.args[0]]
        self.assertEqual((target.stmt.op, target.stmt.line), ("display", parsed.entry[3].line))
        Emitter(parsed).generate()


@unittest.skipUnless(find_tool("cobc") and find_tool("cargo"), "GnuCOBOL and Cargo required")
class NextSentenceNativeTests(unittest.TestCase):
    def test_fixture_matches_gnucobol(self):
        report = verify(ROOT / "tests" / "fixtures" / "next_sentence.cob", fmt="free")
        self.assertTrue(report["match"], report)
        self.assertNotIn("never", report["cobol_stdout"])
        # NEXT SENTENCE leaves an inline PERFORM too.
        self.assertIn("after loop 3", report["cobol_stdout"])


if __name__ == "__main__":
    unittest.main()
