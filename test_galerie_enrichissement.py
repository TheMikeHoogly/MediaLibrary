#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La boucle de `_serve_gallery` : moins de travail, la MEME page.

L'horloge de phases du 12/09 dit ou part le temps d'un `GET /files` de 2 519
photos, une fois le parcours corrige. Deux redites y pesaient :

  `enrichir.dossier` (69 ms) -- `_folder_link_for_key` etait appele une fois
  PAR PHOTO alors que tout, chez elle, passe par `parent_orig` : le dossier
  du chemin. 2 519 appels pour deux reponses.

  `enrichir.dates` (108 ms) -- `_best_time` et `_jour_de` demandaient chacun
  leur date PRECISE, sur le meme couple (cle, entree). `_epoch_precis` lit
  l'EXIF garde en index, le nom du fichier et le garde-fou de la date de
  scan : deux fois par photo la ou une suffit.

Une optimisation qui change ce qui s'affiche n'est pas une optimisation. Ces
bancs prouvent l'identite des deux, et surtout le point non evident : la cle
de memo du lien de dossier ne peut pas confondre deux dossiers differents.

`server.py` n'est pas importe (cela ouvrirait photos.db et monterait cinq
magasins) : les fonctions sont extraites par l'arbre syntaxique.
"""

import ast
import types
import unittest
import urllib.parse
from functools import lru_cache
from pathlib import Path, PurePath

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


# La source de CHAQUE fonction, decoupee UNE fois. `ast.get_source_segment`
# redecoupe les 755 Ko a chaque appel : appele par fonction sur un arbre de
# 16 000 lignes, il faisait durer ce banc 98 secondes. Un banc lent est un
# banc qu'on cesse de lancer.
_LIGNES = SOURCE.splitlines()
SOURCES = {}
for _n in ast.walk(ARBRE):
    if isinstance(_n, ast.FunctionDef):
        SOURCES.setdefault(
            _n.name, '\n'.join(_LIGNES[_n.lineno - 1:_n.end_lineno]))
FONCTIONS = [(_n.name, '\n'.join(_LIGNES[_n.lineno - 1:_n.end_lineno]))
             for _n in ast.walk(ARBRE) if isinstance(_n, ast.FunctionDef)]


def _src(nom):
    try:
        return SOURCES[nom]
    except KeyError:
        raise AssertionError(nom + ' introuvable dans server.py')


def _source_de(nom):
    return _src(nom)


# Les racines de reference : un NAS, comme chez Mike, et un nom qui contient
# le nom de l'autre (piege classique d'un startswith sans separateur).
RACINES = [('Photos Mike', Path(r'\\NAS-Bremblens\home\Photos\Photos Mike')),
           ('Photos Mike Ancien',
            Path(r'\\NAS-Bremblens\home\Photos\Photos Mike Ancien')),
           ('Photos Papa', Path(r'\\NAS-Bremblens\home\Photos\Photos Papa'))]


def _module():
    """`_folder_link_for_key` et la normalisation de cle, seules."""
    m = types.ModuleType('galerie')
    m.__dict__.update({'Path': Path, 'PurePath': PurePath,
                       'lru_cache': lru_cache, 'urllib': urllib,
                       'PKEY_MEMO_MAX': 1 << 17,
                       'media_roots': lambda: RACINES})
    for nom in ('_pkey_chaine', '_pkey', '_folder_link_for_key',
                '_lien_dossier_memo'):
        exec(_src(nom), m.__dict__)                                # noqa: S102
    return m


M = _module()
LIEN = M._folder_link_for_key
MEMO = M._lien_dossier_memo        # la regle testee est CELLE du serveur


# Un corpus de chemins tordus : separateurs melanges, doublons, un "." 
# intermediaire, casse differente de la racine, racine dont le nom est le
# prefixe d'une autre, fichier a la racine d'une racine, nom nu.
CORPUS = [
    r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\IMG_1.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\IMG_2.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\Nikola\IMG_3.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Mike\IMG_4.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Mike Ancien\2022\IMG_5.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Papa\1984\1984_09-3\IMG_6.jpg',
    r'\\nas-bremblens\home\photos\photos mike\2022\IMG_7.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\.\IMG_8.jpg',
    r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\\IMG_9.jpg',
    '/mnt/autre/2019/IMG_10.jpg',
    r'C:\Prog\Claude\MediaLibrary\Uploads\Album\IMG_11.jpg',
    'IMG_12.jpg',
]


class LesQuatreBranchesPassentParLaMemePorte(unittest.TestCase):
    """Un angle mort a rarement une seule porte (CLAUDE.md n. 8).
    `_serve_gallery` remplit `file_data` par QUATRE chemins -- navigation,
    tags, recherche/semblables, meme jour. Corriger le premier et se declarer
    content laisserait les trois autres payer deux fois."""

    def setUp(self):
        self.src = _source_de('_serve_gallery')

    def test_plus_aucun_appel_direct_au_lien_de_dossier(self):
        self.assertEqual(self.src.count('_folder_link_for_key('), 0,
                         'une branche appelle encore le lien sans memo')
        self.assertEqual(self.src.count('_lien_dossier_memo('), 4,
                         'les quatre branches doivent passer par le memo')

    def test_plus_aucune_date_precise_demandee_deux_fois(self):
        """Tant qu'une branche appelle `_best_time` ou `_jour_de`, elle relit
        l'EXIF et le nom de fichier une seconde fois pour rien."""
        self.assertEqual(self.src.count('_best_time('), 0)
        self.assertEqual(self.src.count('_jour_de('), 0)
        self.assertEqual(self.src.count('_epoch_precis('), 4)

    def test_chaque_memo_est_neuf_a_chaque_page(self):
        """Un memo qui survivrait a la requete survivrait a un renommage de
        racine : les quatre dictionnaires sont crees DANS la fonction."""
        self.assertEqual(self.src.count('_liens_dossier = {}'), 1)
        self.assertEqual(self.src.count('_liens = {}'), 3)


class LaCleDeMemoNeConfondJamaisDeuxDossiers(unittest.TestCase):
    """Le seul vrai risque du memo : deux chemins de dossiers DIFFERENTS qui
    partagent la cle. L'inverse -- deux cles pour un meme dossier -- ne coute
    qu'un calcul de plus."""

    def test_meme_cle_donc_meme_reponse(self):
        """Le memo est interroge chemin par chemin, dans l'ordre de la page :
        s'il confondait deux dossiers, la 2e photo recevrait le lien de la
        1re. On compare donc CHAQUE reponse memoisee a la reponse directe."""
        memo = {}
        for c in CORPUS:
            self.assertEqual(MEMO(c, RACINES, memo), LIEN(c, RACINES),
                             'le memo confond un dossier sur %r' % c)

    def test_la_boucle_memoisee_rend_exactement_la_meme_page(self):
        """L'oracle : un appel par photo, comme avant le 12/09. Le corpus est
        parcouru DEUX fois -- une page melange les dossiers, et un memo qui ne
        se trompe qu'au second passage se trompe quand meme."""
        ordre = CORPUS + CORPUS[::-1]
        sans_memo = [LIEN(c, RACINES) for c in ordre]
        memo = {}
        avec = [MEMO(c, RACINES, memo) for c in ordre]
        self.assertEqual(avec, sans_memo)

    def test_le_memo_sert_vraiment(self):
        """Une optimisation qui ne se compte pas est une intention : on
        compte les appels REELS au calcul, memo en place."""
        n = {'v': 0}
        vrai = M.__dict__['_folder_link_for_key']

        def compte(c, roots=None):
            n['v'] += 1
            return vrai(c, roots)

        M.__dict__['_folder_link_for_key'] = compte
        try:
            memo = {}
            for c in CORPUS:
                MEMO(c, RACINES, memo)
        finally:
            M.__dict__['_folder_link_for_key'] = vrai
        self.assertEqual(len(CORPUS), 12)
        self.assertLess(n['v'], len(CORPUS),
                        'le memo ne regroupe rien : %d appels pour %d photos'
                        % (n['v'], len(CORPUS)))

    def test_deux_racines_dont_l_une_prefixe_l_autre(self):
        """`Photos Mike` est un prefixe de `Photos Mike Ancien` : un
        startswith sans separateur les confondrait, et la photo de l'une
        s'afficherait sous le nom de l'autre."""
        a, _ = LIEN(r'\\NAS-Bremblens\home\Photos\Photos Mike\2022\x.jpg',
                    RACINES)
        b, _ = LIEN(
            r'\\NAS-Bremblens\home\Photos\Photos Mike Ancien\2022\x.jpg',
            RACINES)
        self.assertEqual(a, 'Photos Mike/2022')
        self.assertEqual(b, 'Photos Mike Ancien/2022')


class UneSeuleDatePreciseParPhoto(unittest.TestCase):
    """`_best_time` et `_jour_de` gardent leurs noms et leur resultat : ils
    deleguent desormais a un point d'entree qui prend la date precise deja
    calculee. La regle n'est recopiee nulle part -- c'est ce qui se verifie
    ici, dans la source."""

    def test_best_time_delegue_et_ne_recopie_pas_la_regle(self):
        src = _source_de('_best_time')
        self.assertIn('_best_time_depuis(key, e, _epoch_precis(key, e))', src)
        self.assertNotIn('_path_year', src)

    def test_jour_de_delegue_et_ne_recopie_pas_la_regle(self):
        src = _source_de('_jour_de')
        self.assertIn('_jour_depuis(_epoch_precis(cle, entree))', src)
        self.assertNotIn('cle_jour', src)

    def test_la_suite_de_la_regle_a_un_seul_proprietaire(self):
        """`_path_year` PUIS le repli `mtime` : cette suite-la ne doit exister
        qu'a UN endroit, sinon deux galeries dateront la meme photo
        autrement. (`_assertions_pour` cite `_path_year` sans le repli mtime,
        et c'est voulu : une date fausse affirmee au modele est une graine
        d'hallucination.)"""
        porteurs = [nom for nom, src in FONCTIONS
                    if '_path_year(key)' in src and "e.get('mtime')" in src]
        self.assertEqual(porteurs, ['_best_time_depuis'],
                         'la suite de la regle est ecrite dans %r' % porteurs)


class LesDeuxDepuisRendentCEQueLesAnciensRendaient(unittest.TestCase):
    """Les deux `_depuis` executes pour de vrai, contre l'ecriture d'avant,
    sur les cas limites : date precise absente, nulle, presente."""

    def setUp(self):
        m = types.ModuleType('dates')
        journees = types.SimpleNamespace(cle_jour=lambda ep: 'J%s' % ep)
        m.__dict__.update({
            'meme_jour': journees,
            '_path_year': lambda k: 1000 if 'annee' in str(k) else 0,
            '_epoch_precis': lambda k, e: e.get('precise'),
        })
        for nom in ('_best_time', '_best_time_depuis', '_jour_de',
                    '_jour_depuis'):
            exec(_src(nom), m.__dict__)                            # noqa: S102
        self.m = m

    def cas(self):
        return [
            ('photo.jpg', {'precise': 1700000000, 'mtime': 5}),
            ('photo.jpg', {'precise': None, 'mtime': 5}),
            ('photo.jpg', {'precise': 0, 'mtime': 5}),
            ('annee/photo.jpg', {'precise': None, 'mtime': 5}),
            ('annee/photo.jpg', {'precise': 0}),
            ('photo.jpg', {}),
            ('photo.jpg', {'mtime': -1}),
        ]

    def test_une_fois_ou_deux_le_resultat_est_le_meme(self):
        for cle, e in self.cas():
            ep = self.m._epoch_precis(cle, e)
            self.assertEqual(self.m._best_time_depuis(cle, e, ep),
                             self.m._best_time(cle, e),
                             'taken differe sur %r %r' % (cle, e))
            self.assertEqual(self.m._jour_depuis(ep),
                             self.m._jour_de(cle, e),
                             'jour differe sur %r %r' % (cle, e))

    def test_une_date_precise_NULLE_ne_se_confond_pas_avec_absente(self):
        """`_best_time` teste `if precise:` et `_jour_de` `is not None` : un
        0 ne suit donc pas le meme chemin dans les deux. Le banc le fige."""
        self.assertEqual(self.m._best_time_depuis('annee/p.jpg', {}, 0), 1000)
        self.assertEqual(self.m._jour_depuis(0), 'J0')
        self.assertIsNone(self.m._jour_depuis(None))


if __name__ == '__main__':
    unittest.main(verbosity=2)
