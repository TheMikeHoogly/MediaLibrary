#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_pages_composants.py` -- sans serveur.

Un banc d'observation se trompe de deux facons, et les deux sont graves :
il peut manquer une panne reelle, ou il peut declarer vert ce qu'il n'a
pas pu regarder. Les tests ci-dessous portent surtout sur la seconde.

SORTIE EN ASCII PUR.
"""

import re
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_pages_composants as V  # noqa: E402


FEUILLE = ('<style id="ui-components">.btn { min-height:44px }'
           '.btn--confirmer { } .btn--destructif { } .btn--discret { }'
           '</style>')
TOKENS = ('<style id="ui-shared">:root{--touch:44px}\n'
          'body { background: var(--salle); color: var(--texte);'
          ' font-family: var(--f-texte); }</style>')


def page(feuille=FEUILLE, style_page='<style>.x{}</style>', tokens=TOKENS,
         marqueur=''):
    return ('<html><head>' + marqueur + feuille + style_page + tokens +
            '</head><body></body></html>')


def faux_serveur(pages, redirections=None):
    """`redirections` : {chemin demande -> chemin realmente servi}."""
    redirections = redirections or {}
    def chercher(hote, port, chemin, delai=10):
        arrivee = redirections.get(chemin, chemin)
        if arrivee not in pages:
            raise urllib.error.HTTPError(chemin, 404, 'nope', None, None)
        v = pages[arrivee]
        if isinstance(v, Exception):
            raise v
        return v, arrivee
    return chercher


def lancer(pages, redirections=None):
    dit = []
    n = V.verifier('h', 1, ecrire=dit.append,
                   chercher=faux_serveur(pages, redirections))
    return n, "\n".join(dit)


# Bati depuis V.ADOPTANTES : une page de plus dans la convergence ne doit
# pas rendre ces tests faux -- ni, pire, les rendre verts pour rien.
TOUT_BON = dict([(c, page()) for c in V.ADOPTANTES]
                + [(c, page(feuille='', tokens=TOKENS))
                   for c in (V.TEMOIN,) + V.AUTRES + ('/ailleurs',)])


class LeCasNominal(unittest.TestCase):

    def test_tout_bon_rend_zero_faute(self):
        n, texte = lancer(TOUT_BON)
        self.assertEqual(n, 0, texte)
        self.assertIn("gardent le dernier mot", texte)


class CE_QU_ON_N_A_PAS_REGARDE_NE_COMPTE_PAS_POUR_VERT(unittest.TestCase):
    """Le mode de panne le plus cher : croire qu'on a observe.

    Les deux tests du bas sont nes d'un rouge OBSERVE, pas invente : au
    premier lancement reel, le temoin pointait sur une route inexistante et
    le banc a ecrit "rien n'a pu etre verifie" alors qu'il venait de lire et
    de juger bonnes les deux pages converties. Deux mensonges d'un coup --
    sur ce qu'il avait vu, et sur pourquoi il n'avait pas vu le reste.
    """

    def test_serveur_injoignable_compte_comme_faute(self):
        pages = dict(TOUT_BON)
        pages[V.ADOPTANTES[0]] = urllib.error.URLError('connexion refusee')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("SERVEUR MUET", texte)
        self.assertNotIn("gardent le dernier mot", texte)

    def test_une_route_404_se_dit_ROUTE_et_pas_SERVEUR(self):
        """Un 404 veut dire que le banc s'est trompe d'adresse ; un refus de
        connexion veut dire que le serveur est mort. Confondre les deux
        envoie chercher la panne au mauvais endroit."""
        pages = dict(TOUT_BON)
        del pages[V.TEMOIN]
        _n, texte = lancer(pages)
        self.assertIn("ROUTE MUETTE", texte)
        self.assertIn("HTTP 404", texte)
        self.assertNotIn("SERVEUR MUET", texte)

    def test_le_verdict_ne_dit_pas_RIEN_quand_il_a_lu_des_pages(self):
        pages = dict(TOUT_BON)
        del pages[V.TEMOIN]
        _n, texte = lancer(pages)
        self.assertIn("%d page(s) lue(s), 1 NON REGARDEE(S)"
                      % (len(V.ADOPTANTES) + len(V.AUTRES)), texte)
        self.assertIn("pas de preuve", texte)

    def test_et_il_nomme_la_page_qu_il_n_a_pas_pu_regarder(self):
        pages = dict(TOUT_BON)
        del pages[V.TEMOIN]
        _n, texte = lancer(pages)
        self.assertIn(V.TEMOIN, texte.split("NON REGARDEE(S)")[1])


class LeMarqueurRestant(unittest.TestCase):

    def test_un_marqueur_servi_est_un_grief(self):
        pages = dict(TOUT_BON)
        pages[V.ADOPTANTES[0]] = page(feuille='', marqueur=V.MARQUEUR)
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("marqueur est encore la", texte)

    def test_ni_marqueur_ni_feuille_est_aussi_un_grief(self):
        """La page ne passe peut-etre pas par _send_html du tout."""
        pages = dict(TOUT_BON)
        pages[V.ADOPTANTES[1]] = page(feuille='')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("pas de <style id=\"ui-components\">", texte)


class LaPageGardeLeDernierMot(unittest.TestCase):

    def test_feuille_APRES_le_style_de_la_page_est_un_grief(self):
        pages = dict(TOUT_BON)
        pages[V.ADOPTANTES[0]] = ('<html><head><style>.x{}</style>' + FEUILLE +
                            TOKENS + '</head></html>')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("perd la cascade", texte)

    def test_les_feuilles_a_id_ne_se_font_pas_passer_pour_celle_de_la_page(self):
        """`<style id="...">` n'est pas le style de la page : sinon le banc
        crierait a la cascade perdue sur une page parfaitement saine."""
        html = '<html><head>' + TOKENS + FEUILLE + '<style>.x{}</style></head>'
        self.assertEqual(V.style_de_la_page(html), html.index('<style>.x{}'))


class LaFeuilleDoitPorterLesRegles(unittest.TestCase):

    def test_une_feuille_videe_est_un_grief(self):
        pages = dict(TOUT_BON)
        pages[V.ADOPTANTES[0]] = page(feuille='<style id="ui-components"></style>')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("ne porte pas .btn", texte)

    def test_les_tokens_absents_sont_un_grief(self):
        """components.css est ecrit en var(--...) : sans tokens il rend vide."""
        pages = dict(TOUT_BON)
        pages[V.ADOPTANTES[1]] = page(tokens='')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("ui-shared", texte)


class LeTemoinProuveQueCEstUnOptIn(unittest.TestCase):

    def test_une_page_non_convertie_qui_recoit_la_feuille_est_un_grief(self):
        pages = dict(TOUT_BON)
        pages[V.TEMOIN] = page()
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("plus un opt-in", texte)

    def test_le_temoin_est_bien_une_page_NON_listee_comme_adoptante(self):
        self.assertNotIn(V.TEMOIN, V.ADOPTANTES)


class UNE_PAGE_QUI_REPOND_AILLEURS_N_EST_PAS_CETTE_PAGE(unittest.TestCase):
    """Troisieme rouge OBSERVE, le pire des trois.

    Le temoin pointait sur `/faces`, qui repond **302 vers /people**. urllib
    suit la redirection sans rien dire : le banc a ecrit « la page temoin
    (/faces) reste intacte » en ayant lu `/people`. Il a nomme une page et
    juge une autre -- et il l'a fait EN VERT.

    Un temoin sert a prouver qu'une page NON convertie ne recoit rien. Si le
    banc ne sait pas quelle page il a lue, le temoin ne temoigne de rien, et
    le vert qu'il rapporte est un vert emprunte.
    """

    def test_une_redirection_silencieuse_est_un_grief(self):
        n, texte = lancer(TOUT_BON, redirections={V.TEMOIN: '/ailleurs'})
        self.assertGreater(n, 0)
        self.assertIn("REPOND AILLEURS", texte)

    def test_le_verdict_ne_passe_pas_au_vert_dessus(self):
        _n, texte = lancer(TOUT_BON, redirections={V.TEMOIN: '/ailleurs'})
        self.assertNotIn("reste intacte", texte)

    def test_une_adoptante_redirigee_est_un_grief_aussi(self):
        n, texte = lancer(TOUT_BON,
                          redirections={V.ADOPTANTES[0]: V.ADOPTANTES[1]})
        self.assertGreater(n, 0)
        self.assertIn("REPOND AILLEURS", texte)

    def test_et_le_grief_NOMME_les_deux_chemins(self):
        _n, texte = lancer(TOUT_BON, redirections={V.TEMOIN: '/ailleurs'})
        self.assertIn(V.TEMOIN, texte)
        self.assertIn('/ailleurs', texte)


class LES_TROIS_UNIVERSELLES_ARRIVENT_D_UN_SEUL_ENDROIT(unittest.TestCase):
    """`body { background | color | font-family }` etait ecrit onze fois, a
    l'identique. Il l'est desormais une seule, dans `ui/base.css`.

    Ce que ce banc tient : la feuille commune les PORTE, et aucune page ne les
    redeclare. Le second point est le vrai : une page qui les reecrit gagne la
    cascade (son `<style>` precede `base.css`... non -- `base.css` est injecte
    a `</head>`, donc il gagne, et la page perd sa declaration SANS le savoir).
    Dans les deux sens, deux sources pour une meme decision, c'est la
    divergence qui recommence.
    """

    def test_la_feuille_partagee_les_porte(self):
        n, texte = lancer(TOUT_BON)
        self.assertEqual(n, 0, texte)

    def test_une_page_qui_redeclare_le_fond_est_un_grief(self):
        pages = dict(TOUT_BON)
        pages[V.ADOPTANTES[0]] = page(
            style_page='<style>body{background:#000}</style>')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("redeclare", texte)

    def test_une_feuille_partagee_SANS_les_universelles_est_un_grief(self):
        pages = dict(TOUT_BON)
        pages[V.TEMOIN] = page(feuille='',
                               tokens='<style id="ui-shared">:root{}</style>')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)
        self.assertIn("universelles", texte)

    def test_le_temoin_est_verifie_LUI_AUSSI(self):
        """Les universelles ne sont pas un opt-in : elles valent pour les onze
        pages, converties ou non."""
        pages = dict(TOUT_BON)
        pages[V.TEMOIN] = page(feuille='',
                               style_page='<style>body{color:#fff}</style>')
        n, texte = lancer(pages)
        self.assertGreater(n, 0)


class IlNeModifieRien(unittest.TestCase):

    def test_aucune_ecriture_dans_le_module(self):
        """`\\bopen\\(` et pas `open(` : sinon `urlopen(` fait rougir le test
        pour rien, et un test qui crie a tort finit par etre desactive."""
        source = Path(V.__file__).read_text(encoding='utf-8')
        for interdit in (r'\.unlink\(', r'os\.remove\(', r'\bopen\(',
                         r'\.write_text\(', r'\.write\(', r'method='):
            self.assertIsNone(
                re.search(interdit, source),
                interdit + " dans une famille verifier_ : elle observe, "
                "elle n'agit pas")


if __name__ == '__main__':
    unittest.main(verbosity=0)
