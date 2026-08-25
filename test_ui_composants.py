#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de l'ADOPTION du design system dans `server.py` -- SUR LE CODE DE PROD.

Pourquoi ce fichier
-------------------
`components.css` redefinit `.btn`, `.chip`, `.feuille`. L'injecter partout
ecraserait les onze pages historiques ; ne l'injecter nulle part le laisse
mort. Le mecanisme d'ADOPTION est donc la piece qui porte tout le chantier de
convergence, et il porte trois choses qu'aucune regle pure ne montre :

1. **Le marqueur est remplace, MEME par du vide.** Un `<!--UI:components-->`
   qui resterait dans le HTML serait un commentaire muet : on ne saurait pas si
   la page a adopte ou si `ui/` manquait. C'est le mode de panne que ce projet
   paye le plus cher.
2. **La page garde le DERNIER MOT.** Le marqueur vit AVANT le `<style>` de la
   page, donc la feuille commune arrive AVANT lui. Si l'injection se faisait a
   `</head>` comme tokens/base, la page perdrait la cascade au moment meme ou
   elle converge, et n'aurait plus aucun moyen de garder une exception le temps
   de la migration.
3. **Une page qui n'a PAS adopte ne recoit rien.** C'est toute la difference
   entre un opt-in et une injection globale.

Comme les autres tests de greffe, ce module lit `server.py` sans l'importer :
le serveur tire torch et insightface, un test n'a pas a payer ca.
"""

import ast
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py -- l'adoption du "
                         "design system a bouge, ce test doit etre relu.")


class FausseReponse:
    """Un `self` de handler : juste ce que `_send_html` touche."""

    def __init__(self):
        self.corps = None

    def send_response(self, code):
        self.code = code

    def send_header(self, *a):
        pass

    def end_headers(self):
        pass

    @property
    def wfile(self):
        rep = self

        class W:
            def write(self, data):
                rep.corps = data.decode('utf-8')
        return W()


def envoyer(html, composants='<style id="ui-components">.btn{}</style>'):
    ns = {
        'APP_NAV_CSS': '<style id="appnav-css"></style>',
        'APP_NAV_HTML': '<nav></nav>',
        'SUJETS_NAV_HTML': '<nav id="sujets"></nav>',
        'ui_shared_css': lambda: '<style id="ui-shared"></style>',
        'ui_composants_css': lambda: composants,
        '_UI_COMPOSANTS_MARQUEUR': '<!--UI:components-->',
    }
    exec(compile(ast.Module([_noeud('_send_html')], []), str(SERVER), 'exec'),
         ns)
    r = FausseReponse()
    ns['_send_html'](r, html)
    return r.corps


PAGE = ('<html><head><!--UI:components-->\n<style>.btn{color:red}</style>'
        '</head><body></body></html>')
PAGE_SANS = '<html><head><style>.btn{color:red}</style></head><body></body>'


class LeMarqueurEstToujoursRemplace(unittest.TestCase):

    def test_une_page_qui_a_adopte_recoit_la_feuille(self):
        sortie = envoyer(PAGE)
        self.assertIn('id="ui-components"', sortie)
        self.assertNotIn('<!--UI:components-->', sortie)

    def test_meme_quand_la_feuille_est_VIDE_le_marqueur_disparait(self):
        """`ui/` absent : le serveur demarre quand meme (invariant zero
        dependance) et la page rend avec son CSS a elle. Mais le marqueur ne
        doit pas rester : un commentaire muet ne se distingue pas d'un oubli."""
        sortie = envoyer(PAGE, composants='')
        self.assertNotIn('<!--UI:components-->', sortie)
        self.assertNotIn('id="ui-components"', sortie)

    def test_une_page_qui_n_a_PAS_adopte_ne_recoit_rien(self):
        sortie = envoyer(PAGE_SANS)
        self.assertNotIn('id="ui-components"', sortie)


class LaPageGardeLeDernierMot(unittest.TestCase):

    def test_la_feuille_commune_arrive_AVANT_le_style_de_la_page(self):
        """Sinon la page perd la cascade au moment ou elle converge."""
        sortie = envoyer(PAGE)
        self.assertLess(sortie.index('id="ui-components"'),
                        sortie.index('<style>.btn{color:red}'))

    def test_et_APRES_les_tokens_dont_elle_depend(self):
        """`components.css` utilise var(--salle-3), var(--touch)... : les tokens
        doivent etre la. Ils sont injectes a `</head>`, donc apres -- ce qui
        marche parce qu'une variable CSS se resout a l'USAGE, pas a la
        declaration. Ce test tient le fait, pour qu'on ne le redecouvre pas."""
        sortie = envoyer(PAGE)
        self.assertIn('id="ui-shared"', sortie)


# La liste des pages converties vit ICI et dans `verifier_pages_composants.py`
# (routes). Une page qui entre dans la convergence doit entrer dans les deux :
# la premiere prouve le fichier, la seconde prouve le serveur qui le sert.
CONVERTIES = ('residu', 'tranche', 'subjects', 'people', 'pets')


class LesPagesConverties(unittest.TestCase):
    """`residu` et `tranche` le 25/08 : elles avaient ecrit le `.btn` canonique
    a l'identique, toutes les deux, sans se concerter. `subjects` le meme jour :
    elle l'ecrivait aussi pareil, sous DEUX AUTRES NOMS (`.btn.prim`,
    `.btn.warn`) -- meme idee, meme valeurs, vocabulaire different. C'est la
    forme la plus couteuse de divergence : elle ne se voit pas a l'ecran."""

    def _page(self, nom):
        return (SERVER.parent / 'ui' / 'pages' / (nom + '.html')).read_text(
            encoding='utf-8')

    def test_elles_posent_le_marqueur(self):
        for nom in CONVERTIES:
            self.assertIn('<!--UI:components-->', self._page(nom), nom)

    def test_elles_n_ont_plus_de_btn_a_elles(self):
        """Deux definitions du meme bouton, c'est la divergence qui recommence."""
        for nom in CONVERTIES:
            css = self._page(nom)
            for redite in ('\n.btn {', '\n  .btn{', '\n.btn--confirmer {',
                           '.btn.prim{', '.btn.warn{'):
                self.assertNotIn(redite, css, nom + " redeclare " + redite)

    def test_le_vocabulaire_est_UN(self):
        """`.prim` / `.warn` etaient des synonymes locaux du canonique. Les
        laisser vivre a cote, c'est garder deux mots pour une idee."""
        for nom in CONVERTIES:
            html = self._page(nom)
            for vieux in ('btn prim', 'btn warn', 'btn primary', 'btn danger'):
                self.assertNotIn(vieux, html, nom + " porte encore " + vieux)

    def test_le_marqueur_vient_AVANT_leur_style(self):
        for nom in CONVERTIES:
            html = self._page(nom)
            self.assertLess(html.index('<!--UI:components-->'),
                            html.index('<style'), nom)

    def test_components_css_porte_bien_ce_qu_elles_ont_cede(self):
        css = (SERVER.parent / 'ui' / 'components.css').read_text(
            encoding='utf-8')
        for regle in ('.btn {', '.btn--confirmer', '.btn--destructif',
                      '.btn--discret', '.btn kbd'):
            self.assertIn(regle, css, regle + " manque a components.css")


class LeBundleSuit(unittest.TestCase):

    def test_bundle_cuit_aussi_les_composants(self):
        """Sans ca, un dist sans `ui/` servirait les pages converties SANS
        leurs boutons -- une page nue qui a l'air d'un bug de donnees."""
        b = (SERVER.parent / 'bundle.py').read_text(encoding='utf-8')
        self.assertIn('MARQUEUR_COMPOSANTS', b)
        self.assertIn('construire_composants', b)

    def test_le_marqueur_que_bundle_cherche_existe_dans_server(self):
        self.assertIn('_UI_COMPOSANTS_CACHE = {"css": None, "sig": None}',
                      SOURCE)


if __name__ == '__main__':
    unittest.main(verbosity=0)
