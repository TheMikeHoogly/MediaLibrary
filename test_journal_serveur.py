#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — le journal du serveur.

Pourquoi ce fichier
───────────────────
Ce journal existe pour qu'un défaut cesse de dépendre de quelqu'un qui regarde
une fenêtre `cmd.exe` au bon moment. Il n'a donc le droit d'échouer sur rien :
un disque plein, une console qui refuse un caractère, un thread qui meurt —
aucun de ces cas ne doit tuer la photothèque, et aucun ne doit non plus
disparaître en silence. C'est exactement ce que ces tests tiennent.

Le point le plus facile à rater : `print` écrit le texte PUIS le saut de ligne,
en deux appels. Un journal qui date chaque appel produirait des demi-lignes
horodatées, illisibles — donc invérifiables, donc inutiles.
"""

import faulthandler
import io
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import journal_serveur as J                                    # noqa: E402


class FauxFluxCP1252:
    """Une console Windows : elle refuse ce qui n'est pas dans cp1252."""

    encoding = 'cp1252'

    def __init__(self):
        self.vu = []

    def write(self, texte):
        texte.encode('cp1252')          # lève UnicodeEncodeError, comme la vraie
        self.vu.append(texte)
        return len(texte)

    def flush(self):
        pass

    def isatty(self):
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.chemin = self.tmp / '_journal_serveur.log'
        self.journal = J.Journal(self.chemin)

    def tearDown(self):
        self.journal.fermer()

    def lire(self):
        return self.chemin.read_text(encoding='utf-8')


class LeJournal(Base):

    def test_chaque_ligne_porte_une_heure(self):
        """Sans heure, « ca a plante » ne se recoupe avec rien : ni un clic, ni
        un redemarrage, ni un banc."""
        self.journal.ecrire("quelque chose")
        ligne = self.lire().strip()
        self.assertRegex(ligne, r'^\d{2}:\d{2}:\d{2} quelque chose$')

    def test_un_texte_multiligne_est_date_ligne_par_ligne(self):
        """Un traceback fait dix lignes : une seule datée et neuf orphelines
        rendraient le recoupement impossible au milieu du tas."""
        self.journal.ecrire("un\ndeux\ntrois")
        for ligne in self.lire().strip().split('\n'):
            self.assertRegex(ligne, r'^\d{2}:\d{2}:\d{2} ')

    def test_un_disque_qui_refuse_n_arrete_pas_le_serveur(self):
        """La photothèque ne doit pas mourir parce que son journal ne peut plus
        écrire. Le journal se tait ; la console, elle, reste."""
        # Un chemin qui EST un dossier : `open` refuse sous Windows comme
        # sous Linux, la ou un `chmod` ne veut rien dire sous Windows.
        (self.tmp / 'impossible').mkdir()
        self.journal.fermer()
        self.journal.chemin = self.tmp / 'impossible'
        self.journal._f = None
        self.journal.ecrire("rien ne doit lever")   # ne lève pas
        self.journal.ecrire("deux fois non plus")

    def test_le_journal_est_BORNE_et_garde_une_archive(self):
        """Un journal qui grossit sans fin remplit le disque de la photothèque
        — et devient illisible bien avant."""
        petit = J.Journal(self.tmp / 'borne.log', taille_max=400)
        for i in range(200):
            petit.ecrire("x" * 50)
        petit.fermer()
        self.assertLess((self.tmp / 'borne.log').stat().st_size, 2000)
        self.assertTrue((self.tmp / 'borne.log.1').exists(),
                        "l'archive doit exister : tourner sans garder, c'est "
                        "effacer la preuve qu'on voulait justement lire")


class LeMiroir(Base):

    def test_la_console_garde_TOUT_ce_qu_elle_avait(self):
        console = io.StringIO()
        m = J.Miroir(console, self.journal)
        m.write("bonjour\n")
        self.assertEqual(console.getvalue(), "bonjour\n")

    def test_print_ecrit_UNE_ligne_au_journal_pas_deux(self):
        """`print` fait deux appels — le texte, puis le saut de ligne."""
        m = J.Miroir(io.StringIO(), self.journal)
        m.write("bonjour")
        m.write("\n")
        self.assertEqual(len(self.lire().strip().split('\n')), 1)

    def test_une_ligne_inachevee_attend_sa_fin(self):
        m = J.Miroir(io.StringIO(), self.journal)
        m.write("moitie")
        self.assertEqual(self.lire(), "")
        m.write(" de ligne\n")
        self.assertIn("moitie de ligne", self.lire())

    def test_une_console_cp1252_ne_fait_plus_tomber_ce_qui_l_entoure(self):
        """Le defaut du 22/08 : un « ↻ » sur une console cp1252 levait
        UnicodeEncodeError et emportait 11 tests. La console encaisse
        maintenant ; le JOURNAL, lui, garde le vrai caractere."""
        console = FauxFluxCP1252()
        m = J.Miroir(console, self.journal)
        m.write("recharge ↻ finie\n")          # ne lève pas
        self.assertIn("↻", self.lire())
        self.assertTrue(console.vu, "la console doit avoir recu une version "
                        "degradee, pas rien du tout")

    def test_le_miroir_rend_bien_le_nombre_de_caracteres(self):
        """Un flux qui ment sur ce qu'il a écrit casse ce qui l'utilise."""
        m = J.Miroir(io.StringIO(), self.journal)
        self.assertEqual(m.write("abc"), 3)


class LesCrochets(Base):

    def test_un_thread_qui_meurt_laisse_sa_trace(self):
        """LE cas qui n'apparait nulle part ailleurs : un worker meurt, sa file
        se remplit, et le serveur a l'air parfaitement vivant."""
        J._ETAT['installe'] = False
        sortie_o, sortie_e = sys.stdout, sys.stderr
        crochet_fil = threading.excepthook
        crochet = sys.excepthook
        try:
            J.installer(self.tmp / 'installe.log', source=__file__)
            t = threading.Thread(target=lambda: 1 / 0, name='faux_worker')
            t.start()
            t.join()
            texte = (self.tmp / 'installe.log').read_text(encoding='utf-8')
        finally:
            sys.stdout, sys.stderr = sortie_o, sortie_e
            threading.excepthook = crochet_fil
            sys.excepthook = crochet
            faulthandler.disable()
            for reste in (J._ETAT.get('journal'), J._ETAT.get('crash')):
                try:
                    reste.fermer() if hasattr(reste, 'fermer') else reste.close()
                except (AttributeError, OSError, ValueError):
                    pass
            J._ETAT['installe'] = False
            J._ETAT['journal'] = J._ETAT['crash'] = None
        self.assertIn('THREAD MORT : faux_worker', texte)
        self.assertIn('ZeroDivisionError', texte)
        self.assertEqual(texte.count('ZeroDivisionError: division by zero'), 2,
                         "une fois par la marque, une fois par la trace que "
                         "stderr apporte - trois fois voudrait dire qu'on "
                         "ecrit la trace deux fois")
        self.assertIn('Traceback (most recent call last)', texte,
                      "la trace complete doit arriver par le miroir de stderr")

    def test_la_banniere_ancre_le_demarrage(self):
        """« Qu'est-ce qui a plante DEPUIS que ce serveur tourne ? » doit se
        repondre sans lire six heures de journal."""
        chemin = self.tmp / 'deux.log'
        j = J.Journal(chemin)
        j.ecrire("vieux bruit d'avant")
        j.ecrire(J._banniere(__file__), horodater=False)
        j.ecrire("le defaut qui nous interesse")
        j.fermer()
        recent = J.depuis_le_dernier_demarrage(chemin)
        self.assertIn("le defaut qui nous interesse", recent)
        self.assertNotIn("vieux bruit", recent)

    def test_sans_journal_du_tout_la_lecture_rend_du_vide(self):
        self.assertEqual(J.depuis_le_dernier_demarrage(self.tmp / 'jamais'), '')

    def test_dire_ecrit_au_journal_sans_encombrer_la_console(self):
        J._ETAT['journal'] = self.journal
        try:
            J.dire("detail", "utile", 42)
        finally:
            J._ETAT['journal'] = None
        self.assertIn("detail utile 42", self.lire())

    def test_dire_sans_journal_installe_ne_leve_pas(self):
        J._ETAT['journal'] = None
        J.dire("personne n'ecoute")


class SousLaCharge(Base):

    def test_dix_threads_n_entrelacent_pas_leurs_lignes(self):
        """Le serveur est un `ThreadingHTTPServer` : dix requetes ecrivent en
        meme temps. Un journal entrelace est un journal qu'on ne peut pas
        citer."""
        m = J.Miroir(io.StringIO(), self.journal)

        def bavard(n):
            for i in range(20):
                m.write(f"fil{n}-ligne{i}\n")

        fils = [threading.Thread(target=bavard, args=(n,)) for n in range(10)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        lignes = [l for l in self.lire().split('\n') if l.strip()]
        self.assertEqual(len(lignes), 200)
        for ligne in lignes:
            self.assertRegex(ligne, r'^\d{2}:\d{2}:\d{2} fil\d-ligne\d+$')


if __name__ == '__main__':
    unittest.main(verbosity=2)
