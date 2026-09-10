#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ce que gardent les trois caches de vignettes — point d'audit O15.

Trois dossiers locaux servent de cache : `photo_thumbs` (grille 512 px et plein
ecran 1600 px, plus les images-cles de video), `face_thumbs` (decoupes de
visages) et `animal_thumbs` (decoupes d'animaux). **Rien ne les purge jamais.**
Le code le dit lui-meme, dans `_serve_thumb` :

    « Les anciennes vignettes orphelines restent sur disque
      (purge maintenance : a traiter avec O15). »

Le nom de fichier est une empreinte de ce qui DEFINIT la vignette :

    photo   md5("<cle>|<taille>")                     512 et 1600
    video   md5("<cle>|<taille>|video")
    visage  md5("<cle>|<index>|<bbox>")
    animal  md5("a|<cle>|<index>|<bbox>")

**Les deux premieres ont CHANGE le 10/09**, et c'est le correctif du cache :
elles portaient le MTIME, que l'ecriture d'un tag XMP change sans toucher un
pixel. Le nom dit maintenant QUELLE vignette c'est ; c'est le TAMPON (le mtime
du fichier de cache, mis a celui de la source) qui dit si elle est a jour.
Consequence pour ce banc : une vignette de photo n'est plus orpheline parce que
la photo a ete retaguee — elle l'est parce que la photo a ete RENOMMEE ou a
disparu. **Et tous les fichiers de l'ancien format sont, eux, orphelins d'un
coup** : c'est une migration, pas une derive, et le bat 51 la traite avec
`--formule-changee`.

Ce banc ne suppose pas : il RECALCULE les noms vivants depuis l'index et compte
ce qui reste.

Il n'efface RIEN. Il rend un compte et, avec `--liste`, ecrit la liste des
orphelines pour qu'un outil de purge — ecrit apres, et separement — ait de quoi
travailler.

  python mesure_caches_vignettes.py
  python mesure_caches_vignettes.py --liste _vignettes_orphelines.json
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

DOSSIERS = {
    'photo_thumbs':  'grille 512 px, plein ecran 1600 px, images-cles video',
    'face_thumbs':   'decoupes de visages',
    'animal_thumbs': 'decoupes d animaux',
}


def _md5(s):
    return hashlib.md5(s.encode('utf-8', 'replace')).hexdigest()


def noms_vivants(tags, faces, animals):
    """Les noms de fichier qu'un cache PEUT servir aujourd'hui, par dossier.

    Recalcule EXACTEMENT les formules de `server.py`. Si l'une d'elles change
    la-bas sans changer ici, ce banc declarera orphelin tout le cache : c'est
    voyant, et c'est voulu — un banc qui se trompe en silence serait pire."""
    photo, visage, animal = set(), set(), set()
    for k, _e in tags.items():
        for s in (512, 1600):
            photo.add(_md5(f"{k}|{s}"))
            photo.add(_md5(f"{k}|{s}|video"))
    for k, e in (faces or {}).items():
        for i, f in enumerate(e.get('faces') or []):
            visage.add(_md5(f"{k}|{i}|{f.get('bbox', [0, 0, 0, 0])}"))
    for k, e in (animals or {}).items():
        for i, a in enumerate(e.get('animals') or []):
            animal.add(_md5(f"a|{k}|{i}|{a.get('bbox', [0, 0, 0, 0])}"))
    return {'photo_thumbs': photo, 'face_thumbs': visage,
            'animal_thumbs': animal}


def inventorier(dossier):
    """(n, octets, plus_vieux_jours) — un seul `scandir`, pas de `stat` en
    plus : ces dossiers portent des dizaines de milliers d'entrees."""
    n, poids, vieux, noms = 0, 0, None, {}
    d = RACINE / dossier
    if not d.is_dir():
        return 0, 0, None, {}
    maintenant = time.time()
    with os.scandir(d) as it:
        for x in it:
            if not x.is_file():
                continue
            st = x.stat()
            n += 1
            poids += st.st_size
            age = (maintenant - st.st_mtime) / 86400
            vieux = age if vieux is None else max(vieux, age)
            noms[Path(x.name).stem] = (st.st_size, st.st_mtime)
    return n, poids, vieux, noms


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--liste', default='',
                    help='ecrire la liste des orphelines dans ce JSON')
    a = ap.parse_args(argv)

    from store_sqlite import open_store
    if not (RACINE / 'photos.db').exists():
        print('  photos.db absente.')
        return 2
    tags = open_store(RACINE / 'tags_index.json', RACINE, None).data
    faces = open_store(RACINE / 'faces_index.json', RACINE, None).data
    animaux = open_store(RACINE / 'animals_index.json', RACINE, None).data

    vivants = noms_vivants(tags, faces, animaux)

    print('=' * 74)
    print('  O15 — LES TROIS CACHES DE VIGNETTES')
    print('=' * 74)
    print('  index : %d photos, %d fiches visages, %d fiches animaux'
          % (len(tags), len(faces), len(animaux)))
    print('-' * 74)
    total_n = total_o = orph_n = orph_o = 0
    orphelines = {}
    for dossier, quoi in DOSSIERS.items():
        n, poids, vieux, noms = inventorier(dossier)
        vs = vivants[dossier]
        # `morts` : [(nom, (octets, mtime))]. Le premier jet ecrivait
        # `sum(t[0] for t in morts)` en croyant reprendre le `t` de la
        # comprehension — c'etait le COUPLE, donc `t[0]` etait le nom, et la
        # somme d'entiers additionnait des chaines. Un banc tombe en une
        # seconde ; la meme confusion dans du code qui ecrit se serait vue
        # plus tard et ailleurs.
        morts = [(nom, taille) for nom, (taille, _mt) in noms.items()
                 if nom not in vs]
        mo = sum(taille for _nom, taille in morts)
        total_n += n
        total_o += poids
        orph_n += len(morts)
        orph_o += mo
        orphelines[dossier] = sorted(nom for nom, _t in morts)
        print('  %-14s %s' % (dossier, quoi))
        print('     fichiers   : %7d   %9.1f Mo' % (n, poids / 1048576))
        print('     noms vivants recalcules depuis l index : %d' % len(vs))
        if n:
            print('     ORPHELINS  : %7d   %9.1f Mo   soit %.0f %% du dossier'
                  % (len(morts), mo / 1048576, 100.0 * len(morts) / n))
            print('     plus ancien fichier : %.0f jours' % (vieux or 0))
        print('-' * 74)
    print('  TOTAL          %7d fichiers   %9.1f Mo' % (total_n, total_o / 1048576))
    print('  DONT ORPHELINS %7d fichiers   %9.1f Mo' % (orph_n, orph_o / 1048576))
    print('=' * 74)
    print('  Une vignette orpheline n est pas une perte : elle se REGENERE a')
    print('  la premiere demande, en lisant l original sur le NAS. Ce qu elle')
    print('  coute, c est de la place, et le temps de la retrouver.')
    if a.liste:
        Path(a.liste).write_text(
            json.dumps(orphelines, indent=1), encoding='utf-8')
        print('  liste ecrite : %s' % a.liste)
    print('  Rien n a ete efface : ce banc LIT.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
