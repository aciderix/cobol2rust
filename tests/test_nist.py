from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import prepare_nist


class NistPreparationTests(unittest.TestCase):
    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            marker = output / "user-file"
            marker.write_bytes(b"preserve me")
            with self.assertRaisesRegex(ValueError, "inexistant"):
                prepare_nist.prepare(output)
            self.assertEqual(marker.read_bytes(), b"preserve me")
            self.assertEqual(list(output.iterdir()), [marker])

    def test_corrupt_download_stops_before_compilation(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "nist"
            with (patch.object(prepare_nist.shutil, "which", return_value="unused-tool"),
                  patch.object(prepare_nist, "build_opener") as opener,
                  patch.object(prepare_nist, "run") as run):
                opener.return_value.open.return_value = io.BytesIO(b"corrupt archive")
                with self.assertRaisesRegex(ValueError, "SHA256 incorrect"):
                    prepare_nist.prepare(output)
                run.assert_not_called()
                self.assertFalse((output / "manifest.json").exists())
                self.assertEqual(list((output / "extracted").iterdir()), [])

    def test_mirror_is_used_only_after_network_error(self):
        name = "newcob.val.tar.gz"
        url, _ = prepare_nist.ASSETS[name]
        mirror = prepare_nist.MIRRORS[name][0]
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / name
            def fake_download(candidate, path, expected):
                path.write_bytes(b"partial")
                if candidate == url:
                    raise prepare_nist.URLError("HTTP Error 403: Forbidden")
            with patch.object(prepare_nist, "download", side_effect=fake_download) as download:
                self.assertEqual(prepare_nist.download_asset(name, destination), mirror)
            self.assertEqual([call.args[0] for call in download.call_args_list], [url, mirror])
            destination.unlink()
            with (patch.object(prepare_nist, "download",
                               side_effect=ValueError("SHA256 incorrect")) as download,
                  self.assertRaisesRegex(ValueError, "SHA256 incorrect")):
                prepare_nist.download_asset(name, destination)
            self.assertEqual(download.call_count, 1)

    def test_unsafe_archive_members_are_rejected(self):
        for name, member_type in [("../escape", tarfile.REGTYPE),
                                  ("newcob.val", tarfile.SYMTYPE)]:
            with self.subTest(name=name, member_type=member_type), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root / "corpus.tar.gz"
                with tarfile.open(archive, "w:gz") as package:
                    member = tarfile.TarInfo(name)
                    member.type = member_type
                    member.linkname = "../escape" if member_type == tarfile.SYMTYPE else ""
                    package.addfile(member)
                destination = root / "output"
                destination.mkdir()
                with self.assertRaisesRegex(ValueError, "Archive NIST inattendue"):
                    prepare_nist.extract_archive(archive, destination)
                self.assertEqual(list(destination.iterdir()), [])
                self.assertFalse((root / "escape").exists())

    def test_missing_modules_cannot_produce_successful_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "NC").mkdir()
            (root / "NC" / "NC101A.CBL").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Corpus incomplet"):
                prepare_nist.corpus_manifest(root)


if __name__ == "__main__":
    unittest.main()
