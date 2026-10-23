"""Measure static source acceptance; never compile or execute corpus programs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cobol2rust import __version__
from cobol2rust.audit import SKIP
from cobol2rust.cli import emit_unit
from cobol2rust.frontend import CobolError, Parser, load_source, source_format
from cobol2rust.toolchain import ROOT


STATUSES = ("preprocess_blocked", "frontend_blocked", "emission_blocked",
            "emission_accepted", "internal_error")
EXTENSIONS = {".cob", ".cbl"}


def discover(root, extensions):
    """Keep source symlinks in the inventory and report incomplete traversal."""
    paths, errors, excluded = [], [], []
    if root.is_symlink():
        if root.suffix.lower() in extensions and not root.is_dir():
            return [root], errors, excluded
        return [], [f"refusing symbolic-link corpus root: {root}"], excluded
    if root.is_file():
        if root.suffix.lower() in extensions:
            return [root], errors, excluded
        return [], [f"source extension must be one of {sorted(extensions)}: {root}"], excluded
    if not root.is_dir():
        return [], [f"corpus directory not found or inaccessible: {root}"], excluded

    def traversal_error(error):
        errors.append(str(error))

    for directory, folders, files in os.walk(root, followlinks=False, onerror=traversal_error):
        retained = []
        for name in sorted(folders):
            path = Path(directory) / name
            if path.is_symlink():
                errors.append(f"untraversed symbolic-link directory: {path}")
            elif name in SKIP:
                excluded.append(path.relative_to(root).as_posix())
            else:
                retained.append(name)
        folders[:] = retained
        paths.extend(Path(directory) / name for name in sorted(files)
                     if Path(name).suffix.lower() in extensions)
    return sorted(paths), sorted(errors), sorted(excluded)


def inspect_source(path, fmt, includes, call_paths=()):
    result = {"source": str(path), "source_sha256": None, "verified": False,
              "copybooks": [], "copybooks_complete": False}
    stage = "preprocess"
    try:
        if path.is_symlink():
            raise CobolError("symbolic-link source is not read")
        original = path.read_bytes()
        result["source_sha256"] = hashlib.sha256(original).hexdigest()
        result["initial_source_format"] = source_format(original.decode("utf-8-sig"), fmt)
        expanded, copies = load_source(path, list(includes), fmt)
        result["expanded_sha256"] = hashlib.sha256(expanded.encode("utf-8")).hexdigest()
        # On failure load_source does not return the COPY files it already read.
        # An incomplete list is deliberately not presented as an empty known list.
        result["copybooks"] = [{"path": name, "sha256": hashlib.sha256(Path(name).read_bytes()).hexdigest()}
                               for name in copies]
        result["copybooks_complete"] = True
        stage = "frontend"
        program = Parser(expanded).parse()
        result["program"] = program.name
        stage = "emission"
        emit_unit(path, fmt, includes, [path.parent / relative for relative in call_paths])
        result["status"] = "emission_accepted"
    except CobolError as error:
        result.update(status=stage + "_blocked", diagnostic=str(error))
    except (OSError, UnicodeError) as error:
        result.update(status="preprocess_blocked" if stage == "preprocess" else "internal_error",
                      diagnostic=f"{type(error).__name__}: {error}")
    except Exception as error:
        result.update(status="internal_error", diagnostic=f"{type(error).__name__}: {error}")
    return result


def git_head():
    try:
        result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "HEAD"],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def implementation_hashes():
    paths = [Path(__file__).resolve()]
    for extension in ("*.py", "*.rs"):
        paths.extend((ROOT / "cobol2rust").rglob(extension))
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def measure(root, fmt="auto", includes=(), corpus_id=None, corpus_source=None, include_subprograms=False,
            call_paths=()):
    root = Path(root).absolute()
    includes = [Path(path).absolute() for path in includes]
    extensions = EXTENSIONS | ({".sub"} if include_subprograms else set())
    try:
        paths, errors, excluded = discover(root, extensions)
    except OSError as error:
        paths, errors, excluded = [], [str(error)], []
    if not paths and not errors:
        errors.append(f"no source files found for extensions {sorted(extensions)}")
    results = [inspect_source(path, fmt, includes, call_paths) for path in paths]
    counts = {status: sum(row["status"] == status for row in results) for status in STATUSES}
    grouped = {}
    for row in results:
        if "diagnostic" in row:
            diagnostic = re.sub(r"\b(ligne|line)\s+\d+\b", r"\1 <n>", row["diagnostic"], flags=re.I)
            key = row["status"], diagnostic
            grouped.setdefault(key, []).append({"source": row["source"], "program": row.get("program")})
    tool = {"name": "cobol2rust", "version": __version__, "git_head": git_head()}
    try:
        tool["source_files_sha256"] = implementation_hashes()
    except OSError as error:
        tool["source_files_sha256"] = None
        tool["source_files_error"] = str(error)
    report = {
        "schema_version": 1,
        "tool": tool,
        "corpus": {"root": str(root), "id": corpus_id, "source": corpus_source},
        "format_requested": fmt, "copybook_paths": [str(path) for path in includes],
        "call_paths_relative_to_source": [str(path) for path in call_paths],
        "static_only": True, "verified": False, "compiled": 0, "executed": 0, "compared": 0,
        "scope": "source preprocessing, parsing/layout and Rust emission only; no behavioral equivalence established",
        "denominator": {"sources": len(paths), "extensions": sorted(extensions),
                        "excluded_directory_names": sorted(SKIP), "excluded_directories": excluded,
                        "discovery_complete": not errors},
        "discovery_errors": errors, "counts": counts,
        "diagnostic_scope": "first blocking diagnostic per source, not an exhaustive inventory of missing features; only line numbers are normalized for grouping",
        "copybook_scope": "COPY list is unknown when preprocessing fails; hashes are supplied after successful expansion",
        "diagnostic_groups": [{"status": status, "diagnostic": diagnostic, "sources": rows}
                              for (status, diagnostic), rows in sorted(grouped.items())],
        "results": results,
    }
    code = 2 if errors or counts["internal_error"] or "source_files_error" in tool else 1 if counts["emission_accepted"] != len(paths) else 0
    return report, code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--format", choices=["auto", "free", "fixed"], default="auto")
    parser.add_argument("-I", "--copybook-path", type=Path, action="append", default=[])
    parser.add_argument("--corpus-id", help="user-supplied corpus identity or revision")
    parser.add_argument("--corpus-source", help="user-supplied provenance URL or description")
    parser.add_argument("--include-subprograms", action="store_true", help="also inventory .SUB source files")
    parser.add_argument("--call-path", action="append", default=[],
                        help="directory of CALLed programs, relative to each source (e.g. lib for NIST IC)")
    parser.add_argument("--report", type=Path, help="new JSON report; default is standard output")
    args = parser.parse_args(argv)
    if args.report and (args.report.exists() or args.report.is_symlink()):
        print(f"coverage: report already exists: {args.report}", file=sys.stderr)
        return 2
    report, code = measure(args.corpus, args.format, args.copybook_path, args.corpus_id,
                           args.corpus_source, args.include_subprograms, args.call_path)
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x", encoding="utf-8") as output:
                output.write(encoded)
        except OSError as error:
            print(f"coverage: {error}", file=sys.stderr)
            return 2
        print(f"{report['counts']['emission_accepted']}/{report['denominator']['sources']} accepted for Rust emission; "
              f"0 compiled/executed/compared; report: {args.report}")
    else:
        print(encoded, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
