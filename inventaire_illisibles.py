"""
Inventaire et recuperation des images illisibles.
──────────────────────────────────────────────────────────────────────────────

CONTEXTE
    987 photos sur 30 682 portent `failed: True` : ni tagues, ni analysees
    pour les visages ou les animaux, invisibles a tout le systeme. Sequelles
    probables d'un crash disque suivi d'une recuperation professionnelle.

    Un fichier peut echouer pour des raisons TRES differentes, qui n'appellent
    pas le meme traitement :

      - 0 octet                  perdu, rien a tenter
      - JPEG tronque             le debut est la : recuperable en grande partie
      - JPEG a l'en-tete abime   parfois recuperable en reconstruisant
      - format non reconnu       PAS corrompu du tout — il manque un decodeur
                                 (RAW Pentax .PEF renomme .JPG, HEIC, TIFF)
      - octets aleatoires        ce que la recuperation a rendu : perdu

    Les distinguer demande de lire les PREMIERS OCTETS, pas l'extension.

GARANTIE
    Ce script NE MODIFIE JAMAIS un original. Les images reconstruites sont
    ecrites dans un dossier separe, et l'inventaire est en lecture seule.

USAGE
    python inventaire_illisibles.py                # inventaire, lecture seule
    python inventaire_illisibles.py --reparer      # tente la recuperation
    python inventaire_illisibles.py --exporter 12  # echantillon a relire
"""

import json
import shutil
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

DB = SCRIPT_DIR / "photos.db"
SORTIE = SCRIPT_DIR / "recuperees"
RAPPORT = SCRIPT_DIR / "eval" / "illisibles.json"
ECHANT = SCRIPT_DIR / "eval" / "illisibles"

# Signatures reelles, lues dans le fichier — l'extension ment souvent apres
# une recuperation de disque.
SIGNATURES = [
    (b'\xff\xd8\xff',              'jpeg'),
    (b'\x89PNG\r\n\x1a\n',         'png'),
    (b'II*\x00',                   'tiff/raw'),   # Pentax PEF, Nikon NEF, DNG
    (b'MM\x00*',                   'tiff/raw'),
    (b'GIF8',                      'gif'),
    (b'BM',                        'bmp'),
    (b'RIFF',                      'webp?'),
    (b'\x00\x00\x00\x18ftyp',      'heic/mp4'),
    (b'\x00\x00\x00\x1cftyp',      'heic/mp4'),
    (b'PK\x03\x04',                'zip?'),
]

JPEG_DEBUT = b'\xff\xd8\xff'
JPEG_FIN = b'\xff\xd9'


def _upload_dir():
    try:
        for l in (SCRIPT_DIR / "dossier_uploads.txt").read_text(
                encoding='utf-8').splitlines():
            l = l.strip()
            if l and not l.startswith('#'):
                return Path(l)
    except OSError:
        pass
    return SCRIPT_DIR


def resoudre(cle):
    p = Path(cle)
    return p if p.is_absolute() else _upload_dir() / cle


def signature(tete):
    for magie, nom in SIGNATURES:
        if tete.startswith(magie):
            return nom
    if not tete:
        return 'vide'
    return 'inconnu'


def diagnostiquer(chemin):
    """Renvoie un dict decrivant l'etat reel du fichier."""
    d = {"existe": False, "taille": 0, "format": None, "etat": None,
         "tete": "", "mtime": None}
    try:
        st = chemin.stat()
    except OSError as e:
        d["etat"] = f"introuvable ({type(e).__name__})"
        return d
    d["existe"] = True
    d["taille"] = st.st_size
    d["mtime"] = time.strftime('%Y-%m-%d', time.localtime(st.st_mtime))
    if st.st_size == 0:
        d["format"], d["etat"] = 'vide', 'perdu (0 octet)'
        return d
    try:
        with open(chemin, 'rb') as f:
            tete = f.read(32)
            f.seek(max(0, st.st_size - 4))
            queue = f.read(4)
    except OSError as e:
        d["etat"] = f"illisible ({type(e).__name__})"
        return d
    d["tete"] = tete[:12].hex()
    d["format"] = signature(tete)

    if d["format"] == 'jpeg':
        d["etat"] = ('jpeg complet (erreur ailleurs)' if JPEG_FIN in queue
                     else 'jpeg tronque')
    elif d["format"] == 'tiff/raw':
        d["etat"] = 'format brut non decode (decodeur manquant)'
    elif d["format"] in ('heic/mp4',):
        d["etat"] = 'heic — decodeur manquant'
    elif d["format"] == 'inconnu':
        d["etat"] = 'octets non identifiables (perdu ?)'
    else:
        d["etat"] = f'{d["format"]} — a verifier'
    return d


def jpeg_incorpore(donnees):
    """Cherche un flux JPEG complet dans le fichier (miniature EXIF, apercu RAW).

    C'est souvent le SEUL survivant d'un fichier abime : les appareils
    incorporent un apercu pleine largeur dans les RAW, et l'EXIF d'un JPEG
    contient une miniature independante de l'image principale.
    """
    meilleur = None
    debut = donnees.find(JPEG_DEBUT)
    while debut != -1:
        fin = donnees.find(JPEG_FIN, debut + 3)
        if fin == -1:
            break
        bloc = donnees[debut:fin + 2]
        if meilleur is None or len(bloc) > len(meilleur):
            meilleur = bloc
        debut = donnees.find(JPEG_DEBUT, fin + 2)
    return meilleur


def _sauver(im, cible):
    """Ecrit l'image en respectant son orientation.

    Sans exif_transpose, une photo prise en portrait ressort COUCHEE : le
    capteur enregistre en paysage et l'orientation vit dans l'EXIF, qui ne
    survit pas a la reconstruction. On grave donc la rotation dans les pixels.
    """
    from PIL import ImageOps
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:                                        # noqa: BLE001
        pass
    im = im.convert('RGB')
    im.save(cible, 'JPEG', quality=92)
    return im.size


def tenter_recuperation(chemin, cible, profond=True):
    """(succes, methode, detail). N'ecrit jamais sur l'original."""
    from PIL import Image, ImageFile

    # 1) JPEG tronque : Pillow sait terminer une image incomplete.
    ancien = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    try:
        with Image.open(chemin) as im:
            taille = _sauver(im, cible)
        return True, 'pillow (image tronquee acceptee)', f"{taille[0]}x{taille[1]}"
    except Exception:                                        # noqa: BLE001
        pass
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = ancien

    # 2) Decodeur brut, si rawpy est installe (Pentax PEF, Nikon NEF, DNG…)
    try:
        import rawpy
        with rawpy.imread(str(chemin)) as brut:
            from PIL import Image as I
            I.fromarray(brut.postprocess()).save(cible, 'JPEG', quality=92)
        return True, 'rawpy (format brut)', ''
    except ImportError:
        pass
    except Exception:                                        # noqa: BLE001
        pass

    # 3) Dernier recours : chercher un flux JPEG N'IMPORTE OU dans le fichier.
    # C'est la seule chance des fichiers dont l'EN-TETE est detruit mais dont
    # les donnees survivent plus loin — le cas le plus frequent apres une
    # recuperation de disque, qui rend des secteurs bruts.
    if not profond:
        return False, '', 'analyse profonde non demandee'
    try:
        donnees = chemin.read_bytes()
    except OSError:
        return False, '', 'lecture impossible'
    bloc = jpeg_incorpore(donnees)
    if bloc and len(bloc) > 4096:
        from PIL import Image, ImageFile
        import io
        ancien = ImageFile.LOAD_TRUNCATED_IMAGES
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            with Image.open(io.BytesIO(bloc)) as im:
                taille = _sauver(im, cible)
            return (True, 'flux JPEG retrouve dans le fichier',
                    f"{taille[0]}x{taille[1]}, {len(bloc)//1024} Ko")
        except Exception:                                    # noqa: BLE001
            cible.write_bytes(bloc)      # illisible par PIL mais peut-etre par
            return True, 'fragment JPEG brut extrait', f"{len(bloc)//1024} Ko"
        finally:
            ImageFile.LOAD_TRUNCATED_IMAGES = ancien
    return False, '', 'aucune donnee exploitable'


def charger_illisibles():
    if not DB.exists():
        raise SystemExit(f"  Base introuvable : {DB}")
    cx = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cles = []
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            if json.loads(v).get('failed'):
                cles.append(k)
        except ValueError:
            continue
    cx.close()
    return cles


def main():
    args = sys.argv[1:]
    reparer = '--reparer' in args

    print("=" * 74)
    print("  INVENTAIRE DES IMAGES ILLISIBLES")
    print("=" * 74)
    cles = charger_illisibles()
    print(f"  {len(cles)} fichiers marques illisibles dans l'index\n")
    if not cles:
        return 0

    fiches = []
    etats = Counter()
    formats = Counter()
    t0 = time.time()
    for i, k in enumerate(cles, 1):
        d = diagnostiquer(resoudre(k))
        d["cle"] = k
        fiches.append(d)
        etats[d["etat"]] += 1
        formats[d["format"] or '-'] += 1
        if i % 100 == 0:
            print(f"    {i}/{len(cles)}…", flush=True)
    print(f"  inventaire en {time.time()-t0:.0f} s\n")

    print("  ── ce que contiennent reellement ces fichiers ──")
    for etat, n in etats.most_common():
        print(f"    {n:>5}  {etat}")
    print()
    print("  ── signature reelle (l'extension ment apres une recuperation) ──")
    for f, n in formats.most_common():
        print(f"    {n:>5}  {f}")
    print()

    # Tout fichier NON VIDE merite une tentative : un en-tete detruit ne veut
    # pas dire que les donnees le sont. Seuls les 0 octet sont sans espoir.
    recuperables = [f for f in fiches if f["existe"] and f["taille"] > 0]
    perdus = [f for f in fiches if not f["existe"] or f["taille"] == 0]
    entete_sain = [f for f in recuperables
                   if f["etat"] and ('tronque' in f["etat"]
                                     or 'complet' in f["etat"]
                                     or 'decodeur' in f["etat"]
                                     or 'non decode' in f["etat"])]
    print(f"  A tenter                    : {len(recuperables)}")
    print(f"    dont en-tete encore lisible : {len(entete_sain)}")
    print(f"    dont en-tete detruit        : {len(recuperables)-len(entete_sain)}"
          "  (recherche de flux JPEG dans le fichier)")
    print(f"  Sans espoir (0 octet)       : {len(perdus)}")
    print()

    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text(json.dumps({"fichiers": fiches}, ensure_ascii=False,
                                  indent=1), encoding='utf-8')
    print(f"  + inventaire complet : {RAPPORT}")

    if '--exporter' in args:
        i = args.index('--exporter')
        n = int(args[i+1]) if i+1 < len(args) and args[i+1].isdigit() else 12
        ECHANT.mkdir(parents=True, exist_ok=True)
        for vieux in ECHANT.glob('*'):
            vieux.unlink()
        pris = 0
        for f in fiches:
            if pris >= n or not f["existe"] or f["taille"] == 0:
                continue
            try:
                src = resoudre(f["cle"])
                shutil.copy2(src, ECHANT / f"{pris:03d}_{src.name}")
                pris += 1
            except OSError:
                continue
        print(f"  + {pris} fichiers copies dans {ECHANT} (pour analyse)")

    if not reparer:
        print()
        print("  LECTURE SEULE — rien n'a ete ecrit ni modifie.")
        print("  Relancer avec --reparer pour tenter la recuperation.")
        print()
        return 0

    print()
    print("=" * 74)
    print("  RECUPERATION")
    print("=" * 74)
    print(f"  Les images reconstruites vont dans {SORTIE}.")
    print("  Les originaux ne sont JAMAIS modifies.\n")
    SORTIE.mkdir(parents=True, exist_ok=True)
    methodes = Counter()
    reussites = []
    for i, f in enumerate(recuperables, 1):
        if not f["existe"]:
            continue
        src = resoudre(f["cle"])
        cible = SORTIE / (src.stem + "__recup.jpg")
        n = 1
        while cible.exists():
            cible = SORTIE / f"{src.stem}__recup_{n}.jpg"
            n += 1
        try:
            ok, methode, detail = tenter_recuperation(src, cible)
        except Exception as e:                               # noqa: BLE001
            ok, methode, detail = False, '', f"{type(e).__name__}"
        if ok:
            methodes[methode] += 1
            reussites.append({"cle": f["cle"], "sortie": cible.name,
                              "methode": methode, "detail": detail})
        else:
            methodes[f"echec ({detail})"] += 1
            if cible.exists():
                cible.unlink()
        if i % 50 == 0:
            print(f"    {i}/{len(recuperables)}…", flush=True)

    print()
    for m, n in methodes.most_common():
        print(f"    {n:>5}  {m}")
    total = len(reussites)
    print()
    print(f"  {total} image(s) recuperee(s) sur {len(recuperables)} tentees")
    print(f"  → {SORTIE}")
    print()
    print("  Regarde-les avant d'en faire quoi que ce soit : une image")
    print("  reconstruite peut etre partielle (bas de l'image gris ou raye).")
    print("  Rien n'a ete remplace : tes originaux sont intacts.")
    (RAPPORT.parent / "recuperees.json").write_text(
        json.dumps({"recuperees": reussites}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    print(f"  + journal : {RAPPORT.parent / 'recuperees.json'}")
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
