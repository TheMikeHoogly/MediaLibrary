#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les ABSENTES du rapport Google sont-elles JETABLES, ou faut-il les sauver ?

Le bat 49 refuse d'effacer l'extrait du Takeout tant qu'une seule photo
n'existe QUE chez Google. C'est le bon réflexe, et il ne doit pas s'assouplir.
Mais il existe une famille d'absentes qui n'est pas une perte : la moitié
VIDÉO d'une Motion Photo, que Google exporte parfois SANS EXTENSION.

Le 09/09, la vérification en a listé 14 — les mêmes 14 fichiers sans extension
que Mike venait d'effacer du NAS après qu'on eut lu leurs premiers octets
(`00 00 00 18 66 74 79 70 6D 70 34 32` : une boîte `ftyp mp42`, donc du MP4).
Ils pèsent de 1 954 à 11 501 octets là où leur photo jumelle en pèse trois à
sept millions : ce sont des fragments, pas des films.

Deux preuves sont exigées ensemble, jamais une seule :
  1. une PHOTO de même tige existe dans le MÊME dossier Google — c'est la
     signature d'une Motion Photo ;
  2. les premiers octets du fichier portent une boîte `ftyp` — c'est du MP4,
     donc bien la moitié vidéo et pas une photo qu'on aurait mal nommée.

Une absente qui ne réunit pas les deux est déclarée À GARDER. Un fichier
illisible est déclaré À GARDER : sans preuve, on ne jette pas.

Code retour : 0 si TOUTES les absentes sont jetables (ou s'il n'y en a pas),
1 s'il en reste au moins une à sauver, 2 si le rapport est illisible.

  python verifier_absentes_jetables.py --rapport _google.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

EXT_IMAGE = {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.webp', '.gif',
             '.dng', '.tif', '.tiff'}


def _paire(chemin):
    """(dossier, tige, extension) en minuscules, séparateurs normalisés."""
    c = str(chemin).replace('\\', '/')
    dossier, base = c.rsplit('/', 1) if '/' in c else ('', c)
    tige, ext = os.path.splitext(base)
    return dossier.lower(), tige.lower(), ext.lower()


def stills_du_rapport(rapport):
    """{(dossier, tige): {noms de fichier}} des PHOTOS vues dans l'export.

    Tous les verdicts confondus : la photo d'une Motion Photo est le plus
    souvent CERTAIN ou PROBABLE (le NAS la porte) tandis que sa vidéo sort en
    ABSENT. Ne regarder que les absentes rendrait la jumelle invisible.

    On garde les NOMS et pas seulement les tiges, parce qu'un fichier ne doit
    jamais être sa propre jumelle : une absente nommée `perdue.jpg` s'inscrit
    ici, et sans cette précaution elle se verrait elle-même comme la photo qui
    l'autorise à disparaître. Trouvé par un test, pas à la relecture."""
    vus = {}
    for lst in (rapport.get('par_verdict') or {}).values():
        for x in (lst or ()):
            c = x.get('chemin_google')
            if not c:
                continue
            dossier, tige, ext = _paire(c)
            if ext in EXT_IMAGE:
                nom = str(c).replace('\\', '/').rsplit('/', 1)[-1].lower()
                vus.setdefault((dossier, tige), set()).add(nom)
    return vus


def est_mp4(chemin, lire=None):
    """(vrai/faux, raison) — le fichier commence-t-il par une boîte `ftyp` ?

    Un MP4 commence par la taille de la première boîte sur quatre octets, puis
    son type. On cherche `ftyp` aux octets 4 à 8. On ne devine RIEN à partir du
    nom : c'est justement le nom qui manque ici."""
    try:
        octets = (lire or _lire_debut)(chemin)
    except OSError as e:
        return False, "illisible (%s)" % e.__class__.__name__
    if len(octets) < 8:
        return False, "moins de 8 octets"
    return (octets[4:8] == b'ftyp'), ("ftyp" if octets[4:8] == b'ftyp'
                                      else "en-tete %r" % octets[:8])


def _lire_debut(chemin, n=12):
    with open(chemin, 'rb') as f:
        return f.read(n)


def juger(rapport, lire=None):
    """[(chemin, jetable, raison)] pour chaque ABSENTE du rapport."""
    stills = stills_du_rapport(rapport)
    out = []
    for x in ((rapport.get('par_verdict') or {}).get('ABSENT') or []):
        c = x.get('chemin_google')
        if not c:
            continue
        dossier, tige, ext = _paire(c)
        nom = str(c).replace('\\', '/').rsplit('/', 1)[-1].lower()
        # Une PHOTO absente n'est jamais la moitié vidéo de quoi que ce soit,
        # et ne peut pas non plus être sa propre jumelle.
        jumelle = bool(stills.get((dossier, tige), set()) - {nom})
        mp4, pourquoi = est_mp4(c, lire=lire)
        if jumelle and mp4:
            out.append((c, True, "moitie video d une Motion Photo "
                                 "(photo jumelle + %s)" % pourquoi))
        elif not jumelle:
            out.append((c, False, "aucune photo de meme nom dans ce dossier"))
        else:
            out.append((c, False, "photo jumelle, mais pas du MP4 : %s"
                                  % pourquoi))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--rapport', default='_google.json')
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    p = Path(a.rapport)
    if not p.is_file():
        print("rapport introuvable : %s" % a.rapport)
        return 2
    try:
        rapport = json.loads(p.read_text(encoding='utf-8'))
    except ValueError as e:
        print("rapport illisible : %s" % e)
        return 2

    verdicts = juger(rapport)
    if not verdicts:
        print("  Aucune absente. Rien a juger.")
        return 0

    jetables = [v for v in verdicts if v[1]]
    garder = [v for v in verdicts if not v[1]]
    print("=" * 74)
    print("  LES %d ABSENTE(S) : jetables, ou a sauver ?" % len(verdicts))
    print("=" * 74)
    if jetables:
        print("  JETABLES (%d) — moitie video d une Motion Photo :" % len(jetables))
        for c, _, r in jetables:
            print("    %s" % os.path.basename(c.replace('\\', '/')))
        print("    Regle de Mike, 08/09 : une Motion Photo ne garde que son")
        print("    image. Ces fichiers-la sont ce qu'on a decide de jeter.")
    if garder:
        print("")
        print("  A SAUVER (%d) — a copier sur le NAS avant tout :" % len(garder))
        for c, _, r in garder:
            print("    %s" % c)
            print("        %s" % r)
    print("=" * 74)

    if a.sortie_json:
        Path(a.sortie_json).write_text(json.dumps(
            {'jetables': [c for c, _, _ in jetables],
             'a_sauver': [{'chemin': c, 'pourquoi': r} for c, _, r in garder]},
            indent=1, ensure_ascii=False), encoding='utf-8')

    return 1 if garder else 0


if __name__ == '__main__':
    sys.exit(main())
