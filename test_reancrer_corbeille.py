#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bancs de `reancrer_corbeille.py`, sur un arbre jouet (aucun NAS).

Ce qui est verifie tient en une phrase : on ne reancre QUE sur preuve
d'empreinte, et tout ce qu'on ecrit se defait.
"""

import hashlib
import json
import sqlite3
import shutil
import tempfile
import unittest
from pathlib import Path

import reancrer_corbeille as R


def h(octets):
    return hashlib.sha256(octets).hexdigest()


class Arbre(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='reancre_'))
        self.fonds = self.tmp / 'fonds'
        self.corb = self.tmp / 'corbeille'
        (self.fonds / '2019').mkdir(parents=True)
        self.corb.mkdir()
        self.db = self.tmp / 'photos.db'
        R.DOSSIER_JOURNAL = self.tmp / 'journaux'

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def poser_index(self, cles):
        cx = sqlite3.connect(self.db)
        cx.execute('CREATE TABLE tags (k TEXT PRIMARY KEY, v TEXT NOT NULL)')
        cx.executemany('INSERT INTO tags(k,v) VALUES(?,?)',
                       [(c, '{}') for c in cles])
        cx.commit()
        cx.close()

    def poser_groupe(self, nom, canon_note, sha, contenu=b'copie'):
        g = self.corb / nom
        g.mkdir()
        (g / 'doublon.jpg').write_bytes(contenu)
        (g / 'manifeste.json').write_text(json.dumps({
            'canonique': canon_note, 'sha256': sha, 'groupe': nom,
            'date_application': '2026-01-01 00:00:00', 'origine': 'test'}),
            encoding='utf-8')
        return g


class TestReancrage(Arbre):
    def lancer(self, *args):
        """Le script lit la corbeille du plan et photos.db a cote de lui."""
        (self.tmp / 'docs').mkdir(exist_ok=True)
        (self.tmp / 'docs' / 'plan_rangement.json').write_text(
            json.dumps({'corbeille': str(self.corb)}), encoding='utf-8')
        vrai_racine = R.RACINE
        R.RACINE = self.tmp
        try:
            return R.main(list(args))
        finally:
            R.RACINE = vrai_racine

    def test_reancre_quand_l_empreinte_correspond(self):
        vraie = self.fonds / '2019' / 'IMG_1.JPG'
        vraie.write_bytes(b'la vraie photo')
        self.poser_groupe('g1', str(self.tmp / 'ailleurs' / 'IMG_1.JPG'),
                          h(b'la vraie photo'))
        self.poser_index([str(vraie)])
        self.assertEqual(self.lancer('--appliquer'), 0)
        mani = json.loads((self.corb / 'g1' / 'manifeste.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(mani['canonique'], str(vraie))
        self.assertIn('canonique_avant', mani)

    def test_refuse_quand_le_nom_est_pris_par_une_autre_photo(self):
        """Le coeur du banc : 3 cas sur 40 mesures etaient dans ce cas."""
        autre = self.fonds / '2019' / 'IMG_1.JPG'
        autre.write_bytes(b'une AUTRE photo, meme nom')
        note = str(self.tmp / 'ailleurs' / 'IMG_1.JPG')
        self.poser_groupe('g1', note, h(b'la vraie photo'))
        self.poser_index([str(autre)])
        self.lancer('--appliquer')
        mani = json.loads((self.corb / 'g1' / 'manifeste.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(mani['canonique'], note)
        self.assertNotIn('canonique_avant', mani)

    def test_apercu_n_ecrit_rien(self):
        vraie = self.fonds / '2019' / 'IMG_1.JPG'
        vraie.write_bytes(b'la vraie photo')
        note = str(self.tmp / 'ailleurs' / 'IMG_1.JPG')
        self.poser_groupe('g1', note, h(b'la vraie photo'))
        self.poser_index([str(vraie)])
        self.assertEqual(self.lancer(), 0)
        mani = json.loads((self.corb / 'g1' / 'manifeste.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(mani['canonique'], note)

    def test_ne_touche_pas_un_groupe_deja_en_place(self):
        vraie = self.fonds / '2019' / 'IMG_1.JPG'
        vraie.write_bytes(b'la vraie photo')
        self.poser_groupe('g1', str(vraie), h(b'la vraie photo'))
        self.poser_index([str(vraie)])
        self.lancer('--appliquer')
        mani = json.loads((self.corb / 'g1' / 'manifeste.json')
                          .read_text(encoding='utf-8'))
        self.assertNotIn('canonique_avant', mani)

    def test_annuler_remet_le_chemin_d_origine(self):
        vraie = self.fonds / '2019' / 'IMG_1.JPG'
        vraie.write_bytes(b'la vraie photo')
        note = str(self.tmp / 'ailleurs' / 'IMG_1.JPG')
        self.poser_groupe('g1', note, h(b'la vraie photo'))
        self.poser_index([str(vraie)])
        self.lancer('--appliquer')
        journal = R.DERNIER_JOURNAL
        self.assertTrue(journal and Path(journal).exists())
        self.assertEqual(R.annuler(journal), 0)
        mani = json.loads((self.corb / 'g1' / 'manifeste.json')
                          .read_text(encoding='utf-8'))
        self.assertEqual(mani['canonique'], note)
        self.assertNotIn('canonique_avant', mani)
        self.assertNotIn('reancre_le', mani)

    def test_deux_journaux_dans_la_meme_seconde_ne_s_ecrasent_pas(self):
        R.DOSSIER_JOURNAL.mkdir(parents=True, exist_ok=True)
        a = R.nouveau_journal()
        a.write_text('{}', encoding='utf-8')
        b = R.nouveau_journal()
        self.assertNotEqual(a, b)

    def test_index_vide_refuse_de_conclure(self):
        self.poser_groupe('g1', str(self.tmp / 'x.jpg'), h(b'x'))
        self.poser_index([])
        self.assertEqual(self.lancer('--appliquer'), 1)

    def test_manifeste_sans_sha256_est_garde(self):
        vraie = self.fonds / '2019' / 'IMG_1.JPG'
        vraie.write_bytes(b'la vraie photo')
        note = str(self.tmp / 'ailleurs' / 'IMG_1.JPG')
        g = self.poser_groupe('g1', note, None)
        self.poser_index([str(vraie)])
        self.lancer('--appliquer')
        mani = json.loads((g / 'manifeste.json').read_text(encoding='utf-8'))
        self.assertEqual(mani['canonique'], note)

    def test_le_fichier_quarantine_n_est_jamais_touche(self):
        """Cet outil ne supprime rien : c'est sa promesse la plus importante."""
        vraie = self.fonds / '2019' / 'IMG_1.JPG'
        vraie.write_bytes(b'la vraie photo')
        g = self.poser_groupe('g1', str(self.tmp / 'ailleurs' / 'IMG_1.JPG'),
                              h(b'la vraie photo'), contenu=b'la copie')
        self.poser_index([str(vraie)])
        self.lancer('--appliquer')
        self.assertEqual((g / 'doublon.jpg').read_bytes(), b'la copie')


if __name__ == '__main__':
    unittest.main(verbosity=2)
