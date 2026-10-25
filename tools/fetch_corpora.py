"""Fetch pinned public COBOL corpora; never compile or execute their programs."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_nist import HTTPSRedirectsOnly, build_opener, check_digest, file_sha256


# Dépôts publics épinglés par commit ; les licences restent celles des dépôts.
REPOSITORIES = {
    "carddemo": ("https://github.com/aws-samples/aws-mainframe-modernization-carddemo.git",
                 "59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e", "Apache-2.0",
                 "Application CICS/VSAM/DB2 IBM Enterprise COBOL avec JCL et BMS"),
    "cobol-programming-course": ("https://github.com/openmainframeproject/cobol-programming-course.git",
                                 "780b1c9624e066b9d784a738896e493282c5fbf4", "CC-BY-4.0",
                                 "Exemples du cours Open Mainframe Project, IBM Enterprise COBOL"),
    "beg-cobol-for-programmers": ("https://github.com/Apress/beg-cobol-for-programmers.git",
                                  "3d2656fadd3cd3534beab8e00f85fe96ac41f5c2", "Freeware (Apress)",
                                  "Programmes du livre Beginning COBOL for Programmers, avec données"),
    "proleap-cobol-parser": ("https://github.com/uwol/proleap-cobol-parser.git",
                             "d1bfe75bdd6d480f70c74c6345bcc02610ac30d3", "MIT",
                             "Fichiers de test d'un parser COBOL 85 (fragments, dialectes)"),
    "che4z-lsp-for-cobol": ("https://github.com/eclipse-che4z/che-che4z-lsp-for-cobol.git",
                            "7ae2bceb8bcfd5f0692d2b8af8e846b93ae42a26", "EPL-2.0",
                            "Fichiers de test d'un serveur de langage COBOL IBM"),
    "zopeneditor-sample": ("https://github.com/IBM/zopeneditor-sample.git",
                           "8f9835308de6159eb54f226041d5f81a780cb8eb", "Apache-2.0",
                           "Petite application exemple IBM Z Open Editor"),
}
GNUCOBOL = ("https://ftp.gnu.org/gnu/gnucobol/gnucobol-3.2.tar.xz",
            "3bb48af46ced4779facf41fdc2ee60e4ccb86eaa99d010b36685315df39c2ee2")
COBOL_SUFFIXES = {".cbl", ".cob", ".cobol", ".cpy", ".copy", ".sub"}


def git(arguments: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *arguments], cwd=cwd, capture_output=True,
                            text=True, timeout=600)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(arguments)} échoué : {result.stderr.strip()}")
    return result.stdout.strip()


def clone_pinned(url: str, commit: str, destination: Path) -> None:
    destination.mkdir()
    git(["init", "-q"], destination)
    git(["fetch", "-q", "--depth", "1", url, commit], destination)
    git(["checkout", "-q", "--detach", "FETCH_HEAD"], destination)
    if git(["rev-parse", "HEAD"], destination) != commit:
        raise ValueError(f"Commit inattendu pour {url}")


def inventory(root: Path) -> dict:
    counts: dict[str, int] = {}
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(root).parts:
            suffix = path.suffix.lower()
            if suffix in COBOL_SUFFIXES:
                counts[suffix] = counts.get(suffix, 0) + 1
    return dict(sorted(counts.items()))


def fetch_gnucobol_testsuite(output: Path, local: Path | None = None) -> dict:
    """Keep the GnuCOBOL 3.2 sources: testsuite (.at) and libcob reference runtime."""
    url, expected = GNUCOBOL
    archive = output / "gnucobol-3.2.tar.xz"
    if local and local.is_file():
        # Archive already downloaded by install_gnucobol.sh: same pinned digest.
        shutil.copyfile(local, archive)
    else:
        with build_opener(HTTPSRedirectsOnly()).open(url, timeout=120) as response:
            with archive.open("xb") as stream:
                shutil.copyfileobj(response, stream)
    check_digest(archive, expected)
    destination = output / "gnucobol-3.2"
    destination.mkdir()
    def strip_top_level(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
        _, _, name = member.name.partition("/")
        return tarfile.data_filter(member.replace(name=name), path) if name else None

    with tarfile.open(archive, "r:xz") as package:
        package.extractall(destination, filter=strip_top_level)
    tests = sorted((destination / "tests" / "testsuite.src").glob("*.at"))
    setups = sum(path.read_text(encoding="utf-8", errors="replace").count("AT_SETUP(")
                 for path in tests)
    return {"name": "gnucobol-3.2", "url": url, "sha256": expected, "license": "GPL-3.0-or-later",
            "description": "Sources GnuCOBOL 3.2 : testsuite autotest et runtime libcob",
            "testsuite_files": len(tests), "testsuite_cases": setups}


def fetch(output: Path, names: list[str], with_gnucobol: bool, gnucobol_archive: Path | None = None) -> dict:
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"Le dossier de sortie doit être inexistant : {output}")
    output.mkdir(parents=True)
    entries = []
    for name in names:
        url, commit, license_name, description = REPOSITORIES[name]
        print(f"Clonage épinglé : {name} @ {commit[:12]}", flush=True)
        clone_pinned(url, commit, output / name)
        entries.append({"name": name, "url": url, "commit": commit, "license": license_name,
                        "description": description, "cobol_files": inventory(output / name)})
    if with_gnucobol:
        print("Téléchargement vérifié : gnucobol-3.2.tar.xz", flush=True)
        entries.append(fetch_gnucobol_testsuite(output, gnucobol_archive))
    manifest = {
        "corpora": entries, "programs_executed": False, "conformance_claimed": False,
        "notices": "Dépôts conservés avec leurs licences d'origine, hors des sources du projet ; "
                   "aucune licence de redistribution n'est revendiquée.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".tools/corpora"),
                        help="dossier de sortie inexistant (défaut : .tools/corpora)")
    parser.add_argument("--only", nargs="+", choices=sorted(REPOSITORIES), default=list(REPOSITORIES),
                        help="sous-ensemble de dépôts")
    parser.add_argument("--without-gnucobol", action="store_true",
                        help="ne pas récupérer les sources et la testsuite GnuCOBOL 3.2")
    parser.add_argument("--gnucobol-archive", type=Path,
                        default=Path(os.environ.get("WORK", "/opt/src")) / "gnucobol-3.2.tar.xz",
                        help="archive locale déjà téléchargée (empreinte vérifiée), sinon téléchargement")
    args = parser.parse_args(argv)
    try:
        manifest = fetch(args.output, args.only, not args.without_gnucobol, args.gnucobol_archive)
    except (OSError, ValueError, RuntimeError, URLError, tarfile.TarError, subprocess.TimeoutExpired) as exc:
        print(f"Récupération des corpus échouée : {exc}", file=sys.stderr)
        return 1
    for entry in manifest["corpora"]:
        print(f"{entry['name']}: {entry.get('cobol_files', entry.get('testsuite_cases'))}")
    print("Aucun programme des corpus exécuté ; aucune conformité revendiquée.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
