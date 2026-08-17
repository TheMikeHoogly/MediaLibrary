# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (17/08/2026, fin de session 17)

**1. Les 2 374 vecteurs orphelins sont purgés — et l'effet est observé.**
`purger_vecteurs_orphelins.py` (44 vérifications) met en quarantaine JSONL
(`_corbeille_vecteurs/`, vecteur en base64, `--restaurer` rétablit) puis
supprime. Après redémarrage : **0 résultat muet sur 1 600** contre 2,6 % avant,
et 0 orphelin base contre base — deux chemins, même chiffre. Le fichier de
quarantaine (2 374 lignes, toutes relues) reste à vider **à la main** quand la
recherche aura vécu quelques jours.

**2. Ce que la purge a appris, et qui vaut plus que la purge** : « le fichier
existe » ne veut pas dire « il sera repris ». 91 photos bien présentes vivaient
dans `.corbeille-rangement` — hors de toute racine scannée, donc muettes à vie.
La règle de SÉLECTION du scan est répliquée dans `sera_re_tague()` ; tester
`is_file()` ne suffisait pas.

**3. Le banc 3b a clos la re-passe de tagging** (16/08) : préférence 63,9 % mais
hallucinations doublées, et 59 % hors des 30 pièges. ~50 h de GPU non dépensées.

## Prochain pas — par valeur

1. **Régénérer `docs/plan_renommage.json`, puis lancer un lot.** Les lots sont
   débloqués sans réserve — plus rien n'attend le banc. Le plan actuel est
   antérieur au plancher 1900 ET aux lieux GPS : le régénérer d'abord, comparer
   au précédent (2 114 entrées), et **ne rien appliquer sans dry-run lu**.
2. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) : le
   banc a mesuré autre chose que ce qu'il visait. Chaque photo taguée à partir
   de maintenant le paie. **Ne pas revenir à V0 sans protocole** — ce serait
   refaire à l'envers l'erreur qu'on vient d'éviter.
3. **14a, suites** : les `faits` ne filtrent pas encore ; pas de filtre par
   espèce ni par fiche ; le tri d'un résultat sans mot-clé passe encore par
   `_best_time` (donc `mtime`) là où la sélection l'exclut.
4. **Deux images tronquées** (`Sanetsch/DSC00550.JPG`,
   `France & Belgique/DSC00795.JPG`) repassent en attente d'encodage à chaque
   démarrage — visibles dans `erreurs_images` de `/api/search/status`. Petit,
   mais c'est du bruit permanent dans un compteur qu'on lit.
5. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : les deux planchers 1990 restants coûtent
7 photos et 0, et ils sont couplés. La strate « piège » du banc 3b (83 %) est
une hypothèse post-hoc sur 30 photos, pas une décision.

**Ordre des gestes git : 27 → 0 → 28.**
