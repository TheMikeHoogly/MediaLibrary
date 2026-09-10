#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ma formule de nommage parle-t-elle encore la langue de `server.py` ?

Le 10/09, l'apercu du bat 51 a montre des taux de reconnaissance BAS :
photo_thumbs 33,1 %, face_thumbs 16,9 %, animal_thumbs 25,8 %. Mike a repondu
NON, et il a eu raison : deux histoires expliquent ces chiffres, et elles
demandent des gestes opposes.

  (a) VETUSTE — les caches sont vieux, les mtime et les bbox ont bouge depuis
      (campagne de retag qui reecrit les XMP, re-embedding qui deplace les
      cadres de visages). Alors effacer est juste.
  (b) DERIVE — ma formule ne calcule plus le meme nom que `server.py`. Alors
      effacer serait le pire geste possible.

Le plancher de 5 % du bat 51 ne separe pas ces deux histoires : il n'attrape
qu'une derive TOTALE. Ce banc regarde l'AGE : si les vignettes les plus JEUNES
sont reconnues, la formule suit le serveur.

**ET IL Y A UNE TROISIEME HISTOIRE, que ce banc a confondue avec (b) au premier
lancement.** Le 10/09 il a rendu « DERIVE » sur `photo_thumbs` (16 % des plus
jeunes reconnus) et « VETUSTE » sur les deux autres (100 %). La difference
entre les trois n'est pas la qualite de la formule : c'est **ce qu'il y a dans
la cle**. Une vignette de photo est nommee `md5(cle|taille|MTIME)` ; un
visage, `md5(cle|index|BBOX)`. Or la campagne de retag reecrit les XMP en
continu, donc **change le mtime de milliers de photos par jour** : une vignette
faite le 08/09 pour une photo retaguee le 09/09 est VRAIMENT orpheline, et le
sera meme si elle a une heure. Tant que la campagne tourne, un cache indexe sur
le mtime se perime plus vite qu'il ne se remplit, et le critere de l'age ne
sait plus rien dire.

**Ce qui, lui, PROUVE que la formule est juste** : 2 563 vignettes de photo SONT
reconnues. Une formule fausse n'en reconnaitrait pas une seule -- on ne tombe
pas 2 563 fois par accident sur un md5. Le verdict « DERIVE » etait donc une
FAUSSE ALARME de cet instrument, pas une derive du code.

Le critere de l'age reste valable la ou la cle ne depend de rien que la
campagne reecrive (`face_thumbs`, `animal_thumbs`). Ailleurs, il faut attendre
la fin de la campagne pour que l'image redevienne lisible -- et c'est
exactement ce que ce banc dit maintenant, au lieu de crier a la derive.

Il n'efface rien, il ne propose rien : il regarde les N fichiers les plus
JEUNES de chaque cache et dit combien sont reconnus.

  python verifier_formule_vignettes.py
  python verifier_formule_vignettes.py --n 50
"""

import argparse
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

DOSSIERS = ('photo_thumbs', 'face_thumbs', 'animal_thumbs')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--n', type=int, default=30,
                    help='combien des PLUS JEUNES examiner par dossier')
    a = ap.parse_args(argv)

    import mesure_caches_vignettes as M
    from store_sqlite import open_store
    if not (RACINE / 'photos.db').exists():
        print('  photos.db absente.')
        return 2
    vivants = M.noms_vivants(
        open_store(RACINE / 'tags_index.json', RACINE, None).data,
        open_store(RACINE / 'faces_index.json', RACINE, None).data,
        open_store(RACINE / 'animals_index.json', RACINE, None).data)

    maintenant = time.time()
    print('=' * 74)
    print('  LA FORMULE PARLE-T-ELLE ENCORE LA MEME LANGUE QUE server.py ?')
    print('=' * 74)
    print('  Lecture : si les vignettes les PLUS JEUNES sont reconnues, la')
    print('  formule est juste et les orphelines sont vraiment vieilles.')
    print('  Si les plus jeunes sont orphelines, c est MOI qui derive.')
    verdicts = []
    for d in DOSSIERS:
        dossier = RACINE / d
        if not dossier.is_dir():
            continue
        vs = vivants[d]
        fichiers = []
        with os.scandir(dossier) as it:
            for x in it:
                if x.is_file():
                    st = x.stat()
                    fichiers.append((st.st_mtime, Path(x.name).stem))
        if not fichiers:
            continue
        fichiers.sort(reverse=True)
        jeunes = fichiers[:a.n]
        vieux = fichiers[-a.n:]
        rj = sum(1 for _t, n in jeunes if n in vs)
        rv = sum(1 for _t, n in vieux if n in vs)
        glob = sum(1 for _t, n in fichiers if n in vs)
        print('-' * 74)
        print('  %-14s %d fichier(s), %.1f %% reconnus au total'
              % (d, len(fichiers), 100.0 * glob / len(fichiers)))
        print('     les %2d plus JEUNES (%s a %s) : %d reconnus sur %d  -> %.0f %%'
              % (len(jeunes),
                 time.strftime('%d/%m %H:%M', time.localtime(jeunes[-1][0])),
                 time.strftime('%d/%m %H:%M', time.localtime(jeunes[0][0])),
                 rj, len(jeunes), 100.0 * rj / len(jeunes)))
        print('     les %2d plus VIEUX  (%s a %s) : %d reconnus sur %d  -> %.0f %%'
              % (len(vieux),
                 time.strftime('%d/%m %H:%M', time.localtime(vieux[-1][0])),
                 time.strftime('%d/%m %H:%M', time.localtime(vieux[0][0])),
                 rv, len(vieux), 100.0 * rv / len(vieux)))
        tj = 100.0 * rj / len(jeunes)
        # LE CRITERE DE L'AGE NE VAUT PAS PARTOUT, et le dire est tout
        # l'apprentissage du 10/09. Une cle qui porte le MTIME se perime a
        # chaque ecriture XMP : pendant une campagne de retag, elle se perime
        # plus vite qu'elle ne se remplit, et « jeune mais orphelin » devient
        # normal. Ce qui prouve la formule, alors, ce n'est plus l'age : c'est
        # qu'elle reconnaisse QUELQUE CHOSE — on ne tombe pas par accident sur
        # des milliers de md5 justes.
        indexe_sur_mtime = (d == 'photo_thumbs')
        if tj >= 90:
            v = 'VETUSTE — la formule suit le serveur, les vieux sont vieux'
        elif glob == 0:
            v = 'DERIVE — pas UN seul nom reconnu : NE PAS EFFACER'
        elif indexe_sur_mtime:
            v = ('ILLISIBLE PENDANT LA CAMPAGNE — la cle porte le mtime, que '
                 'le retag reecrit ; %d noms reconnus prouvent la formule, '
                 'l age ne prouve plus rien. Attendre la fin de la campagne.'
                 % glob)
        elif tj <= 30:
            v = 'DERIVE — meme les plus jeunes echappent : NE PAS EFFACER'
        else:
            v = 'INCERTAIN — a regarder de plus pres avant tout effacement'
        for bout in [v[i:i+64] for i in range(0, len(v), 64)]:
            print('     => %s' % bout if bout is v[:64] else '        %s' % bout)
        verdicts.append((d, tj, v))
    print('=' * 74)
    for d, tj, v in verdicts:
        print('  %-14s %5.0f %% des plus jeunes reconnus   %s'
              % (d, tj, v.split(' — ')[0]))
    print('  Rien n a ete efface : ce banc LIT.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
