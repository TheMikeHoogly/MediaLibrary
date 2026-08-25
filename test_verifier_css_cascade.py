#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_css_cascade.py` — la PREUVE avant l'extraction.

Ce que ces tests tiennent
-------------------------
Cet instrument va autoriser a deplacer des regles CSS a travers onze pages
dont une fait 1 594 lignes de style. Ce qu'il declare << identique >> ne sera
pas relu a l'oeil. Les tests portent donc, dans l'ordre :

1. **Ce qu'il DOIT voir** : une valeur qui change, une declaration qui
   disparait, un ordre qui s'inverse a selecteur egal.
2. **Ce qu'il DOIT accepter** : une regle qui change de FICHIER ou de place
   sans que la gagnante change. C'est tout l'objet du chantier — un
   instrument qui crierait la aussi ne servirait a rien.
3. **Ce qu'il ne sait pas decider et qu'il NOMME** : raccourcis, !important,
   blocs opaques. Un instrument muet sur ses angles morts donne la permission
   d'aller vite la ou il faut aller lentement.
4. **Il ne modifie rien** — famille `verifier_`.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_css_cascade as C  # noqa: E402


def cmp_(avant, apres):
    return C.comparer([("avant.css", avant)], [("apres.css", apres)])


class CeQuIlDoitVoir(unittest.TestCase):

    def test_une_valeur_qui_change_est_VUE(self):
        r = cmp_(".a{color:red}", ".a{color:blue}")
        self.assertFalse(r['identique'])
        self.assertEqual(r['changees'], [('', '.a', 'color')])

    def test_une_declaration_qui_DISPARAIT_est_vue(self):
        r = cmp_(".a{color:red;margin-top:0}", ".a{color:red}")
        self.assertFalse(r['identique'])
        self.assertIn(('', '.a', 'margin-top'), r['disparues'])

    def test_une_declaration_qui_APPARAIT_est_vue(self):
        r = cmp_(".a{color:red}", ".a{color:red;z-index:9}")
        self.assertFalse(r['identique'])
        self.assertIn(('', '.a', 'z-index'), r['apparues'])

    def test_un_ordre_INVERSE_a_selecteur_egal_change_la_gagnante(self):
        """C'est LE risque du chantier : hisser une regle la fait passer
        devant celle qui la corrigeait."""
        r = cmp_(".a{color:red}.a{color:blue}", ".a{color:blue}.a{color:red}")
        self.assertFalse(r['identique'])
        self.assertEqual(r['changees'], [('', '.a', 'color')])

    def test_un_media_query_n_est_pas_confondu_avec_la_regle_nue(self):
        r = cmp_(".a{color:red}@media(max-width:600px){.a{color:blue}}",
                 ".a{color:red}")
        self.assertFalse(r['identique'])
        self.assertEqual(len(r['disparues']), 1)
        self.assertIn('media', r['disparues'][0][0])


class CeQuIlDoitAccepter(unittest.TestCase):

    def test_une_regle_qui_change_de_FICHIER_ne_change_rien(self):
        """L'objet meme du chantier : hisser sans casser."""
        r = C.comparer([("page.css", ".a{color:red}.b{margin:0}")],
                       [("commun.css", ".a{color:red}"),
                        ("page.css", ".b{margin:0}")])
        self.assertTrue(r['identique'], r)

    def test_l_ordre_entre_selecteurs_DIFFERENTS_ne_compte_pas_ici(self):
        r = cmp_(".a{color:red}.b{color:blue}", ".b{color:blue}.a{color:red}")
        self.assertTrue(r['identique'])

    def test_la_mise_en_forme_et_les_commentaires_ne_comptent_pas(self):
        r = cmp_(".a{color:red}",
                 "/* hisse le 25/08 */\n.a {\n  color : red ;\n}\n")
        self.assertTrue(r['identique'])

    def test_un_selecteur_groupe_vaut_ses_selecteurs_separes(self):
        r = cmp_(".a,.b{color:red}", ".a{color:red}\n.b{color:red}")
        self.assertTrue(r['identique'])

    def test_un_doublon_exact_ne_change_pas_la_gagnante(self):
        r = cmp_(".a{color:red}", ".a{color:red}.a{color:red}")
        self.assertTrue(r['identique'])


class LaCascade(unittest.TestCase):

    def test_la_DERNIERE_ecrite_gagne(self):
        regles, _o, _n = C.analyser(".a{color:red}.a{color:blue}")
        self.assertEqual(C.gagnantes(regles)[('', '.a', 'color')],
                         ('blue', False))

    def test_un_important_bat_ce_qui_le_SUIT(self):
        regles, _o, _n = C.analyser(".a{color:red !important}.a{color:blue}")
        self.assertEqual(C.gagnantes(regles)[('', '.a', 'color')],
                         ('red', True))

    def test_les_media_imbriques_font_un_contexte_distinct(self):
        css = "@media print{@supports(display:grid){.a{color:red}}}"
        regles, _o, _n = C.analyser(css)
        cle = list(C.gagnantes(regles))[0]
        self.assertIn('media', cle[0])
        self.assertIn('supports', cle[0])


class LesAnglesMortsSontNOMMES(unittest.TestCase):

    def test_les_raccourcis_en_collision_sont_COMPTES(self):
        """margin apres margin-top : la table ne bouge pas, la page si."""
        r = cmp_(".a{margin-top:4px;margin:0}", ".a{margin:0;margin-top:4px}")
        self.assertTrue(r['identique'],
                        "la table des gagnantes ne voit pas ce piege")
        self.assertTrue(r['raccourcis'], "il doit au moins le NOMMER")

    def test_le_rapport_REFUSE_de_dire_feu_vert(self):
        dit = []
        C.rapport(cmp_(".a{color:red}", ".a{color:red}"), ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("IDENTIQUE", texte)
        self.assertIn("Ce n est PAS un feu vert", texte)
        self.assertIn("NE SAIT PAS DECIDER", texte)

    def test_un_bloc_opaque_qui_DIFFERE_empeche_le_verdict(self):
        r = cmp_("@keyframes p{from{opacity:0}to{opacity:1}}",
                 "@keyframes p{from{opacity:1}to{opacity:0}}")
        self.assertTrue(r['opaques_differents'])
        dit = []
        C.rapport(r, ecrire=dit.append)
        self.assertIn("DIFFERENT", "\n".join(dit))

    def test_un_keyframes_identique_ne_declenche_rien(self):
        r = cmp_("@keyframes p{from{opacity:0}}.a{color:red}",
                 ".a{color:red}@keyframes p{from{opacity:0}}")
        self.assertTrue(r['identique'])
        self.assertFalse(r['opaques_differents'])

    def test_un_import_est_signale_comme_non_decidable(self):
        r = cmp_("@import url(x.css);.a{color:red}", ".a{color:red}")
        self.assertTrue(r['non_decidables'])

    def test_les_important_sont_comptes(self):
        r = cmp_(".a{color:red}", ".a{color:red !important}")
        self.assertEqual(r['importants'], 1)


class LAnalyseNeSeFaitPasPieger(unittest.TestCase):

    def test_une_accolade_dans_une_chaine_ne_ferme_pas_le_bloc(self):
        regles, _o, _n = C.analyser('.a{content:"}";color:red}')
        props = {r['propriete'] for r in regles}
        self.assertEqual(props, {'content', 'color'})

    def test_un_point_virgule_dans_une_url_ne_coupe_pas_la_valeur(self):
        regles, _o, _n = C.analyser('.a{background:url(a.png?x=1;y=2)}')
        self.assertEqual(regles[0]['valeur'], 'url(a.png?x=1;y=2)')

    def test_un_deux_points_de_pseudo_classe_ne_devient_pas_une_propriete(self):
        regles, _o, _n = C.analyser('a:hover{color:red}')
        self.assertEqual(regles[0]['selecteur'], 'a:hover')
        self.assertEqual(regles[0]['propriete'], 'color')

    def test_le_style_d_une_page_html_est_extrait(self):
        html = "<html><head><style>.a{color:red}</style></head><body></body>"
        self.assertEqual(C.styles_de_page(html).strip(), ".a{color:red}")

    def test_plusieurs_blocs_style_sont_concatenes_DANS_L_ORDRE(self):
        html = "<style>.a{color:red}</style>x<style>.a{color:blue}</style>"
        regles, _o, _n = C.analyser(C.styles_de_page(html))
        self.assertEqual(C.gagnantes(regles)[('', '.a', 'color')][0], 'blue')


class LInventaireDuCommun(unittest.TestCase):

    def test_ce_que_deux_pages_declarent_PAREIL_est_hissable(self):
        r = C.commun({'p1': ".a{color:red}", 'p2': ".a{color:red}"})
        self.assertEqual(r['hissables'], 1)
        self.assertEqual(r['discordantes'], 0)

    def test_ce_qu_elles_declarent_DIFFEREMMENT_ne_l_est_pas(self):
        """Hisser une valeur que les pages contredisent en casserait une."""
        r = C.commun({'p1': ".a{color:red}", 'p2': ".a{color:blue}"})
        self.assertEqual(r['hissables'], 0)
        self.assertEqual(r['discordantes'], 1)

    def test_ce_qu_une_SEULE_page_declare_n_est_pas_partage(self):
        r = C.commun({'p1': ".a{color:red}", 'p2': ".b{color:red}"})
        self.assertEqual(r['partagees'], 0)

    def test_le_rapport_NOMME_les_discordantes(self):
        dit = []
        C.rapport_commun(C.commun({'p1': ".a{color:red}",
                                   'p2': ".a{color:blue}"}), ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("DISCORDANTES", texte)
        self.assertIn(".a", texte)



class LaMemeValeurEcriteAutrement(unittest.TestCase):
    """Le rouge de cette classe n'est pas synthetique : il a ete OBSERVE.

    Au premier contact reel (25/08), l'inventaire des onze pages a rendu 32
    discordances — dont SIX qui etaient `.01ms` contre `0.01ms`, la meme
    duree ecrite deux fois. Un instrument qui compte ca comme un ecart gonfle
    ses alarmes de 19 %, et des alarmes qu'on apprend a ignorer ne protegent
    plus rien.
    """

    def test_un_zero_de_tete_ne_fait_pas_une_discordance(self):
        self.assertEqual(C.normalise_valeur(".01ms"),
                         C.normalise_valeur("0.01ms"))

    def test_un_zero_de_queue_non_plus(self):
        self.assertEqual(C.normalise_valeur("0.50em"),
                         C.normalise_valeur(".5em"))

    def test_l_unite_se_compare_sans_la_casse(self):
        self.assertEqual(C.normalise_valeur("10PX"), C.normalise_valeur("10px"))

    def test_une_CHAINE_n_est_jamais_touchee(self):
        """`content: \".01\"` est un texte : le normaliser changerait ce que
        la page AFFICHE."""
        self.assertEqual(C.normalise_valeur('".01"'), '".01"')

    def test_une_vraie_difference_reste_une_difference(self):
        self.assertNotEqual(C.normalise_valeur("10px"),
                            C.normalise_valeur("11px"))

    def test_l_inventaire_ne_compte_plus_l_ecriture_comme_un_ecart(self):
        r = C.commun({'p1': "*{animation-duration:.01ms}",
                      'p2': "*{animation-duration:0.01ms}"})
        self.assertEqual(r['discordantes'], 0)
        self.assertEqual(r['hissables'], 1)
        self.assertEqual(r['ecritures_differentes'], 1)

    def test_et_le_rapport_le_DIT_au_lieu_de_le_taire(self):
        dit = []
        C.rapport_commun(C.commun({'p1': "*{animation-duration:.01ms}",
                                   'p2': "*{animation-duration:0.01ms}"}),
                         ecrire=dit.append)
        self.assertIn("ecrites AUTREMENT", "\n".join(dit))

    def test_une_reecriture_pendant_l_extraction_ne_crie_pas(self):
        r = cmp_(".a{transition:.5s}", ".a{transition:0.5s}")
        self.assertTrue(r['identique'])



class CeQuiNePeutMordreSurCettePage(unittest.TestCase):
    """Ne de la premiere conversion reelle (25/08).

    Adopter `components.css` sur `residu` apporte 59 declarations nouvelles —
    `.planche`, `.toast`, `.chip`, `.donnee` — dont la page n'a AUCUN element.
    Les compter comme des changements noie le seul qui compte : le
    `justify-content` ajoute a `.btn`, que la page, elle, porte. Un instrument
    qui crie 59 fois pour une vraie alarme n'est plus lu.
    """

    def test_une_classe_absente_de_la_page_ne_mord_pas(self):
        self.assertFalse(C.mord_sur('.toast', '<div class="bar"></div>'))

    def test_une_classe_PRESENTE_mord(self):
        self.assertTrue(C.mord_sur('.bar', '<div class="bar"></div>'))

    def test_un_selecteur_de_TYPE_mord_toujours(self):
        """`body`, `h2` : aucun identifiant a chercher, donc jamais inerte."""
        self.assertTrue(C.mord_sur('body', '<p>rien</p>'))

    def test_un_selecteur_COMPOSE_exige_tous_ses_identifiants(self):
        self.assertFalse(C.mord_sur('.bar .toast', '<div class="bar"></div>'))
        self.assertTrue(C.mord_sur('.bar .n', '<div class="bar"><i class="n">'))

    def test_un_attribut_compte_comme_un_identifiant(self):
        self.assertFalse(C.mord_sur('.chip[aria-pressed="true"]',
                                    '<div class="chip"></div>'))

    def test_une_classe_batie_en_JS_est_trouvee_dans_la_SOURCE(self):
        """C'est pourquoi on cherche dans toute la source, pas dans le HTML
        rendu : `b.className = 'btn btn--confirmer'` compte."""
        self.assertTrue(C.mord_sur(
            '.btn--confirmer', "<script>b.className='btn btn--confirmer'</script>"))

    def test_les_inertes_sont_COMPTEES_a_part_et_le_verdict_les_ignore(self):
        r = C.comparer([("a.css", ".bar{color:red}")],
                       [("a.css", ".bar{color:red}"),
                        ("commun.css", ".toast{color:blue}")],
                       source_page='<div class="bar"></div>')
        self.assertEqual(r['apparues_actives'], [])
        self.assertEqual(len(r['apparues_inertes']), 1)
        self.assertTrue(r['identique_sur_ce_qui_mord'])

    def test_une_apparue_qui_MORD_fait_tomber_le_verdict(self):
        r = C.comparer([("a.css", ".bar{color:red}")],
                       [("a.css", ".bar{color:red;padding:0}")],
                       source_page='<div class="bar"></div>')
        self.assertEqual(len(r['apparues_actives']), 1)
        self.assertFalse(r['identique_sur_ce_qui_mord'])

    def test_le_rapport_DIT_que_le_compte_des_inertes_est_un_plancher(self):
        dit = []
        C.rapport(C.comparer([("a.css", ".bar{color:red}")],
                             [("a.css", ".bar{color:red}"),
                              ("c.css", ".toast{color:blue}")],
                             source_page='<div class="bar"></div>'),
                  ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("INERTES", texte)
        self.assertIn("PLANCHER", texte)

    def test_sans_page_fournie_rien_ne_change(self):
        """L'ancien comportement reste : pas de page, pas de tri."""
        r = cmp_(".a{color:red}", ".a{color:red}")
        self.assertFalse(r['inertes_connues'])
        self.assertTrue(r['identique'])


class IlNeModifieRien(unittest.TestCase):

    def test_aucune_ecriture_ni_suppression_dans_le_module(self):
        source = Path(C.__file__).read_text(encoding='utf-8')
        for interdit in ('.unlink(', 'os.remove(', 'shutil.'):
            self.assertNotIn(interdit, source, interdit + " dans une famille "
                             "verifier_ : elle est en lecture seule")

    def test_la_seule_ecriture_possible_est_le_json_demande(self):
        source = Path(C.__file__).read_text(encoding='utf-8')
        self.assertEqual(source.count('write_text('), 1)


if __name__ == '__main__':
    unittest.main(verbosity=0)
