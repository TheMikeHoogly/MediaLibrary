#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`_resolve_key` : le `Path` memoise, et `UPLOAD_DIR` volontairement dehors.

Ce que ce fichier protege (12/09)
---------------------------------
`_resolve_key` etait appelee une fois par photo dans la galerie, et la
construction du `Path` y pesait l'essentiel des 38 ms de `enrichir.dossier`.
La moitie qui ne depend QUE de la cle est memoisee.

Le piege, et la raison d'etre de ce banc : **`UPLOAD_DIR` se regle au
demarrage** (`--upload-dir` dans `argv`) et des bancs le deplacent. S'il
entrait dans le cache, un deplacement du dossier serait ignore jusqu'au
redemarrage — un defaut muet, et le pire de tous : celui qui fait viser un
AUTRE fichier. La branche Uploads se recalcule donc a chaque appel.

Le banc lit `server.py` par l'arbre syntaxique et ne l'importe PAS : le
serveur tire torch et insightface.

**A lancer sous WINDOWS** (agent de banc). `Path(r'\\\\NAS\\x.jpg').is_absolute()`
est FAUX sous Linux : la VM y verrait des chemins relatifs la ou la prod voit
des UNC, et ce banc-la mesurerait la plateforme, pas la regle. Meme cas que
`test_galerie_enrichissement.py`.
"""
import ast
import io
import os
import unittest
from functools import lru_cache
from pathlib import Path

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.py')

with io.open(SERVER, encoding='utf-8') as _f:
    SOURCE = _f.read()
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable dans server.py')


def _espace(upload_dir):
    """Les deux fonctions de prod, dans un espace ou `UPLOAD_DIR` est a nous."""
    esp = {'Path': Path, 'lru_cache': lru_cache, 'UPLOAD_DIR': upload_dir}
    for nom in ('_cle_en_chemin', '_resolve_key'):
        exec(compile(ast.Module(body=[_noeud(nom)], type_ignores=[]),
                     SERVER, 'exec'), esp)
    return esp


class LaReponseNeChangePas(unittest.TestCase):
    """L'ORACLE : l'ecriture d'avant, sur chaque forme de cle du projet."""

    CLES = [
        r'\\NAS-Bremblens\home\Photos\2016\x.jpg',
        r'C:\Prog\y.jpg',
        'photo.jpg',
        'Album/Sous/photo.jpg',
        r'Album\Sous\photo.jpg',
        '',
        'C:/mixte/z.jpg',
    ]

    def _oracle(self, name, upload_dir):
        p = Path(name)
        return p if p.is_absolute() else upload_dir / name

    def test_chaque_forme_de_cle(self):
        up = Path(r'D:\Uploads')
        esp = _espace(up)
        for k in self.CLES:
            self.assertEqual(esp['_resolve_key'](k), self._oracle(k, up), k)

    def test_une_cle_qui_est_deja_un_Path(self):
        """Le cache veut du hashable ; un `Path` l'est, mais la branche non-str
        existe pour ne RIEN supposer de ce que les appelants passent."""
        up = Path(r'D:\Uploads')
        esp = _espace(up)
        for k in (Path('photo.jpg'), Path(r'C:\abs\x.jpg')):
            self.assertEqual(esp['_resolve_key'](k), self._oracle(k, up), k)


class UPLOAD_DIR_RESTE_DEHORS(unittest.TestCase):
    """Le seul vrai risque de ce memo, et il se teste."""

    def test_deplacer_UPLOAD_DIR_est_vu_TOUT_DE_SUITE(self):
        esp = _espace(Path(r'D:\Avant'))
        avant = esp['_resolve_key']('photo.jpg')
        self.assertEqual(avant, Path(r'D:\Avant\photo.jpg'))
        esp['UPLOAD_DIR'] = Path(r'E:\Apres')
        apres = esp['_resolve_key']('photo.jpg')
        self.assertEqual(apres, Path(r'E:\Apres\photo.jpg'),
                         'UPLOAD_DIR est entre dans le cache')

    def test_une_cle_ABSOLUE_ne_depend_pas_d_UPLOAD_DIR(self):
        esp = _espace(Path(r'D:\Avant'))
        k = r'\\NAS\Photos\x.jpg'
        avant = esp['_resolve_key'](k)
        esp['UPLOAD_DIR'] = Path(r'E:\Apres')
        self.assertEqual(esp['_resolve_key'](k), avant)


class LeMemoEvitVraimentDuTravail(unittest.TestCase):

    def test_deux_appels_sur_la_MEME_cle_ne_construisent_qu_un_Path(self):
        esp = _espace(Path(r'D:\Uploads'))
        esp['_cle_en_chemin'].cache_clear()
        for _ in range(5):
            esp['_resolve_key'](r'\\NAS\Photos\2016\x.jpg')
        info = esp['_cle_en_chemin'].cache_info()
        self.assertEqual(info.misses, 1)
        self.assertEqual(info.hits, 4)

    def test_le_cache_est_BORNE_et_tient_le_fonds(self):
        esp = _espace(Path(r'D:\Uploads'))
        info = esp['_cle_en_chemin'].cache_info()
        self.assertIsNotNone(info.maxsize)
        self.assertGreaterEqual(info.maxsize, 44605)

    def test_deux_cles_DIFFERENTES_ne_se_confondent_pas(self):
        esp = _espace(Path(r'D:\Uploads'))
        a = esp['_resolve_key'](r'\\NAS\Photos\2016\x.jpg')
        b = esp['_resolve_key'](r'\\NAS\Photos\2016\y.jpg')
        self.assertNotEqual(a, b)


if __name__ == '__main__':
    unittest.main(verbosity=2)
