#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests d'`appliquer_menage.py` -- sur un arbre jouet, jamais le vrai depot.

Ce que ces tests protegent : le VETO. La politique nomme des motifs ; c'est
l'inventaire qui autorise. Le jour ou le veto cesse de mordre, ce script
efface un fichier que du code lit -- exactement la panne du 08/09 avec
`_google.json` et le bat 32.

Lance : python test_appliquer_menage.py
"""

import json
import os
import shutil
import time
import sys
import tempfile
import unittest
from pathlib import Path

import appliquer_menage as M


class LeVetoDeLInventaire(unittest.TestCase):
    """La politique propose, l'inventaire dispose."""

    def setUp(self):
        self.vrai = M.inventaire_frais
        self.d = Path(tempfile.mkdtemp(prefix='menage_'))
        self.racine = M.RACINE

    def tearDown(self):
        M.inventaire_frais = self.vrai
        M.RACINE = self.racine
        shutil.rmtree(self.d, ignore_errors=True)

    def _monde(self, fichiers, familles):
        M.RACINE = self.d
        for rel in fichiers:
            p = self.d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('x' * 50, encoding='utf-8')
        M.inventaire_frais = lambda: (familles, None)

    def test_un_fichier_LU_PAR_DU_CODE_ne_part_PAS(self):
        # Le cas `_google.json` : la politique le nomme, un bat le lit.
        self._monde(['_rapport_sef_avant.json'],
                    {'_rapport_sef_avant.json': 'LU PAR DU CODE'})
        bouge, retenus, err = M.trier()
        self.assertIsNone(err)
        self.assertEqual(bouge, [])
        self.assertEqual(retenus[0][0], '_rapport_sef_avant.json')
        self.assertIn('LU PAR DU CODE', retenus[0][1])

    def test_un_fichier_ORPHELIN_part(self):
        self._monde(['_rapport_sef_avant.json'],
                    {'_rapport_sef_avant.json': 'ORPHELIN'})
        bouge, _r, _e = M.trier()
        self.assertEqual([b['fichier'] for b in bouge],
                         ['_rapport_sef_avant.json'])

    def test_un_fichier_que_l_inventaire_n_a_PAS_VU_est_retenu(self):
        # Ne pas savoir n'est pas savoir que non.
        self._monde(['_rapport_sef_avant.json'], {})
        bouge, retenus, _e = M.trier()
        self.assertEqual(bouge, [])
        self.assertIn('non vu', retenus[0][1])

    def test_un_journal_LU_PAR_UN_MOTIF_part_quand_l_age_le_dit(self):
        """L'etape 3 du bat 50 promettait un choix qu'elle ne pouvait tenir.

        Mesure du 09/09 : Mike repond « 2 » et lit « Rien a deplacer ».
        35 des 44 journaux sont `LU PAR UN MOTIF` -- forcement, `undo_*.json`
        EST le motif. Ici le jugement vient de l'AGE, que Mike fournit et qui
        est plus fort."""
        self._monde(['docs/undo_annee_20260101_000000.json'],
                    {'docs/undo_annee_20260101_000000.json': 'LU PAR UN MOTIF'})
        vieux = time.time() - 200 * 86400
        os.utime(self.d / 'docs/undo_annee_20260101_000000.json',
                 (vieux, vieux))
        bouge, _r, _e = M.trier(avec_journaux=30)
        self.assertEqual([b['fichier'] for b in bouge],
                         ['docs/undo_annee_20260101_000000.json'])

    def test_un_journal_LU_PAR_DU_CODE_reste_meme_vieux(self):
        """`docs/plan_rangement.json` est nomme en clair par les bats 26 et
        39 : ce n'est pas un journal perime, c'est une entree vivante."""
        self._monde(['docs/plan_rangement.json'],
                    {'docs/plan_rangement.json': 'LU PAR DU CODE'})
        vieux = time.time() - 200 * 86400
        os.utime(self.d / 'docs/plan_rangement.json', (vieux, vieux))
        bouge, retenus, _e = M.trier(avec_journaux=30)
        self.assertEqual(bouge, [])
        self.assertIn('LU PAR DU CODE', retenus[0][1])

    def test_un_motif_hors_journaux_reste_vetote(self):
        """L'exception est NOMMEE : elle ne vaut que pour les journaux."""
        self._monde(['_to_delete/x.jsonl'],
                    {'_to_delete/x.jsonl': 'LU PAR UN MOTIF'})
        bouge, retenus, _e = M.trier()
        self.assertEqual(bouge, [])
        self.assertIn('LU PAR UN MOTIF', retenus[0][1])

    def test_LU_PAR_CONVENTION_est_retenu_aussi(self):
        # Un .bat, un test : personne ne les cite, tout le monde s'en sert.
        self._monde(['ui/pages/faces.html'],
                    {'ui/pages/faces.html': 'LU PAR CONVENTION'})
        bouge, retenus, _e = M.trier()
        self.assertEqual(bouge, [])
        self.assertIn('CONVENTION', retenus[0][1])

    def test_l_inventaire_en_panne_ARRETE_tout(self):
        M.RACINE = self.d
        M.inventaire_frais = lambda: (None, 'casse')
        bouge, retenus, err = M.trier()
        self.assertEqual((bouge, retenus), ([], []))
        self.assertEqual(err, 'casse')


class LesJournauxSontHorsPolitique(unittest.TestCase):
    def setUp(self):
        self.vrai, self.racine = M.inventaire_frais, M.RACINE
        self.d = Path(tempfile.mkdtemp(prefix='menage_j_'))
        M.RACINE = self.d
        p = self.d / 'docs' / 'undo_annee_20260101_000000.json'
        p.parent.mkdir(parents=True)
        p.write_text('x', encoding='utf-8')
        # VIEUX pour de vrai : le premier jet ecrivait le fichier a l'instant
        # puis attendait qu'un seuil d'UN JOUR l'attrape. Le test etait faux,
        # pas le code -- l'age se lit sur le disque, il ne se souhaite pas.
        import os
        vieux = time.time() - 400 * 86400
        os.utime(p, (vieux, vieux))
        M.inventaire_frais = lambda: (
            {'docs/undo_annee_20260101_000000.json': 'ORPHELIN'}, None)

    def tearDown(self):
        M.inventaire_frais, M.RACINE = self.vrai, self.racine
        shutil.rmtree(self.d, ignore_errors=True)

    def test_par_defaut_on_n_y_touche_PAS(self):
        # 88 des 89 sont gitignores : c'est la seule chose de la liste qu'on
        # ne peut pas recuperer.
        bouge, _r, _e = M.trier()
        self.assertEqual(bouge, [])

    def test_il_faut_les_demander_avec_un_AGE(self):
        bouge, _r, _e = M.trier(avec_journaux=1)
        self.assertEqual(len(bouge), 1)

    def test_un_journal_TROP_RECENT_reste(self):
        bouge, retenus, _e = M.trier(avec_journaux=36500)
        self.assertEqual(bouge, [])
        self.assertIn('trop recent', retenus[0][1])


class RienNEstEfface(unittest.TestCase):
    def setUp(self):
        self.vrai, self.racine = M.inventaire_frais, M.RACINE
        self.d = Path(tempfile.mkdtemp(prefix='menage_u_'))
        M.RACINE = self.d
        M.CORBEILLE = self.d / '_corbeille_menage'
        (self.d / '_rapport_sef_avant.json').write_text('bonjour',
                                                        encoding='utf-8')
        M.inventaire_frais = lambda: (
            {'_rapport_sef_avant.json': 'ORPHELIN'}, None)

    def tearDown(self):
        M.inventaire_frais, M.RACINE = self.vrai, self.racine
        shutil.rmtree(self.d, ignore_errors=True)

    def test_deplace_puis_ANNULE_remet_tout(self):
        bouge, _r, _e = M.trier()
        dest = M.CORBEILLE / 'essai'
        faits, ratees, manif = M.deplacer(bouge, dest)
        self.assertEqual(faits, ['_rapport_sef_avant.json'])
        self.assertEqual(ratees, [])
        self.assertFalse((self.d / '_rapport_sef_avant.json').exists())
        self.assertTrue(manif.is_file())
        self.assertEqual(M.annuler(dest), 0)
        self.assertEqual((self.d / '_rapport_sef_avant.json')
                         .read_text(encoding='utf-8'), 'bonjour')

    def test_annuler_ne_LOGE_PAS_par_dessus_un_fichier_revenu(self):
        # Si quelque chose a repris la place, on le dit au lieu d'ecraser.
        bouge, _r, _e = M.trier()
        dest = M.CORBEILLE / 'essai2'
        M.deplacer(bouge, dest)
        (self.d / '_rapport_sef_avant.json').write_text('AUTRE',
                                                        encoding='utf-8')
        self.assertEqual(M.annuler(dest), 1)
        self.assertEqual((self.d / '_rapport_sef_avant.json')
                         .read_text(encoding='utf-8'), 'AUTRE')

    def test_annuler_sans_manifeste_rend_2(self):
        self.assertEqual(M.annuler(self.d / 'nexistepas'), 2)


if __name__ == '__main__':
    unittest.main(verbosity=0)
