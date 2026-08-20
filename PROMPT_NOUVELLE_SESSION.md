# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (20/08/2026, session 28)

**Chantier 14a-(iv) CLOS** : le filtre des noms de la recherche et la ligne de
faits partagent enfin l'autorité (`_autorite_des_noms`). 13 photos sortaient
d'une recherche par un nom retiré ; observé après redémarrage, Silvio
495 → 494, Danica 325 → 324.

**Tu as un TROISIÈME canal — utilise-le.** `_commande_banc.txt` → le nom d'un
banc et ses arguments, par exemple `mesure_espece_recherche.py --base copie.db
--exemples 14`. L'agent (fenêtre « MediaLibrary - Bancs ») le lance sous
Windows et écrit `_banc_sortie.txt`. Il ne lance QUE `mesure_ verifier_
diagnostic_ comptes_ inventaire_ test_ eval_`, sans shell ni chemin. C'est
ainsi qu'on mesure ce que la VM ne peut pas atteindre (elle n'a pas le LAN).

**L'espèce a réfuté deux fois** : SigLIP ne rend que la moitié des détections
de YOLO, mais `det_score` ne dit pas l'espèce (`cheval` 0,934 sur *chien*).
Ce qui tient : la **CONCORDANCE** YOLO ∧ tagueur — **3 065** photos, chat
**2 316**.

## Prochain pas

1. **Câbler le 5ᵉ axe `espece:`** (forme A, choix de Mike) : un jeton explicite
   dans la recherche, annoncé dans la ligne « ce que j'ai compris », plus des
   puces qui l'insèrent. Matière : la concordance, jamais `det_score` seul.
   Mesurer d'abord ce que le jeton rend, avec le nouveau canal.
2. **Gestes Mike** : nettoyer Flo (5 909 photos) ; re-rejeter Caline ;
   `copie.db` (290 Mo) traîne à la racine, désormais gitignoré.
3. **Le reste** (`ROADMAP.md`) : prompt de PROD qui hallucine ; doublons
   proches ; UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base ; backfill ÉCRIT de
`faits` ; index des noms en UNE passe ; filtre des noms sur les `kw` bruts ;
`det_score` comme critère d'espèce ; agent git dans le serveur ; planchers
1990 (7 et 0, couplés) ; plafond 2100 (0).

**Les TROIS canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer ;
`canal.py` les lit tous) : `_commande_serveur.txt` → `redemarrer`, puis
VÉRIFIER `GET /api/serveur` (`code_a_jour` vrai) ; `_commande_git.txt` →
`commit` (traite autonome) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json` ; `_commande_banc.txt` → un banc, puis
LIRE `_banc_sortie.txt`. Trois fenêtres doivent être ouvertes — Serveur, Git,
Bancs ; un agent est vivant si son `_agent_*_vu.txt` a moins de 30 s.

**Mesurer** : jamais sur `photos.db` (le serveur est l'écrivain unique) — copier
la base, puis `TZ=Europe/Zurich`. Les bancs IMPORTENT la prod, ils ne la
recopient pas. Et un banc qui n'a jamais tourné est une promesse : le canal des
bancs existe pour qu'aucun ne soit livré sans avoir tourné.
