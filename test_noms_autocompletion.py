#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `noms_pour_saisie` dans `server.py` -- SUR LE CODE DE PROD.

Pourquoi ce fichier
-------------------
`/api/names` part au chargement de CHAQUE page, pour l'autocompletion.
`mesure_recherche_nommee` l'a chiffre le 23/08 : **359-364 ms**, soit presque
le double du filtre nomme O7 qu'on croyait etre le sujet. La cause n'est pas
la liste des noms -- les deux magasins de fiches sont petits -- mais le
COMPTAGE : un balayage de tout l'index (43 000 fiches) avec `parse_tag_nomme`
sur chacun de leurs mots-cles, refait a chaque appel.

Ce que ces tests tiennent
-------------------------
1. **Le comptage est mis en cache**, et le second appel ne rebalaie pas
   l'index. C'est le gain.
2. **La LISTE des noms ne l'est PAS.** Un nom cree a l'instant doit paraitre
   dans l'autocompletion tout de suite, sinon on le recree en <<Nouveau>> --
   exactement le defaut que le cap `[:40]` avait deja cause (I7). Ce qui a le
   droit d'avoir une minute de retard est un CHIFFRE d'affichage, jamais la
   presence d'un nom.
3. **Le cache expire.** Un compteur fige finirait par mentir sans jamais se
   corriger.
4. **Le compte reste juste** : normalise en minuscules, personnes et animaux
   comptes separement.

Comme les autres tests de greffe, ce module lit `server.py` sans l'importer :
le serveur tire torch et insightface, un test n'a pas a payer ca.
"""

import ast
import threading
import time
import unittest
from collections import Counter
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py -- "
                         "l'autocompletion a bouge, ce test doit etre relu.")


class DataQuiCompteSesBalayages(dict):
    """Un `STORE.data` qui dit combien de fois on l'a parcouru."""

    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        self.balayages = 0

    def items(self):
        self.balayages += 1
        return dict.items(self)


class FauxStore:
    def __init__(self, data):
        self.data = data


def _photo(*noms):
    return {'kw_fr': list(noms), 'kw_en': []}


def espace(fiches=None, personnes=(), animaux=(), horloge=None):
    data = DataQuiCompteSesBalayages(fiches or {})
    ns = {
        'time': horloge or time,
        'threading': threading,
        'Counter': Counter,
        'STORE': FauxStore(data),
        'PEOPLE_STORE': FauxStore({str(i): {'name': n}
                                   for i, n in enumerate(personnes)}),
        'PETS_STORE': FauxStore({str(i): {'name': n, 'species': 'chat'}
                                 for i, n in enumerate(animaux)}),
        '_sans_accents': lambda s: (s or '').lower(),
        'parse_tag_nomme': _parse_tag_nomme,
    }
    for nom in ('_compte_des_noms', 'noms_pour_saisie'):
        exec(compile(ast.Module([_noeud(nom)], []), str(SERVER), 'exec'), ns)
    for cle in ('_NOMS_COMPTE_CACHE', '_NOMS_COMPTE_LOCK',
                'NOMS_COMPTE_TTL_S'):
        ns[cle] = _global_de_server(cle)
    ns['_NOMS_COMPTE_CACHE'] = {"at": 0.0, "compte": None}
    ns['_NOMS_COMPTE_LOCK'] = threading.Lock()
    return ns, data


def _global_de_server(nom):
    """La valeur d'une constante de module, sans importer server.py."""
    for n in ARBRE.body:
        if isinstance(n, ast.Assign):
            for c in n.targets:
                if isinstance(c, ast.Name) and c.id == nom:
                    try:
                        return ast.literal_eval(n.value)
                    except ValueError:
                        return None
    raise AssertionError(nom + " introuvable dans server.py")


def _parse_tag_nomme(kw):
    for prefixe in ('personne', 'animal'):
        if (kw or '').lower().startswith(prefixe + ':'):
            return (prefixe, kw.split(':', 1)[1])
    return None


class Horloge:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t


class LeComptageEstMisEnCache(unittest.TestCase):

    def test_le_second_appel_ne_rebalaie_PAS_l_index(self):
        ns, data = espace(fiches={'a': _photo('personne:Val')},
                          personnes=['Val'])
        ns['noms_pour_saisie']()
        apres_un = data.balayages
        ns['noms_pour_saisie']()
        self.assertEqual(data.balayages, apres_un,
                         "le comptage doit venir du cache au second appel")

    def test_le_PREMIER_appel_balaie_bien_lui(self):
        ns, data = espace(fiches={'a': _photo('personne:Val')},
                          personnes=['Val'])
        ns['noms_pour_saisie']()
        self.assertGreaterEqual(data.balayages, 1)

    def test_le_cache_EXPIRE(self):
        h = Horloge()
        ns, data = espace(fiches={'a': _photo('personne:Val')},
                          personnes=['Val'], horloge=h)
        ns['noms_pour_saisie']()
        apres_un = data.balayages
        h.t += ns['NOMS_COMPTE_TTL_S'] + 1
        ns['noms_pour_saisie']()
        self.assertGreater(data.balayages, apres_un,
                           "un compteur fige finirait par mentir sans se "
                           "corriger")

    def test_la_duree_est_une_CONSTANTE_lisible(self):
        self.assertEqual(_global_de_server('NOMS_COMPTE_TTL_S'), 60)


class LaListeDesNomsNEstPasEnCache(unittest.TestCase):

    def test_un_nom_cree_a_l_instant_parait_TOUT_DE_SUITE(self):
        """Un nom absent de l'autocompletion est recree en <<Nouveau>> : c'est
        le defaut que le cap [:40] avait deja cause (I7). Ce qui a le droit
        d'avoir une minute de retard est un CHIFFRE, jamais une presence."""
        ns, _d = espace(fiches={'a': _photo('personne:Val')},
                        personnes=['Val'])
        ns['noms_pour_saisie']()                     # le cache se remplit
        ns['PEOPLE_STORE'].data['99'] = {'name': 'Mathilde'}
        noms = [x['nom'] for x in ns['noms_pour_saisie']()]
        self.assertIn('Mathilde', noms)

    def test_un_nom_neuf_est_a_zero_photo_pas_absent(self):
        ns, _d = espace(personnes=['Mathilde'])
        sortie = ns['noms_pour_saisie']()
        self.assertEqual([x['nom'] for x in sortie], ['Mathilde'])
        self.assertEqual(sortie[0]['n'], 0)


class LeCompteResteJuste(unittest.TestCase):

    def test_le_compte_suit_les_photos(self):
        ns, _d = espace(fiches={'a': _photo('personne:Val'),
                                'b': _photo('personne:Val', 'personne:Zab'),
                                'c': _photo('animal:Luna')},
                        personnes=['Val', 'Zab'], animaux=['Luna'])
        par_nom = {x['nom']: x['n'] for x in ns['noms_pour_saisie']()}
        self.assertEqual(par_nom['Val'], 2)
        self.assertEqual(par_nom['Zab'], 1)
        self.assertEqual(par_nom['Luna'], 1)

    def test_une_personne_et_un_animal_du_meme_nom_ne_se_melangent_pas(self):
        ns, _d = espace(fiches={'a': _photo('animal:Luna')},
                        personnes=['Luna'], animaux=['Luna'])
        sortie = ns['noms_pour_saisie']()
        par_genre = {x['genre']: x['n'] for x in sortie}
        self.assertEqual(par_genre['animal'], 1)
        self.assertEqual(par_genre['personne'], 0)

    def test_la_casse_de_l_index_ne_perd_pas_de_photos(self):
        """Un `animal:luna` d'index appartient a la fiche <<Luna>> : le
        compter a part afficherait <<0 photo>> sous un nom qui en porte (I7)."""
        ns, _d = espace(fiches={'a': _photo('animal:luna')}, animaux=['Luna'])
        self.assertEqual(ns['noms_pour_saisie']()[0]['n'], 1)

    def test_le_filtre_par_prefixe_et_par_genre_tient_toujours(self):
        ns, _d = espace(fiches={'a': _photo('personne:Val')},
                        personnes=['Val', 'Zab'], animaux=['Vodka'])
        self.assertEqual([x['nom'] for x in ns['noms_pour_saisie'](None, 'V')],
                         ['Val', 'Vodka'])
        self.assertEqual([x['nom'] for x in
                          ns['noms_pour_saisie']('personne', 'V')], ['Val'])


if __name__ == '__main__':
    unittest.main(verbosity=0)
