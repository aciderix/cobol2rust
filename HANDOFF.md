# Handoff — COBOL vers Rust

État au 23 octobre 2026, après livraison de la version **0.4.0**.

## Reprise cloud et objectif élargi

Dernière étape : `Parser.search_statement` (nœuds `search_test`/`search_step`/
`search_all`), USAGE INDEX (`Usage::Index` petit-boutiste), INSPECT
(`Parser.inspect_statement`, `storage_runtime::Inspect` = portage de
`strings.c` avec tampons `thread_local` persistants comme les statiques de
libcob ; accès hors tampon = arrêt nommé), `View::store_truncated`
(`cob_decimal_get_display` opt 0), EVALUATE désucré en conditions
(`Parser.evaluate_subject`/`evaluate_object` = `evaluate_test`), ELSE
imbriqués, 88 de groupe, SET mixte, littéraux signés dans `lex` (seulement
après un opérande entre parenthèses). NIST **229/458**, 227/227 conformes.

Dernière étape : `conditions.py` = `build_expr_shift/reduce/finish` de
typeck.c ; `Parser.expression_tokens` produit la liste `expr_tokens` de
parser.y (un signe collé à des chiffres est un littéral signé). STRING/UNSTRING
(`storage_runtime::StringInto`/`Unstring`, nœuds `string`/`unstring`) ; une
comparaison de délimiteur multiple qui lirait l'octet après la source (bogue
libcob) est un arrêt nommé. `reserved.py` = mots réservés de cobc.
NIST **233/458**, 231/231 conformes.

Dernière étape : `Parser.same_records` (SAME RECORD AREA via `redefines` du
premier enregistrement), `Parser.renames` + `apply_renames` (champ 66 ajouté
après `layout_fields`, `redefines` pour ne pas l'initialiser), REDEFINES 01
plus grand dans `layout.py`, `Number::power` (= cob_decimal_pow entier),
`Value::negative_zero`. NIST **251/458**, 249/249 conformes. Prochains :
CORRESPONDING, COPY REPLACING, DEBUGGING MODE, INDEXED, LINAGE.

Dernière étape : `Parser.corresponding_pairs` (Stmt `sequence` pour MOVE
CORR), troncature DISPLAY dans `View::assign`, `View::move_deedited`.
NIST **256/458**, 254/254 conformes.

Dernière étape : `load_source` repère COPY par `lex`, la fin par
`copy_replace.statement_end` (textes pplex, hors pseudo-texte) et applique
`copy_replace.apply`. `frontend.DEBUGGING_LINES` (= -fdebugging-line, option
`--debugging-lines`, `nist_verify.DEBUGGING_LINES`). NIST **262/458**,
260/260 conformes. Prochain : fonctions intrinsèques (module IF).

Dernière étape : `Parser.FUNCTIONS` / `function_call` (arité, LENGTH
littéral), `Emitter.function` → `runtime::intrinsic::*` (port d'intrinsic.c ;
les fonctions texte reçoivent les octets bruts de `Operand::of`). `coverage.py`
émet les sources USING comme sous-programmes. NIST **313/458**, 289/289
conformes. Prochains : ALTER, DEBUGGING MODE, INDEXED, LINAGE.

Dernière étape : ALTER (`Program.alters`, nœuds `alter_check`/`alter`/
`alter_zap`/`alter_save`/`alter_restore` dans `control.py`, état `alter` du
struct), `Parser.resolve_procedures` (règles `cb_ref`, noms internes uniques
des homonymes), `frontend.STD` / `--std cobol85` (`Program.segments`,
`Program.default_byte_init`), `tools/verify.py` lit `standards`,
`nist_verify` compile avec `RUNNER_FLAGS` et `RAW_INPUT`. NIST **327/458**,
302/303 conformes (OBNC1M : SIGINT). Prochain : DEBUGGING MODE (en cours).

Dernière étape : DEBUGGING MODE. `normalize` active les lignes D après le
motif pplex ; `Parser.debug_item` (DEBUG-ITEM ajouté après la mise en page),
`use_statement` rend les cibles, `debugging_program` (cb_validate_labels) ;
dans `control.py`, nœuds `debug_gate`, `debug_name`, `debug_contents`,
`debug_line`, `debug_resume` (fichiers : section avant le traitement du
statut), marques `fall_through` du frontend ; `runtime::debugging_mode`
(COB_SET_DEBUG). NIST **336/458**, 311/312. Prochain : INDEXED (en cours :
`tools/bdb_dump.c` pour comparer logiquement les fichiers BDB de cobc).

Dernière étape : INDEXED. `file_runtime::IndexedFile` (état `key`/`data`/
`last_readkey`/`last_dupno` de `struct indexed_file`), `Btree` (format
`cobol2rust-btree-1`), `FileSpec.record_key`/`alternate_keys` résolues en
(nom, décalage, taille, doublons), `Parser.index_key` (cob_findkey_attr),
`verification.indexed_contents` + `cobol2rust/bdb_dump.c`,
`nist_verify.rust_seed`. NIST **375/458**, 350/351. Prochain : PROGRAM
COLLATING SEQUENCE (en cours), LINAGE, fonctions trigonométriques.

Dernière étape : `Parser.special_names` (tables `mnemonics`, `switch_conditions`,
`alphabets`, `classes`, `symbolic`), `runtime::switch_on`/`set_switch`,
`display_error`, `Value::accept` = `cob_accept`. `verify --runtime-env` accepte
`COB_SWITCH_n` ; `nist_verify.RUNNER_ENV` = commutateurs de report.pl.
NIST **205/458**, 203/203 conformes.

Dernière étape : segments de SECTION acceptés (ALTER refusé, donc sans effet),
`CobolFile::close_unit` pour CLOSE REEL/UNIT/NO REWIND, OPEN NO REWIND/REVERSED
ignorés. NIST **198/458**, 196/196 conformes. Prochains blocages : INDEXED (34,
format BDB), SPECIAL-NAMES (11) et PROGRAM COLLATING (12), DEBUGGING MODE (12),
USAGE INDEX (7), COPY REPLACING (10), SAME RECORD AREA (6), FUNCTION (IF).

Dernière étape : SORT/MERGE. `FileSpec.sort` (SD), `Parser.sort_statement`,
nœuds `sort_init`/`sort_using`/`sort_giving`/`sort_close` et `return_sort` dans
`control.py` (procédures = nœuds `call` comme PERFORM), `file_runtime::SortFile`
(tri stable au premier RETURN comme `cob_file_sort_compare`). Restent refusés :
COLLATING SEQUENCE, fichiers USING/GIVING variables ou RELATIVE/INDEXED.

Dernière étape : clauses de données. SIGN = variantes `Usage::SignLeading`,
`SignLeadingSeparate`, `SignTrailingSeparate` et helpers `display_digits`/
`display_bytes` (seul '-' séparé est négatif ; un octet séparé autre que +/-
arrête). Le 4e élément de la méta `Value::Num` dit d'afficher le signe en fin.
SYNCHRONIZED : `layout.py` refuse tout cas où cobc insérerait du remplissage.
MOVE -0 vers un nombre signé refusé (cobc garde un zéro négatif).

Dernière étape : édition et comparaisons. `data_parser.edited_picture` refait
`cb_build_picture` (groupes de symboles identiques, CR/DB = C/D, chiffres et
échelle, taille) et `valid_char_order` la table de précédence de tree.c.
`storage_runtime::edit` est `cob_move_display_to_edited` ligne à ligne ; MOVE
édite les chiffres propres de l'émetteur (`move_edited`), un calcul passe par
les chiffres de l'image (modulo). `Kind::AlnumEdited` (valeur initiale éditée
sans VALUE, groupe émetteur brut, MOVE ALL refusé) et `Kind::Justified`.
`Emitter.folded_comparison` = `compare_field_literal` (tree.c), appliqué aux
conditions et aux WHEN d'EVALUATE. Un numérique édité se compare comme texte.

Dernière étape : NEXT SENTENCE, programmes frères, PICTURE P. Le parseur ajoute
un marqueur `sentence_end` à chaque point séparateur du niveau paragraphe ; le
graphe (construit à rebours) fait de NEXT SENTENCE un saut vers la suite du
prochain marqueur. `Program.siblings` : programmes après `END PROGRAM` dans le
même source, prioritaires sur le chemin d'appel (dlsym de l'exécutable par
libcob), non compilés en modules par `verify`. PICTURE P comme `cb_build_picture`
de tree.c : P final → échelle négative, P initial → V implicite, seuls les 9
stockés ; `Kind::Numeric.scale` et `Number::units` sont signés (`i32`). DISPLAY
suit `pretty_display_numeric`. Quirk reproduit : ADD/SUBTRACT d'un opérande
`cb_fits_int` sans ROUNDED ni SIZE ERROR passe par `cob_add_int`, qui tronque
l'opérande aux positions P du receveur (`ADD 15 TO S99P` ajoute 10, et rien si
le quotient est nul). P limité à DISPLAY ; MOVE texte↔P et comparaisons mixtes
refusés ou arrêtés.

Dernière étape : CALL/CANCEL/LINKAGE. `cli.run_unit` découvre les appelés
(`<nom>.CBL/.cob` du `--call-path`, PROGRAM-ID identique), `generate_unit` émet
une structure par programme et un `RunUnit` (instance persistante par appelé,
CANCEL = abandon de l'instance, donc fermeture des fichiers comme le
`P_cancel` de codegen.c). LINKAGE : `storage_runtime::rebind` sur la mémoire de
l'argument, `content_copy` pour BY CONTENT. Nom introuvable : ON EXCEPTION
seulement si `surely_absent` (majuscules, pas `SYSTEM`/`EXTFH`, pas de source
non convertie du chemin). Piège natif sondé : dans `ON EXCEPTION DISPLAY ..
NOT ON EXCEPTION ..`, GnuCOBOL donne NOT ON EXCEPTION au DISPLAY — refusé.
`verify` compile les appelés en `cobc -m` dans `modules/` (COB_LIBRARY_PATH) ;
`nist_verify` utilise `<module>/lib`, `coverage.py --call-path lib`.
NIST **126/458**, 124/124 programmes acceptés conformes.

Dernière étape : enregistrements variables, PERFORM VARYING AFTER, formes
lexicales et MOVE ALL. Limites comme `finalize_file` de cobc (clause élargie par
les 01, minimum par défaut au premier puis au plus petit) dans `FileSpec.record_min/
record_max/depending`. La zone FD (`fileN_area`, vue de `record_max` octets) sert
aux lectures ; les 01 alternatifs peuvent être plus grands (layout étend la zone).
Écriture : taille = DEPENDING ON plafonné à la taille de l'enregistrement nommé,
44 hors limites. SEQUENTIAL variable : en-tête 4 octets (u16 big endian + 0 0,
COB_VARSEQ_FORMAT 0). RELATIVE : `size_t` = taille, données `record_max`.
Lecture : DEPENDING ON = taille lue ; READ INTO déplace la taille lue (préfixe).
REWRITE SEQUENTIAL : 44 si la taille lue diffère (remplace l'ancien arrêt).
LINE SEQUENTIAL variable reste refusé. PERFORM VARYING ... AFTER suit
`output_perform_until` (réinitialisation du niveau suivant en tête de boucle).
Mots commençant par un chiffre, littéraux `.5` (normalisés à l'émission par
`numeric_text`), PIC `V9(n)`, PIC A, ASCENDING KEY, MOVE ALL et SET entier TO
index ajoutés. NIST **115/458** ; nouvelles sources toutes conformes.

Dernière étape : fichiers RELATIVE (`file_runtime::RelativeFile`). Format
GnuCOBOL 3.2 Linux x86-64 : emplacement = `size_t` little endian (8 octets,
taille d'enregistrement, 0 = vide, trou lu comme vide) puis `record_max`
octets. Chaque méthode suit `cob_open`/`cob_read`/`cob_read_next`/`cob_write`/
`cob_rewrite`/`cob_delete`/`cob_start` puis `relative_*` de `fileio.c`, y compris
leurs écarts : REWRITE direct d'un emplacement vide écrit les données, garde
la taille 0 et rend 00 ; DELETE d'un emplacement déjà vide rend 00 ; START en
échec arme la fin de fichier (READ NEXT suivant 46) ; READ NEXT met la clé à
0 puis rend 14 si le numéro dépasse sa PICTURE ; OPTIONAL absent : READ NEXT
10 puis 46, READ direct 10 puis 23 (`flag_first_read` = 2 à l'OPEN).
Choix de lecture comme `cb_emit_read` : NEXT, accès SEQUENTIAL ou DYNAMIC avec
AT END lisent séquentiellement, sinon par RELATIVE KEY. AT END couvre toute la
classe 1x, INVALID KEY la 2x (`file_status` reçoit les deux indicateurs).
RELATIVE KEY : entier non signé de 9 chiffres au plus hors de l'enregistrement.
START : =, >, NOT < (>= et LT/LE refusés). SELECT suit `parser.y` : `RELATIVE
[KEY]`, `[FILE] STATUS` qualifié, organisation sans ORGANIZATION, RESERVE ignoré,
statut VSAM refusé. Deux SELECT d'un même chemin sont permis ; leur ouverture
simultanée s'arrête (`claim_path`). NIST **95/458** ; les 29 nouvelles sources
RELATIVE/SELECT sont conformes (762 PASS, 4 DELETED natifs). Prochains :
RECORD VARYING, NEXT SENTENCE, noms commençant par un chiffre, INDEXED.

Dernière étape : OPEN I-O et REWRITE SEQUENTIAL. `State::InputOutput(File)`
lit sans tampon pour que REWRITE recule exactement d'un enregistrement
(`sequential_rewrite`). Mesures natives : I-O absent 35 ; OPTIONAL absent 05 et
fichier créé vide ; REWRITE sans READ réussi 43 (aussi après un REWRITE, un
WRITE ou une fin de fichier) ; WRITE en I-O 48 ; REWRITE hors I-O 49. Un READ 0x
arme REWRITE (`read_done`). LINE SEQUENTIAL en I-O/REWRITE est refusé : la
réécriture native écrase des lignes de longueur différente. REWRITE après un
enregistrement partiel s'arrête. NIST **66/458**, **66/66 conformes**
(539 PASS, 1 INSPECT) : `build/nist-verify-66.json`.

Dernière étape : DECLARATIVES, READ souple et CLOSE WITH LOCK.
`USE AFTER [STANDARD] {ERROR|EXCEPTION} PROCEDURE [ON] {fichiers|INPUT|OUTPUT|
I-O|EXTEND}` est analysé dans `use_statement` ; `Program.file_declaratives`,
`mode_declaratives` et `main_block` (exécution après END DECLARATIVES).
`control.py` transforme OPEN/CLOSE/WRITE en nœuds `io` et ajoute aux READ la
cible déclarative : comme `output_ferror_stmt`/`output_file_error` de cobc,
tout statut 1x..9x non pris par AT END appelle la section USE du fichier, sinon
celle du dernier mode d'OPEN (`last_open_mode`, conservé par un 41, pris sur
toute autre tentative), comme un PERFORM, puis reprend après l'instruction.
Un 46 après fin de fichier n'est pas AT END. Sans FILE STATUS, une exception
sans gestionnaire reste fatale. OPEN/CLOSE à plusieurs fichiers sont découpés,
chaque fichier ayant son contrôle (instructions implicites de cobc).
USE GLOBAL et USE FOR DEBUGGING restent refusés.

READ accepte `[NEXT] [RECORD]`, `[AT] END` et `NOT [AT] END` (scanner cobc).
CLOSE WITH LOCK : OPEN suivant 38, READ 47 ; un second CLOSE d'un fichier
verrouillé suit un chemin anormal de libcob (avertissement, 00) et s'arrête
en Rust. NO REWIND, REEL et UNIT restent refusés.
NIST : **59/458**, les 29 nouvelles sources conformes (117 PASS natifs). Prochain :
OPEN I-O + REWRITE séquentiel (8), puis RELATIVE (32) et INDEXED (26).

Dernière étape : receveurs multiples, groupes et configuration documentaire.
**Bug silencieux corrigé** : `ADD 1 TO A, B.` ne gardait que A et faisait de
`B.` un en-tête de paragraphe (NC245A). Les verbes arithmétiques lisent
désormais tous leurs receveurs avec ROUNDED propre (`Stmt("compute")` et
`Stmt("arithmetic")` portent `(partagé, [(réf, expr, rounded)])`). Mesures
natives : un opérande unique est relu après chaque stockage (`ADD X TO X Y`
donne Y=12), plusieurs opérandes sont sommés une fois, COMPUTE/GIVING évaluent
une fois, les indices du receveur sont évalués à son stockage, SIZE ERROR garde
seulement le receveur fautif. Un nom de paragraphe/section homonyme d'une donnée,
condition, fichier ou index est refusé (`procedure_name_check`).

FILE STATUS accepte un groupe de 2 octets (octets bruts, comme GnuCOBOL ; autres
tailles refusées nativement). VALUE de groupe : littéral alphanumérique, ZERO ou
SPACE, appliqué après les feuilles sur toutes les occurrences ; VALUE subordonné,
numérique, ALL, HIGH-VALUES, REDEFINES/FD et ODO refusés. USAGE de groupe hérité
par les feuilles sans USAGE ; un USAGE explicite subordonné l'emporte (natif).
MEMORY SIZE, SEGMENT-LIMIT 1..49, MULTIPLE FILE [TAPE], SAME [SORT|SORT-MERGE]
AREA sont ignorés comme dans `parser.y` ; SAME RECORD AREA, RERUN, PROGRAM
COLLATING SEQUENCE et WITH DEBUGGING MODE restent refusés. Lignes `D`/`d` :
commentaires, sauf si le texte contient DEBUGGING MODE (refus explicite).

`tools/nist_verify.py` rejoue les prédécesseurs natifs du runner (tout depuis le
dernier `.CBL`, `XXXXX*` effacés avant chaque `.CBL`), compare GnuCOBOL/Rust et
exige un REPORT identique au journal natif ; les `comp_only` de `report.pl`
sont seulement compilés. `tools/nist_native_reference.sh` régénère la référence
(lancée en arrière-plan par le hook). NIST : **30/458**, et **30/30** conformes
(401 PASS, 1 INSPECT SM106A) : `build/nist-verify-30.json`. Prochain blocage :
DECLARATIVES `USE AFTER ERROR` (23), puis RELATIVE (32), INDEXED (26) et les
fonctions intrinsèques du module IF.

Dernière étape : FD DATA RECORDS et MOVE numérique tronquant. `file_parser.py`
garde `DATA RECORD(S) [IS|ARE] nom...` en métadonnée `data_records` : GnuCOBOL
n'en résout pas les noms (même inconnus) et la clause est sans effet. La liste
s'arrête aux mots réservés FD (`FD_WORDS`) ; doublon et liste vide sont refusés.

Le MOVE numérique vers numérique passe par `View.move_number` : troncature des
décimales, magnitude modulo 10^chiffres (binaire compris), valeur absolue vers
non signé, zéro négatif conservé en DISPLAY (`00p`) et COMP-3 (`D`), pas en
binaire. COMPUTE/ADD sans SIZE ERROR gardent l'arrêt 70 ; ne pas les faire
passer par ce chemin sans essai natif. Une source index reste stricte.

Piège natif : vers COMP-3, cobc utilise `cob_set_packed_int` pour une source
binaire dont la valeur mise à l'échelle tient sur 32 bits, et pour un littéral
entier tenant dans un int avec chiffres + échelle ≤ 9. Ce chemin remplit tous
les quartets physiques : `1234 → PIC 99 COMP-3` donne `234F`. Les relectures
natives sont ensuite incohérentes (DISPLAY/comparaison voient 34, MOVE COMP-3
vers COMP-3 voit 234). Le littéral est donc refusé à l'émission
(`check_packed_literal_move`) et la source binaire arrêtée à l'exécution
(`move_binary_to_packed`) lorsque le quartet de tête recevrait un chiffre non nul.

NIST : **20/458** (`build/coverage-nist-data-records.json`). SM102A, SM104A,
SM204A, SQ128A, ST103A, ST104A, ST115A et ST121A ont des REPORT identiques au
runner natif officiel (44 PASS). Les `.SUB` lisent les fichiers de leurs
producteurs (`*HEADER,COBOL,<producteur>,SUBPRG,<sub>` dans newcob.val),
exécutés en GnuCOBOL dans l'ordre du runner. Priorités suivantes : RELATIVE
(32), INDEXED (26), FILE STATUS de groupe (25), VALUE/USAGE de groupe (24).

Environnement Linux du 23 octobre 2026 (Ubuntu 24.04) : GnuCOBOL 3.2.0
compilé depuis les sources GNU signées avec BDB (`tools/install_gnucobol.sh`).
La suite découvre **201 tests : 200 réussis, un PE Windows ignoré** ; les
comparaisons COBOL/Rust ne sont plus ignorées. NIST est reproduit à **12/458**
(`build/coverage-nist-baseline.json`). Le site web GnuCOBOL renvoyant 403,
`prepare_nist.py` bascule sur le miroir SourceForge, SHA256 inchangé.
Le runner NIST natif donne 9610 PASS et 0 FAIL sur 9748 tests
(`.tools/nist-native-gnucobol-3.2`). `tools/fetch_corpora.py` ajoute six dépôts
publics épinglés et la testsuite GnuCOBOL 3.2. Acceptation statique initiale :
beg-cobol 16/113, proleap 43/759, che4z 55/1504, carddemo 0/44,
cobol-programming-course 0/7, zopeneditor 0/5 (`build/coverage-<corpus>.json`).
Les 1346 cas `.at` GnuCOBOL ne sont pas encore extraits en programmes autonomes.

Dernière étape : séparateurs virgule/point-virgule et entrées documentaires
d'Identification. Le lexer conserve une PICTURE comme un mot contigu, avec ses
virgules d'édition ; il sépare un seul point/virgule terminal et s'arrête aussi
sur `;` ou `*>`. Ne pas reconstruire l'image en recollant des tokens espacés.
Les séparateurs ordinaires ne terminent pas une phrase ; dans les parenthèses,
ils restent des délimiteurs pour ne pas transformer `table(1,+2)` en `table(1+2)`.
Une séquence contiguë du même séparateur forme un seul token. Les listes mixtes
plus larges restent refusées. PIC/PICTURE sont refusés comme noms ordinaires,
mais restent permis comme noms COPY non cités.

`DocumentaryFilter` dans `documentary.py` est appelé par `normalize`, avant
`fixed_fragment`, lex et COPY. AUTHOR, INSTALLATION, DATE-WRITTEN, DATE-COMPILED,
SECURITY et REMARKS doivent commencer leur ligne physique avec un point.
En fixe, la prose de zone B continue jusqu'à la prochaine ligne normale de zone A,
réanalysée ; en libre, seule la ligne d'en-tête est masquée. Les guillemets ouverts
et COPY documentaires ne deviennent pas du code. Un littéral ordinaire déjà
ouvert garde ses contrôles, et `-` documentaire reste explicitement refusé.
Une directive séparée reste active : FREE termine la prose fixe, FIXED la conserve.
Ne pas faire passer le source brut directement au Parser pour ce filtrage :
il attend le source normalisé, comme auparavant.

La ligne COPY garde sa validation propre et refuse les virgules/points-virgules
supplémentaires non cités. Les noms cités avec ponctuation et les commentaires
finaux sont préservés. Ne pas déduire la grammaire du préprocesseur de celle du
lexer ordinaire.

Validation après revue : **200 tests découverts, 199 réussis, un PE Windows ignoré**
(`/workspace/tooling/separators-documentary-reviewed-tests.log`). Les 37 ajouts
couvrent notamment les limites PICTURE/commentaires, guillemets, COPY, positions,
formats, portée de phrase et sous-scripts avec signe unaire.

NIST statique : **12/458 émissions acceptées**, 16 blocages au prétraitement,
430 à l'analyse, aucun à l'émission et zéro erreur interne
(`build/coverage-nist-separators-documentary-reviewed.json`). Les premiers
diagnostics/statuts changent pour 94 sources ; 57 passent du prétraitement à
l'analyse. NC246A et SQ202A sont les deux nouvelles sources acceptées.

Les **51/51 comparaisons locales** passent
(`build/verification-separators-documentary.json`). NC246A et SQ202A ont aussi
**2/2 comparaisons natives conformes**, stdout identique, codes nuls et fichiers
identiques aux références indépendantes. Leurs bilans donnent **49 + 1 = 50 PASS**,
sans FAIL/DELETED/INSPECT (`build/nist-separators-documentary-verification.json`).
SQ202A crée et relit 750 records de 120 octets ; son XXXXX001 fait 90000 octets,
SHA256 `c3a5a8f0b77c2ddb7ee6f59ae960fb0beb2b39e82f99ab1b101fa94c49e9c415`.
Les références natives et leur provenance sont conservées dans
`/workspace/tooling/separator-nist-probes`. Aucun changement des sources NIST
ni jeu d'entrée externe n'a été nécessaire. Cela ne remplace pas le runner NIST
complet. Priorités désormais : FD DATA RECORD (36 premiers diagnostics),
RELATIVE (32), INDEXED (26), FILE STATUS de groupe (25), VALUE/USAGE de groupe (24).

Étape précédente : comparaisons mixtes et MOVE depuis du texte. Les comparaisons
conservent le contexte AST dans `comparison_order`, sans assouplir `Value.compare`.
Un champ numérique DISPLAY/COMP/COMP-3, même avec V, est comparé à un champ PIC X,
groupe ou refmod par ses chiffres de magnitude sur la largeur PICTURE, sans
signe ni point. Les littéraux numériques non signés gardent leurs chiffres
lexicaux ; ZERO remplit la largeur texte. Un littéral texte vide représente un
espace dans ce contexte. DISPLAY non signé invalide est comparé brut ; signé
invalide garde l'arrêt conservateur nommé.

Attention : GnuCOBOL peut replier une comparaison directe contre un littéral
texte selon la PICTURE, même après MOVE. Garde actuelle : champ entier et
littéral ASCII uniquement numérique de même largeur. Les autres littéraux
doivent passer par PIC X pour être comparés. Index, signes numériques explicites,
expressions arithmétiques et catégories mixtes EVALUATE/88 restent refusés.
La régression native DIRECT:FALSE/FIELD:TRUE préserve ce contre-exemple.

`assign_text_move` gère les sources PIC X/refmod vers Numeric ou edited, les
littéraux texte vers edited seulement, et les groupes source par copie brute.
La lecture suit un buffer natif : DISPLAY à sa capacité/échelle, autres usages
et edited à 76 positions dont 38 fractionnaires. Les caractères invalides ne
sont examinés que jusqu'au remplissage du buffer ; l'excès entier est sauté
avant validation. DISPLAY conserve le signe initial, même si les chiffres
deviennent zéro ; le chemin indirect l'efface si invalide. Les zéros négatifs
gardent overpunch p ou nibble D en stockage, même si l'affichage vaut +0000.

`Expr.figurative_space` distingue SPACE, refusé vers edited, du littéral " ",
accepté. La déédition, les calculs sur/vers texte, VALUE texte vers numérique,
le texte vers index et les littéraux texte vers Numeric ordinaire restent
refusés. Ne pas promouvoir ces chemins via `num()` ou `View.assign`.
Voir `tests/test_mixed_types.py` et `tests/fixtures/mixed_types.cob`.

Validation : **163 tests découverts, 162 réussis et un PE Windows ignoré**,
**49/49 comparaisons locales conformes** (`build/verification-mixed-types.json`).
La suite ciblée de 22 tests passe aussi après le correctif du littéral texte
vide. Le fichier attendu de la fixture a 13 octets (`MATCH\n-12.30\n`), SHA256
`3513c1fc64a7b34e0ed21ae9a38eba43bcd1cec141594786c5a81054fb00267a`.

NIST : **10/458 émissions acceptées**, 73 blocages au prétraitement, 375 à
l'analyse, aucun blocage d'émission et zéro erreur interne
(`build/coverage-nist-mixed-types-final.json`). NC132A et ST126A sont désormais
acceptés. NC132A, ST107A et ST126A ont **3/3 comparaisons natives conformes**,
codes nuls et fichiers identiques aux références indépendantes. Leurs bilans
déclarent **25 + 6 + 18 = 49 PASS**, sans FAIL/DELETED/INSPECT
(`build/nist-mixed-types-verification.json`).

Les données ST107A/ST126A ont finalement été produites avec les générateurs
officiels ST106A/ST125A en GnuCOBOL, sous
`/workspace/tooling/nist-mixed-probes/seed-st107` et `seed-st126`. Les fichiers
XXXXX001/2/3 font chacun 243 octets, neuf records de 27 octets, SHA256
`50fbb785d0857f495d756ba1632e236ec9115aac8ab413570871c8db2fe05cf7`.
Les mentions historiques ci-dessous de données absentes sont donc levées.
Ne pas compter les deux PASS des générateurs natifs comme support Rust de SORT.
Voir `tools/README.md` pour reproduire la génération et la comparaison.

Étape précédente : MOVE numérique vers texte des rapports CCVS. Le frontend
distingue désormais `Stmt("move")` de `assign` arithmétique et conserve
`Expr.figurative_zero`. L'émission convertit chaque source juste avant le
récepteur, à partir d'une vue résolue une fois ; ne pas prendre de snapshot
unique des octets avant tous les récepteurs, cela casserait les alias.

Un entier DISPLAY/COMP/COMP-3/index vers PIC X ou refmod envoie sa magnitude
sur la largeur PICTURE, sans signe ; le récepteur tronque à droite ou complète
d'espaces. COMP/COMP-3/index font un modulo de capacité après décodage.
Une destination groupe reçoit au contraire le stockage brut, signe overpunch,
COMP/COMP-3 et source V compris. Un champ V vers PIC X ou refmod est refusé
comme dans le profil GnuCOBOL par défaut. Index vers groupe reste refusé : son
stockage natif diffère du profil interne big-endian des index synthétiques.

Les littéraux préservent leurs chiffres lexicaux sans signe ni point
(`-0012.30` envoie `001230`). ZERO/ZEROS/ZEROES remplissent toute la taille
active du récepteur ; le littéral 0 est suivi d'espaces. Les calculs vers PIC X,
texte vers nombre, déédition et comparaisons mixtes restent refusés.
DISPLAY non signé invalide est copié brut vers PIC X ; signé invalide s'arrête
avec un diagnostic nommé, car GnuCOBOL peut normaliser le signe en modifiant
la source. Les helpers `numeric_move_text` ne changent pas `View.assign` ou
`Value.bytes`, ni les règles d'initialisation VALUE.

Les **17 tests ciblés** passent : règles de largeur/signe, groupes bruts,
littéraux/ZERO, modulo binaire/index, alias, source indexée résolue une fois,
rapport avec octets attendus et refus explicites. Voir
`tests/test_numeric_move.py` et `tests/fixtures/numeric_move_report.cob`.

Validation complète : **141 tests découverts, 140 réussis et un PE Windows
ignoré** ; **48/48 comparaisons locales conformes**
(`build/verification-numeric-move.json`). Le fichier attendu de la nouvelle
fixture a 28 octets, SHA256
`6a4189b0879af9bba617f35fa87b29897c19d48db58e7d8afd82c7d45c586f60`.

La mesure NIST passe à **8/458 émissions acceptées**, avec 73 blocages au
prétraitement, 375 à l'analyse, 2 à l'émission et aucune erreur interne
(`build/coverage-nist-numeric-move.json`). NC127A, NC136A, NC137A, SM106A,
SM107A et ST107A rejoignent NC110M et SM301M. NC132A atteint maintenant une
comparaison nombre/texte, ST126A un transfert texte vers nombre. Ces deux
opérations restent refusées. La mesure est statique ; ST107A requiert en outre
des données de tri externes pour une exécution pertinente.

Les **5 nouveaux programmes autonomes** NC127A, NC136A, NC137A, SM106A et
SM107A ont aussi une comparaison native réussie, codes nuls, stdout et fichiers
identiques (`build/nist-numeric-move-verification.json`). Leurs REPORT ont les
mêmes empreintes qu'une exécution native indépendante. Bilans : 2, 8, 8, 0 et
200 PASS automatiques, soit **218 réussites, aucun FAIL/DELETED et une
inspection requise dans SM106A**. Ne pas transformer cette inspection en PASS.
Ce contrôle des bilans ne remplace pas le runner NIST complet. ST107A attend
`XXXXX001` (SEQUENTIAL, 27 octets par record) généré par ST106A ; données absentes,
donc pas d'exécution ni de jeu fabriqué.

Étape précédente : GO TO et contrôle explicite des retours PERFORM. Le nouveau
`control.py` abaisse tous les contrôles en graphe avec continuations ;
`emitter.py` génère une boucle `pc` et une pile
`PerformFrame { through, return_pc }`, en remplacement des appels de méthodes
Rust par bloc. Un GO ne dépile aucun cadre : une fin de PERFORM peut être
atteinte plus tard, après un détour hors de sa plage. Chaque point de retour
compare seulement le sommet et dépile un seul cadre correspondant.

Les fins de paragraphe et de section sont distinctes, même en fin du dernier
paragraphe. EXIT SECTION est maintenant accepté dans une section explicite et
saute directement à sa borne, en contournant le retour d'un éventuel PERFORM
de paragraphe. EXIT PARAGRAPH vise sa propre borne ; EXIT nu reste sans effet.
GO accepte TO facultatif, cibles section/paragraphe et DEPENDING [ON] avec
contrôleur entier de neuf chiffres au plus (table subscriptée ou index implicite
inclus). Les valeurs hors de 1..N poursuivent sans saut. Les décimaux et grandes
largeurs restent refusés : GnuCOBOL a des conversions dépendantes du stockage,
dont une réduction à 32 bits de grands DISPLAY/COMP-3.

Autre règle native importante : le compteur TIMES est unique par site syntaxique
et non sauvegardé par un appel PERFORM. Une réentrée récursive au même site
écrase son compteur externe. Le nouveau moteur reproduit cet effet ; les sites
distincts gardent des compteurs distincts. IF/EVALUATE, READ, SIZE ERROR et les
boucles inline ont des continuations explicites, que GO peut quitter.

Les **37 tests ciblés** passent (21 GO et 16 sections). Les preuves natives
conservent les cadres dormants, comparaisons au sommet, deux points de retour,
sauts depuis handlers/boucles, compteurs récursifs et contrôleurs calculés.
Les variantes ALTER/GO sans cible, EXIT SECTION hors section explicite,
EXIT PERFORM/CYCLE, qualifications/homonymes et sections segmentées restent
refusées. Voir `tests/test_goto.py` et `tests/fixtures/goto_flow.cob`.

La suite complète découvre **124 tests : 123 réussis, un PE Windows ignoré**.
Le corpus local donne **47/47 comparaisons conformes**
(`build/verification-goto.json`), y compris la nouvelle fixture de sauts.

NIST : **2/458 émissions acceptées**, 73 blocages au prétraitement, 375 à
l'analyse, 8 à l'émission et aucune erreur interne
(`build/coverage-nist-goto.json`). Les premiers diagnostics/statuts changent
pour 47 sources. GO TO ne bloque plus en premier ; les huit nouveaux blocages
d'émission sont des conversions numérique/texte CCVS-E-4 non modélisées.
NC110M rejoint SM301M parmi les sources acceptées. Cette mesure reste statique.
NC110M a aussi une comparaison native réussie, codes nuls et octets identiques
(`build/nist-nc110m-verification.json`). Sa ligne PASS est présente, sa ligne
FAIL absente et sa fin de test atteinte : cette preuve GO/PERFORM ciblée ne
constitue pas une exécution complète du runner de conformité NIST.

Étape précédente (21 octobre) : sections de procédure et PERFORM. Le frontend conserve
l'entrée anonyme, chaque préambule de section (même vide) et les paragraphes
dans `Program.blocks`, avec des plages semi-ouvertes dans `Program.sections`.
`entry` et `paragraphs` partagent toujours les listes des corps correspondants.
`procedure_range` résout un paragraphe seul ou toute une section. THRU/THROUGH
accepte des bornes mixtes, y compris un paragraphe jusqu'à sa propre section.

L'émission utilise une méthode par bloc et `perform_range`, avec retours
imbriqués/récursifs et enchaînement séquentiel. EXIT PARAGRAPH termine seulement
le bloc courant ; une section continue ensuite. EXIT nu est désormais sans
effet. STOP RUN/GOBACK restent propagés. Le rapport CLI expose les sections et
blocs sans introduire de faux noms dans la liste des paragraphes.

Les 16 tests ciblés passent, dont 8 comparaisons Rust/GnuCOBOL et une preuve
native du refus EXIT SECTION. La suite complète découvre **103 tests : 102
réussis, un PE Windows ignoré**. Le corpus local donne **46/46 comparaisons
conformes** (`build/verification-sections.json`). Sous GnuCOBOL, EXIT SECTION dans un paragraphe
appelé peut dépasser le retour de son PERFORM et poursuivre dans la section
suivante. Ne pas le traduire par un retour Rust ou par un saut qui dépilerait
les appels. Il faudra modéliser les positions de contrôle et la pile des
PERFORM pour couvrir ces transferts. EXIT PERFORM, qualifications/homonymes
de procédures et sections à segments numérotés restent refusés. Une cible de
procédure homonyme d'une donnée reste aussi hors profil du parser actuel.

La mesure `build/coverage-nist-sections.json` conserve **1/458 émission
acceptée**, 73 blocages au prétraitement, 384 à l'analyse et zéro erreur
interne. Les premiers diagnostics changent pour 48 sources ; GO TO est
désormais le premier obstacle sur 46 sources. Ce rapport est statique et ne
valide pas les assertions NIST. Voir `tests/test_sections.py` et
`tests/fixtures/sections.cob`.

Étape précédente : première famille de PICTURE éditées (signe fixe +/- avec 9,
point explicite, Z initiaux suivis de 9 obligatoires), y compris les images
NIST `-9(9).9(9)` et `-.9(18)`. Les offsets des tokens distinguent le point
interne de fin de déclaration. La catégorie `edited` conserve les octets,
formate les sources numériques et reste distincte des opérandes numériques.
Échelle/ROUNDED précèdent le calcul du signe puis le modulo de capacité.
VALUE texte est brut ; INITIALIZE et le défaut formatent zéro. La déédition,
MOVE texte vers edited, ACCEPT édité et SIZE ERROR vers edited sont refusés.
Les comparaisons et sujets/cas EVALUATE directement édités sont aussi refusés :
GnuCOBOL replie certains littéraux composés de chiffres selon la PICTURE, même
si REDEFINES a modifié les octets. Une comparaison brute serait alors fausse.
Les sous-chaînes alphanumériques et copies vers PIC X restent comparables ;
un test natif conserve la différence. IS NUMERIC examine toujours les octets.

Les clauses FD LABEL OMITTED/STANDARD, BLOCK, RECORD exact et RECORDING F du
profil disque GnuCOBOL sont analysées dans `file_parser.py` et conservées dans
`FileSpec.fd_clauses`. Après layout, RECORD doit égaler la taille physique de
chaque description : un écart peut activer le format variable natif.

Validation de cette extension : **86 tests réussis, un ignoré** (87 découverts),
**45/45 comparaisons locales conformes** (`build/verification-edited-final.json`).
NIST reste à **1/458 émission acceptée**, 73 blocages au prétraitement et 384 à
l'analyse, zéro erreur interne (`build/coverage-nist-edited-final.json`). Les anciens
blocages de PICTURE et LABEL/BLOCK révèlent notamment les sections de procédure
(44 premiers diagnostics CCVS1 SECTION), les paragraphes AUTHOR et d'autres
clauses FD (DATA RECORD). Voir `tests/test_edited.py`, `tests/test_fd_clauses.py`
et la fixture intégrée `tests/fixtures/edited_report.cob`.

Étape précédente : SEQUENTIAL fixe, implicite ou explicite, conserve les octets
bruts sans délimiteur et accepte COMP/COMP-3 dans les groupes FD. Plusieurs
descriptions 01 de même taille partagent leur mémoire ; des tailles différentes
restent refusées pour ne pas produire un format fixe à la place d'un variable.
WRITE conserve désormais le nom du record dans son AST. `CobolFile` distingue
SEQUENTIAL et LINE SEQUENTIAL ; le rapport de conversion expose l'organisation
par fichier.

BEFORE/AFTER ADVANCING accepte PAGE ou un entier littéral 0..65535. Contrôles
bruts LF/CR/FF ; AFTER arme un LF final, BEFORE le désarme, WRITE nu conserve
l'état. CLOSE et Drop couvrent la fermeture implicite à STOP RUN. Une lecture
SEQ partielle conserve la queue du FD et retourne 00, puis 10 et 46 ; READ INTO
copie seulement `last_read_size()` octets avant le padding de sa destination.

Validation de cette extension : **75 tests réussis, un ignoré** (76 découverts),
**44/44 comparaisons locales conformes** (`build/verification-sequential.json`).
NIST reste à **1/458 émission acceptée**, 73 blocages au prétraitement et 384 à
l'analyse, zéro erreur interne (`build/coverage-nist-sequential.json`). Le
SEQUENTIAL implicite ne bloque plus ; les premières erreurs révèlent notamment
les PICTURE éditées, clauses FD LABEL/BLOCK, fichiers relatifs/indexés et
paragraphes documentaires. Les formats variables, autres clauses FD et
compteurs ADVANCING variables restent refusés. Voir `tests/test_sequential.py`
et les fixtures `sequential_records.cob`, `sequential_report.cob`.

Étape précédente : le normaliseur accepte les continuations fixes (mots, nombres,
PICTURE et littéraux), les espaces jusqu'à la colonne 72 et les tabulations
aux taquets de huit colonnes. Les guillemets en colonne 72 et les littéraux
fermés adjacents ont des tests natifs. Le parser accepte ENVIRONMENT et
CONFIGURATION vides, SOURCE-COMPUTER et OBJECT-COMPUTER à nom machine seul.
Les clauses de configuration non modélisées et indicateurs debug restent
refusés. Voir `tests/test_fixed.py`, `tests/test_configuration.py` et la nouvelle
fixture `tests/fixtures/fixed_continuation.cob`.

Validation de cette extension : **63 tests réussis, un ignoré** (64 découverts),
**42/42 comparaisons locales conformes** (`build/verification-continuations.json`).
NIST : **1/458 émission acceptée**, 73 blocages au prétraitement et 384 à
l'analyse, zéro erreur interne (`build/coverage-nist-fixed.json`). Le seul
programme accepté, SM301M avec COPY KSM31, a également une comparaison native
réussie (`build/nist-sm301m-verification.json`), sans valider ses assertions
NIST de signalement des standards. Les mesures initiales ci-dessous restent
conservées pour comparaison. Les obstacles majoritaires suivants concernent
les fichiers séquentiels implicites et leurs rapports, puis le lexing et les
paragraphes documentaires.

L'utilisateur fixe désormais comme objectif une **garantie universelle de
conversion COBOL vers Rust**. Ne pas limiter la feuille de route au sous-ensemble actuel,
ni annoncer cette garantie avant d'en avoir établi la portée et les preuves.
Voir [COVERAGE.md](COVERAGE.md) pour les profils, niveaux de validation et
premières mesures sur un corpus externe.

Le checkout actif est `/workspace/cobol2rust` sous Linux ; les chemins Windows
ci-dessous décrivent la livraison historique. Pour les outils de cette machine :
`source /workspace/tooling/activate.sh`, puis activer `.venv/bin/activate` depuis
la racine du checkout. Chaque tâche cloud est isolée ; utiliser le checkout
existant sans créer de worktree sauf demande explicite.

La reprise Linux a validé les 41 comparaisons du corpus livré et 33 tests Python,
avec un test d'inspection du PE Windows ignoré (34 découverts). Le rapport actuel
est `build/verification.json`. Cela lève l'absence de validation Linux signalée
dans les sections historiques ci-dessous, pour ces entrées seulement.

Les nouveaux outils `tools/prepare_nist.py` et `tools/coverage.py` préparent
et mesurent NIST CCVS85. Le corpus sous `.tools/nist-ccvs85/extracted` comprend
414 `.CBL` et 44 `.SUB` : **0/458 émission acceptée**, 398 blocages au
prétraitement et 60 à l'analyse, sans erreur interne. Les continuations fixes
et sections CONFIGURATION sont les premiers obstacles majoritaires. Aucun cas
NIST n'a été exécuté ; seul l'extracteur EXEC85 l'a été. Ne pas confondre le
corpus local de 41 programmes avec une conformité COBOL85. Le rapport est
`build/coverage-nist.json`, la provenance `.tools/nist-ccvs85/manifest.json`.

Après la première étape d'ajout des outils, la suite complète découvrait
49 tests : 48 réussissaient, un test PE Windows était ignoré. Le langage pris
en charge par le convertisseur n'avait pas encore été étendu dans cette
première étape de mesure. Les paquets de livraison
historiques n'ont pas été régénérés et la version reste 0.4.0.

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
- IF, EVALUATE, boucles, sections et paragraphes, PERFORM THRU mixte,
  retours imbriqués/récursifs et enchaînement séquentiel.
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
| `cobol2rust/documentary.py` | Filtrage des entrées documentaires IDENTIFICATION avant littéraux/COPY |
| `cobol2rust/data_parser.py` | Déclarations, PICTURE éditées, groupes, OCCURS, index et conditions 88 |
| `cobol2rust/file_parser.py` | Clauses FD du profil disque et métadonnées |
| `cobol2rust/layout.py` | Tailles physiques, offsets, dimensions et validation des dispositions |
| `cobol2rust/emitter.py` | Génération Rust, longueurs actives ODO et correspondance des lignes |
| `cobol2rust/runtime.rs` | Valeurs, décimaux exacts, opérations contrôlées et diagnostics |
| `cobol2rust/storage_runtime.rs` | Mémoire partagée, vues, sérialisation, tableaux et initialisation |
| `cobol2rust/file_runtime.rs` | LINE SEQUENTIAL, SEQUENTIAL fixe, contrôles ADVANCING et statuts |
| `cobol2rust/cli.py` | Commandes et génération du projet/rapport de conversion |
| `cobol2rust/control.py` | Graphe de contrôle, continuations et points de retour PERFORM |
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
   SEQUENTIAL fixe conserve tous les octets et ne sépare pas les records par
   LF. Les descriptions FD égales sont des vues partagées. Le préfixe physique
   d'un READ partiel et la queue inchangée du buffer doivent rester distincts
   pour READ INTO. Ne pas perdre le LF final pending après AFTER, même si des
   WRITE nus suivent, ni l'ajouter après BEFORE.
10. **PICTURE éditées et FD.** Une image éditée n'est pas un opérande numérique.
    Ne pas ajouter une déédition implicite dans Value.num(). Son signe est fixé
    après l'échelle, avant la troncature de capacité ; un débordement de MOVE
    n'est pas traité comme l'overflow conservateur des champs non édités.
    Les VALUE texte et numériques ont des chemins distincts. Ne pas ignorer
    un RECORD CONTAINS incohérent : cela peut changer le format physique.
    Une comparaison directe edited n'est pas une simple comparaison de texte
    sous toutes les optimisations GnuCOBOL ; conserver le refus tant que ce
    profil de comparaison n'est pas modélisé.
11. **Procédures.** Conserver l'ordre des blocs et les préambules de sections
    vides. GO ne dépile pas les retours en attente ; les points de retour
    comparent seulement le sommet. Fin paragraphe et fin section sont deux
    points distincts. EXIT SECTION saute la première, EXIT PARAGRAPH la vise.
    EXIT nu ne retourne pas. TIMES partage son compteur par site, même lors
    d'une réentrée récursive ; ne pas restaurer le compteur externe.
12. **MOVE vers texte.** Un groupe destinataire copie le stockage brut ; PIC X
    ou refmod reçoit les chiffres d'un entier. Ne pas confondre ces catégories
    ni traiter les champs V comme les littéraux décimaux. Préserver les chiffres
    lexicaux et la distinction ZERO/0. Réserver la conversion au MOVE, sans
    accepter de calcul vers texte ou de texte vers nombre par effet de bord.
13. **Comparaisons et MOVE depuis texte.** Préserver l'AST : littéral, champ et
    groupe ne sont pas interchangeables. Les optimisations de littéraux texte
    exigent la garde de largeur/échelle. La lecture alpha utilise un buffer fini,
    pas un parseur décimal générique ; conserver signe et zéros négatifs natifs.

Les lignes des diagnostics et source maps désignent `expanded.cob`, après
normalisation et expansion des COPY, et non toujours le source d'origine.

## Limites connues et suite conseillée

Les limites détaillées sont dans le README. Restent notamment hors périmètre :
SEARCH, tables à glissement ou stride variable, ODO dans un FD, USAGE INDEX
explicite, COMP-5, images éditées complexes et déédition, profils IBM/Micro Focus/EBCDIC, COPY REPLACING,
fonctions intrinsèques, appels interprogrammes, enregistrements variables,
fichiers relatifs/indexés, SQL et CICS. Sans gestionnaire arithmétique, les dépassements
et signes négatifs non signés provoquent encore un arrêt conservateur de code 70.
Le découpage LINE SEQUENTIAL avec COB_LS_SPLIT actif reste partiellement refusé.

Priorités possibles pour la prochaine étape :

1. Lever les blocages suivants du corpus NIST après séparateurs et paragraphes
   documentaires : DATA RECORD, organisations RELATIVE/INDEXED, FILE STATUS
   de groupe et VALUE/USAGE de groupe. Utiliser un essai natif avant chaque
   nouvelle règle et des comparaisons stdout/fichiers.
   SEARCH reste une extension utile des tables.
2. Reprendre précisément INITIALIZE des groupes ODO composés en examinant le C
   généré et le runtime GnuCOBOL ; conserver le refus tant que l'équivalence
   n'est pas établie.
3. Maintenir la validation Linux désormais acquise pour le corpus local et
   l'étendre aux nouveaux profils ; elle ne valide pas les dialectes IBM ou
   Micro Focus.
4. Pour le parcours sans sources, choisir d'abord une cible étroite, par exemple
   GnuCOBOL x86 PE. Compiler un petit exemple connu, analyser ses imports/appels
   `cob_*`, étudier son levage avec ARET puis comparer le Rust aux effets du
   binaire original. L'inspecteur actuel ne fournit pas cette chaîne.
5. Ajouter un corpus métier lorsque des programmes et leurs données seront
   disponibles, en épinglant le dialecte et les options du compilateur source.

Mettre à jour ce fichier, la version, la documentation, les rapports et les
paquets lors de la prochaine livraison. Le présent ajout documentaire ne change
pas la version 0.4.0 et ne régénère pas rétroactivement les archives déjà livrées.
