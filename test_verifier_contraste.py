#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_contraste.py` -- sans navigateur, sans page.

Un banc qui mesure un plancher se trompe de deux facons : il peut rater un
couple sous le seuil, et il peut declarer vert un couple qu'il n'a pas su
resoudre. Les tests portent d'abord sur la seconde.

Les valeurs de reference viennent de la formule WCAG 2.1 (relative luminance,
(L1+0.05)/(L2+0.05)) et sont verifiables a la main : noir sur blanc = 21:1,
une couleur sur elle-meme = 1:1.

SORTIE EN ASCII PUR.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_contraste as K  # noqa: E402

TOKENS = """:root {
  --salle: #0C0B0A; --salle-2: #14120F; --salle-3: #1C1916; --salle-4: #24201D;
  --papier: #EDE7DC; --papier-2: #DDD5C6;
  --encre: #C8321E; --fixateur: #4A8C7B;
  --texte: #F2EDE6; --texte-papier: #1A1714;
  --r-md: 6px; --touch: 44px;
}"""


class LaFormuleEstCELLE_DE_WCAG(unittest.TestCase):

    def test_noir_sur_blanc_vaut_21(self):
        self.assertAlmostEqual(K.contraste('#000000', '#ffffff'), 21.0, 2)

    def test_une_couleur_sur_elle_meme_vaut_1(self):
        self.assertAlmostEqual(K.contraste('#4A8C7B', '#4A8C7B'), 1.0, 6)

    def test_l_ordre_des_deux_couleurs_ne_change_rien(self):
        self.assertAlmostEqual(K.contraste('#C8321E', '#0C0B0A'),
                               K.contraste('#0C0B0A', '#C8321E'), 9)

    def test_la_forme_courte_a_trois_chiffres_est_lue(self):
        self.assertAlmostEqual(K.contraste('#fff', '#000000'), 21.0, 2)


class LesTokensSeResolvent(unittest.TestCase):

    def test_un_var_pointe_bien_sa_valeur(self):
        t = K.lire_tokens(TOKENS)
        self.assertEqual(K.resoudre('var(--salle)', t), '#0c0b0a')

    def test_ce_qui_n_est_PAS_une_couleur_n_entre_pas_dans_la_table(self):
        """`--touch: 44px` n'est pas une couleur : le prendre pour un fond
        ferait planter la luminance sur un nombre de pixels."""
        t = K.lire_tokens(TOKENS)
        self.assertNotIn('--touch', t)
        self.assertNotIn('--r-md', t)

    def test_un_var_INCONNU_rend_None_au_lieu_d_un_faux_vert(self):
        self.assertIsNone(K.resoudre('var(--nexiste-pas)',
                                     K.lire_tokens(TOKENS)))

    def test_un_var_qui_se_pointe_elle_meme_ne_boucle_pas(self):
        self.assertIsNone(K.resoudre('var(--a)', {'--a': 'var(--a)'}))

    def test_une_couleur_que_l_instrument_ne_sait_pas_lire_rend_None(self):
        for v in ('rgb(200 50 30)', 'color-mix(in srgb, red, blue)', 'hsl(0 0 0)'):
            self.assertIsNone(K.resoudre(v, {}), v)


class UN_FOND_TRANSPARENT_PREND_LE_PIRE_CAS(unittest.TestCase):
    """Un bouton a contour ne choisit pas la surface sur laquelle il se pose.
    Le juger sur la plus favorable serait se mentir exactement la ou le
    composant est le plus fragile."""

    def test_la_famille_se_lit_dans_le_NOM_du_token_pas_dans_les_pixels(self):
        """`--encre` est sombre et vit pourtant sur le noir : deviner la
        famille a la luminance donnait la mauvaise reponse (rouge observe)."""
        self.assertEqual(K.famille('var(--texte-papier)')[0],
                         K.SURFACES_CLAIRES)
        self.assertEqual(K.famille('var(--texte)')[0], K.SURFACES_SOMBRES)

    def test_un_token_qui_ne_NOMME_pas_sa_surface_est_dit_INDETERMINE(self):
        noms, indetermine = K.famille('var(--encre)')
        self.assertTrue(indetermine)
        self.assertIn('--salle', noms)
        self.assertIn('--papier', noms)

    def test_le_pire_cas_est_retenu(self):
        t = K.lire_tokens(TOKENS)
        r, surface, indet = K.juger('.btn--destructif', '#C8321E',
                                    'transparent', t, 'var(--encre)')
        self.assertTrue(indet)
        self.assertLessEqual(r, K.contraste('#C8321E', t['--salle']))
        self.assertIsNotNone(surface)

    def test_un_texte_de_papier_est_juge_sur_le_PAPIER(self):
        t = K.lire_tokens(TOKENS)
        _r, surface, _i = K.juger('.btn--discret', '#1A1714', 'transparent',
                                  t, 'var(--texte-papier)')
        self.assertIn(surface, K.SURFACES_CLAIRES)


class CE_QU_IL_NE_SAIT_PAS_EST_COMPTE(unittest.TestCase):

    def test_un_couple_non_resolu_est_LISTE_pas_ignore(self):
        css = ".x { color: rgb(1 2 3); background: var(--salle); }"
        _cps, indecis = K.couples(css, K.lire_tokens(TOKENS))
        self.assertEqual(len(indecis), 1)

    def test_le_rapport_les_NOMME(self):
        css = ".x { color: rgb(1 2 3); background: var(--salle); }"
        dit = []
        K.verifier.__globals__  # noqa
        cps, indecis = K.couples(css, K.lire_tokens(TOKENS))
        self.assertIn('.x', indecis[0][0])


class ILNeCorrigeRien(unittest.TestCase):

    def test_aucune_ecriture_dans_le_module(self):
        import re
        source = Path(K.__file__).read_text(encoding='utf-8')
        for interdit in (r'\bopen\(', r'\.write_text\(', r'\.unlink\(',
                         r'os\.remove\('):
            self.assertIsNone(re.search(interdit, source), interdit)


class SurLeVraiSysteme(unittest.TestCase):
    """Le rouge qui a fait naitre ce banc, tenu comme un fait."""

    def test_blanc_sur_fixateur_est_SOUS_le_seuil(self):
        self.assertLess(K.contraste('#ffffff', '#4A8C7B'), K.SEUIL_TEXTE)

    def test_encre_sur_salle_est_SOUS_le_seuil(self):
        self.assertLess(K.contraste('#C8321E', '#0C0B0A'), K.SEUIL_TEXTE)

    def test_mais_texte_sur_salle_3_tient_largement(self):
        self.assertGreater(K.contraste('#F2EDE6', '#1C1916'), 10)

    def test_et_le_survol_neuf_ne_casse_pas_le_texte(self):
        """`--salle-4` est une surface : le texte doit y rester lisible."""
        self.assertGreater(K.contraste('#F2EDE6', '#24201D'), K.SEUIL_TEXTE)


if __name__ == '__main__':
    unittest.main(verbosity=0)
