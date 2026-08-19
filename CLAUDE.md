# MediaLibrary — brief projet

> Dépôt GitHub privé `TheMikeHoogly/MediaLibrary`. Tous les chemins sont relatifs
> à `SCRIPT_DIR`. Lu à chaque session : **invariants seulement**. État courant →
> `ROADMAP.md` ; reprise → `PROMPT_NOUVELLE_SESSION.md` ; détail → skills et docs.

## Ce que c'est

Photothèque familiale locale : serveur **Python stdlib pur** (`http.server`) sur
le réseau domestique, ~30 000 photos sur NAS SMB, 5 pipelines d'IA locale —
tagging `qwen3-vl:2b` (Ollama), visages InsightFace `buffalo_l` (512-d), animaux
YOLO11s, individus animaux DINOv2 (768-d), recherche sémantique SigLIP 2
(`semantic.py`). Les noms attribués (`personne:Nom`, `animal:Nom`) sont écrits
dans les **XMP des fichiers** (exiftool) : ils survivent à la base.
**Matériel : RTX 3050 Laptop, 4 Go VRAM** — la contrainte qui filtre toutes les
décisions techniques. `FACE_USE_GPU=False` **volontaire** (VRAM prise par Ollama).

## Règles absolues

1. **`.bat` en ASCII PUR.** `cmd.exe` relit le fichier par décalage d'octets : un
   seul caractère multi-octets fait sauter des étapes en silence. Interdits même
   en `REM` : accents, `« »`, `─ → ✓ ⚠`, emoji. Contrôle avant livraison et
   **lire sa sortie** : `python verifier_bat.py` (+ hook PostToolUse). Déjà
   commise 2×.
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
5. **Git = gestes de Mike, exclusivement.** Claude ne touche jamais à git : ni
   outil de plugin/MCP, ni `git` via `device_bash` (chaque appel laisse un
   `.git/index.lock` que la VM ne peut pas supprimer). Lire l'état :
   `.git/HEAD` (branche courante), `.git/logs/HEAD` (commits) et
   `.git/logs/refs/heads/main` (**fusions** — le choix 2 fusionne sans
   checkout, donc rien n'en paraît dans `logs/HEAD`) via staging — lecture
   seule, aucun verrou.

## Fichiers

| Fichier | Rôle |
|---|---|
| `server.py` | Monolithe ~12 000 l. : config, stores, pipelines, workers, routeur, 9 pages HTML inline |
| `store_sqlite.py` / `vectors.py` | Persistance SQLite / vecteurs BLOB + cosinus |
| `ROADMAP.md` | Priorités — à relire en début de session |
| `PROMPT_NOUVELLE_SESSION.md` | Éphémère : état + prochain pas, réécrit chaque session |
| `eval/DECISIONS.md` | Adopté / rejeté / parké — ne rien reproposer sans le relire |
| `docs/` | Audits, rangement, `GIT_WORKFLOW.md` (circulation sandbox ↔ machine ↔ GitHub) |

**Skills (`.claude/skills/`)** : `monolith-surgery` avant toute modif de
`server.py` · `photo-ui` dès qu'on touche l'UI · `vision-eval` dès qu'on
change/teste un modèle ou un seuil.

## Protocole

**« Go »** : **d'abord VÉRIFIER l'état réel, ensuite lire les docs.** Une doc
décrit l'intention de la FIN de session précédente, pas ce que Mike a fait
après — commits, redémarrage, fusion. Lire `.git/HEAD`, `.git/logs/HEAD` et
`.git/logs/refs/heads/main` via staging (lecture seule) : ils disent ce qui est
commité et ce qui est FUSIONNÉ. Annoncer l'écart quand la doc se trompe.
Puis : `ROADMAP.md`, `eval/DECISIONS.md` (+ doc de chantier du sujet) → débrief
2–3 lignes → attaquer le plus utile (ou faire choisir), plan court avant le
code.

**Chaque échange qui fait avancer** : mettre à jour `ROADMAP.md` (statut),
`PROMPT_NOUVELLE_SESSION.md` (réécrit en entier), `eval/DECISIONS.md` (si une
éval a tranché). Écrire `SESSION_COMMIT.txt` à la racine (ASCII, sans guillemets
ni `!`, 2 lignes : `branche=feat/…`, `titre=…` court) — `27 - Git.bat`,
**choix 1**, le consomme. Tout git passe par ce bat unique (état + conseil,
commit, **redémarrage du serveur**, fusion, branches, GitHub) : donner à Mike
les gestes dans l'ordre (**1**, puis **7**, puis **2** après validation en
réel) — commit, push et redémarrage restent ses gestes.

**Fin de session (systématique)** : condenser les docs de suivi sous les seuils
du lint — **le détail vit dans git, pas dans les docs : c'est le levier tokens** ;
`python nettoyer_session.py` (lint propre attendu ; `--appliquer` ou bat 29 =
quarantaine réversible `_corbeille_session/`, rien n'est supprimé) ; laisser
`PROMPT_NOUVELLE_SESSION.md` en amorce lean prête à coller.

## Méthode

- **Un score parfait est une alarme, pas un succès** (deux bancs du projet ne
  mesuraient pas ce qu'ils prétendaient).
- **Une correction n'est acquise qu'une fois son effet observé en réel** — un
  proxy n'est pas le juge.

## Tester en réel

Serveur chez Mike : **192.168.0.13:8080**, via **Claude-in-Chrome**. **Pas de
hot-reload** : toute modif de `server.py` exige un redémarrage — geste Mike,
`27 - Git.bat` choix 7 (proposé d'office après un commit qui touche un `.py`). Clics/captures : onglet au premier
plan obligatoire ; l'état passe par `fetch('/api/…')` GET (marche onglet caché) ;
GPU/ordonnanceur : `GET /api/search/status`. Livraison sandbox → disque :
`SendUserFile` puis `device_commit_files`. Tests :
`python test_ordonnanceur.py` (27 vérifications).
