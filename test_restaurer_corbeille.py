#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bancs de `restaurer_corbeille.py` -- sur un FAUX fonds, jamais sur le NAS.

Ce qu'il faut prouver avant de laisser cet outil toucher a l'archive :

1. il ne restaure QUE ce qu'un jugement ecrit a classe « vraie derniere
   copie » -- un groupe absent du rapport ne bouge pas ;
2. il n'ECRASE jamais une origine deja occupee (c'est la perte qu'on
   cherche a eviter, pas une variante acceptable) ;
3. un sha256 qui ne correspond plus au manifeste ARRETE le geste ;
4. l'annulation remet exactement ce qui a ete deplace ;
5. « deja fait » n'est pas un echec -- deux bats du projet l'ont crie a tort.
"""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restaurer_corbeille as R  # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()


class Fonds:
    """Un faux fonds : une corbeille, des groupes, des origines."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='restcorb_'))
        self.corbeille = self.tmp / '.corbeille-rangement'
        self.fonds = self.tmp / 'Photos'
        self.corbeille.mkdir(parents=True)
        self.fonds.mkdir(parents=True)

    def groupe(self, gid, nom, contenu, origine_rel, sha_manifeste=None):
        d = self.corbeille / gid
        d.mkdir()
        (d / nom).write_bytes(contenu)
        origine = self.fonds / origine_rel
        (d / 'manifeste.json').write_text(json.dumps({
            'origine': str(origine),
            'canonique': str(self.fonds / 'ailleurs.jpg'),
            'sha256': sha_manifeste or sha(contenu),
            'groupe': gid,
        }), encoding='utf-8')
        return {'groupe': gid, 'fichier': nom}, origine

    def detruire(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Restauration(unittest.TestCase):
    def setUp(self):
        self.f = Fonds()

    def tearDown(self):
        self.f.detruire()

    def test_apercu_ne_deplace_rien(self):
        ligne, origine = self.f.groupe('aaa', 'x_a.jpg', b'AAA', 'Flo/a.jpg')
        stats, journal = R.restaurer(self.f.corbeille, [ligne], appliquer=False)
        self.assertEqual(stats['restaures'], 1)
        self.assertIsNone(journal)
        self.assertFalse(origine.exists())
        self.assertTrue((self.f.corbeille / 'aaa' / 'x_a.jpg').exists())

    def test_restaure_et_journalise(self):
        ligne, origine = self.f.groupe('aaa', 'x_a.jpg', b'AAA', 'Flo/a.jpg')
        stats, journal = R.restaurer(self.f.corbeille, [ligne], appliquer=True,
                                     journal_dir=self.f.tmp)
        self.assertEqual((stats['restaures'], stats['refuses']), (1, 0))
        self.assertTrue(origine.exists())
        self.assertEqual(origine.read_bytes(), b'AAA')
        self.assertFalse((self.f.corbeille / 'aaa' / 'x_a.jpg').exists())
        # le manifeste garde la trace, et le dossier du groupe reste
        mani = json.loads((self.f.corbeille / 'aaa' / 'manifeste.json')
                          .read_text(encoding='utf-8'))
        self.assertIn('restaure_le', mani)
        self.assertEqual(mani['restaure_vers'], str(origine))
        self.assertTrue(Path(journal).exists())

    def test_jamais_par_dessus_une_origine_occupee(self):
        ligne, origine = self.f.groupe('aaa', 'x_a.jpg', b'AAA', 'Flo/a.jpg')
        origine.parent.mkdir(parents=True, exist_ok=True)
        origine.write_bytes(b'JE SUIS VIVANT')
        stats, _ = R.restaurer(self.f.corbeille, [ligne], appliquer=True,
                               journal_dir=self.f.tmp)
        self.assertEqual((stats['restaures'], stats['refuses']), (0, 1))
        self.assertEqual(origine.read_bytes(), b'JE SUIS VIVANT')
        self.assertTrue((self.f.corbeille / 'aaa' / 'x_a.jpg').exists())

    def test_sha256_qui_ne_colle_plus_arrete_tout(self):
        ligne, origine = self.f.groupe('aaa', 'x_a.jpg', b'AAA', 'Flo/a.jpg',
                                       sha_manifeste=sha(b'AUTRE CHOSE'))
        stats, _ = R.restaurer(self.f.corbeille, [ligne], appliquer=True,
                               journal_dir=self.f.tmp)
        self.assertEqual((stats['restaures'], stats['refuses']), (0, 1))
        self.assertFalse(origine.exists())

    def test_deja_fait_n_est_pas_un_echec(self):
        ligne, origine = self.f.groupe('aaa', 'x_a.jpg', b'AAA', 'Flo/a.jpg')
        R.restaurer(self.f.corbeille, [ligne], appliquer=True,
                    journal_dir=self.f.tmp)
        stats, _ = R.restaurer(self.f.corbeille, [ligne], appliquer=True,
                               journal_dir=self.f.tmp)
        self.assertEqual((stats['deja_fait'], stats['refuses']), (1, 0))

    def test_annuler_remet_exactement(self):
        ligne, origine = self.f.groupe('aaa', 'x_a.jpg', b'AAA', 'Flo/a.jpg')
        _, journal = R.restaurer(self.f.corbeille, [ligne], appliquer=True,
                                 journal_dir=self.f.tmp)
        self.assertEqual(R.annuler(journal), 0)
        self.assertFalse(origine.exists())
        src = self.f.corbeille / 'aaa' / 'x_a.jpg'
        self.assertTrue(src.exists())
        self.assertEqual(src.read_bytes(), b'AAA')
        mani = json.loads((self.f.corbeille / 'aaa' / 'manifeste.json')
                          .read_text(encoding='utf-8'))
        self.assertNotIn('restaure_le', mani)

    def test_manifeste_illisible_refuse(self):
        ligne, _ = self.f.groupe('aaa', 'x_a.jpg', b'AAA', 'Flo/a.jpg')
        (self.f.corbeille / 'aaa' / 'manifeste.json').write_text('{pas du json',
                                                                 encoding='utf-8')
        stats, _ = R.restaurer(self.f.corbeille, [ligne], appliquer=True,
                               journal_dir=self.f.tmp)
        self.assertEqual((stats['restaures'], stats['refuses']), (0, 1))


class LaListeVientDUnJugementEcrit(unittest.TestCase):
    """L'outil ne DECIDE jamais qu'une photo est la derniere de son espece."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='restrap_'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lit_la_classe_vraie_derniere_copie(self):
        rap = self.tmp / 'r.json'
        rap.write_text(json.dumps({'genere_le': 'x', 'lignes': {
            'jumeau_pixels': [{'groupe': 'zzz', 'fichier': 'z.jpg'}],
            'vraie_derniere_copie': [{'groupe': 'aaa', 'fichier': 'a.jpg'}],
            'illisible': [{'groupe': 'yyy', 'fichier': 'y.jpg'}],
        }}), encoding='utf-8')
        lignes, err = R.groupes_a_restaurer(rap)
        self.assertEqual(err, '')
        self.assertEqual([l['groupe'] for l in lignes], ['aaa'])

    def test_rapport_absent_refuse(self):
        lignes, err = R.groupes_a_restaurer(self.tmp / 'nulle_part.json')
        self.assertEqual(lignes, [])
        self.assertIn('introuvable', err)

    def test_classe_absente_refuse(self):
        rap = self.tmp / 'r.json'
        rap.write_text(json.dumps({'lignes': {'jumeau_pixels': []}}),
                       encoding='utf-8')
        lignes, err = R.groupes_a_restaurer(rap)
        self.assertEqual(lignes, [])
        self.assertIn(R.CLASSE, err)


if __name__ == '__main__':
    unittest.main(verbosity=2)
