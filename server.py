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
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
UPLOAD_DIR = None
if len(sys.argv) > 1:
    UPLOAD_DIR = Path(sys.argv[1])
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

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
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
PERSON_QUEUE = queue.Queue()          # (chemin, tag) à écrire dans les fichiers
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
        """Valide l'attribution de photos au sujet (écrit le tag)."""
        name = (name or "").strip()[:60]
        if not name:
            return 0
        tag = f"{self.prefix}:{name}"
        n = 0
        for k in keys:
            _index_add_person(k, tag)
            _enqueue_person_write(k, tag)
            n += 1
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
        """Renomme un sujet : remplace <prefix>:Ancien par <prefix>:Nouveau
        partout (index + fichiers) et fusionne les fiches."""
        old = (old or "").strip()
        new = (new or "").strip()[:60]
        if not old or not new or old.lower() == new.lower():
            return 0
        oldtag, newtag = f"{self.prefix}:{old}", f"{self.prefix}:{new}"
        n = 0
        for k, e in list(STORE.data.items()):
            if _kw_has(e, oldtag):
                _index_remove_person(k, oldtag)
                _index_add_person(k, newtag)
                _enqueue_person_write(k, oldtag, 'del')
                _enqueue_person_write(k, newtag, 'add')
                n += 1
        op = self.store.data.pop(old.lower(), None)
        if op:
            npp = self.store.data.get(new.lower())
            if npp is None:
                npp = self._new_entry(new, op.get("species") if self.species else None)
            npp["name"] = new
            npp["refs"] = ((npp.get("refs") or []) + (op.get("refs") or []))[:80]
            npp["exclude"] = list(set((npp.get("exclude") or [])
                                      + (op.get("exclude") or [])))
            npp["faces"] = _merge_assigned(
                npp.get("faces"),
                [(x[0], x[1]) for x in (op.get("faces") or [])
                 if isinstance(x, (list, tuple)) and len(x) == 2])
            self.store.set(new.lower(), npp)
        STORE.save()
        return n

    def delete(self, name):
        """Supprime entièrement un sujet : retire son tag partout et efface
        sa fiche. Les tags dans les FICHIERS sont retirés via la file."""
        name = (name or "").strip()[:60]
        if not name:
            return 0
        tag = f"{self.prefix}:{name}"
        n = 0
        for k, e in list(STORE.data.items()):
            if _kw_has(e, tag):
                _index_remove_person(k, tag)
                _enqueue_person_write(k, tag, 'del')
                n += 1
        self.store.data.pop(name.lower(), None)
        self.store.save()
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

def ensure_exiftool():
    w = shutil.which("exiftool")
    if w:
        return Path(w)
    # un exiftool*.exe déposé n'importe où dans le dossier du projet ?
    try:
        hits = sorted(SCRIPT_DIR.rglob("exiftool*.exe"))
    except OSError:
        hits = []
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
    """Reconstruit les métadonnées d'un fichier au bloc EXIF endommagé.
    ExifTool réécrit toutes les métadonnées lisibles ; une sauvegarde
    « nom.jpg_original » est conservée à côté du fichier."""
    if not EXIFTOOL:
        return False
    print(f"  🔧 Réparation EXIF : {path.name}")
    r = _run_exiftool(["-all=", "-tagsfromfile", "@", "-all:all", "-unsafe",
                       "-charset", "filename=UTF8", str(path)])
    if r.returncode != 0:
        print(f"  ⚠ Réparation échouée : {r.stderr.strip()[:150]}")
        return False
    print(f"  ✓ Métadonnées reconstruites — sauvegarde *_original conservée")
    return True


def write_metadata(path, keywords, desc):
    """Écrit les mots-clés/description dans le fichier (XMP + IPTC + XPKeywords)."""
    global LAST_WRITE_ERROR
    LAST_WRITE_ERROR = ""
    if not EXIFTOOL:
        return _write_metadata_piexif(path, keywords, desc)
    args = ["-overwrite_original", "-q", "-m",
            "-charset", "filename=UTF8", "-codedcharacterset=utf8"]
    for k in keywords:
        args.append(f"-MWG:Keywords={k}")
    if desc:
        args.append(f"-MWG:Description={' '.join(desc.split())}")
    if path.suffix.lower() in ('.jpg', '.jpeg'):
        args.append(f"-XPKeywords={'; '.join(keywords)}")
    args.append(str(path))
    try:
        r = _run_exiftool(args)
        if r.returncode != 0:
            LAST_WRITE_ERROR = r.stderr.strip()[:200]
            print(f"  ⚠ ExifTool: {LAST_WRITE_ERROR}")
            return False
        return True
    except Exception as e:
        LAST_WRITE_ERROR = str(e)[:200]
        print(f"  ⚠ ExifTool: {e}")
        return False


def _norm_import_kw(k):
    """Normalise un mot-clé importé d'un fichier. Les mots-clés IA sont en
    minuscules ; on aligne dessus SAUF les tags nommés « personne:… » et
    « animal:… » dont on PRÉSERVE la casse (sinon « personne:Nom » deviendrait
    « personne:nom » et ne correspondrait plus au nom dans people.json/pets.json)."""
    s = str(k).strip()
    low = s.lower()
    if low.startswith('personne:') or low.startswith('animal:'):
        return s
    return low


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
        e = STORE.data.get(key)
        if isinstance(e, dict):
            for t in (e.get('kw_fr') or []):
                tl = str(t).lower()
                if ((tl.startswith('personne:') or tl.startswith('animal:'))
                        and tl not in exclus):
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
            parts = _chemin_relatif(k).replace('/', '\\').split('\\')[:-1]
        except Exception:
            parts = list(Path(k).parts)[:-1]
        for p in reversed(parts):
            lieu = _lieu_plausible(p)
            if not lieu:
                continue
            for cand in [lieu] + [m for m in lieu.split() if len(m) >= 5]:
                if _sans_accents(cand) in lx:
                    return lx[_sans_accents(cand)], 'chemin'
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


def _path_years(key):
    """TOUTES les années (19xx/20xx) portées par le CHEMIN, en entiers.

    L'ensemble, pas seulement la plus ancienne : un dossier peut porter une
    PLAGE (« Photos 2005-2010\\2008\\… ») et exiger l'égalité avec le seul
    minimum ferait reculer la photo de trois ans. Sert de garde-fou aux dates
    EXIF des photos scannées (`tagging_meta.date_fiable`)."""
    return {int(y) for y in re.findall(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)', str(key))
            if 1990 <= int(y) <= 2100}


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
    Renvoie un timestamp epoch (0 si rien)."""
    precise = []
    t = e.get('taken') if isinstance(e, dict) else None
    if isinstance(t, (int, float)) and t > 0:
        precise.append(t)
    fn = _fname_time(Path(key).name)
    if fn:
        precise.append(fn)
    if precise:
        return min(precise)
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


def tagger_worker():
    fails = {}
    downs = {}
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
                STORE.set(name, {"failed": True, "error": f"timeout Ollama x{n}",
                                 "at": time.time()})
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
                STORE.set(name, {"failed": True, "error": str(e)[:200],
                                 "at": time.time()})
                pending_done(name)
        except Exception as e:
            print(f"  ✗ Erreur tagging {name}: {e} — listé sur /sante")
            STORE.set(name, {"failed": True, "error": str(e)[:200],
                             "at": time.time()})
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
        if first and len(unknown) > 200:
            print(f"  🔍 Lecture des métadonnées existantes de {len(unknown)} "
                  f"fichier(s) (par lots de 40, patience)…")
        # `vus` inutile ici : une lecture ratée renvoie simplement la photo à la
        # file de tagging IA — rien n'est perdu, rien n'est marqué.
        existing, _vus = read_existing_metadata([cur[k] for k in unknown],
                                                progress=first)
        n_import = n_queue = 0
        for k in unknown:
            p = cur[k]
            size, mtime = _stat_of(p)
            meta = existing.get(_pkey(p))
            if meta:
                kw, desc = meta
                STORE.set(k, {"kw_fr": kw, "kw_en": [], "desc": desc,
                              "in_file": True, "at": time.time(),
                              "size": size, "mtime": mtime,
                              "imported": True}, save=False)
                n_import += 1
            else:
                enqueue(k)
                n_queue += 1
        STORE.save()
        print(f"  🏷  {label} : {n_queue} photo(s) à taguer"
              + (f", {n_import} importée(s)" if n_import else ""))
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
                changed.append(k)
        if changed:
            STORE.remove_many(changed)
            for k in changed:
                enqueue(k)
            print(f"  ♻ {label} : {len(changed)} fichier(s) modifié(s) → re-tagging")

    # 4) fichiers disparus : nettoyage (la racine vient d'être listée, donc joignable)
    #    forget_everywhere purge en cascade tags + détections visages/animaux +
    #    vecteur sémantique (avant : STORE seul → détections orphelines, bug ARZOPA).
    #    Les fiches nommées (PEOPLE/PETS, keyées par nom) ne sont pas touchées.
    if orphans:
        n = forget_everywhere(orphans)
        if n:
            print(f"  🧹 {label} : {n} entrée(s) de fichiers disparus retirée(s)"
                  f" (tags + visages/animaux + vecteurs)")


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
                if f.is_file() and f.suffix.lower() in IMAGE_EXT
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
                     if p.is_file() and p.suffix.lower() in IMAGE_EXT
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
      - sujets : `rekey` + `save`. Le `save` (`_reconcilier`) supprime l'ancienne
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
    moved = STORE.rekey(old, new, mtime=mtime)
    if not moved:
        return False
    subject_stores = (FACE_STORE, PEOPLE_STORE, ANIMAL_STORE, PETS_STORE)
    for st in subject_stores:
        try:
            st.rekey(old, new, mtime=mtime)
        except Exception as e:
            print(f"  ⚠ re-clé {getattr(st, 'path', st)} {old!r}→{new!r} : {e}")
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


def forget_everywhere(keys):
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
    """
    keys = [k for k in keys if k]
    if not keys:
        return 0
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
                str(kw).startswith(('personne:', 'animal:'))
                for kw in (se.get('kw_fr') or [])):
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
        forget_everywhere(fantomes)
    return fantomes


# ─── Operations de fichiers (vue Dossiers) ───────────────────────────────────
# Logique pure et testee dans fichiers.py (module stdlib, import leger). La
# re-cle de l'index passe par rekey_everywhere : un deplacement/renommage ne
# perd jamais un nom humain. « Supprimer » = quarantaine reversible, jamais rm.
import fichiers
FILE_OPS = None
FILE_OPS_LOCK = threading.Lock()
FILES_TRASH_DIR = SCRIPT_DIR / ".corbeille-rangement"


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
            trash_dir=FILES_TRASH_DIR)
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
    """Clés dont l'index contient TOUS les tags demandés."""
    besoin = [t.lower() for t in tags]
    out = set()
    for k, e in list(STORE.data.items()):
        if e.get('failed'):
            continue
        kw = [str(x).lower() for x in
              ((e.get('kw_fr') or []) + (e.get('kw_en') or []))]
        if all(t in kw for t in besoin):
            out.add(k)
    return out


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
_LIEUX_BRUIT = re.compile(
    r'^(?:\d+|camera|dcim|photos?|images?|divers|screenshots?|whatsapp'
    r'|samsung|iphone|xiaomi|huawei|pixel|sauvegardes?|export\w*)$', re.I)


def _lieu_plausible(nom):
    """Un dossier est-il un nom de lieu ? Heuristique, corrigeable à la main."""
    n = re.sub(r'^\d{2,8}[-_ ]*', '', str(nom)).strip()      # « 240211_… »
    n = re.sub(r'\b(19|20)\d{2}\b', '', n).strip()           # année
    n = re.sub(r'^\d{1,2}[ .\-]+', '', n).strip()            # « 07 Voyage… »
    if len(n) < 4 or _LIEUX_BRUIT.match(n):
        return None
    mots = [m for m in re.split(r'[\s_\-]+', n) if len(m) > 2
            and not _LIEUX_BRUIT.match(m)]
    return ' '.join(mots) if mots else None


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
    s = str(k)
    bas = s.lower().replace('/', '\\')
    for _lbl, racine in (roots if roots is not None else media_roots()):
        r = str(racine).lower().replace('/', '\\').rstrip('\\')
        if bas.startswith(r):
            return s[len(r):]
    return s


def _cles_du_lieu(lieux):
    """Clés dont le chemin, sous la racine média, contient tous ces lieux."""
    besoin = [_sans_accents(l) for l in lieux]
    roots = media_roots()          # 1× : sinon _chemin_relatif relit config + stats NAS par clé
    out = set()
    for k in list(STORE.data):
        chemin = _sans_accents(_chemin_relatif(k, roots))
        if all(b in chemin for b in besoin):
            out.add(k)
    return out


def semantic_search(requete, limite=80):
    """Recherche HYBRIDE : noms humains + lieu + sens de l'image.

    SigLIP ne connaît pas « Luna » ni « Mike » : ce sont des étiquettes posées
    par un humain, invisibles au contenu visuel. On les traite donc à part —
    filtrage exact sur le tag — puis on classe le sous-ensemble obtenu par
    similarité sémantique sur le reste de la phrase.
    """
    sem = _semantic_mod()
    vs = photo_vectors()
    tags, reste = _extraire_noms(requete)
    lieux, reste = _extraire_lieux(reste)

    # Trois dimensions se combinent : QUI (tags posés par un humain), OÙ
    # (chemin du fichier), et QUOI (sens de l'image). Chacune filtre, la
    # dernière classe. « Luna à Bremblens en hiver » se lit ainsi de gauche
    # à droite.
    if tags or lieux:
        candidats = _cles_portant(tags) if tags else None
        if lieux:
            du_lieu = _cles_du_lieu(lieux)
            candidats = du_lieu if candidats is None else (candidats & du_lieu)
        if not candidats:
            return []
        if not reste:
            # Aucun autre mot : on rend les plus récentes d'abord.
            avec_date = sorted(
                candidats,
                key=lambda k: _best_time(k, STORE.data.get(k) or {}) or '',
                reverse=True)
            return [(k, 1.0) for k in avec_date[:limite]]
        with SEMANTIC_LOCK:
            q = sem.encoder_textes([reste])[0]
        return vs.search(sem.KIND, q, limite=limite, restreindre=candidats)

    with SEMANTIC_LOCK:            # le modèle n'est pas réentrant
        q = sem.encoder_textes([requete])[0]
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
             and not (isinstance(e, dict) and e.get('failed'))]
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


def noms_pour_saisie(genre=None, prefixe=""):
    """Source d'autocomplétion : personnes ET animaux, avec leur volume.

    Les deux magasins sont séparés ; les chercher ensemble évite de créer un
    « Luna » animal alors qu'une personne du même nom existe déjà.
    """
    from collections import Counter
    p = _sans_accents(prefixe)
    out = []
    compte = Counter()
    for k, e in list(STORE.data.items()):
        for kw in ((e.get('kw_fr') or []) + (e.get('kw_en') or [])):
            s = str(kw)
            if s.startswith('personne:') or s.startswith('animal:'):
                compte[s] += 1
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
                        "n": compte.get(f"{genre_i}:{nom}", 0)})
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
MAINT_LOOP_STATE = {"dernier_scan": 0.0, "derniere_erreur": "", "erreur_at": 0.0}
# Vérification de la sauvegarde (audit A, « assurance-vie ») : résultat de la
# dernière restauration à blanc du snapshot NAS. Voir backup_verify().
BACKUP_VERIFY_STATE = {"at": 0.0, "ok": None, "integrity": "", "detail": "",
                       "confirmes": None, "exclusions": None,
                       "jugements_exportes": 0.0}


def maintenance_loop():
    """ExifTool + scan initial, puis re-scan toutes les 5 minutes."""
    global EXIFTOOL
    EXIFTOOL = ensure_exiftool()
    # purge des entrées de dossiers cachés (.thumbs, @eaDir…) déjà indexées
    bad = [k for k in list(STORE.data) if _is_hidden_path(_resolve_key(k))]
    if bad:
        n = STORE.remove_many(bad)
        print(f"  🧹 {n} entrée(s) de dossiers cachés retirée(s) de l'index")
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
    first = True
    cycle = 0
    while True:
        # try/except (audit O5) : la première exception non prévue tuait la
        # boucle SILENCIEUSEMENT — plus de scan NI de backup jusqu'au
        # redémarrage. On journalise, on affiche dans /reglages, on continue.
        try:
            # scan approfondi ~1x/heure : détecte aussi les fichiers modifiés
            deep = (cycle % 12 == 6)
            scan_uploads(first, deep)
            retro_write_metadata()
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
@media(max-width:560px){
  .appnav{gap:2px;padding:8px 8px;}
  .appnav .brand span.t{display:none;}
  .appnav a.tab{padding:7px 10px;font-size:13px;}
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
  <a class="tab" data-p="/reglages" href="/reglages">&#9881;&#65039; R&eacute;glages</a>
</nav>
<div class="netbusy" role="status" aria-live="polite" aria-hidden="true">
  <span class="netbusy__s" aria-hidden="true"></span><span>Traitement en cours&hellip;</span>
</div>
<script>(function(){var p=location.pathname;
  // Fusion « Sujets » (ROADMAP #4) : /people et /pets sont des vues
  // specialisees de Sujets — l'onglet Sujets reste allume quand on y est.
  if(p.indexOf('/people')===0 || p.indexOf('/pets')===0) p='/sujets';
  document.querySelectorAll('.appnav a.tab').forEach(function(a){
    var d=a.getAttribute('data-p');
    if(p===d || (d!=='/'&&p.indexOf(d)===0)) a.classList.add('active');
  });})();</script>
<script>(function(){
  // Indicateur d'activite reseau : enrobe window.fetch pour compter les requetes
  // en vol (tous les appels de l'appli passent par fetch, y compris post()). Un
  // delai de 250 ms evite un clignotement sur les requetes instantanees (ex.
  // sondages de statut) ; seul un vrai temps d'attente affiche le sablier. Les
  // vignettes se chargent via <img>, pas fetch -> elles ne le declenchent pas.
  var pending=0, timer=null;
  function el(){ return document.querySelector('.netbusy'); }
  function show(){ var b=el(); if(b){ b.classList.add('on'); b.setAttribute('aria-hidden','false'); } }
  function hide(){ var b=el(); if(b){ b.classList.remove('on'); b.setAttribute('aria-hidden','true'); } }
  if(!window.fetch) return;
  var orig=window.fetch;
  window.fetch=function(){
    pending++;
    if(pending===1){ clearTimeout(timer); timer=setTimeout(show, 250); }
    function done(){ pending--; if(pending<=0){ pending=0; clearTimeout(timer); hide(); } }
    return orig.apply(this, arguments).then(
      function(r){ done(); return r; },
      function(e){ done(); throw e; });
  };
})();</script>"""


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


HTML_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Envoyer des photos v10</title>
<style>
  /* Etape A tokenisation « chambre noire » : couleurs/police en dur -> tokens.
     Bouton d'envoi = papier (principal neutre) ; barre de progression =
     veilleuse (travail en cours) ; etats ok/err = fixateur/encre.
     Passe DESIGN (11/08) : valeurs hors echelle calees sur les tokens, memes
     mappings que les autres pages (0.9/1rem -> --t-md, 1.1rem -> --t-lg,
     1.6rem -> --t-xl, radius 8-14px -> --r-md ou --r-pill (piste de
     progression), espacements -> echelle 4px). outline:none RETIRE (plancher
     base.css). Radius 20px des grandes cartes d'envoi et tailles d'icones
     (2/3rem) conserves : signature de la page, hors gamme des tokens. */
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: var(--f-texte);
    background: var(--salle);
    color: var(--texte);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--e-6) var(--e-4) 40px;
  }
  h1 { font-size: var(--t-xl); margin-bottom: var(--e-2); text-align: center; }
  .subtitle { color: var(--graphite); font-size: var(--t-md); margin-bottom: var(--e-8); text-align: center; }

  .pick-btn {
    display: block;
    width: 100%;
    max-width: 480px;
    padding: 40px var(--e-6);
    background: var(--salle-3);
    border: 2px dashed var(--graphite);
    border-radius: 20px;
    text-align: center;
    cursor: pointer;
    color: var(--texte);
    font-size: var(--t-md);
  }
  .pick-btn:active { background: var(--salle-2); }
  .pick-btn--dossier { margin-top: var(--e-3); padding: var(--e-6) var(--e-6); }
  .pick-icon { font-size: 3rem; margin-bottom: var(--e-3); }
  .pick-btn--dossier .pick-icon { font-size: 2rem; margin-bottom: var(--e-2); }
  .pick-label { font-size: var(--t-lg); font-weight: 600; margin-bottom: var(--e-2); }
  .pick-hint { color: var(--graphite); font-size: var(--t-sm); }

  .summary { width: 100%; max-width: 480px; margin-top: var(--e-4); font-size: var(--t-md);
             color: var(--graphite); font-variant-numeric: tabular-nums; }
  .summary b { color: var(--texte); }

  /* Plancher d'accessibilite : focus visible + mouvement reduit. */
  .pick-btn:focus-visible, .btn:focus-visible, .gallery-link:focus-visible,
  .search-row input:focus-visible, .search-row button:focus-visible {
    outline: 2px solid var(--veilleuse); outline-offset: 2px;
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { transition-duration: 0.01ms !important;
                             animation-duration: 0.01ms !important; }
  }

  .btn {
    display: block;
    width: 100%;
    max-width: 480px;
    margin-top: var(--e-4);
    padding: var(--e-4);
    background: var(--papier);
    color: var(--texte-papier);
    border: none;
    border-radius: var(--r-md);
    font-size: var(--t-lg);
    font-weight: 600;
    cursor: pointer;
  }
  .btn:active { opacity: 0.85; }
  .btn:disabled { background: var(--salle-3); color: var(--graphite); cursor: default; }

  #status { width: 100%; max-width: 480px; margin-top: var(--e-6); font-size: var(--t-md); }
  .file-item {
    display: flex; align-items: center; gap: var(--e-3);
    padding: var(--e-3) var(--e-4); background: var(--salle-3); border-radius: var(--r-md); margin-bottom: var(--e-2);
  }
  .file-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--t-md); }
  .file-item .state { flex-shrink: 0; font-size: var(--t-sm); }
  .state.ok { color: var(--fixateur); }
  .state.err { color: var(--encre); }
  .state.pending { color: var(--graphite); }

  .progress-bar-wrap { width: 100%; max-width: 480px; margin-top: var(--e-4); background: var(--salle-3); border-radius: var(--r-pill); height: 8px; display: none; }
  .progress-bar { height: 100%; border-radius: var(--r-pill); background: var(--veilleuse); width: 0%; transition: width 0.2s; }

  .gallery-link { margin-top: var(--e-6); color: var(--texte); text-decoration: none; font-size: var(--t-md); }

  .search-row { display: flex; gap: var(--e-2); width: 100%; max-width: 480px; margin-top: var(--e-8); }
  .search-row input { flex: 1; padding: var(--e-3) var(--e-4); border-radius: var(--r-md); border: var(--trait);
                      background: var(--salle-3); color: var(--texte); font-size: var(--t-md); }
  .search-row input:focus { border-color: var(--veilleuse); }
  .search-row button { padding: var(--e-3) var(--e-4); border-radius: var(--r-md); border: none;
                       background: var(--salle-3); color: var(--texte); font-size: var(--t-md); cursor: pointer; }
</style>
</head>
<body>
<!--APPNAV-->

<h1>Envoyer des photos</h1>
<p style="color:var(--graphite);font-size:var(--t-xs);margin-bottom:var(--e-1)">v10 &middot; tagging IA</p>
<p class="subtitle">Meme reseau WiFi &middot; Aucune inscription requise</p>

<input type="file" id="fileInput" multiple accept="image/*,video/*" style="display:none">
<input type="file" id="dirInput" webkitdirectory multiple style="display:none">

<label for="fileInput" class="pick-btn" id="pickBtn">
  <div class="pick-icon">&#128247;</div>
  <div class="pick-label">Choisir des photos</div>
  <div class="pick-hint">Une ou plusieurs images &middot; videos</div>
</label>

<label for="dirInput" class="pick-btn pick-btn--dossier" id="pickDirBtn">
  <div class="pick-icon">&#128193;</div>
  <div class="pick-label">Choisir un dossier</div>
  <div class="pick-hint">Tout un album, sous-dossiers compris</div>
</label>

<div class="progress-bar-wrap" id="progressWrap">
  <div class="progress-bar" id="progressBar"></div>
</div>

<div id="summary" class="summary" style="display:none"></div>

<button class="btn" id="uploadBtn" disabled>Envoyer</button>

<div id="status"></div>

<div class="search-row">
  <input type="search" id="searchInput" placeholder="Rechercher (noms, lieux, sens&hellip;)"
         aria-label="Rechercher des photos (noms, lieux, sens de l'image)">
  <button id="searchBtn">&#128269;</button>
</div>

<div>
  <a class="gallery-link" href="/files">Voir toute la galerie</a>
  &nbsp;&middot;&nbsp;
  <a class="gallery-link" href="/browse">Explorer les dossiers</a>
</div>

<script>
(function() {
  var input = document.getElementById('fileInput');
  var dirInput = document.getElementById('dirInput');
  var btn = document.getElementById('uploadBtn');
  var list = document.getElementById('status');
  var summary = document.getElementById('summary');
  var progressWrap = document.getElementById('progressWrap');
  var progressBar = document.getElementById('progressBar');
  var files = [];
  var MAX_ROWS = 60;    // au-dela, on n'affiche qu'un resume (un album peut etre gros)

  function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function relOf(f) { return f.webkitRelativePath || f.name; }

  function onPick(picked) {
    files = Array.prototype.slice.call(picked);
    if (files.length <= MAX_ROWS) {
      list.innerHTML = files.map(function(f, i) {
        return '<div class="file-item"><span class="name">' + esc(relOf(f)) + '</span>'
             + '<span class="state pending" id="s' + i + '">En attente</span></div>';
      }).join('');
    } else {
      list.innerHTML = '';
    }
    summary.style.display = files.length ? 'block' : 'none';
    summary.innerHTML = '<b>' + files.length + '</b> fichier(s) prets a envoyer.';
    btn.disabled = files.length === 0;
    btn.textContent = 'Envoyer';
  }

  input.onchange = function() { onPick(input.files); };
  dirInput.onchange = function() { onPick(dirInput.files); };

  function setState(i, txt, cls) {
    var el = document.getElementById('s' + i);
    if (el) { el.textContent = txt; el.className = 'state ' + cls; }
  }

  btn.onclick = function() {
    if (!files.length) return;
    btn.disabled = true;
    progressWrap.style.display = 'block';
    var done = 0, ok = 0, skip = 0, err = 0;

    function tick(i, txt, cls) {
      done++;
      progressBar.style.width = (done / files.length * 100) + '%';
      setState(i, txt, cls);
      summary.innerHTML = 'Envoyees <b>' + ok + '</b> &middot; ignorees <b>' + skip
        + '</b> &middot; erreurs <b>' + err + '</b> &middot; ' + done + '/' + files.length;
    }

    function next(i) {
      if (i >= files.length) {
        btn.textContent = 'Envoyer d\\'autres ?';
        btn.disabled = false;
        btn.onclick = function() { location.reload(); };
        return;
      }
      setState(i, 'Envoi...', 'pending');
      var fd = new FormData();
      fd.append('file', files[i], files[i].name);
      fd.append('relpath', relOf(files[i]));
      fetch('/upload', { method: 'POST', body: fd })
        .then(function(r) { return r.text().then(function(t) {
          return { ok: r.ok, status: r.status, body: t }; }); })
        .then(function(res) {
          if (res.ok && res.body === 'SKIP') { skip++; tick(i, 'Deja present', 'ok'); }
          else if (res.ok) { ok++; tick(i, 'OK', 'ok'); }
          else { err++; tick(i, 'Erreur ' + res.status, 'err'); }
          next(i + 1);
        })
        .catch(function(e) { err++; tick(i, 'Echec reseau', 'err'); next(i + 1); });
    }
    next(0);
  };

  var si = document.getElementById('searchInput');
  function goSearch() {
    var q = si.value.trim();
    location.href = q ? '/files?q=' + encodeURIComponent(q) : '/files';
  }
  document.getElementById('searchBtn').onclick = goSearch;
  si.addEventListener('keydown', function(e) { if (e.key === 'Enter') goSearch(); });
})();
</script>
</body>
</html>
"""

GALLERY_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Galerie photos</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
/* Etape A tokenisation « chambre noire ». Filtres actifs (personne, tag, tri,
   geo) = fixateur (selection humaine) ; bandeau IA + barre de progression =
   veilleuse (en cours) ; « Tout effacer » = encre ; boutons primaires = papier ;
   focus = veilleuse. Grille repeat(5) laissee telle quelle (planche contact
   auto-fill = redesign etape B, point 11). Structure/espacements inchanges.
   Etape B (10/08) : les espacements/rayons/tailles qui EGALENT deja un token
   pointent vers lui (12px->--e-3, 8px->--e-2, 16px->--e-4, 0.75rem->--t-xs,
   0.85rem->--t-sm, 999px->--r-pill) — rendu identique, valeurs calculees
   prouvees. .pchip et .chip fusionnes en un seul jeu (fin de la divergence
   connue : ils etaient deux forks identiques).
   Passe DESIGN (11/08) : valeurs hors echelle calees sur les tokens, memes
   mappings que PEOPLE/PETS/MAP (0.8-0.82rem/13px -> --t-sm, 0.65-0.7rem ->
   --t-xs, 0.9rem -> --t-md, 1.1rem -> --t-lg, radius 8/10px -> --r-md,
   gaps/paddings -> echelle 4px : 5px -> --e-1, 6/7px -> --e-2, 10px -> --e-3,
   14/18px -> --e-4). Divergences tranchees : outline:none de #q RETIRE (le
   plancher base.css fournit l'anneau focus) ; .pchip/.chip alignes sur le chip
   canonique (min-height 32px, comme .mchip). Tailles fixes (180px, 300px,
   positions) non tokenisees. */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--f-texte);
        background: var(--salle); color: var(--texte); min-height: 100vh; }
/* -- filtres personnes + geo -- */
.selbar { display: flex; align-items: center; gap: var(--e-2); padding: var(--e-2) var(--e-4);
          background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; }
.selbar .lbl { color: var(--graphite); font-size: var(--t-xs); margin-right: 2px; }
/* .pchip + .chip : jeu unique, selecteurs groupes (rendu inchange). */
.pchip, .chip { min-height: 32px; padding: var(--e-1) var(--e-3); border-radius: var(--r-pill); border: var(--trait);
         background: var(--salle-3); color: var(--graphite); font-size: var(--t-sm); cursor: pointer;
         user-select: none; }
.pchip.on, .chip.on { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.pchip .n, .chip .n { color: var(--graphite); font-size: var(--t-xs); margin-left: var(--e-1); font-family: var(--f-donnees); }
.pchip.on .n, .chip.on .n { color: #fff; }
.geobtn { padding: var(--e-1) var(--e-3); border-radius: var(--r-md); border: var(--trait);
          background: var(--salle-3); color: var(--texte); font-size: var(--t-sm); cursor: pointer; }
.geobtn.on { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
#geopanel { display: none; padding: var(--e-3) var(--e-4); background: var(--salle);
            border-bottom: var(--trait); }
#geopanel.open { display: block; }
#geomap { height: 300px; border-radius: var(--r-md); overflow: hidden; background: var(--salle-3); }
.georow { display: flex; align-items: center; gap: var(--e-3); margin-top: var(--e-2); flex-wrap: wrap; }
.georow input[type=range] { flex: 1; min-width: 140px; accent-color: var(--fixateur); }
.georow .cnt { color: var(--graphite); font-size: var(--t-sm); font-family: var(--f-donnees); }
.georow button { padding: var(--e-2) var(--e-3); border-radius: var(--r-md); border: var(--trait);
                 background: var(--salle-3); color: var(--texte); font-size: var(--t-sm); cursor: pointer; }
.georow button.prim { background: var(--papier); border-color: var(--papier); color: var(--texte-papier); }

/* -- toolbar -- */
.bar { display: flex; align-items: center; gap: var(--e-3); padding: var(--e-4);
        background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; }
.back { color: var(--texte); text-decoration: none; font-size: var(--t-md); margin-right: auto; }
.btn-group { display: flex; gap: var(--e-2); }
.tb { padding: var(--e-2) var(--e-4); border: var(--trait); border-radius: var(--r-md);
       background: var(--salle-3); color: var(--texte); font-size: var(--t-sm); cursor: pointer; }
.tb.active { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.tb.demo { background: var(--salle-3); border-color: var(--graphite); }
.tb.demo.on { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.count { color: var(--graphite); font-size: var(--t-sm); font-family: var(--f-donnees); }
#q { padding: var(--e-2) var(--e-3); border-radius: var(--r-md); border: var(--trait);
     background: var(--salle-3); color: var(--texte); font-size: var(--t-sm); width: 180px; }
#q:focus { border-color: var(--veilleuse); }

/* ── bandeau IA ── */
#pending { display: none; padding: var(--e-2) var(--e-4); background: var(--salle-2); color: var(--veilleuse);
           font-size: var(--t-sm); border-bottom: 1px solid var(--veilleuse-d); }
#pending a { color: var(--veilleuse); }

/* -- barre de tags -- */
.tagbar { display: flex; align-items: center; gap: var(--e-2); padding: var(--e-3) var(--e-4);
          background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; }
.chip.mode { background: var(--salle-3); border-color: var(--graphite); color: var(--texte); }
.chip.clear { background: transparent; border-color: var(--encre); color: var(--encre); display: none; }
.tagbar-label { color: var(--graphite); font-size: var(--t-xs); margin-right: var(--e-1); }
.tagchips { display: flex; flex-wrap: wrap; gap: var(--e-2); width: 100%; margin-top: var(--e-2); }
.tagchips.hidden { display: none; }

/* -- barre de dossiers -- */
.folders { display: flex; flex-wrap: wrap; gap: var(--e-2); padding: var(--e-3) var(--e-4);
           background: var(--salle-2); border-bottom: var(--trait); }
.fchip { padding: var(--e-2) var(--e-3); border-radius: var(--r-md); background: var(--salle-3); color: var(--texte);
         text-decoration: none; font-size: var(--t-sm); border: var(--trait); }
.fchip.up { background: var(--salle-3); border-color: var(--graphite); color: var(--graphite); }

/* ── grid ── */
/* Etape B : planche contact. Densite par auto-fill + clamp (jamais un nombre
   de colonnes en dur), gouttiere serree facon film. content-visibility sur les
   cellules pour tenir les grandes planches sans virtual scroll. */
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(clamp(96px, 18vw, 168px), 1fr));
        gap: var(--e-1); padding: var(--e-2); background: var(--salle); }

.cell { background: var(--salle-3); border-radius: var(--r-sm); overflow: hidden; cursor: pointer;
        content-visibility: auto; contain-intrinsic-size: auto 210px; }
.cell .ph { position: relative; aspect-ratio: 1; overflow: hidden; background: var(--salle-3); }
.cell img { width: 100%; height: 100%; object-fit: cover; display: block;
             opacity: 0; transition: opacity 0.3s, transform 0.2s; }
.cell img.loaded { opacity: 1; }
.cell:hover img { transform: scale(1.05); }
.caption { padding: var(--e-1) var(--e-2) var(--e-2); font-size: var(--t-xs); line-height: 1.25; color: var(--graphite);
           min-height: 2.3em; display: -webkit-box; -webkit-line-clamp: 2;
           -webkit-box-orient: vertical; overflow: hidden; }
.caption.empty { color: var(--graphite); font-style: italic; }

/* -- lightbox -- */
#lb { display: none; position: fixed; inset: 0; background: #000;
       z-index: 100; flex-direction: column; }
#lb.open { display: flex; }
#lb-img { flex: 1; object-fit: contain; width: 100%; min-height: 0; }
#lb-meta { background: var(--salle-2); padding: var(--e-3) var(--e-4) 0; }
#lb-tags { font-size: var(--t-md); color: var(--texte); line-height: 1.4; }
#lb-tags.none { color: var(--graphite); font-style: italic; }
#lb-desc { font-size: var(--t-sm); color: var(--graphite); margin-top: var(--e-1); font-style: italic; }
#lb-bar { background: var(--salle-2); padding: var(--e-3) var(--e-4); display: flex;
           align-items: center; gap: var(--e-3); flex-shrink: 0; }
#lb-name { flex: 1; font-size: var(--t-sm); color: var(--graphite);
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#lb-close { color: #fff; background: var(--salle-3); border: none; border-radius: var(--r-md);
             padding: var(--e-2) var(--e-4); cursor: pointer; font-size: var(--t-md); }
/* -- semblables : navigation, pas une action -- neutre, cible 44px -- */
#lb-sim { min-height: var(--touch); padding: 0 var(--e-4); border-radius: var(--r-md);
          background: var(--salle-3); border: var(--trait); color: var(--texte);
          cursor: pointer; font-size: var(--t-md); }
#lb-sim:hover { background: var(--salle-2); }
#lb-prev, #lb-next { color: #fff; background: var(--salle-3); border: none;
                      border-radius: var(--r-md); padding: var(--e-2) var(--e-3); cursor: pointer; font-size: var(--t-lg); }

/* -- slideshow -- */
#ss { display: none; position: fixed; inset: 0; background: #000;
       z-index: 200; flex-direction: column; }
#ss.open { display: flex; }
#ss-img { flex: 1; object-fit: contain; width: 100%; min-height: 0; }
#ss-footer { background: var(--salle); padding: var(--e-3) var(--e-4); flex-shrink: 0; }
#ss-name { font-size: var(--t-sm); color: var(--graphite); text-align: center; margin-bottom: var(--e-2);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
#ss-folderwrap { text-align: center; margin-bottom: var(--e-2); }
#ss-folder { display: inline-block; color: var(--texte); background: var(--salle-3);
            border: var(--trait); border-radius: var(--r-md); padding: var(--e-1) var(--e-3);
            font-size: var(--t-sm); text-decoration: none; max-width: 80vw;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#ss-folder:hover { background: var(--salle-2); }
#ss-folder.hidden { display: none; }
#ss-track { height: 4px; background: var(--salle-3); border-radius: 2px; overflow: hidden; }
#ss-fill { height: 100%; background: var(--veilleuse); width: 0%; transition: width linear; }
#ss-stop { position: absolute; top: 14px; right: 14px; background: rgba(0,0,0,0.6);
            color: #fff; border: var(--trait); border-radius: var(--r-md);
            padding: var(--e-2) var(--e-4); cursor: pointer; font-size: var(--t-sm); z-index: 201; }

/* -- barre de filtre par motif (point 21) : regroupe la vue par regle. Actif =
   fixateur (choix humain), coherent avec les chips personnes/tags. -- */
.motifbar { display: none; align-items: center; gap: var(--e-2); padding: var(--e-2) var(--e-4);
            background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; }
.motifbar.show { display: flex; }
.motifbar .lbl { color: var(--graphite); font-size: var(--t-xs); margin-right: 2px; }
.mchip { min-height: 32px; padding: var(--e-1) var(--e-3); border-radius: var(--r-pill); border: var(--trait);
         background: var(--salle-3); color: var(--graphite); font-size: var(--t-sm);
         cursor: pointer; text-decoration: none; }
.mchip.on { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.mchip .n { font-family: var(--f-donnees); font-size: var(--t-xs); margin-left: var(--e-1); opacity: 0.75; }
.mchip.on .n { opacity: 1; }

/* -- bouton supprimer dans la visionneuse : destructif = encre, cible 44px -- */
#lb-del { min-height: var(--touch); padding: 0 var(--e-4); border-radius: var(--r-md);
          background: transparent; border: 1px solid var(--encre); color: var(--encre);
          cursor: pointer; font-size: var(--t-md); }
#lb-del:hover { background: var(--encre); color: #fff; }

/* -- toast d'annulation 10s (meme registre que /browse et /people) -- */
.gtoast { position: fixed; left: 50%; bottom: var(--e-4); transform: translateX(-50%);
          z-index: 300; display: none; gap: var(--e-3); align-items: center;
          max-width: 90vw; background: var(--salle-3); border: var(--trait);
          border-radius: var(--r-pill); padding: var(--e-3) var(--e-3) var(--e-3) var(--e-4); font-size: var(--t-sm);
          color: var(--texte); box-shadow: 0 8px 24px #0008; }
.gtoast.show { display: flex; }
.gtoast .b { min-height: 36px; padding: 0 var(--e-4); border-radius: var(--r-pill); border: var(--trait);
             background: var(--salle-2); color: var(--texte); cursor: pointer; }
</style>
</head>
<body>
<!--APPNAV-->

<div class="bar">
  <input type="search" id="q" placeholder="Recherche tags&hellip;">
  <button class="tb" id="btn-ia" aria-pressed="false"
          title="Recherche par le sens : d&eacute;cris la photo en fran&ccedil;ais">IA</button>
  <span class="count" id="cnt"></span>
  <div class="btn-group">
    <button class="tb active" id="btn-date">Date</button>
    <button class="tb" id="btn-name">Nom A-Z</button>
  </div>
  <div class="btn-group">
    <button class="tb demo" id="btn-seq">&#9654; Demo</button>
    <button class="tb demo" id="btn-rnd">&#9654; Aleatoire</button>
    <button class="tb demo" id="btn-asc" title="Chaque photo partage un tag avec la precedente">&#9654; Association</button>
  </div>
</div>

<div id="pending"></div>
__FOLDERS__
<div class="tagbar" id="tagbar"></div>
<div class="motifbar" id="motifbar"></div>

<div class="selbar" id="selbar">
  <span class="lbl">Personnes :</span>
  <span id="personchips"></span>
  <button class="geobtn" id="geotoggle">&#128506; Géo</button>
  <span class="lbl" id="selinfo"></span>
</div>
<div id="geopanel">
  <div id="geomap"></div>
  <div class="georow">
    <span class="lbl">Rayon :</span>
    <input type="range" id="georadius" min="1" max="500" value="25">
    <span class="cnt" id="georadlbl">25 km</span>
    <span class="cnt" id="geocount"></span>
    <button class="prim" id="geoapply">Appliquer</button>
    <button id="geoclear">Effacer</button>
  </div>
  <div class="lbl" style="margin-top:var(--e-2)">Clique un point sur la carte pour définir le centre, règle le rayon, puis « Appliquer ».</div>
</div>

<div class="grid" id="grid"></div>

<!-- lightbox -->
<div id="lb">
  <img id="lb-img" src="" alt="">
  <div id="lb-meta">
    <div id="lb-tags"></div>
    <div id="lb-desc"></div>
  </div>
  <div id="lb-bar">
    <button id="lb-prev">&#8592;</button>
    <span id="lb-name"></span>
    <button id="lb-next">&#8594;</button>
    <button id="lb-sim" aria-label="Voir les photos semblables">&#128269; Semblables</button>
    <button id="lb-del" aria-label="Supprimer cette photo">&#128465;&#65039; Supprimer</button>
    <button id="lb-close">Fermer</button>
  </div>
</div>

<!-- toast d'annulation (suppression reversible, 10 s) -->
<div class="gtoast" id="gtoast" role="status" aria-live="polite"></div>

<!-- slideshow -->
<div id="ss">
  <button id="ss-stop">&#9632; Arreter</button>
  <img id="ss-img" src="" alt="">
  <div id="ss-footer">
    <div id="ss-name"></div>
    <div id="ss-folderwrap"><a id="ss-folder" class="hidden" href="#" title="Ouvrir le dossier d'origine"></a></div>
    <div id="ss-track"><div id="ss-fill"></div></div>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
(function() {
  var FILES = __FILE_JSON__;
  var INITIAL_TAGGED = __TAGGED__;
  var REC = __REC__;
  var HASSUBS = __HASSUBS__;
  var DIRQ = __DIRQ__;
  var SEARCHQ = __SEARCHQ__;   // requete si /files?q= (page de resultats globale), sinon ''
  var MOTIFS = __MOTIFS__;
  var sorted = FILES.slice();
  var visible = FILES.slice();
  var currentSort = '';     // defini au premier appel de sortBy
  var sortAsc = true;       // chronologique par defaut : du plus ancien au plus recent
  var observer;
  var lbIdx = 0;
  var TAGDATA = __TAGDATA__;
  var selTags = (TAGDATA.sel || []).slice();
  var mode = TAGDATA.mode === 'or' ? 'or' : 'and';
  var selPersons = [];      // tags "personne:Nom" sélectionnés (filtre client, ET)
  var geoFilter = null;     // {lat, lon, km} ou null
  var qInput = document.getElementById('q');
  qInput.value = new URLSearchParams(location.search).get('q') || '';
  var qTimer = null;
  qInput.addEventListener('input', function() {
    if (qTimer) clearTimeout(qTimer);
    qTimer = setTimeout(modeIA ? rechercheIA : applyFilter, modeIA ? 450 : 250);
  });

  // ── recherche semantique (SigLIP 2) ──
  // Le filtre habituel compare des mots-cles ; ce mode-ci compare le SENS.
  // « chat endormi sur le canape » fonctionne sans qu'aucun de ces mots
  // n'apparaisse dans les tags.
  var modeIA = false, iaResultats = null, iaJeton = 0, iaNoms = '';
  var btnIA = document.getElementById('btn-ia');
  btnIA.addEventListener('click', function() {
    modeIA = !modeIA;
    btnIA.className = 'tb' + (modeIA ? ' active' : '');
    btnIA.setAttribute('aria-pressed', modeIA ? 'true' : 'false');
    qInput.placeholder = modeIA ? 'Décris la photo…' : 'Recherche tags…';
    iaResultats = null;
    if (modeIA && qInput.value.trim()) rechercheIA(); else applyFilter();
    if (modeIA) qInput.focus();
  });

  function rechercheIA() {
    var t = qInput.value.trim();
    if (!t) { iaResultats = null; applyFilter(); return; }
    var jeton = ++iaJeton;                 // ignore les reponses hors delai
    var cnt = document.getElementById('cnt');
    cnt.textContent = 'recherche…';
    fetch('/api/search?q=' + encodeURIComponent(t) + '&n=200')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (jeton !== iaJeton) return;
        if (d.error) { cnt.textContent = d.error; iaResultats = null; return; }
        iaResultats = {};
        (d.results || []).forEach(function(x, i) { iaResultats[x.key] = i; });
        // Rend visible ce que la requete a compris : un nom reconnu est
        // traite comme un filtre exact, le reste comme du sens.
        iaNoms = (d.noms && d.noms.length)
          ? d.noms.join(' + ') + (d.reste ? ' · ' + d.reste : '') : '';
        applyFilter();
      })
      .catch(function() {
        if (jeton === iaJeton) cnt.textContent = 'recherche indisponible';
      });
  }

  function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  // ── sort (reversible) ──
  // « Date » = date de PRISE (taken, repli mtime), du plus ancien au plus recent
  // par defaut ; un reclic sur le meme bouton inverse le sens. « Nom » de meme
  // (A-Z par defaut, reclic = Z-A). Le diaporama « Demo » suit ensuite cet ordre.
  function photoTime(f){ return f.taken || f.mtime || 0; }
  function updateSortButtons() {
    var d = document.getElementById('btn-date'), n = document.getElementById('btn-name');
    d.className = 'tb' + (currentSort==='date' ? ' active' : '');
    n.className = 'tb' + (currentSort==='name' ? ' active' : '');
    d.textContent = 'Date ' + (currentSort==='date' ? (sortAsc ? '↑' : '↓') : '');
    n.textContent = currentSort==='name' ? ('Nom ' + (sortAsc ? 'A→Z' : 'Z→A')) : 'Nom A-Z';
    d.title = currentSort==='date'
      ? 'Chronologique — ' + (sortAsc ? 'du plus ancien au plus recent' : 'du plus recent au plus ancien') + ' (reclic pour inverser)'
      : 'Trier par date de prise';
    n.title = 'Trier par nom' + (currentSort==='name' ? ' (reclic pour inverser)' : '');
  }
  function sortBy(m) {
    if (m === currentSort) sortAsc = !sortAsc;     // reclic = inverse le sens
    else { currentSort = m; sortAsc = true; }       // nouveau tri = sens par defaut
    updateSortButtons();
    var s = FILES.slice();
    if (m === 'date') s.sort(function(a,b){ return photoTime(a) - photoTime(b); });
    else s.sort(function(a,b){ return a.name.localeCompare(b.name); });
    if (!sortAsc) s.reverse();
    sorted = s;
    applyFilter();
  }

  // ── tags (barre repliable, tags du dossier + sous-dossiers via l'index) ──
  function tagNavUrl(tags, m) {
    var p = ['dir=' + encodeURIComponent(DIRQ || '0')];
    if (tags.length) {
      p.push('tags=' + encodeURIComponent(tags.join(',')));
      p.push('tmode=' + m);
    }
    return '/files?' + p.join('&');
  }

  function buildTagbar() {
    var tagsArr;
    if (TAGDATA.counts && TAGDATA.counts.length) {
      tagsArr = TAGDATA.counts;           // index serveur : récursif
    } else {
      var counts = {};
      FILES.forEach(function(f) {
        (f.kw || []).forEach(function(t) { counts[t] = (counts[t] || 0) + 1; });
      });
      tagsArr = Object.keys(counts)
        .sort(function(a, b) { return counts[b] - counts[a]; })
        .slice(0, 40)
        .map(function(t) { return [t, counts[t]]; });
    }
    var bar = document.getElementById('tagbar');
    bar.innerHTML = '';
    if (!tagsArr.length) {
      bar.innerHTML = '<span class="tagbar-label">Aucun mot-cl&eacute; pour le moment &mdash; le tagging IA les ajoute automatiquement.</span>';
      return;
    }
    // navigation serveur quand la page ne contient pas toutes les photos du sous-arbre
    var srvNav = selTags.length > 0 || (HASSUBS && !REC);

    var collapsed = true;
    try { collapsed = localStorage.getItem('tagbarOpen') !== '1'; } catch (e) {}
    if (selTags.length) collapsed = false;

    var toggle = document.createElement('span');
    toggle.className = 'chip mode';
    var wrap = document.createElement('div');
    wrap.className = 'tagchips' + (collapsed ? ' hidden' : '');

    function updToggle() {
      toggle.textContent = (collapsed ? '▸' : '▾') + ' Filtres'
        + (selTags.length ? ' — ' + selTags.length + ' actif' + (selTags.length > 1 ? 's' : '') : '')
        + ' (' + tagsArr.length + ' tags)';
    }
    toggle.onclick = function() {
      collapsed = !collapsed;
      wrap.className = 'tagchips' + (collapsed ? ' hidden' : '');
      try { localStorage.setItem('tagbarOpen', collapsed ? '0' : '1'); } catch (e) {}
      updToggle();
    };
    bar.appendChild(toggle);

    var modeBtn = document.createElement('span');
    modeBtn.className = 'chip mode';
    modeBtn.id = 'modeBtn';
    modeBtn.textContent = (mode === 'and') ? 'ET' : 'OU';
    modeBtn.title = 'Combiner les mots-cles en ET ou en OU';
    modeBtn.onclick = function() {
      mode = (mode === 'and') ? 'or' : 'and';
      modeBtn.textContent = (mode === 'and') ? 'ET' : 'OU';
      if (srvNav && selTags.length) { location.href = tagNavUrl(selTags, mode); return; }
      applyFilter();
    };
    wrap.appendChild(modeBtn);

    tagsArr.forEach(function(tn) {
      var t = tn[0], n = tn[1];
      var c = document.createElement('span');
      var on = selTags.indexOf(t) >= 0;
      c.className = 'chip' + (on ? ' on' : '');
      c.innerHTML = esc(t) + '<span class="n">' + n + '</span>';
      c.onclick = function() {
        var i = selTags.indexOf(t);
        if (srvNav) {
          var ns = selTags.slice();
          if (i >= 0) ns.splice(ns.indexOf(t), 1); else ns.push(t);
          location.href = tagNavUrl(ns, mode);
          return;
        }
        if (i >= 0) selTags.splice(i, 1); else selTags.push(t);
        c.className = 'chip' + (i < 0 ? ' on' : '');
        document.getElementById('clearBtn').style.display = selTags.length ? 'inline-block' : 'none';
        updToggle();
        applyFilter();
      };
      wrap.appendChild(c);
    });

    var clr = document.createElement('span');
    clr.className = 'chip clear';
    clr.id = 'clearBtn';
    clr.textContent = 'Tout effacer';
    clr.style.display = selTags.length ? 'inline-block' : 'none';
    clr.onclick = function() {
      if (srvNav) { location.href = tagNavUrl([], mode); return; }
      selTags = [];
      var chips = wrap.querySelectorAll('.chip.on');
      for (var i = 0; i < chips.length; i++) chips[i].className = 'chip';
      clr.style.display = 'none';
      updToggle();
      applyFilter();
    };
    wrap.appendChild(clr);

    bar.appendChild(wrap);
    updToggle();
  }

  function applyFilter() {
    var words = (modeIA ? [] : qInput.value.trim().toLowerCase()
                 .split(/[\s,;]+/).filter(Boolean));
    visible = sorted.filter(function(f) {
      var kw = f.kw || [];
      // En mode IA, seules les photos rapportees par /api/search passent ;
      // les filtres chips, personnes et geo restent cumulables.
      if (modeIA && iaResultats && iaResultats[f.key] === undefined) return false;
      if (selTags.length) {
        var okChips = (mode === 'and')
          ? selTags.every(function(t) { return kw.indexOf(t) >= 0; })
          : selTags.some(function(t) { return kw.indexOf(t) >= 0; });
        if (!okChips) return false;
      }
      if (selPersons.length) {
        for (var pp = 0; pp < selPersons.length; pp++) {
          if (kw.indexOf(selPersons[pp]) < 0) return false;
        }
      }
      if (geoFilter) {
        if (!f.gps) return false;
        if (haversine(geoFilter.lat, geoFilter.lon, f.gps[0], f.gps[1]) > geoFilter.km) return false;
      }
      if (words.length) {
        var hay = kw.join(' ') + ' ' + f.name.toLowerCase() + ' ' + (f.desc || '').toLowerCase();
        for (var i = 0; i < words.length; i++) {
          if (hay.indexOf(words[i]) < 0) return false;
        }
      }
      return true;
    });
    // Le classement par pertinence prime sur le tri date/nom : c'est ce que
    // l'utilisateur attend quand il a formule une requete.
    if (modeIA && iaResultats) {
      visible.sort(function(a, b) {
        return iaResultats[a.key] - iaResultats[b.key];
      });
    }
    renderGrid();
  }

  // ── vignettes serveur (audit O1) ──
  // La grille chargeait les ORIGINAUX (2-6 Mo/case lus sur le NAS) ; /api/thumb
  // sert un JPEG 512 px (grille) ou 1600 px (diaporama) avec cache disque, et
  // REDIRIGE vers l'original quand il ne sait pas (vidéo, format exotique) —
  // aucun cas particulier ici. La visionneuse (lightbox) garde l'original.
  function thumbUrl(f, s) {
    if (!f || !f.key) return f ? f.url : '';
    return '/api/thumb?key=' + encodeURIComponent(f.key) + '&s=' + (s || 512);
  }

  // ── grid ──
  function renderGrid() {
    var grid = document.getElementById('grid');
    grid.innerHTML = '';
    if (observer) observer.disconnect();

    observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          var img = e.target.querySelector('img');
          if (img && img.dataset.src) {
            img.src = img.dataset.src;
            img.onload = function() { img.classList.add('loaded'); };
            img.onerror = function() {
              // vignette serveur KO (clé qui ne résout pas, cas rares) :
              // retenter UNE fois avec l'original avant de masquer la case.
              var fb = img.dataset.fb;
              if (fb && img.src.indexOf('/api/thumb') >= 0) {
                img.src = fb;
                return;
              }
              var c = img.closest('.cell');
              if (c) c.style.display = 'none';
            };
            delete img.dataset.src;
            observer.unobserve(e.target);
          }
        }
      });
    }, { rootMargin: '200px' });

    visible.forEach(function(f, i) {
      var cell = document.createElement('div');
      cell.className = 'cell';
      var cap = f.desc || '';
      cell.innerHTML = '<div class="ph"><img data-src="' + thumbUrl(f, 512)
                     + '" data-fb="' + esc(f.url) + '" alt="" title="' + esc(f.name) + '"></div>'
                     + '<div class="caption' + (cap ? '' : ' empty') + '">'
                     + (cap ? esc(cap) : 'pas encore analysée') + '</div>';
      cell.onclick = function() { openLb(i); };
      grid.appendChild(cell);
      observer.observe(cell);
    });

    var txt = visible.length + ' photo(s)';
    if (selTags.length) txt += ' / ' + FILES.length;
    document.getElementById('cnt').textContent =
      (modeIA && iaNoms) ? txt + ' — ' + iaNoms : txt;
  }

  // ── lightbox ──
  function openLb(i) {
    lbIdx = i;
    document.getElementById('lb').classList.add('open');
    showLb();
  }
  function showLb() {
    var f = visible[lbIdx];
    document.getElementById('lb-img').src = f.url;
    document.getElementById('lb-name').textContent = f.name + '  (' + f.size + ')';
    var t = document.getElementById('lb-tags');
    if (f.kw && f.kw.length) { t.textContent = f.kw.join(' · '); t.className = ''; }
    else { t.textContent = 'pas encore de tags'; t.className = 'none'; }
    document.getElementById('lb-desc').textContent = f.desc || '';
  }
  function lbMove(d) {
    if (!visible.length) return;
    lbIdx = (lbIdx + d + visible.length) % visible.length;
    showLb();
  }
  function closeLb() { document.getElementById('lb').classList.remove('open'); }

  document.getElementById('lb').addEventListener('click', function(e) {
    if (e.target === this) closeLb();
  });

  // « Semblables » : navigation (page /files?sim=), pas un filtre client --
  // les résultats couvrent TOUTE la photothèque, pas le dossier courant.
  document.getElementById('lb-sim').addEventListener('click', function() {
    var f = visible[lbIdx];
    if (f && f.key) location.href = '/files?sim=' + encodeURIComponent(f.key);
  });

  // 5 bandes verticales : seules les bandes des bords (20%) naviguent
  document.getElementById('lb-img').addEventListener('click', function(e) {
    var w = this.clientWidth;
    if (e.offsetX < w / 5) lbMove(-1);
    else if (e.offsetX > w * 4 / 5) lbMove(1);
  });

  // swipe gauche/droite
  var tsX = null, tsY = null;
  var lbEl = document.getElementById('lb');
  lbEl.addEventListener('touchstart', function(e) {
    if (e.touches.length === 1) {
      tsX = e.touches[0].clientX;
      tsY = e.touches[0].clientY;
    }
  }, { passive: true });
  lbEl.addEventListener('touchend', function(e) {
    if (tsX === null) return;
    var dx = e.changedTouches[0].clientX - tsX;
    var dy = e.changedTouches[0].clientY - tsY;
    tsX = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      lbMove(dx < 0 ? 1 : -1);
    }
  }, { passive: true });

  document.addEventListener('keydown', function(e) {
    if (document.getElementById('lb').classList.contains('open')) {
      if (e.key === 'ArrowLeft') lbMove(-1);
      if (e.key === 'ArrowRight') lbMove(1);
      if (e.key === 'Escape') closeLb();
    }
    if (document.getElementById('ss').classList.contains('open')) {
      if (e.key === 'ArrowLeft') { e.preventDefault(); ssMove(-1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); ssMove(1); }
      if (e.key === ' ') { e.preventDefault(); ssTogglePause(); }
      if (e.key === 'Escape') stopSlideshow();
    }
  });

  // ── slideshow (respecte le filtre actif) ──
  var ssTimer = null;
  var ssIdx = 0;
  var ssMode = 'seq';
  var ssOrder = [];
  var DURATION = 10000;

  // met à jour le chip « dossier d'origine » du diaporama
  function ssSetFolder(it) {
    var fl = document.getElementById('ss-folder');
    if (it && it.gurl) {
      fl.href = it.gurl;
      fl.textContent = '📁 ' + (it.folder || 'Dossier');
      fl.classList.remove('hidden');
    } else {
      fl.classList.add('hidden');
    }
  }

  function buildOrder(m) {
    var arr = visible.map(function(_, i) { return i; });
    if (m === 'rnd') {
      for (var i = arr.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
      }
    }
    // m === 'seq' : « Demo » suit l'ordre courant de la planche (tri + sens
    // choisis par l'utilisateur). arr est deja 0..n-1 dans l'ordre de `visible`,
    // donc on ne re-trie pas : on joue exactement ce que l'on voit.
    return arr;
  }

  function ssOpen() {
    var el = document.getElementById('ss');
    el.classList.add('open');
    var req = el.requestFullscreen || el.webkitRequestFullscreen || el.mozRequestFullScreen || el.msRequestFullscreen;
    if (req) { try { req.call(el).catch(function() {}); } catch (e) {} }
  }

  // ── aléatoire en flux : démarrage instantané, photos piochées au fil de l'eau ──
  var rndStream = false;
  var rndHist = [];
  var rndPos = -1;
  var rndLoopMode = 'rnd';   // 'rnd' | 'seq' | 'asc' — comportement en fin de playlist
  var ssPaused = false;

  function shuffleItems(a) {
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  function fetchPlaylist(mode, cb) {
    var d = new URLSearchParams(location.search).get('dir') || '0';
    fetch('/api/playlist?dir=' + encodeURIComponent(d) + '&mode=' + mode)
      .then(function(r) { return r.json(); })
      .then(function(j) { cb((j && j.items) ? j.items : []); })
      .catch(function() { cb([]); });
  }

  function ssTogglePause() {
    ssPaused = !ssPaused;
    var nameEl = document.getElementById('ss-name');
    if (ssPaused) {
      if (ssTimer) clearTimeout(ssTimer);
      ssTimer = null;
      // gèle la barre de progression à sa position actuelle
      var fill = document.getElementById('ss-fill');
      var w = getComputedStyle(fill).width;
      fill.style.transition = 'none';
      fill.style.width = w;
      nameEl.textContent = '⏸ ' + nameEl.textContent.replace(/^⏸ /, '');
    } else {
      // reprise : cycle complet sur la photo courante
      if (rndStream) {
        if (rndPos >= 0) rndShow(rndHist[rndPos]); else rndNext();
      } else {
        showSlide();
      }
    }
  }

  var streamMode = 'rnd';
  var rndErr = 0;

  function fetchRandom(cb) {
    var d = new URLSearchParams(location.search).get('dir') || '0';
    fetch('/api/random?dir=' + encodeURIComponent(d))
      .then(function(r) { return r.json(); })
      .then(function(j) { cb(j && j.url ? j : null); })
      .catch(function() { cb(null); });
  }

  function rndFetch(cb) {
    var last = (rndPos >= 0 && rndHist[rndPos]) ? rndHist[rndPos] : null;
    if (streamMode === 'asc' && last && last.key) {
      var ex = rndHist.slice(-15).map(function(it) { return it.key || ''; }).join('|');
      fetch('/api/assoc?prev=' + encodeURIComponent(last.key)
            + '&exclude=' + encodeURIComponent(ex))
        .then(function(r) { return r.json(); })
        .then(function(j) {
          if (j && j.url) cb(j);
          else fetchRandom(cb);  // pas d'association possible → pioche aléatoire
        })
        .catch(function() { fetchRandom(cb); });
      return;
    }
    fetchRandom(cb);
  }

  function rndShow(item) {
    var img = document.getElementById('ss-img');
    img.style.opacity = 0;
    img.src = thumbUrl(item, 1600);
    img.onload = function() {
      rndErr = 0;
      img.style.transition = 'opacity 0.5s';
      img.style.opacity = 1;
    };
    img.onerror = function() {
      // vignette serveur KO : retenter une fois l'original avant de passer
      if (item.url && img.src.indexOf('/api/thumb') >= 0) { img.src = item.url; return; }
      // image endommagée : on passe à la suivante sans l'afficher
      rndErr++;
      if (rndErr < 10) setTimeout(rndNext, 400);
    };
    var label = item.name || '';
    if (item.via && item.via.length) {
      label += '   —   lien : ' + item.via.join(' · ');
    }
    document.getElementById('ss-name').textContent = (ssPaused ? '⏸ ' : '') + label;
    ssSetFolder(item);
    ssStartFill();
    if (ssTimer) clearTimeout(ssTimer);
    ssTimer = ssPaused ? null : setTimeout(rndNext, DURATION);
  }

  function rndNext() {
    if (rndPos < rndHist.length - 1) {
      rndPos++;
      rndShow(rndHist[rndPos]);
      return;
    }
    // fin de la playlist pré-chargée
    if (!rndHist.length) {
      if (ssTimer) clearTimeout(ssTimer);
      ssTimer = setTimeout(rndNext, 2000);   // playlist pas encore prête
      return;
    }
    // on reboucle : re-mélange en aléatoire, ordre conservé sinon
    if (rndLoopMode === 'rnd') rndHist = shuffleItems(rndHist.slice());
    rndPos = 0;
    rndShow(rndHist[0]);
  }

  function rndPrev() {
    if (rndPos > 0) {
      rndPos--;
      rndShow(rndHist[rndPos]);
    }
  }

  function buildAssocOrder() {
    // ordonne 'visible' pour que chaque photo partage un tag avec la précédente
    var idx = visible.map(function(_, i) { return i; });
    if (idx.length < 2) return idx;
    var order = [idx[0]], used = {}; used[idx[0]] = 1;
    var cur = idx[0];
    while (order.length < idx.length) {
      var curkw = visible[cur].kw || [];
      var best = -1;
      for (var t = 0; t < idx.length; t++) {
        var j = idx[t];
        if (used[j]) continue;
        var kw = visible[j].kw || [];
        if (kw.some(function(x) { return curkw.indexOf(x) >= 0; })) { best = j; break; }
      }
      if (best < 0) {
        for (var u = 0; u < idx.length; u++) { if (!used[idx[u]]) { best = idx[u]; break; } }
      }
      order.push(best); used[best] = 1; cur = best;
    }
    return order;
  }

  function startSlideshow(m) {
    var localSel = selPersons.length > 0 || geoFilter != null;
    if (localSel) {
      // sélection personnes/géo : on joue toujours l'ensemble filtré localement
      if (!visible.length) return;
      ssPaused = false;
      rndStream = false;
      ssMode = m;
      ssOrder = (m === 'asc') ? buildAssocOrder() : buildOrder(m);
      ssIdx = 0;
      ssOpen();
      showSlide();
      return;
    }
    var filtered = selTags.length > 0 || qInput.value.trim() !== '';
    ssPaused = false;
    if (!filtered) {
      // Aucun filtre → on joue TOUTE la portée via une playlist ordonnée une
      // seule fois : aucune répétition (fini la pioche avec remise), seq
      // chronologique, association calculée sur l'ensemble.
      var plMode = (m === 'asc') ? 'assoc' : (m === 'rnd') ? 'rnd' : 'seq';
      rndStream = true;
      rndLoopMode = m;
      rndHist = [];
      rndPos = -1;
      rndErr = 0;
      ssOpen();
      document.getElementById('ss-name').textContent = 'Chargement…';
      fetchPlaylist(plMode, function(items) {
        if (!items.length) { document.getElementById('ss-name').textContent = 'Aucune photo'; return; }
        rndHist = items;
        rndPos = -1;
        rndNext();
      });
      return;
    }
    if (!visible.length) return;
    rndStream = false;
    ssMode = m;
    ssOrder = buildOrder(m);
    ssIdx = 0;
    ssOpen();
    showSlide();
  }

  function ssStartFill() {
    var fill = document.getElementById('ss-fill');
    fill.style.transition = 'none';
    fill.style.width = '0%';
    if (ssPaused) return;
    setTimeout(function() {
      fill.style.transition = 'width ' + DURATION + 'ms linear';
      fill.style.width = '100%';
    }, 50);
  }

  function showSlide() {
    if (ssTimer) clearTimeout(ssTimer);
    ssTimer = null;

    var f = visible[ssOrder[ssIdx]];
    var img = document.getElementById('ss-img');
    img.style.opacity = 0;
    img.src = thumbUrl(f, 1600);
    img.onload = function() {
      img.style.transition = 'opacity 0.5s';
      img.style.opacity = 1;
    };
    img.onerror = function() {
      // vignette serveur KO : retenter une fois l'original avant de passer
      if (f.url && img.src.indexOf('/api/thumb') >= 0) { img.src = f.url; return; }
      if (!ssPaused) setTimeout(function() { ssMove(1); }, 300);
    };
    document.getElementById('ss-name').textContent = (ssPaused ? '⏸ ' : '') + f.name;
    ssSetFolder(f);

    ssStartFill();
    if (!ssPaused) {
      ssTimer = setTimeout(function() {
        ssIdx = (ssIdx + 1) % ssOrder.length;
        if (ssIdx === 0 && ssMode === 'rnd') ssOrder = buildOrder('rnd');
        showSlide();
      }, DURATION);
    }
  }

  function stopSlideshow() {
    rndStream = false;
    ssPaused = false;
    if (ssTimer) clearTimeout(ssTimer);
    ssTimer = null;
    document.getElementById('ss').classList.remove('open');
    var ex = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen || document.msExitFullscreen;
    if (ex && (document.fullscreenElement || document.webkitFullscreenElement)) {
      try { ex.call(document).catch(function() {}); } catch (e) {}
    }
  }

  // navigation manuelle pendant le diaporama : il continue de tourner
  function ssMove(d) {
    if (rndStream) {
      if (d < 0) rndPrev(); else rndNext();
      return;
    }
    if (!ssOrder.length) return;
    ssIdx = (ssIdx + d + ssOrder.length) % ssOrder.length;
    showSlide();  // relance aussi le minuteur et la barre de progression
  }

  // 5 bandes verticales : bords = précédent/suivant, milieu = pause
  document.getElementById('ss-img').addEventListener('click', function(e) {
    var w = this.clientWidth;
    if (e.offsetX < w / 5) ssMove(-1);
    else if (e.offsetX > w * 4 / 5) ssMove(1);
    else ssTogglePause();
  });

  // swipe gauche/droite sur tout l'écran du diaporama
  var ssTX = null, ssTY = null;
  var ssEl2 = document.getElementById('ss');
  ssEl2.addEventListener('touchstart', function(e) {
    if (e.touches.length === 1) {
      ssTX = e.touches[0].clientX;
      ssTY = e.touches[0].clientY;
    }
  }, { passive: true });
  ssEl2.addEventListener('touchend', function(e) {
    if (ssTX === null) return;
    var dx = e.changedTouches[0].clientX - ssTX;
    var dy = e.changedTouches[0].clientY - ssTY;
    ssTX = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      ssMove(dx < 0 ? 1 : -1);
    }
  }, { passive: true });

  document.addEventListener('fullscreenchange', function() {
    if (!document.fullscreenElement && !document.webkitFullscreenElement && ssTimer) {
      stopSlideshow();
    }
  });
  document.addEventListener('webkitfullscreenchange', function() {
    if (!document.webkitFullscreenElement && !document.fullscreenElement && ssTimer) {
      stopSlideshow();
    }
  });

  // ── bandeau tagging IA ──
  function poll() {
    fetch('/api/status').then(function(r) { return r.json(); }).then(function(s) {
      var el = document.getElementById('pending');
      if (s.pending > 0) {
        el.style.display = 'block';
        el.textContent = '\\u{1F3F7} ' + s.pending + ' photo(s) en cours d\\'analyse IA\\u2026';
        setTimeout(poll, 10000);
      } else if (s.tagged > INITIAL_TAGGED) {
        el.style.display = 'block';
        el.innerHTML = '\\u2713 Nouveaux mots-cl\\u00e9s disponibles \\u2014 <a href="/files">actualiser la galerie</a>';
      } else {
        el.style.display = 'none';
      }
    }).catch(function() {});
  }

  // ── init ──
  document.getElementById('btn-date').onclick = function() { sortBy('date'); };
  document.getElementById('btn-name').onclick = function() { sortBy('name'); };
  document.getElementById('btn-seq').onclick  = function() { startSlideshow('seq'); };
  document.getElementById('btn-rnd').onclick  = function() { startSlideshow('rnd'); };
  document.getElementById('btn-asc').onclick  = function() { startSlideshow('asc'); };
  document.getElementById('lb-prev').onclick  = function() { lbMove(-1); };
  document.getElementById('lb-next').onclick  = function() { lbMove(1); };
  document.getElementById('lb-close').onclick = function() { closeLb(); };
  document.getElementById('ss-stop').onclick  = function() { stopSlideshow(); };

  buildTagbar();
  sortBy('date');
  poll();

  // ── filtre par motif (point 21) : navigation serveur (?motif=), lecture
  //    seule. Chips = liens ; actif en fixateur. Jamais une etiquette « rebut ».
  function motifNavUrl(m) {
    var params = new URLSearchParams(location.search);
    if (m) params.set('motif', m); else params.delete('motif');
    var qs = params.toString();
    return location.pathname + (qs ? '?' + qs : '');
  }
  function buildMotifbar() {
    var bar = document.getElementById('motifbar');
    var counts = (MOTIFS && MOTIFS.counts) || {};
    var sel = (MOTIFS && MOTIFS.sel) || '';
    var LABELS = {capture: "Captures d'\\u00e9cran", document: 'Documents / scans',
                  facture: 'Re\\u00e7us / factures'};
    var order = ['capture', 'document', 'facture'];
    var present = order.filter(function(k) { return counts[k]; });
    if (!present.length && !sel) { bar.className = 'motifbar'; return; }
    bar.innerHTML = '<span class="lbl">Motif :</span>';
    present.forEach(function(k) {
      var a = document.createElement('a');
      a.className = 'mchip' + (sel === k ? ' on' : '');
      a.href = motifNavUrl(sel === k ? '' : k);
      if (sel === k) a.setAttribute('aria-current', 'true');
      a.innerHTML = esc(LABELS[k] || k) + '<span class="n">' + counts[k] + '</span>';
      bar.appendChild(a);
    });
    if (sel) {
      var c = document.createElement('a');
      c.className = 'mchip'; c.href = motifNavUrl('');
      c.textContent = 'Tout afficher';
      bar.appendChild(c);
    }
    bar.className = 'motifbar show';
  }
  buildMotifbar();

  // ── suppression reversible depuis la visionneuse (point 21) ──
  // Le fichier part immediatement en quarantaine (.corbeille-rangement/, cote
  // serveur, re-cle de l'index compris) ; le toast offre l'annulation 10 s.
  var gToastEl = document.getElementById('gtoast'), gToastT = null;
  function gToast(msg, avecUndo) {
    gToastEl.innerHTML = '';
    var s = document.createElement('span'); s.textContent = msg;
    gToastEl.appendChild(s);
    if (avecUndo) {
      var b = document.createElement('button');
      b.className = 'b'; b.textContent = 'Annuler';
      b.onclick = function() {
        fetch('/api/files/undo', {method: 'POST',
          headers: {'Content-Type': 'application/json'}, body: '{}'})
          .then(function(r) { return r.json(); })
          .then(function(r) {
            if (r.ok) location.reload();
            else gToast(r.error || 'Rien \\u00e0 annuler.', false);
          })
          .catch(function() { gToast('Le serveur n a pas r\\u00e9pondu.', false); });
      };
      gToastEl.appendChild(b);
    }
    gToastEl.className = 'gtoast show';
    if (gToastT) clearTimeout(gToastT);
    gToastT = setTimeout(function() { gToastEl.className = 'gtoast'; },
                         avecUndo ? 10000 : 4000);
  }

  function removeCurrent() {
    var f = visible[lbIdx];
    function drop(arr) { var i = arr.indexOf(f); if (i >= 0) arr.splice(i, 1); }
    drop(FILES); drop(sorted); drop(visible);
    if (!visible.length) { closeLb(); renderGrid(); return; }
    if (lbIdx >= visible.length) lbIdx = visible.length - 1;
    renderGrid();
    showLb();
  }

  document.getElementById('lb-del').onclick = function() {
    var f = visible[lbIdx];
    if (!f) return;
    var btn = this; btn.disabled = true;
    fetch('/api/files/delete', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key: f.key})})
      .then(function(r) { return r.json(); })
      .then(function(r) {
        btn.disabled = false;
        if (!r.ok) { gToast(r.error || 'Echec de la suppression.', false); return; }
        removeCurrent();
        gToast('Photo d\\u00e9plac\\u00e9e vers la corbeille.', true);
      })
      .catch(function() {
        btn.disabled = false;
        gToast('Le serveur n a pas r\\u00e9pondu.', false);
      });
  };

  // ── filtres personnes + géo ──
  function haversine(la1, lo1, la2, lo2) {
    var R = 6371, d2r = Math.PI / 180;
    var dLa = (la2 - la1) * d2r, dLo = (lo2 - lo1) * d2r;
    var a = Math.sin(dLa / 2) * Math.sin(dLa / 2) +
            Math.cos(la1 * d2r) * Math.cos(la2 * d2r) * Math.sin(dLo / 2) * Math.sin(dLo / 2);
    return 2 * R * Math.asin(Math.sqrt(a));
  }
  function updateSelInfo() {
    var parts = [];
    if (selPersons.length) parts.push(selPersons.length + ' personne(s)');
    if (geoFilter) parts.push('zone ' + geoFilter.km + ' km');
    document.getElementById('selinfo').textContent = parts.length ? ('· sélection : ' + parts.join(' + ')) : '';
  }
  var PERSONS = (function() {
    var s = {};
    FILES.forEach(function(f) {
      (f.kw || []).forEach(function(k) { if (k.indexOf('personne:') === 0) s[k] = 1; });
    });
    return Object.keys(s).sort();
  })();
  function renderPersonChips() {
    var box = document.getElementById('personchips'); box.innerHTML = '';
    if (!PERSONS.length) { box.innerHTML = '<span class="lbl">(aucune ici)</span>'; return; }
    PERSONS.forEach(function(tag) {
      var b = document.createElement('span');
      b.className = 'pchip' + (selPersons.indexOf(tag) >= 0 ? ' on' : '');
      b.textContent = tag.slice(9);
      b.onclick = function() {
        var i = selPersons.indexOf(tag);
        if (i >= 0) selPersons.splice(i, 1); else selPersons.push(tag);
        renderPersonChips(); updateSelInfo(); applyFilter();
      };
      box.appendChild(b);
    });
  }
  renderPersonChips();

  var geoMap = null, geoCenter = null, geoMarker = null, geoCircle = null;
  function geoInit() {
    if (geoMap) { setTimeout(function() { geoMap.invalidateSize(); }, 60); return; }
    geoMap = L.map('geomap').setView([46.8, 8.2], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(geoMap);
    var pts = [];
    FILES.forEach(function(f) {
      if (f.gps) {
        L.circleMarker([f.gps[0], f.gps[1]], { radius: 3, color: '#4A8C7B', weight: 1, fillOpacity: 0.6 }).addTo(geoMap);  /* --fixateur */
        pts.push([f.gps[0], f.gps[1]]);
      }
    });
    if (pts.length) geoMap.fitBounds(L.latLngBounds(pts), { padding: [30, 30] });
    geoMap.on('click', function(e) { setGeoCenter(e.latlng.lat, e.latlng.lng); });
    setTimeout(function() { geoMap.invalidateSize(); }, 60);
  }
  function setGeoCenter(lat, lon) {
    geoCenter = [lat, lon];
    if (geoMarker) geoMap.removeLayer(geoMarker);
    geoMarker = L.marker([lat, lon]).addTo(geoMap);
    drawGeoCircle();
  }
  function drawGeoCircle() {
    if (!geoCenter) return;
    var km = parseInt(document.getElementById('georadius').value, 10);
    if (geoCircle) geoMap.removeLayer(geoCircle);
    geoCircle = L.circle(geoCenter, { radius: km * 1000, color: '#4A8C7B', fillOpacity: 0.08 }).addTo(geoMap);  /* --fixateur (zone) */
    var n = 0;
    FILES.forEach(function(f) {
      if (f.gps && haversine(geoCenter[0], geoCenter[1], f.gps[0], f.gps[1]) <= km) n++;
    });
    document.getElementById('geocount').textContent = '· ' + n + ' photo(s) dans la zone';
  }
  document.getElementById('geotoggle').onclick = function() {
    var p = document.getElementById('geopanel');
    var open = p.classList.toggle('open');
    this.classList.toggle('on', open);
    if (open) geoInit();
  };
  document.getElementById('georadius').oninput = function() {
    document.getElementById('georadlbl').textContent = this.value + ' km';
    drawGeoCircle();
  };
  document.getElementById('geoapply').onclick = function() {
    if (!geoCenter) { alert('Clique d\\'abord un point sur la carte.'); return; }
    var km = parseInt(document.getElementById('georadius').value, 10);
    geoFilter = { lat: geoCenter[0], lon: geoCenter[1], km: km };
    updateSelInfo(); applyFilter();
  };
  document.getElementById('geoclear').onclick = function() {
    geoFilter = null;
    document.getElementById('geocount').textContent = '';
    updateSelInfo(); applyFilter();
  };

  // Page de resultats globale (/files?q=..., depuis un Lieu de /sujets ou un
  // marqueur de Carte) : le serveur a deja rempli la grille avec le resultat
  // de la recherche, dans l'ordre de pertinence. On se met en mode IA — pas de
  // filtre par mot-cle, tri par pertinence — pour que la barre reflete la
  // requete et qu'affiner reste possible. iaResultats = tout FILES (chaque
  // photo passe le test d'appartenance), rang = position renvoyee par le serveur.
  if (SEARCHQ) {
    qInput.value = SEARCHQ;
    modeIA = true;
    btnIA.className = 'tb active';
    btnIA.setAttribute('aria-pressed', 'true');
    qInput.placeholder = 'Décris la photo…';
    iaResultats = {};
    FILES.forEach(function(f, i) { iaResultats[f.key] = i; });
    applyFilter();
  }

  // lancement auto du diaporama après redirection récursive
  var pl = new URLSearchParams(location.search).get('play');
  if (pl === 'seq' || pl === 'rnd') {
    setTimeout(function() { startSlideshow(pl); }, 300);
  }
})();
</script>
</body>
</html>
"""


BROWSE_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Explorateur</title>
<style>
/* Etape A tokenisation (chambre noire) : couleurs + police remplacees par les
   tokens de ui/tokens.css. Interdits retires : bleu iOS #0a84ff, gris neutre #555.
   Etape B : espacements/rayons/tailles qui EGALENT deja un token pointent vers lui
   (16px->--e-4, 12px->--e-3, 8px->--e-2, 0.75rem->--t-xs, 0.85rem->--t-sm,
   999px->--r-pill). Substitutions a valeur identique : rendu inchange.
   Passe DESIGN (11/08) : valeurs hors echelle calees sur les tokens, memes
   mappings que les autres pages (0.9rem -> --t-md, 0.78rem/13px -> --t-sm avec
   --t-xs pour les compteurs de donnees, radius 8/10px -> --r-md, espacements ->
   echelle 4px). Tailles fixes (22px des cases a cocher) non tokenisees. */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--f-texte);
       background: var(--salle); color: var(--texte); min-height: 100vh; }
.bar { display: flex; gap: var(--e-4); align-items: center; padding: var(--e-4);
       background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; }
.back { color: var(--texte); text-decoration: none; font-size: var(--t-md); }
.crumbs { color: var(--graphite); font-size: var(--t-md); }
.crumbs a { color: var(--texte); text-decoration: none; }
.list { max-width: 720px; margin: 0 auto; padding: var(--e-3); }
.row { display: flex; align-items: center; gap: var(--e-3); padding: var(--e-3) var(--e-4);
       background: var(--salle-2); border-radius: var(--r-md); margin-bottom: var(--e-2);
       text-decoration: none; color: var(--texte); font-size: var(--t-md); }
.row:active { background: var(--salle-3); }
.row .ic { flex-shrink: 0; }
.row .nm { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row .sz { color: var(--graphite); font-size: var(--t-xs); flex-shrink: 0; }
.row.dir .nm { color: var(--texte); }
.empty { color: var(--graphite); text-align: center; padding: var(--e-8); }
/* Etape B — gestion de fichiers : rangees selectionnables + barre d'actions sur
   PAPIER (surface « decider »). Cibles 44px, primaire = fixateur, suppr = encre. */
.row .lk { display: flex; align-items: center; gap: var(--e-3); flex: 1; min-width: 0;
           text-decoration: none; color: inherit; }
.row .sel { width: 22px; height: 22px; flex-shrink: 0; accent-color: var(--fixateur); cursor: pointer; }
.row.marked { outline: 2px solid var(--veilleuse); outline-offset: -2px; }
.actbar { position: sticky; bottom: var(--e-2); margin: var(--e-3) auto 0; max-width: 720px;
          display: flex; gap: var(--e-2); align-items: center; flex-wrap: wrap;
          background: var(--papier); color: var(--texte-papier);
          border: 1px solid var(--papier-2); border-radius: var(--r-md);
          padding: var(--e-3); box-shadow: 0 6px 30px #000a; }
.actbar .cnt { font-family: var(--f-donnees); font-size: var(--t-xs); margin-right: auto; }
.actbar .b { min-height: var(--touch); padding: 0 var(--e-4); border-radius: var(--r-md);
             border: 1px solid var(--graphite-p); background: transparent;
             color: var(--texte-papier); font: 500 var(--t-sm) var(--f-texte); cursor: pointer; }
.actbar .b:disabled { opacity: 0.4; cursor: default; }
.actbar .b.prim { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.actbar .b.del { border-color: var(--encre); color: var(--encre); }
.fxtoast { position: sticky; bottom: var(--e-2); margin: var(--e-2) auto 0; max-width: 560px;
           display: flex; gap: var(--e-3); align-items: center; background: var(--salle-3);
           border: var(--trait); border-radius: var(--r-pill); padding: var(--e-3) var(--e-3) var(--e-3) var(--e-4); font-size: var(--t-sm); }
.fxtoast .b { min-height: 36px; padding: 0 var(--e-3); border-radius: var(--r-pill); border: var(--trait);
              background: var(--salle-2); color: var(--texte); cursor: pointer; }
</style>
</head>
<body>
<!--APPNAV-->
<div class="bar">
  __EXTRA__
  <span class="crumbs">__CRUMBS__</span>
</div>
<div class="list">
__ROWS__
</div>
<div class="actbar" id="actbar" style="display:none">
  <span class="cnt" id="fx-cnt">Aucune s&eacute;lection</span>
  <button class="b" id="fx-rename" disabled>Renommer</button>
  <button class="b" id="fx-cut" disabled>Couper</button>
  <button class="b prim" id="fx-paste" style="display:none">Coller ici</button>
  <button class="b del" id="fx-del" disabled>Supprimer</button>
  <button class="b" id="fx-mkdir">Nouveau dossier</button>
  <button class="b" id="fx-undo" title="Annuler la derni&egrave;re op&eacute;ration">Annuler</button>
</div>
<div class="fxtoast" id="fx-toast" style="display:none" role="status" aria-live="polite"></div>
<script>window.__BROWSE_CTX__ = __CTX__;</script>
<script>
(function(){
  var CTX = window.__BROWSE_CTX__;                 // {idx, sub} en dossier, sinon null
  var bar = document.getElementById('actbar'), toastEl = document.getElementById('fx-toast');
  function api(op, body){ return fetch('/api/files/'+op, {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(body||{})})
    .then(function(r){return r.json();}); }
  function flash(m){ try{ sessionStorage.setItem('fx_flash', m); }catch(e){} }
  function cutGet(){ try{ return JSON.parse(sessionStorage.getItem('fx_cut')||'[]'); }catch(e){ return []; } }
  function cutSet(a){ try{ (a&&a.length) ? sessionStorage.setItem('fx_cut', JSON.stringify(a))
                                         : sessionStorage.removeItem('fx_cut'); }catch(e){} }
  function selected(){ return [].slice.call(document.querySelectorAll('.row .sel:checked'))
    .map(function(c){ var r=c.closest('.row'); return {idx:+r.dataset.idx, rel:r.dataset.rel, name:r.dataset.name}; }); }
  function toast(msg, undo){
    if(!toastEl) return; toastEl.innerHTML='';
    var s=document.createElement('span'); s.style.flex='1'; s.textContent=msg; toastEl.appendChild(s);
    if(undo){ var b=document.createElement('button'); b.className='b'; b.textContent='Annuler';
      b.onclick=function(){ api('undo',{}).then(function(r){ if(r.ok) location.reload(); else toast(r.error||'Echec.', false); }); };
      toastEl.appendChild(b); }
    toastEl.style.display='flex';
    clearTimeout(toastEl._t); toastEl._t=setTimeout(function(){ toastEl.style.display='none'; }, undo?10000:4000);
  }
  try{ var fl=sessionStorage.getItem('fx_flash'); if(fl){ sessionStorage.removeItem('fx_flash'); toast(fl, true); } }catch(e){}
  function refresh(){
    var inFolder = CTX && typeof CTX.idx==='number'; if(bar) bar.style.display = inFolder?'flex':'none';
    if(!inFolder) return; var sel=selected(), cut=cutGet();
    document.getElementById('fx-cnt').textContent = sel.length ? (sel.length+' s\\u00e9lectionn\\u00e9(s)')
      : (cut.length ? (cut.length+' \\u00e0 coller') : 'Aucune s\\u00e9lection');
    document.getElementById('fx-rename').disabled = sel.length!==1;
    document.getElementById('fx-cut').disabled = sel.length===0;
    document.getElementById('fx-del').disabled = sel.length===0;
    var p=document.getElementById('fx-paste'); p.style.display = cut.length?'inline-block':'none';
    p.textContent = 'Coller ici ('+cut.length+')';
  }
  document.addEventListener('change', function(e){ if(e.target.classList&&e.target.classList.contains('sel')) refresh(); });
  function bind(id, fn){ var el=document.getElementById(id); if(el) el.onclick=fn; }
  bind('fx-rename', function(){ var s=selected(); if(s.length!==1) return;
    var nn=prompt('Nouveau nom :', s[0].name); if(!nn||!nn.trim()||nn===s[0].name) return;
    api('rename',{idx:s[0].idx, rel:s[0].rel, name:nn.trim()}).then(function(r){
      if(r.ok){ flash('Renomm\\u00e9.'); location.reload(); } else toast(r.error||'Echec.', false); }); });
  bind('fx-cut', function(){ var s=selected(); if(!s.length) return; cutSet(s);
    toast(s.length+' coup\\u00e9(s). Ouvre le dossier cible puis \\u00ab Coller ici \\u00bb.', false); refresh(); });
  bind('fx-paste', function(){ var cut=cutGet(); if(!cut.length||!CTX) return; var n=cut.length, i=0;
    (function next(){ if(i>=cut.length){ cutSet([]); flash(n+' d\\u00e9plac\\u00e9(s).'); location.reload(); return; }
      var it=cut[i++]; api('move',{idx:it.idx, rel:it.rel, dst_idx:CTX.idx, dst_rel:CTX.sub}).then(function(r){
        if(!r.ok){ cutSet([]); toast(r.error||'Echec du d\\u00e9placement.', false); return; } next(); }); })(); });
  bind('fx-del', function(){ var s=selected(); if(!s.length) return;
    if(!confirm('Envoyer '+s.length+' \\u00e9l\\u00e9ment(s) \\u00e0 la corbeille ? (r\\u00e9versible)')) return;
    var n=s.length, i=0; (function next(){ if(i>=s.length){ flash(n+' envoy\\u00e9(s) \\u00e0 la corbeille.'); location.reload(); return; }
      var it=s[i++]; api('delete',{idx:it.idx, rel:it.rel}).then(function(r){ if(!r.ok){ toast(r.error||'Echec.', false); return; } next(); }); })(); });
  bind('fx-mkdir', function(){ if(!CTX) return; var nm=prompt('Nom du nouveau dossier :'); if(!nm||!nm.trim()) return;
    api('mkdir',{idx:CTX.idx, rel:CTX.sub, name:nm.trim()}).then(function(r){
      if(r.ok){ flash('Dossier cr\\u00e9\\u00e9.'); location.reload(); } else toast(r.error||'Echec.', false); }); });
  bind('fx-undo', function(){ api('undo',{}).then(function(r){ if(r.ok){ flash('Annul\\u00e9.'); location.reload(); } else toast(r.error||'Rien \\u00e0 annuler.', false); }); });
  refresh();
})();
</script>
</body>
</html>
"""


REGLAGES_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reglages &amp; maintenance</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--f-texte); background: var(--salle); color: var(--texte); min-height: 100vh; }
.wrap { max-width: 1000px; margin: 0 auto; padding: var(--e-2) var(--e-4) 60px; }
h2 { font: 600 var(--t-lg)/1.2 var(--f-affichage); margin: 22px 0 10px; }
.hd { display: flex; align-items: center; gap: 10px; margin: var(--e-2) 0 2px; }
.hd .t { color: var(--graphite); font-family: var(--f-donnees); font-size: var(--t-xs); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
.card { background: var(--salle-3); border: var(--trait); border-radius: 10px; padding: var(--e-3); }
.card .k { color: var(--graphite); font-size: 0.72rem; }
.card .v { font: 600 var(--t-lg)/1.1 var(--f-donnees); margin-top: var(--e-1); }
.card .tv { color: var(--graphite); font-size: var(--t-xs); margin-top: var(--e-1); }
a.card { text-decoration: none; color: inherit; display: block; transition: border-color .15s, background .15s; }
a.card:hover { border-color: var(--graphite); background: var(--salle-2); }
a.card .k { font-size: var(--t-md); color: var(--texte); }
table { width: 100%; border-collapse: collapse; font-size: var(--t-sm); }
td, th { text-align: left; padding: 6px var(--e-2); border-bottom: var(--trait); }
td.n, th.n { text-align: right; font-family: var(--f-donnees); }
.mut { color: var(--graphite); font-size: 0.8rem; }
.panel { background: var(--papier); color: var(--texte-papier); border: 1px solid var(--papier-2);
         border-radius: var(--r-md); padding: 14px; margin: 10px 0; box-shadow: 0 6px 30px #000a; }
.panel h3 { font: 600 var(--t-md)/1.2 var(--f-affichage); margin-bottom: var(--e-2); }
.panel td, .panel th { border-color: var(--papier-2); }
.rowf { display: flex; gap: var(--e-2); align-items: center; flex-wrap: wrap; }
.b { min-height: var(--touch); padding: 0 14px; border-radius: 8px; border: 1px solid var(--graphite-p);
     background: transparent; color: var(--texte-papier); font: 500 var(--t-sm) var(--f-texte); cursor: pointer; }
.b.prim { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
.badge { font-family: var(--f-donnees); font-size: 0.72rem; padding: 2px var(--e-2); border-radius: var(--r-pill);
         border: 1px solid var(--graphite-p); color: var(--graphite-p); }
.badge.on { color: #fff; background: var(--fixateur); border-color: var(--fixateur); }
.badge.paused { color: #fff; background: var(--veilleuse); border-color: var(--veilleuse); }
.subh { font: 600 var(--t-sm)/1.2 var(--f-affichage); margin: 16px 0 2px; letter-spacing: -0.01em; }
.stepren { list-style: none; display: flex; flex-direction: column; gap: var(--e-2); margin-top: var(--e-2); }
.stepren li { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.stepren > li > .b { flex: 0 0 auto; min-width: 12rem; }
.stepren .mut { flex: 1 1 14rem; min-width: 0; }
.renmsg { margin-top: 10px; padding: var(--e-2) var(--e-3); border-radius: var(--r-md); background: var(--papier-2);
          color: var(--texte-papier); font: 500 0.82rem var(--f-donnees); }
</style>
</head>
<body>
<!--APPNAV-->
<div class="wrap">
  <div class="hd">
    <h2 style="margin:0">Reglages &amp; maintenance</h2>
    <span class="t" id="clock"></span>
    <button class="b" id="refresh" style="margin-left:auto;border-color:var(--graphite);color:var(--texte)">Rafraichir</button>
  </div>
  <p class="mut">Reconnaissance des visages : <b>CPU</b> (seul Ollama utilise le GPU). Cette page se rafraichit toute seule.</p>

  <h2>Outils &amp; pages</h2>
  <div class="cards">
    <a class="card" href="/files"><div class="k">&#128247; Galerie</div><div class="tv">Planche contact, recherche par tags</div></a>
    <a class="card" href="/browse"><div class="k">&#128193; Dossiers</div><div class="tv">Parcourir + gerer les fichiers (deplacer, renommer)</div></a>
    <a class="card" href="/map"><div class="k">&#128506;&#65039; Carte</div><div class="tv">Photos geolocalisees</div></a>
    <a class="card" href="/people"><div class="k">&#128101; Personnes</div><div class="tv">Nommer, verifier, tri au clavier</div></a>
    <a class="card" href="/pets"><div class="k">&#128062; Animaux</div><div class="tv">Chats nommes, groupes</div></a>
    <a class="card" href="/"><div class="k">&#128228; Envoyer des photos</div><div class="tv">Upload depuis le telephone</div></a>
    <a class="card" href="/sante"><div class="k">&#129658; Sante</div><div class="tv">Fichiers a probleme (EXIF, illisibles)</div></a>
  </div>

  <h2>Etat en direct</h2>
  <div class="cards" id="live"></div>

  <h2>Bibliotheque</h2>
  <div class="cards" id="lib"></div>

  <div class="panel">
    <h3>Maintenance <span class="badge" id="maint-badge"></span></h3>
    <div class="rowf" style="margin-bottom:10px">
      <button class="b prim" id="run">Lancer un cycle maintenant</button>
      <button class="b" id="pause">Pause</button>
      <button class="b" id="census">Recensement (lecture seule)</button>
      <button class="b" id="planyear">Plan de rangement par annee</button>
      <span class="mut" id="maint-msg"></span>
    </div>
    <table id="steps"><thead><tr><th>Etape</th><th>Autonomie</th><th class="n">Cadence</th><th>Dernier passage</th></tr></thead><tbody></tbody></table>
    <p class="mut" style="margin-top:8px">Autonomie : <b>auto</b> = executee seule quand due (sur/reversible) ; <b>propose</b> = plan prepare, pas applique ; <b>off</b> = desactivee.</p>

    <h4 class="subh">Renommage intelligent des fichiers</h4>
    <p class="mut">Renomme les fichiers bruts (Screenshot_, IMG_, exports WhatsApp&hellip;) en noms dates et lisibles, EN PLACE sur le NAS. Entierement reversible. Suis les 4 etapes dans l'ordre :</p>
    <ol class="stepren">
      <li><button class="b" id="planren">1 &middot; Generer le plan</button><span class="mut">Ecrit <b>docs/plan_renommage.md</b> &mdash; a relire avant d'appliquer.</span></li>
      <li><button class="b" id="rencheck">2 &middot; Verifier a blanc</button><span class="mut">Simulation : compte les renommages applicables, ne touche aucun fichier.</span></li>
      <li><button class="b prim" id="renapply">3 &middot; Appliquer un lot</button><span class="mut">Renomme reellement jusqu'a 200 fichiers. Reclique pour le lot suivant, jusqu'a 0 restant.</span></li>
      <li><button class="b" id="renundo">4 &middot; Annuler le dernier lot</button><span class="mut">Defait le dernier lot applique.</span></li>
    </ol>
    <div class="renmsg" id="ren-msg" role="status" aria-live="polite">Clique &laquo;&nbsp;1 &middot; Generer le plan&nbsp;&raquo; pour commencer.</div>

    <h4 class="subh">Reclassement des animaux mal classes</h4>
    <p class="mut">Des photos d'animaux (Mutz, Caline&hellip;) portent encore un tag <b>personne:</b> au lieu de <b>animal:</b>, parfois avec une fiche personne en double. Cet outil corrige le prefixe SANS changer le nom, et retire la fiche en double. Entierement reversible. Les tags sans prefixe (l'adjectif &laquo; caline &raquo;) ne sont pas touches.</p>
    <ol class="stepren">
      <li><button class="b" id="reclcheck">1 &middot; Apercu (a blanc)</button><span class="mut">Compte les photos <b>personne:</b> a passer en <b>animal:</b> ; ne touche a rien.</span></li>
      <li><button class="b prim" id="reclapply">2 &middot; Appliquer</button><span class="mut">Reclasse les photos listees + retire les fiches en double. Reversible.</span></li>
      <li><button class="b" id="reclundo">3 &middot; Annuler le dernier reclassement</button><span class="mut">Remet les tags <b>personne:</b> et restaure les fiches.</span></li>
    </ol>
    <div class="renmsg" id="recl-msg" role="status" aria-live="polite">Clique &laquo;&nbsp;1 &middot; Apercu&nbsp;&raquo; pour voir ce qui serait reclasse.</div>
  </div>

  <h2>Dedoublonnage &amp; rangement</h2>
  <div id="dedup"></div>

  <h2>Reglages (lecture seule)</h2>
  <div id="config"></div>
</div>
<script>
function j(u,o){ return fetch(u,o).then(function(r){return r.json();}); }
function esc(s){ return (''+s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];}); }
function card(k,v){ return '<div class="card"><div class="k">'+esc(k)+'</div><div class="v">'+esc(v)+'</div></div>'; }
function human(n){ if(n==null) return '?'; var u=['o','Ko','Mo','Go','To'],i=0; while(n>=1024&&i<4){n/=1024;i++;} return n.toFixed(i?1:0)+' '+u[i]; }
function tstamp(t){ if(!t) return 'jamais'; return new Date(t*1000).toLocaleString('fr-FR'); }
function kv(obj){ var r=''; Object.keys(obj||{}).forEach(function(k){ r+='<tr><td>'+esc(k)+'</td><td class="n">'+esc(obj[k])+'</td></tr>'; });
  return r ? ('<table>'+r+'</table>') : '<span class="mut">aucune donnee (lance le recensement)</span>'; }
function load(){
  j('/api/maint/status').then(function(s){
    document.getElementById('clock').textContent = new Date().toLocaleTimeString('fr-FR');
    var hw=s.hw||{}, g=hw.gpu||null, q=s.queues||{}, c=s.counts||{}, m=s.maint||{};
    document.getElementById('live').innerHTML=[
      card('CPU', hw.cpu_percent!=null?Math.round(hw.cpu_percent)+' %':'?'),
      card('RAM libre', hw.ram_avail_gb!=null?(hw.ram_avail_gb+' / '+hw.ram_total_gb+' Go'):'?'),
      card('GPU VRAM', g?(g.vram_free_mb+' / '+g.vram_total_mb+' Mo'):'\\u2014'),
      card('Occupe', s.busy?'oui':'non'),
      card('File tagging', q.tag||0),
      card('File visages', q.faces||0),
      card('File animaux', q.animaux||0),
      card('Ecritures noms', q.personnes||0),
      card('Empreintes animaux', s.pets_vec!=null?s.pets_vec:(s.pets_embed!=null?s.pets_embed:'?'))
    ].join('');
    // Boucle scan/backup (audit O5) : un crash silencieux devient visible ici.
    var bo=s.boucle||{}, bv=s.backup_verify||{};
    function heure(t){ if(!t) return 'jamais'; return new Date(t*1000).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'}); }
    var scanTxt=heure(bo.dernier_scan);
    if(bo.derniere_erreur && (bo.erreur_at||0)>=(bo.dernier_scan||0)) scanTxt='\\u26a0 erreur';
    var scanTv=bo.derniere_erreur?('Derniere erreur ('+heure(bo.erreur_at)+') : '+bo.derniere_erreur):'Scan + sauvegarde NAS';
    // Verification de sauvegarde (assurance-vie de la verite terrain, audit A).
    // ok=true : verifiee saine ; ok=false : integrity_check NON ok (alerte) ;
    // ok=null : verification impossible (ne PAS incriminer la sauvegarde).
    var bvTxt = !bv.at ? 'jamais'
      : bv.ok===true ? 'ok '+heure(bv.at)
      : bv.ok===false ? '\\u26a0 suspecte'
      : 'verif. impossible';
    var bvTv = bv.at
      ? ('Restauration a blanc : '+(bv.confirmes!=null?bv.confirmes+' confirmes, '+bv.exclusions+' exclusions':'?')
         +(bv.detail?' \\u00b7 '+bv.detail:'')
         +(bv.jugements_exportes?' \\u00b7 jugements exportes '+heure(bv.jugements_exportes):''))
      : 'Apres la 1re sauvegarde horaire';
    // Lecture des dates/GPS dans les fichiers : la tache mourait au demarrage
    // sans rien dire (12 407 photos sans date au jour pres). Elle rend
    // desormais des comptes ici.
    var bf=s.backfill||{};
    function bfCard(titre, o){
      o=o||{};
      var v = o.etat==='en cours' ? (o.faits||0)+' / '+(o.todo||0)
            : o.etat==='termine'  ? (o.trouves||0)+' lues'
            : (o.etat||'?');
      var muets = o.muets ? (' \\u00b7 \\u26a0 '+o.muets+' fichiers muets (a relire au prochain demarrage)') : '';
      var tv = o.erreur ? ('\\u26a0 '+o.erreur)
             : o.etat==='termine' ? ('Termine a '+heure(o.fini_at)+' \\u00b7 '+(o.todo||0)+' fichiers relus'+muets)
             : o.etat==='en cours' ? ((o.trouves||0)+' trouvees jusqu\\'ici'+muets)
             : 'Lecture ExifTool en tache de fond';
      return '<div class="card"><div class="k">'+esc(titre)+'</div><div class="v">'+esc(v)+'</div><div class="tv">'+esc(tv)+'</div></div>';
    }
    document.getElementById('live').innerHTML+=[
      '<div class="card"><div class="k">Dernier scan</div><div class="v">'+esc(scanTxt)+'</div><div class="tv">'+esc(scanTv)+'</div></div>',
      '<div class="card"><div class="k">Sauvegarde verifiee</div><div class="v">'+esc(bvTxt)+'</div><div class="tv">'+esc(bvTv)+'</div></div>',
      bfCard('Dates de prise de vue', bf.dates),
      bfCard('Coordonnees GPS', bf.gps),
      bfCard('Noms relus dans les fichiers', bf.noms)
    ].join('');
    document.getElementById('lib').innerHTML=[
      card('Entrees', c.entrees||0), card('Taguees', c.tagues||0),
      card('Personnes', c.personnes||0), card('Animaux', c.animaux||0),
      card('Visages', c.visages||0)
    ].join('');
    var badge=document.getElementById('maint-badge');
    if(m.paused){ badge.textContent='en pause'; badge.className='badge paused'; }
    else if(m.auto){ badge.textContent='auto'; badge.className='badge on'; }
    else { badge.textContent='off'; badge.className='badge'; }
    document.getElementById('pause').textContent = m.paused?'Reprendre':'Pause';
    var au=m.autonomy||{}, itv=m.intervals||{}, st=m.state||{};
    var tb=document.querySelector('#steps tbody'); tb.innerHTML='';
    Object.keys(itv).forEach(function(k){
      var jours=Math.round((itv[k]||0)/86400*10)/10;
      tb.innerHTML+='<tr><td>'+esc(k)+'</td><td>'+esc(au[k]||'?')+'</td><td class="n">'+jours+' j</td><td>'+esc(tstamp(st[k]))+'</td></tr>';
    });
    var pa=s.plan_annee||{}, pae='';
    if(pa.total_a_ranger!=null){
      pae='<div class="k">A ranger : <b>'+pa.total_a_ranger+'</b> \\u00b7 sans date : <b>'+(pa.sans_date||0)+'</b> \\u00b7 conflits : <b>'+(pa.conflits||0)+'</b></div>';
      var yr=pa.par_annee||{}, keys=Object.keys(yr);
      if(keys.length){ pae+='<table style="margin-top:6px"><tr><th>Annee</th><th class="n">A ranger</th></tr>';
        keys.forEach(function(k){ pae+='<tr><td>'+esc(k)+'</td><td class="n">'+esc(yr[k])+'</td></tr>'; }); pae+='</table>'; }
    } else { pae='<span class="mut">Clique \\u00ab Plan de rangement par annee \\u00bb pour le generer (lecture seule).</span>'; }
    document.getElementById('dedup').innerHTML=
      '<div class="cards"><div class="card" style="grid-column:1/-1"><div class="k">Recensement (doublons par contenu)</div>'+kv(s.recensement)+'</div>'+
      '<div class="card" style="grid-column:1/-1"><div class="k">Plan de rangement (dedoublonnage)</div>'+kv(s.plan)+'</div>'+
      '<div class="card" style="grid-column:1/-1"><div class="k">Rangement par annee (_A TRIER)</div>'+pae+'</div></div>';
    var cf=s.config||{}, rows='';
    rows+='<tr><td>Modele tagging</td><td>'+esc(cf.MODEL||'?')+'</td></tr>';
    rows+='<tr><td>Pipeline animaux</td><td>'+esc(cf.ANIMAL_PIPELINE_VERSION||'?')+'</td></tr>';
    var tp=cf.tagging_pipe||{}, tps=Object.keys(tp).sort().map(function(k){return esc(k)+' : '+tp[k];}).join(' \\u00b7 ');
    rows+='<tr><td>Pipeline tagging</td><td>'+esc(cf.TAGGING_PIPELINE_VERSION||'?')+(tps?'<br><span class="mut">'+tps+'</span>':'')+'</td></tr>';
    rows+='<tr><td>Seuil match visages</td><td>'+esc(cf.FACE_MATCH_SIM)+'</td></tr>';
    rows+='<tr><td>Seuil match animaux</td><td>'+esc(cf.PET_MATCH_SIM)+'</td></tr>';
    rows+='<tr><td>Dossier Uploads</td><td>'+esc(cf.UPLOAD_DIR||'')+'</td></tr>';
    (cf.racines||[]).forEach(function(r){ rows+='<tr><td>Racine \\u00ab '+esc(r[0])+' \\u00bb</td><td>'+esc(r[1])+'</td></tr>'; });
    document.getElementById('config').innerHTML='<table>'+rows+'</table>';
  }).catch(function(){});
}
function act(u, warn, msgId){
  if(warn && !confirm(warn)) return;
  var el=document.getElementById(msgId||'maint-msg');
  el.textContent='\\u2026';
  j(u,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(function(r){
    el.textContent = r.msg || (r.paused!=null?(r.paused?'Maintenance en pause.':'Maintenance reprise.'):(r.ok?'OK.':(r.error||'Echec.')));
    setTimeout(load, 800);
  }).catch(function(){ el.textContent='Le serveur n a pas repondu.'; });
}
document.getElementById('refresh').onclick=load;
document.getElementById('run').onclick=function(){ act('/api/maint/run'); };
document.getElementById('pause').onclick=function(){ act('/api/maint/toggle'); };
document.getElementById('census').onclick=function(){ act('/api/maint/census', 'Lancer le recensement complet ? Lecture seule mais ~4 h et sollicite le NAS.'); };
document.getElementById('planyear').onclick=function(){ act('/api/maint/plan-annee'); };
document.getElementById('planren').onclick=function(){ act('/api/maint/plan-renommage', null, 'ren-msg'); };
document.getElementById('rencheck').onclick=function(){ act('/api/maint/rename-check', null, 'ren-msg'); };
document.getElementById('renapply').onclick=function(){ act('/api/maint/rename-apply', 'Appliquer un lot de renommage (max 200 fichiers, EN PLACE sur le NAS) ? Reversible via Annuler.', 'ren-msg'); };
document.getElementById('renundo').onclick=function(){ act('/api/maint/rename-undo', 'Annuler le dernier lot de renommage ?', 'ren-msg'); };
document.getElementById('reclcheck').onclick=function(){ act('/api/maint/reclass-apercu', null, 'recl-msg'); };
document.getElementById('reclapply').onclick=function(){ act('/api/maint/reclass-apply', 'Reclasser les photos personne: en animal: pour les noms d animaux connus, et retirer les fiches en double ? Reversible via Annuler.', 'recl-msg'); };
document.getElementById('reclundo').onclick=function(){ act('/api/maint/reclass-undo', 'Annuler le dernier reclassement ?', 'recl-msg'); };
load(); setInterval(load, 6000);
</script>
</body>
</html>
"""


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


MAP_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Carte des photos</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">
<style>
/* Etape A tokenisation « chambre noire ». Zone definie par l'utilisateur
   (cercle, slider, halo, bouton actif) = fixateur (selection). Popups Leaflet
   sur fond blanc par defaut : texte en tokens papier. Visionneuse plein ecran =
   vrai noir (salle de projection). Structure/espacements inchanges.
   Etape B (10/08) : espacements/rayons/tailles qui EGALENT un token pointent
   vers lui (rendu identique). #4a8c7b des cercles/halo Leaflet (script) RESTE
   en dur : l'API Leaflet n'accepte pas var(). Blancs/noirs translucides de la
   visionneuse plein ecran laisses tels quels (overlays, hors palette tokens).
   Passe DESIGN (11/08) : valeurs hors echelle calees sur les tokens, memes
   mappings que PEOPLE/PETS (0.8-0.82rem -> --t-sm, 0.78rem -> --t-xs,
   0.9/1rem -> --t-md, radius 8px -> --r-md, gaps/paddings -> echelle 4px).
   Positions et tailles fixes (130px, 220px, top/right, 34%) non tokenisees.
   Recherche (11/08) : meme vocabulaire que la galerie (noms + lieux + sens,
   /api/search) ; le champ filtre les marqueurs, la zone/diaporama composent. */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--f-texte);
       background: var(--salle); color: var(--texte);
       height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
.bar { display: flex; align-items: center; gap: var(--e-3); padding: var(--e-3) var(--e-4);
       background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; flex: 0 0 auto; }
.bar a { color: var(--texte); text-decoration: none; font-size: var(--t-md); }
.bar .sp { margin-left: auto; }
.count { color: var(--graphite); font-size: var(--t-sm); }
.tb { padding: var(--e-2) var(--e-3); border: var(--trait); border-radius: var(--r-md);
      background: var(--salle-3); color: var(--texte); font-size: var(--t-sm); cursor: pointer; }
#q { flex: 0 1 240px; min-width: 130px; padding: var(--e-2) var(--e-3); border: var(--trait);
     border-radius: var(--r-pill); background: var(--salle-3); color: var(--texte);
     font-size: var(--t-sm); font-family: inherit; }
#q::placeholder { color: var(--graphite); }
#map { flex: 1 1 auto; min-height: 0; background: var(--salle-3); }
#empty { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
         max-width: 420px; padding: var(--e-6); text-align: center; color: var(--graphite); display: none; }
.leaflet-popup-content { margin: var(--e-2) var(--e-3); }
.pop img { width: 220px; max-width: 60vw; height: auto; border-radius: var(--r-md);
           display: block; background: var(--salle-3); }
.pop .fn { font-size: var(--t-sm); color: var(--texte-papier); margin-top: var(--e-2); word-break: break-word; }
.pop .fo { font-size: var(--t-xs); margin-top: var(--e-1); }
.pop .fo a { color: var(--texte-papier); text-decoration: none; }
.pop .de { font-size: var(--t-xs); color: var(--graphite-p); margin-top: var(--e-1); font-style: italic; }
.pop .op { display: inline-block; margin-top: var(--e-2); font-size: var(--t-xs); color: var(--texte-papier);
           text-decoration: none; }
/* -- zone + diaporama -- */
.tb.active { background: var(--fixateur); color: #fff; border-color: transparent; }
#zctrls { display: flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }
#zctrls.hidden { display: none; }
#zrad { width: 130px; accent-color: var(--fixateur); }
#zinfo { font-size: var(--t-sm); color: var(--graphite); min-width: 118px; }
#zcount { font-size: var(--t-sm); color: var(--texte); font-weight: 600; }
#zhint { position: fixed; bottom: 26px; left: 50%; transform: translateX(-50%); z-index: 500;
  background: rgba(20,18,15,.9); border: var(--trait); color: var(--texte); padding: var(--e-2) var(--e-4);
  border-radius: var(--r-pill); font-size: var(--t-sm); display: none; }
.zcircle-mk { filter: drop-shadow(0 0 4px var(--fixateur)); }
#show { position: fixed; inset: 0; background: #000; display: none; z-index: 1000; }
#show.on { display: block; }
#show img { position: absolute; inset: 0; margin: auto; max-width: 100%; max-height: 100%; object-fit: contain; }
#show .x { position: absolute; top: 12px; right: 18px; font-size: 34px; color: #fff; cursor: pointer;
  z-index: 3; line-height: 1; text-shadow: 0 1px 4px #000; }
#show .nav { position: absolute; top: 0; bottom: 0; width: 34%; z-index: 1; cursor: pointer; }
#show .nav.l { left: 0; } #show .nav.r { right: 0; }
#show .meta { position: absolute; left: 0; right: 0; bottom: 0; z-index: 2; padding: var(--e-4);
  background: linear-gradient(transparent, #000d); color: var(--texte); font-size: var(--t-sm);
  display: flex; gap: var(--e-3); align-items: center; }
#show .meta .sp { flex: 1; }
#show .cbtn { background: #ffffff1a; border: 1px solid #ffffff40; color: #fff; border-radius: var(--r-md);
  padding: var(--e-2) var(--e-3); cursor: pointer; font-size: var(--t-md); }
#show .cbtn:hover { background: #ffffff30; }
#show #show-name { color: var(--graphite); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 40vw; }
</style>
</head>
<body>
<!--APPNAV-->
<div class="bar">
  <input type="search" id="q" placeholder="Rechercher (noms, lieux, sens)&hellip;"
         aria-label="Rechercher des photos sur la carte (noms, lieux, sens de l'image)">
  <span class="count" id="cnt">Chargement&hellip;</span>
  <button class="tb" id="zone">&#128205; D&eacute;finir une zone</button>
  <span id="zctrls" class="hidden">
    <input type="range" id="zrad" min="0" max="100" value="35">
    <span id="zinfo">rayon</span>
    <span id="zcount">0 photo</span>
    <select class="tb" id="zmode" title="Mode du diaporama">
      <option value="seq">Chronologique</option>
      <option value="rand">Al&eacute;atoire</option>
      <option value="assoc">Association</option>
    </select>
    <button class="tb active" id="zplay">&#9654; Diaporama</button>
    <button class="tb" id="zclear" title="Effacer la zone">&#10005;</button>
  </span>
  <span class="sp"></span>
  <button class="tb" id="fit">Recentrer</button>
</div>
<div id="zhint">Appuie sur la carte et fais glisser pour d&eacute;finir le centre puis le rayon</div>
<div id="map"></div>
<div id="empty">Aucune photo géolocalisée pour l'instant.<br><br>
  Le serveur lit les coordonnées GPS des photos en tâche de fond au démarrage
  (backfill). Reviens dans quelques minutes, ou tague de nouvelles photos
  prises avec la géolocalisation activée.</div>

<div id="show">
  <span class="x" onclick="showClose()">&times;</span>
  <div class="nav l" onclick="showStep(-1)"></div>
  <div class="nav r" onclick="showStep(1)"></div>
  <img id="show-img" src="" alt="">
  <div class="meta">
    <button class="cbtn" onclick="showStep(-1)" title="Précédent">&#9198;</button>
    <button class="cbtn" id="show-pp" onclick="showToggle()" title="Pause/Lecture">&#9208;</button>
    <button class="cbtn" onclick="showStep(1)" title="Suivant">&#9197;</button>
    <span id="show-pos"></span>
    <span class="sp"></span>
    <span id="show-name"></span>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
var map = L.map('map', { preferCanvas: true }).setView([46.8, 8.2], 4);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap'
}).addTo(map);
var cluster = L.markerClusterGroup({ chunkedLoading: true, maxClusterRadius: 50 });
map.addLayer(cluster);
// La carte est dimensionnée par flexbox : on force Leaflet à recalculer sa
// taille après la mise en page (sinon tuiles/centrage peuvent être décalés).
setTimeout(function(){ map.invalidateSize(); }, 150);
window.addEventListener('resize', function(){ map.invalidateSize(); });
var bounds = null;
var ALL = [];        // toutes les photos géolocalisées

// Vignettes serveur (audit O1) : les popups et le diaporama de zone chargeaient
// les ORIGINAUX (2-6 Mo/photo sur le NAS). /api/thumb redirige vers l'original
// s'il ne sait pas produire la vignette — aucun cas particulier ici.
function mapThumb(p, s){
  if (!p || !p.key) return p ? p.url : '';
  return '/api/thumb?key=' + encodeURIComponent(p.key) + '&s=' + (s || 512);
}
var PTS = [];        // sous-ensemble affiché (filtre de recherche appliqué)
var FILTER_Q = '';   // requête active, '' = pas de filtre

function esc(s) {
  return (s || '').replace(/[&<>"]/g, function(c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  });
}

// Rendu (ré)appliqué à chaque changement de filtre. La zone et le diaporama
// travaillent sur PTS : ils composent donc naturellement avec la recherche
// (« Luna à Bremblens » puis zone puis diaporama).
function render(pts){
  PTS = pts;
  cluster.clearLayers();
  var latlngs = [];
  pts.forEach(function(p){
    var m = L.marker([p.lat, p.lon]);
    var html = '<div class="pop">' +
      '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">' +
      '<img loading="lazy" src="' + esc(mapThumb(p, 512)) + '"></a>' +
      '<div class="fn">' + esc(p.name) + '</div>' +
      (p.lieu ? '<div class="fo">📍 ' + esc(p.lieu) + '</div>' : '') +
      '<div class="fo">📁 <a href="' + esc(p.gurl) + '">' + esc(p.folder) + '</a></div>' +
      (p.desc ? '<div class="de">' + esc(p.desc) + '</div>' : '') +
      '<a class="op" href="' + esc(p.url) + '" target="_blank" rel="noopener">' +
      'Ouvrir l\\'image ↗</a></div>';
    m.bindPopup(html, { minWidth: 220, maxWidth: 300 });
    cluster.addLayer(m);
    latlngs.push([p.lat, p.lon]);
  });
  bounds = latlngs.length ? L.latLngBounds(latlngs) : null;
  if (bounds) map.fitBounds(bounds, { padding: [40, 40] });
  var s = pts.length > 1 ? 's' : '';
  document.getElementById('cnt').textContent = FILTER_Q
    ? pts.length + ' / ' + ALL.length + ' photo' + s + ' — « ' + FILTER_Q + ' »'
    : pts.length + ' photo' + s + ' géolocalisée' + s;
  recompute();   // la zone éventuelle recompte sur le sous-ensemble affiché
}

fetch('/api/geo').then(function(r){ return r.json(); }).then(function(d){
  ALL = d.points || [];
  if (!ALL.length) {
    document.getElementById('cnt').textContent = '0 photo géolocalisée';
    document.getElementById('empty').style.display = 'block';
    return;
  }
  render(ALL);
}).catch(function(e){
  document.getElementById('cnt').textContent = 'Erreur de chargement';
});

document.getElementById('fit').onclick = function(){
  if (bounds) map.fitBounds(bounds, { padding: [40, 40] });
};

/* ===== Recherche : même vocabulaire que la galerie (noms + lieux + sens) =====
   /api/search rend les mêmes urls que /api/geo (_url_for_key) : on filtre les
   marqueurs par appartenance, sans dupliquer la logique côté client. */
var qEl = document.getElementById('q');
function doSearch(){
  var q = qEl.value.trim();
  if (!q){ FILTER_Q = ''; render(ALL); return; }
  fetch('/api/search?q=' + encodeURIComponent(q) + '&n=1500')
    .then(function(r){ return r.json(); })
    .then(function(d){
      var urls = {};
      (d.results || []).forEach(function(x){ urls[x.url] = 1; });
      FILTER_Q = q;
      render(ALL.filter(function(p){ return urls[p.url]; }));
    })
    .catch(function(){
      document.getElementById('cnt').textContent = 'Recherche indisponible';
    });
}
qEl.addEventListener('keydown', function(e){
  if (e.key === 'Enter') doSearch();
  else if (e.key === 'Escape'){ qEl.value = ''; doSearch(); }
});
qEl.addEventListener('search', doSearch);   // croix native du champ type=search

/* ===== Zone : point + rayon (clic-glissé, souris + tactile) ===== */
var zoneOn = false, center = null, circle = null, cmark = null, inZone = [], drawing = false;
var R_MIN = 100, R_MAX = 100000;   // rayon : 100 m … 100 km

function sliderToR(v){ return Math.round(R_MIN * Math.pow(R_MAX / R_MIN, v/100)); }
function rToSlider(r){ r = Math.max(R_MIN, Math.min(R_MAX, r)); return 100 * Math.log(r/R_MIN) / Math.log(R_MAX/R_MIN); }
function radiusM(){ return sliderToR(+document.getElementById('zrad').value); }
function fmtDist(m){ return m >= 1000 ? (m/1000).toFixed(m < 10000 ? 1 : 0) + ' km' : Math.round(m) + ' m'; }
function hav(a, b){
  var R = 6371000, t = Math.PI/180;
  var dLat = (b[0]-a[0])*t, dLon = (b[1]-a[1])*t, la1 = a[0]*t, la2 = b[0]*t;
  var x = Math.sin(dLat/2)*Math.sin(dLat/2) + Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)*Math.sin(dLon/2);
  return 2*R*Math.asin(Math.min(1, Math.sqrt(x)));
}

var mapEl = document.getElementById('map');

document.getElementById('zone').onclick = function(){ setArmed(!zoneOn); };

function setArmed(on){
  zoneOn = on;
  document.getElementById('zone').classList.toggle('active', on);
  document.getElementById('zhint').style.display = (on && !center) ? 'block' : 'none';
  mapEl.style.cursor = on ? 'crosshair' : '';
  mapEl.style.touchAction = on ? 'none' : '';   // laisse passer le glissé tactile
  if (on) map.dragging.disable(); else map.dragging.enable();
}

function placeCircle(ll){
  center = [ll.lat, ll.lng];
  document.getElementById('zhint').style.display = 'none';
  if (!circle){
    circle = L.circle(ll, { radius: radiusM(), color: '#4A8C7B', weight: 2, fillColor: '#4A8C7B', fillOpacity: 0.12 }).addTo(map);  /* --fixateur (zone selectionnee) */
    cmark = L.marker(ll, { draggable: true }).addTo(map);
    cmark.on('drag', function(ev){ center = [ev.latlng.lat, ev.latlng.lng]; circle.setLatLng(ev.latlng); recompute(); });
  } else { circle.setLatLng(ll); cmark.setLatLng(ll); }
  document.getElementById('zctrls').classList.remove('hidden');
  recompute();
}

function setRadiusFromMeters(r){
  r = Math.max(R_MIN, Math.min(R_MAX, Math.round(r)));
  document.getElementById('zrad').value = rToSlider(r);
  if (circle) circle.setRadius(r);
  recompute();
}

function evLatLng(ev){
  var rect = mapEl.getBoundingClientRect();
  return map.containerPointToLatLng(L.point(ev.clientX - rect.left, ev.clientY - rect.top));
}
// clic/tap-glissé : pose le centre au contact, puis étire le rayon en glissant
mapEl.addEventListener('pointerdown', function(ev){
  if (!zoneOn) return;
  drawing = true;
  try { mapEl.setPointerCapture(ev.pointerId); } catch(e){}
  placeCircle(evLatLng(ev));
  ev.preventDefault();
}, true);
mapEl.addEventListener('pointermove', function(ev){
  if (!drawing || !zoneOn || !center) return;
  var ll = evLatLng(ev);
  setRadiusFromMeters(hav(center, [ll.lat, ll.lng]));
  ev.preventDefault();
}, true);
function endDraw(ev){
  if (!drawing) return;
  drawing = false;
  try { mapEl.releasePointerCapture(ev.pointerId); } catch(e){}
  setArmed(false);   // fin du geste : on rend la carte à la navigation normale
}
mapEl.addEventListener('pointerup', endDraw, true);
mapEl.addEventListener('pointercancel', endDraw, true);

document.getElementById('zrad').oninput = function(){ if (circle) circle.setRadius(radiusM()); recompute(); };

function recompute(){
  var r = radiusM();
  inZone = center ? PTS.filter(function(p){ return hav(center, [p.lat, p.lon]) <= r; }) : [];
  document.getElementById('zinfo').textContent = 'rayon ' + fmtDist(r);
  document.getElementById('zcount').textContent = inZone.length + ' photo' + (inZone.length > 1 ? 's' : '');
  var pb = document.getElementById('zplay');
  pb.disabled = !inZone.length; pb.style.opacity = inZone.length ? 1 : 0.5;
}

document.getElementById('zclear').onclick = function(){
  if (circle){ map.removeLayer(circle); map.removeLayer(cmark); circle = cmark = null; }
  center = null; inZone = [];
  document.getElementById('zctrls').classList.add('hidden');
  setArmed(false);
};

/* ordres de lecture */
function shuffle(a){ a = a.slice(); for (var i=a.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=a[i]; a[i]=a[j]; a[j]=t; } return a; }
function seqOrder(a){ return a.slice().sort(function(x,y){ return (y.taken||0) - (x.taken||0); }); }
function assocOrder(a){
  if (a.length < 3) return a.slice();
  var pool = a.slice(), out = [];
  var cur = pool.splice(Math.floor(Math.random()*pool.length), 1)[0]; out.push(cur);
  while (pool.length){
    var ck = cur.kw || [], bi = 0, bs = -1;
    for (var i=0;i<pool.length;i++){
      var s = 0, kw = pool[i].kw || [];
      for (var j=0;j<kw.length;j++){ if (ck.indexOf(kw[j]) >= 0) s++; }
      if (s > bs){ bs = s; bi = i; }
    }
    cur = pool.splice(bi, 1)[0]; out.push(cur);
  }
  return out;
}

document.getElementById('zplay').onclick = function(){
  if (!inZone.length) return;
  var mode = document.getElementById('zmode').value;
  var list = mode === 'rand' ? shuffle(inZone) : mode === 'assoc' ? assocOrder(inZone) : seqOrder(inZone);
  showStart(list);
};

/* ===== Diaporama plein écran ===== */
var SHOW = { list: [], i: 0, timer: null, playing: false };
function showStart(list){
  SHOW.list = list; SHOW.i = 0; SHOW.playing = true;
  document.getElementById('show').classList.add('on');
  document.getElementById('show-pp').innerHTML = '&#9208;';
  showRender(); showTick();
}
function showRender(){
  var p = SHOW.list[SHOW.i];
  document.getElementById('show-img').src = mapThumb(p, 1600);
  document.getElementById('show-pos').textContent = (SHOW.i+1) + ' / ' + SHOW.list.length;
  document.getElementById('show-name').textContent = p.name;
}
function showTick(){ clearTimeout(SHOW.timer); if (SHOW.playing) SHOW.timer = setTimeout(function(){ showStep(1); }, 4500); }
function showStep(d){ if (!SHOW.list.length) return; SHOW.i = (SHOW.i + d + SHOW.list.length) % SHOW.list.length; showRender(); showTick(); }
function showToggle(){ SHOW.playing = !SHOW.playing; document.getElementById('show-pp').innerHTML = SHOW.playing ? '&#9208;' : '&#9654;'; showTick(); }
function showClose(){ clearTimeout(SHOW.timer); SHOW.playing = false; document.getElementById('show').classList.remove('on'); document.getElementById('show-img').src = ''; }
document.addEventListener('keydown', function(e){
  if (!document.getElementById('show').classList.contains('on')) return;
  if (e.key === 'ArrowLeft') showStep(-1);
  else if (e.key === 'ArrowRight') showStep(1);
  else if (e.key === ' ') { e.preventDefault(); showToggle(); }
  else if (e.key === 'Escape') showClose();
});
// balayage tactile gauche/droite dans le diaporama
(function(){
  var sw = document.getElementById('show'), sx = 0, sy = 0;
  sw.addEventListener('touchstart', function(e){ if (e.touches.length === 1){ sx = e.touches[0].clientX; sy = e.touches[0].clientY; } }, { passive: true });
  sw.addEventListener('touchend', function(e){
    var t = e.changedTouches[0], dx = t.clientX - sx, dy = t.clientY - sy;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.5) showStep(dx < 0 ? 1 : -1);
  }, { passive: true });
})();
</script>
</body>
</html>"""


# ────────────────── Reconnaissance de personnes (Phase 1) ──────────────────
# Détection des visages + calcul d'un « embedding » (vecteur 512D) par visage,
# stockés dans faces_index.json. La mise en correspondance avec des noms
# (Phase 2) se fera à partir de ces vecteurs. Tout est local (GPU si présent).

FACE_APP = None            # instance InsightFace (chargée paresseusement)
FACE_INIT_DONE = False
FACE_ERROR = ""            # message si les dépendances manquent
FACE_PROVIDER = ""         # 'GPU' / 'CPU' effectivement utilisé


_HW_CACHE = {"at": 0.0, "data": None}


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
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        line = (r.stdout or "").strip().splitlines()
        if r.returncode == 0 and line:
            p = [x.strip() for x in line[0].split(",")]
            if len(p) >= 5:
                d["gpu"] = {"name": p[0], "vram_total_mb": int(float(p[1])),
                            "vram_used_mb": int(float(p[2])), "vram_free_mb": int(float(p[3])),
                            "util": int(float(p[4]))}
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


def name_pet_cluster(cid, name):
    """Nomme un groupe d'animaux : voir SubjectStore.name_cluster."""
    return PETS.name_cluster(cid, name)


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
        out.append({"name": nm, "photos": tagcount.get(nm.strip().lower(), 0),
                    "crop": crop})
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


def write_person_tag(path, tag):
    """Ajoute le mot-clé « personne:Nom » dans le fichier (XMP + IPTC), sans
    doublon (-= puis +=) et sans toucher aux autres mots-clés."""
    if not EXIFTOOL:
        return False
    args = ["-overwrite_original", "-q", "-m", "-charset", "filename=UTF8",
            "-codedcharacterset=utf8",
            f"-XMP-dc:Subject-={tag}", f"-XMP-dc:Subject+={tag}",
            f"-IPTC:Keywords-={tag}", f"-IPTC:Keywords+={tag}",
            str(path)]
    try:
        return _run_exiftool(args).returncode == 0
    except Exception:
        return False


def write_person_untag(path, tag):
    """Retire le mot-clé « personne:Nom » du fichier (XMP + IPTC)."""
    if not EXIFTOOL:
        return False
    args = ["-overwrite_original", "-q", "-m", "-charset", "filename=UTF8",
            "-codedcharacterset=utf8",
            f"-XMP-dc:Subject-={tag}", f"-IPTC:Keywords-={tag}", str(path)]
    try:
        return _run_exiftool(args).returncode == 0
    except Exception:
        return False


def person_writer():
    """Écrit/retire les tags personne:Nom dans les fichiers, en série (un seul
    ExifTool à la fois), pour ne pas saturer le NAS."""
    while True:
        item = PERSON_QUEUE.get()
        try:
            path, tag, op = item[0], item[1], item[2]
            key = item[3] if len(item) >= 4 else None
            ok = write_person_untag(path, tag) if op == 'del' else write_person_tag(path, tag)
            # PÉRENNITÉ : après notre propre écriture, on resynchronise le mtime
            # stocké dans l'index avec celui du fichier — sinon le balayage
            # « fichiers modifiés » re-tague la photo et perd le tag nommé.
            if ok and key is not None:
                try:
                    size, mtime = _stat_of(path)
                    e = STORE.data.get(key)
                    if isinstance(e, dict) and mtime is not None:
                        e['mtime'] = mtime
                        if size is not None:
                            e['size'] = size
                except Exception:
                    pass
        except Exception as e:
            print(f"  ⚠ écriture personne {item} : {e}")
        finally:
            PERSON_QUEUE.task_done()


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
    p = _resolve_key(key)
    try:
        if p.is_file():
            PERSON_QUEUE.put((p, tag, op, key))
    except OSError:
        pass


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
        out.append({"name": nm, "photos": tagcount.get(nm.strip().lower(), 0),
                    "crop": crop})
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
         sous-chaine du chemin relatif — EXACTEMENT la logique de _cles_du_lieu,
         pour que /sujets et la barre de recherche parlent des memes lieux.

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
        lieux_norm = [(nk, lbl) for nk, lbl in index.items() if nk]
        for k in list(STORE.data):
            if k in gps_keys:               # le GPS prime : pas de double compte
                continue
            chemin = _sans_accents(_chemin_relatif(k, roots))
            for nk, lbl in lieux_norm:
                if nk in chemin:
                    agg.setdefault(nk, {"name": lbl, "keys": set()})["keys"].add(k)
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
            pidx = {nm: n for n, nm in enumerate(names)}
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
                ptags = set()
                if isinstance(se, dict):
                    for kw in (se.get('kw_fr') or []):
                        if kw.startswith('personne:'):
                            ptags.add(kw[9:])
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
                    if nm in ptags or k in persons[j]["exclude"] or best < CUR_ADD_SIM:
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
                ptags = [kw[9:] for kw in (se.get('kw_fr') or []) if kw.startswith('personne:')]
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
                for nm in ptags:
                    if nm not in pidx:
                        continue
                    p = persons[pidx[nm]]
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


PETS_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Animaux</title>
<style>
  /* Etape A tokenisation « chambre noire ». Anciennes vars nav (--bg/--card/
     --accent...) remplacees par les tokens. Bouton primaire = papier ; danger
     = encre ; intrus selectionne = encre ; focus = veilleuse. Cartes/groupes =
     cellules --salle-3. Structure/espacements inchanges.
     Etape B (10/08) : espacements/rayons qui EGALENT un token pointent vers lui
     (rendu identique). Font-sizes en px laissees (px != rem, non equivalent aux
     tokens --t-*). Noirs/blancs translucides (fonds photo #000, ombres, overlays)
     laisses : hors palette de tokens, non interdits. */
  body{font-family:var(--f-texte);margin:0;background:var(--salle);color:var(--texte);}
  main{padding:var(--e-6) var(--e-4) 90px;max-width:1200px;margin:0 auto;}
  .strip{display:flex;align-items:center;gap:var(--e-4);flex-wrap:wrap;font-size:var(--t-sm);
    color:var(--graphite);background:var(--salle-3);border:var(--trait);
    border-radius:var(--r-md);padding:var(--e-3) var(--e-4);margin-bottom:var(--e-6);}
  .strip b{color:var(--texte);}
  .strip .warn{color:var(--veilleuse);}
  h2{font-size:var(--t-sm);text-transform:uppercase;letter-spacing:.6px;color:var(--graphite);
    margin:var(--e-6) 0 var(--e-4);font-weight:600;}
  .row{display:flex;align-items:center;gap:var(--e-3);}
  /* ancre du lien profond /pets#groupes (onglet Classification de /sujets) */
  #groupes{scroll-margin-top:118px;}
  .sp{flex:1;}
  .btn{padding:var(--e-2) var(--e-4);border-radius:var(--r-md);border:var(--trait);
    background:#ffffff0d;color:var(--texte);cursor:pointer;font-size:var(--t-sm);font-weight:500;
    transition:background .15s;}
  .btn:hover{background:#ffffff1a;}
  .btn.primary{background:var(--papier);
    border:none;color:var(--texte-papier);box-shadow:0 2px 10px #0006;}
  .btn.danger{color:var(--encre);border-color:var(--encre);}
  .btn:disabled{opacity:.5;cursor:default;}
  .cats{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:var(--e-4);}
  .cat{background:var(--salle-3);border:var(--trait);border-radius:var(--r-md);
    padding:var(--e-3);cursor:pointer;text-align:center;transition:transform .12s,border-color .15s;}
  .cat:hover{transform:translateY(-3px);border-color:var(--graphite);}
  .cat .av{width:96px;height:96px;border-radius:50%;object-fit:cover;background:#000;margin:var(--e-1) auto var(--e-3);
    display:block;box-shadow:0 4px 14px #0008;}
  .cat .av.ph{background:#000 url('data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'40\\' height=\\'40\\'><text y=\\'32\\' font-size=\\'32\\'>🐱</text></svg>') center/40px no-repeat;}
  .cat .nm{font-weight:600;font-size:var(--t-md);}
  .cat .ct{color:var(--graphite);font-size:var(--t-xs);margin-top:2px;}
  .groups{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--e-4);}
  .group{background:var(--salle-3);border:var(--trait);border-radius:var(--r-md);padding:var(--e-4);}
  .group .sz{font-size:var(--t-xs);color:var(--graphite);margin-bottom:var(--e-3);}
  .thumbs{display:flex;flex-wrap:wrap;gap:var(--e-1);margin-bottom:var(--e-3);}
  .thumbs img{width:58px;height:58px;object-fit:cover;border-radius:var(--r-md);background:var(--salle-3);}
  /* Rangee de nommage : miroir du .cl .row cote Personnes. flex-wrap + min-width:0
     pour que, dans une carte etroite de la grille (280px), les boutons ne debordent
     PAS a droite (bug : « Rejeter le groupe » masque par la cellule voisine, visible
     seulement sur la derniere carte). Champ pleine largeur, boutons dessous, cibles 44px. */
  .group .nmrow{display:flex;gap:var(--e-2);flex-wrap:wrap;align-items:center;}
  .group .nmrow>*{min-width:0;}
  .group .nmrow .btn{flex:1 1 auto;min-height:44px;}
  .group input{flex:1 1 100%;min-height:44px;padding:var(--e-2) var(--e-3);background:var(--salle-3);color:var(--texte);
    border:var(--trait);border-radius:var(--r-md);font-size:var(--t-sm);}
  .group input:focus{border-color:var(--veilleuse);}
  .muted{color:var(--graphite);font-size:var(--t-sm);}
  /* détail */
  #detail{display:none;}
  .dhead{display:flex;align-items:center;gap:var(--e-4);flex-wrap:wrap;margin-bottom:var(--e-2);}
  .dhead .title{font-size:var(--t-xl);font-weight:700;}
  .dhead .ct{color:var(--graphite);font-size:var(--t-sm);}
  /* menu de mode du diaporama : le rendu natif des <option> heritait un gris
     peu lisible ; on force fond sombre + texte contraste (tokens photo-ui). */
  #d-mode{background:var(--salle-3);color:var(--texte);border:var(--trait);
    border-radius:var(--r-md);padding:var(--e-2) var(--e-3);font-size:var(--t-sm);cursor:pointer;}
  #d-mode:focus{border-color:var(--veilleuse);}
  #d-mode option{background:var(--salle-2);color:var(--texte);}
  .hint{color:var(--graphite);font-size:var(--t-sm);margin:var(--e-2) 0 var(--e-4);line-height:1.5;}
  .photos{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:var(--e-3);}
  .ph{position:relative;border-radius:var(--r-md);overflow:hidden;cursor:pointer;aspect-ratio:1;
    background:#000;border:2px solid transparent;transition:border-color .12s;}
  .ph img{width:100%;height:100%;object-fit:cover;display:block;}
  .ph .sim{position:absolute;left:6px;bottom:6px;font-size:var(--t-xs);padding:2px 6px;border-radius:var(--r-md);
    background:#000a;color:var(--texte);font-weight:600;font-family:var(--f-donnees);}
  .ph .zoom{position:absolute;top:5px;right:5px;width:26px;height:26px;border-radius:var(--r-md);
    background:#000a;color:#fff;border:none;cursor:pointer;font-size:var(--t-sm);line-height:26px;padding:0;}
  .ph.sel{border-color:var(--encre);}
  .ph.sel::after{content:'\\2713';position:absolute;top:5px;left:5px;width:22px;height:22px;
    border-radius:50%;background:var(--encre);color:#fff;font-weight:700;text-align:center;line-height:22px;font-size:var(--t-sm);}
  #selbar{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);display:none;
    align-items:center;gap:var(--e-4);background:rgba(20,18,15,.93);border:var(--trait);
    border-radius:var(--r-pill);padding:var(--e-3) var(--e-4);box-shadow:0 8px 30px #000a;z-index:60;backdrop-filter:blur(8px);}
  #selbar b{color:var(--encre);}
  #lightbox{position:fixed;inset:0;background:#000e;display:none;align-items:center;justify-content:center;
    z-index:80;padding:var(--e-6);}
  #lightbox img{max-width:96vw;max-height:92vh;border-radius:var(--r-md);box-shadow:0 10px 50px #000;}
  #lightbox .x{position:absolute;top:16px;right:22px;font-size:var(--t-xl);color:#fff;cursor:pointer;line-height:1;}
  /* diaporama plein ecran */
  #pshow{position:fixed;inset:0;background:#000;display:none;z-index:90;}
  #pshow.on{display:block;}
  #pshow img{position:absolute;inset:0;margin:auto;max-width:100%;max-height:100%;object-fit:contain;}
  #pshow .x{position:absolute;top:12px;right:18px;font-size:var(--t-xl);color:#fff;cursor:pointer;z-index:3;line-height:1;text-shadow:0 1px 4px #000;}
  #pshow .pnav{position:absolute;top:0;bottom:0;width:34%;z-index:1;cursor:pointer;}
  #pshow .pnav.l{left:0;} #pshow .pnav.r{right:0;}
  #pshow .pmeta{position:absolute;left:0;right:0;bottom:0;z-index:2;padding:var(--e-4);
    background:linear-gradient(transparent,#000d);color:var(--texte);font-size:var(--t-sm);display:flex;gap:var(--e-3);align-items:center;}
  #pshow .pcbtn{background:#ffffff1a;border:1px solid #ffffff40;color:#fff;border-radius:var(--r-md);padding:6px var(--e-3);cursor:pointer;font-size:var(--t-md);}
  #pshow #pshow-name{color:var(--graphite);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:40vw;}
  #pshow #pshow-folder{color:var(--texte);background:var(--salle-3);border:var(--trait);border-radius:var(--r-md);
    padding:var(--e-1) var(--e-3);font-size:var(--t-sm);text-decoration:none;white-space:nowrap;max-width:32vw;
    overflow:hidden;text-overflow:ellipsis;}
  #pshow #pshow-folder:hover{background:var(--salle-2);}
  #pshow #pshow-folder.hidden{display:none;}
</style>
</head>
<body>
<!--APPNAV-->
<!--SUJETSNAV-->
<main>
  <!-- VUE D'ENSEMBLE -->
  <section id="overview">
    <div class="strip" id="strip">Chargement&hellip;</div>

    <!-- Harmonisation avec /people (12/08) : la file « A verifier » des animaux
         vit dans /sujets?vue=classification, a cote de celle des personnes. -->
    <p class="muted" style="margin:0 0 var(--e-3)">Les propositions &agrave; v&eacute;rifier
      (chats reconnus mais incertains, rattachements automatiques &agrave; annuler) se jugent
      dans <a href="/sujets?vue=classification#verifier-animaux" style="color:var(--texte)">Sujets
      &rsaquo; Classification</a>, avec celles des personnes.</p>

    <div class="row"><h2 style="margin:0">Animaux</h2><span class="sp"></span></div>
    <div class="cats" id="named"><span class="muted">Aucun chat nomm&eacute; pour le moment.</span></div>

    <div class="row" style="margin-top:8px"><h2 id="groupes" style="margin:0">Groupes &agrave; identifier</h2>
      <span class="sp"></span>
      <button class="btn" id="recalc">&#8635; Recalculer</button></div>
    <div class="groups" id="clusters"><span class="muted">Chargement des groupes&hellip;</span></div>
  </section>

  <!-- DÉTAIL D'UN CHAT -->
  <section id="detail">
    <div class="dhead">
      <button class="btn" onclick="showOverview()">&#8592; Retour</button>
      <span class="title" id="d-name"></span>
      <span class="ct" id="d-count"></span>
      <select class="btn" id="d-mode" title="Mode du diaporama">
        <option value="seq">Chronologique</option>
        <option value="rnd">Al&eacute;atoire</option>
        <option value="assoc">Association</option>
      </select>
      <button class="btn primary" id="d-play">&#9654; Diaporama</button>
      <span class="sp"></span>
      <button class="btn" id="d-find">&#128269; Rechercher plus</button>
      <button class="btn" id="d-rename">&#9998; Renommer</button>
      <button class="btn danger" id="d-delete">&#128465; Supprimer</button>
    </div>
    <div class="hint">Les photos les <b>moins ressemblantes</b> sont en premier &mdash; ce sont les erreurs probables.
      Clique une photo pour la <b>s&eacute;lectionner</b> (intrus &agrave; retirer), ou l'ic&ocirc;ne &#9974; pour la voir en grand.</div>
    <div class="photos" id="d-photos"></div>
  </section>
</main>

<div id="selbar">
  <span><b id="sel-n">0</b> s&eacute;lectionn&eacute;e(s)</span>
  <button class="btn danger" id="sel-remove">Retirer de ce chat</button>
  <button class="btn" id="sel-clear">Annuler</button>
</div>
<div id="lightbox"><span class="x" onclick="closeLb()">&times;</span><img id="lb-img" src=""></div>

<div id="pshow">
  <span class="x" onclick="pshowClose()">&times;</span>
  <div class="pnav l" onclick="pshowStep(-1)"></div>
  <div class="pnav r" onclick="pshowStep(1)"></div>
  <img id="pshow-img" src="" alt="">
  <div class="pmeta">
    <button class="pcbtn" onclick="pshowStep(-1)" title="Précédent">&#9198;</button>
    <button class="pcbtn" id="pshow-pp" onclick="pshowToggle()" title="Pause/Lecture">&#9208;</button>
    <button class="pcbtn" onclick="pshowStep(1)" title="Suivant">&#9197;</button>
    <span id="pshow-pos"></span><a id="pshow-folder" class="hidden" href="#" title="Ouvrir le dossier d'origine"></a><span class="sp" style="flex:1"></span><span id="pshow-name"></span>
  </div>
</div>

<script>
function esc(s){ return (s||'').replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function post(url,obj){ return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(obj||{})}).then(function(r){return r.json();}); }

var CUR=null, SEL={}, CUR_PHOTOS=[];

function loadStatus(){
  fetch('/api/animals/status').then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById('strip');
    el.innerHTML='Photos analys&eacute;es <b>'+d.photos_processed+'</b>'
      +' &middot; chats d&eacute;tect&eacute;s <b>'+(d.cats||0)+'</b>'
      +' &middot; empreintes calcul&eacute;es <b>'+(d.embedded||0)+'</b>'
      +' &middot; en attente '+d.pending
      // Le moteur DINOv2 se charge PARESSEUSEMENT (au premier besoin) : tant
      // qu'aucune erreur n'est remontee, son absence juste apres un redemarrage
      // est normale — ne pas crier « installe timm » a tort (faux positif vecu).
      +(d.dino_error?' &middot; <span class="warn">moteur d empreintes en erreur : '
          +String(d.dino_error).replace(/[&<>"]/g,'')+' (relance &laquo; 10 - Installer nommage des chats.bat &raquo;)</span>'
        :(d.dino?'':' &middot; moteur d empreintes en veille (charg&eacute; au premier besoin)'));
  });
}

function loadNamed(){
  fetch('/api/pets/list').then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById('named'); var pets=d.pets||[];
    if(!pets.length){ el.innerHTML='<span class="muted">Aucun chat nomm&eacute; pour le moment. Identifie un groupe ci-dessous.</span>'; return; }
    el.innerHTML='';
    pets.forEach(function(p){
      var c=document.createElement('div'); c.className='cat';
      c.innerHTML=(p.crop?'<img class="av" src="'+p.crop+'">':'<div class="av ph"></div>')
        +'<div class="nm">'+esc(p.name)+'</div><div class="ct">'+p.photos+' photo(s)</div>';
      c.onclick=function(){ openCat(p.name); };
      el.appendChild(c);
    });
    // Lien profond depuis /sujets : ?name=X ouvre directement la fiche.
    try{ var _n=new URLSearchParams(location.search).get('name');
      if(_n && pets.some(function(p){return p.name===_n;})){ openCat(_n); } }catch(e){}
  });
}

function loadClusters(rebuild){
  var el=document.getElementById('clusters');
  fetch('/api/pets/clusters'+(rebuild?'?rebuild=1':'')).then(function(r){return r.json();}).then(function(d){
    if(d.building){ el.innerHTML='<span class="muted">Regroupement en cours&hellip;</span>';
      setTimeout(function(){ loadClusters(false); },4000); return; }
    var cl=d.clusters||[];
    if(!cl.length){ el.innerHTML='<span class="muted">Aucun groupe pour l instant (les empreintes se calculent en fond).</span>'; return; }
    el.innerHTML='';
    cl.forEach(function(c){ el.appendChild(carteGroupe(c)); });
  });
}

/* ---- Attribution unifiée ----------------------------------------------
   Une seule action remplace « Nommer » et les rejets : un refus n'est qu'une
   attribution à une cible spéciale. Les vignettes sont sélectionnables, ce
   qui permet de traiter un groupe mixte sans fonction « scinder ». */
var SPECIAUX=[
  {v:'__pas_animal__', t:'Ce n’est pas un animal', d:'peluche, statue, reflet… écarté définitivement'},
  {v:'__pas_animal__', t:'C’est une personne (pas un animal)', d:'humain détecté comme animal — miroir de « C’est un animal » côté Personnes'},
  {v:'__inconnu__',    t:'Animal inconnu',            d:'vrai animal, mais pas un des miens'}
];
var NOMS_CACHE=null, NOMS_CACHE_INFLIGHT=null;
function chargerNoms(){
  if(NOMS_CACHE) return Promise.resolve(NOMS_CACHE);
  // Deduplication : si plusieurs cartes demandent les noms avant la reponse,
  // elles partagent la MEME requete au lieu d'en lancer une chacune (miroir de
  // nomsPersonnes sur /people, qui corrigeait la tempete de /api/names).
  if(NOMS_CACHE_INFLIGHT) return NOMS_CACHE_INFLIGHT;
  NOMS_CACHE_INFLIGHT=fetch('/api/names?genre=animal').then(function(r){return r.json();})
    .then(function(d){ NOMS_CACHE=d.noms||[]; NOMS_CACHE_INFLIGHT=null; return NOMS_CACHE; })
    .catch(function(){ NOMS_CACHE_INFLIGHT=null; return []; });   // pas de rejet non capture
  return NOMS_CACHE_INFLIGHT;
}
function toast(msg, jeton){
  var t=document.getElementById('toast');
  if(!t){ t=document.createElement('div'); t.id='toast';
    t.style.cssText='position:sticky;bottom:12px;margin:12px auto 0;max-width:520px;'+
      'display:flex;align-items:center;gap:12px;background:var(--salle-3);'+
      'border:var(--trait);border-radius:999px;padding:var(--e-3) var(--e-3) var(--e-3) var(--e-4);'+
      'font-size:var(--t-sm);z-index:60;box-shadow:0 8px 30px #000a';
    document.querySelector('main').appendChild(t); }
  t.innerHTML='<span style="flex:1"></span>';
  t.firstChild.textContent=msg;
  if(jeton){ var b=document.createElement('button'); b.className='btn'; b.textContent='Annuler';
    b.onclick=function(){ post('/api/undo',{jeton:jeton}).then(function(){
      t.remove(); loadClusters(true); loadNamed(); }); };
    t.appendChild(b); }
  t.style.display='flex';
  clearTimeout(t._m); t._m=setTimeout(function(){ t.remove(); },10000);
}
function carteGroupe(c){
  var card=document.createElement('div'); card.className='group';
  var membres=c.membres||[];
  var sel=membres.map(function(){return true;});
  var esp=c.species?(' · '+c.species):'';
  card.innerHTML='<div class="sz">'+c.size+' apparition(s)'+esp+
      ' <span style="color:var(--graphite)">— clique pour désélectionner</span></div>'+
    '<div class="thumbs"></div>'+
    '<div class="nmrow"><input placeholder="C’est… (« Inti, Luna » si les deux)" autocomplete="off">'+
    '<button class="btn primary">Attribuer</button>'+
    '<button class="btn danger rejeter">Rejeter le groupe</button>'+
    '<button class="btn archiver" title="Sortir ce groupe de la file, à re-tagger plus tard">Archiver (inconnu)</button></div>'+
    '<div class="props" style="margin-top:6px"></div>';
  var zone=card.querySelector('.thumbs');
  (c.crops||[]).forEach(function(u,i){
    var b=document.createElement('button'); b.type='button';
    b.style.cssText='padding:0;border:none;background:none;cursor:pointer;position:relative;line-height:0';
    b.innerHTML='<img loading="lazy" src="'+esc(u)+'">';
    b.setAttribute('aria-pressed','true');
    b.onclick=function(){ sel[i]=!sel[i]; b.setAttribute('aria-pressed',sel[i]?'true':'false');
      b.style.opacity=sel[i]?'1':'.35'; b.style.outline=sel[i]?'2px solid var(--fixateur)':'none';
      b.style.outlineOffset='-2px'; maj(); };
    b.style.outline='2px solid var(--fixateur)'; b.style.outlineOffset='-2px';
    zone.appendChild(b);
  });
  var inp=card.querySelector('input'), btn=card.querySelector('button.primary');
  var rej=card.querySelector('.rejeter');
  var arch=card.querySelector('.archiver');
  var props=card.querySelector('.props');
  function choisis(){ return membres.filter(function(_m,i){return sel[i];}); }
  function maj(){ btn.textContent='Attribuer '+choisis().length; }
  // « tous » = rejet du groupe entier (miroir de carteGroupeP côté visages) :
  // on n'agit pas sur la sélection mais sur tous les membres.
  function envoyer(cible, tous){
    var m=tous?membres:choisis(); if(!m.length){ inp.focus(); return; }
    // Deux animaux sur la même photo : on accepte plusieurs noms séparés
    // par une virgule ou un « + ». Les deux tags sont posés.
    if(typeof cible==='string' && /[,+]/.test(cible))
      cible=cible.split(/\s*[,+]\s*/).filter(Boolean);
    btn.disabled=true; rej.disabled=true; if(arch) arch.disabled=true;
    post('/api/assign',{genre:'animal',membres:m,cible:cible}).then(function(r){
      btn.disabled=false; rej.disabled=false; if(arch) arch.disabled=false;
      if(!r.ok){ props.textContent=r.erreur||'échec'; return; }
      toast(r.libelle||'fait', r.jeton);
      if(m.length>=membres.length){ card.remove(); } else { loadClusters(true); }
      loadNamed(); loadStatus();
    }).catch(function(){ btn.disabled=false; rej.disabled=false; if(arch) arch.disabled=false;
      props.textContent='Le serveur n a pas repondu. Reessaie dans un instant.'; });
  }
  function listeProps(){
    var t=inp.value.trim().toLowerCase();
    chargerNoms().then(function(noms){
      props.innerHTML='';
      noms.filter(function(p){ return !t || p.nom.toLowerCase().indexOf(t)===0; })
        .slice(0,4).forEach(function(p){
          props.appendChild(prop(p.nom+' · '+p.n+' photos', p.nom)); });
      if(t && !noms.some(function(p){return p.nom.toLowerCase()===t;}))
        props.appendChild(prop('Nouveau : '+inp.value.trim(), inp.value.trim()));
      if(!t) SPECIAUX.forEach(function(s){ props.appendChild(prop(s.t+' — '+s.d, s.v)); });
    });
  }
  function prop(txt,val){
    var b=document.createElement('button'); b.className='btn';
    b.style.cssText='display:block;width:100%;text-align:left;margin:2px 0;font-size:12.5px';
    b.textContent=txt; b.onclick=function(){ envoyer(val); }; return b;
  }
  inp.addEventListener('input',listeProps);
  // Ne PAS peupler les propositions au chargement : chaque /api/names?genre=animal
  // parcourt tout l'index cote serveur ; le faire pour chaque groupe en meme temps
  // saturait le serveur (miroir du correctif /people). On differe au focus / a la
  // frappe : un seul a la fois.
  inp.addEventListener('focus',listeProps);
  inp.addEventListener('keydown',function(e){ if(e.key==='Enter'&&inp.value.trim()) envoyer(inp.value.trim()); });
  btn.onclick=function(){ if(inp.value.trim()) envoyer(inp.value.trim()); else inp.focus(); };
  // Rejeter le groupe entier : vrais animaux mais cluster non nommable
  // (nuques, profils). Réversible via le toast d'annulation. Miroir des visages.
  rej.onclick=function(){ envoyer('__non_group__', true); };
  // Archiver (inconnu) : vrai animal mais pas un des miens. Miroir du bouton
  // cote Personnes ; le backend gere deja __inconnu__ pour genre:animal (SPECIAUX).
  if(arch) arch.onclick=function(){ envoyer('__inconnu__', true); };
  maj();
  return card;
}

/* ---- détail d'un chat ---- */
function showOverview(){ document.getElementById('detail').style.display='none';
  document.getElementById('overview').style.display='block'; CUR=null; clearSel();
  loadNamed(); loadStatus(); }

function openCat(name){
  CUR=name; CUR_PHOTOS=[]; clearSel();
  document.getElementById('overview').style.display='none';
  document.getElementById('detail').style.display='block';
  document.getElementById('d-name').textContent=name;
  document.getElementById('d-count').textContent='chargement…';
  document.getElementById('d-play').disabled=true;
  var g=document.getElementById('d-photos'); g.innerHTML='<span class="muted">Chargement&hellip;</span>';
  window.scrollTo(0,0);
  fetch('/api/pets/photos?name='+encodeURIComponent(name))
    .then(function(r){ if(!r.ok) throw new Error('http '+r.status); return r.json(); })
    .then(function(d){
    if(d.error) throw new Error(d.error);
    var ph=d.photos||[]; CUR_PHOTOS=ph;
    document.getElementById('d-count').textContent=ph.length+' photo(s)';
    document.getElementById('d-play').disabled=!ph.length;
    if(!ph.length){ g.innerHTML='<span class="muted">Aucune photo. Utilise &laquo; Rechercher plus &raquo;.</span>'; return; }
    g.innerHTML='';
    // rendu léger : les vignettes se chargent progressivement (lazy) au défilement
    ph.forEach(function(p){
      var d1=document.createElement('div'); d1.className='ph'; d1.dataset.key=p.key;
      var sim=(p.sim==null?'':'<span class="sim">'+p.sim+'</span>');
      d1.innerHTML='<img loading="lazy" decoding="async" src="'+(p.crop_url||p.url)+'">'+sim
        +'<button class="zoom" title="Voir en grand">&#9974;</button>';
      d1.onclick=function(ev){ if(ev.target.classList.contains('zoom')){ openLb(p.url); return; } toggleSel(d1,p.key); };
      g.appendChild(d1);
    });
  }).catch(function(){
    // Cause la plus frequente : le serveur etait occupe (analyse IA en fond) et
    // la requete a expire. On ne laisse pas un message mort : on propose de
    // reessayer, le geste attendu.
    document.getElementById('d-count').textContent='';
    document.getElementById('d-play').disabled=true;
    g.innerHTML='';
    var w=document.createElement('span'); w.className='muted';
    w.textContent='Chargement interrompu (le serveur est peut-etre occupe). ';
    var b=document.createElement('button'); b.className='btn'; b.textContent='Reessayer';
    b.style.marginLeft='6px'; b.onclick=function(){ openCat(name); };
    w.appendChild(b); g.appendChild(w);
  });
}

/* ---- diaporama d'un chat (chronologique / aléatoire / association) ---- */
// Chronologique = du plus ANCIEN au plus recent (date de prise). Les photos sans
// date fiable (taken absent) vont a la fin plutot qu'au debut.
function seqPhotos(a){ return a.slice().sort(function(x,y){
  return (x.taken||Infinity)-(y.taken||Infinity); }); }
function shufflePhotos(a){ a=a.slice(); for(var i=a.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=a[i];a[i]=a[j];a[j]=t; } return a; }
function assocPhotos(a){
  if(a.length<3) return a.slice();
  var pool=a.slice(), out=[]; var cur=pool.splice(Math.floor(Math.random()*pool.length),1)[0]; out.push(cur);
  while(pool.length){ var ck=cur.kw||[], bi=0, bs=-1;
    for(var i=0;i<pool.length;i++){ var s=0, kw=pool[i].kw||[]; for(var j=0;j<kw.length;j++){ if(ck.indexOf(kw[j])>=0) s++; } if(s>bs){ bs=s; bi=i; } }
    cur=pool.splice(bi,1)[0]; out.push(cur); }
  return out;
}
document.getElementById('d-play').onclick=function(){
  if(!CUR_PHOTOS.length) return;
  var m=document.getElementById('d-mode').value;
  var list=(m==='rnd')?shufflePhotos(CUR_PHOTOS):(m==='assoc')?assocPhotos(CUR_PHOTOS):seqPhotos(CUR_PHOTOS);
  pshowStart(list);
};

/* lecteur plein écran (images complètes, chargées au fil de la lecture) */
var PSHOW={list:[],i:0,timer:null,playing:false};
function pshowStart(list){ if(!list.length) return; PSHOW.list=list; PSHOW.i=0; PSHOW.playing=true;
  document.getElementById('pshow').classList.add('on'); document.getElementById('pshow-pp').innerHTML='&#9208;'; pshowRender(); pshowTick(); }
function pshowRender(){ var p=PSHOW.list[PSHOW.i];
  // Vignettes serveur (audit O1) : 1600 px au lieu de l'original NAS.
  document.getElementById('pshow-img').src=p.key?'/api/thumb?key='+encodeURIComponent(p.key)+'&s=1600':p.url;
  document.getElementById('pshow-pos').textContent=(PSHOW.i+1)+' / '+PSHOW.list.length;
  document.getElementById('pshow-name').textContent=p.name||'';
  var pf=document.getElementById('pshow-folder');
  if(p.gurl){ pf.href=p.gurl; pf.textContent='📁 '+(p.folder||'Dossier'); pf.classList.remove('hidden'); }
  else{ pf.classList.add('hidden'); } }
function pshowTick(){ clearTimeout(PSHOW.timer); if(PSHOW.playing) PSHOW.timer=setTimeout(function(){ pshowStep(1); },4500); }
function pshowStep(d){ if(!PSHOW.list.length) return; PSHOW.i=(PSHOW.i+d+PSHOW.list.length)%PSHOW.list.length; pshowRender(); pshowTick(); }
function pshowToggle(){ PSHOW.playing=!PSHOW.playing; document.getElementById('pshow-pp').innerHTML=PSHOW.playing?'&#9208;':'&#9654;'; pshowTick(); }
function pshowClose(){ clearTimeout(PSHOW.timer); PSHOW.playing=false; document.getElementById('pshow').classList.remove('on'); document.getElementById('pshow-img').src=''; }
document.addEventListener('keydown',function(e){
  if(!document.getElementById('pshow').classList.contains('on')) return;
  if(e.key==='ArrowLeft') pshowStep(-1); else if(e.key==='ArrowRight') pshowStep(1);
  else if(e.key===' '){ e.preventDefault(); pshowToggle(); } else if(e.key==='Escape') pshowClose();
});
(function(){ var sw=document.getElementById('pshow'), sx=0, sy=0;
  sw.addEventListener('touchstart',function(e){ if(e.touches.length===1){ sx=e.touches[0].clientX; sy=e.touches[0].clientY; } },{passive:true});
  sw.addEventListener('touchend',function(e){ var t=e.changedTouches[0], dx=t.clientX-sx, dy=t.clientY-sy;
    if(Math.abs(dx)>45 && Math.abs(dx)>Math.abs(dy)*1.5) pshowStep(dx<0?1:-1); },{passive:true});
})();

function toggleSel(el,key){ if(SEL[key]){ delete SEL[key]; el.classList.remove('sel'); }
  else { SEL[key]=1; el.classList.add('sel'); } updateSelbar(); }
function clearSel(){ SEL={}; document.querySelectorAll('.ph.sel').forEach(function(e){e.classList.remove('sel');}); updateSelbar(); }
function updateSelbar(){ var n=Object.keys(SEL).length; document.getElementById('sel-n').textContent=n;
  document.getElementById('selbar').style.display=n?'flex':'none'; }

document.getElementById('sel-clear').onclick=clearSel;
document.getElementById('sel-remove').onclick=function(){
  var keys=Object.keys(SEL); if(!keys.length||!CUR) return;
  post('/api/pets/untag',{name:CUR,keys:keys}).then(function(){ openCat(CUR); });
};
document.getElementById('d-find').onclick=function(){
  var b=this; b.disabled=true; b.textContent='Recherche…';
  post('/api/pets/find',{name:CUR}).then(function(d){
    var props=d.proposals||[]; b.disabled=false; b.innerHTML='&#128269; Rechercher plus';
    if(!props.length){ alert('Aucune nouvelle photo trouvee.'); return; }
    if(confirm(CUR+' : '+props.length+' photo(s) proposee(s). Toutes les attribuer ?')){
      post('/api/pets/confirm',{name:CUR,keys:props.map(function(p){return p.key;})}).then(function(){ openCat(CUR); });
    }
  });
};
document.getElementById('d-rename').onclick=function(){
  var nn=prompt('Nouveau nom pour '+CUR+' :',CUR); if(!nn||nn===CUR) return;
  post('/api/pets/rename',{old:CUR,new:nn}).then(function(){ openCat(nn); });
};
document.getElementById('d-delete').onclick=function(){
  if(!confirm('Supprimer '+CUR+' ? Le tag sera retire de toutes ses photos.')) return;
  post('/api/pets/delete',{name:CUR}).then(function(){ showOverview(); });
};

function openLb(url){ document.getElementById('lb-img').src=url; document.getElementById('lightbox').style.display='flex'; }
function closeLb(){ document.getElementById('lightbox').style.display='none'; document.getElementById('lb-img').src=''; }
document.getElementById('lightbox').onclick=function(e){ if(e.target.id==='lightbox') closeLb(); };
document.addEventListener('keydown',function(e){ if(e.key==='Escape') closeLb(); });

document.getElementById('recalc').onclick=function(){ post('/api/pets/recluster',{}).then(function(){ loadClusters(false); }); };

loadStatus(); loadNamed(); loadClusters(false);
setInterval(function(){ if(!CUR) loadStatus(); },15000);
// Lien profond /pets#groupes (onglet Classification) : la grille des chats
// nommés au-dessus se peint en async — cible mouvante. Re-viser 2,5 s,
// stop à la première interaction (même remède que /people).
(function(){
  if((location.hash||'')!=='#groupes') return;
  var stop=false, t0=Date.now();
  ['wheel','touchstart','keydown','mousedown'].forEach(function(ev){
    window.addEventListener(ev, function(){ stop=true; }, {passive:true, once:true});
  });
  (function vise(){
    if(stop) return;
    var el=document.getElementById('groupes');
    if(el) el.scrollIntoView({block:'start'});
    if(Date.now()-t0<2500) setTimeout(vise, 400);
  })();
})();
</script>
</body>
</html>"""


FACES_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Visages détectés</title>
<style>
/* Etape A tokenisation « chambre noire ». Grille de visages = planche contact
   (cellules --salle-3). Score de detection = donnee (texte vif). Avertissement
   moteur = encre.
   Passe DESIGN (11/08) : valeurs restantes calees sur les tokens, memes
   mappings que les autres pages (0.9rem -> --t-md, 0.8/0.85rem -> --t-sm,
   0.68rem -> --t-xs, radius 8px -> --r-md, espacements -> echelle 4px). */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--f-texte);
       background: var(--salle); color: var(--texte); }
.bar { display: flex; align-items: center; gap: var(--e-3); padding: var(--e-3) var(--e-4);
       background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; }
.bar a { color: var(--texte); text-decoration: none; font-size: var(--t-md); }
.bar .sp { margin-left: auto; }
#stat { padding: var(--e-3) var(--e-4); background: var(--salle-2); border-bottom: var(--trait);
        color: var(--graphite); font-size: var(--t-sm); line-height: 1.5; }
#stat b { color: var(--texte); }
.warn { color: var(--encre); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: var(--e-2); padding: var(--e-3); }
.face { background: var(--salle-3); border-radius: var(--r-md); overflow: hidden; }
.face a { display: block; }
.face img { width: 100%; aspect-ratio: 1; object-fit: cover; display: block;
            background: var(--salle-3); }
.face .m { padding: var(--e-1) var(--e-2) var(--e-2); font-size: var(--t-xs); color: var(--graphite);
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.face .sc { color: var(--texte); font-family: var(--f-donnees); }
.note { padding: 0 var(--e-4) var(--e-6); color: var(--graphite); font-size: var(--t-sm); line-height: 1.5; }
</style>
</head>
<body>
<!--APPNAV-->
<div class="bar">
  <span class="sp"></span>
  <button onclick="location.reload()" style="padding:6px 12px;border:var(--trait);
    border-radius:8px;background:var(--salle-3);color:var(--texte);cursor:pointer;">Actualiser</button>
</div>
<div id="stat">Chargement&hellip;</div>
<div class="grid" id="grid"></div>
<div class="note">Phase 1 : détection uniquement. Chaque vignette est un visage
  trouvé par l'IA (recadré). Objectif : vérifier que la détection est correcte
  sur tes photos. Le nommage des personnes et l'écriture du tag
  « personne:Nom » arriveront en Phase 2.</div>
<script>
function esc(s){return (s||'').replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
fetch('/api/faces/status').then(function(r){return r.json();}).then(function(s){
  var el = document.getElementById('stat');
  if (!s.engine) {
    el.innerHTML = '<span class="warn">Moteur de reconnaissance non chargé.</span><br>' +
      esc(s.error || '') + '<br>Lance « 7 - Installer reconnaissance visages.bat » ' +
      'puis relance le serveur.';
    return;
  }
  el.innerHTML = 'Moteur : <b>' + esc(s.provider) + '</b> &middot; ' +
    'Photos analysées : <b>' + s.photos_processed + '</b> &middot; ' +
    'Photos avec visage(s) : <b>' + s.photos_with_faces + '</b> &middot; ' +
    'Visages détectés : <b>' + s.total_faces + '</b> &middot; ' +
    'En attente : <b>' + s.pending + '</b>' +
    (s.pending ? ' — l\\'analyse tourne en arrière-plan, actualise dans un moment.' : '') +
    '<br>' + hwLine(s);
}).catch(function(){});
function hwLine(s){
  var h = s.hw || {}, parts = [];
  parts.push('CPU : <b>' + (h.cpu_count || '?') + ' cœurs' +
             (h.cpu_percent != null ? ' · ' + Math.round(h.cpu_percent) + '%' : '') + '</b>');
  if (h.ram_total_gb != null) parts.push('RAM : <b>' + h.ram_avail_gb + ' / ' + h.ram_total_gb + ' Go libres</b>');
  if (h.gpu) parts.push('GPU : <b>' + esc(h.gpu.name) + ' · ' + h.gpu.vram_free_mb + '/' + h.gpu.vram_total_mb + ' Mo libres · ' + h.gpu.util + '%</b>');
  else parts.push('GPU : <b>non détecté</b>');
  parts.push('Ré-embedding : <b>' + (s.reembedded || 0) + ' photos traitées</b>');
  parts.push('Moteur visages : <b>' + esc(s.face_engine_last || 'CPU') + '</b>' +
             (s.gpu_faces_ready ? ' (GPU dispo)' : ''));
  if (!h.psutil) parts.push('<span style="color:var(--graphite)">(installe psutil pour CPU/RAM en direct)</span>');
  return '<span style="color:var(--graphite)">🖥 ' + parts.join(' &middot; ') + '</span>';
}
fetch('/api/faces/list?limit=400').then(function(r){return r.json();}).then(function(d){
  var g = document.getElementById('grid');
  (d.faces || []).forEach(function(f){
    var div = document.createElement('div');
    div.className = 'face';
    div.innerHTML = '<a href="' + esc(f.photo_url) + '" target="_blank" rel="noopener">' +
      '<img loading="lazy" src="' + esc(f.crop_url) + '"></a>' +
      '<div class="m"><span class="sc">' + f.score + '</span> &middot; ' +
      esc(f.name) + '</div>';
    g.appendChild(div);
  });
}).catch(function(){});
// chargement de fond progressif des vignettes (sans attendre le scroll)
var _lq=[], _lqActive=0, _LQ_CONC=4;
function loadQueue(){
  while(_lqActive<_LQ_CONC && _lq.length){
    var el=_lq.shift(); _lqActive++;
    (function(im){
      im.onload=im.onerror=function(){ _lqActive--; im.onload=im.onerror=null; loadQueue(); };
      im.src=im.getAttribute('data-src'); im.removeAttribute('data-src');
    })(el);
  }
}
function bgLoad(){
  document.querySelectorAll('img[loading="lazy"]').forEach(function(el){
    el.removeAttribute('loading');
    if(el.complete && el.naturalWidth>0) return;
    var s=el.getAttribute('src');
    if(s){ el.setAttribute('data-src', s); el.removeAttribute('src'); }
  });
  document.querySelectorAll('img[data-src]').forEach(function(el){ if(_lq.indexOf(el)<0) _lq.push(el); });
  loadQueue();
}
setInterval(bgLoad, 1000);
bgLoad();
</script>
</body>
</html>"""


SUBJECTS_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sujets</title>
<style>
  /* « Sujets » (ROADMAP #4) : ENTREE UNIQUE des entites nommees (personnes,
     animaux, lieux) depuis la fusion — les onglets Personnes/Animaux ont quitte
     la nav ; /people et /pets restent des vues specialisees (files de travail,
     correction), atteintes par la rangee « Files de travail » ci-dessous ou par
     les cartes (?name=). Tout en tokens « chambre noire ». */
  body{font-family:var(--f-texte);margin:0;background:var(--salle);color:var(--texte);}
  main{padding:var(--e-6) var(--e-4) 90px;max-width:1200px;margin:0 auto;}
  h1{font:600 var(--t-xl)/1.1 var(--f-affichage);letter-spacing:-.01em;margin:0 0 var(--e-2);}
  .intro{color:var(--graphite);font-size:var(--t-sm);line-height:1.5;
    margin:0 0 var(--e-6);max-width:62ch;}
  .barre{display:flex;gap:var(--e-3);align-items:center;flex-wrap:wrap;margin-bottom:var(--e-6);}
  .barre input{flex:1;min-width:220px;min-height:var(--touch);padding:0 var(--e-4);
    font:var(--t-md)/1 var(--f-texte);background:var(--salle-3);color:var(--texte);
    border:var(--trait);border-radius:var(--r-md);}
  .barre input::placeholder{color:var(--graphite);}
  .filtres{display:flex;gap:var(--e-2);}
  .chip{min-height:36px;padding:0 var(--e-4);border-radius:var(--r-pill);border:var(--trait);
    background:var(--salle-3);color:var(--graphite);cursor:pointer;
    font:500 var(--t-sm)/1 var(--f-texte);}
  .chip .n{font-family:var(--f-donnees);font-size:var(--t-xs);opacity:.7;margin-left:6px;}
  .chip[aria-pressed="true"]{background:var(--fixateur);border-color:var(--fixateur);color:#fff;}
  .chip[aria-pressed="true"] .n{opacity:.85;}
  .grille{display:grid;
    grid-template-columns:repeat(auto-fill,minmax(clamp(120px,20vw,180px),1fr));
    gap:var(--e-4);}
  .sc{display:flex;flex-direction:column;background:var(--salle-3);border:var(--trait);
    border-radius:var(--r-md);overflow:hidden;text-decoration:none;color:var(--texte);}
  .sc .vig{aspect-ratio:1;background:var(--salle-2);position:relative;overflow:hidden;}
  .sc .vig img{width:100%;height:100%;object-fit:cover;display:block;}
  .sc .vig .ph{width:100%;height:100%;display:flex;align-items:center;
    justify-content:center;font-size:2rem;color:var(--graphite);}
  .sc .badge{position:absolute;top:var(--e-2);left:var(--e-2);background:#000a;
    color:var(--texte);border-radius:var(--r-pill);padding:2px 8px;font-size:var(--t-xs);}
  .sc .meta{padding:var(--e-3);}
  .sc .nm{font:600 var(--t-md)/1.2 var(--f-affichage);letter-spacing:-.01em;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .sc .ct{font-family:var(--f-donnees);font-size:var(--t-xs);color:var(--graphite);margin-top:2px;}
  .msg{color:var(--graphite);padding:var(--e-8) 0;text-align:center;}
  /* Onglet Classification : cartes de files de travail. Compteur en monospace
     (--f-donnees, plancher photo-ui : une mesure se compare) ; > 0 = veilleuse
     (travail en attente), 0 = graphite. Toute la carte est cliquable (cible
     >= 44 px), c'est un lien de navigation (<a>), pas un bouton. */
  .ctype h2{font:600 var(--t-lg)/1.2 var(--f-affichage);letter-spacing:-.01em;
    margin:var(--e-6) 0 var(--e-3);}
  .cgrid{display:grid;gap:var(--e-3);
    grid-template-columns:repeat(auto-fill,minmax(240px,1fr));}
  .qc{display:flex;flex-direction:column;gap:var(--e-1);min-height:var(--touch);
    padding:var(--e-4);background:var(--salle-3);border:var(--trait);
    border-radius:var(--r-md);color:var(--texte);text-decoration:none;}
  .qc .k{font:500 var(--t-md)/1.2 var(--f-texte);}
  .qc .n{font:600 var(--t-xl)/1.1 var(--f-donnees);color:var(--graphite);}
  .qc.attente .n{color:var(--veilleuse);}
  .qc .tv{color:var(--graphite);font-size:var(--t-sm);line-height:1.4;}
  @media(hover:hover){.sc:hover,.qc:hover{border-color:var(--papier-2);}}
  /* Files « À vérifier » incarnées ICI (déplacées de /people, harmonisées
     avec les animaux) : mêmes classes que sur /people (.cl, .row, .qui,
     bande auto .grid/.prop) pour garder un seul vocabulaire visuel. */
  .ctype h3{display:flex;align-items:center;gap:var(--e-2);flex-wrap:wrap;
    font:600 var(--t-md)/1.2 var(--f-affichage);letter-spacing:-.01em;
    margin:var(--e-4) 0 var(--e-2);}
  .ctype h3 .c{color:var(--graphite);font-family:var(--f-donnees);
    font-size:var(--t-sm);font-weight:normal;}
  .qmsg{color:var(--graphite);font-size:var(--t-sm);margin:0 0 var(--e-2);}
  .kbd-hint{color:var(--graphite);font-size:var(--t-xs);font-family:var(--f-donnees);}
  .kbd-hint b{color:var(--texte);font-weight:600;}
  .btn{min-height:var(--touch);padding:var(--e-2) var(--e-4);border:var(--trait);
    border-radius:var(--r-md);background:var(--salle-3);color:var(--texte);
    font:500 var(--t-sm)/1 var(--f-texte);cursor:pointer;}
  .btn.prim{background:var(--papier);border-color:var(--papier);color:var(--texte-papier);}
  .btn.warn{background:transparent;border-color:var(--encre);color:var(--encre);}
  .ctype h3 .btn{min-height:0;font-size:var(--t-xs);padding:var(--e-1) var(--e-2);}
  .cl{background:var(--salle-3);border:var(--trait);border-radius:var(--r-md);
    padding:var(--e-3);margin-bottom:var(--e-3);}
  /* Tri au clavier : la carte « en cours de décision » porte l'anneau veilleuse. */
  .cl.active{outline:2px solid var(--veilleuse);outline-offset:2px;}
  .cl .row{display:flex;gap:var(--e-2);align-items:center;flex-wrap:wrap;}
  .cl .row > *{min-width:0;}
  .cl .row .sz{color:var(--graphite);font-size:var(--t-sm);flex:1 1 12rem;
    margin-right:auto;overflow-wrap:anywhere;}
  .cl .row .qui{flex:1 1 150px;min-width:120px;}
  .cl .row .btn,.cl .row .qui{min-height:44px;}
  @media(max-width:900px){
    .cl .row{align-items:stretch;}
    .cl .row .sz{flex-basis:100%;}
    .cl .row .btn,.cl .row .qui{flex-basis:100%;width:100%;}
    .cl .row > img{align-self:flex-start;}
  }
  input.qui{padding:var(--e-2) var(--e-3);border-radius:var(--r-md);
    border:var(--trait);background:var(--salle-3);color:var(--texte);
    font-size:var(--t-sm);font-family:var(--f-texte);}
  input.qui:focus{border-color:var(--veilleuse);}
  .cl .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));
    gap:var(--e-1);}
  .prop{position:relative;}
  .prop img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:var(--r-md);
    background:var(--salle-3);display:block;}
  .prop .s{position:absolute;bottom:2px;right:4px;font-size:var(--t-xs);
    font-family:var(--f-donnees);color:var(--texte);background:rgba(0,0,0,.55);
    padding:0 3px;border-radius:var(--r-sm);}
  .prop .x{position:absolute;top:3px;right:4px;background:var(--encre);color:#fff;
    border:none;border-radius:var(--r-sm);font-size:var(--t-xs);padding:1px 5px;
    cursor:pointer;}
  .ctype .cgrid{margin-top:var(--e-3);}
  .btn:focus-visible,input.qui:focus-visible,.qc:focus-visible,.sc:focus-visible{
    outline:2px solid var(--veilleuse);outline-offset:2px;}
  /* Ancres des files : la nav (app + sous-nav Sujets, sticky) ne doit pas
     recouvrir le titre quand scrollIntoView l'amene en haut. */
  #verifier,#verifier-animaux{scroll-margin-top:118px;}
  @media(prefers-reduced-motion:reduce){
    *,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;}
  }
</style>
</head>
<body>
<!--APPNAV-->
<!--SUJETSNAV-->
<main>
  <h1>Sujets</h1>
  <div id="vue-annuaire">
  <p class="intro">Toutes les personnes, les animaux et les lieux, au m&ecirc;me endroit.
    Ouvre une personne ou un animal pour sa fiche compl&egrave;te (photos, correction,
    renommage) ; un lieu ouvre la galerie filtr&eacute;e sur ce lieu. Le travail en
    attente (&agrave; v&eacute;rifier, groupes &agrave; nommer) vit dans l&rsquo;onglet
    <a href="/sujets?vue=classification" style="color:var(--texte)">Classification</a>.</p>
  <div class="barre">
    <input id="q" type="search" placeholder="Filtrer par nom&hellip;" autocomplete="off"
      aria-label="Filtrer les sujets par nom">
    <div class="filtres" role="group" aria-label="Type de sujet">
      <button class="chip" data-f="tous" aria-pressed="true">Tous<span class="n" id="n-tous"></span></button>
      <button class="chip" data-f="personne" aria-pressed="false">Personnes<span class="n" id="n-personne"></span></button>
      <button class="chip" data-f="animal" aria-pressed="false">Animaux<span class="n" id="n-animal"></span></button>
      <button class="chip" data-f="lieu" aria-pressed="false">Lieux<span class="n" id="n-lieu"></span></button>
    </div>
  </div>
  <div class="grille" id="grille"></div>
  <div class="msg" id="msg">Chargement&hellip;</div>
  </div>

  <!-- Onglet Classification : GUICHET UNIQUE du travail en attente. Les files
       « À vérifier » (personnes ET animaux, harmonisées) se jugent ICI —
       déplacées de /people le 12/08 ; les cartes restantes ouvrent les vues
       spécialisées (groupes, inconnus) par lien profond ancré. -->
  <div id="vue-classif" hidden>
  <p class="intro">Le travail de classification en attente, s&eacute;par&eacute; par type.
    Les propositions &laquo;&nbsp;&Agrave; v&eacute;rifier&nbsp;&raquo; se jugent ici m&ecirc;me
    (personnes et animaux) ; les cartes ouvrent directement la bonne section.</p>
  <div class="qmsg"><span class="kbd-hint">Raccourcis : <b>Espace</b>/<b>Entr&eacute;e</b> = oui &middot; <b>X</b> = non &middot; <b>Z</b> = annuler &middot; une lettre = corriger le nom</span></div>
  <div class="qmsg" id="curstats" hidden><span class="kbd-hint" id="curstats-txt"></span></div>
  <section class="ctype" aria-labelledby="ct-p">
    <h2 id="ct-p">&#128100; Personnes</h2>
    <h3 id="verifier">&Agrave; v&eacute;rifier <span class="c" id="curc"></span>
      <button class="btn" id="curref">&#8635; Rafra&icirc;chir</button></h3>
    <div class="qmsg" id="curmsg">Chargement&hellip;</div>
    <div id="autowrap"></div>
    <div id="curbox"></div>
    <div class="cgrid" id="c-personnes"></div>
  </section>
  <section class="ctype" aria-labelledby="ct-a">
    <h2 id="ct-a">&#128062; Animaux</h2>
    <h3 id="verifier-animaux">&Agrave; v&eacute;rifier <span class="c" id="petcurc"></span>
      <button class="btn" id="petcurref">&#8635; Rafra&icirc;chir</button></h3>
    <div class="qmsg" id="petcurmsg">Chargement&hellip;</div>
    <div id="petautowrap"></div>
    <div id="petcurbox"></div>
    <div class="cgrid" id="c-animaux"></div>
  </section>
  <section class="ctype" aria-labelledby="ct-l">
    <h2 id="ct-l">&#128205; Lieux</h2>
    <div class="cgrid" id="c-lieux"></div>
  </section>
  </div>
</main>
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function _norm(s){return String(s||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'');}
var ALL=[], FILT='tous';
function href(s){
  // Personne/animal -> fiche detail (?name=) ; lieu -> galerie filtree (?q=),
  // qui gere deja le filtrage par lieu (semantic_search / _extraire_lieux).
  if(s.type==='lieu') return '/files?q='+encodeURIComponent(s.name);
  return (s.type==='animal'?'/pets':'/people')+'?name='+encodeURIComponent(s.name);
}
function typeMot(t){return t==='animal'?'animal':t==='lieu'?'lieu':'personne';}
function carte(s){
  var badge=s.type==='animal'?'\\ud83d\\udc3e':s.type==='lieu'?'\\ud83d\\udccd':'\\ud83d\\udc64';
  var vig=s.crop
    ? '<img loading="lazy" src="'+esc(s.crop)+'" alt="">'
    : '<div class="ph" aria-hidden="true">'+badge+'</div>';
  var a=document.createElement('a');
  a.className='sc'; a.href=href(s);
  a.setAttribute('aria-label', s.name+' — '+s.photos+' photo'+(s.photos>1?'s':'')+
    ' ('+typeMot(s.type)+')');
  a.innerHTML='<div class="vig">'+vig+'<span class="badge" aria-hidden="true">'+badge+'</span></div>'+
    '<div class="meta"><div class="nm">'+esc(s.name)+'</div>'+
    '<div class="ct">'+s.photos+' photo'+(s.photos>1?'s':'')+'</div></div>';
  return a;
}
function rendre(){
  var q=_norm(document.getElementById('q').value.trim());
  var list=ALL.filter(function(s){
    if(FILT!=='tous' && s.type!==FILT) return false;
    if(q && _norm(s.name).indexOf(q)<0) return false;
    return true;
  });
  var g=document.getElementById('grille'), m=document.getElementById('msg');
  g.innerHTML='';
  if(!list.length){ m.textContent=ALL.length?'Aucun sujet ne correspond au filtre.':'Aucun sujet nomm\\u00e9 pour le moment.'; return; }
  m.textContent='';
  var frag=document.createDocumentFragment();
  list.forEach(function(s){ frag.appendChild(carte(s)); });
  g.appendChild(frag);
}
document.querySelectorAll('.chip').forEach(function(c){
  c.onclick=function(){
    FILT=c.getAttribute('data-f');
    document.querySelectorAll('.chip').forEach(function(x){
      x.setAttribute('aria-pressed', x===c?'true':'false'); });
    rendre();
  };
});
document.getElementById('q').addEventListener('input', rendre);

// ── Bascule Annuaire / Classification (?vue=classification) ──
var VUE=(new URLSearchParams(location.search).get('vue')==='classification')?'classif':'annuaire';
if(VUE==='classif'){
  document.getElementById('vue-annuaire').hidden=true;
  document.getElementById('vue-classif').hidden=false;
  chargerClassif();
}
// Pré-sélection d'un type dans l'annuaire (?type=lieu depuis Classification).
var TYPEQ=new URLSearchParams(location.search).get('type');
if(VUE==='annuaire' && ['personne','animal','lieu'].indexOf(TYPEQ)>=0){
  FILT=TYPEQ;
  document.querySelectorAll('.chip').forEach(function(x){
    x.setAttribute('aria-pressed', x.getAttribute('data-f')===TYPEQ?'true':'false'); });
}

function qcarte(cible, opts){
  // Carte de file de travail : lien vers la section de la vue specialisee.
  var a=document.createElement('a');
  a.className='qc'; a.href=opts.href;
  a.innerHTML='<span class="k">'+esc(opts.titre)+'</span>'+
    '<span class="n">&hellip;</span>'+
    '<span class="tv">'+esc(opts.desc)+'</span>';
  document.getElementById(cible).appendChild(a);
  return a;
}
function qmaj(a, n, building, extra, neutre){
  var el=a.querySelector('.n');
  el.textContent = building ? 'calcul\\u2026' : String(n);
  // veilleuse = « travail en attente » ; un simple compte (lieux) reste neutre
  a.classList.toggle('attente', !neutre && !building && n>0);
  if(extra){ var tv=a.querySelector('.tv'); tv.textContent=tv.textContent+' \\u00b7 '+extra; }
}
function chargerClassif(){
  var cGrp=qcarte('c-personnes',{titre:'Groupes \\u00e0 nommer', href:'/people#groupes',
    desc:'Visages regroup\\u00e9s automatiquement, en attente d\\u2019un nom.'});
  var cInc=qcarte('c-personnes',{titre:'Inconnus (archiv\\u00e9s)', href:'/people#inconnus',
    desc:'Visages mis de c\\u00f4t\\u00e9 \\u2014 r\\u00e9activables pour un re-tri.'});
  var cPets=qcarte('c-animaux',{titre:'Groupes \\u00e0 identifier', href:'/pets#groupes',
    desc:'Chats d\\u00e9tect\\u00e9s regroup\\u00e9s par ressemblance, \\u00e0 nommer.'});
  var cLieux=qcarte('c-lieux',{titre:'Lieux nomm\\u00e9s', href:'/sujets?type=lieu',
    desc:'Lieux reconnus (lieux.txt + dossiers). Le g\\u00e9ocodage GPS (gps_place) s\\u2019active depuis R\\u00e9glages.'});
  function j(u){ return fetch(u).then(function(r){ return r.json(); }); }
  j('/api/people/clusters').then(function(d){ qmaj(cGrp, d.count||0, d.building); })
    .catch(function(){ qmaj(cGrp,'?',false); });
  j('/api/people/inconnus').then(function(d){ qmaj(cInc, d.count||0, d.building); })
    .catch(function(){ qmaj(cInc,'?',false); });
  j('/api/pets/clusters').then(function(d){ qmaj(cPets, (d.clusters||[]).length||d.count||0, d.building); })
    .catch(function(){ qmaj(cPets,'?',false); });
  j('/api/sujets/list').then(function(d){ qmaj(cLieux, (d.lieux||[]).length, false, null, true); })
    .catch(function(){ qmaj(cLieux,'?',false, null, true); });
  loadCurator(false);
  loadPetCurator(false);
}

// ── Files « À vérifier » — DÉPLACÉES de /people, harmonisées animaux (12/08).
//    Personnes : merge/remove/add via /api/curator + /api/assign (genre visage).
//    Animaux : add via /api/assign (genre animal) — « Aucun » = __inconnu__,
//    « Pas un animal » = __pas_animal__, tout est réversible (undo) et
//    journalisé (compteur de séance commun aux deux files). ──
function post(url,obj){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(obj||{})}).then(function(r){return r.json();});}
var NOMS_CACHE={};
function nomsDe(genre){
  // Cache de la PROMESSE (anti-tempête de /api/names, leçon /pets du 11/08).
  if(NOMS_CACHE[genre]) return NOMS_CACHE[genre];
  NOMS_CACHE[genre]=fetch('/api/names?genre='+genre).then(function(r){return r.json();})
    .then(function(d){ return d.noms||[]; })
    .catch(function(){ NOMS_CACHE[genre]=null; return []; });
  return NOMS_CACHE[genre];
}
function toastP(msg, jeton, apres){
  var t=document.getElementById('toastp');
  if(!t){ t=document.createElement('div'); t.id='toastp';
    t.setAttribute('role','status'); t.setAttribute('aria-live','polite');
    t.style.cssText='position:fixed;left:50%;bottom:18px;transform:translateX(-50%);display:flex;'+
      'align-items:center;gap:12px;background:var(--salle-3);border:var(--trait);border-radius:999px;'+
      'padding:var(--e-3) var(--e-3) var(--e-3) var(--e-4);font-size:var(--t-sm);z-index:60';
    document.body.appendChild(t); }
  t.innerHTML='<span style="flex:1"></span>'; t.firstChild.textContent=msg;
  if(jeton){ var b=document.createElement('button'); b.className='btn'; b.textContent='Annuler';
    b.onclick=function(){ post('/api/undo',{jeton:jeton}).then(function(){ t.remove();
        if(apres){ apres(); } else { loadCurator(true); loadPetCurator(true); } }); };
    t.appendChild(b); }
  clearTimeout(t._m); t._m=setTimeout(function(){ t.remove(); },10000);
}
// Compteur de séance : rythme et erreurs découvertes, calculés côté serveur
// (journal des jugements — COMMUN personnes + animaux). Masqué sans geste récent.
function majStats(st){
  var w=document.getElementById('curstats'), t=document.getElementById('curstats-txt');
  if(!w||!t) return;
  if(!st||!st.n){ w.hidden=true; return; }
  var s='S\\u00e9ance : <b>'+st.n+'</b> jugement'+(st.n>1?'s':'');
  if(st.par_minute!=null) s+=' \\u00b7 <b>'+String(st.par_minute).replace('.',',')+'</b>/min';
  s+=' \\u00b7 <b>'+st.erreurs+'</b> erreur'+(st.erreurs>1?'s':'')+' d\\u00e9couverte'+(st.erreurs>1?'s':'');
  t.innerHTML=s; w.hidden=false;
}
function curCount(){
  var n=document.querySelectorAll('#curbox > .cl').length;
  document.getElementById('curc').textContent=n?('('+n+')'):'';
  if(!n) document.getElementById('curmsg').textContent='Rien \\u00e0 v\\u00e9rifier pour le moment.';
}
function petCount(){
  var n=document.querySelectorAll('#petcurbox > .cl').length;
  document.getElementById('petcurc').textContent=n?('('+n+')'):'';
  if(!n) document.getElementById('petcurmsg').textContent='Rien \\u00e0 v\\u00e9rifier pour le moment.';
}
// Une carte ne se juge QU'UNE fois : le retrait n'a lieu qu'au retour du
// serveur, et deux pressions rapides d'Espace (plus rapides que l'aller-retour)
// envoyaient deux jugements pour la même photo. Verrou local, relâché en cas
// d'échec pour que le geste reste rejouable.
function _prend(el){ if(el._jug) return false; el._jug=true; el.style.opacity=.5; return true; }
function _rend(el){ el._jug=false; el.style.opacity=''; }
function assigner(s, el, cible){
  if(!_prend(el)) return;
  post('/api/assign',{genre:'visage',cle:s.key,i:s.i,cible:cible,propose:s.person,
                      sim:s.sim,marge:s.margin})
    .then(function(r){
      if(!r.ok){ _rend(el); toastP(r.erreur||'Echec de l attribution.'); return; }
      if(r.stats) majStats(r.stats);
      toastP(r.libelle||'fait', r.jeton, function(){ loadCurator(true); });
      el.remove(); NOMS_CACHE['personne']=null; curCount(); curMark();
    }).catch(function(){ _rend(el); toastP('Le serveur n a pas repondu. Reessaie dans un instant.'); });
}
function assignerA(s, el, cible){
  if(!_prend(el)) return;
  post('/api/assign',{genre:'animal',membres:[[s.key,s.i]],cible:cible,propose:s.animal,
                      sim:s.sim,marge:s.margin})
    .then(function(r){
      if(!r.ok){ _rend(el); toastP(r.erreur||'Echec de l attribution.'); return; }
      if(r.stats) majStats(r.stats);
      toastP(r.libelle||'fait', r.jeton, function(){ loadPetCurator(true); });
      el.remove(); NOMS_CACHE['animal']=null; petCount(); curMark();
    }).catch(function(){ _rend(el); toastP('Le serveur n a pas repondu. Reessaie dans un instant.'); });
}
function propose2(champ, zone, genre, agir){
  var t=champ.value.trim().toLowerCase();
  nomsDe(genre).then(function(noms){
    zone.innerHTML='';
    noms.filter(function(p){return !t||p.nom.toLowerCase().indexOf(t)===0;})
      .slice(0,4).forEach(function(p){
        var b=document.createElement('button'); b.className='btn';
        b.style.cssText='margin:2px 4px 0 0;font-size:12.5px';
        b.textContent=p.nom+' \\u00b7 '+p.n;
        b.onclick=function(){ agir(p.nom); };
        zone.appendChild(b); });
    if(t && !noms.some(function(p){return p.nom.toLowerCase()===t;})){
      var nb=document.createElement('button'); nb.className='btn';
      nb.style.cssText='margin:2px 4px 0 0;font-size:12.5px';
      nb.textContent='Nouveau : '+champ.value.trim();
      nb.onclick=function(){ agir(champ.value.trim()); };
      zone.appendChild(nb); }
  });
}
function curResolve(action, sug, el){
  if(!_prend(el)) return;
  post('/api/curator/resolve',{action:action,sug:sug}).then(function(r){
    if(r&&r.stats) majStats(r.stats);
    el.remove(); curCount(); curMark();
  }).catch(function(){ _rend(el); toastP('Le serveur n a pas repondu. Reessaie dans un instant.'); });
}
function loadCurator(rebuild){
  fetch('/api/curator/list'+(rebuild?'?rebuild=1':'')).then(function(r){return r.json();}).then(function(d){
    var msg=document.getElementById('curmsg'), box=document.getElementById('curbox');
    majStats(d.stats||null);
    if(d.building){ msg.textContent='Analyse des visages en cours\\u2026'; box.innerHTML=''; setTimeout(function(){loadCurator(false);},4000); return; }
    var auto=d.auto||[], aw=document.getElementById('autowrap');
    if(!auto.length){ aw.innerHTML=''; }
    else{
      var ah='<div class="cl"><div style="font-size:var(--t-sm);color:var(--graphite);margin-bottom:var(--e-2)">\\ud83e\\udd16 Ajout\\u00e9s automatiquement r\\u00e9cemment ('+auto.length+') \\u2014 v\\u00e9rifie, annule (\\u2717) en cas d\\u2019erreur :</div><div class="grid">';
      auto.forEach(function(a){
        ah+='<label class="prop" style="cursor:default"><a href="'+esc(a.url)+'" target="_blank" rel="noopener"><img loading="lazy" src="'+esc(a.crop_url)+'" alt=""></a>'+
          '<span class="s">'+esc(a.person)+' '+a.sim+'</span>'+
          '<button class="x" title="Annuler" data-p="'+esc(a.person)+'" data-k="'+esc(a.key)+'">\\u2717</button></label>';
      });
      ah+='</div></div>'; aw.innerHTML=ah;
      aw.querySelectorAll('button.x').forEach(function(b){
        b.onclick=function(){
          var p=b.getAttribute('data-p'), k=b.getAttribute('data-k'), cell=b.closest('.prop');
          cell.style.opacity=.4;
          post('/api/people/untag',{name:p,keys:[k]}).then(function(){ cell.remove(); });
        };
      });
    }
    var items=d.items||[];
    document.getElementById('curc').textContent=items.length?('('+items.length+')'):'';
    if(!items.length){ msg.textContent=auto.length?'':'Rien \\u00e0 v\\u00e9rifier pour le moment.'; box.innerHTML=''; curMark(); return; }
    msg.textContent='';
    box.innerHTML='';
    items.forEach(function(s){
      var el=document.createElement('div'); el.className='cl'; var html='';
      var crop='<img loading="lazy" src="'+esc(s.crop_url)+'" style="width:80px;height:80px;object-fit:cover;border-radius:var(--r-md);background:var(--salle-3)" alt="">';
      if(s.type==='merge'){
        html='<div class="row"><span class="sz">M\\u00eame personne ? <b>'+esc(s.a)+'</b> et <b>'+esc(s.b)+'</b> (sim '+s.sim+')</span>'+
          '<button class="btn prim">\\u2713 Fusionner</button><button class="btn">\\u2717 Diff\\u00e9rents</button></div>';
      } else if(s.type==='remove'){
        var labelR='<b>Faux positif ?</b> visage tagu\\u00e9 <b>'+esc(s.person)+'</b> \\u2014 score '+s.sim;
        html='<div class="row" style="align-items:center">'+crop+
          '<a href="'+esc(s.url)+'" target="_blank" rel="noopener" class="sz" style="text-decoration:none;color:var(--graphite)">'+labelR+'</a>'+
          '<button class="btn prim">\\u2713 Oui, c\\u2019est '+esc(s.person)+'</button>'+
          '<button class="btn warn">\\u2717 Retirer le tag</button>'+
          '<input class="qui" placeholder="ou : c\\u2019est\\u2026" autocomplete="off">'+
          '<button class="btn">Pas un visage</button>'+
          '<button class="btn anim">C\\u2019est un animal</button></div>'+
          '<div class="props2" style="margin-top:6px"></div>';
      } else {
        var doute=s.rival
          ? (' <span style="color:var(--veilleuse)">\\u00b7 h\\u00e9site avec <b>'+esc(s.rival)+
             '</b> ('+s.rival_sim+', \\u00e9cart '+s.margin+')</span>') : '';
        var label='<b>Ajouter \\u00e0 '+esc(s.person)+' ?</b> \\u2014 score '+s.sim+doute;
        html='<div class="row" style="align-items:center">'+crop+
          '<a href="'+esc(s.url)+'" target="_blank" rel="noopener" class="sz" style="text-decoration:none;color:var(--graphite)">'+label+'</a>'+
          '<button class="btn prim">\\u2713 Oui, '+esc(s.person)+'</button>'+
          '<input class="qui" placeholder="ou : c\\u2019est\\u2026" autocomplete="off">'+
          '<button class="btn">\\u2717 Aucun</button>'+
          '<button class="btn anim">C\\u2019est un animal</button></div>'+
          '<div class="props2" style="margin-top:6px"></div>';
      }
      el.innerHTML=html;
      var b=el.querySelectorAll('button');
      if(s.type==='merge'){
        b[0].onclick=function(){curResolve('accept',s,el);};
        b[1].onclick=function(){curResolve('reject',s,el);};
      } else if(s.type==='remove'){
        b[0].onclick=function(){ curResolve('reject',s,el); };
        b[1].onclick=function(){ curResolve('accept',s,el); };
        b[2].onclick=function(){ assigner(s, el, '__pas_visage__'); };
        var baR=el.querySelector('.anim');
        if(baR) baR.onclick=function(){ assigner(s, el, '__pas_visage__'); };
        var qr=el.querySelector('.qui'), prr=el.querySelector('.props2');
        if(qr){
          qr.addEventListener('input',function(){ propose2(qr,prr,'personne',function(nom){ assigner(s,el,nom); }); });
          qr.addEventListener('keydown',function(e){
            if(e.key==='Enter'&&qr.value.trim()) assigner(s,el,qr.value.trim()); });
        }
      } else {
        b[0].onclick=function(){curResolve('accept',s,el);};
        b[1].onclick=function(){ assigner(s, el, '__pas_visage__'); };
        var baA=el.querySelector('.anim');
        if(baA) baA.onclick=function(){ assigner(s, el, '__pas_visage__'); };
        var q=el.querySelector('.qui'), pr=el.querySelector('.props2');
        if(q){
          q.addEventListener('input',function(){ propose2(q,pr,'personne',function(nom){ assigner(s,el,nom); }); });
          q.addEventListener('keydown',function(e){
            if(e.key==='Enter'&&q.value.trim()) assigner(s,el,q.value.trim()); });
        }
      }
      box.appendChild(el);
    });
    curMark();
  }).catch(function(){});
}
function loadPetCurator(rebuild){
  fetch('/api/pets/curator/list'+(rebuild?'?rebuild=1':'')).then(function(r){return r.json();}).then(function(d){
    var msg=document.getElementById('petcurmsg'), box=document.getElementById('petcurbox');
    majStats(d.stats||null);
    if(d.building){ msg.textContent='Analyse des chats en cours\\u2026'; box.innerHTML=''; setTimeout(function(){loadPetCurator(false);},4000); return; }
    var auto=d.auto||[], aw=document.getElementById('petautowrap');
    if(!auto.length){ aw.innerHTML=''; }
    else{
      var ah='<div class="cl"><div style="font-size:var(--t-sm);color:var(--graphite);margin-bottom:var(--e-2)">\\ud83e\\udd16 Ajout\\u00e9s automatiquement r\\u00e9cemment ('+auto.length+') \\u2014 v\\u00e9rifie, annule (\\u2717) en cas d\\u2019erreur :</div><div class="grid">';
      auto.forEach(function(a){
        ah+='<label class="prop" style="cursor:default"><a href="'+esc(a.url)+'" target="_blank" rel="noopener"><img loading="lazy" src="'+esc(a.crop_url)+'" alt=""></a>'+
          '<span class="s">'+esc(a.animal)+' '+a.sim+'</span>'+
          '<button class="x" title="Annuler" data-p="'+esc(a.animal)+'" data-k="'+esc(a.key)+'">\\u2717</button></label>';
      });
      ah+='</div></div>'; aw.innerHTML=ah;
      aw.querySelectorAll('button.x').forEach(function(b){
        b.onclick=function(){
          var p=b.getAttribute('data-p'), k=b.getAttribute('data-k'), cell=b.closest('.prop');
          cell.style.opacity=.4;
          post('/api/pets/untag',{name:p,keys:[k]}).then(function(){ cell.remove(); });
        };
      });
    }
    var items=d.items||[];
    document.getElementById('petcurc').textContent=items.length?('('+items.length+')'):'';
    if(!items.length){ msg.textContent=auto.length?'':'Rien \\u00e0 v\\u00e9rifier pour le moment.'; box.innerHTML=''; curMark(); return; }
    msg.textContent='';
    box.innerHTML='';
    items.forEach(function(s){
      var el=document.createElement('div'); el.className='cl';
      var crop='<img loading="lazy" src="'+esc(s.crop_url)+'" style="width:80px;height:80px;object-fit:cover;border-radius:var(--r-md);background:var(--salle-3)" alt="">';
      var doute=s.rival
        ? (' <span style="color:var(--veilleuse)">\\u00b7 h\\u00e9site avec <b>'+esc(s.rival)+
           '</b> ('+s.rival_sim+', \\u00e9cart '+s.margin+')</span>') : '';
      var label='<b>Ajouter \\u00e0 '+esc(s.animal)+' ?</b> \\u2014 score '+s.sim+doute;
      el.innerHTML='<div class="row" style="align-items:center">'+crop+
        '<a href="'+esc(s.url)+'" target="_blank" rel="noopener" class="sz" style="text-decoration:none;color:var(--graphite)">'+label+'</a>'+
        '<button class="btn prim">\\u2713 Oui, '+esc(s.animal)+'</button>'+
        '<input class="qui" placeholder="ou : c\\u2019est\\u2026" autocomplete="off">'+
        '<button class="btn">\\u2717 Aucun</button>'+
        '<button class="btn">Pas un animal</button></div>'+
        '<div class="props2" style="margin-top:6px"></div>';
      var b=el.querySelectorAll('button');
      b[0].onclick=function(){ assignerA(s, el, s.animal); };
      b[1].onclick=function(){ assignerA(s, el, '__inconnu__'); };
      b[2].onclick=function(){ assignerA(s, el, '__pas_animal__'); };
      var q=el.querySelector('.qui'), pr=el.querySelector('.props2');
      q.addEventListener('input',function(){ propose2(q,pr,'animal',function(nom){ assignerA(s,el,nom); }); });
      q.addEventListener('keydown',function(e){
        if(e.key==='Enter'&&q.value.trim()) assignerA(s,el,q.value.trim()); });
      box.appendChild(el);
    });
    curMark();
  }).catch(function(){});
}
// ── Tri au clavier UNIFIÉ : la 1re carte (personnes d'abord, puis animaux)
//    porte l'anneau veilleuse ; les touches agissent dessus. ──
function curMark(scroll){
  var rows=document.querySelectorAll('#curbox > .cl, #petcurbox > .cl');
  rows.forEach(function(r,i){ r.classList.toggle('active', i===0); });
  if(scroll && rows[0]){ try{ rows[0].scrollIntoView({block:'center'}); }catch(e){} }
}
function curUndo(){
  var b=document.querySelector('#toastp button'); if(b){ b.click(); return; }
  fetch('/api/undo',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(){ loadCurator(true); loadPetCurator(true); }).catch(function(){});
}
document.addEventListener('keydown', function(e){
  if(VUE!=='classif') return;
  var tag=(e.target.tagName||'').toLowerCase();
  if(tag==='input'||tag==='textarea'||tag==='select'){ if(e.key==='Escape') e.target.blur(); return; }
  var row=document.querySelector('#curbox > .cl.active, #petcurbox > .cl.active'); if(!row) return;
  var bs=row.querySelectorAll('button');
  if(e.key===' '||e.key==='Enter'||e.key==='o'||e.key==='O'){
    e.preventDefault(); if(bs[0]) bs[0].click(); setTimeout(function(){curMark(true);},150);
  } else if(e.key==='x'||e.key==='X'||e.key==='Delete'){
    e.preventDefault(); if(bs[1]) bs[1].click(); setTimeout(function(){curMark(true);},150);
  } else if(e.key==='z'||e.key==='Z'){
    e.preventDefault(); curUndo();
  } else if(/^[a-zA-Z]$/.test(e.key)){
    var inp=row.querySelector('.qui');
    if(inp){ e.preventDefault(); inp.focus(); inp.value+=e.key; inp.dispatchEvent(new Event('input')); }
  }
});
document.getElementById('curref').onclick=function(){ document.getElementById('curmsg').textContent='Analyse demand\\u00e9e\\u2026'; loadCurator(true); };
document.getElementById('petcurref').onclick=function(){ document.getElementById('petcurmsg').textContent='Analyse demand\\u00e9e\\u2026'; loadPetCurator(true); };

// Lien profond vers une file (#verifier / #verifier-animaux) : les cartes se
// peignent APRES le fetch, donc la cible bouge — meme mode de panne que la
// regression « Gerer » du 12/08. Remede identique : re-viser 2,5 s, en
// s'arretant des que l'utilisateur interagit.
(function(){
  var h=(location.hash||'').replace('#','');
  if(['verifier','verifier-animaux'].indexOf(h)<0) return;
  var stop=false, t0=Date.now();
  ['wheel','touchstart','keydown','mousedown'].forEach(function(ev){
    window.addEventListener(ev, function(){ stop=true; }, {passive:true, once:true});
  });
  (function vise(){
    if(stop) return;
    var el=document.getElementById(h);
    if(el) el.scrollIntoView({block:'start'});
    if(Date.now()-t0<2500) setTimeout(vise, 400);
  })();
})();

fetch('/api/sujets/list').then(function(r){return r.json();}).then(function(d){
  var P=(d.personnes||[]).map(function(x){x.type='personne';return x;});
  var A=(d.animaux||[]).map(function(x){x.type='animal';return x;});
  var L=(d.lieux||[]).map(function(x){x.type='lieu';return x;});
  ALL=P.concat(A).concat(L).sort(function(a,b){return (b.photos||0)-(a.photos||0);});
  document.getElementById('n-tous').textContent=ALL.length;
  document.getElementById('n-personne').textContent=P.length;
  document.getElementById('n-animal').textContent=A.length;
  document.getElementById('n-lieu').textContent=L.length;
  rendre();
}).catch(function(){
  document.getElementById('msg').textContent='Impossible de charger les sujets. Le serveur n a pas r\\u00e9pondu. R\\u00e9essaie dans un instant.';
});
</script>
</body>
</html>"""


PEOPLE_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Personnes</title>
<style>
/* Etape A tokenisation « chambre noire ». Barre/cartes/clusters = tokens
   (--salle-2 barre, --salle-3 cellules). Bouton primaire = papier ; focus =
   veilleuse ; boutons destructifs (warn, retrait) = encre. Panneaux de nommage
   gardes en sombre pour l'etape A (le passage « papier » = redesign etape B).
   Structure/espacements/12a inchanges.
   Etape B (10/08) : espacements/rayons/tailles qui EGALENT un token pointent
   vers lui (rendu identique). Divergences design tranchees : #222 (fond de
   vignette, gris froid) -> --salle-3 (placeholder d'image standard) ; #f0a35b
   (« hesite avec X ») -> --veilleuse (incertitude IA) — voir le JS. */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--f-texte);
       background: var(--salle); color: var(--texte); }
.bar { display: flex; align-items: center; gap: var(--e-3); padding: var(--e-3) var(--e-4);
       background: var(--salle-2); border-bottom: var(--trait); flex-wrap: wrap; }
.bar a { color: var(--texte); text-decoration: none; font-size: var(--t-md); }
.bar .sp { margin-left: auto; }
h2 { font-size: var(--t-md); padding: var(--e-4) var(--e-4) 6px; color: var(--texte); }
h2 .c { color: var(--graphite); font-size: var(--t-sm); font-weight: normal; }
.msg { padding: var(--e-2) var(--e-4); color: var(--graphite); font-size: var(--t-sm); }
button { font-family: inherit; }
.btn { padding: var(--e-2) var(--e-4); border: var(--trait); border-radius: var(--r-md);
       background: var(--salle-3); color: var(--texte); font-size: var(--t-sm); cursor: pointer; }
.btn.prim { background: var(--papier); border-color: var(--papier); color: var(--texte-papier); }
.people { display: flex; flex-wrap: wrap; gap: var(--e-3); padding: var(--e-2) var(--e-4) var(--e-3); }
.pcard { background: var(--salle-3); border: var(--trait); border-radius: var(--r-md);
         padding: var(--e-3); width: 150px; text-align: center; }
.pcard img { width: 90px; height: 90px; object-fit: cover; border-radius: 50%;
             background: var(--salle-3); }
.pcard .nm { margin-top: var(--e-2); font-weight: 600; font-size: var(--t-md); }
.pcard .ct { color: var(--graphite); font-size: var(--t-xs); margin-bottom: var(--e-2); }
.clus { padding: var(--e-2) var(--e-4); }
.cl { background: var(--salle-3); border: var(--trait); border-radius: var(--r-md);
      padding: var(--e-3); margin-bottom: var(--e-3); }
/* Tri au clavier : la carte « en cours de decision » porte l'anneau veilleuse. */
.cl.active { outline: 2px solid var(--veilleuse); outline-offset: 2px; }
.kbd-hint { color: var(--graphite); font-size: var(--t-xs); font-family: var(--f-donnees); }
.kbd-hint b { color: var(--texte); font-weight: 600; }
.cl .faces { display: flex; flex-wrap: wrap; gap: var(--e-1); margin-bottom: var(--e-2); }
.cl .faces img { width: 66px; height: 66px; object-fit: cover; border-radius: var(--r-md);
                 background: var(--salle-3); }
.cl .row { display: flex; gap: var(--e-2); align-items: center; flex-wrap: wrap; }
/* 12a — la rangee d'actions ne doit jamais deborder : enfants qui retrecissent,
   champ elastique, et repli vertical (actions pleine largeur) sous 900px. */
.cl .row > * { min-width: 0; }
.cl .row .sz { color: var(--graphite); font-size: var(--t-sm); flex: 1 1 12rem; margin-right: auto;
               overflow-wrap: anywhere; }
.cl .row .qui { flex: 1 1 150px; min-width: 120px; }
.cl .row input[type=text] { flex: 1 1 12rem; }
.cl .row .btn, .cl .row .qui, .cl .row input[type=text] { min-height: 44px; }
@media (max-width: 900px) {
  .cl .row { align-items: stretch; }
  .cl .row .sz { flex-basis: 100%; }
  .cl .row .btn, .cl .row .qui, .cl .row input[type=text] { flex-basis: 100%; width: 100%; }
  .cl .row > img { align-self: flex-start; }
}
/* Cible aussi .qui : un des inputs .qui n'a pas d'attribut type, donc
   input[type=text] seul le ratait -> champ blanc par defaut (bug reel). */
input[type=text], input.qui { padding: var(--e-2) var(--e-3); border-radius: var(--r-md); border: var(--trait);
                   background: var(--salle-3); color: var(--texte); font-size: var(--t-sm); }
input[type=text]:focus, input.qui:focus { border-color: var(--veilleuse); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px,1fr));
        gap: var(--e-1); }
.prop { position: relative; }
.prop img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: var(--r-md);
            background: var(--salle-3); display: block; }
.prop input { position: absolute; top: 4px; left: 4px; width: 18px; height: 18px; }
.prop .s { position: absolute; bottom: 2px; right: 4px; font-size: var(--t-xs); font-family: var(--f-donnees);
           color: var(--texte); background: rgba(0,0,0,.55); padding: 0 3px; border-radius: var(--r-sm); }
.note { padding: var(--e-2) var(--e-4) var(--e-6); color: var(--graphite); font-size: var(--t-sm); line-height: 1.5; }
/* scroll-margin : la nav sticky (z50) ne doit pas recouvrir le haut du panneau
   quand scrollIntoView l'amene en haut de l'ecran. */
#panel { margin: 0 var(--e-4) var(--e-3); scroll-margin-top: 72px; }
/* ancres des files de travail (liens profonds depuis /sujets Classification) :
   meme protection contre la nav sticky (+ sous-nav Sujets). */
#groupes, #inconnus { scroll-margin-top: 118px; }
#panel .box { background: var(--salle-3); border: var(--trait); border-radius: var(--r-md);
              padding: var(--e-3); }
#panel h3 { font-size: var(--t-md); margin-bottom: var(--e-1); }
#panel .acts { display: flex; gap: var(--e-2); flex-wrap: wrap; margin: var(--e-2) 0; }
.btn.warn { background: transparent; border-color: var(--encre); color: var(--encre); }
.prop .x { position: absolute; top: 3px; right: 4px; background: var(--encre);
           color: #fff; border: none; border-radius: var(--r-sm); font-size: var(--t-xs);
           padding: 1px 5px; cursor: pointer; }
.pcard { cursor: pointer; }
/* ── diaporama d'une personne ── */
#pslide { display: none; position: fixed; inset: 0; z-index: 500; background: #000;
          flex-direction: column; }
#pslide.open { display: flex; }
#ps-img { flex: 1; min-height: 0; width: 100%; object-fit: contain; }
#ps-bar { display: flex; align-items: center; gap: var(--e-3); padding: var(--e-3) var(--e-4);
          background: var(--salle); }
#ps-cap { flex: 1; color: var(--graphite); font-size: var(--t-sm); overflow: hidden;
          text-overflow: ellipsis; white-space: nowrap; }
#ps-folder { color: var(--texte); background: var(--salle-3); border: var(--trait);
             border-radius: var(--r-md); padding: 6px var(--e-3); font-size: var(--t-sm);
             text-decoration: none; white-space: nowrap; flex-shrink: 0;
             max-width: 40vw; overflow: hidden; text-overflow: ellipsis; }
#ps-folder:hover { background: var(--salle-2); }
#ps-folder.hidden { display: none; }
#ps-seek { display: none; position: absolute; left: 16px; bottom: 60px; z-index: 3;
           width: 38vw; max-width: 420px; accent-color: var(--veilleuse); cursor: pointer;
           background: rgba(0,0,0,0.35); border-radius: var(--r-md); }
#ps-bar button { background: var(--salle-3); color: #fff; border: var(--trait);
                 border-radius: var(--r-md); padding: var(--e-2) var(--e-4); font-size: var(--t-md); cursor: pointer; }
/* ── nommer rapidement ── */
#quickname { display: none; position: fixed; inset: 0; z-index: 600;
             background: rgba(0,0,0,.85); padding: 20px; overflow: auto; }
#quickname.open { display: block; }
/* Etape B — deux registres : la modale « nommer rapidement » est une SURFACE
   DE TRAVAIL (papier), posee sur un scrim sombre. Champ clair, boutons adaptes
   au fond clair ; « Nommer » = fixateur (confirmation humaine). */
.qn-card { max-width: 900px; margin: 20px auto; background: var(--papier);
           color: var(--texte-papier); border: 1px solid var(--papier-2);
           border-radius: var(--r-md); padding: var(--e-4);
           box-shadow: 0 1px 0 var(--papier-2), 0 12px 40px #000a; }
.qn-h { font-size: var(--t-md); color: var(--texte-papier); margin-bottom: var(--e-3); }
.qn-faces { display: grid; grid-template-columns: repeat(auto-fill, minmax(96px,1fr));
            gap: var(--e-1); margin-bottom: var(--e-3); }
.qn-faces img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: var(--r-md); background: var(--papier-2); }
#qn-actions { display: flex; gap: var(--e-2); align-items: center; flex-wrap: wrap; }
#qn-input { flex: 1; min-width: 200px; padding: var(--e-2) var(--e-3); border-radius: var(--r-md);
            border: 1px solid var(--papier-2); background: #fff; color: var(--texte-papier); font-size: var(--t-md); }
#qn-input:focus { border-color: var(--veilleuse); }
/* Controles sur papier : boutons a contour, primaire = fixateur (confirmer). */
.qn-card .btn { background: transparent; border-color: var(--graphite-p); color: var(--texte-papier); }
.qn-card .btn.prim { background: var(--fixateur); border-color: var(--fixateur); color: #fff; }
</style>
</head>
<body>
<!--APPNAV-->
<!--SUJETSNAV-->
<div class="bar">
  <span class="sp"></span>
  <button class="btn" id="recluster">&#128260; Regrouper</button>
</div>

<!-- Personnes deja identifiees EN TETE : c'est le point de depart de la revue
     (voir un nom connu, puis le corriger). Le panneau de correction #panel est
     place AVANT la grille : la grille se peint par lots au scroll
     (renderInBatches), donc tout element place APRES elle recule a chaque lot —
     le scrollIntoView de « Gerer » chassait une cible mouvante et n'atterrissait
     jamais (regression signalee 12/08 : « plus rien ne se passe »). Avant la
     grille, la position du panneau est stable ; les lots se peignent dessous.
     Les files de travail (groupes / inconnus) restent SOUS ce bloc, pour la
     meme raison (un lot peint toujours sous la zone de travail). La file
     « A verifier » a migre vers /sujets?vue=classification (12/08).
     Le filtre garde la liste compacte malgre les ~324 fiches, et l'ancre
     « Aller aux groupes » evite de tout scroller. -->
<h2 style="display:flex;align-items:center;gap:var(--e-2);flex-wrap:wrap">Personnes nommées <span class="c" id="pc"></span>
  <input type="text" id="pfilter" placeholder="Filtrer par nom&hellip;" autocomplete="off"
         aria-label="Filtrer les personnes par nom" style="flex:0 1 220px;max-width:220px">
  <a href="#groupes" class="btn" style="font-size:var(--t-xs);padding:var(--e-1) var(--e-2);margin-left:auto;text-decoration:none">Aller aux groupes &#8595;</a></h2>
<div id="panel"></div>
<div class="people" id="people"></div>

<div class="note">Clique une personne pour voir ses photos et corriger les faux
  positifs. Fiche polluée (ex. trop de faux positifs apr&egrave;s avoir tagu&eacute; des
  profils) ? &laquo;&nbsp;&#129529; Nettoyer (r&eacute;f&eacute;rence)&nbsp;&raquo; recalcule sa signature &agrave;
  partir de 3 &agrave; 6 photos nettes, puis retire d'un coup les photos sous le seuil
  de ressemblance.</div>

<!-- La file « À vérifier » a QUITTÉ cette page (12/08) : elle vit maintenant
     dans /sujets?vue=classification, aux côtés de celle des animaux — un seul
     endroit où juger, un seul compteur de séance. Cette page garde ce qui lui
     est propre : fiches, correction, groupes, inconnus. -->
<div class="note">Les propositions &agrave; v&eacute;rifier (visages incertains, faux positifs,
  fusions) se jugent d&eacute;sormais dans
  <a href="/sujets?vue=classification#verifier" style="color:var(--texte)">Sujets &rsaquo; Classification</a>,
  avec celles des animaux.</div>

<h2 id="groupes">Groupes à nommer <span class="c" id="cc"></span>
  <button class="btn" id="quickbtn" style="font-size:var(--t-xs);padding:var(--e-1) var(--e-2);margin-left:var(--e-2)">&#9889; Nommer rapidement</button></h2>
<div class="msg" id="clmsg">Chargement&hellip;</div>
<div class="clus" id="clusters"></div>

<h2 id="inconnus">Inconnus (archiv&eacute;s) <span class="c" id="inc"></span>
  <button class="btn" id="inbtn" style="font-size:var(--t-xs);padding:var(--e-1) var(--e-2);margin-left:var(--e-2)">Afficher</button></h2>
<div class="msg" id="inmsg">Visages mis de c&ocirc;t&eacute; pour un re-tag ult&eacute;rieur. Nommer un groupe le sort des inconnus ; &laquo;&nbsp;R&eacute;activer&nbsp;&raquo; le renvoie dans &laquo;&nbsp;Groupes &agrave; nommer&nbsp;&raquo;.</div>
<div class="clus" id="inconnus"></div>

<div id="pslide">
  <img id="ps-img" alt="">
  <input type="range" id="ps-seek" min="0" value="0" step="1" title="Aller à une photo">
  <div id="ps-bar">
    <span id="ps-cap"></span>
    <a id="ps-folder" class="hidden" href="#" title="Ouvrir le dossier d'origine"></a>
    <button id="ps-prev" title="Précédente">&#9664;</button>
    <button id="ps-pause" title="Pause">&#10073;&#10073;</button>
    <button id="ps-next" title="Suivante">&#9654;</button>
    <button id="ps-close" title="Fermer">&#10005;</button>
  </div>
</div>

<div id="quickname">
  <div class="qn-card">
    <div id="qn-body"></div>
    <div id="qn-actions">
      <input type="text" id="qn-input" placeholder="Nom de la personne (ou vide pour ignorer)" autocomplete="off">
      <button class="btn prim" id="qn-name">Nommer &amp; suivant</button>
      <button class="btn" id="qn-skip">Ignorer</button>
      <button class="btn" id="qn-close" style="margin-left:auto">Fermer</button>
    </div>
  </div>
</div>

<script>
function esc(s){return (s||'').replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function post(url,obj){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(obj||{})}).then(function(r){return r.json();});}

function carteP(p){
  var d=document.createElement('div'); d.className='pcard';
  d.innerHTML=(p.crop?'<img loading="lazy" src="'+esc(p.crop)+'">':'<div style="height:90px"></div>')+
    '<div class="nm">'+esc(p.name)+'</div>'+
    '<div class="ct">'+p.photos+' photo'+(p.photos>1?'s':'')+'</div>'+
    '<button class="btn">Gérer</button>';
  d.onclick=function(){openPerson(p);};
  return d;
}
// Liste complete gardee en memoire : le filtre re-rend un SOUS-ENSEMBLE sans
// refrapper le serveur. Filtre insensible casse ET accents (normalize NFD).
var ALL_PEOPLE=[];
function _norm(s){ return (s||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,''); }
function renderPeople(){
  var q=_norm(document.getElementById('pfilter').value.trim());
  var list=q?ALL_PEOPLE.filter(function(p){return _norm(p.name).indexOf(q)>=0;}):ALL_PEOPLE;
  var el=document.getElementById('people'); el.innerHTML='';
  if(!list.length){ el.innerHTML='<div class="msg">'+(q?'Aucune personne ne correspond au filtre.':'Aucune personne nommée pour l\\'instant.')+'</div>'; return; }
  renderInBatches(el, list, carteP);
}
function loadPeople(){
  fetch('/api/people/list').then(function(r){return r.json();}).then(function(d){
    ALL_PEOPLE=d.people||[];
    document.getElementById('pc').textContent=ALL_PEOPLE.length?('('+ALL_PEOPLE.length+')'):'';
    renderPeople();
    // Lien profond depuis /sujets : ?name=X ouvre directement la fiche.
    try{ var _n=new URLSearchParams(location.search).get('name');
      if(_n){ var _nl=_n.toLowerCase();
        var _p=ALL_PEOPLE.filter(function(x){return String(x.name).toLowerCase()===_nl;})[0];
        if(_p){ openPerson(_p);
          var _pn=document.getElementById('panel');
          if(_pn){ try{ _pn.scrollIntoView({block:'start'}); }catch(e){} } } } }catch(e){}
  });
}

function openPerson(p){
  var panel=document.getElementById('panel');
  panel.innerHTML='<div class="box"><h3>'+esc(p.name)+' <span style="color:var(--graphite);font-weight:normal;font-size:var(--t-sm)">'+
    p.photos+' photo'+(p.photos>1?'s':'')+'</span></h3>'+
    '<div class="acts">'+
    '<button class="btn prim" id="a-ss">▶ Chronologique</button>'+
    '<button class="btn" id="a-ssr">🔀 Aléatoire</button>'+
    '<button class="btn" id="a-ssa">🔗 Association</button>'+
    '<button class="btn" id="a-find">Chercher d\\'autres photos</button>'+
    '<button class="btn" id="a-corr">Corriger (retirer des photos)</button>'+
    '<button class="btn" id="a-clean">🧹 Nettoyer (référence)</button>'+
    '<button class="btn" id="a-ren">Renommer</button>'+
    '<button class="btn warn" id="a-del">Supprimer</button>'+
    '<button class="btn" id="a-close" style="margin-left:auto">Fermer</button>'+
    '</div><div id="a-box"></div></div>';
  var box=document.getElementById('a-box');
  document.getElementById('a-ss').onclick=function(){startPersonSlideshow(p.name,'seq');};
  document.getElementById('a-ssr').onclick=function(){startPersonSlideshow(p.name,'rnd');};
  document.getElementById('a-ssa').onclick=function(){startPersonSlideshow(p.name,'assoc');};
  document.getElementById('a-find').onclick=function(){findMore(p.name,box);};
  document.getElementById('a-corr').onclick=function(){correctPhotos(p.name,box);};
  document.getElementById('a-clean').onclick=function(){cleanPerson(p.name,box);};
  document.getElementById('a-close').onclick=function(){panel.innerHTML='';};
  document.getElementById('a-ren').onclick=function(){
    var nn=prompt('Nouveau nom pour « '+p.name+' » :',p.name); if(!nn||!nn.trim())return;
    post('/api/people/rename',{old:p.name,new:nn.trim()}).then(function(r){
      panel.innerHTML=''; loadPeople();
    });
  };
  document.getElementById('a-del').onclick=function(){
    if(!confirm('Supprimer « '+p.name+' » et retirer son nom de toutes ses photos ?'))return;
    post('/api/people/delete',{name:p.name}).then(function(r){ panel.innerHTML=''; loadPeople(); });
  };
  panel.scrollIntoView({behavior:'smooth',block:'start'});
}

// Carte photo cochable (label + case + vignette + score). Construite en noeuds
// DOM (pas de innerHTML) : compatible rendu par lots renderInBatches, et pas de
// souci d'echappement. `checked` = etat initial de la case.
function _photoCard(f, checked){
  var lab=document.createElement('label'); lab.className='prop';
  var cb=document.createElement('input'); cb.type='checkbox'; cb.checked=!!checked;
  cb.setAttribute('data-k', f.key); if(f.sim!=null) cb.setAttribute('data-s', f.sim);
  var a=document.createElement('a'); a.href=f.url||'#'; a.target='_blank'; a.rel='noopener';
  a.addEventListener('click', function(e){ e.stopPropagation(); });
  var img=document.createElement('img'); img.loading='lazy'; img.src=f.crop_url||f.url;
  a.appendChild(img); lab.appendChild(cb); lab.appendChild(a);
  if(f.sim!=null){ var s=document.createElement('span'); s.className='s'; s.textContent=f.sim; lab.appendChild(s); }
  return lab;
}

// Vue partagee « retirer par seuil » : liste triee du moins au plus
// ressemblant, seuil ajustable, compteur en direct, retrait de masse PILOTE PAR
// LES DONNEES (fiable meme si la grille n'est peinte que par lots). Utilisee par
// « Nettoyer (reference) » (signature propre) et « Corriger » (signature
// actuelle). `container` = element ou tout est rendu ; `note` = entete optionnel.
function scoredRemoval(container, name, ph, defThr, noteHtml){
  container.innerHTML=(noteHtml||'')+
    '<div class="msg" style="color:var(--graphite)">'+ph.length+
    ' photo(s), du moins au plus ressemblant. Seuil '+
    '<input type="number" id="thr" value="'+defThr+'" step="0.05" min="0" max="1" style="width:74px"> '+
    '&rarr; <b id="belowc">0</b> sous le seuil (cochées ci-dessous, décoche pour épargner).</div>'+
    '<div class="grid" id="cgrid"></div>'+
    '<button class="btn warn" id="rm" style="margin-top:8px">Retirer &laquo; '+esc(name)+' &raquo; des photos sous le seuil</button>';
  var cg=container.querySelector('#cgrid');
  function below(){ var t=parseFloat(container.querySelector('#thr').value)||0;
    return ph.filter(function(f){ return (f.sim!=null?f.sim:1)<t; }); }
  function refresh(){ var b=below(); container.querySelector('#belowc').textContent=b.length;
    renderInBatches(cg, b, function(f){ return _photoCard(f, true); }); }
  container.querySelector('#thr').addEventListener('input', refresh);
  container.querySelector('#rm').onclick=function(){
    // Cartes peintes : on respecte leur case (decochee = epargnee). Cartes non
    // encore peintes (rendu par lots) : incluses par defaut.
    var painted={}; cg.querySelectorAll('input').forEach(function(c){ painted[c.getAttribute('data-k')]=c.checked; });
    var keys=[]; below().forEach(function(f){ if(!(f.key in painted) || painted[f.key]) keys.push(f.key); });
    if(!keys.length) return;
    if(!confirm('Retirer « '+name+' » de '+keys.length+' photo(s) sous le seuil ?\\nCes photos ne seront plus re-proposées automatiquement.')) return;
    var btn=container.querySelector('#rm'); btn.disabled=true; btn.textContent='Retrait en cours…';
    post('/api/people/untag',{name:name,keys:keys}).then(function(r){
      container.innerHTML='<div class="msg">&#10003; '+r.removed+' photo(s) retir&eacute;e(s). Elles n\\'apparaissent plus et ne seront pas re-taggu&eacute;es.</div>'; loadPeople();
    });
  };
  refresh();
}

function cleanPerson(name,box){
  box.innerHTML='<div class="msg">Choisis <b>3 à 6</b> photos <b>nettes et de face</b> de '+esc(name)+
    ' comme référence (clique dessus) — ci-dessous, ses photos <b>les plus ressemblantes d\\'abord</b>, donc les vraies. Elles redéfinissent sa signature « propre », sans les profils. Puis « Analyser ».</div>'+
    '<div class="grid" id="refgrid"><div class="msg">Chargement des photos les plus ressemblantes&hellip;</div></div>'+
    '<button class="btn prim" id="anz" style="margin-top:8px">Analyser avec cette référence</button>'+
    '<div id="clean-res"></div>';
  var sel={};
  // order=best : les photos les PLUS ressemblantes d'abord. Sur une fiche
  // polluee, un echantillon « pire d'abord » ne montrerait que des faux
  // positifs -> impossible d'y choisir une vraie photo de reference.
  fetch('/api/people/photos?name='+encodeURIComponent(name)+'&limit=80&order=best').then(function(r){return r.json();}).then(function(d){
    var g=document.getElementById('refgrid'); g.innerHTML='';
    var photos=d.photos||[];
    if(!photos.length){ g.innerHTML='<div class="msg">Aucune photo &agrave; afficher.</div>'; return; }
    photos.forEach(function(f){
      var img=f.crop_url||f.url; var el=document.createElement('div'); el.className='prop';
      el.innerHTML='<img loading="lazy" src="'+esc(img)+'">';
      el.onclick=function(){
        if(sel[f.key]){ delete sel[f.key]; el.style.outline=''; }
        else { if(Object.keys(sel).length>=6) return; sel[f.key]=1; el.style.outline='3px solid var(--fixateur)'; }
      };
      g.appendChild(el);
    });
  }).catch(function(){
    document.getElementById('refgrid').innerHTML='<div class="msg">Impossible de charger l\\'&eacute;chantillon. R&eacute;essaie.</div>';
  });
  document.getElementById('anz').onclick=function(){
    var refs=Object.keys(sel);
    if(!refs.length){ alert('Choisis au moins une photo de référence.'); return; }
    var res=document.getElementById('clean-res');
    res.innerHTML='<div class="msg" style="display:flex;align-items:center;gap:var(--e-2)">'+
      '<span class="netbusy__s"></span><span>Analyse de <b>'+esc(name)+'</b> en cours&hellip; on re-score '+
      '<b>toutes</b> ses photos avec la nouvelle référence. Le sablier en bas à droite confirme que ça travaille.</span></div>';
    res.scrollIntoView({behavior:'smooth',block:'center'});
    post('/api/people/setref',{name:name,ref_keys:refs}).then(function(){
      return post('/api/people/refscore',{name:name,ref_keys:refs});
    }).then(function(d){
      scoredRemoval(res, name, (d.photos||[]), 0.35, null);
    }).catch(function(e){
      res.innerHTML='<div class="msg">Échec de l\\'analyse : '+esc(String((e&&e.message)||e))+'. R&eacute;essaie.</div>';
    });
  };
}

function correctPhotos(name,box){
  box.innerHTML='<div class="msg" style="display:flex;align-items:center;gap:var(--e-2)"><span class="netbusy__s"></span>'+
    '<span>Chargement et scoring de <b>toutes</b> les photos de '+esc(name)+'&hellip;</span></div>';
  // On charge TOUTE la fiche (le scoring est vectorise -> rapide), en mode leger
  // (pas de dossier/mots-cles : inutiles ici), pour que le tri par seuil couvre
  // l'ensemble, pas seulement un sous-ensemble.
  fetch('/api/people/photos?name='+encodeURIComponent(name)+'&limit=50000&light=1').then(function(r){return r.json();}).then(function(d){
    var ph=d.photos||[];
    if(!ph.length){ box.innerHTML='<div class="msg">Aucune photo.</div>'; return; }
    var note='<div class="msg">Scores selon la signature <b>actuelle</b> de '+esc(name)+
      ' (encore polluée). Règle le seuil pour cocher d\\'un coup les faux positifs sous ce score, puis retire. '+
      'Pour une séparation plus fine, &laquo; &#129529; Nettoyer (r&eacute;f&eacute;rence) &raquo; recalcule d\\'abord une signature propre.</div>';
    scoredRemoval(box, name, ph, 0.2, note);
  }).catch(function(e){
    box.innerHTML='<div class="msg">Échec du chargement : '+esc(String((e&&e.message)||e))+'. R&eacute;essaie.</div>';
  });
}

function findMore(name,box){
  box.innerHTML='<div class="msg">Recherche&hellip;</div>';
  post('/api/people/find',{name:name}).then(function(d){
    var pr=d.proposals||[];
    if(!pr.length){ box.innerHTML='<div class="msg">Aucune nouvelle photo trouvée.</div>'; return; }
    var html='<div style="margin:var(--e-2) 0;font-size:var(--t-sm);color:var(--graphite)">'+pr.length+
      ' proposition(s) — décoche les erreurs :</div><div class="grid">';
    pr.forEach(function(f,i){
      html+='<label class="prop"><input type="checkbox" checked data-k="'+esc(f.key)+'">'+
        '<img loading="lazy" src="'+esc(f.crop_url)+'"><span class="s">'+f.sim+'</span></label>';
    });
    html+='</div><button class="btn prim" style="margin-top:8px">Valider la sélection</button>';
    box.innerHTML=html;
    box.querySelector('button').onclick=function(){
      var keys=[]; box.querySelectorAll('input:checked').forEach(function(c){keys.push(c.getAttribute('data-k'));});
      if(!keys.length){ box.innerHTML='<div class="msg">Rien de sélectionné.</div>'; return; }
      post('/api/people/confirm',{name:name,keys:keys}).then(function(r){
        box.innerHTML='<div class="msg">✓ '+r.tagged+' photo(s) attribuée(s) à '+esc(name)+'.</div>';
        loadPeople();
      });
    };
  });
}

/* ---- Attribution unifiée des groupes (miroir de la page Animaux) --------
   Vignettes sélectionnables : on traite un groupe mixte (nuques + découpes de
   chat) sans « scinder ». Un rejet est une attribution à une cible spéciale :
   « Ce n'est pas un visage » (découpe de chat/objet → hors pipeline visages),
   « Rejeter le groupe » (vrais visages non regroupables). Tout est réversible. */
/* Cibles spéciales de rejet, dans l'ordre d'affichage. « C'est un animal »
   et « Ce n'est pas un visage » pointent la même cible (__pas_visage__, écart
   réversible du pipeline visages) : deux libellés d'INTENTION distincts pour le
   même geste. Le premier traite explicitement le cas Mutz (chien/chat détecté
   comme visage), miroir du « C'est une personne » ajouté côté Animaux. */
var SPECIAUX_P=[
  {v:'__pas_visage__', t:'C’est un animal (pas une personne)',
   d:'chien ou chat détecté comme visage — ex. Mutz'},
  {v:'__pas_visage__', t:'Ce n’est pas un visage',
   d:'objet, statue, reflet — écarté du pipeline visages'},
  {v:'__inconnu__', t:'C’est un inconnu (archiver)',
   d:'vrai visage, personne non reconnue — à re-tagger plus tard'}
];
function carteGroupeP(c){
  var el=document.createElement('div'); el.className='cl';
  var membres=c.membres||[];
  var sel=membres.map(function(){return true;});
  el.innerHTML='<div class="sz" style="color:var(--graphite);font-size:var(--t-sm);margin-bottom:var(--e-2)">'+c.size+
      ' visage(s) <span style="color:var(--graphite)">— clique une vignette pour la désélectionner</span></div>'+
    '<div class="faces"></div>'+
    '<div class="row"><input type="text" class="qui" placeholder="C’est… (nom de la personne)" autocomplete="off">'+
    '<button class="btn prim nommer">Attribuer</button>'+
    '<button class="btn warn rejeter">Rejeter le groupe</button>'+
    '<button class="btn archiver" title="Sortir ce groupe de la file, à re-tagger plus tard">Archiver (inconnu)</button></div>'+
    '<div class="props2" style="margin-top:6px"></div>';
  var zone=el.querySelector('.faces');
  (c.crops||[]).forEach(function(u,i){
    var b=document.createElement('button'); b.type='button';
    b.style.cssText='padding:0;border:none;background:none;cursor:pointer;position:relative;line-height:0';
    b.innerHTML='<img loading="lazy" src="'+esc(u)+'" alt="">';
    function paint(){ b.setAttribute('aria-pressed',sel[i]?'true':'false');
      b.style.opacity=sel[i]?'1':'.35';
      b.style.outline=sel[i]?'2px solid var(--fixateur)':'none'; b.style.outlineOffset='-2px'; }
    b.onclick=function(){ sel[i]=!sel[i]; paint(); maj(); };
    paint(); zone.appendChild(b);
  });
  var inp=el.querySelector('input'), btn=el.querySelector('.nommer'),
      rej=el.querySelector('.rejeter'), arch=el.querySelector('.archiver'),
      props=el.querySelector('.props2');
  function choisis(){ return membres.filter(function(_m,i){return sel[i];}); }
  function maj(){ btn.textContent='Attribuer '+choisis().length; }
  function envoyer(cible, tous){
    var m=tous?membres:choisis();
    if(!m.length){ inp.focus(); return; }
    // Deux personnes sur la même vignette : plusieurs noms séparés par « , » ou « + ».
    if(typeof cible==='string' && /[,+]/.test(cible))
      cible=cible.split(/\\s*[,+]\\s*/).filter(Boolean);
    btn.disabled=true; rej.disabled=true; if(arch) arch.disabled=true;
    post('/api/assign',{genre:'visage',membres:m,cible:cible}).then(function(r){
      btn.disabled=false; rej.disabled=false; if(arch) arch.disabled=false;
      if(!r.ok){ props.textContent=r.erreur||'échec'; return; }
      toastP(r.libelle||'fait', r.jeton, function(){ loadClusters(true); loadPeople(); loadInconnus(true); });
      if(m.length>=membres.length){ el.remove(); } else { loadClusters(true); }
      loadPeople(); loadInconnus(true);
    }).catch(function(e){ btn.disabled=false; rej.disabled=false; if(arch) arch.disabled=false;
      props.textContent='Le serveur n a pas repondu. Reessaie dans un instant.'; });
  }
  function listeProps(){
    var t=inp.value.trim().toLowerCase();
    nomsPersonnes().then(function(noms){
      props.innerHTML='';
      noms.filter(function(p){return !t||p.nom.toLowerCase().indexOf(t)===0;})
        .slice(0,4).forEach(function(p){ props.appendChild(prop(p.nom+' · '+p.n, p.nom)); });
      if(t && !noms.some(function(p){return p.nom.toLowerCase()===t;}))
        props.appendChild(prop('Nouveau : '+inp.value.trim(), inp.value.trim()));
      if(!t) SPECIAUX_P.forEach(function(s){ props.appendChild(prop(s.t+' — '+s.d, s.v)); });
    });
  }
  function prop(txt,val){
    var b=document.createElement('button'); b.className='btn';
    b.style.cssText='display:block;width:100%;text-align:left;margin:2px 0;font-size:12.5px';
    b.textContent=txt; b.onclick=function(){ envoyer(val,false); }; return b;
  }
  inp.addEventListener('input',listeProps);
  // IMPORTANT : ne PAS peupler les propositions au chargement. Chaque appel a
  // /api/names?genre=personne declenche un scan lourd cote serveur ; le faire
  // pour chaque groupe en meme temps saturait le serveur (facecrop/assign en
  // « Failed to fetch »). On differe au focus / a la frappe : un seul a la fois.
  inp.addEventListener('focus',listeProps);
  inp.addEventListener('keydown',function(e){ if(e.key==='Enter'&&inp.value.trim()) envoyer(inp.value.trim(),false); });
  btn.onclick=function(){ if(inp.value.trim()) envoyer(inp.value.trim(),false); else inp.focus(); };
  rej.onclick=function(){ envoyer('__non_group__', true); };
  if(arch) arch.onclick=function(){ envoyer('__inconnu__', true); };
  maj();
  return el;
}
// Rendu incremental : construire les ~2000 groupes (>11 000 vignettes) d'un
// coup figeait le rendu. On pose un lot de cartes, puis le suivant quand une
// sentinelle approche du bas de l'ecran (IntersectionObserver, marge 600px).
// carteGroupeP / carteInconnu restent inchanges ; les cartes sont de vrais
// noeuds DOM (remove() individuel apres nommage marche toujours). Repli sans
// IntersectionObserver (navigateurs anciens) : tout rendre.
function renderInBatches(box, items, makeCard, batch){
  batch = batch || 24;
  box.innerHTML='';
  var i=0, obs=null;
  var sentinel=document.createElement('div');
  sentinel.className='batch-sentinel'; sentinel.setAttribute('aria-hidden','true');
  function paint(){
    var end=Math.min(i+batch, items.length);
    var frag=document.createDocumentFragment();
    for(; i<end; i++){ frag.appendChild(makeCard(items[i])); }
    if(sentinel.parentNode) box.insertBefore(frag, sentinel); else box.appendChild(frag);
    if(i>=items.length){ if(obs) obs.disconnect(); sentinel.remove(); }
  }
  box.appendChild(sentinel);
  if('IntersectionObserver' in window){
    obs=new IntersectionObserver(function(entries){
      if(entries.some(function(e){return e.isIntersecting;})) paint();
    }, {rootMargin:'600px'});
    obs.observe(sentinel);
    paint();
  } else {
    while(i<items.length) paint();
  }
}
function loadClusters(rebuild){
  fetch('/api/people/clusters'+(rebuild?'?rebuild=1':'')).then(function(r){return r.json();}).then(function(d){
    var msg=document.getElementById('clmsg'), box=document.getElementById('clusters');
    document.getElementById('cc').textContent=d.count?('('+d.count+')'):'';
    if(d.building){ msg.textContent='Regroupement en cours… (quelques secondes à une minute)';
      box.innerHTML=''; setTimeout(function(){loadClusters(false);},4000); return; }
    if(!d.clusters.length){ msg.textContent='Aucun groupe. Clique « Regrouper » (le scan des visages doit être avancé).'; box.innerHTML=''; return; }
    msg.textContent='';
    box.innerHTML='';
    renderInBatches(box, d.clusters, carteGroupeP);
  });
}

document.getElementById('recluster').onclick=function(){
  document.getElementById('clmsg').textContent='Regroupement demandé…';
  post('/api/people/recluster',{}).then(function(){ setTimeout(function(){loadClusters(false);},1500); });
};

// ── Inconnus (archivés) : file de re-tag, chargée à la demande ──
// Vue paresseuse : on ne construit les groupes d'inconnus (potentiellement
// nombreux) que si l'utilisateur ouvre la section. Nommer un groupe lève
// l'archive (côté serveur, _nommer_membres_visages) ; « Réactiver » le renvoie
// dans « Groupes à nommer » sans lui donner de nom (/api/people/desarchiver).
var INCONNU_SHOWN=false;
function loadInconnus(rebuild){
  if(!INCONNU_SHOWN) return;
  fetch('/api/people/inconnus'+(rebuild?'?rebuild=1':'')).then(function(r){return r.json();}).then(function(d){
    var box=document.getElementById('inconnus');
    document.getElementById('inc').textContent=d.count?('('+d.count+')'):'';
    if(d.building){ box.innerHTML='<span style="color:var(--graphite);padding:var(--e-2)">Regroupement des inconnus…</span>';
      setTimeout(function(){loadInconnus(false);},3000); return; }
    box.innerHTML='';
    if(!d.clusters.length){ box.innerHTML='<span style="color:var(--graphite);padding:var(--e-2)">Aucun visage archivé.</span>'; return; }
    renderInBatches(box, d.clusters, carteInconnu);
  });
}
function carteInconnu(c){
  var el=document.createElement('div'); el.className='cl';
  var membres=c.membres||[];
  var sel=membres.map(function(){return true;});
  el.innerHTML='<div class="sz" style="color:var(--graphite);font-size:var(--t-sm);margin-bottom:var(--e-2)">'+c.size+
      ' visage(s) archivé(s) <span style="color:var(--graphite)">— nomme le groupe pour l’identifier, ou réactive-le</span></div>'+
    '<div class="faces"></div>'+
    '<div class="row"><input type="text" class="qui" placeholder="C’est… (nom de la personne)" autocomplete="off">'+
    '<button class="btn prim nommer">Attribuer</button>'+
    '<button class="btn reactiver" title="Renvoyer ce groupe dans Groupes à nommer">Réactiver</button></div>'+
    '<div class="props2" style="margin-top:6px"></div>';
  var zone=el.querySelector('.faces');
  (c.crops||[]).forEach(function(u,i){
    var b=document.createElement('button'); b.type='button';
    b.style.cssText='padding:0;border:none;background:none;cursor:pointer;position:relative;line-height:0';
    b.innerHTML='<img loading="lazy" src="'+esc(u)+'" alt="">';
    function paint(){ b.setAttribute('aria-pressed',sel[i]?'true':'false');
      b.style.opacity=sel[i]?'1':'.35';
      b.style.outline=sel[i]?'2px solid var(--fixateur)':'none'; b.style.outlineOffset='-2px'; }
    b.onclick=function(){ sel[i]=!sel[i]; paint(); };
    paint(); zone.appendChild(b);
  });
  var inp=el.querySelector('input'), btn=el.querySelector('.nommer'),
      rea=el.querySelector('.reactiver'), props=el.querySelector('.props2');
  function choisis(){ return membres.filter(function(_m,i){return sel[i];}); }
  function nommer(noms){
    var m=choisis(); if(!m.length){ inp.focus(); return; }
    var cible=noms;
    if(typeof cible==='string' && /[,+]/.test(cible)) cible=cible.split(/\\s*[,+]\\s*/).filter(Boolean);
    btn.disabled=true; rea.disabled=true;
    post('/api/assign',{genre:'visage',membres:m,cible:cible}).then(function(r){
      btn.disabled=false; rea.disabled=false;
      if(!r.ok){ props.textContent=r.erreur||'échec'; return; }
      toastP(r.libelle||'fait', r.jeton, function(){ loadInconnus(true); loadClusters(false); loadPeople(); });
      loadInconnus(true); loadPeople();
    }).catch(function(){ btn.disabled=false; rea.disabled=false;
      props.textContent='Le serveur n a pas repondu. Reessaie dans un instant.'; });
  }
  function reactiver(){
    btn.disabled=true; rea.disabled=true;
    post('/api/people/desarchiver',{membres:membres}).then(function(r){
      btn.disabled=false; rea.disabled=false;
      if(!r.ok){ props.textContent=(r&&r.erreur)||'échec'; return; }
      toastP(r.libelle||'réactivé', r.jeton, function(){ loadInconnus(true); loadClusters(true); });
      el.remove(); loadClusters(true);
    }).catch(function(){ btn.disabled=false; rea.disabled=false;
      props.textContent='Le serveur n a pas repondu. Reessaie dans un instant.'; });
  }
  function prop(txt,val){
    var b=document.createElement('button'); b.className='btn';
    b.style.cssText='display:block;width:100%;text-align:left;margin:2px 0;font-size:12.5px';
    b.textContent=txt; b.onclick=function(){ nommer(val); }; return b;
  }
  function listeProps(){
    var t=inp.value.trim().toLowerCase();
    nomsPersonnes().then(function(noms){
      props.innerHTML='';
      noms.filter(function(p){return !t||p.nom.toLowerCase().indexOf(t)===0;})
        .slice(0,4).forEach(function(p){ props.appendChild(prop(p.nom+' · '+p.n, p.nom)); });
      if(t && !noms.some(function(p){return p.nom.toLowerCase()===t;}))
        props.appendChild(prop('Nouveau : '+inp.value.trim(), inp.value.trim()));
    });
  }
  inp.addEventListener('input',listeProps);
  inp.addEventListener('focus',listeProps);
  inp.addEventListener('keydown',function(e){ if(e.key==='Enter'&&inp.value.trim()) nommer(inp.value.trim()); });
  btn.onclick=function(){ if(inp.value.trim()) nommer(inp.value.trim()); else inp.focus(); };
  rea.onclick=reactiver;
  return el;
}
document.getElementById('inbtn').onclick=function(){
  var box=document.getElementById('inconnus'), b=document.getElementById('inbtn');
  if(INCONNU_SHOWN){ INCONNU_SHOWN=false; box.innerHTML=''; document.getElementById('inc').textContent=''; b.textContent='Afficher'; return; }
  INCONNU_SHOWN=true; b.textContent='Masquer';
  box.innerHTML='<span style="color:var(--graphite);padding:var(--e-2)">Regroupement des inconnus…</span>';
  loadInconnus(true);
};

// ── file « À vérifier » (curateur) ──
/* Attribution unifiée côté personnes : le même geste que sur la page Animaux. */
var NOMS_P=null, NOMS_P_INFLIGHT=null;
function nomsPersonnes(){
  if(NOMS_P) return Promise.resolve(NOMS_P);
  // Deduplication : si plusieurs appels arrivent avant la reponse (ex. plusieurs
  // groupes), ils partagent la MEME requete au lieu d'en lancer une chacun.
  if(NOMS_P_INFLIGHT) return NOMS_P_INFLIGHT;
  NOMS_P_INFLIGHT=fetch('/api/names?genre=personne').then(function(r){return r.json();})
    .then(function(d){ NOMS_P=d.noms||[]; NOMS_P_INFLIGHT=null; return NOMS_P; })
    .catch(function(){ NOMS_P_INFLIGHT=null; return []; });   // pas de rejet non capture
  return NOMS_P_INFLIGHT;
}
function toastP(msg, jeton, apres){
  var t=document.getElementById('toastp');
  if(!t){ t=document.createElement('div'); t.id='toastp';
    t.setAttribute('role','status'); t.setAttribute('aria-live','polite');
    t.style.cssText='position:sticky;bottom:12px;margin:12px auto 0;max-width:520px;display:flex;'+
      'align-items:center;gap:12px;background:var(--salle-3);border:var(--trait);border-radius:999px;'+
      'padding:var(--e-3) var(--e-3) var(--e-3) var(--e-4);font-size:var(--t-sm);z-index:60';
    document.body.appendChild(t); }
  t.innerHTML='<span style="flex:1"></span>'; t.firstChild.textContent=msg;
  if(jeton){ var b=document.createElement('button'); b.className='btn'; b.textContent='Annuler';
    b.onclick=function(){ fetch('/api/undo',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({jeton:jeton})}).then(function(){ t.remove();
        if(apres){ apres(); } }); };
    t.appendChild(b); }
  clearTimeout(t._m); t._m=setTimeout(function(){ t.remove(); },10000);
}
// ── diaporama des photos d'une personne (à la suite / aléatoire) ──
var psPhotos=[], psOrder=[], psIdx=0, psName='', psTimer=null, psPaused=false, psDur=6000, psMode='seq';
function psApplyOrder(mode){
  psOrder=psPhotos.map(function(_,i){return i;});
  if(mode==='rnd'){
    for(var i=psOrder.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=psOrder[i]; psOrder[i]=psOrder[j]; psOrder[j]=t; }
  } else if(mode==='assoc'){
    // chaîne d'association : chaque photo partage un max de mots-clés avec la précédente
    var pool=psOrder.slice(), ord=[]; var cur=pool.splice(Math.floor(Math.random()*pool.length),1)[0]; ord.push(cur);
    while(pool.length){ var ck=psPhotos[cur].kw||[], bi=0, bs=-1;
      for(var i=0;i<pool.length;i++){ var s=0, kw=psPhotos[pool[i]].kw||[]; for(var j=0;j<kw.length;j++){ if(ck.indexOf(kw[j])>=0) s++; } if(s>bs){ bs=s; bi=i; } }
      cur=pool.splice(bi,1)[0]; ord.push(cur); }
    psOrder=ord;
  } else {
    // diaporama normal = chronologique, du plus ANCIEN au plus recent (date de
    // prise) ; photos sans date fiable en fin.
    psOrder.sort(function(a,b){ return (psPhotos[a].taken||Infinity)-(psPhotos[b].taken||Infinity); });
  }
}
function startPersonSlideshow(name, mode){
  // ouverture INSTANTANÉE de l'écran (réactif), puis chargement léger en tâche
  // de fond via un endpoint sans calcul de visages → 1ère photo quasi immédiate.
  if(psTimer){ clearTimeout(psTimer); psTimer=null; }
  psName=name; psMode=mode; psPaused=false; psPhotos=[]; psOrder=[]; psIdx=0;
  var el=document.getElementById('pslide'); el.classList.add('open');
  var req=el.requestFullscreen||el.webkitRequestFullscreen||el.msRequestFullscreen;
  if(req){ try{ req.call(el).catch(function(){}); }catch(e){} }
  document.getElementById('ps-pause').innerHTML='&#10073;&#10073;';
  document.getElementById('ps-img').removeAttribute('src');
  document.getElementById('ps-cap').textContent='Chargement…';
  document.getElementById('ps-folder').classList.add('hidden');
  var seek=document.getElementById('ps-seek'); if(seek) seek.style.display='none';
  fetch('/api/people/slideshow?name='+encodeURIComponent(name)).then(function(r){return r.json();}).then(function(d){
    if(!document.getElementById('pslide').classList.contains('open')) return; // fermé entre-temps
    var ph=(d.photos||[]).filter(function(f){return f.url;});
    if(!ph.length){ psClose(); alert('Aucune photo pour '+name+'.'); return; }
    psPhotos=ph; psApplyOrder(mode); psIdx=0;
    if(seek){ seek.max=(psPhotos.length-1); seek.value=0; seek.style.display=(psPhotos.length>1?'block':'none'); }
    psShow();
  }).catch(function(){ psClose(); });
}
var psSeekTimer=null;
// MAJ légère (légende + chip + position du slider), SANS charger l'image
function psRenderMeta(){
  if(!psPhotos.length) return;
  var f=psPhotos[psOrder[psIdx]];
  document.getElementById('ps-cap').textContent=psName+'  —  '+(psIdx+1)+' / '+psPhotos.length+'   ·   '+(f.name||'');
  var fl=document.getElementById('ps-folder');
  if(f.gurl){ fl.href=f.gurl; fl.textContent='📁 '+(f.folder||'Dossier'); fl.classList.remove('hidden'); }
  else{ fl.classList.add('hidden'); }
  var sk=document.getElementById('ps-seek');
  if(sk && document.activeElement!==sk){ sk.value=psIdx; }
}
function psShow(){
  if(psTimer){ clearTimeout(psTimer); psTimer=null; }
  if(psSeekTimer){ clearTimeout(psSeekTimer); psSeekTimer=null; }
  if(!psPhotos.length) return;
  var f=psPhotos[psOrder[psIdx]];
  // Vignettes serveur (audit O1) : 1600 px suffit au plein écran, l'original
  // (2-6 Mo NAS) n'est plus lu ; /api/thumb redirige s'il ne sait pas.
  document.getElementById('ps-img').src=f.key?'/api/thumb?key='+encodeURIComponent(f.key)+'&s=1600':f.url;
  psRenderMeta();
  var nx=psPhotos[psOrder[(psIdx+1)%psOrder.length]]; if(nx){ var pr=new Image(); pr.src=nx.key?'/api/thumb?key='+encodeURIComponent(nx.key)+'&s=1600':nx.url; }
  if(!psPaused) psTimer=setTimeout(function(){ psNext(1); }, psDur);
}
function psNext(d){ if(!psOrder.length) return; psIdx=(psIdx+d+psOrder.length)%psOrder.length; psShow(); }
function psSeekTo(v){
  if(!psPhotos.length) return;
  psIdx=Math.max(0,Math.min(psPhotos.length-1,parseInt(v,10)||0));
  // pendant le glissement du slider : on met à jour la légende instantanément
  // (données déjà en mémoire), mais on DIFFÈRE le chargement de l'image pour ne
  // pas déclencher une requête réseau par photo survolée. L'image ne se charge
  // que ~180 ms après l'arrêt du curseur → réactivité conservée jusqu'à la fin.
  if(psTimer){ clearTimeout(psTimer); psTimer=null; }
  psRenderMeta();
  if(psSeekTimer) clearTimeout(psSeekTimer);
  psSeekTimer=setTimeout(function(){ psSeekTimer=null; psShow(); }, 180);
}
function psClose(){ if(psTimer){clearTimeout(psTimer);psTimer=null;} document.getElementById('pslide').classList.remove('open');
  if(document.fullscreenElement){ try{ document.exitFullscreen(); }catch(e){} } }
function psTogglePause(){ psPaused=!psPaused; document.getElementById('ps-pause').innerHTML=psPaused?'&#9654;':'&#10073;&#10073;';
  if(!psPaused) psShow(); else if(psTimer){ clearTimeout(psTimer); psTimer=null; } }
document.getElementById('ps-next').onclick=function(){ psNext(1); };
document.getElementById('ps-prev').onclick=function(){ psNext(-1); };
document.getElementById('ps-pause').onclick=psTogglePause;
document.getElementById('ps-close').onclick=psClose;
(function(){ var sk=document.getElementById('ps-seek');
  if(sk){ sk.addEventListener('input',function(){ psSeekTo(this.value); }); } })();
document.addEventListener('keydown',function(e){
  if(!document.getElementById('pslide').classList.contains('open')) return;
  if(e.key==='Escape') psClose();
  else if(e.key==='ArrowRight') psNext(1);
  else if(e.key==='ArrowLeft') psNext(-1);
  else if(e.key===' '){ e.preventDefault(); psTogglePause(); }
});

// ── nommer rapidement : les plus gros groupes anonymes, un par un ──
var qnList=[], qnIdx=0;
function quickNameStart(){
  fetch('/api/people/clusters').then(function(r){return r.json();}).then(function(d){
    if(d.building){ alert('Regroupement en cours — réessaie dans un instant.'); return; }
    qnList=(d.clusters||[]).slice(); qnIdx=0;
    if(!qnList.length){ alert('Aucun groupe anonyme à nommer pour le moment.'); return; }
    document.getElementById('quickname').classList.add('open');
    document.getElementById('qn-actions').style.display='flex';
    qnShow();
  });
}
function qnShow(){
  var body=document.getElementById('qn-body');
  if(qnIdx>=qnList.length){
    body.innerHTML='<div class="msg">Terminé ! Tous les groupes ont été passés en revue. 🎉</div>';
    document.getElementById('qn-actions').style.display='none'; loadClusters(false); return;
  }
  var c=qnList[qnIdx];
  var imgs=(c.crops||[]).map(function(u){return '<img loading="lazy" src="'+esc(u)+'">';}).join('');
  body.innerHTML='<div class="qn-h">Groupe '+(qnIdx+1)+' / '+qnList.length+' — <b>'+c.size+' visages</b></div>'+
    '<div class="qn-faces">'+imgs+'</div>';
  var inp=document.getElementById('qn-input'); inp.value=''; setTimeout(function(){inp.focus();},30);
  bgLoad();
}
function qnName(){
  if(qnIdx>=qnList.length) return;
  var c=qnList[qnIdx], nm=document.getElementById('qn-input').value.trim();
  if(!nm){ qnIdx++; qnShow(); return; }
  var btn=document.getElementById('qn-name'); btn.disabled=true;
  post('/api/people/name',{cid:c.cid,name:nm}).then(function(){ btn.disabled=false; loadPeople(); qnIdx++; qnShow(); })
    .catch(function(){ btn.disabled=false; qnIdx++; qnShow(); });
}
document.getElementById('quickbtn').onclick=quickNameStart;
document.getElementById('qn-name').onclick=qnName;
document.getElementById('qn-skip').onclick=function(){ qnIdx++; qnShow(); };
document.getElementById('qn-close').onclick=function(){ document.getElementById('quickname').classList.remove('open'); loadClusters(false); };
document.getElementById('qn-input').addEventListener('keydown',function(e){ if(e.key==='Enter') qnName(); });

document.getElementById('pfilter').addEventListener('input', renderPeople);
loadPeople();
loadClusters(false);

// ── chargement de fond progressif des vignettes (sans attendre le scroll) ──
var _lq=[], _lqActive=0, _LQ_CONC=4;
function loadQueue(){
  while(_lqActive<_LQ_CONC && _lq.length){
    var el=_lq.shift(); _lqActive++;
    (function(im){
      im.onload=im.onerror=function(){ _lqActive--; im.onload=im.onerror=null; loadQueue(); };
      im.src=im.getAttribute('data-src'); im.removeAttribute('data-src');
    })(el);
  }
}
function bgLoad(){
  document.querySelectorAll('img[loading="lazy"]').forEach(function(el){
    el.removeAttribute('loading');
    if(el.complete && el.naturalWidth>0) return;   // déjà chargée
    var s=el.getAttribute('src');
    if(s){ el.setAttribute('data-src', s); el.removeAttribute('src'); }
  });
  document.querySelectorAll('img[data-src]').forEach(function(el){ if(_lq.indexOf(el)<0) _lq.push(el); });
  loadQueue();
}
setInterval(bgLoad, 1000);
bgLoad();
// Liens profonds des sections de travail (onglet Classification de /sujets) :
// la grille des personnes se peint PAR LOTS au-dessus de ces ancres — cible de
// scroll mouvante (même mode de panne que la régression « Gérer » du 12/08).
// Remède : re-viser l'ancre pendant 2,5 s, en s'arrêtant dès que l'utilisateur
// interagit (molette, toucher, clavier).
(function(){
  var h=(location.hash||'').replace('#','');
  if(['groupes','inconnus'].indexOf(h)<0) return;
  var stop=false, t0=Date.now();
  ['wheel','touchstart','keydown','mousedown'].forEach(function(ev){
    window.addEventListener(ev, function(){ stop=true; }, {passive:true, once:true});
  });
  (function vise(){
    if(stop) return;
    var el=document.getElementById(h);
    if(el) el.scrollIntoView({block:'start'});
    if(Date.now()-t0<2500) setTimeout(vise, 400);
  })();
})();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.client_address[0]}  {fmt % args}")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/' or path == '':
            self._send_html(HTML_PAGE)

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

        elif path == '/api/search/status':
            self._serve_semantic_status()

        elif path == '/api/hardware':
            self._serve_hardware()

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

        elif path == '/api/people/slideshow':
            self._serve_person_slideshow()

        elif path == '/api/curator/list':
            self._serve_curator_list()
        elif path == '/api/pets/curator/list':
            self._serve_pets_curator_list()

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
            self._do_post()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, str(e).encode(), 'text/plain')

    def _read_json_body(self):
        n = int(self.headers.get('Content-Length', 0))
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return {}

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
        except fichiers.FileOpError as e:
            self._send(200, json.dumps({"ok": False, "error": str(e)},
                       ensure_ascii=False).encode(), 'application/json')

    def _do_post(self):
        path = urllib.parse.urlparse(self.path).path
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
                         if f.is_file() and f.suffix.lower() in IMAGE_EXT
                         and not _is_hidden_path(f.relative_to(folder))]
            else:
                files = [f for f in folder.iterdir()
                         if f.is_file() and f.suffix.lower() in IMAGE_EXT
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
                fparts.append('<a class="fchip up" href="/files?dir='
                              + urllib.parse.quote(parent, safe='/')
                              + '">&#11014;&#65039; Parent</a>')
            else:
                fparts.append('<a class="fchip up" href="/browse">&#11014;&#65039; Dossiers</a>')
        for e in subdirs:
            sv = f"{idx}/{(sub + '/' if sub else '') + e.name}"
            fparts.append('<a class="fchip" href="/files?dir='
                          + urllib.parse.quote(sv, safe='/')
                          + f'">&#128193; {html.escape(e.name)}</a>')
        cur = f"{idx}/{sub}" if sub else str(idx)
        if rec:
            fparts.append('<a class="fchip up" href="/files?dir='
                          + urllib.parse.quote(cur, safe='/')
                          + '">&#128257; Ce dossier seul</a>')
        elif subdirs:
            fparts.append('<a class="fchip up" href="/files?dir='
                          + urllib.parse.quote(cur, safe='/')
                          + '&amp;rec=1">&#128257; Inclure les sous-dossiers</a>')
        if fparts:
            lv = f'/browse/{idx}/' + urllib.parse.quote(sub) if sub else f'/browse/{idx}'
            fparts.append(f'<a class="fchip up" href="{lv}">&#128196; Liste</a>')
        folders_html = ('<div class="folders">' + ''.join(fparts) + '</div>') if fparts else ''
        if search_mode:
            folders_html = ''   # une page de resultats n'a pas de sous-dossiers
        if sim_mode:
            # Bandeau : d'où vient la page + retour. Le nom suffit ; la photo
            # de référence arrive de toute façon en tête d'aucun résultat
            # (elle est écartée) et son dossier reste à un clic.
            folders_html = ('<div class="folders">'
                            '<span class="fchip">&#128269; Semblables à '
                            + html.escape(Path(simparam).name) + '</span>'
                            '</div>')
        is_uploads = folder in (UPLOAD_DIR, UPLOAD_DIR.resolve())
        roots_g = media_roots()
        file_data = []
        for f in files:
            entry = (STORE.get(str(f))
                     or (STORE.get(f.name) if is_uploads else None)
                     or {})
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
            folder_lbl, gurl = _folder_link_for_key(str(f), roots_g)
            file_data.append({
                'name': f.relative_to(folder).as_posix() if rec else f.name,
                # Clé d'index : sert à recouper les résultats de la recherche
                # sémantique (clés Uploads = nom nu), ET à cibler la suppression
                # par clé (point 21). Pour une racine supplémentaire, on garde
                # TOUJOURS le chemin absolu : un fichier non encore indexé y
                # retombait sinon sur un nom nu, résolu à tort sous Uploads par
                # _key_to_target (mauvaise racine). Uploads : comportement
                # inchangé (nom nu, relatif).
                'key': str(f) if (not is_uploads
                                  or STORE.get(str(f)) is not None) else f.name,
                'url': url_for(f),
                'size': human_size(size),
                'mtime': mtime,
                # Date de PRISE (epoch) pour le tri chronologique de la galerie
                # et l'ordre du diaporama — _best_time : EXIF, sinon nom/annee, sinon mtime.
                'taken': _best_time(str(f), entry),
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
                    'kw': sorted(kws),
                    'gps': e.get('gps'),
                    'desc': e.get('desc', ''),
                    'folder': folder_lbl,
                    'gurl': gurl,
                })

        # Recherche globale (/files?q=...) : on REMPLACE la grille par le resultat
        # de semantic_search, dans l'ordre de pertinence renvoye. Meme forme
        # d'objet que la branche `sel` (donc rendu client inchange). Lecture seule,
        # index en memoire ; note_heavy_activity car semantic_search peut lire les
        # vecteurs. Cap a 1500 : couvre les gros lieux (Bremblens ~1141) sans
        # exploser le rendu (vignettes en lazy-load).
        if search_mode or sim_mode:
            note_heavy_activity()
            roots_cache = media_roots()
            file_data = []
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
                                        '<span class="fchip">Cette photo n\'a '
                                        'pas encore été analysée : son vecteur '
                                        'sera calculé en tâche de fond, '
                                        'réessayer dans quelques minutes.'
                                        '</span></div>')
                        resultats_q = []
                else:
                    resultats_q = semantic_search(qparam, 1500)
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
                    'kw': kws,
                    'gps': e.get('gps'),
                    'desc': e.get('desc', ''),
                    'folder': folder_lbl,
                    'gurl': gurl,
                })

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

        page = (GALLERY_PAGE
                .replace('__FOLDERS__', folders_html)
                .replace('__MOTIFS__', json.dumps(
                    {'counts': motif_counts, 'sel': motif}, ensure_ascii=False))
                .replace('__FILE_JSON__', json.dumps(file_data, ensure_ascii=False))
                .replace('__TAGGED__', str(STORE.tagged_count()))
                .replace('__REC__', '1' if rec else '0')
                .replace('__HASSUBS__', '1' if subdirs else '0')
                .replace('__DIRQ__', json.dumps(dirparam))
                .replace('__SEARCHQ__', json.dumps(qparam if search_mode else ''))
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
        try:
            resultats = semantic_search(requete, limite)
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
        noms, reste = _extraire_noms(requete)
        lieux, reste = _extraire_lieux(reste)
        self._send(200, json.dumps(
            {'results': sortie, 'q': requete,
             'noms': [n.split(':', 1)[1] for n in noms],
             'lieux': lieux, 'reste': reste},
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

    def _serve_semantic_status(self):
        etat = dict(SEMANTIC_STATE)
        etat['total'] = len(STORE.data)
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
        self._send_html(MAP_PAGE)

    def _serve_faces(self):
        self._send_html(FACES_PAGE)

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
        self._send_html(PETS_PAGE)

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
        if path == '/api/pets/name':
            tagged = name_pet_cluster(str(data.get('cid', '')), data.get('name', ''))
            self._send(200, json.dumps({"ok": tagged > 0, "tagged": tagged}).encode(),
                       'application/json')
        elif path == '/api/pets/find':
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
            n = rename_cat(data.get('old', ''), data.get('new', ''))
            self._send(200, json.dumps({"ok": n > 0, "moved": n}).encode(),
                       'application/json')
        elif path == '/api/pets/delete':
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

    def _serve_hardware(self):
        body = json.dumps({'hw': hw_state()}, ensure_ascii=False).encode()
        self._send(200, body, 'application/json')

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
        if url is None:
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

    def _serve_people(self):
        self._send_html(PEOPLE_PAGE)

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
        self._send_html(SUBJECTS_PAGE)

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
            n = rename_person(data.get('old', ''), data.get('new', ''))
            self._send(200, json.dumps({"ok": n > 0, "moved": n}).encode(),
                       'application/json')
        elif path == '/api/people/delete':
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

    # ─── Centre de controle : /reglages ───────────────────────────────────
    def _serve_reglages(self):
        self._send_html(REGLAGES_PAGE)

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
            'boucle': dict(MAINT_LOOP_STATE),
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
                'par_annee': pa.get('par_annee') or {}})(load('plan_rangement_annee.json') or {}),
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

        p = None
        for _ in range(6):
            cand = _random_photo(folder)
            if cand is None:
                break
            ce = STORE.get(str(cand)) or STORE.get(cand.name) or {}
            if not ce.get('failed'):
                p = cand
                break
        if p is None:
            self._send(200, b'{"url": null}', 'application/json')
            return
        key = p.name if _pkey(p.parent) == _pkey(UPLOAD_DIR) else str(p)
        entry = STORE.get(str(p)) or STORE.get(p.name) or {}
        kw = list(dict.fromkeys(
            (entry.get('kw_fr') or []) + (entry.get('kw_en') or [])))
        folder, gurl = _folder_link_for_key(str(p))
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
        if rows:
            body = '\n'.join(rows)
            body += ('<p class="empty">Ces fichiers sont candidats à la suppression '
                     '(dans \\\\nas-bremblens\\home\\Uploads).<br>'
                     '« EXIF endommagé » = la photo s\'affiche mais ses métadonnées '
                     'sont corrompues (les tags restent dans la galerie).</p>')
        else:
            body = '<p class="empty">Aucun fichier à problème détecté &#127881;</p>'
        page = (BROWSE_PAGE
                .replace('__EXTRA__', '')
                .replace('__CRUMBS__', f'Santé — {len(problems)} fichier(s) à problème')
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
            page = (BROWSE_PAGE
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
        for e in files:
            relf = (sub + '/' if sub else '') + e.name
            href = f'/media/{idx}/' + urllib.parse.quote(relf)
            try:
                sz = human_size(e.stat().st_size)
            except OSError:
                sz = '?'
            ext = e.suffix.lower()
            if ext in IMAGE_EXT:
                icon = '&#128247;'
            elif ext in {'.mp4', '.mov', '.avi', '.mkv'}:
                icon = '&#127909;'
            else:
                icon = '&#128196;'
            nm_a = html.escape(e.name, quote=True)
            rows.append(f'<div class="row" data-idx="{idx}" data-rel="{html.escape(relf, quote=True)}" data-name="{nm_a}">'
                        f'<input type="checkbox" class="sel" aria-label="Selectionner {nm_a}">'
                        f'<a class="lk" href="{href}" target="_blank"><span class="ic">{icon}</span>'
                        f'<span class="nm">{html.escape(e.name)}</span></a>'
                        f'<span class="sz">{sz}</span></div>')

        dirval = f"{idx}/{sub}" if sub else str(idx)
        glink = ('<a class="back" href="/files?dir='
                 + urllib.parse.quote(dirval, safe='/')
                 + '">&#128444;&#65039; Galerie de ce dossier</a>')
        page = (BROWSE_PAGE
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
        self._send_file(filepath)

    def _serve_file(self, url_path):
        rel = urllib.parse.unquote(url_path[len('/uploads/'):])
        filepath = self._resolve_safe(rel)
        if filepath is None or not filepath.is_file():
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
        if '<!--APPNAV-->' in html_str:
            html_str = html_str.replace('<!--APPNAV-->', APP_NAV_HTML)
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

    threading.Thread(target=tagger_worker, daemon=True).start()
    threading.Thread(target=maintenance_loop, daemon=True).start()
    threading.Thread(target=_backfill, args=('gps', backfill_gps),
                     daemon=True).start()
    threading.Thread(target=_backfill, args=('dates', backfill_dates),
                     daemon=True).start()
    threading.Thread(target=reconcile_named_tags, daemon=True).start()
    threading.Thread(target=_backfill, args=('noms', reimport_name_tags),
                     daemon=True).start()
    threading.Thread(target=face_worker, daemon=True).start()
    threading.Thread(target=face_scan_loop, daemon=True).start()
    threading.Thread(target=animal_worker, daemon=True).start()
    threading.Thread(target=animal_scan_loop, daemon=True).start()
    threading.Thread(target=pet_embed_loop, daemon=True).start()
    threading.Thread(target=rederive_pet_refs, daemon=True).start()
    threading.Thread(target=cat_curator_loop, daemon=True).start()
    threading.Thread(target=person_writer, daemon=True).start()
    threading.Thread(target=curator_loop, daemon=True).start()
    threading.Thread(target=reembed_loop, daemon=True).start()
    threading.Thread(target=semantic_loop, daemon=True).start()
    threading.Thread(target=maintenance_orchestrator, daemon=True).start()

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
