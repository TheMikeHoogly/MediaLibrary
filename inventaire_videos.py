#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier videos, PHASE 0 : le plan de rangement par annee des VIDEOS.

Les `.mp4` de `_A TRIER` ne sont ni indexees ni rangees (le scan filtre
IMAGE_EXT). Ce banc les recense, les DATE et ecrit le plan que
`appliquer_plan_annee.py --plan docs/plan_rangement_videos.json` (bat 39)
applique — meme regle de cible que les photos (`rangement_annee.cible` :
`Photos <Nom>\\<annee>`, `_SANS_DATE` sans date fiable), meme journal undo,
meme garde-fou de collision. LECTURE SEULE ici. Sortie ASCII, flush.

LA DATE d'une video, dans l'ordre, et JAMAIS le mtime :
  1. le NOM de fichier `AAAAMMJJ_HHMMSS` (Samsung, WhatsApp `VID-AAAAMMJJ`) :
     c'est l'heure LOCALE de la prise, la plus sure ;
  2. ExifTool : `QuickTime:CreationDate` (porte le fuseau), sinon
     `QuickTime:CreateDate` / `MediaCreateDate` (UTC chez Samsung — a une
     heure pres, l'annee est la meme sauf a minuit le 31 decembre) ;
  3. le DOSSIER annee du Takeout (`Takeout Google\\2021\\`) ;
  4. rien -> `_SANS_DATE`, et le rapport le dit.
Une video dont ExifTool ne rend pas une date > 2000 est comptee « sans date »
(les 1970/1904 sont des compteurs a zero, pas des dates).

    inventaire_videos.py                       # tout _A TRIER
    inventaire_videos.py --limite 40           # echantillon (le canal du banc coupe a 600 s)
    inventaire_videos.py --racine b64:<dossier>
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import rangement_annee as RA  # noqa: E402

VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.wmv'}
NOM_DATE = re.compile(r'(?<!\d)((?:19|20)\d{2})(\d{2})(\d{2})(?:[_-](\d{2})(\d{2})(\d{2}))?(?!\d)')
TAGS = ('QuickTime:CreationDate', 'QuickTime:CreateDate', 'QuickTime:MediaCreateDate',
        'QuickTime:TrackCreateDate', 'CreateDate', 'DateTimeOriginal')


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def deb64(v):
    return base64.b64decode(v[4:]).decode('utf-8') if str(v).startswith('b64:') else v


def exiftool():
    for c in sorted(ICI.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return p
    return None


def date_du_nom(nom):
    """epoch depuis `AAAAMMJJ[_HHMMSS]` dans le nom, ou None."""
    m = NOM_DATE.search(nom)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    h, mi, s = (int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
    try:
        return datetime(y, mo, d, h, mi, s).timestamp()
    except ValueError:
        return None


def date_exif(valeur):
    """epoch depuis une valeur ExifTool `AAAA:MM:JJ HH:MM:SS[+HH:MM]`, ou None
    (et None pour les dates < 2000 : compteurs a zero)."""
    if not valeur or not isinstance(valeur, str):
        return None
    m = re.match(r'(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})', valeur)
    if not m:
        return None
    y = int(m.group(1))
    if y < 2000:
        return None
    try:
        return datetime(y, *map(int, m.groups()[1:])).timestamp()
    except ValueError:
        return None


def dates_exiftool(exe, fichiers, log):
    """{chemin: epoch|None} via UN processus ExifTool (-fast2 : en-tetes)."""
    out = {}
    if not fichiers or not exe:
        return out
    lot = 200
    for i in range(0, len(fichiers), lot):
        part = fichiers[i:i + lot]
        args = [str(exe), '-j', '-fast', '-charset', 'filename=utf8', '-charset', 'utf8'] + \
               ['-' + t for t in TAGS] + part
        try:
            r = subprocess.run(args, capture_output=True, timeout=500)
            data = json.loads(r.stdout.decode('utf-8', 'replace') or '[]')
        except (subprocess.TimeoutExpired, ValueError, OSError) as e:
            log('  exiftool : %s' % asc(e))
            data = []
        for e in data:
            src = e.get('SourceFile')
            ts = None
            for t in TAGS:
                k = t.split(':')[-1]
                ts = date_exif(e.get(k))
                if ts:
                    break
            if src:
                out[os.path.normpath(src)] = ts
        log('  exiftool %d/%d' % (min(i + lot, len(fichiers)), len(fichiers)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='')
    ap.add_argument('--limite', type=int, default=0)
    ap.add_argument('--sans-exiftool', action='store_true')
    a = ap.parse_args(argv)
    if a.racine:
        racine = Path(deb64(a.racine))
    else:
        import inventaire_fonds as F
        racine = Path(str(F.racines()[0])) / '_A TRIER'
    log = lambda s: print(s, flush=True)  # noqa: E731
    log('RACINE : %s' % asc(racine))
    t0 = time.time()
    videos = []
    for r, _dirs, files in os.walk(str(racine)):
        for f in files:
            if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                videos.append(os.path.join(r, f))
    videos.sort()
    log('%d video(s) trouvee(s) en %.1f s' % (len(videos), time.time() - t0))
    if a.limite:
        videos = videos[:a.limite]
        log('  (echantillon : %d)' % len(videos))

    # 1. le nom
    ts = {v: date_du_nom(os.path.basename(v)) for v in videos}
    par_nom = sum(1 for t in ts.values() if t)
    # 2. exiftool pour le reste
    restants = [v for v in videos if not ts[v]]
    exe = None if a.sans_exiftool else exiftool()
    if restants and not exe:
        log('  exiftool introuvable : %d video(s) sans nom date restent SANS DATE' % len(restants))
    ex = dates_exiftool(exe, restants, log) if exe else {}
    par_exif = 0
    for v in restants:
        t = ex.get(os.path.normpath(v))
        if t:
            ts[v] = t
            par_exif += 1
    # 3. le DOSSIER annee du Takeout (`Takeout Google\2021\x.MP4`) : c'est la
    # regle des photos absentes (27/08) — l'annee du dossier, jamais le mtime.
    par_dossier = 0
    for v in videos:
        if not ts[v]:
            parent = os.path.basename(os.path.dirname(v))
            if re.fullmatch(r'(19|20)\d{2}', parent):
                ts[v] = datetime(int(parent), 7, 1).timestamp()
                par_dossier += 1
    sans = [v for v in videos if not ts[v]]

    plan = RA.construire_plan((v, v, ts[v] or 0) for v in videos)
    plan['genere_le'] = time.strftime('%Y-%m-%d %H:%M:%S')
    plan['source'] = 'inventaire_videos.py'
    plan['racine'] = str(racine)
    plan['provenance_date'] = {'nom': par_nom, 'exiftool': par_exif, 'dossier_annee': par_dossier,
                               'sans_date': len(sans)}
    octets = 0
    for m in plan['moves']:
        try:
            octets += os.path.getsize(m['src'])
        except OSError:
            pass
    print('=' * 70)
    print('PLAN VIDEOS : %d a ranger (%.1f Go), %d deja en place, %d conflit(s), %d sans date'
          % (plan['total_a_ranger'], octets / 1e9, plan['deja'], len(plan['conflits']), plan['sans_date']))
    print('  date par le NOM : %d   par ExifTool : %d   par le DOSSIER annee : %d   aucune : %d'
          % (par_nom, par_exif, par_dossier, len(sans)))
    print('  par annee : %s' % json.dumps(plan['par_annee']))
    cibles = sorted({os.path.dirname(m['dst']) for m in plan['moves']})
    print('  dossiers cibles : %d' % len(cibles))
    for c in cibles[:12]:
        print('    -> %s' % asc(c))
    for m in plan['moves'][:6]:
        print('  ex: %s -> %s' % (asc(os.path.basename(m['src'])), asc(m['dst'])))
    for v in sans[:8]:
        print('  SANS DATE : %s' % asc(v))
    (ICI / 'docs').mkdir(exist_ok=True)
    (ICI / 'docs' / 'plan_rangement_videos.json').write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    print('plan ecrit : docs/plan_rangement_videos.json  (%.1f s)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
