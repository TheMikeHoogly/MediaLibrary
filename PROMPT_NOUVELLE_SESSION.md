# Amorce de reprise — MediaLibrary

> À coller dans une nouvelle conversation après connexion de
> `C:\Prog\Claude\MediaLibrary`. Règles, protocole, architecture, tests en réel :
> `CLAUDE.md` (chargé auto). Ici : **uniquement l'état et le prochain pas.**

Tu reprends **MediaLibrary**. Lis `ROADMAP.md`, puis `eval/DECISIONS.md` (ce qui
a été tranché) et `eval/METHODE.md` (comment on tranche). Débrief en 2–3 lignes,
puis on attaque.

## Où on en est (16/08/2026, fin de session 16)

**1. Le banc 3b a tranché : la re-passe de tagging est CLOSE.** 147 paires
notées à l'aveugle. V2CTX préféré 94/147 (63,9 %, p = 0,0009), au-dessus du
seuil pré-enregistré — **mais ses hallucinations ont doublé** (24 contre 13 ;
apparié 15 contre 4, p = 0,019), et **hors des 30 pièges la préférence tombe
sous le seuil** (69/117, p = 0,064). Le critère écrit d'avance est un ET.
**~50 h de GPU ne seront pas dépensées.** Le chantier 3 est clos.

**2. 14a livré et observé en réel.** La recherche a quatre dimensions : noms →
lieux → **période** → sens. « années 80 » rend 752 photos, le lieu géocodé fait
passer Lausanne de 120 à 1 031, et `sans_date` (3 824 / 260) est compté ET
affiché.

**3. Trois pannes muettes fermées** : `sys.argv[1]` pris pour `UPLOAD_DIR` ;
l'import de `server` qui mourait sur une sortie redirigée ; et le banc qui
tournait 25 min sur 57 % d'un échantillon dont les fichiers avaient été
déplacés — `eval_tagging.py` refuse maintenant au-delà de 15 % de clés mortes,
`recler_echantillon.py` suit les renommages sans régénérer.

## Prochain pas — par valeur

1. **Purger les 2 374 vecteurs orphelins.** `/api/search` remonte des photos
   absentes de l'index : résultats muets, 2,6 % des résultats, dont 2 143 du
   dossier ARZOPA supprimé le 08/08. Diagnostic prêt et sans risque :
   `python verifier_orphelins.py` (base contre base, zéro accès disque). Aucun
   n'a de jumeau dans `tags` — la purge ne perd rien d'indexé. Le geste
   d'écriture reste à écrire (`forget_everywhere` existe). **Réversible ou rien.**
2. **Les lots de renommage sont débloqués sans réserve** — plus rien n'attend le
   banc. **Régénérer `docs/plan_renommage.json` d'abord** : il est antérieur au
   plancher 1900 ET aux lieux GPS.
3. **Le prompt de PRODUCTION hallucine plus que V0** (`eval/DECISIONS.md`) : le
   banc a mesuré autre chose que ce qu'il visait. Chaque photo taguée à partir
   de maintenant le paie. **Ne pas revenir à V0 sans protocole** — ce serait
   refaire à l'envers l'erreur qu'on vient d'éviter.
4. **14a, suites** : les `faits` ne filtrent pas encore ; pas de filtre par
   espèce ni par fiche ; le tri d'un résultat sans mot-clé passe encore par
   `_best_time` (donc `mtime`) là où la sélection l'exclut.
5. **Le reste** (`ROADMAP.md`) : gestes Mike (Flo, Caline) ; doublons proches ;
   UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : les deux planchers 1990 restants coûtent
7 photos et 0, et ils sont couplés. La strate « piège » du banc (83 %) est une
hypothèse post-hoc sur 30 photos, pas une décision.

**Ordre des gestes git : 27 → 0 → 28.**
