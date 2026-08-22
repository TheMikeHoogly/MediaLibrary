# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 36)

**`PETS` est mesuré**, pour la première fois du projet
(`mesure_rattachements_animaux.py`, 21 tests, lecture seule sur copie).
12 fiches, **351 couples** `[photo, animal]`, 330 mesurables.

**L'index des animaux est SAIN, et le recalage n'y sera pas porté.**
**0 hors bornes.** **10 décalés, dont 8 sur des photos que la fiche cite
plusieurs fois** — Mutz cité **7 fois** sur `111-1103_IMG.JPG`, 10 animaux :
c'est le nommage d'un GROUPE, pas un index qui glisse. Restent **2 vrais
candidats sur 330 (0,6 %)**, contre 3,5 % côté visages avant réparation. La
raison est dans le code : rien ne ré-embarque une photo déjà connue côté
animaux, et `migrate_animal_pipeline` vide tout puis remet `faces = []`.

**Le résultat qui compte porte sur l'INSTRUMENT.** Sur 330 couples **confirmés
par des humains**, **122 (37 %) scorent sous `PET_MATCH_SIM = 0,55`** —
médiane 0,603, p10 0,392, min 0,231. Le seuil coupe au MILIEU de la
distribution des rattachements JUSTES ; la même colonne vaut **1,1 %** côté
visages. C'est ce plafond qui limite tout ce qu'on voudrait automatiser sur les
animaux. **Ne pas y toucher sans jugements humains** — même exigence que la
tranche 0,35–0,40.

**Deux tas précis, un geste humain.** **15 clés mortes** (Inti 7, Luna 5,
Pins 2, Pticon 1), corroborées par un second chemin — le croisement par le tag
`animal:` en rend exactement 15, les mêmes fiches. Et **6 couples d'espèce
incohérente** : Luna, un chat, posée sur une détection **`dog`**, sur 4 photos.
Faux certains, sans qu'aucun seuil ait à le dire.

**Une réserve, pas un défaut : 651 photos portent un nom d'animal sans aucun
rattachement** (Inti 420, Mutz 111, Luna 94 ; Puma, Kevin et Le chat de
Bremblens : zéro couple pour 7, 6 et 2 photos taguées).

## Prochain pas

1. **Les 21 couples d'animaux à trancher** (15 clés mortes + 6 espèces
   incohérentes). Les clés mortes se traitent comme le 22/08 côté visages :
   chercher d'abord si la photo vit sous un AUTRE chemin
   (`journaux_deplacements.py`, 19 331 déplacements connus) avant d'envisager
   un retrait. Les 6 « espèce » ne demandent aucune recherche : la détection
   est un chien, la fiche un chat.
2. **Chantier 12 — la répétition** (choix de Mike : ordre 1-4-3-2). Test « PC
   mort lundi, tout revit vendredi », et c'est un **geste de Mike** : restaurer
   POUR DE VRAI sur un dossier vierge, chronométrer, puis
   `verifier_restauration.py --restaure <dossier>` — il compare les décisions
   humaines **nom par nom**, un total identique ne prouve rien.
3. **Correctifs d'audit I4–I8.** Dont **I7**, un vrai défaut produit : la casse
   des tags nommés n'est normalisée qu'à trois endroits, donc un
   `personne:nom` importé n'est **jamais** auto-guéri. Puis I4 (code mort
   rejeté), I5/I6 (`/reglages` ment sur le GPU), I8 (routes orphelines).
4. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Deux pistes ouvertes par Mike (22/08), à instruire** — détail dans
`ROADMAP.md`, section « Pistes ouvertes par Mike » :
(a) **tirer plus du LLM local à matériel constant** (sortie contrainte,
auto-cohérence, décodage spéculatif, petits modèles parus depuis
`qwen3-vl:2b`) — **se renseigner à l'ouverture de toute session touchant au
tagging, à la description ou à la recherche**, ce domaine bouge vite ;
(b) **ouvrir la médiathèque à toute la famille**, dossiers persos et contrôle
de qui voit quoi — trois questions à trancher avant la première ligne de code.

**Une décision à cinq secondes qui traîne depuis sept sessions** :
l'extraction `ui/` (point 7) — lui donner une session ou la parquer.

**Un repli silencieux repéré, non traité, et il est DOUBLE** : `_serve_facecrop`
sert le visage **0** quand l'index est hors bornes, `_serve_animalcrop` fait
exactement pareil pour l'animal, et `/people` pour l'avatar. Zéro cas
aujourd'hui des deux côtés (mesuré), mais c'est un mensonge muet à l'endroit
exact où un humain juge. À rendre visible quand on touchera la zone.

**Ne pas rouvrir sans chiffre neuf** : le chantier des rattachements (visages
ET animaux) ; abaisser `CUR_ADD_SIM` ; porter le recalage aux animaux ;
16(a) ; `taken` en base ; backfill ÉCRIT de `faits` ; index des noms en UNE
passe ; filtre des noms sur les `kw` bruts ; `det_score` comme critère
d'espèce ; règle d'espèce ÉLARGIE ; re-passe de tagging en LOT (50 h GPU —
l'incrémental reste ouvert) ; agent git dans le serveur ; planchers 1990 ;
plafond 2100.

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

**Un ZÉRO parfait est une alarme, exactement comme un score parfait.** Le banc
des animaux rendait « 0 photo taguée » pour les DOUZE fiches : il lisait `kw`,
la prod écrit `kw_fr`, et `_kw_has` compare en minuscules. Un compte identique
sur toutes les lignes d'un tableau accuse la COLONNE, pas les lignes.

**Un banc ne se recopie pas d'un domaine à l'autre.** Les visages passent par
`classifier.prototypes` (k-moyennes), les animaux par une simple moyenne
(`cat_centroid`) ; les seuils, les espèces nommables et le champ de tags
diffèrent aussi. Prendre la règle du voisin mesure un magasin qui n'existe pas.

**Un FICHIER n'est pas une SCÈNE** — et ça vaut aussi pour les animaux : sans
la colonne « combien de fois la fiche cite cette photo », les 10 décalés se
lisaient comme 10 avaries. Il y en a 2.

**Un score parfait est une alarme, y compris quand c'est le sien.**

**Un écart de score n'est pas une identité fausse, et un seuil bas nomme une
cécité.** Côté visages, 12 des 13 couples sous le seuil étaient JUSTES. Côté
animaux ils sont 122 sur 330 — la même phrase, à une autre échelle.

**Un test ne doit rien imprimer.** L'agent git CAPTURE la sortie ; sous Windows
un `print` part dans un tuyau, l'encodage local reprend la main, et le premier
« é » tue le test par `UnicodeEncodeError`.

**La sandbox ne peut pas écrire sur le fonds.** Tout ce qui MODIFIE l'archive
se termine par un bouton dans `/reglages` ou un geste de Mike — prévois-le dans
la conception, sinon le chantier finit en cul-de-sac.
