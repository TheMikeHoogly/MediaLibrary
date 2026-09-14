#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mesure — ce qu'exiftool rend VRAIMENT sur une video du fonds.

POURQUOI

`verifier_doublons_atrier.comparer_videos` tranche « cette copie est tronquee,
le fonds porte plus long » sur `exiftool -Duration#`. Ses bancs injectent les
durees : ils tiennent la REGLE, pas la lecture. Si le champ ne s'appelait pas
`Duration`, ou s'il rendait « 0:00:12 » au lieu d'un nombre, toutes les durees
vaudraient 0 -- et le verdict « tronquee » ne se declencherait JAMAIS, sans
une ligne d'erreur. C'est la panne muette que ce projet paye le plus cher.

Ce banc va donc chercher la reponse sur de VRAIS fichiers, et il imprime
AUSSI l'empreinte tete+milieu, l'autre moitie de la regle.

LECTURE SEULE : ouvre les fichiers en lecture, n'ecrit rien, ne touche ni
`photos.db` ni le NAS. Famille `mesure_`, lancable au banc.

USAGE
    python mesure_duree_video.py                     (prend les videos de _A TRIER)
    python mesure_duree_video.py --n 4
    python mesure_duree_video.py --base copie.db
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import verifier_doublons_atrier as V                            # noqa: E402


def videos_du_fonds(base, n):
    cx = sqlite3.connect('file:%s?mode=ro&immutable=1' % Path(base).as_posix(),
                         uri=True)
    try:
        out = []
        for k, in cx.execute('SELECT k FROM tags'):
            if Path(k).suffix.lower() in V.VIDEO_EXT:
                out.append(k)
                if len(out) >= n:
                    break
        return out
    finally:
        cx.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--n', type=int, default=6)
    a = ap.parse_args(argv)

    exe = V.exiftool()
    if not exe:
        print('exiftool ABSENT -- la regle des durees ne peut pas etre lue')
        return 2
    print('exiftool : %s' % V.asc(exe))

    chemins = videos_du_fonds(ICI / a.base, a.n)
    if not chemins:
        print('aucune video dans l index')
        return 1
    print('%d video(s) prise(s) dans l index' % len(chemins))

    t0 = time.perf_counter()
    D = V.durees(exe, chemins, log=lambda m: None)
    dt = time.perf_counter() - t0
    print('durees lues en %.1f s' % dt)

    lues = sans = 0
    for p in chemins:
        d, res = D.get(V.hkey(p), (None, None))
        emp = V.empreinte_flux(p)
        ok = isinstance(d, float) and d > 0
        lues += 1 if ok else 0
        sans += 0 if ok else 1
        print('  %s' % V.asc(Path(p).name))
        print('     duree=%r  resolution=%r  %s'
              % (d, res, 'LUE' if ok else '** NON LUE **'))
        if emp is None:
            print('     empreinte : ILLISIBLE')
        else:
            print('     taille=%d  tete+milieu=%s' % (emp[0], emp[1][:16]))

    # Une duree manquante ne doit pas rester un mystere : on redemande le
    # fichier SEUL et on imprime ce qu'exiftool a vraiment dit. Un lot qui
    # avale une erreur est exactement la panne muette qu'on cherche ici.
    manquants = [p for p in chemins
                 if not (D.get(V.hkey(p), (0, ''))[0] or 0) > 0]
    for p in manquants[:3]:
        # Par le MEME chemin que la prod (fichier d'arguments), sinon le
        # diagnostic mesurerait un autre appel que celui qui a echoue.
        brut = V.exiftool_json(
            exe, ['-Duration#', '-ImageSize', '-FileType', '-Error',
                  '-Warning', '-s3', '-j'], [p],
            log=lambda m: print('     log: %s' % m))
        print()
        print('  DIAGNOSTIC sur %s' % V.asc(Path(p).name))
        print('     json=%s' % V.asc(str(brut)[:500]))
        print('     existe=%s  hors_ascii=%s  octets=%s'
              % (Path(p).exists(), any(ord(c) > 127 for c in str(p)),
                 Path(p).stat().st_size if Path(p).exists() else '?'))

    print()
    print('VERDICT durees lues=%d non_lues=%d bloc=%d'
          % (lues, sans, V.BLOC))
    if sans:
        print('ATTENTION : une duree non lue vaut 0, et une video tronquee ne')
        print('            serait alors JAMAIS reconnue comme telle.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
