# Architecture 0.4

La chaîne source comprend cinq étapes distinctes : normalisation/COPY, analyse
syntaxique, calcul de la disposition mémoire, émission Rust et vérification
différentielle contre le source original compilé par GnuCOBOL.

## Frontend et données

`frontend.py` contient le lexer, les expressions, les références et les
instructions. `data_parser.py` construit les groupes, champs et conditions 88.
Les clés internes des champs incluent leur groupe ; les références OF/IN sont
résolues sans renommer arbitrairement un champ ambigu.

`layout.py` calcule la taille physique, les offsets et les dimensions OCCURS.
Les vues REDEFINES réutilisent l'offset de leur zone d'origine. Les tailles
supérieures à la zone et les dispositions indirectes sont refusées. Les ODO
terminaux conservent une allocation maximale et des offsets fixes. L'émetteur
calcule la longueur active des groupes et les bornes actives de la dimension
variable à chaque référence. Les contrôleurs externes scalaires évitent les
cycles d'adressage ; les tables à stride variable et le glissement sont refusés.
Un tableau conserve son stride par dimension ; un sous-script
ne modifie pas le descripteur partagé.

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

`runtime.rs` conserve le moteur décimal avec `num-bigint`. `storage_runtime.rs`
encode/décode DISPLAY, COMP-3 et COMP/BINARY selon le profil déclaré. Les groupes
contenant du binaire peuvent être affichés en octets bruts. `file_runtime.rs`
utilise les mêmes vues pour les enregistrements structurés LINE SEQUENTIAL,
avec une restriction aux colonnes DISPLAY et aux octets ASCII imprimables.

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
INITIALIZE de groupe ODO composé est refusé ; l'initialisation d'une occurrence
résolue et le cas uniforme texte vérifié restent disponibles.

## Preuves et limites

`verification.py` compile le source original et le Rust dans deux parcours
distincts, copie les mêmes jeux d'entrée, puis compare stdout et les fichiers
finaux octet pour octet. Les rapports comprennent les empreintes des sources,
copybooks, entrées, fichiers produits et le profil de stockage. Les cas réussis
sont une preuve pour les entrées testées, pas pour l'ensemble du langage.

`audit.py` ne lance aucun programme : il inventorie seulement les sources
acceptées par le frontend et leurs blocages. `binary.py` inspecte PE/ELF ; il
n'existe pas encore de parcours binaire vers ce modèle de données ou vers Rust.
