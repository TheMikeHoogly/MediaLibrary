# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (18/08/2026, fin de session 20)

**Le scan rend enfin des comptes — chantier 10a, LIVRÉ mais PAS OBSERVÉ.**
`comptes_index.py` (module PUR, 37 tests) branche un registre sur le **goulot**
de l'index en mémoire : `TrackedDict` (`store_sqlite.py`), par où passe toute
clé qui entre ou sort. Trois choses deviennent visibles :

1. **Qui retire, et combien** — chaque appelant déclare son motif :
   `scan:disparus`, `scan:modifies`, `purge:cles_fantomes`,
   `demarrage:dossiers_caches`, `rekey`, `tagging`.
2. **Ce qui retire SANS le dire** — bucket « (non declare) », avec des exemples
   de clés. C'est le bucket intéressant, pas les autres.
3. **L'écart inexpliqué de chaque cycle de scan** :
   `inexpliqué = (fin − début) − (ajouts − retraits)`. Non nul = la taille de
   l'index a changé **hors du goulot**. C'est le chiffre qui manquait aux −250
   du 17/08 ; zéro partout ferme le sujet.

Lecture : `/reglages` → panneau « Comptes de l'index » (badge *reconcilie* /
*ecart ±n* / *en attente*), et `GET /api/maint/status` → clé `oublis`.
L'étape 4 de `_sync_dir` dit maintenant `n/demandées` au lieu de se taire
quand `n = 0`. Au passage : `.panel .mut` passe de 2,2:1 à 5,9:1 (plancher a11y).

**Rien n'est acquis tant que ce n'est pas observé en réel.** Un instrument non
lu vaut zéro.

## Prochain pas — par valeur

1. **Observer 10a chez Mike.** Ouvrir `/reglages` après quelques cycles de scan
   (5 min chacun). Trois lectures possibles : tout à zéro → l'index est sain et
   le sujet se ferme ; « (non declare) » non nul → une porte oubliée, les
   exemples de clés disent laquelle ; écart inexpliqué non nul → l'index bouge
   hors du goulot, et le nombre dit de combien. **Ne rien décider avant.**
2. **Décider quoi faire des 72** (ROADMAP 10b). Trois gestes indépendants, du
   moins cher au plus cher : garder l'étape 2 du repli (le NOM — 1 cas, module
   pur, sans redémarrage) ; rendre au plan de renommage les 15 noms périmés ;
   corriger `taken` en base (pipeline de dates, `monolith-surgery`, backfill —
   et surtout **ne pas emporter les 1 369 dates antérieures**).
3. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Ne pas revenir à V0 sans protocole.**
4. **14a, suites** : les `faits` ne filtrent pas encore ; pas de filtre par
   espèce ni par fiche ; le tri d'un résultat sans mot-clé passe encore par
   `_best_time` (donc `mtime`) là où la sélection l'exclut.
5. **Le reste** (`ROADMAP.md`) : deux images tronquées en attente d'encodage à
   chaque démarrage ; gestes Mike (Flo, Caline) ; doublons proches ; UI (11) ;
   restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : les deux planchers 1990 restants coûtent
7 photos et 0, et ils sont couplés. La strate « piège » du banc 3b (83 %) est
une hypothèse post-hoc sur 30 photos, pas une décision.

**À vider à la main** quand la recherche aura vécu quelques jours :
`_corbeille_vecteurs/` (2 374 lignes, toutes relues) et
`_corbeille_session/plan_avant/`.

**Ordre des gestes git : 27 → 0 → 28.**
