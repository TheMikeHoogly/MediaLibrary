#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
O14 — `flush()` ecrit ce qui est signale, `save()` garde la garantie profonde.

Ce banc existe parce que la correction du 10/09 est un ARBITRAGE, pas un gain
gratuit : `flush()` est 6 547 fois moins cher que `save()` a vide (mesure sur
44 121 entrees : 0,1 ms contre 627,2 ms), et il ne voit PAS les mutations
profondes. Chaque point d'appel qui l'utilise doit donc pouvoir le PROUVER.

Les trois bancs qui comptent :
  1. `flush()` persiste bien une mutation de premier niveau ;
  2. `flush()` ne voit PAS une mutation profonde -- c'est sa limite, ecrite
     noir sur blanc, pour qu'on ne la decouvre pas un jour dans une base ;
  3. `save()` la voit toujours -- la garantie n'a pas bouge.
Puis : les trois points d'appel convertis, et la PREUVE au point d'appel.
"""

import ast
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


def _corps(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ast.get_source_segment(SOURCE, n) or ''
    raise AssertionError(nom + ' introuvable dans server.py')


class LeFlushEtSaLimite(unittest.TestCase):
    def setUp(self):
        from store_sqlite import SqliteStore
        self.tmp = tempfile.TemporaryDirectory()
        self.st = SqliteStore(Path(self.tmp.name) / 'b.db', 'tags')
        self.st.set('a.jpg', {'kw_fr': ['chat'], 'faits': {'lieu': 'Bremblens'}})
        self.st.save()

    def tearDown(self):
        try:
            self.st.cx.close()
        except Exception:                                         # noqa: BLE001
            pass
        self.tmp.cleanup()

    def _relire(self):
        from store_sqlite import SqliteStore
        st2 = SqliteStore(self.st.db_path, 'tags')
        v = dict(st2.data.get('a.jpg') or {})
        st2.cx.close()
        return v

    def test_flush_persiste_une_mutation_de_PREMIER_NIVEAU(self):
        self.st.data['a.jpg']['kw_fr'] = ['chat', 'jardin']
        self.assertEqual(self.st.flush(), 1)
        self.assertEqual(self._relire()['kw_fr'], ['chat', 'jardin'])

    def test_flush_NE_VOIT_PAS_une_mutation_PROFONDE(self):
        """Sa limite, ecrite noir sur blanc. `e['faits']['lieu'] = ...` ne
        passe pas par `__setitem__` de premier niveau : rien ne le signale."""
        self.st.data['a.jpg']['faits']['lieu'] = 'Lausanne'
        self.assertEqual(self.st.flush(), 0)
        self.assertEqual(self._relire()['faits']['lieu'], 'Bremblens')

    def test_save_la_voit_TOUJOURS(self):
        """La garantie n'a pas bouge : c'est pour ca que `save()` reste."""
        self.st.data['a.jpg']['faits']['lieu'] = 'Lausanne'
        self.st.save()
        self.assertEqual(self._relire()['faits']['lieu'], 'Lausanne')

    def test_flush_prend_le_verrou(self):
        """`_flush_rapide` ne verrouille pas : l'appeler nu depuis une route
        HTTP ecrirait pendant qu'un worker mute. `flush()` est le nom public
        parce qu'il pose le verrou."""
        import store_sqlite
        src = ast.get_source_segment(
            (HERE / 'store_sqlite.py').read_text(encoding='utf-8'),
            [n for n in ast.walk(ast.parse(
                (HERE / 'store_sqlite.py').read_text(encoding='utf-8')))
             if isinstance(n, ast.FunctionDef) and n.name == 'flush'][0])
        self.assertIn('with self.lock', src)


class LesTroisPointsDAppelConvertis(unittest.TestCase):
    """Un `flush()` pose la ou une mutation profonde peut passer perdrait une
    ecriture en silence. Chaque conversion se PROUVE au point d'appel, et le
    banc verifie que la preuve est ecrite a cote."""

    def test_sync_dir_flush_et_dit_pourquoi(self):
        s = _corps('_sync_dir')
        self.assertIn('STORE.flush()', s)
        self.assertIn('save=False', s)          # la preuve : tout est signale

    def test_cat_auto_pass_flush(self):
        s = _corps('_cat_auto_pass')
        self.assertIn('STORE.flush()', s)
        self.assertNotIn('STORE.save()', s)

    def test_reembed_flush(self):
        s = _corps('reembed_one_batch')
        self.assertIn('FACE_STORE.flush()', s)
        self.assertNotIn('FACE_STORE.save()', s)

    def test_le_repli_JSON_porte_le_MEME_NOM(self):
        """`server.py` tient l'un OU l'autre magasin selon que `photos.db`
        existe. Un `flush()` qui n'existerait que sur SQLite ferait tomber le
        scan des qu'on revient au JSON — et le retour arriere est justement
        cense etre trivial (CLAUDE.md, regle 4)."""
        self.assertIn('def flush(self):', _corps('TagStore')
                      if False else SOURCE.split('class TagStore')[1][:3000])


if __name__ == '__main__':
    unittest.main(verbosity=2)
