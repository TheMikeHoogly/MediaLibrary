#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — que rendrait un backfill DÉTERMINISTE du champ `faits` ?
──────────────────────────────────────────────────────────────────────────────

CE QU'ON MESURE, ET POURQUOI

`faits` est le germe de la mémoire familiale à provenance : chaque fait
(personne, animal, espèce, lieu, date) porte sa source. Il n'est écrit
aujourd'hui que par le worker de tagging, en aval du VLM — donc **uniquement
sur les photos taguées DEPUIS l'estampillage du pipeline** : 81 entrées sur
43 064 (0,19 %), exactement celles qui portent `pipe = …|v2ctx|kb1`.

Y brancher un filtre de recherche rendrait presque rien EN AYANT L'AIR DE
MARCHER — la forme d'erreur nommée le 15/08. Or la matière est déjà en base
pour la grande majorité des photos : noms `personne:`/`animal:` dans `kw_fr`,
espèces dans la table `animals`, lieux dans `gps_places.json` ou dans le
chemin, dates dans `taken`. Un backfill **pur** (sans GPU, sans VLM, sans
relecture du NAS) peut donc pourvoir `faits` avant tout filtre.

Ce module compte ce que ce backfill rendrait. **Il n'écrit rien.**

CE QU'IL NE FAIT PAS

- Aucun `UPDATE`, aucun fichier touché, aucun accès NAS, aucun modèle.
- Il refuse d'ouvrir un fichier nommé `photos.db` : le serveur est l'écrivain
  unique, on mesure sur une COPIE (invariant du projet).
- Il ne RECOPIE pas la prod là où elle est importable : la FORME des faits
  vient de `tagging_meta.faits_structures` (la fonction de prod), les noms de
  `tagging_meta.noms_depuis_kw`, la date lue dans le NOM du miroir déclaré
  `renommage_facts.fname_datetime`, l'année du dossier de
  `renommage_facts.path_year`.

LES DEUX APPROXIMATIONS, DÉCLARÉES

1. **Lieu par le CHEMIN** — la prod (`server._lieu_pour_cle`, branche 2) passe
   par `_lieu_plausible` segment par segment ; ici on utilise le miroir du
   renommage (`renommage_facts.resolve_path_place`), qui dit « même logique »
   sans être le même code. Le compte « lieu par chemin » est donc une
   ESTIMATION, pas le chiffre de la prod. Le lieu par GPS, lui, lit le même
   `gps_places.json` que la prod : celui-là est exact.
2. **Espèce** — comptée ici, mais elle dépend des DÉTECTIONS (table `animals`),
   pas de l'index : à traiter à part dans le backfill.

FUSEAU HORAIRE — la base porte des epochs LOCAUX (`time.mktime`). Lancé
ailleurs qu'en Europe/Zurich, le libellé d'une date du 31 décembre au soir peut
basculer d'année. Le fuseau est affiché en tête de rapport.

USAGE
    python mesure_faits_backfill.py --base copie.db [--json rapport.json]
                                    [--exemples 5]
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

try:
    import tagging_meta
    from renommage_facts import (fname_datetime, load_lieux, names_from_entry,
                                 path_year, resolve_path_place)
except ImportError:                      # exécuté hors du dossier du projet
    sys.stderr.write("mesure_faits_backfill : modules du projet introuvables — "
                     "lancer depuis le dossier du projet.\n")
    raise


# ───────────────────────────── logique PURE ─────────────────────────────

def nom_de(cle):
    """Nom de fichier d'une clé Windows, lisible sous POSIX aussi."""
    return str(cle).replace('\\', '/').rsplit('/', 1)[-1]


def epoch_du_nom(cle):
    """Epoch de la date lue dans le NOM, ou None. Miroir de `_fname_time` via
    `renommage_facts.fname_datetime` — une seule règle pour tous les bancs."""
    d8, hms = fname_datetime(nom_de(cle))
    if not d8:
        return None
    h, m, s = (int(hms[0:2]), int(hms[2:4]), int(hms[4:6])) if hms else (12, 0, 0)
    try:
        return time.mktime((int(d8[0:4]), int(d8[4:6]), int(d8[6:8]),
                            h, m, s, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


def date_et_source(cle, entree):
    """Date affichable et sa source, dans l'ordre de `server._assertions_pour` :
    `taken` (exif) → date lue dans le NOM → année du DOSSIER. **Jamais le
    `mtime`** (décision du 15/08 : le tagging de 2026 a réécrit une photo de
    1998). Renvoie (libellé|None, source|None)."""
    t = entree.get('taken') if isinstance(entree, dict) else None
    if isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0:
        return tagging_meta.format_date_fr(t), 'exif'
    fn = epoch_du_nom(cle)
    if fn:
        return tagging_meta.format_date_fr(fn), 'nom du fichier'
    an = path_year(cle)          # rend « YYYY » (chaine), pas un epoch
    if an:
        return str(an), 'annee du dossier'
    return None, None


def assertions_depuis_index(cle, entree, especes, gps_place, lieux):
    """Assemble le dict d'assertions attendu par `tagging_meta.faits_structures`
    à partir de la SEULE base — miroir de `server._assertions_pour`, mais sans
    relire le fichier.

    D'où la source des noms : **`index`**, et non `xmp`. Le backfill ne rouvre
    aucun fichier ; écrire `xmp` ferait porter au fait la provenance d'une
    lecture qui n'a pas eu lieu, et toute la valeur du champ tombe."""
    persons, animals = tagging_meta.noms_depuis_kw(names_from_entry(entree))
    lieu, lieu_src = (gps_place, 'gps') if gps_place else (
        resolve_path_place(cle, lieux), 'chemin')
    if not lieu:
        lieu_src = None
    date_txt, date_src = date_et_source(cle, entree)
    return {'key': cle, 'persons': persons, 'animals': animals,
            'species': sorted(especes or []),
            'lieu': lieu, 'lieu_src': lieu_src,
            'date': date_txt, 'date_src': date_src,
            'noms_src': 'index'}


def lieu_colle_dans_un_mot(cle, lieu):
    """Le libellé de lieu tiré du CHEMIN est-il collé À L'INTÉRIEUR d'un mot ?

    `renommage_facts.resolve_path_place` — la règle du RENOMMAGE — teste une
    SOUS-CHAÎNE : « Ins » se trouve dans « Cousins&Cousines ». Ce compte dit
    combien de photos reçoivent ainsi un lieu qui n'est pas dans leur chemin.
    (La règle du Knowledge Builder, `server._lieu_pour_cle`, compare des
    segments ENTIERS et n'a pas ce défaut : l'écart entre les deux est
    précisément ce que ce compteur mesure.)"""
    from renommage_facts import _media_relative_dir, _sans_accents
    lab = _sans_accents(lieu or '')
    if not lab:
        return False
    dossier = _media_relative_dir(cle)
    return not re.search(r'(?<![a-z])' + re.escape(lab) + r'(?![a-z])', dossier)


def signature(faits):
    """Ensemble {(type, valeur)} d'une liste de faits — pour comparer deux
    listes sans se laisser distraire par l'ordre ni par la source."""
    return {(f.get('t'), f.get('v')) for f in (faits or [])}


# ─────────────────────────── lectures (COPIE) ───────────────────────────

def ouvrir(base):
    """Ouvre la COPIE en lecture seule. Refuse `photos.db` : le serveur est
    l'écrivain unique (invariant du projet)."""
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais mesurer sur photos.db. "
                         "Copie la base d'abord, puis --base copie.db")
    if not p.exists():
        raise SystemExit(f"Base introuvable : {p}")
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def especes_par_cle(cx):
    """{clé: {espèces}} depuis la table `animals` (détections)."""
    out = {}
    try:
        cur = cx.execute('SELECT k, v FROM animals')
    except sqlite3.Error:
        return out
    for k, v in cur:
        try:
            e = json.loads(v)
        except (ValueError, TypeError):
            continue
        sp = {a.get('species') for a in (e.get('animals') or [])
              if isinstance(a, dict) and a.get('species')}
        if sp:
            out[k] = sp
    return out


def gps_places(chemin):
    """{clé: libellé} du géocodage inverse précalculé — le MÊME fichier que la
    prod (`server.gps_places_connus`). Vide s'il est absent."""
    try:
        d = json.loads(Path(chemin).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


# ────────────────────────────── la mesure ──────────────────────────────

def mesurer(base, dossier_projet, exemples=5):
    cx = ouvrir(base)
    esp = especes_par_cle(cx)
    gps = gps_places(Path(dossier_projet) / 'gps_places.json')
    lieux = load_lieux(Path(dossier_projet) / 'lieux.txt')

    n = 0
    pipes = Counter()
    dispo = Counter()          # matière disponible, par type de fait
    par_nb = Counter()         # nb de faits par entrée, APRÈS backfill
    src_date = Counter()
    src_lieu = Counter()
    deja, deja_identiques, deja_differents = 0, 0, 0
    non_date, date_seule = 0, 0
    lieu_colle = Counter()
    ecarts = []
    muettes = []

    for cle, v in cx.execute('SELECT k, v FROM tags'):
        n += 1
        try:
            e = json.loads(v)
        except (ValueError, TypeError):
            e = {}
        pipes[e.get('pipe')] += 1

        a = assertions_depuis_index(cle, e, esp.get(cle), gps.get(cle), lieux)
        F = tagging_meta.faits_structures(a)

        if a['persons']:
            dispo['personne'] += 1
        if a['animals']:
            dispo['animal'] += 1
        if a['species']:
            dispo['espece'] += 1
        if a['lieu']:
            dispo['lieu'] += 1
            src_lieu[a['lieu_src']] += 1
            if a['lieu_src'] == 'chemin' and lieu_colle_dans_un_mot(cle, a['lieu']):
                lieu_colle[a['lieu']] += 1
        if a['date']:
            dispo['date'] += 1
            src_date[a['date_src']] += 1

        types = {f['t'] for f in F}
        if types - {'date'}:
            non_date += 1
        elif types:
            date_seule += 1

        par_nb[len(F)] += 1
        if len(F) == 0 and len(muettes) < exemples:
            muettes.append(cle)

        anciens = e.get('faits')
        if anciens:
            deja += 1
            if signature(anciens) == signature(F):
                deja_identiques += 1
            else:
                deja_differents += 1
                if len(ecarts) < exemples:
                    ecarts.append({'cle': cle, 'avant': anciens, 'apres': F})

    couverts = n - par_nb[0]
    return {
        'base': str(base),
        'fuseau': time.strftime('%Z%z'),
        'entrees': n,
        'pipes': {str(k): v for k, v in pipes.most_common()},
        'faits_aujourdhui': deja,
        'faits_apres_backfill': couverts,
        'gagnees': couverts - deja if couverts >= deja else 0,
        'muettes': par_nb[0],
        'au_moins_un_fait_non_date': non_date,
        'date_seule': date_seule,
        'lieu_colle_dans_un_mot': dict(lieu_colle.most_common()),
        'matiere': dict(dispo),
        'source_date': dict(src_date),
        'source_lieu': dict(src_lieu),
        'faits_par_entree': {str(k): v for k, v in sorted(par_nb.items())},
        'deja_identiques': deja_identiques,
        'deja_differents': deja_differents,
        'exemples_ecarts': ecarts,
        'exemples_muettes': muettes,
    }


def pourcent(x, n):
    return f"{(100.0 * x / n):.2f} %" if n else "-"


def rapport(r):
    n = r['entrees']
    L = []
    A = L.append
    A("=" * 70)
    A("  MESURE — backfill deterministe du champ `faits`")
    A("=" * 70)
    A(f"  Base    : {r['base']}   (COPIE, lecture seule)")
    A(f"  Fuseau  : {r['fuseau']}")
    A(f"  Entrees : {n}")
    A("")
    A("  AUJOURD'HUI")
    A(f"    entrees avec `faits` : {r['faits_aujourdhui']}"
      f"   ({pourcent(r['faits_aujourdhui'], n)})")
    for k, v in r['pipes'].items():
        A(f"      pipe {k!s:<28} {v}")
    A("")
    A("  MATIERE DEJA EN BASE  (ce qu'un backfill PUR pourrait ecrire)")
    for t in ('personne', 'animal', 'espece', 'lieu', 'date'):
        v = r['matiere'].get(t, 0)
        A(f"    {t:<10} {v:>7}   ({pourcent(v, n)})")
    A(f"      lieu par source  : {r['source_lieu']}")
    A(f"      date par source  : {r['source_date']}")
    A("")
    A("  APRES BACKFILL")
    A(f"    entrees avec >= 1 fait : {r['faits_apres_backfill']}"
      f"   ({pourcent(r['faits_apres_backfill'], n)})")
    A(f"    gagnees                : {r['gagnees']}")
    A(f"    restent MUETTES        : {r['muettes']}"
      f"   ({pourcent(r['muettes'], n)})")
    A("")
    A("    UN SCORE PARFAIT EST UNE ALARME — le chiffre ci-dessus est porte")
    A("    par la DATE, que presque toute photo possede. Les deux chiffres")
    A("    honnetes :")
    A(f"      au moins 1 fait NON-date : {r['au_moins_un_fait_non_date']}"
      f"   ({pourcent(r['au_moins_un_fait_non_date'], n)})")
    A(f"      faits = la DATE SEULE    : {r['date_seule']}"
      f"   ({pourcent(r['date_seule'], n)})")
    A("    nombre de faits par entree :")
    for k, v in r['faits_par_entree'].items():
        A(f"      {k:>2} fait(s) : {v}")
    A("")
    A("  LES ENTREES DEJA POURVUES — le backfill dit-il la meme chose ?")
    A(f"    identiques : {r['deja_identiques']}")
    A(f"    differents : {r['deja_differents']}")
    for x in r['exemples_ecarts']:
        A(f"      {x['cle']}")
        A(f"        avant : {json.dumps(x['avant'], ensure_ascii=False)}")
        A(f"        apres : {json.dumps(x['apres'], ensure_ascii=False)}")
    if r['exemples_muettes']:
        A("")
        A("  EXEMPLES D'ENTREES QUI RESTERAIENT MUETTES")
        for c in r['exemples_muettes']:
            A(f"      {c}")
    colle = r.get('lieu_colle_dans_un_mot') or {}
    if colle:
        A("")
        A("  LIEU DE CHEMIN COLLE A L'INTERIEUR D'UN MOT  (regle du RENOMMAGE)")
        A(f"    total : {sum(colle.values())}")
        for lab, v in list(colle.items())[:8]:
            A(f"      {lab:<14} {v}")
        A("    `resolve_path_place` teste une SOUS-CHAINE ; le Knowledge")
        A("    Builder (`server._lieu_pour_cle`) compare des segments ENTIERS.")
        A("    Cet ecart est la raison de ne PAS backfiller le lieu avec ce")
        A("    miroir : le backfill doit appeler la regle de la prod.")
    A("")
    A("  RAPPELS — deux approximations declarees :")
    A("    * lieu par CHEMIN : miroir du renommage, pas le code de la prod.")
    A("      Le lieu par GPS lit le meme gps_places.json que la prod : exact.")
    A("    * espece : vient des DETECTIONS, pas de l'index — a traiter a part.")
    A("=" * 70)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', required=True,
                    help="COPIE de photos.db (jamais photos.db lui-meme)")
    ap.add_argument('--projet', default=os.path.dirname(os.path.abspath(__file__)),
                    help="dossier du projet (gps_places.json, lieux.txt)")
    ap.add_argument('--exemples', type=int, default=5)
    ap.add_argument('--json', help="ecrire le rapport brut en JSON")
    args = ap.parse_args()

    r = mesurer(args.base, args.projet, exemples=args.exemples)
    print(rapport(r))
    if args.json:
        Path(args.json).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                                   encoding='utf-8')
        print(f"\n  JSON ecrit : {args.json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
