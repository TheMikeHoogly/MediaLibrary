# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (19/08/2026, fin de session 24)

**Git : guichet unique, NON observé.** `27 - Git.bat` remplace les bats 27, 28 et
30 (dans `_bat_archive/`) : état du dépôt + geste conseillé, commit de session,
fusion fast-forward sans checkout, purge des branches, ouverture GitHub. Aucun
choix ne fait de `checkout main` — le serveur peut rester allumé. **Mike ne l'a
pas encore lancé : premier lancement = l'observation.**

**Backfill des `faits` : mesuré, rien d'écrit.** `mesure_faits_backfill.py`
(lecture seule sur COPIE, 17 tests, `test_mesure_faits_backfill.py`) :
`faits` = **81** entrées sur 43 064 ; un backfill déterministe en porterait
**42 974 (99,79 %)** — **alarme, pas succès** : **12 752 (29,61 %)** n'auraient
que la DATE. Chiffre honnête : **30 222 (70,18 %)** avec un fait NON-date.
Matière : personne **18 863** · lieu **13 757** (6 595 GPS + 7 162 chemin) ·
espèce **4 750** · animal **935** · date **42 773** (3 995 par la seule année du
dossier). **90** resteraient muettes.

> La mesure a tourné sous **UTC** (VM Linux). Les COMPTES ne bougent pas ; seuls
> les libellés de date d'un 31 décembre au soir pourraient basculer d'année.
> La relancer sous Windows (Europe/Zurich) avant de citer un libellé.

## Prochain pas

1. **Trancher la forme avant d'écrire le backfill.** Deux constats l'imposent :
   (a) `faits` est un **instantané, pas une vue** — **12** des 81 pourvues
   divergent déjà de l'index (noms retirés depuis) ; un backfill écrit une fois
   se périmera pareil. (b) le **lieu** ne doit pas passer par
   `renommage_facts.resolve_path_place` (sous-chaîne : **577** lieux collés dans
   un mot, dont **442 « Ins »** depuis « Cousins&Cousines ») mais par la règle du
   KB, `server._lieu_pour_cle`, qui compare des segments entiers. `espece` vient
   des détections : à traiter à part. Source des noms = **`index`**, jamais
   `xmp` : le backfill ne rouvre aucun fichier.
2. **Le filtre APRÈS, mesuré sur la couverture réelle** — jamais sur les 99,79 %.
3. **Deux boutons qui mentent** (petit, `photo-ui`) : « Date ↑ » reste allumé sur
   `/files?q=` alors que l'ordre affiché est celui du serveur ; et en mode IA les
   boutons de tri ne font rien — un clic est avalé. Ancres : `sortBy`,
   `updateSortButtons`, `applyFilter`, bloc `if (SEARCHQ)` de `GALLERY_PAGE`.
4. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Pas de retour à V0 sans protocole.**
5. **Trois constats du registre 10a**, non traités : ajout étiqueté `tagging` au
   lieu de `scan:*` ; `dict.__ior__` non redéfini dans `TrackedDict` ;
   `cycles_vus` = longueur d'un anneau de 10, pas un compteur.
6. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : corriger `taken` en base (72 photos) reste
NON DÉCIDÉ — c'est le geste qui risque d'emporter les **1 369** dates
antérieures. Les deux planchers 1990 coûtent 7 photos et 0, et ils sont couplés.
Le plafond 2100 d'une date lue dans un NOM coûte 0 aujourd'hui.

**À vider à la main** : `_corbeille_vecteurs/` (5,1 Mo) et
`_corbeille_session/plan_avant/`.

**Gestes git : `27 - Git.bat`, choix 1 (commit) → `0 - Démarrer le serveur.bat`
→ observation en réel → choix 2 (fusion). Puis choix 3 si des branches
fusionnées traînent.**
