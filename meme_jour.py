#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moteur « même jour, autres années » — pur, testable hors serveur.

Rassemble les photos qui partagent le même **mois-jour** (un 14 août, toutes
années confondues). Zéro IA, zéro GPU, zéro accès NAS : tout se lit dans
l'index déjà en mémoire.

INVARIANT DU CHANTIER — **dates PRÉCISES uniquement.** Le repli « année du
dossier » de `server._best_time` place la photo au 1ᵉʳ janvier à midi ; le
prendre pour une date de prise de vue rassemblerait des milliers de photos sous
un 1ᵉʳ janvier qui n'a jamais existé. Une photo sans date précise n'appartient
donc à AUCUN jour — elle est absente de l'index, jamais rangée par défaut.
Deux sources précises, et deux seulement (mêmes que la branche 1 de
`_best_time`) : la date EXIF sauvegardée (`taken`) et la date lue dans le NOM
du fichier ; on garde la plus ancienne, parce qu'une date de MODIFICATION
faussée par le tagging est toujours postérieure à la prise de vue.

Les epochs du projet sont produits par `time.mktime` (heure LOCALE) : le
mois-jour se relit donc avec `time.localtime`, jamais `gmtime` — sinon une
photo prise à 00h30 en été bascule la veille.

Le module ne connaît ni STORE ni server : `epoch_precis` reçoit son lecteur de
date de nom de fichier en paramètre (`server._fname_time`), ce qui garde une
seule implémentation de cette règle dans le projet.
"""

import re
import time

# Accentué : ce libellé est montré à l'humain (« 14 août »), contrairement à
# tagging_meta.MOIS_FR qui alimente des faits/prompts et reste sans accents.
MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
           'août', 'septembre', 'octobre', 'novembre', 'décembre']

RE_JOUR = re.compile(r'^(\d{2})-(\d{2})$')

ANNEE_MIN, ANNEE_MAX = 1990, 2100


def epoch_precis(cle, entree, fname_time, credible=None):
    """Date de prise de vue PRÉCISE (au jour près) d'une photo, ou None.

    `fname_time` : callable nom_de_fichier -> epoch|None (server._fname_time).
    JAMAIS le repli « année du dossier » : voir l'en-tête du module.

    `credible` : callable (clé, epoch) -> bool, injecté comme `fname_time` pour
    qu'il n'existe qu'UNE implémentation de la règle dans le projet. Le serveur
    passe `faits_vue.date_credible`, qui écarte la date du SCAN — le numériseur
    l'inscrit dans `DateTimeOriginal` **et** dans le nom, donc les DEUX sources
    doivent y passer (72 photos, mesurées le 19/08). `None` = tout est cru,
    comportement d'avant le 19/08."""
    precises = []
    t = entree.get('taken') if isinstance(entree, dict) else None
    if isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0:
        precises.append(float(t))
    try:
        fn = fname_time(str(cle).replace('\\', '/').rsplit('/', 1)[-1])
    except Exception:                                         # noqa: BLE001
        fn = None
    if isinstance(fn, (int, float)) and fn > 0:
        precises.append(float(fn))
    if credible is not None:
        precises = [e for e in precises if credible(cle, e)]
    return min(precises) if precises else None


def cle_jour(epoch):
    """epoch local -> « MM-JJ », ou None si l'epoch est inexploitable."""
    try:
        t = time.localtime(float(epoch))
    except (ValueError, TypeError, OverflowError, OSError):
        return None
    if not (ANNEE_MIN <= t.tm_year <= ANNEE_MAX):
        return None
    return '%02d-%02d' % (t.tm_mon, t.tm_mday)


def annee_de(epoch):
    """Année (int) d'un epoch local, ou 0."""
    try:
        return time.localtime(float(epoch)).tm_year
    except (ValueError, TypeError, OverflowError, OSError):
        return 0


def jour_demande(param):
    """Normalise le paramètre reçu par /api/jour et /files?jour= :
    « 08-14 » tel quel, ou None si ce n'est pas un jour (l'appelant traitera
    alors le paramètre comme une CLÉ de photo). Un 02-30 est refusé ici : il ne
    peut correspondre à aucune photo, autant le dire tout de suite."""
    m = RE_JOUR.match(str(param or '').strip())
    if not m:
        return None
    mois, jour = int(m.group(1)), int(m.group(2))
    if not (1 <= mois <= 12 and 1 <= jour <= 31):
        return None
    if jour > (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[mois - 1]:
        return None
    return '%02d-%02d' % (mois, jour)


def construire_index(entrees, fname_time, credible=None):
    """{« MM-JJ » : [(epoch, clé), …]} — chaque liste triée du plus ANCIEN au
    plus récent. `entrees` : itérable (clé, entrée) — typiquement
    `STORE.data.items()`. Les entrées `failed` et celles sans date précise sont
    ignorées (voir l'invariant du module).

    `credible` : passé tel quel à `epoch_precis` — l'index du jour doit écarter
    la date du SCAN comme le reste, sinon une photo de 1985 numérisée en 2006
    revient hanter un « 1er juin » où elle n'a jamais été prise."""
    index = {}
    for cle, entree in entrees:
        if not isinstance(entree, dict) or entree.get('failed'):
            continue
        ep = epoch_precis(cle, entree, fname_time, credible)
        if ep is None:
            continue
        j = cle_jour(ep)
        if j is None:
            continue
        index.setdefault(j, []).append((ep, cle))
    for lst in index.values():
        lst.sort(key=lambda it: it[0])
    return index


def photos_du_jour(index, jour, exclure=None):
    """[(epoch, clé)] du jour, du plus ancien au plus récent, la photo de
    référence retirée. Toutes les années sont gardées, y compris celle de la
    référence (choix tranché le 14/08 : ne rien cacher — l'après-midi du même
    mariage a autant sa place que le 14 août 2011)."""
    items = index.get(jour) or []
    if exclure is None:
        return list(items)
    return [it for it in items if it[1] != exclure]


def grouper_par_annee(items):
    """[(année, [(epoch, clé), …]), …] trié par année CROISSANTE — l'ordre du
    récit familial, du plus ancien au plus récent, comme la planche contact."""
    par_an = {}
    for ep, cle in items:
        an = annee_de(ep)
        if an:
            par_an.setdefault(an, []).append((ep, cle))
    return [(an, par_an[an]) for an in sorted(par_an)]


def libelle_jour(jour):
    """« 08-14 » -> « 14 août ». Déterministe, sans locale (strftime('%B')
    dépend du poste et '%-d' n'existe pas sous Windows)."""
    j = jour_demande(jour)
    if not j:
        return ''
    mois, num = int(j[:2]), int(j[3:])
    return '%d %s' % (num, MOIS_FR[mois - 1])
