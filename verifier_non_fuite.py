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
  8. /api/files/delete      -> B sur le PRIVE de A : 404, et A la voit encore ;
     (etape 5)                 B sur une photo PARTAGEE de A : 403, intacte ;
                               A sur la sienne, renommee a l'IDENTIQUE : permis
                               (le seul geste d'ecriture qui ne change rien —
                               c'est le temoin POSITIF : la garde ne refuse pas tout)
  9. /api/people/delete, /api/maint/census -> 403 pour B (admin seul) ;
     le nom vise n'existe pas et le recensement est en lecture seule : si la
     porte cedait, rien ne serait perdu.
Un « ne SAIT pas » (pas de nom sur la photo) est dit, pas rendu vert ; et si A
ne voit pas la cle (pas indexee, chemin faux), le banc S'ARRETE (code 2) : un
banc sans matiere ne rend ni vert ni rouge.
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
    ap.add_argument('--cle-partagee', default=None,
                    help='chemin d une photo PARTAGEE de A (hors PRIVE) ; sinon cherchee par les noms')
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

    # PRECONDITION : A doit VOIR la photo. Sinon le banc ne prouve rien — une
    # cle absente de l'index (pas encore scannee, faute de frappe) rendrait
    # « B ne voit rien » vert pour de mauvaises raisons. Ce n'est pas une
    # fuite, c'est un banc sans matiere : on le DIT, et on s'arrete.
    _, fa = A.json('/api/faits?key=' + urllib.parse.quote(cle))
    if cle not in (fa or {}).get('faits', {}):
        print('PRECONDITION NON TENUE : A (%s) ne voit pas cette cle.' % a.a)
        print('  Soit elle n est pas (encore) indexee (scan ~5 min, ligne « +1 » au journal),')
        print('  soit le chemin est faux. Le banc ne peut rien prouver : rien n est vert, rien n est rouge.')
        return 2
    ca, _, _ = A.req('/api/thumb?key=' + urllib.parse.quote(cle))
    if ca != 200:
        print('PRECONDITION NON TENUE : /api/thumb pour A -> %d (attendu 200). Le banc s arrete.' % ca)
        return 2
    notes.append('ok   A voit la photo (faits + vignette) : le banc a sa matiere')

    # 1. la vignette
    cb, _, _ = B.req('/api/thumb?key=' + urllib.parse.quote(cle))
    ok(cb == 404, '/api/thumb pour B -> %d (attendu 404, jamais 403)' % cb)

    # 2. les faits
    _, fb = B.json('/api/faits?key=' + urllib.parse.quote(cle))
    fait_a = (fa or {}).get('faits', {}).get(cle)
    ok(cle in ((fb or {}).get('inconnues') or []), '/api/faits : pour B, la cle est "inconnue"')
    noms = list((fait_a or {}).get('noms') or [])
    if not noms:
        print('  (la photo ne porte aucun nom : les controles 4-6 ne peuvent pas etre faits sur elle)')

    # 3. le fichier lui-meme : /media/<i>/<chemin relatif a la racine>. La
    # racine est le prefixe du chemin jusqu'a `Photos` ; l'index i se cherche
    # (A doit obtenir 200 pour l'un d'eux), puis B doit avoir 404 sur le MEME.
    url = None
    kp = cle.replace('\\', '/')
    if '/Photos/' in kp:
        rel = urllib.parse.quote(kp.split('/Photos/', 1)[1])
        for i in range(6):
            cand = '/media/%d/%s' % (i, rel)
            ca, _, _ = A.req(cand)
            if ca == 200:
                url = cand; break
    if url:
        cb, _, _ = B.req(url)
        notes.append('ok   %s pour A -> 200' % asc(url))
        ok(cb == 404, '%s pour B -> %d (attendu 404)' % (asc(url), cb))
    else:
        print('  (aucune URL /media/<i>/... ne rend 200 pour A : controle 3 non fait)')

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

    # 8. l'ecriture (etape 5) : B ne touche pas aux photos de A
    _, moi_b = B.json('/api/moi')
    if (moi_b or {}).get('admin'):
        print('  (B est ADMIN : les controles 8-9 ne prouveraient rien — choisir un B sans droits)')
    else:
        cb, db = B.json('/api/files/delete', {'key': cle})
        ok(cb == 404, '/api/files/delete du PRIVE de A par B -> %d (attendu 404, jamais 403)' % cb)
        ca, _, _ = A.req('/api/thumb?key=' + urllib.parse.quote(cle))
        ok(ca == 200, 'apres la tentative de B, A voit toujours sa photo (%d)' % ca)
        # une photo PARTAGEE de A : donnee, ou cherchee dans ce que B voit de A
        partagee = deb64(a.cle_partagee) if a.cle_partagee else None
        if not partagee and noms:
            for n in noms:
                _, pb = B.json('/api/people/photos?name=' + urllib.parse.quote(n) + '&limit=50000&light=1')
                for ph in (pb or {}).get('photos', []):
                    k = str(ph.get('key') or '')
                    if ('Photos ' + a.a) in k and 'PRIVE' not in k.upper():
                        partagee = k; break
                if partagee:
                    break
        if partagee:
            cb, db = B.json('/api/files/delete', {'key': partagee})
            ok(cb == 403, '/api/files/delete d une photo PARTAGEE de A par B -> %d (attendu 403)' % cb)
            cb2, _, _ = B.req('/api/thumb?key=' + urllib.parse.quote(partagee))
            ok(cb2 == 200, 'la photo partagee est intacte et toujours visible de B (%d)' % cb2)
        else:
            print('  (aucune photo PARTAGEE de A trouvee : passer --cle-partagee ; controle 403 non fait)')
        # temoin positif : A garde la main chez lui. Renommer a l'identique
        # passe la garde puis rend `changed: false` SANS toucher au disque.
        tgt = None
        kp = cle.replace('\\', '/')
        if '/Photos/' in kp:
            for i in range(6):
                ca, da = A.json('/api/files/rename',
                                {'idx': i, 'rel': kp.split('/Photos/', 1)[1], 'name': kp.rsplit('/', 1)[1]})
                if ca == 200 and da and da.get('ok'):
                    tgt = (i, da); break
                if ca == 403:
                    tgt = (i, da); break
        if tgt and tgt[1].get('ok'):
            ok(tgt[1].get('changed') is False, 'A renomme sa photo a l identique : permis, rien ne change (changed=%s)' % tgt[1].get('changed'))
        elif tgt:
            ok(False, 'A est REFUSE chez lui : %s' % asc(tgt[1]))
        else:
            print('  (temoin positif non fait : aucune racine /media ne porte la cle)')
        # 9. fiche entiere et maintenance : admin seul
        cb, _ = B.json('/api/people/delete', {'name': '__banc_non_fuite_inexistant__'})
        ok(cb == 403, '/api/people/delete par B -> %d (attendu 403 : admin seul)' % cb)
        cb, _ = B.json('/api/maint/census', {})
        ok(cb == 403, '/api/maint/census par B -> %d (attendu 403 : admin seul)' % cb)

    for l in notes:
        print('  ' + asc(l))
    for l in griefs:
        print('  ' + asc(l))
    print('=' * 60)
    print('%d controle(s) verts, %d FUITE(S)' % (len(notes), len(griefs)))
    return 1 if griefs else 0


if __name__ == '__main__':
    sys.exit(main())
