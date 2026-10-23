from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import fetch_corpora


class CorpusFetchTests(unittest.TestCase):
    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            marker = output / "user-file"
            marker.write_bytes(b"preserve me")
            with (patch.object(fetch_corpora, "clone_pinned") as clone,
                  self.assertRaisesRegex(ValueError, "inexistant")):
                fetch_corpora.fetch(output, ["carddemo"], with_gnucobol=False)
            clone.assert_not_called()
            self.assertEqual(list(output.iterdir()), [marker])

    def test_repositories_are_pinned_to_full_commits(self):
        for name, (url, commit, license_name, _) in fetch_corpora.REPOSITORIES.items():
            with self.subTest(name=name):
                self.assertTrue(url.startswith("https://github.com/"))
                self.assertRegex(commit, r"^[0-9a-f]{40}$")
                self.assertTrue(license_name)

    def test_inventory_counts_cobol_sources_outside_git(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ("src/A.CBL", "src/b.cob", "copy/C.cpy", "notes.txt", ".git/objects/x.cbl"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            self.assertEqual(fetch_corpora.inventory(root), {".cbl": 1, ".cob": 1, ".cpy": 1})

    def test_manifest_records_commits_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "corpora"
            def fake_clone(url, commit, destination):
                destination.mkdir()
                (destination / "MAIN.cbl").write_text("", encoding="utf-8")
            with patch.object(fetch_corpora, "clone_pinned", side_effect=fake_clone):
                manifest = fetch_corpora.fetch(output, ["zopeneditor-sample"], with_gnucobol=False)
            entry = manifest["corpora"][0]
            self.assertEqual(entry["commit"], fetch_corpora.REPOSITORIES["zopeneditor-sample"][1])
            self.assertEqual(entry["cobol_files"], {".cbl": 1})
            self.assertFalse(manifest["programs_executed"])
            self.assertTrue((output / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
