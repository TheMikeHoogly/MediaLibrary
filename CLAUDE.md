# MediaLibrary — brief projet

> Projet renommé « MediaLibrary » (ex-« MobileFileTransfer »). Dépôt GitHub
> privé : `TheMikeHoogly/MediaLibrary`. Le nom du dossier local peut différer,
> sans effet : tous les chemins du code sont relatifs à `SCRIPT_DIR`.

Ce fichier est lu automatiquement au début de chaque session. Il contient le
strict nécessaire ; les règles détaillées vivent dans les skills, listées plus bas.

## Ce qu'est ce projet

Serveur photo local en **Python stdlib pure** (`http.server`), servi au téléphone
sur le réseau domestique. Il indexe un fonds familial d'environ 30 000 photos
stocké sur un NAS SMB, et y applique quatre pipelines d'IA locale :

| Pipeline | Modèle | Sortie |
|---|---|---|
| Tagging | `qwen3-vl:2b` via Ollama | mots-clés FR/EN + description |
| Visages | InsightFace `buffalo_l` (ArcFace) | détection + embeddings 512-d |
| Animaux | YOLO11s | détection d'espèce |
| Chats nommés | DINOv2 base | embeddings 768-d + regroupement |

Les noms attribués (`personne:Nom`, `animal:Nom`) sont écrits dans les
**métadonnées XMP des fichiers** via exiftool : le travail survit à l'application.

Matériel : **RTX 3050 Laptop, 4 Go de VRAM**. C'est la contrainte qui filtre
toutes les décisions techniques.

## Règles absolues

### 1. Les fichiers `.bat` sont en ASCII PUR

`cmd.exe` relit le fichier par **décalage d'octets** après chaque commande. Un
seul caractère UTF-8 multi-octets désaligne son curseur : il exécute alors des
fragments de lignes (`'nir'`, `'e.py'`, `'Contenu'`) et **saute silencieusement
des étapes, y compris des vérifications**.

Interdits dans le contenu, y compris en commentaire `REM` : accents, `«` `»`,
`─` `═`, `→`, `✓` `✗` `⚠`, emoji. Utiliser `=` et `-` comme séparateurs, `"`
pour citer, et écrire sans accents (`arrete`, `deja`, `verifie`). Le *nom* du
fichier peut être accentué ; seul le contenu est relu par le parseur.

Contrôle obligatoire avant livraison — et **lire réellement sa sortie** :

```bash
python verifier_bat.py
```

Cette erreur a déjà été commise deux fois. Un hook `PostToolUse` la bloque
désormais à l'écriture (voir `.claude/settings.json`).

### 2. Les noms attribués par un humain ne se perdent jamais

Toute migration doit les préserver, sur le modèle de `migrate_animal_pipeline()`
qui relance détection et empreintes mais conserve les noms. Un changement qui
risque d'en perdre un est faux, quel que soit son gain par ailleurs.

### 3. Zéro dépendance au démarrage

Les imports lourds (`numpy`, `torch`, `insightface`, `ultralytics`) sont
**paresseux, dans les fonctions**. Le serveur doit démarrer et servir ses pages
sans eux. Ne jamais les remonter en tête de fichier. Côté client : ni npm, ni
bundler, ni framework.

### 4. La base SQLite vit en local, jamais sur le NAS

`photos.db` est dans le dossier du script (WAL activé). SQLite sur SMB a un
verrouillage non fiable et pas de WAL — c'est le scénario de corruption. La
sauvegarde part sur le NAS par snapshot atomique (`backup_db()` dans
`maintenance_loop`).

## Architecture des fichiers

| Fichier | Rôle |
|---|---|
| `server.py` | Monolithe : config, stores, pipelines, workers, routeur, 7 pages HTML inline |
| `store_sqlite.py` | Persistance SQLite compatible `TagStore` — écriture incrémentale |
| `vectors.py` | Magasin de vecteurs BLOB + recherche cosinus numpy |
| `migrate_to_sqlite.py` | JSON → SQLite, vérifié et réversible |
| `migrate_embeddings.py` | Embeddings hors JSON → table BLOB |
| `ROADMAP.md` | **Où en est le projet, ce qui reste — à relire en début de session** |
| `eval/DECISIONS.md` | Journal des évaluations : ce qui a été adopté, et ce qui a été rejeté sur mesure |
| `docs/AUDIT_2026.md` | État de l'art, dette technique, roadmap initiale |
| `ui/prototype.html` | Direction visuelle « chambre noire » |

## Skills du projet — à charger selon la tâche

Elles sont dans `.claude/skills/` et se déclenchent sur description. En cas de
doute, les lire explicitement :

- **`photo-ui`** — dès qu'une page, du CSS ou du JS d'interface est touché.
  Tokens de couleur et de typographie, composants, plancher d'accessibilité,
  interdiction du build step.
- **`vision-eval`** — dès qu'il est question de changer, comparer ou tester un
  modèle, ou d'ajuster un seuil. Impose un jeu de validation issu du corpus
  réel, une mesure de VRAM et une décision écrite.
- **`monolith-surgery`** — avant toute modification de `server.py`. Invariants,
  repères de navigation dans les 7 500 lignes, règle ASCII des `.bat`.

## Reprendre le projet dans une nouvelle conversation

Tout ce qu'il faut savoir est dans les fichiers, pas dans l'historique. L'ordre
de lecture :

1. **`ROADMAP.md`** — ce qui est fait, ce qui reste, par ordre de valeur.
2. **`eval/DECISIONS.md`** — les idées déjà **rejetées sur mesure**. Le relire
   évite de reproposer MegaDescriptor, les contre-exemples ou `sqlite-vec`,
   tous écartés chiffres à l'appui.
3. **`docs/AUDIT_EXTERNE_2026.md`** — la direction en cours (le LLM comme
   moteur de raisonnement sur des assertions, pas sur les pixels) et le
   séquencement décidé. Le banc associé : `eval/PLAN_assertions_vs_pixels.md`
   + `eval_tagging.py`.
4. Les trois skills de `.claude/skills/` selon la tâche.

Une phrase suffit pour démarrer : « Lis ROADMAP.md et DECISIONS.md, puis
attaque le point N. »

**Deux réflexes à garder.** Un score parfait est un signal d'alarme, pas un
succès : deux bancs d'essai de ce projet ne mesuraient pas ce qu'ils
prétendaient. Et une correction n'est pas acquise tant que son effet n'a pas
été observé — trois diagnostics successifs ont été justes sans traiter la vraie
cause.

## État connu du système

- **Le GPU n'est utilisé que par Ollama.** `torch` installé est la build CPU
  (`2.13.0+cpu`, `cuda = None`) et un dossier `~orch` orphelin traîne dans le
  venv, vestige d'une désinstallation pip interrompue. YOLO, DINOv2 et
  InsightFace tournent donc tous sur CPU, et les seuils `*_GPU_MIN_FREE_MB`
  sont sans effet. Les erreurs `cublasLt64_13.dll introuvable` au démarrage
  viennent de là — elles sont bénignes (repli `CPUExecutionProvider`).
- Migration SQLite : faite et vérifiée (64 676 entrées, 318 personnes, 9 chats).
- Sortie des embeddings : script prêt, validé sur copie de la base réelle.
