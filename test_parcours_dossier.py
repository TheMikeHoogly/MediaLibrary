#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`_lister_dossier` : la meme reponse que l'ancienne ecriture, sans les stats.

L'horloge des routes a designe `GET /files` (31,4 s au pire le 10/09), et
`mesure_parcours_dossier.py` a montre pourquoi : sur `Photos Mike/2022`
(2 465 photos, partage SMB), `iterdir()` + `is_file()` coute **26,05 s** la ou
`os.scandir` coute **308 ms**. Un facteur 84, du au NOMBRE d'allers-retours
reseau, pas a leur latence.

Un gain de 84x sur le chemin le plus chaud ne vaut rien s'il change ce qui
s'affiche. Ces bancs comparent donc la nouvelle ecriture a L'ANCIENNE, gardee
ici telle qu'elle etait, sur des arbres construits pour ca : dossiers caches,
extensions en majuscules, fichiers non-medias, imbrication. L'ancienne
implementation est l'ORACLE -- pas ma relecture d'elle.

Le dernier banc mesure ce que le changement pretend economiser : le nombre
d'appels a `stat()`. Une optimisation qui ne se compte pas est une intention.

`server.py` n'est pas importe (cela ouvrirait photos.db et monterait cinq
magasins) : la fonction est extraite par l'arbre syntaxique et executee seule.
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

MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff',
             '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp'}


def _src(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ast.get_source_segment(SOURCE, n) or ''
    raise AssertionError(nom + ' introuvable dans server.py')


def _module():
    """`_lister_dossier` seule, avec le strict necessaire autour d'elle."""
    m = types.ModuleType('parcours')
    m.__dict__.update({'os': os, 'Path': Path, 'MEDIA_EXT': MEDIA_EXT})
    exec(_src('_lister_dossier'), m.__dict__)                      # noqa: S102
    return m


LISTER = _module()._lister_dossier


# ─────────────────────────── l'oracle : l'ancien code ───────────────────────

def _is_hidden_path(p):
    return any(part.startswith(('.', '@', '#')) for part in Path(p).parts)


def ancienne_ecriture(folder, rec=False):
    """Le code de `_serve_gallery` AVANT le 10/09, mot pour mot."""
    if rec:
        files = [f for f in folder.rglob('*')
                 if f.is_file() and f.suffix.lower() in MEDIA_EXT
                 and not _is_hidden_path(f.relative_to(folder))]
    else:
        files = [f for f in folder.iterdir()
                 if f.is_file() and f.suffix.lower() in MEDIA_EXT
                 and not f.name.startswith(('.', '@', '#'))]
    subdirs = sorted([e for e in folder.iterdir() if e.is_dir()
                      and not e.name.startswith(('.', '@', '#'))],
                     key=lambda x: x.name.lower())
    return files, subdirs


def batir(racine, arbre):
    """`{'a/b.jpg': None, 'c': {}}` -> un vrai arbre de fichiers vides."""
    for chemin in arbre:
        p = racine / chemin
        if chemin.endswith('/'):
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'')


class Arbre(unittest.TestCase):
    """Chaque banc batit son arbre puis compare les DEUX ecritures."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def comparer(self, rec=False):
        af, asd = ancienne_ecriture(self.d, rec)
        nf, nsd = LISTER(self.d, rec)
        self.assertEqual(sorted(str(x) for x in af), sorted(str(x) for x in nf),
                         'les fichiers different')
        # L'ORDRE des sous-dossiers compte : c'est la barre de navigation.
        self.assertEqual([x.name for x in asd], [x.name for x in nsd],
                         'les sous-dossiers different (contenu ou ordre)')
        return nf, nsd


class LesFichiersDUnDossier(Arbre):

    def test_un_dossier_ordinaire(self):
        batir(self.d, ['a.jpg', 'b.png', 'c.mp4', 'notes.txt', 'sousA/',
                       'sousB/'])
        f, s = self.comparer()
        self.assertEqual(len(f), 3)
        self.assertEqual([x.name for x in s], ['sousA', 'sousB'])

    def test_un_dossier_vide(self):
        f, s = self.comparer()
        self.assertEqual((f, s), ([], []))

    def test_les_extensions_en_majuscules_comptent(self):
        """Un appareil photo ecrit `DSC_0001.JPG`. Une comparaison sensible a
        la casse effacerait un tiers du fonds de l'affichage."""
        batir(self.d, ['A.JPG', 'B.Jpeg', 'C.MOV'])
        f, _s = self.comparer()
        self.assertEqual(len(f), 3)

    def test_ce_qui_n_est_pas_un_media_reste_dehors(self):
        batir(self.d, ['a.jpg', 'lisezmoi.txt', 'base.db', 'x.json',
                       'y.jpg_original'])
        f, _s = self.comparer()
        self.assertEqual([x.name for x in f], ['a.jpg'])

    def test_un_fichier_sans_extension(self):
        batir(self.d, ['a.jpg', 'LISEZMOI'])
        f, _s = self.comparer()
        self.assertEqual([x.name for x in f], ['a.jpg'])


class LesDossiersCaches(Arbre):
    """`.thumbs`, `@eaDir` (Synology) et `#recycle` sont sur CE NAS."""

    def test_les_trois_prefixes_sont_ecartes(self):
        batir(self.d, ['vu.jpg', '.thumbs/', '@eaDir/', '#recycle/'])
        f, s = self.comparer()
        self.assertEqual([x.name for x in f], ['vu.jpg'])
        self.assertEqual(s, [])

    def test_un_fichier_cache_est_ecarte(self):
        batir(self.d, ['vu.jpg', '.cache.jpg', '@rien.jpg', '#tmp.jpg'])
        f, _s = self.comparer()
        self.assertEqual([x.name for x in f], ['vu.jpg'])

    def test_recursif_ne_descend_PAS_dans_un_dossier_cache(self):
        """Le gain n'est pas seulement d'eviter un stat : `@eaDir` de Synology
        contient une vignette par photo du dossier. L'ancienne ecriture le
        parcourait ENTIEREMENT avant de tout jeter."""
        batir(self.d, ['vu.jpg', '@eaDir/SYNOPHOTO_THUMB_M.jpg',
                       '@eaDir/SYNOPHOTO_THUMB_XL.jpg', '.thumbs/t.png'])
        f, _s = self.comparer(rec=True)
        self.assertEqual([x.name for x in f], ['vu.jpg'])


class LeModeRecursif(Arbre):

    def test_les_sous_dossiers_remontent(self):
        batir(self.d, ['a.jpg', '2020/b.jpg', '2020/c.txt',
                       '2021/ete/d.png', '2021/ete/@eaDir/e.jpg'])
        f, s = self.comparer(rec=True)
        self.assertEqual(sorted(x.name for x in f), ['a.jpg', 'b.jpg', 'd.png'])
        # Les sous-dossiers restent les enfants IMMEDIATS : c'est la barre de
        # navigation, pas l'arbre entier.
        self.assertEqual([x.name for x in s], ['2020', '2021'])

    def test_le_chemin_reste_relatif_au_dossier_demande(self):
        """`_serve_gallery` affiche `f.relative_to(folder)`. Un chemin qui ne
        descend pas du dossier ferait tomber la page entiere."""
        batir(self.d, ['2021/ete/d.png'])
        f, _s = LISTER(self.d, rec=True)
        self.assertEqual([str(x.relative_to(self.d).as_posix()) for x in f],
                         ['2021/ete/d.png'])

    def test_profondeur_de_trois_niveaux(self):
        batir(self.d, ['a/b/c/d.jpg', 'a/b/e.jpg', 'a/f.jpg'])
        f, _s = self.comparer(rec=True)
        self.assertEqual(len(f), 3)


class LOrdreDesSousDossiers(Arbre):

    def test_le_tri_ignore_la_casse(self):
        """`['Ete', 'automne', 'Hiver']` trie sur les octets donnerait les
        majuscules d'abord — la barre de navigation deviendrait illisible."""
        batir(self.d, ['automne/', 'Ete/', 'hiver/', 'Bapteme/'])
        _f, s = self.comparer()
        self.assertEqual([x.name for x in s],
                         ['automne', 'Bapteme', 'Ete', 'hiver'])


class CeQueLeChangementEconomise(Arbre):
    """Compter les allers-retours, pas les croire."""

    def _compter_stats(self, appel):
        n = {'v': 0}
        vrai_stat = os.stat

        def compte(*a, **k):
            n['v'] += 1
            return vrai_stat(*a, **k)

        os.stat = compte
        try:
            appel()
        finally:
            os.stat = vrai_stat
        return n['v']

    def test_la_nouvelle_ecriture_appelle_beaucoup_moins_stat(self):
        batir(self.d, [f'IMG_{i:04d}.jpg' for i in range(120)] + ['s1/', 's2/'])
        vieux = self._compter_stats(lambda: ancienne_ecriture(self.d))
        neuf = self._compter_stats(lambda: LISTER(self.d))
        # Sur un partage SMB, chacun de ces appels est un aller-retour reseau.
        self.assertGreater(vieux, 100,
                           "l'ancienne ecriture devrait payer un stat par entree")
        self.assertLess(neuf, vieux / 10,
                        f'gain insuffisant : {vieux} -> {neuf} appels')

    def test_meme_economie_en_recursif(self):
        batir(self.d, [f'{a}/IMG_{i:03d}.jpg'
                       for a in ('2020', '2021') for i in range(60)])
        vieux = self._compter_stats(lambda: ancienne_ecriture(self.d, True))
        neuf = self._compter_stats(lambda: LISTER(self.d, True))
        self.assertGreater(vieux, 100)
        self.assertLess(neuf, vieux / 10,
                        f'gain insuffisant : {vieux} -> {neuf} appels')


def deux_passes(dossier, rec=False):
    """L'ecriture du 10/09 au 12/09 : `os.walk` PUIS un second `os.scandir`
    pour les sous-dossiers. Oracle du point mesure le 12/09 -- pas ma
    relecture d'elle."""
    fichiers, sous = [], []
    if rec:
        for racine, dirs, noms in os.walk(dossier):
            dirs[:] = [d for d in dirs if not d.startswith(('.', '@', '#'))]
            rp = Path(racine)
            for n in noms:
                if n.startswith(('.', '@', '#')):
                    continue
                if os.path.splitext(n)[1].lower() in MEDIA_EXT:
                    fichiers.append(rp / n)
        with os.scandir(dossier) as it:
            for e in it:
                if not e.name.startswith(('.', '@', '#')) and e.is_dir():
                    sous.append(Path(e.path))
    else:
        with os.scandir(dossier) as it:
            for e in it:
                if e.name.startswith(('.', '@', '#')):
                    continue
                if e.is_dir():
                    sous.append(Path(e.path))
                elif (e.is_file()
                      and os.path.splitext(e.name)[1].lower() in MEDIA_EXT):
                    fichiers.append(Path(e.path))
    sous.sort(key=lambda x: x.name.lower())
    return fichiers, sous


class LeDossierDeTeteNEstEnumereQuUneFois(Arbre):
    """Une enumeration SMB de 2 519 entrees coute 368 ms. La deuxieme ne
    rendait rien que la premiere n'ait deja vu -- et une optimisation qui ne
    se compte pas est une intention (12/09)."""

    def _compter_enum(self, cible, appel):
        """Combien de fois CE dossier-la est enumere."""
        n = {'v': 0}
        vrai = os.scandir
        vise = os.path.normcase(os.path.abspath(str(cible)))

        def compte(chemin='.', *a, **k):
            if os.path.normcase(os.path.abspath(str(chemin))) == vise:
                n['v'] += 1
            return vrai(chemin, *a, **k)

        os.scandir = compte
        try:
            appel()
        finally:
            os.scandir = vrai
        return n['v']

    def test_deux_passes_hier_une_seule_aujourd_hui(self):
        batir(self.d, ['IMG_1.jpg', 'IMG_2.jpg', 'ete/IMG_3.jpg', 'hiver/'])
        vieux = self._compter_enum(self.d, lambda: deux_passes(self.d, True))
        neuf = self._compter_enum(self.d, lambda: LISTER(self.d, True))
        self.assertEqual(vieux, 2, "l'ecriture d'avant enumerait deux fois")
        self.assertEqual(neuf, 1, 'le dossier de tete doit etre lu UNE fois')

    def test_et_elle_rend_exactement_la_meme_chose(self):
        batir(self.d, ['IMG_1.jpg', 'a/IMG_2.JPG', 'a/b/IMG_3.png',
                       '.cache/IMG_4.jpg', '@eaDir/', 'Zoo/', 'note.txt'])
        vf, vs = deux_passes(self.d, True)
        nf, ns = LISTER(self.d, True)
        self.assertEqual(sorted(str(x) for x in nf),
                         sorted(str(x) for x in vf))
        self.assertEqual([x.name for x in ns], [x.name for x in vs])

    def test_le_mode_NON_recursif_n_a_pas_bouge(self):
        batir(self.d, ['IMG_1.jpg', 'a/', 'note.txt'])
        self.assertEqual(self._compter_enum(self.d,
                                            lambda: LISTER(self.d, False)), 1)

    def test_un_dossier_illisible_leve_encore(self):
        """`os.walk` avale l'erreur et ne rend AUCUN tuple : sans le repli,
        la page dirait « aucune photo » la ou elle doit dire pourquoi."""
        manquant = self.d / 'ce-dossier-n-existe-pas'
        with self.assertRaises(OSError):
            LISTER(manquant, True)
        with self.assertRaises(OSError):
            LISTER(manquant, False)


class LaFonctionEstBienCELLEQueLeServeurAPPELLE(unittest.TestCase):
    """Un banc qui mesure une fonction que la route n'appelle plus mesure le
    vide. Le 10/09, une correction de cache posee sur deux chemins d'ecriture
    sur trois est passee verte pour exactement cette raison."""

    def _appels(self, nom):
        for n in ast.walk(ARBRE):
            if isinstance(n, ast.FunctionDef) and n.name == nom:
                return {c.func.id for c in ast.walk(n)
                        if isinstance(c, ast.Call)
                        and isinstance(c.func, ast.Name)}
        self.fail(nom + ' introuvable')

    def test_serve_gallery_appelle_lister_dossier(self):
        """La CHAINE, pas un nom : depuis le cache du 12/09 (§ 3.16), la page
        appelle `_lister_dossier_frais`, qui appelle `_lister_dossier`. Ce
        banc mesure `_lister_dossier` : si l'un des deux maillons saute, il
        mesure le vide. La version d'avant n'exigeait que le nom direct —
        elle est donc tombee ROUGE le jour du cache, et rien ne la lancait
        (§ 3.18)."""
        self.assertIn('_lister_dossier_frais', self._appels('_serve_gallery'))
        self.assertIn('_lister_dossier', self._appels('_lister_dossier_frais'))

    def test_plus_aucun_rglob_ni_iterdir_dans_serve_gallery(self):
        """La correction ne vaut que si l'ancien chemin a DISPARU. Le laisser
        a cote, meme mort, laisserait la prochaine session croire aux deux."""
        for n in ast.walk(ARBRE):
            if isinstance(n, ast.FunctionDef) and n.name == '_serve_gallery':
                src = ast.get_source_segment(SOURCE, n) or ''
                self.assertNotIn('rglob', src)
                self.assertNotIn('.iterdir()', src)
                return
        self.fail('_serve_gallery introuvable')


if __name__ == '__main__':
    unittest.main(verbosity=2)
