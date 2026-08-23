#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — le balayage de l'écart index/fichiers sur TOUS les noms.

Ce banc échantillonne : son honnêteté tient entièrement à trois choses, et
c'est ce que ces tests vérifient.

1. **Un compte et une estimation ne se mélangent pas.** Un nom entièrement lu
   rend un chiffre EXACT ; un nom échantillonné rend une projection. Présenter
   l'un pour l'autre ferait décider d'une réparation de plusieurs heures sur
   du vent.
2. **Le plafond se DIT.** Ce que la part laisse dehors est compté et affiché.
   C'est la leçon de `/api/people/photos`, payée deux fois le 23/08 : un
   plafond muet se lit comme une exhaustivité.
3. **La part ne dépasse jamais le fonds d'un nom.** Sinon un nom de 3 photos
   serait « estimé » alors qu'il est comptable exactement.
"""
import io
import unittest

import verifier_xmp_toutes_personnes as T


class Repartition(unittest.TestCase):

    def test_la_part_ne_depasse_jamais_le_fonds_du_nom(self):
        parts, non_lus = T.repartir([('a', 3), ('b', 100)], par_nom=8, budget=0)
        self.assertEqual(parts['a'], 3, "un nom de 3 photos se compte EXACTEMENT")
        self.assertEqual(parts['b'], 8)

    def test_ce_qui_reste_dehors_est_COMPTE(self):
        _, non_lus = T.repartir([('a', 3), ('b', 100)], par_nom=8, budget=0)
        self.assertEqual(non_lus, 92, "3-3 = 0 pour a, 100-8 = 92 pour b")

    def test_le_budget_global_reduit_au_prorata_sans_rien_annuler(self):
        comptes = [(f'n{i}', 50) for i in range(10)]
        parts, non_lus = T.repartir(comptes, par_nom=10, budget=40)
        self.assertLessEqual(sum(parts.values()), 45)
        self.assertTrue(all(v >= 1 for v in parts.values()),
                        "aucun nom ne doit tomber a zero : il disparaitrait "
                        "du rapport sans que personne le sache")
        self.assertGreater(non_lus, 400)

    def test_un_nom_sans_photo_ne_reclame_rien(self):
        parts, _ = T.repartir([('vide', 0)], par_nom=8, budget=0)
        self.assertEqual(parts['vide'], 0)


class Arithmetique(unittest.TestCase):

    def test_un_nom_lu_EN_ENTIER_rend_un_chiffre_exact_et_zero_estime(self):
        self.assertEqual(T.estimer(lus=342, manque=54, total=342), (54, 0))

    def test_un_nom_ECHANTILLONNE_rend_zero_exact_et_une_projection(self):
        exact, est = T.estimer(lus=200, manque=37, total=5562)
        self.assertEqual(exact, 0, "un echantillon ne CONSTATE pas, il projette")
        self.assertEqual(est, round(5562 * 37 / 200))

    def test_rien_de_lu_ne_produit_aucun_chiffre(self):
        self.assertEqual(T.estimer(lus=0, manque=0, total=900), (0, 0))

    def test_wilson_encadre_le_taux_et_reste_dans_les_bornes(self):
        b, h = T.wilson(37, 200)
        self.assertLess(b, 37 / 200.0)
        self.assertGreater(h, 37 / 200.0)
        self.assertGreaterEqual(b, 0.0)
        self.assertLessEqual(h, 1.0)

    def test_wilson_sur_zero_lecture_ne_divise_pas_par_zero(self):
        self.assertEqual(T.wilson(0, 0), (0.0, 1.0))


class LeRapportNeTaitRien(unittest.TestCase):

    def _texte(self, lignes, non_lus, file_serveur=0):
        buf = io.StringIO()
        T.rapporter(lignes, non_lus, file_serveur, len(lignes),
                    ecrire=lambda s='': buf.write(str(s) + "\n"))
        return buf.getvalue()

    def test_le_NON_LU_est_affiche_meme_quand_il_est_gros(self):
        txt = self._texte([{'nom': 'Mike', 'total': 5562, 'lus': 200,
                            'manque': 37, 'exact': 0, 'estime': 1029,
                            'illisible': 0}], non_lus=5362)
        self.assertIn('NON LUS', txt)
        self.assertIn('5362', txt)

    def test_exact_et_estime_sont_deux_lignes_DISTINCTES(self):
        txt = self._texte([
            {'nom': 'Ellie', 'total': 342, 'lus': 342, 'manque': 54,
             'exact': 54, 'estime': 0, 'illisible': 0},
            {'nom': 'Mike', 'total': 5562, 'lus': 200, 'manque': 37,
             'exact': 0, 'estime': 1029, 'illisible': 0}], non_lus=5362)
        self.assertIn('ECART CERTAIN', txt)
        self.assertIn('ECART ESTIME', txt)
        self.assertIn('54', txt)
        self.assertIn('1029', txt)
        self.assertIn('1083', txt, "le total des deux doit etre donne")

    def test_un_nom_marque_exact_ou_estime_dans_le_tableau(self):
        txt = self._texte([
            {'nom': 'Ellie', 'total': 342, 'lus': 342, 'manque': 54,
             'exact': 54, 'estime': 0, 'illisible': 0}], non_lus=0)
        self.assertIn('exact', txt)

    def test_une_file_qui_TOURNE_est_dite(self):
        txt = self._texte([{'nom': 'x', 'total': 1, 'lus': 1, 'manque': 1,
                            'exact': 1, 'estime': 0, 'illisible': 0}],
                          non_lus=0, file_serveur=1200)
        self.assertIn('1200', txt)
        self.assertIn('comblee', txt)


class LaLectureDesNoms(unittest.TestCase):
    """Le banc a d'abord lu la mauvaise clé (`names` au lieu de `noms`) et a
    rendu « 0 nom, 0 écart, 0 à réparer » sans broncher. Un rapport nul tiré
    d'une lecture ratée est le plus dangereux de tous : il a exactement
    l'allure d'une bonne nouvelle."""

    def _faux(self, charge):
        import contextlib, io, json as _json, urllib.request

        class R:
            def read(self_): return _json.dumps(charge).encode('utf-8')
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False

        @contextlib.contextmanager
        def patch():
            vrai = urllib.request.urlopen
            urllib.request.urlopen = lambda *a, **k: R()
            try:
                yield
            finally:
                urllib.request.urlopen = vrai
        return patch()

    def test_la_cle_de_la_route_est_bien_noms(self):
        with self._faux({'noms': [{'nom': 'Ellie', 'n': 342}]}):
            self.assertEqual(T.noms_du_serveur('http://x'), [('Ellie', 342)])

    def test_une_liste_nue_passe_aussi(self):
        with self._faux([{'nom': 'Mike', 'n': 5562}]):
            self.assertEqual(T.noms_du_serveur('http://x'), [('Mike', 5562)])

    def test_une_reponse_dont_on_ne_TIRE_RIEN_leve(self):
        with self._faux({'autre_chose': [{'nom': 'Ellie', 'n': 342}]}):
            with self.assertRaises(ValueError):
                T.noms_du_serveur('http://x')


class LeClassementNeRangePasDuBRUIT(unittest.TestCase):
    """Le premier jet rangeait « Val : 602 à réparer » sur DEUX écarts en
    QUATRE lectures. Le nombre avait l'air d'une priorité ; c'était un bruit
    de tirage. Un taux par nom exige assez de lectures, ou rien."""

    def _texte(self, lignes, non_lus=0):
        buf = io.StringIO()
        T.rapporter(lignes, non_lus, 0, len(lignes),
                    ecrire=lambda s='': buf.write(str(s) + "\n"))
        return buf.getvalue()

    def _l(self, nom, total, lus, manque):
        exact, est = T.estimer(lus, manque, total)
        return {'nom': nom, 'total': total, 'lus': lus, 'manque': manque,
                'exact': exact, 'estime': est, 'illisible': 0}

    def test_un_nom_lu_QUATRE_fois_n_est_pas_classe(self):
        txt = self._texte([self._l('Val', 1205, 4, 2)])
        self.assertNotIn('Val', txt)
        self.assertIn('moins de', txt, "leur absence doit etre DITE")

    def test_un_nom_assez_lu_est_classe(self):
        txt = self._texte([self._l('Mike', 5562, 200, 37)])
        self.assertIn('Mike', txt)

    def test_un_petit_nom_lu_EN_ENTIER_est_classe_meme_sous_le_seuil(self):
        """Trois photos lues sur trois, c'est un COMPTE, pas un echantillon."""
        txt = self._texte([self._l('Nino', 3, 3, 2)])
        self.assertIn('Nino', txt)
        self.assertIn('exact', txt)

    def test_quand_RIEN_n_est_classable_le_rapport_le_dit(self):
        txt = self._texte([self._l('Val', 1205, 4, 2),
                           self._l('Zab', 1016, 4, 2)])
        self.assertIn('taux GLOBAL', txt)

    def test_le_taux_global_reste_affiche_meme_sans_classement(self):
        txt = self._texte([self._l('Val', 1205, 4, 2)])
        self.assertIn('taux d ecart mesure', txt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
