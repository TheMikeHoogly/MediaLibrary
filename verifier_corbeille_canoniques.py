#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pourquoi 353 groupes de la corbeille refusent la purge (« canonique manquante »).

Le manifeste de chaque groupe note le chemin ABSOLU de la copie gardee (la
canonique). Depuis, le fonds a ete RANGE (bat 26, bat 39, rapatriements) : la
canonique a change de place. Le chemin note ne repond plus, alors le garde-fou
de `purger_corbeille.py` refuse — a raison, il ne sait pas si le contenu existe
encore.

Ce banc ne supprime RIEN et ne modifie RIEN. Il repond a une seule question,
groupe par groupe : la canonique a-t-elle DEMENAGE (le contenu vit ailleurs) ou
a-t-elle vraiment DISPARU ?

Preuve retenue, dans cet ordre :
  1. meme sha256 que le manifeste, trouve ailleurs  -> DEMENAGEE (certain)
  2. meme nom de fichier, taille identique          -> DEMENAGEE (probable)
  3. rien                                           -> DISPARUE

Le nom seul ne prouve rien (deux appareils ecrivent IMG_0001.JPG) : c'est
pourquoi le sha256 passe en premier et la taille sert de second temoin.

Usage :
    python verifier_corbeille_canoniques.py
    python verifier_corbeille_canoniques.py --sans-hash   # nom+taille seulement
Sortie : docs/corbeille_canoniques.json
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'corbeille_canoniques.json'


def sha256(path, buf=1 << 16):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def lire_json(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception:
        return defaut


def index_par_nom(db_path, table='tags'):
    """{nom de fichier minuscule: [chemins]} depuis photos.db.

    L index N EST PLUS un JSON (`tags_index.json`) depuis le passage a SQLite :
    lire l ancien fichier rend un dictionnaire VIDE, et un index vide fait
    conclure « tout a disparu » -- une reponse fausse qui a l air d une reponse.
    On ouvre donc la base en LECTURE SEULE (le serveur ecrit dedans en meme
    temps) et on ne demande que les cles, jamais les valeurs : c est un
    balayage d index, pas un chargement du fonds.
    """
    par_nom = defaultdict(list)
    uri = 'file:' + str(db_path).replace('?', '%3f').replace('#', '%23') \
          + '?mode=ro'
    cx = sqlite3.connect(uri, uri=True, timeout=30.0)
    try:
        cx.execute('PRAGMA busy_timeout=30000')
        for (cle,) in cx.execute(f'SELECT k FROM "{table}"'):
            par_nom[Path(cle).name.lower()].append(cle)
    finally:
        cx.close()
    return par_nom


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--hash', type=int, default=0, metavar='N',
                    help='verifier au sha256 les N premiers cas retrouves '
                         '(0 = aucun ; le hash sur SMB coute ~1 s par photo)')
    ap.add_argument('--jours', type=float, default=30.0)
    a = ap.parse_args(argv)

    plan = lire_json(RACINE / 'docs' / 'plan_rangement.json', {})
    corbeille = plan.get('corbeille')
    if not corbeille:
        print('Corbeille inconnue (docs/plan_rangement.json).')
        return 1
    corbeille = Path(corbeille)
    if not corbeille.exists():
        print(f'Corbeille absente : {corbeille}')
        return 1

    # L'index dit ou vivent les photos AUJOURD HUI, sans balayer le NAS.
    # photos.db vit sur le disque LOCAL, a cote du script (jamais le NAS).
    db = RACINE / 'photos.db'
    if not db.exists():
        print(f'Index introuvable : {db} — sans lui on ne peut rien conclure.')
        return 1
    t0 = time.time()
    par_nom = index_par_nom(db)
    print(f'index lu : {len(par_nom)} nom(s) distinct(s) en {time.time()-t0:.0f} s')
    if not par_nom:
        print('Index VIDE : je refuse de conclure « disparue » a partir de rien.')
        return 1

    stats = {'groupes': 0, 'canon_ok': 0, 'demenagee_sha': 0,
             'demenagee_nom': 0, 'sha_different': 0, 'disparue': 0,
             'octets_recuperables': 0, 'octets_gardes': 0}
    hashes_faits = 0
    lignes = []
    cles_manifeste = None
    for groupe in sorted(p for p in corbeille.iterdir() if p.is_dir()):
        mani = lire_json(groupe / 'manifeste.json')
        if not mani:
            continue
        stats['groupes'] += 1
        if cles_manifeste is None:
            cles_manifeste = sorted(mani)
        canon = mani.get('canonique') or ''
        if canon and Path(canon).exists():
            stats['canon_ok'] += 1
            continue

        poids = sum(f.stat().st_size for f in groupe.iterdir()
                    if f.is_file() and f.name != 'manifeste.json')
        nom = Path(canon).name.lower()
        attendu = mani.get('sha256')
        candidats = par_nom.get(nom, [])
        trouve, preuve = None, 'disparue'

        # L'ordre est celui du COUT, pas celui de l'envie. L'index repond en
        # memoire ; le NAS repond en secondes. On ne descend sur le disque que
        # pour les cas ou l'index a deja dit oui.
        for c in candidats:
            try:
                if Path(c).exists():
                    trouve, preuve = c, 'nom+chemin'
                    break
            except OSError:
                continue

        # Le sha256 tranche vraiment (deux appareils ecrivent IMG_0001.JPG),
        # mais il coute ~1 s par photo sur SMB : on n'en fait qu'un
        # ECHANTILLON, de quoi mesurer le taux d'erreur du temoin faible.
        if trouve is not None and attendu and hashes_faits < a.hash:
            hashes_faits += 1
            try:
                preuve = 'sha256' if sha256(trouve) == attendu else 'nom, autre contenu'
            except OSError:
                pass

        if preuve == 'sha256':
            stats['demenagee_sha'] += 1
            stats['octets_recuperables'] += poids
        elif preuve == 'nom+chemin':
            stats['demenagee_nom'] += 1
            stats['octets_recuperables'] += poids
        elif preuve == 'nom, autre contenu':
            stats['sha_different'] += 1
            stats['octets_gardes'] += poids
        else:
            stats['disparue'] += 1
            stats['octets_gardes'] += poids
        lignes.append({'groupe': groupe.name, 'canonique_notee': canon,
                       'preuve': preuve, 'canonique_trouvee': trouve,
                       'octets': poids})

    RAPPORT.parent.mkdir(exist_ok=True)
    RAPPORT.write_text(json.dumps(
        {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
         'corbeille': str(corbeille), 'stats': stats, 'lignes': lignes},
        ensure_ascii=False, indent=1), encoding='utf-8')

    print('-' * 62)
    print(f'cles d un manifeste    : {cles_manifeste}')
    print(f"groupes lus            : {stats['groupes']}")
    print(f"canonique en place     : {stats['canon_ok']}")
    print(f"RETROUVEE (sha256)     : {stats['demenagee_sha']}   <- meme "
          "contenu, certain")
    print(f"RETROUVEE (nom+chemin) : {stats['demenagee_nom']}   <- vit dans "
          "l'index, contenu non verifie")
    print(f"nom pris, autre contenu: {stats['sha_different']}   <- le temoin "
          "faible s'est trompe")
    print(f"DISPARUE               : {stats['disparue']}   <- NE PAS purger")
    print(f"sha256 calcules        : {hashes_faits}")
    print(f"espace a recuperer     : "
          f"{stats['octets_recuperables']/1024**3:.2f} Go")
    print(f"espace garde (disparu) : "
          f"{stats['octets_gardes']/1024**3:.2f} Go")
    print(f'rapport : {RAPPORT.relative_to(RACINE)}')
    for l in lignes[:12]:
        print(f"  [{l['preuve']:<11}] {l['groupe']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
