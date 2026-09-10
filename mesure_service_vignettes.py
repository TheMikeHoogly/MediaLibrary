#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le cache de vignettes sert-il encore a quelque chose ? — analyse du 10/09.

Le compte de O15 a laisse une question ouverte, et elle est plus interessante
que les 722 Mo : `photo_thumbs` contient 7 737 fichiers, dont **2 561
seulement** portent un nom que le serveur demanderait aujourd'hui. Pour
44 604 photos et quatre variantes possibles chacune (512, 1600, et leurs
equivalents video), cela fait un cache qui ne repond presque plus.

Ce banc chiffre trois choses, et rien d'autre :

  1. **LE TAUX DE SERVICE** — combien de photos ont, ici et maintenant, une
     vignette 512 utilisable. C'est ce que l'utilisateur ressent : une case de
     galerie sans vignette en cache, c'est un original de 2 a 6 Mo relu sur le
     NAS.
  2. **LA VITESSE DE PEREMPTION** — combien de photos ont vu leur `mtime`
     changer dans les dernieres 24 h, 7 j, 30 j. Le nom du cache est
     `md5(cle|taille|MTIME)` : chaque changement de mtime jette la vignette.
     Or **ecrire un tag XMP change le mtime sans changer un seul pixel**.
  3. **CE QUI POURRAIT SERVIR DE CLE STABLE** — quels champs de l'index
     survivent a une ecriture de tag. S'il n'y en a aucun, la conclusion n'est
     pas « changer de champ » mais « changer de mecanique ».

Il ne propose rien et ne modifie rien.

  python mesure_service_vignettes.py
"""

import hashlib
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))


def main(argv=None):
    from store_sqlite import open_store
    if not (RACINE / 'photos.db').exists():
        print('  photos.db absente.')
        return 2
    tags = open_store(RACINE / 'tags_index.json', RACINE, None).data

    presents = set()
    d = RACINE / 'photo_thumbs'
    if d.is_dir():
        with os.scandir(d) as it:
            presents = {Path(x.name).stem for x in it if x.is_file()}

    maintenant = time.time()
    n = 0
    servies512 = servies1600 = 0
    sans_mtime = 0
    fenetres = {1: 0, 7: 0, 30: 0}
    tailles = {'avec_size': 0}
    for cle, e in tags.items():
        if not isinstance(e, dict):
            continue
        n += 1
        mt = e.get('mtime')
        if mt is None:
            sans_mtime += 1
        else:
            age = (maintenant - float(mt)) / 86400
            for f in fenetres:
                if age < f:
                    fenetres[f] += 1
        if e.get('size') is not None:
            tailles['avec_size'] += 1
        # NOUVEAU NOMMAGE (10/09) : le nom ne porte plus le mtime. Mais la
        # VALIDITE, elle, le compare toujours — d'ou le stat ci-dessous. Un
        # fichier present mais mal tamponne ne SERT pas.
        h512 = hashlib.md5(f"{cle}|512".encode('utf-8', 'replace')).hexdigest()
        h1600 = hashlib.md5(f"{cle}|1600".encode('utf-8', 'replace')).hexdigest()
        for h, compteur in ((h512, '512'), (h1600, '1600')):
            if h not in presents:
                continue
            # Present ne veut pas dire SERVI : le tampon doit concorder.
            try:
                st = (d / (h + '.jpg')).stat()
            except OSError:
                continue
            if mt is not None and int(st.st_mtime) != int(mt):
                continue
            if compteur == '512':
                servies512 += 1
            else:
                servies1600 += 1

    print('=' * 74)
    print('  LE CACHE DE VIGNETTES SERT-IL ENCORE ?')
    print('=' * 74)
    print('  photos dans l index          : %d' % n)
    print('  fichiers dans photo_thumbs   : %d' % len(presents))
    print('-' * 74)
    print('  1) TAUX DE SERVICE — ce que l utilisateur ressent')
    print('     photos avec une vignette 512  utilisable : %6d  (%.1f %%)'
          % (servies512, 100.0 * servies512 / max(n, 1)))
    print('     photos avec une vignette 1600 utilisable : %6d  (%.1f %%)'
          % (servies1600, 100.0 * servies1600 / max(n, 1)))
    print('     -> une case de galerie sans vignette relit l ORIGINAL sur le')
    print('        NAS : 2 a 6 Mo au lieu de ~50 Ko.')
    print('-' * 74)
    print('  2) VITESSE DE PEREMPTION — combien de photos ont change de mtime')
    for f in (1, 7, 30):
        print('     dans les %2d dernier(s) jour(s) : %6d photo(s)  (%.1f %%)'
              % (f, fenetres[f], 100.0 * fenetres[f] / max(n, 1)))
    print('     -> chacune a jete ses vignettes, sans qu un seul pixel change :')
    print('        ecrire un tag XMP change le mtime.')
    print('-' * 74)
    print('  3) UNE CLE STABLE EXISTE-T-ELLE DANS L INDEX ?')
    print('     entrees portant `size`  : %d  (change aussi a chaque ecriture'
          % tailles['avec_size'])
    print('       de tag : le bloc XMP grossit)')
    print('     entrees sans `mtime`    : %d' % sans_mtime)
    print('     -> aucun champ ne decrit les PIXELS. Le cache est donc indexe')
    print('        sur une identite de FICHIER pour retrouver une image qui,')
    print('        elle, n a pas bouge.')
    print('=' * 74)
    print('  Rien n a ete modifie : ce banc LIT.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
