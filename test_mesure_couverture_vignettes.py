#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le banc de couverture recopie trois choses de server.py : la formule du nom de
vignette et les deux listes d'extensions. S'il diverge, il compte faux EN
SILENCE — il dirait « 3 % de couverture » d'un cache plein. Ces bancs le
comparent au serveur par l'arbre syntaxique, et comptent sur un petit monde
construit a la main.
"""

import ast
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import mesure_couverture_vignettes as m

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


def _constante(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == nom for t in n.targets):
            return ast.literal_eval(n.value)
    raise AssertionError(nom)


def _fichier_vignette_du_serveur():
    for n in ARBRE.body:
        if isinstance(n, ast.FunctionDef) and n.name == '_fichier_vignette':
            g = {'PHOTO_THUMB_DIR': Path('/cache')}
            exec(ast.get_source_segment(SOURCE, n), g)                 # noqa: S102
            return g['_fichier_vignette']
    raise AssertionError('_fichier_vignette')


class LeBancDitLaMemeChoseQueLeServeur(unittest.TestCase):
    def test_la_formule_du_nom(self):
        f = _fichier_vignette_du_serveur()
        for cle in (r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\a.jpg',
                    'Album/Été.JPG', 'x.heic'):
            for s in (512, 1600):
                self.assertEqual(f(cle, s).stem, m.nom_vignette(cle, s))
                self.assertEqual(f(cle, s, video=True).stem,
                                 m.nom_vignette(cle, s, video=True))

    def test_les_extensions(self):
        self.assertEqual(m.IMAGE_EXT, _constante('IMAGE_EXT'))
        self.assertEqual(m.VIDEO_EXT, _constante('VIDEO_EXT'))


class IlCompteJuste(unittest.TestCase):
    def test_un_petit_monde(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'copie.db'
            cx = sqlite3.connect(base)
            cx.execute('CREATE TABLE tags (k TEXT PRIMARY KEY, v TEXT)')
            lignes = {
                r'\\NAS\home\Photos\Photos Mike\2022\a.jpg': {'mtime': 100.4},
                r'\\NAS\home\Photos\Photos Mike\2022\b.jpg': {'mtime': 200.0},
                r'\\NAS\home\Photos\Photos Flo\c.JPG': {},
                r'\\NAS\home\Photos\Photos Flo\d.mp4': {'mtime': 1},
                r'\\NAS\home\Photos\Photos Flo\e.jpg': {'failed': True},
            }
            for k, v in lignes.items():
                cx.execute('INSERT INTO tags VALUES (?, ?)', (k, json.dumps(v)))
            cx.commit()
            cx.close()
            entrees, table = m.lire_index(base)
            self.assertEqual(table, 'tags')
            cles = list(lignes)
            cache = {m.nom_vignette(cles[0], 512): 100.9,     # a jour (seconde)
                     m.nom_vignette(cles[1], 512): 150.0,     # perimee
                     m.nom_vignette(cles[2], 512): 5.0,       # sans mtime
                     m.nom_vignette(cles[0], 1600): 100.0}
            r = m.mesurer(entrees, cache)
            self.assertEqual((r['images'], r['videos'], r['echecs']), (3, 1, 1))
            self.assertEqual(r['512'], 3)
            self.assertEqual(r['512_a_jour'], 2)
            self.assertEqual(r['1600'], 1)
            self.assertEqual(r['par_fonds']['Photos Mike'], [2, 2])
            self.assertEqual(r['par_fonds']['Photos Flo'], [1, 1])

    def test_il_refuse_la_base_vivante(self):
        self.assertEqual(m.main(['--base', 'photos.db']), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
