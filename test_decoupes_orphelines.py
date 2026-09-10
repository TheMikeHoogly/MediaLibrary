#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Celui qui remplace une detection nettoie ses decoupes (10/09).

Le pendant du correctif des vignettes, dans l'autre sens. Pour une vignette de
photo, nous SAVIONS que l'image n'avait pas change et nous la gardions ; pour
une decoupe, nous savons que le cadre a change et nous la jetons. Dans les deux
cas c'est l'ECRIVAIN qui sait, donc c'est lui qui agit — et O15 se ferme par
construction au lieu d'etre une corvee qui revient.

Mesure qui a motive ce banc : **83 % de `face_thumbs`** (28 880 fichiers,
192,9 Mo) et **74 % de `animal_thumbs`** etaient orphelins. Le re-embedding
deplace les cadres ; la migration du pipeline animal remet le magasin a zero.

Le banc verifie aussi le SENS de l'analyse : sur les cinq endroits qui ecrivent
une liste de detections, trois n'ecrivent QUE s'il n'y avait rien (`FACE_STORE.
has(name)`, `fe is None`) — ils n'ont donc rien a nettoyer, et leur ajouter un
nettoyage aurait ete du bruit.
"""

import ast
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable dans server.py')


def _src(nom):
    return ast.get_source_segment(SOURCE, _noeud(nom)) or ''


def _helpers(faces_dir, animaux_dir):
    m = types.ModuleType('dec')
    m.__dict__.update({'os': os, 'Path': Path,
                       'FACE_THUMB_DIR': Path(faces_dir),
                       'ANIMAL_THUMB_DIR': Path(animaux_dir)})
    for nom in ('_nom_decoupe', '_oublier_decoupes', '_oublier_visages',
                '_oublier_animaux', '_vider_cache_decoupes'):
        exec(_src(nom), m.__dict__)                                # noqa: S102
    return m


class CeluiQuiRemplaceNettoie(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.f = Path(self.tmp.name) / 'faces'
        self.a = Path(self.tmp.name) / 'animaux'
        self.f.mkdir()
        self.a.mkdir()
        self.m = _helpers(self.f, self.a)

    def tearDown(self):
        self.tmp.cleanup()

    def _poser(self, key, detections, dossier, prefixe=''):
        for i, d in enumerate(detections):
            nom = self.m._nom_decoupe(key, i, d['bbox'], prefixe)
            (Path(dossier) / (nom + '.jpg')).write_bytes(b'jpeg')

    def test_un_cadre_DEPLACE_perd_sa_decoupe(self):
        vieux = [{'bbox': [1, 2, 3, 4]}]
        neuf = [{'bbox': [9, 9, 9, 9]}]
        self._poser('x.jpg', vieux, self.f)
        self.assertEqual(self.m._oublier_visages('x.jpg', vieux, neuf), 1)
        self.assertEqual(list(self.f.glob('*.jpg')), [])

    def test_un_cadre_INCHANGE_garde_la_sienne(self):
        """Sinon on referait pour rien une decoupe encore bonne."""
        m = [{'bbox': [1, 2, 3, 4]}]
        self._poser('x.jpg', m, self.f)
        self.assertEqual(self.m._oublier_visages('x.jpg', m, m), 0)
        self.assertEqual(len(list(self.f.glob('*.jpg'))), 1)

    def test_sur_plusieurs_visages_seuls_les_deplaces_partent(self):
        vieux = [{'bbox': [1, 1, 1, 1]}, {'bbox': [2, 2, 2, 2]}]
        neuf = [{'bbox': [1, 1, 1, 1]}, {'bbox': [8, 8, 8, 8]}]
        self._poser('x.jpg', vieux, self.f)
        self.assertEqual(self.m._oublier_visages('x.jpg', vieux, neuf), 1)
        self.assertEqual(len(list(self.f.glob('*.jpg'))), 1)

    def test_une_detection_VIDEE_perd_tout(self):
        vieux = [{'bbox': [1, 1, 1, 1]}, {'bbox': [2, 2, 2, 2]}]
        self._poser('x.jpg', vieux, self.f)
        self.assertEqual(self.m._oublier_visages('x.jpg', vieux, []), 2)

    def test_rien_a_oublier_ne_touche_a_rien(self):
        self._poser('x.jpg', [{'bbox': [1, 1, 1, 1]}], self.f)
        self.assertEqual(self.m._oublier_visages('x.jpg', None, [{'bbox': [7]}]), 0)
        self.assertEqual(len(list(self.f.glob('*.jpg'))), 1)

    def test_les_animaux_ont_leur_PREFIXE(self):
        """`a|` : le meme cadre sur la meme photo ne designe pas le meme
        fichier selon qu'on parle d'un visage ou d'un animal."""
        d = [{'bbox': [1, 2, 3, 4]}]
        self.assertNotEqual(self.m._nom_decoupe('x.jpg', 0, [1, 2, 3, 4]),
                            self.m._nom_decoupe('x.jpg', 0, [1, 2, 3, 4], 'a|'))
        self._poser('x.jpg', d, self.a, 'a|')
        self.assertEqual(self.m._oublier_animaux('x.jpg', d, []), 1)

    def test_on_ne_touche_pas_a_la_decoupe_d_une_AUTRE_photo(self):
        d = [{'bbox': [1, 1, 1, 1]}]
        self._poser('x.jpg', d, self.f)
        self._poser('y.jpg', d, self.f)
        self.m._oublier_visages('x.jpg', d, [])
        self.assertEqual(len(list(self.f.glob('*.jpg'))), 1)

    def test_vider_le_cache_en_entier(self):
        for i in range(5):
            (self.a / ('%02d.jpg' % i)).write_bytes(b'x')
        self.assertEqual(self.m._vider_cache_decoupes(self.a), 5)
        self.assertEqual(list(self.a.glob('*')), [])

    def test_vider_un_dossier_absent_ne_casse_pas(self):
        self.assertEqual(
            self.m._vider_cache_decoupes(Path(self.tmp.name) / 'nexistepas'), 0)


class LesDeuxSeulsSitesQuiREMPLACENT(unittest.TestCase):
    """Cinq endroits ecrivent une liste de detections ; **deux seulement**
    remplacent une liste EXISTANTE. Les trois autres sont gardes par
    `FACE_STORE.has(name)` ou `fe is None` : ils n'ecrivent que s'il n'y avait
    rien, donc ils n'ont rien a nettoyer. Ce banc tient les deux ET la raison
    des trois autres — sans quoi un lecteur pressé ajouterait du nettoyage
    partout, et personne ne saurait plus pourquoi."""

    def test_le_re_embedding_oublie_les_anciens_cadres(self):
        s = _src('reembed_one_batch')
        self.assertIn("_oublier_visages(k, e.get('faces'), newfaces)", s)

    def test_la_migration_du_pipeline_animal_vide_le_cache(self):
        s = _src('migrate_animal_pipeline')
        self.assertIn('ANIMAL_STORE.data = {}', s)
        self.assertIn('_vider_cache_decoupes(ANIMAL_THUMB_DIR)', s)

    def test_les_trois_autres_sont_GARDES_donc_exempts(self):
        self.assertIn('FACE_STORE.has(name)', _src('face_worker'))
        self.assertIn('ANIMAL_STORE.has(name)', _src('animal_worker'))
        s = _src('_detections_pour_retag') if any(
            isinstance(n, ast.FunctionDef) and n.name == '_detections_pour_retag'
            for n in ast.walk(ARBRE)) else SOURCE
        self.assertIn('fe is None', s)
        self.assertIn('ae is None', s)


if __name__ == '__main__':
    unittest.main(verbosity=2)
