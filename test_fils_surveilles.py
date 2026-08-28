#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — un fil de travail mort se relance, et cinq morts d'affilée alertent.

Pourquoi ce fichier
───────────────────
Le 27/08 à 23:42:50, `tagger_worker` est mort. Sa file s'est remplie, le
serveur est resté d'apparence parfaitement vivante, et la panne a été
découverte à 07:43 par un HUMAIN qui lisait le journal — huit heures de
tagging perdues. `journal_serveur` posait pourtant le constat depuis le
23/08 ; son propre commentaire décrit le cas mot pour mot. Personne ne le
lisait, et aucun des vingt fils de `main()` ne se relançait.

Règle de Mike (28/08) : **le fil mort SE RELANCE, cinq morts consécutives
ALERTENT.** Ces tests tiennent les quatre points où cette règle peut se
trahir en silence :

1. **Il repart.** Sinon rien n'a changé.
2. **« Consécutives » se compte sur les morts SANS reprise entre elles.** Un
   fil qui a travaillé cinq minutes remet le compteur à zéro — sinon une mort
   par jour finirait par ressembler à une boucle et l'alerte perdrait son sens.
3. **Une tâche à un coup a le droit de FINIR**, et ne se rejoue pas. Relancer
   un backfill qui a réussi lui ferait refaire son travail sans le savoir ;
   c'est le mode de panne que ce mécanisme pourrait CRÉER.
4. **La trace survit.** En rattrapant l'exception, le superviseur prive
   `threading.excepthook` de son passage. Sans la réimprimer, on échangerait
   huit heures d'arrêt contre la perte du diagnostic qui a permis de
   comprendre la panne.

Ces tests lisent `server.py` **sans l'importer** (`import server` ouvre
`photos.db`, dont le serveur est l'écrivain unique) : les fonctions sont
extraites de l'AST et exécutées avec des faux à nous.

Chacun a été vu ROUGE sur le code d'avant. Les tests n'impriment rien
(l'agent git capture la sortie, et sa console est en cp1252).
"""

import ast
import io
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

FONCTIONS = ('fils_etat', '_fil_note', '_fil_tourne', 'fil_surveille')
CONSTANTES = ('FIL_REPRISE_S', 'FIL_ALERTE', 'FIL_PAUSE_S', 'FIL_PAUSE_MAX_S',
              'FIL_RAPPEL_S')


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(
        f"{nom} introuvable dans server.py — si la surveillance des fils a "
        "bouge, ces tests doivent etre RELUS, pas contournes.")


def _constante(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.Assign):
            for c in n.targets:
                if isinstance(c, ast.Name) and c.id == nom:
                    return ast.literal_eval(n.value)
    raise AssertionError(f"{nom} introuvable dans server.py")


def banc():
    """Les fonctions de la prod, dans un monde à nous : horloge et sommeil
    tenus à la main. Le temps ne doit JAMAIS être un ingrédient d'un banc —
    un test qui dort cinq minutes pour prouver un seuil de cinq minutes ne
    sera pas relancé, donc ne protégera rien."""
    espace = {
        '__builtins__': __builtins__,
        'threading': threading, 'time': time, 'traceback': _FauxTrace(),
        'FILS': {}, 'FILS_LOCK': threading.Lock(),
    }
    for nom in CONSTANTES:
        espace[nom] = _constante(nom)
    mod = ast.Module(body=[_noeud(n) for n in FONCTIONS], type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(SERVER), 'exec'), espace)
    return espace


class _FauxTrace:
    """Un faux `traceback` qui COMPTE au lieu d'imprimer."""

    def __init__(self):
        self.appels = 0

    def print_exc(self):
        self.appels += 1


class Horloge:
    """Une horloge qu'on avance à la main, et le sommeil qui va avec."""

    def __init__(self, espace):
        self.t = 1000.0
        self.dormi = []
        self._vrai = espace['time'].time

    def maintenant(self):
        return self.t

    def dormir(self, s):
        self.dormi.append(s)
        self.t += s


def _greffe_horloge(espace, horloge):
    """`time.time` du module remplacé — sans toucher au vrai `time`."""
    class FauxTime:
        time = staticmethod(horloge.maintenant)
        sleep = staticmethod(horloge.dormir)
    espace['time'] = FauxTime


class TestIlRepart(unittest.TestCase):
    """Point 1 — sinon rien n'a changé."""

    def setUp(self):
        self.e = banc()
        self.h = Horloge(self.e)
        _greffe_horloge(self.e, self.h)

    def test_un_fil_qui_meurt_est_relance(self):
        tours = []

        def cible():
            tours.append(1)
            raise RuntimeError("database is locked")

        with redirect_stdout(io.StringIO()):
            self.e['_fil_tourne'](cible, 'tagueur', True, (), self.h.dormir,
                                  lambda n: n < 3)
        self.assertEqual(len(tours), 3, "le fil n'a pas ete relance")
        etat = self.e['fils_etat']()['tagueur']
        self.assertEqual(etat['morts'], 3)
        self.assertEqual(etat['consecutives'], 3)

    def test_l_attente_double_au_lieu_de_marteler(self):
        with redirect_stdout(io.StringIO()):
            self.e['_fil_tourne'](_meurt, 'tagueur', True, (), self.h.dormir,
                                  lambda n: n < 4)
        self.assertEqual(self.h.dormi, [1.0, 2.0, 4.0, 8.0])

    def test_un_fil_qui_REND_est_une_mort_aussi(self):
        """Un worker qui sort de sa boucle sans erreur laisse sa file se
        remplir tout aussi surement qu'un worker qui leve."""
        with redirect_stdout(io.StringIO()):
            self.e['_fil_tourne'](lambda: None, 'tagueur', True, (),
                                  self.h.dormir, lambda n: n < 2)
        etat = self.e['fils_etat']()['tagueur']
        self.assertEqual(etat['morts'], 2)
        self.assertIn('rendu sans erreur', etat['erreur'])


class TestLeCompteurEtLAlerte(unittest.TestCase):
    """Point 2 — « consécutives », et ce qui le remet à zéro."""

    def setUp(self):
        self.e = banc()
        self.h = Horloge(self.e)
        _greffe_horloge(self.e, self.h)

    def test_cinq_morts_d_affilee_alertent(self):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            self.e['_fil_tourne'](_meurt, 'tagueur', True, (), self.h.dormir,
                                  lambda n: n < self.e['FIL_ALERTE'])
        etat = self.e['fils_etat']()['tagueur']
        self.assertEqual(etat['consecutives'], self.e['FIL_ALERTE'])
        self.assertTrue(etat['alerte'], "cinq morts d'affilee n'ont pas alerte")
        self.assertIn('ALERTE', sortie.getvalue())

    def test_quatre_morts_n_alertent_pas(self):
        """Contrôle NÉGATIF : un mécanisme qui alerte toujours n'alerte pas."""
        with redirect_stdout(io.StringIO()):
            self.e['_fil_tourne'](_meurt, 'tagueur', True, (), self.h.dormir,
                                  lambda n: n < self.e['FIL_ALERTE'] - 1)
        self.assertFalse(self.e['fils_etat']()['tagueur']['alerte'])

    def test_une_reprise_qui_TIENT_remet_le_compteur_a_zero(self):
        seuil = self.e['FIL_REPRISE_S']
        horloge = self.h

        def cible(tenu=[False]):
            # la 3e vie travaille plus longtemps que le seuil de reprise
            if len(horloge.dormi) == 2:
                horloge.t += seuil + 1
            raise RuntimeError("boum")

        with redirect_stdout(io.StringIO()):
            self.e['_fil_tourne'](cible, 'tagueur', True, (), self.h.dormir,
                                  lambda n: n < 4)
        etat = self.e['fils_etat']()['tagueur']
        self.assertEqual(etat['morts'], 4)
        self.assertEqual(etat['consecutives'], 2, (
            "une reprise qui a tenu plus de %ds n'a pas remis le compteur "
            "a zero : cinq morts etalees sur cinq jours finiraient par "
            "alerter comme une boucle" % seuil))


class TestUneTacheAUnCoupADroitDeFinir(unittest.TestCase):
    """Point 3 — le mode de panne que ce mécanisme pourrait CRÉER."""

    def setUp(self):
        self.e = banc()
        self.h = Horloge(self.e)
        _greffe_horloge(self.e, self.h)

    def test_un_backfill_qui_reussit_n_est_pas_rejoue(self):
        tours = []
        with redirect_stdout(io.StringIO()):
            self.e['_fil_tourne'](lambda: tours.append(1), 'backfill:gps',
                                  False, (), self.h.dormir, lambda n: n < 50)
        self.assertEqual(len(tours), 1, (
            "une tache a un coup a ete rejouee : un backfill relance en "
            "boucle referait son travail sans le savoir"))
        etat = self.e['fils_etat']()['backfill:gps']
        self.assertTrue(etat['fini'])
        self.assertEqual(etat['morts'], 0)

    def test_un_backfill_qui_echoue_se_DIT_mais_ne_se_rejoue_pas(self):
        tours = []

        def cible():
            tours.append(1)
            raise RuntimeError("NAS injoignable")

        with redirect_stdout(io.StringIO()):
            self.e['_fil_tourne'](cible, 'backfill:gps', False, (),
                                  self.h.dormir, lambda n: n < 50)
        self.assertEqual(len(tours), 1)
        etat = self.e['fils_etat']()['backfill:gps']
        self.assertEqual(etat['morts'], 1)
        self.assertIn('NAS injoignable', etat['erreur'])


class TestLaTraceSurvit(unittest.TestCase):
    """Point 4 — ne pas échanger huit heures d'arrêt contre le diagnostic."""

    def test_la_trace_est_reimprimee(self):
        e = banc()
        h = Horloge(e)
        _greffe_horloge(e, h)
        with redirect_stdout(io.StringIO()):
            e['_fil_tourne'](_meurt, 'tagueur', True, (), h.dormir,
                             lambda n: n < 2)
        self.assertEqual(e['traceback'].appels, 2, (
            "le superviseur rattrape l'exception, donc threading.excepthook "
            "ne la verra plus : sans reimpression la trace est PERDUE"))


class TestLesVingtFilsSontSurveilles(unittest.TestCase):
    """Le garde-fou de source : un fil lancé à la main est un fil sans filet."""

    def test_plus_aucun_threading_Thread_nu_dans_main(self):
        nus = []
        for n in ast.walk(ARBRE):
            if not (isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == 'Thread'
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == 'threading'):
                continue
            # celui du superviseur lui-meme est le seul legitime
            if n.lineno in _lignes_de(_noeud('fil_surveille')):
                continue
            cibles = [k.value for k in n.keywords if k.arg == 'target']
            noms = [getattr(c, 'id', None) for c in cibles]
            if any(x in _FILS_DE_MAIN for x in noms):
                nus.append((n.lineno, noms))
        self.assertEqual(nus, [], (
            f"fil(s) de travail lance(s) sans surveillance : {nus} — "
            "c'est la forme exacte qui a coute huit heures le 27/08"))


_FILS_DE_MAIN = {
    'tagger_worker', 'maintenance_loop', '_backfill', 'reconcile_named_tags',
    'face_worker', 'face_scan_loop', 'animal_worker', 'animal_scan_loop',
    'pet_embed_loop', 'rederive_pet_refs', 'cat_curator_loop', 'person_writer',
    'curator_loop', 'reembed_loop', 'semantic_loop', 'maintenance_orchestrator',
    'pilotage_loop',
}


def _lignes_de(noeud):
    return range(noeud.lineno, (noeud.end_lineno or noeud.lineno) + 1)


def _meurt():
    raise RuntimeError("database is locked")


if __name__ == '__main__':
    unittest.main()
