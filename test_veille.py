#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1 -- la VEILLE (16/09). Sur le code de prod, sans importer server.py.

Ce qui doit tenir :
1. `/api/veille` ne rend RIEN sans compte, et ne tire que dans la VUE
   (`STORE.data`), jamais une video ni un fichier en echec ; `n` est borne.
2. Une vignette demandee par la veille (`veille=1`) ne suspend pas le
   travail de fond ; toute autre, si.
3. `/api/random` ne cite plus une photo que le compte n'a pas le droit de
   voir (la marche part du DISQUE, que la vue ne couvre pas).
4. Cote client : la veille ne s'arme qu'avec un compte, avale le geste qui
   la reveille, et ne part pas quand quelqu'un regarde deja quelque chose.
"""
import ast
import json
import os
import random
import re
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / 'server.py'
ARBRE = ast.parse(SERVER.read_text(encoding='utf-8'))
GLOBAL_JS = (HERE / 'ui' / 'global.js').read_text(encoding='utf-8')
CSS = (HERE / 'ui' / 'components.css').read_text(encoding='utf-8')


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable')


def _sans_docstring(fn):
    corps = list(fn.body)
    if corps and isinstance(corps[0], ast.Expr) and isinstance(
            getattr(corps[0], 'value', None), ast.Constant):
        corps = corps[1:]
    return corps


def _appels(noeuds, nom):
    out = []
    for racine in noeuds:
        for n in ast.walk(racine):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == nom:
                out.append(n)
    return out


class Faux:
    def __init__(self, chemin):
        self.path = chemin
        self.envoye = None

    def _send(self, code, corps, typ):
        self.envoye = (code, json.loads(corps))


def veille(data, qui='mike', n='120'):
    ns = {'urllib': urllib, 'json': json, 'os': os, 'random': random,
          'IMAGE_EXT': {'.jpg', '.png'}, 'VEILLE_TIRAGE_MAX': 400,
          'utilisateur_vu': lambda: qui,
          '_best_time': lambda k, e: e.get('t', 0),
          'STORE': type('S', (), {'data': data})()}
    exec(compile(ast.Module([_noeud('_serve_veille')], []), str(SERVER), 'exec'), ns)
    f = Faux('/api/veille?n=' + n)
    ns['_serve_veille'](f)
    return f.envoye


class LaRoute(unittest.TestCase):
    def test_sans_compte_rien(self):
        code, d = veille({'a.jpg': {}}, qui=None)
        self.assertEqual((code, d['items']), (200, []))

    def test_ne_tire_que_des_images_valides_de_la_vue(self):
        data = {'a.jpg': {'t': 5}, 'b.mp4': {}, 'c.jpg': {'failed': True},
                'd.png': {'video': True}, 'e.txt': {}, 'f.JPG': {}}
        _c, d = veille(data)
        self.assertEqual(sorted(i['k'] for i in d['items']), ['a.jpg', 'f.JPG'])
        self.assertEqual(d['total'], 2)
        self.assertEqual([i['t'] for i in d['items'] if i['k'] == 'a.jpg'], [5])

    def test_n_est_borne_et_sans_remise(self):
        data = {'p%d.jpg' % i: {} for i in range(1000)}
        _c, d = veille(data, n='999999')
        ks = [i['k'] for i in d['items']]
        self.assertEqual(len(ks), 400)
        self.assertEqual(len(set(ks)), 400)
        _c, d = veille(data, n='abc')
        self.assertEqual(len(d['items']), 120)

    def test_la_route_est_branchee(self):
        src = ast.unparse(_noeud('_do_get'))
        self.assertIn("path == '/api/veille'", src)
        self.assertIn('self._serve_veille()', src)


class LeTravailDeFondNeCedePasALaVeille(unittest.TestCase):
    def test_note_heavy_activity_est_sous_la_garde_veille(self):
        fn = _noeud('_serve_thumb')
        corps = _sans_docstring(fn)
        appels = _appels(corps, 'note_heavy_activity')
        self.assertEqual(len(appels), 1)
        gardes = [n for n in ast.walk(ast.Module(corps, []))
                  if isinstance(n, ast.If) and 'veille' in ast.unparse(n.test)
                  and any(c is appels[0] for b in n.body for c in ast.walk(b))]
        self.assertEqual(len(gardes), 1, 'le seul note_heavy_activity doit etre sous la garde')


class LeHasardRespecteLaVue(unittest.TestCase):
    def test_random_juge_le_candidat_avant_de_le_citer(self):
        fn = _noeud('_serve_random')
        corps = _sans_docstring(fn)
        self.assertEqual(len(_appels(corps, 'chemin_visible')), 1)
        src = ast.unparse(ast.Module(corps, []))
        self.assertLess(src.index('chemin_visible(cand)'),
                        src.index('_index_key_for_path(cand)'))


class LeClient(unittest.TestCase):
    def test_armee_seulement_avec_un_compte(self):
        i = GLOBAL_JS.index('if (!d || !d.nom) return;')
        self.assertGreater(GLOBAL_JS.index('Veille.armer()'), i)
        self.assertEqual(GLOBAL_JS.count('Veille.armer()'), 1)

    def test_la_vignette_porte_veille_1_et_la_taille_1600(self):
        self.assertIn("'/api/thumb?s=1600&veille=1&key='", GLOBAL_JS)

    def test_le_geste_de_reveil_est_avale(self):
        bloc = GLOBAL_JS[GLOBAL_JS.index('function geste(ev)'):]
        bloc = bloc[:bloc.index('function armer()')]
        self.assertIn('ev.preventDefault(); ev.stopPropagation();', bloc)
        self.assertIn("capture: true", GLOBAL_JS)
        self.assertIn("addEventListener('click', clic, true)", GLOBAL_JS)

    def test_ne_part_pas_quand_on_regarde_deja(self):
        bloc = GLOBAL_JS[GLOBAL_JS.index('function occupee()'):]
        bloc = bloc[:bloc.index('function rearmer()')]
        for garde in ('document.hidden', 'fullscreenElement', '#ss.open', 'paused'):
            self.assertIn(garde, bloc)

    def test_elle_s_eteint_et_ne_demande_plus_rien(self):
        self.assertRegex(GLOBAL_JS, r'var DUREE = 30 \* 60 \* 1000;')
        bloc = GLOBAL_JS[GLOBAL_JS.index('function eteindre()'):]
        bloc = bloc[:bloc.index('function lancer(')]
        self.assertIn('clearTimeout(pas)', bloc)
        self.assertIn("removeAttribute('src')", bloc)

    def test_jamais_sur_la_page_de_connexion(self):
        self.assertIn('connexion/.test(location.pathname)', GLOBAL_JS)

    def test_le_style_vit_dans_components_et_laisse_gagner_hidden(self):
        regle = re.search(r'\n\.veille \{([^}]*)\}', CSS).group(1)
        self.assertNotIn('display', regle)
        self.assertIn('var(--salle)', regle)


if __name__ == '__main__':
    unittest.main()
