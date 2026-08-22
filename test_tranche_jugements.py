#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du magasin de verdicts de la page /tranche — SUR LE CODE DE PROD.

Pourquoi par ANALYSE DU SOURCE, comme `test_gallery_placeholders`
─────────────────────────────────────────────────────────────────
`import server` construit les stores et ouvre `photos.db`, dont le serveur est
l'ecrivain unique (regle 4 du projet). Ce module extrait donc de l'AST les
fonctions et la methode a eprouver, et les execute dans un espace de noms a
elles, avec un fichier temporaire a la place du fichier de travail. Ce n'est
pas une copie du code : c'est le code, joue ailleurs.

Ce qui est verifie, et pourquoi ce sont ces cas-la
──────────────────────────────────────────────────
1. **Un verdict ne s'ecrase pas tout seul.** L'identite d'une proposition est
   (photo, VISAGE, nom) : deux visages de la meme photo peuvent recevoir deux
   propositions differentes, et les confondre perdrait un jugement.
2. **L'ecriture est atomique** et ne laisse pas de `.tmp` derriere elle
   (invariant 2) : trente jugements, c'est une seance qu'on ne recommence pas.
3. **Un fichier absent ou abime rend une seance vierge**, jamais une panne :
   une page de jugement qui refuse de s'ouvrir ne mesure rien.
4. **Un verdict inconnu est REFUSE.** Le banc ne compte que juste / faux /
   indecidable ; laisser passer un quatrieme mot ferait un total qui ne
   correspond a aucun taux.
5. **La page n'attribue rien.** Le test lit le source du gestionnaire et exige
   qu'aucune fonction d'ecriture du fonds n'y apparaisse — c'est la promesse
   qui rend la mesure utilisable, et une promesse non testee se perd.

FUSEAU HORAIRE : sans objet.
"""

import ast
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

# Toute fonction d'ecriture du fonds : si l'une apparait dans le gestionnaire,
# la page ne serait plus une mesure mais un geste.
ECRITURES_INTERDITES = ('_auto_add', 'STORE.save', 'PEOPLE_STORE.save',
                        'PETS_STORE.save', 'write_tags', 'enqueue',
                        'curator_accept', 'rekey_everywhere', 'exiftool')


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    raise AssertionError(f"{nom} introuvable dans server.py — la page /tranche "
                         "a bouge, ce test doit etre relu avant d'etre cru.")


def _constante(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == nom:
            return ast.literal_eval(n.value)
    raise AssertionError(f"{nom} introuvable dans server.py")


def espace(dossier):
    """Les fonctions de prod, executees avec un fichier de travail a nous."""
    ns = {'json': json, 'os': os, 'time': __import__('time'),
          'TRANCHE_JUGEMENTS': Path(dossier) / '_tranche_jugements.json',
          'TRANCHE_VERDICTS': _constante('TRANCHE_VERDICTS')}
    for nom in ('_tranche_id', '_tranche_lire_jugements',
                '_tranche_ecrire_jugements'):
        exec(compile(ast.Module([_noeud(nom)], []), str(SERVER), 'exec'), ns)
    return ns


class FauxSelf:
    """Le strict necessaire du gestionnaire HTTP : lire un corps, repondre."""

    def __init__(self, corps):
        self.corps = corps
        self.reponses = []

    def _read_json_body(self):
        return self.corps

    def _send(self, code, body, ctype):
        self.reponses.append((code, body, ctype))


def poster(ns, corps, chemin='/api/tranche/juger'):
    """Joue `_do_tranche_post` de la prod dans l'espace de noms d'essai."""
    ns = dict(ns)
    ns.setdefault('threading', __import__('threading'))
    ns.setdefault('TRANCHE_LOCK', ns['threading'].Lock())
    ns.setdefault('_journal_jugement', lambda evt: ns.setdefault(
        'journal', []).append(evt) if isinstance(ns.get('journal'), list)
        else ns.__setitem__('journal', [evt]))
    exec(compile(ast.Module([_noeud('_do_tranche_post')], []),
                 str(SERVER), 'exec'), ns)
    faux = FauxSelf(corps)
    ns['_do_tranche_post'](faux, chemin)
    return faux, ns


class TestIdentite(unittest.TestCase):

    def test_le_visage_fait_partie_de_l_identite(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            a = ns['_tranche_id']('p.jpg', 0, 'Flo')
            b = ns['_tranche_id']('p.jpg', 1, 'Flo')
            c = ns['_tranche_id']('p.jpg', 0, 'Zoe')
            self.assertEqual(len({a, b, c}), 3)


class TestMagasin(unittest.TestCase):

    def test_ecrit_relit_et_ne_laisse_pas_de_tmp(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            ns['_tranche_ecrire_jugements']({'a|0|Flo': {'verdict': 'juste'}})
            self.assertEqual(ns['_tranche_lire_jugements']()['a|0|Flo'],
                             {'verdict': 'juste'})
            restes = [p.name for p in Path(d).iterdir() if p.suffix == '.tmp']
            self.assertEqual(restes, [])

    def test_fichier_absent_rend_une_seance_vierge(self):
        with TemporaryDirectory() as d:
            self.assertEqual(espace(d)['_tranche_lire_jugements'](), {})

    def test_fichier_abime_rend_une_seance_vierge_sans_tomber(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            ns['TRANCHE_JUGEMENTS'].write_text('{ ceci n est pas du json',
                                               encoding='utf-8')
            self.assertEqual(ns['_tranche_lire_jugements'](), {})

    def test_forme_inattendue_rend_une_seance_vierge(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            ns['TRANCHE_JUGEMENTS'].write_text('[1, 2, 3]', encoding='utf-8')
            self.assertEqual(ns['_tranche_lire_jugements'](), {})


class TestGestionnaire(unittest.TestCase):

    def corps(self, **kw):
        base = {'key': 'photo.jpg', 'i': 0, 'person': 'Flo',
                'verdict': 'juste', 'sim': 0.36, 'margin': 0.1, 'rival': 'Zoe'}
        base.update(kw)
        return base

    def test_enregistre_un_verdict(self):
        with TemporaryDirectory() as d:
            faux, ns = poster(espace(d), self.corps())
            code, body, _ = faux.reponses[0]
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)['juges'], 1)
            v = ns['_tranche_lire_jugements']()['photo.jpg|0|Flo']
            self.assertEqual(v['verdict'], 'juste')
            self.assertEqual(v['person'], 'Flo')
            self.assertIn('ts', v)

    def test_refuse_un_verdict_inconnu(self):
        with TemporaryDirectory() as d:
            faux, ns = poster(espace(d), self.corps(verdict='peut-etre'))
            self.assertEqual(faux.reponses[0][0], 400)
            self.assertEqual(ns['_tranche_lire_jugements'](), {})

    def test_refuse_une_proposition_sans_photo_ou_sans_nom(self):
        with TemporaryDirectory() as d:
            for manque in ({'key': ''}, {'person': ''}):
                faux, ns = poster(espace(d), self.corps(**manque))
                self.assertEqual(faux.reponses[0][0], 400)
                self.assertEqual(ns['_tranche_lire_jugements'](), {})

    def test_deux_visages_de_la_meme_photo_ne_s_ecrasent_pas(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            poster(ns, self.corps(i=0, verdict='juste'))
            poster(ns, self.corps(i=1, verdict='faux'))
            v = ns['_tranche_lire_jugements']()
            self.assertEqual(v['photo.jpg|0|Flo']['verdict'], 'juste')
            self.assertEqual(v['photo.jpg|1|Flo']['verdict'], 'faux')

    def test_rejuger_remplace_au_lieu_d_empiler(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            poster(ns, self.corps(verdict='juste'))
            poster(ns, self.corps(verdict='faux'))
            v = ns['_tranche_lire_jugements']()
            self.assertEqual(len(v), 1)
            self.assertEqual(v['photo.jpg|0|Flo']['verdict'], 'faux')

    def test_un_autre_chemin_est_un_404(self):
        with TemporaryDirectory() as d:
            faux, _ = poster(espace(d), self.corps(), '/api/tranche/autre')
            self.assertEqual(faux.reponses[0][0], 404)

    def test_les_mots_du_verdict_sont_ceux_du_banc(self):
        """Le serveur collecte, le banc conclut : deux vocabulaires differents
        donneraient un total qui ne correspond a aucun taux."""
        import mesure_tranche_seuil as T
        self.assertEqual(tuple(_constante('TRANCHE_VERDICTS')), T.VERDICTS)


class TestPromesse(unittest.TestCase):

    def test_le_gestionnaire_n_attribue_rien(self):
        src = ast.get_source_segment(SOURCE, _noeud('_do_tranche_post')) or ''
        for interdit in ECRITURES_INTERDITES:
            self.assertNotIn(interdit, src,
                             f"{interdit} dans _do_tranche_post : la page "
                             "cesserait d'etre une mesure.")

    def test_la_lecture_ne_touche_pas_au_fonds(self):
        src = ast.get_source_segment(SOURCE, _noeud('_serve_tranche_list')) or ''
        for interdit in ECRITURES_INTERDITES:
            self.assertNotIn(interdit, src)

    def test_la_page_dit_qu_elle_n_attribue_rien(self):
        """Une promesse tenue par le code mais tue par l'interface se perd :
        celui qui juge doit savoir que son verdict ne pose aucun nom."""
        page = _constante('TRANCHE_PAGE')
        self.assertIn('mesure', page)
        self.assertIn('attribue aucun nom', page)


if __name__ == '__main__':
    unittest.main()
