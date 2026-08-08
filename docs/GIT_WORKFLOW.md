# Workflow git / GitHub — MediaLibrary

Ce fichier explique **comment le code circule** entre le sandbox de Claude, la
machine de Mike, et GitHub (`TheMikeHoogly/MediaLibrary`, privé). Il existe pour
qu'on n'ait plus à se redemander « pourquoi la branche n'est pas mergée ».

## Les deux contraintes qui commandent tout

1. **Le sandbox de Claude ne peut pas pousser.** Il n'a pas les identifiants
   GitHub (`could not read Username for github.com`). Claude peut committer en
   local sur une branche, mais **`git push` et les merges dans `main` sont des
   gestes de Mike** (ou passent par GitHub).

2. **Le serveur tient `server.py` ouvert.** Sur Windows, tant que
   `0 - Démarrer le serveur.bat` tourne, le fichier est verrouillé. Toute
   commande qui **réécrit `server.py` dans le répertoire de travail** échoue —
   c'est le cas d'un `git checkout main` puis `git merge` classique, parce que
   `main` ne contient pas encore les modifs et le checkout doit réécrire le
   fichier.

La conséquence pratique : **on ne fusionne pas en checkoutant `main` en local
pendant que le serveur tourne.** On fusionne autrement (voir plus bas).

## Le modèle de branches

- **`main`** = la vérité intégrée et publiée. `main` == `origin/main`.
- **`feat/...` ou `fix/...`** = un chantier. On y committe au fil de l'eau, on
  pousse sur `origin`, on fusionne dans `main` quand c'est validé en réel.
- Le serveur de Mike tourne **sur la branche de travail courante** (pas sur
  `main`) : c'est normal, il exécute le code en cours de validation.

## Le cas normal : fusionner une branche finie (fast-forward)

Quand une branche descend proprement de `main` (elle contient tout `main` +
ses propres commits), la fusion est un **fast-forward** : zéro conflit, on
avance juste le pointeur `main`. C'est le cas le plus courant ici.

**La méthode sans verrou** : on avance `main` **côté GitHub**, sans jamais
checkouter `main` en local. Le répertoire de travail n'est pas touché, donc le
verrou `server.py` n'a aucune importance. Le serveur peut rester allumé.

### Le plus simple : `28 - Fusionner la branche dans main.bat`

Double-clic. Le script (sur la machine de Mike) :

1. vérifie qu'il ne reste rien à committer ;
2. `git fetch origin` ;
3. contrôle que c'est bien un fast-forward (sinon il s'arrête et explique) ;
4. `git push origin HEAD` (publie la branche) ;
5. `git push origin HEAD:main` (avance `main` sur GitHub) ;
6. `git fetch origin main:main` (met à jour la ref locale `main`, sans checkout).

### Ou à la main (mêmes commandes)

Depuis `C:\Prog\Claude\MediaLibrary`, **sur ta branche de travail** :

```bat
git fetch origin
git push origin HEAD
git push origin HEAD:main
git fetch origin main:main
```

> `git push origin HEAD:main` échoue **exprès** si `main` a avancé de son côté
> (non fast-forward). C'est une sécurité : pas de `--force`, jamais. Si ça
> échoue, voir le cas divergent ci-dessous.

## Le cas divergent : `main` a avancé, ou il y a des conflits

Là, un vrai merge commit est nécessaire, et il **réécrit `server.py`** — donc
**serveur arrêté d'abord** (ferme la fenêtre de `0 - Démarrer le serveur.bat`) :

```bat
git checkout main
git pull origin main
git merge nom-de-ta-branche
REM  ... resoudre les conflits eventuels, puis :
git push origin main
git checkout nom-de-ta-branche
```

Puis relancer le serveur.

## Commencer un nouveau chantier

Depuis `main` à jour :

```bat
git fetch origin
git checkout main
git pull origin main
git checkout -b feat/mon-nouveau-chantier
```

Ou, plus simple, `27 - Commit de session.bat` propose de créer une branche au
moment du premier commit.

## Committer pendant une session : `27 - Commit de session.bat`

Ajoute tout, committe, pousse la branche. C'est le geste de fin de session.
`28` vient **après**, quand la branche est validée et prête pour `main`.

## Supprimer une branche fusionnée (optionnel, pour garder le dépôt propre)

Une fois une branche dans `main`, on peut la retirer :

```bat
git push origin --delete feat/ma-branche
git checkout main
git branch -d feat/ma-branche
```

Aujourd'hui plusieurs branches déjà fusionnées traînent (`feat/triage-galerie`,
`phase1/rekey-everywhere`, `rangement-phase0`) — elles peuvent être supprimées
sans risque, leur contenu est dans `main`.

## Option « tout automatisé » : GitKraken

Claude a accès à l'outil GitKraken (création/fusion de pull requests, push)
**si Mike s'y connecte une fois**. Tant que ce n'est pas fait, Claude ne peut ni
pousser ni fusionner lui-même — il prépare tout et te donne les commandes.

Pour l'activer : `gk auth login` dans un terminal, ou le lien de connexion
GitKraken. Après ça, Claude pourra ouvrir et fusionner les PR directement, et ce
fichier sera complété avec ce flux.

## Vérifier l'état à tout moment

```bat
git branch -vv
git log --oneline main..HEAD
git status -sb
```

- `git branch -vv` : chaque branche, son suivi distant, si elle est en avance.
- `git log --oneline main..HEAD` : ce que la branche courante a en plus de `main`.
- `git status -sb` : modifs non commitées.
