#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — l'ECART entre l'index et la marche sur le NAS, fichier par fichier
──────────────────────────────────────────────────────────────────────────────

POURQUOI

La page du fonds entier (`/files?dir=1&rec=1`) marche 12 à 17 s sur le
partage SMB pour trouver 44 483 fichiers, quand l'index en connaît 44 482 en
0,3 s (PERFORMANCE.md § 3.24, mesuré à nouveau le 13/09 au soir). Avant de
décider si une grille récursive doit encore MARCHER — `ROADMAP.md` § C3 —, il
faut savoir ce que la marche apporte que l'index n'a pas : QUELS fichiers,
et pourquoi l'index les ignore.

CE QU'IL FAIT

1. Un snapshot cohérent de `photos.db` (`mesure_copie_base.copier`, API
   `backup`, source en lecture seule) — une copie datée, pas celle qui traîne.
2. Les clés de la table `tags` situées sous la racine NAS, normalisées comme
   `_pkey` (`Path(k).as_posix().lower()`).
3. La MÊME marche que `_lister_dossier(rec=True)` : `os.walk`, élagage des
   dossiers `.` `@` `#`, extensions `MEDIA_EXT` — recopiées ici plutôt
   qu'importées, parce qu'importer `server.py` ouvre `photos.db` (règle 4).
4. La différence dans les deux sens, avec pour chaque fichier hors index :
   taille, date, extension, et s'il existe dans l'index sous une autre CASSE
   ou un autre chemin (même nom de fichier ailleurs).

CE QU'IL NE FAIT PAS

Aucune écriture sur `photos.db`, sur le NAS ni sur l'index. Famille
`mesure_`, lançable au banc.

USAGE
    python mesure_ecart_index_marche.py
    python mesure_ecart_index_marche.py --sans-copie     (réutilise copie.db)
    python mesure_ecart_index_marche.py --exemples 50
"""

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif',
             '.bmp', '.tiff', '.tif'}
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.wmv'}
MEDIA_EXT = IMAGE_EXT | VIDEO_EXT
CACHES = ('.', '@', '#')


def pkey(p):
    return Path(p).as_posix().lower()


def racine_nas(fichier=ICI / 'dossiers_a_taguer.txt'):
    for ligne in fichier.read_text(encoding='utf-8', errors='replace').splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith('#'):
            return ligne
    raise SystemExit('aucune racine dans dossiers_a_taguer.txt')


def marcher(racine):
    """Même parcours que `_lister_dossier(rec=True)` — mêmes filtres."""
    fichiers, dossiers = [], 0
    for r, dirs, noms in os.walk(racine):
        dossiers += 1
        dirs[:] = [d for d in dirs if not d.startswith(CACHES)]
        for n in noms:
            if n.startswith(CACHES):
                continue
            if os.path.splitext(n)[1].lower() in MEDIA_EXT:
                fichiers.append(os.path.join(r, n))
    return fichiers, dossiers


def cles_index(base, racine):
    cx = sqlite3.connect('file:%s?mode=ro&immutable=1' % Path(base).as_posix(),
                         uri=True)
    try:
        toutes = [k for k, in cx.execute('SELECT k FROM tags')]
    finally:
        cx.close()
    pref = pkey(racine) + '/'
    sous = [k for k in toutes if pkey(k).startswith(pref)]
    return toutes, sous


def decrire(chemin):
    d = {'chemin': chemin, 'ext': os.path.splitext(chemin)[1].lower()}
    try:
        st = os.stat(chemin)
        d['octets'] = st.st_size
        d['mtime'] = datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    except OSError as e:
        d['stat'] = 'ERREUR %s' % e
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--sans-copie', action='store_true')
    ap.add_argument('--exemples', type=int, default=20)
    a = ap.parse_args(argv)

    base = ICI / a.base
    if base.name == 'photos.db':
        raise SystemExit('refus : jamais sur photos.db (règle 4)')
    if not a.sans_copie:
        sys.path.insert(0, str(ICI))
        from mesure_copie_base import copier
        rap = copier(ICI / 'photos.db', base)
        print('copie : snapshot à %s, %.1f s, WAL absorbé %d octets, intégrité %s'
              % (datetime.fromtimestamp(rap['snapshot_a']).strftime('%H:%M:%S'),
                 rap['duree_s'], rap['wal_octets'], rap.get('integrite')))
    else:
        print('copie : réutilise %s (modifiée %s)' % (
            base.name, datetime.fromtimestamp(base.stat().st_mtime).strftime('%d/%m %H:%M')))

    racine = racine_nas()
    print('racine : %s' % racine)

    t0 = time.perf_counter()
    toutes, sous = cles_index(base, racine)
    t_idx = time.perf_counter() - t0
    print('index : %d clés au total, %d sous la racine (%.2f s)' % (len(toutes), len(sous), t_idx))

    t0 = time.perf_counter()
    c0 = time.process_time()
    fichiers, dossiers = marcher(racine)
    t_marche = time.perf_counter() - t0
    c_marche = time.process_time() - c0
    print('marche : %d fichiers média, %d dossiers lus, %.1f s horloge, %.1f s CPU'
          % (len(fichiers), dossiers, t_marche, c_marche))

    idx = {pkey(k): k for k in sous}
    mar = {pkey(f): f for f in fichiers}
    if len(idx) != len(sous):
        print('ATTENTION : %d clés d index se confondent après normalisation' % (len(sous) - len(idx)))
    if len(mar) != len(fichiers):
        print('ATTENTION : %d fichiers marchés se confondent après normalisation' % (len(fichiers) - len(mar)))

    seul_marche = sorted(set(mar) - set(idx))
    seul_index = sorted(set(idx) - set(mar))
    print()
    print('ECART : %d fichier(s) vus par la marche et absents de l index ; '
          '%d clé(s) d index sans fichier sur le disque' % (len(seul_marche), len(seul_index)))

    noms_index = {}
    for k in toutes:
        noms_index.setdefault(os.path.basename(k).lower(), []).append(k)

    print()
    print('--- marche seulement (%d, %d montrés) ---' % (len(seul_marche), min(len(seul_marche), a.exemples)))
    for p in seul_marche[:a.exemples]:
        d = decrire(mar[p])
        homonymes = noms_index.get(os.path.basename(p), [])
        print('  %s' % d['chemin'])
        print('     ext=%s octets=%s mtime=%s %s' % (
            d['ext'], d.get('octets', '?'), d.get('mtime', '?'), d.get('stat', '')))
        if homonymes:
            print('     même nom dans l index (%d) : %s' % (len(homonymes), ' | '.join(homonymes[:3])))
        else:
            print('     aucun homonyme dans l index')

    print()
    print('--- index seulement (%d, %d montrés) ---' % (len(seul_index), min(len(seul_index), a.exemples)))
    for p in seul_index[:a.exemples]:
        print('  %s' % idx[p])

    print()
    print('RESUME index_sous_racine=%d marche=%d seul_marche=%d seul_index=%d marche_s=%.1f'
          % (len(sous), len(fichiers), len(seul_marche), len(seul_index), t_marche))
    return 0


if __name__ == '__main__':
    sys.exit(main())
