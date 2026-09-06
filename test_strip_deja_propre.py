#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""<< Deja fait >> n est pas un echec — banc sur `verifier_apres`.

Le 06/09 le bat 42 a affiche << ECHEC >> sur un fonds parfaitement propre :
0 faits, 20 rates, alors que le strip avait ete fait le 03/09. Meme faute que
le bat 45 la semaine precedente. La lecon etait ecrite dans les Reflexes ; elle
n avait ete appliquee qu a un seul outil. Ce banc la tient ici.
"""

import os
import tempfile
import unittest
from pathlib import Path

import appliquer_strip_motionphoto as S


class VerifierApres(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='strip_'))
        self.p = self.tmp / 'photo.jpg'

    def ecrire(self, octets):
        self.p.write_bytes(octets)
        return self.p.stat().st_size

    def test_rien_a_retirer_n_est_pas_un_echec(self):
        """Pas de _original, exiftool content, taille inchangee -> deja propre."""
        t = self.ecrire(b'\xff\xd8' + b'x' * 100 + b'\xff\xd9')
        etat, grief = S.verifier_apres(self.p, t, exiftool_ok=True)
        self.assertEqual(etat, 'deja_propre')
        self.assertIn('aucune video', grief)

    def test_exiftool_en_erreur_reste_un_rate(self):
        """La distinction se PROUVE : sans exiftool content, c est un rate."""
        t = self.ecrire(b'\xff\xd8' + b'x' * 100 + b'\xff\xd9')
        etat, _ = S.verifier_apres(self.p, t, exiftool_ok=False)
        self.assertEqual(etat, 'rate')

    def test_taille_changee_sans_original_reste_un_rate(self):
        """Le fichier a bouge mais rien ne le sauvegarde : on n absout pas."""
        self.ecrire(b'\xff\xd8' + b'x' * 100 + b'\xff\xd9')
        etat, _ = S.verifier_apres(self.p, 9999, exiftool_ok=True)
        self.assertEqual(etat, 'rate')

    def test_un_vrai_strip_est_fait(self):
        t_avant = 5000
        self.ecrire(b'\xff\xd8' + b'x' * 100 + b'\xff\xd9')
        (self.tmp / 'photo.jpg_original').write_bytes(b'plus gros' * 500)
        etat, grief = S.verifier_apres(self.p, t_avant, exiftool_ok=True)
        self.assertEqual(etat, 'fait')
        self.assertIsNone(grief)

    def test_fichier_disparu_est_un_rate(self):
        etat, grief = S.verifier_apres(self.tmp / 'absent.jpg', 10)
        self.assertEqual(etat, 'rate')
        self.assertEqual(grief, 'DISPARU')

    def test_tmp_exiftool_condamne_le_fichier(self):
        t = self.ecrire(b'\xff\xd8\xff\xd9')
        (self.tmp / 'photo.jpg_exiftool_tmp').write_bytes(b'')
        etat, _ = S.verifier_apres(self.p, t, exiftool_ok=True)
        self.assertEqual(etat, 'rate')

    def test_fin_de_jpeg_absente_est_un_rate(self):
        self.ecrire(b'\xff\xd8' + b'x' * 100)
        (self.tmp / 'photo.jpg_original').write_bytes(b'x' * 5000)
        etat, grief = S.verifier_apres(self.p, 5000, exiftool_ok=True)
        self.assertEqual(etat, 'rate')
        self.assertIn('FF D9', grief)


if __name__ == '__main__':
    unittest.main(verbosity=2)
