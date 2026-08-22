#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — un gabarit sorti du monolithe (point 7), et les trois façons de le perdre.

Pourquoi ce fichier
───────────────────
Sortir une page de `server.py` vers `ui/pages/` déplace un risque : tant que le
HTML était une constante Python, il ne pouvait pas manquer. Maintenant si.
Trois pannes deviennent possibles, et **toutes les trois sont muettes** — elles
rendent une page vide ou tronquée, jamais une erreur :

1. le fichier n'est pas déployé (dossier `ui/` absent) ;
2. `bundle.py` ne cuit pas le gabarit dans le mono-fichier ;
3. le gabarit perd un marqueur (`__ROWS__`…) et le `.replace()` du serveur ne
   remplit plus rien — la page s'affiche, vide, et on cherche le défaut dans
   les données. C'est exactement le mode de panne des « 0 photo taguée » du
   22/08 : un compte à zéro qui accusait la colonne, pas les lignes.

Ces tests tiennent les trois. Ils lisent `server.py` sans l'importer
(`import server` ouvre `photos.db`, dont le serveur est l'écrivain unique) :
la fonction est extraite de l'AST et exécutée dans un espace de noms à elle.

Les tests n'impriment rien (l'agent git capture la sortie).
"""

import ast
import html
import shutil
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SOURCE = (RACINE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

import bundle

# Les marqueurs que `_serve_browse` remplit. En perdre un ne casse rien : ça
# rend une page à moitié vide, ce qui est pire.
MARQUEURS = ('__ROWS__', '__CRUMBS__', '__CTX__', '__EXTRA__')


def fonctions(*noms):
    """Les fonctions demandées de `server.py`, exécutées dans un espace à nous."""
    voulus = [n for n in ast.walk(ARBRE)
              if isinstance(n, ast.FunctionDef) and n.name in noms]
    manquants = set(noms) - {n.name for n in voulus}
    if manquants:
        raise AssertionError(f"introuvable(s) dans server.py : {manquants} — "
                             "si le chargeur de gabarits a bouge, ce test doit "
                             "etre relu, pas contourne.")
    return voulus


class Chargeur:
    """`ui_page` de la prod, branchée sur un dossier à nous."""

    def __init__(self, racine, cuit=None):
        self.ns = {'UI_PAGES_DIR': Path(racine) / 'pages',
                   '_UI_PAGES': {}, '_UI_PAGES_CUIT': dict(cuit or {}),
                   'html': html}
        mod = ast.Module(fonctions('_ui_page_signature', 'ui_page'), [])
        exec(compile(mod, 'server.py', 'exec'), self.ns)

    def __call__(self, nom):
        return self.ns['ui_page'](nom)


class TestChargeurDeGabarit(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / 'pages').mkdir()

    def ecrire(self, nom, txt):
        (self.d / 'pages' / f'{nom}.html').write_text(txt, encoding='utf-8')

    def test_le_gabarit_est_lu_tel_quel(self):
        self.ecrire('x', '<html>ok</html>')
        self.assertEqual(Chargeur(self.d)('x'), '<html>ok</html>')

    def test_une_edition_est_reprise_sans_redemarrer(self):
        # Le confort promis par le mécanisme : si le cache ne voyait pas
        # l'édition, on croirait le fichier ignoré et on redémarrerait pour
        # rien — ou pire, on éditerait le mauvais endroit.
        self.ecrire('x', 'avant')
        charger = Chargeur(self.d)
        self.assertEqual(charger('x'), 'avant')
        import os
        chemin = self.d / 'pages' / 'x.html'
        chemin.write_text('apres et plus long', encoding='utf-8')
        os.utime(chemin, (0, 0))          # mtime ET taille changent
        self.assertEqual(charger('x'), 'apres et plus long')

    def test_sans_fichier_le_gabarit_CUIT_prend_le_relais(self):
        # Le déploiement mono-fichier : `dist/server.py` sans `ui/`.
        self.assertEqual(Chargeur(self.d, {'x': '<html>cuit</html>'})('x'),
                         '<html>cuit</html>')

    def test_le_fichier_prime_sur_le_cuit(self):
        self.ecrire('x', 'du disque')
        self.assertEqual(Chargeur(self.d, {'x': 'du bundle'})('x'), 'du disque')

    def test_rien_nulle_part_DIT_le_fichier_manquant(self):
        # Une page blanche enverrait chercher le défaut dans les données.
        page = Chargeur(self.d)('browse')
        self.assertIn('ui/pages/browse.html', page)
        self.assertIn('bundle.py', page)
        self.assertIn('<!DOCTYPE html>', page)

    def test_le_nom_manquant_est_echappe(self):
        page = Chargeur(self.d)('<script>')
        self.assertNotIn('<script>', page)


class TestGabaritDeBrowse(unittest.TestCase):
    """Le fichier réellement livré, pas un fichier de test."""

    def setUp(self):
        self.chemin = RACINE / 'ui' / 'pages' / 'browse.html'

    def test_le_gabarit_existe(self):
        self.assertTrue(self.chemin.is_file(), str(self.chemin))

    def test_il_porte_TOUS_les_marqueurs_que_le_serveur_remplit(self):
        txt = self.chemin.read_text(encoding='utf-8')
        for m in MARQUEURS:
            self.assertIn(m, txt, m)

    def test_le_serveur_ne_garde_plus_de_copie_en_dur(self):
        # Deux sources pour une même page, c'est la garantie qu'elles
        # divergeront — et qu'on éditera celle qui ne sert pas.
        noms = {c.id for n in ast.walk(ARBRE) if isinstance(n, ast.Assign)
                for c in n.targets if isinstance(c, ast.Name)}
        self.assertNotIn('BROWSE_PAGE', noms)

    def test_le_serveur_passe_bien_par_le_chargeur(self):
        self.assertIn("ui_page('browse')", SOURCE)


class TestBundle(unittest.TestCase):

    def test_le_bundle_cuit_les_pages_presentes(self):
        pages = bundle.cuire_les_pages()
        self.assertIn('browse', pages)
        self.assertEqual(pages['browse'],
                         (RACINE / 'ui' / 'pages' / 'browse.html')
                         .read_text(encoding='utf-8'))

    def test_le_marqueur_des_pages_existe_dans_le_serveur(self):
        # S'il disparaît, `bundle.py` s'arrête avec un message — mais autant
        # le savoir ici, avant de déployer.
        self.assertIn(bundle.MARQUEUR_PAGES, SOURCE)

    def test_un_dossier_sans_pages_ne_cuit_rien(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        ancien = bundle.UI_PAGES_DIR
        bundle.UI_PAGES_DIR = d / 'pages'
        try:
            self.assertEqual(bundle.cuire_les_pages(), {})
        finally:
            bundle.UI_PAGES_DIR = ancien


if __name__ == '__main__':
    unittest.main(verbosity=2)
