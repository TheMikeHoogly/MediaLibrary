#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La corbeille se lit en UN `stat` par panier, et HORS du verrou.

Mesuré le 11/09 (`mesure_corbeille.py`, 252 effacements sur le NAS) :
`GET /api/corbeille` demandait `exists`, `is_dir` puis `stat` — trois
allers-retours SMB par panier, 3,4 s à froid — et le faisait sous
`FILE_OPS_LOCK`, qui bloque tout déplacement et toute restauration.

Ce qui est gardé ici :
  1. **la même réponse** : l'ancienne écriture, recopiée verbatim, sert
     d'oracle sur un arbre qui contient les cas durs (absent, fichier vide,
     dossier imbriqué, dossier vide, mélange) ;
  2. **le nombre d'appels, compté** : un `stat` par panier-fichier, pas trois ;
  3. **le verrou ne couvre que l'instantané du journal** — lu par l'arbre
     syntaxique de la route.
"""

import ast
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import fichiers

HERE = Path(__file__).resolve().parent


def corbeille_avant(journal, now):
    """`FileOps.corbeille` d'avant le 11/09 — l'oracle, à l'identique."""
    out = []
    for rec in journal:
        if rec.get('op') != 'delete':
            continue
        dst = Path(rec['dst'])
        octets = 0
        existe = dst.exists()
        if existe:
            try:
                octets = (sum(f.stat().st_size for f in dst.rglob('*') if f.is_file())
                          if dst.is_dir() else dst.stat().st_size)
            except OSError:
                pass
        expire = rec.get('expire') or (rec.get('ts', now) + fichiers.RETENTION_JOURS * 86400)
        out.append({'ts': rec.get('ts'), 'par': rec.get('par'),
                    'expire': expire, 'expiree': expire <= now,
                    'name': dst.name, 'src': rec['src'], 'dst': str(dst),
                    'existe': existe, 'octets': octets})
    out.sort(key=lambda r: r['expire'])
    return out


class _Monde(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.trash = base / '.corbeille-effacements'
        j = []
        now = time.time()

        def panier(i, quoi):
            d = self.trash / ('20260906-%06d' % i)
            d.mkdir(parents=True)
            return d / quoi

        for i in range(12):
            p = panier(i, 'photo%d.jpg' % i)
            if i % 4:                       # un sur quatre : absent du disque
                p.write_bytes(b'x' * (i * 37))
            j.append({'op': 'delete', 'src': 's%d' % i, 'dst': str(p),
                      'ts': now - i * 86400 * 20, 'par': 'Flo'})
        dossier = panier(50, 'Album')
        (dossier / 'sous' / 'plus').mkdir(parents=True)
        (dossier / 'a.jpg').write_bytes(b'a' * 11)
        (dossier / 'sous' / 'b.jpg').write_bytes(b'b' * 22)
        (dossier / 'sous' / 'plus' / 'c.jpg').write_bytes(b'c' * 33)
        j.append({'op': 'delete', 'src': 'album', 'dst': str(dossier), 'ts': now})
        vide = panier(51, 'Vide')
        vide.mkdir()
        j.append({'op': 'delete', 'src': 'vide', 'dst': str(vide), 'ts': now,
                  'expire': now - 1})
        zero = panier(52, 'zero.jpg')
        zero.write_bytes(b'')
        j.append({'op': 'delete', 'src': 'z', 'dst': str(zero), 'ts': now})
        j.append({'op': 'move', 'src': 'a', 'dst': 'b'})
        self.journal_path = base / 'undo.json'
        self.journal_path.write_text(json.dumps(j), encoding='utf-8')
        self.journal = j
        self.now = now
        self.ops = fichiers.FileOps(
            roots_fn=lambda: [], resolve_key=lambda k: Path(k),
            store_keys=lambda: [], rekey=lambda *a, **k: True,
            journal_path=self.journal_path, trash_dir=self.trash)

    def tearDown(self):
        self._tmp.cleanup()


class LaMemeReponse(_Monde):
    def test_contre_l_ancienne_ecriture(self):
        avant = corbeille_avant(self.journal, self.now)
        self.assertEqual(self.ops.corbeille(maintenant=self.now), avant)
        self.assertEqual(self.ops.corbeille(maintenant=self.now,
                                            journal=self.ops.journal_instantane()),
                         avant)
        # le monde contient bien les cas durs
        self.assertIn(66, [e['octets'] for e in avant])            # le dossier imbriqué
        self.assertTrue(any(not e['existe'] for e in avant))
        self.assertTrue(any(e['existe'] and e['octets'] == 0 for e in avant))

    def test_un_chemin_casse_est_absent(self):
        self.assertEqual(fichiers._present_et_taille('\x00impossible'), (False, 0))
        self.assertEqual(fichiers._present_et_taille(str(self.trash / 'nulle-part')),
                         (False, 0))


class LeNombreDAppels(_Monde):
    def test_un_stat_par_panier_fichier(self):
        vrai = os.stat
        appels = []

        def espion(p, *a, **k):
            appels.append(str(p))
            return vrai(p, *a, **k)
        fichiers_fichiers = [r['dst'] for r in self.journal
                             if r.get('op') == 'delete' and not Path(r['dst']).is_dir()]
        os.stat = espion
        try:
            for d in fichiers_fichiers:
                fichiers._present_et_taille(d)
        finally:
            os.stat = vrai
        self.assertEqual(len(appels), len(fichiers_fichiers))


class LeVerrouNeCouvreQueLeJournal(unittest.TestCase):
    def test_la_route(self):
        src = (HERE / 'server.py').read_text(encoding='utf-8')
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.FunctionDef) and n.name == '_serve_corbeille':
                break
        else:
            self.fail('_serve_corbeille introuvable')
        verrous = [w for w in ast.walk(n) if isinstance(w, ast.With)
                   and 'FILE_OPS_LOCK' in ast.unparse(w.items[0].context_expr)]
        self.assertEqual(len(verrous), 1)
        dedans = ast.unparse(verrous[0])
        self.assertIn('journal_instantane()', dedans)
        self.assertNotIn('.corbeille(', dedans)
        self.assertIn('ops.corbeille(journal=journal)', ast.unparse(n))


if __name__ == '__main__':
    unittest.main(verbosity=2)
