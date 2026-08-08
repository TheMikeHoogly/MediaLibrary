# Prompt de démarrage — à coller dans une nouvelle conversation

> Copie tout le bloc ci-dessous dans une nouvelle conversation Cowork, après
> avoir connecté le dossier `C:\Prog\Claude\MediaLibrary`.
>
> Dernière mise à jour : **8 août 2026** (session « ménage » : audit `.bat`, UI
> renommage, optimisation tagging, diagnostic GPU/RAM, item Mutz, ROADMAP réécrite).

---

Tu reprends le projet **MediaLibrary** — photothèque familiale locale à IA
(~30 000 photos sur NAS, serveur Python stdlib pur, pipelines Ollama/InsightFace/
YOLO/DINOv2, RTX 3050 4 Go). Dossier : `C:\Prog\Claude\MediaLibrary`. Tout
l'état vit dans les fichiers, pas dans l'historique de conversation.

**Lis d'abord, dans l'ordre :** `CLAUDE.md` (règles absolues) → `ROADMAP.md`
(carte des priorités, réécrite au propre le 08/08 — « À faire, par ordre de
valeur ») → `eval/DECISIONS.md` (idées déjà **rejetées sur mesure** :
MegaDescriptor, contre-exemples, `sqlite-vec`, injection des noms au prompt,
détecteur ML de triage) → selon le sujet : `docs/RANGEMENT_2026.md`,
`docs/AUDIT_EXTERNE_2026.md`, et les skills `.claude/skills/` (`monolith-surgery`
**avant tout edit de `server.py`**, `photo-ui` pour l'UI, `vision-eval` pour un
seuil/modèle).

## Garde-fous à ne jamais oublier

- **Les noms attribués par un humain (`personne:` / `animal:`) ne se perdent
  jamais.** Ils vivent dans les XMP des fichiers. Tout déplacement/renommage
  passe par `rekey_everywhere` (transporte tags + visages/personnes/animaux +
  vecteur sémantique).
- **Ne pas ouvrir `photos.db` (WAL) depuis le sandbox Linux** — le serveur (sur
  la machine de Mike) est l'écrivain unique. Les tests qui touchent la vraie base
  la **copient** d'abord. Conséquence : la logique risquée vit dans des **modules
  purs** testables hors machine (`fichiers.py`, `renommage.py`, `interet.py`,
  `tagging_meta.py`…) + `test_*.py`. `server.py` ouvre les stores au niveau module
  → **ne pas l'importer** dans un test du sandbox.
- **Un score parfait est une alarme, un proxy n'est pas le juge.** Vérifier
  l'**effet réel** d'une correction (la notation humaine a renversé « V2 ≈ V0 » ;
  trois diagnostics ont été justes sans traiter la vraie cause).
- **Zéro dépendance au démarrage** (imports lourds paresseux) ; côté client,
  **zéro build, zéro npm**.
- **`server.py` fait ~9 400 lignes.** Charge `monolith-surgery` avant d'y toucher.
  Toute modif risquée passe par une **branche**. Garde-fous : `python
  verifier_ui_tokens.py` (0 interdit dur) pour l'UI, `python verifier_bat.py`
  (**ASCII pur**, lire sa sortie) pour les `.bat`, `py_compile` + `test_*.py`.

## Outillage (ce qui marche)

- **Git** marche dans le shell (`origin = TheMikeHoogly/MediaLibrary`). Commits au
  fil de l'eau sur une branche. Si un verrou périmé bloque (`.git/*.lock`), demander
  une fois `mcp__cowork__allow_cowork_file_delete` puis `rm -f .git/*.lock`.
  **`git push` et les merges dans `main` sont des gestes de Mike** (le sandbox ne
  pousse pas ; et merger en local échoue tant que le serveur verrouille `server.py`
  — préférer éditer en place sur une branche, puis Mike pousse/merge). Éditer un
  fichier ouvert par le serveur marche (écriture en place), mais **un `git checkout`
  qui doit réécrire `server.py` échoue** → faire avancer un ref par `update-ref` +
  `git reset` si besoin (cf. session 07/08).
- **Tester en RÉEL le site** : le serveur tourne chez Mike (**192.168.0.13:8080**).
  Utiliser **Claude-in-Chrome** (`mcp__claude-in-chrome__*`) pour naviguer,
  screenshoter, exécuter du JS de diagnostic (`fetch('/api/...')`, aller-retours
  réversibles sur les vraies données). C'est ce qui a trouvé des bugs que les
  maquettes cachaient. **Le serveur ne recharge pas le code à chaud** : une modif de
  `server.py` n'est active qu'après un **redémarrage** (`0 - Démarrer le serveur.bat`).
- **Computer-use** (`mcp__computer-use__*`) disponible pour lire l'écran de Mike
  (ex. Gestionnaire des tâches pour la RAM). `request_access` d'abord.
- **Avancer en autonomie** : quand Mike dit « continue », il n'est souvent pas au
  PC — avancer sans question bloquante, décisions raisonnables, aller au bout.
- **Connecteurs** : Figma connecté. Les autres (Slack, Notion…) demandent un OAuth
  côté claude.ai. Pour un besoin externe ponctuel (ex. géocodage inverse des GPS),
  chercher d'abord au **registre MCP** avant d'écrire du code jetable.
- **Multi-appareils (Dispatch)** : Mike peut piloter depuis téléphone ou PC, mais le
  travail s'exécute **sur le PC** (mêmes fichiers, même serveur). PC allumé + Claude
  Desktop ouvert + dossier connecté requis.

## ══ ÉTAT AU 8 AOÛT 2026 — LIRE EN PREMIER ══

### Branches

- **`main` == `origin/main`**, poussé et à jour. Porte tout l'intégré, dont les
  deux correctifs du 07/08 (rejet de groupe `/pets`, curateur faux-positifs
  `/people`).
- **`feat/menage-ui-gpu-0807`** — **poussée sur `origin`** (branche de suivi créée),
  **pas encore mergée dans `main`**, **exécutée par le serveur** (Mike a redémarré
  dessus). Contient la session ménage :
  - **Archivage de 22 `.bat`** obsolètes/dangereux dans `_bat_archive/` (réversible,
    README). Neutralisés : `2 - Installer et nettoyer` (tirait `qwen3-vl:4b` +
    supprimait `gemma4:e2b`) et `13 - Reparer le GPU` (re-cassait le GPU réparé).
  - **`/reglages` : bloc « Renommage intelligent » numéroté** (4 étapes) + message
    persistant. **Validé en réel.**
  - **Tagging : 1 seule lecture exiftool/photo** (tags+desc+GPS combinés). Module pur
    `tagging_meta.py` + `test_tagging_meta.py` **15/15**, invariant noms préservé.
    **RESTE : valider en réel après un redémarrage** — mesurer le débit tag/min
    avant/après pour chiffrer le gain.
  - **`CLAUDE.md` corrigé** : torch est bien **CUDA** `2.13.0+cu130` (l'ancienne
    mention « build CPU » était périmée).
  - **ROADMAP.md réécrite** (886 → 183 lignes), ordonnée par valeur, historique
    condensé (le détail reste dans git + `eval/DECISIONS.md`).
- **Fin de session** : `27 - Commit de session.bat` (branche + add + commit + push,
  ASCII pur) ; Claude met à jour ROADMAP.md + ce fichier.

### Diagnostic GPU / RAM (08/08, mesuré — pas de bug de device)

Le GPU **fait** le tagging (Ollama résident ~3,5 Go, util en **rafales ~91 %**). Le
frein n'est pas la sélection de device mais : **(1) la RAM** — machine chargée, RAM
libre ~1,4 Go proche du plancher `REEMBED_MIN_RAM_GB=1.5` qui déclenche l'auto-bridage
(`system_busy`) ; le serveur lui-même est sain (~1,95 Go), le reste est Claude Desktop
(~1 Go), Chrome, Defender, apps de fond. **(2) l'I/O NAS** par photo (~20 s hors-GPU).
Levier sans code : **fermer les apps de fond** pendant un gros run. Sur 4 Go partagés,
Ollama + vision ne tiennent pas ensemble sur le GPU → `FACE_USE_GPU=False` volontaire.

### Prochain pas (détail et ordre complet dans `ROADMAP.md`)

Gestes **humains** à Mike, prêts :
1. **Confirmer ~100 propositions de visages** dans `/people` (priorité n°1, vérité
   terrain à 0,8 %, tri clavier prêt).
2. **Mutz** : sur son groupe de « visages » dans `/people`, cliquer **« Rejeter le
   groupe »** (réversible ; il reste dans Animaux). Cause = pas de garde humain/animal
   + `FACE_DET_THRESHOLD=0.50`. Voir **ROADMAP item 2** (action explicite « c'est un
   animal/une personne » à ajouter + garde SigLIP amont 12b à mesurer).
3. **Appliquer les lots de renommage** : `/reglages` → « Renommage intelligent »
   (Générer → Vérifier à blanc → Appliquer un lot ×N → Annuler). Plan = **2114**.
4. **Redémarrer le serveur** pour activer l'optimisation tagging, puis demander la
   mesure du gain.

Prochains **code** utiles (par valeur, cf. ROADMAP) : action cross-pipeline
personne/animal (item 2) ; garde SigLIP humain/animal 12b (`vision-eval`) ; redesign
étape B (centre de tâches, registre papier) ; page « Sujets » unifiée ; algo
(HDBSCAN, AdaFace) ; géocodage inverse des 684 GPS (enrichit renommage + carte).

Après lecture : dis **« Go »** pour un débrief + prochaines étapes (protocole
`CLAUDE.md`), ou attaque directement le point le plus utile en proposant un plan
court avant d'écrire du code.
