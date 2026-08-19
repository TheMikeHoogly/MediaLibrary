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
import time
from functools import lru_cache

import tagging_meta
from renommage_facts import (_sans_accents, date_de_scan_presumee,
                             fname_datetime, names_from_entry, path_year,
                             path_years)

__all__ = ['chemin_relatif', 'lieu_plausible', 'candidats_du_segment',
           'lieux_du_chemin', 'lieu_par_segments', 'lieu_pour', 'epoch_du_nom',
           'date_credible', 'taken_credible', 'date_et_source', 'assertions',
           'faits', 'OPTIONS_AVANT_14A']


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


def _nettoyer_segment(nom):
    """Segment débarrassé de ce qui n'est jamais un lieu : préfixe numérique
    (« 240211_… »), année, numéro de tête (« 07 Voyage… »)."""
    n = re.sub(r'^\d{2,8}[-_ ]*', '', str(nom)).strip()
    n = re.sub(r'\b(19|20)\d{2}\b', '', n).strip()
    return re.sub(r'^\d{1,2}[ .\-]+', '', n).strip()


def lieu_plausible(nom, separateurs=r'[\s_\-]+'):
    """Un dossier est-il un nom de lieu ? Heuristique, corrigeable à la main.

    `separateurs` : ce qui coupe les MOTS du segment. Par défaut le trait
    d'union en fait partie — et c'est précisément ce qui fait rater
    « Crans-Montana » : le segment devient « Crans Montana », qui n'est plus la
    clé du libellé. `OPTIONS_UNIFIEE` le retire ; `candidats_du_segment` coupe
    alors les traits en DERNIER recours, pour ne rien perdre de ce que la règle
    d'aujourd'hui trouve."""
    n = _nettoyer_segment(nom)
    if len(n) < 4 or LIEUX_BRUIT.match(n):
        return None
    mots = [m for m in re.split(separateurs, n) if len(m) > 2
            and not LIEUX_BRUIT.match(m)]
    return ' '.join(mots) if mots else None


# Variantes de la règle de lieu. Elles existent pour être MESURÉES avant d'être
# adoptées (`mesure_lieu_visible.py`) : `OPTIONS_PROD` est le comportement
# d'aujourd'hui, bit pour bit ; `OPTIONS_UNIFIEE` répare les deux trous connus
# (libellés MULTI-MOTS jamais essayés, trait d'union qui casse la clé).
# Ce que la règle faisait AVANT le 19/08, gardé pour que le banc puisse encore
# mesurer l'écart — la prod, elle, n'a plus qu'un jeu d'options : les défauts.
OPTIONS_AVANT_14A = {'multi_mots': False, 'traits_separateurs': True,
                     'seuil_mot': 5, 'couper_casse': False}


# Découpe d'un mot COLLÉ : « Yani2004 » → Yani, 2004 ; « AchumaniAlto » →
# Achumani, Alto ; « CuevaMarkusIrpavi » → Cueva, Markus, Irpavi. Les dossiers
# de famille collent le lieu à l'année ou au sujet, et la comparaison par mot
# entier les perdait tous (219 photos « Yani », 48 « Achumani », 6 « Irpavi »).
# Ce qui n'a PAS de frontière interne reste entier — « Vallorbe » ne rend pas
# « Orbe », « Chatelain » ne rend pas « Châtel », « Cousins&Cousines » ne rend
# pas « Ins ». C'est toute la différence avec la sous-chaîne.
_MOT_COLLE = re.compile(r"[A-ZÀ-Þ]+(?![a-zà-þ])|[A-ZÀ-Þ]?[a-zà-þ]+|\d+")

# Longueur maximale, en MOTS, d'un groupe essayé. Aucun libellé connu n'en
# compte plus de quatre (« Playa de las Américas », « Banyuls de la Marenda ») ;
# cinq laisse une marge. Sans cette borne, le nombre de groupes croît au CARRÉ
# du nombre de mots — et un nom de fichier renommé en compte dix (mesuré :
# 0,33 s pour l'index entier deviennent 0,89 s). Le segment ENTIER reste
# toujours essayé, quelle que soit sa longueur.
_MAX_MOTS_GROUPE = 5


@lru_cache(maxsize=8192)
def candidats_du_segment(nom, multi_mots=True, traits_separateurs=False,
                         seuil_mot=4, couper_casse=True):
    """Libellés à ESSAYER pour un segment de dossier, du plus spécifique au
    moins. Liste ordonnée, sans doublon — vide si le segment n'est pas un lieu
    plausible.

    Tous ces candidats sont comparés ENTIERS à l'index des lieux (une clé de
    dict). C'est l'invariant du module : jamais de sous-chaîne, sans quoi
    « Ins » retrouve « Cousins&Cousines ».

    `multi_mots` : essayer aussi les groupes de mots CONTIGUS, du plus long au
    plus court, formés sur les mots BRUTS du segment — y compris les articles
    de deux lettres que `lieu_plausible` écarte. Sans ces groupes, un libellé
    en plusieurs mots n'est essayé que si le segment ne dit QUE lui : « Okt
    Frankfurt La Paz » ne rend rien, et « La » ne survit pas au nettoyage.
    `seuil_mot` : longueur minimale d'un mot ISOLÉ — en dessous, un mot court
    noie le chemin de faux positifs (le groupe, lui, n'a pas ce risque).
    `couper_casse` : découper aussi les mots COLLÉS sur leurs frontières de
    casse et de chiffres (`_MOT_COLLE`). Sans lui, « Yani2004 » et
    « AchumaniAlto » ne rendent rien : les dossiers de famille collent le lieu
    à l'année ou au sujet.

    **Mémoïsée, et c'est ce qui la rend payable** : `/sujets` et la recherche
    balaient 43 064 clés, mais celles-ci se partagent quelques milliers de
    segments — « Photos », « 2007 », « 04 Avril » reviennent des centaines de
    fois. Le résultat est un tuple : une valeur de cache ne se mute pas.

    Un NOM DE FICHIER, lui, est unique : le mémoïser ne sert à rien et EXPULSE
    les dossiers du cache (43 064 noms contre 8 192 places — mesuré : 0,28 s
    devenaient 0,83 s). `lieux_du_chemin` l'appelle donc sans cache."""
    return _candidats_du_segment(nom, multi_mots, traits_separateurs,
                                 seuil_mot, couper_casse)


def _candidats_du_segment(nom, multi_mots, traits_separateurs, seuil_mot,
                          couper_casse):
    """Le corps de `candidats_du_segment`, hors cache."""
    n = _nettoyer_segment(nom)
    if len(n) < 4 or LIEUX_BRUIT.match(n):
        return []
    sep = r'[\s_\-]+' if traits_separateurs else r'[\s_]+'
    bruts = [m for m in re.split(sep, n) if m]
    mots = [m for m in bruts if len(m) > 2 and not LIEUX_BRUIT.match(m)]
    if not mots:
        return []
    out = [' '.join(mots)]
    if multi_mots:
        for taille in range(min(len(bruts), _MAX_MOTS_GROUPE), 1, -1):
            for i in range(len(bruts) - taille + 1):
                out.append(' '.join(bruts[i:i + taille]))
    out += [m for m in mots if len(m) >= seuil_mot]
    if not traits_separateurs:
        # Le trait d'union n'est plus un séparateur de MOTS (« Crans-Montana »
        # reste entier), mais il reste un séparateur de DERNIER recours :
        # « Vacances-Crète » doit continuer de rendre « Crète ».
        for m in mots:
            for sm in re.split(r"[\-']+", m):
                if len(sm) >= seuil_mot:
                    out.append(sm)
    if couper_casse:
        for m in bruts:
            morceaux = _MOT_COLLE.findall(m)
            if len(morceaux) > 1:
                for i in range(len(morceaux)):
                    fin = min(len(morceaux), i + _MAX_MOTS_GROUPE)
                    for j in range(fin, i, -1):
                        c = ' '.join(morceaux[i:j])
                        if len(c) >= seuil_mot:
                            out.append(c)
    vus, uniq = set(), []
    for c in out:
        if c and c not in vus:
            vus.add(c)
            uniq.append(c)
    return tuple(uniq)


def lieux_du_chemin(cle, lieux, racines=(), tous=False, avec_fichier=False,
                    **options):
    """Libellés que le CHEMIN désigne, du dossier le plus PROFOND au plus haut.

    `tous=False` s'arrête au premier : le fait « lieu » d'une photo n'en porte
    qu'un, et « Photos / Espagne / Barcelone » est une photo de Barcelone.
    `tous=True` les rend TOUS — c'est ce dont ont besoin `/sujets` et la
    recherche, qui ne répondent pas à la même question : ils comptent une photo
    dans CHAQUE lieu qu'elle désigne, et cherchent un lieu parmi plusieurs.
    Une seule règle, deux façons de la lire.

    `avec_fichier` : le NOM DU FICHIER compte-t-il comme un segment ? Non par
    défaut — un fait « lieu » se lit dans les dossiers, et le renommage ÉCRIT
    des lieux dans les noms (circularité). Mais 127 photos ne nomment leur lieu
    que là (« 20km de Lausanne.jpg »), et « Trinidad » n'existe que par ce
    chemin : c'est une décision, pas une évidence.

    `lieux` : {libellé sans accents: libellé} — `server.lieux_connus()` ou
    `renommage_facts.load_lieux(...)`, c'est le même fichier."""
    if not lieux:
        return []
    parts = chemin_relatif(cle, racines).replace('/', '\\').split('\\')
    if avec_fichier:
        # Sans son extension : « 20km de Lausanne.jpg » finit sinon sur le mot
        # « lausanne.jpg », qui n'est la clé de rien.
        parts = parts[:-1] + [re.sub(r'\.[A-Za-z0-9]{1,5}$', '', parts[-1])]
    else:
        parts = parts[:-1]
    out, vus = [], set()
    for i, p in enumerate(reversed(parts)):
        # i == 0 et `avec_fichier` : c'est le NOM DE FICHIER, unique — hors
        # cache, sinon il expulse les dossiers (voir `candidats_du_segment`).
        cands = (_candidats_du_segment(
            p, options.get('multi_mots', True),
            options.get('traits_separateurs', False),
            options.get('seuil_mot', 4), options.get('couper_casse', True))
            if (i == 0 and avec_fichier) else candidats_du_segment(p, **options))
        for cand in cands:
            lbl = lieux.get(_sans_accents(cand))
            if lbl and lbl not in vus:
                vus.add(lbl)
                out.append(lbl)
                if not tous:
                    return out
    return out


def lieu_par_segments(cle, lieux, racines=(), **options):
    """Lieu déduit du CHEMIN, segment par segment — la règle du Knowledge
    Builder, et la seule qu'on veuille : le PREMIER de `lieux_du_chemin`.

    Le dossier le plus PROFOND gagne : « Photos / Espagne / Barcelone » est une
    photo de Barcelone. Chaque segment est d'abord nettoyé (`lieu_plausible`),
    puis ses candidats (`candidats_du_segment`) sont cherchés dans `lieux` — un
    DICT : la comparaison est une clé, donc un MOT ENTIER. C'est toute la
    différence avec `renommage_facts.resolve_path_place`, qui teste
    `norm in dossier` et trouve « Ins » dans « Cousins&Cousines »."""
    l = lieux_du_chemin(cle, lieux, racines, tous=False, **options)
    return l[0] if l else None


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


def date_credible(cle, epoch):
    """Cette date PRÉCISE peut-elle être crue pour cette photo ?

    Faux quand c'est la date du SCAN : le numériseur inscrit l'instant du scan
    dans `DateTimeOriginal` **et** dans le nom du fichier, et l'index l'a gardé
    — une photo de `Photos Papa\\1990\\1990_Achumani` sort au 1er mai 2007.
    Mesuré le 19/08 : **72** photos en base, +2 à +32 ans au-delà de leur
    dossier.

    Le critère est celui du renommage depuis le 17/08
    (`renommage_facts.date_de_scan_presumee`), IMPORTÉ et non recopié — sans
    quoi le projet aurait une quatrième règle de date. Il est ASYMÉTRIQUE à
    dessein : une date ANTÉRIEURE au dossier est au contraire l'EXIF qui corrige
    un dossier d'import, et elles sont **1 347** — un garde-fou symétrique
    ferait dix-huit fois plus de dégâts que de bien.

    **Rien n'est écrit** : corriger `taken` en base graverait une déduction
    par-dessus une LECTURE de l'EXIF, et lui ferait perdre sa provenance. Comme
    pour `faits` le 19/08, la correction est une VUE."""
    try:
        annee = time.localtime(float(epoch)).tm_year
    except (ValueError, TypeError, OverflowError, OSError):
        return False
    return not date_de_scan_presumee(annee, path_years(cle))


def taken_credible(cle, entree):
    """Le `taken` de l'index, ou None s'il porte la date du SCAN."""
    t = entree.get('taken') if isinstance(entree, dict) else None
    if not (isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0):
        return None
    return float(t) if date_credible(cle, t) else None


def date_et_source(cle, entree):
    """(libellé, source) de la date : `taken` (exif) → date lue dans le NOM →
    année du DOSSIER, **la date du SCAN écartée des deux premières**
    (`date_credible`, 72 photos). **Jamais le `mtime`** — il porte la date du TAGGING, pas
    celle de la prise de vue (une photo de 1998 réécrite en 2026). Une date
    fausse affirmée est une graine d'hallucination, pas un fait : mieux vaut
    rien."""
    t = taken_credible(cle, entree)
    if t:
        return tagging_meta.format_date_fr(t), 'exif'
    fn = epoch_du_nom(cle)
    if fn and date_credible(cle, fn):
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
