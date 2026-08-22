#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — la casse des tags nommés, et les noms que PERSONNE ne réclame
──────────────────────────────────────────────────────────────────────────────

LA QUESTION

L'audit interne du 11/08 (I7) dit : « la casse des tags nommés n'est
normalisée qu'à trois endroits, donc un `personne:nom` importé n'est JAMAIS
auto-guéri ». C'est un défaut de CODE, écrit un mois avant ce banc. Personne
n'a jamais demandé au FONDS s'il en portait la trace.

Ce banc pose la seule question qui décide de la valeur du correctif :
**combien de tags nommés, aujourd'hui, échappent aux comparaisons faites en
casse sensible ?** Un défaut latent se corrige quand même — mais on ne
l'annonce pas comme une réparation, et on ne lui donne pas la place d'un
chantier. Le chiffre le dit, pas l'intention.

CINQ VERDICTS, ET UN SEUL EST « NORMAL »

  * `ok`               — préfixe en minuscules, nom écrit comme la fiche.
  * `prefixe`          — « Personne:Flo » : invisible à tout `startswith(
                         'personne:')`. Le tag existe et rien ne le voit.
  * `casse`            — « animal:luna » quand la fiche dit « Luna » : le
                         curateur croit la photo NON taguée (il peut proposer
                         un doublon) et son contrôle REMOVE ne la visite
                         jamais — c'est le « jamais auto-guéri » de I7.
  * `sans_fiche`       — « personne:Florine » sans aucune fiche Florine : le
                         nom vit dans l'index, s'affiche, filtre… mais aucune
                         signature, aucun avatar, aucun curateur. Ce n'est PAS
                         un défaut de casse : c'est une personne que
                         `/api/names` ne connaît pas.
  * `doublon_de_casse` — deux écritures du même nom sur la même photo.

CE QUE LE VERDICT N'EST PAS

Il ne dit pas si le nom est JUSTE. « Florine » sur 153 photos peut être une
personne à part entière, ou l'ancien nom de quelqu'un d'autre : ça, c'est un
jugement humain, et il ne se déduit d'aucune colonne.

CE QU'IL NE FAIT PAS

Aucun `UPDATE`, aucun accès NAS, aucun modèle, aucun appel réseau. Lecture
seule sur une COPIE (`mesure_copie_base.py` la fabrique) — jamais `photos.db`,
le serveur en est l'écrivain unique.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_noms_casse.py --base copie.db
    python mesure_noms_casse.py --base copie.db --exemples 8 --json r.json
"""

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# La RÈGLE vient de la prod, elle n'est pas recopiée ici (`eval/METHODE.md`,
# 14/08). Si `parse_tag_nomme` n'existe pas encore — ce banc a été écrit AVANT
# le correctif I7 — on tombe sur une lecture locale STRICTEMENT équivalente,
# et le rapport le DIT. Un banc qui se tait sur ce qu'il n'a pas pu importer
# mesure un cousin de la prod sans prévenir.
try:
    from tagging_meta import parse_tag_nomme
    REGLE = 'tagging_meta.parse_tag_nomme (prod)'
except ImportError:                                    # pragma: no cover
    REGLE = 'repli local (parse_tag_nomme absent de tagging_meta)'

    def parse_tag_nomme(t):
        s = str(t)
        low = s.lower()
        for pref in ('personne', 'animal'):
            if low.startswith(pref + ':'):
                nom = s.split(':', 1)[1].strip()
                return (pref, nom) if nom else None
        return None


PREFIXES = ('personne', 'animal')
TABLE_FICHE = {'personne': 'people', 'animal': 'pets'}


# ──────────────────────────── le cœur, PUR ────────────────────────────

def verdict(tag, fiches):
    """(verdict, genre, nom, nom_fiche) pour UN tag nommé.

    `fiches` : {(genre, nom_en_minuscules): orthographe de la fiche}.
    Renvoie None si le tag n'est pas un tag nommé."""
    parse = parse_tag_nomme(tag)
    if not parse:
        return None
    genre, nom = parse
    s = str(tag)
    prefixe_brut = s.split(':', 1)[0]
    fiche = fiches.get((genre, nom.lower()))
    if fiche is None:
        v = 'sans_fiche'
    elif nom != fiche:
        v = 'casse'
    elif prefixe_brut != genre:
        v = 'prefixe'
    else:
        v = 'ok'
    # Le préfixe prime : un tag que `startswith` ne voit pas est invisible
    # AVANT d'être mal orthographié.
    if prefixe_brut != genre and v in ('casse', 'sans_fiche'):
        v = 'prefixe'
    return v, genre, nom, fiche


def doublons_de_casse(tags):
    """[[écritures]] — les noms écrits de PLUSIEURS façons sur la même photo."""
    vus = defaultdict(list)
    for t in tags:
        p = parse_tag_nomme(t)
        if p:
            vus[(p[0], p[1].lower())].append(str(t))
    return [lst for lst in vus.values() if len(set(lst)) > 1]


# ─────────────────────────── lecture de la base ───────────────────────────

def ouvrir(base):
    """Ouvre la COPIE, en LECTURE SEULE. Refuse `photos.db`."""
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais mesurer sur photos.db. "
                         "Copie la base d'abord (mesure_copie_base.py), "
                         "puis --base copie.db")
    if not p.exists():
        raise SystemExit(f"Base introuvable : {p}")
    return sqlite3.connect(f'file:{p}?mode=ro', uri=True)


def lire_json(v):
    try:
        e = json.loads(v)
        return e if isinstance(e, dict) else {}
    except (ValueError, TypeError):
        return {}


def fiches_par_nom(cx):
    """{(genre, nom_minuscule): orthographe de la fiche} — l'AUTORITÉ."""
    out = {}
    for genre in PREFIXES:
        try:
            cur = cx.execute(f'SELECT k, v FROM "{TABLE_FICHE[genre]}"')
        except sqlite3.Error:
            continue
        for k, v in cur:
            e = lire_json(v)
            nom = str(e.get('name') or '').strip()
            if nom:
                out[(genre, nom.lower())] = nom
            elif k:                       # fiche sans `name` : la clé fait foi
                out[(genre, str(k).lower())] = str(k)
    return out


def mesurer(base, exemples=6):
    cx = ouvrir(base)
    t0 = time.perf_counter()
    fiches = fiches_par_nom(cx)
    compte = Counter()
    par_nom = defaultdict(Counter)        # (genre, nom brut) -> verdicts
    photos = defaultdict(set)             # verdict -> clés
    ex = defaultdict(list)
    doublons, ex_doublons = 0, []
    lus = 0
    for k, v in cx.execute('SELECT k, v FROM tags'):
        e = lire_json(v)
        if not e or e.get('failed'):
            continue
        lus += 1
        tags = [str(t) for t in (e.get('kw_fr') or [])]
        for t in tags:
            r = verdict(t, fiches)
            if not r:
                continue
            v_, genre, nom, fiche = r
            compte[v_] += 1
            par_nom[(genre, t)][v_] += 1
            photos[v_].add(k)
            if v_ != 'ok' and len(ex[v_]) < exemples:
                ex[v_].append({'cle': k, 'tag': t, 'fiche': fiche})
        for lst in doublons_de_casse(tags):
            doublons += 1
            if len(ex_doublons) < exemples:
                ex_doublons.append({'cle': k, 'ecritures': sorted(set(lst))})
    cx.close()
    total = sum(compte.values())
    suspects = {}
    for (genre, tag), c in par_nom.items():
        mauvais = {v_: n for v_, n in c.items() if v_ != 'ok'}
        if mauvais:
            suspects[f'{genre}|{tag}'] = mauvais
    return {
        'base': str(base), 'regle': REGLE,
        'photos_lues': lus, 'fiches': len(fiches),
        'tags_nommes': total,
        'verdicts': dict(compte),
        'photos_par_verdict': {v_: len(s) for v_, s in photos.items()},
        'doublons_de_casse': doublons,
        'suspects': suspects,
        'exemples': {v_: l for v_, l in ex.items()},
        'exemples_doublons': ex_doublons,
        'duree_s': round(time.perf_counter() - t0, 2),
    }


# ──────────────────────────────── rapport ────────────────────────────────

LIBELLE = {
    'ok': "conformes (préfixe minuscule, nom comme la fiche)",
    'prefixe': "PRÉFIXE non canonique — aucun `startswith` ne les voit",
    'casse': "nom en CASSE divergente — le curateur ne les visite jamais (I7)",
    'sans_fiche': "nom SANS FICHE — l'index le porte, `/api/names` l'ignore",
}


def afficher(rap):
    L = []
    A = L.append
    A("=" * 78)
    A("MESURE — casse des tags nommés, et noms sans fiche")
    A("=" * 78)
    A(f"Base : {rap['base']} | règle : {rap['regle']}")
    A(f"{rap['photos_lues']} photos lues, {rap['fiches']} fiches, "
      f"{rap['tags_nommes']} tags nommés.")
    A("")
    A("-- VERDICTS ----------------------------------------------------------")
    for v_ in ('ok', 'prefixe', 'casse', 'sans_fiche'):
        n = rap['verdicts'].get(v_, 0)
        ph = rap['photos_par_verdict'].get(v_, 0)
        A("  %-12s %6d tag(s) sur %5d photo(s) — %s"
          % (v_, n, ph, LIBELLE[v_]))
    A("  %-12s %6d — deux écritures du même nom sur UNE photo"
      % ('doublons', rap['doublons_de_casse']))
    A("")
    if not rap['suspects'] and not rap['doublons_de_casse']:
        A("  AUCUN tag nommé n'échappe aux comparaisons en casse sensible.")
        A("  I7 est un défaut LATENT : le corriger est de la robustesse, pas")
        A("  une réparation. Ne pas l'annoncer comme telle.")
    else:
        A("-- CE QUI ÉCHAPPE, NOM PAR NOM ---------------------------------------")
        for cle, c in sorted(rap['suspects'].items(),
                             key=lambda kv: -sum(kv[1].values())):
            genre, tag = cle.split('|', 1)
            A("  %-9s %-28s %s" % (genre, tag,
                                   ', '.join(f"{v_}={n}" for v_, n in c.items())))
    A("")
    A("-- À REGARDER, PAS À CROIRE ------------------------------------------")
    for v_ in ('prefixe', 'casse', 'sans_fiche'):
        for e in rap['exemples'].get(v_) or []:
            A("  [%s] %s" % (v_, e['tag']))
            A("      fiche : %s" % (e['fiche'] if e['fiche'] else '(aucune)'))
            A("      %s" % e['cle'][-68:])
    for e in rap['exemples_doublons']:
        A("  [doublon] %s" % ' + '.join(e['ecritures']))
        A("      %s" % e['cle'][-68:])
    A("=" * 78)
    A(f"Durée : {rap['duree_s']} s")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', required=True, help="COPIE de photos.db")
    ap.add_argument('--exemples', type=int, default=6)
    ap.add_argument('--json', dest='sortie_json')
    a = ap.parse_args(argv)
    rap = mesurer(a.base, a.exemples)
    print(afficher(rap))
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\nJSON : {a.sortie_json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
