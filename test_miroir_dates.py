#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Une SEULE regle lit la date dans un nom de fichier — et elle est memoisee.

Ce que ce fichier protege, et pourquoi il existe (12/09)
--------------------------------------------------------
`server._fname_time` et `faits_vue.epoch_du_nom` faisaient la meme lecture,
chacune avec sa propre expression reguliere. Les docstrings les declaraient
miroirs ; personne ne les avait comparees. `mesure_miroir_dates.py` l'a fait :
**0 desaccord sur les 44 966 fichiers du fonds**, mais une divergence REELLE
sur les cas limites — une heure impossible (<< 250000 >>) partait dans
`mktime`, qui NORMALISE et faisait basculer au JOUR SUIVANT d'un cote,
pendant que l'autre la rejetait et retombait a midi.

`_fname_time` DELEGUE desormais. Trois choses a tenir, et ce banc les tient :

1. **Il n'y a plus qu'un lecteur.** Sur l'ARBRE : `_fname_time` ne contient
   plus ni `re.search`, ni `mktime` — sinon un second lecteur est revenu, et
   la question << lequel a raison ? >> avec lui.
2. **C'est la regle STRICTE qui a gagne.** Une heure impossible ne doit JAMAIS
   devenir un autre jour. Le cas est nomme, pas seulement couvert.
3. **La memoire ne change pas la reponse**, et elle porte sur le nom NU —
   deux copies d'une photo dans deux dossiers, c'est la meme date de nom.

Le banc lit `server.py` par l'arbre syntaxique et n'importe PAS le serveur :
il tire torch et insightface, un test n'a pas a payer ca.
"""
import ast
import io
import os
import time
import unittest

import faits_vue

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.py')

with io.open(SERVER, encoding='utf-8') as _f:
    SOURCE = _f.read()
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable dans server.py')


def _charge(nom):
    """La fonction de prod, executee dans un espace minimal."""
    espace = {'faits_vue': faits_vue, 'time': time}
    exec(compile(ast.Module(body=[_noeud(nom)], type_ignores=[]),
                 SERVER, 'exec'), espace)
    return espace[nom]


FNAME_TIME = _charge('_fname_time')


class IlNYAPlusQuUnLecteur(unittest.TestCase):

    def test_fname_time_delegue_et_ne_relit_plus_rien(self):
        """Sur les APPELS de l'arbre, pas sur le texte.

        La premiere ecriture de ce banc cherchait `mktime` dans
        `ast.unparse(...)` — et tombait ROUGE sur la DOCSTRING, qui raconte
        justement l'ancienne regle. C'est la faute du § 3.18, refaite le jour
        meme : un banc qui lit du texte mesure du texte."""
        corps = _noeud('_fname_time').body
        # La docstring dehors : elle a le droit de nommer ce qu'elle raconte.
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)):
            corps = corps[1:]
        appels = set()
        for n in corps:
            for c in ast.walk(n):
                if isinstance(c, ast.Call):
                    appels.add(ast.unparse(c.func))
        self.assertEqual(appels, {'faits_vue.epoch_du_nom'},
                         'un SECOND lecteur est revenu dans _fname_time')

    def test_les_deux_portes_rendent_la_meme_chose(self):
        for nom in ('20181211_230148.jpg', 'IMG_20181227.jpg', '20180101.jpg',
                    'rien.jpg', '19890704_101010.jpg', '2018-01-01 12.00.00.jpg',
                    '20180101_250000.jpg', '20180101_126100.jpg',
                    'IMG_1998.jpg', ''):
            self.assertEqual(FNAME_TIME(nom), faits_vue.epoch_du_nom(nom), nom)

    def test_un_seul_appel_a_mktime_dans_le_projet_pour_cette_regle(self):
        """`_fname_time` etait le second. Qu'il le redevienne doit se VOIR."""
        self.assertEqual(SOURCE.count('def _fname_time'), 1)


class LaRegleSTRICTEAGagne(unittest.TestCase):
    """Une heure IMPOSSIBLE ne devient jamais un autre JOUR."""

    def _jour(self, epoch):
        t = time.localtime(epoch)
        return (t.tm_mon, t.tm_mday)

    def test_une_heure_impossible_retombe_a_midi_et_garde_son_jour(self):
        sain = FNAME_TIME('20180101_120000.jpg')
        for casse in ('20180101_250000.jpg', '20180101_126100.jpg',
                      '20180101_120061.jpg', '20180101_999999.jpg'):
            v = FNAME_TIME(casse)
            self.assertIsNotNone(v, casse)
            self.assertEqual(self._jour(v), self._jour(sain), casse)
            self.assertEqual(v, sain, casse + ' : midi, comme sans heure')

    def test_une_heure_VALIDE_est_toujours_lue(self):
        """La regle stricte ne doit pas jeter l'heure du cas ordinaire."""
        midi = FNAME_TIME('20180101.jpg')
        self.assertNotEqual(FNAME_TIME('20180101_093012.jpg'), midi)
        self.assertEqual(self._jour(FNAME_TIME('20180101_235959.jpg')), (1, 1))

    def test_la_DATE_invalide_reste_refusee(self):
        """Le garde-fou d'AVANT ne doit pas avoir disparu avec le reste."""
        for nom in ('20181301_120000.jpg', '20180132_120000.jpg',
                    '19890704_101010.jpg'):
            self.assertIsNone(FNAME_TIME(nom), nom)


class LaMemoireNeChangePasLaReponse(unittest.TestCase):

    def test_deux_fois_le_meme_nom_rend_deux_fois_la_meme_chose(self):
        a = faits_vue.epoch_du_nom('20200304_101112.jpg')
        b = faits_vue.epoch_du_nom('20200304_101112.jpg')
        self.assertEqual(a, b)

    def test_la_memoire_porte_sur_le_nom_NU(self):
        """Deux copies dans deux dossiers : meme nom, meme date — et UN seul
        calcul. C'est la raison de couper la cle avant de memoiser."""
        faits_vue._epoch_du_nom_nu.cache_clear()
        a = faits_vue.epoch_du_nom(r'\\NAS\Photos\2020\20200304_101112.jpg')
        b = faits_vue.epoch_du_nom('Album/autre/20200304_101112.jpg')
        self.assertEqual(a, b)
        self.assertEqual(faits_vue._epoch_du_nom_nu.cache_info().misses, 1)
        self.assertEqual(faits_vue._epoch_du_nom_nu.cache_info().hits, 1)

    def test_les_DEUX_barres_coupent(self):
        ref = faits_vue.epoch_du_nom('20200304_101112.jpg')
        self.assertEqual(faits_vue.epoch_du_nom(r'A\B\20200304_101112.jpg'), ref)
        self.assertEqual(faits_vue.epoch_du_nom('A/B/20200304_101112.jpg'), ref)
        self.assertEqual(faits_vue.epoch_du_nom(r'A\B/20200304_101112.jpg'), ref)

    def test_la_memoire_est_BORNEE(self):
        """Un cache sans borne sur 44 605 noms est une fuite qui attend son
        jour. La borne doit tenir le fonds ENTIER, sinon elle ne sert a rien."""
        info = faits_vue._epoch_du_nom_nu.cache_info()
        self.assertIsNotNone(info.maxsize)
        self.assertGreaterEqual(info.maxsize, 44605)

    def test_un_nom_SANS_date_est_memoise_aussi(self):
        """11 503 fichiers du fonds n'ont aucune date dans leur nom : si le
        cache ne gardait pas les None, ils repayeraient a chaque fois."""
        faits_vue._epoch_du_nom_nu.cache_clear()
        self.assertIsNone(faits_vue.epoch_du_nom('rien_du_tout.jpg'))
        self.assertIsNone(faits_vue.epoch_du_nom('rien_du_tout.jpg'))
        self.assertEqual(faits_vue._epoch_du_nom_nu.cache_info().misses, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
