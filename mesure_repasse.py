#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure 3a — que rapporterait une re-passe de tagging ? (ROADMAP point 3a)
──────────────────────────────────────────────────────────────────────────────

QUESTION POSÉE
    La passe complète vaut ~51 h GPU (43 000 entrées × 4,26 s). On ne la paie
    qu'une fois : avant de la lancer, on veut le CHIFFRE, pas l'intuition.
    Deux choses ont changé depuis que les entrées ont été taguées :
      1. le PROMPT (v0 → v2ctx) et le Knowledge Builder (kb1) ;
      2. les FAITS eux-mêmes — les backfills des 13-14/08 ont ajouté des
         milliers de dates et de GPS, le stock de visages nommés a grossi.
    Une re-passe ne rapporte QUE si l'entrée verrait aujourd'hui des faits
    qu'elle n'avait pas au moment de son tagging.

CE QUE LE SCRIPT COMPARE
    `faits` (liste {t, v, src} écrite PAR le worker au moment du tagging,
    server.py l. 1817-1821) contre les faits que `_assertions_pour` produirait
    AUJOURD'HUI pour la même clé. Aucun modèle, aucun GPU, aucune lecture NAS :
    tout vient de photos.db, de lieux.txt et de la clé elle-même.

LECTURE SEULE, SUR UNE COPIE
    Le serveur est l'écrivain unique de `photos.db` (CLAUDE.md, règle 4) : on
    copie la base (+ -wal, -shm) dans un dossier temporaire, on vérifie son
    intégrité, on mesure sur la copie, on la jette. La base vivante n'est
    jamais ouverte, même en lecture — pas de -shm à recréer sous son nez.

APPROXIMATIONS ASSUMÉES (les dire plutôt que les cacher)
    - `_chemin_relatif` du serveur retire la racine média lue en config ; ici on
      retire « \\\\hôte\\partage » d'un chemin UNC. Même effet sur les clés NAS
      (le nom du serveur, « NAS-Bremblens », ne doit pas livrer « Bremblens »
      comme lieu), sans avoir à charger la config.
    - Les noms viennent des fiches personnes/animaux et des mots-clés de
      l'entrée (miroir de `_noms_attendus`), pas d'une relecture XMP du fichier :
      c'est la source EN MÉMOIRE qui fait autorité au moment d'une re-passe, et
      elle n'exige pas 43 000 lectures NAS.
    - `gps_place` n'est pas activé (gps_places.json absent) : les faits « lieu »
      d'origine GPS valent 0 aujourd'hui. Le script les compte à part, en
      POTENTIEL — c'est le rendement du bat 18, pas celui de la re-passe.

USAGE
    python mesure_repasse.py [--db CHEMIN] [--json SORTIE] [--exemples N]
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import tagging_meta          # noqa: E402  (pur, aucune I/O)
import renommage_facts       # noqa: E402  (pur, aucune I/O)

SECONDES_PAR_PHOTO = 4.26     # mesuré à l'adoption de v2ctx (eval/DECISIONS.md)


# ─────────────────────────── copie sûre de la base ───────────────────────────

def copier_base(db):
    """Copie `photos.db` et ses annexes WAL dans un dossier temporaire.

    L'ordre .db → -wal → -shm est celui que SQLite sait rattraper : une frame
    de WAL copiée à moitié est rejetée par sa somme de contrôle, donc au pire
    on perd la ou les toutes dernières transactions — jamais la cohérence.
    """
    db = Path(db)
    if not db.exists():
        raise SystemExit(f"Base introuvable : {db}")
    tmp = Path(tempfile.mkdtemp(prefix="mesure_repasse_"))
    cible = tmp / db.name
    total = 0
    for suffixe in ("", "-wal", "-shm"):
        src = Path(str(db) + suffixe)
        if src.exists():
            shutil.copy2(src, str(cible) + suffixe)
            total += src.stat().st_size
    return cible, tmp, total


def charger_table(cx, table):
    """{clé: dict} d'une table de SqliteStore (les vecteurs restent en BLOB —
    on ne relit que le JSON, donc aucun embedding n'est chargé)."""
    out = {}
    try:
        cur = cx.execute(f'SELECT k, v FROM "{table}"')
    except sqlite3.Error:
        return out
    for k, v in cur:
        try:
            e = json.loads(v)
        except (ValueError, TypeError):
            continue
        if isinstance(e, dict):
            out[k] = e
    return out


# ─────────────────── miroirs des fonctions pures de server.py ────────────────

_LIEUX_BRUIT = re.compile(
    r'^(?:\d+|camera|dcim|photos?|images?|divers|screenshots?|whatsapp'
    r'|samsung|iphone|xiaomi|huawei|pixel|sauvegardes?|export\w*)$', re.I)


def _sans_accents(s):
    s = unicodedata.normalize('NFD', str(s).lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def _lieu_plausible(nom):
    """Miroir de server._lieu_plausible (l. 2949)."""
    n = re.sub(r'^\d{2,8}[-_ ]*', '', str(nom)).strip()
    n = re.sub(r'\b(19|20)\d{2}\b', '', n).strip()
    n = re.sub(r'^\d{1,2}[ .\-]+', '', n).strip()
    if len(n) < 4 or _LIEUX_BRUIT.match(n):
        return None
    mots = [m for m in re.split(r'[\s_\-]+', n) if len(m) > 2
            and not _LIEUX_BRUIT.match(m)]
    return ' '.join(mots) if mots else None


def _parties_dossier(key):
    """Composants de DOSSIER de la clé, hôte et partage UNC retirés."""
    p = str(key).replace('/', '\\')
    unc = p.startswith('\\\\')
    parts = [c for c in p.split('\\') if c]
    if parts:
        parts = parts[:-1]
    if unc:
        parts = parts[2:]
    return parts


def lieu_pour_cle(key, lieux, gps_places):
    """Miroir de server._lieu_pour_cle : géocodage précalculé d'abord, sinon
    lieu déduit du chemin. Renvoie (libellé, source) ou (None, None)."""
    g = gps_places.get(key)
    if g:
        return g, 'gps'
    if lieux:
        for p in reversed(_parties_dossier(key)):
            lieu = _lieu_plausible(p)
            if not lieu:
                continue
            for cand in [lieu] + [m for m in lieu.split() if len(m) >= 5]:
                if _sans_accents(cand) in lieux:
                    return lieux[_sans_accents(cand)], 'chemin'
    return None, None


def date_pour_cle(key, entry):
    """Miroir de la branche DATE de server._assertions_pour : EXIF sauvegardé,
    puis date du nom de fichier, puis année du dossier. Jamais de mtime."""
    taken = entry.get('taken')
    if taken:
        return tagging_meta.format_date_fr(taken), 'exif'
    d8, hms = renommage_facts.fname_datetime(renommage_facts._basename(key))
    if d8:
        try:
            ep = time.mktime((int(d8[:4]), int(d8[4:6]), int(d8[6:8]),
                              int(hms[:2]) if hms else 12,
                              int(hms[2:4]) if hms else 0,
                              int(hms[4:6]) if hms else 0, 0, 0, -1))
            return tagging_meta.format_date_fr(ep), 'nom du fichier'
        except (ValueError, OverflowError, OSError):
            pass
    y = renommage_facts.path_year(key)
    if y:
        return str(int(y)), 'annee du dossier'
    return None, None


def noms_attendus(key, entry, people, pets):
    """Miroir de server._noms_attendus : fiches personnes/animaux (faces /
    exclude) + tags nommés déjà portés par l'entrée. `exclude` fait autorité."""
    tags, exclus = [], set()
    for store, prefix in ((people, 'personne'), (pets, 'animal')):
        for pe in store.values():
            nom = pe.get('name')
            if not nom:
                continue
            tag = f"{prefix}:{nom}"
            if key in set(pe.get('exclude') or []):
                exclus.add(tag.lower())
                continue
            for kf in (pe.get('faces') or []):
                if isinstance(kf, (list, tuple)) and len(kf) == 2 and kf[0] == key:
                    tags.append(tag)
                    break
    for t in (entry.get('kw_fr') or []):
        tl = str(t).lower()
        if ((tl.startswith('personne:') or tl.startswith('animal:'))
                and tl not in exclus):
            tags.append(t)
    return tags, exclus


def faits_aujourdhui(key, entry, ctx):
    """Faits que `_assertions_pour` + `faits_structures` produiraient MAINTENANT.
    Même format que `entry['faits']` : [{'t','v','src'}]."""
    tags, _exclus = noms_attendus(key, entry, ctx['people'], ctx['pets'])
    persons, animals = tagging_meta.noms_depuis_kw(tags)
    ae = ctx['animals'].get(key) or {}
    especes = sorted({a.get('species') for a in (ae.get('animals') or [])
                      if a.get('species')})
    lieu, lieu_src = lieu_pour_cle(key, ctx['lieux'], ctx['gps_places'])
    date_txt, date_src = date_pour_cle(key, entry)
    return tagging_meta.faits_structures({
        'persons': persons, 'animals': animals, 'species': especes,
        'lieu': lieu, 'lieu_src': lieu_src,
        'date': date_txt, 'date_src': date_src, 'noms_src': 'xmp'})


# ─────────────────────────────── la mesure ───────────────────────────────────

TYPES = ('date', 'lieu', 'personne', 'animal', 'espece')


def paires(faits):
    return {(f.get('t'), f.get('v')) for f in (faits or [])
            if isinstance(f, dict) and f.get('t') and f.get('v')}


def valeur(faits, t):
    for f in (faits or []):
        if isinstance(f, dict) and f.get('t') == t:
            return f.get('v')
    return None


def mesurer(tags, ctx, exemples=0):
    st = {
        'entrees': len(tags), 'echecs': 0, 'taguees': 0,
        'pipe': {},
        'sans_faits_alors': 0,
        'gagnes': {t: 0 for t in TYPES},        # entrées gagnant >=1 fait de ce type
        'changes': {t: 0 for t in TYPES},       # entrées dont le fait change de valeur
        'alors': {t: 0 for t in TYPES},
        'maintenant': {t: 0 for t in TYPES},
        'entrees_gain': 0, 'entrees_gain_v0': 0, 'entrees_gain_kb1': 0,
        'entrees_sans_aucun_fait': 0,
        'gps_sans_lieu': 0,
        'taken_present': 0,
        'date_src': {},            # d'ou vient la date qu'on donnerait en contexte
        'richesse': {},            # nb de faits en contexte -> nb d'entrees
        'strates': {},             # profil de faits -> nb d'entrees (menu de re-passe)
        'at_mois': {},             # mois du tagging -> nb d'entrees
        'exemples': [],
    }
    for key, e in tags.items():
        if e.get('failed'):
            st['echecs'] += 1
            continue
        st['taguees'] += 1
        pipe = e.get('pipe') or 'v0'
        st['pipe'][pipe] = st['pipe'].get(pipe, 0) + 1
        if e.get('taken'):
            st['taken_present'] += 1

        at = e.get('at')
        if at:
            try:
                lt = time.localtime(float(at))
                mois = f"{lt.tm_year:04d}-{lt.tm_mon:02d}"
            except (ValueError, OSError, OverflowError, TypeError):
                mois = 'illisible'
        else:
            mois = 'absent'
        st['at_mois'][mois] = st['at_mois'].get(mois, 0) + 1

        alors = e.get('faits') or []
        if not alors:
            st['sans_faits_alors'] += 1
        maintenant = faits_aujourdhui(key, e, ctx)
        if e.get('gps') and not any(f.get('t') == 'lieu' for f in maintenant):
            st['gps_sans_lieu'] += 1
        if not maintenant:
            st['entrees_sans_aucun_fait'] += 1

        # Ce que vaut le contexte qu'on donnerait AUJOURD'HUI : sa source pour la
        # date (« 2005 » deduit d'un dossier n'est pas « 19 juin 2005 » lu en EXIF)
        # et son profil, qui chiffre les re-passes CIBLEES possibles.
        _d, dsrc = date_pour_cle(key, e)
        st['date_src'][dsrc or 'aucune'] = st['date_src'].get(dsrc or 'aucune', 0) + 1
        types_m = {f.get('t') for f in maintenant}
        st['richesse'][len(maintenant)] = st['richesse'].get(len(maintenant), 0) + 1
        profil = ('nom' if {'personne', 'animal'} & types_m else
                  'espece' if 'espece' in types_m else
                  'lieu' if 'lieu' in types_m else
                  'date seule' if 'date' in types_m else 'aucun fait')
        if profil == 'date seule' and dsrc == 'annee du dossier':
            profil = 'annee seule'
        st['strates'][profil] = st['strates'].get(profil, 0) + 1

        pa, pm = paires(alors), paires(maintenant)
        nouveaux = pm - pa
        gain_types = {t for (t, _v) in nouveaux}
        chg_types = set()
        for t in ('date', 'lieu'):              # faits à valeur unique
            va, vm = valeur(alors, t), valeur(maintenant, t)
            if va and vm and va != vm:
                chg_types.add(t)
        for t in TYPES:
            st['alors'][t] += sum(1 for (tt, _v) in pa if tt == t)
            st['maintenant'][t] += sum(1 for (tt, _v) in pm if tt == t)
            if t in gain_types:
                st['gagnes'][t] += 1
            if t in chg_types:
                st['changes'][t] += 1
        if gain_types or chg_types:
            st['entrees_gain'] += 1
            if pipe == 'v0':
                st['entrees_gain_v0'] += 1
            else:
                st['entrees_gain_kb1'] += 1
            if len(st['exemples']) < exemples:
                st['exemples'].append({
                    'cle': key, 'pipe': pipe,
                    'alors': sorted(f"{t}={v}" for t, v in pa),
                    'gagne': sorted(f"{t}={v}" for t, v in nouveaux),
                    'change': sorted(chg_types)})
    return st


def heures(n):
    return n * SECONDES_PAR_PHOTO / 3600.0


def rapport(st, ctx, lignes=None):
    """Rapport ASCII (la console Windows n'a pas a deviner l'encodage)."""
    P = (lignes.append if lignes is not None else print)
    tag = st['taguees'] or 1
    P("")
    P("=== Mesure 3a - ce que rapporterait une re-passe de tagging ===")
    P(f"Entrees d'index    : {st['entrees']}   (taguees {st['taguees']}, "
      f"en echec {st['echecs']})")
    P(f"Fiches chargees    : personnes {len(ctx['people'])}, animaux "
      f"{len(ctx['pets'])}, lieux {len(ctx['lieux'])}, "
      f"gps_places {len(ctx['gps_places'])}")
    P("")
    P("-- Repartition par version de pipeline --")
    for k in sorted(st['pipe']):
        n = st['pipe'][k]
        P(f"   {k:<32} {n:>7}  ({100.0 * n / tag:.1f} %)")
    P("")
    P("-- Faits : au moment du tagging  vs  aujourd'hui --")
    P("   type        alors  aujourd'hui   entrees qui GAGNENT  qui CHANGENT")
    for t in TYPES:
        P(f"   {t:<10} {st['alors'][t]:>7} {st['maintenant'][t]:>12}"
          f" {st['gagnes'][t]:>21} {st['changes'][t]:>13}")
    P("")
    P("-- Ce qui decide --")
    g = st['entrees_gain']
    P(f"   Entrees taguees                              : {st['taguees']:>7}")
    P(f"   Sans aucun fait enregistre au tagging (v0)   : "
      f"{st['sans_faits_alors']:>7}")
    P(f"   Entrees avec >=1 fait NOUVEAU ou CHANGE      : {g:>7}"
      f"  ({100.0 * g / tag:.1f} %)")
    P(f"      dont estampillees v0                      : "
      f"{st['entrees_gain_v0']:>7}")
    P(f"      dont deja au pipeline courant             : "
      f"{st['entrees_gain_kb1']:>7}")
    P(f"   Entrees SANS aucun fait, meme aujourd'hui    : "
      f"{st['entrees_sans_aucun_fait']:>7}   (rien a gagner cote faits)")
    P(f"   Entrees portant une date EXIF sauvegardee    : "
      f"{st['taken_present']:>7}")
    P("")
    P("-- LIRE CECI AVANT LES CHIFFRES --")
    P("   `faits` n'existe QUE depuis kb1 : une entree v0 n'en porte aucun, non")
    P("   parce que rien n'etait connu, mais parce que RIEN N'ETAIT ENREGISTRE.")
    P("   Comparer alors/aujourd'hui sur ces entrees repondrait toujours 'tout")
    P("   est nouveau'. Ce qui est vraiment etabli, lui, ne depend d'aucun")
    P("   enregistrement : le prompt v0 etait l'IMAGE SEULE (aucun fait en")
    P("   contexte, jamais). Donc pour toute entree v0, les faits en contexte")
    P("   au moment du tagging valaient ZERO. La seule question qui reste est")
    P("   la RICHESSE du contexte qu'on donnerait aujourd'hui - ci-dessous.")
    P("")
    P("-- Date qu'on donnerait aujourd'hui, PAR SOURCE --")
    for k in sorted(st['date_src'], key=lambda x: -st['date_src'][x]):
        n = st['date_src'][k]
        P(f"   {k:<20} {n:>7}  ({100.0 * n / tag:.1f} %)")
    P("   ('annee du dossier' = « 2005 » ; 'exif'/'nom du fichier' = jour precis)")
    P("")
    P("-- Richesse du contexte (nb de faits par photo) --")
    for k in sorted(st['richesse']):
        P(f"   {k} fait(s) {st['richesse'][k]:>10}")
    P("")
    P("-- Menu des re-passes CIBLEES (strate la plus riche d'abord) --")
    ordre = ['nom', 'espece', 'lieu', 'date seule', 'annee seule', 'aucun fait']
    cumul = 0
    for k in ordre:
        n = st['strates'].get(k, 0)
        if not n:
            continue
        cumul += n
        P(f"   {k:<12} {n:>7} photos | cumul {cumul:>7} = {heures(cumul):>5.1f} h GPU")
    P("")
    P("-- Quand ces entrees ont-elles ete taguees ? --")
    for k in sorted(st['at_mois']):
        P(f"   {k:<10} {st['at_mois'][k]:>7}")
    P("   (v2ctx adopte le 12/08 ; backfills dates/GPS les 13-14/08)")
    P("")
    P("-- Cout GPU (a " + f"{SECONDES_PAR_PHOTO} s/photo) --")
    P(f"   Passe complete   : {st['taguees']:>7} photos = "
      f"{heures(st['taguees']):.1f} h")
    P(f"   Passe ciblee     : {g:>7} photos = {heures(g):.1f} h"
      "   (seulement celles qui gagnent un fait)")
    P("")
    P("-- Potentiel dormant (independant de la re-passe) --")
    P(f"   Entrees avec GPS mais sans lieu aujourd'hui  : "
      f"{st['gps_sans_lieu']:>7}")
    P("   -> autant de faits 'lieu' que le bat 18 (gps_place) ferait naitre")
    P("      AVANT la re-passe. A activer d'abord : le fait vaut mieux que le tour.")
    for ex in st['exemples']:
        P("")
        P(f"   ex. {ex['cle']}  [{ex['pipe']}]")
        P(f"       alors : {', '.join(ex['alors']) or '(rien)'}")
        P(f"       gagne : {', '.join(ex['gagne']) or '(rien)'}"
          + (f" | change : {', '.join(ex['change'])}" if ex['change'] else ""))
    P("")
    return lignes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default=str(SCRIPT_DIR / 'photos.db'))
    ap.add_argument('--lieux', default=str(SCRIPT_DIR / 'lieux.txt'))
    ap.add_argument('--gps-places', default=str(SCRIPT_DIR / 'gps_places.json'))
    ap.add_argument('--json', help="ecrit le detail chiffre dans ce fichier")
    ap.add_argument('--sortie', help="ecrit le rapport texte dans ce fichier")
    ap.add_argument('--exemples', type=int, default=5)
    a = ap.parse_args()

    copie, tmp, octets = copier_base(a.db)
    try:
        print(f"Copie de la base : {octets / 1e6:.0f} Mo -> {copie}")
        cx = sqlite3.connect(str(copie))
        ok = cx.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != 'ok':
            raise SystemExit(f"Copie non integre : {ok}")
        tags = charger_table(cx, 'tags')
        ctx = {
            'people': charger_table(cx, 'people'),
            'pets': charger_table(cx, 'pets'),
            'animals': charger_table(cx, 'animals'),
            'lieux': renommage_facts.load_lieux(Path(a.lieux)),
            'gps_places': {},
        }
        try:
            brut = json.loads(Path(a.gps_places).read_text(encoding='utf-8'))
            if isinstance(brut, dict):
                ctx['gps_places'] = {k: v for k, v in brut.items() if v}
        except (OSError, ValueError):
            pass
        cx.close()
        st = mesurer(tags, ctx, exemples=a.exemples)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    lignes = rapport(st, ctx, lignes=[])
    texte = '\n'.join(lignes)
    print(texte)
    if a.sortie:
        Path(a.sortie).write_text(texte + '\n', encoding='utf-8')
    if a.json:
        st.pop('exemples', None) if a.exemples == 0 else None
        Path(a.json).write_text(json.dumps(st, ensure_ascii=False, indent=1),
                                encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
