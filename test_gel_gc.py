#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Geler les objets permanents — et ne rien casser en le faisant (12/09).

La sonde du 11/09 a chiffré ce que le ramasse-miettes coûte à ce serveur :
une collecte complète toutes les ~40 s, **230 à 568 ms**, tous fils arrêtés,
parce qu'elle parcourt les millions d'objets des index chargés au démarrage.
`geler_les_permanents()` les sort de son champ (`gc.freeze`).

Ce banc tient les trois promesses de ce geste :
  1. il gèle vraiment, et il est idempotent ;
  2. **ce qui naît APRÈS reste ramassé** — c'est la seule chose qui pourrait
     transformer l'optimisation en fuite ;
  3. il ne lève JAMAIS, même si l'interpréteur refuse (`gc` sans `freeze`),
     et il est appelé au bon endroit : après les sondes, avant le premier fil.
"""

import ast
import gc
import sys
import textwrap
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
_LIGNES = SOURCE.splitlines(keepends=True)
_ARBRE = ast.parse(SOURCE)


def _src(nom):
    for n in _ARBRE.body:
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return textwrap.dedent(''.join(_LIGNES[n.lineno - 1:n.end_lineno]))
    raise AssertionError(nom + ' introuvable')


def _constante(nom):
    for n in _ARBRE.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == nom:
            return ''.join(_LIGNES[n.lineno - 1:n.end_lineno])
    raise AssertionError(nom + ' introuvable')


def _charger(gc_module=None):
    ns = {}
    exec(_constante('GC_SEUIL_GEN2'), ns)                           # noqa: S102
    if gc_module is not None:
        ancien = sys.modules.get('gc')
        sys.modules['gc'] = gc_module
        try:
            exec(_src('geler_les_permanents'), ns)                 # noqa: S102
            fn = ns['geler_les_permanents']
            return fn()
        finally:
            if ancien is None:
                sys.modules.pop('gc', None)
            else:
                sys.modules['gc'] = ancien
    exec(_src('geler_les_permanents'), ns)                          # noqa: S102
    return ns['geler_les_permanents']


class LeGel(unittest.TestCase):
    def setUp(self):
        self._seuils = gc.get_threshold()
        gc.unfreeze()

    def tearDown(self):
        gc.unfreeze()
        gc.set_threshold(*self._seuils)

    def test_il_gele_et_se_repete_sans_dommage(self):
        geler = _charger()
        avant = gc.get_freeze_count()
        n, seuil = geler()
        self.assertIsInstance(n, int)
        self.assertGreater(n, avant)
        self.assertEqual(gc.get_freeze_count(), n)
        self.assertEqual(geler()[0], gc.get_freeze_count())

    def test_il_ESPACE_les_collectes_completes(self):
        """Le gel les rend 3,6x moins chères et 3,7x plus fréquentes (mesuré) :
        sans ce seuil, le temps total passé à ramasser ne bouge pas."""
        geler = _charger()
        a0, b0, _c0 = gc.get_threshold()
        _n, seuil = geler()
        a, b, c = gc.get_threshold()
        self.assertEqual((a, b), (a0, b0), 'les deux premiers seuils ne bougent pas')
        self.assertEqual(c, seuil)
        self.assertGreaterEqual(c, 100)

    def test_ce_qui_NAIT_APRES_est_toujours_ramasse(self):
        """La promesse qui compte : un cycle créé après le gel se ramasse."""
        geler = _charger()
        geler()

        class Boucle:
            pass
        a, b = Boucle(), Boucle()
        a.autre, b.autre = b, a          # un cycle, que seul le GC peut défaire
        del a, b
        self.assertGreaterEqual(gc.collect(), 2)

    def test_un_interpreteur_qui_REFUSE_ne_fait_pas_tomber_le_serveur(self):
        faux = types.ModuleType('gc')
        faux.collect = lambda: 0

        def freeze():
            raise NotImplementedError('pas de gel ici')
        faux.freeze = freeze
        faux.get_freeze_count = lambda: 0
        self.assertEqual(_charger(faux), (None, None))

    def test_un_gc_SANS_freeze_du_tout(self):
        faux = types.ModuleType('gc')
        faux.collect = lambda: 0
        self.assertEqual(_charger(faux), (None, None))

    def test_un_gc_qui_refuse_le_SEUIL_gele_quand_meme(self):
        vrai = gc
        faux = types.ModuleType('gc')
        faux.collect = vrai.collect
        faux.freeze = vrai.freeze
        faux.get_freeze_count = vrai.get_freeze_count
        faux.get_threshold = vrai.get_threshold

        def refuse(*a):
            raise ValueError('non')
        faux.set_threshold = refuse
        geles, seuil = _charger(faux)
        self.assertIsInstance(geles, int)
        self.assertIsNone(seuil)


class OuIlEstAPPELE(unittest.TestCase):
    def test_apres_les_sondes_et_avant_le_premier_fil(self):
        main = SOURCE[SOURCE.rindex("if __name__ == '__main__':"):]
        self.assertLess(main.index('SONDE_GC.brancher()'),
                        main.index('geler_les_permanents()'))
        self.assertLess(main.index('geler_les_permanents()'),
                        main.index('migrate_animal_pipeline()'))
        # Les magasins sont chargés à l'IMPORT : le gel les attrape donc tous.
        self.assertLess(SOURCE.index('STORE = make_store(INDEX_FILE)'),
                        SOURCE.rindex("if __name__ == '__main__':"))

    def test_le_serveur_DIT_ce_qu_il_a_gele(self):
        main = SOURCE[SOURCE.rindex("if __name__ == '__main__':"):]
        i = main.index('geler_les_permanents()')
        self.assertIn('objets permanents gelés', main[i:i + 400])
        self.assertIn('espacées', main[i:i + 400])
        self.assertIn('gel indisponible', main[i:i + 400])


if __name__ == '__main__':
    unittest.main()
