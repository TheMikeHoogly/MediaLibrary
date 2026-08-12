"""
Recherche semantique — encodeur SigLIP 2 (open_clip) + vocabulaire controle.
──────────────────────────────────────────────────────────────────────────────

POURQUOI UN ENCODEUR PLUTOT QU'UN VLM
    qwen3-vl:2b GENERE du texte pour produire des mots-cles : lent, non
    deterministe, et il faut _salvage_tags() / parse_tags() pour rattraper le
    JSON malforme. SigLIP 2 place images et textes dans le MEME espace
    vectoriel. Un seul encodage par photo donne trois choses :

      1. la recherche en langue naturelle ("Luna endormie sur le canape") ;
      2. le tagging, par comparaison a un VOCABULAIRE CONTROLE que tu ecris
         toi-meme — deterministe, et un tag ajoute apres coup ne demande PAS
         de reanalyser les photos, seulement d'encoder l'etiquette ;
      3. les photos similaires et les doublons, par simple distance cosinus.

    Le VLM reste utile pour ce qu'il fait mieux : la description en phrase.

CE MODULE EST AUTONOME
    Il s'utilise sans server.py, pour eprouver le socle avant de l'integrer :

        python semantic.py --diagnostic
        python semantic.py --banc 20          # mesure vitesse + VRAM reelles
        python semantic.py --indexer 500      # encode et stocke
        python semantic.py --chercher "chat sur le canape"
        python semantic.py --tags 20          # tagging par vocabulaire controle

VRAM
    La carte fait 4 Go, partages avec Ollama. Le modele n'est charge sur GPU
    que si assez de VRAM est libre (SIGLIP_GPU_MIN_FREE_MB), exactement comme
    les pipelines visages et animaux. Sinon CPU, sans erreur.
"""

import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


# ── Avertissements Hugging Face ──────────────────────────────────────────────
# Deux messages apparaissent au premier telechargement :
#
#  1. « unauthenticated requests to the HF Hub » — sans jeton, le Hub applique
#     des limites de debit plus basses. Sans consequence ici : le modele n'est
#     telecharge qu'une fois. Pose un jeton dans hf_token.txt si tu telecharges
#     souvent (jeton en lecture seule, cree sur huggingface.co/settings/tokens).
#
#  2. « your machine does not support symlinks » — le cache HF duplique alors
#     les fichiers au lieu de les lier : environ 1,5 Go de disque en double
#     pour ce modele. Se corrige en activant le mode developpeur de Windows
#     (Parametres > Confidentialite et securite > Pour les developpeurs).
#     Ce message-la, on le neutralise seulement apres l'avoir explique.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
_JETON = SCRIPT_DIR / "hf_token.txt"
if "HF_TOKEN" not in os.environ and _JETON.exists():
    try:
        for _l in _JETON.read_text(encoding='utf-8').splitlines():
            _l = _l.strip()
            if _l and not _l.startswith('#'):
                os.environ["HF_TOKEN"] = _l
                break
    except OSError:
        pass
# Deplacer le cache (par defaut C:\Users\...\.cache\huggingface) si le disque
# systeme est juste : creer hf_cache.txt contenant le chemin voulu.
try:
    for _l in (SCRIPT_DIR / "hf_cache.txt").read_text(encoding='utf-8').splitlines():
        _l = _l.strip()
        if _l and not _l.startswith('#'):
            os.environ["HF_HOME"] = _l
            break
except OSError:
    pass


def _calmer_hf():
    """Reduit le bruit de huggingface_hub une fois la bibliotheque chargee.

    On ne touche qu'au niveau WARNING : les vraies erreurs restent visibles.
    """
    import logging
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    try:
        from huggingface_hub.utils import logging as hf_log
        hf_log.set_verbosity_error()
    except Exception:                                        # noqa: BLE001
        pass

# ── Configuration ────────────────────────────────────────────────────────────
MODELE = "ViT-B-16-SigLIP2-256"        # tour image + texte, multilingue
POIDS = "webli"
MODELE_FICHIER = SCRIPT_DIR / "siglip_modele.txt"   # pour changer sans toucher au code
VOCAB_FICHIER = SCRIPT_DIR / "vocabulaire_tags.txt"
SIGLIP_GPU_MIN_FREE_MB = 1400          # VRAM libre exigee pour monter sur GPU
SIGLIP_MAX_SIDE = 512                  # pre-redimensionnement avant encodage
SIGLIP_BATCH = 8
GABARIT = "une photo de {}"            # gabarit de prompt pour le zero-shot

try:
    for _l in MODELE_FICHIER.read_text(encoding='utf-8').splitlines():
        _l = _l.strip()
        if _l and not _l.startswith('#'):
            MODELE, _, _p = _l.partition('/')
            MODELE = MODELE.strip()
            POIDS = (_p.strip() or POIDS)
            break
except OSError:
    pass

# Version du pipeline : si elle change, les vecteurs stockes sont perimes.
VERSION = f"siglip2|{MODELE}|{POIDS}|max{SIGLIP_MAX_SIDE}"
KIND = "photo"                          # espace de vecteurs dans la table


# ── Chargement paresseux du modele ───────────────────────────────────────────
_ETAT = {"modele": None, "preproc": None, "tokenizer": None,
         "device": None, "erreur": ""}

# Arbitre GPU optionnel, injecte par le serveur (set_arbitre). Quand il est
# present, la decision CPU/GPU passe par un bail de VRAM (un seul point de
# verite cote serveur) au lieu de la sonde privee ci-dessous. En usage CLI
# autonome, rien n'est injecte : le seuil SIGLIP_GPU_MIN_FREE_MB s'applique
# comme avant. Zero dependance : deux callables, rien de plus.
_ARBITRE = None   # (demander() -> bool, confirmer() -> None, rendre() -> None)


def set_arbitre(demander, confirmer=None, rendre=None):
    """Branche l'arbitre de VRAM du serveur. `demander` renvoie True si un
    bail est accorde ; `confirmer` signale que le modele est monte ; `rendre`
    restitue le bail quand le montage echoue — sans lui, un bail accorde puis
    jamais monte resterait soustrait de la VRAM jusqu'au redemarrage (famine),
    et le cache de demander() renverrait 'cuda' pour toujours (re-OOM a chaque
    lot au lieu du repli CPU)."""
    global _ARBITRE
    _ARBITRE = (demander, confirmer or (lambda: None), rendre or (lambda: None))

# Journal des images refusees. Sans lui, un lot qui ne produit aucun vecteur
# est indiscernable d'un lot lent : c'est ce qui a rendu le blocage de
# l'encodage si difficile a localiser.
ERREURS_MAX = 20
DERNIERES_ERREURS = []


def _vram_libre_mb():
    try:
        import torch
        if not torch.cuda.is_available():
            return 0
        libre, _ = torch.cuda.mem_get_info()
        return libre / 1048576
    except Exception:                                        # noqa: BLE001
        return 0


def _device_cible():
    libre = _vram_libre_mb()
    if _ARBITRE is not None:
        try:
            return ("cuda" if _ARBITRE[0]() else "cpu"), libre
        except Exception:                                    # noqa: BLE001
            pass                       # arbitre en panne → sonde privee
    if libre >= SIGLIP_GPU_MIN_FREE_MB:
        return "cuda", libre
    return "cpu", libre


def encodeur(forcer_device=None):
    """Renvoie (modele, preproc, tokenizer, device) ou (None, ...) si absent."""
    if _ETAT["modele"] is not None and not forcer_device:
        return (_ETAT["modele"], _ETAT["preproc"], _ETAT["tokenizer"],
                _ETAT["device"])
    try:
        import torch
        import open_clip
        _calmer_hf()
    except ImportError as e:
        _ETAT["erreur"] = (
            f"{e}. Lance \"14 - Installer la recherche semantique.bat\".")
        return None, None, None, None
    device = forcer_device or _device_cible()[0]

    def _rendre_bail():
        # Restitue le bail 'semantique' si on l'avait obtenu (jamais lors d'un
        # forcer_device : aucun bail n'a ete demande dans ce cas).
        if device == "cuda" and _ARBITRE is not None and not forcer_device:
            try:
                _ARBITRE[2]()
            except Exception:                                # noqa: BLE001
                pass

    try:
        modele, _, preproc = open_clip.create_model_and_transforms(
            f"hf-hub:timm/{MODELE}.{POIDS}") if MODELE.startswith("hf-hub") \
            else open_clip.create_model_and_transforms(MODELE, pretrained=POIDS)
        tokenizer = open_clip.get_tokenizer(MODELE)
    except Exception as e:                                   # noqa: BLE001
        _ETAT["erreur"] = f"chargement de {MODELE}/{POIDS} impossible : {e}"
        _rendre_bail()
        return None, None, None, None
    try:
        modele = modele.to(device).eval()
        if device == "cuda":
            # Les poids font 1,5 Go en float32. Sur une carte de 4 Go partagee
            # avec Ollama et InsightFace, le float16 n'est pas un raffinement :
            # c'est ce qui rend la cohabitation possible. La perte de precision
            # est negligeable pour une recherche par similarite cosinus.
            modele = modele.half()
    except Exception:                                        # noqa: BLE001
        # Montage GPU rate (OOM au .to : le pic fp32 depasse la VRAM libre) →
        # bail rendu, repli CPU. Sans ce rendu, 1400 Mo fantomes resteraient
        # soustraits et demander() repondrait 'cuda' pour toujours (re-OOM).
        _rendre_bail()
        device = "cpu"
        modele = modele.to(device).eval()
    _ETAT.update(modele=modele, preproc=preproc, tokenizer=tokenizer,
                 device=device, demi=(device == "cuda"), erreur="")
    if device == "cuda" and _ARBITRE is not None:
        try:
            _ARBITRE[1]()              # bail materialise : la sonde le voit
        except Exception:                                    # noqa: BLE001
            pass
    return modele, preproc, tokenizer, device


# ── Encodage ─────────────────────────────────────────────────────────────────

def _charger_image(chemin):
    from PIL import Image, ImageOps
    with Image.open(chemin) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if SIGLIP_MAX_SIDE:
            im.thumbnail((SIGLIP_MAX_SIDE, SIGLIP_MAX_SIDE))
        return im.copy()


def encoder_images(chemins, lot=SIGLIP_BATCH):
    """[(chemin, vecteur float32 normalise)] ; les images illisibles sont omises."""
    import numpy as np
    import torch
    modele, preproc, _, device = encodeur()
    if modele is None:
        raise RuntimeError(_ETAT["erreur"])
    out = []
    for debut in range(0, len(chemins), lot):
        tranche = chemins[debut:debut + lot]
        tenseurs, gardes = [], []
        for c in tranche:
            try:
                tenseurs.append(preproc(_charger_image(c)))
                gardes.append(c)
            except Exception as e:                           # noqa: BLE001
                # Une image illisible ne doit pas interrompre le lot, mais
                # avaler l'erreur en silence rend un blocage indiagnostiquable :
                # on garde les dernieres pour les exposer dans l'etat.
                DERNIERES_ERREURS.append(
                    {"chemin": str(c)[-90:], "erreur": f"{type(e).__name__}: {e}"[:160]})
                del DERNIERES_ERREURS[:-ERREURS_MAX]
                continue
        if not tenseurs:
            continue
        with torch.no_grad():
            x = torch.stack(tenseurs).to(device)
            if _ETAT.get("demi"):
                x = x.half()
            v = modele.encode_image(x).float()
            v = v / v.norm(dim=-1, keepdim=True)
        out.extend(zip(gardes, v.cpu().numpy().astype(np.float32)))
    return out


def encoder_textes(textes):
    import numpy as np
    import torch
    modele, _, tokenizer, device = encodeur()
    if modele is None:
        raise RuntimeError(_ETAT["erreur"])
    with torch.no_grad():
        t = tokenizer(textes).to(device)
        v = modele.encode_text(t).float()
        v = v / v.norm(dim=-1, keepdim=True)
    return v.cpu().numpy().astype(np.float32)


# ── Vocabulaire controle ─────────────────────────────────────────────────────

VOCAB_DEFAUT = """\
# Vocabulaire controle du tagging semantique.
# Un tag par ligne. Les lignes vides et celles commencant par # sont ignorees.
# Ajouter un tag ici NE DEMANDE PAS de reanalyser les photos : seule
# l'etiquette est encodee, puis comparee aux vecteurs deja calcules.
#
# --- lieux ---
plage
montagne
neige
foret
lac
ville
interieur
jardin
restaurant
piscine
# --- moments ---
nuit
coucher de soleil
hiver
ete
# --- scenes ---
repas de famille
anniversaire
mariage
concert
voyage
randonnee
sport
# --- sujets ---
portrait
photo de groupe
enfant
bebe
chat
chien
oiseau
fleur
paysage
monument
voiture
bateau
nourriture
gateau
# --- divers ---
document scanne
capture d ecran
selfie
"""


def vocabulaire():
    if not VOCAB_FICHIER.exists():
        VOCAB_FICHIER.write_text(VOCAB_DEFAUT, encoding='utf-8')
    tags = []
    for l in VOCAB_FICHIER.read_text(encoding='utf-8').splitlines():
        l = l.strip()
        if l and not l.startswith('#'):
            tags.append(l)
    return tags


def matrice_vocabulaire():
    tags = vocabulaire()
    return tags, encoder_textes([GABARIT.format(t) for t in tags])


# ── Acces a la base ──────────────────────────────────────────────────────────

def ouvrir_magasin():
    import sqlite3
    from vectors import VectorStore
    db = SCRIPT_DIR / "photos.db"
    if not db.exists():
        raise RuntimeError(f"{db} introuvable — lance d'abord la migration.")
    cx = sqlite3.connect(str(db), isolation_level=None, timeout=30.0)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA synchronous=NORMAL")
    cx.execute("PRAGMA busy_timeout=30000")
    return cx, VectorStore(cx)


def _upload_dir():
    for nom in ("dossier_uploads.txt",):
        try:
            for l in (SCRIPT_DIR / nom).read_text(encoding='utf-8').splitlines():
                l = l.strip()
                if l and not l.startswith('#'):
                    return Path(l)
        except OSError:
            pass
    return SCRIPT_DIR


def resoudre(cle):
    """Meme regle que _resolve_key() dans server.py."""
    p = Path(cle)
    return p if p.is_absolute() else _upload_dir() / cle


def cles_a_encoder(cx, vs, limite=None):
    """Photos presentes dans l'index mais pas encore encodees."""
    deja = {k for k, in cx.execute(
        "SELECT k FROM vectors WHERE kind=? AND ver=?", (KIND, VERSION))}
    reste = [k for (k,) in cx.execute('SELECT k FROM tags') if k not in deja]
    return reste[:limite] if limite else reste


# ── Commandes ────────────────────────────────────────────────────────────────

# ── Verification d'espece ────────────────────────────────────────────────────
# YOLO11 utilise les classes COCO : ni singe, ni renard, ni lama, ni peluche.
# Tout mammifere poilu tombe donc dans « cat » ou « dog ». SigLIP, lui, sait
# repondre a la question « qu'est-ce que c'est ? » sur un vocabulaire ouvert.
#
# Le libelle francais sert au prompt ; le code sert au pipeline. Les codes
# absents de COCO (primate, faune, objet, humain, rien) marquent une detection
# a ECARTER du nommage individuel.
ESPECES = [
    ("un chat",                        "cat"),
    ("un chaton",                      "cat"),
    ("un chien",                       "dog"),
    ("un chiot",                       "dog"),
    ("un cheval",                      "horse"),
    ("une vache",                      "cow"),
    ("un mouton",                      "sheep"),
    ("une chevre",                     "sheep"),
    ("un oiseau",                      "bird"),
    ("une poule",                      "bird"),
    ("un lapin",                       "lapin"),
    ("un singe",                       "primate"),
    ("un lama ou un alpaga",           "faune"),
    ("un ecureuil",                    "faune"),
    ("un renard",                      "faune"),
    ("un ours",                        "faune"),
    ("un cerf ou une biche",           "faune"),
    ("un animal en peluche",           "objet"),
    ("une statue ou une figurine",     "objet"),
    ("un dessin ou une illustration",  "objet"),
    ("une personne, sans animal",      "humain"),
    ("un paysage sans aucun animal",   "rien"),
]

# Especes pour lesquelles un nommage individuel a du sens.
NOMMABLES = {"cat", "dog", "horse"}

_VOCAB_ESP = {"libelles": None, "codes": None, "M": None}


def matrice_especes():
    if _VOCAB_ESP["M"] is None:
        libelles = [l for l, _ in ESPECES]
        _VOCAB_ESP["libelles"] = libelles
        _VOCAB_ESP["codes"] = [c for _, c in ESPECES]
        _VOCAB_ESP["M"] = encoder_textes(libelles)
    return _VOCAB_ESP["libelles"], _VOCAB_ESP["codes"], _VOCAB_ESP["M"]


def verifier_especes(chemins):
    """[(chemin, libelle, code, score, marge)] pour des DECOUPES d'animaux."""
    import numpy as np
    libelles, codes, M = matrice_especes()
    out = []
    for chemin, v in encoder_images(list(chemins)):
        s = M @ v
        o = np.argsort(-s)
        j = int(o[0])
        marge = float(s[j] - s[int(o[1])]) if len(o) > 1 else 1.0
        out.append((chemin, libelles[j], codes[j], float(s[j]), marge))
    return out


def cmd_diagnostic():
    print("=" * 70)
    print("  DIAGNOSTIC DE LA RECHERCHE SEMANTIQUE")
    print("=" * 70)
    print(f"\n  Modele    : {MODELE} / {POIDS}")
    print(f"  Version   : {VERSION}")
    for nom, note in (("open_clip", ""),
                      ("transformers", " (tour texte de SigLIP 2)")):
        try:
            m = __import__(nom)
            print(f"  {nom:<13}: {getattr(m, '__version__', 'installe')}{note}")
        except ImportError:
            print(f"  {nom:<13}: ABSENT{note} -> lance"
                  " \"14 - Installer la recherche semantique.bat\"")
    try:
        import torch
        etat = "CUDA" if torch.version.cuda else "CPU — build sans CUDA !"
        print(f"  torch        : {torch.__version__} ({etat})")
    except ImportError:
        print("  torch        : ABSENT")
    dev, libre = _device_cible()
    print(f"  VRAM libre: {libre:.0f} Mo  -> cible {dev}"
          f" (seuil {SIGLIP_GPU_MIN_FREE_MB} Mo)")
    tags = vocabulaire()
    print(f"  Vocabulaire : {len(tags)} tags dans {VOCAB_FICHIER.name}")
    try:
        cx, vs = ouvrir_magasin()
        total = cx.execute('SELECT count(*) FROM tags').fetchone()[0]
        faits = cx.execute("SELECT count(*) FROM vectors WHERE kind=? AND ver=?",
                           (KIND, VERSION)).fetchone()[0]
        print(f"  Photos    : {faits:,} encodees sur {total:,}".replace(',', ' '))
        cx.close()
    except Exception as e:                                   # noqa: BLE001
        print(f"  Base      : {e}")
    print()
    return 0


def cmd_banc(n=20):
    """Mesure sur de VRAIES photos du corpus : vitesse, VRAM, extrapolation."""
    print("=" * 70)
    print(f"  BANC D'ESSAI SUR {n} PHOTOS REELLES")
    print("=" * 70)
    cx, vs = ouvrir_magasin()
    total = cx.execute('SELECT count(*) FROM tags').fetchone()[0]
    cles = [k for (k,) in cx.execute('SELECT k FROM tags LIMIT ?', (n * 3,))]
    chemins = [resoudre(k) for k in cles]
    chemins = [p for p in chemins if p.exists()][:n]
    cx.close()
    if not chemins:
        print("  Aucune photo accessible (NAS monte ?).")
        return 1

    dev, libre = _device_cible()
    print(f"\n  VRAM libre avant chargement : {libre:.0f} Mo -> {dev}")
    t0 = time.perf_counter()
    modele, _, _, device = encodeur()
    if modele is None:
        print(f"  x {_ETAT['erreur']}")
        return 1
    print(f"  Modele charge en {time.perf_counter()-t0:.1f} s sur {device}")
    print(f"  VRAM libre apres chargement : {_vram_libre_mb():.0f} Mo")

    encoder_images(chemins[:2])                              # prechauffage
    t0 = time.perf_counter()
    res = encoder_images(chemins)
    dt = time.perf_counter() - t0
    if not res:
        print("  x aucune image encodee")
        return 1
    par_img = dt / len(res)
    print(f"\n  {len(res)} images encodees en {dt:.1f} s"
          f"  ->  {par_img*1000:.0f} ms par image")
    print(f"  Dimension du vecteur : {len(res[0][1])}")
    print(f"  VRAM libre pendant l'encodage : {_vram_libre_mb():.0f} Mo")
    print(f"\n  Extrapolation sur {total:,} photos : "
          f"{par_img*total/60:.0f} minutes".replace(',', ' '))
    print(f"  Stockage : {total*len(res[0][1])*2/1048576:.0f} Mo en float16")

    # Verification de sens : les tags proposes doivent decrire la photo.
    print("\n" + "=" * 70)
    print("  CONTROLE DE COHERENCE  -  A LIRE ATTENTIVEMENT")
    print("=" * 70)
    print("  Ouvre chaque photo ci-dessous et compare aux tags proposes.")
    print("  Ce qui compte est l'ORDRE, pas la valeur : le premier tag")
    print("  doit decrire la photo. Les scores SigLIP sont typiquement")
    print("  compris entre 0,05 et 0,35 - un score bas n'est pas un defaut.")
    print()
    import numpy as np
    tags, M = matrice_vocabulaire()
    V = np.stack([v for _, v in res])
    scores = V @ M.T
    for i in range(min(6, len(res))):
        top = np.argsort(-scores[i])[:3]
        print(f"  {res[i][0]}")
        print("      -> " + " | ".join(f"{tags[j]} {scores[i][j]:.2f}"
                                       for j in top))
    print()
    print("  VERDICT")
    print("  - Tags plausibles sur la plupart des photos : on peut indexer.")
    print("  - Tags absurdes ou tous identiques : arrete-toi, le modele ou")
    print("    le gabarit de prompt est en cause. Copie cette sortie et")
    print("    montre-la, on corrige avant d'encoder 30 000 images.")
    print()
    return 0


def cmd_indexer(limite=None, bavard=True):
    cx, vs = ouvrir_magasin()
    reste = cles_a_encoder(cx, vs, limite)
    if not reste:
        print("  Toutes les photos sont deja encodees.")
        cx.close()
        return 0
    print(f"  {len(reste):,} photo(s) a encoder...".replace(',', ' '))
    import numpy as np
    faits = t_total = 0
    for debut in range(0, len(reste), SIGLIP_BATCH * 4):
        paquet = reste[debut:debut + SIGLIP_BATCH * 4]
        chemins = {str(resoudre(k)): k for k in paquet}
        existants = [p for p in chemins if Path(p).exists()]
        if not existants:
            continue
        t0 = time.perf_counter()
        res = encoder_images(existants)
        t_total += time.perf_counter() - t0
        import base64
        vs.put_many_b64(
            KIND,
            [(chemins[str(p)], base64.b64encode(
                v.astype(np.float16).tobytes()).decode()) for p, v in res],
            ver=VERSION)
        faits += len(res)
        if bavard and faits:
            print(f"    {faits:>6,}/{len(reste):,}  "
                  f"{t_total/max(faits,1)*1000:.0f} ms/image".replace(',', ' '))
    cx.close()
    print(f"  + {faits} photo(s) encodee(s)")
    return 0


def cmd_chercher(requete, limite=20):
    cx, vs = ouvrir_magasin()
    q = encoder_textes([requete])[0]
    t0 = time.perf_counter()
    res = vs.search(KIND, q, limite=limite)
    dt = (time.perf_counter() - t0) * 1000
    print(f"\n  « {requete} »  —  {len(res)} resultats en {dt:.1f} ms\n")
    for k, s in res:
        print(f"    {s:.3f}  {k[:80]}")
    cx.close()
    print()
    return 0


def cmd_tags(n=20, seuil=0.12):
    """Tagging par vocabulaire controle sur les photos deja encodees."""
    import numpy as np
    cx, vs = ouvrir_magasin()
    cles, M = vs.matrice(KIND)
    if not cles:
        print("  Aucune photo encodee : lance --indexer d'abord.")
        cx.close()
        return 1
    tags, T = matrice_vocabulaire()
    for k, v in list(zip(cles, M))[:n]:
        s = T @ v
        top = [(tags[j], float(s[j])) for j in np.argsort(-s)[:4]
               if s[j] >= seuil]
        print(f"  {k[:56]:<56} " + ", ".join(f"{t} {x:.2f}" for t, x in top))
    cx.close()
    print()
    return 0


EVAL_DIR = SCRIPT_DIR / "eval"
ECHANT_DIR = EVAL_DIR / "echantillon"
ECHANT_JSON = EVAL_DIR / "echantillon.json"
VERITE_JSON = EVAL_DIR / "verite.json"


def _echantillon_stable(cles, n):
    """Tirage reproductible : meme corpus -> meme echantillon, toujours.

    Un jeu d'evaluation qui change a chaque execution ne permet pas de
    comparer deux modeles entre eux (cf. skill vision-eval).
    """
    import hashlib
    return [k for _, k in sorted(
        (hashlib.blake2b(k.encode('utf-8'), digest_size=8).digest(), k)
        for k in cles)][:n]


def cmd_exporter(n=24, cote=640):
    """Copie un echantillon reduit dans eval/ pour relecture humaine.

    ATTENTION : ce sont de VRAIES photos de famille. Elles sont copiees
    dans le dossier du projet pour pouvoir etre examinees. Supprime
    eval/echantillon/ quand l'evaluation est terminee.
    """
    import json
    import numpy as np
    from PIL import Image, ImageOps

    cx, vs = ouvrir_magasin()
    toutes = [k for (k,) in cx.execute('SELECT k FROM tags')]
    cx.close()
    choisies = _echantillon_stable(toutes, n * 3)

    ECHANT_DIR.mkdir(parents=True, exist_ok=True)
    for vieux in ECHANT_DIR.glob("*.jpg"):
        vieux.unlink()

    retenues = []
    for cle in choisies:
        src = resoudre(cle)
        if src.exists():
            retenues.append((cle, src))
        if len(retenues) >= n:
            break
    if not retenues:
        print("  Aucune photo accessible (NAS monte ?).")
        return 1

    print(f"  Encodage de {len(retenues)} photos...")
    res = dict(encoder_images([s for _, s in retenues]))
    tags, T = matrice_vocabulaire()

    fiches = []
    for i, (cle, src) in enumerate(retenues):
        v = res.get(src)
        if v is None:
            continue
        nom = f"{i:03d}.jpg"
        try:
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((cote, cote))
                im.save(ECHANT_DIR / nom, "JPEG", quality=80)  # EXIF non recopie
        except Exception as e:                                # noqa: BLE001
            print(f"  ! {src.name} : {e}")
            continue
        s = T @ v
        ordre = np.argsort(-s)[:5]
        # Le VECTEUR de l'image est conserve : changer le vocabulaire ou le
        # gabarit de prompt se reevalue alors sans relire une seule photo
        # (seules les etiquettes texte sont reencodees, ce qui est instantane).
        import base64
        fiches.append({"fichier": nom, "cle": cle,
                       "tags": [[tags[j], round(float(s[j]), 4)] for j in ordre],
                       "vecteur": base64.b64encode(
                           v.astype(np.float16).tobytes()).decode()})

    EVAL_DIR.mkdir(exist_ok=True)
    ECHANT_JSON.write_text(json.dumps(
        {"version": VERSION, "modele": MODELE, "poids": POIDS,
         "gabarit": GABARIT, "vocabulaire": tags, "photos": fiches},
        ensure_ascii=False, indent=1), encoding='utf-8')

    print(f"\n  + {len(fiches)} photos dans {ECHANT_DIR}")
    print(f"  + propositions de tags dans {ECHANT_JSON.name}")
    print("\n  Montre ces deux elements a Claude : il ouvrira les images,")
    print("  jugera les tags et ecrira eval/verite.json.")
    print("  Ensuite : semantic.py --evaluer  (rejouable a chaque changement)")
    print("\n  Ce sont de vraies photos de famille, copiees en 640 px dans le")
    print("  projet. Supprime eval/echantillon/ quand tu as termine.")
    return 0


def cmd_evaluer(k=3):
    """Compare les tags proposes a la verite terrain de eval/verite.json."""
    import json
    if not ECHANT_JSON.exists():
        print("  Lance d'abord : semantic.py --exporter")
        return 1
    if not VERITE_JSON.exists():
        print(f"  {VERITE_JSON} absent.")
        print("  Fais annoter l'echantillon par Claude, ou ecris-le a la main :")
        print('    {"000.jpg": ["plage", "ete"], "001.jpg": ["portrait"]}')
        return 1
    ech = json.loads(ECHANT_JSON.read_text(encoding='utf-8'))
    verite = json.loads(VERITE_JSON.read_text(encoding='utf-8'))

    # Rescoring : si les vecteurs d'images sont conserves, on recalcule les tags
    # avec le vocabulaire ACTUEL. Un tag ajoute est donc mesurable tout de suite,
    # sans relire les photos ni refaire l'export.
    mode = "tags figes a l'export"
    if all("vecteur" in f for f in ech["photos"]):
        try:
            import base64
            import numpy as np
            tags, T = matrice_vocabulaire()
            for f in ech["photos"]:
                v = np.frombuffer(base64.b64decode(f["vecteur"]),
                                  dtype=np.float16).astype(np.float32)
                s = T @ (v / (np.linalg.norm(v) or 1.0))
                f["tags"] = [[tags[j], round(float(s[j]), 4)]
                             for j in np.argsort(-s)[:5]]
            mode = f"recalcule sur le vocabulaire actuel ({len(tags)} tags)"
        except Exception as e:                               # noqa: BLE001
            mode = f"tags figes ({e})"

    n = top1 = rappel = 0
    desaccords = []
    for f in ech["photos"]:
        attendus = {t.lower() for t in verite.get(f["fichier"], [])}
        if not attendus:
            continue
        n += 1
        proposes = [t.lower() for t, _ in f["tags"][:k]]
        if proposes and proposes[0] in attendus:
            top1 += 1
        else:
            desaccords.append((f["fichier"], proposes[0] if proposes else "-",
                               sorted(attendus)))
        if attendus & set(proposes):
            rappel += 1

    print("=" * 70)
    print("  EVALUATION DU TAGGING PAR VOCABULAIRE CONTROLE")
    print("=" * 70)
    print(f"  Modele    : {ech.get('modele')} / {ech.get('poids')}")
    print(f"  Version   : {ech.get('version')}")
    print(f"  Gabarit   : {ech.get('gabarit')}")
    print(f"  Tags      : {mode}")
    print(f"  Annotees  : {n} photos sur {len(ech['photos'])}")
    if not n:
        print("  Aucune photo annotee.")
        return 1
    print()
    print(f"  Justesse au rang 1  : {100*top1/n:5.1f} %  ({top1}/{n})")
    print(f"  Rappel dans le top {k}: {100*rappel/n:5.1f} %  ({rappel}/{n})")
    if desaccords:
        print(f"\n  Desaccords au rang 1 ({len(desaccords)}) :")
        for f, p, a in desaccords[:12]:
            print(f"    {f}  propose « {p} »  attendu {a}")
    print()
    print("  Consigne les resultats dans eval/DECISIONS.md avant de changer")
    print("  quoi que ce soit : sans trace ecrite, on reteste deux fois le")
    print("  meme reglage six mois plus tard (cf. skill vision-eval).")
    print()
    return 0


def main():
    args = sys.argv[1:]
    def val(drapeau, defaut):
        if drapeau in args:
            i = args.index(drapeau)
            if i + 1 < len(args):
                try:
                    return int(args[i + 1])
                except ValueError:
                    pass
        return defaut

    if '--banc' in args:
        return cmd_banc(val('--banc', 20))
    if '--exporter' in args:
        return cmd_exporter(val('--exporter', 24))
    if '--evaluer' in args:
        return cmd_evaluer()
    if '--indexer' in args:
        return cmd_indexer(val('--indexer', 0) or None)
    if '--tags' in args:
        return cmd_tags(val('--tags', 20))
    if '--chercher' in args:
        i = args.index('--chercher')
        if i + 1 < len(args):
            return cmd_chercher(args[i + 1])
        print("  Usage : --chercher \"ta requete\"")
        return 1
    return cmd_diagnostic()


if __name__ == '__main__':
    sys.exit(main())
