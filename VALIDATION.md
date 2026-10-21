# Validation — 21 octobre 2026

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
