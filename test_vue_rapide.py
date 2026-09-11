#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La vue par utilisateur, plus vite, et EXACTEMENT la même (11/09).

`visibilite.filtre` appelait `visible` pour chaque clé ; il teste maintenant
`est_prive` d'abord (10 clés sur 44 604 sont dans un PRIVE) et ne consulte
`visible` que pour elles. `en_attente` ne passe plus par `sensible_de`, et
`VueFiltree` itère par `filter` natif. Rien de tout ça ne doit changer UNE
réponse : la règle 17b (le privé ne se trahit pas, y compris par un compteur)
ne tolère pas un « presque ».

L'ORACLE : les écritures d'avant, recopiées verbatim ci-dessous, contre les
neuves, sur 6 000 clés tirées au hasard — PRIVE à toutes les profondeurs et
dans toutes les casses, les deux séparateurs, des dossiers propriétaires,
la racine, des entrées sensibles, des entrées qui ne sont pas des dicts — et
pour chaque utilisateur, fil de fond compris.
"""

import random
import unittest

import visibilite as V
from auteurs import ADMIN


# ── ORACLE : visibilite.py au commit 2d40c26, sans rien changer. ──
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

    def keys(self):
        return list(self)

    def values(self):
        return [self._d[k] for k in self]

    def items(self):
        return [(k, self._d[k]) for k in self]


PROPRIOS = ['Mike', 'Flo', 'Papa', 'Florine', 'mike']
UTILISATEURS = [None, ADMIN, 'Flo', 'Papa', 'Florine', 'Inconnu']


def _cle(r):
    sep = r.choice(['/', '\\'])
    segs = r.choice([['N:', 'Photos'], ['', '', 'NAS-Bremblens', 'home', 'Photos'], []])
    segs = list(segs)
    if r.random() < 0.8:
        segs.append(r.choice(['Photos ', 'photos ', 'PHOTOS  ']) + r.choice(PROPRIOS))
    elif r.random() < 0.5:
        segs.append(r.choice(['_A TRIER', '_Uploads', '2019']))
    for _ in range(r.randint(0, 3)):
        if r.random() < 0.08:
            segs.append(r.choice(['PRIVE', 'prive', ' Prive ', 'PRIVEE', 'xPRIVE', 'PRIVE ']))
        else:
            segs.append(r.choice(['2020', 'Vacances', 'Mathilde et Ellie', 'Privé']))
    segs.append('IMG_%05d.jpg' % r.randint(0, 99999))
    return sep.join(segs)


def _entree(r):
    x = r.random()
    if x < 0.05:
        return r.choice([None, 'bruit', 42, []])
    e = {'kw_fr': ['chat']}
    if x < 0.25:
        e['sensible'] = r.choice(['en_attente', 'non', '', None, 1, ['en_attente']])
    return e


class LaMemeReponse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = random.Random(20260911)
        cls.d = {}
        while len(cls.d) < 6000:
            cls.d[_cle(r)] = _entree(r)
        cls.prives = sum(1 for k in cls.d if V.est_prive(k))

    def test_le_tirage_couvre_les_cas_rares(self):
        """Un oracle qui ne tire aucune clé PRIVE ne prouverait rien."""
        self.assertGreater(self.prives, 100)
        self.assertGreater(sum(1 for e in self.d.values() if ancien_en_attente(e)), 50)

    def test_en_attente(self):
        for e in list(self.d.values()) + [{'sensible': 'en_attente'}, {}, None, 'x',
                                          {'sensible': b'en_attente'}]:
            self.assertEqual(V.en_attente(e), ancien_en_attente(e), repr(e))

    def test_le_predicat_cle_par_cle_pour_chaque_utilisateur(self):
        sens = lambda k: ancien_en_attente(self.d.get(k))           # noqa: E731
        for u in UTILISATEURS:
            for avec in (True, False):
                vieux = ancien_filtre(u, sens if avec else None)
                neuf = V.filtre(u, sens if avec else None)
                if u is None:
                    self.assertIsNone(vieux)
                    self.assertIsNone(neuf)
                    continue
                with self.subTest(utilisateur=u, sensible=avec):
                    ecarts = [k for k in self.d if vieux(k) != neuf(k)]
                    self.assertEqual(ecarts, [])

    def test_la_vue_ENTIERE_len_keys_values_items_iter(self):
        sens = lambda k: ancien_en_attente(self.d.get(k))           # noqa: E731
        for u in UTILISATEURS[1:]:
            a = AncienneVue(self.d, ancien_filtre(u, sens))
            n = V.VueFiltree(self.d, V.filtre(u, sens))
            with self.subTest(utilisateur=u):
                self.assertEqual(len(n), len(a))
                self.assertEqual(n.keys(), a.keys())
                self.assertEqual(list(n), list(a))
                self.assertEqual(n.values(), a.values())
                self.assertEqual(n.items(), a.items())
                self.assertLess(len(n), len(self.d) + 1)

    def test_l_iteration_prend_un_INSTANTANE_des_cles(self):
        """Comme avant : ajouter une clé pendant qu'on parcourt ne lève pas."""
        d = {'N:/Photos/Photos Mike/a.jpg': {}, 'N:/Photos/Photos Mike/b.jpg': {}}
        v = V.VueFiltree(d, V.filtre('Flo'))
        vus = []
        for k in v:
            d['N:/Photos/Photos Mike/c%d.jpg' % len(vus)] = {}
            vus.append(k)
        self.assertEqual(len(vus), 2)


if __name__ == '__main__':
    unittest.main()
