# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (19/08/2026, fin de session 23)

**10b CLOS et OBSERVÉ.** Les 15 moves attendus sont appliqués : 15 cibles
distinctes, tous des `YYYY0000_` devenus précis, 0 date de scan réinscrite,
noms humains intacts, plan régénéré à **0**.

**14a — une seule règle de date par réponse, ÉCRIT ET MESURÉ, PAS OBSERVÉ.**
La recherche filtrait par `annee_fiable` (jamais `mtime`) puis TRIAIT par
`_best_time`, dont la branche 3 EST le `mtime`. Mesuré sur COPIE
(`mesure_tri_recherche.py`, 43 064 entrées) : **259** photos sans date sûre,
**257** datées de 2026 par leur propre tagging, **en tête** de **56 des 364
noms** de l'index — 53 des 100 premières pour « Véronique », 29 pour « Mike ».
Et **32** entrées sans même un `mtime` : `_best_time(…) or ''` mélangeait
`float` et `str`, l'ancien tri **ne s'exécute pas** sur l'index entier
(TypeError → 500). Aucun NOM ne déclenche ce mélange aujourd'hui (0/364) et le
chemin par LIEU n'est pas mesuré : **plancher, pas total.**
Corrigé par `recherche.trier_chronologique` (pure) : date précise, sinon année
du DOSSIER, jamais `mtime` ; les sans-date en FIN de liste et **comptées**
(`sans_date_tri`, rendu par `/api/search`). 72 tests verts.

## Prochain pas

1. **OBSERVER EN RÉEL 14a — rien d'autre ne compte avant.** Geste Mike :
   redémarrer (`0`), chercher **« Véronique »** puis **« Mike »** (un nom, rien
   d'autre) et regarder le HAUT de la page : les photos sans date doivent être
   parties de la tête. Contrôle chiffré sans onglet actif :
   `GET /api/search?q=Véronique&n=100` → `sans_date_tri` non nul, et les
   dernières clés du tableau sont les muettes. Avant : 53 des 100 premières.
2. **`sans_date_tri` est compté mais pas AFFICHÉ.** `sans_date` l'est déjà
   (`iaEcartees`) ; wagon `photo-ui`, à décider une fois 1 observé.
3. **14a, suites** : les `faits` ne filtrent pas ; pas de filtre par espèce ni
   par fiche.
4. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Ne pas revenir à V0 sans protocole.**
5. **Trois constats du registre 10a**, non traités : ajout étiqueté `tagging` au
   lieu de `scan:*` ; `dict.__ior__` non redéfini dans `TrackedDict` ;
   `cycles_vus` = longueur d'un anneau de 10, pas un compteur.
6. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : corriger `taken` en base (72 photos)
reste NON DÉCIDÉ — c'est le geste qui risque d'emporter les **1 369** dates
antérieures. Les deux planchers 1990 restants coûtent 7 photos et 0, et ils sont
couplés. Le plafond 2100 d'une date lue dans un NOM coûte 0 aujourd'hui.

**À vider à la main** quand la recherche aura vécu quelques jours :
`_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Ordre des gestes git : 27 → 0 → 28.**
