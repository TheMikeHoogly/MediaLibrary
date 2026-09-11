#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/pets et /people : la vignette de chaque sujet, en UNE passe.

Relevé du 10/09 : `GET /api/pets/list` 2,87 s. La cause se lisait dans le code :
une boucle sur les 17 chats CONTENAIT un balayage des 40 584 détections, et
chaque tour relisait l'index des tags. `people_list` avait le même défaut dans
son repli (une fiche sans avatar = un balayage de l'index entier).
*Un balayage de toute la photothèque imbriqué dans une boucle sur les sujets.*

La correction ne change pas la règle — la PREMIÈRE entrée, dans l'ordre de
l'index, qui porte le tag et fournit une vignette — elle la sert pour tous les
sujets à la fois. Ce qui le garde :

  * **l'ancienne écriture est l'oracle.** Les deux fonctions d'avant le 11/09
    sont recopiées ci-dessous, verbatim, et comparées à la nouvelle sur des
    magasins tirés au hasard (casse des noms, homonymes, photos sans détection
    nommable, entrées cassées), graine fixée : un échec se rejoue ;
  * **le nombre de balayages est COMPTÉ** : un seul, quel que soit le nombre de
    sujets. Une optimisation qui ne se compte pas est une intention.

Les fonctions sont exécutées seules (importer server.py ouvrirait la base).
"""

import ast
import random
import types
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


_LIGNES = SOURCE.splitlines(keepends=True)
_SOURCES = {}


def _src(nom):
    """Le source d'une fonction de premier niveau (mis en cache : relire un
    fichier de 700 Ko à chaque tirage rendrait l'oracle trop lent pour tourner)."""
    if nom not in _SOURCES:
        for n in ARBRE.body:
            if isinstance(n, ast.FunctionDef) and n.name == nom:
                debut = n.lineno - 1 - len(n.decorator_list)
                _SOURCES[nom] = ''.join(_LIGNES[debut:n.end_lineno])
                break
        else:
            raise AssertionError(nom + ' introuvable dans server.py')
    return _SOURCES[nom]


# ─── L'ORACLE : les deux fonctions telles qu'elles étaient le 11/09 au matin ──
AVANT = 'def pets_list_avant():\n    """Chats nommés avec nombre de photos et une vignette."""\n    tagcount = {}\n    for e in STORE.data.values():\n        if not isinstance(e, dict):\n            continue\n        for kw in (e.get(\'kw_fr\') or []):\n            if str(kw).lower().startswith(\'animal:\'):\n                key = str(kw)[7:].strip().lower()\n                tagcount[key] = tagcount.get(key, 0) + 1\n    out = []\n    for pk, pe in PETS_STORE.data.items():\n        if not isinstance(pe, dict):\n            continue\n        nm = pe.get(\'name\', pk)\n        crop = None\n        for k, e in ANIMAL_STORE.data.items():\n            if not _kw_has(STORE.data.get(k), f"animal:{nm}"):\n                continue\n            animals = e.get(\'animals\') if isinstance(e, dict) else None\n            if animals:\n                for i, a in enumerate(animals):\n                    if _nommable(a):\n                        crop = _animal_crop_url(k, i)\n                        break\n            if crop:\n                break\n        # `contestes` : les jugements perdus que la fiche garde en mémoire —\n        # comptés ici pour que la carte le DISE (chantier 17, étape 2).\n        out.append({"name": nm, "photos": tagcount.get(nm.strip().lower(), 0),\n                    "crop": crop,\n                    "contestes": len(_auteurs.contestations(pe))})\n    out.sort(key=lambda x: -x["photos"])\n    return out' + "\n\n" + 'def people_list_avant():\n    """Personnes nommées avec nombre de photos et une vignette."""\n    # Comptage insensible à la casse : on regroupe par nom en minuscules, car\n    # l\'index peut contenir « personne:Nom » (app) ou « personne:nom » (importé).\n    tagcount = {}\n    for e in STORE.data.values():\n        if not isinstance(e, dict):\n            continue\n        for kw in (e.get(\'kw_fr\') or []):\n            if str(kw).lower().startswith(\'personne:\'):\n                key = str(kw)[9:].strip().lower()\n                tagcount[key] = tagcount.get(key, 0) + 1\n    out = []\n    for pk, pe in PEOPLE_STORE.data.items():\n        if not isinstance(pe, dict):\n            continue\n        nm = pe.get(\'name\', pk)\n        crop = None\n        # avatar = visage le plus représentatif (calculé par le curateur)\n        av = pe.get(\'avatar\')\n        if isinstance(av, list) and len(av) == 2:\n            fe = FACE_STORE.data.get(av[0])\n            if isinstance(fe, dict):\n                faces = fe.get(\'faces\') or []\n                if faces:\n                    ai = av[1] if 0 <= av[1] < len(faces) else 0\n                    crop = _crop_url(av[0], ai)\n        if crop is None:   # repli tant que le curateur n\'a pas encore tourné\n            for k, e in STORE.data.items():\n                if _kw_has(e, f"personne:{nm}"):\n                    fe = FACE_STORE.data.get(k)\n                    if isinstance(fe, dict) and fe.get(\'faces\'):\n                        crop = _crop_url(k, 0)\n                        break\n        # `contestes` : les jugements perdus que la fiche garde en mémoire —\n        # comptés ici pour que la carte le DISE (chantier 17, étape 2).\n        out.append({"name": nm, "photos": tagcount.get(nm.strip().lower(), 0),\n                    "crop": crop,\n                    "contestes": len(_auteurs.contestations(pe))})\n    out.sort(key=lambda x: -x["photos"])\n    return out'


class Magasin:
    """Un magasin dont `.data` compte ses balayages (`items`/`values`)."""

    def __init__(self, d):
        self._d = d
        self.balayages = 0

    @property
    def data(self):
        return _Compte(self)


class _Compte:
    def __init__(self, m):
        self._m = m

    def items(self):
        self._m.balayages += 1
        return list(self._m._d.items())

    def values(self):
        self._m.balayages += 1
        return list(self._m._d.values())

    def get(self, k, default=None):
        return self._m._d.get(k, default)


def _monde(store, animaux, chats, visages, personnes):
    g = {'urllib': urllib, 'ANIMAL_NAMEABLE': {'cat', 'dog', 'horse'},
         '_auteurs': types.SimpleNamespace(
             contestations=lambda fiche: fiche.get('contestes_test') or []),
         'STORE': Magasin(store), 'ANIMAL_STORE': Magasin(animaux),
         'PETS_STORE': Magasin(chats), 'FACE_STORE': Magasin(visages),
         'PEOPLE_STORE': Magasin(personnes)}
    for nom in ('_kw_has', '_nommable', '_animal_crop_url', '_crop_url',
                'pets_list', 'people_list', '_premiere_nommable',
                '_premieres_vignettes'):
        exec(_src(nom), g)                                             # noqa: S102
    exec(AVANT, g)                                                     # noqa: S102
    return g


NOMS = ['Inti', 'inti', 'Luna', 'Caline', 'Calinous', 'Mimi', 'Zoé', 'zoé ',
        'Florine', 'Mike', 'Dévi', 'Lucien', 'Personne Seule']


def _tirage(graine):
    r = random.Random(graine)
    store, animaux, visages = {}, {}, {}
    for i in range(r.randint(0, 400)):
        k = r'\\NAS\Photos\%d\p%d.jpg' % (r.randint(2005, 2026), i)
        kw = [r.choice(['chat', 'jardin', 'soleil'])]
        for _ in range(r.randint(0, 3)):
            nom = r.choice(NOMS)
            genre = r.choice(['animal:', 'personne:', 'Animal:', 'PERSONNE:'])
            kw.append(genre + (nom.upper() if r.random() < .2 else nom))
        if r.random() < .03:
            store[k] = 'cassée'
        else:
            store[k] = {'kw_fr': kw, 'failed': r.random() < .05}
        if r.random() < .6:
            dets = []
            for _ in range(r.randint(0, 3)):
                dets.append({'species': r.choice(['cat', 'dog', 'bird', 'cat']),
                             'suspect': r.random() < .15,
                             'inconnu': r.random() < .1})
            animaux[k] = {'animals': dets} if r.random() > .05 else None
        if r.random() < .5:
            visages[k] = {'faces': [{}] * r.randint(0, 2)}
    cles = list(store)
    chats = {}
    for nom in r.sample(NOMS, r.randint(0, 8)):
        chats[nom.lower()] = {'name': nom,
                              'contestes_test': [1] * r.randint(0, 2)}
    personnes = {}
    for nom in r.sample(NOMS, r.randint(0, 10)):
        fiche = {'name': nom}
        if cles and r.random() < .5:
            fiche['avatar'] = [r.choice(cles), r.randint(-1, 3)]
        elif r.random() < .2:
            fiche['avatar'] = 'abîmé'
        personnes[nom.lower() + str(r.random() < .5)] = fiche
    return store, animaux, chats, visages, personnes


class LaRegleNaPasBouge(unittest.TestCase):
    def test_pets_list_rend_ce_que_rendait_l_ancienne_ecriture(self):
        for graine in range(300):
            g = _monde(*_tirage(graine))
            self.assertEqual(g['pets_list'](), g['pets_list_avant'](), graine)

    def test_people_list_rend_ce_que_rendait_l_ancienne_ecriture(self):
        for graine in range(300):
            g = _monde(*_tirage(graine))
            self.assertEqual(g['people_list'](), g['people_list_avant'](),
                             graine)

    def test_le_tirage_couvre_les_cas_qui_comptent(self):
        """Un oracle qui ne voit jamais le cas difficile se donne raison à bon
        compte. On exige que les 300 tirages aient produit : des vignettes
        trouvées ET manquantes, des homonymes de casse, et des repli sans
        avatar dans les deux sens."""
        vus = {'chat_avec': 0, 'chat_sans': 0, 'repli_trouve': 0,
               'repli_vide': 0, 'homonymes': 0}
        for graine in range(300):
            store, animaux, chats, visages, personnes = _tirage(graine)
            g = _monde(store, animaux, chats, visages, personnes)
            for c in g['pets_list_avant']():
                vus['chat_avec' if c['crop'] else 'chat_sans'] += 1
            noms = [f.get('name', '').strip().lower() for f in chats.values()]
            vus['homonymes'] += len(noms) - len(set(noms))
            for p in g['people_list_avant']():
                if p['crop'] and p['crop'].endswith('&i=0'):
                    vus['repli_trouve'] += 1
                elif not p['crop']:
                    vus['repli_vide'] += 1
        for cle, n in vus.items():
            self.assertGreater(n, 0, cle)


class LeNombreDeBalayages(unittest.TestCase):
    def _gros(self):
        store, animaux = {}, {}
        for i in range(3000):
            k = 'p%d.jpg' % i
            store[k] = {'kw_fr': ['jardin']}
            animaux[k] = {'animals': [{'species': 'cat'}]}
        store['p2999.jpg']['kw_fr'].append('animal:Inti')
        chats = {n.lower(): {'name': n} for n in
                 ('Inti', 'Luna', 'Mimi', 'Caline', 'Calinous', 'Zoé')}
        personnes = {n.lower(): {'name': n} for n in
                     ('Mike', 'Florine', 'Dévi', 'Lucien')}
        return store, animaux, chats, {}, personnes

    def test_pets_list_balaie_les_detections_UNE_fois(self):
        g = _monde(*self._gros())
        avant = g['ANIMAL_STORE'].balayages
        g['pets_list_avant']()
        self.assertEqual(g['ANIMAL_STORE'].balayages - avant, 6)   # un par chat
        avant = g['ANIMAL_STORE'].balayages
        g['pets_list']()
        self.assertEqual(g['ANIMAL_STORE'].balayages - avant, 1)

    def test_people_list_balaie_l_index_UNE_fois_pour_tous_les_replis(self):
        g = _monde(*self._gros())
        avant = g['STORE'].balayages
        g['people_list_avant']()
        self.assertEqual(g['STORE'].balayages - avant, 1 + 4)      # comptes + 4 replis
        avant = g['STORE'].balayages
        g['people_list']()
        self.assertEqual(g['STORE'].balayages - avant, 1 + 1)

    def test_sans_repli_a_faire_aucun_balayage_de_plus(self):
        store = {'a.jpg': {'kw_fr': ['personne:Mike']}}
        visages = {'a.jpg': {'faces': [{}]}}
        personnes = {'mike': {'name': 'Mike', 'avatar': ['a.jpg', 0]}}
        g = _monde(store, {}, {}, visages, personnes)
        g['people_list']()
        self.assertEqual(g['STORE'].balayages, 1)                  # les comptes seuls


class LaPasseSArreteQuandToutEstTrouve(unittest.TestCase):
    def test_elle_ne_lit_pas_plus_loin_que_necessaire(self):
        lus = []

        def entrees():
            for i in range(1000):
                lus.append(i)
                yield 'p%d' % i, {'kw_fr': ['animal:Inti'] if i == 3 else []}
        g = _monde({}, {}, {}, {}, {})
        r = g['_premieres_vignettes']({'animal:inti'}, entrees(), None,
                                      lambda k, e: 'url:' + k)
        self.assertEqual(r, {'animal:inti': 'url:p3'})
        self.assertLessEqual(len(lus), 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
