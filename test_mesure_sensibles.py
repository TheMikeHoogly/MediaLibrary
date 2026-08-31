#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regles pures du banc des sensibles (chantier 18) : candidature, tirage
deterministe, lecture du verdict. Aucun acces NAS, base ni Ollama."""

import unittest

from mesure_sensibles import (CATEGORIES, echantillonner, est_candidat,
                              lire_verdict, mots_de)


class LaCandidature(unittest.TestCase):

    def test_un_recu_est_candidat(self):
        self.assertTrue(est_candidat({'kw_fr': ['recu', 'table'], 'desc': ''}))

    def test_la_description_suffit(self):
        self.assertTrue(est_candidat(
            {'kw_fr': ['blanc'], 'desc': 'Une capture de conversation.'}))

    def test_un_paysage_ne_l_est_pas(self):
        self.assertFalse(est_candidat(
            {'kw_fr': ['montagne', 'lac'], 'kw_en': ['mountain'],
             'desc': 'Un lac de montagne au soleil.'}))

    def test_un_tag_nomme_ne_compte_pas(self):
        # « personne:Carte » serait un nom, pas un mot-cle libre.
        self.assertFalse(est_candidat({'kw_fr': ['personne:Carte'], 'desc': ''}))
        self.assertIn('carte', mots_de({'kw_fr': ['carte'], 'desc': ''}))


class LeTirageEstDeterministe(unittest.TestCase):

    ENTREES = ([('c%02d' % i, {'kw_fr': ['document'], 'desc': ''}) for i in range(20)]
               + [('t%02d' % i, {'kw_fr': ['plage'], 'desc': ''}) for i in range(20)])

    def test_meme_graine_meme_echantillon(self):
        a = echantillonner(self.ENTREES, 5, 5, 42)
        b = echantillonner(self.ENTREES, 5, 5, 42)
        self.assertEqual(a, b)
        self.assertEqual(len(a[0]), 5)
        self.assertEqual(len(a[1]), 5)
        self.assertTrue(all(k.startswith('c') for k in a[0]))
        self.assertTrue(all(k.startswith('t') for k in a[1]))

    def test_une_autre_graine_change_le_tirage(self):
        self.assertNotEqual(echantillonner(self.ENTREES, 5, 5, 42),
                            echantillonner(self.ENTREES, 5, 5, 7))


class LaLectureDuVerdict(unittest.TestCase):

    def test_json_propre(self):
        self.assertEqual(lire_verdict('{"sensible": "facture", "confiance": "haute"}'),
                         ('facture', 'haute'))

    def test_json_noye_dans_du_texte(self):
        self.assertEqual(lire_verdict('Voici : {"sensible": "non"} merci'),
                         ('non', ''))

    def test_categorie_inventee_vaut_illisible(self):
        # le garde-fou des axes (26/08) : une valeur libre n'entre pas.
        self.assertEqual(lire_verdict('{"sensible": "porno"}')[0], 'illisible')

    def test_vide_ou_casse(self):
        self.assertEqual(lire_verdict('')[0], 'illisible')
        self.assertEqual(lire_verdict('pas du json')[0], 'illisible')

    def test_les_six_categories_de_mike(self):
        self.assertEqual(CATEGORIES, ('facture', 'paie', 'identite',
                                      'banque', 'medical', 'message'))


if __name__ == '__main__':
    unittest.main(verbosity=1)
