#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification — les décisions humaines suivent-elles la photo qui se déplace ?
──────────────────────────────────────────────────────────────────────────────

CE QU'IL OBSERVE, ET POURQUOI IL FAUT L'OBSERVER

`rekey_everywhere` transportait sept magasins mais pas les DÉCISIONS humaines :
`PEOPLE` et `PETS` sont keyés par NOM, leurs chemins vivent dans la fiche, et
`store.rekey(chemin, chemin)` y était un no-op silencieux. Le correctif du
22/08 branche `recle_decisions` dans ce chemin. Un correctif dont l'effet n'est
pas observé n'est pas acquis (`CLAUDE.md`) — et celui-ci ne se voit nulle part
dans l'interface : le TAG suivait déjà, seule la vérité terrain partait.

D'où cet instrument, qui répond à deux questions :

  * `--contient <fragment>` : quelles fiches citent une clé qui contient ce
    fragment, et dans quel CHAMP (`faces` avec son index, `exclude`,
    `confirmed`, `avatar`) ? À lancer AVANT puis APRÈS un renommage : les mêmes
    décisions doivent réapparaître sous le NOUVEAU chemin, index compris.
  * `--quarantaine <fichier.jsonl>` : l'AUDIT du re-clé. Le journal garde
    l'état AVANT et APRÈS de chaque fiche touchée ; on vérifie que **chaque
    décision sortie a une contrepartie** — soit une arrivée de même type et de
    même index sous un autre chemin (un re-clé), soit une cible qui existait
    déjà dans la fiche (une fusion de doublon). Une sortie sans contrepartie
    serait une décision humaine PERDUE, ce que la règle 2 interdit. C'est le
    seul contrôle qui distingue « 787 décisions déplacées » de « 787 décisions
    déplacées et quelques-unes tombées en route ».
  * sans argument : le compte global — combien de décisions pointent vers une
    clé que l'index n'a plus. C'est le nombre qui doit rester STABLE après un
    déplacement (avant le correctif, il montait).

Le fragment est cherché tel quel, sans espace ni antislash : les arguments d'un
banc sont contraints à `[A-Za-z0-9_.:/=-]` (`banc_agent.py`). Un nom de fichier
suffit — c'est ce qui distingue une photo d'une autre.

CE QU'IL NE FAIT PAS

Aucune écriture. Lecture seule sur la COPIE, jamais sur `photos.db`.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python verifier_recle_decisions.py --base copie.db
    python verifier_recle_decisions.py --base copie.db --contient 20260607_161141.jpg
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

MAGASINS = (('people', 'visage'), ('pets', 'animal'))


def ouvrir(base):
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais lire photos.db. "
                         "Fabrique la copie (mesure_copie_base.py).")
    if not p.exists():
        raise SystemExit(f"Base introuvable : {p}")
    from store_sqlite import SqliteStore
    return {n: SqliteStore(p, n) for n in ('tags', 'people', 'pets')}


def citations(st, fragment=None):
    """[(fiche, champ, clé, index)] — toutes les citations de chemin, ou seules
    celles dont la clé contient `fragment`."""
    out = []
    for magasin, _genre in MAGASINS:
        for pe in st[magasin].data.values():
            if not isinstance(pe, dict) or not pe.get('name'):
                continue
            nom = pe['name']
            for kf in (pe.get('faces') or []):
                if isinstance(kf, (list, tuple)) and len(kf) == 2:
                    out.append((nom, 'faces', kf[0], int(kf[1] or 0)))
            for champ in ('exclude', 'confirmed'):
                for cle in (pe.get(champ) or []):
                    out.append((nom, champ, cle, None))
            av = pe.get('avatar')
            if isinstance(av, (list, tuple)) and len(av) == 2:
                out.append((nom, 'avatar', av[0], int(av[1] or 0)))
    if fragment:
        f = fragment.lower()
        out = [c for c in out if f in str(c[2]).lower()]
    return out


def decisions_d_un_etat(etat):
    """{(type, chemin, index)} d'un état de fiche journalisé.

    L'avatar est DÉRIVÉ (le curateur le recalcule) : il n'entre pas dans le
    compte, sinon un avatar recalculé passerait pour une décision perdue."""
    s = set()
    for kf in (etat.get('faces') or []):
        if isinstance(kf, (list, tuple)) and len(kf) == 2:
            s.add(('rattachement', kf[0], int(kf[1] or 0)))
    for champ in ('exclude', 'confirmed'):
        for cle in (etat.get(champ) or []):
            s.add((champ, cle, None))
    return s


def auditer_quarantaine(chemin):
    """Chaque décision sortie a-t-elle une contrepartie ? (rapport, lignes)."""
    fiches, entete = [], {}
    for i, ligne in enumerate(Path(chemin).read_text(
            encoding='utf-8').splitlines()):
        if not ligne.strip():
            continue
        try:
            op = json.loads(ligne)
        except ValueError:
            continue
        if i == 0 and 'fiche' not in op:
            entete = op
        elif 'fiche' in op:
            fiches.append(op)

    sorties = arrivees = appariees = fusionnees = 0
    orphelines = []
    for f in fiches:
        av = decisions_d_un_etat(f.get('avant') or {})
        ap = decisions_d_un_etat(f.get('apres') or {})
        parties, venues = av - ap, list(ap - av)
        sorties += len(parties)
        arrivees += len(ap - av)
        for x in sorted(parties):
            # Le re-clé ne change QUE le chemin : le type et l'index sont
            # l'empreinte qui permet d'apparier une sortie à une arrivée.
            m = [y for y in venues if y[0] == x[0] and y[2] == x[2]]
            if m:
                venues.remove(m[0])
                appariees += 1
            elif any(y[0] == x[0] and y[2] == x[2] and y != x for y in ap):
                fusionnees += 1
            else:
                orphelines.append((f.get('fiche'), x))
    return {'fichier': str(chemin), 'entete': entete, 'fiches': len(fiches),
            'sorties': sorties, 'arrivees': arrivees, 'appariees': appariees,
            'fusionnees': fusionnees, 'sans_contrepartie': len(orphelines),
            'exemples': orphelines[:5]}


def afficher_audit(r):
    L = [f"AUDIT DE LA QUARANTAINE — {r['fichier']}",
         f"Annoncé par le serveur : {r['entete'].get('decisions')} décision(s) "
         f"sur {r['entete'].get('paires')} clé(s)",
         f"Fiches journalisées : {r['fiches']}",
         f"Sorties {r['sorties']} · arrivées {r['arrivees']} · "
         f"appariées {r['appariees']} · fusionnées (cible déjà présente) "
         f"{r['fusionnees']}"]
    if r['sans_contrepartie']:
        L.append(f"⚠ {r['sans_contrepartie']} décision(s) SANS CONTREPARTIE — "
                 f"règle 2 violée, annuler (bouton 3) et diagnostiquer :")
        for fiche, x in r['exemples']:
            L.append(f"    {fiche} · {x}")
    else:
        L.append("SANS CONTREPARTIE : 0 — aucune décision humaine perdue.")
    return "\n".join(L)


def rapport(base, fragment=None):
    st = ouvrir(base)
    try:
        vivantes = set(st['tags'].data.keys())
        toutes = citations(st)
        # L'avatar est DÉRIVÉ (le curateur le recalcule) : il ne compte pas
        # dans la vérité terrain, mais on le regarde quand même bouger.
        jugements = [c for c in toutes if c[1] != 'avatar']
        mortes = [c for c in jugements if c[2] not in vivantes]
        L = [f"Décisions humaines {len(jugements)} "
             f"{dict(Counter(c[1] for c in jugements))}",
             f"Sur une clé HORS INDEX : {len(mortes)} "
             f"{dict(Counter(c[1] for c in mortes))}",
             f"Avatars : {sum(1 for c in toutes if c[1] == 'avatar')} "
             f"(dérivés, hors compte)"]
        if fragment:
            trouve = citations(st, fragment)
            L.append("")
            L.append(f"Citations contenant « {fragment} » : {len(trouve)}")
            for nom, champ, cle, i in sorted(trouve):
                etat = 'VIVANTE' if cle in vivantes else 'hors index'
                idx = '' if i is None else f' [i={i}]'
                L.append(f"  {nom} · {champ}{idx} · {etat}")
                L.append(f"    {cle}")
            if not trouve:
                L.append("  aucune — ce fragment n'est cité par aucune fiche.")
        return "\n".join(L)
    finally:
        for s in st.values():
            try:
                s.close()
            except Exception:                                  # noqa: BLE001
                pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--contient', default='')
    ap.add_argument('--quarantaine', default='',
                    help="journal JSONL d'un re-clé, à auditer")
    a = ap.parse_args(argv)
    import os
    os.chdir(Path(__file__).resolve().parent)
    if a.quarantaine:
        print(afficher_audit(auditer_quarantaine(a.quarantaine)))
        print()
    print(rapport(a.base, a.contient or None))
    return 0


if __name__ == '__main__':
    sys.exit(main())
