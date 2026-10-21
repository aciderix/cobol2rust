"""Differential execution against GnuCOBOL for a trusted source and one input."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from .cli import convert
from .frontend import CobolError, source_format
from .toolchain import build_rust, compiler_env, find_tool


def snapshot(directory: Path):
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise CobolError("liens symboliques non pris en charge dans les données de vérification")
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = path.read_bytes()
    return result


def manifest(files):
    return {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()}


def validate_file_paths(conversion):
    files = conversion.get("files", [])
    if files:
        for key in ("COB_RUNTIME_CONFIG", "COB_FILE_PATH", "COB_UNIX_LF", "COB_LS_NULLS", "COB_LS_USES_CR"):
            if key in os.environ:
                raise CobolError(f"configuration de fichiers non prise en charge: {key}")
    for spec in files:
        path = spec["path"]["text"]
        windows = PureWindowsPath(path)
        portable = PurePosixPath(path.replace("\\", "/"))
        if windows.drive or windows.root or portable.is_absolute() or ".." in portable.parts:
            raise CobolError("verify requiert des chemins ASSIGN relatifs sans '..' pour comparer les fichiers dans deux dossiers distincts")
        for key in (path, f"DD_{path}", f"dd_{path}"):
            if key in os.environ:
                raise CobolError(f"redirection de fichier par environnement non prise en charge: {key}")


def verify(source: Path, fmt="auto", stdin=b"", includes=(), data_dir: Path | None = None, runtime_env=None):
    cobc, rustc = find_tool("cobc"), find_tool("rustc")
    if not cobc or not rustc:
        raise CobolError("GnuCOBOL et rustc requis: python -m cobol2rust doctor")
    runtime_env = dict(runtime_env or {})
    if any(key not in {"COB_LS_FIXED", "COB_LS_SPLIT"} for key in runtime_env):
        raise CobolError("seuls COB_LS_FIXED et COB_LS_SPLIT peuvent être définis par le vérificateur")
    seed = {}
    seed_directories = []
    if data_dir:
        if not data_dir.is_dir():
            raise CobolError(f"dossier de données introuvable: {data_dir}")
        seed = snapshot(data_dir)
        seed_directories = [p.relative_to(data_dir).as_posix() for p in sorted(data_dir.rglob("*")) if p.is_dir()]
    with tempfile.TemporaryDirectory(prefix="cobol2rust-") as temporary:
        work = Path(temporary)
        output = work / "rust"
        conversion = convert(source, output, fmt, includes)
        validate_file_paths(conversion)
        suffix = ".exe" if os.name == "nt" else ""
        native = work / ("original" + suffix)
        fmt = source_format(source.read_text(encoding="utf-8-sig"), fmt)
        command = [cobc, "-x", "-free" if fmt == "free" else "-fixed", "-I", str(source.resolve().parent)]
        for include in includes:
            command.extend(["-I", str(Path(include).resolve())])
        command.extend([str(source.resolve()), "-o", str(native)])
        commands = [(command, cobc)]
        for command, compiler in commands:
            result = subprocess.run(command, cwd=work, env=compiler_env(compiler), capture_output=True, timeout=60)
            if result.returncode:
                raise CobolError(f"échec de compilation {Path(compiler).name}:\n{result.stderr.decode(errors='replace')}")
        try:
            translated = build_rust(output)
        except RuntimeError as exc:
            raise CobolError(str(exc)) from exc
        results, artifacts = [], []
        for name, binary, compiler in [("cobol", native, cobc), ("rust", translated, rustc)]:
            directory = work / ("run_" + name)
            directory.mkdir()
            for relative in seed_directories:
                (directory / relative).mkdir(parents=True, exist_ok=True)
            for relative, contents in seed.items():
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
            environment = compiler_env(compiler)
            environment.update(runtime_env)
            result = subprocess.run([str(binary)], cwd=directory, env=environment,
                                    input=stdin, capture_output=True, timeout=15)
            results.append(result)
            artifacts.append(snapshot(directory))
        a, b = results
        left, right = artifacts
        differences = sorted(name for name in left.keys() | right.keys() if left.get(name) != right.get(name))
        return {"schema_version": 1, "source": conversion["source"], "source_sha256": conversion["source_sha256"],
                "expanded_sha256": conversion["expanded_sha256"], "copybook_sha256": conversion["copybook_sha256"],
                "storage_profile": conversion["storage_profile"],
                "stdin_sha256": hashlib.sha256(stdin).hexdigest(),
                "scope": "original COBOL vs generated Rust: stdout bytes, zero exit codes and final file bytes for these inputs",
                "runtime_env": runtime_env, "input_files": manifest(seed), "input_directories": seed_directories,
                "files_match": not differences, "file_differences": differences,
                "cobol_files": manifest(left), "rust_files": manifest(right),
                "match": a.stdout == b.stdout and a.returncode == b.returncode == 0 and not differences,
                "cobol_stdout": a.stdout.decode("ascii", errors="backslashreplace"),
                "rust_stdout": b.stdout.decode("ascii", errors="backslashreplace"),
                "cobol_exit": a.returncode, "rust_exit": b.returncode,
                "cobol_stderr": a.stderr.decode(errors="replace"), "rust_stderr": b.stderr.decode(errors="replace")}
