# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (17/08/2026, fin de session 19)

**1. Les dates de SCAN en base sont COMPTÉES : 72**, contre 12 connues — le plan
de renommage n'en voyait que les noms bruts. `mesure_dates_scan.py` (PUR,
32 tests, lecture seule sur une COPIE) applique au champ `taken` le critère que
le renommage applique au nom. Presque toutes dans « Photos Papa » ; écarts +2 à
+32 ans. **Confirmé sur le serveur vivant** : `/api/jour?jour=05-01` rend les
4 photos de `1990_Achumani` avec `precise: true`. Même corpus (43 064).

**2. Le DÉSACCORD des deux chemins a rapporté plus que leur accord.** A (dossier
contre `taken`) voyait 15 fichiers renommés, B (le repli `YYYY0000` laissé dans
le nom) en voyait 27, 12 communs. L'écart n'était pas du bruit :
**(a)** le repli sur le NOM n'est pas gardé — l'étape 2 lit la date du nom de
fichier sans contrôle, et un scanner qui NOMME ses fichiers y réinscrit la date
que l'étape 1 vient d'écarter (1 cas) ; **(b)** 15 noms sont PÉRIMÉS —
`YYYY0000` alors que la date précise est connue depuis, par une tâche de fond
arrivée après le renommage, et le plan ne regarde plus les fichiers renommés.
Les 27 se réconcilient : **12 vrais refus + 15 périmés**.

**3. L'asymétrie protégeait 1 369 dates, pas 20.** Autant de photos portent une
date ANTÉRIEURE à leur dossier (958 à un an) — vidages de téléphone, dossiers
d'import. Un garde-fou symétrique les aurait toutes détruites pour en sauver 72.

**4. Rien n'a été corrigé** : mesurer d'abord. Angle mort compté et assumé :
6 818 photos sans année dans leur dossier, 10 226 sans `taken`.

## Prochain pas — par valeur

1. **Instrumenter ce que le scan OUBLIE** (ROADMAP 10a) — le seul point encore
   sans instrument. `forget_everywhere` renvoie un nombre que personne
   n'enregistre ; l'étape 4 de `_sync_dir` ne dit pas combien de clés elle
   retire ; les −250 du 17/08 restent indiagnosticables. Exposer le compteur
   (résumé de scan + `/api/maint/status`) est la condition pour trancher à la
   prochaine occurrence.
2. **Décider quoi faire des 72** (ROADMAP 10b). Trois gestes indépendants, du
   moins cher au plus cher : garder l'étape 2 du repli (le NOM — 1 cas, module
   pur, sans redémarrage) ; rendre au plan de renommage les 15 noms périmés ;
   corriger `taken` en base (pipeline de dates, `monolith-surgery`, backfill —
   et surtout **ne pas emporter les 1 369 antérieures**).
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
