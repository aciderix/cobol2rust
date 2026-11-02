"""Inventaire des blocages de l'écart « cobc accepte, cobol2rust refuse ».

La mesure ne retient que le premier diagnostic de chaque source. Pour choisir
les chantiers qui débloquent le plus de sources, ce module relit chaque source
de l'écart avec le parseur en mode reprise (Parser.recovered) : une
instruction ou une déclaration refusée est notée, puis l'analyse reprend à la
suivante. Règles de rigueur :

- le premier diagnostic de l'inventaire doit être celui de la mesure, sinon
  la source est marquée `mismatch` et n'entre dans aucun calcul ;
- les diagnostics suivants sont indicatifs (une reprise peut en provoquer) ;
- une source n'est « débloquable » par un ensemble de chantiers que si son
  inventaire est complet (analyse menée jusqu'à la fin du source) et que
  tous ses diagnostics sont dans l'ensemble. C'est un plafond : l'émission
  Rust, qui suit l'analyse, peut encore refuser.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import re

MAX_DIAGNOSTICS = 40


def normalize(diagnostic: str) -> str:
    text = re.sub(r"^(ligne|line) \d+: ", "", diagnostic)
    return re.sub(r" \(près de .*\)$", "", text)[:120]


def inventory_source(source: str, fmt: str, includes: list[Path], first: str) -> dict:
    """Diagnostics of one refused source, the first one as measured."""
    from cobol2rust.cli import load_cached
    from cobol2rust.frontend import CobolError, Parser
    try:
        expanded, _ = load_cached(Path(source), includes, fmt)
    except (CobolError, OSError, UnicodeError) as error:
        diagnostics, complete = [str(error)], False
    else:
        parser = Parser(expanded)
        parser.recovered = []
        complete = True
        try:
            parser.parse()
        except CobolError as error:
            parser.recovered.append(str(error))
            complete = False
        except Exception as error:   # a later statement on a damaged state
            parser.recovered.append(f"{type(error).__name__}: {error}")
            complete = False
        diagnostics = parser.recovered[:MAX_DIAGNOSTICS]
        complete = complete and len(parser.recovered) <= MAX_DIAGNOSTICS
        if not diagnostics:
            # The parse succeeds: the refusal comes from the emission, which
            # stops at its first diagnostic.
            diagnostics, complete = [first], False
    names = list(dict.fromkeys(normalize(diagnostic) for diagnostic in diagnostics))
    return {"diagnostics": names, "complete": complete, "matches_measure": names[0] == normalize(first)}


def _inventory(arguments):
    return inventory_source(*arguments)


def inventory(rows: list[tuple[str, str, list[Path], str]], profile: tuple, jobs: int = 1) -> list[dict]:
    """inventory_source of each (source, format, includes, first diagnostic)."""
    from coverage import _worker_start
    if jobs <= 1 or len(rows) < 2:
        _worker_start(profile)
        return [_inventory(row) for row in rows]
    with ProcessPoolExecutor(max_workers=min(jobs, len(rows)), initializer=_worker_start, initargs=(profile,)) as pool:
        return list(pool.map(_inventory, rows, chunksize=1))


def plan(entries: list[dict], steps: int = 12) -> dict:
    """Per diagnostic counts, and a greedy order of the work that unblocks the
    most complete inventories."""
    usable = [entry for entry in entries if entry["matches_measure"]]
    first = Counter(entry["diagnostics"][0] for entry in usable)
    present = Counter(name for entry in usable for name in entry["diagnostics"])
    complete = [set(entry["diagnostics"]) for entry in usable if entry["complete"]]
    alone = Counter(next(iter(names)) for names in complete if len(names) == 1)
    chosen, unlocked, order = set(), 0, []
    for _ in range(steps):
        def gain(name):
            return sum(1 for names in complete if not names <= chosen and names <= chosen | {name})
        candidates = sorted({name for names in complete for name in names} - chosen,
                            key=lambda name: (-gain(name), -present[name], name))
        if not candidates or gain(candidates[0]) == 0:
            break
        best = candidates[0]
        step_gain = gain(best)
        chosen.add(best)
        unlocked += step_gain
        order.append({"diagnostic": best, "unlocked": step_gain, "cumulative": unlocked,
                      "first": first[best], "present": present[best]})
    rows = [{"diagnostic": name, "first": first[name], "present": count, "alone": alone[name]}
            for name, count in present.most_common()]
    return {"sources": len(entries), "matching": len(usable), "complete": len(complete),
            "distinct": len(present), "diagnostics": rows, "greedy": order}


def table(summary: dict, limit: int = 12) -> list[str]:
    """CAP.md lines: the greedy order, then the diagnostics present most often."""
    lines = [f"Inventaire de l'écart (tous les blocages par source, parseur en mode reprise) : "
             f"{summary['sources']} sources, {summary['matching']} au premier diagnostic identique à la mesure, "
             f"{summary['complete']} à inventaire complet, {summary['distinct']} diagnostics distincts. "
             "« Débloquées » est un plafond : seul l'inventaire complet du parseur compte, l'émission peut "
             "encore refuser.", "",
             "| Ordre | Chantier (diagnostic) | Sources débloquées | Cumul | 1er blocage de | Présent dans |",
             "| ---: | --- | ---: | ---: | ---: | ---: |"]
    for index, step in enumerate(summary["greedy"][:limit], 1):
        lines.append(f"| {index} | {step['diagnostic']} | {step['unlocked']} | {step['cumulative']} | "
                     f"{step['first']} | {step['present']} |")
    lines += ["", "Diagnostics les plus présents (sources où ils apparaissent ; seul blocage d'une source "
              "complète) :", ""]
    for row in summary["diagnostics"][:limit]:
        lines.append(f"- {row['present']} × {row['diagnostic']} (1er : {row['first']}, seul : {row['alone']})")
    return lines
