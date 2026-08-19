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

**14a CLOS et OBSERVÉ — le `mtime` ne classe plus rien.** Le FILTRE le refusait
depuis le 15/08, le TRI le gardait, dans les trois vues. Mesuré sur COPIE
(`mesure_tri_recherche.py`, 43 064 entrées) : **259** photos sans date sûre,
**257** datées de 2026 par leur propre tagging, en tête de **56 des 364 noms**
et de **31 dossiers sur 665** (`Photos\Nikola` 43 sur 54). **32** n'ont pas même
un `mtime` : `_best_time(…) or ''` mélangeait `float` et `str`, et **l'ancien
tri ne s'exécutait pas** sur l'index entier (TypeError → 500) — sans qu'aucun
NOM ne le déclenche (0/364 ; chemin par LIEU non mesuré, plancher pas total).

Corrigé par `recherche.trier_chronologique` (pur) : date précise, sinon année du
DOSSIER, jamais `mtime` ; sans-date en FIN et **comptées**. `/files?q=`, qui se
taisait là où `/api/search` parlait, reçoit le même `detail`. **En réel** :
`sans_date_tri` = **53 · 43 · 29 · 29 · 21** (Véronique, Nikola, Mike, Marie,
Sandra), au chiffre près la mesure ; bandeau « 174 photo(s) — Véronique · 53
sans date connue, en fin de liste » ; sur `dir=1/Nikola`, **20 des 20 premières**
étaient muettes en décroissant, **0 sur 11** désormais. 83 tests verts, dont
`node --check` sur les 9 pages (`test_gallery_placeholders.py`, par AST).

## Prochain pas

1. **14a, suites** : les `faits` ne filtrent pas encore (le lieu passe par
   `gps_places` + chemin) ; pas de filtre par espèce ni par fiche. Wagon du
   point 3 : affichage date · lieu · noms depuis `faits`.
2. **Deux boutons qui mentent** (wagon `photo-ui`) : « Date ↑ » reste allumé sur
   `/files?q=` alors que l'ordre affiché est celui du serveur ; et en mode IA
   les boutons de tri ne font rien du tout — l'écran annonce un tri qu'il
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
