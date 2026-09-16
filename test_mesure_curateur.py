#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le banc du curateur (O8) juge-t-il vraiment (B) contre (A) ?

Synthetique : une base temporaire, jamais photos.db. Le test qui compte est
le dernier -- un (B) faux doit etre VU par le juge.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

import mesure_curateur as M


def base(d, n_pers=5, refs=30, faces=300, graine=7):
    rng = np.random.default_rng(graine)
    db = Path(d) / 'copie.db'
    cx = sqlite3.connect(db)
    cx.execute("CREATE TABLE vectors (kind TEXT, k TEXT, v BLOB, dtype TEXT, ver TEXT, at REAL)")
    rows = []
    for p in range(n_pers):
        for r in range(refs):
            rows.append(('people', 'p%d\x1frefs\x1f%d' % (p, r),
                         rng.standard_normal(16).astype(np.float16).tobytes(), 'f16'))
    for f in range(faces):
        rows.append(('faces', 'x%d.jpg\x1ffaces\x1f0' % f,
                     rng.standard_normal(16).astype(np.float16).tobytes(), 'f16'))
    cx.executemany("INSERT INTO vectors (kind, k, v, dtype) VALUES (?,?,?,?)", rows)
    cx.commit()
    cx.close()
    return str(db)


class Banc(unittest.TestCase):
    def test_b_egale_a(self):
        with tempfile.TemporaryDirectory() as d:
            refs, faces = M.charger(base(d))
            C, pr, n = M.construire(refs)
            self.assertEqual(n, 5)
            self.assertGreater(len(C), 5)  # 30 refs -> plusieurs facettes
            A = M.chemin_a(faces, C, pr, n)
            B = M.chemin_b(faces, C, pr, n, 64)
            self.assertTrue(np.array_equal(A[:, 0], B[:, 0]))
            self.assertLess(np.max(np.abs(A[:, 1:] - B[:, 1:])), 1e-4)

    def test_tranche_ne_change_rien(self):
        with tempfile.TemporaryDirectory() as d:
            refs, faces = M.charger(base(d))
            C, pr, n = M.construire(refs)
            self.assertTrue(np.allclose(M.chemin_b(faces, C, pr, n, 7),
                                        M.chemin_b(faces, C, pr, n, 1000)))

    def test_limite(self):
        with tempfile.TemporaryDirectory() as d:
            _, faces = M.charger(base(d), limite=10)
            self.assertEqual(len(faces), 10)

    def test_photosdb_refuse(self):
        with self.assertRaises(SystemExit):
            M.charger('photos.db')

    def test_le_juge_voit_un_b_faux(self):
        with tempfile.TemporaryDirectory() as d:
            db = base(d)
            vrai = M.chemin_b
            try:
                M.chemin_b = lambda f, C, pr, n, t: vrai(f, C, pr, n, t) * 0
                self.assertEqual(M.main(['--base', db]), 1)
            finally:
                M.chemin_b = vrai
            self.assertEqual(M.main(['--base', db]), 0)


if __name__ == '__main__':
    unittest.main()
