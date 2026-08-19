#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Générateur de plan de RENOMMAGE — logique PURE, lecture seule.

Miroir de `rangement_annee.py` : aucune I/O, aucun modèle, ne mute rien. À
partir d'entrées (clé d'index, entry), propose un nouveau NOM DE BASE canonique
via le cœur déjà testé `renommage.py`, POUR LES SEULS NOMS BRUTS (Screenshot_,
VideoCapture_, IMG_, WhatsApp, Scan_, hash de contenu…). Les fichiers déjà
datés/nommés proprement (ex. `20190704_123045.jpg`) sont laissés tels quels —
choix de Mike (03/08) : « noms bruts seulement ».

UNE SEULE exception à « noms bruts seulement », ajoutée le 19/08 : les noms que
le PLAN a lui-même produits avec la seule année du dossier (« YYYY0000_… »,
`est_nom_annee_seule`). Ils ne sont plus bruts, donc plus jamais relus — alors
qu'une tâche de fond EXIF peut avoir livré la date PRÉCISE depuis (mesure du
17/08 : 15 fichiers). On ne les reprend QUE si la date est devenue précise ;
sinon on n'y touche pas, et on le compte (`stats['perimes_en_attente']`).

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
# Signature du plan LUI-MEME quand il n'avait que l'annee du dossier : mois et
# jour a « 00 ». Aucun appareil ne produit un 00e mois — c'est notre ecriture.
_ANNEE_SEULE = re.compile(r'^(19|20)\d{2}0000[_.]')      # « 20060000_Mike.jpg »


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


def est_nom_annee_seule(name):
    """True si `name` porte la signature « YYYY0000_ » que le PLAN a lui-meme
    ecrite faute de mois et de jour (`resolve_datestamp` etape 3).

    Ces noms ne sont plus « bruts » : `est_nom_brut` les refuse, et le plan ne
    revient donc jamais dessus. Or une tache de fond EXIF peut avoir livre la
    date PRECISE apres le renommage — mesure du 17/08, retrouvee le 19/08 :
    **15 fichiers** portent « YYYY0000 » alors que leur `taken` est aujourd'hui
    connu et COHERENT avec le dossier. Le nom est perime, et rien ne l'aurait
    rattrape.

    Limite ASSUMEE, et comptee plutot que documentee (methode du 17/08 : « une
    limite ecrite n'est pas une limite geree ») : un fichier d'origine qui
    commencerait par hasard par « YYYY0000_ » serait repris lui aussi. Aucun
    appareil ne datant du 00e mois, le cas est theorique ; s'il existe, il
    apparait dans `stats['perimes_repris']`."""
    stem = name.rsplit('.', 1)[0] if '.' in name else name
    return bool(_ANNEE_SEULE.match(stem + '.'))


def _split(key):
    """(dossier POSIX, nom de fichier) d'une clé d'index (chemin Windows ou
    relatif). Les clés Uploads plates n'ont pas de dossier → ('', nom)."""
    k = str(key).replace('\\', '/')
    if '/' in k:
        d, n = k.rsplit('/', 1)
        return d, n
    return '', k


def _suffixe_numerique(base, taken):
    """Rend `base` unique dans `taken` par un compteur LISIBLE (« -2 », « -3 »…)
    inséré avant l'extension. Plus joli qu'un hash : `20060000_Mike-et-Zab.jpg`
    puis `20060000_Mike-et-Zab-2.jpg`. `base` inchangé s'il est déjà libre."""
    if base not in taken:
        return base
    if '.' in base:
        stem, ext = base.rsplit('.', 1)
        ext = '.' + ext
    else:
        stem, ext = base, ''
    n = 2
    while f"{stem}-{n}{ext}" in taken:
        n += 1
    return f"{stem}-{n}{ext}"


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
    n_perimes_repris = n_perimes_attente = 0
    for _dossier, items in par_dossier.items():
        n_total += len(items)
        # Ordre DETERMINISTE (par nom d'origine) : la collision donne un compteur
        # stable, et le fichier « le plus ancien par nom » garde le nom propre.
        items.sort(key=lambda it: it[1].lower())
        # 1) réserver les noms des fichiers qu'on NE renomme PAS (non bruts),
        #    pour ne jamais entrer en collision avec eux. Les noms « YYYY0000_ »
        #    y restent RESERVES même quand on les reprend : leur nouveau nom
        #    diffère forcément, et libérer l'ancien dans la même passe ferait
        #    dépendre le résultat de l'ordre d'application.
        taken = set(n for _k, n, _e in items if not est_nom_brut(n))
        n_laisses += len(taken)
        # 2) proposer un nom pour chaque nom brut, en évitant les collisions.
        for key, old, entry in items:
            brut = est_nom_brut(old)
            perime_possible = (not brut) and est_nom_annee_seule(old)
            if not brut and not perime_possible:
                continue
            facts = rf.resolve_facts(key, entry, lieux=lieux,
                                     gps_place=gps_places.get(key),
                                     image_type=image_types.get(key))
            if perime_possible:
                # On ne revient sur un nom DÉJÀ produit par le plan que si la
                # date a gagné en précision depuis. Sinon `propose_basename`
                # rendrait le même champ date mais un compteur de collision
                # potentiellement différent (« -2 » → « -3 ») : du mouvement pour
                # rien, sur des fichiers déjà rangés. Le silence est ici le bon
                # comportement, mais il se COMPTE (`perimes_en_attente`).
                if facts.get('_date_precision') != 'exact':
                    n_perimes_attente += 1
                    continue
            # Sans AUCUNE date fiable, le nom deviendrait « 00000000_… » : pire
            # que le nom brut. On ne renomme pas ces fichiers (choix Mike, 03/08) ;
            # on garde leur nom d'origine (réservé pour ne pas être écrasé).
            if str(facts.get('date8') or '').startswith('00000000'):
                taken.add(old)
                n_sans_date += 1
                continue
            # base SANS suffixe hex (on ne passe pas `taken` a propose_basename),
            # puis compteur lisible « -2/-3 » si collision dans le dossier.
            new = _suffixe_numerique(renommage.propose_basename(facts), taken)
            if new == old:
                taken.add(old)
                n_inchanges += 1
                continue
            taken.add(new)
            if perime_possible:
                n_perimes_repris += 1
            moves.append({'key': key, 'dossier': _dossier,
                          'old_name': old, 'new_name': new,
                          'motif': 'perime' if perime_possible else 'brut'})

    stats = {'a_renommer': len(moves), 'laisses_tels_quels': n_laisses,
             'inchanges': n_inchanges, 'sans_date_ignores': n_sans_date,
             'perimes_repris': n_perimes_repris,
             'perimes_en_attente': n_perimes_attente,
             'total': n_total}
    return moves, stats


__all__ = ['est_nom_brut', 'est_nom_annee_seule', 'construire_plan']
