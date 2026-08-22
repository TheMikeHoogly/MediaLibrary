# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (23/08/2026, fin de session 39)

**La fusion Flo → Florine a été lancée, et elle a échoué en beauté — d'une
manière qu'aucun test ne pouvait voir.** `rename` mettait une heure à balayer
5 907 photos et ne supprimait la fiche absorbée qu'À LA FIN. Pendant cette
heure, la signature de Flo restait vivante et `AUTO_ADD` (curateur, passe
toutes les 240 s) remettait le nom sur les photos que la fusion venait de lui
retirer. Chiffres du fonds vivant : **5 907 → 4 487, puis REMONTÉE à 5 703** ;
**60 auto-ajouts « Flo » en une heure** ; **17 092 écritures XMP en attente**
pour un geste qui en demande 11 814, à **0,09 op/s** — 50 heures de NAS pour
graver une bagarre. La boucle est morte avant de fusionner les fiches : aucun
journal, donc **rien à annuler**.

**Corrigé, et la course n'est pas arbitrée : elle n'existe plus.** Les fiches
sont fusionnées AVANT la boucle — plus de fiche, plus de signature. Le journal
s'écrit dans un `finally` (interrompue = annulable, et **relancer reprend**),
et les photos qui portent déjà le nom d'arrivée voient quand même leur FICHIER
réécrit — c'est ce qui empêche un nom fantôme de renaître au balayage des
modifiés, et c'est probablement l'origine des « 153 Florine sans fiche ».
**`delete()` avait la même forme** : corrigé aussi. **44 tests** dans
`test_fusion_de_fiches.py`, dont **5 échouent sur l'ancien code**.

**`verifier_fusion.py` + 22 tests** : le geste le plus lourd du projet a enfin
un juge — règle 2 par l'arithmétique des ensembles du journal, quel journal
peut vraiment annuler, disparition de l'ancien nom, file restante.

**État du fonds à cette minute** : `Flo` = **5 725** photos, `Florine` ≥ 2 000
(les deux coexistent, séquelle de la passe ratée), fiche `Flo` intacte avec ses
143 confirmations, aucune fiche `Florine`, file d'écriture **à 0**, serveur à
jour (`code_a_jour` vrai).

## Prochain pas

1. **La fusion, par Mike** : `/people` → `Flo` → Renommer → `Florine`. Le
   bouton ouvre un `prompt()` du navigateur pré-rempli avec `Flo` : tant qu'on
   n'a pas remplacé le texte et validé, RIEN n'est envoyé — et rien ne le dit.
   Signes que le correctif tient, **immédiatement** : la fiche `Florine`
   apparaît dans la seconde, la fiche `Flo` disparaît, puis le compte descend
   **sans jamais remonter**. Ensuite `python verifier_fusion.py --serveur
   http://192.168.0.13:8080` (au banc) doit dire : règle 2 tenue, un seul
   journal, ancien nom disparu. La file XMP (~12 000 opérations) se vide en
   tâche de fond — compter en HEURES, et mesurer le débit réel : à 0,09 op/s
   ce serait 36 h, et si c'est le cas c'est un chantier en soi.
2. **Copie HORS SITE (12 bis)** — le seul manque qui reste à l'assurance-vie,
   et il demande une décision avant du code.
3. **Suite de `ui/`** : le CSS commun (chaque page porte encore son `<style>`)
   puis le redesign — deux chantiers SÉPARÉS, exprès (`photo-ui`).
4. **Reste d'audit** : O7–O9, O11–O15 ; **I1** est VISIBLE dans `/reglages`
   (`tours: visages 0, animaux 0`).
5. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Rien n'attend Mike dans `QUESTIONS_MIKE.md`.**
