#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_controles.py` -- sans navigateur, sans serveur.

Un instrument qui compte ce qui est cliquable sans etre un controle se
trompe de deux facons, et les deux sont graves dans des sens opposes : il
peut manquer un `<span onclick>` -- et il peut CRIER sur du code qui va
bien. Une alarme qu'on apprend a ignorer ne protege plus rien.

Six des classes ci-dessous portent le nom d'un rouge REELLEMENT OBSERVE sur
les onze pages du projet pendant l'ecriture de l'instrument. Aucune ne vient
d'une hypothese : chacune fixe une erreur que l'instrument a commise, sur
des fichiers qui existent.

SORTIE EN ASCII PUR.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_controles as K  # noqa: E402


def page(corps='', script=''):
    return ("<!doctype html><html><head></head><body>%s\n<script>\n%s\n"
            "</script>\n</body></html>" % (corps, script))


def juge(corps='', script=''):
    return K.analyser('essai', page(corps, script))


class UN_SPAN_QUI_SE_CLIQUE_EST_UN_GRIEF(unittest.TestCase):

    def test_l_attribut_onclick_sur_un_span_est_compte(self):
        r = juge('<span onclick="f()">x</span>')
        self.assertEqual(len(r['griefs']), 1)
        self.assertEqual(r['griefs'][0][1], 'span')

    def test_le_meme_attribut_sur_un_button_ne_l_est_pas(self):
        r = juge('<button onclick="f()">x</button>')
        self.assertEqual(r['griefs'], [])
        self.assertEqual(r['natifs'], 1)

    def test_un_span_fabrique_en_JS_est_compte_aussi(self):
        r = juge('', "var c=document.createElement('span');"
                     " c.onclick=function(){};")
        self.assertEqual(len(r['griefs']), 1)

    def test_le_grief_DIT_ce_qui_manque(self):
        r = juge('<div onclick="f()">x</div>')
        self.assertIn('tabindex', r['griefs'][0][3])
        self.assertIn('role', r['griefs'][0][3])
        self.assertIn('clavier', r['griefs'][0][3])


class RENDU_OPERABLE_A_LA_MAIN_N_EST_PAS_UN_GRIEF(unittest.TestCase):

    def test_les_trois_marques_ensemble_font_un_controle_bricole(self):
        r = juge('', "var c=document.createElement('span');"
                     " c.setAttribute('role','button'); c.tabIndex=0;"
                     " c.onkeydown=function(){}; c.onclick=function(){};")
        self.assertEqual(r['griefs'], [])
        self.assertEqual(len(r['bricoles']), 1)

    def test_DEUX_marques_sur_trois_ne_suffisent_pas(self):
        r = juge('', "var c=document.createElement('span');"
                     " c.setAttribute('role','button'); c.tabIndex=0;"
                     " c.onclick=function(){};")
        self.assertEqual(len(r['griefs']), 1)
        self.assertIn('clavier', r['griefs'][0][3])

    def test_bricole_n_est_pas_compte_comme_natif(self):
        r = juge('<span role="button" tabindex="0" onkeydown="f()"'
                 ' onclick="f()">x</span>')
        self.assertEqual(r['natifs'], 0)
        self.assertEqual(len(r['bricoles']), 1)


class UN_LIEN_N_EST_UN_CONTROLE_QUE_S_IL_MENE_QUELQUE_PART(unittest.TestCase):

    def test_un_a_sans_href_sort_de_la_tabulation(self):
        r = juge('<a onclick="f()">x</a>')
        self.assertEqual(len(r['griefs']), 1)
        self.assertIn('href', r['griefs'][0][3])

    def test_un_a_avec_href_est_natif(self):
        r = juge('<a href="/x" onclick="f()">x</a>')
        self.assertEqual(r['natifs'], 1)

    def test_un_href_pose_en_JS_compte_autant_qu_un_href_ecrit(self):
        # ROUGE OBSERVE (people l.300) : `var a=createElement('a');
        # a.href=f.url` -- l'instrument declarait hors tabulation un lien
        # qui y est, parce qu'il ne lisait que les attributs ECRITS.
        r = juge('', "var a=document.createElement('a'); a.href='/x';"
                     " a.addEventListener('click', function(){});")
        self.assertEqual(r['griefs'], [])
        self.assertEqual(r['natifs'], 1)

    def test_un_href_diese_reste_natif_mais_est_DIT(self):
        r = juge('<a href="#" onclick="f()">x</a>')
        self.assertEqual(r['griefs'], [])
        self.assertEqual(len(r['liens']), 1)


class UN_COMMENTAIRE_EST_DE_LA_PROSE(unittest.TestCase):

    def test_un_onclick_cite_dans_un_commentaire_JS_ne_compte_pas(self):
        r = juge('', "// ici on posera plus tard un <span onclick=...>\n"
                     "var b=document.createElement('button');"
                     " b.onclick=function(){};")
        self.assertEqual(r['griefs'], [])
        self.assertEqual(r['poses'], 1)

    def test_un_commentaire_HTML_non_plus(self):
        r = juge('<!-- <div onclick="f()">jadis</div> -->')
        self.assertEqual(r['poses'], 0)

    def test_le_slash_slash_d_une_URL_n_ouvre_pas_un_commentaire(self):
        r = juge('', "var u='https://exemple.ch/'; "
                     "var c=document.createElement('span');"
                     " c.onclick=function(){};")
        self.assertEqual(len(r['griefs']), 1)


class UNE_COMPARAISON_N_EST_PAS_UNE_BALISE(unittest.TestCase):
    """ROUGE OBSERVE (people l.322, l.545)."""

    def test_le_chevron_d_un_test_JS_ne_fabrique_pas_de_balise(self):
        r = juge('', "var t=2; if(1<t){} \n"
                     "var b=document.createElement('button');"
                     " b.onclick=function(){};")
        self.assertEqual(r['griefs'], [])

    def test_mais_le_HTML_ecrit_dans_une_CHAINE_reste_lu(self):
        r = juge('', "el.innerHTML='<div onclick=\"f()\">x</div>';")
        self.assertEqual(len(r['griefs']), 1)
        self.assertEqual(r['griefs'][0][2], 'attribut dans une chaine JS')


class UNE_REGEX_N_EST_PAS_UNE_CHAINE(unittest.TestCase):
    """ROUGE OBSERVE (subjects, `esc()` en tete de script).

    Le guillemet DANS `/[&<>"]/g` ouvrait une fausse chaine et faisait
    basculer tout le reste du fichier : un bouton ecrit cent lignes plus bas
    cessait d'exister pour l'instrument.
    """

    def test_un_guillemet_dans_une_regex_ne_desynchronise_pas_la_suite(self):
        js = ("function esc(s){return (s||'').replace(/[&<>\"]/g,"
              "function(c){return c;});}\n"
              "el.innerHTML='<button class=\"anim\">oui</button>';\n"
              "el.querySelector('.anim').onclick=function(){};")
        r = juge('', js)
        self.assertEqual(r['griefs'], [])
        self.assertEqual(r['natifs'], 1)

    def test_une_division_reste_une_division(self):
        r = juge('', "var x=(a)/2; var y=b/2;"
                     " var c=document.createElement('span');"
                     " c.onclick=function(){};")
        self.assertEqual(len(r['griefs']), 1)


class LA_CIBLE_SE_REMONTE_PAR_TROIS_CHEMINS(unittest.TestCase):

    def test_une_variable_qui_range_un_getElementById(self):
        # ROUGE OBSERVE (gallery l.494) : le motif le plus courant du
        # projet, 119 fois sur les onze pages.
        r = juge('<button id="b1">x</button>',
                 "var btn=document.getElementById('b1');"
                 " btn.addEventListener('click', function(){});")
        self.assertEqual(r['natifs'], 1)
        self.assertEqual(r['indecidables'], [])

    def test_le_parametre_d_un_forEach_sur_querySelectorAll(self):
        # ROUGE OBSERVE (subjects l.228) : la page qui fait CORRECTEMENT
        # ses chips passait pour non decidable. Un instrument qui ne
        # reconnait pas le bon eleve ne peut pas montrer la divergence.
        r = juge('<button class="chip">a</button>',
                 "document.querySelectorAll('.chip').forEach(function(c){"
                 " c.onclick=function(){}; });")
        self.assertEqual(r['natifs'], 1)
        self.assertEqual(r['indecidables'], [])

    def test_un_selecteur_qui_ECRIT_sa_balise(self):
        r = juge('', "el.querySelector('button.btn--principal')"
                     ".onclick=function(){};")
        self.assertEqual(r['natifs'], 1)

    def test_un_selecteur_descendant_se_juge_sur_son_DERNIER_segment(self):
        r = juge('<div class="actes"><button class="btn">x</button></div>',
                 "document.querySelector('.actes .btn')"
                 ".onclick=function(){};")
        self.assertEqual(r['natifs'], 1)


class UN_NOM_DE_CLASSE_EST_UN_JETON_ENTIER(unittest.TestCase):

    def test_le_selecteur_point_n_ne_trouve_pas_la_classe_nommer(self):
        r = juge('<button class="nommer">x</button>',
                 "el.querySelector('.n').onclick=function(){};")
        self.assertEqual(r['natifs'], 0)
        self.assertEqual(len(r['indecidables']), 1)

    def test_une_classe_portee_par_DEUX_balises_ne_tranche_pas(self):
        r = juge('<button class="k">a</button><div class="k">b</div>',
                 "el.querySelector('.k').onclick=function(){};")
        self.assertEqual(len(r['indecidables']), 1)
        self.assertIn('2 balises', r['indecidables'][0][1])


class CE_QU_IL_NE_SAIT_PAS_EST_COMPTE_PAS_TU(unittest.TestCase):

    def test_une_cible_non_remontee_est_listee(self):
        r = juge('', "function bind(id,fn){"
                     " var el=document.getElementById(id);"
                     " if(el) el.onclick=fn; }")
        self.assertEqual(len(r['indecidables']), 1)

    def test_elle_empeche_le_code_zero(self):
        n = K.rapport([juge('', "function bind(id,fn){"
                                " var el=document.getElementById(id);"
                                " if(el) el.onclick=fn; }")],
                      ecrire=lambda *a: None)
        self.assertEqual(n, 1)

    def test_une_delegation_est_NOMMEE_et_pas_rendue_verte(self):
        r = juge('<div id="lb"></div>',
                 "document.getElementById('lb').addEventListener('click',"
                 " function(e){ if(e.target.id==='lb') fermer(); });")
        self.assertEqual(r['griefs'], [])
        self.assertEqual(len(r['oeil']), 1)

    def test_un_ecouteur_sur_document_n_est_pas_un_grief(self):
        r = juge('', "document.addEventListener('click', function(e){});")
        self.assertEqual(r['griefs'], [])
        self.assertEqual(r['indecidables'], [])


class CE_QUI_NE_SE_DECIDE_PAS_SE_DECLARE(unittest.TestCase):
    """Un clic qui DOUBLE une action deja offerte au clavier n'est pas un
    manquement -- mais ca ne se calcule pas : il faut savoir que l'autre
    chemin existe. La declaration vit donc dans la source, avec sa raison.
    """

    def test_une_declaration_exempte_le_gestionnaire_SUIVANT(self):
        r = juge('<!-- controle: redondant -- Echap ferme aussi -->'
                 '<span class="x" onclick="fermer()">x</span>')
        self.assertEqual(r['griefs'], [])
        self.assertEqual(len(r['declares']), 1)
        self.assertEqual(r['declares'][0][3], 'redondant')
        self.assertIn('Echap', r['declares'][0][4])

    def test_elle_ne_couvre_PAS_le_gestionnaire_d_apres(self):
        r = juge('<!-- controle: redondant -- Echap ferme aussi -->'
                 '<span onclick="a()">x</span><span onclick="b()">y</span>')
        self.assertEqual(len(r['declares']), 1)
        self.assertEqual(len(r['griefs']), 1)

    def test_une_declaration_SANS_raison_ne_vaut_rien(self):
        r = juge('<!-- controle: redondant -->'
                 '<span onclick="a()">x</span>')
        self.assertEqual(len(r['griefs']), 1)
        self.assertEqual(r['declares'], [])

    def test_elle_se_lit_aussi_dans_un_commentaire_JS(self):
        r = juge('', "// controle: redondant -- les fleches font pareil\n"
                     "var c=document.createElement('div');"
                     " c.onclick=function(){};")
        self.assertEqual(len(r['declares']), 1)

    def test_elle_n_exempte_pas_un_controle_deja_NATIF(self):
        r = juge('<!-- controle: redondant -- sans objet -->'
                 '<button onclick="a()">x</button>')
        self.assertEqual(r['natifs'], 1)
        self.assertEqual(r['declares'], [])

    def test_la_forme_NATIF_couvre_une_cible_NON_REMONTEE(self):
        # `function bind(id,fn)` recoit l'identifiant en parametre : aucune
        # lecture statique ne dit quelle balise est visee. Les six appels de
        # `browse` visent tous un <button>, ce qui se VERIFIE a la lecture --
        # mais pas par l'instrument. C'est ce que cette forme sert a dire.
        r = juge('', "// controle: natif -- les six appels visent des <button>\n"
                     "function bind(id,fn){"
                     " var el=document.getElementById(id);"
                     " if(el) el.onclick=fn; }")
        self.assertEqual(r['indecidables'], [])
        self.assertEqual(len(r['declares']), 1)
        self.assertEqual(r['declares'][0][3], 'natif')

    def test_un_genre_inconnu_ne_declare_rien(self):
        r = juge('<!-- controle: pratique -- au cas ou -->'
                 '<span onclick="a()">x</span>')
        self.assertEqual(len(r['griefs']), 1)
        self.assertEqual(r['declares'], [])

    def test_le_rapport_les_COMPTE_et_les_NOMME(self):
        lignes = []
        K.rapport([juge('<!-- controle: redondant -- Echap ferme aussi -->'
                        '<span onclick="f()">x</span>')], ecrire=lignes.append)
        t = '\n'.join(lignes)
        self.assertIn('DECLARES DANS LA SOURCE', t)
        self.assertIn('REDONDANT', t)
        self.assertIn('Echap ferme aussi', t)


class LE_RAPPORT_DIT_SA_PORTEE(unittest.TestCase):

    def sortie(self, resultats):
        lignes = []
        K.rapport(resultats, ecrire=lignes.append)
        return '\n'.join(lignes)

    def test_il_compte_les_pages_LUES(self):
        t = self.sortie([juge('<button onclick="f()">x</button>')])
        self.assertIn('1 page(s) LUES', t)

    def test_il_nomme_ce_qu_il_ne_remonte_pas(self):
        t = self.sortie([juge('', "function bind(id,fn){"
                                  " var el=document.getElementById(id);"
                                  " if(el) el.onclick=fn; }")])
        self.assertIn('NON DECIDABLES', t)

    def test_aucune_page_lue_n_est_PAS_un_feu_vert(self):
        lignes = []
        n = K.rapport([], ecrire=lignes.append)
        self.assertNotEqual(n, 0)
        self.assertIn("n'a pu etre verifie", '\n'.join(lignes))

    def test_tout_vert_le_dit_sans_promettre_plus(self):
        t = self.sortie([juge('<button onclick="f()">x</button>')])
        self.assertIn('VERDICT', t)
        self.assertIn('poses sur des controles', t)

    def test_la_sortie_est_en_ASCII_PUR(self):
        t = self.sortie([juge('<span onclick="f()">x</span>')])
        t.encode('ascii')


class L_INSTRUMENT_NE_TOUCHE_A_RIEN(unittest.TestCase):

    def test_il_n_ouvre_aucun_fichier_en_ecriture(self):
        src = Path(__file__).resolve().parent / 'verifier_controles.py'
        texte = src.read_text(encoding='utf-8')
        for interdit in ("'w'", '"w"', "write_text", ".write("):
            self.assertNotIn(interdit, texte,
                             "famille verifier_ : lecture seule")


if __name__ == '__main__':
    unittest.main(verbosity=2)
