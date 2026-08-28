#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — la temperature entre dans le journal, et la sonde ne tue personne.

Pourquoi ce fichier
-------------------
Le 28/08 a 23:10:15 la machine s'est coupee net sous charge. Kernel-Power 41,
aucun minidump, rien dans le journal du serveur. Le seul indice etait indirect
-- la session qui est morte taguait a 27,2 s de moyenne contre 9,7 a 22,8 s
pour les autres du jour -- et je l'ai d'abord MAL LU, en comparant les durees
a l'interieur de la session (plates) au lieu d'entre les sessions (2 a 3 fois
plus lentes). Une deduction tiree d'un chronometre n'est pas une mesure.

Ces tests tiennent les trois choses qui font la difference entre un
thermometre utile et un thermometre decoratif :

1. **Une sonde ne LEVE jamais.** `hw_state` porte l'arbitre GPU et
   `system_busy` : un champ [N/A] sur une autre carte ne doit pas priver le
   serveur de sa propre VRAM. C'est le mode de panne que cette greffe pouvait
   CREER.
2. **Le journal parle quand il faut, et se tait sinon.** Bavard quand ca
   chauffe ou que la carte avoue brider, discret le reste du temps. Un journal
   qui deverse ne se lit pas ; un journal muet ne sert a rien.
3. **Le BASCULEMENT du bridage se trace**, pas seulement l'etat : c'est
   l'instant qu'on cherchera dans le journal apres coup.

Ils lisent `server.py` sans l'importer (`import server` ouvre `photos.db`,
dont le serveur est l'ecrivain unique). Vus ROUGES sur le code d'avant.
SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import ast
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "server.py"
SOURCE = SERVER.read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(
        f"{nom} introuvable dans server.py — si la sonde thermique a bouge, "
        "ces tests doivent etre RELUS, pas contournes.")


def _requete_gpu():
    """La chaine `--query-gpu=...` telle qu'elle part vers nvidia-smi."""
    for n in ast.walk(_noeud('hw_state')):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                and 'query-gpu' in n.value:
            return n.value
    raise AssertionError("requete --query-gpu introuvable dans hw_state")


def _constante(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.Assign):
            for c in n.targets:
                if isinstance(c, ast.Name) and c.id == nom:
                    return ast.literal_eval(n.value)
    raise AssertionError(f"{nom} introuvable dans server.py")


class Horloge:
    """Le temps a la main : un banc qui DORT dix minutes pour prouver un
    rythme de dix minutes ne sera jamais relance, donc ne protegera rien."""

    def __init__(self):
        self.t = 1000.0

    def maintenant(self):
        return self.t

    def dormir(self, s):
        self.t += s


def banc(releves):
    """`thermique_loop` branchee sur une suite de releves GPU a nous."""
    h = Horloge()
    suite = list(releves)
    lignes = []

    class FauxTime:
        time = staticmethod(h.maintenant)
        sleep = staticmethod(h.dormir)

    def faux_hw_state(force=False):
        if not suite:
            raise StopIteration          # sort de la boucle infinie
        return {'gpu': suite.pop(0)}

    espace = {
        '__builtins__': __builtins__,
        'time': FauxTime,
        'hw_state': faux_hw_state,
        'print': lambda *a, **k: lignes.append(' '.join(str(x) for x in a)),
        'THERMIQUE_PERIODE_S': _constante('THERMIQUE_PERIODE_S'),
        'THERMIQUE_TRACE_S': _constante('THERMIQUE_TRACE_S'),
        'THERMIQUE_CHAUD_C': _constante('THERMIQUE_CHAUD_C'),
    }
    mod = ast.Module(body=[_noeud('thermique_loop')], type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(SERVER), 'exec'), espace)
    try:
        espace['thermique_loop']()
    except StopIteration:
        pass
    return lignes


def froid(t=65, **kw):
    d = {'temp_c': t, 'util': 60, 'clocks_mhz': 1700, 'clocks_max_mhz': 2100,
         'watts': 38.0, 'bride_thermique': False}
    d.update(kw)
    return d


class LaSondeNeLevePas(unittest.TestCase):
    """Faute n. 1 — le mode de panne que cette greffe pouvait CREER."""

    def setUp(self):
        self.espace = {'__builtins__': __builtins__}
        mod = ast.Module(body=[_noeud('_nombre')], type_ignores=[])
        ast.fix_missing_locations(mod)
        exec(compile(mod, str(SERVER), 'exec'), self.espace)
        self.nombre = self.espace['_nombre']

    def test_un_champ_NA_rend_None_au_lieu_de_lever(self):
        for brut in ('[N/A]', '', 'Not Supported', None, 'abc'):
            self.assertIsNone(self.nombre(brut), repr(brut))

    def test_un_vrai_nombre_est_lu(self):
        self.assertEqual(self.nombre('64'), 64)
        self.assertEqual(self.nombre(' 2100 '), 2100)
        self.assertEqual(self.nombre('37.78', entier=False), 37.8)

    def test_la_requete_ne_demande_que_du_MESURE(self):
        """`power.limit` et `temperature.memory` rendent [N/A] sur cette carte,
        et un seul champ refuse fait echouer TOUTE la requete groupee -- sans
        dire lequel. Les inclure aveuglerait `hw_state` sur sa propre VRAM.

        On lit la CHAINE de la requete, pas le texte de la fonction : le
        commentaire qui explique l'exclusion cite justement les deux champs
        exclus. Un commentaire est de la PROSE -- regle du projet, et ce test
        s'y est cogne a sa premiere execution."""
        q = _requete_gpu()
        self.assertIn('temperature.gpu', q)
        self.assertIn('clocks_throttle_reasons.hw_thermal_slowdown', q)
        self.assertIn('clocks_throttle_reasons.sw_thermal_slowdown', q)
        self.assertNotIn('power.limit', q)
        self.assertNotIn('temperature.memory', q)


class LeJournalParleQuandIlFaut(unittest.TestCase):
    """Fautes n. 2 et 3 — bavard a propos, discret sinon."""

    def test_a_froid_une_ligne_de_reference_puis_le_rythme_lent(self):
        """Le premier releve s'ecrit TOUJOURS : c'est la ligne de reference du
        demarrage, celle qui dira plus tard a quelle temperature la machine
        partait. Ensuite, silence jusqu'au rythme lent."""
        periode = _constante('THERMIQUE_PERIODE_S')
        lent = _constante('THERMIQUE_TRACE_S')
        n = int(lent / periode)
        court = banc([froid()] * (n - 1))
        self.assertEqual(len(court), 1, (
            "avant le rythme lent, %d releves doivent rendre la SEULE ligne "
            "de reference, pas %d" % (n - 1, len(court))))
        self.assertIn('65', court[0])
        long_ = banc([froid()] * (n + 2))
        self.assertEqual(len(long_), 2, (
            "passe le rythme lent, une deuxieme ligne doit venir"))

    def test_chaud_trace_CHAQUE_releve(self):
        seuil = _constante('THERMIQUE_CHAUD_C')
        lignes = banc([froid(t=seuil + 3)] * 4)
        self.assertEqual(len(lignes), 4)
        self.assertTrue(all('CHAUD' in l for l in lignes))

    def test_le_bridage_se_dit_meme_a_temperature_normale(self):
        """Une carte peut brider AVANT d'atteindre le seuil : c'est justement
        le signal precoce qu'on cherche."""
        lignes = banc([froid(bride_thermique=True)])
        self.assertEqual(len(lignes), 1)
        self.assertIn('BRIDAGE THERMIQUE', lignes[0])

    def test_le_BASCULEMENT_est_trace_des_qu_il_arrive(self):
        """Le retour a la normale compte autant : c'est la fin de l'episode."""
        lignes = banc([froid(bride_thermique=True), froid()])
        self.assertEqual(len(lignes), 2, "la sortie de bridage n'a pas ete tracee")
        self.assertIn('BRIDAGE THERMIQUE', lignes[0])
        self.assertNotIn('BRIDAGE THERMIQUE', lignes[1])

    def test_sans_sonde_il_n_ecrit_JAMAIS(self):
        """Sur une machine sans GPU nvidia, le journal ne doit pas se remplir
        de lignes vides."""
        self.assertEqual(banc([{'temp_c': None}] * 30), [])


class LeFilEstSurveille(unittest.TestCase):
    def test_thermique_loop_passe_par_fil_surveille(self):
        src = SOURCE
        self.assertIn('fil_surveille(thermique_loop)', src)
        self.assertNotIn('threading.Thread(target=thermique_loop', src)


if __name__ == '__main__':
    unittest.main()
