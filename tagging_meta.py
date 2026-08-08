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

Ces fonctions n'ouvrent aucun fichier : elles operent sur des donnees deja
lues. Voir `server.read_meta_and_gps` pour l'appel exiftool reel.
"""


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


def merge_named_tags(kw_fr, existing_kw):
    """Reintegre dans `kw_fr` les tags nommes (personne:/animal:) presents dans
    `existing_kw` mais absents de `kw_fr`, pour ne JAMAIS perdre un nom attribue
    par un humain lors d'un re-tagging IA.

    Ordre preserve (les noms sont ajoutes a la fin), aucun doublon. Les tags non
    nommes de `existing_kw` sont ignores (le re-tagging IA regenere le reste).
    Mute et retourne `kw_fr`.
    """
    for t in (existing_kw or []):
        tl = str(t).lower()
        if (tl.startswith('personne:') or tl.startswith('animal:')) and t not in kw_fr:
            kw_fr.append(t)
    return kw_fr
