#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inventaire — ce que pèse le fonds, et en quoi il est fait
──────────────────────────────────────────────────────────────────────────────

POURQUOI CET INSTRUMENT EXISTE

La copie hors site (point 12 bis) se décide sur un chiffre : combien de Go, et
répartis comment. Sans lui, tout conseil d'hébergeur est une opinion — les prix
se comptent au To, et un fonds de 200 Go ne se sauvegarde pas comme un fonds de
2 To. Le premier coûte quelques francs par mois chez n'importe qui ; le second
exclut la moitié des offres.

CE QU'IL SÉPARE, ET POURQUOI

Les photos et les vidéos ne pèsent pas du tout pareil, et ne valent pas pareil
non plus : une vidéo de vacances de 4 Go pèse autant que six cents photos. Les
compter ensemble cacherait que la facture est peut-être due à trente fichiers.
Le rapport donne donc le poids ET le nombre par famille, plus les plus gros
fichiers — c'est là que se décide ce qu'on sauvegarde en premier.

CE QU'IL NE FAIT PAS

Il n'ouvre aucun fichier : il lit la TAILLE que le système annonce, rien de
plus. Famille `inventaire_`, lecture seule, lançable au banc.

USAGE
    python inventaire_fonds.py
    python inventaire_fonds.py --json _fonds.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent

PHOTO = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.tif', '.tiff', '.gif',
         '.webp', '.bmp', '.dng', '.cr2', '.cr3', '.nef', '.arw', '.orf',
         '.rw2', '.raf'}
VIDEO = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.m2ts',
         '.wmv', '.mpg', '.mpeg', '.webm'}

GROS_MAX = 15          # les plus gros fichiers cités nommément


def famille(nom):
    """`photo`, `video` ou `autre` — d'après l'extension, en minuscules."""
    ext = os.path.splitext(nom)[1].lower()
    if ext in PHOTO:
        return 'photo'
    if ext in VIDEO:
        return 'video'
    return 'autre'


def racines(fichiers=None):
    """Les dossiers à mesurer, lus dans les fichiers de configuration du
    serveur — même source que `inventaire_fantomes`."""
    out = []
    for nom in (fichiers or ('dossiers_a_taguer.txt', 'dossier_uploads.txt')):
        p = RACINE / nom if not os.path.isabs(str(nom)) else Path(nom)
        try:
            lignes = p.read_text(encoding='utf-8').splitlines()
        except OSError:
            continue
        for ligne in lignes:
            ligne = ligne.strip()
            if ligne and not ligne.startswith('#') and ligne not in out:
                out.append(ligne)
    return out


def parcourir(racine):
    """`(chemin, octets)` pour chaque fichier sous `racine` ; `octets` vaut
    None quand la taille n'a pas pu être lue.

    `os.scandir`, et NON `os.walk` + `getsize`. Sur un partage SMB la seconde
    forme demande un aller-retour PAR FICHIER pour une réponse que
    l'énumération du dossier portait déjà : mesuré le 25/08, elle dépassait
    les dix minutes du banc là où celle-ci rend en quelques minutes. Sur un
    disque local la différence ne se voit pas — c'est le réseau qui la fait,
    et ce fonds vit sur le réseau."""
    piles = [str(racine)]
    while piles:
        dossier = piles.pop()
        try:
            it = os.scandir(dossier)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        piles.append(e.path)
                        continue
                    yield e.path, e.stat(follow_symlinks=False).st_size
                except OSError:
                    yield e.path, None


def mesurer(racine, parcours=None):
    """Rend (par_famille, gros, illisibles).

    `par_famille` : {famille: {'n': …, 'octets': …}}
    `gros`        : [(octets, chemin)] triés, les plus gros d'abord
    `illisibles`  : nombre de fichiers dont la taille n'a pas pu être lue —
                    COMPTÉS, jamais ignorés : un fonds mesuré à moitié qui se
                    dit complet est le mode de panne de tout inventaire."""
    par_famille = {}
    gros = []
    illisibles = 0
    for chemin, octets in (parcours or parcourir)(racine):
        if octets is None:
            illisibles += 1
            continue
        f = par_famille.setdefault(famille(os.path.basename(chemin)),
                                   {'n': 0, 'octets': 0})
        f['n'] += 1
        f['octets'] += octets
        gros.append((octets, chemin))
        if len(gros) > GROS_MAX * 20:
            gros.sort(reverse=True)
            del gros[GROS_MAX:]
    gros.sort(reverse=True)
    return par_famille, gros[:GROS_MAX], illisibles


def _go(octets):
    return octets / (1024.0 ** 3)


def rapport(par_famille, gros, illisibles, ecrire=print):
    """Dit le poids, le nombre, et ce qui n'a pas pu être lu."""
    total_n = sum(f['n'] for f in par_famille.values())
    total_o = sum(f['octets'] for f in par_famille.values())
    ecrire("")
    ecrire("=" * 74)
    ecrire("  LE FONDS — poids et composition")
    ecrire("=" * 74)
    ecrire("  %-8s %10s %12s %10s" % ("famille", "fichiers", "Go", "moyenne"))
    for nom in ('photo', 'video', 'autre'):
        f = par_famille.get(nom)
        if not f:
            continue
        moy = (f['octets'] / f['n'] / 1048576.0) if f['n'] else 0.0
        ecrire("  %-8s %10d %12.1f %7.1f Mo" % (nom, f['n'], _go(f['octets']),
                                                moy))
    ecrire("  " + "-" * 44)
    ecrire("  %-8s %10d %12.1f" % ("TOTAL", total_n, _go(total_o)))
    if illisibles:
        ecrire("")
        ecrire("  NON MESURES : %d fichier(s) dont la taille n a pas pu etre"
               % illisibles)
        ecrire("  lue. Le total ci-dessus est donc un PLANCHER.")
    if gros:
        ecrire("")
        ecrire("  LES PLUS GROS FICHIERS :")
        for octets, chemin in gros:
            ecrire("    %8.2f Go  %s" % (_go(octets), chemin))
    ecrire("=" * 74)
    return {'par_famille': par_famille, 'total_n': total_n,
            'total_octets': total_o, 'illisibles': illisibles,
            'gros': [{'octets': o, 'chemin': c} for o, c in gros]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--racine', default='')
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    cibles = [a.racine] if a.racine else racines()
    if not cibles:
        print("aucune racine a mesurer : ni --racine, ni dossiers_a_taguer.txt")
        return 2
    print("  mesure de %d racine(s)..." % len(cibles))
    par_famille, gros, illisibles = {}, [], 0
    for r in cibles:
        pf, g, ill = mesurer(r)
        for nom, v in pf.items():
            f = par_famille.setdefault(nom, {'n': 0, 'octets': 0})
            f['n'] += v['n']
            f['octets'] += v['octets']
        gros.extend(g)
        illisibles += ill
    gros.sort(reverse=True)
    r = rapport(par_famille, gros[:GROS_MAX], illisibles)
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        print("  liste ecrite : %s" % a.sortie_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
