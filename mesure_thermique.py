#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — que sait dire cette machine de sa propre temperature ?
------------------------------------------------------------------------------

POURQUOI CET INSTRUMENT EXISTE

Le 28/08 a 23:10:15, la machine s'est coupee net sous charge : `Kernel-Power
41`, aucun minidump, rien dans le journal. Le seul indice etait indirect et je
l'ai d'abord mal lu : la session qui est morte taguait a **27,2 s de moyenne**
contre 9,7 a 22,8 s pour toutes les autres du jour, et 14,0 s apres le
redemarrage a froid sur le meme travail. Deux a trois fois plus lente, puis
plus rien. C'est une signature de bridage -- mais deduite, jamais mesuree.

Une machine qui tague des heures avec le GPU a 100 % doit pouvoir DIRE sa
temperature. Le journal du serveur porte deja les durees ; y joindre la
temperature les corrole par construction, sans CSV a croiser a la main.

CE QUE CET INSTRUMENT ETABLIT, ET CE QU'IL N'ETABLIT PAS

Il demande a `nvidia-smi` -- fourni par le pilote, aucune dependance -- champ
par champ, ce que la carte accepte de rendre. Un champ non supporte rend
`[N/A]` : on le SAIT au lieu de le supposer, et la greffe dans `hw_state`
n'embarquera que ce qui existe.

Le **CPU** n'est pas de la partie, et c'est une limite, pas un oubli :
`psutil.sensors_temperatures()` ne rend rien sous Windows, et la classe WMI
`MSAcpi_ThermalZoneTemperature` n'est presque jamais implementee sur un
portable. Sa temperature demande un logiciel tiers (HWiNFO). Le GPU suffit
ici : c'est lui qui est sature.

Le champ qui vaut le voyage est `clocks_throttle_reasons.active` : la carte y
DIT elle-meme pourquoi elle ralentit -- thermique, puissance, ou rien. C'est un
fait rendu par le materiel, pas une inference tiree d'un chronometre.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).

USAGE
    python mesure_thermique.py
    python mesure_thermique.py --echantillons 12 --pause 5
"""

import argparse
import subprocess
import sys
import time

# Un par un : un seul champ refuse fait echouer TOUTE la requete groupee, et on
# ne saurait pas lequel. Les demander separement coute quelques millisecondes
# et rend un inventaire exact.
CHAMPS = [
    'temperature.gpu',
    'temperature.memory',
    'clocks.sm',
    'clocks.max.sm',
    'power.draw',
    'power.limit',
    'utilization.gpu',
    'memory.used',
    'clocks_throttle_reasons.active',
    'clocks_throttle_reasons.hw_thermal_slowdown',
    'clocks_throttle_reasons.sw_thermal_slowdown',
    'clocks_throttle_reasons.hw_power_brake_slowdown',
]


def lire(champ, timeout=5):
    """Valeur du champ, ou None si nvidia-smi le refuse."""
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=' + champ,
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    val = (r.stdout or '').strip().splitlines()
    if not val:
        return None
    v = val[0].strip()
    return None if v in ('', '[N/A]', '[Not Supported]') else v


def inventaire(ecrire=print):
    ecrire('=' * 74)
    ecrire('  CE QUE nvidia-smi ACCEPTE DE RENDRE SUR CETTE MACHINE')
    ecrire('=' * 74)
    dispo = {}
    for c in CHAMPS:
        v = lire(c)
        dispo[c] = v
        ecrire('  %-46s %s' % (c, v if v is not None else '-- NON SUPPORTE --'))
    return dispo


def suivre(n, pause, ecrire=print):
    ecrire('')
    ecrire('=' * 74)
    ecrire('  %d RELEVES A %d s D INTERVALLE' % (n, pause))
    ecrire('=' * 74)
    ecrire('  heure     temp  util  horloge/max   watts   bridage')
    for i in range(n):
        t = lire('temperature.gpu')
        u = lire('utilization.gpu')
        c = lire('clocks.sm')
        cm = lire('clocks.max.sm')
        w = lire('power.draw')
        b = lire('clocks_throttle_reasons.active')
        ecrire('  %s   %4s  %4s  %5s/%-5s  %6s   %s'
               % (time.strftime('%H:%M:%S'), t or '?', u or '?',
                  c or '?', cm or '?', w or '?', b or '?'))
        if i + 1 < n:
            time.sleep(pause)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--echantillons', type=int, default=6)
    ap.add_argument('--pause', type=int, default=5)
    a = ap.parse_args(argv)
    d = inventaire()
    if d.get('temperature.gpu') is None:
        print('')
        print('  Aucune temperature GPU lisible : la greffe dans hw_state')
        print('  n aurait rien a porter. Ne pas la faire.')
        return 1
    suivre(a.echantillons, a.pause)
    print('')
    print('  Le bridage se lit dans la derniere colonne. "Not Active" = la')
    print('  carte tourne libre ; toute autre valeur NOMME la cause.')
    print('=' * 74)
    return 0


if __name__ == '__main__':
    sys.exit(main())
