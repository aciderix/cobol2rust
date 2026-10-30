# COBOL → Rust

Première version fonctionnelle d'un transpileur strict, développée dans le dossier
`Cobol` du Bureau. Le convertisseur est écrit en Python 3.11 et produit un projet
Rust lisible, compilable et autonome. Le binaire produit n'utilise ni interpréteur
COBOL ni GnuCOBOL à l'exécution.

**La version 0.4 convertit un sous-ensemble des sources COBOL, dont les groupes,
tableaux fixes et variables, index, gestionnaires SIZE ERROR, niveaux 88,
REDEFINES et fichiers LINE SEQUENTIAL structurés. Elle inspecte les
exécutables PE/ELF, mais ne les décompile pas encore en Rust.** Il ne constitue
pas un convertisseur universel et ne valide pas à lui seul une migration métier.

La couverture universelle est désormais l'objectif de développement. La
[feuille de route et les mesures de couverture](COVERAGE.md) distinguent ce
cap de ce qui est effectivement accepté, compilé et vérifié.

Sur la branche de développement, la suite NIST CCVS85 est couverte telle que
GnuCOBOL 3.2 l'exécute : 451/458 sources acceptées ; sur les 427 programmes
vérifiés, 413 sont exécutés et donnent en Rust des REPORT identiques octet pour
octet (9610 PASS, 0 FAIL, le bilan natif exact) et 14, que le runner natif ne
fait que compiler, sont seulement compilés ; les 7 refus sont des programmes
CM que cobc ne compile pas non plus ([VALIDATION.md](VALIDATION.md)).

**Ce résultat ne mesure pas la couverture du COBOL réel.** Sur six corpus
publics épinglés (2458 sources, dont l'application mainframe CardDemo), le
convertisseur accepte 724 sources là où cobc en accepte 738 (CardDemo 14/14
des sources que cobc accepte) ; sur la testsuite de GnuCOBOL 3.2 (1135
sources), 490 contre 879. Accepter n'est pas exécuter à l'identique : le cap
du projet et sa mesure, exécution comprise, sont dans [CAP.md](CAP.md).

La branche de développement ajoute les fichiers `SEQUENTIAL` fixes, implicites
ou explicites, avec octets bruts, descriptions FD de même taille partageant leur
mémoire et contrôles d'impression `WRITE ... ADVANCING`.
Elle prend aussi en charge un premier sous-ensemble de PICTURE numériques
éditées et les clauses FD LABEL/BLOCK, RECORD de taille exacte, RECORDING F et
DATA RECORDS du profil disque GnuCOBOL vérifié. Un MOVE numérique tronque les
chiffres de tête sans SIZE ERROR, comme en natif.
Les séparateurs virgule/point-virgule et les paragraphes documentaires
d'IDENTIFICATION sont également pris en charge dans le profil décrit ci-dessous.

## Démarrer sous Windows

Ouvrir PowerShell dans ce dossier :

```powershell
cd "$env:USERPROFILE\Desktop\Cobol"
python -m cobol2rust doctor
python -m cobol2rust convert examples/invoice.cob -o build/ma-facture --run
```

Résultat attendu :

```text
HT=000059.85 TVA=000011.97 TTC=000071.82
Commande eligible
```

Le dossier de sortie doit être vide ou inexistant. Cela évite d'écraser un projet
Rust existant. Choisir un nouveau nom pour refaire une conversion.

Le convertisseur trouve automatiquement Rust dans `~/.cargo/bin` si les outils
ne sont pas dans le PATH. Le premier build télécharge `num-bigint` et ses
dépendances ; les builds suivants peuvent utiliser le cache Cargo. La génération
des sources Rust fonctionne sans accès réseau et sans compilateur installé.

## Convertir un source

```powershell
python -m cobol2rust convert chemin/programme.cob -o build/programme-rust
python -m cobol2rust convert examples/fixed.cob --format fixed -o build/fixe --build
python -m cobol2rust convert examples/copybook.cob -I examples -o build/copies --run
python -m cobol2rust convert principal.cob --call-path sousprogrammes -o build/unite
```

`--call-path` désigne les dossiers des programmes appelés par CALL : comme le
CALL dynamique de GnuCOBOL, un nom littéral `X` se résout en `X.cbl`/`X.cob`
dont le PROGRAM-ID est `X`. Le programme principal et tous ses appelés
(transitivement) forment une seule unité d'exécution Rust. Un CALL par
identifiant, dans le principal ou dans un appelé, y ajoute chaque source du
chemin d'appel qui se convertit seule sous son nom ; une telle source dont un
CALL littéral vise un programme du chemin qui ne se convertit pas en est
retirée.

Le projet produit contient :

| Fichier | Contenu |
| --- | --- |
| `Cargo.toml` | Projet Rust ; bibliothèque d'entiers de précision arbitraire `num-bigint` épinglée à 0.4.6 |
| `src/main.rs` | Champs, instructions, conditions, boucles, sections et paragraphes traduits |
| `src/runtime.rs` | Arithmétique décimale, remplissage des champs, saisie et affichage |
| `src/storage_runtime.rs` | Mémoire partagée, disposition des données, tableaux, vues REDEFINES et sérialisation |
| `src/system_runtime.rs` | Routines système d'octets, alias de stockage et ABI scalaire du profil Linux x86_64 |
| `src/file_runtime.rs` | Fichiers LINE SEQUENTIAL et SEQUENTIAL fixes, présent quand le programme utilise des fichiers |
| `expanded.cob` | Source normalisé avec les COPY développés |
| `conversion.json` | Empreintes source/copybooks, champs et offsets, conditions, sections/blocs de procédure, profil mémoire et correspondance des lignes |

Le code Rust peut ensuite être compilé sur Windows ou sur Linux avec Cargo.
Les tests de la livraison ont été exécutés sur Windows. La reprise cloud a
également vérifié sous Linux **460 tests Python** : **459 validés**, un test
d'inspection du PE Windows ignoré. La mesure du 29 octobre accepte
**1203/3593 sources** pour émission Rust ; l'exécution comparée des corpus
applicatifs donne **71/84 identiques**, cinq divergences et huit délais.
Une campagne distincte compare **11/11 scénarios d'entrée sur cinq programmes
interactifs** ; les validations historiques du corpus local sont détaillées
dans le journal de validation.
Les détails sont dans [VALIDATION.md](VALIDATION.md).
Ces résultats portent sur les entrées testées.

## Périmètre actuel

| Domaine | Pris en charge |
| --- | --- |
| Littéraux | Alphanumériques en octets source (UTF-8 compris), hexadécimaux `X"…"` ; concaténation `&`, `Z"…"`, `N"…"` refusés |
| Sources | Lecture en octets comme cobc (colonnes d'octets, BOM UTF-8 ignoré), en-tête IDENTIFICATION et PROCEDURE DIVISION facultatifs, INPUT-OUTPUT SECTION sans FILE-CONTROL si aucun SELECT ; détection du format comme cobc (colonne 7 de la première ligne, format fixe avec `-std=cobol85`), format libre, format fixe explicite avec continuations de mots/nombres/PICTURE/littéraux, commentaires, directive `>>SOURCE FORMAT`, séparateurs virgule/point-virgule |
| Options IBM | Lignes `CBL …` / `PROCESS …` d'options du compilateur ignorées jusqu'à la fin de ligne, comme pplex.l |
| Documentation COBOL | `AUTHOR`, `INSTALLATION`, `DATE-WRITTEN`, `DATE-COMPILED`, `SECURITY`, `REMARKS` avec point, en début de ligne dans IDENTIFICATION |
| Configuration | `ENVIRONMENT DIVISION`, `CONFIGURATION SECTION`, `SOURCE-COMPUTER` et `OBJECT-COMPUTER` avec nom machine seul |
| Copybooks | `COPY nom.` ou `COPY "nom.cpy".` seuls sur une ligne, recherche locale et `-I`, détection des cycles |
| Données | Groupes et champs de niveaux `01` à `49`, `77`, `PIC X`, `PIC 9`, `S`, `V`, `VALUE`, `FILLER` ; `LOCAL-STORAGE SECTION` réinitialisée à chaque CALL ; constantes `78 nom VALUE` et `01 nom CONSTANT [AS]` (littéral, figurative, `ALL` littéral ou expression entière de `cb_evaluate_expr`, toutes opérations de même priorité au niveau 78), substituées à chaque emploi comme le scanner de cobc, y compris `PIC X(nom)` ; `START OF`, `NEXT`, `LENGTH OF` et `FROM` refusés |
| Édition numérique | Signe fixe `+`/`-`, `9` et point décimal explicite ; `Z` initiaux suivis de `9` obligatoires ; rendu depuis une source numérique, copie brute vers texte |
| Tables et vues | `OCCURS n TIMES`, `OCCURS min TO max DEPENDING ON` (objet qualifié `OF`/`IN` compris), `INDEXED BY`, `SET index TO / UP BY / DOWN BY`, sous-scripts, noms qualifiés `OF`/`IN`, `REDEFINES`, sous-chaînes `champ(début:longueur)` |
| Conditions | Niveau `88`, y compris de groupe avec figurative ou `ALL` (répétée sur la taille du groupe), listes et plages `THRU`, `SET TO TRUE/FALSE`, tests `IS [NOT] NUMERIC`, `EVALUATE TRUE` |
| Usages | `DISPLAY`, `COMP` / `BINARY` / `COMP-4`, `COMP-3` / `PACKED-DECIMAL`, `COMP-6` (packed sans demi-octet de signe ; signé, il devient COMP-3 comme pour cobc), alias `COMPUTATIONAL` ; `COMP-5` / `COMPUTATIONAL-5` et `BINARY-CHAR/SHORT/LONG/DOUBLE [SIGNED/UNSIGNED]`, `BINARY-C-LONG`, types C `[UN]SIGNED-SHORT/INT/LONG` et alias `BINARY-INT`/`BINARY-LONG-LONG` de default.conf en binaire réel petit-boutiste : valeur bornée par la taille et non la PICTURE (repli modulo 2^(8×taille) sans SIZE ERROR, SIZE ERROR sur la capacité en bits), affichage `cob_print_realbin` ; `NOT ON SIZE ERROR` seul vers COMP-5 refusé |
| Calcul | `MOVE`, `COMPUTE`, `ADD ... TO`, `SUBTRACT ... FROM`, `MULTIPLY ... BY`, `DIVIDE ... INTO`, receveurs multiples et `GIVING` multiples avec `ROUNDED` par receveur, `ROUNDED MODE [IS]` et ses huit modes (`cob_decimal_do_round`, PROHIBITED en EC-SIZE-TRUNCATION ; `DEFAULT ROUNDED` du paragraphe OPTIONS refusé), `ON SIZE ERROR` / `NOT ON SIZE ERROR` |
| MOVE numérique vers texte | Entier DISPLAY/COMP/COMP-3/index vers PIC X ou sous-chaîne ; copie brute vers groupe hors index ; chiffres lexicaux des littéraux et remplissage ZERO |
| MOVE depuis du texte | Champ PIC X ou sous-chaîne vers numérique/édité ; littéral texte vers édité ou numérique DISPLAY ; groupe source copié brut vers numérique/édité |
| Comparaisons mixtes | Champ numérique face à une variable texte, groupe ou sous-chaîne ; littéral numérique non signé et ZERO face à du texte ; littéral texte face à un champ numérique (`cob_cmp_alnum` des chiffres stockés, sauf repli de `compare_field_literal`) |
| Contrôle | `IF` / `ELSE`, comparaisons explicites, `AND` / `OR` / `NOT`, `EVALUATE` simple, `GO [TO]` vers paragraphe/section, `GO TO ... DEPENDING [ON]` avec contrôleur entier de 9 chiffres au plus, `GO TO` sans cible et `ALTER` (label_N de cobc ; segments indépendants 50-99 remis à zéro comme codegen.c avec `--std cobol85`, ignorés par défaut comme `section-segments: ignore`), noms de procédure homonymes qualifiés `IN`/`OF` et noms entièrement numériques (règles de `cb_ref`), `PERFORM a THRU b` avec `b` avant `a`, `STOP littéral` (DISPLAY puis ACCEPT OMITTED ; le caractère 03 lu par un ACCEPT tue le programme par SIGINT comme `cob_raise`, arrêt nommé si un fichier est encore ouvert, libcob perdant alors ses tampons) |
| Boucles | `PERFORM ... TIMES`, `UNTIL`, `VARYING`, `WITH TEST BEFORE/AFTER`, `UNTIL EXIT` et `FOREVER`, `EXIT PERFORM [CYCLE]` dans un PERFORM en ligne (étiquettes de sortie et de cycle de codegen.c) |
| Procédures | Sections et paragraphes, `PERFORM`, plages `THRU`/`THROUGH` mixtes, retours imbriqués/récursifs, enchaînement séquentiel, `EXIT PARAGRAPH`, `EXIT SECTION` (hors section : fin de la « MAIN SECTION » implicite de cobc, avant la première SECTION), `EXIT` nu sans effet |
| Console | `DISPLAY` de champs, littéraux (signés compris) et fonctions alphanumériques, clauses `UPON` et `[WITH] NO ADVANCING` dans tout ordre, plusieurs listes avec leurs clauses dans une instruction (`display_atom`), `ACCEPT` simple, `ACCEPT ... FROM DATE [YYYYMMDD]`, `DAY [YYYYDDD]`, `DAY-OF-WEEK`, `TIME` |
| Fichiers | LINE SEQUENTIAL texte DISPLAY ; SEQUENTIAL fixe brut, FD multiples de même taille, `OPEN INPUT/OUTPUT/EXTEND`, `OPEN I-O` et `REWRITE` en SEQUENTIAL ; RELATIVE en accès SEQUENTIAL/RANDOM/DYNAMIC avec `RELATIVE KEY`, `READ [NEXT]`, `WRITE`, `REWRITE`, `DELETE`, `START`, `INVALID KEY`, `READ`, `READ INTO`, `AT END`, `NOT AT END`, `WRITE`, `WRITE FROM`, `WRITE BEFORE/AFTER ADVANCING` (entier, identifiant, PAGE, mnémonique FORMFEED/Cnn) en SEQUENTIAL et LINE SEQUENTIAL, FD `LINAGE` avec `LINAGE-COUNTER` et `AT END-OF-PAGE`, Report Writer (RD, `INITIATE`/`GENERATE`/`TERMINATE`, sous-ensemble décrit plus bas), `CLOSE [WITH LOCK]`, `DELETE FILE` (`cob_delete_file` : statuts 35, 38, 41, sans DECLARATIVES comme cobc), `ASSIGN [TO] LINE ADVANCING [FILE]` (LINE SEQUENTIAL sans validation des données, WRITE sans ADVANCING = AFTER 1 LINE), `FILE STATUS`, `SELECT OPTIONAL`, DECLARATIVES `USE AFTER ERROR/EXCEPTION` par fichier ou mode |
| Registres | `LENGTH [OF]` d'un article, d'un littéral ou d'une fonction (`cb_build_length` : littéral pour une taille fixe, somme sur l'OCCURS DEPENDING actif sinon, FUNCTION LENGTH pour une sous-chaîne) ; `RETURN-CODE` (BINARY-LONG par programme, partagé par les programmes contenus, recopié de l'appelé après CALL, conservé entre les CALL, code de sortie de STOP RUN et du GOBACK principal) |
| Tri de table | `SORT table [ON ASCENDING/DESCENDING KEY [clés]]… [WITH DUPLICATES]` comme `cob_table_sort` (stable, offset de clé relatif à son parent, clé OCCURS par défaut, ODO actif) |
| Directives | `>>SOURCE FORMAT`, compilation conditionnelle de pplex (`>>DEFINE nom [AS] littéral|OFF [OVERRIDE]`, `>>IF`/`>>ELIF` avec `[NOT] DEFINED` ou une comparaison, `>>ELSE`, `>>END-IF`, DEFINE standard `CHARSET`, `ENDIAN`, `SIGN`, `PERFORM-TYPE`), `>>DISPLAY` sans effet à l'exécution ; directives MF `$SET` (options sans effet ignorées comme les `#OPTION` de cobc, options actives refusées), `$IF`/`$ELSE`/`$END`, `$DISPLAY` ; `>>TURN`, `>>SET`, `>>DEFINE CONSTANT`/`PARAMETER` refusés |
| Fonctions | `REPOSITORY` : `FUNCTION ALL INTRINSIC` et `FUNCTION nom... INTRINSIC` (noms appelés sans le mot FUNCTION dans le programme et ses programmes contenus) ; fonctions utilisateur (FUNCTION-ID) refusées |
| Autres | `INITIALIZE`, `INITIALIZE ... WITH FILLER`, `INITIALIZE ... REPLACING`, `CONTINUE`, `STOP RUN`, `GOBACK` ; hors `-std=cobol85`, alias de mots réservés de default.conf (`INITIALISE`, `ORGANISATION`, `SYNCHRONISED`, `TIMEOUT`…) |

Les champs numériques DISPLAY et COMP-3 vont jusqu'à **38 chiffres** comme
cobc (`COB_MAX_DIGITS`), les BINARY/COMP/COMP-5 jusqu'à 18 (au-delà, l'erreur
de cobc `binary field cannot be larger than 18 digits`), les PICTURE avec P
jusqu'à 18 chiffres, en DISPLAY, BINARY, COMP-3 ou COMP-5 ; les champs PIC X/A jusqu'à 65535 caractères, les champs édités
jusqu'à 38 chiffres et 256 caractères. Un groupe peut être plus grand.
La mémoire totale est limitée à **16 Mio**, les tableaux à **7 dimensions** et
chaque clause OCCURS à **1..10000 occurrences** (minimum variable autorisé : 0).
Les clauses et variantes absentes
de cette liste ne sont pas réputées prises en charge.

Sont notamment refusés : tables variables à offsets ou strides variables,
REDEFINES indirects, USAGE hors liste (PROGRAM-POINTER, COMP-1/2, COMP-X…), images
éditées hors du sous-ensemble décrit ci-dessous, fonctions intrinsèques hors
liste ci-dessous, CALL d'un programme ni converti ni sûrement absent,
STOP identifiant,
SCREEN SECTION, SQL embarqué et CICS. Les formats de fichier autres que ceux
décrits plus bas (LINE SEQUENTIAL, SEQUENTIAL fixe ou variable, RELATIVE,
INDEXED au format propre de cobol2rust) ne sont pas modélisés.
La déédition, les calculs sur texte et les calculs vers PIC X restent refusés.
Le MOVE d'un littéral texte vers un champ numérique DISPLAY suit
`cb_build_move_literal` : à échelle égale et sans signe séparé, ses octets sont
copiés à la compilation (cadrés à droite, complétés de zéros, BLANK WHEN ZERO
appliqué) ; sinon `cob_move` le traite comme un champ PIC X. Vers un champ
binaire ou packé il reste refusé (optimisations natives de cobc). `MOVE ALL
"littéral"` vers un alphanumérique édité remplit sans édition, comme le
`memset`/`memcpy` de cobc ; une constante figurative y est éditée.

Pour `MOVE`, un entier numérique vers PIC X ou sous-chaîne fournit les chiffres
de sa magnitude sur la largeur PICTURE, sans signe, puis tronque à droite ou
complète d'espaces. Une destination groupe reçoit les octets du stockage source,
y compris overpunch et COMP/COMP-3 ; elle peut aussi recevoir une source avec V.
Une telle source décimale vers PIC X élémentaire est refusée par GnuCOBOL dans
le profil vérifié. Les chiffres d'un littéral sont conservés sans signe ni point :
`MOVE -0012.30 TO texte` envoie `001230`. `ZERO` remplit la destination de zéros,
tandis que le littéral `0` est complété d'espaces.

Le MOVE d'un index implicite vers un groupe reste refusé à cause de son stockage
natif. Les données DISPLAY non signées invalides sont copiées brutes vers PIC X ;
les données signées invalides déclenchent un arrêt nommé, car certaines
normalisations natives de signe et leurs effets sur la source restent à modéliser.

Un MOVE depuis PIC X ou une sous-chaîne vers un champ numérique ou édité suit
la lecture native avec signe initial, point, espaces et virgules. DISPLAY lit
un buffer limité à sa PICTURE ; COMP/COMP-3 et edited passent par 76 positions,
dont 38 fractionnaires. Le remplissage peut arrêter la validation avant un
caractère invalide ; sinon ce caractère ramène le buffer à zéro. Un groupe
source demande au contraire une copie brute du stockage. `MOVE " " TO edited`
est accepté ; la constante figurative `SPACE` reste refusée dans ce contexte.

Une comparaison mixte transforme le champ numérique en chiffres de magnitude
sur sa largeur PICTURE, sans signe ni point, même avec V, puis compare les
octets complétés d'espaces. Les littéraux numériques non signés gardent leurs
chiffres lexicaux ; ZERO remplit la largeur texte. Face à un champ numérique,
un littéral texte direct n'est accepté que pour un entier et des chiffres de
même largeur : GnuCOBOL replie d'autres cas selon la PICTURE. Copier le littéral
vers PIC X permet la comparaison à l'exécution. Restent refusés dans les
comparaisons mixtes : index, signes numériques explicites, expressions
arithmétiques, sujets/cas EVALUATE de catégories différentes et valeurs 88
de catégorie différente du parent.

Les sauts conservent les retours PERFORM en attente ; seule la borne exacte du
cadre au sommet de pile peut reprendre sa continuation. Les fins de paragraphe
et de section sont distinctes. Les compteurs TIMES sont partagés par site lors
d'une réentrée récursive, comme dans le profil GnuCOBOL vérifié. GO DEPENDING
accepte les données entières, tables subscriptées et index implicites ; une
valeur hors de 1..N ne saute pas. Les contrôleurs décimaux ou de plus de neuf
chiffres restent refusés en raison des conversions natives non uniformes.

Le format fixe suit les colonnes 8 à 72 et les taquets de tabulation de huit
colonnes du profil GnuCOBOL utilisé. Les espaces jusqu'à la colonne 72 sont
conservés dans les littéraux continués. Les indicateurs debug `D`, les
continuations à travers une directive de format et les clauses de configuration
ayant une sémantique non modélisée (`SPECIAL-NAMES`, collation, mode debug,
etc.) restent refusés.

Les virgules et points-virgules séparent les mots et opérandes sans terminer
une phrase. Dans les sous-scripts, ils gardent les indices distincts, y compris
`table(1,+2)` ; les suites mixtes de séparateurs restent refusées dans ces listes.
Une PICTURE est un mot contigu : ses virgules d'édition sont conservées et
restent hors du sous-ensemble accepté. Les espaces internes ne sont pas recollés.
COPY conserve sa syntaxe propre ; les séparateurs supplémentaires non cités
sur une ligne COPY sont refusés.

Un en-tête documentaire doit être le premier mot de sa ligne physique dans
IDENTIFICATION. En format libre, seul le reste de cette ligne est ignoré ; en
fixe, la prose de zone B continue jusqu'à la prochaine ligne de code en zone A.
Les guillemets et COPY de cette prose sont ignorés avant l'analyse du code.
Les directives de format sur leur propre ligne restent actives, et une ligne
de continuation `-` dans cette prose est refusée. Les clauses sémantiques de
PROGRAM-ID et de CONFIGURATION restent analysées.

Les erreurs de syntaxe non prise en charge donnent une position et empêchent
la création du projet. Les lignes des diagnostics et de la correspondance
Rust désignent le source **normalisé et développé** (`expanded.cob`), pas
nécessairement la ligne d'origine avant expansion des copybooks.

## Programmes appelés (CALL)

CALL littéral ou par identifiant, USING BY REFERENCE/BY CONTENT/OMITTED, ON EXCEPTION/
OVERFLOW, NOT ON EXCEPTION, CANCEL, EXIT PROGRAM et GOBACK suivent GnuCOBOL 3.2
(`output_call` de codegen.c, `cob_call_field`/`cob_cancel` de call.c) :

- un appelé conserve sa WORKING-STORAGE entre deux CALL ; CANCEL la réinitialise
  et ferme ses fichiers ouverts ; CANCEL d'un programme actif (le principal
  compris) est l'erreur libcob `attempt to CANCEL active program` (`P_cancel`,
  code 1) ; un CALL d'un programme actif est `recursive CALL from 'A' to 'B'
  which is NOT RECURSIVE` (`COB_FERROR_RECURSIVE`, code 1 ; RECURSIVE n'est
  pas pris en charge), sauf sous ON EXCEPTION : `cob_module_global_enter`
  lève alors EC-PROGRAM-RECURSIVE-CALL, l'appel rend -1 dans RETURN-CODE et
  ON EXCEPTION s'exécute ;
- un littéral alphanumérique ou une figurative en argument (`output_call`)
  : BY CONTENT, une copie neuve de ses octets (une figurative vaut un
  caractère) ; BY REFERENCE, la constante du programme elle-même, en lecture
  seule (une écriture de l'appelé est un arrêt nommé, cobc mourant de
  SIGSEGV) ; `OMITTED` passe une adresse nulle. Les littéraux numériques
  transmis par adresse (entier C dans 8 octets en partie non initialisés)
  restent refusés ; le BY VALUE scalaire des routines décrites ci-dessous
  suit un contrat distinct ;
- les articles LINKAGE (et leurs REDEFINES) deviennent des vues sur la mémoire
  de l'argument ; BY CONTENT passe une copie ; un article LINKAGE plus long que
  son argument s'arrête au lieu de lire la mémoire voisine ; un article que
  le CALL ne transmet pas (moins d'arguments, article hors du USING de
  l'entrée, LINKAGE hors de tout USING) n'a pas d'adresse, comme le NULL de
  cobc, et son premier accès est un arrêt nommé (`LINKAGE item not passed by
  caller`) ;
- `01 arg [PIC X] ANY LENGTH` en LINKAGE reçoit la taille réelle de
  l'argument, sans changer ses attributs alphanumériques. Les longueurs,
  sous-chaînes, MOVE et conditions de niveau 88 utilisent cette taille ;
  l'INITIALIZE simple conserve la taille nominale d'un octet, comme cobc.
  Le cache de taille survit à OMITTED, CANCEL et INITIAL. L'ordre de taille
  des paramètres ENTRY reproduit aussi le bogue natif #902. Une lecture ou
  écriture dépassant l'argument reste un arrêt nommé. ANY NUMERIC, les
  formats national/booléen, USAGE autre que DISPLAY et ANY LENGTH GLOBAL
  restent refusés explicitement ; un paramètre ANY ne peut être retransmis
  que BY REFERENCE ;
- `ENTRY 'nom' [USING …]` (`emit_entry`, `output_entry_function`) ajoute un
  point d'entrée : un CALL de ce nom commence à l'instruction ENTRY avec ses
  paramètres, que le programme traverse sinon comme une étiquette. Comme pour
  les modules de cobc, le nom n'est trouvé qu'une fois le programme chargé par
  un CALL de son PROGRAM-ID ; avant, c'est EC-PROGRAM-NOT-FOUND. ENTRY est
  refusé dans un programme contenu, en cobol85, avec convention d'appel ou
  FOR GO TO ;
- un programme principal avec PROCEDURE DIVISION USING est un module (cobc
  refuse `-x`) : il s'exécute comme `cobcrun` l'appelle, sans argument ;
  EXIT PROGRAM et GOBACK terminent alors l'unité avec RETURN-CODE. `verify` le
  compile avec `cobc -m` et le lance par `cobcrun`. cobcrun ne lui passe
  aucune adresse (le C lit un paramètre indéterminé) : le Rust s'arrête au
  premier accès à un paramètre ;
- `PROCEDURE DIVISION CHAINING` (`cob_chain_setup`) : chaque article 01/77 de
  WORKING-STORAGE reçoit, après son initialisation, l'argument de ligne de
  commande de son rang, complété d'espaces ou tronqué ; `PROGRAM-ID nom AS
  "externe"` donne le nom d'appel du module ; `RETURNING OMITTED` est accepté
  (un programme principal ainsi déclaré est un module, cobc refusant `-x`) ;
- EXIT PROGRAM est sans effet dans le programme principal, GOBACK y vaut STOP RUN ;
  STOP RUN dans un appelé termine toute l'unité ;
- un nom introuvable prend ON EXCEPTION seulement s'il est sûrement absent : mot
  majuscule, ni routine système libcob (`SYSTEM`, `CBL_…`, `C$…`), ni source du
  chemin d'appel non convertie. Sinon la conversion ou l'exécution s'arrête.
  Sans ON EXCEPTION, un module sûrement absent suit `cob_call_error` :
  `libcob: error: module 'NOM' not found`, avertissements des fichiers ouverts,
  code de sortie 1.

Les appels littéraux et dynamiques aux routines `CBL_AND`, `CBL_OR`,
`CBL_NOR`, `CBL_XOR`, `CBL_IMP`, `CBL_NIMP`, `CBL_NOT` et `CBL_EQ` portent
les boucles de `common.c`. `C$TOUPPER` et `C$TOLOWER`, avec leurs alias
`CBL_TOUPPER` et `CBL_TOLOWER`, complètent ces douze noms. Les arguments de
données passent BY REFERENCE ou BY CONTENT ; la longueur finale passe BY
VALUE en entier C. Comme `cb_build_call_parameter`, un argument
alphanumérique BY VALUE est réécrit BY CONTENT, sans ajouter de paramètre
formel BY VALUE. Les écritures relisent les octets sources après chaque
octet modifié : des zones qui se chevauchent gardent l'ordre natif. La
longueur peut dépasser la PICTURE ou une sous-chaîne décrite, tant qu'elle
reste dans l'allocation adressée et dans la limite de l'argument LINKAGE.
Une longueur nulle ou négative ne lit ni n'écrit les données, même si leur
adresse est OMITTED. Ces routines renvoient zéro dans RETURN-CODE.

Ce contrat scalaire vise **Linux x86_64**, avec la locale C de LC_CTYPE
initialisée par GnuCOBOL. Les tailles 1, 2, 4 et 8, SIZE AUTO, SIZE DEFAULT
et UNSIGNED conservent les casts et promotions observés dans le C natif ;
la taille implicite vaut 8, SIZE DEFAULT explicite vaut 4. Un littéral
numérique transmet son coefficient sans point décimal, alors qu'un champ
suit son décodeur de stockage natif. Dans les formats pris en charge, les
particularités des signes, des PICTURE P et de la clause SIGN explicite sont
conservées. Ce chemin ne
constitue pas un support général de BY VALUE entre programmes ou vers du C
externe ; les paramètres formels BY VALUE et CALL RETURNING/GIVING restent
refusés.

Comme `cb_build_call_parameter`, un argument alphanumérique écrit BY VALUE
est transmis BY CONTENT ; cette règle de l'appelant ne rend pas les
paramètres formels BY VALUE compatibles.

Les résultats de FUNCTION ABS, MAX, MIN, MEDIAN et MEAN à un argument sont
refusés comme longueur BY VALUE, car leur description de champ doit encore
être reproduite à cet endroit. Les longueurs numériques éditées et les
expressions de longueur ODO qui ne sont pas encore représentées par un
scalaire restent aussi refusées. Une FUNCTION supplémentaire à un appel
littéral de routine connue reste aussi refusée ; les autres arguments
supplémentaires suivent le chemin natif qui les ignore. Une adresse NULL
avec longueur positive, une écriture de littéral en lecture seule ou un
accès au-delà de l'allocation provoquent des arrêts nommés.

Les noms littéraux sont normalisés selon les espaces, le premier NUL et le
dernier composant après `/` ou `\`, sans changer leur casse. Un nom dynamique
conserve l'avertissement natif pour les espaces initiaux. La résolution
dynamique donne priorité aux programmes contenus ; un littéral reconnu
comme routine système garde la priorité de l'appel natif direct.

Les programmes qui suivent `END PROGRAM` dans le même source sont des frères :
ils sont dans l'exécutable et GnuCOBOL les trouve avant le chemin d'appel.
Les programmes contenus (IDENTIFICATION DIVISION à la fin de la PROCEDURE
DIVISION, puis `END PROGRAM`) sont appelables par le programme qui les contient
directement et, s'ils sont `COMMON`, par les autres programmes qu'il contient ;
tout autre CALL de leur nom est refusé (cobc le résoudrait dynamiquement sans
les trouver). Un article 01/77 `GLOBAL` d'un programme contenant est vu par ses
descendants (un nom local le masque) et partage leur stockage ; un article
`EXTERNAL` est un bloc de l'unité d'exécution désigné par son nom, comme
`cob_external_addr` (alloué à zéro, sans VALUE, même taille exigée).

Un FD `EXTERNAL` partage le fichier et sa zone d'enregistrement
(`<fichier>_Record`) dans l'unité d'exécution, comme `cob_file_external_addr` :
le premier programme qui le déclare le crée (son ASSIGN et son OPTIONAL
comptent), chaque programme garde son propre FILE STATUS, et le CANCEL d'un
programme ferme le fichier qu'il a laissé ouvert. Un FD `GLOBAL` d'un programme
contenant est vu par ses descendants avec ses enregistrements ; une nouvelle
instance du programme (après CANCEL) a un nouveau fichier. `USE GLOBAL AFTER
ERROR` sur un mode d'ouverture sert aux programmes contenus qui n'ont pas de
USE pour ce mode, selon le parcours de cobc.c (premier programme défini avant,
de niveau inférieur, jusqu'au niveau 0) ; la procédure s'exécute avec les
données et les fichiers du programme qui la déclare (entrée 2 de sa fonction
C : un alias qui partage son stockage), puis rend la main au programme
appelant. Un programme `INITIAL` est annulé (CANCEL implicite) à chaque retour.

Restent refusés : BY VALUE hors du contrat système ci-dessus, les paramètres
formels USING autres que BY REFERENCE, CALL RETURNING/GIVING, USE GLOBAL sur un nom de
fichier, un USE GLOBAL que le parcours de cobc.c prendrait à un programme non
contenant, ALTER dans un programme à USE GLOBAL et GOBACK ou EXIT PROGRAM dans
sa procédure, FD
EXTERNAL et GLOBAL à la fois, avec LINAGE ou REPORT, SD GLOBAL/EXTERNAL, FD
GLOBAL dont FILE STATUS, RELATIVE KEY ou DEPENDING désigne une donnée non
GLOBAL, plusieurs programmes dans un source appelé,
EXTERNAL AS et VALUE d'un article EXTERNAL, VALUE en LINKAGE hors d'un article
BASED, et `NOT ON EXCEPTION` suivant un
DISPLAY/ACCEPT/CALL de ON EXCEPTION (GnuCOBOL le rattache à ce DISPLAY).

## Adresses : POINTER, ADDRESS OF, BASED, ALLOCATE et FREE

`USAGE POINTER` (8 octets, NULL par défaut, `VALUE NULL`), `ADDRESS OF`
(indices et modification de référence compris), `SET pointeur | ADDRESS OF
article … TO {pointeur | ADDRESS OF | NULL}` et `… UP/DOWN BY n`, `MOVE` entre
pointeurs, les comparaisons d'adresses, les articles `BASED` (01/77, VALUE
gardé pour ALLOCATE INITIALIZED), `ALLOCATE article [INITIALIZED]` et
`ALLOCATE n CHARACTERS [INITIALIZED [TO x]] RETURNING pointeur` (`cob_allocate`,
NULL si la taille n'est pas positive) et `FREE` (`cob_free_alloc` : seule
l'adresse rendue par ALLOCATE est libérée, le pointeur passe alors à NULL)
suivent cobc 3.2. Une adresse native est remplacée par une zone et un décalage :
chaque 01/77 d'un programme est une zone (un tableau `b_` de cobc), comme une
aire ALLOCATE ou un bloc EXTERNAL ; l'arithmétique et l'ordre restent ceux du
natif dans une zone, et tout accès au-delà de la zone, par une adresse NULL ou
après FREE est un arrêt nommé. Un article LINKAGE d'aucune USING garde son
adresse d'un appel à l'autre et après CANCEL (pointeur statique de cobc) ; le
CANCEL libère les zones des articles BASED ; un ASSIGN vers un article sans
adresse donne le statut 31 à l'OPEN, avec le nom `field with NULL address` de
`cob_field_to_string` dans le message d'erreur. Une zone ALLOCATE sans
INITIALIZED TO (`malloc`, contenu indéterminé en natif) est suivie octet par
octet : lire un octet jamais écrit est un arrêt nommé ; `INITIALIZED` seul sur
`n CHARACTERS` est un `calloc` (zéros).

Sont des arrêts nommés, les valeurs natives n'étant pas reproductibles (ASLR,
disposition de l'éditeur de liens) : l'affichage d'une adresse non NULL, seule
ou dans un groupe, et l'ordre de deux adresses de zones différentes. Restent
refusés : les pointeurs BY VALUE (cobc 3.2 les tronque en `int`),
PROGRAM-POINTER et FUNCTION-POINTER, ADDRESS OF PROGRAM, l'arithmétique et les
MOVE entre une adresse et une autre donnée, FUNCTION CONTENT-OF et
CONTENT-LENGTH.

## NEXT SENTENCE et PICTURE P

NEXT SENTENCE poursuit après le prochain point séparateur, y compris depuis un
IF imbriqué, un EVALUATE ou une boucle PERFORM inline qu'il quitte.

PICTURE P (`S99P`, `9(3)P(4)`, `PP99`, `SVP9`) suit l'analyse de cobc : seuls
les 9 sont stockés ; un P final multiplie par 10, un P initial ajoute une
position décimale implicite. MOVE, calcul, comparaison numérique et DISPLAY
(`+990`, `.0012`) sont identiques au natif, y compris la troncature de
l'opérande par `cob_add_int` (`ADD 15 TO S99P` ajoute 10). P est limité à USAGE
DISPLAY ; les MOVE entre texte et champ P sont refusés.

## Édition et comparaisons

Les images éditées numériques (`Z`, `*`, `9`, `+`, `-`, `$` fixes ou flottants,
`,`, `.`, `B`, `0`, `/`, `CR`, `DB`, `P`, BLANK WHEN ZERO) et alphanumériques
(`X`, `A`, `9` avec `B`, `0`, `/`) sont éditées comme libcob, et acceptées ou
refusées comme cobc. Un champ édité se compare comme texte. Comme cobc, une
comparaison d'un champ DISPLAY avec un littéral trop long est résolue à la
compilation (`S99 > -100` est FAUX, comme en natif). JUSTIFIED RIGHT, VALUE ALL
et QUOTE sont pris en charge, ainsi que SIGN LEADING/TRAILING [SEPARATE] et
SYNCHRONIZED lorsqu'il n'impose aucun octet de remplissage.

## SORT et MERGE

SORT et MERGE (SD, clés ASCENDING/DESCENDING, USING/GIVING de fichiers
séquentiels fixes ou SEQUENTIAL variables sans DEPENDING, INPUT/OUTPUT
PROCEDURE, RELEASE, RETURN) reproduisent le tri stable de libcob ; un USING
variable copie la taille lue et un GIVING écrit `record_max`, comme
`cob_copy_check`. Un SD à OCCURS DEPENDING est accepté pour USING/GIVING, où
libcob déplace chaque enregistrement à la taille maximale du SD ; RELEASE et
RETURN d'un tel SD, et SORT … COLLATING SEQUENCE littérale, restent refusés.

## Horloge, ACCEPT FROM DATE et FUNCTION RANDOM

`ACCEPT x FROM DATE [YYYYMMDD]`, `DAY [YYYYDDD]`, `DAY-OF-WEEK` et `TIME`
reprennent `cob_accept_date`… (valeur déplacée comme un champ binaire de 6, 8,
5, 7 ou 8 chiffres, DAY-OF-WEEK comme un caractère alphanumérique) et
FUNCTION CURRENT-DATE ; l'heure vient de `cob_get_current_datetime` : heure
locale (fuseau UTC seul modélisé), nanosecondes toujours lues comme
`clock_gettime` sous Linux, et `COB_CURRENT_DATE` porté de
`check_current_date` (date, heure, nanosecondes, décalage `Z`/`±hh[:]mm`,
gabarits `YYYY`/`MM`/…, normalisation `mktime`). Une valeur invalide de
`COB_CURRENT_DATE` (libcob l'ignore avec un avertissement) et la forme
`@secondes` sont des arrêts nommés. `verify --runtime-env COB_CURRENT_DATE=…`
fixe l'horloge des deux programmes. `FUNCTION RANDOM [(graine)]` reproduit le
Mersenne Twister de GMP 6.3 utilisé par libcob (`gmp_randseed_ui`,
`mpf_urandomb` de 63 bits, `mpf_get_d` tronqué, conversion exacte du double) ;
sans graine au premier appel, libcob tire la graine de l'heure et de l'adresse
du module, valeur non reproductible : le port prend l'heure et une adresse du
programme Rust, ce qui donne une suite native possible.

## Fonctions intrinsèques

Portées de libcob/intrinsic.c : INTEGER, INTEGER-PART, FRACTION-PART, MOD,
REM, ABS, FACTORIAL, EXP10, SUM, MEAN, MEDIAN, MIDRANGE, RANGE, VARIANCE,
STANDARD-DEVIATION, ORD-MAX, ORD-MIN, MAX, MIN, ANNUITY, PRESENT-VALUE,
SQRT, LOG, LOG10, EXP, SIN, COS, TAN, ASIN, ACOS, ATAN, PI, E, RANDOM, CHAR,
ORD, UPPER-CASE, LOWER-CASE, REVERSE, TRIM, CONCATENATE (et CONCAT),
SUBSTITUTE, SUBSTITUTE-CASE, STORED-CHAR-LENGTH, HEX-OF, HEX-TO-CHAR, NUMVAL,
NUMVAL-C, NUMVAL-F, TEST-NUMVAL, TEST-NUMVAL-C, TEST-NUMVAL-F, LENGTH,
HIGHEST-ALGEBRAIC et LOWEST-ALGEBRAIC (selon l'usage de
l'argument, à la compilation), INTEGER-OF-DATE/DAY, DATE-OF-INTEGER,
DAY-OF-INTEGER, TEST-DATE-YYYYMMDD, TEST-DAY-YYYYDDD, YEAR-TO-YYYY,
DATE-TO-YYYYMMDD, DAY-TO-YYYYDDD (année courante de `localtime`, non de
`COB_CURRENT_DATE`, comme libcob), CURRENT-DATE et WHEN-COMPILED, et les
fonctions ISO 8601 FORMATTED-DATE, FORMATTED-TIME, FORMATTED-DATETIME (offset
explicite ou SYSTEM-OFFSET), FORMATTED-CURRENT-DATE, TEST-FORMATTED-DATETIME,
INTEGER-OF-FORMATTED-DATE et SECONDS-FROM-FORMATTED-TIME : formats contrôlés
à la compilation quand ils sont littéraux (`valid_const_date_time_args`),
semaine ISO, passage à UTC de `Z`, signe d'offset de `add_offset_time`
(perdu sous une heure, comme libcob), résultat en espaces pour un argument
invalide. SECONDS-FROM-FORMATTED-TIME d'une date-heure contenue dans une
donnée (lue en chaîne C au-delà de la donnée par libcob) est un arrêt nommé.

`TEST-NUMVAL`, `TEST-NUMVAL-C` et `TEST-NUMVAL-F` renvoient zéro pour une
entrée valide, sinon la position native de l'octet en erreur (parfois après
le dernier octet). La monnaie, CR/DB, le point/virgule du module, les 38
chiffres et les règles d'exposant viennent de `cob_check_numval*`.
`NUMVAL-F` garde la conversion partielle de GnuCOBOL 3.2 : `"1E2"` donne
100, bien que TEST-NUMVAL-F renvoie 3. Les arguments sont lus en stockage
brut : champs, groupes, sous-chaînes, littéraux et fonctions alphanumériques ;
un littéral numérique `-12.30` fournit les octets `-1230`. Le stockage des
résultats numériques calculés, qui dépend notamment du pliage de constantes
de cobc, reste refusé dans ces quatre fonctions. Les limites générales du
runtime restent 1024 décimales et 4096 chiffres ; au-delà, arrêt nommé.
Le registre d'exception est décrit plus bas (« Dernière exception »).

INTEGER-OF-DATE, INTEGER-OF-DAY, DATE-OF-INTEGER et DAY-OF-INTEGER
renvoient zéro pour les arguments hors domaine, comme GnuCOBOL. Les
résultats s'affichent sur 9, 9, 8 et 7 chiffres. Le modèle d'arguments
numériques et sa limite C int restent inchangés ; leur exception n'est pas
portée et rend la dernière exception inconnue.

`DISPLAY` d'un résultat numérique montre le champ temporaire de libcob :
copie de l'argument retenu pour MAX, MIN, MEDIAN (tri stable de glibc) et
MEAN d'un seul argument, l'argument d'ABS avec sa valeur absolue,
`cob_alloc_field` pour un résultat décimal (binaire de 9 ou 20 chiffres, ou
DISPLAY de `mpz_sizeinbase` chiffres, estimation de GMP reproduite), entier
non signé de 9 chiffres pour ORD, LENGTH, INTEGER-OF-DATE… Restent refusés
le DISPLAY de RANDOM (double imprimé par `%G`), d'un argument PICTURE P
(échelle négative) et d'une expression en argument de MAX/MIN/MEDIAN. Un
littéral alphanumérique vide vaut une espace, comme le scanner de cobc, et
est refusé sous `-std=cobol85`. Les fonctions LOCALE-*,
MODULE-*, EXCEPTION-FILE-N, EXCEPTION-LOCATION-N, BIT-OF, COMBINED-DATETIME,
SECONDS-PAST-MIDNIGHT et les fonctions utilisateur restent refusées.

### Dernière exception : FUNCTION EXCEPTION-* et SET LAST EXCEPTION

`FUNCTION EXCEPTION-STATUS`, `EXCEPTION-LOCATION`, `EXCEPTION-STATEMENT`,
`EXCEPTION-FILE` et `SET LAST EXCEPTION TO OFF` lisent et remettent à zéro la
dernière exception de libcob (`cob_set_exception`), commune à toute l'unité
d'exécution : seule `SET LAST EXCEPTION TO OFF` l'efface. Sans `-debug`,
l'emplacement est « programme; ; 0 » et l'instruction inconnue (espaces),
comme cobc sans `-fsource-location`. Exceptions portées : statuts d'E/S de
`save_status` (classe du statut, EC-I-O-EOP, fichier de `cob_error_file`
même sans exception), division par zéro, EC-SIZE-OVERFLOW des stockages
arithmétiques dans un receveur DISPLAY ou édité (avec ou sans SIZE ERROR,
compteurs TALLYING et pas de VARYING compris), EC-SIZE-OVERFLOW de tout
receveur sous SIZE ERROR, EC-SIZE-TRUNCATION de ROUNDED MODE PROHIBITED,
STRING/UNSTRING (EC-OVERFLOW-*), INSPECT (EC-RANGE-INSPECT-SIZE),
ALLOCATE/FREE (EC-STORAGE-IMP, EC-STORAGE-NOT-ALLOC), ACCEPT en fin
d'entrée (EC-IMP-ACCEPT), CALL introuvable (EC-PROGRAM-NOT-FOUND) et appel
récursif sous ON EXCEPTION (EC-PROGRAM-RECURSIVE-CALL, RETURN-CODE -1, au
lieu de l'arrêt fatal), MOD/REM par zéro et fonctions ISO 8601
(EC-ARGUMENT-FUNCTION). Les fonctions sans exception (TRIM, UPPER-CASE…)
n'y touchent pas. Toute autre source possible rend la dernière exception
inconnue : fonction intrinsèque non auditée, exponentiation, stockage
arithmétique dans un receveur binaire ou packé, SORT/MERGE, Report Writer,
CANCEL ou sortie d'un programme INITIAL avec des fichiers ouverts, USE
GLOBAL… La lire alors est un arrêt nommé. Ce suivi n'est généré que si une
fonction EXCEPTION-* figure dans l'unité. Sous `--runtime-checks` (`-debug`),
EXCEPTION-LOCATION et EXCEPTION-STATEMENT sont refusées : cobc y suit
section, paragraphe, ligne et sous-clauses (WHEN, AT END…).

## SPECIAL-NAMES, ACCEPT et DISPLAY UPON

SPECIAL-NAMES accepte les noms mnémoniques de périphériques (DISPLAY UPON
SYSOUT/CONSOLE/SYSERR, ACCEPT FROM SYSIN/CONSOLE), SWITCH-n avec conditions
ON/OFF et SET … TO ON/OFF (état initial lu dans `COB_SWITCH_n`, comme libcob),
les alphabets NATIVE, STANDARD-1, STANDARD-2 et ASCII (sans effet sur une
machine ASCII), les alphabets littéraux (`THRU`, `ALSO`) comme PROGRAM
COLLATING SEQUENCE, les classes utilisateur et SYMBOLIC CHARACTERS. Une
séquence de collation littérale suit `validate_alphabet` et
`cb_validate_collating` de cobc : pondération de chaque octet, LOW-VALUE et
HIGH-VALUE déduits de l'alphabet, comparaisons alphanumériques et SORT du
module selon cette table ; deux littéraux comparés par `=` ou `<>` sont pliés
sur leurs octets bruts, comme dans tree.c. `CURRENCY SIGN IS "c"` (un
caractère, contrôles de `set_currency_picture_symbol`) et `DECIMAL-POINT IS
COMMA` sont des réglages du module (`COB_MODULE_PTR`) : le scanner lit alors
1,5 comme un littéral, les PICTURE échangent `.` et `,`, et l'édition, le MOVE
alphanumérique vers numérique, la dé-édition, NUMVAL/NUMVAL-C et l'affichage
d'un nombre à décimales utilisent ces symboles. `CURRENCY … PICTURE SYMBOL` et
SORT … COLLATING SEQUENCE avec un alphabet littéral restent refusés. Une
clause FD `CODE-SET` avec un alphabet natif est ignorée, comme cobc sur une
machine ASCII ; les autres alphabets sont refusés.
ACCEPT reproduit `cob_accept`.

## SEARCH, USAGE INDEX et INSPECT

`SEARCH` (index VARYING ou premier index de la table, AT END, WHEN multiples)
et `SEARCH ALL` (recherche dichotomique de cobc sur les clés ASCENDING/
DESCENDING) suivent le code généré par cobc. `USAGE INDEX` explicite est un
entier natif de 4 octets petit-boutiste, copié brut vers un groupe.
`INSPECT` TALLYING, REPLACING et CONVERTING, avec BEFORE/AFTER INITIAL, est un
portage de `strings.c` : marqueurs et tampon de remplacement statiques partagés
entre instructions (y compris le marquage incomplet de LEADING en TALLYING),
signe incrusté retiré puis remis, compteurs mis à jour par `cob_add_int`
(troncature des chiffres de poids fort). Un accès hors des tampons de libcob,
qui ferait planter le programme natif, est un arrêt nommé. Les cibles binaires
ou packées et INSPECT BACKWARD restent refusés.

`EVALUATE` suit `cb_emit_evaluate` : sujets multiples `ALSO`, `TRUE`/`FALSE`,
objets `ANY`, `NOT`, `THRU`, conditions, lignes `WHEN` consécutives partageant
les mêmes instructions, et mêmes comparaisons qu'un `IF`. Sans `END-IF`, un
`ELSE` se rattache au `IF` ouvert le plus proche. Un niveau 88 de groupe
compare la zone en alphanumérique. Comme le scanner de cobc, un signe collé à
des chiffres après un opérande est un littéral signé : `T(I +1)` a deux
sous-scripts.

## Conditions, STRING et UNSTRING

Les conditions sont construites par un portage de `cb_build_expr` (pile de
priorités de typeck.c) : conditions abrégées (`A = 1 OR 2`,
`A NOT = B AND > C`), place du NOT, conditions de signe POSITIVE/NEGATIVE/ZERO
et de classe ALPHABETIC(-UPPER/-LOWER), NUMERIC et CLASS utilisateur.
`STRING` (DELIMITED BY, POINTER, ON OVERFLOW) et `UNSTRING` (DELIMITED BY
[ALL] … OR …, DELIMITER IN, COUNT IN, POINTER, TALLYING, ON OVERFLOW)
reprennent `strings.c`, y compris la règle de NOT ON OVERFLOW (aucune
exception levée). Les mots réservés de cobc sont refusés comme noms : la
liste par défaut, ou celle de `config/cobol85.words` avec `--std cobol85`
(NOTHING y redevient un nom, AUTHOR y est réservé). Deux articles frères de même
nom sont acceptés ; seule une référence ambiguë à l'un d'eux est refusée.

## Fichiers, RENAMES, exponentiation

Les clauses SELECT s'écrivent dans n'importe quel ordre ; PADDING CHARACTER
(obsolète) et RECORD DELIMITER STANDARD-1 sont ignorés comme par cobc, VALUE OF
du FD aussi. `SAME RECORD AREA` partage la zone d'enregistrement du premier FD
du groupe (`finalize_file`). Le niveau 66 `RENAMES … [THRU …]` est un alias de
la zone (alphanumérique pour une plage ou un groupe), un REDEFINES de niveau 01
plus grand agrandit la zone (octets supplémentaires nuls). Un 66 peut reprendre le
nom d'un article de son enregistrement : seule une référence non qualifiée est
ambiguë, comme dans `cb_ref`. `**` suit
`cob_decimal_pow` pour les exposants entiers (associatif à droite dans
COMPUTE, à gauche dans les conditions) ; un exposant littéral négatif est
refusé car cob_decimal_pow modifie la constante décimale partagée par cobc.
`MOVE -0` laisse un zéro négatif dans un DISPLAY signé. Un champ DISPLAY non
signé se compare octet par octet à QUOTE, HIGH/LOW-VALUE ou ALL littéral.

## CORRESPONDING, troncature et dé-édition

`MOVE`, `ADD` et `SUBTRACT CORRESPONDING` appariement par nom comme
`emit_corresponding` (sans REDEFINES, OCCURS ni FILLER ; numériques
élémentaires seulement pour le calcul). Sans SIZE ERROR, un receveur DISPLAY
garde les chiffres de poids faible (`cob_decimal_get_display`) ; les receveurs
binaires ou packés, qui passent par d'autres routines de cobc, restent un arrêt
nommé en cas de dépassement. Un MOVE d'un champ édité vers un numérique suit
`cob_move_edited_to_display`.

## COPY REPLACING

`COPY` est développé où qu'il se trouve sur la ligne, et `REPLACING` suit le
portage de `replace.c` (`cobol2rust/copy_replace.py`) : textes de pplex
(mots, littéraux numériques et alphanumériques, autres caractères, espaces),
pseudo-texte `==…==` comparé sans tenir compte de la casse ni des espaces,
identifiants qualifiés ou indicés, littéraux. `COPY nom OF|IN bibliothèque`
cherche `bibliothèque/nom` comme `ppcopy` (tel quel puis dans chaque dossier
`-I`), puis le nom seul. L'instruction `REPLACE ==…== BY ==…== .` et
`REPLACE OFF` s'appliquent au texte qui suit, COPY développés compris (deux
filtres de `replace.c`) ; l'instruction est effacée et les numéros de ligne
conservés. `LEADING ==mot== BY ==…==` et `TRAILING` (COPY et REPLACE)
remplacent le début ou la fin d'un seul mot, comme `is_leading_or_trailing` et
`ppecho_leading_or_trailing` ; une cible littérale exige un mot plus long, une
cible de plusieurs mots est refusée comme par ppparse. REPLACE ALSO/LAST,
`COB_COPY_LIB_*` et REPLACING d'un copybook qui contient lui-même un COPY restent refusés. En format fixe, la
zone de séquence (colonnes 1-6) est ignorée quel que soit son contenu.
`--debugging-lines` reproduit `cobc -fdebugging-line`.
`SOURCE-COMPUTER ... WITH DEBUGGING MODE` et `USE FOR DEBUGGING` (procédures,
ALL PROCEDURES, fichiers) suivent cobc 3.2 ; les sections de débogage ne
s'exécutent qu'avec `COB_SET_DEBUG` vrai à l'exécution, comme libcob. La
surveillance d'articles (`USE FOR DEBUGGING ON [ALL REFERENCES OF] article`)
suit `cb_check_field_debug` : après MOVE, COMPUTE, ADD/SUBTRACT/MULTIPLY/DIVIDE
sans SIZE ERROR, IF et DISPLAY, sous le commutateur, DEBUG-NAME (nom et
qualificatifs écrits), DEBUG-CONTENTS, DEBUG-SUB-1..3 (sous-scripts ou espaces)
puis la section, une fois par article et par instruction, pour un receveur ou
pour toute référence avec ALL ; l'IF est débogué après ses branches comme dans
le C de cobc. GO TO DEPENDING (ALL), PERFORM VARYING/AFTER (valeur initiale,
pas, comparaisons de l'UNTIL en `cob_cmp`) et l'enregistrement d'un WRITE ou
REWRITE suivent le code inline de codegen.c/typeck.c. Un article surveillé dans
une autre instruction, un article indicé ou une référence modifiée sont
refusés. `--fno-ec-data-incompatible` (convert, verify) reproduit
`cobc -fno-ec=data-incompatible` : sans `cob_check_numeric`, le MOVE vers
alphanumérique d'un article à signe séparé invalide copie ses chiffres tels
quels et réécrit l'octet de signe (`COB_PUT_SIGN`) ; sans l'option ce cas reste
un arrêt nommé, comme `--debug` arrête cobc.
Sans `--runtime-checks`, les données numériques invalides se lisent comme
libcob sans `-debug` : chaque octet DISPLAY vaut son quartet bas (`COB_D2I`),
un premier octet X"FF" ou X"00" vaut ±10^taille en lecture décimale
(`cob_decimal_set_display`), le packé garde ses quartets (tout signe autre que
D est positif). Les comparaisons numériques reprennent la routine choisie par
cobc (`memcmp` entre DISPLAY non signés de même description, `cob_cmp_numdisp`,
`cob_cmp_llint`, `cob_numeric_cmp`, `cob_cmp` en DEBUGGING MODE), le MOVE entre
articles de même description copie les octets (`cb_build_move_field`), DISPLAY
montre l'article tel qu'il est stocké (`cob_move_display_to_edited`) et les
clés numériques de SORT passent par `cob_numeric_cmp`. Restent des arrêts
nommés : DISPLAY signé ou binaire invalide, quartet packé supérieur à 9, indice
hors bornes. `--runtime-checks` (convert, verify ; `cobc -debug` pour
l'original) rétablit l'arrêt sur toute donnée invalide.
`--std {default,cobol85}` (convert, verify) choisit le dialecte cobc modélisé ;
`verify --std cobol85` compile aussi l'original avec `-std=cobol85`. Seule
différences modélisées à ce jour : `section-segments` (numéros de segment
ignorés par défaut, actifs en cobol85) et `defaultbyte` (`init` par défaut :
données sans VALUE initialisées selon leur PICTURE, index INDEXED BY à 1 ;
`none` en cobol85 : mémoire laissée à zéro binaire, index à 0). `tools/nist_verify.py` convertit en
cobol85 et compile l'original avec les options de report.pl
(`-std=cobol85 --debug`) ; `tools/verify.py` lit `standards` dans le JSON
d'une fixture pour la vérifier sous plusieurs dialectes.

## Calcul décimal et limites explicites

Le moteur utilise des coefficients entiers décimaux de précision arbitraire.
Il préserve les échelles des opérandes et reproduit le décalage de **38 chiffres
de la division GnuCOBOL 3.2**, puis applique troncature ou arrondi à la destination.
Par exemple, `COMPUTE X = (1 / 3) * 3` ne doit pas être simplifié en `X = 1`.
Ce choix est fondé sur le comportement de l'oracle et le code de
[`cob_decimal_div`](https://gnucobol.sourceforge.io/doxygen/gnucobol-2/numeric_8c_source.html).
Il ne promet pas de reproduire tous les modes arithmétiques IBM/Micro Focus.

Avec `ON SIZE ERROR` ou `NOT ON SIZE ERROR`, une division par zéro ou un résultat
hors de la PICTURE sélectionne la branche d'erreur et conserve la destination.
La branche NOT ON est exécutée seulement en cas de réussite. Les arrondis sont
appliqués avant le contrôle de débordement. Le signe est retiré pour un résultat
négatif dans une destination non signée, comme dans les cas GnuCOBOL testés.
Les données numériques invalides et les limites de capacité intermédiaire
restent des arrêts explicites ; elles ne sont pas absorbées par SIZE ERROR.

Sans ces clauses, une division par zéro dans une instruction arithmétique
rend le résultat NaN comme `cob_decimal_div` : la destination garde sa valeur
et l'exécution continue (dans une condition, elle reste un arrêt nommé).
Pour les destinations numériques non éditées, une valeur hors de la PICTURE, un signe négatif dans un
champ non signé ou une saisie numérique invalide provoque un arrêt explicite,
avec la ligne COBOL et le code **70**. Les intermédiaires dépassant 1024 décimales
ou 4096 chiffres sont aussi refusés. Ce choix conservateur diffère volontairement
des cas où un runtime COBOL tronquerait un dépassement ou continuerait après
une entrée invalide.

## Images numériques éditées

Le sous-ensemble comprend notamment `-9(9).9(9)`, `-.9(18)`, `+9(3).99`,
`9(3).99` et `ZZZ9.99`. Les signes sont fixes ; les Z doivent précéder des 9
entiers obligatoires. Les décimales sont des 9, avec un point explicite.
La capacité reste limitée à 18 positions numériques ; le signe et le point
occupent des octets supplémentaires (20 octets pour `-9(9).9(9)`).

Ces champs gardent une catégorie distincte : ils s'affichent et se copient vers
PIC X en octets bruts. MOVE depuis un nombre, COMPUTE et GIVING peuvent les
alimenter. Le moteur ajuste l'échelle, applique ROUNDED si demandé, puis
tronque les chiffres excédentaires à gauche comme GnuCOBOL. Le signe est fixé
après ajustement d'échelle, avant cette troncature. INITIALIZE et l'absence
de VALUE donnent zéro formaté ; un VALUE textuel copie ses octets tels quels
et complète à droite par des espaces.

IS NUMERIC vérifie les octets présents, même lorsque REDEFINES les a modifiés.
Les comparaisons et sujets/cas EVALUATE portant directement sur un champ édité
restent refusés : l'optimisation de constantes GnuCOBOL peut dépendre de sa
PICTURE et ne correspond pas toujours à une comparaison des octets affichés.
Copier vers PIC X ou utiliser une sous-chaîne alphanumérique explicite permet
de comparer les octets.
La déédition vers un nombre ou une autre image éditée, ACCEPT édité,
l'utilisation comme opérande arithmétique et SIZE ERROR
sur une destination éditée restent refusés. Les signes flottants, séparateurs
de milliers, devises, CR/DB et autres formes non décrites restent hors périmètre.

```powershell
python -m cobol2rust verify tests/fixtures/edited_report.cob
```

Cette fixture combine arrondis, suppression Z, FD partagés et rapport imprimé.

## Groupes, tableaux et mémoire partagée

Les groupes, leurs sous-champs et leurs vues REDEFINES partagent réellement les
mêmes octets. Un MOVE de groupe copie les octets, sans convertir ses colonnes.
Un MOVE vers plusieurs destinations résout l'adresse de sa source une seule fois
et relit cette zone pour chaque destination, conformément aux cas GnuCOBOL testés.
Cette distinction est nécessaire lorsque la première destination recouvre la
source. Le corpus vérifie aussi les sous-chaînes qui se recouvrent.

Le profil mémoire implémenté est celui des options par défaut du GnuCOBOL 3.2
utilisé comme oracle : tailles binaires `1-2-4-8`, ordre **big-endian** pour
COMP/BINARY, décimal compacté COMP-3 avec signe final, et signe DISPLAY ASCII
dans le dernier caractère. Par exemple, une colonne signée négative peut finir
par une lettre `p` à `y` dans sa représentation brute. Un affichage numérique
conserve le signe et le point décimal ; un affichage du groupe écrit ses octets.
Ce profil est consigné dans le rapport de conversion et de vérification. Il ne
couvre pas les options mémoire IBM/Micro Focus, l'EBCDIC, `SIGN SEPARATE`,
`SYNCHRONIZED` ni les variantes de taille/ordre COMP configurées autrement.

Les sous-scripts sont contrôlés à l'exécution, à partir de 1. Une dimension
manquante ou un nom ambigu est refusé pendant la conversion ; un indice ou une
sous-chaîne hors limites provoque un arrêt nommé avec le code 70.

Les tables `OCCURS min TO max DEPENDING ON compteur` réservent leur capacité
maximale. La longueur active des groupes et le nombre d'éléments de SORT
suivent le compteur. Un accès indexé sans `--runtime-checks` peut viser toute
la capacité déclarée, comme GnuCOBOL sans `-debug`, sans lire le compteur.
Avec les contrôles, le compteur puis la borne courante sont vérifiés.
Celui-ci doit être un entier scalaire non ambigu. La table doit terminer
tous ses groupes parents, sans OCCURS
englobant, REDEFINES ni enregistrement FD variable. Ses éléments peuvent être
des groupes avec tableaux fixes imbriqués. Un compteur hors bornes lu pour
calculer une étendue active provoque un arrêt explicite ; un indice hors de
la capacité physique reste un arrêt nommé dans les deux profils.

Les index `INDEXED BY` démarrent à 1 et peuvent servir de sous-scripts, de
variables PERFORM VARYING ou être transférés par MOVE. Le sous-ensemble actuel
les représente comme des ordinaux entiers signés de 32 bits, affichés avec au
moins 9 chiffres et un signe. Les opérations
SET numériques visent les index déclarés ; UP/DOWN relisent leur opérande pour
chaque index destinataire. Les index au-delà de cette capacité
provoquent un arrêt de capacité.

Les niveaux 88 testent leur donnée parente ; ils n'ajoutent pas de mémoire.
`SET condition TO TRUE` choisit la première valeur déclarée. `SET ... TO FALSE`
requiert une clause `WHEN SET TO FALSE` explicite. `INITIALIZE` ignore les FILLER
et les vues REDEFINES subordonnées ; `WITH FILLER` inclut les FILLER. Une vue
REDEFINES nommée directement peut être initialisée. `INITIALIZE … REPLACING
{ALPHABETIC|ALPHANUMERIC|NUMERIC|ALPHANUMERIC-EDITED|NUMERIC-EDITED} [DATA] BY
valeur` suit `output_initialize_one` : un MOVE vers chaque article élémentaire
de la catégorie, occurrence par occurrence, les autres articles restant
inchangés ; VALUE et DEFAULT (COBOL 2002) restent refusés.

Un groupe OCCURS DEPENDING peut contenir son propre contrôleur, être un
enregistrement FD ou le partager avec les autres 01 du FD. Comme le
`flag_receiving` de `cb_build_move`, un récepteur de MOVE (READ/RETURN INTO
compris) qui contient son contrôleur prend sa longueur maximale ; les autres
usages, et WRITE/REWRITE de l'enregistrement, prennent la longueur courante.

L'initialisation d'une occurrence variable précise, par exemple
`INITIALIZE ligne(index)`, est prise en charge. L'initialisation du groupe
variable entier est limitée au cas vérifié de champs texte uniformes avec
table variable élémentaire ; elle remet alors toute la capacité à espaces.
Les autres INITIALIZE de groupes variables sont refusés car GnuCOBOL 3.2 utilise
plusieurs stratégies de génération dont les effets ne sont pas encore reproduits.

`IS NUMERIC` permet de contrôler une colonne avant son utilisation numérique.
Les enregistrements peuvent donc contenir des chiffres invalides qui sont traités
par une branche de rejet. Utiliser ces données comme un nombre sans validation
provoque un arrêt explicite.

## Exemple de traitement par lots

```powershell
python -m cobol2rust verify examples/batch_accounts.cob --data-dir examples/batch_accounts.data
```

Cet exemple lit un fichier de mouvements à colonnes fixes, valide les numéros de
compte et montants, applique crédits et débits à un tableau de soldes COMP-3 puis
écrit `balances.txt`. Il combine fichiers structurés, OCCURS, niveaux 88,
EVALUATE TRUE et contrôles NUMERIC. Le jeu fourni donne **4 mouvements acceptés,
3 rejetés** et des soldes de **7,50 ; 100,00 ; -5,00 ; 0 ; 0**.

Un second exemple combine fichiers, table variable COMP-3, index et gestion
des dépassements de total :

```powershell
python -m cobol2rust verify examples/variable_batch.cob --data-dir examples/variable_batch.data
```

Il charge quatre montants, rejette deux lignes et conserve le total précédent
lors d'un dépassement. Résultat attendu :
`LOADED=4 REJECTED=02 OVERFLOWS=01 TOTAL=0016.75`.
Le fichier `summary.txt` contient la représentation brute `TOTAL=001675`.

Il s'agit d'un exemple d'intégration du corpus, pas d'une application métier
existante portée dans son ensemble.

## Auditer un dossier avant conversion

```powershell
python -m cobol2rust audit chemin/sources -I chemin/copybooks -o build/audit.json
```

L'audit parcourt les fichiers `.cob` et `.cbl`, vérifie le parsing, la disposition
mémoire et l'émission Rust, puis conserve le premier blocage de chaque source.
Il ignore notamment `.tools`, `build`, `target` et les environnements virtuels.
Il n'exécute aucun programme et ne prouve aucune équivalence de comportement.
Un code de retour 1 signale des sources bloquées ; `accepted_by_frontend=true`
signifie qu'il faut ensuite compiler et vérifier le programme avec ses données.

## Vérifier le comportement

```powershell
python -m unittest discover -v
python tools/verify.py
python tools/verify_cases.py --report build/real-input-cases.json
python -m cobol2rust verify examples/invoice.cob -o build/controle-facture.json
```

`verify` compile et **exécute** le source donné avec GnuCOBOL et Rust. Il compare
stdout et les fichiers finaux octet pour octet et exige deux codes de retour nuls. Fournir des sources
de confiance ; `--stdin-file entrees.txt` permet de donner les mêmes entrées aux
deux programmes. Le rapport décrit uniquement les entrées testées.

`tools/verify.py` et le sous-ordre `verify` compilent désormais le **source
original** côté GnuCOBOL. Cela vérifie indépendamment les formats et les COPY,
en plus de la traduction Rust. Voir [tools/README.md](tools/README.md).

`tools/verify_cases.py` lit un manifeste de scénarios, par défaut
`measurements/real-input-cases.json`. Chaque cas décrit le source, le stdin,
les dossiers d'entrée et le profil d'exécution ; leurs empreintes sont
contrôlées avant les comparaisons. Le même moteur traite tous les cas et
conserve les écarts et délais dans le dénominateur. Cette campagne possède
son propre rapport, séparé de la mesure des corpus à stdin vide.

## Fichiers texte séquentiels

```powershell
python -m cobol2rust verify examples/files.cob -o build/controle-fichiers.json
python -m cobol2rust convert examples/files.cob -o build/mes-fichiers --run
python -m cobol2rust verify tests/fixtures/file_copy.cob --data-dir tests/fixtures/file_copy.data
```

La démo crée `transactions.txt`, ajoute une troisième transaction, puis relit
les trois lignes. Les chemins relatifs d'un programme généré sont résolus depuis
son dossier d'exécution. `convert --run` utilise le dossier du projet Cargo
produit ; un exécutable lancé directement utilise le dossier courant.

Le vérificateur prépare **deux dossiers distincts**, y copie les données de
`--data-dir` et y lance chaque programme. Il conserve les données originales et
compare les noms et les octets de tous les fichiers finaux, y compris les entrées
modifiées. Les empreintes et les différences sont enregistrées dans le rapport.
Le vérificateur accepte seulement les chemins ASSIGN et `--file-env` relatifs sans `..` ; la
conversion seule peut conserver un chemin absolu. L'exécution n'est pas un bac
à sable pour des sources non fiables.

Périmètre précis du runtime de fichiers :

- `ORGANIZATION LINE SEQUENTIAL` explicite ou imposée par un périphérique.
- `ASSIGN` comme cobc (`assign_clause`) : littéral ; nom non déclaré pris comme
  nom de fichier tel qu'écrit (`implicit-assign-dynamic-var`) ; donnée lue à
  chaque OPEN (`ASSIGN TO donnée`, `ASSIGN USING`, `DYNAMIC`) ; `EXTERNAL` et
  `-std=cobol85` sans les étiquettes `UT-S-` ; périphériques DISK/DISC/TAPE/
  RANDOM (nom du SELECT sans nom) et CARD-READER… (LINE SEQUENTIAL). Refusés :
  DISPLAY, KEYBOARD, PRINTER, LINE ADVANCING FILE, DISK FROM.
- Noms résolus à l'OPEN comme `cob_chk_file_mapping` : `DD_nom`, `dd_nom`,
  `nom`, éléments `$VAR` des chemins et préfixe `COB_FILE_PATH`, avec les
  particularités de libcob vérifiées ; nom vide ou mal cité : statut 31.
  `verify --file-env NOM=chemin` fournit ces variables aux deux exécutions.
- Un enregistrement `01` par `FD`, sans `VALUE` : PIC X élémentaire ou groupe
  contenant des colonnes texte et numériques DISPLAY, avec FILLER et niveaux 88.
  Les champs COMP/COMP-3 dans LINE SEQUENTIAL sont refusés.
- Octets quelconques comme `lineseq_read`/`lineseq_write` : fins de ligne LF ou
  CRLF (un CR isolé est une donnée), lignes courtes complétées par des espaces,
  espaces finaux retirés à l'écriture sauf avec `COB_LS_FIXED=1`. Avec
  `COB_LS_VALIDATE` (défaut), un caractère de contrôle lu donne le statut 09 ;
  à l'écriture, le statut 71 suit la macro `IS_BAD_CHAR (*p++)` de libcob, qui
  juge un octet de contrôle avec les octets qui le suivent.
- Statuts couverts : `00`, `04`, `05`, `10`, `30`, `35`, `37`, `41`, `42`, `46`,
  `47`, `48`. `FILE STATUS` doit être un champ `PIC XX` ou `PIC 99 DISPLAY`.
  Sans `FILE STATUS` ni gestionnaire, une exception de fichier est
  `cob_fatal_error` : message `libcob: error: … (status = nn) for file …` sur
  stderr, avertissements `implicit CLOSE` des fichiers restés ouverts, code de
  sortie 1 ; ces avertissements suivent aussi STOP RUN. `AT END` traite la
  première fin de fichier ; la lecture suivante donne `46`.
- `COB_LS_SPLIT` suit la valeur par défaut GnuCOBOL 3.2 (`true`) : la suite
  d'une ligne trop longue devient l'enregistrement suivant (statut 06), avec
  le recul `fseek` de libcob, qui relit le dernier octet d'une dernière ligne
  pleine sans délimiteur. `COB_LS_SPLIT=0` tronque avec le statut `04`.
- `I-O`, `REWRITE`, verrouillage, profils de configuration externes et chemins
  SELECT identiques ouverts en même temps ne sont pas pris en charge en LINE SEQUENTIAL.
  Les accès concurrents et les alias de chemin ne sont pas validés.

```powershell
python -m cobol2rust verify tests/fixtures/file_read.cob --data-dir tests/fixtures/file_read.data --runtime-env COB_LS_SPLIT=0
```

Les paramètres `COB_LS_FIXED` et `COB_LS_SPLIT` fournis à `verify` apparaissent
explicitement dans son rapport. La suite lit leurs valeurs dans les fichiers
JSON associés aux fixtures ; les dossiers `.data` contiennent les entrées.

## Fichiers SEQUENTIAL fixes et rapports

```powershell
python -m cobol2rust verify tests/fixtures/sequential_records.cob
python -m cobol2rust verify tests/fixtures/sequential_report.cob
```

`ORGANIZATION SEQUENTIAL`, explicite ou implicite, conserve les enregistrements
fixes octet pour octet et les concatène sans séparateur. Les groupes peuvent
contenir COMP/BINARY et COMP-3 ; un octet nul ou LF reste une donnée. Il ne faut
pas assimiler ce format au texte LINE SEQUENTIAL décrit plus haut.

Plusieurs descriptions `01` d'un même FD partagent la même mémoire et `WRITE`
utilise la description nommée. Des tailles différentes sélectionnent le format
variable à en-têtes de libcob (voir RECORD VARYING plus haut).

En LINE SEQUENTIAL, des 01 de tailles différentes sont acceptés : WRITE écrit
la taille de l'enregistrement nommé, le minimum vaut 0 (`finalize_file`, même
avec RECORD VARYING FROM), READ complète la zone par des espaces et READ INTO
déplace les octets lus (`lineseq_read` fixe la taille de l'enregistrement).

Une lecture finale partielle conserve la queue précédente du buffer FD et
retourne `00` dans le profil GnuCOBOL vérifié, puis `10` et `46` aux lectures
suivantes. `READ INTO` copie uniquement les octets effectivement lus, puis
complète sa destination, au lieu de recopier cette queue ancienne.

`WRITE ... BEFORE/AFTER ADVANCING` est pris en charge pour ces fichiers et
pour LINE SEQUENTIAL avec PAGE, un mnémonique FORMFEED (S01-S05, CSP, TOP) ou
canal C01-C12 (une page, comme `cb_build_write_advancing_mnemonic`), un entier
littéral, ZERO ou un identificateur numérique de 0 à 65535 lignes (hors de cette
plage cobc corromprait l'option : arrêt nommé). Les contrôles sont les octets
LF (lignes), CR (zéro ligne) et FF (PAGE). AFTER écrit le contrôle avant le
record ; BEFORE l'écrit après ; un WRITE LINE SEQUENTIAL sans ADVANCING vaut
BEFORE 1 LINE (`cb_emit_write`). Les espaces des records SEQUENTIAL sont
conservés. Un LF final restant après AFTER est écrit à CLOSE ou à la fermeture
implicite de STOP RUN. OPEN réinitialise cet état.

La clause FD `LINAGE [IS] n [LINES] [WITH FOOTING [AT] f] [LINES AT TOP t]
[LINES AT BOTTOM b]` (entiers ou noms de données) rend le fichier LINE
SEQUENTIAL et suit `cob_linage_write_opt` : marge haute due au premier WRITE,
page logique de n lignes, saut vers la page suivante (lignes restantes, marge
basse, relecture des valeurs, marge haute), statut 57 si la géométrie lue est
invalide. `LINAGE-COUNTER [IN|OF fichier]` est lisible (registre `unsigned int`
affiché sur 10 chiffres) ; `AT END-OF-PAGE`/`NOT AT END-OF-PAGE` reproduisent
`check_eop` et `output_ferror_stmt`. Après un OPEN en 57, libcob garde le mode
ouvert sur un `FILE *` fermé : un nouvel OPEN rend 41, toute autre opération est
un arrêt nommé. Une écriture dans LINAGE-COUNTER et l'OPEN INPUT d'un fichier
LINAGE restent refusés.

La COMMUNICATION SECTION suit cobc 3.2, qui l'analyse sans l'implémenter
(`CB_PENDING`) : acceptée seulement avec `--std cobol85` (non conforme sinon),
`CD nom FOR [INITIAL] INPUT | OUTPUT | [INITIAL] I-O` sans autre clause, puis ses
enregistrements 01 (stockage statique jamais initialisé : VALUE ignoré, les
suivants redéfinissent le premier). ENABLE, DISABLE, PURGE, RECEIVE (ses
instructions NO DATA et WITH DATA sont analysées puis abandonnées), SEND et
`ACCEPT cd MESSAGE COUNT` ne font que mettre à jour DEBUG-LINE ; un CD cible de
USE FOR DEBUGGING ne déclenche donc rien mais agrandit DEBUG-CONTENTS. Comme la
PROCEDURE DIVISION est analysée avec la taille par défaut de 30 octets, `FUNCTION
LENGTH` de DEBUG-CONTENTS ou DEBUG-ITEM et les positions constantes d'une
modification de référence utilisent cette taille, comme dans cobc.

Le Report Writer suit `reportio.c` : un FD
`REPORT [IS] r` (un seul rapport par fichier, sans enregistrement décrit) rend le
fichier LINE SEQUENTIAL ; la REPORT SECTION décrit `RD r PAGE [LIMIT IS|LIMITS
ARE] n [LINES] [HEADING h] [FIRST DETAIL f] [LAST DETAIL l] [FOOTING g]`
(entiers littéraux, valeurs par défaut et contrôles de `page_limit_clause`,
précédés de `CONTROL[S] [IS|ARE] [FINAL] identifiants`,
`finalize_report` et `cob_report_initiate` ; sans clause PAGE les limites
valent 0 avec FIRST DETAIL 1, comme dans le `cob_report` émis par cobc, si bien
que chaque ligne dépasse LAST DETAIL 0 et change de page ; un LINE au-delà de la
limite fait échouer INITIATE comme `limitCheckOneLine`, le GENERATE suivant est un
arrêt nommé), puis des groupes 01 `TYPE` REPORT
HEADING/RH, PAGE HEADING/PH, CONTROL HEADING/CH et CONTROL FOOTING/CF
[identifiant | FINAL], DETAIL/DE, PAGE FOOTING/PF, REPORT FOOTING/RF avec
`LINE [NUMBER] [IS] [PLUS] n` au niveau 01 ou sur leurs articles et `NEXT GROUP
[IS] [PLUS] n | NEXT PAGE` au niveau 01, et des articles élémentaires
`PICTURE`, `COLUMN [NUMBER] [IS] n`, `GROUP [INDICATE]` et soit `SOURCE`
(identifiant, indicé compris, LINE-COUNTER ou PAGE-COUNTER), soit `SUM`
d'identifiants numériques DISPLAY ou d'autres articles SUM (`RESET ON` analysé
et sans effet, comme dans codegen.c), soit `VALUE [ALL]` alphanumérique. Les
ruptures suivent `cob_report_generate` et `cob_report_terminate` : la liste
CONTROLS de cobc va du contrôle le plus mineur au plus majeur (chaque
identifiant est préfixé), un changement rompt aussi les contrôles de séquence
inférieure, les pieds de contrôle s'impriment avec la valeur précédente du
contrôle, les compteurs SUM (`build_sum_counter` : `S9(n+2)V9(s)` en
WORKING-STORAGE) s'additionnent à chaque GENERATE, se reportent dans les
compteurs qui les somment et se remettent à zéro au pied de leur groupe, dans
l'ordre de la liste `sum_prv` de codegen.c ; CONTROL HEADING FINAL n'est jamais
imprimé par libcob 3.2. Les lignes et champs
reprennent `output_report_define_lines` ; la taille d'enregistrement est le
`rcsz` de cobc. `INITIATE`, `GENERATE` groupe DETAIL ou nom de rapport et
`TERMINATE` reproduisent `do_page_heading`, `do_page_footing`, `report_line` et
`report_line_type` (écritures BEFORE n LINES, lignes vides, sauts de page).

Une SOURCE indicée, modifiée par référence ou issue de LOCAL-STORAGE possède
un temporaire distinct en WORKING-STORAGE, comme `cb_field_dup`. Ce temporaire
est typé : DISPLAY signé pour une source numérique ou éditée, PIC X pour les
autres sources ; une longueur littérale de sous-chaîne impose PIC X de cette
longueur. Son initialisation reprend ZERO ou SPACE selon la catégorie de la
source. Les MOVE de préparation précèdent les ruptures de contrôle : un pied
peut donc afficher l'ancienne valeur du contrôle avec la nouvelle valeur d'une
SOURCE indicée. GENERATE exécute successivement les deux passes natives ;
TERMINATE exécute seulement la passe des pieds de rapport et de contrôle.
Les références simples, sans indice ni sous-chaîne et hors LOCAL-STORAGE,
restent lues à l'impression ; LINE-COUNTER, PAGE-COUNTER et les compteurs SUM
restent également lus à ce moment. L'état persistant de parcours de
`cb_emit_report_moves`, y compris son bogue avec un pied élémentaire sans
enfants, est conservé : l'ordre de première utilisation des rapports dans
INITIATE/GENERATE/TERMINATE peut changer les préparations émises.

Les positions constantes des sous-chaînes SOURCE suivent le repli de cobc et
la lecture des chiffres du littéral par `cb_get_int` : le point décimal ne
réduit pas leur coefficient. Les expressions entières exécutées suivent les
étapes de calcul en entier C. Les dépassements lors du repli constant et les
puissances non repliées ou divisions par une constante zéro restent des refus
nommés. Ce traitement concerne les références SOURCE des rapports ; les limites
générales de lecture des indices
et des champs numériques restent applicables.
Restent refusées les SOURCE complexes de groupes ou USAGE INDEX, les PICTURE
à P initial dont la copie native est invalide et les contrôles en
LOCAL-STORAGE dont le descripteur natif n'est pas constant. LOCAL-STORAGE
reste refusé sous `--std cobol85`, comme par GnuCOBOL 3.2.

`LINE-COUNTER`/`PAGE-COUNTER [IN|OF r]` sont lisibles comme des nombres et
affichés sur 10 chiffres. Restent refusés : PRESENT/ABSENT WHEN, SUPPRESS,
SUM UPON, SUM d'opérandes non DISPLAY, CF ALL et OR PAGE, OCCURS, COLUMN
PLUS/LEFT/RIGHT/CENTER, LINE NEXT PAGE, CODE, PAGE ... COLUMNS, limites données par des noms de données, USE
BEFORE REPORTING, plusieurs rapports par FD, READ/WRITE d'un fichier de
rapport ; un INITIATE d'un rapport actif ou un GENERATE/TERMINATE sans
INITIATE est un arrêt nommé.

Les clauses FD `LABEL RECORDS OMITTED/STANDARD`, `BLOCK CONTAINS` (en records
ou caractères, éventuellement sous forme de plage) et `RECORDING MODE` (F, V,
FIXED, VARIABLE ; U et S pour un fichier SEQUENTIAL, ignorés comme par cobc)
sont acceptées dans le profil disque GnuCOBOL vérifié. LABEL/BLOCK sont conservées
dans les métadonnées sans ajouter de labels ni de blocage physique. Une clause
`RECORD CONTAINS n CHARACTERS` exige que n égale la taille physique de chaque
description FD ; sinon le compilateur natif pourrait sélectionner un format
variable et la conversion est refusée. `DATA RECORD(S) [IS|ARE] nom...` est
conservée comme métadonnée : GnuCOBOL n'en résout pas les noms et ne lui donne
aucun effet ; la clause en double ou sans nom reste refusée.

Les fichiers INDEXED suivent le gestionnaire Berkeley DB de libcob 3.2
(clé principale, clés alternées avec ou sans doublons, START, READ KEY,
DELETE, REWRITE), dans un format disque propre à cobol2rust (`nom`, `nom.1`,
...) qui n'est pas interchangeable avec les fichiers BDB de GnuCOBOL ; le
vérificateur compare leur contenu logique (`cobol2rust/bdb_dump.c`, libdb).
Les autres clauses FD et les clés INDEXED composées (SOURCE IS), SUPPRESS ou READ PREVIOUS restent refusés. Le vérificateur refuse les réglages de concaténation de fichiers non
modélisés (`COB_SEQ_CONCAT_NAME`, `COB_SEQ_CONCAT_SEP`). Les options `COB_LS_FIXED`
et `COB_LS_SPLIT` s'appliquent seulement au runtime LINE SEQUENTIAL.

## Sans code source : inspection et préparation

```powershell
python -m cobol2rust inspect chemin/application.exe -o build/inspection.json
```

Cette commande lit le binaire sans le lancer. Elle relève format, architecture,
sections, bibliothèques importées, symboles et indices de runtime COBOL. Les
chaînes de caractères sont des indices, pas une preuve du langage d'origine.
Les exécutables ELF sans table de sections donnent moins d'informations.

Le rapport propose aussi les commandes ARET `info`, `imports` et `decompile`
pour x86/x86-64. `--aret chemin/aret.exe` remplace le nom de commande proposé.
**Aucune de ces commandes n'est exécutée automatiquement et aucun Rust n'est
produit à partir du binaire.**

L'exploration d'ARET dans le dossier voisin a confirmé que son pipeline chargeur
→ analyse → IR → émission peut servir de base au futur volet binaire. Son
backend actuel ne produit pas directement de Rust et la modélisation d'un
runtime COBOL reste à développer. Les modules mainframe z/OS ne sont pas pris
en charge par cet inspecteur.

## Suite du développement

1. Ajouter un corpus métier réel : sources, copybooks, fichiers d'entrée et
   sorties attendues. Épingler le dialecte et les options du compilateur source.
2. Étendre les tableaux variables aux dispositions plus complexes et à SEARCH,
   puis les autres profils mémoire et encodages, clauses de signe et images éditées.
3. Étendre les fichiers `LINE SEQUENTIAL` au découpage des lignes et aux
   autres modes ; ajouter les enregistrements variables/ISAM, appels
   interprogrammes et transactions selon les programmes ciblés.
4. Pour les binaires, commencer par **un compilateur/runtime et une architecture**
   (par exemple GnuCOBOL x86 PE), lever le code avec ARET, modéliser les appels
   `cob_*`, produire du Rust puis comparer les effets observables avec l'original.
5. Ajouter les autres familles de compilateurs et les formats mainframe après
   validation du premier parcours complet.

Référence de langage utilisée pour ce prototype :
[manuel GnuCOBOL](https://gnucobol.sourceforge.io/doc/gnucobol.html).
