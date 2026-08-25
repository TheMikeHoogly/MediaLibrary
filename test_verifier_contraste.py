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


class UN_COMMENTAIRE_AVALE_LE_TOKEN_QUI_LE_SUIT(unittest.TestCase):
    """Rouge OBSERVE, et le plus retors de la journee.

    J'ai ecrit au-dessus de `--fixateur` un commentaire qui contenait la
    phrase « en bordure sur --salle : 4,33:1 ». Le lecteur de tokens cherche
    `--nom : valeur ;` SANS retirer les commentaires : il a vu `--salle`,
    puis a avale tout le texte jusqu'au premier `;` -- c'est-a-dire la
    declaration `--fixateur` elle-meme. Le token a disparu de la table.

    **Et le banc est passe au VERT.** Ses trois couples devenus irresolubles
    sont tombes dans « non decidables », le verdict a dit « le plancher tient
    sur tout ce qui est declare », et le code de sortie valait 0. Trois
    couples avaient cesse d'etre mesures et rien ne criait.

    Meme lecon que sur la preuve de cascade, deux fois deja : un commentaire
    est de la prose, et il faut le retirer AVANT de lire.
    """

    def test_un_commentaire_ne_mange_plus_le_token_suivant(self):
        css = (":root {\n"
               "  /* en bordure sur --salle : 4,33:1, bien au-dessus */\n"
               "  --fixateur: #448172;\n}")
        self.assertEqual(K.lire_tokens(css).get('--fixateur'), '#448172')

    def test_un_faux_token_cite_dans_un_commentaire_n_entre_pas(self):
        css = ":root { /* --invente: #FF0000; */ --vrai: #00FF00; }"
        t = K.lire_tokens(css)
        self.assertNotIn('--invente', t)
        self.assertEqual(t.get('--vrai'), '#00FF00')

    def test_un_commentaire_n_ecrase_pas_un_token_deja_lu(self):
        css = ":root { --salle: #0C0B0A;\n /* --salle : 4,33:1 */\n --x: #FFF; }"
        self.assertEqual(K.lire_tokens(css).get('--salle'), '#0C0B0A')


class UN_COUPLE_NON_MESURE_N_EST_PAS_UN_VERT(unittest.TestCase):
    """Le defaut de fond, et il precedait le commentaire fautif.

    « Le plancher AA tient sur tout ce qui est declare » plus un code 0, avec
    quatre couples listes juste au-dessus comme non decidables : c'est la
    troncature silencieuse deguisee en exhaustivite. Un banc qui ne sait pas
    ne rend pas vert.
    """

    def test_un_non_decidable_empeche_le_code_zero(self):
        css = ".x { color: rgb(1 2 3); background: var(--salle); }"
        io_dit = []
        n = K.verifier_css(css, K.lire_tokens(TOKENS), ecrire=io_dit.append)
        self.assertGreater(n, 0)

    def test_et_le_verdict_ne_dit_pas_que_TOUT_tient(self):
        css = ".x { color: rgb(1 2 3); background: var(--salle); }"
        dit = []
        K.verifier_css(css, K.lire_tokens(TOKENS), ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertNotIn("le plancher AA tient", texte)

    def test_tout_resolu_et_tout_au_dessus_rend_bien_zero(self):
        css = (".x { color: var(--texte); background: var(--salle-3); }")
        dit = []
        n = K.verifier_css(css, K.lire_tokens(TOKENS), ecrire=dit.append)
        self.assertEqual(n, 0, "\n".join(dit))

    def test_le_rapport_dit_sa_PORTEE(self):
        """Il ne mesure que components.css : les couleurs ecrites dans les
        onze pages ne sont pas jugees. Le taire ferait lire un vert partiel
        comme un vert general."""
        dit = []
        K.verifier_css(".x { color: var(--texte); background: var(--salle); }",
                       K.lire_tokens(TOKENS), ecrire=dit.append)
        self.assertIn("components.css", "\n".join(dit))


class CE_QUI_EST_HORS_PORTEE_SE_DECLARE(unittest.TestCase):
    """Il reste un cas qu'aucun calcul ne tranche : `.vue__num`, le numero
    d'une vignette, ecrit PAR-DESSUS UNE PHOTO. Son fond n'est pas une
    couleur, c'est une image quelconque ; sa lisibilite vient d'un
    `text-shadow`. Il n'y a pas de ratio a calculer.

    Le laisser en << non mesure >> laisse le banc rouge pour toujours -- et
    une alarme toujours allumee ne protege plus rien. Le declarer en dur dans
    l'instrument le rendrait aveugle au prochain cas du meme genre, sans
    qu'on le sache.

    La sortie est donc une DECLARATION, ecrite dans le CSS a cote de la
    regle, avec sa raison. Elle se relit, elle se conteste, et elle sort du
    compte des griefs -- pas du rapport.
    """

    CSS = ("/* contraste: hors-portee -- texte sur une PHOTO */\n"
           ".v { color: var(--graphite); text-shadow: 0 1px 2px #000; }")

    def test_une_regle_declaree_hors_portee_ne_compte_pas_comme_grief(self):
        dit = []
        n = K.verifier_css(self.CSS, K.lire_tokens(TOKENS), ecrire=dit.append)
        self.assertEqual(n, 0, "\n".join(dit))

    def test_mais_elle_reste_DITE_dans_le_rapport(self):
        dit = []
        K.verifier_css(self.CSS, K.lire_tokens(TOKENS), ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("HORS PORTEE", texte)
        self.assertIn("PHOTO", texte)

    def test_une_declaration_SANS_raison_ne_vaut_pas(self):
        """Une exemption sans motif est une exemption qu'on ne peut pas
        contester : elle ne sort pas du compte."""
        css = "/* contraste: hors-portee */\n.v { color: rgb(1 2 3); }"
        dit = []
        n = K.verifier_css(css, K.lire_tokens(TOKENS), ecrire=dit.append)
        self.assertGreater(n, 0)

    def test_elle_ne_couvre_PAS_la_regle_suivante(self):
        """Sinon un commentaire pose une fois exempterait toute la feuille."""
        css = (self.CSS + "\n.w { color: rgb(9 9 9); background: #000; }")
        dit = []
        n = K.verifier_css(css, K.lire_tokens(TOKENS), ecrire=dit.append)
        self.assertGreater(n, 0, "\n".join(dit))

    def test_elle_n_exempte_pas_un_couple_MESURABLE_et_mauvais(self):
        """Declarer hors portee ce qui se calcule serait une porte de sortie
        pour tout : la declaration ne vaut que si le couple est irresoluble."""
        css = ("/* contraste: hors-portee -- parce que ca m arrange */\n"
               ".v { color: #777777; background: var(--salle); }")
        dit = []
        n = K.verifier_css(css, K.lire_tokens(TOKENS), ecrire=dit.append)
        self.assertGreater(n, 0, "\n".join(dit))


class LaRaisonSeLitTelleQuEcrite(unittest.TestCase):

    def test_les_tirets_d_un_nom_de_token_survivent(self):
        css = ("/* contraste: hors-portee -- piste : var(--texte) */\n"
               ".v { color: rgb(1 2 3); }")
        self.assertIn('--texte', list(K.exemptions(css).values())[0])

    def test_une_raison_longue_est_COUPEE_VISIBLEMENT(self):
        css = ("/* contraste: hors-portee -- " + "a" * 200 + " */\n"
               ".v { color: rgb(1 2 3); }")
        dit = []
        K.verifier_css(css, K.lire_tokens(TOKENS), ecrire=dit.append)
        self.assertIn("[... suite dans components.css]", "\n".join(dit))


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
