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

Depuis le 18/09 (chantier 19, brique 4), être RECONNU sur une photo la
rouvre : si `personne:Flo` y est, Flo la voit même quand son propriétaire ne
partage pas avec elle. C'est le seul contrepoids du chantier, et il n'agit
que sur le PARTAGE — jamais sur un masque.

Depuis le 18/09 (chantier 19, brique 5), la visibilité n'est plus seulement
une propriété du CHEMIN : chacun choisit qui voit ses photos
(`partage_ferme`). L'admin n'y est PAS un passe-partout — c'est un choix
humain, comme le PRIVE.

Depuis le 18/09 (chantier 19, brique 3), une PERSONNE reconnue sur une photo
peut la masquer sans qu'elle bouge : restent le propriétaire, elle, et
l'admin. C'est le premier masque que quelqu'un pose sur le fichier d'un
AUTRE — d'où `peut_lever`, qui ne rend la clé qu'à elle.

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

import threading

from collections.abc import Mapping
from functools import lru_cache

from auteurs import ADMIN, proprietaire_de

PRIVE = 'PRIVE'

# Chantier 18 (spec tranchée par Mike le 06/09, `eval/DECISIONS.md`). Une photo
# que le tagueur soupçonne de porter un document sensible est MASQUÉE sans être
# DÉPLACÉE : le modèle a manqué 4 des 6 vrais documents de l'échantillon et en a
# inventé 2, et muter l'archive une fois sur trois sur la foi d'un tel verdict
# n'est pas un geste qu'on rattrape. L'état vit en BASE et jamais dans le XMP
# (18c) : un verdict de machine ne se grave pas dans le fichier de quelqu'un.
SENSIBLE_EN_ATTENTE = 'en_attente'   # détecté, masqué, attend le verdict humain
SENSIBLE_NON = 'non'                 # jugé « pas sensible » — mémorisé, plus jamais


def sensible_de(entree):
    """L'axe `sensible` d'une entrée d'index, ou '' — règle PURE (pas de I/O)."""
    if not isinstance(entree, dict):
        return ''
    v = entree.get('sensible')
    return v if isinstance(v, str) else ''


def en_attente(entree):
    """Cette entrée est-elle masquée en attendant un verdict humain ?

    Écrite sans passer par `sensible_de` (11/09) : la vue la demande pour
    CHAQUE clé de chaque lecture agrégée. Même réponse — une valeur égale à
    `'en_attente'` est une chaîne, et une entrée qui n'est pas un dict n'a pas
    d'axe (`test_vue_rapide.py` le tient contre l'écriture d'avant)."""
    return isinstance(entree, dict) and entree.get('sensible') == SENSIBLE_EN_ATTENTE


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


def cible_prive(rel):
    """Le dossier PRIVE ou ranger cette photo, en chemin RELATIF a sa racine
    -- ou (None, raison) quand le geste n'a pas de sens. Regle pure.

    « Rendre une photo privee, c'est la deplacer » (17a) : le geste en un clic
    a donc besoin d'UNE destination evidente, et d'une seule. C'est le `PRIVE`
    du dossier de son PROPRIETAIRE (`Photos Mike/PRIVE`), jamais un PRIVE
    invente ailleurs : a la racine, dans `_A TRIER` ou `_Uploads`, personne
    n'est chez soi -- il n'y a pas de chez-soi ou mettre la photo, et le dire
    vaut mieux qu'en fabriquer un.

    Rend (dossier_relatif, None) si le geste est possible,
    (None, raison) sinon -- deja privee, ou hors dossier proprietaire."""
    segs = _segments(rel)
    if not segs:
        return None, 'Chemin vide.'
    if est_prive(rel):
        return None, 'Cette photo est deja dans un dossier prive.'
    for i, seg in enumerate(segs):
        if proprietaire_de(seg):
            return '/'.join(segs[:i + 1] + [PRIVE]), None
    return None, ("Cette photo n'est dans le dossier de personne : "
                  "la ranger d'abord chez son proprietaire.")


def chez_soi(chemin, utilisateur):
    """Cette photo est-elle chez CET utilisateur ? Là où personne n'est chez
    soi (racine, `_A TRIER`, `_Uploads`), c'est l'admin — et lui seul."""
    proprietaire = proprietaire_de(chemin)
    if proprietaire is None:
        return utilisateur == ADMIN
    return utilisateur == proprietaire


def peut_juger(chemin, utilisateur):
    """Qui VOIT — et donc peut lever — une photo masquée par son ÉTAT ?
    Son propriétaire, ET l'admin. TRANCHÉ PAR MIKE le 07/09.

    C'est la seule différence avec le PRIVE, et elle a une raison. Le PRIVE
    est un choix HUMAIN, un rangement qu'on a voulu : l'admin n'a rien à y
    faire, et la règle le dit depuis le chantier 17. Le masquage sensible est
    un verdict de MACHINE, et la mesure du 06/09 dit qu'il se trompe une fois
    sur trois. Sans passe-partout, un faux positif sur une photo d'un dossier
    sans compte — `Photos Papa`, `_A TRIER`, la racine — serait invisible ET
    injugeable : masquée pour toujours, par erreur, sans personne pour la
    rendre. Le prix, assumé : un vrai document de Florine reste visible pour
    l'admin tant qu'elle n'a pas tranché — il l'était déjà avant le masquage,
    le masque ne fait que le retirer aux AUTRES."""
    return utilisateur == ADMIN or chez_soi(chemin, utilisateur)


def depot_reserve(depot_par, utilisateur):
    """Un dépôt encore dans `_Uploads` est-il FERMÉ à cet utilisateur ?

    Chantier 19, brique 2 (demande de Flo, 17/09). `_Uploads` n'est le dossier
    de personne : jusqu'ici tout le monde y voyait tout, donc une photo
    déposée était offerte à la famille AVANT que quiconque l'ait regardée —
    y compris le filet. Désormais un dépôt n'est visible que de son
    DÉPOSANT (le carnet le sait, `depot_de`) et de l'admin, jusqu'à ce qu'il
    soit rangé chez son propriétaire.

    Règle pure : l'appelant dit qui a déposé (`''` = inconnu, donc à l'admin
    seul — les dépôts d'avant le carnet), la règle ne lit rien."""
    if utilisateur is None:
        return False
    if utilisateur == ADMIN:
        return False
    return depot_par != utilisateur


AXES_VIE_PRIVEE = ('sensible', 'sensible_le', 'sensible_par', 'sensible_motif',
                   'masque_par', 'masque_le')


def preserver_axes(neuve, ancienne):
    """Reporte dans `neuve` les axes de VIE PRIVÉE que `ancienne` portait.

    POURQUOI (19/09). Le tagueur REMPLACE l'entrée d'index quand il tague une
    photo pour la première fois — il ne fusionne que sur un RE-tag, et le
    commentaire de cette branche-là explique bien pourquoi (« un hoquet
    d'ExifTool coûterait sa date à la photo »). Les axes de vie privée ont le
    même besoin, en plus grave : un masque effacé ne se voit pas, il se
    constate le jour où quelqu'un retrouve une photo qu'il croyait fermée.

    Aujourd'hui aucune photo masquée n'arrive vierge chez le tagueur — le
    geste exige un `personne:`, donc un tagging déjà fait. **« Aujourd'hui »
    n'est pas une garantie**, et la règle 2 du projet dit ce qu'on fait des
    décisions humaines : elles ne se perdent jamais. Celle-ci en est une.

    Ne touche QUE ce que la nouvelle entrée ne dit pas déjà : un tagueur qui
    poserait lui-même un axe garde le sien. Modifie `neuve` en place et la
    rend (même contrat que `auteurs.garnir`)."""
    if not isinstance(neuve, dict) or not isinstance(ancienne, dict):
        return neuve
    for axe in AXES_VIE_PRIVEE:
        if axe in ancienne and axe not in neuve:
            neuve[axe] = ancienne[axe]
    return neuve


def masques_de(entree):
    """Les comptes qui ont masqué cette photo (chantier 19, brique 3), ou ().

    Règle PURE : l'appelant donne l'entrée d'index BRUTE. Le champ vit en
    BASE et jamais dans le XMP — un masque posé par un TIERS ne se grave pas
    dans le fichier de quelqu'un d'autre (règle 18c, et ici elle compte
    double : le fichier n'appartient pas à qui masque)."""
    if not isinstance(entree, dict):
        return ()
    v = entree.get('masque_par')
    return tuple(v) if isinstance(v, (list, tuple)) else ()


def masque_personnel(masques, chemin, utilisateur):
    """Cette photo est-elle FERMÉE à cet utilisateur par le masque d'une
    personne reconnue dessus ? Chantier 19, brique 3 (demande de Flo).

    Tranché par Mike le 17/09 : une personne reconnue sur la photo d'un AUTRE
    peut la masquer, et **la photo ne bouge pas** — elle reste chez son
    propriétaire, qui continue de la voir. Restent donc trois regards :
    le PROPRIÉTAIRE (c'est sa photo, et il peut toujours l'effacer), la
    PERSONNE qui a masqué (sinon elle ne pourrait jamais lever son propre
    masque), et l'ADMIN (le même secours que pour le masque machine :
    `peut_juger` explique pourquoi un masque sans passe-partout se change en
    photo perdue). Tous les AUTRES ne la voient plus.

    Ce n'est pas `peut_juger` : là, l'admin et le propriétaire jugent un
    verdict de MACHINE. Ici le masque est le geste d'une PERSONNE sur son
    image, et c'est elle qui le lève — le propriétaire, lui, ne peut pas la
    redévoiler (il peut l'effacer, jamais la remontrer)."""
    if not masques or utilisateur is None:
        return False
    if utilisateur == ADMIN or utilisateur in masques:
        return False
    return not chez_soi(chemin, utilisateur)


def peut_masquer(masques, noms, utilisateur):
    """`utilisateur` peut-il POSER un masque sur cette photo ?

    Seulement s'il est parmi les personnes RECONNUES dessus (`noms`, les
    `personne:` de l'entrée, comparés sans la casse). C'est la règle n° 9 du
    projet : un geste qui ne peut jamais aboutir ne doit pas s'offrir — et
    c'est aussi ce qui empêche un compte de fermer la photo d'un autre sur
    laquelle il n'est pas."""
    if not utilisateur:
        return False
    if utilisateur in masques:
        return False                      # déjà masquée par lui
    bas = {str(n).strip().lower() for n in (noms or ())}
    return str(utilisateur).strip().lower() in bas


def peut_lever(masques, chemin, utilisateur):
    """`utilisateur` peut-il LEVER le masque qu'il a posé ?

    Lui seul, et l'ADMIN en secours. Pas le propriétaire : il peut effacer sa
    photo, jamais la redévoiler — c'est ce qui fait du masque une garantie et
    non une politesse. (`chemin` n'entre pas dans la règle aujourd'hui ; il
    est là pour que l'appelant n'ait pas à deviner quelle question poser.)"""
    if not utilisateur or not masques:
        return False
    return utilisateur == ADMIN or utilisateur in masques


def partage_ferme(fermes, chemin, utilisateur):
    """Cette photo est-elle fermée par la LISTE DE PARTAGE de son propriétaire ?
    Chantier 19, brique 5 (tranché par Mike les 17 et 18/09).

    Jusqu'ici la visibilité était une propriété du CHEMIN : tout ce qui n'est
    pas un PRIVE est à tout le monde. Elle devient une RELATION entre deux
    comptes — Flo décide qui voit `Photos Flo`.

    L'appelant fournit `fermes` : l'ensemble des PROPRIÉTAIRES qui ne
    partagent pas avec cet utilisateur, calculé UNE fois par requête
    (`comptes.fermes_pour`). La règle ne lit ni `comptes.json` ni rien
    d'autre — et quand cet ensemble est vide, ce qui est le cas tant que
    personne n'a rien restreint, elle ne coûte pas une comparaison.

    **L'ADMIN N'EST PAS UN PASSE-PARTOUT ICI** (choix de Mike, 18/09), et
    c'est délibéré : le partage est un choix HUMAIN, comme le PRIVE. Le
    passe-partout de `peut_juger` n'existe que pour les verdicts de MACHINE,
    où une erreur rendrait une photo invisible ET injugeable. Ici, personne ne
    s'est trompé : quelqu'un a décidé.

    Un chemin SANS propriétaire (racine, `_A TRIER`, `_Uploads`) n'a personne
    pour le restreindre : il garde ses règles d'avant."""
    if not fermes or utilisateur is None:
        return False
    proprietaire = proprietaire_de(chemin)
    return (proprietaire is not None and proprietaire != utilisateur
            and proprietaire in fermes)


def visible(chemin, utilisateur, sensible=False, depot_par=None, masques=(),
            fermes=(), reconnu=False):
    """`utilisateur` peut-il voir cette photo ? None (fil de fond) voit tout.

    DEUX causes de masquage, une seule règle. Le CHEMIN : chacun voit tout ce
    qui n'est pas le PRIVE d'un autre ; l'admin voit EN PLUS le PRIVE sans
    propriétaire (racine). Le PRIVE de Flo reste à Flo — l'admin n'est un
    passe-partout que là où personne n'est chez soi. Et, depuis le
    chantier 18, l'ÉTAT : `sensible=True` (l'entrée porte `en_attente`)
    masque la photo pour tout le monde SAUF son propriétaire et l'admin
    (`peut_juger` — la différence avec le PRIVE y est expliquée), sans que le
    fichier bouge.

    C'est le vrai changement du 07/09 : jusque-là la visibilité ne se
    décidait QUE sur le chemin, et masquer sans déplacer était impossible.
    L'appelant fournit `sensible` — la règle reste pure, elle ne lit pas
    l'index elle-même."""
    if utilisateur is None:
        return True
    if est_prive(chemin) and not chez_soi(chemin, utilisateur):
        return False
    # Le masque d'une PERSONNE reconnue (brique 3) : après le PRIVE, avant
    # tout le reste. L'ordre des masques entre eux ne change pas le verdict —
    # ils ferment tous — mais il fixe lequel on NOMME quand il faudra dire
    # pourquoi, et l'ordre écrit dans `docs/CHANTIER_19_VIE_PRIVEE.md` est
    # celui-là.
    if masques and masque_personnel(masques, chemin, utilisateur):
        return False
    # Le dépôt : un masque de plus, et les masques passent avant tout ce qui
    # ouvre (`docs/CHANTIER_19_VIE_PRIVEE.md`). `None` = ce chemin n'est pas
    # un dépôt ; l'appelant le dit, la règle ne cherche pas Uploads.
    if depot_par is not None and depot_reserve(depot_par, utilisateur):
        return False
    if sensible and not peut_juger(chemin, utilisateur):
        return False
    # Le PARTAGE en dernier : les masques ferment d'abord (ordre écrit dans
    # `docs/CHANTIER_19_VIE_PRIVEE.md`), et ce qui ouvre ne rouvre jamais ce
    # qu'un masque a fermé — ici le partage ne fait que fermer DAVANTAGE.
    #
    # LA RECONNAISSANCE (brique 4) est le SEUL contrepoids, et elle n'agit
    # qu'ici : être sur une photo rouvre ce que la liste de partage avait
    # fermé, JAMAIS ce qu'un masque ferme. On est au-dessous des quatre
    # masques dans le code parce qu'on est au-dessous d'eux dans la règle.
    if fermes and partage_ferme(fermes, chemin, utilisateur) and not reconnu:
        return False
    return True


def filtre(utilisateur, sensible=None, depot=None, masques=None, fermes=(),
           reconnu=None):
    """Le prédicat `clé -> bool` d'un utilisateur, ou None s'il voit tout.
    `sensible` : un appelable `clé -> bool` qui dit si l'entrée est masquée
    par son ÉTAT. Absent, seul le chemin décide (le comportement d'avant).

    LA MÊME RÈGLE QUE `visible`, DANS UN AUTRE ORDRE (11/09). La vue appelle
    ce prédicat pour chaque clé de chaque lecture agrégée — 44 603 clés pour
    un `len(STORE.data)`, ~3 µs chacune sur la machine chargée : 47 ms de CPU
    pour trois `len()` dans `/api/maint/status`. Presque aucune clé n'est dans
    un PRIVE (10 sur 44 604 le 11/09) : `est_prive`, mémoïsé, passe devant, et
    `visible` n'est appelée que pour elles. Hors PRIVE, seule l'ÉTAT peut
    masquer, et `peut_juger` décide. `test_vue_rapide.py` compare les deux
    écritures sur des milliers de clés tirées au hasard."""
    if utilisateur is None:
        return None
    if sensible is None and depot is None and masques is None and not fermes:
        def ok(cle):
            return not est_prive(cle) or chez_soi(cle, utilisateur)
        return ok

    def ok(cle):
        # Le masque personnel d'abord : c'est le seul qui puisse fermer une
        # photo à quelqu'un QUI EST DESSUS, et il ne coûte qu'une lecture de
        # champ sur une entrée que `sensible` lit de toute façon.
        if masques is not None:
            m = masques(cle)
            if m and masque_personnel(m, cle, utilisateur):
                return False
        if depot is not None:
            d = depot(cle)
            if d is not None and depot_reserve(d, utilisateur):
                return False
        if est_prive(cle):
            return visible(cle, utilisateur, sensible(cle) if sensible else False)
        if sensible is not None and sensible(cle):
            return peut_juger(cle, utilisateur)
        # `fermes` VIDE (personne n'a rien restreint) : pas une comparaison de
        # plus. C'est ce qui rend la brique 5 gratuite dans le cas courant --
        # le predicat tourne 44 445 fois pour un seul `len()`.
        #
        # Et `reconnu` n'est demande QUE pour les cles que le partage
        # fermerait (brique 4) : lire les noms d'une photo coute une liste de
        # mots-cles, on ne le fait donc pas 44 445 fois mais seulement pour ce
        # qui appartient a quelqu'un qui restreint. Le plan prevoyait un index
        # cle -> noms en memoire ; cet ORDRE-la le rend inutile.
        if fermes and partage_ferme(fermes, cle, utilisateur):
            return bool(reconnu and reconnu(cle, utilisateur))
        return True
    return ok


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

def peut_ecrire(chemin, utilisateur, depot=False):
    """`utilisateur` peut-il toucher ce FICHIER ? None (fil de fond) : tout.

    `depot=True` marque le seul geste qui ENTRE dans un PRIVE sans rien y
    lire : ranger une photo chez son propriétaire. **Tranché par Mike le
    10/09 : « j'ai le droit de déposer dans le privé de tout le monde, mais
    uniquement parce que je suis administrateur ».** L'admin dépose, il ne
    fouille pas — tout le reste du PRIVE d'autrui lui reste fermé, et
    `depot` ne s'écrit qu'au point d'appel de « Rendre privée ».

    La dissymétrie qu'on réparait : sans cette exception, l'admin pouvait
    EFFACER la photo de Flo mais pas la PROTÉGER. Une règle de confidentialité
    qui laisse détruire et interdit d'abriter protège le mauvais geste."""
    if utilisateur is None:
        return True
    if depot and utilisateur == ADMIN and est_prive(chemin):
        return True
    if not visible(chemin, utilisateur):
        return False
    if utilisateur == ADMIN:
        return True
    return proprietaire_de(chemin) == utilisateur


def refus_ecriture(chemin, utilisateur, depot=False):
    """None si le geste est permis ; sinon (code, message) : 404 quand la
    photo n'est pas visible (dire « interdit » dirait « ça existe »), 403
    quand elle est partagée mais n'est pas à lui."""
    if peut_ecrire(chemin, utilisateur, depot):
        return None
    if not visible(chemin, utilisateur):
        return 404, 'Fichier introuvable.'
    proprietaire = proprietaire_de(chemin)
    if proprietaire is None:
        return 403, "Hors d'un dossier propriétaire, seul l'admin range ou efface."
    return 403, f"Cette photo est à {proprietaire} : {proprietaire} ou l'admin peuvent la déplacer ou l'effacer, pas vous."


def refus_rendre_privee(chemin, utilisateur):
    """None si `utilisateur` peut rendre CETTE photo privee, sinon
    (code, message). Regle PURE, mise ici parce que c'est ici que vit la
    notion de chez-soi.

    **Pourquoi cette fonction existe** (10/09). L'onglet /sensibles offrait
    « Rendre privee » sur une photo de `Photos Flo`. Le geste deplace vers le
    PRIVE du PROPRIETAIRE (`cible_prive`), donc `Photos Flo/PRIVE` -- et le
    chantier 17 ferme le PRIVE de Flo meme a l'admin. Le refus tombait donc
    plus bas, dans `FileOps._permis`, sur la creation du dossier, et il
    sortait avec le message concu pour l'INCONNU : « Fichier introuvable. »

    Ce message est juste quand il s'adresse a quelqu'un qui ne peut pas voir
    la photo -- dire « interdit » dirait « ca existe ». Il est FAUX ici :
    l'onglet venait de mettre la photo sous les yeux de Mike, vignette
    comprise, parce que `peut_juger` l'y autorise. **Un refus doit nommer sa
    cause a qui regarde deja la chose.**

    Ce qui change : la cause est dite AVANT de toucher au disque, donc
    l'interface peut eteindre un bouton qui ne peut pas aboutir plutot que de
    le laisser echouer au clic. Et **l'admin depose** (`peut_ecrire(...,
    depot=True)`, tranche par Mike le 10/09) : la dissymetrie qui le laissait
    EFFACER la photo de Flo sans pouvoir la PROTEGER est fermee."""
    if utilisateur is None:
        return None
    # LA VISIBILITE D'ABORD, ET C'EST L'ORDRE QUI COMPTE. Le banc l'a attrape
    # au premier lancement : en demandant `cible_prive` avant, une photo qu'on
    # ne voit pas se faisait repondre « deja dans un dossier prive » — un refus
    # exact, et une CONFIRMATION D'EXISTENCE a qui n'avait pas le droit de
    # savoir qu'elle existe. Le message de l'inconnu ne vaut que s'il est dit
    # en premier.
    if not visible(chemin, utilisateur):
        return 404, 'Fichier introuvable.'
    dossier, raison = cible_prive(chemin)
    if dossier is None:
        return 400, raison
    proprietaire = proprietaire_de(chemin)
    if utilisateur != proprietaire and utilisateur != ADMIN:
        return 403, (f"Le dossier prive de {proprietaire} n'appartient qu'a "
                     f"{proprietaire} : cette photo ne peut y etre rangee que "
                     f"par {proprietaire} ou par l'admin. Vous pouvez la "
                     "mettre a la corbeille.")
    return None


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

    # `filter` natif plutôt qu'un générateur qui rappelle une méthode par clé
    # (11/09) : même prédicat, même instantané des clés, la boucle en C.

    def __iter__(self):
        return filter(self._ok, list(self._d))

    def __len__(self):
        """EXACT, et il le reste : `len()` compte ce qui est visible — c'est
        le point 17b, un compteur ne doit pas trahir ce qu'il cache.

        CE QU'IL COÛTE, mesuré le 18/09 par un banc de la brique 4 :
        `list(vue)` et `sorted(vue)` appellent le prédicat **deux fois par
        clé** — `list()` demande d'abord une taille pour dimensionner son
        tableau, `operator.length_hint` tombe sur ce `__len__` qui filtre
        tout, puis `__iter__` refiltre tout. 44 445 clés coûtent donc 88 890
        appels. `for k in vue`, `vue.keys()` et `len(vue)` n'en font qu'un.

        Deux fausses pistes, écartées par la mesure : `__length_hint__` ne
        sert à rien (`length_hint` essaie `__len__` d'ABORD et ne se rabat
        sur le hint que s'il lève), et mettre les clés filtrées en cache dans
        la vue rendrait `len()` faux dès qu'une écriture passe derrière —
        cher payé pour 8 ms. Le fait est donc CONNU et MESURÉ, pas corrigé ;
        il y a 47 `list(...data)` / `sorted(...data)` dans `server.py`
        (`PERFORMANCE.md`)."""
        return len(list(filter(self._ok, list(self._d))))
    def get(self, k, default=None):
        if not self._ok(k):
            return default
        return self._d.get(k, default)

    def keys(self):
        return list(filter(self._ok, list(self._d)))

    def values(self):
        d = self._d
        return [d[k] for k in filter(self._ok, list(d))]

    def items(self):
        d = self._d
        return [(k, d[k]) for k in filter(self._ok, list(d))]

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


def _cachee(champ, c, ok):
    """Cette citation du champ `champ` est-elle invisible ? Les mêmes tests
    que `filtrer_fiche`, écrits une fois pour les deux sens."""
    if champ == 'faces':
        return isinstance(c, (list, tuple)) and bool(c) and not ok(c[0])
    return isinstance(c, str) and not ok(c)


def _cle_citation(c):
    return tuple(c) if isinstance(c, list) else c


def restaurer_fiche(neuve, brute, ok):
    """Remet dans `neuve` ce que `filtrer_fiche(brute, ok)` en avait retiré.

    L'INVERSE EXACT DU FILTRE (11/09). Le serveur lit une fiche à travers la
    vue, la modifie, et la réécrit par `store.set` : sous un utilisateur
    connecté, la fiche lue était une COPIE sans ses citations invisibles, et la
    réécriture les EFFAÇAIT — visages, confirmations, exclusions et avatar pris
    dans le PRIVE d'un autre. Mesuré sur le vrai `SubjectStore.confirm` : Mike
    confirme une photo sur la fiche de Florine, le visage et la confirmation
    qu'elle a dans `Photos Flo/PRIVE` disparaissent de la base. La règle 2 du
    projet — un nom humain ne se perd jamais — tombait par une LECTURE.

    Ce qu'on ne pouvait pas voir, on ne peut pas l'avoir retiré. Donc :
      - pour `faces`, `exclude`, `confirmed` : les citations invisibles de la
        fiche brute reprennent LEUR PLACE (l'ordre compte : `_merge_assigned`
        coupe les plus anciennes au-delà de 6 000) ; les citations visibles
        suivent ce que l'écriture a décidé, et les nouvelles vont à la fin ;
      - l'`avatar` : invisible dans la brute et absent de la neuve, il revient.
        Un avatar VISIBLE posé par l'écriture l'emporte.
    Rend `neuve`, modifiée en place (comme `auteurs.garnir`)."""
    if not isinstance(neuve, dict) or not isinstance(brute, dict) or neuve is brute:
        return neuve
    for champ in ('faces',) + CHAMPS_CHEMINS:
        B = brute.get(champ)
        if not isinstance(B, list):
            continue
        if not any(_cachee(champ, c, ok) for c in B):
            continue
        N = neuve.get(champ)
        N = list(N) if isinstance(N, list) else []
        restant = {}
        for i, c in enumerate(N):
            restant.setdefault(_cle_citation(c), []).append(i)
        pris = set()
        out = []
        for c in B:
            if _cachee(champ, c, ok):
                out.append(c)
                continue
            places = restant.get(_cle_citation(c))
            if places:
                i = places.pop(0)
                pris.add(i)
                out.append(N[i])
        out.extend(c for i, c in enumerate(N) if i not in pris)
        neuve[champ] = out
    av = brute.get('avatar')
    if (isinstance(av, (list, tuple)) and av and not ok(av[0])
            and not neuve.get('avatar')):
        neuve['avatar'] = av
    return neuve


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

    # ─── `values`, `items`, `copy` : FILTRÉS (11/09) ───────────────────────
    # Hérités de `VueFiltree`, ils lisaient `self._d[k]` — la fiche BRUTE,
    # citations invisibles comprises. `__getitem__` et `get` filtraient, mais
    # les agrégats du serveur (`for pk, pe in PEOPLE_STORE.data.items()` : la
    # page Personnes, ses avatars, ses comptes) passaient à côté : un avatar
    # pris dans le PRIVE de Mike pouvait s'afficher chez Flo. C'est le point
    # 17b que ce module existe pour tenir.

    def values(self):
        ok = self._ok
        return [filtrer_fiche(v, ok) for v in list(self._d.values())]

    def items(self):
        ok = self._ok
        return [(k, filtrer_fiche(v, ok)) for k, v in list(self._d.items())]

    def copy(self):
        return dict(self.items())

    def pop(self, k, *defaut):
        """Retire la fiche ENTIÈRE et la rend BRUTE (11/09).

        La vue est en lecture seule, sauf ce geste-ci, et il a une raison :
        `SubjectStore.rename` et `.delete` (et les annulations) retirent une
        fiche par `store.data.pop(nom)`. Sous un utilisateur connecté, la vue
        n'avait pas de `pop` — renommer, fusionner ou supprimer une fiche
        PLANTAIT depuis l'étape 4. Retirer une fiche n'a rien à cacher : son
        nom est visible par construction (`__contains__`).

        Elle est rendue BRUTE parce que l'appelant la FUSIONNE ailleurs
        (`rename`) : filtrée, ses citations invisibles seraient perdues en
        route. **Ce qu'elle rend ne doit jamais partir tel quel vers un
        client** — c'est une matière d'écriture, pas d'affichage."""
        return self._d.pop(k, *defaut)


VUES_POSEES = 0          # combien de VUES ce processus a posées (compteur d'étendue)

# UNE VUE PAR REQUÊTE, PAS UNE PAR LECTURE (22/09).
#
# `store.data` est une PROPRIÉTÉ : chaque accès relit le compte courant,
# recharge `comptes.json` s'il a bougé, rebâtit le prédicat (six règles depuis
# le chantier 19) et enveloppe le dictionnaire. Le projet écrit `STORE.data`
# dans le corps de ses boucles à **128 endroits** — mesuré à l'arbre — et une
# de ces boucles coûtait **4,0 s sur les 7,3 s** de la page du fonds entier.
# Hisser la vue corrige UN endroit ; ce mémo les corrige tous, et protège ceux
# qu'on écrira demain.
#
# La vue est mémorisée PAR FIL et PAR GÉNÉRATION. Le serveur ouvre une
# génération à chaque requête (`nouvelle_generation`, appelée par `_ouvrir`),
# et toute écriture qui change ce que la règle répondrait en ouvre une aussi.
# Deux requêtes ne partagent donc jamais une vue, et une liste de partage qui
# change pendant une requête la referme.
_GEN = 0
_LOCAL = threading.local()


def nouvelle_generation():
    """Tout ce qui est mémorisé cesse de valoir. Appelé à chaque requête et à
    chaque écriture qui touche une règle (partage, masque, compte)."""
    global _GEN
    _GEN += 1


def generation():
    return _GEN


def brancher(store, utilisateur, par_nom=False, sensible=None, depot=None,
             masques=None, fermes=None, reconnu=None):
    """Fait de `store.data` une VUE dès qu'il y a un utilisateur courant
    (l'admin compris : il ne voit pas le PRIVE des autres). `utilisateur` est
    un appelable (thread-local côté serveur) ; None = fil de fond, tout.
    `sensible` est un appelable `clé -> bool` qui lit l'axe du chantier 18
    dans l'index BRUT. Il doit lire le dictionnaire RÉEL et jamais `.data`
    d'un magasin branché : la vue l'appelle pour décider, et il tournerait
    en rond.
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
        global VUES_POSEES
        d = brut(self)
        u = utilisateur()
        if u is None:
            return d
        memo = getattr(_LOCAL, 'vues', None)
        if memo is None:
            memo = _LOCAL.vues = {}
        garde = memo.get(id(store))
        if garde is not None and garde[0] == _GEN and garde[1] == u and garde[2] is d:
            return garde[3]
        # UN COMPTEUR D'ÉTENDUE (22/09, règle n° 8). Poser une vue n'est pas
        # gratuit : on relit le compte, on recharge `comptes.json` s'il a
        # bougé, on rebâtit le prédicat. Une boucle qui écrit `STORE.data`
        # dans son corps le paie par CLÉ, et rien ne le disait — la page du
        # fonds entier y laissait 4,0 s. Ce compteur est lu par `/files` et
        # rendu dans `/api/perf` : le jour où il repasse à 44 000, ça se voit.
        VUES_POSEES += 1
        # `fermes` est un APPELABLE : la liste de partage peut changer entre
        # deux requetes, et une vue qui garderait l'ensemble d'hier montrerait
        # ce que quelqu'un vient de fermer.
        vue = Vue(d, filtre(u, sensible, depot, masques,
                            fermes(u) if fermes else (), reconnu))
        memo[id(store)] = (_GEN, u, d, vue)
        return vue

    def ecrire(self, valeur):
        # Le dictionnaire RÉEL change d'objet : tout mémo qui le citait est
        # périmé. (Le mémo compare déjà `d` par identité ; la génération le
        # dit plus tôt et pour tous les fils.)
        nouvelle_generation()
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
    if par_nom:
        # L'ÉCRITURE d'une fiche remet ce que l'écrivain ne voyait pas (11/09,
        # `restaurer_fiche`). Posé sur l'ATTRIBUT d'instance, par-dessus ce
        # qui s'y trouve déjà (`auteurs.garnir`) : la réconciliation des
        # auteurs doit voir la fiche ENTIÈRE, sinon elle prendrait chaque
        # citation invisible pour une décision annulée.
        set_avant = store.set

        def set_restaure(name, entry, *a, **kw):
            u = utilisateur()
            if u is not None and isinstance(entry, dict):
                restaurer_fiche(entry, brut(store).get(name),
                                filtre(u, sensible, depot, masques,
                                       fermes(u) if fermes else (), reconnu))
            return set_avant(name, entry, *a, **kw)
        store.set = set_restaure
    return store
