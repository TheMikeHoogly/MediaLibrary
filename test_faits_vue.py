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

# Lieux du fonds réel qui ont payé le chantier 14a-i (19/08).
LIEUX_14A = dict(LIEUX, **{
    'yani': 'Yani', 'achumani': 'Achumani', 'irpavi': 'Irpavi',
    'chatel': 'Châtel', 'crans-montana': 'Crans-Montana',
    "vallee d'aoste": "Vallée d'Aoste", 'sud france': 'Sud France',
    'france': 'France', 'belgique': 'Belgique', 'la paz': 'La Paz',
    'san borja': 'San Borja'})


class TestRegleUnifiee(unittest.TestCase):
    """Le chantier 14a-i : `places_list` et `_cles_du_lieu` — ce que Mike VOIT
    — testaient une SOUS-CHAÎNE, et collaient « Ins » à 493 photos. Les brancher
    sur la règle des segments les aurait débarrassés de 546 faux, mais leur
    aurait aussi coûté 330 VRAIS lieux : les dossiers de famille collent le lieu
    à l'année (« Yani2004 ») ou au sujet (« AchumaniAlto »).

    Chaque test ci-dessous est un cas mesuré sur le fonds, avec son compte."""

    def lieu(self, dossier, fichier='img.jpg', **kw):
        return faits_vue.lieu_par_segments(cle(dossier, fichier), LIEUX_14A,
                                           RACINES, **kw)

    # — ce que la découpe des mots collés RÉCUPÈRE (330 photos) —

    def test_le_lieu_colle_a_son_annee(self):
        """« 20040501 Yani2004 » : 219 photos, perdues par la règle d'origine."""
        self.assertEqual(self.lieu('20040501 Yani2004'), 'Yani')

    def test_le_lieu_colle_a_son_sujet(self):
        self.assertEqual(self.lieu('20010421 AchumaniAlto'), 'Achumani')
        self.assertEqual(self.lieu('20021124 CuevaMarkusIrpavi'), 'Irpavi')

    def test_la_decoupe_gagne_meme_des_lieux_que_la_sous_chaine_ratait(self):
        """« SanBorjaTriniSRZ » : 82 photos qu'AUCUNE des deux règles n'avait."""
        self.assertEqual(self.lieu('20040425 SanBorjaTriniSRZ'), 'San Borja')

    # — et ce qu'elle ne rend PAS : c'est là qu'est la différence avec la
    #   sous-chaîne, et c'est ce qui doit tenir dans le temps —

    def test_mais_un_mot_sans_frontiere_reste_entier(self):
        for dossier, faux in (('04 Les grottes de Vallorbe', 'Orbe'),
                              ('2015 Cousins&Cousines', 'Ins'),
                              ('20260602 Flo et Sylvie Chatelain', 'Châtel')):
            self.assertNotEqual(self.lieu(dossier), faux, dossier)

    def test_le_seuil_protege_les_libelles_courts(self):
        """« Blick ins Tal » : « ins » est un mot entier — et fait 3 lettres."""
        self.assertIsNone(self.lieu('Blick ins Tal'))

    # — les deux trous connus, bouchés —

    def test_le_libelle_multi_mots_est_essaye_dans_le_segment(self):
        """124 photos : « Weekend Vallée d'Aoste »."""
        self.assertEqual(self.lieu("Weekend Vallée d'Aoste"), "Vallée d'Aoste")

    def test_le_trait_d_union_ne_casse_plus_la_cle(self):
        self.assertEqual(self.lieu('Crans-Montana'), 'Crans-Montana')

    def test_mais_il_coupe_encore_en_dernier_recours(self):
        """Ce que la règle d'origine trouvait ne doit pas être perdu."""
        self.assertEqual(self.lieu('Vacances-Crete'), 'Crète')

    # — une règle, deux lectures —

    def test_tous_rend_chaque_lieu_designe(self):
        """`/sujets` et la recherche comptent une photo dans CHAQUE lieu ;
        le fait « lieu » d'une photo, lui, n'en porte qu'un."""
        k = cle('2009', '04 Avril', 'France & Belgique', 'img.jpg')
        self.assertEqual(
            faits_vue.lieux_du_chemin(k, LIEUX_14A, RACINES, tous=True),
            ['France', 'Belgique'])
        self.assertEqual(faits_vue.lieu_par_segments(k, LIEUX_14A, RACINES),
                         'France')

    def test_le_nom_de_fichier_ne_compte_pas_par_defaut(self):
        """Le fait « lieu » se lit dans les DOSSIERS : le renommage écrit des
        lieux dans les noms (71 des 132 cas mesurés), et les relire serait
        circulaire. `/sujets` l'active, pour 52 vrais contre 9 faux."""
        k = cle('2009', '04 Avril', '20km de Lausanne.jpg')
        self.assertEqual(faits_vue.lieux_du_chemin(k, LIEUX_14A, RACINES,
                                                   tous=True), [])
        self.assertEqual(faits_vue.lieux_du_chemin(k, LIEUX_14A, RACINES,
                                                   tous=True,
                                                   avec_fichier=True),
                         ['Lausanne'])

    # — le banc mesure bien un AVANT, pas la règle d'aujourd'hui —

    def test_les_options_d_avant_reproduisent_l_ancienne_regle(self):
        """Si ce test tombe, `mesure_lieu_visible.py` compare deux fois la
        MÊME règle et son « avant/après » ne vaut plus rien."""
        av = faits_vue.OPTIONS_AVANT_14A
        self.assertIsNone(self.lieu('Crans-Montana', **av))
        self.assertIsNone(self.lieu("Weekend Vallée d'Aoste", **av))
        self.assertIsNone(self.lieu('20040501 Yani2004', **av))
        self.assertEqual(self.lieu('Vacances-Crete', **av), 'Crète')


class TestDateDeScan(unittest.TestCase):
    """La date du SCAN, écartée à la LECTURE (19/08). Le numériseur inscrit
    l'instant du scan dans `DateTimeOriginal` **et** dans le nom du fichier ;
    l'index a gardé les deux. 72 photos en base, +2 à +32 ans au-delà de leur
    dossier — contre **1 347** dont le `taken` est ANTÉRIEUR au dossier, et
    celles-là ont raison. D'où un garde-fou asymétrique, et aucune écriture."""

    def epoch(self, an, mois=5, jour=1):
        import time
        return time.mktime((an, mois, jour, 12, 0, 0, 0, 0, -1))

    def test_une_date_posterieure_au_dossier_n_est_pas_crue(self):
        k = cle('Photos Papa', '1990', '1990_Achumani', 'img.jpg')
        self.assertFalse(faits_vue.date_credible(k, self.epoch(2007)))

    def test_une_date_ANTERIEURE_est_crue_c_est_l_exif_qui_corrige(self):
        """1 347 photos : « 2026\\Photos Floflo » contient de vraies photos de
        2014. Un garde-fou symétrique ferait dix-huit fois plus de dégâts."""
        k = cle('2026', 'Photos Floflo', 'img.jpg')
        self.assertTrue(faits_vue.date_credible(k, self.epoch(2014)))

    def test_un_reveillon_reste_credible(self):
        """« 2019 Voyage » qui contient le 1er janvier 2020 : la tolérance d'un
        an couvre les 139 réveillons comptés le 14/08."""
        k = cle('2019 Voyage', 'img.jpg')
        self.assertTrue(faits_vue.date_credible(k, self.epoch(2020, 1, 1)))

    def test_sans_annee_dans_le_dossier_rien_a_contredire(self):
        self.assertTrue(faits_vue.date_credible(cle('Divers', 'img.jpg'),
                                                self.epoch(2007)))

    def test_taken_credible_rend_None_sur_une_date_de_scan(self):
        k = cle('Photos Papa', '1990', '1990_Achumani', 'img.jpg')
        self.assertIsNone(faits_vue.taken_credible(k, {'taken': self.epoch(2007)}))
        self.assertEqual(faits_vue.taken_credible(k, {'taken': self.epoch(1990)}),
                         self.epoch(1990))

    def test_le_fait_retombe_sur_l_annee_du_DOSSIER_pas_sur_le_scan(self):
        """Refuser ne fabrique rien : on retombe sur ce qu'un humain savait."""
        k = cle('Photos Papa', '1990', '1990_Achumani', 'img.jpg')
        self.assertEqual(faits_vue.date_et_source(k, {'taken': self.epoch(2007)}),
                         ('1990', 'annee du dossier'))

    def test_le_nom_de_fichier_y_passe_AUSSI(self):
        """Le garde-fou du 17/08 ne fermait qu'une porte sur deux : le scanner
        écrit la même date dans le nom."""
        k = cle('Photos Papa', '1990', '1990_Achumani', '20070501_120000.jpg')
        self.assertEqual(faits_vue.date_et_source(k, {})[1], 'annee du dossier')

    def test_rien_n_est_ecrit(self):
        """La correction est une VUE : l'entrée d'index n'est pas touchée."""
        k = cle('Photos Papa', '1990', '1990_Achumani', 'img.jpg')
        e = {'taken': self.epoch(2007)}
        faits_vue.date_et_source(k, e)
        self.assertEqual(e, {'taken': self.epoch(2007)})


if __name__ == '__main__':
    unittest.main(verbosity=2)
