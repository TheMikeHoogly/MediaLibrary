#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification — « PC mort lundi, tout revit vendredi » (chantier 12)
──────────────────────────────────────────────────────────────────────────────

CE QUE CE PROJET SAIT DÉJÀ FAIRE, ET CE QU'IL NE SAIT PAS

`backup_db()` pousse un snapshot de `photos.db` sur le NAS et `backup_verify()`
le relit (integrity_check + comptage des jugements). C'est acquis, et c'est la
moitié de l'assurance-vie. L'autre moitié n'a jamais tourné : **remonter un PC
neuf**. Tant qu'une restauration à blanc n'a pas eu lieu, « on a une
sauvegarde » est une promesse, pas un fait — et le projet a déjà payé pour la
différence (`backup_verify` n'existait pas, et personne ne l'avait remarqué).

CE QUE CET INSTRUMENT FAIT — ET NE FAIT PAS

Il ne restaure rien : **la restauration est un geste de Mike**. Lui, il NOMME.

  `--inventaire` (défaut) — ce qu'un disque mort emporterait. Pour chaque
  artefact dont le projet dépend : existe-t-il ici, pèse-t-il quoi, en existe-t-il
  une copie sur le NAS, et **que coûte sa perte** — irrécupérable, recalculable
  (avec son prix en temps), ou re-téléchargeable. C'est la liste des manques,
  écrite avant le sinistre et non pendant.

  `--restaure <dossier>` — la comparaison d'après. Le dossier restauré est
  confronté au vivant : présence de chaque artefact, et surtout **les décisions
  humaines nom par nom** (rattachements, exclusions, confirmations). Un compte
  global identique ne prouve rien : deux erreurs qui se compensent donnent le
  même total. C'est la ventilation par NOM qui fait foi.

CE QUE LA SESSION 31 A CHANGÉ À CETTE LISTE

`docs/undo_*.json` a cessé d'être un historique pour devenir un **actif
porteur** : ces journaux sont la carte des déplacements (19 331 connus), et
c'est par eux que **748** décisions humaines décrochées par le rangement ont pu
retrouver leur photo. Les perdre, c'est perdre définitivement la capacité de
réparer — alors qu'aucune sauvegarde ne les emporte aujourd'hui. Ce constat est
la première raison de faire tourner ce banc.

CE QU'IL N'OUVRE JAMAIS

`photos.db` : le serveur en est l'écrivain unique. Les deux côtés de la
comparaison sont des COPIES (`mesure_copie_base.py` pour le vivant, le fichier
restauré pour l'autre), ouvertes en `mode=ro&immutable=1` — sur un chemin UNC,
l'URI se construit à la main (`Path.as_uri()` met le serveur en autorité, que
SQLite refuse : la leçon est déjà dans `backup_verify`).

FUSEAU HORAIRE : les dates affichées sont locales, et seulement affichées.

USAGE
    python verifier_restauration.py
    python verifier_restauration.py --vivant copie.db
    python verifier_restauration.py --restaure D:/essai-restauration --vivant copie.db
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
from pathlib import Path

RACINE = Path(__file__).resolve().parent

IRRECUPERABLE = 'IRRECUPERABLE'
RECALCULABLE = 'recalculable'
RETELECHARGEABLE = 're-telechargeable'
DANS_GIT = 'dans git'

# Ce dont le projet dépend, et ce que sa perte coûte VRAIMENT. L'ordre est
# celui de la gravité : ce qui ne se refabrique pas d'abord.
ARTEFACTS = (
    ('photos.db', IRRECUPERABLE,
     "l'index, les vecteurs et TOUTES les décisions humaines",
     'photos.db.bak'),
    ('journal_jugements.jsonl', IRRECUPERABLE,
     "l'historique des gestes humains, append-only",
     'journal_jugements.jsonl'),
    ('docs/undo_*.json', IRRECUPERABLE,
     "la CARTE DES DEPLACEMENTS — 19 331 mouvements. C'est par elle que 748 "
     "décisions décrochées ont retrouvé leur photo (22/08). Sans elle, plus "
     "aucune réparation de ce type n'est possible",
     None),
    ('gps_places.json', RECALCULABLE,
     "les libellés de géocodage — 7e magasin keyé par chemin (audit I2)",
     'artefacts/gps_places.json'),
    ('lieux.txt', IRRECUPERABLE,
     "le vocabulaire de lieux corrigé à la main",
     None),
    ('lieux_locaux.txt', IRRECUPERABLE,
     "les lieux locaux saisis à la main",
     None),
    ('vocabulaire_tags.txt', IRRECUPERABLE,
     "le vocabulaire de tags",
     None),
    ('dossier_uploads.txt', IRRECUPERABLE,
     "où le téléphone dépose ses photos",
     None),
    ('dossiers_a_taguer.txt', IRRECUPERABLE,
     "les racines scannées — sans elles, le serveur ne voit plus rien",
     None),
    ('dossiers_a_explorer.txt', IRRECUPERABLE,
     "les racines navigables",
     None),
    ('_comptes_index.json', RECALCULABLE,
     "le carnet de comptes de l'index (repart à zéro, sans plus)",
     None),
    ('photo_thumbs', RECALCULABLE,
     "les vignettes — coût : des heures de NAS, aucune perte d'information",
     None),
    ('face_thumbs', RECALCULABLE, "les découpes de visages", None),
    ('animal_thumbs', RECALCULABLE, "les découpes d'animaux", None),
    ('yolo11s.pt', RETELECHARGEABLE, "le détecteur d'animaux",
     'ultralytics'),
    ('yolo11n.pt', RETELECHARGEABLE, "le détecteur léger", 'ultralytics'),
    ('cities1000.txt', RETELECHARGEABLE,
     "le gazetteer de géocodage", 'bat 18'),
    ('server.py', DANS_GIT, "le serveur", 'GitHub (dépôt privé)'),
    ('requirements.txt', DANS_GIT, "les dépendances", 'GitHub'),
)

# Les quarantaines ne se listent PAS : elles se découvrent. Cette liste-ci en
# nommait trois quand le disque en portait six, et l'inventaire annonçait
# « Total exposé : 0 o » — un zéro qui ne parlait que des dossiers qu'il
# connaissait. Les deux quarantaines nées le 22/08 (`_corbeille_recalage`,
# `_corbeille_retraits`), celles qui rendent annulables le recalage de 33
# rattachements et le retrait de 2 couples, n'étaient sauvegardées nulle part.
# La règle est celle du PRODUCTEUR (`server.backup_artefacts`) : même motif,
# même exclusion — sinon l'instrument mesure un cousin de la sauvegarde.
QUARANTAINE_MOTIF = '_corbeille_*'
QUARANTAINES_NON_SAUVEES = ('_corbeille_session',)


def artefacts_quarantaines(racine=RACINE):
    """Les quarantaines PRÉSENTES, ajoutées à l'inventaire dans l'ordre.

    Celles qui ne sont volontairement pas sauvées y figurent aussi, avec la
    raison : une exclusion tue ne se distingue pas d'un oubli."""
    out = []
    for d in sorted(Path(racine).glob(QUARANTAINE_MOTIF)):
        if not d.is_dir():
            continue
        if d.name in QUARANTAINES_NON_SAUVEES:
            out.append((d.name, RECALCULABLE,
                        "rebut du menage de fin de session — hors sauvegarde, "
                        "volontairement (fichiers de travail, versionnes)",
                        None))
        else:
            out.append((d.name, IRRECUPERABLE,
                        "quarantaine : c'est elle qui rend le geste reversible",
                        None))
    return tuple(out)


# Ce que la base porte, table par table. Les deux dernières sont celles qui
# comptent : elles ne se refabriquent pas.
TABLES = ('tags', 'faces', 'animals', 'vectors', 'people', 'pets')


# Où chaque artefact est attendu DANS la sauvegarde. `None` ci-dessus = sous
# `artefacts/<même nom>` ; les deux exceptions historiques sont à la racine.
def ou_dans_la_sauvegarde(motif, declare):
    if declare:
        return declare
    if motif.startswith('docs/'):
        return 'artefacts/' + motif
    return 'artefacts/' + motif


def dossier_de_sauvegarde(racine=None):
    """Le dossier NAS où `backup_db()` dépose — lu comme `server.py` le lit.

    Répliquer la règle du PRODUCTEUR, pas la deviner : `data_dir.txt` d'abord,
    puis le défaut du serveur. Une sauvegarde cherchée au mauvais endroit
    déclarerait « AUCUNE COPIE » alors qu'elle existe."""
    racine = Path(racine or RACINE)
    defaut = Path(r"\\nas-bremblens\home\Uploads")
    try:
        for ligne in (racine / 'data_dir.txt').read_text(
                encoding='utf-8').splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith('#'):
                return Path(ligne)
    except OSError:
        pass
    return defaut


def uri_lecture_seule(chemin):
    """URI SQLite `mode=ro&immutable=1`, y compris sur un chemin UNC.

    `Path.as_uri()` met le serveur en AUTORITE d'URI (`file://nas/...`), que
    SQLite refuse. Forme acceptée : autorité VIDE, puis `//serveur/partage`.
    """
    brut = str(Path(chemin).resolve())
    if brut.startswith('\\\\'):
        chemin_uri = '//' + brut.lstrip('\\').replace('\\', '/')
    else:
        chemin_uri = brut.replace('\\', '/')
        if not chemin_uri.startswith('/'):
            chemin_uri = '/' + chemin_uri
    return ('file://' + urllib.parse.quote(chemin_uri, safe='/:')
            + '?mode=ro&immutable=1')


def taille(chemin):
    """Octets d'un fichier, ou somme récursive d'un dossier. -1 si absent."""
    p = Path(chemin)
    try:
        if p.is_file():
            return p.stat().st_size
        if p.is_dir():
            return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
    except OSError:
        pass
    return -1


def presence(racine, motif):
    """(présent, octets, nombre de fichiers) — gère les motifs `docs/undo_*`."""
    racine = Path(racine)
    if '*' in motif:
        fichiers = sorted(racine.glob(motif))
        octets = 0
        for f in fichiers:
            try:
                octets += f.stat().st_size
            except OSError:
                pass
        return bool(fichiers), octets, len(fichiers)
    o = taille(racine / motif)
    return o >= 0, max(o, 0), (1 if o >= 0 else 0)


def humain(n):
    for unite in ('o', 'Ko', 'Mo', 'Go'):
        if n < 1024:
            return f"{n:.0f} {unite}" if unite == 'o' else f"{n:.1f} {unite}"
        n /= 1024.0
    return f"{n:.1f} To"


def inventaire(racine=RACINE, sauvegarde=None):
    """Ce qu'un disque mort emporterait, artefact par artefact.

    La colonne « copie » est CONSTATÉE dans le dossier de sauvegarde, jamais
    déclarée : une sauvegarde qu'on affirme sans la regarder est exactement le
    piège que `backup_verify` avait été écrit pour fermer."""
    out = []
    sv = Path(sauvegarde) if sauvegarde else None
    for motif, gravite, role, declare in ARTEFACTS + artefacts_quarantaines(racine):
        ok, octets, n = presence(racine, motif)
        copie, oc, nc = ('hors sujet', 0, 0)
        if gravite == DANS_GIT:
            copie = 'GitHub (dépôt privé)'
        elif gravite == RETELECHARGEABLE:
            copie = declare or 're-télécharger'
        elif sv is None:
            copie = '(sauvegarde non consultée)'
        else:
            attendu = ou_dans_la_sauvegarde(motif, declare)
            la, oc, nc = presence(sv, attendu)
            copie = (f"OUI · {attendu}" if la else 'AUCUNE COPIE')
        out.append({'quoi': motif, 'present': ok, 'octets': octets,
                    'fichiers': n, 'gravite': gravite, 'role': role,
                    'copie': copie, 'copie_octets': oc, 'copie_fichiers': nc})
    return out


def decisions_de_la_base(chemin):
    """{nom: {rattachements, exclusions, confirmations}} lu dans une COPIE.

    Refuse `photos.db` : le serveur en est l'écrivain unique."""
    p = Path(chemin)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais ouvrir photos.db. "
                         "Fabrique la copie (mesure_copie_base.py).")
    if not p.is_file():
        return None, f"base absente : {p}"
    par_nom, tailles = {}, {}
    try:
        cx = sqlite3.connect(uri_lecture_seule(p), uri=True, timeout=30.0)
    except sqlite3.Error as e:
        return None, f"ouverture impossible : {e}"
    try:
        for table in TABLES:
            try:
                tailles[table] = cx.execute(
                    f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except sqlite3.Error:
                tailles[table] = None
        for table in ('people', 'pets'):
            try:
                lignes = cx.execute(f'SELECT v FROM "{table}"').fetchall()
            except sqlite3.Error:
                continue
            for (v,) in lignes:
                try:
                    e = json.loads(v)
                except (ValueError, TypeError):
                    continue
                if not isinstance(e, dict) or not e.get('name'):
                    continue
                d = par_nom.setdefault(e['name'], {'rattachements': 0,
                                                   'exclusions': 0,
                                                   'confirmations': 0})
                d['rattachements'] += len(e.get('faces') or [])
                d['exclusions'] += len(e.get('exclude') or [])
                d['confirmations'] += len(e.get('confirmed') or [])
        try:
            integrite = str(cx.execute('PRAGMA integrity_check').fetchone()[0])
        except sqlite3.Error as e:
            integrite = f'illisible ({e})'
    finally:
        cx.close()
    return {'par_nom': par_nom, 'tables': tailles,
            'integrite': integrite}, None


def comparer(vivant, restaure_base):
    """Ce que la restauration a perdu, nom par nom.

    Un TOTAL identique ne prouve rien : deux erreurs qui se compensent donnent
    le même chiffre. On ventile."""
    a, err_a = decisions_de_la_base(vivant)
    if err_a:
        return None, f"vivant : {err_a}"
    b, err_b = decisions_de_la_base(restaure_base)
    if err_b:
        return None, f"restauré : {err_b}"
    ecarts = []
    for nom in sorted(set(a['par_nom']) | set(b['par_nom'])):
        va = a['par_nom'].get(nom, {'rattachements': 0, 'exclusions': 0,
                                    'confirmations': 0})
        vb = b['par_nom'].get(nom, {'rattachements': 0, 'exclusions': 0,
                                    'confirmations': 0})
        if va != vb:
            ecarts.append({'nom': nom, 'vivant': va, 'restaure': vb})
    return {'tables': {'vivant': a['tables'], 'restaure': b['tables']},
            'integrite_restauree': b['integrite'],
            'noms_vivant': len(a['par_nom']), 'noms_restaure': len(b['par_nom']),
            'ecarts': ecarts}, None


def afficher_inventaire(lignes, racine, sauvegarde=None):
    L = [f"CE QU'UN DISQUE MORT EMPORTERAIT — {racine}",
         f"({time.strftime('%d/%m/%Y %H:%M')}, heure locale)",
         f"Sauvegarde consultée : {sauvegarde or '(aucune)'}", ""]
    manquants = [x for x in lignes if not x['present']]
    sans_copie = [x for x in lignes
                  if x['present'] and x['gravite'] == IRRECUPERABLE
                  and x['copie'] == 'AUCUNE COPIE']
    L.append(f"{len(sans_copie)} artefact(s) présent(s) ici et NULLE PART "
             f"ailleurs — c'est la liste des manques du chantier 12 :")
    for x in sans_copie:
        L.append(f"  ⚠ {x['quoi']}  ({humain(x['octets'])}"
                 + (f", {x['fichiers']} fichiers" if x['fichiers'] > 1 else "")
                 + f")  [{x['gravite']}]\n      {x['role']}")
    if not sans_copie:
        L.append("  (aucun — tout ce qui vit ici a une copie ailleurs)")
    L.append("")
    L.append(f"Total exposé : "
             + humain(sum(x['octets'] for x in sans_copie)))
    L.append("")
    L.append("Tableau complet :")
    for x in lignes:
        etat = ('absent' if not x['present']
                else humain(x['octets'])
                + (f" / {x['fichiers']} f." if x['fichiers'] > 1 else ""))
        L.append(f"  {x['quoi']:<28} {etat:>14}  {x['gravite']:<17} {x['copie']}")
    if manquants:
        L.append("")
        L.append("Absents d'ici (normal si jamais utilisés) : "
                 + ", ".join(x['quoi'] for x in manquants))
    return "\n".join(L)


def afficher_comparaison(r):
    L = ["RESTAURÉ CONTRE VIVANT", ""]
    L.append(f"Intégrité de la base restaurée : {r['integrite_restauree']}")
    for table in TABLES:
        v = r['tables']['vivant'].get(table)
        b = r['tables']['restaure'].get(table)
        marque = '   ' if v == b else ' ⚠ '
        L.append(f"{marque}{table:<10} vivant {v}  restauré {b}")
    L.append("")
    L.append(f"Noms : vivant {r['noms_vivant']} · restauré {r['noms_restaure']}")
    if not r['ecarts']:
        L.append("Décisions humaines : AUCUN écart, nom par nom.")
    else:
        L.append(f"⚠ {len(r['ecarts'])} nom(s) dont les décisions diffèrent :")
        for e in r['ecarts'][:40]:
            L.append(f"  {e['nom']} — vivant {e['vivant']} / "
                     f"restauré {e['restaure']}")
        if len(r['ecarts']) > 40:
            L.append(f"  … et {len(r['ecarts']) - 40} autre(s)")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--vivant', default='copie.db',
                    help="COPIE de la base vivante (jamais photos.db)")
    ap.add_argument('--restaure', default='',
                    help="dossier restauré à blanc ; sans lui, inventaire seul")
    ap.add_argument('--sauvegarde', default='',
                    help="dossier NAS de sauvegarde ; par défaut celui du serveur")
    ap.add_argument('--json', default='')
    a = ap.parse_args(argv)
    import os
    os.chdir(RACINE)

    sv = Path(a.sauvegarde) if a.sauvegarde else dossier_de_sauvegarde()
    if not sv.is_dir():
        print(f"(sauvegarde injoignable : {sv})")
        sv = None
    rapport = {'sauvegarde': str(sv or ''),
               'inventaire': inventaire(RACINE, sv)}
    print(afficher_inventaire(rapport['inventaire'], RACINE, sv))

    if a.restaure:
        dossier = Path(a.restaure)
        print("\n" + "=" * 74)
        rapport['inventaire_restaure'] = inventaire(dossier, sv)
        print(afficher_inventaire(rapport['inventaire_restaure'], dossier, sv))
        print("\n" + "=" * 74)
        cmp_, err = comparer(a.vivant, dossier / 'photos.db')
        if err:
            print(f"Comparaison impossible — {err}")
            rapport['erreur'] = err
        else:
            rapport['comparaison'] = cmp_
            print(afficher_comparaison(cmp_))
    if a.json:
        Path(a.json).write_text(json.dumps(rapport, ensure_ascii=False,
                                           indent=1), encoding='utf-8')
        print(f"\nJSON : {a.json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
