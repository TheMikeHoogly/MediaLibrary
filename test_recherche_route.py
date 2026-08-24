#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la route `/api/search` dans `server.py` -- SUR LE CODE DE PROD.

Pourquoi ce fichier
-------------------
Le MOTEUR est teste ailleurs (`test_recherche`, `recherche.py`). Ce qui reste
ici est la COURROIE, et elle porte une chose qu'aucune regle pure ne montre :
**ce que la route DIT de ce qu'elle a coupe**.

Le 23/08, `mesure_recherche_nommee` a trouve que `semantic_search` CALCULE
`detail['total']` et `detail['tronque']` -- puis que la route ne les rend pas.
Seule la page `/files?q=` les recevait. Un consommateur de l'API voyait donc
1 500 photos sans savoir qu'il y en avait 5 832 : le plafond silencieux
corrige pour la page le 22/08 et pour le MCP le 23/08 vivait encore dans la
route. Un plafond tu se lit comme une exhaustivite -- c'est le mode de panne
que ce projet paye le plus cher.

Et le contraire est aussi un mensonge : la branche SEMANTIQUE classe tout le
fonds par cosinus, il n'y a pas de <<total>> a y lire. Rendre `len(resultats)`
ferait passer une page de resultats pour un fonds entier. La route rend donc
`null`, qui se distingue de zero.

Comme les autres tests de greffe, ce module lit `server.py` sans l'importer :
le serveur tire torch et insightface, un test n'a pas a payer ca. Rien n'est
imprime (l'agent git capture la sortie, et sa console est en cp1252).
"""

import ast
import json
import unittest
import urllib.parse
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

CLE = r"\\NAS-Bremblens\home\Photos\2019\IMG_1.jpg"


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py -- la greffe de "
                         "/api/search a bouge, ce test doit etre relu.")


class FauxStore:
    def __init__(self, data):
        self.data = data


class FausseReponse:
    """Un `self` de handler : juste ce que `_serve_semantic_search` touche."""

    def __init__(self, chemin):
        self.path = chemin
        self.code = None
        self.ctype = None
        self.corps = None

    def _send(self, code, body, ctype):
        self.code, self.ctype, self.corps = code, ctype, body

    def json(self):
        return json.loads(self.corps.decode('utf-8'))


def espace(resultats, detail_rendu):
    """Namespace d'execution. `detail_rendu` est ce que le MOTEUR remplit."""
    def faux_search(requete, limite, detail=None):
        if detail is not None:
            detail.update(detail_rendu)
        return list(resultats)

    ns = {
        'json': json, 'urllib': urllib, 'Path': Path,
        'STORE': FauxStore({CLE: {'kw_fr': ['chat'], 'desc': 'un chat'}}),
        'semantic_search': faux_search,
        'note_heavy_activity': lambda: None,
        'media_roots': lambda: [],
        '_url_for_key': lambda cle, roots: '/img?k=' + cle,
    }
    exec(compile(ast.Module([_noeud('_serve_semantic_search')], []),
                 str(SERVER), 'exec'), ns)
    return ns


def appeler(ns, q='chat', n=None):
    params = [('q', q)] + ([('n', str(n))] if n else [])
    r = FausseReponse('/api/search?' + urllib.parse.urlencode(params))
    ns['_serve_semantic_search'](r)
    return r


BASE = {'noms': [], 'lieux': [], 'periode': '', 'especes': [],
        'especes_inconnues': [], 'reste': '', 'sans_date': 0,
        'sans_date_tri': 0}


class LePlafondSeDit(unittest.TestCase):

    def test_total_et_tronque_sont_RENDUS_quand_le_moteur_les_connait(self):
        """Le filtre deterministe compte AVANT de couper. Ce qu'il sait, la
        route doit le dire."""
        d = dict(BASE, total=5832, tronque=4332)
        r = appeler(espace([(CLE, 1.0)], d), n=1500)
        self.assertEqual(r.code, 200)
        corps = r.json()
        self.assertEqual(corps['total'], 5832)
        self.assertEqual(corps['tronque'], 4332)

    def test_un_consommateur_voit_qu_il_MANQUE_des_photos(self):
        """Le defaut d'origine : 1 500 rendues sur 5 832, sans un mot."""
        d = dict(BASE, total=5832, tronque=4332)
        corps = appeler(espace([(CLE, 1.0)], d), n=1500).json()
        self.assertGreater(corps['tronque'], 0)
        self.assertGreater(corps['total'], len(corps['results']))

    def test_rien_de_coupe_se_dit_ZERO_pas_absent(self):
        """`tronque` absent obligerait chaque consommateur a deviner. Zero est
        une reponse ; l'absence n'en est pas une."""
        d = dict(BASE, total=1, tronque=0)
        corps = appeler(espace([(CLE, 1.0)], d)).json()
        self.assertIn('tronque', corps)
        self.assertEqual(corps['tronque'], 0)
        self.assertEqual(corps['total'], 1)


class CeQuOnNeSaitPasNeSInventePas(unittest.TestCase):

    def test_la_branche_semantique_rend_NULL_et_n_invente_pas_un_total(self):
        """Le cosinus classe TOUT le fonds : il n'y a pas de total a lire.
        Rendre `len(results)` ferait passer une page pour un fonds entier."""
        corps = appeler(espace([(CLE, 0.31)], dict(BASE))).json()
        self.assertIn('total', corps)
        self.assertIsNone(corps['total'])
        self.assertIsNone(corps['tronque'])

    def test_null_se_distingue_de_zero(self):
        """`0` dit <<rien n'a ete coupe>>, `null` dit <<je ne sais pas>>. Les
        confondre, c'est reinventer le plafond muet a l'autre bout."""
        connu = appeler(espace([(CLE, 1.0)], dict(BASE, total=1,
                                                  tronque=0))).json()
        inconnu = appeler(espace([(CLE, 0.31)], dict(BASE))).json()
        self.assertEqual(connu['tronque'], 0)
        self.assertIsNone(inconnu['tronque'])

    def test_une_requete_vide_ne_pretend_rien(self):
        r = appeler(espace([], dict(BASE)), q='')
        self.assertEqual(r.code, 200)
        self.assertEqual(r.json()['results'], [])


class LaRouteEstBranchee(unittest.TestCase):

    def test_do_GET_appelle_bien_le_handler(self):
        """Une methode que le routeur n'appelle pas est du code mort qui a
        l'air vivant."""
        self.assertIn('self._serve_semantic_search()', SOURCE)
        self.assertIn("elif path == '/api/search':", SOURCE)

    def test_la_forme_partagee_avec_similar_et_jour_est_intacte(self):
        """`results` porte key/score/url/name : /api/similar et /api/jour
        rendent la meme, et le MCP lit les trois."""
        corps = appeler(espace([(CLE, 1.0)], dict(BASE))).json()
        self.assertEqual(len(corps['results']), 1)
        for champ in ('key', 'score', 'url', 'name'):
            self.assertIn(champ, corps['results'][0])


if __name__ == '__main__':
    unittest.main(verbosity=0)
