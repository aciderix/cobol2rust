"""Compare original COBOL and generated Rust, including files, in separate run directories."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cobol2rust.verification import verify as compare
from cobol2rust.toolchain import ROOT, find_tool


def verify_fixture(source, fmt, stdin):
    """One comparison per dialect listed in the fixture's `standards` option."""
    options = source.with_suffix(".json")
    config = json.loads(options.read_text(encoding="utf-8")) if options.is_file() else {}
    data = source.with_suffix(".data")
    results = []
    for std in config.get("standards", ["default"]):
        result = compare(source, fmt, stdin, data_dir=data if data.is_dir() else None, runtime_env=config.get("runtime_env"),
                         call_paths=[source.parent / path for path in config.get("call_paths", [])], std=std)
        result["fixture"] = source.name if std == "default" else f"{source.name} -std={std}"
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "verification.json")
    args = parser.parse_args()
    if not find_tool("cobc") or not find_tool("cargo"):
        print("Compilateurs manquants: python -m cobol2rust doctor", file=sys.stderr)
        return 2
    results = []
    cases = [(p, "fixed" if p.stem == "fixed" else "free", b"Alice\n3\n" if p.stem == "interactive" else b"")
             for p in sorted((ROOT / "examples").glob("*.cob"))]
    cases.extend((p, "free", b"") for p in sorted((ROOT / "tests" / "fixtures").glob("*.cob")))
    for source, fmt, stdin in cases:
        try:
            outcomes = verify_fixture(source, fmt, stdin)
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            outcomes = [{"fixture": source.name, "match": False, "error": str(exc)}]
        for result in outcomes:
            results.append(result)
            print(f"{'PASS' if result['match'] else 'FAIL'} {result['fixture']}", flush=True)
            if not result["match"]:
                print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(r["match"] for r in results)
    report = {"fixtures": len(results), "passed": passed, "failed": len(results) - passed, "results": results}
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{passed}/{len(results)} comparaisons conformes; rapport: {args.report}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
