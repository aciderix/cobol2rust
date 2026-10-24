# Validation — 22 octobre 2026

## Fichiers, RENAMES, exponentiation — 24 octobre 2026

- **305 tests découverts : 304 réussis, un test PE Windows ignoré.**
- **91/91 comparaisons locales conformes** ; nouvelles fixtures `renames.cob`,
  `exponentiation.cob`, `figurative_numeric.cob`, `negative_zero.cob`.
- NIST : **251/458** ; **249/249 programmes acceptés conformes** (5841 PASS,
  0 FAIL) : `build/nist-verify-files-renames.json`.
- Sonde native : avec un exposant littéral négatif, `cob_decimal_pow` écrase la
  constante décimale partagée (`3 ** -1` puis `3 ** -1` donne 0,3333 puis 27) ;
  ce cas est refusé.

## Conditions cobc, STRING/UNSTRING — 24 octobre 2026

- **304 tests découverts : 303 réussis, un test PE Windows ignoré.**
- **87/87 comparaisons locales conformes** ; nouvelles fixtures
  `abbreviated_conditions.cob` (23 formes de conditions), `string_unstring.cob`.
- NIST : **233/458** ; **231/231 programmes acceptés conformes** (5497 PASS,
  0 FAIL) : `build/nist-verify-conditions.json` (230, dont NC211A rejeté par
  cobc car `NOTHING` est réservé, désormais refusé aussi) et
  `build/nist-verify-string.json` (NC217A, NC218A).

## SEARCH, USAGE INDEX, INSPECT, EVALUATE — 24 octobre 2026

- **301 tests découverts : 300 réussis, un test PE Windows ignoré.**
- **85/85 comparaisons locales conformes** ; nouvelles fixtures
  `usage_index.cob`, `search_tables.cob`, `inspect_statement.cob`,
  `inspect_markers.cob` (marqueurs statiques de libcob entre instructions),
  `evaluate_forms.cob`, `nested_conditions.cob`.
- NIST : **229/458** ; **227/227 programmes acceptés conformes** (5269 PASS,
  0 FAIL) : `build/nist-verify-inspect.json` (224) et
  `build/nist-verify-subscripts.json`.
- Défaut corrigé : deux `WHEN` consécutifs ne partageaient pas les
  instructions suivantes (le premier ne faisait rien), écart silencieux
  détecté par une sonde native.

## SPECIAL-NAMES et ACCEPT — 24 octobre 2026

- **292 tests découverts : 291 réussis, un test PE Windows ignoré.**
- **78/78 comparaisons locales conformes** ; nouvelles fixtures
  `special_names.cob` (stdout et stderr identiques), `accept_input.cob`.
- NIST : **205/458** ; **203/203 programmes acceptés conformes** (4650 PASS).

## Segments, CLOSE REEL/NO REWIND — 24 octobre 2026

- **290 tests découverts : 289 réussis, un test PE Windows ignoré.**
- **77/77 comparaisons locales conformes** ; nouvelle fixture `close_reel.cob`.
- NIST : **198/458** ; **196/196 programmes acceptés conformes** (4566 PASS).

## SORT et MERGE — 24 octobre 2026

- **289 tests découverts : 288 réussis, un test PE Windows ignoré.**
- **76/76 comparaisons locales conformes** ; nouvelle fixture `sort_merge.cob`
  (USING/GIVING, procédures, MERGE ; octets des fichiers GIVING identiques).
- NIST : **182/458** ; **180/180 programmes acceptés conformes** (4474 PASS).

## Formes arithmétiques, HIGH/LOW-VALUE — 23 octobre 2026

- **286 tests découverts : 285 réussis, un test PE Windows ignoré.**
- **75/75 comparaisons locales conformes** ; nouvelles fixtures
  `divide_remainder.cob`, `high_low_values.cob`, `relative_start_ge.cob`.
- NIST : **166/458** ; **164/164 programmes acceptés conformes** (4296 PASS).

## SIGN, SYNCHRONIZED, clauses de données — 23 octobre 2026

- **283 tests découverts : 282 réussis, un test PE Windows ignoré.**
- **72/72 comparaisons locales conformes** ; nouvelles fixtures
  `sign_clause.cob`, `condition_figuratives.cob`.
- NIST : **153/458** ; **151/151 programmes acceptés conformes** (3656 PASS).

## Édition, pliage des comparaisons, JUSTIFIED — 23 octobre 2026

- **278 tests découverts : 277 réussis, un test PE Windows ignoré.**
- **69/69 comparaisons locales conformes** ; nouvelles fixtures
  `numeric_editing.cob` (23 images × 8 valeurs), `alnum_editing.cob`,
  `comparison_folding.cob`, `edited_size_error.cob`, `value_all_justified.cob`.
- NIST : **141/458** ; **139/139 programmes acceptés conformes** (3072 PASS).

## NEXT SENTENCE, programmes frères, PICTURE P — 23 octobre 2026

- **269 tests découverts : 268 réussis, un test PE Windows ignoré.**
- **65/65 comparaisons locales conformes** ; nouvelles fixtures
  `next_sentence.cob`, `sibling_programs.cob`, `p_scaling.cob`.
- NIST : **131/458** ; **129/129 programmes acceptés conformes** (2180 PASS).

## CALL et programmes liés — 23 octobre 2026

- **261 tests découverts : 260 réussis, un test PE Windows ignoré.**
- **62/62 comparaisons locales conformes** ; nouvelle fixture `call_main.cob`
  (+ `calls/`), sous-programmes compilés en modules `cobc -m` côté natif.
- NIST : **126/458** ; revérification de tous les programmes acceptés :
  **124/124 conformes** (2077 PASS, 0 FAIL) ; 9 nouveaux programmes IC.

## Enregistrements variables — 23 octobre 2026

- **255 tests découverts : 254 réussis, un test PE Windows ignoré.**
- **61/61 comparaisons locales conformes** (nouvelles fixtures
  `variable_records`, `perform_after`, `lexical_forms`, `set_all`).
- NIST : **115/458** ; 12 + 7 + 1 nouvelles sources conformes.

## RELATIVE — 23 octobre 2026

- **243 tests découverts : 242 réussis, un test PE Windows ignoré.**
- **57/57 comparaisons locales conformes**, dont `relative.cob` : statuts,
  clés, trous, START et octets d'emplacements identiques au natif.
- NIST : **95/458** ; 29 nouvelles comparaisons conformes.

## OPEN I-O et REWRITE — 23 octobre 2026

- **239 tests découverts : 238 réussis, un test PE Windows ignoré.**
- `sequential_io.cob` : statuts 35/05/43/48/49 et octets finaux identiques ;
  le fichier OPTIONAL ouvert en I-O est créé vide comme en natif.
- NIST : **66/458** ; vérification complète des acceptées **66/66** conformes.

## DECLARATIVES et fichiers — 23 octobre 2026

- **235 tests découverts : 234 réussis, un test PE Windows ignoré.**
- **55/55 comparaisons locales conformes**, dont `declaratives.cob` : USE par
  fichier et par mode, 10/46/41/42/35, OPEN multiple, mode conservé par 41.
- NIST : **59/458 émissions acceptées** ; 29 nouvelles comparaisons conformes,
  117 PASS natifs identiques.

## Groupes, configuration et receveurs multiples — 23 octobre 2026

- **231 tests découverts : 230 réussis, un test PE Windows ignoré.**
- **54/54 comparaisons locales conformes**, dont `group_value.cob` et
  `multi_receivers.cob` (22 lignes mesurées en natif avant implémentation).
- NIST : **30/458 émissions acceptées** ; **30/30 comparaisons conformes** avec
  les entrées reconstituées du runner, REPORT identiques aux journaux natifs :
  401 PASS, 1 INSPECT, 0 FAIL (`build/nist-verify-30.json`).
- La régénération de `.tools/nist-native-gnucobol-3.2` par
  `tools/nist_native_reference.sh` reproduit le même résumé (9610 PASS) ; seul
  NC214M diffère, par l'heure courante qu'il imprime.

## DATA RECORDS et MOVE numérique tronquant — 23 octobre 2026

Environnement : Ubuntu 24.04 x86-64, Python 3.13, Rust 1.97, GnuCOBOL 3.2.0
compilé depuis les sources GNU signées avec BDB (`tools/install_gnucobol.sh`).

- **212 tests découverts : 211 réussis, un test PE Windows ignoré.** Les ajouts
  couvrent DATA RECORDS (métadonnée, refus natifs, deux comparaisons de
  fichiers), le MOVE tronquant, l'index source strict, les deux chemins COMP-3
  de cobc et l'arrêt nommé du quartet de tête.
- **52/52 comparaisons locales conformes** (`build/verification.json`). La
  fixture `numeric_truncation.cob` couvre DISPLAY/COMP/COMP-3, signes, V,
  littéraux et zéros négatifs `00p`/`000D`, mesurés en natif avant implémentation.
- NIST statique : **20/458 émissions acceptées**, 16 blocages au prétraitement,
  422 à l'analyse, aucun à l'émission et zéro erreur interne
  (`build/coverage-nist-data-records.json`).
- **8/8 nouvelles comparaisons NIST conformes** et **12/12 anciennes** sans
  régression. Les REPORT des 8 nouvelles sources sont identiques aux journaux
  du runner NIST natif : 44 PASS, sans FAIL/DELETED/INSPECT.
- Runner NIST natif complet de référence : 426 programmes, 9748 tests,
  9610 PASS, 0 FAIL, 20 DELETED, 118 INSPECT (`.tools/nist-native-gnucobol-3.2`).

## Séparateurs et paragraphes documentaires

- **200 tests découverts : 199 réussis, un test PE Windows ignoré.** Les 37
  ajouts couvrent séparateurs et portée de phrase, indices signés, PICTURE
  contiguës, commentaires adjacents, refus des éditions non modélisées,
  COPY conservateur et entrées documentaires en formats fixe/libre. Les cas
  documentaires vérifient les guillemets ouverts, COPY ignorés/réels, directives,
  lignes de diagnostic et conservation des clauses sémantiques. Log local :
  `/workspace/tooling/separators-documentary-reviewed-tests.log`.
- **51/51 comparaisons locales conformes**. Les nouvelles fixtures
  `separators.cob` et `documentary_fixed.cob` ont des sorties attendues vérifiées
  indépendamment ; le source documentaire fixe est aussi compilé nativement
  depuis le profil libre grâce à sa directive de format. Rapport :
  `build/verification-separators-documentary.json`.
- NIST statique : **12/458 émissions acceptées**, 16 blocages au prétraitement,
  430 à l'analyse, aucun à l'émission et zéro erreur interne. **94 sources**
  changent de premier diagnostic/statut, dont 57 passent du prétraitement à
  l'analyse. NC246A et SQ202A deviennent acceptés. Rapport :
  `build/coverage-nist-separators-documentary-reviewed.json`.
- **2/2 comparaisons NIST supplémentaires conformes**, codes nuls, stdout et
  fichiers identiques aux références natives indépendantes. NC246A vérifie
  **49 PASS**, SQ202A **1 PASS**, sans FAIL/DELETED/INSPECT. Les bilans et
  lignes de détail sont contrôlés ; les en-têtes répétés ne sont pas comptés
  comme des tests. Rapport : `build/nist-separators-documentary-verification.json`.
- SQ202A écrit et relit **750 records de 120 octets**. Les 90000 octets de
  XXXXX001 ont le SHA256
  `c3a5a8f0b77c2ddb7ee6f59ae960fb0beb2b39e82f99ab1b101fa94c49e9c415`.
  Les deux programmes sont autonomes : aucun stdin, fichier d'entrée, COPY ou
  programme externe. Ce contrôle reste ciblé et ne constitue pas une exécution
  complète du runner NIST ni une garantie universelle.

## Comparaisons mixtes et MOVE depuis texte

- **163 tests découverts : 162 réussis, un test PE Windows ignoré.** Les
  22 nouveaux tests couvrent les six relations dans les deux ordres, largeur
  PICTURE, V, groupes/refmod, littéraux non signés et ZERO, lectures textuelles,
  troncature, invalides, alias et négatifs zéro bruts DISPLAY/COMP-3. Une preuve
  native conserve DIRECT:FALSE/FIELD:TRUE pour une comparaison optimisée avec
  littéral texte ; les cas hors de la garde sont refusés. La suite ciblée a
  aussi été relancée après ajout du cas `ZERO = ""`, faux nativement.
- **49/49 comparaisons locales conformes**. La fixture `mixed_types.cob` combine
  comparaison, lecture signée depuis PIC X, édition et fichier de rapport.
  `mixed-report.txt` contient `MATCH\n-12.30\n` (13 octets), SHA256
  `3513c1fc64a7b34e0ed21ae9a38eba43bcd1cec141594786c5a81054fb00267a`.
  Rapport : `build/verification-mixed-types.json`.
- NIST : **10/458 émissions acceptées**, 73 blocages au prétraitement, 375 à
  l'analyse, aucun blocage d'émission restant et zéro erreur interne. NC132A
  et ST126A sont les deux nouvelles sources acceptées. Rapport :
  `build/coverage-nist-mixed-types-final.json`.
- **3/3 comparaisons NIST supplémentaires conformes**, codes nuls, stdout et
  fichiers finaux identiques aux références natives : NC132A, ST107A et ST126A.
  Leurs bilans donnent **25, 6 et 18 PASS**, soit **49 réussites**, sans FAIL,
  DELETED ni INSPECT. Empreintes sources/COPY, entrées, sorties et bilans :
  `build/nist-mixed-types-verification.json`.
- Les entrées de ST107A et ST126A ont été produites par les programmes officiels
  ST106A et ST125A exécutés en GnuCOBOL. Chaque fichier fait 243 octets, neuf
  records SEQUENTIAL de 27 octets, SHA256
  `50fbb785d0857f495d756ba1632e236ec9115aac8ab413570871c8db2fe05cf7`.
  Les deux PASS des producteurs ne sont pas comptés comme preuve Rust ; SORT
  reste hors périmètre du convertisseur.

Les littéraux texte vers Numeric ordinaire, la déédition, les calculs sur texte
et les catégories mixtes EVALUATE/88 restent refusés. Les comparaisons directes
contre littéral texte exigent un entier et des chiffres de même largeur ; les
autres cas passent par un champ PIC X. Les résultats ne constituent pas une
exécution complète du runner NIST ni une garantie universelle.

## MOVE numérique vers texte et rapports CCVS

- **141 tests découverts : 140 réussis, un test PE Windows ignoré.** Les
  17 nouveaux tests vérifient la distinction MOVE/calcul, chiffres et signe,
  littéraux/ZERO, groupes bruts, source avec V, sous-chaînes, modulo COMP/index,
  alias et adresse source indexée résolue une fois. Les sorties et fichiers
  attendus sont indépendants de l'implémentation.
- **48/48 comparaisons locales conformes**. La nouvelle fixture
  `numeric_move_report.cob` combine compteurs de rapport, remplissage ZERO,
  littéraux et copie brute signée. Son fichier de 28 octets a le SHA256
  `6a4189b0879af9bba617f35fa87b29897c19d48db58e7d8afd82c7d45c586f60`.
  Rapport : `build/verification-numeric-move.json`.
- NIST passe de **2 à 8/458 émissions acceptées** : 73 blocages au
  prétraitement, 375 à l'analyse, 2 à l'émission et zéro erreur interne. Les
  huit anciens diagnostics d'émission changent ; six sources sont acceptées,
  NC132A atteint une comparaison nombre/texte et ST126A un transfert texte vers
  nombre, toujours refusés. Rapport : `build/coverage-nist-numeric-move.json`.
- **5/5 nouvelles comparaisons NIST conformes**, stdout, codes nuls et fichiers
  finaux : NC127A, NC136A, NC137A, SM106A et SM107A. Leurs fichiers REPORT sont
  identiques aux sorties natives indépendantes et donnent respectivement
  2, 8, 8, 0 et 200 PASS automatiques : **218 réussites**, aucun FAIL ni DELETED,
  **une inspection requise dans SM106A**. Ce dernier cas n'est pas compté PASS.
  Rapport avec empreintes, lignes de bilan et compteurs :
  `build/nist-numeric-move-verification.json`.
- ST107A est accepté statiquement mais non exécuté : il attend `XXXXX001`,
  fichier SEQUENTIAL de 27 octets par record produit par ST106A. Ces données
  ne sont pas livrées ; aucun jeu d'entrée de substitution n'a été fabriqué.

Les preuves portent sur ces programmes et ce profil GnuCOBOL, sans runner
complet de conformité. Les DISPLAY signés invalides restent un arrêt nommé ;
la normalisation native de leurs signes et ses mutations restent hors profil.
Un index vers un groupe, les calculs vers texte, la déédition et les conversions
texte vers nombre restent refusés. DISPLAY non signé invalide est copié brut.

## GO TO et retours PERFORM explicites

- **124 tests découverts : 123 réussis, un test PE Windows ignoré.** Les
  21 nouveaux tests GO et les 16 tests sections passent. Les comparaisons
  natives couvrent sauts avant/arrière et vers section, cadres PERFORM en
  attente hors de leur plage, retour au sommet uniquement, deux points de
  retour distincts, EXIT SECTION, sorties des handlers et des boucles inline.
- **47/47 comparaisons locales conformes**, avec `goto_flow.cob` qui combine
  détour hors d'une plage PERFORM, retour différé, GO DEPENDING et EXIT SECTION.
  Rapport : `build/verification-goto.json`.
- Une régression reproduit l'écrasement du compteur TIMES lors d'une réentrée
  récursive au même site, en inline comme en outlined. Les contrôleurs GO
  DEPENDING sont vérifiés en DISPLAY, COMP, COMP-3, table subscriptée et index
  implicite, avec ON facultatif et continuation pour les indices hors plage.
  Décimaux et contrôleurs de plus de neuf chiffres sont explicitement refusés.
- NIST : **2/458 émissions acceptées**, 73 blocages au prétraitement, 375 à
  l'analyse, 8 à l'émission, zéro erreur interne. Les premiers diagnostics ou
  statuts changent pour 47 sources. Rapport : `build/coverage-nist-goto.json`.
  Les blocages GO TO révèlent notamment des conversions numérique/texte des
  rapports CCVS encore refusées ; la mesure reste statique.
- NC110M est aussi compilé et exécuté séparément en GnuCOBOL et Rust : mêmes
  octets stdout, codes nuls, aucun fichier divergent. Sa ligne PASS est présente,
  sa ligne FAIL absente et sa fin de test atteinte. Rapport :
  `build/nist-nc110m-verification.json`. Ces contrôles portent sur les deux
  comportements GO/PERFORM de ce programme, pas sur une conformité NIST complète.

Les étapes ci-dessous conservent leurs résultats historiques.

## Sections de procédure et PERFORM

- **103 tests découverts : 102 réussis, un test PE Windows ignoré.** Les
  16 nouveaux tests comprennent huit comparaisons Rust/GnuCOBOL avec sorties
  attendues indépendantes : bornes section/paragraphe et THRU mixtes,
  préambules et sections vides, enchaînement sans STOP, tous les modes de boucle,
  appels récursifs, propagation STOP RUN et EXIT PARAGRAPH, EXIT nu sans effet.
- **46/46 comparaisons locales conformes**, y compris la fixture intégrée
  `sections.cob` : préambule, section vide, THRU mixte et sorties de paragraphe.
  Rapport : `build/verification-sections.json`.
- Une preuve GnuCOBOL montre que EXIT SECTION peut dépasser le retour d'un
  PERFORM de paragraphe et poursuivre dans la section suivante. Le frontend
  refuse cette instruction, ainsi que EXIT PERFORM, qualifications/homonymes
  de procédures et segments SECTION numérotés.
- Le rapport de conversion conserve les paragraphes déclarés et expose en
  plus les sections, leurs intervalles et les blocs anonymes. Inspection de
  la fixture `sections.cob` : préambules conservés, y compris section vide,
  et aucun nom synthétique ajouté aux paragraphes.
- NIST reste à **1/458 émission acceptée**, 73 blocages au prétraitement,
  384 à l'analyse et zéro erreur interne. Les premiers diagnostics changent
  pour 48 sources ; GO TO est désormais le premier obstacle sur 46 sources.
  Rapport : `build/coverage-nist-sections.json`. Cette mesure statique ne
  compile ni n'exécute les programmes NIST.

## PICTURE éditées et clauses FD

- **87 tests découverts : 86 réussis, un test PE Windows ignoré.** Les nouveaux
  tests comparent des sorties attendues indépendantes en plus de GnuCOBOL/Rust :
  signe après échelle et avant modulo, ROUNDED, suppression Z, initialisation,
  valeurs textuelles brutes, alias, sous-chaînes et IS NUMERIC. Une régression
  native démontre le repli de constantes des comparaisons/EVALUATE directement
  édités et impose leur refus explicite jusqu'à modélisation.
- **45/45 comparaisons locales conformes**. `edited_report.cob` combine FD
  LABEL/BLOCK/RECORD/RECORDING F, images éditées, alias et contrôles d'impression.
  Rapport : `build/verification-edited-final.json`.
- RECORD CONTAINS n'est accepté qu'à taille physique exacte ; les longueurs
  pouvant sélectionner un format variable sont refusées. Les preuves natives
  couvrent LABEL/BLOCK en SEQUENTIAL et LINE SEQUENTIAL, octets et statuts.
- NIST reste à **1/458 émission acceptée**, 73 blocages au prétraitement, 384
  à l'analyse et zéro erreur interne. Les PICTURE et LABEL/BLOCK révèlent
  notamment 44 premiers blocages CCVS1 SECTION et 18 clauses FD DATA.
  Rapport : `build/coverage-nist-edited-final.json`.

La déédition et les images non modélisées restent refusées. Ces tests ne sont
pas une exécution des assertions de conformité NIST.

## Extension SEQUENTIAL fixe et rapports

- **76 tests découverts : 75 réussis, un test PE Windows ignoré.** Les nouveaux
  essais natifs comparent aussi les octets attendus : records bruts sans LF,
  COMP/COMP-3, alias FD, lectures partielles, READ INTO, AFTER/BEFORE avec zéro
  ligne, plusieurs lignes ou PAGE, fermeture implicite et réouverture EXTEND.
- **44/44 comparaisons locales conformes**, avec `sequential_records.cob` et
  `sequential_report.cob`. Rapport : `build/verification-sequential.json`.
- NIST reste à **1/458 émission acceptée**, 73 blocages au prétraitement et
  384 à l'analyse, sans erreur interne. Les anciens refus du SEQUENTIAL
  implicite révèlent désormais les PICTURE éditées, clauses FD et autres
  fonctionnalités manquantes. Rapport : `build/coverage-nist-sequential.json`.

Les organisations SEQUENTIAL et LINE SEQUENTIAL ont des implémentations
distinctes. Les descriptions FD de tailles différentes restent refusées,
ainsi que les formats variables, autres clauses FD et compteurs ADVANCING
variables. Les preuves portent sur le profil GnuCOBOL et les entrées testés.

## Extension du format fixe et des paragraphes de configuration

- **64 tests découverts : 63 réussis, un test PE Windows ignoré.** Les tests
  supplémentaires couvrent continuations, guillemets à la colonne 72,
  littéraux distincts, espaces, tabulations, commentaires et rejets explicites.
  Les comparaisons ciblées utilisent le source fixe original côté GnuCOBOL.
- **42/42 comparaisons du corpus local conformes**, avec une nouvelle fixture
  combinant configuration et continuations. Rapport :
  `build/verification-continuations.json`.
- Le même corpus NIST de 458 sources donne **1 émission acceptée**, 73 blocages
  au prétraitement, 384 à l'analyse et aucune erreur interne. Rapport :
  `build/coverage-nist-fixed.json`.
- SM301M a été compilé et exécuté séparément en COBOL et Rust ; sortie d'un
  espace suivi de LF, codes nuls et fichiers identiques. Rapport :
  `build/nist-sm301m-verification.json`. Cette vérification ne porte pas sur
  les diagnostics de conformité que le test NIST attend du compilateur.

Les sections suivantes décrivent les étapes précédentes.

## Reprise Linux et mesure de couverture externe

Le corpus livré a été recompilé et exécuté sous Linux : **41/41 comparaisons
conformes**, rapport `build/verification.json`. La suite Python historique a
découvert 34 tests : **33 réussis, un ignoré** car le PE du GnuCOBOL portable
Windows n'est pas installé. Les outils sont Python 3.12.14, Rust 1.99.1 et
GnuCOBOL 3.2.0 sur Debian 13 x86-64.

Les outils de préparation et de mesure NIST ajoutent 15 tests. La suite complète
découvre désormais **49 tests : 48 réussis, un ignoré**. La préparation réelle a
produit les mêmes 511 empreintes qu'une extraction avec les outils officiels.

L'analyse statique NIST CCVS85 a inventorié **458 sources** (414 `.CBL` et
44 `.SUB`), toutes bloquées avant émission Rust : 398 au prétraitement, 60 à
l'analyse, zéro erreur interne. Aucun cas NIST n'a été exécuté ; ce résultat
mesure les lacunes de prise en charge, pas une conformité. Les détails,
empreintes et priorités sont dans [COVERAGE.md](COVERAGE.md). Les sections de
livraison ci-dessous conservent leurs résultats historiques Windows.

## Version 0.4 : tables variables, index et erreurs de taille

- **34 tests Python réussis**, avec les 3 tests Rust du moteur décimal inclus.
  Les nouveaux contrôles couvrent les dispositions ODO refusées, les compteurs
  et sous-scripts actifs hors limites, la capacité des index et les données
  invalides qui doivent rester des erreurs malgré un gestionnaire SIZE ERROR.
- **41 programmes conformes à GnuCOBOL** sur stdout, codes de retour nuls et
  fichiers finaux. Rapport : `build/verification-v0.4.json`.
- OCCURS DEPENDING ON terminal réserve sa capacité maximale et utilise la
  longueur active pour les transferts et affichages de groupes. Les éléments
  peuvent contenir des groupes et des tableaux fixes ; les dispositions à
  glissement, les contrôleurs internes et les enregistrements FD variables
  sont refusés.
- INDEXED BY, SET TO/UP/DOWN et PERFORM VARYING sont comparés à l'oracle, y
  compris les index imbriqués, le transfert entre tables de tailles différentes,
  l'état initial à 1 et les bornes signées de 32 bits. SET UP/DOWN relit son
  opérande pour chaque destinataire, ce qu'un cas de régression vérifie.
- ON SIZE ERROR / NOT ON SIZE ERROR couvrent les cinq verbes arithmétiques,
  ROUNDED, GIVING, divisions par zéro imbriquées, destinations COMP-3/COMP,
  résultats négatifs non signés et conservation du champ lors d'un échec.
- Une différence observée sur INITIALIZE de groupe ODO composé a conduit à
  refuser cette forme, plutôt que conserver une traduction inexacte. Le C
  généré par GnuCOBOL 3.2 utilise notamment `cob_init_table`, dont les effets
  aux petites valeurs du compteur nécessitent un modèle séparé. Le cas uniforme
  texte vérifié et l'initialisation d'une occurrence résolue sont pris en charge.
- `examples/variable_batch.cob` charge 4 montants, rejette 2 lignes, traite
  1 dépassement de total et produit `TOTAL=001675` dans `summary.txt`.
  Le total affiché est 16,75 ; la table utilise ODO et COMP-3.
- Démo compilée : `build/demo-variable-v0.4`. Paquet installable :
  `build/dist/cobol2rust-0.4.0-py3-none-any.whl`, testé hors des sources.

Le parcours sans source reste une inspection PE/ELF. La décompilation vers Rust
et la cible Linux ne sont pas validées. Aucun programme métier de l'utilisateur
n'a encore été fourni ; ces résultats portent sur le corpus livré.

## Version 0.3 : mémoire structurée, tableaux et conditions

- **28 tests Python réussis**, avec contrôles de disposition mémoire, noms
  ambigus, indices et sous-chaînes hors limites, dispositions refusées et audit
  statique, en plus des tests précédents. Les 3 tests Rust du moteur décimal
  restent inclus dans le parcours Python.
- **34 programmes conformes à GnuCOBOL** sur stdout et les fichiers finaux.
  Rapport détaillé : `build/verification-v0.3.json`.
- Les groupes et sous-champs partagent désormais leurs octets, y compris à
  travers REDEFINES. Les tableaux fixes imbriqués, les conditions 88, SET,
  EVALUATE TRUE, IS NUMERIC et les sous-chaînes sont couverts par le corpus.
- Les représentations brutes DISPLAY signé, COMP-3 et COMP/BINARY sont comparées
  directement, y compris quand un groupe affiché contient des octets non UTF-8.
  Le profil testé utilise COMP/BINARY big-endian avec tailles 1-2-4-8.
- Un défaut découvert sur MOVE à plusieurs destinations superposées a été
  corrigé : l'adresse source est résolue une fois, puis les données sont relues
  pour chaque destination. Les cas d'alias et d'indices modifiés sont conservés
  dans `tests/fixtures/aliasing.cob`.
- L'exemple d'intégration `examples/batch_accounts.cob` lit un fichier de
  mouvements, valide ses colonnes, met à jour un tableau COMP-3 puis produit
  les soldes. Résultat : 4 mouvements acceptés, 3 rejetés ; soldes 7,50 / 100 /
  -5 / 0 / 0. Console et fichier de sortie sont identiques à l'oracle.
- La démo compilée se trouve dans `build/demo-batch-v0.3`, avec un jeu d'entrée
  copié dans son dossier et un fichier `balances.txt` produit par le Rust.
- Le paquet `build/dist/cobol2rust-0.3.0-py3-none-any.whl` a été construit et
  testé hors des sources : conversion du batch et audit des exemples réussis,
  avec les modules Python et Rust nécessaires inclus.

La commande audit reste une vérification statique, sans preuve d'équivalence.
Le profil mémoire est enregistré dans les rapports, avec les empreintes du
source développé et des copybooks. À cette version, les tableaux variables/indexés, les profils
EBCDIC/IBM/Micro Focus, fichiers indexés et le parcours binaire restent à ajouter.
La cible Linux n'a pas été exécutée.

## Version 0.2 : fichiers LINE SEQUENTIAL

La version 0.2 ajoute les fichiers texte à enregistrement élémentaire PIC X :
ouverture INPUT/OUTPUT/EXTEND, lecture, écriture, copie d'enregistrements,
fichiers optionnels, statuts et branches de fin de fichier.

- **23 tests Python réussis**, dont les refus des constructions non modélisées,
  l'arrêt sur données incompatibles, la conservation des fichiers d'entrée et
  la disponibilité des sous-dossiers d'entrée vides.
- Le test du vérificateur modifie volontairement le Rust généré : stdout et
  codes de retour restent identiques, mais le fichier diffère. Le vérificateur
  signale correctement cette divergence.
- **25 programmes comparés avec GnuCOBOL**, portant sur stdout et les octets des
  fichiers finaux. Rapport : `build/verification-v0.2.json`.
- La référence GnuCOBOL compile le **source original**, avec son format et ses
  copybooks. Le vérificateur n'utilise plus le frontend du transpileur pour
  préparer le source de référence.
- Démo générée et compilée : `build/demo-files-v0.2`, depuis `examples/files.cob`.
- Paquet `build/dist/cobol2rust-0.2.0-py3-none-any.whl` construit ; conversion
  d'un programme à fichiers testée hors du dossier source, avec le nouveau
  runtime Rust correctement inclus.

Les nouveaux cas couvrent l'ajout de lignes, les fichiers absents et optionnels,
la fermeture et la lecture dans des modes incorrects, la deuxième lecture après
EOF, READ INTO, les lignes vides, le remplissage et la troncature, la conservation
des espaces avec COB_LS_FIXED, la copie entre deux fichiers et une dernière ligne
sans saut de ligne.

Le corpus de troncature impose explicitement `COB_LS_SPLIT=0`, consigné dans son
rapport. Le découpage des lignes longues avec ce paramètre actif n'est pas
implémenté : le runtime s'arrête avec un message au lieu de produire un résultat
approximatif. Voir les limites détaillées dans le README.

La cible Linux et la conversion d'exécutables sans sources restent non validées.

## Historique : version initiale 0.1

Environnement : Windows x86-64, Python 3.11.9, Rust 1.96.0
(`stable-x86_64-pc-windows-gnu`), GnuCOBOL 3.2.0 / MinGW GCC 9.2.0.

## Résultats

- **15 tests Python réussis**, incluant le parseur strict, les erreurs de types,
  les COPY cycliques, la protection des sorties existantes, l'inspection PE/ELF,
  les arrêts explicites du runtime et le parcours de la commande `verify`.
- **3 tests Rust réussis**, lancés par la suite Python : calcul et arrondis,
  remplissage texte, troncature des divisions intermédiaires.
- **18 programmes comparés avec GnuCOBOL, 18 conformes**, avec comparaison des
  octets de stdout et deux codes de retour nuls. Le rapport détaillé est dans
  `build/verification.json`.
- Démo `examples/invoice.cob` convertie, compilée et exécutée via Cargo dans
  `build/demo-rust`. Rapport individuel dans `build/invoice-checked.json`.
- Inspection en lecture seule d'un vrai PE x86 (`cobcrun.exe`) : détection des
  imports `libcob-4.dll` et des fonctions `cob_*` ; rapport dans
  `build/cobcrun-inspection.json`.
- Paquet Python `build/dist/cobol2rust-0.1.0-py3-none-any.whl` construit et testé
  hors du dossier source ; le runtime Rust est bien inclus dans le paquet.

Les 18 programmes couvrent : facture, console interactive, format fixe,
copybook, paragraphes, enchaînement séquentiel, `THRU`, arrêt dans un `PERFORM`,
boucles avant/après, incrément variable, conditions imbriquées, `EVALUATE`,
chaînes et commentaires, littéraux numériques, `INITIALIZE`, usages COMP et
COMP-3, arrondis négatifs et précision à 18 chiffres.

## Défaut détecté puis corrigé

Le calcul rationnel exact initial ne reproduisait pas la perte de précision
intermédiaire de GnuCOBOL pour `(1 / 3) * 3`. Le runtime utilise désormais des
coefficients entiers décimaux de précision arbitraire et conserve les échelles,
avec le décalage de division observé dans GnuCOBOL 3.2. Le cas est couvert par
la suite différentielle et un test Rust.

## Portée

Ces résultats portent sur les cas et entrées présents dans le dépôt. Ils ne
constituent pas une preuve de compatibilité avec tous les programmes, dialectes,
options arithmétiques ou runtimes COBOL. Les effets de fichiers et les transactions
ne sont pas comparés : ces constructions sont actuellement refusées par le
convertisseur. Aucun exécutable COBOL n'a été converti en Rust sans ses sources.
La cible Linux n'a pas encore été exécutée.

Pour reproduire depuis la racine :

```powershell
python -m unittest discover -v
python tools/verify.py
```
