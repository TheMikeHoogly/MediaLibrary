#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_faits_backfill` — logique PURE, aucune base, aucun NAS.

Ce qu'on protège ici :

1. La règle de DATE du backfill est celle du Knowledge Builder amont
   (`server._assertions_pour`) : `taken` → date du NOM → année du DOSSIER,
   et **jamais le `mtime`** (décision du 15/08 : le tagging de 2026 a réécrit
   une photo de 1998 ; la seule photo qu'on ne sait pas dater passerait devant
   toutes les autres).
2. La SOURCE des noms est `index`, jamais `xmp` : le backfill ne rouvre aucun
   fichier. Écrire `xmp` ferait porter au fait la provenance d'une lecture qui
   n'a pas eu lieu — et toute la valeur du champ `faits` tombe.
3. Le lieu GPS prime sur le lieu de chemin, comme dans la prod.
4. Le compteur de lieux « collés à l'intérieur d'un mot » attrape bien le cas
   mesuré le 19/08 : « Ins » trouvé dans « Cousins&Cousines ».
5. Le banc REFUSE d'ouvrir `photos.db` : le serveur est l'écrivain unique.
"""

import unittest

import mesure_faits_backfill as M


class TestDate(unittest.TestCase):

    def test_taken_donne_exif(self):
        _, src = M.date_et_source(r'C:\Photos\x.jpg', {'taken': 1234567890})
        self.assertEqual(src, 'exif')

    def test_sans_taken_la_date_du_nom(self):
        txt, src = M.date_et_source(r'C:\Photos\20180101_120000.jpg', {})
        self.assertEqual(src, 'nom du fichier')
        self.assertIn('2018', txt)

    def test_sinon_annee_du_dossier(self):
        txt, src = M.date_et_source(r'C:\Photos\2016\DSC1.jpg', {})
        self.assertEqual((txt, src), ('2016', 'annee du dossier'))

    def test_le_mtime_ne_date_JAMAIS(self):
        # une entrée qui n'a QUE son mtime ne doit produire aucune date
        txt, src = M.date_et_source(r'C:\Photos\DSC1.jpg', {'mtime': 1700000000})
        self.assertIsNone(txt)
        self.assertIsNone(src)

    def test_taken_a_zero_nest_pas_une_date(self):
        txt, _ = M.date_et_source(r'C:\Photos\DSC1.jpg', {'taken': 0})
        self.assertIsNone(txt)


class TestAssertions(unittest.TestCase):

    def test_source_des_noms_est_index_jamais_xmp(self):
        a = M.assertions_depuis_index(
            r'C:\Photos\DSC1.jpg', {'kw_fr': ['personne:Mike']}, None, None, {})
        self.assertEqual(a['noms_src'], 'index')
        F = M.tagging_meta.faits_structures(a)
        self.assertTrue(all(f['src'] == 'index'
                            for f in F if f['t'] in ('personne', 'animal')))

    def test_noms_personnes_et_animaux(self):
        a = M.assertions_depuis_index(
            r'C:\Photos\DSC1.jpg',
            {'kw_fr': ['personne:Mike', 'animal:Mutz', 'chien']}, None, None, {})
        self.assertEqual(a['persons'], ['Mike'])
        self.assertEqual(a['animals'], ['Mutz'])

    def test_le_gps_prime_sur_le_chemin(self):
        lieux = {'lausanne': 'Lausanne'}
        a = M.assertions_depuis_index(r'C:\Photos\Lausanne\DSC1.jpg', {},
                                      None, 'Sion', lieux)
        self.assertEqual((a['lieu'], a['lieu_src']), ('Sion', 'gps'))

    def test_sans_lieu_la_source_est_nulle(self):
        a = M.assertions_depuis_index(r'C:\Photos\DSC1.jpg', {}, None, None, {})
        self.assertIsNone(a['lieu'])
        self.assertIsNone(a['lieu_src'])

    def test_espece_vient_des_detections(self):
        a = M.assertions_depuis_index(r'C:\Photos\DSC1.jpg', {}, {'chat'},
                                      None, {})
        F = M.tagging_meta.faits_structures(a)
        esp = [f for f in F if f['t'] == 'espece']
        self.assertEqual(len(esp), 1)
        self.assertIn('detection', esp[0]['src'])


class TestSignature(unittest.TestCase):

    def test_ignore_ordre_et_source(self):
        a = [{'t': 'personne', 'v': 'Mike', 'src': 'xmp'},
             {'t': 'date', 'v': '1 mai 2020', 'src': 'exif'}]
        b = [{'t': 'date', 'v': '1 mai 2020', 'src': 'exif'},
             {'t': 'personne', 'v': 'Mike', 'src': 'index'}]
        self.assertEqual(M.signature(a), M.signature(b))

    def test_voit_un_nom_disparu(self):
        a = [{'t': 'personne', 'v': 'Flo', 'src': 'xmp'}]
        self.assertNotEqual(M.signature(a), M.signature([]))


class TestLieuColle(unittest.TestCase):

    def test_ins_dans_cousins_est_colle(self):
        self.assertTrue(M.lieu_colle_dans_un_mot(
            r'\\NAS\home\Photos\2007\Cousins&Cousines\DSC1.jpg', 'Ins'))

    def test_un_dossier_entier_nest_pas_colle(self):
        self.assertFalse(M.lieu_colle_dans_un_mot(
            r'\\NAS\home\Photos\2007\Ins\DSC1.jpg', 'Ins'))

    def test_un_chiffre_borne_le_mot(self):
        self.assertFalse(M.lieu_colle_dans_un_mot(
            r'\\NAS\home\Photos\Achumani2001\DSC1.jpg', 'Achumani'))

    def test_lieu_vide(self):
        self.assertFalse(M.lieu_colle_dans_un_mot(r'C:\x\y.jpg', None))


class TestGardeFou(unittest.TestCase):

    def test_refuse_photos_db(self):
        with self.assertRaises(SystemExit):
            M.ouvrir('photos.db')
        with self.assertRaises(SystemExit):
            M.ouvrir(r'C:\Prog\Claude\MediaLibrary\PHOTOS.DB')


if __name__ == '__main__':
    unittest.main(verbosity=2)
