#!/usr/bin/env python3
"""Suite Python en parallèle, un processus par module de test.

Chaque module tourne dans son propre interpréteur (`python -m unittest
tests.<module>`), comme dans `unittest discover` mais isolé : les profils
globaux du frontend et les répertoires temporaires ne se croisent pas. Les
builds Rust prennent chacun un emplacement de compilation verrouillé
(toolchain.build_slot). Les modules les plus longs partent en premier, d'après
les durées du dernier passage (build/test-durations.json).

    python3 tools/run_tests.py            # un processus par CPU
    python3 tools/run_tests.py -j 1       # séquentiel
    python3 tools/run_tests.py test_goto test_inspect
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DURATIONS = ROOT / "build" / "test-durations.json"
SUMMARY = re.compile(r"^Ran (\d+) tests? in", re.M)
OUTCOME = re.compile(r"^(OK|FAILED)(?: \((.*)\))?$", re.M)


def run_module(module: str) -> dict:
    environment = {**os.environ, "CARGO_INCREMENTAL": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    start = time.monotonic()
    result = subprocess.run([sys.executable, "-m", "unittest", "-q", f"tests.{module}"], cwd=ROOT,
                            env=environment, capture_output=True, text=True)
    elapsed = time.monotonic() - start
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "expected failures": 0,
              "unexpected successes": 0}
    ran = SUMMARY.search(result.stderr)
    if ran:
        counts["tests"] = int(ran[1])
    outcome = OUTCOME.search(result.stderr)
    for part in (outcome[2] or "").split(", ") if outcome else []:
        key, _, value = part.partition("=")
        if key in counts and value.isdigit():
            counts[key] = int(value)
    passed = result.returncode == 0 and outcome is not None and outcome[1] == "OK"
    return {"module": module, "seconds": round(elapsed, 1), "passed": passed, "returncode": result.returncode,
            **counts, "output": "" if passed else (result.stdout + result.stderr)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("modules", nargs="*", help="modules de tests/ (défaut : tous)")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    modules = sorted(path.stem for path in (ROOT / "tests").glob("test_*.py"))
    if args.modules:
        unknown = sorted(set(args.modules) - set(modules))
        if unknown:
            parser.error("modules inconnus : " + ", ".join(unknown))
        modules = sorted(set(args.modules))
    try:
        known = json.loads(DURATIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = {}
    # Longest first (unknown durations first of all): the last module to
    # start is a short one, so the run ends close to sum / jobs.
    modules.sort(key=lambda module: -known.get(module, float("inf")))
    start = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(run_module, module) for module in modules]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "ok   " if result["passed"] else "ÉCHEC"
            print(f"{status} {result['module']:40} {result['tests']:4} tests {result['seconds']:7.1f} s", flush=True)
    elapsed = time.monotonic() - start
    known.update({result["module"]: result["seconds"] for result in results})
    DURATIONS.parent.mkdir(parents=True, exist_ok=True)
    DURATIONS.write_text(json.dumps(dict(sorted(known.items())), indent=1) + "\n", encoding="utf-8")
    failed = [result for result in sorted(results, key=lambda result: result["module"]) if not result["passed"]]
    for result in failed:
        print(f"\n===== {result['module']} (code {result['returncode']}) =====\n{result['output'].rstrip()}")
    totals = {key: sum(result[key] for result in results) for key in ("tests", "failures", "errors", "skipped")}
    print(f"\n{totals['tests']} tests dans {len(results)} modules en {elapsed:.0f} s (somme {sum(r['seconds'] for r in results):.0f} s, "
          f"{args.jobs} processus) : {totals['failures']} échecs, {totals['errors']} erreurs, {totals['skipped']} ignorés"
          + (f" ; modules en échec : {', '.join(result['module'] for result in failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
