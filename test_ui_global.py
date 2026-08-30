#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la BRIQUE JS COMMUNE (`ui/global.js`) et de la recherche dans la
barre -- SUR LE CODE DE PROD, sans importer `server.py` (torch, insightface).

Ce qu'on prouve, et pourquoi c'est ce qu'il faut prouver :

1. **La brique arrive juste APRES la barre**, une seule fois, et avant </body>
   quand une page n'a pas de barre. Apres la barre, parce que le sablier doit
   enrober `fetch` AVANT les scripts de la page ; une seule fois, parce que
   deux enrobages compteraient chaque requete deux fois.
2. **Le champ de recherche est un vrai formulaire GET vers /files, nomme q.**
   C'est ce qui le fait marcher sans JS : Entree suffit, et la galerie lit
   deja `?q=` (page de resultats IA, cote serveur).
3. **La barre n'a plus de script inline** : l'onglet actif et le sablier
   vivent dans global.js -- une source, pas deux. Et global.js les porte.
4. **server et bundle assemblent le MEME bloc** (garde-fou anti-derive, comme
   pour le CSS), et le bundle le cuit.
5. **Le `/` ne vole pas le clavier a un champ** : la garde est dans la source.
"""

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SERVER = HERE / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)
GLOBAL_JS = (HERE / "ui" / "global.js").read_text(encoding="utf-8")


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py")


def _assign(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == nom for t in n.targets):
            return n
    raise AssertionError(nom + " introuvable dans server.py")


def _charger(*noms):
    ns = {'Path': Path, 'SCRIPT_DIR': HERE}
    for nom in noms:
        n = _noeud(nom) if not nom.isupper() else _assign(nom)
        exec(compile(ast.Module([n], []), str(SERVER), 'exec'), ns)
    return ns


NS = _charger('APP_NAV_HTML', 'UI_DIR', '_UI_JS_FILES', '_UI_JS_CACHE',
              '_js_signature', 'ui_shared_js', 'injecter_js_commun')
injecter = NS['injecter_js_commun']
NAV = NS['APP_NAV_HTML']
BLOC = '<script id="ui-global">x</script>'


class LaBriqueArriveApresLaBarre(unittest.TestCase):

    def test_apres_la_barre_et_avant_le_reste_de_la_page(self):
        page = '<html><body>' + NAV + '<script>page()</script></body></html>'
        out = injecter(page, BLOC)
        self.assertEqual(out.count('id="ui-global"'), 1)
        self.assertLess(out.index('</nav>'), out.index('id="ui-global"'))
        self.assertLess(out.index('id="ui-global"'), out.index('page()'))

    def test_apres_la_barre_meme_si_la_page_a_un_nav_a_elle_AVANT(self):
        page = ('<html><body><nav class="mienne">a</nav>' + NAV
                + '<script>page()</script></body></html>')
        out = injecter(page, BLOC)
        self.assertLess(out.index('class="appnav"'), out.index('id="ui-global"'))
        self.assertLess(out.index('id="ui-global"'), out.index('page()'))

    def test_jamais_deux_fois(self):
        page = '<html><body>' + NAV + '</body></html>'
        une = injecter(page, BLOC)
        self.assertEqual(injecter(une, BLOC), une)
        self.assertEqual(une.count('id="ui-global"'), 1)

    def test_sans_barre_avant_body(self):
        page = '<html><body><p>connexion</p></body></html>'
        out = injecter(page, BLOC)
        self.assertTrue(out.endswith(BLOC + '</body></html>'))

    def test_bloc_vide_ne_touche_a_rien(self):
        page = '<html><body>' + NAV + '</body></html>'
        self.assertEqual(injecter(page, ''), page)

    def test_send_html_appelle_bien_la_brique(self):
        src = ast.get_source_segment(SOURCE, _noeud('_send_html'))
        self.assertIn('injecter_js_commun(html_str, ui_shared_js())', src)


class LeChampDeRechercheEstUnVraiFormulaire(unittest.TestCase):

    def test_get_vers_files_nomme_q(self):
        self.assertIn('<form class="appnav-q" role="search" action="/files" method="get">', NAV)
        self.assertIn('name="q"', NAV)
        self.assertIn('type="search"', NAV)

    def test_il_a_une_etiquette_pour_le_lecteur_d_ecran(self):
        self.assertIn('<label class="hors-ecran" for="appnav-q">', NAV)
        self.assertIn('id="appnav-q"', NAV)

    def test_le_bouton_est_un_bouton_avec_un_nom(self):
        self.assertIn('<button type="submit" aria-label="Chercher">', NAV)


class LaBarreN_aPlusDeScriptInline(unittest.TestCase):

    def test_zero_script_dans_la_barre(self):
        self.assertNotIn('<script', NAV)

    def test_global_js_porte_les_trois_roles(self):
        self.assertIn(".appnav a.tab", GLOBAL_JS)          # onglet actif
        self.assertIn("'/people'", GLOBAL_JS)              # fusion Sujets
        self.assertIn(".netbusy", GLOBAL_JS)               # sablier
        self.assertIn("window.fetch", GLOBAL_JS)
        self.assertIn(".appnav-q", GLOBAL_JS)              # la recherche
        self.assertIn("ev.key !== '/'", GLOBAL_JS)         # le raccourci

    def test_le_slash_ne_vole_pas_un_champ(self):
        self.assertIn("tag === 'input' || tag === 'textarea'", GLOBAL_JS)
        self.assertIn("isContentEditable", GLOBAL_JS)

    def test_masque_sur_files(self):
        self.assertIn("p.indexOf('/files') === 0", GLOBAL_JS)

    def test_le_sablier_ne_s_enrobe_pas_deux_fois(self):
        self.assertIn("window.fetch.__uiGlobal", GLOBAL_JS)


class ServerEtBundleAccordent(unittest.TestCase):

    def test_meme_bloc(self):
        import bundle
        self.assertEqual(NS['ui_shared_js'](), bundle.construire_js())
        self.assertEqual(bundle.UI_JS_FILES, NS['_UI_JS_FILES'])

    def test_le_bloc_est_un_script_id_ui_global_qui_porte_global_js(self):
        bloc = NS['ui_shared_js']()
        self.assertTrue(bloc.startswith('<script id="ui-global">'))
        self.assertTrue(bloc.endswith('</script>'))
        self.assertIn('/* global.js */', bloc)
        # et aucun </script> de la source ne ferme le bloc a mi-chemin
        self.assertEqual(bloc.count('</script>'), 1)

    def test_le_marqueur_du_bundle_existe_dans_server(self):
        import bundle
        self.assertIn(bundle.MARQUEUR_JS, SOURCE)


if __name__ == '__main__':
    unittest.main(verbosity=1)
