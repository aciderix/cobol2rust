# Cap du projet — à relire au début de chaque session

<!-- cap:début -->
**Cap : convertir le COBOL existant, tel qu'il est écrit et exploité, en Rust
au comportement identique.** Tout le COBOL réel, pas un corpus de test.

**Boussole : l'indicateur de progrès est l'acceptation des corpus réels**
(tableau « Mesure » de CAP.md, `measurements/real-corpora.json`), puis leur
compilation, exécution et comparaison. NIST CCVS85 n'est plus un objectif :
c'est un test de non-régression (451/458 émissions, 427/427 conformes).

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
3. **Limites du modèle** : 38 chiffres comme cobc (aujourd'hui 18), champs
   texte au-delà de 256 caractères, OCCURS et mémoire plus grands,
   niveau 78, Report Writer avec ruptures de contrôle, ENTRY, comparaisons à
   `ALL littéral`.
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
Dernière mesure : 2026-10-25T23:50:11+00:00 (commit `783812c95f`, cobc (GnuCOBOL) 3.2.0). Commande : `python3 tools/real_corpora.py --cobc --record`.

| Corpus | Nature | Sources | cobol2rust accepte | cobc accepte | Écart (cobc oui, nous non) | À examiner (nous oui, cobc non) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| carddemo | application réelle IBM (CICS/VSAM/DB2/IMS/MQ) | 44 | 14 | 14 | 0 | 0 |
| zopeneditor-sample | application exemple IBM | 5 | 5 | 5 | 0 | 0 |
| cobol-programming-course | cours IBM Enterprise COBOL | 32 | 12 | 12 | 0 | 0 |
| beg-cobol-for-programmers | livre, programmes complets | 113 | 64 | 65 | 1 | 0 |
| proleap-cobol-parser | tests de parseur (fragments, dialectes) | 759 | 306 | 311 | 5 | 0 |
| che4z-lsp-for-cobol | tests de serveur de langage IBM | 1505 | 323 | 331 | 8 | 0 |
| gnucobol-testsuite | testsuite GnuCOBOL 3.2 (tests du compilateur) | 1135 | 306 | 879 | 573 | 0 |
| **Total** | | **3593** | **1030** | **1617** | **587** | **0** |

Exécution comparée à cobc (niveaux 3-4) : 2026-10-25T23:50:11+00:00, commit `783812c95f`. Commande : `python3 tools/real_corpora.py --cobc --execute --record`.

| Corpus | Programmes acceptés | Identiques | Divergents | Refusés à la compilation/exécution | Délais/erreurs |
| --- | ---: | ---: | ---: | ---: | ---: |
| carddemo | 8 | 8 | 0 | 0 | 0 |
| zopeneditor-sample | 3 | 3 | 0 | 0 | 0 |
| cobol-programming-course | 12 | 10 | 0 | 0 | 2 |
| beg-cobol-for-programmers | 61 | 52 | 3 | 0 | 6 |

Premiers blocages là où cobc accepte (tous corpus, premier diagnostic par source) :

1. 37 × niveau de donnée attendu
2. 22 × PIC numérique limité à 18 chiffres
3. 18 × . attendu
4. 17 × CALL USING limité aux identifiants BY REFERENCE/CONTENT
5. 15 × USAGE/clause non pris en charge: POINTER
6. 14 × clause SELECT non prise en charge
7. 13 × paragraphe CONFIGURATION non pris en charge
8. 13 × CALL callee: programme non converti ou routine système non pris en charge
9. 12 × CALL USING limité à BY REFERENCE et BY CONTENT
10. 11 × fichier non déclaré: FILE
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
