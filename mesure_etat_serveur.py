#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ce que le PROCESSUS du serveur dit de lui-même, lu depuis la machine de Mike.

POURQUOI CE FICHIER EXISTE

Le protocole du projet dit : « AVANT de redémarrer, lire `uptime_s` ; APRÈS,
VÉRIFIER que `demarre_a` a bougé et que `code_a_jour` est vrai ». Jusqu'au
18/09 cette lecture n'avait qu'UN chemin : Chrome. La VM n'atteint pas le LAN,
et le soir où l'extension Chrome n'a pas répondu, il ne restait aucune façon
de savoir si le serveur exécutait le code du disque — donc aucune façon
honnête de conclure quoi que ce soit d'une mesure.

`/api/serveur` est l'une des quatre routes OUVERTES (`comptes.OUVERTS`) : elle
répond sans session, ce qui est exactement ce qu'un agent local peut lire. Ce
banc ne fait que la lire et l'imprimer. Il ne JUGE pas (règle n° 6) : il
n'écrit rien, ne redémarre rien, et son verdict tient en trois faits datés.

    python mesure_etat_serveur.py
    python mesure_etat_serveur.py --hote 192.168.0.13 --port 8080 --json
    python mesure_etat_serveur.py --sert /ui/global.js --motif mdp-0

CE QUE LE SERVEUR SERT, PAS CE QUE LE DISQUE PORTE

`--sert` lit un chemin OUVERT (les `/ui/` en sont) et dit si des motifs y
figurent. C'est l'autre moitié de la preuve : `code_a_jour` parle du
`server.py` chargé, pas des assets mis en cache mémoire au démarrage. Un
`ui/global.js` corrigé sur le disque et servi dans sa version d'avant est
exactement le genre d'écart qui fait conclure à tort.

Ce qu'il ne peut PAS lire : tout ce qui est derrière la porte
(`/api/maint/status` et son `maint.lourde`, `/api/moi`) exige un cookie de
session. Il le DIT au lieu de rendre un champ vide — un « ? » qu'on prend pour
un « non » est pire qu'une absence nommée.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def lire(url, delai=6.0):
    """(objet, None) ou (None, cause lisible). Jamais d'exception au visage."""
    try:
        with urllib.request.urlopen(url, timeout=delai) as r:
            return json.loads(r.read().decode('utf-8', 'replace')), None
    except urllib.error.HTTPError as e:
        return None, f'HTTP {e.code}' + (' (derrière la porte : session requise)'
                                         if e.code in (401, 403) else '')
    except (urllib.error.URLError, OSError) as e:
        return None, f'injoignable ({e})'
    except ValueError as e:
        return None, f'réponse illisible ({e})'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--hote', default='192.168.0.13')
    ap.add_argument('--port', type=int, default=8080)
    ap.add_argument('--json', action='store_true', help='la réponse brute, sans prose')
    ap.add_argument('--sert', default=None,
                    help='un chemin OUVERT à lire tel que le serveur le sert')
    ap.add_argument('--motif', action='append', default=[],
                    help='un littéral à chercher dans ce que --sert a rendu')
    a = ap.parse_args(argv)
    base = f'http://{a.hote}:{a.port}'

    if a.sert:
        try:
            with urllib.request.urlopen(base + a.sert, timeout=8.0) as r:
                texte = r.read().decode('utf-8', 'replace')
            print(f'{a.sert} : HTTP 200, {len(texte)} caractères')
            for m in a.motif:
                print(f'  {m!r} : ' + ('PRESENT' if m in texte else 'ABSENT'))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            print(f'{a.sert} : {e}')
            return 2
        if not a.motif:
            return 0

    d, cause = lire(base + '/api/serveur')
    if d is None:
        print(f'/api/serveur : {cause}')
        print('Rien ne peut être conclu : le serveur ne se décrit pas.')
        return 2
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0

    up = d.get('uptime_s')
    print(f"pid {d.get('pid')}  —  démarré il y a {up} s")
    print(f"demarre_a       : {d.get('demarre_a')} "
          f"({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(d.get('demarre_a') or 0))})")
    print(f"code_a_jour     : {d.get('code_a_jour')}")
    print(f"  chargé        : {d.get('server_py_mtime_charge')}")
    print(f"  sur le disque : {d.get('server_py_mtime_disque')}")
    print(f"commande en cours dans le canal : {d.get('commande')!r}")
    v = d.get('vignettes') or {}
    if v:
        print('vignettes (fil de fond) : ' + json.dumps(v, ensure_ascii=False))
    # Les deux faits qui gouvernent le geste, dits en clair.
    if isinstance(up, (int, float)) and up < 60:
        print('ATTENTION : moins de 60 s d\'uptime — quelqu\'un vient de redémarrer.')
    if d.get('code_a_jour') is False:
        print('ATTENTION : le processus n\'exécute PAS le server.py du disque.')
    d2, cause2 = lire(base + '/api/maint/status')
    print('/api/maint/status : ' + ('lu' if d2 else cause2))
    if d2:
        print('  maint.lourde = ' + json.dumps((d2.get('maint') or {}).get('lourde'),
                                               ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
