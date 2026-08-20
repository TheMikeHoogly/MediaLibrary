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
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import git_agent as ga

# Le nom du bat porte un accent : il est ecrit ici en \u ASCII pour que ce
# fichier reste lisible partout, comme les .bat eux-memes.
BAT0 = '0 - D\u00e9marrer le serveur.bat'


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
    """La livraison de bout en bout, contre un distant BARE local.

    Le distant n'est pas un décor : depuis le 20/08, `commit` POUSSE. Le banc
    tournait sans distant et validait donc un mode qui, en prod, laissait le
    travail d'une traite autonome sur un seul disque."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.distant = Path(tempfile.mkdtemp()) / 'origin.git'
        subprocess.run(('git', 'init', '--bare', '-q', str(self.distant)),
                       capture_output=True)
        for a in (('init', '-q'), ('config', 'user.email', 'x@y.z'),
                  ('config', 'user.name', 'banc'),
                  ('remote', 'add', 'origin', str(self.distant))):
            subprocess.run(('git',) + a, cwd=str(self.d), capture_output=True)
        (self.d / 'ROADMAP.md').write_text('x', encoding='utf-8')
        (self.d / ga.SESSION_COMMIT).write_text(
            "branche=feat/essai\ntitre=Un titre de banc\nforce=banc\n",
            encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)
        shutil.rmtree(self.distant.parent, ignore_errors=True)

    def _refs_distantes(self):
        r = subprocess.run(('git', 'for-each-ref', '--format=%(refname)'),
                           cwd=str(self.distant), capture_output=True, text=True)
        return set(r.stdout.split())

    def test_commit_cree_la_branche_et_consomme_la_proposition(self):
        rap = ga.livrer(self.d, ga.COMMIT)
        self.assertTrue(rap['ok'], rap)
        self.assertTrue(rap['commit'])
        self.assertFalse((self.d / ga.SESSION_COMMIT).exists(),
                         "la proposition doit être consommée")
        r = subprocess.run(('git', 'rev-parse', '--abbrev-ref', 'HEAD'),
                           cwd=str(self.d), capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), 'feat/essai')

    def test_commit_POUSSE_la_branche(self):
        """La promesse de `CLAUDE.md`, tenue : une traite autonome laisse une
        copie ailleurs que sur le disque de Mike."""
        rap = ga.livrer(self.d, ga.COMMIT)
        self.assertTrue(rap['ok'], rap)
        self.assertIn('refs/heads/feat/essai', self._refs_distantes())

    def test_commit_ne_touche_PAS_a_main(self):
        """Ce que `commit` protège, c'est `main` — pas l'absence de copie."""
        rap = ga.livrer(self.d, ga.COMMIT)
        self.assertTrue(rap['ok'], rap)
        self.assertNotIn('refs/heads/main', self._refs_distantes())

    def test_sans_distant_le_commit_est_fait_et_le_refus_le_DIT(self):
        """Un push impossible ne doit pas se lire « rien n'a marché » : le
        commit est en local, et le rapport doit le dire pour qu'on le pousse
        à la main plutôt que de refaire le travail."""
        subprocess.run(('git', 'remote', 'remove', 'origin'), cwd=str(self.d),
                       capture_output=True)
        rap = ga.livrer(self.d, ga.COMMIT)
        self.assertFalse(rap['ok'])
        self.assertIn('push', (rap['refus'] or '').lower())
        self.assertIn('local', (rap['refus'] or '').lower())
        self.assertTrue(rap['commit'], "le commit local doit être rapporté")

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


# ─────────── les superviseurs se retirent d'eux-mêmes ───────────

class TestGeneration(unittest.TestCase):
    """Deux fenêtres « MediaLibrary - Serveur » ont survécu le 20/08 : le
    `taskkill` par TITRE ne retrouve pas fiablement les fenêtres console, donc
    l'ancien superviseur a relancé un serveur après qu'on a tué le sien.

    Le remplaçant est un jeton de GÉNÉRATION dans un fichier — un titre se
    devine, un fichier se lit. C'est du batch, donc non exécutable ici : on
    vérifie au moins que les trois pièces existent et se répondent, pour qu'un
    nettoyage distrait ne les dissocie pas en silence."""

    def _lire(self, nom):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), nom)
        with io.open(p, encoding='ascii') as f:
            return f.read()

    def test_le_bat0_ecrit_un_jeton_neuf(self):
        src = self._lire(BAT0)
        self.assertIn('_generation.txt', src)
        self.assertIn('%RANDOM%', src)

    def test_les_deux_superviseurs_relisent_et_se_retirent(self):
        for nom in ('superviseur.bat', 'superviseur_git.bat'):
            src = self._lire(nom)
            self.assertIn('GENFILE=_generation.txt', src, nom)
            self.assertIn('GENNOW', src, nom)
            self.assertIn('exit /b 0', src, nom)

    def test_le_taskkill_par_titre_n_est_plus_le_seul_moyen(self):
        """Il reste en best effort — jamais comme unique mécanisme."""
        src = self._lire(BAT0)
        i_gen = src.index('_generation.txt')
        i_kill = src.index('taskkill /F /T /FI')
        self.assertLess(i_gen, i_kill,
                        "la generation doit etre ecrite AVANT tout kill")


if __name__ == '__main__':
    unittest.main(verbosity=2)
