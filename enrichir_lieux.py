#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrichissement des lieux par GÉOCODAGE INVERSE OFFLINE des photos géolocalisées.
──────────────────────────────────────────────────────────────────────────────

CE QUE FAIT CE SCRIPT (sur la machine de Mike, PAS le bac à sable).
    1. Lit `photos.db` en LECTURE SEULE (mode=ro) — sûr à côté du serveur, qui
       reste l'écrivain unique (WAL autorise les lecteurs concurrents).
    2. Collecte les entrées portant un GPS `[lat, lon]` (~684 sur le corpus).
    3. Les CLUSTERISE (domicile + spots + voyages : une poignée de groupes).
    4. Géocode chaque CENTROÏDE contre un gazetteer LOCAL (GeoNames cities1000)
       via `geocode.py` — offline, déterministe, aucune coordonnée envoyée dehors.
    5. Écrit deux sorties :
         - `gps_places.json` : {clé_photo -> libellé de lieu}. Le serveur l'attache
           comme `gps_place` dans les facts de renommage (câblage séparé).
         - des ajouts RÉVERSIBLES à `lieux.txt` (backup .bak, bloc marqué,
           supprimable), pour que la recherche par lieu et le renommage
           reconnaissent ces nouveaux lieux.

DRY-RUN PAR DÉFAUT : sans `--ecrire`, rien n'est modifié ; on n'imprime que le
plan. `--ecrire` applique (backup + écriture). Conforme aux garde-fous du projet
(réversible, l'humain tranche).

Le CŒUR est PUR et testable (`test_geocode.py` couvre geocode ; les fonctions
`construire_places` et `fusionner_lieux` ci-dessous sont pures). Seuls
`lire_gps_ro` (I/O sqlite) et `main` touchent le disque.

Usage (DANS le .venv, sur la machine de Mike — le gazetteer doit exister) :
    python enrichir_lieux.py                 # apercu (dry-run)
    python enrichir_lieux.py --ecrire        # applique
    python enrichir_lieux.py --gazetteer C:\\chemin\\cities1000.txt --eps 2.5
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import geocode

SCRIPT_DIR = Path(__file__).resolve().parent
DB_DEFAUT = SCRIPT_DIR / "photos.db"
GAZ_DEFAUT = SCRIPT_DIR / "cities1000.txt"
LIEUX_FICHIER = SCRIPT_DIR / "lieux.txt"
SORTIE_JSON = SCRIPT_DIR / "gps_places.json"

# Sentinelles du bloc géré dans lieux.txt (permettent une re-exécution
# idempotente : on retire l'ancien bloc avant d'en réécrire un neuf).
MARK_START = "# === Lieux ajoutes par geocodage inverse (enrichir_lieux.py) ==="
MARK_END = "# === Fin des ajouts par geocodage inverse ==="

# Au-delà de cette distance au centroïde, on ne nomme pas (point en mer, GPS
# aberrant) : mieux vaut pas de lieu qu'un lieu faux.
MAX_KM_DEFAUT = 25.0


# ─────────────────────────── I/O sqlite (lecture seule) ──────────────────────

def lire_gps_ro(db_path, table="tags"):
    """Lit (clé, [lat, lon]) des entrées géolocalisées, en LECTURE SEULE.

    N'ouvre JAMAIS la base en écriture : URI `mode=ro`. Le serveur peut tourner.
    Rend une liste de (clé, lat, lon), coordonnées déjà validées par geocode."""
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    cx = sqlite3.connect(uri, uri=True, timeout=30.0)
    try:
        cur = cx.execute(f'SELECT k, v FROM "{table}"')
        out = []
        for k, v in cur:
            try:
                e = json.loads(v)
            except (ValueError, TypeError):
                continue
            g = e.get('gps') if isinstance(e, dict) else None
            if not g or len(g) < 2:
                continue
            ll = geocode._valide_latlon(g[0], g[1])
            if ll:
                out.append((k, ll[0], ll[1]))
        return out
    finally:
        cx.close()


# ─────────────────────────── cœur pur (testable) ─────────────────────────────

def construire_places(gps_list, gaz, eps_km=2.0, max_km=MAX_KM_DEFAUT):
    """(places_par_cle, clusters_info) — PUR.

    `gps_list` : liste de (clé, lat, lon). `gaz` : liste de geocode.Place.
    - places_par_cle : {clé -> libellé} pour toute photo dont le cluster a été
      nommé (les clusters non nommés — trop loin de toute ville — sont omis).
    - clusters_info : un résumé par cluster (centroïde, effectif, libellé, km),
      trié du plus gros au plus petit, pour le rapport lisible.
    """
    points = [(lat, lon) for (_k, lat, lon) in gps_list]
    clusters = geocode.cluster_points(points, eps_km=eps_km)
    places_par_cle = {}
    infos = []
    for c in clusters:
        lat, lon = c['centroid']
        pl = geocode.nearest(lat, lon, gaz, max_km=max_km)
        label = geocode.label_place(pl)
        dist = (geocode.haversine_km(lat, lon, pl.lat, pl.lon)
                if pl is not None else None)
        infos.append({
            'centroid': [round(lat, 5), round(lon, 5)],
            'effectif': c['n'],
            'lieu': label,
            'km': round(dist, 2) if dist is not None else None,
            'pays': pl.cc if pl is not None else None,
        })
        if label:
            for idx in c['members']:
                cle = gps_list[idx][0]
                places_par_cle[cle] = label
    return places_par_cle, infos


def fusionner_lieux(lignes_existantes, nouveaux_labels):
    """Insère `nouveaux_labels` dans les lignes de lieux.txt — PUR et idempotent.

    - retire un éventuel bloc géré d'une exécution précédente (entre sentinelles) ;
    - ne ré-ajoute que les libellés PAS déjà présents (comparaison sans accents,
      inclut les lignes actives ET le bloc géré retiré) ;
    - insère le bloc marqué AVANT la section « Rejetes » si elle existe, sinon en
      fin de fichier. Rend (nouvelles_lignes, labels_reellement_ajoutes).
    """
    # 1) retirer l'ancien bloc géré (+ la ligne vide de séparation qui le suit,
    #    sinon un blanc s'accumulerait à chaque exécution — non idempotent).
    nettoyees = []
    dans_bloc = False
    manger_vide = False
    for l in lignes_existantes:
        s = l.strip()
        if s == MARK_START:
            dans_bloc = True
            continue
        if s == MARK_END:
            dans_bloc = False
            manger_vide = True
            continue
        if dans_bloc:
            continue
        if manger_vide:
            manger_vide = False
            if s == '':
                continue
        nettoyees.append(l)

    # 2) libellés actifs déjà présents (lignes non commentées)
    presents = set()
    for l in nettoyees:
        s = l.split('#')[0].strip()
        if s:
            presents.add(geocode.sans_accents(s))

    ajouts = []
    vus = set(presents)
    for lab in nouveaux_labels:
        n = geocode.sans_accents(lab)
        if n and n not in vus:
            vus.add(n)
            ajouts.append(lab)
    ajouts.sort(key=geocode.sans_accents)

    if not ajouts:
        return nettoyees, []

    bloc = [MARK_START] + ajouts + [MARK_END]

    # 3) insérer avant la section « Rejetes » si repérable
    idx_insert = None
    for i, l in enumerate(nettoyees):
        if l.strip().startswith('# --- Rejetes'):
            idx_insert = i
            break
    if idx_insert is None:
        # avant d'éventuelles lignes vides de fin
        fin = len(nettoyees)
        while fin > 0 and nettoyees[fin - 1].strip() == '':
            fin -= 1
        nouvelles = nettoyees[:fin] + bloc + nettoyees[fin:]
    else:
        nouvelles = nettoyees[:idx_insert] + bloc + [''] + nettoyees[idx_insert:]
    return nouvelles, ajouts


# ─────────────────────────── programme ───────────────────────────────────────

def _rapport(infos, n_photos, n_places):
    nommes = [i for i in infos if i['lieu']]
    non = [i for i in infos if not i['lieu']]
    print(f"=== Geocodage inverse : {n_photos} photos GPS, {len(infos)} clusters "
          f"-> {n_places} photos nommees ===\n")
    print("Clusters nommes (du plus gros au plus petit) :")
    for i in nommes:
        print(f"  {i['effectif']:>4}  {i['lieu']:<24} "
              f"({i['km']} km, {i['pays']})  @ {i['centroid']}")
    if non:
        print(f"\nClusters NON nommes (aucune ville sous {int(MAX_KM_DEFAUT)} km) :")
        for i in non:
            print(f"  {i['effectif']:>4}  ?  @ {i['centroid']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Géocodage inverse offline des photos GPS.")
    ap.add_argument('--db', default=str(DB_DEFAUT))
    ap.add_argument('--gazetteer', default=str(GAZ_DEFAUT))
    ap.add_argument('--eps', type=float, default=2.0, help="rayon de cluster (km)")
    ap.add_argument('--max-km', type=float, default=MAX_KM_DEFAUT,
                    help="distance max au centroïde pour nommer")
    ap.add_argument('--ecrire', action='store_true',
                    help="applique (backup + ecriture) ; sinon dry-run")
    args = ap.parse_args(argv)

    db = Path(args.db)
    gaz_path = Path(args.gazetteer)
    if not db.exists():
        print(f"Base introuvable : {db}")
        return 2
    if not gaz_path.exists():
        print(f"Gazetteer introuvable : {gaz_path}\n"
              f"Lance d'abord le .bat de telechargement du gazetteer "
              f"(GeoNames cities1000), une seule fois.")
        return 2

    print(f"Lecture GPS (ro) depuis {db.name} ...")
    gps_list = lire_gps_ro(db)
    print(f"  {len(gps_list)} photos geolocalisees.")
    if not gps_list:
        print("Aucune coordonnee GPS : rien a faire.")
        return 0

    print(f"Chargement du gazetteer {gaz_path.name} ...")
    gaz = geocode.load_gazetteer(gaz_path)
    print(f"  {len(gaz)} lieux charges.")

    places_par_cle, infos = construire_places(
        gps_list, gaz, eps_km=args.eps, max_km=args.max_km)
    _rapport(infos, len(gps_list), len(places_par_cle))

    labels = sorted({v for v in places_par_cle.values()}, key=geocode.sans_accents)
    lignes = LIEUX_FICHIER.read_text(encoding='utf-8').splitlines() \
        if LIEUX_FICHIER.exists() else []
    _nouvelles, ajouts = fusionner_lieux(lignes, labels)
    print(f"\nLieux deja curates (hors bloc geocodage) : {len(labels) - len(ajouts)} ; "
          f"geres dans le bloc geocodage de lieux.txt : {len(ajouts)}")
    if ajouts:
        print("  + " + ", ".join(ajouts))

    if not args.ecrire:
        print("\n(dry-run — rien ecrit. Relance avec --ecrire pour appliquer.)")
        return 0

    # gps_places.json
    tmp = SORTIE_JSON.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(places_par_cle, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    tmp.replace(SORTIE_JSON)
    print(f"\nEcrit {SORTIE_JSON.name} ({len(places_par_cle)} entrees).")

    # lieux.txt (backup + reecriture) si ajouts
    if ajouts:
        bak = LIEUX_FICHIER.with_suffix('.txt.bak')
        bak.write_text("\n".join(lignes) + "\n", encoding='utf-8')
        LIEUX_FICHIER.write_text("\n".join(_nouvelles) + "\n", encoding='utf-8')
        print(f"Ecrit {LIEUX_FICHIER.name} (+{len(ajouts)} lieux). "
              f"Backup : {bak.name}")
    else:
        print("lieux.txt inchange (aucun nouveau lieu).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
