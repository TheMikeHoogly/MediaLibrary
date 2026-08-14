#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renommage intelligent — RÉSOLVEUR DE FAITS (lecture seule de l'index).
──────────────────────────────────────────────────────────────────────────────

Le pont entre l'index et le cœur déterministe `renommage.py`. À partir d'une
ENTRÉE d'index (le dict `tags`) et de la CLÉ (le chemin), il assemble le dict
`facts` que `renommage.propose_basename` attend. Il ne lit AUCUN fichier,
n'ouvre AUCUN modèle, ne mute rien : purement de la logique sur des données déjà
présentes dans `photos.db`.

Il REFLÈTE (sans les importer) trois fonctions de `server.py` :
  - `_fname_time`  (~l. 975)  : date encodée dans le nom de fichier.
  - `_path_year`   (~l. 992)  : année trouvée dans le chemin (dossiers datés).
  - `_best_time`   (~l. 1006) : date de prise de vue par ordre de fiabilité.
  - `lieux_connus` (~l. 2021) : vocabulaire de lieux (lu de lieux.txt).

Deux faits sont laissés à l'appelant serveur (ils exigent des ressources hors de
ce module) : `gps_place` (géocodage inverse des coordonnées `e['gps']`) et
`image_type` (type SigLIP). Sans eux, le champ 2 retombe sur le lieu déduit du
chemin, puis reste vide — la résolution complète viendra côté serveur.

Politique de DATE (micro-décision, à valider) :
  - date précise (EXIF `taken` ou date dans le nom) -> « YYYYMMDD », precision='exact' ;
  - sinon année du dossier -> « YYYY0000 » (mois/jour inconnus, mais l'année
    RÉELLE est conservée et le tri reste chronologique), precision='annee' ;
  - sinon -> « 00000000 », precision='aucune'. Jamais de mtime (peu fiable) dans
    le NOM : le mtime est fausse par le tagging (voir commentaire de `_best_time`).
"""

import re
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath

# Date + heure eventuelle dans un nom (« 20260608_083049868 », « IMG_20181227 »).
# Miroir de server._fname_time : date, puis HHMMSS optionnel.
_FNAME_DT = re.compile(
    r'(19\d{2}|20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})'
    r'(?:[-_ .T]?(\d{2})[-_.]?(\d{2})[-_.]?(\d{2}))?')
_PATH_YEAR = re.compile(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)')


def _sans_accents(s):
    s = unicodedata.normalize('NFD', str(s).lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def _basename(key):
    """Dernier composant, que la clé soit en « \\ » (NAS) ou « / » (relative)."""
    return key.replace('/', '\\').split('\\')[-1]


def fname_datetime(name):
    """(« YYYYMMDD », « HHMMSS » | None) si le nom encode une date PLAUSIBLE,
    sinon (None, None). L'heure n'est rendue que si presente ET valide
    (miroir de server._fname_time, mais rend des chaines, pas un epoch)."""
    m = _FNAME_DT.search(name)
    if not m:
        return None, None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None, None
    date8 = f"{y:04d}{mo:02d}{d:02d}"
    if m.group(4) is not None:
        hh, mm, ss = int(m.group(4)), int(m.group(5)), int(m.group(6))
        if hh < 24 and mm < 60 and ss < 60:
            return date8, f"{hh:02d}{mm:02d}{ss:02d}"
    return date8, None


# Meme plancher que server.ANNEE_CHEMIN_MIN, et pour la meme raison (mesure du
# 14/08) : a 1990, un dossier « 1985 » ne rendait aucune annee, et les 714 photos
# des annees 80 partaient au renommage en « 00000000 » (precision « aucune »)
# alors que leur dossier porte l'annee en clair. Ici le nom de fichier est deja
# exclu, donc descendre le plancher n'ouvre aucun trou supplementaire.
ANNEE_CHEMIN_MIN, ANNEE_CHEMIN_MAX = 1900, 2100


def path_year(key):
    """« YYYY » de la plus ancienne année trouvée dans le CHEMIN — dossiers datés
    UNIQUEMENT, en EXCLUANT le nom de fichier. Un numéro de séquence comme
    « IMG_1998 » n'est pas une année : le scanner ferait passer 1998 avant le
    vrai dossier (2007) via `min()`, d'où une date fausse au renommage."""
    k = str(key).replace('\\', '/')
    dossier = k.rsplit('/', 1)[0] if '/' in k else ''
    yrs = [int(y) for y in _PATH_YEAR.findall(dossier)
           if ANNEE_CHEMIN_MIN <= int(y) <= ANNEE_CHEMIN_MAX]
    return f"{min(yrs):04d}" if yrs else None


def resolve_datestamp(key, entry):
    """(datestamp, precision). datestamp = « YYYYMMDD » ou « YYYYMMDD-HHMMSS »
    quand l'heure est connue (elle préserve l'ordre INTRA-JOURNEE des rafales et
    réduit les collisions). Voir la politique de date dans l'en-tête."""
    # 1) EXIF sauvegarde ('taken', epoch) -> date + heure
    t = entry.get('taken') if isinstance(entry, dict) else None
    if isinstance(t, (int, float)) and t > 0:
        import time as _t
        lt = _t.localtime(t)
        return (f"{lt.tm_year:04d}{lt.tm_mon:02d}{lt.tm_mday:02d}"
                f"-{lt.tm_hour:02d}{lt.tm_min:02d}{lt.tm_sec:02d}"), 'exact'
    # 2) date (+ heure eventuelle) dans le nom de fichier
    d, hms = fname_datetime(_basename(key))
    if d:
        return (f"{d}-{hms}" if hms else d), 'exact'
    # 3) annee du dossier -> YYYY0000 (pas d'heure)
    y = path_year(key)
    if y:
        return f"{y}0000", 'annee'
    return '00000000', 'aucune'


def names_from_entry(entry):
    """Tags de nom humain (« personne:… » / « animal:… ») de l'entrée tags,
    ordre stable, sans doublon."""
    out, seen = [], set()
    if isinstance(entry, dict):
        for fld in ('kw_fr', 'kw_en'):
            for t in entry.get(fld) or []:
                if isinstance(t, str) and (t.startswith('personne:')
                                           or t.startswith('animal:')):
                    if t not in seen:
                        seen.add(t)
                        out.append(t)
    return out


def load_lieux(path):
    """{lieu_sans_accents: libelle} depuis lieux.txt (miroir de la BRANCHE
    LECTURE de server.lieux_connus — on ne REGÉNÈRE jamais ici). `path` est un
    Path ; renvoie {} s'il est absent."""
    index = {}
    try:
        for l in path.read_text(encoding='utf-8').splitlines():
            l = l.split('#')[0].strip()
            if l:
                index[_sans_accents(l)] = l
    except OSError:
        pass
    return index


def _media_relative_dir(key):
    """Partie DOSSIER du chemin, débarrassée du préfixe serveur/partage. Un
    chemin UNC « \\\\NAS-Bremblens\\home\\Photos\\… » ne doit PAS livrer son
    HÔTE (« NAS-Bremblens ») comme lieu — sinon « Bremblens » colle à toutes les
    photos. On retire donc « \\\\hôte\\partage » (esprit de
    server._chemin_relatif : matcher sur le chemin relatif à la racine média)."""
    p = key.replace('/', '\\')
    unc = p.startswith('\\\\')
    parts = [c for c in p.split('\\') if c]
    if parts:
        parts = parts[:-1]                 # retire le nom de fichier
    if unc:
        parts = parts[2:]                  # retire hôte + partage
    # Les dossiers SYSTEME/TRANSIT du projet sont prefixes « _ » (_Uploads,
    # _A TRIER, _SANS_DATE) : jamais des lieux. Sans ca, « _Uploads » matchait
    # une entree parasite « Upload » de lieux.txt et collait a 835 photos.
    parts = [c for c in parts if not c.startswith('_')]
    return _sans_accents('\\'.join(parts))


def resolve_path_place(key, lieux):
    """Libellé de lieu dont la forme sans accents apparaît dans le DOSSIER
    (hors nom de fichier ET hors préfixe serveur/partage). En cas de plusieurs,
    le libellé le plus long (le plus spécifique). None si rien."""
    if not lieux:
        return None
    dossier = _media_relative_dir(key)
    best = None
    for norm, label in lieux.items():
        if norm and norm in dossier:
            if best is None or len(label) > len(best):
                best = label
    return best


def ext_of(key):
    name = _basename(key)
    return name.rsplit('.', 1)[1] if '.' in name else ''


# Mots ANGLAIS fréquents dans les descriptions IA (qwen déborde parfois en
# anglais). Sert à repérer une description anglaise pour la remplacer par les
# mots-clés FRANÇAIS (choix Mike, 03/08 : forcer le français dans les noms).
_EN_STOP = {
    'the', 'a', 'an', 'of', 'with', 'and', 'on', 'in', 'at', 'is', 'are',
    'view', 'landscape', 'mountain', 'mountains', 'panoramic', 'panorama',
    'scene', 'image', 'photo', 'picture', 'person', 'people', 'man', 'woman',
    'trees', 'sky', 'water', 'snow', 'covered', 'serene', 'dense', 'small',
    'large', 'blue', 'green', 'white', 'landscapes', 'clouds', 'field',
}


def _looks_english(text):
    """Heuristique conservatrice : au moins DEUX mots anglais courants → on
    considère la description comme anglaise. Le français en a rarement deux."""
    mots = re.findall(r'[a-zA-Z]+', str(text).lower())
    return sum(1 for m in mots if m in _EN_STOP) >= 2


def _french_keywords(entry):
    """Mots-clés FRANÇAIS de l'entrée (kw_fr), hors tags de nom (personne:/
    animal:), pour reconstruire un sujet français quand la description déborde
    en anglais. Renvoie les 3 premiers (ordre de l'index)."""
    out = []
    if isinstance(entry, dict):
        for t in (entry.get('kw_fr') or []):
            if (isinstance(t, str) and not t.startswith('personne:')
                    and not t.startswith('animal:')):
                out.append(t)
    return out[:3]


def resolve_facts(key, entry, lieux=None, gps_place=None, image_type=None):
    """Assemble le dict `facts` pour `renommage.propose_basename`.

    Lecture seule. `gps_place` et `image_type` sont fournis par l'appelant
    serveur quand il les a (géocodage inverse, SigLIP) ; None ici sinon.
    La clé d'origine sert de graine anti-collision (`seed`).

    Sujet en FRANÇAIS : si la description IA déborde en anglais ET que des
    mots-clés français existent, on prend ceux-ci à la place (choix Mike, 03/08)."""
    datestamp, precision = resolve_datestamp(key, entry)
    description = entry.get('desc') if isinstance(entry, dict) else None
    if description and _looks_english(description):
        fr = _french_keywords(entry)
        if fr:
            description = ' '.join(fr)
    facts = {
        'date8': datestamp,           # « YYYYMMDD » ou « YYYYMMDD-HHMMSS »
        'gps_place': gps_place,
        'path_place': resolve_path_place(key, lieux),
        'human_place': None,          # tag humain de lieu : brancher si dispo
        'image_type': image_type,
        'names': names_from_entry(entry),
        'description': description,    # français forcé si l'IA a débordé en anglais
        'ext': ext_of(key),
        'seed': key,
        '_date_precision': precision,  # meta, ignoré par propose_basename
    }
    return facts


__all__ = [
    'fname_datetime', 'path_year', 'resolve_datestamp', 'names_from_entry',
    'load_lieux', 'resolve_path_place', 'ext_of', 'resolve_facts',
]
