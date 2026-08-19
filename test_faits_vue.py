#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de `faits_vue` — la VUE des faits d'une photo.

Ce que ces tests protègent, dans l'ordre de ce qui a coûté cher :

1. **Le lieu par SEGMENTS ENTIERS.** Le miroir du renommage
   (`resolve_path_place`) teste une sous-chaîne et colle « Ins » à 442 photos
   de « Cousins&Cousines ». Deux tests le vérifient EN COMPARANT les deux
   règles : si un jour elles se rejoignent, c'est que quelqu'un a rebranché la
   mauvaise.
2. **Un nom retiré ne revient pas.** C'est l'invariant sacré, dans son sens le
   moins intuitif : perdre un nom est interdit, le RESSUSCITER aussi.
3. **La date ne tombe jamais sur `mtime`.**
"""

import unittest

import faits_vue
from renommage_facts import load_lieux, resolve_path_place
from pathlib import Path


RACINES = ['\\\\NAS-Bremblens\\home\\Photos\\_Uploads',
           '\\\\NAS-Bremblens\\home\\Photos']

LIEUX = {'ins': 'Ins', 'orbe': 'Orbe', 'vallorbe': 'Vallorbe',
         'barcelone': 'Barcelone', 'crete': 'Crète', 'lausanne': 'Lausanne',
         'bremblens': 'Bremblens'}


def cle(*segments):
    """Clé d'index NAS à partir de segments de dossier + nom de fichier."""
    return '\\\\NAS-Bremblens\\home\\Photos\\' + '\\'.join(segments)


class TestLieuParSegments(unittest.TestCase):

    def test_ins_ne_colle_pas_a_cousins_et_cousines(self):
        k = cle('2015 Cousins&Cousines', 'img_001.jpg')
        self.assertIsNone(faits_vue.lieu_par_segments(k, LIEUX, RACINES))

    def test_et_la_regle_du_renommage_s_y_trompe_elle(self):
        """Le test qui donne son sens au précédent : les deux règles DIVERGENT.
        S'il tombe, c'est que `resolve_path_place` a changé — ou qu'on a
        rebranché la vue dessus."""
        k = cle('2015 Cousins&Cousines', 'img_001.jpg')
        self.assertEqual(resolve_path_place(k, LIEUX), 'Ins')

    def test_orbe_ne_colle_pas_a_vallorbe(self):
        k = cle('2019 Vallorbe', 'img.jpg')
        self.assertEqual(faits_vue.lieu_par_segments(k, LIEUX, RACINES),
                         'Vallorbe')

    def test_le_dossier_le_plus_profond_gagne(self):
        k = cle('Lausanne', 'Barcelone', 'img.jpg')
        self.assertEqual(faits_vue.lieu_par_segments(k, LIEUX, RACINES),
                         'Barcelone')

    def test_un_mot_long_du_segment_est_cherche(self):
        k = cle('Vacances Crete 2018', 'img.jpg')
        self.assertEqual(faits_vue.lieu_par_segments(k, LIEUX, RACINES),
                         'Crète')

    def test_le_nom_du_NAS_n_est_pas_un_lieu(self):
        """« NAS-Bremblens » contient « Bremblens » : sans le retrait de la
        racine média, 30 682 photos deviendraient des photos de Bremblens."""
        k = cle('2015 Cousins&Cousines', 'img.jpg')
        self.assertIsNone(faits_vue.lieu_par_segments(k, LIEUX, RACINES))
        # ... et sans racines, le défaut réapparaît : la démonstration.
        self.assertEqual(faits_vue.lieu_par_segments(k, LIEUX, []), 'Bremblens')

    def test_dossier_bruit_ignore(self):
        k = '\\\\NAS-Bremblens\\home\\Photos\\DCIM\\img.jpg'
        self.assertIsNone(faits_vue.lieu_par_segments(k, LIEUX, RACINES))

    def test_le_nom_de_fichier_n_est_pas_un_dossier(self):
        k = cle('2020', 'Barcelone.jpg')
        self.assertIsNone(faits_vue.lieu_par_segments(k, LIEUX, RACINES))

    def test_sans_lieux_connus_rien(self):
        self.assertIsNone(faits_vue.lieu_par_segments(cle('Barcelone', 'a.jpg'),
                                                      {}, RACINES))


class TestLieuPour(unittest.TestCase):

    def test_le_gps_prime_sur_le_chemin(self):
        k = cle('Barcelone', 'img.jpg')
        self.assertEqual(faits_vue.lieu_pour(k, LIEUX, RACINES, 'Madrid'),
                         ('Madrid', 'gps'))

    def test_sinon_le_chemin(self):
        k = cle('Barcelone', 'img.jpg')
        self.assertEqual(faits_vue.lieu_pour(k, LIEUX, RACINES, None),
                         ('Barcelone', 'chemin'))

    def test_rien_rend_deux_none(self):
        k = cle('Inconnu', 'img.jpg')
        self.assertEqual(faits_vue.lieu_pour(k, LIEUX, RACINES, None),
                         (None, None))


class TestDate(unittest.TestCase):

    def test_taken_prime(self):
        k = cle('2010', 'img.jpg')
        txt, src = faits_vue.date_et_source(k, {'taken': 1300000000})
        self.assertEqual(src, 'exif')
        self.assertTrue(txt)

    def test_repli_sur_le_nom(self):
        k = cle('Divers', '20150714_120000.jpg')
        txt, src = faits_vue.date_et_source(k, {})
        self.assertEqual(src, 'nom du fichier')
        self.assertIn('2015', txt)

    def test_repli_sur_l_annee_du_dossier(self):
        k = cle('2003 Vacances', 'img.jpg')
        self.assertEqual(faits_vue.date_et_source(k, {}), ('2003',
                                                           'annee du dossier'))

    def test_le_mtime_n_est_JAMAIS_une_date(self):
        """`mtime` porte la date du TAGGING : une photo de 1998 réécrite en
        2026 (décision du 15/08). Il est ici, dans l'entrée, et doit rester
        invisible."""
        k = cle('Divers', 'img.jpg')
        self.assertEqual(faits_vue.date_et_source(k, {'mtime': 1770000000}),
                         (None, None))


class TestNoms(unittest.TestCase):

    def test_par_defaut_les_mots_cles_de_l_index(self):
        k = cle('Divers', 'img.jpg')
        a = faits_vue.assertions(k, {'kw_fr': ['personne:Flo', 'plage']})
        self.assertEqual(a['persons'], ['Flo'])

    def test_noms_attendus_fait_AUTORITE(self):
        """Le cœur du chantier : l'index porte encore « Flo », mais l'autorité
        vivante (fiches + `exclude`) ne le donne plus. Un champ FIGÉ le
        garderait — c'est exactement les 12 divergences des 81 photos déjà
        pourvues. La vue, non."""
        k = cle('Divers', 'img.jpg')
        a = faits_vue.assertions(k, {'kw_fr': ['personne:Flo']},
                                 noms_attendus=[])
        self.assertEqual(a['persons'], [])

    def test_noms_attendus_peut_AJOUTER(self):
        k = cle('Divers', 'img.jpg')
        a = faits_vue.assertions(k, {'kw_fr': []},
                                 noms_attendus=['personne:Mike', 'animal:Mutz'])
        self.assertEqual(a['persons'], ['Mike'])
        self.assertEqual(a['animals'], ['Mutz'])

    def test_la_source_est_index_jamais_xmp(self):
        """La vue ne rouvre aucun fichier : annoncer `xmp` ferait porter au
        fait la provenance d'une lecture qui n'a pas eu lieu."""
        k = cle('Divers', 'img.jpg')
        F = faits_vue.faits(k, {'kw_fr': ['personne:Mike']})
        srcs = {f['src'] for f in F if f['t'] == 'personne'}
        self.assertEqual(srcs, {'index'})


class TestFaits(unittest.TestCase):

    def test_forme_et_provenance(self):
        k = cle('Barcelone', 'img.jpg')
        F = faits_vue.faits(k, {'kw_fr': ['personne:Mike'], 'taken': 1300000000},
                            especes={'chat'}, lieux=LIEUX, racines=RACINES)
        par_type = {f['t']: f for f in F}
        self.assertEqual(par_type['personne']['v'], 'Mike')
        self.assertEqual(par_type['personne']['src'], 'index')
        self.assertEqual(par_type['lieu']['v'], 'Barcelone')
        self.assertEqual(par_type['lieu']['src'], 'chemin')
        self.assertEqual(par_type['espece']['src'], 'detection (yolo+siglip)')
        self.assertEqual(par_type['date']['src'], 'exif')

    def test_photo_muette_rend_une_liste_vide(self):
        k = cle('Inconnu', 'img.jpg')
        self.assertEqual(faits_vue.faits(k, {}, lieux=LIEUX, racines=RACINES),
                         [])

    def test_pas_d_exception_sur_une_entree_bizarre(self):
        for e in ({}, {'kw_fr': None}, {'taken': None}, {'taken': True}):
            faits_vue.faits(cle('X', 'a.jpg'), e, lieux=LIEUX, racines=RACINES)


class TestLieuxReels(unittest.TestCase):
    """Le fichier `lieux.txt` du projet, s'il est là : la règle doit tenir sur
    le vrai vocabulaire, pas seulement sur sept libellés choisis."""

    @classmethod
    def setUpClass(cls):
        cls.lieux = load_lieux(Path(__file__).with_name('lieux.txt'))

    def test_cousins_et_cousines_ne_rend_rien_avec_le_vrai_fichier(self):
        if not self.lieux:
            self.skipTest('lieux.txt absent')
        k = cle('2015 Cousins&Cousines', 'img.jpg')
        self.assertIsNone(faits_vue.lieu_par_segments(k, self.lieux, RACINES))
        self.assertEqual(resolve_path_place(k, self.lieux), 'Ins')



class TestRacinesCouples(unittest.TestCase):
    """`server.media_roots()` rend des couples (libellé, chemin) ; la règle les
    accepte tels quels, pour que le serveur n'ait rien à reformater — un
    reformatage dans l'appelant est une deuxième implémentation qui attend son
    heure."""

    def test_couples_acceptes(self):
        couples = [('Uploads', RACINES[0]), ('Photos', RACINES[1])]
        k = cle('Barcelone', 'img.jpg')
        self.assertEqual(faits_vue.lieu_par_segments(k, LIEUX, couples),
                         'Barcelone')
        self.assertEqual(faits_vue.chemin_relatif(k, couples),
                         '\\Barcelone\\img.jpg')

    def test_la_racine_la_plus_specifique_gagne(self):
        k = ('\\\\NAS-Bremblens\\home\\Photos\\_Uploads\\Barcelone\\img.jpg')
        self.assertEqual(faits_vue.chemin_relatif(k, RACINES),
                         '\\Barcelone\\img.jpg')

if __name__ == '__main__':
    unittest.main(verbosity=2)
