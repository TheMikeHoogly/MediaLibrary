#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`SubjectStore.confirm` GRAVE la confirmation dans la fiche -- SUR LE CODE
DE PROD (fragment exécuté, sans importer server.py).

Pourquoi : le healer du démarrage (« exclusion humaine ré-appliquée ») retire
tout tag d'une photo EXCLUE, sauf si elle est `confirmed` -- le contrôle
`confirmed` passe AVANT `exclude`. Un confirm qui n'écrit pas `confirmed`
fait donc rebondir le tag à chaque démarrage (vu le 30/08 sur 2 des 19 noms
du dédoublonnage). L'exclusion, elle, doit RESTER écrite (règle du 29/08)."""

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _methode(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable")


class FauxStore:
    def __init__(self, data):
        self.data = data
        self.sets = []

    def set(self, k, v, save=True):
        self.data[k] = v
        self.sets.append(k)


def _confirm(fiche, keys):
    """Exécute le VRAI confirm sur une fausse fiche ; rend (n, fiche, appels)."""
    appels = {'index': [], 'xmp': []}
    ns = {
        '_index_add_person': lambda k, t: appels['index'].append((k, t)),
        '_enqueue_person_write': lambda k, t: appels['xmp'].append((k, t)),
        'STORE': type('S', (), {'save': staticmethod(lambda: None)})(),
    }
    exec(compile(ast.Module([_methode('confirm')], []), 'server_confirm', 'exec'), ns)
    store = FauxStore({'mike': fiche} if fiche is not None else {})
    self = type('Sujet', (), {'prefix': 'personne', 'store': store})()
    n = ns['confirm'](self, 'Mike', keys)
    return n, store.data.get('mike'), appels


class LaConfirmationEstGravee(unittest.TestCase):

    def test_le_tag_part_et_confirmed_recoit_la_cle(self):
        n, fiche, appels = _confirm({'name': 'Mike', 'exclude': ['K1'], 'confirmed': []}, ['K1'])
        self.assertEqual(n, 1)
        self.assertEqual(appels['index'], [('K1', 'personne:Mike')])
        self.assertEqual(appels['xmp'], [('K1', 'personne:Mike')])
        self.assertIn('K1', fiche['confirmed'])

    def test_l_exclusion_n_est_PAS_effacee(self):
        n, fiche, _ = _confirm({'name': 'Mike', 'exclude': ['K1']}, ['K1'])
        self.assertIn('K1', fiche['exclude'],
                      "l'exclusion doit rester ecrite : rien ne s'efface (29/08)")

    def test_sans_fiche_le_tag_part_quand_meme(self):
        n, fiche, appels = _confirm(None, ['K1'])
        self.assertEqual(n, 1)
        self.assertIsNone(fiche)
        self.assertEqual(len(appels['index']), 1)

    def test_pas_de_doublon_dans_confirmed(self):
        n, fiche, _ = _confirm({'name': 'Mike', 'confirmed': ['K1']}, ['K1', 'K2'])
        self.assertEqual(sorted(fiche['confirmed']), ['K1', 'K2'])

    def test_le_healer_lit_confirmed_avant_exclude(self):
        """La propriété dont tout dépend : dans le healer du démarrage, le
        contrôle `confirmed` précède le contrôle `exclude` dans la source."""
        i = SOURCE.index('if k in p["confirmed"]')
        j = SOURCE.index('if k in p["exclude"]')
        self.assertLess(i, j)


class LaConfirmationNeutraliseL_Exclusion(unittest.TestCase):
    """`_autorite_des_noms` : une cle confirmee ET exclue par la meme fiche
    n'entre pas dans `exclus` — la confirmation (geste explicite) fait
    autorite pour l'affichage et la recherche, l'exclusion reste ecrite."""

    def _autorite(self, fiche):
        class FauxStore:
            def __init__(self, data): self.data = data
        ns = {
            'PEOPLE_STORE': FauxStore({'mike': fiche}),
            'PETS_STORE': FauxStore({}),
        }
        exec(compile(ast.Module([_methode('_autorite_des_noms')], []),
                     'server_autorite', 'exec'), ns)
        return ns['_autorite_des_noms']()

    def test_exclue_seule_garde_son_autorite(self):
        _, exclus, _ = self._autorite({'name': 'Mike', 'exclude': ['K1']})
        self.assertIn('personne:mike', exclus.get('K1', set()))

    def test_confirmee_ET_exclue_n_est_plus_exclue(self):
        _, exclus, _ = self._autorite({'name': 'Mike', 'exclude': ['K1'],
                                       'confirmed': ['K1']})
        self.assertNotIn('K1', exclus)

    def test_la_confirmation_d_une_autre_cle_ne_leve_rien(self):
        _, exclus, _ = self._autorite({'name': 'Mike', 'exclude': ['K1'],
                                       'confirmed': ['K2']})
        self.assertIn('personne:mike', exclus.get('K1', set()))


if __name__ == '__main__':
    unittest.main(verbosity=1)
