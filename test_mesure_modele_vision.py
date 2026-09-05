#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regles pures de mesure_modele_vision.py (chantier tagging FR-only / gros
modele). Aucun acces NAS, base ni Ollama."""

import unittest

from mesure_modele_vision import dejeton, plain_kw


class LeJeton(unittest.TestCase):

    def test_valeur_normale_inchangee(self):
        self.assertEqual(dejeton('qwen3-vl:4b'), 'qwen3-vl:4b')

    def test_b64_round_trip_avec_espaces_et_antislash(self):
        original = r'\\NAS-Bremblens\home\Photos\Luna & Inti\x.jpg'
        import base64
        enc = base64.urlsafe_b64encode(original.encode('utf-8')).decode().rstrip('=')
        self.assertEqual(dejeton('b64:' + enc), original)


class LesMotsClesLibres(unittest.TestCase):

    def test_exclut_les_tags_nommes(self):
        self.assertEqual(plain_kw(['Chat', 'personne:Flo', 'animal:Rex']),
                         ['chat'])

    def test_liste_vide(self):
        self.assertEqual(plain_kw(None), [])
        self.assertEqual(plain_kw([]), [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
