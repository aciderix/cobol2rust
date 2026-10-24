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
(transitivement) forment une seule unité d'exécution Rust.

Le projet produit contient :

| Fichier | Contenu |
| --- | --- |
| `Cargo.toml` | Projet Rust ; bibliothèque d'entiers de précision arbitraire `num-bigint` épinglée à 0.4.6 |
| `src/main.rs` | Champs, instructions, conditions, boucles, sections et paragraphes traduits |
| `src/runtime.rs` | Arithmétique décimale, remplissage des champs, saisie et affichage |
| `src/storage_runtime.rs` | Mémoire partagée, disposition des données, tableaux, vues REDEFINES et sérialisation |
| `src/file_runtime.rs` | Fichiers LINE SEQUENTIAL et SEQUENTIAL fixes, présent quand le programme utilise des fichiers |
| `expanded.cob` | Source normalisé avec les COPY développés |
| `conversion.json` | Empreintes source/copybooks, champs et offsets, conditions, sections/blocs de procédure, profil mémoire et correspondance des lignes |

Le code Rust peut ensuite être compilé sur Windows ou sur Linux avec Cargo.
Les tests de la livraison ont été exécutés sur Windows. La reprise cloud a
également validé sous Linux 304 tests Python, avec un test d'inspection du PE
Windows ignoré (305 découverts), et les 96 comparaisons COBOL/Rust du corpus actuel.
Les détails sont dans [VALIDATION.md](VALIDATION.md).
Ces résultats portent sur les entrées testées.

## Périmètre actuel

| Domaine | Pris en charge |
| --- | --- |
| Sources | Format libre, format fixe explicite avec continuations de mots/nombres/PICTURE/littéraux, commentaires, directive `>>SOURCE FORMAT`, séparateurs virgule/point-virgule |
| Documentation COBOL | `AUTHOR`, `INSTALLATION`, `DATE-WRITTEN`, `DATE-COMPILED`, `SECURITY`, `REMARKS` avec point, en début de ligne dans IDENTIFICATION |
| Configuration | `ENVIRONMENT DIVISION`, `CONFIGURATION SECTION`, `SOURCE-COMPUTER` et `OBJECT-COMPUTER` avec nom machine seul |
| Copybooks | `COPY nom.` ou `COPY "nom.cpy".` seuls sur une ligne, recherche locale et `-I`, détection des cycles |
| Données | Groupes et champs de niveaux `01` à `49`, `77`, `PIC X`, `PIC 9`, `S`, `V`, `VALUE`, `FILLER` |
| Édition numérique | Signe fixe `+`/`-`, `9` et point décimal explicite ; `Z` initiaux suivis de `9` obligatoires ; rendu depuis une source numérique, copie brute vers texte |
| Tables et vues | `OCCURS n TIMES`, `OCCURS min TO max DEPENDING ON`, `INDEXED BY`, `SET index TO / UP BY / DOWN BY`, sous-scripts, noms qualifiés `OF`/`IN`, `REDEFINES`, sous-chaînes `champ(début:longueur)` |
| Conditions | Niveau `88`, listes et plages `THRU`, `SET TO TRUE/FALSE`, tests `IS [NOT] NUMERIC`, `EVALUATE TRUE` |
| Usages | `DISPLAY`, `COMP` / `BINARY` / `COMP-4`, `COMP-3` / `PACKED-DECIMAL`, alias `COMPUTATIONAL` |
| Calcul | `MOVE`, `COMPUTE`, `ADD ... TO`, `SUBTRACT ... FROM`, `MULTIPLY ... BY`, `DIVIDE ... INTO`, receveurs multiples et `GIVING` multiples avec `ROUNDED` par receveur, `ON SIZE ERROR` / `NOT ON SIZE ERROR` |
| MOVE numérique vers texte | Entier DISPLAY/COMP/COMP-3/index vers PIC X ou sous-chaîne ; copie brute vers groupe hors index ; chiffres lexicaux des littéraux et remplissage ZERO |
| MOVE depuis du texte | Champ PIC X ou sous-chaîne vers numérique/édité ; littéral texte vers édité ; groupe source copié brut vers numérique/édité |
| Comparaisons mixtes | Champ numérique face à une variable texte, groupe ou sous-chaîne ; littéral numérique non signé et ZERO face à du texte ; littéral texte face à un entier uniquement avec chiffres de même largeur |
| Contrôle | `IF` / `ELSE`, comparaisons explicites, `AND` / `OR` / `NOT`, `EVALUATE` simple, `GO [TO]` vers paragraphe/section, `GO TO ... DEPENDING [ON]` avec contrôleur entier de 9 chiffres au plus, `GO TO` sans cible et `ALTER` (label_N de cobc ; segments indépendants 50-99 remis à zéro comme codegen.c avec `--std cobol85`, ignorés par défaut comme `section-segments: ignore`), noms de procédure homonymes qualifiés `IN`/`OF` et noms entièrement numériques (règles de `cb_ref`), `PERFORM a THRU b` avec `b` avant `a`, `STOP littéral` (DISPLAY puis ACCEPT OMITTED ; le caractère 03, SIGINT pour libcob, est un arrêt nommé) |
| Boucles | `PERFORM ... TIMES`, `UNTIL`, `VARYING`, `WITH TEST BEFORE/AFTER` |
| Procédures | Sections et paragraphes, `PERFORM`, plages `THRU`/`THROUGH` mixtes, retours imbriqués/récursifs, enchaînement séquentiel, `EXIT PARAGRAPH`, `EXIT SECTION` dans une section explicite, `EXIT` nu sans effet |
| Console | `DISPLAY`, `WITH NO ADVANCING`, `ACCEPT` simple |
| Fichiers | LINE SEQUENTIAL texte DISPLAY ; SEQUENTIAL fixe brut, FD multiples de même taille, `OPEN INPUT/OUTPUT/EXTEND`, `OPEN I-O` et `REWRITE` en SEQUENTIAL ; RELATIVE en accès SEQUENTIAL/RANDOM/DYNAMIC avec `RELATIVE KEY`, `READ [NEXT]`, `WRITE`, `REWRITE`, `DELETE`, `START`, `INVALID KEY`, `READ`, `READ INTO`, `AT END`, `NOT AT END`, `WRITE`, `WRITE FROM`, `WRITE BEFORE/AFTER ADVANCING` en SEQUENTIAL, `CLOSE [WITH LOCK]`, `FILE STATUS`, `SELECT OPTIONAL`, DECLARATIVES `USE AFTER ERROR/EXCEPTION` par fichier ou mode |
| Autres | `INITIALIZE`, `INITIALIZE ... WITH FILLER`, `CONTINUE`, `STOP RUN`, `GOBACK` |

Les champs numériques sont limités à **18 chiffres**, les champs texte à
**256 caractères ASCII par champ élémentaire**. Un groupe peut être plus grand.
La mémoire totale est limitée à **16 Mio**, les tableaux à **7 dimensions** et
chaque clause OCCURS à **1..10000 occurrences** (minimum variable autorisé : 0).
Les clauses et variantes absentes
de cette liste ne sont pas réputées prises en charge.

Sont notamment refusés : tables variables à offsets ou strides variables,
niveaux 66/78,
REDEFINES indirects ou plus grands que la zone d'origine, `COMP-5`,
images éditées hors du sous-ensemble décrit ci-dessous, conditions abrégées,
fonctions intrinsèques hors liste ci-dessous (trigonométrie, LOG, SQRT,
STANDARD-DEVIATION, RANDOM, CURRENT-DATE, WHEN-COMPILED), appels externes,
`EXIT SECTION` hors section explicite, `EXIT PERFORM`, STOP identifiant,
fichiers à enregistrements variables, relatifs/indexés, SQL embarqué, CICS et
plusieurs programmes liés. Les formats binaires autres que les enregistrements
SEQUENTIAL fixes du profil pris en charge ne sont pas modélisés.
La déédition, les calculs sur texte et les calculs vers PIC X restent refusés.
Le MOVE d'un littéral texte vers un champ numérique ordinaire reste refusé :
les optimisations natives diffèrent du transfert depuis un champ PIC X.

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

CALL littéral ou par identifiant, USING BY REFERENCE/BY CONTENT, ON EXCEPTION/
OVERFLOW, NOT ON EXCEPTION, CANCEL, EXIT PROGRAM et GOBACK suivent GnuCOBOL 3.2
(`output_call` de codegen.c, `cob_call_field`/`cob_cancel` de call.c) :

- un appelé conserve sa WORKING-STORAGE entre deux CALL ; CANCEL la réinitialise
  et ferme ses fichiers ouverts ; CALL ou CANCEL d'un programme actif s'arrête ;
- les articles LINKAGE (et leurs REDEFINES) deviennent des vues sur la mémoire
  de l'argument ; BY CONTENT passe une copie ; un article LINKAGE plus long que
  son argument s'arrête au lieu de lire la mémoire voisine ;
- EXIT PROGRAM est sans effet dans le programme principal, GOBACK y vaut STOP RUN ;
  STOP RUN dans un appelé termine toute l'unité ;
- un nom introuvable prend ON EXCEPTION seulement s'il est sûrement absent : mot
  majuscule, ni routine système libcob (`SYSTEM`, `CBL_…`, `C$…`), ni source du
  chemin d'appel non convertie. Sinon la conversion ou l'exécution s'arrête.

Les programmes qui suivent `END PROGRAM` dans le même source sont des frères :
ils sont dans l'exécutable et GnuCOBOL les trouve avant le chemin d'appel.

Restent refusés : BY VALUE, OMITTED, RETURNING/GIVING, programmes imbriqués,
plusieurs programmes dans un source appelé, EXTERNAL/GLOBAL, LINKAGE hors de USING, VALUE en
LINKAGE, USING dans le programme principal, et `NOT ON EXCEPTION` suivant un
DISPLAY/ACCEPT/CALL de ON EXCEPTION (GnuCOBOL le rattache à ce DISPLAY).

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
séquentiels fixes, INPUT/OUTPUT PROCEDURE, RELEASE, RETURN) reproduisent le tri
stable de libcob. COLLATING SEQUENCE et les fichiers USING/GIVING variables
restent refusés.

## SPECIAL-NAMES, ACCEPT et DISPLAY UPON

SPECIAL-NAMES accepte les noms mnémoniques de périphériques (DISPLAY UPON
SYSOUT/CONSOLE/SYSERR, ACCEPT FROM SYSIN/CONSOLE), SWITCH-n avec conditions
ON/OFF et SET … TO ON/OFF (état initial lu dans `COB_SWITCH_n`, comme libcob),
les alphabets NATIVE, STANDARD-1, STANDARD-2 et ASCII (sans effet sur une
machine ASCII, y compris en PROGRAM COLLATING SEQUENCE), les classes
utilisateur et SYMBOLIC CHARACTERS. CURRENCY SIGN, DECIMAL-POINT IS COMMA et
les alphabets non natifs restent refusés. ACCEPT reproduit `cob_accept`.

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
exception levée). Les mots réservés de cobc sont refusés comme noms.

## Fichiers, RENAMES, exponentiation

Les clauses SELECT s'écrivent dans n'importe quel ordre ; PADDING CHARACTER
(obsolète) et RECORD DELIMITER STANDARD-1 sont ignorés comme par cobc, VALUE OF
du FD aussi. `SAME RECORD AREA` partage la zone d'enregistrement du premier FD
du groupe (`finalize_file`). Le niveau 66 `RENAMES … [THRU …]` est un alias de
la zone (alphanumérique pour une plage ou un groupe), un REDEFINES de niveau 01
plus grand agrandit la zone (octets supplémentaires nuls). `**` suit
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
identifiants qualifiés ou indicés, littéraux. LEADING/TRAILING, COPY OF/IN et
REPLACING d'un copybook qui contient lui-même un COPY restent refusés.
`--debugging-lines` reproduit `cobc -fdebugging-line`.
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

Sans ces clauses, pour les destinations numériques non éditées, une division par zéro, une valeur hors de la PICTURE, un signe négatif dans un
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
maximale. La longueur active des groupes et les bornes de sous-script suivent
le compteur. Celui-ci doit être un entier scalaire non ambigu, déclaré hors du
groupe variable. La table doit terminer tous ses groupes parents, sans OCCURS
englobant, REDEFINES ni enregistrement FD variable. Ses éléments peuvent être
des groupes avec tableaux fixes imbriqués. Un compteur hors bornes provoque
un arrêt explicite.

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
REDEFINES nommée directement peut être initialisée.

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
python -m cobol2rust verify examples/invoice.cob -o build/controle-facture.json
```

`verify` compile et **exécute** le source donné avec GnuCOBOL et Rust. Il compare
stdout et les fichiers finaux octet pour octet et exige deux codes de retour nuls. Fournir des sources
de confiance ; `--stdin-file entrees.txt` permet de donner les mêmes entrées aux
deux programmes. Le rapport décrit uniquement les entrées testées.

`tools/verify.py` et le sous-ordre `verify` compilent désormais le **source
original** côté GnuCOBOL. Cela vérifie indépendamment les formats et les COPY,
en plus de la traduction Rust. Voir [tools/README.md](tools/README.md).

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
Le vérificateur accepte seulement les chemins ASSIGN relatifs sans `..` ; la
conversion seule peut conserver un chemin absolu. L'exécution n'est pas un bac
à sable pour des sources non fiables.

Périmètre précis du runtime de fichiers :

- `ORGANIZATION LINE SEQUENTIAL` explicite ; `ASSIGN TO` avec chemin littéral.
- Un enregistrement `01` par `FD`, sans `VALUE` : PIC X élémentaire ou groupe
  contenant des colonnes texte et numériques DISPLAY, avec FILLER et niveaux 88.
  Les champs COMP/COMP-3 dans LINE SEQUENTIAL sont refusés.
- Texte ASCII imprimable, fins de ligne LF ou CRLF ; les lignes courtes sont
  complétées par des espaces. Les espaces finaux sont retirés à l'écriture, sauf
  avec `COB_LS_FIXED=1`. Les sauts de ligne écrits suivent la plateforme.
- Statuts couverts : `00`, `04`, `05`, `10`, `30`, `35`, `37`, `41`, `42`, `46`,
  `47`, `48`. `FILE STATUS` doit être un champ `PIC XX` ou `PIC 99 DISPLAY`.
  Sans `FILE STATUS`, un échec non traité provoque un arrêt explicite. `AT END`
  traite la première fin de fichier ; la lecture suivante donne `46`.
- `COB_LS_SPLIT` suit la valeur par défaut GnuCOBOL 3.2 (`true`). Le découpage des
  lignes dépassant la taille du FD n'est pas implémenté et provoque un arrêt
  nommé. Pour les tronquer avec le statut `04`, définir `COB_LS_SPLIT=0` pour
  **les deux programmes**, comme dans l'exemple ci-dessous. Avec le découpage
  actif, une dernière ligne exactement aussi longue que le FD sans délimiteur
  est également refusée : le comportement du runtime GnuCOBOL doit être modélisé
  séparément pour ce cas.
- Limite de 1 Mio par ligne physique ; caractères de contrôle, données non ASCII,
  `I-O`, `REWRITE`, verrouillage, redirections de noms par environnement, profils
  de configuration externes et chemins SELECT identiques non pris en charge.
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

Plusieurs descriptions `01` d'un même FD sont acceptées si leurs tailles
physiques sont égales. Elles partagent la même mémoire et `WRITE` utilise la
description nommée. Des tailles différentes sélectionneraient un format variable
à en-têtes, qui reste refusé.

Une lecture finale partielle conserve la queue précédente du buffer FD et
retourne `00` dans le profil GnuCOBOL vérifié, puis `10` et `46` aux lectures
suivantes. `READ INTO` copie uniquement les octets effectivement lus, puis
complète sa destination, au lieu de recopier cette queue ancienne.

`WRITE ... BEFORE/AFTER ADVANCING` est pris en charge pour ces fichiers avec
PAGE ou un entier littéral de 0 à 65535 lignes. Les contrôles sont les octets
LF (lignes), CR (zéro ligne) et FF (PAGE). AFTER écrit le contrôle avant le
record ; BEFORE l'écrit après. Les espaces des records sont conservés. Un LF
final restant après AFTER est écrit à CLOSE ou à la fermeture implicite de
STOP RUN. OPEN réinitialise cet état.

Les clauses FD `LABEL RECORDS OMITTED/STANDARD`, `BLOCK CONTAINS` (en records
ou caractères, éventuellement sous forme de plage) et `RECORDING MODE F` sont
acceptées dans le profil disque GnuCOBOL vérifié. LABEL/BLOCK sont conservées
dans les métadonnées sans ajouter de labels ni de blocage physique. Une clause
`RECORD CONTAINS n CHARACTERS` exige que n égale la taille physique de chaque
description FD ; sinon le compilateur natif pourrait sélectionner un format
variable et la conversion est refusée. `DATA RECORD(S) [IS|ARE] nom...` est
conservée comme métadonnée : GnuCOBOL n'en résout pas les noms et ne lui donne
aucun effet ; la clause en double ou sans nom reste refusée.

Les compteurs ADVANCING variables, LINAGE, les autres clauses FD,
les formats variables, I-O/REWRITE et les fichiers relatifs/indexés restent
refusés. Le vérificateur refuse les réglages de concaténation de fichiers non
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
