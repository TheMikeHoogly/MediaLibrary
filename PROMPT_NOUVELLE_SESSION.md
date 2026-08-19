# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (19/08/2026, fin de session 23)

**10b CLOS et OBSERVÉ** : 15 moves appliqués, 0 date de scan réinscrite, noms
humains intacts, plan régénéré à **0**.

**14a — le `mtime` ne classe plus rien.** Le FILTRE le refusait depuis le 15/08,
le TRI le gardait. Mesuré sur COPIE (`mesure_tri_recherche.py`, 43 064 entrées) :
**259** photos sans date sûre, **257** datées de 2026 par leur propre tagging,
en tête de **56 des 364 noms** et de **31 dossiers sur 665** (deux ENTIÈREMENT
muets ; `Photos\Nikola` 43 sur 54). **32** n'ont pas même un `mtime` :
`_best_time(…) or ''` mélangeait `float` et `str`, l'ancien tri **ne s'exécutait
pas** sur l'index entier (TypeError → 500), sans qu'aucun NOM ne le déclenche
(0/364 ; chemin par LIEU non mesuré — plancher, pas total).

1. **Recherche — OBSERVÉ.** `recherche.trier_chronologique` (pur) : date
   précise, sinon année du DOSSIER, jamais `mtime` ; sans-date en FIN et
   comptées. En réel : `sans_date_tri` = **53 · 43 · 29 · 29 · 21** (Véronique,
   Nikola, Mike, Marie, Sandra) — au chiffre près la mesure hors ligne.
2. **Bandeau + galerie — ÉCRITS, PAS OBSERVÉS.** `/files?q=` dit enfin ce
   qu'elle a compris et écarté (même producteur que `/api/search`) ; la galerie
   sort les photos sans date sûre du tri par date (fin de liste dans les deux
   sens) et les compte. 83 tests verts, dont `node --check` sur les 9 pages.

## Prochain pas

1. **OBSERVER le bandeau et la galerie — rien d'autre avant.** Geste Mike :
   redémarrer (`0`), puis
   (a) accueil → chercher « Véronique » : le compteur doit dire
   « 174 photo(s) — Véronique · 53 sans date connue, en fin de liste » ;
   (b) `http://192.168.0.13:8080/files?dir=1/Nikola` — 54 photos dont **43 sans
   date**, toutes datées de 2026 par leur tagging. **AVANT enregistré le 19/08
   sur le serveur vivant** : en ordre DÉCROISSANT (un reclic sur « Date »),
   **20 des 20 premières** étaient des muettes ; en croissant, 9 sur 20 — mais
   par arithmétique, le dossier n'ayant que **11** photos datées. APRÈS attendu :
   **les 11 datées d'abord dans les deux sens**, les 43 muettes derrière, et le
   compteur qui dit « 43 sans date connue, en fin de liste ».
2. **14a, suites** : les `faits` ne filtrent pas ; pas de filtre par espèce ni
   par fiche. Et le bouton « Date ↑ » reste allumé sur `/files?q=` alors que
   l'ordre affiché est celui du serveur — l'écran annonce un tri qu'il
   n'applique pas.
3. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Ne pas revenir à V0 sans protocole.**
4. **Trois constats du registre 10a**, non traités : ajout étiqueté `tagging` au
   lieu de `scan:*` ; `dict.__ior__` non redéfini dans `TrackedDict` ;
   `cycles_vus` = longueur d'un anneau de 10, pas un compteur.
5. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : corriger `taken` en base (72 photos)
reste NON DÉCIDÉ — c'est le geste qui risque d'emporter les **1 369** dates
antérieures. Les deux planchers 1990 restants coûtent 7 photos et 0, et ils sont
couplés. Le plafond 2100 d'une date lue dans un NOM coûte 0 aujourd'hui.

**À vider à la main** quand la recherche aura vécu quelques jours :
`_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Ordre des gestes git : 27 → 0 → 28.**
