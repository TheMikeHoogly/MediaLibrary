#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc de `comptes` : mot de passe, jeton, frein, porte, fichier.
Sortie ASCII (console cp1252). Aucun `import server`."""

import json
import tempfile
import unittest
from pathlib import Path

import comptes as C

C.TOURS = 2_000     # le banc ne mesure pas le cout du hachage, il mesure la regle


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.chemin = Path(self.tmp.name) / 'comptes.json'
        self.c = C.Comptes(self.chemin)

    def tearDown(self):
        self.tmp.cleanup()


class Noms(unittest.TestCase):
    def test_nom_valide(self):
        for ok in ('Mike', 'Flo', 'Papa', 'Jean-Luc', 'Ana Maria'):
            self.assertTrue(C.nom_valide(ok), ok)
        for ko in ('', '  ', 'a|b', 'a:b', 'a/b', 'a\\b', 'x' * 41, None):
            self.assertFalse(C.nom_valide(ko), repr(ko))


class Porte(Base):
    def test_sans_compte_tout_est_ouvert(self):
        self.assertFalse(self.c.actifs())
        for ch in ('/', '/people', '/api/people/list', '/media/0/x.jpg'):
            self.assertEqual(self.c.porte(ch, None), 'ouvert')

    def test_avec_un_compte_la_porte_se_ferme(self):
        self.c.creer('Mike', 'motdepasse')
        self.assertTrue(self.c.actifs())
        self.assertEqual(self.c.porte('/people', None), 'connexion')
        self.assertEqual(self.c.porte('/api/people/list', None), 'refus')
        self.assertEqual(self.c.porte('/media/0/x.jpg', None), 'connexion')
        self.assertEqual(self.c.porte('/people', 'Mike'), 'ok')
        self.assertEqual(self.c.porte('/api/thumb', 'Flo'), 'ok')
        # ce qui reste ouvert : la connexion elle-meme, les agents locaux, l'UI
        for ch in ('/connexion', '/api/connexion', '/api/serveur', '/ui/base.css'):
            self.assertEqual(self.c.porte(ch, None), 'ouvert', ch)


class MotDePasse(Base):
    def test_creer_et_verifier(self):
        self.c.creer('Mike', 'motdepasse')
        self.assertEqual(self.c.verifier('Mike', 'motdepasse'), 'Mike')
        self.assertIsNone(self.c.verifier('Mike', 'motdepassE'))
        self.assertIsNone(self.c.verifier('Flo', 'motdepasse'))
        self.assertIsNone(self.c.verifier('', ''))
        self.assertEqual(self.c.verifier(' Mike ', 'motdepasse'), 'Mike')

    def test_jamais_en_clair(self):
        self.c.creer('Mike', 'motdepasse')
        brut = self.chemin.read_text(encoding='utf-8')
        self.assertNotIn('motdepasse', brut)
        d = json.loads(brut)
        self.assertEqual(set(d['comptes']['Mike']), {'sel', 'hache', 'admin', 'cree_le'})
        self.assertTrue(d['comptes']['Mike']['admin'])       # Mike = auteurs.ADMIN

    def test_regles_de_creation(self):
        with self.assertRaises(ValueError):
            self.c.creer('Mike', 'court')
        with self.assertRaises(ValueError):
            self.c.creer('a|b', 'motdepasse')
        self.c.creer('Flo', 'motdepasse')
        with self.assertRaises(ValueError):
            self.c.creer('Flo', 'autrechose')
        self.assertFalse(self.c.est_admin('Flo'))
        self.c.creer('Papa', 'motdepasse', admin=True)
        self.assertTrue(self.c.est_admin('Papa'))

    def test_changer_et_supprimer(self):
        self.c.creer('Flo', 'motdepasse')
        self.c.changer_mdp('Flo', 'nouveaumdp')
        self.assertIsNone(self.c.verifier('Flo', 'motdepasse'))
        self.assertEqual(self.c.verifier('Flo', 'nouveaumdp'), 'Flo')
        self.c.creer('Mike', 'motdepasse')
        with self.assertRaises(ValueError):
            self.c.supprimer('Mike')
        self.c.supprimer('Flo')
        self.assertEqual(self.c.noms(), ['Mike'])
        with self.assertRaises(ValueError):
            self.c.supprimer('Flo')

    def test_le_frein(self):
        self.c.creer('Mike', 'motdepasse')
        t = 1_000_000.0
        for i in range(C.ECHECS_MAX):
            self.assertIsNone(self.c.verifier('Mike', 'faux', maintenant=t + i))
        # cinq echecs : meme le BON mot de passe attend
        self.assertGreater(self.c.freine('Mike', t + 5), 0)
        self.assertIsNone(self.c.verifier('Mike', 'motdepasse', maintenant=t + 5))
        # une minute plus tard, la porte se rouvre, et le succes efface l'ardoise
        self.assertEqual(self.c.verifier('Mike', 'motdepasse', maintenant=t + 5 + C.ATTENTE), 'Mike')
        self.assertEqual(self.c.freine('Mike', t + 5 + C.ATTENTE + 1), 0)
        # un nom inconnu se freine aussi (sinon le frein dirait qui existe)
        for i in range(C.ECHECS_MAX):
            self.c.verifier('Zzz', 'faux', maintenant=t + i)
        self.assertGreater(self.c.freine('Zzz', t + 5), 0)


class Jeton(Base):
    def test_aller_retour_et_expiration(self):
        self.c.creer('Mike', 'motdepasse')
        t = 1_000_000.0
        j = self.c.jeton('Mike', maintenant=t)
        self.assertEqual(self.c.lire_jeton(j, maintenant=t + 10), 'Mike')
        self.assertIsNone(self.c.lire_jeton(j, maintenant=t + C.DUREE_SESSION + 1))
        self.assertIsNone(self.c.lire_jeton(j[:-1] + ('0' if j[-1] != '0' else '1'), maintenant=t))
        self.assertIsNone(self.c.lire_jeton('Mike|999999999999|abc', maintenant=t))
        self.assertIsNone(self.c.lire_jeton('', maintenant=t))
        self.assertIsNone(self.c.lire_jeton(None, maintenant=t))

    def test_un_compte_supprime_perd_son_jeton(self):
        self.c.creer('Mike', 'motdepasse')
        self.c.creer('Flo', 'motdepasse')
        j = self.c.jeton('Flo')
        self.assertEqual(self.c.lire_jeton(j), 'Flo')
        self.c.supprimer('Flo')
        self.assertIsNone(self.c.lire_jeton(j))

    def test_revoquer_tout(self):
        self.c.creer('Mike', 'motdepasse')
        j = self.c.jeton('Mike')
        self.c.revoquer_tout()
        self.assertIsNone(self.c.lire_jeton(j))
        self.assertEqual(self.c.lire_jeton(self.c.jeton('Mike')), 'Mike')

    def test_le_secret_survit_au_redemarrage(self):
        self.c.creer('Mike', 'motdepasse')
        j = self.c.jeton('Mike')
        c2 = C.Comptes(self.chemin)      # « redemarrage »
        self.assertEqual(c2.lire_jeton(j), 'Mike')
        self.assertEqual(c2.verifier('Mike', 'motdepasse'), 'Mike')

    def test_le_serveur_voit_un_compte_cree_a_cote(self):
        import time
        c2 = C.Comptes(self.chemin)
        self.assertFalse(c2.actifs())
        time.sleep(0.02)
        self.c.creer('Mike', 'motdepasse')         # « creer_compte.py », un autre processus
        self.assertTrue(c2.recharger_si_change())
        self.assertTrue(c2.actifs())
        self.assertEqual(c2.verifier('Mike', 'motdepasse'), 'Mike')
        self.assertFalse(c2.recharger_si_change())

    def test_fichier_absent_ou_corrompu(self):
        self.chemin.write_text('{pas du json', encoding='utf-8')
        c = C.Comptes(self.chemin)
        self.assertFalse(c.actifs())
        self.assertEqual(c.porte('/people', None), 'ouvert')


class Cookie(unittest.TestCase):
    def test_lecture(self):
        self.assertEqual(C.cookie_session('a=1; session=Mike|1|ab; b=2'), 'Mike|1|ab')
        self.assertEqual(C.cookie_session('session=x'), 'x')
        self.assertIsNone(C.cookie_session('a=1'))
        self.assertIsNone(C.cookie_session(''))
        self.assertIsNone(C.cookie_session(None))
        self.assertIsNone(C.cookie_session('session='))


if __name__ == '__main__':
    unittest.main()
