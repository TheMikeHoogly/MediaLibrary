#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La mémoire de la machine : qui la tient, et ce que le serveur paie quand elle manque.

Constat du 11/09 au soir, pendant la campagne de retag : `/api/maint/status`
passe 50 à 100 ms dans une phase qui ne fait que TROIS `len()`, et balaie
44 600 entrées en 140-190 ms. Les deux sondes posées le même soir
(`sondes.py`) ont écarté les deux suspects habituels :

  * le ramasse-miettes : 0 à 0,7 ms de collecte pendant ces requêtes ;
  * le GIL : un fil qui dort 20 ms se réveille avec 0,4 ms de retard moyen,
    4 ms au pire.

Et `/api/maint/status` elle-même dit, dans `hw` : **0,4 à 0,7 Go de RAM
disponible sur 16,9**. Hypothèse : la machine PAGINE — les pages des objets
Python de l'index sont sorties de la mémoire vive, et chaque parcours les
refait entrer depuis le disque. Ce banc la vérifie sans rien toucher :

  1. l'état de la mémoire du système (disponible, fichier d'échange) ;
  2. les processus qui la tiennent, REGROUPÉS PAR NOM (plage de travail et
     octets privés) — un nom d'exécutable, jamais une ligne de commande ;
  3. le serveur lui-même (`--pid`, lu dans `/api/serveur`) : plage de travail
     contre octets privés — l'écart est ce que Windows lui a retiré ;
  4. une série de N secondes : mémoire disponible, défauts de page du serveur
     par seconde, et, si Windows veut bien les donner, les pages lues DEPUIS LE
     DISQUE par seconde (compteur système, noms anglais puis français).

Il n'écrit RIEN.

  python mesure_memoire.py --pid 13708
  python mesure_memoire.py --pid 13708 --secondes 30 --top 15
"""

import argparse
import subprocess
import sys
import time

Go = 1024 ** 3
Mo = 1024 ** 2

# Pages lues depuis le disque par seconde (défauts de page DURS), et la mémoire
# disponible, vus par Windows. Les noms des compteurs sont TRADUITS selon la
# langue du système : on essaie l'anglais, puis le français.
COMPTEURS = {
    'anglais': [r'\Memory\Pages Input/sec', r'\Memory\Available MBytes',
                r'\Paging File(_Total)\% Usage'],
    'francais': [r'\Mémoire\Pages en entrée/s', r'\Mémoire\Mégaoctets disponibles',
                 r"\Fichier d'échange(_Total)\Pourcentage d'utilisation"],
}


def _psutil():
    try:
        import psutil
        return psutil
    except ImportError:
        print('psutil absent : ce banc ne peut rien mesurer (pip install psutil).')
        sys.exit(2)


def systeme(ps):
    vm = ps.virtual_memory()
    sw = ps.swap_memory()
    print('== SYSTEME ==')
    print(f'  RAM totale      {vm.total / Go:6.1f} Go')
    print(f'  RAM disponible  {vm.available / Go:6.2f} Go  ({100 - vm.percent:.0f} % libre)')
    print(f'  fichier d echange utilise {sw.used / Go:6.2f} Go sur {sw.total / Go:.1f} Go')
    print()


def processus(ps, top):
    groupes = {}
    refus = 0
    for p in ps.process_iter(['name']):
        try:
            mi = p.memory_info()
        except (ps.NoSuchProcess, ps.AccessDenied, OSError):
            refus += 1
            continue
        nom = (p.info.get('name') or '?').lower()
        g = groupes.setdefault(nom, {'n': 0, 'wset': 0, 'prive': 0})
        g['n'] += 1
        g['wset'] += getattr(mi, 'wset', mi.rss)
        g['prive'] += getattr(mi, 'private', getattr(mi, 'vms', 0))
    rangs = sorted(groupes.items(), key=lambda kv: -kv[1]['prive'])[:top]
    print(f'== PROCESSUS, regroupes par nom, les {top} plus gros en octets PRIVES ==')
    print(f'  {"nom":28} {"n":>3} {"prive Go":>9} {"en RAM Go":>10} {"hors RAM":>9}')
    for nom, g in rangs:
        hors = g['prive'] - g['wset']
        print(f'  {nom[:28]:28} {g["n"]:3d} {g["prive"] / Go:9.2f} {g["wset"] / Go:10.2f} '
              f'{max(0, hors) / Go:8.2f}')
    total_prive = sum(g['prive'] for g in groupes.values())
    print(f'  (tous : {total_prive / Go:.1f} Go prives, {len(groupes)} noms, '
          f'{refus} processus illisibles)')
    print()


def serveur(ps, pid):
    try:
        p = ps.Process(pid)
        mi = p.memory_info()
    except Exception as e:                                        # noqa: BLE001
        print(f'== SERVEUR pid {pid} : illisible ({type(e).__name__}) ==\n')
        return None
    wset = getattr(mi, 'wset', mi.rss)
    prive = getattr(mi, 'private', getattr(mi, 'vms', 0))
    print(f'== SERVEUR (pid {pid}) ==')
    print(f'  octets prives        {prive / Go:6.2f} Go')
    print(f'  plage de travail     {wset / Go:6.2f} Go   (ce qui est EN RAM)')
    print(f'  hors de la RAM       {max(0, prive - wset) / Go:6.2f} Go   '
          f'({100 * max(0, prive - wset) / prive if prive else 0:.0f} % du prive)')
    pic = getattr(mi, 'peak_wset', None)
    if pic:
        print(f'  pic de plage         {pic / Go:6.2f} Go')
    print()
    return p


def typeperf(secondes):
    """Les compteurs système, si Windows les donne. Rend (langue, lignes) ou
    (None, raison)."""
    for langue, noms in COMPTEURS.items():
        try:
            r = subprocess.run(['typeperf', *noms, '-si', '1', '-sc', str(secondes)],
                               capture_output=True, timeout=secondes + 20)
        except Exception as e:                                    # noqa: BLE001
            return None, f'typeperf indisponible ({type(e).__name__})'
        sortie = r.stdout.decode('mbcs' if sys.platform == 'win32' else 'utf-8',
                                 errors='replace')
        lignes = [l for l in sortie.splitlines() if l[:1] == '"' and l[1:2].isdigit()]
        if r.returncode == 0 and lignes:
            return langue, lignes
    return None, 'compteurs refuses dans les deux langues'


def serie(ps, p, secondes):
    print(f'== SERIE : {secondes} s, une mesure par seconde ==')
    print('  s   dispo Go   defauts/s du serveur   plage serveur Go')
    avant = None
    for s in range(secondes):
        vm = ps.virtual_memory()
        ligne = f'  {s:2d}  {vm.available / Go:7.2f}'
        if p is not None:
            try:
                mi = p.memory_info()
                d = getattr(mi, 'num_page_faults', None)
                if d is not None and avant is not None:
                    ligne += f'   {d - avant:14d}'
                else:
                    ligne += f'   {"-":>14}'
                avant = d
                ligne += f'   {getattr(mi, "wset", mi.rss) / Go:14.2f}'
            except Exception:                                     # noqa: BLE001
                ligne += '   (serveur illisible)'
        print(ligne)
        time.sleep(1)
    print('  (les defauts de page de Windows comptent les DOUX et les DURS ;')
    print('   les durs, lus sur le disque, sont dans la serie typeperf ci-dessous)')
    print()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--secondes', type=int, default=20)
    ap.add_argument('--top', type=int, default=15)
    a = ap.parse_args(argv)
    ps = _psutil()
    systeme(ps)
    processus(ps, a.top)
    p = serveur(ps, a.pid) if a.pid else None
    serie(ps, p, a.secondes)
    print(f'== COMPTEURS WINDOWS : {a.secondes} s ==')
    langue, lignes = typeperf(a.secondes)
    if langue is None:
        print(f'  {lignes}')
    else:
        print(f'  (noms en {langue}) horodatage, pages lues du disque/s, Mo disponibles, % fichier d echange')
        for l in lignes:
            print('  ' + l)
    print()
    print('A LIRE AVEC SA DATE : la campagne et le serveur tournent pendant ce banc.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
