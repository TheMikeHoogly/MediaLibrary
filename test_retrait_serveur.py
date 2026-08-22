#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la greffe du RETRAIT dans `server.py` — SUR LE CODE DE PROD.

Pourquoi ce fichier
───────────────────
La REGLE est testee ailleurs (`test_retrait_rattachements`, 13 cas). Ce qui
reste est la COURROIE, et elle porte le geste le plus dangereux du projet :
celui qui EFFACE une decision humaine. Trois choses doivent tenir ici, et
aucune ne se voit dans la regle pure :

1. **L'apercu ne touche a rien.** `dry=True` doit laisser la fiche intacte —
   sinon « voir ce qui partirait » deviendrait « faire partir ».
2. **Sans verdict, le geste REFUSE.** Un magasin de verdicts vide ne doit pas
   rendre « 0 retrait, tout va bien » : c'est le mode de panne muet que le
   projet a deja paye deux fois (`store.rekey` faux sans un mot, un croisement
   a 100 %). Il doit dire pourquoi.
3. **L'apercu et l'application comptent PAREIL.** Deux chemins, un chiffre.

Comme les autres tests de greffe, ce module lit `server.py` sans l'importer.
Les tests n'impriment rien (l'agent git capture la sortie).
"""

import ast
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

CLE = r"\\NAS\p\groupe.jpg"


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(f"{nom} introuvable dans server.py — la greffe du "
                         "retrait a bouge, ce test doit etre relu.")


class FauxStore:
    def __init__(self, data):
        self.data = data
        self.sauve = 0

    def set(self, k, v, save=True):
        self.data[k] = v

    def save(self):
        self.sauve += 1


CAS = {"person": "Res Jordi", "key": CLE, "visages": 4, "pourquoi": "ambigu",
       "candidats": [{"i": 1, "sim": 0.68, "cite": True},
                     {"i": 2, "sim": 0.69, "cite": True}]}


def espace(dossier, verdicts, fiches=None, cas=None):
    d = Path(dossier)
    (d / '_residu_a_juger.json').write_text(
        json.dumps({"cas": cas if cas is not None else [CAS]}),
        encoding='utf-8')
    (d / '_residu_jugements.json').write_text(
        json.dumps({"verdicts": verdicts}), encoding='utf-8')
    store = FauxStore(fiches if fiches is not None else {
        'res jordi': {"name": "Res Jordi",
                      "faces": [[CLE, 1], [CLE, 2], ["autre.jpg", 0]],
                      "exclude": ["x.jpg"], "confirmed": ["y.jpg"],
                      "avatar": [CLE, 1]}})
    ns = {'json': json, 'copy': __import__('copy'), 'time': __import__('time'),
          'Path': Path, 'threading': __import__('threading'),
          'PEOPLE_STORE': store,
          'CHAMPS_FICHE': ('faces', 'exclude', 'confirmed', 'avatar'),
          'RESIDU_A_JUGER': d / '_residu_a_juger.json',
          'RESIDU_JUGEMENTS': d / '_residu_jugements.json',
          'CORBEILLE_RETRAITS': d / '_corbeille_retraits',
          '_crop_url': lambda k, i: '/c?%s&i=%d' % (k, i),
          '_suggest_remove': lambda f: None,
          'print': lambda *a, **k: None}
    ns['RESIDU_LOCK'] = ns['threading'].Lock()
    for nom in ('_residu_lire_jugements', 'retirer_rattachements',
                'annuler_retrait'):
        exec(compile(ast.Module([_noeud(nom)], []), str(SERVER), 'exec'), ns)
    return ns, store


def verdict(oui, quoi='juge'):
    return {f"{CLE}|Res Jordi": {"verdict": quoi, "oui": list(oui)}}


class TestApercu(unittest.TestCase):

    def test_l_apercu_ne_touche_a_rien(self):
        with TemporaryDirectory() as d:
            ns, store = espace(d, verdict([2]))
            r = ns['retirer_rattachements'](dry=True)
            self.assertEqual(r['a_retirer'], 1)
            self.assertEqual(len(store.data['res jordi']['faces']), 3)
            self.assertEqual(store.sauve, 0)

    def test_l_apercu_et_l_application_comptent_pareil(self):
        with TemporaryDirectory() as d:
            ns, _s = espace(d, verdict([2]))
            a = ns['retirer_rattachements'](dry=True)['a_retirer']
        with TemporaryDirectory() as d:
            ns, _s = espace(d, verdict([2]))
            b = ns['retirer_rattachements'](dry=False)['retires']
        self.assertEqual(a, b)


class TestRefus(unittest.TestCase):

    def test_sans_verdict_il_REFUSE_et_dit_pourquoi(self):
        """« 0 retrait » se lirait comme « tout va bien ». Le mode de panne
        muet est celui que ce projet paye le plus cher."""
        with TemporaryDirectory() as d:
            ns, store = espace(d, {})
            r = ns['retirer_rattachements'](dry=False)
            self.assertFalse(r['ok'])
            self.assertIn('promesse', r['error'])
            self.assertEqual(len(store.data['res jordi']['faces']), 3)

    def test_sans_cas_il_REFUSE(self):
        with TemporaryDirectory() as d:
            ns, _s = espace(d, verdict([2]))
            ns['RESIDU_A_JUGER'] = Path(d) / 'absent.json'
            r = ns['retirer_rattachements'](dry=False)
            self.assertFalse(r['ok'])
            self.assertIn('--residu', r['error'])

    def test_une_fiche_inconnue_est_comptee_pas_creee(self):
        with TemporaryDirectory() as d:
            ns, store = espace(d, verdict([2]), fiches={})
            r = ns['retirer_rattachements'](dry=True)
            self.assertEqual(r['deja_absents'], 1)
            self.assertEqual(store.data, {})


class TestApplication(unittest.TestCase):

    def test_retire_le_bon_couple_et_garde_le_reste(self):
        with TemporaryDirectory() as d:
            ns, store = espace(d, verdict([2]))
            r = ns['retirer_rattachements'](dry=False)
            self.assertEqual(r['retires'], 1)
            f = store.data['res jordi']
            self.assertEqual(f['faces'], [[CLE, 2], ["autre.jpg", 0]])
            self.assertEqual(f['exclude'], ["x.jpg"])
            self.assertEqual(f['confirmed'], ["y.jpg"])

    def test_la_quarantaine_porte_l_AVANT_et_l_APRES(self):
        with TemporaryDirectory() as d:
            ns, _s = espace(d, verdict([2]))
            ns['retirer_rattachements'](dry=False)
            js = sorted((Path(d) / '_corbeille_retraits').glob('retrait_*.jsonl'))
            self.assertEqual(len(js), 1)
            lignes = [json.loads(x) for x in
                      js[0].read_text(encoding='utf-8').splitlines() if x.strip()]
            self.assertEqual(lignes[0]['retraits'], 1)
            self.assertEqual(len(lignes[1]['avant']['faces']), 3)
            self.assertEqual(len(lignes[1]['apres']['faces']), 2)

    def test_annuler_remet_la_fiche(self):
        with TemporaryDirectory() as d:
            ns, store = espace(d, verdict([2]))
            ns['retirer_rattachements'](dry=False)
            r = ns['annuler_retrait']()
            self.assertEqual(r['fiches_remises'], 1)
            self.assertEqual(len(store.data['res jordi']['faces']), 3)

    def test_annuler_ne_passe_pas_sur_une_fiche_modifiee_depuis(self):
        with TemporaryDirectory() as d:
            ns, store = espace(d, verdict([2]))
            ns['retirer_rattachements'](dry=False)
            store.data['res jordi']['faces'].append(["neuve.jpg", 0])
            r = ns['annuler_retrait']()
            self.assertEqual(r['fiches_remises'], 0)
            self.assertEqual(r['fiches_modifiees_depuis'], 1)

    def test_indecidable_ne_retire_rien(self):
        with TemporaryDirectory() as d:
            ns, store = espace(d, verdict([], 'indecidable'))
            r = ns['retirer_rattachements'](dry=False)
            self.assertEqual(r['retires'], 0)
            self.assertEqual(r['indecidables'], 1)
            self.assertEqual(len(store.data['res jordi']['faces']), 3)


if __name__ == '__main__':
    unittest.main()
