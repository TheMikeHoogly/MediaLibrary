#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_copie_base` — bases jouets en WAL, aucune prod, aucun NAS.

Ce qu'on protège ici :

1. **La porte** : ce banc n'écrit jamais sur un fichier nommé `photos.db`,
   ni sur la source, ni ailleurs qu'à la racine du projet. C'est la seule
   façon dont il pourrait nuire.
2. **La raison d'être** : la copie porte ce qui n'est encore QUE dans le WAL.
   Le test le montre par comparaison — un copier-coller du seul `.db` rend une
   base ouvrable et PÉRIMÉE. Si ce test tombait, le banc n'aurait plus d'objet.
3. **La preuve** : `compter` rend les lignes réellement présentes dans la
   copie, et `quick_check` la dit saine.
4. Les sidecars d'une copie PRÉCÉDENTE sont retirés — sans quoi on lirait un
   mélange de deux instants.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import mesure_copie_base as M


def base_jouet(chemin, lignes=7):
    """Base en WAL dont les lignes sont encore DANS le WAL : la connexion
    reste ouverte, donc rien n'est encore rapatrié dans le `.db`."""
    cx = sqlite3.connect(chemin)
    cx.execute('PRAGMA journal_mode=WAL')
    cx.execute('CREATE TABLE tags (k TEXT PRIMARY KEY, v TEXT)')
    cx.executemany('INSERT INTO tags VALUES (?, ?)',
                   [(f'cle{i}', '{}') for i in range(lignes)])
    cx.commit()
    return cx


class TestPorte(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.avant = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.avant)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_refuse_ecrire_sur_photos_db(self):
        self.assertIn('REFUS', M.verifier_cible('source.db', 'photos.db'))
        self.assertIn('REFUS', M.verifier_cible('source.db', 'PHOTOS.DB'))

    def test_refuse_la_source_comme_cible(self):
        Path('a.db').write_bytes(b'')
        self.assertIn('REFUS', M.verifier_cible('a.db', 'a.db'))

    def test_refuse_hors_de_la_racine(self):
        os.mkdir('ailleurs')
        self.assertIn('REFUS', M.verifier_cible('a.db', 'ailleurs/copie.db'))

    def test_source_absente_est_dite(self):
        self.assertIn('introuvable', M.verifier_cible('absente.db', 'c.db'))

    def test_copier_leve_sur_refus(self):
        with self.assertRaises(SystemExit):
            M.copier('source.db', 'photos.db')


class TestCopie(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.avant = os.getcwd()
        os.chdir(self.tmp)
        self.cx = base_jouet('source.db', lignes=7)

    def tearDown(self):
        self.cx.close()
        os.chdir(self.avant)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_la_copie_porte_ce_qui_n_est_que_dans_le_wal(self):
        # l'état de départ : le WAL n'est pas vide, il porte les lignes
        _, wal, _ = M.tailles('source.db')
        self.assertGreater(wal, 0)

        rap = M.copier('source.db', 'copie.db')
        cx = sqlite3.connect('copie.db')
        try:
            self.assertEqual(
                cx.execute('SELECT COUNT(*) FROM tags').fetchone()[0], 7)
        finally:
            cx.close()

        # et voici pourquoi le banc existe : le copier-coller naif se tait
        shutil.copyfile('source.db', 'naive.db')
        cx = sqlite3.connect('naive.db')
        try:
            vues = cx.execute('SELECT COUNT(*) FROM tags').fetchone()[0]
        except sqlite3.DatabaseError:
            vues = 0                      # table pas meme creee dans le .db
        finally:
            cx.close()
        self.assertLess(vues, 7)
        self.assertEqual(rap['wal_octets'], wal)

    def test_le_rapport_prouve_ce_qu_il_avance(self):
        rap = M.copier('source.db', 'copie.db')
        self.assertEqual(rap['integrite'], 'ok')
        self.assertEqual(rap['lignes']['tags'], 7)
        self.assertGreater(rap['cible_octets'], 0)
        self.assertGreaterEqual(rap['snapshot_a'], rap['source_modifiee_a'])
        self.assertIn('COPIE DE LA BASE', M.afficher(rap))

    def test_les_sidecars_d_une_copie_precedente_partent(self):
        Path('copie.db-wal').write_bytes(b'vieux')
        Path('copie.db-shm').write_bytes(b'vieux')
        rap = M.copier('source.db', 'copie.db')
        self.assertEqual(sorted(rap['sidecars_retires']),
                         ['copie.db-shm', 'copie.db-wal'])

    def test_la_source_reste_intacte(self):
        avant = Path('source.db').read_bytes()
        M.copier('source.db', 'copie.db')
        self.assertEqual(Path('source.db').read_bytes(), avant)
        # et la source est toujours ecrivable : aucun verrou laisse derriere
        self.cx.execute("INSERT INTO tags VALUES ('apres', '{}')")
        self.cx.commit()

    def test_sans_verification_le_dit(self):
        rap = M.copier('source.db', 'copie.db', verifier=False)
        self.assertIn('non vérifiée', rap['integrite'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
