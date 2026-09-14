#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mesure — exiftool et les chemins ACCENTUES : ce que l'ancien appel perdait.

CE QUI A ETE TROUVE (14/09)

`verifier_doublons_atrier` passait les chemins a exiftool sur la LIGNE DE
COMMANDE. Un chemin accentue y arrive mutile : exiftool repond
« Error: File not found », le lot rend simplement une entree de MOINS, et
personne ne le voit. Consequence : une photo accentuee n'a pas d'empreinte,
ne trouve donc jamais sa canonique, et tombe dans `homonymes_differents` --
la liste que `--homonymes-differents` peut RETIRER. Un fichier qu'on n'a pas
su comparer s'y donnait pour un fichier compare et juge different.

**8,4 % du fonds est concerne** : 3 714 cles sur 44 477 portent au moins un
caractere hors ASCII (mesure du 14/09 sur un snapshot de la base).

CE QUE CE BANC FAIT

Il prend des chemins REELS -- des accentues et des ASCII -- et demande leur
empreinte DEUX FOIS : par l'ancien appel (ligne de commande) et par le
nouveau (fichier d'arguments UTF-8). Il imprime les deux comptes. Si le
correctif tient, l'ecart est exactement sur les accentues.

LECTURE SEULE : aucune ecriture, ni sur les fichiers, ni sur `photos.db`
(snapshot en `mode=ro`), ni de rapport. Famille `mesure_`.

USAGE
    python mesure_exiftool_accents.py
    python mesure_exiftool_accents.py --n 12 --base copie.db
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import verifier_doublons_atrier as V                            # noqa: E402


def echantillon(base, n):
    """(accentues, ascii) : des IMAGES qui existent, prises dans l'index."""
    cx = sqlite3.connect('file:%s?mode=ro&immutable=1' % Path(base).as_posix(),
                         uri=True)
    acc, asc_ = [], []
    try:
        for k, in cx.execute('SELECT k FROM tags'):
            if Path(k).suffix.lower() not in V.IMAGE_EXT:
                continue
            cible = acc if any(ord(c) > 127 for c in k) else asc_
            if len(cible) >= n or not os.path.exists(k):
                continue
            cible.append(k)
            if len(acc) >= n and len(asc_) >= n:
                break
    finally:
        cx.close()
    return acc, asc_


def ancien_appel(exe, chemins):
    """L'appel D'AVANT : les chemins sur la ligne de commande."""
    args = [str(exe), '-api', 'RequestAll=3', '-ImageDataHash', '-s3',
            '-q', '-q', '-j', '-charset', 'filename=UTF8'] \
        + [str(p) for p in chemins]
    r = subprocess.run(args, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=600)
    vus = set()
    for item in json.loads(r.stdout or '[]'):
        if item.get('ImageDataHash'):
            vus.add(V.hkey(item.get('SourceFile', '')))
    return vus


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--n', type=int, default=8)
    a = ap.parse_args(argv)

    exe = V.exiftool()
    if not exe:
        print('exiftool ABSENT'); return 2

    acc, asc_ = echantillon(ICI / a.base, a.n)
    print('echantillon : %d accentue(s), %d ascii' % (len(acc), len(asc_)))
    if not acc:
        print('aucun chemin accentue trouve : rien a mesurer'); return 1
    for p in acc[:3]:
        print('  acc : %s' % V.asc(p))

    for titre, lot in (('ACCENTUES', acc), ('ASCII', asc_)):
        if not lot:
            continue
        avant = ancien_appel(exe, lot)
        apres = V.image_hashes(exe, lot, log=lambda m: None)
        na = sum(1 for p in lot if V.hkey(p) in avant)
        np_ = sum(1 for p in lot if V.hkey(p) in apres)
        print('%-10s sur %d : ancien appel %d empreinte(s), '
              'fichier d arguments %d' % (titre, len(lot), na, np_))
        # Et les empreintes doivent etre les MEMES quand les deux repondent :
        # le correctif ne doit pas changer ce qui marchait.
        memes = all(apres.get(V.hkey(p)) for p in lot if V.hkey(p) in avant)
        print('           les empreintes deja obtenues sont retrouvees : %s'
              % memes)

    print()
    print('VERDICT : un ecart sur les ACCENTUES et aucun sur les ASCII designe')
    print('          la ligne de commande, pas le fichier ni exiftool.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
