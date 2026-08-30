#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scinder une liste de mots-cles FR+EN relue du XMP en `kw_fr` / `kw_en`
──────────────────────────────────────────────────────────────────────────────

D'OU VIENT LE MELANGE (mesure du 30/08, copie de l'index) : `write_metadata`
ecrit dans le XMP la liste `kw_fr + kw_en`, dans CET ordre. Quand l'index a
ete reconstruit depuis les fichiers, cette liste est revenue ENTIERE dans
`kw_fr`, et `kw_en` est reste vide : **22 196 photos sur 42 714 (52 %)**. La
recherche les trouve dans les deux langues ; les puces montrent de l'anglais,
et un mot-cle « chair » a l'air d'une faute du tagueur alors qu'il n'en est
pas une. (Le tagueur d'aujourd'hui fuit tres peu : 11 photos sur 4 804.)

LA REGLE, PURE : la liste est un bloc FRANCAIS puis un bloc ANGLAIS, il y a
donc une coupure. Deux vocabulaires appris sur les entrees SAINES (celles qui
ont un `kw_en`) — V_fr = leurs `kw_fr`, V_en = leurs `kw_en`, en frequences —
font voter chaque tag : +1 plutot francais, -1 plutot anglais, 0 inconnu ou
a egalite (« table », « orange »). Score d'une coupure i = votes du prefixe
moins votes du suffixe ; on retient le score maximal, et a score egal la
coupure la plus proche du MILIEU (le tagueur ecrit 6-10 tags par langue). Les
noms `personne:`/`animal:` restent en `kw_fr`, a leur place.

MESURE (30/08, `mesure_scission_fr_en.py`) : 22 190 des 22 196 se scindent,
19 175 avec une coupure unique, 3 015 a ex aequo tranches par le milieu ;
94 sont tout anglais (rien a garder en FR), 6 deja tout francais.

Module PUR : ni store, ni base, ni verrou. Partage par le banc qui mesure et
l'applicateur qui ecrit — une seule lecture de la regle dans le projet.
"""
from collections import Counter

PREFIXES_NOMS = ('personne:', 'animal:')


def vocabulaires(index):
    """(V_fr, V_en) : frequences des tags dans les entrees qui ONT un kw_en.
    `index` : {cle: entree} ou un iterable d'entrees."""
    vfr, ven = Counter(), Counter()
    entrees = index.values() if isinstance(index, dict) else index
    for e in entrees:
        if not isinstance(e, dict):
            continue
        ke = [t for t in (e.get('kw_en') or []) if isinstance(t, str)]
        if not ke:
            continue
        for t in (e.get('kw_fr') or []):
            if isinstance(t, str) and not t.startswith(PREFIXES_NOMS):
                vfr[t.lower()] += 1
        for t in ke:
            ven[t.lower()] += 1
    return vfr, ven


def vote(tag, vfr, ven):
    """+1 plutot francais, -1 plutot anglais, 0 inconnu ou a egalite."""
    f, en = vfr.get(tag.lower(), 0), ven.get(tag.lower(), 0)
    if f == en:
        return 0
    return 1 if f > en else -1


def scinder(kw, vfr, ven):
    """(kw_fr, kw_en, ex_aequo, i) pour une liste SANS noms.

    i parcourt 0..len(kw) ; score(i) = votes(kw[:i]) - votes(kw[i:]). A score
    egal, la coupure la plus proche du milieu. `ex_aequo` = nombre de coupures
    au score maximal (1 = unique)."""
    votes = [vote(t, vfr, ven) for t in kw]
    total = sum(votes)
    scores, pref = [], 0
    for i in range(len(kw) + 1):
        scores.append(pref - (total - pref))
        if i < len(kw):
            pref += votes[i]
    meilleur = max(scores)
    cands = [i for i, sc in enumerate(scores) if sc == meilleur]
    milieu = len(kw) / 2.0
    i_best = min(cands, key=lambda i: (abs(i - milieu), -i))   # a distance egale, le neutre reste FR
    return kw[:i_best], kw[i_best:], len(cands), i_best


def scinder_entree(entree, vfr, ven):
    """Ce que l'applicateur ecrirait pour une entree : (kw_fr, kw_en, ex_aequo),
    ou None si l'entree n'est pas a scinder (elle a deja un `kw_en`, ou n'a
    pas de mots-cles, ou tout est deja francais). Les noms gardent leur place
    dans `kw_fr` ; `kw_en` recoit le bloc anglais, sans nom."""
    if not isinstance(entree, dict) or (entree.get('kw_en') or []):
        return None
    kw = [t for t in (entree.get('kw_fr') or []) if isinstance(t, str)]
    corps = [t for t in kw if not t.startswith(PREFIXES_NOMS)]
    if not corps:
        return None
    fr, en, exaequo, i = scinder(corps, vfr, ven)
    if not en:
        return None
    en_set = set(en)
    kw_fr = [t for t in kw if t.startswith(PREFIXES_NOMS) or t not in en_set]
    return kw_fr, list(en), exaequo
