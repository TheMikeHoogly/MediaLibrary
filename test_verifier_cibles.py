#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_cibles.py` -- sans navigateur, sans serveur.

Un instrument qui compte les cibles trop petites se trompe de deux facons,
et l'une est pire que l'autre. Manquer un bouton de 26 px laisse un defaut
en place ; ACCUSER cinq boutons de 44 px d'en faire 36 fait corriger ce qui
va bien -- et une alarme qu'on apprend a ignorer ne protege plus rien.

Trois des classes ci-dessous portent le nom d'un rouge REELLEMENT OBSERVE
sur les onze pages du projet pendant l'ecriture de l'instrument. Aucune ne
vient d'une hypothese :

  1. il comparait le TEXTE de deux valeurs : `44px` et `var(--touch)` sont
     la meme hauteur, il en tirait 52 non-decidables sur 192 ;
  2. il jugeait un selecteur descendant sur son seul SUJET : entre
     `.actbar .b { 44px }` et `.fxtoast .b { 36px }`, il prenait la derniere
     ecrite -- un verdict au hasard, pire qu'un aveu d'ignorance ;
  3. il rendait NON DECIDABLE `calc(var(--touch) + var(--e-2))`, une
     addition de pixels qu'il savait faire.

SORTIE EN ASCII PUR.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_cibles as K  # noqa: E402

TOKENS = ':root{--touch:44px;--e-2:8px;--e-1:4px}'


def feuilles(composants='', tokens=TOKENS, base=''):
    return {'components.css': composants, 'tokens.css': tokens,
            'base.css': base}


def page(style='', corps='', script='', marqueur=False):
    return ("<!doctype html><html><head>%s<style>%s</style></head><body>%s\n"
            "<script>\n%s\n</script>\n</body></html>"
            % (K.MARQUEUR if marqueur else '', style, corps, script))


def juge(style='', corps='', script='', marqueur=False, **kw):
    r = K.analyser('essai', page(style, corps, script, marqueur),
                   feuilles(**kw))
    return [(v, d) for _e, v, d in r['elements']]


def verdicts(*a, **kw):
    return [v for v, _d in juge(*a, **kw)]


class UNE_HAUTEUR_DECLAREE_SE_COMPARE_AU_PLANCHER(unittest.TestCase):

    def test_44px_passe(self):
        self.assertEqual(verdicts('.b{min-height:44px}',
                                  '<button class="b">x</button>'), ['OK'])

    def test_36px_ne_passe_pas(self):
        self.assertEqual(verdicts('.b{min-height:36px}',
                                  '<button class="b">x</button>'), ['SOUS'])

    def test_le_token_se_resout(self):
        self.assertEqual(verdicts('.b{min-height:var(--touch)}',
                                  '<button class="b">x</button>'), ['OK'])

    def test_height_vaut_min_height_quand_min_height_manque(self):
        self.assertEqual(verdicts('.b{height:26px}',
                                  '<button class="b">x</button>'), ['SOUS'])

    def test_une_unite_relative_n_est_pas_zero(self):
        self.assertEqual(verdicts('.b{min-height:3em}',
                                  '<button class="b">x</button>'),
                         ['NON DECIDABLE'])

    def test_un_token_inconnu_n_est_pas_zero_non_plus(self):
        self.assertEqual(verdicts('.b{min-height:var(--jamais-defini)}',
                                  '<button class="b">x</button>'),
                         ['NON DECIDABLE'])


class ROUGE_1_LE_MEME_PLANCHER_ECRIT_DE_DEUX_FACONS(unittest.TestCase):
    """`44px` et `var(--touch)` sont la MEME hauteur.

    Ce qui doit s'accorder n'est pas le texte de la valeur, c'est le
    VERDICT : tant que les deux lectures tombent du meme cote du plancher,
    savoir laquelle gagne ne change rien."""

    def test_deux_ecritures_du_meme_plancher_ne_font_pas_un_desaccord(self):
        self.assertEqual(
            verdicts('.btn{min-height:var(--touch)} .row .btn{min-height:44px}',
                     '<div class="row"><button class="btn">x</button></div>'),
            ['OK'])

    def test_meme_dans_un_fragment_JS_ou_l_ancetre_est_inconnu(self):
        self.assertEqual(
            verdicts('.btn{min-height:var(--touch)} .row .btn{min-height:44px}',
                     '', "h='<button class=\"btn\">x</button>';"),
            ['OK'])

    def test_mais_deux_verdicts_differents_restent_non_decidables(self):
        self.assertEqual(
            verdicts('.btn{min-height:var(--touch)} .row .btn{min-height:0}',
                     '', "h='<button class=\"btn\">x</button>';"),
            ['NON DECIDABLE'])


class ROUGE_2_L_ANCETRE_DECIDE_QUAND_IL_EST_ECRIT(unittest.TestCase):
    """`.actbar .b` et `.fxtoast .b` pesent pareil : sans l'ancetre, << la
    derniere ecrite gagne >> est un tirage a pile ou face."""

    STYLE = '.actbar .b{min-height:44px} .fxtoast .b{min-height:36px}'

    def test_le_bouton_de_la_barre_est_a_44(self):
        self.assertEqual(
            verdicts(self.STYLE,
                     '<div class="actbar"><button class="b">x</button></div>'),
            ['OK'])

    def test_le_bouton_du_toast_est_a_36(self):
        self.assertEqual(
            verdicts(self.STYLE,
                     '<div class="fxtoast"><button class="b">x</button></div>'),
            ['SOUS'])

    def test_sans_ancetre_connu_l_instrument_refuse_de_choisir(self):
        self.assertEqual(
            verdicts(self.STYLE, '', "h='<button class=\"b\">x</button>';"),
            ['NON DECIDABLE'])

    def test_un_ancetre_qui_ne_correspond_a_rien_refute_les_deux(self):
        self.assertEqual(
            verdicts(self.STYLE,
                     '<div class="autre"><button class="b">x</button></div>'),
            ['NON DECLARE'])

    def test_le_combinateur_enfant_exige_le_parent_IMMEDIAT(self):
        st = '.a>.b{min-height:44px}'
        self.assertEqual(
            verdicts(st, '<div class="a"><button class="b">x</button></div>'),
            ['OK'])
        self.assertEqual(
            verdicts(st, '<div class="a"><span><button class="b">x</button>'
                         '</span></div>'),
            ['NON DECLARE'])

    def test_un_ancetre_lointain_suffit_au_descendant(self):
        self.assertEqual(
            verdicts('.a .b{min-height:44px}',
                     '<div class="a"><span><i><button class="b">x</button>'
                     '</i></span></div>'),
            ['OK'])

    def test_une_balise_vide_ne_devient_pas_un_ancetre(self):
        # <img> ne se ferme pas : s'il empilait, tout ce qui suit serait
        # compte comme son descendant.
        self.assertEqual(
            verdicts('img .b{min-height:36px}',
                     '<img src="x"><button class="b">y</button>'),
            ['NON DECLARE'])


class ROUGE_3_UNE_ADDITION_DE_PIXELS_SE_CALCULE(unittest.TestCase):

    def test_calc_de_deux_tokens(self):
        self.assertEqual(
            verdicts('.b{min-height:calc(var(--touch) + var(--e-2))}',
                     '<button class="b">x</button>'), ['OK'])

    def test_calc_qui_descend_sous_le_plancher(self):
        self.assertEqual(
            verdicts('.b{min-height:calc(var(--touch) - var(--e-2))}',
                     '<button class="b">x</button>'), ['SOUS'])

    def test_un_pourcentage_reste_indecidable(self):
        self.assertEqual(
            verdicts('.b{min-height:calc(100% - 20px)}',
                     '<button class="b">x</button>'), ['NON DECIDABLE'])


class UNE_HAUTEUR_QUE_LE_DISPLAY_IGNORE_EST_INERTE(unittest.TestCase):
    """Le piege qui a rendu ce banc necessaire : la regle est ecrite, elle
    est lue, et elle ne fait rien."""

    def test_un_span_inline_ignore_min_height(self):
        self.assertEqual(
            verdicts('.b{min-height:44px}',
                     '<span class="b" onclick="f()">x</span>'), ['INERTE'])

    def test_le_meme_span_en_inline_flex_l_honore(self):
        self.assertEqual(
            verdicts('.b{min-height:44px;display:inline-flex}',
                     '<span class="b" onclick="f()">x</span>'), ['OK'])

    def test_un_element_REMPLACE_l_honore_meme_en_inline(self):
        self.assertEqual(
            verdicts('.b{min-height:44px;display:inline}',
                     '<input class="b" type="text">'), ['OK'])

    def test_un_bouton_est_inline_block_par_defaut(self):
        self.assertEqual(verdicts('.b{min-height:44px}',
                                  '<button class="b">x</button>'), ['OK'])


class CE_QUI_N_EST_PAS_DECLARE_NE_REND_PAS_VERT(unittest.TestCase):

    def test_un_bouton_sans_aucune_regle(self):
        self.assertEqual(verdicts('', '<button>x</button>'), ['NON DECLARE'])

    def test_un_lien_en_ligne_est_une_exception_NOMMEE(self):
        self.assertEqual(verdicts('', '<a href="/x">y</a>'),
                         ['LIEN EN LIGNE'])

    def test_un_lien_en_bloc_n_en_est_pas_une(self):
        self.assertEqual(verdicts('a{display:block}', '<a href="/x">y</a>'),
                         ['NON DECLARE'])


class LES_REGLES_D_ETAT_NE_DIMENSIONNENT_PAS(unittest.TestCase):

    def test_un_survol_ne_compte_pas_comme_plancher(self):
        self.assertEqual(verdicts('.b:hover{min-height:44px}',
                                  '<button class="b">x</button>'),
                         ['NON DECLARE'])

    def test_un_pseudo_element_non_plus(self):
        self.assertEqual(verdicts('.b::before{min-height:44px}',
                                  '<button class="b">x</button>'),
                         ['NON DECLARE'])

    def test_mais_un_attribut_compte(self):
        self.assertEqual(
            verdicts('.b[aria-pressed="true"]{min-height:44px}',
                     '<button class="b" aria-pressed="true">x</button>'),
            ['OK'])

    def test_et_un_attribut_qui_ne_correspond_pas_est_ecarte(self):
        self.assertEqual(
            verdicts('.b[aria-pressed="true"]{min-height:44px}',
                     '<button class="b" aria-pressed="false">x</button>'),
            ['NON DECLARE'])


class LES_EXEMPTIONS_SE_DECLARENT_DANS_LA_SOURCE(unittest.TestCase):

    def test_une_declaration_avec_sa_raison_exempte(self):
        v = juge('.p input{height:18px}',
                 '<!-- cible: hors-portee -- la vignette entiere est la cible,'
                 ' la case est un indicateur -->'
                 '<label class="p"><input type="checkbox"></label>')
        self.assertEqual([x[0] for x in v], ['DECLARE'])
        self.assertIn('vignette entiere', v[0][1])

    def test_une_declaration_SANS_raison_n_exempte_rien(self):
        self.assertEqual(
            verdicts('.p input{height:18px}',
                     '<!-- cible: hors-portee -->'
                     '<label class="p"><input type="checkbox"></label>'),
            ['SOUS'])

    def test_une_declaration_ne_couvre_QUE_le_prochain_element(self):
        v = juge('.p input{height:18px} .p button{min-height:12px}',
                 '<!-- cible: hors-portee -- la vignette entiere est la cible -->'
                 '<label class="p"><input type="checkbox">'
                 '<button>Valider</button></label>')
        self.assertEqual([x[0] for x in v], ['DECLARE', 'SOUS'])

    def test_une_raison_survit_a_un_retour_a_la_ligne(self):
        v = juge('.p input{height:18px}',
                 '<!-- cible: hors-portee -- la case est un indicateur,\n'
                 '     la vignette entiere est la cible -->'
                 '<label class="p"><input type="checkbox"></label>')
        self.assertEqual([x[0] for x in v], ['DECLARE'])
        self.assertIn('vignette entiere est la cible', v[0][1])

    def test_une_declaration_trop_loin_ne_couvre_rien(self):
        loin = '<p>' + ('mot ' * 400) + '</p>'
        v = juge('.p input{height:18px}',
                 '<!-- cible: hors-portee -- une raison quelconque -->' + loin +
                 '<label class="p"><input type="checkbox"></label>')
        self.assertEqual([x[0] for x in v], ['SOUS'])

    def test_hors_ecran_est_une_categorie_a_part(self):
        self.assertEqual(
            verdicts('', '<input class="hors-ecran" type="file">'),
            ['HORS ECRAN'])

    def test_display_none_n_est_pas_une_cible(self):
        self.assertEqual(
            verdicts('', '<button style="display:none">x</button>'),
            ['NON PEINT'])

    def test_un_champ_cache_n_est_pas_une_cible_du_tout(self):
        self.assertEqual(verdicts('', '<input type="hidden" name="x">'), [])


class COMPONENTS_CSS_EST_UN_OPT_IN(unittest.TestCase):

    COMP = '.btn{min-height:var(--touch)}'

    def test_sans_marqueur_la_feuille_commune_n_entre_pas(self):
        self.assertEqual(
            verdicts('', '<button class="btn">x</button>', composants=self.COMP),
            ['NON DECLARE'])

    def test_avec_marqueur_elle_entre(self):
        self.assertEqual(
            verdicts('', '<button class="btn">x</button>', marqueur=True,
                     composants=self.COMP),
            ['OK'])

    def test_et_la_page_garde_le_dernier_mot_sur_elle(self):
        self.assertEqual(
            verdicts('.btn{min-height:20px}', '<button class="btn">x</button>',
                     marqueur=True, composants=self.COMP),
            ['SOUS'])


class LA_CASCADE_A_QUATRE_ETAGES(unittest.TestCase):

    def test_base_css_gagne_les_egalites_contre_la_page(self):
        self.assertEqual(
            verdicts('.b{min-height:20px}', '<button class="b">x</button>',
                     base='.b{min-height:44px}'),
            ['OK'])

    def test_la_specificite_passe_avant_l_ordre(self):
        self.assertEqual(
            verdicts('#x{min-height:44px} .b{min-height:20px}',
                     '<button id="x" class="b">y</button>'),
            ['OK'])

    def test_important_bat_tout(self):
        self.assertEqual(
            verdicts('#x{min-height:20px} .b{min-height:44px !important}',
                     '<button id="x" class="b">y</button>'),
            ['OK'])

    def test_le_style_en_ligne_gagne_sur_la_feuille(self):
        self.assertEqual(
            verdicts('.b{min-height:44px}',
                     '<button class="b" style="min-height:12px">x</button>'),
            ['SOUS'])


class LE_RAPPORT_DIT_SA_PORTEE_ET_SON_VERDICT(unittest.TestCase):

    def sortie(self, **kw):
        lignes = []
        r = K.analyser('essai', page(**kw), feuilles())
        K.rapport([r], ecrire=lignes.append)
        return '\n'.join(lignes)

    def test_il_nomme_les_pages_sans_components_css(self):
        t = self.sortie(corps='<button>x</button>')
        self.assertIn('components.css', t)
        self.assertIn('essai', t)

    def test_il_donne_le_plancher_qu_il_a_LU(self):
        self.assertIn('--touch = 44px',
                      self.sortie(corps='<button>x</button>'))

    def test_un_plancher_introuvable_se_dit_au_lieu_d_etre_suppose(self):
        lignes = []
        r = K.analyser('essai', page(corps='<button>x</button>'),
                       feuilles(tokens=':root{--e-2:8px}'))
        K.rapport([r], ecrire=lignes.append)
        self.assertIn('INTROUVABLE', '\n'.join(lignes))

    def test_le_verdict_separe_le_prouve_du_non_declare(self):
        t = self.sortie(style='.b{min-height:12px}',
                        corps='<button class="b">x</button>')
        self.assertIn('PROUVE', t)
        self.assertIn('VERDICT', t)

    def test_la_sortie_est_en_ASCII_PUR(self):
        self.sortie(style='.b{min-height:12px}',
                    corps='<button class="b">x</button>').encode('ascii')


class L_INSTRUMENT_NE_TOUCHE_A_RIEN(unittest.TestCase):

    def test_il_n_ouvre_aucun_fichier_en_ecriture(self):
        src = Path(__file__).resolve().parent / 'verifier_cibles.py'
        texte = src.read_text(encoding='utf-8')
        for interdit in ("'w'", '"w"', 'write_text', '.write('):
            self.assertNotIn(interdit, texte,
                             'famille verifier_ : lecture seule')

    def test_le_source_est_en_ASCII_PUR(self):
        src = Path(__file__).resolve().parent / 'verifier_cibles.py'
        src.read_text(encoding='utf-8').encode('ascii')


if __name__ == '__main__':
    unittest.main(verbosity=2)
