#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`Last-Modified` sur les médias : ne pas renvoyer ce que le client a déjà (12/09).

Revenir en arrière sur une photo de 5 Mo la retéléchargeait depuis le NAS :
`_send_file` servait les octets sans jamais dire de quand ils datent. Il pose
maintenant `Last-Modified` (le `mtime`, source de vérité de tout le projet) et
répond **304** à un `If-Modified-Since` à jour.

Ce qui doit tenir, et que ce banc tient :
  1. la règle de comparaison est à la SECONDE, et ne lève sur AUCUN en-tête —
     les clients en écrivent de toutes sortes ;
  2. un **304 ne sort pas quand une PLAGE est demandée** : répondre « rien à
     renvoyer » à qui demande les octets 0-1023 d'une vidéo casserait le seek ;
  3. le cache est en `no-cache`, pas en `max-age` : nos propres écritures XMP
     changent les fichiers, et un cache muet servirait une version périmée.
"""

import ast
import email.utils
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
_LIGNES = SOURCE.splitlines(keepends=True)
_ARBRE = ast.parse(SOURCE)


def _src(nom, genre=ast.FunctionDef):
    for n in ast.walk(_ARBRE):
        if isinstance(n, genre) and n.name == nom:
            return textwrap.dedent(''.join(_LIGNES[n.lineno - 1:n.end_lineno]))
    raise AssertionError(nom + ' introuvable')


_NS = {}
exec(_src('_date_http'), _NS)                                       # noqa: S102
exec(_src('_non_modifie'), _NS)                                     # noqa: S102
date_http, non_modifie = _NS['_date_http'], _NS['_non_modifie']


class LaRegle(unittest.TestCase):
    def test_la_date_est_en_GMT_et_a_la_seconde(self):
        d = date_http(1700000000.7)
        self.assertTrue(d.endswith('GMT'), d)
        self.assertEqual(email.utils.parsedate_to_datetime(d).timestamp(), 1700000000)

    def test_meme_seconde_rien_a_renvoyer(self):
        self.assertTrue(non_modifie(date_http(1700000000.7), 1700000000.7))

    def test_le_fichier_REECRIT_repart_en_entier(self):
        """Une écriture XMP change le `mtime` : le client doit tout reprendre."""
        self.assertFalse(non_modifie(date_http(1700000000.0), 1700000001.2))

    def test_un_client_qui_a_une_version_PLUS_RECENTE(self):
        self.assertTrue(non_modifie(date_http(1700000001.0), 1699999999.0))

    def test_aucun_entete_ne_le_fait_lever(self):
        for e in (None, '', 'n importe quoi', '0', 'Tue, 32 Nov 2023 99:99:99 GMT',
                  'Thu, 01 Jan 1970 00:00:00 GMT', 'a' * 500):
            self.assertIsInstance(non_modifie(e, 1700000000), bool, repr(e))


class DansLaROUTE(unittest.TestCase):
    SRC = _src('_send_file')

    def test_le_304_ne_sort_JAMAIS_sur_une_demande_de_PLAGE(self):
        i = self.SRC.index('send_response(304)')
        condition = self.SRC[self.SRC.index('_non_modifie('):i]
        self.assertIn("not self.headers.get('Range')", condition)

    def test_les_deux_reponses_datent_le_fichier(self):
        self.assertEqual(self.SRC.count("send_header('Last-Modified', derniere)"), 2)
        self.assertEqual(self.SRC.count("send_header('Cache-Control', 'no-cache')"), 2)
        entetes = [l for l in self.SRC.splitlines()
                   if 'send_header(' in l and 'Cache-Control' in l]
        self.assertEqual(len(entetes), 2)
        self.assertFalse([l for l in entetes if 'max-age' in l], entetes)

    def test_la_date_vient_du_MEME_stat_que_la_taille(self):
        """Deux `stat` diraient deux vérités : la taille servie et la date
        envoyée doivent venir du même instant."""
        self.assertEqual(self.SRC.count('filepath.stat()'), 1)
        i = self.SRC.index('st = filepath.stat()')
        self.assertIn('size = st.st_size', self.SRC[i:i + 200])
        self.assertIn('_date_http(st.st_mtime)', self.SRC)

    def test_le_304_sort_AVANT_de_lire_le_fichier(self):
        self.assertLess(self.SRC.index('send_response(304)'), self.SRC.index('open(filepath'))


if __name__ == '__main__':
    unittest.main()
