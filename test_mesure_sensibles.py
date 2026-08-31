#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regles pures du banc des sensibles (chantier 18) : candidature, tirage
deterministe, lecture du verdict. Aucun acces NAS, base ni Ollama."""

import unittest

from mesure_sensibles import (CATEGORIES, echantillonner, empreinte_prompt,
                              est_candidat, lire_verdict, mots_de)


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

    def test_les_sept_categories_de_mike(self):
        # Six le 30/08 ; `administratif` ajoutee le 31/08 (la lettre de la
        # ville de Lausanne que le banc laissait passer en << non >>).
        self.assertEqual(CATEGORIES, ('facture', 'paie', 'identite', 'banque',
                                      'medical', 'message', 'administratif'))

    def test_administratif_est_un_verdict_lisible(self):
        self.assertEqual(lire_verdict('{"sensible": "administratif"}')[0],
                         'administratif')


class L_EmpreinteDuPrompt(unittest.TestCase):
    """Le cache porte l'empreinte de la QUESTION posee : changer les
    categories change l'empreinte, donc les vieux verdicts sont ecartes."""

    def test_stable_et_courte(self):
        e = empreinte_prompt()
        self.assertEqual(e, empreinte_prompt())
        self.assertEqual(len(e), 12)

    def test_change_avec_les_categories(self):
        import mesure_sensibles as m
        avant = empreinte_prompt()
        anciennes = m.CATEGORIES
        try:
            m.CATEGORIES = anciennes[:-1]      # comme avant le 31/08
            self.assertNotEqual(empreinte_prompt(), avant)
        finally:
            m.CATEGORIES = anciennes
        self.assertEqual(empreinte_prompt(), avant)


if __name__ == '__main__':
    unittest.main(verbosity=1)
