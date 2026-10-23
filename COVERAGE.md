# Objectif : couverture universelle du COBOL vers Rust

L'objectif demandé est une **garantie universelle de conversion COBOL vers
Rust**, couvrant tout le COBOL existant, au-delà du sous-ensemble de la version
0.4.0. Cet objectif guide le développement ; il ne
constitue pas une garantie déjà acquise. La couverture sera étendue sans traduire
silencieusement une construction dont le comportement n'est pas reproduit.

## Ce qui doit être couvert

Un profil de compatibilité doit préciser le compilateur source et sa version,
le dialecte, les options de compilation, le format, les copybooks, l'encodage,
la représentation des données et les dépendances d'exécution. Un même texte
COBOL peut avoir des effets différents selon ces paramètres.

| Domaine | Travail nécessaire |
| --- | --- |
| Langage | Standards successifs, prétraitement, extensions de compilateurs, programmes liés |
| Données | PICTURE, mémoire partagée, décimaux, arrondis, encodages et profils binaires |
| Exécution | Appels externes, erreurs, fichiers séquentiels et indexés, entrées/sorties |
| Plateformes | Adaptateurs pour SQL/DB2, CICS, IMS, VSAM et autres services effectivement utilisés |
| Validation | Corpus de conformité, programmes réels, données et compilateurs de référence par profil |

L'inspection d'un exécutable reste distincte de la conversion de ses sources.
Le parcours binaire sans sources vers Rust n'est pas implémenté.

## Niveaux de preuve

1. **Source inventoriée** : identité du corpus et empreintes des fichiers.
2. **Émission acceptée** : prétraitement, parsing, disposition et émission Rust.
   Cela ne démontre ni la compilation ni le comportement.
3. **Compilation réussie** : construction effective du projet Rust généré.
4. **Comparaison exécutée** : comparaison avec le compilateur source du profil,
   sur des entrées identifiées, y compris erreurs et effets externes pertinents.
5. **Conformité du corpus** : assertions et rapports propres à la suite de tests
   contrôlés ; deux sorties identiques ne suffisent pas si les deux programmes
   signalent le même échec de test.

Une preuve formelle éventuelle porte sur un modèle et des hypothèses définis.
Un corpus, même intégralement réussi, ne prouve pas l'équivalence de tous les
programmes possibles. Aucun pourcentage de ce document ne désigne « le COBOL
mondial » : son dénominateur doit toujours être explicite.

## Première référence externe : NIST CCVS85

Le corpus COBOL85 est préparé avec l'extracteur EXEC85 et les fichiers
d'adaptation du projet GnuCOBOL. L'archive originale reste inchangée. Les
substitutions de plateforme et corrections de tests appliquées par EXEC85 sont
enregistrées avec la provenance ; les fichiers ne sont pas simplifiés pour les
faire accepter par notre convertisseur.

- Archive : <https://gnucobol.sourceforge.io/files/newcob.val.tar.gz>
- SHA256 : `e4513f26a9b38911f7bf882fe3d3339a80b45cabc2caf85eb3055b0f5ce87ee0`.
- Préparation GnuCOBOL épinglée au commit
  `59b1b239c2de293be116aa75ed5376d9b311d45d` du
  [dépôt GnuCOBOL](https://github.com/OCamlPro/gnucobol/tree/59b1b239c2de293be116aa75ed5376d9b311d45d/tests/cobol85).
- Modules : NC, SM, IC, SQ, RL, IX, ST, SG, OB, IF, RW, DB et CM.
  DBNOIX est une configuration alternative, exclue de ce dénominateur.
- 390 sources principales, 24 sources de bibliothèque `.CBL`, 44 sous-programmes
  `.SUB`, 51 copybooks et deux fichiers de données.

L'extracteur est le seul programme COBOL compilé et exécuté pendant cette
préparation. Cela ne lance aucun cas NIST ni aucune assertion de conformité.
Les outils amont et le corpus restent hors du dépôt, avec leurs notices
d'origine ; leur disponibilité ne doit pas être assimilée à une autorisation
de redistribution sous la licence de ce projet.

La mesure reproductible avec `tools/coverage.py --include-subprograms`, sous
Linux le 21 octobre 2026, porte sur les **458 sources `.CBL` et `.SUB`** :
**0 émission acceptée**, 398 blocages au prétraitement et 60 à l'analyse,
sans erreur interne. Aucun programme n'a été compilé, exécuté ou comparé par
cet outil. Rapport local : `build/coverage-nist.json` ; provenance et inventaire
des 511 fichiers du corpus : `.tools/nist-ccvs85/manifest.json`.

Les commandes de préparation et de mesure sont documentées dans
[tools/README.md](tools/README.md). Les empreintes des fichiers de l'outil et
du convertisseur sont enregistrées séparément du HEAD Git, pour identifier
aussi une implémentation comportant des changements locaux.

| Premier diagnostic observé | Sources `.CBL` et `.SUB` |
| --- | ---: |
| Indicateur de continuation fixe `-` non pris en charge | 396 |
| Section `CONFIGURATION` non prise en charge | 56 |
| Autres premiers diagnostics | 6 |

Ce regroupement indique seulement le premier obstacle rencontré par fichier.
Le prétraitement parcourt tout le texte avant le parsing : l'ordre de ses
diagnostics n'est pas un classement exhaustif des fonctionnalités manquantes.

## Progression : continuations fixes et configuration

La version de développement accepte désormais les continuations fixes de mots,
nombres, PICTURE et littéraux, avec les espaces, guillemets en colonne 72,
commentaires et tabulations du profil GnuCOBOL. Les noms machine seuls dans
SOURCE-COMPUTER et OBJECT-COMPUTER sont acceptés. Les options sémantiques non
modélisées restent refusées.

| Mesure sur les mêmes 458 sources | Initiale | Après extension |
| --- | ---: | ---: |
| Blocage au prétraitement | 398 | 73 |
| Blocage à l'analyse/disposition | 60 | 384 |
| Émission Rust acceptée | 0 | 1 |
| Erreur interne | 0 | 0 |

Le rapport après extension est `build/coverage-nist-fixed.json`. La progression
vers l'analyse révèle les obstacles suivants ; elle n'est pas une réussite
d'exécution. Les premiers diagnostics concernent maintenant surtout
l'organisation séquentielle implicite (299 sources), les caractères lexicaux
`;` et `$`, les paragraphes documentaires IDENTIFICATION et les autres clauses
de configuration.

Le programme accepté, **SM301M**, développe le copybook KSM31 et affiche un
espace. Il a aussi été compilé et comparé à GnuCOBOL sur son exécution sans
entrée : stdout, codes de retour et fichiers correspondent. Rapport :
`build/nist-sm301m-verification.json`. Ce programme concerne un contrôle de
signalement des standards dans NIST ; notre essai d'exécution ne vérifie pas
les diagnostics attendus par cette suite et ne constitue pas un passage de
ses assertions de conformité.

La suite Python découvre désormais 64 tests : 63 réussissent et un test PE
Windows est ignoré. Le corpus différentiel local comprend 42 programmes,
tous conformes sur leurs entrées testées, dont une nouvelle fixture fixe avec
continuations et CONFIGURATION. Les cas limites du normaliseur ont aussi des
comparaisons natives ciblées.

## Progression : SEQUENTIAL fixe et rapports

Le convertisseur prend maintenant en charge SEQUENTIAL implicite/explicite,
les octets bruts COMP/COMP-3, plusieurs descriptions FD de même taille sur la
même mémoire, les lectures partielles et les contrôles BEFORE/AFTER ADVANCING.
Les preuves ciblées vérifient les octets attendus, les statuts et la fermeture
implicite, en plus de l'égalité avec GnuCOBOL. LINE SEQUENTIAL garde son format
distinct.

Le corpus local comporte **44 programmes, tous conformes** sur les entrées
testées (`build/verification-sequential.json`). La suite découvre **76 tests :
75 réussis, un test PE Windows ignoré**. Les nouvelles fixtures sont
`sequential_records.cob` et `sequential_report.cob`.

La mesure NIST reste à **1/458 émission acceptée**, 73 blocages au prétraitement,
384 à l'analyse et zéro erreur interne (`build/coverage-nist-sequential.json`).
Les blocages de l'organisation séquentielle implicite ont été levés ; les
obstacles suivants apparaissent au premier diagnostic, sans augmentation du
nombre de programmes entièrement acceptés.

| Nouveaux premiers obstacles | Sources |
| --- | ---: |
| PICTURE éditée `-9(9)` | 66 |
| Organisation RELATIVE | 31 |
| Paragraphe documentaire AUTHOR | 26 |
| Organisation INDEXED | 25 |
| VALUE/USAGE de groupe | 24 |
| Clause FD LABEL | 22 |
| Clause FD BLOCK | 16 |
| I-O-CONTROL | 13 |

Les formats variables, les autres clauses FD et les compteurs ADVANCING
variables restent explicitement refusés. Aucun résultat de cette étape ne
constitue une réussite des assertions de conformité NIST.

## Progression : PICTURE éditées et clauses FD

La catégorie éditée couvre les signes fixes, chiffres, point explicite et
suppression de Z initiaux suivis de 9 obligatoires. Les images NIST
`-9(9).9(9)` et `-.9(18)` ont une taille physique de 20 octets, distincte de
leurs 18 positions numériques. L'analyse préserve le point interne de l'image.
Les tests vérifient les octets attendus pour signe, échelle, arrondi, overflow,
VALUE texte/numérique, INITIALIZE, alias et copies. Un contre-exemple natif
préserve le refus des comparaisons directes éditées, dont le résultat peut
dépendre du repli de constantes GnuCOBOL. Les copies vers PIC X et sous-chaînes
alphanumériques ont les comparaisons brutes vérifiées.
Les usages numériques et dééditions non modélisés restent refusés.

Les clauses LABEL/BLOCK, RECORD exact et RECORDING F sont acceptées pour les
fichiers disque du profil GnuCOBOL. La longueur RECORD est vérifiée après
layout afin de refuser tout changement non modélisé vers un format variable.
La nouvelle fixture `edited_report.cob` combine ce support avec les rapports.

Résultats : **86 tests réussis, un ignoré** (87 découverts), **45/45 comparaisons
locales conformes** (`build/verification-edited-final.json`). NIST conserve **1/458
émission acceptée**, 73 blocages au prétraitement, 384 à l'analyse et aucune
erreur interne (`build/coverage-nist-edited-final.json`). Les compteurs globaux sont
inchangés ; les premiers obstacles se déplacent vers des étapes ultérieures.

| Premiers obstacles après extension | Sources |
| --- | ---: |
| Section de procédure CCVS1 | 44 |
| Caractère lexical `;` | 32 |
| Organisation RELATIVE | 31 |
| Paragraphe AUTHOR | 26 |
| FILE STATUS hors profil simple | 25 |
| Organisation INDEXED | 25 |
| VALUE/USAGE de groupe | 24 |
| Caractère lexical `$` | 21 |
| Clause FD DATA | 18 |

## Progression : sections de procédure et PERFORM

Les sections ont maintenant des blocs ordonnés pour leur préambule et leurs
paragraphes. PERFORM peut appeler un paragraphe, une section ou une plage
THRU/THROUGH avec bornes mixtes. Les retours imbriqués/récursifs, l'exécution
séquentielle, les sections vides, EXIT PARAGRAPH et EXIT nu sans effet sont
comparés à GnuCOBOL dans huit tests différentiels. Une preuve native justifie
le refus de EXIT SECTION : il peut dépasser le retour d'un PERFORM de
paragraphe, ce qu'un simple retour de fonction Rust ne reproduirait pas.

Les 16 tests ciblés réussissent ; la suite complète compte **102 réussites et
un test PE Windows ignoré** (103 découverts). Les **46/46 comparaisons locales**
sont conformes (`build/verification-sections.json`). La mesure NIST
`build/coverage-nist-sections.json` donne toujours **1/458 émission acceptée**,
73 blocages au prétraitement, 384 à l'analyse et aucune erreur interne. Les
premiers diagnostics changent pour 48 sources, sans augmenter le nombre de
programmes entièrement acceptés. Aucun programme NIST n'est compilé ou exécuté
par cette mesure.

| Premiers obstacles après sections/PERFORM | Sources |
| --- | ---: |
| GO TO | 46 |
| Caractère lexical `;` | 32 |
| Organisation RELATIVE | 31 |
| Paragraphe AUTHOR | 26 |
| FILE STATUS hors profil simple | 25 |
| Organisation INDEXED | 25 |
| VALUE/USAGE de groupe | 24 |
| Caractère lexical `$` | 21 |
| Clause FD DATA | 18 |

Les qualifications/homonymes de procédures, sections segmentées et variantes
EXIT SECTION/PERFORM restent refusées.

## Progression : GO TO et pile PERFORM — 22 octobre 2026

Un graphe de contrôle et une pile explicite remplacent les appels Rust par
bloc. GO TO conserve les retours PERFORM en attente ; seuls les points de
retour correspondant au sommet de pile reprennent leur continuation. Les fins
de paragraphe et de section sont distinctes. EXIT SECTION peut désormais viser
directement la fin d'une section explicite. Les sauts quittent aussi les corps
IF/EVALUATE, handlers READ/SIZE ERROR et boucles inline.

GO DEPENDING accepte un contrôleur entier de neuf chiffres au plus, table
subscriptée et index implicite compris ; hors de 1..N, aucun saut. Les autres
contrôleurs restent refusés : les conversions natives varient avec l'usage et
la largeur. Les compteurs TIMES partagés par site reproduisent l'écrasement
observé lors d'une réentrée récursive. Les 37 tests ciblés passent.
La suite complète découvre **124 tests : 123 réussis, un PE Windows ignoré**.
Les **47/47 comparaisons locales** sont conformes
(`build/verification-goto.json`).

Mesure statique `build/coverage-nist-goto.json` : **2/458 émissions acceptées**,
73 blocages au prétraitement, 375 à l'analyse, 8 à l'émission et zéro erreur
interne. NC110M rejoint SM301M. Les premiers diagnostics/statuts changent pour
47 sources. Les huit blocages d'émission concernent une conversion
numérique/texte des rapports CCVS-E-4 ; les anciens GO TO ne bloquent plus en
premier. Cette mesure ne compile ni n'exécute les programmes.

NC110M a en complément une comparaison native COBOL/Rust réussie
(`build/nist-nc110m-verification.json`), codes nuls et octets identiques. Les
lignes PASS, absence de FAIL et fin de test sont vérifiées pour ses cas GO et
PERFORM. Cela ne remplace pas le runner complet des assertions NIST.

| Premiers obstacles après GO TO | Sources |
| --- | ---: |
| Caractère lexical `;` | 32 |
| Organisation RELATIVE | 31 |
| Paragraphe AUTHOR | 26 |
| FILE STATUS hors profil simple | 25 |
| Organisation INDEXED | 25 |
| VALUE/USAGE de groupe | 24 |
| Caractère lexical `$` | 21 |
| Clause FD DATA | 18 |
| Conversion numérique/texte CCVS-E-4 (émission) | 8 |

ALTER/GO sans cible, EXIT SECTION hors section explicite, EXIT PERFORM,
qualifications/homonymes de procédures et sections segmentées restent refusés.

## Progression : MOVE numérique vers texte — 22 octobre 2026

Le MOVE vers PIC X/refmod rend les chiffres d'un entier sur sa largeur PICTURE,
sans signe. Vers un groupe, il copie le stockage brut, y compris COMP/COMP-3 et
source avec V. Les littéraux gardent leurs chiffres lexicaux sans signe ni point,
tandis que ZERO remplit toute la destination. La distinction MOVE/affectation
arithmétique maintient les refus des calculs vers texte. Les tests protègent
aussi la relecture d'une source partagée pour chaque récepteur et la résolution
unique de son adresse.

Résultats : **140 tests réussis, un ignoré** (141 découverts), **48/48
comparaisons locales conformes** (`build/verification-numeric-move.json`).
La mesure `build/coverage-nist-numeric-move.json` donne **8/458 émissions
acceptées**, 73 blocages au prétraitement, 375 à l'analyse, 2 à l'émission et
zéro erreur interne. Six nouvelles sources sont acceptées : NC127A, NC136A,
NC137A, SM106A, SM107A et ST107A. Les huit premiers diagnostics d'émission
changent ; NC132A et ST126A atteignent respectivement une comparaison mixte et
un transfert texte vers nombre, encore refusés.

Les cinq nouveaux programmes autonomes sont également compilés/exécutés en
COBOL et Rust, avec codes nuls et sorties/fichiers identiques
(`build/nist-numeric-move-verification.json`). Les empreintes des REPORT sont
contrôlées contre des exécutions natives indépendantes. Leurs bilans déclarent
**218 PASS automatiques**, aucun FAIL/DELETED et **une inspection requise**
dans SM106A, conservée comme telle. Ce contrôle ciblé n'est pas le runner NIST
complet. ST107A n'est pas exécuté : il attend `XXXXX001`, fichier de tri de
27 octets par record produit par ST106A, absent des données livrées.

Restent refusés : champ avec V vers PIC X/refmod, index vers groupe, texte vers
nombre et déédition. Le runtime copie DISPLAY non signé invalide en brut mais
arrête explicitement les DISPLAY signés invalides dont les normalisations et
mutations natives ne sont pas modélisées.

## Progression : comparaisons mixtes et MOVE depuis texte — 22 octobre 2026

La comparaison garde les catégories et la graphie des opérandes. Les champs
numériques peuvent être comparés à du texte variable, par magnitude sur la
largeur PICTURE, sans signe ni point. Les littéraux numériques non signés et
ZERO sont distincts. Face à un littéral texte direct, la garde est limitée aux
entiers et chiffres de même largeur : une régression native démontre un
repli de constante incompatible avec une simple comparaison d'octets ailleurs.

MOVE distingue les groupes source (copie brute), les champs PIC X/refmod
(lecture dans un buffer natif) et les littéraux texte (vers edited uniquement).
Les négatifs zéro et les différences de capacité DISPLAY/autres usages sont
préservés. Les chemins génériques de calcul et de comparaison restent stricts.

Résultats : **162 tests réussis, un ignoré** (163 découverts), **49/49
comparaisons locales conformes** (`build/verification-mixed-types.json`).
NIST atteint **10/458 émissions acceptées**, 73 blocages au prétraitement,
375 à l'analyse, aucun blocage d'émission et zéro erreur interne
(`build/coverage-nist-mixed-types-final.json`). NC132A et ST126A sont les deux
nouvelles sources acceptées.

NC132A, ST107A et ST126A ont aussi des comparaisons natives conformes : mêmes
octets stdout/fichiers et codes nuls. Leurs bilans donnent **49 PASS** (25/6/18),
sans FAIL/DELETED/INSPECT (`build/nist-mixed-types-verification.json`). Les
entrées officielles des consommateurs de tri ont été générées en GnuCOBOL par
ST106A/ST125A : neuf records de 27 octets par fichier. Cela lève l'absence de
données signalée aux étapes précédentes, sans attribuer au convertisseur la
prise en charge de SORT ni les deux PASS des producteurs natifs.

Restent refusés : comparaisons mixtes avec index, signes numériques explicites,
calculs, sujets/cas EVALUATE ou valeurs 88 de catégories différentes ;
littéraux texte vers Numeric ordinaire, déédition et calculs sur texte.
Les blocages majoritaires restent désormais au prétraitement et au frontend.

## Progression : séparateurs et entrées documentaires — 22 octobre 2026

Le lexer traite virgules et points-virgules comme séparateurs hors PICTURE,
en conservant les délimiteurs nécessaires aux sous-scripts et aux expressions
parenthésées. Une PICTURE reste un mot contigu ; ses virgules d'édition ne sont
pas effacées et les images non modélisées restent refusées. COPY garde une
validation distincte, conservatrice sur les séparateurs supplémentaires.

Les paragraphes AUTHOR, INSTALLATION, DATE-WRITTEN, DATE-COMPILED, SECURITY et
REMARKS sont filtrés avant les guillemets et COPY. Leur portée respecte les
zones A/B du format fixe et la ligne physique du format libre. Les directives
de format restent actives ; les clauses sémantiques d'Identification et les
autres divisions restent analysées.

| Mesure sur les mêmes 458 sources | Avant | Après |
| --- | ---: | ---: |
| Blocage au prétraitement | 73 | 16 |
| Blocage à l'analyse/disposition | 375 | 430 |
| Blocage à l'émission | 0 | 0 |
| Émission Rust acceptée | 10 | 12 |
| Erreur interne | 0 | 0 |

Rapport : `build/coverage-nist-separators-documentary-reviewed.json`. Les
premiers diagnostics/statuts changent pour **94 sources**, dont **57** passent
du prétraitement à l'analyse et deux deviennent acceptées : NC246A et SQ202A.
La hausse des blocages à l'analyse reflète les obstacles suivants désormais
atteints ; cette mesure ne compile ni n'exécute les programmes.

| Premiers obstacles après extension | Sources |
| --- | ---: |
| Clause FD DATA | 36 |
| Organisation RELATIVE | 32 |
| Organisation INDEXED | 26 |
| FILE STATUS hors profil simple | 25 |
| VALUE/USAGE de groupe | 24 |
| I-O-CONTROL | 15 |

Les **200 tests découverts** donnent 199 réussites et un PE Windows ignoré ;
les **51/51 comparaisons locales** passent
(`build/verification-separators-documentary.json`). NC246A et SQ202A ont aussi
des comparaisons natives conformes, avec fichiers identiques aux références
indépendantes et **50 PASS** (49/1), sans FAIL/DELETED/INSPECT
(`build/nist-separators-documentary-verification.json`). SQ202A vérifie la
création/relecture de 750 records de 120 octets. Ces essais ciblés ne sont pas
le runner NIST complet et ne démontrent pas la garantie universelle recherchée.

## Progression : DATA RECORDS et MOVE numérique tronquant

La clause FD `DATA RECORD(S) [IS|ARE] nom...` est acceptée comme métadonnée.
GnuCOBOL 3.2 l'analyse sans résoudre ses noms et ne lui donne aucun effet ;
ses doublons et sa forme sans nom restent refusés comme en natif.
Un MOVE numérique vers numérique tronque désormais les chiffres de tête sans
SIZE ERROR, comme la norme et GnuCOBOL ; les calculs sans gestionnaire gardent
l'arrêt conservateur. Le seul cas natif non modélisé (chiffre déposé dans le
quartet de tête d'un COMP-3 pair par une source binaire ou un littéral entier)
est refusé ou arrêté avec un diagnostic nommé.

| Mesure sur les mêmes 458 sources | Avant | Après |
| --- | ---: | ---: |
| Blocage au prétraitement | 16 | 16 |
| Blocage à l'analyse/disposition | 430 | 422 |
| Émission Rust acceptée | 12 | 20 |
| Erreur interne | 0 | 0 |

Les 36 sources dont DATA RECORD était le premier diagnostic changent de statut
ou de diagnostic. Les 8 nouvelles sources acceptées SM102A, SM104A, SM204A,
SQ128A, ST103A, ST104A, ST115A et ST121A ont **8/8 comparaisons natives
conformes** ; leur REPORT est identique octet pour octet au journal du runner
NIST officiel exécuté sous GnuCOBOL 3.2 : **44 PASS, 0 FAIL/DELETED/INSPECT**.
Les cinq `.SUB` lisent les fichiers de leurs producteurs officiels (SM101A,
SM103A, SM203A, ST101A/ST102A, ST119A/ST120A) exécutés en GnuCOBOL. ST115A
dépendait du MOVE tronquant. Les 12 sources acceptées auparavant restent
conformes. Premiers diagnostics désormais : RELATIVE (32), INDEXED (26),
FILE STATUS de groupe (25), VALUE/USAGE de groupe (24), OBJECT-COMPUTER (19).
Rapport : `build/coverage-nist-data-records.json`.

## Progression : groupes, configuration et receveurs multiples

| Mesure sur les mêmes 458 sources | Avant | Après |
| --- | ---: | ---: |
| Blocage au prétraitement | 16 | 15 |
| Blocage à l'analyse/disposition | 422 | 413 |
| Émission Rust acceptée | 20 | 30 |
| Erreur interne | 0 | 0 |

FILE STATUS de groupe débloque 7 sources SQ, VALUE/USAGE de groupe NC245A, les
clauses de configuration sans effet OBSQ4A et SQ303M. `tools/nist_verify.py`
compare les **30** sources acceptées avec les entrées du runner officiel :
**30/30 conformes**, REPORT identiques aux journaux natifs, 401 PASS et 1
INSPECT. Cette vérification a révélé une perte silencieuse de receveur dans
`ADD ... TO A, B.`, corrigée avant mesure. Rapports :
`build/coverage-nist-multi.json` et `build/nist-verify-30.json`.

## Progression : DECLARATIVES et instructions de fichier

DECLARATIVES `USE AFTER ERROR`, les mots facultatifs de READ et CLOSE WITH
LOCK portent l'émission acceptée de **30 à 59/458**. Les 29 nouvelles sources
sont conformes avec `tools/nist_verify.py`, REPORT identiques au runner natif,
117 PASS sans FAIL (`build/nist-verify-decl.json`, `build/nist-verify-rc.json`).
Rapport statique : `build/coverage-nist-read-close.json`.

## Progression : OPEN I-O et REWRITE séquentiels

OPEN I-O et REWRITE SEQUENTIAL portent l'émission acceptée à **66/458**. Toutes
les sources acceptées sont reverifiées avec les entrées du runner : **66/66
conformes**, 539 PASS, 1 INSPECT (SM106A), aucun FAIL
(`build/nist-verify-66.json`). Prochains obstacles : RELATIVE (32), INDEXED (26),
fonctions intrinsèques, WITH DEBUGGING MODE et PROGRAM COLLATING SEQUENCE.

## Progression : RELATIVE et clauses SELECT

Les fichiers RELATIVE, au format disque exact de GnuCOBOL, et la grammaire
SELECT complète portent l'émission acceptée à **95/458**. Les 29 nouvelles
sources sont conformes au runner natif (762 PASS, 4 DELETED également natifs ;
`build/nist-verify-rel.json`, `build/nist-verify-rel2.json`). Les `.SUB` lisent
des fichiers RELATIVE écrits par les producteurs GnuCOBOL.

## Progression : enregistrements variables et formes de langage

Enregistrements variables SEQUENTIAL/RELATIVE au format exact de GnuCOBOL,
PERFORM VARYING ... AFTER, mots commençant par un chiffre, littéraux à point
initial, PIC A/V, MOVE ALL et SET depuis un index portent l'émission acceptée à
**115/458**. Toutes les nouvelles sources sont conformes au runner natif
(`build/nist-verify-var.json` : 12/12, 643 PASS).

## Ordre de travail

1. Conserver une mesure reproductible de l'ensemble des sources NIST, en
   distinguant programmes, sous-programmes, copybooks et données.
2. Poursuivre le prétraitement et les divisions et clauses manquantes après
   les continuations fixes, noms machine, SEQUENTIAL fixe et GO TO ajoutés.
   Étudier DATA RECORD, les autres clauses FD, les organisations RELATIVE/INDEXED
   et les dispositions de groupe, en conservant les refus des formats non modélisés.
   Ajouter des régressions isolées et des essais natifs avant chaque nouvelle règle.
3. Lever les obstacles de données et de contrôle, compiler les programmes
   générés et intégrer le runner de conformité NIST avec ses assertions.
4. Étendre les standards et dialectes avec leurs propres profils et oracles.
   GnuCOBOL seul ne certifie pas les comportements IBM ou Micro Focus.
5. Ajouter les adaptateurs de plateforme et les corpus métier réels. Tester les
   transactions et effets externes, au-delà de stdout et des fichiers locaux.

Les refus explicites restent en place jusqu'à validation de leur remplacement.
Le nombre de programmes acceptés ne doit pas augmenter au prix d'une perte de
fidélité sémantique.
