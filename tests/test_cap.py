"""Garde du cap : la boussole du projet doit rester en place et à jour (CAP.md)."""
import json
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import real_corpora  # noqa: E402


class CapTest(unittest.TestCase):
    def test_compass_documents(self):
        cap = (ROOT / "CAP.md").read_text(encoding="utf-8")
        for marker in ("<!-- cap:début -->", "<!-- cap:fin -->", real_corpora.MARK_BEGIN, real_corpora.MARK_END,
                       "## Journal du cap"):
            self.assertIn(marker, cap)
        self.assertIn("CAP.md", (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_compass_hook_runs_at_every_session_start(self):
        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        groups = settings["hooks"]["SessionStart"]
        # Sans filtre « matcher », le hook s'exécute aussi après une compression.
        commands = [hook["command"] for group in groups if not group.get("matcher") for hook in group["hooks"]]
        self.assertTrue(any(command.endswith("compass.sh") for command in commands))

    def test_measurement_covers_every_pinned_corpus(self):
        summary = json.loads(real_corpora.SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(set(summary["corpora"]), set(real_corpora.CORPORA))
        self.assertIsNotNone(summary["cobc"])
        self.assertTrue(real_corpora.HISTORY.read_text(encoding="utf-8").strip())

    @unittest.skipUnless((real_corpora.CORPORA_DIR / "manifest.json").exists() and shutil.which("cobc"),
                         "corpus réels ou cobc absents : la mesure ne peut pas être refaite ici")
    def test_measurement_describes_current_converter(self):
        self.assertIsNone(real_corpora.stale(),
                          "convertisseur modifié sans nouvelle mesure : python3 tools/real_corpora.py --cobc --record")


if __name__ == "__main__":
    unittest.main()
