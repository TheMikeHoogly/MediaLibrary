#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le strip et la purge Motion Photo font-ils ce qu'ils disent ? (1 septies)

Tout est synthetique : aucun NAS, jamais photos.db, jamais exiftool — on teste
la SELECTION, la VERIFICATION d'apres-strip et la QUARANTAINE, pas l'outil
externe (lui a son banc : verifier_strip_motionphoto).
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import appliquer_strip_motionphoto as S
import appliquer_purge_motionphoto as P

STILL = b'\xff\xd8\xff\xe0' + b'\x11' * 300 + b'\xff\xd9'
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'V' * 2000


class Candidats(unittest.TestCase):
    def test_seules_les_vraies_motion(self):
        rapport = {'fichiers': {
            'a.jpg': {'t': 10, 'g': 'les-deux', 'v': 5},
            'b.jpg': {'t': 10, 'g': 'google', 'v': 4},
            'c.jpg': {'t': 10, 'g': 'samsung'},          # sef-sans-video
            'd.jpg': {'t': 10, 'g': None},
            'e.jpg': {'err': 'x', 'nom': 'e.jpg'},
            'f.jpg': {'t': 10, 'g': 'samsung', 'v': 3},  # samsung AVEC video
        }}
        cles = [k for k, _ in S.candidats(rapport)]
        self.assertEqual(cles, ['a.jpg', 'b.jpg', 'f.jpg'])

    def test_deja_fait(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.jpg'
            p.write_bytes(STILL)
            self.assertIsNone(S.deja_fait(str(p), {'faits': {}}))
            self.assertEqual(S.deja_fait(str(p), {'faits': {str(p): {}}}),
                             'au manifeste')
            (Path(d) / 'x.jpg_original').write_bytes(STILL + MP4)
            self.assertEqual(S.deja_fait(str(p), {'faits': {}}),
                             '_original deja present')


class VerifierApres(unittest.TestCase):
    def _cas(self, d, apres, original=True):
        p = Path(d) / 'x.jpg'
        p.write_bytes(apres)
        if original:
            (Path(d) / 'x.jpg_original').write_bytes(STILL + MP4)
        return str(p)

    def test_strip_reussi(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._cas(d, STILL)
            self.assertIsNone(S.verifier_apres(p, len(STILL + MP4)))

    def test_pas_d_original(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._cas(d, STILL, original=False)
            self.assertIn('_original', S.verifier_apres(p, len(STILL + MP4)))

    def test_pas_plus_petit(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._cas(d, STILL + MP4)
            self.assertIn('pas plus petit', S.verifier_apres(p, len(STILL + MP4)))

    def test_jpeg_invalide(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._cas(d, STILL[:-2] + b'\x00\x00')
            self.assertIn('FF D9', S.verifier_apres(p, len(STILL + MP4)))

    def test_exiftool_tmp_condamne(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._cas(d, STILL)
            (Path(d) / 'x.jpg_exiftool_tmp').write_bytes(b'')
            self.assertIn('_exiftool_tmp', S.verifier_apres(p, len(STILL + MP4)))

    def test_disparu(self):
        self.assertEqual(S.verifier_apres('nulle/part/x.jpg', 10), 'DISPARU')


class Purge(unittest.TestCase):
    def test_ramassage_ignore_les_dossiers_caches(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            (r / 'a').mkdir()
            (r / 'a' / 'x.jpg_original').write_bytes(b'1')
            (r / '.corbeille-rangement').mkdir()
            (r / '.corbeille-rangement' / 'y.jpg_original').write_bytes(b'1')
            (r / 'a' / 'z.jpg').write_bytes(b'1')
            trouves = P.originaux_sous(str(r))
            self.assertEqual([Path(t).name for t in trouves], ['x.jpg_original'])

    def test_quarantaine_deplace_et_manifeste(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d) / 'Photos'
            (r / '.corbeille-rangement').mkdir(parents=True)
            (r / 'Photos Mike' / '2024').mkdir(parents=True)
            orig = r / 'Photos Mike' / '2024' / 'x.jpg_original'
            orig.write_bytes(STILL + MP4)
            man = {'faits': {str(r / 'x.jpg'): {'avant': 1, 'apres': 1,
                                                'original': str(orig)}}}
            P.MANIFESTE = Path(d) / 'strip_manifeste.json'
            P.MANIFESTE.write_text(json.dumps(man), encoding='utf-8')
            code = P.main(['--appliquer'])
            self.assertEqual(code, 0)
            self.assertFalse(orig.exists())
            q = list((r / '.corbeille-rangement').glob('strip_motionphoto_*'))
            self.assertEqual(len(q), 1)
            self.assertTrue((q[0] / 'Photos Mike' / '2024' / 'x.jpg_original').exists())
            self.assertTrue((q[0] / 'manifeste.json').exists())

    def test_racine_photos(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d) / 'Photos'
            (r / '.corbeille-rangement').mkdir(parents=True)
            (r / 'a').mkdir()
            self.assertEqual(P.racine_photos(r / 'a' / 'x.jpg_original'), r)


if __name__ == '__main__':
    unittest.main()
