#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recalage des RATTACHEMENTS dont l'index a glissé
──────────────────────────────────────────────────────────────────────────────

LE DÉFAUT, ET COMMENT IL S'EST FAIT VOIR

Un rattachement est un couple `[photo, index du visage]`. L'index désigne une
POSITION dans `FACE_STORE[photo]['faces']`. Or `reembed_one_batch` REMPLACE
cette liste (`e['faces'] = newfaces`) quand il ré-analyse une photo : l'ordre
et le nombre changent. Le couple survit, sa cible non — et sur une photo de
groupe, l'index de Didier finit par désigner quelqu'un d'autre qui est sur la
même photo.

Le 22/08, Mike l'a vu à l'œil : une planche « visages déjà confirmés de
Didier » contenant Laura Waller, une de Mathieu contenant Mathilde. Mesuré
ensuite (`mesure_rattachements.py`) sur 1 194 couples : **42 décalés**, dont
**41 sur des photos réellement re-détectées** — 5,4 % là-bas contre 0,4 %
ailleurs. Le garde-fou `assigned_keys` de `reembed_one_batch` protège
désormais l'avenir ; il n'a jamais réparé le passé, et il ne lit pas `PETS`.

CE QUI REND LE RECALAGE POSSIBLE — ET CE QUI L'INTERDIT

Le bon index est MESURABLE : c'est le visage de la MÊME photo qui ressemble le
plus à la signature de la personne. Ce n'est pas une devinette, c'est la même
comparaison que celle qui a servi à trouver le défaut.

Mais un recalage déplace une DÉCISION HUMAINE. La règle refuse donc de bouger
dès qu'elle n'est pas sûre, et chaque refus porte un nom :

  * **écart insuffisant** — l'autre visage ne fait pas nettement mieux. Deux
    visages proches (fratrie, même personne détectée deux fois) ne prouvent
    rien, et trancher au hasard serait pire que ne rien faire.
  * **sous le plancher** — le meilleur visage de la photo ne ressemble à
    personne. On ne déplace pas un jugement vers un inconnu ; ce couple-là
    relève d'un retrait, pas d'un recalage, et c'est un autre geste.
  * **déjà pris** — le visage visé est déjà rattaché à QUELQU'UN D'AUTRE. Le
    recaler ferait deux personnes sur un seul visage : un conflit muet vaut
    moins qu'un décalage visible.
  * **ambigu** — la fiche cite cette photo plusieurs fois (la personne y est
    détectée deux fois). Recaler chaque couple vers le même meilleur visage
    les écraserait l'un l'autre. On passe, et on le dit.

CE MODULE EST UNE RÈGLE PURE

Il ne connaît ni store, ni base, ni verrou, ni numpy : il reçoit une fiche et
les SCORES déjà calculés de chaque visage de chaque photo, et rend les CHAMPS à
réassigner. C'est ce qui le rend testable sans ouvrir `photos.db` (l'écrivain
unique est le serveur) et partageable entre le serveur et un banc — le projet a
déjà payé deux fois le prix de deux implémentations d'une même règle.

APERÇU ET APPLICATION SONT LA MÊME FONCTION

`recaler_fiche` ne mute rien : l'aperçu montre exactement ce que l'application
fera, parce que c'est le même appel. Un aperçu calculé à part serait un aperçu
qui ment le jour où les deux dérivent.

JAMAIS DE DOUBLON

Si la fiche cite déjà la cible, le couple recalé FUSIONNE au lieu de s'ajouter
— sinon chaque recalage gonflerait la vérité terrain d'un doublon, et le compte
des décisions mentirait dans le sens flatteur (leçon du re-clé du 22/08).
"""

# Le meilleur visage doit dépasser le désigné d'AU MOINS ça. Même valeur que le
# banc qui a trouvé le défaut : deux seuils portant la même intention finissent
# par diverger.
ECART_MIN = 0.10
# Sous ce score, le meilleur visage de la photo ne ressemble à personne — c'est
# `CUR_FP_SIM`, le seuil auquel le curateur déclare déjà un faux positif.
PLANCHER = 0.30


def _paire(x):
    """La forme `[chemin, index]`, ou None. JSON rend des listes, le serveur
    manipule parfois des tuples : on accepte les deux."""
    if isinstance(x, (list, tuple)) and len(x) == 2 and isinstance(x[0], str):
        try:
            return x[0], int(x[1] or 0)
        except (TypeError, ValueError):
            return None
    return None


def meilleur_visage(scores):
    """(index, score) du meilleur visage d'une photo, ou (None, None).

    `scores` est la liste des similarités à la signature, `None` pour un visage
    sans vecteur. Un seul endroit décide de ce qu'est « le meilleur ».
    """
    meilleur, quel = None, None
    for j, s in enumerate(scores or ()):
        if s is None:
            continue
        if meilleur is None or s > meilleur:
            meilleur, quel = s, j
    return quel, meilleur


def recaler_fiche(fiche, scores_par_photo, ecart=ECART_MIN, plancher=PLANCHER,
                  deja_pris=None):
    """(champs à réassigner, recalages, refus).

    `scores_par_photo` : {chemin: [score du visage 0, 1, …]} — l'appelant les
    calcule, la règle ne connaît pas les vecteurs. Une photo absente de ce dict
    est une photo qu'on ne sait pas juger : on n'y touche JAMAIS.

    `deja_pris` : {(chemin, index): nom} des visages rattachés à quelqu'un.
    Le nom de la fiche courante y est ignoré (c'est elle qui les possède).

    Ne mute rien : rend `{champ: nouvelle valeur}`. C'est l'appelant qui
    réassigne — et c'est ce qui marque l'entrée « sale » côté store, une
    mutation en place au fond d'une liste passant sous le radar de la
    réconciliation (`store_sqlite.TrackedEntry`).
    """
    if not isinstance(fiche, dict):
        return {}, [], []
    faces = fiche.get('faces')
    if not isinstance(faces, (list, tuple)):
        return {}, [], []
    moi = str(fiche.get('name') or '').lower()
    pris = deja_pris or {}

    # Une photo citée plusieurs fois par la MÊME fiche est ambiguë : recaler
    # chacun de ses couples vers le même meilleur visage les écraserait.
    # (couples DISTINCTS : un doublon exact n'est pas une ambiguite, c'est un
    # doublon, et il ne doit pas faire refuser le recalage de son jumeau.)
    couples = {p for p in (_paire(x) for x in faces) if p}
    combien = {}
    for cle_p, _i in couples:
        combien[cle_p] = combien.get(cle_p, 0) + 1

    recalages, refus = [], []
    vus, sortie, bouge = set(), [], False
    for x in faces:
        p = _paire(x)
        if p is None:
            sortie.append(x)
            continue
        cle, i = p
        scores = scores_par_photo.get(cle)
        cible = i
        if scores is not None:
            j, s_best = meilleur_visage(scores)
            s_i = scores[i] if 0 <= i < len(scores) else None
            if j is None:
                pass                                   # aucun vecteur : muet
            elif combien.get(cle, 0) > 1:
                refus.append({"key": cle, "i": i, "pourquoi": "ambigu"})
            elif j == i:
                pass                                   # deja le meilleur
            elif s_best < plancher:
                refus.append({"key": cle, "i": i, "pourquoi": "sous_le_plancher",
                              "sim_vers": s_best})
            elif s_i is not None and (s_best - s_i) < ecart:
                refus.append({"key": cle, "i": i, "pourquoi": "ecart_insuffisant",
                              "sim": s_i, "sim_vers": s_best})
            elif str(pris.get((cle, j), '')).lower() not in ('', moi):
                refus.append({"key": cle, "i": i, "pourquoi": "deja_pris",
                              "par": pris.get((cle, j)), "sim_vers": s_best})
            else:
                cible = j
                recalages.append({"key": cle, "de": i, "vers": j,
                                  "sim": s_i, "sim_vers": s_best,
                                  "hors_bornes": s_i is None})
        if cible != i and (cle, cible) in vus:
            # Le recalage tombe sur une entrée que la fiche cite déjà : on
            # FUSIONNE au lieu d'ajouter. Un doublon PRÉEXISTANT, lui, est
            # laissé tel quel — le retirer ici ferait maigrir la vérité
            # terrain sans que ce soit un recalage, et le compte mentirait.
            recalages[-1]["fusion"] = True
            bouge = True
            continue
        vus.add((cle, cible))
        sortie.append([cle, cible])
        if cible != i:
            bouge = True

    champs = {}
    if bouge:
        champs['faces'] = sortie

    # L'avatar est DÉRIVÉ (le curateur le recalcule), mais un avatar décalé se
    # VOIT dans /people et dans la planche de /tranche : on le recale aussi,
    # sous les mêmes conditions, sans le compter comme une décision.
    av = _paire(fiche.get('avatar'))
    if av:
        scores = scores_par_photo.get(av[0])
        if scores is not None:
            j, s_best = meilleur_visage(scores)
            s_i = scores[av[1]] if 0 <= av[1] < len(scores) else None
            if (j is not None and j != av[1] and s_best >= plancher
                    and (s_i is None or (s_best - s_i) >= ecart)):
                champs['avatar'] = [av[0], j]

    return champs, recalages, refus


def appliquer(fiche, scores_par_photo, ecart=ECART_MIN, plancher=PLANCHER,
              deja_pris=None):
    """Version qui MUTE la fiche. Rend (recalages, refus).

    Réservée aux appelants qui possèdent déjà la fiche et savent la sauver.
    """
    champs, recalages, refus = recaler_fiche(
        fiche, scores_par_photo, ecart, plancher, deja_pris)
    for c, v in champs.items():
        fiche[c] = v
    return recalages, refus


def photos_citees(fiche):
    """Les chemins qu'une fiche cite — dans `faces` et dans `avatar`.

    L'appelant s'en sert pour ne calculer des scores que là où c'est utile :
    une fiche cite quelques dizaines de photos, pas les 42 000 du fonds.
    """
    out = set()
    if not isinstance(fiche, dict):
        return out
    for x in (fiche.get('faces') or ()):
        p = _paire(x)
        if p:
            out.add(p[0])
    av = _paire(fiche.get('avatar'))
    if av:
        out.add(av[0])
    return out


def rattachements_pris(fiches):
    """{(chemin, index): nom} — qui possède déjà quel visage.

    `fiches` est un itérable de dicts de fiches. Sert de garde-fou « déjà
    pris » : sans lui, un recalage peut poser deux personnes sur un visage.
    """
    out = {}
    for fiche in fiches:
        if not isinstance(fiche, dict):
            continue
        nom = fiche.get('name')
        if not nom:
            continue
        for x in (fiche.get('faces') or ()):
            p = _paire(x)
            if p:
                out.setdefault(p, nom)
    return out
