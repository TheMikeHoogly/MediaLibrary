# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (21/08/2026, fin de session 29)

**Trois livraisons, toutes observées avant d'être gravées** ; `main` fusionnée
après chacune. La dernière : `7efc4c0`, les puces d'espèce.

**Le 5ᵉ axe `espece:` est LIVRÉ, forme A.** Un jeton explicite qui filtre sur
la CONCORDANCE — YOLO ∧ tagueur, règle UNIQUE (`faits_vue.dit_l_espece`)
appelée par le serveur ET par le banc. Observé en réel : `espece:chat` rend
**1 500** sur **2 386** (plafond de page), **0 en trop** face à la règle ;
`espece:licorne` rend **0** et le DIT ; `espèce:Chats Luna` rend **198**. Six
puces sous la barre INSÈRENT le jeton — il se compose, il ne remplace pas.

**Le gain n'est pas celui qu'on attendait.** 1 018 photos qu'aucun des six
mots ne rend, oui — mais surtout la PRÉCISION : `q=mouton` rend **1 500**
photos dont **28** moutons, `espece:mouton` en rend **32**, tous confirmés par
deux regards. Le jeton ne gagne pas des photos, il en RETIRE 1 468.

**La sandbox fabrique sa propre copie de la base** : `mesure_copie_base.py`
(API `backup`, source en `mode=ro`, copie DATÉE). 276,5 Mo en 0,9 s, et il
chiffre pourquoi un `copy` était faux — **5,4 Mo** vivaient dans le WAL. Plus
un aller-retour clavier avant de mesurer.

**Un chiffre sans son code n'est pas reproductible.** La concordance du 20/08
(3 065) ne vivait que dans un tableau ; réécrite en code, elle rend **3 134**.
Même famille, pas le même trait — le mouton se dit surtout dans `desc`.

## Prochain pas

1. **La barre de recherche ment sur une page de résultats** (`QUESTIONS_MIKE.md`,
   une question en attente) : `/files?q=` ne charge que le résultat précédent,
   donc y chercher autre chose n'intersecte que CE sous-ensemble — **3** photos
   annoncées là où le fonds en a **354**. Les puces relancent la requête ; la
   barre, non. Défaut ANCIEN, pas propre au 5ᵉ axe.
2. **Gestes Mike** : nettoyer Flo (5 909 photos) ; re-rejeter Caline ;
   `copie.db` (276 Mo) à la racine, gitignorée.
3. **Le reste** (`ROADMAP.md`) : prompt de PROD qui hallucine ; doublons
   proches ; UI (11) ; restauration à blanc (12) ; MCP lecture (13).

**Ne pas rouvrir sans chiffre neuf** : `taken` en base ; backfill ÉCRIT de
`faits` ; index des noms en UNE passe ; filtre des noms sur les `kw` bruts ;
`det_score` comme critère d'espèce ; règle d'espèce ÉLARGIE (poney, brebis,
chaton : +43 photos sur 3 134) ; agent git dans le serveur ; planchers 1990
(7 et 0, couplés) ; plafond 2100 (0).

**Les TROIS canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer ;
`canal.py` les lit tous) : `_commande_serveur.txt` → `redemarrer`, puis
VÉRIFIER `GET /api/serveur` (`code_a_jour` vrai) ; `_commande_git.txt` →
`commit` (traite autonome) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json` ; `_commande_banc.txt` → un banc, puis
LIRE `_banc_sortie.txt`. Trois fenêtres doivent être ouvertes — Serveur, Git,
Bancs ; un agent est vivant si son `_agent_*_vu.txt` a moins de 30 s.

**Mesurer** : jamais sur `photos.db` (le serveur est l'écrivain unique) —
`mesure_copie_base.py` d'abord, puis `--base copie.db`, `TZ=Europe/Zurich`. Les
bancs IMPORTENT la prod, ils ne la recopient pas. Et ce que le serveur FAIT ne
se lit pas dans un banc : `verifier_jeton_espece.py` interroge le serveur
vivant et compare clé par clé — c'est ce contrôle qui a montré le « 3 » qui
mentait.
