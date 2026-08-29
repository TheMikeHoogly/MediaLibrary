#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L'AUTEUR d'une décision humaine — et qui l'emporte quand deux se contredisent
──────────────────────────────────────────────────────────────────────────────

Chantier 17, étape 2 (choix de Mike, 29/08/2026, `eval/DECISIONS.md`).

OÙ VIT L'AUTEUR

Une décision humaine est un élément de liste dans la fiche d'une personne ou
d'un animal — `faces` = `[chemin, index]`, `exclude` / `confirmed` = chemin —
sans place pour un nom. Tout le re-clé, l'annulation et les bancs lisent ces
listes : on ne change PAS leur forme. La fiche gagne un dictionnaire à côté :

    auteurs  { "faces:<chemin>:<index>": "Mike",
               "exclude:<chemin>":       "Flo",
               "confirmed:<chemin>":     "Mike",
               "exclude:<chemin>#contesté": "Flo" }      # jugement perdant, gardé

Une clé d'`auteurs` sans décision dans les listes est retirée (la décision a
été annulée) — SAUF les `#contesté`, qui sont la mémoire d'un jugement perdu.

QUI L'EMPORTE

Florine exclut, Mike confirme — sur la MÊME photo, pour le MÊME nom. Règle :
le PROPRIÉTAIRE de la photo (donné par son dossier `Photos <Nom>`) l'emporte
sur ses photos ; hors d'un dossier propriétaire, l'admin arbitre ; si ni l'un
ni l'autre n'a voix, le jugement DÉJÀ posé reste et le nouveau est contesté
(jamais « le dernier qui écrit gagne » : ça fait perdre un jugement sans le
dire). La décision perdante n'est pas effacée : elle reste dans `auteurs`
avec le suffixe `#contesté`, visible dans la fiche.

Seule la paire `exclude` ↔ `confirmed` est une contradiction. Deux `faces`
n'en sont pas (un visage attribué à deux fiches est un conflit ENTRE fiches,
hors de portée ici — voir ROADMAP, chantier 17).

CE MODULE EST UNE RÈGLE PURE

Comme `recle_decisions` : il prend une fiche, rend les CHAMPS à réassigner,
ne mute rien, ne connaît ni store ni base. Le serveur l'applique au GOULOT
(`PEOPLE_STORE.set` / `PETS_STORE.set`), donc chacun des trente endroits qui
écrivent une décision est couvert sans être touché ; l'applicateur hors-ligne
le partage par `recle_decisions`.
"""

import re

ADMIN = 'Mike'
CONTESTE = '#contesté'
CONTRAIRE = {'exclude': 'confirmed', 'confirmed': 'exclude'}
PROPRIETAIRE_RE = re.compile(r'^photos\s+(\S.*)$', re.I)


def proprietaire_de(chemin):
    """Le propriétaire d'une photo, lu dans son chemin : le premier segment
    `Photos <Nom>` → `<Nom>`. None hors d'un dossier propriétaire (racine,
    `_Uploads`, `_A TRIER` de la racine…). Robuste aux deux séparateurs."""
    for seg in str(chemin or '').replace('\\', '/').split('/'):
        m = PROPRIETAIRE_RE.match(seg.strip())
        if m:
            return m.group(1).strip()
    return None


def ident(champ, cle, idx=None):
    """La clé d'`auteurs` d'une décision."""
    if champ == 'faces':
        return f"faces:{cle}:{int(idx or 0)}"
    return f"{champ}:{cle}"


def lire_ident(k):
    """(champ, chemin, index|None, contesté) depuis une clé d'`auteurs`."""
    conteste = k.endswith(CONTESTE)
    if conteste:
        k = k[:-len(CONTESTE)]
    champ, _, reste = k.partition(':')
    if champ == 'faces':
        chemin, _, i = reste.rpartition(':')
        try:
            return champ, chemin, int(i), conteste
        except ValueError:
            return champ, reste, None, conteste
    return champ, reste, None, conteste


def _paire(x):
    if isinstance(x, (list, tuple)) and len(x) == 2 and isinstance(x[0], str):
        try:
            return x[0], int(x[1] or 0)
        except (TypeError, ValueError):
            return None
    return None


def decisions_de(fiche):
    """L'ensemble des idents des décisions que portent les listes."""
    out = set()
    if not isinstance(fiche, dict):
        return out
    for x in (fiche.get('faces') or []):
        p = _paire(x)
        if p:
            out.add(ident('faces', p[0], p[1]))
    for champ in ('exclude', 'confirmed'):
        for cle in (fiche.get(champ) or []):
            if isinstance(cle, str):
                out.add(ident(champ, cle))
    return out


def arbitre(proprietaire, ancien, nouveau):
    """Qui l'emporte entre l'auteur DÉJÀ posé et le nouveau, sur une photo de
    `proprietaire` (None hors dossier propriétaire)."""
    if proprietaire in (ancien, nouveau):
        return proprietaire
    if ADMIN in (ancien, nouveau):
        return ADMIN
    return ancien


def reconcilier(fiche, auteur):
    """(champs à réassigner) — `{}` si rien ne change.

    Toute décision des listes sans auteur est attribuée à `auteur` ; une
    entrée d'`auteurs` sans décision est retirée (sauf `#contesté`) ; une
    décision NEUVE qui contredit une décision d'un AUTRE auteur passe par
    `arbitre` — le perdant sort de sa liste et reste en `#contesté`.
    """
    if not isinstance(fiche, dict):
        return {}
    auteur = auteur or ADMIN
    avant = dict(fiche.get('auteurs') or {})
    A = dict(avant)
    D = decisions_de(fiche)
    listes = {c: list(fiche.get(c) or []) for c in ('exclude', 'confirmed')}
    retirer = set()

    for k in sorted(D):
        if k in A:
            continue
        champ, cle, _i, _c = lire_ident(k)
        contraire = ident(CONTRAIRE[champ], cle) if champ in CONTRAIRE else None
        if contraire and contraire in D and A.get(contraire) not in (None, auteur):
            gagnant = arbitre(proprietaire_de(cle), A[contraire], auteur)
            if gagnant == auteur:
                A[contraire + CONTESTE] = A.pop(contraire)
                retirer.add(contraire)
                A[k] = auteur
            else:
                A[k + CONTESTE] = auteur
                retirer.add(k)
            continue
        A[k] = auteur

    for k in list(A):
        if k.endswith(CONTESTE):
            continue
        if k not in D or k in retirer:
            del A[k]

    champs = {}
    for k in retirer:
        champ, cle, _i, _c = lire_ident(k)
        listes[champ] = [x for x in listes[champ] if x != cle]
        champs[champ] = listes[champ]
    if A != avant:
        champs['auteurs'] = A
    return champs


def recler(auteurs, old, new):
    """Le dictionnaire `auteurs` avec `old` remplacé par `new` dans ses clés,
    ou None si rien ne change. Une cible déjà présente n'est pas écrasée."""
    if not isinstance(auteurs, dict) or old == new:
        return None
    out, recles = {}, []
    for k, v in auteurs.items():           # d'abord ce qui reste en place…
        champ, cle, i, conteste = lire_ident(k)
        if cle != old:
            out[k] = v
        else:
            recles.append((ident(champ, new, i) + (CONTESTE if conteste else ''), v))
    for nk, v in recles:                   # …puis les re-clés, sans écraser
        out.setdefault(nk, v)
    return out if recles else None


def garnir(store, utilisateur):
    """Enveloppe `store.set(name, entry, save=True)` pour réconcilier `auteurs`
    AVANT chaque écriture d'une fiche — le goulot par où passent toutes les
    décisions. `utilisateur` est un appelable qui rend l'auteur courant."""
    set0 = store.set

    def set_(name, entry, save=True):
        if isinstance(entry, dict):
            for champ, valeur in reconcilier(entry, utilisateur()).items():
                entry[champ] = valeur
        return set0(name, entry, save)
    store.set = set_
    return store
