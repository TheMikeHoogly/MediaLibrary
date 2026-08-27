#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_trailer_samsung.py` — sans NAS, sans base, sans serveur.

Ce que ces tests tiennent
-------------------------
1. **Une correlation n'est pas une cause, et le rapport le DIT.** C'est la
   phrase la plus importante de cet instrument : il lit, il croise, il ne
   sait pas qui a coupe. Un banc qui conclurait << notre code coupe le
   trailer >> ferait exactement ce que ce projet reproche a ses bancs.
2. **La portee est restreinte aux photos SAMSUNG.** Elles seules portent un
   SEF ; compter les autres diluerait le denominateur jusqu'a rendre
   n'importe quel taux rassurant.
3. **Un trailer non vide n'est pas un SEF.** On demande la MARQUE, pas la
   taille : une vignette oubliee ou un octet de bourrage n'est pas un bloc
   Samsung.
4. **Une ligne vide ne compare rien** — et ne rend pas vert.
5. **L'echantillon est REGULIER, pas tire au sort** : deux executions doivent
   juger les memes fichiers, sinon un ecart de resultat ne se distingue pas
   d'un ecart d'echantillon.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_trailer_samsung as T  # noqa: E402


def segment(marqueur, charge):
    n = len(charge) + 2
    return bytes([0xFF, marqueur, n >> 8, n & 0xFF]) + charge


def jpeg(make=b'SAMSUNG', nomme=False, trailer=b''):
    """Un JPEG minimal : SOI, un APP1 de metadonnee, tables, cadre, SOS."""
    meta = b'Exif\x00\x00' + (make or b'')
    if nomme:
        meta += b'<dc:subject>personne:Florine</dc:subject>'
    out = b'\xff\xd8' + segment(0xE1, meta)
    out += segment(0xDB, b'\x00' + b'\x10' * 64)
    out += segment(0xC0, b'\x08\x00\x10\x00\x10\x01\x01\x11\x00')
    out += segment(0xDA, b'\x01\x01\x00\x00\x3f\x00')
    return out + b'\x11' * 64 + b'\xff\xd9' + trailer


SEF = b'\x00' * 200 + b'SEFH' + b'\x00' * 100 + b'SEFT'


def ecrire(dossier, nom, octets):
    p = Path(dossier) / nom
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(octets)
    return str(p)


class LesDeuxFaitsLusDansLeFichier(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="test_sef_")

    def test_une_photo_samsung_nommee_avec_son_SEF(self):
        p = ecrire(self.d, 'a.jpg', jpeg(nomme=True, trailer=SEF))
        f = T.lire_faits(p)
        self.assertTrue(f['samsung'])
        self.assertTrue(f['nomme'])
        self.assertEqual(f['trailer'], len(SEF))
        self.assertTrue(T.a_un_sef(p, f['trailer']))

    def test_un_animal_compte_comme_un_nom_ecrit_par_nous(self):
        p = ecrire(self.d, 'b.jpg', jpeg())
        Path(p).write_bytes(jpeg().replace(b'Exif\x00\x00',
                                           b'Exif\x00\x00animal:Luna '))
        self.assertTrue(T.lire_faits(p)['nomme'])

    def test_une_photo_non_nommee_n_est_pas_prise_pour_une_nommee(self):
        p = ecrire(self.d, 'c.jpg', jpeg(nomme=False, trailer=SEF))
        self.assertFalse(T.lire_faits(p)['nomme'])

    def test_un_trailer_qui_n_est_PAS_un_SEF_ne_compte_pas(self):
        # Une vignette oubliee, du bourrage : ce n'est pas un bloc Samsung.
        p = ecrire(self.d, 'd.jpg', jpeg(trailer=b'\x00' * 2000))
        f = T.lire_faits(p)
        self.assertEqual(f['trailer'], 2000)
        self.assertFalse(T.a_un_sef(p, f['trailer']))

    def test_sans_trailer_il_n_y_a_rien_a_chercher(self):
        p = ecrire(self.d, 'e.jpg', jpeg())
        self.assertEqual(T.lire_faits(p)['trailer'], 0)
        self.assertFalse(T.a_un_sef(p, 0))

    def test_ce_qui_n_est_pas_un_JPEG_rend_None(self):
        p = ecrire(self.d, 'f.jpg', b'pas un jpeg')
        self.assertIsNone(T.lire_faits(p))

    def test_un_fichier_absent_rend_None_sans_lever(self):
        self.assertIsNone(T.lire_faits(os.path.join(self.d, 'rien.jpg')))


class LaPortee(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="test_sef2_")

    def test_une_photo_qui_n_est_pas_SAMSUNG_est_ECARTEE_pas_comptee(self):
        p = ecrire(self.d, 'g.jpg', jpeg(make=b'Canon'))
        t, hors, _e = T.croiser([p], ecrire=lambda *x: None, chaque=0)
        self.assertEqual(hors['pas_samsung'], 1)
        self.assertEqual(sum(t.values()), 0)

    def test_un_illisible_est_COMPTE_a_part(self):
        p = ecrire(self.d, 'h.jpg', b'xx')
        _t, hors, _e = T.croiser([p], ecrire=lambda *x: None, chaque=0)
        self.assertEqual(hors['illisible'], 1)

    def test_le_croisement_range_dans_les_quatre_cases(self):
        c = [ecrire(self.d, 'n1.jpg', jpeg(nomme=True, trailer=SEF)),
             ecrire(self.d, 'n2.jpg', jpeg(nomme=True)),
             ecrire(self.d, 'l1.jpg', jpeg(trailer=SEF)),
             ecrire(self.d, 'l2.jpg', jpeg())]
        t, _h, _e = T.croiser(c, ecrire=lambda *x: None, chaque=0)
        self.assertEqual(t[('nomme', 'sef')], 1)
        self.assertEqual(t[('nomme', 'sans')], 1)
        self.assertEqual(t[('libre', 'sef')], 1)
        self.assertEqual(t[('libre', 'sans')], 1)


class LEchantillon(unittest.TestCase):

    def test_il_est_REGULIER_donc_reproductible(self):
        faux = [('/f/%03d.jpg' % i, 10) for i in range(100)]
        a, n = T.echantillon(['/f'], 10, parcours=lambda r: iter(faux))
        b, _n = T.echantillon(['/f'], 10, parcours=lambda r: iter(faux))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 10)
        self.assertEqual(n, 100)

    def test_un_fonds_plus_petit_que_l_echantillon_passe_en_entier(self):
        faux = [('/f/a.jpg', 1), ('/f/b.jpg', 1)]
        a, n = T.echantillon(['/f'], 50, parcours=lambda r: iter(faux))
        self.assertEqual(len(a), 2)
        self.assertEqual(n, 2)

    def test_ce_qui_n_est_pas_un_JPEG_n_entre_pas_dans_l_echantillon(self):
        faux = [('/f/a.jpg', 1), ('/f/b.mp4', 1), ('/f/c.JPEG', 1)]
        a, _n = T.echantillon(['/f'], 10, parcours=lambda r: iter(faux))
        self.assertEqual(len(a), 2)


class LeVerdict(unittest.TestCase):

    def _dit(self, nse, nsa, lse, lsa):
        lignes = []
        t = {('nomme', 'sef'): nse, ('nomme', 'sans'): nsa,
             ('libre', 'sef'): lse, ('libre', 'sans'): lsa}
        ok = T.rapport(t, {'illisible': 0, 'pas_samsung': 0}, 1000, 400,
                       ecrire=lignes.append)
        return ok, lignes

    def test_le_soupcon_confirme_rend_ROUGE(self):
        # 0 nommee sur 120 a garde son SEF ; 90 non nommees sur 100 l ont.
        ok, lignes = self._dit(0, 120, 90, 10)
        self.assertFalse(ok)
        self.assertTrue(any('NE SE CHEVAUCHENT PAS' in l for l in lignes))

    def test_aucun_ecart_rend_VERT(self):
        ok, lignes = self._dit(80, 20, 80, 20)
        self.assertTrue(ok)
        self.assertTrue(any('Rien n accuse' in l for l in lignes))

    def test_un_ecart_que_l_echantillon_ne_tranche_pas_le_DIT(self):
        ok, lignes = self._dit(3, 2, 4, 1)
        self.assertTrue(ok)
        self.assertTrue(any('CHEVAUCHENT' in l for l in lignes))

    def test_une_ligne_VIDE_ne_compare_rien_et_ne_rend_pas_vert(self):
        ok, lignes = self._dit(0, 0, 90, 10)
        self.assertFalse(ok)
        self.assertTrue(any('ne compare rien' in l for l in lignes))

    def test_la_limite_est_DITE_meme_quand_c_est_vert(self):
        # << Une correlation ne dit pas qui coupe >> : toujours ecrit.
        _ok, lignes = self._dit(80, 20, 80, 20)
        self.assertTrue(any('NE PROUVE PAS' in l for l in lignes))
        self.assertTrue(any('geste de Mike' in l for l in lignes))


class LExclusion(unittest.TestCase):
    """Ce qui vient d'etre importe fabriquerait la correlation cherchee.

    Les 3 776 photos rapatriees du Takeout sont des copies de Google : SEF
    intact, pas encore nommees. Les compter gonflerait la case
    << non nommee, avec SEF >> et prouverait ce qu'on voulait trouver."""

    def test_un_morceau_de_chemin_retire_les_fichiers_concernes(self):
        faux = [('/f/Photos/a.jpg', 1),
                ('/f/_A TRIER/Takeout Google/2024/b.jpg', 1),
                ('/f/Photos/c.jpg', 1)]
        a, n = T.echantillon(['/f'], 10, parcours=lambda r: iter(faux),
                             exclure=('Takeout',))
        self.assertEqual(len(a), 2)
        self.assertEqual(n, 2)
        self.assertEqual(T._ECARTES_CHEMIN, 1)

    def test_l_exclusion_ignore_la_casse(self):
        faux = [('/f/TAKEOUT/a.jpg', 1), ('/f/b.jpg', 1)]
        a, _n = T.echantillon(['/f'], 10, parcours=lambda r: iter(faux),
                              exclure=('takeout',))
        self.assertEqual(len(a), 1)

    def test_sans_exclusion_le_rapport_le_DIT(self):
        lignes = []
        T.rapport({('nomme', 'sef'): 1, ('nomme', 'sans'): 1,
                   ('libre', 'sef'): 1, ('libre', 'sans'): 1},
                  {'illisible': 0, 'pas_samsung': 0}, 10, 4,
                  ecrire=lignes.append)
        self.assertTrue(any('aucune exclusion' in l for l in lignes))

    def test_avec_exclusion_le_rapport_NOMME_ce_qui_est_exclu(self):
        lignes = []
        T.rapport({('nomme', 'sef'): 1, ('nomme', 'sans'): 1,
                   ('libre', 'sef'): 1, ('libre', 'sans'): 1},
                  {'illisible': 0, 'pas_samsung': 0}, 10, 4,
                  exclure=('Takeout',), ecartes=3776, ecrire=lignes.append)
        self.assertTrue(any('EXCLUS' in l and '3776' in l for l in lignes))


if __name__ == '__main__':
    unittest.main(verbosity=0)
