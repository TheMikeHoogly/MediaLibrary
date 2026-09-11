#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L'instrument qui garde HTTP/1.1 : est-ce qu'il voit ce qu'il prétend voir ?

`verifier_content_length.py` autorise un changement risqué — passer le serveur
en HTTP/1.1, où une réponse sans longueur SUSPEND la page. Un instrument qui
rend « aucun grief » sans regarder au bon endroit donnerait ce feu vert à
tort. Ce banc lui montre donc des cas écrits exprès, conformes et fautifs.

Règle 6 du projet : un outil qui JUGE ne témoigne pas de lui-même.
"""

import textwrap
import unittest

from verifier_content_length import examiner


def _code(corps):
    return textwrap.dedent('class H:\n' + textwrap.indent(textwrap.dedent(corps), '    '))


class CeQuIlAccepte(unittest.TestCase):
    def _griefs(self, corps):
        return [g[0] for g in examiner(_code(corps))['griefs']]

    def test_une_longueur_posee_entre_les_deux(self):
        self.assertEqual(self._griefs('''
            def bon(self):
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
        '''), [])

    def test_la_casse_de_l_entete_ne_compte_pas(self):
        self.assertEqual(self._griefs('''
            def bon(self):
                self.send_response(200)
                self.send_header('content-LENGTH', '12')
                self.end_headers()
        '''), [])

    def test_un_decoupage_en_morceaux(self):
        self.assertEqual(self._griefs('''
            def bon(self):
                self.send_response(200)
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()
        '''), [])

    def test_un_code_SANS_CORPS(self):
        for code in (204, 304, 100):
            self.assertEqual(self._griefs(f'''
                def bon(self):
                    self.send_response({code})
                    self.end_headers()
            '''), [], code)

    def test_un_code_CONDITIONNEL_dont_les_deux_branches_ont_un_corps(self):
        self.assertEqual(self._griefs('''
            def bon(self):
                self.send_response(206 if partial else 200)
                self.send_header('Content-Length', str(n))
                self.end_headers()
        '''), [])


class CeQuIlSIGNALE(unittest.TestCase):
    def _griefs(self, corps):
        return [(g[0], g[2]) for g in examiner(_code(corps))['griefs']]

    def test_une_redirection_nue(self):
        self.assertEqual(self._griefs('''
            def faux(self):
                self.send_response(302)
                self.send_header('Location', '/x')
                self.end_headers()
        '''), [('faux', [302])])

    def test_une_longueur_posee_APRES_end_headers_ne_compte_pas(self):
        self.assertEqual(self._griefs('''
            def faux(self):
                self.send_response(200)
                self.end_headers()
                self.send_header('Content-Length', '5')
        '''), [('faux', [200])])

    def test_une_longueur_d_une_AUTRE_reponse_ne_couvre_pas_celle_ci(self):
        griefs = self._griefs('''
            def deux(self):
                self.send_response(200)
                self.send_header('Content-Length', '5')
                self.end_headers()
                self.send_response(302)
                self.end_headers()
        ''')
        self.assertEqual(griefs, [('deux', [302])])

    def test_un_code_conditionnel_dont_UNE_branche_a_un_corps(self):
        self.assertEqual(self._griefs('''
            def faux(self):
                self.send_response(304 if frais else 200)
                self.end_headers()
        '''), [('faux', [304, 200])])

    def test_une_fonction_IMBRIQUEE_est_comptee_UNE_fois(self):
        r = examiner(_code('''
            def dehors(self):
                def dedans():
                    self.send_response(302)
                    self.end_headers()
                dedans()
        '''))
        self.assertEqual([g[0] for g in r['griefs']], ['dedans'])
        self.assertEqual(r['vues'], 1)


class SonEtendue(unittest.TestCase):
    def test_il_dit_ce_qu_il_a_regarde(self):
        r = examiner(_code('''
            def a(self):
                self.send_response(200)
                self.send_header('Content-Length', '1')
                self.end_headers()

            def b(self):
                self.send_response(302)
                self.end_headers()

            def c(self):
                pass
        '''))
        self.assertEqual((r['vues'], r['jugees'], r['conformes']), (2, 2, 1))
        self.assertGreaterEqual(r['fonctions'], 3)

    def test_un_end_headers_ORPHELIN_est_ecarte_et_DIT(self):
        r = examiner(_code('''
            def orpheline(self):
                self.end_headers()
        '''))
        self.assertEqual(r['griefs'], [])
        self.assertEqual([e[0] for e in r['ecartees']], ['orpheline'])


if __name__ == '__main__':
    unittest.main()
