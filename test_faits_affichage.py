#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de l'affichage des `faits` — `_faits_ctx` / `_faits_pour`.

Pourquoi ce fichier existe
──────────────────────────
Brancher la vue sur la planche a demandé une OPTIMISATION, et une optimisation
est exactement l'endroit où un invariant se perd sans bruit. `_noms_attendus`
rebalaie toutes les fiches à chaque photo ; `_faits_ctx` bâtit l'index inversé
une seule fois. Les deux doivent dire **la même chose**, sinon la planche
affiche un nom que la fiche a retiré — et « un nom humain qui réapparaît après
avoir été retiré est une régression », pas un retard d'actualisation.

Le test compare donc les deux implémentations sur les cas qui les séparent, et
vérifie que l'autorité d'`exclude` ne dépend PAS de l'ordre d'itération des
fiches (c'est la raison des deux passes dans `_faits_ctx`).

Comme `test_gallery_placeholders`, il lit `server.py` **sans l'importer** :
`import server` construit les stores et ouvre `photos.db`, dont le serveur est
l'écrivain unique. Les trois fonctions sont extraites du source et exécutées
dans un espace de noms où les stores sont des doublures.
"""
import ast
import io
import os
import unittest

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")


class _Store(object):
    """Doublure de TagStore : seul `.data` est lu par le code testé."""

    def __init__(self, data=None):
        self.data = data or {}

    def get(self, k):
        return self.data.get(k)


def _charger(noms, espace):
    """Extrait des fonctions de `server.py` par leur nom et les exécute dans
    `espace`. On travaille sur le SOURCE (pas sur une copie recopiée à la main)
    : un banc qui recopie la prod mesure autre chose qu'elle."""
    with io.open(SERVER, encoding="utf-8") as f:
        arbre = ast.parse(f.read())
    trouves = set()
    for n in arbre.body:
        if isinstance(n, ast.FunctionDef) and n.name in noms:
            exec(compile(ast.Module(body=[n], type_ignores=[]),
                         SERVER, "exec"), espace)
            trouves.add(n.name)
    manquants = set(noms) - trouves
    if manquants:
        raise AssertionError("introuvables dans server.py : %s" % sorted(manquants))
    return espace


def _espace(people, pets, index, lieux=None, gps=None, racines=()):
    esp = {
        'PEOPLE_STORE': _Store(people), 'PETS_STORE': _Store(pets),
        'STORE': _Store(index),
        'lieux_connus': lambda: (lieux or {}),
        'gps_places_connus': lambda: (gps or {}),
        'media_roots': lambda: racines,
    }
    return _charger(('_faits_ctx', '_faits_pour', '_noms_attendus'), esp)


# ───────────────── l'index inversé dit-il la même chose ? ─────────────────

class TestIndexInverse(unittest.TestCase):
    """`_faits_ctx` + `_faits_pour` contre `_noms_attendus`, photo par photo."""

    PEOPLE = {
        'p1': {'name': 'Luna', 'faces': [['a.jpg', 0], ['b.jpg', 0]]},
        'p2': {'name': 'Flo', 'faces': [['b.jpg', 1], ['c.jpg', 0]],
               'exclude': ['c.jpg']},
        'p3': {'name': 'Mike', 'faces': [['c.jpg', 2]]},
    }
    PETS = {'a1': {'name': 'Caline', 'faces': [['a.jpg', 3]]}}
    INDEX = {
        'a.jpg': {'kw_fr': ['chat', 'personne:Luna']},
        'b.jpg': {'kw_fr': ['personne:Flo', 'plage']},
        # Nom présent dans les mots-clés mais RETIRÉ par la fiche : c'est le
        # cas qui compte, et le seul que `exclude` doit trancher.
        'c.jpg': {'kw_fr': ['personne:Flo', 'personne:Mike']},
    }

    def _noms_des_deux_facons(self, cle, esp):
        ctx = esp['_faits_ctx']()
        e = self.INDEX[cle]
        par_index = esp['_faits_pour'](cle, e, ctx)
        par_index = sorted(par_index['noms']) if par_index else []

        tags, exclus = esp['_noms_attendus'](cle)
        import tagging_meta
        pe, an = tagging_meta.noms_depuis_kw(
            [t for t in tags if str(t).lower() not in exclus])
        return par_index, sorted(pe + an)

    def test_les_deux_voies_donnent_les_memes_noms(self):
        esp = _espace(self.PEOPLE, self.PETS, self.INDEX)
        for cle in ('a.jpg', 'b.jpg', 'c.jpg'):
            a, b = self._noms_des_deux_facons(cle, esp)
            self.assertEqual(a, b, "divergence sur %s : %r vs %r" % (cle, a, b))

    def test_un_nom_retire_ne_revient_pas(self):
        """`exclude` fait autorité — invariant sacré, testé pour lui-même."""
        esp = _espace(self.PEOPLE, self.PETS, self.INDEX)
        ctx = esp['_faits_ctx']()
        f = esp['_faits_pour']('c.jpg', self.INDEX['c.jpg'], ctx)
        self.assertNotIn('Flo', f['noms'])
        self.assertIn('Mike', f['noms'])

    def test_l_autorite_ne_depend_pas_de_l_ordre_des_fiches(self):
        """La raison d'être des DEUX passes : en une seule, un `exclude` posé
        par une fiche vue APRÈS celle qui attribue ne retirerait rien."""
        avant = dict(self.PEOPLE)
        apres = dict(reversed(list(self.PEOPLE.items())))
        esp1 = _espace(avant, self.PETS, self.INDEX)
        esp2 = _espace(apres, self.PETS, self.INDEX)
        for cle in ('a.jpg', 'b.jpg', 'c.jpg'):
            f1 = esp1['_faits_pour'](cle, self.INDEX[cle], esp1['_faits_ctx']())
            f2 = esp2['_faits_pour'](cle, self.INDEX[cle], esp2['_faits_ctx']())
            self.assertEqual(sorted(f1['noms']), sorted(f2['noms']),
                             "l'ordre des fiches change le résultat sur %s" % cle)


# ─────────────────────────── ce que rend la vue ───────────────────────────

class TestFaitsPour(unittest.TestCase):

    def test_rien_a_dire_rend_none(self):
        """Pas de ligne plutôt qu'une ligne vide, 43 064 fois."""
        esp = _espace({}, {}, {'x/y.jpg': {}})
        ctx = esp['_faits_ctx']()
        self.assertIsNone(esp['_faits_pour']('x/y.jpg', {}, ctx))

    def test_le_lieu_ne_vient_jamais_d_une_sous_chaine(self):
        """« Ins » est DANS « Cousins&Cousines » : c'est le défaut que
        `faits_vue` a corrigé, on vérifie qu'il ne rentre pas par ici."""
        esp = _espace({}, {}, {}, lieux={'ins': 'Ins'})
        ctx = esp['_faits_ctx']()
        f = esp['_faits_pour']('D:\\Photos\\Cousins&Cousines\\p.jpg', {}, ctx)
        self.assertIsNone(f, "un lieu collé dans un mot est ressorti : %r" % (f,))

    def test_le_gps_prime_sur_le_chemin_et_le_dit(self):
        esp = _espace({}, {}, {}, lieux={'sion': 'Sion'},
                      gps={'D:\\Photos\\Sion\\p.jpg': 'Lausanne'})
        ctx = esp['_faits_ctx']()
        f = esp['_faits_pour']('D:\\Photos\\Sion\\p.jpg', {}, ctx)
        self.assertEqual(f['lieu'], 'Lausanne')
        self.assertEqual(f['lieu_src'], 'gps')

    def test_la_date_porte_sa_source(self):
        esp = _espace({}, {}, {})
        ctx = esp['_faits_ctx']()
        f = esp['_faits_pour']('D:\\Photos\\1998\\p.jpg', {}, ctx)
        self.assertEqual(f['date'], '1998')
        self.assertEqual(f['date_src'], 'annee du dossier')

    def test_la_date_de_scan_est_ecartee_a_la_lecture(self):
        """Le garde-fou du 19/08 traverse-t-il l'affichage ? Un `taken` de 2015
        sous un dossier 1983 est la date du SCAN — la vue doit retomber sur
        l'année du dossier, comme la recherche et « même jour »."""
        import time
        scan = time.mktime((2015, 8, 10, 12, 0, 0, 0, 0, -1))
        esp = _espace({}, {}, {})
        ctx = esp['_faits_ctx']()
        f = esp['_faits_pour']('D:\\Photos Papa\\1983\\20150810_1.jpg',
                               {'taken': scan}, ctx)
        self.assertEqual(f['date'], '1983')
        self.assertEqual(f['date_src'], 'annee du dossier')


# ──────────────────── le câblage dans la page (source) ────────────────────

class TestCablage(unittest.TestCase):
    """Les quatre modes de `/files` construisent le MÊME objet-photo. Un mode
    oublié, et la ligne disparaît sans erreur — sur une page seulement."""

    def setUp(self):
        with io.open(SERVER, encoding="utf-8") as f:
            self.src = f.read()

    def test_les_quatre_constructeurs_portent_les_faits(self):
        self.assertEqual(self.src.count("'jour': _jour_de("),
                         self.src.count("'faits': _faits_pour("),
                         "un mode de /files construit un objet-photo sans faits")

    def test_le_contexte_est_bati_une_seule_fois(self):
        self.assertEqual(self.src.count("fctx = _faits_ctx()"), 1)

    def test_la_visionneuse_ne_repete_pas_les_noms(self):
        """La ligne de faits les dit déjà, mieux : triés, sans préfixe, avec
        leur source. Le FILTRE de la planche, lui, garde les tags nommés."""
        self.assertIn("kl.indexOf('personne:') !== 0", self.src)
        self.assertIn("aucun mot-clé au-delà des noms", self.src)
        self.assertNotIn("t.textContent = f.kw.join(' · ')", self.src)

    def test_un_seul_producteur_de_la_ligne_pour_les_deux_vues(self):
        """Planche et visionneuse rendent le même fait : deux producteurs
        finiraient par se contredire."""
        self.assertEqual(self.src.count("function faitsHtml("), 1)
        self.assertEqual(self.src.count("faitsHtml(f, false)"), 1)  # planche
        self.assertEqual(self.src.count("faitsHtml(f, true)"), 1)   # visionneuse


if __name__ == "__main__":
    unittest.main(verbosity=2)
