from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = ROOT / "build" if (ROOT / "pyproject.toml").is_file() else Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache"))) / "cobol2rust"


def find_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    suffix = ".exe" if os.name == "nt" else ""
    candidates = [Path.home() / ".cargo" / "bin" / (name + suffix)]
    if name == "cobc":
        candidates.insert(0, ROOT / ".tools" / "gc32" / "bin" / (name + suffix))
    return next((str(p) for p in candidates if p.is_file()), None)


def compiler_env(tool: str) -> dict:
    env = os.environ.copy()
    bindir = Path(tool).resolve().parent
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    if Path(tool).stem == "cobc" and (bindir.parent / "config").is_dir():
        root = bindir.parent
        env["COB_CONFIG_DIR"] = str(root / "config")
        env["COB_COPY_DIR"] = str(root / "copy")
        env["COB_CFLAGS"] = f'-I"{root / "include"}"'
        env["COB_LDFLAGS"] = f'-L"{root / "lib"}"'
    return env


@contextmanager
def build_slot():
    """An exclusive Cargo target directory. Parallel builds (tests, measures)
    each take a free slot; slot 0 is the historical `rust-target`."""
    slots = max(1, os.cpu_count() or 1)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    order = list(range(slots))
    for attempt, blocking in ((order, False), ([os.getpid() % slots], True)):
        for slot in attempt:
            handle = open(CACHE_ROOT / f"rust-target-{slot}.lock", "a+b")
            if _lock(handle, blocking):
                try:
                    yield CACHE_ROOT / ("rust-target" if slot == 0 else f"rust-target-{slot}")
                    return
                finally:
                    _unlock(handle)
                    handle.close()
            handle.close()


def _lock(handle, blocking: bool) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        return True
    except OSError:
        if blocking:
            raise
        return False


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_UN)


def build_rust(project: Path, release: bool = False) -> Path:
    """Build `project` and return its executable, copied into the project's
    own target/ directory while the slot is held: a later build of a crate of
    the same name in that slot cannot replace it."""
    cargo = find_tool("cargo")
    if not cargo:
        raise RuntimeError("Cargo introuvable")
    manifest = tomllib.loads((project / "Cargo.toml").read_text(encoding="utf-8"))
    profile = "release" if release else "debug"
    name = manifest["package"]["name"] + (".exe" if os.name == "nt" else "")
    with build_slot() as target:
        # Cargo's fingerprint of a root package ignores its path: two crates of
        # the same name (PROGRAM-ID) would share it, and the second build could
        # keep the first one's executable.
        subprocess.run([cargo, "clean", "--quiet", "-p", manifest["package"]["name"], *(["--release"] if release else []),
                        "--manifest-path", str(project / "Cargo.toml"), "--target-dir", str(target)],
                       env=compiler_env(cargo), capture_output=True, timeout=120)
        command = [cargo, "build", "--quiet", *(["--release"] if release else []),
                   "--manifest-path", str(project / "Cargo.toml"), "--target-dir", str(target)]
        p = subprocess.run(command, env=compiler_env(cargo), capture_output=True, timeout=300)
        if p.returncode:
            raise RuntimeError("Rust compile:\n" + p.stderr.decode(errors="replace"))
        executable = project / "target" / profile / name
        executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target / profile / name, executable)
    return executable
