#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le nom dit QUELLE vignette, le tampon dit si elle est A JOUR (10/09).

Ce banc tient les quatre proprietes du nouveau cache, et la plus importante est
la troisieme — celle qui fait tout le gain, et qui est aussi la seule qui
pourrait servir une image perimee si on l'appelait au mauvais endroit.

Il lit `server.py` par l'ARBRE SYNTAXIQUE, sans l'importer : le module ouvre
photos.db, monte cinq magasins et lance des fils.
"""

import ast
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable dans server.py')


def _src(nom):
    return ast.get_source_segment(SOURCE, _noeud(nom)) or ''


def _module_des_helpers(dossier):
    """Les quatre helpers, extraits de server.py et executes seuls."""
    m = types.ModuleType('vign')
    m.__dict__['os'] = os
    m.__dict__['PHOTO_THUMB_DIR'] = Path(dossier)
    for nom in ('_fichier_vignette', '_vignette_a_jour', '_tamponner_vignette',
                '_retamponner_vignettes'):
        exec(_src(nom), m.__dict__)                               # noqa: S102
    return m


class LesQuatreProprietes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.m = _module_des_helpers(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _poser(self, key, s, mt, video=False):
        f = self.m._fichier_vignette(key, s, video)
        f.write_bytes(b'jpeg')
        self.m._tamponner_vignette(f, mt)
        return f

    # 1 ────────────────────────────────────────────────────────────────────
    def test_le_nom_NE_PORTE_PLUS_le_mtime(self):
        """La propriete d'ou vient tout le reste : deux versions successives
        de la meme photo ecrivent le MEME fichier."""
        a = self.m._fichier_vignette('x.jpg', 512)
        b = self.m._fichier_vignette('x.jpg', 512)
        self.assertEqual(a, b)
        self.assertNotEqual(a, self.m._fichier_vignette('x.jpg', 1600))
        self.assertNotEqual(a, self.m._fichier_vignette('y.jpg', 512))
        self.assertNotEqual(a, self.m._fichier_vignette('x.jpg', 512, True))

    def test_un_seul_fichier_par_photo_et_par_taille(self):
        """Donc : plus d'orphelin par construction. Une vignette perimee est
        ECRASEE, pas dupliquee — c'est O15 qui disparait a sa racine."""
        d = Path(self.tmp.name)
        self._poser('x.jpg', 512, 1000)
        self._poser('x.jpg', 512, 2000)          # la photo a change
        self._poser('x.jpg', 512, 3000)          # et encore
        self.assertEqual(len(list(d.glob('*.jpg'))), 1)

    # 2 ────────────────────────────────────────────────────────────────────
    def test_le_tampon_juge_la_fraicheur(self):
        f = self._poser('x.jpg', 512, 1_700_000_000)
        self.assertTrue(self.m._vignette_a_jour(f, 1_700_000_000))
        self.assertFalse(self.m._vignette_a_jour(f, 1_700_000_001))

    def test_un_fichier_absent_n_est_jamais_a_jour(self):
        f = self.m._fichier_vignette('jamais_faite.jpg', 512)
        self.assertFalse(self.m._vignette_a_jour(f, 1_700_000_000))

    def test_comparaison_a_la_SECONDE_pas_au_flottant(self):
        """Source sur SMB, cache en local : deux systemes de fichiers, deux
        resolutions. Une egalite de flottants y serait un piege."""
        f = self._poser('x.jpg', 512, 1_700_000_000)
        self.assertTrue(self.m._vignette_a_jour(f, 1_700_000_000.7))

    def test_sans_mtime_on_garde_ce_qu_on_a(self):
        """8 entrees de l'index sur 44 604 n'ont pas de mtime. Jeter ce qu'on
        ne sait pas juger couterait une relecture NAS a chaque affichage."""
        f = self.m._fichier_vignette('x.jpg', 512)
        f.write_bytes(b'jpeg')
        self.assertTrue(self.m._vignette_a_jour(f, None))

    # 3 ────────────────────────────────────────────────────────────────────
    def test_re_tamponner_sauve_les_vignettes_d_une_ecriture_de_tag(self):
        """LE GAIN. Ecrire un tag change le mtime sans toucher un pixel : on
        redate, on ne rejette pas."""
        self._poser('x.jpg', 512, 1000)
        self._poser('x.jpg', 1600, 1000)
        n = self.m._retamponner_vignettes('x.jpg', 2000)
        self.assertEqual(n, 2)
        for s in (512, 1600):
            f = self.m._fichier_vignette('x.jpg', s)
            self.assertTrue(self.m._vignette_a_jour(f, 2000))

    def test_re_tamponner_ne_CREE_rien(self):
        """Il redate ce qui existe. Creer un fichier vide ici servirait une
        vignette illisible a la place d'une regeneration."""
        n = self.m._retamponner_vignettes('jamais_faite.jpg', 2000)
        self.assertEqual(n, 0)
        self.assertEqual(list(Path(self.tmp.name).glob('*.jpg')), [])

    def test_re_tamponner_ne_touche_QUE_cette_photo(self):
        self._poser('x.jpg', 512, 1000)
        self._poser('y.jpg', 512, 1000)
        self.m._retamponner_vignettes('x.jpg', 2000)
        self.assertTrue(self.m._vignette_a_jour(
            self.m._fichier_vignette('y.jpg', 512), 1000))

    # 4 ────────────────────────────────────────────────────────────────────
    def test_re_tamponner_n_est_appele_QUE_sur_des_ecritures_de_METADONNEES(self):
        """La propriete la plus dangereuse a perdre. Appele apres une vraie
        modification d'image, `_retamponner_vignettes` servirait une vignette
        perimee. Ce banc verrouille la liste de ses appelants : en ajouter un
        doit etre un geste conscient, pas un copier-coller."""
        appelants = set()
        for n in ast.walk(ARBRE):
            if not isinstance(n, ast.FunctionDef):
                continue
            src = ast.get_source_segment(SOURCE, n) or ''
            if '_retamponner_vignettes(' in src and n.name != '_retamponner_vignettes':
                # la fonction ENGLOBANTE la plus proche suffit : on veut le nom
                # sous lequel le geste se relit.
                appelants.add(n.name)
        # Les deux chemins d'ecriture de metadonnees, et eux seuls.
        self.assertTrue(appelants, 'aucun appelant : le correctif ne sert a rien')
        for nom in appelants:
            src = _src(nom)
            self.assertTrue(
                'write_metadata(' in src or 'write_person_tags(' in src,
                "%s appelle _retamponner_vignettes sans ecrire de metadonnees "
                "-- si l'image a pu changer, la vignette doit etre REFAITE, "
                "pas redatee" % nom)


class LesDeuxRoutesUtilisentLaNouvelleMecanique(unittest.TestCase):
    def test_la_route_photo(self):
        s = _src('_serve_thumb')
        self.assertIn('_fichier_vignette(key, s)', s)
        self.assertIn('_vignette_a_jour(cache_file, mt)', s)
        self.assertIn('_tamponner_vignette(cache_file, mt)', s)
        self.assertNotIn('|{mt}|', s)          # l'ancien nommage a disparu

    def test_la_route_video(self):
        s = _src('_serve_thumb_video')
        self.assertIn('_fichier_vignette(key, s, video=True)', s)
        self.assertIn('_vignette_a_jour(cache_file, mt)', s)
        self.assertIn('_tamponner_vignette(cache_file, mt)', s)
        self.assertNotIn('|video"', s)


if __name__ == '__main__':
    unittest.main(verbosity=2)
