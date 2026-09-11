#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L'horloge de PHASES sur `GET /api/maint/status` (11/09).

La page /reglages rappelle cette route toutes les 6 s ; l'horloge des routes la
donnait a 0,3-0,7 s par appel, quatre fois sur quatre, sans dire ou. Pour
poser des `top` entre les morceaux, les valeurs du grand dictionnaire sont
maintenant calculees AVANT lui. Ce banc tient ce que ce deplacement promet :

  1. **le corps rendu est IDENTIQUE**, cle pour cle, a celui de l'ancienne
     ecriture — recopiee verbatim ci-dessous et prise pour ORACLE, sur le meme
     monde simule ;
  2. les phases se succedent et couvrent la route ;
  3. le drapeau `sonde` dit si l'appel a lance nvidia-smi ou lu le cache ;
  4. **aucun chemin** n'entre dans le releve (`/api/perf` se lit sans garde
     admin, CLAUDE.md regle 10) — alors que la reponse, elle, en porte.
"""

import ast
import json
import os
import queue
import sys
import tempfile
import threading
import time as _time_reel
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
_LIGNES = SOURCE.splitlines(keepends=True)

# ── L'ORACLE : `_serve_maint_status` telle qu'elle etait au commit 26db8dc,
# recopiee sans rien changer (sauf l'indentation de methode). ──
ORACLE = r'''
def _serve_maint_status(self):
    """Etat consolide (lecture seule) : materiel, files, comptes, etat de la
    maintenance, resumes recensement/plan, config. Alimente /reglages."""
    import maintenance as _m
    docs = SCRIPT_DIR / 'docs'

    def load(name):
        try:
            return json.loads((docs / name).read_text(encoding='utf-8'))
        except Exception:
            return None

    def mtime_de(name):
        try:
            return (docs / name).stat().st_mtime
        except OSError:
            return None

    def summ(o):
        """Resume sur : garde les scalaires, remplace listes/dicts par leur
        taille. Robuste au schema (pas besoin de connaitre les cles)."""
        if not isinstance(o, dict):
            return {}
        r = {}
        for k, v in o.items():
            if isinstance(v, (int, float, str, bool)) or v is None:
                r[k] = v
            elif isinstance(v, list):
                r[f"{k} (n)"] = len(v)
            elif isinstance(v, dict):
                r[f"{k} (cles)"] = len(v)
        return r

    with PENDING_LOCK:
        tagpend = len(PENDING)
    # Stock d'empreintes animales (DINOv2) dans le magasin de vecteurs :
    # compte INDEXE (kind='animals'), instantane, lecture seule. Bien plus
    # parlant que le compteur de session (remis a 0 au demarrage). Repli None
    # si la base vectorielle n'est pas prete.
    try:
        pets_vec = photo_vectors().count('animals')
    except Exception:
        pets_vec = None
    body = {
        'now': time.time(),
        'hw': hw_state(),
        'busy': bool(system_busy() or ui_recent()),
        'queues': {'tag': TAG_QUEUE.qsize(), 'faces': FACE_QUEUE.qsize(),
                   'animaux': ANIMAL_QUEUE.qsize(), 'personnes': PERSON_QUEUE.qsize()},
        'pending': {'tag': tagpend, 'faces': len(FACE_PENDING),
                    'animaux': len(ANIMAL_PENDING)},
        'counts': {'entrees': len(STORE.data), 'tagues': STORE.tagged_count(),
                   'personnes': len(PEOPLE_STORE.data), 'animaux': len(PETS_STORE.data),
                   'visages': len(FACE_STORE.data)},
        # Empreintes animales : `pets_vec` = stock reel (magasin de vecteurs) ;
        # `pets_embed` = calculees depuis le demarrage (activite du worker de
        # fond) ; `dino_loaded` = modele charge (drapeau, PAS d'import lourd,
        # cf. invariant 7).
        'pets_vec': pets_vec,
        'pets_embed': PET_EMBED_STATE.get('done', 0),
        'dino_loaded': DINO_MODEL_OBJ is not None,
        # Boucle scan/backup (audit O5) + vérification de sauvegarde et
        # export des jugements (audit A) : rendus visibles dans /reglages.
        # I6 : l'arbitre VRAM et l'ordonnanceur n'existaient QUE dans
        # `/api/search/status` — la page qui montre l'état du serveur ne
        # savait donc rien des baux, des refus ni des évictions. Un
        # mécanisme qu'on ne voit pas ne se diagnostique pas.
        'gpu': (GPU.etat() if GPU is not None else None),
        'ordonnanceur': (ORDO.etat() if ORDO is not None else None),
        # I5 : le moteur des visages était AFFIRMÉ en dur (« CPU (seul
        # Ollama utilise le GPU) »), ce qui est faux depuis le GPU
        # adaptatif. Il se DIT maintenant, avec ce qu'il a fait en dernier.
        # Lu sur des DRAPEAUX, jamais en appelant `get_face_app()` : cet
        # appel CHARGE InsightFace (invariant 3), et une page d'état qui
        # monte un modèle pour dire s'il est monté serait le contraire
        # d'un instrument.
        'moteurs': {'visages': FACE_LAST_ENGINE or 'CPU',
                    'visages_gpu_pret': FACE_APP_GPU is not None,
                    'visages_gpu_erreur': FACE_GPU_ERROR or '',
                    'visages_gpu_voulu': FACE_USE_GPU},
        'boucle': dict(MAINT_LOOP_STATE,
                       # Un drapeau qu'on ne voit pas ne se prouve
                       # pas : c'est LUI qui fait maintenant céder
                       # la maintenance (is_busy), et sans lui le
                       # journal ne dirait rien tant qu'aucune étape
                       # n'est due.
                       scan_nas=scan_nas_en_cours()),
        # Comptes de l'index (chantier 10a) : qui retire des cles, combien,
        # et ce que personne n'explique. Toutes les listes sont bornees par
        # le registre lui-meme.
        'oublis': REGISTRE.resume(),
        'backup_verify': dict(BACKUP_VERIFY_STATE),
        # Backfills EXIF (dates, GPS) : morts en silence pendant des mois,
        # desormais observables (bug du 13/08, cf. _attendre_exiftool).
        'backfill': {k: dict(v) for k, v in BACKFILL_STATE.items()},
        'maint': {'auto': MAINTENANCE_AUTO, 'paused': MAINT_PAUSED,
                  'every_s': MAINTENANCE_EVERY, 'autonomy': _m.AUTONOMY,
                  'intervals': _m.INTERVALS, 'state': load('maintenance_state.json') or {},
                  'report': summ(load('maintenance_report.json'))},
        'recensement': summ(load('recensement.json')),
        'plan': summ(load('plan_rangement.json')),
        'plan_annee': (lambda pa: {
            'total_a_ranger': pa.get('total_a_ranger'),
            'sans_date': pa.get('sans_date'), 'deja': pa.get('deja'),
            'conflits': len(pa.get('conflits') or []),
            'par_annee': pa.get('par_annee') or {},
            # Quand le plan a ete ECRIT : c'est ce que la page attend pour
            # dire « fini » (le bouton ne l'a jamais dit, 29/08).
            'genere_le': mtime_de('plan_rangement_annee.json')})(
                load('plan_rangement_annee.json') or {}),
        'config': {'MODEL': MODEL, 'ANIMAL_PIPELINE_VERSION': ANIMAL_PIPELINE_VERSION,
                   'TAGGING_PIPELINE_VERSION': TAGGING_PIPELINE_VERSION,
                   'tagging_pipe': _tagging_pipe_counts(),
                   'retag': _retag_etat(),
                   'UPLOAD_DIR': str(UPLOAD_DIR),
                   'racines': [[label, str(r)] for label, r in media_roots()],
                   'FACE_MATCH_SIM': FACE_MATCH_SIM, 'PET_MATCH_SIM': PET_MATCH_SIM},
    }
    self._send(200, json.dumps(body, ensure_ascii=False, default=str).encode(),
               'application/json')
'''


_NOEUDS = {}
for _n in ast.walk(ARBRE):
    if isinstance(_n, (ast.FunctionDef, ast.ClassDef)):
        _NOEUDS.setdefault((type(_n), _n.name), _n)


# Les deux comptes que l'oracle appelait, tels qu'ils etaient (26db8dc) : le
# corps de l'oracle doit se calculer comme avant, pas avec la passe neuve.
ORACLE_COMPTES = r'''
def _tagging_pipe_counts():
    """Répartition des entrées taguées par version de pipeline (audit D) : les
    entrées antérieures à l'estampillage comptent comme « v0 ». Rendu visible
    dans /reglages — plus jamais d'index mixte silencieux. Lecture seule sur
    une copie instantanée du dict (pas de lock nécessaire)."""
    c = {}
    for e in list(STORE.data.values()):
        if isinstance(e, dict) and not e.get('failed'):
            v = e.get('pipe') or 'v0'
            c[v] = c.get(v, 0) + 1
    return c


def _retag_etat():
    """État de la campagne pour /api/serveur : la cible, ce qui reste, ce qui
    est en file, ce qui a été abandonné. Une campagne qui n'avance plus doit se
    VOIR — c'est la leçon des backfills morts en silence pendant des mois."""
    cible = retag_cible()
    if not cible:
        # Un levier POSÉ mais REFUSÉ doit se voir : sinon Mike lit « inactif »
        # alors qu'il vient de créer le fichier, et cherche au mauvais endroit.
        if _RETAG_REFUS_DIT['quoi']:
            return {'actif': False, 'refus': _RETAG_REFUS_DIT['quoi'],
                    'attendu': TAGGING_PIPELINE_VERSION}
        return {'actif': False}
    reste = abandons = 0
    for e in list(STORE.data.values()):
        if not isinstance(e, dict) or e.get('failed') or e.get('video'):
            continue
        if e.get('retag_fail') == cible:
            abandons += 1
        elif e.get('pipe') != cible:
            reste += 1
    with PENDING_LOCK:
        en_file = len(RETAG_PENDING)
    return {'actif': True, 'cible': cible, 'reste': reste, 'en_file': en_file,
            'abandons': abandons, 'lot': RETAG_LOT}
'''


def _src(nom, genre=ast.FunctionDef):
    n = _NOEUDS.get((genre, nom))
    if n is None:
        raise AssertionError(nom + ' introuvable dans server.py')
    return _segment(n)


def _segment(n):
    """Le texte d'un noeud, dedente. `ast.get_source_segment` recoupe les
    750 Ko du fichier a chaque appel : 7 s de banc pour rien."""
    import textwrap
    return textwrap.dedent(''.join(_LIGNES[n.lineno - 1:n.end_lineno])).rstrip('\n')


class _Horloge:
    """`time` dont `time()` est fige : 'now' doit valoir la meme chose dans
    les deux ecritures. `perf_counter` reste le vrai (les phases s'en servent)."""
    def __init__(self, t):
        self.t = t
        self.perf_counter = _time_reel.perf_counter

    def time(self):
        return self.t


class _Store:
    def __init__(self, data):
        self.data = data

    def tagged_count(self):
        return sum(1 for e in self.data.values()
                   if not e.get('failed') and (e.get('kw_fr') or e.get('kw_en')))


class _Vec:
    def count(self, kind):
        return 7 if kind == 'animals' else 0


def _monde(tmp, sonde_neuve=False, vecteurs_ko=False, cible='v3'):
    """Un monde simule, le meme pour l'oracle et pour la route instrumentee."""
    docs = Path(tmp) / 'docs'
    docs.mkdir()
    (docs / 'maintenance_state.json').write_text(json.dumps({'dernier': 12}), encoding='utf-8')
    (docs / 'maintenance_report.json').write_text(json.dumps(
        {'a': 1, 'l': [1, 2], 'd': {'x': 1}, 'n': None}), encoding='utf-8')
    (docs / 'recensement.json').write_text(json.dumps({'groupes': [[1], [2]]}), encoding='utf-8')
    # plan_rangement.json ABSENT : le repli doit etre le meme des deux cotes.
    (docs / 'plan_rangement_annee.json').write_text(json.dumps(
        {'total_a_ranger': 3, 'sans_date': 1, 'deja': 9, 'conflits': [1, 2],
         'par_annee': {'2020': 3}}), encoding='utf-8')
    # `genere_le` est le mtime du plan : le meme dans les deux mondes.
    os.utime(docs / 'plan_rangement_annee.json', (1789000000, 1789000000))
    hw_cache = {'at': 100.0, 'data': None}

    def hw_state(force=False):
        if sonde_neuve:
            hw_cache['at'] += 1.0
        return {'cpu_percent': 12.0, 'gpu': {'vram_free_mb': 900}}

    def photo_vectors():
        if vecteurs_ko:
            raise RuntimeError('pas de base')
        return _Vec()

    store = _Store({
        'N:/Photos/Mike/a.jpg': {'kw_fr': ['chat'], 'pipe': 'v3'},
        'N:/Photos/Mike/b.jpg': {'failed': True, 'pipe': 'v3'},
        'N:/Photos/Mike/c.jpg': {'kw_en': ['dog']},
        'N:/Photos/Mike/d.jpg': {},
        'N:/Photos/Mike/e.jpg': {'kw_fr': ['mer'], 'pipe': 'v2', 'retag_fail': 'v3'},
        'N:/Photos/Mike/f.mp4': {'video': True, 'pipe': 'v1'},
    })
    q = queue.Queue()
    q.put(1)
    m = types.ModuleType('maintenance')
    m.AUTONOMY = 'sur'
    m.INTERVALS = {'scan': 300}
    g = {
        'json': json, 'time': _Horloge(1789150000.5), 'threading': threading,
        'Path': Path, 'SCRIPT_DIR': Path(tmp),
        'PENDING_LOCK': threading.Lock(), 'PENDING': {'x', 'y'},
        'photo_vectors': photo_vectors, 'hw_state': hw_state, '_HW_CACHE': hw_cache,
        'system_busy': lambda: False, 'ui_recent': lambda: True,
        'TAG_QUEUE': q, 'FACE_QUEUE': queue.Queue(), 'ANIMAL_QUEUE': queue.Queue(),
        'PERSON_QUEUE': queue.Queue(),
        'FACE_PENDING': {'f'}, 'ANIMAL_PENDING': set(),
        'STORE': store, 'PEOPLE_STORE': _Store({'Mike': {}}),
        'PETS_STORE': _Store({'Inti': {}, 'Luna': {}}), 'FACE_STORE': _Store({}),
        'PET_EMBED_STATE': {'done': 4}, 'DINO_MODEL_OBJ': None,
        'GPU': types.SimpleNamespace(etat=lambda: {'baux': []}), 'ORDO': None,
        'FACE_LAST_ENGINE': '', 'FACE_APP_GPU': None, 'FACE_GPU_ERROR': None,
        'FACE_USE_GPU': False,
        'MAINT_LOOP_STATE': {'tour': 3}, 'scan_nas_en_cours': lambda: False,
        'REGISTRE': types.SimpleNamespace(resume=lambda: {'actif': True, 'retraits': 2}),
        'BACKUP_VERIFY_STATE': {'ok': True},
        'BACKFILL_STATE': {'dates': {'etat': 'fini'}, 'gps': {'etat': 'fini'}},
        'MAINTENANCE_AUTO': True, 'MAINT_PAUSED': False, 'MAINTENANCE_EVERY': 300,
        'retag_cible': lambda: cible, '_RETAG_REFUS_DIT': {'quoi': None},
        'RETAG_PENDING': {'z'}, 'RETAG_LOT': 50,
        'MODEL': 'qwen3.5:4b', 'ANIMAL_PIPELINE_VERSION': 'a', 'TAGGING_PIPELINE_VERSION': 't',
        'UPLOAD_DIR': Path('C:/Prog/Claude/MediaLibrary/uploads'),
        'media_roots': lambda: [('Uploads', Path('C:/u')), ('Photos Mike', Path('N:/Photos/Mike'))],
        'FACE_MATCH_SIM': 0.5, 'PET_MATCH_SIM': 0.6,
        'PERF_LOCK': threading.Lock(), 'PERF_PHASES': {}, 'PERF_DERNIERS': [],
        'PERF_MAX_DERNIERS': 20,
    }
    return g, m


class _Handler:
    def __init__(self):
        self.envois = []

    def _send(self, code, corps, ctype):
        self.envois.append((code, corps, ctype))


def _executer(code_fonction, g, m, oracle=False):
    ns = dict(g)
    exec(_src('_Phases', ast.ClassDef), ns)                        # noqa: S102
    exec(_src('_phases_note'), ns)                                  # noqa: S102
    if oracle:
        exec(ORACLE_COMPTES, ns)                                    # noqa: S102
    else:
        exec(_src('_passe_index'), ns)                              # noqa: S102
        exec(_src('_retag_etat'), ns)                               # noqa: S102
    exec(code_fonction, ns)                                         # noqa: S102
    h = _Handler()
    ancien = sys.modules.get('maintenance')
    sys.modules['maintenance'] = m
    try:
        ns['_serve_maint_status'](h)
    finally:
        if ancien is None:
            sys.modules.pop('maintenance', None)
        else:
            sys.modules['maintenance'] = ancien
    return h, ns


def _nouvelle():
    return _src('_serve_maint_status')


class LeCorpsNeChangePas(unittest.TestCase):
    def _comparer(self, **monde):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            g1, m1 = _monde(t1, **monde)
            g2, m2 = _monde(t2, **monde)
            ho, _ = _executer(ORACLE, g1, m1, oracle=True)
            hn, ns = _executer(_nouvelle(), g2, m2)
        self.assertEqual(len(ho.envois), 1)
        self.assertEqual(len(hn.envois), 1)
        co, cn = ho.envois[0], hn.envois[0]
        self.assertEqual(co[0], cn[0])
        self.assertEqual(co[2], cn[2])
        do, dn = json.loads(co[1]), json.loads(cn[1])
        # SCRIPT_DIR differe d'un monde a l'autre ; rien d'autre ne doit.
        self.assertEqual(do, dn)
        self.assertEqual(list(do.keys()), list(dn.keys()),
                         "l'ORDRE des cles est celui de l'oracle")
        return dn, ns

    def test_meme_corps_que_l_ORACLE(self):
        d, _ = self._comparer()
        # Le monde simule a bien ete lu (sinon l'egalite ne prouverait rien).
        self.assertEqual(d['counts']['tagues'], 3)
        self.assertEqual(d['config']['tagging_pipe'], {'v3': 1, 'v0': 2, 'v2': 1, 'v1': 1})
        self.assertEqual(d['config']['retag']['reste'], 2)
        self.assertEqual(d['config']['retag']['abandons'], 1)
        self.assertEqual(d['pets_vec'], 7)
        self.assertEqual(d['plan_annee']['conflits'], 2)
        self.assertEqual(d['plan'], {})
        self.assertEqual(d['maint']['report'], {'a': 1, 'l (n)': 2, 'd (cles)': 1, 'n': None})
        self.assertTrue(d['busy'])

    def test_meme_corps_quand_les_VECTEURS_manquent(self):
        d, _ = self._comparer(vecteurs_ko=True)
        self.assertIsNone(d['pets_vec'])

    def test_meme_corps_quand_la_sonde_TOURNE(self):
        self._comparer(sonde_neuve=True)

    def test_meme_corps_SANS_campagne(self):
        d, _ = self._comparer(cible=None)
        self.assertEqual(d['config']['retag'], {'actif': False})


class LesPhases(unittest.TestCase):
    def _releve(self, **monde):
        with tempfile.TemporaryDirectory() as t:
            g, m = _monde(t, **monde)
            _, ns = _executer(_nouvelle(), g, m)
        self.assertEqual(len(ns['PERF_DERNIERS']), 1)
        return ns['PERF_DERNIERS'][0], ns

    def test_les_phases_couvrent_la_route_DANS_L_ORDRE(self):
        r, _ = self._releve()
        self.assertEqual(r['route'], 'GET /api/maint/status')
        self.assertEqual(list(r['phases']), [
            'contexte', 'vecteurs', 'hw', 'files', 'passe', 'comptes',
            'arbitres', 'etats', 'docs', 'retag', 'config',
            'json', 'envoi'])

    def test_le_drapeau_SONDE(self):
        r, _ = self._releve(sonde_neuve=False)
        self.assertIs(r['info']['sonde'], False)
        r, _ = self._releve(sonde_neuve=True)
        self.assertIs(r['info']['sonde'], True)

    def test_des_comptes_JAMAIS_des_chemins(self):
        r, _ = self._releve()
        texte = json.dumps(r)
        for interdit in ('N:/', 'Photos', 'Mike', 'uploads', 'C:/'):
            self.assertNotIn(interdit, texte)
        self.assertEqual(set(r['info']), {'sonde', 'entrees', 'octets'})

    def test_le_chronometre_part_EN_PREMIER_et_se_range_EN_DERNIER(self):
        corps = _NOEUDS[(ast.FunctionDef, '_serve_maint_status')].body
        src = [_segment(s) for s in corps
               if not (isinstance(s, ast.Expr) and isinstance(getattr(s, 'value', None), ast.Constant))]
        premier = next(i for i, s in enumerate(src) if '_Phases(' in s)
        # Rien de CALCULE avant le chronometre, hors les petites definitions locales.
        for s in src[:premier]:
            self.assertTrue(s.startswith(('import ', 'docs =', 'def ')), s)
        self.assertEqual(src[-1], '_phases_note(ph)')


if __name__ == '__main__':
    unittest.main()
