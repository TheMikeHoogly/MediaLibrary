#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les 54 groupes qui restent en corbeille : lesquels sont la DERNIERE copie ?

Regarder ces photos ne repond pas a la question. La planche-contact montre des
chats, des mariages, le Leman -- de vraies photos de famille, et c est
justement ce qui trompe : la question n est pas << cette photo compte-t-elle ?
>> mais << existe-t-elle encore ailleurs ? >>. C est une question de machine,
pas d oeil. Un humain ne peut pas la trancher sur une vignette.

Methode, la meme que le bat 46, appliquee au contenu QUARANTINE cette fois :
  1. l empreinte du fichier quarantine ;
  2. les candidats de l index qui ont EXACTEMENT la meme taille (l index
     porte `size` ; comparer les tailles est gratuit, hacher ne l est pas) ;
  3. sha256 sur ces seuls candidats.
Une empreinte retrouvee -> la photo vit ailleurs, la copie quarantinee est un
vrai doublon. Aucune -> c est la DERNIERE copie : a RESTAURER, jamais a purger.

Ne deplace rien, ne supprime rien, n ecrit que son rapport.

Usage : python verifier_corbeille_dernieres_copies.py
Sortie : docs/corbeille_dernieres_copies.json
"""

import hashlib
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'corbeille_dernieres_copies.json'


def sha256(p, buf=1 << 16):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def index_par_taille(db, table='tags'):
    """{taille: [chemins]} depuis photos.db, en lecture seule."""
    par = defaultdict(list)
    cx = sqlite3.connect('file:' + str(db) + '?mode=ro', uri=True, timeout=30)
    try:
        cx.execute('PRAGMA busy_timeout=30000')
        for cle, val in cx.execute(f'SELECT k, v FROM "{table}"'):
            try:
                t = json.loads(val).get('size')
            except Exception:
                t = None
            if t:
                par[int(t)].append(cle)
    finally:
        cx.close()
    return par


def main():
    plan = json.loads((RACINE / 'docs' / 'plan_rangement.json')
                      .read_text(encoding='utf-8'))
    corb = Path(plan['corbeille'])
    if not corb.exists():
        print(f'Corbeille absente : {corb}')
        return 1
    db = RACINE / 'photos.db'
    t0 = time.time()
    par_taille = index_par_taille(db)
    n_cles = sum(len(v) for v in par_taille.values())
    print(f'index lu : {n_cles} photo(s) avec une taille, '
          f'{len(par_taille)} taille(s) distincte(s) en {time.time()-t0:.0f} s')
    if not par_taille:
        print('Index sans tailles : je refuse de conclure.')
        return 1

    lignes = {'derniere_copie': [], 'doublon_confirme': [], 'illisible': []}
    for g in sorted(p for p in corb.iterdir() if p.is_dir()):
        mani = None
        try:
            mani = json.loads((g / 'manifeste.json').read_text(encoding='utf-8'))
        except Exception:
            pass
        canon = (mani or {}).get('canonique') or ''
        if canon and Path(canon).exists():
            continue                      # purgeable, deja tranche
        fichiers = [f for f in g.iterdir()
                    if f.is_file() and f.name != 'manifeste.json']
        if not fichiers:
            continue
        f = fichiers[0]
        try:
            taille = f.stat().st_size
            emp = sha256(f)
        except OSError as e:
            lignes['illisible'].append({'groupe': g.name, 'fichier': f.name,
                                        'erreur': str(e)})
            continue
        jumeau = None
        for c in par_taille.get(taille, []):
            try:
                if Path(c).exists() and sha256(c) == emp:
                    jumeau = c
                    break
            except OSError:
                continue
        entree = {'groupe': g.name, 'fichier': f.name, 'octets': taille,
                  'canonique_notee': canon, 'jumeau': jumeau}
        lignes['doublon_confirme' if jumeau else 'derniere_copie'].append(entree)

    RAPPORT.parent.mkdir(exist_ok=True)
    RAPPORT.write_text(json.dumps(
        {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'), 'corbeille': str(corb),
         'lignes': lignes}, ensure_ascii=False, indent=1), encoding='utf-8')

    d, j, i = (len(lignes['derniere_copie']), len(lignes['doublon_confirme']),
               len(lignes['illisible']))
    o_d = sum(x['octets'] for x in lignes['derniere_copie'])
    o_j = sum(x['octets'] for x in lignes['doublon_confirme'])
    print('-' * 66)
    print(f'DERNIERE COPIE     : {d}   ({o_d/1024**2:.0f} Mo) <- A RESTAURER')
    print(f'doublon confirme   : {j}   ({o_j/1024**2:.0f} Mo) <- purgeable sans risque')
    print(f'illisible          : {i}')
    for x in lignes['derniere_copie'][:25]:
        print(f'  [restaurer] {x["fichier"]}')
    print(f'rapport : {RAPPORT.relative_to(RACINE)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
