#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Un echec garde en base doit nommer sa propre CAUSE.

Pourquoi ce fichier existe (13/09)
----------------------------------
La campagne de retag a laisse UN abandon sur 40 525 photos. Tout ce qu'il en
restait dans l'index etait la chaine « another row available » — un message de
SQLite (`sqlite3_errstr(SQLITE_ROW)`), donc ni le modele ni la photo. Mais
impossible de dire d'ou il venait : ni le TYPE de l'exception, ni la ligne.
Une heure de lecture de code n'a pas suffi a le reproduire.

`_motif_lisible` fait que la PROCHAINE occurrence se diagnostiquera toute
seule. Ce banc tient les quatre choses qui comptent :

1. le TYPE de l'exception est la (c'est lui qui dit « SQLite », pas « Ollama ») ;
2. l'ENDROIT est la, et c'est la DERNIERE frame — celle qui leve, pas celle
   qui attrape ;
3. une chaine ecrite a la main passe TELLE QUELLE (« timeout Ollama x3 » est
   deja une cause, pas un symptome) ;
4. la borne de 200 caracteres tient, parce que ce texte part dans l'index.

Le banc lit `server.py` par l'arbre syntaxique et ne l'importe PAS : le
serveur tire torch et insightface.
"""
import ast
import io
import os
import sqlite3
import unittest

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server.py')

with io.open(SERVER, encoding='utf-8') as _f:
    SOURCE = _f.read()
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return n
    raise AssertionError(nom + ' introuvable dans server.py')


def _charge(nom):
    espace = {}
    exec(compile(ast.Module(body=[_noeud(nom)], type_ignores=[]),
                 SERVER, 'exec'), espace)
    return espace[nom]


MOTIF = _charge('_motif_lisible')


def _leve_dedans():
    """Une pile a DEUX etages : la frame qui leve n'est pas la premiere."""
    def au_fond():
        raise sqlite3.OperationalError('another row available')
    au_fond()


class LeTypeEtLEndroitSontLa(unittest.TestCase):

    def _capture(self, f):
        try:
            f()
        except BaseException as e:          # noqa: BLE001
            return e
        raise AssertionError('rien leve')

    def test_le_TYPE_est_nomme(self):
        """C'est lui qui dit « SQLite » la ou le message seul ne disait rien."""
        m = MOTIF(self._capture(_leve_dedans))
        self.assertIn('sqlite3.OperationalError', m)
        self.assertIn('another row available', m)

    def test_l_ENDROIT_est_la_DERNIERE_frame(self):
        """Celle qui LEVE, pas celle qui attrape. Une pile a deux etages le
        prouve : la premiere frame est `_leve_dedans`, la derniere `au_fond`."""
        e = self._capture(_leve_dedans)
        m = MOTIF(e)
        self.assertIn('@ ' + os.path.basename(__file__), m)
        # La ligne citee est celle du `raise`, pas celle de l'appel.
        tb = e.__traceback__
        dernier = tb
        while dernier.tb_next is not None:
            dernier = dernier.tb_next
        self.assertIn(':%d' % dernier.tb_lineno, m)
        self.assertNotIn(':%d' % tb.tb_lineno, m.split('@')[-1])

    def test_un_builtin_ne_porte_pas_son_module(self):
        """`builtins.ValueError` serait du bruit ; `ValueError` suffit."""
        m = MOTIF(self._capture(lambda: 1 / 0))
        self.assertTrue(m.startswith('ZeroDivisionError:'), m)

    def test_une_exception_SANS_traceback_ne_casse_pas(self):
        """Une exception fabriquee et jamais levee n'a pas de pile."""
        m = MOTIF(sqlite3.OperationalError('jamais levee'))
        self.assertIn('sqlite3.OperationalError', m)
        self.assertNotIn('@', m)


class UneChaineEcriteAlaMainPasseTelleQuelle(unittest.TestCase):
    """« timeout Ollama x3 » est deja une cause. L'habiller la deguiserait."""

    def test_la_chaine_est_intacte(self):
        self.assertEqual(MOTIF('timeout Ollama x3'), 'timeout Ollama x3')

    def test_un_objet_quelconque_se_lit_quand_meme(self):
        self.assertEqual(MOTIF(42), '42')


class LaBorneTient(unittest.TestCase):
    """Ce texte part dans l'index, une entree par photo : il ne doit pas
    grossir sans limite."""

    def test_une_chaine_trop_longue_est_coupee(self):
        self.assertEqual(len(MOTIF('x' * 5000)), 200)

    def test_une_exception_trop_bavarde_est_coupee_aussi(self):
        try:
            raise ValueError('y' * 5000)
        except ValueError as e:
            self.assertEqual(len(MOTIF(e)), 200)

    def test_la_borne_se_regle(self):
        self.assertEqual(len(MOTIF('x' * 5000, limite=40)), 40)


class LesDEUXPortesLUtilisent(unittest.TestCase):
    """`_marquer_echec` et `_echec_retag` ecrivent toutes deux un motif dans
    l'index. Si une seule passait par la regle, l'autre garderait des echecs
    muets — et on ne le verrait qu'a la prochaine campagne."""

    def _appels(self, nom):
        corps = _noeud(nom).body
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)):
            corps = corps[1:]
        return {ast.unparse(c.func) for n in corps for c in ast.walk(n)
                if isinstance(c, ast.Call)}

    def test_marquer_echec_passe_par_la_regle(self):
        self.assertIn('_motif_lisible', self._appels('_marquer_echec'))

    def test_echec_retag_passe_par_la_regle(self):
        self.assertIn('_motif_lisible', self._appels('_echec_retag'))

    def test_plus_personne_ne_tronque_a_la_main_dans_ces_deux_la(self):
        """`str(raison)[:200]` etait l'ecriture d'avant : la laisser quelque
        part, c'est rouvrir le trou sans que rien ne le dise."""
        for nom in ('_marquer_echec', '_echec_retag'):
            src = ast.unparse(_noeud(nom))
            corps = src.split('"""')[-1] if '"""' in src else src
            self.assertNotIn('str(raison)[:200]', corps, nom)


if __name__ == '__main__':
    unittest.main(verbosity=2)
