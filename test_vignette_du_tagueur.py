#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La vignette de grille écrite par le tagueur, au passage.

Mesuré le 11/09 : **98 % des 39 999 photos n'avaient pas de vignette 512 px**,
et 78 % du coût d'une fabrication à la demande est la lecture de l'original
sur le NAS. Le tagueur, lui, vient de le lire. Choix de Mike (« les deux ») :
il écrit la vignette depuis l'image qu'il a déjà en mémoire.

Ce que ces bancs gardent, dans l'ordre d'importance :
  1. **ce qui part vers l'IA ne change pas d'un octet** — le prompt EST la
     version du pipeline, l'image aussi ; toucher l'une rouvrirait la campagne ;
  2. **la vignette ne sert jamais périmée** : écrite sans tampon, elle n'est
     « à jour » qu'après `_retamponner_vignettes`, que le tagueur appelle APRÈS
     avoir réécrit les métadonnées ;
  3. **elle vaut celle du serveur** : même orientation, même taille, et un écart
     d'image invisible (PSNR) avec l'écriture de `_serve_thumb` prise pour
     oracle ;
  4. **elle ne coûte jamais une photo à la campagne** : aucune exception ne
     remonte.

Fonctions exécutées seules, sur des JPEG fabriqués ici.
"""

import ast
import io
import math
import os
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
_LIGNES = SOURCE.splitlines(keepends=True)


def _src(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ''.join(_LIGNES[n.lineno - 1:n.end_lineno])
    raise AssertionError(nom)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom)


def _monde(cache_dir, max_side=896):
    from PIL import Image, ImageOps
    g = {'Image': Image, 'ImageOps': ImageOps, 'io': io, 'os': os,
         'base64': __import__('base64'), 'PIL_OK': True,
         'MAX_IMAGE_SIDE': max_side, 'PHOTO_THUMB_DIR': Path(cache_dir),
         'TagError': type('TagError', (Exception,), {})}
    exec('VIGNETTE_GRILLE = 512', g)                                   # noqa: S102
    for nom in ('image_to_b64', '_deposer_vignette', '_fichier_vignette',
                '_vignette_a_jour', '_tamponner_vignette',
                '_retamponner_vignettes'):
        exec(_src(nom), g)                                             # noqa: S102
    return g


def _jpeg(chemin, orientation=1, taille=(3000, 2000)):
    from PIL import Image
    im = Image.effect_mandelbrot(taille, (-2, -1.2, 1, 1.2), 80).convert('RGB')
    ex = Image.Exif()
    ex[0x0112] = orientation
    im.save(chemin, 'JPEG', quality=90, exif=ex)


def _oracle_serve_thumb(chemin, s=512):
    """L'écriture de `_serve_thumb` (vérifiée ci-dessous par l'arbre)."""
    from PIL import Image, ImageOps
    with Image.open(chemin) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((s, s))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return buf.getvalue()


def _psnr(a, b):
    from PIL import Image, ImageChops, ImageStat
    ia = Image.open(io.BytesIO(a)).convert('RGB')
    ib = Image.open(io.BytesIO(b)).convert('RGB')
    assert ia.size == ib.size, (ia.size, ib.size)
    st = ImageStat.Stat(ImageChops.difference(ia, ib))
    mse = sum(r * r for r in st.rms) / 3.0
    return float('inf') if mse == 0 else 10 * math.log10(255.0 ** 2 / mse)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cache = self.dir / 'photo_thumbs'
        self.g = _monde(self.cache)

    def tearDown(self):
        self.tmp.cleanup()


class CeQuiPartVersLIA(_Base):
    def test_l_image_envoyee_est_IDENTIQUE_avec_ou_sans_vignette(self):
        for o in (1, 6):
            p = self.dir / ('p%d.jpg' % o)
            _jpeg(p, o)
            cle = str(p)
            sans = self.g['image_to_b64'](p)
            avec = self.g['image_to_b64'](
                p, vignette=self.g['_fichier_vignette'](cle, 512))
            self.assertEqual(sans, avec, o)
            self.assertTrue(self.g['_fichier_vignette'](cle, 512).is_file())


class LaVignetteVautCelleDuServeur(_Base):
    def test_orientation_taille_et_ecart_invisible(self):
        from PIL import Image
        for o, attendu in ((1, (512, 341)), (3, (512, 341)),
                           (6, (341, 512)), (8, (341, 512))):
            p = self.dir / ('o%d.jpg' % o)
            _jpeg(p, o)
            f = self.g['_fichier_vignette'](str(p), 512)
            self.g['image_to_b64'](p, vignette=f)
            data = f.read_bytes()
            self.assertEqual(Image.open(io.BytesIO(data)).size, attendu, o)
            self.assertGreater(_psnr(data, _oracle_serve_thumb(p)), 38, o)

    def test_l_oracle_est_bien_l_ecriture_du_serveur(self):
        # depuis le 11/09 au soir, la route et le fil de fond partagent
        # `_fabriquer_vignette` : c'est elle qui porte l'écriture
        self.assertIn('_fabriquer_vignette(path, s)',
                      ast.unparse(_noeud('_serve_thumb')))
        s = ast.unparse(_noeud('_fabriquer_vignette'))
        for geste in ("ImageOps.exif_transpose(im).convert('RGB')",
                      'im.thumbnail((s, s))', "im.save(buf, 'JPEG', quality=82)"):
            self.assertIn(geste, s)
        d = ast.unparse(_noeud('_deposer_vignette'))
        self.assertIn("v.save(buf, 'JPEG', quality=82)", d)

    def test_une_petite_photo_n_est_pas_agrandie(self):
        p = self.dir / 'petite.jpg'
        _jpeg(p, 1, (300, 200))
        f = self.g['_fichier_vignette'](str(p), 512)
        self.g['image_to_b64'](p, vignette=f)
        from PIL import Image
        with Image.open(f) as im:
            self.assertEqual(im.size, (300, 200))


class ElleNeSertJamaisPerimee(_Base):
    def test_sans_tampon_elle_n_est_pas_a_jour_avec_tampon_elle_l_est(self):
        p = self.dir / 'a.jpg'
        _jpeg(p)
        cle = str(p)
        f = self.g['_fichier_vignette'](cle, 512)
        self.g['image_to_b64'](p, vignette=f)
        mt_apres_ecriture_xmp = 1_700_000_000.7          # une date du passé
        self.assertFalse(self.g['_vignette_a_jour'](f, mt_apres_ecriture_xmp))
        self.assertEqual(self.g['_retamponner_vignettes'](cle, mt_apres_ecriture_xmp), 1)
        self.assertTrue(self.g['_vignette_a_jour'](f, mt_apres_ecriture_xmp))

    def test_le_tagueur_retamponne_APRES_avoir_pris_l_image_et_ecrit_le_xmp(self):
        src = ast.unparse(_noeud('tagger_worker'))
        i_image = src.index('image_to_b64(')
        i_xmp = src.index('write_metadata(path, merged, desc)')
        i_tampon = src.index('_retamponner_vignettes(name, mtime)')
        self.assertLess(i_image, i_xmp)
        self.assertLess(i_xmp, i_tampon)

    def test_le_tagueur_ne_la_demande_que_pour_une_IMAGE(self):
        src = ast.unparse(_noeud('tagger_worker'))
        self.assertIn('vignette=_fichier_vignette(name, VIGNETTE_GRILLE) if '
                      'path.suffix.lower() in IMAGE_EXT else None', src)


class ElleNeCouteRienALaCampagne(_Base):
    def test_une_vignette_deja_la_n_est_pas_reecrite(self):
        p = self.dir / 'a.jpg'
        _jpeg(p)
        f = self.g['_fichier_vignette'](str(p), 512)
        f.parent.mkdir(parents=True)
        f.write_bytes(b'celle du serveur')
        self.g['image_to_b64'](p, vignette=f)
        self.assertEqual(f.read_bytes(), b'celle du serveur')

    def test_un_cache_inecrivable_ne_leve_pas_et_l_IA_recoit_son_image(self):
        p = self.dir / 'a.jpg'
        _jpeg(p)
        bloque = self.dir / 'pas_un_dossier'
        bloque.write_bytes(b'x')                     # un FICHIER là où il faudrait un dossier
        b64 = self.g['image_to_b64'](p, vignette=bloque / 'v.jpg')
        self.assertEqual(b64, self.g['image_to_b64'](p))

    def test_jamais_depuis_une_image_reduite_sous_la_grille(self):
        g = _monde(self.cache, max_side=400)
        p = self.dir / 'a.jpg'
        _jpeg(p)
        f = g['_fichier_vignette'](str(p), 512)
        g['image_to_b64'](p, vignette=f)
        self.assertFalse(f.exists())

    def test_ecriture_atomique_et_aucun_residu(self):
        self.assertIn('os.replace(tmp, cache_file)', _src('_deposer_vignette'))
        p = self.dir / 'a.jpg'
        _jpeg(p)
        self.g['image_to_b64'](p, vignette=self.g['_fichier_vignette'](str(p), 512))
        self.assertEqual([x.suffix for x in self.cache.iterdir()], ['.jpg'])

    def test_le_cout_reste_petit(self):
        """Une vignette tirée d'une image de 896 px : quelques millisecondes,
        pas une relecture. Borne large — c'est un garde-fou, pas une mesure."""
        p = self.dir / 'a.jpg'
        _jpeg(p)
        from PIL import Image
        with Image.open(p) as im:
            im = im.convert('RGB')
            im.thumbnail((896, 896))
            t0 = time.perf_counter()
            self.g['_deposer_vignette'](im, self.cache / 'x.jpg')
            self.assertLess(time.perf_counter() - t0, 0.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
