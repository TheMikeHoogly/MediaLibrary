#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regles pures du banc de comparaison v0/v2ctx (chantier 2 bis). Aucun acces
NAS, base ni Ollama -- comme `test_mesure_sensibles.py`."""

import unittest

from mesure_retag_gain import (assertions_pour, divergence, echantillonner,
                               empreinte_prompt, generation, jaccard,
                               plain_kw, resume_groupe)


class LaGenerationEtLeVocabulaireLibre(unittest.TestCase):

    def test_sans_pipe_est_v0(self):
        self.assertEqual(generation({'kw_fr': ['chat']}), 'v0')

    def test_avec_pipe_est_sa_valeur(self):
        self.assertEqual(generation({'pipe': 'qwen3-vl:2b|v2ctx|kb1'}),
                         'qwen3-vl:2b|v2ctx|kb1')

    def test_pipe_vide_retombe_sur_v0(self):
        # e.get('pipe') or 'v0' -- identique a server._tagging_pipe_counts.
        self.assertEqual(generation({'pipe': ''}), 'v0')

    def test_plain_kw_exclut_les_tags_nommes(self):
        self.assertEqual(plain_kw(['Chat', 'personne:Flo', 'ANIMAL:Rex']),
                         ['chat'])

    def test_plain_kw_minuscule_pour_comparer(self):
        self.assertEqual(plain_kw(['Plage', 'plage']), ['plage', 'plage'])


class LesAssertionsAutoSuffisantes(unittest.TestCase):

    def test_reprend_les_noms_deja_attribues(self):
        a = assertions_pour({'kw_fr': ['personne:Flo', 'plage'],
                             'kw_en': ['animal:Rex']})
        self.assertEqual(a['persons'], ['Flo'])
        self.assertEqual(a['animals'], ['Rex'])
        self.assertEqual(a['tags_fr'], ['plage'])

    def test_sans_date_ni_gps_les_champs_restent_none(self):
        a = assertions_pour({'kw_fr': ['plage']})
        self.assertIsNone(a['date'])
        self.assertIsNone(a['lieu'])
        self.assertEqual(a['species'], [])

    def test_avec_taken_la_date_est_formatee(self):
        # 11 decembre 2018, meme cas que tagging_meta.format_date_fr.
        a = assertions_pour({'kw_fr': [], 'taken': 1544565708})
        self.assertEqual(a['date_src'], 'exif')
        self.assertIn('decembre', a['date'])

    def test_tags_fr_plafonne_a_12(self):
        kw = ['mot%d' % i for i in range(20)]
        a = assertions_pour({'kw_fr': kw})
        self.assertEqual(len(a['tags_fr']), 12)


class LaDivergence(unittest.TestCase):

    def test_jaccard_identique_vaut_1(self):
        self.assertEqual(jaccard(['a', 'b'], ['b', 'a']), 1.0)

    def test_jaccard_vide_des_deux_cotes_vaut_1(self):
        # rien a comparer -> pas de divergence mesurable, pas une alarme.
        self.assertEqual(jaccard([], []), 1.0)

    def test_jaccard_disjoint_vaut_0(self):
        self.assertEqual(jaccard(['a'], ['b']), 0.0)

    def test_divergence_ignore_les_tags_nommes(self):
        d = divergence(['personne:Flo', 'plage'], ['plage'], ['personne:Flo'])
        # cote ancien : {'plage'} (personne: exclu) ; cote nouveau : {'plage'}
        # (personne: exclu aussi) -> identiques, jaccard 1.
        self.assertEqual(d['jaccard'], 1.0)
        self.assertEqual(d['ajoutes'], [])
        self.assertEqual(d['retires'], [])

    def test_divergence_rapporte_ajouts_et_retraits(self):
        d = divergence(['plage', 'ete'], ['plage', 'foule'], [])
        self.assertEqual(d['ajoutes'], ['foule'])
        self.assertEqual(d['retires'], ['ete'])
        self.assertAlmostEqual(d['jaccard'], 1 / 3, places=3)


class LeTirageEstDeterministe(unittest.TestCase):

    ENTREES = ([('v0_%02d' % i, {'kw_fr': ['x']}) for i in range(20)]
               + [('v2_%02d' % i, {'kw_fr': ['x'], 'pipe': 'qwen3-vl:2b|v2ctx|kb1'})
                  for i in range(20)])

    def test_meme_graine_meme_echantillon(self):
        a = echantillonner(self.ENTREES, 5, 5, 42)
        b = echantillonner(self.ENTREES, 5, 5, 42)
        self.assertEqual(a, b)
        self.assertTrue(all(k.startswith('v0_') for k in a[0]))
        self.assertTrue(all(k.startswith('v2_') for k in a[1]))

    def test_une_autre_graine_change_le_tirage(self):
        self.assertNotEqual(echantillonner(self.ENTREES, 5, 5, 42),
                            echantillonner(self.ENTREES, 5, 5, 7))


class LeResumeDeGroupe(unittest.TestCase):

    def test_groupe_vide_rend_des_none(self):
        r = resume_groupe([])
        self.assertEqual(r['n'], 0)
        self.assertIsNone(r['jaccard_moyen'])

    def test_moyenne_simple(self):
        lignes = [{'jaccard': 1.0, 'ajoutes': [], 'retires': []},
                 {'jaccard': 0.5, 'ajoutes': ['a', 'b'], 'retires': ['c']}]
        r = resume_groupe(lignes)
        self.assertEqual(r['n'], 2)
        self.assertAlmostEqual(r['jaccard_moyen'], 0.75)
        self.assertAlmostEqual(r['ajoutes_moyen'], 1.0)
        self.assertAlmostEqual(r['retires_moyen'], 0.5)


class L_EmpreinteDuPrompt(unittest.TestCase):

    def test_stable_d_un_appel_a_l_autre(self):
        self.assertEqual(empreinte_prompt(), empreinte_prompt())

    def test_change_si_le_prompt_de_prod_change(self):
        import tagging_meta as tm
        avant = empreinte_prompt()
        ancien = tm.REGLES_JSON
        try:
            tm.REGLES_JSON = ancien + ' (modifie pour le test)'
            self.assertNotEqual(empreinte_prompt(), avant)
        finally:
            tm.REGLES_JSON = ancien
        self.assertEqual(empreinte_prompt(), avant)


if __name__ == '__main__':
    unittest.main(verbosity=1)
