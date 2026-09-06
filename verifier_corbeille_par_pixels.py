#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les 37 << dernieres copies >> le sont-elles VRAIMENT ? Contre-mesure.

CE QUE LE PREMIER BANC A RATE. `verifier_corbeille_dernieres_copies.py` cherche
le contenu quarantine par son SHA256 dans le fonds, et conclut << derniere
copie >> quand il ne le trouve pas. Or une partie de ces groupes vient du bat 40
-- << dedoublonner par l IMAGE (memes pixels) >>. Deux fichiers y sont declares
doublons quand leurs PIXELS sont identiques, meme si leurs octets different :
un EXIF reecrit, une vignette incorporee, un logiciel qui a resauve le JPEG
suffisent. Le sha256 ne les reconnait donc PAS comme jumeaux, et le banc rend
<< derniere copie >> sur une photo qui existe pourtant, intacte, a deux dossiers
de la.

Trente-sept verdicts nets obtenus d un coup, sur un fonds dont on sait qu il a
ete dedoublonne par les pixels : c est le genre de score qui doit alarmer.

CE BANC-CI compare ce que le bat 40 comparait : les PIXELS. Pour chaque groupe,
il prend le NOM d origine, demande a l index les fichiers qui le portent
aujourd hui, et compare l image decodee -- pas les octets.

Ne deplace rien, ne supprime rien.

Usage : python verifier_corbeille_par_pixels.py
Sortie : docs/corbeille_par_pixels.json
"""

import hashlib
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'corbeille_par_pixels.json'


def empreinte_pixels(p):
    """sha256 de l image DECODEE : insensible a l EXIF, a la vignette
    incorporee, a une resauvegarde du JPEG. C est la comparaison que le bat 40
    a faite pour declarer ces fichiers doublons ; c est donc celle qui dit s il
    avait raison."""
    from PIL import Image, ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    with Image.open(p) as im:
        im = im.convert('RGB')
        return hashlib.sha256(im.tobytes()).hexdigest(), im.size


def index_par_nom(db, table='tags'):
    par = defaultdict(list)
    cx = sqlite3.connect('file:' + str(db) + '?mode=ro', uri=True, timeout=30)
    try:
        cx.execute('PRAGMA busy_timeout=30000')
        for (k,) in cx.execute(f'SELECT k FROM "{table}"'):
            par[Path(k).name.lower()].append(k)
    finally:
        cx.close()
    return par


def main():
    src = RACINE / 'docs' / 'corbeille_dernieres_copies.json'
    if not src.exists():
        print(f'Rapport absent : {src} — lance d abord '
              'verifier_corbeille_dernieres_copies.py')
        return 1
    a_juger = json.loads(src.read_text(encoding='utf-8'))['lignes']['derniere_copie']
    plan = json.loads((RACINE / 'docs' / 'plan_rangement.json')
                      .read_text(encoding='utf-8'))
    corb = Path(plan['corbeille'])

    t0 = time.time()
    par_nom = index_par_nom(RACINE / 'photos.db')
    print(f'index lu : {len(par_nom)} nom(s) distinct(s) en {time.time()-t0:.0f} s')
    if not par_nom:
        print('Index vide : je refuse de conclure.')
        return 1

    res = {'jumeau_pixels': [], 'vraie_derniere_copie': [], 'illisible': []}
    for e in a_juger:
        f = corb / e['groupe'] / e['fichier']
        # Le nom d ORIGINE, pas celui du fichier quarantine (prefixe du groupe).
        nom = Path(e.get('canonique_notee') or e['fichier']).name.lower()
        try:
            emp, dims = empreinte_pixels(f)
        except Exception as ex:
            res['illisible'].append({**e, 'erreur': f'{type(ex).__name__}: {ex}'})
            continue
        jumeau = None
        for c in par_nom.get(nom, []):
            try:
                if Path(c).exists() and empreinte_pixels(c)[0] == emp:
                    jumeau = c
                    break
            except Exception:
                continue
        entree = {**e, 'dims': list(dims), 'jumeau_pixels': jumeau,
                  'candidats_meme_nom': len(par_nom.get(nom, []))}
        res['jumeau_pixels' if jumeau else 'vraie_derniere_copie'].append(entree)

    RAPPORT.write_text(json.dumps(
        {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'), 'lignes': res},
        ensure_ascii=False, indent=1), encoding='utf-8')

    j, d, i = len(res['jumeau_pixels']), len(res['vraie_derniere_copie']), len(res['illisible'])
    o_d = sum(x['octets'] for x in res['vraie_derniere_copie'])
    print('-' * 68)
    print(f'MEMES PIXELS ailleurs  : {j}   <- doublon reel, le sha256 mentait')
    print(f'VRAIE derniere copie   : {d}   ({o_d/1024**2:.0f} Mo)')
    print(f'illisible              : {i}')
    for x in res['vraie_derniere_copie']:
        print(f"  [garder] {x['fichier']}  ({x['candidats_meme_nom']} homonyme(s) dans l index)")
    print(f'rapport : {RAPPORT.relative_to(RACINE)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
