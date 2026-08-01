#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration de l'ETAT du projet vers un nouveau PC — export / import.

Le CODE se migre par `git clone` (depot GitHub). Ce script s'occupe de ce que git
NE versionne PAS mais qu'il faut absolument emporter : la base d'index locale et
la configuration locale (chemins NAS, jeton HF, vocabulaires, lieux).

  A EMPORTER (etat) :
    - photos.db (+ -wal, -shm)  : l'index — tags, embeddings, clusters, noms.
      Les noms humains vivent AUSSI dans les XMP des fichiers (sur le NAS), mais
      la base porte les EMPREINTES et les regroupements : on la migre pour ne pas
      tout recalculer (des heures de CPU).
    - configs .txt : modele, data_dir, dossier_uploads, dossiers_a_taguer,
      dossiers_a_explorer, especes_nommables, vocabulaire_tags, lieux,
      hf_token, hf_cache (celles qui existent).

  PAS emporte (regenerable) : .venv (recree par installer.py), les caches
  d'images (face_thumbs/, animal_thumbs/ — option --avec-caches si tu y tiens),
  les modeles (retelecharges au 1er lancement), les rapports.

IMPORTANT : exporter SERVEUR ARRETE, pour une base coherente (le -wal peut
contenir des ecritures non encore fusionnees ; les trois fichiers ensemble
suffisent a SQLite pour se remettre d'aplomb, mais autant ne pas ecrire pendant
la copie).

Usage :
    python migrer.py exporter [--vers DOSSIER] [--avec-caches]
    python migrer.py importer <archive.zip> [--force]
"""

import argparse
import socket
import sys
import time
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent

ETAT = [
    'photos.db', 'photos.db-wal', 'photos.db-shm',
    'modele.txt', 'data_dir.txt', 'dossier_uploads.txt',
    'dossiers_a_taguer.txt', 'dossiers_a_explorer.txt',
    'especes_nommables.txt', 'vocabulaire_tags.txt', 'lieux.txt',
    'hf_token.txt', 'hf_cache.txt',
]
CACHES = ['face_thumbs', 'animal_thumbs']


def fichiers_etat(base):
    return [f for f in ETAT if (base / f).exists()]


def exporter(base, vers, avec_caches=False):
    base, vers = Path(base), Path(vers)
    vers.mkdir(parents=True, exist_ok=True)
    nom = f"migration_{socket.gethostname()}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    zp = vers / nom
    fichiers = fichiers_etat(base)
    total = 0
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in fichiers:
            z.write(base / f, f)
            total += (base / f).stat().st_size
        if avec_caches:
            for c in CACHES:
                d = base / c
                if d.is_dir():
                    for p in d.rglob('*'):
                        if p.is_file():
                            z.write(p, str(p.relative_to(base)))
                            total += p.stat().st_size
    print("Etat exporte :")
    for f in fichiers:
        print(f"  + {f}  ({(base / f).stat().st_size / 1e6:.1f} Mo)")
    if avec_caches:
        print("  + caches face_thumbs/ + animal_thumbs/")
    print(f"\nArchive : {zp}  ({zp.stat().st_size / 1e6:.1f} Mo compresse)")
    print("A copier sur le nouveau PC, puis : python migrer.py importer "
          f"{zp.name}")
    return zp


def importer(base, zip_path, force=False):
    base, zip_path = Path(base), Path(zip_path)
    if not zip_path.exists():
        print(f"Archive introuvable : {zip_path}")
        return 2
    with zipfile.ZipFile(zip_path) as z:
        noms = [n for n in z.namelist() if not n.endswith('/')]
        conflits = [n for n in noms if (base / n).exists()]
        if conflits and not force:
            print("Des fichiers existent DEJA sur cette installation :")
            for n in conflits:
                print(f"  ! {n}")
            print("\nPour un nouveau PC vierge, il ne devrait pas y en avoir. Si "
                  "tu veux VRAIMENT ecraser l'etat local par celui de l'archive, "
                  "relance avec --force. (Sauvegarde d'abord si un doute.)")
            return 1
        z.extractall(base)
    print(f"Etat restaure depuis {zip_path.name} :")
    for n in noms:
        print(f"  + {n}")
    print("\nTermine. Verifie l'installation : python installer.py --check, "
          "puis demarre le serveur.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    pe = sub.add_parser('exporter')
    pe.add_argument('--vers', default=str(RACINE / 'migration'))
    pe.add_argument('--avec-caches', action='store_true')
    pi = sub.add_parser('importer')
    pi.add_argument('archive')
    pi.add_argument('--force', action='store_true')
    args = ap.parse_args()

    if args.cmd == 'exporter':
        if 'photos.db' not in fichiers_etat(RACINE):
            print("Attention : photos.db introuvable ici — est-ce le bon dossier ?")
        exporter(RACINE, args.vers, args.avec_caches)
        return 0
    return importer(RACINE, args.archive, args.force)


if __name__ == '__main__':
    sys.exit(main())
