# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (19/08/2026, fin de session 22)

**10b — les deux gestes purs sont écrits, TESTÉS, et pas encore observés.**
Ils n'ont demandé aucune ligne de `server.py` : le serveur passe déjà TOUTES les
entrées à `plan_renommage.construire_plan`, qui filtre lui-même.

1. `renommage_facts.resolve_datestamp` — le garde-fou anti-scan couvre
   maintenant les **deux** sources de date précise, `taken` **et** le nom de
   fichier. Le numériseur écrit le même instant dans les deux ; l'étape 2
   réinscrivait donc la date que l'étape 1 venait d'écarter. Portée mesurée sur
   la base du 19/08 : **73** noms refusés = **1** vraie date de scan
   (`Photos Papa\1983\20150810_073417.jpg`) + **72** faux futurs, et **0 nom
   brut** parmi eux. **Le geste ferme une porte ; il ne déplace aucun fichier
   aujourd'hui, et c'est le résultat, pas un échec.**
2. `plan_renommage.est_nom_annee_seule` — le plan revient sur les `YYYY0000_`
   qu'il a lui-même écrits, **et seulement si la date est devenue précise**
   (sinon le compteur de collision se rebrasse pour rien). Plan simulé sur une
   COPIE de la base : **15** moves, exactement les 15 comptés par l'AUTRE chemin
   (`mesure_dates_scan.py`, qui ne lit que le nom et `taken`) — 15 cibles
   distinctes, 0 déjà prise, 0 date de scan réinscrite. **376** `YYYY0000` restent
   en attente d'une date, comptés dans `stats['perimes_en_attente']`.

28/28 tests verts (`test_plan_renommage.py`), et `test_renommage`,
`test_mesure_dates_scan`, `test_appliquer_plan` verts aussi.

## Prochain pas

1. **OBSERVER EN RÉEL 10b — c'est ce qui manque, et rien d'autre ne compte
   avant.** Geste Mike : redémarrer (`0`), `/reglages` → « Generer le plan »,
   relire `docs/plan_renommage.md` (**15 attendus**, tous des `YYYY0000_`),
   appliquer, puis vérifier qu'un des 15 porte bien sa date précise et que les
   noms humains sont intacts. Une correction n'est acquise qu'observée.
2. **Trouvé en chemin, chiffré, NON traité** : `_fname_time` /
   `fname_datetime` acceptent une année jusqu'à 2100, donc `22082010141.jpg`
   (DDMMYYYY + séquence) se lit « 2082-01-01 ». **72** en base, **coût 0** — mais
   seulement parce que les 72 portent un `taken` et que `_best_time` prend
   `min()`. Une seule sans `taken` serait datée du futur. Résiduels du ROADMAP.
3. **Trois constats du registre 10a**, non traités : ajout étiqueté `tagging` au
   lieu de `scan:*` ; `dict.__ior__` non redéfini dans `TrackedDict` ;
   `cycles_vus` = longueur d'un anneau de 10, pas un compteur.
4. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Ne pas revenir à V0 sans protocole.**
5. **14a, suites** : les `faits` ne filtrent pas encore ; pas de filtre par
   espèce ni par fiche ; le tri sans mot-clé passe encore par `_best_time`.
6. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : corriger `taken` en base (72 photos) reste
NON DÉCIDÉ — c'est le geste qui risque d'emporter les **1 369** dates
antérieures. Les deux planchers 1990 restants coûtent 7 photos et 0, et ils sont
couplés.

**À vider à la main** quand la recherche aura vécu quelques jours :
`_corbeille_vecteurs/` et `_corbeille_session/plan_avant/`.

**Ordre des gestes git : 27 → 0 → 28.**
