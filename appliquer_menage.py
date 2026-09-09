#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le grand nettoyage du dépôt — la POLITIQUE propose, l'INVENTAIRE oppose son veto.

Ce script ne décide pas tout seul ce qui est jetable. Il applique une politique
nommée (des motifs de fichiers, chacun avec sa raison), puis il confronte
CHAQUE candidat à `inventaire_fichiers_orphelins.py`, exécuté à l'instant :
**si l'inventaire dit qu'un fichier est lu par du code, par une convention ou
par un motif, il ne part pas, même si la politique le nommait.**

C'est l'inverse d'un `del *.json`, et c'est voulu. Le 08/09, `_google.json` est
parti dans `_to_delete/` parce qu'il commençait par un souligné, et le bat 32
s'est cassé : il le lisait en entrée. Le `.gitignore` en a tiré la règle du
projet — **« c'est le RÔLE qui décide, pas le préfixe »**. Ici le rôle est
mesuré, pas supposé.

RIEN N'EST EFFACÉ. Les fichiers sont DÉPLACÉS sous
`_corbeille_menage\\<horodatage>\\`, arborescence conservée, avec un manifeste.
`--annuler <dossier>` les remet exactement où ils étaient. C'est la même règle
que partout ailleurs dans ce projet : un geste destructif est réversible, ou
il n'est pas.

  python appliquer_menage.py                    # APERCU, n'écrit rien
  python appliquer_menage.py --appliquer
  python appliquer_menage.py --journaux 30      # + les undo de plus de 30 j
  python appliquer_menage.py --annuler _corbeille_menage\\20260909_180000
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
CORBEILLE = RACINE / '_corbeille_menage'

# LA POLITIQUE. Chaque famille porte sa raison en clair : un motif sans raison
# est une suppression qu'on ne saura pas justifier dans six mois.
POLITIQUE = [
    ('rapports_perimes',
     ['_rapport_google_*.json', '_rapport_perdus_takeout.json',
      '_rapport_sef_*.json', '_rapport_takeout_*.json'],
     "rapports d'un fonds qui n'existe plus : le Takeout est efface (bat 49)"),
    ('quarantaine_du_08_09',
     ['_to_delete/*', '_to_delete/**/*'],
     "le dossier porte son nom depuis le 08/09"),
    ('archives_de_carnet',
     ['docs/_archive/*'],
     "vieux plans et audits : git les garde, le dossier n'en a plus besoin"),
    ('pages_mortes',
     ['ui/pages/faces.html'],
     "page retiree : /faces est un 302 vers /people, plus personne ne la lit"),
]

# Les journaux d'annulation sont HORS politique par defaut, et c'est un choix :
# ils pesent le plus (28,9 Mo) mais ils sont la seule chose de cette liste
# qu'on ne peut pas recuperer -- 88 des 89 sont gitignores, donc absents du
# depot. Il faut les demander explicitement, avec un age.
MOTIF_JOURNAUX = ['docs/undo_*.json', 'docs/plan_rangement*.json']

# Ce que l'inventaire doit dire pour qu'un fichier puisse partir.
FAMILLES_JETABLES = {'ORPHELIN', 'CITE EN DOC SEUL'}


def inventaire_frais():
    """Relance l'inventaire MAINTENANT. Jamais un rapport garde.

    Lecon du 09/09, payee deux fois : un rapport de onze jours a fait dire
    « rien a recuperer » sur un Takeout qui portait 570 photos absentes. Un
    rapport n'est pas une preuve, c'est une preuve DATEE."""
    sys.path.insert(0, str(RACINE))
    try:
        import inventaire_fichiers_orphelins as inv
    except ImportError:
        return None, "inventaire_fichiers_orphelins.py introuvable"
    try:
        lignes = inv.inventorier(RACINE)
    except Exception as e:                                        # noqa: BLE001
        return None, "l inventaire a echoue : %s" % e
    return {x['fichier'].replace('\\', '/'): x['famille'] for x in lignes}, None


def _candidats(motifs):
    for m in motifs:
        for p in RACINE.glob(m):
            if p.is_file():
                yield p


def trier(avec_journaux=0):
    """(a_deplacer, retenus, erreur) — la politique passee au crible."""
    fam, err = inventaire_frais()
    if err:
        return [], [], err

    politique = list(POLITIQUE)
    if avec_journaux:
        limite = time.time() - avec_journaux * 86400
        politique.append(('journaux_annulation', MOTIF_JOURNAUX,
                          "journaux d annulation de plus de %d jours"
                          % avec_journaux))

    a_deplacer, retenus, vus = [], [], set()
    for nom, motifs, raison in politique:
        for p in _candidats(motifs):
            rel = str(p.relative_to(RACINE)).replace('\\', '/')
            if rel in vus:
                continue
            vus.add(rel)
            if nom == 'journaux_annulation':
                try:
                    if p.stat().st_mtime > limite:
                        retenus.append((rel, 'journal trop recent'))
                        continue
                except OSError:
                    continue
            f = fam.get(rel)
            # LE VETO. Un fichier que l'inventaire n'a pas vu (None) est
            # retenu lui aussi : ne pas savoir n'est pas savoir que non.
            if f not in FAMILLES_JETABLES:
                retenus.append((rel, 'inventaire : %s' % (f or 'non vu')))
                continue
            try:
                octets = p.stat().st_size
            except OSError:
                octets = 0
            a_deplacer.append({'fichier': rel, 'famille': nom,
                               'raison': raison, 'octets': octets})
    a_deplacer.sort(key=lambda x: -x['octets'])
    retenus.sort()
    return a_deplacer, retenus, None


def deplacer(travaux, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    faits, ratees = [], []
    for t in travaux:
        src = RACINE / t['fichier']
        cible = dest / t['fichier']
        try:
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(cible))
            faits.append(t['fichier'])
        except OSError as e:
            ratees.append((t['fichier'], str(e)))
    manif = dest / '_manifeste.json'
    manif.write_text(json.dumps(
        {'quand': time.strftime('%Y-%m-%d %H:%M:%S'), 'racine': str(RACINE),
         'deplaces': faits, 'ratees': ratees}, indent=1, ensure_ascii=False),
        encoding='utf-8')
    return faits, ratees, manif


def annuler(dossier):
    d = Path(dossier)
    manif = d / '_manifeste.json'
    if not manif.is_file():
        print("manifeste introuvable : %s" % manif)
        return 2
    m = json.loads(manif.read_text(encoding='utf-8'))
    remis, ratees = 0, []
    for rel in m.get('deplaces') or []:
        src, cible = d / rel, RACINE / rel
        if not src.is_file():
            ratees.append((rel, 'absent de la corbeille'))
            continue
        if cible.exists():
            ratees.append((rel, 'un fichier est DEJA revenu a cette place'))
            continue
        try:
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(cible))
            remis += 1
        except OSError as e:
            ratees.append((rel, str(e)))
    print("  %d fichier(s) remis en place." % remis)
    for rel, pourquoi in ratees:
        print("  ! %s : %s" % (rel, pourquoi))
    return 1 if ratees else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--appliquer', action='store_true',
                    help='DEPLACE. Sans lui, rien ne bouge.')
    ap.add_argument('--journaux', type=int, default=0, metavar='JOURS',
                    help='inclure les journaux d annulation plus vieux que N '
                         'jours (0 = ne pas y toucher)')
    ap.add_argument('--annuler', default='', metavar='DOSSIER')
    a = ap.parse_args(argv)

    if a.annuler:
        return annuler(a.annuler)

    print("  inventaire en cours (qui lit quoi) ...")
    travaux, retenus, err = trier(a.journaux)
    if err:
        print("  ARRET : %s" % err)
        return 2

    total = sum(t['octets'] for t in travaux)
    print("=" * 74)
    print("  GRAND MENAGE -- %d fichier(s), %.1f Mo" % (len(travaux),
                                                        total / 1e6))
    print("=" * 74)
    par_fam = {}
    for t in travaux:
        par_fam.setdefault(t['famille'], []).append(t)
    for nom, l in par_fam.items():
        print("  %-22s %4d fichier(s)  %8.1f Ko" % (
            nom, len(l), sum(x['octets'] for x in l) / 1024))
        print("     %s" % l[0]['raison'])
        for x in l[:6]:
            print("       %8.1f Ko  %s" % (x['octets'] / 1024, x['fichier']))
        if len(l) > 6:
            print("       ... et %d autre(s)" % (len(l) - 6))
    if retenus:
        print("-" * 74)
        print("  RETENUS par le veto de l'inventaire (%d) -- la politique les"
              % len(retenus))
        print("  nommait, leurs LECTEURS les gardent :")
        for rel, pourquoi in retenus[:12]:
            print("    %-52s %s" % (rel[:52], pourquoi))
        if len(retenus) > 12:
            print("    ... et %d autre(s)" % (len(retenus) - 12))
    print("=" * 74)

    if not a.appliquer:
        print("  APERCU -- rien n'a bouge. Ajoute --appliquer pour deplacer.")
        return 0
    if not travaux:
        print("  Rien a deplacer.")
        return 0

    dest = CORBEILLE / time.strftime('%Y%m%d_%H%M%S')
    faits, ratees, manif = deplacer(travaux, dest)
    print("  %d fichier(s) deplace(s) vers %s" % (len(faits), dest))
    print("  manifeste : %s" % manif)
    print("  pour tout remettre : --annuler \"%s\"" % dest)
    for rel, e in ratees:
        print("  ! %s : %s" % (rel, e))
    return 1 if ratees else 0


if __name__ == '__main__':
    sys.exit(main())
