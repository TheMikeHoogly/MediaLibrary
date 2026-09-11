#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le péage du GIL : ce que coûtent des entrées-sorties quand des fils CPU tournent.

Constat du 11/09 : la liste de la corbeille (252 `os.stat` sur le NAS) prend
**67 ms** dans un banc seul, et **0,9 à 2 s** dans le serveur. Hypothèse : un
appel système rend le GIL ; pour le reprendre, le fil attend que le fil CPU le
lâche — au plus tard à l'intervalle de bascule (`sys.getswitchinterval()`,
5 ms par défaut). Le serveur a toujours des fils CPU en Python (visages,
DINOv2, encodage sémantique, clustering). 252 × ~5 ms ≈ 1,3 s.

Ce banc le vérifie sans toucher au serveur :
  * la même série de `stat` (fichiers de la corbeille du NAS, et fichiers
    locaux de `photo_thumbs`) ;
  * seule, puis avec 1 et 3 fils CPU purs Python à côté ;
  * avec l'intervalle par défaut, puis à 1 ms et 0,5 ms ;
  * conditions ALTERNÉES, trois tours, on garde le meilleur.

**Et la résolution du minuteur de Windows.** Premier passage (11/09) : à 5 ms
comme à 1 ms, un `stat` local passe de 0,04 ms à ~14 ms avec UN fil CPU —
c'est le pas du minuteur système (15,6 ms), pas l'intervalle, qui fixe
l'attente. Une variante demande donc au minuteur une résolution de 1 ms
(`timeBeginPeriod(1)`, pour CE processus seulement, rendue par
`timeEndPeriod` à la fin de la condition — rien n'est changé dans Windows).

Et il mesure le prix de l'autre côté : combien de tours de boucle un fil CPU
fait par seconde à chaque intervalle — baisser l'intervalle a un coût, il
faut le connaître avant de le proposer.

Il n'écrit RIEN.

  python mesure_peage_gil.py
  python mesure_peage_gil.py --n 250 --tours 3
"""

import argparse
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

RACINE = Path(__file__).resolve().parent


def cibles_nas(n):
    try:
        j = json.loads((RACINE / 'fichiers_undo.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [r['dst'] for r in j if isinstance(r, dict) and r.get('op') == 'delete'][:n]


def cibles_locales(n):
    out = []
    try:
        with os.scandir(RACINE / 'photo_thumbs') as it:
            for e in it:
                out.append(e.path)
                if len(out) >= n:
                    break
    except OSError:
        pass
    return out


def serie(chemins):
    t0 = time.perf_counter()
    for c in chemins:
        try:
            os.stat(c)
        except OSError:
            pass
    return time.perf_counter() - t0


class FilsCPU:
    def __init__(self, n):
        self.n = n
        self.stop = threading.Event()
        self.tours = [0] * n
        self.fils = []

    def _tourne(self, i):
        x = 0
        while not self.stop.is_set():
            for _ in range(1000):
                x = (x * 31 + 7) % 1000003
            self.tours[i] += 1000

    def __enter__(self):
        for i in range(self.n):
            t = threading.Thread(target=self._tourne, args=(i,), daemon=True)
            t.start()
            self.fils.append(t)
        time.sleep(0.2)
        self.t0 = time.perf_counter()
        self.depart = list(self.tours)
        return self

    def __exit__(self, *a):
        self.duree = time.perf_counter() - self.t0
        self.fait = sum(self.tours) - sum(self.depart)
        self.stop.set()
        for t in self.fils:
            t.join()


@contextmanager
def minuteur(ms):
    """Résolution du minuteur Windows pour ce processus (None : ne rien
    demander). Toujours rendue, même sur exception."""
    winmm = None
    if ms and os.name == 'nt':
        try:
            import ctypes
            winmm = ctypes.WinDLL('winmm')
            winmm.timeBeginPeriod(int(ms))
        except Exception:                                      # noqa: BLE001
            winmm = None
    try:
        yield winmm is not None
    finally:
        if winmm is not None:
            winmm.timeEndPeriod(int(ms))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--n', type=int, default=250)
    ap.add_argument('--tours', type=int, default=3)
    a = ap.parse_args(argv)
    series = [('NAS', cibles_nas(a.n)), ('local', cibles_locales(a.n))]
    series = [(nom, c) for nom, c in series if c]
    if not series:
        print('  aucune cible (ni corbeille, ni photo_thumbs)')
        return 2
    defaut = sys.getswitchinterval()
    intervalles = [defaut, 0.001, 0.0005]
    minuteurs = [None, 1]
    conditions = [(mn, ic, nf) for mn in minuteurs for ic in intervalles
                  for nf in (0, 1, 3)]
    print('Python %s, intervalle de bascule par defaut %.1f ms, %d coeurs'
          % (sys.version.split()[0], defaut * 1000, os.cpu_count() or 0))
    for nom, c in series:
        print('Serie %-5s : %d stat' % (nom, len(c)))
    print()
    # chauffe : le cache SMB ne doit pas favoriser la premiere condition
    for _nom, c in series:
        serie(c)
    meilleurs = {}
    debit = {}
    for t in range(a.tours):
        ordre = conditions[t % len(conditions):] + conditions[:t % len(conditions)]
        for mn, ic, nf in ordre:
            sys.setswitchinterval(ic)
            try:
                with minuteur(mn):
                    if nf:
                        with FilsCPU(nf) as f:
                            for nom, c in series:
                                d = serie(c)
                                k = (nom, mn, ic, nf)
                                meilleurs[k] = min(meilleurs.get(k, 9e9), d)
                        debit.setdefault((mn, ic, nf), []).append(
                            f.fait / max(f.duree, 1e-9))
                    else:
                        for nom, c in series:
                            d = serie(c)
                            k = (nom, mn, ic, nf)
                            meilleurs[k] = min(meilleurs.get(k, 9e9), d)
            finally:
                sys.setswitchinterval(defaut)
    for nom, c in series:
        print('  SERIE %s — meilleur de %d tours, en ms (et ms par stat)' % (nom, a.tours))
        print('  %-26s %14s %14s %14s' % ('minuteur / intervalle', 'seul',
                                          '+1 fil CPU', '+3 fils CPU'))
        for mn in minuteurs:
            for ic in intervalles:
                cells = []
                for nf in (0, 1, 3):
                    d = meilleurs[(nom, mn, ic, nf)]
                    cells.append('%7.0f (%5.2f)' % (d * 1000, d * 1000 / len(c)))
                print('  %-26s %14s %14s %14s'
                      % ('%s / %.1f ms' % ('defaut' if mn is None else '1 ms', ic * 1000),
                         *cells))
        print()
    print('  LE PRIX DE L AUTRE COTE — tours de boucle CPU par seconde (moyenne)')
    base = {}
    for mn in minuteurs:
        for ic in intervalles:
            for nf in (1, 3):
                v = sum(debit[(mn, ic, nf)]) / len(debit[(mn, ic, nf)])
                base.setdefault(nf, v)
                print('  minuteur %-6s intervalle %4.1f ms, %d fil(s) : %12.0f tours/s  (%3.0f %%)'
                      % ('defaut' if mn is None else '1 ms', ic * 1000, nf, v,
                         100 * v / base[nf]))
    print()
    print('  A LIRE AVEC SA DATE : la machine fait tourner le serveur et la campagne')
    print('  pendant ce banc ; les ecarts ENTRE conditions comptent, pas l absolu.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
