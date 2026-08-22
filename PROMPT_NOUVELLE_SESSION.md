# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 35)

**Le chantier des rattachements est CLOS.** Parti de 42 couples
`[photo, visage]` qui désignaient le mauvais visage : 33 recalages appliqués
(dont **29 vraies réparations** — l'ancien index scorait sous 0,30, jusqu'à
−0,13), 28 cas jugés à l'œil par Mike sur `/residu`, **2 retraits**. Couples
**1 194 → 1 192**, aucune décision humaine perdue. Ce qui reste est mesuré et
sain : 9 « décalés » qui sont des apparitions multiples (pages d'album,
montages), 13 « faux positifs » **jugés JUSTES à 12 sur 13**, 155 photos à un
seul visage.

**Le résultat qui compte porte sur l'INSTRUMENT, pas sur le fonds.** La colonne
« sous le seuil de faux positif » ne dit pas « ce n'est pas elle » mais **« je
ne la reconnais pas »** : Flo à 0,06, FX à 0,113, Markus à 0,135 — tous
confirmés par Mike. Elle mesure la cécité de l'empreinte. Ces 13 reviendront
dans chaque `--residu` tant que leur score sera bas : ils sont JUGÉS, ne pas
les relire comme 13 défauts.

**Et les 2 seuls vrais retraits étaient une fratrie** : Res confondu avec son
frère Michael Jordi. Ni le score ni la géométrie ne tranchent une fratrie —
seulement quelqu'un qui les connaît. C'est exactement ce que la règle de
recalage refuse d'arbitrer, et elle avait raison.

**Avant, le même jour** : la tranche 0,35–0,40 jugée — **92,6 %**, Wilson
**76,6 %–97,9 %** → file « À vérifier », **jamais l'auto-ajout**, `CUR_ADD_SIM`
ne bouge pas.

## Prochain pas

1. **Chantier 12 — la répétition** (choix de Mike : ordre 1-4-3-2). C'est le
   test « PC mort lundi, tout revit vendredi », et c'est un **geste de Mike** :
   restaurer POUR DE VRAI sur un dossier vierge, chronométrer, puis
   `verifier_restauration.py --restaure <dossier>` — il compare les décisions
   humaines **nom par nom**, un total identique ne prouve rien.
2. **Correctifs d'audit I4–I8.** Dont **I7**, un vrai défaut produit : la casse
   des tags nommés n'est normalisée qu'à trois endroits, donc un
   `personne:nom` importé n'est **jamais** auto-guéri. Puis I4 (code mort
   rejeté), I5/I6 (`/reglages` ment sur le GPU), I8 (routes orphelines).
3. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).
4. **`PETS` n'a jamais été mesuré.** Son magasin porte des empreintes DINOv2,
   et `assigned_keys` ne le lit pas : tout ce qui a été trouvé et réparé côté
   visages est INCONNU côté animaux. Commencer par un banc, pas par un
   correctif — réparer un magasin qu'on n'a pas mesuré est un pari.

**Deux pistes ouvertes par Mike (22/08), à instruire** — détail dans
`ROADMAP.md`, section « Pistes ouvertes par Mike » :
(a) **tirer plus du LLM local à matériel constant** (sortie contrainte,
auto-cohérence, décodage spéculatif, petits modèles parus depuis
`qwen3-vl:2b`) — **se renseigner à l'ouverture de toute session touchant au
tagging, à la description ou à la recherche**, ce domaine bouge vite ;
(b) **ouvrir la médiathèque à toute la famille**, dossiers persos et contrôle
de qui voit quoi — trois questions à trancher avant la première ligne de code.

**Une décision à cinq secondes qui traîne depuis six sessions** :
l'extraction `ui/` (point 7) — lui donner une session ou la parquer.

**Un repli silencieux repéré, non traité** : `_serve_facecrop` sert le visage
**0** quand l'index est hors bornes, et `/people` fait pareil pour l'avatar.
Zéro cas aujourd'hui (mesuré), mais c'est un mensonge muet à l'endroit exact où
un humain juge. À rendre visible quand on touchera la zone.

**Ne pas rouvrir sans chiffre neuf** : le chantier des rattachements ;
abaisser `CUR_ADD_SIM` ; 16(a) ; `taken` en base ; backfill ÉCRIT de `faits` ;
index des noms en UNE passe ; filtre des noms sur les `kw` bruts ; `det_score`
comme critère d'espèce ; règle d'espèce ÉLARGIE ; re-passe de tagging en LOT
(50 h GPU — l'incrémental reste ouvert) ; agent git dans le serveur ;
planchers 1990 ; plafond 2100.

**Les TROIS canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer ;
`canal.py` les lit tous) : `_commande_serveur.txt` → `redemarrer`, puis
VÉRIFIER `GET /api/serveur` (`code_a_jour` vrai) ; `_commande_git.txt` →
`commit` (traite autonome) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json` ; `_commande_banc.txt` → un banc, puis
LIRE `_banc_sortie.txt`. Trois fenêtres ouvertes — Serveur, Git, Bancs ; un
agent est vivant si son `_agent_*_vu.txt` a moins de 30 s.

**Mesurer** : jamais sur `photos.db` — `mesure_copie_base.py` d'abord, puis
`--base copie.db`.

## Ce que cette journée a coûté, et qu'il ne faut pas repayer

**Un échantillon se FIGE, une référence se LIT MAINTENANT.** Figer le tirage le
rend uniforme ; figer la référence est faux — elle n'est pas ce qu'on mesure,
elle est ce CONTRE QUOI on mesure, et elle vieillit précisément là où une
réparation vient de passer.

**Un FICHIER n'est pas une SCÈNE.** Pages d'album photographiées, montages,
flyers : la même personne y paraît plusieurs fois, à des endroits différents.
Toute règle qui suppose une scène par fichier se trompe — et s'y trompe sur la
population même qui la fait invoquer.

**Un score parfait est une alarme, y compris quand c'est le sien.** 15/15
aurait dû faire relire l'instrument AVANT de s'en servir pour contredire un
humain.

**Un écart de score n'est pas une identité fausse, et un seuil bas nomme une
cécité.** Le chiffre qui tranche : le SCORE DU VISAGE DÉSIGNÉ. 0,594–0,745 =
des apparitions multiples ; 0,06–0,295 = des visages que l'empreinte ne sait
pas lire, pas des erreurs.

**Deux pages jumelles ne partagent jamais des touches de sens opposé.**
`/tranche` : `1`/`2`/`3` = Oui/Non/Je ne sais pas. `/residu` : lettres `A`–`H`.
Les chiffres, à dix minutes d'intervalle, ont fait enregistrer quinze réponses
pour une autre.

**Un test ne doit rien imprimer.** L'agent git CAPTURE la sortie ; sous Windows
un `print` part dans un tuyau, l'encodage local reprend la main, et le premier
« é » tue le test par `UnicodeEncodeError`.

**La sandbox ne peut pas écrire sur le fonds.** Tout ce qui MODIFIE l'archive
se termine par un bouton dans `/reglages` ou un geste de Mike — prévois-le dans
la conception, sinon le chantier finit en cul-de-sac.
