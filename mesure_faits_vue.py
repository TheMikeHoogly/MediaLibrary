#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — la VUE des `faits` tient-elle, et à quel prix ?
──────────────────────────────────────────────────────────────────────────────

LA QUESTION, ET POURQUOI ELLE SE POSE MAINTENANT

`mesure_faits_backfill.py` a compté ce qu'un backfill ÉCRIT rendrait : 42 974
entrées pourvues sur 43 064 (99,79 %) — « une alarme, pas un succès », dont
seulement 30 222 avec un fait NON-date. Deux constats ont suivi, et ce sont eux
qui interdisent d'écrire tout de suite :

  (a) `faits` est un INSTANTANÉ : 12 des 81 entrées déjà pourvues divergent
      DÉJÀ de l'index (noms retirés depuis). Écrire 43 064 champs, c'est
      programmer 43 064 péremptions.
  (b) le LIEU du backfill vient du miroir du renommage
      (`resolve_path_place`, sous-chaîne) : 577 photos reçoivent un lieu collé
      À L'INTÉRIEUR d'un mot, dont 442 « Ins » depuis « Cousins&Cousines ».

D'où l'alternative : ne rien écrire, et CALCULER les faits à la demande
(`faits_vue`). Une vue ne se périme pas — mais elle n'est une réponse que si
elle est PAYABLE. Ce module mesure les deux moitiés de la question :

  1. **Ce que la vue rend** — couverture, matière par type, et l'écart avec le
     backfill mesuré : combien de lieux collés disparaissent, combien de faits
     l'autorité vivante (fiches + `exclude`) ajoute ou retire.
  2. **Ce qu'elle coûte** — temps de calcul pour une PAGE (50 photos, le cas
     qui sert l'utilisateur) et pour l'INDEX ENTIER (le cas d'un filtre de
     recherche), avec et sans index inversé des noms. `server._noms_attendus`
     balaie toutes les fiches personnes/animaux à CHAQUE appel : c'est le seul
     endroit où une vue peut coûter cher, et il faut le chiffrer avant de
     conclure quoi que ce soit.

CE QU'IL NE FAIT PAS

Aucun `UPDATE`, aucun fichier touché, aucun accès NAS, aucun modèle. Il refuse
d'ouvrir un fichier nommé `photos.db` : le serveur est l'écrivain unique, on
mesure sur une COPIE (invariant du projet).

LA LOGIQUE VIENT DE LA PROD, ELLE N'EST PAS RECOPIÉE. `faits_vue` est le module
que `server` appellera ; le banc l'IMPORTE (`eval/METHODE.md`, 14/08). Restent
deux DONNÉES que le banc doit fournir lui-même, faute de serveur :
  · les RACINES média — lues dans les fichiers de config SANS `is_dir()` (le
    NAS n'est pas monté ici ; `server._load_dirs_file` les filtrerait toutes) ;
  · l'AUTORITÉ des noms — reconstruite depuis les tables `people`/`pets` de la
    copie, miroir de `server._noms_attendus` (fiches `faces` + index, `exclude`
    faisant autorité). C'est une donnée d'état, pas une règle.

FUSEAU HORAIRE — la base porte des epochs LOCAUX. Lancé ailleurs qu'en
Europe/Zurich, le libellé d'une date du 31 décembre au soir peut basculer
d'année ; les COMPTES, eux, ne bougent pas. Le fuseau est affiché en tête.

USAGE
    python mesure_faits_vue.py --base copie.db [--projet .] [--json rapport.json]
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    import faits_vue
    import tagging_meta
    from renommage_facts import (_media_relative_dir, _sans_accents, load_lieux,
                                 names_from_entry, resolve_path_place)
except ImportError:
    sys.stderr.write("mesure_faits_vue : modules du projet introuvables — "
                     "lancer depuis le dossier du projet.\n")
    raise


# ───────────────────────── lectures (COPIE, lecture seule) ─────────────────────

def ouvrir(base):
    """Ouvre la COPIE. Refuse `photos.db` : le serveur est l'écrivain unique."""
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais mesurer sur photos.db. "
                         "Copie la base d'abord, puis --base copie.db")
    if not p.exists():
        raise SystemExit(f"Base introuvable : {p}")
    return sqlite3.connect(str(p))


def lire_json(v):
    try:
        e = json.loads(v)
        return e if isinstance(e, dict) else {}
    except (ValueError, TypeError):
        return {}


def racines_media(projet):
    """Racines média, dans l'ORDRE de `server.media_roots()` : Uploads d'abord
    (la plus spécifique), puis les dossiers tagués, puis ceux à explorer.

    Lues comme des DONNÉES : `server._load_dirs_file` filtre par `is_dir()`, ce
    qui viderait la liste ici (NAS non monté). Le filtre ne change pas la
    RÈGLE, seulement quelles racines existent — et une racine absente ne
    retirerait rien du chemin, donc le NAS redeviendrait un lieu. Mieux vaut la
    donnée déclarée que le silence."""
    def lignes(nom):
        out = []
        try:
            for l in (Path(projet) / nom).read_text(encoding='utf-8').splitlines():
                l = l.strip().strip('"')
                if l and not l.startswith('#'):
                    out.append(l)
        except OSError:
            pass
        return out

    racines, vus = [], set()
    for r in lignes('dossier_uploads.txt') + lignes('dossiers_a_taguer.txt') \
            + lignes('dossiers_a_explorer.txt'):
        if r.lower() not in vus:
            vus.add(r.lower())
            racines.append(r)
    return racines


def especes_par_cle(cx):
    """{clé: {espèces}} depuis la table `animals` (DÉTECTIONS, pas l'index)."""
    out = {}
    try:
        cur = cx.execute('SELECT k, v FROM animals')
    except sqlite3.Error:
        return out
    for k, v in cur:
        sp = {a.get('species') for a in (lire_json(v).get('animals') or [])
              if isinstance(a, dict) and a.get('species')}
        if sp:
            out[k] = sp
    return out


def autorite_des_noms(cx):
    """(attribues, exclus, nb_fiches) — miroir de `server._noms_attendus`.

    `attribues` : {clé: {tag}} d'après les `faces` des fiches personnes/animaux.
    `exclus`    : {clé: {tag en minuscules}} d'après leurs `exclude`.

    C'est l'AUTORITÉ VIVANTE : un nom retiré (`exclude`) ne peut pas revenir,
    quoi qu'en dise encore l'index. Le champ écrit, lui, n'a pas ce recours —
    d'où les 12 divergences."""
    attribues, exclus = defaultdict(set), defaultdict(set)
    fiches = 0
    for table, prefixe in (('people', 'personne'), ('pets', 'animal')):
        try:
            cur = cx.execute(f'SELECT k, v FROM "{table}"')
        except sqlite3.Error:
            continue
        for _k, v in cur:
            e = lire_json(v)
            nom = e.get('name')
            if not nom:
                continue
            fiches += 1
            tag = f"{prefixe}:{nom}"
            for cle in (e.get('exclude') or []):
                exclus[cle].add(tag.lower())
            for kf in (e.get('faces') or []):
                if isinstance(kf, (list, tuple)) and len(kf) == 2:
                    attribues[kf[0]].add(tag)
    return attribues, exclus, fiches


def noms_attendus(cle, entree, attribues, exclus):
    """Tags de nom qui font AUTORITÉ maintenant. Miroir de
    `server._noms_attendus` : fiches + index (`kw_fr` seul, comme la prod),
    moins les `exclude`."""
    ex = exclus.get(cle) or set()
    tags = [t for t in (attribues.get(cle) or set()) if t.lower() not in ex]
    for t in (entree.get('kw_fr') or []):
        tl = str(t).lower()
        if (tl.startswith('personne:') or tl.startswith('animal:')) \
                and tl not in ex and t not in tags:
            tags.append(t)
    return tags


# ────────────────────────────── comparaisons ──────────────────────────────

def signature(F):
    """{(type, valeur)} — comparer deux listes de faits sans l'ordre ni la
    source."""
    return {(f.get('t'), f.get('v')) for f in (F or [])}


def pourquoi_rate(cle, label, lieux, racines):
    """Pourquoi la règle des SEGMENTS rate-t-elle un libellé que la règle du
    renommage trouve comme MOT ENTIER ?

    Éviter 577 faux lieux n'a de sens que si on sait ce que ça coûte en vrais.
    Ce diagnostic sépare les causes, parce qu'elles n'appellent pas le même
    remède : un segment jeté comme « bruit » est une décision assumée ; un mot
    de moins de 5 lettres écarté est un SEUIL, et un seuil se règle."""
    norm = _sans_accents(label)
    parts = faits_vue.chemin_relatif(cle, racines).replace('/', '\\').split('\\')[:-1]
    for p in reversed(parts):
        if not re.search(r'(?<![a-z])' + re.escape(norm) + r'(?![a-z])',
                         _sans_accents(p)):
            continue                      # le libellé n'est pas dans CE segment
        propre = faits_vue.lieu_plausible(p)
        if not propre:
            return 'segment jete (bruit, trop court, ou purement numerique)'
        mots = propre.split()
        if _sans_accents(propre) == norm:
            return 'incoherent (le segment nettoye EST le libelle)'
        if any(_sans_accents(m) == norm for m in mots):
            court = [m for m in mots if _sans_accents(m) == norm][0]
            return (f'mot de {len(court)} lettres, sous le seuil de 5'
                    if len(court) < 5 else 'mot >= 5 lettres mais non trouve')
        if ' ' in label.strip():
            # La règle ne teste que le segment ENTIER ou ses mots pris un par
            # un : un libellé de plusieurs mots niché dans un segment plus long
            # (« 2013 Vallee d Aoste Italie ») n'est jamais essayé. Ce n'est
            # pas un seuil, c'est un trou.
            return 'libelle MULTI-MOTS, jamais essaye dans un segment plus long'
        return 'libelle efface par le nettoyage du segment (annee, prefixe)'
    return 'libelle hors des segments de dossier'


def lieu_colle_dans_un_mot(cle, lieu):
    """Le lieu tiré du CHEMIN par la règle du RENOMMAGE est-il collé À
    L'INTÉRIEUR d'un mot ? (« Ins » dans « Cousins&Cousines ».)"""
    lab = _sans_accents(lieu or '')
    if not lab:
        return False
    return not re.search(r'(?<![a-z])' + re.escape(lab) + r'(?![a-z])',
                         _media_relative_dir(cle))


# ─────────────────────────────── la mesure ───────────────────────────────

def mesurer(base, projet, exemples=6):
    cx = ouvrir(base)
    t0 = time.perf_counter()
    esp = especes_par_cle(cx)
    gps = {}
    try:
        g = json.loads((Path(projet) / 'gps_places.json').read_text(encoding='utf-8'))
        gps = g if isinstance(g, dict) else {}
    except (OSError, ValueError):
        pass
    lieux = load_lieux(Path(projet) / 'lieux.txt')
    racines = racines_media(projet)
    attribues, exclus, fiches = autorite_des_noms(cx)
    t_prep = time.perf_counter() - t0

    entrees = list(cx.execute('SELECT k, v FROM tags'))
    t_lect = time.perf_counter() - t0 - t_prep

    n = len(entrees)
    dispo = Counter()
    par_nb = Counter()
    src_date, src_lieu = Counter(), Counter()
    non_date = date_seule = 0
    muettes = []

    # Écarts VUE ↔ BACKFILL (ce qu'on gagne à ne pas écrire).
    lieu_perdu = Counter()       # lieux collés que la vue ne donne plus
    lieu_rate = Counter()        # lieux MOT ENTIER que la vue rate quand même
    lieu_rate_pourquoi = Counter()
    lieu_gagne = 0               # lieu que seule la règle des segments trouve
    lieu_different = Counter()   # les deux répondent, mais pas la même chose
    exemples_lieux, exemples_rates = [], []
    noms_retires = noms_ajoutes = 0

    # Écarts VUE ↔ champ `faits` ÉCRIT (les 81, dont 12 divergent).
    ecrites = identiques = differentes = 0
    resolues_par_l_autorite = 0
    exemples_ecarts = []

    t1 = time.perf_counter()
    for cle, v in entrees:
        e = lire_json(v)
        na = noms_attendus(cle, e, attribues, exclus)
        a = faits_vue.assertions(cle, e, especes=esp.get(cle),
                                 gps_place=gps.get(cle), lieux=lieux,
                                 racines=racines, noms_attendus=na)
        F = faits_vue.faits(cle, e, especes=esp.get(cle),
                            gps_place=gps.get(cle), lieux=lieux,
                            racines=racines, noms_attendus=na)

        if a['persons']:
            dispo['personne'] += 1
        if a['animals']:
            dispo['animal'] += 1
        if a['species']:
            dispo['espece'] += 1
        if a['lieu']:
            dispo['lieu'] += 1
            src_lieu[a['lieu_src']] += 1
        if a['date']:
            dispo['date'] += 1
            src_date[a['date_src']] += 1

        types = {f['t'] for f in F}
        if types - {'date'}:
            non_date += 1
        elif types:
            date_seule += 1
        par_nb[len(F)] += 1
        if not F and len(muettes) < exemples:
            muettes.append(cle)

        # — variante BACKFILL : noms de l'index seuls, lieu par sous-chaîne —
        if not gps.get(cle):
            lb = resolve_path_place(cle, lieux)
            if lb and not a['lieu']:
                if lieu_colle_dans_un_mot(cle, lb):
                    lieu_perdu[lb] += 1          # « Ins » dans « Cousins » — bien perdu
                else:
                    lieu_rate[lb] += 1           # MOT ENTIER : la vue le rate
                    lieu_rate_pourquoi[pourquoi_rate(cle, lb, lieux, racines)] += 1
            elif a['lieu_src'] == 'chemin' and not lb:
                lieu_gagne += 1
            elif lb and a['lieu'] and lb != a['lieu']:
                lieu_different[f"{lb} -> {a['lieu']}"] += 1
                if len(exemples_lieux) < 12:
                    exemples_lieux.append({'cle': cle, 'renommage': lb,
                                           'vue': a['lieu']})
            if lb and not a['lieu'] and not lieu_colle_dans_un_mot(cle, lb) \
                    and len(exemples_rates) < 8:
                exemples_rates.append({'cle': cle, 'renommage': lb})
        pb, ab = tagging_meta.noms_depuis_kw(names_from_entry(e))
        if set(pb) - set(a['persons']) or set(ab) - set(a['animals']):
            noms_retires += 1
        if set(a['persons']) - set(pb) or set(a['animals']) - set(ab):
            noms_ajoutes += 1

        # — écart avec le champ ÉCRIT —
        anciens = e.get('faits')
        if anciens:
            ecrites += 1
            if signature(anciens) == signature(F):
                identiques += 1
            else:
                differentes += 1
                perdus = signature(anciens) - signature(F)
                if perdus and all(t in ('personne', 'animal') for t, _ in perdus):
                    resolues_par_l_autorite += 1
                if len(exemples_ecarts) < exemples:
                    exemples_ecarts.append({'cle': cle, 'ecrit': anciens,
                                            'vue': F})
    t_vue = time.perf_counter() - t1

    # — COÛT : une PAGE de 50, index inversé déjà en mémoire —
    page = [c for c, _ in entrees[:50]]
    entrees_par_cle = dict(entrees)
    t2 = time.perf_counter()
    for _ in range(20):
        for cle in page:
            e = lire_json(entrees_par_cle[cle])
            faits_vue.faits(cle, e, especes=esp.get(cle), gps_place=gps.get(cle),
                            lieux=lieux, racines=racines,
                            noms_attendus=noms_attendus(cle, e, attribues, exclus))
    t_page = (time.perf_counter() - t2) / 20

    # — COÛT : la version NAÏVE des noms (balayage des fiches à chaque photo),
    #   c'est-à-dire `server._noms_attendus` tel qu'il est écrit aujourd'hui —
    fiches_brutes = []
    for table, prefixe in (('people', 'personne'), ('pets', 'animal')):
        try:
            for _k, v in cx.execute(f'SELECT k, v FROM "{table}"'):
                e = lire_json(v)
                if e.get('name'):
                    fiches_brutes.append((f"{prefixe}:{e['name']}",
                                          set(e.get('exclude') or []),
                                          e.get('faces') or []))
        except sqlite3.Error:
            pass

    def noms_naif(cle):
        tags = []
        for tag, exc, faces in fiches_brutes:
            if cle in exc:
                continue
            for kf in faces:
                if isinstance(kf, (list, tuple)) and len(kf) == 2 and kf[0] == cle:
                    tags.append(tag)
                    break
        return tags

    t3 = time.perf_counter()
    for cle in page:
        noms_naif(cle)
    t_page_naif = time.perf_counter() - t3

    couverts = n - par_nb[0]
    return {
        'base': str(base),
        'fuseau': time.strftime('%Z%z'),
        'entrees': n,
        'fiches_nommees': fiches,
        'racines': racines,
        'lieux_connus': len(lieux),
        'couverts_par_la_vue': couverts,
        'muettes': par_nb[0],
        'au_moins_un_fait_non_date': non_date,
        'date_seule': date_seule,
        'matiere': dict(dispo),
        'source_date': dict(src_date),
        'source_lieu': dict(src_lieu),
        'faits_par_entree': {str(k): v for k, v in sorted(par_nb.items())},
        'ecart_backfill': {
            'lieux_colles_evites': sum(lieu_perdu.values()),
            'lieux_colles_detail': dict(lieu_perdu.most_common(8)),
            'lieux_MOT_ENTIER_rates': sum(lieu_rate.values()),
            'lieux_MOT_ENTIER_rates_detail': dict(lieu_rate.most_common(10)),
            'lieux_MOT_ENTIER_rates_pourquoi': dict(lieu_rate_pourquoi.most_common()),
            'lieux_differents': dict(lieu_different.most_common(6)),
            'lieux_que_seule_la_vue_trouve': lieu_gagne,
            'exemples_desaccord': exemples_lieux,
            'exemples_rates': exemples_rates,
            'photos_ou_l_autorite_RETIRE_un_nom': noms_retires,
            'photos_ou_l_autorite_AJOUTE_un_nom': noms_ajoutes,
        },
        'ecart_champ_ecrit': {
            'ecrites': ecrites,
            'identiques': identiques,
            'differentes': differentes,
            'divergences_de_noms_resolues': resolues_par_l_autorite,
            'exemples': exemples_ecarts,
        },
        'cout': {
            'preparation_s': round(t_prep, 3),
            'lecture_index_s': round(t_lect, 3),
            'vue_index_entier_s': round(t_vue, 3),
            'vue_par_photo_us': round(1e6 * t_vue / n, 1) if n else None,
            'page_50_ms': round(1000 * t_page, 2),
            'page_50_noms_NAIFS_ms': round(1000 * t_page_naif, 2),
        },
        'exemples_muettes': muettes,
    }


def pourcent(x, n):
    return f"{(100.0 * x / n):.2f} %" if n else "-"


def rapport(r):
    n = r['entrees']
    L, A = [], None
    A = L.append
    A("=" * 72)
    A("  MESURE — la VUE des `faits` : ce qu'elle rend, ce qu'elle coute")
    A("=" * 72)
    A(f"Base      : {r['base']}")
    A(f"Fuseau    : {r['fuseau']}   (les COMPTES n'en dependent pas)")
    A(f"Entrees   : {n}   fiches nommees : {r['fiches_nommees']}   "
      f"lieux connus : {r['lieux_connus']}")
    A(f"Racines   : {', '.join(r['racines']) or '(aucune)'}")
    A("")
    A("-- CE QUE LA VUE REND " + "-" * 50)
    c = r['couverts_par_la_vue']
    A(f"  au moins un fait          : {c}  ({pourcent(c, n)})")
    A(f"  dont au moins un fait NON-DATE : {r['au_moins_un_fait_non_date']}  "
      f"({pourcent(r['au_moins_un_fait_non_date'], n)})   <- le chiffre honnete")
    A(f"  date SEULE                : {r['date_seule']}  "
      f"({pourcent(r['date_seule'], n)})")
    A(f"  muettes                   : {r['muettes']}")
    A("")
    A("  Matiere par type :")
    for t, v in sorted(r['matiere'].items(), key=lambda x: -x[1]):
        A(f"    {t:10s} {v:6d}  ({pourcent(v, n)})")
    A(f"  Source du lieu : {r['source_lieu']}")
    A(f"  Source de la date : {r['source_date']}")
    A("")
    A("-- ECART AVEC LE BACKFILL QU'ON N'ECRIT PAS " + "-" * 28)
    e = r['ecart_backfill']
    A(f"  lieux COLLES dans un mot, evites : {e['lieux_colles_evites']}")
    for lab, k in e['lieux_colles_detail'].items():
        A(f"      {lab:20s} {k}")
    A(f"  lieux MOT ENTIER que la vue rate quand meme : "
      f"{e['lieux_MOT_ENTIER_rates']}   <- le prix de la regle")
    for lab, k in e['lieux_MOT_ENTIER_rates_detail'].items():
        A(f"      {lab:20s} {k}")
    A("  ... pourquoi :")
    for quoi, k in e['lieux_MOT_ENTIER_rates_pourquoi'].items():
        A(f"      {k:5d}  {quoi}")
    if e['lieux_differents']:
        A("  les deux repondent, mais DIFFEREMMENT (renommage -> vue) :")
        for lab, k in e['lieux_differents'].items():
            A(f"      {lab:34s} {k}")
        for x in e['exemples_desaccord'][:6]:
            A(f"        ex. {x['cle']}")
    for x in e['exemples_rates'][:5]:
        A(f"      rate. {x['renommage']:18s} {x['cle']}")
    A(f"  lieux que seule la regle des segments trouve : "
      f"{e['lieux_que_seule_la_vue_trouve']}")
    A(f"  photos ou l'autorite vivante RETIRE un nom  : "
      f"{e['photos_ou_l_autorite_RETIRE_un_nom']}")
    A(f"  photos ou l'autorite vivante AJOUTE un nom  : "
      f"{e['photos_ou_l_autorite_AJOUTE_un_nom']}")
    A("")
    A("-- ECART AVEC LE CHAMP `faits` DEJA ECRIT " + "-" * 30)
    w = r['ecart_champ_ecrit']
    A(f"  entrees pourvues : {w['ecrites']}   identiques : {w['identiques']}   "
      f"differentes : {w['differentes']}")
    A(f"  dont divergences de NOMS que l'autorite tranche : "
      f"{w['divergences_de_noms_resolues']}")
    A("")
    A("-- COUT " + "-" * 63)
    k = r['cout']
    A(f"  preparation (especes, gps, lieux, autorite) : {k['preparation_s']} s")
    A(f"  lecture de l'index                          : {k['lecture_index_s']} s")
    A(f"  VUE sur l'index ENTIER                      : {k['vue_index_entier_s']} s"
      f"   ({k['vue_par_photo_us']} us/photo)")
    A(f"  VUE sur une PAGE de 50                      : {k['page_50_ms']} ms")
    A(f"  ... dont noms par balayage NAIF des fiches  : "
      f"{k['page_50_noms_NAIFS_ms']} ms   (ce que fait server._noms_attendus)")
    A("=" * 72)
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
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                                encoding='utf-8')
        print(f"\nJSON : {a.json}")


if __name__ == '__main__':
    main()
