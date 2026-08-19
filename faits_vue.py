#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faits_vue — les `faits` d'une photo, calculés À LA DEMANDE
──────────────────────────────────────────────────────────────────────────────

POURQUOI CE MODULE EXISTE

`faits` est le germe de la mémoire familiale à provenance : chaque fait
(personne, animal, espèce, lieu, date) porte sa SOURCE. Il n'est écrit
aujourd'hui que par le worker de tagging, en aval du VLM — 81 entrées sur
43 064. La tentation évidente est un backfill : écrire une fois le champ pour
tout le fonds. Deux constats l'interdisent, et ce sont eux qui ont fait naître
ce module :

1. **`faits` est un INSTANTANÉ, pas une vue.** Sur les 81 déjà pourvues, 12
   divergent DÉJÀ de ce que dit l'index : des noms écrits en juin, retirés
   depuis. Un champ figé se périme à la première correction humaine — et le
   coût de la péremption est exactement l'invariant sacré du projet (un nom
   humain qui réapparaît après avoir été retiré est une régression, pas un
   retard d'actualisation). Un backfill ne corrige pas ce défaut : il le
   multiplie par 43 064.

2. **Le lieu ne doit pas venir du miroir du RENOMMAGE.**
   `renommage_facts.resolve_path_place` teste une SOUS-CHAÎNE : « Ins » se
   trouve dans « Cousins&Cousines » (442 photos), « Orbe » dans « Vallorbe »
   (13). La règle du Knowledge Builder compare des SEGMENTS ENTIERS de chemin
   et n'a pas ce défaut. C'est elle qui vit ici — et c'est `server` qui lui
   délègue, pour qu'il n'existe qu'UNE règle et non deux qui se ressemblent
   (`eval/METHODE.md`, 14/08 : un banc qui RECOPIE la prod mesure autre chose
   qu'elle ; il doit l'IMPORTER).

CE QUE LE MODULE GARANTIT

- **Pur** : aucune I/O, aucun accès NAS, aucun modèle, aucun import lourd. Tout
  entre par les paramètres (index, caches de lieux, racines média, détections).
  Testable sans serveur, importable par un banc, appelable dans une boucle.
- **Aucun fichier rouvert** : la source des noms est donc `index`, JAMAIS `xmp`.
  Écrire `xmp` ferait porter au fait la provenance d'une lecture qui n'a pas eu
  lieu, et toute la valeur du champ tombe.
- **La date ne tombe jamais sur `mtime`** (décision du 15/08 : le tagging de
  2026 a réécrit une photo de 1998). Ordre : `taken` → date lue dans le NOM →
  année du DOSSIER, puis plus rien.

LA SOURCE DES NOMS, ET POURQUOI ELLE EST UN PARAMÈTRE

`noms_attendus` est la seule entrée que l'appelant doit fabriquer : la liste des
tags `personne:`/`animal:` qui font AUTORITÉ maintenant. En prod c'est
`server._noms_attendus(cle)` — fiches personnes/animaux (`faces`) fusionnées
avec l'index, `exclude` faisant autorité partout. C'est précisément cette
fusion qui rend les 12 divergences impossibles : un nom retiré ne peut pas
revenir. Passé `None`, on retombe sur les seuls mots-clés de l'entrée d'index
(ce que ferait un backfill) — utile pour MESURER l'écart entre les deux, pas
pour servir l'utilisateur.
"""

import re

import tagging_meta
from renommage_facts import (_sans_accents, fname_datetime, names_from_entry,
                             path_year)

__all__ = ['chemin_relatif', 'lieu_plausible', 'lieu_par_segments', 'lieu_pour',
           'epoch_du_nom', 'date_et_source', 'assertions', 'faits']


# Dossiers qui ne sont jamais des lieux (miroir : `server._LIEUX_BRUIT`).
LIEUX_BRUIT = re.compile(
    r'^(?:\d+|camera|dcim|photos?|images?|divers|screenshots?|whatsapp'
    r'|samsung|iphone|xiaomi|huawei|pixel|sauvegardes?|export\w*)$', re.I)


# ─────────────────────────────── chemin ───────────────────────────────

def chemin_relatif(cle, racines=()):
    """Chemin PRIVÉ de sa racine média.

    Indispensable : le NAS s'appelle « NAS-Bremblens », donc chercher le lieu
    « Bremblens » dans le chemin complet remonte les 30 682 photos. Le nom du
    serveur n'est pas un lieu photographié.

    `racines` : les racines de `media_roots()`, DÉJÀ calculées — dans l'ordre,
    la plus spécifique d'abord (Uploads avant le dossier qui la contient). Ce
    sont des DONNÉES, pas de la logique : le module ne lit aucun fichier de
    configuration et ne state aucun dossier (64 k appels à `is_dir()` sur SMB
    bloquent l'API plusieurs minutes — audit O3). Chaque élément est un chemin,
    ou le couple `(libellé, chemin)` que rend `media_roots()` — l'appelant n'a
    rien à reformater pour appeler la règle."""
    s = str(cle)
    bas = s.lower().replace('/', '\\')
    for racine in racines:
        if isinstance(racine, (tuple, list)) and len(racine) == 2:
            racine = racine[1]
        r = str(racine).lower().replace('/', '\\').rstrip('\\')
        if r and bas.startswith(r):
            return s[len(r):]
    return s


def lieu_plausible(nom):
    """Un dossier est-il un nom de lieu ? Heuristique, corrigeable à la main."""
    n = re.sub(r'^\d{2,8}[-_ ]*', '', str(nom)).strip()      # « 240211_… »
    n = re.sub(r'\b(19|20)\d{2}\b', '', n).strip()           # année
    n = re.sub(r'^\d{1,2}[ .\-]+', '', n).strip()            # « 07 Voyage… »
    if len(n) < 4 or LIEUX_BRUIT.match(n):
        return None
    mots = [m for m in re.split(r'[\s_\-]+', n) if len(m) > 2
            and not LIEUX_BRUIT.match(m)]
    return ' '.join(mots) if mots else None


def lieu_par_segments(cle, lieux, racines=()):
    """Lieu déduit du CHEMIN, segment par segment — la règle du Knowledge
    Builder, et la seule qu'on veuille.

    Le dossier le plus PROFOND gagne (parcours en sens inverse) : « Photos /
    Espagne / Barcelone » est une photo de Barcelone. Chaque segment est
    d'abord nettoyé (`lieu_plausible`), puis cherché dans `lieux` — un DICT :
    la comparaison est une clé, donc un MOT ENTIER. C'est toute la différence
    avec `renommage_facts.resolve_path_place`, qui teste `norm in dossier` et
    trouve « Ins » dans « Cousins&Cousines ».

    `lieux` : {libellé sans accents: libellé} — `server.lieux_connus()` ou
    `renommage_facts.load_lieux(...)`, c'est le même fichier."""
    if not lieux:
        return None
    parts = chemin_relatif(cle, racines).replace('/', '\\').split('\\')[:-1]
    for p in reversed(parts):
        lieu = lieu_plausible(p)
        if not lieu:
            continue
        # Le segment entier d'abord, puis ses mots longs : « Vacances Crete »
        # doit rendre « Crète », mais on ne descend pas sous 5 lettres — un
        # mot court noie le chemin de faux positifs.
        for cand in [lieu] + [m for m in lieu.split() if len(m) >= 5]:
            if _sans_accents(cand) in lieux:
                return lieux[_sans_accents(cand)]
    return None


def lieu_pour(cle, lieux=None, racines=(), gps_place=None):
    """(libellé, source) du lieu. Le GPS précalculé prime sur le chemin : 6 595
    photos ont un `gps_place` que leur dossier ignore (décision du 15/08).
    Renvoie (None, None) si rien."""
    if gps_place:
        return gps_place, 'gps'
    lieu = lieu_par_segments(cle, lieux or {}, racines)
    return (lieu, 'chemin') if lieu else (None, None)


# ──────────────────────────────── date ────────────────────────────────

def epoch_du_nom(cle):
    """Epoch de la date lue dans le NOM du fichier, ou None. Passe par
    `renommage_facts.fname_datetime` : miroir déclaré de `server._fname_time`,
    une seule règle pour la prod et pour les bancs."""
    import time
    nom = str(cle).replace('\\', '/').rsplit('/', 1)[-1]
    d8, hms = fname_datetime(nom)
    if not d8:
        return None
    h, m, s = (int(hms[0:2]), int(hms[2:4]), int(hms[4:6])) if hms else (12, 0, 0)
    try:
        return time.mktime((int(d8[0:4]), int(d8[4:6]), int(d8[6:8]),
                            h, m, s, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


def date_et_source(cle, entree):
    """(libellé, source) de la date : `taken` (exif) → date lue dans le NOM →
    année du DOSSIER. **Jamais le `mtime`** — il porte la date du TAGGING, pas
    celle de la prise de vue (une photo de 1998 réécrite en 2026). Une date
    fausse affirmée est une graine d'hallucination, pas un fait : mieux vaut
    rien."""
    t = entree.get('taken') if isinstance(entree, dict) else None
    if isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0:
        return tagging_meta.format_date_fr(t), 'exif'
    fn = epoch_du_nom(cle)
    if fn:
        return tagging_meta.format_date_fr(fn), 'nom du fichier'
    an = path_year(cle)                  # rend « YYYY » (chaîne), pas un epoch
    if an:
        return str(an), 'annee du dossier'
    return None, None


# ─────────────────────────────── la vue ───────────────────────────────

def assertions(cle, entree, especes=None, gps_place=None, lieux=None,
               racines=(), noms_attendus=None):
    """Dict d'assertions attendu par `tagging_meta.faits_structures`, assemblé
    depuis la SEULE mémoire.

    `noms_attendus` : les tags qui font AUTORITÉ maintenant (voir l'en-tête du
    module). `None` = repli sur les mots-clés de l'entrée d'index."""
    kw = noms_attendus if noms_attendus is not None else names_from_entry(entree)
    persons, animals = tagging_meta.noms_depuis_kw(kw)
    lieu, lieu_src = lieu_pour(cle, lieux, racines, gps_place)
    date_txt, date_src = date_et_source(cle, entree)
    return {'key': cle, 'persons': persons, 'animals': animals,
            'species': sorted(especes or []),
            'lieu': lieu, 'lieu_src': lieu_src,
            'date': date_txt, 'date_src': date_src,
            'noms_src': 'index'}


def faits(cle, entree, **kw):
    """Liste de faits [{'t','v','src'}] d'une photo — la VUE. Même forme que le
    champ `faits` écrit par le worker de tagging, produite par la MÊME fonction
    (`tagging_meta.faits_structures`), mais recalculée, donc jamais périmée."""
    return tagging_meta.faits_structures(assertions(cle, entree, **kw))
