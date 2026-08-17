# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (17/08/2026, fin de session 18)

**1. Le plan de renommage est régénéré, comparé et vérifié à blanc.** 7 058 moves
contre 6 642 le 12/08. Sans date fiable : **435 → 18**. Noms portant un lieu :
**941 → 1 175** (gain GPS). Dry-run : **7 058 applicables, 0 sauté**. Les lots de
200 sont le geste suivant (bouton « 3 · Appliquer un lot », recliquer jusqu'à 0).

**2. La comparaison a payé, et c'est la leçon** : 12 des 1 148 noms changés
écrivaient une date de **SCAN** (2007) sur les photos de Papa rangées sous 1990,
1993 et 2003 — trois lots de numérisation, horodatages espacés de 12 à 20 s.
`tagging_meta.date_fiable` ne garde que `ModifyDate` ; le scanner qui remplit
`DateTimeOriginal` passe au travers, **sa propre docstring le disait**. Garde-fou
`renommage_facts.date_de_scan_presumee` (module PUR, 17/17 tests) : une date
précise postérieure de plus d'un an à toutes les années du dossier n'est pas crue.
**Asymétrique à dessein** — une date ANTÉRIEURE est l'EXIF qui corrige un dossier
d'import (`2026\Photos Floflo` → vraies dates 2014-2018, 20 cas, intacts).
Observé : **12 → 0**, les 12 noms redeviennent ceux du 12/08, 0 effet de bord.

**3. Et l'AVANT avait failli disparaître** : générer le plan réécrit
`docs/plan_renommage.json` en place. Copie archivée dans
`_corbeille_session/plan_avant/` — sans elle, aucune comparaison. (Au passage :
le « plan = 2 114 » de l'ancienne feuille de route était périmé de deux mois.)

**4. `maximum-scale=1` retiré du viewport** (il interdisait le pinch-zoom,
WCAG 1.4.4 — point 11d). Le « mode mobile sur PC » signalé par Mike n'était pas
le site : zoom Chrome à ~400 % sur l'hôte (`innerWidth` = 255 px CSS).

## Prochain pas — par valeur

1. **Cliquer les lots de renommage** jusqu'à 0 restant (200 par clic, journal
   undo par lot, « 4 · Annuler le dernier lot » si besoin). Après le premier lot,
   **observer en réel** : une photo renommée garde-t-elle ses noms humains
   (`rekey_everywhere`), la recherche la retrouve-t-elle ?
2. **Compter les dates de SCAN crues EN BASE** (ROADMAP 10). Le garde-fou protège
   le NOM, pas l'index : `/api/jour` place encore `1990_Achumani\IMG_1307.jpg` au
   1ᵉʳ mai 2007, donc le tri chronologique, « même jour » et le filtre par période
   se trompent. 12 cas connus, portée réelle inconnue. Mesurer sur une COPIE.
3. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) :
   inchangé, chaque photo taguée le paie. **Ne pas revenir à V0 sans protocole.**
4. **14a, suites** : les `faits` ne filtrent pas encore ; pas de filtre par espèce
   ni par fiche ; le tri d'un résultat sans mot-clé passe encore par `_best_time`
   (donc `mtime`) là où la sélection l'exclut.
5. **Deux images tronquées** (`Sanetsch/DSC00550.JPG`,
   `France & Belgique/DSC00795.JPG`) repassent en attente d'encodage à chaque
   démarrage — visibles dans `erreurs_images` de `/api/search/status`.
6. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : les deux planchers 1990 restants coûtent
7 photos et 0, et ils sont couplés. La strate « piège » du banc 3b (83 %) est
une hypothèse post-hoc sur 30 photos, pas une décision.

**À vider à la main** quand la recherche aura vécu quelques jours :
`_corbeille_vecteurs/` (2 374 lignes, toutes relues) et
`_corbeille_session/plan_avant/`.

**Ordre des gestes git : 27 → 0 → 28.**
