#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les journaux d'annulation, relus comme une carte des déplacements
──────────────────────────────────────────────────────────────────────────────

À QUOI ÇA SERT

Chaque rangement par année, chaque dédoublonnage et chacun des 7 058 renommages
appliqués a écrit son journal d'annulation dans `docs/`. Ces fichiers existaient
pour DÉFAIRE. Relus dans l'autre sens, ils disent où chaque photo est allée —
et c'est la preuve la plus forte qu'on puisse avoir : pas une ressemblance de
nom, pas une similarité de vecteur, mais le geste lui-même, écrit par le
programme qui l'a fait.

Le 22/08, c'est ce qui a permis de retrouver **698** des **804** clés sur
lesquelles une décision humaine était restée orpheline — là où le nom de
fichier seul n'en retrouvait que 346, et le vecteur 13 (la purge du 21/08 ayant
emporté les détections des clés mortes).

TROIS FORMES, UN SEUL SENS DE LECTURE

  * `undo_annee_*`, `undo_rangement_*` : un dict avec `operations`.
    - déplacement : `old_key` → `new_key` ;
    - doublon absorbé : `canonique` — le doublon part en corbeille et c'est le
      fichier canonique qui le remplace, donc `src`, `dst` et `old_key` y mènent
      tous les trois.
  * `undo_renommage_*` : une LISTE d'opérations `old_key`/`new_key`.
  * `undo_reclassement_*` : ne déplace AUCUN fichier (personne ↔ animal).
    Ignoré — et c'est un choix, pas un oubli.

CE QU'ON N'EST PAS ALLÉ CHERCHER

Un journal `.annule.json` a déjà été rejoué À L'ENVERS : le suivre remettrait
une décision sur une clé qui n'existe plus. Ignoré aussi.

Module PUR : ni store, ni base, ni verrou. Partagé par le serveur et les bancs,
pour qu'il n'y ait qu'une seule lecture des journaux dans le projet.
"""

import json
from pathlib import Path

# Un journal rejoué pourrait boucler. Une boucle silencieuse serait pire qu'un
# abandon : on borne, et on rend None.
SAUTS_MAX = 10


def chaines(docs):
    """{ancienne clé: nouvelle clé} lu dans tous les journaux de `docs`."""
    chaine = {}
    try:
        fichiers = sorted(Path(docs).glob('undo_*.json'))
    except OSError:
        return chaine
    for f in fichiers:
        if f.name.endswith('.annule.json') or 'reclassement' in f.name:
            continue
        try:
            j = json.loads(f.read_text(encoding='utf-8'))
        except Exception:                                      # noqa: BLE001
            continue
        ops = j.get('operations') if isinstance(j, dict) else j
        for op in (ops or []):
            if not isinstance(op, dict):
                continue
            canon = op.get('canonique')
            if canon:
                for depart in (op.get('src'), op.get('dst'), op.get('old_key')):
                    if depart and depart != canon:
                        chaine.setdefault(depart, canon)
                continue
            a, b = op.get('old_key'), op.get('new_key')
            if a and b and a != b:
                chaine.setdefault(a, b)
    return chaine


def suivre(chaine, cle, vivantes, sauts=SAUTS_MAX):
    """La clé VIVANTE au bout de la chaîne des déplacements, ou None.

    Une photo a pu être déplacée PUIS renommée : on suit, sans jamais repasser
    par une clé déjà vue."""
    vu, cur = {cle}, cle
    for _ in range(sauts):
        suivant = chaine.get(cur)
        if not suivant or suivant in vu:
            return None
        if suivant in vivantes:
            return suivant
        vu.add(suivant)
        cur = suivant
    return None
