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
6. **La planche de reference est VIVANTE.** Le 22/08 elle etait figee dans le
   fichier de tirage : tiree a 21:26, elle montrait encore les couples d'avant
   le recalage applique a 22:19 — trois planches sur trente designaient
   quelqu'un d'autre, dont Didier et Mathieu, les deux fiches signalees a
   l'oeil la veille. Juger contre une reference perimee ne mesure rien, et
   elle se perime precisement la ou une reparation vient de passer.

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


class FauxStore:
    def __init__(self, data):
        self.data = data


def espace_planche(fiches):
    """`_tranche_refs_vivantes` et ses dependances, avec un magasin a nous."""
    ns = {'PEOPLE_STORE': FauxStore(fiches),
          'TRANCHE_REFS_MAX': _constante('TRANCHE_REFS_MAX')}
    for nom in ('_tranche_fiches_par_nom', '_tranche_refs_vivantes'):
        exec(compile(ast.Module([_noeud(nom)], []), str(SERVER), 'exec'), ns)
    return ns


def refs(fiches, nom):
    ns = espace_planche(fiches)
    return ns['_tranche_refs_vivantes'](nom, ns['_tranche_fiches_par_nom']())


class TestPlancheVivante(unittest.TestCase):

    FICHES = {'didier': {'name': 'Didier',
                         'avatar': ['av.jpg', 2],
                         'faces': [['a.jpg', 1], ['av.jpg', 2],
                                   ['b.jpg', 3], ['c.jpg', 0]]}}

    def test_l_avatar_vient_en_tete(self):
        self.assertEqual(refs(self.FICHES, 'Didier')[0], ('av.jpg', 2))

    def test_l_avatar_ne_compte_pas_deux_fois(self):
        """Il est aussi dans `faces` : le montrer deux fois volerait une place
        a une reference que la planche n'aurait alors jamais."""
        r = refs(self.FICHES, 'Didier')
        self.assertEqual(len(r), len(set(r)))
        self.assertEqual(r, [('av.jpg', 2), ('a.jpg', 1), ('b.jpg', 3)])

    def test_le_nombre_est_borne(self):
        self.assertLessEqual(len(refs(self.FICHES, 'Didier')),
                             _constante('TRANCHE_REFS_MAX'))

    def test_une_fiche_inconnue_rend_une_planche_vide(self):
        """Une personne sans fiche n'est pas une panne : la proposition reste
        jugeable, sans reference — et l'absence se VOIT."""
        self.assertEqual(refs(self.FICHES, 'Personne Qui N Existe Pas'), [])

    def test_la_casse_du_nom_ne_perd_pas_la_fiche(self):
        self.assertEqual(refs(self.FICHES, 'DIDIER'),
                         refs(self.FICHES, 'didier'))

    def test_un_couple_abime_est_ignore_sans_panne(self):
        f = {'didier': {'name': 'Didier', 'avatar': 'pas un couple',
                        'faces': [['a.jpg', 'x'], ['b.jpg'], ['c.jpg', 4]]}}
        self.assertEqual(refs(f, 'Didier'), [('c.jpg', 4)])


class TestLaPlancheNeVieillitPasAvecLeTirage(unittest.TestCase):
    """LE cas du 22/08, en un test.

    Le fichier de tirage porte les references d'avant la reparation ; la fiche
    porte celles d'apres. La page doit servir celles de la FICHE — sinon elle
    montre le visage que le recalage vient justement de corriger.
    """

    PERIME = ['\\NAS\Photos\groupe.jpg', 8]      # avant recalage
    RECALE = ['\\NAS\Photos\groupe.jpg', 1]      # apres recalage

    def _servir(self, dossier):
        fichier = Path(dossier) / '_tranche_a_juger.json'
        fichier.write_text(json.dumps({"items": [{
            "key": 'p.jpg', "i": 0, "person": 'Didier',
            "sim": 0.37, "refs": [self.PERIME],
        }]}, ensure_ascii=False), encoding='utf-8')
        ns = espace_planche({'didier': {'name': 'Didier',
                                        'faces': [self.RECALE]}})
        ns.update({'json': json, 'urllib': urllib,
                   'TRANCHE_A_JUGER': fichier,
                   'TRANCHE_LOCK': __import__('threading').Lock(),
                   '_url_for_key': lambda k, *a: '/f/' + k,
                   'note_heavy_activity': lambda: None})
        for nom in ('_tranche_id', '_tranche_lire_jugements', '_crop_url'):
            exec(compile(ast.Module([_noeud(nom)], []), str(SERVER), 'exec'), ns)
        ns['TRANCHE_JUGEMENTS'] = Path(dossier) / '_tranche_jugements.json'
        exec(compile(ast.Module([_noeud('_serve_tranche_list')], []),
                     str(SERVER), 'exec'), ns)
        faux = FauxSelf(None)
        ns['_serve_tranche_list'](faux)
        code, body, _ = faux.reponses[-1]
        self.assertEqual(code, 200)
        return json.loads(body.decode('utf-8'))['items'][0]

    def test_la_page_sert_la_reference_RECALEE(self):
        with TemporaryDirectory() as d:
            it = self._servir(d)
            self.assertEqual(it['refs'], [self.RECALE])
            self.assertIn('i=1', it['refs_urls'][0])

    def test_la_reference_perimee_du_fichier_est_ignoree(self):
        with TemporaryDirectory() as d:
            it = self._servir(d)
            self.assertNotIn(self.PERIME, it['refs'])
            self.assertNotIn('i=8', it['refs_urls'][0])


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

    def test_la_lecture_ne_reprend_pas_les_refs_du_tirage(self):
        """Garde contre le retour du defaut : si `_serve_tranche_list` relit
        `refs` dans le fichier de tirage, la planche re-vieillit avec lui."""
        src = ast.get_source_segment(SOURCE, _noeud('_serve_tranche_list')) or ''
        self.assertNotIn("c.get('refs')", src)
        self.assertIn('_tranche_refs_vivantes', src)

    def test_la_page_dit_qu_elle_n_attribue_rien(self):
        """Une promesse tenue par le code mais tue par l'interface se perd :
        celui qui juge doit savoir que son verdict ne pose aucun nom."""
        page = _constante('TRANCHE_PAGE')
        self.assertIn('mesure', page)
        self.assertIn('attribue aucun nom', page)


if __name__ == '__main__':
    unittest.main()
