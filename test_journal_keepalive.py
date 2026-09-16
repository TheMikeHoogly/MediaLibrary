#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La fin d'un keep-alive n'est pas une panne (16/09).

`handle_one_request` annonce « Request timed out » quand une connexion gardee
ouverte reste muette `timeout` secondes. Le journal le criait ; Mike l'a pris
pour une requete perdue. Les deux methodes sont extraites de `server.py` par
l'arbre et posees sur un vrai `BaseHTTPRequestHandler`, qui les appelle comme
en production -- un faux appel prouverait seulement que le banc sait appeler.
"""
import ast
import contextlib
import io
import socket
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path

SOURCE = (Path(__file__).resolve().parent / 'server.py').read_text(encoding='utf-8')
ARBRE = ast.parse(SOURCE)
LIGNES = SOURCE.splitlines()


def _classe():
    for n in ast.walk(ARBRE):
        if isinstance(n, ast.ClassDef) and any(
                isinstance(b, ast.FunctionDef) and b.name == 'log_error' for b in n.body):
            return n
    raise AssertionError('aucune classe ne definit log_error')


def _handler():
    n = _classe()
    ns = {}
    corps = []
    for b in n.body:
        if (isinstance(b, ast.FunctionDef) and b.name in ('log_message', 'log_error')) or (
                isinstance(b, ast.Assign) and any(
                    getattr(t, 'id', '') == 'KEEPALIVE_FERMES' for t in b.targets)):
            corps.append('\n'.join(LIGNES[b.lineno - 1:b.end_lineno]))
    src = 'class H(BaseHTTPRequestHandler):\n' + '\n'.join(corps)
    exec(src, {'BaseHTTPRequestHandler': BaseHTTPRequestHandler}, ns)   # noqa: S102
    return ns['H']


class Lecteur(io.BytesIO):
    def readline(self, *a):
        raise socket.timeout('timed out')


class LaFinDuKeepAlive(unittest.TestCase):

    def _un(self, H):
        h = H.__new__(H)
        h.client_address = ('192.168.0.13', 1)
        h.rfile = Lecteur()
        h.close_connection = False
        return h

    def test_se_compte_et_se_tait(self):
        H = _handler()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self._un(H).handle_one_request()
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(H.KEEPALIVE_FERMES, 1)

    def test_une_autre_erreur_reste_ecrite(self):
        H = _handler()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self._un(H).log_error('code %d, message %s', 400, 'Bad request')
        self.assertIn('code 400, message Bad request', out.getvalue())
        self.assertEqual(H.KEEPALIVE_FERMES, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
