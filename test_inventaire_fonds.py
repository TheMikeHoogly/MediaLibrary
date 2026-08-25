#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `inventaire_fonds.py` — sans NAS, sans serveur.

Ce que ces tests tiennent
-------------------------
1. **Photos et videos ne sont pas melangees.** Une video de 4 Go pese autant
   que six cents photos : les additionner cacherait que la facture est due a
   trente fichiers.
2. **Ce qui n'a pas pu etre mesure est COMPTE et DIT.** Un fonds mesure a
   moitie qui se dit complet est le mode de panne de tout inventaire — la
   lecon payee deux fois le 23/08 sur les plafonds muets.
3. **Il n'ouvre rien.** Il lit une taille, il ne touche pas aux octets.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventaire_fonds as F  # noqa: E402


def arbre(base, fichiers):
    """`fichiers` : {chemin relatif: taille en octets}."""
    base = Path(base)
    for rel, taille in fichiers.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * taille)
    return base


class LesFamilles(unittest.TestCase):

    def test_photo_video_et_autre_sont_reconnus(self):
        for nom, attendu in (("a.JPG", 'photo'), ("b.heic", 'photo'),
                             ("c.NEF", 'photo'), ("d.mp4", 'video'),
                             ("e.MOV", 'video'), ("f.txt", 'autre'),
                             ("g", 'autre')):
            self.assertEqual(F.famille(nom), attendu, nom)

    def test_la_casse_de_l_extension_ne_change_rien(self):
        self.assertEqual(F.famille("X.JpEg"), F.famille("x.jpeg"))

    def test_photos_et_videos_sont_COMPTEES_A_PART(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_fonds_"))
        arbre(tmp, {"a.jpg": 100, "b.jpg": 200, "film.mp4": 5000,
                    "notes.txt": 7})
        pf, _gros, _ill = F.mesurer(tmp)
        self.assertEqual(pf['photo'], {'n': 2, 'octets': 300})
        self.assertEqual(pf['video'], {'n': 1, 'octets': 5000})
        self.assertEqual(pf['autre'], {'n': 1, 'octets': 7})

    def test_il_descend_dans_les_sous_dossiers(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_fonds2_"))
        arbre(tmp, {"2019/07/a.jpg": 10, "2020/b.jpg": 10})
        pf, _g, _i = F.mesurer(tmp)
        self.assertEqual(pf['photo']['n'], 2)


class CeQuIlNAPasPuLireEstDit(unittest.TestCase):

    def test_un_fichier_illisible_est_COMPTE_pas_ignore(self):
        def parcours_menteur(_racine):
            yield "a.jpg", 10
            yield "fantome.jpg", None

        pf, _g, ill = F.mesurer(".", parcours=parcours_menteur)
        self.assertEqual(ill, 1)
        self.assertEqual(pf['photo']['n'], 1)

    def test_un_dossier_interdit_ne_fait_pas_tomber_la_mesure(self):
        """Un partage qui refuse un sous-dossier ne doit pas emporter le
        reste : ce qui manque se compte, il ne fait pas tomber le banc."""
        pf, _g, _i = F.mesurer("/n/existe/pas/du/tout")
        self.assertEqual(pf, {})

    def test_le_rapport_DIT_que_le_total_est_un_plancher(self):
        dit = []
        F.rapport({'photo': {'n': 1, 'octets': 10}}, [], 3, ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("NON MESURES", texte)
        self.assertIn("PLANCHER", texte)

    def test_sans_illisible_il_ne_parle_pas_de_plancher(self):
        dit = []
        F.rapport({'photo': {'n': 1, 'octets': 10}}, [], 0, ecrire=dit.append)
        self.assertNotIn("PLANCHER", "\n".join(dit))


class LesGrosFichiers(unittest.TestCase):

    def test_les_plus_gros_sont_nommes_et_dans_l_ordre(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_fonds4_"))
        arbre(tmp, {"petit.jpg": 10, "moyen.jpg": 100, "enorme.mp4": 9999})
        _pf, gros, _i = F.mesurer(tmp)
        self.assertEqual(gros[0][0], 9999)
        self.assertTrue(gros[0][1].endswith("enorme.mp4"))
        self.assertGreaterEqual(gros[0][0], gros[-1][0])

    def test_la_liste_des_gros_est_BORNEE(self):
        """Un inventaire qui deverse ne rapporte plus."""
        tmp = Path(tempfile.mkdtemp(prefix="test_fonds5_"))
        arbre(tmp, {"f%03d.jpg" % i: i + 1 for i in range(F.GROS_MAX + 25)})
        _pf, gros, _i = F.mesurer(tmp)
        self.assertEqual(len(gros), F.GROS_MAX)


class IlNOuvreRien(unittest.TestCase):

    def test_aucune_lecture_ni_ecriture_de_contenu(self):
        source = Path(F.__file__).read_text(encoding='utf-8')
        for interdit in ('.read_bytes(', '.write_bytes(', 'open(chemin',
                         '.unlink(', 'os.remove('):
            self.assertNotIn(interdit, source, interdit + " : cet inventaire "
                             "lit des tailles, il ne touche pas aux octets")

    def test_les_fichiers_survivent_a_la_mesure(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_fonds6_"))
        arbre(tmp, {"a.jpg": 10})
        F.mesurer(tmp)
        self.assertEqual(os.path.getsize(tmp / "a.jpg"), 10)


class LeRapport(unittest.TestCase):

    def test_un_fonds_vide_ne_tombe_pas(self):
        dit = []
        r = F.rapport({}, [], 0, ecrire=dit.append)
        self.assertEqual(r['total_n'], 0)
        self.assertEqual(r['total_octets'], 0)

    def test_le_total_est_la_somme_des_familles(self):
        r = F.rapport({'photo': {'n': 2, 'octets': 300},
                       'video': {'n': 1, 'octets': 5000}}, [], 0,
                      ecrire=lambda *x: None)
        self.assertEqual(r['total_n'], 3)
        self.assertEqual(r['total_octets'], 5300)


if __name__ == '__main__':
    unittest.main(verbosity=0)
