#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `journaux_deplacements` — les journaux d'annulation relus à l'endroit.

Ce module est la PREUVE la plus forte dont dispose le projet pour dire « cette
photo est devenue celle-là » : pas un nom qui se ressemble, pas un vecteur qui
s'en approche, le geste lui-même. Il mérite d'être testé sur ses trois formes de
journal et sur ses deux refus (journal annulé, boucle).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from journaux_deplacements import chaines, suivre

A = r"\\NAS\Photos\_A TRIER\dump\x.jpg"
B = r"\\NAS\Photos\2024\x.jpg"
C = r"\\NAS\Photos\2024\20240101_x.jpg"


class Bac(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def ecrire(self, nom, contenu):
        (self.d / nom).write_text(json.dumps(contenu, ensure_ascii=False),
                                  encoding='utf-8')


class ChainesTest(Bac):
    def test_deplacement_par_annee(self):
        self.ecrire('undo_annee_1.json',
                    {'operations': [{'old_key': A, 'new_key': B}]})
        self.assertEqual(chaines(self.d), {A: B})

    def test_renommage_est_une_liste(self):
        self.ecrire('undo_renommage_1.json', [{'old_key': B, 'new_key': C}])
        self.assertEqual(chaines(self.d), {B: C})

    def test_doublon_absorbe_mene_au_canonique(self):
        self.ecrire('undo_rangement_1.json', {'operations': [
            {'src': A, 'dst': r"\\NAS\Photos\.corbeille-rangement\ab\x.jpg",
             'canonique': B}]})
        c = chaines(self.d)
        self.assertEqual(c[A], B)
        self.assertEqual(c[r"\\NAS\Photos\.corbeille-rangement\ab\x.jpg"], B)

    def test_journal_annule_ignore(self):
        self.ecrire('undo_annee_1.annule.json',
                    {'operations': [{'old_key': A, 'new_key': B}]})
        self.assertEqual(chaines(self.d), {})

    def test_reclassement_ignore(self):
        # Il ne déplace aucun fichier : personne ↔ animal.
        self.ecrire('undo_reclassement_1.json', {'noms': [{'nom': 'Mutz',
                                                           'keys': [A]}]})
        self.assertEqual(chaines(self.d), {})

    def test_journal_illisible_saute_sans_planter(self):
        (self.d / 'undo_annee_2.json').write_text('{ pas du json',
                                                  encoding='utf-8')
        self.ecrire('undo_annee_1.json',
                    {'operations': [{'old_key': A, 'new_key': B}]})
        self.assertEqual(chaines(self.d), {A: B})

    def test_dossier_absent(self):
        self.assertEqual(chaines(self.d / 'nulle-part'), {})

    def test_premier_journal_gagne(self):
        # Les journaux sont lus dans l'ordre chronologique de leur nom : le
        # premier déplacement d'une clé est le bon départ de la chaîne.
        self.ecrire('undo_annee_1.json',
                    {'operations': [{'old_key': A, 'new_key': B}]})
        self.ecrire('undo_annee_2.json',
                    {'operations': [{'old_key': A, 'new_key': C}]})
        self.assertEqual(chaines(self.d)[A], B)


class SuivreTest(unittest.TestCase):
    def test_un_saut(self):
        self.assertEqual(suivre({A: B}, A, {B}), B)

    def test_deux_sauts_deplacee_puis_renommee(self):
        self.assertEqual(suivre({A: B, B: C}, A, {C}), C)

    def test_rien_de_vivant_au_bout(self):
        self.assertIsNone(suivre({A: B}, A, set()))

    def test_aucune_chaine(self):
        self.assertIsNone(suivre({}, A, {B}))

    def test_boucle_bornee(self):
        self.assertIsNone(suivre({A: B, B: A}, A, {C}))

    def test_chaine_trop_longue(self):
        longue = {f'k{i}': f'k{i+1}' for i in range(50)}
        self.assertIsNone(suivre(longue, 'k0', {'k49'}, sauts=3))


if __name__ == '__main__':
    unittest.main(verbosity=2)
