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
from .emitter import Emitter, generate_unit
from .frontend import CobolError, Parser, Stmt, load_source
from .toolchain import compiler_env, find_tool


SOURCE_SUFFIXES = (".CBL", ".cbl", ".COB", ".cob")


def statements(program):
    """Every statement of a program, nested bodies included."""
    def walk(item):
        if isinstance(item, Stmt):
            yield item
            yield from walk(item.args)
        elif isinstance(item, (list, tuple)):
            for element in item:
                yield from walk(element)
    for block in program.blocks:
        yield from walk(block.body)


def call_targets(program):
    literals, dynamic = set(), False
    for stmt in statements(program):
        if stmt.op == "call_program":
            if stmt.args[0][0] == "literal":
                literals.add(stmt.args[0][1])
            else:
                dynamic = True
    return literals, dynamic


def run_unit(source: Path, fmt, includes, call_paths):
    """Main program and every program it may CALL, found as <name>.CBL/.cob.

    Like GnuCOBOL's dynamic CALL, a literal name resolves to a module of that
    name in the call path. A name found nowhere raises EXCEPTION at run time.
    A dynamic CALL brings in every program of the call path that converts.
    """
    expanded, copies = load_source(source, list(includes), fmt)
    main = Parser(expanded).parse()
    if main.using:
        raise CobolError("programme principal avec PROCEDURE DIVISION USING non pris en charge")
    directories = [Path(path) for path in call_paths]
    units = {}
    # Programs after the main one in its source are in the executable itself:
    # GnuCOBOL's resolver finds them before searching the call path.
    local = {program.entry_name: program for program in main.siblings}
    pending, dynamic = call_targets(main)
    if dynamic:
        pending |= set(local)
    if dynamic:
        for directory in directories:
            for path in sorted(directory.iterdir()) if directory.is_dir() else []:
                if path.suffix in SOURCE_SUFFIXES:
                    try:
                        load_source(path, list(includes), fmt)
                        pending.add(path.stem)
                    except (CobolError, OSError):
                        continue
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen or name == main.entry_name:
            continue
        seen.add(name)
        if name in local:
            program = local[name]
            literals, more = call_targets(program)
            if more:
                raise CobolError(f"CALL dynamique dans un programme appelé non pris en charge: {name}")
            units[name] = (source, program, expanded, copies)
            pending |= literals
            continue
        path = next((directory / (name + suffix) for directory in directories for suffix in SOURCE_SUFFIXES
                     if (directory / (name + suffix)).is_file()), None)
        if path is None:
            continue
        sub_expanded, sub_copies = load_source(path, list(includes), fmt)
        try:
            program = Parser(sub_expanded).parse()
        except CobolError as exc:
            if dynamic and name not in call_targets(main)[0]:
                continue
            raise CobolError(f"programme appelé {path.name}: {exc}") from exc
        if program.siblings:
            raise CobolError(f"plusieurs programmes dans le source appelé non pris en charge: {path.name}")
        if program.entry_name != name:
            if program.entry_name.upper() == name.upper() or dynamic is False:
                raise CobolError(f"PROGRAM-ID {program.entry_name} de {path.name} différent du nom appelé {name}")
            continue
        units[name] = (path, program, sub_expanded, sub_copies)
        literals, more = call_targets(program)
        if more:
            raise CobolError(f"CALL dynamique dans un programme appelé non pris en charge: {name}")
        pending |= literals
    return main, expanded, copies, [units[name] for name in sorted(units)]


def emit_unit(source: Path, fmt="auto", includes=(), call_paths=()):
    """Rust source of the run unit of `source`, with its parsed programs."""
    main, expanded, copies, subprograms = run_unit(source, fmt, includes, call_paths)
    called = [main.entry_name, *(sub.entry_name for _, sub, _, _ in subprograms)]
    present = {path.stem for directory in map(Path, call_paths) if directory.is_dir()
               for path in directory.iterdir() if path.suffix in SOURCE_SUFFIXES}
    emitters = [Emitter(main, called=called, present=present)]
    for index, (_, sub, _, _) in enumerate(subprograms, 1):
        emitters.append(Emitter(sub, struct=f"Program{index}", subprogram=True, called=called, present=present))
    rust, mapping = generate_unit(emitters)
    return main, expanded, copies, subprograms, rust, mapping


def convert(source: Path, output: Path, fmt="auto", includes=(), call_paths=(), debugging_lines=False,
            std="default"):
    from . import frontend
    if std not in frontend.STANDARDS:
        raise CobolError(f"dialecte non modélisé: {std}; choisir parmi {', '.join(frontend.STANDARDS)}")
    previous = frontend.DEBUGGING_LINES, frontend.STD
    frontend.DEBUGGING_LINES, frontend.STD = debugging_lines, std
    try:
        program, expanded, copies, subprograms, rust, mapping = emit_unit(source, fmt, includes, call_paths)
    finally:
        frontend.DEBUGGING_LINES, frontend.STD = previous
    output = output.resolve()
    # Never replace an existing project or an unrelated directory implicitly.
    if output.exists() and any(output.iterdir()):
        raise CobolError(f"dossier de sortie non vide: {output}; choisir un nouveau dossier")
    if output == source.parent.resolve() or output in source.resolve().parents:
        raise CobolError("le dossier de sortie doit être distinct du dossier source")
    crate = "cobol_" + re.sub(r"[^a-z0-9_]", "_", program.name.lower())
    manifest = f'[package]\nname = "{crate}"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\nnum-bigint = "=0.4.6"\n'
    organizations = sorted({f.organization for f in program.files.values()})
    report = {"schema_version": 1, "tool_version": __version__, "program": program.name,
              "source": str(source.resolve()), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "expanded_sha256": hashlib.sha256(expanded.encode("utf-8")).hexdigest(),
              "copybook_sha256": {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in copies},
              "copybooks": copies, "fields": [asdict(f) for f in program.fields.values()],
              "paragraphs": list(program.paragraphs), "source_map": mapping,
              "sections": {name: {"start_block": start, "end_block_exclusive": end}
                           for name, (start, end) in program.sections.items()},
              "procedure_blocks": [{"index": index, "paragraph": block.name, "section": block.section}
                                   for index, block in enumerate(program.blocks)],
              "control_flow": {"model": "explicit program counter and PERFORM stack",
                               "returns": "top frame only; distinct paragraph and section checkpoints",
                               "times_counters": "shared per source site, including recursive re-entry"},
              "files": [asdict(f) for f in program.files.values()],
              "conditions": [asdict(c) for c in program.conditions.values()],
              "memory_size": program.memory_size,
              "subprograms": [{"program": sub.entry_name, "source": str(path.resolve()),
                               "in_main_source": sub in program.siblings,
                               "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "using": sub.using, "memory_size": sub.memory_size}
                              for path, sub, _, _ in subprograms],
              "call_paths": [str(Path(path).resolve()) for path in call_paths],
              "storage_profile": {"binary_size": "1-2-4-8", "binary_byteorder": "big-endian", "display_sign": "ASCII trailing overpunch"},
              "file_runtime": {"organization": organizations[0] if len(organizations) == 1 else "MIXED",
                               "organizations": organizations,
                               "records": "LINE SEQUENTIAL: printable ASCII DISPLAY; SEQUENTIAL: fixed raw bytes, equal-length FD aliases",
                               "advancing": "SEQUENTIAL only: BEFORE/AFTER, PAGE or literal 0..65535 lines; LF/CR/FF controls",
                               "settings": ["COB_LS_FIXED", "COB_LS_SPLIT"],
                               "settings_apply_to": "LINE SEQUENTIAL",
                               "split_overflow": "explicit abort when COB_LS_SPLIT is enabled"} if program.files else None,
              "diagnostic_lines": "expanded.cob (after COPY expansion and fixed-format normalization)",
              "policy": "Reject unsupported syntax; SIZE ERROR handlers catch arithmetic overflow/division by zero and preserve the receiver; otherwise abort on overflow, invalid input or division by zero.",
              "verified_against_original": False}
    (output / "src").mkdir(parents=True, exist_ok=True)
    (output / "Cargo.toml").write_text(manifest, encoding="utf-8")
    (output / "src" / "main.rs").write_text(rust, encoding="utf-8")
    (output / "src" / "runtime.rs").write_text(Path(__file__).with_name("runtime.rs").read_text(encoding="utf-8"), encoding="utf-8")
    (output / "src" / "storage_runtime.rs").write_text(Path(__file__).with_name("storage_runtime.rs").read_text(encoding="utf-8"), encoding="utf-8")
    if program.files or any(sub.files for _, sub, _, _ in subprograms):
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
    source.add_argument("--call-path", type=Path, action="append", default=[], help="dossier des programmes appelés par CALL")
    source.add_argument("--debugging-lines", action="store_true", help="compiler les lignes D comme cobc -fdebugging-line")
    source.add_argument("--std", choices=["default", "cobol85"], default="default", help="dialecte cobc modélisé (-std)")
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
    verification.add_argument("--call-path", type=Path, action="append", default=[], help="dossier des programmes appelés par CALL")
    verification.add_argument("--stdin-file", type=Path, help="entrées identiques fournies aux deux programmes")
    verification.add_argument("--data-dir", type=Path, help="fichiers d'entrée copiés dans deux dossiers d'exécution distincts")
    verification.add_argument("--runtime-env", action="append", default=[], metavar="NAME=VALUE", help="COB_LS_FIXED, COB_LS_SPLIT ou COB_SWITCH_n identique pour les deux programmes")
    verification.add_argument("--debugging-lines", action="store_true", help="lignes D actives (cobc -fdebugging-line)")
    verification.add_argument("--std", choices=["default", "cobol85"], default="default", help="dialecte cobc (-std) des deux côtés")
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
                            args.data_dir, environment, args.call_path, debugging_lines=args.debugging_lines,
                            std=args.std)
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
            report = convert(args.source, args.output, args.format, args.copybook_path, args.call_path,
                             args.debugging_lines, args.std)
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
