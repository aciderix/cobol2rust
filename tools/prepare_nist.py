"""Prepare the pinned NIST CCVS85 corpus; never execute its validation cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, build_opener


GNUCOBOL_COMMIT = "59b1b239c2de293be116aa75ed5376d9b311d45d"
GNUCOBOL_URL = f"https://raw.githubusercontent.com/OCamlPro/gnucobol/{GNUCOBOL_COMMIT}"
ASSETS = {
    "newcob.val.tar.gz": (
        "https://gnucobol.sourceforge.io/files/newcob.val.tar.gz",
        "e4513f26a9b38911f7bf882fe3d3339a80b45cabc2caf85eb3055b0f5ce87ee0",
    ),
    "Makefile.am": (f"{GNUCOBOL_URL}/tests/cobol85/Makefile.am",
                    "fd19f5c593589362592e86f6b6dca905c97ea2086b2ca7df779ad2a6c96ad63a"),
    "expand.pl": (f"{GNUCOBOL_URL}/tests/cobol85/expand.pl",
                  "19b09ac957ad42704f2ef669a586e7542e7c5776709e1c65cb70522ccfbf33c0"),
    "EXEC85.conf.in": (f"{GNUCOBOL_URL}/tests/cobol85/EXEC85.conf.in",
                       "47fbd7982b386d122df240738248e5a97d41c7b19cde86e04cb7704b1a75eed0"),
    "README": (f"{GNUCOBOL_URL}/tests/cobol85/README",
               "12d87332806e6b8674a029dc298b08020bce1a18bb252e404f97f05d646ce978"),
    "COPYING": (f"{GNUCOBOL_URL}/COPYING",
                "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"),
}
# Le site web du projet peut refuser les clients non navigateurs (403) ;
# le miroir de fichiers SourceForge sert la même archive, vérifiée par SHA256.
MIRRORS = {
    "newcob.val.tar.gz": ("https://downloads.sourceforge.net/project/gnucobol/nist/newcob.val.tar.gz",),
}
NEWCOB_SHA256 = "744a04982095a3abea29a9df5faf63d226083edecc7b5bf34bc412eae0d53274"
MODULES = ("NC", "SM", "IC", "SQ", "RL", "IX", "ST", "SG", "OB", "IF", "RW", "DB", "CM")
EXPECTED_COUNTS = {"cbl": 414, "sub": 44, "copybooks": 51, "data": 2}
EXTRACTOR_REPLACEMENTS = {
    b"002500": b'           SELECT           POPULATION-FILE',
    b"002700": b'           "NEWCOB_VAL" ORGANIZATION LINE SEQUENTIAL.',
    b"003000": b'           "newcob.tmp" ORGANIZATION LINE SEQUENTIAL.',
    b"003100": b'',
    b"003400": b'           "unused".',
    b"003700": b'           "newcob.log".',
    b"004000": b'           "EXEC85.conf" ORGANIZATION LINE SEQUENTIAL.',
}


class HTTPSRedirectsOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise ValueError(f"Redirection non HTTPS refusée : {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_digest(path: Path, expected: str) -> None:
    if file_sha256(path) != expected:
        raise ValueError(f"SHA256 incorrect : {path}; aucun artefact concerné ne sera exécuté")


def download(url: str, destination: Path, expected: str) -> None:
    if not url.startswith("https://"):
        raise ValueError("Les téléchargements doivent utiliser HTTPS")
    with build_opener(HTTPSRedirectsOnly()).open(url, timeout=60) as response:
        with destination.open("xb") as stream:
            shutil.copyfileobj(response, stream)
    check_digest(destination, expected)


def download_asset(name: str, destination: Path) -> str:
    """Try the pinned URL, then its mirrors on network errors only; return the URL used."""
    url, expected = ASSETS[name]
    candidates = (url, *MIRRORS.get(name, ()))
    for index, candidate in enumerate(candidates):
        try:
            download(candidate, destination, expected)
            return candidate
        except URLError:
            destination.unlink(missing_ok=True)
            if index == len(candidates) - 1:
                raise
    raise AssertionError("unreachable")


def extract_archive(archive: Path, destination: Path) -> Path:
    """Read the sole expected regular member without using tar path extraction."""
    with tarfile.open(archive, "r:gz") as package:
        members = package.getmembers()
        if (len(members) != 1 or members[0].name != "newcob.val"
                or not members[0].isfile() or members[0].size != 28210031):
            raise ValueError("Archive NIST inattendue : seul le fichier régulier newcob.val est autorisé")
        source = package.extractfile(members[0])
        assert source is not None
        output = destination / "newcob.val"
        with source, output.open("xb") as stream:
            shutil.copyfileobj(source, stream)
    check_digest(output, NEWCOB_SHA256)
    return output


def make_extractor(source: Path, destination: Path) -> None:
    """Apply exactly the EXEC85.cob substitutions from the pinned Makefile.am."""
    lines = source.read_bytes().splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(b"*HEADER,COBOL,EXEC85"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(b"*END"))
    with destination.open("xb") as stream:
        for line in lines[start + 1:end]:
            stream.write(EXTRACTOR_REPLACEMENTS[line[:6]] + b"\n"
                         if line[:6] in EXTRACTOR_REPLACEMENTS else line)


def run(command: list[str], cwd: Path, log: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=120)
    with log.open("ab") as stream:
        stream.write((json.dumps(command) + "\n").encode("utf-8"))
        stream.write(result.stdout)
        stream.write(result.stderr)
    if result.returncode:
        raise RuntimeError(f"Commande échouée ({result.returncode}), voir {log}")


def corpus_manifest(root: Path) -> tuple[dict, list[dict]]:
    files, counts = [], dict.fromkeys(EXPECTED_COUNTS, 0)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        kind = ("copybooks" if relative.parts[0] in {"copy", "copyalt"}
                else {".CBL": "cbl", ".SUB": "sub", ".DAT": "data"}.get(path.suffix))
        if kind:
            counts[kind] += 1
            files.append({"path": relative.as_posix(), "kind": kind,
                          "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"Corpus incomplet : {counts}; attendu : {EXPECTED_COUNTS}")
    return counts, files


def prepare(output: Path) -> dict:
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"Le dossier de sortie doit être inexistant : {output}")
    cobc, perl = shutil.which("cobc"), shutil.which("perl")
    if not cobc or not perl:
        raise ValueError("GnuCOBOL (cobc) et Perl doivent être présents dans le PATH")
    output.mkdir(parents=True)
    inputs, work, extracted = (output / name for name in ("inputs", "extractor", "extracted"))
    for directory in (inputs, work, extracted):
        directory.mkdir()
    used = {}
    for name in ASSETS:
        print(f"Téléchargement vérifié : {name}", flush=True)
        used[name] = download_asset(name, inputs / name)
    source = extract_archive(inputs / "newcob.val.tar.gz", inputs)
    make_extractor(source, work / "EXEC85.cob")
    log, env = output / "preparation.log", os.environ.copy()
    executable = work / ("EXEC85.exe" if os.name == "nt" else "EXEC85")
    run([cobc, "-V"], work, log, env)
    run([cobc, "-std=cobol85", "-debug", "-x", "EXEC85.cob", "-o", str(executable)], work, log, env)
    for module in MODULES:
        module_dir = extracted / module
        module_dir.mkdir()
        (module_dir / "EXEC85.conf").write_bytes(
            f"*SELECT-MODULE {module}\n".encode("ascii") + (inputs / "EXEC85.conf.in").read_bytes())
        run([str(executable)], module_dir, log,
            {**env, "NEWCOB_VAL": str(source), "COB_UNIX_LF": "Y"})
        run([perl, str(inputs / "expand.pl"), f"{module}/newcob.tmp", module], extracted, log, env)
    counts, files = corpus_manifest(extracted)
    manifest = {
        "corpus": "NIST CCVS85", "prepared": True, "validation_cases_executed": False,
        "conformance_claimed": False, "gnucobol_tools_commit": GNUCOBOL_COMMIT,
        "inputs": [{"path": f"inputs/{name}", "url": used[name], "sha256": expected}
                   for name, (_, expected) in ASSETS.items()],
        "newcob_val_sha256": NEWCOB_SHA256,
        "extractor_sha256": file_sha256(work / "EXEC85.cob"),
        "extractor_replacements": {key.decode(): value.decode() for key, value in EXTRACTOR_REPLACEMENTS.items()},
        "compiler": cobc, "compiler_flags": ["-std=cobol85", "-debug", "-x"],
        "extractor_environment": {"NEWCOB_VAL": str(source), "COB_UNIX_LF": "Y"},
        "modules": list(MODULES), "dbnoix": "alternative de DB, non dupliquée",
        "source_format": "fixed", "copy_directories": ["extracted/copy", "extracted/copyalt"],
        "source_transformations": "EXEC85.conf.in officiel : substitutions X-cards et mises à jour BEGIN-UPDATE",
        "counts": counts, "files": files,
        "scope": "414 .CBL dont 24 bibliothèques; 44 .SUB auxiliaires distincts; aucun test NIST exécuté",
        "notices": "Notices originales conservées dans les inputs et sources; outils GnuCOBOL GPLv3+ (inputs/COPYING). Aucune licence de redistribution du corpus n'est revendiquée.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".tools/nist-ccvs85"),
                        help="dossier de sortie inexistant (défaut : .tools/nist-ccvs85)")
    args = parser.parse_args(argv)
    try:
        manifest = prepare(args.output)
    except (OSError, ValueError, RuntimeError, URLError, tarfile.TarError, subprocess.TimeoutExpired, StopIteration) as exc:
        print(f"Préparation NIST échouée : {exc}", file=sys.stderr)
        return 1
    print(f"Corpus préparé : {args.output.absolute() / 'extracted'}; {manifest['counts']}")
    print("Aucun cas de validation NIST exécuté ; aucune conformité revendiquée.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
