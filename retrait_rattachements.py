#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Retrait des rattachements qu'un HUMAIN a jugés faux
──────────────────────────────────────────────────────────────────────────────

D'OÙ VIENT CE GESTE

`recale_rattachements` remet un couple `[photo, index]` sur le bon visage
quand elle en est sûre, et REFUSE dès qu'elle ne l'est pas. Ce qu'elle refuse
ne se tranche qu'à l'œil : la page `/residu` les montre, un humain répond, et
`mesure_rattachements.py --bilan-residu` en tire le plan. Ce module applique
ce plan — et rien d'autre.

CE N'EST PAS UN RECALAGE, C'EST UNE SUPPRESSION

Un recalage déplace une décision humaine ; un retrait l'efface. La différence
gouverne tout le reste : rien ne part sans un verdict EXPLICITE portant sur ce
couple précis, la quarantaine est écrite AVANT, et l'annulation refuse de
passer sur une fiche modifiée depuis.

TROIS POPULATIONS QUI NE SE MÉLANGENT JAMAIS

  * **à retirer** — le couple est cité par la fiche, et l'humain a dit que ce
    visage n'est PAS cette personne.
  * **confirmé** — cité et reconnu. Rien à faire : c'est de la vérité terrain
    gagnée, pas un geste.
  * **à ajouter** — reconnu mais NON cité. C'est une ATTRIBUTION, un autre
    geste, un autre risque. Le plan de retrait ne les touche pas et les
    compte à part : les fondre ici ferait poser un nom sous couvert de
    réparation.

MODULE PUR

Ni store, ni base, ni verrou, ni numpy : il reçoit les cas, les verdicts, et
une fiche. C'est ce qui le rend testable sans ouvrir `photos.db` (le serveur
est l'écrivain unique) et partageable entre le serveur et le banc — l'aperçu
et l'application sont le MÊME appel, donc l'aperçu ne peut pas mentir.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.
"""

# Le seul verdict qui autorise un geste. « indecidable » n'en autorise aucun,
# et c'est le point : un doute humain n'est pas un feu vert faible, c'est un
# refus.
VERDICT_AGISSANT = 'juge'


def _paire(x):
    if isinstance(x, (list, tuple)) and len(x) == 2:
        try:
            return (x[0], int(x[1] or 0))
        except (TypeError, ValueError):
            return None
    return None


def identite(key, person):
    """Même identité que la page : la photo ET la personne."""
    return f"{key}|{person}"


def plan_depuis_verdicts(cas, verdicts):
    """Le plan, lu dans les verdicts. Ne mute rien, ne suppose rien.

    Un cas sans verdict, ou jugé « indecidable », ne produit AUCUN geste — il
    se compte, pour que le total dise toujours ce qui a été laissé de côté.
    Un visage nommé dans `oui` mais absent des candidats du cas est ignoré :
    un verdict ne porte que sur ce qui a été montré.
    """
    verdicts = verdicts or {}
    retraits, ajouts = [], []
    comptes = {'cas': 0, 'juges': 0, 'indecidables': 0, 'non_juges': 0,
               'a_retirer': 0, 'confirmes': 0, 'a_ajouter': 0,
               'photos_sans_personne': 0}
    for k in (cas or []):
        comptes['cas'] += 1
        person, cle = k.get('person', ''), k.get('key', '')
        v = verdicts.get(identite(cle, person))
        if not v:
            comptes['non_juges'] += 1
            continue
        if v.get('verdict') != VERDICT_AGISSANT:
            comptes['indecidables'] += 1
            continue
        comptes['juges'] += 1
        offerts = set()
        cites = set()
        for d in (k.get('candidats') or []):
            try:
                i = int(d.get('i'))
            except (TypeError, ValueError):
                continue
            offerts.add(i)
            if d.get('cite'):
                cites.add(i)
        oui = {int(x) for x in (v.get('oui') or [])
               if isinstance(x, int) or str(x).lstrip('-').isdigit()}
        oui &= offerts
        for i in sorted(cites - oui):
            comptes['a_retirer'] += 1
            retraits.append({'person': person, 'key': cle, 'i': i})
        comptes['confirmes'] += len(cites & oui)
        for i in sorted(oui - cites):
            comptes['a_ajouter'] += 1
            ajouts.append({'person': person, 'key': cle, 'i': i})
        if cites and not (cites & oui):
            comptes['photos_sans_personne'] += 1
    return {'retraits': retraits, 'ajouts': ajouts, 'comptes': comptes}


def retirer_de_la_fiche(fiche, couples):
    """Rend `{champ: nouvelle valeur}` — ou `{}` si rien ne bouge.

    Ne touche QUE `faces`. `exclude` et `confirmed` sont keyés par photo, pas
    par visage : ils ne peuvent pas porter un décalage d'index, et les toucher
    ici effacerait une décision que personne n'a jugée. `avatar` est DÉRIVÉ —
    le curateur le recalcule ; s'il désignait le visage retiré, il se refera.

    Un couple déjà absent n'est pas une erreur : deux applications de suite
    doivent donner le même état, sinon le bouton « Appliquer » devient un
    piège. Il se compte en `deja_absents`.
    """
    if not isinstance(fiche, dict):
        return {}, {'retires': 0, 'deja_absents': 0}
    faces = fiche.get('faces')
    if not isinstance(faces, (list, tuple)):
        return {}, {'retires': 0, 'deja_absents': len(couples or ())}
    vises = set()
    for c in (couples or ()):
        p = _paire([c.get('key'), c.get('i')] if isinstance(c, dict) else c)
        if p:
            vises.add(p)
    if not vises:
        return {}, {'retires': 0, 'deja_absents': 0}
    sortie, retires = [], 0
    for x in faces:
        p = _paire(x)
        if p is not None and p in vises:
            retires += 1
            continue
        sortie.append(x)
    if not retires:
        return {}, {'retires': 0, 'deja_absents': len(vises)}
    return ({'faces': sortie},
            {'retires': retires, 'deja_absents': max(0, len(vises) - retires)})


def par_fiche(retraits):
    """Les retraits regroupés par nom de fiche, en minuscules (clé du store)."""
    out = {}
    for r in (retraits or ()):
        out.setdefault(str(r.get('person', '')).lower(), []).append(r)
    return out
