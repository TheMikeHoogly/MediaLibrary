#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `dezipper_takeout.py` — sans Takeout, sans reseau, sans NAS.

Ce que ces tests tiennent
-------------------------
1. **Un lot manquant se VOIT.** C'est la seule panne qui, sans instrument,
   produit un arbre d'apparence complete : le reste de la chaine declarerait
   ABSENTES des photos que Google detient. Le total annonce par les noms
   (`-1-of-24`) prime sur le plus grand numero vu, sinon il manque la FIN de
   la serie sans que personne le sache.
2. **`10` vient apres `9`.** Un tri lexicographique melange les lots ; ca ne
   casse rien a l'arrivee, mais ca rend tout journal illisible.
3. **Un zip est une DONNEE, pas une instruction.** Un membre nomme
   `..\\..\\Windows\\x` ou `C:\\x` ecrirait ailleurs : il est refuse, compte
   et nomme.
4. **Reprenable.** Ce qui est deja la a la bonne taille est saute : relancer
   apres une coupure ne recommence pas 75 Go, et sur un dossier deja ouvert
   le script ne fait rien.
5. **Rien ne s'ecrit sans `--extraire`,** et rien ne s'ecrit sur un verdict
   rouge sans `--forcer`.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dezipper_takeout as D  # noqa: E402


def tmp(prefixe):
    d = Path(tempfile.mkdtemp(prefix=prefixe))
    return d


def zip_de(chemin, membres):
    """`membres` : {nom dans l'archive: contenu en octets}."""
    with zipfile.ZipFile(chemin, 'w') as zf:
        for nom, contenu in membres.items():
            zf.writestr(nom, contenu)
    return Path(chemin)


class LesNumerosDeLot(unittest.TestCase):

    def test_les_trois_formes_de_nom_sont_lues(self):
        self.assertEqual(D.numero_de_lot("takeout-20260826T101500Z-1-of-24.zip"),
                         (1, 24))
        self.assertEqual(D.numero_de_lot("takeout-20260826T101500Z-003.zip"),
                         (3, None))
        self.assertEqual(D.numero_de_lot("takeout-20260826T101500Z-7.zip"),
                         (7, None))

    def test_un_zip_etranger_n_a_pas_de_numero(self):
        # Sinon il creuserait un faux trou et bloquerait une extraction saine.
        self.assertIsNone(D.numero_de_lot("photos_de_mamie.zip"))

    def test_le_tri_met_10_apres_9(self):
        d = tmp("test_tri_")
        for n in (1, 2, 9, 10, 11):
            (d / ("takeout-20260826T101500Z-%d.zip" % n)).write_bytes(b"")
        noms = [p.name for p in D.lister_zips(d)]
        self.assertEqual([D.numero_de_lot(n)[0] for n in noms],
                         [1, 2, 9, 10, 11])

    def test_un_dossier_source_absent_ne_tombe_pas(self):
        self.assertEqual(D.lister_zips(Path(tempfile.gettempdir()) / "n_existe_pas_xyz"), [])


class LesTrous(unittest.TestCase):

    def test_un_trou_au_milieu_est_vu(self):
        noms = [Path("t-1.zip"), Path("t-2.zip"), Path("t-4.zip")]
        self.assertEqual(D.trous(noms), ([3], None))

    def test_la_FIN_manquante_est_vue_grace_au_total_annonce(self):
        # Le cas dangereux : 1..3 present, la serie en annonce 5.
        noms = [Path("t-1-of-5.zip"), Path("t-2-of-5.zip"), Path("t-3-of-5.zip")]
        self.assertEqual(D.trous(noms), ([4, 5], 5))

    def test_une_serie_complete_n_a_pas_de_trou(self):
        noms = [Path("t-%d-of-3.zip" % i) for i in (1, 2, 3)]
        self.assertEqual(D.trous(noms), ([], 3))

    def test_sans_aucun_numero_il_n_invente_pas_de_trou(self):
        self.assertEqual(D.trous([Path("a.zip"), Path("b.zip")]), ([], None))


class CeQueLesZipsDisent(unittest.TestCase):

    def test_les_fichiers_distincts_sont_comptes_une_fois(self):
        d = tmp("test_inv_")
        zip_de(d / "t-1.zip", {"Takeout/a.jpg": b"x" * 10})
        zip_de(d / "t-2.zip", {"Takeout/a.jpg": b"x" * 10,
                               "Takeout/b.jpg": b"y" * 20})
        inv = D.inventaire(D.lister_zips(d))
        self.assertEqual(inv['fichiers_distincts'], 2)
        self.assertEqual(inv['octets_distincts'], 30)
        self.assertEqual(inv['octets_ouverts'], 40)   # le doublon compte 2 fois
        self.assertEqual(inv['conflits'], [])

    def test_deux_exports_melanges_font_un_CONFLIT(self):
        d = tmp("test_conflit_")
        zip_de(d / "t-1.zip", {"Takeout/a.jpg": b"x" * 10})
        zip_de(d / "t-2.zip", {"Takeout/a.jpg": b"x" * 11})
        inv = D.inventaire(D.lister_zips(d))
        self.assertEqual(len(inv['conflits']), 1)
        self.assertEqual(inv['conflits'][0]['chemin'], "Takeout/a.jpg")

    def test_un_zip_illisible_est_NOMME_pas_ignore(self):
        d = tmp("test_casse_")
        (d / "t-1.zip").write_bytes(b"ceci n est pas un zip")
        inv = D.inventaire(D.lister_zips(d))
        self.assertEqual(len(inv['erreurs']), 1)
        self.assertEqual(inv['erreurs'][0]['zip'], "t-1.zip")


class LesCheminsQuiSortent(unittest.TestCase):

    def test_un_chemin_normal_atterrit_sous_la_cible(self):
        c = tmp("test_sur_")
        dest = D.chemin_sur(c, "Takeout/Google Photos/a.jpg")
        self.assertIsNotNone(dest)
        self.assertTrue(str(dest).startswith(str(c)))

    def test_le_parent_est_refuse(self):
        c = tmp("test_sur2_")
        self.assertIsNone(D.chemin_sur(c, "../evade.txt"))
        self.assertIsNone(D.chemin_sur(c, "a/../../evade.txt"))

    def test_une_lettre_de_lecteur_est_refusee(self):
        c = tmp("test_sur3_")
        self.assertIsNone(D.chemin_sur(c, "C:/Windows/x.dll"))

    def test_un_chemin_absolu_reste_sous_la_cible(self):
        c = tmp("test_sur4_")
        dest = D.chemin_sur(c, "/etc/passwd")
        self.assertIsNotNone(dest)
        self.assertTrue(str(dest).startswith(str(c)))


class LExtraction(unittest.TestCase):

    def _source(self, prefixe="test_ex_"):
        d = tmp(prefixe)
        zip_de(d / "t-1-of-2.zip", {"Takeout/Google Photos/a.jpg": b"a" * 10})
        zip_de(d / "t-2-of-2.zip", {"Takeout/Google Photos/b.jpg": b"b" * 20,
                                    "Takeout/archive_browser.html": b"h" * 5})
        return d

    def test_sans_appliquer_rien_n_est_ecrit(self):
        d = self._source()
        cible = d / "extrait"
        compte, octets, griefs, complet = D.extraire(D.lister_zips(d), cible,
                                                     appliquer=False,
                                                     ecrire=lambda *x: None)
        self.assertTrue(complet)
        self.assertEqual(compte['absent'], 3)
        self.assertEqual(len(griefs['absent']), 3)
        self.assertEqual(compte['ecrit'], 0)
        self.assertEqual(octets, 0)
        self.assertFalse(cible.exists())

    def test_l_arbre_est_reconstitue(self):
        d = self._source()
        cible = d / "extrait"
        compte, octets, _g, complet = D.extraire(D.lister_zips(d), cible,
                                                 appliquer=True,
                                                 ecrire=lambda *x: None)
        self.assertTrue(complet)
        self.assertEqual(compte['ecrit'], 3)
        self.assertEqual(octets, 35)
        self.assertEqual((cible / "Takeout/Google Photos/a.jpg").read_bytes(),
                         b"a" * 10)

    def test_relancer_ne_reecrit_RIEN(self):
        d = self._source()
        cible = d / "extrait"
        D.extraire(D.lister_zips(d), cible, appliquer=True,
                   ecrire=lambda *x: None)
        compte, octets, _g, _c = D.extraire(D.lister_zips(d), cible,
                                            appliquer=True,
                                            ecrire=lambda *x: None)
        self.assertEqual(compte['ecrit'], 0)
        self.assertEqual(compte['saute'], 3)
        self.assertEqual(octets, 0)

    def test_un_fichier_TRONQUE_est_reecrit(self):
        # La panne de disque plein : bon nom, mauvaise taille.
        d = self._source()
        cible = d / "extrait"
        D.extraire(D.lister_zips(d), cible, appliquer=True,
                   ecrire=lambda *x: None)
        (cible / "Takeout/Google Photos/a.jpg").write_bytes(b"a" * 3)
        compte, _o, _g, _c = D.extraire(D.lister_zips(d), cible,
                                        appliquer=True, ecrire=lambda *x: None)
        self.assertEqual(compte['ecrit'], 1)
        self.assertEqual((cible / "Takeout/Google Photos/a.jpg").stat().st_size, 10)

    def test_un_membre_qui_sort_de_la_cible_est_REFUSE_et_nomme(self):
        d = tmp("test_slip_")
        zip_de(d / "t-1.zip", {"Takeout/ok.jpg": b"o" * 4,
                               "../evade.txt": b"non"})
        cible = d / "extrait"
        compte, _o, griefs, _c = D.extraire(D.lister_zips(d), cible,
                                            appliquer=True,
                                            ecrire=lambda *x: None)
        self.assertEqual(compte['refuse'], 1)
        self.assertEqual(griefs['refuse'], ["../evade.txt"])
        self.assertEqual(compte['ecrit'], 1)
        self.assertFalse((d / "evade.txt").exists())


class LeControleDeLExtraction(unittest.TestCase):
    """Sans `appliquer`, la meme traversee CONTROLE ce qui a ete ouvert.

    « Extraction effectuee OK » n'est pas une preuve : le fichier tronque
    porte le bon nom, et c'est la seule panne de dezippage qui se lit comme un
    succes."""

    def _source(self):
        d = tmp("test_ctrl_")
        zip_de(d / "t-1-of-1.zip", {"Takeout/a.jpg": b"a" * 10,
                                    "Takeout/b.jpg": b"b" * 20})
        return d

    def test_une_extraction_complete_ne_laisse_aucun_grief(self):
        d = self._source()
        cible = d / "extrait"
        D.extraire(D.lister_zips(d), cible, appliquer=True,
                   ecrire=lambda *x: None)
        compte, _o, griefs, _c = D.extraire(D.lister_zips(d), cible,
                                            appliquer=False,
                                            ecrire=lambda *x: None)
        self.assertEqual(compte['saute'], 2)
        self.assertEqual((compte['absent'], compte['tronque']), (0, 0))
        self.assertEqual(griefs, {'absent': [], 'tronque': [], 'refuse': []})

    def test_un_fichier_MANQUANT_est_nomme_comme_absent(self):
        d = self._source()
        cible = d / "extrait"
        D.extraire(D.lister_zips(d), cible, appliquer=True,
                   ecrire=lambda *x: None)
        (cible / "Takeout/a.jpg").unlink()
        compte, _o, griefs, _c = D.extraire(D.lister_zips(d), cible,
                                            appliquer=False,
                                            ecrire=lambda *x: None)
        self.assertEqual(compte['absent'], 1)
        self.assertEqual(griefs['absent'], ["Takeout/a.jpg"])

    def test_un_fichier_TRONQUE_n_est_pas_confondu_avec_un_absent(self):
        d = self._source()
        cible = d / "extrait"
        D.extraire(D.lister_zips(d), cible, appliquer=True,
                   ecrire=lambda *x: None)
        (cible / "Takeout/b.jpg").write_bytes(b"b" * 7)
        compte, _o, griefs, _c = D.extraire(D.lister_zips(d), cible,
                                            appliquer=False,
                                            ecrire=lambda *x: None)
        self.assertEqual((compte['absent'], compte['tronque']), (0, 1))
        self.assertEqual(griefs['tronque'], ["Takeout/b.jpg"])


class LeVerdict(unittest.TestCase):

    def _dit(self):
        lignes = []
        return lignes, lignes.append

    def test_un_dossier_sans_zip_rend_ROUGE_sans_tomber(self):
        d = tmp("test_vide_")
        lignes, ecrire = self._dit()
        self.assertFalse(D.rapport(d, d / "extrait", [], D.inventaire([]),
                                   [], None, ecrire=ecrire))
        self.assertTrue(any("AUCUN" in l for l in lignes))

    def test_un_lot_manquant_rend_ROUGE(self):
        d = tmp("test_manque_")
        zip_de(d / "t-1-of-3.zip", {"a.jpg": b"a"})
        zip_de(d / "t-2-of-3.zip", {"b.jpg": b"b"})
        zips = D.lister_zips(d)
        manquants, total = D.trous(zips)
        lignes, ecrire = self._dit()
        ok = D.rapport(d, d / "extrait", zips, D.inventaire(zips),
                       manquants, total, ecrire=ecrire)
        self.assertFalse(ok)
        self.assertTrue(any("MANQUANT" in l for l in lignes))

    def test_une_serie_complete_rend_VERT(self):
        d = tmp("test_complet_")
        zip_de(d / "t-1-of-2.zip", {"a.jpg": b"a"})
        zip_de(d / "t-2-of-2.zip", {"b.jpg": b"b"})
        zips = D.lister_zips(d)
        manquants, total = D.trous(zips)
        lignes, ecrire = self._dit()
        self.assertTrue(D.rapport(d, d / "extrait", zips, D.inventaire(zips),
                                  manquants, total, ecrire=ecrire))

    def test_un_conflit_rend_ROUGE(self):
        d = tmp("test_confl2_")
        zip_de(d / "t-1-of-2.zip", {"a.jpg": b"a" * 3})
        zip_de(d / "t-2-of-2.zip", {"a.jpg": b"a" * 4})
        zips = D.lister_zips(d)
        lignes, ecrire = self._dit()
        self.assertFalse(D.rapport(d, d / "extrait", zips, D.inventaire(zips),
                                   [], 2, ecrire=ecrire))
        self.assertTrue(any("CONFLIT" in l for l in lignes))

    def test_la_place_manquante_rend_ROUGE(self):
        d = tmp("test_place_")
        zip_de(d / "t-1-of-1.zip", {"a.jpg": b"a" * 1000})
        zips = D.lister_zips(d)
        vrai = D.shutil.disk_usage
        D.shutil.disk_usage = lambda p: type('U', (), {'free': 10})()
        try:
            lignes, ecrire = self._dit()
            ok = D.rapport(d, d / "extrait", zips, D.inventaire(zips),
                           [], 1, ecrire=ecrire)
        finally:
            D.shutil.disk_usage = vrai
        self.assertFalse(ok)
        self.assertTrue(any("PAS ASSEZ DE PLACE" in l for l in lignes))


class LaSuite(unittest.TestCase):

    def test_le_dossier_Google_Photos_est_retrouve_en_profondeur(self):
        c = tmp("test_gp_")
        (c / "Takeout" / "Google Photos" / "2019").mkdir(parents=True)
        self.assertEqual(D.trouver_google_photos(c),
                         c / "Takeout" / "Google Photos")

    def test_a_defaut_il_rend_le_Takeout(self):
        c = tmp("test_gp2_")
        (c / "Takeout" / "Drive").mkdir(parents=True)
        self.assertEqual(D.trouver_google_photos(c), c / "Takeout")

    def test_sur_une_cible_absente_il_ne_tombe_pas(self):
        self.assertIsNone(D.trouver_google_photos(
            Path(tempfile.gettempdir()) / "n_existe_pas_xyz"))


class LaLigneDeCommande(unittest.TestCase):

    def test_sans_extraire_le_disque_reste_INTACT(self):
        d = tmp("test_cli_")
        zip_de(d / "t-1-of-1.zip", {"Takeout/a.jpg": b"a" * 5})
        code = D.main(['--source', str(d)])
        self.assertEqual(code, 0)
        self.assertFalse((d / "extrait").exists())

    def test_un_verdict_rouge_n_ecrit_rien_meme_avec_extraire(self):
        d = tmp("test_cli2_")
        zip_de(d / "t-1-of-3.zip", {"Takeout/a.jpg": b"a" * 5})
        code = D.main(['--source', str(d), '--extraire'])
        self.assertEqual(code, 1)
        self.assertFalse((d / "extrait").exists())

    def test_forcer_passe_outre(self):
        d = tmp("test_cli3_")
        zip_de(d / "t-1-of-3.zip", {"Takeout/a.jpg": b"a" * 5})
        code = D.main(['--source', str(d), '--extraire', '--forcer'])
        self.assertEqual(code, 1)          # le verdict reste rouge...
        self.assertTrue((d / "extrait" / "Takeout" / "a.jpg").exists())  # ...mais il a ecrit

    def test_le_json_porte_le_verdict(self):
        import json
        d = tmp("test_cli4_")
        zip_de(d / "t-1-of-1.zip", {"Takeout/a.jpg": b"a" * 5})
        j = d / "rapport.json"
        D.main(['--source', str(d), '--json', str(j)])
        r = json.loads(j.read_text(encoding='utf-8'))
        self.assertTrue(r['verdict_avant_extraction'])
        self.assertEqual(r['lots'], 1)
        self.assertEqual(r['fichiers_distincts'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=0)
