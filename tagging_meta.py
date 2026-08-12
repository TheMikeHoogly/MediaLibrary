"""Logique pure de lecture/fusion des metadonnees de tagging.

Isolee de server.py pour etre testable hors machine (aucune I/O, aucun acces
NAS ni photos.db). Reunit :

- `parse_meta_gps_item` : parse UN item JSON d'exiftool en (mots-cles,
  description, GPS). Permet au worker de tagging de lire les tags existants ET
  le GPS en UN SEUL appel exiftool au lieu de deux (une lecture NAS et un
  process de moins par photo, pendant que le GPU attend).
- `merge_named_tags` : reintegre les tags nommes humains (personne:/animal:)
  deja presents dans le fichier, pour ne JAMAIS les perdre lors d'un re-tagging
  IA. C'est l'invariant sacre du projet.

S'y ajoute le Knowledge Builder (ADOPTE 31/07, cable session 8) :

- amont : `bloc_assertions` + `prompt_tagging` construisent le prompt de prod
  V2 « assertions en contexte, SANS imperatif de noms » (ADOPTEE 12/08,
  aveugle A/B 25-15 vs V0 -- eval/DECISIONS.md). Le texte est repris VERBATIM
  de eval_tagging.prompt_v2, moins le bloc IMPERATIF : on cable ce qui a ete
  mesure, rien d'autre.
- aval : `faits_structures` produit les faits noms/date/lieu en donnees
  STRUCTUREES avec leur source (provenance) -- jamais via le prompt.

Ces fonctions n'ouvrent aucun fichier : elles operent sur des donnees deja
lues. Voir `server.read_meta_and_gps` pour l'appel exiftool reel et
`server._assertions_pour` pour l'assemblage depuis les stores.
"""
import re
import time


def norm_import_kw(k):
    """Normalise un mot-cle importe d'un fichier. Les mots-cles IA sont en
    minuscules ; on aligne dessus SAUF les tags nommes « personne:… » et
    « animal:… » dont on PRESERVE la casse (sinon « personne:Nom » deviendrait
    « personne:nom » et ne correspondrait plus au nom dans les stores)."""
    s = str(k).strip()
    low = s.lower()
    if low.startswith('personne:') or low.startswith('animal:'):
        return s
    return low


def parse_meta_gps_item(item):
    """Parse UN item JSON renvoye par exiftool en (kw_list|None, desc, gps|None).

    Reunit la logique de `read_existing_metadata` (Subject/Keywords/Description)
    et de `read_gps` (Composite GPS, valeurs numeriques signees en degres
    decimaux). Purement fonctionnel : aucun acces disque.

    - kw : liste normalisee des mots-cles existants, ou None si aucun.
    - desc : description existante (chaine, eventuellement vide).
    - gps : [lat, lon] arrondis a 1e-6, ou None si absent/invalide/(0,0).
    """
    kw = item.get("Subject") or item.get("Keywords") or []
    if isinstance(kw, str):
        kw = [kw]
    kw = [norm_import_kw(k) for k in kw if str(k).strip()] or None

    desc = item.get("Description") or ""
    if isinstance(desc, dict):                 # description localisee {lang: texte}
        desc = str(list(desc.values())[0]) if desc else ""
    desc = str(desc).strip()

    gps = None
    lat, lon = item.get("GPSLatitude"), item.get("GPSLongitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
            gps = [round(float(lat), 6), round(float(lon), 6)]
    return kw, desc, gps


def parse_exif_dt(s):
    """Convertit une date EXIF « 2018:12:11 23:01:48 » en timestamp epoch local.
    Renvoie None si absente/invalide (ou annee aberrante). Copie pure de
    server._parse_exif_dt pour rester testable hors machine."""
    if not s or not isinstance(s, str):
        return None
    m = re.match(r'\s*(\d{4}):(\d{2}):(\d{2})[ T]?(\d{2})?:?(\d{2})?:?(\d{2})?', s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    hh, mm, ss = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
    try:
        return time.mktime((y, mo, d, hh, mm, ss, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


def parse_meta_gps_taken_item(item):
    """`parse_meta_gps_item` + date de prise de vue EXIF, toujours en UN item
    exiftool (donc UNE lecture NAS). La date retenue est la plus ANCIENNE de
    DateTimeOriginal/CreateDate/ModifyDate, comme `server.read_dates` (evite
    les dates de modification faussees par le tagging).

    Renvoie (kw_list|None, desc, gps|None, taken_epoch|None)."""
    kw, desc, gps = parse_meta_gps_item(item)
    ts = [v for v in (parse_exif_dt(item.get(f))
                      for f in ("DateTimeOriginal", "CreateDate", "ModifyDate")) if v]
    return kw, desc, gps, (min(ts) if ts else None)


def merge_named_tags(kw_fr, existing_kw):
    """Reintegre dans `kw_fr` les tags nommes (personne:/animal:) presents dans
    `existing_kw` mais absents de `kw_fr`, pour ne JAMAIS perdre un nom attribue
    par un humain lors d'un re-tagging IA.

    Ordre preserve (les noms sont ajoutes a la fin), aucun doublon. Le doublon
    est juge INSENSIBLE a la casse, comme _kw_has/_index_add_person cote
    serveur : le projet documente la divergence « personne:Nom » (app) vs
    « personne:nom » (importe du fichier) — une deduplication exacte ecrirait
    les deux dans le fichier. Le premier arrive garde sa casse. Les tags non
    nommes de `existing_kw` sont ignores (le re-tagging IA regenere le reste).
    Mute et retourne `kw_fr`.
    """
    have = {str(x).lower() for x in kw_fr}
    for t in (existing_kw or []):
        tl = str(t).lower()
        if (tl.startswith('personne:') or tl.startswith('animal:')) and tl not in have:
            kw_fr.append(t)
            have.add(tl)
    return kw_fr


# ────────────────── Knowledge Builder — amont (prompt V2) ──────────────────

MOIS_FR = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet',
           'aout', 'septembre', 'octobre', 'novembre', 'decembre']


def format_date_fr(epoch):
    """« 11 decembre 2018 » -- deterministe et sans locale : strftime('%-d')
    n'existe pas sous Windows et '%B' depend de la locale du poste. Le banc
    d'eval retombait silencieusement sur l'epoch brut a cause de ca ; ici la
    date est toujours lisible. Renvoie None si l'epoch est inexploitable."""
    try:
        t = time.localtime(float(epoch))
        return f"{t.tm_mday} {MOIS_FR[t.tm_mon - 1]} {t.tm_year}"
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def noms_depuis_kw(kw):
    """Extrait des mots-cles existants les noms humains deja attribues.
    Renvoie (personnes, animaux), listes triees et dedoublonnees."""
    persons, animals = set(), set()
    for t in (kw or []):
        s = str(t)
        low = s.lower()
        if low.startswith('personne:'):
            n = s.split(':', 1)[1].strip()
            if n:
                persons.add(n)
        elif low.startswith('animal:'):
            n = s.split(':', 1)[1].strip()
            if n:
                animals.add(n)
    return sorted(persons), sorted(animals)


def bloc_assertions(a):
    """Rend les assertions en texte francais (une ligne par fait present).
    Verbatim de eval_tagging.bloc_assertions AU LIBELLE DE SOURCE PRES : le
    banc affirmait « (EXIF) » meme pour une date deduite du nom de fichier ou
    de l'annee du dossier, et « (chemin du dossier) » pour un lieu geocode —
    une provenance mensongere affirmee comme verite au modele. Ici le libelle
    suit la vraie source (date_src/lieu_src) ; a defaut, les libelles de
    l'eval."""
    L = ['Faits deja etablis sur cette photo par des modeles specialises :']
    if a.get('date'):
        src = a.get('date_src') or 'exif'
        L.append(f"- Date : {a['date']} ({'EXIF' if src == 'exif' else src})")
    if a.get('lieu'):
        src = a.get('lieu_src') or 'chemin'
        lbl = {'chemin': 'chemin du dossier', 'gps': 'geocodage GPS'}.get(src, src)
        L.append(f"- Lieu : {a['lieu']} ({lbl})")
    if a.get('persons'):
        L.append(f"- Personnes : {', '.join(a['persons'])} (reconnaissance faciale)")
    if a.get('animals'):
        sp = f" ({', '.join(a['species'])})" if a.get('species') else ""
        L.append(f"- Animaux : {', '.join(a['animals'])}{sp} (re-identification)")
    if a.get('tags_fr'):
        L.append(f"- Elements visuels deja notes : {', '.join(a['tags_fr'][:12])}")
    if len(L) == 1:
        L.append('- (aucun fait structure disponible pour cette photo)')
    return '\n'.join(L)


REGLES_JSON = (
    'Retourne UNIQUEMENT du JSON strict, rien d autre :\n'
    '{"keywords_en": ["..."], "keywords_fr": ["..."], "description_fr": "..."}\n'
    'Regles : 6-10 mots-cles par langue, minuscules, 1-2 mots chacun ; '
    'espaces entre les mots, jamais de soulignes ; keywords_fr en vrai '
    'francais ; description_fr = une phrase courte en francais. '
    'Ne transcris jamais un texte, prix, recu ou panneau visible ; '
    'pour un document/recu/capture, utilise des mots generiques '
    '("document", "recu", "capture").'
)


def prompt_tagging(a):
    """Prompt de PROD : V2 « assertions en contexte, sans imperatif de noms »,
    ADOPTEE le 12/08 (aveugle A/B : 25-15 vs V0 ; 4,26 s/photo ;
    eval/DECISIONS.md). Verbatim de eval_tagging.prompt_v2 SANS le bloc
    IMPERATIF : les noms ne passent JAMAIS par le prompt en exigence -- ils
    sont fusionnes en post-traitement deterministe (merge_named_tags +
    faits_structures)."""
    return ('Analyse cette photo. Des modeles specialises ont deja etabli les '
            'faits ci-dessous : traite-les comme la verite (noms, especes, '
            'lieu, date) et complete avec ce que tu VOIS en plus.\n\n'
            + bloc_assertions(a) + '\n\n' + REGLES_JSON)


# ────────────────── Knowledge Builder — aval (provenance) ──────────────────

def faits_structures(a):
    """Fusion AVAL : les faits noms/date/lieu deviennent des donnees
    structurees portant chacune sa SOURCE -- le germe de la memoire familiale
    a provenance (« aucun fait affirme sans provenance »). Deterministe,
    jamais issu du texte du LLM.

    Renvoie une liste de {'t': type, 'v': valeur, 'src': source}, vide si
    aucun fait. Types : personne, animal, espece, lieu, date."""
    F = []
    for p in (a.get('persons') or []):
        F.append({'t': 'personne', 'v': p, 'src': a.get('noms_src') or 'xmp'})
    for n in (a.get('animals') or []):
        F.append({'t': 'animal', 'v': n, 'src': a.get('noms_src') or 'xmp'})
    for sp in (a.get('species') or []):
        F.append({'t': 'espece', 'v': sp, 'src': 'detection (yolo+siglip)'})
    if a.get('lieu'):
        F.append({'t': 'lieu', 'v': a['lieu'], 'src': a.get('lieu_src') or 'chemin'})
    if a.get('date'):
        F.append({'t': 'date', 'v': a['date'], 'src': a.get('date_src') or 'exif'})
    return F
