# Workflow git / GitHub — MediaLibrary

Comment le code circule entre le sandbox de Claude, la machine de Mike et GitHub
(`TheMikeHoogly/MediaLibrary`, privé).

## Les deux contraintes qui commandent tout
1. **Le sandbox ne peut pas pousser** (pas d'identifiants GitHub). Claude committe en
   local sur une branche ; **`git push` et les merges dans `main` = gestes de Mike**.
2. **Le serveur tient `server.py` ouvert** (verrou Windows tant que le `.bat 0` tourne).
   Toute commande qui réécrit `server.py` dans le répertoire de travail échoue — dont un
   `git checkout main` + `git merge` classique. → **on ne checkoute pas `main` en local
   pendant que le serveur tourne.**

## Modèle de branches
- `main` = vérité intégrée et publiée (`main == origin/main`).
- `feat/…` ou `fix/…` = un chantier ; commits au fil de l'eau, poussé, fusionné dans
  `main` une fois validé en réel. Le serveur tourne la branche de travail (normal).

## Fusion normale (fast-forward, sans verrou)
On avance `main` **côté GitHub**, sans checkouter `main` en local (répertoire de travail
non touché → verrou `server.py` sans effet, serveur peut rester allumé).

Le plus simple : **`28 - Fusionner la branche dans main.bat`** (double-clic). Ou à la main,
depuis la branche de travail :
```bat
git fetch origin
git push origin HEAD
git push origin HEAD:main
git fetch origin main:main
```
> `git push origin HEAD:main` échoue **exprès** si `main` a divergé (pas de `--force`, jamais).

## Cas divergent (`main` a avancé / conflits)
Un vrai merge commit réécrit `server.py` → **serveur arrêté d'abord** :
```bat
git checkout main
git pull origin main
git merge nom-de-ta-branche
REM resoudre les conflits, puis :
git push origin main
git checkout nom-de-ta-branche
```
Puis relancer le serveur.

## Gestes courants
- **Commit de session** : `27 - Commit de session.bat` (add + commit + push la branche).
  `28` vient après, quand c'est validé en réel.
- **Nouveau chantier** : juste après un `28` réussi, `git checkout -b feat/…` depuis la
  branche courante (elle est au niveau de `main`). Sinon : `git fetch origin &&
  git checkout main && git pull && git checkout -b feat/…` (serveur arrêté pour ce checkout).
- **État** : `git branch -vv` ; `git log --oneline main..HEAD` ; `git status -sb`.

## Propositions par défaut (`SESSION_COMMIT.txt`)
En fin de session, Claude écrit `SESSION_COMMIT.txt` à la racine (ASCII, sans guillemets
ni `!`) :
```
branche=feat/mon-chantier
titre=Mon titre de commit
```
Le `.bat 27` le lit et propose : bascule sur `branche` (créée si besoin, O/N) et `titre`
comme message par défaut (**Entrée = accepter**). Le fichier est supprimé une fois le
commit fait (proposition consommée). Local, gitignoré ; s'il est absent, le bat pose les
questions manuellement comme avant.

## Verrou `.git/index.lock`
Symptôme : `Unable to create '.../.git/index.lock'`. Cause habituelle : un client git
graphique ouvert sur le dépôt, ou un git planté. Les bats 27/28 le détectent et proposent
de le supprimer (fermer le client d'abord). À la main : `del "…\.git\index.lock"`. S'il
réapparaît, un client git tourne encore : ferme-le.

## Rôle de Claude vis-à-vis de git
Claude **n'exécute aucune commande ni outil git** (ni plugin/MCP, ni `device_bash` — cf.
`CLAUDE.md`) : il prépare tout et donne les commandes ; les bats 27/28 font commit et
fusion. Pour connaître l'état du dépôt (dernier commit, branche), Claude lit
`.git/logs/HEAD` en lecture seule (staging).
