from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.coverage import main, measure
from cobol2rust.toolchain import ROOT


def source(body="stop run.", data=""):
    return ("identification division.\nprogram-id. coverage-case.\n"
            f"data division.\nworking-storage section.\n{data}\n"
            f"procedure division.\n{body}\n")


class CoverageTests(unittest.TestCase):
    def test_mixed_corpus_is_static_and_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "good.CBL"
            good.write_text(source(), encoding="utf-8")
            (root / "bad.cob").write_text(source("call 'external' returning x."), encoding="utf-8")
            (root / "record.cpy").write_text("01 x pic 9.", encoding="utf-8")
            before = {str(path): path.read_bytes() for path in root.iterdir()}
            first, code = measure(root, corpus_id="test-v1", corpus_source="local test")
            second, _ = measure(root, corpus_id="test-v1", corpus_source="local test")
            self.assertEqual(code, 1)
            self.assertEqual(first, second)
            fingerprints = first["tool"]["source_files_sha256"]
            for relative in ["tools/coverage.py", "cobol2rust/frontend.py", "cobol2rust/runtime.rs"]:
                self.assertEqual(fingerprints[relative], hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
            expected_files = {path.relative_to(ROOT).as_posix()
                              for pattern in ("*.py", "*.rs")
                              for path in (ROOT / "cobol2rust").rglob(pattern)}
            self.assertTrue(expected_files.issubset(fingerprints))
            self.assertTrue(all(not Path(relative).is_absolute() for relative in fingerprints))
            self.assertEqual(first["denominator"]["sources"], 2)
            self.assertEqual(first["counts"]["emission_accepted"], 1)
            self.assertEqual(first["counts"]["frontend_blocked"], 1)
            self.assertTrue(first["static_only"])
            self.assertFalse(first["verified"])
            self.assertEqual((first["compiled"], first["executed"], first["compared"]), (0, 0, 0))
            self.assertTrue(all(not row["verified"] for row in first["results"]))
            self.assertEqual(before, {str(path): path.read_bytes() for path in root.iterdir()})
            row = next(row for row in first["results"] if row["source"] == str(good))
            self.assertEqual(row["source_sha256"], hashlib.sha256(good.read_bytes()).hexdigest())

    def test_empty_and_missing_corpus_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            for root in [Path(directory), Path(directory) / "missing"]:
                with self.subTest(root=root):
                    report, code = measure(root)
                    self.assertEqual(code, 2)
                    self.assertFalse(report["denominator"]["discovery_complete"])
                    self.assertEqual(report["denominator"]["sources"], 0)
                    self.assertTrue(report["discovery_errors"])

    def test_copy_hashes_and_unknown_copy_list_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            includes = root / "copybooks"
            includes.mkdir()
            copy = includes / "record.cpy"
            copy.write_text("01 n pic 9 value 3.\n", encoding="utf-8")
            good = root / "good.cob"
            good.write_text(source("display n.", "COPY record."), encoding="utf-8")
            (root / "bad.cob").write_text(source(data="COPY missing."), encoding="utf-8")
            report, code = measure(root, includes=[includes])
            self.assertEqual(code, 1)
            accepted = next(row for row in report["results"] if row["source"] == str(good))
            self.assertEqual(accepted["status"], "emission_accepted")
            self.assertTrue(accepted["copybooks_complete"])
            self.assertEqual(accepted["copybooks"], [{"path": str(copy),
                             "sha256": hashlib.sha256(copy.read_bytes()).hexdigest()}])
            failed = next(row for row in report["results"] if row["source"] != str(good))
            self.assertEqual(failed["status"], "preprocess_blocked")
            self.assertFalse(failed["copybooks_complete"])

    def test_fixed_columns_and_orphan_continuation_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixed = "\n".join(f"{number:06} {line}" for number, line in enumerate(source().splitlines(), 1))
            (root / "fixed.cob").write_text(fixed, encoding="utf-8")
            (root / "continuation.cob").write_text("999999- continuation\n" + fixed, encoding="utf-8")
            report, code = measure(root, fmt="fixed")
            self.assertEqual(code, 1)
            self.assertEqual(report["counts"]["emission_accepted"], 1)
            self.assertEqual(report["counts"]["preprocess_blocked"], 1)

    def test_internal_exception_does_not_look_like_unsupported_syntax(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.cob").write_text(source(), encoding="utf-8")
            with patch("tools.coverage.Parser.parse", side_effect=RuntimeError("unexpected defect")):
                report, code = measure(root)
            self.assertEqual(code, 2)
            self.assertEqual(report["counts"]["internal_error"], 1)
            self.assertIn("RuntimeError: unexpected defect", report["results"][0]["diagnostic"])

    def test_cli_saves_report_once_and_returns_acceptance_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.cob").write_text(source(), encoding="utf-8")
            report_path = root / "report.json"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(root), "--report", str(report_path)]), 0)
                original = report_path.read_bytes()
                self.assertEqual(main([str(root), "--report", str(report_path)]), 2)
            self.assertEqual(report_path.read_bytes(), original)
            self.assertEqual(json.loads(original)["counts"]["emission_accepted"], 1)

    def test_source_symlink_is_counted_and_directory_symlink_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.cob"
            target.write_text(source(), encoding="utf-8")
            (root / "link.cob").symlink_to(target)
            (root / "directory-link").symlink_to(root, target_is_directory=True)
            report, code = measure(root)
            self.assertEqual(code, 2)
            self.assertEqual(report["denominator"]["sources"], 2)
            self.assertEqual(report["counts"]["preprocess_blocked"], 1)
            self.assertFalse(report["denominator"]["discovery_complete"])
            self.assertIn("symbolic-link directory", report["discovery_errors"][0])

    def test_subprogram_extension_is_an_explicit_denominator_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.CBL").write_text(source(), encoding="utf-8")
            (root / "module.SUB").write_text(source(), encoding="utf-8")
            default, default_code = measure(root)
            extended, extended_code = measure(root, include_subprograms=True)
            self.assertEqual((default_code, extended_code), (0, 0))
            self.assertEqual(default["denominator"]["sources"], 1)
            self.assertEqual(extended["denominator"]["sources"], 2)
            self.assertNotIn(".sub", default["denominator"]["extensions"])
            self.assertIn(".sub", extended["denominator"]["extensions"])

    def test_unreadable_source_stays_in_the_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "locked.cob").write_text(source(), encoding="utf-8")
            read_bytes = Path.read_bytes

            def read(path):
                if path.name == "locked.cob":
                    raise PermissionError("not readable")
                return read_bytes(path)

            with patch("tools.coverage.Path.read_bytes", autospec=True, side_effect=read):
                report, code = measure(root)
            self.assertEqual(code, 1)
            self.assertEqual(report["denominator"]["sources"], 1)
            self.assertEqual(report["counts"]["preprocess_blocked"], 1)
            self.assertIsNone(report["results"][0]["source_sha256"])
            self.assertIn("PermissionError", report["results"][0]["diagnostic"])

    def test_diagnostic_groups_normalize_line_numbers_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.cob").write_text(source("call 'external' returning x."), encoding="utf-8")
            (root / "second.cob").write_text("\n\n" + source("call 'external' returning x."), encoding="utf-8")
            report, code = measure(root)
            self.assertEqual(code, 1)
            self.assertEqual(len(report["diagnostic_groups"]), 1)
            group = report["diagnostic_groups"][0]
            self.assertEqual(len(group["sources"]), 2)
            self.assertIn("ligne <n>", group["diagnostic"])
            self.assertNotEqual(report["results"][0]["diagnostic"], report["results"][1]["diagnostic"])

    def test_emission_rejection_is_distinct_from_parsing_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.cob").write_text(source(), encoding="utf-8")
            from cobol2rust.frontend import CobolError
            with patch("tools.coverage.emit_unit", side_effect=CobolError("unsupported emission")):
                report, code = measure(root)
            self.assertEqual(code, 1)
            self.assertEqual(report["counts"]["emission_blocked"], 1)
            self.assertEqual(report["results"][0]["program"], "COVERAGE-CASE")


if __name__ == "__main__":
    unittest.main()
