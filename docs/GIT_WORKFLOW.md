# Workflow git / GitHub — MediaLibrary

Comment le code circule entre le sandbox de Claude, la machine de Mike et GitHub
(`TheMikeHoogly/MediaLibrary`, privé).

## Les deux contraintes qui commandent tout
1. **Le sandbox ne peut pas pousser** (pas d'identifiants GitHub). Claude prépare ;
   **commit, push et fusion = gestes de Mike**.
2. **Le serveur tient `server.py` ouvert** (verrou Windows tant que le `.bat 0`
   tourne). Toute commande qui réécrit `server.py` dans le répertoire de travail
   échoue — dont un `git checkout main` + `git merge` classique. → **on ne
   checkoute jamais `main` en local pendant que le serveur tourne.**

## Guichet unique : `27 - Git.bat`

Un seul bat, un menu. Il **affiche l'état du dépôt et le geste conseillé**, puis :

| Choix | Ce qu'il fait | Réécrit le répertoire de travail ? |
|---|---|---|
| 1 | Commit de session : branche + `add -A` + commit + push | non |
| 2 | Fusion dans `main` en **fast-forward côté remote** | non |
| 3 | Nettoyage des branches déjà fusionnées (local + GitHub) | non |
| 4 | Nouveau chantier : `git checkout -b` depuis la branche courante | non |
| 5 | État détaillé : `status -sb`, `log`, `main..HEAD`, `branch -vv` | non |
| 6 | Ouvrir GitHub (dépôt, branches, commits, comparaison) | non |

**Aucun choix ne fait de `checkout main`** : le serveur peut rester allumé.
Chaque geste demande confirmation ; le verrou `.git\*.lock` est détecté à
l'entrée et à chaque geste.

**Ordre d'une session : `1` (commit) → `0 - Démarrer le serveur.bat` →
observation en réel → `2` (fusion).** On ne fusionne qu'après avoir observé.

Les anciens bats `27` (commit), `28` (fusion) et `30` (branches) sont dans
`_bat_archive/` : leur code est repris tel quel dans le bat unique, les y remettre
suffit à revenir en arrière.

## Modèle de branches
- `main` = vérité intégrée et publiée (`main == origin/main`).
- `feat/…` ou `fix/…` = un chantier ; le serveur tourne la branche de travail.

Ce que fait le choix 2, à la main :
```bat
git fetch origin
git push origin HEAD
git push origin HEAD:main
git fetch origin main:main
```
> `git push origin HEAD:main` échoue **exprès** si `main` a divergé (pas de
> `--force`, jamais).

## Cas divergent (`main` a avancé / conflits)
Le choix 2 refuse et affiche la marche à suivre. Un vrai merge commit réécrit
`server.py` → **serveur arrêté d'abord** :
```bat
git checkout main
git pull origin main
git merge nom-de-ta-branche
REM resoudre les conflits, puis :
git push origin main
git checkout nom-de-ta-branche
```
Puis relancer le serveur.

## Propositions par défaut (`SESSION_COMMIT.txt`)
En fin de session, Claude écrit `SESSION_COMMIT.txt` à la racine (ASCII, sans
guillemets ni `!`) :
```
branche=feat/mon-chantier
titre=Mon titre de commit
```
Le choix 1 le lit et propose la bascule de branche (créée si besoin, O/N) et le
titre comme message par défaut (**Entrée = accepter**). Le fichier est supprimé
une fois le commit fait. Local, gitignoré ; absent, le bat pose les questions.

## Verrou `.git/index.lock`
Symptôme : `Unable to create '.../.git/index.lock'`. Cause habituelle : un client
git graphique ouvert sur le dépôt, ou un git planté. Le bat le détecte et propose
de le supprimer (fermer le client d'abord). À la main :
`del "…\.git\index.lock"`.

## Rôle de Claude vis-à-vis de git
Claude **n'exécute aucune commande ni outil git** (ni plugin/MCP, ni
`device_bash` — cf. `CLAUDE.md`) : il prépare tout, écrit `SESSION_COMMIT.txt` et
donne les choix du bat. Pour connaître l'état du dépôt (dernier commit, branche),
il lit `.git/logs/HEAD` en lecture seule (staging).
