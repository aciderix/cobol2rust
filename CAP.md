# Cap du projet — à relire au début de chaque session

<!-- cap:début -->
**Cap : convertir le COBOL existant, tel qu'il est écrit et exploité, en Rust
au comportement identique.** Tout le COBOL réel, pas un corpus de test.

**Boussole : l'indicateur de progrès est l'acceptation des corpus réels**
(tableau « Mesure » de CAP.md, `measurements/real-corpora.json`), puis leur
compilation, exécution et comparaison. NIST CCVS85 n'est plus un objectif :
c'est un test de non-régression (451/458 émissions, 427/427 conformes).

Règles à chaque étape :
1. Choisir le chantier dans le tableau : d'abord l'écart « cobc accepte,
   cobol2rust refuse », par nombre de sources débloquées. Justifier dans le
   journal tout autre choix (profil IBM, CICS/SQL, limites, preuve).
2. Porter fidèlement cobc/libcob 3.2, vérifier sur un essai natif, refuser
   par un diagnostic nommé ce qui n'est pas reproduit. Implémenter la
   construction en entier, pas seulement la forme qu'un corpus exige.
3. Après tout changement du convertisseur : `python3 tools/real_corpora.py
   --cobc --record`, mesure NIST (451/458) et suite Python ; commiter les
   fichiers `measurements/` et CAP.md avec le code.
4. Ajouter une ligne au journal du cap (CAP.md) : ce qui a été levé et le
   chiffre avant/après.
5. Ne jamais présenter un acquis comme universel ; toujours donner le
   dénominateur. Un programme seulement compilé n'est pas « conforme ».
<!-- cap:fin -->

## Pourquoi ce document existe

La première partie (jusqu'à la PR `aciderix/cobol2rust#1`) a été pilotée
uniquement par les blocages de la suite NIST CCVS85. Elle a atteint le bilan
natif exact de GnuCOBOL 3.2 sur NIST, mais les corpus réels n'ont jamais été
re-mesurés après le 23 octobre 2026. Mesurés à nouveau le 25 octobre 2026 :
CardDemo (application mainframe AWS) **0/44**, zopeneditor-sample (IBM)
**0/5**, alors que cobc compile une partie de ces sources. Atteindre 100 % de
NIST mesurait surtout la progression vers NIST.

Pièges déjà rencontrés, à ne pas reproduire :

- piloter le développement par un seul corpus de conformité ;
- compter « conformes » des programmes seulement compilés (14 des 427 NIST) ;
- implémenter une fonctionnalité jusqu'à ce que le test passe (Report Writer
  sans ruptures de contrôle, limites de 18 chiffres et 256 caractères) ;
- utiliser une heuristique maison là où cobc a une règle (détection du
  format fixe/libre, résolution des noms de fichiers ASSIGN).

## Feuille de route vers l'universalité

Les étapes ne sont pas strictement séquentielles ; le tableau de mesure
décide de la prochaine.

1. **Écart à cobc sur les corpus réels** (profil GnuCOBOL 3.2 par défaut) :
   lever les refus de sources que cobc accepte.
2. **Preuve sur du code réel** : compiler, exécuter et comparer les
   programmes batch des corpus avec leurs données (niveaux 3 et 4 de
   COVERAGE.md), pas seulement les accepter.
3. **Limites du modèle** : 38 chiffres comme cobc (aujourd'hui 18), champs
   texte au-delà de 256 caractères, OCCURS et mémoire plus grands, COMP-5,
   niveau 78, EXIT PERFORM, Report Writer avec ruptures de contrôle.
4. **Profils de compilateur** : IBM Enterprise COBOL (`-std=ibm`, EBCDIC,
   binaire, ddnames), Micro Focus, ACUCOBOL ; un profil = options et
   représentation des données explicites.
5. **Services de plateforme** : adaptateurs EXEC SQL (DB2), EXEC CICS,
   EXEC DLI (IMS), MQ, VSAM, avec un contrat documenté par adaptateur.
6. **Corpus élargis** : testsuite GnuCOBOL (1346 cas `.at`), corpus métier
   de l'utilisateur dès qu'il en fournit, avec données et dialecte épinglés.
7. **Parcours sans sources** : binaire GnuCOBOL vers Rust, cible étroite
   d'abord.

## Mesure

Générée par `tools/real_corpora.py --cobc --record`, ne pas éditer à la main.
Les paramètres de chaque corpus sont figés dans l'outil ; niveau 2 de preuve
seulement (émission acceptée).

<!-- mesure:début -->
Dernière mesure : 2026-10-25T11:38:12+00:00 (commit `9eca7a97d0`, cobc (GnuCOBOL) 3.2.0). Commande : `python3 tools/real_corpora.py --cobc --record`.

| Corpus | Nature | Sources | cobol2rust accepte | cobc accepte | Écart (cobc oui, nous non) | À examiner (nous oui, cobc non) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| carddemo | application réelle IBM (CICS/VSAM/DB2/IMS/MQ) | 44 | 7 | 14 | 7 | 0 |
| zopeneditor-sample | application exemple IBM | 5 | 0 | 5 | 5 | 0 |
| cobol-programming-course | cours IBM Enterprise COBOL | 32 | 11 | 12 | 1 | 0 |
| beg-cobol-for-programmers | livre, programmes complets | 113 | 43 | 65 | 24 | 2 |
| proleap-cobol-parser | tests de parseur (fragments, dialectes) | 759 | 258 | 311 | 58 | 5 |
| che4z-lsp-for-cobol | tests de serveur de langage IBM | 1505 | 307 | 331 | 27 | 3 |
| **Total** | | **2458** | **626** | **738** | **122** | **10** |

Premiers blocages là où cobc accepte (tous corpus, premier diagnostic par source) :

1. 21 × PROCEDURE attendu
2. 18 × niveau de donnée attendu
3. 16 × niveau 88 de groupe limité aux littéraux alphanumériques
4. 7 × IDENTIFICATION DIVISION attendue
5. 6 × USAGE/clause non pris en charge
6. 6 × FILE-CONTROL attendu
7. 6 × expression attendue
8. 4 × RECORDING MODE limité à F pour des enregistrements fixes
9. 4 × instruction non prise en charge: XML
10. 3 × EXIT SECTION requiert une section de procédure
<!-- mesure:fin -->

## Journal du cap

Une ligne par étape : date, ce qui a été levé, total accepté avant → après.

- 2026-10-25 — Mise en place du cap, de l'outil `tools/real_corpora.py` et
  de la mesure de référence (avant toute extension du convertisseur) :
  230/2458, cobc 738, écart 518.
- 2026-10-25 — Détection du format portée de cobc (`ppopen_get_file`),
  ASSIGN complet (`assign_clause`, `validate_assign_name`) et résolution des
  noms à l'OPEN (`cob_chk_file_mapping`, `COB_FILE_PATH`) : **230 → 626**
  acceptées, écart 518 → 122, CardDemo 0 → 7/44. NIST inchangé (451/458).
