#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_repasse.py` — les MIROIRS avant tout.

Le script rejoue hors serveur trois fonctions de `server.py` (`_lieu_pour_cle`,
la branche date de `_assertions_pour`, `_noms_attendus`). Un miroir qui dérive
rend un chiffre faux avec l'aplomb d'un vrai : ces tests fixent les pièges déjà
payés une fois par le projet — l'hôte NAS pris pour un lieu, la date du scanner
prise pour une prise de vue, un `exclude` ignoré.

Aucun accès à photos.db, aucun réseau : logique pure.
"""
import time
import unittest

import mesure_repasse as M


class TestLieu(unittest.TestCase):
    LIEUX = {'bremblens': 'Bremblens', 'morges': 'Morges',
             'indonesie': 'Indonésie'}

    def test_hote_nas_nest_pas_un_lieu(self):
        """Le piège documenté : « \\\\NAS-Bremblens\\home\\… » ne doit PAS livrer
        « Bremblens », sinon le lieu colle à toute la photothèque."""
        cle = r'\\NAS-Bremblens\home\Photos\2005\Vacances\IMG_1.JPG'
        self.assertEqual(M.lieu_pour_cle(cle, self.LIEUX, {}), (None, None))

    def test_dossier_porte_le_lieu(self):
        cle = r'\\NAS-Bremblens\home\Photos\2005\2005-06-19 Flo Morges\P1.JPG'
        self.assertEqual(M.lieu_pour_cle(cle, self.LIEUX, {}), ('Morges', 'chemin'))

    def test_nom_de_fichier_ignore(self):
        """Le lieu se lit dans les DOSSIERS, jamais dans le nom du fichier."""
        cle = r'\\NAS-Bremblens\home\Photos\2005\Divers\Morges.JPG'
        self.assertEqual(M.lieu_pour_cle(cle, self.LIEUX, {}), (None, None))

    def test_geocodage_precalcule_prioritaire(self):
        cle = r'\\NAS-Bremblens\home\Photos\2005\2005 Morges\P1.JPG'
        gps = {cle: 'Lausanne'}
        self.assertEqual(M.lieu_pour_cle(cle, self.LIEUX, gps), ('Lausanne', 'gps'))


class TestDate(unittest.TestCase):

    def test_exif_prioritaire(self):
        ep = time.mktime((2018, 12, 11, 23, 1, 48, 0, 0, -1))
        txt, src = M.date_pour_cle(r'D:\Photos\2005\IMG_20200101.JPG', {'taken': ep})
        self.assertEqual((txt, src), ('11 decembre 2018', 'exif'))

    def test_nom_de_fichier_ensuite(self):
        txt, src = M.date_pour_cle(r'D:\Photos\2005\IMG_20181227.JPG', {})
        self.assertEqual((txt, src), ('27 decembre 2018', 'nom du fichier'))

    def test_annee_du_dossier_en_dernier(self):
        txt, src = M.date_pour_cle(r'D:\Photos\1985\119-1908_IMG.JPG', {})
        self.assertEqual((txt, src), ('1985', 'annee du dossier'))

    def test_numero_de_scanner_nest_pas_une_annee(self):
        """« 119-1908_IMG.JPG » dans un dossier 2002 : 1908 est un numéro de
        séquence. Le nom de fichier est exclu de la lecture des années."""
        txt, src = M.date_pour_cle(r'D:\Photos\2002\119-1908_IMG.JPG', {})
        self.assertEqual((txt, src), ('2002', 'annee du dossier'))

    def test_aucune_date(self):
        self.assertEqual(M.date_pour_cle(r'D:\Photos\Divers\IMG.JPG', {}),
                         (None, None))


class TestNoms(unittest.TestCase):
    PEOPLE = {'p1': {'name': 'Flo', 'faces': [['k1', 0], ['k2', 1]]},
              'p2': {'name': 'Val', 'faces': [['k1', 1]], 'exclude': ['k2']}}
    PETS = {'a1': {'name': 'Mutz', 'faces': [['k2', 0]]}}

    def test_fiches_donnent_les_noms(self):
        tags, _ = M.noms_attendus('k1', {}, self.PEOPLE, self.PETS)
        self.assertEqual(sorted(tags), ['personne:Flo', 'personne:Val'])

    def test_exclude_fait_autorite(self):
        """« Val » est exclue de k2 : ni la fiche ni un mot-clé résiduel ne
        doivent la ressusciter."""
        entry = {'kw_fr': ['chat', 'personne:Val']}
        tags, exclus = M.noms_attendus('k2', entry, self.PEOPLE, self.PETS)
        self.assertIn('personne:val', exclus)
        self.assertNotIn('personne:Val', tags)
        self.assertIn('personne:Flo', tags)
        self.assertIn('animal:Mutz', tags)

    def test_mots_cles_de_lentree_comptent(self):
        entry = {'kw_fr': ['personne:Papa']}
        tags, _ = M.noms_attendus('inconnue', entry, self.PEOPLE, self.PETS)
        self.assertEqual(tags, ['personne:Papa'])


class TestMesure(unittest.TestCase):
    CTX = {'people': {}, 'pets': {}, 'animals': {}, 'lieux': {}, 'gps_places': {}}

    def test_entree_v0_compte_comme_v0(self):
        tags = {r'D:\Photos\2005\a.jpg': {'kw_fr': ['chat'], 'at': 1.0}}
        st = M.mesurer(tags, self.CTX)
        self.assertEqual(st['pipe'], {'v0': 1})
        self.assertEqual(st['taguees'], 1)

    def test_echec_exclu_du_denominateur(self):
        tags = {'a': {'failed': True}, r'D:\Photos\2005\b.jpg': {'at': 1.0}}
        st = M.mesurer(tags, self.CTX)
        self.assertEqual((st['echecs'], st['taguees']), (1, 1))

    def test_fait_deja_enregistre_nest_pas_un_gain(self):
        """Une entrée déjà taguée AVEC ses faits ne gagne rien : c'est ce qui
        empêche la mesure de compter deux fois le même acquis."""
        ep = time.mktime((2018, 12, 11, 12, 0, 0, 0, 0, -1))
        tags = {r'D:\Photos\2018\a.jpg': {
            'pipe': 'qwen3-vl:2b|v2ctx|kb1', 'taken': ep, 'at': 1.0,
            'faits': [{'t': 'date', 'v': '11 decembre 2018', 'src': 'exif'}]}}
        st = M.mesurer(tags, self.CTX)
        self.assertEqual(st['entrees_gain'], 0)
        self.assertEqual(st['gagnes']['date'], 0)

    def test_date_changee_est_comptee_a_part(self):
        """Le plancher des années corrigé le 14/08 a DÉPLACÉ des dates : un fait
        qui change de valeur n'est pas un fait gagné, et se compte à part."""
        ep = time.mktime((1985, 6, 1, 12, 0, 0, 0, 0, -1))
        tags = {r'D:\Photos\1985\a.jpg': {
            'pipe': 'kb1', 'taken': ep, 'at': 1.0,
            'faits': [{'t': 'date', 'v': '3 avril 2026', 'src': 'exif'}]}}
        st = M.mesurer(tags, self.CTX)
        self.assertEqual(st['changes']['date'], 1)
        self.assertEqual(st['gagnes']['date'], 1)   # la nouvelle valeur est neuve
        self.assertEqual(st['entrees_gain'], 1)

    def test_strate_et_richesse_coherentes(self):
        ep = time.mktime((2018, 12, 11, 12, 0, 0, 0, 0, -1))
        ctx = dict(self.CTX, people={'p': {'name': 'Flo',
                                           'faces': [[r'D:\Photos\2018\a.jpg', 0]]}})
        tags = {r'D:\Photos\2018\a.jpg': {'taken': ep, 'at': 1.0}}
        st = M.mesurer(tags, ctx)
        self.assertEqual(st['strates'], {'nom': 1})
        self.assertEqual(st['richesse'], {2: 1})     # date + personne
        self.assertEqual(st['date_src'], {'exif': 1})

    def test_gps_sans_lieu_compte_le_potentiel_dormant(self):
        tags = {r'D:\Photos\Divers\a.jpg': {'gps': [46.5, 6.5], 'at': 1.0}}
        st = M.mesurer(tags, self.CTX)
        self.assertEqual(st['gps_sans_lieu'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
