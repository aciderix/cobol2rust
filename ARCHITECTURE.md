# Architecture 0.4

La chaîne source comprend cinq étapes distinctes : normalisation/COPY, analyse
syntaxique, calcul de la disposition mémoire, émission Rust et vérification
différentielle contre le source original compilé par GnuCOBOL.

Le normaliseur fixe développe les tabulations (taquets de huit colonnes),
limite le texte aux colonnes 8..72 et joint les continuations explicites.
Il préserve les espaces des littéraux ouverts, le traitement des délimiteurs
en colonne 72 et la distinction entre littéraux fermés adjacents. Les lignes
physiques jointes laissent des lignes vides dans `expanded.cob` ; les positions
du parser désignent ce texte normalisé. Les directives de format interrompent
la possibilité de continuer une ligne précédente.

`documentary.py` filtre les entrées AUTHOR, INSTALLATION, DATE-WRITTEN,
DATE-COMPILED, SECURITY et REMARKS de l'IDENTIFICATION DIVISION pendant la
normalisation, avant le traitement des guillemets et l'expansion COPY. Leur
prose peut donc contenir des littéraux ouverts ou le mot COPY sans devenir du
code. L'en-tête doit commencer la zone source d'une ligne physique ; les
occurrences dans les littéraux, les autres divisions et les paragraphes
sémantiques ne sont pas éliminées. Un littéral de code déjà ouvert conserve
ses contrôles de continuation.

En format fixe, l'entrée documentaire comprend son en-tête puis les lignes
de zone B jusqu'à la prochaine ligne normale de zone A, qui est réanalysée.
Les lignes vides et les lignes de commentaire fixes ne terminent pas l'entrée.
En format libre, seule la ligne physique portant l'en-tête est éliminée.
Les directives de format autonomes sont traitées avant ce filtre : FREE
termine une entrée fixe active, FIXED conserve sa règle de zone B. Une
directive incluse dans la prose n'a aucun effet. Les continuations fixes
documentaires avec indicateur `-` sont explicitement refusées.

Le parser accepte les sections ENVIRONMENT/CONFIGURATION vides et les
paragraphes SOURCE-COMPUTER/OBJECT-COMPUTER à nom machine seul. Il refuse les
options de configuration non modélisées, sans ignorer leur sémantique.

## Frontend et données

`frontend.py` contient le lexer, les expressions, les références et les
instructions. `data_parser.py` construit les groupes, champs et conditions 88.
Les clés internes des champs incluent leur groupe ; les références OF/IN sont
résolues sans renommer arbitrairement un champ ambigu.

Après PIC/PICTURE et l'éventuel IS, le lexer conserve l'image comme un mot
ASCII contigu, avec ses virgules d'édition et ses points décimaux internes.
Un seul point ou une seule virgule terminale est rendu au scanner ordinaire ;
un point-virgule ou un commentaire `*>` termine le mot. Les espaces internes ne sont pas supprimés
pour reconstruire une image. Hors des images et des littéraux, les virgules
et points-virgules séparent les tokens sans terminer une phrase. Dans les
parenthèses, ils restent des délimiteurs : `table-a(1,+2)` conserve deux
sous-scripts. Une répétition contiguë du même séparateur forme un délimiteur
unique ; les séparateurs distincts ou séparés par des espaces restent distincts.

COPY conserve une validation propre, plus restrictive que ces séparateurs
ordinaires : la directive doit occuper une ligne entière, sans virgule ni
point-virgule supplémentaire autour de ses tokens. La ponctuation du nom de
fichier entre guillemets et du commentaire final reste permise. Les offsets
des tokens désignent leurs bornes dans le texte normalisé et permettent ce
contrôle de la ligne source, y compris les séparateurs ignorés par le lexer.

`layout.py` calcule la taille physique, les offsets et les dimensions OCCURS.
Les images éditées ont une catégorie `edited`, leur image développée et une
taille physique distincte de leur capacité numérique. Les clauses FD du profil
disque sont analysées dans `file_parser.py`,
conservées dans FileSpec et validées contre les tailles après layout.
Les vues REDEFINES réutilisent l'offset de leur zone d'origine. Les tailles
supérieures à la zone et les dispositions indirectes sont refusées. Les ODO
terminaux conservent une allocation maximale et des offsets fixes. L'émetteur
calcule la longueur active des groupes et les bornes actives de la dimension
variable à chaque référence. Les contrôleurs externes scalaires évitent les
cycles d'adressage ; les tables à stride variable et le glissement sont refusés.
Un tableau conserve son stride par dimension ; un sous-script
ne modifie pas le descripteur partagé.

## Sections et contrôle de procédure

`Program.blocks` conserve l'ordre physique : entrée anonyme, préambule de
chaque section (même vide), puis paragraphes. `Program.sections` décrit des
intervalles de blocs semi-ouverts ; les listes historiques `entry` et
`paragraphs` partagent les corps correspondants. Une cible de PERFORM se résout
vers un paragraphe seul ou toute sa section ; THRU prend le début de la
première cible et la fin de la dernière, y compris pour des cibles mixtes.

`control.py` abaisse les instructions en graphe avec continuations explicites :
actions, tests, appels, sauts et points de retour. `emitter.py` produit une
boucle Rust sur le compteur de position `pc` et une pile de cadres
`PerformFrame { through, return_pc }`. GO TO modifie seulement `pc` : un cadre
PERFORM peut rester en attente hors de sa plage, puis retourner lorsque sa fin
est atteinte plus tard. Chaque point de retour compare uniquement le sommet
de la pile et dépile exactement un cadre si sa borne correspond.

Les fins de paragraphe et de section sont distinctes, dans cet ordre, même
pour le dernier paragraphe d'une section. EXIT PARAGRAPH vise la première ;
EXIT SECTION vise directement la seconde, ce qui peut contourner le retour
d'un PERFORM de paragraphe. EXIT nu est sans effet et STOP RUN/GOBACK terminent
la boucle. IF/EVALUATE, READ et SIZE ERROR choisissent leurs continuations
avant d'exécuter leurs corps. Un saut quitte aussi les boucles inline.

Chaque site TIMES possède un compteur unique, partagé lors d'une réentrée
récursive au même site, conformément au C de GnuCOBOL. Les sites distincts ont
des compteurs distincts. TEST AFTER VARYING vérifie la condition avant
l'incrément final. Le rapport JSON expose sections, blocs et modèle de contrôle.

GO TO DEPENDING accepte une donnée entière de neuf chiffres au plus, y compris
table subscriptée et index implicite. Les valeurs hors de 1..N poursuivent
l'exécution sans saut. Les décimaux et grandes largeurs restent refusés : les
conversions GnuCOBOL dépendent du stockage et peuvent réduire à 32 bits.
EXIT SECTION hors section explicite, EXIT PERFORM, ALTER, noms de procédure
qualifiés ou homonymes et segments numérotés ne sont pas encore modélisés.

## Unité d'exécution et CALL

`cli.run_unit` analyse le programme principal puis, transitivement, chaque cible
CALL littérale trouvée dans `--call-path` (tous les programmes du chemin en cas
de CALL dynamique). `emitter.generate_unit` écrit une structure Rust par
programme (`Program`, `Program1`…) et un `RunUnit` qui garde une instance par
appelé (`Option<Box<…>>` et un indicateur actif). `run` rend
`runtime::Outcome::{Return, Stop}` ; un appelé lie ses articles LINKAGE aux
arguments par `storage_runtime::rebind` dans sa méthode `call`.

## Runtime Rust

Chaque programme possède un espace mémoire `Rc<RefCell<Vec<u8>>>` partagé par
ses vues `Value::View`. La vue désigne une zone, une catégorie de donnée, une
PICTURE et des dimensions. Les groupes et les champs texte exposent les octets ;
les champs numériques sont décodés seulement lorsqu'une valeur est demandée.
Cela permet de tester IS NUMERIC avant de rejeter une donnée invalide.

Les valeurs temporaires d'expression sont des snapshots. Le MOVE d'une variable
conserve toutefois une vue source dont l'adresse est résolue avant les écritures :
chaque destination relit cette vue. Les essais d'alias et de sous-scripts
protègent cette différence contre une simplification incorrecte.

Le frontend distingue `Stmt("move")` des affectations arithmétiques et garde
`Expr.figurative_zero`, sans changer sa valeur numérique. Seul le chemin MOVE
autorise nombre vers texte. Pour un champ entier vers PIC X ou refmod,
`numeric_move_text(false)` enlève le signe et conserve la largeur PICTURE ;
COMP/COMP-3/index passent par magnitude modulo capacité, puis zéros initiaux.
DISPLAY non signé copie ses octets sans les interpréter ; DISPLAY signé valide
retire l'overpunch dans la copie. Les signes invalides sont un arrêt explicite.

Pour un groupe destinataire, `numeric_move_text(true)` copie directement le
stockage, même pour un champ avec V, sans décodage ni correction du signe.
Le cas index vers groupe reste refusé, car son stockage natif diffère de la
représentation interne. Les littéraux vers texte gardent leurs chiffres
lexicaux sans signe ni point. ZERO/ZEROS/ZEROES remplissent la taille active
de chaque récepteur de zéros ; le littéral 0 reste un seul chiffre. Les helpers
ne modifient pas `Value.bytes()` ni `View.assign()` : les calculs, VALUE et
les autres conversions conservent leurs règles.

`Emitter.comparison_order` garde le contexte de la comparaison. Il appelle
`comparison_text` directement sur les vues numériques pour préserver les octets
DISPLAY non signés invalides et la largeur PICTURE. Avec V, la magnitude
conserve tous les chiffres, sans point. Les littéraux numériques non signés
conservent leur graphie et `compare_zero` remplit la largeur de l'autre texte.
Le littéral texte vide est traité comme un espace dans ce contexte, comme par
GnuCOBOL. `Value.compare` général n'acquiert aucune conversion implicite.

Les comparaisons directes contre des littéraux texte sont limitées aux entiers
et chiffres de même largeur : une régression native montre qu'un champ avec V
peut être comparé différemment à un littéral ou à un champ PIC X contenant les
mêmes octets. Index, expressions numériques, signes explicites et catégories
mixtes EVALUATE/88 restent refusés. Les refus des comparaisons éditées restent
distincts de ce nouveau chemin.

`assign_text_move` est réservé au MOVE. Une source groupe copie ses octets et
ses espaces de remplissage directement dans le stockage numérique ou édité.
Une source PIC X/refmod passe par un buffer de chiffres : capacité/échelle du
receveur DISPLAY, ou 76 positions/38 décimales pour les autres usages et edited.
L'excès entier est sauté avant validation ; la lecture s'arrête au remplissage
du buffer. Un caractère invalide rencontré remet les chiffres à zéro. Le signe
initial reste stocké pour DISPLAY ; le chemin indirect l'efface si invalide.
Les négatifs zéro conservent l'overpunch DISPLAY et le nibble D de COMP-3.

Les littéraux texte n'utilisent ce chemin que vers edited : leur transfert vers
un numérique ordinaire peut utiliser des optimisations natives distinctes.
`Expr.figurative_space` préserve aussi la différence entre SPACE et le littéral
" ", le premier étant refusé vers edited par le profil natif. La déédition,
`num()`, `assign()` et les règles VALUE restent strictes.

`runtime.rs` conserve le moteur décimal avec `num-bigint`. `storage_runtime.rs`
encode/décode DISPLAY, COMP-3 et COMP/BINARY selon le profil déclaré. Les groupes
contenant du binaire peuvent être affichés en octets bruts. `file_runtime.rs`
utilise les mêmes vues pour les enregistrements structurés LINE SEQUENTIAL,
avec une restriction aux colonnes DISPLAY et aux octets ASCII imprimables.

`CobolFile` distingue cette organisation du SEQUENTIAL fixe, explicite ou
implicite. Ce dernier lit et écrit les octets bruts sans délimiteur. Les
descriptions 01 FD alternatives deviennent des vues de même taille sur la
zone du premier record ; les tailles différentes sont refusées pour éviter
de produire un format fixe à la place du format variable natif.

Le runtime conserve le nombre d'octets réellement lus : une lecture partielle
préserve la queue du record, tandis que READ INTO ne copie que le préfixe lu.
Les contrôles ADVANCING sont des octets LF/CR/FF ; AFTER arme un LF final,
BEFORE le désarme et WRITE sans contrôle conserve cet état. CLOSE et Drop
finalisent ce LF, pour couvrir aussi STOP RUN sans fermeture explicite.

INITIALIZE parcourt les descriptions des feuilles, en ignorant les FILLER et
REDEFINES subordonnés selon les règles prises en charge. Les clauses VALUE
initialisent les feuilles de WORKING-STORAGE, sur toutes leurs occurrences.
Les buffers FD commencent à zéro binaire ; une lecture remplit leur zone brute.

Les index implicites sont des champs ordinaux distincts du stockage de leur
table, initialisés à 1. Leur affichage suit le format signé de 9 chiffres testé.
SET UP/DOWN évalue son opérande pour chaque destination, afin qu'une modification
du premier index soit visible si celui-ci sert d'opérande au second.

Les instructions avec SIZE ERROR utilisent un chemin `Result<Value, SizeError>`
pour les divisions et une affectation numérique contrôlée. Le contrôle de
PICTURE intervient avant l'écriture et après l'arrondi. Seuls le dépassement
de destination et la division par zéro sont récupérables. Les erreurs de données
restent des diagnostics nommés, sans interception de panique ou d'arrêt processus.
Un MOVE numérique vers numérique utilise `View.move_number` : décimales
tronquées, magnitude modulo 10^chiffres, signe perdu vers un non signé et zéro
négatif conservé en DISPLAY/COMP-3. Il ne lève jamais SIZE ERROR, contrairement
aux calculs sans gestionnaire, qui gardent l'arrêt conservateur. Vers COMP-3,
cobc emploie `cob_set_packed_int` pour les sources binaires et petits littéraux
entiers ; ce chemin remplit le quartet de tête d'une PICTURE paire. Ce cas est
refusé à l'émission (littéral) ou arrêté à l'exécution (`move_binary_to_packed`).
INITIALIZE de groupe ODO composé est refusé ; l'initialisation d'une occurrence
résolue et le cas uniforme texte vérifié restent disponibles.

## Preuves et limites

`Kind::Edited` conserve les octets formatés et leur image dans les vues de
stockage. Une affectation numérique ajuste l'échelle et l'arrondi, calcule le
signe puis tronque à la capacité et applique l'édition. VALUE texte reste une
déclaration brute ; INITIALIZE formate zéro. L'émetteur garde cette catégorie
distincte pour refuser la déédition et les opérandes numériques non modélisés,
tout en autorisant les copies vers du texte et les sous-chaînes alphanumériques.
Les comparaisons directes de champs édités restent refusées : le repli de
constantes GnuCOBOL utilise parfois leur PICTURE, y compris lorsque REDEFINES
en a modifié les octets. Un test natif préserve ce contre-exemple. IS NUMERIC
reste un examen des octets, conformément aux probes du profil de référence.

`verification.py` compile le source original et le Rust dans deux parcours
distincts, copie les mêmes jeux d'entrée, puis compare stdout et les fichiers
finaux octet pour octet. Les rapports comprennent les empreintes des sources,
copybooks, entrées, fichiers produits et le profil de stockage. Les cas réussis
sont une preuve pour les entrées testées, pas pour l'ensemble du langage.

`audit.py` ne lance aucun programme : il inventorie seulement les sources
acceptées par le frontend et leurs blocages. `binary.py` inspecte PE/ELF ; il
n'existe pas encore de parcours binaire vers ce modèle de données ou vers Rust.
