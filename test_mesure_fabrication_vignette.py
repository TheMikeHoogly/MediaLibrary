#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le banc de fabrication recopie l'ecriture de `_serve_thumb`. S'il en diverge,
il mesure une autre vignette que celle du serveur, et son « x3 » ne veut plus
rien dire. Ces bancs le tiennent : l'ecriture recopiee est celle du serveur
(par l'arbre syntaxique), et la variante `draft` respecte l'orientation EXIF
et la taille — sur des JPEG fabriques ici, jamais sur une photo de Mike.
"""

import ast
import io
import tempfile
import unittest
from pathlib import Path

import mesure_fabrication_vignette as m

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')


def _corps(nom):
    for n in ast.walk(ast.parse(SOURCE)):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ast.unparse(n)
    raise AssertionError(nom)


def _jpeg(orientation, taille=(1600, 1200)):
    from PIL import Image
    im = Image.linear_gradient('L').resize(taille).convert('RGB')
    ex = Image.Exif()
    ex[0x0112] = orientation
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=90, exif=ex)
    return buf.getvalue()


class LaCopieEstCelleDuServeur(unittest.TestCase):
    def test_la_sequence_de_serve_thumb(self):
        serveur = _corps('_serve_thumb')
        banc = ast.unparse(ast.parse(
            (HERE / 'mesure_fabrication_vignette.py').read_text(encoding='utf-8')))
        for geste in ("ImageOps.exif_transpose(im).convert('RGB')",
                      'im.thumbnail((s, s))',
                      "im.save(buf, 'JPEG', quality=82)"):
            self.assertIn(geste, serveur, geste)
            self.assertIn(geste, banc, geste)


class LaVarianteDraft(unittest.TestCase):
    def test_orientation_et_taille_identiques(self):
        from PIL import Image
        for o in (1, 3, 6, 8):
            data = _jpeg(o)
            a = Image.open(io.BytesIO(m.fabriquer_actuel(data, 512)))
            b = Image.open(io.BytesIO(m.fabriquer_draft(data, 512)))
            self.assertEqual(a.size, b.size, o)
            self.assertEqual(a.size, (384, 512) if o in (6, 8) else (512, 384))
            self.assertGreater(m.psnr(m.fabriquer_actuel(data, 512),
                                      m.fabriquer_draft(data, 512)), 35, o)

    def test_psnr_identique_et_tailles_differentes(self):
        data = m.fabriquer_actuel(_jpeg(1), 512)
        self.assertEqual(m.psnr(data, data), float('inf'))
        autre = m.fabriquer_actuel(_jpeg(6), 512)
        self.assertIsNone(m.psnr(data, autre))

    def test_le_choix_repartit_et_ne_prend_que_des_jpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i in range(30):
                (d / ('p%02d.jpg' % i)).write_bytes(b'x')
            (d / 'v.mp4').write_bytes(b'x')
            (d / 'q.PNG').write_bytes(b'x')
            choix = m.choisir(d, 5)
            self.assertEqual(len(choix), 5)
            self.assertTrue(all(p.suffix == '.jpg' for p in choix))
            self.assertEqual(choix[0].name, 'p00.jpg')
            self.assertEqual(choix[1].name, 'p06.jpg')


if __name__ == '__main__':
    unittest.main(verbosity=2)
