#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le processeur de la machine : qui le prend, et combien il en reste au serveur.

Constat du 11/09 au soir. Dans `/api/maint/status`, une phase qui ne fait que
trois `len()` coûte 50 à 107 ms, et un parcours de 44 600 entrées 140 à
320 ms — cinq à dix fois le prix du même code sur une machine au repos.
Écartés, mesures à l'appui : le ramasse-miettes (0 à 1 ms pendant ces
requêtes, `sondes.py`), le GIL (un fil qui dort se réveille avec 0,4 ms de
retard moyen), et la pagination seule (après `ollama stop`, 3 Go de RAM
libres, et le chiffre ne bouge pas).

Hypothèse restante : le PROCESSEUR. Ollama ne loge que la moitié du modèle en
VRAM (1,74 Go sur 3,47) ; l'autre moitié calcule sur le CPU, avec 25 fils. Un
fil Python qui calcule doit alors partager les huit cœurs — et Windows le
retire du processeur des dizaines de millisecondes à la fois.

Ce banc mesure, pendant N secondes, sans rien toucher :
  1. l'occupation de chaque cœur ;
  2. les processus qui consomment le plus de CPU (regroupés par nom, en
     « cœurs » : 1,00 = un cœur plein) ;
  3. dans le serveur (`--pid`), le temps CPU de CHAQUE fil — combien de fils
     calculent, et combien.

  python mesure_cpu.py --pid 7852 --secondes 10
"""

import argparse
import sys
import time


def _psutil():
    try:
        import psutil
        return psutil
    except ImportError:
        print('psutil absent.')
        sys.exit(2)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--secondes', type=float, default=10.0)
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args(argv)
    ps = _psutil()

    procs = {}
    for p in ps.process_iter(['name']):
        try:
            procs[p.pid] = (p, (p.info.get('name') or '?').lower(), p.cpu_times())
        except (ps.NoSuchProcess, ps.AccessDenied, OSError):
            continue
    srv = None
    fils_avant = {}
    if a.pid:
        try:
            srv = ps.Process(a.pid)
            fils_avant = {t.id: t.user_time + t.system_time for t in srv.threads()}
        except Exception as e:                                    # noqa: BLE001
            print(f'serveur pid {a.pid} illisible : {type(e).__name__}')
            srv = None
    ps.cpu_percent(percpu=True)
    t0 = time.perf_counter()
    time.sleep(a.secondes)
    coeurs = ps.cpu_percent(percpu=True)
    duree = time.perf_counter() - t0

    print(f'== COEURS ({len(coeurs)}), occupation moyenne sur {duree:.1f} s ==')
    print('  ' + '  '.join(f'{c:5.1f}%' for c in coeurs))
    print(f'  moyenne {sum(coeurs) / len(coeurs):.1f} %  — soit {sum(coeurs) / 100:.2f} coeurs pleins sur {len(coeurs)}')
    print()

    groupes = {}
    for pid, (p, nom, avant) in procs.items():
        try:
            apres = p.cpu_times()
        except (ps.NoSuchProcess, ps.AccessDenied, OSError):
            continue
        d = (apres.user - avant.user) + (apres.system - avant.system)
        g = groupes.setdefault(nom, [0, 0.0])
        g[0] += 1
        g[1] += d
    rangs = sorted(groupes.items(), key=lambda kv: -kv[1][1])[:a.top]
    print(f'== PROCESSUS qui consomment le plus (en coeurs : 1,00 = un coeur plein) ==')
    for nom, (n, d) in rangs:
        print(f'  {nom[:30]:30} {n:3d}  {d / duree:5.2f} coeur(s)')
    print()

    if srv is not None:
        try:
            fils = srv.threads()
        except Exception as e:                                    # noqa: BLE001
            print(f'fils du serveur illisibles : {type(e).__name__}')
            fils = []
        conso = []
        for t in fils:
            d = t.user_time + t.system_time - fils_avant.get(t.id, t.user_time + t.system_time)
            conso.append((d, t.id))
        conso.sort(reverse=True)
        total = sum(d for d, _ in conso)
        print(f'== SERVEUR (pid {a.pid}) : {len(fils)} fils, {total / duree:.2f} coeur(s) au total ==')
        print('  les fils qui ont calcule (en % d un coeur) :')
        actifs = [(d, i) for d, i in conso if d / duree >= 0.01]
        for d, i in actifs[:15]:
            print(f'    fil {i:6d}  {100 * d / duree:6.1f} %')
        print(f'  ({len(actifs)} fils au-dessus de 1 %, {len(fils) - len(actifs)} en attente)')
        print('  (les fils NEUFS depuis le debut de la mesure comptent depuis zero)')
        print()
    print('A LIRE AVEC SA DATE : la campagne et le serveur tournent pendant ce banc.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
