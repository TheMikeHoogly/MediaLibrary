#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_noms_casse` et de la RÈGLE UNIQUE `parse_tag_nomme`.

Logique PURE : aucune base, aucun serveur, aucun fichier.

Ce qu'on protège ici est un invariant du projet, pas un confort d'écriture :

1. **Le préfixe se lit sans égard à la casse.** C'est tout le défaut I7 : un
   « Personne:Flo » écrit par un autre logiciel était lu par trois fonctions
   et invisible aux trois autres — donc jamais compté, jamais rattaché, jamais
   retiré. Si ce test tombe, le défaut est de retour.
2. **Le NOM, lui, n'est jamais abaissé.** « Res Jordi » doit ressortir « Res
   Jordi » : ce nom part dans les XMP des fichiers, et la règle 2 du projet dit
   qu'un nom humain ne se perd jamais — le rendre en minuscules serait le
   perdre à moitié.
3. **Le verdict `sans_fiche` n'est PAS un verdict de casse.** Un nom que
   l'index porte et qu'aucune fiche ne réclame est une personne invisible à
   `/api/names`, pas une faute d'orthographe : les deux ne se réparent pas
   pareil, donc ils ne se comptent pas ensemble.
"""

import unittest

import mesure_noms_casse as M
from tagging_meta import est_tag_nomme, noms_depuis_kw, parse_tag_nomme

FICHES = {('personne', 'flo'): 'Flo',
          ('personne', 'res jordi'): 'Res Jordi',
          ('animal', 'luna'): 'Luna'}


class TestRegleUnique(unittest.TestCase):

    def test_le_prefixe_se_lit_sans_egard_a_la_casse(self):
        for t in ('personne:Flo', 'Personne:Flo', 'PERSONNE:Flo'):
            self.assertEqual(parse_tag_nomme(t), ('personne', 'Flo'), t)
        self.assertEqual(parse_tag_nomme('Animal:Luna'), ('animal', 'Luna'))

    def test_le_nom_n_est_jamais_abaisse(self):
        self.assertEqual(parse_tag_nomme('personne:Res Jordi')[1], 'Res Jordi')
        self.assertEqual(parse_tag_nomme('PERSONNE:Élodie')[1], 'Élodie')

    def test_ce_qui_n_est_pas_un_tag_nomme(self):
        for t in ('chat', 'personne', 'personnes:Flo', 'personne:', 'lieu:Ins',
                  'personne:   '):
            self.assertIsNone(parse_tag_nomme(t), t)
            self.assertFalse(est_tag_nomme(t), t)

    def test_les_espaces_autour_du_nom_ne_comptent_pas(self):
        self.assertEqual(parse_tag_nomme('personne:  Flo  '),
                         ('personne', 'Flo'))

    def test_un_nom_a_deux_points_garde_tout_ce_qui_suit(self):
        self.assertEqual(parse_tag_nomme('personne:Jean:Pierre')[1],
                         'Jean:Pierre')

    def test_noms_depuis_kw_partage_la_regle(self):
        p, a = noms_depuis_kw(['Personne:Flo', 'animal:Luna', 'chat',
                               'ANIMAL:Mutz'])
        self.assertEqual(p, ['Flo'])
        self.assertEqual(a, ['Luna', 'Mutz'])


class TestVerdict(unittest.TestCase):

    def v(self, tag):
        return M.verdict(tag, FICHES)[0]

    def test_conforme(self):
        self.assertEqual(self.v('personne:Flo'), 'ok')
        self.assertEqual(self.v('animal:Luna'), 'ok')

    def test_casse_du_nom(self):
        self.assertEqual(self.v('animal:luna'), 'casse')
        self.assertEqual(self.v('personne:FLO'), 'casse')

    def test_prefixe_non_canonique_prime(self):
        # Invisible à tout `startswith` : c'est le défaut le plus grave, il
        # prime sur l'orthographe du nom comme sur l'absence de fiche.
        self.assertEqual(self.v('Personne:Flo'), 'prefixe')
        self.assertEqual(self.v('Personne:flo'), 'prefixe')
        self.assertEqual(self.v('Personne:Inconnue'), 'prefixe')

    def test_sans_fiche_n_est_pas_un_defaut_de_casse(self):
        self.assertEqual(self.v('personne:Florine'), 'sans_fiche')
        self.assertEqual(self.v('personne:florine'), 'sans_fiche')

    def test_un_mot_cle_ordinaire_n_a_pas_de_verdict(self):
        self.assertIsNone(M.verdict('chat', FICHES))

    def test_le_verdict_rend_l_orthographe_de_la_fiche(self):
        self.assertEqual(M.verdict('animal:luna', FICHES),
                         ('casse', 'animal', 'luna', 'Luna'))


class TestDoublons(unittest.TestCase):

    def test_deux_ecritures_du_meme_nom(self):
        d = M.doublons_de_casse(['personne:Flo', 'personne:flo', 'chat'])
        self.assertEqual(len(d), 1)
        self.assertEqual(sorted(set(d[0])), ['personne:Flo', 'personne:flo'])

    def test_le_meme_tag_deux_fois_n_est_pas_un_doublon_de_casse(self):
        self.assertEqual(M.doublons_de_casse(['personne:Flo', 'personne:Flo']),
                         [])

    def test_deux_noms_distincts_ne_sont_pas_un_doublon(self):
        self.assertEqual(M.doublons_de_casse(['personne:Flo', 'personne:Mike']),
                         [])

    def test_le_genre_separe_les_noms(self):
        # « Luna » personne et « Luna » animal coexistent : ce n'est pas un
        # doublon d'écriture, ce sont deux sujets.
        self.assertEqual(M.doublons_de_casse(['personne:Luna', 'animal:Luna']),
                         [])


class TestRapport(unittest.TestCase):

    def rapport(self, **kw):
        r = {'base': 'copie.db', 'regle': 'prod', 'photos_lues': 10,
             'fiches': 3, 'tags_nommes': 12,
             'verdicts': {'ok': 12}, 'photos_par_verdict': {'ok': 10},
             'doublons_de_casse': 0, 'suspects': {}, 'exemples': {},
             'exemples_doublons': [], 'duree_s': 0.1}
        r.update(kw)
        return r

    def test_zero_defaut_le_dit_comme_un_defaut_latent(self):
        txt = M.afficher(self.rapport())
        self.assertIn('LATENT', txt)

    def test_un_defaut_est_nomme_avec_son_compte(self):
        txt = M.afficher(self.rapport(
            verdicts={'ok': 9, 'casse': 3},
            photos_par_verdict={'ok': 9, 'casse': 3},
            suspects={'animal|animal:luna': {'casse': 3}},
            exemples={'casse': [{'cle': 'k.jpg', 'tag': 'animal:luna',
                                 'fiche': 'Luna'}]}))
        self.assertIn('animal:luna', txt)
        self.assertIn('Luna', txt)
        self.assertNotIn('LATENT', txt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
