#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plan de rangement par ANNEE (lecture seule, testable hors serveur).

Regle (docs/RANGEMENT_2026.md, « Reorganisation par annee ») : un fichier sous
`_A TRIER` est range vers `<base>/Photos Mike/AAAA/` (ou `<proprietaire>/AAAA/`
si `_A TRIER` vit deja chez un proprietaire) d'apres sa date de prise de vue
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

# Le fonds a un PROPRIETAIRE (chantier 17, 26/08/2026) : ce qui sort de
# `Photos\_A TRIER` descend dans « Photos Mike », pas a la racine. Le 27 et le
# 28/08, faute de cette ligne, 1 217 photos du Takeout ont ete rangees dans
# `Photos\<annee>` — un dossier par annee a cote des dossiers proprietaires.
DOSSIER_FONDS = "Photos Mike"
# « Photos Mike », « Photos Flo », « Photos Papa » : un dossier proprietaire.
PROPRIETAIRE_RE = re.compile(r'^photos\s+\S', re.I)


def base_du_fonds(base):
    """Sous quel dossier ranger ce qui sort de `<base>/_A TRIER`.

    - `<base>` est deja un dossier proprietaire (« Photos Flo/_A TRIER ») :
      on range chez lui — c'est la boite de reception par proprietaire.
    - `<base>` est la racine `Photos` : on range chez le proprietaire du
      fonds, `Photos/Photos Mike/<annee>`."""
    base = Path(base)
    if PROPRIETAIRE_RE.match(base.name or ''):
        return base
    return base / DOSSIER_FONDS


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
    dst_dir = base_du_fonds(base) / (str(an) if an else SANS_DATE)
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
