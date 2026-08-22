#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-clé des DÉCISIONS HUMAINES quand une photo est déplacée ou renommée
──────────────────────────────────────────────────────────────────────────────

LE TROU, ET POURQUOI IL NE SE VOYAIT PAS

`server.rekey_everywhere` transporte sept magasins quand une photo change de
chemin, et quatre d'entre eux — `FACE`, `ANIMAL`, `PEOPLE`, `PETS` — passent
dans la MÊME boucle `st.rekey(old, new)`. Mais `PEOPLE` et `PETS` sont les
seuls magasins keyés par NOM et non par chemin : les chemins y vivent À
L'INTÉRIEUR de la fiche —

    faces      [[chemin, index], …]   quel VISAGE est cette personne
    exclude    [chemin, …]            « ce n'est PAS elle sur cette photo »
    confirmed  [chemin, …]            « si, c'est bien elle »
    avatar     [chemin, index]        la vignette qui la représente

`store.rekey(ancien_chemin, nouveau_chemin)` y cherche donc une entrée dont la
CLÉ serait un chemin. Il n'en trouve jamais, renvoie faux, et ne dit rien. La
boucle avait l'air de couvrir quatre magasins ; elle en couvrait deux.

CE QUE ÇA A COÛTÉ, MESURÉ AVANT LE CORRECTIF (22/08/2026)

Sur **3 364** décisions humaines, **928** pointaient vers une clé que l'index
n'a plus (596 rattachements, 249 exclusions, 83 confirmations), réparties sur
**804** clés. Le TAG survivait — il vit dans `tags` et dans le XMP du fichier —
donc la photo gardait son nom et la règle 2 tenait. Ce qui se perdait, c'est la
VÉRITÉ TERRAIN : quel visage est Flo, quelles photos ont été écartées d'un nom,
lesquelles ont été confirmées. Et une exclusion perdue, c'est un faux positif
qui revient — le mode de panne « je corrige et ça revient ».

CE MODULE EST UNE RÈGLE PURE

Il ne connaît ni store, ni base, ni verrou : il prend une fiche, rend les
CHAMPS à réassigner. C'est ce qui le rend testable sans ouvrir `photos.db`
(l'écrivain unique est le serveur) et partageable entre le serveur et un banc —
le projet a déjà payé le prix de deux implémentations d'une même règle.

L'INDEX D'UNE VIGNETTE EST CONSERVÉ, ET CE N'EST PAS UN PARI

`rekey_everywhere` déplace l'entrée de `FACE_STORE` / `ANIMAL_STORE` EN BLOC :
la liste des détections de la nouvelle clé est celle de l'ancienne, dans le même
ordre. Re-clé `[ancien, 3]` en `[nouveau, 3]` désigne donc la même vignette.

JAMAIS DE DOUBLON

Si la fiche cite déjà la cible — la photo avait été jugée sous ses deux
chemins — l'entrée re-clée fusionne au lieu de s'ajouter. Sans quoi chaque
re-clé gonflerait la vérité terrain d'un doublon, et le compte des décisions
mentirait dans le sens flatteur.
"""

CHAMPS_PHOTO = ('exclude', 'confirmed')


def _paire(x):
    """La forme `[chemin, index]` ou None. JSON rend des listes, le code du
    serveur manipule parfois des tuples : on accepte les deux."""
    if isinstance(x, (list, tuple)) and len(x) == 2 and isinstance(x[0], str):
        try:
            return x[0], int(x[1] or 0)
        except (TypeError, ValueError):
            return None
    return None


def recler_fiche(fiche, old, new):
    """(champs à réassigner, nombre de décisions re-clées).

    Ne mute RIEN : rend un dict `{champ: nouvelle valeur}`. C'est l'appelant qui
    réassigne — et c'est ce qui marque l'entrée « sale » côté store, une
    mutation en place au fond d'une liste passant sous le radar de la
    réconciliation (`store_sqlite.TrackedEntry`).

    Un `avatar` re-clé ne compte pas comme une décision : il est DÉRIVÉ (le
    curateur le recalcule), on le transporte pour ne pas laisser une vignette
    morte dans `/people`, pas parce qu'il serait un jugement.
    """
    if not isinstance(fiche, dict) or old == new:
        return {}, 0
    champs, n = {}, 0

    faces = fiche.get('faces')
    if isinstance(faces, (list, tuple)) and any(
            (_paire(x) or ('', 0))[0] == old for x in faces):
        vus, sortie = set(), []
        for x in faces:
            p = _paire(x)
            if p is None:
                sortie.append(x)
                continue
            cle, i = (new, p[1]) if p[0] == old else p
            if (cle, i) in vus:          # déjà jugé sous l'autre chemin
                continue
            vus.add((cle, i))
            sortie.append([cle, i])
            if p[0] == old:
                n += 1
        champs['faces'] = sortie

    for champ in CHAMPS_PHOTO:
        lst = fiche.get(champ)
        if not isinstance(lst, (list, tuple)) or old not in lst:
            continue
        vus, sortie = set(), []
        for x in lst:
            y = new if x == old else x
            if y in vus:
                continue
            vus.add(y)
            sortie.append(y)
        champs[champ] = sortie
        n += 1

    av = _paire(fiche.get('avatar'))
    if av and av[0] == old:
        champs['avatar'] = [new, av[1]]

    return champs, n


def appliquer(fiche, old, new):
    """Version qui MUTE la fiche et rend le nombre de décisions re-clées.

    Réservée aux appelants qui possèdent déjà la fiche et savent la sauver.
    """
    champs, n = recler_fiche(fiche, old, new)
    for c, v in champs.items():
        fiche[c] = v
    return n
