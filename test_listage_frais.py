#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le cache de listage : il VERIFIE la fraicheur, il ne la PARIE pas.

`parcours` est la phase la plus lourde de `GET /files` une fois les redites
enlevees : 350 ms d'attente SMB pour relire un dossier qui, neuf fois sur
dix, n'a pas bouge. Un dossier voit sa date de modification changer des
qu'une entree y est ajoutee, retiree ou renommee -- pas quand le CONTENU d'un
fichier change. MESURE le 12/09 : le detecteur coute 6,8 ms contre 343 sur
`Photos Mike/2022` (2 dossiers), 130,9 contre 1 467 sur `Photos Papa`
(271 dossiers), soit 0,48 ms par dossier.

Ces bancs travaillent sur un VRAI arbre de fichiers, pas sur des dates
simulees : c'est le systeme de fichiers qui doit prouver la regle, pas ma
relecture d'elle. Ils comptent aussi les appels a `_lister_dossier` -- une
optimisation qui ne se compte pas est une intention.

`server.py` n'est pas importe : les fonctions sont extraites par l'arbre
syntaxique.
"""

import ast
import os
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
LIGNES = SOURCE.splitlines()

MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff',
             '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp'}

FONCTIONS = ('_lister_dossier', '_listage_intact', '_lister_dossier_frais')
CONSTANTES = ('_LISTAGE', '_LISTAGE_LOCK', 'LISTAGE_MAX', 'LISTAGE_TTL_S',
              'LISTAGE_PART_MAX')


def _module():
    """Les trois fonctions du listage et LEURS constantes, telles quelles."""
    m = types.ModuleType('listage')
    m.__dict__.update({'os': os, 'time': time, 'threading': threading,
                       'Path': Path, 'MEDIA_EXT': MEDIA_EXT})
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name in FONCTIONS:
            exec('\n'.join(LIGNES[n.lineno - 1:n.end_lineno]),             # noqa: S102
                 m.__dict__)
        elif isinstance(n, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id in CONSTANTES
                for c in n.targets):
            exec('\n'.join(LIGNES[n.lineno - 1:n.end_lineno]),             # noqa: S102
                 m.__dict__)
    manque = [x for x in FONCTIONS + CONSTANTES if x not in m.__dict__]
    if manque:
        raise AssertionError('introuvable dans server.py : %r' % manque)
    return m


def batir(base, chemins):
    for c in chemins:
        p = base / c
        if c.endswith('/'):
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'x')


class Arbre(unittest.TestCase):
    """Un vrai dossier, un module neuf : aucun banc n'herite du cache d'un
    autre."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.m = _module()
        self.m._LISTAGE.clear()
        self.appels = {'n': 0}
        vrai = self.m.__dict__['_lister_dossier']

        def compte(dossier, rec=False, dossiers_vus=None):
            self.appels['n'] += 1
            return vrai(dossier, rec, dossiers_vus)

        self.m.__dict__['_lister_dossier'] = compte
        self.frais = self.m._lister_dossier_frais

    def tearDown(self):
        self.tmp.cleanup()

    def noms(self, res):
        f, s = res
        return (sorted(x.name for x in f), sorted(x.name for x in s))

    def pause(self):
        """Le temps que le systeme de fichiers distingue deux instants."""
        time.sleep(0.02)


class UnDossierQuiNAPasBougeNEstPasRelu(Arbre):

    def test_le_second_appel_ne_relit_pas(self):
        batir(self.d, ['a.jpg', 'b.jpg', 'sous/'])
        un = self.frais(self.d)
        self.assertEqual(self.appels['n'], 1)
        deux = self.frais(self.d)
        self.assertEqual(self.appels['n'], 1, 'le dossier a ete relu pour rien')
        self.assertEqual(self.noms(deux), self.noms(un))

    def test_ecrire_DANS_un_fichier_ne_change_pas_le_listage(self):
        """C'est la propriete qui rend le cache utile : le tagueur reecrit les
        XMP sans changer la liste des entrees."""
        batir(self.d, ['a.jpg'])
        un = self.frais(self.d)
        self.pause()
        (self.d / 'a.jpg').write_bytes(b'beaucoup plus de contenu qu avant')
        deux = self.frais(self.d)
        self.assertEqual(self.appels['n'], 1)
        self.assertEqual(self.noms(deux), self.noms(un))


class CeQuiFaitTOMBERLeCache(Arbre):

    def test_un_fichier_AJOUTE(self):
        batir(self.d, ['a.jpg'])
        self.frais(self.d)
        self.pause()
        batir(self.d, ['b.jpg'])
        f, _s = self.frais(self.d)
        self.assertEqual(self.appels['n'], 2, 'le dossier n a pas ete relu')
        self.assertEqual(sorted(x.name for x in f), ['a.jpg', 'b.jpg'])

    def test_un_fichier_EFFACE(self):
        batir(self.d, ['a.jpg', 'b.jpg'])
        self.frais(self.d)
        self.pause()
        (self.d / 'b.jpg').unlink()
        f, _s = self.frais(self.d)
        self.assertEqual(self.appels['n'], 2)
        self.assertEqual(sorted(x.name for x in f), ['a.jpg'])

    def test_un_fichier_RENOMME(self):
        batir(self.d, ['a.jpg'])
        self.frais(self.d)
        self.pause()
        (self.d / 'a.jpg').rename(self.d / 'z.jpg')
        f, _s = self.frais(self.d)
        self.assertEqual(self.appels['n'], 2)
        self.assertEqual(sorted(x.name for x in f), ['z.jpg'])

    def test_un_fichier_ajoute_dans_un_SOUS_dossier(self):
        """Le piege : la date du dossier de tete ne bouge PAS quand une
        entree change dans un sous-dossier. Surveiller la tete seule
        servirait un listage faux jusqu'au filet des 300 s."""
        batir(self.d, ['a.jpg', 'sous/b.jpg'])
        self.frais(self.d, True)
        self.pause()
        batir(self.d, ['sous/c.jpg'])
        f, _s = self.frais(self.d, True)
        self.assertEqual(self.appels['n'], 2,
                         'un sous-dossier modifie n a pas fait tomber le cache')
        self.assertEqual(sorted(x.name for x in f), ['a.jpg', 'b.jpg', 'c.jpg'])

    def test_un_dossier_CREE(self):
        batir(self.d, ['a.jpg'])
        self.frais(self.d)
        self.pause()
        (self.d / 'neuf').mkdir()
        _f, s = self.frais(self.d)
        self.assertEqual(self.appels['n'], 2)
        self.assertEqual([x.name for x in s], ['neuf'])


class LesDeuxModesNeSeMelangentPas(Arbre):

    def test_recursif_et_non_recursif_ont_leur_entree(self):
        batir(self.d, ['a.jpg', 'sous/b.jpg'])
        plat, _ = self.noms(self.frais(self.d, False))
        prof, _ = self.noms(self.frais(self.d, True))
        self.assertEqual(plat, ['a.jpg'])
        self.assertEqual(prof, ['a.jpg', 'b.jpg'])
        self.assertEqual(self.appels['n'], 2)
        self.frais(self.d, False)
        self.frais(self.d, True)
        self.assertEqual(self.appels['n'], 2, 'une entree a ecrase l autre')


class LesGardeFous(Arbre):

    def test_le_cache_est_BORNE(self):
        """Chaque entree porte ses `Path` : sans borne, naviguer dans cent
        dossiers garderait cent listages en memoire."""
        for i in range(self.m.LISTAGE_MAX + 3):
            d = self.d / ('d%02d' % i)
            d.mkdir()
            batir(d, ['a.jpg'])
            self.frais(d)
        self.assertLessEqual(len(self.m._LISTAGE), self.m.LISTAGE_MAX)

    def test_le_filet_des_300_s(self):
        """Le detecteur peut manquer une ecriture tombee PENDANT le parcours
        (ou dans la meme seconde, la ou les dates n'ont qu'une seconde de
        resolution). Le TTL est le filet, pas le mecanisme."""
        batir(self.d, ['a.jpg'])
        self.frais(self.d)
        self.assertEqual(self.appels['n'], 1)
        for e in self.m._LISTAGE.values():
            e['at'] -= self.m.LISTAGE_TTL_S + 1
        self.frais(self.d)
        self.assertEqual(self.appels['n'], 2, 'le filet n a pas joue')

    def test_un_arbre_trop_large_cesse_d_etre_cache(self):
        """Verifier 1 000 dossiers coute plus que relire un petit arbre : la
        regle se MESURE, elle ne devine pas un nombre maximum."""
        batir(self.d, ['a.jpg'])
        self.frais(self.d)
        for e in self.m._LISTAGE.values():
            e['parcours_ms'] = 0.0      # tout depassera la part maximum
        self.frais(self.d)
        self.assertEqual(len(self.m._LISTAGE), 0,
                         'le dossier trop cher a verifier reste cache')

    def test_un_dossier_disparu_ne_reste_pas_en_cache(self):
        d = self.d / 'temporaire'
        d.mkdir()
        batir(d, ['a.jpg'])
        self.frais(d)
        for x in d.iterdir():
            x.unlink()
        d.rmdir()
        with self.assertRaises(OSError):
            self.frais(d)


class LesDossiersSURVEILLESSontCEUXQuOnALUS(Arbre):

    def test_non_recursif_le_dossier_seul(self):
        batir(self.d, ['a.jpg', 'sous/b.jpg'])
        self.frais(self.d, False)
        cle = (str(self.d), False)
        self.assertEqual(list(self.m._LISTAGE[cle]['dates']), [str(self.d)])

    def test_recursif_tous_les_dossiers_lus_et_AUCUN_elague(self):
        batir(self.d, ['a.jpg', 'sous/b.jpg', 'sous/encore/c.jpg',
                       '.cache/d.jpg', '@eaDir/e.jpg'])
        self.frais(self.d, True)
        cle = (str(self.d), True)
        vus = sorted(self.m._LISTAGE[cle]['dates'])
        attendu = sorted([str(self.d), str(self.d / 'sous'),
                          str(self.d / 'sous' / 'encore')])
        self.assertEqual(vus, attendu,
                         'un dossier elague est surveille, ou un dossier lu '
                         'ne l est pas')


if __name__ == '__main__':
    unittest.main(verbosity=2)
