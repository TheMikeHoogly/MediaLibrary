#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deux fichiers portent-ils la MEME IMAGE, metadonnees mises a part ?

Cas d'usage : une copie dans `_A TRIER` et une dans le fonds, meme nom, tailles
qui different de quelques centaines d'octets (des tags XMP/IPTC ecrits a des
moments differents). L'octet differe, donc un sha256 dit « pas doublon » a tort.
`exiftool -ImageDataHash` hashe les PIXELS seuls (hors metadonnees) : meme hash
= meme photo, quel que soit le bloc de tags. C'est la preuve qui autorise a
retirer la copie `_A TRIER` sans rien perdre de l'image.

Lecture seule. Sortie ASCII.

    verifier_meme_image.py --a b64:<chemin1> --b b64:<chemin2>
"""
import argparse
import base64
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent


def exiftool():
    for c in sorted(ICI.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return p
    return None


def deb64(v):
    return base64.urlsafe_b64decode(v[4:] + '=' * (-len(v[4:]) % 4)).decode('utf-8') if v.startswith('b64:') else v


def image_hash(exe, chemin):
    r = subprocess.run([str(exe), '-api', 'RequestAll=3', '-ImageDataHash',
                        '-s3', '-q', '-charset', 'filename=UTF8', str(chemin)],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=180)
    return (r.stdout or '').strip() or '(vide)'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    a = ap.parse_args(argv)
    exe = exiftool()
    if not exe:
        print('exiftool ABSENT'); return 2
    pa, pb = Path(deb64(a.a)), Path(deb64(a.b))
    for lbl, p in (('A', pa), ('B', pb)):
        print('%s : %s  %s' % (lbl, p.name, 'existe' if p.exists() else 'ABSENT'))
    ha, hb = image_hash(exe, pa), image_hash(exe, pb)
    print('ImageDataHash A : %s' % ha)
    print('ImageDataHash B : %s' % hb)
    print('=> %s' % ('MEME IMAGE (retrait de la copie sur' if ha == hb and ha != '(vide)'
                     else 'IMAGES DIFFERENTES (ne PAS confondre)'))
    print('   _A TRIER sans risque)' if ha == hb and ha != '(vide)' else '')
    return 0


if __name__ == '__main__':
    sys.exit(main())
