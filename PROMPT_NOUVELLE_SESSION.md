# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 33)

**La tranche 0,35–0,40 est tranchée, et l'œil de Mike avait raison deux fois,
pour deux raisons différentes.**

**Le chiffre.** 30 propositions jugées par lui : **25 justes, 2 faux, 3
indécidables** → **92,6 %** sur 27 tranchées, **Wilson 95 % : 76,6 %–97,9 %**.
Ce que l'intervalle autorise, et rien de plus : la tranche a sa place dans la
file **« À vérifier »**, **jamais dans l'auto-ajout**. `CUR_ADD_SIM` ne bouge
pas.

**Première raison — la planche était FIGÉE, et c'est corrigé.** Il a dit :
« je n'ai pas constaté d'amélioration, certaines photos proposées pour une
personne contiennent une AUTRE personne. » Le tirage datait de **21:26**, le
recalage avait été appliqué à **22:19**, et la page servait les références du
FICHIER : l'état d'avant la réparation. **3 planches sur 30** — Didier,
Mathieu, Markus Grossert, dont les deux qu'il avait nommés la veille.
`_tranche_refs_vivantes` relit désormais la fiche à chaque affichage, et le
banc ne tire plus de références du tout : elles appartiennent à la PAGE.
Observé après redémarrage (`code_a_jour` vrai) : **4 références corrigées sur
les 3 planches**, les mêmes 4 que la quarantaine du recalage — deux chemins —
et les 30 verdicts ont survécu. La légende dit maintenant « visages déjà
**rattachés à** X » : `confirmed` est un autre champ, et une planche qui se dit
*confirmée* accuse le jugement humain d'une faute qui est celle de l'index.

**Seconde raison — le résidu est CONCENTRÉ, et c'est le prochain pas.** Les
**9 décalés** restants et les **34 refus « ambigu »** tiennent sur **10
fiches**, et **Didier en porte 4 des 9**. « 0,8 % sur 1 194 couples » se lit
comme un fonds sain ; sur SA fiche, c'est un intrus à chaque ouverture.

**La page du résidu est LIVRÉE (fin de session 33).**
`mesure_rattachements.py --base copie.db --residu` écrit **15 cas sur 9
fiches, 34 couples cités** ; la page **`/residu`** (18 tests) les montre côte à
côte avec la planche de référence — vivante, et **la photo en cause en est
retirée** : le visage qu'on juge ne peut pas être sa propre référence. Elle
n'attribue rien et ne retire rien ; un verdict ne peut désigner qu'un visage
MONTRÉ. Observé en réel : 15 cas servis, sélection sans écriture. Un lien y
mène depuis `/reglages`, sous les boutons du recalage.

## Prochain pas

0. **Juger les 15 cas sur `http://192.168.0.13:8080/residu`** (clavier `1`–`9`
   pour cocher, `Entrée` pour valider, `0` je ne sais pas, `Z` revenir), puis
   `mesure_rattachements.py --base copie.db --bilan-residu`. Le bilan sépare
   **à retirer** (cité, jugé pas elle), **confirmé**, et **à AJOUTER** (jugé
   elle mais non cité — une attribution, autre geste, hors plan de retrait).
   Le retrait est DESTRUCTIF : quarantaine réversible et geste de Mike, comme
   le recalage. **Il reste à ÉCRIRE** — les trois boutons dans `/reglages`,
   passant par la même fonction que le bilan.
   Et **`PETS` n'a jamais été mesuré** (empreintes DINOv2, `assigned_keys` ne
   le lit pas).
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

**Un échantillon se FIGE, une référence se LIT MAINTENANT.** C'est la leçon du
22/08 : figer le tirage est ce qui le rend uniforme, figer la référence est
faux — elle n'est pas ce qu'on mesure, elle est ce CONTRE QUOI on mesure, et
elle vieillit précisément là où une réparation vient de passer.

**Un défaut concentré ne se voit pas dans un taux.** 0,8 % sur le fonds, mais
4 intrus sur une seule fiche. Compter par FICHE avant de conclure que le fonds
va bien.

**Un test ne doit rien imprimer.** L'agent git CAPTURE la sortie ; sous Windows
un `print` part dans un tuyau, l'encodage local reprend la main, et le premier
« é » tue le test par `UnicodeEncodeError`.

**La sandbox ne peut pas écrire sur le fonds.** Tout ce qui MODIFIE l'archive
se termine par un bouton dans `/reglages` ou un geste de Mike — prévois-le dans
la conception, sinon le chantier finit en cul-de-sac.
