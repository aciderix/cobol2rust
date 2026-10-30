# Cap du projet — à relire au début de chaque session

<!-- cap:début -->
**Cap : convertir le COBOL existant, tel qu'il est écrit et exploité, en Rust
au comportement identique.** Tout le COBOL réel, pas un corpus de test.

**Boussole : l'indicateur de progrès est l'acceptation des corpus réels**
(tableau « Mesure » de CAP.md, `measurements/real-corpora.json`), puis leur
compilation, exécution et comparaison. NIST CCVS85 n'est plus un objectif :
c'est un test de non-régression (451/458 émissions, 413 programmes exécutés
et comparés et 14 autres seulement compilés).

Règles à chaque étape :
1. Choisir le chantier dans le tableau : d'abord l'écart « cobc accepte,
   cobol2rust refuse », par nombre de sources débloquées. Justifier dans le
   journal tout autre choix (profil IBM, CICS/SQL, limites, preuve).
2. Porter fidèlement cobc/libcob 3.2, vérifier sur un essai natif, refuser
   par un diagnostic nommé ce qui n'est pas reproduit. Implémenter la
   construction en entier, pas seulement la forme qu'un corpus exige.
3. Après tout changement du convertisseur : `python3 tools/real_corpora.py
   --cobc --record`, mesure NIST (451/458) et suite Python ; commiter les
   fichiers `measurements/` et CAP.md avec le code.
4. Ajouter une ligne au journal du cap (CAP.md) : ce qui a été levé et le
   chiffre avant/après.
5. Ne jamais présenter un acquis comme universel ; toujours donner le
   dénominateur. Un programme seulement compilé n'est pas « conforme ».
6. Aucun traitement spécial du convertisseur pour faire passer un programme
   ou un corpus. Les règles viennent des déclarations, de l'état
   d'exécution et du profil ; jeux d'entrée et oracles restent dans la
   validation.
<!-- cap:fin -->

## Pourquoi ce document existe

La première partie (jusqu'à la PR `aciderix/cobol2rust#1`) a été pilotée
uniquement par les blocages de la suite NIST CCVS85. Elle a atteint le bilan
natif exact de GnuCOBOL 3.2 sur NIST, mais les corpus réels n'ont jamais été
re-mesurés après le 23 octobre 2026. Mesurés à nouveau le 25 octobre 2026 :
CardDemo (application mainframe AWS) **0/44**, zopeneditor-sample (IBM)
**0/5**, alors que cobc compile une partie de ces sources. Atteindre 100 % de
NIST mesurait surtout la progression vers NIST.

Pièges déjà rencontrés, à ne pas reproduire :

- piloter le développement par un seul corpus de conformité ;
- compter « conformes » des programmes seulement compilés (14 des 427 NIST) ;
- implémenter une fonctionnalité jusqu'à ce que le test passe (Report Writer
  sans ruptures de contrôle, limites de 18 chiffres et 256 caractères) ;
- utiliser une heuristique maison là où cobc a une règle (détection du
  format fixe/libre, résolution des noms de fichiers ASSIGN).

## Feuille de route vers l'universalité

Les étapes ne sont pas strictement séquentielles ; le tableau de mesure
décide de la prochaine.

1. **Écart à cobc sur les corpus réels** (profil GnuCOBOL 3.2 par défaut) :
   lever les refus de sources que cobc accepte.
2. **Preuve sur du code réel** : compiler, exécuter et comparer les
   programmes batch des corpus avec leurs données (niveaux 3 et 4 de
   COVERAGE.md), pas seulement les accepter : `tools/real_corpora.py
   --execute` (stdin vide, fichiers du dossier du programme). Étendre ensuite
   avec de vrais jeux d'entrée (stdin, fichiers, variables DD).
3. **Limites du modèle** : OCCURS et mémoire plus grands, comparaisons à
   `ALL littéral`, PICTURE P au-delà de 18 chiffres
   (38 chiffres, niveau 78, Report Writer avec ruptures et ENTRY sont faits).
4. **Profil des contrôles d'exécution** : sans `-debug`, cobc calcule avec
   les données numériques invalides (COMP-3 ou DISPLAY corrompus) au lieu de
   s'arrêter ; le runtime s'arrête aujourd'hui toujours (arrêt nommé). Porter
   les deux comportements, choisis par le profil (`-debug`, `-fec=…`).
5. **Performance** : le Rust généré est environ 16 fois plus lent que
   GnuCOBOL en release (85 fois en debug) sur une boucle arithmétique
   (CBLC2) ; une migration doit au moins approcher le natif (arithmétique à
   précision fixe quand elle suffit, moins de copies de valeurs).
6. **Profils de compilateur** : IBM Enterprise COBOL (`-std=ibm`, EBCDIC,
   binaire, ddnames), Micro Focus, ACUCOBOL ; un profil = options et
   représentation des données explicites.
7. **Services de plateforme** : adaptateurs EXEC SQL (DB2), EXEC CICS,
   EXEC DLI (IMS), MQ, VSAM, avec un contrat documenté par adaptateur.
8. **Corpus élargis** : testsuite GnuCOBOL mesurée depuis le 25 octobre
   2026 (`tools/extract_testsuite.py` : 1135 sources de 954 tests compilés
   sans option, sur 1344 tests `AT_SETUP`) ; corpus métier de l'utilisateur
   dès qu'il en fournit, avec données et dialecte épinglés.
9. **Parcours sans sources** : binaire GnuCOBOL vers Rust, cible étroite
   d'abord.

## Mesure

Générée par `tools/real_corpora.py --cobc --record` (et `--execute` pour la
partie exécution), ne pas éditer à la main. Les paramètres de chaque corpus
sont figés dans l'outil.

<!-- mesure:début -->
Dernière mesure : 2026-10-30T22:44:23+00:00 (commit `3f70d8d89b`, cobc (GnuCOBOL) 3.2.0). Commande : `python3 tools/real_corpora.py --cobc --record`.

| Corpus | Nature | Sources | cobol2rust accepte | cobc accepte | Écart (cobc oui, nous non) | À examiner (nous oui, cobc non) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| carddemo | application réelle IBM (CICS/VSAM/DB2/IMS/MQ) | 44 | 14 | 14 | 0 | 0 |
| zopeneditor-sample | application exemple IBM | 5 | 5 | 5 | 0 | 0 |
| cobol-programming-course | cours IBM Enterprise COBOL | 32 | 12 | 12 | 0 | 0 |
| beg-cobol-for-programmers | livre, programmes complets | 113 | 64 | 65 | 1 | 0 |
| proleap-cobol-parser | tests de parseur (fragments, dialectes) | 759 | 306 | 311 | 5 | 0 |
| che4z-lsp-for-cobol | tests de serveur de langage IBM | 1505 | 323 | 331 | 8 | 0 |
| gnucobol-testsuite | testsuite GnuCOBOL 3.2 (tests du compilateur) | 1135 | 521 | 879 | 358 | 0 |
| **Total** | | **3593** | **1245** | **1617** | **372** | **0** |

Exécution comparée à cobc (niveaux 3-4) : 2026-10-30T22:44:23+00:00, commit `3f70d8d89b`. Commande : `python3 tools/real_corpora.py --cobc --execute --record`.

| Corpus | Programmes acceptés | Identiques | Divergents | Refusés à la compilation/exécution | Délais/erreurs |
| --- | ---: | ---: | ---: | ---: | ---: |
| carddemo | 8 | 8 | 0 | 0 | 0 |
| zopeneditor-sample | 3 | 3 | 0 | 0 | 0 |
| cobol-programming-course | 12 | 10 | 0 | 0 | 2 |
| beg-cobol-for-programmers | 61 | 53 | 2 | 0 | 6 |

Premiers blocages là où cobc accepte (tous corpus, premier diagnostic par source) :

1. 37 × niveau de donnée attendu
2. 12 × clause SELECT non prise en charge
3. 9 × expression non prise en charge: LINE
4. 8 × PROCEDURE attendu
5. 8 × . attendu
6. 8 × PROGRAM-ID attendu
7. 7 × USAGE/clause non pris en charge: DEPENDING
8. 7 × nom inconnu: ENVIRONMENT; qualifier avec OF/IN si nécessaire
9. 7 × USAGE/clause non pris en charge: IS
10. 6 × CALL BY VALUE : ABI hors des routines système d'octets non prise en charge
<!-- mesure:fin -->

## Journal du cap

Une ligne par étape : date, ce qui a été levé, total accepté avant → après.

- 2026-10-25 — Mise en place du cap, de l'outil `tools/real_corpora.py` et
  de la mesure de référence (avant toute extension du convertisseur) :
  230/2458, cobc 738, écart 518.
- 2026-10-25 — Détection du format portée de cobc (`ppopen_get_file`),
  ASSIGN complet (`assign_clause`, `validate_assign_name`) et résolution des
  noms à l'OPEN (`cob_chk_file_mapping`, `COB_FILE_PATH`) : **230 → 626**
  acceptées, écart 518 → 122, CardDemo 0 → 7/44. NIST inchangé (451/458).
- 2026-10-25 — En-tête IDENTIFICATION et PROCEDURE DIVISION facultatifs,
  INPUT-OUTPUT SECTION vide, niveau 88 de groupe avec figuratives,
  EXIT PERFORM [CYCLE], PERFORM UNTIL EXIT / FOREVER ; rigueur alignée sur
  cobc (lecture en octets, IF/ELSE sans instruction, COMMON hors programme
  contenu, END PROGRAM sensible à la casse) : **626 → 678** acceptées,
  écart 122 → 60, **à examiner 10 → 0** (plus aucune source acceptée que
  cobc refuse).
- 2026-10-25 — COMP-5 et BINARY-CHAR/SHORT/LONG/DOUBLE (binaire réel :
  `cob_decimal_get_binary`, `cob_print_realbin`), registre RETURN-CODE
  (CALL, CANCEL, programmes contenus, code de sortie), RECORDING MODE ignoré
  comme par cobc : **678 → 685** acceptées, écart 60 → 53, CardDemo 8 → 10,
  zopeneditor 0 → 3. Vérification NIST complète : 426/427 sur l'état
  précédent, l'écart NC214M étant l'horloge figée en dur (lue désormais dans
  le journal de référence). Prochains : ENTRY (CardDemo), comparaisons à
  `ALL littéral`, Report Writer avec ruptures (CONTROLS), puis compilation et
  exécution des programmes batch acceptés (niveaux 3-4 sur code réel).
- 2026-10-25 — Exécution comparée sur code réel (`--execute`) : les
  divergences trouvées sont portées de libcob (cob_call_error, cob_fatal_error
  et avertissements implicit CLOSE, NaN de division par zéro, lineseq_read
  avec COB_LS_SPLIT/VALIDATE, bogue IS_BAD_CHAR de lineseq_write), plus les
  littéraux X"…", non ASCII et `&`. Programmes identiques à cobc : CardDemo
  **0 → 8/8**, zopeneditor 3/3, cours 8/11, livre 39 → **41/52** ; NIST
  complet 427/427 (9610 PASS). Acceptation statique inchangée (685/2458).
  Restent : données invalides sans `-debug`, indices hors bornes, programmes
  interactifs sans jeu d'entrée, performance.
- 2026-10-25 — Données numériques invalides sans contrôles d'exécution
  (étape 4 de la feuille de route, justifiée par les divergences du livre et
  du cours) : lecture `COB_D2I`, premiers octets X"FF"/X"00" en lecture
  décimale, routine de comparaison choisie par cobc (`memcmp`,
  `cob_cmp_numdisp`, `cob_cmp_llint`, `cob_numeric_cmp`), copie d'octets de
  `cb_build_move_field`, MOVE HIGH/LOW-VALUE en `memset`, DISPLAY tel que
  stocké, clés de SORT par `cob_numeric_cmp` ; `--runtime-checks` garde
  l'arrêt nommé (`-debug`). Programmes identiques à cobc : cours **8 → 9/11**,
  livre **41 → 45/52**, CardDemo 8/8, zopeneditor 3/3. Acceptation statique
  inchangée (685/2458), NIST 451/458. Restent : indices hors bornes
  (Listing13-6), DISPLAY signé ou binaire invalide, programmes interactifs.
- 2026-10-25 — ENTRY (`emit_entry`, `output_entry_function` : point
  d'entrée trouvé une fois le module chargé), programme à PROCEDURE DIVISION
  USING converti seul comme module (`cobc -m`, exécuté comme par `cobcrun`),
  articles LINKAGE sans adresse (hors USING, non transmis : arrêt nommé au
  premier accès), `LENGTH OF` (`cb_build_length`), DEPENDING ON qualifié :
  **685 → 693** acceptées, écart 53 → 45, **CardDemo 10 → 14/44 et
  zopeneditor 3 → 5/5, tous deux à égalité avec cobc**. NIST complet sur
  l'étape précédente : 427/427, 9610 PASS ; émission 451/458. Outil de
  mesure : horloge figée pour l'exécution (SAM1 divergeait d'une seconde) et
  liste des blocages limitée à l'écart. Prochains : SORT de table
  (`cob_table_sort`), en-tête IDENTIFICATION absent suivi d'AUTHOR, INSPECT
  d'une fonction, Report Writer avec CONTROLS.
- 2026-10-25 — SORT de table (`cob_table_sort` : tri fusion stable de la
  glibc, clé lue à son offset dans son parent comme `cb_emit_sort_init`),
  INSPECT d'un littéral ou d'une fonction (TALLYING), sous-chaîne d'un
  résultat de fonction, IF clos par le terminateur englobant, entrées
  documentaires après PROGRAM-ID sans en-tête, CLASS avec figuratives, FD à
  enregistrement numérique : **693 → 703** acceptées, écart 45 → 35 ; cours
  **12/12** et livre 55 → 62/113 (cobc 65). Exécution identique à cobc : cours
  10/12, livre 45 → **52/59** (Listing13-6 : indice hors bornes ; 6 délais de
  programmes interactifs). Émission NIST 451/458. Restent dans le livre :
  Report Writer avec CONTROLS (18-1, 18-2), CALL d'un nom en casse mixte
  (16-2, qui pourrait désigner un symbole C du processus).
- 2026-10-25 — Lignes IBM `CBL`/`PROCESS` ignorées comme pplex.l, EXIT
  SECTION de la section implicite « MAIN SECTION » de cobc (sortie avant la
  première SECTION), LOCAL-STORAGE SECTION (initialisée à chaque CALL) :
  **703 → 713** acceptées, écart 35 → 25 ; exécution inchangée (CardDemo 8/8,
  zopeneditor 3/3, cours 10/12, livre 52/59). Émission NIST 451/458.
  Prochain chantier de code réel : Report Writer avec CONTROLS (livre
  18-1/18-2, port de reportio.c) ; le reste de l'écart est fait de
  fragments de tests de parseur (XML, SCREEN, COMMUNICATION, dialectes).
- 2026-10-25 — Report Writer avec ruptures de contrôle (port de
  `cob_report_generate`/`cob_report_terminate` : CONTROLS [FINAL], CH/CF,
  pieds imprimés avec la valeur précédente du contrôle, SUM et
  `build_sum_counter`, report des compteurs, NEXT GROUP, GROUP INDICATE,
  VALUE ALL) : **713 → 715** acceptées, livre **64/65** (cobc 65 ; reste
  16-2). Fixture `report_controls` identique à cobc ; NIST RW 6/6 conformes
  (40 PASS), émission 451/458. Exécution du livre : 52/61 identiques ; 18-1 et
  18-2 sont identiques sur plus de 1200 lignes puis s'arrêtent, comme 13-6,
  sur un indice hors bornes que GnuCOBOL lit sans contrôle (la dernière ligne
  sans fin de ligne est relue par libcob, d'où StateName(70)).
- 2026-10-25 — READ KEY d'un article où ne commence aucune clé (statut 23 de
  `cob_findkey_attr`, la variante CardDemo CBTRN01C de che4z), 01 homonymes
  (simple avertissement de cobc), paragraphes de CONFIGURATION dans tout
  ordre ou vides, point facultatif avant le SELECT suivant (`missing-period`),
  `STOP RUN RETURNING/GIVING/WITH STATUS`, littéraux `Z"…"` : **715 → 724**
  acceptées, écart 23 → 14 (restent : XML, SCREEN, COMMUNICATION hors
  cobol85, `$SET`, CALL d'un nom en casse mixte ou d'un numérique). Exécution
  inchangée. Émission NIST 451/458.
- 2026-10-25 — Nouveau corpus `gnucobol-testsuite` : les programmes des tests
  de cobc 3.2 compilés sans option (`tools/extract_testsuite.py`, dérivé de
  l'archive GnuCOBOL épinglée). Mesure initiale 256/1135, cobc 879, et 13
  sources acceptées que cobc refuse, toutes corrigées : bornes constantes de
  référence et d'indice, VALUE signé sur non signé, REDEFINES d'une
  redéfinition, INDEXED avant ASCENDING, WHEN vide avant WHEN OTHER, GO TO
  vers/depuis DECLARATIVES (cobol85), noms de programme invalides
  (`cobc_check_valid_name`), mot commençant par `_`, littéral de plus de 8191
  caractères (160 en cobol85), mot quelconque après `STOP RUN` pris comme
  statut. La règle du WHEN vide a révélé un bogue ancien : `WHEN 'A' WHEN 'B'
  instr` donnait une branche vide au premier WHEN quand le second commençait
  par un littéral (corrigé, fixture `evaluate_literal_when` comparée à cobc).
  Résultat : **970/3593** acceptées, cobc 1617, à examiner 13 → 0 ; six
  corpus d'origine inchangés à 724/2458 (écart 14) ; écart de la testsuite
  633. Exécution inchangée. Émission NIST 451/458.
- 2026-10-26 — Premiers blocages de la testsuite : clauses DISPLAY dans tout
  ordre et `NO ADVANCING` sans `WITH` (plusieurs listes par instruction,
  `display_atom` ; opérandes `x` sans arithmétique, littéral signé affiché
  avec son signe), DISPLAY et STRING de fonctions alphanumériques, FUNCTION
  TRIM [LEADING|TRAILING] (`cob_intr_trim`), constantes `78` et `01
  CONSTANT` (substitution du scanner `cb_add_78`, `cb_evaluate_expr`, `PIC
  X(nom)`), CANCEL d'un programme actif (`P_cancel` : erreur libcob,
  code 1). Testsuite **246 → 306** acceptées, total **970 → 1030**/3593
  (cobc 1617, à examiner 0) ; six corpus d'origine inchangés (724). Des 60
  sources débloquées, exécutées face à cobc hors mesure : 49 identiques, 11
  arrêts nommés (sous-chaîne hors bornes lue par cobc au-delà du champ,
  troncature native, CALL non converti), aucune sortie divergente après
  correction de CANCEL. Exécution des corpus inchangée ; NIST 451/458,
  échantillon de 8 programmes (EVALUATE, CANCEL) conforme 173/173 PASS.
- 2026-10-26 — Paramètre de mesure changé (mesures précédentes non
  strictement comparables) : la mesure statique cherche désormais les
  programmes appelés dans le dossier de l'appelant, comme l'exécution le
  faisait déjà ; un CALL par identifiant d'un appelé est pris en charge et
  une source trouvée par balayage qui ne se convertit pas seule est écartée
  au lieu de faire refuser l'unité. Arguments CALL littéraux et figuratives
  (BY CONTENT copie, BY REFERENCE constante en lecture seule), `OMITTED`,
  erreurs libcob de CALL récursif et de CANCEL actif. Résultat : **1030 →
  1045**/3593 (testsuite 306 → 322, proleap 306 → 305 : IC114A appelle
  IC115A, que cobc refuse aussi, et n'est plus accepté seul). Des 12
  sources débloquées exécutées face à cobc : 9 identiques, 3 de mêmes
  sortie et code d'erreur (pile d'appels de libcob sur stderr non
  reproduite). Exécution des corpus inchangée ; NIST 451/458, les 24
  programmes IC (CALL/CANCEL) conformes, 245 PASS, 0 FAIL.
- 2026-10-26 — Limites et formes de la testsuite : champs DISPLAY et COMP-3
  jusqu'à 38 chiffres (`COB_MAX_DIGITS`, BINARY/COMP-5 refusés au-delà de 18
  avec l'erreur de cobc), `ROUNDED MODE` (huit modes de
  `cob_decimal_do_round`), `DELETE FILE` (`cob_delete_file`, sans
  DECLARATIVES), types C `[UN]SIGNED-SHORT/INT/LONG` et `BINARY-C-LONG`,
  alias réservés de default.conf (`BINARY-INT`, `ORGANISATION`,
  `INITIALISE`…), `REPOSITORY` des fonctions intrinsèques. Testsuite **322 →
  363**, total **1045 → 1086**/3593 (cobc 1617, à examiner 0). Des 41
  sources débloquées, exécutées face à cobc : 39 identiques, 2 arrêts
  nommés (indice et sous-chaîne hors bornes lus par cobc sans contrôle).
  Exécution des corpus inchangée ; NIST 451/458.
- 2026-10-26 — `COMP-6` (packed sans demi-octet de signe,
  `COB_FLAG_NO_SIGN_NIBBLE` ; signé, il devient COMP-3 comme pour cobc) et
  test de classe NUMERIC d'un packed comme `cob_is_numeric` (le demi-octet de
  remplissage n'est pas contrôlé à part, COMP-3 compris). Testsuite **363 →
  370**, total **1086 → 1093**/3593. Des 7 sources débloquées, exécutées
  face à cobc : 5 identiques, 2 arrêts nommés (MOVE binaire remplissant le
  demi-octet de remplissage). Exécution des corpus inchangée ; NIST 451/458.
- 2026-10-26 — Compilation conditionnelle de pplex (`>>DEFINE`, `>>IF`/`>>ELIF`
  avec `DEFINED` ou comparaison, `>>ELSE`, `>>END-IF`, DEFINE standard
  `CHARSET`/`ENDIAN`/`SIGN`/`PERFORM-TYPE`, `>>DISPLAY` sans effet à
  l'exécution). Testsuite **370 → 384**, total **1093 → 1107**/3593. Les 14
  sources débloquées, exécutées face à cobc, ont d'abord révélé deux écarts
  sémantiques, corrigés : `VALUE -0` d'un DISPLAY signé stocke un zéro
  négatif (`p`), et ADD/SUBTRACT d'un opérande entier passe par
  `cob_add_int` pour tout receveur DISPLAY, mis à l'échelle ou COMP-6 (un
  opérande nul laisse le receveur intact) ; ensuite 14/14 identiques.
  Exécution des corpus inchangée ; NIST 451/458 et 30 programmes NC
  d'ADD/SUBTRACT conformes (1755 PASS, 0 FAIL).
- 2026-10-26 — PICTURE P (mise à l'échelle) en BINARY, COMP-3 et COMP-5, plus
  seulement en DISPLAY (fixture `picture_p_usages` identique à cobc).
  Testsuite **384 → 394**, total **1107 → 1117**/3593. Des 10 sources
  débloquées, exécutées face à cobc : 9 identiques, 1 arrêt nommé (MOVE
  binaire remplissant le demi-octet de remplissage). NIST 451/458.
- 2026-10-26 — Directives MF (`$` en zone d'indicateur ou en tête de ligne) :
  `$SET` (options sans effet ignorées comme les `#OPTION` de cobc, options
  actives refusées), `$IF`/`$ELSE`/`$END`, `$DISPLAY` (mots et littéraux
  seulement, sinon l'erreur de syntaxe de cobc). Total **1117 → 1122**/3593
  (proleap 305 → 306, testsuite 394 → 398), à examiner 0. Des 5 sources
  débloquées, exécutées face à cobc : 3 identiques, 2 arrêts nommés (indice
  hors bornes lu par cobc sans contrôle). NIST 451/458.
- 2026-10-26 — En-têtes de programme : `PROCEDURE DIVISION CHAINING`
  (`cob_chain_setup`, vérifié à la main avec arguments : octets identiques ;
  CALL d'un programme CHAINING = erreur libcob du test officiel),
  `PROGRAM-ID nom AS "externe"`, `RETURNING OMITTED` (principal en module),
  programme suivant sans IDENTIFICATION DIVISION ; `ASSIGN LINE ADVANCING
  FILE` (`flag_line_adv` : LINE SEQUENTIAL sans validation, WRITE sans
  ADVANCING = AFTER 1). Testsuite **398 → 410**, total **1122 → 1134**/3593.
  Des 12 sources débloquées, exécutées face à cobc : 9 identiques, 2 mêmes
  erreur et code (fichier d'entrée absent), 1 où cobc meurt de SIGSEGV hors
  de son test (le test officiel attend l'erreur CHAINING reproduite). NIST
  451/458.
- 2026-10-26 — Troncature d'un receveur packed sans SIZE ERROR
  (`cob_decimal_get_packed` : chiffres de poids fort perdus, signe conservé,
  zéro négatif ; la retenue de `cob_add_packed_int` dans le demi-octet de
  remplissage reste un arrêt nommé), modification de référence de tout
  article (octets bruts, COMP-3/COMP/COMP-5/INDEX compris), affichage d'un
  binaire au-delà de sa PICTURE (chiffres de poids faible comme
  `pretty_display_numeric`), `88 ... FALSE [IS]`, FUNCTION HEX-OF et
  HEX-TO-CHAR. Testsuite **410 → 418**, total **1134 → 1142**/3593. Des 8
  sources débloquées (dont 6 tests de 500 champs packed), exécutées face à
  cobc : 7 identiques, 1 arrêt nommé. NIST 451/458.
- 2026-10-26 — `COPY`/`REPLACE ... REPLACING LEADING|TRAILING` (remplacement
  partiel d'un mot, `is_leading_or_trailing` et `ppecho_leading_or_trailing`
  de pplex ; cible littérale plus longue exigée, cible de plusieurs mots
  refusée comme ppparse). Testsuite **418 → 423**, total **1142 → 1147**/3593,
  à examiner 0. Des 5 sources débloquées, exécutées face à cobc : 5
  identiques. Exécution des corpus inchangée. NIST 451/458.
- 2026-10-26 — Fonctions intrinsèques : DISPLAY du champ résultat numérique
  (`cob_alloc_field` avec l'estimation `mpz_sizeinbase` de GMP, copie de
  l'argument de MAX/MIN/MEDIAN/MEAN et d'ABS, entier non signé de 9
  chiffres, DISPLAY de DATE-OF-INTEGER) ; ABS, FRACTION-PART, EXP10,
  CONCATENATE/CONCAT, SUBSTITUTE(-CASE), STORED-CHAR-LENGTH,
  HIGHEST/LOWEST-ALGEBRAIC, TEST-DATE-YYYYMMDD, TEST-DAY-YYYYDDD,
  YEAR-TO-YYYY, DATE-TO-YYYYMMDD, DAY-TO-YYYYDDD ; littéral vide = une
  espace (refusé sous cobol85). Testsuite **423 → 453**, total
  **1147 → 1177**/3593, à examiner 0. Des 30 sources débloquées, exécutées
  face à cobc : 30 identiques. Exécution des corpus inchangée. NIST 451/458.
- 2026-10-26 — Fonctions ISO 8601 : FORMATTED-DATE, FORMATTED-TIME,
  FORMATTED-DATETIME (offset ou SYSTEM-OFFSET), FORMATTED-CURRENT-DATE,
  TEST-FORMATTED-DATETIME, INTEGER-OF-FORMATTED-DATE,
  SECONDS-FROM-FORMATTED-TIME (intrinsic.c, `valid_const_date_time_args`
  de tree.c pour un format littéral). Testsuite **453 → 467**, total
  **1177 → 1191**/3593, à examiner 0. Des 14 sources débloquées, exécutées
  face à cobc : 14 identiques (2 autres tests ISO 8601 restent bloqués par
  EXCEPTION-STATUS). Exécution des corpus inchangée. NIST 451/458.
- 2026-10-28 — Reprise sur les deux branches Claude déjà intégrées à main
  (`ab7c864`), sans réappliquer l'ancien chantier DATA RECORD. Choix d'un
  écart intrinsèque mesuré et isolable, avant les chantiers plus volumineux
  SCREEN/POINTER/CALL BY VALUE : NUMVAL-F et TEST-NUMVAL/TEST-NUMVAL-C/
  TEST-NUMVAL-F, port de `cob_intr_numval_f` et `cob_check_numval*`.
  Testsuite **467 → 471**, total **1191 → 1195**/3593, écart **426 → 422**,
  à examiner 0. Les quatre sources débloquées s'exécutent à l'identique de
  cobc ; deux profils indépendants ajoutent 412 résultats comparés.
  Conversion permissive et validation stricte restent distinctes ; provenance
  lexicale du signe conservée pour ne pas confondre `-1` et `-(1)`.
  Le stockage des résultats numériques calculés reste un refus nommé ; les
  limites générales du runtime restent 1024 décimales/4096 chiffres et les
  registres EXCEPTION-* non modélisés. NIST statique inchangé : 451/458.
  Suite Python : 431 découverts, 430 validés, un ignoré ; les deux contrôles
  BDB initialement bloqués par les dépendances cloud passent après préparation
  de leurs en-têtes et réexécution, sans changement du convertisseur.
- 2026-10-29 — Paramètres `PIC X ANY LENGTH` : choix d'une extension
  générale et isolable du descripteur LINKAGE avant les plus grands
  chantiers SCREEN/POINTER/CALL BY VALUE. Taille reçue, refmod, MOVE,
  conditions 88, omission, CANCEL/INITIAL et ordre ENTRY (bogue natif #902)
  portés de cobc ; limites mémoire contrôlées au premier accès. ANY NUMERIC,
  GLOBAL et autres formats restent des refus nommés. Testsuite
  **471 → 479**, total **1195 → 1203/3593**, écart **422 → 414**,
  à examiner 0. NIST statique **451/458**, sans erreur interne. Exécution
  globale renouvelée : **70/84 identiques**, six divergences et huit délais.
  Les trois exemples zopeneditor plantent dans le natif à la fermeture
  implicite après GOBACK (descripteur ASSIGN périmé) ; sorties et fichiers
  identiques, codes -11/16 : ils restent comptés divergents.
  Suite Python complète : **448 découverts, 447 validés, un PE Windows ignoré**,
  aucun échec ni erreur ; 17 nouveaux tests ANY LENGTH réussis.
  Des huit sources débloquées, quatre programmes s'exécutent à l'identique
  de cobc, couvrant deux callees ; deux modules syntaxiques sont seulement
  compilés des deux côtés.
- 2026-10-29 — Fidélité d'exécution : chantier choisi dans les écarts réels
  et les entrées non couvertes (étape 2 de la feuille de route). Capacité
  ODO distincte de la longueur logique selon EC-BOUND ; SORT garde son
  nombre courant et les accès hors capacité restent nommés. Les quatre
  conversions calendaires renvoient zéro hors domaine, avec les largeurs
  natives et les limites numériques actuelles. Aucune règle par nom de
  programme. Acceptation **1203 → 1203/3593**, écart 414, à examiner 0 ;
  NIST statique **451/458**, zéro erreur interne. Exécution de référence
  **70 → 71/84 identiques**, livre **52 → 53/61** : Listing13-6 devient
  identique ; cinq divergences et huit délais restent comptés.
  Nouveau moteur générique de scénarios déclarés : **11/11 comparaisons
  identiques sur cinq programmes interactifs**, dans un rapport distinct
  du protocole à stdin vide. Les sources, stdin, dossiers et oracles sont
  épinglés ; une modification des entrées invalide la preuve. Deux tests
  calendaires comparent 119 résultats ; quatre tests ODO et six du moteur
  de scénarios complètent la couverture ciblée.
  Suite Python complète : **460 découverts, 459 validés, un PE Windows ignoré**,
  sans échec ni erreur.
- 2026-10-29 — Capture des SOURCE de rapports : chantier de fidélité
  d'exécution choisi après l'audit des écarts du livre, avant les extensions
  SCREEN/POINTER plus volumineuses. Un contre-exemple valide déjà accepté
  divergeait à une rupture de contrôle ; il produit maintenant les mêmes
  38 octets que le natif. Temporaires typés de `cb_field_dup`, ordre des deux
  passes de préparation et état persistant de `cb_emit_report_moves` portés,
  avec repli constant des positions SOURCE. Les sources simples restent
  lues à l'impression ; les formes non reproduites sont refusées par nom.
  Aucun traitement par nom de programme. Acceptation **1203 → 1203/3593**,
  écart 414, à examiner 0 ; NIST statique **451/458**, zéro erreur interne.
  Exécution globale renouvelée : **71/84 identiques**, cinq divergences et
  huit délais inchangés ; ni les sources du corpus ni les gardes d'accès
  hors capacité physique ne sont modifiées. Dix-sept nouveaux tests,
  dont 23 positions dans les deux profils ; avec les tests Report Writer
  existants, **26/26 réussis**.
  Suite complète : **477 découverts, 476 validés, un PE Windows ignoré**,
  aucun échec ni erreur ; scénarios d'entrée **11/11 identiques**, avec
  leur dénominateur distinct. Les limites restantes sont documentées dans
  VALIDATION.md et HANDOFF.md.
- 2026-10-30 — Routines système d'octets : choix de dix blocages BY VALUE
  isolables avant SCREEN (backend et preuve terminale absents) et POINTER
  (modèle d'adresses à porter). Port des huit CBL logiques et des routines
  de casse avec leurs alias, en conservant les alias mémoire, les lectures
  scalaires et casts natifs du profil Linux x86_64. Les autres ABI, CALL
  RETURNING et descriptions de résultats non reproduites restent des refus
  nommés. Un BY VALUE alphanumérique devient BY CONTENT, comme dans cobc.
  Aucun cas spécial par programme. Testsuite **479 → 490**, total
  **1203 → 1214/3593**, écart **414 → 403**, à examiner zéro. Dix programmes
  de routines exécutés à l'identique avec codes zéro ; le onzième cas
  syntaxique s'arrête des deux côtés sur PROG2 absent (codes 1/1), sans être
  compté comme exécution réussie. Exécution globale renouvelée : **71/84**,
  cinq divergences et huit délais inchangés ; NIST statique **451/458**,
  zéro erreur interne. Quatorze nouveaux tests ; ciblage **22/22**, dont
  3072 octets et 29 longueurs scalaires dans les deux profils. Les scénarios
  d'entrée restent **11/11**, avec leur propre dénominateur.
  Suite complète : **491 découverts, 490 validés, un PE Windows ignoré**,
  sans échec ni erreur ; preuves et empreintes dans
  `build/system-calls-validation-20261030.json`.
- 2026-10-30 — Modèle d'adresses : USAGE POINTER, BASED, ADDRESS OF, SET
  ADDRESS/UP/DOWN, ALLOCATE et FREE, deuxième groupe des « Premiers
  blocages » après SCREEN (qui exige un backend terminal vérifiable). Une
  adresse native devient une région (chaque 01/77, zone ALLOCATE, bloc
  EXTERNAL ou copie BY CONTENT) et un décalage dans les 8 octets du
  POINTER ; tout accès hors région est un arrêt nommé. Ports de
  `cob_allocate` (calloc ou malloc ; une zone malloc est suivie octet par
  octet et lire un octet jamais écrit est un arrêt nommé), `cob_free_alloc`,
  `cb_check_set_to`, de la comparaison `(int)(a-b)`, de l'adresse statique
  d'un article LINKAGE hors USING (persistante à travers CALL et CANCEL), de
  la libération des BASED au CANCEL et du statut 31 d'un ASSIGN sans
  adresse, avec le nom `field with NULL address` de `cob_field_to_string`.
  Refus nommés : DISPLAY d'une adresse non NULL (ASLR), ordre de deux
  régions, arithmétique hors SET, BY VALUE d'un pointeur (tronqué en int par
  cobc 3.2), PROGRAM-POINTER, VALUE en LINKAGE hors BASED. Aucun cas spécial
  par programme. Testsuite **490 → 501/1135**, total **1214 → 1225/3593**,
  écart **403 → 392**, à examiner zéro. Sur les onze sources débloquées,
  sept s'exécutent à l'identique avec codes zéro ; run_file-020/prog
  s'arrête des deux côtés sur le statut 31 avec le même message (codes 1/1,
  non compté comme réussite) ; data_pointer-001 s'arrête nommément sur le
  DISPLAY d'adresse ; run_misc-115/prog et prog2 plantent en natif (SIGSEGV)
  là où Rust s'arrête nommément. Exécution globale renouvelée : **74/84
  identiques**, deux divergences et huit délais ; zopeneditor passe de 0/3 à
  3/3 parce que le plantage natif -11 à la fermeture implicite n'est plus
  observé (six essais natifs à 16), sans changement de ces programmes côté
  Rust ; il peut réapparaître. NIST statique **451/458**. Sept nouveaux
  tests (quatorze refus, deux fixtures identiques au natif, message du
  statut 31, huit arrêts nommés). Suite complète : **498 découverts, 497
  validés, un PE Windows ignoré**, sans échec ni erreur.
- 2026-10-30 — Dernière exception : FUNCTION EXCEPTION-STATUS/LOCATION/
  STATEMENT/FILE et SET LAST EXCEPTION TO OFF, troisième ligne des premiers
  blocages (9 + 6 sources de la même famille). Port de `cob_set_exception`
  et de la table `exception.def` (exception-io.def à sa place, nom par
  `cob_get_last_exception_name`), de `save_status` (classe du statut,
  EC-I-O-EOP, `cob_error_file` à chaque opération), de `cob_decimal_div`,
  des stockages de `cob_decimal_get_display` (receveurs DISPLAY ou édités,
  SIZE ERROR, TALLYING, VARYING), de PROHIBITED, de strings.c, de
  `cob_allocate`/`cob_free_alloc`, de `cob_accept` en fin d'entrée, de
  `cob_mod_or_rem` (zéro et EC-ARGUMENT-FUNCTION au lieu d'un arrêt), des
  fonctions ISO 8601, du CALL introuvable et de `cob_module_global_enter` :
  un appel récursif sous ON EXCEPTION rend -1 avec
  EC-PROGRAM-RECURSIVE-CALL au lieu de l'arrêt fatal. Audit par fermeture
  des appels d'intrinsic.c : 44 fonctions sans exception, les autres non
  auditées rendent la dernière exception inconnue, comme l'exponentiation,
  les receveurs binaires ou packés, SORT/MERGE, Report Writer, CANCEL ou
  fin d'un programme INITIAL avec fichiers ouverts, USE GLOBAL ; la lire
  alors est un arrêt nommé. Suivi généré seulement pour une unité qui lit
  la dernière exception. Sous `-debug`, EXCEPTION-LOCATION/STATEMENT
  restent refusées (section, paragraphe et sous-clauses de cobc). Un
  littéral entier en valeur d'une fonction ISO 8601 donne ses chiffres
  (`cb_build_numeric_literal`). Aucun cas spécial par programme.
  Testsuite **501 → 516/1135**, total **1225 → 1240/3593**, écart
  **392 → 377**, à examiner zéro. Sur les quinze sources débloquées, douze
  s'exécutent à l'identique avec codes zéro ; run_misc-040 caller et callee
  sont identiques et finissent par le STOP RUN RETURNING 1 de leur
  gestionnaire (codes 1/1, non comptés comme réussites) ; callee2 exécuté
  seul s'arrête des deux côtés sur la récursion fatale, seule la pile
  « Last statement of … Started by <chemin> » de libcob diffère. Exécution
  globale renouvelée : **74/84**, deux divergences et huit délais,
  inchangés. NIST statique **451/458**. Six nouveaux tests, deux fixtures
  identiques au natif. Suite complète : **504 découverts, 503 validés, un
  PE Windows ignoré**, sans échec ni erreur.
- 2026-10-30 — START complet et READ PREVIOUS : deuxième groupe hors
  SCREEN après les verrous SELECT (essais entre processus), dont les cinq
  sources START visent une construction de fichiers réelle. Ports de
  `start_op` (=, >, >=, <, <= et leurs formes NOT ; NOT = refusé), FIRST,
  LAST, `WITH SIZE/LENGTH` (INDEXED, statut 23 hors de 1..taille de la
  clé), `relative_start` et du chemin BDB d'`indexed_start_internal`
  (DB_PREV, DB_LAST, DB_NEXT_NODUP des doublons), puis de READ PREVIOUS
  (`cob_read_next`, `relative_read_next` avec ses reculs de deux
  emplacements qui sautent des enregistrements en natif, `indexed_read_next`
  DB_PREV/DB_LAST et la fin immédiate après OPEN). Aucun cas spécial par
  programme. Testsuite **516 → 521/1135**, total **1240 → 1245/3593**,
  écart **377 → 372**, à examiner zéro. Les cinq sources débloquées
  (run_file-030/031/032/073/074) s'exécutent à l'identique avec codes zéro.
  Exécution globale renouvelée : **74/84**, deux divergences et huit délais,
  inchangés. NIST statique **451/458**. Trois nouveaux tests, dont la
  fixture `start_previous.cob` (statuts, enregistrements et fichiers
  identiques au natif). Deux cas du test RELATIVE qui attendaient le refus
  de START < et READ PREVIOUS deviennent NOT = et WITH LENGTH. Suite
  complète : **507 découverts, 506 validés, un PE Windows ignoré**.
