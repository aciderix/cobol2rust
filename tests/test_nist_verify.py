from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import nist_verify


class NistVerifyTests(unittest.TestCase):
    def corpus(self, root: Path, names: list[str]) -> Path:
        (root / "SQ").mkdir(parents=True)
        for name in names:
            (root / "SQ" / name).write_text("", encoding="utf-8")
        return root

    def test_sub_programs_replay_programs_since_the_last_cbl(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.corpus(Path(temp), ["SQ101A.CBL", "SQ102A.SUB", "SQ103A.SUB", "SQ104A.CBL"])
            source, chain = nist_verify.predecessors(root, "SQ103A")
            self.assertEqual(source.name, "SQ103A.SUB")
            self.assertEqual([path.name for path in chain], ["SQ101A.CBL", "SQ102A.SUB"])
            # The runner removes XXXXX* before every .CBL: it starts from nothing.
            source, chain = nist_verify.predecessors(root, "SQ104A")
            self.assertEqual(chain, [])

    def test_unknown_or_orphan_programs_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.corpus(Path(temp), ["SQ100A.SUB", "SQ101A.CBL"])
            with self.assertRaisesRegex(ValueError, "introuvable"):
                nist_verify.predecessors(root, "SQ999A")
            with self.assertRaisesRegex(ValueError, "aucun programme principal"):
                nist_verify.predecessors(root, "SQ100A")

    def test_runner_counts_are_read_from_report_txt(self):
        with tempfile.TemporaryDirectory() as temp:
            logs = Path(temp)
            (logs / "SQ").mkdir()
            (logs / "SQ" / "report.txt").write_text(
                "Filename    total pass fail deleted inspect\n"
                "SQ101A.CBL      9    8    1       0       0 OK\n", encoding="utf-8")
            self.assertEqual(nist_verify.runner_counts(logs, "SQ101A"),
                             {"total": 9, "pass": 8, "fail": 1, "deleted": 0, "inspect": 0})
            self.assertIsNone(nist_verify.runner_counts(logs, "SQ102A"))


if __name__ == "__main__":
    unittest.main()
