#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demon d'analyse Phase 2 — produit un PLAN DE RANGEMENT a provenance.
──────────────────────────────────────────────────────────────────────────────

Lit le recensement Phase 0 (`docs/recensement.json`, lecture seule) et en tire un
PLAN d'operations PROPOSEES, que le serveur appliquera plus tard (rekey + undo).
Ce script n'ecrit AUCUN fichier photo, ne mute NI le NAS NI l'index : il ne
produit que deux rapports relisables. C'est le « demon PROPOSE / serveur EXECUTE »
de docs/RANGEMENT_2026.md.

Operations produites, toutes REVERSIBLES a l'application :

  - `quarantine` : une copie EXACTE (meme sha256) d'un fichier dont une autre
    copie, mieux rangee, est retenue comme CANONIQUE. La copie part en
    `.corbeille-rangement/` (jamais de rm). Regle de canonique (cf. recensement) :
    dossier annee > autre > `_A TRIER` ; a egalite, chemin le plus court.

  - `sans_date` : fichier sans aucune date fiable (EXIF/nom/chemin) — proposition
    de rangement en `_SANS_DATE/`, TOUJOURS en revue humaine (jamais automatique).

INVARIANT DE SECURITE (le plus important). « Sans perte » = fusionner AVANT de
retirer. On croise l'index (copie /tmp de photos.db) : si une copie a quarantiner
porte un nom humain (`personne:`/`animal:`) que la canonique n'a pas, on l'inscrit
dans `fusion_noms` et on marque l'operation `revue=true`. L'application DEVRA
ecrire ces noms dans la canonique (XMP + index) avant tout retrait. Un nom humain
ne se perd jamais.

Usage :
    python plan_rangement.py           # ecrit docs/plan_rangement.{json,md}
    python plan_rangement.py --stdout  # affiche seulement la synthese
"""

import json
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
RECENSEMENT = RACINE / "docs" / "recensement.json"
PLAN_JSON = RACINE / "docs" / "plan_rangement.json"
PLAN_MD = RACINE / "docs" / "plan_rangement.md"


# ── zone d'un chemin (miroir de recensement_doublons.classer_zone) ────────────

def zone_of(path):
    parts = str(path).replace('/', '\\').split('\\')
    annee = False
    for p in parts[:-1]:
        pl = p.strip().lower()
        if pl.startswith('_a trier') or pl == '_a_trier' or pl == 'a trier':
            return 'a_trier'
        if len(p) == 4 and p.isdigit() and 1990 <= int(p) <= 2100:
            annee = True
    return 'annee' if annee else 'autre'


def photos_root(paths):
    """Racine « …\\Photos » commune, pour y ancrer .corbeille-rangement / _SANS_DATE."""
    for p in paths:
        s = str(p).replace('/', '\\')
        i = s.lower().rfind('\\photos\\')
        if i >= 0:
            return s[:i + len('\\photos')]
    # repli : dossier parent commun
    return '\\\\NAS-Bremblens\\home\\Photos'


def basename(path):
    return str(path).replace('/', '\\').split('\\')[-1]


# ── noms humains depuis l'index (copie lecture seule) ─────────────────────────

def load_names(db_copy):
    """{chemin: [tags de nom humain]} pour toutes les entrees tags qui en ont un.
    Lecture seule sur une COPIE de photos.db."""
    out = {}
    try:
        cx = sqlite3.connect(str(db_copy))
        for k, v in cx.execute("SELECT k, v FROM tags"):
            try:
                e = json.loads(v)
            except Exception:
                continue
            noms = []
            for fld in ('kw_fr', 'kw_en'):
                for t in e.get(fld) or []:
                    if isinstance(t, str) and (t.startswith('personne:')
                                               or t.startswith('animal:')):
                        noms.append(t)
            if noms:
                out[k] = noms
        cx.close()
    except Exception as e:
        print(f"  (index illisible, fusion de noms desactivee : {e})")
    return out


# ── construction du plan ──────────────────────────────────────────────────────

def build_plan(rec, names_by_path):
    root = photos_root([g['canonique_proposee'] for g in rec['groupes_doublons']]
                       or rec.get('fichiers_sans_date', []))
    corbeille = root + '\\.corbeille-rangement'
    sans_date_dir = root + '\\_SANS_DATE'
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    ops = []
    stats = {'quarantine': 0, 'octets_quarantine': 0, 'sans_date': 0,
             'groupes': 0, 'canon_en_a_trier': 0, 'fusions_noms': 0,
             'quarantine_nommee': 0}
    qn = 0

    for g in rec['groupes_doublons']:
        copies = list(dict.fromkeys(g['copies']))     # dedupe, ordre garde
        canon = g['canonique_proposee']
        if canon not in copies:
            # securite : canonique absente de ses copies -> on ne touche pas
            ops.append({'type': 'ignore', 'raison': 'canonique absente des copies',
                        'preuve': {'sha256': g['sha256'], 'canonique': canon}})
            continue
        stats['groupes'] += 1
        if zone_of(canon) == 'a_trier':
            stats['canon_en_a_trier'] += 1

        # union des noms de TOUTES les copies, et ceux qui manquent au canon
        canon_names = set(names_by_path.get(canon, []))
        union_names = set(canon_names)
        for c in copies:
            union_names |= set(names_by_path.get(c, []))
        a_fusionner = sorted(union_names - canon_names)

        for c in copies:
            if c == canon:
                continue
            qn += 1
            noms_src = names_by_path.get(c, [])
            # noms de CETTE copie absents du canon (a preserver imperativement)
            manquants = sorted(set(noms_src) - canon_names)
            op = {
                'id': f'q{qn:04d}',
                'type': 'quarantine',
                'src': c,
                'dst': f'{corbeille}\\{g["sha256"][:8]}\\{basename(c)}',
                'raison': ("doublon exact (sha256) d'une copie canonique retenue "
                           f"(zone canon = {zone_of(canon)}, zone copie = {zone_of(c)})"),
                'preuve': {
                    'sha256': g['sha256'], 'taille': g['taille'],
                    'canonique': canon, 'n_copies': len(copies),
                },
                'fusion_noms': manquants,
                'revue': bool(manquants),
                'manifeste': {'groupe': g['sha256'][:8], 'origine': c,
                              'canonique': canon, 'date_plan': now},
            }
            ops.append(op)
            stats['quarantine'] += 1
            stats['octets_quarantine'] += g['taille']
            if noms_src:
                stats['quarantine_nommee'] += 1
            if manquants:
                stats['fusions_noms'] += 1

    for p in rec.get('fichiers_sans_date', []):
        ops.append({
            'id': f'd{stats["sans_date"]+1:04d}',
            'type': 'sans_date',
            'src': p,
            'dst': f'{sans_date_dir}\\{basename(p)}',
            'raison': 'aucune date fiable (EXIF / nom / chemin)',
            'revue': True,
        })
        stats['sans_date'] += 1

    plan = {
        'genere_le': now,
        'source': str(RECENSEMENT.name),
        'racine_photos': root,
        'corbeille': corbeille,
        'stats': stats,
        'operations': ops,
    }
    return plan


def write_md(plan):
    s = plan['stats']
    go = s['octets_quarantine'] / 1024**3      # Go base 1024, comme le recensement
    md = []
    md.append("# Plan de rangement — Phase 2 (proposition, non applique)\n")
    md.append(f"Genere le {plan['genere_le']} depuis `{plan['source']}`. "
              "**Lecture seule : aucune operation n'a ete executee.**\n")
    md.append("## Ce que le plan propose\n")
    md.append(f"- **Quarantaines (doublons exacts)** : {s['quarantine']} copies, "
              f"**{go:.1f} Go** liberables, vers `.corbeille-rangement/` "
              "(reversible, jamais de suppression dure).")
    md.append(f"- Groupes de doublons traites : {s['groupes']}.")
    md.append(f"- Fichiers **sans date fiable** (proposition `_SANS_DATE/`, en "
              f"revue) : {s['sans_date']}.\n")
    md.append("## Points d'attention (a relire avant d'appliquer)\n")
    md.append(f"- **Copies nommees a quarantiner** : {s['quarantine_nommee']} "
              "(elles portent un nom humain dans l'index).")
    md.append(f"- **Fusions de noms requises AVANT retrait** : {s['fusions_noms']} "
              "operations ou la copie retiree porte un nom absent de la canonique. "
              "Ces noms sont listes dans `fusion_noms` et l'op est marquee "
              "`revue=true` : l'application DOIT les ecrire dans la canonique "
              "(XMP + index) avant tout retrait. **Aucun nom humain n'est perdu.**")
    md.append(f"- **Canonique encore dans `_A TRIER`** : {s['canon_en_a_trier']} "
              "groupes (aucune copie mieux rangee n'existe ; la survivante pourra "
              "etre rangee par annee ensuite).\n")
    md.append("## Application (etape suivante, mutante, differee)\n")
    md.append("Le serveur applique ce plan par lots : pour chaque `quarantine`, "
              "fusionner `fusion_noms` dans la canonique, deplacer la copie vers "
              "`dst` (avec manifeste), re-cler l'index via `rekey_everywhere`, "
              "le tout annulable (quarantaine 30 j). Detail par operation dans "
              "`plan_rangement.json`.")
    return "\n".join(md) + "\n"


def main():
    if not RECENSEMENT.exists():
        print(f"{RECENSEMENT} introuvable — lance d'abord le recensement Phase 0.")
        return 2
    rec = json.loads(RECENSEMENT.read_text(encoding='utf-8'))

    # index : copie /tmp lecture seule (jamais la vraie base)
    names = {}
    src_db = RACINE / "photos.db"
    if src_db.exists():
        tmp = Path(tempfile.mkdtemp(prefix="plan_idx_"))
        try:
            shutil.copy2(src_db, tmp / "photos.db")
            names = load_names(tmp / "photos.db")
            print(f"  index : {len(names)} fichier(s) portant un nom humain")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        print("  (photos.db absent : fusion de noms non verifiee)")

    plan = build_plan(rec, names)
    md = write_md(plan)

    if '--stdout' in sys.argv:
        print(md)
        return 0

    PLAN_JSON.write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                         encoding='utf-8')
    PLAN_MD.write_text(md, encoding='utf-8')
    s = plan['stats']
    print(f"Ecrit {PLAN_MD.name} + {PLAN_JSON.name} : "
          f"{s['quarantine']} quarantaines ({s['octets_quarantine']/1024**3:.1f} Go), "
          f"{s['sans_date']} sans-date, {s['fusions_noms']} fusions de noms requises.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
