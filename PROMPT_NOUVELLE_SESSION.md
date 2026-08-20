# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md`. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (20/08/2026, fin de session 28)

**Chantier 14a CLOS : ce qu'on cherche est ce qu'on voit.** Le filtre des noms
de la recherche lisait les `kw` bruts de l'index pendant que la ligne de faits
lisait les fiches. **13 photos** sortaient d'une recherche par un nom
qu'`exclude` avait retiré ; **0** dans l'autre sens (363 tags nommés balayés
sur copie). `_autorite_des_noms()` est l'unique implémentation, partagée par
`_faits_ctx` (affichage) et `_cles_portant` (filtre). **Observé** après
redémarrage (`code_a_jour` vrai) : Silvio **495 → 494**, Danica **325 → 324**,
clés exclues absentes. La fiche fait foi sur l'orthographe : « Luna · luna »
(2 photos) et « luna » seul (1) ont disparu.

**Portée du filtre, dite et non supposée : 92,74 %** — nom ou lieu atteint
**27 936** des **30 122** photos à fait NON-date. Les **2 186** autres n'ont
qu'une ESPÈCE : hors de portée du déterministe.

**Le travail est commité EN LOCAL sur `feat/filtre-des-noms-sur-l-autorite`,
`main` est INTACTE** (traite autonome). **Attention** : `commit` ne POUSSE pas —
vérifié dans `.git`, contre ce qu'annonçait `CLAUDE.md`. Rien n'est encore sur
GitHub. Pour fusionner : `27 - Git.bat` → **2**, ou `livrer` dans
`_commande_git.txt` (qui pousse, puis fait le fast-forward).

## Prochain pas

1. **`QUESTIONS_MIKE.md`, deux choix qui t'attendent** : (a) l'ESPÈCE comme
   5ᵉ axe du filtre — les 2 186 photos hors de portée ; ma recommandation :
   **pas en ET** (YOLO rate des chats, le filtre rétrécirait en silence) ;
   (b) `commit` ne pousse pas — une traite autonome n'a aucune copie hors de
   ta machine. Rien n'est câblé en attendant.
2. **Gestes Mike** : nettoyer Flo (5 909 photos) ; re-rejeter Caline.
3. **Le reste** (`ROADMAP.md`) : prompt de PROD qui hallucine ; doublons
   proches ; UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base ; backfill ÉCRIT de
`faits` ; index des noms en UNE passe ; filtre des noms sur les `kw` bruts ;
agent git dans le serveur ; planchers 1990 (7 et 0, couplés) ; plafond 2100 (0).

**Pas encore observé** : la branche KB de `faits_vue` (`pending` = 0) — le
premier tagging sera son observation.

**À vider à la main** : `_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Les deux canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer) :
`_commande_serveur.txt` → `redemarrer`, puis VÉRIFIER `GET /api/serveur`
(`demarre_a` bougé, `code_a_jour` vrai) ; `_commande_git.txt` → `commit`
(traite autonome, `main` intacte) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json`. Deux fenêtres requises
(« MediaLibrary - Serveur » et « - Git ») ; l'agent est vivant si
`_agent_git_vu.txt` a moins de 30 s, sinon `ping`, sinon rendre la main.

**Mesurer** : jamais sur `photos.db` (le serveur est l'écrivain unique) — copier
la base, puis `TZ=Europe/Zurich` (un epoch local mal lu invente des
divergences). Les bancs IMPORTENT la prod, ils ne la recopient pas.
