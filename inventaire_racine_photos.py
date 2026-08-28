#!/usr/bin/env python3
"""Ce que contiennent encore les dossiers a la RACINE de `Photos`.

Depuis le deplacement du fonds sous `Photos Mike`, les dossiers `Photos\\<annee>`
a la racine devraient etre vides. Mais leur date de modification dit qu'ils ont
bouge le 28/08 au soir. Avant d'ecrire un .bat qui les efface, on COMPTE.

Pour chaque entree de premier niveau de la racine : nombre de fichiers, de
medias (photo/video), d'autres fichiers (sidecars, _original, thumbs), total
en octets, profondeur, et quelques exemples. Lecture seule, sortie ASCII.

    inventaire_racine_photos.py [--racine=b64:...] [--exemples=3]
"""
import argparse
import os
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import inventaire_fonds as F  # noqa: E402

MEDIA = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.gif', '.bmp',
         '.tif', '.tiff', '.mp4', '.mov', '.avi', '.m4v', '.3gp', '.mkv',
         '.wmv', '.mts', '.dng', '.cr2', '.nef', '.arw'}


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def compter(dossier, exemples):
    n = nm = na = 0
    octets = 0
    prof = 0
    ex = []
    autres_ext = {}
    for racine, dirs, fichiers in os.walk(dossier):
        p = Path(racine).relative_to(dossier)
        prof = max(prof, len(p.parts))
        for f in fichiers:
            n += 1
            ext = os.path.splitext(f)[1].lower()
            chemin = os.path.join(racine, f)
            try:
                octets += os.path.getsize(chemin)
            except OSError:
                pass
            if ext in MEDIA:
                nm += 1
                if len(ex) < exemples:
                    ex.append(str(Path(chemin).relative_to(dossier)))
            else:
                na += 1
                autres_ext[ext or '(sans)'] = autres_ext.get(ext or '(sans)', 0) + 1
    return n, nm, na, octets, prof, ex, autres_ext


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='')
    ap.add_argument('--exemples', type=int, default=3)
    a = ap.parse_args(argv)
    racines = [a.racine] if a.racine else [str(r) for r in F.racines()]
    for r in racines:
        # la racine `Photos` est le PARENT des racines du fonds si celles-ci
        # sont `Photos Mike` etc. ; on remonte tant que le nom n'est pas Photos
        p = Path(r)
        while p.name.lower() != 'photos' and p.parent != p:
            p = p.parent
        if p.name.lower() != 'photos':
            p = Path(r)
        print('RACINE : %s' % asc(p))
        print('=' * 78)
        try:
            entrees = sorted(p.iterdir(), key=lambda x: x.name.lower())
        except OSError as e:
            print('  illisible : %s' % asc(e))
            continue
        vides = []
        for e in entrees:
            if not e.is_dir():
                print('  [fichier] %s' % asc(e.name), flush=True)
                continue
            if not e.name[:4].isdigit():
                # `.thumbs`, `_A TRIER`, `Photos Mike`... : des dizaines de
                # milliers de fichiers en SMB, hors question. On ne compte
                # que les dossiers <annee> de la racine.
                print('  %-24s (non parcouru : pas un dossier annee)' % asc(e.name), flush=True)
                continue
            n, nm, na, octets, prof, ex, autres = compter(e, a.exemples)
            etat = 'VIDE' if n == 0 else ''
            if n == 0:
                vides.append(e.name)
            print('  %-24s %6d fichiers  %6d medias  %6d autres  %8.1f Mo  prof %d  %s'
                  % (asc(e.name), n, nm, na, octets / 1e6, prof, etat), flush=True)
            for x in ex:
                print('      ex: %s' % asc(x), flush=True)
            if autres:
                top = sorted(autres.items(), key=lambda kv: -kv[1])[:5]
                print('      autres: %s' % ', '.join('%s x%d' % kv for kv in top))
        print('-' * 78)
        print('  dossiers VIDES (effacables sans perte) : %d -> %s'
              % (len(vides), ', '.join(asc(v) for v in vides) or 'aucun'))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
