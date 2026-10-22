# Outils de validation

## Mesure d'un corpus externe

`coverage.py` mesure séparément le prétraitement, l'analyse et l'émission Rust.
Il ne compile ni n'exécute les programmes audités. Un rapport conserve les
empreintes des sources, les copybooks connus, le format et les premiers
diagnostics. Les erreurs internes restent distinctes des formes non prises en
charge. Voir [COVERAGE.md](../COVERAGE.md) pour l'objectif et les limites de ces
mesures.

Pour préparer le corpus NIST CCVS85 (GnuCOBOL et Perl requis) :

```bash
python tools/prepare_nist.py --output .tools/nist-ccvs85
python tools/coverage.py .tools/nist-ccvs85/extracted --format fixed \
  --include-subprograms \
  -I .tools/nist-ccvs85/extracted/copy \
  -I .tools/nist-ccvs85/extracted/copyalt \
  --corpus-id NIST-CCVS85-e4513f26 \
  --corpus-source https://gnucobol.sourceforge.io/files/newcob.val.tar.gz \
  --report build/coverage-nist.json
```

La préparation télécharge des artefacts épinglés et vérifie leurs SHA256. Elle
compile et lance seulement l'extracteur officiel EXEC85, puis prépare les
sources avec les adaptations GnuCOBOL enregistrées dans son manifeste. Aucun
cas de conformité NIST n'est exécuté. Le corpus et les outils amont restent dans
le dossier local ignoré, avec leurs notices d'origine.

Les dossiers de préparation et rapports doivent être inexistants ; choisir un
nouveau nom pour une autre exécution. Le code de sortie de `coverage.py` vaut
0 si toutes les sources sélectionnées passent l'émission, 1 si des sources sont
bloquées, 2 si le corpus est vide/inaccessible, la découverte est incomplète,
une erreur interne survient ou le rapport ne peut pas être enregistré. Un code
0 ne prouve pas l'équivalence d'exécution. L'option `--include-subprograms`
ajoute les `.SUB` aux `.cob`/`.cbl` ; les exclusions et le dénominateur sont
enregistrés dans le rapport. Les listes COPY restent inconnues sur échec du
prétraitement.

## Consommateurs NIST avec données de tri officielles

ST107A et ST126A attendent des fichiers produits respectivement par ST106A et
ST125A. Ces producteurs peuvent être exécutés avec GnuCOBOL pour fournir les
mêmes entrées au COBOL original et au Rust des consommateurs. Leurs opérations
SORT et leurs propres PASS ne sont pas attribués au convertisseur.

Exemple Bash depuis la racine, avec GnuCOBOL et Cargo disponibles dans
l'environnement, et un nouveau dossier de travail :

```bash
set -e
mkdir -p build
mkdir build/nist-st125-data
cobc -fixed -x .tools/nist-ccvs85/extracted/ST/ST125A.CBL \
  -I .tools/nist-ccvs85/extracted/copy \
  -I .tools/nist-ccvs85/extracted/copyalt \
  -o build/nist-st125-data/generator
(cd build/nist-st125-data && ./generator)
mkdir build/nist-st125-data/seed
cp build/nist-st125-data/XXXXX001 build/nist-st125-data/XXXXX002 \
  build/nist-st125-data/XXXXX003 build/nist-st125-data/seed/
python -m cobol2rust verify .tools/nist-ccvs85/extracted/ST/ST126A.SUB \
  --format fixed -I .tools/nist-ccvs85/extracted/copy \
  -I .tools/nist-ccvs85/extracted/copyalt \
  --data-dir build/nist-st125-data/seed -o build/nist-st126a.json
```

Pour ST107A, utiliser ST106A comme producteur et ne copier que XXXXX001 dans
le jeu d'entrée. Dans le profil mesuré, chaque fichier fait 243 octets, neuf
records SEQUENTIAL de 27 octets, SHA256
`50fbb785d0857f495d756ba1632e236ec9115aac8ab413570871c8db2fe05cf7`.
Les comparaisons ont donné NC132A 25/25, ST107A 6/6 et ST126A 18/18 PASS dans
leurs bilans CCVS, fichiers identiques au Rust. Cette vérification ciblée ne
remplace pas le runner NIST complet ; voir [VALIDATION.md](../VALIDATION.md).

## Programmes NIST autonomes NC246A et SQ202A

Ces deux sources n'attendent aucune donnée d'entrée ni programme externe.
Elles peuvent être comparées directement, avec des noms de rapports nouveaux :

```bash
python -m cobol2rust verify .tools/nist-ccvs85/extracted/NC/NC246A.CBL \
  --format fixed -I .tools/nist-ccvs85/extracted/copy \
  -I .tools/nist-ccvs85/extracted/copyalt -o build/nist-nc246a.json
python -m cobol2rust verify .tools/nist-ccvs85/extracted/SQ/SQ202A.CBL \
  --format fixed -I .tools/nist-ccvs85/extracted/copy \
  -I .tools/nist-ccvs85/extracted/copyalt -o build/nist-sq202a.json
```

Les exécutions comparées ont donné **49 PASS** pour NC246A et **1 PASS** pour
SQ202A, sans FAIL/DELETED/INSPECT, avec mêmes fichiers que les références
natives indépendantes. SQ202A produit et relit XXXXX001 : 750 records de
120 octets, SHA256
`c3a5a8f0b77c2ddb7ee6f59ae960fb0beb2b39e82f99ab1b101fa94c49e9c415`.
Le rapport de développement regroupé est
`build/nist-separators-documentary-verification.json`. Les bilans proviennent
des REPORT natifs comparés octet pour octet ; cela ne remplace pas le runner
complet des assertions NIST. Le nombre d'occurrences textuelles de PASS seul
ne suffit pas, car les en-têtes de page peuvent répéter ce mot.

## Comparaison des programmes livrés

Depuis la racine du projet :

```powershell
python -m unittest discover -v
python tools/verify.py
```

Le second outil compile chaque exemple et chaque fixture dans `tests/fixtures`
avec **deux compilateurs indépendants** : GnuCOBOL 3.2 et rustc. Il exécute les
deux programmes dans des dossiers distincts avec les mêmes entrées, compare les
octets de stdout et de tous les fichiers finaux et exige deux codes de retour
nuls. Une erreur, une différence ou un délai dépassé fait
échouer la commande. Il ne faut donc l'utiliser qu'avec des sources de confiance.
Les dossiers et les exécutables temporaires sont supprimés à la fin de chaque cas.
GnuCOBOL compile le source original, avec son format et ses copybooks ; il ne
reçoit pas le source normalisé par notre frontend.

Les dossiers portant le suffixe `.data` à côté d'une fixture sont copiés comme
entrées. Son éventuel fichier `.json` peut définir `runtime_env` pour les
paramètres pris en charge (`COB_LS_FIXED`, `COB_LS_SPLIT`). Les rapports conservent
ces paramètres, les empreintes d'entrée et les différences de fichiers.

Le rapport est écrit dans `build/verification.json`. Les fins de ligne sont
comparées sans normalisation. Les espaces de remplissage et les signes sont
également conservés. Cette preuve porte sur les entrées testées, pas sur tous
les chemins possibles du programme ni sur tous les dialectes COBOL.

`python -m cobol2rust doctor` montre les compilateurs trouvés. Sous Windows,
`~/.cargo/bin` est aussi consulté. Le GnuCOBOL portable local est reconnu à
`.tools/gc32/bin/cobc.exe`. Aucun changement du PATH système n'est nécessaire.

L'environnement local préparé pendant le développement contient le binaire
GnuCOBOL 3.2 de son mainteneur Windows, avec son GCC et ses licences d'origine :
<https://www.arnoldtrembley.com/GnuCOBOL.htm>. Ces outils restent exclus des
sources du projet par `.gitignore`.
