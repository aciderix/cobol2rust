# cobol2rust — consignes permanentes

## Le cap passe avant tout

Lire **CAP.md** avant de choisir un travail : il fixe le cap (conversion du
COBOL réel, pas d'un corpus de test), la boussole (mesure des corpus réels)
et les règles de chaque étape. Le hook `.claude/hooks/compass.sh` le
réinjecte à chaque démarrage, reprise et compression du contexte ; s'il
signale une mesure périmée, la refaire avant de conclure quoi que ce soit.

- Le prochain chantier se choisit dans le tableau « Mesure » de CAP.md :
  d'abord l'écart « cobc accepte, cobol2rust refuse ». NIST CCVS85 n'est
  qu'un test de non-régression ; ne pas le reprendre comme objectif.
- Chaque étape se termine par la mesure (`python3 tools/real_corpora.py
  --cobc --record`), une ligne au journal de CAP.md et un commit qui inclut
  `measurements/` et CAP.md.
- Ne jamais écrire qu'une forme est prise en charge si elle n'est que
  partiellement implémentée ; ne jamais appeler « conforme » un programme
  seulement compilé ; toujours donner le dénominateur.

## Philosophie technique (voir HANDOFF.md, « Règles sémantiques à préserver »)

- GnuCOBOL 3.2 est la référence : porter son C (cobc, libcob) fidèlement,
  y compris ses bogues observables, et vérifier par un essai natif.
- Refuser par un diagnostic nommé plutôt qu'approximer. Accepter une source
  que cobc refuse est aussi un défaut (colonne « À examiner » de la mesure).
- Preuves : comparaison octet pour octet de stdout, fichiers et codes de
  retour (`cobol2rust verify`, `tools/verify.py`).

## Commandes

```bash
python3 -m unittest discover -q                 # suite complète (~8 min avec cobc)
python3 tools/real_corpora.py --cobc --record     # boussole : corpus réels face à cobc
python3 tools/real_corpora.py --check             # la mesure enregistrée est-elle à jour ?
python3 tools/coverage.py .tools/nist-ccvs85/extracted --format fixed --include-subprograms \
  --std cobol85 -I .tools/nist-ccvs85/extracted/copy -I .tools/nist-ccvs85/extracted/copyalt \
  --report build/coverage-nist.json             # non-régression : 451/458
```

Vérification NIST complète (environ 1 h 15) : dernière section de
VALIDATION.md, avec `CARGO_INCREMENTAL=0` (sinon plus de 20 Go de cache).
Lancer les commandes longues en tâche de fond de l'outil, jamais avec `&` :
un processus détaché ignore SIGINT et `test_runtime_registers` échoue.
Avant de reprendre, `git fetch` et repartir de `origin/main` si la branche de
travail y est déjà fusionnée (d'autres sessions poussent sur `main`).
Les corpus réels se récupèrent par `python3 tools/fetch_corpora.py --output
.tools/corpora --without-gnucobol` ; GnuCOBOL par `tools/install_gnucobol.sh`.

## Conventions

- Documentation, diagnostics et messages de commit en français ; sujets de
  commit courts et descriptifs, comme l'historique.
- Code : suivre le style environnant ; commentaires rares, qui nomment la
  fonction C portée (`cob_chk_file_mapping`, `cb_build_assignment_name`…).
- Mettre à jour README.md, COVERAGE.md, VALIDATION.md et HANDOFF.md quand
  le périmètre change.
