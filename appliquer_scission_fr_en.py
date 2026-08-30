#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APPLIQUE la scission FR/EN des mots-cles relus du XMP — index seul, REVERSIBLE
──────────────────────────────────────────────────────────────────────────────

22 196 entrees de l'index (52 %, mesure du 30/08) ont un `kw_en` VIDE et un
`kw_fr` qui porte les deux langues a la suite (la liste ecrite dans le XMP,
relue telle quelle). Ce script remet chaque bloc a sa place, dans l'INDEX
seulement : le fichier XMP porte deja les deux listes fusionnees, il n'a rien
a apprendre. La regle est celle de `scission_fr_en.py` (pure, mesuree par
`mesure_scission_fr_en.py` : 22 190 scindables sur 22 196).

A LANCER SERVEUR ARRETE — et PROUVE (HTTP + `BEGIN IMMEDIATE`,
`appliquer_plan_annee.refus_d_ecriture`) : il ecrit dans `photos.db`.

Ce qu'il change par entree : `kw_fr` (le bloc francais + les noms, a leur
place), `kw_en` (le bloc anglais). Rien d'autre — ni `desc`, ni `in_file`,
ni les dates. Journal `docs/undo_scission_<date>.json` avec, par cle, les
listes d'AVANT ; `--undo` les remet.

    python appliquer_scission_fr_en.py                    # APERCU (rien n est ecrit)
    python appliquer_scission_fr_en.py --appliquer [--limite N] [--sans-ex-aequo]
    python appliquer_scission_fr_en.py --undo docs/undo_scission_XXXX.json --appliquer

`--sans-ex-aequo` : ne touche que les entrees a coupure UNIQUE (19 175), et
laisse les 3 015 ex aequo pour un second regard.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from appliquer_plan_annee import refus_d_ecriture
import scission_fr_en as S

RACINE = Path(__file__).resolve().parent


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def plan(data, sans_ex_aequo=False, limite=0):
    """Les operations : [(cle, kw_fr_avant, kw_fr_apres, kw_en_apres, ex_aequo)]."""
    vfr, ven = S.vocabulaires(data)
    ops = []
    for k in sorted(data.keys()):
        e = data.get(k)
        if not isinstance(e, dict) or e.get('failed') or e.get('video'):
            continue
        r = S.scinder_entree(e, vfr, ven)
        if r is None:
            continue
        kw_fr, kw_en, exaequo = r
        if sans_ex_aequo and exaequo > 1:
            continue
        ops.append((k, list(e.get('kw_fr') or []), kw_fr, kw_en, exaequo))
        if limite and len(ops) >= limite:
            break
    return ops, (len(vfr), len(ven))


def appliquer(store, ops, log):
    n = 0
    journal = {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'), 'operations': []}
    for k, avant, kw_fr, kw_en, exaequo in ops:
        e = store.data.get(k)
        if not isinstance(e, dict) or (e.get('kw_en') or []):
            log('  [skip] entree changee entre-temps : %s' % k)
            continue
        ne = dict(e)
        ne['kw_fr'], ne['kw_en'] = kw_fr, kw_en
        store.set(k, ne, save=False)
        journal['operations'].append({'k': k, 'kw_fr_avant': avant, 'kw_en_avant': list(e.get('kw_en') or []),
                                      'kw_fr': kw_fr, 'kw_en': kw_en, 'ex_aequo': exaequo})
        n += 1
        if n % 2000 == 0:
            store.save()
            log('  ... %d entrees' % n)
    store.save()
    return n, journal


def undo(store, journal_path, dry, log):
    j = json.loads(Path(journal_path).read_text(encoding='utf-8'))
    n = 0
    for op in j.get('operations', []):
        e = store.data.get(op['k'])
        if not isinstance(e, dict):
            log('  [skip] cle absente : %s' % op['k'])
            continue
        if list(e.get('kw_fr') or []) != op['kw_fr'] or list(e.get('kw_en') or []) != op['kw_en']:
            log('  [skip] entree modifiee depuis, on ne l ecrase pas : %s' % op['k'])
            continue
        if not dry:
            ne = dict(e)
            ne['kw_fr'], ne['kw_en'] = op['kw_fr_avant'], op['kw_en_avant']
            store.set(op['k'], ne, save=False)
        n += 1
    if not dry:
        store.save()
    log('Undo %s: %d entree(s) %s.' % ('(a blanc) ' if dry else '', n, 'a remettre' if dry else 'remises'))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true')
    ap.add_argument('--limite', type=int, default=0)
    ap.add_argument('--sans-ex-aequo', action='store_true')
    ap.add_argument('--undo', metavar='JOURNAL')
    ap.add_argument('--db', default=str(RACINE / 'photos.db'))
    ap.add_argument('--forcer', action='store_true')
    ap.add_argument('--exemples', type=int, default=6)
    a = ap.parse_args(argv)
    log = lambda m: print(asc(m), flush=True)  # noqa: E731
    dry = not a.appliquer
    refus = refus_d_ecriture(a.db, False, a.forcer)   # meme l apercu OUVRE la base : serveur arrete
    if refus:
        log(refus)
        return 1
    if not Path(a.db).exists():
        log('REFUS : %s absent' % a.db)
        return 1
    from store_sqlite import SqliteStore
    store = SqliteStore(a.db, 'tags')
    if a.undo:
        return undo(store, a.undo, dry, log)
    ops, (nfr, nen) = plan(store.data, a.sans_ex_aequo, a.limite)
    uniques = sum(1 for o in ops if o[4] == 1)
    log('%s : %d entree(s) a scinder (%d a coupure unique, %d ex aequo) ; vocabulaire FR %d / EN %d'
        % ('APERCU' if dry else 'APPLICATION', len(ops), uniques, len(ops) - uniques, nfr, nen))
    for k, avant, kw_fr, kw_en, exaequo in ops[:a.exemples]:
        log('  %s  (ex aequo %d)\n     FR: %s\n     EN: %s' % (k[-70:], exaequo, ', '.join(kw_fr), ', '.join(kw_en)))
    if dry:
        log('(apercu — rien n est ecrit ; --appliquer pour executer)')
        return 0
    n, journal = appliquer(store, ops, log)
    jp = RACINE / 'docs' / ('undo_scission_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
    jp.write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding='utf-8')
    log('\n%d entree(s) scindee(s). Journal undo : %s' % (n, jp.name))
    log('Reversible : appliquer_scission_fr_en.py --undo docs/%s --appliquer' % jp.name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
