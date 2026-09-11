#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L'horloge de PHASES : ou partent les secondes d'une route, sans rien y changer.

L'horloge des routes (test_horloge_routes.py) dit QUELLE route coute. Le 11/09,
`/files` froid tombait de 31,4 s a 10,2 s apres `scandir`, et personne ne
savait ou passaient les 10 s restantes. Celle-ci le dit.

Memes devoirs que l'autre, dans le meme ordre :
  1. **ne jamais faire tomber la requete** ;
  2. compter juste — des phases qui se succedent, dont la somme est le total ;
  3. **ne rien changer a ce que la page calcule**. Les bancs du bas relisent
     `_serve_gallery` par l'arbre syntaxique : les appels chronometres ont
     garde leurs arguments exacts.

Et un quatrieme, propre a celle-ci : `/api/perf` se lit sans garde admin, donc
**aucun nom de dossier** ne doit y entrer (CLAUDE.md, regle 10).
"""

import ast
import json
import tempfile
import threading
import time
import types
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)


def _noeud(nom, genre=ast.FunctionDef):
    for n in ast.walk(ARBRE):
        if isinstance(n, genre) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable dans server.py')


def _src(nom, genre=ast.FunctionDef):
    return ast.get_source_segment(SOURCE, _noeud(nom, genre)) or ''


def _horloge(tmp):
    import os as _os
    m = types.ModuleType('perf')
    m.__dict__.update({
        'threading': threading, 'time': time, 'json': json, 'os': _os,
        'urllib': urllib, 'Path': Path,
        'PERF_LOCK': threading.Lock(), 'PERF_ROUTES': {},
        'PERF_DEPUIS': time.time(), 'PERF_MAX_ROUTES': 300,
        'PERF_SEUILS': (30, 100, 300, 1000, 3000),
        'PERF_PHASES': {}, 'PERF_DERNIERS': [], 'PERF_MAX_DERNIERS': 20,
        'SCRIPT_DIR': Path(tmp), 'PERF_FICHIER': Path(tmp) / '_perf_routes.json',
    })
    exec(_src('_Phases', ast.ClassDef), m.__dict__)                # noqa: S102
    for nom in ('_route_perf', '_perf_note', '_phases_note', 'perf_tableau',
                'perf_ecrire'):
        exec(_src(nom), m.__dict__)                                # noqa: S102
    return m


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.m = _horloge(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class LeChronometre(_Base):
    def test_les_phases_se_SUCCEDENT_et_leur_somme_est_le_total(self):
        """Un trou dans la liste doit se voir comme une phase, pas comme un
        temps disparu : chaque `top` range ce qui s'est ecoule depuis le
        precedent."""
        ph = self.m._Phases('GET /x')
        time.sleep(0.02)
        ph.top('a')
        time.sleep(0.04)
        ph.top('b')
        total = (time.perf_counter() - ph.t0) * 1000.0
        self.assertGreaterEqual(ph.ms['a'], 15)
        self.assertGreaterEqual(ph.ms['b'], 35)
        self.assertLess(ph.ms['a'], ph.ms['b'])
        self.assertAlmostEqual(ph.ms['a'] + ph.ms['b'], total, delta=5)

    def test_une_SOUS_phase_ne_deplace_pas_le_curseur(self):
        """`ajoute` range un accumulateur de boucle ; il ne doit pas voler le
        temps de la phase suivante."""
        ph = self.m._Phases('GET /x')
        ph.ajoute('enrichir.faits', 0.5)
        time.sleep(0.02)
        ph.top('enrichir')
        self.assertAlmostEqual(ph.ms['enrichir.faits'], 500.0)
        self.assertGreaterEqual(ph.ms['enrichir'], 15)
        self.assertLess(ph.ms['enrichir'], 400)

    def test_un_nom_repete_S_ADDITIONNE(self):
        ph = self.m._Phases('GET /x')
        ph.ajoute('a', 0.1)
        ph.ajoute('a', 0.2)
        self.assertAlmostEqual(ph.ms['a'], 300.0)


class CeQuiEstRange(_Base):
    def _execution(self, ms_par_phase, **info):
        ph = self.m._Phases('GET /files')
        for nom, ms in ms_par_phase.items():
            ph.ajoute(nom, ms / 1000.0)
        ph.note(**info)
        self.m._phases_note(ph)

    def test_agregat_par_phase_appels_total_et_pire(self):
        self._execution({'parcours': 100, 'enrichir': 900})
        self._execution({'parcours': 300, 'enrichir': 100})
        agr = self.m.perf_tableau()['phases']['GET /files']
        self.assertEqual(agr['parcours']['n'], 2)
        self.assertAlmostEqual(agr['parcours']['ms'], 400)
        self.assertAlmostEqual(agr['parcours']['max'], 300)
        self.assertAlmostEqual(agr['enrichir']['max'], 900)
        self.assertEqual(agr['(total)']['n'], 2)

    def test_le_detail_des_DERNIERES_executions_est_borne(self):
        """C'est le detail d'UNE ouverture froide qu'on veut lire : l'agregat
        la noierait dans les ouvertures chaudes. Mais sans borne, c'est de la
        memoire qui grossit a chaque clic."""
        for i in range(self.m.PERF_MAX_DERNIERS + 7):
            self._execution({'parcours': i}, fichiers=i)
        d = self.m.perf_tableau()['derniers']
        self.assertEqual(len(d), self.m.PERF_MAX_DERNIERS)
        self.assertEqual(d[-1]['info']['fichiers'],
                         self.m.PERF_MAX_DERNIERS + 6)     # les PLUS RECENTS
        self.assertEqual(d[0]['info']['fichiers'], 7)

    def test_le_tableau_reste_du_JSON_et_part_dans_le_fichier(self):
        self.m._perf_note('GET', '/files', 10)
        self._execution({'json': 12.5}, mode='dossier', rec=False)
        self.assertTrue(self.m.perf_ecrire())
        t = json.loads(self.m.PERF_FICHIER.read_text(encoding='utf-8'))
        self.assertIn('GET /files', t['phases'])
        self.assertEqual(t['derniers'][0]['info']['mode'], 'dossier')

    def test_le_tableau_rendu_est_une_COPIE(self):
        """Un lecteur de `/api/perf` qui serialise pendant qu'une requete note
        ne doit pas tenir les dictionnaires vivants."""
        self._execution({'a': 1})
        t = self.m.perf_tableau()
        t['phases']['GET /files']['a']['n'] = 999
        t['derniers'][0]['info']['x'] = 1
        self.assertEqual(self.m.PERF_PHASES['GET /files']['a']['n'], 1)
        self.assertNotIn('x', self.m.PERF_DERNIERS[0]['info'])


class ElleNeCassePasLaRequete(_Base):
    def test_un_chronometre_ABIME_ne_leve_pas(self):
        class Abime:
            route = 'GET /x'
            t0 = 'pas un nombre'
            ms = None
            info = None
        self.m._phases_note(Abime())          # ne doit pas lever
        self.m._phases_note(None)             # ni ceci

    def test_plusieurs_FILS_notent_ensemble(self):
        def bruit():
            for _ in range(100):
                ph = self.m._Phases('GET /files')
                ph.ajoute('a', 0.001)
                self.m._phases_note(ph)
        fils = [threading.Thread(target=bruit) for _ in range(8)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(self.m.PERF_PHASES['GET /files']['a']['n'], 800)
        self.assertEqual(len(self.m.PERF_DERNIERS), self.m.PERF_MAX_DERNIERS)


# ─── Les bancs qui relisent `_serve_gallery` ──────────────────────────────
GALERIE = _noeud('_serve_gallery')


def _appels(noeud, nom):
    out = []
    for n in ast.walk(noeud):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id == nom) or \
                    (isinstance(f, ast.Attribute) and f.attr == nom):
                out.append(n)
    return out


def _tops():
    """Les noms passes a `ph.top`, dans l'ordre du texte."""
    tops = []
    for n in ast.walk(GALERIE):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'top' and isinstance(n.func.value, ast.Name)
                and n.func.value.id == 'ph'):
            tops.append((n.lineno, n.args[0].value))
    return [t for _l, t in sorted(tops)]


class ElleEstPoseeDansLaGalerie(unittest.TestCase):
    def test_le_chronometre_part_EN_PREMIER_et_se_range_EN_DERNIER(self):
        premier = GALERIE.body[0]
        self.assertIn("_Phases('GET /files')", ast.unparse(premier))
        dernier = GALERIE.body[-1]
        self.assertEqual(ast.unparse(dernier), '_phases_note(ph)')
        # et apres l'envoi : sinon la phase la plus lourde (gzip + socket)
        # sortirait du compte
        textes = [ast.unparse(s) for s in GALERIE.body]
        self.assertLess(textes.index('self._send_html(page)'),
                        textes.index('_phases_note(ph)'))

    def test_les_phases_qui_couvrent_le_chemin_d_un_DOSSIER(self):
        """Dans l'ordre ou la page les traverse. Une phase oubliee ne fausse
        pas le total — elle se deverse dans la suivante — mais elle ment sur
        le coupable."""
        attendues = ['prelude', 'index', 'parcours', 'barre', 'carte_cles',
                     'faits_ctx', 'enrichir', 'motifs', 'marques', 'json',
                     'tagged_count', 'gabarit', 'envoi']
        tops = _tops()
        pos = [tops.index(a) for a in attendues]
        self.assertEqual(pos, sorted(pos), tops)

    def test_les_appels_chronometres_ont_garde_leurs_ARGUMENTS(self):
        """Sortis du litteral pour etre mesures — mais la meme cle, la meme
        entree, le meme contexte. Une virgule deplacee ici changerait la date
        d'une photo, sans qu'aucune horloge ne le dise."""
        boucle = [n for n in ast.walk(GALERIE) if isinstance(n, ast.For)
                  and ast.unparse(n.target) == 'f'][0]
        attendu = {
            '_best_time': '_best_time(fkey or str(f), entry)',
            '_jour_de': '_jour_de(fkey or str(f), entry)',
            '_faits_pour': '_faits_pour(fkey or str(f), entry, fctx)',
        }
        for nom, texte in attendu.items():
            vus = [ast.unparse(c) for c in _appels(boucle, nom)]
            self.assertEqual(vus, [texte], nom)

    def test_le_json_de_la_planche_est_calcule_UNE_fois(self):
        vus = [ast.unparse(c) for c in _appels(GALERIE, 'dumps')
               if ast.unparse(c.args[0]) == 'file_data']
        self.assertEqual(vus, ['json.dumps(file_data, ensure_ascii=False)'])
        self.assertEqual(len(_appels(GALERIE, 'tagged_count')), 1)

    def test_AUCUN_nom_de_dossier_n_entre_dans_le_releve(self):
        """`/api/perf` se lit sans garde admin. Un dossier prive n'a rien a y
        faire — le mode, les comptes et les millisecondes suffisent."""
        interdits = {'dirparam', 'folder', 'sub', 'f', 'fkey', 'qparam',
                     'simparam', 'jourparam', 'folders_html', 'file_data'}
        for c in _appels(GALERIE, 'note'):
            if not (isinstance(c.func.value, ast.Name) and c.func.value.id == 'ph'):
                continue
            noms = {n.id for kw in c.keywords for n in ast.walk(kw.value)
                    if isinstance(n, ast.Name)}
            # `len(file_data)` est un compte, pas un contenu : on l'autorise
            # explicitement, et rien d'autre
            noms.discard('len')
            directs = {kw.arg for kw in c.keywords
                       if isinstance(kw.value, ast.Name)}
            self.assertFalse(directs & interdits, ast.unparse(c))
            for kw in c.keywords:
                if isinstance(kw.value, ast.Call) and \
                        ast.unparse(kw.value.func) == 'len':
                    continue
                fuite = {n.id for n in ast.walk(kw.value)
                         if isinstance(n, ast.Name)} & (interdits - {'file_data'})
                self.assertFalse(fuite, ast.unparse(c))

    def test_l_horloge_des_routes_n_a_PAS_bouge(self):
        """Celle-ci s'ajoute a l'autre ; elle ne la remplace pas."""
        self.assertIn('_perf_note(', _src('do_GET'))
        self.assertNotIn('_Phases(', _src('do_GET'))



class ElleEstPoseeSurLaCarte(unittest.TestCase):
    """`/api/geo` (11/09 au soir) : même instrument, mêmes règles."""

    def test_premier_et_dernier_geste(self):
        n = _noeud('_serve_geo')
        corps = n.body[1:] if isinstance(n.body[0], ast.Expr) else n.body
        self.assertIn("_Phases('GET /api/geo')", ast.unparse(corps[0]))
        self.assertEqual(ast.unparse(n.body[-1]), '_phases_note(ph)')
        src = ast.unparse(n)
        self.assertLess(src.index("self._send(200, body, 'application/json')"),
                        src.index('_phases_note(ph)'))

    def test_des_comptes_jamais_des_cles(self):
        for c in _appels(_noeud('_serve_geo'), 'note'):
            self.assertEqual(sorted(kw.arg for kw in c.keywords),
                             ['entrees', 'octets', 'points'])
            for kw in c.keywords:
                self.assertEqual(ast.unparse(kw.value.func), 'len')


if __name__ == '__main__':
    unittest.main(verbosity=2)
