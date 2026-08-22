#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_bat` — les trois façons dont un .bat ment.

Pourquoi ce fichier
───────────────────
`cmd.exe` ne dit presque jamais ce qui ne va pas. Trois défauts différents ont
déjà coûté au projet, et aucun ne produit un message utilisable :

1. **Un caractère non-ASCII** désaligne le parseur, qui exécute des fragments
   de lignes et SAUTE des étapes — y compris des vérifications. Commis 2×.
2. **Des fins de ligne LF** cassent les blocs multi-lignes : « qui etait
   inattendu ».
3. **Une parenthèse dans un `echo` à l'intérieur d'un bloc** ferme le bloc.
   Payé le 22/08 : « le dossier n'etait pas vide (git refuse), ou le reseau… »
   a tué le lanceur sur « ou etait inattendu » — un message qui ne nomme ni le
   fichier, ni la ligne, ni la cause.

Le contrôle du 3ᵉ cas est un HEURISTIQUE : il suit la profondeur des blocs. Ces
tests fixent ce qu'il doit attraper ET ce qu'il ne doit pas signaler — un
contrôle qui crie sur du code correct se fait désactiver, et ne protège alors
plus de rien.
"""

import unittest

import verifier_bat as V


def pbs(texte):
    return V.parentheses_dans_un_bloc(texte)


class TestCeQuIlDoitAttraper(unittest.TestCase):

    def test_le_cas_reel_du_22_08(self):
        p = pbs("if exist toto (\n"
                "    echo   pas vide (git refuse), ou le reseau.\n"
                ")\n")
        self.assertEqual(len(p), 1)
        self.assertIn('l.2', p[0])

    def test_une_parenthese_fermante_seule_compte_aussi(self):
        self.assertEqual(len(pbs("if a==b (\n    echo fin de citation)\n)\n")), 1)

    def test_dans_un_bloc_else(self):
        p = pbs("if a==b (\n    echo ok\n) else (\n    echo rate (voir plus haut)\n)\n")
        self.assertEqual(len(p), 1)
        self.assertIn('l.4', p[0])

    def test_dans_un_bloc_for(self):
        self.assertEqual(len(pbs("for %%f in (*) do (\n    echo (%%f)\n)\n")), 1)

    def test_deux_niveaux_de_bloc(self):
        p = pbs("if a==b (\n    if c==d (\n        echo (dedans)\n    )\n)\n")
        self.assertEqual(len(p), 1)


class TestCeQuIlNeDoitPasSignaler(unittest.TestCase):
    """Les faux positifs sont le vrai danger : ils font désactiver l'outil."""

    def test_hors_bloc_une_parenthese_est_inoffensive(self):
        self.assertEqual(pbs("echo   ceci (entre parentheses) va bien.\n"), [])

    def test_parenthese_echappee_dans_un_bloc(self):
        self.assertEqual(pbs("if a==b (\n    echo ceci ^(echappe^) passe\n)\n"), [])

    def test_apres_la_fermeture_du_bloc(self):
        self.assertEqual(pbs("if a==b (\n    echo ok\n)\necho ensuite (libre)\n"), [])

    def test_un_commentaire_n_est_pas_une_commande(self):
        self.assertEqual(pbs("if a==b (\n    REM ceci (commente) ne fait rien\n)\n"), [])

    def test_une_commande_qui_n_est_pas_echo(self):
        # `set` et consorts ont leurs propres regles ; ce controle ne parle
        # que de ce qu'il a vu casser, plutot que de deviner large.
        self.assertEqual(pbs("if a==b (\n    set /a X=(1+2)*3\n)\n"), [])

    def test_un_fichier_sans_aucun_bloc(self):
        self.assertEqual(pbs("@echo off\necho bonjour\npause\n"), [])


class TestLesAutresControles(unittest.TestCase):
    """Le contrôle neuf ne doit pas avoir désarmé les deux anciens."""

    def setUp(self):
        import shutil, tempfile
        from pathlib import Path
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def ecrire(self, octets):
        p = self.d / 'x.bat'
        p.write_bytes(octets)
        return p

    def test_non_ascii_toujours_detecte(self):
        p = self.ecrire("echo   déjà vu\r\n".encode('utf-8'))
        self.assertTrue(any('->' in x for x in V.controler(p)))

    def test_lf_toujours_detecte(self):
        p = self.ecrire(b"@echo off\necho a\n")
        self.assertTrue(any('CRLF' in x for x in V.controler(p)))

    def test_bom_toujours_detecte(self):
        p = self.ecrire(b"\xef\xbb\xbf@echo off\r\n")
        self.assertTrue(any('BOM' in x for x in V.controler(p)))

    def test_un_bat_propre_ne_dit_rien(self):
        p = self.ecrire(b"@echo off\r\nif exist toto goto :suite\r\n"
                        b"echo   absent\r\n:suite\r\npause\r\n")
        self.assertEqual(V.controler(p), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
