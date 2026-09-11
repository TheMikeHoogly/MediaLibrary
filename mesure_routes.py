#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ce que le serveur passe son temps a servir — le classement, avant d'optimiser.

Trois optimisations ont deja ete faites sur ce serveur : les vignettes (O1), la
compression HTTP (O11), la reconciliation du magasin (O14). Toutes justes, et
toutes CHOISIES A L'OEIL. Ce banc existe pour que la suivante soit choisie sur
un chiffre.

Il lit `_perf_routes.json`, que le serveur depose a chaque cycle de maintenance
(l'horloge vit dans `do_GET`/`do_POST`, cf. `_perf_note`), et il classe par
**TEMPS TOTAL** — pas par maximum. *Une route lente appelee trois fois coute
moins qu'une route tiede appelee mille fois ; c'est le total qui dit ou une
optimisation se paie.*

Il donne aussi la lecture du RESSENTI, qui n'est pas la meme chose : combien de
requetes ont depasse 300 ms et 1 s. Une route peut peser lourd au total sans
qu'aucune requete ne soit penible, et l'inverse.

**A LIRE AVEC SA DATE.** Un releve pris pendant la campagne de retag est une
BORNE HAUTE : le tagueur tient le NAS et le GPU, tout ce qui lit le disque en
souffre. Le meme instrument relu apres la campagne donne la ligne de base
propre — et l'ecart entre les deux est lui-meme une mesure.

  python mesure_routes.py
  python mesure_routes.py --n 25
"""

import argparse
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
FICHIER = RACINE / '_perf_routes.json'


def _duree(s):
    if s < 90:
        return '%.0f s' % s
    if s < 5400:
        return '%.0f min' % (s / 60)
    return '%.1f h' % (s / 3600)


def _phases(t):
    """OU part le temps d'une route instrumentee (horloge de phases, 11/09).

    Deux vues, et c'est la seconde qui decide : l'AGREGAT melange ouvertures
    froides et chaudes ; le DETAIL des dernieres executions montre une
    ouverture froide telle qu'elle a ete vecue. Une sous-phase (nom a point)
    est une part de sa parente : elle n'entre pas dans la colonne « part »."""
    phases = t.get('phases') or {}
    derniers = t.get('derniers') or []
    if not phases:
        return
    for route, d in sorted(phases.items()):
        tot = d.get('(total)') or {}
        n = max(tot.get('n', 0), 1)
        print('-' * 78)
        print('  OU PART LE TEMPS : %s  (%d execution(s), %.0f ms en moyenne)'
              % (route, tot.get('n', 0), tot.get('ms', 0) / n))
        print('  %-26s %10s %10s %8s' % ('phase', 'moyenne', 'pire', 'part'))
        premier = sorted(((k, v) for k, v in d.items()
                          if k != '(total)' and '.' not in k),
                         key=lambda kv: -kv[1]['ms'])
        for k, v in premier:
            print('  %-26s %8.0fms %8.0fms %6.1f %%'
                  % (k, v['ms'] / n, v['max'],
                     100.0 * v['ms'] / max(tot.get('ms', 0), 1e-9)))
            for k2, v2 in sorted(((a, b) for a, b in d.items()
                                  if a.startswith(k + '.')),
                                 key=lambda kv: -kv[1]['ms']):
                print('    %-24s %8.0fms %8.0fms'
                      % (k2[len(k):], v2['ms'] / n, v2['max']))
    if derniers:
        print('-' * 78)
        print('  LES DERNIERES EXECUTIONS (la plus recente en bas)')
        for x in derniers[-10:]:
            info = x.get('info') or {}
            ph = sorted(((k, v) for k, v in (x.get('phases') or {}).items()
                         if '.' not in k), key=lambda kv: -kv[1])[:4]
            print('  %s  %8.0fms  %-9s %5s fich. %4s stat  | %s'
                  % (time.strftime('%H:%M:%S', time.localtime(x.get('t', 0))),
                     x.get('total_ms', 0), info.get('mode', '?'),
                     info.get('fichiers', '?'), info.get('stats_nas', '?'),
                     '  '.join('%s %.0f' % kv for kv in ph)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--n', type=int, default=20, help='lignes a montrer')
    a = ap.parse_args(argv)

    if not FICHIER.is_file():
        print('  %s absent.' % FICHIER.name)
        print('  Le serveur le depose a chaque cycle de maintenance (~5 min).')
        print("  S'il manque encore, c'est qu'aucune requete n'a ete servie")
        print('  depuis le dernier demarrage.')
        return 2
    t = json.loads(FICHIER.read_text(encoding='utf-8'))
    routes = t.get('routes') or []
    seuils = t.get('seuils_ms') or [30, 100, 300, 1000, 3000]
    total_ms = sum(r['ms'] for r in routes)
    total_n = sum(r['n'] for r in routes)
    age = time.time() - Path(FICHIER).stat().st_mtime

    print('=' * 78)
    print('  CE QUE LE SERVEUR PASSE SON TEMPS A SERVIR')
    print('=' * 78)
    print('  fenetre de mesure : %s depuis le dernier demarrage'
          % _duree(t.get('duree_s', 0)))
    print('  releve ecrit il y a %s' % _duree(age))
    print('  %d requete(s), %.1f s de fil serveur au total'
          % (total_n, total_ms / 1000))
    print('-' * 78)
    print('  %-34s %7s %9s %8s %8s' % ('route', 'appels', 'total', 'moyenne',
                                       'part'))
    print('-' * 78)
    for r in routes[:a.n]:
        print('  %-34s %7d %8.1fs %7.0fms %6.1f %%'
              % (r['cle'][:34], r['n'], r['ms'] / 1000,
                 r['ms'] / max(r['n'], 1),
                 100.0 * r['ms'] / max(total_ms, 1e-9)))
    if len(routes) > a.n:
        reste = sum(r['ms'] for r in routes[a.n:])
        print('  %-34s %7d %8.1fs %7s %6.1f %%'
              % ('... et %d autre(s)' % (len(routes) - a.n),
                 sum(r['n'] for r in routes[a.n:]), reste / 1000, '',
                 100.0 * reste / max(total_ms, 1e-9)))
    print('-' * 78)
    print('  LE RESSENTI — ce n est PAS le meme classement')
    print('  %-34s %9s %9s %9s' % ('route', '>%dms' % seuils[2],
                                   '>%dms' % seuils[3], 'le pire'))
    print('-' * 78)
    # seaux : [<30, <100, <300, <1000, <3000, >=3000]
    def au_dela(r, i):
        return sum(r['seaux'][i + 1:])
    lents = sorted(routes, key=lambda r: -au_dela(r, 2))
    montres = 0
    for r in lents:
        if au_dela(r, 2) == 0:
            break
        print('  %-34s %9d %9d %8.0fms'
              % (r['cle'][:34], au_dela(r, 2), au_dela(r, 3), r['max']))
        montres += 1
        if montres >= a.n:
            break
    if not montres:
        print('  aucune requete au-dela de %d ms — rien ne pique.' % seuils[2])
    _phases(t)
    print('=' * 78)
    print('  A LIRE AVEC SA DATE : pendant la campagne de retag, ce releve est')
    print('  une BORNE HAUTE — le tagueur tient le NAS et le GPU. Le meme banc')
    print('  relu apres la campagne donne la ligne de base propre.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
