#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Planches-contact des photos que le banc « sensibles » n a pas classees « non ».

Pourquoi : `docs/sensibles_echantillon.json` rend un verdict par photo, mais un
verdict n est pas une image. Pour que Mike -- ou Claude -- tranche, il faut
VOIR. Ce banc assemble les photos concernees en quelques planches numerotees,
ecrites dans `_planches/` (ignore par git, hors du fonds) : un seul regard
suffit alors pour une dizaine de photos.

Il ne DEPLACE rien, ne marque rien, n ecrit pas dans l index. Les planches sont
volontairement en basse definition : on veut reconnaitre la NATURE d une image
(facture ? photo de famille ?), jamais lire ce qu elle raconte -- c est la
regle du chantier 18, et une planche lisible mot a mot la violerait.

Usage :
    python verifier_planches_sensibles.py
    python verifier_planches_sensibles.py --verdicts illisible
    python verifier_planches_sensibles.py --cote 520 --par-planche 6
Sortie : _planches/planche_N.jpg + _planches/planches.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SORTIE = RACINE / '_planches'
ECHANTILLON = RACINE / 'docs' / 'sensibles_echantillon.json'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--verdicts', default='',
                    help='ne garder que ces verdicts (virgules) ; '
                         'defaut = tout sauf « non »')
    ap.add_argument('--cote', type=int, default=520, help='cote d une case (px)')
    ap.add_argument('--par-planche', type=int, default=6)
    ap.add_argument('--colonnes', type=int, default=3)
    a = ap.parse_args(argv)

    try:
        from PIL import Image, ImageDraw, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
    except ImportError:
        print('Pillow absent.')
        return 1

    if not ECHANTILLON.exists():
        print(f'Echantillon absent : {ECHANTILLON}')
        return 1
    donnees = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
    lignes = donnees.get('lignes', [])

    garder = {v.strip() for v in a.verdicts.split(',') if v.strip()}
    if garder:
        choisies = [l for l in lignes if l.get('verdict') in garder]
    else:
        choisies = [l for l in lignes if l.get('verdict') != 'non']
    if not choisies:
        print('Rien a montrer.')
        return 0

    SORTIE.mkdir(exist_ok=True)
    for vieux in SORTIE.glob('planche_*.jpg'):
        vieux.unlink()

    cote, par, cols = a.cote, a.par_planche, a.colonnes
    lignes_grille = (par + cols - 1) // cols
    marge = 26  # bandeau du numero, sous chaque case
    index, planche_no, manquantes = [], 0, 0

    for depart in range(0, len(choisies), par):
        lot = choisies[depart:depart + par]
        planche_no += 1
        toile = Image.new('RGB', (cols * cote, lignes_grille * (cote + marge)),
                          (24, 24, 26))
        crayon = ImageDraw.Draw(toile)
        for i, l in enumerate(lot):
            n = depart + i + 1
            x = (i % cols) * cote
            y = (i // cols) * (cote + marge)
            chemin = Path(l['key'])
            etat = 'ok'
            try:
                im = Image.open(chemin)
                im.draft('RGB', (cote, cote))
                im = im.convert('RGB')
                im.thumbnail((cote, cote))
                toile.paste(im, (x + (cote - im.width) // 2,
                                 y + (cote - im.height) // 2))
            except Exception as e:
                etat = f'illisible ({type(e).__name__})'
                manquantes += 1
                crayon.text((x + 12, y + cote // 2), etat, fill=(220, 90, 90))
            crayon.text((x + 10, y + cote + 6),
                        f"{n:>2}. {l.get('verdict')} - {chemin.name[:44]}",
                        fill=(230, 226, 220))
            index.append({'n': n, 'planche': planche_no,
                          'verdict': l.get('verdict'), 'groupe': l.get('groupe'),
                          'key': l['key'], 'etat': etat})
        chemin_planche = SORTIE / f'planche_{planche_no}.jpg'
        toile.save(chemin_planche, quality=78, optimize=True)
        print(f'{chemin_planche.name} : {len(lot)} case(s), '
              f'{chemin_planche.stat().st_size/1024:.0f} Ko')

    (SORTIE / 'planches.json').write_text(json.dumps(
        {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
         'source': str(ECHANTILLON.name), 'cases': index},
        ensure_ascii=False, indent=1), encoding='utf-8')
    print('-' * 62)
    print(f'{len(choisies)} photo(s) sur {planche_no} planche(s) ; '
          f'{manquantes} illisible(s) sur disque')
    print(f'sortie : _planches/  (index : planches.json)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
