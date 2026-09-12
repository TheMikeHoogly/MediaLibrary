#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`_pkey` mémoïsé : la même règle, calculée une fois par chaîne.

L'horloge de phases du 11/09 a trouvé deux balayages de TOUTE la photothèque
à chaque ouverture de dossier : `_index_entries_under` (378–772 ms, un `_pkey`
par clé) et la reconstruction de `_key_index` (618–784 ms, verrou tenu, une
fois par minute). Les deux recalculent pour 44 604 clés une normalisation dont
la réponse ne change jamais.

Ce qu'il ne fallait PAS faire, et que ces bancs gardent :
  * réécrire la règle. `Path(p).as_posix().lower()` n'est pas équivalent à un
    `replace('\\\\', '/')` sur les cas tordus (PERFORMANCE.md § 3.8). Les bancs
    comparent donc à l'ANCIENNE expression prise pour oracle, et ils le font
    avec `PureWindowsPath` — les règles de Windows, pas celles de la sandbox ;
  * changer la carte. Deux clés qui se normalisent pareil : la DERNIÈRE gagne,
    comme dans `fichiers.build_key_index` ; une clé qui lève est écartée.

Et une optimisation qui ne se compte pas est une intention : un banc COMPTE les
objets `Path` construits par la seconde reconstruction de la carte.
"""

import ast
import sys
import threading
import time
import types
import unittest
from functools import lru_cache
from pathlib import Path, PurePath, PureWindowsPath

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


def _src(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ast.get_source_segment(SOURCE, n)
    raise AssertionError(nom + ' introuvable dans server.py')


def _sans_decorateur(src):
    return '\n'.join(l for l in src.splitlines() if not l.startswith('@'))


def _oracle(p):
    """L'expression d'AVANT le 11/09, sous les règles de Windows."""
    return PureWindowsPath(p).as_posix().lower()


def _fichiers_windows(PathFn):
    """`norm` et `build_key_index` de fichiers.py, exécutés avec `PathFn` à
    la place de `Path` : le vrai code, sous les règles de Windows."""
    src = (HERE / 'fichiers.py').read_text(encoding='utf-8')
    mod = types.ModuleType('fichiers_windows')
    mod.Path = PathFn
    for n in ast.parse(src).body:
        if isinstance(n, ast.FunctionDef) and n.name in ('norm', 'build_key_index'):
            exec(ast.get_source_segment(src, n), mod.__dict__)         # noqa: S102
    return mod


UPLOAD = PureWindowsPath(r'\\NAS-Bremblens\home\Photos\_Uploads')

CAS = [
    r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\20220213_173019.jpg',
    r'\\nas-bremblens\HOME\photos\Photos Mike\2022\20220213_173019.JPG',
    '//NAS-Bremblens/home/Photos/Photos Mike/2022/x.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Mike\\2022\x.jpg',       # double
    r'\\NAS-Bremblens\home\Photos\.\Photos Mike\x.jpg',           # point
    r'\\NAS-Bremblens\home\Photos\Photos Mike' + '\\',            # final
    r'\\NAS-Bremblens\home\Photos\Photos Flo\Évasion\Été 2015.jpg',
    r'C:\Prog\Claude\MediaLibrary\uploads\a.jpg',
    'Album/x.jpg', 'Album\\x.jpg', 'x.JPG', '', ' espace .jpg', '.',
    r'\\NAS-Bremblens\home\Photos\PRIVE\ß.jpg',
]


class _Monde:
    """`_pkey`, ses deux mémoires, `_resolve_key` et `_key_index`, exécutés
    seuls (importer server.py ouvrirait la base et lancerait des fils), avec
    les règles de chemin de Windows et un compteur de `Path` construits."""

    def __init__(self, index):
        self.construits = 0
        monde = self

        def FauxPath(*a):
            monde.construits += 1
            return PureWindowsPath(*a)

        self.fichiers_mod = _fichiers_windows(FauxPath)
        self.g = {
            'Path': FauxPath, 'PurePath': PurePath, 'lru_cache': lru_cache, 'time': time,
            'threading': threading, 'fichiers': self.fichiers_mod,
            'UPLOAD_DIR': UPLOAD, 'INDEX_BRUT': index,
            '_KEY_IDX': {"at": 0.0, "n": -1, "map": None},
            '_KEY_IDX_LOCK': threading.Lock(), 'KEY_IDX_TTL': 60.0,
        }
        exec('PKEY_MEMO_MAX = 1 << 17', self.g)                        # noqa: S102
        # `_cle_en_chemin` AVANT `_resolve_key` : depuis le 12/09 la seconde
        # delegue a la premiere (§ 3.23). Un espace qui ne porterait pas les
        # deux rendrait une carte VIDE — et ce banc mesurerait son propre
        # espace au lieu de la regle.
        for nom in ('_pkey', '_pkey_chaine', '_pkey_de_cle', '_cle_en_chemin',
                    '_resolve_key', '_key_index'):
            src = _src(nom)
            if nom in ('_pkey_chaine', '_pkey_de_cle'):
                src = '@lru_cache(maxsize=PKEY_MEMO_MAX)\n' + _sans_decorateur(src)
            exec(src, self.g)                                          # noqa: S102

    def ancienne_carte(self, index):
        """L'ancienne reconstruction, telle qu'elle était écrite :
        `fichiers.build_key_index(list(INDEX_BRUT.keys()), _resolve_key)` —
        le vrai code de `fichiers.py`, sous les règles de Windows."""
        f = _fichiers_windows(PureWindowsPath)
        g = {'Path': PureWindowsPath, 'UPLOAD_DIR': UPLOAD,
             'lru_cache': lru_cache}
        exec(_src('_cle_en_chemin'), g)                                # noqa: S102
        exec(_src('_resolve_key'), g)                                  # noqa: S102
        return f.build_key_index(list(index.keys()), g['_resolve_key'])


class LaRegleNaPasBouge(unittest.TestCase):
    def test_chaque_cas_tordu_rend_ce_que_rendait_l_ancienne_expression(self):
        m = _Monde({})
        for tour in (1, 2):                    # 2e tour : servi par la mémoire
            for c in CAS:
                self.assertEqual(m.g['_pkey'](c), _oracle(c), (tour, c))

    def test_un_PATH_rend_la_meme_cle_et_passe_par_sa_chaine(self):
        """Depuis le 11/09 au soir, un `Path` est mémoïsé par sa chaîne :
        `Path(str(p))` est le même chemin que `p`. Vérifié sur les cas tordus,
        sous les règles de Windows ; et un `Path` déjà vu ne reconstruit rien."""
        m = _Monde({})
        for c in CAS:
            self.assertEqual(m.g['_pkey'](PureWindowsPath(c)), _oracle(c), c)
        p = PureWindowsPath(CAS[0])
        m.g['_pkey'](p)
        n = m.construits
        for _ in range(50):
            m.g['_pkey'](p)
        self.assertEqual(m.construits, n)

    def test_un_objet_ni_chaine_ni_path_passe_par_le_calcul_direct(self):
        class Entree:                       # un DirEntry : str() n'est PAS le chemin
            def __fspath__(self):
                return r'\\NAS\a\B.jpg'

            def __str__(self):
                return '<DirEntry B.jpg>'
        m = _Monde({})
        self.assertEqual(m.g['_pkey'](Entree()), _oracle(r'\\NAS\a\B.jpg'))

    def test_une_chaine_deja_vue_ne_se_recalcule_pas(self):
        m = _Monde({})
        c = CAS[0]
        m.g['_pkey'](c)
        n = m.construits
        for _ in range(100):
            m.g['_pkey'](c)
        self.assertEqual(m.construits, n)

    def test_la_memoire_est_BORNEE(self):
        """Sans borne, chaque renommage laisserait une entrée de plus pour
        toujours. Avec une borne trop courte, 44 604 clés la videraient à
        chaque clic et on repaierait tout."""
        m = _Monde({})
        for nom in ('_pkey_chaine', '_pkey_de_cle'):
            taille = m.g[nom].cache_info().maxsize
            self.assertIsNotNone(taille, nom)
            self.assertGreaterEqual(taille, 2 * 44604, nom)
        self.assertIn('@lru_cache(maxsize=PKEY_MEMO_MAX)', SOURCE)
        self.assertIn('PKEY_MEMO_MAX = 1 << 17', SOURCE)


class LaCarteNaPasBouge(unittest.TestCase):
    def _index(self):
        d = {c: {'x': i} for i, c in enumerate(CAS) if c not in ('', '.')}
        # deux clés qui se normalisent pareil : la DERNIÈRE doit gagner
        d[r'\\NAS-BREMBLENS\home\Photos\Photos Mike\2022\20220213_173019.jpg'] = {}
        return d

    def test_meme_carte_meme_gagnant_que_l_ancienne_reconstruction(self):
        index = self._index()
        m = _Monde(index)
        carte = m.g['_key_index']()
        self.assertEqual(carte, m.ancienne_carte(index))
        cle = _oracle(CAS[0])
        self.assertEqual(carte[cle],
                         r'\\NAS-BREMBLENS\home\Photos\Photos Mike\2022\20220213_173019.jpg')

    def test_une_cle_d_uploads_devient_un_chemin_sous_UPLOAD_DIR(self):
        """C'est la différence avec `_index_entries_under`, qui lit la VUE et
        reconnaît Uploads par l'absence de `/` : les deux ne sont pas
        interchangeables, et ce banc le rappelle."""
        m = _Monde({'Album/x.jpg': {}})
        carte = m.g['_key_index']()
        self.assertEqual(list(carte), [_oracle(UPLOAD / 'Album/x.jpg')])

    def test_la_seconde_reconstruction_ne_construit_AUCUN_Path(self):
        """Ce que la correction prétend économiser, compté. Première
        reconstruction : au moins un `Path` par clé. TTL expiré, même index :
        zéro."""
        index = {r'\\NAS-Bremblens\home\Photos\Photos Mike\%d\p%d.jpg' % (i % 20, i): {}
                 for i in range(2000)}
        m = _Monde(index)
        c1 = m.g['_key_index']()
        premiere = m.construits
        self.assertGreaterEqual(premiere, 2000)
        m.g['_KEY_IDX']['at'] = 0.0                  # TTL expiré
        c2 = m.g['_key_index']()
        self.assertIsNot(c1, c2)                     # elle a bien été rebâtie
        self.assertEqual(c1, c2)
        self.assertEqual(m.construits, premiere)

    def test_elle_se_rebatit_toujours_quand_l_index_change(self):
        index = {r'\\NAS\a\1.jpg': {}}
        m = _Monde(index)
        self.assertEqual(len(m.g['_key_index']()), 1)
        index[r'\\NAS\a\2.jpg'] = {}
        self.assertEqual(len(m.g['_key_index']()), 2)


class LesAppelantsNOntPasBouge(unittest.TestCase):
    def test_l_appelant_de_la_galerie_demande_toujours_pkey(self):
        """C'est l'appelant qu'on accélère par la mémoire, pas la règle qu'on
        contourne : `_index_entries_under` normalise CHAQUE clé par `_pkey`,
        dans sa boucle.

        Sur l'ARBRE, pas sur une ligne : la version d'avant cherchait le texte
        `_pkey(k).startswith(pref)`, et elle est tombée ROUGE le 12/09 quand
        le § 3.17 a scindé l'expression en `kp = _pkey(k)` puis
        `kp.startswith(pref)` — même règle, même appel, autre écriture. Rien
        ne la lançait (§ 3.18)."""
        arbre = ast.parse(_src('_index_entries_under'))
        boucles = [n for n in ast.walk(arbre) if isinstance(n, ast.For)]
        self.assertTrue(boucles, 'plus de boucle sur les clés de l\'index')
        dans_boucle = set()
        for b in boucles:
            for c in ast.walk(b):
                if (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                        and isinstance(b.target, ast.Name)):
                    args = [a.id for a in c.args if isinstance(a, ast.Name)]
                    if b.target.id in args:
                        dans_boucle.add(c.func.id)
        self.assertIn('_pkey', dans_boucle,
                      'la boucle ne normalise plus chaque clé par _pkey')

    def test_la_carte_n_appelle_plus_la_reconstruction_sans_memoire(self):
        s = _src('_key_index')
        self.assertIn('_pkey_de_cle(k)', s)
        self.assertNotIn('build_key_index(', ast.unparse(ast.parse(s)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
