"""Mesure de référence du cap : acceptation des corpus COBOL réels, face à cobc.

C'est l'indicateur principal du projet (voir CAP.md). Les paramètres de chaque
corpus sont figés ici, pour que deux mesures successives soient comparables :
format, dialecte, extensions et répertoires de copybooks. Pour chaque source,
l'outil note l'émission Rust de cobol2rust et, avec --cobc, l'acceptation
syntaxique de GnuCOBOL 3.2 avec les mêmes paramètres. L'écart utile est
« cobc accepte, cobol2rust refuse » : c'est ce qu'il faut lever en priorité.

Rien n'est compilé ni exécuté : c'est le niveau 2 de preuve (COVERAGE.md).

Sorties :
- build/real-corpora/<corpus>.json : rapports complets de coverage.py ;
- measurements/real-corpora.json : tableau de bord versionné (dernière mesure) ;
- measurements/real-corpora-history.jsonl : une ligne par mesure enregistrée ;
- CAP.md : tableau régénéré entre les marqueurs « mesure ».
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

CORPORA_DIR = ROOT / ".tools" / "corpora"
SUMMARY = ROOT / "measurements" / "real-corpora.json"
HISTORY = ROOT / "measurements" / "real-corpora-history.jsonl"
CAP = ROOT / "CAP.md"
MARK_BEGIN, MARK_END = "<!-- mesure:début -->", "<!-- mesure:fin -->"
SOURCE_SUFFIXES = {".cbl", ".cob", ".cobol"}
COPY_SUFFIXES = {".cpy", ".copy"}

# Paramètres figés : les changer rend les mesures incomparables (le noter dans CAP.md).
# format "auto" = détection de cobc (default.conf), appliquée des deux côtés.
CORPORA = {
    "carddemo": {"format": "auto", "std": "default", "kind": "application réelle IBM (CICS/VSAM/DB2/IMS/MQ)"},
    "zopeneditor-sample": {"format": "auto", "std": "default", "kind": "application exemple IBM"},
    "cobol-programming-course": {"format": "auto", "std": "default", "kind": "cours IBM Enterprise COBOL"},
    "beg-cobol-for-programmers": {"format": "auto", "std": "default", "kind": "livre, programmes complets"},
    "proleap-cobol-parser": {"format": "auto", "std": "default", "kind": "tests de parseur (fragments, dialectes)"},
    "che4z-lsp-for-cobol": {"format": "auto", "std": "default", "kind": "tests de serveur de langage IBM"},
}


# Corpora of complete programs: --execute compiles, runs and compares their
# accepted main programs with GnuCOBOL (levels 3 and 4 of COVERAGE.md).
EXECUTED = ("carddemo", "zopeneditor-sample", "cobol-programming-course", "beg-cobol-for-programmers")


def execute_source(name: str, source: str) -> dict:
    """Run one accepted program natively and in Rust, empty stdin, with the
    files of its own directory as input data (a copy, under a short name that
    cobc accepts as a program file name)."""
    from cobol2rust import frontend
    from cobol2rust.frontend import CobolError
    from cobol2rust.verification import verify
    settings = CORPORA[name]
    frontend.STD = settings["std"]
    original = Path(source)
    includes = [original.parent, *copy_dirs(CORPORA_DIR / name)]
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / ("program" + original.suffix.lower())
        copy.write_bytes(original.read_bytes())
        try:
            report = verify(copy, fmt=settings["format"], includes=includes, data_dir=original.parent,
                            call_paths=[original.parent], std=settings["std"], release=True)
        except CobolError as error:
            return {"status": "refused", "diagnostic": normalize(str(error).splitlines()[0] if str(error) else "")}
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        except Exception as error:
            return {"status": "error", "diagnostic": f"{type(error).__name__}: {error}"[:200]}
    if report["match"]:
        return {"status": "identical", "exit": report["cobol_exit"]}
    reasons = []
    if report["cobol_stdout"] != report["rust_stdout"]:
        reasons.append("stdout")
    if report["file_differences"]:
        reasons.append("fichiers " + ", ".join(report["file_differences"][:5]))
    if report["cobol_exit"] != report["rust_exit"] or report["cobol_exit"] not in {0, -2}:
        reasons.append(f"sortie {report['cobol_exit']}/{report['rust_exit']}")
    return {"status": "different", "reasons": reasons, "rust_stderr": report["rust_stderr"][-200:]}


def execute_corpus(name: str, report: dict) -> dict:
    rows = [row for row in report["results"] if row["status"] == "emission_accepted" and not row.get("subprogram")]
    results = {}
    for row in rows:
        relative = Path(row["source"]).relative_to(CORPORA_DIR / name).as_posix()
        results[relative] = execute_source(name, row["source"])
        print(f"  {name}: {results[relative]['status']:9} {relative}", flush=True)
    counts = Counter(result["status"] for result in results.values())
    return {"programs": len(rows), **{key: counts.get(key, 0) for key in ("identical", "different", "refused", "timeout", "error")},
            "results": results}


def implementation_sha256() -> str:
    digest = hashlib.sha256()
    for path in sorted([*(ROOT / "cobol2rust").glob("*.py"), *(ROOT / "cobol2rust").glob("*.rs")]):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def git_head() -> str | None:
    result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() or None


def copy_dirs(root: Path) -> list[Path]:
    return sorted({path.parent for path in root.rglob("*") if path.suffix.lower() in COPY_SUFFIXES and path.is_file()})


def normalize(diagnostic: str) -> str:
    text = re.sub(r"^(ligne|line) \d+: ", "", diagnostic)
    return re.sub(r" \(près de .*\)$", "", text)[:120]


def measure_corpus(name: str) -> dict:
    from cobol2rust import frontend
    from coverage import measure
    settings = CORPORA[name]
    frontend.STD = settings["std"]
    root = CORPORA_DIR / name
    report, _ = measure(root, settings["format"], copy_dirs(root), corpus_id=name, extensions=SOURCE_SUFFIXES)
    return report


def cobc_accepts(source: str, settings: dict, includes: list[Path]) -> bool | None:
    # cobc refuses a file whose base name is not a valid program name (length,
    # spaces): a link with a short name removes this artefact of the file name.
    # The source directory stays first in the copybook search, as for cobc.
    command = ["cobc", "-fsyntax-only", f"-I{Path(source).parent}"] + [f"-I{path}" for path in includes]
    if settings["std"] != "default":
        command.append(f"-std={settings['std']}")
    if settings["format"] != "auto":
        command.append(f"-f{settings['format']}")
    with tempfile.TemporaryDirectory() as directory:
        link = Path(directory) / ("source" + Path(source).suffix.lower())
        link.symlink_to(source)
        try:
            return subprocess.run([*command, link.name], capture_output=True, timeout=120, cwd=directory).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return None


def cobc_version() -> str | None:
    try:
        return subprocess.run(["cobc", "-V"], capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return None


def summarize(name: str, report: dict, cobc: dict | None, commit: str | None) -> dict:
    rows = report["results"]
    accepted = [row for row in rows if row["status"] == "emission_accepted"]
    refused = [row for row in rows if row["status"] != "emission_accepted"]
    entry = {"kind": CORPORA[name]["kind"], "commit": commit, "settings": CORPORA[name],
             "sources": len(rows), "accepted": len(accepted),
             "internal_errors": sum(row["status"] == "internal_error" for row in rows),
             "blockers": Counter(normalize(row.get("diagnostic", row["status"])) for row in refused).most_common(12)}
    if cobc is not None:
        gap = [row for row in refused if cobc.get(row["source"])]
        entry.update(cobc_accepted=sum(1 for value in cobc.values() if value),
                     accepted_where_cobc_refuses=sum(1 for row in accepted if cobc.get(row["source"]) is False),
                     accepted_where_cobc_refuses_sources=sorted(
                         Path(row["source"]).relative_to(CORPORA_DIR / name).as_posix()
                         for row in accepted if cobc.get(row["source"]) is False),
                     gap=len(gap),
                     gap_sources=sorted([Path(row["source"]).relative_to(CORPORA_DIR / name).as_posix(),
                                         normalize(row.get("diagnostic", row["status"]))] for row in gap),
                     gap_blockers=Counter(normalize(row.get("diagnostic", row["status"])) for row in gap).most_common(12))
    return entry


def cap_table(summary: dict) -> str:
    lines = [f"Dernière mesure : {summary['measured_at']} (commit `{(summary['git_head'] or '?')[:10]}`, "
             f"{summary['cobc'] or 'cobc absent'}). Commande : `python3 tools/real_corpora.py --cobc --record`.",
             "",
             "| Corpus | Nature | Sources | cobol2rust accepte | cobc accepte | Écart (cobc oui, nous non) "
             "| À examiner (nous oui, cobc non) |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, entry in summary["corpora"].items():
        lines.append(f"| {name} | {entry['kind']} | {entry['sources']} | {entry['accepted']} | "
                     f"{entry.get('cobc_accepted', '—')} | {entry.get('gap', '—')} | "
                     f"{entry.get('accepted_where_cobc_refuses', '—')} |")
    totals = summary["totals"]
    lines.append(f"| **Total** | | **{totals['sources']}** | **{totals['accepted']}** | "
                 f"**{totals.get('cobc_accepted', '—')}** | **{totals.get('gap', '—')}** | "
                 f"**{totals.get('accepted_where_cobc_refuses', '—')}** |")
    execution = summary.get("execution")
    if execution:
        stale_note = "" if execution["implementation_sha256"] == summary["implementation_sha256"] else \
            " — **antérieure au convertisseur actuel, à refaire avec `--execute`**"
        lines += ["", f"Exécution comparée à cobc (niveaux 3-4) : {execution['measured_at']}, commit "
                  f"`{(execution['git_head'] or '?')[:10]}`{stale_note}. Commande : "
                  "`python3 tools/real_corpora.py --cobc --execute --record`.", "",
                  "| Corpus | Programmes acceptés | Identiques | Divergents | Refusés à la compilation/exécution | Délais/erreurs |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for name, entry in execution["corpora"].items():
            lines.append(f"| {name} | {entry['programs']} | {entry['identical']} | {entry['different']} | "
                         f"{entry['refused']} | {entry['timeout'] + entry['error']} |")
    gap = Counter()
    for entry in summary["corpora"].values():
        for diagnostic, count in entry.get("gap_blockers") or entry["blockers"]:
            gap[diagnostic] += count
    lines += ["", "Premiers blocages là où cobc accepte (tous corpus, premier diagnostic par source) :", ""]
    lines += [f"{rank}. {count} × {diagnostic}" for rank, (diagnostic, count) in enumerate(gap.most_common(10), 1)]
    return "\n".join(lines)


def update_cap(summary: dict) -> None:
    text = CAP.read_text(encoding="utf-8")
    begin, end = text.index(MARK_BEGIN) + len(MARK_BEGIN), text.index(MARK_END)
    CAP.write_text(text[:begin] + "\n" + cap_table(summary) + "\n" + text[end:], encoding="utf-8")


def stale() -> str | None:
    """Return why the recorded measurement does not describe the current converter."""
    if not SUMMARY.exists():
        return "aucune mesure enregistrée"
    recorded = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if recorded.get("implementation_sha256") != implementation_sha256():
        return f"le convertisseur a changé depuis la mesure du {recorded.get('measured_at')}"
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", choices=sorted(CORPORA), default=list(CORPORA))
    parser.add_argument("--cobc", action="store_true", help="mesurer aussi l'acceptation de cobc -fsyntax-only")
    parser.add_argument("--record", action="store_true",
                        help="enregistrer measurements/ et le tableau de CAP.md (tous les corpus requis)")
    parser.add_argument("--execute", action="store_true",
                        help="compiler, exécuter et comparer à cobc les programmes acceptés de " + ", ".join(EXECUTED))
    parser.add_argument("--check", action="store_true",
                        help="code 1 si la mesure enregistrée ne correspond plus au convertisseur actuel")
    args = parser.parse_args(argv)
    if args.check:
        reason = stale()
        print(f"mesure périmée : {reason}" if reason else "mesure à jour")
        return 1 if reason else 0
    if args.record and set(args.only) != set(CORPORA):
        parser.error("--record exige tous les corpus, pour garder un dénominateur stable")
    manifest_path = CORPORA_DIR / "manifest.json"
    if not manifest_path.exists():
        print("corpus absents : lancer python3 tools/fetch_corpora.py --output .tools/corpora --without-gnucobol",
              file=sys.stderr)
        return 2
    pins = {entry["name"]: entry.get("commit") for entry in json.loads(manifest_path.read_text())["corpora"]}
    from fetch_corpora import REPOSITORIES
    for name in args.only:
        if pins.get(name) != REPOSITORIES[name][1]:
            print(f"{name} : commit {pins.get(name)} différent de l'épinglage {REPOSITORIES[name][1]}", file=sys.stderr)
            return 2
    with ProcessPoolExecutor(max_workers=min(len(args.only), os.cpu_count() or 1)) as pool:
        reports = dict(zip(args.only, pool.map(measure_corpus, args.only)))
    output = ROOT / "build" / "real-corpora"
    output.mkdir(parents=True, exist_ok=True)
    corpora = {}
    for name in args.only:
        (output / f"{name}.json").write_text(json.dumps(reports[name], indent=1, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
        cobc = None
        if args.cobc:
            includes = copy_dirs(CORPORA_DIR / name)
            sources = [row["source"] for row in reports[name]["results"]]
            with ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as pool:
                cobc = dict(zip(sources, pool.map(lambda source: cobc_accepts(source, CORPORA[name], includes), sources)))
        corpora[name] = summarize(name, reports[name], cobc, pins.get(name))
    totals = {key: sum(entry[key] for entry in corpora.values()) for key in ("sources", "accepted")}
    if args.cobc:
        totals.update({key: sum(entry[key] for entry in corpora.values()) for key in ("cobc_accepted", "gap", "accepted_where_cobc_refuses")})
    measured_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    summary = {"schema": 1, "measured_at": measured_at,
               "git_head": git_head(), "implementation_sha256": implementation_sha256(),
               "cobc": cobc_version() if args.cobc else None,
               "scope": "niveau 2 (émission acceptée) ; le bloc execution, s'il existe, porte les niveaux 3 et 4",
               "totals": totals, "corpora": corpora}
    if args.execute:
        executed = {name: execute_corpus(name, reports[name]) for name in args.only if name in EXECUTED}
        summary["execution"] = {"measured_at": measured_at, "git_head": summary["git_head"],
                                "implementation_sha256": summary["implementation_sha256"],
                                "scope": "stdin vide, fichiers du dossier du programme en entrée ; "
                                         "stdout, fichiers finaux et code de sortie comparés à cobc",
                                "corpora": executed}
    elif SUMMARY.exists() and "execution" in json.loads(SUMMARY.read_text(encoding="utf-8")):
        # The last execution stays in the record with its own date and hash.
        summary["execution"] = json.loads(SUMMARY.read_text(encoding="utf-8"))["execution"]
    # Unrecorded working copy, for inspecting the gap between two records.
    (output / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, entry in corpora.items():
        print(f"{name:28} {entry['accepted']:5}/{entry['sources']:<5} cobc {entry.get('cobc_accepted', '—'):>5}"
              f"  écart {entry.get('gap', '—'):>4}  à examiner {entry.get('accepted_where_cobc_refuses', '—')}")
    print(f"{'TOTAL':28} {totals['accepted']:5}/{totals['sources']:<5} cobc {totals.get('cobc_accepted', '—'):>5}"
          f"  écart {totals.get('gap', '—'):>4}  à examiner {totals.get('accepted_where_cobc_refuses', '—')}")
    if args.execute:
        for name, entry in summary["execution"]["corpora"].items():
            print(f"exécution {name:18} {entry['identical']}/{entry['programs']} identiques, {entry['different']} divergents, "
                  f"{entry['refused']} refusés, {entry['timeout']} délais, {entry['error']} erreurs")
    if args.record:
        if not args.cobc:
            parser.error("--record exige --cobc : l'écart à cobc fait partie du tableau de bord")
        SUMMARY.parent.mkdir(exist_ok=True)
        SUMMARY.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        line = {"measured_at": summary["measured_at"], "git_head": summary["git_head"],
                "implementation_sha256": summary["implementation_sha256"], "totals": totals,
                "execution": {name: {key: entry[key] for key in ("programs", "identical", "different", "refused", "timeout", "error")}
                              for name, entry in summary["execution"]["corpora"].items()} if args.execute else None,
                "corpora": {name: {key: entry.get(key) for key in ("sources", "accepted", "cobc_accepted", "gap",
                                                       "accepted_where_cobc_refuses")}
                            for name, entry in corpora.items()}}
        with HISTORY.open("a", encoding="utf-8") as history:
            history.write(json.dumps(line, ensure_ascii=False) + "\n")
        update_cap(summary)
        print(f"enregistré : {SUMMARY.relative_to(ROOT)}, {HISTORY.relative_to(ROOT)}, CAP.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
