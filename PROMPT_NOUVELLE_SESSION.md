# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (21/08/2026, fin de session 29)

**Cinq livraisons, toutes observées avant d'être gravées**, `main` fusionnée
après chacune — la dernière porte la re-priorisation.

**Le 5ᵉ axe `espece:` est LIVRÉ**, forme A : un jeton explicite qui filtre sur
la CONCORDANCE YOLO ∧ tagueur, règle UNIQUE (`faits_vue.dit_l_espece`) appelée
par le serveur ET par le banc. Observé : `espece:chat` rend **1 500** sur
**2 386** (plafond de page), **0 en trop** ; `espece:licorne` rend **0** et le
DIT ; six puces INSÈRENT le jeton. Le vrai gain n'est pas le rappel mais la
PRÉCISION : `q=mouton` rend 1 500 photos dont **28** moutons, `espece:mouton`
en rend **32**, tous confirmés.

**La barre de recherche ne ment plus** sur une page de résultats : elle attend
`Entrée` et relance côté serveur. Elle annonçait **3** photos là où le fonds en
a **354**.

**La sandbox est autonome pour mesurer** : `mesure_copie_base.py` fabrique la
copie (API `backup`, `mode=ro`, copie DATÉE), les bancs tournent par le
troisième canal, `verifier_jeton_espece.py` compare le serveur VIVANT à la
règle, clé par clé.

**Deux chiffres ont été corrigés le 21/08, et ils changent la feuille de
route.** « Vérité terrain 0,8 % » mélangeait deux mesures : **18 863** photos
portent un nom (44,8 %, 352 noms) — le produit est couvert — contre **1 196**
visages rattachés sur 71 868 (1,66 %) — seul un ALGORITHME en dépend. Et le
compte oubliait les **1 496 exclusions**, qui sont des étiquettes elles aussi :
vérité terrain réelle **2 692** décisions. Chantier 9 et mode Flo : PARQUÉS.

## Prochain pas

1. **Chantier 12 — la restauration à blanc.** Le seul item dont l'échec serait
   irréversible, et il n'a jamais tourné. Restaurer le snapshot NAS sur un
   dossier VIERGE, chronométrer, noter chaque manque (dont la copie hors-site
   de `journal_jugements.jsonl`). **Partage des rôles** : la restauration est
   un geste de Mike ; ce que la sandbox peut faire, c'est l'INSTRUMENT —
   un `verifier_restauration.py` qui compare le restauré au vivant (entrées,
   noms humains, vecteurs, fiches) et dit ce qui manque. Écrire l'instrument
   d'abord, il rend la manip mesurable au lieu de rassurante.
2. **Chantier 16 — l'agent de tagging INCRÉMENTAL** (idée de Mike, 21/08) :
   re-décrire les seules photos dont la connaissance a CHANGÉ. **Un banc AVANT
   tout code**, jugé en aveugle sur un ET (apport **et** hallucination), et une
   FRONTIÈRE DE PROVENANCE entre ce que le modèle a vu et ce qu'on lui a dit —
   sans elle, la concordance du 5ᵉ axe mesure son propre écho. Périmètre plus
   petit qu'il n'y paraît : `faits` étant une VUE, la médiathèque apprend déjà
   sans LLM ; seule la prose de la description reste en jeu.
3. **Les finitions, en TRAITE AUTONOME** (`commit`, `main` intacte) : UI (11),
   audit I4–I8 / O7–O15, plafond de page à 1 500 sur `espece:chat`. Aucun
   jugement produit là-dedans.
4. **MCP lecture seule (13)**, puis le reste de `ROADMAP.md`.

**Une décision à cinq secondes qui traîne** : l'extraction `ui/` (point 7) —
lui donner une session ou la parquer. La laisser flotter coûte de l'attention
à chaque relecture.

**Ne pas rouvrir sans chiffre neuf** : `taken` en base ; backfill ÉCRIT de
`faits` ; index des noms en UNE passe ; filtre des noms sur les `kw` bruts ;
`det_score` comme critère d'espèce ; règle d'espèce ÉLARGIE (poney, brebis :
+43 sur 3 134) ; re-passe de tagging en LOT (50 h GPU — l'incrémental, lui,
est ouvert) ; agent git dans le serveur ; planchers 1990 ; plafond 2100.

**Les TROIS canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer ;
`canal.py` les lit tous) : `_commande_serveur.txt` → `redemarrer`, puis
VÉRIFIER `GET /api/serveur` (`code_a_jour` vrai) ; `_commande_git.txt` →
`commit` (traite autonome) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json` ; `_commande_banc.txt` → un banc, puis
LIRE `_banc_sortie.txt`. Trois fenêtres ouvertes — Serveur, Git, Bancs ; un
agent est vivant si son `_agent_*_vu.txt` a moins de 30 s.

**Mesurer** : jamais sur `photos.db` — `mesure_copie_base.py` d'abord, puis
`--base copie.db`, `TZ=Europe/Zurich`. Les bancs IMPORTENT la prod. Et ce que
le serveur FAIT ne se lit pas dans un banc : `verifier_jeton_espece.py`
interroge le serveur vivant et compare clé par clé — c'est ce contrôle qui a
montré le « 3 » qui mentait.
