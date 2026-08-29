#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le banc de NON-FUITE du chantier 17 : B ne voit RIEN du PRIVE de A.

Sur le VRAI serveur, avec deux comptes. LECTURE SEULE (ne cree rien, n'ecrit
rien). Sortie ASCII (console cp1252).

    verifier_non_fuite.py --a Mike --mdp-a b64:... --b Flo --mdp-b b64:... --cle b64:<chemin PRIVE de A>
    verifier_non_fuite.py ... --url http://127.0.0.1:8080

Ce qu'il prouve, route par route, pour la cle donnee (une photo du PRIVE
de A, deja indexee) : A la voit ; B ne la voit pas, et RIEN ne la trahit :
  1. /api/thumb?key=        -> 200 pour A, 404 pour B (jamais 403)
  2. /api/faits?key=        -> un fait pour A ; pour B : `inconnues` la cite
  3. /media/<url de A>      -> 200 pour A, 404 pour B
  4. /api/people/list       -> pour chaque nom porte par la photo, le compteur
                               de B = celui de A moins 1 (17b : le compteur)
  5. /api/people/photos     -> la cle absente chez B pour ces noms
  6. /api/search?q=<nom>    -> la cle absente chez B (si un nom est porte)
  7. sans cookie            -> 401 sur l'API, 302 sur une page (la porte)
Un « ne SAIT pas » (pas de nom sur la photo) est dit, pas rendu vert.
"""
import argparse
import base64
import http.cookiejar
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def deb64(v):
    return base64.b64decode(v[4:]).decode('utf-8') if v.startswith('b64:') else v


class Client:
    def __init__(self, url):
        self.url = url.rstrip('/')
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.op.addheaders = []

    def req(self, path, data=None, suivre=True):
        """(code, corps_bytes, content-type). Les 3xx/4xx sont RENDUS, pas leves."""
        body = json.dumps(data).encode() if data is not None else None
        r = urllib.request.Request(self.url + path, data=body,
                                   headers={'Content-Type': 'application/json'} if body else {})
        if not suivre:
            class NoRedir(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            op = urllib.request.build_opener(NoRedir, urllib.request.HTTPCookieProcessor(self.cj))
        else:
            op = self.op
        try:
            with op.open(r, timeout=60) as resp:
                return resp.status, resp.read(), resp.headers.get('Content-Type', '')
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get('Content-Type', '')

    def json(self, path, data=None):
        code, corps, _ = self.req(path, data)
        try:
            return code, json.loads(corps or b'null')
        except ValueError:
            return code, None

    def connexion(self, nom, mdp):
        code, d = self.json('/api/connexion', {'nom': nom, 'mdp': mdp})
        return bool(d and d.get('ok'))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default='http://127.0.0.1:8080')
    ap.add_argument('--a', required=True, help='le proprietaire du PRIVE')
    ap.add_argument('--mdp-a', required=True)
    ap.add_argument('--b', required=True, help="l'autre")
    ap.add_argument('--mdp-b', required=True)
    ap.add_argument('--cle', required=True, help='chemin (cle d index) d une photo du PRIVE de A')
    a = ap.parse_args(argv)
    cle = deb64(a.cle)
    A, B, anon = Client(a.url), Client(a.url), Client(a.url)
    griefs, notes = [], []

    def ok(cond, quoi):
        (notes if cond else griefs).append(('ok  ' if cond else 'FUITE ') + quoi)

    # 0. la porte
    code, _, _ = anon.req('/api/people/list')
    ok(code == 401, 'sans cookie, /api/people/list -> %d (attendu 401)' % code)
    code, _, _ = anon.req('/people', suivre=False)
    ok(code == 302, 'sans cookie, /people -> %d (attendu 302 vers /connexion)' % code)

    if not A.connexion(a.a, deb64(a.mdp_a)):
        print('connexion de A (%s) refusee : le banc ne peut rien prouver' % a.a); return 2
    if not B.connexion(a.b, deb64(a.mdp_b)):
        print('connexion de B (%s) refusee : le banc ne peut rien prouver' % a.b); return 2
    print('A = %s, B = %s, cle = %s' % (a.a, a.b, asc(cle)))

    # 1. la vignette
    ca, _, _ = A.req('/api/thumb?key=' + urllib.parse.quote(cle))
    cb, _, _ = B.req('/api/thumb?key=' + urllib.parse.quote(cle))
    ok(ca == 200, '/api/thumb pour A -> %d' % ca)
    ok(cb == 404, '/api/thumb pour B -> %d (attendu 404, jamais 403)' % cb)

    # 2. les faits
    _, fa = A.json('/api/faits?key=' + urllib.parse.quote(cle))
    _, fb = B.json('/api/faits?key=' + urllib.parse.quote(cle))
    fait_a = (fa or {}).get('faits', {}).get(cle)
    ok(cle in (fa or {}).get('faits', {}), '/api/faits : A connait la photo')
    ok(cle in ((fb or {}).get('inconnues') or []), '/api/faits : pour B, la cle est « inconnue »')
    noms = list((fait_a or {}).get('noms') or [])
    if not noms:
        print('  (la photo ne porte aucun nom : les controles 4-6 ne peuvent pas etre faits sur elle)')

    # 3. le fichier lui-meme (l'URL /media/ vient de la reponse de A)
    _, pa = A.json('/api/people/photos?name=' + urllib.parse.quote(noms[0]) + '&limit=50000&light=1') if noms else (0, None)
    url = None
    for ph in ((pa or {}).get('photos') or []):
        if ph.get('key') == cle:
            url = ph.get('url'); break
    if url:
        ca, _, _ = A.req(url)
        cb, _, _ = B.req(url)
        ok(ca == 200, '%s pour A -> %d' % (asc(url), ca))
        ok(cb == 404, '%s pour B -> %d (attendu 404)' % (asc(url), cb))
    else:
        print('  (pas d URL /media pour cette cle dans la fiche de A : controle 3 non fait)')

    # 4-5. les compteurs et les fiches
    if noms:
        _, la = A.json('/api/people/list'); _, lb = B.json('/api/people/list')
        ca_ = {p['name']: p['photos'] for p in (la or {}).get('people', [])}
        cb_ = {p['name']: p['photos'] for p in (lb or {}).get('people', [])}
        for n in noms:
            ok(ca_.get(n, 0) - cb_.get(n, 0) == 1,
               'compteur de %s : A=%s, B=%s (attendu A-1)' % (asc(n), ca_.get(n), cb_.get(n)))
            _, pb = B.json('/api/people/photos?name=' + urllib.parse.quote(n) + '&limit=50000&light=1')
            cles_b = {ph.get('key') for ph in (pb or {}).get('photos', [])}
            ok(cle not in cles_b, 'fiche %s pour B : la cle est absente' % asc(n))
            # 6. la recherche
            _, sb = B.json('/api/search?q=' + urllib.parse.quote('personne:' + n) + '&limit=50000')
            txt = json.dumps(sb or {}, ensure_ascii=False)
            ok(cle.replace('\\', '\\\\') not in txt and cle not in txt,
               'recherche personne:%s pour B : la cle est absente' % asc(n))

    for l in notes:
        print('  ' + asc(l))
    for l in griefs:
        print('  ' + asc(l))
    print('=' * 60)
    print('%d controle(s) verts, %d FUITE(S)' % (len(notes), len(griefs)))
    return 1 if griefs else 0


if __name__ == '__main__':
    sys.exit(main())
