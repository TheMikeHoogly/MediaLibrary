#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plan de rangement par ANNEE (lecture seule, testable hors serveur).

Regle (docs/RANGEMENT_2026.md, « Reorganisation par annee ») : un fichier sous
`_A TRIER` est range vers `<base>/AAAA/` d'apres sa date de prise de vue
(`_best_time` cote serveur, injecte ici comme un simple timestamp). Sans date
FIABLE, il va dans un bac explicite `_SANS_DATE/` — on ne devine jamais une
annee. On aplatit (on ne recree pas l'arborescence sous `_A TRIER`).

Ce module ne DEPLACE rien : il produit un plan a provenance (liste de moves
src->dst) qu'un humain relit, puis qu'on applique avec la primitive de
deplacement deja testee (fichiers.FileOps / rekey_everywhere : aucun nom perdu).
"""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path

# _A TRIER, A TRIER, _A_TRIER, a trier... (tolerant a la casse et au separateur)
ATRI_RE = re.compile(r'^_?a[ _]tri', re.I)
SANS_DATE = "_SANS_DATE"


def annee_de(ts):
    """Annee d'un timestamp epoch, ou None si absent/invalide."""
    if not ts or ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts).year
    except (OSError, OverflowError, ValueError):
        return None


def _atri_index(parts):
    """Index du 1er composant « _A TRIER » dans parts, ou None."""
    for i, p in enumerate(parts):
        if ATRI_RE.match(str(p).strip()):
            return i
    return None


def cible(abspath, ts):
    """(dst_dir, dst) pour ranger `abspath` par annee, ou None si le chemin n'est
    PAS sous « _A TRIER ». `base` = tout ce qui precede le composant _A TRIER."""
    p = Path(abspath)
    idx = _atri_index(p.parts)
    if idx is None:
        return None
    base = Path(*p.parts[:idx]) if idx > 0 else Path(p.anchor or ".")
    an = annee_de(ts)
    dst_dir = base / (str(an) if an else SANS_DATE)
    return dst_dir, dst_dir / p.name


def construire_plan(items):
    """`items` : iterable de (key, abspath, ts). Renvoie un plan a provenance :
      - moves      : [{key, src, dst, annee}] a deplacer,
      - deja       : nb deja dans leur dossier annee (rien a faire),
      - conflits   : [{key, src, dst}] dont la cible entre en COLLISION avec un
                     autre move du plan (meme dossier + meme nom) — a trancher,
      - sans_date  : nb ranges dans _SANS_DATE,
      - par_annee  : {annee: n}, total_a_ranger.
    Les collisions avec un fichier DEJA sur le disque sont, elles, refusees au
    moment de l'application (la primitive de deplacement ne recouvre jamais)."""
    moves, conflits = [], []
    deja = 0
    vus = {}                       # dst normalise -> key (collisions internes)
    par_annee = Counter()
    sans_date = 0
    for key, abspath, ts in items:
        r = cible(abspath, ts)
        if r is None:
            continue
        dst_dir, dst = r
        if Path(abspath).parent == dst_dir:
            deja += 1
            continue
        dn = str(dst).lower()
        if dn in vus:
            conflits.append({'key': key, 'src': str(abspath), 'dst': str(dst)})
            continue
        vus[dn] = key
        an = annee_de(ts)
        if an:
            par_annee[an] += 1
        else:
            sans_date += 1
        moves.append({'key': key, 'src': str(abspath), 'dst': str(dst),
                      'annee': an or SANS_DATE})
    return {'moves': moves, 'deja': deja, 'conflits': conflits,
            'sans_date': sans_date, 'par_annee': dict(sorted(par_annee.items())),
            'total_a_ranger': len(moves)}
