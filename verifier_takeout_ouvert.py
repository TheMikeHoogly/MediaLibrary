#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L'export Takeout est-il vraiment ouvert en entier ?
──────────────────────────────────────────────────────────────────────────────

POURQUOI CET INSTRUMENT EXISTE

« Extraction effectuée OK » n'est pas une preuve. Le dézippage a **une** panne
qui se lit comme un succès : le fichier écrit à moitié. Il porte le bon nom,
il est au bon endroit, il ne manque à personne — et il ne pèse pas la bonne
taille. La chaîne d'après, `verifier_photos_google.py`, compare justement des
NOMS et des TAILLES : un fichier tronqué du côté Google devient un PROBABLE au
lieu d'un CERTAIN, et le verdict qui autorise à effacer 75 Go se dégrade sans
que personne sache pourquoi.

L'autre panne est plus bête et plus grave : **un lot jamais ouvert**. Rien ne
manque visiblement — l'arbre a des dossiers, des photos, des années. Ce sont
les photos ABSENTES qui, ensuite, interdiront tout effacement, et on cherchera
la cause chez Google alors qu'elle est dans un `.zip` resté fermé.

Le contrôle est le même travail que le dézippage, moins l'écriture : on relit
le SOMMAIRE de chaque lot et on demande au disque si chaque membre y est, à la
bonne taille. C'est `dezipper_takeout.extraire(appliquer=False)` — **la même
traversée**, donc le contrôle et le geste ne peuvent pas diverger.

CE QU'IL NE PEUT PAS VOIR, ET IL LE DIT

Cet export se nomme `takeout-<date>-1-001.zip` : **la série n'annonce aucun
total**. Un trou au milieu se voit (`001, 002, 004`) ; un lot manquant à la
FIN est invisible aux noms seuls. Le rapport dit donc le plus haut numéro vu
et rappelle qu'il faut le comparer à ce que la page Google Takeout annonçait.
Un banc qui ne SAIT pas ne rend pas vert en silence.

Il ne vérifie pas les CRC : la taille tient lieu de preuve, comme partout dans
cette chaîne, et le rapport le dit. `dezipper_takeout.py --tester` les calcule
si on veut payer la lecture de 96 Go.

Il n'écrit rien, nulle part : famille `verifier_`, lecture seule.

USAGE
    python verifier_takeout_ouvert.py
    python verifier_takeout_ouvert.py --json=_takeout_ouvert.json
    python verifier_takeout_ouvert.py --source=D:/Takeout --cible=D:/ouvert

    Sortie 0 = tout ce que les lots contiennent est sur le disque, entier.
    1 = au moins un membre absent ou tronqué, un lot illisible, ou un trou.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dezipper_takeout as D                                   # noqa: E402

LISTE_MAX = 25


def rapport(source, cible, zips, inv, manquants, total, compte, griefs,
            complet, ecrire=print):
    """True si l'export est ouvert en entier."""
    ok = True
    ecrire("")
    ecrire("=" * 74)
    ecrire("  TAKEOUT - L EXPORT EST-IL OUVERT EN ENTIER ?")
    ecrire("=" * 74)
    ecrire("  lots   : %s" % source)
    ecrire("  ouvert : %s" % cible)
    ecrire("")

    if not zips:
        ecrire("  AUCUN .zip dans le dossier des lots : rien a controler.")
        ecrire("  (Sans les lots, l arbre ouvert ne se prouve pas.)")
        return False
    if not Path(cible).is_dir():
        ecrire("  Le dossier ouvert n existe pas. Rien n a ete extrait.")
        return False

    ecrire("  %d lot(s), %s compresses, %d fichiers distincts (%s ouverts)"
           % (len(zips), D.go(inv['octets_zip']), inv['fichiers_distincts'],
              D.go(inv['octets_distincts'])))

    if inv['erreurs']:
        ok = False
        ecrire("")
        ecrire("  LOT(S) ILLISIBLE(S) (%d) :" % len(inv['erreurs']))
        for e in inv['erreurs'][:LISTE_MAX]:
            ecrire("    %-44s %s" % (e['zip'][:44], e['cause'][:56]))

    if manquants:
        ok = False
        ecrire("")
        ecrire("  LOT(S) MANQUANT(S) dans la numerotation : %s"
               % ', '.join(str(i) for i in manquants[:LISTE_MAX]))
    else:
        haut = max((D.numero_de_lot(p.name) or (0, None))[0] for p in zips)
        ecrire("  Numerotation : aucun trou, du 1 au %d." % haut)
        if not total:
            ecrire("  PORTEE : ces noms n annoncent AUCUN total. Un lot")
            ecrire("  manquant a la FIN serait invisible ici - comparer %d"
                   % haut)
            ecrire("  avec ce que la page Google Takeout annoncait.")

    ecrire("")
    ecrire("  entiers sur le disque : %d" % compte['saute'])
    ecrire("  ABSENTS               : %d" % compte['absent'])
    ecrire("  TRONQUES              : %d" % compte['tronque'])
    ecrire("  refuses (hors cible)  : %d" % compte['refuse'])
    for famille, quoi in (('absent', 'ABSENTS du disque'),
                          ('tronque', 'TRONQUES (bon nom, mauvaise taille)'),
                          ('refuse', 'REFUSES (chemin sortant de la cible)')):
        lignes = griefs.get(famille) or []
        if not lignes:
            continue
        ok = False
        ecrire("")
        ecrire("  %s — %d listes :" % (quoi, min(len(lignes), LISTE_MAX)))
        for x in lignes[:LISTE_MAX]:
            ecrire("    %s" % x[:70])
        if compte[famille] > len(lignes):
            ecrire("    ... et %d autre(s), non listes mais COMPTES"
                   % (compte[famille] - len(lignes)))

    if not complet:
        ok = False
        ecrire("")
        ecrire("  Le controle s est INTERROMPU : il ne couvre pas tous les")
        ecrire("  lots. Ce qui precede ne prouve rien sur le reste.")

    ecrire("")
    ecrire("  Empreintes NON calculees : la taille tient lieu de preuve.")
    ecrire("  (dezipper_takeout.py --tester lit les 96 Go si on veut payer.)")
    ecrire("")
    if ok:
        ecrire("  L EXPORT EST OUVERT EN ENTIER. Suite :")
        gp = D.trouver_google_photos(cible)
        ecrire("    verifier_photos_google.py --takeout %s"
               % (gp if gp else '<dossier Google Photos>'))
    else:
        ecrire("  NE PAS CONCLURE SUR CET ARBRE. Relancer le dezippage :")
        ecrire("  il reprend ou il en est, et ne reecrit que ce qui manque.")
    ecrire("=" * 74)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="L export Takeout est-il ouvert en entier ?")
    ap.add_argument('--source', default=D.SOURCE_DEFAUT)
    ap.add_argument('--cible', default=None)
    ap.add_argument('--json', dest='sortie_json', default=None)
    a = ap.parse_args(argv)

    source = Path(a.source)
    cible = Path(a.cible) if a.cible else source / 'extrait'

    zips = D.lister_zips(source)
    print("  lecture du sommaire de %d lot(s)..." % len(zips))
    inv = D.inventaire(zips)
    manquants, total = D.trous(zips)
    print("  controle du disque, lot par lot :")
    compte, _octets, griefs, complet = (
        D.extraire(zips, cible, appliquer=False)
        if zips and Path(cible).is_dir()
        else ({e: 0 for e in D.ETATS}, 0,
              {'absent': [], 'tronque': [], 'refuse': []}, False))
    ok = rapport(source, cible, zips, inv, manquants, total, compte, griefs,
                 complet)

    if a.sortie_json:
        Path(a.sortie_json).write_text(json.dumps(
            {'source': str(source), 'cible': str(cible), 'lots': len(zips),
             'total_annonce': total, 'manquants': manquants,
             'erreurs': inv['erreurs'], 'fichiers_distincts':
             inv['fichiers_distincts'], 'compte': compte, 'griefs': griefs,
             'complet': complet, 'ok': ok},
            indent=2, ensure_ascii=False), encoding='utf-8')
        print("  rapport JSON : %s" % a.sortie_json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
