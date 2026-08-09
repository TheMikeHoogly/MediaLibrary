#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Géocodage inverse OFFLINE — coordonnées GPS -> nom de lieu.
──────────────────────────────────────────────────────────────────────────────

Pourquoi offline (décision d'architecture). Les GPS d'un fonds FAMILIAL pointent
le domicile et les lieux de vie : les envoyer à une API cloud (TomTom, OSM…) est
un problème de vie privée ET casse l'autonomie du serveur (clé d'API, quota,
réseau au démarrage). On géocode donc contre un GAZETTEER LOCAL (GeoNames
`cities1000`), en pur stdlib : aucune dépendance lourde, aucun réseau, résultat
déterministe et reproductible. Fidèle aux invariants du projet (« zéro dépendance
au démarrage », « la donnée vit en local »).

Ce module est PUR (aucun accès à photos.db, aucun modèle) : il transforme des
coordonnées en libellés. Il est donc testable dans le bac à sable avec un petit
gazetteer synthétique (`test_geocode.py`). Le batch qui lit la base et écrit
`lieux.txt`/`gps_places.json` vit dans `enrichir_lieux.py` ; le serveur ne fait
qu'attacher le résultat précalculé (`gps_place`).

Coût. Les points d'un corpus se regroupent en une poignée de clusters (domicile +
spots + voyages). On CLUSTERISE d'abord, puis on ne géocode que les centroïdes
(~dizaines), pas les centaines de points bruts. Le plus-proche-voisin en Python
pur sur ~150 000 villes coûte alors quelques dizaines de recherches, < 1 s.

Format gazetteer attendu : GeoNames `cities1000.txt`, tab-séparé, colonnes
officielles (0 geonameid, 1 name, 2 asciiname, 4 lat, 5 lon, 8 country code,
10 admin1 code, 14 population). Téléchargé une fois par le `.bat` dédié.
"""

import math
import unicodedata
from pathlib import Path

# Rayon terrestre moyen (km). Suffisant : on cherche le plus proche, pas une
# distance géodésique au mètre près.
_R_TERRE_KM = 6371.0088

# Colonnes GeoNames utiles (indices dans la ligne tab-séparée).
_COL_NAME = 1
_COL_LAT = 4
_COL_LON = 5
_COL_CC = 8
_COL_ADMIN1 = 10
_COL_POP = 14


def sans_accents(s):
    """Minuscule sans diacritiques (parité avec server._sans_accents /
    renommage_facts._sans_accents : même clé de comparaison partout)."""
    s = unicodedata.normalize('NFD', str(s).lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance grand-cercle en km entre deux points (degrés décimaux)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * _R_TERRE_KM * math.asin(math.sqrt(a))


def _valide_latlon(lat, lon):
    """(lat, lon) plausibles ? Rejette None, NaN, hors bornes, et le point nul
    (0, 0) au large de l'Afrique — un GPS manquant encodé en zéro, pas un lieu."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None
    if math.isnan(lat) or math.isnan(lon):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    if abs(lat) < 1e-6 and abs(lon) < 1e-6:
        return None
    return (lat, lon)


class Place:
    """Une entrée du gazetteer. `label` porte les accents (affichage) ; `norm`
    est sa forme de comparaison ; `pop` sert à départager deux villes proches."""
    __slots__ = ('label', 'norm', 'lat', 'lon', 'cc', 'admin1', 'pop')

    def __init__(self, label, lat, lon, cc='', admin1='', pop=0):
        self.label = label
        self.norm = sans_accents(label)
        self.lat = lat
        self.lon = lon
        self.cc = cc
        self.admin1 = admin1
        self.pop = pop

    def __repr__(self):
        return f"Place({self.label!r}, {self.lat}, {self.lon}, cc={self.cc})"


def load_gazetteer(path, min_pop=0):
    """Charge un gazetteer GeoNames (`cities1000.txt` ou sous-ensemble) en liste
    de `Place`. Ignore les lignes malformées. `min_pop` filtre les hameaux si on
    veut privilégier les villes nommées. `path` : str | Path."""
    places = []
    p = Path(path)
    with p.open(encoding='utf-8') as f:
        for ligne in f:
            cols = ligne.rstrip('\n').split('\t')
            if len(cols) <= _COL_POP:
                continue
            ll = _valide_latlon(cols[_COL_LAT], cols[_COL_LON])
            if not ll:
                continue
            name = cols[_COL_NAME].strip()
            if not name:
                continue
            try:
                pop = int(cols[_COL_POP] or 0)
            except ValueError:
                pop = 0
            if pop < min_pop:
                continue
            places.append(Place(name, ll[0], ll[1],
                                cols[_COL_CC].strip(),
                                cols[_COL_ADMIN1].strip(), pop))
    return places


def nearest(lat, lon, places, max_km=None):
    """Le `Place` le plus proche de (lat, lon), ou None. Si `max_km` est fourni,
    on ne rend rien au-delà (un point en pleine mer n'a pas de ville proche).
    À distance quasi égale (< 0,5 km d'écart), on préfère la ville la plus
    peuplée — c'est le nom que l'humain emploie (« Lausanne » plutôt qu'un
    hameau collé)."""
    ll = _valide_latlon(lat, lon)
    if not ll or not places:
        return None
    lat, lon = ll
    best = None
    best_d = float('inf')
    for pl in places:
        d = haversine_km(lat, lon, pl.lat, pl.lon)
        if d < best_d - 0.5:
            best, best_d = pl, d
        elif d < best_d + 0.5 and best is not None and pl.pop > best.pop:
            # quasi-ex aequo : la plus peuplée gagne (best_d reste le min réel)
            best = pl
            best_d = min(best_d, d)
    if best is None:
        return None
    if max_km is not None and best_d > max_km:
        return None
    return best


def cluster_points(points, eps_km=2.0):
    """Regroupe des points (lat, lon) par proximité (agglomération gloutonne :
    un point rejoint le premier cluster dont le centroïde est à < eps_km, sinon
    il en ouvre un). Rend une liste de clusters, chacun :
        {'centroid': (lat, lon), 'members': [idx...], 'n': k}
    `members` porte les INDICES d'origine (pour rattacher les clés ensuite).

    Simplicité assumée : les clusters GPS d'un fonds photo sont nets et bien
    séparés (un domicile, quelques spots, des voyages) — pas besoin de HDBSCAN
    ici. eps_km ~2 km regroupe une ville sans fusionner deux villages voisins."""
    clusters = []
    for idx, pt in enumerate(points):
        ll = _valide_latlon(pt[0], pt[1])
        if not ll:
            continue
        lat, lon = ll
        cible = None
        cible_d = float('inf')
        for c in clusters:
            d = haversine_km(lat, lon, c['centroid'][0], c['centroid'][1])
            if d < eps_km and d < cible_d:
                cible, cible_d = c, d
        if cible is None:
            clusters.append({'centroid': (lat, lon),
                             '_sum': [lat, lon], 'members': [idx], 'n': 1})
        else:
            cible['members'].append(idx)
            cible['n'] += 1
            cible['_sum'][0] += lat
            cible['_sum'][1] += lon
            cible['centroid'] = (cible['_sum'][0] / cible['n'],
                                 cible['_sum'][1] / cible['n'])
    for c in clusters:
        c.pop('_sum', None)
    clusters.sort(key=lambda c: c['n'], reverse=True)
    return clusters


def label_place(place, avec_pays=False):
    """Libellé d'affichage d'un `Place`, dans le style de lieux.txt (accentué,
    un nom propre). `avec_pays` ajoute le code pays entre parenthèses pour lever
    une ambiguïté (« Trinidad (BO) ») — off par défaut : lieux.txt est mono-mot."""
    if place is None:
        return None
    if avec_pays and place.cc:
        return f"{place.label} ({place.cc})"
    return place.label


__all__ = [
    'sans_accents', 'haversine_km', 'Place', 'load_gazetteer',
    'nearest', 'cluster_points', 'label_place',
]
