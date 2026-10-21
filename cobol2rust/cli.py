from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .binary import inspect_binary
from .emitter import Emitter
from .frontend import CobolError, Parser, load_source
from .toolchain import compiler_env, find_tool


def convert(source: Path, output: Path, fmt="auto", includes=()):
    expanded, copies = load_source(source, list(includes), fmt)
    program = Parser(expanded).parse()
    rust, mapping = Emitter(program).generate()
    output = output.resolve()
    # Never replace an existing project or an unrelated directory implicitly.
    if output.exists() and any(output.iterdir()):
        raise CobolError(f"dossier de sortie non vide: {output}; choisir un nouveau dossier")
    if output == source.parent.resolve() or output in source.resolve().parents:
        raise CobolError("le dossier de sortie doit être distinct du dossier source")
    crate = "cobol_" + re.sub(r"[^a-z0-9_]", "_", program.name.lower())
    manifest = f'[package]\nname = "{crate}"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\nnum-bigint = "=0.4.6"\n'
    report = {"schema_version": 1, "tool_version": __version__, "program": program.name,
              "source": str(source.resolve()), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "expanded_sha256": hashlib.sha256(expanded.encode("utf-8")).hexdigest(),
              "copybook_sha256": {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in copies},
              "copybooks": copies, "fields": [asdict(f) for f in program.fields.values()],
              "paragraphs": list(program.paragraphs), "source_map": mapping,
              "files": [asdict(f) for f in program.files.values()],
              "conditions": [asdict(c) for c in program.conditions.values()],
              "memory_size": program.memory_size,
              "storage_profile": {"binary_size": "1-2-4-8", "binary_byteorder": "big-endian", "display_sign": "ASCII trailing overpunch"},
              "file_runtime": {"organization": "LINE SEQUENTIAL", "records": "PIC X or groups of DISPLAY columns, printable ASCII",
                               "settings": ["COB_LS_FIXED", "COB_LS_SPLIT"],
                               "split_overflow": "explicit abort when COB_LS_SPLIT is enabled"} if program.files else None,
              "diagnostic_lines": "expanded.cob (after COPY expansion and fixed-format normalization)",
              "policy": "Reject unsupported syntax; SIZE ERROR handlers catch arithmetic overflow/division by zero and preserve the receiver; otherwise abort on overflow, invalid input or division by zero.",
              "verified_against_original": False}
    (output / "src").mkdir(parents=True, exist_ok=True)
    (output / "Cargo.toml").write_text(manifest, encoding="utf-8")
    (output / "src" / "main.rs").write_text(rust, encoding="utf-8")
    (output / "src" / "runtime.rs").write_text(Path(__file__).with_name("runtime.rs").read_text(encoding="utf-8"), encoding="utf-8")
    (output / "src" / "storage_runtime.rs").write_text(Path(__file__).with_name("storage_runtime.rs").read_text(encoding="utf-8"), encoding="utf-8")
    if program.files:
        (output / "src" / "file_runtime.rs").write_text(Path(__file__).with_name("file_runtime.rs").read_text(encoding="utf-8"), encoding="utf-8")
    (output / "expanded.cob").write_text(expanded + "\n", encoding="utf-8")
    (output / "conversion.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="COBOL vers Rust autonome; analyse PE/ELF sans exécution")
    parser.add_argument("--version", action="version", version=__version__)
    subs = parser.add_subparsers(dest="command", required=True)
    source = subs.add_parser("convert", help="convertir un source COBOL en projet Cargo")
    source.add_argument("source", type=Path)
    source.add_argument("-o", "--output", type=Path, required=True)
    source.add_argument("--format", choices=["auto", "free", "fixed"], default="auto")
    source.add_argument("-I", "--copybook-path", type=Path, action="append", default=[])
    source.add_argument("--build", action="store_true", help="compiler le Rust généré")
    source.add_argument("--run", action="store_true", help="compiler et exécuter le Rust généré")
    binary = subs.add_parser("inspect", help="inspecter un exécutable COBOL potentiel (sans le lancer)")
    binary.add_argument("binary", type=Path)
    binary.add_argument("-o", "--output", type=Path)
    binary.add_argument("--aret", help="chemin d'ARET pour les commandes proposées")
    verification = subs.add_parser("verify", help="compiler et exécuter un source de confiance avec COBOL et Rust, puis comparer")
    verification.add_argument("source", type=Path)
    verification.add_argument("--format", choices=["auto", "free", "fixed"], default="auto")
    verification.add_argument("-I", "--copybook-path", type=Path, action="append", default=[])
    verification.add_argument("--stdin-file", type=Path, help="entrées identiques fournies aux deux programmes")
    verification.add_argument("--data-dir", type=Path, help="fichiers d'entrée copiés dans deux dossiers d'exécution distincts")
    verification.add_argument("--runtime-env", action="append", default=[], metavar="NAME=VALUE", help="COB_LS_FIXED ou COB_LS_SPLIT identique pour les deux programmes")
    verification.add_argument("-o", "--output", type=Path, help="rapport JSON")
    inventory = subs.add_parser("audit", help="inventorier les sources COBOL acceptées et leurs blocages, sans exécution")
    inventory.add_argument("path", type=Path)
    inventory.add_argument("--format", choices=["auto", "free", "fixed"], default="auto")
    inventory.add_argument("-I", "--copybook-path", type=Path, action="append", default=[])
    inventory.add_argument("-o", "--output", type=Path)
    subs.add_parser("doctor", help="localiser les compilateurs sans modifier le PATH")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            print(json.dumps({name: find_tool(name) for name in ("python", "rustc", "cargo", "cobc")}, indent=2))
        elif args.command == "audit":
            from .audit import audit
            if args.output and args.output.exists():
                raise CobolError(f"rapport existant: {args.output}")
            report = audit(args.path, args.format, args.copybook_path)
            encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded, encoding="utf-8")
            print(encoded, end="")
            return 1 if report["blocked"] else 0
        elif args.command == "verify":
            from .verification import verify
            if args.output and args.output.exists():
                raise CobolError(f"rapport existant: {args.output}")
            environment = {}
            for item in args.runtime_env:
                if "=" not in item:
                    raise CobolError("--runtime-env requiert NAME=VALUE")
                key, value = item.split("=", 1)
                environment[key] = value
            report = verify(args.source, args.format, args.stdin_file.read_bytes() if args.stdin_file else b"", args.copybook_path,
                            args.data_dir, environment)
            encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            if args.output:
                if args.output.exists():
                    raise CobolError(f"rapport existant: {args.output}")
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded, encoding="utf-8")
            print(encoded, end="")
            return 0 if report["match"] else 1
        elif args.command == "inspect":
            report = inspect_binary(args.binary, args.aret)
            encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            if args.output:
                if args.output.exists():
                    raise CobolError(f"rapport existant: {args.output}")
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded, encoding="utf-8")
            else:
                print(encoded, end="")
        else:
            cargo = find_tool("cargo") if args.build or args.run else None
            if (args.build or args.run) and not cargo:
                raise CobolError("Cargo introuvable; installer Rust ou omettre --build/--run")
            report = convert(args.source, args.output, args.format, args.copybook_path)
            print(f"{report['program']} -> {args.output.resolve()}", flush=True)
            if cargo:
                command = [cargo, "run" if args.run else "build", "--quiet"]
                return subprocess.run(command, cwd=args.output, env=compiler_env(cargo), check=False).returncode
        return 0
    except (CobolError, OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        print(f"cobol2rust: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
