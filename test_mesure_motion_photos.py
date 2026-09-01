#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le compte des Motion Photos dit-il vrai ? (mesure_motion_photos)

Tout est synthetique : aucun NAS, jamais photos.db. Chaque test verrouille un
comportement precis — une mutation de la detection ou du calcul de taille doit
faire rougir au moins un test.
"""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import mesure_motion_photos as M

STILL = b'\xff\xd8\xff\xe0' + b'\x12' * 400 + b'\xff\xd9'
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'V' * 3000


def xmp(morceau):
    """Un APP1 plausible portant `morceau` de XMP, glisse dans le still."""
    return STILL[:4] + b'<x:xmpmeta ' + morceau + b'/>' + STILL[4:]


class Detection(unittest.TestCase):
    def test_rien(self):
        genre, v = M.detecter(STILL, STILL)
        self.assertIsNone(genre)
        self.assertIsNone(v)

    def test_samsung_par_la_queue(self):
        genre, _ = M.detecter(STILL, MP4 + b'SEFT')
        self.assertEqual(genre, 'samsung')

    def test_google_attribut_et_element(self):
        for forme in (b'GCamera:MotionPhoto="1"', b'MicroVideo=\'1\'',
                      b'<GCamera:MotionPhoto>1</GCamera:MotionPhoto>'):
            genre, _ = M.detecter(xmp(forme), STILL)
            self.assertEqual(genre, 'google', forme)

    def test_motionphoto_zero_ne_compte_pas(self):
        genre, _ = M.detecter(xmp(b'GCamera:MotionPhoto="0"'), STILL)
        self.assertIsNone(genre)

    def test_les_deux(self):
        genre, _ = M.detecter(xmp(b'MicroVideo="1"'), b'xSEFT')
        self.assertEqual(genre, 'les-deux')


class TailleXmp(unittest.TestCase):
    def test_v1_microvideooffset(self):
        self.assertEqual(M.taille_video_xmp(xmp(b'MicroVideoOffset="123456"')), 123456)

    def test_v2_item_length_du_video(self):
        t = xmp(b'Item:Mime="image/jpeg" Item:Length="0" '
                b'Item:Mime="video/mp4" Item:Length="2222"')
        self.assertEqual(M.taille_video_xmp(t), 2222)

    def test_length_du_still_jamais(self):
        t = xmp(b'Item:Mime="image/jpeg" Item:Length="777"')
        self.assertIsNone(M.taille_video_xmp(t))


class TailleFenetre(unittest.TestCase):
    def test_trailer_depuis_le_ffd9(self):
        data = STILL + MP4
        v = M.taille_video_fenetre(data, 0, len(data))
        self.assertEqual(v, len(MP4))

    def test_fenetre_partielle_offsets_justes(self):
        data = STILL + MP4
        base = len(STILL) - 10  # la fenetre commence AVANT la fin du still
        v = M.taille_video_fenetre(data[base:], base, len(data))
        self.assertEqual(v, len(MP4))

    def test_sans_ftyp_rien(self):
        self.assertIsNone(M.taille_video_fenetre(STILL, 0, len(STILL)))

    def test_faux_ftyp_dans_l_entropie_ignore(self):
        faux = b'\xff\xd8' + b'\x00\x01ftyp\xff\xfe' + b'\x33' * 500 + b'\xff\xd9'
        self.assertIsNone(M.taille_video_fenetre(faux, 0, len(faux)))

    def test_faux_ftyp_puis_vrai_mp4(self):
        mixte = STILL[:4] + b'\x00\x01ftyp\xff\xfe' + STILL[4:] + MP4
        self.assertEqual(M.taille_video_fenetre(mixte, 0, len(mixte)), len(MP4))


class Sonde(unittest.TestCase):
    def _fichier(self, octets):
        d = Path(self._tmp.name)
        p = d / 'photo.jpg'
        p.write_bytes(octets)
        return p

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_samsung_taille_par_fenetre(self):
        sef = MP4 + b'\x00' * 40 + b'SEFT'
        ent = M.sonder(self._fichier(STILL + sef), 1 << 20)
        self.assertEqual(ent['g'], 'samsung')
        self.assertEqual(ent['v'], len(sef))
        self.assertEqual(ent['me'], 'fenetre')

    def test_google_taille_par_xmp(self):
        corps = xmp(b'MicroVideo="1" MicroVideoOffset="3016"')
        ent = M.sonder(self._fichier(corps + MP4), 1 << 20)
        self.assertEqual(ent['g'], 'google')
        self.assertEqual((ent['v'], ent['me']), (3016, 'xmp'))

    def test_jpeg_ordinaire(self):
        ent = M.sonder(self._fichier(STILL), 1 << 20)
        self.assertIsNone(ent['g'])
        self.assertNotIn('v', ent)
        self.assertNotIn('s', ent)

    def test_sef_annuaire_sans_video_ne_lit_pas_plus(self):
        # SEFH present, pas de MotionPhoto_Data : conclu sans fenetre
        sef = b'SEFH' + b'Image_UTC_Data' + b'\x00' * 40 + b'SEFT'
        ent = M.sonder(self._fichier(STILL + sef), 1 << 20)
        self.assertEqual(ent['g'], 'samsung')
        self.assertNotIn('v', ent)

    def test_sef_annuaire_avec_video_est_mesure(self):
        sef = MP4 + b'SEFH' + b'MotionPhoto_Data' + b'\x00' * 40 + b'SEFT'
        ent = M.sonder(self._fichier(STILL + sef), 1 << 20)
        self.assertEqual(ent['g'], 'samsung')
        self.assertEqual(ent['v'], len(sef))

    def test_suspect_dit(self):
        ent = M.sonder(self._fichier(STILL + MP4), 1 << 20)  # ftyp, aucun marqueur
        self.assertIsNone(ent['g'])
        self.assertEqual(ent.get('s'), 1)


class Candidats(unittest.TestCase):
    def test_filtre_et_refus(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'copie.db'
            cx = sqlite3.connect(db)
            cx.execute('CREATE TABLE tags (k TEXT PRIMARY KEY, v TEXT)')
            lignes = [(r'N:\Photos\Photos Mike\2024\a.jpg', '{}'),
                      (r'N:\Photos\Photos Mike\2024\b.JPEG', '{}'),
                      (r'N:\Photos\Photos Mike\2024\c.mp4', '{}'),
                      (r'N:\Photos\.corbeille-rangement\d.jpg', '{}')]
            cx.executemany('INSERT INTO tags VALUES (?, ?)', lignes)
            cx.commit()
            cx.close()
            cles = M.charger_cles(str(db))
            self.assertEqual(len(cles), 2)
            self.assertTrue(all(c.lower().endswith(('.jpg', '.jpeg')) for c in cles))

    def test_photosdb_refuse(self):
        with self.assertRaises(SystemExit):
            M.charger_cles('photos.db')


class Divers(unittest.TestCase):
    def test_annee_depuis_le_chemin(self):
        self.assertEqual(M.annee_de(r'N:\Photos\Photos Flo\2022\x.jpg'), '2022')
        self.assertEqual(M.annee_de(r'N:\Photos\Photos Flo\divers\x.jpg'), '????')

    def test_annee_depuis_le_nom(self):
        self.assertEqual(M.annee_de(r'N:\Photos\Photos Flo\d\2017-07-24 13.04.03.jpg'), '2017')

    def test_sef_sans_video_n_est_pas_motion(self):
        self.assertEqual(M.genre_effectif({'g': 'samsung'}), 'sef-sans-video')
        self.assertEqual(M.genre_effectif({'g': 'samsung', 'v': 100}), 'samsung')
        self.assertEqual(M.genre_effectif({'g': 'google'}), 'google')
        self.assertIsNone(M.genre_effectif({'g': None}))


if __name__ == '__main__':
    unittest.main()
