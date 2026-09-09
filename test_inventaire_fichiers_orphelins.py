#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bancs de `inventaire_fichiers_orphelins.py`.

Le banc central est `test_un_binaire_est_un_candidat` : c'est la panne du
09/09. L'instrument ne PARCOURAIT que le texte, donc 609 binaires de
`_to_delete/` n'entraient jamais dans l'inventaire, donc le veto
d'`appliquer_menage.py` les retenait tous faute de verdict -- et j'ai lu ces
810 retenus comme de la prudence. Un banc qui verifie seulement que les
verdicts sont justes ne trouve pas ca : il faut verifier que le champ de vision
est complet.
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventaire_fichiers_orphelins as inv  # noqa: E402


def _ecrire(racine, chemin, contenu=b''):
    p = Path(racine) / chemin
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(contenu, str):
        p.write_text(contenu, encoding='utf-8')
    else:
        p.write_bytes(contenu)
    return p


class DepotFactice(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.r = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def familles(self, bilan=None):
        return {l['fichier'].replace(os.sep, '/'): l['famille']
                for l in inv.inventorier(self.r, bilan)}


class TestChampDeVision(DepotFactice):
    def test_un_binaire_est_un_candidat(self):
        """LA panne du 09/09 : un .pyc que personne ne cite doit etre JUGE."""
        _ecrire(self.r, '_to_delete/vieux.pyc', b'\x00\x01\x02\x03')
        _ecrire(self.r, '_to_delete/photo.jpg', b'\xff\xd8\xff\xe0rien')
        f = self.familles()
        self.assertIn('_to_delete/vieux.pyc', f)
        self.assertIn('_to_delete/photo.jpg', f)
        self.assertEqual(f['_to_delete/vieux.pyc'], 'ORPHELIN')

    def test_un_binaire_cite_par_du_code_est_protege(self):
        """Candidat, oui -- mais juge sur ses LECTEURS comme les autres."""
        _ecrire(self.r, 'modele_perso.dat', b'\x00' * 40)
        _ecrire(self.r, 'charge.py', "ouvrir('modele_perso.dat')\n")
        self.assertEqual(self.familles()['modele_perso.dat'], 'LU PAR DU CODE')

    def test_un_binaire_ne_sert_jamais_de_lecteur(self):
        """Un .jpg qui contient par hasard le nom d'un autre ne le sauve pas.

        C'est l'autre moitie de la separation : elargir le PARCOURS ne doit pas
        elargir la LECTURE, sinon n'importe quel octet de bruit devient une
        citation et l'instrument ne declare plus jamais rien orphelin."""
        _ecrire(self.r, 'bruit.jpg', b'\xff\xd8 secret_du_projet.json \xff\xd9')
        _ecrire(self.r, 'secret_du_projet.json', '{}')
        self.assertEqual(self.familles()['secret_du_projet.json'], 'ORPHELIN')

    def test_un_pycache_est_parcouru_mais_ne_lit_rien(self):
        """La SECONDE porte de l'angle mort du 09/09.

        `__pycache__` etait dans IGNORES : ouvrir le parcours aux binaires
        n'avait donc rendu que 217 des 800 fichiers de `_to_delete/`, les 583
        autres etant des .pyc ranges la-dedans. Un elagage de DOSSIER survit a
        une correction qui ne touche qu'au filtre d'EXTENSION."""
        _ecrire(self.r, '_to_delete/vieux/__pycache__/mod.cpython-311.pyc',
                b'\x00\x0d\x0d\n')
        f = self.familles()
        self.assertIn('_to_delete/vieux/__pycache__/mod.cpython-311.pyc', f)
        self.assertEqual(f['_to_delete/vieux/__pycache__/mod.cpython-311.pyc'],
                         'ORPHELIN')

    def test_rien_dans_un_pycache_ne_sert_de_lecteur(self):
        """Parcouru, oui ; lecteur, jamais. Un artefact de construction ne
        temoigne pas de ce que le projet lit -- il recopie du code d'hier."""
        _ecrire(self.r, '__pycache__/vieux.txt', 'donnees_vivantes.json')
        _ecrire(self.r, 'donnees_vivantes.json', '{}')
        self.assertEqual(self.familles()['donnees_vivantes.json'], 'ORPHELIN')

    def test_une_corbeille_archivee_nest_pas_la_corbeille_vivante(self):
        """LA TROISIEME porte, et la plus large : 579 des 800 fichiers de
        `_to_delete/`. `_corbeille_session` designait le meuble de la racine ;
        compare au nom NU, il faisait aussi taire la corbeille MORTE archivee
        dans la quarantaine. Une protection qui vise un dossier PARTICULIER
        doit nommer sa PLACE."""
        _ecrire(self.r, '_corbeille_session/vif.json', '{}')
        _ecrire(self.r, '_to_delete/vieux/_corbeille_session/mort.json', '{}')
        f = self.familles()
        self.assertNotIn('_corbeille_session/vif.json', f)
        self.assertIn('_to_delete/vieux/_corbeille_session/mort.json', f)

    def test_un_homonyme_de_meuble_est_juge(self):
        """`photos.db` a la racine est la base ; une COPIE archivee est un
        fichier comme un autre, et 283 Mo caches ne se decident pas tout
        seuls."""
        _ecrire(self.r, 'photos.db', b'SQLite format 3\x00')
        _ecrire(self.r, '_to_delete/avant/photos.db', b'SQLite format 3\x00')
        f = self.familles()
        self.assertNotIn('photos.db', f)
        self.assertIn('_to_delete/avant/photos.db', f)

    def test_le_bilan_nomme_les_dossiers_elagues(self):
        """Un elagage qui ne s'imprime pas redevient invisible au passage
        suivant."""
        _ecrire(self.r, '.venv/lib/x.py', 'x')
        _ecrire(self.r, 'uploads/photo.jpg', b'\xff')
        bilan = {}
        inv.inventorier(self.r, bilan)
        noms = {e.replace(os.sep, '/') for e, _ in bilan['elagues']}
        self.assertIn('.venv', noms)
        self.assertIn('uploads', noms)

    def test_un_dossier_ignore_reste_hors_du_parcours(self):
        """IGNORES garde son sens : un fonds etranger n'est pas un candidat."""
        _ecrire(self.r, '.venv/lib/truc.py', 'x')
        _ecrire(self.r, 'node_modules/paquet/index.js', 'x')
        f = self.familles()
        self.assertFalse([k for k in f if k.startswith(('.venv/',
                                                        'node_modules/'))])

    def test_le_bilan_compte_ce_qui_a_ete_parcouru(self):
        for n in ('a.py', 'b.pyc', 'c.jpg', 'd.md'):
            _ecrire(self.r, n, b'x')
        bilan = {}
        inv.inventorier(self.r, bilan)
        self.assertEqual(bilan['parcourus'], 4)
        self.assertEqual(bilan['elagues'], [])
        # .pyc et .jpg ne sont pas des lecteurs ; .py et .md le sont.
        self.assertEqual(bilan['lecteurs_potentiels'], 2)

    def test_un_lecteur_trop_gros_est_compte_pas_oublie(self):
        """Un lecteur ecarte pour sa taille doit LAISSER UNE TRACE."""
        _ecrire(self.r, 'enorme.txt', 'x' * (inv.PLAFOND_LECTURE + 10))
        bilan = {}
        inv.inventorier(self.r, bilan)
        self.assertIn('enorme.txt', bilan['ecartes_taille'])
        self.assertEqual(bilan['lecteurs_lus'], bilan['lecteurs_potentiels'] - 1)


class TestConventionsNouvelles(DepotFactice):
    def test_annexe_sqlite_jamais_orpheline(self):
        """Separer un -wal de sa base pendant une ecriture corrompt la base."""
        _ecrire(self.r, 'photos.db-wal', b'\x00' * 8)
        _ecrire(self.r, 'photos.db-shm', b'\x00' * 8)
        f = self.familles()
        self.assertEqual(f['photos.db-wal'], 'LU PAR CONVENTION')
        self.assertEqual(f['photos.db-shm'], 'LU PAR CONVENTION')

    def test_poids_de_modele_jamais_orphelin(self):
        _ecrire(self.r, 'yolo11s.pt', b'\x80\x02')
        self.assertEqual(self.familles()['yolo11s.pt'], 'LU PAR CONVENTION')

    def test_une_base_reste_protegee_par_son_nom(self):
        _ecrire(self.r, 'photos.db', b'SQLite format 3\x00')
        self.assertNotIn('photos.db', self.familles())


class TestBavardageBat(DepotFactice):
    def test_citation_en_REM_seul_est_signalee_mais_pas_degradee(self):
        """L'instrument SIGNALE, il ne tranche pas.

        Un `REM lit x.json` precede presque toujours la vraie lecture ; changer
        la famille sur ce seul indice effacerait des entrees vivantes."""
        _ecrire(self.r, 'donnees_utiles.json', '{}')
        _ecrire(self.r, 'un.bat', 'REM on lisait donnees_utiles.json avant\r\n'
                                  'echo fini\r\n')
        lignes = {l['fichier']: l for l in inv.inventorier(self.r)}
        e = lignes['donnees_utiles.json']
        self.assertEqual(e['famille'], 'LU PAR DU CODE')
        self.assertTrue(e['citation_bavarde'])

    def test_citation_vive_dans_un_bat_nest_pas_signalee(self):
        _ecrire(self.r, 'donnees_utiles.json', '{}')
        _ecrire(self.r, 'un.bat', 'REM on lit donnees_utiles.json\r\n'
                                  'python t.py --in donnees_utiles.json\r\n')
        lignes = {l['fichier']: l for l in inv.inventorier(self.r)}
        self.assertFalse(lignes['donnees_utiles.json']['citation_bavarde'])

    def test_deux_points_deux_points_compte_comme_commentaire(self):
        _ecrire(self.r, 'donnees_utiles.json', '{}')
        _ecrire(self.r, 'un.bat', ':: donnees_utiles.json est mort\r\necho ok\r\n')
        lignes = {l['fichier']: l for l in inv.inventorier(self.r)}
        self.assertTrue(lignes['donnees_utiles.json']['citation_bavarde'])

    def test_un_echo_qui_nomme_un_fichier_nest_pas_une_lecture(self):
        """Bat 33, ligne 105 : la commande d'exemple est AFFICHEE, pas lancee.
        `_rapport_google_apres.json` etait protege par du texte a l'ecran."""
        _ecrire(self.r, 'donnees_utiles.json', '{}')
        _ecrire(self.r, 'un.bat',
                'echo   python outil.py --json donnees_utiles.json\r\n')
        lignes = {l['fichier']: l for l in inv.inventorier(self.r)}
        self.assertTrue(lignes['donnees_utiles.json']['citation_bavarde'])

    def test_un_echo_REDIRIGE_est_une_vraie_ecriture(self):
        """`echo livrer > _commande_git.txt` est le canal de commande de tout
        ce projet : le depouiller casserait la detection du canal lui-meme."""
        _ecrire(self.r, 'donnees_utiles.json', '{}')
        _ecrire(self.r, 'un.bat', 'echo {} > donnees_utiles.json\r\n')
        lignes = {l['fichier']: l for l in inv.inventorier(self.r)}
        self.assertFalse(lignes['donnees_utiles.json']['citation_bavarde'])

    def test_un_py_nest_pas_deshabille_de_ses_commentaires(self):
        """`sans_commentaires` ne touche QUE les .bat : un `#` en Python peut
        etre a l'interieur d'une chaine, et REM n'existe pas la-bas."""
        t = "x = '# pas un commentaire'\n"
        self.assertEqual(inv.sans_bavardage(t, '.py'), t)


class TestAutoProtection(DepotFactice):
    def test_le_nettoyeur_ne_protege_pas_ses_propres_cibles(self):
        """La pathologie de l'auto-lecture, un cran plus haut.

        `appliquer_menage.py` porte la liste des motifs A JETER. Comptee comme
        lecture, elle protege exactement ce qu'elle designe : mesure du 09/09,
        `_rapport_perdus_takeout.json` retenu par le veto parce que le
        nettoyeur le nommait comme cible. Nommer une chose pour l'effacer
        n'est pas la lire."""
        _ecrire(self.r, '_rapport_perdus_takeout.json', '{}')
        _ecrire(self.r, 'appliquer_menage.py',
                "POLITIQUE = ['_rapport_perdus_takeout.json']\n")
        _ecrire(self.r, 'test_appliquer_menage.py',
                "CIBLE = '_rapport_perdus_takeout.json'\n")
        self.assertEqual(self.familles()['_rapport_perdus_takeout.json'],
                         'ORPHELIN')


    def test_l_instrument_ne_se_lit_pas_lui_meme_ni_son_banc(self):
        """Le quatrieme cas, fabrique en documentant les trois premiers.

        Ce fichier-ci nomme en clair chaque fichier sur lequel l'instrument
        s'est trompe. Au passage suivant, ces fichiers redevenaient
        `LU PAR DU CODE` -- lus par l'instrument qui venait d'expliquer que
        personne ne les lisait. **Ecrire l'histoire d'une erreur la
        refaisait.** Un outil qui juge ne temoigne pas."""
        _ecrire(self.r, '_rapport_ancien.json', '{}')
        _ecrire(self.r, 'inventaire_fichiers_orphelins.py',
                "# jadis _rapport_ancien.json etait mal protege\n")
        _ecrire(self.r, 'test_inventaire_fichiers_orphelins.py',
                "CAS = '_rapport_ancien.json'\n")
        self.assertEqual(self.familles()['_rapport_ancien.json'], 'ORPHELIN')

    def test_la_corbeille_du_menage_nest_pas_reparcourue(self):
        """Son `_manifeste.json` cite les 506 fichiers deplaces : le
        proces-verbal du menage temoignait de ses propres victimes."""
        _ecrire(self.r, '_corbeille_menage/20260909/_manifeste.json',
                '{"deplaces": ["vivant.json"]}')
        _ecrire(self.r, 'vivant.json', '{}')
        f = self.familles()
        self.assertFalse([k for k in f if k.startswith('_corbeille_menage/')])
        self.assertEqual(f['vivant.json'], 'ORPHELIN')


class TestContratDeSortie(DepotFactice):
    def test_inventorier_rend_toujours_une_liste(self):
        """`appliquer_menage.py` appelle `inventorier(RACINE)` et itere dessus.
        Le bilan est un ARGUMENT, jamais un second retour."""
        _ecrire(self.r, 'a.py', 'rien\n')
        r = inv.inventorier(self.r)
        self.assertIsInstance(r, list)
        self.assertTrue(all('famille' in x and 'fichier' in x for x in r))

    def test_chaque_ligne_dit_si_elle_a_ete_lue(self):
        _ecrire(self.r, 'a.py', 'rien\n')
        _ecrire(self.r, 'b.pyc', b'\x00')
        d = {l['fichier']: l['texte'] for l in inv.inventorier(self.r)}
        self.assertTrue(d['a.py'])
        self.assertFalse(d['b.pyc'])

    def test_json_est_serialisable(self):
        _ecrire(self.r, 'a.pyc', b'\x00\xff')
        json.dumps(inv.inventorier(self.r))


if __name__ == '__main__':
    unittest.main(verbosity=2)
