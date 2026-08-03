#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Générateur de plan de RENOMMAGE — logique PURE, lecture seule.

Miroir de `rangement_annee.py` : aucune I/O, aucun modèle, ne mute rien. À
partir d'entrées (clé d'index, entry), propose un nouveau NOM DE BASE canonique
via le cœur déjà testé `renommage.py`, POUR LES SEULS NOMS BRUTS (Screenshot_,
VideoCapture_, IMG_, WhatsApp, Scan_, hash de contenu…). Les fichiers déjà
datés/nommés proprement (ex. `20190704_123045.jpg`) sont laissés tels quels —
choix de Mike (03/08) : « noms bruts seulement ».

Le renommage se fait EN PLACE (même dossier), donc les collisions sont résolues
DANS le dossier d'origine : on réserve d'abord les noms des fichiers qu'on ne
renomme pas, puis `propose_basename(..., taken=…)` ajoute un suffixe si besoin.

Le serveur appellera `construire_plan(...)` puis écrira
`docs/plan_renommage.{json,md}` ; l'APPLICATION (mutante, in-process, re-clé via
`rekey_everywhere`, réversible) est un étage séparé — exactement comme pour le
rangement par année (`appliquer_plan_annee.py`).
"""
import re

import renommage
import renommage_facts as rf

# ── Détection des noms « bruts » (peu informatifs), insensible à la casse ──────
# Préfixes/motifs d'exports automatiques que l'on veut canoniser. Extensible.
_BRUTS = re.compile(
    r'^(?:'
    r'screenshot|screen[ _-]?shot|capture|'      # captures d'écran
    r'videocapture|vid[_-]|'                       # captures vidéo
    r'img[_-]|'                                    # exports appareil « IMG_… »
    r'scan[_ ]|numeris|'                           # scans
    r'photo0\d|'                                   # vieux téléphones « Photo0001 »
    r'image-|hqdefault|received_|inshot|collage'   # divers (web, retouche, partage)
    r')', re.IGNORECASE)
_WHATSAPP = re.compile(r'-WA\d{3,}', re.IGNORECASE)      # « IMG-20190704-WA0001 »
_HASHNAME = re.compile(r'^[0-9a-f]{16,}$', re.IGNORECASE)  # nom = hash de contenu
_DATE_CLEAN = re.compile(r'^\d{8}[_-]\d{6}')             # « 20190704_123045 » déjà propre


def est_nom_brut(name):
    """True si `name` (nom de fichier, extension comprise) est un nom BRUT à
    canoniser. False pour un nom déjà daté/propre — on n'y touche pas.

    Priorité : un nom déjà « YYYYMMDD_HHMMSS… » est propre même s'il contient
    par ailleurs un motif brut ; un nom = hash de contenu ou marqué WhatsApp est
    brut ; sinon on teste les préfixes d'exports automatiques."""
    stem = name.rsplit('.', 1)[0] if '.' in name else name
    if _DATE_CLEAN.match(stem):
        return False
    if _HASHNAME.match(stem):
        return True
    if _WHATSAPP.search(name):
        return True
    return bool(_BRUTS.match(stem))


def _split(key):
    """(dossier POSIX, nom de fichier) d'une clé d'index (chemin Windows ou
    relatif). Les clés Uploads plates n'ont pas de dossier → ('', nom)."""
    k = str(key).replace('\\', '/')
    if '/' in k:
        d, n = k.rsplit('/', 1)
        return d, n
    return '', k


def construire_plan(entries, lieux=None, gps_places=None, image_types=None):
    """Construit le plan de renommage.

    entries : itérable de (key, entry). Renvoie `(moves, stats)` où chaque move
    est `{key, dossier, old_name, new_name}`. SEULS les noms bruts sont proposés.
    Ne renomme jamais vers un nom déjà pris dans le dossier (collision résolue
    par suffixe déterministe), ni vers le nom actuel (aucun move nul).

    `gps_places` / `image_types` : dicts optionnels clé→valeur, fournis par le
    serveur quand il a le géocodage inverse / le type SigLIP (sinon le segment
    lieu/type est simplement omis du nom)."""
    gps_places = gps_places or {}
    image_types = image_types or {}

    par_dossier = {}
    for key, entry in entries:
        d, n = _split(key)
        par_dossier.setdefault(d, []).append((key, n, entry))

    moves = []
    n_laisses = n_inchanges = n_total = n_sans_date = 0
    for _dossier, items in par_dossier.items():
        n_total += len(items)
        # 1) réserver les noms des fichiers qu'on NE renomme PAS (non bruts),
        #    pour ne jamais entrer en collision avec eux.
        taken = set(n for _k, n, _e in items if not est_nom_brut(n))
        n_laisses += len(taken)
        # 2) proposer un nom pour chaque nom brut, en évitant les collisions.
        for key, old, entry in items:
            if not est_nom_brut(old):
                continue
            facts = rf.resolve_facts(key, entry, lieux=lieux,
                                     gps_place=gps_places.get(key),
                                     image_type=image_types.get(key))
            # Sans AUCUNE date fiable, le nom deviendrait « 00000000_… » : pire
            # que le nom brut. On ne renomme pas ces fichiers (choix Mike, 03/08) ;
            # on garde leur nom d'origine (réservé pour ne pas être écrasé).
            if str(facts.get('date8') or '').startswith('00000000'):
                taken.add(old)
                n_sans_date += 1
                continue
            new = renommage.propose_basename(facts, taken=taken)
            if new == old:
                taken.add(old)
                n_inchanges += 1
                continue
            taken.add(new)
            moves.append({'key': key, 'dossier': _dossier,
                          'old_name': old, 'new_name': new})

    stats = {'a_renommer': len(moves), 'laisses_tels_quels': n_laisses,
             'inchanges': n_inchanges, 'sans_date_ignores': n_sans_date,
             'total': n_total}
    return moves, stats


__all__ = ['est_nom_brut', 'construire_plan']
