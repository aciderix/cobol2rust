#!/bin/bash
# Prépare une session cloud : GnuCOBOL 3.2, corpus NIST, corpus publics, cache Cargo.
# Idempotent : chaque étape est sautée si son résultat est déjà présent.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"
LOG="$ROOT/build/session-start.log"
mkdir -p build
: > "$LOG"
export PATH="$HOME/.cargo/bin:/usr/local/bin:$PATH"

step() { echo "[session-start] $*"; echo "== $*" >> "$LOG"; }

step "GnuCOBOL 3.2"
tools/install_gnucobol.sh >> "$LOG" 2>&1

if [ ! -f .tools/nist-ccvs85/manifest.json ]; then
    step "corpus NIST CCVS85"
    rm -rf .tools/nist-ccvs85
    python3 tools/prepare_nist.py --output .tools/nist-ccvs85 >> "$LOG" 2>&1 \
        || echo "[session-start] AVERTISSEMENT : préparation NIST échouée, voir $LOG"
fi

if [ ! -f .tools/corpora/manifest.json ]; then
    step "corpus publics et testsuite GnuCOBOL"
    rm -rf .tools/corpora
    python3 tools/fetch_corpora.py --output .tools/corpora >> "$LOG" 2>&1 \
        || echo "[session-start] AVERTISSEMENT : récupération des corpus échouée, voir $LOG"
fi

# Le premier build télécharge num-bigint ; le garder dans le cache Cargo.
step "cache Cargo"
WARM="$(mktemp -d)"
python3 -m cobol2rust convert examples/hello.cob -o "$WARM/hello" --build >> "$LOG" 2>&1 \
    || echo "[session-start] AVERTISSEMENT : build Rust de préchauffage échoué, voir $LOG"
rm -rf "$WARM"

echo "[session-start] prêt : $(cobc -V | head -1), $(rustc --version)"
