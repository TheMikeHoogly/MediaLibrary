#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `recle_decisions` — la règle pure du re-clé des décisions humaines.

Pourquoi ce fichier existe
──────────────────────────
Le trou corrigé ici n'a rien cassé pendant des semaines : `store.rekey` renvoyait
faux en silence sur `PEOPLE` et `PETS`, et le TAG survivait par ailleurs (index +
XMP). Seule la VÉRITÉ TERRAIN partait — 928 décisions sur 3 364 mesurées le
22/08. Une panne muette se re-teste, elle ne se re-relit pas.

Aucun `import server` : construire les stores ouvrirait `photos.db`, dont le
serveur est l'écrivain unique (invariant du projet).
"""
import unittest

from recle_decisions import appliquer, recler_fiche

A = r"\\NAS\Photos\_A TRIER\dump\20240101_120000.jpg"
B = r"\\NAS\Photos\2024\20240101_120000.jpg"
C = r"\\NAS\Photos\2024\autre.jpg"


class RattachementsTest(unittest.TestCase):
    def test_recle_en_gardant_l_index(self):
        f = {'name': 'Flo', 'faces': [[A, 3], [C, 0]]}
        champs, n = recler_fiche(f, A, B)
        self.assertEqual(n, 1)
        self.assertEqual(champs['faces'], [[B, 3], [C, 0]])

    def test_plusieurs_visages_de_la_meme_photo(self):
        f = {'name': 'Flo', 'faces': [[A, 0], [A, 2]]}
        champs, n = recler_fiche(f, A, B)
        self.assertEqual(n, 2)
        self.assertEqual(champs['faces'], [[B, 0], [B, 2]])

    def test_pas_de_doublon_si_la_cible_est_deja_citee(self):
        # La photo avait été jugée sous ses DEUX chemins : le re-clé fusionne.
        f = {'name': 'Flo', 'faces': [[A, 1], [B, 1]]}
        champs, n = recler_fiche(f, A, B)
        self.assertEqual(champs['faces'], [[B, 1]])
        self.assertEqual(n, 1)

    def test_tuple_accepte_comme_liste(self):
        f = {'name': 'Flo', 'faces': [(A, 0)]}
        champs, _n = recler_fiche(f, A, B)
        self.assertEqual(champs['faces'], [[B, 0]])

    def test_entree_malformee_conservee_telle_quelle(self):
        # Ne jamais JETER ce qu'on ne comprend pas : on le transporte.
        f = {'name': 'Flo', 'faces': [[A, 0], 'bizarre']}
        champs, n = recler_fiche(f, A, B)
        self.assertEqual(champs['faces'], [[B, 0], 'bizarre'])
        self.assertEqual(n, 1)


class ExclusionsEtConfirmationsTest(unittest.TestCase):
    def test_exclusion_recle(self):
        f = {'name': 'Flo', 'exclude': [A, C]}
        champs, n = recler_fiche(f, A, B)
        self.assertEqual(champs['exclude'], [B, C])
        self.assertEqual(n, 1)

    def test_confirmation_recle(self):
        f = {'name': 'Flo', 'confirmed': [A]}
        champs, n = recler_fiche(f, A, B)
        self.assertEqual(champs['confirmed'], [B])
        self.assertEqual(n, 1)

    def test_exclusion_deja_presente_ne_double_pas(self):
        f = {'name': 'Flo', 'exclude': [A, B]}
        champs, _n = recler_fiche(f, A, B)
        self.assertEqual(champs['exclude'], [B])


class AvatarTest(unittest.TestCase):
    def test_avatar_transporte_mais_pas_compte(self):
        f = {'name': 'Flo', 'avatar': [A, 2]}
        champs, n = recler_fiche(f, A, B)
        self.assertEqual(champs['avatar'], [B, 2])
        self.assertEqual(n, 0, "l'avatar est dérivé, pas un jugement")


class RienAFaireTest(unittest.TestCase):
    def test_fiche_sans_la_cle_n_est_pas_touchee(self):
        f = {'name': 'Flo', 'faces': [[C, 0]], 'exclude': [C]}
        self.assertEqual(recler_fiche(f, A, B), ({}, 0))

    def test_meme_chemin_des_deux_cotes(self):
        f = {'name': 'Flo', 'faces': [[A, 0]]}
        self.assertEqual(recler_fiche(f, A, A), ({}, 0))

    def test_fiche_non_dict(self):
        self.assertEqual(recler_fiche(None, A, B), ({}, 0))
        self.assertEqual(recler_fiche('bizarre', A, B), ({}, 0))

    def test_refs_ne_sont_pas_des_chemins(self):
        # `refs` porte des EMBEDDINGS base64, pas des clés : n'y toucher jamais.
        f = {'name': 'Flo', 'refs': [A], 'faces': [[A, 0]]}
        champs, _n = recler_fiche(f, A, B)
        self.assertNotIn('refs', champs)


class AppliquerTest(unittest.TestCase):
    def test_mute_la_fiche(self):
        f = {'name': 'Luna', 'faces': [[A, 0]], 'exclude': [A]}
        n = appliquer(f, A, B)
        self.assertEqual(n, 2)
        self.assertEqual(f['faces'], [[B, 0]])
        self.assertEqual(f['exclude'], [B])

    def test_idempotent(self):
        f = {'name': 'Luna', 'faces': [[A, 0]]}
        appliquer(f, A, B)
        self.assertEqual(appliquer(f, A, B), 0)
        self.assertEqual(f['faces'], [[B, 0]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
