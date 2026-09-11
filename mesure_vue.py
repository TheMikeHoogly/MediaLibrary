#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ce que coûte la VUE par utilisateur, sur les vraies clés de la photothèque.

Le 11/09, l'horloge de phases a montré que trois `len()` dans
`/api/maint/status` coûtent 50 à 100 ms de CPU : dès qu'un compte est
connecté, `STORE.data` rend une vue qui appelle le prédicat de visibilité
CLÉ PAR CLÉ. Le prédicat a été réécrit (même règle, autre ordre) et
`VueFiltree` itère par `filter` natif ; le banc sandbox disait ×1,4 à ×1,6,
mais sur la machine de Mike les phases varient plus que le gain.

Ce banc tranche : les DEUX écritures, sur les MÊMES clés réelles (lues dans
`copie.db`, jamais `photos.db`), conditions ALTERNÉES, on garde le meilleur
de chaque — un tour lent pris par le NAS ou la campagne ne décide de rien.

L'ancienne écriture est recopiée ici verbatim (commit 2d40c26) : un banc qui
importerait deux fois le module mesurerait deux fois le même code.

  python mesure_vue.py --base copie.db --tours 5
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import visibilite as V


# ── ANCIENNE ÉCRITURE (2d40c26), recopiée sans rien changer ──────────────
def ancien_sensible_de(entree):
    if not isinstance(entree, dict):
        return ''
    v = entree.get('sensible')
    return v if isinstance(v, str) else ''


def ancien_en_attente(entree):
    return ancien_sensible_de(entree) == V.SENSIBLE_EN_ATTENTE


def ancien_filtre(utilisateur, sensible=None):
    if utilisateur is None:
        return None
    if sensible is None:
        return lambda cle: V.visible(cle, utilisateur)
    return lambda cle: V.visible(cle, utilisateur, sensible(cle))


class AncienneVue:
    def __init__(self, d, ok):
        self._d = d
        self._ok = ok

    def __iter__(self):
        return (k for k in list(self._d) if self._ok(k))

    def __len__(self):
        return sum(1 for _ in self)

    def values(self):
        return [self._d[k] for k in self]

    def items(self):
        return [(k, self._d[k]) for k in self]


def _index(base):
    cx = sqlite3.connect(f'file:{Path(base).resolve().as_posix()}?mode=ro', uri=True)
    d = {}
    for k, v in cx.execute('SELECT k, v FROM "tags"'):
        # Seul l'axe `sensible` compte ici : garder les entrées entières
        # ferait mesurer l'allocation de 44 600 dicts, pas la vue. Le test se
        # fait sur le NOM du champ puis par `json.loads` : chercher
        # `"sensible": "en_attente"` dans le texte dependrait des separateurs
        # de `json.dumps` — premiere version, et elle a compte ZERO la ou il y
        # en a 7 (un compteur qui rend zero doit etre prouve).
        e = {}
        if '"sensible"' in v:
            try:
                if V.en_attente(json.loads(v)):
                    e = {'sensible': V.SENSIBLE_EN_ATTENTE}
            except (ValueError, TypeError):
                e = {}
        d[k] = e
    cx.close()
    return d


def _mesure(fn, tours):
    meilleur = None
    for _ in range(tours):
        t0 = time.perf_counter()
        n = fn()
        dt = (time.perf_counter() - t0) * 1000.0
        meilleur = dt if meilleur is None else min(meilleur, dt)
    return meilleur, n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--tours', type=int, default=5)
    ap.add_argument('--utilisateur', default=V.ADMIN)
    a = ap.parse_args(argv)
    if Path(a.base).name.lower() == 'photos.db':
        print('Refus : ce banc ne lit que la COPIE (mesure_copie_base.py).')
        return 2
    d = _index(a.base)
    caches = sum(1 for e in d.values() if e.get('sensible'))
    print(f'{len(d)} cles reelles ({a.base}), dont {caches} en attente de verdict, '
          f'{sum(1 for k in d if V.est_prive(k))} dans un PRIVE')
    print(f'Utilisateur : {a.utilisateur} — meilleur de {a.tours} tours, conditions alternees')
    print()

    sens_v = lambda k: ancien_en_attente(d.get(k))                 # noqa: E731
    sens_n = lambda k: V.en_attente(d.get(k))                      # noqa: E731
    vieille = AncienneVue(d, ancien_filtre(a.utilisateur, sens_v))
    neuve = V.VueFiltree(d, V.filtre(a.utilisateur, sens_n))

    gestes = [
        ('len(vue)', lambda v: len(v)),
        ('list(vue)', lambda v: len(list(v))),
        ('vue.values()', lambda v: len(v.values())),
        ('vue.items()', lambda v: len(v.items())),
    ]
    print(f'  {"geste":14} {"avant ms":>9} {"apres ms":>9} {"gain":>6}   compte')
    for nom, geste in gestes:
        # ALTERNEES : avant, apres, avant, apres… un tour lent pris par la
        # campagne tombe des deux cotes.
        ms_v = ms_n = None
        for _ in range(a.tours):
            t0 = time.perf_counter()
            nv = geste(vieille)
            ms_v = min(ms_v or 1e9, (time.perf_counter() - t0) * 1000.0)
            t0 = time.perf_counter()
            nn = geste(neuve)
            ms_n = min(ms_n or 1e9, (time.perf_counter() - t0) * 1000.0)
        marque = 'IDENTIQUE' if nv == nn else f'ECART {nv} vs {nn}'
        print(f'  {nom:14} {ms_v:9.1f} {ms_n:9.1f} {ms_v / ms_n:5.2f}x   {nn} ({marque})')
    print()
    # Et le prix d'UNE clé, la vraie unite de ce cout.
    cles = list(d)
    for nom, ok in (('avant', ancien_filtre(a.utilisateur, sens_v)),
                    ('apres', V.filtre(a.utilisateur, sens_n))):
        ms, _ = _mesure(lambda ok=ok: sum(1 for k in cles if ok(k)), a.tours)
        print(f'  predicat seul, {nom} : {ms:7.1f} ms  soit {ms * 1000 / len(cles):.2f} us par cle')
    print()
    print('A LIRE AVEC SA DATE : la campagne et le serveur tournent pendant ce banc.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
