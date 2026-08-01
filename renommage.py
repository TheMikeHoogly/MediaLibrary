#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renommage intelligent — coeur DETERMINISTE (assemblage + assainissement).
──────────────────────────────────────────────────────────────────────────────

Ce module ne fait qu'UNE chose : transformer les FAITS deja connus d'une photo
(date, lieu/type, noms humains, description) en un nom de fichier lisible,
chronologique et sur pour Windows/SMB. Il n'ouvre aucun fichier, n'appelle aucun
modele, ne touche ni au NAS ni a l'index. C'est la brique « assemblage du nom
depuis les assertions » de la spec (docs/RANGEMENT_2026.md, « Renommage
intelligent ») — la seule partie qu'on peut ecrire et prouver sans rien muter.

    Format :  YYYYMMDD_<lieu-ou-type>_<sujet>.<ext>
      _  separe les trois champs ;  -  separe les mots dans un champ.
      Tri lexicographique == chronologique grace a YYYYMMDD (8 chiffres).

L'APPLICATION (renommage reel sur le NAS + re-cle via rekey_everywhere +
journal de provenance + undo) est un AUTRE etage, volontairement pas ici : il
mute le NAS, donc il attend la fin du recensement et une revue. Ce module lui
fournira les noms.

Decisions (defauts proposes dans la spec, appliques ici ; a confirmer par Mike) :
  - champ SUJET : conserve la casse des noms propres (Luna, Claudia-Binaki) ;
    lieu/type et sujet tire d'une description sont en minuscules.
  - plafond : nom complet (extension comprise) <= 120 caracteres, le champ
    sujet est tronque sur une frontiere de mot (« - »).
  - pas de date fiable -> champ date « 00000000 » (regroupe et signale les
    indates en tete de tri ; aucune date inventee, pas de SANSDATE separe).
  - noms multiples -> tries, uniques, joints par « -et- », plafonnes a 3 (au
    dela : « -et-al »).
  - collision de nom -> suffixe « -<4 hex du sha256 d'une graine> » (la graine
    est fournie par l'appelant : chemin d'origine ou hash de contenu).

Aucun import lourd : stdlib pure, importable a tout moment (invariant « zero
dependance au demarrage »).
"""

import hashlib
import re
import unicodedata

# ── Assainissement ASCII ─────────────────────────────────────────────────────
# NFKD retire la plupart des diacritiques ; cette table couvre les cas que la
# decomposition ne traite pas (ligatures, lettres barrees).
_ASCII_MAP = {
    'œ': 'oe', 'Œ': 'OE', 'æ': 'ae', 'Æ': 'AE',
    'ø': 'o', 'Ø': 'O', 'ß': 'ss', 'ẞ': 'SS',
    'đ': 'd', 'Đ': 'D', 'ł': 'l', 'Ł': 'L',
    'þ': 'th', 'Þ': 'Th', 'ð': 'd', 'Ð': 'D',
}

# Caracteres interdits dans un nom de fichier Windows, plus les separateurs.
_FORBIDDEN = set('/\\:*?"<>|')

# Noms de peripheriques reserves par Windows (insensibles a la casse, sans ext).
_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}

_DATE8_RE = re.compile(r'^\d{8}(?:-\d{6})?_')   # « YYYYMMDD_ » ou « YYYYMMDD-HHMMSS_ »


def to_ascii(s):
    """Repli ASCII sur du texte : table de ligatures puis NFKD sans diacritiques."""
    if not s:
        return ''
    out = []
    for ch in str(s):
        if ch in _ASCII_MAP:
            out.append(_ASCII_MAP[ch])
        else:
            out.append(ch)
    s = ''.join(out)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    # tout ce qui n'est pas ASCII imprimable restant est retire par le slug.
    return s


def slug_field(s, lower=False):
    """Un champ -> mots ASCII joints par « - ». Chars interdits, ponctuation,
    espaces et non-ASCII deviennent des separateurs ; les « - » multiples sont
    reduits ; pas de « - » en bord. Vide -> ''."""
    s = to_ascii(s)
    # remplace tout ce qui n'est ni lettre/chiffre ASCII par un espace-frontiere
    s = ''.join(c if (c.isascii() and c.isalnum()) else ' ' for c in s)
    mots = [m for m in s.split() if m]
    slug = '-'.join(mots)
    if lower:
        slug = slug.lower()
    return slug


def _avoid_reserved(stem):
    """Un radical qui EST un nom reserve Windows est prefixe pour le neutraliser."""
    if stem.upper() in _RESERVED:
        return '_' + stem
    return stem


# ── Champs ───────────────────────────────────────────────────────────────────

def field_date(date8):
    """Champ 1, calcule par l'appelant (_best_time / resolve_datestamp cote
    serveur). Accepte « YYYYMMDD » ou « YYYYMMDD-HHMMSS » (heure = ordre
    intra-journee des rafales). Tout le reste -> « 00000000 »."""
    if isinstance(date8, str) and re.fullmatch(r'\d{8}(?:-\d{6})?', date8):
        return date8
    return '00000000'


def field_place_or_type(gps_place=None, path_place=None, human_place=None,
                        image_type=None):
    """Champ 2, par ordre de confiance decroissant : GPS inverse > lieu deduit
    du chemin > tag humain de lieu > type d'image (vocabulaire SigLIP). En
    minuscules. Vide si vraiment rien (l'appelant decidera d'un repli)."""
    for cand in (gps_place, path_place, human_place, image_type):
        s = slug_field(cand, lower=True)
        if s:
            return s
    return ''


# Articles en tete a retirer d'un sujet tire de description (« un lac… » -> « lac… »)
# et connecteurs a ne pas laisser EN FIN de slug (« …-de » est laid). Les
# connecteurs INTERNES sont conserves pour la lisibilite (« lac-au-couchant »).
_ART_FR = {'un', 'une', 'le', 'la', 'les', 'des', 'de', 'du', 'd', 'l'}
_STOP_TAIL = _ART_FR | {'au', 'aux', 'en', 'et', 'a', 'avec', 'sur', 'dans',
                        'pour', 'par', 'sous', 'sans', 'chez', 'vers', 'entre',
                        'the', 'of', 'and', 'with', 'in', 'on', 'at', 'to',
                        'from', 'for', 'by'}


def _distill(text, max_words=5):
    """Slug COURT tire d'une description : minuscule, sans articles en tete ni
    connecteur en fin, plafonne a `max_words` mots. « Un lac au couchant » ->
    « lac-au-couchant » ; une phrase entiere -> ses premiers mots porteurs."""
    mots = [m for m in slug_field(text, lower=True).split('-') if m]
    while mots and mots[0] in _ART_FR:
        mots.pop(0)
    mots = mots[:max_words]
    while mots and mots[-1] in _STOP_TAIL:
        mots.pop()
    return '-'.join(mots)


def field_subject(names=None, description=None, max_names=3):
    """Champ 3 : noms humains d'abord (fait le plus fiable, casse conservee),
    sinon un slug court DISTILLE de la description (minuscules).

    `names` : liste de noms deja DEPOUILLES du prefixe (« Luna », pas
    « animal:Luna »). Tries, uniques, joints par « -et- », plafonnes a
    `max_names` puis suffixe « -et-al »."""
    slugs = []
    seen = set()
    for n in (names or []):
        sl = slug_field(n, lower=False)
        if sl and sl.lower() not in seen:
            seen.add(sl.lower())
            slugs.append(sl)
    if slugs:
        slugs.sort(key=str.lower)
        if len(slugs) > max_names:
            return '-et-'.join(slugs[:max_names]) + '-et-al'
        return '-et-'.join(slugs)
    return _distill(description)


# ── Assemblage ───────────────────────────────────────────────────────────────

def _strip_name_prefix(tag):
    """« personne:Luna » / « animal:Inti » -> « Luna » / « Inti »."""
    if ':' in tag:
        return tag.split(':', 1)[1]
    return tag


def clean_ext(ext):
    """Extension -> minuscule ASCII sans point ni caractere douteux."""
    ext = to_ascii(ext or '').lstrip('.')
    ext = ''.join(c for c in ext if c.isascii() and c.isalnum())
    return ext.lower()


def _truncate_subject(subject, budget):
    """Tronque le sujet a `budget` caracteres sur une frontiere de mot (« - »).
    Si le premier mot deja depasse, coupe dur (mieux qu'un nom vide)."""
    if len(subject) <= budget:
        return subject
    if budget <= 0:
        return ''
    coupe = subject[:budget]
    if '-' in coupe:
        coupe = coupe.rsplit('-', 1)[0]
    return coupe or subject[:budget]


def assemble(date8, place_or_type, subject, ext, max_len=120):
    """Assemble et plafonne. Seul le SUJET est tronque (date et lieu/type sont
    courts et porteurs). Renvoie le nom de base final (sans collision suffix).

    Un champ vide n'introduit pas de « __ » : les champs vides sont omis, mais
    la date est toujours presente (« 00000000 » au pire)."""
    date8 = field_date(date8)
    ext = clean_ext(ext)
    place_or_type = place_or_type or ''
    subject = subject or ''

    fixe = date8 + ('_' + place_or_type if place_or_type else '')
    suffixe_ext = ('.' + ext) if ext else ''
    # budget restant pour « _<sujet> »
    budget = max_len - len(fixe) - len(suffixe_ext) - 1  # 1 pour le « _ »
    sujet = _truncate_subject(subject, budget) if subject else ''

    champs = date8
    if place_or_type:
        champs += '_' + place_or_type
    if sujet:
        champs += '_' + sujet

    champs = _avoid_reserved(champs)
    return champs + suffixe_ext


def collision_suffix(basename, seed):
    """Insere « -<4 hex du sha256(seed)> » avant l'extension. `seed` doit etre
    stable et discriminant (chemin d'origine, ou hash de contenu)."""
    h = hashlib.sha256(str(seed).encode('utf-8')).hexdigest()[:4]
    if '.' in basename:
        stem, ext = basename.rsplit('.', 1)
        return f'{stem}-{h}.{ext}'
    return f'{basename}-{h}'


def is_already_renamed(basename, provenance_seen=False):
    """Idempotence : un fichier deja au format (« ^\\d{8}_ ») ET marque comme
    auto-renomme dans la provenance ne doit pas etre re-prefixe. Le second
    critere protege un fichier d'origine qui commencerait par hasard par 8
    chiffres + « _ » (photos d'appareil : « 20190704_123045.jpg »)."""
    return bool(_DATE8_RE.match(basename)) and provenance_seen


# ── Orchestration ────────────────────────────────────────────────────────────

def propose_basename(facts, taken=None):
    """Fabrique le nom propose depuis un dict de FAITS deja resolus par
    l'appelant (le serveur : _best_time, lieux.txt, GPS, SigLIP, tags).

    Cles attendues (toutes optionnelles sauf `ext`) :
        date8, gps_place, path_place, human_place, image_type,
        names (liste, prefixe « personne:/animal: » toleree),
        description, ext, seed (graine anti-collision : chemin d'origine).

    `taken` : ensemble de noms de base deja pris dans le dossier cible ; si le
    nom propose y figure, on ajoute le suffixe de collision.

    Ne fabrique JAMAIS un nom vide : sans lieu/type ni sujet, il reste au moins
    « YYYYMMDD.ext ». Renvoie le nom de base (str)."""
    names = [_strip_name_prefix(n) for n in (facts.get('names') or [])]
    place_or_type = field_place_or_type(
        gps_place=facts.get('gps_place'),
        path_place=facts.get('path_place'),
        human_place=facts.get('human_place'),
        image_type=facts.get('image_type'))
    subject = field_subject(names=names, description=facts.get('description'))

    base = assemble(facts.get('date8'), place_or_type, subject,
                    facts.get('ext'))

    if taken and base in taken:
        seed = facts.get('seed') or base
        base = collision_suffix(base, seed)
    return base


__all__ = [
    'to_ascii', 'slug_field', 'clean_ext',
    'field_date', 'field_place_or_type', 'field_subject',
    'assemble', 'collision_suffix', 'is_already_renamed', 'propose_basename',
]
