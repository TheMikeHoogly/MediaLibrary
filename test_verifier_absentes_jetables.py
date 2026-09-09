#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de verifier_absentes_jetables.py.

Ce que ces tests protegent : le bat 49 efface 96 Go et la corbeille ne les
reprendra pas. Le jour ou cet instrument dit JETABLE a tort, une photo
disparait du monde. Chaque test ci-dessous est donc ecrit dans ce sens :
le doute rend A SAUVER, jamais l'inverse.

Lance : python test_verifier_absentes_jetables.py
"""

import json
import sys
import unittest

import verifier_absentes_jetables as V

FTYP = bytes([0, 0, 0, 24]) + b'ftypmp42'
JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0, 16, 0x4A, 0x46, 0x49, 0x46, 0, 1])
D = 'C:\\GP\\Takeout\\Google Photos\\Photos from 2024'


def rapport(absentes, autres=()):
    return {'par_verdict': {
        'ABSENT': [{'chemin_google': c} for c in absentes],
        'CERTAIN': [{'chemin_google': c} for c in autres]}}


class LeCasReel(unittest.TestCase):
    """Les 14 sans extension du 09/09."""

    def test_photo_jumelle_ET_ftyp_donnent_JETABLE(self):
        r = rapport([D + '\\20240712_202715'], [D + '\\20240712_202715.jpg'])
        v = V.juger(r, lire=lambda c, n=12: FTYP)
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0][1], v[0][2])


class LeDouteRendASauver(unittest.TestCase):

    def test_sans_photo_jumelle_on_GARDE(self):
        # Une vraie video autonome : rien ne dit que c'est une Motion Photo.
        r = rapport([D + '\\vacances'], [D + '\\autre_chose.jpg'])
        v = V.juger(r, lire=lambda c, n=12: FTYP)
        self.assertFalse(v[0][1])
        self.assertIn('aucune photo de meme nom', v[0][2])

    def test_photo_jumelle_mais_PAS_du_mp4_on_GARDE(self):
        # Une photo mal nommee a cote d'une autre : surtout pas jetable.
        r = rapport([D + '\\20240712_202715'], [D + '\\20240712_202715.jpg'])
        v = V.juger(r, lire=lambda c, n=12: JPEG)
        self.assertFalse(v[0][1])
        self.assertIn('pas du MP4', v[0][2])

    def test_un_fichier_ILLISIBLE_on_GARDE(self):
        def casse(c, n=12):
            raise OSError('disparu')
        r = rapport([D + '\\20240712_202715'], [D + '\\20240712_202715.jpg'])
        v = V.juger(r, lire=casse)
        self.assertFalse(v[0][1])
        self.assertIn('illisible', v[0][2])

    def test_un_fichier_TRONQUE_sous_huit_octets_on_GARDE(self):
        r = rapport([D + '\\20240712_202715'], [D + '\\20240712_202715.jpg'])
        v = V.juger(r, lire=lambda c, n=12: b'\x00\x00\x00')
        self.assertFalse(v[0][1])

    def test_un_fichier_n_est_JAMAIS_sa_propre_jumelle(self):
        # Rouge au premier lancement : une absente nommee `perdue.jpg`
        # s'inscrivait elle-meme parmi les photos temoins et se donnait
        # ainsi le feu vert. Sur un script qui autorise un effacement
        # definitif, c'est le pire defaut possible.
        r = rapport([D + '\\perdue.jpg'])
        v = V.juger(r, lire=lambda c, n=12: FTYP)
        self.assertFalse(v[0][1], v[0][2])
        self.assertIn('aucune photo de meme nom', v[0][2])

    def test_la_jumelle_doit_etre_dans_le_MEME_dossier(self):
        autre = 'C:\\GP\\Takeout\\Google Photos\\Photos from 2025'
        r = rapport([D + '\\20240712_202715'],
                    [autre + '\\20240712_202715.jpg'])
        v = V.juger(r, lire=lambda c, n=12: FTYP)
        self.assertFalse(v[0][1])


class LeCodeRetour(unittest.TestCase):
    """C'est lui que le bat 49 lit : il ne doit jamais mentir."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.d = Path(tempfile.mkdtemp(prefix='absjet_'))

    def _ecrire(self, r):
        p = self.d / 'r.json'
        p.write_text(json.dumps(r), encoding='utf-8')
        return str(p)

    def test_une_seule_a_sauver_rend_1(self):
        # On passe par de VRAIS fichiers : main() n'a pas d'injection.
        (self.d / 'x.jpg').write_bytes(b'0' * 20)
        r = {'par_verdict': {
            'ABSENT': [{'chemin_google': str(self.d / 'perdue.jpg')}],
            'CERTAIN': []}}
        self.assertEqual(V.main(['--rapport', self._ecrire(r)]), 1)

    def test_zero_absente_rend_0(self):
        r = {'par_verdict': {'ABSENT': [], 'CERTAIN': []}}
        self.assertEqual(V.main(['--rapport', self._ecrire(r)]), 0)

    def test_un_rapport_introuvable_rend_2_pas_0(self):
        # 0 voudrait dire « rien ne bloque » : ce serait un feu vert menteur.
        self.assertEqual(V.main(['--rapport', str(self.d / 'rien.json')]), 2)

    def test_un_rapport_illisible_rend_2_pas_0(self):
        p = self.d / 'casse.json'
        p.write_text('{ pas du json', encoding='utf-8')
        self.assertEqual(V.main(['--rapport', str(p)]), 2)

    def test_toutes_jetables_rend_0(self):
        photo = self.d / '20240712_202715.jpg'
        photo.write_bytes(JPEG)
        video = self.d / '20240712_202715'
        video.write_bytes(FTYP)
        r = {'par_verdict': {
            'ABSENT': [{'chemin_google': str(video)}],
            'CERTAIN': [{'chemin_google': str(photo)}]}}
        self.assertEqual(V.main(['--rapport', self._ecrire(r)]), 0)


if __name__ == '__main__':
    unittest.main(verbosity=0)
