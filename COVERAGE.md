# Objectif : couverture universelle du COBOL vers Rust

> **Indicateur principal depuis le 25 octobre 2026 : les corpus réels**
> (tableau de [CAP.md](CAP.md), `tools/real_corpora.py`). Les sections NIST
> ci-dessous décrivent la première partie ; NIST est désormais un test de
> non-régression, pas une mesure de la couverture du COBOL existant.

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

Les formats variables et les autres clauses FD restent explicitement refusés
(les compteurs ADVANCING variables et LINAGE sont pris en charge depuis). Aucun résultat de cette étape ne
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

## Progression : CALL et programmes liés

CALL/CANCEL/LINKAGE (unité d'exécution multi-programmes, `--call-path lib` pour
le module IC) portent l'émission acceptée à **126/458** (dont 2 modules de
`IC/lib` vérifiés par leur appelant IC116M). Les 9 nouveaux programmes IC sont
conformes au runner natif (51 PASS ; `build/nist-verify-ic.json`) et la
revérification complète donne **124/124 programmes conformes**, 2077 PASS,
4 DELETED et 1 INSPECT natifs, aucun FAIL (`build/nist-verify-call.json`).
Obstacles IC restants : programmes imbriqués ou multiples par source, USAGE
INDEX, NEXT SENTENCE, EXTERNAL/GLOBAL, PICTURE avec B/0.

## Progression : NEXT SENTENCE, programmes frères et PICTURE P

NEXT SENTENCE (saut après le prochain point séparateur, y compris hors d'une
boucle inline), programmes frères dans un même source (résolus avant le chemin
d'appel, comme le résolveur de libcob) et PICTURE P portent l'émission acceptée
à **131/458**. Revérification complète : **129/129 programmes conformes**,
2180 PASS, 0 FAIL (`build/nist-verify-p.json`). Les sources NC à P bloquent
maintenant sur l'édition numérique générale (`/ , B 0 $ CR DB *`, P édité),
QUOTE, SYNCHRONIZED, CORRESPONDING, BLANK WHEN ZERO et RENAMES.

## Progression : édition numérique et alphanumérique, pliage des comparaisons

`cob_move_display_to_edited` et `cob_move_alphanum_to_edited` sont portés
symbole par symbole ; les images suivent `cb_build_picture` et la table de
précédence de cobc (63 images, aucun écart d'acceptation). Les comparaisons de
champs édités sont alphanumériques ; les comparaisons champ DISPLAY/littéral
suivent le pliage `compare_field_literal` de cobc (par exemple `S99 > -100`
vaut FAUX natif). S'y ajoutent BLANK WHEN ZERO, JUSTIFIED, QUOTE, VALUE ALL,
SIZE ERROR sur receveur édité, MOVE de champs P vers X et la valeur absolue dans
un receveur non signé. Émission acceptée : **141/458** ; revérification :
**139/139 programmes conformes**, 3072 PASS, 0 FAIL (`build/nist-verify-editing.json`).

## Progression : SIGN, SYNCHRONIZED et clauses de données

Clause SIGN (LEADING/TRAILING, SEPARATE, héritée du groupe) comme
`cob_real_get_sign`/`cob_real_put_sign`, affichage du signe séparé final comme
`pretty_display_numeric`, SYNCHRONIZED sans remplissage (DISPLAY ou binaire déjà
aligné ; le remplissage de `compute_size` reste refusé), FILLER implicite,
`88 … VALUE ALL` et constantes figuratives de niveau 88, VALUE ZERO sur PIC X.
Émission acceptée : **153/458** ; revérification : **151/151 programmes
conformes**, 3656 PASS, 0 FAIL (`build/nist-verify-sign.json`).

## Progression : formes arithmétiques, HIGH/LOW-VALUE, START >=

`ADD a b GIVING c` sans TO, `DIVIDE … BY … GIVING`, REMAINDER (reste calculé
sur le quotient complet tronqué à l'échelle du quotient, comme
`cob_div_quotient`), HIGH-VALUE/LOW-VALUE (octets 0xFF/0x00 en VALUE, MOVE,
comparaisons ALL et niveaux 88) et `START … >=`/`GREATER OR EQUAL` (COB_GE).
Émission acceptée : **166/458** ; revérification : **164/164 programmes
conformes**, 4296 PASS, 0 FAIL (`build/nist-verify-arith.json`).

## Progression : SORT et MERGE

SD, SORT/MERGE (clés ASCENDING/DESCENDING, WITH DUPLICATES), USING/GIVING
SEQUENTIAL et LINE SEQUENTIAL à enregistrements fixes, INPUT/OUTPUT PROCEDURE,
RELEASE [FROM] et RETURN [INTO] AT END, abaissés comme le C de cobc
(`cob_file_sort_init`, PERFORM des procédures, `cob_file_sort_close`). Le tri
est celui de libcob : stable, clés numériques par valeur, les autres octet par
octet ; MERGE est un tri stable des fichiers USING dans l'ordre. Les FILE
STATUS des fichiers USING/GIVING ne sont pas mis à jour, comme en natif.
Émission acceptée : **182/458** ; revérification : **180/180 programmes
conformes**, 4474 PASS, 0 FAIL (`build/nist-verify-sort.json`).

## Progression : segments, CLOSE REEL/UNIT/NO REWIND

Numéros de segment de SECTION acceptés (sans effet hors ALTER, toujours
refusé, comme dans codegen.c), `CLOSE REEL/UNIT [FOR REMOVAL]` (le fichier reste
ouvert, 07) et `CLOSE WITH NO REWIND` (fermé, 07) comme `cob_file_close`,
`OPEN … WITH NO REWIND/REVERSED` ignorés comme par cobc, et `file_runtime.rs`
fourni quand seul un sous-programme a des fichiers. Émission acceptée :
**198/458** ; revérification : **196/196 programmes conformes**, 4566 PASS,
0 FAIL (`build/nist-verify-close.json`).

## Progression : SPECIAL-NAMES et ACCEPT

SPECIAL-NAMES : noms mnémoniques (DISPLAY UPON SYSOUT/CONSOLE/SYSERR, ACCEPT
FROM SYSIN/CONSOLE, comme `cb_build_display_mnemonic`), SWITCH-n et leurs
conditions ON/OFF (`COB_SWITCH_n` lu comme `cob_init`, SET … TO ON/OFF),
ALPHABET NATIVE/STANDARD-1/STANDARD-2/ASCII (table identité `cob_native`, d'où
PROGRAM COLLATING SEQUENCE et SORT COLLATING acceptés pour ces alphabets),
CLASS utilisateur et SYMBOLIC CHARACTERS. ACCEPT suit `cob_accept` (ligne
jusqu'au LF, CR conservé, troncature des DISPLAY numériques, MOVE
alphanumérique). `nist_verify` reproduit `COB_SWITCH_1=ON`/`COB_SWITCH_2=OFF`
de report.pl. Émission acceptée : **205/458** ; revérification : **203/203
programmes conformes**, 4650 PASS, 0 FAIL (`build/nist-verify-special.json`).

## Progression : SEARCH, USAGE INDEX, INSPECT, EVALUATE

SEARCH et SEARCH ALL (code généré par cobc, y compris une condition 88 de clé
comme `build_cond_88`), USAGE INDEX explicite (entier natif petit-boutiste),
INSPECT TALLYING/REPLACING/CONVERTING porté de `strings.c` (tampons statiques,
marquage LEADING incomplet, signe incrusté, `cob_add_int` tronquant), EVALUATE
réécrit d'après `cb_emit_evaluate` (ALSO, ANY, THRU, NOT, TRUE/FALSE, WHEN
consécutifs), ELSE imbriqués sans END-IF, 88 de groupe, SET mixte index/entier,
BY et ON facultatifs dans INDEXED BY / DEPENDING ON, KEY après INDEXED,
littéraux signés du scanner de cobc dans les sous-scripts, et passage BY
REFERENCE de l'allocation entière d'un groupe ODO (IC207A). Émission acceptée :
**229/458** ; revérification : **227/227 programmes conformes**, 5269 PASS,
0 FAIL (`build/nist-verify-inspect.json`, `build/nist-verify-subscripts.json`).

## Progression : conditions cobc, STRING/UNSTRING

`conditions.py` porte `cb_build_expr` (conditions abrégées, NOT, signe,
classes) ; STRING et UNSTRING suivent `strings.c` ; les mots réservés de cobc
sont refusés comme noms (NC211A, que cobc rejette, n'est plus accepté).
Émission acceptée : **233/458** ; revérification : **231/231 programmes
conformes**, 5497 PASS, 0 FAIL (`build/nist-verify-conditions.json`,
`build/nist-verify-string.json`).

## Progression : fichiers, RENAMES, exponentiation

Ordre libre des clauses SELECT, PADDING, RECORD DELIMITER, VALUE OF, SAME
RECORD AREA, RENAMES, REDEFINES 01 plus grand, `**`, ALL figuratif, MOVE -0,
comparaisons numériques/figuratives. Émission acceptée : **251/458** ;
revérification : **249/249 programmes conformes**, 5841 PASS, 0 FAIL
(`build/nist-verify-files-renames.json`).

## Progression : CORRESPONDING, troncature DISPLAY, dé-édition

Émission acceptée : **256/458** ; revérification : **254/254 programmes
conformes**, 6104 PASS, 0 FAIL (`build/nist-verify-corresponding.json`).

## Progression : COPY REPLACING

Émission acceptée : **262/458** ; revérification : **260/260 programmes
conformes**, 6156 PASS, 0 FAIL (`build/nist-verify-copy-replacing.json`).

Depuis : `REPLACING LEADING ==mot== BY ==…==` et `TRAILING` (COPY et REPLACE),
portage de `is_leading_or_trailing`/`ppecho_leading_or_trailing` ; les 5
sources de la testsuite GnuCOBOL qui en dépendaient sont identiques à cobc.

## Progression : fonctions intrinsèques

Port de libcob/intrinsic.c pour INTEGER, INTEGER-PART, MOD, REM, FACTORIAL,
SUM, MEAN, MEDIAN, MIDRANGE, RANGE, VARIANCE, ORD-MAX, ORD-MIN, MAX, MIN,
ANNUITY, PRESENT-VALUE, CHAR, ORD, UPPER-CASE, LOWER-CASE (ASCII), REVERSE, TRIM
[LEADING|TRAILING] (`cob_intr_trim`, résultat vide pour un argument tout en espaces), HEX-OF, HEX-TO-CHAR,
INTEGER-OF-DATE/DAY, DATE-OF-INTEGER, DAY-OF-INTEGER, NUMVAL, NUMVAL-C et
LENGTH (littéral à la compilation pour un item fixe, comme cb_build_intrinsic).
Restent refusées : RANDOM et la modification de référence d'un résultat
(CURRENT-DATE et WHEN-COMPILED sont portés depuis, voir plus bas) (SQRT, LOG, LOG10, EXP, SIN, COS, TAN, ASIN, ACOS,
ATAN, STANDARD-DEVIATION, PI et E sont portés depuis : voir plus bas).
`tools/coverage.py` émet les sources à PROCEDURE DIVISION USING comme
sous-programmes. Émission acceptée : **313/458** (dont 24 sous-programmes) ;
revérification : **289/289 programmes principaux conformes**, 6608 PASS,
0 FAIL (`build/nist-verify-intrinsics.json`).

Depuis (mesure des corpus réels) : ABS, FRACTION-PART, EXP10, CONCATENATE,
CONCAT, SUBSTITUTE, SUBSTITUTE-CASE, STORED-CHAR-LENGTH, HIGHEST-ALGEBRAIC,
LOWEST-ALGEBRAIC, TEST-DATE-YYYYMMDD, TEST-DAY-YYYYDDD, YEAR-TO-YYYY,
DATE-TO-YYYYMMDD et DAY-TO-YYYYDDD, et le DISPLAY du champ résultat des
fonctions numériques (`cob_alloc_field`, `cob_alloc_set_field_uint`, copie
d'argument) ; puis les fonctions ISO 8601 (FORMATTED-*, TEST-FORMATTED-DATETIME,
INTEGER-OF-FORMATTED-DATE, SECONDS-FROM-FORMATTED-TIME) ; voir le README,
« Fonctions intrinsèques ».

## Progression : ALTER, noms de procédure, dialecte cobol85

ALTER (label_N de cobc, remise à zéro des paragraphes de segments
indépendants à la chute dans la SECTION, au PERFORM et au GO TO d'un autre
segment), GO TO sans cible, noms de procédure homonymes qualifiés IN/OF et
entièrement numériques (`cb_ref`), PERFORM a THRU b inversé, PERFORM en ligne
sans option, compteur TIMES selon `cob_get_llint` et `cb_check_integer_value`,
STOP littéral. Option `--std cobol85` : `section-segments` et `defaultbyte:
none`. Émission acceptée : **327/458** ; revérification : **302/303
programmes principaux conformes**, 6980 PASS, 0 FAIL
(`build/nist-verify-alter.json`) ; OBNC1M diverge sur SIGINT (non modélisé).

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

## Progression : DEBUGGING MODE

`SOURCE-COMPUTER ... WITH DEBUGGING MODE` active les lignes D qui suivent
(pplex.l) ; `USE FOR DEBUGGING` sur procédures, `ALL PROCEDURES` et fichiers
(OPEN, CLOSE, READ, DELETE, START) ; DEBUG-ITEM construit comme
`cb_build_debug_item` ; DEBUG-LINE de la dernière instruction commencée,
DEBUG-NAME dans l'orthographe de la première occurrence du mot,
DEBUG-CONTENTS (START PROGRAM, PERFORM LOOP, FALL THROUGH, USE PROCEDURE,
SORT INPUT/OUTPUT, MERGE OUTPUT, cible d'ALTER, enregistrement lu) ;
sections de débogage actives selon `COB_SET_DEBUG`. Les identifiants surveillés
(`ON identifiant`, `ALL REFERENCES OF`) restent refusés. Émission acceptée :
**336/458** ; revérification : **311/312 programmes principaux conformes**,
7275 PASS, 0 FAIL (`build/nist-verify-debugging.json`).

## Progression : INDEXED

Port des fonctions Berkeley DB de fileio.c (`indexed_open`, `start_internal`,
`read_next`, `write_internal`, `delete_internal`, `rewrite`, `check_alt_keys`,
`get_dupno`) sur des btrees ordonnés comme BDB (memcmp, doublons dans l'ordre
d'insertion, numéro de doublon natif). Comportements de libcob conservés : pas
de statut 02 (écrasé par DB_PUT), REWRITE séquentiel à clé changée accepté,
21 au lieu de 22 en écriture séquentielle OUTPUT. Format disque propre à
cobol2rust (fichiers `nom`, `nom.1`, ...), non interchangeable avec les
fichiers BDB de GnuCOBOL. Refusés : clés composées (SOURCE IS), SUPPRESS,
READ PREVIOUS, LOCK. Émission acceptée : **375/458** ; revérification :
**350/351 programmes principaux conformes** (`build/nist-verify-indexed.json`).

## Progression : PROGRAM COLLATING SEQUENCE et fonctions mathématiques

Alphabets littéraux (`validate_alphabet` : littéraux, `THRU`, `ALSO`, doublons
refusés comme cobc) utilisés comme PROGRAM COLLATING SEQUENCE : la table de
pondération remplace l'ordre natif dans `cob_cmp_alnum`/`cob_cmp_all` et dans
le SORT du module ; LOW-VALUE est le premier caractère de l'alphabet et
HIGH-VALUE suit `cb_validate_collating`. Deux littéraux comparés par `=` ou
`<>` restent pliés sur leurs octets bruts (tree.c). Fonctions SQRT, LOG,
LOG10, EXP, SIN, COS, TAN, ASIN, ACOS, ATAN, STANDARD-DEVIATION, PI et E :
calcul en virgule flottante décimale à 150 chiffres, ramené à 96 chiffres
significatifs arrondis au plus proche comme `cob_decimal_set_mpf`
(COB_MAX_INTERMEDIATE_FLOATING_SIZE). Émission acceptée : **390/458** ;
revérification : **365/366 programmes principaux conformes**, 8066 PASS,
0 FAIL (`build/nist-verify-math.json`, `build/coverage-nist-math.json`).

## Progression : LINAGE, ADVANCING et formes de préprocesseur

Port de `cob_linage_write_opt`, `file_linage_check` et `lineseq_write` (marge
haute au premier WRITE, saut de page, statut 57, END-OF-PAGE via `check_eop`),
ADVANCING sur LINE SEQUENTIAL, par identifiant, ZERO et mnémonique
FORMFEED/Cnn, qualification d'un enregistrement par son FD (`PRINT-REC IN
PRINT-FILE`). Formes levées au passage : `TEST BEFORE/AFTER` sans WITH, liste de
mots réservés `cobol85.words` en `--std cobol85`, `[NOT] [ON] SIZE ERROR` qui ne
capture plus le NOT ON EXCEPTION d'un CALL englobant, articles frères
homonymes, I-O-CONTROL vide, instruction REPLACE, `COPY … OF|IN`, zone de
séquence quelconque, `SET` à plusieurs groupes de commutateurs, terminateur de
portée qui ferme les instructions conditionnelles englobées. Émission
acceptée : **407/458** ; revérification : **382/383 programmes principaux conformes**, 8325 PASS, 0 FAIL
(`build/nist-verify-linage.json`, `build/coverage-nist-linage.json`).

## Progression : OCCURS DEPENDING, symboles du module, INITIALIZE REPLACING

Contrôleur OCCURS DEPENDING interne au groupe (longueur maximale pour le
récepteur d'un MOVE, `flag_receiving`), tables variables dans les
enregistrements FD (taille courante à WRITE/REWRITE, `record_min` selon
`occurs_min`), ELSE et WHEN qui ferment les instructions conditionnelles
englobées ; CURRENCY SIGN et DECIMAL-POINT IS COMMA (scanner, PICTURE, édition,
NUMVAL, affichage) ; MOVE de littéral alphanumérique vers numérique DISPLAY
(`cb_build_move_literal`) et MOVE ALL vers alphanumérique édité ; INITIALIZE
REPLACING (`output_initialize_one`) ; SORT USING/GIVING de fichiers SEQUENTIAL
variables ; CODE-SET d'alphabet natif ignoré ; programmes contenus (visibilité
directe ou COMMON), articles GLOBAL partagés avec les descendants, articles
EXTERNAL par nom (`cob_external_addr`) ; FUNCTION CURRENT-DATE (horloge
système, fuseau UTC seul modélisé) et WHEN-COMPILED (littéral de l'heure de
conversion, comme `cb_set_intr_when_compiled`). Émission acceptée :
**426/458** ; revérification : **401/402 programmes principaux conformes**, 9303 PASS, 0 FAIL
(`build/nist-verify-odo.json`, `build/coverage-nist-odo.json`).

## Progression : Report Writer

Port de `reportio.c` sans ruptures de contrôle (`do_page_heading`,
`do_page_footing`, `report_line`, `report_line_type`, `cob_report_generate`,
`cob_report_terminate`) et des règles de cobc pour la REPORT SECTION
(`page_limit_clause`, `finalize_report`, `output_report_define_lines`) : FD
REPORT, RD avec limites de page littérales, groupes RH/PH/DE/PF/RF, LINE [PLUS],
COLUMN, SOURCE, VALUE, LINE-COUNTER et PAGE-COUNTER. Émission acceptée :
**430/458** ; revérification : **405/406 programmes principaux conformes**,
9343 PASS, 0 FAIL (`build/nist-verify-report.json`,
`build/coverage-nist-report.json`).

## Progression : USE FOR DEBUGGING sur articles

Port de `cb_check_field_debug` (liste `debug_check` de chaque instruction,
émise après son corps sous `cob_debugging_mode`), des cas inline de codegen.c
(`output_goto`, `output_perform`, `output_perform_until`, `output_cond_debug`)
et de typeck.c (pas de PERFORM VARYING, enregistrement de WRITE/REWRITE) ;
option `--fno-ec-data-incompatible` pour DB201A. Émission acceptée :
**434/458** ; revérification : **409/410 programmes principaux conformes**,
9438 PASS, 0 FAIL (`build/nist-verify-debug-items.json`,
`build/coverage-nist-debug-items.json`).

## Progression : horloge, RANDOM, comparaisons littérales, SD à ODO

Port de `cob_get_current_datetime` et `check_current_date` (ACCEPT FROM
DATE/DAY/DAY-OF-WEEK/TIME, COB_CURRENT_DATE), de FUNCTION RANDOM (Mersenne
Twister de GMP 6.3.0, `mpf_urandomb` puis `mpf_get_d`), de
`compare_field_literal` pour les comparaisons d'un numérique à un littéral
alphanumérique, et de `cob_file_sort_using/giving` pour un SD à OCCURS
DEPENDING. Émission acceptée : **439/458** ; revérification : **414/415
programmes principaux conformes**, 9555 PASS, 0 FAIL
(`build/nist-verify-isolated.json`, `build/coverage-nist-isolated.json`).

## Progression : fin de la première partie

FD EXTERNAL/GLOBAL et USE GLOBAL (registre de fichiers partagés, alias du
programme déclarant exécutant sa section comme l'entrée 2 de cobc), programmes
INITIAL, 66 homonyme, LINE SEQUENTIAL à tailles multiples, RD sans PAGE et
contrôle des LINE à l'INITIATE, COMMUNICATION SECTION telle que cobc 3.2
l'analyse sans l'implémenter, SIGINT sur le caractère 03 lu par ACCEPT.
Émission acceptée : **451/458** (les 7 refus sont des programmes CM que cobc
ne compile pas) ; revérification : **427/427 programmes principaux
conformes**, 9610 PASS, 0 FAIL, 20 DELETED, 118 INSPECT, le bilan exact du
runner natif (`build/nist-verify-final.json`, `build/coverage-nist-final.json`).

## Progression : données invalides sans contrôles d'exécution

Sans `-debug`, libcob calcule avec les données numériques invalides : port de
`COB_D2I` et des cas X"FF"/X"00" de `cob_decimal_set_display`, du packé lu
par quartets, de la sélection de cobc pour les comparaisons
(`cb_build_cond_default`, `cb_check_num_cond`, `cb_build_optim_cond`,
`cob_numeric_cmp`), des copies de `cb_build_move_field`, de
`cb_build_move_high/low`, de l'affichage par `cob_move_display_to_edited` et
des clés de `cob_file_sort_compare`. Fixtures `invalid_numeric_data`,
`invalid_numeric_compare`, `invalid_numeric_move` identiques à cobc. Sur code
réel (`tools/real_corpora.py --execute`) : 65/74 programmes acceptés
identiques (CardDemo 8/8, zopeneditor 3/3, cours 9/11, livre 45/52) ; les
autres sont un indice hors bornes et des programmes interactifs sans jeu
d'entrée (délai). Avec `--runtime-checks`, toute donnée invalide reste un arrêt
nommé.

## Progression : ENTRY, modules et LENGTH OF

Port de `emit_entry` et `output_entry_function` (ENTRY littéral avec USING,
liaison par point d'entrée, nom résolu une fois le module chargé comme par
`cob_resolve`), d'un programme à PROCEDURE DIVISION USING exécuté comme
module (`cobc -m` puis `cobcrun`, sans argument), d'un article LINKAGE sans
adresse, de `cb_build_length` et de DEPENDING ON qualifié. Acceptation des
corpus réels : 685 → 693/2458 ; CardDemo 14/44 et zopeneditor 5/5, autant
que cobc. Les modules acceptés ne sont pas exécutés par la mesure (ils
attendent un appelant) ; un accès à un paramètre non transmis est un arrêt
nommé, là où GnuCOBOL lit une adresse indéterminée.

## Progression : SORT de table et formes du livre

Port de `cob_table_sort` (tri fusion stable de `qsort` en glibc 2.39, clés
numériques par `cob_numeric_cmp`, autres par `memcmp` ou la séquence de
classement du programme, offset de clé relatif à son parent comme
`cb_emit_sort_init`, clé OCCURS par défaut, élément entier pour KEY sans nom),
INSPECT TALLYING d'un littéral ou d'une fonction (`cb_emit_inspect`),
sous-chaîne d'un résultat de fonction, IF terminé par le terminateur d'une
instruction englobante, entrées documentaires sans IDENTIFICATION DIVISION,
CLASS avec figuratives, FD à enregistrement numérique. Fixtures
`table_sort`, `scope_and_function_forms`, `numeric_record` identiques à cobc.
Corpus réels : 703/2458 acceptées (cobc 738) ; cours 12/12, livre 62/113.

## Progression : Report Writer avec ruptures de contrôle

Port de `cob_report_generate`, `cob_report_terminate`, `report_line_and`,
`report_line_type` (arrêt des pieds de séquence supérieure),
`zero_all_counters`, `sum_all_detail`, `sum_this_counter`, `set_next_info` et
`clear_group_indicate` de reportio.c, de `build_sum_counter` (tree.c) et de
l'ordre des listes de codegen.c (`output_report_control`,
`output_report_sum_counters`). Fixture `report_controls` (deux contrôles et
FINAL, cumuls de SUM, NEXT GROUP PLUS et NEXT PAGE, débordement de page,
GROUP INDICATE) identique à cobc ; NIST RW101A-RW104A, RW301M, RW302M
conformes. Corpus réels : 715/2458 acceptées (cobc 738), livre 64/65.

## Progression : NUMVAL-F et validateurs — 28 octobre 2026

Après reprise des branches Claude intégrées à `main`, la mesure est refaite
sur les sept corpus : **1191 → 1195 émissions sur 3593 sources**, cobc 1617,
**écart 426 → 422**, aucune acceptation refusée par cobc dans ces corpus.
Testsuite : **467 → 471/1135**, six corpus d'origine inchangés à 724/2458.

NUMVAL-F porte `cob_intr_numval_f` ; TEST-NUMVAL/TEST-NUMVAL-C/TEST-NUMVAL-F
portent les validateurs natifs, positions d'erreur et symboles du module.
Les noms nouveaux ne partagent pas un parseur décimal simplifié : la
conversion permissive reste distincte des tests. Les champs et littéraux
sont lus en stockage, avec provenance lexicale du signe ; les temporaires
numériques calculés et capacités hors limites restent des refus nommés.

Dix tests ciblés passent. Les quatre programmes débloqués s'exécutent à
l'identique de cobc, comme les deux profils indépendants point/virgule
(412 résultats) : `build/numval-real-source-verification-20261028.json`.
NIST statique reste à **451/458**, sans erreur interne ; aucun nouveau
passage complet du runner NIST ni exécution globale des autres corpus n'est
revendiqué ici. Les détails et limites sont dans [VALIDATION.md](VALIDATION.md).
La suite découvre 431 tests : 430 validés, un PE Windows ignoré, avec
réexécution réussie des deux contrôles initialement bloqués par la dépendance
de développement Berkeley DB absente du cloud.

## Progression : paramètres ANY LENGTH — 29 octobre 2026

Les paramètres LINKAGE `01 arg [PIC X] ANY LENGTH` ont un descripteur de
taille dynamique. Les opérations et les niveaux 88 l'utilisent, y compris
les sous-chaînes, la retransmission et les appels de tailles successives.
Le comportement natif d'ENTRY et la persistance après CANCEL/INITIAL sont
portés ; les formats ANY NUMERIC et le partage GLOBAL restent refusés.

La mesure passe de **1195 à 1203/3593 émissions acceptées** : testsuite
**471 → 479/1135**, écart à cobc **422 → 414**, zéro acceptation refusée par
cobc dans les corpus. NIST statique reste à **451/458**, sans erreur interne.
Suite Python complète : **447/448 validés**, un PE Windows ignoré ;
les 17 nouveaux tests ANY LENGTH réussissent.
Les huit sources débloquées comprennent quatre programmes comparés au
natif (**4/4 identiques**) et leurs deux callees, plus deux modules
syntaxiques seulement compilés des deux côtés.

La comparaison globale est renouvelée : **70/84 identiques**, six
divergences et huit délais (stdin vide, données du dossier source). Les
trois exemples zopeneditor présentent désormais un crash natif à la
fermeture implicite, avec sorties et fichiers identiques ; ils sont donc
comptés divergents. Les détails sont dans [VALIDATION.md](VALIDATION.md).

## Progression : capacité ODO et entrées réelles — 29 octobre 2026

Une référence indexée ODO utilise la capacité déclarée sans contrôles
d'exécution ; les contrôles valident la borne courante. Longueur des
groupes et SORT restent fondés sur le compteur. Cette règle générale rend
Listing13-6 identique au natif sans dépendre de son nom ni de ses valeurs.
Les quatre conversions calendaires renvoient zéro hors domaine dans le
modèle numérique existant, avec leurs largeurs natives à l'affichage.

Acceptation inchangée : **1203/3593**, écart 414, zéro acceptation refusée
par cobc dans les corpus. Exécution de référence : **71/84 identiques**,
cinq divergences et huit délais ; livre **53/61**. NIST statique reste
à **451/458**, sans erreur interne.

Un moteur générique lit les scénarios versionnés de
`measurements/real-input-cases.json` : **11/11 comparaisons identiques sur
cinq programmes interactifs**, avec sources, stdin et dossiers épinglés.
Ce résultat garde son dénominateur ; il ne remplace pas la mesure à stdin
vide. Les deux rapports hors capacité physique et les trois plantages
natifs zopeneditor restent des divergences de cette mesure. Les détails
et limites sont dans [VALIDATION.md](VALIDATION.md).
Suite Python complète : **459/460 validés**, un PE Windows ignoré, aucun
échec ni erreur. Les douze nouveaux tests couvrent ODO, calendrier et moteur
de scénarios ; les deux tests calendaires comparent 119 résultats natifs.

## Progression : capture des SOURCE de rapports — 29 octobre 2026

Les SOURCE indicées, modifiées par référence ou locales sont préparées dans
des temporaires typés distincts, comme `finalize_report` et `cb_field_dup`.
Les deux listes de `cb_emit_report_moves` précèdent GENERATE ; seule la
seconde précède TERMINATE. L'état natif persistant du parcours et l'ordre de
première utilisation des rapports sont conservés. Les sources simples et
compteurs restent lus à l'impression. Un contre-exemple valide auparavant
divergent produit désormais les mêmes 38 octets que GnuCOBOL.

Les positions de sous-chaînes SOURCE suivent le repli constant natif et ses
conversions entières. Les dépassements constants, puissances non repliées,
divisions par une constante zéro et descriptions de copies non reproduites
sont des refus nommés. Les limites générales de lecture des indices et des
champs numériques restent applicables ; USE BEFORE REPORTING reste refusé.

Dix-sept nouveaux tests couvrent capture, typage, initialisation, contrôles,
LOCAL-STORAGE, TERMINATE, ordre des rapports et 23 positions dans les deux
profils. Avec les tests Report Writer existants : **26/26 réussis**.
Acceptation statique inchangée : **1203/3593**, aucun changement de statut
des sources des sept corpus ; NIST statique **451/458**, sans erreur interne.
Les sources et données des corpus n'ont pas été modifiées.
L'exécution de référence est aussi renouvelée : **71/84 identiques**, cinq
divergentes et huit délais, avec les mêmes programmes dans chaque catégorie.
Les scénarios avec entrées déclarées restent **11/11 identiques**, avec leur
propre dénominateur. Suite Python complète : **476/477 validés**, un PE
Windows ignoré, aucun échec ni erreur. Bilan des preuves :
`build/report-source-validation-20261029.json`.

## Progression : routines système d'octets — 30 octobre 2026

Port des huit opérations logiques CBL sur les octets et de TOUPPER/TOLOWER,
avec leurs alias : douze noms de `system.def`. Les lectures et écritures
gardent les alias vivants et les chevauchements ; BY CONTENT isole sa copie.
La longueur non positive ne touche pas aux adresses. Les scalaires BY VALUE
de ces routines suivent le profil Linux x86_64 ; les autres ABI et CALL
RETURNING restent refusés, ainsi que les descriptions de résultats de
FUNCTION non reproduites. Un BY VALUE alphanumérique devient BY CONTENT,
sans rendre les paramètres formels BY VALUE compatibles.

Acceptation **1203 → 1214/3593**, testsuite **479 → 490/1135**, écart à cobc
**414 → 403**, aucune acceptation refusée par cobc. Les six autres corpus
restent à 724/2458. NIST statique **451/458**, zéro erreur interne.
Exécution globale renouvelée : **71/84 identiques**, cinq divergences et
huit délais. Les onze nouvelles sources sont validées séparément ; elles
n'entrent pas dans le dénominateur des 84 programmes batch d'origine.
Les dix programmes de routines s'exécutent à l'identique avec des codes
zéro. Le cas syntaxique restant s'arrête des deux côtés sur PROG2 absent
(codes 1/1) et n'est pas compté comme une exécution réussie.

Quatorze tests ajoutés, dont une fixture de **3072 octets** sur toutes les
valeurs d'octet et **29 longueurs scalaires dans deux profils**. Avec les
appels existants, **22/22 tests ciblés réussissent**. Les détails, limites
et preuves sont dans [VALIDATION.md](VALIDATION.md).
Suite Python complète : **490/491 validés**, un PE Windows ignoré, sans
échec ni erreur. Les scénarios d'entrée restent **11/11 identiques**,
distincts des campagnes des corpus et des nouvelles sources.
Preuves : `build/system-calls-validation-20261030.json`.

## Progression : modèle d'adresses — 30 octobre 2026

`USAGE POINTER`, `BASED`, `ADDRESS OF`, `SET … TO/UP BY/DOWN BY`, `ALLOCATE`
et `FREE` suivent cobc 3.2 (`cb_check_set_to`, `cb_emit_allocate_identifier`,
`cb_emit_allocate_characters`, `cob_allocate`, `cob_free_alloc`). Une adresse
native devient une région (chaque 01/77 d'un programme, zone ALLOCATE, bloc
EXTERNAL, copie BY CONTENT) et un décalage, dans les 8 octets du POINTER ;
tout accès hors région, par NULL ou après FREE est un arrêt nommé. Une zone
`malloc` (ALLOCATE sans INITIALIZED TO) est suivie octet par octet : lire un
octet jamais écrit est un arrêt nommé. Un ASSIGN vers un article sans adresse
donne le statut 31 avec le nom `field with NULL address`
(`cob_field_to_string`). Restent des arrêts nommés le DISPLAY d'une adresse
non NULL (ASLR) et l'ordre de deux régions ; restent refusés les pointeurs BY
VALUE, PROGRAM-POINTER/FUNCTION-POINTER, l'arithmétique hors SET et VALUE en
LINKAGE hors article BASED.

Acceptation **1214 → 1225/3593**, testsuite **490 → 501/1135**, écart à cobc
**403 → 392**, aucune acceptation refusée par cobc. Sur les onze sources
débloquées, sept s'exécutent à l'identique avec des codes zéro ;
run_file-020/prog s'arrête des deux côtés sur le statut 31 avec le même
message (codes 1/1, pas compté comme réussite) ; data_pointer-001 s'arrête
nommément sur le DISPLAY d'une adresse ; les deux programmes de run_misc-115
plantent en natif (SIGSEGV) là où Rust s'arrête nommément. Exécution globale
renouvelée : **74/84 identiques**, deux divergences et huit délais ;
zopeneditor passe de 0/3 à 3/3 sans changement côté Rust (le plantage natif à
la fermeture implicite n'est plus observé). NIST statique **451/458**.
Fixtures `pointers.cob` et `pointer_tables.cob` identiques au natif ;
détails dans [VALIDATION.md](VALIDATION.md).

## Progression : dernière exception — 30 octobre 2026

`FUNCTION EXCEPTION-STATUS`, `EXCEPTION-LOCATION`, `EXCEPTION-STATEMENT`,
`EXCEPTION-FILE` et `SET LAST EXCEPTION TO OFF` suivent la dernière exception
de libcob (`cob_set_exception`, table `exception.def`), commune à l'unité
d'exécution. Sources portées : `save_status`, division par zéro, stockages
arithmétiques DISPLAY ou édités (`cob_decimal_get_display`), SIZE ERROR,
ROUNDED MODE PROHIBITED, STRING/UNSTRING, INSPECT, ALLOCATE/FREE, ACCEPT en
fin d'entrée, CALL introuvable ou récursif sous ON EXCEPTION, MOD/REM et
fonctions ISO 8601. Toute autre source possible rend l'exception inconnue :
sa lecture est alors un arrêt nommé. Sous `-debug`, EXCEPTION-LOCATION et
EXCEPTION-STATEMENT restent refusées.

Acceptation **1225 → 1240/3593**, testsuite **501 → 516/1135**, écart à cobc
**392 → 377**, aucune acceptation refusée par cobc. Douze des quinze sources
débloquées s'exécutent à l'identique avec des codes zéro, deux à l'identique
avec le code 1 voulu par le test ; la troisième de run_misc-040, exécutée
seule, ne diffère que par la pile de l'erreur fatale de libcob. Exécution
globale **74/84**, inchangée ; NIST statique **451/458**. Fixtures
`exceptions.cob` et `exception_recursive_call.cob` identiques au natif ;
détails dans [VALIDATION.md](VALIDATION.md).

## Progression : START complet et READ PREVIOUS — 30 octobre 2026

START suit `cob_start` pour toutes les conditions de `start_op` (=, >, >=,
<, <= et leurs formes NOT), FIRST, LAST et `WITH SIZE/LENGTH`, en RELATIVE
(`relative_start`) et INDEXED (`indexed_start_internal`, Berkeley DB). READ
PREVIOUS suit `cob_read_next`, `relative_read_next` (reculs de libcob 3.2
compris) et `indexed_read_next`. Acceptation **1240 → 1245/3593**, testsuite
**516 → 521/1135**, écart **377 → 372** ; les cinq sources débloquées
s'exécutent à l'identique avec des codes zéro. Exécution globale **74/84**,
inchangée ; NIST statique **451/458**. Fixture `start_previous.cob`
identique au natif.

## Progression : INITIALIZE VALUE et DEFAULT — 30 octobre 2026

`INITIALIZE … {ALL|catégorie} [TO] VALUE … [THEN] [TO] DEFAULT` suit
`cb_emit_initialize`, `deduce_initialize_type` et `output_initialize` : VALUE
de l'article ou du groupe, REPLACING, puis ZERO/SPACE ; un article OCCURS est
initialisé dans sa première occurrence, recopiée sur les autres
(`propagate_table`). Acceptation **1245 → 1250/3593**, testsuite **521 →
526/1135**, écart **372 → 367** ; les cinq sources débloquées s'exécutent à
l'identique avec des codes zéro. Exécution globale **74/84**, inchangée ;
NIST statique **451/458**. Fixture `initialize_value.cob` identique au natif.

## Progression : EXTERNAL AS — 31 octobre 2026

`EXTERNAL [AS littéral]` désigne le bloc de l'unité d'exécution par le nom C de
`cb_to_cname` ; `cob_external_addr` est porté (première déclaration,
avertissement pour une plus courte, erreur pour une plus longue). Acceptation
**1250 → 1255/3593**, testsuite **526 → 531/1135**, écart **367 → 362** ;
quatre des cinq sources débloquées s'exécutent à l'identique avec des codes
zéro, la cinquième s'arrête des deux côtés sur l'erreur de taille. Exécution
globale **74/84**, inchangée ; NIST statique **451/458**. Fixture
`external_as.cob` identique au natif.
