#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_axe_espece` — logique PURE, aucune base, aucun serveur.

Ce qu'on protège ici, c'est la RÈGLE DE CONCORDANCE : c'est elle qui décidera
ce que le jeton `espece:` rend, et elle n'existait jusqu'ici que sous forme de
chiffres dans `eval/DECISIONS.md`.

1. **Mot ENTIER, jamais sous-chaîne** — « château » ne contient pas un chat,
   « brochet » pas un chat non plus. C'est la leçon du 19/08 (« Ins » trouvé
   dans « Cousins&Cousines »), appliquée avant de la repayer.
2. **Accents et casse ne changent rien** : la recherche compare normalisé.
3. **`kw_fr` et `desc` sont deux sources distinctes**, et le banc doit savoir
   laquelle parle — une règle portée par le seul texte libre ne serait pas la
   même règle.
4. **Stricte contre élargie** : « poney » ou « brebis » ne comptent QUE dans la
   règle élargie. Si cette frontière tombait, les deux colonnes du rapport
   diraient la même chose et la comparaison ne trancherait plus rien.
"""

import unittest

import mesure_axe_espece as M


class TestMotEntier(unittest.TestCase):

    def test_chateau_n_est_pas_un_chat(self):
        self.assertEqual(M.dit_l_espece({'kw_fr': ['château']}, 'chat'),
                         (False, False))

    def test_le_mot_et_son_pluriel_comptent(self):
        self.assertTrue(M.dit_l_espece({'kw_fr': ['chat']}, 'chat')[0])
        self.assertTrue(M.dit_l_espece({'kw_fr': ['deux chats']}, 'chat')[0])

    def test_dans_un_keyword_compose(self):
        self.assertTrue(M.dit_l_espece({'kw_fr': ['chat gris et blanc']},
                                       'chat')[0])

    def test_accents_et_casse(self):
        self.assertTrue(M.dit_l_espece({'kw_fr': ['CHÂTAIGNE', 'Chat']},
                                       'chat')[0])
        self.assertTrue(M.dit_l_espece({'desc': "Un CHEVAL au pré."},
                                       'cheval')[1])


class TestLesDeuxSources(unittest.TestCase):

    def test_kw_fr_et_desc_sont_distinguees(self):
        self.assertEqual(M.dit_l_espece({'kw_fr': ['chien'], 'desc': ''},
                                        'chien'), (True, False))
        self.assertEqual(M.dit_l_espece({'kw_fr': [], 'desc': 'un chien'},
                                        'chien'), (False, True))
        self.assertEqual(M.dit_l_espece({'kw_fr': ['chien'], 'desc': 'chien'},
                                        'chien'), (True, True))

    def test_entree_vide_ne_dit_rien(self):
        self.assertEqual(M.dit_l_espece({}, 'vache'), (False, False))


class TestStricteContreElargie(unittest.TestCase):

    def test_poney_est_un_cheval_seulement_en_elargie(self):
        e = {'kw_fr': ['poney']}
        self.assertEqual(M.dit_l_espece(e, 'cheval'), (False, False))
        self.assertTrue(any(M.dit_l_espece(e, 'cheval', elargie=True)))

    def test_brebis_agneau_chaton_veau(self):
        for mot, m in (('mouton', 'brebis'), ('mouton', 'agneaux'),
                       ('chat', 'chaton'), ('vache', 'veau')):
            e = {'kw_fr': [m]}
            self.assertEqual(M.dit_l_espece(e, mot), (False, False), m)
            self.assertTrue(any(M.dit_l_espece(e, mot, elargie=True)), m)

    def test_l_elargie_contient_la_stricte(self):
        for mot in M.STRICTES:
            self.assertTrue(M.formes(mot) <= M.formes(mot, elargie=True))

    def test_chaque_espece_coco_a_ses_formes(self):
        for mot in M.MOTS.values():
            self.assertIn(mot, M.STRICTES)
            self.assertIn(mot, M.ELARGIES)
            self.assertIn(mot, M.formes(mot))


class TestRapport(unittest.TestCase):

    def rapport(self):
        v = {'tagueur': 10, 'concordance': 8, 'deja_rendu': 5, 'ajout': 3,
             'tagueur_seul': 2, 'yolo_seul': 1, 'ajout_espece_seule': 1,
             'rendu_hors_concordance': 4}
        return {
            'base': 'copie.db', 'photos_lues': 100, 'lecture_s': 1.0,
            'taguees_avec_les_faits': 82, 'fait_non_date': 90,
            'atteintes_nom_ou_lieu': 80, 'espece_seule': 10,
            'publie_20_08_union': M.PUBLIE_UNION, 'duree_s': 2.0,
            'especes': [{'espece': 'cat', 'mot': 'chat', 'yolo': 12,
                         'rendus_par_le_mot': 9, 'publie_20_08': 2316,
                         'mot_mange_par': {'noms': [], 'lieux': []},
                         'ou_le_tagueur_le_dit': [3, 2, 5],
                         'variantes': {'stricte': v, 'elargie': dict(v)},
                         'exemples_ajout': ['a.jpg'],
                         'exemples_hors': ['b.jpg']}],
            'regle': {r: {'union': 8, 'ajout': 3, 'espece_seule_atteinte': 2,
                          'espece_seule_atteinte_par_le_seul_jeton': 1}
                      for r in ('stricte', 'elargie')},
        }

    def test_le_rapport_montre_l_ajout_et_l_ecart(self):
        txt = M.afficher(self.rapport())
        self.assertIn('AJOUTE', txt)
        self.assertIn('2316', txt)          # le publié du 20/08, pour l'écart
        self.assertIn('ESPÈCE SEULE', txt)

    def test_le_mot_mange_par_un_nom_est_signale(self):
        r = self.rapport()
        r['especes'][0]['mot_mange_par'] = {'noms': ['Chat'], 'lieux': []}
        self.assertIn('ATTENTION', M.afficher(r))


if __name__ == '__main__':
    unittest.main(verbosity=2)
