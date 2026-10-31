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
import re
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cobol2rust.frontend import CobolError
from cobol2rust.cli import convert
from cobol2rust.toolchain import build_rust, find_tool
from cobol2rust.verification import verify


RUNNER_FLAGS = ["-std=cobol85", "--debug"]
# report.pl compiles these programs with -fdebugging-line ($cobc_flags).
DEBUGGING_LINES = {"SM206A"}
# Programs that print the clock: both runs use the moment of the reference
# run, read from its log (reference_clock); this value is the fallback, from
# the run of 23 October 2026 (DATE 261023, DAY 26296, TIME 15092270).
RUNNER_CLOCK = {"NC214M": "2026/10/23 15:09:22.700000000"}
NATIVE_LOGS = Path(".tools/nist-native-gnucobol-3.2")


def reference_clock(name: str) -> str:
    """COB_CURRENT_DATE of the native reference run, from the DATE YYMMDD and
    HHMMSSFF lines of the program's REPORT log."""
    log = NATIVE_LOGS / name[:2] / f"{name}.log"
    if log.exists():
        text = log.read_text(encoding="ascii", errors="replace")
        date = re.search(r"0*(\d{6})\.0+\s+DATE YYMMDD", text)
        time = re.search(r"0*(\d{1,8})\.0+\s+HHMMSSFF", text)
        if date and time:
            d, t = date.group(1), time.group(1).zfill(8)
            return f"20{d[:2]}/{d[2:4]}/{d[4:]} {t[:2]}:{t[2:4]}:{t[4:6]}.{t[6:]}0000000"
    return RUNNER_CLOCK[name]
# report.pl $cobc_flags{DB201A} = "-fno-ec=data-incompatible".
NO_EC_DATA_INCOMPATIBLE = {"DB201A"}
# report.pl $raw_input, written with `echo "..." > $exe.inp` (so plus "\n").
RAW_INPUT = {"OBNC1M": b"\n" * 8 + b"\x03\n", "NC302M": b"\n\n"}
# report.pl sets these switches for every program.
RUNNER_ENV = {"COB_SWITCH_1": "ON", "COB_SWITCH_2": "OFF"}


def runner_env(name: str) -> dict:
    """report.pl: the runtime DEBUG switch is on for the DB module, except DB102A."""
    environment = {**RUNNER_ENV, "COB_SET_DEBUG": "Y" if name[:2] == "DB" and name != "DB102A" else "N"}
    if name in RUNNER_CLOCK:
        environment["COB_CURRENT_DATE"] = reference_clock(name)
    return environment
# report.pl executes DB103M a second time with the runtime DEBUG switch off;
# its REPORT log is the first run's, report.txt has a line for each run.
RERUN_ENV = {"DB103M": {"COB_SET_DEBUG": "N"}}
# report.pl only compiles these programs: their execution is not part of the suite.
COMPILE_ONLY = {"NC401M", "RL301M", "RL401M", "IC401M", "IX301M", "IX401M", "SQ303M",
                "SQ401M", "ST301M", "RW301M", "RW302M", "DB205A"}
# tests/cobol85/Makefile.am: "currently untested modules: CM" (never run).
UNTESTED_MODULES = {"CM"}


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
                           env={**os.environ, **runner_env(program.stem), "REPORT": f"{program.stem}.log"}, timeout=300)
    for path in sorted(run_dir.glob("XXXXX*")):
        shutil.copy2(path, seed / path.name)
    return seed


def rust_seed(corpus: Path, chain: list[Path], copybooks: list[Path], call_paths: list[Path], work: Path) -> Path:
    """The predecessors converted to Rust and run in turn: INDEXED files are
    in cobol2rust's own format, not GnuCOBOL's Berkeley DB."""
    run_dir, seed = work / "rust_native", work / "rust_seed"
    run_dir.mkdir(parents=True)
    seed.mkdir()
    for program in chain:
        project = work / f"rust_{program.stem}"
        convert(program, project, fmt="fixed", includes=copybooks, call_paths=call_paths, std="cobol85", runtime_checks=True)
        binary = build_rust(project)
        stdin = program.with_suffix(".DAT")
        with (stdin.open("rb") if stdin.exists() else open(os.devnull, "rb")) as stream:
            subprocess.run([str(binary)], cwd=run_dir, stdin=stream, capture_output=True,
                           env={**os.environ, **runner_env(program.stem)}, timeout=300)
    for path in sorted(run_dir.glob("XXXXX*")):
        shutil.copy2(path, seed / path.name)
    return seed


def has_berkeley_db(directory: Path) -> bool:
    """A Berkeley DB btree: magic 0x053162 at offset 12 of its meta page."""
    return any(path.read_bytes()[12:16] in {b"\x62\x31\x05\x00", b"\x00\x05\x31\x62"}
               for path in directory.iterdir() if path.is_file())


def runner_counts(native_logs: Path, name: str) -> dict | None:
    summary = native_logs / name[:2] / "report.txt"
    if not summary.exists():
        return None
    keys = ("total", "pass", "fail", "deleted", "inspect")
    runs = [dict(zip(keys, map(int, fields[1:6])))
            for fields in map(str.split, summary.read_text(encoding="utf-8", errors="replace").splitlines())
            if fields and fields[0].split(".")[0] == name and len(fields) >= 6 and fields[1].isdigit()]
    if not runs:
        return None
    # The executions of a program re-run by report.pl add up.
    return {key: sum(run[key] for run in runs) for key in keys}


def check(corpus: Path, native_logs: Path, name: str, work: Path) -> dict:
    copybooks = [corpus / "copy", corpus / "copyalt"]
    source, chain = predecessors(corpus, name)
    # The runner compiles <module>/lib/*.CBL as modules beside the programs.
    call_paths = [path for path in [corpus / name[:2] / "lib"] if path.is_dir()]
    work.mkdir(parents=True)
    if name in COMPILE_ONLY or name[:2] in UNTESTED_MODULES:
        convert(source, work / "rust", fmt="fixed", includes=copybooks, call_paths=call_paths, std="cobol85",
                runtime_checks=True)
        build_rust(work / "rust")
        return {"program": name, "source": source.name, "compile_only": True, "passed": True,
                "runner_counts": runner_counts(native_logs, name)}
    seed = native_seed(corpus, chain, copybooks, work) if chain else None
    rust_data = rust_seed(corpus, chain, copybooks, call_paths, work) if seed and has_berkeley_db(seed) else None
    stdin = source.with_suffix(".DAT")
    report = verify(source, fmt="fixed", includes=copybooks,
                    stdin=stdin.read_bytes() if stdin.exists() else RAW_INPUT.get(name, b""),
                    data_dir=seed, rust_data_dir=rust_data, call_paths=call_paths,
                    runtime_env=runner_env(name), debugging_lines=name in DEBUGGING_LINES,
                    cobc_flags=RUNNER_FLAGS, std="cobol85", no_ec_data_incompatible=name in NO_EC_DATA_INCOMPATIBLE,
                    runtime_checks=True)
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
    if name in RERUN_ENV:
        rerun = verify(source, fmt="fixed", includes=copybooks,
                       stdin=stdin.read_bytes() if stdin.exists() else RAW_INPUT.get(name, b""),
                       data_dir=seed, rust_data_dir=rust_data, call_paths=call_paths,
                       runtime_env={**runner_env(name), **RERUN_ENV[name]}, debugging_lines=name in DEBUGGING_LINES,
                       cobc_flags=RUNNER_FLAGS, std="cobol85", no_ec_data_incompatible=name in NO_EC_DATA_INCOMPATIBLE,
                    runtime_checks=True)
        entry["rerun_match"] = rerun["match"]
        entry["passed"] = entry["passed"] and rerun["match"]
    return entry


def guarded_check(task) -> dict:
    try:
        return check(*task)
    except (OSError, ValueError, CobolError, subprocess.SubprocessError) as exc:
        return {"program": task[2], "passed": False, "error": str(exc)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("programs", nargs="*", help="noms NIST, par ex. SQ143A")
    parser.add_argument("--accepted-from", type=Path,
                        help="rapport coverage.py : vérifier toutes ses émissions acceptées")
    parser.add_argument("--corpus", type=Path, default=Path(".tools/nist-ccvs85/extracted"))
    parser.add_argument("--native-logs", type=Path, default=Path(".tools/nist-native-gnucobol-3.2"))
    parser.add_argument("--work", type=Path, required=True, help="dossier de travail inexistant")
    parser.add_argument("-o", "--output", type=Path, required=True, help="nouveau rapport JSON")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1,
                        help="programmes vérifiés en parallèle (défaut : un par CPU)")
    args = parser.parse_args(argv)
    global NATIVE_LOGS
    NATIVE_LOGS = args.native_logs
    names = list(args.programs)
    if args.accepted_from:
        results = json.loads(args.accepted_from.read_text(encoding="utf-8"))["results"]
        # <module>/lib holds called modules: they are checked through their callers.
        names += [Path(r["source"]).stem for r in results
                  if r["status"] == "emission_accepted" and Path(r["source"]).parent.name != "lib"]
    if not names:
        parser.error("aucun programme demandé")
    if args.work.exists() or args.output.exists():
        parser.error("le dossier de travail et le rapport doivent être inexistants")
    if not find_tool("cobc") or not find_tool("cargo"):
        print("GnuCOBOL et Cargo sont requis", file=sys.stderr)
        return 2
    entries = []
    names = sorted(set(names))
    tasks = [(args.corpus.absolute(), args.native_logs.absolute(), name, args.work.absolute() / name) for name in names]
    # Each program has its own work directory; convert() sets the frontend
    # profile, which is global: one process per program at a time.
    with ProcessPoolExecutor(max_workers=max(1, min(args.jobs, len(tasks)))) as pool:
        for entry in pool.map(guarded_check, tasks):
            entries.append(entry)
            name = entry["program"]
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
