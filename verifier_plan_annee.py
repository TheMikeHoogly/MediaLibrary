#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifie le PLAN de rangement par annee AVANT de l appliquer.

CE QUE LE BAT 26 DISAIT, ET POURQUOI CA NE SUFFIT PAS

`appliquer_plan_annee.py` refuse d ecraser : quand le dossier d annee porte
deja un fichier du meme nom, il ecrit « [skip] destination deja prise
(collision) » et passe au suivant. La regle est bonne -- un deplacement ne
recouvre JAMAIS -- mais le message laisse Mike devant une question a laquelle
l outil ne repond pas : **est-ce le meme fichier, ou deux photos qui portent
le meme nom ?** Les deux cas demandent des gestes opposes :

  - MEME IMAGE : la copie d `_A TRIER` est un doublon, elle peut partir a la
    corbeille reversible ;
  - IMAGE DIFFERENTE : deux photos differentes se disputent un nom. Effacer
    l une des deux perd une photo. Il faut renommer, pas jeter.

Une collision n est donc PAS une permission d effacer, et c est exactement ce
que ce banc existe pour dire.

CE QU IL FAIT

Pour chaque deplacement du plan, il regarde si la cible est prise, et si oui
il compare les deux fichiers : `ImageDataHash` pour les images (les pixels
seuls, insensibles a la remorque de metadonnees), empreinte tete+milieu et
duree pour les videos -- le meme outillage que le bat 36, par le meme chemin
(fichier d arguments UTF-8, donc les chemins accentues passent entiers).

Et il applique la regle n. 2 du projet : **un doublon qui porte un nom humain
absent de sa canonique n est jamais « retirable »**, il passe en REVUE.

CE QU IL NE FAIT PAS

Il ne deplace rien, n efface rien, ne touche ni `photos.db` (snapshot en
lecture seule) ni les fichiers. Il ecrit un seul rapport,
`docs/plan_annee_collisions.json`. Famille `verifier_`, lancable au banc.

USAGE
    python verifier_plan_annee.py
    python verifier_plan_annee.py --plan docs/plan_rangement_annee.json
    python verifier_plan_annee.py --base copie.db      (controle des noms)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path, PureWindowsPath

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import verifier_doublons_atrier as V                            # noqa: E402

PLAN_DEFAUT = ICI / 'docs' / 'plan_rangement_annee.json'
RAPPORT = ICI / 'docs' / 'plan_annee_collisions.json'

# Les verdicts, du plus sur au moins sur. L ordre EST le classement affiche :
# ce qui demande un geste humain se lit en premier.
LIBRE = 'libre'
DOUBLON = 'doublon'
REVUE = 'revue'
VOISIN = 'voisin'
DIFFERENT = 'different'
ILLISIBLE = 'illisible'
ABSENT = 'source absente'


def nom(p):
    return PureWindowsPath(p).name


def charger_plan(chemin):
    try:
        d = json.loads(Path(chemin).read_text(encoding='utf-8'))
    except OSError:
        raise SystemExit('plan introuvable : %s' % chemin)
    except ValueError as e:
        raise SystemExit('plan illisible : %s' % e)
    return d.get('moves') or []


def noms_humains(base):
    """{chemin normalise -> {tags personne:/animal:}} depuis un SNAPSHOT."""
    if not base:
        return {}
    b = Path(base)
    if b.name == 'photos.db':
        raise SystemExit('refus : jamais sur photos.db (regle 4)')
    if not b.exists():
        print('  (pas de copie de la base : controle des noms desactive)')
        return {}
    return V.load_names(b)


def _o(n):
    """Une taille en Mo, courte -- c est une DONNEE, elle s aligne."""
    return '%.1f Mo' % (n / 1e6) if n else '?'


def comparer(src, dst, exe, hashes, durees, noms):
    """Le verdict d UNE collision, et la phrase qui l explique.

    La phrase porte les CHIFFRES des deux cotes quand ils different : « meme
    nom, flux different » laisse Mike devant le meme vide que le « [skip] »
    d origine. Deux tailles et deux durees lui disent en une ligne laquelle
    des deux copies il est en train de regarder."""
    if not os.path.exists(src):
        return ABSENT, 'la source n est plus la'
    ext = PureWindowsPath(src).suffix.lower()
    es, ed = V.empreinte_flux(src), V.empreinte_flux(dst)
    ts = es[0] if es else 0
    td = ed[0] if ed else 0
    quoi = 'image'
    if ext in V.IMAGE_EXT:
        hs, hd = hashes.get(V.hkey(src)), hashes.get(V.hkey(dst))
        if not hs or not hd:
            return ILLISIBLE, 'pas d empreinte d image des deux cotes'
        if hs != hd:
            return DIFFERENT, ('meme nom, PIXELS differents -- ici %s, '
                               'dans le fonds %s' % (_o(ts), _o(td)))
    elif ext in V.VIDEO_EXT:
        quoi = 'flux'
        if es is None or ed is None:
            return ILLISIBLE, 'fichier illisible'
        ds = durees.get(V.hkey(src), (0.0, ''))[0]
        dd = durees.get(V.hkey(dst), (0.0, ''))[0]
        if es != ed:
            chiffres = ('ici %s / %.2f s, dans le fonds %s / %.2f s'
                        % (_o(ts), ds, _o(td), dd))
            if es[1] == ed[1]:
                return DIFFERENT, 'meme debut, la suite differe -- ' + chiffres
            # MEME DUREE a 50 ms pres et taille a quelques pour-cent : les
            # octets different, mais pas la video. Le premier jet de ce banc
            # disait « deux films distincts » sur quatre fichiers qui font la
            # MEME duree a la centieme et 0,5 % de taille d ecart -- une
            # conclusion que la mesure ne portait pas. Hypothese NON VERIFIEE
            # pour l ecart d octets : le conteneur (l atome `moov` en tete
            # d un cote, en queue de l autre) decale tout le fichier, donc
            # l empreinte tete+milieu, sans qu une image change.
            ecart = abs(ts - td) / max(ts, td, 1)
            if abs(ds - dd) <= 0.05 and ds > 0 and ecart <= 0.05:
                return VOISIN, ('MEME DUREE, %.1f %% de taille d ecart -- '
                                'le meme film, conteneur different ? %s'
                                % (ecart * 100, chiffres))
            return DIFFERENT, 'DUREES differentes -- ' + chiffres
    else:
        return ILLISIBLE, 'ni image ni video connue'
    # Meme contenu. Reste la regle n. 2 : aucun nom humain ne se perd.
    manque = noms.get(V.hkey(src), set()) - noms.get(V.hkey(dst), set())
    if manque:
        return REVUE, ('meme %s, mais elle porte %s que la cible n a pas'
                       % (quoi, ', '.join(sorted(manque)[:3])))
    return DOUBLON, 'meme %s que la cible : doublon' % quoi


# Code de sortie « rien ne peut bouger » (16/09). Le bat 26 le lit pour
# s'arreter AVANT d'arreter le serveur : le 16/09, 19 cibles sur 19 etaient
# prises, et le bat a quand meme coupe le serveur puis rejoue deux fois
# « 19 skip » -- une etape qui ne pouvait pas aboutir (regle 9).
RIEN = 3


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', default=str(PLAN_DEFAUT))
    ap.add_argument('--base', default='copie.db')
    a = ap.parse_args(argv)

    moves = charger_plan(a.plan)
    age = time.time() - Path(a.plan).stat().st_mtime
    print('plan : %d deplacement(s), genere il y a %d min'
          % (len(moves), age / 60))
    if not moves:
        print('VERDICT : rien a ranger.')
        return RIEN

    prises = [m for m in moves if os.path.exists(m['dst'])]
    libres = len(moves) - len(prises)
    print('cibles LIBRES : %d   |   cibles DEJA PRISES : %d'
          % (libres, len(prises)))
    if not prises:
        print()
        print('VERDICT : aucune collision, le plan se range tel quel.')
        _ecrire({}, libres, a.plan)
        return 0

    exe = V.exiftool()
    if not exe:
        print('exiftool ABSENT : les collisions ne peuvent pas etre jugees.')
        return RIEN if libres == 0 else 2

    images, videos = [], []
    for m in prises:
        ext = PureWindowsPath(m['src']).suffix.lower()
        if ext in V.IMAGE_EXT:
            images += [m['src'], m['dst']]
        elif ext in V.VIDEO_EXT:
            videos += [m['src'], m['dst']]
    hashes = V.image_hashes(exe, images, lambda s: None) if images else {}
    dur = V.durees(exe, videos, lambda s: None) if videos else {}
    noms = noms_humains(ICI / a.base)

    par_verdict = {}
    for m in prises:
        v, pourquoi = comparer(m['src'], m['dst'], exe, hashes, dur, noms)
        par_verdict.setdefault(v, []).append(
            {'src': m['src'], 'dst': m['dst'], 'pourquoi': pourquoi})

    print()
    for v in (DIFFERENT, VOISIN, REVUE, ILLISIBLE, ABSENT, DOUBLON):
        lot = par_verdict.get(v) or []
        if not lot:
            continue
        print('%-14s : %d' % (v.upper(), len(lot)))
        for e in lot[:8]:
            print('   %-26s %s' % (V.asc(nom(e['src'])), V.asc(e['pourquoi'])))
        if len(lot) > 8:
            print('   ... et %d autre(s)' % (len(lot) - 8))

    n_voi = len(par_verdict.get(VOISIN) or [])
    n_dif = len(par_verdict.get(DIFFERENT) or [])
    n_dup = len(par_verdict.get(DOUBLON) or [])
    n_rev = len(par_verdict.get(REVUE) or [])
    print()
    print('CE QUE CA VEUT DIRE')
    if n_dup:
        print('  %d fichier(s) d _A TRIER sont le MEME que celui deja range :'
              % n_dup)
        print('    des doublons. Le bat 36 sait les retirer vers la corbeille')
        print('    reversible -- ils n ont pas a etre effaces a la main.')
    if n_rev:
        print('  %d portent un NOM HUMAIN que la cible n a pas : a fusionner'
              % n_rev)
        print('    AVANT tout retrait. Un nom perdu ne se retrouve pas.')
    if n_voi:
        print('  %d %s la MEME DUREE et une taille tres proche : les octets'
              % (n_voi, 'a' if n_voi == 1 else 'ont'))
        print('    different, la video non. Ce banc ne peut pas trancher plus')
        print('    loin -- les regarder, pas les jeter sur ce seul ecart.')
    if n_dif:
        print('  %d %s le MEME NOM et des DUREES differentes : ce sont deux'
              % (n_dif, 'a' if n_dif == 1 else 'ont'))
        print('    fichiers distincts. En effacer un en perd un. Renommer.')
    print()
    print('VERDICT libres=%d doublons=%d revue=%d voisins=%d differents=%d '
          'illisibles=%d'
          % (libres, n_dup, n_rev, n_voi, n_dif,
             len(par_verdict.get(ILLISIBLE) or [])))
    print('Une collision n est PAS une permission d effacer.')
    _ecrire(par_verdict, libres, a.plan)
    if libres == 0:
        print()
        print('RIEN NE PEUT BOUGER : toutes les cibles sont prises. Le rangement')
        print('sauterait les %d -- inutile d arreter le serveur pour ca.' % len(prises))
        return RIEN
    return 0


def _ecrire(par_verdict, libres, plan):
    rap = {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
           'plan': str(plan), 'libres': libres,
           'par_verdict': {k: v for k, v in par_verdict.items()}}
    try:
        RAPPORT.parent.mkdir(exist_ok=True)
        RAPPORT.write_text(json.dumps(rap, ensure_ascii=False, indent=1),
                           encoding='utf-8')
        print('Rapport : %s' % RAPPORT.name)
    except OSError as e:
        print('rapport non ecrit : %s' % e)


if __name__ == '__main__':
    sys.exit(main())
