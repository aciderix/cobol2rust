from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_cases


def digest(data):
    return hashlib.sha256(data).hexdigest()


class VerifyCasesTests(unittest.TestCase):
    def dataset(self, root, count=1):
        source = root / "main.cob"
        source.write_text("identification division. program-id. demo. procedure division. stop run.\n")
        for directory, name, data in (("data", "input.bin", b"\x00\xff"),
                                      ("copy", "record.cpy", b"01 record-a pic xx."),
                                      ("lib", "sub.cob", b"program-id. sub.")):
            target = root / directory
            target.mkdir()
            (target / name).write_bytes(data)
        manifest = {"schema_version": 1,
                    "input_directories_sha256": {name: verify_cases.tree_sha256(root / name)
                                                 for name in ("data", "copy", "lib")},
                    "cases": [{"id": f"case-{n}", "source": "main.cob", "source_sha256": digest(source.read_bytes()),
                               "stdin": f"élève-{n}\n", "stdin_sha256": digest(f"élève-{n}\n".encode()),
                               "data_dir": "data", "includes": ["copy"], "call_paths": ["lib"],
                               "fmt": "free", "std": "cobol85", "timeout": 7, "release": True,
                               "runtime_env": {"COB_CURRENT_DATE": "2026/10/25 12:00:00.00"},
                               "expected_native": {"exit": 0, "stdout": "résultat\\xff\n", "stderr": ""}}
                              for n in range(count)]}
        path = root / "cases.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return path, manifest

    def comparison(self, source, stdin, **kwargs):
        return {"match": True, "stderr_match": True, "source_sha256": digest(source.read_bytes()),
                "stdin_sha256": digest(stdin), "cobol_exit": 0, "rust_exit": 0,
                "cobol_stdout": "résultat\\xff\n", "rust_stdout": "résultat\\xff\n",
                "cobol_stderr": "", "rust_stderr": "", "files_match": True}

    def run_manifest(self, path, root):
        with redirect_stdout(io.StringIO()):
            return verify_cases.run_cases(path, root=root)

    def test_cases_pass_their_inputs_and_options_to_the_existing_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, manifest = self.dataset(root, 2)
            with patch.object(verify_cases, "verify", side_effect=self.comparison) as compare:
                report, status = self.run_manifest(path, root)
            self.assertEqual((status, report["passed"], report["sources"]), (0, 2, 1))
            self.assertEqual(report["manifest_sha256"], digest(path.read_bytes()))
            self.assertEqual(compare.call_count, 2)
            args, kwargs = compare.call_args_list[1]
            self.assertEqual(args, (root / "main.cob",))
            self.assertEqual(kwargs, {"stdin": "élève-1\n".encode(), "data_dir": root / "data",
                                      "includes": [root / "copy"], "call_paths": [root / "lib"],
                                      **{key: manifest["cases"][1][key] for key in
                                         ("runtime_env", "fmt", "std", "timeout", "release")}})
            self.assertEqual((root / "data" / "input.bin").read_bytes(), b"\x00\xff")

    def test_every_case_is_checked_before_any_compilation(self):
        for mutation in ("source", "stdin", "data", "duplicate", "escape"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path, manifest = self.dataset(root, 2)
                if mutation == "source":
                    (root / "main.cob").write_text("changed")
                elif mutation == "data":
                    (root / "data" / "input.bin").write_bytes(b"changed")
                else:
                    if mutation == "stdin":
                        manifest["cases"][1]["stdin"] = "changed"
                    elif mutation == "duplicate":
                        manifest["cases"][1]["id"] = manifest["cases"][0]["id"]
                    else:
                        manifest["cases"][1]["source"] = "../outside.cob"
                    path.write_text(json.dumps(manifest))
                with patch.object(verify_cases, "verify") as compare:
                    report, status = self.run_manifest(path, root)
                self.assertEqual(status, 2)
                self.assertEqual(report["status"], "invalid_manifest")
                compare.assert_not_called()

    def test_mutations_during_a_comparison_block_subsequent_compilations(self):
        for target in ("source", "data", "manifest"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path, _ = self.dataset(root, 2)

                def compare(source, stdin, **kwargs):
                    result = self.comparison(source, stdin, **kwargs)
                    changed = {"source": source, "data": root / "data" / "input.bin", "manifest": path}[target]
                    changed.write_bytes(b"changed")
                    return result

                with patch.object(verify_cases, "verify", side_effect=compare) as mocked:
                    report, status = self.run_manifest(path, root)
                self.assertEqual((status, report["failed"], mocked.call_count), (1, 2, 1))
                self.assertEqual([row["status"] for row in report["results"]], ["error", "error"])

    def test_oracle_stderr_and_provenance_are_required_even_if_match_is_true(self):
        for mutation in ("oracle", "stderr", "provenance"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path, _ = self.dataset(root)

                def compare(source, stdin, **kwargs):
                    result = self.comparison(source, stdin, **kwargs)
                    key, value = {"oracle": ("cobol_stdout", "unexpected"),
                                  "stderr": ("stderr_match", False),
                                  "provenance": ("source_sha256", "0" * 64)}[mutation]
                    result[key] = value
                    return result

                with patch.object(verify_cases, "verify", side_effect=compare):
                    report, status = self.run_manifest(path, root)
                self.assertEqual((status, report["failed"]), (1, 1))
                self.assertEqual(report["results"][0]["status"], "different")

    def test_timeouts_and_refusals_remain_in_the_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, _ = self.dataset(root, 2)
            errors = [subprocess.TimeoutExpired("native", 7), ValueError("construction non prise en charge")]
            with patch.object(verify_cases, "verify", side_effect=errors):
                report, status = self.run_manifest(path, root)
            self.assertEqual((status, report["cases"], report["passed"], report["failed"]), (1, 2, 0, 2))
            self.assertEqual(report["counts"], {"timeout": 1, "error": 1})

    def test_tree_hash_covers_paths_contents_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a").write_bytes(b"bytes")
            first = verify_cases.tree_sha256(root)
            (root / "a").rename(root / "b")
            renamed = verify_cases.tree_sha256(root)
            (root / "b").write_bytes(b"changed")
            changed = verify_cases.tree_sha256(root)
            (root / "empty").mkdir()
            empty = verify_cases.tree_sha256(root)
            self.assertEqual(len({first, renamed, changed, empty}), 4)


if __name__ == "__main__":
    unittest.main()
