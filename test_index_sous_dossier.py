#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`_index_entries_under` : la meme reponse, sans consulter la vue 44 605 fois.

La phase `index` de `GET /files` pesait 112 a 136 ms. Sous-phases posees le
12/09 pour savoir OU : le BALAYAGE des cles en portait 101 a 118, le compte
des mots-cles 11 a 18. Et le cout n'etait pas `_pkey` -- memoise depuis le
11/09 -- mais la VUE par utilisateur, ~3 us par cle (PERFORMANCE.md § 3.11) :
44 605 x 3 us = 134 ms, ce que l'horloge lisait.

La correction balaye l'index BRUT et ne demande a la vue que les cles
retenues. Elle reste l'autorite : `VueFiltree.get` applique le MEME predicat
que `items()`. Ces bancs le prouvent avec la VRAIE `VueFiltree` de
`visibilite.py` comme oracle -- l'ancienne ecriture, mot pour mot, contre la
neuve, sur des cas ou elles pourraient diverger.

Un banc de performance qui ne verifierait que le temps laisserait passer une
fuite : ici ce qui se mesure, c'est le NOMBRE d'appels au predicat ET
l'identite des reponses.
"""

import ast
import io
import types
import unittest
from functools import lru_cache
from pathlib import Path, PurePath

import visibilite

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
LIGNES = SOURCE.splitlines()


def source_de(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return '\n'.join(LIGNES[n.lineno - 1:n.end_lineno])
    raise AssertionError(nom + ' introuvable dans server.py')


def ancienne_ecriture(folder, pkey, store_data, upload_dir):
    """L'ecriture d'avant le 12/09, mot pour mot : elle est l'ORACLE."""
    fp = pkey(folder)
    up = pkey(upload_dir)
    out = []
    if fp == up or fp == pkey(Path(upload_dir).resolve()):
        for k, e in list(store_data.items()):
            if '/' not in pkey(k):
                out.append((k, e))
        return out
    pref = fp + '/'
    for k, e in list(store_data.items()):
        if pkey(k).startswith(pref):
            out.append((k, e))
    return out


class Socle(unittest.TestCase):

    def bati(self, brut, cache=(), upload='/uploads'):
        """Un module avec un index BRUT et une VUE qui cache `cache`."""
        self.appels = {'n': 0}
        caches = set(cache)

        def visible(k):
            self.appels['n'] += 1
            return k not in caches

        vue = visibilite.VueFiltree(brut, visible)
        m = types.ModuleType('idx')
        m.__dict__.update({
            'Path': Path, 'PurePath': PurePath, 'lru_cache': lru_cache,
            'PKEY_MEMO_MAX': 1 << 17, 'INDEX_BRUT': brut,
            'UPLOAD_DIR': Path(upload),
            'STORE': types.SimpleNamespace(data=vue),
        })
        for nom in ('_pkey_chaine', '_pkey', '_index_entries_under'):
            exec(source_de(nom), m.__dict__)                        # noqa: S102
        self.vue = vue
        self.brut = brut
        return m

    def oracle(self, m, folder):
        return ancienne_ecriture(folder, m._pkey, self.vue, m.UPLOAD_DIR)


class LaMemeReponseQueLAncienneEcriture(Socle):

    def cas(self):
        return {
            '/nas/Photos/2022/a.jpg': {'kw_fr': ['a']},
            '/nas/Photos/2022/sous/b.jpg': {'kw_fr': ['b']},
            '/nas/Photos/2023/c.jpg': {'kw_fr': ['c']},
            '/nas/Photos/2022bis/d.jpg': {'kw_fr': ['d']},
            'e.jpg': {'kw_fr': ['e']},
            'Camera/f.jpg': {'kw_fr': ['f']},
        }

    def test_un_dossier_du_NAS(self):
        m = self.bati(self.cas())
        d = Path('/nas/Photos/2022')
        self.assertEqual(m._index_entries_under(d), self.oracle(m, d))
        self.assertEqual([k for k, _e in m._index_entries_under(d)],
                         ['/nas/Photos/2022/a.jpg',
                          '/nas/Photos/2022/sous/b.jpg'])

    def test_un_dossier_dont_le_nom_PREFIXE_un_autre(self):
        """`2022` ne doit pas attraper `2022bis` : c'est le `/` du prefixe."""
        m = self.bati(self.cas())
        d = Path('/nas/Photos/2022')
        self.assertNotIn('/nas/Photos/2022bis/d.jpg',
                         [k for k, _e in m._index_entries_under(d)])

    def test_la_racine_Uploads_ne_prend_que_les_cles_SIMPLES(self):
        m = self.bati(self.cas())
        d = Path('/uploads')
        self.assertEqual(m._index_entries_under(d), self.oracle(m, d))
        self.assertEqual([k for k, _e in m._index_entries_under(d)], ['e.jpg'])

    def test_un_dossier_vide(self):
        m = self.bati(self.cas())
        d = Path('/nas/Photos/1999')
        self.assertEqual(m._index_entries_under(d), [])
        self.assertEqual(m._index_entries_under(d), self.oracle(m, d))


class LaVueRESTELAutorite(Socle):

    def test_une_entree_CACHEE_n_entre_pas(self):
        brut = {'/nas/Photos/2022/a.jpg': {'kw_fr': ['a']},
                '/nas/Photos/2022/secret.jpg': {'kw_fr': ['s']}}
        m = self.bati(brut, cache=['/nas/Photos/2022/secret.jpg'])
        d = Path('/nas/Photos/2022')
        cles = [k for k, _e in m._index_entries_under(d)]
        self.assertEqual(cles, ['/nas/Photos/2022/a.jpg'])
        self.assertEqual(m._index_entries_under(d), self.oracle(m, d))

    def test_une_entree_cachee_HORS_du_dossier_ne_change_rien(self):
        brut = {'/nas/Photos/2022/a.jpg': {}, '/nas/Photos/2023/x.jpg': {}}
        m = self.bati(brut, cache=['/nas/Photos/2023/x.jpg'])
        d = Path('/nas/Photos/2022')
        self.assertEqual(m._index_entries_under(d), self.oracle(m, d))

    def test_les_ENTREES_rendues_sont_les_memes_objets(self):
        e = {'kw_fr': ['a']}
        m = self.bati({'/nas/Photos/2022/a.jpg': e})
        d = Path('/nas/Photos/2022')
        self.assertIs(m._index_entries_under(d)[0][1], e)


class CeQueLeChangementEconomise(Socle):
    """Une optimisation qui ne se compte pas est une intention."""

    def test_le_predicat_n_est_plus_appele_pour_TOUT_le_fonds(self):
        brut = {}
        for i in range(1000):
            brut['/nas/Photos/2023/%04d.jpg' % i] = {}
        for i in range(20):
            brut['/nas/Photos/2022/%04d.jpg' % i] = {}
        m = self.bati(brut)
        d = Path('/nas/Photos/2022')

        self.appels['n'] = 0
        m._index_entries_under(d)
        neuf = self.appels['n']

        self.appels['n'] = 0
        ancienne_ecriture(d, m._pkey, self.vue, m.UPLOAD_DIR)
        vieux = self.appels['n']

        self.assertGreaterEqual(vieux, 1020,
                                "l'ancienne ecriture consultait la vue pour "
                                "chaque cle de l'index")
        self.assertLessEqual(neuf, 40,
                             'la vue ne doit etre consultee que sur les cles '
                             'retenues : %d appels' % neuf)


if __name__ == '__main__':
    unittest.main(verbosity=2)
