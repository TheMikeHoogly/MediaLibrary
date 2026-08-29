#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cree (ou re-mot-de-passe) un compte dans comptes.json, sur le PC du serveur.

C'est le geste d'AMORCAGE du chantier 17 (etape 4) : le premier compte ferme la
porte du serveur (tout le monde doit se connecter), donc il se cree ICI, a la
main, jamais par une route ouverte. Les suivants peuvent passer par Reglages
(admin connecte). Le mot de passe est demande sans echo ; il n'est jamais
ecrit en clair (PBKDF2, 300 000 tours, sel par compte).

    python creer_compte.py Mike            # cree Mike (= l'admin, auteurs.ADMIN)
    python creer_compte.py Flo             # cree Flo (voit Photos Flo\\PRIVE)
    python creer_compte.py Flo --mdp       # change son mot de passe
    python creer_compte.py --liste

Le NOM est celui du dossier `Photos <Nom>` : c'est lui que la vue compare.
Le serveur relit comptes.json des qu'il change : rien a redemarrer.
Sortie ASCII (console cp1252).
"""
import argparse
import getpass
import sys
from pathlib import Path

import comptes as C

ICI = Path(__file__).resolve().parent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('nom', nargs='?', default='')
    ap.add_argument('--mdp', action='store_true', help='changer le mot de passe d un compte existant')
    ap.add_argument('--liste', action='store_true')
    ap.add_argument('--admin', action='store_true', help='drapeau admin (Mike l est d office)')
    ap.add_argument('--fichier', default=str(ICI / 'comptes.json'))
    a = ap.parse_args(argv)
    cs = C.Comptes(a.fichier)
    if a.liste or not a.nom:
        noms = cs.noms()
        print('%d compte(s) dans %s' % (len(noms), a.fichier))
        for n in noms:
            print('  %s%s' % (n, '  (admin)' if cs.est_admin(n) else ''))
        if not noms:
            print('  (aucun : la porte du serveur est OUVERTE, comme avant)')
        return 0
    nom = a.nom.strip()
    if not C.nom_valide(nom):
        print('nom invalide : %r' % nom); return 1
    dossier = Path(r'\\NAS-Bremblens\home\Photos') / ('Photos ' + nom)
    print('compte : %s   (dossier attendu : %s)' % (nom, dossier))
    m1 = getpass.getpass('mot de passe (8 caracteres au moins) : ')
    m2 = getpass.getpass('encore une fois : ')
    if m1 != m2:
        print('les deux saisies different, rien fait'); return 1
    try:
        if a.mdp:
            cs.changer_mdp(nom, m1)
            print('mot de passe change pour %s' % nom)
        else:
            cs.creer(nom, m1, admin=a.admin)
            print('compte cree : %s%s' % (nom, '  (admin)' if cs.est_admin(nom) else ''))
            if len(cs.noms()) == 1:
                print('PREMIER compte : la porte du serveur se FERME des maintenant.')
    except ValueError as e:
        print('refus : %s' % e); return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
