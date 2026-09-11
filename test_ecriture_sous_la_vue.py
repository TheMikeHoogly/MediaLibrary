#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Écrire une fiche À TRAVERS la vue sans rien perdre de ce qu'on ne voit pas (11/09).

Trouvé en mesurant `/api/maint/status` : sous un utilisateur connecté, chaque
lecture de `PEOPLE_STORE.data` / `PETS_STORE.data` rend une VUE qui filtre les
citations de chemins invisibles (le PRIVE d'un autre). Le serveur lit une
fiche, la modifie, la réécrit — et trois défauts en sortaient :

  1. **la réécriture EFFAÇAIT les citations invisibles** (visages,
     confirmations, exclusions, avatar) : règle 2 du projet ;
  2. **renommer, fusionner, supprimer une fiche PLANTAIT** (la vue n'avait
     pas de `pop`) ;
  3. **`values()` / `items()` / `copy()` rendaient les fiches BRUTES** : fuite
     17b, alors que `get` et `[]` filtraient.

Ce banc les tient. D'abord la règle pure (`restaurer_fiche`, l'inverse exact
de `filtrer_fiche`) sur 600 fiches tirées au hasard ; puis la vue ; puis le
VRAI `SubjectStore` de server.py — `confirm`, `untag`, `name_cluster`,
`rename`, `delete` — exécuté sous « Mike » sur une fiche qui cite le PRIVE de
Flo, avec les vrais `visibilite.brancher` et `auteurs.garnir`, dans l'ordre où
le serveur les pose.
"""

import ast
import copy
import json
import random
import textwrap
import threading
import time
import unittest
from collections import Counter
from pathlib import Path

import auteurs as A
import visibilite as V

HERE = Path(__file__).resolve().parent

FLO_PRIV = 'N:/Photos/Photos Flo/PRIVE/x.jpg'
FLO_PRIV2 = 'N:/Photos/Photos Flo/PRIVE/y.jpg'
MIKE_PUB = 'N:/Photos/Photos Mike/2020/a.jpg'
MIKE_PUB2 = 'N:/Photos/Photos Mike/2020/b.jpg'
MIKE_PRIV = 'N:/Photos/Photos Mike/PRIVE/m.jpg'
RACINE = 'N:/Photos/2019/r.jpg'
CHEMINS = [FLO_PRIV, FLO_PRIV2, MIKE_PUB, MIKE_PUB2, MIKE_PRIV, RACINE,
           'N:/Photos/Photos Papa/p.jpg', 'N:/Photos/PRIVE/z.jpg']
UTILISATEURS = ['Mike', 'Flo', 'Papa']


def _cachees(champ, L, ok):
    return [c for c in (L or []) if V._cachee(champ, c, ok)]


def _visibles(champ, L, ok):
    return [c for c in (L or []) if not V._cachee(champ, c, ok)]


def _fiche(r):
    f = {'name': 'X', 'refs': ['r1']}
    if r.random() < 0.9:
        f['faces'] = [[r.choice(CHEMINS), r.randint(0, 3)] for _ in range(r.randint(0, 8))]
        if r.random() < 0.1:
            f['faces'].append('bruit')
    for champ in V.CHAMPS_CHEMINS:
        if r.random() < 0.7:
            f[champ] = [r.choice(CHEMINS) for _ in range(r.randint(0, 5))]
    if r.random() < 0.6:
        f['avatar'] = [r.choice(CHEMINS), r.randint(0, 2)]
    return f


class LaRegle(unittest.TestCase):
    def test_600_ALLER_RETOUR_filtrer_puis_restaurer_rend_la_fiche(self):
        r = random.Random(911)
        for i in range(600):
            b = _fiche(r)
            ok = V.filtre(r.choice(UTILISATEURS))
            n = V.filtrer_fiche(b, ok)
            if n is b:
                continue
            with self.subTest(tirage=i):
                self.assertEqual(V.restaurer_fiche(copy.deepcopy(n), b, ok), b)

    def test_600_EDITIONS_ce_qui_est_cache_reste_ce_qui_est_vu_suit_l_ecriture(self):
        r = random.Random(1109)
        for i in range(600):
            b = _fiche(r)
            ok = V.filtre(r.choice(UTILISATEURS))
            n = copy.deepcopy(V.filtrer_fiche(b, ok))
            # L'écrivain ne touche QUE ce qu'il voit : retire, ajoute, remplace.
            for champ in ('faces',) + V.CHAMPS_CHEMINS:
                if champ not in n or r.random() < 0.3:
                    continue
                L = n[champ]
                if L and r.random() < 0.5:
                    L.pop(r.randrange(len(L)))
                if r.random() < 0.5:
                    L.append([MIKE_PUB2, 9] if champ == 'faces' else MIKE_PUB2)
                if r.random() < 0.2:
                    n[champ] = list(reversed(L))
            if r.random() < 0.3:
                n['avatar'] = None
            voulu = copy.deepcopy(n)
            res = V.restaurer_fiche(n, b, ok)
            with self.subTest(tirage=i):
                for champ in ('faces',) + V.CHAMPS_CHEMINS:
                    if champ not in b and champ not in voulu:
                        continue
                    self.assertEqual(_cachees(champ, res.get(champ), ok),
                                     _cachees(champ, b.get(champ), ok),
                                     f'{champ} : le cache, dans son ordre')
                    self.assertEqual(Counter(map(str, _visibles(champ, res.get(champ), ok))),
                                     Counter(map(str, voulu.get(champ) or [])),
                                     f'{champ} : le visible, tel que l ecriture l a voulu')
                av = b.get('avatar')
                if isinstance(av, list) and av and not ok(av[0]) and not voulu.get('avatar'):
                    self.assertEqual(res['avatar'], av)
                else:
                    self.assertEqual(res.get('avatar'), voulu.get('avatar'))

    def test_l_ORDRE_des_citations_cachees_est_garde(self):
        """`_merge_assigned` coupe les plus ANCIENNES au-delà de 6 000 : une
        citation cachée renvoyée en fin de liste deviendrait la plus récente."""
        ok = V.filtre('Mike')
        b = {'faces': [[FLO_PRIV, 0], [MIKE_PUB, 0], [FLO_PRIV2, 1], [MIKE_PUB2, 0]]}
        n = V.filtrer_fiche(b, ok)
        n = copy.deepcopy(n)
        n['faces'].append([RACINE, 3])
        res = V.restaurer_fiche(n, b, ok)
        self.assertEqual(res['faces'], [[FLO_PRIV, 0], [MIKE_PUB, 0], [FLO_PRIV2, 1],
                                        [MIKE_PUB2, 0], [RACINE, 3]])

    def test_un_avatar_VISIBLE_pose_par_l_ecriture_l_emporte(self):
        ok = V.filtre('Mike')
        b = {'avatar': [FLO_PRIV, 0]}
        n = {'avatar': [MIKE_PUB, 2]}
        self.assertEqual(V.restaurer_fiche(n, b, ok)['avatar'], [MIKE_PUB, 2])

    def test_rien_de_cache_rien_ne_bouge(self):
        ok = V.filtre('Mike')
        b = {'faces': [[MIKE_PUB, 0]], 'exclude': [RACINE]}
        n = {'faces': [], 'exclude': [RACINE, MIKE_PUB2]}
        self.assertEqual(V.restaurer_fiche(n, b, ok), {'faces': [], 'exclude': [RACINE, MIKE_PUB2]})
        self.assertIs(V.restaurer_fiche(b, b, ok), b)
        self.assertEqual(V.restaurer_fiche(n, None, ok), n)
        self.assertEqual(V.restaurer_fiche('bruit', b, ok), 'bruit')


class LaVue(unittest.TestCase):
    P = {'florine': {'name': 'Florine', 'faces': [[FLO_PRIV, 0], [MIKE_PUB, 0]],
                     'avatar': [FLO_PRIV, 0]}}

    def test_values_items_copy_FILTRENT(self):
        v = V.VueFiches(copy.deepcopy(self.P), V.filtre('Mike'))
        attendu = {'name': 'Florine', 'faces': [[MIKE_PUB, 0]], 'avatar': None}
        self.assertEqual(v.values(), [attendu])
        self.assertEqual(v.items(), [('florine', attendu)])
        self.assertEqual(v.copy(), {'florine': attendu})
        self.assertEqual(dict(v), {'florine': attendu})
        # Et chez Flo, rien n'est caché : la fiche entière.
        self.assertEqual(V.VueFiches(self.P, V.filtre('Flo')).values(), [self.P['florine']])

    def test_pop_retire_la_fiche_ENTIERE_et_la_rend_brute(self):
        d = copy.deepcopy(self.P)
        v = V.VueFiches(d, V.filtre('Mike'))
        self.assertEqual(v.pop('florine'), self.P['florine'])
        self.assertEqual(d, {})
        self.assertIsNone(v.pop('florine', None))
        with self.assertRaises(KeyError):
            v.pop('florine')

    def test_la_vue_par_CHEMIN_reste_sans_pop(self):
        v = V.VueFiltree({MIKE_PUB: {}}, V.filtre('Mike'))
        self.assertFalse(hasattr(v, 'pop'))


# ─── Le VRAI SubjectStore ──────────────────────────────────────────────────
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
_LIGNES = SOURCE.splitlines(keepends=True)
_NOEUDS = {}
for _n in ast.parse(SOURCE).body:
    if isinstance(_n, (ast.FunctionDef, ast.ClassDef)):
        _NOEUDS.setdefault(_n.name, _n)


def _src(nom):
    n = _NOEUDS[nom]
    return textwrap.dedent(''.join(_LIGNES[n.lineno - 1:n.end_lineno]))


class _Magasin:
    """Comme `SqliteStore` : `.data` propriété, `set`/`get`/`has` sur `_d`."""
    def __init__(self, d):
        self._d = d
        self.lock = threading.RLock()

    @property
    def data(self):
        return self._d

    @data.setter
    def data(self, v):
        self._d.clear()
        self._d.update(v)

    def set(self, name, entry, save=True):
        with self.lock:
            self._d[name] = entry

    def get(self, k):
        return self._d.get(k)

    def has(self, k):
        return bool(self._d.get(k))

    def save(self):
        pass


class _Index:
    data = {}

    def save(self):
        pass


def _fiche_florine():
    return {'name': 'Florine', 'refs': ['r'], 'at': 1.0,
            'faces': [[FLO_PRIV, 0], [MIKE_PUB, 0]],
            'confirmed': [FLO_PRIV], 'exclude': [FLO_PRIV2],
            'avatar': [FLO_PRIV, 0],
            'auteurs': {'faces:%s:0' % FLO_PRIV: 'Flo', 'confirmed:%s' % FLO_PRIV: 'Flo',
                        'exclude:%s' % FLO_PRIV2: 'Flo', 'faces:%s:0' % MIKE_PUB: 'Mike'}}


class LeVraiSubjectStore(unittest.TestCase):
    def setUp(self):
        self.courant = threading.local()
        self.d = {'florine': _fiche_florine()}
        st = _Magasin(self.d)
        qui = lambda: getattr(self.courant, 'nom', None)             # noqa: E731
        # L'ORDRE du serveur : `garnir` (l. ~670), puis `brancher` (l. ~791).
        A.garnir(st, lambda: qui() or A.ADMIN)
        V.brancher(st, qui, par_nom=True, sensible=lambda k: False)
        ns = {'time': time, 'json': json, 'copy': copy, 'Path': Path,
              'STORE': _Index(), '_index_add_person': lambda k, t: None,
              '_index_remove_person': lambda k, t: None,
              '_enqueue_person_write': lambda *a: None,
              '_kw_has': lambda e, t: False, '_journal_fusion': lambda *a: None}
        for nom in ('_merge_assigned', '_fiche_pour_journal', 'SubjectStore'):
            exec(_src(nom), ns)                                       # noqa: S102
        self.cache = {'byid': {'c1': [(MIKE_PUB2, 1)]}, 'clusters': [{'cid': 'c1'}]}
        self.S = ns['SubjectStore']('personne', 'personne', st, _Index(), 'faces',
                                    self.cache, threading.Lock())
        self.courant.nom = 'Mike'

    def _cache_de_flo_intact(self, fiche, auteurs=True):
        self.assertIn([FLO_PRIV, 0], fiche['faces'])
        self.assertIn(FLO_PRIV, fiche['confirmed'])
        self.assertIn(FLO_PRIV2, fiche['exclude'])
        self.assertEqual(fiche['avatar'], [FLO_PRIV, 0])
        if not auteurs:
            return
        a = fiche['auteurs']
        self.assertEqual(a.get('faces:%s:0' % FLO_PRIV), 'Flo')
        self.assertEqual(a.get('confirmed:%s' % FLO_PRIV), 'Flo')
        self.assertEqual(a.get('exclude:%s' % FLO_PRIV2), 'Flo')

    def test_Mike_ne_voit_pas_le_prive_de_Flo(self):
        vu = self.S.store.data['florine']
        self.assertEqual(vu['faces'], [[MIKE_PUB, 0]])
        self.assertIsNone(vu['avatar'])

    def test_CONFIRMER_ne_perd_rien(self):
        self.assertEqual(self.S.confirm('Florine', [MIKE_PUB2]), 1)
        f = self.d['florine']
        self._cache_de_flo_intact(f)
        self.assertIn(MIKE_PUB2, f['confirmed'])
        self.assertEqual(f['auteurs'].get('confirmed:%s' % MIKE_PUB2), 'Mike')

    def test_RETIRER_ne_perd_rien(self):
        self.assertEqual(self.S.untag('Florine', [MIKE_PUB2]), 1)
        f = self.d['florine']
        self._cache_de_flo_intact(f)
        self.assertIn(MIKE_PUB2, f['exclude'])

    def test_NOMMER_un_groupe_ne_perd_rien(self):
        self.S.name_cluster('c1', 'Florine')
        f = self.d['florine']
        self._cache_de_flo_intact(f)
        self.assertIn([MIKE_PUB2, 1], f['faces'])

    def test_RENOMMER_ne_plante_plus_et_ne_perd_rien(self):
        self.S.rename('Florine', 'Flo')
        self.assertNotIn('florine', self.d)
        f = self.d['flo']
        self._cache_de_flo_intact(f)
        self.assertEqual(f['name'], 'Flo')
        self.assertEqual(f['auteurs'].get('faces:%s:0' % MIKE_PUB), 'Mike')

    def test_rename_garde_les_auteurs_de_l_absorbee_AUSSI_en_fil_de_fond(self):
        """Jusqu'au 11/09, `rename` fusionnait les listes mais pas `auteurs` :
        la réconciliation attribuait les décisions de Flo à celui qui renomme."""
        self.courant.nom = None
        self.S.rename('Florine', 'Flo')
        self._cache_de_flo_intact(self.d['flo'])

    def test_une_cle_d_auteur_COMMUNE_la_fiche_qui_recoit_garde_la_sienne(self):
        self.d['flo'] = {'name': 'Flo', 'refs': [], 'faces': [[MIKE_PUB, 0]],
                         'auteurs': {'faces:%s:0' % MIKE_PUB: 'Flo'}}
        self.courant.nom = None
        self.S.rename('Florine', 'Flo')
        self.assertEqual(self.d['flo']['auteurs'].get('faces:%s:0' % MIKE_PUB), 'Flo')

    def test_FUSIONNER_dans_une_fiche_qui_cache_aussi_ne_perd_rien(self):
        self.d['flo'] = {'name': 'Flo', 'refs': [], 'at': 0.5,
                         'faces': [[MIKE_PRIV, 2], [FLO_PRIV2, 5]],
                         'auteurs': {'faces:%s:2' % MIKE_PRIV: 'Mike',
                                     'faces:%s:5' % FLO_PRIV2: 'Flo'}}
        self.S.rename('Florine', 'Flo')
        f = self.d['flo']
        self._cache_de_flo_intact(f)
        self.assertIn([FLO_PRIV2, 5], f['faces'])
        self.assertEqual(f['auteurs'].get('faces:%s:5' % FLO_PRIV2), 'Flo')

    def test_SUPPRIMER_ne_plante_plus(self):
        self.S.delete('Florine')
        self.assertNotIn('florine', self.d)

    def test_le_FIL_DE_FOND_ecrit_comme_avant(self):
        self.courant.nom = None
        self.S.confirm('Florine', [MIKE_PUB2])
        self._cache_de_flo_intact(self.d['florine'])


if __name__ == '__main__':
    unittest.main()
