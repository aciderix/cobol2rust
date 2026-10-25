#!/usr/bin/env python3
"""Programs of the GnuCOBOL 3.2 testsuite (tests/testsuite.src/*.at) as a
corpus for tools/real_corpora.py.

Each AT_SETUP test becomes a directory holding the files of its AT_DATA
blocks (programs, copybooks, input data). Only tests whose first compilation
is `$COMPILE <file>` or `$COMPILE_ONLY <file>` without any option are kept:
the measurement then compiles them with cobc's defaults, like the other
corpora; the others are counted in the manifest as excluded, by reason.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

QUADRIGRAPHS = {"@<:@": "[", "@:>@": "]", "@S|@": "$", "@%:@": "#", "@&t@": "", "@{:@": "(", "@}:@": ")"}


def quoted(text: str, start: int) -> tuple[str, int]:
    """The m4 quoted string opening at text[start] == '[' and the index after it."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    raise ValueError("unbalanced m4 quote")


def unquote(text: str) -> str:
    for key, value in QUADRIGRAPHS.items():
        text = text.replace(key, value)
    return text


def tests(at: str):
    """(title, body) of each AT_SETUP ... AT_CLEANUP."""
    for match in re.finditer(r"^AT_SETUP\(\[(.*?)\]\)(.*?)^AT_CLEANUP", at, re.S | re.M):
        yield match[1], match[2]


def data_blocks(body: str):
    for match in re.finditer(r"AT_DATA\(\[([^\]]+)\],\s*", body):
        if body[match.end()] != "[":
            continue
        content, _ = quoted(body, match.end())
        # The opening quote is usually followed by the newline of the macro.
        yield match[1], unquote(content[1:] if content.startswith("\n") else content)


def first_compile(body: str):
    """The first AT_CHECK that runs $COMPILE or $COMPILE_ONLY."""
    for match in re.finditer(r"AT_CHECK\(\[\$(COMPILE(?:_ONLY)?)((?: [^\]\s]+)+)\]", body):
        words = match[2].split()
        return match[1], words[:-1], words[-1]
    return None


def extract(source: Path, output: Path) -> dict:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    kept, excluded = [], {}
    for at in sorted(source.glob("*.at")):
        for number, (title, body) in enumerate(tests(at.read_text(encoding="latin-1")), 1):
            compile_ = first_compile(body)
            files = dict(data_blocks(body))
            reason = None
            if compile_ is None:
                reason = "sans $COMPILE ou $COMPILE_ONLY"
            elif compile_[1]:
                reason = "options de compilation"
            elif compile_[2] not in files or not compile_[2].endswith((".cob", ".cbl", ".CBL", ".COB")):
                reason = "programme compilé absent des AT_DATA"
            if reason:
                excluded[reason] = excluded.get(reason, 0) + 1
                continue
            directory = output / f"{at.stem}-{number:03d}"
            directory.mkdir()
            for name, content in files.items():
                path = directory / name
                if path.resolve().parent != directory.resolve():
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content.encode("latin-1"))
            kept.append({"test": directory.name, "title": title, "program": compile_[2], "mode": compile_[0]})
    manifest = {"source": str(source), "kept": len(kept), "excluded": excluded, "tests": kept}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=Path(".tools/corpora/gnucobol-3.2/tests/testsuite.src"))
    parser.add_argument("--output", type=Path, default=Path(".tools/corpora/gnucobol-testsuite"))
    args = parser.parse_args()
    manifest = extract(args.source, args.output)
    print(f"{manifest['kept']} tests retenus ; exclus : {manifest['excluded']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
