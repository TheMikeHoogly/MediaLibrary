#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests des GABARITS de pages de `server.py` — purs, par ANALYSE DU SOURCE.

Pourquoi ce fichier existe
──────────────────────────
Les sept pages sont des chaînes littérales trouées de marqueurs `__NOM__` que
le routeur remplace un par un. Ajouter un marqueur dans la page et oublier son
`.replace()` ne casse RIEN côté Python : la page part telle quelle, et c'est le
NAVIGATEUR qui meurt — `var X = __SEARCHMETA__;` est une erreur de syntaxe qui
emporte tout le script de la galerie. Panne muette côté serveur, page morte
côté client : exactement la forme d'erreur que le projet paie le plus cher.

Ce module lit `server.py` **sans l'importer** (`import server` construit les
stores et ouvre `photos.db` — l'écrivain unique est le serveur, invariant du
projet). Il travaille donc sur l'AST : les constantes `*_PAGE` d'un côté, tous
les `.replace('__X__', …)` du fichier de l'autre.

Il vérifie aussi que le JavaScript de chaque page PARSE, quand `node` est
disponible — sinon le test se déclare ignoré plutôt que vert.
"""
import ast
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest

import ui_gabarits

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
# Un marqueur n'est jamais precede d'un point : `window.__BROWSE_CTX__` est un
# VRAI identifiant JS, pas un trou a remplir. Sans ce garde, le test signalait un
# manquant qui n'en etait pas — et un test qui crie a tort finit ignore.
MARQUEUR = re.compile(r"(?<![.\w])__[A-Z][A-Z0-9_]*__")


def _arbre():
    with io.open(SERVER, encoding="utf-8") as f:
        return ast.parse(f.read())


def _pages(arbre=None):
    """{nom: texte} des gabarits — désormais lus dans `ui/pages/` (point 7).

    Les pages ont quitté `server.py` ; les CLÉS gardent l'ancien nom de
    constante (`GALLERY_PAGE`…), qui reste la façon dont ce projet désigne
    chaque page. `arbre` est accepté et ignoré : la signature ne change pas
    pour les appelants."""
    return ui_gabarits.tous()


def _remplaces(arbre):
    """Marqueurs qui apparaissent en 1er argument d'un `.replace(...)`."""
    out = set()
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "replace" and n.args
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            out.update(MARQUEUR.findall(n.args[0].value))
    return out


class TestMarqueurs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.arbre = _arbre()
        cls.pages = _pages(cls.arbre)
        cls.remplaces = _remplaces(cls.arbre)

    def test_les_pages_sont_trouvees(self):
        """Si ce test tombe, les autres ne mesurent plus rien (0 page = 0
        marqueur manquant = vert trompeur)."""
        self.assertIn("GALLERY_PAGE", self.pages)
        self.assertGreaterEqual(len(self.pages), 7)

    def test_tout_marqueur_de_page_a_son_replace(self):
        manquants = {}
        for nom, texte in self.pages.items():
            trous = set(MARQUEUR.findall(texte)) - self.remplaces
            if trous:
                manquants[nom] = sorted(trous)
        self.assertEqual(manquants, {},
                         "marqueur sans .replace() : la page part avec le trou "
                         "et le navigateur meurt sur une erreur de syntaxe")

    def test_searchmeta_est_bien_du_json(self):
        """`__SEARCHMETA__` est injecté dans une expression JS : il DOIT être
        produit par `json.dumps`, jamais par un `str()` de dict Python (guillemets
        simples, `None`, `True` — trois façons de casser le script)."""
        with io.open(SERVER, encoding="utf-8") as f:
            src = f.read()
        i = src.index("'__SEARCHMETA__'")
        self.assertIn("json.dumps", src[i:i + 200])


class TestTriDeLaGalerie(unittest.TestCase):
    """SENTINELLES, pas un test de comportement — à lire comme tel.

    Le tri de la galerie vit dans une chaîne littérale : le faire tourner
    exigerait un DOM, donc une dépendance que le projet s'interdit. Ces tests
    vérifient donc que le CORRECTIF EST LÀ, pas qu'il ordonne juste ; c'est
    l'observation en réel qui juge l'ordre. Ils tombent si quelqu'un remet la
    règle d'avant — et c'est tout ce qu'ils promettent.
    """

    @classmethod
    def setUpClass(cls):
        cls.page = _pages(_arbre())["GALLERY_PAGE"]

    def test_les_photos_sans_date_sont_separees_du_tri_par_date(self):
        self.assertIn("function sansDate(f)", self.page)
        self.assertIn("muettes", self.page)

    def test_plus_de_reverse_global_sur_le_tri_par_date(self):
        """`s.reverse()` appliqué à TOUTE la liste remettait les muettes en
        tête au reclic : c'est exactement le geste qu'on ne veut plus."""
        self.assertNotIn("if (!sortAsc) s.reverse();\n    sorted = s;",
                         self.page)

    def test_le_compte_des_sans_date_est_dit(self):
        self.assertIn("sans date connue, en fin de liste", self.page)


class TestJavaScriptParse(unittest.TestCase):
    """Le JS de chaque page parse-t-il ? (ignoré si `node` est absent)"""

    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node") or shutil.which("nodejs")
        cls.pages = _pages(_arbre())

    def test_chaque_page_parse(self):
        if not self.node:
            self.skipTest("node absent — vérification JS non faite (pas verte)")
        # Les marqueurs sont remplacés par une valeur JS neutre : on teste la
        # SYNTAXE de la page, pas les données du jour.
        neutre = {"__FILE_JSON__": "[]", "__TAGDATA__": "{}", "__MOTIFS__": "{}",
                  "__SEARCHMETA__": "{}", "__TAGGED__": "0", "__REC__": "0",
                  "__HASSUBS__": "0", "__DIRQ__": '""', "__SEARCHQ__": '""',
                  "__FOLDERS__": "", "__JOURQ__": '""', "__ANNEEQ__": '""',
                  "__CTX__": "null"}
        for nom, texte in sorted(self.pages.items()):
            for m in set(MARQUEUR.findall(texte)):
                texte = texte.replace(m, neutre.get(m, '""'))
            for i, bloc in enumerate(re.findall(
                    r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
                    texte, re.S)):
                if not bloc.strip():
                    continue
                with tempfile.NamedTemporaryFile("w", suffix=".js",
                                                 delete=False,
                                                 encoding="utf-8") as f:
                    f.write(bloc)
                    chemin = f.name
                try:
                    r = subprocess.run([self.node, "--check", chemin],
                                       capture_output=True, text=True)
                    self.assertEqual(
                        r.returncode, 0,
                        f"{nom}, script #{i} ne parse pas :\n{r.stderr[:800]}")
                finally:
                    os.unlink(chemin)


if __name__ == "__main__":
    unittest.main(verbosity=2)
