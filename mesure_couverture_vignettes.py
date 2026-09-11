#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combien de photos ont DEJA leur vignette de grille — avant de decider qui doit
la fabriquer.

`GET /api/thumb` est premier au temps total depuis le 11/09 : 35 requetes,
62,9 s, **28 au-dessus d'une seconde**. Une vignette absente du cache se
fabrique en lisant l'original sur le NAS, pendant que la campagne de retag
tient le disque. La piste (PERFORMANCE.md § 3.0) : que le TAGUEUR, qui ouvre
deja chaque photo, ecrive la vignette au passage.

Elle ne vaut que si le fonds est MAL couvert. Ce banc le dit, et il ne
suppose rien : il recalcule, pour chaque cle de l'index, le nom exact que
`server._fichier_vignette` donnerait a sa vignette 512 px et 1 600 px, et il
regarde si le fichier existe dans `photo_thumbs\\`.

**Ce qu'il lit** : `copie.db` (en lecture seule), jamais `photos.db` — le
serveur est son ecrivain unique. **La copie a son age**, et le banc l'imprime :
une photo renommee depuis porte une autre cle, et une photo retaguee depuis a
un autre mtime. D'ou deux chiffres, et un seul est ferme :
  * PRESENTE (le fichier existe sous ce nom) — ferme ;
  * A JOUR selon la copie (tampon = mtime de la copie) — BORNE BASSE : une
    photo retaguee apres la copie a une vignette re-tamponnee que la copie
    croit perimee.

Il n'ecrit RIEN, n'ouvre aucune photo, ne touche pas au NAS.

  python mesure_couverture_vignettes.py
  python mesure_couverture_vignettes.py --base copie.db
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# Recopies de server.py — `test_mesure_couverture_vignettes.py` verifie par
# l'arbre syntaxique qu'ils n'ont pas diverge.
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.bmp', '.tiff', '.tif'}
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.wmv'}


def nom_vignette(cle, taille, video=False):
    """Le nom (sans .jpg) que `server._fichier_vignette` donne a la vignette."""
    return hashlib.md5(("%s|%s%s" % (cle, taille, '|video' if video else ''))
                       .encode('utf-8', 'replace')).hexdigest()


def lire_index(base):
    """[(cle, entree)] depuis la table de l'index des tags d'une COPIE."""
    cx = sqlite3.connect(f'file:{base}?mode=ro', uri=True)
    try:
        tables = [r[0] for r in cx.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        table = 'tags' if 'tags' in tables else None
        if table is None:
            best = -1
            for t in tables:
                cols = [r[1] for r in cx.execute(f'PRAGMA table_info("{t}")')]
                if cols[:2] != ['k', 'v']:
                    continue
                n = cx.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
                if n > best:
                    table, best = t, n
        if table is None:
            return [], None
        out = []
        for k, v in cx.execute(f'SELECT k, v FROM "{table}"'):
            try:
                e = json.loads(v)
            except (ValueError, TypeError):
                e = None
            out.append((k, e if isinstance(e, dict) else {}))
        return out, table
    finally:
        cx.close()


def inventorier(dossier):
    """{nom sans .jpg : mtime} — un seul `scandir`."""
    out = {}
    if not dossier.is_dir():
        return out
    with os.scandir(dossier) as it:
        for x in it:
            if x.is_file() and x.name.endswith('.jpg'):
                out[x.name[:-4]] = x.stat().st_mtime
    return out


def fonds_de(cle):
    """Le premier dossier sous `Photos` (Photos Mike, Photos Flo...), pour dire
    OU le cache manque — ou `Uploads` pour une cle relative."""
    parts = [p for p in str(cle).replace('\\', '/').split('/') if p]
    for i, p in enumerate(parts[:-1]):
        if p.lower() == 'photos' and i + 1 < len(parts) - 1:
            return parts[i + 1]
    return 'Uploads' if len(parts) <= 2 else parts[-2]


def mesurer(entrees, cache):
    r = {'images': 0, 'videos': 0, 'echecs': 0,
         '512': 0, '512_a_jour': 0, '1600': 0, 'sans_mtime': 0,
         'par_fonds': {}}
    for k, e in entrees:
        if e.get('failed'):
            r['echecs'] += 1
            continue
        ext = os.path.splitext(str(k))[1].lower()
        if ext in VIDEO_EXT or e.get('video'):
            r['videos'] += 1
            continue
        if ext not in IMAGE_EXT:
            continue
        r['images'] += 1
        f = r['par_fonds'].setdefault(fonds_de(k), [0, 0])
        f[0] += 1
        mt = e.get('mtime')
        n512 = nom_vignette(k, 512)
        if n512 in cache:
            r['512'] += 1
            f[1] += 1
            if mt is None:
                r['sans_mtime'] += 1
                r['512_a_jour'] += 1
            elif int(cache[n512]) == int(mt):
                r['512_a_jour'] += 1
        if nom_vignette(k, 1600) in cache:
            r['1600'] += 1
    return r


def pc(a, b):
    return 100.0 * a / b if b else 0.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', default='copie.db')
    a = ap.parse_args(argv)
    base = RACINE / a.base
    if a.base.lower().startswith('photos.db'):
        print('  photos.db refusee : le serveur en est l ecrivain unique.')
        return 2
    if not base.is_file():
        print('  %s absente.' % base.name)
        return 2
    age_j = (time.time() - base.stat().st_mtime) / 86400
    t0 = time.perf_counter()
    entrees, table = lire_index(base)
    cache = inventorier(RACINE / 'photo_thumbs')
    r = mesurer(entrees, cache)
    duree = time.perf_counter() - t0

    print('=' * 74)
    print('  COUVERTURE DU CACHE DE VIGNETTES (photo_thumbs)')
    print('=' * 74)
    print('  index lu      : %s, table "%s", %d cles — copie agee de %.1f jours'
          % (base.name, table, len(entrees), age_j))
    print('  cache         : %d fichiers .jpg dans photo_thumbs' % len(cache))
    print('  compte        : %.1f s' % duree)
    print('-' * 74)
    print('  photos (images, hors echecs)      %7d' % r['images'])
    print('  videos (hors de ce compte)        %7d' % r['videos'])
    print('  echecs                            %7d' % r['echecs'])
    print('-' * 74)
    print('  vignette 512 PRESENTE             %7d   %5.1f %%'
          % (r['512'], pc(r['512'], r['images'])))
    print('    dont a jour selon la copie      %7d   %5.1f %%   (borne basse)'
          % (r['512_a_jour'], pc(r['512_a_jour'], r['images'])))
    print('  vignette 512 ABSENTE              %7d   %5.1f %%'
          % (r['images'] - r['512'], pc(r['images'] - r['512'], r['images'])))
    print('  vignette 1600 presente            %7d   %5.1f %%'
          % (r['1600'], pc(r['1600'], r['images'])))
    print('-' * 74)
    print('  PAR FONDS (512 presente / photos)')
    for nom, (n, ok) in sorted(r['par_fonds'].items(), key=lambda x: -x[1][0])[:15]:
        print('    %-32s %6d / %6d   %5.1f %%' % (nom[:32], ok, n, pc(ok, n)))
    print('=' * 74)
    print('  A LIRE : une cle renommee depuis la copie compte comme ABSENTE, et')
    print('  une photo retaguee depuis compte comme PERIMEE. Rien n a ete ecrit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
