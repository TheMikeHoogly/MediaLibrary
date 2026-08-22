#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — le re-clé que le rangement n'a jamais fait sur les décisions humaines
──────────────────────────────────────────────────────────────────────────────

LA CAUSE, ET CE N'EST PAS LA PURGE DU 17/08

`rekey_everywhere` transporte SEPT magasins quand une photo est déplacée ou
renommée, et quatre d'entre eux — `FACE`, `ANIMAL`, `PEOPLE`, `PETS` — passent
dans la MÊME boucle. Mais `PEOPLE` et `PETS` ne sont pas keyés par CHEMIN : leur
clé est le NOM, et les chemins vivent À L'INTÉRIEUR de la fiche —
`faces` = [[chemin, index]], `exclude` et `confirmed` = [chemin].
`store.rekey(ancien_chemin, nouveau_chemin)` y cherche donc une entrée dont la
clé serait un chemin. Il n'en trouve jamais, renvoie faux, et ne dit rien. La
boucle a l'air de couvrir quatre magasins ; elle en couvre deux.

Chaque rangement par année et chacun des **7 058** renommages appliqués a donc
pu laisser une décision humaine pointer vers une clé que l'index n'a plus. Le
TAG survit — il vit dans `tags` et dans le XMP, donc la photo garde son nom et
la règle 2 tient. Ce qui se perd, c'est la VÉRITÉ TERRAIN : quel VISAGE est
Flo, quelles photos ont été écartées d'un nom, lesquelles ont été confirmées.

POURQUOI LE GESTE EST UN RE-CLÉ, ET PAS UN NOUVEAU JUGEMENT

`rekey_everywhere` a bien déplacé l'ENTRÉE de `FACE_STORE` en bloc : la liste
des détections de la nouvelle clé est, octet pour octet, celle de l'ancienne.
L'INDEX d'une vignette est donc conservé par construction. Réparer, c'est
réécrire `ancien` → `nouveau` dans les listes de la fiche en gardant l'index —
pas re-juger, pas ré-apparier, pas inventer. C'est aussi ce qui permet de
réparer les décisions dont la purge du 21/08 a emporté les vecteurs : on n'en
a pas besoin.

CE QUI IDENTIFIE LE JUMEAU, ET QUAND ON SE TAIT

  * par JOURNAL — le plus fort des trois, et il était là depuis le début.
    Lu par `journaux_deplacements`, le module que le SERVEUR utilise aussi pour
    réparer : une seule lecture des journaux dans le projet, jamais deux.
    Chaque rangement, chaque dédoublonnage et chacun des 7 058 renommages a
    écrit son journal d'annulation dans `docs/` : `old_key` → `new_key` pour
    un déplacement ou un renommage, `src` → `canonique` pour un doublon
    absorbé. Ce n'est pas une ressemblance, c'est le geste lui-même, écrit par
    le programme qui l'a fait. Les chaînes se suivent (déplacée PUIS renommée),
    et un jumeau trouvé là ne dépend ni du nom ni des vecteurs — donc il
    survit à la purge du 21/08, qui a emporté les détections des clés mortes.
  * par NOM DE FICHIER — le rangement déplace sans renommer, c'est la forme
    dominante. **Refusé si plusieurs clés vivantes portent ce nom** et qu'aucun
    vecteur ne départage : deux photos homonymes existent, et se tromper de
    photo écrirait un jugement humain à côté.
  * par VECTEUR — le même fichier rend les mêmes détections au bruit float16
    près (`SIM_MEME_PHOTO` = 0,999). Insensible au renommage, c'est le CONTENU
    qui parle. Seul chemin quand la photo a été RENOMMÉE.

`preuve` vaut `journal`, `nom+vecteur`, `nom` (rien à comparer : la purge a
emporté les détections de la clé morte) ou `vecteur` (renommée).

Un score parfait est une alarme, pas un succès : 1,0000 est ATTENDU ici — c'est
le même fichier — et c'est pourquoi tout ce qui est en dessous de 0,999 est
refusé au lieu d'être arrondi.

CE QUE CE BANC NE FAIT PAS

Aucune écriture, ni en base ni sur le NAS. Il rend le PLAN de re-clé, fiche par
fiche. L'appliquer reste un geste du serveur, écrivain unique.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_report_orphelines.py --base copie.db
    python mesure_report_orphelines.py --base copie.db --json _plan_recle.json
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import journaux_deplacements
import mesure_propagation_noms as MP
from verifier_orphelins import basename_cle

SIM_MEME_PHOTO = 0.999

# (magasin de fiches, genre, magasin de détections, champ de la liste)
MAGASINS = (
    ('people', 'visage', 'faces', 'faces'),
    ('pets', 'animal', 'animals', 'animals'),
)


def ouvrir(base):
    """Ouvre la COPIE. Refuse `photos.db` comme tous les bancs du projet."""
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais mesurer sur photos.db. "
                         "Fabrique la copie (mesure_copie_base.py), "
                         "puis --base copie.db")
    if not p.exists():
        raise SystemExit(f"Base introuvable : {p}")
    from store_sqlite import SqliteStore
    return {n: SqliteStore(p, n) for n in
            ('tags', 'people', 'pets', 'faces', 'animals')}


def decisions(st):
    """Décisions humaines, avec la fiche et le magasin de détections associés."""
    out = []
    for fiches, genre, table, champ in MAGASINS:
        for pk, pe in st[fiches].data.items():
            if not isinstance(pe, dict) or not pe.get('name'):
                continue
            base = {'nom': pe['name'], 'fiche': pk, 'magasin': fiches,
                    'genre': genre, 'table': table, 'champ': champ}
            for kf in (pe.get('faces') or []):
                if isinstance(kf, (list, tuple)) and len(kf) == 2:
                    out.append({**base, 'type': 'rattachement',
                                'cle': kf[0], 'i': int(kf[1] or 0)})
            for cle in (pe.get('exclude') or []):
                out.append({**base, 'type': 'exclusion', 'cle': cle, 'i': None})
            for cle in (pe.get('confirmed') or []):
                out.append({**base, 'type': 'confirmation', 'cle': cle,
                            'i': None})
    return out


def vecteurs_de(store, champ, cle):
    """[(index, vecteur)] des détections d'une clé, dans l'ordre des index."""
    e = store.data.get(cle)
    if not isinstance(e, dict):
        return []
    out = []
    for i, d in enumerate(e.get(champ) or []):
        if not isinstance(d, dict) or not d.get('emb'):
            continue
        try:
            out.append((i, MP.emb_de_b64(d['emb'])))
        except Exception:                                      # noqa: BLE001
            pass
    return out


def matrice_vivante(store, champ, vivantes):
    """(matrice des détections vivantes, [(clé, index)]) — ou (None, [])."""
    import numpy as np
    lignes, ou = [], []
    for k in vivantes:
        for _i, v in vecteurs_de(store, champ, k):
            lignes.append(v)
            ou.append(k)
    if not lignes:
        return None, []
    return np.stack(lignes).astype(np.float32), ou


def sim_max(st, cle_a, cle_b):
    """Meilleure similarité entre les détections de deux clés, tous magasins.

    Rend None si l'un des deux côtés n'a aucune détection : il n'y a alors rien
    à comparer, et prétendre le contraire serait un score inventé."""
    import numpy as np
    best = None
    for table, champ in (('faces', 'faces'), ('animals', 'animals')):
        va = [v for _i, v in vecteurs_de(st[table], champ, cle_a)]
        vb = [v for _i, v in vecteurs_de(st[table], champ, cle_b)]
        if not va or not vb:
            continue
        s = float(np.max(np.stack(va) @ np.stack(vb).T))
        best = s if best is None else max(best, s)
    return best


def jumeau_par_vecteur(st, cle, vivantes_par_table):
    """La clé vivante qui porte la MÊME photo, reconnue par ses détections."""
    import numpy as np
    meilleure = 0.0
    for table, champ in (('faces', 'faces'), ('animals', 'animals')):
        M, ou = vivantes_par_table[table]
        if M is None:
            continue
        vv = [v for _i, v in vecteurs_de(st[table], champ, cle)]
        if not vv:
            continue
        sims = np.stack(vv).astype(np.float32) @ M.T
        plat = int(np.argmax(sims))
        best = float(sims.flat[plat])
        meilleure = max(meilleure, best)
        if best >= SIM_MEME_PHOTO:
            return ou[plat % len(ou)], round(best, 4)
    return None, round(meilleure, 4)


def jumeau_de(st, cle, par_nom, vivantes_par_table, chaine=None,
              vivantes=None):
    """(jumeau, preuve, similarité, raison du refus).

    Le JOURNAL d'abord : c'est le geste lui-même, pas une ressemblance. Puis le
    nom — forme dominante, gratuite. Plusieurs homonymes vivants : le vecteur
    départage, et à défaut on se tait."""
    if chaine:
        j = journaux_deplacements.suivre(chaine, cle, vivantes or set())
        if j:
            s = sim_max(st, cle, j)
            return j, 'journal', (round(s, 4) if s is not None else None), None
    cands = [k for k in par_nom.get(basename_cle(cle), []) if k != cle]
    if len(cands) == 1:
        s = sim_max(st, cle, cands[0])
        if s is None:
            return cands[0], 'nom', None, None
        if s >= SIM_MEME_PHOTO:
            return cands[0], 'nom+vecteur', round(s, 4), None
        return None, None, round(s, 4), 'homonyme : le vecteur dit non'
    if len(cands) > 1:
        scores = [(sim_max(st, cle, c), c) for c in cands]
        bons = [(s, c) for s, c in scores if s is not None
                and s >= SIM_MEME_PHOTO]
        if len(bons) == 1:
            return bons[0][1], 'nom+vecteur', round(bons[0][0], 4), None
        return None, None, None, f'{len(cands)} homonymes vivants, indécidable'
    j, s = jumeau_par_vecteur(st, cle, vivantes_par_table)
    if j:
        return j, 'vecteur', s, None
    return None, None, s, 'aucun jumeau'


def nb_detections(store, champ, cle):
    """Combien de détections porte une clé — bornes du re-clé d'un index."""
    e = store.data.get(cle)
    if not isinstance(e, dict):
        return 0
    return len(e.get(champ) or [])


def deja_la(fiche, d, jumeau):
    """La décision est-elle DÉJÀ posée sur le jumeau ? Un test par type."""
    if d['type'] == 'rattachement':
        return any(isinstance(kf, (list, tuple)) and len(kf) == 2
                   and kf[0] == jumeau and int(kf[1] or 0) == d['i']
                   for kf in (fiche.get('faces') or []))
    if d['type'] == 'exclusion':
        return jumeau in (fiche.get('exclude') or [])
    return jumeau in (fiche.get('confirmed') or [])


def mesurer(base, exemples=12):
    st = ouvrir(base)
    try:
        return _mesurer(st, exemples)
    finally:
        for s in st.values():
            try:
                s.close()
            except Exception:                                  # noqa: BLE001
                pass


def _mesurer(st, exemples):
    vivantes = set(st['tags'].data.keys())
    par_nom = defaultdict(list)
    for k in vivantes:
        par_nom[basename_cle(k)].append(k)

    toutes = decisions(st)
    mortes = [d for d in toutes if d['cle'] not in vivantes]
    cles_mortes = sorted({d['cle'] for d in mortes})

    # La matrice vivante ne sert qu'aux clés sans homonyme : on ne la construit
    # que si au moins une en a besoin (elle coûte quelques secondes).
    besoin = any(not [k for k in par_nom.get(basename_cle(c), []) if k != c]
                 for c in cles_mortes)
    vivantes_par_table = {'faces': (None, []), 'animals': (None, [])}
    if besoin:
        for table, champ in (('faces', 'faces'), ('animals', 'animals')):
            vivantes_par_table[table] = matrice_vivante(st[table], champ,
                                                        vivantes)

    chaine = journaux_deplacements.chaines(
        Path(__file__).resolve().parent / 'docs')

    jumeaux, refus_cle, refus_bornes = {}, {}, []
    preuves = Counter()
    for c in cles_mortes:
        j, preuve, sim, raison = jumeau_de(st, c, par_nom, vivantes_par_table,
                                           chaine, vivantes)
        if j:
            jumeaux[c] = {'jumeau': j, 'preuve': preuve, 'sim': sim}
            preuves[preuve] += 1
        else:
            refus_cle[c] = {'raison': raison, 'sim': sim}

    fiches = {'visage': st['people'].data, 'animal': st['pets'].data}
    plan = defaultdict(list)          # fiche -> [décisions à re-clé]
    compte = Counter()
    for d in mortes:
        info = jumeaux.get(d['cle'])
        if not info:
            compte['sans_jumeau'] += 1
            compte[f"sans_jumeau_{d['type']}"] += 1
            continue
        fiche = fiches[d['genre']].get(d['fiche']) or {}
        if deja_la(fiche, d, info['jumeau']):
            compte['deja_la'] += 1
            continue
        # Un rattachement désigne une VIGNETTE. Le re-clé garde son index —
        # légitime, puisque `rekey_everywhere` a déplacé la liste des détections
        # en bloc — mais un doublon absorbé (`canonique`) est un AUTRE fichier,
        # re-détecté pour son compte. Si l'index dépasse ce que le jumeau porte,
        # ce n'est plus un re-clé, c'est un pari : on refuse.
        if d['type'] == 'rattachement':
            n = nb_detections(st[d['table']], d['champ'], info['jumeau'])
            if d['i'] >= n:
                compte['hors_bornes'] += 1
                refus_bornes.append({**d, 'jumeau': info['jumeau'],
                                     'detections_du_jumeau': n})
                continue
        compte['a_recler'] += 1
        compte[f"a_recler_{d['type']}"] += 1
        plan[f"{d['magasin']}/{d['fiche']}"].append(
            {'type': d['type'], 'nom': d['nom'], 'i': d['i'],
             'de': d['cle'], 'vers': info['jumeau'],
             'preuve': info['preuve'], 'sim': info['sim']})

    return {
        'fonds': {'cles_vivantes': len(vivantes),
                  'decisions_totales': len(toutes),
                  'decisions_sur_cle_morte': len(mortes),
                  'cles_mortes_distinctes': len(cles_mortes)},
        'par_type_mortes': dict(Counter(d['type'] for d in mortes)),
        'cles': {'avec_jumeau': len(jumeaux), 'sans_jumeau': len(refus_cle)},
        'journal': {'deplacements_connus': len(chaine)},
        'preuves': dict(preuves),
        'refus': dict(Counter(v['raison'] for v in refus_cle.values())),
        'comptes': dict(compte),
        'fiches_touchees': len(plan),
        'refus_bornes': refus_bornes[:exemples],
        'plan': {k: v for k, v in plan.items()},
        'exemples': [x for v in list(plan.values())[:exemples] for x in v][:exemples],
    }


def afficher(r):
    L, f, c = [], r['fonds'], r['comptes']
    L.append(f"Décisions humaines {f['decisions_totales']} · sur une clé HORS "
             f"INDEX {f['decisions_sur_cle_morte']} {r['par_type_mortes']}")
    L.append(f"Clés mortes distinctes {f['cles_mortes_distinctes']} · "
             f"avec jumeau {r['cles']['avec_jumeau']} · "
             f"sans {r['cles']['sans_jumeau']} {r['refus']}")
    L.append(f"Preuve du jumeau : {r['preuves']} · journaux : "
             f"{r['journal']['deplacements_connus']} déplacements connus")
    L.append(f"À RE-CLÉ {c.get('a_recler', 0)} décisions sur "
             f"{r['fiches_touchees']} fiches "
             f"(rattachements {c.get('a_recler_rattachement', 0)}, "
             f"exclusions {c.get('a_recler_exclusion', 0)}, "
             f"confirmations {c.get('a_recler_confirmation', 0)}) · "
             f"déjà là {c.get('deja_la', 0)} · "
             f"index hors bornes {c.get('hors_bornes', 0)} · "
             f"perdues {c.get('sans_jumeau', 0)} "
             f"(rattachements {c.get('sans_jumeau_rattachement', 0)}, "
             f"exclusions {c.get('sans_jumeau_exclusion', 0)}, "
             f"confirmations {c.get('sans_jumeau_confirmation', 0)})")
    L.append("")
    for x in r['exemples']:
        L.append(f"  {x['type']} · {x['nom']} · preuve {x['preuve']} "
                 f"({x['sim']}) · i={x['i']}")
        L.append(f"    de   : {x['de']}")
        L.append(f"    vers : {x['vers']}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--json', default='')
    ap.add_argument('--exemples', type=int, default=12)
    a = ap.parse_args(argv)
    import os
    os.chdir(Path(__file__).resolve().parent)
    r = mesurer(a.base, a.exemples)
    print(afficher(r))
    if a.json:
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=1),
                                encoding='utf-8')
        print(f"\nJSON : {a.json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
