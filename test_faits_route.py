#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la greffe de `/api/faits` dans `server.py` -- SUR LE CODE DE PROD.

Pourquoi ce fichier
-------------------
La REGLE est testee ailleurs : `faits_vue.assertions` a son banc, et
`test_faits_affichage` tient ce que la page en fait. Ce qui reste ici est la
COURROIE, et elle porte trois choses qu'aucune regle pure ne montre :

1. **Les trois etats ne se confondent pas.** Un fait rendu, `null` pour une
   photo connue qui ne porte rien, et la cle citee dans `inconnues` quand
   l'index l'ignore. Confondre les deux derniers ferait lire <<cette photo ne
   porte rien>> la ou il faut lire <<je ne connais pas cette photo>> -- le mode
   de panne muet que ce projet paye le plus cher.
2. **Le contexte est bati UNE fois pour tout le lot.** C'est la SEULE raison
   d'accepter plusieurs cles ; si la boucle le rebatissait, la route couterait
   N fois le prix qu'elle pretend eviter.
3. **La route est BRANCHEE.** Une methode `_serve_faits` que `do_GET` n'appelle
   pas est du code mort qui a l'air vivant.

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
CLE_NUE = r"\\NAS-Bremblens\home\Photos\2019\SansRien.jpg"


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py -- la greffe de "
                         "/api/faits a bouge, ce test doit etre relu.")


class FauxStore:
    def __init__(self, data):
        self.data = data


class FausseReponse:
    """Un `self` de handler : juste ce que `_serve_faits` touche."""

    def __init__(self, chemin):
        self.path = chemin
        self.code = None
        self.ctype = None
        self.corps = None

    def _send(self, code, body, ctype):
        self.code, self.ctype, self.corps = code, ctype, body

    def json(self):
        return json.loads(self.corps.decode('utf-8'))


def espace(fiches=None, faits=None, alias=None):
    """Namespace d'execution + les compteurs qui servent de temoins."""
    temoins = {'ctx': 0, 'lourd': 0, 'faits': []}

    def faux_ctx():
        temoins['ctx'] += 1
        return {'sentinelle': temoins['ctx']}

    def faux_faits_pour(cle, entree, ctx):
        temoins['faits'].append((cle, ctx['sentinelle']))
        return (faits or {}).get(cle)

    def faux_lourd():
        temoins['lourd'] += 1

    ns = {
        'json': json, 'urllib': urllib,
        'MAX_FAITS': 200,
        'STORE': FauxStore(fiches if fiches is not None else {}),
        '_faits_ctx': faux_ctx,
        '_faits_pour': faux_faits_pour,
        'note_heavy_activity': faux_lourd,
        '_resolve_key': lambda k: k,
        '_index_key_for_path': lambda k: (alias or {}).get(k),
    }
    exec(compile(ast.Module([_noeud('_serve_faits')], []), str(SERVER), 'exec'),
         ns)
    return ns, temoins


def appeler(ns, cles, brut=None):
    q = brut if brut is not None else urllib.parse.urlencode(
        [('key', c) for c in cles])
    r = FausseReponse('/api/faits?' + q)
    ns['_serve_faits'](r)
    return r


FAIT = {'date': '2019-07-14', 'date_src': 'exif',
        'lieu': 'Bremblens', 'lieu_src': 'gps', 'noms': ['Florine']}


class LesTroisEtats(unittest.TestCase):

    def test_une_photo_connue_rend_ses_faits(self):
        ns, _t = espace(fiches={CLE: {'kw_fr': []}}, faits={CLE: FAIT})
        r = appeler(ns, [CLE])
        self.assertEqual(r.code, 200)
        self.assertEqual(r.json()['faits'][CLE]['lieu'], 'Bremblens')
        self.assertEqual(r.json()['inconnues'], [])

    def test_une_photo_connue_SANS_faits_rend_null_et_reste_connue(self):
        """`null` dit <<je connais cette photo, elle ne porte ni date, ni lieu,
        ni nom>>. La ranger dans `inconnues` dirait autre chose."""
        ns, _t = espace(fiches={CLE_NUE: {'kw_fr': []}}, faits={})
        r = appeler(ns, [CLE_NUE])
        d = r.json()
        self.assertIn(CLE_NUE, d['faits'])
        self.assertIsNone(d['faits'][CLE_NUE])
        self.assertEqual(d['inconnues'], [])

    def test_une_cle_inconnue_est_NOMMEE_et_pas_inventee(self):
        ns, _t = espace(fiches={})
        r = appeler(ns, ['zzz.jpg'])
        d = r.json()
        self.assertEqual(d['inconnues'], ['zzz.jpg'])
        self.assertNotIn('zzz.jpg', d['faits'])

    def test_les_trois_etats_cohabitent_dans_une_seule_reponse(self):
        ns, _t = espace(fiches={CLE: {}, CLE_NUE: {}}, faits={CLE: FAIT})
        d = appeler(ns, [CLE, CLE_NUE, 'zzz.jpg']).json()
        self.assertEqual(d['faits'][CLE]['noms'], ['Florine'])
        self.assertIsNone(d['faits'][CLE_NUE])
        self.assertEqual(d['inconnues'], ['zzz.jpg'])
        self.assertEqual(d['demandees'], 3)


class LeRattrapageDesCles(unittest.TestCase):

    def test_une_cle_minusculee_par_SMB_est_retrouvee(self):
        """Le resolve de l'hote SMB minuscule la racine : une cle recopiee
        depuis un vieux lien ne tombe plus dans l'index. Meme rattrapage que
        `_jour_resoudre` -- sans lui, <<absent>> serait faux."""
        demandee = CLE.lower()
        ns, temoins = espace(fiches={CLE: {}}, faits={CLE: FAIT},
                             alias={demandee: CLE})
        d = appeler(ns, [demandee]).json()
        # rendue sous la cle DEMANDEE (l'appelant doit s'y retrouver)...
        self.assertIn(demandee, d['faits'])
        self.assertEqual(d['faits'][demandee]['lieu'], 'Bremblens')
        # ...mais calculee avec la cle d'INDEX (la seule que la regle connait).
        self.assertEqual(temoins['faits'][0][0], CLE)

    def test_le_rattrapage_ne_fabrique_pas_de_photo(self):
        ns, _t = espace(fiches={}, alias={'x.jpg': 'y.jpg'})
        d = appeler(ns, ['x.jpg']).json()
        self.assertEqual(d['inconnues'], ['x.jpg'])


class LeCoutDuLot(unittest.TestCase):

    def test_le_contexte_est_bati_UNE_fois_pour_tout_le_lot(self):
        """C'est la seule raison d'accepter plusieurs cles. Rebati par cle, le
        lot couterait exactement ce qu'il pretend eviter."""
        cles = ['p%d.jpg' % i for i in range(25)]
        ns, temoins = espace(fiches={c: {} for c in cles})
        appeler(ns, cles)
        self.assertEqual(temoins['ctx'], 1)
        self.assertEqual(len(temoins['faits']), 25)
        self.assertEqual({s for _c, s in temoins['faits']}, {1})

    def test_la_route_cede_la_priorite_au_travail_de_fond(self):
        """`media_roots()` fait des stats SMB (audit O3) : cette route touche
        le NAS, donc l'invariant 5 s'applique."""
        ns, temoins = espace(fiches={CLE: {}})
        appeler(ns, [CLE])
        self.assertEqual(temoins['lourd'], 1)

    def test_au_dela_du_plafond_la_route_le_DIT(self):
        """Un plafond muet se lit comme une exhaustivite (ROADMAP 14a)."""
        cles = ['p%d.jpg' % i for i in range(250)]
        ns, temoins = espace(fiches={c: {} for c in cles})
        d = appeler(ns, cles).json()
        self.assertTrue(d['tronque'])
        self.assertEqual(d['plafond'], 200)
        self.assertEqual(d['demandees'], 200)
        self.assertEqual(len(temoins['faits']), 200)

    def test_sous_le_plafond_rien_n_est_annonce_comme_tronque(self):
        ns, _t = espace(fiches={CLE: {}})
        self.assertNotIn('tronque', appeler(ns, [CLE]).json())


class LesRefus(unittest.TestCase):

    def test_sans_cle_c_est_un_400_qui_dit_la_forme_attendue(self):
        ns, temoins = espace()
        r = appeler(ns, [], brut='')
        self.assertEqual(r.code, 400)
        self.assertIn('key', r.json()['error'])
        self.assertEqual(temoins['ctx'], 0)      # rien n'a ete bati pour rien

    def test_des_cles_vides_ne_comptent_pas_pour_des_cles(self):
        ns, _t = espace()
        r = appeler(ns, [], brut='key=&key=%20%20')
        self.assertEqual(r.code, 400)


class LaGreffe(unittest.TestCase):

    def test_la_route_est_BRANCHEE_dans_do_GET(self):
        """Une methode que le routeur n'appelle jamais est du code mort qui a
        l'air vivant."""
        self.assertIn("elif path == '/api/faits':", SOURCE)
        self.assertIn('self._serve_faits()', SOURCE)

    def test_la_route_n_est_PAS_en_ecriture(self):
        depart = SOURCE.index('def do_POST')
        self.assertNotIn('/api/faits', SOURCE[depart:])

    def test_le_statut_et_le_type_sont_explicites(self):
        ns, _t = espace(fiches={CLE: {}})
        r = appeler(ns, [CLE])
        self.assertEqual(r.code, 200)
        self.assertEqual(r.ctype, 'application/json')

    def test_les_accents_du_fonds_survivent_au_JSON(self):
        """`ensure_ascii=False` : un lieu suisse s'ecrit avec des accents, et
        un agent qui relit `Gen\\u00e8ve` a perdu quelque chose."""
        fait = dict(FAIT, lieu='Genève', noms=['Maryline Baudère'])
        ns, _t = espace(fiches={CLE: {}}, faits={CLE: fait})
        r = appeler(ns, [CLE])
        self.assertIn('Genève'.encode('utf-8'), r.corps)
        self.assertEqual(r.json()['faits'][CLE]['lieu'], 'Genève')


if __name__ == '__main__':
    unittest.main(verbosity=2)
