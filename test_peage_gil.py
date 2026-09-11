#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le réglage du péage du GIL : ce qu'il pose, ce qu'il ne doit jamais faire.

Mesuré le 11/09 (`mesure_peage_gil.py`) : sous Windows, un `stat` local passe
de 0,04 ms à 6–37 ms dès qu'un fil de calcul Python tourne, parce que la
reprise du GIL attend le pas du minuteur (15,6 ms). Minuteur à 1 ms + bascule
à 1 ms : 1,4–4,1 ms, sans perte de débit CPU. **Bascule à 0,5 ms : le débit
des fils de calcul tombe à 16 %.**

Ce que ces bancs gardent :
  1. **le plancher d'1 ms** — dans la constante ET dans le code qui l'applique ;
  2. **jamais d'exception au démarrage** : ni Windows absent, ni `winmm`
     introuvable, ni un `setswitchinterval` qui refuse ;
  3. **posé avant le premier fil** de `__main__` ;
  4. **visible** dans `/api/serveur`.
"""

import ast
import sys
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
_LIGNES = SOURCE.splitlines(keepends=True)


def _src(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ''.join(_LIGNES[n.lineno - 1:n.end_lineno])
    raise AssertionError(nom)


def _constante(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == nom for t in n.targets):
            return ast.literal_eval(n.value)
    raise AssertionError(nom)


def _monde(os_name='posix', sys_mod=None, ctypes_mod=None, bascule=None):
    faux_os = types.SimpleNamespace(name=os_name)
    g = {'os': faux_os, 'sys': sys_mod or sys,
         'GIL_BASCULE_S': _constante('GIL_BASCULE_S') if bascule is None else bascule,
         'MINUTEUR_WINDOWS_MS': _constante('MINUTEUR_WINDOWS_MS'),
         'GIL_REGLAGE': {"bascule_ms": None, "minuteur_ms": None, "erreur": None}}
    if ctypes_mod is not None:
        g['__builtins__'] = dict(__builtins__ if isinstance(__builtins__, dict)
                                 else vars(__builtins__))
        vrai_import = g['__builtins__']['__import__']

        def faux_import(nom, *a, **k):
            if nom == 'ctypes':
                if isinstance(ctypes_mod, Exception):
                    raise ctypes_mod
                return ctypes_mod
            return vrai_import(nom, *a, **k)
        g['__builtins__']['__import__'] = faux_import
    exec(_src('regler_peage_gil'), g)                                  # noqa: S102
    return g


class LePlancher(unittest.TestCase):
    def test_la_constante_ne_descend_pas_sous_1_ms(self):
        self.assertGreaterEqual(_constante('GIL_BASCULE_S'), 0.001)

    def test_le_code_l_applique_meme_si_la_constante_ment(self):
        avant = sys.getswitchinterval()
        try:
            g = _monde(bascule=0.0001)
            r = g['regler_peage_gil']()
            self.assertAlmostEqual(sys.getswitchinterval(), 0.001, places=6)
            self.assertAlmostEqual(r['bascule_ms'], 1.0, places=3)
        finally:
            sys.setswitchinterval(avant)


class JamaisDExceptionAuDemarrage(unittest.TestCase):
    def setUp(self):
        self.avant = sys.getswitchinterval()

    def tearDown(self):
        sys.setswitchinterval(self.avant)

    def test_hors_windows_le_minuteur_n_est_pas_touche(self):
        r = _monde('posix')['regler_peage_gil']()
        self.assertIsNone(r['minuteur_ms'])
        self.assertIsNone(r['erreur'])

    def test_windows_sans_ctypes(self):
        r = _monde('nt', ctypes_mod=ImportError('pas de ctypes'))['regler_peage_gil']()
        self.assertIsNone(r['minuteur_ms'])
        self.assertIn('minuteur', r['erreur'])

    def test_windows_winmm_introuvable(self):
        def WinDLL(nom):
            raise OSError('winmm introuvable')
        r = _monde('nt', ctypes_mod=types.SimpleNamespace(WinDLL=WinDLL))['regler_peage_gil']()
        self.assertIsNone(r['minuteur_ms'])
        self.assertIn('winmm', r['erreur'])

    def test_windows_accepte(self):
        appels = []
        winmm = types.SimpleNamespace(timeBeginPeriod=lambda ms: appels.append(ms) or 0)
        r = _monde('nt', ctypes_mod=types.SimpleNamespace(WinDLL=lambda n: winmm))['regler_peage_gil']()
        self.assertEqual(appels, [1])
        self.assertEqual(r['minuteur_ms'], 1)

    def test_windows_refuse_la_resolution(self):
        winmm = types.SimpleNamespace(timeBeginPeriod=lambda ms: 97)   # TIMERR_NOCANDO
        r = _monde('nt', ctypes_mod=types.SimpleNamespace(WinDLL=lambda n: winmm))['regler_peage_gil']()
        self.assertIsNone(r['minuteur_ms'])

    def test_un_sys_qui_refuse(self):
        faux_sys = types.SimpleNamespace(
            setswitchinterval=lambda v: (_ for _ in ()).throw(ValueError('non')),
            getswitchinterval=lambda: 0.005)
        r = _monde('posix', sys_mod=faux_sys)['regler_peage_gil']()
        self.assertIn('bascule', r['erreur'])


class IlEstPoseAuBonEndroit(unittest.TestCase):
    def test_avant_le_premier_fil_de_main(self):
        mains = [n for n in ARBRE.body if isinstance(n, ast.If)
                 and ast.unparse(n.test) == "__name__ == '__main__'"]
        dernier = mains[-1]
        src = ast.unparse(dernier)
        self.assertIn('regler_peage_gil()', src)
        self.assertLess(src.index('regler_peage_gil()'), src.index('fil_surveille('))

    def test_visible_dans_api_serveur(self):
        for n in ast.walk(ARBRE):
            if isinstance(n, ast.FunctionDef) and n.name == '_serve_serveur_etat':
                self.assertIn("'gil': dict(GIL_REGLAGE)", ast.unparse(n).replace('"', "'"))
                return
        self.fail('_serve_serveur_etat introuvable')


if __name__ == '__main__':
    unittest.main(verbosity=2)
