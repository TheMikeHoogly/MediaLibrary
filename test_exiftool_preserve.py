#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`-P` : ExifTool rend au fichier sa date de modification.

Sans lui, chaque ecriture de tags remplace la date du fichier par l'instant
de l'ecriture. MESURE le 12/09 sur `Photos Mike/2022`, 400 fichiers du meme
dossier : les VIDEOS, que le tagueur ne touche pas, portent 50 jours
distincts de 2022 ; les IMAGES, taguees, en portent UN seul, 2026-09-09.

Un banc qui se contenterait de chercher "-P" dans le source ne prouverait
rien : il dirait que la chaine est ecrite, pas qu'ExifTool obeit. Celui-ci
fait l'ALLER-RETOUR sur un vrai fichier, avec le vrai ExifTool du projet, et
il porte son propre CONTRE-EXEMPLE -- la meme ecriture sans `-P`, qui DOIT
changer la date. Un banc qui ne peut pas echouer ne mesure rien.

Ecrit uniquement dans son propre dossier temporaire.
"""

import ast
import io
import os
import shutil
import subprocess
import tempfile
import time
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
LIGNES = SOURCE.splitlines()


def _exiftool():
    """L'ExifTool du projet, ou None -- meme ordre que `ensure_exiftool`."""
    w = shutil.which('exiftool')
    if w:
        return Path(w)
    for c in (HERE / 'exiftool.exe', HERE / 'exiftool' / 'exiftool.exe'):
        if c.is_file():
            return c
    try:
        for d in sorted(HERE.glob('exiftool*')):
            if d.is_dir():
                for n in ('exiftool.exe', 'exiftool(-k).exe'):
                    if (d / n).is_file():
                        return d / n
    except OSError:
        pass
    return None


def _module(outil):
    m = types.ModuleType('exif')
    m.__dict__.update({'os': os, 'subprocess': subprocess, 'io': io,
                       'Path': Path, 'EXIFTOOL': outil})
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name in ('_run_exiftool',
                                                         'write_person_tags'):
            exec('\n'.join(LIGNES[n.lineno - 1:n.end_lineno]), m.__dict__)  # noqa: S102
        elif isinstance(n, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id == 'EXIFTOOL_PRESERVE'
                for c in n.targets):
            exec('\n'.join(LIGNES[n.lineno - 1:n.end_lineno]), m.__dict__)  # noqa: S102
    for x in ('_run_exiftool', 'write_person_tags', 'EXIFTOOL_PRESERVE'):
        if x not in m.__dict__:
            raise AssertionError('%s introuvable dans server.py' % x)
    return m


OUTIL = _exiftool()
VIEUX = time.mktime((2014, 3, 21, 10, 30, 0, 0, 0, -1))


@unittest.skipIf(OUTIL is None, 'ExifTool absent : ce banc ne peut rien dire')
class ExifToolRendLaDateDuFichier(unittest.TestCase):

    def setUp(self):
        try:
            from PIL import Image
        except ImportError:                                   # pragma: no cover
            self.skipTest('Pillow absent')
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / 'photo.jpg'
        Image.new('RGB', (32, 24), (120, 140, 160)).save(self.p, 'JPEG')
        os.utime(self.p, (VIEUX, VIEUX))
        self.m = _module(OUTIL)

    def tearDown(self):
        self.tmp.cleanup()

    def mots_cles(self):
        r = subprocess.run([str(OUTIL), '-json', '-XMP-dc:Subject', str(self.p)],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=120)
        return r.stdout

    def test_la_date_survit_a_une_ecriture_de_tag(self):
        avant = os.stat(self.p).st_mtime
        self.assertAlmostEqual(avant, VIEUX, delta=2)
        ok = self.m.write_person_tags(self.p, {'personne:Florine': 'add'})
        self.assertTrue(ok, "ExifTool a refuse d'ecrire")
        # Le tag est REELLEMENT ecrit : sinon la date survivrait parce qu'on
        # n'a rien fait, et le banc se donnerait raison tout seul.
        self.assertIn('Florine', self.mots_cles())
        apres = os.stat(self.p).st_mtime
        self.assertAlmostEqual(apres, avant, delta=2,
                               msg='la date du fichier a ete reecrite malgre -P')

    def test_le_CONTRE_EXEMPLE_sans_P_change_bien_la_date(self):
        """La meme ecriture, `-P` retire : si la date ne bougeait pas non
        plus, c'est que ce banc ne mesure pas ce qu'il croit."""
        avant = os.stat(self.p).st_mtime
        args = ['-overwrite_original', '-q', '-m',
                '-XMP-dc:Subject+=personne:Temoin', str(self.p)]
        r = subprocess.run([str(OUTIL)] + args, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[:200])
        apres = os.stat(self.p).st_mtime
        self.assertGreater(apres, avant + 60,
                           'sans -P la date aurait du etre remplacee : ce banc '
                           'ne distingue pas les deux cas')

    def test_le_drapeau_est_pose_en_TETE_pour_tout_le_monde(self):
        """Trois ecrivains passent par `_run_exiftool` ; un quatrieme
        arrivera. Le drapeau est pose la, pas chez chacun."""
        src = ''
        for n in ast.walk(ARBRE):
            if isinstance(n, ast.FunctionDef) and n.name == '_run_exiftool':
                src = '\n'.join(LIGNES[n.lineno - 1:n.end_lineno])
        self.assertIn('EXIFTOOL_PRESERVE', src)
        self.assertEqual(self.m.EXIFTOOL_PRESERVE, '-P')


if __name__ == '__main__':
    unittest.main(verbosity=2)
