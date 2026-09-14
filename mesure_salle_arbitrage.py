#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mesure — ce qui reste dans `_A TRIER\\Google porte mieux`, paire par paire.

POURQUOI

Le bat 33 y a depose les fichiers que Google detenait en version PLUS GROSSE
que le NAS, « un dossier a part, pour qu'on sache qu'ils attendent un
arbitrage ». L'arbitrage n'a jamais ete fait pour ce qui reste. Et la question
n'est PAS « lequel est le plus gros » -- on le sait deja, c'est celui de
Google -- mais « **l'octet en plus est-il de l'IMAGE ou de la remorque ?** ».

  - Meme image (ou meme flux) : l'octet en plus est du hors-image. Le NAS a
    deja la photo, la copie de Google ne porte rien de neuf.
  - Image differente : Google porte une MEILLEURE version, et c'est le seul
    cas ou il faut vraiment trancher.

Ce banc pose les deux cotes l'un a cote de l'autre et laisse Mike decider. Il
ne deplace rien, n'efface rien, n'ecrit aucun rapport.

CE QU'IL LIT

L'index (snapshot `mode=ro`) pour apparier chaque fichier de la salle avec
son homonyme du fonds, puis, sur le disque : `ImageDataHash` pour les images
(les pixels seuls), empreinte tete+milieu et duree pour les videos. Le tout
par le chemin de `verifier_doublons_atrier`, donc par fichier d'arguments --
un chemin accentue passe entier.

USAGE
    python mesure_salle_arbitrage.py
    python mesure_salle_arbitrage.py --base copie.db
"""

import argparse
import collections
import sqlite3
import sys
from pathlib import Path, PureWindowsPath

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import rangement_annee as _ra                                   # noqa: E402
import verifier_doublons_atrier as V                            # noqa: E402

# Les cles du fonds sont des chemins WINDOWS. Sous Linux `os.path.basename`
# rendrait le chemin ENTIER (le backslash n'y est pas un separateur) : ce banc
# a ete ecrit une premiere fois comme ca et il a conclu « aucun jumeau » sur
# 18 fichiers qui en ont tous un. La plateforme repondait, pas la regle.
_ra.Path = PureWindowsPath


def nom(k):
    return PureWindowsPath(k).name


def paires(base):
    cx = sqlite3.connect('file:%s?mode=ro&immutable=1' % Path(base).as_posix(),
                         uri=True)
    try:
        salle, fonds = [], collections.defaultdict(list)
        for k, in cx.execute('SELECT k FROM tags'):
            if _ra.est_arbitrage(k):
                salle.append(k)
            else:
                fonds[nom(k).lower()].append(k)
    finally:
        cx.close()
    return [(k, (fonds.get(nom(k).lower()) or [None])[0]) for k in sorted(salle)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    a = ap.parse_args(argv)

    exe = V.exiftool()
    if not exe:
        print('exiftool ABSENT'); return 2

    lot = paires(ICI / a.base)
    print('%d fichier(s) dans la salle d arbitrage' % len(lot))
    orphelins = [s for s, f in lot if not f]
    if orphelins:
        print('%d SANS jumeau dans le fonds : le NAS ne les a pas du tout,'
              ' il n y a rien a arbitrer -- ils se rangent.' % len(orphelins))
        for s in orphelins:
            print('   %s' % V.asc(s))

    images = [(s, f) for s, f in lot
              if f and PureWindowsPath(s).suffix.lower() in V.IMAGE_EXT]
    videos = [(s, f) for s, f in lot
              if f and PureWindowsPath(s).suffix.lower() in V.VIDEO_EXT]

    meme, different, illisible = [], [], []

    if images:
        H = V.image_hashes(exe, [x for p in images for x in p],
                           log=lambda m: print('  %s' % m))
        print()
        print('IMAGES -- %d paire(s). Les PIXELS seuls (ImageDataHash).' % len(images))
        print('%-24s %11s %11s   %s' % ('fichier', 'salle', 'fonds', 'verdict'))
        for s, f in images:
            hs, hf = H.get(V.hkey(s)), H.get(V.hkey(f))
            es, ef = V.empreinte_flux(s), V.empreinte_flux(f)
            ts = es[0] if es else 0
            tf = ef[0] if ef else 0
            if not hs or not hf:
                v = 'ILLISIBLE (pas d empreinte)'
                illisible.append(s)
            elif hs == hf:
                v = 'MEME IMAGE -- le +%d o est hors-image' % (ts - tf)
                meme.append(s)
            else:
                v = 'IMAGE DIFFERENTE -- a regarder'
                different.append(s)
            print('%-24s %11d %11d   %s' % (V.asc(nom(s)), ts, tf, v))

    if videos:
        D = V.durees(exe, [x for p in videos for x in p],
                     log=lambda m: print('  %s' % m))
        print()
        print('VIDEOS -- %d paire(s). Le FLUX (tete+milieu) et la DUREE.' % len(videos))
        print('%-24s %11s %11s %8s %8s   %s'
              % ('fichier', 'salle', 'fonds', 'd.salle', 'd.fonds', 'verdict'))
        for s, f in videos:
            es, ef = V.empreinte_flux(s), V.empreinte_flux(f)
            ds = D.get(V.hkey(s), (0.0, ''))[0]
            df = D.get(V.hkey(f), (0.0, ''))[0]
            ts = es[0] if es else 0
            tf = ef[0] if ef else 0
            if not es or not ef:
                v = 'ILLISIBLE'
                illisible.append(s)
            elif es[1] == ef[1] and ts == tf:
                v = 'MEME FICHIER'
                meme.append(s)
            elif es[1] == ef[1]:
                v = ('MEME DEBUT, +%d o ici (%.2f s contre %.2f s)'
                     % (ts - tf, ds, df))
                (meme if ds <= df + 0.05 else different).append(s)
            else:
                v = 'FLUX DIFFERENT -- a regarder'
                different.append(s)
            print('%-24s %11d %11d %8.2f %8.2f   %s'
                  % (V.asc(nom(s)), ts, tf, ds, df, v))

    print()
    print('RESUME salle=%d meme_contenu=%d a_regarder=%d illisible=%d'
          % (len(lot), len(meme), len(different), len(illisible)))
    print('« meme_contenu » = le NAS a deja l image ou le flux : la copie de')
    print('Google ne porte que du hors-image, elle peut partir a la corbeille.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
