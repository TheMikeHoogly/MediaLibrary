#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de `pilotage` — le canal d'arrêt/redémarrage du serveur.

Ce qui est protégé ici, dans l'ordre du risque :

1. **Un fichier douteux ne coupe JAMAIS le serveur.** Vide, absent, tronqué,
   binaire, mot inconnu : tout rend `marche`. Un pilotage qui tombe en panne
   doit laisser le service debout, pas l'éteindre.
2. **Les deux écritures possibles se valent** — CRLF de `echo` sous Windows,
   LF d'un shell POSIX, BOM éventuel.
3. **On n'écrit pas n'importe quoi** : une commande inconnue lève, plutôt que
   d'atterrir dans le fichier où le serveur la lirait comme `marche`.
"""

import os
import tempfile
import unittest
from pathlib import Path

import pilotage


class TestLire(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.f = Path(self.dir.name) / pilotage.FICHIER

    def tearDown(self):
        self.dir.cleanup()

    def ecrit_brut(self, octets):
        self.f.write_bytes(octets)

    def test_fichier_absent_rend_marche(self):
        self.assertEqual(pilotage.lire(self.f), 'marche')

    def test_dossier_a_la_place_du_fichier(self):
        self.assertEqual(pilotage.lire(Path(self.dir.name)), 'marche')

    def test_fichier_vide_rend_marche(self):
        self.ecrit_brut(b'')
        self.assertEqual(pilotage.lire(self.f), 'marche')

    def test_mot_inconnu_rend_marche(self):
        self.ecrit_brut(b'explose\n')
        self.assertEqual(pilotage.lire(self.f), 'marche')

    def test_binaire_rend_marche(self):
        self.ecrit_brut(bytes(range(0, 32)))
        self.assertEqual(pilotage.lire(self.f), 'marche')

    def test_fin_de_ligne_windows(self):
        self.ecrit_brut(b'redemarrer\r\n')
        self.assertEqual(pilotage.lire(self.f), 'redemarrer')

    def test_fin_de_ligne_posix(self):
        self.ecrit_brut(b'redemarrer\n')
        self.assertEqual(pilotage.lire(self.f), 'redemarrer')

    def test_sans_fin_de_ligne(self):
        self.ecrit_brut(b'arret')
        self.assertEqual(pilotage.lire(self.f), 'arret')

    def test_bom_utf8(self):
        self.ecrit_brut(b'\xef\xbb\xbfarret\r\n')
        self.assertEqual(pilotage.lire(self.f), 'arret')

    def test_casse_et_espaces(self):
        self.ecrit_brut(b'   REDEMARRER   \r\n')
        self.assertEqual(pilotage.lire(self.f), 'redemarrer')

    def test_seule_la_premiere_ligne_compte(self):
        self.ecrit_brut(b'arret\nredemarrer\n')
        self.assertEqual(pilotage.lire(self.f), 'arret')


class TestEcrire(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.f = Path(self.dir.name) / pilotage.FICHIER

    def tearDown(self):
        self.dir.cleanup()

    def test_aller_retour(self):
        for c in pilotage.COMMANDES:
            pilotage.ecrire(self.f, c)
            self.assertEqual(pilotage.lire(self.f), c)

    def test_commande_inconnue_leve(self):
        with self.assertRaises(ValueError):
            pilotage.ecrire(self.f, 'sudo rm')
        self.assertFalse(self.f.exists())

    def test_ecrit_en_ascii_pur(self):
        """Le fichier est relu par `cmd.exe` (`set /p`), qui n'aime que
        l'ASCII — même règle que les `.bat`."""
        pilotage.ecrire(self.f, 'redemarrer')
        self.f.read_bytes().decode('ascii')      # lève si non ASCII

    def test_aucun_fichier_temporaire_ne_traine(self):
        pilotage.ecrire(self.f, 'marche')
        restes = [p.name for p in Path(self.dir.name).iterdir()]
        self.assertEqual(restes, [pilotage.FICHIER])

    def test_normalise_la_casse(self):
        pilotage.ecrire(self.f, '  ARRET ')
        self.assertEqual(self.f.read_bytes(), b'arret\r\n')

    def test_fin_de_ligne_TOUJOURS_crlf(self):
        """L'autre lecteur est `cmd.exe` (`set /p`). Écrit depuis une VM Linux,
        un LF nu suffirait à faire échouer la comparaison côté batch — et le
        redémarrage serait perdu sans un mot."""
        for c in pilotage.COMMANDES:
            pilotage.ecrire(self.f, c)
            self.assertTrue(self.f.read_bytes().endswith(b'\r\n'), c)
            self.assertEqual(self.f.read_bytes().count(b'\n'), 1)


class TestDoitSortir(unittest.TestCase):

    def test_marche_ne_sort_pas(self):
        self.assertFalse(pilotage.doit_sortir('marche'))

    def test_les_deux_autres_sortent(self):
        self.assertTrue(pilotage.doit_sortir('redemarrer'))
        self.assertTrue(pilotage.doit_sortir('arret'))

    def test_un_mot_inconnu_ne_sort_pas(self):
        """`lire` ne rend jamais ça, mais si un appelant court-circuite `lire`,
        le défaut reste « on continue de servir »."""
        self.assertFalse(pilotage.doit_sortir('nimportequoi'))
        self.assertFalse(pilotage.doit_sortir(None))


class TestContrat(unittest.TestCase):

    def test_code_de_redemarrage_distinct_de_0_et_1(self):
        """Le superviseur distingue « redémarre-moi » d'un plantage par ce
        code. S'il valait 0 ou 1, une boucle de crash passerait pour une série
        de redémarrages voulus, et le garde-fou des cinq échecs ne servirait
        plus à rien."""
        self.assertNotIn(pilotage.CODE_REDEMARRAGE, (0, 1))

    def test_periode_de_veille_raisonnable(self):
        self.assertTrue(0.5 <= pilotage.PERIODE_S <= 10)

    def test_le_defaut_est_celui_qui_ne_fait_rien(self):
        self.assertEqual(pilotage.DEFAUT, 'marche')
        self.assertFalse(pilotage.doit_sortir(pilotage.DEFAUT))


if __name__ == '__main__':
    unittest.main(verbosity=2)
