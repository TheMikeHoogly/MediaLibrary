#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `git_agent` — le canal, les lectures, et surtout LA PORTE.

Ce qui compte ici n'est pas que l'agent sache commiter : c'est qu'il sache
REFUSER, et qu'un `force=` ne puisse pas ouvrir les portes qui protègent le
dépôt lui-même (verrou, branche, fichiers énormes ou binaires). Un garde-fou
contournable par la seule chose qui a le droit de le contourner n'est pas un
garde-fou.

Les contrôles non contournables sont donc testés SUR UN VRAI DÉPÔT git, créé
dans un dossier temporaire — jamais celui du projet. Les contrôles négociables
(serveur à jour, tests, bats, lint) ne le sont pas : ils lancent des processus
et supposent le projet complet ; ils sont couverts par le refus qu'ils
produisent en usage réel, visible dans `_etat_git.json`.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import git_agent as ga


def _git_dispo():
    try:
        subprocess.run(['git', '--version'], capture_output=True, timeout=20)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# ──────────────────────────── le canal ────────────────────────────

class TestCanal(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.f = self.d / ga.FICHIER_COMMANDE

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_absent_vide_ou_inconnu_ne_fait_rien(self):
        """Le doute penche du côté qui NE TOUCHE PAS au dépôt."""
        self.assertEqual(ga.lire_commande(self.f), ga.RIEN)
        self.f.write_bytes(b'')
        self.assertEqual(ga.lire_commande(self.f), ga.RIEN)
        self.f.write_bytes(b'pousse tout sur main !!\r\n')
        self.assertEqual(ga.lire_commande(self.f), ga.RIEN)

    def test_bom_lf_crlf_espaces_majuscules(self):
        for octets in (b'\xef\xbb\xbflivrer\r\n', b'livrer\n', b'  LIVRER \r\n',
                       b'livrer'):
            self.f.write_bytes(octets)
            self.assertEqual(ga.lire_commande(self.f), ga.LIVRER, repr(octets))

    def test_ecriture_crlf_et_atomique(self):
        """L'autre lecteur est `cmd.exe` (`set /p`) : mêmes octets partout,
        quel que soit le monde d'où l'on écrit."""
        ga.ecrire_commande(self.f, 'livrer')
        self.assertEqual(self.f.read_bytes(), b'livrer\r\n')
        self.assertFalse((self.d / (ga.FICHIER_COMMANDE + '.tmp')).exists())

    def test_ping_est_une_commande_inerte(self):
        """Un signe de vie qui ne touche à rien : demander une livraison pour
        savoir si l'agent écoute serait un test qui modifie le dépôt."""
        self.f.write_bytes(b'ping\r\n')
        self.assertEqual(ga.lire_commande(self.f), ga.PING)
        self.assertIn(ga.PING, ga.COMMANDES)

    def test_mot_inconnu_refuse_a_l_ecriture(self):
        with self.assertRaises(ValueError):
            ga.ecrire_commande(self.f, 'push --force')


# ─────────────────────── lectures pures ───────────────────────

class TestLectures(unittest.TestCase):
    def test_session_commit(self):
        sc = ga.lire_session_commit(
            "# commentaire\nbranche=feat/x-y\ntitre=Un titre\nforce=doc seule\n")
        self.assertEqual(sc, {'branche': 'feat/x-y', 'titre': 'Un titre',
                              'force': 'doc seule'})

    def test_session_commit_vide(self):
        self.assertEqual(ga.lire_session_commit(''),
                         {'branche': '', 'titre': '', 'force': ''})

    def test_branches_refusees(self):
        for mauvais in ('', 'main', 'Feat/Majuscules', 'sans-prefixe',
                        'feat/', 'wip/truc'):
            self.assertIsNotNone(ga.motif_branche(mauvais), repr(mauvais))
        for bon in ('feat/faits-affiches', 'fix/a1', 'chore/amorce-28',
                    'docs/roadmap', 'test/banc'):
            self.assertIsNone(ga.motif_branche(bon), repr(bon))

    def test_porcelain_renommage_et_guillemets(self):
        c = ga.porcelain(' M server.py\n?? git_agent.py\n'
                         'R  vieux.py -> neuf.py\n M "0 - D\\303\\251marrer.bat"\n')
        self.assertIn('server.py', c)
        self.assertIn('git_agent.py', c)
        self.assertIn('vieux.py', c)
        self.assertIn('neuf.py', c)
        self.assertTrue(any('marrer.bat' in x for x in c), c)

    def test_fichiers_dangereux(self):
        gros = lambda c: 99 * 1024 * 1024
        petit = lambda c: 10
        self.assertIsNotNone(ga.motif_fichiers(['photos.db'], petit))
        self.assertIsNotNone(ga.motif_fichiers(['yolo11s.pt'], petit))
        self.assertIsNotNone(ga.motif_fichiers(['docs/capture.pdf'], gros))
        self.assertIsNone(ga.motif_fichiers(['server.py', 'ROADMAP.md'], petit))

    def test_supprime_n_a_pas_de_poids(self):
        """Un fichier effacé n'existe plus : sa taille est 0, pas un refus."""
        def absent(c):
            raise OSError('supprimé')
        self.assertIsNone(ga.motif_fichiers(['ROADMAP.md'], absent))

    def test_py_a_observer_ignore_tests_et_bancs(self):
        c = ['server.py', 'faits_vue.py', 'test_faits_vue.py',
             'mesure_faits_vue.py', 'ROADMAP.md']
        self.assertEqual(ga.py_a_observer(c), ['server.py', 'faits_vue.py'])

    def test_tests_pour(self):
        presents = {'test_faits_vue.py', 'test_server.py'}
        self.assertEqual(
            ga.tests_pour(['faits_vue.py', 'test_faits_vue.py', 'ROADMAP.md',
                           'sans_test.py'], lambda n: n in presents),
            ['test_faits_vue.py'])


# ─────────── la porte : ce qu'un `force=` ne doit PAS ouvrir ───────────

@unittest.skipUnless(_git_dispo(), "git indisponible")
class TestPorteNonContournable(unittest.TestCase):
    """`force=` lève les contrôles négociables. Il ne lève RIEN de ce qui
    protège le dépôt : un verrou, la branche `main`, un binaire de 290 Mo."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        for a in (('init', '-q'), ('config', 'user.email', 'x@y.z'),
                  ('config', 'user.name', 'banc')):
            subprocess.run(('git',) + a, cwd=str(self.d), capture_output=True)
        (self.d / 'ROADMAP.md').write_text('x', encoding='utf-8')
        self.sc = {'branche': 'feat/essai', 'titre': 'T', 'force': 'raison'}

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_force_ouvre_la_porte_quand_tout_va_bien(self):
        refus, notes = ga.controler(self.d, self.sc, ['ROADMAP.md'])
        self.assertIsNone(refus, refus)
        self.assertTrue(any('FORCE' in n for n in notes), notes)

    def test_force_n_ouvre_pas_sur_un_verrou(self):
        (self.d / '.git' / 'index.lock').write_text('', encoding='utf-8')
        refus, _ = ga.controler(self.d, self.sc, ['ROADMAP.md'])
        self.assertIn('verrou', (refus or '').lower())

    def test_force_n_ouvre_pas_main(self):
        sc = dict(self.sc, branche='main')
        refus, _ = ga.controler(self.d, sc, ['ROADMAP.md'])
        self.assertIsNotNone(refus)

    def test_force_n_ouvre_pas_un_binaire(self):
        (self.d / 'photos.db').write_bytes(b'0' * 32)
        refus, _ = ga.controler(self.d, self.sc, ['ROADMAP.md', 'photos.db'])
        self.assertIn('photos.db', refus or '')

    def test_force_n_ouvre_pas_un_arbre_propre(self):
        refus, _ = ga.controler(self.d, self.sc, [])
        self.assertIn('rien à commiter', refus or '')

    def test_pas_de_checkout_vers_une_branche_existante(self):
        """Y basculer réécrirait server.py sous le serveur qui tourne."""
        subprocess.run(('git', 'add', '-A'), cwd=str(self.d), capture_output=True)
        subprocess.run(('git', 'commit', '-qm', 'base'), cwd=str(self.d),
                       capture_output=True)
        subprocess.run(('git', 'branch', 'feat/essai'), cwd=str(self.d),
                       capture_output=True)
        (self.d / 'ROADMAP.md').write_text('y', encoding='utf-8')
        refus, _ = ga.controler(self.d, self.sc, ['ROADMAP.md'])
        self.assertIn('existe', (refus or '').lower())


@unittest.skipUnless(_git_dispo(), "git indisponible")
class TestCommit(unittest.TestCase):
    """La livraison locale, de bout en bout — sans distant, donc sans push."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        for a in (('init', '-q'), ('config', 'user.email', 'x@y.z'),
                  ('config', 'user.name', 'banc')):
            subprocess.run(('git',) + a, cwd=str(self.d), capture_output=True)
        (self.d / 'ROADMAP.md').write_text('x', encoding='utf-8')
        (self.d / ga.SESSION_COMMIT).write_text(
            "branche=feat/essai\ntitre=Un titre de banc\nforce=banc\n",
            encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_commit_cree_la_branche_et_consomme_la_proposition(self):
        rap = ga.livrer(self.d, ga.COMMIT)
        self.assertTrue(rap['ok'], rap)
        self.assertTrue(rap['commit'])
        self.assertFalse((self.d / ga.SESSION_COMMIT).exists(),
                         "la proposition doit être consommée")
        r = subprocess.run(('git', 'rev-parse', '--abbrev-ref', 'HEAD'),
                           cwd=str(self.d), capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), 'feat/essai')

    def test_sans_titre_rien_n_est_commite(self):
        (self.d / ga.SESSION_COMMIT).write_text("branche=feat/essai\n",
                                                encoding='utf-8')
        rap = ga.livrer(self.d, ga.COMMIT)
        self.assertFalse(rap['ok'])
        self.assertIn('titre', rap['refus'])

    def test_etat_garde_l_historique(self):
        f = self.d / ga.FICHIER_ETAT
        ga.ecrire_etat(f, {'quand': 1, 'ok': True})
        d = ga.ecrire_etat(f, {'quand': 2, 'ok': False, 'refus': 'x'})
        self.assertEqual(d['dernier']['quand'], 2)
        self.assertEqual(d['historique'][0]['quand'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
