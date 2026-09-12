#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La passe « motifs » de la galerie : UNE classification par photo.

Ce que ce fichier protege (12/09)
---------------------------------
1. **Le compte et le filtre lisent la MEME liste.** L'ecriture d'avant
   appelait `interet.classer_regle` DEUX fois par photo des qu'un filtre etait
   pose : une fois pour compter les motifs, une fois pour filtrer. Le temps
   n'est pas le sujet principal — deux lectures de la meme regle peuvent
   DIVERGER, et alors le bandeau annonce un compte que la grille ne montre
   pas. C'est le mode de panne que ce projet paye le plus cher : muet.
2. **La moitie DOSSIER de la regle est memoisee**, parce qu'elle ne depend que
   du dossier et qu'une page de 2 519 photos n'en porte que deux ou trois.
   La memoire ne doit rien changer a la reponse.
3. **`indice_nom` lit le NOM, pas le chemin.** Elle utilisait `Path`, qui ne
   coupe pas les `\\` sous Linux : le motif se cherchait alors dans le chemin
   ENTIER, et un dossier `Screenshots` faisait passer toutes ses photos pour
   des captures PAR LEUR NOM. Invisible en prod (Windows), faux dans les
   bancs — donc invisible tout court.

Le banc lit `server.py` par l'arbre syntaxique et ne l'importe PAS.
"""
import ast
import io
import os
import unittest

import interet

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.py')

with io.open(SERVER, encoding='utf-8') as _f:
    SOURCE = _f.read()
ARBRE = ast.parse(SOURCE)


def _galerie():
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == '_serve_gallery':
            return n
    raise AssertionError('_serve_gallery introuvable')


class UneSeuleClassificationParPhoto(unittest.TestCase):

    def test_classer_regle_n_est_appelee_QU_UNE_fois_dans_la_galerie(self):
        """Sur les APPELS de l'arbre. Deux appels, c'est deux lectures qui
        peuvent se contredire — pas seulement deux fois le prix."""
        appels = [c for c in ast.walk(_galerie())
                  if isinstance(c, ast.Call)
                  and ast.unparse(c.func) == 'interet.classer_regle']
        self.assertEqual(len(appels), 1, ast.unparse(_galerie().body[-1])[:0]
                         or 'la passe motifs classe deux fois la meme photo')

    def test_le_compte_et_le_filtre_partagent_la_MEME_liste(self):
        """Le lien entre les deux : `_cats`, batie une fois."""
        src = ast.unparse(_galerie())
        self.assertIn('_cats = [interet.classer_regle', src)
        self.assertIn('zip(file_data, _cats)', src)


class LaRegleDuDossierEstMemoisee(unittest.TestCase):

    CAS = [
        (r'\\\\NAS\\Photos\\Screenshots\\x.jpg', ('capture', 'dossier Screenshots')),
        (r'\\\\NAS\\Photos\\Scans\\y.jpg', ('document', 'dossier Scans')),
        (r'\\\\NAS\\Photos\\2016\\z.jpg', (None, None)),
        ('A/Screenshots/w.jpg', ('capture', 'dossier Screenshots')),
        ('z.jpg', (None, None)),
        ('', (None, None)),
    ]

    def test_la_reponse_ne_change_pas(self):
        for cle, attendu in self.CAS:
            self.assertEqual(interet.classer_regle(cle), attendu, cle)

    def test_deux_photos_du_MEME_dossier_ne_coutent_qu_un_calcul(self):
        interet._regle_du_dossier.cache_clear()
        for nom in ('a.jpg', 'b.jpg', 'c.jpg'):
            interet.classer_regle('\\\\NAS\\Photos\\2016\\' + nom)
        self.assertEqual(interet._regle_du_dossier.cache_info().misses, 1)

    def test_deux_dossiers_DIFFERENTS_ne_se_confondent_pas(self):
        interet._regle_du_dossier.cache_clear()
        self.assertEqual(interet.classer_regle('A\\\\Screenshots\\\\x.jpg')[0],
                         'capture')
        self.assertEqual(interet.classer_regle('A\\\\2016\\\\x.jpg')[0], None)
        self.assertEqual(interet.classer_regle('A\\\\Scans\\\\x.jpg')[0],
                         'document')

    def test_les_DEUX_barres_coupent(self):
        """Une cle du NAS porte des `\\`, une cle d'Uploads des `/`."""
        for cle in ('A\\\\Screenshots\\\\x.jpg', 'A/Screenshots/x.jpg',
                    'A\\\\Screenshots/x.jpg'):
            self.assertEqual(interet.classer_regle(cle),
                             ('capture', 'dossier Screenshots'), cle)

    def test_le_cache_est_BORNE(self):
        info = interet._regle_du_dossier.cache_info()
        self.assertIsNotNone(info.maxsize)
        self.assertGreaterEqual(info.maxsize, 4096)

    def test_le_NOM_prime_toujours_sur_le_dossier(self):
        """L'ordre des deux moities ne doit pas avoir bouge : le nom d'abord,
        avec son motif lisible, le dossier en repli."""
        self.assertEqual(
            interet.classer_regle('A\\\\2016\\\\Screenshot_20200101.png'),
            ('capture', 'Screenshot_'))


class LaRegleDuNomEstMemoiseeAussi(unittest.TestCase):
    """Elle ne depend que du NOM NU — et deux copies d'une photo dans deux
    dossiers portent le meme nom."""

    def test_deux_cles_de_MEME_nom_ne_coutent_qu_un_calcul(self):
        interet._indice_du_nom_nu.cache_clear()
        interet.indice_nom('A\\2016\\Screenshot_20200101.png')
        interet.indice_nom('B\\autre\\Screenshot_20200101.png')
        self.assertEqual(interet._indice_du_nom_nu.cache_info().misses, 1)
        self.assertEqual(interet._indice_du_nom_nu.cache_info().hits, 1)

    def test_un_nom_SANS_motif_est_memoise_aussi(self):
        """La grande majorite des photos ne matchent RIEN : si le cache ne
        gardait pas ce cas, il ne servirait presque jamais."""
        interet._indice_du_nom_nu.cache_clear()
        self.assertEqual(interet.indice_nom('A\\2016\\vacances.jpg'),
                         (None, None))
        self.assertEqual(interet.indice_nom('B\\2017\\vacances.jpg'),
                         (None, None))
        self.assertEqual(interet._indice_du_nom_nu.cache_info().misses, 1)

    def test_le_cache_est_BORNE(self):
        info = interet._indice_du_nom_nu.cache_info()
        self.assertIsNotNone(info.maxsize)
        self.assertGreaterEqual(info.maxsize, 44605)

    def test_la_memoire_ne_change_pas_la_reponse(self):
        for cle, attendu in (
                ('A\\2016\\Screenshot_20200101.png', 'capture'),
                ('A\\2016\\vacances.jpg', None)):
            interet._indice_du_nom_nu.cache_clear()
            froid = interet.indice_nom(cle)
            chaud = interet.indice_nom(cle)
            self.assertEqual(froid, chaud)
            self.assertEqual(froid[0], attendu, cle)


class IndiceNomLitLeNOM(unittest.TestCase):
    """Elle utilisait `Path`, qui ne coupe pas les `\\` sous Linux."""

    def test_un_dossier_capture_ne_fait_pas_du_NOM_une_capture(self):
        cat, motif = interet.indice_nom('A\\\\Screenshots\\\\vacances.jpg')
        self.assertIsNone(cat, 'le motif a ete cherche dans le CHEMIN')

    def test_le_nom_seul_est_toujours_lu(self):
        self.assertEqual(
            interet.indice_nom('A\\\\2016\\\\Screenshot_20200101.png')[0],
            'capture')

    def test_les_deux_barres_coupent_aussi_ici(self):
        self.assertIsNone(interet.indice_nom('A/Screenshots/vacances.jpg')[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
