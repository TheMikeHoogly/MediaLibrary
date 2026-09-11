#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les trois comptes de /reglages en UNE passe (11/09).

`/api/maint/status` balayait l'index trois fois par appel : `tagged_count`,
`_tagging_pipe_counts`, la boucle de `_retag_etat`. `_passe_index` les fait en
une. Ce banc prend les trois ecritures d'avant, RECOPIEES VERBATIM, pour
oracle, sur 400 index tires au hasard — entrees ratees, videos, sans pipe,
abandons de campagne, valeurs vides — avec et sans campagne.

Et il compte : la passe neuve lit l'index UNE fois, les anciennes trois.
"""

import ast
import random
import threading
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
_LIGNES = SOURCE.splitlines(keepends=True)
_NOEUDS = {n.name: n for n in ast.walk(ast.parse(SOURCE))
           if isinstance(n, ast.FunctionDef)
           and n.name in ('_passe_index', '_retag_etat', '_serve_maint_status')}


def _src(nom):
    n = _NOEUDS[nom]
    return textwrap.dedent(''.join(_LIGNES[n.lineno - 1:n.end_lineno]))


# ── ORACLE : les trois ecritures au commit 26db8dc, sans rien changer. ──
ORACLE = r'''
def tagged_count(self):
    return sum(1 for e in self.data.values()
               if not e.get('failed') and (e.get('kw_fr') or e.get('kw_en')))


def _tagging_pipe_counts():
    c = {}
    for e in list(STORE.data.values()):
        if isinstance(e, dict) and not e.get('failed'):
            v = e.get('pipe') or 'v0'
            c[v] = c.get(v, 0) + 1
    return c


def _retag_etat():
    cible = retag_cible()
    if not cible:
        if _RETAG_REFUS_DIT['quoi']:
            return {'actif': False, 'refus': _RETAG_REFUS_DIT['quoi'],
                    'attendu': TAGGING_PIPELINE_VERSION}
        return {'actif': False}
    reste = abandons = 0
    for e in list(STORE.data.values()):
        if not isinstance(e, dict) or e.get('failed') or e.get('video'):
            continue
        if e.get('retag_fail') == cible:
            abandons += 1
        elif e.get('pipe') != cible:
            reste += 1
    with PENDING_LOCK:
        en_file = len(RETAG_PENDING)
    return {'actif': True, 'cible': cible, 'reste': reste, 'en_file': en_file,
            'abandons': abandons, 'lot': RETAG_LOT}
'''


class _Vue(dict):
    """`values()` qui se compte : combien de fois l'index est-il PARCOURU ?"""
    lectures = 0

    def values(self):
        type(self).lectures += 1
        return super().values()


class _Store:
    def __init__(self, data):
        self.data = data


def _entree(r):
    e = {}
    if r.random() < 0.08:
        e['failed'] = r.choice([True, 1, 'oui'])
    if r.random() < 0.05:
        e['failed'] = r.choice([False, 0, '', None])
    if r.random() < 0.6:
        e['kw_fr'] = r.choice([['chat'], [], None])
    if r.random() < 0.4:
        e['kw_en'] = r.choice([['cat'], [], None])
    if r.random() < 0.85:
        e['pipe'] = r.choice(['v3', 'v2', '', None, 'v1'])
    if r.random() < 0.1:
        e['video'] = r.choice([True, False])
    if r.random() < 0.1:
        e['retag_fail'] = r.choice(['v3', 'v2'])
    return e


def _monde(data, cible, refus=None):
    return {
        'STORE': _Store(data), 'retag_cible': lambda: cible,
        '_RETAG_REFUS_DIT': {'quoi': refus}, 'TAGGING_PIPELINE_VERSION': 'v3',
        'PENDING_LOCK': threading.Lock(), 'RETAG_PENDING': {'a', 'b'},
        'RETAG_LOT': 50,
    }


class LaPasseEgaleLesTroisEcritures(unittest.TestCase):
    def _une(self, data, cible, refus=None):
        o = _monde(data, cible, refus)
        exec(ORACLE, o)                                            # noqa: S102
        n = _monde(data, cible, refus)
        exec(_src('_passe_index'), n)                              # noqa: S102
        exec(_src('_retag_etat'), n)                               # noqa: S102

        attendu = (o['tagged_count'](o['STORE']), o['_tagging_pipe_counts'](),
                   o['_retag_etat']())
        passe = n['_passe_index'](n['retag_cible']())
        obtenu = (passe['tagues'], passe['pipes'], n['_retag_etat'](passe))
        self.assertEqual(attendu[0], obtenu[0])
        self.assertEqual(attendu[1], obtenu[1])
        self.assertEqual(list(attendu[1]), list(obtenu[1]),
                         "l'ordre des versions est celui de l'iteration")
        self.assertEqual(attendu[2], obtenu[2])
        # Et sans passe fournie, `_retag_etat` rend encore la meme chose.
        self.assertEqual(attendu[2], n['_retag_etat']())

    def test_400_index_tires_au_hasard(self):
        r = random.Random(20260911)
        for i in range(400):
            data = {f'k{j}': _entree(r) for j in range(r.randint(0, 60))}
            cible = r.choice(['v3', 'v2', None])
            refus = r.choice([None, None, 'v9'])
            with self.subTest(tirage=i):
                self._une(data, cible, refus)

    def test_index_VIDE(self):
        self._une({}, 'v3')
        self._une({}, None)

    def test_une_passe_faite_pour_une_AUTRE_cible_ne_sert_pas(self):
        """Le levier peut changer entre la passe et `_retag_etat` : alors on
        recompte, on ne rend pas les chiffres d'une autre campagne."""
        data = {'a': {'pipe': 'v2'}, 'b': {'pipe': 'v3'}, 'c': {'retag_fail': 'v3'}}
        n = _monde(data, 'v3')
        exec(_src('_passe_index'), n)                              # noqa: S102
        exec(_src('_retag_etat'), n)                               # noqa: S102
        faite_pour_v2 = n['_passe_index']('v2')
        r = n['_retag_etat'](faite_pour_v2)
        self.assertEqual((r['reste'], r['abandons']), (1, 1))


class LeNombreDeParcours(unittest.TestCase):
    def test_UNE_lecture_de_l_index_contre_TROIS(self):
        data = _Vue({f'k{j}': {'kw_fr': ['x'], 'pipe': 'v2'} for j in range(50)})
        o = _monde(data, 'v3')
        exec(ORACLE, o)                                            # noqa: S102
        _Vue.lectures = 0
        o['tagged_count'](o['STORE'])
        o['_tagging_pipe_counts']()
        o['_retag_etat']()
        self.assertEqual(_Vue.lectures, 3)

        n = _monde(data, 'v3')
        exec(_src('_passe_index'), n)                              # noqa: S102
        exec(_src('_retag_etat'), n)                               # noqa: S102
        _Vue.lectures = 0
        passe = n['_passe_index'](n['retag_cible']())
        n['_retag_etat'](passe)
        self.assertEqual(_Vue.lectures, 1)


    def test_la_ROUTE_se_sert_de_la_passe(self):
        """Une route qui appellerait encore les anciens comptes rendrait le
        meme corps — seul ce banc verrait les deux parcours revenus."""
        appels = {}
        for n in ast.walk(_NOEUDS['_serve_maint_status']):
            if isinstance(n, ast.Call):
                f = n.func
                nom = f.attr if isinstance(f, ast.Attribute) else getattr(f, 'id', '')
                appels.setdefault(nom, []).append(n)
        self.assertEqual(len(appels.get('_passe_index', [])), 1)
        self.assertNotIn('tagged_count', appels)
        self.assertNotIn('_tagging_pipe_counts', appels)
        retag = appels.get('_retag_etat', [])
        self.assertEqual(len(retag), 1)
        self.assertEqual([ast.unparse(a) for a in retag[0].args], ['passe'])


if __name__ == '__main__':
    unittest.main()
