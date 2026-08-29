#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Recense les DOSSIERS VIDES sous une racine (par defaut `_A TRIER`).

LECTURE SEULE : n'efface rien, ecrit `docs/dossiers_vides.json` que
`effacer_dossiers_vides.py` (bat 38) applique. Sortie ASCII, flush a chaque
dossier (un parcours NAS coupe a 600 s doit laisser une trace).

Un dossier est VIDE s'il ne contient aucun fichier, a aucune profondeur —
c'est-a-dire rien, ou seulement des dossiers eux-memes vides. Un dossier qui
ne contient que des SCORIES (`Thumbs.db`, `desktop.ini`, `.DS_Store`,
`._*`) est QUASI-VIDE ; un dossier qui ne contient que des `*_original`
d'ExifTool est un RELIQUAT (regle Motion Photo, etape 2). Les deux sont
comptes a part et jamais effaces ici — la regle « un dossier modifie hier
soir n'est pas vide : compter avant d'effacer ».

    inventaire_dossiers_vides.py                      # _A TRIER de la premiere racine
    inventaire_dossiers_vides.py --racine b64:<dossier>
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
SCORIES = {'thumbs.db', 'desktop.ini', '.ds_store'}


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def deb64(v):
    return base64.b64decode(v[4:]).decode('utf-8') if v.startswith('b64:') else v


def est_scorie(nom):
    n = nom.lower()
    return n in SCORIES or n.startswith('._')


def est_reliquat(nom):
    """Un `*_original` d'ExifTool (la version complete d'une Motion Photo
    apres `-trailer:all=`, regle 1 septies) : pas un media, pas une scorie —
    sa purge est l'etape (2) de la regle, un geste de Mike apres verification."""
    return nom.lower().endswith('_original')


def recenser(racine, log=print):
    """(vides, quasi_vides, dossiers_parcourus). `vides` et `quasi_vides` sont
    des listes de chemins ; un dossier vide dont le parent est vide aussi
    y figure (l'effacement va du plus profond au moins profond)."""
    racine = Path(racine)
    vides, quasi, reliquats, n = [], [], {}, 0
    # bottom-up : on sait pour chaque enfant s'il etait vide avant le parent
    etat = {}       # chemin -> 'vide' | 'quasi' | 'reliquats' | 'plein'
    for r, dirs, files in os.walk(str(racine), topdown=False):
        n += 1
        if n % 200 == 0:
            log('  ... %d dossiers' % n)
        vrais = [f for f in files if not est_scorie(f) and not est_reliquat(f)]
        origs = [f for f in files if est_reliquat(f)]
        scories = [f for f in files if est_scorie(f)]
        enfants = [etat.get(os.path.join(r, d), 'plein') for d in dirs]
        if vrais or 'plein' in enfants:
            etat[r] = 'plein'
        elif origs or 'reliquats' in enfants:
            etat[r] = 'reliquats'
            reliquats[r] = len(origs)
        elif scories or 'quasi' in enfants:
            etat[r] = 'quasi'
            quasi.append(r)
        else:
            etat[r] = 'vide'
            vides.append(r)
    # la racine elle-meme n'est jamais candidate
    vides = [v for v in vides if Path(v) != racine]
    quasi = [v for v in quasi if Path(v) != racine]
    reliquats.pop(str(racine), None)
    return vides, quasi, n, reliquats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--racine', default='')
    a = ap.parse_args(argv)
    if a.racine:
        racine = Path(deb64(a.racine))
    else:
        sys.path.insert(0, str(ICI))
        import inventaire_fonds as F
        racine = Path(str(F.racines()[0])) / '_A TRIER'
    print('RACINE : %s' % asc(racine), flush=True)
    if not racine.is_dir():
        print('  introuvable'); return 1
    t0 = time.time()
    vides, quasi, n, reliquats = recenser(racine, log=lambda s: print(s, flush=True))
    print('%d dossiers parcourus en %.1f s' % (n, time.time() - t0))
    print('=' * 70)
    print('VIDES (effacables sans perte) : %d' % len(vides))
    for v in sorted(vides):
        print('  %s' % asc(os.path.relpath(v, racine)))
    print('QUASI-VIDES (scories seulement, GARDES) : %d' % len(quasi))
    for v in sorted(quasi):
        print('  %s' % asc(os.path.relpath(v, racine)))
    print('RELIQUATS (*_original d ExifTool seulement, GARDES - regle Motion Photo, etape 2) : %d' % len(reliquats))
    for v in sorted(reliquats):
        print('  %s  (%d _original)' % (asc(os.path.relpath(v, racine)), reliquats[v]))
    (ICI / 'docs').mkdir(exist_ok=True)
    (ICI / 'docs' / 'dossiers_vides.json').write_text(json.dumps({
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'), 'racine': str(racine),
        'vides': sorted(vides, key=lambda p: -len(p)),   # profond d'abord
        'quasi_vides': sorted(quasi), 'reliquats': reliquats, 'parcourus': n,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print('liste ecrite : docs/dossiers_vides.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
