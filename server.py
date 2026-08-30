#!/usr/bin/env python3
"""
Photo Upload Server v10 — upload WiFi + tagging IA local.
- Upload depuis le téléphone : http://<ip-du-pc>:8080
- Chaque photo est analysée par Ollama (qwen3-vl:4b) en arrière-plan :
  mots-clés FR + EN écrits DANS le fichier (XMP/IPTC via ExifTool)
  et dans un index (tags_index.json) pour la galerie.
- Galerie filtrable par mots-clés combinables (ET/OU).

Run: python server.py [dossier_uploads]
"""

import base64
import copy
import hashlib
import html
import io
import json
import os
import queue
import random
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── Une sortie REDIRIGÉE ne doit pas tuer l'import ───────────────────────────
# Windows : quand stdout est une CONSOLE, Python encode dans la page de code du
# terminal et les pictogrammes des messages de démarrage passent. Quand stdout
# est un TUYAU ou un FICHIER (`python eval_tagging.py > sortie.txt`, un outil
# qui capture, un test), Python retombe sur cp1252 et le premier « 🗄 » lève
# UnicodeEncodeError — À L'IMPORT, donc avant toute ligne utile. L'outil meurt
# sur un glyphe décoratif.
# On ne change pas l'encodage (ce serait du mojibake dans une console cp850) :
# on change seulement la POLITIQUE D'ERREUR. Un caractère non représentable
# devient « ? » et le programme continue. Le message compte, pas l'icône.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(errors='replace')
    except (AttributeError, ValueError, OSError):
        pass                       # flux remplacé par un objet sans reconfigure

# ────────────────────────── Config ──────────────────────────

PORT = 8080
OLLAMA_URL = "http://localhost:11434"
MODEL = "qwen3-vl:2b"
# Le modèle peut être changé sans toucher au code : fichier modele.txt
try:
    for _line in (Path(__file__).resolve().parent / "modele.txt").read_text(
            encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#'):
            MODEL = _line
            break
except OSError:
    pass
MAX_IMAGE_SIDE = 896           # redimensionnement avant envoi à l'IA
SCRIPT_DIR = Path(__file__).resolve().parent

# ─── Le journal du serveur ────────────────────────────────────────────────────
# Tout ce que ce fichier raconte va dans une fenêtre `cmd.exe` — chez Mike, et
# nulle part ailleurs. Un thread qui meurt la nuit n'y laisse rien qu'un
# traceback que personne ne lira, et diagnostiquer à distance coûtait un
# aller-retour humain. Le miroir garde la console INTACTE et écrit la même
# chose, datée, dans `_journal_serveur.log`.
# Sous `if __name__` : un banc qui importerait ce fichier ne doit pas se
# retrouver avec ses `print` détournés — ni créer un journal en passant.
if __name__ == '__main__':
    try:
        import journal_serveur
        journal_serveur.installer(SCRIPT_DIR / '_journal_serveur.log',
                                  source=__file__)
    except Exception as _e:                                   # noqa: BLE001
        print(f"  ! journal du serveur indisponible ({_e}) — la console reste "
              f"la seule trace.")

# ── De quand date ce processus, et fait-il tourner le code du disque ? ───────
# Sans hot-reload, la question « le serveur exécute-t-il ce que je viens
# d'écrire ? » n'avait aucune réponse observable : on redémarrait, et on
# croyait. On fige donc ici l'instant du démarrage ET le mtime de `server.py`
# AU MOMENT OÙ IL A ÉTÉ CHARGÉ. Comparé au mtime actuel, il répond seul :
# `/api/serveur` rend `code_a_jour`. Un redémarrage oublié cesse d'être
# indétectable.
DEMARRE_A = time.time()
try:
    SERVER_PY_MTIME = Path(__file__).resolve().stat().st_mtime
except OSError:
    SERVER_PY_MTIME = None

# ── Emplacement des INDEX (tags / visages / personnes) ───────────────────────
# NE PAS déplacer sans copier les .json d'abord : sinon tout le travail accumulé
# est perdu (les visages/personnes ne sont PAS stockés dans les photos). Reste
# sur le dossier historique. Modifiable via data_dir.txt seulement si tu as
# déplacé les .json toi-même.
DATA_DIR = Path(r"\\nas-bremblens\home\Uploads")
try:
    for _l in (SCRIPT_DIR / "data_dir.txt").read_text(encoding='utf-8').splitlines():
        _l = _l.strip()
        if _l and not _l.startswith('#'):
            DATA_DIR = Path(_l)
            break
except OSError:
    pass

# ── Dossier des UPLOADS depuis le téléphone (librement modifiable) ────────────
# Priorité : argument ligne de commande > dossier_uploads.txt > défaut (= DATA_DIR).
# `server` est IMPORTÉ par des outils qui ont leurs propres drapeaux
# (`eval_tagging.py --depouiller`, `mesure_repasse.py --limit 50`) : sans ce
# garde, `argv[1] = "--depouiller"` devient un UPLOAD_DIR relatif et muet, et
# `_creer_dossier_si_absolu` doit refuser un dossier nommé « --depouiller ».
# Un chemin ne commence jamais par « - » : seul un drapeau le fait.
_argv_dir = sys.argv[1] if len(sys.argv) > 1 else ''
UPLOAD_DIR = None
if _argv_dir and not _argv_dir.startswith('-'):
    UPLOAD_DIR = Path(_argv_dir)
else:
    try:
        for _l in (SCRIPT_DIR / "dossier_uploads.txt").read_text(encoding='utf-8').splitlines():
            _l = _l.strip()
            if _l and not _l.startswith('#'):
                UPLOAD_DIR = Path(_l)
                break
    except OSError:
        pass
if UPLOAD_DIR is None:
    UPLOAD_DIR = DATA_DIR

def _creer_dossier_si_absolu(p, quoi):
    """`mkdir` SEULEMENT si le chemin est absolu POUR LA PLATEFORME COURANTE.

    Ces deux créations sont des EFFETS DE BORD À L'IMPORT : un simple
    `import server` (un test, une relecture, un outil) suffit à les déclencher.
    Sous Windows, « \\\\nas-bremblens\\home\\Uploads » est un chemin UNC et tout
    va bien. Sous POSIX (VM du pont, sandbox, CI), l'antislash est un caractère
    ORDINAIRE : la même ligne fabrique, dans le dossier du projet, un répertoire
    dont le NOM contient des antislashs. Windows relit ensuite ce nom comme un
    chemin UNC — et le 14/08 c'est exactement ce qui a fait disparaître ExifTool :
    le parcours de `ensure_exiftool` quittait le disque local pour interroger le
    NAS, l'OSError était avalée, et les trois tâches de fond mouraient en
    silence. Deux dossiers fantômes (04 et 31/07) pour une capacité perdue.
    Ici on refuse de créer, et on le DIT."""
    if not p.is_absolute():
        print(f"  ⚠ {quoi} n'est pas un chemin absolu sur cette plateforme : "
              f"{p!s} — dossier NON créé (import hors Windows ?).")
        return
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"  ⚠ {quoi} : création impossible ({e}).")


_creer_dossier_si_absolu(DATA_DIR, "DATA_DIR")
_creer_dossier_si_absolu(UPLOAD_DIR, "UPLOAD_DIR")
INDEX_FILE = DATA_DIR / "tags_index.json"

# ─── Reconnaissance des animaux (Phase 1 : détection YOLO) ───
ANIMALS_INDEX_FILE = DATA_DIR / "animals_index.json"

# ─── Reconnaissance de personnes (Phase 1 : détection + embeddings) ───
FACES_INDEX_FILE = DATA_DIR / "faces_index.json"
FACE_MODEL = "buffalo_l"        # modèle InsightFace (téléchargé au 1er lancement)
# GPU désactivé : la RTX 3050 (4 Go) est déjà occupée par Ollama (tagging).
# Les visages tournent sur CPU pour ne pas gêner le tagging. Passer à True
# pour tenter le GPU (nécessite CUDA 13 + VRAM libre — voir historique projet).
FACE_USE_GPU = False
# GPU adaptatif : les visages basculent sur GPU seulement quand assez de VRAM est
# libre (Ollama au repos), sinon CPU — le tagging garde la priorité sur le GPU.
FACE_GPU_ENABLE = True
FACE_GPU_MIN_FREE_MB = 1200     # VRAM libre requise pour router/initialiser le GPU
FACE_GPU_MEM_LIMIT_MB = 1024    # plafond mémoire de la session GPU visages
FACE_DET_THRESHOLD = 0.50       # score de détection minimal (abaissé = capte profils/petits/flous)
FACE_MAX_SIDE = 1600            # redimensionnement avant détection (vitesse)
FACE_SCAN_INTERVAL = 300        # secondes entre deux balayages visages
# ─── Phase 2 : regroupement + nommage des personnes ───
PEOPLE_FILE = DATA_DIR / "people.json"
FACE_CLUSTER_SIM = 0.50         # seuil cosinus de regroupement des visages (resserré = plus pur)
CLUSTER_SPLIT_SIM = 0.55        # re-regroupement interne plus strict pour tester la scission
CLUSTER_SPLIT_CONFIRM = 0.45    # on scinde seulement si 2 sous-groupes sont + éloignés que ça
FACE_MATCH_SIM = 0.42           # seuil pour proposer une correspondance à une personne nommée
FACE_MIN_CLUSTER = 3            # taille minimale d'un groupe affiché
# ─── Phase B : ré-embedding adaptatif des visages de mauvaise qualité ───
REEMBED_ENABLE = True
REEMBED_MIN_SCORE = 0.78        # visage « faible » sous ce score de détection
REEMBED_MIN_FACE_PX = 90        # ou visage plus petit que ça (largeur en px d'origine)
REEMBED_BATCH = 6               # photos re-analysées par lot
REEMBED_CPU_BUSY = 70           # % CPU au-dessus duquel on lève le pied
REEMBED_MIN_RAM_GB = 1.5        # RAM libre minimale pour travailler
REEMBED_IDLE_SLEEP = 120        # s d'attente quand plus rien à faire
REEMBED_BUSY_SLEEP = 60         # s d'attente quand la machine est occupée
REEMBED_PACE = 2                # s entre deux lots
REEMBED_UI_QUIET = 12           # s : le ré-embedding cède le NAS après une requête image
FACE_THUMB_DIR = SCRIPT_DIR / "face_thumbs"   # cache disque local des vignettes de visages
LAST_HEAVY_AT = 0.0             # dernier accès NAS via l'UI (crop/média/upload)

# ─── Orchestrateur de maintenance (nettoyage/dédoublonnage/purge/renommage) ───
# Un thread de fond appelle maintenance.run_cycle : chaque étape a sa cadence et
# son autonomie (auto pour le sûr et réversible, propose pour le gros). Il vit
# DANS le serveur pour partager l'index en mémoire (écrivain unique, pas de cache
# périmé) et céder à l'UI. Voir maintenance.py. Mettre à False pour le désactiver.
MAINTENANCE_AUTO = True
MAINTENANCE_EVERY = 3600        # s : fréquence d'évaluation du cycle (les étapes gardent leur propre cadence)
MAINT_PAUSED = False            # pause RUNTIME depuis /reglages (l'auto reste actif au démarrage)

# ─── Reconnaissance des animaux — Phase 1 : détection (YOLO / Ultralytics) ───
# Chaîne SÉPARÉE des visages : YOLO trouve les animaux (chat/chien/oiseau…),
# résultats écrits dans animals_index.json. Le nommage individuel (Caline, Inti,
# Luna) viendra en Phase 2 (embeddings). Tourne sur CPU par défaut pour ne pas
# disputer la VRAM à Ollama (tagging) ni aux visages.
ANIMAL_YOLO_WEIGHTS = "yolo11s.pt"   # small : plus précis que nano (détecte + de chats)
ANIMAL_DEVICE = "cpu"                # repli si GPU indisponible
ANIMAL_GPU_ENABLE = True             # GPU adaptatif : CUDA quand la VRAM est libre, sinon CPU
ANIMAL_GPU_MIN_FREE_MB = 1600        # VRAM libre requise pour router YOLO sur GPU
ANIMAL_DET_THRESHOLD = 0.30          # confiance minimale (abaissée = capte + de chats)
ANIMAL_MAX_SIDE = 1600               # redimensionnement avant détection (vitesse)
ANIMAL_SCAN_INTERVAL = 300           # secondes entre deux balayages animaux
# Version du pipeline animaux : détecteur + seuil + modèle d'empreinte. Si ça
# change, on relance détection + empreintes (migration propre) — voir
# migrate_animal_pipeline(). Les NOMS (tags) sont préservés.
ANIMAL_PIPELINE_VERSION = "yolo11s|det0.30|dinov2_base"
# Classes COCO retenues (id → espèce). Seuls les chats seront nommables en
# Phase 2 ; les autres servent de simples tags d'espèce.
ANIMAL_CLASSES = {14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse',
                  18: 'sheep', 19: 'cow'}
ANIMAL_THUMB_DIR = SCRIPT_DIR / "animal_thumbs"   # cache disque des découpes (Phase 2)
PHOTO_THUMB_DIR = SCRIPT_DIR / "photo_thumbs"     # cache disque des vignettes (audit O1)

# ─── Reconnaissance des chats — Phase 2 : nommage individuel (embeddings) ───
# Chaque chat détecté est transformé en vecteur (DINOv2) → regroupement →
# nommage (Caline / Inti / Luna) → attribution automatique, exactement comme les
# personnes. Fichier de noms séparé (pets.json). Tag écrit : « animal:Nom ».
PETS_FILE = DATA_DIR / "pets.json"
# ─── Espèces nommables individuellement ───
# Le nommage n'était historiquement branché que sur « cat ». Il vaut pour tout
# animal familier photographié régulièrement. Les espèces croisées de passage
# (vache, mouton, oiseau sauvage) restent de simples tags d'espèce : les
# regrouper individuellement n'aurait pas de sens.
# Modifiable via especes_nommables.txt, une espèce par ligne.
ANIMAL_NAMEABLE = {'cat', 'dog', 'horse'}
try:
    _lst = set()
    for _l in (SCRIPT_DIR / "especes_nommables.txt").read_text(
            encoding='utf-8').splitlines():
        _l = _l.split('#')[0].strip()
        if _l:
            _lst.add(_l)
    if _lst:
        ANIMAL_NAMEABLE = _lst
except OSError:
    pass


def _nommable(a):
    """Une détection est-elle éligible au nommage individuel ?

    Écarte aussi les détections que la vérification d'espèce SigLIP a
    contredites (voir verifier_especes.py) : c'est ce qui empêche un groupe
    de macaques d'être présenté comme « 9 apparitions de ce chat ».
    """
    if (not isinstance(a, dict) or a.get('suspect') or a.get('inconnu')
            or a.get('non_group')):
        return False
    return a.get('species') in ANIMAL_NAMEABLE


def _meme_espece(a, espece):
    """Deux animaux ne se regroupent que s'ils sont de la même espèce."""
    return _nommable(a) and (not espece or a.get('species') == espece)
DINO_MODEL = "vit_base_patch14_dinov2.lvd142m"    # base : distingue mieux 2 chats proches
DINO_DEVICE = "cpu"             # repli si GPU indisponible
PET_GPU_ENABLE = True           # GPU adaptatif pour DINOv2 (CUDA si VRAM libre)
PET_GPU_MIN_FREE_MB = 1800      # vit_base est plus lourd → exige + de VRAM libre
PET_CLUSTER_SIM = 0.60          # seuil cosinus de regroupement des chats (à calibrer)
PET_MATCH_SIM = 0.55            # seuil pour proposer/attribuer une photo à un chat
# Auto-attribution des chats (comme le curateur des personnes) : conservatrice
# pour NE PAS polluer pendant une absence prolongée. Seuil élevé + marge nette
# avec le 2e chat le plus proche.
CAT_AUTO_ENABLE = True
CAT_AUTO_SIM = 0.66            # rattachement auto seulement à forte confiance
CAT_AUTO_MARGIN = 0.10        # écart requis avec le 2e chat le plus proche
PET_MIN_CLUSTER = 2             # taille min d'un groupe affiché (peu de photos → 2)
PET_EMBED_BATCH = 8             # découpes embarquées par lot (backfill)

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.bmp', '.tiff', '.tif'}
# ─── Les VIDÉOS dans la galerie (chantier 1 octies, phase 1 — 30/08/2026,
# demandé par Mike : « les traiter comme les photos »). Le SCAN les indexe
# (entrée `{video: True, duree, taken}` écrite directement, JAMAIS mise en file
# du tagueur), la VIGNETTE est une image-clé ffmpeg, la visionneuse ouvre un
# `<video>`. Tout pipeline d'IA reste fermé aux vidéos : chacun filtre déjà
# sur IMAGE_EXT, et le sémantique saute `video` — c'est la phase 2 qui les
# ouvrira. `VIDEOS_DANS_L_INDEX = False` rend le scan d'hier, sans rien casser
# (les entrées déjà écrites restent, inertes).
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.wmv'}
VIDEOS_DANS_L_INDEX = True
MEDIA_EXT = IMAGE_EXT | (VIDEO_EXT if VIDEOS_DANS_L_INDEX else set())

# Version du pipeline de TAGGING (audit D), sur le modèle d'ANIMAL_PIPELINE_VERSION :
# modèle Ollama | variante de prompt | version de fusion (Knowledge Builder).
# Changer l'un des trois OBLIGE à bumper la chaîne — sinon des descriptions issues
# de prompts différents cohabitent silencieusement dans l'index. Chaque nouvelle
# entrée est estampillée ('pipe') ; les entrées antérieures comptent comme « v0 »
# (visible dans /reglages). PAS de re-tagging automatique au bump : ~43 000
# entrées × 4,3 s ≈ 51 h GPU — c'est une décision explicite (ROADMAP), contrairement
# aux embeddings animaux où le mélange de versions serait mathématiquement faux.
# - v2ctx = « assertions en contexte, sans impératif de noms », ADOPTÉE 12/08
#   (aveugle A/B 25-15 vs V0 — eval/DECISIONS.md). Prompt : tagging_meta.prompt_tagging.
# - kb1   = Knowledge Builder : faits noms/date/lieu structurés et sourcés en
#   post-traitement déterministe (tagging_meta.faits_structures), jamais via le prompt.
TAGGING_PIPELINE_VERSION = "qwen3-vl:2b|v2ctx|kb1"

# PROMPT V0 (image seule, anglais) : n'est PLUS le prompt de production depuis la
# version v2ctx ci-dessus. Conservé comme référence du banc d'éval (eval_tagging.py
# le lit via s.PROMPT) et comme repli si ollama_generate est appelé sans prompt.
PROMPT = (
    'Analyze this photo. Return ONLY strict JSON, no other text:\n'
    '{"keywords_en": ["..."], "keywords_fr": ["..."], "description_fr": "..."}\n'
    'Rules: 6-10 keywords per language, lowercase, concise (1-2 words each), covering: '
    'main subjects, scene or location type, activity, mood, dominant colors, season or '
    'time of day if visible. Use spaces between words, never underscores. '
    'NEVER read, transcribe or copy any text, numbers, prices, receipts, labels, '
    'addresses or signs visible in the image; describe it visually only. '
    'For a document, receipt or screenshot, just use generic keywords like '
    '"document", "receipt", "screenshot", "text". '
    'keywords_fr must be real French words (translate, do not copy the English). '
    'description_fr: one short sentence in French.'
)

# ────────────────────────── Pillow (optionnel) ──────────────────────────

PIL_OK = False
try:
    from PIL import Image, ImageOps
    PIL_OK = True
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        print("  ⚠ pillow-heif absent : les HEIC ne seront pas tagués (pip install pillow-heif)")
except ImportError:
    print("  ⚠ Pillow absent : images envoyées en pleine taille à l'IA (pip install pillow)")


class TagError(Exception):
    pass


class OllamaDown(Exception):
    pass


# ────────────────────────── Index des tags ──────────────────────────

class TagStore:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {}
        try:
            self.data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            pass

    def has(self, name):
        e = self.data.get(name)
        return bool(e) and not e.get('failed')

    def get(self, name):
        return self.data.get(name)

    def set(self, name, entry, save=True):
        with self.lock:
            self.data[name] = entry
            if save:
                self._save()

    def save(self):
        with self.lock:
            self._save()

    def _save(self):
        # Écriture ATOMIQUE : on écrit dans un fichier temporaire puis on le
        # renomme par-dessus l'original. Une écriture interrompue (coupure NAS,
        # arrêt du process) ne peut donc plus corrompre l'index → plus de perte
        # de tags au redémarrage.
        data = json.dumps(self.data, ensure_ascii=False, indent=1)
        tmp = self.path.with_name(self.path.name + '.tmp')
        try:
            tmp.write_text(data, encoding='utf-8')
            os.replace(tmp, self.path)
        except OSError as e:
            # repli non-atomique si le rename échoue (rare, ex. verrou SMB)
            try:
                self.path.write_text(data, encoding='utf-8')
            except OSError:
                print(f"  ⚠ Impossible d'écrire {self.path.name}: {e}")

    def rekey(self, old, new, mtime=None):
        """Déplace une entrée vers une nouvelle clé (fichier déplacé/renommé)."""
        with self.lock:
            e = self.data.pop(old, None)
            if e is None:
                return False
            if mtime is not None:
                e['mtime'] = mtime
            self.data[new] = e
            return True

    def remove_many(self, keys):
        with self.lock:
            n = 0
            for k in keys:
                if self.data.pop(k, None) is not None:
                    n += 1
            if n:
                self._save()
            return n

    def tagged_count(self):
        return sum(1 for e in self.data.values()
                   if not e.get('failed') and (e.get('kw_fr') or e.get('kw_en')))


# ─── Persistance : SQLite si photos.db existe, sinon JSON (comportement d'origine) ───
# TagStore réécrit l'index ENTIER à chaque set() (~43 Mo sur SMB avec 16 000
# visages). SqliteStore garde le même dictionnaire en mémoire — donc tous les
# accès à `.data` ci-dessous sont inchangés — mais n'écrit que les lignes
# modifiées. La base vit en LOCAL : SQLite sur SMB a un verrouillage non fiable
# et pas de WAL. Une sauvegarde atomique part sur le NAS (maintenance_loop).
#
# Migration :  python migrate_to_sqlite.py --appliquer
# Retour arrière : supprimer photos.db (+ -wal/-shm) → retour au JSON.
DB_DIR = SCRIPT_DIR                     # disque local, JAMAIS le NAS
DB_BACKUP = DATA_DIR / "photos.db.bak"  # snapshot sauvegardé par le NAS
DB_BACKUP_INTERVAL = 3600               # s entre deux sauvegardes de la base
try:
    from store_sqlite import open_store as _open_store
except ImportError:                     # module absent → comportement historique
    def _open_store(json_path, db_dir, fallback):
        return fallback(json_path)


def make_store(json_path):
    st = _open_store(json_path, DB_DIR, TagStore)
    if type(st).__name__ == 'SqliteStore':
        print(f"  🗄 {json_path.name} → SQLite ({len(st.data)} entrées)")
    return st


STORE = make_store(INDEX_FILE)

# ─── Comptes de l'index : ce que le scan OUBLIE (chantier 10a, 18/08/2026) ────
# Le 17/08, l'index EN MÉMOIRE a perdu 250 entrées que `photos.db` avait
# gardées, et le mécanisme est resté introuvable — non par manque d'hypothèses
# (trois testées, trois tombées) mais parce que RIEN NE COMPTAIT les retraits :
# `forget_everywhere()` renvoyait un nombre que personne n'enregistrait.
#
# Le registre (`comptes_index.py`) se branche sur le GOULOT — `TrackedDict`
# dans `store_sqlite.py`, par où passe toute clé qui entre ou sort de l'index —
# et chaque appelant DÉCLARE son motif. Trois choses deviennent visibles :
#   • combien chaque motif retire (scan:disparus, purge:cles_fantomes…) ;
#   • ce qui retire SANS motif (bucket « (non declare) », avec des exemples) ;
#   • l'ÉCART INEXPLIQUÉ de chaque cycle de scan — la taille de l'index a
#     changé sans qu'aucune mutation passée par le goulot ne l'explique.
# C'est ce dernier chiffre qui manquait aux −250. Lecture : `/reglages` et
# `GET /api/maint/status` (clé « oublis »).


class _RegistreInerte:
    """Registre qui ne compte rien et ne casse rien.

    Utilisé quand le module est absent OU quand l'index tourne encore sur le
    repli JSON (`TagStore`), dont le dict nu n'est pas instrumenté : mieux vaut
    un instrument MUET qu'un instrument qui ment — des compteurs à zéro se
    liraient « rien n'a été retiré », et la réconciliation crierait à l'écart
    inexpliqué à chaque cycle.
    """

    actif = False

    def motif(self, *a, **k):
        import contextlib
        return contextlib.nullcontext()

    def motif_du_thread(self, *a, **k):
        return None

    def cle_ajoutee(self, *a):
        pass

    def cle_retiree(self, *a):
        pass

    def cles_retirees(self, *a):
        pass

    def debut_cycle(self, *a):
        pass

    def fin_cycle(self, *a):
        return None

    def resume(self):
        return {'actif': False}

    def ligne_cycle(self, *a):
        return ''

    def ligne_motifs(self):
        return ''

    def etat(self):
        return {}

    def restaurer(self, *a):
        return False


try:
    from comptes_index import RegistreOublis
except ImportError:                     # module absent → instrument inerte
    RegistreOublis = None

# Le carnet de comptes SURVIT au redémarrage (22/08). Sans ça il ne
# diagnostique rien : le 21/08, la cause des 2 283 clés oubliées n'a pas pu être
# établie parce que `par_motif` était reparti à zéro au redémarrage de 19:31 —
# l'instrument bâti POUR ça n'avait rien gardé. Le module reste PUR (aucune
# E/S) : il rend un dict, c'est ici qu'on l'écrit.
COMPTES_FILE = SCRIPT_DIR / "_comptes_index.json"


def charger_comptes():
    """Reprend le carnet de la vie précédente. Silencieux si absent ou illisible :
    un instrument ne doit jamais empêcher le serveur de démarrer."""
    try:
        etat = json.loads(COMPTES_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    try:
        return bool(REGISTRE.restaurer(etat))
    except Exception:                                        # noqa: BLE001
        return False


def sauver_comptes():
    """Écrit le carnet, atomiquement (tmp + replace) comme les index : une
    coupure au mauvais moment laisserait sinon un JSON tronqué, et le carnet
    repartirait de zéro — exactement ce qu'on corrige."""
    try:
        etat = REGISTRE.etat()
        if not etat:
            return False
        tmp = COMPTES_FILE.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(etat, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, COMPTES_FILE)
        return True
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠ Comptes de l'index non sauvés : {e}")
        return False


if RegistreOublis is not None and hasattr(STORE, 'brancher_registre'):
    REGISTRE = RegistreOublis()
    STORE.brancher_registre(REGISTRE)
    _repris = charger_comptes()
    print(f"  📒 Comptes de l'index actifs — départ à {len(STORE.data)} entrées"
          + (f" (carnet repris, {REGISTRE.redemarrages} redémarrage(s), "
             f"{REGISTRE.retraits} retrait(s) au total)" if _repris else
             " (carnet neuf)"))
    # Écrire TOUT DE SUITE, sans attendre un cycle : un premier scan dure des
    # minutes, et deux redémarrages rapprochés n'en laissaient jamais finir un.
    # C'est exactement comme ça que le carnet du 21/08 est resté vide — la même
    # leçon que `_backup_du()`, dont l'échéance se lit sur le FICHIER et non sur
    # un compteur de tours qui ne survit pas.
    sauver_comptes()
else:
    REGISTRE = _RegistreInerte()
    if RegistreOublis is None:
        print("  📒 Comptes de l'index indisponibles (comptes_index.py absent)")
    else:
        print("  📒 Comptes de l'index indisponibles (index JSON non instrumenté)")

TAG_QUEUE = queue.Queue()
PENDING = set()
PENDING_LOCK = threading.Lock()
EXIFTOOL = None

# Reconnaissance de personnes : index séparé (n'alourdit pas tags_index.json)
FACE_STORE = make_store(FACES_INDEX_FILE)
FACE_QUEUE = queue.Queue()
FACE_PENDING = set()
FACE_PENDING_LOCK = threading.Lock()

# Reconnaissance des animaux : index séparé (Phase 1 : détection)
ANIMAL_STORE = make_store(ANIMALS_INDEX_FILE)
ANIMAL_QUEUE = queue.Queue()
ANIMAL_PENDING = set()
ANIMAL_PENDING_LOCK = threading.Lock()

# Phase 2 : chats nommés + cache de regroupement
PETS_STORE = make_store(PETS_FILE)
PET_CLUSTER_CACHE = {"at": 0.0, "building": False, "clusters": [], "byid": {}}
PET_CLUSTER_LOCK = threading.Lock()
PET_EMBED_STATE = {"done": 0}

# Phase 2 : personnes nommées + file d'écriture des tags personne:Nom
PEOPLE_STORE = make_store(PEOPLE_FILE)

# ─── L'AUTEUR des décisions humaines (chantier 17, étape 2 — 29/08/2026) ─────
# Règle pure dans `auteurs.py` (choix de Mike, eval/DECISIONS.md). Branchée au
# GOULOT : chaque `set()` sur une fiche personne/animal réconcilie `auteurs`
# avec les listes `faces`/`exclude`/`confirmed` — toute décision neuve reçoit
# l'utilisateur courant, une décision annulée perd son auteur, deux jugements
# contradictoires passent par l'arbitre (propriétaire de la photo, puis admin ;
# le perdant reste en `#contesté`). Les trente écritures du serveur sont donc
# couvertes sans être touchées. Tant que l'authentification (étape 4) n'existe
# pas, l'utilisateur courant est l'admin — Mike, seul écrivain aujourd'hui.
import auteurs as _auteurs

_UTILISATEUR = threading.local()


def utilisateur_courant():
    """Qui écrit en ce moment : posé par le routeur HTTP (étape 4), l'admin
    sinon. Ne rend jamais None : une décision sans auteur est une décision
    perdue pour la règle « les noms de QUI »."""
    return getattr(_UTILISATEUR, 'nom', None) or _auteurs.ADMIN


_auteurs.garnir(PEOPLE_STORE, utilisateur_courant)
_auteurs.garnir(PETS_STORE, utilisateur_courant)

# ─── La VUE par utilisateur (chantier 17, étape 3 — 29/08/2026) ──────────────
# Règle pure dans `visibilite.py` (17a : le partage se fait par dossier, sauf
# `PRIVE` ; 17b : le privé ne se trahit pas, y compris par un compteur).
# Branchée à la LECTURE des magasins : `STORE.data`, `FACE_STORE.data`,
# `ANIMAL_STORE.data` cachent les clés que l'utilisateur courant n'a pas le
# droit de voir ; `PEOPLE_STORE.data` / `PETS_STORE.data` rendent des fiches
# sans leurs citations invisibles (faces, exclude, confirmed, avatar). Tout ce
# qui agrège (fiches, /api/names, chips, /sujets, la carte) hérite du filtre
# sans être touché. Les fils de fond n'ont pas d'utilisateur : ils voient
# tout, comme avant. Tant que le routeur ne pose pas `_UTILISATEUR.nom`
# (étape 4), `utilisateur_vu()` rend None et RIEN ne change — le mécanisme
# est en place, dormant, et son banc (`test_visibilite.py`) le prouve à vide.
# ATTENTION pour l'étape 4 : une route qui ÉCRIT `STORE.data[k] = …` en
# direct sous un utilisateur courant tomberait sur la vue (lecture seule) —
# les écritures doivent passer par `store.set()` (SqliteStore écrit `_d`).
import visibilite as _visibilite


def utilisateur_vu():
    """Qui REGARDE : None tant que personne n'est connecté (fil de fond, ou
    requête sans compte — étape 4). Contrairement à `utilisateur_courant()`,
    ne retombe PAS sur l'admin : un fil de fond qui se prendrait pour l'admin
    verrait la vue au lieu du dictionnaire, et ne pourrait plus écrire."""
    return getattr(_UTILISATEUR, 'nom', None)


def chemin_visible(chemin):
    """Le garde des routes qui servent des OCTETS par chemin (fichier,
    vignette) : la vue des magasins ne les couvre pas. Refus = 404, jamais
    403 — dire « interdit » dirait « ça existe »."""
    return _visibilite.visible(str(chemin), utilisateur_vu())


def refus_ecriture(chemin):
    """Le garde des gestes sur FICHIER (chantier 17, étape 5 — renommer,
    déplacer, effacer, créer un dossier, annuler) : None si l'utilisateur
    courant a la main, sinon (code, message). Injecté dans `FileOps` — un
    seul goulot, consulté AVANT de toucher au disque. Les DÉCISIONS sur une
    photo ne passent pas ici (arbitrées par `auteurs`)."""
    return _visibilite.refus_ecriture(str(chemin), utilisateur_vu())


for _st in (STORE, FACE_STORE, ANIMAL_STORE):
    _visibilite.brancher(_st, utilisateur_vu)
for _st in (PEOPLE_STORE, PETS_STORE):
    _visibilite.brancher(_st, utilisateur_vu, par_nom=True)

# ─── Les COMPTES (chantier 17, étape 4 — 29/08/2026, choix de Mike : un mot de
# passe par compte). Règle dans `comptes.py` ; fichier `comptes.json` HORS git.
# Le routeur ouvre chaque requête par `_ouvrir()` : il lit le cookie, pose
# `_UTILISATEUR.nom` (ce qui ARME la vue de l'étape 3 et signe les décisions
# de l'étape 2), et ferme la porte aux sans-compte — SEULEMENT si un compte
# existe. Sans compte, le serveur est exactement celui d'hier.
import comptes as _comptes

COMPTES = _comptes.Comptes(SCRIPT_DIR / 'comptes.json')
if COMPTES.actifs():
    print(f"  🔐 comptes : {len(COMPTES.noms())} — la porte est FERMÉE (connexion requise)")
else:
    print("  🔓 comptes : aucun — la porte est ouverte (creer_compte.py pour la fermer)")


def migrer_auteurs():
    """Attribution RÉTROACTIVE à l'admin de toute décision sans auteur (une
    passe au démarrage, idempotente : rejouée, elle ne trouve rien). Rien n'est
    perdu ni changé dans les listes ; l'annulation est `pe.pop('auteurs')` sur
    les fiches listées dans le journal `docs/migration_auteurs.json`."""
    fiches, n = [], 0
    for magasin, st in (('people', PEOPLE_STORE), ('pets', PETS_STORE)):
        for pk, pe in list(st.data.items()):
            if not isinstance(pe, dict):
                continue
            champs = _auteurs.reconcilier(pe, _auteurs.ADMIN)
            if not champs:
                continue
            n += len(champs.get('auteurs') or {}) - len(pe.get('auteurs') or {})
            fiches.append(f"{magasin}:{pk}")
            for champ, valeur in champs.items():
                pe[champ] = valeur
            st.set(pk, pe, save=False)
        if fiches:
            st.save()
    if fiches:
        try:
            (SCRIPT_DIR / 'docs').mkdir(exist_ok=True)
            (SCRIPT_DIR / 'docs' / 'migration_auteurs.json').write_text(json.dumps(
                {'quand': time.strftime('%Y-%m-%d %H:%M:%S'), 'auteur': _auteurs.ADMIN,
                 'decisions': n, 'fiches': fiches}, ensure_ascii=False, indent=1),
                encoding='utf-8')
        except OSError as e:
            print(f"  ⚠ journal migration auteurs : {e}")
        print(f"  ✍ auteurs : {n} décision(s) attribuée(s) à {_auteurs.ADMIN} "
              f"sur {len(fiches)} fiche(s)")
    return n


PERSON_QUEUE = queue.Queue()          # (chemin, tag, op, clé, n°) à écrire
# La file d'écriture XMP SURVIT à un arrêt. Elle n'existait qu'en mémoire : la
# fusion Flo → Florine du 23/08 y a laissé 11 814 écritures pour ~11 h de
# travail, et un redémarrage — ou une coupure — les aurait perdues SANS RIEN
# pour les retrouver. Des milliers de photos auraient gardé `personne:Flo` dans
# leur fichier quand l'index disait `Florine` : c'est ainsi que naît un nom
# fantôme, et c'est la règle 2 qui tombe. Un journal en ajout pur note chaque
# geste AVANT de l'enfiler ; un seul écrivain les consomme dans l'ordre, donc
# une POSITION suffit à dire où il en est. Au démarrage, ce qui est au-delà de
# la position repart en file.
PERSON_JOURNAL = SCRIPT_DIR / "_file_personnes.jsonl"
PERSON_JOURNAL_POS = SCRIPT_DIR / "_file_personnes.pos"
PERSON_JOURNAL_ECHECS = SCRIPT_DIR / "_file_personnes_echecs.jsonl"
PERSON_JOURNAL_LOCK = threading.Lock()
PERSON_SEQ = 0                        # dernier n° distribué (sous le verrou)
PERSON_LOT_MAX = 16                   # gestes groupés en une invocation
CLUSTER_CACHE = {"at": 0.0, "building": False, "clusters": [], "byid": {}}
CLUSTER_LOCK = threading.Lock()
# Vue « (Inconnus) » : clusters des visages archivés (champ 'inconnu'), séparés de
# la file « À nommer » pour un re-tag ultérieur. Même forme que CLUSTER_CACHE.
INCONNU_CACHE = {"at": 0.0, "building": False, "clusters": [], "byid": {}}
INCONNU_LOCK = threading.Lock()


# ─── Magasin de sujets commun (point 7 du ROADMAP) ───────────────────────────
# PEOPLE_STORE et PETS_STORE ont la MÊME forme d'entrée (name, refs, faces,
# exclude, confirmed ; species pour les animaux). Les gestes de gestion —
# nommer un groupe, proposer d'autres photos, confirmer, réviser, détacher,
# renommer, supprimer — n'y différaient que par SIX branchements :
#
#   préfixe de tag · store de fiches · store de détection (+ champ) ·
#   vignette (crop) · seuil de similarité · cache/verrou de regroupement.
#
# SubjectStore les injecte à la construction ; chaque geste devient une méthode
# unique valable des deux côtés. Conséquence voulue (harmonisation) : une
# amélioration d'un côté profite automatiquement à l'autre. Deux trous sont
# ainsi comblés : `find_more` applique désormais `exclude` AUSSI aux animaux
# (une photo corrigée ne revient plus dans les propositions), et `photos`
# partage la même sélection du meilleur visage/animal.
#
# Les fonctions historiques (name_cluster, find_more, confirm_person, …) sont
# conservées comme wrappers d'une ligne : aucune route ni appelant à changer.
# Les helpers référencés (crop, centroïde, _kw_has, _index_*, …) sont définis
# plus bas dans le fichier ; comme ils ne sont résolus qu'à l'APPEL, l'ordre de
# définition n'a pas d'importance.
class SubjectStore:
    def __init__(self, kind, prefix, store, det_store, det_field,
                 cache, lock, species=False, has_avatar=False,
                 filter_nommable=False):
        self.kind = kind                # 'personne' | 'animal'
        self.prefix = prefix            # préfixe de tag
        self.store = store              # PEOPLE_STORE | PETS_STORE
        self.det_store = det_store      # FACE_STORE | ANIMAL_STORE
        self.det_field = det_field      # 'faces' | 'animals'
        self.cache = cache              # CLUSTER_CACHE | PET_CLUSTER_CACHE
        self.lock = lock                # CLUSTER_LOCK | PET_CLUSTER_LOCK
        self.species = species          # les animaux portent une espèce déduite
        self.has_avatar = has_avatar    # avatar calculé par le curateur (personnes)
        self.filter_nommable = filter_nommable  # animaux : ignorer les non-nommables

    # --- helpers à liaison tardive (définis plus bas dans le module) ---
    def _crop(self, k, i):
        return _animal_crop_url(k, i) if self.kind == 'animal' else _crop_url(k, i)

    def _centroid(self, pe):
        return cat_centroid(pe) if self.kind == 'animal' else person_centroid(pe)

    def _sim(self):
        # résolu à l'appel : honore les surcharges de seuils.txt
        return PET_MATCH_SIM if self.kind == 'animal' else FACE_MATCH_SIM

    def _new_entry(self, name, espece=None):
        e = {"name": name, "refs": [], "at": time.time()}
        if self.species:
            e["species"] = espece or "cat"
        return e

    # --- gestes unifiés ---
    def name_cluster(self, cid, name):
        """Nomme un groupe : enregistre la fiche + tague ses photos."""
        name = (name or "").strip()[:60]
        if not name:
            return 0
        with self.lock:
            members = list(self.cache["byid"].get(cid, []))
        if not members:
            return 0
        tag = f"{self.prefix}:{name}"
        refs = []
        especes = {}
        for (k, i) in members:
            de = self.det_store.data.get(k)
            if isinstance(de, dict):
                items = de.get(self.det_field) or []
                if i < len(items):
                    if self.species:
                        sp = items[i].get('species')
                        if sp:
                            especes[sp] = especes.get(sp, 0) + 1
                    if items[i].get('emb') and len(refs) < 40:
                        refs.append(items[i]['emb'])
        pk = name.lower()
        if self.species:
            # L'espèce est DÉDUITE du groupe, plus jamais supposée « cat ».
            espece = max(especes, key=especes.get) if especes else 'cat'
            pe = self.store.data.get(pk) or self._new_entry(name, espece)
            pe.setdefault("species", espece)
        else:
            pe = self.store.data.get(pk) or self._new_entry(name)
        pe["name"] = name
        # Les NOUVELLES références passent en tête : une fiche plafonnée à 80
        # refs n'en acceptait plus jamais, donc nommer à la main n'améliorait
        # plus rien. Les plus anciennes sortent — la signature suit le sujet.
        pe["refs"] = (refs + (pe.get("refs") or []))[:80]
        pe["faces"] = _merge_assigned(pe.get("faces"), members)
        self.store.set(pk, pe)
        photos = list(dict.fromkeys(k for (k, i) in members))
        for k in photos:
            _index_add_person(k, tag)
            _enqueue_person_write(k, tag)
        STORE.save()
        # Retire le groupe nommé du cache : sinon il réapparaît indéfiniment
        # dans « Groupes à nommer » (le cache n'est pas reconstruit à chaque fois).
        with self.lock:
            self.cache["byid"].pop(cid, None)
            self.cache["clusters"] = [c for c in self.cache["clusters"]
                                      if c.get("cid") != cid]
        return len(photos)

    def find_more(self, name, limit=300):
        """Propose d'autres photos du sujet (proches de ses références, pas
        encore taguées). Pour validation manuelle."""
        import numpy as np
        pk = (name or "").lower()
        pe = self.store.data.get(pk)
        if not pe or not pe.get("refs"):
            return []
        try:
            R = np.stack([_emb_from_b64(s) for s in pe["refs"]])
        except Exception:
            return []
        tag = f"{self.prefix}:{pe.get('name', name)}"
        exclude = set(pe.get("exclude") or [])   # photos corrigées : ne plus proposer
        sim_thr = self._sim()
        props = []
        for k, e in list(self.det_store.data.items()):
            if not isinstance(e, dict) or e.get('failed'):
                continue
            if k in exclude:
                continue
            se = STORE.data.get(k)
            if _kw_has(se, tag):
                continue  # déjà attribué
            for i, f in enumerate(e.get(self.det_field) or []):
                if self.filter_nommable and not _nommable(f):
                    continue
                emb = f.get('emb')
                if not emb:
                    continue
                try:
                    sim = float(np.max(R @ _emb_from_b64(emb)))
                except Exception:
                    continue
                if sim >= sim_thr:
                    props.append((sim, k, i))
                    break
        props.sort(reverse=True)
        return [{"key": k, "i": i, "sim": round(s, 3), "crop_url": self._crop(k, i)}
                for (s, k, i) in props[:limit]]

    def confirm(self, name, keys):
        """Valide l'attribution de photos au sujet (écrit le tag).

        Et GRAVE la confirmation dans la fiche (`confirmed`) : sans elle, un
        tag reposé sur une photo que la fiche EXCLUT est re-retiré par la
        correction « exclusion humaine ré-appliquée » à chaque démarrage — le
        30/08, 2 des 19 noms recopiés par le dédoublonnage ont rebondi ainsi
        avant que Mike ne tranche « c'est bien lui ». L'exclusion n'est PAS
        effacée (règle du 29/08 : rien ne s'efface, les deux jugements restent
        écrits) ; `confirmed` passe simplement devant, comme dans le healer."""
        name = (name or "").strip()[:60]
        if not name:
            return 0
        tag = f"{self.prefix}:{name}"
        pk = name.lower()
        pe = self.store.data.get(pk)
        confirmed = set(pe.get("confirmed") or []) if isinstance(pe, dict) else set()
        n = 0
        for k in keys:
            _index_add_person(k, tag)
            _enqueue_person_write(k, tag)
            confirmed.add(k)
            n += 1
        if isinstance(pe, dict):
            pe["confirmed"] = list(confirmed)
            self.store.set(pk, pe)
        STORE.save()
        return n

    def photos(self, name, limit=2000, order='worst', light=False):
        """Photos taguées <prefix>:Nom, pour révision. On retient le
        visage/animal qui ressemble LE MIEUX à la signature.

        order='worst' (défaut) : tri du moins au plus ressemblant (faux positifs
        en tête, pour la correction) ; coupe à `limit` en cours de route (sous-
        ensemble arbitraire, suffisant pour corriger).
        order='best' : SCAN COMPLET puis tri du plus au moins ressemblant, top
        `limit`. Sert au CHOIX de références (« Nettoyer ») : sur une fiche
        polluée, seul le haut du classement contient de vraies photos du sujet —
        un sous-ensemble « pire d'abord » n'en montrerait aucune."""
        tag = f"{self.prefix}:{name}"
        pk = name.lower()
        pe = self.store.data.get(pk)
        cen = self._centroid(pe) if isinstance(pe, dict) else None
        # Scoring VECTORISE (voir _best_sims_for_tag) : le scan complet est
        # desormais rapide, meme sous charge. On trie TOUT puis on ne construit
        # les champs riches (vignette, dossier, date) que pour le top `limit`.
        scored = _best_sims_for_tag(tag, cen, self.det_store, self.det_field,
                                    self.filter_nommable)
        if order == 'best':
            scored.sort(key=lambda t: (t[2] if t[2] is not None else -2.0),
                        reverse=True)
        else:
            scored.sort(key=lambda t: (t[2] if t[2] is not None else 2.0))
        scored = scored[:max(1, limit)]
        roots = media_roots()
        out = []
        for k, e, sim, bi in scored:
            crop = self._crop(k, bi) if bi is not None else None
            rec = {"key": k, "crop_url": crop, "url": _url_for_key(k, roots),
                   "name": Path(k).name, "sim": sim,
                   "i": (bi if bi is not None else 0)}
            # light : on omet dossier / mots-cles / date (inutiles au tri par
            # seuil) -> charge utile plus legere sur une fiche a milliers de photos.
            if not light:
                rec["taken"] = _best_time(k, e)
                rec["kw"] = list(dict.fromkeys((e.get('kw_fr') or [])
                                               + (e.get('kw_en') or [])))
                folder, gurl = _folder_link_for_key(k, roots)
                rec["folder"] = folder
                rec["gurl"] = gurl
            out.append(rec)
        return out

    def untag(self, name, keys):
        """Retire le tag de photos mal attribuées et mémorise l'exclusion."""
        name = (name or "").strip()[:60]
        if not name:
            return 0
        tag = f"{self.prefix}:{name}"
        pk = name.lower()
        pe = self.store.data.get(pk)
        exclude = set(pe.get("exclude") or []) if isinstance(pe, dict) else set()
        n = 0
        for k in keys:
            _index_remove_person(k, tag)
            _enqueue_person_write(k, tag, 'del')
            exclude.add(k)
            n += 1
        if isinstance(pe, dict):
            pe["exclude"] = list(exclude)
            self.store.set(pk, pe)
        STORE.save()
        return n

    def rename(self, old, new):
        """Renomme un sujet : fusionne les FICHES d'abord, puis remplace
        <prefix>:Ancien par <prefix>:Nouveau partout (index + fichiers).

        L'ORDRE N'EST PAS COSMÉTIQUE — c'est le correctif du 22/08.

        La boucle sur les photos met une HEURE (un `stat` NAS par photo, 5 907
        photos pour Flo). Tant que la fiche absorbée existe, sa SIGNATURE
        existe : `curator_loop()` repasse toutes les 240 s et `AUTO_ADD`
        rattache l'ancien nom aux photos que la fusion vient de lui retirer.
        Mesuré ce jour-là : `Flo` descend de 5 907 à 4 487, puis REMONTE à
        5 703 pendant que la boucle tourne encore, 60 auto-ajouts « Flo » dans
        l'heure, et 17 092 écritures XMP en attente pour une fusion qui en
        demande 11 814 — les deux mécanismes se battaient, et le NAS écrivait
        les coups des deux camps. Supprimer la fiche AVANT retire la signature
        avant la course : il n'y a plus de course.

        DEUX AUTRES PROPRIÉTÉS TIENNENT À CETTE FORME :

        — Le journal est écrit dans un `finally`. Une boucle interrompue (la
          première l'a été) laissait un fonds à moitié renommé et RIEN pour
          l'annuler. Désormais ce qui a été fait est toujours noté, quoi qu'il
          arrive, et relancer le même renommage REPREND le travail : la fiche
          est déjà fusionnée (`op` vaut None), la boucle finit les photos.

        — Les photos qui portent DÉJÀ le nouveau nom voient quand même leur
          FICHIER réécrit. Une photo dont l'index a basculé sans que l'XMP
          suive (file perdue au redémarrage, écriture échouée) garde l'ancien
          nom dans ses métadonnées ; au prochain balayage des fichiers
          modifiés il REVIENT dans l'index, sans fiche — un nom fantôme, tel
          que « personne:Florine, 153 photos, aucune fiche ». La règle est
          donc : après un renommage, plus AUCUN fichier ne porte l'ancien nom.
        """
        old = (old or "").strip()
        new = (new or "").strip()[:60]
        if not old or not new or old.lower() == new.lower():
            return 0
        oldtag, newtag = f"{self.prefix}:{old}", f"{self.prefix}:{new}"
        n = 0
        avant_old = _fiche_pour_journal(self.store.data.get(old.lower()))
        avant_new = _fiche_pour_journal(self.store.data.get(new.lower()))
        op = self.store.data.pop(old.lower(), None)
        if op:
            npp = self.store.data.get(new.lower())
            if npp is None:
                npp = self._new_entry(new, op.get("species") if self.species else None)
            npp["name"] = new
            npp["refs"] = ((npp.get("refs") or []) + (op.get("refs") or []))[:80]
            # TOUS les ensembles de décisions humaines, pas seulement `exclude`.
            # Jusqu'au 22/08, `confirmed` et `nomerge` n'étaient pas transportés :
            # une fusion emportait en silence les « c'est bien elle » de la fiche
            # absorbée — 143 pour Flo, et autant à chaque merge du curateur
            # depuis que la fonction existe. Une exclusion et une confirmation
            # sont la même matière : un humain a tranché.
            for champ in ("exclude", "confirmed", "nomerge"):
                fusion = set(npp.get(champ) or []) | set(op.get(champ) or [])
                if fusion:
                    npp[champ] = sorted(fusion)
            npp["faces"] = _merge_assigned(
                npp.get("faces"),
                [(x[0], x[1]) for x in (op.get("faces") or [])
                 if isinstance(x, (list, tuple)) and len(x) == 2])
            # L'avatar de la fiche absorbée vaut mieux que pas d'avatar : une
            # fiche sans portrait se relit mal, et le curateur mettrait un
            # cycle entier à en recalculer un.
            if not npp.get("avatar") and op.get("avatar"):
                npp["avatar"] = op["avatar"]
            if self.species and not npp.get("species") and op.get("species"):
                npp["species"] = op["species"]
            # La fiche fusionnée date de la PLUS ANCIENNE des deux : c'est
            # depuis ce jour-là que ce sujet est connu.
            ats = [x.get("at") for x in (npp, op) if isinstance(x.get("at"), (int, float))]
            if ats:
                npp["at"] = min(ats)
            self.store.set(new.lower(), npp)
        apres_new = _fiche_pour_journal(self.store.data.get(new.lower()))
        # `deja` : cette photo portait-elle DEJA le nouveau nom ? C'est la
        # seule information qui permette de defaire la fusion sans mentir.
        # Renommer Florine en Flo pour revenir en arriere emporterait les 153
        # photos qui portaient Florine AVANT — un aller-retour ne rend pas ce
        # qu'il a pris. Voir `annuler_fusion`.
        touchees = []
        try:
            for k, e in list(STORE.data.items()):
                a_ancien = _kw_has(e, oldtag)
                a_nouveau = _kw_has(e, newtag)
                if not (a_ancien or a_nouveau):
                    continue
                if a_ancien:
                    _index_remove_person(k, oldtag)
                    _index_add_person(k, newtag)
                    touchees.append([k, 1 if a_nouveau else 0])
                    n += 1
                # Le FICHIER est reecrit dans les deux cas (voir la docstring) :
                # une photo deja basculee dans l'index peut garder l'ancien nom
                # dans son XMP, et c'est par la que naissent les noms fantomes.
                # `touchees` ne la compte PAS : elle ne portait pas l'ancien
                # nom, annuler ne doit donc rien lui rendre.
                _enqueue_person_write(k, oldtag, 'del')
                _enqueue_person_write(k, newtag, 'add')
        finally:
            STORE.save()
            _journal_fusion(self.prefix, old, new, touchees, avant_old,
                            avant_new, apres_new)
        return n

    def delete(self, name):
        """Supprime entièrement un sujet : efface sa FICHE, puis retire son tag
        partout. Les tags dans les FICHIERS sont retirés via la file.

        MÊME ORDRE QUE `rename`, ET POUR LA MÊME RAISON. La fiche part
        d'ABORD : tant qu'elle vit, sa signature vit, et `AUTO_ADD` remet le
        nom sur les photos que la boucle vient de lui retirer — une heure de
        balayage contre une passe de curateur toutes les 240 s. Mesuré le
        22/08 sur `rename`, qui avait la même forme (voir sa docstring).
        """
        name = (name or "").strip()[:60]
        if not name:
            return 0
        tag = f"{self.prefix}:{name}"
        n = 0
        self.store.data.pop(name.lower(), None)
        self.store.save()
        for k, e in list(STORE.data.items()):
            if _kw_has(e, tag):
                _index_remove_person(k, tag)
                _enqueue_person_write(k, tag, 'del')
                n += 1
        STORE.save()
        return n


# Le registre est construit ici (tous les stores/caches existent) ; les fiches
# et fichiers sur disque sont INCHANGÉS (mêmes PEOPLE_FILE / PETS_FILE).
SUBJECTS = {
    'personne': SubjectStore('personne', 'personne', PEOPLE_STORE,
                             FACE_STORE, 'faces', CLUSTER_CACHE, CLUSTER_LOCK,
                             species=False, has_avatar=True,
                             filter_nommable=False),
    'animal': SubjectStore('animal', 'animal', PETS_STORE,
                           ANIMAL_STORE, 'animals', PET_CLUSTER_CACHE,
                           PET_CLUSTER_LOCK, species=True, has_avatar=False,
                           filter_nommable=True),
}
PEOPLE = SUBJECTS['personne']
PETS = SUBJECTS['animal']


def enqueue(name):
    with PENDING_LOCK:
        if name in PENDING:
            return
        PENDING.add(name)
    TAG_QUEUE.put(name)


def pending_done(name):
    with PENDING_LOCK:
        PENDING.discard(name)


# ────────────────────────── ExifTool ──────────────────────────

# Dossiers que la recherche d'ExifTool ne doit JAMAIS parcourir : volumineux
# (vignettes, uploads, environnement virtuel) ou hors sujet (git, corbeilles).
EXIFTOOL_SKIP_DIRS = {
    '.git', '.venv', '__pycache__', 'photo_thumbs', 'face_thumbs',
    'animal_thumbs', 'uploads', 'recuperees', 'dist', 'OLD', 'docs', 'eval',
    'ui', '_corbeille_session', '_to_delete', '_bat_archive',
}


def _exiftool_emplacements_probables():
    """Emplacements PLAUSIBLES d'exiftool.exe, sans parcourir le projet.

    Le zip officiel s'extrait dans « exiftool-XX.XX_64/ » et contient
    « exiftool.exe » (ou « exiftool(-k).exe » selon la version) : on le cherche
    par motif, pas par parcours total. Répondre vite ici, c'est ne jamais avoir
    besoin du parcours de secours."""
    yield SCRIPT_DIR / "exiftool.exe"
    yield SCRIPT_DIR / "exiftool" / "exiftool.exe"
    yield SCRIPT_DIR / "exiftool" / "exiftool(-k).exe"
    try:
        dossiers = sorted(SCRIPT_DIR.glob("exiftool*"))
    except OSError:
        dossiers = []
    for d in dossiers:
        try:
            if not d.is_dir():
                continue
        except OSError:
            continue
        yield d / "exiftool.exe"
        yield d / "exiftool(-k).exe"


def _exiftool_parcours_de_secours():
    """Parcours borné et BAVARD du dossier du projet.

    Remplace `sorted(SCRIPT_DIR.rglob("exiftool*.exe"))` sous `except OSError:
    hits = []` — un parcours total dont l'échec était MUET. Le 14/08, deux
    répertoires créés par erreur et nommés « \\\\NAS-Bremblens\\home\\... »
    (cf. `_creer_dossier_si_absolu`) faisaient sortir le parcours du disque
    local : Windows relit un nom à antislashs comme un chemin UNC et va
    interroger le NAS. L'OSError était avalée, `hits` devenait vide, le code
    enchaînait sur le téléchargement, et le seul message visible était un 404
    sans rapport. ExifTool passait pour absent et les trois tâches de fond
    (dates, noms, GPS) sortaient aussitôt.

    Un travail de fond qui ne rend pas de comptes finit par ne plus travailler
    du tout : ici on élague, et on dit ce qu'on n'a pas pu lire."""
    trouves, illisibles = [], []
    for racine, dossiers, fichiers in os.walk(SCRIPT_DIR,
                                              onerror=illisibles.append):
        # Élagage EN PLACE (os.walk le relit) : on ne descend ni dans les gros
        # dossiers, ni dans un nom qui contient un séparateur — un tel nom n'est
        # pas un dossier légitime ici, et c'est lui qui égarait le parcours.
        dossiers[:] = [d for d in dossiers
                       if d not in EXIFTOOL_SKIP_DIRS
                       and not d.startswith('.')
                       and '\\' not in d and '/' not in d]
        for f in fichiers:
            bas = f.lower()
            if bas.startswith('exiftool') and bas.endswith('.exe'):
                trouves.append(Path(racine) / f)
    for e in illisibles:
        print(f"  ⚠ Recherche d'ExifTool : « {getattr(e, 'filename', '?')} » "
              f"illisible ({type(e).__name__}) — ignoré.")
    return sorted(trouves)


def ensure_exiftool():
    w = shutil.which("exiftool")
    if w:
        return Path(w)
    # d'abord les emplacements probables (rapide, aucun parcours)
    for c in _exiftool_emplacements_probables():
        try:
            if not c.is_file():
                continue
            if c.name.lower() == "exiftool.exe":
                return c
            cible = c.with_name("exiftool.exe")
            c.rename(cible)
            return cible
        except OSError:
            continue
    # sinon seulement, un exiftool*.exe déposé ailleurs dans le projet
    hits = _exiftool_parcours_de_secours()
    for h in hits:
        if h.name.lower() == "exiftool.exe":
            return h
    for h in hits:
        target = h.with_name("exiftool.exe")
        h.rename(target)
        return target
    if list(SCRIPT_DIR.glob("Image-ExifTool-*")):
        print("  ⚠ Le dossier Image-ExifTool-* est la version SOURCE (Perl), inutilisable ici.")
        print("    Il faut le zip « Windows Executable » (exiftool-XX.XX_64.zip) depuis")
        print("    https://exiftool.org — extrais-le dans le dossier du projet.")
    # Dire ce qu'on a cherché AVANT de parler réseau : sans cette ligne, un
    # échec local se présentait sous la forme d'une erreur de téléchargement.
    print(f"  ℹ Aucun exiftool*.exe trouvé sous {SCRIPT_DIR} "
          f"(ni « exiftool » dans le PATH).")
    print("  ⬇ Téléchargement d'ExifTool (une seule fois)…")
    edir = SCRIPT_DIR / "exiftool"
    try:
        ver = urllib.request.urlopen(
            "https://exiftool.org/ver.txt", timeout=30).read().decode().strip()
        urls = [
            f"https://downloads.sourceforge.net/project/exiftool/exiftool-{ver}_64.zip",
            f"https://sourceforge.net/projects/exiftool/files/exiftool-{ver}_64.zip/download",
            f"https://exiftool.org/exiftool-{ver}_64.zip",
        ]
        data = None
        last_err = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=600) as r:
                    candidate = r.read()
                if zipfile.is_zipfile(io.BytesIO(candidate)):
                    data = candidate
                    break
                last_err = RuntimeError(f"réponse non-zip depuis {url.split('/')[2]}")
            except Exception as e:
                last_err = e
        if data is None:
            raise last_err or RuntimeError("téléchargement impossible")
        zpath = SCRIPT_DIR / "exiftool.zip"
        zpath.write_bytes(data)
        edir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(edir)
        zpath.unlink()
        for h in edir.rglob("*.exe"):
            if "exiftool" in h.name.lower():
                target = h.with_name("exiftool.exe")
                if h.name != "exiftool.exe":
                    h.rename(target)
                print(f"  ✓ ExifTool installé : {target}")
                return target
    except Exception as e:
        print(f"  ⚠ ExifTool indisponible ({e})")
        print("     → Plan B : écriture des mots-clés dans les JPEG via piexif.")
        print("     → Pour la solution complète (XMP/IPTC + HEIC) : télécharge le zip")
        print("       Windows 64-bit sur https://exiftool.org et extrais-le dans un")
        print(f"       dossier nommé « exiftool » à côté de server.py")
    return None


def _write_metadata_piexif(path, keywords, desc):
    """Plan B sans ExifTool : XPKeywords/XPComment (lus par l'Explorateur
    Windows) dans les JPEG, en pur Python."""
    if path.suffix.lower() not in ('.jpg', '.jpeg'):
        return False
    try:
        import piexif
        try:
            exif = piexif.load(str(path))
        except Exception:
            exif = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        kw = '; '.join(keywords)
        exif['0th'][piexif.ImageIFD.XPKeywords] = kw.encode('utf-16le') + b'\x00\x00'
        if desc:
            exif['0th'][piexif.ImageIFD.XPComment] = desc.encode('utf-16le') + b'\x00\x00'
        piexif.insert(piexif.dump(exif), str(path))
        return True
    except Exception as e:
        print(f"  ⚠ piexif ({path.name}): {e}")
        return False


def _run_exiftool(args, timeout=180):
    """Lance ExifTool via un argfile UTF-8 avec BOM — indispensable sous
    Windows pour que les accents survivent au passage des arguments."""
    import tempfile
    argfile = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                         encoding='utf-8-sig') as tf:
            tf.write('\n'.join(args))
            argfile = tf.name
        return subprocess.run([str(EXIFTOOL), "-@", argfile],
                              capture_output=True, text=True,
                              encoding='utf-8', errors='replace',
                              timeout=timeout)
    finally:
        if argfile:
            try:
                os.unlink(argfile)
            except OSError:
                pass


LAST_WRITE_ERROR = ""


def repair_file(path):
    """DERNIER RECOURS : reconstruit les métadonnées (`-all=` puis recopie).

    Ce que ça coûte, mesuré le 29/08 (`verifier_reparation_exif.py`) : le
    trailer Samsung part — la vidéo d'un Motion Photo, 2 à 3 Mo — et le profil
    ICC avec lui, même avec `--trailer:all`. Quatorze photos de 2024 l'ont subi
    le 28/08. D'où l'ordre désormais : d'abord `write_metadata`, qui sur un EXIF
    illisible réécrit XMP + IPTC SANS toucher l'EXIF (tout est gardé) ; ceci
    seulement si cette voie-là échoue aussi. La sauvegarde « nom.jpg_original »
    reste à côté du fichier — c'est elle qui porte ce qui est perdu."""
    if not EXIFTOOL:
        return False
    print(f"  🔧 Réparation EXIF (dernier recours, trailer et ICC PERDUS, "
          f"sauvegarde *_original) : {path.name}")
    r = _run_exiftool(["-all=", "-tagsfromfile", "@", "-all:all", "-unsafe",
                       "-charset", "filename=UTF8", str(path)])
    if r.returncode != 0:
        print(f"  ⚠ Réparation échouée : {r.stderr.strip()[:150]}")
        return False
    print(f"  ✓ Métadonnées reconstruites — sauvegarde *_original conservée")
    return True


def write_metadata(path, keywords, desc):
    """Écrit les mots-clés/description dans le fichier (XMP + IPTC + XPKeywords).

    Si ExifTool refuse parce qu'il ne sait pas RELIRE l'EXIF (« Error reading
    OtherImageStart data in IFD0 » — Motion Photo Samsung), second essai en
    XMP + IPTC seulement : l'EXIF n'est pas réécrit, le trailer (vidéo
    embarquée) et le profil ICC restent. Mesuré sur une copie le 29/08 :
    +501 octets, tout gardé. Un rattrapage ne détruit jamais plus que ce
    qu'il répare."""
    global LAST_WRITE_ERROR
    LAST_WRITE_ERROR = ""
    if not EXIFTOOL:
        return _write_metadata_piexif(path, keywords, desc)
    jpeg = path.suffix.lower() in ('.jpg', '.jpeg')
    try:
        r = _run_exiftool(ecriture_meta.args_ecriture(keywords, desc, jpeg) + [str(path)])
        if r.returncode == 0:
            return True
        err = r.stderr.strip()
        if ecriture_meta.exif_illisible(err):
            print(f"  ⚠ EXIF illisible pour ExifTool ({err[:80]}) → "
                  f"XMP + IPTC seulement, EXIF et trailer conservés : {path.name}")
            r2 = _run_exiftool(ecriture_meta.args_ecriture(keywords, desc, jpeg,
                                                           sans_exif=True) + [str(path)])
            if r2.returncode == 0:
                return True
            err = r2.stderr.strip() or err
        LAST_WRITE_ERROR = err[:200]
        print(f"  ⚠ ExifTool: {LAST_WRITE_ERROR}")
        return False
    except Exception as e:
        LAST_WRITE_ERROR = str(e)[:200]
        print(f"  ⚠ ExifTool: {e}")
        return False


# LA règle de lecture des tags nommés, une seule fois pour tout le serveur
# (module pur : `re` + `time`, aucun import lourd, invariant 3). Avant elle,
# six lectures coexistaient — trois normalisées, trois en casse sensible — et
# un « Personne:Flo » importé d'un fichier tagué ailleurs restait invisible à
# la moitié d'entre elles : jamais compté, jamais rattaché, jamais retiré
# (audit interne I7).
from tagging_meta import est_tag_nomme, parse_tag_nomme      # noqa: E402
import ecriture_meta                                          # noqa: E402


def _norm_import_kw(k):
    """Normalise un mot-clé importé d'un fichier. Les mots-clés IA sont en
    minuscules ; on aligne dessus SAUF les tags nommés « personne:… » et
    « animal:… » dont on PRÉSERVE la casse (sinon « personne:Nom » deviendrait
    « personne:nom » et ne correspondrait plus au nom dans people.json/pets.json).

    Le PRÉFIXE, lui, est canonisé : « Personne:Flo » entre comme
    « personne:Flo ». Le nom est ce qui doit survivre, pas la façon dont un
    autre logiciel a écrit l'étiquette — et un préfixe capitalisé rendait le
    tag invisible à toute lecture qui le cherche en minuscules."""
    s = str(k).strip()
    pn = parse_tag_nomme(s)
    if pn:
        return f"{pn[0]}:{pn[1]}"
    return s.lower()


def read_existing_metadata(paths, progress=False):
    """Lit les mots-clés déjà présents (fichiers tagués par un autre logiciel).

    Renvoie ({clé: (mots-clés, description)}, {clés VUES}). `vus` est vital ici :
    c'est cette lecture qui rapatrie les noms humains écrits dans les fichiers
    (`reimport_name_tags`). Confondre « lu, aucun mot-clé » avec « ExifTool n'a
    rien dit » ferait marquer la photo comme vérifiée alors qu'elle ne l'a pas
    été — et un nom présent dans le XMP ne serait PLUS JAMAIS repris."""
    result, vus = {}, set()
    if not EXIFTOOL or not paths:
        return result, vus
    for i in range(0, len(paths), 40):
        if progress and i and i % 800 == 0:
            print(f"    … {i}/{len(paths)} fichiers lus")
        chunk = paths[i:i + 40]
        args = ["-json", "-q", "-m", "-fast2",
                "-charset", "filename=UTF8",
                "-XMP-dc:Subject", "-IPTC:Keywords", "-XMP-dc:Description"]
        args += [str(p) for p in chunk]
        try:
            r = _run_exiftool(args, timeout=600)
            for item in json.loads(r.stdout or "[]"):
                key = _pkey(item.get("SourceFile", ""))
                vus.add(key)
                kw = item.get("Subject") or item.get("Keywords") or []
                if isinstance(kw, str):
                    kw = [kw]
                desc = item.get("Description") or ""
                if isinstance(desc, dict):
                    desc = str(list(desc.values())[0]) if desc else ""
                if kw:
                    result[key] = ([_norm_import_kw(k) for k in kw if str(k).strip()],
                                   str(desc).strip())
        except Exception:
            pass
    return result, vus


def read_gps(paths, progress=False):
    """Lit les coordonnées GPS (lat, lon) des fichiers via ExifTool.
    Retourne ({clé_index: [lat, lon]}, {clés VUES}) ; les fichiers sans GPS sont
    absents du premier dictionnaire mais présents dans le second.
    -n = valeurs numériques ; le groupe Composite applique déjà le signe
    N/S et E/W, on obtient donc des degrés décimaux signés.

    `vus` = fichiers sur lesquels ExifTool s'est VRAIMENT prononcé. Sans cette
    distinction, un lot raté (NAS muet, timeout) est indiscernable de « lu,
    rien trouvé » et le backfill écrit None partout — condamnant les photos
    pour toujours. Même garde-fou que `read_meta_and_gps` (voir
    `tagging_meta.valeurs_a_ecrire`)."""
    result, vus = {}, set()
    if not EXIFTOOL or not paths:
        return result, vus
    for i in range(0, len(paths), 60):
        if progress and i and i % 1200 == 0:
            print(f"    … GPS {i}/{len(paths)} fichiers lus")
        chunk = paths[i:i + 60]
        args = ["-json", "-n", "-q", "-m", "-fast2",
                "-charset", "filename=UTF8",
                "-Composite:GPSLatitude", "-Composite:GPSLongitude"]
        args += [str(p) for p in chunk]
        try:
            r = _run_exiftool(args, timeout=600)
            for item in json.loads(r.stdout or "[]"):
                key = _pkey(item.get("SourceFile", ""))
                vus.add(key)
                lat, lon = item.get("GPSLatitude"), item.get("GPSLongitude")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
                        result[key] = [round(float(lat), 6), round(float(lon), 6)]
        except Exception:
            pass
    return result, vus


def read_meta_and_gps(path, cle=None):
    """Lit en UN SEUL appel exiftool les mots-clés/description existants, le
    GPS ET la date de prise de vue d'un fichier. Fusionne
    `read_existing_metadata` + `read_gps` + `read_dates` pour le worker de
    tagging : une lecture NAS et un process exiftool de moins par photo. Le GPS
    est inchangé par l'écriture des mots-clés (`write_metadata` ne touche que
    Keywords/Description), donc lire avant l'écriture donne la même valeur
    qu'après. Appelé AVANT le VLM depuis la version v2ctx : les faits lus
    partent dans le prompt (Knowledge Builder amont).

    `cle` : la clé d'index de la photo, sur laquelle porte l'arbitrage de la
    date (voir plus bas). À défaut, le chemin sert de repli.

    Retourne (kw_list|None, desc, gps|None, taken_epoch|None, ok). `ok` est
    True seulement si exiftool a VRAIMENT lu le fichier : il distingue « lu,
    rien trouvé » (gps/taken absents pour de bon → l'entrée peut le mémoriser)
    d'un échec transitoire (NAS, timeout → ne PAS écrire gps/taken None, sinon
    les backfills sautent la photo pour toujours). Le parsing pur (testé) vit
    dans `tagging_meta` (`parse_meta_gps_item` + `champs_dates_item` +
    `date_fiable`)."""
    if not EXIFTOOL:
        return None, "", None, None, False
    import tagging_meta
    args = ["-json", "-n", "-q", "-m", "-fast2",
            "-charset", "filename=UTF8",
            "-XMP-dc:Subject", "-IPTC:Keywords", "-XMP-dc:Description",
            "-Composite:GPSLatitude", "-Composite:GPSLongitude",
            "-DateTimeOriginal", "-CreateDate", "-ModifyDate", str(path)]
    try:
        r = _run_exiftool(args)
        items = json.loads(r.stdout or "[]")
        if items:
            kw, desc, gps = tagging_meta.parse_meta_gps_item(items[0])
            # MÊME arbitrage que le backfill par lots : la date du scan d'un
            # vieux tirage n'est pas sa date de prise de vue. Sans cela, une
            # photo recevrait une date différente selon le chemin de code qui
            # l'a touchée — tagging ou backfill.
            # L'arbitrage porte sur la CLÉ D'INDEX, pas sur le chemin absolu :
            # c'est elle que `_best_time`/`_path_year` regardent ensuite. Pour
            # une photo d'Uploads (clé = nom nu), juger sur le chemin absolu
            # ferait intervenir une année du dossier d'installation — et la
            # même photo recevrait deux dates selon le chemin de code.
            taken = tagging_meta.date_fiable(
                tagging_meta.champs_dates_item(items[0]),
                _path_years(cle if cle is not None else str(path)))
            return kw, desc, gps, taken, True
        return None, "", None, None, False
    except Exception:
        return None, "", None, None, False


def _merge_named_tags(kw_fr, existing_kw):
    """Réintègre les tags nommés (personne:/animal:) déjà présents dans le
    fichier — invariant sacré : jamais perdre un nom humain. Délègue à la
    logique pure testée (`tagging_meta.merge_named_tags`)."""
    import tagging_meta
    return tagging_meta.merge_named_tags(kw_fr, existing_kw)


def _noms_attendus(key):
    """Tags nommés attendus/retirés sur une photo d'après les sources EN
    MÉMOIRE : fiches personnes/animaux (champs 'faces' et 'exclude', comme
    reconcile_named_tags) et entrée d'index courante. Aucune I/O.

    Sert de re-fusion juste avant l'écriture du worker de tagging : depuis que
    la lecture exiftool passe AVANT le VLM (v2ctx), la fenêtre lecture→écriture
    couvre tout l'appel Ollama (secondes, jusqu'à 600 s). Deux courses couvertes,
    dans les deux sens : un nom ATTRIBUÉ pendant l'appel serait écrasé par la
    fusion depuis des mots-clés périmés (invariant : jamais perdre un nom
    humain) ; un nom RETIRÉ pendant l'appel serait ressuscité par cette même
    fusion (exclude = autorité, partout).

    Renvoie (tags_attendus, tags_exclus_lower)."""
    tags, exclus = [], set()
    try:
        for store, prefix in ((PEOPLE_STORE, 'personne'), (PETS_STORE, 'animal')):
            for pe in list(store.data.values()):
                if not isinstance(pe, dict) or not pe.get('name'):
                    continue
                tag = f"{prefix}:{pe['name']}"
                if key in set(pe.get('exclude') or []):
                    exclus.add(tag.lower())
                    continue
                for kf in (pe.get('faces') or []):
                    if (isinstance(kf, (list, tuple)) and len(kf) == 2
                            and kf[0] == key):
                        tags.append(tag)
                        break
        # La FICHE fait foi sur l'orthographe : un `animal:luna` d'index ne
        # s'ajoute pas à côté du `animal:Luna` d'une fiche, sinon le même
        # animal est nommé deux fois (2 photos le 20/08) — et la fusion
        # RÉÉCRIT le doublon dans l'index à chaque tagging.
        deja = {t.lower() for t in tags}
        e = STORE.data.get(key)
        if isinstance(e, dict):
            for t in (e.get('kw_fr') or []):
                tl = str(t).lower()
                if ((tl.startswith('personne:') or tl.startswith('animal:'))
                        and tl not in exclus and tl not in deja):
                    deja.add(tl)
                    tags.append(t)
    except Exception:
        pass
    return tags, exclus


def _lieu_pour_cle(k):
    """Lieu connu d'une photo, pour le Knowledge Builder : géocodage inverse
    précalculé (gps_places.json, si gps_place est activé) d'abord, sinon lieu
    déduit du chemin (lieux_connus + _lieu_plausible — même logique que le
    renommage). Renvoie (libellé, source) ou (None, None). Aucun accès NAS,
    aucun modèle : lectures de caches en mémoire."""
    try:
        g = gps_places_connus().get(k)
        if g:
            return g, 'gps'
    except Exception:
        pass
    try:
        lx = lieux_connus()
    except Exception:
        lx = {}
    if lx:
        try:
            import faits_vue
            lieu = faits_vue.lieu_par_segments(k, lx, media_roots())
            if lieu:
                return lieu, 'chemin'
        except Exception:
            pass
    return None, None


def _assertions_pour(key, existing_kw, taken):
    """Knowledge Builder AMONT : assemble les faits déjà connus sur une photo
    AVANT l'appel au VLM (prompt v2ctx). Zéro calcul GPU, zéro lecture NAS :
    tout vient des mots-clés déjà lus dans le fichier (`existing_kw`), de
    l'ANIMAL_STORE, des caches lieux et de la date EXIF (`taken`) — avec repli
    nom de fichier puis année du dossier, SANS repli mtime (une date fausse
    affirmée au modèle est une graine d'hallucination, pas un fait).

    Renvoie le dict d'assertions attendu par tagging_meta.bloc_assertions /
    prompt_tagging / faits_structures (sources incluses, pour la provenance)."""
    import tagging_meta
    persons, animals = tagging_meta.noms_depuis_kw(existing_kw)
    especes = []
    try:
        ae = ANIMAL_STORE.data.get(key)
        if isinstance(ae, dict):
            especes = sorted({a.get('species') for a in (ae.get('animals') or [])
                              if a.get('species')})
    except Exception:
        pass
    lieu, lieu_src = _lieu_pour_cle(key)
    date_txt = date_src = None
    if taken:
        date_txt, date_src = tagging_meta.format_date_fr(taken), 'exif'
    else:
        fn = _fname_time(Path(key).name)
        if fn:
            date_txt, date_src = tagging_meta.format_date_fr(fn), 'nom du fichier'
        else:
            py = _path_year(key)
            if py:
                date_txt, date_src = str(time.localtime(py).tm_year), 'annee du dossier'
    plain = [t for t in (existing_kw or [])
             if not (str(t).lower().startswith('personne:')
                     or str(t).lower().startswith('animal:'))]
    return {'key': key, 'persons': persons, 'animals': animals,
            'species': especes, 'lieu': lieu, 'lieu_src': lieu_src,
            'date': date_txt, 'date_src': date_src, 'tags_fr': plain[:12],
            'noms_src': 'xmp'}


def _tagging_pipe_counts():
    """Répartition des entrées taguées par version de pipeline (audit D) : les
    entrées antérieures à l'estampillage comptent comme « v0 ». Rendu visible
    dans /reglages — plus jamais d'index mixte silencieux. Lecture seule sur
    une copie instantanée du dict (pas de lock nécessaire)."""
    c = {}
    for e in list(STORE.data.values()):
        if isinstance(e, dict) and not e.get('failed'):
            v = e.get('pipe') or 'v0'
            c[v] = c.get(v, 0) + 1
    return c


# État des deux backfills (dates, GPS). Ils sont morts EN SILENCE à chaque
# démarrage pendant des mois (voir `_attendre_exiftool`) : 42 060 entrées sur
# 43 067 n'avaient jamais été lues, sans qu'aucun écran ne le dise. Un travail
# de fond qui ne rend pas de comptes finit par ne plus travailler du tout —
# même leçon que la boucle de maintenance (audit O5) et que `backup_verify`.
# Rendu dans /reglages.
# `muets` : fichiers d'un lot dont ExifTool n'a rien dit (timeout, NAS qui
# décroche). Ils ne sont PAS décidés — c'est voulu — mais ils repasseront à
# chaque démarrage : sans ce compteur, une boucle perpétuelle sur un lot
# pathologique se déguiserait en « terminé ».
BACKFILL_STATE = {
    "dates": {"etat": "au demarrage", "todo": 0, "faits": 0, "trouves": 0,
              "muets": 0, "fini_at": 0.0, "erreur": ""},
    "gps": {"etat": "au demarrage", "todo": 0, "faits": 0, "trouves": 0,
            "muets": 0, "fini_at": 0.0, "erreur": ""},
    "noms": {"etat": "au demarrage", "todo": 0, "faits": 0, "trouves": 0,
             "muets": 0, "fini_at": 0.0, "erreur": ""},
}


def _backfill(nom, fn):
    """Lance un backfill en rendant compte de sa mort éventuelle.

    Un thread daemon qui lève une exception disparaît sans un mot : c'est le
    deuxième moyen (après le renoncement à ExifTool) pour que ce travail cesse
    en silence. Ici l'échec devient un état lisible dans /reglages."""
    try:
        fn()
    except Exception as e:                                    # noqa: BLE001
        BACKFILL_STATE[nom]["etat"] = "erreur"
        BACKFILL_STATE[nom]["erreur"] = str(e)[:200]
        print(f"  ⚠ Backfill {nom} interrompu : {e}")
    except BaseException as e:                                # noqa: BLE001
        # Laisser l'état à « en cours » ferait attendre les autres tâches
        # jusqu'à leur plafond de 6 h. On note, puis on laisse remonter.
        BACKFILL_STATE[nom]["etat"] = "erreur"
        BACKFILL_STATE[nom]["erreur"] = type(e).__name__
        raise


def _attendre_exiftool(quoi, delai=1800):
    """Attend qu'ExifTool soit prêt, au lieu de renoncer tout de suite.

    LE BUG (13/08/2026) : `EXIFTOOL` est affecté par `maintenance_loop`, lancé
    dans le même souffle que les backfills. Ceux-ci testaient `if not EXIFTOOL:
    return` AVANT leur `time.sleep()` — donc quelques microsecondes après le
    démarrage, alors que `ensure_exiftool()` (which + rglob, parfois un
    téléchargement) n'avait pas encore rendu la main. Les deux tâches se
    terminaient instantanément, sans un mot, à CHAQUE démarrage depuis
    toujours. Coût observé : 12 407 photos sans aucune date au jour près
    (29 % de la photothèque) alors que 27 fichiers sur 30 en portent une dans
    leur EXIF — mesuré par `diagnostic_dates.py`.

    Le délai couvre le PIRE cas d'`ensure_exiftool()` : première installation,
    ExifTool absent du PATH, téléchargement lent (ver.txt + jusqu'à trois URL
    à 600 s de timeout). Abandonner plus tôt condamnerait la session entière
    alors que l'outil finit par arriver.

    Renvoie True si ExifTool est disponible dans le délai imparti."""
    fin = time.time() + delai
    while time.time() < fin:
        if EXIFTOOL:
            return True
        time.sleep(1)
    BACKFILL_STATE[quoi]["etat"] = "ExifTool indisponible"
    print(f"  ⚠ Backfill {quoi} : ExifTool toujours indisponible après "
          f"{delai} s — tâche abandonnée pour cette session.")
    return False


# États depuis lesquels une tâche va encore lire le NAS — donc pour lesquels
# une autre doit patienter. « en attente des … » en fait partie : sans lui, la
# passe des noms doublerait le GPS pendant que celui-ci attend son tour.
ETATS_EN_COURS = ("au demarrage", "en attente des dates", "inventaire",
                  "en cours")


def _attendre_backfill(autre, delai=6 * 3600, moi=None):
    """Attend qu'un autre backfill ait fini son passage sur le NAS.

    Les deux tâches lisent les MÊMES ~42 000 fichiers : les lancer ensemble
    double la charge du NAS pour rien et se paie sur la navigation. Les dates
    passent d'abord — c'est ce qui manque à la chronologie ; le GPS suit."""
    fin = time.time() + delai
    while time.time() < fin:
        if BACKFILL_STATE[autre]["etat"] not in ETATS_EN_COURS:
            return
        time.sleep(10)
    # Dépassement : on part quand même (mieux vaut deux passages simultanés
    # qu'un travail jamais fait), mais on le DIT — et pas seulement dans une
    # console que personne ne relit : /reglages doit le montrer, sinon la
    # sérialisation semblerait tenue alors qu'elle a cédé.
    if moi:
        BACKFILL_STATE[moi]["erreur"] = (
            f"attente de « {autre} » dépassée — lancé en parallèle")
    print(f"  ℹ Backfill : attente de « {autre} » dépassée ({delai // 3600} h) "
          f"— démarrage en parallèle.")


def backfill_gps():
    """Complète l'index en lisant le GPS des photos déjà taguées qui n'ont
    pas encore de champ 'gps'. Tourne une fois au démarrage, en tâche de
    fond, par lots. Marque gps=None quand aucune coordonnée n'est présente
    pour ne pas relire le fichier au prochain démarrage — mais seulement pour
    les fichiers dont ExifTool a vraiment parlé (`tagging_meta.valeurs_a_ecrire`)."""
    import tagging_meta
    etat = BACKFILL_STATE["gps"]
    time.sleep(8)  # laisse le serveur démarrer avant de solliciter le NAS
    if not _attendre_exiftool("gps"):
        return
    # Dernier servi, volontairement : la carte attend, les noms non. L'ordre
    # est dates -> noms -> GPS, du plus structurant au plus accessoire.
    etat["etat"] = "en attente des dates"
    _attendre_backfill("dates", moi="gps")
    _attendre_backfill("noms", moi="gps")
    etat["etat"] = "inventaire"
    todo = []  # (clé_index, chemin)
    for n, (k, e) in enumerate(list(STORE.data.items())):
        if not isinstance(e, dict) or e.get('failed') or 'gps' in e:
            continue
        p = _resolve_key(k)
        if p.suffix.lower() not in IMAGE_EXT:
            continue
        # L'inventaire fait un stat() par photo SUR LE NAS : à 42 000 entrées
        # il dure des minutes et l'UI passe d'abord (invariant « l'UI cède la
        # priorité au NAS » — il ne valait que pour la boucle de lecture).
        if n % 200 == 0:
            while ui_recent():
                time.sleep(3)
        try:
            if p.exists():
                todo.append((k, p))
        except OSError:
            continue
    etat["todo"] = len(todo)
    if not todo:
        etat["etat"] = "rien a lire"
        return
    print(f"  🗺  Backfill GPS : {len(todo)} photos à lire…")
    etat["etat"] = "en cours"
    found = 0
    for i in range(0, len(todo), 60):
        while ui_recent():
            time.sleep(3)
        batch = todo[i:i + 60]
        gps, vus = read_gps([p for _k, p in batch])
        a_ecrire = tagging_meta.valeurs_a_ecrire(
            [(k, _pkey(p)) for k, p in batch], gps, vus)
        etat["muets"] += len(batch) - len(a_ecrire)
        with STORE.lock:
            for k, g in a_ecrire.items():
                e = STORE.data.get(k)
                if not isinstance(e, dict):
                    continue
                e['gps'] = g if g else None
                if g:
                    found += 1
            STORE._save()
        etat["faits"] = min(i + 60, len(todo))
        etat["trouves"] = found
        time.sleep(0.2)  # ménage le NAS/CPU
    etat["etat"] = "termine"
    etat["fini_at"] = time.time()
    print(f"  ✓ Backfill GPS terminé : {found} photos géolocalisées")


def _parse_exif_dt(s):
    """Convertit une date EXIF « 2018:12:11 23:01:48 » en timestamp epoch local.
    Renvoie None si absente/invalide (ou année aberrante)."""
    if not s or not isinstance(s, str):
        return None
    m = re.match(r'\s*(\d{4}):(\d{2}):(\d{2})[ T]?(\d{2})?:?(\d{2})?:?(\d{2})?', s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    hh, mm, ss = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
    try:
        return time.mktime((y, mo, d, hh, mm, ss, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


def _fname_time(name):
    """Date encodée dans le nom de fichier (20181211_230148, IMG_20181227…).
    Renvoie un timestamp epoch ou None."""
    m = re.search(r'(19\d{2}|20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})'
                  r'(?:[-_ .T]?(\d{2})[-_.]?(\d{2})[-_.]?(\d{2}))?', name)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    hh, mm, ss = int(m.group(4) or 12), int(m.group(5) or 0), int(m.group(6) or 0)
    try:
        return time.mktime((y, mo, d, hh, mm, ss, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


# Plancher des années lues dans un CHEMIN. 1990 était la valeur d'origine : elle
# convient à des dates d'APPAREIL PHOTO, pas à des noms de DOSSIERS. Mesuré le
# 14/08 : elle exilait les années 80 de la photothèque. Un dossier « 1985 » ne
# rendait AUCUNE année, avec deux dégâts en cascade — (1) `_path_year` rendait 0,
# donc `_best_time` tombait sur `mtime` et 714 photos de 1982-1989 étaient datées
# de 2026, la date de COPIE sur le NAS ; (2) le garde-fou anti-scan de
# `date_fiable` se désarme quand le chemin n'a aucune année (« rien à
# contredire ») — les 13 photos de « 1985\19850601 … » portent encore la date de
# la séance de numérisation, 16/11/2006. Au-dessous de 1970, `time.mktime` refuse
# sous Windows : `_path_year` rend alors 0 et la photo garde son repli — dégradé,
# jamais cassé.
ANNEE_CHEMIN_MIN, ANNEE_CHEMIN_MAX = 1900, 2100


def _path_years(key):
    """TOUTES les années (19xx/20xx) portées par les DOSSIERS de la clé, en
    entiers — le NOM DE FICHIER est exclu.

    L'ensemble, pas seulement la plus ancienne : un dossier peut porter une
    PLAGE (« Photos 2005-2010\\2008\\… ») et exiger l'égalité avec le seul
    minimum ferait reculer la photo de trois ans. Sert de garde-fou aux dates
    EXIF des photos scannées (`tagging_meta.date_fiable`).

    Le nom de fichier est écarté pour la raison déjà écrite dans
    `renommage_facts.path_year` : un numéro de séquence de scanner n'est pas une
    année. « 119-1908_IMG.JPG » dans un dossier 2002 rendait {1908, 2002}, et
    `_path_year_num` prend le `min()` — la photo reculait de 94 ans. Invisible
    jusqu'ici parce que le plancher 1990 jetait le 1908 par accident ; en le
    descendant, il fallait boucher le trou pour de bon. Mesuré sur 19 384
    fichiers (Photos Papa, Photos Flo, 2010, _A TRIER) : 38 photos tirées en
    arrière par leur nom, et AUCUNE ne perd son repli en excluant le nom — une
    date vraiment portée par le nom passe de toute façon avant, par
    `_fname_time` (`_best_time`, branche 1)."""
    k = str(key).replace('/', '\\')
    dossiers = k.rsplit('\\', 1)[0] if '\\' in k else ''
    return {int(y) for y in re.findall(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)', dossiers)
            if ANNEE_CHEMIN_MIN <= int(y) <= ANNEE_CHEMIN_MAX}


def _path_year_num(key):
    """Année la plus ancienne du chemin, en entier (0 si aucune) — le repli
    chronologique historique."""
    yrs = _path_years(key)
    return min(yrs) if yrs else 0


def _path_year(key):
    """Année (19xx/20xx) trouvée dans le CHEMIN (dossiers datés « …\\2016\\… »).
    Repli approximatif quand ni EXIF ni nom de fichier n'ont de date. Renvoie un
    timestamp au 1er janvier de la plus ancienne année trouvée, ou 0."""
    an = _path_year_num(key)
    if not an:
        return 0
    try:
        return time.mktime((an, 1, 1, 12, 0, 0, 0, 0, -1))
    except (ValueError, OverflowError):
        return 0


def _best_time(key, e):
    """Date de PRISE DE VUE d'une photo, par ordre de FIABILITÉ :
    1) dates PRÉCISES (EXIF sauvegardé + date dans le nom de fichier) → on prend
       la plus ancienne (évite les dates de MODIFICATION, faussées par le tagging);
    2) sinon, l'année du dossier (approx. 1er janvier) ;
    3) en tout dernier recours seulement, le mtime (peu fiable).
    Renvoie un timestamp epoch (0 si rien).

    La branche 1 est DÉLÉGUÉE à `_epoch_precis` depuis le 19/08. Elle en était
    la copie — même minimum sur les mêmes deux sources — et cette copie a
    survécu au garde-fou de la date de SCAN : la recherche datait déjà une photo
    de « Photos Papa\\1985 » de 1985, pendant que la galerie la classait en
    2006. 70 photos, une seule règle désormais."""
    precise = _epoch_precis(key, e)
    if precise:
        return precise
    py = _path_year(key)
    if py:
        return py
    m = e.get('mtime') if isinstance(e, dict) else None
    if isinstance(m, (int, float)) and m > 0:
        return m
    return 0


def read_dates(paths, progress=False):
    """Lit les dates de prise de vue via ExifTool. Renvoie
    ({clé: {'o': epoch|None, 'm': epoch|None}}, {clés VUES}).

    Les champs restent SÉPARÉS : `o` = prise de vue (DateTimeOriginal /
    CreateDate, la plus ancienne des deux), `m` = dernière écriture du fichier
    (ModifyDate). Les aplatir en un seul `min()` ferait passer la date de SCAN
    d'un tirage de 1995 pour sa date de prise de vue. L'arbitrage vit dans
    `tagging_meta.date_fiable` (pur, testé).

    `vus` : voir `read_gps`. Un fichier absent de la réponse d'ExifTool n'est
    PAS décidé — il sera représenté au prochain démarrage plutôt que marqué
    « sans date » à tort."""
    import tagging_meta
    result, vus = {}, set()
    if not EXIFTOOL or not paths:
        return result, vus
    for i in range(0, len(paths), 60):
        if progress and i and i % 1200 == 0:
            print(f"    … dates {i}/{len(paths)} fichiers lus")
        chunk = paths[i:i + 60]
        args = ["-json", "-q", "-m", "-fast2", "-charset", "filename=UTF8",
                "-DateTimeOriginal", "-CreateDate", "-ModifyDate"]
        args += [str(p) for p in chunk]
        try:
            r = _run_exiftool(args, timeout=600)
            for item in json.loads(r.stdout or "[]"):
                key = _pkey(item.get("SourceFile", ""))
                vus.add(key)
                champs = tagging_meta.champs_dates_item(item)
                if champs['o'] or champs['m']:
                    result[key] = champs
        except Exception:
            pass
    return result, vus


def backfill_dates():
    """Complète l'index avec la date de prise de vue EXIF ('taken') des photos
    qui ne l'ont pas encore. Tâche de fond, par lots, une fois au démarrage.
    Marque taken=None quand aucune date EXIF n'est présente (le nom de fichier et
    le mtime servent alors de repli via _best_time) — mais UNIQUEMENT pour les
    fichiers dont ExifTool a vraiment parlé, sans quoi un lot raté condamnerait
    ces photos pour toujours (`tagging_meta.valeurs_a_ecrire`)."""
    import tagging_meta
    etat = BACKFILL_STATE["dates"]
    time.sleep(10)  # laisse le serveur démarrer ; le GPS attend CE passage-ci
    if not _attendre_exiftool("dates"):
        return
    etat["etat"] = "inventaire"
    todo = []
    for n, (k, e) in enumerate(list(STORE.data.items())):
        if not isinstance(e, dict) or e.get('failed') or 'taken' in e:
            continue
        p = _resolve_key(k)
        if p.suffix.lower() not in IMAGE_EXT:
            continue
        if n % 200 == 0:            # voir backfill_gps : l'UI passe d'abord
            while ui_recent():
                time.sleep(3)
        try:
            if p.exists():
                todo.append((k, p))
        except OSError:
            continue
    etat["todo"] = len(todo)
    if not todo:
        etat["etat"] = "rien a lire"
        return
    print(f"  📅 Backfill dates de prise de vue : {len(todo)} photos à lire…")
    etat["etat"] = "en cours"
    found = 0
    for i in range(0, len(todo), 60):
        # cède le NAS seulement quand TU navigues (lecture EXIF = I/O léger, ok en
        # parallèle du tagging Ollama). Prioritaire : sans vraie date de prise de
        # vue, le tri chronologique se dégrade.
        while ui_recent():
            time.sleep(3)
        batch = todo[i:i + 60]
        bruts, vus = read_dates([p for _k, p in batch])
        # Arbitrage par photo : la date du SCAN d'un vieux tirage ne doit pas
        # passer pour sa date de prise de vue (tagging_meta.date_fiable).
        dates = {}
        for _k, _p in batch:
            _pk = _pkey(_p)
            _d = tagging_meta.date_fiable(bruts.get(_pk) or {},
                                          _path_years(_k))
            if _d:
                dates[_pk] = _d
        a_ecrire = tagging_meta.valeurs_a_ecrire(
            [(k, _pkey(p)) for k, p in batch], dates, vus)
        etat["muets"] += len(batch) - len(a_ecrire)
        with STORE.lock:
            for k, dt in a_ecrire.items():
                e = STORE.data.get(k)
                if not isinstance(e, dict):
                    continue
                e['taken'] = dt if dt else None
                if dt:
                    found += 1
            if (i // 60) % 10 == 0:      # sauvegarde tous les ~10 lots seulement
                STORE._save()
        etat["faits"] = min(i + 60, len(todo))
        etat["trouves"] = found
        time.sleep(0.2)
    STORE.save()
    etat["etat"] = "termine"
    etat["fini_at"] = time.time()
    print(f"  ✓ Backfill dates terminé : {found} dates de prise de vue lues")


# ────────────────────────── Tagging IA ──────────────────────────

def image_to_b64(path):
    if PIL_OK:
        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                im = im.convert("RGB")
                im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=85)
                return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            # fichier endommagé : ne PAS l'envoyer brut à Ollama
            raise TagError(f"image illisible ({str(e)[:120]})")
    if path.suffix.lower() in ('.heic', '.heif'):
        raise TagError("HEIC illisible (installer pillow-heif)")
    return base64.b64encode(path.read_bytes()).decode()


def ollama_generate(b64, prompt=None):
    """Appelle le VLM. `prompt` = prompt contextualisé par photo (v2ctx, bâti
    par tagging_meta.prompt_tagging) ; à défaut, repli sur le PROMPT V0."""
    payload = {
        "model": MODEL,
        "prompt": prompt or PROMPT,
        "images": [b64],
        "stream": False,
        "format": "json",
        "think": False,   # qwen3-vl:4b est un modèle « thinking » : on le désactive
        "options": {
            "temperature": 0.2,     # factuel, peu de créativité
            "num_predict": 256,     # plafond de sortie : le JSON tient largement
            "num_ctx": 4096,        # contexte réduit = moins de VRAM occupée
            "repeat_penalty": 1.05, # anti-boucles léger (cf. article XDA)
        },
        "keep_alive": "30m",
    }
    req = urllib.request.Request(
        OLLAMA_URL + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            out = json.loads(r.read())
        resp = (out.get("response") or "").strip()
        if not resp:
            # certains modèles « thinking » mettent tout dans ce champ
            resp = (out.get("thinking") or "").strip()
        return resp
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        raise TagError(f"Ollama HTTP {e.code}: {body}")
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        raise OllamaDown(str(e))


def _norm_keywords(lst):
    if not isinstance(lst, list):
        return []
    out, seen = [], set()
    for k in lst:
        k = str(k).replace('_', ' ')
        k = re.sub(r'\s+', ' ', k.strip().lower())
        if k and len(k) <= 40 and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:12]


def _salvage_tags(raw):
    """Récupère les mots-clés d'une réponse JSON tronquée (ex. reçu/document
    bavard qui dépasse le plafond de sortie). On extrait uniquement les chaînes
    complètes (paires de guillemets) des tableaux ; la dernière, coupée, est
    ignorée."""
    def arr(key):
        m = re.search(r'"' + key + r'"\s*:\s*\[(.*?)(?:\]|$)', raw, re.S)
        if not m:
            return []
        return re.findall(r'"([^"]+)"', m.group(1))
    kw_en = _norm_keywords(arr("keywords_en"))
    kw_fr = _norm_keywords(arr("keywords_fr"))
    dm = re.search(r'"description_fr"\s*:\s*"([^"]*)"', raw)
    desc = (dm.group(1) if dm else "").strip()[:300]
    return kw_fr, kw_en, desc


def parse_tags(raw):
    raw = (raw or "").strip()
    if not raw:
        raise TagError("réponse vide du modèle (thinking ?)")
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                data = None
    if data is not None:
        kw_en = _norm_keywords(data.get("keywords_en"))
        kw_fr = _norm_keywords(data.get("keywords_fr"))
        desc = str(data.get("description_fr") or "").strip()[:300]
    else:
        # réponse tronquée : on récupère ce qui est exploitable
        kw_fr, kw_en, desc = _salvage_tags(raw)
    if not kw_en and not kw_fr:
        raise TagError(f"aucun mot-clé exploitable: {raw[:100]}")
    return kw_fr, kw_en, desc


def _marquer_echec(name, raison):
    """Note l'échec d'un fichier dans l'index — sans JAMAIS tuer son appelant.

    Le 27/08 à 23:42:50, c'est cette écriture-ci qui a porté le coup fatal.
    `STORE.set` venait d'échouer sur « database is locked » ; le gestionnaire
    d'erreur du tagueur a alors réécrit dans la MÊME base, encore verrouillée,
    et cette seconde erreur — hors de tout `except` — a tué le thread. La file
    s'est remplie, le serveur avait l'air parfaitement vivant, et huit heures
    de tagging sont parties.

    La règle qui en sort : **un rattrapage ne doit jamais dépendre de la
    ressource qui vient de tomber.** Ne pas pouvoir noter l'échec est
    regrettable ; mourir en essayant de le noter fait perdre tout le reste.
    Renvoie True si la note est passée, False si l'index était indisponible."""
    try:
        STORE.set(name, {"failed": True, "error": str(raison)[:200],
                         "at": time.time()})
        return True
    except Exception as e:
        print(f"  ⚠ {name}: échec impossible à noter ({e}) — index "
              f"indisponible, la photo sera revue au prochain scan")
        return False


def tagger_worker():
    fails = {}
    downs = {}
    # Ce thread ne fait qu'une chose : toutes ses entrees d'index relevent du
    # tagging. Motif permanent -> les milliers d'AJOUTS legitimes ne noient pas
    # le bucket « non declare ». Contrepartie assumee : un RETRAIT fait ici
    # serait etiquete « tagging » plutot que non declare -- mais une ligne
    # « tagging » avec des retraits non nuls est justement une anomalie visible,
    # ce worker n'etant cense qu'ajouter.
    # Les autres threads (maintenance, HTTP) restent volontairement SANS motif
    # permanent : c'est la qu'un oubli non declare doit pouvoir se montrer.
    REGISTRE.motif_du_thread('tagging')
    while True:
        name = TAG_QUEUE.get()
        try:
            path = _resolve_key(name)
            if not path.exists() or STORE.has(name) or _is_hidden_path(path):
                pending_done(name)
                continue
            print(f"  🏷  Analyse IA : {name}")
            t0 = time.time()
            b64 = image_to_b64(path)
            # Knowledge Builder AMONT : la lecture exiftool (mots-clés existants
            # + GPS + date, toujours UN seul appel) passe AVANT le VLM — les
            # faits connus (noms XMP, espèce, lieu, date) partent DANS le prompt
            # v2ctx « assertions en contexte, sans impératif de noms »
            # (ADOPTÉE 12/08, eval/DECISIONS.md).
            import tagging_meta
            existing_kw, gps, taken, meta_ok = None, None, None, False
            try:
                existing_kw, _exdesc, gps, taken, meta_ok = read_meta_and_gps(
                    path, cle=name)
            except Exception:
                pass
            faits = _assertions_pour(name, existing_kw, taken)
            raw = ollama_generate(b64, tagging_meta.prompt_tagging(faits))
            kw_fr, kw_en, desc = parse_tags(raw)
            # PÉRENNITÉ : ne jamais perdre les tags nommés (personne:/animal:)
            # déjà écrits dans le fichier — un ré-tagging IA les ré-intègre au
            # lieu de les écraser (logique pure testée : tagging_meta). C'est la
            # SEULE voie des noms vers la sortie : jamais via le prompt. La
            # re-fusion depuis les fiches/index EN MÉMOIRE (_noms_attendus)
            # couvre les deux courses pendant l'appel Ollama : nom attribué
            # (sinon écrasé) et nom retiré (sinon ressuscité — exclude gagne).
            attendus, exclus = _noms_attendus(name)
            if exclus and existing_kw:
                existing_kw = [t for t in existing_kw
                               if str(t).lower() not in exclus]
            kw_fr = _merge_named_tags(kw_fr, existing_kw)
            kw_fr = _merge_named_tags(kw_fr, attendus)
            merged = list(dict.fromkeys(kw_fr + kw_en))
            in_file = write_metadata(path, merged, desc)
            size, mtime = _stat_of(path)   # après écriture des métadonnées
            entry = {"kw_fr": kw_fr, "kw_en": kw_en, "desc": desc,
                     "in_file": in_file, "at": time.time(),
                     "size": size, "mtime": mtime,
                     "pipe": TAGGING_PIPELINE_VERSION}
            if meta_ok:
                # « lu, absent » se mémorise (les backfills n'y reviendront
                # pas) ; un échec transitoire laisse les clés absentes → les
                # backfills GPS/dates retenteront plus tard.
                entry["gps"] = gps if gps else None
                entry["taken"] = taken if taken else None
            # Knowledge Builder AVAL : faits structurés et sourcés (provenance),
            # fusion déterministe — jamais issus du texte du LLM.
            fs = tagging_meta.faits_structures(faits)
            if fs:
                entry["faits"] = fs
            if not in_file:
                entry["write_fails"] = 1
            STORE.set(name, entry)
            pending_done(name)
            fails.pop(name, None)
            print(f"  ✓ {name} tagué en {time.time() - t0:.0f}s : "
                  f"{', '.join(merged[:6])}")
        except OllamaDown as e:
            n = downs.get(name, 0) + 1
            downs[name] = n
            if n >= 5:
                # 5 timeouts sur le MÊME fichier : c'est lui le problème
                print(f"  ✗ {name}: 5 timeouts Ollama — abandonné, listé sur /sante")
                _marquer_echec(name, f"timeout Ollama x{n}")
                pending_done(name)
            else:
                print(f"  ⚠ Ollama injoignable ({e}) — nouvel essai dans 30 s "
                      f"({n}/5). Ollama est-il lancé ?")
                time.sleep(30)
                TAG_QUEUE.put(name)
        except TagError as e:
            n = fails.get(name, 0) + 1
            fails[name] = n
            if n < 3:
                print(f"  ⚠ {name}: {e} — essai {n}/3")
                TAG_QUEUE.put(name)
            else:
                print(f"  ✗ Abandon du tagging de {name}: {e} — listé sur /sante")
                _marquer_echec(name, e)
                pending_done(name)
        except Exception as e:
            print(f"  ✗ Erreur tagging {name}: {e} — listé sur /sante")
            _marquer_echec(name, e)
            pending_done(name)
        finally:
            TAG_QUEUE.task_done()


SCAN_INTERVAL = 300  # secondes entre deux scans du dossier Uploads

# Dossiers supplémentaires à taguer (un chemin par ligne, scan récursif)
TAG_DIRS_FILE = SCRIPT_DIR / "dossiers_a_taguer.txt"


def _resolve_key(name):
    """Clé d'index → chemin : nom simple = dossier Uploads,
    chemin absolu = dossier supplémentaire."""
    p = Path(name)
    return p if p.is_absolute() else UPLOAD_DIR / name


def _safe_upload_rel(raw):
    """Chemin relatif d'upload assaini et confiné : chaque composant est nettoyé
    comme un nom de fichier, sans « .. » ni racine absolue, mais les sous-dossiers
    sont préservés (upload d'un dossier complet depuis le téléphone). Renvoie une
    chaîne posix (« Album/Sous/photo.jpg ») ou None si rien d'exploitable."""
    if not raw:
        return None
    clean = []
    for p in re.split(r'[\\/]+', raw):
        p = p.strip()
        if p in ('', '.', '..'):
            continue
        clean.append(re.sub(r'[^\w\-.]', '_', p))
    return '/'.join(clean) or None


# ── Doublons à l'upload : détection par CONTENU, indépendante du nom ──────────
# Deux images identiques peuvent porter des noms différents ; leur seul point
# commun garanti est la taille en octets (mêmes dimensions → mêmes octets). On
# filtre donc d'abord par taille, puis on confirme par sha256. Portée : l'arbre
# UPLOAD_DIR — garde-fou de première ligne pour que la page web ne fabrique pas
# les doublons que le démon de rangement devra ensuite nettoyer. Le
# dédoublonnage complet du NAS reste le travail de ce démon (voir
# docs/RANGEMENT_2026.md).
_UP_SIZE_IDX = {"at": 0.0, "map": None}
_UP_SIZE_LOCK = threading.Lock()
UP_IDX_TTL = 120.0        # s : le map taille→chemins est recalculé au plus une fois par 2 min


def _sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(buf), b''):
            h.update(chunk)
    return h.hexdigest()


def _upload_size_map():
    """{taille: [chemins]} des fichiers sous UPLOAD_DIR, mis en cache (TTL). Ne
    hashe rien : sert seulement à restreindre la comparaison aux même-tailles."""
    with _UP_SIZE_LOCK:
        now = time.time()
        if _UP_SIZE_IDX["map"] is None or now - _UP_SIZE_IDX["at"] > UP_IDX_TTL:
            m = {}
            try:
                for p in UPLOAD_DIR.rglob('*'):
                    try:
                        if p.is_file():
                            m.setdefault(p.stat().st_size, []).append(p)
                    except OSError:
                        pass
            except OSError:
                pass
            _UP_SIZE_IDX["map"], _UP_SIZE_IDX["at"] = m, now
        return _UP_SIZE_IDX["map"]


def _upload_size_map_add(p):
    """Ajoute un fichier fraîchement écrit au cache, pour que les fichiers
    suivants d'un même album se dédoublonnent contre lui sans recalcul."""
    with _UP_SIZE_LOCK:
        m = _UP_SIZE_IDX["map"]
        if m is not None:
            try:
                m.setdefault(p.stat().st_size, []).append(p)
            except OSError:
                pass


def _upload_content_dup(data):
    """Chemin d'un fichier Uploads au contenu identique (même taille ET même
    sha256), quel que soit son nom — ou None. La taille filtre d'abord ; on ne
    hashe que les rares fichiers de même taille."""
    cands = _upload_size_map().get(len(data))
    if not cands:
        return None
    cible = _sha256_bytes(data)
    for p in list(cands):
        try:
            if p.is_file() and _sha256_file(p) == cible:
                return p
        except OSError:
            continue
    return None


def _pkey(p):
    """Clé de correspondance insensible aux séparateurs / à la casse."""
    return Path(p).as_posix().lower()


def _is_hidden_path(p):
    """Vrai si un composant du chemin est caché : .thumbs, @eaDir, #recycle…"""
    return any(part.startswith(('.', '@', '#')) for part in Path(p).parts)


# Dossiers navigables/galerie mais PAS tagués automatiquement
BROWSE_DIRS_FILE = SCRIPT_DIR / "dossiers_a_explorer.txt"


def _load_dirs_file(file, verbose=False):
    dirs = []
    try:
        for line in file.read_text(encoding='utf-8').splitlines():
            line = line.strip().strip('"')
            if not line or line.startswith('#'):
                continue
            p = Path(line)
            if p.is_dir():
                dirs.append(p)
            elif verbose:
                print(f"  ⚠ Dossier introuvable (ignoré) : {line}")
    except FileNotFoundError:
        pass
    except OSError as e:
        if verbose:
            print(f"  ⚠ Lecture de {file.name} impossible : {e}")
    return dirs


def load_extra_dirs(verbose=False):
    return _load_dirs_file(TAG_DIRS_FILE, verbose)


def load_browse_dirs():
    return _load_dirs_file(BROWSE_DIRS_FILE)


# Cache de media_roots() (audit O3) : chaque appel relisait les deux fichiers
# de config ET statait chaque dossier sur SMB — NAS débranché, toute l'UI gelait
# sur des timeouts en cascade. TTL court (8 s) : dans la fenêtre, zéro stat.
# Au-delà : si les fichiers de config n'ont pas bougé (stat LOCAL, pas cher),
# on garde la liste, avec un rebuild complet toutes les 60 s quand même — un
# dossier NAS revenu en ligne réapparaît ainsi sans toucher la config.
_MEDIA_ROOTS_CACHE = {"at": 0.0, "built_at": 0.0, "sig": None, "roots": None}
MEDIA_ROOTS_TTL = 8.0          # s sans AUCUNE vérification
MEDIA_ROOTS_REBUILD = 60.0     # s entre deux rebuilds complets (stats SMB)


def _media_roots_sig():
    """Signature (mtime, taille) des deux fichiers de config — stats locaux."""
    sig = []
    for f in (TAG_DIRS_FILE, BROWSE_DIRS_FILE):
        try:
            st = f.stat()
            sig.append((int(st.st_mtime), st.st_size))
        except OSError:
            sig.append((0, 0))
    return tuple(sig)


def media_roots():
    """Racines navigables : Uploads + dossiers tagués + dossiers à explorer.
    Mise en cache (voir _MEDIA_ROOTS_CACHE) : les appelants reçoivent la même
    liste partagée — elle ne doit jamais être mutée en place."""
    now = time.time()
    c = _MEDIA_ROOTS_CACHE
    if c["roots"] is not None and now - c["at"] < MEDIA_ROOTS_TTL:
        return c["roots"]
    if (c["roots"] is not None and now - c["built_at"] < MEDIA_ROOTS_REBUILD
            and _media_roots_sig() == c["sig"]):
        c["at"] = now
        return c["roots"]
    roots = [("Uploads", UPLOAD_DIR)]
    seen = {str(UPLOAD_DIR).lower()}
    for d in load_extra_dirs() + load_browse_dirs():
        k = str(d).lower()
        if k in seen:
            continue
        seen.add(k)
        roots.append((d.name or str(d), d))
    c.update(at=now, built_at=now, sig=_media_roots_sig(), roots=roots)
    return roots


def _key_to_target(key):
    """Cle d'index STORE -> (idx, rel) pour FileOps, ou None si la cle ne resout
    sous aucune racine navigable. `rel` est le chemin relatif POSIX depuis la
    racine, nom de fichier INCLUS (ce que delete/resolve_target attendent).

    Miroir inverse de fichiers.key_for_new_path : par convention scan_uploads,
    une cle relative (nom simple ou « Album/x.jpg ») vit sous UPLOAD_DIR
    (racine 0), une cle absolue sous la racine supplementaire qui la contient
    (la plus specifique si plusieurs s'imbriquent). Comparaison casse-insensible
    via _pkey (les cles sont des chemins Windows)."""
    p = Path(key)
    if not p.is_absolute():
        return 0, p.as_posix()
    na = _pkey(p)
    best = None
    for i, (_label, root) in enumerate(media_roots()):
        rp = _pkey(Path(root)).rstrip('/')
        if na == rp or not na.startswith(rp + '/'):
            continue
        rel = p.as_posix()[len(Path(root).as_posix()):].lstrip('/')
        if best is None or len(rp) > best[2]:
            best = (i, rel, len(rp))
    return (best[0], best[1]) if best else None


def _folder_link_for_key(k, roots=None):
    """Pour une photo `k`, renvoie (label_dossier, url) où url pointe vers la
    vue Dossiers/galerie (/files?dir=…) de son dossier d'origine. Même logique
    que _serve_geo, mais en préservant la casse d'origine du chemin."""
    if roots is None:
        roots = media_roots()
    korig = Path(k).as_posix()
    kp = korig.lower()
    folder, gurl = 'Uploads', '/files'
    if '/' in korig:
        parent_orig = korig.rsplit('/', 1)[0]
        for i, (label, root) in enumerate(roots):
            rp = _pkey(root).rstrip('/')
            if kp.startswith(rp + '/'):
                rel = parent_orig[len(rp) + 1:] if len(parent_orig) > len(rp) else ''
                folder = label + ('/' + rel if rel else '')
                if rel:
                    gurl = ('/files?dir=' + str(i) + '/'
                            + urllib.parse.quote(rel, safe='/'))
                else:
                    gurl = '/files?dir=' + str(i)
                break
        else:
            folder = parent_orig.rsplit('/', 1)[-1]
    return folder, gurl


def _random_photo(root):
    """Pioche une photo au hasard par marche aléatoire dans l'arborescence.
    Quasi instantané même sur des dizaines de milliers de photos (pas
    d'énumération complète). Pondération par nombre d'entrées immédiates."""
    for _attempt in range(12):
        d = str(root)
        for _depth in range(20):
            try:
                with os.scandir(d) as it:
                    entries = list(it)
            except OSError:
                break
            dirs, files = [], []
            for e in entries:
                if e.name.startswith(('.', '@', '#')):
                    continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        dirs.append(e)
                    elif (e.is_file()
                          and os.path.splitext(e.name)[1].lower() in IMAGE_EXT):
                        files.append(e)
                except OSError:
                    continue
            total = len(dirs) + len(files)
            if total == 0:
                break  # cul-de-sac : on retente depuis la racine
            i = random.randrange(total)
            if i >= len(dirs):
                return Path(files[i - len(dirs)].path)
            d = dirs[i].path
    return None


def _assoc_chain(items, cap=1500):
    """Ordonne une liste de photos {kw:[…]} en « chaîne d'association » : chaque
    photo partage un maximum de mots-clés avec la précédente. O(n²) → on limite
    le tronçon chaîné à `cap`, le reste est ajouté tel quel."""
    if len(items) <= 2:
        return items
    head = items[:cap]
    tail = items[cap:]
    pool = list(range(len(head)))
    kwsets = [set(it.get('kw') or []) for it in head]
    start = random.randrange(len(pool))
    order = [pool.pop(start)]
    cur = order[0]
    while pool:
        ck = kwsets[cur]
        bi, bs = 0, -1
        for pi, j in enumerate(pool):
            s = len(ck & kwsets[j]) if ck else 0
            if s > bs:
                bs = s
                bi = pi
        cur = pool.pop(bi)
        order.append(cur)
    return [head[i] for i in order] + tail


_ASSOC_CACHE = {"at": 0.0, "tags": None}
_ASSOC_LOCK = threading.Lock()


def _tag_index():
    """Index inversé tag → clés de photos (reconstruit au plus toutes les 60 s)."""
    with _ASSOC_LOCK:
        if _ASSOC_CACHE["tags"] is None or time.time() - _ASSOC_CACHE["at"] > 60:
            tags = {}
            for k, e in list(STORE.data.items()):
                if e.get('failed'):
                    continue
                for t in set((e.get('kw_fr') or []) + (e.get('kw_en') or [])):
                    tags.setdefault(t, []).append(k)
            _ASSOC_CACHE["tags"] = tags
            _ASSOC_CACHE["at"] = time.time()
        return _ASSOC_CACHE["tags"]


def _url_for_key(k, roots=None):
    """URL servable pour une clé d'index, quelle que soit sa racine."""
    if '/' not in _pkey(k):
        return '/uploads/' + urllib.parse.quote(k)
    kp = _pkey(k)
    if roots is None:
        roots = media_roots()
    for i, (_label, root) in enumerate(roots):
        rp = _pkey(root)
        if kp.startswith(rp + '/'):
            return f'/media/{i}/' + urllib.parse.quote(kp[len(rp) + 1:])
    return None


# ─── « Même jour, autres années » : index MM-JJ en mémoire ───────────────────
# Moteur pur et testé dans meme_jour.py (import léger : re + time). Bâti sur
# les dates PRÉCISES uniquement — jamais le repli « année du dossier », qui
# rangerait des milliers de photos sous un 1ᵉʳ janvier qui n'a jamais existé.
# Même cache que _key_index : reconstruit quand le nombre d'entrées change ou
# après JOUR_IDX_TTL. Aucun accès NAS, aucun GPU.
import meme_jour
_JOUR_IDX = {"at": 0.0, "n": -1, "map": None}
_JOUR_IDX_LOCK = threading.Lock()
JOUR_IDX_TTL = 300.0


def _jour_index():
    """{« MM-JJ » : [(epoch, clé), …]}, en cache."""
    with _JOUR_IDX_LOCK:
        n, now = len(STORE.data), time.time()
        if (_JOUR_IDX["map"] is None or _JOUR_IDX["n"] != n
                or now - _JOUR_IDX["at"] > JOUR_IDX_TTL):
            import faits_vue
            _JOUR_IDX["map"] = meme_jour.construire_index(
                list(STORE.data.items()), _fname_time, faits_vue.date_credible)
            _JOUR_IDX["n"], _JOUR_IDX["at"] = n, now
        return _JOUR_IDX["map"]


def _jour_de(cle, entree):
    """« MM-JJ » d'une photo si sa date est PRÉCISE, sinon None. Sert aussi à
    la visionneuse : sans jour, le bouton « Même jour » se cache — on n'ouvre
    pas une porte sur une page qui n'a rien à montrer."""
    ep = _epoch_precis(cle, entree)      # garde-fou de la date de SCAN compris
    return meme_jour.cle_jour(ep) if ep is not None else None


def _autorite_des_noms():
    """Index INVERSE de l'autorite vivante :
    `({cle: [tags]}, {cle: {exclus}}, {tag minuscule: orthographe de la fiche})`.

    Une seule implementation, deux appelants -- ce qui s'AFFICHE (`_faits_ctx`)
    et ce que la recherche FILTRE (`_cles_portant`). Ils repondaient a la meme
    question par deux chemins : l'affichage par les fiches, le filtre par les
    `kw` bruts de l'index. Resultat mesure le 20/08 sur la base reelle : 13
    photos que la recherche rendait alors que leur ligne de faits ne portait
    pas le nom -- des retraits humains que le filtre ignorait. `exclude` fait
    autorite PARTOUT, y compris dans le seul endroit que l'utilisateur
    interroge.

    `_noms_attendus(cle)` repond encore a la meme question pour UNE photo (le
    worker de tagging) en rebalayant toutes les fiches : gratuit une fois,
    ruineux pour une planche -- 13,9 ms par lot de 50, et le balayage
    recommence a chaque photo. L'index ci-dessous se batit en un seul passage ;
    ensuite chaque photo n'est plus qu'un acces dict, et le cout cesse de
    dependre du nombre de fiches.

    DEUX passes, et c'est voulu : les `exclude` de toutes les fiches sont
    collectes AVANT les `faces`. En une seule passe, un nom retire par une
    fiche pourrait etre ressuscite par une autre selon l'ordre du dict -- une
    autorite qui depend d'un ordre d'iteration n'en est pas une.

    `canon` : l'orthographe que l'HUMAIN a choisie dans la fiche. L'index porte
    encore des mots-cles ecrits avant elle (`animal:luna`) ; c'est la fiche qui
    tranche, sinon la meme Luna s'affiche « Luna » ici et « luna » la."""
    attendus, exclus, canon = {}, {}, {}
    try:
        fiches = []
        for store, prefix in ((PEOPLE_STORE, 'personne'), (PETS_STORE, 'animal')):
            for pe in list(store.data.values()):
                if isinstance(pe, dict) and pe.get('name'):
                    fiches.append(("%s:%s" % (prefix, pe['name']), pe))
        for tag, pe in fiches:                    # passe 1 : les retraits
            canon.setdefault(tag.lower(), tag)
            # Une photo que la MEME fiche confirme ET exclut porte deux
            # jugements contradictoires : la confirmation (le geste explicite
            # « c'est bien lui », 30/08) neutralise l'AUTORITE de l'exclusion
            # sans l'effacer — même préséance que le healer du démarrage,
            # sinon confirmer une photo exclue ne changerait rien à l'écran.
            conf = set(pe.get('confirmed') or [])
            for k in (pe.get('exclude') or []):
                if k in conf:
                    continue
                exclus.setdefault(k, set()).add(tag.lower())
        for tag, pe in fiches:                    # passe 2 : les attributions
            for kf in (pe.get('faces') or []):
                if (isinstance(kf, (list, tuple)) and len(kf) == 2
                        and tag.lower() not in exclus.get(kf[0], ())):
                    attendus.setdefault(kf[0], []).append(tag)
    except Exception:                             # noqa: BLE001
        return {}, {}, {}
    return attendus, exclus, canon


def _noms_fusionnes(cle, entree, attendus, exclus, canon=None):
    """Tags de nom qui font AUTORITE sur une photo : ceux des fiches, plus ceux
    de l'index que personne n'a retires.

    La FICHE fait foi sur l'ORTHOGRAPHE — deux defauts d'un coup, tous deux
    observes le 20/08 sur la base reelle : sans le filtre de casse, une photo
    que la fiche revendique ET que l'index nomme autrement affiche
    « Luna . luna » (2 photos) ; sans `canon`, une photo que la fiche ne
    revendique pas s'affiche « luna » tout court (1 photo). Le nom montre alors
    l'accident d'ecriture d'un mot-cle, pas le choix de l'humain.

    Aucun nom n'est PERDU au passage : seule sa graphie change, et la recherche
    compare en minuscules (`_cles_portant`)."""
    canon = canon or {}
    deja = {t.lower() for t in (attendus.get(cle) or ())}
    ex = exclus.get(cle) or ()
    noms = list(attendus.get(cle) or ())
    e = entree if isinstance(entree, dict) else {}
    for t in (e.get('kw_fr') or []):
        tl = str(t).lower()
        if ((tl.startswith('personne:') or tl.startswith('animal:'))
                and tl not in ex and tl not in deja):
            deja.add(tl)
            noms.append(canon.get(tl, t))
    return noms


# Plafond de /api/faits. Le cout d'un lot est celui de `_faits_ctx()`, bati UNE
# fois ; ce qui grimpe avec le nombre de cles est la boucle, pas le contexte.
# 200 est le plafond d'une page de resultats cote MCP : au-dela, c'est un
# parcours, pas un affichage.
MAX_FAITS = 200


def _faits_ctx():
    """Contexte partage par TOUTES les photos d'une page -- construit UNE fois.

    L'autorite des noms vient de `_autorite_des_noms()`, que partage le filtre
    de la recherche : ce qu'on cherche et ce qu'on voit ne peuvent plus se
    contredire.

    Rend un dict opaque, a passer tel quel a `_faits_pour`."""
    attendus, exclus, canon = _autorite_des_noms()
    try:
        lieux = lieux_connus()
    except Exception:                             # noqa: BLE001
        lieux = {}
    try:
        gps = gps_places_connus()
    except Exception:                             # noqa: BLE001
        gps = {}
    return {'attendus': attendus, 'exclus': exclus, 'canon': canon,
            'lieux': lieux, 'gps': gps, 'racines': media_roots()}


def _faits_pour(cle, entree, ctx):
    """`date . lieu . noms` d'une photo, chacun avec sa SOURCE -- la VUE.

    Pas le champ `faits` grave en base : ecrit par le seul worker de tagging
    (81 photos sur 43 064) et deja perime sur 12 d'entre elles. Le backfill a
    ete rejete le 19/08 pour cette raison meme ; ce qui s'affiche se recalcule.

    Une seule regle, celle que partagent le renommage, le Knowledge Builder,
    `/sujets` et la recherche : `faits_vue.assertions`. Rien n'est reassemble
    ici -- un deuxieme assemblage, meme fidele, finit par diverger, et c'est
    alors l'ecran qui ment sur ce que le moteur a compris.

    `ctx` vient de `_faits_ctx()`. Rend None quand la photo ne porte AUCUN des
    trois : mieux vaut ne rien afficher qu'une ligne vide."""
    import faits_vue
    e = entree if isinstance(entree, dict) else {}
    kw = _noms_fusionnes(cle, e, ctx['attendus'], ctx['exclus'],
                         ctx.get('canon'))
    a = faits_vue.assertions(cle, e, gps_place=ctx['gps'].get(cle),
                             lieux=ctx['lieux'], racines=ctx['racines'],
                             noms_attendus=kw)
    noms = list(a['persons']) + list(a['animals'])
    if not (a['date'] or a['lieu'] or noms):
        return None
    return {'date': a['date'], 'date_src': a['date_src'],
            'lieu': a['lieu'], 'lieu_src': a['lieu_src'], 'noms': noms}


def _jour_resoudre(param):
    """Paramètre de /api/jour et /files?jour= → (jour « MM-JJ », clé de la photo
    de référence ou None). Accepte les deux formes : un jour tout fait
    (« 08-14 », pour un lien qu'on partage ou qu'on remet en favori) ou la CLÉ
    d'une photo (ce que passe le bouton de la visionneuse). Renvoie
    (None, clé) si la photo existe mais n'a pas de date précise — l'appelant
    doit alors le DIRE, pas afficher une page vide."""
    j = meme_jour.jour_demande(param)
    if j:
        return j, None
    cle = param
    if cle and STORE.data.get(cle) is None:
        # Lien ancien ou clé minusculée (hôte SMB) : on repasse par l'index
        # secondaire plutôt que de rendre une page vide.
        alt = _index_key_for_path(_resolve_key(cle))
        if alt:
            cle = alt
    # `or {}` : une photo déposée à l'instant n'est pas encore dans l'index,
    # mais son NOM peut déjà porter la date — on ne lui refuse pas la page.
    return _jour_de(cle, STORE.data.get(cle) or {}), cle


def _index_entries_under(folder):
    """Entrées de l'index situées sous un dossier (récursif), sans toucher
    au système de fichiers."""
    fp = _pkey(folder)
    up = _pkey(UPLOAD_DIR)
    out = []
    if fp == up or fp == _pkey(Path(UPLOAD_DIR).resolve()):
        for k, e in list(STORE.data.items()):
            if '/' not in _pkey(k):  # clés simples = racine Uploads
                out.append((k, e))
        return out
    pref = fp + '/'
    for k, e in list(STORE.data.items()):
        if _pkey(k).startswith(pref):
            out.append((k, e))
    return out


# ─── Chemin réel → clé d'index (la casse ne doit JAMAIS décider) ─────────────
# Les clés d'index gardent la casse d'origine du NAS (« \\NAS-Bremblens\… »)
# alors que Path.resolve() MINUSCULE le nom d'hôte SMB : un STORE.get(str(f))
# est un accès de dictionnaire, donc sensible à la casse, et rate TOUTES les
# photos de la racine NAS. Symptôme observé le 14/08 : la galerie par dossier
# affichait la photothèque entière sans tags, sans description, sans GPS et au
# 1ᵉʳ janvier, alors que la même photo vue par /files?q= portait 20 tags et sa
# vraie date. Le reste du code passait déjà par _pkey ; ici on rétablit la même
# règle via l'index secondaire {chemin normalisé: clé} de fichiers.py — celui
# que la vue Dossiers utilise déjà pour ne jamais perdre un nom humain.
#
# Le dictionnaire est bâti une fois puis mis en cache : reconstruit quand le
# nombre d'entrées change (tagging, purge) ou après KEY_IDX_TTL. Un renommage
# garde la même taille : la carte peut donc être périmée au plus TTL secondes,
# et un accès périmé retombe proprement sur « pas d'entrée » (le fichier n'est
# de toute façon plus à cet endroit du disque).
_KEY_IDX = {"at": 0.0, "n": -1, "map": None}
_KEY_IDX_LOCK = threading.Lock()
KEY_IDX_TTL = 60.0


def _key_index():
    """{chemin normalisé (_pkey) : clé d'index exacte}, en cache."""
    with _KEY_IDX_LOCK:
        n, now = len(STORE.data), time.time()
        if (_KEY_IDX["map"] is None or _KEY_IDX["n"] != n
                or now - _KEY_IDX["at"] > KEY_IDX_TTL):
            _KEY_IDX["map"] = fichiers.build_key_index(
                list(STORE.data.keys()), _resolve_key)
            _KEY_IDX["n"], _KEY_IDX["at"] = n, now
        return _KEY_IDX["map"]


def _key_index_invalider():
    """Force la reconstruction des DEUX cartes au prochain accès. Un renommage
    ne change pas le nombre d'entrées : la garde par taille ne verrait rien, et
    l'index MM-JJ servirait pendant 5 min une clé morte (vignette 404, et une
    suppression visant un fichier qui n'est plus là). Verrous pris l'un APRÈS
    l'autre, jamais imbriqués."""
    with _KEY_IDX_LOCK:
        _KEY_IDX["n"] = -1
    with _JOUR_IDX_LOCK:
        _JOUR_IDX["n"] = -1


def _index_key_for_path(p, carte=None):
    """Clé d'index d'un fichier du disque, insensible à la casse et aux
    séparateurs — ou None si le fichier n'est pas indexé. À utiliser partout
    où l'on part d'un chemin PARCOURU (donc resolve()) pour retrouver l'entrée.

    `carte` : instantané obtenu par `_key_index()`. Le passer est OBLIGATOIRE
    dans une boucle — sans lui, chaque fichier redemande la carte, et il suffit
    qu'un thread de fond ajoute une entrée (tagging) ou renomme (rangement)
    entre deux tours pour reconstruire 43 000 entrées à chaque itération,
    verrou tenu. Un instantané figé pour la durée d'une requête est de toute
    façon plus cohérent qu'une carte qui bouge en cours de rendu."""
    k = (_key_index() if carte is None else carte).get(_pkey(p))
    return k if k is not None and STORE.data.get(k) is not None else None


def _assoc_next(prev_key, exclude):
    """Mode Association : photo suivante ayant AU MOINS un tag commun avec la
    précédente ET au moins un tag nouveau. Les candidats sont pondérés par la
    rareté des tags partagés : un lien via « libellule » (rare) l'emporte
    sur un lien via « ciel » (10 000 photos)."""
    e = STORE.data.get(prev_key) or {}
    prev_tags = set((e.get('kw_fr') or []) + (e.get('kw_en') or []))
    if not prev_tags:
        return None
    tags = _tag_index()
    cand = {}
    for t in prev_tags:
        lst = tags.get(t) or []
        if not lst:
            continue
        w = 1.0 / (len(lst) ** 0.7)
        for k in lst:
            if k != prev_key and k not in exclude:
                cand[k] = cand.get(k, 0.0) + w
    pool = []
    for k, w in cand.items():
        ce = STORE.data.get(k) or {}
        ck = set((ce.get('kw_fr') or []) + (ce.get('kw_en') or []))
        if ck - prev_tags:  # exige au moins un tag différent
            pool.append((k, w))
    for _ in range(5):
        if not pool:
            return None
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        acc = 0.0
        chosen = pool[-1][0]
        for k, w in pool:
            acc += w
            if acc >= r:
                chosen = k
                break
        if _url_for_key(chosen):
            ce = STORE.data.get(chosen) or {}
            ck = set((ce.get('kw_fr') or []) + (ce.get('kw_en') or []))
            shared = sorted(ck & prev_tags,
                            key=lambda t: len(tags.get(t) or []))[:2]
            return chosen, shared
        pool = [(k, w) for k, w in pool if k != chosen]
    return None


def retro_write_metadata():
    """Écrit dans les fichiers les tags encore uniquement dans l'index.
    Abandonne après 3 échecs (fichier endommagé) — visible sur /sante."""
    for name, e in list(STORE.data.items()):
        if e.get('failed') or e.get('in_file'):
            continue
        if e.get('write_fails', 0) >= 3 and e.get('repair_tried'):
            continue
        kw = list(dict.fromkeys((e.get('kw_fr') or []) + (e.get('kw_en') or [])))
        if not kw:
            continue
        p = _resolve_key(name)
        if not p.exists():
            continue
        ok = write_metadata(p, kw, e.get('desc', ''))
        if not ok and not e.get('repair_tried'):
            # EXIF endommagé ? → une tentative de réparation, puis on réessaie
            e['repair_tried'] = True
            if repair_file(p):
                ok = write_metadata(p, kw, e.get('desc', ''))
        if ok:
            e['in_file'] = True
            e['size'], e['mtime'] = _stat_of(p)
            e.pop('file_error', None)
            e.pop('write_fails', None)
            STORE.set(name, e)
            print(f"  ✓ Tags écrits dans le fichier {name}")
        else:
            e['write_fails'] = e.get('write_fails', 0) + 1
            if e['write_fails'] >= 3:
                e['file_error'] = LAST_WRITE_ERROR or "écriture métadonnées impossible"
                print(f"  ⚠ {name}: abandon — listé sur /sante")
            STORE.set(name, e)


def _stat_of(p):
    try:
        st = p.stat()
        return int(st.st_size), int(st.st_mtime)
    except OSError:
        return None, None


def _meta_videos(chemins):
    """{chemin normalisé: (taken|None, duree_s|None)} par UN ExifTool (-fast :
    le `moov` en fin de MP4 n'est pas lu par -fast2, mesuré 0/7 le 29/08).
    La date vient du NOM d'abord (`AAAAMMJJ_HHMMSS`, `VID-…-WA`), comme
    `inventaire_videos` ; jamais du mtime."""
    from inventaire_videos import TAGS, date_du_nom, date_exif
    out = {}
    reste = []
    for p in chemins:
        t = date_du_nom(Path(p).name)
        out[_pkey(p)] = [t, None]
        reste.append(p)
    if not reste or not EXIFTOOL:
        return {k: tuple(v) for k, v in out.items()}
    for i in range(0, len(reste), 150):
        part = reste[i:i + 150]
        try:
            r = _run_exiftool(['-j', '-fast', '-charset', 'filename=utf8', '-charset', 'utf8',
                               '-Duration#'] + ['-' + t for t in TAGS] + [str(p) for p in part],
                              timeout=600)
            data = json.loads(r.stdout or '[]')
        except Exception as e:
            print(f"  ⚠ ExifTool sur {len(part)} vidéo(s) : {e}")
            data = []
        for e in data:
            src = e.get('SourceFile')
            if not src:
                continue
            k = _pkey(src)
            if k not in out:
                continue
            if out[k][0] is None:
                for t in TAGS:
                    ts = date_exif(e.get(t.split(':')[-1]))
                    if ts:
                        out[k][0] = ts
                        break
            d = e.get('Duration')
            try:
                out[k][1] = round(float(d), 1) if d is not None else None
            except (TypeError, ValueError):
                pass
    return {k: tuple(v) for k, v in out.items()}


def indexer_videos(cles, label=''):
    """Écrit l'entrée d'index d'une vidéo (phase 1) : `video`, `duree`, `taken`,
    taille, mtime — mots-clés VIDES, `in_file` faux. Elle n'est JAMAIS mise
    en file du tagueur ni d'un pipeline : chacun filtre sur IMAGE_EXT, et le
    sémantique saute `video`. Rend le nombre d'entrées écrites."""
    if not VIDEOS_DANS_L_INDEX or not cles:
        return 0
    metas = _meta_videos(list(cles.values()))
    n = 0
    for k, p in cles.items():
        size, mtime = _stat_of(p)
        taken, duree = metas.get(_pkey(p), (None, None))
        e = {"video": True, "kw_fr": [], "kw_en": [], "desc": "", "in_file": False,
             "at": time.time(), "size": size, "mtime": mtime}
        if duree is not None:
            e["duree"] = duree
        if taken:
            e["taken"] = float(taken)
        STORE.set(k, e, save=False)
        n += 1
    if n:
        STORE.save()
    return n


def _sync_dir(label, cur, own_keys, first=False, deep=False):
    """Synchronise l'index avec l'état réel d'une racine.
    cur : clé d'index → Path des fichiers réellement présents.
    own_keys : clés de l'index appartenant à cette racine.
    Gère : nouveaux, déplacés/renommés (re-clé sans IA), modifiés
    (re-tagging, scan approfondi) et supprimés (nettoyage)."""
    with PENDING_LOCK:
        pending_now = set(PENDING)

    unknown = [k for k in cur if k not in STORE.data and k not in pending_now]
    orphans = [k for k in own_keys if k not in cur]

    # 1) déplacements / renommages : re-clé sans re-tagging
    moved = 0
    if unknown and orphans:
        by_pkey = {_pkey(k): k for k in orphans}
        by_sig = {}
        for k in orphans:
            e = STORE.data.get(k) or {}
            if e.get('size') is not None:
                by_sig.setdefault((Path(k).name.lower(), e['size']), []).append(k)
        still = []
        for k in unknown:
            old = by_pkey.get(_pkey(k))
            if old is None:
                size, _mt = _stat_of(cur[k])
                cands = by_sig.get((cur[k].name.lower(), size))
                old = cands.pop(0) if cands else None
            if old is not None and old in orphans:
                _sz, mt = _stat_of(cur[k])
                # Point de re-clé UNIQUE (save différé) : transporte tags +
                # visages/animaux + empreintes sémantiques, pas seulement les
                # tags. Sans ça, un fichier déplacé perdait ses détections et
                # son vecteur sémantique (orphelins purgés au scan suivant).
                if rekey_everywhere(old, k, mtime=mt, save=False):
                    orphans.remove(old)
                    moved += 1
                    continue
            still.append(k)
        unknown = still
        if moved:
            # Batch : STORE.save() commite aussi le sémantique (connexion cx
            # partagée) ; les stores de sujets ont leur propre connexion.
            STORE.save()
            for _st in (FACE_STORE, PEOPLE_STORE, ANIMAL_STORE, PETS_STORE):
                _st.save()
            gps_places_save()   # 7e magasin (audit I2), differe par save=False
            print(f"  🔀 {label} : {moved} déplacement(s)/renommage(s) détecté(s)"
                  f" — index + détections + empreintes re-clés sans re-tagging")

    # 2) nouveaux fichiers : import des tags in-file, sinon file d'attente IA
    if unknown:
        # Les vidéos d'abord (phase 1) : leur entrée s'écrit ici, elles ne
        # passent ni par la lecture des métadonnées photo ni par le tagueur.
        videos = [k for k in unknown if cur[k].suffix.lower() in VIDEO_EXT]
        if videos:
            if first and len(videos) > 200:
                print(f"  🎬 {label} : {len(videos)} vidéo(s) à indexer (date par le nom, "
                      f"sinon ExifTool par lots de 150, patience)…")
            n_vid = indexer_videos({k: cur[k] for k in videos}, label)
            unknown = [k for k in unknown if k not in set(videos)]
            if n_vid:
                print(f"  🎬 {label} : {n_vid} vidéo(s) indexée(s) ; aucun tagging")
        if first and len(unknown) > 200:
            print(f"  🔍 Lecture des métadonnées existantes de {len(unknown)} "
                  f"fichier(s) (par lots de 40, patience)…")
        # `vus` inutile ici : une lecture ratée renvoie simplement la photo à la
        # file de tagging IA — rien n'est perdu, rien n'est marqué.
        existing, _vus = read_existing_metadata([cur[k] for k in unknown],
                                                progress=first)
        # Le XMP porte UNE liste : `kw_fr + kw_en` telle que write_metadata
        # l'a écrite. Relue entière dans `kw_fr` avec un `kw_en` vide, elle a
        # fait 22 196 entrées « anglaises » (52 %, mesure du 30/08). On la
        # scinde à la relecture, par la règle pure `scission_fr_en` (les
        # vocabulaires s'apprennent sur l'index déjà là : 22 190 / 22 196 sur
        # la copie). Sans index sain (premier démarrage à vide), rien ne vote
        # et tout reste en `kw_fr`, comme avant.
        import scission_fr_en
        vfr, ven = scission_fr_en.vocabulaires(STORE.data) if existing else ({}, {})
        n_import = n_queue = n_scinde = 0
        for k in unknown:
            p = cur[k]
            size, mtime = _stat_of(p)
            meta = existing.get(_pkey(p))
            if meta:
                kw, desc = meta
                kw_en = []
                if vfr:
                    r = scission_fr_en.scinder_entree({"kw_fr": kw, "kw_en": []}, vfr, ven)
                    if r:
                        kw, kw_en = r[0], r[1]
                        n_scinde += 1
                STORE.set(k, {"kw_fr": kw, "kw_en": kw_en, "desc": desc,
                              "in_file": True, "at": time.time(),
                              "size": size, "mtime": mtime,
                              "imported": True}, save=False)
                n_import += 1
            else:
                enqueue(k)
                n_queue += 1
        STORE.save()
        print(f"  🏷  {label} : {n_queue} photo(s) à taguer"
              + (f", {n_import} importée(s)" if n_import else "")
              + (f" dont {n_scinde} FR/EN scindée(s)" if n_scinde else ""))
    elif first and not moved:
        print(f"  🏷  {label} : rien de nouveau à taguer")

    # 3) fichiers modifiés (scan approfondi ~1x/heure) : re-tagging
    if deep:
        changed = []
        for k, p in cur.items():
            e = STORE.data.get(k)
            if not e or e.get('failed') or k in pending_now:
                continue
            old_m = e.get('mtime')
            if old_m is None:
                continue
            _sz, mtime = _stat_of(p)
            if mtime is not None and abs(mtime - old_m) > 2:
                if e.get('video') or p.suffix.lower() in VIDEO_EXT:
                    indexer_videos({k: p}, label)     # jamais le tagueur
                    continue
                changed.append(k)
        if changed:
            # Motif déclaré : ces retraits sont TEMPORAIRES (l'entrée revient
            # après re-tagging), mais ils font quand même baisser l'index —
            # sans motif ils passeraient pour un oubli.
            with REGISTRE.motif('scan:modifies', label=label):
                STORE.remove_many(changed)
            for k in changed:
                enqueue(k)
            print(f"  ♻ {label} : {len(changed)} fichier(s) modifié(s) → re-tagging")

    # 4) fichiers disparus : nettoyage (la racine vient d'être listée, donc joignable)
    #    forget_everywhere purge en cascade tags + détections visages/animaux +
    #    vecteur sémantique (avant : STORE seul → détections orphelines, bug ARZOPA).
    #    Les fiches nommées (PEOPLE/PETS, keyées par nom) ne sont pas touchées.
    if orphans:
        n = forget_everywhere(orphans, motif='scan:disparus', label=label)
        # On dit TOUJOURS combien on a demandé et combien est parti : « 0 sur
        # 250 » est une information, et c'est précisément celle qui manquait le
        # 17/08. L'écart = clés déjà absentes de l'index (déjà retirées par un
        # autre chemin), et c'est lui qu'il faut voir.
        ecart = len(orphans) - n
        print(f"  🧹 {label} : {n}/{len(orphans)} entrée(s) de fichiers disparus"
              f" retirée(s) (tags + visages/animaux + vecteurs)"
              + (f" — {ecart} déjà absente(s) de l'index" if ecart else ""))


def scan_uploads(first=False, deep=False):
    """Scan des racines : Uploads (plat) + dossiers à taguer (récursif)."""
    # ── racine Uploads, RECURSIF : fichier a plat -> clé = nom ; fichier en
    #    sous-dossier -> clé = chemin relatif posix (MEME convention que l'upload
    #    de dossier, cf. _do_post ~« dest.relative_to(UPLOAD_DIR).as_posix() »).
    #    Avant, ce scan etait plat (iterdir) : un sous-dossier depose hors de
    #    l'app (ex. « ARZOPA ») n'etait JAMAIS enumere, donc jamais tague, meme
    #    apres une nuit de serveur. La recursion le corrige. ──
    try:
        imgs = [f for f in UPLOAD_DIR.rglob('*')
                if f.is_file() and f.suffix.lower() in MEDIA_EXT
                and not _is_hidden_path(f.relative_to(UPLOAD_DIR))]
    except OSError as e:
        print(f"  ⚠ Scan impossible: {e}")
        return
    cur = {}
    for f in imgs:
        rel = f.relative_to(UPLOAD_DIR)
        cur[f.name if len(rel.parts) == 1 else rel.as_posix()] = f
    # « own » = les clés d'Uploads (nom simple OU relatif). Une clé de dossier
    # supplementaire est ABSOLUE (jamais relative), donc exclue proprement : le
    # scan Uploads ne purge pas les entrees des dossiers NAS a taguer.
    own = [k for k in STORE.data if not Path(k).is_absolute()]
    _sync_dir("Uploads", cur, own, first, deep)

    # ── dossiers supplémentaires (dossiers_a_taguer.txt), récursif ──
    # Un dossier à taguer peut ENGLOBER la racine Uploads (ex. la racine Photos
    # contient _Uploads) : ses fichiers sont alors vus deux fois — clé relative
    # par le circuit upload, clé ABSOLUE par ce scan → double entrée et double
    # tagging (observé le 12/08 : 19 photos uploadées indexées 2×). L'arbre
    # Uploads appartient au scan ci-dessus (clé relative) : on l'exclut ici par
    # préfixe (_pkey, comparaison de chaînes — pas de resolve() par fichier sur
    # le NAS). Les entrées absolues déjà créées deviennent orphelines au scan
    # suivant → purge en cascade par forget_everywhere (étape 4 de _sync_dir).
    up_pref = _pkey(UPLOAD_DIR) + '/'
    for d in load_extra_dirs(verbose=first):
        if first:
            print(f"  🔍 Énumération de {d} — peut prendre plusieurs minutes "
                  f"sur le NAS…")
        try:
            files = [p for p in d.rglob('*')
                     if p.is_file() and p.suffix.lower() in MEDIA_EXT
                     and not _is_hidden_path(p.relative_to(d))
                     and not _pkey(p).startswith(up_pref)]
        except OSError as e:
            print(f"  ⚠ Scan de {d} impossible : {e}")
            continue
        if first:
            print(f"  🔍 {d} : {len(files)} image(s)")
        cur = {str(p): p for p in files}
        pref = _pkey(d) + '/'
        own = [k for k in STORE.data if _pkey(k).startswith(pref)]
        _sync_dir(str(d), cur, own, first, deep)


# ─── Ordonnancement des travaux de fond ──────────────────────────────────────
# Avant : chaque boucle décidait seule par « if system_busy(): dors ». Comme
# system_busy() est vrai dès 70 % de CPU et que le balayage des visages l'y
# maintient, l'encodage sémantique est resté bloqué à 5 % du corpus.
# Maintenant : un seul travail lourd à la fois, choisi par tour de rôle à
# déficit — le plus endetté passe, donc personne ne meurt de faim.
# Les poids règlent la FRÉQUENCE, pas une priorité stricte (qui affamerait
# les derniers, ce qui est précisément le défaut corrigé).
POIDS_FOND = {
    'visages': 4.0,        # file la plus longue, priorité de fait
    'animaux': 2.0,
    'semantique': 2.0,     # doit rattraper 95 % du corpus
    'empreintes_chats': 1.0,
    'reembed': 1.0,        # travail d'entretien, peut attendre
}
CRENEAU_MAX = 90.0         # s : au-delà, le travail est réputé bloqué
def _vram_libre_sonde(force=False):
    """Mo de VRAM réellement libres (0 sans GPU). Sonde de l'arbitre — corrige
    au passage l'ancienne lambda qui lisait une clé inexistante (`gpu_free_mb`
    au lieu de `gpu.vram_free_mb`) et renvoyait toujours 0."""
    g = hw_state(force).get('gpu') or {}
    return g.get('vram_free_mb', 0)


try:
    from ordonnanceur import ArbitreGPU, Ordonnanceur
    ORDO = Ordonnanceur(POIDS_FOND)
    GPU = ArbitreGPU(_vram_libre_sonde,
                     sonde_fraiche=lambda: _vram_libre_sonde(True))
    # Priorités des baux VRAM (plus grand = prioritaire) : la recherche/tags
    # SigLIP sert l'UI, les visages passent avant les chats. Ollama (tagging)
    # reste HORS bail : processus externe, la sonde voit sa consommation, il
    # a donc de fait la priorité absolue — c'est le contrat historique
    # « le tagging garde la priorité sur le GPU », conservé tel quel.
    # Les libérateurs (descente CPU pour éviction) sont enregistrés plus bas,
    # à côté de chaque pipeline.
    GPU.enregistrer('semantique', prio=3)
    GPU.enregistrer('visages', prio=2)
    GPU.enregistrer('animaux', prio=1)
    GPU.enregistrer('empreintes_chats', prio=0)
except ImportError:                     # module absent → comportement d'avant
    ORDO = GPU = None


def creneau(nom, timeout=120.0):
    """Contexte de travail de fond. Renvoie toujours un objet utilisable."""
    if ORDO is None:
        from contextlib import contextmanager

        @contextmanager
        def _passe():
            yield True
        return _passe()
    return ORDO.creneau(nom, timeout=timeout, duree_max=CRENEAU_MAX)


# ─── Recherche sémantique (SigLIP 2) ─────────────────────────────────────────
# Un encodeur, trois usages : recherche en langue naturelle, tags par
# vocabulaire contrôlé, photos similaires. Entièrement optionnel : sans la
# bibliothèque, le serveur démarre et fonctionne comme avant.
SEMANTIC_ENABLE = True
SEMANTIC_BATCH = 16            # photos encodées par passe
SEMANTIC_SUBBATCH = 4          # sous-lot : le verrou est rendu entre deux (audit O6)
SEMANTIC_IDLE_SLEEP = 90       # s d'attente quand tout est encodé
SEMANTIC_BUSY_SLEEP = 45       # s d'attente quand la machine est occupée
SEMANTIC_PACE = 1.0            # s entre deux lots (laisse respirer le NAS)
SEMANTIC_SCAN_MAX = 600        # clés examinées au plus pour réunir un lot
SEMANTIC_SKIP = set()          # clés qui n'ont produit aucun vecteur
SEMANTIC_STATE = {"done": 0, "pending": None, "device": "", "erreur": "",
                  "actif": False, "ecartees": 0}
PHOTO_VEC = None
SEMANTIC_LOCK = threading.Lock()


def _semantic_mod():
    """Import paresseux : jamais au démarrage (invariant zéro dépendance).
    Branche l'arbitre GPU au premier import (idempotent) : la décision
    CPU/GPU de SigLIP passe alors par les baux au lieu de sa sonde privée.
    En usage CLI autonome (sans injection), semantic.py garde son seuil."""
    import semantic
    if GPU is not None and getattr(semantic, '_ARBITRE', None) is None:
        try:
            semantic.set_arbitre(
                lambda: GPU.demander('semantique',
                                     semantic.SIGLIP_GPU_MIN_FREE_MB),
                lambda: GPU.confirmer('semantique'),
                lambda: GPU.rendre('semantique'))
        except Exception:
            pass
    return semantic


_DICO_FR_EN = {'dico': None, 'quand': 0.0}
DICO_FR_EN_TTL_S = 6 * 3600


def dico_fr_en():
    """Le dictionnaire FR→EN appris sur l'index (`elargissement_fr_en`),
    reconstruit au plus toutes les 6 h — 1,7 s sur 42 714 entrées, 2 339
    paires le 30/08. Mesuré sur la copie (`mesure_elargissement.py`) :
    rappel@200 de la requête française 0,583 → 0,658 avec l'élargissement,
    pour un plafond idéal de 0,663 (Mike a tranché l'élargissement le 30/08).
    Jamais None après le premier appel : un index vide donne un dictionnaire
    vide, et la requête part seule, comme avant."""
    import elargissement_fr_en
    maintenant = time.time()
    if _DICO_FR_EN['dico'] is None or maintenant - _DICO_FR_EN['quand'] > DICO_FR_EN_TTL_S:
        try:
            # Instantané sous STORE.lock : le scan et le tagueur écrivent
            # l'index pendant qu'on le lit (« dictionary changed size »).
            with STORE.lock:
                entrees = list(STORE.data.values())
            t0 = time.time()
            _DICO_FR_EN['dico'] = elargissement_fr_en.Dictionnaire(entrees)
            print(f"  📖 dictionnaire FR→EN : {len(_DICO_FR_EN['dico'])} paire(s) apprises sur "
                  f"{_DICO_FR_EN['dico'].n_photos} photo(s) bilingues, {time.time() - t0:.1f} s")
        except Exception as e:                                    # noqa: BLE001
            print(f"  ! dictionnaire FR→EN : {e}")
            _DICO_FR_EN['dico'] = elargissement_fr_en.Dictionnaire()
        _DICO_FR_EN['quand'] = maintenant
    return _DICO_FR_EN['dico']


def encoder_requete(sem, texte, detail=None):
    """Le vecteur d'une requête texte : la requête ET sa forme anglaise
    (élargissement FR→EN, moyenne des deux vecteurs normée — la forme
    `fr+en` du banc), ou la requête seule quand rien n'est connu. `detail`
    reçoit `elargi` : ce que le moteur a ajouté, pour le DIRE."""
    import elargissement_fr_en
    import numpy as np
    textes = elargissement_fr_en.formes(dico_fr_en(), texte)
    if detail is not None:
        detail['elargi'] = textes[1] if len(textes) > 1 else None
    with SEMANTIC_LOCK:            # le modèle n'est pas réentrant
        V = sem.encoder_textes(textes)
    if len(textes) == 1:
        return V[0]
    q = V.mean(axis=0)
    return q / (np.linalg.norm(q) or 1.0)


def photo_vectors():
    """Magasin de vecteurs sur la connexion déjà ouverte par le store."""
    global PHOTO_VEC
    if PHOTO_VEC is None:
        if not hasattr(STORE, 'cx'):
            raise RuntimeError("recherche sémantique : base SQLite requise "
                               "(lance « 11 - Migrer vers SQLite.bat »)")
        from vectors import VectorStore
        PHOTO_VEC = VectorStore(STORE.cx)
    return PHOTO_VEC


# Regle PURE du re-cle des decisions humaines (module stdlib, import leger) :
# `PEOPLE` et `PETS` sont les deux seuls magasins keyes par NOM, leurs chemins
# vivent DANS la fiche. Partagee avec les bancs, testee sans ouvrir photos.db.
import recle_decisions


def _recler_decisions_humaines(old, new):
    """Re-cle les decisions humaines a l'INTERIEUR des fiches personnes/animaux.

    `store.rekey(ancien_chemin, nouveau_chemin)` est un NO-OP sur PEOPLE et PETS :
    leur cle est le NOM de la personne ou de l'animal, pas un chemin. Il cherche
    une entree dont la cle serait un chemin, n'en trouve jamais, renvoie faux et
    ne dit rien — la boucle des « quatre magasins de sujets » ci-dessous en
    couvrait donc DEUX.

    Mesure du 22/08/2026, avant ce correctif : **928** decisions humaines sur
    **3 364** pointaient vers une cle absente de l'index (596 rattachements, 249
    exclusions, 83 confirmations), sur 804 cles — la trace de chaque rangement
    par annee et de chacun des 7 058 renommages appliques. Le TAG survivait (il
    vit dans `tags` et dans le XMP), donc la photo gardait son nom : la regle 2
    tenait. C'est la VERITE TERRAIN qui partait — quel VISAGE est Flo, quelles
    photos ont ete ecartees d'un nom, lesquelles ont ete confirmees. Et une
    exclusion perdue, c'est un faux positif qui revient.

    L'INDEX d'une vignette est conserve : `rekey_everywhere` deplace l'entree de
    FACE_STORE / ANIMAL_STORE EN BLOC, la liste des detections est la meme.

    `save=False` : la sauvegarde suit celle des autres magasins, deja assuree
    par l'appelant (contrat de `rekey_everywhere`). Reassigner les CHAMPS — et
    non muter au fond d'une liste — est ce qui marque l'entree « sale » cote
    store (`store_sqlite.TrackedEntry`).

    Cout : un balayage des fiches (~360, ~3 400 decisions au total) par re-cle,
    negligeable devant le `rename` sur le NAS qui l'accompagne.

    Renvoie le nombre de decisions re-clees.
    """
    n = 0
    for st in (PEOPLE_STORE, PETS_STORE):
        for pk, pe in list(st.data.items()):
            if not isinstance(pe, dict):
                continue
            champs, k = recle_decisions.recler_fiche(pe, old, new)
            if not champs:
                continue
            for champ, valeur in champs.items():
                pe[champ] = valeur
            st.set(pk, pe, save=False)
            n += k
    return n


def rekey_everywhere(old, new, mtime=None, save=True):
    """Point de re-clé UNIQUE pour un déplacement/renommage `old` → `new`.

    L'état d'une photo est réparti sur SEPT magasins keyés par le chemin : le
    store `tags` (STORE), les quatre stores de sujets (FACE/PEOPLE/ANIMAL/PETS),
    le magasin de vecteurs sémantique (`photo_vectors()`) et les libellés de
    géocodage `gps_places.json` (audit I2). Re-clé le seul
    store `tags` — ce que faisait le scan jusqu'ici — laisse les détections
    visages/animaux et l'embedding sémantique sous l'ANCIENNE clé : orphelins,
    purgés au scan suivant. Le nom humain (`personne:`/`animal:`) vit dans les
    tags et dans le XMP du fichier, donc il n'est pas *perdu* ; mais visages,
    empreintes chat et vecteur sémantique le seraient. Cette fonction les
    transporte tous en un seul geste (invariant du chantier rangement : aucune
    info perdue — voir docs/RANGEMENT_2026.md, « Prochain pas serveur »).

    Mécanique par magasin :
      - `tags` : `STORE.rekey` déplace l'entrée en mémoire ; c'est lui qui
        décide si le déplacement « compte » (renvoi de la fonction).
      - sujets keyés par CHEMIN (`FACE`, `ANIMAL`) : `rekey` + `save`. Les deux
        autres (`PEOPLE`, `PETS`) sont keyés par NOM : `rekey` y est un NO-OP
        SILENCIEUX, et leurs décisions humaines sont transportées par
        `_recler_decisions_humaines` (mesuré : 928 décisions perdues avant le
        correctif du 22/08).
        Le `save` (`_reconcilier`) supprime l'ancienne
        clé — donc son préfixe vecteur — puis ré-extrait la nouvelle depuis
        l'entrée en mémoire, où l'embedding est toujours présent : les vecteurs
        de sujets sont ainsi transportés SANS recalcul.
      - sémantique : `rekey_prefix_all` réécrit le seul préfixe des clés
        vecteurs (octets préservés), commité avec la connexion partagée `cx`.

    Idempotent (rejoué → l'ancienne clé a disparu, chaque étape renvoie
    faux/0). `save=False` diffère TOUTES les sauvegardes au batch appelant :
    dans ce cas, l'appelant DOIT ensuite sauver STORE et les quatre stores de
    sujets (le sémantique, sur la connexion de STORE, est commité par
    `STORE.save()`), plus `gps_places_save()` (7ᵉ magasin, audit I2).

    Renvoie True si l'entrée `tags` a été re-clée, False sinon.
    """
    # Un re-clé = 1 retrait + 1 ajout : NEUTRE en taille d'index, mais il doit
    # être déclaré, sinon il gonfle le bucket « non declare » des deux côtés et
    # noie le seul signal qui compte.
    with REGISTRE.motif('rekey'):
        moved = STORE.rekey(old, new, mtime=mtime)
    if not moved:
        return False
    _key_index_invalider()   # la carte {chemin: clé} vient de mentir
    subject_stores = (FACE_STORE, PEOPLE_STORE, ANIMAL_STORE, PETS_STORE)
    for st in subject_stores:
        try:
            st.rekey(old, new, mtime=mtime)
        except Exception as e:
            print(f"  ⚠ re-clé {getattr(st, 'path', st)} {old!r}→{new!r} : {e}")
    # PEOPLE et PETS ne sont pas keyés par CHEMIN : la boucle ci-dessus n'y a
    # rien trouvé et n'a rien dit. Leurs décisions humaines — quel visage est
    # Flo, quelles photos sont écartées d'un nom, lesquelles sont confirmées —
    # vivent DANS la fiche et se transportent ici (correctif du 22/08/2026).
    try:
        _recler_decisions_humaines(old, new)
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠ re-clé des décisions humaines {old!r}→{new!r} : {e}")
    # 7ᵉ magasin keyé par chemin (audit I2) : les libellés de géocodage.
    # `save` suit le même différé que les stores (flush au batch appelant).
    try:
        gps_places_rekey(old, new, save=save)
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠ re-clé gps_places {old!r}→{new!r} : {e}")
    if hasattr(STORE, 'cx'):
        try:
            # Sous STORE.lock (audit O4) : rekey_prefix_all fait son propre
            # BEGIN IMMEDIATE sur la connexion PARTAGÉE — croisé avec un
            # _ecrire() concurrent, c'est « transaction within transaction »
            # ou des lignes emportées par le ROLLBACK de l'autre.
            with STORE.lock:
                photo_vectors().rekey_prefix_all(old, new)
        except Exception as e:
            print(f"  ⚠ re-clé sémantique {old!r}→{new!r} : {e}")
    if save:
        STORE.save()
        for st in subject_stores:
            st.save()
    return moved


# Carte des deplacements, relue dans les journaux d'annulation de `docs/`.
# Module pur, partage avec les bancs : une seule lecture des journaux.
import journaux_deplacements

CORBEILLE_DECISIONS = SCRIPT_DIR / "_corbeille_decisions"

# Les quatre champs d'une fiche qui citent un CHEMIN. `refs` porte des
# embeddings, pas des cles : ne jamais y toucher.
CHAMPS_FICHE = ('faces', 'exclude', 'confirmed', 'avatar')


def _detections_du_genre(genre, cle):
    """Combien de detections porte une cle, dans le magasin qui va avec le
    genre de la fiche. Un visage InsightFace ne se compte pas dans `animals`."""
    st, champ = ((FACE_STORE, 'faces') if genre == 'visage'
                 else (ANIMAL_STORE, 'animals'))
    e = st.data.get(cle)
    return len(e.get(champ) or []) if isinstance(e, dict) else 0


def _fiches_par_genre():
    """[(magasin, genre, store)] — l'ordre est celui des deux magasins keyes
    par NOM, les deux que `rekey_everywhere` ne savait pas transporter."""
    return (('people', 'visage', PEOPLE_STORE), ('pets', 'animal', PETS_STORE))


def _decisions_sur_cles_mortes(vivantes):
    """{cle morte: {genre: index maximal cite}} — de quoi verifier les bornes.

    Une exclusion ou une confirmation n'a pas d'index : elle inscrit -1, ce qui
    passe toujours la borne. C'est voulu : elles designent la PHOTO."""
    out = {}
    for _magasin, genre, st in _fiches_par_genre():
        for pe in st.data.values():
            if not isinstance(pe, dict) or not pe.get('name'):
                continue
            for kf in (pe.get('faces') or []):
                if (isinstance(kf, (list, tuple)) and len(kf) == 2
                        and kf[0] not in vivantes):
                    d = out.setdefault(kf[0], {})
                    d[genre] = max(d.get(genre, -1), int(kf[1] or 0))
            for champ in ('exclude', 'confirmed'):
                for cle in (pe.get(champ) or []):
                    if cle not in vivantes:
                        out.setdefault(cle, {}).setdefault(genre, -1)
    return out


def reparer_decisions_orphelines(dry=True):
    """Finit le re-cle que le rangement n'a jamais fait sur les DECISIONS.

    `rekey_everywhere` re-clait sept magasins, mais `store.rekey(chemin, chemin)`
    est un no-op silencieux sur PEOPLE et PETS, keyes par NOM. Le correctif
    preventif (`_recler_decisions_humaines`) ferme le robinet ; celui-ci eponge
    ce qui a coule : au 22/08/2026, **928** decisions humaines sur 3 364
    pointaient vers une cle absente de l'index, sur 804 cles.

    OU VA CHAQUE PHOTO : les journaux d'annulation de `docs/` le disent —
    `old_key` -> `new_key` pour un deplacement ou un renommage, `canonique` pour
    un doublon absorbe. Ce n'est pas une ressemblance de nom ni une similarite
    de vecteur : c'est le geste lui-meme, ecrit par le programme qui l'a fait.

    DEUX GARDE-FOUS. La cible doit etre VIVANTE dans l'index (sinon on
    deplacerait une decision d'un mort vers un autre). Et l'index d'un
    rattachement doit tomber DANS les detections de la cible : `rekey_everywhere`
    a deplace la liste des detections en bloc, donc l'index est conserve — mais
    un doublon absorbe est un AUTRE fichier, re-detecte pour son compte. Un index
    hors bornes n'est plus un re-cle, c'est un pari : on saute la cle.

    Le meme chemin de code que le correctif preventif : `_recler_decisions_humaines`.
    Ce qui repare ici est exactement ce qui protegera demain.

    Reversible : chaque fiche touchee est journalisee AVANT/APRES dans
    `_corbeille_decisions/`, et `annuler_recle_decisions()` la remet.
    """
    vivantes = set(STORE.data.keys())
    chaine = journaux_deplacements.chaines(SCRIPT_DIR / 'docs')
    mortes = _decisions_sur_cles_mortes(vivantes)

    paires, sans_jumeau, hors_bornes = [], 0, 0
    for cle, par_genre in mortes.items():
        cible = journaux_deplacements.suivre(chaine, cle, vivantes)
        if not cible:
            sans_jumeau += 1
            continue
        if any(i >= 0 and i >= _detections_du_genre(g, cible)
               for g, i in par_genre.items()):
            hors_bornes += 1
            continue
        paires.append((cle, cible))

    res = {'ok': True, 'dry': dry, 'cles_mortes': len(mortes),
           'a_recler': len(paires), 'sans_jumeau': sans_jumeau,
           'hors_bornes': hors_bornes,
           'deplacements_connus': len(chaine)}
    if dry or not paires:
        res['decisions'] = 0
        return res

    interessantes = {c for c, _n in paires}
    avant = {}
    for magasin, _genre, st in _fiches_par_genre():
        for pk, pe in list(st.data.items()):
            if not isinstance(pe, dict):
                continue
            cite = any(
                (isinstance(kf, (list, tuple)) and len(kf) == 2
                 and kf[0] in interessantes)
                for kf in (pe.get('faces') or [])) or any(
                c in interessantes
                for champ in ('exclude', 'confirmed')
                for c in (pe.get(champ) or []))
            if cite:
                avant[(magasin, pk)] = {c: copy.deepcopy(pe.get(c))
                                        for c in CHAMPS_FICHE}

    n = 0
    for ancien, nouveau in paires:
        n += _recler_decisions_humaines(ancien, nouveau)
    for _magasin, _genre, st in _fiches_par_genre():
        st.save()

    lignes = [json.dumps({'at': time.time(), 'paires': len(paires),
                          'decisions': n}, ensure_ascii=False)]
    for (magasin, pk), etat in avant.items():
        st = PEOPLE_STORE if magasin == 'people' else PETS_STORE
        pe = st.data.get(pk) or {}
        lignes.append(json.dumps(
            {'magasin': magasin, 'fiche': pk, 'avant': etat,
             'apres': {c: pe.get(c) for c in CHAMPS_FICHE}},
            ensure_ascii=False))
    try:
        CORBEILLE_DECISIONS.mkdir(exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        (CORBEILLE_DECISIONS / f'recle_{ts}.jsonl').write_text(
            "\n".join(lignes) + "\n", encoding='utf-8')
    except OSError as e:
        print(f"  ⚠ quarantaine des décisions impossible : {e}")

    res.update(decisions=n, fiches=len(avant))
    print(f"  🔑 Re-clé des décisions : {n} sur {len(avant)} fiche(s), "
          f"{len(paires)} clé(s) — réversible (_corbeille_decisions/)")
    return res


def annuler_recle_decisions(journal=None):
    """Remet les fiches telles qu'elles etaient avant le dernier re-cle.

    Ne restaure une fiche que si son etat ACTUEL est bien celui que le journal
    a note en sortie : si un humain a juge depuis, on ne lui passe pas dessus —
    on le compte et on le dit."""
    try:
        js = sorted(CORBEILLE_DECISIONS.glob('recle_*.jsonl'))
    except OSError:
        js = []
    jp = Path(journal) if journal else (js[-1] if js else None)
    if not jp or not jp.is_file():
        return {'ok': False, 'error': 'aucun re-clé à annuler.'}
    remises, modifiees = 0, 0
    for i, ligne in enumerate(jp.read_text(encoding='utf-8').splitlines()):
        if not ligne.strip():
            continue
        try:
            op = json.loads(ligne)
        except ValueError:
            continue
        if i == 0 and 'fiche' not in op:
            continue
        st = PEOPLE_STORE if op.get('magasin') == 'people' else PETS_STORE
        pe = st.data.get(op.get('fiche'))
        if not isinstance(pe, dict):
            continue
        if {c: pe.get(c) for c in CHAMPS_FICHE} != op.get('apres'):
            modifiees += 1
            continue
        for champ, valeur in (op.get('avant') or {}).items():
            if valeur is None:
                pe.pop(champ, None)
            else:
                pe[champ] = valeur
        st.set(op['fiche'], pe, save=False)
        remises += 1
    for _magasin, _genre, st in _fiches_par_genre():
        st.save()
    try:
        jp.rename(jp.with_suffix('.jsonl.annule'))
    except OSError:
        pass
    return {'ok': True, 'fiches_remises': remises, 'fiches_modifiees_depuis':
            modifiees}


CORBEILLE_RECALAGE = SCRIPT_DIR / "_corbeille_recalage"
CORBEILLE_RETRAITS = SCRIPT_DIR / "_corbeille_retraits"
CORBEILLE_FUSIONS = SCRIPT_DIR / "_corbeille_fusions"


def _scores_des_visages(pe, cles):
    """{cle: [score de chaque detection]} — chaque visage d'une photo contre la
    signature de la fiche.

    MEME comparaison que `build_suggestions` : le maximum des facettes. Une cle
    absente du magasin de visages n'entre PAS dans le resultat, et la regle de
    recalage n'y touchera donc jamais — ne rien savoir n'autorise pas a bouger
    une decision humaine.
    """
    import numpy as np
    P = person_prototypes(pe)
    if P is None or not len(P):
        return {}
    out = {}
    for k in cles:
        e = FACE_STORE.data.get(k)
        if not isinstance(e, dict) or e.get('failed'):
            continue
        scores = []
        for f in (e.get('faces') or []):
            emb = f.get('emb') if isinstance(f, dict) else None
            v = None
            if emb:
                try:
                    v = _emb_from_b64(emb)
                except Exception:                                  # noqa: BLE001
                    v = None
            scores.append(float(np.max(P @ v)) if v is not None else None)
        out[k] = scores
    return out


def recaler_rattachements(dry=True):
    """Remet sur le BON VISAGE les rattachements dont l'index a glisse.

    LE DEFAUT. Un rattachement est un couple [photo, index du visage], et
    l'index designe une POSITION dans `FACE_STORE[photo]['faces']`. Or
    `reembed_one_batch` REMPLACE cette liste quand il re-analyse une photo :
    l'ordre et le nombre changent, le couple survit, sa cible non. Sur une
    photo de groupe, l'index de Didier finit par designer quelqu'un d'autre
    qui est sur la meme photo. Le garde-fou `assigned_keys` protege desormais
    l'avenir ; il n'a jamais repare le passe.

    MESURE (22/08/2026, `mesure_rattachements.py`, 1 194 couples) : **42
    decales**, dont **41 sur des photos reellement re-detectees** — 5,4 % la
    contre 0,4 % ailleurs. C'est une BORNE BASSE : une empreinte faussement
    confirmee est entree dans la signature et blanchit son propre couple.

    LA REGLE EST PURE ET PARTAGEE. `recale_rattachements.recaler_fiche` decide,
    ici comme dans le banc — l'apercu et l'application sont le MEME appel, donc
    l'apercu ne peut pas mentir. Ce module refuse de bouger des qu'il n'est pas
    sur, et chaque refus porte un nom (ecart insuffisant, sous le plancher,
    deja pris, ambigu).

    LES ANIMAUX NE SONT PAS TRAITES ICI. `PETS` porte des empreintes DINOv2,
    pas des visages, et personne ne l'a encore mesure. Reparer un magasin qu'on
    n'a pas mesure serait un pari — c'est un chantier a part.

    Reversible : chaque fiche touchee est journalisee AVANT/APRES dans
    `_corbeille_recalage/`, et `annuler_recalage()` la remet.
    """
    import recale_rattachements as recale
    pris = recale.rattachements_pris(
        pe for pe in PEOPLE_STORE.data.values() if isinstance(pe, dict))

    plan, refus_par_motif, avant = [], {}, {}
    for pk, pe in list(PEOPLE_STORE.data.items()):
        if not isinstance(pe, dict):
            continue
        cles = recale.photos_citees(pe)
        if not cles:
            continue
        scores = _scores_des_visages(pe, cles)
        if not scores:
            continue
        champs, recalages, refus = recale.recaler_fiche(
            pe, scores, deja_pris=pris)
        for r in refus:
            refus_par_motif[r['pourquoi']] = refus_par_motif.get(
                r['pourquoi'], 0) + 1
        if not champs:
            continue
        for r in recalages:
            plan.append(dict(r, person=pe.get('name', pk),
                             crop_de=_crop_url(r['key'], r['de']),
                             crop_vers=_crop_url(r['key'], r['vers'])))
        if not dry:
            avant[pk] = {c: copy.deepcopy(pe.get(c)) for c in CHAMPS_FICHE}
            for c, v in champs.items():
                pe[c] = v
            PEOPLE_STORE.set(pk, pe, save=False)

    res = {'ok': True, 'dry': dry, 'a_recaler': len(plan),
           'fiches': len(avant) if not dry else None,
           'refus': refus_par_motif,
           'exemples': plan[:20]}
    if dry or not plan:
        return res

    PEOPLE_STORE.save()
    lignes = [json.dumps({'at': time.time(), 'recalages': len(plan)},
                         ensure_ascii=False)]
    for pk, etat in avant.items():
        pe = PEOPLE_STORE.data.get(pk) or {}
        lignes.append(json.dumps(
            {'magasin': 'people', 'fiche': pk, 'avant': etat,
             'apres': {c: pe.get(c) for c in CHAMPS_FICHE}},
            ensure_ascii=False))
    try:
        CORBEILLE_RECALAGE.mkdir(exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        (CORBEILLE_RECALAGE / f'recalage_{ts}.jsonl').write_text(
            "\n".join(lignes) + "\n", encoding='utf-8')
    except OSError as e:
        print(f"  ⚠ quarantaine du recalage impossible : {e}")
    # Les signatures et les avatars sont derives des rattachements : la file du
    # curateur doit se refaire, sinon elle continue de proposer sur l'ancienne
    # carte. On la vide plutot que de la recalculer ici (l'UI la reconstruit).
    _suggest_remove(lambda s: True)
    print(f"  🎯 Recalage : {len(plan)} rattachement(s) remis sur le bon "
          f"visage, {len(avant)} fiche(s) — réversible (_corbeille_recalage/)")
    return res


def retirer_rattachements(dry=True):
    """Retire les rattachements qu'un HUMAIN a jugés faux sur `/residu`.

    CE GESTE EFFACE UNE DECISION HUMAINE — c'est ce qui le separe du recalage,
    qui ne fait que la deplacer. Rien ne part sans un verdict EXPLICITE portant
    sur ce couple precis : le module `retrait_rattachements` lit les cas et les
    verdicts, et c'est LUI qui decide, ici comme dans le banc (`--bilan-residu`).
    L'apercu et l'application sont le MEME appel : l'apercu ne peut pas mentir.

    CE QUI N'EST PAS FAIT ICI, VOLONTAIREMENT. Les visages reconnus mais NON
    cites (« a ajouter ») sont comptes et laisses : ce serait une ATTRIBUTION,
    un autre geste et un autre risque, et le glisser dans un bouton nomme
    « retirer » serait poser un nom en douce.

    Le TAG de la photo ne bouge pas : il vit dans l'index et dans le XMP
    (regle 2). Ce qui part, c'est la vérité terrain « CE visage est elle » —
    et c'est precisement ce que l'humain vient de dire faux.

    Reversible : chaque fiche touchee est journalisee AVANT/APRES dans
    `_corbeille_retraits/`, et `annuler_retrait()` la remet.
    """
    import retrait_rattachements as retrait
    try:
        cas = json.loads(RESIDU_A_JUGER.read_text(encoding='utf-8')).get('cas') or []
    except (OSError, ValueError):
        return {'ok': False, 'error': "aucun cas à juger : lance "
                                      "mesure_rattachements.py --residu."}
    with RESIDU_LOCK:
        verdicts = _residu_lire_jugements()
    if not verdicts:
        return {'ok': False, 'error': "aucun verdict : la page /residu n'a "
                                      "encore rien recueilli. Un plan de "
                                      "suppression sans jugement n'est qu'une "
                                      "promesse."}
    plan = retrait.plan_depuis_verdicts(cas, verdicts)
    comptes = plan['comptes']
    groupes = retrait.par_fiche(plan['retraits'])

    exemples, avant, faits, absents = [], {}, 0, 0
    for pk, couples in groupes.items():
        pe = PEOPLE_STORE.data.get(pk)
        if not isinstance(pe, dict):
            absents += len(couples)
            continue
        champs, bilan = retrait.retirer_de_la_fiche(pe, couples)
        absents += bilan['deja_absents']
        for c in couples:
            if len(exemples) < 30:
                exemples.append(dict(c, crop=_crop_url(c['key'], c['i'])))
        if not champs:
            continue
        faits += bilan['retires']
        if not dry:
            avant[pk] = {ch: copy.deepcopy(pe.get(ch)) for ch in CHAMPS_FICHE}
            for ch, v in champs.items():
                pe[ch] = v
            PEOPLE_STORE.set(pk, pe, save=False)

    res = {'ok': True, 'dry': dry, 'a_retirer': comptes['a_retirer'],
           'retires': faits, 'deja_absents': absents,
           'confirmes': comptes['confirmes'],
           'a_ajouter': comptes['a_ajouter'],
           'non_juges': comptes['non_juges'],
           'indecidables': comptes['indecidables'],
           'fiches': len(avant) if not dry else len(groupes),
           'exemples': exemples}
    if dry or not faits:
        return res

    PEOPLE_STORE.save()
    lignes = [json.dumps({'at': time.time(), 'retraits': faits},
                         ensure_ascii=False)]
    for pk, etat in avant.items():
        pe = PEOPLE_STORE.data.get(pk) or {}
        lignes.append(json.dumps(
            {'magasin': 'people', 'fiche': pk, 'avant': etat,
             'apres': {ch: pe.get(ch) for ch in CHAMPS_FICHE}},
            ensure_ascii=False))
    try:
        CORBEILLE_RETRAITS.mkdir(exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        (CORBEILLE_RETRAITS / f'retrait_{ts}.jsonl').write_text(
            "\n".join(lignes) + "\n", encoding='utf-8')
    except OSError as e:
        print(f"  ⚠ quarantaine du retrait impossible : {e}")
    # Signatures et avatars derivent des rattachements : la file du curateur
    # se refait, sinon elle continue de proposer sur l'ancienne carte.
    _suggest_remove(lambda s: True)
    print(f"  ✂ Retrait : {faits} rattachement(s) juge(s) faux retire(s), "
          f"{len(avant)} fiche(s) — réversible (_corbeille_retraits/)")
    return res


def annuler_retrait(journal=None):
    """Remet les fiches telles qu'elles etaient avant le dernier retrait.

    Meme prudence que `annuler_recalage` : une fiche modifiee depuis n'est pas
    ecrasee, elle est comptee et dite."""
    try:
        js = sorted(CORBEILLE_RETRAITS.glob('retrait_*.jsonl'))
    except OSError:
        js = []
    jp = Path(journal) if journal else (js[-1] if js else None)
    if not jp or not jp.is_file():
        return {'ok': False, 'error': 'aucun retrait à annuler.'}
    remises, modifiees = 0, 0
    for i, ligne in enumerate(jp.read_text(encoding='utf-8').splitlines()):
        if not ligne.strip():
            continue
        try:
            op = json.loads(ligne)
        except ValueError:
            continue
        if i == 0 and 'fiche' not in op:
            continue
        pe = PEOPLE_STORE.data.get(op.get('fiche'))
        if not isinstance(pe, dict):
            continue
        if {ch: pe.get(ch) for ch in CHAMPS_FICHE} != op.get('apres'):
            modifiees += 1
            continue
        for champ, valeur in (op.get('avant') or {}).items():
            if valeur is None:
                pe.pop(champ, None)
            else:
                pe[champ] = valeur
        PEOPLE_STORE.set(op['fiche'], pe, save=False)
        remises += 1
    PEOPLE_STORE.save()
    _suggest_remove(lambda s: True)
    try:
        jp.rename(jp.with_suffix('.jsonl.annule'))
    except OSError:
        pass
    return {'ok': True, 'fiches_remises': remises,
            'fiches_modifiees_depuis': modifiees}


def annuler_recalage(journal=None):
    """Remet les fiches telles qu'elles etaient avant le dernier recalage.

    Ne restaure une fiche que si son etat ACTUEL est bien celui que le journal
    a note en sortie : si un humain a juge depuis, on ne lui passe pas dessus —
    on le compte et on le dit."""
    try:
        js = sorted(CORBEILLE_RECALAGE.glob('recalage_*.jsonl'))
    except OSError:
        js = []
    jp = Path(journal) if journal else (js[-1] if js else None)
    if not jp or not jp.is_file():
        return {'ok': False, 'error': 'aucun recalage à annuler.'}
    remises, modifiees = 0, 0
    for i, ligne in enumerate(jp.read_text(encoding='utf-8').splitlines()):
        if not ligne.strip():
            continue
        try:
            op = json.loads(ligne)
        except ValueError:
            continue
        if i == 0 and 'fiche' not in op:
            continue
        pe = PEOPLE_STORE.data.get(op.get('fiche'))
        if not isinstance(pe, dict):
            continue
        if {c: pe.get(c) for c in CHAMPS_FICHE} != op.get('apres'):
            modifiees += 1
            continue
        for champ, valeur in (op.get('avant') or {}).items():
            if valeur is None:
                pe.pop(champ, None)
            else:
                pe[champ] = valeur
        PEOPLE_STORE.set(op['fiche'], pe, save=False)
        remises += 1
    PEOPLE_STORE.save()
    _suggest_remove(lambda s: True)
    try:
        jp.rename(jp.with_suffix('.jsonl.annule'))
    except OSError:
        pass
    return {'ok': True, 'fiches_remises': remises,
            'fiches_modifiees_depuis': modifiees}



def _fiche_pour_journal(fiche):
    """Copie JSON-SURE d'une fiche, pour le journal de fusion.

    POURQUOI PAS `copy.deepcopy`. Le 23/08, la fusion Flo -> Florine est morte
    sur `TypeError: cannot pickle '_thread.RLock' object`, dans le deepcopy de
    la fiche. Une fiche VIVANTE peut porter, en memoire, autre chose que les
    decisions humaines qu'elle stocke sur disque — et un verrou ne se copie
    pas. Dans l'ancien ordre le defaut frappait APRES une heure de balayage :
    les 5 907 photos etaient renommees, la fusion des fiches n'avait pas lieu,
    aucun journal n'etait ecrit, et le message n'arrivait que dans la console.

    Le journal n'a besoin que de ce qui se RELIT : `confirmed`, `exclude`,
    `nomerge`, `faces`, `avatar`, `at`. Ce qui ne passe pas en JSON est donc
    ECARTE et NOMME dans la console — un champ inattendu est une information,
    pas une raison de faire tomber le geste le plus lourd du projet.

    Ligne d'impression en ASCII PUR : l'agent git lance les tests sans
    PYTHONUTF8, et sur une console cp1252 un symbole leve une
    UnicodeEncodeError qui fait passer des tests au rouge sans nommer sa cause.
    """
    if not isinstance(fiche, dict):
        return None
    out, refuses = {}, []
    for k, v in fiche.items():
        try:
            json.dumps(v, ensure_ascii=False)
        except (TypeError, ValueError):
            refuses.append(str(k))
            continue
        out[k] = copy.deepcopy(v)
    if refuses:
        print("  Fiche %r : champ(s) non JSON ecarte(s) du journal : %s"
              % (str(fiche.get('name') or '?'), ", ".join(refuses)))
    return out


def _journal_fusion(prefix, ancien, nouveau, touchees, avant_old, avant_new,
                    apres_new):
    """Note ce qu'une fusion de fiches vient de prendre, pour pouvoir le rendre.

    POURQUOI. Fusionner deux noms est le seul geste de ce projet qui reecrive
    des MILLIERS de fichiers du fonds — Flo vers Florine, le 22/08 : 5 907
    photos, 11 814 operations exiftool. Tous les autres gestes destructeurs ont
    leur quarantaine (`_corbeille_recalage`, `_corbeille_retraits`,
    `_corbeille_decisions`) ; celui-la, le plus lourd, n'en avait aucune.

    CE QUI EST NOTE, ET POURQUOI CE N'EST PAS UN SIMPLE `rename` INVERSE.
    Renommer Florine en Flo pour revenir en arriere emporterait aussi les
    photos qui portaient Florine AVANT la fusion (153 au 22/08, dont 149 qui
    portaient les deux noms). Un aller-retour ne rend pas ce qu'il a pris. Le
    journal note donc, photo par photo, si elle portait DEJA le nouveau nom :
    `annuler_fusion` ne retire le nouveau tag que de celles qui ne l'avaient
    pas, et rend l'ancien a toutes.

    Les deux fiches sont notees AVANT (pour les rendre) et APRES (pour refuser
    de passer sur un humain qui aurait juge depuis) — meme prudence que
    `annuler_retrait` et `annuler_recalage`.
    """
    if not touchees and avant_old is None:
        return None
    try:
        CORBEILLE_FUSIONS.mkdir(exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        jp = CORBEILLE_FUSIONS / f'fusion_{ts}.jsonl'
        i = 0
        while jp.exists():          # deux fusions dans la meme seconde : la
            i += 1                  # seconde ne doit pas effacer la premiere
            jp = CORBEILLE_FUSIONS / f'fusion_{ts}_{i}.jsonl'
        lignes = [json.dumps(
            {'at': time.time(), 'prefix': prefix, 'ancien': ancien,
             'nouveau': nouveau, 'photos': len(touchees),
             'fiche_ancienne': avant_old, 'fiche_cible_avant': avant_new,
             'fiche_cible_apres': apres_new}, ensure_ascii=False)]
        for k, deja in touchees:
            lignes.append(json.dumps({'k': k, 'deja': deja},
                                     ensure_ascii=False))
        jp.write_text("\n".join(lignes) + "\n", encoding='utf-8')
        # ASCII PUR, et ce n'est pas de la coquetterie : c'est la seule ligne
        # de prod qu'un TEST execute directement, et l'agent git lance les
        # tests sans PYTHONUTF8 — sur une console cp1252, un « ↻ » leve une
        # UnicodeEncodeError qui fait passer 11 tests au rouge sans nommer sa
        # cause (22/08 : deux refus de livraison avant de comprendre). Le banc,
        # lui, force l'UTF-8 : les deux portes ne jugeaient pas la meme chose.
        print("  Fusion journalisee : %s -> %s, %d photo(s) - reversible (%s)"
              % (ancien, nouveau, len(touchees), jp.name))
        return jp
    except OSError as e:
        print(f"  \u26a0 journal de fusion impossible : {e}")
        return None


def fusions_journalisees():
    """Les journaux de fusion encore annulables, du plus ancien au plus recent."""
    try:
        return sorted(CORBEILLE_FUSIONS.glob('fusion_*.jsonl'))
    except OSError:
        return []


def annuler_fusion(journal=None):
    """Defait la derniere fusion de fiches : les deux noms reviennent, et
    chaque photo retrouve le tag qu'elle portait.

    Les tags des FICHIERS repassent par la file d'ecriture XMP : l'annulation
    coute autant d'operations que la fusion, et ne se voit sur le NAS qu'une
    fois la file vidée.

    Une fiche cible modifiee depuis la fusion n'est pas ecrasee : elle est
    comptee et dite. Le reste est quand meme rendu — les tags des photos ne
    dependent pas de l'etat de la fiche.
    """
    js = fusions_journalisees()
    jp = Path(journal) if journal else (js[-1] if js else None)
    if not jp or not jp.is_file():
        return {'ok': False, 'error': 'aucune fusion à annuler.'}
    try:
        lignes = jp.read_text(encoding='utf-8').splitlines()
        entete = json.loads(lignes[0])
    except (OSError, ValueError, IndexError):
        return {'ok': False, 'error': f'journal illisible : {jp.name}'}
    prefix = entete.get('prefix') or 'personne'
    sujet = SUBJECTS.get(prefix)
    if sujet is None:
        return {'ok': False, 'error': f'genre inconnu : {prefix}'}
    ancien, nouveau = entete.get('ancien') or '', entete.get('nouveau') or ''
    if not ancien or not nouveau:
        return {'ok': False, 'error': f'journal incomplet : {jp.name}'}
    oldtag, newtag = f"{prefix}:{ancien}", f"{prefix}:{nouveau}"

    rendus, absents = 0, 0
    for ligne in lignes[1:]:
        if not ligne.strip():
            continue
        try:
            op = json.loads(ligne)
        except ValueError:
            continue
        k = op.get('k')
        if k not in STORE.data:
            absents += 1
            continue
        _index_add_person(k, oldtag)
        _enqueue_person_write(k, oldtag, 'add')
        if not op.get('deja'):
            _index_remove_person(k, newtag)
            _enqueue_person_write(k, newtag, 'del')
        rendus += 1

    st = sujet.store
    ecrasee = 0
    if st.data.get(nouveau.lower()) != entete.get('fiche_cible_apres'):
        ecrasee = 1                       # jugee depuis : on n'y touche pas
    else:
        avant = entete.get('fiche_cible_avant')
        if avant is None:
            st.data.pop(nouveau.lower(), None)
        else:
            st.set(nouveau.lower(), avant, save=False)
    if entete.get('fiche_ancienne') is not None:
        st.set(ancien.lower(), entete['fiche_ancienne'], save=False)
    st.save()
    STORE.save()
    _suggest_remove(lambda s: True)
    try:
        jp.rename(jp.with_suffix('.jsonl.annule'))
    except OSError:
        pass
    return {'ok': True, 'photos_rendues': rendus, 'photos_disparues': absents,
            'ancien': ancien, 'nouveau': nouveau,
            'fiche_cible_jugee_depuis': ecrasee}


def forget_everywhere(keys, motif='oubli', label=''):
    """Inverse de `rekey_everywhere` : OUBLIE completement des cles dont le
    FICHIER a disparu. Sans elle, la purge du scan (`_sync_dir` etape 4) ne
    retirait que le store `tags` et laissait les detections visages/animaux et
    le vecteur semantique orphelins (bug « ARZOPA », constate le 08/08 :
    ~4 500 detections de fichiers supprimes subsistaient).

    Retire donc, pour chaque cle :
      - l'entree `tags` (STORE) ;
      - les detections `faces` et `animals` — dont leurs vecteurs, purges par
        `_ecrire` (via `vec.delete_prefix`) au moment du `remove_many` ;
      - le vecteur semantique nu (kind='photo') via `delete_all`.

    AUCUN nom humain perdu, par construction : les fiches PEOPLE/PETS sont keyees
    par NOM (« mike », « luna »), pas par chemin de photo — elles ne sont donc
    jamais touchees ici. Le tag `personne:`/`animal:` de la photo disparait avec
    la photo (elle n'existe plus), mais la fiche et sa signature (refs = copies)
    survivent. Renvoie le nombre d'entrees `tags` retirees.

    `motif` / `label` : DECLARATION au carnet de comptes (comptes_index.py).
    Le nombre renvoye ne suffisait pas — personne ne l'enregistrait (17/08).
    L'appelant dit desormais POURQUOI il oublie, et le registre garde la trace
    (compte par motif + exemples de cles), lisible dans /reglages.
    """
    keys = [k for k in keys if k]
    if not keys:
        return 0
    with REGISTRE.motif(motif, label=label):
        n = STORE.remove_many(keys)
    # Seules FACE_STORE et ANIMAL_STORE portent des detections keyees par photo.
    # PEOPLE/PETS sont keyes par nom -> volontairement exclus (ne rien casser).
    for st in (FACE_STORE, ANIMAL_STORE):
        try:
            st.remove_many(keys)
        except Exception as e:                               # noqa: BLE001
            print(f"  ⚠ oubli {getattr(st, 'path', st)} : {e}")
    # 7e magasin keye par chemin (audit I2) : libelles de geocodage.
    try:
        gps_places_forget(keys)
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠ oubli gps_places : {e}")
    if hasattr(STORE, 'cx'):
        try:
            # Sous STORE.lock (audit O4) : delete_all transactionne sur la
            # connexion partagée — même risque de croisement que rekey.
            pv = photo_vectors()
            with STORE.lock:
                for k in keys:
                    pv.delete_all(k)
        except Exception as e:                               # noqa: BLE001
            print(f"  ⚠ oubli vecteur semantique : {e}")
    return n


def purge_cles_fantomes(dry_run=False):
    """Retire les CLES FANTOMES de FACE_STORE/ANIMAL_STORE : des cles MALFORMEES
    qui ne resolvent vers aucun fichier alors qu'un DOUBLON de meme basename
    existe sous une cle qui, elle, se resout (cas « ARZOPA » : la vraie photo est
    sous « ads\\ARZOPA\\x.JPG », un doublon fantome traine sous « ARZOPA/x.JPG »
    sans la racine). Ces cles fantomes gonflaient la file « A verifier » de
    /people avec des cartes sans vignette (/api/facecrop 404).

    A la difference des fichiers disparus (traites par _sync_dir via la liste du
    dossier), une cle fantome n'appartient a aucun dossier scanne : elle ne se
    resout tout simplement pas. On la detecte SANS stater tout le store :
    `cles_fantomes_par_collision` ne stat que les basenames en COLLISION (rares).

    SANS RISQUE par construction : on ne retire qu'un doublon dont la vraie donnee
    subsiste sous la bonne cle ; et jamais une cle portant un nom humain
    (`personne:`/`animal:`). Ne s'execute que si Uploads est joignable (sinon tout
    passerait pour fantome — meme prudence que _sync_dir). Renvoie la liste
    purgee (ou seulement detectee si dry_run)."""
    try:
        if not UPLOAD_DIR.exists():
            return []
    except OSError:
        return []
    from verifier_orphelins import cles_fantomes_par_collision
    # Cles portant un nom humain : jamais touchees (garde-fou defensif ; en
    # pratique le nom vit dans STORE/PEOPLE, pas dans une cle fantome).
    named = set()
    for k, se in list(STORE.data.items()):
        if isinstance(se, dict) and any(
                est_tag_nomme(kw) for kw in (se.get('kw_fr') or [])):
            named.add(k)

    def _est_fichier(k):
        try:
            return _resolve_key(k).is_file()
        except OSError:
            return False

    fantomes = []
    for st in (FACE_STORE, ANIMAL_STORE):
        fantomes += cles_fantomes_par_collision(
            list(st.data.keys()), _est_fichier, named)
    fantomes = sorted(set(fantomes))
    if fantomes and not dry_run:
        forget_everywhere(fantomes, motif='purge:cles_fantomes')
    return fantomes


# ── Detections HORS INDEX : le TROISIEME orphelin (mesure le 21/08) ─────────
# 2 374 fiches de visages et 2 377 de detections animales survivaient a des
# cles que `tags` avait oubliees — exactement les 2 374 cles dont la purge du
# 17/08 avait retire les vecteurs SigLIP en laissant les visages. Personne
# n'etait charge de les retirer :
#   * `_sync_dir` calcule ses orphelins A PARTIR de `STORE` : une cle deja
#     absente de l'index lui est INVISIBLE, `forget_everywhere` n'est donc
#     jamais appele pour elle ;
#   * `purge_cles_fantomes` exige un JUMEAU VIVANT de meme basename, or les
#     deux jumeaux (`ARZOPA/x` et `...\_Uploads\ARZOPA\x`) etaient morts.
# Cout mesure : le curateur re-scorait 3 698 visages morts toutes les 240 s,
# rejetes en silence par le garde-fou des cles fantomes.
DETECTIONS_TRASH_DIR = SCRIPT_DIR / "_corbeille_detections"


def _cles_jugees_par_un_humain():
    """Cles portant une decision humaine (rattachement, exclusion,
    confirmation) d'apres les fiches PEOPLE/PETS.

    Les trois comptent : « ce visage n'est PAS Flo » est une etiquette humaine
    au meme titre qu'un rattachement. Aucune de ces cles ne se purge, meme si
    sa photo a disparu — regle 2 du projet, et le 21/08 en a denombre 120."""
    out = set()
    for st in (PEOPLE_STORE, PETS_STORE):
        for pe in list(st.data.values()):
            if not isinstance(pe, dict) or not pe.get('name'):
                continue
            for kf in (pe.get('faces') or []):
                if isinstance(kf, (list, tuple)) and len(kf) == 2:
                    out.add(kf[0])
            out.update(pe.get('exclude') or [])
            out.update(pe.get('confirmed') or [])
    return out


def _quarantaine_detections(lots):
    """Ecrit les entrees AVANT de les retirer. Une purge sans trace n'est pas
    reversible — et le 17/08 a prouve que la trace sert : c'est son fichier de
    quarantaine qui a permis, quatre jours apres, d'etablir que les deux
    magasins n'avaient pas ete traites pareil."""
    DETECTIONS_TRASH_DIR.mkdir(parents=True, exist_ok=True)
    chemin = DETECTIONS_TRASH_DIR / time.strftime(
        "detections_hors_index_%Y%m%d_%H%M%S.jsonl")
    n = 0
    with chemin.open('w', encoding='utf-8') as f:
        for table, cles in lots.items():
            st = FACE_STORE if table == 'faces' else ANIMAL_STORE
            for k in cles:
                e = st.data.get(k)
                if e is None:
                    continue
                f.write(json.dumps({"table": table, "k": k, "v": dict(e)},
                                   ensure_ascii=False) + "\n")
                n += 1
    return chemin, n


def purge_detections_hors_index(dry_run=False):
    """Retire les detections dont la cle a quitte l'index et n'y reviendra pas.

    DEUX GARDE-FOUS, non negociables :
      * une cle portant une DECISION HUMAINE n'est jamais touchee ;
      * on ne retire que ce que l'index ne reprendra JAMAIS : fichier absent,
        ou chemin cache (`.corbeille-rangement`, `@eaDir`). Une cle dont le
        fichier existe encore sous un chemin normal est en attente de
        re-tagging (`scan:modifies` retire l'entree le temps du cycle) : la
        purger ferait perdre des detections que le scan allait rendre. Elle est
        COMPTEE, pas touchee — un residu qui grossit est un signal.
    Ne s'execute que si la racine des uploads est joignable : NAS debranche,
    tout passerait pour disparu (meme prudence que `_sync_dir`).
    Quarantaine JSONL avant tout retrait. Renvoie (purgees, protegees, attente).
    """
    try:
        if not UPLOAD_DIR.exists():
            return [], [], []
    except OSError:
        return [], [], []
    from verifier_orphelins import cles_hors_index_a_purger

    def _est_fichier(k):
        try:
            return _resolve_key(k).is_file()
        except OSError:
            return True          # doute -> on ne purge pas
    def _est_cache(k):
        try:
            return _is_hidden_path(_resolve_key(k))
        except OSError:
            return False

    cles_tags = set(STORE.data)
    proteges = _cles_jugees_par_un_humain()
    lots, purgees, protegees, attente = {}, [], [], []
    for st, table in ((FACE_STORE, 'faces'), (ANIMAL_STORE, 'animals')):
        a_purger, prot, att = cles_hors_index_a_purger(
            list(st.data.keys()), cles_tags, proteges, _est_fichier, _est_cache)
        lots[table] = a_purger
        purgees += a_purger
        protegees += prot
        attente += att
    purgees = sorted(set(purgees))
    if purgees and not dry_run:
        try:
            chemin, n = _quarantaine_detections(lots)
            print(f"  \U0001f5c4 quarantaine : {n} detection(s) ecrite(s) dans "
                  f"{chemin.name}")
        except OSError as e:                                 # noqa: BLE001
            # Pas de trace = pas de purge. Le retrait attendra.
            print(f"  ! quarantaine impossible ({e}) : purge ANNULEE")
            return [], sorted(set(protegees)), sorted(set(attente))
        forget_everywhere(purgees, motif='purge:hors_index')
    return purgees, sorted(set(protegees)), sorted(set(attente))


# ─── Operations de fichiers (vue Dossiers) ───────────────────────────────────
# Logique pure et testee dans fichiers.py (module stdlib, import leger). La
# re-cle de l'index passe par rekey_everywhere : un deplacement/renommage ne
# perd jamais un nom humain. « Supprimer » = quarantaine reversible, jamais rm.
import fichiers
FILE_OPS = None
FILE_OPS_LOCK = threading.Lock()


def _corbeille_effacements():
    """Où vont les effacements (chantier 17, étape 6 ; choix de Mike, 29/08 :
    « effacer, c'est effacer du NAS ») : `.corbeille-effacements` à la racine
    du premier dossier tagué — le NAS, sauvegardé par son snapshot, et le
    nom ne se confond pas avec `.corbeille-rangement` du dédoublonnage. Le
    point la cache au scan (`_is_hidden_path`) : au démarrage ses clés sont
    oubliées, comme avant, et `restaurer` les rend au scan. Repli sur le
    dossier du script si aucun dossier tagué n'est déclaré."""
    for d in _load_dirs_file(TAG_DIRS_FILE):
        return Path(d) / ".corbeille-effacements"
    return SCRIPT_DIR / ".corbeille-effacements"


FILES_TRASH_DIR = _corbeille_effacements()


def file_ops():
    """Singleton FileOps branche sur les magasins du serveur (cree a la 1re
    utilisation, donc apres l'ouverture des stores)."""
    global FILE_OPS
    if FILE_OPS is None:
        FILE_OPS = fichiers.FileOps(
            roots_fn=media_roots,
            resolve_key=_resolve_key,
            store_keys=lambda: list(STORE.data.keys()),
            rekey=rekey_everywhere,
            journal_path=SCRIPT_DIR / "fichiers_undo.json",
            trash_dir=FILES_TRASH_DIR,
            garde=refus_ecriture,          # étape 5 : chacun n'efface que ses photos
            auteur=utilisateur_vu)         # étape 6 : le journal dit QUI a effacé
    return FILE_OPS


def _sans_accents(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower())
                   if unicodedata.category(c) != 'Mn')


def noms_connus():
    """{nom normalisé: tag} pour toutes les personnes et tous les animaux."""
    index = {}
    for store, prefixe in ((PEOPLE_STORE, 'personne'), (PETS_STORE, 'animal')):
        for e in store.data.values():
            nom = (e.get('name') or '').strip()
            if nom:
                index[_sans_accents(nom)] = f"{prefixe}:{nom}"
    return index


# ─── Le garde-fou du filtre (26/08) ──────────────────────────────────────────
# `/files?q=animal:Zzzznexistepas` rendait **1 500 photos**, et la page
# annonçait un FILTRE. Le jeton ne ressemblait à aucun nom NU — `_extraire_noms`
# ne connaît aucun préfixe — il partait donc en recherche sémantique. Le défaut
# corrigé le 21/08 pour `espece:licorne` vivait encore sur les quatre autres
# axes, et l'interface écrit elle-même ce vocabulaire : « le FILTRE de la
# planche garde les tags nommés : y chercher personne:Luna a du sens »
# (`gallery.html`). La règle est désormais commune aux cinq axes, dans
# `recherche.extraire_jetons` : ce qu'on ne sait pas satisfaire rend RIEN.
#
# `espece:` n'est PAS dans cette table : `extraire_especes` l'a déjà consommé
# quand on arrive ici. L'ordre de `semantic_search` reste l'invariant.
AXES_DE_JETON = {'personne': 'personne', 'personnes': 'personne',
                 'animal': 'animal', 'animaux': 'animal',
                 'lieu': 'lieu', 'lieux': 'lieu'}


def _resoudre_jeton(axe, valeur):
    """Valeur canonique d'un jeton `<axe>:<valeur>`, ou None.

    **L'axe doit être le bon.** « Luna » est une chatte : `personne:Luna` ne
    doit pas rendre ses photos — il doit dire qu'aucune PERSONNE ne porte ce
    nom. Rendre les photos de l'animal serait deviner à la place de
    l'utilisateur ; les rendre TOUTES était le défaut d'hier.

    Lit les mêmes autorités que le reste du moteur : `noms_connus()` (fiches
    personnes et animaux) et `lieux_connus()`. Aucun vocabulaire en dur.
    """
    v = _sans_accents(valeur)
    if axe in ('personne', 'animal'):
        tag = noms_connus().get(v)
        if tag:
            prefixe, nom = tag.split(':', 1)
            if prefixe == axe:
                return nom
        return None
    if axe == 'lieu':
        return lieux_connus().get(v)
    return None


def _extraire_noms(requete):
    """Détache de la requête les noms de personnes/animaux qu'elle contient.

    « Luna endormie sur le canapé » → (['animal:Luna'], 'endormie sur le canapé')
    Les noms composés sont testés en premier (« Le chat de Bremblens »).
    """
    index = noms_connus()
    reste = ' ' + _sans_accents(requete) + ' '
    original = requete
    trouves = []
    for nom in sorted(index, key=len, reverse=True):
        motif = ' ' + nom + ' '
        if motif in reste:
            trouves.append(index[nom])
            reste = reste.replace(motif, ' ')
            # retire aussi du texte d'origine, en respectant les accents
            i = _sans_accents(original).find(nom)
            if i >= 0:
                original = original[:i] + original[i + len(nom):]
    return trouves, ' '.join(original.split())


def _cles_portant(tags):
    """Clés qui portent TOUS les noms demandés — d'après l'AUTORITÉ VIVANTE.

    Pas d'après les `kw` bruts de l'index, et c'est la correction du 20/08
    (chantier 14a-iv) : le filtre les lisait tels quels, tandis que la ligne de
    faits sous la vignette lit les fiches, où `exclude` fait autorité. Les deux
    répondaient à la même question par deux chemins, donc ils divergeaient —
    **13 photos** que la recherche rendait alors que leur ligne de faits ne
    portait pas le nom (Mike 6, Flo 5, Silvio 1, Danica 1). Un nom retiré à la
    main réapparaissait dans le seul endroit où l'utilisateur le cherche : la
    forme de régression la plus chère du projet, en silence.

    Les `kw_en` restent lus : un nom n'y est pas censé être, mais s'il s'y
    trouve encore, l'oublier RETIRERAIT une photo trouvable — un retrait doit
    venir d'un humain, jamais d'un refactoring.

    Coût : le balayage de l'index était déjà là ; s'y ajoute un seul passage
    sur les 363 fiches (`_autorite_des_noms`), pas un par photo."""
    besoin = [t.lower() for t in tags]
    attendus, exclus, _canon = _autorite_des_noms()
    out = set()
    for k, e in list(STORE.data.items()):
        if e.get('failed'):
            continue
        ex = exclus.get(k) or ()
        kw = {str(x).lower() for x in
              ((e.get('kw_fr') or []) + (e.get('kw_en') or []))}
        kw -= set(ex)
        kw |= {t.lower() for t in (attendus.get(k) or ())}
        if all(t in kw for t in besoin):
            out.add(k)
    return out



# ─── Espèce (5ᵉ axe, chantier 14a) ───────────────────────────────────────────
# Deux regards INDÉPENDANTS doivent dire la même espèce : YOLO qui l'a détectée
# dans les pixels, et le tagueur qui l'a écrite en français. C'est la
# CONCORDANCE, et c'est le choix du 20/08 — pas `det_score`, qui dit « il y a
# un animal ici » sans dire lequel (`cheval` 0,934 sur un chien).

def _cles_de_l_espece(mots):
    """Clés dont YOLO **et** le tagueur disent l'espèce — toutes les espèces
    demandées, comme `_cles_portant` exige tous les noms.

    On part de l'ANIMAL_STORE et non de l'index : seules ~4 750 photos portent
    une détection, contre 43 000 entrées. Le filtre ne coûte donc pas un
    balayage du fonds, et il n'a **aucun cache à invalider** — une photo taguée
    il y a dix secondes est filtrable tout de suite. Un index à rafraîchir
    aurait été plus rapide et parfois faux ; ici la fraîcheur est gratuite.

    Les 82 photos taguées AVEC les faits en contexte sont GARDÉES, alors que le
    banc les écarte. Ce n'est pas une divergence : le banc mesure un ACCORD, et
    un accord obtenu en soufflant la réponse ne prouve rien ; l'utilisateur,
    lui, cherche sa photo de chat — la lui cacher au nom de la méthode serait
    absurde."""
    import faits_vue
    out = None
    for mot in mots:
        label = faits_vue.label_de_l_espece(mot)
        if label is None:
            return set()
        vues = set()
        for k, ae in list(ANIMAL_STORE.data.items()):
            if not isinstance(ae, dict):
                continue
            if not any(isinstance(a, dict) and a.get('species') == label
                       for a in (ae.get('animals') or [])):
                continue
            e = STORE.data.get(k)
            if not isinstance(e, dict) or e.get('failed'):
                continue
            if any(faits_vue.dit_l_espece(e, mot)):
                vues.add(k)
        out = vues if out is None else (out & vues)
    return out if out is not None else set()


# ─── Lieux ───────────────────────────────────────────────────────────────────
# Seules 2 % des photos portent des coordonnées GPS. Les NOMS DE DOSSIERS, eux,
# sont une mine : « Danemark », « 07 Voyage en Indonésie », « Bolivie 2015 ».
# On en tire un vocabulaire de lieux, épuré des noms d'appareils et des dates.
LIEUX_FICHIER = SCRIPT_DIR / "lieux.txt"
_LIEUX_CACHE = {"at": 0.0, "index": {}}
# Géocodage inverse OFFLINE (enrichir_lieux.py) : clé_photo -> libellé de lieu,
# précalculé contre un gazetteer LOCAL (aucun GPS envoyé à un service tiers). Le
# serveur ne fait qu'ATTACHER ce fait au renommage ; il ne géocode pas lui-même.
# Absent tant que le batch n'a pas tourné -> {} (le segment lieu est omis).
GPS_PLACES_FICHIER = SCRIPT_DIR / "gps_places.json"
_GPS_PLACES_CACHE = {"mtime": -1.0, "index": {}}
def _lieu_plausible(nom):
    """Un dossier est-il un nom de lieu ? Heuristique, corrigeable à la main.

    La règle vit dans `faits_vue` — une seule implémentation pour le serveur et
    pour la VUE des faits. Deux règles qui se ressemblent finissent par
    diverger, et une provenance qui affirme un lieu que la page ne montre pas
    est pire qu'une absence de provenance."""
    import faits_vue
    return faits_vue.lieu_plausible(nom)


def lieux_connus():
    """{lieu normalise: libelle}. Lu depuis lieux.txt, sinon deduit des dossiers.

    Le fichier prime : l'heuristique se trompe forcément sur un fonds réel,
    et c'est à l'utilisateur de trancher — pas au code de deviner mieux.
    """
    if time.time() - _LIEUX_CACHE["at"] < 300 and _LIEUX_CACHE["index"]:
        return _LIEUX_CACHE["index"]
    index = {}
    try:
        for l in LIEUX_FICHIER.read_text(encoding='utf-8').splitlines():
            l = l.split('#')[0].strip()
            if l:
                index[_sans_accents(l)] = l
    except OSError:
        pass
    if not index:                       # première fois : on propose une liste
        from collections import Counter
        # Un nom de personne ou d'animal n'est PAS un lieu : « Caline » est un
        # dossier fréquent, mais c'est un chat.
        interdits = {_sans_accents(n) for n in noms_connus()}
        interdits |= {'janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin',
                      'juillet', 'aout', 'septembre', 'octobre', 'novembre',
                      'decembre', 'best', 'divers', 'anni', 'appart'}
        compte = Counter()
        roots = media_roots()          # 1× (cf. _chemin_relatif) : premier lancement seulement
        for k in list(STORE.data):
            parts = _chemin_relatif(k, roots).replace('/', '\\').split('\\')
            for p in parts[:-1]:
                lieu = _lieu_plausible(p)
                if not lieu:
                    continue
                # On indexe le libellé ENTIER et chacun de ses mots : sans ça,
                # « Bremblens » ne trouverait pas le dossier « Appart
                # Bremblens », ni « Indonésie » le dossier « Voyage en
                # Indonésie ». C'est ainsi qu'on parle d'un lieu.
                candidats = {lieu} | {m for m in lieu.split() if len(m) >= 5}
                for c in candidats:
                    if _sans_accents(c) not in interdits:
                        compte[c] += 1
        retenus = [l for l, n in compte.most_common(120) if n >= 8]
        index = {_sans_accents(l): l for l in retenus}
        try:
            LIEUX_FICHIER.write_text(
                "# Lieux reconnus par la recherche (un par ligne).\n"
                "# Déduits des noms de dossiers : corrige, supprime, complète.\n"
                "# Supprimer ce fichier le fait régénérer.\n#\n"
                + "\n".join(sorted(retenus)) + "\n", encoding='utf-8')
        except OSError:
            pass
    _LIEUX_CACHE.update(at=time.time(), index=index)
    return index


def gps_places_connus():
    """{clé_photo: libellé} du géocodage inverse précalculé (gps_places.json).

    Rechargé quand le fichier change (mtime), sinon servi du cache. Rend {} si le
    fichier est absent ou illisible — le renommage retombe alors sur le lieu
    déduit du chemin. Aucun accès réseau, aucun modèle : simple lecture d'un JSON
    produit hors ligne par enrichir_lieux.py."""
    # Mutations en attente (re-clé/oubli différés d'un batch, audit I2) : ne
    # pas les écraser par une relecture du disque avant leur flush.
    if _GPS_PLACES_CACHE.get("dirty"):
        return _GPS_PLACES_CACHE["index"]
    try:
        mtime = GPS_PLACES_FICHIER.stat().st_mtime
    except OSError:
        _GPS_PLACES_CACHE.update(mtime=-1.0, index={})
        return _GPS_PLACES_CACHE["index"]
    if mtime == _GPS_PLACES_CACHE["mtime"] and _GPS_PLACES_CACHE["index"]:
        return _GPS_PLACES_CACHE["index"]
    try:
        data = json.loads(GPS_PLACES_FICHIER.read_text(encoding='utf-8'))
        index = {k: v for k, v in data.items() if isinstance(v, str) and v}
    except (OSError, ValueError, AttributeError):
        index = {}
    _GPS_PLACES_CACHE.update(mtime=mtime, index=index)
    return index


# ── gps_places.json suit les re-clés et les oublis (audit I2) ────────────────
# C'était le 7ᵉ magasin keyé par chemin, IGNORÉ de rekey_everywhere et
# forget_everywhere : activer gps_place puis renommer 2114 fichiers aurait
# orphaniné tous les libellés. Modèle : mutation du cache en mémoire (marqué
# dirty), flush atomique (tmp + os.replace) — immédiat pour un geste isolé,
# différé au batch pour les lots (gps_places_save aux côtés de STORE.save).
# No-op tant que le fichier n'existe pas (gps_place inactif).

_GPS_PLACES_LOCK = threading.Lock()   # sérialise les MUTATIONS (pas la lecture)


def gps_places_rekey(old, new, save=True):
    """Suit un renommage `old` → `new` dans gps_places.json. Renvoie True si
    un libellé a été déplacé.

    COPY-ON-WRITE : les lecteurs (places_list, _serve_geo…) itèrent l'index
    du cache SANS verrou ni copie — muter l'objet partagé en place ferait un
    « dictionary changed size during iteration » en plein lot de renommage.
    On mute donc une COPIE puis on remplace l'objet du cache (atomique)."""
    with _GPS_PLACES_LOCK:
        index = gps_places_connus()
        if old not in index:
            return False
        index = dict(index)
        index[new] = index.pop(old)
        _GPS_PLACES_CACHE["index"] = index
        _GPS_PLACES_CACHE["dirty"] = True
    if save:
        gps_places_save()
    return True


def gps_places_forget(keys, save=True):
    """Retire les libellés des photos disparues. Renvoie le nombre retiré.
    Copy-on-write, comme gps_places_rekey."""
    with _GPS_PLACES_LOCK:
        index = dict(gps_places_connus())
        n = 0
        for k in keys:
            if index.pop(k, None) is not None:
                n += 1
        if n:
            _GPS_PLACES_CACHE["index"] = index
            _GPS_PLACES_CACHE["dirty"] = True
    if n and save:
        gps_places_save()
    return n


def gps_places_save():
    """Flush atomique du cache muté vers gps_places.json. No-op si propre.

    NOTE : réécrit le fichier depuis l'index FILTRÉ de gps_places_connus
    (valeurs str non vides uniquement — le format qu'écrit enrichir_lieux.py
    aujourd'hui). Si enrichir_lieux.py enrichit un jour son format, adapter
    le filtre AVANT, sinon les entrées d'un autre type seraient perdues au
    premier renommage."""
    with _GPS_PLACES_LOCK:
        if not _GPS_PLACES_CACHE.get("dirty"):
            return
        tmp = GPS_PLACES_FICHIER.with_suffix('.json.tmp')
        try:
            tmp.write_text(json.dumps(_GPS_PLACES_CACHE["index"],
                                      ensure_ascii=False, indent=0),
                           encoding='utf-8')
            os.replace(tmp, GPS_PLACES_FICHIER)
            _GPS_PLACES_CACHE["dirty"] = False
            _GPS_PLACES_CACHE["mtime"] = GPS_PLACES_FICHIER.stat().st_mtime
        except OSError as e:
            print(f"  ⚠ Écriture de gps_places.json impossible : {e}")


def _extraire_lieux(requete):
    """Détache de la requête les lieux qu'elle contient."""
    index = lieux_connus()
    reste = ' ' + _sans_accents(requete) + ' '
    original = requete
    trouves = []
    for lieu in sorted(index, key=len, reverse=True):
        if ' ' + lieu + ' ' in reste:
            trouves.append(index[lieu])
            reste = reste.replace(' ' + lieu + ' ', ' ')
            i = _sans_accents(original).find(lieu)
            if i >= 0:
                original = original[:i] + original[i + len(lieu):]
    return trouves, ' '.join(original.split())


def _chemin_relatif(k, roots=None):
    """Chemin PRIVÉ de sa racine média.

    Indispensable : le NAS s'appelle « NAS-Bremblens », donc chercher le lieu
    « Bremblens » dans le chemin complet remonte les 30 682 photos. Le nom du
    serveur n'est pas un lieu photographié.

    `roots` : passer media_roots() DÉJÀ calculé quand on appelle en boucle sur
    tout l'index. Sinon chaque appel relit les fichiers de config ET fait des
    is_dir() (stats SMB sur le NAS) — 64k appels bloquent l'API plusieurs
    minutes (place_list / _cles_du_lieu). Défaut None = comportement d'origine.
    """
    import faits_vue
    return faits_vue.chemin_relatif(
        k, roots if roots is not None else media_roots())


def _cles_du_lieu(lieux):
    """Clés dont le CHEMIN **ou** le lieu GÉOCODÉ désigne tous ces lieux.

    Le chemin seul ne suffit plus depuis l'activation de `gps_place` (14/08) :
    6 595 photos portent un lieu venu du GPS alors que leur dossier ne dit rien
    (« DCIM », « Sauvegarde téléphone »). Chercher « Sion » ne les trouvait pas
    — la matière avait doublé côté lieux et la recherche n'en voyait que la
    moitié. Les deux sources sont donc en OU, lieu par lieu ; le ET porte,
    comme avant, sur l'ENSEMBLE des lieux demandés.

    **La branche CHEMIN délègue à `faits_vue` depuis le 19/08** (chantier
    14a-i). Elle testait une SOUS-CHAÎNE : « Ins » se trouvait dans
    « Cousins&Cousines » et une recherche « Ins » rendait 499 clés dont 488
    fausses. C'était la TROISIÈME règle de lieu du projet, la seule que
    l'utilisateur voie — il n'en reste qu'une. La branche GPS, elle, ne change
    pas : un libellé de gazetteer n'est pas un chemin de dossier.

    Zéro accès NAS : `gps_places_connus` et `lieux_connus` sont des caches
    mémoire adossés au mtime de leur fichier.
    """
    import faits_vue
    besoin = [_sans_accents(l) for l in lieux]
    roots = media_roots()          # 1× : sinon _chemin_relatif relit config + stats NAS par clé
    try:
        gps = gps_places_connus()
    except Exception:                                         # noqa: BLE001
        gps = {}
    try:
        index = lieux_connus()
    except Exception:                                         # noqa: BLE001
        index = {}
    out = set()
    for k in list(STORE.data):
        # `avec_fichier` : 52 photos ne nomment leur lieu que dans leur nom de
        # fichier (« 060_Lavando Trinidad.jpg ») contre 9 qui s'y trompent
        # (« Grupo en la Laguna » — la lagune, pas La Laguna). Mesuré le 19/08.
        du_chemin = {_sans_accents(l) for l in faits_vue.lieux_du_chemin(
            k, index, roots, tous=True, avec_fichier=True)}
        libelle = _sans_accents(gps.get(k) or '') if gps else ''
        if all(b in du_chemin or (libelle and b in libelle) for b in besoin):
            out.add(k)
    return out


# ─── Couche DÉTERMINISTE de la recherche (chantier 14a) ──────────────────────
# Moteur pur et testé dans recherche.py (import léger : re + time + geocode).
# Il ne fait que DÉCOMPOSER la phrase ; le filtrage temporel se fait ici, sur
# l'index déjà en mémoire — zéro GPU, zéro NAS.
import recherche


def _epoch_precis(cle, entree):
    """Date au JOUR près d'une photo, ou None. Une seule implémentation de
    cette règle dans le projet (`meme_jour`), partagée avec « même jour ».

    `faits_vue.date_credible` écarte la date du SCAN : le numériseur l'inscrit
    dans `DateTimeOriginal` ET dans le nom du fichier, et l'index l'a gardée —
    72 photos, de +2 à +32 ans au-delà de leur dossier (mesure du 19/08). Le
    renommage s'en protégeait depuis le 17/08 ; le tri, le filtre par période
    et « même jour » la croyaient encore. **Rien n'est corrigé en base** : la
    lecture applique le garde-fou, `taken` garde sa provenance."""
    import faits_vue
    return meme_jour.epoch_precis(cle, entree or {}, _fname_time,
                                  faits_vue.date_credible)


# Année SÛRE : date précise, sinon année du DOSSIER, **jamais `mtime`**.
# `_best_time` retombe sur `mtime` en dernier recours — légitime pour ranger
# une galerie, mensonger pour répondre « photos de 2015 » : le tagging de 2026
# a réécrit le fichier d'une photo de 1998.
_annee_fiable = recherche.annee_fiable_depuis(_epoch_precis, _path_year_num)


def _sans_date_sure(cle, e):
    """1 si AUCUNE date sûre ne classe cette photo — ni précise, ni année de
    dossier. Elle n'est alors ni récente ni ancienne : elle est INCONNUE.

    La galerie classait ces photos par `_best_time`, donc par leur `mtime`,
    c'est-à-dire par la date de leur dernier tagging (2026) : en ordre
    décroissant elles passaient en tête. Mesuré le 19/08 : **258** photos dans
    **31** dossiers, dont deux ENTIÈREMENT muets (22 photos) — `Photos\\Nikola`
    en compte 43 sur 54. Le client les range désormais en fin de liste dans les
    deux sens, et les compte."""
    try:
        return 0 if _annee_fiable(cle, e or {}) else 1
    except Exception:                                         # noqa: BLE001
        return 1


def semantic_search(requete, limite=80, detail=None):
    """Recherche HYBRIDE : noms humains + lieu + PÉRIODE + sens de l'image.

    SigLIP ne connaît ni « Luna », ni « Sion », ni « décembre 2015 » : ce sont
    des étiquettes posées par un humain, un chemin, une date EXIF — invisibles
    au contenu visuel. On les traite donc à part, par filtrage exact, puis on
    CLASSE le sous-ensemble obtenu par similarité sémantique sur ce qui reste
    de la phrase.

    Quatre dimensions se combinent : QUI (tags posés par un humain), OÙ
    (chemin du fichier **ou** lieu géocodé), QUAND (date de prise de vue), et
    QUOI (sens de l'image). Les trois premières filtrent, la dernière classe.
    « Luna à Sion en décembre 2015 » se lit ainsi de gauche à droite.

    **L'ordre d'extraction est un invariant** : noms, puis lieux, puis dates.
    Quelqu'un peut s'appeler « Mai » ; un nom humain mangé par un mois serait
    une capacité perdue en silence.

    `detail` : dict optionnel rempli en sortie (noms, lieux, période, reste,
    `sans_date`) — l'appelant HTTP en a besoin pour DIRE ce qu'il a compris et
    combien de photos ont été écartées faute de date. Il n'est pas rendu par la
    valeur de retour pour ne pas casser la forme `[(clé, score)]` que partagent
    /api/search, /api/similar et /api/jour.
    """
    sem = _semantic_mod()
    vs = photo_vectors()
    import faits_vue
    especes, esp_inconnues, reste = recherche.extraire_especes(
        requete, faits_vue.espece_canonique)
    # Les jetons EXPLICITES avant les noms nus : `personne:Mai` doit gagner sur
    # le mois, et un jeton préfixé n'est ambigu avec rien. Ce que le résolveur
    # ne reconnaît pas ressort dans `jetons_inconnus` au lieu de retomber dans
    # le sens — c'est là que 1 500 photos sortaient d'un nom inventé.
    # `axe_inconnu_refuse=True` : on est le DERNIER extracteur de jetons —
    # `espece:` est déjà consommé — donc ce qui reste sous la forme
    # `<mot>:<valeur>` n'a plus personne pour le satisfaire.
    jetons, jetons_inconnus, reste = recherche.extraire_jetons(
        reste, AXES_DE_JETON, _resoudre_jeton, axe_inconnu_refuse=True)
    tags_dits = [f"{axe}:{val}" for axe, val in jetons
                 if axe in ('personne', 'animal')]
    lieux_dits = [val for axe, val in jetons if axe == 'lieu']
    noms_inconnus = [f"{axe}:{val}" for axe, val, connu in jetons_inconnus
                     if connu]
    axes_inconnus = [axe for axe, _val, connu in jetons_inconnus if not connu]
    tags, reste = _extraire_noms(reste)
    tags = tags_dits + [t for t in tags if t not in tags_dits]
    lieux, reste = _extraire_lieux(reste)
    lieux = lieux_dits + [l for l in lieux if l not in lieux_dits]
    periode, reste = recherche.extraire_periode(reste)
    if detail is not None:
        detail.update(noms=[t.split(':', 1)[-1] for t in tags], lieux=lieux,
                      periode=periode.libelle if periode else '',
                      especes=especes, especes_inconnues=esp_inconnues,
                      noms_inconnus=noms_inconnus, axes_inconnus=axes_inconnus,
                      reste=reste, sans_date=0, sans_date_tri=0)

    candidats = _cles_portant(tags) if tags else None
    if lieux:
        du_lieu = _cles_du_lieu(lieux)
        candidats = du_lieu if candidats is None else (candidats & du_lieu)
    if esp_inconnues or noms_inconnus or axes_inconnus:
        # `espece:licorne`, `animal:Zzz`, `couleur:rouge` : un filtre qu'on ne
        # sait pas satisfaire ne rend RIEN, et la page le dit. Le laisser
        # passer rendrait tout le fonds, ce que l'utilisateur lirait comme un
        # accord — et c'est ce qui a produit un verdict faux sur une chatte
        # qui a vécu seize ans ici (26/08).
        return []
    if especes:
        de_l_espece = _cles_de_l_espece(especes)
        candidats = (de_l_espece if candidats is None
                     else (candidats & de_l_espece))
    if periode is not None:
        # Sur les candidats déjà réduits quand il y en a — sinon sur tout
        # l'index (43 000 entrées, opérations pures : quelques dizaines de ms).
        source = ([(k, STORE.data.get(k) or {}) for k in candidats]
                  if candidats is not None else list(STORE.data.items()))
        du_temps, sans_date = recherche.filtrer_periode(
            source, periode, _epoch_precis, _annee_fiable)
        candidats = du_temps if candidats is None else (candidats & du_temps)
        if detail is not None:
            detail['sans_date'] = sans_date

    if candidats is not None:
        if not candidats:
            return []
        if not reste:
            # Aucun autre mot : on rend les plus récentes d'abord — avec la
            # MÊME règle de date que le filtre juste au-dessus. `_best_time`
            # était branché ici : sa branche 3 est le `mtime`, celui-là même
            # que `_annee_fiable` refuse (le tagging de 2026 réécrit le
            # fichier d'une photo de 1998). La photo dont la date est
            # certainement fausse s'affichait donc en TÊTE, et sa clé
            # (`… or ''`) mélangeait `float` et `str` : une seule photo sans
            # aucune date faisait tomber la recherche en TypeError.
            # `sorted(candidats)` d'abord : le tri est stable, les ex æquo
            # gardent donc un ordre reproductible d'une requête à l'autre.
            ordre, sans_date_tri = recherche.trier_chronologique(
                ((k, STORE.data.get(k) or {}) for k in sorted(candidats)),
                _epoch_precis, _annee_fiable)
            if detail is not None:
                detail['sans_date_tri'] = sans_date_tri
                # Un plafond SILENCIEUX se lit comme une exhaustivité :
                # `espece:chat` rend 2 386 photos et la page en affichait
                # 1 500 sans le dire — 886 disparues sans un mot. Le filtre
                # déterministe connaît son total AVANT de couper : il le dit.
                detail['total'] = len(ordre)
                detail['tronque'] = max(0, len(ordre) - int(limite))
            return [(k, 1.0) for k in ordre[:limite]]
        q = encoder_requete(sem, reste, detail)
        return vs.search(sem.KIND, q, limite=limite, restreindre=candidats)

    q = encoder_requete(sem, requete, detail)
    return vs.search(sem.KIND, q, limite=limite)


def similar_by_key(cle, limite=80):
    """Photos proches d'une photo donnée — cosinus dans l'espace SigLIP.

    AUCUN encodage : le vecteur de la photo est déjà en base, la requête se
    résume à « décoder un BLOB puis classer » — zéro GPU, zéro accès NAS.
    C'est ce qui rend la navigation « semblables » gratuite : chaque résultat
    peut à son tour servir de requête, de proche en proche.

    Renvoie None si la photo n'a pas (encore) de vecteur : photo fraîchement
    déposée (l'encodeur de fond n'est pas passé) ou écartée (`failed`) — deux
    situations que l'appelant doit distinguer d'un résultat vide.
    """
    sem = _semantic_mod()          # import léger ; source unique de KIND
    vs = photo_vectors()
    b64 = vs.get_b64(sem.KIND, cle)
    if not b64:
        return None
    import numpy as np
    q = np.frombuffer(base64.b64decode(b64), dtype=np.float16).astype(np.float32)
    # limite+1 : la photo elle-même sort en tête (cosinus 1.0), on l'écarte.
    res = vs.search(sem.KIND, q, limite=limite + 1)
    return [(k, s) for k, s in res if k != cle][:limite]


def semantic_loop():
    """Encode les photos en tâche de fond, en cédant la place à l'UI."""
    if not SEMANTIC_ENABLE:
        return
    time.sleep(20)                 # laisse le scan initial démarrer
    try:
        sem = _semantic_mod()
        vs = photo_vectors()
    except Exception as e:                                    # noqa: BLE001
        SEMANTIC_STATE["erreur"] = str(e)[:200]
        print(f"  ℹ Recherche sémantique indisponible : {e}")
        print("     → « 14 - Installer la recherche semantique.bat »")
        return
    print("  🔎 Recherche sémantique : encodage en tâche de fond")
    while True:
        try:
            # L'UI garde la priorité absolue ; pour le reste on ATTEND son
            # tour au lieu de renoncer.
            if ui_recent():
                time.sleep(5)
                continue
            with creneau('semantique', timeout=180) as ok:
                if not ok:
                    continue
                fait = _semantique_un_lot(sem, vs)
            # Le créneau est rendu AVANT de dormir : attendre en le gardant
            # bloquerait les autres travaux pour rien.
            time.sleep(SEMANTIC_PACE if fait else SEMANTIC_IDLE_SLEEP)
        except Exception as e:                                # noqa: BLE001
            SEMANTIC_STATE["erreur"] = str(e)[:200]
            print(f"  ⚠ Encodage sémantique : {e}")
            time.sleep(SEMANTIC_BUSY_SLEEP)


def _semantique_un_lot(sem, vs):
    """UN lot d'encodage, puis on rend la main. Pas de boucle interne : garder
    le créneau au-delà de son lot priverait les autres travaux.

    Les clés qui ne produisent AUCUN vecteur sont mises de côté. Sans cela un
    lot défaillant — fichier absent, image illisible, format non décodé — est
    réessayé à l'identique toutes les 90 s et l'encodage n'avance plus jamais.
    C'est ce qui l'a figé à 1 447 photos sur 30 682.
    """
    deja = {k for k, in STORE.cx.execute(
        "SELECT k FROM vectors WHERE kind=? AND ver=?",
        (sem.KIND, sem.VERSION))}
    # Respecter le drapeau `failed` comme le font tous les autres pipelines :
    # ce sont des fichiers dont l'illisibilité est DÉJÀ constatée (987 sur
    # 30 682 ici). Les réessayer était la cause du blocage à 1 447 photos.
    reste = [k for k, e in list(STORE.data.items())
             if k not in deja and k not in SEMANTIC_SKIP
             and not (isinstance(e, dict) and (e.get('failed') or e.get('video')))]
    SEMANTIC_STATE["pending"] = len(reste)
    SEMANTIC_STATE["ecartees"] = len(SEMANTIC_SKIP)
    if not reste:
        SEMANTIC_STATE["actif"] = False
        return 0
    # AUCUN accès au NAS pour choisir le lot : un exists() sur SMB coûte
    # jusqu'à plusieurs centaines de millisecondes, et en tester 600 fige la
    # tâche pendant des minutes — c'est ce qui la bloquait au démarrage.
    # On prend simplement les clés suivantes ; encoder_images() ignore déjà
    # les images illisibles, et tout ce qui ne rend pas de vecteur est écarté.
    chemins = {}
    for k in reste[:SEMANTIC_BATCH]:
        chemins[str(_resolve_key(k))] = k
    if not chemins:
        return 0
    SEMANTIC_STATE["etape"] = f"encodage de {len(chemins)} photo(s)"
    SEMANTIC_STATE["actif"] = True
    # Audit O6 : le verrou n'est plus tenu sur le lot ENTIER (16 photos =
    # 10–30 s CPU) mais par SOUS-LOT : une recherche — qui ne prend le verrou
    # que le temps d'encoder sa requête texte — s'intercale entre deux
    # sous-lots au lieu d'attendre la fin du lot. Entre deux sous-lots, si
    # l'UI vient de parler, on S'ARRÊTE là : les vecteurs déjà produits sont
    # écrits, le reste du lot repassera au tour suivant. Seules les clés
    # réellement TENTÉES peuvent être écartées (une clé non tentée n'a rien
    # prouvé de son illisibilité).
    tous = list(chemins)
    res, tentes = [], []
    for i in range(0, len(tous), SEMANTIC_SUBBATCH):
        sous = tous[i:i + SEMANTIC_SUBBATCH]
        with SEMANTIC_LOCK:
            res.extend(sem.encoder_images(sous))
            SEMANTIC_STATE["device"] = sem._ETAT.get("device") or ""
        tentes.extend(sous)
        if i + SEMANTIC_SUBBATCH < len(tous) and ui_recent():
            SEMANTIC_STATE["etape"] = (
                f"lot interrompu (UI active) : {len(tentes)}/{len(tous)}")
            break
    import base64
    import numpy as np
    lot = [(chemins[str(p)],
            base64.b64encode(v.astype(np.float16).tobytes()).decode())
           for p, v in res]
    # Sous STORE.lock (audit O4) : put_many_b64 écrit sur la connexion
    # partagée ; croisé avec un _ecrire() d'un autre thread, les vecteurs
    # pouvaient être emportés par son ROLLBACK.
    with STORE.lock:
        vs.put_many_b64(sem.KIND, lot, ver=sem.VERSION)
    SEMANTIC_STATE["done"] += len(res)
    # Une image présente mais qu'aucun vecteur ne suit (illisible, format non
    # décodé, EXIF cassé) est écartée elle aussi : elle bloquerait autant.
    # Uniquement parmi les clés TENTÉES (O6 : un lot interrompu par l'UI ne
    # doit pas écarter des photos jamais passées à l'encodeur).
    obtenus = {chemins[str(p)] for p, _v in res}
    for p in tentes:
        k = chemins[p]
        if k not in obtenus:
            SEMANTIC_SKIP.add(k)
    return len(res)


# ─── Attribution unifiée ─────────────────────────────────────────────────────
# Toutes les corrections du projet étaient binaires (« ✓ Ajouter / ✗ Non »).
# Or l'intention réelle est presque toujours une ATTRIBUTION : quand on refuse,
# on sait souvent ce que c'est. Le refus jetait cette information.
#
# Une seule action remplace tous ces boutons. Un rejet devient simplement une
# attribution à une cible spéciale — d'où l'absence de bouton dédié.
CIBLE_PAS_ANIMAL = "__pas_animal__"    # peluche, statue, reflet, macaque…
CIBLE_INCONNU = "__inconnu__"          # vrai animal, mais pas un des nôtres
CIBLE_PAS_VISAGE = "__pas_visage__"    # decoupe de chat/objet : PAS un visage humain
CIBLE_NON_GROUP = "__non_group__"      # vrai visage, mais pas un groupe nommable (nuque, profil)
CIBLES_SPECIALES = {CIBLE_PAS_ANIMAL, CIBLE_INCONNU, CIBLE_PAS_VISAGE,
                    CIBLE_NON_GROUP}

ANNULATIONS = []                       # pile d'opérations réversibles
ANNUL_MAX = 40
ANNUL_LOCK = threading.Lock()


ANNUL_SEQ = [0]


def _empiler_annulation(libelle, defaire):
    with ANNUL_LOCK:
        # Compteur, PAS l'horloge : trois attributions dans la même
        # milliseconde recevaient le même jeton, et l'annulation défaisait
        # alors une autre opération que celle demandée.
        ANNUL_SEQ[0] += 1
        jeton = f"u{ANNUL_SEQ[0]}"
        ANNULATIONS.append({"jeton": jeton, "libelle": libelle, "defaire": defaire,
                            "at": time.time()})
        del ANNULATIONS[:-ANNUL_MAX]
    return jeton


def annuler(jeton=None):
    """Défait la dernière opération, ou celle désignée par son jeton."""
    with ANNUL_LOCK:
        if not ANNULATIONS:
            return None
        if jeton is None:
            op = ANNULATIONS.pop()
        else:
            trouve = [i for i, o in enumerate(ANNULATIONS) if o["jeton"] == jeton]
            if not trouve:
                return None
            op = ANNULATIONS.pop(trouve[0])
    try:
        op["defaire"]()
        return op["libelle"]
    except Exception as e:                                    # noqa: BLE001
        print(f"  ⚠ Annulation impossible : {e}")
        return None


_NOMS_COMPTE_CACHE = {"at": 0.0, "compte": None}
_NOMS_COMPTE_LOCK = threading.Lock()

# 60 s, comme `_ASSOC_CACHE` : ce qu'on perd est qu'un nom fraîchement posé
# compte une photo de retard pendant au plus une minute, sur un CHIFFRE
# d'affichage. La présence d'un nom dans la liste, elle, n'est jamais
# retardée — c'est l'absence d'un nom qui le fait recréer en « Nouveau ».
NOMS_COMPTE_TTL_S = 60


def _compte_des_noms():
    """{(genre, nom minusculé): nb de photos} — reconstruit au plus toutes
    les `NOMS_COMPTE_TTL_S` secondes.

    POURQUOI CE CACHE EXISTE (24/08)

    `/api/names` part au chargement de CHAQUE page, pour l'autocomplétion.
    `mesure_recherche_nommee` l'a chiffré le 23/08 : **359–364 ms**, presque
    le double du filtre nommé O7 qu'on croyait être le sujet. La liste des
    noms ne coûte rien — les deux magasins de fiches sont petits ; c'est CE
    comptage qui coûte : tout l'index (43 000 fiches) et `parse_tag_nomme`
    sur chacun de leurs mots-clés, refait à chaque appel.

    Compté sur le nom NORMALISÉ : un « animal:luna » d'index appartient à la
    fiche « Luna » — le compter à part afficherait « 0 photo » sous un nom qui
    en porte, et c'est ce zéro qui rendait le défaut invisible (I7).
    """
    from collections import Counter
    with _NOMS_COMPTE_LOCK:
        c = _NOMS_COMPTE_CACHE
        if (c["compte"] is not None
                and time.time() - c["at"] < NOMS_COMPTE_TTL_S):
            return c["compte"]
        compte = Counter()
        for k, e in list(STORE.data.items()):
            for kw in ((e.get('kw_fr') or []) + (e.get('kw_en') or [])):
                pn = parse_tag_nomme(kw)
                if pn:
                    compte[(pn[0], pn[1].lower())] += 1
        c["compte"], c["at"] = compte, time.time()
        return compte


def noms_pour_saisie(genre=None, prefixe=""):
    """Source d'autocomplétion : personnes ET animaux, avec leur volume.

    Les deux magasins sont séparés ; les chercher ensemble évite de créer un
    « Luna » animal alors qu'une personne du même nom existe déjà.

    Seul le COMPTAGE est mis en cache (`_compte_des_noms`). La LISTE, non :
    un nom créé à l'instant doit paraître tout de suite, sinon on le recrée
    en « Nouveau » au geste suivant.
    """
    p = _sans_accents(prefixe)
    out = []
    compte = _compte_des_noms()
    for store, genre_i in ((PEOPLE_STORE, 'personne'), (PETS_STORE, 'animal')):
        if genre and genre_i != genre:
            continue
        for e in store.data.values():
            if not isinstance(e, dict):
                continue
            nom = (e.get('name') or '').strip()
            if not nom or (p and not _sans_accents(nom).startswith(p)):
                continue
            out.append({"nom": nom, "genre": genre_i,
                        "espece": e.get('species') or '',
                        "n": compte.get((genre_i, nom.lower()), 0)})
    out.sort(key=lambda x: -x["n"])
    return out


def attribuer_animaux(membres, cible):
    """Attribue un sous-ensemble de détections à un nom, ou l'écarte.

    `membres` : [(clé, index)]. Toujours un SOUS-ENSEMBLE possible — c'est ce
    qui permet de traiter un groupe mixte sans fonction « scinder ».
    """
    membres = [(str(k), int(i)) for k, i in membres if str(k)]
    if not membres:
        return {"ok": False, "n": 0}

    if isinstance(cible, str) and cible in CIBLES_SPECIALES:
        # Trois rejets distincts, comme côté visages (harmonisation) :
        #   pas un animal (suspect) · animal inconnu (inconnu) ·
        #   « Rejeter le groupe » = vrais animaux mais cluster non nommable
        #   (nuques, profils flous) → non_group, honoré par _nommable/_gather_cats.
        if cible == CIBLE_NON_GROUP:
            champ, libelle = 'non_group', "marquée(s) non regroupable(s)"
        elif cible == CIBLE_PAS_ANIMAL:
            champ, libelle = 'suspect', "écartée(s) (pas un animal)"
        else:
            champ, libelle = 'inconnu', "marquée(s) inconnue(s)"
        touchees = []
        for k, i in membres:
            e = ANIMAL_STORE.data.get(k)
            animaux = (e.get('animals') if isinstance(e, dict) else None) or []
            if i < len(animaux) and not animaux[i].get(champ):
                animaux[i][champ] = True
                animaux[i]['par_humain'] = True   # certitude humaine, pas IA
                touchees.append((k, i))
        ANIMAL_STORE.save()

        def defaire():
            for k, i in touchees:
                e = ANIMAL_STORE.data.get(k)
                animaux = (e.get('animals') if isinstance(e, dict) else None) or []
                if i < len(animaux):
                    animaux[i].pop(champ, None)
                    animaux[i].pop('par_humain', None)
            ANIMAL_STORE.save()
            _invalider_groupes_animaux()

        jeton = _empiler_annulation(f"{len(touchees)} détection(s) {libelle}", defaire)
        _invalider_groupes_animaux()
        return {"ok": True, "n": len(touchees), "jeton": jeton,
                "libelle": f"{len(touchees)} {libelle}"}

    # Plusieurs noms possibles pour les MÊMES vignettes : c'est le cas de deux
    # animaux sur une même photo, où YOLO produit des cadres qui se recouvrent
    # (mesuré : 106 paires au-dessus de 25 % de recouvrement sur ce corpus).
    # La découpe montre alors les deux, et une seule attribution serait fausse.
    noms = cible if isinstance(cible, list) else [cible]
    noms = [str(n).strip()[:60] for n in noms if str(n).strip()]
    if not noms:
        return {"ok": False, "n": 0}
    resultats = [_nommer_membres_animaux(membres, n) for n in noms]
    jetons = [r["jeton"] for r in resultats if r.get("jeton")]

    def defaire_tout():
        for j in reversed(jetons):
            annuler(j)

    if len(resultats) == 1:
        return resultats[0]
    jeton = _empiler_annulation(
        f"{len(membres)} vignette(s) → {', '.join(noms)}", defaire_tout)
    return {"ok": True, "n": sum(r.get("n", 0) for r in resultats),
            "jeton": jeton, "noms": noms,
            "libelle": f"{len(membres)} vignette(s) → {' + '.join(noms)}"}


def _invalider_groupes_animaux():
    with PET_CLUSTER_LOCK:
        PET_CLUSTER_CACHE["at"] = 0.0


def _nommer_membres_animaux(membres, nom):
    """Cœur du nommage, sur un sous-ensemble arbitraire de détections."""
    tag = f"animal:{nom}"
    refs, especes = [], {}
    reactives = []
    marques = []          # détections où CE nommage a posé `par_humain`
    for (k, i) in membres:
        ae = ANIMAL_STORE.data.get(k)
        animaux = (ae.get('animals') if isinstance(ae, dict) else None) or []
        if i < len(animaux):
            a = animaux[i]
            sp = a.get('species')
            if sp:
                especes[sp] = especes.get(sp, 0) + 1
            if a.get('emb') and len(refs) < 40:
                refs.append(a['emb'])
            # Nommer, c'est affirmer que c'est bien cet animal : un « suspect »
            # posé par la vérification SigLIP est donc levé, et la détection
            # marquée comme jugée par un humain (plus jamais réévaluée).
            if a.get('suspect') or a.get('inconnu'):
                reactives.append((k, i, a.pop('suspect', None),
                                  a.pop('inconnu', None)))
            # `par_humain` est désormais LU par build_cat_suggestions (garde-fou
            # « une décision humaine n'est jamais re-questionnée »). Il doit donc
            # être annulable comme le reste : sans ça, accepter puis ANNULER
            # retirait bien le tag mais faisait disparaître la proposition de la
            # file POUR TOUJOURS (fuite inoffensive tant que personne ne le
            # lisait — devenue perte de donnée visible avec la file animaux).
            if not a.get('par_humain'):
                marques.append((k, i))
            a['par_humain'] = True
    espece = max(especes, key=especes.get) if especes else 'cat'

    pk = nom.lower()
    existait = pk in PETS_STORE.data
    avant = dict(PETS_STORE.data.get(pk) or {})
    pe = PETS_STORE.data.get(pk) or {"name": nom, "species": espece,
                                     "refs": [], "at": time.time()}
    pe["name"] = nom
    pe.setdefault("species", espece)
    # Les NOUVELLES références passent en tête : avec l'ancien ordre,
    # une fiche ayant atteint 80 références n'en acceptait plus jamais,
    # donc nommer à la main n'améliorait plus rien. Les plus anciennes
    # sortent à la place — la signature suit l'animal qui vieillit.
    pe["refs"] = (refs + (pe.get("refs") or []))[:80]
    pe["faces"] = _merge_assigned(pe.get("faces"), membres)
    PETS_STORE.set(pk, pe)

    ajoutees = []
    for k in dict.fromkeys(k for (k, _i) in membres):
        se = STORE.data.get(k)
        if se is not None and not _kw_has(se, tag):
            if _index_add_person(k, tag):
                _enqueue_person_write(k, tag, 'add')
                ajoutees.append(k)
    STORE.save()

    ANIMAL_STORE.save()

    def defaire():
        for k, i, sus, inc in reactives:
            ae = ANIMAL_STORE.data.get(k)
            animaux = (ae.get('animals') if isinstance(ae, dict) else None) or []
            if i < len(animaux):
                if sus:
                    animaux[i]['suspect'] = sus
                if inc:
                    animaux[i]['inconnu'] = inc
        for k, i in marques:          # ne retire QUE ce que ce nommage a posé
            ae = ANIMAL_STORE.data.get(k)
            animaux = (ae.get('animals') if isinstance(ae, dict) else None) or []
            if i < len(animaux):
                animaux[i].pop('par_humain', None)
        ANIMAL_STORE.save()
        for k in ajoutees:
            _index_remove_person(k, tag)
            _enqueue_person_write(k, tag, 'del')
        if existait:
            PETS_STORE.set(pk, avant)
        else:
            PETS_STORE.data.pop(pk, None)
            PETS_STORE.save()
        STORE.save()
        _invalider_groupes_animaux()

    jeton = _empiler_annulation(
        f"{len(ajoutees)} photo(s) attribuée(s) à {nom}", defaire)
    _invalider_groupes_animaux()
    return {"ok": True, "n": len(ajoutees), "jeton": jeton, "espece": espece,
            "libelle": f"{len(ajoutees)} photo(s) → {nom}"}


def attribuer_visage(cle, i, cible, personne_proposee=""):
    """Suggestion de visage : accepter, corriger vers un AUTRE nom, ou écarter.

    C'est le cas que le binaire perdait : on refuse « Florine » alors qu'on
    sait qu'il s'agit de « Flo », et l'information est jetée.
    """
    cle = str(cle or "")
    if not cle:
        return {"ok": False}

    if cible in CIBLES_SPECIALES:
        pk = (personne_proposee or "").lower()
        pe = PEOPLE_STORE.data.get(pk)
        if isinstance(pe, dict):
            excl = list(pe.get('exclude') or [])
            if cle not in excl:
                excl.append(cle)
                pe['exclude'] = excl
                PEOPLE_STORE.set(pk, pe)
        # Si la photo PORTE déjà le tag de la personne proposée (carte « faux
        # positif ? » : on écarte un non-visage déjà tagué), on retire ce tag
        # erroné — sinon la même fausse alerte reviendrait à chaque passe.
        se_sp = STORE.data.get(cle)
        tag_sp = f"personne:{personne_proposee}"
        retire_sp = False
        if se_sp is not None and personne_proposee and _kw_has(se_sp, tag_sp):
            _index_remove_person(cle, tag_sp)
            _enqueue_person_write(cle, tag_sp, 'del')
            STORE.save()
            retire_sp = True
        _suggest_remove(lambda s: s.get('type') == 'remove'
                        and s.get('person') == personne_proposee
                        and s.get('key') == cle)

        def defaire_excl():
            pe2 = PEOPLE_STORE.data.get(pk)
            if isinstance(pe2, dict):
                pe2['exclude'] = [x for x in (pe2.get('exclude') or []) if x != cle]
                PEOPLE_STORE.set(pk, pe2)
            if retire_sp:
                _index_add_person(cle, tag_sp)
                _enqueue_person_write(cle, tag_sp, 'add')
                STORE.save()
        jeton = _empiler_annulation(f"visage écarté de {personne_proposee}",
                                    defaire_excl)
        return {"ok": True, "jeton": jeton,
                "libelle": f"écarté de {personne_proposee}"}

    nom = (cible or "").strip()[:60]
    if not nom:
        return {"ok": False}
    tag = f"personne:{nom}"
    se = STORE.data.get(cle)
    if se is None:
        return {"ok": True, "n": 0, "libelle": "déjà attribué"}
    if _kw_has(se, tag):
        # Déjà tagué avec CE nom. On délègue quand même à _nommer_membres_visages :
        # c'est idempotent sur le tag (il ne re-tague pas) mais il CRÉE/complète la
        # FICHE et inscrit le visage comme référence + assigné. Ça répare le cas des
        # anciens tags posés SANS fiche par le curateur unitaire (le bug corrigé ici)
        # et, si l'utilisateur re-confirme le même nom depuis « faux positif ? »,
        # enregistre la confirmation (plus jamais signalé).
        confirme = bool(personne_proposee) and nom.lower() == personne_proposee.lower()
        # CORRECTION vers un nom que la photo PORTE DÉJÀ (ex. photo taguée à la fois
        # « Mathilde » — le bon — ET « Flo » — le faux positif). Il faut RETIRER le
        # tag erroné (personne_proposee) et l'exclure, EXACTEMENT comme la branche
        # « pas encore tagué » plus bas. Sans ça, ce branchement ré-affirmait juste
        # le bon nom sans retirer le mauvais → le faux positif revenait à chaque
        # passe. Bug observé : « je corrige vers le bon nom et ça revient sans fin. »
        corrige = bool(personne_proposee) and nom.lower() != personne_proposee.lower()
        pk = (personne_proposee or "").lower()
        tag_ancien = f"personne:{personne_proposee}"
        retire_ancien = False
        if corrige:
            pe = PEOPLE_STORE.data.get(pk)
            if isinstance(pe, dict):
                excl = list(pe.get('exclude') or [])
                if cle not in excl:
                    excl.append(cle)
                    pe['exclude'] = excl
                    PEOPLE_STORE.set(pk, pe)
            if _kw_has(se, tag_ancien):
                _index_remove_person(cle, tag_ancien)
                _enqueue_person_write(cle, tag_ancien, 'del')
                retire_ancien = True
            _suggest_remove(lambda s: s.get('type') == 'remove'
                            and s.get('person') == personne_proposee
                            and s.get('key') == cle)
            STORE.save()
        res0 = _nommer_membres_visages([(cle, int(i or 0))], nom)
        if confirme:
            _person_add_set(nom, 'confirmed', cle)
            _suggest_remove(lambda s: s.get('type') == 'remove'
                            and s.get('person') == nom and s.get('key') == cle)
        if corrige:
            def defaire0():
                if res0.get('jeton'):
                    annuler(res0['jeton'])
                if retire_ancien:
                    _index_add_person(cle, tag_ancien)
                    _enqueue_person_write(cle, tag_ancien, 'add')
                    STORE.save()
                pe2 = PEOPLE_STORE.data.get(pk)
                if isinstance(pe2, dict):
                    pe2['exclude'] = [x for x in (pe2.get('exclude') or []) if x != cle]
                    PEOPLE_STORE.set(pk, pe2)
            jeton0 = _empiler_annulation(
                f"{personne_proposee} retiré, {nom} conservé", defaire0)
            return {"ok": True, "n": res0.get("n", 0), "jeton": jeton0, "corrige": True,
                    "libelle": f"→ {nom} (corrigé depuis {personne_proposee})"}
        return {"ok": True, "n": res0.get("n", 0), "jeton": res0.get("jeton"),
                "libelle": (f"confirmé : {nom}" if confirme else f"→ {nom}")}
    # Si l'utilisateur corrige vers un AUTRE nom, la proposition initiale
    # devient une exclusion : sinon elle reviendra indéfiniment.
    corrige = personne_proposee and nom.lower() != personne_proposee.lower()
    pk = (personne_proposee or "").lower()
    tag_ancien = f"personne:{personne_proposee}"
    retire_ancien = False
    if corrige:
        pe = PEOPLE_STORE.data.get(pk)
        if isinstance(pe, dict):
            excl = list(pe.get('exclude') or [])
            if cle not in excl:
                excl.append(cle)
                pe['exclude'] = excl
                PEOPLE_STORE.set(pk, pe)
        # Corriger depuis une carte « faux positif ? » : la photo PORTE le tag
        # erroné. On le retire (sinon la même fausse alerte revient sans fin).
        if _kw_has(se, tag_ancien):
            _index_remove_person(cle, tag_ancien)
            _enqueue_person_write(cle, tag_ancien, 'del')
            retire_ancien = True
        _suggest_remove(lambda s: s.get('type') == 'remove'
                        and s.get('person') == personne_proposee
                        and s.get('key') == cle)
        STORE.save()

    # Nommage réel : créer/enrichir la FICHE (PEOPLE_STORE) avec ce visage comme
    # référence et l'inscrire dans `faces` (donc « assigné » : il ne revient plus
    # dans « À vérifier » ni « À nommer »), + écrire le tag XMP. C'est ce que faisait
    # déjà le chemin des GROUPES (_nommer_membres_visages) mais PAS le curateur
    # unitaire : il ne posait que le tag, d'où un « nouveau » nom jamais sauvegardé
    # comme personne/groupe et une proposition qui revenait au redémarrage.
    res = _nommer_membres_visages([(cle, int(i or 0))], nom)
    jeton_nom = res.get('jeton')

    def defaire():
        if jeton_nom:
            annuler(jeton_nom)              # défait fiche + référence + tag
        if retire_ancien:
            _index_add_person(cle, tag_ancien)
            _enqueue_person_write(cle, tag_ancien, 'add')
            STORE.save()
        if corrige:
            pe2 = PEOPLE_STORE.data.get(pk)
            if isinstance(pe2, dict):
                pe2['exclude'] = [x for x in (pe2.get('exclude') or []) if x != cle]
                PEOPLE_STORE.set(pk, pe2)

    jeton = _empiler_annulation(f"photo attribuée à {nom}", defaire)
    return {"ok": True, "n": res.get("n", 1), "jeton": jeton, "corrige": bool(corrige),
            "libelle": f"→ {nom}" + (f" (corrigé depuis {personne_proposee})"
                                     if corrige else "")}


def _invalider_groupes_visages():
    """Vide le cache des groupes de visages. Au prochain accès il est reconstruit
    par _gather_faces, qui honore les marquages pas_visage / non_group."""
    with CLUSTER_LOCK:
        CLUSTER_CACHE["clusters"] = []
        CLUSTER_CACHE["byid"] = {}
        CLUSTER_CACHE["at"] = 0.0
    # La vue « (Inconnus) » dépend des mêmes marquages : la forcer à se reconstruire.
    with INCONNU_LOCK:
        INCONNU_CACHE["clusters"] = []
        INCONNU_CACHE["byid"] = {}
        INCONNU_CACHE["at"] = 0.0


def _marquer_visages(membres, champ):
    """Pose un marquage humain (pas_visage | non_group) sur un sous-ensemble de
    visages, de façon réversible. Miroir du chemin « cible spéciale » de
    attribuer_animaux : la certitude humaine n'est jamais réévaluée."""
    touches = []
    for k, i in membres:
        e = FACE_STORE.data.get(k)
        faces = (e.get('faces') if isinstance(e, dict) else None) or []
        if i < len(faces) and not faces[i].get(champ):
            faces[i][champ] = True
            faces[i]['par_humain'] = True     # jugement humain, jamais réévalué
            touches.append((k, i))
    FACE_STORE.save()

    def defaire():
        for k, i in touches:
            e = FACE_STORE.data.get(k)
            faces = (e.get('faces') if isinstance(e, dict) else None) or []
            if i < len(faces):
                faces[i].pop(champ, None)
                faces[i].pop('par_humain', None)
        FACE_STORE.save()
        _invalider_groupes_visages()

    libelle = ("écartée(s) (pas un visage)" if champ == 'pas_visage'
               else "archivée(s) comme inconnue(s)" if champ == 'inconnu'
               else "marquée(s) non regroupable(s)")
    jeton = _empiler_annulation(f"{len(touches)} vignette(s) {libelle}", defaire)
    _invalider_groupes_visages()
    return {"ok": True, "n": len(touches), "jeton": jeton,
            "libelle": f"{len(touches)} {libelle}"}


def _nommer_membres_visages(membres, nom):
    """Nomme un sous-ensemble de visages : tag personne:Nom + fiche + refs.
    Réversible. Miroir de _nommer_membres_animaux (harmonisation des pipelines)."""
    tag = f"personne:{nom}"
    refs = []
    reactives = []                 # visages archivés « inconnu » levés par ce nommage
    for (k, i) in membres:
        fe = FACE_STORE.data.get(k)
        faces = (fe.get('faces') if isinstance(fe, dict) else None) or []
        if i < len(faces):
            emb = faces[i].get('emb')
            if emb and len(refs) < 40:
                refs.append(emb)
            # Nommer un visage archivé sous « (Inconnus) », c'est lui donner une
            # identité : on lève l'archive (miroir de _nommer_membres_animaux qui
            # relève 'inconnu'). Réversible : restauré dans defaire().
            if faces[i].get('inconnu'):
                faces[i].pop('inconnu', None)
                reactives.append((k, i))
    if reactives:
        FACE_STORE.save()

    pk = nom.lower()
    existait = pk in PEOPLE_STORE.data
    avant = dict(PEOPLE_STORE.data.get(pk) or {})
    pe = PEOPLE_STORE.data.get(pk) or {"name": nom, "refs": [], "at": time.time()}
    pe["name"] = nom
    # Nouvelles refs en tête (une fiche à 80 refs n'en acceptait plus) :
    # la signature suit la personne qui vieillit.
    pe["refs"] = (refs + (pe.get("refs") or []))[:80]
    pe["faces"] = _merge_assigned(pe.get("faces"), membres)
    # Une attribution POSITIVE lève une éventuelle exclusion humaine antérieure sur
    # ces mêmes photos : `exclude` (« pas cette personne ») et l'assignation sont
    # mutuellement exclusifs. Sans ça, l'auto-guérison du curateur — qui honore
    # `exclude` — retirerait aussitôt le tag qu'on vient de poser (cas « je change
    # d'avis »). Réversible : `avant` (copie de la fiche) est restauré par defaire().
    mkeys = set(k for (k, _i) in membres)
    excl0 = pe.get("exclude") or []
    if any(x in mkeys for x in excl0):
        pe["exclude"] = [x for x in excl0 if x not in mkeys]
    PEOPLE_STORE.set(pk, pe)

    ajoutees = []
    for k in dict.fromkeys(k for (k, _i) in membres):
        se = STORE.data.get(k)
        if se is not None and not _kw_has(se, tag):
            if _index_add_person(k, tag):
                _enqueue_person_write(k, tag, 'add')
                ajoutees.append(k)
    STORE.save()

    def defaire():
        for k in ajoutees:
            _index_remove_person(k, tag)
            _enqueue_person_write(k, tag, 'del')
        for k, i in reactives:                     # ré-archive ce qui était inconnu
            fe = FACE_STORE.data.get(k)
            faces = (fe.get('faces') if isinstance(fe, dict) else None) or []
            if i < len(faces):
                faces[i]['inconnu'] = True
        if reactives:
            FACE_STORE.save()
        if existait:
            PEOPLE_STORE.set(pk, avant)
        else:
            PEOPLE_STORE.data.pop(pk, None)
            PEOPLE_STORE.save()
        STORE.save()
        _invalider_groupes_visages()

    jeton = _empiler_annulation(
        f"{len(ajoutees)} photo(s) attribuée(s) à {nom}", defaire)
    _invalider_groupes_visages()
    return {"ok": True, "n": len(ajoutees), "jeton": jeton,
            "libelle": f"{len(ajoutees)} photo(s) → {nom}"}


def attribuer_visages(membres, cible):
    """Attribue un SOUS-ENSEMBLE de visages à un nom, ou l'écarte.

    `membres` : [(clé, index)]. Miroir de attribuer_animaux : sous-ensemble,
    noms multiples, cibles spéciales. C'est ce qui permet de traiter un groupe
    mixte (nuques + découpes de chat) sans fonction « scinder » — et de rejeter
    un groupe entier (tous membres → non_group) ou une vignette (pas_visage).
    """
    membres = [(str(k), int(i)) for k, i in membres if str(k)]
    if not membres:
        return {"ok": False, "n": 0}

    if isinstance(cible, str) and cible in CIBLES_SPECIALES:
        # __inconnu__ (archive « (Inconnus) ») : vrai visage humain mais personne
        # non reconnue — on l'archive pour le re-tagger plus tard, sans ecrire de
        # faux nom dans les XMP. Miroir du champ 'inconnu' cote animaux.
        if cible == CIBLE_PAS_VISAGE:
            champ = 'pas_visage'
        elif cible == CIBLE_INCONNU:
            champ = 'inconnu'
        else:
            champ = 'non_group'
        return _marquer_visages(membres, champ)

    noms = cible if isinstance(cible, list) else [cible]
    noms = [str(n).strip()[:60] for n in noms if str(n).strip()]
    if not noms:
        return {"ok": False, "n": 0}
    resultats = [_nommer_membres_visages(membres, n) for n in noms]
    if len(resultats) == 1:
        return resultats[0]
    jetons = [r["jeton"] for r in resultats if r.get("jeton")]

    def defaire_tout():
        for j in reversed(jetons):
            annuler(j)

    total = sum(r["n"] for r in resultats)
    jeton = _empiler_annulation(f"{total} attribution(s) sur {len(noms)} noms",
                                defaire_tout)
    return {"ok": True, "n": total, "jeton": jeton,
            "libelle": " ; ".join(r["libelle"] for r in resultats)}


# État observable de la boucle de scan/backup (audit O5) : « dernier scan à
# HH:MM » dans /reglages — un crash silencieux devient visible.
MAINT_LOOP_STATE = {"dernier_scan": 0.0, "derniere_erreur": "", "erreur_at": 0.0,
                    # Réconciliation du dernier cycle de scan (comptes_index) :
                    # debut/fin/ajouts/retraits/inexplique. Vide tant qu'aucun
                    # cycle n'a tourné.
                    "dernier_cycle": {}}
# Vérification de la sauvegarde (audit A, « assurance-vie ») : résultat de la
# dernière restauration à blanc du snapshot NAS. Voir backup_verify().
BACKUP_VERIFY_STATE = {"at": 0.0, "ok": None, "integrity": "", "detail": "",
                       "confirmes": None, "exclusions": None,
                       "jugements_exportes": 0.0}


def maintenance_loop():
    """ExifTool + scan initial, puis re-scan toutes les 5 minutes."""
    global EXIFTOOL
    EXIFTOOL = ensure_exiftool()
    # purge des entrées de dossiers cachés (.thumbs, @eaDir…) déjà indexées.
    # `forget_everywhere` et NON `STORE.remove_many` : retirer l'entrée d'index
    # sans la cascade laissait les détections de visages derrière — 91 clés le
    # 21/08, toutes dans `.corbeille-rangement`, invisibles ensuite à tout le
    # monde (`_sync_dir` ne voit que ce qui est ENCORE dans l'index). Le motif
    # reste déclaré au registre : c'est forget_everywhere qui le porte.
    bad = [k for k in list(STORE.data) if _is_hidden_path(_resolve_key(k))]
    if bad:
        n = forget_everywhere(bad, motif='demarrage:dossiers_caches')
        print(f"  🧹 {n} entrée(s) de dossiers cachés retirée(s) de l'index "
              "(avec leurs détections)")
    # Purge unique des clés fantômes (doublons malformés type « ARZOPA » qui ne
    # résolvent pas mais dont la vraie photo existe sous une clé correcte). Sans
    # risque (aucun nom humain), et peu coûteux (ne stat que les collisions).
    try:
        fant = purge_cles_fantomes()
        if fant:
            ex = ', '.join(k[:40] for k in fant[:3])
            print(f"  🧹 {len(fant)} clé(s) fantôme(s) purgée(s) de FACE/ANIMAL "
                  f"(doublons malformés, ex. {ex})")
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠ purge clés fantômes ignorée : {e}")
    # Détections dont la clé a quitté l'index : le troisième orphelin (21/08).
    # Base contre base, puis un stat par clé CANDIDATE seulement — le coût est
    # borné par la taille de l'anomalie, pas par celle du corpus.
    try:
        purgees, protegees, attente = purge_detections_hors_index()
        if purgees or protegees or attente:
            print(f"  🧹 hors index : {len(purgees)} détection(s) purgée(s), "
                  f"{len(protegees)} protégée(s) (décision humaine), "
                  f"{len(attente)} en attente de re-tagging")
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠ purge des détections hors index ignorée : {e}")
    first = True
    cycle = 0
    while True:
        # try/except (audit O5) : la première exception non prévue tuait la
        # boucle SILENCIEUSEMENT — plus de scan NI de backup jusqu'au
        # redémarrage. On journalise, on affiche dans /reglages, on continue.
        try:
            # scan approfondi ~1x/heure : détecte aussi les fichiers modifiés
            deep = (cycle % 12 == 6)
            # Réconciliation du cycle (chantier 10a) : on encadre le scan par la
            # TAILLE de l'index et on compare à ce que les mutations déclarées
            # prédisent. Le `finally` est essentiel : un cycle laissé OUVERT
            # ferait porter au suivant les mutations de deux cycles — un
            # instrument qui ment est pire que pas d'instrument.
            # `len()` et le snapshot des compteurs doivent etre pris ENSEMBLE :
            # sinon un ajout concurrent glisse entre les deux et fabrique un
            # ecart de +1 la ou rien n'a fui. Toutes les mutations de l'index
            # passent par le verrou du store, donc le prendre ici les exclut.
            # Ordre de verrous : STORE.lock -> registre (jamais l'inverse).
            with STORE.lock:
                REGISTRE.debut_cycle(len(STORE.data))
            try:
                scan_uploads(first, deep)
                retro_write_metadata()
            finally:
                with STORE.lock:
                    _res = REGISTRE.fin_cycle(len(STORE.data))
                MAINT_LOOP_STATE["dernier_cycle"] = _res or {}
                _ligne = REGISTRE.ligne_cycle(_res)
                if _ligne:
                    print(f"  📒 {_ligne}")
                # Le carnet part sur disque À CHAQUE cycle : un redémarrage
                # perdrait au pire le cycle en cours, jamais l'historique.
                sauver_comptes()
            first = False
            MAINT_LOOP_STATE["dernier_scan"] = time.time()
        except Exception as e:                                # noqa: BLE001
            MAINT_LOOP_STATE["derniere_erreur"] = str(e)[:200]
            MAINT_LOOP_STATE["erreur_at"] = time.time()
            print(f"  ⚠ Boucle de maintenance : {e} — la boucle continue")
        # Sauvegarde de la base locale vers le NAS (~1x/heure), HORS du try du
        # scan : un scan qui échoue durablement (NAS listable mais dossier en
        # panne…) ne doit pas priver le backup — c'est lui qui protège les
        # noms. backup_db() attrape déjà toutes ses exceptions. Snapshot
        # cohérent même pendant l'écriture, renommé atomiquement à l'arrivée :
        # le travail humain reste sur un volume sauvegardé, sans SQLite sur SMB.
        # L'échéance se lit sur le FICHIER, pas sur un compteur de tours :
        # voir _backup_du() — le compteur ne survivait pas au redémarrage.
        cycle += 1
        if _backup_du():
            backup_db()
        time.sleep(SCAN_INTERVAL)


class _MaintSv:
    """Pont serveur → maintenance.run_cycle. Injecte l'index EN MÉMOIRE du
    serveur (écrivain unique, donc pas de cache périmé) et rekey_everywhere pour
    les étapes mutantes ; les étapes lecture seule (recensement, plan) partent en
    sous-processus. is_busy() reflète l'activité UI + la charge machine, pour
    céder la priorité. Voir maintenance.py."""

    def __init__(self):
        import maintenance as _m
        self.dry = False
        self.autonomy = dict(_m.AUTONOMY)
        self.intervals = dict(_m.INTERVALS)
        docs = SCRIPT_DIR / 'docs'
        corb = None
        try:
            corb = json.loads((docs / 'plan_rangement.json')
                              .read_text(encoding='utf-8')).get('corbeille')
        except Exception:
            pass
        self.paths = {'corbeille': corb,
                      'plan': str(docs / 'plan_rangement.json'),
                      'recensement': str(docs / 'recensement.json'),
                      'state': str(docs / 'maintenance_state.json'),
                      'report': str(docs / 'maintenance_report.json'),
                      'racine': str(SCRIPT_DIR)}

    def rekey(self, old, new):
        return rekey_everywhere(old, new)

    def tags_get(self, k):
        return STORE.data.get(k)

    def tags_set(self, k, e):
        STORE.set(k, e, save=False)

    def tags_save(self):
        STORE.save()

    def is_busy(self):
        return system_busy() or ui_recent()

    def log(self, m):
        print(f"  🧹 maintenance : {m}")

    def run_readonly(self, args):
        import subprocess
        return subprocess.run([sys.executable] + list(args),
                              cwd=str(SCRIPT_DIR)).returncode


def maintenance_orchestrator():
    """Thread de fond : évalue le cycle de maintenance à intervalle régulier.
    Chaque étape décide elle-même si elle est due (voir maintenance.py). Ne
    démarre rien tant que MAINTENANCE_AUTO est False."""
    if not MAINTENANCE_AUTO:
        return
    import maintenance as _m
    time.sleep(120)                      # laisse le scan initial se poser
    sv = _MaintSv()
    while True:
        try:
            if not MAINT_PAUSED:              # pause runtime depuis /reglages
                _m.run_cycle(sv)
        except Exception as e:
            print(f"  ⚠ maintenance : {e}")
        time.sleep(MAINTENANCE_EVERY)


def _backup_du():
    """La sauvegarde est-elle DUE ? L'échéance se lit sur le mtime du snapshot.

    Mode de panne corrigé le 12/08 : l'échéance était un compteur de tours
    (`cycle % 12`), variable LOCALE de maintenance_loop, donc remise à zéro à
    chaque démarrage. Le backup exigeait ainsi 1 h de fonctionnement d'affilée
    — or il n'y a pas de hot-reload : toute modif de server.py impose un
    redémarrage, et une journée de développement en compte plusieurs par
    heure. Résultat : la base pouvait n'être JAMAIS sauvegardée les jours de
    travail, c'est-à-dire exactement les jours où des jugements humains sont
    produits. `backup_verify` n'ayant jamais tourné, rien ne le signalait.

    Le fichier porte lui-même sa date : aucun état à maintenir, un redémarrage
    ne remet plus le compteur à zéro, et une sauvegarde en retard part au
    premier tour qui suit le démarrage. Absent ou NAS injoignable : on tente
    (backup_db attrape ses propres erreurs)."""
    try:
        return (time.time() - DB_BACKUP.stat().st_mtime) >= DB_BACKUP_INTERVAL
    except OSError:
        return True


def backup_db():
    """Snapshot de photos.db vers le NAS. Sans effet si l'on est resté en JSON."""
    if not hasattr(STORE, 'backup_to'):
        return
    try:
        # Les 5 stores partagent la même base : on les fait converger avant
        # le snapshot, sinon une mutation profonde non encore réconciliée
        # (ex. e['refs'].append(...)) manquerait dans la sauvegarde.
        for st in (STORE, FACE_STORE, ANIMAL_STORE, PETS_STORE, PEOPLE_STORE):
            if hasattr(st, 'backup_to'):
                st.save()
        if STORE.backup_to(DB_BACKUP):
            print(f"  💾 Sauvegarde de la base → {DB_BACKUP}")
            # Assurance-vie (audit A) : un snapshot jamais relu n'est pas une
            # sauvegarde. Restauration à blanc + comptage des jugements, puis
            # export du journal des jugements — le tout best-effort.
            backup_verify()
            export_jugements()
            # Ce que la base ne porte pas et qui ne se refabrique pas
            # (chantier 12) : 20 Mo à côté d'un snapshot de 276.
            backup_artefacts()
    except Exception as e:                                  # noqa: BLE001
        print(f"  ⚠ Sauvegarde de la base impossible : {e}")


def _compte_jugements_live():
    """(confirmés, exclusions) actuellement en mémoire (PEOPLE + PETS)."""
    conf = excl = 0
    for st in (PEOPLE_STORE, PETS_STORE):
        for e in list(st.data.values()):
            if isinstance(e, dict):
                conf += len(e.get('confirmed') or [])
                excl += len(e.get('exclude') or [])
    return conf, excl


def backup_verify():
    """Restauration à blanc du snapshot NAS (audit A — « assurance-vie »).

    L'actif le plus coûteux à reproduire (les jugements humains : confirmés,
    exclusions) ne vivait que dans photos.db, sauvegardé par une copie JAMAIS
    relue. Ici, après chaque backup : ouverture du snapshot NAS en lecture
    seule immuable (aucun verrou SMB — le mode immutable ne pose pas de
    verrou), PRAGMA integrity_check (relit toutes les pages : c'est la
    restauration à blanc), puis comptage des jugements humains dans les
    tables people/pets, comparé au vivant. Résultat dans BACKUP_VERIFY_STATE
    (affiché par /reglages). Best-effort : ne fait jamais échouer le backup."""
    import sqlite3 as _sq
    # ok : True = vérifié sain ; False = snapshot SUSPECT (integrity_check
    # non-ok) ; None = vérification impossible (à distinguer d'une alerte —
    # un échec d'ouverture n'incrimine pas la sauvegarde).
    res = {"at": time.time(), "ok": None, "integrity": "", "detail": "",
           "confirmes": None, "exclusions": None}
    try:
        # URI SQLite : PAS Path.as_uri() — sur un chemin UNC Windows
        # (\\nas\share\...), as_uri() met le serveur en AUTORITÉ d'URI, que
        # SQLite refuse (« invalid uri authority »). Forme acceptée : autorité
        # VIDE puis chemin commençant par //serveur/share → file:////nas/...
        raw = str(DB_BACKUP.resolve())
        if raw.startswith('\\\\'):
            upath = '//' + raw.lstrip('\\').replace('\\', '/')
        else:
            upath = raw.replace('\\', '/')
            if not upath.startswith('/'):
                upath = '/' + upath
        uri = ('file://' + urllib.parse.quote(upath, safe='/:')
               + '?mode=ro&immutable=1')
        cx = _sq.connect(uri, uri=True, timeout=30.0)
        try:
            res["integrity"] = str(cx.execute(
                "PRAGMA integrity_check").fetchone()[0])
            conf = excl = 0
            for table in ("people", "pets"):
                try:
                    for (v,) in cx.execute(f'SELECT v FROM "{table}"'):
                        try:
                            e = json.loads(v)
                        except (ValueError, TypeError):
                            continue
                        conf += len(e.get('confirmed') or [])
                        excl += len(e.get('exclude') or [])
                except _sq.Error as e:
                    res["detail"] = f"table {table} illisible : {e}"
            res["confirmes"], res["exclusions"] = conf, excl
        finally:
            cx.close()
        vconf, vexcl = _compte_jugements_live()
        res["ok"] = (res["integrity"] == "ok")
        if not res["ok"]:
            res["detail"] = f"integrity_check : {res['integrity'][:120]}"
            print(f"  ⚠ Sauvegarde NAS SUSPECTE — {res['detail']}")
        elif conf < vconf or excl < vexcl:
            # Normal si des jugements sont arrivés depuis le VACUUM ; anormal
            # si l'écart persiste de backup en backup.
            res["detail"] = (f"snapshot en retard : {vconf - conf} confirmation(s), "
                             f"{vexcl - excl} exclusion(s) de moins que le vivant")
        print(f"  ✔ Sauvegarde vérifiée (restauration à blanc) : integrity="
              f"{res['integrity'][:20]}, {conf} confirmé(s), {excl} exclusion(s)")
    except Exception as e:                                  # noqa: BLE001
        res["ok"] = None            # indéterminé — pas une alerte « suspecte »
        res["detail"] = str(e)[:200]
        print(f"  ⚠ Vérification de la sauvegarde impossible : {e}")
    BACKUP_VERIFY_STATE.update(res)


# Ce que la sauvegarde du 22/08 a cessé d'oublier. `backup_db()` ne poussait que
# `photos.db` et le journal des jugements ; `verifier_restauration.py` a nommé
# **9 artefacts IRRÉCUPÉRABLES sans aucune copie**, pour 20 Mo au total — dont
# `docs/undo_*.json`, la carte des 19 331 déplacements par laquelle 748
# décisions humaines ont retrouvé leur photo. Perdre 20 Mo à côté d'un snapshot
# de 276 Mo n'avait aucune raison d'être.
ARTEFACTS_A_SAUVER = (
    'lieux.txt', 'lieux_locaux.txt', 'vocabulaire_tags.txt',
    'dossier_uploads.txt', 'dossiers_a_taguer.txt', 'dossiers_a_explorer.txt',
    'gps_places.json',
)
# Les quarantaines se DÉCOUVRENT, elles ne se listent plus. Une liste en dur
# est toujours en retard d'un chantier : celle-ci nommait trois corbeilles
# quand le projet en avait six, et les deux nées le 22/08
# (`_corbeille_recalage`, `_corbeille_retraits`) — celles qui rendent
# annulables le recalage de 33 rattachements et le retrait de 2 couples —
# n'étaient sauvées NULLE PART. L'instrument du chantier 12 annonçait quand
# même « Total exposé : 0 o », parce qu'il lisait la même liste. Un geste
# annoncé RÉVERSIBLE dont la réversibilité tient à un dossier qu'aucune
# sauvegarde n'emporte est une promesse qu'un disque mort annule en silence.
QUARANTAINE_MOTIF = '_corbeille_*'
# Exclue, et pour une raison qui s'écrit : `_corbeille_session` est le rebut du
# ménage de fin de session (fichiers de travail, versionnés pour la plupart).
# Elle grossit de ~2 Mo par session et ne porte aucune décision humaine.
QUARANTAINES_NON_SAUVEES = ('_corbeille_session',)


def quarantaines(racine=None):
    """Les dossiers de quarantaine à sauver, découverts sur le disque."""
    base = Path(racine or SCRIPT_DIR)
    return tuple(sorted(
        d.name for d in base.glob(QUARANTAINE_MOTIF)
        if d.is_dir() and d.name not in QUARANTAINES_NON_SAUVEES))


def _copier_si_different(src, dst):
    """Copie `src` vers `dst` seulement si taille ou date diffèrent.

    Renommage atomique à l'arrivée : jamais de fichier à moitié écrit sur le
    NAS — même contrat que `export_jugements` et que l'écriture des index.
    Renvoie les octets copiés, 0 si rien à faire."""
    try:
        st = src.stat()
    except OSError:
        return 0
    try:
        d = dst.stat()
        if d.st_size == st.st_size and int(d.st_mtime) >= int(st.st_mtime):
            return 0
    except OSError:
        pass
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(dst.suffix + '.tmp')
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
        return st.st_size
    except OSError as e:
        print(f"  ⚠ Sauvegarde de {src.name} impossible : {e}")
        return 0


def backup_artefacts():
    """Copie sur le NAS ce que `photos.db` ne porte PAS (chantier 12).

    Les réglages saisis à la main (racines scannées, vocabulaires de lieux et de
    tags), les libellés de géocodage, les JOURNAUX DE DÉPLACEMENT et TOUTES les
    quarantaines présentes sur le disque (découvertes, jamais listées). Sans eux, un PC neuf ne redémarre pas le projet : sans
    `dossiers_a_taguer.txt` le serveur ne voit plus rien, sans `docs/undo_*`
    plus aucune décision décrochée n'est réparable, et sans les corbeilles les
    purges cessent d'être réversibles.

    Incrémental (taille + date), best-effort : ne fait jamais échouer le backup.
    """
    cible = DB_BACKUP.parent / 'artefacts'
    n = octets = 0
    try:
        for nom in ARTEFACTS_A_SAUVER:
            o = _copier_si_different(SCRIPT_DIR / nom, cible / nom)
            n += 1 if o else 0
            octets += o
        for src in sorted((SCRIPT_DIR / 'docs').glob('undo_*.json')):
            o = _copier_si_different(src, cible / 'docs' / src.name)
            n += 1 if o else 0
            octets += o
        for dossier in quarantaines():
            racine = SCRIPT_DIR / dossier
            if not racine.is_dir():
                continue
            for src in sorted(racine.rglob('*')):
                if src.is_file():
                    o = _copier_si_different(
                        src, cible / dossier / src.relative_to(racine))
                    n += 1 if o else 0
                    octets += o
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠ Sauvegarde des artefacts interrompue : {e}")
    BACKUP_VERIFY_STATE['artefacts'] = {'at': time.time(), 'fichiers': n,
                                        'octets': octets}
    if n:
        print(f"  🧰 Artefacts hors base sauvés : {n} fichier(s), "
              f"{octets / 1048576:.1f} Mo")
    return n


def export_jugements():
    """Copie du journal des jugements humains vers le NAS (hors du PC).

    journal_jugements.jsonl est append-only et LOCAL (comme photos.db) ; sans
    copie, un disque mort emporte l'historique des gestes. Copie entière +
    renommage atomique côté NAS : jamais de fichier à moitié écrit. Le fichier
    NAS est ensuite copiable hors site avec le reste du volume sauvegardé."""
    try:
        if not JUGEMENTS_PATH.exists():
            return False
        cible = DB_BACKUP.parent / JUGEMENTS_PATH.name
        tmp = cible.with_suffix(cible.suffix + '.tmp')
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(JUGEMENTS_PATH, tmp)
        os.replace(tmp, cible)
        BACKUP_VERIFY_STATE["jugements_exportes"] = time.time()
        return True
    except OSError as e:
        print(f"  ⚠ Export du journal des jugements impossible : {e}")
        return False


# ────────────────────────── Pages HTML ──────────────────────────

# Composant partagé : barre de navigation unifiée + thème sombre épuré. Injectés
# par _send_html là où le gabarit contient <!--APPNAV--> (et le thème avant
# </head>). Une seule source → cohérence garantie sur toutes les pages.
APP_NAV_CSS = """<style id="appnav-css">
/* Barre de nav partagee (7 pages) tokenisee « chambre noire ».
   Noms herites (--txt/--mut/--line) repointes sur les tokens de ui/tokens.css
   pour compat ; les regles .appnav utilisent directement les tokens.
   Choix design : onglet actif = pastille PAPIER (principal neutre = « vous etes
   ici »), jamais un accent ; la pastille de marque = veilleuse (la lampe
   inactinique, embleme de la chambre noire). */
:root{
  --line:#26221E; --txt:var(--texte); --mut:var(--graphite); --radius:12px;
}
.appnav{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:6px;
  padding:10px 14px;background:rgba(12,11,10,.86);backdrop-filter:blur(10px);
  border-bottom:var(--trait);flex-wrap:wrap;font-family:var(--f-texte);}
.appnav .brand{font-weight:700;font-size:15px;color:var(--texte);margin-right:10px;
  display:flex;align-items:center;gap:7px;text-decoration:none;letter-spacing:.2px;}
.appnav .brand .dot{width:9px;height:9px;border-radius:50%;
  background:var(--veilleuse);box-shadow:0 0 8px var(--veilleuse-d);}
.appnav a.tab{display:inline-flex;align-items:center;gap:6px;padding:7px 13px;
  border-radius:999px;color:var(--graphite);text-decoration:none;font-size:14px;
  font-weight:500;transition:background .15s,color .15s;white-space:nowrap;}
.appnav a.tab:hover{color:var(--texte);background:#ffffff10;}
.appnav a.tab.active{color:var(--texte-papier);background:var(--papier);
  box-shadow:0 2px 10px #0007;}
.appnav .sp{flex:1;}
/* Indicateur d'activite reseau global : apparait des qu'une requete fetch/POST
   est en vol (voir le script d'enrobage plus bas). Accent --veilleuse = « en
   cours / en attente », par le design system. Rassure : « ca travaille, patiente
   » plutot que « le site a plante ». Coin bas-droit, non intrusif, au-dessus de
   tout (z-index tres haut) pour rester visible meme sur une modale ou un
   diaporama. */
.netbusy{position:fixed;right:14px;bottom:14px;z-index:1000;display:none;
  align-items:center;gap:9px;padding:9px 15px;border-radius:999px;
  background:var(--salle-2);border:1px solid var(--veilleuse);color:var(--texte);
  font:500 13px/1 var(--f-texte);box-shadow:0 6px 22px #000a;}
.netbusy.on{display:flex;}
.netbusy__s{width:14px;height:14px;border-radius:50%;
  border:2px solid var(--veilleuse);border-top-color:transparent;
  animation:netbusy-spin .7s linear infinite;}
@keyframes netbusy-spin{to{transform:rotate(360deg);}}
@media(prefers-reduced-motion:reduce){.netbusy__s{animation:none;}}
/* Recherche IA depuis TOUT onglet (1 duodecies, Mike 30/08) : un vrai
   formulaire vers /files?q=, donc Entree suffit et rien ne depend du JS.
   Cible tactile a --touch (44 px) comme tout controle du systeme ; masque par
   global.js sur /files, ou la galerie porte deja sa barre. */
.appnav-q{display:flex;align-items:center;gap:var(--e-1);margin-left:var(--e-2);}
.appnav-q input{min-height:var(--touch);width:clamp(140px,22vw,300px);
  padding:0 var(--e-3);border:var(--trait);border-radius:var(--r-pill);
  background:var(--salle-3);color:var(--texte);font:var(--t-sm) var(--f-texte);}
.appnav-q input::placeholder{color:var(--graphite);opacity:1;}
.appnav-q button{min-height:var(--touch);min-width:var(--touch);padding:0 var(--e-2);
  border:var(--trait);border-radius:var(--r-pill);background:var(--salle-3);
  color:var(--texte);font:var(--t-sm) var(--f-texte);cursor:pointer;}
@media(hover:hover){.appnav-q button:hover{background:var(--salle-4);}}
.appnav-q button:active{background:var(--salle-4);}
.appnav-q kbd{font:var(--t-xs) var(--f-donnees);color:var(--graphite);
  border:var(--trait);border-radius:var(--r-sm);padding:1px 5px;}
/* Le pense-bete des raccourcis (point 6 du plancher). Bouton « ? » dans la
   barre, panneau ouvert par la touche ? ou le bouton, ferme par Echap ; le
   contenu vient de /api/raccourcis (docs/RACCOURCIS.md), rendu par global.js.
   Un panneau qu'on LIT, pas ou l'on decide : surface sombre, pas papier. */
.appnav-aide{min-height:var(--touch);min-width:var(--touch);border:var(--trait);
  border-radius:var(--r-pill);background:var(--salle-3);color:var(--texte);
  font:600 var(--t-md)/1 var(--f-donnees);cursor:pointer;}
@media(hover:hover){.appnav-aide:hover{background:var(--salle-4);}}
.appnav-aide:active{background:var(--salle-4);}
.raccourcis{position:fixed;inset:0;z-index:900;display:none;align-items:flex-start;
  justify-content:center;padding:var(--e-6) var(--e-4);background:#000a;overflow:auto;}
.raccourcis.on{display:flex;}
.raccourcis__p{width:min(720px,100%);background:var(--salle-2);color:var(--texte);
  border:var(--trait);border-radius:var(--r-md);padding:var(--e-4) var(--e-6);
  box-shadow:0 12px 40px #000c;font-family:var(--f-texte);}
.raccourcis__t{display:flex;align-items:center;gap:var(--e-3);margin:0 0 var(--e-3);}
.raccourcis__t h2{margin:0;font:600 var(--t-lg)/1.2 var(--f-affichage);flex:1;}
.raccourcis__p h3{margin:var(--e-4) 0 var(--e-2);font:600 var(--t-md)/1.2 var(--f-affichage);
  color:var(--texte);}
.raccourcis__p h3 .ici{font:var(--t-xs) var(--f-texte);color:var(--texte-papier);
  background:var(--papier);border-radius:var(--r-pill);padding:2px 8px;margin-left:var(--e-2);}
.raccourcis__p p{margin:0 0 var(--e-2);color:var(--graphite);font-size:var(--t-sm);}
.raccourcis__p table{border-collapse:collapse;width:100%;font-size:var(--t-sm);}
.raccourcis__p td{padding:var(--e-1) var(--e-2);border-top:var(--trait);vertical-align:top;}
.raccourcis__p td:first-child{white-space:nowrap;width:1%;}
.raccourcis__p kbd,.raccourcis__p code{font:var(--t-xs) var(--f-donnees);color:var(--texte);
  border:var(--trait);border-radius:var(--r-sm);padding:1px 5px;background:var(--salle-3);}
.raccourcis__p .btn{min-height:var(--touch);padding:0 var(--e-4);border:var(--trait);
  border-radius:var(--r-md);background:var(--salle-3);color:var(--texte);cursor:pointer;
  font:500 var(--t-sm)/1 var(--f-texte);}
@media(max-width:560px){
  .appnav{gap:2px;padding:8px 8px;}
  .raccourcis{padding:var(--e-2);}
  .raccourcis__p{padding:var(--e-3) var(--e-4);}
  .appnav .brand span.t{display:none;}
  .appnav a.tab{padding:7px 10px;font-size:13px;}
  /* Telephone : le champ passe en DERNIER et prend le reste de la ligne ou
     Reglages est tombe — deux lignes de barre, pas trois (mesure a 390 px :
     128 px avec le champ seul sur sa ligne, contre ~84 px ainsi). */
  .appnav-q{margin-left:0;flex:1 1 160px;order:1;}
  .appnav-q input{flex:1;width:auto;}
  .appnav-q kbd{display:none;}
  .netbusy{right:10px;bottom:10px;padding:8px 13px;font-size:12px;}
}
</style>"""

APP_NAV_HTML = """<nav class="appnav">
  <a class="brand" href="/"><span class="dot"></span><span class="t">Photos</span></a>
  <a class="tab" data-p="/files" href="/files">&#128247; Galerie</a>
  <a class="tab" data-p="/browse" href="/browse">&#128193; Dossiers</a>
  <a class="tab" data-p="/map" href="/map">&#128506;&#65039; Carte</a>
  <a class="tab" data-p="/sujets" href="/sujets">&#128450;&#65039; Sujets</a>
  <span class="sp"></span>
  <form class="appnav-q" role="search" action="/files" method="get">
    <label class="hors-ecran" for="appnav-q">Recherche IA : d&eacute;cris la photo</label>
    <input type="search" id="appnav-q" name="q" placeholder="D&eacute;cris la photo&hellip;"
           autocomplete="off" title="Recherche IA sur toute la phototh&egrave;que (raccourci : /)">
    <button type="submit" aria-label="Chercher">&#128269;</button>
    <kbd aria-hidden="true" title="Raccourci clavier">/</kbd>
  </form>
  <a class="tab" data-p="/reglages" href="/reglages">&#9881;&#65039; R&eacute;glages</a>
  <button type="button" class="appnav-aide" aria-label="Raccourcis clavier"
          aria-haspopup="dialog" aria-expanded="false" title="Raccourcis clavier (touche ?)">?</button>
</nav>
<div class="netbusy" role="status" aria-live="polite" aria-hidden="true">
  <span class="netbusy__s" aria-hidden="true"></span><span>Traitement en cours&hellip;</span>
</div>
<!-- l'onglet actif et le sablier reseau vivent dans ui/global.js, la brique commune -->"""


# Sous-navigation « Sujets » (ROADMAP #2 : guichet unique). UNE source, injectée
# par _send_html là où le gabarit contient <!--SUJETSNAV--> (/sujets, /people,
# /pets) : l'annuaire, les vues spécialisées et l'onglet Classification se
# présentent comme les facettes d'un même guichet. Onglet actif = pastille
# papier (même convention que l'appnav : « vous êtes ici », jamais un accent).
SUJETS_NAV_HTML = """<style id="sujetsnav-css">
.sujnav{display:flex;gap:var(--e-2);align-items:center;flex-wrap:wrap;
  padding:var(--e-2) var(--e-4);border-bottom:var(--trait);
  background:var(--salle-2);font-family:var(--f-texte);}
.sujnav .lbl{color:var(--graphite);font-size:var(--t-xs);
  text-transform:uppercase;letter-spacing:.06em;margin-right:var(--e-1);}
.sujnav a{display:inline-flex;align-items:center;gap:6px;min-height:36px;
  padding:0 var(--e-3);border-radius:var(--r-pill);color:var(--graphite);
  text-decoration:none;font:500 var(--t-sm)/1 var(--f-texte);white-space:nowrap;}
.sujnav a:hover{color:var(--texte);background:#ffffff10;}
.sujnav a.active{color:var(--texte-papier);background:var(--papier);}
.sujnav a .n{font-family:var(--f-donnees);font-size:var(--t-xs);opacity:.75;}
</style>
<nav class="sujnav" aria-label="Sections Sujets">
  <span class="lbl">Sujets</span>
  <a data-s="/sujets" href="/sujets">Annuaire</a>
  <a data-s="/people" href="/people">&#128101; Personnes</a>
  <a data-s="/pets" href="/pets">&#128062; Animaux</a>
  <a data-s="classif" href="/sujets?vue=classification">&#128203; Classification</a>
</nav>
<script>(function(){
  var p=location.pathname;
  var vue=new URLSearchParams(location.search).get('vue');
  var cur = p.indexOf('/people')===0 ? '/people'
          : p.indexOf('/pets')===0   ? '/pets'
          : (vue==='classification'  ? 'classif' : '/sujets');
  document.querySelectorAll('.sujnav a').forEach(function(a){
    if(a.getAttribute('data-s')===cur) a.classList.add('active');
  });
})();</script>"""


# ─── Assets UI partages (design system « chambre noire ») ────────────────────
# tokens.css + base.css sont injectes sur CHAQUE page par _send_html, a la
# maniere d'APP_NAV_CSS : une seule source dans ui/, donc coherence garantie.
# Charges au demarrage et relus si un fichier change (confort de dev, sans
# redemarrage). Invariant zero-dependance : si ui/ est absent, le serveur
# demarre quand meme et sert des pages sans le design system (chaine vide).
# components.css est OPT-IN (adopte page par page lors du redesign), donc PAS
# injecte ici — l'injecter globalement ecraserait le CSS des pages historiques.
UI_DIR = SCRIPT_DIR / "ui"
_UI_GLOBAL_FILES = ("tokens.css", "base.css")   # ordre : variables puis a11y
_UI_CACHE = {"css": None, "sig": None}

# ─── Adoption du design system, page par page ────────────────────────────────
# `components.css` redefinit `.btn`, `.chip`, `.feuille`… : l'injecter partout
# ecraserait les pages historiques (voir plus haut). Une page l'ADOPTE en
# posant le marqueur `<!--UI:components-->` a l'endroit exact ou elle veut la
# feuille — en pratique JUSTE AVANT son propre `<style>`.
#
# POURQUOI DANS LA PAGE, ET AVANT SON STYLE. Le CSS injecte a `</head>` arrive
# APRES le `<style>` de la page et gagnerait donc la cascade : la page perdrait
# le dernier mot au moment meme ou elle converge, et n'aurait plus aucun moyen
# de garder une exception le temps de la migration. Le marqueur laisse la page
# choisir sa place, et donc garder la main.
_UI_COMPOSANTS_FILES = ("components.css",)
_UI_COMPOSANTS_MARQUEUR = "<!--UI:components-->"
_UI_COMPOSANTS_CACHE = {"css": None, "sig": None}


def _ui_signature():
    """(nom, mtime, taille) par fichier : detecte une edition sans tout relire."""
    sig = []
    for name in _UI_GLOBAL_FILES:
        try:
            st = (UI_DIR / name).stat()
            sig.append((name, int(st.st_mtime), st.st_size))
        except OSError:
            sig.append((name, 0, 0))
    return tuple(sig)


def _composants_signature():
    """Même idiome que `_ui_signature` : une edition se voit sans tout relire."""
    sig = []
    for name in _UI_COMPOSANTS_FILES:
        try:
            st = (UI_DIR / name).stat()
            sig.append((name, int(st.st_mtime), st.st_size))
        except OSError:
            sig.append((name, 0, 0))
    return tuple(sig)


def ui_composants_css():
    """Le bloc `<style id="ui-components">` des pages qui ont ADOPTE le design
    system. Chaine vide si `ui/` est absent — le serveur demarre quand meme
    (invariant zero-dependance), la page rend alors avec son CSS a elle."""
    sig = _composants_signature()
    if _UI_COMPOSANTS_CACHE["sig"] != sig:
        parts = []
        for name in _UI_COMPOSANTS_FILES:
            try:
                txt = (UI_DIR / name).read_text(encoding="utf-8")
            except Exception:
                txt = ""
            if txt.strip():
                parts.append(f"/* {name} */\n{txt}")
        _UI_COMPOSANTS_CACHE["css"] = (
            '<style id="ui-components">\n' + "\n".join(parts) + "\n</style>"
        ) if parts else ""
        _UI_COMPOSANTS_CACHE["sig"] = sig
    return _UI_COMPOSANTS_CACHE["css"]


def ui_shared_css():
    """Bloc <style id="ui-shared"> a injecter dans chaque page. Mis en cache,
    recharge si un fichier ui/ a change. Chaine vide si ui/ absent."""
    sig = _ui_signature()
    if _UI_CACHE["sig"] != sig:
        parts = []
        for name in _UI_GLOBAL_FILES:
            try:
                txt = (UI_DIR / name).read_text(encoding="utf-8")
            except Exception:
                txt = ""
            if txt.strip():
                parts.append(f"/* {name} */\n{txt}")
        _UI_CACHE["css"] = ('<style id="ui-shared">\n' + "\n".join(parts) +
                            "\n</style>") if parts else ""
        _UI_CACHE["sig"] = sig
    return _UI_CACHE["css"]


# ─── La brique JS commune (1 duodecies) ──────────────────────────────────────
# ui/global.js, injectee sur CHAQUE page par _send_html juste apres la barre
# (<!--APPNAV-->), sinon avant </body>. Meme contrat que le CSS partage : une
# seule source, relue si elle change, cuite par bundle.py, chaine vide si ui/
# est absent — le serveur sert alors des pages sans onglet allume ni sablier,
# mais il sert. Le formulaire de recherche de la barre n'en depend PAS.
_UI_JS_FILES = ("global.js",)
_UI_JS_CACHE = {"js": None, "sig": None}


def _js_signature():
    sig = []
    for name in _UI_JS_FILES:
        try:
            st = (UI_DIR / name).stat()
            sig.append((name, int(st.st_mtime), st.st_size))
        except OSError:
            sig.append((name, 0, 0))
    return tuple(sig)


def ui_shared_js():
    """Bloc <script id="ui-global"> a injecter dans chaque page. Mis en cache,
    recharge si ui/global.js a change. Chaine vide si ui/ absent."""
    sig = _js_signature()
    if _UI_JS_CACHE["sig"] != sig:
        parts = []
        for name in _UI_JS_FILES:
            try:
                txt = (UI_DIR / name).read_text(encoding="utf-8")
            except Exception:
                txt = ""
            # Un « </script> » dans la source fermerait le bloc a mi-chemin.
            txt = txt.replace("</script", "<\\/script")
            if txt.strip():
                parts.append(f"/* {name} */\n{txt}")
        _UI_JS_CACHE["js"] = ('<script id="ui-global">\n' + "\n".join(parts) +
                              "\n</script>") if parts else ""
        _UI_JS_CACHE["sig"] = sig
    return _UI_JS_CACHE["js"]


def injecter_js_commun(html_str, bloc):
    """Pose le bloc JS commun UNE fois : juste apres la barre (le sablier doit
    enrober `fetch` AVANT les scripts de la page, et l'onglet s'allume sans
    attendre la fin de l'analyse), sinon avant </body>. Regle pure."""
    if not bloc or 'id="ui-global"' in html_str:
        return html_str
    debut_nav = html_str.find('<nav class="appnav">')
    fin_nav = html_str.find('</nav>', debut_nav) if debut_nav >= 0 else -1
    if fin_nav >= 0:
        k = fin_nav + len('</nav>')
        return html_str[:k] + bloc + html_str[k:]
    if '</body>' in html_str:
        return html_str.replace('</body>', bloc + '</body>', 1)
    return html_str


# ─── Gabarits de pages sortis du monolithe (point 7) ─────────────────────────
# Même mécanisme que le CSS partagé, pour la même raison : une seule source,
# relue quand elle change, et un mono-fichier qui reste déployable seul.
# `bundle.py` CUIT les gabarits dans `_UI_PAGES_CUIT` ; sans `ui/`, c'est lui
# qui répond, exactement comme pour `_UI_CACHE`.
# Une page ABSENTE des deux côtés ne rend pas une page blanche : elle DIT quel
# fichier manque. Un gabarit muet se lirait comme une page vide, et on
# chercherait le défaut dans les données (leçon des « 0 photo taguée »).
UI_PAGES_DIR = UI_DIR / "pages"
_UI_PAGES = {}                  # nom -> {"html": …, "sig": (mtime, taille)}
_UI_PAGES_CUIT = {}             # rempli par bundle.py — NE PAS renommer


def _ui_page_signature(nom):
    try:
        st = (UI_PAGES_DIR / f"{nom}.html").stat()
        return (int(st.st_mtime), st.st_size)
    except OSError:
        return (0, 0)


def ui_page(nom):
    """Gabarit HTML de la page `nom`, lu dans `ui/pages/<nom>.html`.

    Mis en cache, relu si le fichier change (édition sans redémarrage), replié
    sur le gabarit cuit par `bundle.py` quand `ui/` est absent."""
    sig = _ui_page_signature(nom)
    cache = _UI_PAGES.get(nom)
    if cache is not None and cache["sig"] == sig:
        return cache["html"]
    html_str = ""
    if sig != (0, 0):
        try:
            html_str = (UI_PAGES_DIR / f"{nom}.html").read_text(encoding="utf-8")
        except OSError:
            html_str = ""
    if not html_str:
        html_str = _UI_PAGES_CUIT.get(nom, "")
    if not html_str:
        html_str = (
            "<!DOCTYPE html><html lang=\"fr\"><head><meta charset=\"UTF-8\">"
            f"<title>Gabarit manquant</title></head><body>"
            f"<h1>Gabarit introuvable&nbsp;: ui/pages/{html.escape(nom)}.html</h1>"
            "<p>Le serveur tourne, mais cette page n'a pas de gabarit&nbsp;: "
            "le dossier <code>ui/</code> est absent et ce fichier n'a pas ete "
            "cuit par <code>bundle.py</code>. Redeploie <code>ui/</code>, ou "
            "regenere <code>dist/server.py</code>.</p></body></html>")
    _UI_PAGES[nom] = {"html": html_str, "sig": sig}
    return html_str


# HTML_PAGE vit dans ui/pages/upload.html (point 7).

# GALLERY_PAGE vit dans ui/pages/gallery.html (point 7).


# BROWSE_PAGE vit desormais dans ui/pages/browse.html (point 7, premiere
# page sortie du monolithe). Lue par ui_page('browse') a chaque service :
# une edition du gabarit se voit sans redemarrer.


# REGLAGES_PAGE vit dans ui/pages/reglages.html (point 7).


# ────────────────────────── Serveur HTTP ──────────────────────────

def _run_maint_once():
    """Un cycle de maintenance a la demande (bouton /reglages), en arriere-plan."""
    import maintenance as _m
    try:
        _m.run_cycle(_MaintSv())
    except Exception as e:                                    # noqa: BLE001
        print(f"  ⚠ maintenance (manuel) : {e}")


def generer_plan_annee():
    """Plan de rangement par ANNEE des fichiers sous « _A TRIER », depuis l'index
    EN MEMOIRE. LECTURE SEULE : n'ecrit AUCUN fichier media, seulement
    docs/plan_rangement_annee.{json,md}. `_best_time` ne lit pas le NAS (date
    stockee + nom + annee de chemin), donc c'est rapide et sans I/O disque lourde.
    L'APPLICATION reste un geste separe (via la primitive de deplacement testee)."""
    import rangement_annee as _ra
    items = []
    for key, e in list(STORE.data.items()):
        if not isinstance(e, dict):
            continue
        p = _resolve_key(key)
        if _ra._atri_index(Path(p).parts) is None:
            continue
        items.append((key, str(p), _best_time(key, e)))
    plan = _ra.construire_plan(items)
    # Cle CIBLE de chaque move, derivee ICI ou les racines/UPLOAD_DIR sont connus
    # (le seul endroit qui peut la calculer correctement). L'applicateur autonome
    # s'en sert pour re-cler l'index sans deviner ; il retombe sur str(dst) sinon.
    #   - cle absolue (dossier NAS supplementaire, cas de « _A TRIER ») : new = str(dst)
    #   - cle relative posix (fichier sous Uploads) : new = dst relatif a UPLOAD_DIR
    for mv in plan['moves']:
        if fichiers.norm(mv['key']) == fichiers.norm(mv['src']):
            mv['new_key'] = str(Path(mv['dst']))
        else:
            mv['new_key'] = fichiers.key_for_new_path(UPLOAD_DIR, UPLOAD_DIR, mv['dst'])
    docs = SCRIPT_DIR / 'docs'
    try:
        docs.mkdir(exist_ok=True)
    except OSError:
        pass
    (docs / 'plan_rangement_annee.json').write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    lignes = ["# Plan de rangement par annee (lecture seule)", "",
              f"- A ranger : **{plan['total_a_ranger']}**",
              f"- Sans date fiable -> _SANS_DATE : **{plan['sans_date']}**",
              f"- Conflits de plan (a trancher) : **{len(plan['conflits'])}**",
              f"- Deja en place : {plan['deja']}", "", "## Par annee", ""]
    for an, n in plan['par_annee'].items():
        lignes.append(f"- {an} : {n}")
    (docs / 'plan_rangement_annee.md').write_text("\n".join(lignes) + "\n",
                                                  encoding='utf-8')
    return plan


def _run_plan_annee():
    try:
        p = generer_plan_annee()
        print(f"  🗂 plan rangement annee : {p['total_a_ranger']} a ranger, "
              f"{p['sans_date']} sans date, {len(p['conflits'])} conflits")
    except Exception as e:                                    # noqa: BLE001
        print(f"  ⚠ plan rangement annee : {e}")


def _remplacer_nom(key, nouveau_nom):
    """Cle avec le DERNIER composant remplace, en preservant le separateur
    d'origine (Windows « \\ » pour les racines NAS, « / » pour Uploads). Sert a
    deriver la cle CIBLE d'un renommage EN PLACE."""
    k = str(key)
    i = max(k.rfind('\\'), k.rfind('/'))
    return (k[:i + 1] + nouveau_nom) if i >= 0 else nouveau_nom


def generer_plan_renommage():
    """Plan de RENOMMAGE des NOMS BRUTS, depuis l'index EN MEMOIRE. LECTURE
    SEULE : n'ecrit AUCUN fichier media, seulement docs/plan_renommage.{json,md}.

    Renommage EN PLACE (meme dossier) -> `new_key` = meme cle, nouveau nom de
    base, separateur d'origine preserve, pour que l'applicateur in-process
    re-cle l'index (rekey_everywhere) sans deviner. L'APPLICATION reste un geste
    separe (Phase 3). Ne cible QUE les noms bruts (plan_renommage.est_nom_brut)."""
    import plan_renommage as _pr
    import renommage_facts as _rf
    try:
        lieux = _rf.load_lieux(LIEUX_FICHIER)
    except Exception:                                         # noqa: BLE001
        lieux = None
    entries = [(k, e) for k, e in list(STORE.data.items())
               if isinstance(e, dict) and not e.get('failed')]
    gps_places = gps_places_connus()   # géocodage inverse offline précalculé
    moves, stats = _pr.construire_plan(entries, lieux=lieux, gps_places=gps_places)
    for mv in moves:
        mv['new_key'] = _remplacer_nom(mv['key'], mv['new_name'])
    plan = {'moves': moves, 'stats': stats}
    docs = SCRIPT_DIR / 'docs'
    try:
        docs.mkdir(exist_ok=True)
    except OSError:
        pass
    (docs / 'plan_renommage.json').write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    lignes = ["# Plan de renommage (lecture seule) — noms bruts seulement", "",
              f"- A renommer : **{stats['a_renommer']}**",
              f"- Laisses tels quels (deja dates/propres) : {stats['laisses_tels_quels']}",
              f"- Bruts deja au bon nom : {stats['inchanges']}",
              f"- Total examine : {stats['total']}", "",
              "## Exemples (30 premiers)", "",
              "| Ancien nom | Nouveau nom |", "|---|---|"]
    for mv in moves[:30]:
        lignes.append(f"| {mv['old_name']} | {mv['new_name']} |")
    (docs / 'plan_renommage.md').write_text("\n".join(lignes) + "\n",
                                            encoding='utf-8')
    return plan


def _run_plan_renommage():
    try:
        p = generer_plan_renommage()
        s = p['stats']
        print(f"  ✏ plan renommage : {s['a_renommer']} a renommer sur "
              f"{s['total']} (bruts seulement)")
    except Exception as e:                                    # noqa: BLE001
        print(f"  ⚠ plan renommage : {e}")


RENOMMAGE_LOT = 200   # renommages effectifs par clic « Appliquer un lot »


def appliquer_renommage(limite=None, dry=True):
    """Applique `docs/plan_renommage.json` EN PLACE, IN-PROCESS, réversible.

    Sécurité (miroir de `appliquer_plan_annee.py`) : la source doit exister, la
    cible NE doit PAS exister (jamais d'écrasement), la clé cible doit être
    absente de l'index. `dry=True` ne renomme rien (compte l'applicable). `limite`
    borne le nombre de renommages EFFECTIFS (le reste attend un prochain lot ;
    les déjà-renommés — source absente — sont sautés silencieusement, donc
    recliquer reprend là où on s'était arrêté). Chaque renommage re-clé via
    `rekey_everywhere` (tags + visages/animaux + sémantique → aucun nom humain
    perdu) et un journal undo est écrit. Renvoie un résumé."""
    plan_path = SCRIPT_DIR / 'docs' / 'plan_renommage.json'
    try:
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
    except Exception as e:                                    # noqa: BLE001
        return {'ok': False, 'error': f'plan illisible ({e}) — génère-le d’abord.'}
    moves = plan.get('moves') or []
    faits, sautes, journal = 0, [], []
    for mv in moves:
        key, new_key, new_name = mv.get('key'), mv.get('new_key'), mv.get('new_name')
        if not (key and new_key and new_name):
            sautes.append([mv.get('old_name'), 'move incomplet']); continue
        try:
            src = _resolve_key(key)
        except Exception:                                     # noqa: BLE001
            sautes.append([mv.get('old_name'), 'clé irrésolue']); continue
        if not src.is_file():
            continue    # déjà renommé (source absente) → repris silencieusement
        dst = src.parent / new_name
        if dst.exists():
            sautes.append([mv.get('old_name'), 'cible existante — jamais écraser']); continue
        if STORE.data.get(new_key) is not None:
            sautes.append([mv.get('old_name'), 'clé cible déjà indexée']); continue
        # applicable
        if not dry and limite is not None and faits >= limite:
            break
        if dry:
            faits += 1; continue
        try:
            note_heavy_activity()
            src.rename(dst)                       # même dossier → renommage atomique
        except OSError as e:
            sautes.append([mv.get('old_name'), f'rename: {e}']); continue
        rekey_everywhere(key, new_key, save=False)
        journal.append({'old_key': key, 'new_key': new_key,
                        'src': str(src), 'dst': str(dst)})
        faits += 1
    if not dry and journal:
        STORE.save()
        for st in (FACE_STORE, PEOPLE_STORE, ANIMAL_STORE, PETS_STORE):
            st.save()
        gps_places_save()   # 7e magasin (audit I2), differe par save=False
        ts = time.strftime('%Y%m%d_%H%M%S')
        try:
            (SCRIPT_DIR / 'docs' / f'undo_renommage_{ts}.json').write_text(
                json.dumps(journal, ensure_ascii=False, indent=1), encoding='utf-8')
        except OSError:
            pass
    return {'ok': True, 'dry': dry, 'faits': faits, 'sautes': len(sautes),
            'exemples_sautes': sautes[:8], 'total_plan': len(moves)}


def annuler_renommage(journal_path=None):
    """Annule le dernier lot de renommage (ou le journal indiqué) : renomme
    `dst → src` et re-clé `new_key → old_key`. Sûr et idempotent : un op déjà
    annulé (dst absent ou src présent) est sauté."""
    docs = SCRIPT_DIR / 'docs'
    if journal_path:
        jp = Path(journal_path)
    else:
        js = sorted(docs.glob('undo_renommage_*.json'))
        if not js:
            return {'ok': False, 'error': 'aucun lot de renommage à annuler.'}
        jp = js[-1]
    try:
        journal = json.loads(jp.read_text(encoding='utf-8'))
    except Exception as e:                                    # noqa: BLE001
        return {'ok': False, 'error': str(e)}
    annules = 0
    for op in reversed(journal):
        src, dst = Path(op['src']), Path(op['dst'])
        if not dst.is_file() or src.exists():
            continue
        try:
            note_heavy_activity()
            dst.rename(src)
        except OSError:
            continue
        rekey_everywhere(op['new_key'], op['old_key'], save=False)
        annules += 1
    if annules:
        STORE.save()
        for st in (FACE_STORE, PEOPLE_STORE, ANIMAL_STORE, PETS_STORE):
            st.save()
        gps_places_save()   # 7e magasin (audit I2), differe par save=False
        try:
            jp.rename(jp.with_name(jp.stem + '.annule.json'))
        except OSError:
            pass
    return {'ok': True, 'annules': annules}


def human_size(n):
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} To"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# MAP_PAGE vit dans ui/pages/map.html (point 7).


# ────────────────── Reconnaissance de personnes (Phase 1) ──────────────────
# Détection des visages + calcul d'un « embedding » (vecteur 512D) par visage,
# stockés dans faces_index.json. La mise en correspondance avec des noms
# (Phase 2) se fera à partir de ces vecteurs. Tout est local (GPU si présent).

FACE_APP = None            # instance InsightFace (chargée paresseusement)
FACE_INIT_DONE = False
FACE_ERROR = ""            # message si les dépendances manquent
FACE_PROVIDER = ""         # 'GPU' / 'CPU' effectivement utilisé


_HW_CACHE = {"at": 0.0, "data": None}


def _nombre(brut, entier=True):
    """Nombre lu d'une sortie nvidia-smi, ou None si le champ est [N/A].

    Une sonde ne doit JAMAIS lever : `hw_state` porte l'arbitre GPU et
    `system_busy`. Un champ absent sur une autre carte rendrait le serveur
    aveugle a sa propre VRAM."""
    try:
        v = float(str(brut).strip())
    except (TypeError, ValueError):
        return None
    return int(v) if entier else round(v, 1)


def hw_state(force=False):
    """Sonde le matériel : CPU, RAM (via psutil si présent), GPU/VRAM (via
    nvidia-smi). Résultat mis en cache ~8 s (`force=True` court-circuite le
    cache — nécessaire à l'arbitre GPU juste après une éviction, sinon la
    mesure périmée ne voit pas la VRAM rendue). Permet au serveur de
    s'adapter à la machine (et de se ré-adapter si le matériel change)."""
    now = time.time()
    if not force and _HW_CACHE["data"] is not None and now - _HW_CACHE["at"] < 8:
        return _HW_CACHE["data"]
    d = {"cpu_count": os.cpu_count() or 1, "cpu_percent": None,
         "ram_total_gb": None, "ram_avail_gb": None, "gpu": None, "psutil": False}
    try:
        import psutil
        d["psutil"] = True
        d["cpu_percent"] = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        d["ram_total_gb"] = round(vm.total / 1e9, 1)
        d["ram_avail_gb"] = round(vm.available / 1e9, 1)
    except Exception:
        pass
    try:
        # Les champs sont ceux que `mesure_thermique.py` a PROUVES lisibles sur
        # cette carte (28/08). Un seul champ refuse fait echouer TOUTE la
        # requete groupee, sans dire lequel : `power.limit` et
        # `temperature.memory` rendent [N/A] ici, ils sont donc absents. Ne
        # jamais en ajouter un sans l'avoir mesure d'abord.
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,memory.free,"
             "utilization.gpu,temperature.gpu,clocks.sm,clocks.max.sm,"
             "power.draw,clocks_throttle_reasons.active,"
             "clocks_throttle_reasons.hw_thermal_slowdown,"
             "clocks_throttle_reasons.sw_thermal_slowdown",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        line = (r.stdout or "").strip().splitlines()
        if r.returncode == 0 and line:
            p = [x.strip() for x in line[0].split(",")]
            if len(p) >= 5:
                d["gpu"] = {"name": p[0], "vram_total_mb": int(float(p[1])),
                            "vram_used_mb": int(float(p[2])), "vram_free_mb": int(float(p[3])),
                            "util": int(float(p[4]))}
            if len(p) >= 10:
                # `_nombre` et non `int(...)` : un champ peut rendre [N/A] sur
                # une autre machine, et une sonde qui LEVE prive le serveur de
                # tout `hw_state` — donc de son arbitre GPU.
                d["gpu"].update({
                    "temp_c": _nombre(p[5]),
                    "clocks_mhz": _nombre(p[6]),
                    "clocks_max_mhz": _nombre(p[7]),
                    "watts": _nombre(p[8], entier=False),
                    "bridage": p[9] or None})
            if len(p) >= 12:
                # Les DEUX drapeaux booleens plutot que le masque de `bridage` :
                # nvidia-smi les rend en toutes lettres ("Active" / "Not
                # Active"), la ou le masque demanderait de connaitre par coeur
                # les constantes NVML. On garde le masque pour la trace, on
                # JUGE sur ce qui se lit.
                d["gpu"]["bride_thermique"] = (
                    p[10].strip().lower() == 'active'
                    or p[11].strip().lower() == 'active')
    except Exception:
        pass
    _HW_CACHE["data"] = d
    _HW_CACHE["at"] = now
    return d


def system_busy():
    """Vrai si la machine est occupée (utilisateur actif / RAM basse) → on lève
    le pied sur les tâches de fond lourdes."""
    hw = hw_state()
    cp = hw.get("cpu_percent")
    if cp is not None and cp > REEMBED_CPU_BUSY:
        return True
    ram = hw.get("ram_avail_gb")
    if ram is not None and ram < REEMBED_MIN_RAM_GB:
        return True
    return False


def reembed_resolution():
    """Résolution d'analyse adaptée à la RAM libre. 0 = pleine résolution."""
    ram = hw_state().get("ram_avail_gb")
    if ram is None:
        return 2048
    if ram >= 6:
        return 0
    if ram >= 3:
        return 2560
    return 2048


def get_face_app():
    """Charge InsightFace une seule fois. Retourne None si indisponible
    (dépendances non installées) — le serveur continue de fonctionner."""
    global FACE_APP, FACE_INIT_DONE, FACE_ERROR, FACE_PROVIDER
    if FACE_INIT_DONE:
        return FACE_APP
    FACE_INIT_DONE = True
    try:
        import warnings
        warnings.filterwarnings("ignore", category=FutureWarning)
        if FACE_USE_GPU:
            # Charge les DLL CUDA/cuDNN (wheels pip nvidia-*-cu13) avant onnx.
            try:
                import onnxruntime as _ort
                if hasattr(_ort, 'preload_dlls'):
                    _ort.preload_dlls()
            except Exception as _e:
                print(f"  · preload CUDA ignoré : {_e}")
        from insightface.app import FaceAnalysis
        providers = (['CUDAExecutionProvider', 'CPUExecutionProvider']
                     if FACE_USE_GPU else ['CPUExecutionProvider'])
        app = FaceAnalysis(name=FACE_MODEL, providers=providers,
                           allowed_modules=['detection', 'recognition'])
        app.prepare(ctx_id=0, det_size=(640, 640))
        # quel provider a réellement été retenu ?
        try:
            used = app.models['detection'].session.get_providers()
            FACE_PROVIDER = 'GPU' if any('CUDA' in p for p in used) else 'CPU'
        except Exception:
            FACE_PROVIDER = '?'
        FACE_APP = app
        print(f"  ✓ Reconnaissance de visages prête — {FACE_MODEL} ({FACE_PROVIDER})")
    except Exception as e:
        FACE_ERROR = str(e)[:200]
        FACE_APP = None
        print(f"  ⚠ Reconnaissance de visages indisponible : {FACE_ERROR}")
        print("     → Lance « 7 - Installer reconnaissance visages.bat » "
              "(insightface + onnxruntime-gpu).")
    return FACE_APP


class ImageReadError(OSError):
    """Lecture des octets d'une image impossible (I/O disque/SMB), à distinguer
    d'un échec de décodage (fichier réellement corrompu). Transitoire par nature
    — ex. « [Errno 22] Invalid argument » renvoyé par un partage SMB sous charge
    concurrente (recensement + workers). Mérite un retry et ne doit PAS poisonner
    l'index de façon permanente."""


def _read_bytes_retry(path, tries=3, pause=0.4):
    """Lit tout le fichier en mémoire, en réessayant sur erreur d'I/O. Le partage
    SMB renvoie par intermittence EINVAL sous charge (recensement + workers) ; un
    simple retour arrière suffit presque toujours. Une fois les octets en RAM, le
    décodage PIL est fiable — vérifié : la copie locale d'un fichier qui échoue
    via SMB se décode sans faute."""
    last = None
    for i in range(tries):
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError as e:
            last = e
            if i + 1 < tries:
                time.sleep(pause * (i + 1))
    raise ImageReadError(str(last)) from last


def _is_transient_io_fail(entry):
    """Une entrée `failed` due à une lecture SMB transitoire (Errno 22) mérite une
    nouvelle passe, contrairement à un vrai fichier corrompu — qui, lui, reste
    `failed` (le décodage se fait désormais en mémoire, il ne peut plus échouer
    pour une raison d'I/O)."""
    if not isinstance(entry, dict) or not entry.get('failed'):
        return False
    err = entry.get('error') or ''
    return 'Invalid argument' in err or 'Errno 22' in err


def _load_bgr(path, max_side=None):
    """Charge une image en tableau numpy BGR (format attendu par InsightFace).
    max_side : côté max de redimensionnement (0/None = pleine résolution).
    Renvoie (array, scale) pour repasser les coordonnées à l'échelle d'origine.

    Les octets sont lus via `_read_bytes_retry` (résilient au hoquet SMB) puis
    décodés depuis la mémoire : une lecture SMB fautive lève `ImageReadError`
    (transitoire, à retenter), un vrai fichier corrompu lève une erreur PIL
    (permanente)."""
    import io
    import numpy as np
    if not PIL_OK:
        raise RuntimeError("Pillow requis")
    if max_side is None:
        max_side = FACE_MAX_SIDE
    data = _read_bytes_retry(path)
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        w0, h0 = im.size
        if max_side and max_side > 0:
            im.thumbnail((max_side, max_side))
        w1 = im.size[0]
        scale = w0 / w1 if w1 else 1.0
        arr = np.asarray(im)[:, :, ::-1].copy()   # RGB -> BGR
    return arr, scale


FACE_APP_GPU = None
FACE_GPU_INIT = False
FACE_GPU_ERROR = ""
FACE_LAST_ENGINE = ""


def get_face_app_gpu():
    """Instance InsightFace sur GPU (CUDA), initialisée à la demande la première
    fois qu'il y a assez de VRAM libre. Réutilise les DLL CUDA/cuDNN fournies par
    PyTorch (installé via « 8 - Activer GPU (PyTorch CUDA).bat »)."""
    global FACE_APP_GPU, FACE_GPU_INIT, FACE_GPU_ERROR
    if FACE_GPU_INIT:
        return FACE_APP_GPU
    FACE_GPU_INIT = True
    try:
        try:
            import torch  # noqa: F401  → charge les DLL CUDA/cuDNN de PyTorch
        except Exception:
            pass
        try:
            import onnxruntime as _ort
            if hasattr(_ort, 'preload_dlls'):
                _ort.preload_dlls()
        except Exception:
            pass
        from insightface.app import FaceAnalysis
        provs = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        popts = [{'gpu_mem_limit': FACE_GPU_MEM_LIMIT_MB * 1024 * 1024,
                  'arena_extend_strategy': 'kSameAsRequested'}, {}]
        try:
            app = FaceAnalysis(name=FACE_MODEL, providers=provs, provider_options=popts,
                               allowed_modules=['detection', 'recognition'])
        except TypeError:
            app = FaceAnalysis(name=FACE_MODEL, providers=provs,
                               allowed_modules=['detection', 'recognition'])
        app.prepare(ctx_id=0, det_size=(640, 640))
        used = []
        try:
            used = app.models['detection'].session.get_providers()
        except Exception:
            pass
        if not any('CUDA' in p for p in used):
            FACE_GPU_ERROR = "CUDA non actif (DLL/pilote ?)"
            FACE_APP_GPU = None
            print(f"  ⚠ GPU visages : {FACE_GPU_ERROR} — reste sur CPU")
        else:
            FACE_APP_GPU = app
            print("  🚀 InsightFace GPU prêt (CUDA) — bascule adaptative activée")
    except Exception as e:
        FACE_GPU_ERROR = str(e)[:200]
        FACE_APP_GPU = None
        print(f"  ⚠ GPU visages indisponible : {FACE_GPU_ERROR}")
    return FACE_APP_GPU


FACE_DEV_LOCK = threading.Lock()   # tenu pendant l'inférence GPU visages


def _liberer_gpu_visages():
    """Éviction : jette la session InsightFace GPU (une session onnxruntime ne
    migre pas, on la détruit ; elle se reconstruira au prochain bail accordé).
    False si une inférence est en vol — on n'interrompt jamais un calcul."""
    global FACE_APP_GPU, FACE_GPU_INIT
    if not FACE_DEV_LOCK.acquire(blocking=False):
        return False
    try:
        if FACE_APP_GPU is not None:
            FACE_APP_GPU = None
            FACE_GPU_INIT = False      # ré-init possible au prochain bail
            try:
                import gc
                gc.collect()           # libère la session ORT (et sa VRAM)
            except Exception:
                pass
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
        return True
    finally:
        FACE_DEV_LOCK.release()


def pick_app():
    """Choisit CPU ou GPU pour l'analyse des visages. La décision passe par
    l'arbitre (bail 'visages') quand il existe : un seul point de vérité sur
    la VRAM, Ollama (hors bail) garde de fait la priorité. Sans arbitre :
    l'ancienne sonde directe."""
    if FACE_GPU_ENABLE:
        if GPU is not None:
            GPU.menage(sauf='visages')
            ok = GPU.demander('visages', FACE_GPU_MIN_FREE_MB)
        else:
            g = hw_state().get("gpu")
            ok = bool(g and g.get("vram_free_mb", 0) >= FACE_GPU_MIN_FREE_MB)
        if ok:
            # L'init (plusieurs secondes de session ORT) se fait SOUS le
            # verrou : sinon le libérateur d'éviction voit FACE_APP_GPU=None
            # pendant l'init, « réussit » sans rien libérer, et la session
            # finit résidente sans bail (600 Mo zombies). Le verrou ferme
            # aussi la course check-then-act sur FACE_GPU_INIT (double init).
            with FACE_DEV_LOCK:
                a = get_face_app_gpu()
                if a is not None:
                    if GPU is not None:
                        GPU.confirmer('visages')
                    return a, "GPU"
                if GPU is not None:    # init GPU ratée → on rend le bail
                    GPU.rendre('visages')
    return get_face_app(), "CPU"


def detect_faces(path, max_side=None):
    """Détecte les visages d'une photo. Retourne une liste :
    [{bbox:[x1,y1,x2,y2] (échelle d'origine), det_score, emb:<b64 float16>}].
    Les visages sous FACE_DET_THRESHOLD sont ignorés (flous, de profil…).
    Choisit CPU/GPU dynamiquement (pick_app)."""
    global FACE_LAST_ENGINE
    app, eng = pick_app()
    if app is None:
        raise RuntimeError("moteur visages indisponible")
    FACE_LAST_ENGINE = eng
    arr, scale = _load_bgr(path, max_side)
    out = []
    if eng == "GPU":
        # Le verrou signale « inférence en vol » au libérateur d'éviction :
        # la session GPU ne peut pas être détruite sous nos pieds. Si une
        # éviction est passée entre pick_app et ici, la session référencée
        # n'est plus la session courante → on bascule sur CPU plutôt que de
        # calculer sur une session dont l'arbitre a déjà « rendu » la VRAM.
        with FACE_DEV_LOCK:
            if FACE_APP_GPU is not app:
                app, eng = get_face_app(), "CPU"
                FACE_LAST_ENGINE = eng
                if app is None:
                    raise RuntimeError("moteur visages indisponible")
            faces = app.get(arr)
    else:
        faces = app.get(arr)
    for f in faces:
        score = float(getattr(f, 'det_score', 0.0))
        if score < FACE_DET_THRESHOLD:
            continue
        emb = getattr(f, 'normed_embedding', None)
        if emb is None:
            continue
        b = [int(round(v * scale)) for v in f.bbox]
        out.append({
            "bbox": b,
            "det_score": round(score, 3),
            "emb": base64.b64encode(emb.astype('float16').tobytes()).decode(),
        })
    return out


if GPU is not None:
    GPU.enregistrer('visages', liberer=_liberer_gpu_visages)


def enqueue_face(name):
    with FACE_PENDING_LOCK:
        if name in FACE_PENDING:
            return
        FACE_PENDING.add(name)
    FACE_QUEUE.put(name)


def face_worker():
    """Thread unique (évite la contention GPU) : détecte les visages des
    photos en file et écrit le résultat dans faces_index.json.

    Une lecture SMB transitoire (`ImageReadError`) n'est PAS écrite comme un
    échec permanent : elle est remise en file un nombre borné de fois, puis, si
    elle persiste, laissée pour un prochain balayage. Seul un vrai échec de
    décodage écrit `failed`."""
    io_retries = {}
    while True:
        name = FACE_QUEUE.get()
        requeue = False
        try:
            path = _resolve_key(name)
            if (not path.exists() or _is_hidden_path(path)
                    or FACE_STORE.has(name)):
                continue
            # Sous l'ordonnanceur (audit I1) : POIDS_FOND déclare `visages`
            # mais la boucle consommait sa file sans garde — la promesse
            # « un seul travail lourd à la fois » ne couvrait pas la boucle
            # la plus lourde, et ORDO.etat() affichait `visages: 0` à jamais.
            # Pas de tour disponible → la photo repart en file (finally).
            with creneau('visages', timeout=180) as ok:
                if not ok:
                    requeue = True
                    continue
                faces = detect_faces(path)
            FACE_STORE.set(name, {"faces": faces, "n": len(faces),
                                  "at": time.time()})
            io_retries.pop(name, None)
            if faces:
                print(f"  🙂 {len(faces)} visage(s) : {name}")
        except ImageReadError as e:
            n = io_retries.get(name, 0) + 1
            if n <= 3:
                io_retries[name] = n
                requeue = True
                print(f"  ~ Visages {name} : lecture SMB KO ({e}) — "
                      f"nouvel essai {n}/3")
                time.sleep(1.0 * n)
            else:
                io_retries.pop(name, None)
                print(f"  ⚠ Visages {name} : lecture SMB toujours KO après "
                      f"3 essais — laissé pour un prochain balayage")
        except Exception as e:
            FACE_STORE.set(name, {"failed": True, "error": str(e)[:200],
                                  "at": time.time()})
            print(f"  ⚠ Visages {name} : {e}")
        finally:
            with FACE_PENDING_LOCK:
                FACE_PENDING.discard(name)
            FACE_QUEUE.task_done()
            if requeue:
                enqueue_face(name)


def face_scan_loop():
    """Balaye périodiquement l'index des photos taguées et met en file celles
    qui n'ont pas encore été analysées pour les visages. S'arrête d'elle-même
    si le moteur est indisponible (dépendances absentes)."""
    time.sleep(12)  # laisse le serveur démarrer
    if get_face_app() is None:
        return
    while True:
        try:
            queued = 0
            for k, e in list(STORE.data.items()):
                if not isinstance(e, dict) or e.get('failed'):
                    continue
                fe = FACE_STORE.get(k)
                if fe is not None and not _is_transient_io_fail(fe):
                    continue
                p = _resolve_key(k)
                if p.suffix.lower() in IMAGE_EXT:
                    enqueue_face(k)
                    queued += 1
            if queued:
                print(f"  🙂 Balayage visages : {queued} photo(s) en file")
        except Exception as e:
            print(f"  ⚠ Balayage visages : {e}")
        time.sleep(FACE_SCAN_INTERVAL)


# ══════════════════ Reconnaissance des animaux — Phase 1 ══════════════════
# Détection d'animaux (chat/chien/oiseau…) via YOLO. Chaîne indépendante des
# visages : elle écrit les boîtes détectées dans animals_index.json. Le nommage
# individuel des chats (Caline, Inti, Luna) arrivera en Phase 2 (embeddings).

YOLO_MODEL = None
YOLO_INIT_DONE = False
YOLO_ERROR = ""


def get_yolo():
    """Charge le modèle YOLO une seule fois (paresseux). Renvoie None et
    désactive proprement la détection animaux si Ultralytics n'est pas installé
    — le serveur continue de tourner (comme pour les visages)."""
    global YOLO_MODEL, YOLO_INIT_DONE, YOLO_ERROR
    if YOLO_INIT_DONE:
        return YOLO_MODEL
    YOLO_INIT_DONE = True
    try:
        from ultralytics import YOLO
        weights = SCRIPT_DIR / ANIMAL_YOLO_WEIGHTS
        src = str(weights) if weights.exists() else ANIMAL_YOLO_WEIGHTS
        YOLO_MODEL = YOLO(src)   # télécharge les poids au 1er lancement si absents
        print(f"  ✓ Détection d'animaux prête — {ANIMAL_YOLO_WEIGHTS} ({ANIMAL_DEVICE})")
    except Exception as e:
        YOLO_ERROR = str(e)[:200]
        YOLO_MODEL = None
        print(f"  ⚠ Détection d'animaux indisponible : {YOLO_ERROR}")
        print("     → Lance « 9 - Installer reconnaissance animaux.bat » (ultralytics).")
    return YOLO_MODEL


def _pick_gpu_device(enable, min_free_mb, fallback='cpu', nom=None):
    """Renvoie 'cuda' si le GPU a assez de VRAM libre (Ollama au repos), sinon
    'cpu'. Avec l'arbitre (`nom` fourni) : la décision passe par un bail —
    un seul point de vérité, plus de sondes concurrentes qui se croient
    seules. Sans arbitre : sonde directe, hw_state() en cache ~8 s."""
    if not enable:
        return fallback
    if GPU is not None and nom:
        GPU.menage(sauf=nom)
        return 'cuda' if GPU.demander(nom, min_free_mb) else fallback
    try:
        g = hw_state().get("gpu")
        if g and g.get("vram_free_mb", 0) >= min_free_mb:
            return 'cuda'
    except Exception:
        pass
    return fallback


ANIMAL_LAST_DEVICE = "cpu"
ANIMAL_DEV_LOCK = threading.Lock()   # tenu pendant predict → éviction sûre


def _liberer_gpu_animaux():
    """Éviction : descend YOLO sur CPU. False si une détection est en vol."""
    global ANIMAL_LAST_DEVICE
    if not ANIMAL_DEV_LOCK.acquire(blocking=False):
        return False
    try:
        m = YOLO_MODEL
        if m is not None and ANIMAL_LAST_DEVICE == 'cuda':
            try:
                m.to('cpu')
            except Exception:
                return False
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
        ANIMAL_LAST_DEVICE = 'cpu'
        return True
    finally:
        ANIMAL_DEV_LOCK.release()


if GPU is not None:
    GPU.enregistrer('animaux', liberer=_liberer_gpu_animaux)


def detect_animals(path, max_side=None):
    """Détecte les animaux d'une photo. Retourne une liste :
    [{bbox:[x1,y1,x2,y2] (échelle d'origine), det_score, species}].
    Seules les classes de ANIMAL_CLASSES sont retenues, au-dessus du seuil."""
    global ANIMAL_LAST_DEVICE
    model = get_yolo()
    if model is None:
        raise RuntimeError("moteur animaux indisponible")
    if max_side is None:
        max_side = ANIMAL_MAX_SIDE
    arr, scale = _load_bgr(path, max_side)   # numpy BGR, comme pour les visages
    out = []
    # Le verrou signale « détection en vol » au libérateur d'éviction. La
    # décision est prise SOUS le verrou : hors verrou, une éviction pouvait
    # passer entre la décision et le predict — YOLO remontait alors en VRAM
    # sans bail (invisible, inévincable) pendant que le bénéficiaire de
    # l'éviction montait dans l'espace « libéré ». Sûr : les libérateurs font
    # un acquire non-bloquant, ils échouent proprement pendant qu'on décide.
    with ANIMAL_DEV_LOCK:
        dev = _pick_gpu_device(ANIMAL_GPU_ENABLE, ANIMAL_GPU_MIN_FREE_MB,
                               ANIMAL_DEVICE, nom='animaux')
        ANIMAL_LAST_DEVICE = dev
        try:
            results = model.predict(arr, conf=ANIMAL_DET_THRESHOLD,
                                    classes=list(ANIMAL_CLASSES.keys()),
                                    device=dev, verbose=False)
            if dev == 'cuda' and GPU is not None:
                GPU.confirmer('animaux')   # le modèle réside désormais en VRAM
        except Exception:
            # repli CPU si le GPU refuse (VRAM insuffisante, driver…)
            ANIMAL_LAST_DEVICE = 'cpu'
            if dev == 'cuda' and GPU is not None:
                GPU.rendre('animaux')
            results = model.predict(arr, conf=ANIMAL_DET_THRESHOLD,
                                    classes=list(ANIMAL_CLASSES.keys()),
                                    device='cpu', verbose=False)
    for r in results:
        boxes = getattr(r, 'boxes', None)
        if boxes is None:
            continue
        for box in boxes:
            cls = int(box.cls[0])
            species = ANIMAL_CLASSES.get(cls)
            if not species:
                continue
            score = float(box.conf[0])
            xy = [float(v) for v in box.xyxy[0].tolist()]
            b = [int(round(v * scale)) for v in xy]
            out.append({"bbox": b, "det_score": round(score, 3),
                        "species": species})
    return out


def enqueue_animal(name):
    with ANIMAL_PENDING_LOCK:
        if name in ANIMAL_PENDING:
            return
        ANIMAL_PENDING.add(name)
    ANIMAL_QUEUE.put(name)


def animal_worker():
    """Thread unique : détecte les animaux des photos en file et écrit le
    résultat dans animals_index.json.

    Même politique que `face_worker` : une lecture SMB transitoire
    (`ImageReadError`) est retentée un nombre borné de fois sans écrire `failed`,
    pour ne pas exclure définitivement une photo saine d'un simple hoquet réseau."""
    io_retries = {}
    while True:
        name = ANIMAL_QUEUE.get()
        requeue = False
        try:
            path = _resolve_key(name)
            if (not path.exists() or _is_hidden_path(path)
                    or ANIMAL_STORE.has(name)):
                continue
            # Sous l'ordonnanceur (audit I1) — même raison que face_worker.
            with creneau('animaux', timeout=180) as ok:
                if not ok:
                    requeue = True
                    continue
                animals = detect_animals(path)
            ANIMAL_STORE.set(name, {"animals": animals, "n": len(animals),
                                    "at": time.time()})
            io_retries.pop(name, None)
            if animals:
                sp = ", ".join(sorted({a["species"] for a in animals}))
                print(f"  🐾 {len(animals)} animal(aux) [{sp}] : {name}")
        except ImageReadError as e:
            n = io_retries.get(name, 0) + 1
            if n <= 3:
                io_retries[name] = n
                requeue = True
                print(f"  ~ Animaux {name} : lecture SMB KO ({e}) — "
                      f"nouvel essai {n}/3")
                time.sleep(1.0 * n)
            else:
                io_retries.pop(name, None)
                print(f"  ⚠ Animaux {name} : lecture SMB toujours KO après "
                      f"3 essais — laissé pour un prochain balayage")
        except Exception as e:
            ANIMAL_STORE.set(name, {"failed": True, "error": str(e)[:200],
                                    "at": time.time()})
            print(f"  ⚠ Animaux {name} : {e}")
        finally:
            with ANIMAL_PENDING_LOCK:
                ANIMAL_PENDING.discard(name)
            ANIMAL_QUEUE.task_done()
            if requeue:
                enqueue_animal(name)


def animal_scan_loop():
    """Balaye périodiquement l'index des photos taguées et met en file celles
    pas encore analysées pour les animaux. S'arrête si le moteur est absent."""
    time.sleep(15)   # laisse le serveur démarrer (après les visages)
    if get_yolo() is None:
        return
    while True:
        try:
            queued = 0
            for k, e in list(STORE.data.items()):
                if not isinstance(e, dict) or e.get('failed'):
                    continue
                ae = ANIMAL_STORE.get(k)
                if ae is not None and not _is_transient_io_fail(ae):
                    continue
                p = _resolve_key(k)
                if p.suffix.lower() in IMAGE_EXT:
                    enqueue_animal(k)
                    queued += 1
            if queued:
                print(f"  🐾 Balayage animaux : {queued} photo(s) en file")
        except Exception as e:
            print(f"  ⚠ Balayage animaux : {e}")
        time.sleep(ANIMAL_SCAN_INTERVAL)


# ═══════════ Reconnaissance des chats — Phase 2 : embeddings + nommage ═══════════
# On calcule un vecteur visuel (DINOv2) par chat détecté, on regroupe les chats
# qui se ressemblent, tu nommes les groupes (Caline / Inti / Luna), puis chaque
# nouveau chat est rattaché au plus proche. Réutilise les briques génériques des
# visages (cluster_faces, _emb_from_b64, écriture des tags).

DINO_MODEL_OBJ = None
DINO_TF = None
DINO_INIT_DONE = False
DINO_ERROR = ""
DINO_CUR_DEVICE = DINO_DEVICE   # device courant du modèle DINOv2 (CPU/GPU adaptatif)


def get_dino():
    """Charge DINOv2 (via timm) une seule fois. Renvoie (modèle, transform) ou
    (None, None) si indisponible — le reste du serveur continue de tourner."""
    global DINO_MODEL_OBJ, DINO_TF, DINO_INIT_DONE, DINO_ERROR
    if DINO_INIT_DONE:
        return DINO_MODEL_OBJ, DINO_TF
    DINO_INIT_DONE = True
    try:
        import timm, torch
        m = timm.create_model(DINO_MODEL, pretrained=True, num_classes=0)
        m.eval()
        try:
            m.to(DINO_DEVICE)
        except Exception:
            pass
        cfg = timm.data.resolve_data_config({}, model=m)
        DINO_TF = timm.data.create_transform(**cfg)
        DINO_MODEL_OBJ = m
        print(f"  ✓ Embeddings chats prêts — DINOv2 ({DINO_DEVICE})")
    except Exception as e:
        DINO_ERROR = str(e)[:200]
        DINO_MODEL_OBJ = None
        print(f"  ⚠ Embeddings chats indisponibles : {DINO_ERROR}")
        print("     → Lance « 10 - Installer nommage des chats.bat » (timm).")
    return DINO_MODEL_OBJ, DINO_TF


PET_DEV_LOCK = threading.Lock()    # tenu pendant migration+forward DINOv2


def _dino_target_device():
    return _pick_gpu_device(PET_GPU_ENABLE, PET_GPU_MIN_FREE_MB, DINO_DEVICE,
                            nom='empreintes_chats')


def _liberer_gpu_dino():
    """Éviction : descend DINOv2 sur CPU. False si un embedding est en vol."""
    global DINO_CUR_DEVICE
    if not PET_DEV_LOCK.acquire(blocking=False):
        return False
    try:
        if DINO_MODEL_OBJ is not None and DINO_CUR_DEVICE == 'cuda':
            try:
                DINO_MODEL_OBJ.to('cpu')
            except Exception:
                return False
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
        DINO_CUR_DEVICE = 'cpu'
        return True
    finally:
        PET_DEV_LOCK.release()


if GPU is not None:
    GPU.enregistrer('empreintes_chats', liberer=_liberer_gpu_dino)


def _embed_pil(im_crop):
    """Vecteur normalisé (float32) d'une découpe PIL, ou None. GPU adaptatif :
    on ne déplace le modèle (opération coûteuse) que si la décision VRAM change."""
    global DINO_CUR_DEVICE
    model, tf = get_dino()
    if model is None:
        return None
    import torch, numpy as np
    # Le verrou couvre migration + forward : le libérateur d'éviction ne peut
    # pas descendre le modèle pendant qu'on calcule dessus.
    with PET_DEV_LOCK:
        dev = _dino_target_device()
        if dev != DINO_CUR_DEVICE:
            try:
                model.to(dev)
                DINO_CUR_DEVICE = dev
                if GPU is not None:
                    if dev == 'cuda':
                        GPU.confirmer('empreintes_chats')
                    else:
                        GPU.rendre('empreintes_chats')
            except Exception:
                if dev == 'cuda' and GPU is not None:
                    GPU.rendre('empreintes_chats')   # bail promis, non monté
                dev = DINO_CUR_DEVICE     # échec (VRAM ?) → on reste où on est
        x = tf(im_crop.convert("RGB")).unsqueeze(0)
        try:
            x = x.to(DINO_CUR_DEVICE)
        except Exception:
            pass
        try:
            with torch.no_grad():
                feat = model(x)
        except Exception:
            # repli CPU si le GPU refuse en cours de route
            if DINO_CUR_DEVICE != 'cpu':
                try:
                    model.to('cpu')
                    DINO_CUR_DEVICE = 'cpu'
                    if GPU is not None:
                        GPU.rendre('empreintes_chats')
                    with torch.no_grad():
                        feat = model(x.to('cpu'))
                except Exception:
                    return None
            else:
                return None
    v = feat[0].float().cpu().numpy()
    nn = float(np.linalg.norm(v))
    return v / nn if nn else v


def _emb_to_b64(v):
    import numpy as np
    return base64.b64encode(v.astype('float16').tobytes()).decode()


def embed_cats_one_batch():
    """Calcule les embeddings manquants des chats détectés, un lot à la fois.
    Charge chaque photo une seule fois (plusieurs chats → une seule lecture)."""
    if get_dino()[0] is None:
        return 0
    done = 0
    for k, e in list(ANIMAL_STORE.data.items()):
        if not isinstance(e, dict) or e.get('failed'):
            continue
        animals = e.get('animals') or []
        todo = [a for a in animals
                if _nommable(a) and not a.get('emb')]
        if not todo:
            continue
        p = _resolve_key(k)
        try:
            if not p.is_file():
                continue
        except OSError:
            continue
        try:
            with Image.open(p) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                w, h = im.size
                changed = False
                for a in todo:
                    x1, y1, x2, y2 = a.get('bbox', [0, 0, 0, 0])
                    box = (max(0, int(x1)), max(0, int(y1)),
                           min(w, int(x2)), min(h, int(y2)))
                    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
                        a['emb'] = ''      # boîte inexploitable → marque vide
                        changed = True
                        continue
                    v = _embed_pil(im.crop(box))
                    if v is not None:
                        a['emb'] = _emb_to_b64(v)
                        changed = True
                        done += 1
                        PET_EMBED_STATE["done"] += 1
            if changed:
                ANIMAL_STORE.set(k, e)
        except Exception as ex:
            print(f"  ⚠ embed chat {k} : {ex}")
        if done >= PET_EMBED_BATCH or system_busy() or ui_recent():
            break
    return done


def pet_embed_loop():
    """Calcule en fond les embeddings des chats, quand la machine est au calme."""
    time.sleep(90)
    if get_dino()[0] is None:
        return
    while True:
        try:
            # On calcule les empreintes dès que la DÉTECTION est finie, même si le
            # tagging IA tourne encore (sinon, avec 30 000 photos à re-taguer, la
            # file de tagging n'est jamais vide et les empreintes ne se font
            # JAMAIS). DINOv2 est adaptatif GPU→CPU : pas de conflit VRAM avec
            # Ollama. On cède seulement quand tu navigues.
            if ui_recent():
                time.sleep(5)
                continue
            if not ANIMAL_QUEUE.empty():
                time.sleep(15)      # la détection passe d'abord
                continue
            with creneau('empreintes_chats', timeout=180) as ok:
                did = embed_cats_one_batch() if ok else 0
            time.sleep(2 if did else 120)
        except Exception as e:
            print(f"  ⚠ Embeddings chats : {e}")
            time.sleep(30)


def _animal_crop_url(key, i):
    return '/api/animalcrop?key=' + urllib.parse.quote(key, safe='') + '&i=' + str(i)


def _assigned_face_set(store):
    """Ensemble des (clé, index) déjà attribués à un nom dans `store`
    (people.json ou pets.json). Sert à EXCLURE définitivement ces visages/chats
    du regroupement « à nommer » : une fois nommé, un groupe ne réapparaît plus,
    même après « Recalculer » ou si les références étaient plafonnées."""
    s = set()
    for pe in store.data.values():
        if not isinstance(pe, dict):
            continue
        for kf in (pe.get('faces') or []):
            if isinstance(kf, (list, tuple)) and len(kf) == 2:
                try:
                    s.add((kf[0], int(kf[1])))
                except (ValueError, TypeError):
                    continue
    return s


def _merge_assigned(existing, members, cap=6000):
    """Fusionne (sans doublon) la liste [[clé, index], …] déjà attribuée avec les
    membres d'un groupe qu'on vient de nommer."""
    out = list(existing or [])
    seen = {(x[0], x[1]) for x in out if isinstance(x, (list, tuple)) and len(x) == 2}
    for (k, i) in members:
        if (k, i) not in seen:
            out.append([k, i])
            seen.add((k, i))
    return out[-cap:]


def _gather_cats(espece=None):
    """Animaux nommables embarqués : (vecteurs normalisés, méta (clé, index)).

    `espece` restreint à une espèce : un chien et un chat ne doivent jamais
    tomber dans le même groupe, quelle que soit la proximité de leurs
    empreintes. Exclut les animaux déjà attribués à un nom.
    """
    assigned = _assigned_face_set(PETS_STORE)
    vecs, meta = [], []
    dim = None
    for k, e in list(ANIMAL_STORE.data.items()):
        if not isinstance(e, dict) or e.get('failed'):
            continue
        for i, a in enumerate(e.get('animals') or []):
            if not _meme_espece(a, espece):
                continue
            if (k, i) in assigned:
                continue
            emb = a.get('emb')
            if not emb:
                continue
            try:
                v = _emb_from_b64(emb)
            except Exception:
                continue
            # sécurité : n'accepte qu'une seule dimension (après changement de
            # modèle DINOv2, d'anciennes empreintes d'autre dimension traînent).
            if dim is None:
                dim = v.shape[0]
            elif v.shape[0] != dim:
                continue
            vecs.append(v)
            meta.append((k, i))
    return vecs, meta


def _filter_known_cats(vecs, meta):
    """Écarte les chats déjà attribués à un chat nommé (>= PET_MATCH_SIM)."""
    import numpy as np
    refs, owners = [], []
    for pk, pe in PETS_STORE.data.items():
        if not isinstance(pe, dict):
            continue
        for s in (pe.get('refs') or []):
            try:
                refs.append(_emb_from_b64(s))
                owners.append(pk)
            except Exception:
                continue
    if not refs or not vecs:
        return vecs, meta
    E = np.stack(vecs)
    # ne garde que les références de MÊME dimension que les empreintes courantes
    # (après changement de modèle, les anciennes réf. sont incompatibles).
    refs = [r for r in refs if r.shape[0] == E.shape[1]]
    if not refs:
        return vecs, meta
    R = np.stack(refs)
    keep_v, keep_m = [], []
    S = E @ R.T
    mx = S.max(axis=1)
    for r in range(E.shape[0]):
        if mx[r] < PET_MATCH_SIM:
            keep_v.append(vecs[r])
            keep_m.append(meta[r])
    return keep_v, keep_m


def build_pet_clusters():
    """Recalcule les groupes de chats (tâche de fond, mise en cache)."""
    with PET_CLUSTER_LOCK:
        if PET_CLUSTER_CACHE["building"]:
            return
        PET_CLUSTER_CACHE["building"] = True
    try:
        try:
            import numpy  # noqa: F401
        except Exception as e:
            print(f"  ⚠ Regroupement chats impossible (numpy absent) : {e}")
            return
        # Un regroupement PAR ESPÈCE : mélanger chiens et chats dans le même
        # calcul produit des groupes hétérogènes que rien ne permet de nommer.
        light, byid = [], {}
        for espece in sorted(ANIMAL_NAMEABLE):
            vecs, meta = _gather_cats(espece)
            if not vecs:
                continue
            n_all = len(vecs)
            vecs, meta = _filter_known_cats(vecs, meta)
            if not vecs:
                continue
            print(f"  🐾 {espece} : regroupement de {len(vecs)} inconnu(s) "
                  f"({n_all - len(vecs)} déjà nommé(s), ignoré(s))…")
            clusters = cluster_faces(vecs, meta, PET_CLUSTER_SIM,
                                     PET_MIN_CLUSTER)
            for c in clusters:
                cid = f"{espece}:{len(light)}"
                members = c["members"]
                # « membres » accompagne les vignettes : c'est ce qui permet
                # à l'interface d'attribuer un SOUS-ENSEMBLE du groupe.
                light.append({"cid": cid, "size": c["size"], "species": espece,
                              "membres": [[k, i] for (k, i) in members[:18]],
                              "crops": [_animal_crop_url(k, i)
                                        for (k, i) in members[:18]]})
                byid[cid] = members
        with PET_CLUSTER_LOCK:
            PET_CLUSTER_CACHE["clusters"] = light
            PET_CLUSTER_CACHE["byid"] = byid
            PET_CLUSTER_CACHE["at"] = time.time()
        print(f"  ✓ {len(light)} groupe(s) d'animaux trouvé(s)")
    finally:
        with PET_CLUSTER_LOCK:
            PET_CLUSTER_CACHE["building"] = False


def find_more_cats(name, limit=300):
    """Propose d'autres photos d'un animal nommé : voir SubjectStore.find_more.
    Applique désormais AUSSI `exclude` (une photo corrigée ne revient plus)."""
    return PETS.find_more(name, limit)


def confirm_cat(name, keys):
    """Valide l'attribution de photos à un animal : voir SubjectStore.confirm."""
    return PETS.confirm(name, keys)


def pets_list():
    """Chats nommés avec nombre de photos et une vignette."""
    tagcount = {}
    for e in STORE.data.values():
        if not isinstance(e, dict):
            continue
        for kw in (e.get('kw_fr') or []):
            if str(kw).lower().startswith('animal:'):
                key = str(kw)[7:].strip().lower()
                tagcount[key] = tagcount.get(key, 0) + 1
    out = []
    for pk, pe in PETS_STORE.data.items():
        if not isinstance(pe, dict):
            continue
        nm = pe.get('name', pk)
        crop = None
        for k, e in ANIMAL_STORE.data.items():
            if not _kw_has(STORE.data.get(k), f"animal:{nm}"):
                continue
            animals = e.get('animals') if isinstance(e, dict) else None
            if animals:
                for i, a in enumerate(animals):
                    if _nommable(a):
                        crop = _animal_crop_url(k, i)
                        break
            if crop:
                break
        # `contestes` : les jugements perdus que la fiche garde en mémoire —
        # comptés ici pour que la carte le DISE (chantier 17, étape 2).
        out.append({"name": nm, "photos": tagcount.get(nm.strip().lower(), 0),
                    "crop": crop,
                    "contestes": len(_auteurs.contestations(pe))})
    out.sort(key=lambda x: -x["photos"])
    return out


ANIMAL_VER_FILE = SCRIPT_DIR / "animal_pipeline.ver"


def migrate_animal_pipeline():
    """Si le pipeline animaux a changé (détecteur YOLO, seuil, modèle d'empreinte),
    on relance détection + empreintes : on VIDE animals_index.json (re-détection
    avec le nouveau modèle) et on efface les références des chats (dimension
    d'empreinte incompatible). Les NOMS (tags animal:… dans l'index et les
    fichiers) sont PRÉSERVÉS ; les références sont re-dérivées ensuite depuis les
    tags (rederive_pet_refs). Tourne une fois, au démarrage, avant les workers."""
    try:
        cur = ANIMAL_VER_FILE.read_text(encoding='utf-8').strip()
    except Exception:
        cur = ""
    if cur == ANIMAL_PIPELINE_VERSION:
        return
    n = len(ANIMAL_STORE.data)
    with ANIMAL_STORE.lock:
        ANIMAL_STORE.data = {}
        ANIMAL_STORE._save()
    with PETS_STORE.lock:
        for pk, pe in PETS_STORE.data.items():
            if isinstance(pe, dict):
                pe['refs'] = []
                pe['faces'] = []        # indices (clé,i) devenus caducs
                pe['need_refs'] = 1
        PETS_STORE._save()
    try:
        ANIMAL_VER_FILE.write_text(ANIMAL_PIPELINE_VERSION, encoding='utf-8')
    except Exception:
        pass
    print(f"  ♻ Migration pipeline animaux → {ANIMAL_PIPELINE_VERSION}")
    print(f"     {n} détection(s) à refaire (yolo11s) + empreintes (DINOv2 base) — "
          f"les noms sont conservés, ça se reconstruit en tâche de fond.")


def rederive_pet_refs():
    """Reconstruit les références (empreintes moyennes) de chaque chat nommé à
    partir de ses photos DÉJÀ taguées, avec le nouveau modèle d'empreinte. Se
    base sur les tags (préservés), pas sur des indices. Tourne en fond jusqu'à ce
    que chaque chat ait de nouveau des références."""
    time.sleep(90)
    while True:
        did = pending = 0
        for pk, pe in list(PETS_STORE.data.items()):
            if not isinstance(pe, dict) or pe.get('refs'):
                continue
            nm = pe.get('name')
            if not nm:
                continue
            tag = f"animal:{nm}"
            refs = []
            for k, e in list(STORE.data.items()):
                if not _kw_has(e, tag):
                    continue
                ae = ANIMAL_STORE.data.get(k)
                if not isinstance(ae, dict):
                    continue
                for a in (ae.get('animals') or []):
                    if _nommable(a) and a.get('emb'):
                        refs.append(a['emb'])
                        if len(refs) >= 80:
                            break
                if len(refs) >= 80:
                    break
            if refs:
                pe['refs'] = refs
                pe.pop('need_refs', None)
                PETS_STORE.set(pk, pe)
                did += 1
                print(f"  ✓ Références recalculées : {nm} ({len(refs)})")
            else:
                pending += 1
        time.sleep(120 if (did or pending) else 600)


# ── Curateur animaux (onglet Classification de /sujets) ──
# Miroir du curateur des personnes : les rattachements auto restent silencieux
# et conservateurs (_cat_auto_pass), mais ils sont désormais JOURNALISÉS
# (bande « ajoutés automatiquement », annulable), et les cas proches du seuil
# deviennent des propositions « Ajouter à X ? » à juger — file par MARGE
# croissante, jamais par score absolu (même règle anti-circularité).
CAT_AUTO_LOG_MAX = 500
CAT_AUTO_LOG = []             # journal réversible des rattachements auto (récent)
CAT_CUR_MAX_SUGGEST = 120     # plafond de la file animaux
CAT_SUGGEST_CACHE = {"at": 0.0, "building": False, "items": []}
CAT_SUGGEST_LOCK = threading.Lock()

# Course entre un jugement et une reconstruction de file. Purger le cache au
# moment du jugement (fait) ne suffit pas : une passe DÉMARRÉE AVANT le geste
# écrase ensuite le cache avec une liste calculée sans lui, et la carte jugée
# réapparaît — le mode de panne « je corrige et ça revient », observé le 12/08.
# On garde donc une trace horodatée des cartes jugées ; toute reconstruction
# écarte celles jugées APRÈS son démarrage. Vaut pour les deux files.
JUGES_RECENTS = []            # [(ts, clé)], borné
JUGES_LOCK = threading.Lock()


def _note_juge(key):
    """Mémorise qu'une carte portant cette clé vient d'être jugée."""
    if not key:
        return
    with JUGES_LOCK:
        JUGES_RECENTS.append((time.time(), str(key)))
        if len(JUGES_RECENTS) > 400:
            del JUGES_RECENTS[:-400]


def _juges_depuis(t0):
    """Clés jugées depuis l'instant t0 (démarrage d'une reconstruction)."""
    with JUGES_LOCK:
        return {k for ts, k in JUGES_RECENTS if ts >= t0}


def _cat_suggest_remove(pred):
    """Retire du cache les suggestions animaux correspondant au prédicat."""
    with CAT_SUGGEST_LOCK:
        CAT_SUGGEST_CACHE["items"] = [s for s in CAT_SUGGEST_CACHE["items"]
                                      if not pred(s)]


def _cat_auto_pass():
    """Une passe d'auto-attribution des chats : rattache les chats détectés qui
    correspondent TRÈS clairement à un chat nommé (seuil élevé + marge nette avec
    le 2e). Conservateur exprès (mieux vaut en oublier que d'en mal étiqueter)."""
    import numpy as np
    pets = []
    for pk, pe in list(PETS_STORE.data.items()):
        if not isinstance(pe, dict):
            continue
        nm = pe.get('name')
        cen = cat_centroid(pe)
        if not nm or cen is None:
            continue
        pets.append((nm, cen, set(pe.get('exclude') or [])))
    if not pets:
        return 0
    C = np.stack([c for _n, c, _x in pets])
    added = 0
    for k, e in list(ANIMAL_STORE.data.items()):
        if not isinstance(e, dict) or e.get('failed'):
            continue
        se = STORE.data.get(k)
        for ai, a in enumerate(e.get('animals') or []):
            if not _nommable(a) or not a.get('emb'):
                continue
            try:
                v = _emb_from_b64(a['emb'])
                if v.shape[0] != C.shape[1]:
                    continue
                sims = C @ v
            except Exception:
                continue
            order = np.argsort(sims)[::-1]
            best = int(order[0])
            bs = float(sims[best])
            second = float(sims[int(order[1])]) if len(order) > 1 else -1.0
            if bs >= CAT_AUTO_SIM and (bs - second) >= CAT_AUTO_MARGIN:
                nm, _c, excl = pets[best]
                if k in excl:
                    break
                tag = f"animal:{nm}"
                if se is not None and not _kw_has(se, tag):
                    if _index_add_person(k, tag):
                        _enqueue_person_write(k, tag)
                        added += 1
                        # Journal réversible (bande « ajoutés automatiquement »
                        # de l'onglet Classification, comme pour les personnes).
                        CAT_AUTO_LOG.append({
                            "animal": nm, "key": k, "i": int(ai),
                            "sim": round(bs, 3),
                            "crop_url": _animal_crop_url(k, ai),
                            "url": _url_for_key(k), "at": time.time()})
                        if len(CAT_AUTO_LOG) > CAT_AUTO_LOG_MAX:
                            del CAT_AUTO_LOG[:-CAT_AUTO_LOG_MAX]
            break   # un seul chat représentatif par photo suffit
    if added:
        STORE.save()
        print(f"  🐱 Auto-attribution chats : {added} photo(s) rattachée(s)")
    return added


def cat_curator_loop():
    """Auto-attribution des chats en tâche de fond (équivalent du curateur des
    personnes). Tourne pendant l'absence pour récupérer les chats tout seul.
    Reconstruit aussi la file « À vérifier » animaux après chaque passe."""
    time.sleep(180)
    while True:
        try:
            if ANIMAL_QUEUE.empty() and not ui_recent():
                n = _cat_auto_pass() if CAT_AUTO_ENABLE else 0
                build_cat_suggestions()
                time.sleep(200 if n else 600)
            else:
                time.sleep(60)
        except Exception as e:
            print(f"  ⚠ Auto-attribution chats : {e}")
            time.sleep(120)


def build_cat_suggestions():
    """File « À vérifier » des animaux (onglet Classification de /sujets).

    Propose les chats détectés qui ressemblent à un chat nommé (score ≥
    PET_MATCH_SIM) mais que l'auto-attribution NE prendra PAS toute seule
    (score < CAT_AUTO_SIM ou marge < CAT_AUTO_MARGIN) : exactement la zone
    d'incertitude où le jugement humain informe le plus. Tri par MARGE
    croissante, jamais par score absolu (anti-circularité, comme le curateur
    des personnes). Lecture seule : aucun tag posé ici — accepter/rejeter
    passe par /api/assign (undo + journal des jugements)."""
    with CAT_SUGGEST_LOCK:
        if CAT_SUGGEST_CACHE["building"]:
            return
        CAT_SUGGEST_CACHE["building"] = True
    t0 = time.time()
    try:
        import numpy as np
        # Garde-fou « clés fantômes » (même leçon que build_suggestions) : une
        # clé qui ne résout vers aucun fichier produit une carte sans vignette
        # (/api/animalcrop → 404). On l'écarte, mais SEULEMENT si sa racine est
        # joignable — jamais quand le NAS est déconnecté (sinon tout le corpus
        # passerait pour disparu).
        def _racine_ok(p):
            try:
                return Path(p).exists()
            except OSError:
                return False
        _up_ok = _racine_ok(UPLOAD_DIR)
        pets = []
        for pk, pe in list(PETS_STORE.data.items()):
            if not isinstance(pe, dict):
                continue
            nm = pe.get('name')
            cen = cat_centroid(pe)
            if not nm or cen is None:
                continue
            pets.append((nm, cen, set(pe.get('exclude') or [])))
        items = []
        if pets:
            C = np.stack([c for _n, c, _x in pets])
            for k, e in list(ANIMAL_STORE.data.items()):
                if not isinstance(e, dict) or e.get('failed'):
                    continue
                se = STORE.data.get(k)
                for ai, a in enumerate(e.get('animals') or []):
                    # par_humain : détection déjà jugée par un humain — plus
                    # jamais re-questionnée (même garde-fou que la vérif d'espèce).
                    if not _nommable(a) or not a.get('emb') or a.get('par_humain'):
                        continue
                    try:
                        v = _emb_from_b64(a['emb'])
                        if v.shape[0] != C.shape[1]:
                            continue
                        sims = C @ v
                    except Exception:
                        continue
                    order = np.argsort(sims)[::-1]
                    best = int(order[0])
                    bs = float(sims[best])
                    second = float(sims[int(order[1])]) if len(order) > 1 else -1.0
                    nm, _c, excl = pets[best]
                    marge = bs - second
                    if bs < PET_MATCH_SIM or k in excl:
                        break
                    # Ce que l'auto-attribution prendra toute seule n'est pas
                    # une question à poser.
                    if CAT_AUTO_ENABLE and bs >= CAT_AUTO_SIM and marge >= CAT_AUTO_MARGIN:
                        break
                    if se is not None and _kw_has(se, f"animal:{nm}"):
                        break
                    # Clé fantôme : un seul is_file() local, sur les vrais
                    # candidats uniquement (pas sur tout le corpus).
                    _rp = _resolve_key(k)
                    _root_ok = _racine_ok(Path(_rp.anchor)) if _rp.is_absolute() else _up_ok
                    if _root_ok:
                        try:
                            if not _rp.is_file():
                                break
                        except OSError:
                            pass
                    rival = pets[int(order[1])][0] if len(order) > 1 else ""
                    items.append({"type": "add", "genre": "animal", "animal": nm,
                                  "key": k, "i": int(ai), "sim": round(bs, 3),
                                  "margin": round(marge, 3), "rival": rival,
                                  "rival_sim": round(second, 3),
                                  "crop_url": _animal_crop_url(k, ai),
                                  "box": _boite_animal(k, int(ai)),
                                  "url": _url_for_key(k)})
                    break   # un seul chat représentatif par photo suffit
        items.sort(key=lambda x: x.get("margin", 9.9))
        items = items[:CAT_CUR_MAX_SUGGEST]
        # Cartes jugées PENDANT cette passe : elles ne doivent pas revenir.
        recents = _juges_depuis(t0)
        if recents:
            items = [s for s in items if s.get("key") not in recents]
        with CAT_SUGGEST_LOCK:
            CAT_SUGGEST_CACHE["items"] = items
            CAT_SUGGEST_CACHE["at"] = time.time()
    finally:
        with CAT_SUGGEST_LOCK:
            CAT_SUGGEST_CACHE["building"] = False


def cat_centroid(pe):
    """Signature d'un chat = moyenne normalisée de ses embeddings de référence."""
    import numpy as np
    vs = []
    for s in (pe.get('refs') or []):
        try:
            vs.append(_emb_from_b64(s))
        except Exception:
            pass
    if not vs:
        return None
    c = np.mean(np.stack(vs), axis=0)
    n = np.linalg.norm(c)
    return c / n if n else c


def cat_photos(name, limit=2000):
    """Photos taguées animal:Nom, pour révision/correction. Pour chaque photo on
    retient le chat qui ressemble LE MIEUX à la signature, et on trie du moins au
    plus ressemblant → les faux positifs remontent en tête (comme pour les
    personnes)."""
    return PETS.photos(name, limit)


def untag_cat(name, keys):
    """Retire animal:Nom de photos mal attribuées : voir SubjectStore.untag."""
    return PETS.untag(name, keys)


def rename_cat(old, new):
    """Renomme un animal : voir SubjectStore.rename."""
    return PETS.rename(old, new)


def delete_cat(name):
    """Supprime entièrement un animal : voir SubjectStore.delete."""
    return PETS.delete(name)


def note_heavy_activity():
    """À appeler quand l'UI lit une image sur le NAS (crop/média/upload), pour
    que le ré-embedding cède le NAS pendant que l'utilisateur navigue."""
    global LAST_HEAVY_AT
    LAST_HEAVY_AT = time.time()


def ui_recent():
    return (time.time() - LAST_HEAVY_AT) < REEMBED_UI_QUIET


def _face_is_poor(f):
    """Visage de mauvaise qualité : score de détection faible OU petit visage."""
    if float(f.get('det_score', 1.0)) < REEMBED_MIN_SCORE:
        return True
    b = f.get('bbox')
    if b and len(b) == 4 and (b[2] - b[0]) < REEMBED_MIN_FACE_PX:
        return True
    return False


REEMBED_STATE = {"done": 0, "improved": 0}


def reembed_one_batch():
    """Ré-analyse un lot de photos aux visages faibles, en meilleure résolution.
    Remplace leurs empreintes par de meilleures. Marque 'reemb' pour ne pas y
    revenir. Retourne le nombre de photos ré-analysées."""
    ms = reembed_resolution()
    n = 0
    changed = False
    # Visages déjà attribués à une personne : la ré-détection change l'ordre/le
    # nombre de `faces`, ce qui casserait les références (clé,i) des fiches.
    assigned_keys = {k for (k, _i) in _assigned_face_set(PEOPLE_STORE)}
    for k, e in list(FACE_STORE.data.items()):
        if not isinstance(e, dict) or e.get('failed') or e.get('reemb'):
            continue
        faces = e.get('faces') or []
        # INVARIANT « ne jamais perdre un jugement humain ». `detect_faces` REMPLACE
        # la liste `faces` (ordre et nombre peuvent changer) : ré-embarquer une photo
        # qu'un humain a déjà jugée effacerait ses marquages (pas_visage / non_group /
        # inconnu / par_humain) et casserait les références des fiches nommées. On la
        # saute donc définitivement (reemb=1). C'ÉTAIT la cause du « Caline (chatte)
        # revient sans cesse comme personne » : ses découpes de chat, marquées
        # « animal », sont faibles → étaient ré-embarquées → démarquées → re-cluster.
        if k in assigned_keys or any(
                f.get('par_humain') or f.get('pas_visage')
                or f.get('non_group') or f.get('inconnu') for f in faces):
            e['reemb'] = 1
            changed = True
            continue
        if not any(_face_is_poor(f) for f in faces):
            e['reemb'] = 1          # rien à améliorer → on marque
            changed = True
            continue
        p = _resolve_key(k)
        try:
            if not p.is_file():
                e['reemb'] = 1
                changed = True
                continue
        except OSError:
            continue
        try:
            newfaces = detect_faces(p, max_side=ms)
            e['faces'] = newfaces
            e['n'] = len(newfaces)
            e['reemb'] = 1
            e['reemb_ms'] = ms
            FACE_STORE.set(k, e)    # sauvegarde
            n += 1
            REEMBED_STATE["done"] += 1
            print(f"  🔬 Ré-embedding ({'full' if ms == 0 else str(ms) + 'px'}) : "
                  f"{k} — {len(newfaces)} visage(s)")
        except Exception as ex:
            e['reemb'] = 1
            changed = True
            print(f"  ⚠ ré-embed {k} : {ex}")
        if n >= REEMBED_BATCH or system_busy() or ui_recent():
            break                   # cède le NAS dès que l'UI l'utilise
    if changed and n == 0:
        FACE_STORE.save()           # persiste les marquages « rien à faire »
    return n


def reembed_loop():
    """Améliore en continu les empreintes des visages faibles — mais seulement
    quand la machine est au calme (détection finie, CPU/RAM disponibles).
    S'adapte à l'état matériel courant (résolution, throttling)."""
    time.sleep(60)
    if not REEMBED_ENABLE or get_face_app() is None:
        return
    while True:
        try:
            if ui_recent():
                time.sleep(5)
                continue
            if not (FACE_QUEUE.empty() and TAG_QUEUE.empty()):
                time.sleep(REEMBED_BUSY_SLEEP)   # travail d'entretien : après
                continue
            with creneau('reembed', timeout=240) as ok:
                did = reembed_one_batch() if ok else 0
            time.sleep(REEMBED_PACE if did else REEMBED_IDLE_SLEEP)
        except Exception as e:
            print(f"  ⚠ Ré-embedding : {e}")
            time.sleep(30)


# ────────────────── Phase 2 : regroupement + nommage ──────────────────

def _emb_from_b64(s):
    import numpy as np
    v = np.frombuffer(base64.b64decode(s), dtype=np.float16).astype(np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n else v


def _stack_embs(embs):
    """Décode une liste d'embeddings base64 (float16) en UNE matrice float32
    normalisée par ligne, en un minimum d'opérations numpy (un seul frombuffer,
    une seule normalisation). Renvoie None si les tailles sont hétérogènes ou en
    cas d'échec → l'appelant retombe sur le chemin lent, par élément."""
    import numpy as np
    try:
        raw = [base64.b64decode(s) for s in embs]
        if not raw:
            return None
        w = len(raw[0])
        if w == 0 or any(len(b) != w for b in raw):
            return None
        M = np.frombuffer(b''.join(raw), dtype=np.float16).astype(np.float32)
        M = M.reshape(len(raw), -1)
        nrm = np.linalg.norm(M, axis=1, keepdims=True)
        nrm[nrm == 0] = 1.0
        return M / nrm
    except Exception:
        return None


def _best_sims_for_tag(tag, sig, det_store, det_field, filter_nommable=False):
    """Pour chaque photo taguée `tag`, meilleur score cosinus de ses détections
    (visages/animaux) contre le vecteur signature `sig`.

    VECTORISÉ : un seul gros produit matriciel au lieu d'un produit par visage.
    Le scan par-visage bloquait le GIL des milliers de fois en concurrence avec
    les workers (mesuré : 156 s pour re-scorer une personne à 6338 photos) ; un
    unique matmul libère le GIL et rend la même opération quasi immédiate. Si le
    décodage groupé échoue (tailles hétérogènes), repli transparent par élément.

    Renvoie une liste (key, entry, best_sim|None, best_idx|None) dans l'ordre
    d'insertion de STORE. `sig` None → best_sim None partout."""
    import numpy as np
    rows = []          # [k, e, first_idx|None]
    embs, owner, fidx = [], [], []
    for k, e in STORE.data.items():
        if not _kw_has(e, tag):
            continue
        de = det_store.data.get(k)
        items = (de.get(det_field) if isinstance(de, dict) else None) or []
        if filter_nommable:
            cand = [(i, a) for i, a in enumerate(items) if _nommable(a)]
        else:
            cand = list(enumerate(items))
        ridx = len(rows)
        rows.append([k, e, (cand[0][0] if cand else None)])
        for i, a in cand:
            emb = a.get('emb')
            if emb:
                embs.append(emb)
                owner.append(ridx)
                fidx.append(i)
    best = [-2.0] * len(rows)
    bidx = [r[2] for r in rows]
    if embs and sig is not None:
        sigv = np.asarray(sig, dtype=np.float32)
        M = _stack_embs(embs)
        if M is not None and M.shape[1] == sigv.shape[0]:
            sc = M @ sigv
            for o, fi, s in zip(owner, fidx, sc):
                if s > best[o]:
                    best[o] = float(s)
                    bidx[o] = fi
        else:  # repli lent, par élément (dimensions hétérogènes / échec décodage)
            for s, o, fi in zip(embs, owner, fidx):
                try:
                    d = float(np.dot(sigv, _emb_from_b64(s)))
                except Exception:
                    continue
                if d > best[o]:
                    best[o] = d
                    bidx[o] = fi
    return [(rows[i][0], rows[i][1],
             (round(best[i], 3) if best[i] > -2.0 else None), bidx[i])
            for i in range(len(rows))]


def cluster_faces(vecs, meta, sim_thr, min_size):
    """Regroupement glouton par similarité cosinus (une passe). vecs : liste de
    vecteurs normalisés ; meta : liste (clé, index_visage) parallèle."""
    import numpy as np
    n = len(vecs)
    if n == 0:
        return []
    D = vecs[0].shape[0]
    cap = 64
    cent = np.zeros((cap, D), np.float32)   # centroïdes normalisés
    csum = np.zeros((cap, D), np.float32)   # somme des membres
    cnt = np.zeros(cap, np.int32)
    m = 0
    assign = [0] * n
    for idx in range(n):
        v = vecs[idx]
        j = -1
        if m:
            sims = cent[:m] @ v
            jj = int(np.argmax(sims))
            if sims[jj] >= sim_thr:
                j = jj
        if j < 0:
            if m >= cap:
                cap *= 2
                cent = np.vstack([cent, np.zeros((cap - m, D), np.float32)])
                csum = np.vstack([csum, np.zeros((cap - m, D), np.float32)])
                cnt = np.concatenate([cnt, np.zeros(cap - m, np.int32)])
            j = m
            m += 1
            csum[j] = v
            cnt[j] = 1
            nn = np.linalg.norm(v)
            cent[j] = v / nn if nn else v
        else:
            csum[j] += v
            cnt[j] += 1
            c = csum[j]
            nn = np.linalg.norm(c)
            cent[j] = c / nn if nn else c
        assign[idx] = j
    groups = {}
    for mm, a in zip(meta, assign):
        groups.setdefault(a, []).append(mm)
    cl = [{"members": mem, "size": len(mem)}
          for mem in groups.values() if len(mem) >= min_size]
    cl.sort(key=lambda c: c["size"], reverse=True)
    return cl


def _gather_faces():
    """Tous les visages de l'index : (clés, index, vecteurs normalisés).
    Exclut les visages déjà attribués à une personne (ne réapparaissent jamais)."""
    assigned = _assigned_face_set(PEOPLE_STORE)
    vecs, meta = [], []
    for k, e in list(FACE_STORE.data.items()):
        if not isinstance(e, dict) or e.get('failed'):
            continue
        for i, f in enumerate(e.get('faces') or []):
            if (k, i) in assigned:
                continue
            # Marquages humains (12b) : une decoupe jugee « pas un visage »
            # (chat, objet) ou un visage juge « non regroupable » (nuque,
            # profil detourne) ne doit plus jamais reformer un groupe. Un visage
            # archive sous « (Inconnus) » (inconnu) est sorti de « A nommer » : il
            # vit dans sa propre vue, jusqu'a re-tag.
            if f.get('pas_visage') or f.get('non_group') or f.get('inconnu'):
                continue
            emb = f.get('emb')
            if not emb:
                continue
            try:
                vecs.append(_emb_from_b64(emb))
                meta.append((k, i))
            except Exception:
                continue
    return vecs, meta


def _crop_url(key, i):
    return '/api/facecrop?key=' + urllib.parse.quote(key, safe='') + '&i=' + str(i)


def _boite_visage(key, i):
    """[x1, y1, x2, y2] du visage `i` (pixels de l'image ORIENTÉE), ou None.

    Part dans les cartes de classification : la loupe encadre le visage dont
    parle la carte — sur une tablée de huit, la photo entière ne dit pas
    lequel. Le client normalise avec naturalWidth/Height : mêmes pixels que
    la détection (exif_transpose côté serveur, orientation native côté
    navigateur)."""
    e = FACE_STORE.get(key)
    faces = (e.get('faces') or []) if isinstance(e, dict) else []
    if 0 <= i < len(faces):
        b = faces[i].get('bbox')
        if isinstance(b, (list, tuple)) and len(b) == 4:
            return [int(v) for v in b]
    return None


def _boite_animal(key, i):
    """Même contrat que `_boite_visage`, pour une détection d'animal."""
    e = ANIMAL_STORE.get(key)
    dets = (e.get('animals') or []) if isinstance(e, dict) else []
    if 0 <= i < len(dets):
        b = dets[i].get('bbox')
        if isinstance(b, (list, tuple)) and len(b) == 4:
            return [int(v) for v in b]
    return None


def _filter_known(vecs, meta):
    """Écarte les visages qui correspondent déjà à une personne nommée
    (similarité >= seuil), pour que « Groupes à nommer » ne montre que des
    inconnus. Exception : un visage dont la photo a été corrigée (exclue) pour
    la personne qu'il matche est conservé — c'était un faux positif."""
    import numpy as np
    people = []
    for pk, pe in PEOPLE_STORE.data.items():
        if not isinstance(pe, dict):
            continue
        refs = pe.get('refs') or []
        if not refs:
            continue
        try:
            R = np.stack([_emb_from_b64(s) for s in refs])
        except Exception:
            continue
        people.append((pk, R, set(pe.get('exclude') or [])))
    if not people or not vecs:
        return vecs, meta
    R_all = np.vstack([R for (_pk, R, _ex) in people])
    owner = []
    for pid, (_pk, R, _ex) in enumerate(people):
        owner += [pid] * R.shape[0]
    owner = np.array(owner)
    excl = [ex for (_pk, _R, ex) in people]
    keep_v, keep_m = [], []
    E = np.stack(vecs)
    CH = 2000
    for s in range(0, E.shape[0], CH):
        sub = E[s:s + CH]
        Sm = sub @ R_all.T
        mx = Sm.max(axis=1)
        for r in range(sub.shape[0]):
            gi = s + r
            if mx[r] < FACE_MATCH_SIM:
                keep_v.append(vecs[gi])
                keep_m.append(meta[gi])
                continue
            cols = np.where(Sm[r] >= FACE_MATCH_SIM)[0]
            pids = set(owner[cols].tolist())
            key = meta[gi][0]
            if any(key not in excl[pid] for pid in pids):
                continue  # déjà identifié → masqué
            keep_v.append(vecs[gi])
            keep_m.append(meta[gi])
    return keep_v, keep_m


def _cluster_centroid(members, vmap):
    import numpy as np
    M = np.stack([vmap[m] for m in members])
    c = M.mean(axis=0)
    n = np.linalg.norm(c)
    return c / n if n else c


def _purify_clusters(clusters, vmap):
    """Sépare les clusters qui mélangent deux personnes, SANS fragmenter ceux
    d'une même personne (angles variés). Méthode : re-regrouper les membres à un
    seuil plus strict ; on ne scinde que si les deux sous-groupes obtenus sont
    réellement éloignés (centroïdes < CLUSTER_SPLIT_CONFIRM) — signe de deux
    personnes distinctes. Sinon on garde le cluster tel quel. Jamais de
    suppression : au pire quelques piles de plus, jamais une pile corrompue."""
    import numpy as np
    out = []
    for c in clusters:
        mem = c["members"]
        if len(mem) < 2 * FACE_MIN_CLUSTER:
            out.append(c)
            continue
        mv = [vmap[m] for m in mem]
        subs = cluster_faces(mv, mem, CLUSTER_SPLIT_SIM, FACE_MIN_CLUSTER)
        if len(subs) >= 2:
            cens = [_cluster_centroid(s["members"], vmap) for s in subs]
            # scinde dès qu'AU MOINS deux sous-groupes sont réellement éloignés
            far = any(float(cens[a] @ cens[b]) < CLUSTER_SPLIT_CONFIRM
                      for a in range(len(cens)) for b in range(a + 1, len(cens)))
            if far:
                out.extend(subs)          # au moins deux personnes distinctes → on éclate
                continue
        out.append(c)                     # même personne (angles variés) → on garde entier
    out = [c for c in out if c["size"] >= FACE_MIN_CLUSTER]
    out.sort(key=lambda c: c["size"], reverse=True)
    return out


def build_clusters():
    """Recalcule les groupes de visages (tâche de fond, mise en cache)."""
    with CLUSTER_LOCK:
        if CLUSTER_CACHE["building"]:
            return
        CLUSTER_CACHE["building"] = True
    try:
        try:
            import numpy  # noqa: F401
        except Exception as e:
            print(f"  ⚠ Regroupement impossible (numpy absent) : {e}")
            return
        vecs, meta = _gather_faces()
        n_all = len(vecs)
        vecs, meta = _filter_known(vecs, meta)
        print(f"  👥 Regroupement de {len(vecs)} visages inconnus "
              f"({n_all - len(vecs)} déjà identifiés, ignorés)…")
        t0 = time.time()
        clusters = cluster_faces(vecs, meta, FACE_CLUSTER_SIM, FACE_MIN_CLUSTER)
        vmap = {m: v for m, v in zip(meta, vecs)}
        clusters = _purify_clusters(clusters, vmap)   # éclate les intrus
        light, byid = [], {}
        for n, c in enumerate(clusters):
            cid = str(n)
            members = c["members"]
            # « membres » accompagne les vignettes : c'est ce qui permet a
            # l'interface d'attribuer (ou d'ecarter) un SOUS-ENSEMBLE du groupe.
            light.append({"cid": cid, "size": c["size"],
                          "membres": [[k, i] for (k, i) in members[:18]],
                          "crops": [_crop_url(k, i) for (k, i) in members[:18]]})
            byid[cid] = members
        with CLUSTER_LOCK:
            CLUSTER_CACHE["clusters"] = light
            CLUSTER_CACHE["byid"] = byid
            CLUSTER_CACHE["at"] = time.time()
        print(f"  ✓ {len(light)} groupe(s) trouvé(s) en {time.time() - t0:.0f}s")
    finally:
        with CLUSTER_LOCK:
            CLUSTER_CACHE["building"] = False


def _gather_inconnus():
    """Visages archivés sous « (Inconnus) » : (vecteurs, meta). Symétrique de
    _gather_faces mais NE garde QUE les détections marquées 'inconnu' (et jamais
    déjà attribuées, ni 'pas_visage'/'non_group')."""
    assigned = _assigned_face_set(PEOPLE_STORE)
    vecs, meta = [], []
    for k, e in list(FACE_STORE.data.items()):
        if not isinstance(e, dict) or e.get('failed'):
            continue
        for i, f in enumerate(e.get('faces') or []):
            if not f.get('inconnu') or f.get('pas_visage') or f.get('non_group'):
                continue
            if (k, i) in assigned:
                continue
            emb = f.get('emb')
            if not emb:
                continue
            try:
                vecs.append(_emb_from_b64(emb))
                meta.append((k, i))
            except Exception:
                continue
    return vecs, meta


def build_inconnus():
    """Regroupe les visages archivés « (Inconnus) » (tâche de fond, cache).

    Seuil de taille = 1 : contrairement à « À nommer » (min 3), un inconnu
    archivé ne doit JAMAIS disparaître de la vue, même seul — c'est une file de
    re-tag, pas une découverte de groupes. Nommer un cluster lève l'archive."""
    with INCONNU_LOCK:
        if INCONNU_CACHE["building"]:
            return
        INCONNU_CACHE["building"] = True
    try:
        try:
            import numpy  # noqa: F401
        except Exception as e:
            print(f"  ⚠ Regroupement des inconnus impossible (numpy absent) : {e}")
            return
        vecs, meta = _gather_inconnus()
        if not vecs:
            with INCONNU_LOCK:
                INCONNU_CACHE["clusters"] = []
                INCONNU_CACHE["byid"] = {}
                INCONNU_CACHE["at"] = time.time()
            return
        clusters = cluster_faces(vecs, meta, FACE_CLUSTER_SIM, 1)
        clusters.sort(key=lambda c: c["size"], reverse=True)
        light, byid = [], {}
        for n, c in enumerate(clusters):
            cid = str(n)
            members = c["members"]
            light.append({"cid": cid, "size": c["size"],
                          "membres": [[k, i] for (k, i) in members[:18]],
                          "crops": [_crop_url(k, i) for (k, i) in members[:18]]})
            byid[cid] = members
        with INCONNU_LOCK:
            INCONNU_CACHE["clusters"] = light
            INCONNU_CACHE["byid"] = byid
            INCONNU_CACHE["at"] = time.time()
        print(f"  📦 {len(light)} groupe(s) d'inconnus archivés")
    finally:
        with INCONNU_LOCK:
            INCONNU_CACHE["building"] = False


def desarchiver_visages(membres):
    """Sort un sous-ensemble de visages de l'archive « (Inconnus) » sans les
    nommer : lève le champ 'inconnu' pour qu'ils réintègrent « À nommer ».
    Réversible (miroir de _marquer_visages)."""
    membres = [(str(k), int(i)) for k, i in membres if str(k)]
    touches = []
    for k, i in membres:
        e = FACE_STORE.data.get(k)
        faces = (e.get('faces') if isinstance(e, dict) else None) or []
        if i < len(faces) and faces[i].get('inconnu'):
            faces[i].pop('inconnu', None)
            touches.append((k, i))
    if not touches:
        return {"ok": True, "n": 0, "libelle": "rien à réactiver"}
    FACE_STORE.save()

    def defaire():
        for k, i in touches:
            e = FACE_STORE.data.get(k)
            faces = (e.get('faces') if isinstance(e, dict) else None) or []
            if i < len(faces):
                faces[i]['inconnu'] = True
        FACE_STORE.save()
        _invalider_groupes_visages()

    libelle = f"{len(touches)} visage(s) réactivé(s)"
    jeton = _empiler_annulation(libelle, defaire)
    _invalider_groupes_visages()
    return {"ok": True, "n": len(touches), "jeton": jeton, "libelle": libelle}


def write_person_tags(path, gestes):
    """Applique PLUSIEURS gestes sur une même photo en UNE invocation ExifTool.

    `gestes` : `{tag: 'add'|'del'}`. Un ajout fait `-=` puis `+=` (pas de
    doublon, comme avant) ; un retrait fait `-=` seul. IPTC suit XMP.

    POURQUOI GROUPER : le coût dominant n'est pas l'écriture, c'est le
    DÉMARRAGE du processus ExifTool — ~2,6 s mesurés sur SMB le 23/08. Or
    renommer une personne demande DEUX gestes par photo (retirer l'ancien nom,
    ajouter le nouveau) : la fusion Flo → Florine a ainsi coûté 11 814
    invocations pour 5 907 photos, soit ~11 h pendant lesquelles un simple
    redémarrage devenait interdit. Une invocation par PHOTO au lieu d'une par
    GESTE divise ce coût par deux — et l'ordre est préservé, le dernier geste
    posé sur un tag l'emporte, exactement comme deux appels successifs."""
    if not EXIFTOOL or not gestes:
        return False
    args = ["-overwrite_original", "-q", "-m", "-charset", "filename=UTF8",
            "-codedcharacterset=utf8"]
    for tag, op in gestes.items():
        args += [f"-XMP-dc:Subject-={tag}", f"-IPTC:Keywords-={tag}"]
        if op != 'del':
            args += [f"-XMP-dc:Subject+={tag}", f"-IPTC:Keywords+={tag}"]
    args.append(str(path))
    try:
        return _run_exiftool(args).returncode == 0
    except Exception:
        return False


def write_person_tag(path, tag):
    """Ajoute le mot-clé « personne:Nom » dans le fichier (XMP + IPTC), sans
    doublon (-= puis +=) et sans toucher aux autres mots-clés."""
    return write_person_tags(path, {tag: 'add'})


def write_person_untag(path, tag):
    """Retire le mot-clé « personne:Nom » du fichier (XMP + IPTC)."""
    return write_person_tags(path, {tag: 'del'})


def _file_personnes_note(path, tag, op, key):
    """Note un geste dans le journal de la file AVANT de l'enfiler, et rend son
    numéro d'ordre.

    Écrire d'abord, enfiler ensuite : si tout s'arrête entre les deux, le geste
    sera REFAIT au démarrage suivant — refaire est sans effet (l'écriture est
    idempotente), tandis qu'oublier laisse un nom fantôme dans un fichier."""
    global PERSON_SEQ
    with PERSON_JOURNAL_LOCK:
        PERSON_SEQ += 1
        n = PERSON_SEQ
        try:
            with open(PERSON_JOURNAL, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"n": n, "chemin": str(path), "tag": tag,
                                    "op": op, "cle": key},
                                   ensure_ascii=False) + "\n")
        except OSError as e:                                  # noqa: BLE001
            print(f"  ! file personne : journal non ecrit ({e})")
    return n


def _file_personnes_faite(lot):
    """Avance la position : tout ce qui porte un numéro <= elle est consommé.

    Une position suffit parce que `person_writer` est l'écrivain UNIQUE et
    consomme dans l'ordre. Elle avance même quand l'écriture a échoué : le
    geste a été TENTÉ, et le rejouer indéfiniment ferait boucler un fichier
    illisible. Ce qui a échoué est nommé dans `_file_personnes_echecs.jsonl`,
    jamais avalé."""
    global PERSON_SEQ
    n = max([it[4] for it in lot if len(it) >= 5 and it[4]] or [0])
    if not n:
        return
    with PERSON_JOURNAL_LOCK:
        try:
            tmp = Path(str(PERSON_JOURNAL_POS) + '.tmp')
            tmp.write_text(str(n), encoding='utf-8')
            os.replace(tmp, PERSON_JOURNAL_POS)
        except OSError:
            return
        # File vide et rien de plus récent enfilé : le journal a fini son
        # office, on le remet à zéro pour qu'il ne grossisse pas sans fin.
        if PERSON_QUEUE.qsize() == 0 and n >= PERSON_SEQ:
            try:
                PERSON_JOURNAL.unlink(missing_ok=True)
                PERSON_JOURNAL_POS.unlink(missing_ok=True)
                PERSON_SEQ = 0
            except OSError:
                pass


def _file_personnes_echec(lot, motif):
    """Nomme par écrit ce que la file n'a pas su écrire."""
    try:
        with open(PERSON_JOURNAL_ECHECS, 'a', encoding='utf-8') as f:
            for it in lot:
                f.write(json.dumps(
                    {"quand": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "chemin": str(it[0]), "tag": it[1], "op": it[2],
                     "cle": it[3] if len(it) >= 4 else None,
                     "motif": motif}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _file_personnes_reprise():
    """Remet en file ce qu'un arrêt a laissé en plan, et rend leur nombre.

    Lit le journal, saute tout ce que la position déclare consommé, et réenfile
    le reste. Une ligne tronquée par une coupure est ignorée sans faire tomber
    la reprise. Le chemin est RÉSOLU depuis la clé quand elle existe : entre
    l'arrêt et le redémarrage, la photo a pu être rangée ailleurs.

    ELLE NE JUGE PAS DE L'EXISTENCE (23/08). Elle testait `is_file()` et
    comptait les « non » comme perdus. Au DÉMARRAGE, c'est le pire moment pour
    poser cette question : le partage NAS peut n'être pas encore joignable, et
    un `is_file()` prudent jetait alors TOUTE la file que ce journal existe
    pour sauver — le défaut annulait exactement le remède. Ce qui ne s'écrira
    pas sera NOMMÉ par l'écrivain, qui, lui, a essayé."""
    global PERSON_SEQ
    if not PERSON_JOURNAL.exists():
        return 0
    try:
        pos = int((PERSON_JOURNAL_POS.read_text(encoding='utf-8')
                   if PERSON_JOURNAL_POS.exists() else '0').strip() or 0)
    except (OSError, ValueError):
        pos = 0
    repris = 0
    dernier = pos
    try:
        with open(PERSON_JOURNAL, encoding='utf-8') as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    d = json.loads(ligne)
                    n = int(d.get('n') or 0)
                except (ValueError, TypeError):
                    continue
                dernier = max(dernier, n)
                if n <= pos:
                    continue
                cle = d.get('cle')
                try:
                    p = _resolve_key(cle) if cle else Path(d.get('chemin') or '')
                except OSError:
                    p = Path(d.get('chemin') or '')
                PERSON_QUEUE.put((p, d.get('tag'), d.get('op') or 'add', cle, n))
                repris += 1
    except OSError as e:                                      # noqa: BLE001
        print(f"  ! file personne : journal illisible ({e})")
        return 0
    PERSON_SEQ = max(PERSON_SEQ, dernier)
    if repris:
        print(f"  * File XMP : {repris} ecriture(s) reprises apres arret. "
              "Ce qui ne s ecrira pas sera nomme dans "
              "_file_personnes_echecs.jsonl.")
    return repris


def _ecrire_lot_personne(lot):
    """Écrit en UNE invocation tous les gestes d'une même photo, resynchronise
    le mtime de l'index, puis avance la position de la file durable."""
    path = lot[0][0]
    gestes = {}
    for it in lot:
        gestes[it[1]] = 'del' if it[2] == 'del' else 'add'
    ok = False
    motif = ""
    try:
        ok = write_person_tags(path, gestes)
        if not ok:
            motif = "exiftool absent" if not EXIFTOOL else "exiftool a refuse"
        # PÉRENNITÉ : après notre propre écriture, on resynchronise le mtime
        # stocké dans l'index avec celui du fichier — sinon le balayage
        # « fichiers modifiés » re-tague la photo et perd le tag nommé.
        if ok:
            for key in dict.fromkeys(it[3] for it in lot
                                     if len(it) >= 4 and it[3] is not None):
                try:
                    size, mtime = _stat_of(path)
                    e = STORE.data.get(key)
                    if isinstance(e, dict) and mtime is not None:
                        e['mtime'] = mtime
                        if size is not None:
                            e['size'] = size
                except Exception:
                    pass
    except Exception as e:                                    # noqa: BLE001
        motif = f"{type(e).__name__}: {e}"
        print(f"  ! ecriture personne {path} : {e}")
    finally:
        if not ok:
            _file_personnes_echec(lot, motif or "inconnu")
        _file_personnes_faite(lot)
        for _ in lot:
            PERSON_QUEUE.task_done()


def person_writer():
    """Écrit/retire les tags personne:Nom dans les fichiers, en série (un seul
    ExifTool à la fois), pour ne pas saturer le NAS.

    Les gestes qui se suivent sur la MÊME photo partent ENSEMBLE : un renommage
    en pose deux par photo, coup sur coup, et les payer en deux processus
    doublait la facture (voir `write_person_tags`)."""
    reste = None
    while True:
        premier = reste if reste is not None else PERSON_QUEUE.get()
        reste = None
        lot = [premier]
        while len(lot) < PERSON_LOT_MAX:
            try:
                autre = PERSON_QUEUE.get_nowait()
            except queue.Empty:
                break
            if str(autre[0]) == str(premier[0]):
                lot.append(autre)
            else:
                reste = autre           # pris, pas encore fait : il ouvre le
                break                   # prochain lot, et sera compté là
        _ecrire_lot_personne(lot)


def _kw_has(e, tag):
    """Le mot-clé est-il présent (comparaison insensible à la casse) ?
    Indispensable car les tags importés d'un fichier et ceux écrits par l'app
    peuvent différer de casse (personne:Nom vs personne:nom)."""
    if not isinstance(e, dict):
        return False
    tl = tag.lower()
    return any(str(x).lower() == tl for x in (e.get('kw_fr') or []))


def _index_add_person(key, tag):
    """Ajoute le tag à l'entrée d'index (en mémoire) pour le filtre galerie."""
    e = STORE.data.get(key)
    if isinstance(e, dict) and not e.get('failed'):
        kw = e.get('kw_fr') or []
        if tag.lower() not in [str(x).lower() for x in kw]:
            kw.append(tag)
            e['kw_fr'] = kw
            return True
    return False


def _index_remove_person(key, tag):
    """Retire le tag de l'entrée d'index (en mémoire), insensible à la casse."""
    e = STORE.data.get(key)
    if isinstance(e, dict):
        kw = e.get('kw_fr') or []
        tl = tag.lower()
        newkw = [x for x in kw if str(x).lower() != tl]
        if len(newkw) != len(kw):
            e['kw_fr'] = newkw
            return True
    return False


def _enqueue_person_write(key, tag, op='add'):
    """Note le geste au journal, PUIS l'enfile — sans juger d'abord si le
    fichier existe.

    POURQUOI CE N'EST PLUS UN `is_file()`, et ce que ça coûtait (23/08).
    Cette fonction testait `p.is_file()` et, sur un « non », ne notait rien,
    n'enfilait rien, ne disait rien. Or `is_file()` interroge un partage SMB :
    il répond « non » quand le NAS hoquette, quand la session réseau se
    renégocie, quand le partage n'est pas encore monté — sur un fichier qui
    existe. Le geste disparaissait alors ENTRE l'index et le fichier, sans une
    ligne nulle part : la règle 2 tombait en silence.

    Le compte, ce jour-là : `personne:Ellie` — **342 photos à l'index, 54 dont
    le fichier ne porte pas le nom**, file à zéro ; `Mike`, **37 sur 200**
    tirées. Les deux seuls noms sans écart (Florine 200/200, Stéphane Plouvin
    58/58) sont précisément les deux dont les fichiers ont été RÉÉCRITS en
    entier. Ce qui s'accumule geste par geste fuyait ; ce qui est réécrit d'un
    bloc, non.

    Le seul endroit qui a le droit de déclarer une écriture impossible est
    celui qui l'a TENTÉE : `_ecrire_lot_personne` nomme ce qui échoue dans
    `_file_personnes_echecs.jsonl`, et la position avance quand même. Partout
    ailleurs, décider revient à perdre sans trace."""
    try:
        p = _resolve_key(key)
    except OSError:
        p = Path(str(key))          # même une clé irrésoluble laisse une trace
    n = _file_personnes_note(p, tag, op, key)
    PERSON_QUEUE.put((p, tag, op, key, n))


def reclasser_animaux(dry=True):
    """Reclasse les photos taguees `personne:Nom` en `animal:Nom` quand Nom est
    un animal connu (fiche PETS_STORE). PRESERVE le nom (change seulement le
    prefixe) et retire au passage la fiche `personne` en double d'une fiche
    animal du meme nom. Ecrit via les primitives existantes (XMP + index, file
    PERSON_QUEUE, ecrivain unique) ; entierement REVERSIBLE via un journal
    `docs/undo_reclassement_*.json`.

    Balaye TOUS les noms (generalise, pas seulement Mutz/Caline). Les tags SANS
    prefixe (ex. l'adjectif « caline ») ne sont jamais touches."""
    pets = set(PETS_STORE.data.keys())          # cles minuscules
    par_nom = {}                                 # nl -> {'nom':suffixe, 'keys':set}
    for key, e in list(STORE.data.items()):
        if not isinstance(e, dict) or e.get('failed'):
            continue
        for kw in (e.get('kw_fr') or []):
            s = str(kw)
            if s.lower().startswith('personne:'):
                suf = s.split(':', 1)[1]
                if suf.lower() in pets:
                    par_nom.setdefault(suf.lower(),
                                       {'nom': suf, 'keys': set()})['keys'].add(key)
    dup = [pk for pk in PEOPLE_STORE.data.keys() if pk in pets]
    toutes = set().union(*[d['keys'] for d in par_nom.values()]) if par_nom else set()
    rapport = {
        'noms': [{'nom': d['nom'], 'photos': len(d['keys']),
                  'fiche_double': nl in dup}
                 for nl, d in sorted(par_nom.items())],
        'total_photos': len(toutes),
        'fiches_double': dup,
    }
    if dry:
        return {'ok': True, 'dry': True, **rapport}

    # Rien a convertir : NE PAS creer de journal (sinon un journal vide masque le
    # vrai lors d'une annulation ulterieure). Idempotent : reappliquer ne fait rien.
    # (Les fiches en double ne sont retirees qu'avec la conversion de leur nom.)
    if not par_nom:
        return {'ok': True, 'dry': False, 'photos': 0,
                'noms_traites': [], 'fiches_retirees': []}

    journal = {'at': time.time(), 'noms': []}
    for nl, d in par_nom.items():
        nom = d['nom']
        keys = sorted(d['keys'])
        atag = f"animal:{nom}"
        for k in keys:                           # 1) ajoute animal:Nom
            _index_add_person(k, atag)
            _enqueue_person_write(k, atag, 'add')
        fiche = PEOPLE_STORE.data.get(nl)        # fiche personne en double (ou None)
        retires = PEOPLE.delete(nom)             # 2) retire personne:Nom (fichiers+index) + fiche
        journal['noms'].append({'nom': nom, 'keys': keys,
                                'fiche': fiche, 'retires': retires})
    STORE.save()
    _invalider_groupes_visages()
    _invalider_groupes_animaux()
    docs = SCRIPT_DIR / 'docs'
    docs.mkdir(exist_ok=True)
    jp = docs / f"undo_reclassement_{int(journal['at'])}.json"
    jp.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'ok': True, 'dry': False, 'journal': jp.name,
            'photos': sum(len(x['keys']) for x in journal['noms']),
            'noms_traites': [x['nom'] for x in journal['noms']],
            'fiches_retirees': dup}


def annuler_reclassement():
    """Annule le DERNIER reclassement : re-`personne:`, retire `animal:` (uniquement
    ce que ce lot avait pose), restaure les fiches supprimees. Journal renomme .done."""
    docs = SCRIPT_DIR / 'docs'
    # Dernier journal NON VIDE et pas encore annule (.json, pas .json.done).
    jp, journal = None, None
    for f in sorted(docs.glob('undo_reclassement_*.json'), reverse=True):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if data.get('noms'):
            jp, journal = f, data
            break
    if jp is None:
        return {'ok': False, 'error': "Aucun reclassement a annuler."}
    for x in journal.get('noms', []):
        nom = x['nom']
        atag, ptag = f"animal:{nom}", f"personne:{nom}"
        for k in x.get('keys', []):
            _index_remove_person(k, atag)
            _enqueue_person_write(k, atag, 'del')
            _index_add_person(k, ptag)
            _enqueue_person_write(k, ptag, 'add')
        if x.get('fiche') is not None:
            PEOPLE_STORE.set(nom.lower(), x['fiche'])
    STORE.save()
    _invalider_groupes_visages()
    _invalider_groupes_animaux()
    jp.rename(jp.with_name(jp.name + '.done'))
    return {'ok': True, 'photos': sum(len(x.get('keys', [])) for x in journal.get('noms', [])),
            'fiches_restaurees': sum(1 for x in journal.get('noms', []) if x.get('fiche'))}


def reconcile_named_tags():
    """Recovery pérenne : réapplique dans l'index les tags nommés (personne:/
    animal:) pour les photos déjà attribuées à un nom (champ 'faces' des fiches),
    au cas où un ré-tagging IA les aurait effacés de l'index. Ne réécrit PAS les
    fichiers (ils portent déjà le tag) ; respecte les retraits manuels
    ('exclude'). Tourne une fois au démarrage — corrige aussi rétroactivement."""
    time.sleep(35)
    changed = 0
    for store, prefix in ((PEOPLE_STORE, 'personne'), (PETS_STORE, 'animal')):
        for pk, pe in list(store.data.items()):
            if not isinstance(pe, dict):
                continue
            nm = pe.get('name')
            if not nm:
                continue
            tag = f"{prefix}:{nm}"
            exclude = set(pe.get('exclude') or [])
            keys = set()
            for kf in (pe.get('faces') or []):
                if isinstance(kf, (list, tuple)) and len(kf) == 2 and kf[0] not in exclude:
                    keys.add(kf[0])
            for k in keys:
                e = STORE.data.get(k)
                if isinstance(e, dict) and not e.get('failed') and not _kw_has(e, tag):
                    if _index_add_person(k, tag):
                        changed += 1
    if changed:
        STORE.save()
    print(f"  ✓ Réconciliation tags nommés (fiches) : {changed} tag(s) réappliqué(s)")


def reimport_name_tags():
    """Recovery pérenne, source de vérité = les FICHIERS : relit les mots-clés
    des photos et réintègre dans l'index tout tag personne:/animal: qui y
    manque (effacé par un ré-tagging). Une seule passe (marque 'namechk'),
    throttlée et polie avec le NAS. Récupère aussi les noms tagués « à la main ».

    MÊME BUG DE COURSE que les backfills, corrigé le 13/08 : la garde
    `if not EXIFTOOL` était AVANT le sleep, donc cette passe mourait elle aussi
    en silence à chaque démarrage — alors qu'elle sert l'invariant le plus
    sacré du projet (aucun nom humain perdu). Aucune entrée ne portait
    'namechk' : elle n'a jamais tourné."""
    etat = BACKFILL_STATE["noms"]
    time.sleep(45)
    if not _attendre_exiftool("noms"):
        return
    etat["etat"] = "en attente des dates"
    _attendre_backfill("dates", moi="noms")   # un seul balayage du NAS à la fois
    etat["etat"] = "inventaire"
    todo = []
    for n, (k, e) in enumerate(list(STORE.data.items())):
        if not isinstance(e, dict) or e.get('failed') or e.get('namechk'):
            continue
        p = _resolve_key(k)
        if p.suffix.lower() not in IMAGE_EXT:
            continue
        if n % 200 == 0:
            while ui_recent():
                time.sleep(3)
        todo.append((k, p))
    etat["todo"] = len(todo)
    if not todo:
        etat["etat"] = "rien a lire"
        return
    etat["etat"] = "en cours"
    # Exclusions humaines : tag_minuscule -> set(clés) rejetées à la main. Ré-importer
    # un mot-clé depuis le FICHIER ne doit jamais ressusciter une correction (le
    # fichier peut encore porter l'ancien tag si l'écriture XMP de retrait a échoué
    # sur le NAS). Sans ce garde, le curateur re-proposait aussitôt le faux positif.
    excl_par_tag = {}
    for _store, _prefix in ((PEOPLE_STORE, 'personne'), (PETS_STORE, 'animal')):
        for _pk, _pe in _store.data.items():
            if isinstance(_pe, dict):
                for _kx in (_pe.get('exclude') or []):
                    excl_par_tag.setdefault(f"{_prefix}:{_pk}", set()).add(_kx)
    print(f"  🔖 Vérification des tags nommés dans {len(todo)} fichier(s) (fond)…")
    added = 0
    for i in range(0, len(todo), 60):
        while ui_recent() or system_busy():
            time.sleep(3)
        batch = todo[i:i + 60]
        try:
            meta, vus = read_existing_metadata([p for _k, p in batch])
        except Exception:
            meta, vus = {}, set()
        etat["muets"] += sum(1 for _k, p in batch if _pkey(p) not in vus)
        with STORE.lock:
            for k, p in batch:
                e = STORE.data.get(k)
                if not isinstance(e, dict):
                    continue
                if _pkey(p) not in vus:
                    # ExifTool n'a rien dit de ce fichier (NAS muet, timeout) :
                    # surtout NE PAS poser 'namechk'. Le marquer « vérifié »
                    # sans l'avoir lu enterrerait pour toujours les noms que son
                    # XMP contient peut-être — l'invariant sacré du projet.
                    continue
                m = meta.get(_pkey(p))
                if m:
                    kw = e.get('kw_fr') or []
                    low = {str(x).lower() for x in kw}
                    for t in m[0]:
                        tl = str(t).lower()
                        if (tl.startswith('personne:') or tl.startswith('animal:')) and tl not in low:
                            if k in excl_par_tag.get(tl, ()):
                                continue     # correction humaine : ne pas ré-importer
                            kw.append(t)
                            low.add(tl)
                            added += 1
                    e['kw_fr'] = kw
                e['namechk'] = 1
            if (i // 60) % 10 == 0:      # sauvegarde tous les ~10 lots
                STORE._save()
        etat["faits"] = min(i + 60, len(todo))
        etat["trouves"] = added
        time.sleep(0.1)
    STORE.save()
    etat["etat"] = "termine"
    etat["fini_at"] = time.time()
    print(f"  ✓ Tags nommés vérifiés : {added} tag(s) récupéré(s) depuis les fichiers")


def name_cluster(cid, name):
    """Nomme un groupe de visages : voir SubjectStore.name_cluster."""
    return PEOPLE.name_cluster(cid, name)


def find_more(name, limit=300):
    """Propose d'autres photos d'une personne nommée : voir SubjectStore.find_more."""
    return PEOPLE.find_more(name, limit)


def confirm_person(name, keys):
    """Valide l'attribution de photos à une personne : voir SubjectStore.confirm."""
    return PEOPLE.confirm(name, keys)


def people_list():
    """Personnes nommées avec nombre de photos et une vignette."""
    # Comptage insensible à la casse : on regroupe par nom en minuscules, car
    # l'index peut contenir « personne:Nom » (app) ou « personne:nom » (importé).
    tagcount = {}
    for e in STORE.data.values():
        if not isinstance(e, dict):
            continue
        for kw in (e.get('kw_fr') or []):
            if str(kw).lower().startswith('personne:'):
                key = str(kw)[9:].strip().lower()
                tagcount[key] = tagcount.get(key, 0) + 1
    out = []
    for pk, pe in PEOPLE_STORE.data.items():
        if not isinstance(pe, dict):
            continue
        nm = pe.get('name', pk)
        crop = None
        # avatar = visage le plus représentatif (calculé par le curateur)
        av = pe.get('avatar')
        if isinstance(av, list) and len(av) == 2:
            fe = FACE_STORE.data.get(av[0])
            if isinstance(fe, dict):
                faces = fe.get('faces') or []
                if faces:
                    ai = av[1] if 0 <= av[1] < len(faces) else 0
                    crop = _crop_url(av[0], ai)
        if crop is None:   # repli tant que le curateur n'a pas encore tourné
            for k, e in STORE.data.items():
                if _kw_has(e, f"personne:{nm}"):
                    fe = FACE_STORE.data.get(k)
                    if isinstance(fe, dict) and fe.get('faces'):
                        crop = _crop_url(k, 0)
                        break
        # `contestes` : les jugements perdus que la fiche garde en mémoire —
        # comptés ici pour que la carte le DISE (chantier 17, étape 2).
        out.append({"name": nm, "photos": tagcount.get(nm.strip().lower(), 0),
                    "crop": crop,
                    "contestes": len(_auteurs.contestations(pe))})
    out.sort(key=lambda x: -x["photos"])
    return out


def places_list():
    """Lieux nommes (3e type de sujet) avec nombre de photos et une vignette.

    Deux sources, fusionnees :
      1. GEOCODAGE GPS (prioritaire) : gps_places_connus() = {cle: libelle},
         precalcule hors ligne par enrichir_lieux.py. Vide tant que le gazetteer
         + enrichir_lieux.py --ecrire n'ont pas tourne : la page reste alors
         alimentee par le repli ci-dessous.
      2. REPLI DOSSIERS : lieux_connus() (lieux.txt / heuristique), retrouves par
         faits_vue.lieux_du_chemin — SEGMENTS entiers, pas sous-chaine (19/08,
         chantier 14a-i : « Ins » comptait 493 photos dont 442 venaient de
         « Cousins&Cousines »). Meme appel que _cles_du_lieu, pour que /sujets
         et la barre de recherche parlent des memes lieux : une seule regle.

    Le GPS prime : une photo deja nommee par GPS n'est pas re-comptee par le
    chemin. Lecture seule, tout en memoire (index + gps_places.json en cache) :
    aucun acces NAS -> pas de note_heavy_activity.

    La vignette passe par /api/thumb (residu de l'audit O1, corrige le 13/08) :
    cette section chargeait encore 25 ORIGINAUX pleine resolution (2-6 Mo lus
    sur le NAS par carte affichee) la ou toutes les autres grilles sont passees
    aux vignettes 512 px. Les cartes Personnes/Animaux, elles, affichent une
    decoupe /api/facecrop : deja legere, rien a changer. /api/thumb redirige
    vers l'original s'il ne sait pas vignetter (video, HEIC, PIL absent), donc
    le client n'a aucun cas particulier a gerer."""
    roots = media_roots()
    gps = gps_places_connus()               # {cle: libelle} ; {} si non active
    agg = {}                                # normalise -> {"name", "keys"(set)}
    for k, label in gps.items():
        if k not in STORE.data:             # cle fantome : on ignore
            continue
        nk = _sans_accents(label)
        if not nk:
            continue
        agg.setdefault(nk, {"name": label, "keys": set()})["keys"].add(k)
    gps_keys = set(gps)                      # photos deja attribuees par GPS
    index = lieux_connus()                  # {normalise: libelle}
    if index:
        import faits_vue
        for k in list(STORE.data):
            if k in gps_keys:               # le GPS prime : pas de double compte
                continue
            # tous=True : une photo compte dans CHAQUE lieu qu'elle designe
            # (« France & Belgique » est les deux) ; avec_fichier=True : 52
            # photos ne nomment leur lieu que la (mesure du 19/08).
            for lbl in faits_vue.lieux_du_chemin(k, index, roots, tous=True,
                                                 avec_fichier=True):
                agg.setdefault(_sans_accents(lbl),
                               {"name": lbl, "keys": set()})["keys"].add(k)
    out = []
    for a in agg.values():
        keys = a["keys"]
        if not keys:
            continue
        crop = None
        for k in keys:                      # premiere photo servable = vignette
            # _url_for_key reste le test de SERVABILITE (cle sous une racine) ;
            # seule l'URL rendue change : vignette au lieu de l'original.
            if _url_for_key(k, roots):
                # safe='' : meme encodage que le encodeURIComponent des pages
                # (les cles Windows portent antislashs et espaces).
                crop = ('/api/thumb?key=' + urllib.parse.quote(k, safe='')
                        + '&s=512')
                break
        out.append({"name": a["name"], "photos": len(keys), "crop": crop})
    out.sort(key=lambda x: -x["photos"])
    return out


def person_photos(name, limit=2000, order='worst', light=False):
    """Photos taguées personne:Nom, pour révision/correction. Pour chaque photo,
    on identifie le visage qui correspond LE MIEUX à la signature de la personne
    (pas forcément le visage n°0) et on affiche CE visage. Trié du moins au plus
    ressemblant (order='worst') → les faux positifs remontent en tête ; ou du
    plus au moins ressemblant (order='best') pour le choix de références.
    light=True → charge utile réduite (sans dossier/mots-clés/date)."""
    return PEOPLE.photos(name, limit, order, light)


def sujet_contestes(store, name):
    """Les jugements CONTESTÉS d'une fiche, prêts à MONTRER (chantier 17,
    étape 2). La règle est `auteurs.contestations` (pure) ; ici on n'ajoute
    que ce que la page ne peut pas calculer : la vignette et le lien. Une
    fiche sans `auteurs` ou inconnue rend [] — une liste vide, pas une erreur :
    « rien de contesté » est un état normal, pas une absence de donnée."""
    pe = store.data.get((name or '').strip().lower())
    if not isinstance(pe, dict):
        return []
    roots = media_roots()
    out = []
    for c in _auteurs.contestations(pe):
        k = c['chemin']
        i = c['idx'] if c['idx'] is not None else 0
        c['name'] = Path(k).name
        c['url'] = _url_for_key(k, roots)
        c['crop_url'] = _crop_url(k, i) if FACE_STORE.data.get(k) else None
        c['proprietaire'] = _auteurs.proprietaire_de(k)
        out.append(c)
    return out


def person_slideshow_list(name, limit=8000):
    """Liste LÉGÈRE des photos d'une personne pour le diaporama : uniquement les
    champs utiles à l'affichage (url, nom, tags, date, dossier). Contrairement à
    person_photos(), aucun calcul de similarité de visage (numpy) ni de vignette
    → réponse quasi instantanée, même pour une personne avec beaucoup de photos."""
    tag = f"personne:{name}"
    roots = media_roots()
    out = []
    for k, e in STORE.data.items():
        if not isinstance(e, dict) or e.get('failed'):
            continue
        if not _kw_has(e, tag):
            continue
        url = _url_for_key(k, roots)
        if not url:
            continue
        kw = list(dict.fromkeys((e.get('kw_fr') or []) + (e.get('kw_en') or [])))
        folder, gurl = _folder_link_for_key(k, roots)
        out.append({"url": url, "name": Path(k).name, "key": k,
                    "taken": _best_time(k, e), "kw": kw,
                    "folder": folder, "gurl": gurl})
        if len(out) >= limit:
            break
    return out


def _ref_embeddings(ref_keys):
    """Embeddings de référence : le visage principal (0) de chaque photo choisie."""
    refs = []
    for rk in ref_keys:
        fe = FACE_STORE.data.get(rk)
        if isinstance(fe, dict):
            faces = fe.get('faces') or []
            if faces and faces[0].get('emb'):
                try:
                    refs.append(_emb_from_b64(faces[0]['emb']))
                except Exception:
                    pass
    return refs


def ref_scores(name, ref_keys):
    """Pour chaque photo taguée « name », score de ressemblance à la référence.
    On prend la MOYENNE de similarité sur toutes les références choisies (pas le
    max) : un intrus qui ne colle qu'à une seule référence obtient un score
    faible, alors qu'un vrai visage, proche de toutes, reste élevé. Trié du pire
    au meilleur (faux positifs en tête)."""
    import numpy as np
    refs = _ref_embeddings(ref_keys)
    if not refs:
        return []
    # mean(R @ emb) == emb · mean(R) : la moyenne sur les references se ramene a
    # un produit scalaire contre le vecteur moyen -> scoring vectorise (helper).
    sig = np.stack(refs).mean(axis=0)
    tag = f"personne:{name}"
    ref_set = set(ref_keys)
    roots = media_roots()   # UNE fois : _url_for_key(k) sans roots le recalculait
    out = []                # par photo (lecture fichiers + is_dir NAS x milliers).
    for k, e, sim, _idx in _best_sims_for_tag(tag, sig, FACE_STORE, 'faces'):
        out.append({"key": k, "sim": (sim if sim is not None else -1.0),
                    "crop_url": _crop_url(k, 0), "url": _url_for_key(k, roots),
                    "name": Path(k).name, "is_ref": k in ref_set})
    out.sort(key=lambda x: x["sim"])
    return out


def set_reference(name, ref_keys):
    """Remplace les références d'une personne par des références « propres »
    (les visages des photos choisies), pour assainir les futures recherches
    et le masquage au regroupement."""
    name = (name or "").strip()[:60]
    refs = _ref_embeddings(ref_keys)
    if not name or not refs:
        return 0
    import numpy as np
    pk = name.lower()
    pe = PEOPLE_STORE.data.get(pk) or {"name": name, "refs": [], "at": time.time()}
    pe["name"] = name
    pe["refs"] = [base64.b64encode(v.astype(np.float16).tobytes()).decode()
                  for v in refs][:80]
    PEOPLE_STORE.set(pk, pe)
    return len(refs)


def untag_person(name, keys):
    """Retire personne:Nom de photos mal attribuées : voir SubjectStore.untag."""
    return PEOPLE.untag(name, keys)


def delete_person(name):
    """Supprime entièrement une personne : voir SubjectStore.delete."""
    return PEOPLE.delete(name)


def rename_person(old, new):
    """Renomme une personne : voir SubjectStore.rename."""
    return PEOPLE.rename(old, new)


# ────────────── Curateur : suggestions d'amélioration (Phase A) ──────────────
# Compare en continu les visages aux « signatures » (centroïdes) des personnes
# nommées et propose : faux positifs à retirer, nouveaux matchs à ajouter,
# doublons de personnes à fusionner. NE MODIFIE RIEN seul — tout passe par ta
# validation. Les signatures ne grandissent que sur confirmation (anti-dérive).

CURATOR_INTERVAL = 240        # s entre deux passes (quand la machine est calme)
CUR_ADD_SIM = 0.40            # proposer un ajout au-dessus de ce score
CUR_ADD_STRONG = 0.55         # ajout « franc » (haute confiance)
CUR_FP_SIM = 0.30             # sous ce score, un visage tagué est un faux positif probable
CUR_FP_STRONG = 0.20          # faux positif « franc »
CUR_MERGE_SIM = 0.55          # fusion de deux personnes (signatures très proches)
CUR_MAX_SUGGEST = 400         # plafond total de suggestions
# Auto-ajout : au-dessus de ce score, on rattache automatiquement (sans validation),
# À CONDITION d'une marge nette avec la 2e personne la plus proche (anti-confusion).
# Les auto-ajouts N'ENRICHISSENT PAS les signatures (anti-dérive) et sont réversibles.
AUTO_ADD_ENABLE = True
AUTO_ADD_SIM = 0.40           # auto-ajout à partir de ce score (abaissé sur observation)
AUTO_ADD_MARGIN = 0.10        # best - 2e meilleur doit dépasser ça (garde-fou anti-confusion)
# Mesuré le 30/07/2026 sur le corpus réel : 3 299 visages sur 3 343 candidats
# passent en automatique (99 %). Le résidu n'est PAS un défaut de seuil : ce
# sont les visages qu'une deuxième personne dispute (Florine/Flo, Mutz/Caline).
# Abaisser la marge ne les résoudrait pas, cela trancherait au hasard.
# Réglable sans toucher au code : créer seuils.txt avec des lignes
# « AUTO_ADD_MARGIN = 0.05 ».
try:
    for _l in (SCRIPT_DIR / "seuils.txt").read_text(encoding='utf-8').splitlines():
        _l = _l.split('#')[0].strip()
        if '=' not in _l:
            continue
        _n, _v = (x.strip() for x in _l.split('=', 1))
        if _n in ('AUTO_ADD_SIM', 'AUTO_ADD_MARGIN', 'FACE_MATCH_SIM',
                  'CAT_AUTO_SIM', 'CAT_AUTO_MARGIN', 'PET_CLUSTER_SIM',
                  'PET_MATCH_SIM', 'FACE_CLUSTER_SIM'):
            try:
                globals()[_n] = float(_v)
                print(f"  ⚙ seuils.txt : {_n} = {_v}")
            except ValueError:
                pass
except OSError:
    pass
AUTO_LOG_MAX = 500
AUTO_LOG = []                 # journal réversible des ajouts automatiques (récent)
SUGGEST_CACHE = {"at": 0.0, "building": False, "items": []}
SUGGEST_LOCK = threading.Lock()

# ── Journal des jugements humains (instrumenter le geste de vérité terrain) ──
# Chaque décision prise dans la file « À vérifier » (accepter, rejeter,
# corriger, « pas un visage ») est datée et append-only : une ligne JSON par
# geste dans journal_jugements.jsonl (LOCAL, comme photos.db — jamais le NAS).
# Sert deux métriques honnêtes : jugements/minute et erreurs découvertes —
# jamais l'accord modèle-humain (circulaire). L'export/sauvegarde hors site des
# jugements est un chantier séparé (ROADMAP « assurance-vie »).
JUGEMENTS_PATH = SCRIPT_DIR / "journal_jugements.jsonl"
JUGEMENTS_LOCK = threading.Lock()
JUGEMENTS_RECENTS = []        # miroir mémoire (séance en cours) pour les stats
JUGEMENTS_PAUSE = 300         # > 5 min sans geste = nouvelle séance


def _journal_jugement(evt):
    """Consigne un jugement humain (journal fichier + miroir mémoire).

    Best-effort : une panne d'écriture ne fait jamais échouer le geste."""
    evt = dict(evt)
    evt["ts"] = round(time.time(), 3)
    with JUGEMENTS_LOCK:
        JUGEMENTS_RECENTS.append(evt)
        if len(JUGEMENTS_RECENTS) > 2000:
            del JUGEMENTS_RECENTS[:-2000]
        try:
            with open(JUGEMENTS_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"  ⚠ Journal des jugements : {e}")


def _stats_seance():
    """Métriques de la séance en cours (jugements/minute, erreurs découvertes).

    Séance = suite de jugements séparés de moins de JUGEMENTS_PAUSE secondes,
    finissant maintenant. Le rythme n'est affiché qu'après 30 s de recul."""
    now = time.time()
    with JUGEMENTS_LOCK:
        sel = []
        fin = now
        for evt in reversed(JUGEMENTS_RECENTS):
            if fin - evt["ts"] > JUGEMENTS_PAUSE:
                break
            sel.append(evt)
            fin = evt["ts"]
    if not sel:
        return {"n": 0}
    n = len(sel)
    conf = sum(1 for e in sel if e.get("verdict") == 'confirmation')
    err = sum(1 for e in sel if e.get("verdict") == 'erreur_decouverte')
    duree = max(0.0, sel[0]["ts"] - sel[-1]["ts"])   # sel est en ordre inverse
    par_min = round(n / (duree / 60.0), 1) if duree >= 30 else None
    return {"n": n, "confirmations": conf, "erreurs": err,
            "duree_s": int(duree), "par_minute": par_min}


# ────────────── Tranche a juger : mesurer un seuil sans le bouger ────────────
# `mesure_tranche_seuil.py` tire un echantillon UNIFORME de propositions dont le
# score tombe dans une tranche donnee (0,35-0,40 : sous CUR_ADD_SIM, donc
# invisible aujourd'hui) et l'ecrit dans `_tranche_a_juger.json`. La page
# /tranche le donne a juger — et RIEN D'AUTRE : aucun tag, aucun nom, aucune
# fiche touchee. Un verdict est une MESURE ; le confondre avec un geste rendrait
# le chiffre inutilisable, puisqu'on mesurerait un seuil avec des rattachements
# qu'on vient soi-meme de poser.
# Le taux et son intervalle se lisent par `mesure_tranche_seuil.py --bilan` :
# le serveur COLLECTE, le banc CONCLUT. Les memes mots de verdict des deux
# cotes (juste / faux / indecidable), sinon le banc compterait autre chose.
# La PLANCHE DE REFERENCE, elle, n'est pas dans le tirage : elle est relue
# dans la fiche a chaque affichage (`_tranche_refs_vivantes`). Un tirage se
# fige, une reference se lit maintenant.
TRANCHE_A_JUGER = SCRIPT_DIR / "_tranche_a_juger.json"
TRANCHE_JUGEMENTS = SCRIPT_DIR / "_tranche_jugements.json"
TRANCHE_VERDICTS = ('juste', 'faux', 'indecidable')
TRANCHE_REFS_MAX = 3   # visages de reference montres a cote de la proposition
TRANCHE_LOCK = threading.Lock()


def _tranche_id(key, i, person):
    """Identite d'une proposition : la photo, LE VISAGE, et le nom propose.

    L'index compte : deux visages de la meme photo peuvent recevoir deux
    propositions differentes, et les confondre ecraserait un verdict."""
    return f"{key}|{i}|{person}"


def _tranche_lire_jugements():
    """Verdicts deja poses. Fichier absent ou illisible = seance vierge : une
    page de jugement ne doit jamais tomber en panne parce qu'un fichier de
    travail manque."""
    try:
        d = json.loads(TRANCHE_JUGEMENTS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    v = d.get('verdicts') if isinstance(d, dict) else None
    return v if isinstance(v, dict) else {}


def _tranche_ecrire_jugements(verdicts):
    """Ecriture atomique (.tmp puis os.replace, invariant 2), sous TRANCHE_LOCK.

    L'avancement survit a un redemarrage : trente jugements, c'est une seance
    qu'on ne recommence pas parce que le serveur a redemarre entre deux."""
    tmp = TRANCHE_JUGEMENTS.with_suffix('.tmp')
    tmp.write_text(json.dumps({"verdicts": verdicts}, ensure_ascii=False,
                              indent=1), encoding='utf-8')
    os.replace(tmp, TRANCHE_JUGEMENTS)


# ───────────── Le RESIDU du recalage : ce qui ne se juge qu'a l'oeil ────────
# `recale_rattachements` REFUSE de reparer un couple quand la fiche cite
# plusieurs visages de la MEME photo : ou la personne y est vraiment detectee
# deux fois, ou un index a glisse et designe son voisin. Le score ne departage
# pas, et trancher au hasard deplacerait un jugement humain.
# `mesure_rattachements.py --residu` ecrit ces cas, la page /residu les donne a
# juger, et le RETRAIT reste un geste de Mike : la page COLLECTE, le banc
# CONCLUT (`--bilan-residu`). Meme partage que la tranche, et pour la meme
# raison — un verdict melange au geste qu'il gouverne ne mesure plus rien.
RESIDU_A_JUGER = SCRIPT_DIR / "_residu_a_juger.json"
RESIDU_JUGEMENTS = SCRIPT_DIR / "_residu_jugements.json"
RESIDU_VERDICTS = ('juge', 'indecidable')
RESIDU_LOCK = threading.Lock()


_DIMS_PHOTO = {}
_DIMS_LOCK = threading.Lock()


def _dimensions_photo(key):
    """(largeur, hauteur) de la photo REDRESSEE, ou None.

    Les `bbox` des visages sont exprimees dans l'espace redresse : les deux
    producteurs (`_serve_facecrop`, `_serve_thumb`) appliquent
    `exif_transpose` AVANT de decouper. Pour poser un cadre en POURCENTAGE
    par-dessus la vignette, il faut donc les memes dimensions — d'ou la
    lecture de l'orientation EXIF plutot qu'un `size` brut, qui donnerait un
    cadre pivote sur toute photo prise a la verticale.

    Seul l'en-tete du fichier est lu (PIL est paresseux), et le resultat est
    mis en cache : les dimensions d'une photo ne changent pas.
    """
    with _DIMS_LOCK:
        if key in _DIMS_PHOTO:
            return _DIMS_PHOTO[key]
    dims = None
    if PIL_OK:
        try:
            path = _resolve_key(key)
            if path.is_file():
                with Image.open(path) as im:
                    w, h = im.size
                    try:
                        orient = (im.getexif() or {}).get(0x0112)
                    except Exception:                          # noqa: BLE001
                        orient = None
                    if orient in (5, 6, 7, 8):
                        w, h = h, w
                    dims = (w, h)
        except Exception:                                      # noqa: BLE001
            dims = None
    with _DIMS_LOCK:
        _DIMS_PHOTO[key] = dims
    return dims


def _boite_en_fractions(bbox, dims):
    """Un `bbox` en pixels devient (gauche, haut, largeur, hauteur) en % —
    le client n'a alors rien a savoir de la taille de la vignette."""
    if not (dims and isinstance(bbox, (list, tuple)) and len(bbox) == 4):
        return None
    w, h = dims
    if not (w and h):
        return None
    x1, y1, x2, y2 = [float(v) for v in bbox]
    return [round(100.0 * x1 / w, 3), round(100.0 * y1 / h, 3),
            round(100.0 * (x2 - x1) / w, 3), round(100.0 * (y2 - y1) / h, 3)]


def _residu_id(key, person):
    """Identite d'un cas : la photo ET la personne.

    Pas le visage : le cas porte sur TOUS les visages cites de cette photo par
    cette fiche — c'est justement leur mise en concurrence qui est la question.
    """
    return f"{key}|{person}"


def _residu_lire_jugements():
    try:
        d = json.loads(RESIDU_JUGEMENTS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    v = d.get('verdicts') if isinstance(d, dict) else None
    return v if isinstance(v, dict) else {}


def _residu_ecrire_jugements(verdicts):
    """Ecriture atomique (.tmp puis os.replace, invariant 2), sous RESIDU_LOCK."""
    tmp = RESIDU_JUGEMENTS.with_suffix('.tmp')
    tmp.write_text(json.dumps({"verdicts": verdicts}, ensure_ascii=False,
                              indent=1), encoding='utf-8')
    os.replace(tmp, RESIDU_JUGEMENTS)


def _tranche_fiches_par_nom():
    """Les fiches de personnes indexees par nom en minuscules, en une passe."""
    out = {}
    for pk, pe in PEOPLE_STORE.data.items():
        if isinstance(pe, dict):
            out[str(pe.get('name', pk)).lower()] = pe
    return out


def _tranche_refs_vivantes(person, fiches):
    """Les visages de reference d'une personne, LUS MAINTENANT.

    Le 22/08, l'echantillon avait ete tire a 21:26 et le recalage des
    rattachements applique a 22:19 : la page servait encore les references
    d'AVANT la reparation. Trois planches sur trente montraient donc le visage
    de quelqu'un d'autre — dont Didier et Mathieu, exactement les deux fiches
    signalees a l'oeil la veille, et sur lesquelles aucune amelioration
    n'etait possible puisque c'etait l'image d'avant.

    Figer l'ECHANTILLON est juste : c'est le tirage, et un tirage qui bouge
    n'est plus uniforme. Figer la REFERENCE est faux : la reference n'est pas
    ce qu'on mesure, c'est ce CONTRE QUOI on mesure, et elle doit dire l'etat
    du fonds a l'instant du jugement. Une planche perimee ne trompe pas au
    hasard : elle trompe precisement la ou une reparation vient de passer.

    L'avatar d'abord — c'est le portrait que le curateur juge le plus
    representatif —, puis les rattachements, sans doublon.
    """
    pe = fiches.get(str(person or '').lower())
    if not isinstance(pe, dict):
        return []
    vus, liste = set(), []
    for source in ((pe.get('avatar'),), (pe.get('faces') or ())):
        for kf in source:
            if len(liste) >= TRANCHE_REFS_MAX:
                break
            if not isinstance(kf, (list, tuple)) or len(kf) != 2:
                continue
            try:
                couple = (kf[0], int(kf[1] or 0))
            except (TypeError, ValueError):
                continue
            if couple in vus:
                continue
            vus.add(couple)
            liste.append(couple)
    return liste


def _refs_vecteurs(pe):
    vs = []
    for s in (pe.get('refs') or []):
        try:
            vs.append(_emb_from_b64(s))
        except Exception:
            pass
    return vs


def person_centroid(pe):
    """Signature d'une personne = moyenne normalisée de ses embeddings de réf."""
    import numpy as np
    vs = _refs_vecteurs(pe)
    if not vs:
        return None
    c = np.mean(np.stack(vs), axis=0)
    n = np.linalg.norm(c)
    return c / n if n else c


def person_prototypes(pe):
    """Plusieurs facettes plutôt qu'une moyenne — voir classifier.py.

    Une personne photographiée sur vingt ans n'est pas un point : la moyenne
    tombe entre les modes et se rapproche mécaniquement des autres fiches.

    Mesuré sur ce corpus (389 visages de test, sans fuite) : 3 cas corrigés,
    0 cassé, et 2 des 16 cas ambigus tranchés. Le gain n'est pas
    statistiquement significatif (p ≈ 0,25) mais il est sans risque, d'où
    l'adoption. Le même essai sur les ANIMAUX donne l'inverse (99,8 % → 99,6 %) :
    ils gardent donc le centroïde unique. Voir eval/DECISIONS.md.
    """
    vs = _refs_vecteurs(pe)
    if not vs:
        return None
    try:
        from classifier import prototypes
        return prototypes(vs)
    except Exception:                                         # noqa: BLE001
        c = person_centroid(pe)
        return None if c is None else c.reshape(1, -1)


def _person_add_ref(name, key, i):
    """Enrichit la signature avec un visage confirmé (clé, index)."""
    fe = FACE_STORE.data.get(key)
    if not isinstance(fe, dict):
        return
    faces = fe.get('faces') or []
    if not faces:
        return
    if i < 0 or i >= len(faces):
        i = 0
    emb = faces[i].get('emb')
    if not emb:
        return
    pk = name.lower()
    pe = PEOPLE_STORE.data.get(pk)
    if not isinstance(pe, dict):
        return
    refs = pe.get('refs') or []
    if emb not in refs:
        refs.append(emb)
    pe['refs'] = refs[-150:]
    PEOPLE_STORE.set(pk, pe)


def _person_add_set(name, field, key):
    pk = name.lower()
    pe = PEOPLE_STORE.data.get(pk)
    if not isinstance(pe, dict):
        return
    s = set(pe.get(field) or [])
    s.add(key)
    pe[field] = list(s)
    PEOPLE_STORE.set(pk, pe)


def _auto_add(name, key, i, sim):
    """Rattache automatiquement un visage à une personne : tag (index + fichier),
    journalisé et RÉVERSIBLE, SANS enrichir la signature (anti-dérive)."""
    tag = f"personne:{name}"
    if not _index_add_person(key, tag):
        return False
    _enqueue_person_write(key, tag, 'add')
    AUTO_LOG.append({"person": name, "key": key, "i": int(i), "sim": round(float(sim), 3),
                     "crop_url": _crop_url(key, i), "url": _url_for_key(key), "at": time.time()})
    if len(AUTO_LOG) > AUTO_LOG_MAX:
        del AUTO_LOG[:-AUTO_LOG_MAX]
    return True


def build_suggestions():
    """Recalcule la file de suggestions (tâche de fond, mise en cache)."""
    with SUGGEST_LOCK:
        if SUGGEST_CACHE["building"]:
            return
        SUGGEST_CACHE["building"] = True
    t0 = time.time()
    try:
        import numpy as np
        persons = []
        for pk, pe in PEOPLE_STORE.data.items():
            if not isinstance(pe, dict):
                continue
            P = person_prototypes(pe)
            if P is None or not len(P):
                continue
            persons.append({"name": pe.get('name', pk), "c": P[0], "P": P,
                            "exclude": set(pe.get('exclude') or []),
                            "confirmed": set(pe.get('confirmed') or []),
                            "nomerge": set(pe.get('nomerge') or [])})
        items = []
        if persons:
            # Chaque personne fournit PLUSIEURS lignes (ses facettes) ; le
            # score d'une personne est le maximum sur ses lignes. `proprio`
            # associe chaque ligne à sa personne.
            dim = persons[0]["P"].shape[1]
            lignes, proprio = [], []
            for idx, p in enumerate(persons):
                if p["P"].shape[1] != dim:
                    continue
                for row in p["P"]:
                    lignes.append(row)
                    proprio.append(idx)
            Cproto = np.stack(lignes)
            proprio = np.asarray(proprio)
            C = np.stack([p["c"] for p in persons])
            names = [p["name"] for p in persons]
            # Indexé en MINUSCULES : l'index peut porter « personne:flo » là où
            # la fiche dit « Flo ». Cherché en casse sensible, ce tag n'était
            # jamais visité par le contrôle REMOVE — donc jamais auto-guéri,
            # même quand la décision humaine disait de le retirer (I7).
            pidx = {str(nm).lower(): n for n, nm in enumerate(names)}
            # ADD : visage non attribué proche d'une signature
            add_seen = set()
            auto_count = 0
            best_av = {}          # avatar : meilleur visage par personne (index → (sim,clé,i))
            # Garde-fou « clés fantômes » (cas ARZOPA) : une même photo pouvait
            # exister sous une clé correcte (« ads\ARZOPA\… ») ET une clé malformée
            # (« ARZOPA\… », sans la racine) qui ne résout vers aucun fichier →
            # /api/facecrop 404 → carte sans vignette. On écarte ces propositions,
            # mais SEULEMENT si la racine est joignable, jamais quand le NAS est
            # déconnecté (sinon tout le corpus passerait pour disparu — leçon de
            # verifier_orphelins). Ne touche QUE des propositions : aucun nom perdu.
            def _racine_ok(p):
                try:
                    return Path(p).exists()
                except OSError:
                    return False
            _up_ok = _racine_ok(UPLOAD_DIR)
            for k, e in list(FACE_STORE.data.items()):
                if not isinstance(e, dict) or e.get('failed'):
                    continue
                se = STORE.data.get(k)
                # Noms NORMALISÉS : « personne:flo » dit que la photo porte
                # déjà Flo. Comparé en casse sensible, il ne le disait pas — et
                # le curateur proposait (ou ajoutait) un second tag du même nom.
                ptags = set()
                if isinstance(se, dict):
                    for kw in (se.get('kw_fr') or []):
                        pn = parse_tag_nomme(kw)
                        if pn and pn[0] == 'personne':
                            ptags.add(pn[1].lower())
                for i, f in enumerate(e.get('faces') or []):
                    # 12b : une decoupe marquee « pas un visage » (chat, objet)
                    # ne doit jamais etre proposee au rattachement a une personne.
                    # Idem un visage archive « inconnu » : hors file « A verifier »
                    # tant qu'il n'est pas re-tague.
                    if f.get('pas_visage') or f.get('inconnu'):
                        continue
                    emb = f.get('emb')
                    if not emb:
                        continue
                    try:
                        v = _emb_from_b64(emb)
                    except Exception:
                        continue
                    # max des facettes, par personne
                    brut = Cproto @ v
                    sims = np.full(len(persons), -2.0, dtype=np.float32)
                    np.maximum.at(sims, proprio, brut)
                    j = int(np.argmax(sims))
                    best = float(sims[j])
                    # avatar : on retient le meilleur visage de chaque personne
                    if best > best_av.get(j, (-9.0,))[0]:
                        best_av[j] = (best, k, i)
                    # 2e meilleure personne, pour le contrôle de marge (anti-confusion)
                    second = -1.0
                    if len(sims) >= 2:
                        second = float(np.partition(sims, -2)[-2])
                    nm = names[j]
                    if (nm.lower() in ptags or k in persons[j]["exclude"]
                            or best < CUR_ADD_SIM):
                        continue
                    kk = (nm, k)
                    if kk in add_seen:
                        continue
                    add_seen.add(kk)
                    # Clé fantôme : proposition (ou auto-attribution) écartée si le
                    # fichier ne se résout pas ET que sa racine est joignable. Un
                    # seul is_file() local, sur les vrais candidats uniquement.
                    _rp = _resolve_key(k)
                    _root_ok = _racine_ok(Path(_rp.anchor)) if _rp.is_absolute() else _up_ok
                    if _root_ok:
                        try:
                            if not _rp.is_file():
                                continue
                        except OSError:
                            pass
                    margin = best - second
                    if AUTO_ADD_ENABLE and best >= AUTO_ADD_SIM and margin >= AUTO_ADD_MARGIN:
                        if _auto_add(nm, k, i, best):
                            auto_count += 1
                        continue
                    # Le concurrent : c'est LUI qui explique la question posée.
                    # Sans cette information, l'utilisateur ne peut pas savoir
                    # pourquoi le rattachement n'a pas été fait tout seul.
                    rival = ""
                    if len(sims) >= 2:
                        ordre = np.argsort(sims)[::-1]
                        rival = names[int(ordre[1])]
                    items.append({"type": "add", "person": nm, "key": k, "i": i,
                                  "sim": round(best, 3), "crop_url": _crop_url(k, i),
                                  "box": _boite_visage(k, i),
                                  "url": _url_for_key(k), "strong": best >= CUR_ADD_STRONG,
                                  "margin": round(margin, 3),
                                  "rival": rival, "rival_sim": round(second, 3)})
            if auto_count:
                STORE.save()
                print(f"  🤖 Auto-ajout : {auto_count} visage(s) rattaché(s) (score ≥ "
                      f"{AUTO_ADD_SIM}, marge ≥ {AUTO_ADD_MARGIN})")
            # met à jour l'avatar (visage le plus représentatif) de chaque personne
            for jj, (_sv, ak, ai) in best_av.items():
                pe2 = PEOPLE_STORE.data.get(names[jj].lower())
                if isinstance(pe2, dict):
                    pe2['avatar'] = [ak, ai]
            if best_av:
                PEOPLE_STORE.save()
            # REMOVE : photo taguée mais loin de la signature (faux positif)
            rm_seen = set()
            fp_healed = 0        # tags erronés re-retirés (exclusion humaine ré-appliquée)
            for k, se in list(STORE.data.items()):
                if not isinstance(se, dict):
                    continue
                ptags = [pn[1] for pn in
                         (parse_tag_nomme(kw) for kw in (se.get('kw_fr') or []))
                         if pn and pn[0] == 'personne']
                if not ptags:
                    continue
                fe = FACE_STORE.data.get(k)
                fvecs = []   # (index_visage, vecteur)
                for fi, f in enumerate((fe.get('faces') if isinstance(fe, dict) else None) or []):
                    emb = f.get('emb')
                    if emb:
                        try:
                            fvecs.append((fi, _emb_from_b64(emb)))
                        except Exception:
                            pass
                if not fvecs:
                    continue
                for nm_tag in ptags:
                    j = pidx.get(nm_tag.lower())
                    if j is None:
                        continue
                    # La FICHE fait foi sur l'orthographe : ce qui part dans une
                    # suggestion ou un retrait porte SON nom, pas l'écriture
                    # trouvée dans l'index.
                    nm = names[j]
                    p = persons[j]
                    if k in p["confirmed"]:
                        continue
                    # Correction humaine FAISANT AUTORITÉ. Une photo EXCLUE d'une
                    # personne (rejet « faux positif ? » ou correction vers un autre
                    # nom) ne doit JAMAIS être re-signalée. `exclude` était honoré à
                    # l'AJOUT (plus haut) mais PAS ici : dès que le tag erroné
                    # resurgissait (ré-import XMP, rescan d'un fichier modifié, clé en
                    # double), la même carte revenait — d'où « je corrige et ça revient
                    # sans fin ». On ré-applique la décision : retirer le tag, ne rien
                    # proposer. Idempotent (une passe ne fait rien si le tag est déjà
                    # parti) ; le nom Dévi posé par la correction n'est pas touché.
                    if k in p["exclude"]:
                        if _index_remove_person(k, f"personne:{nm}"):
                            _enqueue_person_write(k, f"personne:{nm}", 'del')
                            fp_healed += 1
                        continue
                    # meilleur visage de la photo POUR CETTE personne.
                    # MÊME score que le chemin d'ajout : le maximum sur les
                    # facettes. Scorer l'ajout et le retrait différemment
                    # produirait des visages ajoutés puis aussitôt signalés
                    # comme faux positifs.
                    bi, bestsim = fvecs[0][0], -2.0
                    for fi, v in fvecs:
                        s = float(np.max(p["P"] @ v))
                        if s > bestsim:
                            bestsim, bi = s, fi
                    if bestsim < CUR_FP_SIM:
                        kk = (nm, k)
                        if kk not in rm_seen:
                            rm_seen.add(kk)
                            items.append({"type": "remove", "person": nm, "key": k, "i": bi,
                                          "sim": round(bestsim, 3), "crop_url": _crop_url(k, bi),
                                          "box": _boite_visage(k, bi),
                                          "url": _url_for_key(k), "strong": bestsim < CUR_FP_STRONG})
            if fp_healed:
                STORE.save()
                print(f"  🩹 Faux positifs : {fp_healed} tag(s) erroné(s) re-retiré(s) "
                      "(exclusion humaine ré-appliquée)")
            # MERGE : deux signatures très proches
            for a in range(len(persons)):
                for b in range(a + 1, len(persons)):
                    if names[b] in persons[a]["nomerge"]:
                        continue
                    s = float(persons[a]["c"] @ persons[b]["c"])
                    if s >= CUR_MERGE_SIM:
                        items.append({"type": "merge", "a": names[a], "b": names[b],
                                      "sim": round(s, 3), "strong": True})
        # Tri de la file (priorité n°1 du ROADMAP : instrumenter le geste).
        # - remove d'abord : chaque faux positif retiré est une erreur corrigée ;
        #   score CROISSANT (le plus flagrant en tête).
        # - add ensuite, par MARGE CROISSANTE avec la 2e personne (incertitude
        #   du modèle). JAMAIS par score absolu : trier par score ferait juger
        #   d'abord ce que le modèle croit déjà savoir (circularité) ; la marge
        #   place le jugement humain là où il informe le plus.
        order = {"remove": 0, "merge": 1, "add": 2}

        def _cle_tri(x):
            t = x["type"]
            if t == "remove":
                fin = x.get("sim", 0.0)        # plus bas = plus flagrant
            elif t == "add":
                fin = x.get("margin", 9.9)     # plus serré = plus incertain
            else:
                fin = -x.get("sim", 0.0)       # merge : les plus proches d'abord
            return (order.get(t, 3), fin)

        items.sort(key=_cle_tri)
        items = items[:CUR_MAX_SUGGEST]
        # Cartes jugées PENDANT cette passe : purger le cache au moment du geste
        # ne suffit pas si la reconstruction avait démarré avant (elle écrase
        # avec une liste d'avant le jugement). Voir _note_juge.
        recents = _juges_depuis(t0)
        if recents:
            items = [s for s in items if s.get("key") not in recents]
        with SUGGEST_LOCK:
            SUGGEST_CACHE["items"] = items
            SUGGEST_CACHE["at"] = time.time()
    finally:
        with SUGGEST_LOCK:
            SUGGEST_CACHE["building"] = False


def curator_accept(sug):
    t = sug.get("type")
    if t == "add":
        name, key, i = sug.get("person", ""), sug.get("key", ""), int(sug.get("i", 0))
        tag = f"personne:{name}"
        _index_add_person(key, tag)
        _enqueue_person_write(key, tag, 'add')
        STORE.save()
        _person_add_ref(name, key, i)       # visage confirmé → enrichit la signature
        return True
    if t == "remove":
        return untag_person(sug.get("person", ""), [sug.get("key", "")]) > 0
    if t == "merge":
        return rename_person(sug.get("b", ""), sug.get("a", "")) > 0
    return False


def curator_reject(sug):
    t = sug.get("type")
    if t == "add":
        _person_add_set(sug.get("person", ""), "exclude", sug.get("key", ""))
        return True
    if t == "remove":
        name, key, i = sug.get("person", ""), sug.get("key", ""), int(sug.get("i", 0))
        _person_add_set(name, "confirmed", key)   # « c'est bien elle » → ne plus signaler
        _person_add_ref(name, key, i)             # et enrichit la signature
        return True
    if t == "merge":
        _person_add_set(sug.get("a", ""), "nomerge", sug.get("b", ""))
        _person_add_set(sug.get("b", ""), "nomerge", sug.get("a", ""))
        return True
    return False


def _suggest_remove(pred):
    """Retire du cache les suggestions correspondant au prédicat (résolues)."""
    with SUGGEST_LOCK:
        SUGGEST_CACHE["items"] = [s for s in SUGGEST_CACHE["items"] if not pred(s)]


def curator_loop():
    # Ré-attribue automatiquement les visages aux personnes nommées à partir de
    # leurs signatures. Ne dépend PAS d'Ollama → doit tourner même pendant le
    # re-tagging IA (sinon, avec 30 000 photos à taguer, il ne tournerait jamais
    # et les personnes ne se récupéreraient pas). C'est ce qui recrée tout seul
    # les photos perdues, pendant ton absence.
    time.sleep(30)
    while True:
        try:
            if FACE_QUEUE.empty() and PEOPLE_STORE.data and not ui_recent():
                build_suggestions()
        except Exception as e:
            print(f"  ⚠ Curateur : {e}")
        time.sleep(CURATOR_INTERVAL)


# PETS_PAGE vit dans ui/pages/pets.html (point 7).


# FACES_PAGE vit dans ui/pages/faces.html (point 7).


# TRANCHE_PAGE vit dans ui/pages/tranche.html (point 7).


# RESIDU_PAGE vit dans ui/pages/residu.html (point 7).

# SUBJECTS_PAGE vit dans ui/pages/subjects.html (point 7).


# PEOPLE_PAGE vit dans ui/pages/people.html (point 7).


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.client_address[0]}  {fmt % args}")

    # ─── La porte (chantier 17, étape 4) ───────────────────────────────
    def _ouvrir(self):
        """Lit le cookie, pose l'utilisateur courant, applique la porte.
        Rend True si la requête peut continuer ; sinon la réponse est déjà
        partie (302 vers /connexion pour une page, 401 pour une API)."""
        path = urllib.parse.urlparse(self.path).path
        COMPTES.recharger_si_change()
        nom = None
        if COMPTES.actifs():
            nom = COMPTES.lire_jeton(_comptes.cookie_session(self.headers.get('Cookie')))
        _UTILISATEUR.nom = nom
        verdict = COMPTES.porte(path, nom)
        if verdict in ('ouvert', 'ok'):
            return True
        if verdict == 'refus':
            self._send(401, json.dumps({"error": "connexion requise"}).encode(), 'application/json')
            return False
        suite = urllib.parse.quote(self.path if self.path.startswith('/') else '/')
        self.send_response(302)
        self.send_header('Location', '/connexion?suite=' + suite)
        self.end_headers()
        return False

    def _exige_admin(self, quoi):
        """Étape 5 (choix de Mike, 29/08) : supprimer ou renommer une FICHE
        entière, et la maintenance du fonds, sont à l'admin seul — tant que la
        porte est fermée (sans compte, rien ne change). Rend True si la
        requête peut continuer ; sinon le 403 est déjà parti."""
        nom = utilisateur_vu()
        if not COMPTES.actifs() or (nom and COMPTES.est_admin(nom)):
            return True
        print(f"  ⛔ {nom} : {quoi} refusé (403) — réservé à l'admin")
        self._send(403, json.dumps({"ok": False, "error": f"{quoi} : réservé à l'admin."},
                   ensure_ascii=False).encode(), 'application/json')
        return False

    def do_GET(self):
        try:
            if self._ouvrir():
                self._do_get()
        finally:
            _UTILISATEUR.nom = None     # le fil sert la requête suivante : jamais d'héritage

    def _serve_connexion_post(self):
        d = self._read_json_body()
        nom = COMPTES.verifier(d.get('nom'), d.get('mdp'))
        if not nom:
            attente = COMPTES.freine((d.get('nom') or '').strip())
            self._send(200, json.dumps({"ok": False, "attente": attente}).encode(), 'application/json')
            return
        jeton = COMPTES.jeton(nom)
        body = json.dumps({"ok": True, "nom": nom, "admin": COMPTES.est_admin(nom)}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        # Pas de `Secure` : le LAN est en http, Tailscale termine le TLS.
        self.send_header('Set-Cookie', f"{_comptes.COOKIE}={jeton}; Path=/; HttpOnly; SameSite=Lax; "
                                       f"Max-Age={_comptes.DUREE_SESSION}")
        self.end_headers()
        self.wfile.write(body)
        print(f"  🔐 connexion : {nom}")

    def _serve_deconnexion(self):
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Set-Cookie', f"{_comptes.COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
        self.end_headers()
        self.wfile.write(body)

    def _serve_moi(self):
        nom = utilisateur_vu()
        self._send(200, json.dumps({"nom": nom, "admin": bool(nom and COMPTES.est_admin(nom)),
                                    "porte": COMPTES.actifs()}).encode(), 'application/json')

    def _serve_comptes(self):
        """Gestion des comptes, ADMIN seulement. Sans compte (porte ouverte),
        c'est Mike seul devant son serveur : il peut créer le premier ici aussi."""
        nom = utilisateur_vu()
        path = urllib.parse.urlparse(self.path).path
        d = self._read_json_body() if self.command == 'POST' else {}
        cible = (d.get('nom') or nom or '').strip()
        # Chacun peut changer SON mot de passe ; tout le reste est à l'admin.
        soi = (path == '/api/comptes/mdp' and nom and cible == nom)
        if COMPTES.actifs() and not soi and not (nom and COMPTES.est_admin(nom)):
            self._send(403, json.dumps({"error": "admin seulement"}).encode(), 'application/json')
            return
        if self.command == 'GET':
            self._send(200, json.dumps({"comptes": [
                {"nom": n, "admin": COMPTES.est_admin(n)} for n in COMPTES.noms()],
                "moi": nom}, ensure_ascii=False).encode(), 'application/json')
            return
        try:
            if path == '/api/comptes':
                c = COMPTES.creer(d.get('nom'), d.get('mdp'), admin=bool(d.get('admin')))
                print(f"  🔐 compte créé par {nom or 'la porte ouverte'} : {c}")
            elif path == '/api/comptes/mdp':
                COMPTES.changer_mdp(cible, d.get('mdp'))
            elif path == '/api/comptes/supprimer':
                COMPTES.supprimer((d.get('nom') or '').strip())
                print(f"  🔐 compte supprimé par {nom} : {d.get('nom')}")
            else:
                self._send(404, b'Not found', 'text/plain'); return
        except ValueError as e:
            self._send(200, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode(),
                       'application/json')
            return
        self._send(200, json.dumps({"ok": True, "comptes": COMPTES.noms()}, ensure_ascii=False).encode(),
                   'application/json')

    def _do_get(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/' or path == '':
            self._send_html(ui_page('upload'))

        elif path == '/connexion':
            self._send_html(ui_page('connexion'))

        elif path == '/api/moi':
            self._serve_moi()

        elif path == '/api/comptes':
            self._serve_comptes()

        elif path == '/api/corbeille':
            self._serve_corbeille()

        elif path == '/files':
            self._serve_gallery()

        elif path == '/map':
            self._serve_map()

        elif path == '/api/geo':
            self._serve_geo()

        elif path == '/faces':
            # Page « Visages » retirée : redirige vers Personnes (compat marque-pages)
            self.send_response(302)
            self.send_header('Location', '/people')
            self.end_headers()

        elif path == '/api/faces/status':
            self._serve_faces_status()

        elif path == '/api/animals/status':
            self._serve_animals_status()

        elif path == '/sujets':
            self._serve_sujets()

        elif path == '/api/sujets/list':
            self._serve_sujets_list()

        elif path == '/pets':
            self._serve_pets()

        elif path == '/api/pets/clusters':
            self._serve_pets_clusters()

        elif path == '/api/pets/list':
            self._serve_pets_list()

        elif path == '/api/pets/photos':
            self._serve_cat_photos()

        elif path == '/api/animalcrop':
            self._serve_animalcrop()

        elif path == '/api/names':
            self._serve_names()

        elif path == '/api/search':
            self._serve_semantic_search()
        elif path == '/api/similar':
            self._serve_similar()
        elif path == '/api/jour':
            self._serve_jour()
        elif path == '/api/faits':
            self._serve_faits()

        elif path == '/api/search/status':
            self._serve_semantic_status()

        elif path == '/api/faces/list':
            self._serve_faces_list()

        elif path == '/api/facecrop':
            self._serve_facecrop()

        elif path == '/api/thumb':
            self._serve_thumb()

        elif path == '/people':
            self._serve_people()

        elif path == '/api/people/clusters':
            self._serve_people_clusters()

        elif path == '/api/people/inconnus':
            self._serve_people_inconnus()

        elif path == '/api/people/list':
            self._serve_people_list()

        elif path == '/api/people/photos':
            self._serve_person_photos()

        elif path == '/api/people/contestes':
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            body = json.dumps(
                {"contestes": sujet_contestes(PEOPLE_STORE, (q.get('name') or [''])[0])},
                ensure_ascii=False).encode()
            self._send(200, body, 'application/json')

        elif path == '/api/people/slideshow':
            self._serve_person_slideshow()

        elif path == '/api/curator/list':
            self._serve_curator_list()
        elif path == '/api/pets/curator/list':
            self._serve_pets_curator_list()
        elif path == '/tranche':
            self._send_html(ui_page('tranche'))
        elif path == '/api/tranche/list':
            self._serve_tranche_list()
        elif path == '/residu':
            self._send_html(ui_page('residu'))
        elif path == '/api/residu/list':
            self._serve_residu_list()

        elif path == '/api/status':
            self._serve_status()

        elif path == '/api/random':
            self._serve_random()

        elif path == '/api/playlist':
            self._serve_playlist()

        elif path == '/api/assoc':
            self._serve_assoc()

        elif path == '/sante':
            self._serve_health()

        elif path == '/reglages':
            self._serve_reglages()

        elif path == '/api/serveur':
            self._serve_serveur_etat()

        elif path == '/api/raccourcis':
            self._serve_raccourcis()

        elif path == '/api/maint/status':
            self._serve_maint_status()

        elif path == '/eval':
            self._serve_eval_page()

        elif path == '/browse' or path.startswith('/browse/'):
            self._serve_browse(path)

        elif path.startswith('/media/'):
            self._serve_media(path)

        elif path.startswith('/uploads/'):
            self._serve_file(path)

        else:
            self._send(404, b'Not found', 'text/plain')

    def do_POST(self):
        note_heavy_activity()
        print(f"  POST {self.path}")
        try:
            if self._ouvrir():
                self._do_post()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, str(e).encode(), 'text/plain')
        finally:
            _UTILISATEUR.nom = None

    def _read_json_body(self):
        n = int(self.headers.get('Content-Length', 0))
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return {}

    # ─── La corbeille à 6 mois (chantier 17, étape 6 — 17d) ────────────
    def _serve_corbeille(self):
        """Ce que la corbeille porte (qui, quoi, quand ça expire) — l'endroit
        où l'admin voit ce qui va expirer. Admin seul : la liste cite des
        photos de tous."""
        if not self._exige_admin('La corbeille'):
            return
        with FILE_OPS_LOCK:
            entrees = file_ops().corbeille()
        self._send(200, json.dumps({"ok": True, "retention_jours": fichiers.RETENTION_JOURS,
                                    "entrees": entrees,
                                    "expirees": sum(1 for e in entrees if e['expiree']),
                                    "octets": sum(e['octets'] for e in entrees)},
                                   ensure_ascii=False).encode(), 'application/json')

    def _do_corbeille_post(self, path):
        """`restaurer` {ts} : remet UN effacement précis — le garde de l'étape 5
        s'applique (le propriétaire ou l'admin). `purger` {appliquer} : à blanc
        sans `appliquer: true` ; supprime DÉFINITIVEMENT ce qui a passé les
        180 jours — le seul rm du serveur, admin seul, sous le verrou."""
        d = self._read_json_body()
        try:
            with FILE_OPS_LOCK:
                if path == '/api/corbeille/restaurer':
                    res = file_ops().restaurer(d.get('ts'), UPLOAD_DIR)
                    print(f"  ♻ {utilisateur_vu()} restaure {res.get('name')} depuis la corbeille")
                elif path == '/api/corbeille/purger':
                    if not self._exige_admin('La purge de la corbeille'):
                        return
                    res = file_ops().purger(appliquer=bool(d.get('appliquer')))
                    if res['appliquer']:
                        print(f"  🗑 {utilisateur_vu()} purge la corbeille : {len(res['purges'])} panier(s), {res['octets']} o")
                else:
                    self._send(404, b'Not found', 'text/plain')
                    return
            self._send(200, json.dumps({"ok": True, **res}, ensure_ascii=False).encode(),
                       'application/json')
        except fichiers.FileOpRefus as e:
            print(f"  ⛔ {utilisateur_vu()} : {path} refusé ({e.code}) — {e}")
            self._send(e.code, json.dumps({"ok": False, "error": str(e)},
                       ensure_ascii=False).encode(), 'application/json')
        except fichiers.FileOpError as e:
            self._send(200, json.dumps({"ok": False, "error": str(e)},
                       ensure_ascii=False).encode(), 'application/json')

    def _do_files_post(self, path):
        """Operations de fichiers (vue Dossiers) : renommer / deplacer / creer
        un dossier / supprimer (quarantaine reversible) / annuler. La logique
        vit dans fichiers.py (module pur, teste). do_POST a deja appele
        note_heavy_activity() (invariant UI > NAS)."""
        d = self._read_json_body()
        ops = file_ops()
        up = UPLOAD_DIR
        try:
            with FILE_OPS_LOCK:
                if path == '/api/files/rename':
                    res = ops.rename(d.get('idx'), d.get('rel', ''), d.get('name', ''), up)
                elif path == '/api/files/move':
                    res = ops.move(d.get('idx'), d.get('rel', ''),
                                   d.get('dst_idx'), d.get('dst_rel', ''), up)
                elif path == '/api/files/mkdir':
                    res = ops.mkdir(d.get('idx'), d.get('rel', ''), d.get('name', ''))
                elif path == '/api/files/delete':
                    # Deux formes : {idx, rel} (vue Dossiers) ou {key} (galerie,
                    # point 21). La cle est resolue en (idx, rel) ; introuvable
                    # => FileOpError (deja capturee, renvoie {ok:false, error}).
                    idx, rel = d.get('idx'), d.get('rel', '')
                    if d.get('key') is not None:
                        tgt = _key_to_target(d.get('key'))
                        if not tgt:
                            raise fichiers.FileOpError(
                                "Photo introuvable dans les dossiers connus.")
                        idx, rel = tgt
                    res = ops.delete(idx, rel, up)
                elif path == '/api/files/undo':
                    res = ops.undo(up)
                else:
                    self._send(404, b'Not found', 'text/plain')
                    return
            self._send(200, json.dumps({"ok": True, **res},
                       ensure_ascii=False).encode(), 'application/json')
        except fichiers.FileOpRefus as e:
            # étape 5 : 403 sur une photo partagée qui n'est pas à lui, 404
            # sur une photo qu'il ne voit pas. Le client lit `error` comme
            # pour toute autre erreur ; le journal dit QUI a été refusé.
            print(f"  ⛔ {utilisateur_vu()} : {path} refusé ({e.code}) — {e}")
            self._send(e.code, json.dumps({"ok": False, "error": str(e)},
                       ensure_ascii=False).encode(), 'application/json')
        except fichiers.FileOpError as e:
            self._send(200, json.dumps({"ok": False, "error": str(e)},
                       ensure_ascii=False).encode(), 'application/json')

    def _do_post(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/connexion':
            self._serve_connexion_post()
            return
        if path == '/api/deconnexion':
            self._serve_deconnexion()
            return
        if path in ('/api/comptes', '/api/comptes/mdp', '/api/comptes/supprimer'):
            self._serve_comptes()
            return
        if path == '/api/assign':
            self._do_assign()
            return
        if path == '/api/undo':
            data = self._read_json_body()
            libelle = annuler(data.get('jeton'))
            self._send(200, json.dumps(
                {"ok": bool(libelle), "libelle": libelle or ""},
                ensure_ascii=False).encode(), 'application/json')
            return
        if path.startswith('/api/files/'):
            self._do_files_post(path)
            return
        if path.startswith('/api/corbeille/'):
            self._do_corbeille_post(path)
            return
        if path.startswith('/api/maint/'):
            self._do_maint_post(path)
            return
        if path.startswith('/api/people/'):
            self._do_people_post(path)
            return
        if path.startswith('/api/pets/'):
            self._do_pets_post(path)
            return
        if path.startswith('/api/curator/'):
            self._do_curator_post(path)
            return
        if path.startswith('/api/tranche/'):
            self._do_tranche_post(path)
            return
        if path.startswith('/api/residu/'):
            self._do_residu_post(path)
            return
        if path == '/eval/notes':
            self._do_eval_notes()
            return
        if self.path != '/upload':
            self._send(404, b'Not found', 'text/plain')
            return

        content_type = self.headers.get('Content-Type', '')
        boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
        if not content_type.startswith('multipart/form-data') or not boundary_match:
            self._send(400, b'Bad request', 'text/plain')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length <= 0:
            self._send(400, b'No content', 'text/plain')
            return

        body = self.rfile.read(content_length)
        boundary = boundary_match.group(1).strip('"').encode()

        data = None
        original_name = None
        relpath = None

        for part in body.split(b'--' + boundary):
            if b'\r\n\r\n' not in part:
                continue
            head, _, payload = part.partition(b'\r\n\r\n')
            head_str = head.decode('utf-8', errors='replace')
            name_m = re.search(r'name="([^"]*)"', head_str, re.IGNORECASE)
            if not name_m:
                continue
            field = name_m.group(1)
            if field == 'file':
                file_m = re.search(r'filename="([^"]*)"', head_str, re.IGNORECASE)
                if file_m:
                    original_name = Path(file_m.group(1)).name
                data = payload.rstrip(b'\r\n')
            elif field == 'relpath':
                relpath = payload.rstrip(b'\r\n').decode('utf-8', 'replace').strip()

        if not data:
            self._send(400, b'No file', 'text/plain')
            return

        # Doublon de CONTENU (nom indifférent) : même taille PUIS même sha256.
        # Empêche la page web de fabriquer des doublons, y compris quand la même
        # image revient sous un autre nom ou dans un autre album.
        if _upload_content_dup(data) is not None:
            self._send(200, b'SKIP', 'text/plain')
            return

        # ── Deux modes d'écriture ──────────────────────────────────────────
        # DOSSIER : le client envoie un chemin relatif avec sous-dossier
        # (webkitdirectory). On préserve l'arborescence sous UPLOAD_DIR et on
        # garde le nom d'origine. PLAT (historique) : nom simple → horodaté.
        # Le saut des déjà-présents est géré par le contrôle de contenu ci-dessus.
        rel = _safe_upload_rel(relpath)
        if rel and '/' in rel:
            base = UPLOAD_DIR / rel
            # Confinement dur : jamais hors de UPLOAD_DIR, quoi qu'envoie le client.
            try:
                if UPLOAD_DIR.resolve() not in base.resolve().parents:
                    self._send(400, b'Bad path', 'text/plain')
                    return
            except OSError:
                self._send(400, b'Bad path', 'text/plain')
                return
            # Contenu nouveau : si le chemin est déjà pris par un AUTRE contenu,
            # on décale le nom pour ne rien écraser.
            dest = base
            counter = 1
            while dest.exists():
                dest = base.with_name(f"{base.stem}_{counter}{base.suffix}")
                counter += 1
            key = dest.relative_to(UPLOAD_DIR).as_posix()
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:20]
            if original_name:
                stem = Path(original_name).stem
                suffix = Path(original_name).suffix or '.jpg'
                safe_stem = re.sub(r'[^\w\-.]', '_', stem)
                filename = f"{safe_stem}_{timestamp}{suffix}"
            else:
                filename = f"photo_{timestamp}.jpg"
            dest = UPLOAD_DIR / filename
            counter = 1
            while dest.exists():
                dest = UPLOAD_DIR / f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
                counter += 1
            key = dest.name

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        except OSError as e:
            print(f"  ✗ Write error: {e}")
            self._send(500, str(e).encode(), 'text/plain')
            return

        print(f"  ✓ Saved {dest} ({human_size(len(data))})")
        _upload_size_map_add(dest)   # dédoublonnage des fichiers suivants du même album

        # → file d'attente du tagging IA (clé relative si sous-dossier)
        if dest.suffix.lower() in IMAGE_EXT:
            enqueue(key)

        self._send(200, b'OK', 'text/plain')

    def _serve_gallery(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        dirparam = (q.get('dir') or [''])[0]
        rec = (q.get('rec') or [''])[0] == '1'
        tagsparam = (q.get('tags') or [''])[0]
        tmode = (q.get('tmode') or ['and'])[0]
        sel = [t.strip() for t in tagsparam.split(',') if t.strip()]
        # Filtre par motif (point 21) : regroupe la vue par regle nom/dossier
        # (capture / document / facture), lecture seule. Jamais une etiquette
        # « rebut », jamais une auto-selection : un simple outil de confort.
        motif = (q.get('motif') or [''])[0].strip()

        # Recherche globale : /files?q=... SANS dossier. La grille devient le
        # resultat de semantic_search (lieux + noms + sens), pas le contenu d'un
        # dossier. Sans ca, un lien Lieu (/sujets) ou un marqueur de Carte ouvre
        # une galerie VIDE : le dossier Uploads est vide, et le filtre IA cote
        # client ne fait qu'intersecter les photos deja chargees.
        qparam = (q.get('q') or [''])[0].strip()
        search_mode = bool(qparam) and not dirparam and not sel and not motif
        # Page « semblables » : /files?sim=<clé>. Même mécanique que ?q= —
        # la grille devient un résultat classé — mais la requête est une PHOTO
        # (son vecteur déjà en base), pas un texte. Navigation de proche en
        # proche : chaque résultat offre à son tour son bouton « Semblables ».
        simparam = (q.get('sim') or [''])[0].strip()
        sim_mode = (bool(simparam) and not search_mode
                    and not dirparam and not sel and not motif)
        # Page « même jour, autres années » : /files?jour=<clé de photo> ou
        # /files?jour=MM-JJ. Troisième mode « la grille est un résultat », après
        # ?q= et ?sim= — mais celui-ci ne coûte ni vecteur ni GPU : il lit
        # l'index MM-JJ en mémoire (dates PRÉCISES uniquement).
        jourparam = (q.get('jour') or [''])[0].strip()
        jour_mode = (bool(jourparam) and not search_mode and not sim_mode
                     and not dirparam and not sel and not motif)

        if dirparam:
            roots = media_roots()
            parts = dirparam.split('/', 1)
            try:
                idx = int(parts[0])
                root = roots[idx][1]
            except (ValueError, IndexError):
                self._send(404, b'Not found', 'text/plain')
                return
            sub = parts[1] if len(parts) > 1 else ''
            base = root.resolve()
            try:
                folder = (root / sub).resolve() if sub else base
            except OSError:
                self._send(404, b'Not found', 'text/plain')
                return
            if (folder != base and base not in folder.parents) or not folder.is_dir():
                self._send(404, b'Not found', 'text/plain')
                return

            def url_for(p):
                relf = p.relative_to(base).as_posix()
                return f'/media/{idx}/' + urllib.parse.quote(relf)
        else:
            folder = UPLOAD_DIR
            idx, sub = 0, ''

            def url_for(p):
                return '/uploads/' + urllib.parse.quote(
                    p.relative_to(UPLOAD_DIR).as_posix())

        # tags du dossier ET de ses sous-dossiers, depuis l'index (instantané)
        entries = _index_entries_under(folder)
        tag_counts = {}
        for _k, _e in entries:
            if _e.get('failed'):
                continue
            for t in set((_e.get('kw_fr') or []) + (_e.get('kw_en') or [])):
                tag_counts[t] = tag_counts.get(t, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:60]

        try:
            if rec:
                files = [f for f in folder.rglob('*')
                         if f.is_file() and f.suffix.lower() in MEDIA_EXT
                         and not _is_hidden_path(f.relative_to(folder))]
            else:
                files = [f for f in folder.iterdir()
                         if f.is_file() and f.suffix.lower() in MEDIA_EXT
                         and not f.name.startswith(('.', '@', '#'))]
            subdirs = sorted([e for e in folder.iterdir() if e.is_dir()
                              and not e.name.startswith(('.', '@', '#'))],
                             key=lambda x: x.name.lower())
        except OSError as e:
            self._send(500, str(e).encode(), 'text/plain')
            return

        # barre de navigation par dossiers
        fparts = []
        if dirparam:
            if sub:
                parent = f"{idx}/{sub.rsplit('/', 1)[0]}" if '/' in sub else str(idx)
                fparts.append('<a class="btn btn--nav" href="/files?dir='
                              + urllib.parse.quote(parent, safe='/')
                              + '">&#11014;&#65039; Parent</a>')
            else:
                fparts.append('<a class="btn btn--nav" href="/browse">&#11014;&#65039; Dossiers</a>')
        for e in subdirs:
            sv = f"{idx}/{(sub + '/' if sub else '') + e.name}"
            fparts.append('<a class="btn btn--nav" href="/files?dir='
                          + urllib.parse.quote(sv, safe='/')
                          + f'">&#128193; {html.escape(e.name)}</a>')
        cur = f"{idx}/{sub}" if sub else str(idx)
        if rec:
            fparts.append('<a class="btn btn--nav" href="/files?dir='
                          + urllib.parse.quote(cur, safe='/')
                          + '">&#128257; Ce dossier seul</a>')
        elif subdirs:
            fparts.append('<a class="btn btn--nav" href="/files?dir='
                          + urllib.parse.quote(cur, safe='/')
                          + '&amp;rec=1">&#128257; Inclure les sous-dossiers</a>')
        if fparts:
            lv = f'/browse/{idx}/' + urllib.parse.quote(sub) if sub else f'/browse/{idx}'
            fparts.append(f'<a class="btn btn--nav" href="{lv}">&#128196; Liste</a>')
        folders_html = ('<div class="folders">' + ''.join(fparts) + '</div>') if fparts else ''
        if search_mode:
            folders_html = ''   # une page de resultats n'a pas de sous-dossiers
        if sim_mode:
            # Bandeau : d'où vient la page + retour. Le nom suffit ; la photo
            # de référence arrive de toute façon en tête d'aucun résultat
            # (elle est écartée) et son dossier reste à un clic.
            folders_html = ('<div class="folders">'
                            '<span class="fetiquette">&#128269; Semblables à '
                            + html.escape(Path(simparam).name) + '</span>'
                            '</div>')
        jour_items, jour_libelle = [], ''
        if jour_mode:
            jour_cle, jour_ref = _jour_resoudre(jourparam)
            if not jour_cle:
                # État vide RÉDIGÉ (plancher photo-ui n° 7) : dire POURQUOI.
                # 29 % de la photothèque n'a pas de date au jour près ; une
                # page muette laisserait croire à une panne.
                folders_html = (
                    '<div class="folders"><span class="fetiquette">'
                    'Cette photo n\'a pas de date de prise de vue au jour '
                    'près : seule son année est connue, on ne peut donc pas '
                    'la rapprocher d\'un même jour.</span></div>')
            else:
                jour_libelle = meme_jour.libelle_jour(jour_cle)
                jour_items = meme_jour.photos_du_jour(
                    _jour_index(), jour_cle, exclure=jour_ref)
        is_uploads = folder in (UPLOAD_DIR, UPLOAD_DIR.resolve())
        roots_g = media_roots()
        carte_cles = _key_index()   # UN instantané pour toute la boucle
        # Faits (date . lieu . noms) : le contexte des noms, lieux et
        # racines est bati UNE fois pour la page entiere -- voir
        # `_faits_ctx`. Les quatre modes de la page (navigation, tags,
        # recherche, meme jour) le partagent : c'est le meme instantane
        # qui sert la planche et la visionneuse.
        fctx = _faits_ctx()
        file_data = []
        for f in files:
            # Clé d'index EXACTE (casse d'origine) : `f` vient d'un parcours de
            # `folder`, donc d'un resolve() qui minuscule l'hôte SMB — un accès
            # direct STORE.get(str(f)) raterait toute la racine NAS.
            fkey = _index_key_for_path(f, carte_cles)
            if fkey is None and is_uploads and STORE.get(f.name) is not None:
                fkey = f.name
            entry = (STORE.get(fkey) if fkey else None) or {}
            if entry.get('failed'):
                continue  # image endommagée : on ne l'affiche pas
            # évite un stat() réseau par fichier quand l'index connaît déjà
            size, mtime = entry.get('size'), entry.get('mtime')
            if size is None or mtime is None:
                try:
                    st = f.stat()
                    size, mtime = st.st_size, st.st_mtime
                except OSError:
                    size, mtime = 0, 0
            kw = list(dict.fromkeys(
                (entry.get('kw_fr') or []) + (entry.get('kw_en') or [])))
            # Chemin ABSOLU, pas la clé : une clé d'Uploads est relative
            # (« Album/x.jpg ») et _folder_link_for_key ne la rattacherait à
            # aucune racine (lien vers la racine au lieu du sous-dossier).
            # _resolve_key préserve la casse d'origine de la clé NAS.
            folder_lbl, gurl = _folder_link_for_key(
                str(_resolve_key(fkey)) if fkey else str(f), roots_g)
            file_data.append({
                'name': f.relative_to(folder).as_posix() if rec else f.name,
                # Clé d'index : sert à recouper les résultats de la recherche
                # sémantique (clés Uploads = nom nu), ET à cibler la suppression
                # par clé (point 21). Pour une racine supplémentaire, on garde
                # TOUJOURS le chemin absolu : un fichier non encore indexé y
                # retombait sinon sur un nom nu, résolu à tort sous Uploads par
                # _key_to_target (mauvaise racine). Uploads : comportement
                # inchangé (nom nu, relatif). Photo INDEXÉE : on renvoie la clé
                # telle qu'elle est stockée (casse d'origine) — c'est elle que
                # /api/similar, la suppression par clé et /api/jour attendent.
                # Non indexé : convention scan_uploads — nom nu SEULEMENT à la
                # racine d'Uploads. Un « x.jpg » d'un sous-dossier rendu en nom
                # nu se résout à la racine et fait viser un AUTRE fichier.
                'key': fkey or (f.name if is_uploads
                                and _pkey(f.parent) == _pkey(UPLOAD_DIR)
                                else str(f)),
                'url': url_for(f),
                'size': human_size(size),
                'mtime': mtime,
                # Date de PRISE (epoch) pour le tri chronologique de la galerie
                # et l'ordre du diaporama — _best_time : EXIF, sinon nom/annee, sinon mtime.
                'taken': _best_time(fkey or str(f), entry),
                # Jour « MM-JJ » si la date est PRÉCISE (sinon None) : c'est lui
                # qui décide si le bouton « Même jour » s'affiche.
                'jour': _jour_de(fkey or str(f), entry),
                'faits': _faits_pour(fkey or str(f), entry, fctx),
                'kw': kw,
                'gps': entry.get('gps'),
                'desc': entry.get('desc', ''),
                'folder': folder_lbl,
                'gurl': gurl,
            })
        # sélection de tags active : résultats récursifs depuis l'index,
        # sans parcourir le NAS
        if sel:
            roots_cache = media_roots()
            fp = _pkey(folder)
            file_data = []
            for k, e in entries:
                if e.get('failed'):
                    continue
                kws = set((e.get('kw_fr') or []) + (e.get('kw_en') or []))
                ok = (any(t in kws for t in sel) if tmode == 'or'
                      else all(t in kws for t in sel))
                if not ok:
                    continue
                url = _url_for_key(k, roots_cache)
                if not url:
                    continue
                kp = _pkey(k)
                name = kp[len(fp) + 1:] if kp.startswith(fp + '/') else Path(k).name
                folder_lbl, gurl = _folder_link_for_key(k, roots_cache)
                file_data.append({
                    'name': name,
                    # Cle d'index : necessaire au filtre par motif et a la
                    # suppression par cle (meme role que dans le chemin nav).
                    'key': k,
                    'url': url,
                    'size': human_size(e.get('size') or 0),
                    'mtime': e.get('mtime') or 0,
                    'taken': _best_time(k, e),   # date de prise (epoch) pour le tri chronologique
                    'jour': _jour_de(k, e),
                    'faits': _faits_pour(k, e, fctx),
                    'kw': sorted(kws),
                    'gps': e.get('gps'),
                    'desc': e.get('desc', ''),
                    'folder': folder_lbl,
                    'gurl': gurl,
                })

        detail_q = {}
        # Recherche globale (/files?q=...) : on REMPLACE la grille par le resultat
        # de semantic_search, dans l'ordre de pertinence renvoye. Meme forme
        # d'objet que la branche `sel` (donc rendu client inchange). Lecture seule,
        # index en memoire ; note_heavy_activity car semantic_search peut lire les
        # vecteurs. Cap a 1500 : couvre les gros lieux (Bremblens ~1141) sans
        # exploser le rendu (vignettes en lazy-load). Depuis le 22/08 il est
        # ANNONCE quand il coupe (`detail['tronque']`) : `espece:chat` rend
        # 2 386 photos, la page en montrait 1 500 sans un mot.
        if search_mode or sim_mode:
            note_heavy_activity()
            roots_cache = media_roots()
            file_data = []
            # Ce que la requête a COMPRIS et ce qu'elle a mis de côté : la page
            # `/files?q=` le taisait, alors que /api/search le dit depuis le
            # 15/08 — la même requête s'expliquait dans un canal et filtrait en
            # silence dans l'autre. Un seul producteur (`semantic_search`), donc
            # aucune ré-extraction côté page.
            try:
                if sim_mode:
                    # 200 : aligné sur la recherche IA côté client (n=200) —
                    # au-delà, la pertinence cosinus ne veut plus dire
                    # grand-chose et la planche devient du bruit.
                    resultats_q = similar_by_key(simparam, 200)
                    if resultats_q is None:
                        # Pas encore de vecteur : photo fraîchement déposée ou
                        # écartée. État vide RÉDIGÉ (plancher photo-ui n° 7).
                        folders_html = ('<div class="folders">'
                                        '<span class="fetiquette">Cette photo n\'a '
                                        'pas encore été analysée : son vecteur '
                                        'sera calculé en tâche de fond, '
                                        'réessayer dans quelques minutes.'
                                        '</span></div>')
                        resultats_q = []
                else:
                    resultats_q = semantic_search(qparam, 1500,
                                                  detail=detail_q)
            except Exception:                                 # noqa: BLE001
                resultats_q = []
            for k, _score in resultats_q:
                e = STORE.get(k) or {}
                if e.get('failed'):
                    continue
                url = _url_for_key(k, roots_cache)
                if not url:
                    continue
                kws = list(dict.fromkeys(
                    (e.get('kw_fr') or []) + (e.get('kw_en') or [])))
                folder_lbl, gurl = _folder_link_for_key(k, roots_cache)
                file_data.append({
                    'name': Path(k).name,
                    'key': k,
                    'url': url,
                    'size': human_size(e.get('size') or 0),
                    'mtime': e.get('mtime') or 0,
                    'taken': _best_time(k, e),
                    'jour': _jour_de(k, e),
                    'faits': _faits_pour(k, e, fctx),
                    'kw': kws,
                    'gps': e.get('gps'),
                    'desc': e.get('desc', ''),
                    'folder': folder_lbl,
                    'gurl': gurl,
                })

        # « Même jour » : la grille devient la journée, du plus ANCIEN au plus
        # récent (l'ordre du récit familial). Même forme d'objet que les autres
        # modes, donc rendu client inchangé — sauf `annee`, qui laisse la
        # vignette porter son millésime.
        if jour_mode:
            roots_cache = media_roots()
            file_data = []
            for _ep, k in jour_items[:1500]:
                e = STORE.data.get(k) or {}
                url = _url_for_key(k, roots_cache)
                if not url:
                    continue
                kws = list(dict.fromkeys(
                    (e.get('kw_fr') or []) + (e.get('kw_en') or [])))
                folder_lbl, gurl = _folder_link_for_key(k, roots_cache)
                file_data.append({
                    'name': Path(k).name,
                    'key': k,
                    'url': url,
                    'size': human_size(e.get('size') or 0),
                    'mtime': e.get('mtime') or 0,
                    'taken': _ep,
                    'annee': meme_jour.annee_de(_ep),
                    'jour': _jour_de(k, e),
                    'faits': _faits_pour(k, e, fctx),
                    'kw': kws,
                    'gps': e.get('gps'),
                    'desc': e.get('desc', ''),
                    'folder': folder_lbl,
                    'gurl': gurl,
                })
            # Bandeau bâti sur ce qui est RÉELLEMENT rendu (après le plafond et
            # après les clés sans URL servable) : un compteur qui annonce plus
            # que ce qu'on voit est un compteur qui ment.
            chips = ('<span class="fetiquette">&#128197; ' + html.escape(jour_libelle)
                     + '</span>')
            comptes = {}
            for _e in file_data:
                comptes[_e['annee']] = comptes.get(_e['annee'], 0) + 1
            # Une puce par année : c'est le récit de la page (« ce jour-là,
            # en 2008, en 2011, en 2019 »), et un ancrage pour l'œil.
            for an in sorted(comptes):
                chips += ('<span class="fetiquette jour-an">' + str(an)
                          + ' <b>' + str(comptes[an]) + '</b></span>')
            if not comptes:
                chips += ('<span class="fetiquette">Aucune autre photo ce '
                          'jour-là dans la photothèque.</span>')
            folders_html = '<div class="folders">' + chips + '</div>'

        # Comptes par motif sur la vue courante, puis filtre eventuel. Import
        # PARESSEUX : interet est pur (re/pathlib), aucun modele ni deps ML au
        # chargement — le serveur demarre sans torch/cv2 (invariant zero-dep).
        motif_counts = {}
        try:
            import interet
            for _e in file_data:
                _cat, _m = interet.classer_regle(_e.get('key', ''))
                if _cat:
                    motif_counts[_cat] = motif_counts.get(_cat, 0) + 1
            if motif:
                file_data = [_e for _e in file_data
                             if interet.classer_regle(_e.get('key', ''))[0] == motif]
        except Exception:                                     # noqa: BLE001
            motif_counts = {}
            if motif:
                file_data = []

        # Marque les photos qu'aucune date sûre ne classe. Post-passe UNIQUE :
        # les trois branches qui remplissent `file_data` (navigation, sélection,
        # recherche) partagent ainsi la même règle. La clé n'est écrite que pour
        # les concernées — 258 sur 43 064 : écrire « 0 » 43 064 fois coûterait
        # 300 ko de JSON pour ne rien dire.
        for _fd in file_data:
            _k = _fd.get('key') or _fd.get('name') or ''
            _e = STORE.data.get(_k)
            if _sans_date_sure(_k, _e):
                _fd['sd'] = 1
            # Phase 1 des vidéos : la planche sait qu'elle tient une vidéo
            # (badge « ▶ durée », `<video>` dans la visionneuse).
            if (isinstance(_e, dict) and _e.get('video')) or \
                    Path(_k).suffix.lower() in VIDEO_EXT:
                _fd['video'] = 1
                if isinstance(_e, dict) and _e.get('duree'):
                    _fd['duree'] = _e['duree']

        # Sur une grille qui est un RÉSULTAT (?q=, ?sim=, ?jour=), les puces
        # de filtre comptent les tags DU RÉSULTAT — pas ceux du dossier
        # Uploads, que `folder` désigne par défaut. Vu le 29/08 : les mêmes
        # « 60 tags » (personne:Florine 8, extérieur 7…) sur « Indonésie »
        # 1 002 photos et sur une requête à 0 photo. Une puce qui ne compte
        # pas ce qu'on regarde est un filtre qui ment.
        grille_resultat = bool(search_mode or sim_mode or jour_mode)
        if grille_resultat:
            tag_counts = {}
            for _fd in file_data:
                _e = STORE.data.get(_fd.get('key') or _fd.get('name') or '') or {}
                if _e.get('failed'):
                    continue
                for t in set((_e.get('kw_fr') or []) + (_e.get('kw_en') or [])):
                    tag_counts[t] = tag_counts.get(t, 0) + 1
            top_tags = sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:60]

        page = (ui_page('gallery')
                .replace('__FOLDERS__', folders_html)
                .replace('__MOTIFS__', json.dumps(
                    {'counts': motif_counts, 'sel': motif}, ensure_ascii=False))
                .replace('__FILE_JSON__', json.dumps(file_data, ensure_ascii=False))
                .replace('__TAGGED__', str(STORE.tagged_count()))
                .replace('__REC__', '1' if rec else '0')
                .replace('__HASSUBS__', '1' if subdirs else '0')
                .replace('__DIRQ__', json.dumps(dirparam))
                .replace('__SEARCHQ__', json.dumps(qparam if search_mode else ''))
                .replace('__GRILLE_RESULTAT__', '1' if grille_resultat else '0')
                .replace('__SEARCHMETA__', json.dumps(
                    detail_q if search_mode else {}, ensure_ascii=False))
                .replace('__MOIS_JOUR__', json.dumps(
                    meme_jour.MOIS_FR, ensure_ascii=False))
                .replace('__TAGDATA__', json.dumps(
                    {'counts': top_tags, 'sel': sel, 'mode': tmode},
                    ensure_ascii=False)))
        self._send_html(page)

    def _serve_geo(self):
        """Liste JSON des photos géolocalisées, pour la vue carte."""
        roots = media_roots()
        gps_places = gps_places_connus()   # géocodage inverse offline précalculé
        pts = []
        for k, e in list(STORE.data.items()):
            if not isinstance(e, dict) or e.get('failed'):
                continue
            g = e.get('gps')
            if not (isinstance(g, list) and len(g) == 2):
                continue
            lat, lon = g
            if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
                continue
            url = _url_for_key(k, roots)
            if not url:
                continue
            kp = _pkey(k)
            # dossier lisible + lien galerie
            folder, gurl = 'Uploads', '/files'
            if '/' in kp:
                parent = kp.rsplit('/', 1)[0]
                for i, (label, root) in enumerate(roots):
                    rp = _pkey(root)
                    if kp.startswith(rp + '/'):
                        rel = parent[len(rp) + 1:] if len(parent) > len(rp) else ''
                        folder = label + ('/' + rel if rel else '')
                        if rel:
                            gurl = ('/files?dir=' + str(i) + '/'
                                    + urllib.parse.quote(rel, safe='/') + '&rec=1')
                        else:
                            gurl = '/files?dir=' + str(i) + '&rec=1'
                        break
                else:
                    folder = parent.rsplit('/', 1)[-1]
            kw = list(dict.fromkeys(
                (e.get('kw_fr') or []) + (e.get('kw_en') or [])))
            pts.append({
                'url': url, 'key': k, 'lat': lat, 'lon': lon,
                'name': Path(k).name, 'folder': folder, 'gurl': gurl,
                'desc': e.get('desc', ''), 'kw': kw[:8],
                'taken': _best_time(k, e),
                'lieu': gps_places.get(k),   # lieu géocodé (None si non calculé)
            })
        body = json.dumps({'points': pts}, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_names(self):
        """Autocomplétion : personnes ET animaux, dans une seule liste."""
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        genre = (qs.get('genre', [''])[0] or '') or None
        prefixe = qs.get('q', [''])[0] or ''
        # Le client met la liste en cache et filtre localement a la frappe : il
        # faut donc renvoyer TOUTES les personnes/animaux, pas seulement les plus
        # photographies. L'ancien cap [:40] excluait toute personne au-dela du
        # 40e rang par volume (ex. Mathilde, 110 photos) — jamais proposee a
        # l'autocompletion, donc re-creee comme « Nouveau » a chaque fois.
        noms = noms_pour_saisie(genre, prefixe)[:2000]
        self._send(200, json.dumps({'noms': noms}, ensure_ascii=False).encode(),
                   'application/json')

    # ─── Recherche sémantique (SigLIP 2) ───────────────────────────────────
    def _serve_semantic_search(self):
        """Texte libre → photos, par similarité dans l'espace SigLIP 2."""
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        requete = (qs.get('q', [''])[0] or '').strip()
        # Plafond aligné sur la page de résultats /files?q= (1500) : la carte
        # filtre ses marqueurs par le même vocabulaire et a besoin de la même
        # couverture. Le défaut reste 80 (autocomplétion / usages légers).
        limite = min(int(qs.get('n', ['80'])[0] or 80), 1500)
        if not requete:
            self._send(200, json.dumps({'results': []}).encode(),
                       'application/json')
            return
        detail = {}
        try:
            resultats = semantic_search(requete, limite, detail=detail)
        except Exception as e:                                # noqa: BLE001
            self._send(200, json.dumps(
                {'results': [], 'error': str(e)[:200]},
                ensure_ascii=False).encode(), 'application/json')
            return
        note_heavy_activity()
        roots = media_roots()
        sortie = []
        for cle, score in resultats:
            e = STORE.data.get(cle) or {}
            sortie.append({
                'key': cle, 'score': round(score, 4),
                'url': _url_for_key(cle, roots),
                'name': Path(cle).name,
                'desc': e.get('desc', ''),
                'kw': (e.get('kw_fr') or e.get('kw_en') or [])[:8],
            })
        # La décomposition vient de `semantic_search` (`detail`) au lieu d'être
        # RECALCULÉE ici : deux extractions parallèles finissent toujours par
        # diverger, et c'est alors l'écran qui ment sur ce que le moteur a fait.
        # `sans_date` : photos écartées faute de date assez précise pour la
        # période demandée. Sans ce chiffre, « 3 résultats » se lit « il n'y a
        # que 3 photos » au lieu de « 12 000 photos n'ont pas de mois connu ».
        self._send(200, json.dumps(
            {'results': sortie, 'q': requete,
             'noms': detail.get('noms', []),
             'lieux': detail.get('lieux', []),
             'periode': detail.get('periode', ''),
             # 5ᵉ axe : ce que le jeton `espece:` a filtré, et ce qu'il n'a
             # pas su lire. Une espèce inconnue rend zéro photo : le taire
             # ferait passer un filtre impossible pour un fonds vide.
             'especes': detail.get('especes', []),
             'especes_inconnues': detail.get('especes_inconnues', []),
             # Les jetons que le moteur n'a pas su satisfaire, et qui rendent
             # donc ZÉRO photo : `noms_inconnus` porte la valeur (« animal:Zzz
             # »), `axes_inconnus` la seule graphie de l'axe (« couleur »).
             # Sans eux, l'appelant ne distingue pas « ce nom n'existe pas » de
             # « ce nom n'a pas de photo », et c'est toute la différence.
             'noms_inconnus': detail.get('noms_inconnus', []),
             'axes_inconnus': detail.get('axes_inconnus', []),
             'sans_date': detail.get('sans_date', 0),
             # `sans_date_tri` : photos RENDUES mais placées sans aucune date
             # sûre — elles vont en fin de liste. Une protection qui s'annule
             # doit se compter, même quand elle ne cache rien.
             'sans_date_tri': detail.get('sans_date_tri', 0),
             # LE PLAFOND SE DIT (24/08). Le filtre déterministe COMPTE avant
             # de couper : `total` = ce qui correspondait, `tronque` = ce qui
             # n'a pas tenu dans `n`. Ces deux chiffres étaient calculés par
             # `semantic_search` puis JETÉS ici — seule la page `/files?q=`
             # les recevait, et un consommateur de l'API voyait 1 500 photos
             # sans savoir qu'il y en avait 5 832. Le plafond silencieux
             # corrigé pour la page le 22/08 et pour le MCP le 23/08 vivait
             # encore dans la route.
             # `null` et non `len(results)` quand le moteur ne SAIT pas : la
             # branche sémantique classe tout le fonds par cosinus, il n'y a
             # pas de total à y lire, et rendre le nombre de résultats ferait
             # passer une page pour un fonds entier. `0` dit « rien n'a été
             # coupé », `null` dit « je ne sais pas » — les confondre, c'est
             # réinventer le plafond muet à l'autre bout.
             'total': detail.get('total'),
             'tronque': detail.get('tronque'),
             'reste': detail.get('reste', requete),
             # L'élargissement FR→EN (30/08) : ce que le moteur a encodé EN
             # PLUS de la requête, ou null. Un moteur qui ajoute des mots
             # sans le dire serait un plafond muet d'un autre genre.
             'elargi': detail.get('elargi')},
            ensure_ascii=False).encode(), 'application/json')

    def _serve_similar(self):
        """Photo → photos proches (cosinus sur le vecteur DÉJÀ en base).

        Même forme de sortie que /api/search (`results` : key/score/url/name/
        desc/kw) pour que tout consommateur de l'un lise l'autre — y compris
        le futur serveur MCP lecture (feuille de route, point 13).
        `encodee:false` distingue « pas encore de vecteur » d'un vrai vide.
        """
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        cle = (qs.get('key', [''])[0] or '').strip()
        limite = min(int(qs.get('n', ['80'])[0] or 80), 500)
        if not cle:
            self._send(200, json.dumps({'results': []}).encode(),
                       'application/json')
            return
        try:
            resultats = similar_by_key(cle, limite)
        except Exception as e:                                # noqa: BLE001
            self._send(200, json.dumps(
                {'results': [], 'error': str(e)[:200]},
                ensure_ascii=False).encode(), 'application/json')
            return
        if resultats is None:
            self._send(200, json.dumps(
                {'results': [], 'encodee': False, 'key': cle},
                ensure_ascii=False).encode(), 'application/json')
            return
        note_heavy_activity()
        roots = media_roots()
        sortie = []
        for k, score in resultats:
            e = STORE.data.get(k) or {}
            sortie.append({
                'key': k, 'score': round(score, 4),
                'url': _url_for_key(k, roots),
                'name': Path(k).name,
                'desc': e.get('desc', ''),
                'kw': (e.get('kw_fr') or e.get('kw_en') or [])[:8],
            })
        self._send(200, json.dumps(
            {'results': sortie, 'encodee': True, 'key': cle},
            ensure_ascii=False).encode(), 'application/json')

    def _serve_faits(self):
        """La ligne de faits (date . lieu . noms) de photos DESIGNEES.

        Pourquoi une route, alors que `_serve_browse` calcule deja ces faits :
        parce qu'il les calcule DANS une page. Rien d'autre que le HTML ne
        pouvait les lire -- ni un banc, ni le MCP en lecture seule (point 13) -
        et refaire l'assemblage ailleurs est exactement ce que `faits_vue`
        existe pour empecher (voir `_faits_pour` : un deuxieme assemblage, meme
        fidele, finit par diverger).

        ?key=<cle>, repetable, MAX_FAITS au plus. Le contexte est bati UNE fois
        pour tout le lot -- c'est ce qui rend un appel groupe moins cher que N
        appels, et c'est la meme economie que fait la page.

        Trois etats, et ils ne se confondent pas : un fait rendu ; `null` pour
        une photo CONNUE qui ne porte aucun des trois ; et la cle citee dans
        `inconnues` quand l'index ne la connait pas. Une cle absente rendue
        comme un fait vide se lirait <<cette photo ne porte rien>>, alors
        qu'elle dit <<je ne connais pas cette photo>>."""
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        cles = [c.strip() for c in qs.get('key', []) if c and c.strip()]
        if not cles:
            self._send(400, json.dumps(
                {'error': 'aucune cle : ?key=<cle>, repetable, %d au plus'
                          % MAX_FAITS}, ensure_ascii=False).encode(),
                'application/json')
            return
        tronque = len(cles) > MAX_FAITS
        cles = cles[:MAX_FAITS]
        # `media_roots()` fait des stats SMB (audit O3) : cette route touche
        # donc le NAS, et cede la priorite au travail de fond comme les autres.
        note_heavy_activity()
        ctx = _faits_ctx()
        faits, inconnues = {}, []
        for cle in cles:
            k, e = cle, STORE.data.get(cle)
            if e is None:
                # Lien ancien, ou cle minusculee par le resolve de l'hote SMB :
                # meme rattrapage que `_jour_resoudre`, plutot qu'un <<absent>>
                # qui serait faux.
                alt = _index_key_for_path(_resolve_key(cle))
                if alt:
                    k, e = alt, STORE.data.get(alt)
            if e is None:
                inconnues.append(cle)
                continue
            faits[cle] = _faits_pour(k, e, ctx)
        corps = {'faits': faits, 'inconnues': inconnues,
                 'demandees': len(cles)}
        if tronque:
            # Un plafond muet se lit comme une exhaustivite (ROADMAP 14a).
            corps['tronque'] = True
            corps['plafond'] = MAX_FAITS
        self._send(200, json.dumps(corps, ensure_ascii=False).encode(),
                   'application/json')

    def _serve_jour(self):
        """« Même jour, autres années » — les photos qui partagent le mois-jour
        d'une photo donnée, groupées par année.

        ?key=<clé de photo> (ce que passe la visionneuse) ou ?jour=MM-JJ (lien
        partageable). Même forme de sortie que /api/search et /api/similar
        (`results` : key/url/name/desc/kw), plus `annees` pour le récit et
        `jour`/`libelle` pour le titre. Zéro IA, zéro GPU, zéro accès NAS :
        tout vient de l'index en mémoire — pas de note_heavy_activity.

        `precise:false` distingue « cette photo n'a pas de date au jour près »
        d'un vrai jour vide : sans ça, une photo datée du seul « année du
        dossier » ouvrirait une page muette."""
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        param = ((qs.get('jour', [''])[0] or qs.get('key', [''])[0]) or '').strip()
        try:
            limite = min(int(qs.get('n', ['1500'])[0] or 1500), 5000)
        except ValueError:      # ?n=abc : un paramètre bancal n'est pas un 500
            limite = 1500
        if not param:
            self._send(200, json.dumps({'results': [], 'annees': []}).encode(),
                       'application/json')
            return
        jour, cle_ref = _jour_resoudre(param)
        if not jour:
            self._send(200, json.dumps(
                {'results': [], 'annees': [], 'precise': False, 'key': cle_ref},
                ensure_ascii=False).encode(), 'application/json')
            return
        items = meme_jour.photos_du_jour(_jour_index(), jour, exclure=cle_ref)
        roots = media_roots()
        sortie, comptes = [], {}
        for _ep, k in items[:limite]:
            e = STORE.data.get(k) or {}
            an = meme_jour.annee_de(_ep)
            comptes[an] = comptes.get(an, 0) + 1
            sortie.append({
                'key': k,
                'url': _url_for_key(k, roots),
                'name': Path(k).name,
                'annee': an,
                'taken': _ep,
                'desc': e.get('desc', ''),
                'kw': (e.get('kw_fr') or e.get('kw_en') or [])[:8],
            })
        # `annees` décrit `results`, pas la journée entière : au-delà du
        # plafond `n`, `total` dit ce qui a été écarté (pas de troncature
        # silencieuse).
        annees = [{'annee': an, 'n': comptes[an]} for an in sorted(comptes)]
        self._send(200, json.dumps(
            {'results': sortie, 'annees': annees, 'jour': jour,
             'libelle': meme_jour.libelle_jour(jour), 'precise': True,
             'key': cle_ref, 'rendus': len(sortie), 'total': len(items)},
            ensure_ascii=False).encode(), 'application/json')

    def _serve_semantic_status(self):
        etat = dict(SEMANTIC_STATE)
        etat['total'] = len(STORE.data)
        # L'élargissement FR→EN (30/08) : taille du dictionnaire appris, pour
        # que « elargi: null » se lise (dictionnaire vide ? jamais construit ?)
        # au lieu de se deviner.
        d = _DICO_FR_EN.get('dico')
        etat['dico_fr_en'] = None if d is None else {
            'paires': len(d), 'photos': d.n_photos,
            'construit': time.strftime('%H:%M:%S', time.localtime(_DICO_FR_EN['quand']))}
        # Rendre l'ordonnancement OBSERVABLE : sans ça, un travail affamé
        # ressemble à un travail lent, et on cherche au mauvais endroit.
        try:
            etat['erreurs_images'] = list(_semantic_mod().DERNIERES_ERREURS)[-8:]
        except Exception:                                     # noqa: BLE001
            pass
        if ORDO is not None:
            etat['ordonnanceur'] = ORDO.etat()
        if GPU is not None:
            etat['gpu'] = GPU.etat()
        self._send(200, json.dumps(etat, ensure_ascii=False).encode(),
                   'application/json')

    def _serve_map(self):
        self._send_html(ui_page('map'))

    def _serve_faces(self):
        self._send_html(ui_page('faces'))

    def _serve_faces_status(self):
        processed = with_faces = total = reembedded = 0
        for e in FACE_STORE.data.values():
            if not isinstance(e, dict) or e.get('failed'):
                continue
            processed += 1
            n = e.get('n', 0)
            if n:
                with_faces += 1
                total += n
            if e.get('reemb'):
                reembedded += 1
        with FACE_PENDING_LOCK:
            pending = len(FACE_PENDING)
        engine = get_face_app() is not None
        body = json.dumps({
            'engine': engine,
            'provider': FACE_PROVIDER or ('?' if engine else ''),
            'error': FACE_ERROR,
            'photos_processed': processed,
            'photos_with_faces': with_faces,
            'total_faces': total,
            'pending': pending,
            'reembedded': reembedded,
            'reembed_done': REEMBED_STATE.get('done', 0),
            'face_engine_last': FACE_LAST_ENGINE or 'CPU',
            'gpu_faces_ready': FACE_APP_GPU is not None,
            'gpu_faces_error': FACE_GPU_ERROR,
            'hw': hw_state(),
        }, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_animals_status(self):
        """État de la détection d'animaux (Phase 1). Compte les photos
        analysées, celles contenant un animal, et le détail par espèce."""
        processed = with_animals = total = 0
        by_species = {}
        for e in ANIMAL_STORE.data.values():
            if not isinstance(e, dict) or e.get('failed'):
                continue
            processed += 1
            animals = e.get('animals') or []
            if animals:
                with_animals += 1
                total += len(animals)
                for a in animals:
                    sp = a.get('species', '?')
                    by_species[sp] = by_species.get(sp, 0) + 1
        with ANIMAL_PENDING_LOCK:
            pending = len(ANIMAL_PENDING)
        engine = get_yolo() is not None
        body = json.dumps({
            'engine': engine,
            'weights': ANIMAL_YOLO_WEIGHTS,
            'device': ANIMAL_DEVICE,
            'error': YOLO_ERROR,
            'photos_processed': processed,
            'photos_with_animals': with_animals,
            'total_animals': total,
            'by_species': by_species,
            'cats': by_species.get('cat', 0),
            'pending': pending,
            'embedded': PET_EMBED_STATE.get('done', 0),
            'dino': DINO_MODEL_OBJ is not None,
            'dino_error': DINO_ERROR,
        }, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    # ─── Phase 2 chats : pages & API ───
    def _serve_pets(self):
        self._send_html(ui_page('pets'))

    def _serve_pets_clusters(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rebuild = (q.get('rebuild') or ['0'])[0] == '1'
        with PET_CLUSTER_LOCK:
            building = PET_CLUSTER_CACHE["building"]
            has = bool(PET_CLUSTER_CACHE["clusters"])
            at = PET_CLUSTER_CACHE["at"]
        if (rebuild or not has) and not building:
            threading.Thread(target=build_pet_clusters, daemon=True).start()
            building = True
        with PET_CLUSTER_LOCK:
            clusters = list(PET_CLUSTER_CACHE["clusters"])
        body = json.dumps({"building": building, "at": at,
                           "count": len(clusters), "clusters": clusters},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_pets_list(self):
        body = json.dumps({"pets": pets_list()}, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_cat_photos(self):
        note_heavy_activity()   # ouverture d'un détail → le backfill cède le NAS
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = (q.get('name') or [''])[0]
        try:
            photos = cat_photos(name)
        except Exception as e:                                # noqa: BLE001
            # Jamais un 500 non-JSON (que le client ne sait pas lire) : on renvoie
            # une erreur JSON exploitable, et l'UI propose de reessayer.
            body = json.dumps({"photos": [], "error": str(e)[:200]},
                              ensure_ascii=False).encode()
            self._send(200, body, 'application/json')
            return
        body = json.dumps({"photos": photos},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_animalcrop(self):
        """Recadrage JPEG d'un animal détecté (clé + index), avec cache disque."""
        note_heavy_activity()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        key = (q.get('key') or [''])[0]
        try:
            i = int((q.get('i') or ['0'])[0])
        except ValueError:
            i = 0
        e = ANIMAL_STORE.get(key)
        if not isinstance(e, dict) or e.get('failed') or not PIL_OK:
            self._send(404, b'Not found', 'text/plain')
            return
        animals = e.get('animals') or []
        if not animals:
            self._send(404, b'Not found', 'text/plain')
            return
        if i < 0 or i >= len(animals):
            i = 0
        bbox = animals[i].get('bbox', [0, 0, 0, 0])
        import hashlib
        ck = hashlib.md5(f"a|{key}|{i}|{bbox}".encode('utf-8', 'replace')).hexdigest()
        cache_file = ANIMAL_THUMB_DIR / (ck + ".jpg")
        data = None
        try:
            if cache_file.is_file():
                data = cache_file.read_bytes()
        except OSError:
            data = None
        if data is None:
            path = _resolve_key(key)
            try:
                if not path.is_file():
                    self._send(404, b'Not found', 'text/plain')
                    return
                x1, y1, x2, y2 = bbox
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    w, h = im.size
                    mw, mh = int((x2 - x1) * 0.15), int((y2 - y1) * 0.15)
                    box = (max(0, x1 - mw), max(0, y1 - mh),
                           min(w, x2 + mw), min(h, y2 + mh))
                    crop = im.crop(box)
                    crop.thumbnail((256, 256))
                    buf = io.BytesIO()
                    crop.save(buf, "JPEG", quality=82)
                    data = buf.getvalue()
                try:
                    ANIMAL_THUMB_DIR.mkdir(parents=True, exist_ok=True)
                    cache_file.write_bytes(data)
                except OSError:
                    pass
            except Exception:
                self._send(404, b'Not found', 'text/plain')
                return
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'max-age=86400')
        self.end_headers()
        self.wfile.write(data)

    def _do_assign(self):
        """Route unique d'attribution — animaux ET visages.

        Un rejet n'est qu'une attribution à une cible spéciale : il n'y a donc
        qu'un seul chemin de code, et une seule chose à apprendre côté UI.
        """
        d = self._read_json_body()
        genre = d.get('genre', 'animal')
        cible = d.get('cible', '')
        try:
            if genre == 'animal':
                res = attribuer_animaux(d.get('membres') or [], cible)
            elif genre == 'visage':
                # Deux formes : attribution par SOUS-ENSEMBLE (groupes, avec
                # « membres ») ou suggestion unitaire du curateur (cle + i).
                if d.get('membres'):
                    res = attribuer_visages(d.get('membres') or [], cible)
                else:
                    res = attribuer_visage(d.get('cle', ''), int(d.get('i', 0) or 0),
                                           cible, d.get('propose', ''))
            else:
                res = {"ok": False, "erreur": "genre inconnu"}
        except Exception as e:                                # noqa: BLE001
            res = {"ok": False, "erreur": str(e)[:200]}
        # Instrumentation : une attribution UNITAIRE de visage avec personne
        # proposée vient d'une carte de la file « À vérifier » → jugement humain
        # (confirmation du nom, correction vers un autre nom, ou « pas un
        # visage »). Les attributions par groupes (« membres ») n'en sont pas.
        try:
            if (genre == 'visage' and not d.get('membres') and d.get('propose')
                    and isinstance(res, dict) and res.get('ok')):
                cible_n = str(cible).strip().lower()
                prop_n = str(d.get('propose')).strip().lower()
                if cible_n == '__pas_visage__':
                    verdict, geste = 'erreur_decouverte', 'pas_visage'
                elif cible_n == prop_n:
                    verdict, geste = 'confirmation', 'confirme_nom'
                else:
                    verdict, geste = 'erreur_decouverte', 'corrige_nom'
                _journal_jugement({"source": "assign", "geste": geste,
                                   "verdict": verdict, "person": d.get('propose'),
                                   "cible": cible, "key": d.get('cle'),
                                   "sim": d.get('sim'), "margin": d.get('marge')})
                # Une carte jugée sort de la file TOUT DE SUITE (comme le chemin
                # resolve). Sans ça, seule la reconstruction suivante la purgeait
                # et elle réapparaissait au rechargement de la page — le mode de
                # panne « je corrige et ça revient ». Observé en réel le 12/08.
                _suggest_remove(lambda s: s.get('key') == d.get('cle')
                                and s.get('person') == d.get('propose')
                                and s.get('type') in ('add', 'remove'))
                _note_juge(d.get('cle'))
                res["stats"] = _stats_seance()
            # Même instrumentation pour une suggestion UNITAIRE d'animal (file
            # « À vérifier » de l'onglet Classification) : un seul membre +
            # animal proposé = jugement humain. Les attributions par groupes
            # (plusieurs membres, pas de « propose ») n'en sont pas.
            elif (genre == 'animal' and d.get('propose')
                    and len(d.get('membres') or []) == 1
                    and isinstance(res, dict) and res.get('ok')):
                cible_n = str(cible).strip().lower() if isinstance(cible, str) else ''
                prop_n = str(d.get('propose')).strip().lower()
                if cible_n == CIBLE_PAS_ANIMAL:
                    verdict, geste = 'erreur_decouverte', 'pas_animal'
                elif cible_n == CIBLE_INCONNU:
                    verdict, geste = 'erreur_decouverte', 'aucun_animal'
                elif cible_n == prop_n:
                    verdict, geste = 'confirmation', 'confirme_nom'
                else:
                    verdict, geste = 'erreur_decouverte', 'corrige_nom'
                _k0 = str((d.get('membres') or [[None, 0]])[0][0])
                _journal_jugement({"source": "curator_animal", "geste": geste,
                                   "verdict": verdict, "animal": d.get('propose'),
                                   "cible": cible, "key": _k0,
                                   "sim": d.get('sim'), "margin": d.get('marge')})
                # La carte jugée sort de la file TOUT DE SUITE (même remède que
                # côté visages : sinon elle réapparaît au rechargement).
                _cat_suggest_remove(lambda s: s.get('key') == _k0)
                _note_juge(_k0)
                res["stats"] = _stats_seance()
        except Exception:                                     # noqa: BLE001
            pass
        self._send(200, json.dumps(res, ensure_ascii=False).encode(),
                   'application/json')

    def _do_pets_post(self, path):
        data = self._read_json_body()
        # `/api/pets/name` a été retiré le 22/08 (audit I8) : aucune page ne
        # l'appelait depuis que le nommage des animaux passe par `/api/assign`
        # (genre animal), qui journalise le jugement et sait le défaire. Le
        # chemin des PERSONNES, lui, a un client vivant et reste en place.
        if path == '/api/pets/find':
            props = find_more_cats(data.get('name', ''))
            self._send(200, json.dumps({"proposals": props}, ensure_ascii=False).encode(),
                       'application/json')
        elif path == '/api/pets/confirm':
            tagged = confirm_cat(data.get('name', ''), data.get('keys') or [])
            self._send(200, json.dumps({"ok": tagged > 0, "tagged": tagged}).encode(),
                       'application/json')
        elif path == '/api/pets/untag':
            n = untag_cat(data.get('name', ''), data.get('keys') or [])
            self._send(200, json.dumps({"ok": n > 0, "removed": n}).encode(),
                       'application/json')
        elif path == '/api/pets/rename':
            if not self._exige_admin('Renommer une fiche'):
                return
            n = rename_cat(data.get('old', ''), data.get('new', ''))
            self._send(200, json.dumps({"ok": n > 0, "moved": n}).encode(),
                       'application/json')
        elif path == '/api/pets/delete':
            if not self._exige_admin('Supprimer une fiche'):
                return
            n = delete_cat(data.get('name', ''))
            self._send(200, json.dumps({"ok": True, "removed": n}).encode(),
                       'application/json')
        elif path == '/api/pets/recluster':
            with PET_CLUSTER_LOCK:
                building = PET_CLUSTER_CACHE["building"]
            if not building:
                threading.Thread(target=build_pet_clusters, daemon=True).start()
            self._send(200, b'{"building": true}', 'application/json')
        else:
            self._send(404, b'Not found', 'text/plain')

    def _serve_faces_list(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        try:
            limit = min(1000, max(1, int((q.get('limit') or ['400'])[0])))
        except ValueError:
            limit = 400
        roots = media_roots()
        items = []  # (at, key, url, i, score)
        for k, e in FACE_STORE.data.items():
            if not isinstance(e, dict) or e.get('failed'):
                continue
            faces = e.get('faces') or []
            if not faces:
                continue
            url = _url_for_key(k, roots)
            if not url:
                continue
            at = e.get('at', 0)
            for i, f in enumerate(faces):
                items.append((at, k, url, i, f.get('det_score', 0)))
        items.sort(key=lambda t: t[0], reverse=True)  # plus récents d'abord
        out = []
        for at, k, url, i, score in items[:limit]:
            out.append({
                'crop_url': '/api/facecrop?key=' + urllib.parse.quote(k, safe='')
                            + '&i=' + str(i),
                'photo_url': url,
                'i': i,
                'score': score,
                'name': Path(k).name,
            })
        body = json.dumps({'faces': out}, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_facecrop(self):
        """Renvoie le recadrage JPEG d'un visage détecté (clé + index), avec
        CACHE DISQUE local : on ne relit l'original sur le NAS qu'une seule fois."""
        note_heavy_activity()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        key = (q.get('key') or [''])[0]
        try:
            i = int((q.get('i') or ['0'])[0])
        except ValueError:
            i = 0
        e = FACE_STORE.get(key)
        if not isinstance(e, dict) or e.get('failed') or not PIL_OK:
            self._send(404, b'Not found', 'text/plain')
            return
        faces = e.get('faces') or []
        if not faces:
            self._send(404, b'Not found', 'text/plain')
            return
        if i < 0 or i >= len(faces):
            i = 0                          # index périmé (ré-embedding) → visage principal
        bbox = faces[i].get('bbox', [0, 0, 0, 0])
        import hashlib
        ck = hashlib.md5(f"{key}|{i}|{bbox}".encode('utf-8', 'replace')).hexdigest()
        cache_file = FACE_THUMB_DIR / (ck + ".jpg")
        data = None
        try:
            if cache_file.is_file():
                data = cache_file.read_bytes()
        except OSError:
            data = None
        if data is None:
            path = _resolve_key(key)
            try:
                if not path.is_file():
                    self._send(404, b'Not found', 'text/plain')
                    return
                x1, y1, x2, y2 = bbox
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    w, h = im.size
                    mw, mh = int((x2 - x1) * 0.3), int((y2 - y1) * 0.3)
                    box = (max(0, x1 - mw), max(0, y1 - mh),
                           min(w, x2 + mw), min(h, y2 + mh))
                    crop = im.crop(box)
                    crop.thumbnail((256, 256))
                    buf = io.BytesIO()
                    crop.save(buf, "JPEG", quality=82)
                    data = buf.getvalue()
                try:
                    FACE_THUMB_DIR.mkdir(parents=True, exist_ok=True)
                    cache_file.write_bytes(data)
                except OSError:
                    pass
            except Exception:
                self._send(404, b'Not found', 'text/plain')
                return
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'max-age=86400')
        self.end_headers()
        self.wfile.write(data)

    def _serve_thumb(self):
        """Vignette JPEG d'une photo (audit O1), avec CACHE DISQUE local.

        Les grilles (galerie, carte, diaporamas) chargeaient les ORIGINAUX
        pleine résolution : 2–6 Mo lus sur le NAS par case affichée. Ici :
        JPEG 512 px (grille) ou 1600 px (diaporama/plein écran), généré une
        seule fois — ≈ −98 % d'octets NAS en navigation. Même motif que
        `_serve_facecrop`. Si la vignette est impossible (vidéo, HEIC non
        décodé, PIL absent), REDIRIGE vers l'original : le client ne gère
        aucun cas particulier."""
        note_heavy_activity()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        key = (q.get('key') or [''])[0]
        s = (q.get('s') or ['512'])[0]
        s = 1600 if s == '1600' else 512      # deux tailles, pas d'arbitraire
        if not key:
            self._send(404, b'Not found', 'text/plain')
            return
        # CONFINEMENT — même exigence que /media et /uploads : la clé doit
        # résoudre sous une racine servable (_url_for_key → None sinon).
        # Sans ce garde, une clé absolue arbitraire ferait vignetter
        # n'importe quelle image du disque via _resolve_key.
        url = _url_for_key(key)
        if url is None or not chemin_visible(key):   # 17b : même 404 que « absent »
            self._send(404, b'Not found', 'text/plain')
            return

        def _fallback():
            self.send_response(302)
            self.send_header('Location', url)
            self.end_headers()

        if not PIL_OK:
            _fallback()
            return
        path = _resolve_key(key)
        if path.suffix.lower() in VIDEO_EXT:
            self._serve_thumb_video(key, path, s)
            return
        if path.suffix.lower() not in IMAGE_EXT:
            _fallback()
            return
        import hashlib
        # mtime (de l'index, en mémoire — pas de stat NAS) dans la clé de
        # cache : un fichier modifié ou une clé recyclée ne sert jamais une
        # vignette périmée. Les anciennes vignettes orphelines restent sur
        # disque (purge maintenance : à traiter avec O15).
        e = STORE.get(key)
        mt = e.get('mtime') if isinstance(e, dict) else None
        ck = hashlib.md5(f"{key}|{s}|{mt}".encode('utf-8', 'replace')).hexdigest()
        cache_file = PHOTO_THUMB_DIR / (ck + ".jpg")
        data = None
        try:
            if cache_file.is_file():
                data = cache_file.read_bytes()
        except OSError:
            data = None
        if data is None:
            try:
                if not path.is_file():
                    # clé qui ne résout pas en fichier (ex. nom nu d'un
                    # sous-dossier Uploads) : laisser l'URL servable trancher.
                    _fallback()
                    return
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    im.thumbnail((s, s))
                    buf = io.BytesIO()
                    im.save(buf, "JPEG", quality=82)
                    data = buf.getvalue()
                try:
                    PHOTO_THUMB_DIR.mkdir(parents=True, exist_ok=True)
                    cache_file.write_bytes(data)
                except OSError:
                    pass
            except Exception:
                # original illisible par PIL (format exotique) : l'original
                # lui-même reste peut-être affichable par le navigateur.
                _fallback()
                return
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'max-age=86400')
        self.end_headers()
        self.wfile.write(data)

    def _serve_thumb_video(self, key, path, s):
        """L'image-clé d'une vidéo (phase 1) : une trame à ~10 % de la durée
        (1 s au plus tôt) par ffmpeg, mise en cache comme une vignette de
        photo. Sans ffmpeg, ou sur échec : 404 — la planche montre son
        badge « ▶ » sur fond vide, jamais un original de 500 Mo."""
        import hashlib
        import shutil as _sh
        e = STORE.get(key)
        mt = e.get('mtime') if isinstance(e, dict) else None
        ck = hashlib.md5(f"{key}|{s}|{mt}|video".encode('utf-8', 'replace')).hexdigest()
        cache_file = PHOTO_THUMB_DIR / (ck + ".jpg")
        data = None
        try:
            if cache_file.is_file():
                data = cache_file.read_bytes()
        except OSError:
            data = None
        if data is None:
            ff = _sh.which('ffmpeg')
            if not ff or not path.is_file():
                self._send(404, b'Not found', 'text/plain')
                return
            duree = e.get('duree') if isinstance(e, dict) else None
            pos = max(1.0, min(float(duree or 0) * 0.1, 30.0)) if duree else 1.0
            try:
                note_heavy_activity()
                r = subprocess.run(
                    [ff, '-hide_banner', '-loglevel', 'error', '-ss', f'{pos:.1f}',
                     '-i', str(path), '-frames:v', '1', '-vf', f'scale={int(s)}:-2',
                     '-q:v', '4', '-f', 'image2', '-'],
                    capture_output=True, timeout=60)
                data = r.stdout if r.returncode == 0 and r.stdout else None
                if data is None and pos > 1.0:       # vidéo plus courte qu'annoncé
                    r = subprocess.run(
                        [ff, '-hide_banner', '-loglevel', 'error', '-i', str(path),
                         '-frames:v', '1', '-vf', f'scale={int(s)}:-2', '-q:v', '4',
                         '-f', 'image2', '-'], capture_output=True, timeout=60)
                    data = r.stdout if r.returncode == 0 and r.stdout else None
            except Exception as ex:
                print(f"  ⚠ image-clé ffmpeg : {ex}")
                data = None
            if not data:
                self._send(404, b'Not found', 'text/plain')
                return
            try:
                PHOTO_THUMB_DIR.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(data)
            except OSError:
                pass
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'max-age=86400')
        self.end_headers()
        self.wfile.write(data)

    def _serve_people(self):
        self._send_html(ui_page('people'))

    def _serve_people_clusters(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rebuild = (q.get('rebuild') or ['0'])[0] == '1'
        with CLUSTER_LOCK:
            building = CLUSTER_CACHE["building"]
            has = bool(CLUSTER_CACHE["clusters"])
            at = CLUSTER_CACHE["at"]
        if (rebuild or not has) and not building:
            threading.Thread(target=build_clusters, daemon=True).start()
            building = True
        with CLUSTER_LOCK:
            clusters = list(CLUSTER_CACHE["clusters"])
        body = json.dumps({"building": building, "at": at,
                           "count": len(clusters), "clusters": clusters},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_people_inconnus(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rebuild = (q.get('rebuild') or ['0'])[0] == '1'
        with INCONNU_LOCK:
            building = INCONNU_CACHE["building"]
            at = INCONNU_CACHE["at"]
        # `at == 0` = jamais construit (ou invalidé) : on (re)construit une fois.
        # Un résultat VIDE est un état valide (aucun archivé) — pas de reconstruction
        # en boucle, car build_inconnus pose toujours `at` même à vide.
        if (rebuild or at == 0.0) and not building:
            threading.Thread(target=build_inconnus, daemon=True).start()
            building = True
        with INCONNU_LOCK:
            clusters = list(INCONNU_CACHE["clusters"])
        body = json.dumps({"building": building, "at": at,
                           "count": len(clusters), "clusters": clusters},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_people_list(self):
        body = json.dumps({"people": people_list()}, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    # ─── Surcouche « Sujets » : vue unifiée personnes + animaux (ROADMAP #4) ───
    def _serve_sujets(self):
        self._send_html(ui_page('subjects'))

    def _serve_sujets_list(self):
        # Réutilise les listes existantes (mêmes formes {name, photos, crop}) ;
        # la page les fusionne et les trie. Lecture seule, données en mémoire
        # (aucun accès NAS → pas de note_heavy_activity).
        body = json.dumps({"personnes": people_list(), "animaux": pets_list(),
                           "lieux": places_list()},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_person_photos(self):
        note_heavy_activity()   # ouverture d'un détail → le backfill cède le NAS
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = (q.get('name') or [''])[0]
        # `limit` optionnel : « Nettoyer (reference) » ne charge qu'un petit
        # echantillon pour CHOISIR des references (60 photos ~ instantane), au
        # lieu des 2000 par defaut — sinon, sur une personne a 6000 photos, la
        # grille restait vide longtemps (« il ne se passe rien »).
        try:
            limit = int((q.get('limit') or ['2000'])[0])
        except ValueError:
            limit = 2000
        limit = max(1, min(50000, limit))
        order = (q.get('order') or ['worst'])[0]
        if order not in ('worst', 'best'):
            order = 'worst'
        light = (q.get('light') or ['0'])[0] in ('1', 'true')
        body = json.dumps({"photos": person_photos(name, limit, order, light)},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_person_slideshow(self):
        note_heavy_activity()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = (q.get('name') or [''])[0]
        body = json.dumps({"photos": person_slideshow_list(name)},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_residu_list(self):
        """Les cas a juger + les verdicts deja poses. LECTURE SEULE.

        Les vignettes des candidats ET la planche de reference sont calculees
        ICI, depuis les fiches vivantes : le fichier de tirage ne porte que des
        index. Une reference figee vieillit avec le tirage, et elle vieillit
        exactement la ou une reparation vient de passer (defaut du 22/08).
        """
        try:
            d = json.loads(RESIDU_A_JUGER.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self._send(200, json.dumps({
                "cas": [], "verdicts": {}, "absent": True,
            }, ensure_ascii=False).encode(), 'application/json')
            return
        fiches = _tranche_fiches_par_nom()
        cas = []
        for c in (d.get('cas') or []):
            k = c.get('key', '')
            person = c.get('person', '')
            # Les `bbox` viennent du magasin VIVANT, jamais du fichier de
            # tirage : un cadre pose au mauvais endroit serait pire qu'aucun
            # cadre — il designerait un innocent avec autorite.
            e = FACE_STORE.data.get(k)
            visages = (e.get('faces') or []) if isinstance(e, dict) else []
            dims = _dimensions_photo(k) if visages else None
            cands = []
            for x in (c.get('candidats') or []):
                try:
                    i = int(x.get('i'))
                except (TypeError, ValueError):
                    continue
                bb = None
                if 0 <= i < len(visages) and isinstance(visages[i], dict):
                    bb = _boite_en_fractions(visages[i].get('bbox'), dims)
                cands.append(dict(x, i=i, crop_url=_crop_url(k, i), boite=bb))
            if not cands:
                continue
            # La planche montre les rattachements d'AILLEURS : ceux de CETTE
            # photo sont precisement ce qui est en cause, et les remontrer
            # comme reference ferait juger la piece a conviction contre
            # elle-meme.
            refs = [r for r in _tranche_refs_vivantes(person, fiches)
                    if r[0] != k]
            cas.append(dict(c, id=_residu_id(k, person), person=person,
                            candidats=cands, url=_url_for_key(k),
                            photo_url='/api/thumb?key='
                                      + urllib.parse.quote(k, safe='') + '&s=1200',
                            # Le fichier a pu disparaitre (cles fantomes des
                            # anciens uploads) : sans dimensions, pas de cadre
                            # et pas de vignette. Le DIRE vaut mieux qu'une
                            # image cassee sur une page de jugement.
                            photo_lisible=bool(dims),
                            refs_urls=[_crop_url(r[0], r[1]) for r in refs]))
        with RESIDU_LOCK:
            verdicts = _residu_lire_jugements()
        self._send(200, json.dumps({
            "cas": cas, "verdicts": verdicts, "ecartes": d.get('ecartes'),
        }, ensure_ascii=False).encode(), 'application/json')

    def _do_residu_post(self, path):
        """Enregistre un jugement. N'ATTRIBUE ET NE RETIRE RIEN."""
        if path != '/api/residu/juger':
            self._send(404, b'Not found', 'text/plain')
            return
        d = self._read_json_body() or {}
        key = str(d.get('key') or '')
        person = str(d.get('person') or '')
        verdict = str(d.get('verdict') or '')
        if not key or not person:
            self._send(400, b'key et person requis', 'text/plain')
            return
        if verdict not in RESIDU_VERDICTS:
            self._send(400, ("verdict inconnu : " + verdict).encode(),
                       'text/plain')
            return
        offerts = []
        for x in (d.get('candidats') or []):
            try:
                offerts.append(int(x))
            except (TypeError, ValueError):
                pass
        oui = []
        for x in (d.get('oui') or []):
            try:
                oui.append(int(x))
            except (TypeError, ValueError):
                pass
        # Un verdict ne peut designer qu'un visage que la page a MONTRE. Sinon
        # le banc conclurait sur un visage que personne n'a regarde — et une
        # decision humaine se poserait sur une vue qui n'a pas eu lieu.
        hors = [i for i in oui if i not in offerts]
        if hors:
            self._send(400, ("visage hors du cas : "
                             + ",".join(str(i) for i in hors)).encode(),
                       'text/plain')
            return
        oui = sorted(set(oui))
        evt = {"verdict": verdict, "key": key, "person": person,
               "oui": oui, "non": sorted(i for i in set(offerts)
                                         if i not in oui),
               "ts": time.time()}
        with RESIDU_LOCK:
            verdicts = _residu_lire_jugements()
            verdicts[_residu_id(key, person)] = evt
            _residu_ecrire_jugements(verdicts)
        _journal_jugement({"source": "residu", "geste": "residu_" + verdict,
                           "key": key, "person": person, "oui": oui})
        self._send(200, json.dumps({"ok": True}).encode(), 'application/json')

    def _serve_tranche_list(self):
        """L'echantillon a juger + les verdicts deja poses. LECTURE SEULE.

        Les vignettes passent par /api/facecrop, qui a son cache disque : juger
        trente visages ne relit chaque original sur le NAS qu'une seule fois.
        """
        try:
            d = json.loads(TRANCHE_A_JUGER.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self._send(200, json.dumps({
                "items": [], "verdicts": {}, "absent": True,
            }, ensure_ascii=False).encode(), 'application/json')
            return
        items = []
        fiches = _tranche_fiches_par_nom()
        for c in (d.get('items') or []):
            k = c.get('key', '')
            try:
                i = int(c.get('i') or 0)
            except (TypeError, ValueError):
                i = 0
            person = c.get('person', '')
            # Les references sont RELUES ici, jamais reprises du fichier de
            # tirage : entre le tirage et le jugement, une reparation a pu
            # passer (recalage du 22/08). Ce qui est fige, c'est l'echantillon.
            refs = _tranche_refs_vivantes(person, fiches)
            c = {ck: cv for ck, cv in c.items() if ck != 'refs'}
            items.append(dict(c, id=_tranche_id(k, i, person),
                              crop_url=_crop_url(k, i), url=_url_for_key(k),
                              refs=[[r[0], r[1]] for r in refs],
                              refs_urls=[_crop_url(r[0], r[1]) for r in refs]))
        with TRANCHE_LOCK:
            verdicts = _tranche_lire_jugements()
        self._send(200, json.dumps({
            "items": items, "verdicts": verdicts, "bornes": d.get('bornes'),
            "tirage": d.get('tirage'),
        }, ensure_ascii=False).encode(), 'application/json')

    def _do_tranche_post(self, path):
        """Enregistre UN verdict. N'attribue rien : ni tag, ni fiche, ni XMP."""
        if path != '/api/tranche/juger':
            self._send(404, b'Not found', 'text/plain')
            return
        d = self._read_json_body()
        verdict = d.get('verdict')
        key, person = d.get('key') or '', d.get('person') or ''
        try:
            i = int(d.get('i') or 0)
        except (TypeError, ValueError):
            i = 0
        if verdict not in TRANCHE_VERDICTS or not key or not person:
            self._send(400, json.dumps(
                {"ok": False, "erreur": "verdict ou proposition invalide"},
                ensure_ascii=False).encode(), 'application/json')
            return
        evt = {"verdict": verdict, "key": key, "i": i, "person": person,
               "sim": d.get('sim'), "margin": d.get('margin'),
               "rival": d.get('rival'), "ts": round(time.time(), 3)}
        with TRANCHE_LOCK:
            verdicts = _tranche_lire_jugements()
            verdicts[_tranche_id(key, i, person)] = evt
            _tranche_ecrire_jugements(verdicts)
            n = len(verdicts)
        # Le journal garde la trace meme si le fichier de travail disparait, et
        # c'est LUI que la sauvegarde emporte sur le NAS. Les mots juste/faux/
        # indecidable ne comptent ni comme « confirmation » ni comme
        # « erreur_decouverte » dans les stats de seance : c'est voulu, juger
        # une tranche n'est pas curer le fonds.
        _journal_jugement({"source": "tranche", "geste": "tranche_" + verdict,
                           "verdict": verdict, "person": person, "key": key,
                           "sim": d.get('sim'), "margin": d.get('margin')})
        self._send(200, json.dumps({"ok": True, "juges": n}).encode(),
                   'application/json')

    def _serve_curator_list(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rebuild = (q.get('rebuild') or ['0'])[0] == '1'
        with SUGGEST_LOCK:
            building = SUGGEST_CACHE["building"]
            has = bool(SUGGEST_CACHE["items"])
            at = SUGGEST_CACHE["at"]
        if (rebuild or (not has and at == 0)) and not building:
            threading.Thread(target=build_suggestions, daemon=True).start()
            building = True
        with SUGGEST_LOCK:
            items = list(SUGGEST_CACHE["items"])
        auto = list(reversed(AUTO_LOG[-60:]))   # ajouts automatiques récents (réversibles)
        body = json.dumps({"building": building, "at": at,
                           "count": len(items), "items": items, "auto": auto,
                           "stats": _stats_seance()},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_pets_curator_list(self):
        """File « À vérifier » des animaux + bande des rattachements auto
        récents (annulables). Même forme de réponse que /api/curator/list."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rebuild = (q.get('rebuild') or ['0'])[0] == '1'
        with CAT_SUGGEST_LOCK:
            building = CAT_SUGGEST_CACHE["building"]
            has = bool(CAT_SUGGEST_CACHE["items"])
            at = CAT_SUGGEST_CACHE["at"]
        if (rebuild or (not has and at == 0)) and not building:
            threading.Thread(target=build_cat_suggestions, daemon=True).start()
            building = True
        with CAT_SUGGEST_LOCK:
            items = list(CAT_SUGGEST_CACHE["items"])
        auto = list(reversed(CAT_AUTO_LOG[-60:]))
        body = json.dumps({"building": building, "at": at,
                           "count": len(items), "items": items, "auto": auto,
                           "stats": _stats_seance()},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _do_curator_post(self, path):
        if path != '/api/curator/resolve':
            self._send(404, b'Not found', 'text/plain')
            return
        data = self._read_json_body()
        action = data.get('action', '')
        sug = data.get('sug') or {}
        ok = curator_accept(sug) if action == 'accept' else \
            curator_reject(sug) if action == 'reject' else False

        # retire du cache la suggestion résolue (et les suggestions devenues caduques)
        def same(s):
            if s.get('type') != sug.get('type'):
                return False
            if sug.get('type') == 'merge':
                pair1 = {s.get('a'), s.get('b')}
                pair2 = {sug.get('a'), sug.get('b')}
                return pair1 == pair2
            # add/remove : même personne + même photo
            return s.get('person') == sug.get('person') and s.get('key') == sug.get('key')
        _suggest_remove(same)
        _note_juge(sug.get('key'))
        # Instrumentation du geste : chaque résolution est un jugement humain.
        # add+accept / remove+reject = confirmation ; add+reject / remove+accept
        # = erreur du modèle découverte ; merge = ni l'un ni l'autre.
        if ok:
            t = sug.get("type")
            if t == "add":
                verdict = 'confirmation' if action == 'accept' else 'erreur_decouverte'
            elif t == "remove":
                verdict = 'erreur_decouverte' if action == 'accept' else 'confirmation'
            else:
                verdict = 'fusion' if action == 'accept' else 'refus_fusion'
            _journal_jugement({"source": "curator", "geste": f"{t}_{action}",
                               "verdict": verdict, "person": sug.get("person"),
                               "key": sug.get("key"), "sim": sug.get("sim"),
                               "margin": sug.get("margin")})
        self._send(200, json.dumps({"ok": ok, "stats": _stats_seance()}).encode(),
                   'application/json')

    def _do_people_post(self, path):
        data = self._read_json_body()
        if path == '/api/people/name':
            tagged = name_cluster(str(data.get('cid', '')), data.get('name', ''))
            self._send(200, json.dumps({"ok": tagged > 0, "tagged": tagged}).encode(),
                       'application/json')
        elif path == '/api/people/find':
            props = find_more(data.get('name', ''))
            self._send(200, json.dumps({"proposals": props}, ensure_ascii=False).encode(),
                       'application/json')
        elif path == '/api/people/confirm':
            keys = data.get('keys') or []
            tagged = confirm_person(data.get('name', ''), keys)
            self._send(200, json.dumps({"ok": tagged > 0, "tagged": tagged}).encode(),
                       'application/json')
        elif path == '/api/people/untag':
            n = untag_person(data.get('name', ''), data.get('keys') or [])
            self._send(200, json.dumps({"ok": n > 0, "removed": n}).encode(),
                       'application/json')
        elif path == '/api/people/rename':
            if not self._exige_admin('Renommer une fiche'):
                return
            n = rename_person(data.get('old', ''), data.get('new', ''))
            self._send(200, json.dumps({"ok": n > 0, "moved": n}).encode(),
                       'application/json')
        elif path == '/api/people/delete':
            if not self._exige_admin('Supprimer une fiche'):
                return
            n = delete_person(data.get('name', ''))
            self._send(200, json.dumps({"ok": True, "removed": n}).encode(),
                       'application/json')
        elif path == '/api/people/refscore':
            photos = ref_scores(data.get('name', ''), data.get('ref_keys') or [])
            self._send(200, json.dumps({"photos": photos}, ensure_ascii=False).encode(),
                       'application/json')
        elif path == '/api/people/setref':
            n = set_reference(data.get('name', ''), data.get('ref_keys') or [])
            self._send(200, json.dumps({"ok": n > 0, "refs": n}).encode(),
                       'application/json')
        elif path == '/api/people/recluster':
            with CLUSTER_LOCK:
                building = CLUSTER_CACHE["building"]
            if not building:
                threading.Thread(target=build_clusters, daemon=True).start()
            self._send(200, b'{"building": true}', 'application/json')
        elif path == '/api/people/desarchiver':
            membres = data.get('membres') or []
            res = desarchiver_visages(membres)
            self._send(200, json.dumps(res, ensure_ascii=False).encode(),
                       'application/json')
        else:
            self._send(404, b'Not found', 'text/plain')

    def _serve_status(self):
        with PENDING_LOCK:
            pending = len(PENDING)
        body = json.dumps({
            'pending': pending,
            'tagged': STORE.tagged_count(),
            'model': MODEL,
        }).encode()
        self._send(200, body, 'application/json')

    def _serve_serveur_etat(self):
        """Identité du PROCESSUS : depuis quand il tourne, et s'il exécute le
        `server.py` qui est sur le disque.

        C'est l'instrument qui rend le redémarrage OBSERVABLE. Sans lui, la
        seule preuve qu'un redémarrage a eu lieu était de faire confiance au
        geste — et le projet a déjà payé pour savoir qu'observer sans
        redémarrer, c'est observer l'ancien code. `code_a_jour` à `false` dit
        exactement cela, avant qu'on ne conclue quoi que ce soit d'une mesure.

        Lecture seule, un `stat` local, aucun accès NAS."""
        import pilotage
        try:
            mtime = (SCRIPT_DIR / 'server.py').stat().st_mtime
        except OSError:
            mtime = None
        a_jour = (mtime is not None and SERVER_PY_MTIME is not None
                  and abs(mtime - SERVER_PY_MTIME) < 0.001)
        body = json.dumps({
            'pid': os.getpid(),
            'demarre_a': DEMARRE_A,
            'uptime_s': round(time.time() - DEMARRE_A, 1),
            'commande': pilotage.lire(SCRIPT_DIR / pilotage.FICHIER),
            'server_py_mtime_charge': SERVER_PY_MTIME,
            'server_py_mtime_disque': mtime,
            'code_a_jour': a_jour,
        }, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_raccourcis(self):
        """Le pense-bête des raccourcis (point 6 du plancher) : `docs/RACCOURCIS.md`
        tel quel, en Markdown. UNE source — le panneau « ? » de `ui/global.js` le
        lit ici, la doc n'est plus une copie à maintenir. Un `stat` local, relu
        à chaque appel (le fichier est petit et le panneau rare). Absent : 404
        qui le DIT, pas une page vide."""
        chemin = SCRIPT_DIR / 'docs' / 'RACCOURCIS.md'
        try:
            body = chemin.read_bytes()
        except OSError:
            self._send(404, 'docs/RACCOURCIS.md introuvable'.encode('utf-8'),
                       'text/plain; charset=utf-8')
            return
        self._send(200, body, 'text/markdown; charset=utf-8')

    # ─── Centre de controle : /reglages ───────────────────────────────────
    def _serve_reglages(self):
        self._send_html(ui_page('reglages'))

    def _serve_maint_status(self):
        """Etat consolide (lecture seule) : materiel, files, comptes, etat de la
        maintenance, resumes recensement/plan, config. Alimente /reglages."""
        import maintenance as _m
        docs = SCRIPT_DIR / 'docs'

        def load(name):
            try:
                return json.loads((docs / name).read_text(encoding='utf-8'))
            except Exception:
                return None

        def mtime_de(name):
            try:
                return (docs / name).stat().st_mtime
            except OSError:
                return None

        def summ(o):
            """Resume sur : garde les scalaires, remplace listes/dicts par leur
            taille. Robuste au schema (pas besoin de connaitre les cles)."""
            if not isinstance(o, dict):
                return {}
            r = {}
            for k, v in o.items():
                if isinstance(v, (int, float, str, bool)) or v is None:
                    r[k] = v
                elif isinstance(v, list):
                    r[f"{k} (n)"] = len(v)
                elif isinstance(v, dict):
                    r[f"{k} (cles)"] = len(v)
            return r

        with PENDING_LOCK:
            tagpend = len(PENDING)
        # Stock d'empreintes animales (DINOv2) dans le magasin de vecteurs :
        # compte INDEXE (kind='animals'), instantane, lecture seule. Bien plus
        # parlant que le compteur de session (remis a 0 au demarrage). Repli None
        # si la base vectorielle n'est pas prete.
        try:
            pets_vec = photo_vectors().count('animals')
        except Exception:
            pets_vec = None
        body = {
            'now': time.time(),
            'hw': hw_state(),
            'busy': bool(system_busy() or ui_recent()),
            'queues': {'tag': TAG_QUEUE.qsize(), 'faces': FACE_QUEUE.qsize(),
                       'animaux': ANIMAL_QUEUE.qsize(), 'personnes': PERSON_QUEUE.qsize()},
            'pending': {'tag': tagpend, 'faces': len(FACE_PENDING),
                        'animaux': len(ANIMAL_PENDING)},
            'counts': {'entrees': len(STORE.data), 'tagues': STORE.tagged_count(),
                       'personnes': len(PEOPLE_STORE.data), 'animaux': len(PETS_STORE.data),
                       'visages': len(FACE_STORE.data)},
            # Empreintes animales : `pets_vec` = stock reel (magasin de vecteurs) ;
            # `pets_embed` = calculees depuis le demarrage (activite du worker de
            # fond) ; `dino_loaded` = modele charge (drapeau, PAS d'import lourd,
            # cf. invariant 7).
            'pets_vec': pets_vec,
            'pets_embed': PET_EMBED_STATE.get('done', 0),
            'dino_loaded': DINO_MODEL_OBJ is not None,
            # Boucle scan/backup (audit O5) + vérification de sauvegarde et
            # export des jugements (audit A) : rendus visibles dans /reglages.
            # I6 : l'arbitre VRAM et l'ordonnanceur n'existaient QUE dans
            # `/api/search/status` — la page qui montre l'état du serveur ne
            # savait donc rien des baux, des refus ni des évictions. Un
            # mécanisme qu'on ne voit pas ne se diagnostique pas.
            'gpu': (GPU.etat() if GPU is not None else None),
            'ordonnanceur': (ORDO.etat() if ORDO is not None else None),
            # I5 : le moteur des visages était AFFIRMÉ en dur (« CPU (seul
            # Ollama utilise le GPU) »), ce qui est faux depuis le GPU
            # adaptatif. Il se DIT maintenant, avec ce qu'il a fait en dernier.
            # Lu sur des DRAPEAUX, jamais en appelant `get_face_app()` : cet
            # appel CHARGE InsightFace (invariant 3), et une page d'état qui
            # monte un modèle pour dire s'il est monté serait le contraire
            # d'un instrument.
            'moteurs': {'visages': FACE_LAST_ENGINE or 'CPU',
                        'visages_gpu_pret': FACE_APP_GPU is not None,
                        'visages_gpu_erreur': FACE_GPU_ERROR or '',
                        'visages_gpu_voulu': FACE_USE_GPU},
            'boucle': dict(MAINT_LOOP_STATE),
            # Comptes de l'index (chantier 10a) : qui retire des cles, combien,
            # et ce que personne n'explique. Toutes les listes sont bornees par
            # le registre lui-meme.
            'oublis': REGISTRE.resume(),
            'backup_verify': dict(BACKUP_VERIFY_STATE),
            # Backfills EXIF (dates, GPS) : morts en silence pendant des mois,
            # desormais observables (bug du 13/08, cf. _attendre_exiftool).
            'backfill': {k: dict(v) for k, v in BACKFILL_STATE.items()},
            'maint': {'auto': MAINTENANCE_AUTO, 'paused': MAINT_PAUSED,
                      'every_s': MAINTENANCE_EVERY, 'autonomy': _m.AUTONOMY,
                      'intervals': _m.INTERVALS, 'state': load('maintenance_state.json') or {},
                      'report': summ(load('maintenance_report.json'))},
            'recensement': summ(load('recensement.json')),
            'plan': summ(load('plan_rangement.json')),
            'plan_annee': (lambda pa: {
                'total_a_ranger': pa.get('total_a_ranger'),
                'sans_date': pa.get('sans_date'), 'deja': pa.get('deja'),
                'conflits': len(pa.get('conflits') or []),
                'par_annee': pa.get('par_annee') or {},
                # Quand le plan a ete ECRIT : c'est ce que la page attend pour
                # dire « fini » (le bouton ne l'a jamais dit, 29/08).
                'genere_le': mtime_de('plan_rangement_annee.json')})(
                    load('plan_rangement_annee.json') or {}),
            'config': {'MODEL': MODEL, 'ANIMAL_PIPELINE_VERSION': ANIMAL_PIPELINE_VERSION,
                       'TAGGING_PIPELINE_VERSION': TAGGING_PIPELINE_VERSION,
                       'tagging_pipe': _tagging_pipe_counts(),
                       'UPLOAD_DIR': str(UPLOAD_DIR),
                       'racines': [[label, str(r)] for label, r in media_roots()],
                       'FACE_MATCH_SIM': FACE_MATCH_SIM, 'PET_MATCH_SIM': PET_MATCH_SIM},
        }
        self._send(200, json.dumps(body, ensure_ascii=False, default=str).encode(),
                   'application/json')

    def _do_maint_post(self, path):
        """Actions SURES : lancer un cycle (auto = sur/reversible), pause runtime,
        recensement lecture seule. Les etapes destructives restent gouvernees par
        l'autonomie du cycle (quarantaine reversible), jamais un rm ici."""
        global MAINT_PAUSED
        import subprocess
        if not self._exige_admin('La maintenance du fonds'):
            return
        if path == '/api/maint/run':
            threading.Thread(target=_run_maint_once, daemon=True).start()
            res = {'ok': True, 'msg': 'Cycle de maintenance lance en arriere-plan.'}
        elif path == '/api/maint/toggle':
            MAINT_PAUSED = not MAINT_PAUSED
            res = {'ok': True, 'paused': MAINT_PAUSED}
        elif path == '/api/maint/census':
            try:
                subprocess.Popen([sys.executable, 'recensement_doublons.py'],
                                 cwd=str(SCRIPT_DIR))
                res = {'ok': True, 'msg': 'Recensement (lecture seule) lance en arriere-plan.'}
            except Exception as e:                            # noqa: BLE001
                res = {'ok': False, 'error': str(e)}
        elif path == '/api/maint/plan-annee':
            threading.Thread(target=_run_plan_annee, daemon=True).start()
            res = {'ok': True, 'msg': 'Plan de rangement par annee en cours (lecture seule)...'}
        elif path == '/api/maint/plan-renommage':
            threading.Thread(target=_run_plan_renommage, daemon=True).start()
            res = {'ok': True, 'msg': 'Plan de renommage en cours (lecture seule) — docs/plan_renommage.md.'}
        elif path == '/api/maint/rename-check':
            res = appliquer_renommage(dry=True)
            if res.get('ok'):
                res['msg'] = (f"A blanc : {res['faits']} renommage(s) applicable(s), "
                              f"{res['sautes']} saute(s) sur {res['total_plan']}.")
        elif path == '/api/maint/rename-apply':
            res = appliquer_renommage(limite=RENOMMAGE_LOT, dry=False)
            if res.get('ok'):
                res['msg'] = (f"Lot applique : {res['faits']} renomme(s), "
                              f"{res['sautes']} saute(s). Reclique pour continuer.")
        elif path == '/api/maint/rename-undo':
            res = annuler_renommage()
            if res.get('ok'):
                res['msg'] = f"Annulation : {res['annules']} renommage(s) remis."
        elif path == '/api/maint/reclass-apercu':
            res = reclasser_animaux(dry=True)
            if res.get('ok'):
                det = ", ".join(f"{n['nom']} ({n['photos']})" for n in res['noms']) or "aucun"
                res['msg'] = (f"A blanc : {res['total_photos']} photo(s) a reclasser "
                              f"personne -> animal [{det}] ; "
                              f"{len(res['fiches_double'])} fiche(s) en double.")
        elif path == '/api/maint/reclass-apply':
            res = reclasser_animaux(dry=False)
            if res.get('ok'):
                if res['photos'] == 0 and not res.get('fiches_retirees'):
                    res['msg'] = "Rien a reclasser : tout est deja en animal:."
                else:
                    res['msg'] = (f"Reclasse : {res['photos']} photo(s) passees en animal: "
                                  f"[{', '.join(res['noms_traites']) or 'aucun'}] ; "
                                  f"{len(res['fiches_retirees'])} fiche(s) en double retiree(s). "
                                  f"Reversible (Annuler).")
        elif path == '/api/maint/recalage-apercu':
            res = recaler_rattachements(dry=True)
            if res.get('ok'):
                r = res['refus']
                res['msg'] = (
                    f"A blanc : {res['a_recaler']} rattachement(s) a recaler. "
                    + ("Refuses : " + ", ".join(
                        f"{v} {k.replace('_', ' ')}" for k, v in sorted(r.items()))
                       + "." if r else "Aucun refus.")
                    + " Un refus n'est pas un echec : la regle ne bouge une "
                      "decision humaine que lorsqu'elle est sure.")
        elif path == '/api/maint/recalage-apply':
            res = recaler_rattachements(dry=False)
            if res.get('ok'):
                res['msg'] = (
                    f"Recale : {res['a_recaler']} rattachement(s) remis sur le "
                    f"bon visage, {res.get('fiches', 0)} fiche(s) touchee(s). "
                    f"Reversible (Annuler).")
        elif path == '/api/maint/recalage-undo':
            res = annuler_recalage()
            if res.get('ok'):
                res['msg'] = (
                    f"Annulation : {res['fiches_remises']} fiche(s) remise(s)"
                    + (f", {res['fiches_modifiees_depuis']} laissee(s) telle(s) "
                       f"quelle(s) (jugees depuis)."
                       if res['fiches_modifiees_depuis'] else "."))
        elif path == '/api/maint/retrait-apercu':
            res = retirer_rattachements(dry=True)
            if res.get('ok'):
                # « 2 a retirer » apres coup se lit comme « il reste 2 a
                # faire ». Un apercu doit dire l'ETAT, pas repeter le plan.
                deja = (res['a_retirer'] and not res['retires']
                        and res['deja_absents'] >= res['a_retirer'])
                res['msg'] = (
                    (f"Deja fait : les {res['a_retirer']} rattachement(s) "
                     f"juge(s) faux ne sont plus dans les fiches. "
                     if deja else
                     f"A blanc : {res['a_retirer']} rattachement(s) juge(s) faux "
                     f"sur {res['fiches']} fiche(s). ")
                    + f"Confirmes par toi : {res['confirmes']}. "
                    + (f"{res['a_ajouter']} visage(s) reconnu(s) mais NON "
                       f"rattache(s) ne sont PAS touches ici : ajouter un nom "
                       f"est un autre geste. "
                       if res['a_ajouter'] else "")
                    + (f"{res['non_juges']} cas pas encore juge(s). "
                       if res['non_juges'] else "")
                    + (f"{res['indecidables']} laisse(s) indecidable(s). "
                       if res['indecidables'] else ""))
        elif path == '/api/maint/retrait-apply':
            res = retirer_rattachements(dry=False)
            if res.get('ok'):
                res['msg'] = (
                    f"Retire : {res['retires']} rattachement(s) juge(s) faux, "
                    f"{res.get('fiches', 0)} fiche(s) touchee(s). "
                    + (f"{res['deja_absents']} etai(en)t deja parti(s). "
                       if res['deja_absents'] else "")
                    + "Les tags des photos n'ont pas bouge. Reversible (Annuler).")
        elif path == '/api/maint/retrait-undo':
            res = annuler_retrait()
            if res.get('ok'):
                res['msg'] = (
                    f"Annulation : {res['fiches_remises']} fiche(s) remise(s)"
                    + (f", {res['fiches_modifiees_depuis']} laissee(s) telle(s) "
                       f"quelle(s) (jugees depuis)."
                       if res['fiches_modifiees_depuis'] else "."))
        elif path == '/api/maint/fusion-undo':
            res = annuler_fusion()
            if res.get('ok'):
                res['msg'] = (
                    f"Fusion defaite : {res['ancien']} rendu a "
                    f"{res['photos_rendues']} photo(s). Les fichiers du NAS "
                    f"repassent par la file d'ecriture."
                    + (f" {res['photos_disparues']} photo(s) ont disparu du "
                       f"fonds depuis." if res['photos_disparues'] else "")
                    + (" La fiche cible a ete jugee depuis : elle est laissee "
                       "telle quelle." if res['fiche_cible_jugee_depuis']
                       else ""))
        elif path == '/api/maint/recle-apercu':
            res = reparer_decisions_orphelines(dry=True)
            if res.get('ok'):
                res['msg'] = (
                    f"A blanc : {res['a_recler']} cle(s) a re-cler sur "
                    f"{res['cles_mortes']} orpheline(s) ; {res['sans_jumeau']} "
                    f"sans destination connue, {res['hors_bornes']} hors bornes. "
                    f"{res['deplacements_connus']} deplacement(s) connus des journaux.")
        elif path == '/api/maint/recle-apply':
            res = reparer_decisions_orphelines(dry=False)
            if res.get('ok'):
                res['msg'] = (
                    f"Re-cle : {res.get('decisions', 0)} decision(s) humaine(s) "
                    f"remises sur la bonne photo, {res.get('fiches', 0)} fiche(s) "
                    f"touchee(s). Reversible (Annuler).")
        elif path == '/api/maint/recle-undo':
            res = annuler_recle_decisions()
            if res.get('ok'):
                res['msg'] = (
                    f"Annulation : {res['fiches_remises']} fiche(s) remise(s)"
                    + (f", {res['fiches_modifiees_depuis']} laissee(s) telle(s) "
                       f"quelle(s) (jugees depuis)."
                       if res['fiches_modifiees_depuis'] else "."))
        elif path == '/api/maint/reclass-undo':
            res = annuler_reclassement()
            if res.get('ok'):
                res['msg'] = (f"Annulation : {res['photos']} photo(s) remises en personne:, "
                              f"{res['fiches_restaurees']} fiche(s) restauree(s).")
        else:
            self._send(404, b'Not found', 'text/plain')
            return
        self._send(200, json.dumps(res, ensure_ascii=False).encode(), 'application/json')

    def _serve_playlist(self):
        """Liste ORDONNÉE de photos pour le diaporama — sans remise, donc aucune
        répétition (contrairement à /api/random qui pioche avec remise).
        ?dir=… (même portée que /api/random) · ?mode=seq|rnd|assoc.
        seq = chronologique (mtime) · rnd = mélange complet · assoc = chaîne de
        tags. Construite depuis l'index en mémoire (rapide, pas de scan NAS)."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        dirparam = (q.get('dir') or [''])[0]
        mode = (q.get('mode') or ['seq'])[0]
        roots = media_roots()
        base_pkey = None
        if dirparam and dirparam != '0':
            parts = dirparam.split('/', 1)
            try:
                idx = int(parts[0])
                root = roots[idx][1]
            except (ValueError, IndexError):
                self._send(200, b'{"items": []}', 'application/json')
                return
            sub = parts[1] if len(parts) > 1 else ''
            try:
                base = (root / sub) if sub else root
            except OSError:
                self._send(200, b'{"items": []}', 'application/json')
                return
            base_pkey = _pkey(base)
        items = []
        for key, e in list(STORE.data.items()):
            if not isinstance(e, dict) or e.get('failed'):
                continue
            if base_pkey is not None:
                kp = _pkey(_resolve_key(key))
                if kp != base_pkey and not kp.startswith(base_pkey + '/'):
                    continue
            url = _url_for_key(key, roots)
            if not url:
                continue
            kw = list(dict.fromkeys((e.get('kw_fr') or []) + (e.get('kw_en') or [])))
            folder, gurl = _folder_link_for_key(key, roots)
            items.append({'url': url, 'name': Path(key).name, 'key': key,
                          'taken': _best_time(key, e), 'kw': kw,
                          'folder': folder, 'gurl': gurl})
        if mode == 'rnd':
            random.shuffle(items)
        elif mode == 'assoc':
            random.shuffle(items)          # départ varié
            items = _assoc_chain(items)
        else:                               # seq : chronologique, du + ANCIEN au + récent (défaut)
            # Photos sans date fiable (taken 0) reléguées en fin, comme la planche.
            items.sort(key=lambda it: it['taken'] or float('inf'))
        CAP = 12000
        items = items[:CAP]
        body = json.dumps({'items': items, 'mode': mode, 'total': len(items)},
                          ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_random(self):
        """Une photo au hasard sous ?dir=… — pioche instantanée pour le
        diaporama aléatoire en flux."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        dirparam = (q.get('dir') or [''])[0]
        if dirparam and dirparam != '0':
            roots = media_roots()
            parts = dirparam.split('/', 1)
            try:
                idx = int(parts[0])
                root = roots[idx][1]
            except (ValueError, IndexError):
                self._send(404, b'{}', 'application/json')
                return
            sub = parts[1] if len(parts) > 1 else ''
            base = root.resolve()
            try:
                folder = (root / sub).resolve() if sub else base
            except OSError:
                self._send(404, b'{}', 'application/json')
                return
            if (folder != base and base not in folder.parents) or not folder.is_dir():
                self._send(404, b'{}', 'application/json')
                return

            def url_for(p):
                return f'/media/{idx}/' + urllib.parse.quote(
                    p.relative_to(base).as_posix())
        else:
            folder = UPLOAD_DIR

            def url_for(p):
                return '/uploads/' + urllib.parse.quote(
                    p.relative_to(UPLOAD_DIR).as_posix())

        # Même piège de casse que la galerie : _random_photo marche sous
        # `folder`, issu d'un resolve() qui minuscule l'hôte SMB. Sans le
        # passage par l'index secondaire, le diaporama aléatoire du NAS
        # renvoyait des photos sans tags ni description, et une clé
        # minusculée que /api/similar ne retrouvait pas.
        p, key, entry = None, None, {}
        for _ in range(6):
            cand = _random_photo(folder)
            if cand is None:
                break
            ck = _index_key_for_path(cand)
            ce = (STORE.get(ck) if ck else None) or {}
            if not ce.get('failed'):
                p, key, entry = cand, ck, ce
                break
        if p is None:
            self._send(200, b'{"url": null}', 'application/json')
            return
        if key is None:   # fichier pas encore indexé : convention scan_uploads
            key = p.name if _pkey(p.parent) == _pkey(UPLOAD_DIR) else str(p)
        kw = list(dict.fromkeys(
            (entry.get('kw_fr') or []) + (entry.get('kw_en') or [])))
        folder, gurl = _folder_link_for_key(str(_resolve_key(key)))
        body = json.dumps({
            'url': url_for(p),
            'name': p.name,
            'key': key,
            'kw': kw,
            'desc': entry.get('desc', ''),
            'folder': folder,
            'gurl': gurl,
        }, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _serve_assoc(self):
        """Photo suivante du mode Association (tag commun + tag nouveau)."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        prev = (q.get('prev') or [''])[0]
        exclude = set((q.get('exclude') or [''])[0].split('|')) - {''}
        res = _assoc_next(prev, exclude) if prev else None
        if res is None:
            self._send(200, b'{"url": null}', 'application/json')
            return
        key, shared = res
        url = _url_for_key(key)
        e = STORE.data.get(key) or {}
        kw = list(dict.fromkeys(
            (e.get('kw_fr') or []) + (e.get('kw_en') or [])))
        folder, gurl = _folder_link_for_key(key)
        body = json.dumps({
            'url': url,
            'key': key,
            'name': Path(key).name,
            'kw': kw,
            'desc': e.get('desc', ''),
            'via': shared,
            'folder': folder,
            'gurl': gurl,
        }, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

    def _resolve_safe(self, rel):
        """Résout un chemin relatif en restant confiné dans UPLOAD_DIR."""
        rel = rel.replace('\\', '/').strip('/')
        base = UPLOAD_DIR.resolve()
        try:
            target = (UPLOAD_DIR / rel).resolve() if rel else base
        except OSError:
            return None
        if target != base and base not in target.parents:
            return None
        return target

    def _serve_health(self):
        """Liste les fichiers à problème : image illisible ou métadonnées
        non inscriptibles (EXIF endommagé)."""
        problems = []
        for name, e in sorted(STORE.data.items()):
            if e.get('failed'):
                problems.append((name, 'illisible',
                                 'Analyse IA impossible — ' + str(e.get('error', ''))[:150]))
            elif e.get('file_error') or e.get('write_fails', 0) >= 3:
                problems.append((name, 'exif',
                                 'Image OK mais métadonnées non inscriptibles — '
                                 + str(e.get('file_error', ''))[:150]))
        rows = []
        for name, kind, msg in problems:
            badge = '&#10060; illisible' if kind == 'illisible' else '&#9888;&#65039; EXIF endommagé'
            inner = (f'<span class="ic">{badge}</span>'
                     f'<span class="nm">{html.escape(name)}<br>'
                     f'<small style="color:#777">{html.escape(msg)}</small></span>')
            if Path(name).is_absolute():
                # dossier supplémentaire : pas servi par /uploads
                rows.append(f'<span class="row">{inner}</span>')
            else:
                href = '/uploads/' + urllib.parse.quote(name)
                rows.append(f'<a class="row" href="{href}" target="_blank">{inner}</a>')
        # Les FILS d'abord : un fichier illisible est un incident, un fil mort
        # est une panne qui arrête le travail sans que rien d'autre le dise.
        # C'est le manque exact du 27/08 — la mort était dans le journal, elle
        # n'était sur aucune page.
        fils = []
        for nom, e in sorted(fils_etat().items()):
            if e.get('fini') and not e.get('erreur'):
                continue                     # une tâche à un coup qui a fini
            if e.get('vivant') and not e.get('morts'):
                continue                     # au travail, jamais tombé
            depuis = time.time() - float(e.get('depuis') or time.time())
            etat = ('ALERTE' if e.get('alerte')
                    else ('mort' if not e.get('vivant') else 'reparti'))
            fils.append(
                f'<span class="row"><span class="ic">&#9888;&#65039; {etat}</span>'
                f'<span class="nm">{html.escape(nom)}<br>'
                f'<small style="color:#777">'
                f'{e.get("morts", 0)} mort(s), {e.get("consecutives", 0)} '
                f'd\'affilee &#183; depuis {depuis / 60:.0f} min &#183; '
                f'{html.escape(str(e.get("erreur") or ""))[:150]}'
                f'</small></span></span>')
        if fils:
            rows = fils + rows

        if rows:
            body = '\n'.join(rows)
            body += ('<p class="empty">Ces fichiers sont candidats à la suppression '
                     '(dans \\\\nas-bremblens\\home\\Uploads).<br>'
                     '« EXIF endommagé » = la photo s\'affiche mais ses métadonnées '
                     'sont corrompues (les tags restent dans la galerie).</p>')
        else:
            body = ('<p class="empty">Aucun fichier à problème détecté, '
                    'et les fils de travail tournent &#127881;</p>')
        page = (ui_page('browse')
                .replace('__EXTRA__', '')
                .replace('__CRUMBS__',
                         f'Santé — {len(problems)} fichier(s) à problème, '
                         f'{len(fils)} fil(s) à signaler')
                .replace('__CTX__', 'null')
                .replace('__ROWS__', body))
        self._send_html(page)

    def _serve_browse(self, url_path):
        rel = urllib.parse.unquote(url_path[len('/browse'):]).replace('\\', '/').strip('/')
        roots = media_roots()

        # racine : liste des dossiers navigables
        if not rel:
            rows = []
            for i, (label, root) in enumerate(roots):
                rows.append(f'<a class="row dir" href="/files?dir={i}">'
                            f'<span class="ic">&#128193;</span>'
                            f'<span class="nm">{html.escape(label)}</span>'
                            f'<span class="sz">{html.escape(str(root))}</span></a>')
            page = (ui_page('browse')
                    .replace('__EXTRA__', '')
                    .replace('__CRUMBS__', 'Dossiers')
                    .replace('__CTX__', 'null')     # racine : pas de gestion de fichiers
                    .replace('__ROWS__', '\n'.join(rows)))
            self._send_html(page)
            return

        parts = rel.split('/', 1)
        try:
            idx = int(parts[0])
            label, root = roots[idx]
        except (ValueError, IndexError):
            self._send(404, b'Not found', 'text/plain')
            return
        sub = parts[1] if len(parts) > 1 else ''
        base = root.resolve()
        try:
            d = (root / sub).resolve() if sub else base
        except OSError:
            self._send(404, b'Not found', 'text/plain')
            return
        if (d != base and base not in d.parents) or not d.is_dir():
            self._send(404, b'Not found', 'text/plain')
            return

        dirs, files = [], []
        try:
            for e in sorted(d.iterdir(), key=lambda p: p.name.lower()):
                if (e.name.startswith(('.', '@', '#')) or e.name == 'tags_index.json'
                        or e.name.endswith('_original')):
                    continue
                (dirs if e.is_dir() else files).append(e)
        except OSError as e:
            self._send(500, str(e).encode(), 'text/plain')
            return

        crumbs = ['<a href="/browse">Dossiers</a>',
                  f'<a href="/browse/{idx}">{html.escape(label)}</a>']
        acc = ''
        for part in [p for p in sub.split('/') if p]:
            acc += '/' + urllib.parse.quote(part)
            crumbs.append(f'<a href="/browse/{idx}{acc}">{html.escape(part)}</a>')

        rows = []
        for e in dirs:
            relf = (sub + '/' if sub else '') + e.name
            href = f'/browse/{idx}/' + urllib.parse.quote(relf)
            nm_a = html.escape(e.name, quote=True)
            rows.append(f'<div class="row dir" data-idx="{idx}" data-rel="{html.escape(relf, quote=True)}" data-name="{nm_a}">'
                        f'<input type="checkbox" class="sel" aria-label="Selectionner {nm_a}">'
                        f'<a class="lk" href="{href}"><span class="ic">&#128193;</span>'
                        f'<span class="nm">{html.escape(e.name)}</span></a></div>')
        # Les fichiers : une PLANCHE de vignettes (Mike, 30/08 : « une vue
        # avec les previews, comme une galerie »), pas une liste de noms.
        # Meme structure .row / .sel / .lk que la liste (la gestion de
        # fichiers — selection, renommer, couper, corbeille — lit ces
        # classes) ; seule la mise en page change. /api/thumb rend 512 px
        # (image OU image-cle d'une video) et REDIRIGE vers l'original quand
        # il ne sait pas — le client n'a aucun cas particulier.
        tuiles = []
        for e in files:
            relf = (sub + '/' if sub else '') + e.name
            href = f'/media/{idx}/' + urllib.parse.quote(relf)
            try:
                sz = human_size(e.stat().st_size)
            except OSError:
                sz = '?'
            ext = e.suffix.lower()
            nm_a = html.escape(e.name, quote=True)
            visuel = ext in IMAGE_EXT or ext in {'.mp4', '.mov', '.avi', '.mkv'}
            if visuel:
                thumb = ('/api/thumb?key='
                         + urllib.parse.quote(str(e), safe='') + '&s=512')
                badge = ('<span class="vid" aria-hidden="true">&#9654;</span>'
                         if ext not in IMAGE_EXT else '')
                tuiles.append(
                    f'<div class="row tuile" data-idx="{idx}" data-rel="{html.escape(relf, quote=True)}" data-name="{nm_a}">'
                    f'<input type="checkbox" class="sel" aria-label="Selectionner {nm_a}">'
                    f'<a class="lk" href="{href}" target="_blank">'
                    f'<img class="th" loading="lazy" src="{thumb}" alt="">{badge}'
                    f'<span class="nm">{html.escape(e.name)}</span></a>'
                    f'<span class="sz">{sz}</span></div>')
            else:
                rows.append(f'<div class="row" data-idx="{idx}" data-rel="{html.escape(relf, quote=True)}" data-name="{nm_a}">'
                            f'<input type="checkbox" class="sel" aria-label="Selectionner {nm_a}">'
                            f'<a class="lk" href="{href}" target="_blank"><span class="ic">&#128196;</span>'
                            f'<span class="nm">{html.escape(e.name)}</span></a>'
                            f'<span class="sz">{sz}</span></div>')
        if tuiles:
            rows.append('<div class="planche">' + '\n'.join(tuiles) + '</div>')

        dirval = f"{idx}/{sub}" if sub else str(idx)
        glink = ('<a class="back" href="/files?dir='
                 + urllib.parse.quote(dirval, safe='/')
                 + '">&#128444;&#65039; Galerie de ce dossier</a>')
        page = (ui_page('browse')
                .replace('__EXTRA__', glink)
                .replace('__CRUMBS__', ' / '.join(crumbs))
                .replace('__CTX__', json.dumps({"idx": idx, "sub": sub}))
                .replace('__ROWS__', '\n'.join(rows) or '<p class="empty">Dossier vide</p>'))
        self._send_html(page)

    # ── Éval en cours : notation à l'aveugle, atteignable en VPN ─────────────
    # Le banc (eval_tagging.py, hors serveur) génère eval/rating_v2sans.html ;
    # ces deux routes ne font que SERVIR cette page et RECEVOIR les notes,
    # pour pouvoir juger à distance sans geste fichier sur la machine.
    # Fichiers FIXES sous eval/ : aucun chemin ne vient du client, donc
    # aucune traversée possible.

    def _serve_eval_page(self):
        """GET /eval — sert eval/rating_v2sans.html telle quelle. Relue à
        chaque requête (pas de cache : elle change entre deux runs d'éval).
        Disque local, pas le NAS — pas de note_heavy_activity()."""
        f = SCRIPT_DIR / 'eval' / 'rating_v2sans.html'
        try:
            body = f.read_bytes()
        except OSError:
            self._send(404, "Aucune éval en cours "
                       "(eval/rating_v2sans.html absent).".encode(),
                       'text/plain; charset=utf-8')
            return
        self._send(200, body, 'text/html; charset=utf-8')

    def _do_eval_notes(self):
        """POST /eval/notes — reçoit le JSON de la page /eval et l'écrit dans
        eval/notes_v2sans.json, atomiquement (tmp + os.replace, disque local,
        modèle TagStore._save). Taille bornée (les notes font ~2 Ko ; on coupe
        à 1 Mo) et JSON validé : un corps illisible ne remplace jamais des
        notes déjà déposées."""
        try:
            n = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            n = 0
        if not 0 < n <= 1_000_000:
            self._send(400, b'Taille invalide', 'text/plain; charset=utf-8')
            return
        try:
            notes = json.loads(self.rfile.read(n))
        except Exception:
            notes = None
        if not isinstance(notes, dict) or not notes:
            self._send(400, b'JSON invalide', 'text/plain; charset=utf-8')
            return
        dest = SCRIPT_DIR / 'eval' / 'notes_v2sans.json'
        tmp = dest.with_name(dest.name + '.tmp')
        try:
            tmp.write_text(json.dumps(notes, ensure_ascii=False, indent=1),
                           encoding='utf-8')
            os.replace(tmp, dest)
        except OSError as e:
            self._send(500, f"Écriture impossible : {e}".encode(),
                       'text/plain; charset=utf-8')
            return
        print(f"  📝 Notes d'éval reçues → {dest.name} ({len(notes)} cartes)")
        self._send(200, json.dumps({"ok": True, "cartes": len(notes)}).encode(),
                   'application/json')

    def _serve_media(self, url_path):
        """Sert un fichier depuis une racine de media_roots(), confiné."""
        note_heavy_activity()
        rel = urllib.parse.unquote(url_path[len('/media/'):]).replace('\\', '/').strip('/')
        parts = rel.split('/', 1)
        roots = media_roots()
        try:
            idx = int(parts[0])
            root = roots[idx][1]
            sub = parts[1]
        except (ValueError, IndexError):
            self._send(404, b'Not found', 'text/plain')
            return
        base = root.resolve()
        try:
            filepath = (root / sub).resolve()
        except OSError:
            self._send(404, b'Not found', 'text/plain')
            return
        if (filepath != base and base not in filepath.parents) or not filepath.is_file():
            self._send(404, b'Not found', 'text/plain')
            return
        if not chemin_visible(filepath):       # 17b : le PRIVE d'un autre, 404
            self._send(404, b'Not found', 'text/plain')
            return
        self._send_file(filepath)

    def _serve_file(self, url_path):
        rel = urllib.parse.unquote(url_path[len('/uploads/'):])
        filepath = self._resolve_safe(rel)
        if filepath is None or not filepath.is_file():
            self._send(404, b'Not found', 'text/plain')
            return
        if not chemin_visible(filepath):       # 17b
            self._send(404, b'Not found', 'text/plain')
            return
        self._send_file(filepath)

    def _send_file(self, filepath):
        """Streaming par blocs + Range (audit O2). Avant : read_bytes() —
        un .mp4 de 500 Mo = 500 Mo de RAM PAR REQUÊTE, et sans Accept-Ranges
        le téléphone ne pouvait pas chercher dans une vidéo (le navigateur
        exige des réponses 206 pour le seek). Range géré : « bytes=a-b »,
        « bytes=a- » et « bytes=-n » ; malformé → 200 complet (toléré par la
        norme), hors bornes → 416."""
        ext = filepath.suffix.lower()
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.gif': 'image/gif', '.webp': 'image/webp', '.heic': 'image/heic',
            '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.avi': 'video/x-msvideo',
        }
        mime = mime_map.get(ext, 'application/octet-stream')
        try:
            size = filepath.stat().st_size
        except OSError:
            self._send(404, b'Not found', 'text/plain')
            return
        start, end, partial = 0, size - 1, False
        rng = self.headers.get('Range', '')
        m = re.match(r'bytes=(\d*)-(\d*)$', rng.strip()) if rng else None
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
            else:                       # « bytes=-n » : les n derniers octets
                start = max(0, size - int(m.group(2)))
            if start >= size or start > end:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
            partial = True
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', mime)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Disposition', f'inline; filename="{filepath.name}"')
        self.end_headers()
        with open(filepath, 'rb') as f:
            f.seek(start)
            reste = end - start + 1
            while reste > 0:
                bloc = f.read(min(1024 * 1024, reste))
                if not bloc:
                    break
                self.wfile.write(bloc)
                reste -= len(bloc)

    def _send_html(self, html_str):
        # Barre de navigation + thème partagés : injectés là où le gabarit
        # contient le marqueur <!--APPNAV--> (nav) et avant </head> (thème).
        if '</head>' in html_str and 'appnav-css' not in html_str:
            html_str = html_str.replace('</head>', APP_NAV_CSS + '</head>', 1)
        # Design system partage (tokens + plancher d'accessibilite). Apres
        # APP_NAV_CSS, donc au plus pres de </head>. Le marqueur « ui-shared »
        # evite la double injection quand bundle.py a deja cuit le CSS.
        if '</head>' in html_str and 'ui-shared' not in html_str:
            shared = ui_shared_css()
            if shared:
                html_str = html_str.replace('</head>', shared + '</head>', 1)
        # Adoption du design system : la page a pose le marqueur la ou elle
        # veut la feuille. Remplace meme par une chaine vide — un marqueur qui
        # resterait dans le HTML serait un commentaire muet, et on ne saurait
        # pas si la page a adopte ou si ui/ manquait.
        if _UI_COMPOSANTS_MARQUEUR in html_str:
            html_str = html_str.replace(_UI_COMPOSANTS_MARQUEUR,
                                        ui_composants_css(), 1)
        if '<!--APPNAV-->' in html_str:
            html_str = html_str.replace('<!--APPNAV-->', APP_NAV_HTML)
        html_str = injecter_js_commun(html_str, ui_shared_js())
        # Sous-navigation Sujets (guichet unique) : /sujets, /people, /pets.
        if '<!--SUJETSNAV-->' in html_str:
            html_str = html_str.replace('<!--SUJETSNAV-->', SUJETS_NAV_HTML)
        data = html_str.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def pilotage_loop():
    """Veille sur `_commande_serveur.txt` : arrêt et redémarrage COMMANDÉS.

    Le protocole, ses raisons et ses garde-fous sont dans `pilotage.py`. Ici,
    seulement le geste : lire un mot toutes les deux secondes (un `stat` local,
    jamais le NAS) et sortir quand il le dit.

    POURQUOI `os._exit` ET PAS UN ARRÊT PROPRE. Le redémarrage existant
    (`0 - Demarrer le serveur.bat`, appelé par le bat 27) fait un
    `taskkill /F` : ce chemin-ci n'est donc pas plus brutal que celui qu'il
    remplace, il est seulement déclenché autrement. Et il est sûr pour la même
    raison que l'autre l'était : les écritures d'index sont atomiques et
    validées une par unité de travail (invariant 2), donc il n'existe aucun
    instant où mourir laisse une donnée à moitié écrite. Un `serve_forever`
    interrompu proprement, lui, attendrait des workers qui peuvent tenir une
    lecture NAS de plusieurs minutes — un redémarrage qui ne redémarre pas est
    pire qu'un redémarrage sec.

    Le processus ne se relance jamais lui-même : il sort, et `superviseur.bat`
    décide. Un processus qui organiserait sa propre résurrection ne pourrait
    pas garantir que le port est libéré avant de le reprendre.
    """
    import pilotage
    chemin = SCRIPT_DIR / pilotage.FICHIER
    while True:
        time.sleep(pilotage.PERIODE_S)
        try:
            cmd = pilotage.lire(chemin)
        except Exception:                                     # noqa: BLE001
            continue                    # une veille ne doit jamais tuer l'hôte
        if not pilotage.doit_sortir(cmd):
            continue
        print(f"\n[pilotage] commande recue : {cmd} — arret du serveur "
              f"(code {pilotage.CODE_REDEMARRAGE}).", flush=True)
        try:
            sys.stdout.flush()
        except Exception:                                     # noqa: BLE001
            pass
        os._exit(pilotage.CODE_REDEMARRAGE)


# ─────────────────────── La temperature, au JOURNAL ─────────────────────
# Le 28/08 a 23:10:15 la machine s'est coupee net sous charge : Kernel-Power 41,
# aucun minidump, rien dans le journal. Le seul indice etait INDIRECT, et je l'ai
# d'abord mal lu : la session qui est morte taguait a 27,2 s de moyenne contre
# 9,7 a 22,8 s pour toutes les autres du jour, et 14,0 s apres le redemarrage a
# froid sur le meme travail. Deduire un bridage d'un chronometre, c'est tenir
# une opinion. La carte, elle, sait dire sa temperature ET NOMMER la cause de
# son ralentissement : il suffisait de le lui demander.
#
# Le journal porte deja les durees de tagging. Y joindre la temperature les
# corrole PAR CONSTRUCTION -- plus aucun fichier a croiser a la main.
THERMIQUE_PERIODE_S = 60.0    # un releve par minute
THERMIQUE_TRACE_S = 600.0     # une ligne toutes les 10 min en regime normal
THERMIQUE_CHAUD_C = 85        # au-dela : on trace CHAQUE releve


def thermique_loop():
    """Releve la temperature du GPU et l'ecrit au journal.

    Discret quand tout va bien (une ligne toutes les 10 min), bavard des que ca
    chauffe ou que la carte AVOUE brider. Un journal qui deverse ne se lit pas ;
    un journal muet ne sert a rien le jour ou la machine tombe."""
    dernier = 0.0
    etait_bride = False
    while True:
        time.sleep(THERMIQUE_PERIODE_S)
        g = (hw_state() or {}).get('gpu') or {}
        t = g.get('temp_c')
        if t is None:
            continue                  # pas de sonde : rien a dire, jamais
        bride = bool(g.get('bride_thermique'))
        chaud = t >= THERMIQUE_CHAUD_C
        maintenant = time.time()
        # On ecrit sur un EVENEMENT (ca chauffe, ou le bridage vient de
        # basculer) ou sur le rythme lent. Le basculement compte autant que
        # l'etat : c'est l'instant qu'on cherchera dans le journal.
        if not (chaud or bride or bride != etait_bride
                or maintenant - dernier >= THERMIQUE_TRACE_S):
            continue
        dernier = maintenant
        etait_bride = bride
        marque = "  🌡" if not (chaud or bride) else "  🔥 CHAUD"
        print("%s GPU %s°C — %s%% — %s/%s MHz — %s W%s"
              % (marque, t, g.get('util'), g.get('clocks_mhz'),
                 g.get('clocks_max_mhz'), g.get('watts'),
                 " — BRIDAGE THERMIQUE" if bride else ""), flush=True)


# ─────────────────── Surveillance des fils de travail ───────────────────
# Le 27/08 à 23:42:50, `tagger_worker` est mort sur un verrou SQLite. Sa file
# s'est remplie, le serveur est resté d'apparence parfaitement vivante, et la
# panne a été découverte à 07:43 par un humain — HUIT HEURES. `journal_serveur`
# posait le constat depuis le 23/08 ; personne ne le lisait.
#
# Règle de Mike (28/08) : un fil de travail mort SE RELANCE, et cinq morts
# consécutives ALERTENT. « Consécutives » se compte sur les morts SANS reprise
# qui tient entre elles — un fil qui a travaillé cinq minutes remet le compteur
# à zéro, sinon une mort par jour finirait par ressembler à une boucle. Passé
# cinq, on continue de relancer — renoncer ramènerait exactement la panne qu'on
# répare — mais l'alerte est permanente sur `/sante` et répétée au journal, qui
# se lit à distance.
FILS = {}
FILS_LOCK = threading.Lock()
FIL_REPRISE_S = 300.0      # une reprise qui tient 5 min remet le compteur à zéro
FIL_ALERTE = 5             # cinq morts d'affilée : une panne dure, pas un incident
FIL_PAUSE_S = 1.0          # attente avant la 1re relance, doublée ensuite
FIL_PAUSE_MAX_S = 300.0    # plafond : on n'abandonne pas, on espace
FIL_RAPPEL_S = 600.0       # une alerte se répète, sans inonder le journal


def fils_etat():
    """Instantané du registre — pour `/sante` et pour les bancs."""
    with FILS_LOCK:
        return {nom: dict(e) for nom, e in FILS.items()}


def _fil_note(nom, **champs):
    with FILS_LOCK:
        e = FILS.setdefault(nom, {'morts': 0, 'consecutives': 0, 'alerte': False,
                                  'vivant': True, 'fini': False,
                                  'depuis': time.time(), 'erreur': None,
                                  'boucle': True})
        e.update(champs)
        return dict(e)


def _fil_tourne(cible, nom, boucle, args, dormir, continuer):
    """La vie d'un fil surveillé : il travaille, il meurt, il repart.

    `continuer` est le seul paramètre qui n'existe que pour la MESURE — un banc
    ne peut pas observer une boucle infinie. Il vaut None en production, et la
    boucle est alors vraiment sans fin."""
    attente = FIL_PAUSE_S
    dernier_cri = 0.0
    tour = 0
    while continuer is None or continuer(tour):
        tour += 1
        _fil_note(nom, vivant=True, depuis=time.time())
        debut = time.time()
        propre, erreur = False, None
        try:
            cible(*args)
            propre = True
        except Exception as e:                                # noqa: BLE001
            erreur = f"{type(e).__name__}: {e}"
            # La trace s'imprime ICI. En rattrapant l'exception on prive
            # `threading.excepthook` de son passage : sans cette ligne, on
            # échangerait huit heures d'arrêt contre la PERTE du diagnostic
            # qui a permis de comprendre la panne. Le journal garde les deux.
            traceback.print_exc()
        duree = time.time() - debut

        if propre and not boucle:
            _fil_note(nom, vivant=False, fini=True, erreur=None)
            return                  # une tâche à un coup a le DROIT de finir

        if erreur is None:
            erreur = "rendu sans erreur (un fil de travail ne doit pas rendre)"
        tenu = duree >= FIL_REPRISE_S
        with FILS_LOCK:
            e = FILS.setdefault(nom, {'morts': 0, 'consecutives': 0})
            e['morts'] = e.get('morts', 0) + 1
            e['consecutives'] = 1 if tenu else e.get('consecutives', 0) + 1
            e['vivant'] = False
            e['erreur'] = erreur
            e['alerte'] = e['consecutives'] >= FIL_ALERTE
            consecutives, alerte = e['consecutives'], e['alerte']
        print(f"  FIL MORT : {nom} : {erreur} — apres {duree:.0f}s, "
              f"{consecutives} d affilee", flush=True)

        if not boucle:
            # Une tâche à un coup qui échoue se DIT, elle ne se rejoue pas :
            # un backfill relancé en boucle referait son travail sans le savoir.
            _fil_note(nom, fini=True)
            return

        maintenant = time.time()
        if alerte and maintenant - dernier_cri >= FIL_RAPPEL_S:
            dernier_cri = maintenant
            print(f"  ALERTE : {nom} est mort {consecutives} fois d affilee — "
                  f"derniere cause : {erreur}. Voir /sante.", flush=True)
        if tenu:
            attente = FIL_PAUSE_S
        (dormir or time.sleep)(attente)
        attente = min(attente * 2, FIL_PAUSE_MAX_S)


def fil_surveille(cible, nom=None, boucle=True, args=(), dormir=None,
                  continuer=None, demarrer=True):
    """Lance `cible` dans un fil SURVEILLÉ, qui se relance s'il doit boucler.

    `boucle=True` : le fil ne doit jamais rendre — une exception COMME un
    retour sont des morts, et il repart. **Il repart de la FILE, jamais de
    l'élément qu'il tenait** : `task_done()` vit dans un `finally`, un fil tué
    avant laisse déjà un compteur faussé, et rejouer l'élément le fausserait
    une seconde fois.

    `boucle=False` : une tâche à un coup. Elle a le droit de FINIR ; si elle
    échoue, sa mort est enregistrée et VISIBLE, mais elle n'est pas rejouée."""
    nom = nom or getattr(cible, '__name__', 'fil')
    _fil_note(nom, vivant=True, fini=False, depuis=time.time(), boucle=boucle,
              morts=0, consecutives=0, alerte=False, erreur=None)
    t = threading.Thread(target=_fil_tourne, name=nom, daemon=True,
                         args=(cible, nom, boucle, tuple(args), dormir,
                               continuer))
    if demarrer:
        t.start()
    return t


class QuietServer(ThreadingHTTPServer):
    """N'affiche pas de traceback quand un téléphone ferme sa connexion."""

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                            BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


if __name__ == '__main__':
    ip = get_local_ip()

    # Migration éventuelle du pipeline animaux (modèles/seuils changés) AVANT de
    # lancer les workers, pour repartir sur une base propre (pas de dimensions
    # d'empreintes mélangées).
    migrate_animal_pipeline()

    # La commande repasse à « marche » AVANT que la veille ne démarre : sans
    # cela, un processus relancé lirait le « redemarrer » qui l'a fait naître
    # et ressortirait aussitôt — une boucle de redémarrage, à la milliseconde
    # près, et sans rien pour la dire.
    try:
        import pilotage
        pilotage.ecrire(SCRIPT_DIR / pilotage.FICHIER, 'marche')
        fil_surveille(pilotage_loop)
    except Exception as e:                                    # noqa: BLE001
        print(f"  ⚠ Pilotage par fichier indisponible ({e}) — "
              f"redemarrage uniquement par les bats.")

    # Qui BOUCLE et qui REND a été MESURÉ, pas supposé : un `while True:` dans
    # l'AST de chaque fonction. Se tromper de colonne ici relancerait sans fin
    # une tâche qui avait simplement fini son travail.
    fil_surveille(tagger_worker)
    fil_surveille(maintenance_loop)
    fil_surveille(_backfill, nom='backfill:gps', boucle=False,
                  args=('gps', backfill_gps))
    fil_surveille(_backfill, nom='backfill:dates', boucle=False,
                  args=('dates', backfill_dates))
    fil_surveille(reconcile_named_tags, boucle=False)
    fil_surveille(_backfill, nom='backfill:noms', boucle=False,
                  args=('noms', reimport_name_tags))
    # Le plan de rangement par année se RECALCULE à chaque démarrage. Le 29/08,
    # bat 26 a relu un plan de la veille (cibles RACINE) parce que seul le
    # bouton Réglages le régénérait ; et appliquer_plan_annee REFUSE désormais
    # un plan plus vieux que la bannière DEMARRAGE — ce recalcul est ce qui le
    # rend applicable. Lecture seule de l'index, pas de NAS. Un coup, pas une boucle.
    fil_surveille(_run_plan_annee, nom='plan:annee', boucle=False)
    # Chantier 17 : les décisions existantes appartiennent à Mike (une passe,
    # idempotente, journalisée dans docs/migration_auteurs.json).
    fil_surveille(migrer_auteurs, nom='migration:auteurs', boucle=False)
    fil_surveille(face_worker)
    fil_surveille(face_scan_loop)
    fil_surveille(animal_worker)
    fil_surveille(animal_scan_loop)
    fil_surveille(pet_embed_loop)
    fil_surveille(rederive_pet_refs)
    fil_surveille(cat_curator_loop)
    _file_personnes_reprise()   # AVANT l'ecrivain : la file d'abord
    fil_surveille(person_writer)
    fil_surveille(curator_loop)
    fil_surveille(reembed_loop)
    fil_surveille(semantic_loop)
    fil_surveille(maintenance_orchestrator)
    fil_surveille(thermique_loop)

    with QuietServer(('', PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        print()
        print("  ╔══════════════════════════════════════╗")
        print("  ║  📸  Photo Upload Server v10 + IA    ║")
        print("  ╠══════════════════════════════════════╣")
        print(f"  ║  Ouvrir sur le téléphone :           ║")
        url = f"http://{ip}:{PORT}"
        print(f"  ║  {url:<36}║")
        print("  ║                                      ║")
        print(f"  ║  Dossier : {str(UPLOAD_DIR)[:27]:<27}║")
        print(f"  ║  Modèle IA : {MODEL:<24}║")
        print("  ║  Ctrl+C pour arrêter                 ║")
        print("  ╚══════════════════════════════════════╝")
        print()
        httpd.serve_forever()
# v10.1
