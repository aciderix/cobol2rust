# Outils de validation

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
