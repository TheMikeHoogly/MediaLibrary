# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 34)

**Le résidu du recalage est JUGÉ : 34 couples confirmés, 0 à retirer.** Et
c'est le banc qui avait tort, pas l'œil. Un test géométrique a déclaré le
résultat impossible — deux visages aux boîtes disjointes ne peuvent pas être la
même personne — en rendant **0,0 sur 15 cas sur 15**. La première photo ouverte
est une **page d'album photographiée** : 3735×1378, cinq tirages dans un seul
fichier, où Céline paraît deux fois légitimement ; `Flyer_Jenny.jpg` porte
quatre portraits de Jenny. **Un fichier n'est pas une scène**, et un score
parfait reste une alarme — y compris quand c'est le sien.

**Les refus de `recale_rattachements` étaient donc justes.** Vérifié dans
l'autre sens (`--verifier-recalages`) : sur les **33 recalages appliqués**,
**29 (87,9 %) étaient de vraies réparations** — ancien index sous 0,30, jusqu'à
**−0,13** — contre **4 rebrassages**. Le geste tient ; c'est le MOT qui était
trop fort : « décalé » nomme un ÉCART de score, pas une identité fausse.

**Avant, dans la même journée** : la tranche 0,35–0,40 a été jugée —
**92,6 %**, Wilson **76,6 %–97,9 %** → file « À vérifier », **jamais
l'auto-ajout**, `CUR_ADD_SIM` ne bouge pas. Et la planche de référence de
`/tranche`, qui était figée dans le tirage, se relit maintenant dans la fiche
(`_tranche_refs_vivantes`).

## Prochain pas

0. **Un clic de Mike** : `/reglages` → « Rattachements que tu as juges faux »
   → **2 · Appliquer**. Les 28 cas de `/residu` sont jugés : **2 à retirer**
   (`Res Jordi` sur `Bei Michael Jordi.jpg` et `…2.jpg` — il l'avait confondu
   avec son frère Michael), **45 confirmés**, 0 à ajouter, 0 indécidable.
   Aperçu vérifié sur le serveur vivant, mêmes nombres que `--bilan-residu`.
   Réversible (`_corbeille_retraits/`, bouton 3).
   **Et le résultat qui compte n'est pas le retrait** : **12 des 13 « faux
   positifs » étaient JUSTES** (0,06–0,295). Cette colonne ne nomme pas des
   rattachements faux, elle nomme les visages sur lesquels l'empreinte échoue.
   À relire avant de rouvrir quoi que ce soit sur la reconnaissance.
1. **Chantier 12 — la répétition** (choix de Mike : ordre 1-4-3-2). Restaurer
   POUR DE VRAI sur un dossier vierge, chronométrer, puis
   `verifier_restauration.py --restaure <dossier>` : il compare les décisions
   humaines **nom par nom** — un total identique ne prouve rien.
2. **Correctifs d'audit I4–I8.** Dont **I7**, un vrai défaut produit : la casse
   des tags nommés n'est normalisée qu'à trois endroits, donc un
   `personne:nom` importé n'est **jamais** auto-guéri. Puis I4 (code mort
   rejeté), I5/I6 (`/reglages` ment sur le GPU), I8 (routes orphelines).
3. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Une décision à cinq secondes qui traîne depuis cinq sessions** :
l'extraction `ui/` (point 7) — lui donner une session ou la parquer.

**Un repli silencieux repéré, non traité** : `_serve_facecrop` sert le visage
**0** quand l'index est hors bornes, et `/people` fait pareil pour l'avatar.
Zéro cas aujourd'hui (mesuré), mais c'est un mensonge muet à l'endroit exact où
un humain juge. À rendre visible quand on touchera la zone.

**Ne pas rouvrir sans chiffre neuf** : abaisser `CUR_ADD_SIM` (tranché le
22/08) ; 16(a) (mesuré, 17 photos) ; `taken` en base ; backfill ÉCRIT de
`faits` ; index des noms en UNE passe ; filtre des noms sur les `kw` bruts ;
`det_score` comme critère d'espèce ; règle d'espèce ÉLARGIE ; re-passe de
tagging en LOT (50 h GPU — l'incrémental reste ouvert) ; agent git dans le
serveur ; planchers 1990 ; plafond 2100.

**Les TROIS canaux, mêmes octets** (CRLF, via `device_bash`, jamais supprimer ;
`canal.py` les lit tous) : `_commande_serveur.txt` → `redemarrer`, puis
VÉRIFIER `GET /api/serveur` (`code_a_jour` vrai) ; `_commande_git.txt` →
`commit` (traite autonome) ou `livrer` (Mike présent), puis VÉRIFIER
`.git/logs/*`, jamais `_etat_git.json` ; `_commande_banc.txt` → un banc, puis
LIRE `_banc_sortie.txt`. Trois fenêtres ouvertes — Serveur, Git, Bancs ; un
agent est vivant si son `_agent_*_vu.txt` a moins de 30 s.

**Mesurer** : jamais sur `photos.db` — `mesure_copie_base.py` d'abord, puis
`--base copie.db`.

**Un échantillon se FIGE, une référence se LIT MAINTENANT.** Figer le tirage
est ce qui le rend uniforme ; figer la référence est faux — elle n'est pas ce
qu'on mesure, elle est ce CONTRE QUOI on mesure, et elle vieillit précisément
là où une réparation vient de passer.

**Un FICHIER n'est pas une SCÈNE.** Pages d'album photographiées, montages,
flyers : la même personne y paraît plusieurs fois, à des endroits différents.
Toute règle qui suppose une scène par fichier se trompe ici — et elle s'y
trompe sur la population même qui la fait invoquer.

**Un score parfait est une alarme, y compris quand c'est le sien.** 15/15
aurait dû faire relire l'instrument AVANT de s'en servir pour contredire un
humain.

**Un écart de score n'est pas une identité fausse.** Le chiffre qui sépare :
le SCORE DU VISAGE DÉSIGNÉ. 0,594–0,745 = des apparitions multiples ;
0,06–0,295 = des inconnus.

**Un test ne doit rien imprimer.** L'agent git CAPTURE la sortie ; sous Windows
un `print` part dans un tuyau, l'encodage local reprend la main, et le premier
« é » tue le test par `UnicodeEncodeError`.

**La sandbox ne peut pas écrire sur le fonds.** Tout ce qui MODIFIE l'archive
se termine par un bouton dans `/reglages` ou un geste de Mike — prévois-le dans
la conception, sinon le chantier finit en cul-de-sac.
