#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests -- les lieux d'un CHEMIN se calculent une fois par cle (04/10).

`/api/sujets/list` payait ~1,5 s sur 2,2 s a recalculer, pour 44 000 cles et
a CHAQUE appel, une regle qui ne depend que de la cle, de l'index des lieux et
des racines. `_lieux_des_cles` la memorise. Ce qui doit tenir :

1. **Le meme resultat** que la regle appelee directement, cle par cle.
2. **Payee une fois** : un deuxieme appel ne rappelle pas la regle.
3. **Invalidee par le CONTENU** de l'index ou des racines, pas par l'identite
   du dict (`lieux_connus` le rebatit toutes les 5 min sans que rien change).
4. **Pas d'oubli par un compte partiel** : un appel sur un sous-ensemble ne
   fait pas recalculer le reste a l'appel complet suivant.

Lit `server.py` sans l'importer (`import server` ouvre `photos.db`).
SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""
import ast
import sys
import types
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
ARBRE = ast.parse(SERVER.read_text(encoding="utf-8"))


def _charger():
    noeuds = []
    for n in ARBRE.body:
        if isinstance(n, ast.FunctionDef) and n.name == '_lieux_des_cles':
            noeuds.append(n)
        if isinstance(n, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id == '_LIEUX_MEMO'
                for c in n.targets):
            noeuds.append(n)
    assert len(noeuds) == 2, "_lieux_des_cles / _LIEUX_MEMO introuvables"
    appels = []

    def regle(k, index, roots, tous=False, avec_fichier=False):
        appels.append(k)
        assert tous and avec_fichier, "la regle doit etre appelee comme avant"
        return [index[m] for m in sorted(index) if m in k.lower()]

    faux = types.ModuleType('faits_vue')
    faux.lieux_du_chemin = regle
    espace = {'__builtins__': __builtins__}
    mod = ast.Module(body=noeuds, type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(SERVER), 'exec'), espace)
    return espace, appels, faux, regle


class LesLieuxMemorises(unittest.TestCase):
    def setUp(self):
        self.espace, self.appels, faux, self.regle = _charger()
        self._ancien = sys.modules.get('faits_vue')
        sys.modules['faits_vue'] = faux
        self.f = self.espace['_lieux_des_cles']
        self.index = {'sion': 'Sion', 'bali': 'Bali', 'paris': 'Paris'}
        self.roots = [('Photos', r'\\NAS\Photos')]
        self.cles = [r'\\NAS\Photos\%s\img%d.jpg' % (d, i)
                     for i, d in enumerate(['Sion', 'Bali', 'Divers',
                                            'Paris Sion', 'x'] * 20)]

    def tearDown(self):
        if self._ancien is None:
            sys.modules.pop('faits_vue', None)
        else:
            sys.modules['faits_vue'] = self._ancien

    def test_meme_resultat_que_la_regle(self):
        out = self.f(self.cles, self.index, self.roots)
        for k in self.cles:
            self.assertEqual(out[k], tuple(self.regle(
                k, self.index, self.roots, tous=True, avec_fichier=True)))

    def test_payee_une_seule_fois(self):
        self.f(self.cles, self.index, self.roots)
        n = len(self.appels)
        self.assertEqual(n, len(self.cles))
        self.f(self.cles, self.index, self.roots)
        self.assertEqual(len(self.appels), n, "la regle a ete rappelee")

    def test_un_index_EGAL_mais_neuf_n_invalide_pas(self):
        self.f(self.cles, self.index, self.roots)
        n = len(self.appels)
        self.f(self.cles, dict(self.index), list(self.roots))
        self.assertEqual(len(self.appels), n)

    def test_un_index_CHANGE_invalide(self):
        self.f(self.cles, self.index, self.roots)
        n = len(self.appels)
        autre = dict(self.index, divers='Divers')
        out = self.f(self.cles, autre, self.roots)
        self.assertEqual(len(self.appels), 2 * n)
        self.assertIn('Divers', out[self.cles[2]])

    def test_des_racines_changees_invalident(self):
        self.f(self.cles, self.index, self.roots)
        n = len(self.appels)
        self.f(self.cles, self.index, self.roots + [('U', r'C:\Up')])
        self.assertEqual(len(self.appels), 2 * n)

    def test_un_appel_partiel_ne_fait_pas_oublier_le_reste(self):
        self.f(self.cles, self.index, self.roots)
        n = len(self.appels)
        self.f(self.cles[:10], self.index, self.roots)
        self.f(self.cles, self.index, self.roots)
        self.assertEqual(len(self.appels), n)

    def test_un_PETIT_compte_ne_vide_pas_la_memoire_du_grand(self):
        """Le cas reel : l'admin voit 44 000 cles, Flo quelques milliers.
        Le garde de taille ne doit pas prendre le petit appel pour un signe
        que la memoire a trop grossi."""
        grand = [r'\\NAS\Photos\Sion\g%d.jpg' % i for i in range(3000)]
        self.f(grand, self.index, self.roots)
        n = len(self.appels)
        for _ in range(3):
            self.f(grand[:10], self.index, self.roots)
            self.f(grand, self.index, self.roots)
        self.assertEqual(len(self.appels), n, "la memoire s'est videe")

    def test_le_resultat_ne_rend_que_les_cles_demandees(self):
        self.f(self.cles, self.index, self.roots)
        out = self.f(self.cles[:3], self.index, self.roots)
        self.assertEqual(set(out), set(self.cles[:3]))


class LeComptageEnUnePasse(unittest.TestCase):
    """`_compter_sujets` remplace deux boucles recopiees ici VERBATIM (celles
    de `people_list` et `pets_list` avant le 04/10) : elles servent d'oracle
    sur des index tires au hasard, casse et espaces compris."""

    @staticmethod
    def _ancien_personnes(valeurs):
        tagcount = {}
        for e in valeurs:
            if not isinstance(e, dict):
                continue
            for kw in (e.get('kw_fr') or []):
                if str(kw).lower().startswith('personne:'):
                    key = str(kw)[9:].strip().lower()
                    tagcount[key] = tagcount.get(key, 0) + 1
        return tagcount

    @staticmethod
    def _ancien_animaux(valeurs):
        tagcount = {}
        for e in valeurs:
            if not isinstance(e, dict):
                continue
            for kw in (e.get('kw_fr') or []):
                if str(kw).lower().startswith('animal:'):
                    key = str(kw)[7:].strip().lower()
                    tagcount[key] = tagcount.get(key, 0) + 1
        return tagcount

    def test_meme_comptage_que_les_deux_boucles_d_avant(self):
        import random
        n = [x for x in ARBRE.body if isinstance(x, ast.FunctionDef)
             and x.name == '_compter_sujets']
        self.assertEqual(len(n), 1)
        esp = {'__builtins__': __builtins__}
        m = ast.Module(body=n, type_ignores=[])
        ast.fix_missing_locations(m)
        exec(compile(m, str(SERVER), 'exec'), esp)
        f = esp['_compter_sujets']
        alea = random.Random(4)
        mots = ['personne:Mike', 'Personne:mike ', 'personne: Flo', 'animal:Inti',
                'ANIMAL:inti', 'animal:', 'plage', 'personne:', 7, None,
                'animalerie', 'personnel']
        for _ in range(300):
            idx = {}
            for i in range(alea.randint(0, 40)):
                r = alea.random()
                if r < 0.1:
                    idx['k%d' % i] = None
                elif r < 0.2:
                    idx['k%d' % i] = {'kw_fr': None}
                else:
                    idx['k%d' % i] = {'kw_fr': [alea.choice(mots) for _ in
                                                range(alea.randint(0, 6))]}
            cles, p, a = f(idx.items())
            self.assertEqual(cles, list(idx))
            self.assertEqual(p, self._ancien_personnes(idx.values()))
            self.assertEqual(a, self._ancien_animaux(idx.values()))


class LesDeuxAppelantsPassentParLaMemoire(unittest.TestCase):
    def _src(self, nom):
        for n in ARBRE.body:
            if isinstance(n, ast.FunctionDef) and n.name == nom:
                corps = n.body[1:] if (n.body and isinstance(n.body[0], ast.Expr)
                                       and isinstance(n.body[0].value, ast.Constant)) else n.body
                return '\n'.join(ast.unparse(x) for x in corps)
        raise AssertionError(nom + ' introuvable')

    def test_places_list_et_cles_du_lieu(self):
        for nom in ('places_list', '_cles_du_lieu'):
            src = self._src(nom)
            self.assertIn('_lieux_des_cles(', src, nom)
            self.assertNotIn('lieux_du_chemin(', src, nom)


if __name__ == '__main__':
    unittest.main()
