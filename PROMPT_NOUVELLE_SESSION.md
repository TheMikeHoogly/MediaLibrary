# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (19/08/2026, fin de session 23)

**10b et 14a CLOS, tous deux observés en réel.** Le `mtime` ne classe plus rien :
le filtre le refusait depuis le 15/08, le tri le gardait dans les trois vues.
**259** photos sans date sûre (dont **257** datées de 2026 par leur propre
tagging) montaient en tête de **56 des 364 noms** et de **31 dossiers sur 665** ;
**32** n'avaient pas même un `mtime`, et l'ancien tri **ne s'exécutait pas** sur
l'index entier (TypeError → 500). Après correction, en réel : `sans_date_tri` =
**53 · 43 · 29 · 29 · 21** (Véronique, Nikola, Mike, Marie, Sandra), au chiffre
près la mesure hors ligne ; sur `dir=1/Nikola`, **20 des 20 premières** étaient
muettes en décroissant, **0 sur 11** désormais. Détail : `ROADMAP.md` et git.

Branche `feat/tri-recherche-une-seule-regle-de-date` **fusionnée** : `main` et
`HEAD` sur `f02d263`, arbre propre. Le bat **30** n'a pas tourné.

## Prochain pas

1. **`faits` : la matière manque AVANT le filtre — compté le 19/08, non traité.**
   Le ROADMAP disait « les `faits` ne filtrent pas ». Le vrai obstacle est en
   amont : `faits` ne couvre que **81** entrées sur **43 064** (**0,19 %**),
   exactement les 81 estampillées `v2ctx|kb1` — les 42 983 autres n'ont aucun
   `pipe` (deux chemins, un nombre). Y brancher un filtre rendrait presque rien
   **en ayant l'air de marcher** : la forme d'erreur nommée le 15/08. Or le
   matériau est DÉJÀ en base pour **37 999** photos (18 863 `personne:`,
   32 838 dates, 6 614 GPS, 935 animaux). Donc **backfill DÉTERMINISTE d'abord**
   — pur, sans GPU ni VLM, sans relire le NAS — chaque fait portant sa VRAIE
   source (« index »), jamais celle d'un tagging qui n'a pas eu lieu : sinon la
   provenance ment et toute la valeur du champ tombe. `espece` dépend des
   détections, à traiter à part. Le filtre vient APRÈS, mesuré sur la couverture.
2. **Deux boutons qui mentent** (petit, `photo-ui`) : « Date ↑ » reste allumé sur
   `/files?q=` alors que l'ordre affiché est celui du serveur ; et en mode IA les
   boutons de tri ne font rien — un clic est avalé. Ancres : `sortBy`,
   `updateSortButtons`, `applyFilter`, bloc `if (SEARCHQ)` de `GALLERY_PAGE`.
3. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Pas de retour à V0 sans protocole.**
4. **Trois constats du registre 10a**, non traités : ajout étiqueté `tagging` au
   lieu de `scan:*` ; `dict.__ior__` non redéfini dans `TrackedDict` ;
   `cycles_vus` = longueur d'un anneau de 10, pas un compteur.
5. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : corriger `taken` en base (72 photos) reste
NON DÉCIDÉ — c'est le geste qui risque d'emporter les **1 369** dates
antérieures. Les deux planchers 1990 coûtent 7 photos et 0, et ils sont couplés.
Le plafond 2100 d'une date lue dans un NOM coûte 0 aujourd'hui.

**À vider à la main** : `_corbeille_vecteurs/` (5,1 Mo, purge du 17/08 — la
recherche a vécu deux jours, 0 muet observé) et `_corbeille_session/plan_avant/`.

**Ordre des gestes git : 27 → 0 → 28.** Puis **30** quand des branches
fusionnées traînent.
