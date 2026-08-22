# Amorce de reprise — MediaLibrary

> À coller après connexion de `C:\Prog\Claude\MediaLibrary`. Règles et
> protocole : `CLAUDE.md`. Ici : **l'état et le prochain pas, rien d'autre.**

Tu reprends **MediaLibrary**. **VÉRIFIE avant de lire** : `.git/HEAD`,
`.git/logs/HEAD` et `.git/logs/refs/heads/main` disent ce qui a été commité et
FUSIONNÉ — ce document, non. Puis `ROADMAP.md`, `eval/DECISIONS.md`,
`eval/METHODE.md` — et `docs/DECISIONS_OUTILLAGE.md` si le sujet touche aux
canaux. Débrief en 2–3 lignes, puis on attaque.

## Où on en est (22/08/2026, fin de session 37)

**Le chantier des animaux est CLOS, et il se ferme sur une réfutation.** Les
21 couples « à trancher » ne demandent **aucun geste sur le fonds**.

**Les 6 « espèce incohérente » sont JUSTES, 6 sur 6.** Le banc tenait l'espèce
pour son verdict le plus solide — « faux sans qu'aucun seuil ait à le dire ».
Le score de la détection DÉSIGNÉE, qui manquait, dit l'inverse : **0,441 /
0,594 / 0,604 / 0,623 / 0,666** contre une médiane de **0,603** sur les couples
confirmés. Les six crops ouverts dans `/api/animalcrop` : **six chats crème**.
**C'est l'ÉTIQUETTE d'espèce de YOLO qui ment, pas le rattachement** — et elle
range Luna sous « chien » dans l'axe espèce. Un couple à **0,441** est juste
(un seuil bas nomme une cécité) ; le seul « recalage évident », **+0,036**,
était deux BOÎTES du même chat.

**Les 15 clés mortes n'ont aucune contrepartie, par trois chemins.** Journaux
d'annulation (19 331 déplacements) : rien. Même nom de fichier vivant : rien.
Disque : `verifier_orphelins --filtre ARZOPA --table animals` rend **115
entrées, 0 présente, 115 « disparu »**, dont 12 jugées par un humain. On
**garde** — suite du choix du 22/08 sur le résidu des visages ; leurs
détections survivent sous l'ancien chemin, un humain peut encore les regarder.

## Prochain pas — ordre choisi par Mike (22/08) : 1, 12, 7

1. **Chantier 12 — la répétition.** Test « PC mort lundi, tout revit
   vendredi », et c'est un **geste de Mike** : restaurer POUR DE VRAI sur un
   dossier vierge, chronométrer, puis `verifier_restauration.py --restaure
   <dossier>` — il compare les décisions humaines **nom par nom**, un total
   identique ne prouve rien.
2. **Extraction `ui/` (point 7)** : Mike lui donne sa session — sortir les
   9 pages HTML inline de `server.py` vers `ui/`, `bundle.py` déjà préparatoire.
   Gros diff sur le monolithe : `monolith-surgery` avant la première ligne.
3. **Correctifs d'audit I4–I8.** Dont **I7**, un vrai défaut produit : la casse
   des tags nommés n'est normalisée qu'à trois endroits, donc un `personne:nom`
   importé n'est **jamais** auto-guéri. Puis I4 (code mort rejeté), I5/I6
   (`/reglages` ment sur le GPU), I8 (routes orphelines).
4. **MCP lecture seule (13)** : recherche, fiches et `faits` en outils MCP
   locaux (JSON-RPC stdio, zéro dépendance — skill `mcp-builder`).

**Chiffre neuf laissé ouvert (22/08)** : l'étiquette d'espèce de YOLO est
fausse **au moins 6 fois sur 351** couples d'animaux nommés (1,7 %), en
silence, et **l'axe espèce en dépend**. Aucun instrument ne la mesure sur le
fonds entier. Ne pas en faire un chantier sans avoir décidé ce qu'on en ferait.

**Deux pistes ouvertes par Mike (22/08), à instruire** — détail dans
`ROADMAP.md`, section « Pistes ouvertes par Mike » :
(a) **tirer plus du LLM local à matériel constant** (sortie contrainte,
auto-cohérence, décodage spéculatif, petits modèles parus depuis
`qwen3-vl:2b`) — **se renseigner à l'ouverture de toute session touchant au
tagging, à la description ou à la recherche**, ce domaine bouge vite ;
(b) **ouvrir la médiathèque à toute la famille**, dossiers persos et contrôle
de qui voit quoi — trois questions à trancher avant la première ligne de code.

**Un repli silencieux repéré, non traité, et il est DOUBLE** : `_serve_facecrop`
sert le visage **0** quand l'index est hors bornes, `_serve_animalcrop` fait
exactement pareil pour l'animal, et `/people` pour l'avatar. Zéro cas
aujourd'hui des deux côtés (mesuré), mais c'est un mensonge muet à l'endroit
exact où un humain juge. À rendre visible quand on touchera la zone.

**Deux fichiers de suivi serrent** : `ROADMAP.md` **47 078** et
`eval/DECISIONS.md` **47 029** octets pour 50 000. La prochaine session qui les
touche condense d'abord — le détail vit dans git, pas dans les docs.

**Ne pas rouvrir sans chiffre neuf** : le chantier des rattachements (visages
ET animaux, clos des deux côtés) ; les 15 clés mortes et les 6 espèces ;
abaisser `CUR_ADD_SIM` ; porter le recalage aux animaux ; 16(a) ; `taken` en
base ; backfill ÉCRIT de `faits` ; index des noms en UNE passe ; filtre des
noms sur les `kw` bruts ; `det_score` comme critère d'espèce ; règle d'espèce
ÉLARGIE ; re-passe de tagging en LOT (50 h GPU — l'incrémental reste ouvert) ;
agent git dans le serveur ; planchers 1990 ; plafond 2100.

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

**Le verdict qu'un instrument croit le plus solide est celui qu'il faut
mesurer en premier.** « L'espèce tranche sans seuil, aucun score n'a besoin de
le dire » : c'était l'hypothèse la plus sûre du banc des animaux, et la seule
qui ait été fausse — 6 fois sur 6. Ce qui l'a fait tomber est un chiffre
qu'elle avait déclaré INUTILE : le score de la détection désignée.

**Un ZÉRO parfait est une alarme, exactement comme un score parfait** — et
deux fois de suite dans la même session. « 0 photo taguée » pour les douze
fiches accusait la COLONNE (`kw` au lieu de `kw_fr`). « 15 clés mortes sur 15
sans contrepartie » ne s'est tenu qu'après un TROISIÈME chemin, le disque.

**Un écart de score n'est pas une identité fausse, et un seuil bas nomme une
cécité.** Encore : un couple à 0,441 vu à l'œil est Luna.

**Avant de recaler, REGARDER.** Deux boîtes qui se recouvrent sur le même chat
donnent un « meilleur candidat » à +0,036 : le recalage aurait été un
rebrassage.

**La sandbox ne peut pas écrire sur le fonds.** Tout ce qui MODIFIE l'archive
se termine par un bouton dans `/reglages` ou un geste de Mike — prévois-le dans
la conception, sinon le chantier finit en cul-de-sac.
