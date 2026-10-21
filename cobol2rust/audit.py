"""Read-only inventory of source acceptance; it does not claim behavioral equivalence."""
from __future__ import annotations

import os
from pathlib import Path

from .emitter import Emitter
from .frontend import CobolError, Parser, load_source

SKIP = {".git", ".tools", ".venv", "venv", "build", "target", "node_modules", "__pycache__"}


def sources(root: Path):
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise CobolError(f"chemin introuvable: {root}")
    paths = []
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = sorted(d for d in folders if d not in SKIP and not (Path(directory) / d).is_symlink())
        paths.extend(Path(directory) / f for f in files if Path(f).suffix.lower() in {".cob", ".cbl"})
    return sorted(paths)


def audit(root: Path, fmt="auto", includes=()):
    results = []
    for path in sources(root):
        result = {"source": str(path.resolve()), "accepted_by_frontend": False, "verified": False}
        try:
            expanded, copies = load_source(path, list(includes), fmt)
            program = Parser(expanded).parse()
            Emitter(program).generate()
            result.update(accepted_by_frontend=True, program=program.name, data_items=len(program.fields),
                          conditions=len(program.conditions), files=len(program.files), memory_bytes=program.memory_size,
                          copybooks=copies)
        except (CobolError, OSError, UnicodeError) as error:
            result["diagnostic"] = str(error)
        results.append(result)
    accepted = sum(item["accepted_by_frontend"] for item in results)
    return {"schema_version": 1, "root": str(root.resolve()), "static_only": True,
            "scope": "parse, layout and Rust emission checks; no input program is executed and no equivalence is established",
            "sources": len(results), "accepted": accepted, "blocked": len(results) - accepted, "results": results}
