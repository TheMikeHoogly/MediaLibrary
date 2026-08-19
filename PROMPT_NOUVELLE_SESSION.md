# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md`. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (19/08/2026, fin de session 27)

**Tu livres toi-même dans git, mais seulement si tu peux le prouver.**
`git_agent.py` tourne sous Windows (fenêtre « MediaLibrary - Git », ouverte par
`0 - Démarrer le serveur.bat`) et surveille `_commande_git.txt` : `rien`,
`commit`, `livrer`. `livrer` = contrôles + commit + push + fast-forward de main.

Il **refuse** si un `.py` que le serveur importe est plus récent que
`demarre_a`, si un `test_*.py` d'un module touché est rouge, si un `.bat` n'est
pas ASCII pur, si le lint des docs crie. Jamais contournables, même avec
`force=raison` : verrou `.git/*.lock`, branche `main` ou hors convention,
fichier binaire ou > 5 Mo, `checkout` vers une branche existante (il réécrirait
`server.py` sous le serveur). **L'ordre s'inverse : éditer → redémarrer →
OBSERVER → livrer.** 21 tests, dont six sur ce que `force=` n'ouvre pas.
**Observé** : son premier acte a été de se commiter lui-même (`a43f9d0`, 10
fichiers, push et fast-forward de main compris, cinq contrôles passés).

**Vérifie toujours dans `.git/logs/*`**, jamais dans `_etat_git.json` : celui-ci
dit ce que l'agent a TENTÉ, git dit ce qui s'est PASSÉ. Canal fermé ou refus
non levable → `27 - Git.bat` (**8** montre le dernier rapport).

**Avant** (14a-iii) : `date · lieu · noms` s'affichent sous chaque vignette et
dans la visionneuse, avec leurs sources. Index inversé des noms : **1,11 ms**
par page de 50 contre **9,65 ms** (×8,7). Observé : `q=Ins` → 11 photos,
11 dates · 11 lieux · 5 noms, page **1 048–1 462 ms** contre 1 539.

**Traite autonome** (« go », Mike absent) : livrer avec `commit`, pas `livrer`
— `main` reste intacte, la fusion attend son retour. Un choix qui lui
appartient va dans `QUESTIONS_MIKE.md` avec une recommandation, et on passe au
point suivant. Détail : `CLAUDE.md`.

## Prochain pas

1. **Le filtre (14a-iv)** : filtrer la recherche sur les faits, mesuré sur les
   **69,95 %** (photos avec un fait NON-date), jamais sur 99,79 %.
2. **Deux questions t'attendent** dans `QUESTIONS_MIKE.md` : les noms en
   double dans la visionneuse, et `eval/DECISIONS.md` à saturation.
3. **Gestes Mike** : nettoyer Flo (5 909 photos) ; re-rejeter Caline.
4. **Le reste** (`ROADMAP.md`) : prompt de PROD qui hallucine ; doublons
   proches ; UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base ; backfill ÉCRIT de
`faits` ; index des noms en UNE passe ; agent git dans le serveur ; planchers
1990 (7 et 0, couplés) ; plafond 2100 (0).

**Pas encore observé** : la branche KB de `faits_vue` (`pending` = 0) — le
premier tagging sera son observation.

**À vider à la main** : `_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Les deux canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer) :
`_commande_serveur.txt` → `redemarrer`, puis VÉRIFIER `GET /api/serveur`
(`demarre_a` bougé, `code_a_jour` vrai) ; `_commande_git.txt` → `livrer`, puis
VÉRIFIER `.git/logs/HEAD`.
