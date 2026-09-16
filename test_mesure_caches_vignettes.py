#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O15 sur une COPIE : `--base` lit l'index sans toucher photos.db (regle 4)."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import mesure_caches_vignettes as M


def copie(d):
    db = Path(d) / 'copie.db'
    cx = sqlite3.connect(db)
    for t in ('tags', 'faces', 'animals'):
        cx.execute('CREATE TABLE "%s" (k TEXT PRIMARY KEY, v TEXT NOT NULL)' % t)
    cx.execute('INSERT INTO tags VALUES (?, ?)', ('N:\\a.jpg', '{}'))
    cx.execute('INSERT INTO faces VALUES (?, ?)',
               ('N:\\a.jpg', json.dumps({'faces': [{'bbox': [1, 2, 3, 4]}]})))
    cx.execute('INSERT INTO animals VALUES (?, ?)',
               ('N:\\a.jpg', json.dumps({'animals': [{'bbox': [5, 6, 7, 8]}]})))
    cx.commit()
    cx.close()
    return db


class LireCopie(unittest.TestCase):
    def test_memes_noms_que_le_serveur(self):
        with tempfile.TemporaryDirectory() as d:
            tags, faces, animaux = M.lire_copie(str(copie(d)))
            v = M.noms_vivants(tags, faces, animaux)
            self.assertIn(M._md5('N:\\a.jpg|512'), v['photo_thumbs'])
            self.assertEqual(v['face_thumbs'], {M._md5('N:\\a.jpg|0|[1, 2, 3, 4]')})
            self.assertEqual(v['animal_thumbs'], {M._md5('a|N:\\a.jpg|0|[5, 6, 7, 8]')})

    def test_lecture_seule(self):
        with tempfile.TemporaryDirectory() as d:
            db = copie(d)
            avant = db.read_bytes()
            M.lire_copie(str(db))
            self.assertEqual(db.read_bytes(), avant)
            self.assertFalse(Path(str(db) + '-wal').exists())

    def test_photosdb_refuse(self):
        with self.assertRaises(SystemExit):
            M.lire_copie('photos.db')


if __name__ == '__main__':
    unittest.main()
