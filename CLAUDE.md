# MediaLibrary — brief projet

> Dépôt GitHub privé `TheMikeHoogly/MediaLibrary` (ex-« MobileFileTransfer »).
> Le nom du dossier local est sans effet : tous les chemins sont relatifs à `SCRIPT_DIR`.

Fichier lu automatiquement au début de chaque session. Le strict nécessaire ; le
détail vit dans les skills (`.claude/skills/`) et les docs listés plus bas.

## Ce que c'est

Serveur photo local en **Python stdlib pure** (`http.server`), servi au téléphone
sur le réseau domestique. Indexe ~30 000 photos familiales sur un NAS SMB et y
applique cinq pipelines d'IA locale :

| Pipeline | Modèle | Sortie |
|---|---|---|
| Tagging | `qwen3-vl:2b` (Ollama) | mots-clés FR/EN + description |
| Visages | InsightFace `buffalo_l` | détection + embeddings 512-d |
| Animaux | YOLO11s | détection d'espèce |
| Chats nommés | DINOv2 base | embeddings 768-d + regroupement |
| Recherche sémantique | SigLIP 2 (`semantic.py`) | embeddings image/texte + tags vocabulaire |

Les noms attribués (`personne:Nom`, `animal:Nom`) sont écrits dans les **XMP des
fichiers** (exiftool) : ils survivent à la base. **Matériel : RTX 3050 Laptop, 4 Go
VRAM** — la contrainte qui filtre toutes les décisions techniques.

## Règles absolues

1. **`.bat` en ASCII PUR.** `cmd.exe` relit le fichier par décalage d'octets ; un
   seul caractère multi-octets désaligne le curseur et fait sauter des étapes
   silencieusement. Interdits dans le contenu (même en `REM`) : accents, `« »`,
   `─ ═ → ✓ ✗ ⚠`, emoji. Écrire sans accents (`arrete`, `deja`). Contrôle avant
   livraison, et **lire sa sortie** : `python verifier_bat.py`. (Hook `PostToolUse`
   qui bloque à l'écriture.) Déjà commise 2×.
2. **Les noms humains ne se perdent jamais.** Toute migration les préserve (modèle
   `migrate_animal_pipeline()`). Un changement qui risque d'en perdre un est faux,
   quel que soit son gain.
3. **Zéro dépendance au démarrage.** Imports lourds (`numpy`, `torch`, `insightface`,
   `ultralytics`) **paresseux, dans les fonctions**. Côté client : ni npm, ni bundler,
   ni framework.
4. **SQLite en local, jamais sur le NAS.** `photos.db` dans le dossier du script (WAL).
   SQLite sur SMB = corruption. Sauvegarde NAS par snapshot atomique (`backup_db()`).
   Ne pas ouvrir `photos.db` depuis le sandbox Linux : le serveur est l'écrivain unique
   — les tests copient la base d'abord.

## Architecture des fichiers

| Fichier | Rôle |
|---|---|
| `server.py` | Monolithe (~12 000 l.) : config, stores, pipelines, workers, routeur, 9 pages HTML inline (7 historiques + `/reglages` + `/sujets`) |
| `store_sqlite.py` / `vectors.py` | Persistance SQLite (`TagStore`) / magasin de vecteurs BLOB + cosinus |
| `ROADMAP.md` | **Où en est le projet, ce qui reste — à relire en début de session** |
| `PROMPT_NOUVELLE_SESSION.md` | Amorce de reprise (état + prochain pas) |
| `eval/DECISIONS.md` | Décisions tranchées : adopté / rejeté / parké — pour ne rien re-proposer |
| `docs/AUDIT_EXTERNE_2026.md` | Direction tagging (LLM = raisonnement sur assertions, pas pixels) |
| `docs/RANGEMENT_2026.md` | Rangement / dédoublonnage / renommage : état de référence |
| `docs/GIT_WORKFLOW.md` | Circulation du code sandbox ↔ machine ↔ GitHub |

## Skills (`.claude/skills/`) — charger selon la tâche

- **`monolith-surgery`** — avant toute modif de `server.py`. Invariants, navigation par grep.
- **`photo-ui`** — dès qu'une page/CSS/JS d'interface est touché. Tokens, a11y, zéro-build.
- **`vision-eval`** — dès qu'on change/compare/teste un modèle ou ajuste un seuil.

## Protocole de session (« Go ») et tenue des docs

L'état vit dans les **fichiers**, pas dans l'historique de conversation : sessions
courtes et fraîches, on repart des fichiers de suivi. C'est le vrai levier tokens.

**Quand Mike écrit « Go » :**
1. Lire `ROADMAP.md` puis `eval/DECISIONS.md` (+ le doc de chantier pertinent selon le sujet).
2. Débrief bref (2–3 lignes : où on en est) + prochaines étapes par ordre de valeur.
3. Attaquer la plus utile (ou faire choisir), plan court avant d'écrire du code.

**À la fin de chaque échange qui fait avancer :** mettre à jour `ROADMAP.md`
(statut), `PROMPT_NOUVELLE_SESSION.md` (reprise), `eval/DECISIONS.md` (si une éval a
tranché). C'est ce qui rend les sessions courtes sûres. **Toujours proposer à Mike un
titre de commit** (court, français, style git du dépôt) pour la session — le commit et
`git push` restent des gestes de Mike.

**Préparer une nouvelle discussion (dès que l'échange devient long) — systématique :**
mettre à jour + **condenser** les docs de suivi sous les seuils du lint (`ROADMAP.md`,
`PROMPT_NOUVELLE_SESSION.md` : le détail vit dans git, pas dans les docs — c'est le levier
tokens), vérifier `python nettoyer_session.py` (lint propre attendu), et laisser
`PROMPT_NOUVELLE_SESSION.md` comme **amorce lean prête à coller**. ⚠ Éviter `git` via
`device_bash` sur le dossier monté : chaque appel laisse un `.git/index.lock` que la VM ne
peut pas supprimer et qui bloquerait le commit de Mike.

**Nettoyage de fin de session (systématique) :** lancer `29 - Nettoyage de
session.bat` (ou `python nettoyer_session.py --appliquer`). Deux volets sûrs :
(1) met en **quarantaine réversible** les répertoires/fichiers de travail
éphémères de la racine (dossiers `--…`, `__pycache__`, `.fuse_hidden…`, `.pyc`,
dossiers vides connus) dans `_corbeille_session/AAAA-MM-JJ/` avec `manifest.json`
— rien n'est supprimé, Mike vide la corbeille quand il est sûr ; (2) **lint de
cohérence** des `*.md` de suivi (références orphelines, bloat, dates périmées) —
informatif, à corriger à la main. Liste blanche stricte : `_bat_archive`,
`recuperees`, `*_thumbs`, `docs`, `ui`, `eval`, `uploads`, `.git`, `.venv` et
tous les fichiers source/données sont **préservés**.

## Deux réflexes de méthode

- **Un score parfait est une alarme, pas un succès** — deux bancs de ce projet ne
  mesuraient pas ce qu'ils prétendaient (l'un circulaire, l'autre inéquitable).
- **Une correction n'est acquise qu'une fois son effet observé en réel** — trois
  diagnostics ont été justes sans traiter la vraie cause ; un proxy n'est pas le juge.

## Tester en réel

Serveur chez Mike : **192.168.0.13:8080**. Utiliser **Claude-in-Chrome** (naviguer,
`fetch('/api/…')` GET pour vérifier l'état). Le serveur **ne recharge pas à chaud** :
une modif de `server.py` n'est active qu'après redémarrage (`0 - Démarrer le serveur.bat`).
`git push` / merges dans `main` = **gestes de Mike** (cf. `docs/GIT_WORKFLOW.md`).
⚠ Claude-in-Chrome : les clics/captures ne marchent que si l'onglet est **au premier plan**.
Matériel : `FACE_USE_GPU=False` **volontaire** (4 Go VRAM pris par Ollama résident).
