#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification -- QUE SONT, au juste, les images que le tagueur ne sait pas lire ?
------------------------------------------------------------------------------

`/sante` en annonce plus de mille, toutes sous le meme libelle : « Analyse IA
impossible -- image illisible ». Un libelle unique pour des causes differentes
empeche de decider quoi que ce soit : on ne peut ni les ecarter, ni les
reparer, ni meme savoir combien meritent l'un ou l'autre.

Ce banc les OUVRE, quelques octets chacune, et les CLASSE. Il ne repare rien,
ne retire rien, n'ecrit rien dans l'index : il rend un rapport.

LES CLASSES, et ce qu'elles impliquent

  perdu-texte   Le fichier commence par du TEXTE (« Read error in ... ») : un
                outil de recuperation de disque a ecrit son message d'erreur
                DANS le fichier, a la place des pixels. Poids normal, contenu
                perdu. Aucune taille minimale ne les attrape -- ce ne sont pas
                des vignettes.
  perdu-vide    Que des octets nuls au debut. Meme famille : le fichier a la
                bonne taille et rien dedans.
  tronquee      Vrai debut de JPEG/PNG, mais la fin manque (pas de marqueur de
                fin). L'image existe en partie.
  vignette      Image VALIDE, mais minuscule -- c'est le cas que Mike soupconne.
                On mesure ses PIXELS, pas ses octets : une photo de 2005 pese
                peu et fait quand meme 1600x1200 ; une vignette de 160x120 peut
                peser plus qu'elle apres un mauvais reencodage.
  image         Image valide, de taille normale : si elle est ici, la cause est
                ailleurs (droits, HEIC sans greffon, hoquet SMB au moment du
                tagage). A ne PAS ecarter.
  absente       Le fichier n'est plus la.

USAGE (par l'agent banc)
    verifier_images_illisibles.py --base copie.db
    verifier_images_illisibles.py --base copie.db --budget-s 300 --max 400
"""
import argparse
import io
import json
import sqlite3
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
# Le seuil de vignette vit dans `tagging_meta.VIGNETTE_MAX_PX` : une seule
# valeur, et c'est celle que le serveur applique.


def entrees_illisibles(base):
    """Les cles que l'index declare en echec de LECTURE d'image."""
    if Path(base).name == 'photos.db':
        raise SystemExit('REFUS : ce banc lit une COPIE (--base copie.db), '
                         'jamais photos.db -- le serveur est l ecrivain unique.')
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).as_posix(), uri=True)
    out = []
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if not isinstance(e, dict) or not e.get('failed'):
            continue
        err = str(e.get('error') or '')
        if 'illisible' in err or 'identify image file' in err or 'truncated' in err:
            out.append((k, err[:120]))
    cx.close()
    return out


def dimensions(chemin):
    """(largeur, hauteur) sans decoder l image, ou None. PIL lit l en-tete."""
    try:
        from PIL import Image
        with Image.open(chemin) as im:
            return im.size
    except Exception:
        return None


def classer(chemin):
    """(classe, taille_octets, dimensions|None).

    N ouvre que quelques octets ; le VERDICT vient de
    `tagging_meta.classe_contenu`, la MEME regle que le serveur applique en
    marquant un echec. Ce banc a d abord porte sa propre copie de la regle : la
    garder aurait fabrique la divergence que ce projet passe son temps a
    reparer -- deux endroits qui repondent a la meme question, et un jour deux
    reponses.
    """
    import tagging_meta
    p = Path(chemin)
    try:
        taille = p.stat().st_size
    except OSError:
        return 'absente', 0, None
    try:
        with io.open(p, 'rb') as f:
            tete = f.read(64)
            queue = b''
            if taille > 2:
                f.seek(-2, 2)
                queue = f.read(2)
    except OSError as e:
        return 'illisible-disque:' + str(e)[:40], taille, None
    dims = dimensions(p)
    return tagging_meta.classe_contenu(tete, queue, taille, dims), taille, dims


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--budget-s', type=int, default=300)
    ap.add_argument('--max', type=int, default=0, help='0 = toutes')
    ap.add_argument('--rapport', default='docs/images_illisibles.json')
    a = ap.parse_args(argv)

    cles = entrees_illisibles(a.base)
    if a.max:
        cles = cles[:a.max]
    print('entrees en echec de lecture dans l index : %d' % len(cles))
    t0 = time.time()
    par_classe = {}
    detail = []
    vus = 0
    for cle, err in cles:
        if time.time() - t0 > a.budget_s:
            break
        classe, taille, dims = classer(cle)
        vus += 1
        d = par_classe.setdefault(classe, {'n': 0, 'octets': 0, 'exemples': []})
        d['n'] += 1
        d['octets'] += taille
        if len(d['exemples']) < 3:
            d['exemples'].append({'cle': cle, 'octets': taille, 'dims': dims})
        detail.append({'cle': cle, 'classe': classe, 'octets': taille,
                       'dims': list(dims) if dims else None})
    print('regardees : %d en %.0f s%s' % (vus, time.time() - t0,
          '' if vus == len(cles) else ' (BUDGET ATTEINT -- relancer pour la suite)'))
    print('-' * 66)
    for classe, d in sorted(par_classe.items(), key=lambda x: -x[1]['n']):
        print('%-12s %5d  (%.1f Go au total)' % (classe, d['n'], d['octets'] / 1e9))
        for ex in d['exemples']:
            print('               %s  %d o  %s' % (Path(ex['cle']).name[:44],
                                                   ex['octets'], ex['dims'] or ''))
    print('-' * 66)
    n_vign = par_classe.get('vignette', {}).get('n', 0)
    n_perdu = sum(par_classe.get(c, {}).get('n', 0)
                  for c in ('perdu-texte', 'perdu-vide', 'tronquee'))
    print('CE QUE CA DIT :')
    print('  %d vignette(s) -- des images VALIDES mais minuscules (<= %d px).'
          % (n_vign, __import__('tagging_meta').VIGNETTE_MAX_PX))
    print('     Ce sont les seules qu une regle de taille peut ecarter, et')
    print('     elle doit se prononcer sur les PIXELS, pas sur les octets.')
    print('  %d fichier(s) au contenu PERDU (perdu-texte, perdu-vide, tronquee).' % n_perdu)
    print('     Poids normal, pixels absents : AUCUN seuil de taille ne les')
    print('     attrape. Les ecarter est une autre decision -- ils ne sont pas')
    print('     « pas des photos », ils sont des photos CASSEES, et c est a')
    print('     Mike de dire s il veut les voir listees ou rangees a part.')
    print('  %d valide(s) : la cause est ailleurs. Ne PAS les ecarter.'
          % par_classe.get('image', {}).get('n', 0))
    rap = ICI / a.rapport
    rap.parent.mkdir(parents=True, exist_ok=True)
    rap.write_text(json.dumps({'quand': time.strftime('%Y-%m-%d %H:%M:%S'),
                               'vignette_max_px': __import__('tagging_meta').VIGNETTE_MAX_PX,
                               'regardees': vus, 'total': len(cles),
                               'par_classe': {c: {'n': d['n'], 'octets': d['octets']}
                                              for c, d in par_classe.items()},
                               'detail': detail}, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print('rapport : %s' % a.rapport)
    return 0


if __name__ == '__main__':
    sys.exit(main())
