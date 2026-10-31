"""Differential execution against GnuCOBOL for a trusted source and one input."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from .cli import convert
from .frontend import CobolError, decode_source, source_format
from .toolchain import CACHE_ROOT, build_rust, compiler_env, find_tool

INDEXED_MAGIC = b"cobol2rust-btree-1\n"


def bdb_dumper() -> Path:
    """Compile bdb_dump.c (libdb) once: the logical content of cobc's files."""
    target = CACHE_ROOT / "bdb_dump"
    source = Path(__file__).with_name("bdb_dump.c")
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        return target
    compiler = find_tool("gcc") or find_tool("cc")
    if not compiler:
        raise CobolError("compilateur C requis pour comparer les fichiers INDEXED (Berkeley DB)")
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([compiler, "-O1", "-o", str(target), str(source), "-ldb"], capture_output=True)
    if result.returncode:
        raise CobolError("bdb_dump: libdb introuvable pour comparer les fichiers INDEXED:\n"
                         + result.stderr.decode(errors="replace"))
    return target


def indexed_contents(left, right, left_dir):
    """Replace each INDEXED file pair (cobc: a Berkeley DB btree; Rust:
    cobol2rust's own format) by its key/data pairs in btree order, as
    bdb_dump writes them. Other files stay compared byte for byte."""
    names = []
    for name in sorted(left.keys() & right.keys()):
        if left[name][12:16] == b"\x62\x31\x05\x00" and right[name].startswith(INDEXED_MAGIC):
            dump = subprocess.run([str(bdb_dumper()), str(left_dir / name)], capture_output=True)
            left[name] = dump.stdout if dump.returncode == 0 else b"<bdb_dump failed>" + dump.stderr
            right[name] = right[name][len(INDEXED_MAGIC):]
            names.append(name)
    return names


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


def validate_file_env(file_env):
    """File names given to both runs through cob_chk_file_mapping (DD_name,
    dd_name, name, COB_FILE_PATH): relative, so each run stays in its folder."""
    for key, value in file_env.items():
        portable = PurePosixPath(value.replace("\\", "/"))
        if (not key or "=" in key or (key.startswith("COB_") and key != "COB_FILE_PATH") or not value
                or PureWindowsPath(value).drive or portable.is_absolute() or ".." in portable.parts or "$" in value):
            raise CobolError(f"variable de fichier refusée par le vérificateur: {key}={value}")


def validate_file_paths(conversion, file_env=()):
    files = conversion.get("files", [])
    if files:
        for key in ("COB_RUNTIME_CONFIG", *(() if "COB_FILE_PATH" in file_env else ("COB_FILE_PATH",)), "COB_UNIX_LF", "COB_LS_NULLS", "COB_LS_USES_CR",
                    "COB_SEQ_CONCAT_NAME", "COB_SEQ_CONCAT_SEP"):
            if key in os.environ:
                raise CobolError(f"configuration de fichiers non prise en charge: {key}")
    for spec in files:
        if spec["path"] is None:
            # ASSIGN data-name: the name is only known at run time; both runs
            # share the same inputs and the directory snapshots are compared.
            continue
        path = spec["path"]["text"]
        windows = PureWindowsPath(path)
        portable = PurePosixPath(path.replace("\\", "/"))
        if windows.drive or windows.root or portable.is_absolute() or ".." in portable.parts:
            raise CobolError("verify requiert des chemins ASSIGN relatifs sans '..' pour comparer les fichiers dans deux dossiers distincts")
        for key in (path, f"DD_{path}", f"dd_{path}"):
            if key in os.environ and key not in file_env:
                raise CobolError(f"redirection de fichier par environnement non prise en charge: {key}")


def verify(source: Path, fmt="auto", stdin=b"", includes=(), data_dir: Path | None = None, runtime_env=None,
           call_paths=(), cobc_flags=(), debugging_lines=False, std="default", rust_data_dir: Path | None = None,
           no_ec_data_incompatible=False, file_env=None, timeout=15, release=False, runtime_checks=False,
           arguments=(), companions=()):
    """`rust_data_dir` seeds the Rust run instead of `data_dir`, for INDEXED
    files written by converted predecessors in cobol2rust's own format.
    `arguments` follow argv[0] on both command lines; argv[0] is the same
    for both programs (`./<source stem>`, or the module name under cobcrun),
    since libcob's messages (CBL_GC_GETOPT) print it. `companions` are
    other main programs the tested one runs (CALL "SYSTEM" "./name"): each
    is compiled by cobc for the GnuCOBOL run and converted for the Rust run,
    as `./<source stem>` in that run's directory."""
    arguments = [str(argument) for argument in arguments]
    companions = [Path(companion) for companion in companions]
    cobc, rustc = find_tool("cobc"), find_tool("rustc")
    if not cobc or not rustc:
        raise CobolError("GnuCOBOL et rustc requis: python -m cobol2rust doctor")
    runtime_env = dict(runtime_env or {})
    file_env = dict(file_env or {})
    validate_file_env(file_env)
    if any(key not in {"COB_LS_FIXED", "COB_LS_SPLIT", "COB_SET_DEBUG", "COB_CURRENT_DATE"} and not re.fullmatch(r"COB_SWITCH_\d+", key)
           for key in runtime_env):
        raise CobolError("seuls COB_LS_FIXED, COB_LS_SPLIT, COB_SET_DEBUG, COB_CURRENT_DATE et COB_SWITCH_n peuvent être définis par le vérificateur")
    seed = {}
    seed_directories = []
    if data_dir:
        if not data_dir.is_dir():
            raise CobolError(f"dossier de données introuvable: {data_dir}")
        seed = snapshot(data_dir)
        seed_directories = [p.relative_to(data_dir).as_posix() for p in sorted(data_dir.rglob("*")) if p.is_dir()]
    rust_seed = seed
    if rust_data_dir:
        if not rust_data_dir.is_dir() or not data_dir:
            raise CobolError(f"dossier de données Rust introuvable: {rust_data_dir}")
        rust_seed = snapshot(rust_data_dir)
    with tempfile.TemporaryDirectory(prefix="cobol2rust-") as temporary:
        work = Path(temporary)
        output = work / "rust"
        conversion = convert(source, output, fmt, includes, call_paths, debugging_lines, std, no_ec_data_incompatible,
                             runtime_checks)
        # The runtime checks of the conversion are cobc's -debug.
        if runtime_checks and not any(flag in {"-debug", "--debug"} for flag in cobc_flags):
            cobc_flags = [*cobc_flags, "-debug"]
        validate_file_paths(conversion, file_env)
        suffix = ".exe" if os.name == "nt" else ""
        native = work / ("original" + suffix)
        fmt = source_format(decode_source(source.read_bytes()), fmt)
        if any(flag.startswith("-std") and flag != f"-std={std}" for flag in cobc_flags):
            raise CobolError(f"options cobc incohérentes avec le dialecte converti: {std}")
        if std != "default" and not any(flag.startswith("-std") for flag in cobc_flags):
            cobc_flags = [f"-std={std}", *cobc_flags]
        options = [*cobc_flags, *(["-fdebugging-line"] if debugging_lines else []),
                   *(["-fno-ec=data-incompatible"] if no_ec_data_incompatible else []),
                   "-free" if fmt == "free" else "-fixed", "-I", str(source.resolve().parent)]
        for include in includes:
            options.extend(["-I", str(Path(include).resolve())])
        # Called programs become modules loaded by name, as GnuCOBOL's
        # default dynamic CALL does; only the converted ones are provided.
        modules = work / "modules"
        modules.mkdir()
        module = conversion.get("module")
        library = ".dll" if os.name == "nt" else ".so"
        if module:
            # PROCEDURE DIVISION USING: cobc -x refuses it; cobcrun runs the
            # module without arguments.
            cobcrun = find_tool("cobcrun")
            if not cobcrun:
                raise CobolError("cobcrun requis pour vérifier un module (PROCEDURE DIVISION USING)")
            commands = [([cobc, "-m", *options, str(source.resolve()), "-o", str(modules / (module + library))], cobc)]
        else:
            commands = [([cobc, "-x", *options, str(source.resolve()), "-o", str(native)], cobc)]
        for sub in conversion["subprograms"]:
            if sub["in_main_source"]:
                continue
            commands.append(([cobc, "-m", *options, sub["source"], "-o", str(modules / (sub["program"] + library))], cobc))
        for command, compiler in commands:
            result = subprocess.run(command, cwd=work, env=compiler_env(compiler), capture_output=True, timeout=60)
            if result.returncode:
                raise CobolError(f"échec de compilation {Path(compiler).name}:\n{result.stderr.decode(errors='replace')}")
        try:
            translated = build_rust(output, release=True) if release else build_rust(output)
        except RuntimeError as exc:
            raise CobolError(str(exc)) from exc
        companion_binaries = {"cobol": [], "rust": []}
        for index, companion in enumerate(companions):
            native_companion = work / f"companion{index}-native{suffix}"
            companion_format = source_format(decode_source(companion.read_bytes()), "auto")
            command = [cobc, "-x", *(f for f in options if f not in {"-free", "-fixed"}),
                       "-free" if companion_format == "free" else "-fixed", str(companion.resolve()), "-o", str(native_companion)]
            result = subprocess.run(command, cwd=work, env=compiler_env(cobc), capture_output=True, timeout=60)
            if result.returncode:
                raise CobolError(f"échec de compilation cobc du compagnon {companion.name}:\n{result.stderr.decode(errors='replace')}")
            companion_output = work / f"companion{index}-rust"
            convert(companion, companion_output, "auto", includes, call_paths, debugging_lines, std, no_ec_data_incompatible,
                    runtime_checks)
            try:
                companion_rust = build_rust(companion_output, release=True) if release else build_rust(companion_output)
            except RuntimeError as exc:
                raise CobolError(str(exc)) from exc
            companion_binaries["cobol"].append((companion.stem + suffix, native_companion))
            companion_binaries["rust"].append((companion.stem + suffix, companion_rust))
        results, artifacts = [], []
        for name, binary, compiler in [("cobol", native, cobc), ("rust", translated, rustc)]:
            directory = work / ("run_" + name)
            directory.mkdir()
            for relative in seed_directories:
                (directory / relative).mkdir(parents=True, exist_ok=True)
            for relative, contents in (seed if name == "cobol" else rust_seed).items():
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
            for executable_name, executable in companion_binaries[name]:
                shutil.copy2(executable, directory / executable_name)
            environment = compiler_env(compiler)
            environment.update(runtime_env)
            environment.update(file_env)
            if name == "cobol":
                environment["COB_LIBRARY_PATH"] = str(modules)
            # cobcrun shifts argv: libcob's argv[0] is the module name.
            argv0 = module if module else "./" + source.stem
            command = [cobcrun, module, *arguments] if name == "cobol" and module else [argv0, *arguments]
            executable = None if name == "cobol" and module else str(binary)
            result = subprocess.run(command, executable=executable, cwd=directory, env=environment,
                                    input=stdin, capture_output=True, timeout=timeout)
            results.append(result)
            artifacts.append(snapshot(directory))
        a, b = results
        left, right = artifacts
        indexed = indexed_contents(left, right, work / "run_cobol")
        companion_names = {executable_name for executable_name, _ in companion_binaries["cobol"]}
        for artifact in (left, right):
            for executable_name in companion_names:
                artifact.pop(executable_name, None)
        differences = sorted(name for name in left.keys() | right.keys() if left.get(name) != right.get(name))
        return {"schema_version": 1, "source": conversion["source"], "source_sha256": conversion["source_sha256"],
                "expanded_sha256": conversion["expanded_sha256"], "copybook_sha256": conversion["copybook_sha256"],
                "storage_profile": conversion["storage_profile"],
                "stdin_sha256": hashlib.sha256(stdin).hexdigest(), "arguments": arguments,
                "std": std, "cobc_flags": list(cobc_flags),
                "scope": "original COBOL vs generated Rust: stdout bytes, zero exit codes and final file bytes for these inputs",
                "runtime_env": runtime_env, "file_env": file_env, "input_files": manifest(seed), "rust_input_files": manifest(rust_seed), "input_directories": seed_directories,
                "files_match": not differences, "file_differences": differences,
                "indexed_files_compared_logically": indexed,
                "cobol_files": manifest(left), "rust_files": manifest(right),
                # Both runs end normally, or both die of SIGINT (cob_raise on
                # character 03 read by ACCEPT); other signals are never modelled.
                # Another exit status (RETURN-CODE, cob_fatal_error) matches
                # only with the same stderr bytes (libcob's messages).
                "match": a.stdout == b.stdout and a.returncode == b.returncode
                         and (a.returncode in {0, -2} or (a.returncode > 0 and a.stderr == b.stderr))
                         and not differences,
                "stderr_match": a.stderr == b.stderr,
                "cobol_stdout": a.stdout.decode("ascii", errors="backslashreplace"),
                "rust_stdout": b.stdout.decode("ascii", errors="backslashreplace"),
                "cobol_exit": a.returncode, "rust_exit": b.returncode,
                "cobol_stderr": a.stderr.decode(errors="replace"), "rust_stderr": b.stderr.decode(errors="replace")}
