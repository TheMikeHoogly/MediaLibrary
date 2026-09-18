#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — les CAPTURES D'ECRAN, le signal franc du filet (chantier 19, brique 1)
──────────────────────────────────────────────────────────────────────────────

POURQUOI (plan du 17/09, `docs/CHANTIER_19_VIE_PRIVEE.md`)

Le filet « intime » a ete MESURE le 17/09 et REFUSE en automatique : sur les
vecteurs SigLIP, une photo de plage et une photo intime ne se separent pas.
Mais le plan note qu'une capture de conversation, elle, « se detecte sans
modele : pas d'appareil dans l'EXIF, format PNG, dimensions d'ecran. Signal
franc, A MESURER avant d'etre cable. »

Ce banc fait cette mesure, et RIEN d'autre : il ne masque pas, n'ecrit pas,
n'ouvre aucune image. Il lit une COPIE de la base (`mesure_copie_base.py`),
jamais `photos.db`.

CE QU'IL DIT AVANT DE CONCLURE

Un banc qui suppose les champs qu'il lit mesure ses suppositions. Celui-ci
commence donc par INVENTORIER ce que portent vraiment les entrees, et par
DIRE ce qu'il ne trouve pas -- un signal absent de la base n'est pas un
signal faible, c'est un signal qu'on ne peut pas encore lire, et les deux ne
se decident pas de la meme facon.

Trois signaux, comptes separement puis croises :
  1. l'EXTENSION (.png) ;
  2. l'absence d'APPAREIL dans les champs de l'entree (s'il y en a) ;
  3. le mot-cle du tagueur (« capture d ecran », deja dans le filet documents).

Le croisement est le sujet : un signal qui recoupe exactement le tagueur
n'apporte rien ; un signal qui attrape ce que le tagueur a manque est la
raison d'exister du filet -- et ce qu'il attrape EN TROP est son prix.

  python mesure_copie_base.py
  python mesure_captures_ecran.py --base copie.db
  python mesure_captures_ecran.py --base copie.db --exemples 12
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ICI = Path(__file__).resolve().parent
# Les noms de champ ou un appareil se serait pose, si la base en portait un.
CHAMPS_APPAREIL = ('make', 'model', 'appareil', 'camera', 'exif_make',
                   'exif_model', 'marque', 'modele')
MOTS_CAPTURE = ('capture d ecran', "capture d'ecran", 'capture ecran',
                'screenshot', 'screen shot')


def entrees(base):
    cx = sqlite3.connect('file:%s?mode=ro' % base, uri=True)
    try:
        for k, v in cx.execute('SELECT k, v FROM tags'):
            try:
                e = json.loads(v)
            except ValueError:
                e = None
            yield k, (e if isinstance(e, dict) else {})
    finally:
        cx.close()


def mots(e):
    out = []
    for champ in ('kw_fr', 'kw_en'):
        for t in (e.get(champ) or []):
            out.append(str(t).lower())
    return out


def dit_capture(e):
    for m in mots(e):
        for cible in MOTS_CAPTURE:
            if cible in m:
                return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--exemples', type=int, default=0,
                    help="combien de NOMS DE FICHIER citer par case (jamais d'image)")
    a = ap.parse_args(argv)
    base = Path(a.base)
    if not base.is_absolute():
        base = ICI / base
    if not base.exists():
        print('base introuvable : %s (lancer mesure_copie_base.py)' % base)
        return 2

    champs = Counter()
    n = 0
    png, sans_appareil, tagueur = set(), set(), set()
    avec_appareil = set()
    for k, e in entrees(base):
        n += 1
        for c in e:
            champs[c] += 1
        if k.lower().endswith('.png'):
            png.add(k)
        vu = any(e.get(c) for c in CHAMPS_APPAREIL)
        (avec_appareil if vu else sans_appareil).add(k)
        if dit_capture(e):
            tagueur.add(k)

    print('entrees lues : %d' % n)
    print('\nCE QUE PORTE UNE ENTREE (20 champs les plus frequents)')
    for c, combien in champs.most_common(20):
        print('  %-18s %6d  (%4.1f %%)' % (c, combien, 100.0 * combien / max(n, 1)))

    trouves = [c for c in CHAMPS_APPAREIL if champs.get(c)]
    print('\nL APPAREIL')
    if trouves:
        print('  champs presents : %s' % ', '.join(trouves))
        print('  entrees AVEC appareil : %d   SANS : %d' % (len(avec_appareil), len(sans_appareil)))
    else:
        print("  AUCUN champ d'appareil dans la base : ce signal n'est pas")
        print('  faible, il est ILLISIBLE ici. Le lire demanderait de rouvrir')
        print('  les fichiers (exiftool sur 44 000 photos) ou de le stocker au')
        print('  tagging. A trancher avant de le compter pour acquis.')

    print('\nLES DEUX SIGNAUX LISIBLES, ET LEUR CROISEMENT')
    print('  .png                      : %6d' % len(png))
    print('  mot-cle du tagueur        : %6d' % len(tagueur))
    print('  les deux                  : %6d' % len(png & tagueur))
    print('  .png que le tagueur a MANQUE : %6d' % len(png - tagueur))
    print('  dit capture SANS etre .png   : %6d' % len(tagueur - png))
    if png:
        print('  part des .png que le tagueur nomme : %.1f %%'
              % (100.0 * len(png & tagueur) / len(png)))

    if a.exemples:
        print('\nQUELQUES NOMS (jamais une image), pour juger sur piece')
        for libelle, ens in (('.png manques par le tagueur', png - tagueur),
                             ('dits captures sans etre .png', tagueur - png)):
            print('  %s :' % libelle)
            for k in sorted(ens)[:a.exemples]:
                print('    %s' % Path(k).name)
    print('\nCE BANC NE MASQUE RIEN ET N ECRIT RIEN.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
