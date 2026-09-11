#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pourquoi `GET /api/corbeille` met 4,9 s — et le met SOUS `FILE_OPS_LOCK`.

Relevé du 10/09 : 4,88 s au pire. `FileOps.corbeille()` relit le journal
(`fichiers_undo.json`) puis, pour CHAQUE effacement, interroge le NAS :

    dst.exists()                      un aller-retour SMB
    dst.is_dir()                      un deuxième
    dst.stat() (ou rglob + stat)      un troisième, ou un par fichier

Et la route tient le verrou global des opérations de fichiers pendant tout ce
temps : aucun déplacement, aucune restauration ne peut partir.

Ce banc compare, sur le VRAI journal et le VRAI NAS, trois écritures qui
doivent rendre exactement les mêmes (existe, octets) :

  1. actuelle     exists + is_dir + stat/rglob       (l'écriture de fichiers.py)
  2. un stat      os.stat une fois ; S_ISDIR décide ; scandir pour un dossier
  3. par dossier  un os.scandir par dossier-parent — Windows livre la taille
                  avec la ligne du répertoire

Méthodes ALTERNÉES d'un tour à l'autre, pour que le cache SMB ne favorise pas
celle qui passe en second. Il n'écrit RIEN et n'ouvre aucun fichier.

  python mesure_corbeille.py
  python mesure_corbeille.py --tours 3
"""

import argparse
import json
import os
import stat as st_mod
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent


def lire_effacements(journal):
    try:
        j = json.loads(Path(journal).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [r for r in j if isinstance(r, dict) and r.get('op') == 'delete'
            and r.get('dst')]


def actuelle(dsts):
    """L'écriture de `FileOps.corbeille` au 11/09, à l'identique."""
    out = []
    for d in dsts:
        dst = Path(d)
        octets = 0
        existe = dst.exists()
        if existe:
            try:
                octets = (sum(f.stat().st_size for f in dst.rglob('*') if f.is_file())
                          if dst.is_dir() else dst.stat().st_size)
            except OSError:
                pass
        out.append((existe, octets))
    return out


def _taille_dossier(chemin):
    total = 0
    pile = [chemin]
    while pile:
        try:
            with os.scandir(pile.pop()) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            pile.append(e.path)
                        elif e.is_file():
                            total += e.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def un_stat(dsts):
    out = []
    for d in dsts:
        try:
            s = os.stat(d)
        except OSError:
            out.append((False, 0))
            continue
        if st_mod.S_ISDIR(s.st_mode):
            out.append((True, _taille_dossier(d)))
        else:
            out.append((True, s.st_size))
    return out


def par_dossier(dsts):
    """Un scandir par dossier-parent ; les lignes du répertoire portent la
    taille. Un effacement dont le parent n'existe plus : absent."""
    parents = {}
    for d in dsts:
        p = os.path.dirname(d)
        if p not in parents:
            vus = {}
            try:
                with os.scandir(p) as it:
                    for e in it:
                        vus[e.name.lower()] = e
            except OSError:
                pass
            parents[p] = vus
    out = []
    for d in dsts:
        e = parents[os.path.dirname(d)].get(os.path.basename(d).lower())
        if e is None:
            out.append((False, 0))
        elif e.is_dir():
            out.append((True, _taille_dossier(e.path)))
        else:
            try:
                out.append((True, e.stat().st_size))
            except OSError:
                out.append((True, 0))
    return out


METHODES = [('actuelle (exists+is_dir+stat)', actuelle),
            ('un stat', un_stat),
            ('un scandir par dossier', par_dossier)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--journal', default='fichiers_undo.json')
    ap.add_argument('--tours', type=int, default=3)
    a = ap.parse_args(argv)
    eff = lire_effacements(RACINE / a.journal)
    if not eff:
        print('  aucun effacement dans %s' % a.journal)
        return 2
    dsts = [r['dst'] for r in eff]
    print('Journal  : %s, %d effacements, %d dossiers-parents distincts'
          % (a.journal, len(dsts), len({os.path.dirname(d) for d in dsts})))
    print('Tours    : %d, methodes alternees' % a.tours)
    print()
    temps = {n: [] for n, _f in METHODES}
    resultats = {}
    for t in range(a.tours):
        ordre = METHODES[t % len(METHODES):] + METHODES[:t % len(METHODES)]
        for nom, f in ordre:
            t0 = time.perf_counter()
            r = f(dsts)
            temps[nom].append(time.perf_counter() - t0)
            resultats.setdefault(nom, r)
    ref = resultats[METHODES[0][0]]
    base = min(temps[METHODES[0][0]])
    print('  %-32s %10s %10s %7s %s' % ('methode', 'premier', 'meilleur', 'x', 'accord'))
    print('  ' + '-' * 72)
    for nom, _f in METHODES:
        accord = 'oui' if resultats[nom] == ref else 'NON'
        print('  %-32s %8.0fms %8.0fms %6.1f  %s'
              % (nom, temps[nom][0] * 1000, min(temps[nom]) * 1000,
                 base / max(min(temps[nom]), 1e-9), accord))
    presents = sum(1 for e, _o in ref if e)
    print()
    print('  %d effacements presents sur le disque, %.1f Mo'
          % (presents, sum(o for _e, o in ref) / 1048576))
    if any(resultats[n] != ref for n, _f in METHODES):
        for nom, _f in METHODES:
            diff = [i for i, (x, y) in enumerate(zip(resultats[nom], ref)) if x != y]
            if diff:
                print('  %s differe sur %d entree(s), ex. %s : %s vs %s'
                      % (nom, len(diff), dsts[diff[0]][-60:],
                         resultats[nom][diff[0]], ref[diff[0]]))
    print()
    print('  A LIRE AVEC SA DATE : pendant la campagne de retag, le NAS est dispute.')
    print('  Rien n a ete ecrit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
