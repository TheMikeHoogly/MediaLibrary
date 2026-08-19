#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — la règle de lieu que Mike VOIT (chantier 14a-i)
──────────────────────────────────────────────────────────────────────────────

LA QUESTION, ET POURQUOI ELLE SE POSE MAINTENANT

Le lieu a **trois** règles, pas deux (19/08, observé) :

  1. le RENOMMAGE (`renommage_facts.resolve_path_place`) — sous-chaîne ;
  2. le Knowledge Builder (`faits_vue.lieu_par_segments`) — segments entiers,
     corrigé et branché ;
  3. **`server.places_list` et `server._cles_du_lieu`** — la page `/sujets` ET
     la recherche : sous-chaîne, intacte, et **la seule que Mike voie**.

En réel : `/sujets` affiche « Ins : 493 photos » alors que 442 viennent de
« Cousins&Cousines », et une recherche « Ins » rend 80 résultats dont 32 en
viennent. Corriger (2) sans (3), c'est corriger là où personne ne regarde.

Avant de rebrancher (3) sur la règle des segments, il faut savoir ce que ça
COÛTE : la règle des segments évite les collés, mais elle rate des mots
ENTIERS — libellés MULTI-MOTS jamais essayés (« Vallée d'Aoste » sous
« Weekend Vallée d'Aoste ») et traits d'union qui cassent la clé
(« Crans-Montana » devient « Crans Montana »). Ce banc chiffre les deux
directions, libellé par libellé, AVANT tout changement.

**Un avant/après n'existe que si l'AVANT a été enregistré** (`eval/METHODE.md`).

CE QU'IL MESURE

  A — la règle d'AUJOURD'HUI : sous-chaîne du chemin relatif, tous les
      libellés qui matchent (c'est ainsi que `/sujets` compte).
  B — les SEGMENTS, options de prod (`faits_vue.OPTIONS_PROD`) : ce que
      donnerait une unification sans rien corriger d'autre.
  C — les SEGMENTS unifiés (`faits_vue.OPTIONS_UNIFIEE`) : groupes de mots
      contigus essayés, trait d'union conservé dans la clé.

Puis, pour chaque paire (photo, libellé) que A rend et que C ne rend pas, il
dit POURQUOI — collé à l'intérieur d'un mot (bon débarras), présent seulement
dans le nom de FICHIER, segment jugé non-lieu, ou mot trop court (vraie perte).

CE QU'IL NE FAIT PAS

Aucun `UPDATE`, aucun fichier touché, aucun accès NAS, aucun modèle. Il refuse
d'ouvrir un fichier nommé `photos.db` : le serveur est l'écrivain unique, on
mesure sur une COPIE (invariant du projet).

LA LOGIQUE DE L'APRÈS VIENT DE LA PROD : `faits_vue` est le module que
`server` appellera, le banc l'IMPORTE (`eval/METHODE.md`, 14/08). L'AVANT, lui,
est RECOPIÉ ici en trois lignes — il n'existe qu'inline dans `server.py`, et
c'est exactement ce que ce chantier corrige. La recopie est donc vérifiée
contre le serveur VIVANT : « Ins » doit sortir à 493 sur `/sujets`. Deux
chemins qui tombent sur le même chiffre.

USAGE
    python mesure_lieu_visible.py --base copie.db [--projet .] [--json r.json]
"""

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    import faits_vue
    from mesure_faits_vue import ouvrir, racines_media
    from renommage_facts import _sans_accents, load_lieux
except ImportError:
    sys.stderr.write("mesure_lieu_visible : modules du projet introuvables — "
                     "lancer depuis le dossier du projet.\n")
    raise


# ───────────────────────────── données (COPIE) ─────────────────────────────

def cles_de_l_index(cx):
    """Toutes les clés de l'index — c'est sur elles que `places_list` et
    `_cles_du_lieu` itèrent (`STORE.data`)."""
    return [r[0] for r in cx.execute('SELECT k FROM tags')]


def gps_par_cle(projet):
    """{clé: libellé} du géocodage inverse — miroir de
    `server.gps_places_connus` (simple lecture du JSON produit hors ligne)."""
    try:
        d = json.loads((Path(projet) / 'gps_places.json')
                       .read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


# ────────────────────────── A : la règle d'aujourd'hui ──────────────────────

def regle_actuelle(chemin_norm, lieux_norm):
    """**RECOPIE** de `server.places_list` / `_cles_du_lieu` : le libellé sans
    accents est cherché en SOUS-CHAÎNE dans le chemin relatif — nom de fichier
    compris. Trois lignes, et les 577 collés du fonds.

    Recopiée faute d'être extractible : elle est inline dans `server.py`. C'est
    la seule entorse à « le banc importe la prod », et elle se vérifie contre
    le serveur vivant (voir l'en-tête)."""
    return {lbl for nk, lbl in lieux_norm if nk and nk in chemin_norm}


# ───────────────────────── pourquoi une paire disparaît ─────────────────────

_MOTS = re.compile(r"[^0-9a-z]+")


def _tokens(texte):
    return [m for m in _MOTS.split(_sans_accents(texte)) if m]


def est_mot_entier(libelle, texte):
    """Le libellé apparaît-il dans ce texte comme une suite de MOTS ENTIERS ?

    « Ins » n'est pas un mot entier de « Cousins&Cousines » ; « Orbe » n'en est
    pas un de « Vallorbe ». C'est le juge de ce banc : il sépare le faux
    positif (bon débarras) de la vraie perte."""
    cible, mots = _tokens(libelle), _tokens(texte)
    n = len(cible)
    if not n or len(mots) < n:
        return False
    return any(mots[i:i + n] == cible for i in range(len(mots) - n + 1))


def cause_du_retrait(cle, libelle, racines, options):
    """Pourquoi la règle des segments ne rend-elle pas ce libellé que la
    sous-chaîne rendait ? Rend un motif court, comparable, comptable."""
    rel = faits_vue.chemin_relatif(cle, racines).replace('/', '\\')
    parts = rel.split('\\')
    dossiers, fichier = parts[:-1], (parts[-1] if parts else '')
    if options.get('avec_fichier'):
        dossiers = dossiers + [fichier]
    porteurs = [p for p in dossiers if est_mot_entier(libelle, p)]
    if not porteurs:
        if est_mot_entier(libelle, fichier):
            return 'seulement dans le nom de fichier'
        return 'colle a l interieur d un mot'
    sep = r'[\s_\-]+' if options.get('traits_separateurs', True) else r'[\s_]+'
    for p in porteurs:
        propre = faits_vue.lieu_plausible(p, sep)
        if propre is None:
            continue
        mots = _tokens(libelle)
        if len(mots) > 1:
            return 'libelle multi-mots jamais essaye'
        if len(mots[0]) < options.get('seuil_mot', 5):
            return 'mot plus court que le seuil'
        return 'autre (segment retenu, libelle non trouve)'
    return 'segment juge non-lieu (bruit, trop court, annee)'


# ────────────────────────────── la mesure ──────────────────────────────

# Les variantes MESURÉES. `prod` est la règle des segments telle qu'elle tourne
# déjà dans le Knowledge Builder ; les suivantes ajoutent UNE correction à la
# fois, pour qu'aucun gain ni aucune perte ne soit attribué au mauvais réglage.
_AV = faits_vue.OPTIONS_AVANT_14A
VARIANTES = [
    ('B  segments (avant 14a)', dict(_AV)),
    ('C  + groupes de mots + trait d union',
     dict(_AV, multi_mots=True, traits_separateurs=False)),
    ('D  C + seuil de mot a 4',
     dict(_AV, multi_mots=True, traits_separateurs=False, seuil_mot=4)),
    ('E  D + decoupe des mots COLLES', {}),
    ('F  E + le nom de FICHIER compte', {'avec_fichier': True}),
]


def compter(par_cle):
    """{libellé: nombre de photos} — la colonne de `/sujets`."""
    c = Counter()
    for labels in par_cle.values():
        for l in labels:
            c[l] += 1
    return c


def compter_sujets(par_cle, gps):
    """`/sujets` tel qu'il s'affiche : le GPS PRIME, une photo déjà nommée par
    GPS n'est pas re-comptée par le chemin (`places_list`)."""
    c = Counter()
    for k, labels in par_cle.items():
        g = gps.get(k)
        if g:
            c[g] += 1
        else:
            for l in labels:
                c[l] += 1
    return c


def mesurer(base, projet, exemples=3):
    cx = ouvrir(base)
    racines = racines_media(projet)
    lieux = load_lieux(Path(projet) / 'lieux.txt')
    lieux_norm = [(nk, lbl) for nk, lbl in lieux.items() if nk]
    gps = gps_par_cle(projet)
    cles = cles_de_l_index(cx)

    t0 = time.time()
    A = {k: regle_actuelle(_sans_accents(faits_vue.chemin_relatif(k, racines)),
                           lieux_norm) for k in cles}
    temps = {'A  sous-chaine (aujourd hui)': time.time() - t0}

    variantes = {}
    for nom, opts in VARIANTES:
        t0 = time.time()
        variantes[nom] = {k: set(faits_vue.lieux_du_chemin(
            k, lieux, racines, tous=True, **opts)) for k in cles}
        temps[nom] = time.time() - t0

    resultats = {}
    for nom, opts in VARIANTES:
        V = variantes[nom]
        causes, exs = Counter(), defaultdict(list)
        par_lieu = defaultdict(Counter)          # libellé -> cause -> n
        ajouts, ex_ajouts = Counter(), defaultdict(list)
        for k in cles:
            for lbl in A[k] - V[k]:
                cause = cause_du_retrait(k, lbl, racines, opts)
                causes[cause] += 1
                par_lieu[lbl][cause] += 1
                if len(exs[cause]) < exemples:
                    exs[cause].append((lbl, k))
            for lbl in V[k] - A[k]:
                ajouts[lbl] += 1
                if len(ex_ajouts[lbl]) < 1:
                    ex_ajouts[lbl].append(k)
        # LE chiffre qui compte : une photo qui perd son SEUL lieu sort de
        # /sujets et de la recherche. Perdre un doublon (« Orbe » quand
        # « Vallorbe » reste) ne coûte rien ; perdre le dernier, si.
        orphelines = [k for k in cles if A[k] and not V[k] and not gps.get(k)]
        perdus_par_lieu = Counter()
        for k in orphelines:
            for lbl in A[k]:
                perdus_par_lieu[lbl] += 1
        resultats[nom] = {
            'orphelines': len(orphelines),
            'orphelines_par_lieu': perdus_par_lieu,
            'exemples_orphelines': orphelines[:4],
            'photos': sum(1 for k in cles if V[k]),
            'paires': sum(len(V[k]) for k in cles),
            'causes': causes, 'exemples': dict(exs), 'par_lieu': par_lieu,
            'ajouts': ajouts, 'exemples_ajouts': dict(ex_ajouts),
            'sujets': compter_sujets(V, gps), 'compte': compter(V),
        }

    # Recherche : ce que `_cles_du_lieu` rend pour UN lieu demandé (chemin OU
    # libellé GPS). Le OU du GPS est inchangé — seule la branche CHEMIN bouge.
    dernier = variantes[VARIANTES[-1][0]]
    gps_norm = {k: _sans_accents(v or '') for k, v in gps.items()}
    recherche = {}
    for nk, lbl in lieux_norm:
        av = sum(1 for k in cles if lbl in A[k] or nk in gps_norm.get(k, ''))
        ap = sum(1 for k in cles
                 if lbl in dernier[k] or nk in gps_norm.get(k, ''))
        if av or ap:
            recherche[lbl] = (av, ap)

    return {
        'corpus': {'cles': len(cles), 'lieux': len(lieux),
                   'racines': racines, 'gps': len(gps)},
        'A': {'photos': sum(1 for k in cles if A[k]),
              'paires': sum(len(A[k]) for k in cles),
              'sujets': compter_sujets(A, gps), 'compte': compter(A)},
        'variantes': resultats, 'recherche': recherche, 'temps': temps,
        'ordre': [n for n, _ in VARIANTES],
    }


# ─────────────────────────────── rapport ───────────────────────────────

def pourcent(x, n):
    return f"{100.0 * x / n:.2f} %" if n else "—"


def rapport(r):
    c = r['corpus']
    L = []
    A = L.append
    A("=" * 78)
    A("MESURE — la regle de lieu VISIBLE (/sujets et recherche)")
    A("=" * 78)
    A(f"Corpus : {c['cles']} cles, {c['lieux']} lieux connus, "
      f"{c['gps']} photos geocodees, {len(c['racines'])} racines")
    A("")
    A("1. COUVERTURE — lieu deduit du CHEMIN seul (GPS mis a part)")
    A(f"   {'regle':<40}{'photos':>9}{'%':>9}{'paires':>9}")
    A(f"   {'A  sous-chaine (aujourd hui)':<40}{r['A']['photos']:>9}"
      f"{pourcent(r['A']['photos'], c['cles']):>9}{r['A']['paires']:>9}")
    for nom in r['ordre']:
        v = r['variantes'][nom]
        A(f"   {nom:<40}{v['photos']:>9}"
          f"{pourcent(v['photos'], c['cles']):>9}{v['paires']:>9}")
    A("")
    for nom in r['ordre']:
        v = r['variantes'][nom]
        A(f"2. « {nom} » — ce qu'elle RETIRE a la sous-chaine, et pourquoi")
        A(f"   {sum(v['causes'].values())} paires (photo, lieu) retirees, "
          f"{sum(v['ajouts'].values())} ajoutees")
        A(f"   >>> {v['orphelines']} photos n'ont PLUS AUCUN lieu "
          f"(elles en avaient un) — c'est le seul cout qui se voit")
        if v['orphelines_par_lieu']:
            A("       " + ', '.join(
                f"{lbl} {n}" for lbl, n in
                v['orphelines_par_lieu'].most_common(8)))
        for cause, n in v['causes'].most_common():
            A(f"     {n:>6}  {cause}")
            for lbl, k in v['exemples'].get(cause, [])[:2]:
                A(f"             ex. « {lbl} »  <-  {k[-64:]}")
        if v['ajouts']:
            A("     ajouts :")
            for lbl, n in v['ajouts'].most_common(8):
                ex = (v['exemples_ajouts'].get(lbl) or [''])[0]
                A(f"     {n:>6}  {lbl:<22} ex. {ex[-52:]}")
        A("")
    dernier = r['ordre'][-1]
    v = r['variantes'][dernier]
    A(f"3. PAR LIEU — ce que « {dernier} » retire, cause par cause")
    A(f"   {'lieu':<20}{'perd':>6}  causes")
    for lbl, causes in sorted(v['par_lieu'].items(),
                              key=lambda x: -sum(x[1].values()))[:16]:
        detail = ', '.join(f"{n} {ca}" for ca, n in causes.most_common())
        A(f"   {lbl:<20}{sum(causes.values()):>6}  {detail[:52]}")
    A("")
    A(f"4. LA PAGE /sujets — avant / apres « {dernier} » (GPS prioritaire)")
    sA, sC = r['A']['sujets'], v['sujets']
    bouge = sorted(set(sA) | set(sC),
                   key=lambda l: -abs(sA.get(l, 0) - sC.get(l, 0)))
    A(f"   {'lieu':<26}{'avant':>8}{'apres':>8}{'ecart':>9}")
    for lbl in bouge[:22]:
        av, ap = sA.get(lbl, 0), sC.get(lbl, 0)
        if av == ap:
            break
        A(f"   {lbl:<26}{av:>8}{ap:>8}{ap - av:>+9}")
    A("")
    A("5. LA RECHERCHE — nombre de cles rendues par lieu demande")
    rec = r['recherche']
    bouge = sorted(rec, key=lambda l: -abs(rec[l][0] - rec[l][1]))
    A(f"   {'lieu':<26}{'avant':>8}{'apres':>8}{'ecart':>9}")
    for lbl in bouge[:16]:
        av, ap = rec[lbl]
        if av == ap:
            break
        A(f"   {lbl:<26}{av:>8}{ap:>8}{ap - av:>+9}")
    A("")
    A("6. COUT (index entier, en memoire, sans acces disque)")
    n = c['cles']
    for nom, t in r['temps'].items():
        A(f"   {nom:<40}{t:>6.2f} s   ({1000.0 * t / n * 50:.1f} ms / 50)")
    A("")
    A("Le banc ne tranche pas : il chiffre. La decision va dans DECISIONS.md.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', required=True, help='COPIE de photos.db')
    ap.add_argument('--projet', default='.', help='dossier du projet')
    ap.add_argument('--json', help='ecrire le rapport brut en JSON')
    a = ap.parse_args()
    r = mesurer(a.base, a.projet)
    print(rapport(r))
    if a.json:
        brut = {k: (dict(v) if isinstance(v, (Counter, defaultdict)) else v)
                for k, v in r.items()}
        brut['recherche'] = {k: list(v) for k, v in r['recherche'].items()}
        Path(a.json).write_text(
            json.dumps(brut, ensure_ascii=False, indent=1, default=str),
            encoding='utf-8')
        print(f"\nJSON : {a.json}")


if __name__ == '__main__':
    main()
