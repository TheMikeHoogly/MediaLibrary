#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la mesure du tri de recherche — purs, sur une base SYNTHETIQUE.

Aucune photo, aucun NAS, aucun serveur : la base de test est fabriquee ici.
Le module mesure ; ces tests verifient qu'il mesure ce qu'il annonce, y compris
la panne qu'il est cense mettre au jour.
"""
import json
import os
import sqlite3
import tempfile
import time
import unittest

import mesure_tri_recherche as m


def _epoch(an, mois=1, jour=1, h=12):
    return time.mktime((an, mois, jour, h, 0, 0, 0, 0, -1))


P = "\\\\NAS\\home\\Photos"


class TestRangs(unittest.TestCase):

    def test_taken_donne_precis(self):
        self.assertEqual(m.rang_de(P + "\\x.jpg", {"taken": _epoch(2015)}),
                         'precis')

    def test_date_dans_le_nom_donne_precis_sans_taken(self):
        self.assertEqual(m.rang_de(P + "\\20150704_120000_a.jpg", {}), 'precis')

    def test_yyyy0000_nest_pas_une_date_precise(self):
        """Le repli du renommage : mois 00 -> aucune date lisible dans le nom.
        C'est pour cela que 376 photos attendent encore une date."""
        self.assertIsNone(m.epoch_du_nom(P + "\\20060000_Mike.jpg"))

    def test_annee_du_dossier_seule(self):
        self.assertEqual(m.rang_de(P + "\\2006\\brut.jpg", {}), 'annee_dossier')

    def test_le_nom_de_fichier_ne_fait_pas_une_annee_de_dossier(self):
        """« 119-1908_IMG.JPG » : un numero de sequence n'est pas une annee
        (correctif du 14/08, 38 photos reculees de 94 ans)."""
        self.assertEqual(m.annee_dossier("\\\\NAS\\z\\119-1908_IMG.JPG"), 0)

    def test_sans_date_sure_mais_avec_mtime(self):
        self.assertEqual(m.rang_de("\\\\NAS\\_Uploads\\brut.jpg",
                                   {"mtime": _epoch(2026, 8, 19)}), 'mtime')

    def test_sans_rien_du_tout(self):
        self.assertEqual(m.rang_de("\\\\NAS\\_Uploads\\brut.jpg", {}), 'aucune')


class TestAncienTri(unittest.TestCase):

    def test_le_mtime_place_la_photo_muette_EN_TETE(self):
        """Le defaut, reproduit : 2026 (date de tagging) bat 2015 (vraie date)."""
        items = [(P + "\\a.jpg", {"taken": _epoch(2015, 12, 25)}),
                 ("\\\\NAS\\_Uploads\\muette.jpg", {"mtime": _epoch(2026, 8, 19)})]
        cles, plantage = m.trier_avant(items)
        self.assertIsNone(plantage)
        self.assertEqual(cles[0][0], "\\\\NAS\\_Uploads\\muette.jpg")

    def test_le_melange_float_chaine_fait_tomber_lancien_tri(self):
        """`_best_time(...) or ''` : une seule photo sans rien suffit."""
        items = [(P + "\\a.jpg", {"taken": _epoch(2015)}),
                 ("\\\\NAS\\_Uploads\\rien.jpg", {})]
        cles, plantage = m.trier_avant(items)
        self.assertIsNone(cles)
        self.assertIn('not supported', plantage)


class TestMesureSurBase(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.copie = os.path.join(self.dir, 'copie.db')
        cx = sqlite3.connect(self.copie)
        cx.execute('CREATE TABLE "tags" (k TEXT PRIMARY KEY, v TEXT NOT NULL)')
        lignes = [
            (P + "\\2015\\a.jpg", {"taken": _epoch(2015, 12, 25)}),
            (P + "\\2018\\c.jpg", {"taken": _epoch(2018, 7, 4)}),
            (P + "\\2006\\brut.jpg", {}),                       # annee dossier
            ("\\\\NAS\\_Uploads\\muette.jpg", {"mtime": _epoch(2026, 8, 19)}),
            ("\\\\NAS\\_Uploads\\rien.jpg", {}),
        ]
        for k, e in lignes:
            cx.execute('INSERT INTO "tags"(k,v) VALUES(?,?)',
                       (k, json.dumps(e)))
        cx.commit()
        cx.close()

    def test_refuse_photos_db(self):
        with self.assertRaises(SystemExit):
            m.charger(os.path.join(self.dir, 'photos.db'))

    def test_comptes_et_avant_apres(self):
        rap = m.mesurer(m.charger(self.copie), tete=2)
        self.assertEqual(rap['total'], 5)
        self.assertEqual(rap['rangs'],
                         {'precis': 2, 'annee_dossier': 1,
                          'mtime': 1, 'aucune': 1})
        self.assertEqual(rap['annees_mtime'], {2026: 1})
        # L'ancien tri ne peut meme pas s'executer sur ce corpus : c'est le
        # resultat, pas un echec du test.
        self.assertIsNotNone(rap['plantage_ancien_tri'])
        self.assertIsNone(rap['muettes_en_tete_avant'],
                          "l'ancien tri ne s'execute pas : « non mesurable », "
                          "surtout pas 0")
        self.assertEqual(rap['muettes_en_tete_apres'], 0,
                         "les muettes vont en FIN de liste")
        self.assertEqual(rap['sans_date_compte_par_le_nouveau_tri'], 2)

    def test_par_nom_ne_voit_que_les_vrais_noms(self):
        items = [("\\\\NAS\\a.jpg", {"kw_fr": ["personne:Flo", "chien"]}),
                 ("\\\\NAS\\b.jpg", {"kw_en": ["ANIMAL:Luna"]}),
                 ("\\\\NAS\\c.jpg", {"kw_fr": ["plage"]})]
        d = m.par_nom(items)
        self.assertEqual(set(d), {"personne:flo", "animal:luna"})

    def test_par_nom_signale_la_requete_qui_plante(self):
        """Un nom porte par une photo sans aucune date ET par une photo datee :
        c'est exactement le melange qui faisait tomber `sorted`."""
        items = [(P + "\\2015\\a.jpg",
                  {"taken": _epoch(2015), "kw_fr": ["personne:Flo"]}),
                 ("\\\\NAS\\_Uploads\\rien.jpg",
                  {"kw_fr": ["personne:Flo"]})]
        self.assertTrue(m.par_nom(items)["personne:flo"]["plante"])

    def test_le_nouveau_tri_range_les_muettes_en_dernier(self):
        items = m.charger(self.copie)
        cles, _ = m.recherche.trier_chronologique(
            items, m.epoch_precis,
            m.recherche.annee_fiable_depuis(m.epoch_precis, m.annee_dossier))
        self.assertEqual(cles[0], P + "\\2018\\c.jpg")
        self.assertEqual(set(cles[-2:]), {"\\\\NAS\\_Uploads\\muette.jpg",
                                          "\\\\NAS\\_Uploads\\rien.jpg"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
