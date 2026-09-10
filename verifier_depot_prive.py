#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
« Rendre privee » peut-il aboutir, photo par photo ? -- la mesure du 10/09.

Ce banc ne DEPLACE rien. Il refait, sur les vraies cles de l'index et avec le
vrai module de regles, les trois questions que le serveur se pose avant de
toucher au disque :

  1. `refus_rendre_privee(cle, utilisateur)`   -- le geste est-il permis ?
  2. `cible_prive(rel)`                        -- ou irait la photo ?
  3. `refus_ecriture(<destination>, u, depot=True)` -- le DEPOT est-il permis
     sur le dossier PRIVE a creer, puis sur le fichier a y poser ?

Il existe parce que le 10/09 la reponse etait « Fichier introuvable » sur une
photo dont la vignette etait a l'ecran, et que la cause vivait deux etages
sous le message. Un refus qui ne se mesure pas se relit mal.

  python verifier_depot_prive.py
  python verifier_depot_prive.py --utilisateur Flo
"""

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--utilisateur', default='Mike')
    ap.add_argument('--cle', default='')
    a = ap.parse_args(argv)

    import visibilite as vis
    u = a.utilisateur

    cles = [a.cle] if a.cle else []
    if not cles:
        from store_sqlite import open_store
        if not (RACINE / 'photos.db').exists():
            print('  photos.db absente.')
            return 2
        st = open_store(RACINE / 'tags_index.json', RACINE, None)
        cles = [c for c, e in list(st.data.items()) if vis.en_attente(e)]

    print('=' * 74)
    print('  « RENDRE PRIVEE » -- ce que le serveur repondrait a %s' % u)
    print('  ADMIN = %r' % vis.ADMIN)
    print('=' * 74)
    aboutit = bloque = 0
    for cle in cles:
        prop = vis.proprietaire_de(cle)
        verdict = vis.refus_rendre_privee(cle, u)
        print('-' * 74)
        print('  %s' % Path(cle).name)
        print('    proprietaire : %r     deja privee : %s'
              % (prop, vis.est_prive(cle)))
        if verdict:
            bloque += 1
            print('    => REFUS %d : %s' % verdict)
            continue
        dossier, raison = vis.cible_prive(cle)
        print('    destination  : %s' % dossier)
        # Les DEUX chemins que `_rendre_privee` fait controler : le dossier
        # PRIVE (mkdir) puis le fichier qui s'y pose (move).
        chemins = [dossier, dossier + '/' + Path(cle).name]
        ok = True
        for c in chemins:
            r = vis.refus_ecriture(c, u, depot=True)
            print('    depot sur %-58s : %s'
                  % (c[-58:], 'PERMIS' if r is None else 'REFUS %d %s' % r))
            ok = ok and r is None
        # Et le controle NEGATIF : sans le depot, le meme chemin doit rester
        # ferme -- sinon l'exception serait devenue un passe-partout.
        sans = vis.refus_ecriture(chemins[1], u)
        print('    sans depot (doit rester ferme hors de chez soi) : %s'
              % ('PERMIS' if sans is None else 'REFUS %d' % sans[0]))
        aboutit += 1 if ok else 0
        bloque += 0 if ok else 1
        print('    => %s' % ('ABOUTIT' if ok else 'BLOQUE plus bas'))
    print('=' * 74)
    print('  %d aboutissent, %d bloquees, sur %d en attente de verdict.'
          % (aboutit, bloque, len(cles)))
    print('  Rien n a bouge : ce banc LIT.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
