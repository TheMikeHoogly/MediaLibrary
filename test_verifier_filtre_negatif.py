#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_filtre_negatif.py` — sans serveur, sans reseau.

Ce que ces tests tiennent
-------------------------
1. **Le rouge est GRAVE, pas suppose.** Chaque cas rouge est celui qu'on a
   VU le 26/08 : 1 500 photos pour `animal:Zzzznexistepas`. Un banc dont on
   n'a jamais observe le rouge ne prouve rien.
2. **Zero ne suffit pas : il faut que le refus soit NOMME.** « ce nom
   n'existe pas » et « ce nom n'a pas de photo » se lisent pareil sinon, et
   c'est exactement la confusion qui a fait conclure qu'une chatte de seize
   ans n'avait aucune photo.
3. **Le POSITIF est ce qui empeche le banc de mentir a son tour.** Un moteur
   qui rendrait zero pour tout passerait tous les controles negatifs.
4. **Une portee reduite ne rend pas vert.** Ce qui n'a pas ete teste est dit.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_filtre_negatif as V  # noqa: E402


def reponse(n=0, noms=(), axes=(), especes=(), erreur=None):
    r = {'results': [{'key': 'k%d' % i} for i in range(n)],
         'noms_inconnus': list(noms), 'axes_inconnus': list(axes),
         'especes_inconnues': list(especes)}
    if erreur:
        r['error'] = erreur
    return r


NEG = {'titre': 'animal inconnu', 'q': 'animal:' + V.INVENTE,
       'attente': 'zero_nomme', 'liste': 'noms_inconnus'}
POS = {'titre': 'animal connu', 'q': 'animal:Luna', 'attente': 'au_moins_un'}
PHRASE = {'titre': 'phrase', 'q': 'Luna : la chatte',
          'attente': 'pas_de_refus'}


class LeControleNegatif(unittest.TestCase):

    def test_LE_defaut_du_26_08_est_rouge(self):
        # 1 500 photos rendues pour un nom invente.
        ok, motif = V.verdict(NEG, reponse(n=1500))
        self.assertFalse(ok)
        self.assertIn('1500', motif)

    def test_zero_SANS_le_dire_est_rouge(self):
        # Un filtre impossible et un fonds pauvre se liraient pareil.
        ok, motif = V.verdict(NEG, reponse(n=0))
        self.assertFalse(ok)
        self.assertIn('NOMME', motif)

    def test_zero_ET_nomme_est_vert(self):
        ok, _m = V.verdict(NEG, reponse(n=0, noms=['animal:' + V.INVENTE]))
        self.assertTrue(ok)

    def test_le_refus_doit_porter_LA_valeur_demandee(self):
        # Un refus qui nomme autre chose ne prouve pas que CE jeton a mordu.
        ok, _m = V.verdict(NEG, reponse(n=0, noms=['personne:Bidule']))
        self.assertFalse(ok)

    def test_un_axe_inconnu_se_lit_dans_SA_liste(self):
        c = {'titre': 'axe', 'q': 'couleur:rouge', 'attente': 'zero_nomme',
             'liste': 'axes_inconnus', 'valeur': 'couleur'}
        self.assertTrue(V.verdict(c, reponse(n=0, axes=['couleur']))[0])
        # nomme dans la MAUVAISE liste : rouge.
        self.assertFalse(V.verdict(c, reponse(n=0, noms=['couleur']))[0])


class LeControlePositif(unittest.TestCase):

    def test_zero_pour_une_valeur_REELLE_est_rouge(self):
        # Sans ce controle, un moteur qui rend zero partout serait vert.
        ok, motif = V.verdict(POS, reponse(n=0))
        self.assertFalse(ok)
        self.assertIn('zero', motif)

    def test_un_garde_fou_qui_mord_le_reel_est_rouge(self):
        ok, motif = V.verdict(POS, reponse(n=12, noms=['animal:Luna']))
        self.assertFalse(ok)
        self.assertIn('REELLE', motif)

    def test_des_photos_et_aucun_refus_est_vert(self):
        self.assertTrue(V.verdict(POS, reponse(n=12))[0])


class LeFauxPositif(unittest.TestCase):

    def test_une_phrase_ponctuee_ne_doit_pas_etre_refusee(self):
        ok, motif = V.verdict(PHRASE, reponse(n=3, axes=['Luna']))
        self.assertFalse(ok)
        self.assertIn('tort', motif)

    def test_une_phrase_ponctuee_sans_refus_est_verte(self):
        self.assertTrue(V.verdict(PHRASE, reponse(n=3))[0])

    def test_meme_avec_zero_photo_l_absence_de_refus_suffit(self):
        # « pas de refus » ne parle pas du nombre : une phrase peut ne rien
        # trouver sans qu'aucun filtre n'ait menti.
        self.assertTrue(V.verdict(PHRASE, reponse(n=0))[0])


class LesPannesDeMesure(unittest.TestCase):

    def test_pas_de_reponse_est_rouge_pas_vert(self):
        self.assertFalse(V.verdict(NEG, None)[0])

    def test_une_erreur_serveur_est_rouge(self):
        ok, motif = V.verdict(POS, reponse(n=0, erreur='boom'))
        self.assertFalse(ok)
        self.assertIn('boom', motif)


class LePlan(unittest.TestCase):

    def test_les_cinq_axes_sont_couverts_en_negatif_sans_rien_connaitre(self):
        plan = V.plan_des_controles(None, None, None)
        negatifs = [c['q'] for c in plan if c['attente'] == 'zero_nomme']
        for prefixe in ('animal:', 'personne:', 'lieu:', 'espece:',
                        V.AXE_INVENTE + ':'):
            self.assertTrue(any(q.startswith(prefixe) for q in negatifs),
                            prefixe)

    def test_ce_qui_n_est_pas_connu_n_est_pas_teste(self):
        court = V.plan_des_controles(None, None, None)
        long_ = V.plan_des_controles('Mike', 'Luna', 'Sion')
        self.assertGreater(len(long_), len(court))
        self.assertTrue(any(c['q'] == 'Luna' for c in long_))

    def test_un_jeton_faux_empoisonne_une_requete_par_ailleurs_valable(self):
        plan = V.plan_des_controles(None, 'Luna', None)
        c = [x for x in plan if 'empoisonne' in x['titre']][0]
        self.assertEqual(c['attente'], 'zero_nomme')
        self.assertIn('animal:Luna', c['q'])
        self.assertIn(V.INVENTE, c['q'])


class LaPageEstUnCanalAPart(unittest.TestCase):

    def test_les_photos_de_la_page_sont_relues_telles_que_servies(self):
        html = 'blah\n  var FILES = [{"key": "a"}, {"key": "b"}];\n  var X=1;'
        self.assertEqual(len(V.files_de_la_page(html)), 2)

    def test_une_page_vide_rend_une_liste_vide_pas_None(self):
        self.assertEqual(V.files_de_la_page('var FILES = [];'), [])

    def test_une_page_sans_marqueur_rend_None(self):
        # None = « je ne sais pas », et le banc en fait un GRIEF, pas un vert.
        self.assertIsNone(V.files_de_la_page('<html>rien</html>'))

    def test_un_json_casse_rend_None(self):
        self.assertIsNone(V.files_de_la_page('var FILES = [{"key":;'))


class LeRapport(unittest.TestCase):

    def _lignes(self):
        d = []
        return d, d.append

    def test_tout_vert_sur_cinq_axes_rend_vrai(self):
        res = [{'titre': 't', 'q': 'q', 'ok': True, 'motif': 'm'}]
        _l, ecrire = self._lignes()
        self.assertTrue(V.rapport(res, {'axes': 5, 'non_testes': []},
                                  ecrire=ecrire))

    def test_un_grief_rend_faux(self):
        res = [{'titre': 't', 'q': 'q', 'ok': False, 'motif': 'm'}]
        _l, ecrire = self._lignes()
        self.assertFalse(V.rapport(res, {'axes': 5, 'non_testes': []},
                                   ecrire=ecrire))

    def test_une_portee_trop_courte_ne_rend_PAS_vert(self):
        res = [{'titre': 't', 'q': 'q', 'ok': True, 'motif': 'm'}]
        lignes, ecrire = self._lignes()
        self.assertFalse(V.rapport(res, {'axes': 2, 'non_testes': []},
                                   ecrire=ecrire))
        self.assertTrue(any('Portee insuffisante' in l for l in lignes))

    def test_un_code_PERIME_ne_rend_pas_vert(self):
        # Observer sans redemarrer, c'est observer l'ancien code.
        res = [{'titre': 't', 'q': 'q', 'ok': True, 'motif': 'm'}]
        lignes, ecrire = self._lignes()
        self.assertFalse(V.rapport(res, {'axes': 5, 'non_testes': [],
                                         'code_perime': True}, ecrire=ecrire))
        self.assertTrue(any('ANCIEN code' in l for l in lignes))

    def test_ce_qui_n_a_pas_ete_teste_est_DIT(self):
        res = [{'titre': 't', 'q': 'q', 'ok': True, 'motif': 'm'}]
        lignes, ecrire = self._lignes()
        V.rapport(res, {'axes': 5, 'non_testes': ['axe lieu sans positif']},
                  ecrire=ecrire)
        self.assertTrue(any('NON TESTE' in l for l in lignes))



class LaPageDoitAussiLeDIRE(unittest.TestCase):
    """Une grille vide sans un mot se lit comme un fonds pauvre."""

    def test_la_decomposition_de_la_page_est_relue(self):
        html = 'var SEARCHMETA = {"noms_inconnus": ["animal:Zzz"]};'
        self.assertEqual(V.meta_de_la_page(html),
                         {'noms_inconnus': ['animal:Zzz']})

    def test_une_page_sans_SEARCHMETA_rend_None(self):
        self.assertIsNone(V.meta_de_la_page('<html>rien</html>'))

    def test_une_valeur_js_du_mauvais_type_ne_passe_pas_pour_un_dict(self):
        self.assertIsNone(V.meta_de_la_page('var SEARCHMETA = [1,2];'))
if __name__ == '__main__':
    unittest.main(verbosity=0)
