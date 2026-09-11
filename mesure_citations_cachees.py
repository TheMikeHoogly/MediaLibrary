#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combien de décisions humaines une écriture À TRAVERS la vue pouvait effacer.

Le 11/09, un banc (`test_ecriture_sous_la_vue.py`) a montré que sous un
utilisateur connecté, confirmer, retirer ou nommer sur une fiche de personne
ou d'animal RÉÉCRIVAIT la fiche sans ses citations invisibles pour cet
utilisateur — visages, confirmations, exclusions, avatar pris dans le PRIVE
d'un autre. Ce banc dit l'EXPOSITION réelle, sur une copie de la base : pour
chaque compte, combien de fiches citent quelque chose qu'il ne voit pas, et
combien de citations cela fait.

Il ne dit PAS ce qui a été perdu : une citation effacée n'est plus dans la base.
Il dit ce qui l'aurait été au prochain geste — et, en comparant deux copies
datées, il peut montrer une baisse.

Il lit `copie.db` (jamais `photos.db`), n'écrit rien, n'affiche que des NOMS
de fiches et des nombres, jamais un chemin.

  python mesure_citations_cachees.py --base copie.db
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import visibilite as V


def _cachee(champ, c, ok):
    """Les memes tests que `visibilite.filtrer_fiche` (recopies : ce banc doit
    tourner aussi contre la version d'avant du module)."""
    if champ == 'faces':
        return isinstance(c, (list, tuple)) and bool(c) and not ok(c[0])
    return isinstance(c, str) and not ok(c)


def _lire(cx, table):
    out = {}
    try:
        for k, v in cx.execute(f'SELECT k, v FROM "{table}"'):
            try:
                out[k] = json.loads(v)
            except (ValueError, TypeError):
                continue
    except sqlite3.Error as e:
        print(f'  table {table} illisible : {e}')
    return out


def _sensibles(cx):
    s = set()
    try:
        for k, v in cx.execute('SELECT k, v FROM "tags"'):
            if '"sensible"' not in v:
                continue
            try:
                if V.en_attente(json.loads(v)):
                    s.add(k)
            except (ValueError, TypeError):
                continue
    except sqlite3.Error:
        pass
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--comptes', default='comptes.json')
    ap.add_argument('--detail', type=int, default=12)
    a = ap.parse_args(argv)
    if Path(a.base).name.lower() == 'photos.db':
        print('Refus : ce banc ne lit que la COPIE (mesure_copie_base.py).')
        return 2
    try:
        noms = list((json.loads(Path(a.comptes).read_text(encoding='utf-8'))
                     .get('comptes') or {}).keys())
    except (OSError, ValueError):
        noms = []
    noms = noms or [V.ADMIN]
    cx = sqlite3.connect(f'file:{Path(a.base).resolve().as_posix()}?mode=ro', uri=True)
    sensibles = _sensibles(cx)
    print(f'Base : {a.base} — comptes : {", ".join(noms)} — photos en attente (sensible) : {len(sensibles)}')
    # TEMOIN D'ETENDUE : un zero partout ne vaut que si l'instrument VOIT des
    # cles cachees. Combien de photos de l'index sont invisibles a chacun ?
    cles = [k for (k,) in cx.execute('SELECT k FROM "tags"')]
    prives = [k for k in cles if V.est_prive(k)]
    print(f'Temoin : {len(cles)} cles d index, dont {len(prives)} dans un PRIVE')
    for u in noms:
        ok = V.filtre(u, lambda k: k in sensibles)
        print(f'  invisibles pour {u} : {sum(1 for k in cles if not ok(k))}')
    print()
    for table in ('people', 'pets'):
        fiches = _lire(cx, table)
        print(f'== {table} : {len(fiches)} fiches ==')
        for u in noms:
            ok = V.filtre(u, lambda k: k in sensibles)
            touchees = []
            total = {'faces': 0, 'exclude': 0, 'confirmed': 0, 'avatar': 0}
            for pk, f in fiches.items():
                if not isinstance(f, dict):
                    continue
                n = {c: len([x for x in (f.get(c) or []) if _cachee(c, x, ok)])
                     for c in ('faces', 'exclude', 'confirmed')}
                av = f.get('avatar')
                n['avatar'] = int(isinstance(av, (list, tuple)) and bool(av) and not ok(av[0]))
                if any(n.values()):
                    touchees.append((sum(n.values()), f.get('name', pk), n))
                    for c in total:
                        total[c] += n[c]
            touchees.sort(reverse=True)
            print(f'  vu par {u} : {len(touchees)} fiche(s) citent l invisible — '
                  f'visages {total["faces"]}, confirmations {total["confirmed"]}, '
                  f'exclusions {total["exclude"]}, avatars {total["avatar"]}')
            for s, nom, n in touchees[:a.detail]:
                print(f'      {nom[:30]:30} {s:6d}  (visages {n["faces"]}, conf {n["confirmed"]}, '
                      f'excl {n["exclude"]}, avatar {n["avatar"]})')
        print()
    print('Ce banc n ecrit rien. A lire avec la date de la copie (mesure_copie_base.py).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
