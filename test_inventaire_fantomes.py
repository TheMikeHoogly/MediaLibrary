#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `inventaire_fantomes.py` — sans NAS, sans serveur.

Ce que ces tests tiennent
-------------------------
1. **Il ne confond pas un fantome avec une photo dont le nom lui ressemble.**
   `endswith`, jamais `in`.
2. **Il separe les deux cas.** Un fantome dont l'original est intact a cote est
   effacable ; un fantome SANS original est peut-etre la seule copie qui reste
   (ExifTool mort entre le remplacement et le renommage). Les melanger, c'est
   proposer une suppression de donnees comme du menage.
3. **Il n'efface RIEN.** Famille `inventaire_`, lecture seule.
4. **Il ne tait pas ce qu'il ne liste pas.** Un plafond muet se lit comme un
   fonds propre — la lecon payee deux fois le 23/08.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventaire_fantomes as I  # noqa: E402


def arbre(base, fichiers):
    base = Path(base)
    for rel in fichiers:
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 10)
    return base


class CeQuIlReconnait(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test_fantomes_"))

    def test_un_fantome_est_trouve(self):
        arbre(self.tmp, ["2019/a.jpg", "2019/a.jpg_exiftool_tmp"])
        f = I.trouver(self.tmp)
        self.assertEqual(len(f), 1)
        self.assertTrue(f[0]['chemin'].endswith("a.jpg_exiftool_tmp"))

    def test_une_photo_dont_le_NOM_ressemble_n_en_est_pas_un(self):
        """`endswith`, pas `in` : sinon l'inventaire proposerait d'effacer une
        vraie photo."""
        arbre(self.tmp, ["mon_exiftool_tmp_backup.jpg"])
        self.assertEqual(I.trouver(self.tmp), [])

    def test_il_descend_dans_les_sous_dossiers(self):
        arbre(self.tmp, ["a/b/c/x.jpg", "a/b/c/x.jpg_exiftool_tmp"])
        self.assertEqual(len(I.trouver(self.tmp)), 1)

    def test_un_fonds_propre_rend_une_liste_vide(self):
        arbre(self.tmp, ["2019/a.jpg", "2019/b.jpg"])
        self.assertEqual(I.trouver(self.tmp), [])


class LesDeuxCasNeSeMelangentPas(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test_fantomes2_"))

    def test_l_original_intact_est_signale_comme_present(self):
        arbre(self.tmp, ["a.jpg", "a.jpg_exiftool_tmp"])
        self.assertTrue(I.trouver(self.tmp)[0]['original_present'])

    def test_un_fantome_SANS_original_est_signale(self):
        """Peut-etre la seule copie qui reste : l'effacer serait une perte."""
        arbre(self.tmp, ["a.jpg_exiftool_tmp"])
        self.assertFalse(I.trouver(self.tmp)[0]['original_present'])

    def test_le_rapport_les_COMPTE_a_part(self):
        arbre(self.tmp, ["a.jpg", "a.jpg_exiftool_tmp", "b.jpg_exiftool_tmp"])
        r = I.rapport(I.trouver(self.tmp), ecrire=lambda *x: None)
        self.assertEqual(r['n'], 2)
        self.assertEqual(r['avec_original'], 1)
        self.assertEqual(r['sans_original'], 1)

    def test_le_rapport_NOMME_les_orphelins_et_previent(self):
        arbre(self.tmp, ["b.jpg_exiftool_tmp"])
        dit = []
        I.rapport(I.trouver(self.tmp), ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("NE PAS EFFACER EN LOT", texte)
        self.assertIn("b.jpg_exiftool_tmp", texte)

    def test_un_fonds_PROPRE_ne_parle_pas_de_photos_bloquees(self):
        """Observe le 24/08 : sur zero fantome, le rapport annoncait quand
        meme <<photos BLOQUEES : 0>> suivi de son explication. Un rapport qui
        recite son avertissement quand il n a rien trouve apprend a le lire
        sans le voir."""
        dit = []
        I.rapport([], ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertNotIn("BLOQUEES", texte)
        self.assertIn("Aucun", texte)

    def test_le_rapport_ne_propose_la_suppression_que_s_il_y_a_a_effacer(self):
        dit = []
        I.rapport([], ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertNotIn("Remove-Item", texte)
        self.assertIn("Aucun", texte)


class IlNEffaceRien(unittest.TestCase):

    def test_le_fichier_est_toujours_la_apres_l_inventaire(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_fantomes3_"))
        arbre(tmp, ["a.jpg", "a.jpg_exiftool_tmp"])
        I.rapport(I.trouver(tmp), ecrire=lambda *x: None)
        self.assertTrue((tmp / "a.jpg_exiftool_tmp").is_file())
        self.assertTrue((tmp / "a.jpg").is_file())

    def test_aucun_unlink_ni_remove_dans_le_module(self):
        """La garantie se lit dans le code, pas seulement dans un test."""
        source = Path(I.__file__).read_text(encoding='utf-8')
        for interdit in ('.unlink(', 'os.remove(', 'shutil.rmtree('):
            self.assertNotIn(interdit, source, interdit + " dans une famille "
                             "inventaire_ : elle est en lecture seule")


class IlNeTaitPasCeQuIlNeListePas(unittest.TestCase):

    def test_au_dela_du_plafond_le_reste_est_COMPTE(self):
        faux = [{'chemin': 'x%d_exiftool_tmp' % i, 'original': 'x%d' % i,
                 'original_present': False, 'octets': 1, 'quand': 1.0}
                for i in range(I.LISTE_MAX + 7)]
        dit = []
        I.rapport(faux, ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("et 7 autre(s) non listes", texte)

    def test_le_compte_total_est_dit_meme_quand_la_liste_est_coupee(self):
        faux = [{'chemin': 'x%d_exiftool_tmp' % i, 'original': 'x%d' % i,
                 'original_present': False, 'octets': 1, 'quand': 1.0}
                for i in range(I.LISTE_MAX + 7)]
        r = I.rapport(faux, ecrire=lambda *x: None)
        self.assertEqual(r['n'], I.LISTE_MAX + 7)


class LesRacines(unittest.TestCase):

    def test_elles_viennent_des_fichiers_du_SERVEUR(self):
        """Un inventaire qui regarde ailleurs que la ou l'on ecrit ne mesure
        rien."""
        tmp = Path(tempfile.mkdtemp(prefix="test_fantomes4_"))
        (tmp / "conf.txt").write_text(
            "# un commentaire\n\n\\\\NAS\\home\\Photos\n", encoding='utf-8')
        self.assertEqual(I.racines([tmp / "conf.txt"]),
                         ["\\\\NAS\\home\\Photos"])

    def test_les_doublons_ne_sont_pas_balayes_deux_fois(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_fantomes5_"))
        (tmp / "a.txt").write_text("\\\\NAS\\P\n", encoding='utf-8')
        (tmp / "b.txt").write_text("\\\\NAS\\P\n", encoding='utf-8')
        self.assertEqual(I.racines([tmp / "a.txt", tmp / "b.txt"]),
                         ["\\\\NAS\\P"])

    def test_un_fichier_absent_ne_fait_pas_tomber_l_inventaire(self):
        self.assertEqual(I.racines(["/n/existe/pas.txt"]), [])


if __name__ == '__main__':
    unittest.main(verbosity=0)
