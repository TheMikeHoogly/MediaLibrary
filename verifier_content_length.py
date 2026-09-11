#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avant HTTP/1.1 : est-ce que CHAQUE réponse dit sa longueur ?

En HTTP/1.0 la connexion se ferme après chaque réponse : le client sait que le
corps est fini parce que la socket se ferme, et une réponse sans
`Content-Length` marche quand même. En **HTTP/1.1** la connexion RESTE
OUVERTE : une réponse sans longueur (ni découpage en morceaux) désynchronise
le dialogue — le navigateur attend des octets qui ne viendront pas, et **la
page reste suspendue**. C'est une panne bien pire que la lenteur qu'on corrige
en activant le keep-alive.

Ce banc lit `server.py` par l'ARBRE SYNTAXIQUE et suit chaque `end_headers()`
jusqu'à son `send_response()` dans la même fonction :

  - un `Content-Length` posé entre les deux → conforme ;
  - un `Transfer-Encoding: chunked` → conforme ;
  - un code **204**, **304** ou **1xx** → conforme sans corps (RFC 9110) ;
  - sinon : **SIGNALÉ**, avec la ligne et le code concerné.

Et il imprime son ÉTENDUE (règle 8 du projet) : combien de fonctions
parcourues, combien de réponses vues, combien jugées, combien écartées et
pourquoi. Un instrument qui rend « 0 problème » sans dire ce qu'il a regardé
ne prouve rien.

  python verifier_content_length.py
  python verifier_content_length.py --fichier server.py
"""

import argparse
import ast
import sys
from pathlib import Path

SANS_CORPS = {204, 304}


def _codes(noeud):
    """Les codes possibles du `send_response` : un littéral, ou les deux
    branches d'un `A if c else B` (`206 if partial else 200`)."""
    if not noeud.args:
        return []
    a = noeud.args[0]
    if isinstance(a, ast.Constant) and isinstance(a.value, int):
        return [a.value]
    if isinstance(a, ast.IfExp):
        return [x.value for x in (a.body, a.orelse)
                if isinstance(x, ast.Constant) and isinstance(x.value, int)]
    return []


def _appels(corps, nom):
    """Les appels `self.<nom>(…)` dans un morceau d'arbre, avec leur ligne."""
    out = []
    for n in ast.walk(corps):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == nom
                and isinstance(n.func.value, ast.Name) and n.func.value.id == 'self'):
            out.append(n)
    return out


def _entete_pose(appel):
    """(nom, valeur littérale ou None) d'un `send_header`."""
    if not appel.args:
        return None, None
    a = appel.args[0]
    nom = a.value if isinstance(a, ast.Constant) else None
    val = None
    if len(appel.args) > 1 and isinstance(appel.args[1], ast.Constant):
        val = appel.args[1].value
    return (nom.lower() if isinstance(nom, str) else None), val


def _innermost(arbre):
    """clé (id) d'un appel -> la fonction la PLUS PROCHE qui le contient.

    Sans ça, une fonction imbriquée (`_fallback` dans `_serve_thumb`) est
    comptée deux fois : un grief en double fait croire à deux défauts là où il
    y en a un, et un instrument qui compte double ne compte plus."""
    proprio = {}
    for f in ast.walk(arbre):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(f):
            if isinstance(n, ast.Call):
                avant = proprio.get(id(n))
                if avant is None or f.lineno > avant.lineno:
                    proprio[id(n)] = f
    return proprio


def examiner(source):
    arbre = ast.parse(source)
    fonctions = [n for n in ast.walk(arbre)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    proprio = _innermost(arbre)
    vues = jugees = conformes = 0
    griefs = []
    ecartees = []
    for f in fonctions:
        fins = [x for x in _appels(f, 'end_headers') if proprio.get(id(x)) is f]
        if not fins:
            continue
        reponses = _appels(f, 'send_response')
        entetes = _appels(f, 'send_header')
        for fin in fins:
            vues += 1
            # Le `send_response` qui la précède dans le TEXTE de la fonction.
            avant = [r for r in reponses if r.lineno <= fin.lineno]
            if not avant:
                ecartees.append((f.name, fin.lineno, 'aucun send_response avant'))
                continue
            rep = max(avant, key=lambda r: r.lineno)
            codes = _codes(rep)
            jugees += 1
            if codes and all(c in SANS_CORPS or c < 200 for c in codes):
                conformes += 1
                continue
            longueur = False
            for e in entetes:
                if not (rep.lineno <= e.lineno <= fin.lineno):
                    continue
                nom, val = _entete_pose(e)
                if nom == 'content-length':
                    longueur = True
                if nom == 'transfer-encoding' and isinstance(val, str) \
                        and 'chunked' in val.lower():
                    longueur = True
            if longueur:
                conformes += 1
            else:
                griefs.append((f.name, fin.lineno, codes or ['?'],
                               rep.lineno))
    return {'fonctions': len(fonctions), 'vues': vues, 'jugees': jugees,
            'conformes': conformes, 'griefs': griefs, 'ecartees': ecartees}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--fichier', default='server.py')
    a = ap.parse_args(argv)
    src = Path(a.fichier).read_text(encoding='utf-8')
    r = examiner(src)
    print(f'{a.fichier} : {r["fonctions"]} fonctions parcourues, '
          f'{r["vues"]} reponses ecrites a la main, {r["jugees"]} jugees, '
          f'{r["conformes"]} conformes.')
    for nom, ligne, motif in r['ecartees']:
        print(f'  ECARTEE  {nom} l.{ligne} : {motif}')
    if not r['griefs']:
        print('Aucune reponse sans longueur : HTTP/1.1 ne peut pas suspendre une page ici.')
        return 0
    print()
    print('REPONSES SANS LONGUEUR — en HTTP/1.1 elles suspendent le client :')
    for nom, ligne, codes, ligne_rep in r['griefs']:
        print(f'  {nom} : end_headers l.{ligne}, send_response l.{ligne_rep} '
              f'code {"/".join(str(c) for c in codes)}')
    print()
    print('Correctif : `Content-Length: 0` pour une reponse sans corps '
          '(302, 416...), la vraie longueur sinon.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
