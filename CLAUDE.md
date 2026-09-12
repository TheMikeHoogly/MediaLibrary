# MediaLibrary — brief projet

> Dépôt GitHub privé `TheMikeHoogly/MediaLibrary`. Tous les chemins sont relatifs
> à `SCRIPT_DIR`. Lu à chaque session : **invariants seulement**. État courant →
> `ROADMAP.md` ; reprise → `PROMPT_NOUVELLE_SESSION.md` ; détail → skills et docs.

## Ce que c'est

Photothèque familiale locale : serveur **Python stdlib pur** (`http.server`) sur
le réseau domestique, **~40 600 photos** sur NAS SMB (mesure du 10/09 :
`faces_index` en porte 40 584), 5 pipelines d'IA locale — tagging
**`qwen3.5:4b`** (Ollama ; `qwen3-vl:2b` était le modèle d'avant la campagne du
05/09), visages InsightFace `buffalo_l` (512-d), animaux
YOLO11s, individus animaux DINOv2 (768-d), recherche sémantique SigLIP 2
(`semantic.py`). Les noms attribués (`personne:Nom`, `animal:Nom`) sont écrits
dans les **XMP des fichiers** (exiftool) : ils survivent à la base.
**Matériel : RTX 3050 Laptop, 4 Go VRAM** — la contrainte qui filtre toutes les
décisions techniques. `FACE_USE_GPU=False` **volontaire** (VRAM prise par Ollama).

## Règles absolues

1. **`.bat` en ASCII PUR, et sans parenthèse dans un bloc.** `cmd.exe` relit le
   fichier par décalage d'octets : un seul caractère multi-octets fait sauter des
   étapes en silence. Interdits même en `REM` : accents, `« »`, `─ → ✓ ⚠`, emoji.
   **Et une parenthèse dans un `echo` À L'INTÉRIEUR d'un bloc `( … )` FERME le
   bloc** — mort sur « ou etait inattendu », un message qui ne nomme ni le
   fichier, ni la ligne, ni la cause (22/08). Écrire `^(` `^)`, ou mieux : pas de
   blocs, des `goto`. Contrôle avant livraison et **lire sa sortie** :
   `python verifier_bat.py` (+ hook PostToolUse) — il voit les trois défauts.
   Déjà commise 3×.
   **Et ne JAMAIS éditer un `.bat` pendant qu'il TOURNE** : même correction
   juste, même ASCII pur — le décalage d'octets déplace le curseur du
   `cmd.exe` en cours, qui saute ou meurt sans rien dire. Le 23/08 la fenêtre
   des Bancs est morte comme ça, sur l'ajout d'une ligne d'aide. Le 09/09 une
   reformulation de +70 octets pendant le bat 49 lui a fait exécuter un
   FRAGMENT de ligne : Windows a résolu `.py` vers l'alias du Microsoft Store,
   « Python est introuvable », errelevel 9009, et un message d'arrêt FAUX —
   démontré en recalculant l'offset sur les deux versions. Éditer, puis
   demander à Mike de ROUVRIR la fenêtre — et vérifier son `_agent_*_vu.txt`.
2. **Les noms humains ne se perdent jamais.** Toute migration les préserve
   (modèle `migrate_animal_pipeline()`). Un changement qui risque d'en perdre un
   est faux, quel que soit son gain.
3. **Zéro dépendance au démarrage.** Imports lourds (numpy, torch, insightface,
   ultralytics) **paresseux, dans les fonctions**. Client : ni npm, ni bundler,
   ni framework.
4. **SQLite en local, jamais sur le NAS** (SMB = corruption). `photos.db` WAL
   dans le dossier du script ; sauvegarde NAS par snapshot (`backup_db()`).
   Ne jamais ouvrir `photos.db` depuis le sandbox : le serveur est l'écrivain
   unique — les tests copient la base d'abord.
5. **Git : jamais depuis la VM, toujours par l'AGENT.** `git` lancé sur le
   dossier MONTÉ laisse un `.git/index.lock` que la VM ne sait pas supprimer —
   donc ni outil de plugin/MCP, ni `git` via `device_bash`, jamais. Claude
   livre en écrivant **`livrer`** dans `_commande_git.txt` ; `git_agent.py`
   (fenêtre « MediaLibrary - Git ») CONTRÔLE, puis commit + push + fusion
   fast-forward. Il **refuse** tant que le serveur ne fait pas tourner le code
   visé, qu'un test d'un module touché est rouge, qu'un `.bat` n'est pas ASCII
   pur ou que le lint crie — d'où l'ordre : **éditer → redémarrer → OBSERVER →
   livrer**, la preuve AVANT le commit. `force=raison` dans
   `SESSION_COMMIT.txt` lève les contrôles négociables, jamais le verrou, la
   branche ni les fichiers binaires. Ce que l'agent ne sait pas faire (`reset`,
   `rebase`, `--force`, vraie fusion, suppression de branche) reste à Mike :
   `27 - Git.bat`.
   **Lire l'état, toujours et d'abord** : `.git/HEAD`, `.git/logs/HEAD` et
   `.git/logs/refs/heads/main` (**fusions** — le fast-forward se fait sans
   checkout, rien n'en paraît dans `logs/HEAD`) via staging, lecture seule,
   aucun verrou. `_etat_git.json` dit ce que l'agent a **tenté** ; git dit ce
   qui s'est **passé**.

6. **Un outil qui JUGE ne TÉMOIGNE pas.** Un instrument qui se lit lui-même se
   donne toujours raison. Mesuré **cinq fois** sur la seule chaîne de ménage
   (09/09) : la sortie `_orphelins.json` citait tous les fichiers du dépôt ;
   `_banc_sortie.txt` recopiait ce qu'il venait d'imprimer ; la POLITIQUE
   d'`appliquer_menage.py` — une liste de cibles **à jeter** — protégeait ce
   qu'elle désignait ; son banc faisait pareil avec ses fixtures ; et
   l'instrument lui-même, **parce que j'avais écrit dans ses commentaires le
   nom des fichiers sur lesquels il s'était trompé** : écrire l'histoire d'une
   erreur la refaisait. Tout ce qui juge, mesure, nettoie ou consigne — l'outil,
   son banc, ses rapports, ses manifestes — est **hors du corpus de preuve**.
7. **Une protection doit nommer la PLACE, pas seulement le nom.** Un élagage
   comparé à un nom NU frappe aussi les homonymes, y compris ceux qu'on vient
   de jeter : `_corbeille_session` protégeait la corbeille VIVANTE de la racine
   et faisait taire la corbeille MORTE archivée dans `_to_delete\` — **579 des
   800 fichiers**. Idem pour `photos.db`, dont une COPIE de 283 Mo héritait de
   la protection de la base. Ancrer (`IGNORES_RACINE` vs `IGNORES_PARTOUT`).
8. **Un angle mort a rarement une seule porte.** Corriger la première et se
   déclarer content est l'erreur, pas la première erreur. Ce qui rend la
   suivante visible : **un compteur d'ÉTENDUE imprimé à chaque passage** —
   combien de fichiers parcourus, combien examinés, combien d'écartés et
   pourquoi. 719 → 3 761 → 3 883 → 4 465, trois portes, trois passages.
   *Une règle qu'on ne mesure pas n'est pas un plancher, c'est un vœu.*
9. **Une option qui ne peut JAMAIS aboutir est une promesse que l'outil ne
   tiendra pas.** L'étape 3 du bat 50 proposait de purger les journaux : 35 des
   44 étaient `LU PAR UN MOTIF`, donc vétotés par construction — Mike a répondu
   « 2 » deux fois et lu « Rien à déplacer ». Le bouton « Rendre privée » de
   /sensibles échouait de même à chaque clic. Dans les deux cas : le dire AVANT
   (éteindre le contrôle, nommer la cause), ou permettre le geste.
10. **Un refus doit nommer sa cause à qui regarde déjà la chose.** « Fichier
   introuvable » existe pour ne pas révéler une existence à qui n'a pas le
   droit de la connaître — et il devient un mensonge dès que l'interface a mis
   la photo sous les yeux de celui qui clique. Corollaire d'ORDRE, attrapé par
   un banc : la visibilité se teste EN PREMIER, sinon un refus exact (« déjà
   dans un dossier privé ») confirme une existence à qui n'y a pas droit.

11. **Une analyse n'est pas un fait : elle se CONTRE-VÉRIFIE avant de servir.**
   La faute la plus coûteuse de ce projet n'est pas une erreur de code, c'est
   une conclusion juste-en-apparence qu'on découvre fausse à l'itération
   suivante. Quatre fois le 12/09, en une matinée : une sortie de banc LUE
   AVANT la fin du run (95 s de banc, 30 s d'attente) a fait conclure deux
   fois de suite à un échec, puis à une cause introuvable — le correctif
   marchait ; un banc affirmait que `_serve_gallery` n'appelait plus
   `_best_time`, il l'appelait dans TROIS autres branches ; un compteur posé
   à 4 en valait 6, dont mon propre commentaire ; et une consigne donnée à
   Mike sur Windows reposait sur un paquet « en attente » que DISM ne portait
   pas. **Le réflexe à prendre** : énoncer la conclusion sous une forme
   FALSIFIABLE (un nombre, un nom, un compte), puis lancer d'abord le contrôle
   qui la ferait TOMBER — jamais celui qui la confirme. Trois conditions de
   recevabilité, avant d'agir ou de l'écrire à Mike :
   **(a) la mesure est-elle FRAÎCHE ?** un canal revenu à `rien`, un
   horodatage, une taille — une sortie lue pendant qu'elle s'écrit répond sur
   le run d'avant ; **(b) ai-je cherché les AUTRES portes ?** (règle n° 8) ;
   **(c) d'où vient ce que je tiens pour acquis ?** une doc, un commentaire,
   un `PROMPT_NOUVELLE_SESSION` disent l'intention DATÉE de leur auteur, pas
   l'état — le 12/09 le plan écrit désignait `index` et un `resolve()` alors
   que la mesure a désigné le parcours, deux fois plus lourd qu'eux réunis.
   *Un résultat qui confirme ce que j'attendais est le moment de vérifier, pas
   celui de conclure.*

## Fichiers

| Fichier | Rôle |
|---|---|
| `server.py` | Monolithe ~12 000 l. : config, stores, pipelines, workers, routeur, 9 pages HTML inline |
| `store_sqlite.py` / `vectors.py` | Persistance SQLite / vecteurs BLOB + cosinus |
| `pilotage.py` / `superviseur.bat` | Arrêt et redémarrage commandés par `_commande_serveur.txt` |
| `journal_serveur.py` | Miroir daté de la console du serveur → `_journal_serveur.log` : ce qui plante se lit à distance |
| `git_agent.py` / `superviseur_git.bat` | Livraison git commandée par `_commande_git.txt`, sous contrôles ; rapport dans `_etat_git.json` |
| `banc_agent.py` / `superviseur_banc.bat` | Lance un BANC sous Windows sur ordre de `_commande_banc.txt` ; sortie dans `_banc_sortie.txt`. Familles qui MESURENT seulement, sans shell ni chemin |
| `canal.py` | Lire et écrire un ordre : les trois canaux, mêmes octets (BOM/CRLF/LF, écriture atomique) |
| `ROADMAP.md` | Priorités — à relire en début de session |
| `PROMPT_NOUVELLE_SESSION.md` | Éphémère : état + prochain pas, réécrit chaque session |
| `eval/DECISIONS.md` | Adopté / rejeté / parké sur la PHOTOTHÈQUE — ne rien reproposer sans le relire |
| `eval/DECISIONS_UI.md` | Idem pour l'ÉCRAN (07/09) : composants, cibles, contraste, ce qu'une grille compte |
| `docs/DECISIONS_OUTILLAGE.md` | Idem pour l'OUTILLAGE : les trois canaux, le pilotage, la livraison git |
| `docs/` | Audits, rangement, `GIT_WORKFLOW.md` (circulation sandbox ↔ machine ↔ GitHub) |

**Skills (`.claude/skills/`)** : `monolith-surgery` avant toute modif de
`server.py` · `photo-ui` dès qu'on touche l'UI · `vision-eval` pour un modèle
ou un seuil.

## Protocole

**« Go »** : **d'abord VÉRIFIER l'état réel, ensuite lire les docs.** Une doc
décrit l'intention de la FIN de session précédente, pas ce que Mike a fait
après — commits, redémarrage, fusion. Lire `.git/HEAD`, `.git/logs/HEAD` et
`.git/logs/refs/heads/main` via staging (lecture seule) : ils disent ce qui est
commité et ce qui est FUSIONNÉ. Annoncer l'écart quand la doc se trompe.
Puis : `ROADMAP.md`, `eval/DECISIONS.md` (+ l'outillage si le sujet y touche,
+ doc de chantier) → débrief
2–3 lignes → attaquer le plus utile (ou faire choisir), plan court avant le
code.

**MESURER** : le banc et ses arguments dans `_commande_banc.txt`, puis LIRE
`_banc_sortie.txt` — la VM n'atteint pas le LAN, un banc qui interroge le
serveur ne tourne QUE par là. Un banc livré sans avoir tourné est une promesse.

**Chaque échange qui fait avancer** : mettre à jour `ROADMAP.md` (statut),
`PROMPT_NOUVELLE_SESSION.md` (réécrit en entier), et le fichier de décisions du
DOMAINE si une éval a tranché. Écrire `SESSION_COMMIT.txt` à la racine (ASCII, sans guillemets ni `!` :
`branche=feat/…`, `titre=…` court, `force=raison` seulement si une preuve est
impossible à produire). Puis **redémarrer, observer en réel**, et seulement
alors écrire `livrer` dans `_commande_git.txt`. VÉRIFIER ensuite dans
`.git/logs/*`, pas dans le rapport de l'agent. Si l'agent refuse, il dit
pourquoi : corriger, ne pas forcer par réflexe. Canal fermé (fenêtre absente)
ou refus non levable → rendre la main à Mike : `27 - Git.bat`, **1** puis **2**.

**Traite autonome (« go », Mike absent)** : livrer avec **`commit`** — branche
+ push, `main` INTACTE : une traite qui dérape se jette en supprimant UNE
branche ; la fusion (`livrer`) attend son retour. Un choix qui lui appartient —
jugement produit, geste irréversible sur l'archive, chiffre qui contredit une
décision écrite — s'écrit dans `QUESTIONS_MIKE.md` avec une recommandation, et
on PASSE au point suivant qui n'en dépend pas. Jamais s'arrêter au premier
caillou ; jamais trancher à sa place.

**Fin de session (systématique)** : docs de suivi cohérentes — **le détail vit
dans git, pas dans les docs : c'est le levier tokens**, et le seuil du lint
(100 000 depuis le 23/08) ne rattrape plus qu'un emballement franc, c'est le
RÔLE de chaque fichier qui le tient court ; `python nettoyer_session.py` (lint propre attendu ;
`--appliquer` ou bat 29 = quarantaine réversible `_corbeille_session/`, rien
n'est supprimé) ; laisser `PROMPT_NOUVELLE_SESSION.md` en amorce lean prête à
coller.

## Méthode

- **Un score parfait est une alarme, pas un succès** (deux bancs du projet ne
  mesuraient pas ce qu'ils prétendaient).
- **Contre-vérifier AVANT de livrer une conclusion** (règle n° 11) : la
  falsifier, pas la confirmer ; prouver la fraîcheur de la mesure ; nommer ce
  qui n'est qu'hérité d'une doc.
- **Une correction n'est acquise qu'une fois son effet observé en réel** — un
  proxy n'est pas le juge, et un banc qui n'a pas tourné n'est pas un banc :
  le 20/08, une conclusion tirée de deux échantillons est tombée dès que le
  banc a tourné en entier.

## Tester en réel

Serveur chez Mike : **192.168.0.13:8080**, via **Claude-in-Chrome**. **Pas de
hot-reload** : toute modif de `server.py` exige un redémarrage.

**LE PONT ÉCRIT PARFOIS LA VERSION PRÉCÉDENTE DU FICHIER.** C'est le défaut
d'outillage le plus coûteux du projet : `device_commit_files` répond
« written » et dépose le contenu du commit d'AVANT. Arrivé une douzaine de fois
les 09 et 10/09, sur des `.md`, des `.py`, un `SESSION_COMMIT.txt` et surtout
les `_commande_*.txt` — un agent exécute alors l'ordre qu'on croyait avoir
remplacé, et on lit le résultat du mauvais banc en croyant lire le sien.
**Parade, systématique** : committer **DEUX FOIS**, puis re-stager et comparer
la TAILLE ; si elle diffère, re-committer. Pour un CANAL (`_commande_*.txt`), y
écrire d'abord `rien`, le committer deux fois, puis l'ordre réel deux fois : un
rejeu périmé écrit alors `rien`, qui ne fait rien. **Diagnostiquer par la
TAILLE, jamais par le symptôme** — le chercher ailleurs coûte trois
allers-retours au lieu d'un.

**Redémarrage par Claude** (`pilotage.py` + `superviseur.bat`) : écrire un mot
dans `_commande_serveur.txt` — `redemarrer`, `arret`, `marche` — via
`device_bash`, **en CRLF** (`printf 'redemarrer\r\n'` : l'autre lecteur est
`cmd.exe`) ; ne jamais le supprimer. Même protocole pour `_commande_git.txt`
(`rien`, `ping`, `commit`, `livrer`) et `_commande_banc.txt` (un banc + ses
arguments). **AVANT** de redémarrer, lire `uptime_s` : sous 60 s quelqu'un vient
de le faire — ne pas se battre avec lui. **APRÈS**, VÉRIFIER
`GET /api/serveur` : `demarre_a` bougé, `code_a_jour` vrai, sinon la mesure
porte sur l'ancien code. Les TROIS fenêtres du bat 0 sont requises (Serveur,
Git, Bancs) ; un agent est vivant si son `_agent_*_vu.txt` a moins de 30 s
(`git_agent.py --etat`), sinon `ping`, et si rien ne répond rendre la main à
Mike. Un redémarrage interrompt tagging et scan.

**Ce que le serveur a raconté se lit à distance** : `_journal_serveur.log`
(miroir daté de sa console, `journal_serveur.py`) — les tracebacks des threads
qui meurent y sont, la console de Mike n'est plus le seul témoin. Depuis le
dernier démarrage : `sed -n '/===== DEMARRAGE/,$p' _journal_serveur.log` sur la
dernière bannière. Plantage dur d'une lib native : `_journal_serveur_crash.log`.
**Le lire AVANT de supposer** — c'est là que se trouve la cause, pas dans une
hypothèse.

**Le NAS, `N:\\Photos`, se CONNECTE à chaque session** (picker « Add folder »
de l'app, non persistant ; UNC et lecteur mappé ingrantables) : demander à Mike
au « Go ». Connecté, il se lit avec `device_list_dir`, se prélève avec
`device_stage_files`, s'écrit avec `device_commit_files` — mais il n'est PAS
monté dans `device_bash` (réseau) : un script sur tout le fonds passe par
l'agent banc (Windows, UNC). Sans lui, aucun regard direct sur les photos.

**Le serveur se regarde avec Claude in Chrome, jamais avec le navigateur intégré**
de l'app : celui-ci traite `192.168.0.13:8080` comme un site « à risque » et
demande une autorisation à Mike À CHAQUE action (29/08). Chrome : une
permission de site, une fois.

Clics/captures : onglet au premier plan ; l'état passe par `fetch('/api/…')`
GET (marche onglet caché) ; GPU : `GET /api/search/status`. Sandbox → disque :
`SendUserFile` puis `device_commit_files`.
