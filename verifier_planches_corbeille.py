#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Planches-contact des groupes de corbeille que le bat 46 n a PAS pu reancrer.

Apres le bat 46 (325 groupes reancres sur preuve d empreinte) et le bat 24
(364 fichiers purges, 25,36 Go rendus), il reste des groupes que la purge
refuse : leur canonique -- la copie GARDEE -- reste introuvable. Le nom existe
peut-etre encore dans le fonds, mais porte par une AUTRE photo ; ou il n existe
plus du tout.

Ces groupes-la sont l inverse d un dechet : la copie quarantinee est peut-etre
la DERNIERE trace de la photo. Le bon geste y est de RESTAURER, pas de purger
-- mais ca ne se decide pas sur un nom de fichier, ca se decide en regardant.

Ce banc assemble donc ce qu il y a DEDANS, en planches numerotees, dans
`_planches_corbeille/`. Il ne deplace rien, ne supprime rien, n ecrit pas dans
l index. Basse definition volontaire : on reconnait ce qu est une image, on ne
la contemple pas.

Usage :
    python verifier_planches_corbeille.py
    python verifier_planches_corbeille.py --cote 460 --par-planche 9
Sortie : _planches_corbeille/planche_N.jpg + planches.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SORTIE = RACINE / '_planches_corbeille'


def lire_json(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception:
        return defaut


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--cote', type=int, default=460)
    ap.add_argument('--par-planche', type=int, default=9)
    ap.add_argument('--colonnes', type=int, default=3)
    a = ap.parse_args(argv)

    try:
        from PIL import Image, ImageDraw, ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
    except ImportError:
        print('Pillow absent.')
        return 1

    plan = lire_json(RACINE / 'docs' / 'plan_rangement.json', {})
    corbeille = Path(plan.get('corbeille') or '')
    if not corbeille.exists():
        print(f'Corbeille absente : {corbeille}')
        return 1

    # Les groupes qui restent A JUGER : canonique notee absente, et pas de
    # marque de reancrage. Un groupe sans manifeste compte aussi -- on ne sait
    # meme pas ce qu il gardait.
    a_juger = []
    for g in sorted(p for p in corbeille.iterdir() if p.is_dir()):
        mani = lire_json(g / 'manifeste.json')
        if mani is None:
            a_juger.append((g, '(pas de manifeste)', 'sans manifeste'))
            continue
        canon = mani.get('canonique') or ''
        if canon and Path(canon).exists():
            continue                       # purgeable, rien a juger
        pourquoi = ('nom repris par une autre photo'
                    if canon and Path(canon).name else 'aucun candidat')
        a_juger.append((g, canon, pourquoi))

    if not a_juger:
        print('Rien a juger : tous les groupes ont leur canonique.')
        return 0

    SORTIE.mkdir(exist_ok=True)
    for vieux in SORTIE.glob('planche_*.jpg'):
        vieux.unlink()

    cote, par, cols = a.cote, a.par_planche, a.colonnes
    lignes = (par + cols - 1) // cols
    marge = 34                              # deux lignes de legende
    index, planche_no, illisibles = [], 0, 0

    for depart in range(0, len(a_juger), par):
        lot = a_juger[depart:depart + par]
        planche_no += 1
        toile = Image.new('RGB', (cols * cote, lignes * (cote + marge)),
                          (24, 24, 26))
        crayon = ImageDraw.Draw(toile)
        for i, (groupe, canon, pourquoi) in enumerate(lot):
            n = depart + i + 1
            x, y = (i % cols) * cote, (i // cols) * (cote + marge)
            fichiers = [f for f in groupe.iterdir()
                        if f.is_file() and f.name != 'manifeste.json']
            etat = 'ok'
            if not fichiers:
                etat = 'groupe vide'
                crayon.text((x + 12, y + cote // 2), etat, fill=(220, 90, 90))
            else:
                try:
                    im = Image.open(fichiers[0])
                    im.draft('RGB', (cote, cote))
                    im = im.convert('RGB')
                    im.thumbnail((cote, cote))
                    toile.paste(im, (x + (cote - im.width) // 2,
                                     y + (cote - im.height) // 2))
                except Exception as e:
                    etat = f'illisible ({type(e).__name__})'
                    illisibles += 1
                    crayon.text((x + 12, y + cote // 2), etat, fill=(220, 90, 90))
            nom_fic = fichiers[0].name if fichiers else '—'
            crayon.text((x + 8, y + cote + 4), f'{n:>2}. {nom_fic[:46]}',
                        fill=(230, 226, 220))
            crayon.text((x + 8, y + cote + 18), f'    {pourquoi}',
                        fill=(163, 156, 147))
            index.append({'n': n, 'planche': planche_no, 'groupe': groupe.name,
                          'fichier': nom_fic, 'canonique_notee': canon,
                          'pourquoi': pourquoi, 'etat': etat,
                          'octets': sum(f.stat().st_size for f in fichiers)})
        p_out = SORTIE / f'planche_{planche_no}.jpg'
        toile.save(p_out, quality=76, optimize=True)
        print(f'{p_out.name} : {len(lot)} case(s), '
              f'{p_out.stat().st_size/1024:.0f} Ko')

    (SORTIE / 'planches.json').write_text(json.dumps(
        {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
         'corbeille': str(corbeille), 'cases': index},
        ensure_ascii=False, indent=1), encoding='utf-8')
    total = sum(c['octets'] for c in index)
    print('-' * 62)
    print(f'{len(a_juger)} groupe(s) a juger sur {planche_no} planche(s) ; '
          f'{illisibles} illisible(s) ; {total/1024**3:.2f} Go')
    print('sortie : _planches_corbeille/  (index : planches.json)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
