"""Compare converted NIST CCVS85 programs with GnuCOBOL on the runner's own inputs.

The official runner executes each module in sorted order in one directory and
removes XXXXX* before every .CBL program. A .SUB program therefore reads the
files left by the programs since the last .CBL. This tool replays those
predecessors natively, snapshots their data files, then runs `verify` on the
same inputs. When native runner logs are available, the Rust REPORT must also
be byte-identical to the program's log and its counts are taken from report.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cobol2rust.frontend import CobolError
from cobol2rust.cli import convert
from cobol2rust.toolchain import build_rust, find_tool
from cobol2rust.verification import verify


RUNNER_FLAGS = ["-std=cobol85", "--debug"]
# report.pl only compiles these programs: their execution is not part of the suite.
COMPILE_ONLY = {"NC401M", "RL301M", "RL401M", "IC401M", "IX301M", "IX401M", "SQ303M",
                "SQ401M", "ST301M", "RW301M", "RW302M", "DB205A"}


def module_programs(corpus: Path, module: str) -> list[Path]:
    directory = corpus / module
    return sorted([*directory.glob("*.CBL"), *directory.glob("*.SUB")], key=lambda path: path.name)


def predecessors(corpus: Path, name: str) -> tuple[Path, list[Path]]:
    programs = module_programs(corpus, name[:2])
    index = next((i for i, path in enumerate(programs) if path.stem == name), None)
    if index is None:
        raise ValueError(f"programme NIST introuvable : {name}")
    start = index
    while start >= 0 and programs[start].suffix != ".CBL":
        start -= 1
    if start < 0:
        raise ValueError(f"aucun programme principal avant {name}")
    return programs[index], programs[start:index]


def native_seed(corpus: Path, chain: list[Path], copybooks: list[Path], work: Path) -> Path:
    """Run the predecessors with GnuCOBOL and keep the XXXXX* data they leave."""
    cobc = find_tool("cobc")
    run_dir, seed = work / "native", work / "seed"
    run_dir.mkdir(parents=True)
    seed.mkdir()
    for program in chain:
        executable = run_dir / program.stem
        include = [argument for path in copybooks for argument in ("-I", str(path))]
        subprocess.run([cobc, "-x", *RUNNER_FLAGS, *include, str(program), "-o", str(executable)],
                       cwd=run_dir, check=True, capture_output=True, timeout=300)
        stdin = program.with_suffix(".DAT")
        with (stdin.open("rb") if stdin.exists() else open(os.devnull, "rb")) as stream:
            subprocess.run([str(executable)], cwd=run_dir, stdin=stream, capture_output=True,
                           env={**os.environ, "REPORT": f"{program.stem}.log"}, timeout=300)
    for path in sorted(run_dir.glob("XXXXX*")):
        shutil.copy2(path, seed / path.name)
    return seed


def runner_counts(native_logs: Path, name: str) -> dict | None:
    summary = native_logs / name[:2] / "report.txt"
    if not summary.exists():
        return None
    for line in summary.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if fields and fields[0].split(".")[0] == name and len(fields) >= 6 and fields[1].isdigit():
            keys = ("total", "pass", "fail", "deleted", "inspect")
            return dict(zip(keys, map(int, fields[1:6])))
    return None


def check(corpus: Path, native_logs: Path, name: str, work: Path) -> dict:
    copybooks = [corpus / "copy", corpus / "copyalt"]
    source, chain = predecessors(corpus, name)
    work.mkdir(parents=True)
    if name in COMPILE_ONLY:
        convert(source, work / "rust", fmt="fixed", includes=copybooks)
        build_rust(work / "rust")
        return {"program": name, "source": source.name, "compile_only": True, "passed": True,
                "runner_counts": runner_counts(native_logs, name)}
    seed = native_seed(corpus, chain, copybooks, work) if chain else None
    stdin = source.with_suffix(".DAT")
    report = verify(source, fmt="fixed", includes=copybooks,
                    stdin=stdin.read_bytes() if stdin.exists() else b"", data_dir=seed)
    entry = {"program": name, "source": source.name, "predecessors": [path.stem for path in chain],
             "match": report["match"], "cobol_exit": report["cobol_exit"], "rust_exit": report["rust_exit"],
             "rust_stderr": report["rust_stderr"][-300:], "seed_files": report.get("input_files", {})}
    log = native_logs / name[:2] / f"{name}.log"
    rust_report = report["rust_files"].get("REPORT")
    if log.exists():
        expected = hashlib.sha256(log.read_bytes()).hexdigest()
        entry["report_matches_runner"] = bool(rust_report) and rust_report["sha256"] == expected
    entry["runner_counts"] = runner_counts(native_logs, name)
    entry["passed"] = report["match"] and entry.get("report_matches_runner", rust_report is None)
    return entry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("programs", nargs="*", help="noms NIST, par ex. SQ143A")
    parser.add_argument("--accepted-from", type=Path,
                        help="rapport coverage.py : vérifier toutes ses émissions acceptées")
    parser.add_argument("--corpus", type=Path, default=Path(".tools/nist-ccvs85/extracted"))
    parser.add_argument("--native-logs", type=Path, default=Path(".tools/nist-native-gnucobol-3.2"))
    parser.add_argument("--work", type=Path, required=True, help="dossier de travail inexistant")
    parser.add_argument("-o", "--output", type=Path, required=True, help="nouveau rapport JSON")
    args = parser.parse_args(argv)
    names = list(args.programs)
    if args.accepted_from:
        results = json.loads(args.accepted_from.read_text(encoding="utf-8"))["results"]
        names += [Path(r["source"]).stem for r in results if r["status"] == "emission_accepted"]
    if not names:
        parser.error("aucun programme demandé")
    if args.work.exists() or args.output.exists():
        parser.error("le dossier de travail et le rapport doivent être inexistants")
    if not find_tool("cobc") or not find_tool("cargo"):
        print("GnuCOBOL et Cargo sont requis", file=sys.stderr)
        return 2
    entries = []
    for name in sorted(set(names)):
        try:
            entry = check(args.corpus.absolute(), args.native_logs.absolute(), name, args.work.absolute() / name)
        except (OSError, ValueError, CobolError, subprocess.SubprocessError) as exc:
            entry = {"program": name, "passed": False, "error": str(exc)}
        entries.append(entry)
        counts = entry.get("runner_counts") or {}
        print(f"{'PASS' if entry['passed'] else 'FAIL'} {name}"
              + (f" ({counts['pass']}/{counts['total']} PASS natifs)" if counts else "")
              + (f" : {entry.get('error') or entry.get('rust_stderr', '').strip()}" if not entry["passed"] else ""),
              flush=True)
    totals = {key: sum((entry.get("runner_counts") or {}).get(key, 0) for entry in entries if entry["passed"])
              for key in ("total", "pass", "fail", "deleted", "inspect")}
    summary = {"programs": entries, "passed": sum(entry["passed"] for entry in entries),
               "checked": len(entries), "runner_totals_of_passed": totals,
               "scope": "comparaison GnuCOBOL/Rust et REPORT du runner natif ; pas une certification"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{summary['passed']}/{summary['checked']} conformes ; bilans natifs des conformes : {totals}")
    return 0 if summary["passed"] == summary["checked"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
