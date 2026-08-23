# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

> ⚠ **NE REDÉMARRE PAS LE SERVEUR tant que `/api/maint/status` →
> `queues.personnes` n'est pas à 0.** La fusion Flo → Florine y a laissé
> ~11 700 écritures XMP (~3,4 h) ; un redémarrage les jette, et des milliers de
> photos garderaient `personne:Flo` dans leurs métadonnées alors que l'index
> dit `Florine` — c'est ainsi que naît un nom fantôme. La file est vide ? Alors
> le protocole normal reprend.

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

**Et ce n'est pas la bagarre qui l'a tuée : un VERROU dans la fiche.**
`TypeError: cannot pickle '_thread.RLock' object`, dans le `copy.deepcopy` de
la fiche — une ligne qui venait APRÈS la boucle. Les 5 907 photos étaient
renommées, puis la fusion mourait sans fiche, sans journal et sans un mot à
l'écran. Le nouvel ordre a déplacé ce mur de la 60ᵉ minute à la 1ʳᵉ
milliseconde. Le journal prend maintenant une copie JSON-SÛRE et **nomme** ce
qu'il écarte. **Qui met un verrou dans une fiche de personne ? Pas encore
su** — la ligne de console le dira au prochain renommage, et c'est à suivre.

**Corrigé, et la course n'est pas arbitrée : elle n'existe plus.** Les fiches
sont fusionnées AVANT la boucle — plus de fiche, plus de signature. Le journal
s'écrit dans un `finally` (interrompue = annulable, et **relancer reprend**),
et les photos qui portent déjà le nom d'arrivée voient quand même leur FICHIER
réécrit — c'est ce qui empêche un nom fantôme de renaître au balayage des
modifiés, et c'est probablement l'origine des « 153 Florine sans fiche ».
**`delete()` avait la même forme** : corrigé aussi. **45 tests** dans
`test_fusion_de_fiches.py`, dont **5 échouent sur l'ancien code**.

**`verifier_fusion.py` + 22 tests** : le geste le plus lourd du projet a enfin
un juge — règle 2 par l'arithmétique des ensembles du journal, quel journal
peut vraiment annuler, disparition de l'ancien nom, file restante.

**LA FUSION EST FAITE ET VÉRIFIÉE (23/08, 08:31).** Un seul nom, `Florine`,
**5 909 photos**, plus aucun `Flo`. `verifier_fusion.py` au banc : règle 2
tenue — **143 → 143 confirmations**, 1 215 → 1 215 exclusions, 84 → 84 visages,
avatar présent, date la plus ancienne ; un seul journal
(`fusion_20260823_083124.jsonl`), annulable. La boucle a mis **2 minutes** là
où elle en mettait 60 hier : la lenteur était la bagarre, pas le `stat` NAS.
Reste la file XMP, **~11 700 opérations à 0,95 op/s, ~3,4 h** — le fonds
lui-même n'est à jour qu'une fois vidée.

**À savoir avant d'annuler** : 5 724 des 5 725 photos portaient DÉJÀ `Florine`
(séquelle de la passe morte). Annuler rendrait `Flo` sans retirer `Florine` —
fidèle à l'état d'avant CE geste, pas d'avant-hier.

## Prochain pas

1. **Qui met un VERROU dans une fiche de personne ?** La question ouverte de
   la session. `_fiche_pour_journal` nomme désormais dans la console le champ
   qu'il écarte — la ligne du 23/08 est à lire dans la fenêtre du serveur, et
   à remonter jusqu'au code qui pose cet objet. Une fiche est du JSON : elle ne
   doit pas porter d'objet vivant, et rien ne l'interdit aujourd'hui.
   **Vérifier au passage que la file XMP est bien allée à 0** (`/api/maint/
   status`, `queues.personnes`) : tant qu'elle tourne, les XMP du fonds portent
   encore `Flo` pour une partie des photos.
2. **Copie HORS SITE (12 bis)** — le seul manque qui reste à l'assurance-vie,
   et il demande une décision avant du code.
3. **Suite de `ui/`** : le CSS commun (chaque page porte encore son `<style>`)
   puis le redesign — deux chantiers SÉPARÉS, exprès (`photo-ui`).
4. **Reste d'audit** : O7–O9, O11–O15 ; **I1** est VISIBLE dans `/reglages`
   (`tours: visages 0, animaux 0`).
5. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Rien n'attend Mike dans `QUESTIONS_MIKE.md`.**
