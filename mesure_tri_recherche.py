#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — combien de photos le tri de la recherche place-t-il par leur `mtime` ?
──────────────────────────────────────────────────────────────────────────────

CE QU'ON MESURE, ET POURQUOI

`server.semantic_search` a deux règles de date, et elles se contredisent.
Le FILTRE (« photos de 2015 ») passe par `recherche.annee_fiable_depuis`, qui
refuse explicitement le `mtime` : le tagging de 2026 réécrit le fichier d'une
photo de 1998 (décision du 15/08). Le TRI de la branche « aucun mot pour
SigLIP » (`Luna en 2015`, `à Sion`) appelait `_best_time`, dont la branche 3
**est** ce `mtime`. Conséquence : la photo dont on ne sait RIEN dater prend la
date de son dernier tagging et passe DEVANT toutes les autres — le seul cas
certainement faux s'affiche en tête.

Ce module compte la portée, avant / après. Il ne corrige rien.

CE QU'IL NE FAIT PAS

- Il n'écrit RIEN. Aucun `UPDATE`, aucun fichier touché.
- Il refuse d'ouvrir un fichier nommé `photos.db` : le serveur est l'écrivain
  unique, on mesure sur une COPIE (invariant du projet).
- Il ne RECOPIE pas les critères. Le tri « après » vient de
  `recherche.trier_chronologique` (la fonction de PROD) ; les lecteurs de date
  viennent de `renommage_facts` (`fname_datetime`, `path_year`), miroirs
  déclarés de `server._fname_time` / `_path_year_num`. Un banc qui recopie la
  prod mesure autre chose qu'elle (14/08).

LES QUATRE RANGS

  precis        : `taken` ou date dans le NOM -> classée à la seconde.
  annee_dossier : ni l'un ni l'autre, mais une année dans les DOSSIERS.
  mtime         : aucune date sûre, mais un `mtime` -> **c'est le mensonge**.
                  L'ancien tri la datait de sa dernière écriture.
  aucune        : pas même un `mtime` -> `_best_time` rend 0, et l'ancienne clé
                  `_best_time(...) or ''` rendait la CHAÎNE vide. Mélangée à des
                  `float`, elle fait tomber `sorted` en `TypeError` : la
                  recherche répond 500. Ce compte dit si le mélange est possible.

DEUX LECTURES DU MÊME DÉFAUT

  (A) par ENTRÉE   : combien de photos sont placées par leur `mtime`.
  (B) par POSITION : combien d'entre elles occupent la TÊTE du classement.
Ce ne sont pas deux chemins indépendants — (B) trie ce que (A) compte — mais
c'est (B) qui dit ce que l'écran montre : dix photos muettes suffisent à
occuper le haut de page, et dix photos, en (A), se lisent « rien ».

FUSEAU HORAIRE — la base porte des epochs LOCAUX (`time.mktime`). Lancé
ailleurs qu'en Europe/Zurich, ce module peut faire basculer d'année une photo
du 31 décembre au soir. Il l'affiche en tête de rapport.

USAGE
    python mesure_tri_recherche.py --base copie.db [--tete 100] [--exemples 10]
                                   [--json rapport.json]
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import Counter

try:
    import recherche
    from renommage_facts import fname_datetime, path_year
except ImportError:                      # exécuté hors du dossier du projet
    sys.stderr.write("mesure_tri_recherche : modules du projet introuvables — "
                     "lancer depuis le dossier du projet.\n")
    raise


# ───────────────────────────── logique PURE ─────────────────────────────

def nom_de(cle):
    """Nom de fichier d'une clé Windows, lisible sous POSIX aussi."""
    return str(cle).replace('\\', '/').rsplit('/', 1)[-1]


def epoch_du_nom(cle):
    """Epoch de la date lue dans le NOM, ou None. Miroir de `_fname_time` :
    on passe par `renommage_facts.fname_datetime` pour n'avoir qu'UNE règle."""
    d8, hms = fname_datetime(nom_de(cle))
    if not d8:
        return None
    h, m, s = (int(hms[0:2]), int(hms[2:4]), int(hms[4:6])) if hms else (12, 0, 0)
    try:
        return time.mktime((int(d8[0:4]), int(d8[4:6]), int(d8[6:8]),
                            h, m, s, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


def epoch_precis(cle, entree):
    """Date PRÉCISE : `taken` et date du NOM, la plus ANCIENNE des deux —
    branche 1 de `_best_time`, et règle de `meme_jour.epoch_precis`."""
    precises = []
    t = entree.get('taken') if isinstance(entree, dict) else None
    if isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0:
        precises.append(float(t))
    fn = epoch_du_nom(cle)
    if fn:
        precises.append(float(fn))
    return min(precises) if precises else None


def annee_dossier(cle):
    """Année la plus ancienne des DOSSIERS du chemin (0 si aucune) —
    `_path_year_num`, via son miroir `renommage_facts.path_year`."""
    a = path_year(cle)
    return int(a) if a else 0


def mtime_de(entree):
    m = entree.get('mtime') if isinstance(entree, dict) else None
    if isinstance(m, (int, float)) and not isinstance(m, bool) and m > 0:
        return float(m)
    return None


def rang_de(cle, entree):
    """« precis » | « annee_dossier » | « mtime » | « aucune »."""
    if epoch_precis(cle, entree) is not None:
        return 'precis'
    if annee_dossier(cle):
        return 'annee_dossier'
    return 'mtime' if mtime_de(entree) is not None else 'aucune'


def cle_best_time(cle, entree):
    """La clé de tri d'AVANT, à l'identique : `_best_time(...) or ''`.
    Reproduite ici — et SEULEMENT ici — parce que mesurer un avant/après exige
    de faire tourner l'avant ; le code de prod, lui, ne la porte plus."""
    ep = epoch_precis(cle, entree)
    if ep is not None:
        return ep
    an = annee_dossier(cle)
    if an:
        try:
            return time.mktime((an, 1, 1, 12, 0, 0, 0, 0, -1))
        except (ValueError, OverflowError):
            pass
    m = mtime_de(entree)
    return m if m is not None else ''


def trier_avant(items):
    """L'ancien tri. Rend `(clés, plantage)` : `plantage` est le message du
    `TypeError` quand `float` et `str` se mélangent — la panne réelle, pas une
    hypothèse."""
    try:
        return sorted(items, key=lambda it: cle_best_time(it[0], it[1]),
                      reverse=True), None
    except TypeError as e:
        return None, str(e)


def annee_de(epoch):
    try:
        return time.localtime(float(epoch)).tm_year
    except (ValueError, TypeError, OverflowError, OSError):
        return 0



# ────────────────── (C) par REQUÊTE : ce que l'écran subit ──────────────────
#
# Compter les photos muettes ne dit pas si quelqu'un les voit. Une recherche par
# NOM SEUL (« Flo ») passe exactement par la branche corrigée : `_extraire_noms`
# retire le nom, il ne reste plus un mot pour SigLIP, et le tri décide seul de
# la page. On rejoue donc chaque nom de l'index. Les noms sont lus dans
# `kw_fr`/`kw_en`, comme `server._cles_portant` — pas dans une vue.
#
# Le chemin par LIEU (`_cles_du_lieu`) mène à la même branche, mais il demande
# `lieux.txt` et `gps_places.json` : il n'est PAS mesuré ici, et ce compte est
# donc un PLANCHER, pas un total.

def noms_de(entree):
    """Tags `personne:` / `animal:` d'une entrée, en minuscules."""
    kw = (entree.get('kw_fr') or []) + (entree.get('kw_en') or [])
    return {str(x).lower() for x in kw
            if str(x).lower().startswith(('personne:', 'animal:'))}


def par_nom(items, tete=100):
    """Rejoue « un nom, rien d'autre » pour chaque nom de l'index.

    Rend {nom: {'photos', 'muettes', 'plante', 'mtime_en_tete'}} :
      plante        — l'ancien tri lève `TypeError` (chaîne vide + float
                      mélangés) : la recherche répondait 500.
      mtime_en_tete — parmi les `tete` premières de l'ancien ordre, combien
                      étaient là par leur seul `mtime`. Mesuré seulement quand
                      l'ancien tri tient debout.
    """
    par_tag = {}
    for cle, e in items:
        if e.get('failed'):
            continue
        for n in noms_de(e):
            par_tag.setdefault(n, []).append((cle, e))
    out = {}
    for nom, sous in par_tag.items():
        muettes = [c for c, e in sous if cle_best_time(c, e) == '']
        placees_mtime = {c for c, e in sous if rang_de(c, e) == 'mtime'}
        avant, plantage = trier_avant(sous)
        out[nom] = {
            'photos': len(sous),
            'muettes': len(muettes),
            'placees_mtime': len(placees_mtime),
            'plante': plantage is not None,
            'mtime_en_tete': (sum(1 for c, _ in avant[:tete]
                                  if c in placees_mtime)
                              if avant is not None else None),
        }
    return out



# ─────────── (D) la GALERIE : le meme mensonge, cote client ───────────
#
# `sortBy('date')` de `GALLERY_PAGE` classe par `f.taken || f.mtime`, et `taken`
# est déjà `_best_time` — donc `mtime` en dernier recours. C'est la règle que la
# recherche vient d'abandonner, toujours en place dans la vue la plus utilisée.
#
# Elle ne se voit pas de la même façon dans les deux sens : le tri par défaut est
# CROISSANT, et une photo sans date porte un `mtime` de 2026, la plus grande
# valeur — elle tombe donc en fin de liste, là où la règle honnête la met aussi.
# **C'est au reclic (décroissant) que le défaut sort** : ces photos passent en
# tête. On compte donc les deux, séparément, plutôt que d'annoncer un seul
# chiffre qui vaudrait pour un sens et pas pour l'autre.

def dossier_de(cle):
    k = str(cle).replace('\\', '/')
    return k.rsplit('/', 1)[0] if '/' in k else ''


def par_dossier(items, mini=2):
    """Par DOSSIER : combien de photos n'ont aucune date sûre, et le dossier
    est-il entièrement muet (auquel cas son ordre est arbitraire de bout en
    bout, dans les deux sens) ?

    Rend {'dossiers', 'dossiers_touches', 'photos_sans_date_sure',
    'dossiers_entierement_muets', 'photos_dans_ces_dossiers', 'pires'}.
    """
    par = {}
    for cle, e in items:
        if e.get('failed'):
            continue
        par.setdefault(dossier_de(cle), []).append((cle, e))
    touches, muets, pires = 0, [], []
    total_muettes = 0
    for d, sous in par.items():
        if len(sous) < mini:
            continue
        muettes = sum(1 for c, e in sous if rang_de(c, e) in ('mtime', 'aucune'))
        if not muettes:
            continue
        touches += 1
        total_muettes += muettes
        if muettes == len(sous):
            muets.append((len(sous), d))
        pires.append((muettes, len(sous), d))
    pires.sort(reverse=True)
    muets.sort(reverse=True)
    return {
        'dossiers': sum(1 for v in par.values() if len(v) >= mini),
        'dossiers_touches': touches,
        'photos_sans_date_sure': total_muettes,
        'dossiers_entierement_muets': len(muets),
        'photos_dans_ces_dossiers': sum(n for n, _ in muets),
        'pires': pires[:8],
    }


# ─────────────────────────── lecture de la COPIE ───────────────────────────

def charger(chemin):
    """[(clé, entrée)] de la table `tags` d'une COPIE. Lecture seule."""
    if os.path.basename(chemin).lower() == 'photos.db':
        raise SystemExit("REFUS : mesurer sur une COPIE, jamais sur photos.db "
                         "(le serveur en est l'ecrivain unique).")
    cx = sqlite3.connect(f'file:{chemin}?mode=ro', uri=True)
    try:
        items = []
        for k, v in cx.execute('SELECT k, v FROM "tags"'):
            try:
                e = json.loads(v)
            except (ValueError, TypeError):
                e = {}
            items.append((k, e if isinstance(e, dict) else {}))
        return items
    finally:
        cx.close()


# ───────────────────────────── rapport ─────────────────────────────

def mesurer(items, tete=100, exemples=10):
    rangs = Counter()
    par_mtime = []
    sans_rien = []
    for cle, e in items:
        r = rang_de(cle, e)
        rangs[r] += 1
        if r == 'mtime':
            par_mtime.append((mtime_de(e), cle))
        elif r == 'aucune':
            sans_rien.append(cle)

    avant, plantage = trier_avant(items)
    apres, sans_date_apres = recherche.trier_chronologique(
        items, epoch_precis,
        recherche.annee_fiable_depuis(epoch_precis, annee_dossier))

    muettes = {c for _, c in par_mtime} | set(sans_rien)
    # `avant is None` = l'ancien tri ne s'exécute pas du tout sur ce corpus.
    # On rend alors None, jamais 0 : « non mesurable » et « aucune » sont deux
    # réponses différentes, et les confondre ferait passer une panne pour un
    # bon score (un score parfait est une alarme).
    tete_avant = ([c for c, _ in avant[:tete]] if avant is not None else None)
    rapport = {
        'total': len(items),
        'rangs': dict(rangs),
        'annees_mtime': dict(Counter(annee_de(m) for m, _ in par_mtime)),
        'plantage_ancien_tri': plantage,
        'tete': tete,
        'muettes_en_tete_avant': (None if tete_avant is None
                                  else sum(1 for c in tete_avant
                                           if c in muettes)),
        'muettes_en_tete_apres': sum(1 for c in apres[:tete] if c in muettes),
        'sans_date_compte_par_le_nouveau_tri': sans_date_apres,
        'exemples_mtime': [c for _, c in sorted(par_mtime, reverse=True)[:exemples]],
        'exemples_aucune': sans_rien[:exemples],
        'fuseau': time.tzname,
    }
    rapport['galerie'] = par_dossier(items)
    noms = par_nom(items, tete=tete)
    casses = {n: d for n, d in noms.items() if d['plante']}
    en_tete = {n: d for n, d in noms.items()
               if d['mtime_en_tete']}
    rapport['requetes_par_nom'] = {
        'noms': len(noms),
        'noms_qui_plantent': len(casses),
        'photos_derriere_ces_noms': sum(d['photos'] for d in casses.values()),
        'exemples_qui_plantent': sorted(
            casses, key=lambda n: -casses[n]['photos'])[:exemples],
        'noms_avec_du_mtime_en_tete': len(en_tete),
        'exemples_mtime_en_tete': [
            (n, en_tete[n]['mtime_en_tete'], en_tete[n]['photos'])
            for n in sorted(en_tete, key=lambda n: -en_tete[n]['mtime_en_tete'])
        ][:exemples],
    }
    return rapport


def imprimer(rap):
    p = print
    p("")
    p(f"  Fuseau horaire du poste de mesure : {rap['fuseau']}")
    p(f"  Entrees lues : {rap['total']}")
    p("")
    p("  RANG DE DATE (ce que le tri a pour se decider)")
    for nom, libelle in (('precis', 'date precise (taken / nom)'),
                         ('annee_dossier', 'annee du DOSSIER seule'),
                         ('mtime', 'AUCUNE date sure -> mtime'),
                         ('aucune', 'aucune date, pas meme un mtime')):
        p(f"    {libelle:<34} {rap['rangs'].get(nom, 0):>7}")
    p("")
    if rap['annees_mtime']:
        p("  ANNEE PRETEE aux photos placees par leur mtime")
        for an in sorted(rap['annees_mtime'], reverse=True):
            p(f"    {an:<34} {rap['annees_mtime'][an]:>7}")
        p("")
    p("  EN TETE DE CLASSEMENT DE L'INDEX ENTIER (les %d premieres)"
      % rap['tete'])
    av = rap['muettes_en_tete_avant']
    p("    photos sans date sure, AVANT   %7s"
      % ('non mesurable' if av is None else av))
    p(f"    photos sans date sure, APRES   {rap['muettes_en_tete_apres']:>7}")
    p("")
    p(f"  Comptees `sans_date` par le nouveau tri : "
      f"{rap['sans_date_compte_par_le_nouveau_tri']}")
    if rap['plantage_ancien_tri']:
        p(f"  ANCIEN TRI EN PANNE : TypeError — {rap['plantage_ancien_tri']}")
        p("    (float et chaine vide melanges : la recherche repondait 500)")
    else:
        p("  Ancien tri : pas de TypeError sur ce corpus.")
    ga = rap.get('galerie') or {}
    if ga:
        p("  LA GALERIE (tri client `taken || mtime`, meme mensonge)")
        p(f"    dossiers de 2 photos et plus  {ga['dossiers']:>7}")
        p(f"    dont au moins une sans date   {ga['dossiers_touches']:>7}")
        p(f"    photos concernees             "
          f"{ga['photos_sans_date_sure']:>7}")
        p(f"    dossiers ENTIEREMENT muets    "
          f"{ga['dossiers_entierement_muets']:>7}"
          f"  ({ga['photos_dans_ces_dossiers']} photos, ordre arbitraire)")
        for m, n, d in ga['pires']:
            p(f"    {m:>4}/{n:<5} {d[-58:]}")
        p("")
    rq = rap.get('requetes_par_nom') or {}
    if rq:
        p("  UN NOM, RIEN D'AUTRE (la branche corrigee) — PLANCHER : le")
        p("  chemin par LIEU mene a la meme branche et n'est pas mesure ici.")
        p(f"    noms dans l'index               {rq['noms']:>7}")
        p(f"    noms dont la recherche PLANTE   {rq['noms_qui_plantent']:>7}")
        p(f"    photos derriere ces noms        "
          f"{rq['photos_derriere_ces_noms']:>7}")
        p(f"    noms avec du mtime EN TETE      "
          f"{rq['noms_avec_du_mtime_en_tete']:>7}")
        if rq['exemples_qui_plantent']:
            p("    -> " + ", ".join(rq['exemples_qui_plantent']))
        for n, k, tot in rq['exemples_mtime_en_tete']:
            p(f"    {n:<28} {k:>3} des {rap['tete']} premieres "
              f"(sur {tot} photos)")
        p("")
    for titre, cle in (("Exemples places par leur mtime", 'exemples_mtime'),
                       ("Exemples sans aucune date", 'exemples_aucune')):
        if rap[cle]:
            p("")
            p(f"  {titre} :")
            for c in rap[cle]:
                p(f"    {c}")
    p("")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--base', required=True, help='COPIE de photos.db')
    ap.add_argument('--tete', type=int, default=100)
    ap.add_argument('--exemples', type=int, default=10)
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    rap = mesurer(charger(a.base), tete=a.tete, exemples=a.exemples)
    imprimer(rap)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(rap, f, ensure_ascii=False, indent=1)
        print(f"  rapport JSON -> {a.json}\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
