# Validation — 30 octobre 2026

## Littéraux B et H — 31 octobre 2026

- `scan_b` / `scan_h` : B"…" et H"…" donnent un littéral numérique ; cinq
  cas de refus confrontés à `cobc -fsyntax-only` (caractère invalide, H de
  17 chiffres, B"012", B en `-std=cobol85`) et B"0101" accepté par les deux.
- Preuves : `tests/fixtures/boolean_hex_literals.cob` identique au natif
  (VALUE, MOVE, COMPUTE, comparaison) ; run_extensions-002 et -005
  identiques au natif ; `tests/test_boolean_hex_literals.py` : quatre tests.
- Mesure : **1262 → 1264/3593**, écart **355 → 353** ; exécution comparée
  inchangée (74/84) ; NIST statique **451/458** ; suite **533 tests, 0 échec,
  un PE Windows ignoré** (`tools/run_tests.py`).

## Inventaire de l'écart — 31 octobre 2026

- Mesure (`real_corpora.py --cobc --execute --record`) : total inchangé
  **1262/3593**, écart **355**, à examiner 0 ; exécution comparée inchangée
  (74/84). Seuls changent des libellés de refus : `SCREEN SECTION non prise
  en charge à cet endroit` (36 sources, auparavant « niveau de donnée
  attendu »), `GOBACK RETURNING` et `EXIT PROGRAM RETURNING/GIVING non pris
  en charge` (auparavant « instruction non prise en charge: RETURNING »).
- Inventaire : **355/355** sources au premier diagnostic identique à la
  mesure, **198** à inventaire complet, 224 diagnostics distincts ; ordre
  glouton enregistré dans CAP.md et `measurements/real-corpora.json`.
- Le mode reprise est inactif hors inventaire (`Parser.recovered = None`) ;
  la boucle de `block()` réécrite reste équivalente (mêmes arrêts). NIST
  statique **451/458** (`build/coverage-nist-inventory.json`).
- Quatre nouveaux tests dans `tests/test_pipeline.py` : diagnostics suivants
  et premier conservé, usages d'une déclaration sautée, terminateur de
  l'instruction refusée, plan limité aux inventaires complets.
- Suite (`tools/run_tests.py`, 4 processus) : **529 tests, 0 échec, un PE
  Windows ignoré**, en 255 s (somme 1018 s, après redémarrage du conteneur :
  caches Cargo des emplacements à reconstruire).

## Pipeline de validation parallèle — 31 octobre 2026

Étape d'outillage : rien de ce que le convertisseur accepte ou produit ne
change. Preuves d'identité :

- Mesure des corpus réels, conversion de 3593 sources : rapports par source
  identiques à ceux d'avant la modification (statut, diagnostic, programme,
  empreintes du source étendu et des copybooks) : **0 écart**.
- Cache d'analyse : Rust émis par `emit_unit` sans cache, avec cache, puis
  une seconde fois avec cache, comparé sur les **1198 unités acceptées**
  (programmes principaux des sept corpus) : **0 différence**.
- Exécution comparée en parallèle : même statut et mêmes raisons pour chacun
  des 84 programmes (CardDemo 8/8, zopeneditor 3/3, cours 10/12, livre
  53/61).
- NIST statique : **451/458**, rapport identique source par source
  (`build/coverage-nist-pipeline.json`), en 9 s au lieu d'environ une minute.
- NIST ciblé (20 programmes à OPEN multiple) avec `--jobs` : **20/20
  conformes**, 124 PASS, 0 FAIL, 1 INSPECT, en 16 s
  (`build/nist-verify-pipeline.json`).
- NIST complet avec `--jobs` : **427/427 conformes, 9610 PASS, 0 FAIL,
  20 DELETED, 118 INSPECT**, comme la référence, en **375 s** au lieu
  d'environ 1 h 15 (`build/nist-verify-pipeline-full.json`).
- Suite Python avec `tools/run_tests.py` (4 processus) : **525 tests en
  162 s** (somme des modules 603 s), un test PE Windows ignoré ; six
  nouveaux tests dans `tests/test_pipeline.py` (cache d'analyse, portée des
  constantes et index, builds parallèles de programmes de même nom).

Défaut latent corrigé : deux crates de même nom (`cobol_prog`) compilées
dans un même répertoire Cargo pendant que la première existait encore
recevaient le même exécutable (empreinte Cargo indépendante du chemin d'un
paquet racine). Reproduit par 8 programmes `prog` (sortie `v2` répétée),
corrigé par `cargo clean -p` dans un emplacement verrouillé ; le test
`test_programs_with_one_name_built_in_parallel_keep_their_executable` le
couvre.

## COLUMN PLUS, erreurs de reportio et OPEN de plusieurs fichiers — 31 octobre 2026

- `col_or_plus` et `output_report_data` : COLUMN PLUS n se place à
  `report_col_pos + n - 1` (la colonne suivant l'article précédent de la
  ligne) ; sur le premier article d'une LINE, PLUS est ignoré et n est la
  colonne ; PLUS 0 et un article sans COLUMN prennent `report_col_pos`. Un
  01, une LINE ou un TYPE remet la position à 1. LEFT/RIGHT/CENTER restent
  refusés.
- reportio.c : INITIATE d'un rapport actif affiche `libcob: error: INITIATE
  r was already done`, lève EC-REPORT-ACTIVE et poursuit ; GENERATE et
  TERMINATE sans INITIATE lèvent EC-REPORT-INACTIVE puis `cob_hard_failure`.
  Le nom est celui du RD tel qu'écrit (`r->report_name`).
- OPEN de plusieurs modes (`open_file_entry`) : d'après le C généré par
  cobc, chaque mode ouvre un groupe d'instructions implicites, enfants du
  dernier fichier du groupe précédent (`begin_implicit_statement` avec le
  `current_statement` d'alors) ; un fichier est contrôlé après son
  ouverture, le dernier d'un groupe après les groupes suivants, chaque
  contrôle testant `cob_exception_code`. Dans `OPEN INPUT a OUTPUT b`,
  l'échec de `a` n'est vu que si `b` échoue aussi, et le gestionnaire par
  défaut nomme `cob_error_file` (le dernier fichier ouvert). Avec USE, la procédure du
  dernier fichier peut précéder le gestionnaire par défaut (fatal) d'un
  autre. Le suivi de `cob_exception_code` (save_status, cob_set_exception,
  init de STRING/UNSTRING/INSPECT, ALLOCATE/FREE ; fonctions non auditées et
  CALL : inconnu) n'est généré que pour les unités ayant un tel OPEN et des
  DECLARATIVES ; une lecture en état inconnu est un arrêt nommé. CLOSE
  contrôle chaque fichier aussitôt (C généré à l'appui).
- Preuves : `tests/fixtures/report_column_plus.cob`,
  `tests/fixtures/open_several.cob` et `tests/fixtures/open_entries.cob`
  identiques au natif (stdout, stderr, fichiers, codes), ainsi que
  `declaratives.cob` (deux fichiers d'un même mode, contrôlés chacun) ;
  `tests/test_open_several_column_plus.py` : cinq tests.
  Re-vérification NIST des 20 programmes à OPEN multiple : **20/20
  conformes**, 124 PASS, 0 FAIL, 1 INSPECT (`build/nist-verify-open-20261031.json`).

Mesure : **1255 → 1262/3593**, testsuite **531 → 538/1135**, écart **362 →
355**. Les sept sources débloquées (run_reportwriter-002/005/006/010/022/023/
024) s'exécutent à l'identique, cinq avec codes zéro et deux sur l'erreur
fatale (codes 1/1). Exécution globale renouvelée : **74/84**, inchangée. NIST
statique : **451/458** (`build/coverage-nist-column-plus-20261031.json`).
Suite Python complète : **519 tests découverts, 518 validés et un test PE
Windows ignoré**.

## EXTERNAL AS — 31 octobre 2026

- `external_clause` : `EXTERNAL AS littéral` (01/77) ; `cb_to_cname` donne le
  nom de tout article EXTERNAL (majuscules, `-` et espace en `_`), si bien que
  `EXT-VAR`, `"ext-var"` et `EXT_VAR` désignent le même article.
- `cob_external_addr` : l'article est alloué par sa première déclaration ;
  plus court, `libcob: warning: EXTERNAL item 'X' previously allocated with
  size N, requested size is M` et le préfixe de l'article est partagé ; plus
  long, l'erreur `libcob: error: …` (code 1). Le cas spécial `ERRNO` de 4
  octets (l'`errno` du C) est refusé à la conversion.
- Preuves : `tests/fixtures/external_as.cob` (deux programmes : littéral en
  minuscules, collision `other_b`/`other-b`, avertissement de taille)
  identique au natif, stderr compris ; `tests/test_external_as.py` : quatre
  tests, dont l'erreur de taille. Suite complète : **514 découverts, 513
  validés, un PE Windows ignoré**.

Mesure : **1250 → 1255/3593**, testsuite **526 → 531/1135**, écart **367 →
362**. Quatre sources débloquées identiques avec codes zéro (run_misc-013
caller/callee, run_misc-014 bigger/callee) ; run_misc-014/smaller s'arrête
des deux côtés sur l'erreur de taille, mais la pile « Last statement of …
Started by <chemin> » que libcob ajoute aux erreurs fatales n'est pas
reproduite. Exécution globale renouvelée : **74/84**, inchangée. NIST
statique : **451/458** (`build/coverage-nist-external-as-20261031.json`).

## INITIALIZE VALUE et DEFAULT — 30 octobre 2026

- Grammaire de parser.y : `_initialize_filler`, `_initialize_value` (ALL ou
  une catégorie, TO facultatif), `_initialize_replacing`,
  `_initialize_default` ([THEN] [TO] DEFAULT) ; sans VALUE ni REPLACING,
  DEFAULT s'applique (`cb_emit_initialize`).
- `deduce_initialize_type` : SIGN SEPARATE élémentaire, REDEFINES subordonné,
  FILLER élémentaire sans WITH FILLER, VALUE de l'article ou du groupe,
  groupe uniforme ou composé, REPLACING par catégorie, DEFAULT (édité et
  packé par MOVE). `output_initialize_one` : VALUE comme à l'initialisation
  du stockage (`output_initialize_to_value`), REPLACING par MOVE, DEFAULT par
  MOVE ZERO/SPACE. `output_initialize_compound` : un article OCCURS est
  initialisé dans sa première occurrence, recopiée octet pour octet sur les
  autres (`propagate_table`) ; les parties non initialisées de la première
  occurrence écrasent donc celles des suivantes, comme en natif.
- La catégorie de `catégorie TO VALUE` n'est pas vérifiée (aucun test de
  `p->val` contre la catégorie dans codegen.c) : elle vaut ALL, essai natif à
  l'appui. Une sous-chaîne ou une table variable reste refusée avec ces
  phrases ; les formes simples et REPLACING sans DEFAULT gardent leur chemin.
- Preuves : `tests/fixtures/initialize_value.cob` (neuf cas : VALUE, VALUE
  de groupe, FILLER, REDEFINES, édité, packé, REPLACING THEN DEFAULT,
  propagation d'occurrence, occurrence indicée) identique au natif ;
  `tests/test_initialize_value.py` : trois tests. Suite complète : **510
  découverts, 509 validés, un PE Windows ignoré**.

Mesure : **1245 → 1250/3593**, testsuite **521 → 526/1135**, écart **372 →
367**, aucune acceptation refusée par cobc. Les cinq sources débloquées
s'exécutent à l'identique avec codes zéro. Exécution globale renouvelée :
**74/84 identiques**, inchangée. NIST statique : **451/458**
(`build/coverage-nist-initialize-20261030.json`).

## START complet et READ PREVIOUS — 30 octobre 2026

- START : `start_op` de parser.y (`NOT >` = LE, `NOT <` = GE, `NOT >=` = LT,
  `NOT <=` = GT ; NOT = est une erreur), FIRST et LAST sur la clé du fichier,
  `WITH SIZE/LENGTH` réservé à INDEXED (`cb_emit_start`), statut 23 hors de
  1..taille de la clé (`cob_start`). RELATIVE : `relative_start` (FIRST = GE
  depuis 0, LAST = LE depuis le dernier emplacement, LT/LE bornés à la
  taille du fichier). INDEXED : chemin BDB d'`indexed_start_internal`
  (DB_SET_RANGE puis DB_PREV ou DB_LAST ; LE avec doublons par
  DB_NEXT_NODUP puis DB_PREV).
- READ PREVIOUS : `cob_read_next` (46 au début de fichier, drapeaux de fin et
  de début), `relative_read_next` (recul de deux emplacements depuis la
  position courante, d'un après un enregistrement, `lseek` négatif sans
  effet : en natif des enregistrements sont sautés, essai à l'appui) et
  `indexed_read_next` (DB_PREV, DB_LAST en fin de fichier ou après
  suppression, fin immédiate après OPEN).
- Preuves : `tests/fixtures/start_previous.cob` (INDEXED à clé alternée avec
  doublons, clés partielles, toutes les conditions, WITH LENGTH/SIZE ;
  RELATIVE à trous) identique au natif, statuts, enregistrements et
  fichiers ; `tests/test_start_previous.py` : trois tests. Suite complète :
  **507 découverts, 506 validés, un PE Windows ignoré**.

Mesure : **1240 → 1245/3593**, testsuite **516 → 521/1135**, écart **377 →
372**, aucune acceptation refusée par cobc. Les cinq sources débloquées
(run_file-030/031/032/073/074) s'exécutent à l'identique avec codes zéro.
Exécution globale renouvelée : **74/84 identiques**, inchangée. NIST
statique : **451/458** (`build/coverage-nist-start-20261030.json`).

## Dernière exception — 30 octobre 2026

FUNCTION EXCEPTION-STATUS (9 premiers blocages) et ses voisines EXCEPTION-
LOCATION/STATEMENT/FILE (6) forment la troisième ligne de la mesure, après
SCREEN (backend terminal) et les verrous SELECT (essais entre processus).
Aucune règle ne dépend du nom d'un programme.

- Registre : `cob_set_exception`, `cob_get_last_exception_name` (entrée
  exacte, puis inclusion depuis la fin de la table) et les quatre fonctions
  de intrinsic.c ; seule SET LAST EXCEPTION TO OFF (`cob_set_exception (0)`)
  l'efface. Sans `-fsource-location` (profil par défaut), l'emplacement est
  « programme; ; 0 » et l'instruction des espaces. Le programme courant
  (COB_MODULE_PTR) suit les CALL.
- Sources portées : `save_status` (classe du statut, EC-I-O-EOP ;
  `cob_error_file` change à chaque opération, même réussie), `cob_decimal_div`,
  `cob_decimal_get_display` pour un receveur DISPLAY ou le temporaire DISPLAY
  d'un édité (sans SIZE ERROR, compteurs TALLYING de `cob_add_int`, pas de
  VARYING), tout receveur sous SIZE ERROR (KEEP_ON_OVERFLOW), PROHIBITED
  (EC-SIZE-TRUNCATION), strings.c, `cob_allocate`/`cob_free_alloc`,
  `cob_accept` en fin d'entrée, `cob_mod_or_rem` (zéro au lieu de l'arrêt
  nommé précédent), les sept fonctions ISO 8601 (`invalid_args`), le CALL
  introuvable et `cob_module_global_enter` : sous ON EXCEPTION, un appel
  récursif rend -1 avec EC-PROGRAM-RECURSIVE-CALL, sans NOT ON EXCEPTION.
- Inconnu, puis arrêt nommé à la lecture : fonctions intrinsèques non
  auditées (une fermeture des appels d'intrinsic.c isole 44 fonctions sans
  exception), exponentiation (`cob_decimal_pow`), stockage dans un receveur
  binaire, packé ou index (chemins optimisés de `cb_build_optim_add`),
  division par zéro dans une expression contenant une fonction (remise à
  zéro de `cob_exception_code`), SORT/MERGE, RELEASE, Report Writer, CANCEL
  ou fin d'un programme INITIAL avec des fichiers ouverts (`cob_close`),
  USE GLOBAL, SET UP/DOWN et toute instruction non auditée.
- Refus : EXCEPTION-LOCATION et EXCEPTION-STATEMENT sous `--runtime-checks`
  (cobc -debug suit section, paragraphe, ligne et sous-clauses).
- Preuves : `tests/fixtures/exceptions.cob` (E/S, cob_error_file, division,
  dépassements DISPLAY et édité, PROHIBITED, SIZE ERROR, MOD, FORMATTED-DATE,
  STRING, UNSTRING, INSPECT, FREE, ALLOCATE, CALL introuvable) et
  `exception_recursive_call.cob` (trois programmes, code de sortie 255)
  identiques au natif ; `tests/test_exceptions.py` : six tests dont les
  refus et trois arrêts nommés. Suite complète : **504 découverts, 503
  validés, un PE Windows ignoré**.

Mesure : **1225 → 1240/3593 émissions acceptées**, testsuite **501 →
516/1135**, écart **392 → 377**, aucune acceptation refusée par cobc. Les
quinze sources débloquées sont de la testsuite : douze identiques avec codes
zéro (run_functions-024/025 ×2/026/027/036/062/086/119, run_misc-132/170/171) ;
run_misc-040 caller et callee identiques, terminés par le STOP RUN RETURNING
1 de leur gestionnaire (codes 1/1, non comptés comme réussites) ; callee2
exécuté seul s'arrête des deux côtés sur la récursion fatale, mais la pile
« Last statement of … Started by <chemin> » de libcob n'est pas reproduite.
Exécution globale renouvelée : **74/84 identiques**, deux divergences et huit
délais, inchangés. NIST statique : **451/458**, zéro erreur interne
(`build/coverage-nist-exceptions-20261030.json`).

## Modèle d'adresses — 30 octobre 2026

USAGE POINTER (14 premiers blocages de la mesure précédente avec SET ADDRESS,
BASED et ALLOCATE) est le deuxième groupe après SCREEN, qui exige un backend
terminal vérifiable. Aucune règle ne dépend du nom d'un programme.

- Adresses : une région par 01/77 de chaque programme (tableaux `b_` séparés
  de cobc), par zone ALLOCATE, bloc EXTERNAL ou copie BY CONTENT, et un
  décalage, encodés en little endian dans les 8 octets du POINTER. Les vues
  liées à une adresse portent la fin de leur région : tout accès au-delà, par
  NULL ou après FREE/CANCEL est un arrêt nommé, distinct selon la cause.
- Ports : `cob_allocate` (NULL si la taille n'est pas dans 1..2147483646 ;
  `calloc` pour INITIALIZED à low-values, sinon `malloc` puis `cob_move` de
  la valeur TO), `cb_emit_allocate_identifier` (INITIALIZE WITH FILLER ALL TO
  VALUE THEN TO DEFAULT), `cob_free_alloc` (seule l'adresse exacte rendue est
  libérée, le pointeur passe alors à NULL), `cb_check_set_to`, comparaison
  `(int)(a-b)`, pointeur statique d'un article LINKAGE hors USING (persistant
  à travers CALL et CANCEL), libération des BASED au CANCEL, INITIALIZE à
  NULL (REPLACING n'y touche pas).
- Une zone `malloc` est suivie octet par octet : lire un octet jamais écrit
  est un arrêt nommé, puisque son contenu natif est indéterminé. Un ASSIGN
  vers un article sans adresse donne le statut 31 ; le message d'erreur
  nomme le fichier `('field with NULL address')`, comme `cob_field_to_string`.
- Arrêts nommés : DISPLAY d'une adresse non NULL, seule ou dans un groupe
  (ASLR), ordre de deux régions (disposition de l'éditeur de liens). Refus :
  pointeur BY VALUE (tronqué en int par cobc 3.2), PROGRAM-POINTER et
  FUNCTION-POINTER, ADDRESS OF PROGRAM, arithmétique et MOVE entre adresse et
  autre donnée, VALUE en LINKAGE hors BASED, CONTENT-OF/CONTENT-LENGTH.
- Preuves : fixtures `tests/fixtures/pointers.cob` (programme et
  sous-programme `keeper` : toutes les formes, statut 31, persistance au
  CANCEL) et `pointer_tables.cob` (OCCURS de pointeurs, INITIALIZE/REPLACING,
  REDEFINES d'un BASED, ADDRESS OF modifié) identiques au natif ;
  `tests/test_pointers.py` vérifie quatorze refus, le message de statut 31 et
  huit arrêts nommés.

Mesure : **1214 → 1225/3593 émissions acceptées**, testsuite **490 →
501/1135**, écart **403 → 392**, aucune acceptation refusée par cobc. Les onze
sources débloquées sont toutes de la testsuite : sept identiques avec codes
zéro (run_misc-027/097/098/099/127, run_extensions-007, run_file-020/prog2) ;
run_file-020/prog identique mais arrêté des deux côtés sur le statut 31
(codes 1/1, non compté comme réussite) ; data_pointer-001 arrêté nommément sur
le DISPLAY d'une adresse ; run_misc-115/prog et prog2 plantent en natif
(SIGSEGV, -11) quand Rust s'arrête nommément (70).

Exécution globale renouvelée : **74/84 identiques**, deux divergences (les
indices hors bornes du livre) et huit délais. CardDemo 8/8, zopeneditor 3/3,
cours 10/12, livre 53/61. Le passage de zopeneditor de 0/3 à 3/3 ne vient pas
de ce changement : le natif terminait par -11 à la fermeture implicite
(descripteur ASSIGN périmé après GOBACK, voir le 29 octobre) et termine
désormais à 16 comme Rust, sur six essais natifs successifs. Ce plantage
dépend de la mémoire native ; il peut réapparaître.
NIST statique : **451/458**, zéro erreur interne
(`build/coverage-nist-pointers-20261030.json`).

## Routines système d'octets — 30 octobre 2026

Le chantier vise dix des treize premiers écarts `CALL BY VALUE` de la
mesure précédente. SCREEN et POINTER demandent respectivement un backend
terminal vérifiable et un modèle d'adresses ; les routines d'octets offrent
un contrat natif isolable. Les noms reconnus sont les symboles de
`system.def`, sans sélection selon le nom d'un programme du corpus.

- Port de `cob_sys_and/or/nor/xor/imp/nimp/eq/not` et
  `cob_sys_toupper/tolower` de `common.c`. Douze noms sont reconnus, alias
  `CBL_TOUPPER/TOLOWER` et `C$TOUPPER/TOLOWER` compris. La fixture compare
  les 256 valeurs d'octet dans douze enregistrements : **3072 octets**,
  SHA256 `d420b7baf1c856087bc5d76514c10da561903bd4b3b036b231ec8406aa275515`,
  stdout `byte calls OK`, stderr vide et codes zéro dans les deux profils.
- Les opérations lisent et écrivent chaque octet dans l'ordre natif,
  avec alias vivants et chevauchements. BY CONTENT isole la copie. La
  longueur non positive ne déréférence aucun pointeur ; une longueur
  positive peut dépasser la PICTURE dans l'allocation adressée. Les accès
  hors allocation, pointeurs omis et écritures dans les littéraux restent
  des arrêts nommés, sans inventer de mémoire native.
- La longueur est un scalaire C int après les conversions de
  `output_call_by_value_args`. Taille implicite 8, SIZE 1/2/4/8, AUTO,
  DEFAULT et UNSIGNED suivent le profil **Linux x86_64**, bogues de signe
  compris. DISPLAY optimisé, SIGN explicite ou hérité, packed, COMP-6 et
  binaire ont leurs lecteurs distincts ; la table native `pack_to_bin`
  conserve son entrée anormale `0x2F → 25`. CALL n'insère pas de validation
  numérique dans le profil `-debug` non plus.
- Les **29 cas scalaires** sont comparés dans les deux profils ; sortie
  native SHA256 `4890e551b71bb9e9ac30ffe4c83e4fea159cd5b43ba54ff3edc0751285fec607`.
  Les autres tests couvrent les noms, chemins, NUL, avertissement des noms
  dynamiques avec espaces, priorité des programmes contenus, appel système
  littéral direct et absence de lecture d'un scalaire supplémentaire statique.
  **14 nouveaux tests** ; avec les appels existants, **22/22 réussis**.
  Journal : `/workspace/tooling/system-calls-targeted-final-20261030.log`.

Le support BY VALUE reste propre à l'ABI de ces routines. Les paramètres
formels ou ABI utilisateur/externe, CALL RETURNING, les résultats de FUNCTION
conservant une description non reproduite (ABS, MAX, MIN, MEDIAN, MEAN à un
argument) et les FUNCTION scalaires supplémentaires d'un appel littéral
restent refusés. Les positions/indices et les autres limites générales du
modèle numérique restent applicables. La casse utilise la libc dans une
locale C privée, comme LC_CTYPE après `cob_init`, sans GnuCOBOL à l'exécution.

Mesure complète renouvelée : **1203 → 1214/3593 émissions acceptées**,
testsuite **479 → 490/1135**, écart à cobc **414 → 403**, aucune acceptation
refusée par cobc. Dix cas correspondent aux routines ciblées ; le onzième
utilise la conversion de l'argument alphanumérique BY VALUE en BY CONTENT.
Les six autres corpus restent à 724/2458 ; leurs sources et données ne sont
pas modifiées. Exécution globale : **71/84 identiques**, cinq divergentes
et huit délais, avec les mêmes programmes dans chaque catégorie.
NIST statique : **451/458**, zéro erreur interne,
`build/coverage-nist-system-calls-20261030.json`. Les 413 exécutions NIST et
14 compilations seules restent une preuve historique.

Les onze sources nouvellement émises ont été compilées et exécutées avec
leurs dossiers et chemins d'appels : **10/10 programmes de routines
système identiques**, stdout/stderr, fichiers et codes zéro. La source
syntaxique restante appelle PROG2, absent du corpus : même arrêt nommé et
mêmes sorties des deux côtés, codes **1/1**. Elle n'est pas comptée comme
une exécution réussie. Rapport :
`build/system-calls-new-sources-verification-20261030.json`.
Le champ `match` du vérificateur compare aussi des codes non nuls égaux ;
le classement positif de cette campagne exige explicitement le code zéro.
Les onze scénarios avec entrées déclarées restent **11/11 identiques**,
dans leur dénominateur distinct :
`build/real-input-cases-system-calls-20261030.json`.

Suite Python complète : **491 tests découverts, 490 validés et un test PE
Windows ignoré**, aucun échec ni erreur (311 secondes). Journal :
`/workspace/tooling/system-calls-all-tests-20261030.log`.
Bilan avec empreintes : `build/system-calls-validation-20261030.json`.
L'empreinte du convertisseur est
`3f1a8f2de13b8af36d90232d28dec7bef715554fcb0c5d6882586734c3205305`.

## Capture des SOURCE de rapports — 29 octobre 2026

Le chantier corrige un écart d'exécution valide identifié pendant l'audit
des rapports du livre, avant les extensions de syntaxe les plus nombreuses.
Il porte `finalize_report`, `cb_field_dup`, `cb_emit_report_moves` et les
étiquettes `rwmove`/`rwfoot` de GnuCOBOL 3.2. Aucun nom de programme ni
valeur du corpus ne sélectionne le comportement du convertisseur.

- Une SOURCE indicée, modifiée par référence ou locale reçoit un champ
  temporaire distinct en WORKING-STORAGE. Son type DISPLAY signé ou PIC X,
  sa largeur et sa valeur initiale reprennent la description native ; il
  ne s'agit pas d'un cache du texte imprimé.
- GENERATE prépare les deux listes de MOVE avant la restauration des anciens
  contrôles ; TERMINATE prépare seulement la seconde. L'état persistant de
  parcours natif et l'ordre de première utilisation des rapports sont
  conservés, y compris les copies omises ou répétées avec un pied élémentaire.
  Les SOURCE simples et les compteurs restent lus à l'impression.
- Les positions des sous-chaînes SOURCE reproduisent le repli des constantes
  de `cb_build_binary_op`, le coefficient brut lu par `cb_get_int` et la
  troncature entière à chaque étape des calculs non repliés. Les dépassements
  constants, puissances non repliées et divisions par une constante zéro
  sont refusés ; la lecture générale des champs numériques et des indices
  conserve ses limites documentées.
- Le contre-exemple initial passe de fichiers différents à une comparaison
  identique : **38 octets**, SHA256
  `b9fd0e001f2a1289bc0818effd277d32a59cd5083898f01359e6d5b27b16bccd`,
  stdout/stderr vides et codes zéro. Rapports avant/après :
  `build/report-source-before-20261029.json` et
  `build/report-source-after-20261029.json`.
- **17 nouveaux tests** couvrent copies typées distinctes, sous-chaînes,
  LOCAL-STORAGE, contrôles directs, TERMINATE, état persistant entre rapports,
  profils par défaut/contrôlé et refus nommés. Le test des positions compare
  23 expressions dans chacun des deux profils. La fixture intégrée produit
  **218 octets** identiques (SHA256
  `6e7208ecb9a9636a1c07a76c66bc608ff9d840b04072dc16bf724889166b4aa2`).
  Avec les tests Report Writer existants : **26/26 réussis**.

Les copies de groupes et USAGE INDEX complexes, les PICTURE P initiales dont
la copie native est invalide et les contrôles locaux dont le C natif ne
compile pas restent refusés. LOCAL-STORAGE est aussi refusé dans le profil
cobol85, conformément à sa configuration native. USE BEFORE REPORTING
reste hors périmètre ; il faudrait reprendre les préparations à chaque
continuation native avant de l'accepter.

La mesure complète est renouvelée sur l'empreinte
`aa33eb3af3fe6cac36ae680e4ecd10a5fcc02dbb3c85913da9e51c2ff09340f9` :
**1203/3593 émissions acceptées**, écart à cobc 414, zéro acceptation
refusée par cobc et aucun changement de statut des sources. Exécution à
stdin vide : **71/84 identiques**, cinq divergentes et huit délais ; les
mêmes programmes restent dans chaque catégorie, sans erreur nouvelle.
NIST statique : **451/458**, zéro erreur interne, rapport
`build/coverage-nist-report-source-20261029.json`. Les 413 exécutions NIST
et 14 compilations seules restent une preuve historique, non renouvelée
par cette mesure statique.

Les onze scénarios d'entrée restent **11/11 identiques**, dans leur
dénominateur distinct : `build/real-input-cases-report-source-20261029.json`.
Suite Python complète : **477 tests découverts, 476 validés et un test PE
Windows ignoré**, sans échec ni erreur (315 secondes). Journal :
`/workspace/tooling/report-source-all-tests-20261029.log`. Bilan avec
empreintes et comparaison des sources inchangées :
`build/report-source-validation-20261029.json`.

## Capacité ODO et scénarios d'entrée — 29 octobre 2026

Le travail porte sur la fidélité d'exécution, en réponse aux écarts de la
mesure précédente. Les règles du convertisseur dépendent des déclarations
et du profil GnuCOBOL 3.2 ; les jeux d'entrée sont des données de validation.

- Une référence indexée `OCCURS DEPENDING ON` conserve la capacité déclarée
  sans contrôles ; le contrôleur n'est pas lu. Avec `--runtime-checks`,
  contrôleur et indice sont vérifiés. Les opérations sur la table entière,
  notamment SORT, gardent le nombre courant. Les accès au-delà de la
  capacité restent des arrêts nommés. Quatre nouveaux tests couvrent les
  deux profils, la longueur active et un SORT partiel.
- INTEGER-OF-DATE, INTEGER-OF-DAY, DATE-OF-INTEGER et DAY-OF-INTEGER
  renvoient zéro pour un argument hors domaine dans le modèle numérique
  existant, comme `cob_intr_*`. Les champs résultats gardent respectivement
  leurs 9, 9, 8 et 7 chiffres à l'affichage. Deux tests différentiels
  comparent **119 résultats**, dont limites, années bissextiles, fractions,
  DISPLAY, COMP-3, COMP-5 et profil contrôlé. Les limites d'arguments C int
  et le refus des lecteurs EXCEPTION-* sont conservés.
- `tools/verify_cases.py` traite un manifeste déclaratif, sans sélection
  selon un nom de source. Sources, stdin et dossiers d'entrée sont épinglés
  par empreinte, vérifiés avant et pendant la campagne. Six tests couvrent
  le passage des paramètres, les mutations, les oracles, les écarts et les
  délais. Les entrées de cinq programmes interactifs sont versionnées dans
  `measurements/real-input-cases.json` : **11/11 comparaisons identiques**,
  avec contrôle des sorties natives attendues et de stderr.
  Rapport : `build/real-input-cases-final-20261029.json`.
- Mesure finale sur le même convertisseur : **1203/3593 émissions
  acceptées**, écart à cobc 414, zéro acceptation refusée par cobc ;
  **71/84 exécutions identiques**, cinq divergentes et huit délais, contre
  70/84 avant correction. Le seul résultat modifié est Listing13-6,
  désormais identique (stdout, fichiers et code zéro). CardDemo 8/8,
  zopeneditor 0/3, cours 10/12 et livre **53/61**.
- NIST statique : **451/458 émissions**, zéro erreur interne, rapport
  `build/coverage-nist-odo-calendar-final-20261029.json`. Le runner complet
  NIST n'est pas relancé ; sa preuve historique distingue 413 exécutions
  comparées de 14 autres programmes seulement compilés.
- Suite Python complète : **460 tests découverts, 459 validés, un test PE
  Windows ignoré**, aucun échec ni erreur (296 secondes). Journal :
  `/workspace/tooling/odo-calendar-all-tests-final-20261029.log`.
  Bilan et empreintes : `build/odo-calendar-validation-final-20261029.json`.

Les onze scénarios sont une campagne distincte du protocole « stdin vide ».
Ils ne retirent aucun délai de son dénominateur. L'audit des huit délais a
identifié cinq programmes interactifs sans saisie et trois boucles infinies
des sources (CBL0015 et les exercices Listing12-3/4).

Les deux rapports du chapitre 18 ont un autre problème : leur dernier
enregistrement n'a pas de LF. Le comportement natif de LINE SEQUENTIAL,
avec COB_LS_SPLIT par défaut, produit un fragment qui mène à l'indice 70
dans une table de 50 éléments. `-debug` arrête aussi le natif. Les contrôles
sur copies de données et avec `COB_LS_SPLIT=0` montrent de plus un accès à
l'indice 165 après HIGH-VALUES dans Listing18-2. Les sources et données du
corpus restent inchangées ; les gardes Rust sont conservées. Preuves dans
`/workspace/tooling/report-bounds-20261029`.

## Paramètres ANY LENGTH — 29 octobre 2026

- `01 arg [PIC X] ANY LENGTH` transmet la taille réelle de l'argument,
  en conservant ses attributs alphanumériques. Portage de
  `validate_any_length_item`, `cb_validate_program_body` et
  `output_entry_function` de GnuCOBOL 3.2. Aucun nom de programme du corpus
  n'intervient dans le convertisseur.
- Mesure complète : **1195 → 1203/3593 émissions acceptées**, cobc 1617,
  **écart 422 → 414**, aucune acceptation refusée par cobc. Testsuite
  **471 → 479/1135** ; six autres corpus inchangés à 724/2458.
- Dix-sept nouveaux tests couvrent tailles de 1 à 1024 octets, champs,
  groupes, littéraux, stockage numérique, BY CONTENT depuis l'appelant,
  retransmission BY REFERENCE, refmod, MOVE, INSPECT, STRING/UNSTRING,
  JUSTIFIED, niveaux 88 et INITIALIZE. Les longueurs ne lisent pas
  l'adresse d'un paramètre omis. Le cache persiste après CANCEL/INITIAL et
  l'ordre natif ENTRY, bogue #902 compris, est conservé. Un accès dépassant
  l'argument s'arrête avec un diagnostic nommé.
- Suite Python complète : **448 tests découverts, 447 validés et un test
  PE Windows ignoré**, aucun échec ni erreur (290 secondes). Journal :
  `/workspace/tooling/any-length-all-tests-20261029.log`.
- Les quatre nouveaux programmes d'exécution (`run_misc-110/111` caller,
  `112/113` prog) correspondent à cobc : **4/4**, stdout, fichiers,
  stderr et codes zéro. Les deux callees sont couverts par ces appels.
  `syn_misc-055` et `syn_refmod-005` sont compilés en Rust et comme modules
  natifs, sans exécution. Les huit nouvelles sources sont inchangées ;
  rapport : `build/any-length-real-source-verification-20261029.json`.
- NIST statique : **451/458 émissions**, zéro erreur interne
  (`build/coverage-nist-any-length-20261029.json`). Le runner complet
  historique n'est pas relancé : 413 programmes exécutés/comparés et
  14 autres seulement compilés.
- Exécution globale des corpus renouvelée, avec stdin vide et fichiers du
  dossier source : **70/84 identiques**, 6 divergents et 8 délais.
  CardDemo 8/8, zopeneditor 0/3, cours 10/12, livre 52/61. Les trois
  exemples zopeneditor ont stdout et fichiers identiques mais le natif
  plante à la fermeture implicite (SIGSEGV, code -11), contre 16 en Rust.
  Le C généré conserve une adresse de descripteur ASSIGN local après
  GOBACK ; le crash est dans `cob_field_to_string` lors du CLOSE. Un essai
  natif séparé remplaçant GOBACK par STOP RUN termine à 16. Les sources du
  corpus restent intactes ; traces dans
  `/workspace/tooling/sam1-audit-20261029`.
  Les autres divergences sont Listing13-6 et les deux rapports du chapitre
  18, arrêtés sur indices hors bornes. Les délais concernent les entrées
  interactives ou boucles ; aucun de ces cas n'est compté identique.

ANY NUMERIC, ANY LENGTH GLOBAL, les PICTURE autres que X et les USAGE
autres que DISPLAY restent des refus nommés. INITIALIZE simple et la
validation des opérandes INSPECT gardent leur taille nominale d'un octet,
comme le C natif ; INITIALIZE REPLACING utilise la taille dynamique.

## Reprise main et famille NUMVAL — 28 octobre 2026

- Reprise sur `ab7c864`, intégrant les deux branches Claude. Baseline des
  sept corpus refaite : 1191/3593 émissions, cobc 1617, écart 426,
  aucune source acceptée que cobc refuse.
- Après NUMVAL-F et TEST-NUMVAL/TEST-NUMVAL-C/TEST-NUMVAL-F : **1195/3593**
  émissions acceptées, cobc 1617, **écart 422**, toujours zéro fausse
  acceptation dans les corpus. Testsuite 471/1135, autres corpus inchangés.
  Les fichiers `measurements/` et le tableau de CAP.md sont régénérés.
- **Dix tests ciblés réussis**, dont cinq différentiels : positions d'octets,
  38 chiffres, signes/CR/DB, monnaie multioctet, exposants, point/virgule,
  données binaires, groupes, sous-chaînes, REPOSITORY et affichage du résultat.
  Le signe lexical d'un nombre est distingué d'une opération comme `-(1)`.
- Les quatre programmes débloqués (`run_functions-077`, `108`, `109`, `110`)
  sont exécutés face à cobc, avec stdout, fichiers et codes identiques.
  Deux profils indépendants, **412 résultats**, correspondent également.
  Rapport : `build/numval-real-source-verification-20261028.json` (6/6).
- NIST statique inchangé : **451/458 émissions**, zéro erreur interne,
  `--std cobol85` (`build/coverage-nist-numval-reviewed-20261028.json`).
  Le runner complet n'est pas relancé pour cet incrément ; son historique
  distingue 413 exécutions comparées et 14 cas seulement compilés.
- Le compilateur natif utilisait une bibliothèque XML incompatible avec sa
  compilation. libxml2 2.12.10, construite depuis une archive GNOME vérifiée,
  corrige l'environnement du sysroot. Les tests de stderr et du module lancé
  par cobcrun repassent sans masquer d'avertissement.
- **431 tests Python découverts : 430 validés, un PE Windows ignoré.**
  L'exécution complète a rencontré deux erreurs de dépendance BDB (en-tête
  `db.h` absent). Après préparation du paquet de développement Berkeley DB
  5.3.28 vérifié et compilation de `build/bdb_dump`, les deux méthodes
  concernées sont rejouées avec succès, sans modifier le convertisseur :
  `EvaluateNativeTests.test_renames_larger_redefines_and_exponentiation` et
  `RealFormsNativeTests.test_fixtures_match_cobc`. Aucun échec restant.
  Bilan et empreintes des logs : `build/numval-unit-validation-20261028.json`.

Les résultats numériques calculés comme arguments de ces quatre fonctions
restent refusés : leur stockage peut être binaire, ou un littéral issu du
pliage de constantes natif. Les limites de 1024 décimales/4096 chiffres et le
refus des fonctions EXCEPTION-* sont conservés. La dernière mesure globale
d'exécution des corpus réels reste datée du 26 octobre, avec sa propre
empreinte ; les six comparaisons ci-dessus portent sur le nouvel incrément.

## Données invalides, ENTRY et modules — 25 octobre 2026

- Vérification NIST complète sur 1c167ab (données invalides sans contrôles,
  routine de comparaison de cobc) : **427/427 conformes, 9610 PASS, 0 FAIL,
  20 DELETED, 118 INSPECT** (`build/nist-verify-1c167ab.json`) ; émission
  451/458.
- Code réel (`tools/real_corpora.py --cobc --execute --record`, horloge
  figée à `2026/10/25 12:00:00.00`) : CardDemo 8/8 identiques, zopeneditor
  3/3, cours 9/11 (2 délais, boucles aussi infinies en natif), livre 45/52
  (Listing13-6 : indice hors bornes ; 6 délais de programmes interactifs).
- Nouvelles fixtures natives : `invalid_numeric_data`,
  `invalid_numeric_compare`, `invalid_numeric_move`, `entry_statement`,
  `entry_not_loaded` (avec `entry_calls/ENTSUB.cob`), `module_using`
  (exécuté par `cobcrun`), `length_of`.

## Exécution comparée sur code réel — 25 octobre 2026

`tools/real_corpora.py --cobc --execute --record` compile, exécute (stdin
vide, fichiers du dossier du programme, build release) et compare à cobc les
programmes acceptés : CardDemo 8/8 identiques, zopeneditor 3/3, cours 8/11
(1 divergent : COMP-3 invalide ; 2 boucles infinies aussi en natif), livre
41/52 (5 divergents, 6 délais de programmes interactifs). Nouvelles fixtures
natives : `call_not_found`, `call_not_found_dynamic`, `file_exit_messages`,
`divide_by_zero`, `line_sequential_split`, `line_sequential_bad_char`,
`non_ascii_literals`, `literal_concatenation`. Vérification NIST complète sur
566aece : 427/427, 9610 PASS, 0 FAIL, 20 DELETED, 118 INSPECT.

## Corpus réels après les premières étapes du cap — 25 octobre 2026

`tools/real_corpora.py --cobc --record` : **685/2458** acceptées (référence
230), cobc 738, écart 53, aucune source acceptée que cobc refuse. Nouvelles
preuves natives : `assign_names`, `assign_mapping` (variables DD_, $VAR,
COB_FILE_PATH), `group_condition_figurative`, `exit_perform`, en-têtes
facultatifs, `comp5`, `return_code` (CALL, CANCEL, code de sortie 44) et
`return_code_nested` (code 23). Vérification NIST complète sur le commit
7c4ab9b : 426/427, seul NC214M divergeait à cause de l'horloge figée du
23 octobre alors que la référence native a été régénérée le 25 ; l'outil lit
désormais l'horloge dans le journal de référence et NC214M passe.

## Testsuite GnuCOBOL comme septième corpus — 25 octobre 2026

`tools/extract_testsuite.py` extrait de l'archive GnuCOBOL 3.2 épinglée les
programmes des tests `AT_SETUP` dont la première compilation est `$COMPILE`
ou `$COMPILE_ONLY` sans option : 954 tests, 1135 sources (exclus : 298 avec
options, 87 sans compilation, 5 dont le programme n'est pas dans les
`AT_DATA`). Mesure (`tools/real_corpora.py --cobc --execute --record`) :
**970/3593 sources acceptées, cobc 1617, 0 acceptée que cobc refuse** ; la
testsuite seule 246/1135 (cobc 879). Les six autres corpus restent à 724/2458
et l'exécution comparée est inchangée (CardDemo 8/8, zopeneditor 3/3, cours
10/12, livre 52/61). Niveau 2 de preuve pour la testsuite (pas d'exécution
comparée : ses sorties attendues dépendent souvent d'options de test).

## Mesure de référence des corpus réels — 25 octobre 2026

Nouvelle boussole (CAP.md). `tools/real_corpora.py --cobc --record`, six corpus
publics épinglés, format `auto` (heuristique de cobol2rust d'alors, règle
de cobc côté cobc), copybooks de chaque corpus :
**230/2458 sources acceptées, cobc 738, écart 518** (sources que cobc accepte
et que cobol2rust refuse). CardDemo 0/44 (cobc 14), zopeneditor-sample 0/5
(cobc 5). 15 sources sont acceptées alors que cobc les refuse (IF vide,
indicateur invalide en colonne 7…) : à examiner comme défauts de rigueur.
Niveau 2 de preuve seulement. Fichiers : `measurements/real-corpora.json`.

## Fin de la première partie : couverture NIST du runner natif — 25 octobre 2026

- **369 tests découverts : 368 réussis, un test PE Windows ignoré.**
- **129/129 comparaisons locales conformes** ; nouvelles fixtures
  `external_files.cob`, `global_files.cob`, `initial_program.cob`,
  `line_sequential_variable.cob`, `report_no_page.cob`, `communication.cob`
  (`-std=cobol85`) et `stop_literal.cob` (SIGINT sur le caractère 03, vérifié
  par `test_runtime_registers`).
- NIST : **451/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **427/427 programmes principaux conformes** (dont 14 que report.pl compile
  seulement, et le module CM que la suite n'exécute pas) : **9610 PASS, 0 FAIL,
  20 DELETED, 118 INSPECT, total 9748**, exactement le bilan natif de
  `summary.txt`. Précision : 413 de ces programmes sont exécutés et comparés ;
  les 14 autres (12 que report.pl compile seulement, plus CM201M et CM303M du
  module CM jamais exécuté) sont seulement convertis et compilés. Rapports : `build/nist-verify-final.json`,
  `build/coverage-nist-final.json`. 13 programmes ajoutés : CM201M, CM303M,
  DB205A, DB304M, IC227A, IC233A, IC234A, IC401M, NC401M, OBNC1M, RW301M,
  RW302M, SQ401M ; DB103M est vérifié dans ses deux exécutions (COB_SET_DEBUG
  Y puis N, 42/42).
- Restent refusés : CM101M, CM102M, CM103M, CM104M, CM105M, CM202M, CM401M,
  que cobc 3.2 ne compile pas lui-même (erreurs de syntaxe CD, CD sans
  enregistrement).
- L'écart OBNC1M est levé : les deux programmes meurent de SIGINT après le
  STOP littéral et le REPORT est identique.

## Horloge, RANDOM, comparaisons littérales, SD à ODO — 25 octobre 2026

- **354 tests découverts : 352 réussis, un test PE Windows ignoré** ; l'échec
  restant (`test_p_scaling`) encodait l'ancien refus d'un article P comparé à un
  littéral alphanumérique, comparaison désormais émise et vérifiée en natif
  (fixture `mixed_literal_compare.cob`, cas d1-d5).
- **122/122 comparaisons locales conformes** ; nouvelles fixtures
  `clock_accept.cob` (ACCEPT FROM DATE/DAY/DAY-OF-WEEK/TIME sous
  COB_CURRENT_DATE, normalisation de mktime), `random_function.cob`
  (Mersenne Twister de GMP) et `mixed_literal_compare.cob`
  (`compare_field_literal` de cobc).
- NIST : **439/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **414/415 programmes principaux conformes** (9555 PASS, 0 FAIL, 16 DELETED,
  118 INSPECT) : `build/nist-verify-isolated.json`,
  `build/coverage-nist-isolated.json`. 5 programmes ajoutés : IF131A, IF403M,
  NC103A, NC214M (horloge figée au moment du log de référence), ST137A.
  Écart connu inchangé : OBNC1M (SIGINT).

## USE FOR DEBUGGING sur articles — 25 octobre 2026

- **347 tests découverts : 346 réussis, un test PE Windows ignoré.**
- **119/119 comparaisons locales conformes** ; nouvelle fixture
  `debugging_items.cob` (receveurs et ALL REFERENCES, IF débogué après ses
  branches, PERFORM VARYING/AFTER/UNTIL, GO TO DEPENDING, sous-scripts et
  qualificatifs, WRITE d'un enregistrement surveillé), en default et cobol85,
  commutateur de débogage actif ; MOVE sans `cob_check_numeric` vérifié avec
  `-fno-ec=data-incompatible`.
- NIST : **434/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **409/410 programmes principaux conformes** (9438 PASS, 0 FAIL, 16 DELETED,
  118 INSPECT) : `build/nist-verify-debug-items.json`,
  `build/coverage-nist-debug-items.json`. 4 programmes ajoutés : DB201A
  (avec `-fno-ec=data-incompatible` comme report.pl), DB202A, DB203A, DB303M.
  Écart connu inchangé : OBNC1M (SIGINT).

## Report Writer — 24 octobre 2026

- **341 tests découverts : 340 réussis, un test PE Windows ignoré.**
- **117/117 comparaisons locales conformes** ; nouvelle fixture
  `report_writer.cob` (REPORT/PAGE HEADING, DETAIL à plusieurs lignes,
  LINE absolue, PAGE/REPORT FOOTING, GENERATE du rapport, deux rapports, OPEN
  EXTEND) ; stdout et fichiers de rapport identiques à cobc.
- NIST : **430/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **405/406 programmes principaux conformes** (9343 PASS, 0 FAIL, 12 DELETED,
  104 INSPECT) : `build/nist-verify-report.json`,
  `build/coverage-nist-report.json`. 4 programmes ajoutés : RW101A, RW102A,
  RW103A, RW104A (fichiers de rapport XXXXX049 identiques à ceux de cobc).
  Écart connu inchangé : OBNC1M (SIGINT).

## OCCURS DEPENDING, symboles du module, programmes contenus — 24 octobre 2026

- **336 tests découverts : 335 réussis, un test PE Windows ignoré.**
- **116/116 comparaisons locales conformes** ; nouvelles fixtures
  `odo_internal.cob` (contrôleur interne, READ INTO, enregistrements FD
  variables), `decimal_comma.cob` (CURRENCY SIGN, DECIMAL-POINT IS COMMA),
  `literal_numeric_move.cob`, `initialize_replacing.cob`,
  `nested_programs.cob` (COMMON, GLOBAL, EXTERNAL, programme frère) et
  `current_date.cob` (format de CURRENT-DATE et WHEN-COMPILED).
- NIST : **426/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **401/402 programmes principaux conformes** (9303 PASS, 0 FAIL, 12 DELETED,
  104 INSPECT) : `build/nist-verify-odo.json`, `build/coverage-nist-odo.json`.
  19 programmes ajoutés : IC226A, IC228A, IC235A, IF107A, IF142A, IF401M,
  NC105A, NC107A, NC108M, NC223A, NC247A, RL210A, RL211A, SM103A, SQ111A,
  SQ214A, ST110A, ST123A, ST146A. Écart connu inchangé : OBNC1M (SIGINT ; libcob
  perd alors les tampons stdio des fichiers ouverts).

## LINAGE, ADVANCING et formes de préprocesseur — 24 octobre 2026

- **327 tests découverts : 326 réussis, un test PE Windows ignoré.**
- **110/110 comparaisons locales conformes** ; nouvelles fixtures
  `linage.cob` (FOOTING/TOP/BOTTOM littéraux et noms de données, AT/NOT AT
  END-OF-PAGE, ADVANCING identifiant, PAGE, FORMFEED, C01, 0 ligne, statut 57
  au changement de page, LINE SEQUENTIAL avec AFTER/BEFORE) et
  `preprocessing.cob` (REPLACE/REPLACE OFF, COPY OF bibliothèque, TEST BEFORE
  sans WITH, homonymes, I-O-CONTROL vide, SET à plusieurs groupes, NOT ON
  EXCEPTION après ADD) ; les trois fichiers LINAGE sont identiques à cobc.
- NIST : **407/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **382/383 programmes principaux conformes** (8325 PASS, 0 FAIL, 8 DELETED,
  104 INSPECT, ces derniers surtout dans les programmes d'impression LINAGE
  dont le REPORT est comparé octet à octet) : `build/nist-verify-linage.json`,
  `build/coverage-nist-linage.json`. 17 programmes ajoutés : IC222A, IF402M,
  NC114M, NC174A, NC201A, NC211A, SM207A, SM208A, SM401M, SQ101M, SQ201M,
  SQ207M, SQ208M, SQ209M, SQ210M, SQ212A, ST147A. Écart connu inchangé :
  OBNC1M (SIGINT).

## PROGRAM COLLATING SEQUENCE et fonctions mathématiques — 24 octobre 2026

- **311 tests découverts : 310 réussis, un test PE Windows ignoré.**
- **108/108 comparaisons locales conformes** ; nouvelles fixtures
  `collating_sequence.cob` (alphabet littéral THRU/ALSO, HIGH/LOW-VALUE,
  comparaisons et SORT selon la table) et `math_functions.cob` (SQRT, LOG,
  LOG10, EXP, trigonométrie, STANDARD-DEVIATION, PI, E).
- NIST : **390/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **365/366 programmes principaux conformes** (8066 PASS, 0 FAIL, 8 DELETED,
  14 INSPECT) : `build/nist-verify-math.json`, `build/coverage-nist-math.json`.
  15 programmes ajoutés : IF101A, IF103A, IF104A, IF106A, IF116A, IF117A,
  IF135A, IF136A, IF137A, IF139A, IX210A, IX214A, IX215A, NC215A, NC219A.
  Écart connu inchangé : OBNC1M (SIGINT).

## Organisation INDEXED — 24 octobre 2026

- **310 tests découverts : 309 réussis, un test PE Windows ignoré.**
- **106/106 comparaisons locales conformes** ; nouvelle fixture
  `indexed_files.cob` (clés alternées avec et sans doublons, START partiel,
  READ KEY, DELETE/REWRITE puis READ NEXT, statuts 21/22/23/43/46).
- NIST : **375/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **350/351 programmes principaux conformes** (7671 PASS, 0 FAIL, 8 DELETED,
  14 INSPECT) : `build/nist-verify-indexed.json`,
  `build/coverage-nist-indexed.json`. 39 programmes IX ajoutés.
- Les fichiers INDEXED sont comparés logiquement : `cobol2rust/bdb_dump.c`
  (libdb 5.3) liste les paires clé/donnée des btrees Berkeley DB de cobc,
  comparées à celles du format propre de cobol2rust. Les programmes chaînés
  reçoivent côté Rust les fichiers écrits par leurs prédécesseurs convertis.
  Écart connu inchangé : OBNC1M (SIGINT).

## DEBUGGING MODE et USE FOR DEBUGGING — 24 octobre 2026

- **310 tests découverts : 309 réussis, un test PE Windows ignoré.**
- **105/105 comparaisons locales conformes** ; nouvelle fixture
  `debugging_procedures.cob` (dialectes `default` et `cobol85`,
  `COB_SET_DEBUG=Y`, et sans le commutateur dans les tests).
- NIST : **336/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **311/312 programmes principaux conformes** (7275 PASS, 0 FAIL, 7 DELETED,
  14 INSPECT) : `build/nist-verify-debugging.json`,
  `build/coverage-nist-debugging.json`. Neuf programmes DB ajoutés (DB101A,
  DB102A, DB103M, DB104A, DB105A, DB204A, DB301M, DB302M, DB305M), avec
  `COB_SET_DEBUG` réglé comme report.pl (Y pour DB sauf DB102A). Écart connu
  inchangé : OBNC1M (SIGINT).

## ALTER, noms de procédure, dialecte cobol85 — 24 octobre 2026

- **307 tests découverts : 306 réussis, un test PE Windows ignoré.**
- **103/103 comparaisons locales conformes** ; nouvelles fixtures
  `alter_statement.cob` et `default_byte.cob` (vérifiées sous `default` et
  `-std=cobol85`), `procedure_names.cob`, `perform_backward_thru.cob`,
  `perform_times_count.cob`.
- NIST : **327/458** émissions acceptées (dont 24 sous-programmes `lib`) ;
  **302/303 programmes principaux conformes** (6980 PASS, 0 FAIL, 7 DELETED,
  1 INSPECT) : `build/nist-verify-alter.json`, `build/coverage-nist-alter.json`.
  L'original est désormais compilé avec les options de report.pl
  (`-std=cobol85 --debug`) et le Rust converti en dialecte cobol85 ; les
  entrées clavier `$raw_input` de report.pl sont fournies (NC302M, OBNC1M).
- Écart connu : OBNC1M lit le caractère 03 au 9ᵉ `STOP littéral` ; libcob
  lève SIGINT (processus tué), le Rust s'arrête par un arrêt nommé (code 70).
  Le REPORT est identique au journal natif ; seul le mode de fin diffère.

## Fonctions intrinsèques — 24 octobre 2026

- **305 tests découverts : 304 réussis, un test PE Windows ignoré.**
- **96/96 comparaisons locales conformes** ; nouvelle fixture
  `intrinsic_functions.cob`.
- NIST : **313/458** émissions acceptées, dont 24 sous-programmes `lib`
  désormais émis comme sous-programmes et vérifiés au travers de leurs
  appelants ; **289/289 programmes principaux conformes** (6608 PASS, 0 FAIL,
  7 DELETED, 1 INSPECT) : `build/nist-verify-intrinsics.json`,
  `build/coverage-nist-intrinsics.json`.

## COPY REPLACING — 24 octobre 2026

- **305 tests découverts : 304 réussis, un test PE Windows ignoré.**
- **95/95 comparaisons locales conformes** ; nouvelle fixture
  `copy_replacing.cob` (copybooks `replacing_items.cpy`, `replacing_code.cpy`).
- Séparateurs de COPY vérifiés contre cobc (`, COPY`, `COPY ;` acceptés ;
  `COPY "x";.` refusé).
- NIST : **262/458** ; **260/260 programmes acceptés conformes** (6156 PASS,
  0 FAIL) : `build/nist-verify-copy-replacing.json`. SM206A est vérifié avec
  `-fdebugging-line`, comme le compile report.pl.

## CORRESPONDING, troncature DISPLAY, dé-édition — 24 octobre 2026

- **305 tests découverts : 304 réussis, un test PE Windows ignoré.**
- **94/94 comparaisons locales conformes** ; nouvelles fixtures
  `corresponding.cob`, `display_truncation.cob`, `deediting.cob`.
- NIST : **256/458** ; **254/254 programmes acceptés conformes** (6104 PASS,
  0 FAIL) : `build/nist-verify-corresponding.json`.

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
