# Fichiers .bat archivés (07/08/2026)

Ces `.bat` ont été déplacés hors de la racine lors du ménage de session. Ils ne
sont **pas supprimés** : les remettre à la racine suffit à les réactiver. Ils
correspondent à des étapes d'installation ponctuelles déjà faites, à des bancs
d'évaluation, ou à des scripts devenus **dangereux à relancer**.

## ⚠️ Dangereux à relancer — ne pas exécuter sans réflexion

- **`2 - Installer et nettoyer.bat`** — télécharge `qwen3-vl:4b` (ce n'est PAS le
  modèle de production `qwen3-vl:2b`) et **supprime `gemma4:e2b`**, le modèle
  challenger que la roadmap prévoit de tester. Le relancer casserait la config
  Ollama actuelle.
- **`13 - Reparer le GPU.bat`** — sa prémisse (« torch est la build CPU + dossier
  orphelin `~orch` ») est **déjà corrigée** : torch est en `2.13.0+cu130` (CUDA).
  Relancer `reparer_gpu.py --nettoyer` pourrait désinstaller/réinstaller torch et
  **re-casser** le GPU qui fonctionne.

## Remplacés par un guichet unique (19/08/2026)

`27 - Commit de session.bat`, `28 - Fusionner la branche dans main.bat` et
`30 - Nettoyer les branches fusionnees.bat` sont **remplacés par `27 - Git.bat`**
(menu : état + conseil, commit, fusion fast-forward, branches, GitHub). Leur code
y est repris tel quel, en sous-routines. Les remettre à la racine suffit à
revenir en arrière — ils fonctionnent toujours.

## Installation ponctuelle — déjà faite

`7`, `8`, `9`, `10`, `14` (installers visages/GPU/animaux/chats/recherche),
`11`, `12` (migrations SQLite + embeddings, terminées et vérifiées),
`20`, `21` (préparation et publication du dépôt git, faites).

## Bancs d'évaluation et outils de dev — ponctuels

`3`, `4`, `5`, `6`, `15`, `16`, `18`, `19`, `22`, `22b`, `23`. Utiles pour rejouer
une évaluation, mais pas dans le flux courant.

## Restés à la racine (courants)

`0` (démarrer), les deux `1` (Ollama, installateur nouveau PC), `17` (récupérer
illisibles), `24` (purger la corbeille — destructif mais bien protégé), `25`
(maintenance), `26` (ranger par année), `27 - Git.bat` (tout git), `29`
(nettoyage de session), les deux `Migrer` (export/import nouveau PC),
`Verifier GPU` et `Moniteur GPU` (diagnostic GPU, lecture seule).
