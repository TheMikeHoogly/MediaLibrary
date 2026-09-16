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


class XmpResiduel(unittest.TestCase):
    """15/09 : le strip laisse le XMP. 454 fichiers annoncaient une video
    plus grosse que le fichier lui-meme."""

    def _f(self, d, data):
        p = Path(d) / 'x.jpg'
        p.write_bytes(data)
        return str(p)

    def test_video_annoncee_plus_grosse_que_le_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            corps = xmp(b'MicroVideo="1" MicroVideoOffset="4441609"')
            ent = M.sonder(self._f(d, corps), 1 << 20)
            self.assertEqual(ent['g'], 'xmp-residuel')
            self.assertNotIn('v', ent)
            self.assertEqual(ent.get('xr'), 1)
            self.assertEqual(M.genre_effectif(ent), 'xmp-residuel')

    def test_offset_plausible_mais_pas_de_ftyp(self):
        with tempfile.TemporaryDirectory() as d:
            corps = xmp(b'MotionPhoto="1" MicroVideoOffset="100"') + b'\x00' * 200
            ent = M.sonder(self._f(d, corps), 1 << 20)
            self.assertEqual(ent['g'], 'xmp-residuel')

    def test_vraie_video_verifiee(self):
        with tempfile.TemporaryDirectory() as d:
            corps = xmp(b'MicroVideo="1" MicroVideoOffset="3016"')
            ent = M.sonder(self._f(d, corps + MP4), 1 << 20)
            self.assertEqual((ent['g'], ent['v'], ent.get('xv')), ('google', 3016, 1))
            self.assertNotIn('xr', ent)

    def test_les_deux_residuel_devient_sef(self):
        with tempfile.TemporaryDirectory() as d:
            corps = xmp(b'MicroVideo="1" MicroVideoOffset="999999"') + b'SEFH' + b'SEFT'
            ent = M.sonder(self._f(d, corps), 1 << 20)
            self.assertEqual(M.genre_effectif(ent), 'sef-sans-video')

    def test_google_sans_offset_et_sans_boite(self):
        with tempfile.TemporaryDirectory() as d:
            ent = M.sonder(self._f(d, xmp(b'MotionPhoto="1"')), 1 << 20)
            self.assertEqual(ent['g'], 'xmp-residuel')

    def test_google_sans_offset_fichier_plus_grand_que_la_fenetre(self):
        with tempfile.TemporaryDirectory() as d:
            corps = xmp(b'MotionPhoto="1"') + b'\x00' * 5000
            ent = M.sonder(self._f(d, corps), 1024)
            self.assertEqual(ent['g'], 'google')  # inconnu : on ne conclut pas

    def test_cache_xmp_non_verifie_est_resonde(self):
        with tempfile.TemporaryDirectory() as d:
            ancien = M.RAPPORT
            M.RAPPORT = Path(d) / 'r.json'
            try:
                M.ecrire_cache({'a': {'t': 1, 'm': 1, 'g': 'google', 'v': 9, 'me': 'xmp'},
                                'b': {'t': 1, 'm': 1, 'g': 'google', 'v': 9, 'me': 'xmp', 'xv': 1},
                                'c': {'t': 1, 'm': 1, 'g': None},
                                'd': {'t': 1, 'm': 1, 'g': 'google'},
                                'e': {'t': 1, 'm': 1, 'g': 'xmp-residuel', 'xr': 1}}, {})
                self.assertEqual(set(M.charger_cache()), {'b', 'c', 'e'})
            finally:
                M.RAPPORT = ancien

    def test_le_strip_ne_prend_pas_les_residuels(self):
        import appliquer_strip_motionphoto as S
        rap = {'fichiers': {'a': {'g': 'xmp-residuel', 't': 1}, 'b': {'g': 'google', 'v': 5},
                            'c': {'g': 'samsung'}}}
        self.assertEqual([k for k, _ in S.candidats(rap)], ['b'])


class RapportLimiteALIndex(unittest.TestCase):
    def test_entree_hors_index_retiree(self):
        with tempfile.TemporaryDirectory() as d:
            ancien = M.RAPPORT
            M.RAPPORT = Path(d) / 'r.json'
            try:
                f = Path(d) / 'a.jpg'
                f.write_bytes(STILL)
                db = Path(d) / 'copie.db'
                cx = sqlite3.connect(db)
                cx.execute('CREATE TABLE tags (k TEXT PRIMARY KEY, v TEXT)')
                cx.execute('INSERT INTO tags VALUES (?, ?)', (str(f), '{}'))
                cx.commit()
                cx.close()
                M.ecrire_cache({M.nk(Path(d) / 'parti.jpg'):
                                {'t': 9, 'm': 9, 'g': 'les-deux', 'v': 5, 'me': 'fenetre', 'fv': 2}}, {})
                self.assertEqual(M.main(['--base', str(db)]), 0)
                rap = json.loads(M.RAPPORT.read_text(encoding='utf-8'))
                self.assertEqual(set(rap['fichiers']), {M.nk(f)})
            finally:
                M.RAPPORT = ancien


class Fraicheur(unittest.TestCase):
    """15/09 : un cache jamais re-verifie a rendu le compte d'AVANT le strip."""

    def test_strip_invalide_l_entree(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'a.jpg'
            f.write_bytes(STILL + MP4 + b'\x00' * 40 + b'SEFT')
            ent = M.sonder(str(f), 1 << 20)
            self.assertTrue(ent.get('v'))
            g = Path(d) / 'b.jpg'
            g.write_bytes(STILL)
            h = Path(d) / 'c.jpg'
            fichiers = {M.nk(f): dict(ent), M.nk(g): M.sonder(str(g), 1 << 20),
                        M.nk(h): {'err': 'x', 'nom': 'c.jpg'}}
            h.write_bytes(STILL)
            # le strip : meme mtime (exiftool -P), taille plus petite
            st = os.stat(f)
            f.write_bytes(STILL)
            os.utime(f, (st.st_atime, st.st_mtime))
            disparu = Path(d) / 'z.jpg'
            fichiers[M.nk(disparu)] = {'t': 1, 'm': 1, 'g': None}
            r = M.perimees(fichiers, [str(f), str(g), str(h), str(disparu)], 2)
            self.assertEqual(r, (4, 1, 2, 1))
            self.assertEqual(set(fichiers), {M.nk(g)})

    def test_mtime_seul_invalide(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'a.jpg'
            f.write_bytes(STILL)
            fichiers = {M.nk(f): M.sonder(str(f), 1 << 20)}
            st = os.stat(f)
            os.utime(f, (st.st_atime, st.st_mtime + 10))
            self.assertEqual(M.perimees(fichiers, [str(f)]), (1, 0, 1, 0))


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
