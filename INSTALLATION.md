# Installation & migration vers un nouveau PC

Procédure de bout en bout pour remonter le projet sur une machine neuve — pensée
pour être **fiable, reproductible et largement automatisée**. Trois choses vivent
séparément, et se remontent chacune à leur façon :

| Quoi | Où ça vit | Comment ça se remonte |
|---|---|---|
| **Le code** | dépôt GitHub `TheMikeHoogly/MediaLibrary` | `git clone` |
| **L'état** (index + config) | local, gitignoré | `migrer.py` (archive zip) |
| **L'environnement** (.venv, deps, modèle Ollama) | local | `installer.py` |
| **Les modèles IA** (InsightFace/YOLO/DINOv2/SigLIP) | cache local | re-téléchargés (ou `--prewarm`) |
| **Les noms humains** (`personne:`/`animal:`) | **XMP des fichiers, sur le NAS** | voyagent avec le NAS — rien à faire |

Point important : les **daemons de maintenance** (dédoublonnage, purge…) tournent
**dans le serveur** (threads de fond). Remonter et démarrer le serveur suffit
donc à tout relancer — aucune tâche planifiée Windows à recréer.

## Prérequis à installer à la main (une fois)

Sur le nouveau PC, avant tout :

1. **Python 3.10+** — `winget install Python.Python.3.12`
2. **Ollama** — https://ollama.com (fournit le LLM de tagging)
3. **Git** — `winget install Git.Git`
4. **GPU (PC dédié IA)** — un pilote NVIDIA récent. `installer.py` posera la build
   CUDA de PyTorch ; pas besoin d'installer CUDA séparément.
5. **ExifTool** — le serveur le télécharge tout seul au 1er lancement.

## Procédure

### Sur l'ANCIEN PC (exporter l'état)

1. **Arrête le serveur** (base cohérente).
2. Lance **`Migrer - Exporter (ancien PC).bat`** (ou `python migrer.py exporter`).
   → crée `migration\migration_<PC>_<date>.zip` (index `photos.db` + config).
3. Copie ce zip sur le nouveau PC (clé USB, réseau, NAS…).

### Sur le NOUVEAU PC

1. `git clone https://github.com/TheMikeHoogly/MediaLibrary.git` puis entre dans
   le dossier.
2. **`1 - Installer (nouveau PC).bat`** (ou `python installer.py`). Il détecte le
   GPU (build CUDA, sinon CPU), crée `.venv`, installe les dépendances, tire le
   modèle Ollama, pose les gabarits de config. Il demande si tu veux
   pré-télécharger les modèles (`--prewarm`) et le démarrage auto à l'ouverture de
   session (`--autostart`).
3. **`Migrer - Importer (nouveau PC).bat`** avec le chemin du zip → restaure
   `photos.db` et la config.
4. **Vérifie** : `python installer.py --check` (bilan de santé : deps, torch/CUDA,
   onnxruntime, Ollama, base présente).
5. **Démarre** : `0 - Démarrer le serveur.bat` (ou automatiquement si `--autostart`).
   Ouvre `http://localhost:8080`.

## Réglages utiles

- **Forcer le moteur** : `python installer.py --gpu` ou `--cpu`.
- **NAS différent** : si les chemins UNC changent, édite `dossier_uploads.txt`,
  `dossiers_a_taguer.txt`, `dossiers_a_explorer.txt`, `data_dir.txt` (un chemin
  par ligne). Sinon l'archive migrée les apporte déjà.
- **Modèle de tagging** : `modele.txt` (défaut `qwen3-vl:2b`).
- **Couper la maintenance auto** : `MAINTENANCE_AUTO = False` en tête de
  `server.py`.

## En cas de souci

- `installer.py --check` dit ce qui manque, ligne par ligne.
- GPU non vu par PyTorch → pilote NVIDIA à jour, ou repli `--cpu` (tout marche,
  plus lent).
- Modèle Ollama absent → `ollama pull qwen3-vl:2b`.
- Un `.bat` qui « saute des étapes » → `python verifier_bat.py` (les `.bat`
  doivent rester en ASCII pur).
