#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DEPLACE des dossiers entiers sous un dossier proprietaire, REVERSIBLEMENT.

Premier geste du chantier 17 (multi-utilisateurs) : le fonds existant
appartient a Mike, donc tout ce qui n'est ni « Photos Flo » ni « Photos Papa »
descend d'un cran dans « Photos Mike ». 26 dossiers, **25 559 photos**.

A LANCER SERVEUR ARRETE. Le serveur est l'ECRIVAIN UNIQUE de `photos.db` ; le
script le PROUVE avant de toucher a quoi que ce soit (`BEGIN IMMEDIATE`), il
ne se contente pas de le demander.

Pourquoi ce script existe alors que `appliquer_plan_annee.py` deplace deja
--------------------------------------------------------------------------
**Parce que le chemin HORS-LIGNE ne re-cle que CINQ magasins sur SEPT.**
`appliquer_plan.rekey_stores` dit de lui-meme « miroir de
server.rekey_everywhere » et ne l'est pas : il appelle `.rekey()` sur
`people` et `pets`, qui sont keyes par NOM et pas par chemin — un NO-OP
SILENCIEUX. Il ignore aussi `gps_places.json`. Le serveur, lui, a recu le
correctif du 22/08 (`_recler_decisions_humaines`, via `recle_decisions`) et
transporte les sept.

Mesure sur la copie de la base : **983 decisions humaines** (739 personnes,
244 animaux) pointent vers les 25 559 photos a deplacer. Les deplacer avec
l'outillage existant les laisserait accrochees a l'ANCIEN chemin — c'est
exactement l'incident du 22/08, ou 928 decisions sur 3 364 avaient ete
perdues sans un mot, a trente fois cette echelle. Le TAG survivrait (il vit
dans les `kw` et dans le XMP, la regle 2 tient) ; c'est la VERITE TERRAIN qui
partirait — quel VISAGE est qui, quelles photos ont ete ECARTEES d'un nom.

Ce script transporte les SEPT magasins, et un test l'exige.

Ce qui le rend rapide, et pourquoi c'est aussi ce qui le rend sur
----------------------------------------------------------------
Un dossier se deplace en UN `rename` (operation de metadonnees), pas en
25 559 copies. Les 25 559 changements sont dans l'INDEX, pas sur le disque :
le NAS ne recopie pas un octet. Un `rename` qui echoue echoue en entier, il
ne laisse pas un dossier a moitie deplace.

Ordre, par dossier, et c'est une garantie
-----------------------------------------
  1. la source existe, la destination n'existe PAS (jamais de recouvrement) ;
  2. `rename` du dossier ;
  3. re-cle par PREFIXE de toutes ses cles d'index, les sept magasins ;
  4. journalisation.
Si (3) meurt en route, le journal dit ou : `--undo` reprend a l'envers.

Modes
-----
    python deplacer_dossiers.py                       # APERCU, ne touche rien
    python deplacer_dossiers.py --appliquer
    python deplacer_dossiers.py --undo <journal> --appliquer

SORTIE EN ASCII PUR (console cp1252 de l'agent des bancs).
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
DB = RACINE / 'photos.db'
LISTE = RACINE / 'dossiers_a_deplacer.txt'
CORBEILLE = RACINE / '_corbeille_deplacements'
GPS = RACINE / 'gps_places.json'

RACINE_PHOTOS = r'\\NAS-Bremblens\home\Photos'
VERS = 'Photos Mike'

# Les SEPT magasins. `tags` decide ; `faces`/`animals` sont keyes par CHEMIN ;
# `people`/`pets` par NOM (leurs decisions passent par `recle_decisions`) ; le
# semantique par prefixe de cle vecteur ; `gps_places.json` par chemin.
TABLES = ('tags', 'faces', 'people', 'animals', 'pets')
KEYEES_PAR_CHEMIN = ('faces', 'animals')


# ── lecture de la liste ──────────────────────────────────────────────────

def lire_liste(chemin):
    """Les noms de dossier, valides. Un nom qui ressemble a un chemin est
    REFUSE : ce script deplace des dossiers de premier niveau, et accepter
    `..\\autre` en ferait un outil de deplacement arbitraire."""
    out, refus = [], []
    for brut in Path(chemin).read_text(encoding='utf-8').splitlines():
        nom = brut.strip()
        if not nom or nom.startswith('#'):
            continue
        if ('\\' in nom or '/' in nom or nom in ('.', '..')
                or nom.startswith('.') or ':' in nom):
            refus.append(nom)
            continue
        out.append(nom)
    return out, refus


# ── le serveur doit etre arrete, et ca se PROUVE ─────────────────────────

def serveur_arrete(db):
    """(vrai/faux, ce qu'on a observe).

    Le demander dans un README ne suffit pas : deux ecrivains sur SQLite,
    c'est l'invariant 4 du projet. `BEGIN IMMEDIATE` prend le verrou
    d'ecriture ; si le serveur vit, il est deja pris."""
    try:
        cx = sqlite3.connect(str(db), timeout=1.0)
        try:
            cx.execute('BEGIN IMMEDIATE')
            cx.execute('ROLLBACK')
            return True, 'verrou d ecriture obtenu'
        finally:
            cx.close()
    except sqlite3.OperationalError as e:
        return False, 'base verrouillee (%s)' % str(e)[:60]
    except Exception as e:                                    # noqa: BLE001
        return False, 'base illisible (%s)' % str(e)[:60]


# ── re-cle COMPLETE : les sept magasins ──────────────────────────────────

def recle_une_cle(old, new, stores, semantic, gps):
    """Transporte TOUT ce qu'une photo porte. Rend (deplacee, decisions).

    Miroir de `server.rekey_everywhere`, celui d'APRES le correctif du 22/08.
    Les deux endroits qui manquaient au miroir precedent sont marques.
    """
    import recle_decisions
    if not stores['tags'].rekey(old, new):
        return False, 0
    for t in KEYEES_PAR_CHEMIN:
        try:
            stores[t].rekey(old, new)
        except Exception as e:                                # noqa: BLE001
            print('    ! re-cle %s : %s' % (t, str(e)[:70]))
    # (1) MANQUAIT hors-ligne : les decisions humaines vivent DANS la fiche,
    #     dont la cle est un NOM. `.rekey()` n'y trouve rien et ne dit rien.
    decisions = 0
    for t in ('people', 'pets'):
        st = stores[t]
        for pk, pe in list(st.data.items()):
            if not isinstance(pe, dict):
                continue
            champs, k = recle_decisions.recler_fiche(pe, old, new)
            if not champs:
                continue
            for champ, valeur in champs.items():
                pe[champ] = valeur
            st.set(pk, pe, save=False)
            decisions += k
    try:
        semantic.rekey_prefix_all(old, new)
    except Exception as e:                                    # noqa: BLE001
        print('    ! re-cle semantique : %s' % str(e)[:70])
    # (2) MANQUAIT hors-ligne : le 7e magasin, les libelles de geocodage.
    if old in gps:
        gps[new] = gps.pop(old)
    return True, decisions


def cles_sous(stores, prefixe):
    """Les cles d'index qui vivent sous ce dossier. Triees : un journal qui se
    rejoue doit se rejouer dans le meme ordre."""
    return sorted(k for k in stores['tags'].data if k.startswith(prefixe))


# ── apercu ───────────────────────────────────────────────────────────────

def separateur(racine):
    """Le separateur de la RACINE, pas celui du systeme qui execute.

    Une cle d index est un chemin Windows STOCKE COMME TEXTE
    (`\\\\NAS-Bremblens\\home\\Photos\\...`). Les tests, eux, tournent aussi
    sous Linux sur un dossier temporaire. Prendre `os.sep` casserait les cles
    reelles ; coder `\\` en dur casse les tests -- et un script qu on ne peut
    pas tester ailleurs qu en production n est pas testable. Le separateur se
    LIT donc dans la racine qu on nous donne. Trouve par le test le 26/08."""
    return '\\' if '\\' in racine else os.sep


def examiner(noms, racine, vers, stores, gps, ecrire=print):
    """Ce que le deplacement ferait. Ne touche a rien."""
    import recle_decisions
    sep = separateur(racine)
    base = racine.rstrip('\\/') + sep
    dest_racine = base + vers + sep
    lots, total, total_dec, total_gps = [], 0, 0, 0
    for nom in noms:
        prefixe = base + nom + sep
        cles = cles_sous(stores, prefixe)
        src, dst = base + nom, dest_racine + nom
        dec = 0
        for t in ('people', 'pets'):
            for pe in stores[t].data.values():
                if not isinstance(pe, dict):
                    continue
                for k in cles:
                    _c, n = recle_decisions.recler_fiche(pe, k, k + '#')
                    dec += n
        gps_n = sum(1 for k in cles if k in gps)
        lots.append({'nom': nom, 'cles': cles, 'src': src, 'dst': dst,
                     'decisions': dec, 'gps': gps_n,
                     'src_existe': _existe(src), 'dst_existe': _existe(dst)})
        total += len(cles)
        total_dec += dec
        total_gps += gps_n
    ecrire('DEPLACEMENT VERS "%s"' % vers)
    ecrire('')
    ecrire('  %-24s %8s %10s %6s  %s' % ('dossier', 'photos', 'decisions',
                                         'gps', 'disque'))
    for l in lots:
        etat = ('source ABSENTE' if not l['src_existe']
                else 'DESTINATION DEJA LA' if l['dst_existe'] else 'ok')
        ecrire('  %-24s %8d %10d %6d  %s'
               % (l['nom'], len(l['cles']), l['decisions'], l['gps'], etat))
    ecrire('  %-24s %8d %10d %6d' % ('TOTAL', total, total_dec, total_gps))
    ecrire('')
    bloquants = [l['nom'] for l in lots
                 if not l['src_existe'] or l['dst_existe']]
    if bloquants:
        ecrire('BLOQUANT : %d dossier(s) ne peuvent pas etre deplaces --'
               % len(bloquants))
        ecrire('%s' % ', '.join(bloquants))
        ecrire('Rien ne sera fait tant qu ils sont dans la liste.')
    vides = [l['nom'] for l in lots if not l['cles']]
    if vides:
        ecrire('A VERIFIER : %d dossier(s) sans AUCUNE photo dans l index --'
               % len(vides))
        ecrire('%s.' % ', '.join(vides))
        ecrire('Ce n est pas un feu vert : un dossier peut exister sur le NAS')
        ecrire('sans avoir ete scanne. Le deplacement marchera, mais aucune')
        ecrire('cle ne suivra -- verifier que c est bien voulu.')
    return lots, bloquants


def _existe(p):
    try:
        return Path(p).exists()
    except OSError:
        return False


# ── application ──────────────────────────────────────────────────────────

def appliquer(lots, stores, semantic, gps, journal, ecrire=print):
    ops = 0
    for l in lots:
        ecrire('  %s : %d photo(s)' % (l['nom'], len(l['cles'])))
        Path(l['dst']).parent.mkdir(parents=True, exist_ok=True)
        os.rename(l['src'], l['dst'])
        _noter(journal, {'quoi': 'rename', 'src': l['src'], 'dst': l['dst']})
        n, dec = 0, 0
        for old in l['cles']:
            new = l['dst'] + old[len(l['src']):]
            deplacee, d = recle_une_cle(old, new, stores, semantic, gps)
            if deplacee:
                n += 1
                dec += d
                _noter(journal, {'quoi': 'recle', 'old': old, 'new': new})
        ecrire('    index : %d cle(s), %d decision(s) humaine(s)' % (n, dec))
        ops += 1
    return ops


def _noter(journal, obj):
    obj['at'] = time.time()
    with open(journal, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def defaire(journal, stores, semantic, gps, ecrire=print):
    """Rejoue le journal A L ENVERS. Les re-cles d abord, les renames apres."""
    lignes = [json.loads(x) for x in
              Path(journal).read_text(encoding='utf-8').splitlines() if x.strip()]
    n_r, n_m = 0, 0
    for op in reversed(lignes):
        if op['quoi'] == 'recle':
            if recle_une_cle(op['new'], op['old'], stores, semantic, gps)[0]:
                n_r += 1
        elif op['quoi'] == 'rename':
            if _existe(op['dst']) and not _existe(op['src']):
                os.rename(op['dst'], op['src'])
                n_m += 1
    ecrire('  remis : %d dossier(s), %d cle(s) d index' % (n_m, n_r))
    return n_m, n_r


# ── main ─────────────────────────────────────────────────────────────────

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--liste', default=str(LISTE))
    p.add_argument('--vers', default=VERS)
    p.add_argument('--racine', default=RACINE_PHOTOS)
    p.add_argument('--db', default=str(DB))
    p.add_argument('--appliquer', action='store_true')
    p.add_argument('--undo', default='')
    a = p.parse_args(argv)

    noms, refus = lire_liste(a.liste)
    if refus:
        print('REFUSE : %d entree(s) ne sont pas des noms de dossier simples --'
              % len(refus))
        print('%s' % ', '.join(refus[:8]))
        return 2
    if not noms:
        print('aucun dossier dans %s -- rien a faire, et ce n est pas un feu'
              ' vert.' % a.liste)
        return 2

    ok, dit = serveur_arrete(Path(a.db))
    if not ok:
        print('SERVEUR VIVANT (%s).' % dit)
        print('Ce script est le second ecrivain de photos.db : il ne demarre')
        print('pas. Arreter le serveur -- mot `arret` dans')
        print('_commande_serveur.txt -- puis relancer.')
        return 2

    from appliquer_plan import open_stores
    stores, semantic = open_stores(a.db)
    gps = {}
    if GPS.is_file():
        try:
            gps = json.loads(GPS.read_text(encoding='utf-8'))
        except Exception:                                     # noqa: BLE001
            gps = {}

    if a.undo:
        if not a.appliquer:
            print('APERCU d une annulation : relancer avec --appliquer.')
            return 0
        n_m, n_r = defaire(a.undo, stores, semantic, gps)
        _sauver(stores, gps)
        return 0 if (n_m or n_r) else 1

    lots, bloquants = examiner(noms, a.racine, a.vers, stores, gps)
    if bloquants:
        return 1
    if not a.appliquer:
        print('APERCU. Rien n a ete touche. --appliquer pour executer.')
        return 0

    CORBEILLE.mkdir(exist_ok=True)
    journal = CORBEILLE / ('deplacement_%s.jsonl'
                           % time.strftime('%Y%m%d_%H%M%S'))
    print('journal : %s' % journal.name)
    appliquer(lots, stores, semantic, gps, journal)
    _sauver(stores, gps)
    print('')
    print('FAIT. Pour tout remettre :')
    print('  python deplacer_dossiers.py --undo %s --appliquer' % journal)
    return 0


def _sauver(stores, gps):
    for t in TABLES:
        stores[t].save()
    if gps:
        GPS.write_text(json.dumps(gps, ensure_ascii=False, indent=1),
                       encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
