#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_raccourcis` -- l'instrument du point 6 du plancher.

Un instrument qui rend vert sans savoir rougir est pire que pas
d'instrument : il endort. Chaque contrôle ci-dessous fabrique la panne que
l'instrument doit voir, et vérifie qu'il la voit. Deux d'entre eux gardent
un défaut trouvé au PREMIER lancement sur les vraies pages (31/08) :
l'espace effacé par `strip()`, et la plage `A`-`Z` développée en vingt-six
faux griefs.
"""
import unittest

from verifier_raccourcis import (PLAGE_LETTRE, canon, lettres_de_plage,
                                 touches_documentees, touches_ecoutees)


class LeReleveDuCode(unittest.TestCase):

    def test_egalite_simple(self):
        self.assertEqual(touches_ecoutees("if (e.key === 'Enter') go();"),
                         {'Entree'})

    def test_l_espace_est_releve(self):
        # Defaut du premier lancement : `strip()` reduisait ' ' a '' et la
        # touche qui JUGE une carte disparaissait du releve.
        self.assertIn('Espace', touches_ecoutees("if (e.key === ' ') ok();"))

    def test_la_difference_compte_autant_que_l_egalite(self):
        # `if (ev.key !== '/') return;` est la forme des raccourcis de la
        # brique commune -- l'ignorer rendait l'instrument aveugle aux seuls
        # raccourcis presents sur TOUTES les pages.
        self.assertEqual(touches_ecoutees("if (ev.key !== '/') return;"), {'/'})

    def test_la_plage_de_lettres_est_UNE_entree(self):
        self.assertEqual(
            touches_ecoutees("else if (/^[a-zA-Z]$/.test(e.key)) saisir();"),
            {PLAGE_LETTRE})

    def test_une_constante_de_lettres_est_LUE_pas_devinee(self):
        src = "var LETTRES = 'ABCD';\nvar n = LETTRES.indexOf(e.key.toUpperCase());"
        self.assertEqual(touches_ecoutees(src), {'A', 'B', 'C', 'D'})

    def test_la_casse_ne_fabrique_pas_deux_touches(self):
        self.assertEqual(touches_ecoutees("e.key === 'z' || e.key === 'Z'"),
                         {'Z'})

    def test_une_source_sans_raccourci_ne_rend_rien(self):
        self.assertEqual(touches_ecoutees("var key = f.key; go(key);"), set())


class LeReleveDeLaDoc(unittest.TestCase):

    DOC = ("## Partout\n\n| Touche | Effet |\n|---|---|\n"
           "| `/` | focus |\n| `Echap` | ferme |\n\n"
           "## Juger\n\n| Touche | Effet |\n|---|---|\n"
           "| `Espace` / `Entree` | oui |\n| `A`-`D` | cocher |\n")

    def test_premiere_colonne_seulement(self):
        t = touches_documentees(self.DOC)
        self.assertLessEqual({'/', 'Echap', 'Espace', 'Entree'}, t)
        self.assertNotIn('FOCUS', t)

    def test_les_separateurs_ne_sont_pas_des_touches(self):
        self.assertNotIn('---', touches_documentees(self.DOC))

    def test_une_plage_courte_se_developpe(self):
        self.assertEqual(lettres_de_plage('| `A`-`D` |'), {'A', 'B', 'C', 'D'})

    def test_une_plage_large_est_la_PLAGE(self):
        # Defaut du premier lancement : `A`-`Z` developpee fabriquait seize
        # griefs (« I, J, K... promises et plus ecoutees »).
        self.assertEqual(lettres_de_plage('| toute lettre `A`-`Z` |'),
                         {PLAGE_LETTRE})

    def test_ce_qui_suit_le_marqueur_de_fin_ne_compte_pas(self):
        md = self.DOC + '\n<!-- panneau: fin -->\n| `Z` | note interne |\n'
        self.assertNotIn('Z', touches_documentees(md))


class LesDeuxGriefs(unittest.TestCase):
    """Le coeur : l'instrument doit VOIR chacune des deux pannes."""

    DOC = "| Touche | Effet |\n|---|---|\n| `Entree` | valider |\n"

    def test_une_touche_ecoutee_et_non_documentee_est_vue(self):
        ecoutees = touches_ecoutees("e.key === 'Enter' || e.key === 'F2'")
        muettes = ecoutees - touches_documentees(self.DOC)
        self.assertEqual(muettes, {'F2'})

    def test_une_touche_promise_et_plus_ecoutee_est_vue(self):
        doc = self.DOC + '| `Suppr` | effacer |\n'
        fantomes = touches_documentees(doc) - touches_ecoutees("e.key === 'Enter'")
        self.assertEqual(fantomes, {'Suppr'})

    def test_le_vocabulaire_se_rencontre_des_deux_cotes(self):
        # Le code dit « Escape », la doc ecrit « Echap » : sans la table de
        # correspondance, les deux ne se croisent jamais et TOUT est grief.
        self.assertEqual(canon('Escape'), canon('Échap'))
        self.assertEqual(canon('Enter'), canon('Entrée'))
        self.assertEqual(canon('ArrowLeft'), canon('←'))
        code = touches_ecoutees("e.key === 'Escape' || e.key === 'ArrowLeft'")
        doc = touches_documentees('| `Échap` | x |\n| `←` | y |\n')
        self.assertEqual(code - doc, set())


if __name__ == '__main__':
    unittest.main(verbosity=1)
