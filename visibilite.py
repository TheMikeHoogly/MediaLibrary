#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
La VUE par utilisateur — ce que chacun a le droit de voir
──────────────────────────────────────────────────────────

Chantier 17, étape 3 (spécifié par Mike le 26/08/2026, ROADMAP 17(a)(b)).

LA RÈGLE

Le partage se fait par DOSSIER : tout ce qui est sous `Photos <Nom>` est
partagé avec tous, SAUF le sous-dossier `PRIVE` de ce dossier, visible de
son seul propriétaire. Un `PRIVE` hors dossier propriétaire (à la racine,
dans `_A TRIER`…) n'a pas de propriétaire : il est à l'admin seul. Rien
d'autre n'est caché — pas de marquage photo par photo.

    visible(chemin, utilisateur) -> bool

LE PRIVÉ NE SE TRAHIT PAS, Y COMPRIS PAR UN COMPTEUR (17b)

Si Florine est sur une photo du `PRIVE` de Mike, sa fiche ne la compte pas
pour les autres. Tout ce qui agrège lit les magasins ; le filtre vit donc AU
MAGASIN, pas dans les routes : `brancher(store, utilisateur, ...)` fait que
`store.data` rend, pour l'utilisateur courant, une VUE en
lecture seule qui ne contient que ses clés visibles (l'admin compris). Les cent soixante-six
lectures du serveur sont couvertes sans être touchées — c'est le même geste
que `auteurs.garnir` au goulot des écritures. Les fils de fond (scan,
tagging, curateur) n'ont pas d'utilisateur courant : ils voient tout, comme
avant, et rien ne change pour eux.

Deux formes de magasin, deux filtres :
  - keyé par CHEMIN (index, visages, animaux) : la vue cache la clé ;
  - keyé par NOM (personnes, animaux nommés) : la fiche est visible, mais
    ses listes qui citent des chemins (`faces`, `exclude`, `confirmed`,
    `avatar`) sont filtrées — sinon l'avatar d'une fiche pourrait être un
    visage d'une photo privée, et une vignette est une fuite.

CE QUE LA VUE NE FAIT PAS

Elle ne sait pas QUI regarde (l'écriture sur FICHIER, elle, a sa règle plus
bas : `peut_ecrire`, étape 5) :
`utilisateur()` est fourni par le serveur (thread-local, posé par le routeur
à l'étape 4 ; None = fil de fond, pas de filtre). Elle n'est pas non plus la
preuve de non-fuite : le banc `test_visibilite.py` prouve la règle et la vue ;
la preuve sur les ROUTES (vignette, fichier, recherche) demande un serveur
avec deux comptes — étape 4.
"""

from collections.abc import Mapping
from functools import lru_cache

from auteurs import ADMIN, proprietaire_de

PRIVE = 'PRIVE'


def _segments(chemin):
    return [s for s in str(chemin or '').replace('\\', '/').split('/') if s]


@lru_cache(maxsize=262144)
def est_prive(chemin):
    """Le chemin traverse-t-il un dossier `PRIVE` (insensible à la casse) ?
    Mémoïsé : la vue le demande pour CHAQUE clé à chaque lecture agrégée."""
    c = str(chemin or '')
    if PRIVE not in c.upper():
        return False
    return any(s.strip().upper() == PRIVE for s in _segments(c))


def visible(chemin, utilisateur):
    """`utilisateur` peut-il voir cette photo ? None (fil de fond) voit tout.
    Chacun voit tout ce qui n'est pas le PRIVE d'un autre ; l'admin voit EN
    PLUS le PRIVE sans propriétaire (racine). Le PRIVE de Flo reste à Flo :
    l'admin n'est un passe-partout que là où personne n'est chez soi."""
    if not est_prive(chemin):
        return True
    if utilisateur is None:
        return True
    proprietaire = proprietaire_de(chemin)
    if proprietaire is None:
        return utilisateur == ADMIN
    return utilisateur == proprietaire


def filtre(utilisateur):
    """Le prédicat `clé -> bool` d'un utilisateur, ou None s'il voit tout."""
    if utilisateur is None:
        return None
    return lambda cle: visible(cle, utilisateur)


# ─── L'ÉCRITURE restreinte (chantier 17, étape 5 — 29/08/2026, choix de Mike :
# « chacun n'efface que ses propres photos », ROADMAP 17(d)) ─────────────────
# Le geste sur FICHIER (renommer, déplacer, effacer, créer un dossier, annuler)
# est au PROPRIÉTAIRE du dossier `Photos <Nom>` — et à l'admin, partout où il
# VOIT (le PRIVE de Flo lui reste fermé : ne pas voir, c'est ne pas toucher).
# Hors d'un dossier propriétaire (racine, `_A TRIER`, `_Uploads`), personne
# n'est chez soi : l'admin seul. Les DÉCISIONS sur une photo (confirmer,
# exclure, nommer un visage) ne passent PAS ici : elles restent arbitrées par
# `auteurs` (le propriétaire l'emporte, le perdant est `#contesté`) — juger
# une photo partagée est permis, la détruire ne l'est pas.

def peut_ecrire(chemin, utilisateur):
    """`utilisateur` peut-il toucher ce FICHIER ? None (fil de fond) : tout."""
    if utilisateur is None:
        return True
    if not visible(chemin, utilisateur):
        return False
    if utilisateur == ADMIN:
        return True
    return proprietaire_de(chemin) == utilisateur


def refus_ecriture(chemin, utilisateur):
    """None si le geste est permis ; sinon (code, message) : 404 quand la
    photo n'est pas visible (dire « interdit » dirait « ça existe »), 403
    quand elle est partagée mais n'est pas à lui."""
    if peut_ecrire(chemin, utilisateur):
        return None
    if not visible(chemin, utilisateur):
        return 404, 'Fichier introuvable.'
    proprietaire = proprietaire_de(chemin)
    if proprietaire is None:
        return 403, "Hors d'un dossier propriétaire, seul l'admin range ou efface."
    return 403, f"Cette photo est à {proprietaire} : {proprietaire} ou l'admin peuvent la déplacer ou l'effacer, pas vous."


class VueFiltree(Mapping):
    """Un dictionnaire vu à travers un prédicat sur ses clés. LECTURE SEULE :
    une écriture à travers la vue serait une écriture qui ne sait pas ce
    qu'elle cache. `len()` compte ce qui est visible — c'est le point (17b)."""

    __slots__ = ('_d', '_ok')

    def __init__(self, d, ok):
        self._d = d
        self._ok = ok

    def __getitem__(self, k):
        if not self._ok(k):
            raise KeyError(k)
        return self._d[k]

    def __contains__(self, k):
        return self._ok(k) and k in self._d

    def __iter__(self):
        return (k for k in list(self._d) if self._ok(k))

    def __len__(self):
        return sum(1 for _ in self)

    def get(self, k, default=None):
        if not self._ok(k):
            return default
        return self._d.get(k, default)

    def keys(self):
        return list(self)

    def values(self):
        return [self._d[k] for k in self]

    def items(self):
        return [(k, self._d[k]) for k in self]

    def copy(self):
        return dict(self.items())


CHAMPS_CHEMINS = ('exclude', 'confirmed')


def filtrer_fiche(fiche, ok):
    """Une COPIE de la fiche (personne/animal) sans ses citations de chemins
    invisibles. Les listes ne sont copiées que si elles changent ; `auteurs`
    n'est pas filtré (des clés, pas des vignettes ; l'étape 5 verra)."""
    if not isinstance(fiche, dict):
        return fiche
    out = None

    def touche():
        nonlocal out
        if out is None:
            out = dict(fiche)
        return out

    faces = fiche.get('faces')
    if isinstance(faces, list):
        vis = [f for f in faces if not (isinstance(f, (list, tuple)) and f and not ok(f[0]))]
        if len(vis) != len(faces):
            touche()['faces'] = vis
    for champ in CHAMPS_CHEMINS:
        L = fiche.get(champ)
        if isinstance(L, list):
            vis = [c for c in L if not (isinstance(c, str) and not ok(c))]
            if len(vis) != len(L):
                touche()[champ] = vis
    av = fiche.get('avatar')
    if isinstance(av, (list, tuple)) and av and not ok(av[0]):
        touche()['avatar'] = None
    return out if out is not None else fiche


class VueFiches(VueFiltree):
    """La vue d'un magasin keyé par NOM : toute fiche est là, filtrée."""

    __slots__ = ()

    def __getitem__(self, k):
        return filtrer_fiche(self._d[k], self._ok)

    def __contains__(self, k):
        return k in self._d

    def __iter__(self):
        return iter(list(self._d))

    def __len__(self):
        return len(self._d)

    def get(self, k, default=None):
        if k not in self._d:
            return default
        return filtrer_fiche(self._d[k], self._ok)


def brancher(store, utilisateur, par_nom=False):
    """Fait de `store.data` une VUE dès qu'il y a un utilisateur courant
    (l'admin compris : il ne voit pas le PRIVE des autres). `utilisateur` est
    un appelable (thread-local côté serveur) ; None = fil de fond, tout.
    Le magasin garde sa classe d'origine sous une sous-classe dynamique : les
    écritures (`set`, `remove_many`, `data = {}`) passent par le dictionnaire
    réel, comme avant — la vue n'est posée que sur la LECTURE de `.data`."""
    cls = type(store)
    desc = cls.__dict__.get('data') or getattr(cls, 'data', None)
    Vue = VueFiches if par_nom else VueFiltree

    def brut(self):
        if isinstance(desc, property):
            return desc.fget(self)
        return self.__dict__['data']

    def lire(self):
        d = brut(self)
        u = utilisateur()
        if u is None:
            return d
        return Vue(d, lambda cle: visible(cle, u))

    def ecrire(self, valeur):
        if isinstance(desc, property) and desc.fset:
            desc.fset(self, valeur)
        else:
            self.__dict__['data'] = valeur

    def get(self, name):
        return lire(self).get(name)

    def has(self, name):
        e = lire(self).get(name)
        return bool(e) and not (isinstance(e, dict) and e.get('failed'))

    # `get`/`has` d'un SqliteStore lisent `_d` en direct : sans ceci, une clé
    # cachée par la vue resterait lisible par `STORE.get(k)`.
    store.__class__ = type(cls.__name__, (cls,), {'data': property(lire, ecrire),
                                                 'get': get, 'has': has})
    return store
