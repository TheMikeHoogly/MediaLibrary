#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — un verrou SQLite passager ne tue plus personne.

Pourquoi ce fichier
───────────────────
Le 27/08 à 23:42:50, le tagueur est mort. La séquence, lue dans
`_journal_serveur.log`, tient en trois lignes :

    ✗ Erreur tagging <photo>: database is locked — listé sur /sante
    THREAD MORT : Thread-2 (tagger_worker) : OperationalError: database is locked

`STORE.set` a échoué sur un verrou ; le gestionnaire d'erreur du tagueur a
alors réécrit dans la MÊME base encore verrouillée ; cette seconde erreur,
levée DANS le `except`, n'était rattrapée par personne. Le thread est mort,
la file s'est remplie, et le serveur est resté parfaitement vivant à ne rien
faire. Windows a redémarré la machine huit heures plus tard : il n'a
interrompu qu'un serveur qui ne travaillait déjà plus.

Deux fautes distinctes, donc deux verrous à poser, et ces tests les séparent :

1. **Un refus transitoire ne doit pas remonter.** La base a plusieurs
   écrivains légitimes (les magasins, la sauvegarde de 00:30). Un verrou de
   trois secondes est de l'attente, pas une panne.
2. **Un rattrapage ne doit jamais dépendre de la ressource qui vient de
   tomber.** C'est la faute qui a réellement tué le fil, et c'est la plus
   générale des deux.

Chacun a été vu ROUGE sur le code d'avant : sans ça, ils ne prouveraient rien.
Les tests n'impriment rien d'utile (l'agent git capture la sortie).
"""

import ast
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import store_sqlite

RACINE = Path(__file__).resolve().parent
SERVEUR = (RACINE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SERVEUR)


def _fonction(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(
        f"{nom} introuvable dans server.py — si le rattrapage du tagueur a "
        "bouge, ces tests doivent etre RELUS, pas contournes.")


class VerrouUneFois:
    """Une connexion qui refuse les N premiers `BEGIN IMMEDIATE`, puis cède.

    C'est exactement la forme du verrou réel : il finit toujours par tomber.
    Un faux qui refuserait pour toujours ne mesurerait pas la même chose."""

    def __init__(self, vraie, refus):
        self._vraie = vraie
        self.restants = refus
        self.begins = 0

    def execute(self, sql, *a, **kw):
        if sql.startswith("BEGIN"):
            self.begins += 1
            if self.restants > 0:
                self.restants -= 1
                raise sqlite3.OperationalError("database is locked")
        return self._vraie.execute(sql, *a, **kw)

    def __getattr__(self, nom):
        return getattr(self._vraie, nom)


def _magasin(dossier):
    return store_sqlite.SqliteStore(Path(dossier) / "t.db", "tags")


def _sans_pause(cas):
    """Neutralise les attentes : réelles en prod, elles ne prouvent rien ici et
    coûteraient six secondes par test.

    `hasattr` et non un accès direct — c'est le point de méthode : sur le code
    d'AVANT la constante n'existe pas, et un test qui rougit parce qu'un NOM
    manque ne dit rien du COMPORTEMENT. Il faut que l'ancien code s'exécute
    vraiment pour qu'on voie en quoi il était faux."""
    if hasattr(store_sqlite, 'VERROU_PAUSE_S'):
        ancien = store_sqlite.VERROU_PAUSE_S
        store_sqlite.VERROU_PAUSE_S = 0.0
        cas.addCleanup(setattr, store_sqlite, 'VERROU_PAUSE_S', ancien)


class TestLeVerrouSAttend(unittest.TestCase):
    """Faute n° 1 — un refus transitoire ne doit pas remonter."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.st = _magasin(self.tmp.name)
        self.addCleanup(self.st.cx.close)
        _sans_pause(self)

    def test_deux_refus_puis_la_ligne_est_ecrite(self):
        self.st.cx = VerrouUneFois(self.st.cx, refus=2)
        with redirect_stdout(io.StringIO()):
            self.st.set("photo.jpg", {"kw_fr": ["chat"]})
        self.assertEqual(self.st.cx.restants, 0, "les refus n'ont pas ete consommes")
        ligne = self.st.cx.execute(
            'SELECT v FROM "tags" WHERE k=?', ("photo.jpg",)).fetchone()
        self.assertIsNotNone(ligne, "la ligne n'a jamais atteint le disque")
        self.assertIn("chat", ligne[0])

    def test_un_verrou_qui_ne_cede_jamais_finit_par_se_dire(self):
        """L'obstination est BORNÉE : une base réellement bloquée doit se voir.
        Réessayer sans fin transformerait une panne en silence."""
        self.st.cx = VerrouUneFois(self.st.cx, refus=999)
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(sqlite3.OperationalError):
                self.st.set("photo.jpg", {"kw_fr": ["chat"]})
        self.assertEqual(self.st.cx.begins,
                         getattr(store_sqlite, 'VERROU_ESSAIS', 1))

    def test_une_vraie_erreur_ne_se_reessaie_pas(self):
        """Un « no such table » ne guérira pas : le réessayer cinq fois ne
        ferait que retarder le diagnostic."""
        class Casse(VerrouUneFois):
            def execute(self, sql, *a, **kw):
                if sql.startswith("BEGIN"):
                    self.begins += 1
                    raise sqlite3.OperationalError("no such table: tags")
                return self._vraie.execute(sql, *a, **kw)

        self.st.cx = Casse(self.st.cx, refus=0)
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(sqlite3.OperationalError):
                self.st.set("photo.jpg", {"kw_fr": ["chat"]})
        self.assertEqual(self.st.cx.begins, 1, "une erreur definitive a ete reessayee")


class TestLeSignalSurvitALEchec(unittest.TestCase):
    """Faute n° 1 bis — ce qui n'a pas pu s'écrire doit rester à écrire."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.st = _magasin(self.tmp.name)
        self.addCleanup(self.st.cx.close)
        _sans_pause(self)

    def test_apres_un_echec_la_cle_est_toujours_sale(self):
        self.st.cx = VerrouUneFois(self.st.cx, refus=999)
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(sqlite3.OperationalError):
                self.st.set("photo.jpg", {"kw_fr": ["chat"]})
        self.assertIn("photo.jpg", self.st._dirty,
                      "le signal d'ecriture a ete perdu avec l'echec : plus "
                      "rien ne dit qu'il reste quelque chose a ecrire")

    def test_et_la_prochaine_ecriture_la_rattrape(self):
        faux = VerrouUneFois(self.st.cx, refus=999)
        self.st.cx = faux
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(sqlite3.OperationalError):
                self.st.set("photo.jpg", {"kw_fr": ["chat"]})
        faux.restants = 0                      # le verrou tombe
        with redirect_stdout(io.StringIO()):
            self.st.set("autre.jpg", {"kw_fr": ["chien"]})
        vues = {k for (k,) in self.st.cx.execute('SELECT k FROM "tags"')}
        self.assertEqual(vues, {"photo.jpg", "autre.jpg"},
                         "la photo de l'ecriture ratee n'a pas ete rattrapee")


class TestLeRattrapageNeTuePlus(unittest.TestCase):
    """Faute n° 2 — la faute qui a réellement tué le fil."""

    def setUp(self):
        self.notes = []
        self.espace = {
            '__builtins__': __builtins__,
            'time': __import__('time'),
            'STORE': self,
            'print': self.notes.append,
        }
        mod = ast.Module(body=[_fonction('_marquer_echec')], type_ignores=[])
        ast.fix_missing_locations(mod)
        exec(compile(mod, 'server.py', 'exec'), self.espace)
        self.marquer = self.espace['_marquer_echec']
        self.ecrit = {}
        self.leve = None

    # — le faux index —
    def set(self, name, entry):
        if self.leve:
            raise self.leve
        self.ecrit[name] = entry

    def test_un_index_verrouille_ne_leve_pas(self):
        self.leve = sqlite3.OperationalError("database is locked")
        self.assertFalse(self.marquer("photo.jpg", "peu importe"),
                         "l'echec doit se DIRE non note, pas se taire")
        self.assertTrue(self.notes, "rien n'a ete dit sur la console")

    def test_quand_l_index_repond_la_note_est_ecrite(self):
        """Contrôle POSITIF : un rattrapage qui avale tout, y compris le
        succès, serait un instrument muet."""
        self.assertTrue(self.marquer("photo.jpg", ValueError("casse")))
        self.assertTrue(self.ecrit["photo.jpg"]["failed"])
        self.assertIn("casse", self.ecrit["photo.jpg"]["error"])


class TestAucunRattrapageNEcritEnDirect(unittest.TestCase):
    """Le garde-fou de source : la faute ne doit pas pouvoir revenir.

    Un test de comportement sur `_marquer_echec` ne protège que `_marquer_echec`.
    Ce qui a tué le fil, c'est un `STORE.set` NU dans un `except` — et rien
    n'empêche d'en réécrire un demain. On lit donc le tagueur lui-même."""

    def test_les_except_du_tagueur_passent_par_le_rattrapage(self):
        coupables = []
        for handler in ast.walk(_fonction('tagger_worker')):
            if not isinstance(handler, ast.ExceptHandler):
                continue
            for n in ast.walk(handler):
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == 'set'
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == 'STORE'):
                    coupables.append(n.lineno)
        self.assertEqual(coupables, [], (
            "STORE.set appele en direct dans un except de tagger_worker "
            f"(ligne(s) {coupables}) : c'est la forme exacte qui a tue le fil "
            "le 27/08 — passer par _marquer_echec."))


if __name__ == '__main__':
    unittest.main()
