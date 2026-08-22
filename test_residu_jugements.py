#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la page /residu — SUR LE CODE DE PROD.

Pourquoi par ANALYSE DU SOURCE, comme `test_tranche_jugements`
──────────────────────────────────────────────────────────────
`import server` construit les stores et ouvre `photos.db`, dont le serveur est
l'ecrivain unique (regle 4). Ce module extrait donc de l'AST les fonctions et
les methodes a eprouver et les joue dans un espace de noms a elles, avec des
fichiers temporaires. Ce n'est pas une copie du code : c'est le code, ailleurs.

Ce qui est verifie, et pourquoi
───────────────────────────────
1. **Un verdict ne peut designer qu'un visage MONTRE.** Sinon le banc
   conclurait sur un visage que personne n'a regarde, et une decision humaine
   se poserait sur une vue qui n'a pas eu lieu.
2. **« Aucun n'est elle » est un verdict**, pas une absence : la liste `oui`
   vide est legitime et se distingue d'un cas non juge.
3. **L'ecriture est atomique** et ne laisse pas de `.tmp` (invariant 2).
4. **La page n'attribue rien et ne retire rien** : le source des deux
   gestionnaires ne contient aucune fonction d'ecriture du fonds. Le retrait
   est un geste humain — c'est ce qui rend le jugement utilisable comme mesure.
5. **La planche de reference ecarte la photo EN CAUSE.** Montrer comme
   reference le visage qu'on est en train de juger ferait juger la piece a
   conviction contre elle-meme.

FUSEAU HORAIRE : sans objet.
"""

import ast
import json
import os
import unittest
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

ECRITURES_INTERDITES = ('_auto_add', 'STORE.save', 'PEOPLE_STORE.save',
                        'PETS_STORE.save', 'write_tags', 'enqueue',
                        'curator_accept', 'rekey_everywhere', 'exiftool',
                        'forget_everywhere')


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    raise AssertionError(f"{nom} introuvable dans server.py — la page /residu "
                         "a bouge, ce test doit etre relu avant d'etre cru.")


def _constante(nom):
    for n in ARBRE.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == nom:
            return ast.literal_eval(n.value)
    raise AssertionError(f"{nom} introuvable dans server.py")


class FauxStore:
    def __init__(self, data):
        self.data = data


class FauxSelf:
    def __init__(self, corps=None):
        self.corps = corps
        self.reponses = []

    def _read_json_body(self):
        return self.corps

    def _send(self, code, body, ctype):
        self.reponses.append((code, body, ctype))


CAS = {"key": r"\\NAS\p\groupe.jpg", "person": 'Didier', "visages": 12,
       "pourquoi": 'ambigu',
       "candidats": [{"i": 1, "sim": 0.908, "cite": True},
                     {"i": 8, "sim": 0.745, "cite": True}]}


def espace(dossier, fiches=None, cas=None):
    ns = {'json': json, 'os': os, 'time': __import__('time'),
          'urllib': urllib,
          'threading': __import__('threading'),
          'PEOPLE_STORE': FauxStore(fiches if fiches is not None else {}),
          'TRANCHE_REFS_MAX': _constante('TRANCHE_REFS_MAX'),
          'RESIDU_VERDICTS': _constante('RESIDU_VERDICTS'),
          'RESIDU_A_JUGER': Path(dossier) / '_residu_a_juger.json',
          'RESIDU_JUGEMENTS': Path(dossier) / '_residu_jugements.json',
          '_url_for_key': lambda k, *a: '/f/' + k,
          'note_heavy_activity': lambda: None,
          '_journal_jugement': lambda evt: None}
    ns['RESIDU_LOCK'] = ns['threading'].Lock()
    for nom in ('_residu_id', '_residu_lire_jugements',
                '_residu_ecrire_jugements', '_tranche_fiches_par_nom',
                '_tranche_refs_vivantes', '_crop_url', '_serve_residu_list',
                '_do_residu_post'):
        exec(compile(ast.Module([_noeud(nom)], []), str(SERVER), 'exec'), ns)
    if cas is not None:
        ns['RESIDU_A_JUGER'].write_text(
            json.dumps({"cas": cas}, ensure_ascii=False), encoding='utf-8')
    return ns


def poster(ns, corps, chemin='/api/residu/juger'):
    faux = FauxSelf(corps)
    ns['_do_residu_post'](faux, chemin)
    return faux


def lister(ns):
    faux = FauxSelf()
    ns['_serve_residu_list'](faux)
    code, body, _ = faux.reponses[-1]
    return code, json.loads(body.decode('utf-8'))


class TestVerdict(unittest.TestCase):

    def corps(self, **kw):
        c = {"key": CAS['key'], "person": 'Didier', "verdict": 'juge',
             "oui": [1], "candidats": [1, 8]}
        c.update(kw)
        return c

    def test_enregistre_un_jugement(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            faux = poster(ns, self.corps())
            self.assertEqual(faux.reponses[-1][0], 200)
            v = ns['_residu_lire_jugements']()[CAS['key'] + '|Didier']
            self.assertEqual(v['oui'], [1])
            self.assertEqual(v['non'], [8])

    def test_un_visage_hors_du_cas_est_REFUSE(self):
        """Le coeur de la promesse : un verdict ne porte que sur ce qui a ete
        MONTRE. Accepter i=5 ici ferait retirer ou poser une decision humaine
        sur un visage que personne n'a regarde."""
        with TemporaryDirectory() as d:
            ns = espace(d)
            faux = poster(ns, self.corps(oui=[5]))
            self.assertEqual(faux.reponses[-1][0], 400)
            self.assertEqual(ns['_residu_lire_jugements'](), {})

    def test_aucun_n_est_elle_est_un_verdict(self):
        """`oui` vide n'est pas une absence de reponse : c'est la reponse la
        plus lourde du lot — les deux couples cites sont a retirer."""
        with TemporaryDirectory() as d:
            ns = espace(d)
            self.assertEqual(poster(ns, self.corps(oui=[])).reponses[-1][0], 200)
            v = ns['_residu_lire_jugements']()[CAS['key'] + '|Didier']
            self.assertEqual(v['oui'], [])
            self.assertEqual(v['non'], [1, 8])

    def test_les_deux_visages_peuvent_etre_elle(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            poster(ns, self.corps(oui=[1, 8]))
            v = ns['_residu_lire_jugements']()[CAS['key'] + '|Didier']
            self.assertEqual((v['oui'], v['non']), ([1, 8], []))

    def test_refuse_un_verdict_inconnu(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            self.assertEqual(poster(ns, self.corps(verdict='peut-etre'))
                             .reponses[-1][0], 400)
            self.assertEqual(ns['_residu_lire_jugements'](), {})

    def test_refuse_un_cas_sans_photo_ou_sans_personne(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            self.assertEqual(poster(ns, self.corps(person='')).reponses[-1][0], 400)
            self.assertEqual(poster(ns, self.corps(key='')).reponses[-1][0], 400)

    def test_rejuger_remplace_au_lieu_d_empiler(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            poster(ns, self.corps(oui=[1]))
            poster(ns, self.corps(oui=[8]))
            v = ns['_residu_lire_jugements']()
            self.assertEqual(len(v), 1)
            self.assertEqual(v[CAS['key'] + '|Didier']['oui'], [8])

    def test_deux_personnes_sur_la_meme_photo_ne_s_ecrasent_pas(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            poster(ns, self.corps())
            poster(ns, self.corps(person='Flo'))
            self.assertEqual(len(ns['_residu_lire_jugements']()), 2)

    def test_un_autre_chemin_est_un_404(self):
        with TemporaryDirectory() as d:
            faux = poster(espace(d), self.corps(), '/api/residu/autre')
            self.assertEqual(faux.reponses[-1][0], 404)

    def test_ecriture_atomique_sans_tmp_derriere(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            poster(ns, self.corps())
            restes = [f for f in os.listdir(d) if f.endswith('.tmp')]
            self.assertEqual(restes, [])

    def test_fichier_abime_rend_une_seance_vierge_sans_tomber(self):
        with TemporaryDirectory() as d:
            ns = espace(d)
            ns['RESIDU_JUGEMENTS'].write_text('{ pas du json',
                                              encoding='utf-8')
            self.assertEqual(ns['_residu_lire_jugements'](), {})


class TestListe(unittest.TestCase):

    FICHES = {'didier': {'name': 'Didier',
                         'faces': [[CAS['key'], 1], ['ailleurs1.jpg', 0],
                                   ['ailleurs2.jpg', 2]]}}

    def test_chaque_candidat_recoit_sa_vignette(self):
        with TemporaryDirectory() as d:
            code, r = lister(espace(d, self.FICHES, [CAS]))
            self.assertEqual(code, 200)
            c = r['cas'][0]
            self.assertEqual(len(c['candidats']), 2)
            self.assertIn('i=1', c['candidats'][0]['crop_url'])
            self.assertIn('i=8', c['candidats'][1]['crop_url'])

    def test_la_planche_ECARTE_la_photo_en_cause(self):
        """Le visage juge ne peut pas servir de reference a son propre
        jugement."""
        with TemporaryDirectory() as d:
            _code, r = lister(espace(d, self.FICHES, [CAS]))
            urls = r['cas'][0]['refs_urls']
            self.assertEqual(len(urls), 2)
            quotee = urllib.parse.quote(CAS['key'], safe='')
            self.assertFalse(any(quotee in u for u in urls))

    def test_fichier_absent_ne_tombe_pas(self):
        with TemporaryDirectory() as d:
            code, r = lister(espace(d))
            self.assertEqual(code, 200)
            self.assertTrue(r['absent'])
            self.assertEqual(r['cas'], [])

    def test_les_verdicts_deja_poses_reviennent_avec_les_cas(self):
        with TemporaryDirectory() as d:
            ns = espace(d, self.FICHES, [CAS])
            poster(ns, {"key": CAS['key'], "person": 'Didier',
                        "verdict": 'juge', "oui": [1], "candidats": [1, 8]})
            _code, r = lister(ns)
            self.assertIn(CAS['key'] + '|Didier', r['verdicts'])


class TestPromesse(unittest.TestCase):

    def test_ni_le_post_ni_la_lecture_ne_touchent_au_fonds(self):
        for nom in ('_do_residu_post', '_serve_residu_list'):
            src = ast.get_source_segment(SOURCE, _noeud(nom)) or ''
            for interdit in ECRITURES_INTERDITES:
                self.assertNotIn(interdit, src,
                                 f"{interdit} dans {nom} : la page cesserait "
                                 "d'etre une mesure.")

    def test_les_mots_du_verdict_sont_ceux_du_banc(self):
        page = _constante('RESIDU_PAGE')
        for mot in _constante('RESIDU_VERDICTS'):
            self.assertIn(mot, page)

    def test_la_page_dit_qu_elle_ne_retire_rien(self):
        page = _constante('RESIDU_PAGE')
        self.assertIn('ne retire rien', page)
        self.assertIn('collecte', page)


if __name__ == '__main__':
    unittest.main()
