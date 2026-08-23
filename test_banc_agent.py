#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `banc_agent` — surtout de ce que la porte NE laisse PAS passer.

Un agent qui lance des scripts sur la machine de Mike ne se juge pas sur ce
qu'il sait faire : il se juge sur ce qu'il refuse. La moitié de ce fichier
vérifie donc des refus, un par forme d'attaque ou de maladresse — chemin,
famille qui écrit, métacaractère de shell, script absent.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import banc_agent as ba          # noqa: E402
import canal                     # noqa: E402


class TestCanalPartage(unittest.TestCase):
    """`canal` est désormais la seule façon de lire et d'écrire un ordre.
    Trois agents en dépendent : ce qu'il garantit se teste ici une fois."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.f = self.d / 'c.txt'

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_absent_vide_illisible_rendent_le_defaut(self):
        self.assertEqual(canal.lire_ligne(self.f, 'rien'), 'rien')
        self.f.write_text('   \n\n', encoding='utf-8')
        self.assertEqual(canal.lire_ligne(self.f, 'rien'), 'rien')
        self.assertEqual(canal.lire_ligne(self.d, 'rien'), 'rien')  # un dossier

    def test_bom_crlf_lf_et_lignes_en_trop(self):
        for octets in (b'\xef\xbb\xbfmesure_x.py\r\n', b'mesure_x.py\n',
                       b'  mesure_x.py  \r\nbruit\r\n'):
            self.f.write_bytes(octets)
            self.assertEqual(canal.lire_ligne(self.f, 'rien'), 'mesure_x.py')

    def test_la_casse_est_CONSERVEE(self):
        """Un canal peut transporter un chemin : `Copie.db` n'est pas
        `copie.db`. C'est l'appelant qui normalise selon son vocabulaire."""
        self.f.write_bytes(b'mesure_x.py --base Copie.DB\r\n')
        self.assertEqual(canal.lire_ligne(self.f), 'mesure_x.py --base Copie.DB')

    def test_ecriture_en_crlf_et_atomique(self):
        canal.ecrire_ligne(self.f, 'ping')
        self.assertEqual(self.f.read_bytes(), b'ping\r\n')
        self.assertFalse(list(self.d.glob('*.tmp')), "le .tmp doit disparaître")

    def test_un_ordre_accentue_est_refuse_a_l_ecriture(self):
        """`cmd.exe` compte en octets : un accent y désaligne un `set /p`
        aussi sûrement que dans un `.bat`."""
        with self.assertRaises(ValueError):
            canal.ecrire_ligne(self.f, 'mesure_étoile.py')


class TestPorte(unittest.TestCase):
    """Ce que `banc_agent` refuse — et il n'a aucun `force=` pour l'ouvrir."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        for nom in ('mesure_x.py', 'verifier_y.py', 'purger_corbeille.py',
                    'appliquer_plan.py', 'server.py', 'notes.txt'):
            (self.d / nom).write_text('print("ok")\n', encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _refus(self, ordre):
        return ba.motif_refus(ordre, self.d) or ''

    def test_un_banc_de_mesure_passe(self):
        self.assertIsNone(ba.motif_refus('mesure_x.py', self.d))
        self.assertIsNone(ba.motif_refus('verifier_y.py --base copie.db', self.d))

    def test_les_familles_qui_ECRIVENT_ne_passent_pas(self):
        for nom in ('purger_corbeille.py', 'appliquer_plan.py', 'server.py'):
            self.assertIn('famille', self._refus(nom), nom)

    def test_pas_de_chemin_pas_de_remontee(self):
        for ordre in ('../mesure_x.py', 'sous/mesure_x.py',
                      r'C:\mesure_x.py', './mesure_x.py'):
            self.assertIn('chemin', self._refus(ordre), ordre)

    def test_pas_de_metacaractere_de_shell(self):
        """Ils ne sont pas neutralisés, ils sont REFUSÉS — et de toute façon
        aucun shell ne les verrait : `subprocess.run` reçoit une liste."""
        for mauvais in ('mesure_x.py && del *', 'mesure_x.py | more',
                        'mesure_x.py > sortie.txt', 'mesure_x.py $(pwd)',
                        'mesure_x.py "un deux"', "mesure_x.py ;ls"):
            self.assertTrue(self._refus(mauvais), mauvais)

    def test_un_banc_absent_est_refuse(self):
        self.assertIn('introuvable', self._refus('mesure_absent.py'))

    def test_pas_un_python(self):
        self.assertIn('Python', self._refus('notes.txt'))

    def test_ordre_vide(self):
        self.assertIn('vide', self._refus('   '))

    def test_le_decoupage_ne_reinterprete_rien(self):
        self.assertEqual(ba.decouper('  mesure_x.py   --base  copie.db '),
                         ['mesure_x.py', '--base', 'copie.db'])


class TestLancement(unittest.TestCase):
    """Le tour complet : lancer, écrire la sortie, consommer l'ordre."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / 'mesure_bavard.py').write_text(
            "import sys\n"
            "print('des accents : éàü')\n"
            "sys.stderr.write('et une erreur\\n')\n",
            encoding='utf-8')
        (self.d / 'mesure_rate.py').write_text(
            "import sys\nsys.exit(3)\n", encoding='utf-8')
        (self.d / 'mesure_fleuve.py').write_text(
            "print('x' * 500000)\n", encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_la_sortie_est_ecrite_accents_compris(self):
        """Une sortie REDIRIGÉE n'est pas une console : sans
        `PYTHONIOENCODING`, un « é » tue le banc et on croit qu'il a planté."""
        rap = ba.lancer(self.d, 'mesure_bavard.py')
        self.assertTrue(rap['ok'], rap)
        txt = (self.d / ba.FICHIER_SORTIE).read_text(encoding='utf-8')
        self.assertIn('éàü', txt)
        self.assertIn('et une erreur', txt, "stderr doit être FUSIONNÉ")

    def test_un_code_non_nul_n_est_pas_un_succes(self):
        rap = ba.lancer(self.d, 'mesure_rate.py')
        self.assertFalse(rap['ok'])
        self.assertEqual(rap['code'], 3)

    def test_une_sortie_fleuve_est_tronquee_ET_LE_DIT(self):
        rap = ba.lancer(self.d, 'mesure_fleuve.py')
        self.assertTrue(rap['tronquee'])
        self.assertIn('tronquée', (self.d / ba.FICHIER_SORTIE)
                      .read_text(encoding='utf-8'))

    def test_un_refus_ne_lance_rien_et_ne_boucle_pas(self):
        """L'ordre est consommé même sur un refus : sinon l'agent rejoue le
        même refus toutes les trois secondes et noie le rapport utile."""
        ba.ecrire_commande(self.d / ba.FICHIER_COMMANDE, 'server.py')
        rap = ba.un_tour(self.d)
        self.assertIsNotNone(rap['refus'])
        self.assertEqual(ba.lire_commande(self.d / ba.FICHIER_COMMANDE), 'rien')

    def test_ping_est_inerte(self):
        ba.ecrire_commande(self.d / ba.FICHIER_COMMANDE, 'ping')
        rap = ba.un_tour(self.d)
        self.assertTrue(rap['ok'])
        self.assertFalse((self.d / ba.FICHIER_SORTIE).exists(),
                         "un signe de vie n'écrit pas de sortie")

    def test_rien_ne_fait_rien(self):
        ba.ecrire_commande(self.d / ba.FICHIER_COMMANDE, 'rien')
        self.assertIsNone(ba.un_tour(self.d))

    def test_l_interpreteur_se_choisit_par_PLATEFORME(self):
        """`.venv/Scripts/python.exe` existe aussi vu depuis la VM Linux — le
        dossier y est monté — mais il ne s'y exécute pas. Tester `is_file()`
        seul faisait échouer l'agent au lieu de le faire se rabattre."""
        faux = self.d / '.venv' / 'Scripts'
        faux.mkdir(parents=True)
        (faux / 'python.exe').write_bytes(b'MZ pas un ELF')
        py = ba.python_du_projet(self.d)
        if os.name != 'nt':
            self.assertEqual(str(py), sys.executable)

    def test_l_etat_garde_l_historique(self):
        f = self.d / ba.FICHIER_ETAT
        ba.ecrire_etat(f, {'quand': 1, 'ok': True})
        d = ba.ecrire_etat(f, {'quand': 2, 'ok': False})
        self.assertEqual(d['dernier']['quand'], 2)
        self.assertEqual(d['historique'][0]['quand'], 1)


class TestJetonB64(unittest.TestCase):
    """Le jeton `b64:` — porter un ACCENT ou un ESPACE sans ouvrir la porte.

    Pourquoi ces tests existent : le 23/08, `verifier_xmp_personnes.py --nom
    "Stéphane Plouvin"` s'est révélé INLANÇABLE par ce canal. `ARG_OK` ne
    visait pas les noms humains, il les a attrapés au passage — 168 des 352
    noms de la photothèque, 6 119 photos, hors de portée du seul instrument
    qui prouve la règle 2 sur le DISQUE.

    Ce qui est vérifié ici tient en une phrase : le jeton rend une VALEUR,
    il ne rend pas la porte plus large."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        for nom in ('mesure_x.py', 'verifier_y.py'):
            (self.d / nom).write_text('print("ok")\n', encoding='utf-8')
        (self.d / 'mesure_argv.py').write_text(
            "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
            encoding='utf-8')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _refus(self, ordre):
        return ba.motif_refus(ordre, self.d) or ''

    def test_le_jeton_rend_le_nom_EXACT(self):
        self.assertEqual(ba.dejeton('b64:U3TDqXBoYW5lIFBsb3V2aW4'),
                         'Stéphane Plouvin')
        self.assertEqual(ba.dejeton('b64:QsOpYQ'), 'Béa')

    def test_le_bourrage_est_facultatif(self):
        """Un base64 padé porte des « = » ; sans eux il est plus court et
        `ARG_OK` l'admet aussi. Les deux doivent rendre le même nom."""
        self.assertEqual(ba.dejeton('b64:QsOpYQ=='), ba.dejeton('b64:QsOpYQ'))

    def test_un_argument_NU_traverse_intact(self):
        """Le jeton est un cas, pas une couche : ce qui n'en porte pas ne doit
        pas être touché — un `--base` décodé serait un défaut muet."""
        for a in ('--base', 'copie.db', '0.5', 'b64', 'ab64:x'):
            self.assertEqual(ba.dejeton(a), a)

    def test_un_jeton_passe_la_porte(self):
        self.assertIsNone(ba.motif_refus(
            'verifier_y.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4', self.d))

    def test_un_jeton_VIDE_est_un_refus(self):
        self.assertIn('b64', self._refus('mesure_x.py --nom b64:'))

    def test_un_jeton_QUI_N_EST_PAS_DE_L_UTF8_est_un_refus(self):
        """`_w` décode en 0xFF, qui n'est aucun texte. Le laisser passer
        donnerait au banc un argument à moitié né."""
        self.assertIn('b64', self._refus('mesure_x.py --nom b64:_w'))

    def test_un_CARACTERE_DE_CONTROLE_est_un_refus(self):
        """Aucun nom ne porte de tabulation. Un canal qui l'accepte accepte
        qu'on lui glisse une ligne dans un argument."""
        self.assertIn('b64', self._refus('mesure_x.py --nom b64:CQ'))

    def test_le_jeton_NE_ROUVRE_PAS_la_porte(self):
        """Les trois barrières jugent ce qui TRANSITE, et le jeton transite en
        base64url. Une famille qui écrit reste refusée, un chemin reste
        refusé — décoder ne vient qu'après, et jamais sur le nom du banc."""
        (self.d / 'purger_tout.py').write_text('', encoding='utf-8')
        self.assertIn('famille', self._refus('purger_tout.py --nom b64:QsOpYQ'))
        self.assertIn('argument', self._refus('mesure_x.py "un deux"'))

    def test_le_banc_RECOIT_un_seul_argument_et_le_bon(self):
        """La preuve de bout en bout : ce que le script voit dans `sys.argv`.
        Un espace décodé ne doit pas se rescinder en deux arguments."""
        rap = ba.lancer(self.d, 'mesure_argv.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4')
        self.assertTrue(rap['ok'], rap)
        txt = (self.d / ba.FICHIER_SORTIE).read_text(encoding='utf-8')
        self.assertIn('["--nom", "St\\u00e9phane Plouvin"]', txt)

    def test_la_sortie_DIT_ce_qui_a_vraiment_tourne(self):
        """Un rapport qui n'affiche que l'ordre brut laisserait lire
        `b64:U3TDqXBo…` là où il faut lire un nom."""
        ba.lancer(self.d, 'mesure_argv.py --nom b64:QsOpYQ')
        txt = (self.d / ba.FICHIER_SORTIE).read_text(encoding='utf-8')
        self.assertIn('décodé', txt)
        self.assertIn('Béa', txt)

    def test_sans_jeton_la_sortie_ne_change_pas(self):
        ba.lancer(self.d, 'mesure_argv.py --base copie.db')
        txt = (self.d / ba.FICHIER_SORTIE).read_text(encoding='utf-8')
        self.assertNotIn('décodé', txt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
