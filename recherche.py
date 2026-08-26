#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Décomposition DÉTERMINISTE d'une requête de recherche — pur, testable.

Chantier 14a. Le champ de recherche reçoit une phrase ; avant de la donner à
SigLIP, on lui retire ce qui se décide **sans modèle et sans GPU**. Trois
dimensions existaient déjà dans `server.semantic_search` — QUI (noms posés par
un humain), OÙ (lieux), QUOI (le sens de l'image). Ce module ajoute la
quatrième, **QUAND**, et rend le reste à SigLIP.

Le module ne connaît ni STORE ni server : comme `meme_jour`, il reçoit ses
lecteurs de date en paramètre. Une seule implémentation de chaque règle dans le
projet.

## Ordre imposé (invariant du chantier)

    noms  →  lieux  →  PÉRIODE  →  reste → SigLIP

Les noms d'abord, toujours : quelqu'un peut s'appeler « Mai », et un nom humain
qui se ferait manger par un mois serait une capacité perdue en silence — la
forme d'erreur la plus chère du projet. Les lieux ensuite, pour la même raison
(« Sion » n'est pas une date, mais « Mai » est un village du Cameroun).

## Deux précisions de date, jamais mélangées

`_best_time` du serveur retombe sur `mtime` en dernier recours : pour une
ANNÉE demandée, c'est un mensonge (le tagging de 2026 réécrit le fichier d'une
photo de 1998). Ce module distingue donc :

- **précision « annee »** — « photos de 2015 ». Sources acceptées : dates
  précises (EXIF, nom de fichier) **et** année du dossier. Jamais `mtime`.
  C'est ce qui rend visibles les ~29 % de photos sans date au jour près.
- **précision « precise »** — « en décembre », « à Noël », « le 14 août ».
  Le mois n'existe pas dans une année de dossier : seule la date précise
  compte (`meme_jour.epoch_precis`).

Et le filtre **COMPTE** ce qu'il écarte faute de précision (`sans_date`) : une
protection qui s'annule doit se compter, sinon « 3 résultats » se lit comme
« il n'y a que 3 photos » au lieu de « 12 000 photos n'ont pas de mois ».

## Ce que ce module ne fait PAS

- Pâques et les fêtes mobiles : leur date change chaque année et personne ne
  les a demandées. Une fête mal placée d'un jour est pire qu'absente.
- « Les vacances », « quand il neigeait » : c'est du SENS, donc SigLIP.
- Deviner une période quand la requête n'en contient pas : `None` est une
  réponse, et elle laisse la requête entière à SigLIP.
"""

import re
import time
import unicodedata

from geocode import sans_accents

# Bornes d'une année plausible dans une REQUÊTE. 1900 et non 1990 : le plancher
# 1990 a déjà coûté 716 photos des années 80 (session 14, `eval/DECISIONS.md`)
# — on ne le réintroduit pas ici par distraction.
ANNEE_MIN, ANNEE_MAX = 1900, 2099

# Sans accents : ce vocabulaire sert à COMPARER (la requête est normalisée).
# Les libellés montrés à l'humain viennent de `meme_jour.MOIS_FR`, accentués.
MOIS = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet',
        'aout', 'septembre', 'octobre', 'novembre', 'decembre']
MOIS_LIBELLE = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                'juillet', 'août', 'septembre', 'octobre', 'novembre',
                'décembre']
JOURS_DU_MOIS = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# Hémisphère NORD, et c'est un CHOIX : le fonds est suisse. Les bornes sont
# calendaires (mois entiers), pas astronomiques — « été 2015 » veut dire
# juin-juillet-août, pas « à partir du 21 juin ». Personne ne cherche au
# solstice près.
SAISONS = {
    'printemps': (3, 4, 5),
    'ete': (6, 7, 8),
    'hiver': (12, 1, 2),
    'automne': (9, 10, 11),
}
SAISON_LIBELLE = {'printemps': 'printemps', 'ete': 'été', 'hiver': 'hiver',
                  'automne': 'automne'}

# Fêtes à date FIXE seulement (voir l'en-tête). Le réveillon déborde sur deux
# jours et deux années : on prend les deux jours, l'année demandée s'applique
# aux deux — un 31/12/2015 et un 01/01/2015 sont tous deux « le réveillon de
# 2015 » pour quelqu'un qui cherche, et trancher plus finement inventerait une
# intention.
FETES = {
    'noel': (('12-24', '12-25'), 'Noël'),
    'reveillon': (('12-31', '01-01'), 'réveillon'),
    'nouvel an': (('12-31', '01-01'), 'Nouvel An'),
    'jour de l an': (('01-01',), "Jour de l'An"),
    'saint sylvestre': (('12-31',), 'Saint-Sylvestre'),
}

# Prépositions avalées AVEC la date, pour qu'elles ne partent pas polluer
# SigLIP : « photos de Luna en 2015 » doit lui laisser « photos », pas
# « photos en ».
_PREP = r"(?:en|de|du|d['’]|dans|vers|autour de|a|au|aux)\s+"
_AN = r"(?:1[89]\d\d|20\d\d)"


class Periode:
    """Contrainte temporelle extraite d'une requête. Immuable en pratique.

    `an_min`/`an_max` : bornes d'année INCLUSIVES (None = pas de borne).
    `mois`   : ensemble de mois 1-12 retenus (vide = tous).
    `jours`  : ensemble de « MM-JJ » retenus (vide = tous).
    `libelle`: ce qu'on montre à l'humain, pour qu'il voie ce qui a été
               compris — une recherche qui filtre en silence est une recherche
               qu'on n'ose plus croire.
    """

    __slots__ = ('an_min', 'an_max', 'mois', 'jours', 'libelle')

    def __init__(self, an_min=None, an_max=None, mois=(), jours=(),
                 libelle=''):
        self.an_min = an_min
        self.an_max = an_max
        self.mois = frozenset(mois)
        self.jours = frozenset(jours)
        self.libelle = libelle

    def exige_date_precise(self):
        """Un mois ou un jour demandé n'existe pas dans une année de dossier."""
        return bool(self.mois or self.jours)

    def contient_annee(self, an):
        if not an:
            return False
        if self.an_min is not None and an < self.an_min:
            return False
        if self.an_max is not None and an > self.an_max:
            return False
        return True

    def contient_epoch(self, epoch):
        """epoch LOCAL (les epochs du projet viennent de `time.mktime`)."""
        try:
            t = time.localtime(float(epoch))
        except (ValueError, TypeError, OverflowError, OSError):
            return False
        if not self.contient_annee(t.tm_year):
            return False
        if self.mois and t.tm_mon not in self.mois:
            return False
        if self.jours and '%02d-%02d' % (t.tm_mon, t.tm_mday) not in self.jours:
            return False
        return True

    def __repr__(self):                                       # pragma: no cover
        return (f"Periode({self.an_min}..{self.an_max}, mois={sorted(self.mois)},"
                f" jours={sorted(self.jours)}, {self.libelle!r})")

    def __eq__(self, autre):
        return (isinstance(autre, Periode)
                and (self.an_min, self.an_max, self.mois, self.jours)
                == (autre.an_min, autre.an_max, autre.mois, autre.jours))

    def __hash__(self):
        return hash((self.an_min, self.an_max, self.mois, self.jours))


def _an(txt):
    """« 2015 » → 2015 si c'est une année plausible, sinon None."""
    try:
        n = int(txt)
    except (TypeError, ValueError):
        return None
    return n if ANNEE_MIN <= n <= ANNEE_MAX else None


def _libelle_annees(an_min, an_max):
    if an_min is not None and an_max is not None:
        return str(an_min) if an_min == an_max else f"{an_min}–{an_max}"
    if an_min is not None:
        return f"depuis {an_min}"
    if an_max is not None:
        return f"jusqu'en {an_max}"
    return ''


def _joindre(*morceaux):
    return ' '.join(m for m in morceaux if m)


# ─── Règles, de la PLUS SPÉCIFIQUE à la plus générale ────────────────────────
# L'ordre compte : « décembre 2015 » doit être lu par la règle mois+année, pas
# par la règle « année seule » qui laisserait « décembre » à SigLIP.

def _r_intervalle(m, ref):
    a, b = _an(m.group('a')), _an(m.group('b'))
    if a is None or b is None:
        return None
    a, b = min(a, b), max(a, b)
    return Periode(a, b, libelle=_libelle_annees(a, b))


def _r_avant(m, ref):
    a = _an(m.group('a'))
    return None if a is None else Periode(an_max=a - 1,
                                          libelle=f"avant {a}")


def _r_apres(m, ref):
    a = _an(m.group('a'))
    return None if a is None else Periode(an_min=a + 1,
                                          libelle=f"après {a}")


def _r_depuis(m, ref):
    a = _an(m.group('a'))
    return None if a is None else Periode(an_min=a, libelle=f"depuis {a}")


def _r_jusqua(m, ref):
    a = _an(m.group('a'))
    return None if a is None else Periode(an_max=a, libelle=f"jusqu'en {a}")


def _r_decennie(m, ref):
    """« années 80 », « années 1990 », « annees 2000 »."""
    brut = m.group('d')
    if len(brut) == 2:
        n = int(brut)
        # « années 20 » est ambigu ; le fonds est familial et commence au
        # siècle dernier : 30-99 → 19xx, 00-29 → 20xx.
        debut = 1900 + n if n >= 30 else 2000 + n
    else:
        debut = _an(brut)
        if debut is None:
            return None
        debut -= debut % 10
    return Periode(debut, debut + 9, libelle=f"années {debut}")


def _r_fete_annee(m, ref):
    return _fete(m.group('f'), _an(m.group('a')))


def _r_fete(m, ref):
    return _fete(m.group('f'), None)


def _fete(nom, an):
    jours, libelle = FETES[' '.join(sans_accents(nom).split())]
    return Periode(an, an, jours=jours,
                   libelle=_joindre(libelle, str(an) if an else ''))


def _r_jour_mois_annee(m, ref):
    return _jour_mois(m.group('j'), m.group('m'), _an(m.group('a')))


def _r_jour_mois(m, ref):
    return _jour_mois(m.group('j'), m.group('m'), None)


def _jour_mois(jour, mois, an):
    i = MOIS.index(sans_accents(mois))
    j = int(jour)
    if not (1 <= j <= JOURS_DU_MOIS[i]):
        return None                       # « 31 février » : aucune photo
    return Periode(an, an, jours=('%02d-%02d' % (i + 1, j),),
                   libelle=_joindre(f"{j} {MOIS_LIBELLE[i]}",
                                    str(an) if an else ''))


def _r_mois_annee(m, ref):
    return _mois(m.group('m'), _an(m.group('a')))


def _r_mois(m, ref):
    return _mois(m.group('m'), None)


def _mois(mois, an):
    i = MOIS.index(sans_accents(mois))
    return Periode(an, an, mois=(i + 1,),
                   libelle=_joindre(MOIS_LIBELLE[i], str(an) if an else ''))


def _r_saison_annee(m, ref):
    return _saison(m.group('s'), _an(m.group('a')))


def _r_saison(m, ref):
    return _saison(m.group('s'), None)


def _saison(saison, an):
    s = sans_accents(saison)
    return Periode(an, an, mois=SAISONS[s],
                   libelle=_joindre(SAISON_LIBELLE[s], str(an) if an else ''))


def _r_cette_annee(m, ref):
    return Periode(ref, ref, libelle=str(ref))


def _r_annee_derniere(m, ref):
    return Periode(ref - 1, ref - 1, libelle=str(ref - 1))


def _r_il_y_a(m, ref):
    n = int(m.group('n'))
    if n > 200:
        return None
    a = ref - n
    return None if a < ANNEE_MIN else Periode(a, a, libelle=str(a))


def _r_annee(m, ref):
    a = _an(m.group('a'))
    return None if a is None else Periode(a, a, libelle=str(a))


_MOIS_RE = '|'.join(MOIS)
_SAISON_RE = '|'.join(SAISONS)
_FETE_RE = '|'.join(f.replace(' ', r'\s+') for f in
                    sorted(FETES, key=len, reverse=True))

# (regex, fabricant). Testées dans cet ordre, en boucle, jusqu'à épuisement :
# « Luna en 2015 et 2018 » donne bien les deux années (elles fusionnent).
REGLES = [
    (rf"\bentre\s+(?P<a>{_AN})\s+et\s+(?P<b>{_AN})\b", _r_intervalle),
    (rf"\bde\s+(?P<a>{_AN})\s+(?:a|à)\s+(?P<b>{_AN})\b", _r_intervalle),
    (rf"\b(?P<a>{_AN})\s*[-–]\s*(?P<b>{_AN})\b", _r_intervalle),
    (rf"\bavant\s+(?:{_PREP})?(?P<a>{_AN})\b", _r_avant),
    (rf"\b(?:apres|après)\s+(?:{_PREP})?(?P<a>{_AN})\b", _r_apres),
    (rf"\bdepuis\s+(?:{_PREP})?(?P<a>{_AN})\b", _r_depuis),
    (rf"\bjusqu[' ]?(?:en|a|à)\s+(?P<a>{_AN})\b", _r_jusqua),
    (rf"\b(?:annees|années)\s+(?P<d>\d{{4}}|\d{{2}})\b", _r_decennie),
    (rf"\b(?:le\s+)?(?P<j>\d{{1,2}})\s+(?P<m>{_MOIS_RE})\s+"
     rf"(?:{_PREP})?(?P<a>{_AN})\b", _r_jour_mois_annee),
    (rf"\b(?:le\s+)?(?P<j>\d{{1,2}})\s+(?P<m>{_MOIS_RE})\b", _r_jour_mois),
    (rf"\b(?P<f>{_FETE_RE})\s+(?:{_PREP})?(?P<a>{_AN})\b", _r_fete_annee),
    (rf"\b(?:{_PREP})?(?P<m>{_MOIS_RE})\s+(?:{_PREP})?(?P<a>{_AN})\b",
     _r_mois_annee),
    (rf"\b(?:{_PREP})?(?P<s>{_SAISON_RE})\s+(?:{_PREP})?(?P<a>{_AN})\b",
     _r_saison_annee),
    (rf"\b(?P<f>{_FETE_RE})\b", _r_fete),
    (rf"\b(?:{_PREP})?(?P<m>{_MOIS_RE})\b", _r_mois),
    (rf"\b(?:{_PREP})?(?P<s>{_SAISON_RE})\b", _r_saison),
    (rf"\bcette\s+annee\b|\bcette\s+année\b", _r_cette_annee),
    (rf"\bl[' ]?(?:annee|année)\s+(?:derniere|dernière)\b", _r_annee_derniere),
    (rf"\bil\s+y\s+a\s+(?P<n>\d{{1,3}})\s+ans?\b", _r_il_y_a),
    (rf"\b(?:{_PREP})?(?P<a>{_AN})\b", _r_annee),
]

# « été » est aussi le participe passé d'« être » : « la photo a été prise à
# Sion » ne parle pas de la saison. On refuse la saison quand elle suit un
# auxiliaire. Le cas inverse (« l'été 2015 ») n'est jamais précédé d'un
# auxiliaire.
_AUXILIAIRE_AVANT_ETE = re.compile(r"\b(?:a|as|ai|ont|avons|avez|avait|"
                                   r"avaient|aurait|aura|eu)\s+$")

_COMPILEES = [(re.compile(rx), fab) for rx, fab in REGLES]


def _fusionner(periodes):
    """Plusieurs contraintes dans une phrase → une seule.

    Les années s'UNISSENT (« 2015 et 2018 » = l'enveloppe 2015-2018 : une
    plage est ce que l'humain veut dire, et c'est ce qu'on lui montre), les
    mois et les jours s'INTERSECTENT quand ils portent sur la même dimension
    — sinon ils se cumulent (« décembre 2015 » = mois ∩ année).
    """
    if not periodes:
        return None
    if len(periodes) == 1:
        return periodes[0]
    mins = [p.an_min for p in periodes if p.an_min is not None]
    maxs = [p.an_max for p in periodes if p.an_max is not None]
    mois, jours = set(), set()
    for p in periodes:
        if p.mois:
            mois = (mois & set(p.mois)) if mois else set(p.mois)
        if p.jours:
            jours = (jours & set(p.jours)) if jours else set(p.jours)
    return Periode(min(mins) if mins else None,
                   max(maxs) if maxs else None,
                   mois, jours,
                   ' + '.join(p.libelle for p in periodes if p.libelle))


def _normaliser_avec_positions(texte):
    """`texte` → (version comparable, position[i] = index d'origine du i-ᵉ car.).

    Pourquoi pas un simple `sans_accents` : on a besoin de RENDRE la requête
    amputée de ses dates, donc de reporter sur l'ORIGINAL des positions
    trouvées sur la version normalisée. `_extraire_noms`/`_extraire_lieux`
    supposent que la normalisation conserve la longueur — c'est vrai du texte
    précomposé, FAUX d'un « e + accent combinant » (2 caractères → 1) et d'un
    « İ » (1 → 2 en minuscule). Rare, mais un décalage d'un caractère coupe un
    mot en deux au lieu de lever une erreur : exactement la panne muette que ce
    projet paie cher. On garde donc la carte des positions au lieu de parier.

    Le résultat est identique à `geocode.sans_accents` (vérifié par test) :
    une seule clé de comparaison dans tout le projet.
    """
    caracteres, position = [], []
    for i, ch in enumerate(texte):
        for c in unicodedata.normalize('NFD', ch.lower()):
            if unicodedata.combining(c):
                continue
            caracteres.append(c)
            position.append(i)
    return ''.join(caracteres), position


def extraire_periode(requete, annee_ref=None):
    """« Luna a Sion en decembre 2015 » → (Periode, 'Luna a Sion').

    Rend `(None, requete)` si la requête ne contient aucune date : c'est une
    réponse, pas un échec — toute la phrase part alors à SigLIP.

    `annee_ref` : année de référence des formules relatives (« cette année »).
    Injectée pour que les tests ne dépendent pas du calendrier.
    """
    texte = str(requete or '')
    if not texte.strip():
        return None, texte
    if annee_ref is None:
        annee_ref = time.localtime().tm_year
    # `sans_accents` conserve la longueur (NFD puis retrait des combinantes) :
    # les positions trouvées sur la version normalisée valent sur l'originale.
    norm, position = _normaliser_avec_positions(texte)

    trouvees, spans, consomme = [], [], [False] * len(norm)
    for rx, fabriquer in _COMPILEES:
        for m in rx.finditer(norm):
            if any(consomme[m.start():m.end()]):
                continue                       # déjà pris par une règle plus
                                               # spécifique
            if (m.groupdict().get('s') == 'ete'
                    and _AUXILIAIRE_AVANT_ETE.search(norm[:m.start('s')])):
                continue
            p = fabriquer(m, annee_ref)
            if p is None:
                continue
            trouvees.append(p)
            spans.append((position[m.start()], position[m.end() - 1] + 1))
            for i in range(m.start(), m.end()):
                consomme[i] = True

    if not trouvees:
        return None, texte
    reste = texte
    for debut, fin in sorted(spans, reverse=True):
        reste = reste[:debut] + _MARQUE + reste[fin:]
    return _fusionner(trouvees), _nettoyer_reste(reste)


# Marqueur du trou laissé par une date retirée. Sert à repérer les
# conjonctions ORPHELINES : « Luna en 2015 et 2018 » laissait « Luna et ».
_MARQUE = '\x00'
_CONNECTEURS = {'et', 'ou', 'puis', 'en', 'de', 'du', 'a', 'au', 'aux',
                'dans', 'vers', 'le', 'la', 'les', 'l', "l'", 'd', "d'"}


def _nettoyer_reste(reste):
    """Retire les connecteurs devenus orphelins autour d'une date retirée.

    Conservateur par construction : un mot n'est retiré que s'il est dans la
    courte liste ET collé au trou. « chien et chat » garde son « et » — il n'y
    a pas de trou à côté ; « Luna et ␀ » perd le sien. Ce qui reste part à
    SigLIP, où un connecteur isolé n'apporte rien et peut nuire.
    """
    jetons = [j for j in reste.replace(_MARQUE, f' {_MARQUE} ').split() if j]
    garder = []
    for i, j in enumerate(jetons):
        if j == _MARQUE:
            continue
        voisin_trou = ((i > 0 and jetons[i - 1] == _MARQUE)
                       or (i + 1 < len(jetons) and jetons[i + 1] == _MARQUE))
        if voisin_trou and sans_accents(j).strip(",;") in _CONNECTEURS:
            continue
        garder.append(j)
    return ' '.join(garder)


# ─── JETONS D'AXE — `<axe>:<valeur>`, et ce qu'on ne sait pas satisfaire ─────
# Le 26/08, `/files?q=animal:Zzzznexistepas` rendait **1 500 photos**. Le jeton
# ne ressemblait à aucun nom NU, aucun extracteur ne le réclamait : il partait
# donc en recherche sémantique, et la page l'annonçait comme un FILTRE. Le
# défaut avait été corrigé le 21/08 pour `espece:licorne` et oublié sur les
# autres axes — alors que l'interface écrit elle-même ce vocabulaire (« le
# FILTRE de la planche garde les tags nommés : y chercher personne:Luna a du
# sens », `gallery.html`). Un filtre qui ment a produit un verdict faux sur une
# chatte qui a vécu seize ans dans cette maison.
#
# Trois règles, et elles valent pour TOUS les axes :
#   1. axe connu, valeur inconnue  → RIEN, et on nomme la valeur ;
#   2. axe inconnu                 → RIEN, et on nomme l'axe ;
#   3. jamais de repli silencieux sur le sens : c'est ce repli qui rendait
#      tout le fonds pour un nom inventé.
#
# La valeur peut tenir en PLUSIEURS MOTS — `personne:Cédric Baudin` est
# exactement ce que la galerie écrit. On garde le plus long groupe de mots que
# le résolveur reconnaît (comme `_extraire_noms` teste les noms composés en
# premier) ; à défaut le PREMIER mot, et c'est lui qu'on nomme dans le refus.
# Des guillemets ferment la question : `personne:"Anne Marie"`.
#
# Un espace AVANT le deux-points n'est toléré que sur un axe CONNU
# (`espece : chats`, graphie acceptée depuis le 20/08). Sur un axe inconnu il
# faut le deux-points COLLÉ : sans cette nuance, « Luna : la chatte » — une
# phrase, pas un filtre — ne rendrait plus rien.

_JETON_AXE = re.compile(
    r"(?<![\w:/])([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9'’_-]*)(\s*):\s*(?=[^\s,;])")

MOTS_MAX_VALEUR = 4          # « Le chat de Bremblens » : quatre mots suffisent
_FERMANTE = {'"': '"', '“': '”', '«': '»'}


def _cle_de_comparaison(mot):
    """Même clé que `geocode.sans_accents` — une seule dans tout le projet."""
    return _normaliser_avec_positions(mot)[0]


def _valeur_du_jeton(texte, debut, borne, axe, resoudre):
    """(valeur, fin) — la plus LONGUE valeur que `resoudre` reconnaît.

    `borne` : là où commence le jeton suivant. Sans elle, la valeur de
    `personne:X` avalerait `animal:Y` écrit juste après."""
    zone = texte[debut:borne]
    for fin_de_valeur in (',', ';'):
        i = zone.find(fin_de_valeur)
        if i >= 0:
            zone = zone[:i]
    if zone[:1] in _FERMANTE:
        j = zone.find(_FERMANTE[zone[0]], 1)
        if j > 0:
            return zone[1:j].strip(), debut + j + 1
    mots, pos = [], 0
    while len(mots) < MOTS_MAX_VALEUR:
        while pos < len(zone) and zone[pos].isspace():
            pos += 1
        if pos >= len(zone):
            break
        d = pos
        while pos < len(zone) and not zone[pos].isspace():
            pos += 1
        mots.append((zone[d:pos], debut + pos))
    if not mots:
        return '', debut
    if axe is not None:
        for n in range(len(mots), 0, -1):
            candidat = ' '.join(m for m, _f in mots[:n])
            if resoudre(axe, candidat) is not None:
                return candidat, mots[n - 1][1]
    return mots[0][0], mots[0][1]


def extraire_jetons(requete, axes, resoudre, axe_inconnu_refuse=False):
    """Détache tous les jetons `<axe>:<valeur>` d'une requête.

    `axes`    : {graphie sans accent en minuscules -> axe canonique}. Le module
                ne connaît AUCUN vocabulaire, il le reçoit — comme il reçoit
                ses lecteurs de date.
    `resoudre`: (axe, valeur) -> valeur canonique | None.
    `axe_inconnu_refuse` : **False par défaut, et c'est un rouge observé.**
                Un extracteur qui ne s'occupe que de SON axe croise forcément
                ceux des autres : appelé pour `espece:` sur « animal:Caline »,
                il a annoncé « espèce inconnue : Caline » et mangé le jeton
                (banc du 26/08, huit griefs d'un coup). Chaque extracteur
                laisse donc passer ce qui n'est pas à lui ; SEUL le dernier —
                celui qui connaît tous les axes — met ce drapeau à True et
                refuse ce qui reste.

    Rend `(retenus, inconnus, reste)` :
      retenus  [(axe, valeur canonique)]  — dédoublonnés, dans l'ordre lu ;
      inconnus [(axe, valeur, axe_connu)] — `axe_connu` False = l'AXE lui-même
               est inconnu, et alors `axe` est la graphie telle qu'écrite ;
      reste    la requête amputée de ses jetons, espaces normalisés.

    Les INCONNUS sont rendus, jamais avalés : c'est toute la correction. Un
    appelant qui en reçoit un doit rendre ZÉRO photo et le DIRE.
    """
    texte = requete or ''
    trouves = list(_JETON_AXE.finditer(texte))
    retenus, inconnus, morceaux = [], [], []
    i = 0
    for rang, m in enumerate(trouves):
        if m.start() < i:                     # avalé par la valeur précédente
            continue
        axe = axes.get(_cle_de_comparaison(m.group(1)))
        if axe is None and (m.group(2) or not axe_inconnu_refuse):
            # Espace avant le deux-points : « Luna : la chatte » est une
            # phrase. Axe d'un AUTRE extracteur : ce n'est pas à celui-ci de
            # le juger — il le laisse intact pour le suivant.
            continue
        borne = len(texte)
        for suivant in trouves[rang + 1:]:
            if suivant.start() >= m.end():
                borne = suivant.start()
                break
        valeur, fin = _valeur_du_jeton(texte, m.end(), borne, axe, resoudre)
        if not valeur:
            continue
        morceaux.append(texte[i:m.start()])
        i = fin
        if axe is None:
            trace = (m.group(1), valeur, False)
            if trace not in inconnus:
                inconnus.append(trace)
            continue
        canonique = resoudre(axe, valeur)
        if canonique is None:
            trace = (axe, valeur, True)
            if trace not in inconnus:
                inconnus.append(trace)
        elif (axe, canonique) not in retenus:
            retenus.append((axe, canonique))
    morceaux.append(texte[i:])
    return retenus, inconnus, ' '.join(' '.join(morceaux).split())


# ─── ESPÈCE — le 5ᵉ axe, et il est EXPLICITE ────────────────────────────────
# Forme A (choix de Mike, 20/08) : un jeton que l'utilisateur écrit, jamais une
# promotion silencieuse d'un mot de la phrase. « chat » tapé seul reste du SENS
# et part à SigLIP ; `espece:chat` est un FILTRE. La différence est mesurée :
# `q=mouton` rend 1 500 photos dont 28 moutons confirmés, `espece:mouton` en
# rend 32, tous confirmés par deux regards (21/08).
#
# `especes:` au pluriel et `espèce:` accentué sont acceptés : refuser une
# graphie que l'utilisateur écrira forcément serait une panne, pas une règle.
# Le mécanisme est COMMUN depuis le 26/08 (voir « JETONS D'AXE » plus haut) :
# `espece:` avait déjà sa règle — un jeton qu'on ne sait pas satisfaire rend
# RIEN — et les autres axes ne l'avaient pas. Deux implémentations de la même
# règle auraient divergé une deuxième fois ; celle-ci est la seule.
#
# `especes:` au pluriel et `espèce:` accentué sont acceptés : refuser une
# graphie que l'utilisateur écrira forcément serait une panne, pas une règle.
AXES_ESPECE = {'espece': 'espece', 'especes': 'espece'}


def extraire_especes(requete, canonique):
    """Détache les jetons `espece:` de la requête.

    « Luna espece:chat en 2015 » → (['chat'], [], 'Luna en 2015')

    `canonique` : mot → espèce canonique ou `None` (en prod
    `faits_vue.espece_canonique`). Le module ne connaît pas le vocabulaire, il
    le REÇOIT — comme il reçoit ses lecteurs de date. Une seule liste
    d'espèces dans le projet, et elle vit à côté de la règle qui les lit.

    Rend `(especes, inconnues, reste)`. Les INCONNUES sont rendues au lieu
    d'être ignorées : `espece:licorne` doit dire « je ne connais pas cette
    espèce » et ne rien rendre. Les ignorer rendrait TOUTES les photos, et
    l'utilisateur lirait ce silence comme un accord.

    L'extraction passe AVANT les noms — contrairement à l'ordre des trois
    autres axes — parce qu'un jeton préfixé n'est ambigu avec rien : personne
    ne s'appelle « espece:… ». C'est le retirer TARD qui serait risqué.

    Depuis le 26/08 ce n'est plus qu'une VUE sur `extraire_jetons` : la règle
    du jeton insatisfaisable est la même pour les cinq axes, et elle n'a plus
    qu'un seul endroit où être fausse.
    """
    retenus, inconnus, reste = extraire_jetons(
        requete, AXES_ESPECE, lambda _axe, valeur: canonique(valeur))
    return ([v for _a, v in retenus],
            [v for _a, v, _connu in inconnus],
            reste)


def filtrer_periode(entrees, periode, epoch_precis, annee_fiable):
    """Restreint des (clé, entrée) à une période. Rend `(clés, sans_date)`.

    `epoch_precis(cle, entree)` → epoch|None — date au jour près SEULEMENT
    (`meme_jour.epoch_precis`), jamais l'année du dossier.
    `annee_fiable(cle, entree)` → int|0 — année sûre : dates précises, sinon
    année du DOSSIER. **Jamais `mtime`** (voir l'en-tête).

    `sans_date` compte les photos écartées **faute de la précision exigée**,
    pas celles qui sont hors période. C'est ce chiffre qui distingue « il n'y a
    que 3 photos en décembre » de « 12 000 photos n'ont pas de mois connu ».
    """
    retenues, sans_date = set(), 0
    precis = periode.exige_date_precise()
    for cle, entree in entrees:
        if not isinstance(entree, dict) or entree.get('failed'):
            continue
        if precis:
            ep = epoch_precis(cle, entree)
            if ep is None:
                sans_date += 1
                continue
            if periode.contient_epoch(ep):
                retenues.add(cle)
        else:
            an = annee_fiable(cle, entree)
            if not an:
                sans_date += 1
                continue
            if periode.contient_annee(an):
                retenues.add(cle)
    return retenues, sans_date


def annee_fiable_depuis(epoch_precis, path_year_num):
    """Fabrique le lecteur d'année SÛRE attendu par `filtrer_periode`.

    Ordre : date précise (EXIF, nom de fichier) → année du DOSSIER → 0.
    Le `mtime` de `server._best_time` est volontairement absent : le tagging
    de 2026 réécrit le fichier d'une photo de 1998, et « photos de 2026 »
    remonterait alors la moitié de la photothèque.
    """
    def lire(cle, entree):
        ep = epoch_precis(cle, entree)
        if ep is not None:
            try:
                return time.localtime(float(ep)).tm_year
            except (ValueError, TypeError, OverflowError, OSError):
                pass
        try:
            return int(path_year_num(cle)) or 0
        except (TypeError, ValueError):
            return 0
    return lire


# ── Tri chronologique : la même règle de date que le FILTRE ──────────────
#
# Le cas « aucun mot pour SigLIP » (« Luna en 2015 ») a déjà tout filtré ; il
# ne reste qu'à RANGER. Le serveur y appelait `_best_time`, dont la branche 3
# est le `mtime` — la source que le filtre d'à côté refuse explicitement
# (`annee_fiable_depuis`, décision du 15/08). Une photo sans date connue
# prenait donc la date de son dernier tagging (2026) et passait DEVANT toutes
# les autres : la seule dont la date est certainement fausse s'affichait en
# tête. Deux règles de date pour une même réponse finissent toujours par se
# contredire ; il n'y en a plus qu'une.

# Rangs de précision. L'ordre du tri est (année, rang, epoch) décroissant : à
# année égale, une photo précisément datée passe devant une photo datée par son
# seul DOSSIER — lui donner un 1er janvier la ferait passer devant un 1er
# janvier RÉEL, c'est-à-dire inventer un jour (refus du 15/08).
RANG_PRECIS, RANG_ANNEE, RANG_AUCUN = 2, 1, 0


def trier_chronologique(entrees, epoch_precis, annee_fiable):
    """Ordonne des (clé, entrée) de la plus RÉCENTE à la plus ancienne.
    Rend `(clés_triées, sans_date)`.

    `epoch_precis` et `annee_fiable` : les MÊMES lecteurs que `filtrer_periode`
    — une seule règle de date par réponse.

    `sans_date` compte les photos placées SANS aucune date sûre : elles vont en
    FIN de liste, jamais en tête. Une protection qui s'annule doit se compter,
    sinon la dégradation est muette.

    Le tri ne jette rien — pas même une entrée `failed` : filtrer est le travail
    de `filtrer_periode`, ranger est le sien. Les ex æquo gardent l'ordre reçu
    (`sorted` stable) : l'appelant passe ses clés triées, et la même requête
    rend deux fois la même page.
    """
    rangs = []
    sans_date = 0
    for cle, entree in entrees:
        e = entree if isinstance(entree, dict) else {}
        ep = None
        try:
            ep = epoch_precis(cle, e)
        except Exception:                                     # noqa: BLE001
            ep = None
        if ep is not None:
            try:
                an = time.localtime(float(ep)).tm_year
                rangs.append(((an, RANG_PRECIS, float(ep)), cle))
                continue
            except (ValueError, TypeError, OverflowError, OSError):
                pass
        try:
            an = int(annee_fiable(cle, e)) or 0
        except (TypeError, ValueError):
            an = 0
        if an:
            rangs.append(((an, RANG_ANNEE, 0.0), cle))
        else:
            sans_date += 1
            rangs.append(((0, RANG_AUCUN, 0.0), cle))
    rangs.sort(key=lambda it: it[0], reverse=True)
    return [cle for _, cle in rangs], sans_date
