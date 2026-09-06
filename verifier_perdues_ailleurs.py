#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification — les 942 photos perdues existent-elles AILLEURS ?
------------------------------------------------------------------------------

Le registre (`docs/photos_perdues.md`) liste 942 photos dont le fichier est une
coquille : 2 a 3 Mo remplis de « Read error in the sector ! », sequelle de la
recuperation d un disque tombe en panne. Elles vont de **1983 a 2021**, et ce
sont les annees recentes qui interessent : plus de 350 datent de 2016-2021,
l ere du telephone, celle ou Google Photos sauvegardait tout automatiquement.
Avant de mettre quoi que ce soit a la corbeille — dont la purge a 180 jours ne
se rattrape pas — il faut savoir lesquelles sont recuperables.

DEUX RESERVOIRS, ET ILS NE SE VALENT PAS

  --index copie.db   Le NAS lui-meme, vu par l index : une photo dont le nom
                     existe AILLEURS dans la phototheque est peut-etre la meme,
                     rangee deux fois. Gratuit et exhaustif : aucune lecture
                     disque, l index connait deja tous les chemins.
  --ou <dossier>     Un dossier a parcourir (le Takeout Google, un vieux
                     disque). Repetable. Le chemin peut passer en `b64:` si il
                     contient des espaces.

CE QUE « TROUVEE » VEUT DIRE, ET CE QUE CA NE VEUT PAS DIRE

Le rapprochement se fait par NOM DE FICHIER. C est un indice fort — les noms
d appareil (`DSC01510.JPG`, `20180614_193355.jpg`) sont pratiquement uniques —
mais ce n est PAS une preuve : deux appareils peuvent produire `IMG_0001.JPG`.
Le banc verifie donc en plus que le candidat est une VRAIE image (ses premiers
octets), et qu il n est pas lui-meme une coquille. Il ne compare pas les
pixels : ce serait le geste suivant, sur une liste bien plus courte.

LECTURE SEULE. Rien n est copie, deplace ni ecrit — sauf le rapport.

USAGE (par l agent banc)
    verifier_perdues_ailleurs.py --index copie.db
    verifier_perdues_ailleurs.py --index copie.db --ou b64:QzpcR09PR0xFIFBIT1RPU1xleHRyYWl0
"""
import argparse
import base64
import io
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif',
             '.tif', '.tiff'}


def dejeton(arg):
    if isinstance(arg, str) and arg.startswith('b64:'):
        corps = arg[4:]
        return base64.urlsafe_b64decode(corps + '=' * (-len(corps) % 4)).decode('utf-8')
    return arg


def est_une_vraie_image(chemin):
    """Le candidat porte-t-il vraiment des pixels ? On lit 16 octets.

    Sans ce controle, une coquille rangee deux fois compterait comme un
    sauvetage -- et on effacerait l original en croyant avoir une copie."""
    try:
        with io.open(chemin, 'rb') as f:
            tete = f.read(16)
    except OSError:
        return False
    import tagging_meta
    return not tagging_meta.contenu_perdu(tagging_meta.classe_contenu(tete))


def reservoir_index(base, exclure):
    """{nom_minuscule: [chemins]} depuis l index -- le NAS, gratuitement."""
    if Path(base).name == 'photos.db':
        raise SystemExit('REFUS : ce banc lit une COPIE (--index copie.db).')
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).as_posix(), uri=True)
    par_nom = defaultdict(list)
    for (k,) in cx.execute('SELECT k FROM tags'):
        if k in exclure:
            continue
        par_nom[Path(k).name.lower()].append(k)
    cx.close()
    return par_nom


def reservoir_dossier(racine, budget_s, t0):
    """{nom_minuscule: [chemins]} en parcourant un dossier."""
    par_nom = defaultdict(list)
    r = Path(racine)
    if not r.is_dir():
        print('  ! reservoir introuvable : %s' % racine)
        return par_nom, 0
    n = 0
    for p in r.rglob('*'):
        if time.time() - t0 > budget_s:
            print('  ! BUDGET ATTEINT en parcourant %s -- resultat PARTIEL' % racine)
            break
        try:
            if p.is_file() and p.suffix.lower() in IMAGE_EXT:
                par_nom[p.name.lower()].append(str(p))
                n += 1
        except OSError:
            continue
    return par_nom, n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--registre', default='docs/photos_perdues.json')
    ap.add_argument('--index', default='')
    ap.add_argument('--ou', action='append', default=[], dest='dossiers')
    ap.add_argument('--budget-s', type=int, default=420)
    ap.add_argument('--rapport', default='docs/perdues_ailleurs.json')
    a = ap.parse_args(argv)

    reg = json.loads((ICI / a.registre).read_text(encoding='utf-8'))
    perdues = reg['photos']
    cles_perdues = {p['cle'] for p in perdues}
    print('%d photo(s) perdue(s) a retrouver.' % len(perdues))

    t0 = time.time()
    reservoirs = []
    if a.index:
        par_nom = reservoir_index(a.index, cles_perdues)
        print('  index : %d nom(s) distinct(s) ailleurs sur le NAS' % len(par_nom))
        reservoirs.append(('le NAS (index)', par_nom))
    for d in a.dossiers:
        chemin = dejeton(d)
        par_nom, n = reservoir_dossier(chemin, a.budget_s, t0)
        print('  %s : %d image(s), %d nom(s) distinct(s)'
              % (chemin, n, len(par_nom)))
        reservoirs.append((chemin, par_nom))
    if not reservoirs:
        raise SystemExit('aucun reservoir : donner --index et/ou --ou.')

    trouvees, par_annee_t, par_annee_n, detail = 0, Counter(), Counter(), []
    for p in perdues:
        nom = p['nom'].lower()
        an = (p.get('date') or '????')[:4]
        cands = []
        for etiquette, par_nom in reservoirs:
            for c in par_nom.get(nom, []):
                cands.append((etiquette, c))
        bons = [(e, c) for e, c in cands if est_une_vraie_image(c)]
        if bons:
            trouvees += 1
            par_annee_t[an] += 1
            detail.append({'perdue': p['cle'], 'date': p.get('date'),
                           'candidats': [{'ou': e, 'chemin': c} for e, c in bons]})
        else:
            par_annee_n[an] += 1
    print('-' * 66)
    print('RETROUVEES (meme nom, et le candidat porte de vrais pixels) : %d sur %d'
          % (trouvees, len(perdues)))
    print('par annee, retrouvees / perdues :')
    for an in sorted(set(par_annee_t) | set(par_annee_n)):
        print('  %s : %3d / %3d' % (an, par_annee_t[an],
                                    par_annee_t[an] + par_annee_n[an]))
    print('-' * 66)
    print('LE NOM N EST PAS UNE PREUVE : deux appareils peuvent ecrire')
    print('IMG_0001.JPG. Avant d effacer quoi que ce soit, regarder les')
    print('candidats -- la liste est dans le rapport, et elle est courte.')
    (ICI / a.rapport).write_text(json.dumps(
        {'quand': time.strftime('%Y-%m-%d %H:%M:%S'), 'perdues': len(perdues),
         'retrouvees': trouvees, 'detail': detail}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    print('rapport : %s' % a.rapport)
    return 0


if __name__ == '__main__':
    sys.exit(main())
