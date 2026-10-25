#!/bin/bash
# Réinjecte le cap du projet dans le contexte : démarrage, reprise, /clear et
# après chaque compression (SessionStart sans filtre). Lecture seule, rapide.
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT" || exit 0

echo "=== CAP DU PROJET (CAP.md) — à respecter pour tout choix de travail ==="
sed -n '/<!-- cap:début -->/,/<!-- cap:fin -->/p' CAP.md | grep -v '<!-- cap:'
echo
echo "=== DERNIÈRE MESURE DES CORPUS RÉELS ==="
sed -n '/<!-- mesure:début -->/,/<!-- mesure:fin -->/p' CAP.md | grep -v '<!-- mesure:'
echo
if command -v python3 >/dev/null; then
    python3 tools/real_corpora.py --check 2>/dev/null \
        | sed 's/^mesure périmée/ATTENTION : mesure périmée/' \
        | sed '/^ATTENTION/s/$/ — relancer python3 tools\/real_corpora.py --cobc --record avant de conclure./'
fi
echo "=== JOURNAL DU CAP (dernières étapes) ==="
sed -n '/^## Journal du cap/,$p' CAP.md | grep '^- ' | tail -5
exit 0
