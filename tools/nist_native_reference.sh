#!/usr/bin/env bash
# Run the official GnuCOBOL NIST runner and keep its per-program logs as the
# reference for tools/nist_verify.py. Needs the configured GnuCOBOL build tree
# left by install_gnucobol.sh and the corpus prepared by prepare_nist.py.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK=${WORK:-/opt/src}
RUNNER="$WORK/gnucobol-3.2/tests/cobol85"
OUTPUT="$ROOT/.tools/nist-native-gnucobol-3.2"

if [ -f "$OUTPUT/summary.log" ]; then
    echo "Référence native déjà présente : $OUTPUT"
    exit 0
fi
[ -f "$RUNNER/Makefile" ] || { echo "Arbre GnuCOBOL configuré absent : $RUNNER" >&2; exit 1; }
cp "$ROOT/.tools/nist-ccvs85/inputs/newcob.val" "$RUNNER/"
make -C "$RUNNER" test
rm -rf "$OUTPUT.partial"
mkdir -p "$OUTPUT.partial"
cp "$RUNNER/summary.log" "$RUNNER/summary.txt" "$OUTPUT.partial/"
for module in NC SM IC SQ RL IX ST SG OB IF RW DB CM; do
    [ -d "$RUNNER/$module" ] || continue
    mkdir -p "$OUTPUT.partial/$module"
    find "$RUNNER/$module" -maxdepth 1 -type f \( -name '*.log' -o -name 'report.txt' \) \
        -exec cp {} "$OUTPUT.partial/$module/" \;
done
mv "$OUTPUT.partial" "$OUTPUT"
grep -E "^Total" "$OUTPUT/summary.log"
