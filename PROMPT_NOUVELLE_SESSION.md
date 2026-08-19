# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ depuis — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md`. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (19/08/2026, fin de session 25)

**`faits` est une VUE — le backfill est REJETÉ.** `faits_vue.py` (pur, 26 tests)
calcule les faits à la demande ; `server` lui délègue la règle de lieu. Rien
n'est écrit en base, aucune migration. Pourquoi : sur les 81 entrées pourvues,
la vue en
**corrige 4** — 3 noms « Flo » retirés depuis, **1 photo qui a reçu 6 noms APRÈS
son tagging**. Couverture 99,79 %, mais le chiffre honnête est **69,14 %** avec un
fait NON-date. Coût : **1,4 ms** par page de 50 — seule prudence,
`_noms_attendus` balaie toutes les fiches à chaque appel : en balayage complet,
index inversé construit **une fois**.

**Observé après redémarrage** : `import faits_vue` tient, et `_chemin_relatif`
délégué (43 064 appels pour bâtir `/sujets`) laisse « Bremblens » à **2 398** et
non 30 682. **Pas encore observé** : la branche du KB (`pending` = 0) — le
premier tagging sera son observation.

**Ce qui commande la suite : le lieu a TROIS règles, pas deux.** (1) renommage —
sous-chaîne ; (2) Knowledge Builder — segments entiers (corrigée) ;
(3) **`places_list` / `_cles_du_lieu`, soit `/sujets` ET la recherche —
sous-chaîne, intacte, et la SEULE que Mike voie.** En réel : `/sujets` affiche
**« Ins » : 493 photos** (≥ 442 collées depuis « Cousins&Cousines »), et une
recherche « Ins » rend 80 résultats dont **32** en viennent. La correction a
atterri là où personne ne regarde.

## Prochain pas

1. **Unifier la règle de lieu sur ses trois appelants**, en commençant par ceux
   qui se VOIENT (`places_list`, `_cles_du_lieu`). Ils comptent AUTREMENT : tous
   les libellés qui matchent, pas le premier ; et `_cles_du_lieu` fait un ET sur
   plusieurs lieux, GPS en OU. Mesurer AVANT/APRÈS sur copie.
2. **Corriger la règle** : (a) **124 libellés MULTI-MOTS jamais essayés** —
   « Weekend Vallée d'Aoste » : essayer le libellé entier DANS le segment ;
   (b) **seuil de 5 lettres**, 47 photos — mesurer les faux qu'il rattrape AVANT
   de le baisser ; (c) **« France & Belgique »** (157) : deux lieux ou aucun,
   c'est une décision ; (d) 207 effacés au nettoyage, en dernier.
3. **Brancher la vue** (affichage date · lieu · noms, point 3 du ROADMAP).
   **Le filtre ensuite**, mesuré sur 69,14 %, jamais 99,79 %.
4. **Deux boutons qui mentent** (`photo-ui`) : « Date ↑ » reste allumé sur
   `/files?q=` alors que l'ordre vient du serveur ; en mode IA les boutons de tri
   avalent le clic. Ancres : `sortBy`, `updateSortButtons`, `applyFilter`, bloc
   `if (SEARCHQ)` de `GALLERY_PAGE`.
5. **Le reste** (`ROADMAP.md`) : prompt de PROD qui hallucine ; registre 10a ;
   gestes Mike (Flo, Caline) ; doublons proches ; UI (11) ; restauration à
   blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base NON DÉCIDÉ (72 photos
contre **1 369** antérieures) ; planchers 1990 : 7 et 0, couplés ; plafond 2100 : 0.

**À vider à la main** : `_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Tu peux redémarrer le serveur toi-même** (nouveau) : écrire `redemarrer` dans
`_commande_serveur.txt` via `device_bash`, puis VÉRIFIER `GET /api/serveur`
(`demarre_a` bougé, `code_a_jour` vrai). Détail : `CLAUDE.md`, « Tester en réel ».
Exige la fenêtre « MediaLibrary - Serveur » (superviseur) ; **la toute première
fois, Mike doit avoir relancé par `0 - Démarrer le serveur.bat`.**

**Git : `27 - Git.bat`, 1 (commit) → 2 (fusion).**
