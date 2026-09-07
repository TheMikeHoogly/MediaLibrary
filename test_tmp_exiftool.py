#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banc du ramassage des `_exiftool_tmp` orphelins (defaut du 07/09 au soir).

LE DEFAUT. Quand l'ecriture XMP depasse son delai, `subprocess.run` TUE
ExifTool et relance l'exception ; son `finally` ne ramasse que l'argfile, et le
`<photo>_exiftool_tmp` deja ecrit sur le NAS reste. Toute ecriture ulterieure
sur cette photo echoue alors POUR TOUJOURS (« Temporary file already exists »),
la reparation de dernier recours comprise, et la photo est abandonnee. Mesure
du 07/09 : 13 photos en huit heures, une toutes les 30 a 60 minutes, soit 60 a
80 sur les cinq jours restants de la campagne.

CE QUE CE BANC PROUVE. La regle pure (`ecriture_meta.tmp_orphelin`) reconnait
CE refus-la et pas un autre ; le ramassage n'efface QUE sur preuve ; et le
cablage fait les deux choses qui manquaient : reessayer une fois apres avoir
ramasse, et ramasser aussi quand l'appel a ete tue.

La fonction `ramasser_tmp_exiftool` est LUE dans `server.py` par `ast` puis
executee dans un module vide : `import server` ouvrirait `photos.db`, que la VM
ne sait meme pas ouvrir en lecture par-dessus le montage.
"""

import ast
import contextlib
import io
import shutil
import tempfile
import types
import unittest
from pathlib import Path

import ecriture_meta as E

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py")


def _src(nom):
    return ast.get_source_segment(SOURCE, _noeud(nom)) or ""


def _corps(nom):
    """La fonction SANS sa docstring — un banc juge du code, pas d'une prose."""
    n = _noeud(nom)
    corps = n.body[1:] if (n.body and isinstance(n.body[0], ast.Expr)
                           and isinstance(n.body[0].value, ast.Constant)
                           and isinstance(n.body[0].value.value, str)) else n.body
    return "\n".join(ast.get_source_segment(SOURCE, x) or "" for x in corps)


def _charger_ramasser():
    """`ramasser_tmp_exiftool` seule, dans un module vide (pas de photos.db)."""
    mod = types.ModuleType("_ramasse")
    mod.__dict__['Path'] = Path
    exec(compile(_src("ramasser_tmp_exiftool"), "<server.py>", "exec"),
         mod.__dict__)
    return mod.ramasser_tmp_exiftool


RAMASSER = _charger_ramasser()


def ramasser(path):
    """`ramasser_tmp_exiftool` avec sa sortie CAPTUREE — rend (verdict, dit).

    Deux raisons. (1) La console de Mike est en **cp1252** : le `⚠` des
    messages de refus n'y passe pas, et ce banc etait VERT sur la VM (UTF-8)
    et ROUGE chez lui, sur les trois cas qui impriment. Le serveur est
    protege depuis le 22/08 (`journal_serveur`) ; un banc lance a la main ne
    l'est pas. (2) Capturer permet de verifier que le refus est NOMME, ce que
    ce banc ne verifiait pas : un refus muet ferait chercher la panne
    ailleurs."""
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        verdict = RAMASSER(path)
    return verdict, tampon.getvalue()


class LaRegleReconnaitCeRefusLa(unittest.TestCase):
    def test_le_vrai_message(self):
        self.assertTrue(E.tmp_orphelin(
            "Error: Temporary file already exists: "
            "//NAS-Bremblens/home/Photos/Photos Flo/Sista/x.jpg_exiftool_tmp"))

    def test_et_pas_un_autre(self):
        # L'EXIF illisible a DEJA sa voie (XMP + IPTC seulement) : les
        # confondre enverrait une photo saine sur le chemin du ramassage.
        for autre in ("Error reading OtherImageStart data in IFD0",
                      "Warning: [minor] Bad IFD", "", None):
            self.assertFalse(E.tmp_orphelin(autre), repr(autre))

    def test_les_deux_regles_ne_se_marchent_pas_dessus(self):
        illisible = "Error reading OtherImageStart data in IFD0"
        self.assertTrue(E.exif_illisible(illisible))
        self.assertFalse(E.tmp_orphelin(illisible))


class OnN_effacePasSansPreuve(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tmpexif_"))
        self.photo = self.tmp / "photo.jpg"
        self.orphelin = Path(str(self.photo) + "_exiftool_tmp")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ramasse_une_copie_tronquee(self):
        self.photo.write_bytes(b"X" * 1000)
        self.orphelin.write_bytes(b"X" * 400)
        verdict, dit = ramasser(self.photo)
        self.assertTrue(verdict)
        self.assertEqual(dit, "")            # un succes ne bavarde pas
        self.assertFalse(self.orphelin.exists())
        self.assertTrue(self.photo.exists())          # la photo ne bouge pas
        self.assertEqual(self.photo.stat().st_size, 1000)

    def test_photo_absente_on_garde_le_tmp(self):
        # Sans la photo, le tmp est peut-etre tout ce qui reste : l'effacer
        # serait exactement la perte qu'on pretend eviter.
        self.orphelin.write_bytes(b"X" * 400)
        verdict, dit = ramasser(self.photo)
        self.assertFalse(verdict)
        self.assertIn("photo d origine manque", dit)
        self.assertTrue(self.orphelin.exists())

    def test_tmp_plus_gros_que_la_photo_on_garde(self):
        # Le tmp est cense etre une copie TRONQUEE. S'il est plus gros, ce
        # n'est pas le cas qu'on a mesure — on ne devine pas, on garde.
        self.photo.write_bytes(b"X" * 100)
        self.orphelin.write_bytes(b"X" * 900)
        verdict, dit = ramasser(self.photo)
        self.assertFalse(verdict)
        self.assertIn("pas plus petit", dit)
        self.assertTrue(self.orphelin.exists())

    def test_taille_egale_on_garde(self):
        self.photo.write_bytes(b"X" * 500)
        self.orphelin.write_bytes(b"X" * 500)
        verdict, dit = ramasser(self.photo)
        self.assertFalse(verdict)
        self.assertIn("pas plus petit", dit)
        self.assertTrue(self.orphelin.exists())

    def test_pas_de_tmp_rien_a_faire_et_pas_d_erreur(self):
        self.photo.write_bytes(b"X" * 100)
        verdict, dit = ramasser(self.photo)
        self.assertFalse(verdict)
        self.assertEqual(dit, "")            # rien a faire : rien a dire
        self.assertTrue(self.photo.exists())

    def test_ne_parcourt_jamais_le_disque(self):
        # « Balayage jamais par defaut » (CLAUDE.md) : le chemin est celui de
        # la photo qu'on ecrit, jamais le resultat d'une recherche.
        s = _corps("ramasser_tmp_exiftool")
        for interdit in ("glob", "rglob", "iterdir", "walk", "scandir"):
            self.assertNotIn(interdit, s, interdit)


class LeCablageFaitLesDeuxChoses(unittest.TestCase):
    def setUp(self):
        self.s = _corps("write_metadata")

    def test_ramasse_puis_reessaie_une_fois(self):
        self.assertIn("ecriture_meta.tmp_orphelin(err) and "
                      "ramasser_tmp_exiftool(path)", self.s)
        apres = self.s.split("ramasser_tmp_exiftool(path)")[1]
        self.assertIn("_run_exiftool(", apres.split("if ecriture_meta.exif_illisible")[0])

    def test_une_seule_fois(self):
        # Reessayer en boucle sur un NAS qui refuse ferait une file bloquee.
        self.assertEqual(self.s.count("ramasser_tmp_exiftool(path)"), 2)

    def test_le_timeout_ramasse_ce_qu_il_vient_d_orpheliner(self):
        # C'est LA le defaut : subprocess.run tue le processus et son finally
        # ne ramasse que l'argfile.
        garde = self.s.split("except Exception as e:")[1]
        self.assertIn("ramasser_tmp_exiftool(path)", garde)

    def test_l_ordre_est_conserve(self):
        # Le tmp orphelin se traite AVANT l'EXIF illisible : sinon la voie
        # « XMP + IPTC seulement » echouerait pour la meme raison, sans le
        # dire, et la photo partirait quand meme en reparation.
        self.assertLess(self.s.index("tmp_orphelin"),
                        self.s.index("exif_illisible"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
