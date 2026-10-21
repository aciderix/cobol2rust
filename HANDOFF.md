# Handoff — COBOL vers Rust

État au 21 octobre 2026, après livraison de la version **0.4.0**.

## Objectif et dossier de travail

L'utilisateur souhaite un convertisseur automatique COBOL vers Rust, avec
sources disponibles ou, à terme, à partir d'un programme compilé. Il a autorisé
l'exploration, les développements et les tests dans le dossier `Cobol` du Bureau.

**Projet à poursuivre : `C:\Users\fromt\Desktop\Cobol`.**
Le dossier initial de la conversation est
`C:\Users\fromt\Desktop\Automatic-reverse-engineering-toolkit` (ARET).
Attention à préciser le bon répertoire pour les commandes : ARET a été exploré
comme base possible du futur parcours binaire, mais ses sources n'ont pas été
modifiées pendant ces travaux.

Le dossier Cobol était initialement vide. Aucun source métier ni exécutable
COBOL de l'utilisateur n'a encore été fourni. Les exemples et fixtures actuels
ont été créés pour développer et vérifier le convertisseur.

## État fonctionnel

Le paquet Python `cobol2rust` produit des projets Cargo lisibles et des
exécutables Rust autonomes, sans runtime COBOL à l'exécution. La dépendance
Rust `num-bigint = "=0.4.6"` est liée statiquement.

Le sous-ensemble source comprend notamment :

- Formats libre/fixe, COPY simples avec répertoires `-I` et détection des cycles.
- Groupes, noms qualifiés OF/IN, FILLER, niveaux 88, REDEFINES et sous-chaînes.
- PIC X, 9, S, V ; usages DISPLAY, COMP/BINARY/COMP-4 et COMP-3.
- Tableaux fixes imbriqués et OCCURS DEPENDING ON terminal, sous restrictions.
- INDEXED BY, SET TO/UP BY/DOWN BY, index signés de 32 bits et PERFORM VARYING.
- Calcul décimal, ROUNDED, ON SIZE ERROR et NOT ON SIZE ERROR sur les cinq
  verbes arithmétiques ; une destination GIVING.
- IF, EVALUATE, boucles, paragraphes, PERFORM THRU et enchaînement séquentiel.
- Console et fichiers LINE SEQUENTIAL, y compris enregistrements structurés,
  statuts, fichiers optionnels et branches de fin de fichier.

Les commandes disponibles sont `convert`, `verify`, `audit`, `inspect`,
`doctor` et `--version`. `audit` est une analyse statique ; il ne prouve pas
l'équivalence d'un programme. `inspect` lit PE/ELF sans lancer le binaire.

**Le parcours exécutable sans source → Rust n'est pas implémenté.**
L'inspection propose seulement des commandes ARET. Ne pas présenter cette
fonction comme une décompilation opérationnelle.

## Validations déjà réalisées

- **34 tests Python réussis**, comprenant l'exécution des **3 tests Rust** du
  moteur décimal ; dernière commande : `python -m unittest discover -v`.
- **41 programmes comparés à GnuCOBOL, 41 conformes** sur les octets de stdout,
  les codes de retour nuls et les noms/octets des fichiers finaux.
  Rapport : `build/verification-v0.4.json`.
- Le dernier rapport a été contrôlé contre les empreintes des sources actuelles.
  Il inclut les bornes d'index -2147483648 et +2147483647.
- Le wheel a été installé et utilisé hors du dossier source : import, version,
  conversion, compilation, audit des exemples et exécution de la démo réussis.
  Les 14 fichiers Python/Rust du wheel ont été comparés aux fichiers du projet.
- L'archive source contient 75 fichiers, comparés au projet au moment de sa
  création. Elle précède l'ajout du présent HANDOFF.md.

Ces résultats portent sur les entrées du corpus livré. La compilation et
l'exécution sous Linux n'ont pas été testées ; aucun environnement WSL
opérationnel n'était disponible.

## Reprise rapide sous Windows

```powershell
cd C:\Users\fromt\Desktop\Cobol
python -m cobol2rust --version
python -m cobol2rust doctor
python -m unittest discover -v
python tools/verify.py --report build/verification-reprise.json
```

Le corpus différentiel prend plusieurs minutes. Il compile le source COBOL
original, sans passer par notre frontend, et le Rust généré séparément. Les
deux exécutions reçoivent des copies des mêmes données dans deux dossiers
temporaires distincts ; les données d'origine sont préservées.

```powershell
python -m cobol2rust verify examples/variable_batch.cob --data-dir examples/variable_batch.data
python -m cobol2rust convert examples/variable_batch.cob -o build/reprise-variable
```

Une sortie de conversion doit être vide ou inexistante. Ne pas écraser un
projet généré existant pour reprendre un essai. La conversion seule ne copie
pas les fichiers d'entrée ; `verify --data-dir` les prépare pour les deux
exécutions. Pour lancer le Rust de cet exemple directement, copier `amounts.txt`
depuis `examples/variable_batch.data` dans son répertoire d'exécution.

## Environnement et artefacts locaux

- Python 3.11.9 sur le PATH.
- Rust 1.96.0, cible `stable-x86_64-pc-windows-gnu` ; outils dans
  `C:\Users\fromt\.cargo\bin`. Le détecteur les trouve sans modifier le PATH
  système. MinGW est disponible.
- GnuCOBOL portable 3.2.0 / GCC 9.2 : `.tools/gc32/bin/cobc.exe`.
  `toolchain.compiler_env` prépare ses chemins de configuration et de liaison.
- Sources GnuCOBOL consultables dans `.tools/gnucobol/gnucobol-3.2_win`.
- Démo compilée : `build/demo-variable-v0.4` ; exécutable dans
  `target/debug/cobol_variable_batch.exe` sous ce dossier.
- Wheel : `build/dist/cobol2rust-0.4.0-py3-none-any.whl`.
- Sources distribuables : `build/dist/cobol2rust-0.4.0-source.zip`.
- Scripts exploratoires : `build/probe_v04.py`, `build/probes-v04`.
- Contrôle de livraison déjà exécuté : `build/release_check_v04.py`.
  Il utilise des dossiers de sortie fixes déjà remplis ; ne pas le relancer
  tel quel sans lui attribuer de nouvelles sorties.
- `.tools`, `build`, caches et environnements sont ignorés par `.gitignore`.
  Les archives et rapports locaux ne remplacent pas les sources maintenues.

Pour reconstruire le wheel :

```powershell
python -m pip wheel --no-deps . -w build/dist
```

Utiliser l'isolation de build par défaut : l'essai avec `--no-build-isolation`
a échoué car `bdist_wheel` n'était pas installé dans le Python système.

## Carte du code

| Fichier | Rôle |
| --- | --- |
| `cobol2rust/frontend.py` | Lexer, formats/COPY, AST, expressions, références et instructions |
| `cobol2rust/data_parser.py` | Déclarations, groupes, OCCURS, index et conditions 88 |
| `cobol2rust/layout.py` | Tailles physiques, offsets, dimensions et validation des dispositions |
| `cobol2rust/emitter.py` | Génération Rust, longueurs actives ODO et correspondance des lignes |
| `cobol2rust/runtime.rs` | Valeurs, décimaux exacts, opérations contrôlées et diagnostics |
| `cobol2rust/storage_runtime.rs` | Mémoire partagée, vues, sérialisation, tableaux et initialisation |
| `cobol2rust/file_runtime.rs` | Fichiers LINE SEQUENTIAL et statuts |
| `cobol2rust/cli.py` | Commandes et génération du projet/rapport de conversion |
| `cobol2rust/verification.py` | Oracle indépendant, données d'entrée et comparaison des effets |
| `cobol2rust/toolchain.py` | Détection et environnement des compilateurs |
| `cobol2rust/audit.py`, `binary.py` | Audit statique et inspection binaire |
| `tools/verify.py` | Parcours de tous les exemples et fixtures |
| `tests/test_structures.py` | Contrôles de disposition, ODO, index et erreurs récupérables |

Voir aussi `README.md`, `ARCHITECTURE.md`, `VALIDATION.md` et `tools/README.md`.

## Règles sémantiques à préserver

1. **Mémoire partagée réelle.** Groupes, éléments, REDEFINES et sous-chaînes
   utilisent des vues sur les mêmes octets. Les clés des champs incluent leur
   hiérarchie pour résoudre correctement les noms qualifiés.
2. **MOVE à plusieurs destinations.** L'adresse de la source variable est
   résolue une fois ; son contenu est relu pour chaque destinataire. Une copie
   unique de la valeur serait incorrecte si une destination recouvre la source.
   Cas de régression : `tests/fixtures/aliasing.cob`.
3. **Arithmétique décimale.** Coefficients BigInt et échelles explicites,
   sans flottants. La division reproduit le décalage de 38 chiffres GnuCOBOL 3.2.
   Ne pas simplifier `(1 / 3) * 3` en 1.
4. **SIZE ERROR.** Division par zéro et dépassement de PICTURE sont récupérables
   par le chemin contrôlé. L'arrondi précède le contrôle, et une erreur laisse
   la destination intacte. Un résultat négatif non signé perd son signe dans ce
   chemin, conformément aux essais. Une donnée numérique invalide reste un
   arrêt nommé ; ne pas intercepter globalement les erreurs pour la masquer.
5. **Index.** Initialement 1, ordinaux signés de 32 bits, affichage signé avec
   au moins 9 chiffres. SET UP/DOWN évalue son opérande pour chaque destination :
   si le premier index sert d'opérande, sa nouvelle valeur affecte le second.
6. **ODO terminal.** Allocation maximale, offsets fixes, longueur des groupes
   et bornes de la dimension calculées avec le compteur actif. Le contrôleur
   doit être un entier scalaire externe au groupe variable. Les autres
   dispositions sont refusées, sans approximation au maximum déclaré.
7. **INITIALIZE et ODO.** Le groupe variable entier n'est pris en charge que
   pour le cas vérifié de texte uniforme avec table variable élémentaire.
   Les groupes ODO composés sont refusés : le C de GnuCOBOL 3.2 utilise plusieurs
   stratégies, dont `cob_init_table`, avec des effets observés aux petites
   valeurs du compteur qui restent à modéliser. Une occurrence résolue peut
   être initialisée, par exemple `INITIALIZE row-a(idx)`.
8. **Profil mémoire.** COMP/BINARY big-endian avec tailles 1/2/4/8, COMP-3 avec
   signe final, signe DISPLAY ASCII dans le dernier octet. Un affichage de
   groupe écrit les octets bruts, même non UTF-8. Les index implicites sont
   séparés de la zone de leur table.
9. **Fichiers.** Conserver les espaces, fins de ligne, statuts et effets sur
   les fichiers dans les comparaisons. `COB_LS_FIXED` et `COB_LS_SPLIT` sont les
   seules options runtime configurables du vérificateur ; leurs valeurs sont
   enregistrées dans le rapport.

Les lignes des diagnostics et source maps désignent `expanded.cob`, après
normalisation et expansion des COPY, et non toujours le source d'origine.

## Limites connues et suite conseillée

Les limites détaillées sont dans le README. Restent notamment hors périmètre :
SEARCH, tables à glissement ou stride variable, ODO dans un FD, USAGE INDEX
explicite, COMP-5, images éditées, profils IBM/Micro Focus/EBCDIC, COPY REPLACING,
continuations fixes, fonctions intrinsèques, appels interprogrammes, fichiers
binaires/indexés, SQL et CICS. Sans gestionnaire arithmétique, les dépassements
et signes négatifs non signés provoquent encore un arrêt conservateur de code 70.
Le découpage LINE SEQUENTIAL avec COB_LS_SPLIT actif reste partiellement refusé.

Priorités possibles pour la prochaine étape :

1. Étendre le sous-ensemble source à partir de cas concrets, avec un essai natif
   avant chaque nouvelle règle et des comparaisons stdout/fichiers. SEARCH
   constitue une extension naturelle des tables et index actuels.
2. Reprendre précisément INITIALIZE des groupes ODO composés en examinant le C
   généré et le runtime GnuCOBOL ; conserver le refus tant que l'équivalence
   n'est pas établie.
3. Valider les projets générés sur un environnement Linux réel.
4. Pour le parcours sans sources, choisir d'abord une cible étroite, par exemple
   GnuCOBOL x86 PE. Compiler un petit exemple connu, analyser ses imports/appels
   `cob_*`, étudier son levage avec ARET puis comparer le Rust aux effets du
   binaire original. L'inspecteur actuel ne fournit pas cette chaîne.
5. Ajouter un corpus métier lorsque des programmes et leurs données seront
   disponibles, en épinglant le dialecte et les options du compilateur source.

Mettre à jour ce fichier, la version, la documentation, les rapports et les
paquets lors de la prochaine livraison. Le présent ajout documentaire ne change
pas la version 0.4.0 et ne régénère pas rétroactivement les archives déjà livrées.
