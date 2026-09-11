#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le fil de fond qui fabrique les vignettes de grille manquantes.

Choix de Mike le 11/09 (« les deux ») : le tagueur écrit celles qu'il repasse,
ce fil fait le reste — ~39 000 photos. Il lit le NAS pendant des heures ; ce
qui compte le plus est donc ce qu'il NE fait PAS :

  1. **il ne dispute rien** : ni à la campagne (file de tagging non vide →
     il attend), ni à l'interface (`ui_recent` → il cède, même au milieu d'un
     lot), ni au disque (sous le plancher → il s'arrête et le dit) ;
  2. **il ne sert jamais une vignette périmée** : tamponnée au mtime de
     l'index, ou pas du tout ;
  3. **il ne fabrique pas autre chose que la route** : la même fonction,
     `_fabriquer_vignette`, prouvée identique à l'ancienne écriture de
     `_serve_thumb` octet pour octet ;
  4. **il ne meurt pas** : une photo illisible est notée et sautée ; un fil
     désactivé dort au lieu de rendre (pour `fil_surveille`, rendre = mourir).

Et il PROUVE son chemin dès le démarrage : un lot témoin de 3 photos, campagne
ou pas, dont le résultat se lit dans `/api/serveur`.
"""

import ast
import io
import os
import shutil
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
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


def _constante(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == nom for t in n.targets):
            return ''.join(_LIGNES[n.lineno - 1:n.end_lineno])
    raise AssertionError(nom)


class Arret(Exception):
    pass


class _File:
    def __init__(self, vide=True):
        self.vide = vide

    def empty(self):
        return self.vide


def _monde(tmp, index, **k):
    from PIL import Image, ImageOps
    etat = {'dormi': [], 'creneaux': 0, 'ui': k.get('ui', lambda: False)}

    def dormir(sec):
        etat['dormi'].append(sec)
        if len(etat['dormi']) > k.get('tours', 6):
            raise Arret()

    @contextmanager
    def creneau(nom, timeout=120.0):
        etat['creneaux'] += 1
        yield k.get('creneau_ok', True)

    etat['dormir'] = dormir
    g = {'os': os, 'io': io, 'time': time, 'shutil': shutil, 'Path': Path,
         'Image': Image, 'ImageOps': ImageOps, 'PIL_OK': True,
         'PHOTO_THUMB_DIR': Path(tmp) / 'photo_thumbs',
         'SCRIPT_DIR': Path(tmp), 'INDEX_BRUT': index,
         'TAG_QUEUE': _File(k.get('file_vide', True)),
         'ui_recent': lambda: etat['ui'](),
         'creneau': creneau,
         '_best_time': lambda cle, e: e.get('t', 0),
         '_resolve_key': lambda cle: Path(cle),
         'print': lambda *a, **kw: etat.setdefault('dit', []).append(a)}
    for nom in ('IMAGE_EXT', 'VIGNETTE_GRILLE', 'VIGNETTES_FOND_ENABLE',
                'VIGNETTES_LOT', 'VIGNETTES_PACE', 'VIGNETTES_ATTENTE_S',
                'VIGNETTES_REPOS_S', 'VIGNETTES_DISQUE_MIN_GO',
                'VIGNETTES_TEMOIN', 'VIGNETTES_ETAT', '_VIGNETTES_ECHECS'):
        exec(_constante(nom), g)                                       # noqa: S102
    g.update(k.get('surcharges', {}))
    for nom in ('_is_hidden_path', '_fichier_vignette', '_vignette_a_jour',
                '_tamponner_vignette', '_fabriquer_vignette',
                '_vignettes_a_faire', '_noms_vignettes_presents',
                '_vignette_de_fond', '_disque_libre_go', 'vignettes_loop'):
        exec(_src(nom), g)                                             # noqa: S102
    if 'disque' in k:
        g['_disque_libre_go'] = lambda: k['disque']
    return g, etat


def _jpeg(chemin, taille=(1200, 900)):
    from PIL import Image
    Image.effect_mandelbrot(taille, (-2, -1.2, 1, 1.2), 50).convert('RGB').save(
        chemin, 'JPEG', quality=90)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / 'nas').mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def photo(self, nom, t=0, mt=None):
        p = self.tmp / 'nas' / nom
        _jpeg(p)
        return str(p), {'t': t, 'mtime': mt if mt is not None else int(p.stat().st_mtime)}


class LaListeDeCeQuiReste(_Base):
    def test_ce_qui_est_ecarte_et_l_ordre(self):
        g, _ = _monde(self.tmp, {})
        fv = lambda k: g['_fichier_vignette'](k, 512).stem
        index = {
            'a.jpg': {'t': 10, 'mtime': 100},
            'b.JPG': {'t': 30, 'mtime': 100},
            'c.jpg': {'t': 20, 'mtime': 100},              # présente, à jour
            'd.jpg': {'t': 40, 'mtime': 200},              # présente, périmée
            'e.jpg': {'t': 50},                            # présente, sans mtime
            'v.mp4': {'t': 99, 'mtime': 1},
            'w.jpg': {'t': 99, 'video': 1},
            'f.jpg': {'t': 99, 'failed': True},
            'n.txt': {'t': 99},
            '//NAS/Photos/.corbeille-effacements/x.jpg': {'t': 99},
            'casse.jpg': 'pas un dict',
        }
        presents = {fv('c.jpg'): 100, fv('d.jpg'): 150, fv('e.jpg'): 7}
        self.assertEqual(g['_vignettes_a_faire'](index, presents),
                         ['d.jpg', 'b.JPG', 'a.jpg'])
        self.assertEqual(g['_vignettes_a_faire'](index, presents, 2),
                         ['d.jpg', 'b.JPG'])
        g['_VIGNETTES_ECHECS'].add('b.JPG')
        self.assertEqual(g['_vignettes_a_faire'](index, presents),
                         ['d.jpg', 'a.jpg'])

    def test_elle_supporte_un_index_qui_bouge_pendant_le_compte(self):
        index = {'p%d.jpg' % i: {'t': i, 'mtime': 1} for i in range(200)}
        g, _ = _monde(self.tmp, index)
        arret = threading.Event()

        def ecrivain():
            i = 1000
            while not arret.is_set():
                index['q%d.jpg' % i] = {'t': 0, 'mtime': 1}
                index.pop('q%d.jpg' % (i - 1), None)
                i += 1
        t = threading.Thread(target=ecrivain)
        t.start()
        try:
            for _ in range(50):
                g['_vignettes_a_faire'](index, {})
        finally:
            arret.set()
            t.join()


class UneVignette(_Base):
    def test_meme_octets_que_l_ancienne_ecriture_de_la_route(self):
        from PIL import Image, ImageOps
        k, _e = self.photo('a.jpg')
        g, _ = _monde(self.tmp, {})
        with Image.open(k) as im:                       # l'ÉCRITURE D'AVANT
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((512, 512))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
            avant = buf.getvalue()
        self.assertEqual(g['_fabriquer_vignette'](Path(k), 512), avant)

    def test_ecrite_tamponnee_puis_laissee(self):
        k, e = self.photo('a.jpg', mt=1_700_000_000)
        g, _ = _monde(self.tmp, {k: e})
        self.assertTrue(g['_vignette_de_fond'](k))
        f = g['_fichier_vignette'](k, 512)
        self.assertEqual(int(f.stat().st_mtime), 1_700_000_000)
        self.assertTrue(g['_vignette_a_jour'](f, e['mtime']))
        self.assertFalse(g['_vignette_de_fond'](k))          # déjà à jour
        self.assertEqual(g['VIGNETTES_ETAT']['faites'], 1)
        self.assertEqual([x.suffix for x in f.parent.iterdir()], ['.jpg'])

    def test_une_photo_illisible_est_notee_et_sautee(self):
        p = self.tmp / 'nas' / 'casse.jpg'
        p.write_bytes(b'pas une image')
        k = str(p)
        g, _ = _monde(self.tmp, {k: {'mtime': 1}})
        self.assertFalse(g['_vignette_de_fond'](k))
        self.assertIn(k, g['_VIGNETTES_ECHECS'])
        self.assertEqual(g['VIGNETTES_ETAT']['echecs'], 1)
        self.assertEqual(g['_vignettes_a_faire'](g['INDEX_BRUT'], {}), [])


class LeFilNeDisputeRien(_Base):
    def _index(self, n=5):
        return dict(self.photo('p%d.jpg' % i, t=i) for i in range(n))

    def test_le_lot_temoin_part_meme_pendant_la_campagne_puis_le_fil_attend(self):
        index = self._index(6)
        g, etat = _monde(self.tmp, index, file_vide=False, tours=4)
        with self.assertRaises(Arret):
            g['vignettes_loop'](etat['dormir'])
        temoin = g['VIGNETTES_ETAT']['temoin']
        self.assertEqual((temoin['faites'], temoin['essayees']), (3, 3))
        self.assertEqual(g['VIGNETTES_ETAT']['faites'], 3)
        self.assertEqual(g['VIGNETTES_ETAT']['etat'], 'attend la fin du tagging')
        self.assertEqual(etat['creneaux'], 0)
        # les trois PLUS RÉCENTES
        faites = {g['_fichier_vignette'](k, 512).stem for k in index}
        presents = set(g['_noms_vignettes_presents']())
        self.assertEqual(len(presents & faites), 3)
        for k in ('p5', 'p4', 'p3'):
            cle = str(self.tmp / 'nas' / (k + '.jpg'))
            self.assertIn(g['_fichier_vignette'](cle, 512).stem, presents)

    def test_campagne_finie_il_fabrique_tout_puis_se_repose(self):
        index = self._index(5)
        g, etat = _monde(self.tmp, index, tours=8)
        with self.assertRaises(Arret):
            g['vignettes_loop'](etat['dormir'])
        self.assertEqual(g['VIGNETTES_ETAT']['faites'], 5)
        self.assertEqual(g['VIGNETTES_ETAT']['etat'], 'a jour')
        self.assertIn(g['VIGNETTES_REPOS_S'], etat['dormi'])
        self.assertGreaterEqual(etat['creneaux'], 1)

    def test_l_interface_d_abord(self):
        index = self._index(5)
        g, etat = _monde(self.tmp, index, ui=lambda: True, tours=5)
        g['VIGNETTES_ETAT']['temoin'] = {'deja': 1}
        with self.assertRaises(Arret):
            g['vignettes_loop'](etat['dormir'])
        self.assertEqual(g['VIGNETTES_ETAT']['faites'], 0)
        self.assertEqual(g['VIGNETTES_ETAT']['etat'], "cede a l'interface")

    def test_l_interface_arrete_un_lot_en_cours_et_rien_n_est_perdu(self):
        """L'UI est consultée ENTRE deux photos d'un même lot — un lot de 20
        photos, c'est ~10 s de NAS qu'on ne doit pas imposer à un clic."""
        index = self._index(6)
        journal = []
        g, etat = _monde(self.tmp, index, tours=10)
        fabs = []

        def ui():
            r = len(fabs) == 2 and not any(x[0] == 'ui' and x[1] for x in journal)
            journal.append(('ui', r, len(etat['dormi'])))
            return r
        g['ui_recent'] = ui
        vraie = g['_vignette_de_fond']

        def fab(k):
            fabs.append(k)
            journal.append(('fab', k, len(etat['dormi'])))
            return vraie(k)
        g['_vignette_de_fond'] = fab
        g['VIGNETTES_ETAT']['temoin'] = {'deja': 1}
        with self.assertRaises(Arret):
            g['vignettes_loop'](etat['dormir'])
        self.assertEqual(g['VIGNETTES_ETAT']['faites'], 6)   # tout, au final
        self.assertEqual(len(fabs), 6)                        # et une seule fois chacune
        # entre deux fabrications consécutives, l'UI a été consultée
        for a, b in zip(journal, journal[1:]):
            self.assertFalse(a[0] == 'fab' and b[0] == 'fab', journal)
        # le signal de l'UI est tombé AU MILIEU du lot, et a été suivi d'un sommeil
        i = next(j for j, x in enumerate(journal) if x[0] == 'ui' and x[1])
        self.assertTrue(all(x[2] > journal[i][2] for x in journal[i + 1:] if x[0] == 'fab'))

    def test_le_disque_d_abord(self):
        index = self._index(3)
        g, etat = _monde(self.tmp, index, disque=5.0, tours=3)
        g['VIGNETTES_ETAT']['temoin'] = {'deja': 1}
        with self.assertRaises(Arret):
            g['vignettes_loop'](etat['dormir'])
        self.assertEqual(g['VIGNETTES_ETAT']['faites'], 0)
        self.assertEqual(g['VIGNETTES_ETAT']['etat'], 'disque plein')
        self.assertTrue(etat.get('dit'))          # et il le DIT

    def test_un_creneau_refuse_ne_perd_pas_le_lot(self):
        index = self._index(3)
        g, etat = _monde(self.tmp, index, creneau_ok=False, tours=4)
        g['VIGNETTES_ETAT']['temoin'] = {'deja': 1}
        with self.assertRaises(Arret):
            g['vignettes_loop'](etat['dormir'])
        self.assertEqual(g['VIGNETTES_ETAT']['faites'], 0)
        self.assertEqual(g['VIGNETTES_ETAT']['a_faire'], 3)

    def test_desactive_il_dort_il_ne_rend_pas(self):
        g, etat = _monde(self.tmp, {}, tours=3,
                         surcharges={'VIGNETTES_FOND_ENABLE': False})
        with self.assertRaises(Arret):
            g['vignettes_loop'](etat['dormir'])
        self.assertEqual(g['VIGNETTES_ETAT']['etat'], 'desactive')


class IlEstBrancheLaOuIlFaut(unittest.TestCase):
    def test_la_route_utilise_la_meme_fabrication(self):
        s = ast.unparse(ast.parse(_src_methode('_serve_thumb')))
        self.assertIn('data = _fabriquer_vignette(path, s)', s)
        self.assertNotIn('im.thumbnail', s)

    def test_le_fil_est_lance_et_surveille(self):
        self.assertIn('fil_surveille(vignettes_loop)', SOURCE)

    def test_son_etat_se_lit_dans_api_serveur(self):
        self.assertIn("'vignettes': dict(VIGNETTES_ETAT)",
                      _src_methode('_serve_serveur_etat'))


def _src_methode(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            import textwrap
            return textwrap.dedent(''.join(_LIGNES[n.lineno - 1:n.end_lineno]))
    raise AssertionError(nom)


if __name__ == '__main__':
    unittest.main(verbosity=2)
