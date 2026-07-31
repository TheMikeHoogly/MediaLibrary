#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recensement_doublons.py — Phase 0 du chantier « Rangement & dedoublonnage ».

But : un CHIFFRE, pas une intuition. Ce script est en LECTURE SEULE. Il
n'ecrit rien d'autre que ses deux rapports (recensement.json + recensement.md) ;
il ne touche jamais un fichier photo, ni `photos.db`, ni le NAS.

Il repond aux questions que l'index seul ne peut pas trancher (cf.
docs/RANGEMENT_2026.md) :
  - Combien de doublons EXACTS (par contenu, pas par nom) ?
  - Combien d'octets recuperables ?
  - Quelle repartition entre la zone de transit `_A TRIER` et les dossiers annee ?
  - Combien de fichiers sans date fiable (candidats `_SANS_DATE`) ?
  - Quelles sont les plus grosses annees ?

Algorithme (taille d'abord, hash ensuite — JAMAIS le nom) :
  1. Enumerer tous les fichiers medias sous les racines reelles.
  2. Grouper par TAILLE. Une taille unique ne peut pas avoir de doublon : on ne
     la hashe pas (economie majeure).
  3. Pour chaque groupe de meme taille (>= 2) : hash rapide (premiers + derniers
     64 Ko), re-grouper ; puis sha256 complet uniquement sur les sous-groupes
     encore colles. Meme sha256 = doublons exacts, quel que soit le nom.

Les racines sont lues dans les memes fichiers de config que server.py
(dossier_uploads.txt, dossiers_a_taguer.txt, dossiers_a_explorer.txt), ou
surchargees par --root pour tester en local.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# Extensions medias — memes valeurs que server.py (IMAGE_EXT) + les videos.
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif',
             '.bmp', '.tiff', '.tif'}
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.wmv'}
MEDIA_EXT = IMAGE_EXT | VIDEO_EXT

QUICK_BYTES = 64 * 1024          # taille lue aux deux bouts pour le hash rapide
_YEAR_DIR_RE = re.compile(r'^(19\d{2}|20\d{2})$')


# ─────────────────────────── lecture des racines ───────────────────────────

def _read_config_lines(name):
    """Lignes utiles d'un fichier de config (# = commentaire, guillemets otes)."""
    out = []
    try:
        for line in (SCRIPT_DIR / name).read_text(encoding='utf-8').splitlines():
            line = line.strip().strip('"')
            if line and not line.startswith('#'):
                out.append(line)
    except OSError:
        pass
    return out


def media_roots(cli_roots=None):
    """Racines reelles a recenser, dedupliquees (insensible a la casse).
    Repro fidele de server.media_roots() : Uploads + tagues + explores.
    --root surcharge entierement la config (utile pour un test local)."""
    raw = []
    if cli_roots:
        raw = list(cli_roots)
    else:
        up = _read_config_lines('dossier_uploads.txt')
        raw = up[:1] + _read_config_lines('dossiers_a_taguer.txt') \
            + _read_config_lines('dossiers_a_explorer.txt')
    roots, seen = [], set()
    for r in raw:
        p = Path(r)
        k = str(p).lower().rstrip('\\/')
        if k in seen:
            continue
        seen.add(k)
        roots.append(p)
    return roots


def _is_hidden_path(p):
    """Vrai si un composant du chemin est cache : .thumbs, @eaDir, #recycle…
    Meme regle que server._is_hidden_path."""
    return any(part.startswith(('.', '@', '#')) for part in Path(p).parts)


# ─────────────────────────── dates (lecture seule) ──────────────────────────

def _fname_time(name):
    """Date encodee dans le nom de fichier. Repro de server._fname_time."""
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


def _path_year(path):
    """Annee trouvee dans le CHEMIN (dossier date). Repro de server._path_year.
    Repli APPROXIMATIF : ne compte pas comme une date fiable."""
    yrs = [int(y) for y in re.findall(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)', str(path))
           if 1990 <= int(y) <= 2100]
    if not yrs:
        return 0
    try:
        return time.mktime((min(yrs), 1, 1, 12, 0, 0, 0, 0, -1))
    except (ValueError, OverflowError):
        return 0


_EXIF_DT_RE = re.compile(r'\s*(\d{4}):(\d{2}):(\d{2})')


def _exif_time(path):
    """Date EXIF de prise de vue (DateTimeOriginal / DateTimeDigitized / DateTime),
    lue via Pillow. Renvoie un epoch, ou None si absente/illisible/non-image.
    LECTURE SEULE : ne lit que l'en-tete du fichier."""
    if Image is None or path.suffix.lower() not in IMAGE_EXT:
        return None
    try:
        with Image.open(path) as im:
            exif = im.getexif()
    except Exception:
        return None
    if not exif:
        return None
    # 36867 = DateTimeOriginal, 36868 = DateTimeDigitized, 306 = DateTime
    for tag in (36867, 36868, 306):
        v = exif.get(tag)
        if not v:
            # sous-IFD Exif pour DateTimeOriginal/Digitized
            try:
                sub = exif.get_ifd(0x8769)
                v = sub.get(tag)
            except Exception:
                v = None
        if not v or not isinstance(v, str):
            continue
        m = _EXIF_DT_RE.match(v)
        if not m:
            continue
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
            continue
        try:
            return time.mktime((y, mo, d, 12, 0, 0, 0, 0, -1))
        except (ValueError, OverflowError):
            continue
    return None


def date_info(path):
    """Renvoie (epoch, source) pour un fichier. source est l'un de :
    'exif', 'nom', 'chemin' (approx.), 'aucune'. Une date FIABLE = exif ou nom."""
    t = _exif_time(path)
    if t:
        return t, 'exif'
    t = _fname_time(path.name)
    if t:
        return t, 'nom'
    py = _path_year(path)
    if py:
        return py, 'chemin'
    return 0, 'aucune'


# ─────────────────────────── classement des chemins ─────────────────────────

def zone_of(path):
    """Classe un chemin : 'a_trier' si un composant ressemble a _A TRIER,
    'annee' si un composant est une annee (AAAA), sinon 'autre'."""
    a_trier = False
    annee = False
    for part in Path(path).parts:
        norm = part.upper().replace(' ', '').replace('_', '')
        if 'ATRIER' in norm:
            a_trier = True
        if _YEAR_DIR_RE.match(part.strip()):
            annee = True
    if a_trier:
        return 'a_trier'
    if annee:
        return 'annee'
    return 'autre'


def canonical(paths):
    """Choisit la copie canonique d'un groupe de doublons.
    Regle (cf. RANGEMENT_2026) : dossier annee > _A TRIER ; a defaut, chemin le
    plus court (souvent le mieux range). La copie `_A TRIER` est presque toujours
    celle a retirer — c'est le geste que Mike fait a la main."""
    def rank(p):
        z = zone_of(p)
        z_score = {'annee': 0, 'autre': 1, 'a_trier': 2}[z]
        return (z_score, len(str(p)), str(p).lower())
    return min(paths, key=rank)


# ─────────────────────────── hachage par contenu ────────────────────────────

def quick_hash(path):
    """Empreinte bon marche : premiers + derniers QUICK_BYTES octets + taille."""
    h = hashlib.sha1()
    try:
        size = path.stat().st_size
        with open(path, 'rb') as f:
            head = f.read(QUICK_BYTES)
            h.update(head)
            if size > QUICK_BYTES:
                f.seek(max(size - QUICK_BYTES, QUICK_BYTES))
                h.update(f.read(QUICK_BYTES))
        h.update(str(size).encode())
    except OSError:
        return None
    return h.hexdigest()


def full_hash(path):
    """sha256 complet, par blocs de 1 Mo."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


# ─────────────────────────── parcours principal ─────────────────────────────

def enumerate_files(roots, log):
    """Enumere (path, size, mtime) pour tous les medias non caches sous roots."""
    files = []
    seen_paths = set()
    for root in roots:
        if not root.exists():
            log(f"  ATTENTION racine introuvable, ignoree : {root}")
            continue
        log(f"  parcours de {root} …")
        n0 = len(files)
        for dirpath, dirnames, filenames in os.walk(root):
            # elaguer les dossiers caches (.thumbs, @eaDir, #recycle…)
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(('.', '@', '#'))]
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext not in MEDIA_EXT:
                    continue
                p = Path(dirpath) / name
                if _is_hidden_path(p):
                    continue
                key = str(p).lower()
                if key in seen_paths:      # racines qui se recouvrent
                    continue
                seen_paths.add(key)
                try:
                    st = p.stat()
                except OSError:
                    continue
                files.append((p, st.st_size, st.st_mtime))
        log(f"    {len(files) - n0} fichiers medias")
    return files


def find_exact_duplicates(files, log):
    """Renvoie une liste de groupes de doublons exacts (>= 2 fichiers identiques).
    Chaque groupe = {'sha256', 'size', 'paths': [...]}. Ne hashe que les
    collisions de taille, puis les collisions de hash rapide."""
    by_size = defaultdict(list)
    for p, size, _ in files:
        by_size[size].append(p)

    candidates = {s: ps for s, ps in by_size.items() if len(ps) >= 2}
    n_cand = sum(len(ps) for ps in candidates.values())
    log(f"  {len(candidates)} tailles partagees, {n_cand} fichiers a examiner "
        f"(sur {len(files)}).")

    # etape 1 : hash rapide
    by_quick = defaultdict(list)
    done = 0
    for size, ps in candidates.items():
        for p in ps:
            qh = quick_hash(p)
            done += 1
            if done % 500 == 0:
                log(f"    hash rapide {done}/{n_cand} …")
            if qh is not None:
                by_quick[(size, qh)].append(p)

    # etape 2 : sha256 complet sur les collisions de hash rapide
    groups = []
    still = {k: ps for k, ps in by_quick.items() if len(ps) >= 2}
    n_full = sum(len(ps) for ps in still.values())
    log(f"  {n_full} fichiers passent au sha256 complet.")
    by_full = defaultdict(list)
    done = 0
    for (size, _qh), ps in still.items():
        for p in ps:
            fh = full_hash(p)
            done += 1
            if done % 200 == 0:
                log(f"    sha256 {done}/{n_full} …")
            if fh is not None:
                by_full[(size, fh)].append(p)

    for (size, sha), ps in by_full.items():
        if len(ps) >= 2:
            groups.append({'sha256': sha, 'size': size, 'paths': ps})
    # trier : plus gros gain d'abord
    groups.sort(key=lambda g: g['size'] * (len(g['paths']) - 1), reverse=True)
    return groups


# ─────────────────────────── rapports ───────────────────────────────────────

def human_bytes(n):
    for unit in ('o', 'Ko', 'Mo', 'Go', 'To'):
        if n < 1024 or unit == 'To':
            return f"{n:.1f} {unit}" if unit != 'o' else f"{n} o"
        n /= 1024


def build_reports(files, groups, out_dir, log):
    total = len(files)
    total_bytes = sum(s for _, s, _ in files)

    # zones
    zones = {'a_trier': 0, 'annee': 0, 'autre': 0}
    zone_bytes = {'a_trier': 0, 'annee': 0, 'autre': 0}
    for p, size, _ in files:
        z = zone_of(p)
        zones[z] += 1
        zone_bytes[z] += size

    # dates fiables + histogramme par annee
    log("  lecture des dates (EXIF/nom/chemin) …")
    src_count = {'exif': 0, 'nom': 0, 'chemin': 0, 'aucune': 0}
    year_hist = defaultdict(int)
    sans_date = []
    for i, (p, size, mt) in enumerate(files):
        if i and i % 1000 == 0:
            log(f"    dates {i}/{total} …")
        epoch, src = date_info(p)
        src_count[src] += 1
        if src in ('exif', 'nom', 'chemin') and epoch:
            year_hist[time.localtime(epoch).tm_year] += 1
        if src == 'aucune':
            sans_date.append(str(p))

    # doublons
    dup_files = sum(len(g['paths']) for g in groups)
    dup_extra = sum(len(g['paths']) - 1 for g in groups)   # copies retirables
    recoverable = sum(g['size'] * (len(g['paths']) - 1) for g in groups)

    # ─ JSON detaille ─
    data = {
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_fichiers': total,
        'total_octets': total_bytes,
        'zones': zones,
        'zones_octets': zone_bytes,
        'dates_source': src_count,
        'annees': dict(sorted(year_hist.items())),
        'doublons': {
            'groupes': len(groups),
            'fichiers_impliques': dup_files,
            'copies_retirables': dup_extra,
            'octets_recuperables': recoverable,
        },
        'fichiers_sans_date': sans_date,
        'groupes_doublons': [
            {
                'sha256': g['sha256'],
                'taille': g['size'],
                'octets_recuperables': g['size'] * (len(g['paths']) - 1),
                'canonique_proposee': str(canonical(g['paths'])),
                'copies': [str(p) for p in g['paths']],
            }
            for g in groups
        ],
    }
    (out_dir / 'recensement.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    # ─ MD synthese ─
    top_years = sorted(year_hist.items(), key=lambda kv: kv[1], reverse=True)[:12]
    fiables = src_count['exif'] + src_count['nom']
    md = []
    md.append('# Recensement des doublons — Phase 0\n')
    md.append(f"Genere le {data['genere_le']}. **Lecture seule, aucune "
              f"modification.**\n")
    md.append('## Vue d\'ensemble\n')
    md.append(f"- Fichiers medias recenses : **{total}** "
              f"({human_bytes(total_bytes)})")
    md.append(f"- Sous `_A TRIER` : **{zones['a_trier']}** "
              f"({100 * zones['a_trier'] / total:.0f} %, "
              f"{human_bytes(zone_bytes['a_trier'])})")
    md.append(f"- Sous un dossier annee : **{zones['annee']}** "
              f"({100 * zones['annee'] / total:.0f} %)")
    md.append(f"- Ailleurs : **{zones['autre']}** "
              f"({100 * zones['autre'] / total:.0f} %)\n")
    md.append('## Doublons exacts (par contenu)\n')
    md.append(f"- Groupes de doublons : **{len(groups)}**")
    md.append(f"- Fichiers impliques : **{dup_files}**")
    md.append(f"- Copies retirables (hors canonique) : **{dup_extra}**")
    md.append(f"- **Octets recuperables : {human_bytes(recoverable)}**\n")
    md.append('## Dates\n')
    md.append(f"- Date fiable (EXIF ou nom de fichier) : **{fiables}** "
              f"({100 * fiables / total:.0f} %)")
    md.append(f"  - dont EXIF : {src_count['exif']}, nom de fichier : "
              f"{src_count['nom']}")
    md.append(f"- Date approximative (annee du chemin seulement) : "
              f"**{src_count['chemin']}**")
    md.append(f"- **Sans aucune date (candidats `_SANS_DATE`) : "
              f"{src_count['aucune']}**\n")
    md.append('## Plus grosses annees\n')
    for y, c in top_years:
        md.append(f"- {y} : {c}")
    md.append('')
    md.append('## Lecture\n')
    md.append("Le detail par groupe de doublons (chemins, canonique proposee, "
              "octets) est dans `recensement.json`. Aucune suppression n'a eu "
              "lieu : ce rapport sert a decider si le dedoublonnage vaut "
              "l'effort et a calibrer les seuils avant d'ecrire quoi que ce "
              "soit.\n")
    (out_dir / 'recensement.md').write_text('\n'.join(md), encoding='utf-8')

    return data


# ─────────────────────────── point d'entree ─────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', action='append', default=None,
                    help='Racine a recenser (repetable). Surcharge la config. '
                         'Utile pour un test local.')
    ap.add_argument('--out', default=None,
                    help='Dossier des rapports (defaut : docs/ a cote du script).')
    args = ap.parse_args()

    def log(msg):
        print(msg, flush=True)

    t0 = time.time()
    out_dir = Path(args.out) if args.out else (SCRIPT_DIR / 'docs')
    out_dir.mkdir(parents=True, exist_ok=True)

    log('=== Recensement des doublons (Phase 0, lecture seule) ===')
    if Image is None:
        log('  NOTE : Pillow absent — les dates EXIF ne seront pas lues '
            '(repli nom/chemin).')
    roots = media_roots(args.root)
    if not roots:
        log('AUCUNE racine. Verifie dossier_uploads.txt / dossiers_a_taguer.txt '
            'ou passe --root.')
        return 1
    log('Racines :')
    for r in roots:
        log(f'  - {r}')

    files = enumerate_files(roots, log)
    if not files:
        log('Aucun fichier media trouve.')
        return 1
    log(f"Total : {len(files)} fichiers medias.")

    log('Recherche des doublons exacts …')
    groups = find_exact_duplicates(files, log)

    log('Redaction des rapports …')
    data = build_reports(files, groups, out_dir, log)

    dt = time.time() - t0
    log('')
    log('=== Resume ===')
    log(f"  fichiers            : {data['total_fichiers']}")
    log(f"  groupes de doublons : {data['doublons']['groupes']}")
    log(f"  copies retirables   : {data['doublons']['copies_retirables']}")
    log(f"  octets recuperables : {human_bytes(data['doublons']['octets_recuperables'])}")
    log(f"  sous _A TRIER       : {data['zones']['a_trier']}")
    log(f"  sans date fiable    : {data['dates_source']['aucune']}")
    log(f"  duree               : {dt:.0f} s")
    log('')
    log(f"Rapports ecrits dans {out_dir} :")
    log(f"  - recensement.md   (synthese lisible)")
    log(f"  - recensement.json (detail par groupe)")
    return 0


# Import paresseux de Pillow : le script demarre meme sans (repli nom/chemin).
try:
    from PIL import Image
except Exception:
    Image = None


if __name__ == '__main__':
    sys.exit(main())
