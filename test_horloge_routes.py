#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L'horloge des routes : ce qu'elle compte, et ce qu'elle ne doit jamais casser.

Un instrument de mesure pose sur le chemin le plus chaud du serveur a deux
devoirs, et le second passe avant le premier :

  1. compter juste ;
  2. **ne jamais faire tomber une requete** — une horloge qui casse ce qu'elle
     mesure est pire que pas d'horloge.

Les bancs lisent `server.py` par l'arbre syntaxique et executent les quatre
fonctions de l'horloge seules : importer le module ouvrirait photos.db, monterait
cinq magasins et lancerait des fils.
"""

import ast
import json
import sys
import threading
import time
import types
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable dans server.py')


def _src(nom):
    return ast.get_source_segment(SOURCE, _noeud(nom)) or ''


def _horloge(tmp):
    m = types.ModuleType('perf')
    import os as _os
    m.__dict__.update({
        'threading': threading, 'time': time, 'json': json, 'os': _os,
        'urllib': urllib, 'Path': Path,
        'PERF_LOCK': threading.Lock(), 'PERF_ROUTES': {},
        'PERF_DEPUIS': time.time(), 'PERF_MAX_ROUTES': 300,
        'PERF_SEUILS': (30, 100, 300, 1000, 3000),
        'SCRIPT_DIR': Path(tmp), 'PERF_FICHIER': Path(tmp) / '_perf_routes.json',
    })
    for nom in ('_route_perf', '_perf_note', 'perf_tableau', 'perf_ecrire'):
        exec(_src(nom), m.__dict__)                                # noqa: S102
    return m


class LaCleDeClassement(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.m = _horloge(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_l_argument_ne_fait_PAS_une_ligne_de_tableau(self):
        """Sans repliage, `/api/thumb?key=...` ferait 44 604 lignes et aucune
        n'aurait de sens : ce qu'on veut savoir, c'est ce que coute « servir
        une vignette »."""
        a = self.m._route_perf('GET', '/api/thumb?key=x.jpg&s=512')
        b = self.m._route_perf('GET', '/api/thumb?key=y.jpg&s=1600')
        self.assertEqual(a, b)
        self.assertEqual(a, 'GET /api/thumb')

    def test_les_chemins_de_FICHIER_se_replient_sur_leur_prefixe(self):
        a = self.m._route_perf('GET', '/media/Photos%20Mike/2023/a.jpg')
        b = self.m._route_perf('GET', '/media/Photos%20Flo/2015/b.jpg')
        self.assertEqual(a, b)
        self.assertTrue(a.endswith('*'))

    def test_deux_METHODES_ne_se_melangent_pas(self):
        self.assertNotEqual(self.m._route_perf('GET', '/api/x'),
                            self.m._route_perf('POST', '/api/x'))

    def test_un_chemin_vide_ne_casse_rien(self):
        self.assertEqual(self.m._route_perf('GET', ''), 'GET /')
        self.assertEqual(self.m._route_perf('GET', None), 'GET /')


class CeQueLHorlogeCompte(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.m = _horloge(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _ligne(self, cle):
        return {r['cle']: r for r in self.m.perf_tableau()['routes']}[cle]

    def test_appels_total_et_maximum(self):
        for ms in (10, 20, 300):
            self.m._perf_note('GET', '/api/x', ms)
        r = self._ligne('GET /api/x')
        self.assertEqual(r['n'], 3)
        self.assertAlmostEqual(r['ms'], 330)
        self.assertAlmostEqual(r['max'], 300)

    def test_les_seaux_repondent_a_UNE_question_exactement(self):
        """« Combien de requetes ont depasse 300 ms » — un histogramme ne se
        trompe pas sur ce qu'il mesure, un centile approche si."""
        for ms in (1, 29, 30, 99, 100, 299, 300, 999, 1000, 2999, 3000, 9999):
            self.m._perf_note('GET', '/api/x', ms)
        seaux = self._ligne('GET /api/x')['seaux']
        self.assertEqual(seaux, [2, 2, 2, 2, 2, 2])
        self.assertEqual(sum(seaux[3:]), 6)      # >= 300 ms

    def test_le_classement_se_fait_sur_le_TOTAL_pas_le_maximum(self):
        """Une route lente appelee trois fois coute moins qu'une route tiede
        appelee mille fois."""
        for _ in range(1000):
            self.m._perf_note('GET', '/tiede', 5)      # 5 s au total
        for _ in range(3):
            self.m._perf_note('GET', '/lente', 900)    # 2,7 s, mais pique
        cles = [r['cle'] for r in self.m.perf_tableau()['routes']]
        self.assertEqual(cles[0], 'GET /tiede')

    def test_le_nombre_de_lignes_est_BORNE(self):
        """Un chemin arbitraire ne doit pas pouvoir faire grossir la table sans
        fin : c'est de la memoire, et c'est ouvert sur le reseau."""
        for i in range(self.m.PERF_MAX_ROUTES + 50):
            self.m._perf_note('GET', '/inconnu/%d' % i, 1)
        self.assertLessEqual(len(self.m.PERF_ROUTES),
                             self.m.PERF_MAX_ROUTES + 1)
        self.assertIn('GET (autres)', self.m.PERF_ROUTES)


class ElleNeCassePasCeQuElleMesure(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.m = _horloge(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_une_horloge_qui_echoue_ne_leve_JAMAIS(self):
        """Le devoir qui passe avant compter juste."""
        class Mechant:
            def __str__(self):
                raise RuntimeError('boum')
        self.m._perf_note('GET', Mechant(), 10)       # ne doit pas lever
        self.m._perf_note('GET', '/api/x', None)      # ni sur un temps absurde

    def test_le_depot_est_ATOMIQUE(self):
        """Un banc qui lit pendant l'ecriture ne doit pas tomber sur un demi
        fichier : `.tmp` puis `os.replace`."""
        self.assertIn('os.replace', _src('perf_ecrire'))
        self.assertIn(".with_suffix('.tmp')", _src('perf_ecrire'))

    def test_rien_a_dire_ne_depose_rien(self):
        """Un fichier de zero route ferait croire a une mesure faite."""
        self.assertFalse(self.m.perf_ecrire())
        self.m._perf_note('GET', '/api/x', 1)
        self.assertTrue(self.m.perf_ecrire())
        t = json.loads(self.m.PERF_FICHIER.read_text(encoding='utf-8'))
        self.assertEqual(t['routes'][0]['cle'], 'GET /api/x')

    def test_elle_compte_sous_plusieurs_FILS(self):
        """`ThreadingHTTPServer` : huit requetes peuvent noter en meme temps."""
        def bruit():
            for _ in range(200):
                self.m._perf_note('GET', '/api/x', 1)
        fils = [threading.Thread(target=bruit) for _ in range(8)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(self.m.PERF_ROUTES['GET /api/x']['n'], 1600)


class ElleEstPOSEE_LA_OU_IL_FAUT(unittest.TestCase):
    def test_dans_l_enveloppe_pas_dans_le_routeur(self):
        """Mesurer ne doit pas etre l'occasion de rouvrir 250 lignes de
        dispatch : `do_GET` etait deja une fine enveloppe autour de `_do_get`,
        et c'est la que l'horloge se pose."""
        for methode in ('do_GET', 'do_POST'):
            s = _src(methode)
            self.assertIn('perf_counter()', s, methode)
            self.assertIn('_perf_note(', s, methode)
        # le routeur lui-meme n'a pas ete touche
        self.assertNotIn('_perf_note(', _src('_do_get'))

    def test_elle_note_meme_quand_la_requete_ECHOUE(self):
        """Dans le `finally` : une requete refusee par la porte, ou qui leve,
        a quand meme coute du temps — et c'est souvent celle-la qui pique."""
        for methode in ('do_GET', 'do_POST'):
            n = _noeud(methode)
            essais = [x for x in ast.walk(n) if isinstance(x, ast.Try)]
            self.assertTrue(essais, methode)
            corps_finally = ''.join(
                ast.get_source_segment(SOURCE, st) or ''
                for e in essais for st in e.finalbody)
            self.assertIn('_perf_note(', corps_finally, methode)

    def test_le_tableau_se_depose_a_chaque_cycle_de_maintenance(self):
        self.assertIn('perf_ecrire()', _src('maintenance_loop'))

    def test_et_se_lit_aussi_par_l_API(self):
        self.assertIn("'/api/perf'", SOURCE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
