#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_visages_orphelins.py`.

Ce banc décide si une purge peut avoir lieu : ses cas fixent donc ce qui
compte comme jumeau (nom de fichier, visage), ce qui n'en a AUCUN — la seule
liste qui interdit le geste — et le fait qu'un jumeau portant déjà le nom ne
demande rien.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import mesure_visages_orphelins as O
from test_mesure_propagation_noms import Base, b64, vecteur


class Fonds:
    """Un petit fonds : des clés vivantes (dans l'index) et des orphelines."""

    def __init__(self, d):
        self.base = Base(d)
        self.d = d

    def vivante(self, cle, visages, noms=()):
        self.base.photo(cle, visages, noms=noms)

    def orpheline(self, cle, visages):
        """Une fiche de visages SANS entrée d'index — le cas des 2 374."""
        self.base.faces.set(cle, {"faces": visages})

    def fiche(self, nom, **extra):
        self.base.personne(nom, [vecteur(500)], **extra)

    def mesurer(self):
        self.base.fermer()
        return O.mesurer(str(self.base.db), self.d)


class TestComptes(unittest.TestCase):

    def test_une_decision_sur_une_cle_vivante_n_est_pas_en_danger(self):
        with TemporaryDirectory() as d:
            f = Fonds(d)
            f.vivante('viv.jpg', [{"emb": b64(vecteur(1))}])
            f.fiche('Alice', faces=[['viv.jpg', 0]])
            r = f.mesurer()
            self.assertEqual(r['decisions']['sur_cle_orpheline'], 0)
            self.assertNotIn('sauvetage', r)

    def test_les_trois_types_de_decision_sont_comptes(self):
        with TemporaryDirectory() as d:
            f = Fonds(d)
            f.orpheline('orph.jpg', [{"emb": b64(vecteur(1))}])
            f.fiche('Alice', faces=[['orph.jpg', 0]],
                    exclude=['orph.jpg'], confirmed=['orph.jpg'])
            r = f.mesurer()
            self.assertEqual(r['decisions']['en_danger_par_type'],
                             {'rattachement': 1, 'exclusion': 1,
                              'confirmation': 1})

    def test_une_cle_inconnue_partout_est_signalee_a_part(self):
        with TemporaryDirectory() as d:
            f = Fonds(d)
            f.vivante('viv.jpg', [{"emb": b64(vecteur(1))}])
            f.fiche('Alice', faces=[['nulle-part.jpg', 0]])
            r = f.mesurer()
            self.assertEqual(r['decisions']['sur_cle_inconnue_partout'], 1)
            self.assertEqual(r['decisions']['sur_cle_orpheline'], 0)


class TestJumeaux(unittest.TestCase):

    def test_jumeau_par_nom_de_fichier(self):
        """`ARZOPA/x.jpg` et `.../_Uploads/ARZOPA/x.jpg` : la forme dominante."""
        with TemporaryDirectory() as d:
            f = Fonds(d)
            v = b64(vecteur(1))
            f.vivante('/nas/_Uploads/ARZOPA/x.jpg', [{"emb": v}])
            f.orpheline('ARZOPA/x.jpg', [{"emb": v}])
            f.fiche('Alice', faces=[['ARZOPA/x.jpg', 0]])
            r = f.mesurer()
            s = r['sauvetage']
            self.assertEqual(s['jumeau_trouve'], 1)
            self.assertEqual(s['AUCUN_JUMEAU'], 0)
            self.assertEqual(r['exemples_a_reporter'][0]['jumeau_retenu'],
                             '/nas/_Uploads/ARZOPA/x.jpg')

    def test_jumeau_par_visage_quand_la_photo_a_ete_renommee(self):
        """7 058 renommages ont eu lieu : le nom de fichier ne suffit pas."""
        with TemporaryDirectory() as d:
            f = Fonds(d)
            v = b64(vecteur(1))
            f.vivante('2019/20190712_lac.jpg', [{"emb": v}])
            f.orpheline('ARZOPA/brut.jpg', [{"emb": v}])
            f.fiche('Alice', faces=[['ARZOPA/brut.jpg', 0]])
            r = f.mesurer()
            self.assertEqual(r['sauvetage']['jumeau_par_visage_SEUL'], 1)
            self.assertEqual(r['sauvetage']['AUCUN_JUMEAU'], 0)

    def test_une_autre_photo_de_la_meme_personne_n_est_pas_un_jumeau(self):
        """Le seuil vaut « le meme fichier », pas « la meme personne »."""
        with TemporaryDirectory() as d:
            f = Fonds(d)
            socle = vecteur(1)
            f.vivante('autre.jpg', [{"emb": b64(vecteur(2, 0.30, socle))}])
            f.orpheline('ARZOPA/brut.jpg', [{"emb": b64(socle)}])
            f.fiche('Alice', faces=[['ARZOPA/brut.jpg', 0]])
            r = f.mesurer()
            self.assertEqual(r['sauvetage']['AUCUN_JUMEAU'], 1)
            self.assertEqual(r['sans_jumeau'][0]['nom'], 'Alice')
            self.assertLess(r['sans_jumeau'][0]['meilleure_sim'],
                            O.SIM_MEME_PHOTO)

    def test_un_jumeau_qui_porte_deja_le_nom_ne_demande_rien(self):
        with TemporaryDirectory() as d:
            f = Fonds(d)
            v = b64(vecteur(1))
            f.vivante('/nas/x.jpg', [{"emb": v}], noms=['Alice'])
            f.orpheline('x.jpg', [{"emb": v}])
            f.fiche('Alice', faces=[['x.jpg', 0]])
            r = f.mesurer()
            self.assertEqual(r['sauvetage']['jumeau_porte_deja_le_nom'], 1)
            self.assertEqual(r['sauvetage']['a_reporter'], 0)

    def test_la_liste_sans_jumeau_est_complete_et_nommee(self):
        """C'est elle qu'on relit avant le geste : jamais un echantillon."""
        with TemporaryDirectory() as d:
            f = Fonds(d)
            for n in range(12):
                f.orpheline(f'perdue{n}.jpg', [{"emb": b64(vecteur(600 + n))}])
            f.fiche('Alice', faces=[[f'perdue{n}.jpg', 0] for n in range(12)])
            r = f.mesurer()
            self.assertEqual(r['sauvetage']['AUCUN_JUMEAU'], 12)
            self.assertEqual(len(r['sans_jumeau']), 12)


class TestRapport(unittest.TestCase):

    def test_le_rapport_s_affiche_sans_exception(self):
        with TemporaryDirectory() as d:
            f = Fonds(d)
            v = b64(vecteur(1))
            f.vivante('/nas/x.jpg', [{"emb": v}])
            f.orpheline('x.jpg', [{"emb": v}])
            f.orpheline('perdue.jpg', [{"emb": b64(vecteur(700))}])
            f.fiche('Alice', faces=[['x.jpg', 0], ['perdue.jpg', 0]])
            texte = O.afficher(f.mesurer())
            self.assertIn('AUCUN JUMEAU', texte)
            self.assertIn('LIMITES DECLAREES', texte)

    def test_sans_decision_en_danger_le_rapport_le_dit(self):
        with TemporaryDirectory() as d:
            f = Fonds(d)
            f.vivante('viv.jpg', [{"emb": b64(vecteur(1))}])
            f.fiche('Alice')
            texte = O.afficher(f.mesurer())
            self.assertIn('aucune decision humaine', texte)




class TestChemins(unittest.TestCase):

    def test_un_composant_cache_est_reconnu(self):
        for cle in ('/nas/.corbeille-rangement/39562880/x.JPG',
                    r'\\nas\home\@eaDir\x.jpg', '#recycle/x.jpg',
                    '.thumbs/x.jpg'):
            self.assertTrue(O.chemin_cache(cle), cle)

    def test_un_chemin_normal_ne_l_est_pas(self):
        for cle in ('2019/ete/x.jpg', r'\\nas\home\Photos\2019\x.jpg',
                    'ARZOPA/x.jpg'):
            self.assertFalse(O.chemin_cache(cle), cle)

    def test_une_cle_relative_est_toujours_sous_une_racine(self):
        self.assertTrue(O.sous_une_racine('ARZOPA/x.jpg', []))

    def test_une_cle_absolue_hors_racine_est_muette_a_vie(self):
        racines = [r'\\NAS-Bremblens\home\Photos']
        self.assertTrue(O.sous_une_racine(
            r'\\NAS-Bremblens\home\Photos\2019\x.jpg', racines))
        self.assertFalse(O.sous_une_racine(
            r'\\NAS-Bremblens\home\Autre\x.jpg', racines))


class TestCauses(unittest.TestCase):
    """Trois familles, trois bugs differents — c'est la CAUSE, pas le symptome."""

    def test_les_familles_sont_distinguees(self):
        with TemporaryDirectory() as d:
            up = Path(d)
            (up / '.corbeille').mkdir()
            (up / '.corbeille' / 'cachee.jpg').write_bytes(b'x')
            (up / 'vivante.jpg').write_bytes(b'x')
            orphelines = {
                '.corbeille/cachee.jpg',      # fichier present, chemin cache
                'ARZOPA/vivante.jpg',         # morte, jumeau qui resout
                'ARZOPA/disparue.jpg',        # morte, aucun jumeau
            }
            fam, ex = O.pourquoi_elles_survivent(
                orphelines, {'vivante.jpg'}, up, [str(up)])
            self.assertEqual(fam.get('chemin_cache'), 1)
            self.assertEqual(fam.get('jumeau_qui_resout'), 1)
            self.assertEqual(fam.get('personne_ne_les_voit'), 1)
            self.assertIn('.corbeille/cachee.jpg', ex['chemin_cache'])

    def test_un_fichier_present_hors_racine_est_signale(self):
        with TemporaryDirectory() as d:
            up = Path(d)
            (up / 'ailleurs.jpg').write_bytes(b'x')
            fam, _ = O.pourquoi_elles_survivent(
                {str(up / 'ailleurs.jpg')}, set(), up,
                [r'\\NAS-Bremblens\home\Photos'])
            self.assertEqual(fam.get('hors_racine_scannee'), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
