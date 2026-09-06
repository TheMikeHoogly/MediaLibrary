#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `appliquer_perdues.py` sur un ARBRE JOUET.

Ce script deplace des photos de famille : il ne se livre pas sans que ses
proprietes de surete soient prouvees ailleurs que dans son intention.

Ce qui est tenu ici :
  1. APERCU = rien ne bouge. C est le mode par defaut.
  2. Une coquille qui attend un rapatriement n est JAMAIS mise en corbeille
     avant -- sinon on perd l endroit ou remettre la photo.
  3. Le rapatriement met la coquille de cote AVANT de copier, pas apres.
  4. Une source illisible est sautee : on ne remplace pas une coquille par une
     autre.
  5. `--undo` remet tout exactement en place, pour les deux gestes.
  6. L arborescence est gardee en quarantaine (deux photos de meme nom dans
     deux dossiers ne s ecrasent pas).
  7. Deux gestes dans la MEME seconde n ecrasent pas le journal d annulation
     du premier -- sinon le premier geste deviendrait inannulable en silence.
"""
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import appliquer_perdues as A

COQUILLE = b'   Read error in the sector !   ' * 4
VRAIE = b'\xff\xd8\xff\xe0' + b'JFIF' + b'\x00' * 40 + b'\xff\xd9'


class Arbre(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        A.DOSSIER_JOURNAL = self.tmp / 'journaux'   # jamais dans docs/
        self.racine = self.tmp / 'Photos'
        for rel in ('Photos Mike/2009/DSC1.JPG', 'Photos Mike/2010/DSC1.JPG',
                    'Photos Mike/2019/IMG_A.jpg'):
            f = self.racine / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(COQUILLE)
        self.dehors = self.tmp / 'Takeout'
        self.dehors.mkdir()
        (self.dehors / 'IMG_A.jpg').write_bytes(VRAIE)
        (self.dehors / 'casse.jpg').write_bytes(COQUILLE)
        self.perdues = [{'cle': str(self.racine / r), 'nom': Path(r).name,
                         'octets': len(COQUILLE)}
                        for r in ('Photos Mike/2009/DSC1.JPG',
                                  'Photos Mike/2010/DSC1.JPG',
                                  'Photos Mike/2019/IMG_A.jpg')]
        self.ext = {str(self.racine / 'Photos Mike/2019/IMG_A.jpg'):
                    str(self.dehors / 'IMG_A.jpg')}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def contenu(self, rel):
        return (self.racine / rel).read_bytes()

    # 1 --------------------------------------------------------------
    def test_apercu_ne_touche_a_rien(self):
        A.restaurer(self.perdues, self.ext, appliquer=False)
        A.corbeille(self.perdues, self.ext, appliquer=False)
        self.assertEqual(self.contenu('Photos Mike/2019/IMG_A.jpg'), COQUILLE)
        self.assertTrue((self.racine / 'Photos Mike/2009/DSC1.JPG').exists())
        self.assertFalse((self.racine / A.CORBEILLE).exists())

    # 2 --------------------------------------------------------------
    def test_une_photo_a_rapatrier_n_est_pas_mise_en_corbeille(self):
        faits = A.corbeille(self.perdues, self.ext, appliquer=True)
        deplacees = {Path(f['cle']).parent.name for f in faits}
        self.assertNotIn('2019', deplacees,
                         "la coquille qui attend sa photo doit rester en place")
        self.assertTrue((self.racine / 'Photos Mike/2019/IMG_A.jpg').exists())
        self.assertEqual(len(faits), 2)

    # 3 et 4 ----------------------------------------------------------
    def test_rapatriement_met_la_coquille_de_cote_puis_copie(self):
        faits = A.restaurer(self.perdues, self.ext, appliquer=True)
        self.assertEqual(len(faits), 1)
        self.assertEqual(self.contenu('Photos Mike/2019/IMG_A.jpg'), VRAIE)
        self.assertTrue(Path(faits[0]['coquille']).exists())
        self.assertEqual(Path(faits[0]['coquille']).read_bytes(), COQUILLE)

    def test_source_illisible_sautee(self):
        ext = {str(self.racine / 'Photos Mike/2009/DSC1.JPG'):
               str(self.dehors / 'casse.jpg')}
        faits = A.restaurer(self.perdues, ext, appliquer=True)
        self.assertEqual(faits, [])
        self.assertEqual(self.contenu('Photos Mike/2009/DSC1.JPG'), COQUILLE)

    # 5 --------------------------------------------------------------
    def test_undo_corbeille(self):
        A.corbeille(self.perdues, {}, appliquer=True)
        self.assertFalse((self.racine / 'Photos Mike/2009/DSC1.JPG').exists())
        A.undo(str(A.DERNIER_JOURNAL), appliquer=True)
        self.assertEqual(self.contenu('Photos Mike/2009/DSC1.JPG'), COQUILLE)

    def test_undo_restauration(self):
        A.restaurer(self.perdues, self.ext, appliquer=True)
        A.undo(str(A.DERNIER_JOURNAL), appliquer=True)
        self.assertEqual(self.contenu('Photos Mike/2019/IMG_A.jpg'), COQUILLE)

    # 6 --------------------------------------------------------------
    def test_deux_memes_noms_ne_s_ecrasent_pas(self):
        faits = A.corbeille(self.perdues, self.ext, appliquer=True)
        dsts = [Path(f['dst']) for f in faits]
        self.assertEqual(len(set(dsts)), 2, "l arborescence doit etre gardee")
        for d in dsts:
            self.assertTrue(d.exists())
        A.undo(str(A.DERNIER_JOURNAL), appliquer=True)


    # 7 --------------------------------------------------------------
    def test_deux_journaux_dans_la_meme_seconde(self):
        a = A.journal('essai', [{'x': 1}])
        b = A.journal('essai', [{'x': 2}])
        self.assertNotEqual(a, b)
        self.assertTrue(a.exists() and b.exists())
        self.assertEqual(json.loads(a.read_text(encoding='utf-8'))['ops'],
                         [{'x': 1}])


if __name__ == '__main__':
    unittest.main(verbosity=2)
