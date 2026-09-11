#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les sondes du processus (sondes.py, 11/09) : ramasse-miettes et retard du GIL.

Un instrument qui se trompe designe le mauvais coupable ; un instrument qui
leve fait tomber ce qu'il observe. Ces bancs tiennent les deux : les chiffres
sont justes sur des horloges simulees, et rien ne leve, meme abime.
"""

import gc
import threading
import unittest
import ast
import textwrap
from pathlib import Path

import sondes

HERE = Path(__file__).resolve().parent


class _Horloge:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class LaSondeGC(unittest.TestCase):
    def test_une_collecte_simulee_est_rangee_par_GENERATION(self):
        h = _Horloge()
        s = sondes.SondeGC(horloge=h)
        s.rappel('start', {'generation': 2})
        h.t += 0.080
        s.rappel('stop', {'generation': 2, 'collected': 5})
        s.rappel('start', {'generation': 0})
        h.t += 0.001
        s.rappel('stop', {'generation': 0, 'collected': 0})
        e = s.etat()
        self.assertAlmostEqual(e['par_gen']['2']['ms'], 80.0, places=3)
        self.assertEqual(e['par_gen']['2']['n'], 1)
        self.assertEqual(e['par_gen']['2']['collectes'], 5)
        self.assertAlmostEqual(e['par_gen']['0']['ms'], 1.0, places=3)
        self.assertAlmostEqual(s.total_ms, 81.0, places=3)
        self.assertEqual(e['pire']['gen'], 2)

    def test_un_stop_SANS_start_ne_compte_rien(self):
        s = sondes.SondeGC(horloge=_Horloge())
        s.rappel('stop', {'generation': 1})
        self.assertEqual(s.total_ms, 0.0)
        self.assertEqual(s.etat()['par_gen']['1']['n'], 0)

    def test_un_rappel_ABIME_ne_leve_pas(self):
        s = sondes.SondeGC(horloge=_Horloge())
        s.rappel('start', None)
        s.rappel('stop', None)
        s.rappel('start', {'generation': 'x'})
        s.rappel('stop', {'generation': 'x', 'collected': 'beaucoup'})
        s.rappel('start', {'generation': 1})
        s.rappel('stop', {'generation': 1, 'collected': 'beaucoup'})
        s.rappel(None, 42)
        self.assertEqual(sorted(s.etat()['par_gen']), ['0', '1', '2'])

    def test_une_VRAIE_collecte_est_vue(self):
        s = sondes.SondeGC()
        self.assertTrue(s.brancher())
        self.assertTrue(s.brancher())
        try:
            self.assertEqual(gc.callbacks.count(s.rappel), 1, 'brancher est idempotent')
            gc.collect()
        finally:
            s.debrancher()
        self.assertNotIn(s.rappel, gc.callbacks)
        self.assertGreaterEqual(s.etat()['par_gen']['2']['n'], 1)
        self.assertGreater(s.total_ms, 0.0)


class _Temps:
    """Horloge et sommeil simules : `dormir` avance l'horloge de la duree
    demandee PLUS un retard impose."""
    def __init__(self, retards):
        self.t = 0.0
        self.mur_t = 1000.0
        self.retards = list(retards)

    def horloge(self):
        return self.t

    def mur(self):
        return self.mur_t

    def dormir(self, d):
        r = self.retards.pop(0)
        self.t += d + r
        self.mur_t += d + r


class LaSondeGIL(unittest.TestCase):
    def _sonde(self, retards, **kw):
        tp = _Temps(retards)
        s = sondes.SondeGIL(periode=0.02, horloge=tp.horloge, dormir=tp.dormir,
                            mur=tp.mur, **kw)
        return s, tp

    def test_le_retard_est_ce_qui_DEPASSE_la_periode(self):
        s, _ = self._sonde([0.0, 0.003, 0.060])
        self.assertAlmostEqual(s.tour(), 0.0, places=6)
        self.assertAlmostEqual(s.tour(), 3.0, places=6)
        self.assertAlmostEqual(s.tour(), 60.0, places=6)
        c = s.etat()['cumul']
        self.assertEqual(c['n'], 3)
        self.assertAlmostEqual(c['max_ms'], 60.0)
        #            <2  2-5 5-15 15-50 50-150 >150
        self.assertEqual(c['seaux'], [1, 1, 0, 0, 1, 0])

    def test_les_BORNES_des_seaux(self):
        s, _ = self._sonde([0.0019, 0.0021, 0.0051, 0.0151, 0.0501, 0.1501])
        for _ in range(6):
            s.tour()
        self.assertEqual(s.etat()['cumul']['seaux'], [1, 1, 1, 1, 1, 1])

    def test_la_FENETRE_se_remet_a_zero_et_garde_la_precedente(self):
        s, tp = self._sonde([0.0] * 5 + [0.030], fenetre_s=60.0)
        for _ in range(5):
            s.tour()
        tp.mur_t += 61.0
        s.tour()
        e = s.etat()
        self.assertEqual(e['cumul']['n'], 6)
        self.assertEqual(e['fenetre']['n'], 1)
        self.assertEqual(e['fenetre_precedente']['n'], 5)
        self.assertAlmostEqual(e['fenetre']['max_ms'], 30.0)

    def test_un_retard_NEGATIF_n_existe_pas(self):
        tp = _Temps([0.0])
        tp.dormir = lambda d: None          # l'horloge n'avance pas
        s = sondes.SondeGIL(periode=0.02, horloge=tp.horloge, dormir=tp.dormir, mur=tp.mur)
        self.assertEqual(s.tour(), 0.0)

    def test_la_boucle_qui_CASSE_le_dit_et_ne_leve_pas(self):
        def casse(_):
            raise OSError('plus de minuteur')
        s = sondes.SondeGIL(periode=0.02, dormir=casse)
        s.boucle()
        self.assertFalse(s.vivante)
        self.assertIn('minuteur', s.erreur)

    def test_la_boucle_s_arrete_quand_on_le_lui_dit(self):
        s, _ = self._sonde([0.0] * 3)
        n = iter([True, True, True, False])
        s.boucle(continuer=lambda: next(n))
        self.assertEqual(s.etat()['cumul']['n'], 3)
        self.assertFalse(s.vivante)

    def test_un_vrai_fil_mesure(self):
        s = sondes.SondeGIL(periode=0.002)
        arret = threading.Event()
        t = threading.Thread(target=s.boucle, args=(lambda: not arret.is_set(),))
        t.start()
        arret.wait(0.05)
        arret.set()
        t.join(1)
        self.assertGreater(s.etat()['cumul']['n'], 0)


class LeBranchementDansLeServeur(unittest.TestCase):
    """Par l'arbre syntaxique : ce que server.py fait des sondes."""
    SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')

    def test_branchees_au_demarrage_JUSTE_APRES_le_peage(self):
        s = self.SOURCE
        i = s.rindex("if __name__ == '__main__':")
        main = s[i:]
        self.assertLess(main.index('regler_peage_gil()'), main.index('SONDE_GC.brancher()'))
        self.assertLess(main.index('SONDE_GIL.demarrer()'), main.index('migrate_animal_pipeline()'))

    def test_un_module_ABSENT_n_empeche_pas_de_demarrer(self):
        s = self.SOURCE
        i = s.index('import sondes as _sondes')
        bloc = s[s.rindex('try:', 0, i):s.index('SONDE_GC = SONDE_GIL = None', i)]
        self.assertIn('except Exception', bloc)

    def test_le_chronometre_de_phases_ne_depend_pas_des_sondes(self):
        """`_Phases` et `_phases_note` sont exec'ues SANS sondes par
        test_horloge_phases.py : elles doivent les chercher, pas les supposer."""
        arbre = ast.parse(self.SOURCE)
        for n in ast.walk(arbre):
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in ('_Phases', '_phases_note'):
                noms = {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}
                self.assertNotIn('SONDE_GC', noms, n.name)


if __name__ == '__main__':
    unittest.main()
