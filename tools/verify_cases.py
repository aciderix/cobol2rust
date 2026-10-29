"""Compare des cas d'entrée déclarés, séparément du protocole corpus stdin vide.

Les sources et stdin UTF-8 sont épinglés par SHA-256. Les dossiers de données,
COPY et appelés ont une empreinte d'arbre canonique (chemins, types et hashes).
L'oracle expected_native, facultatif, utilise les textes retournés par verify
(stdout ASCII avec backslashreplace), et non une nouvelle lecture des octets.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cobol2rust.toolchain import ROOT
from cobol2rust.verification import verify
from tools.real_corpora import implementation_sha256


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def tree_sha256(directory):
    """SHA-256 du JSON canonique des [type, chemin relatif, hash éventuel]."""
    if not directory.is_dir():
        raise ValueError(f"dossier d'entrée absent : {directory}")
    entries = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            raise ValueError(f"lien symbolique dans les entrées : {path}")
        if path.is_dir():
            entries.append(["directory", relative])
        elif path.is_file():
            entries.append(["file", relative, sha256(path.read_bytes())])
        else:
            raise ValueError(f"entrée non régulière : {path}")
    return sha256(canonical(entries))


def repo_path(root, value, directory=False):
    if (not isinstance(value, str) or not value or "\\" in value
            or PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
            or ".." in PurePosixPath(value).parts):
        raise ValueError(f"chemin relatif au dépôt attendu : {value!r}")
    path = (root / value).resolve()
    if not path.is_relative_to(root) or not (path.is_dir() if directory else path.is_file()):
        raise ValueError(f"{'dossier' if directory else 'source'} absent ou hors dépôt : {value}")
    return path


def pinned_hash(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("empreinte SHA-256 hexadécimale attendue")
    return value


def prepare(manifest, root):
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("schema_version 1 attendu")
    rows = manifest.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("liste de cas non vide attendue")
    pins = manifest.get("input_directories_sha256", {})
    if not isinstance(pins, dict):
        raise ValueError("input_directories_sha256 doit être un objet")
    directories = {repo_path(root, name, True): pinned_hash(digest) for name, digest in pins.items()}
    allowed = {"id", "source", "source_sha256", "stdin", "stdin_sha256", "data_dir", "includes", "call_paths",
               "runtime_env", "fmt", "std", "timeout", "release", "expected_native"}
    prepared, identifiers = [], set()
    for row in rows:
        if not isinstance(row, dict) or row.keys() - allowed:
            raise ValueError("cas invalide ou option inconnue")
        name = row.get("id")
        if not isinstance(name, str) or not name or name in identifiers:
            raise ValueError("identifiant de cas vide ou dupliqué")
        identifiers.add(name)
        source = repo_path(root, row.get("source"))
        digest = pinned_hash(row.get("source_sha256"))
        stdin = row.get("stdin", "")
        if not isinstance(stdin, str):
            raise ValueError(f"{name} : stdin doit être un texte UTF-8")
        stdin = stdin.encode("utf-8")
        if sha256(stdin) != pinned_hash(row.get("stdin_sha256")):
            raise ValueError(f"{name} : empreinte stdin différente")
        kwargs = {"fmt": row.get("fmt", "auto"), "std": row.get("std", "default"),
                  "timeout": row.get("timeout", 15), "release": row.get("release", False),
                  "runtime_env": row.get("runtime_env", {})}
        if not isinstance(kwargs["fmt"], str) or kwargs["fmt"] not in {"auto", "fixed", "free"} or not isinstance(kwargs["std"], str):
            raise ValueError(f"{name} : format ou dialecte invalide")
        timeout = kwargs["timeout"]
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout <= 0 or not isinstance(kwargs["release"], bool)):
            raise ValueError(f"{name} : timeout positif et release booléen attendus")
        env = kwargs["runtime_env"]
        if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
            raise ValueError(f"{name} : runtime_env doit associer des textes")
        kwargs["data_dir"] = repo_path(root, row["data_dir"], True) if row.get("data_dir") is not None else None
        for key in ("includes", "call_paths"):
            paths = row.get(key, [])
            if not isinstance(paths, list):
                raise ValueError(f"{name} : {key} doit être une liste")
            kwargs[key] = [repo_path(root, path, True) for path in paths]
        used = [*kwargs["includes"], *kwargs["call_paths"], *([kwargs["data_dir"]] if kwargs["data_dir"] else [])]
        if any(path not in directories for path in used):
            raise ValueError(f"{name} : empreinte de dossier d'entrée manquante")
        expected = row.get("expected_native", {})
        if (not isinstance(expected, dict) or expected.keys() - {"exit", "stdout", "stderr"}
                or any(not isinstance(v, str) for k, v in expected.items() if k != "exit")
                or ("exit" in expected and type(expected["exit"]) is not int)):
            raise ValueError(f"{name} : oracle natif invalide")
        prepared.append({"id": name, "source": source, "source_sha256": digest,
                         "stdin": stdin, "stdin_sha256": sha256(stdin), "options": kwargs,
                         "expected_native": expected, "case_sha256": sha256(canonical(row))})
    return prepared, directories


def check_inputs(cases, directories, manifest_path, manifest_sha256):
    if sha256(manifest_path.read_bytes()) != manifest_sha256:
        raise ValueError("manifeste modifié pendant la campagne")
    for case in cases:
        if sha256(case["source"].read_bytes()) != case["source_sha256"]:
            raise ValueError(f"source modifiée : {case['source']}")
    for directory, digest in directories.items():
        if tree_sha256(directory) != digest:
            raise ValueError(f"dossier d'entrée modifié : {directory}")


def run_cases(cases_path, root=ROOT):
    root, cases_path = root.resolve(), cases_path.resolve()
    fingerprint = implementation_sha256()
    report = {"schema_version": 1, "measured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "scope": "Campagne avec jeux d'entrée déclarés ; distincte de la mesure corpus stdin vide. "
                       "stdout, stderr, fichiers et codes de sortie comparés pour ces entrées seulement.",
              "implementation_sha256": fingerprint, "manifest": str(cases_path), "results": []}
    try:
        raw = cases_path.read_bytes()
        report["manifest_sha256"] = sha256(raw)
        cases, directories = prepare(json.loads(raw), root)
        check_inputs(cases, directories, cases_path, report["manifest_sha256"])
    except (ValueError, OSError) as exc:
        report.update(status="invalid_manifest", error=str(exc), cases=0, passed=0, failed=0)
        return report, 2
    for case in cases:
        row = {key: case[key] for key in ("id", "source_sha256", "stdin_sha256", "case_sha256")}
        row["source"] = case["source"].relative_to(root).as_posix()
        try:
            check_inputs(cases, directories, cases_path, report["manifest_sha256"])
            comparison = verify(case["source"], stdin=case["stdin"], **case["options"])
            row["comparison"] = comparison
            check_inputs(cases, directories, cases_path, report["manifest_sha256"])
            differences = [key for key, expected in case["expected_native"].items()
                           if comparison.get("cobol_" + key) != expected]
            provenance = (comparison.get("source_sha256") == case["source_sha256"]
                          and comparison.get("stdin_sha256") == case["stdin_sha256"])
            row["oracle_differences"] = differences
            row["status"] = "identical" if (comparison.get("match") and comparison.get("stderr_match")
                                                    and provenance and not differences) else "different"
            if not provenance:
                row["error"] = "empreintes du résultat différentes des entrées épinglées"
        except subprocess.TimeoutExpired:
            row.update(status="timeout", error="délai de comparaison dépassé")
        except (ValueError, OSError, RuntimeError) as exc:
            row.update(status="error", error=str(exc))
        report["results"].append(row)
        print(f"{row['status']:10} {case['id']}", flush=True)
    counts = Counter(row["status"] for row in report["results"])
    if implementation_sha256() != fingerprint:
        report["error"] = "convertisseur modifié pendant la campagne"
    report.update(status="complete", cases=len(cases), sources=len({case["source"] for case in cases}),
                  passed=counts["identical"], failed=len(cases) - counts["identical"], counts=dict(counts))
    return report, 0 if report["failed"] == 0 and "error" not in report else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=Path, default=ROOT / "measurements" / "real-input-cases.json")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "real-input-cases-verification.json")
    args = parser.parse_args(argv)
    report, status = run_cases(args.cases)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['passed']}/{report['cases']} comparaisons identiques ; rapport : {args.report}")
    if report.get("error"):
        print(report["error"], file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
