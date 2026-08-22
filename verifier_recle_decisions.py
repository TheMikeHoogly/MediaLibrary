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
    a = ap.parse_args(argv)
    import os
    os.chdir(Path(__file__).resolve().parent)
    print(rapport(a.base, a.contient or None))
    return 0


if __name__ == '__main__':
    sys.exit(main())
