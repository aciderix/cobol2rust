from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
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


def build_rust(project: Path) -> Path:
    cargo = find_tool("cargo")
    if not cargo:
        raise RuntimeError("Cargo introuvable")
    target = CACHE_ROOT / "rust-target"
    command = [cargo, "build", "--quiet", "--manifest-path", str(project / "Cargo.toml"), "--target-dir", str(target)]
    p = subprocess.run(command, env=compiler_env(cargo), capture_output=True, timeout=120)
    if p.returncode:
        raise RuntimeError("Rust compile:\n" + p.stderr.decode(errors="replace"))
    manifest = tomllib.loads((project / "Cargo.toml").read_text(encoding="utf-8"))
    return target / "debug" / (manifest["package"]["name"] + (".exe" if os.name == "nt" else ""))
