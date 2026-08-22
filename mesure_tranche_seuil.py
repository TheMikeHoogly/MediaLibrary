#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — ce que vaut une TRANCHE de score, jugée par un humain
──────────────────────────────────────────────────────────────────────────────

LA QUESTION, ET POURQUOI ELLE NE SE RÉPOND PAS SANS MIKE

`CUR_ADD_SIM = 0.40` : sous ce score, une proposition de rattachement n'est ni
faite ni montrée. `mesure_propagation_noms.py` a compté le réservoir qui dort
là-dessous — 28 684 visages, meilleur voisin médian 0,21 — et sa conclusion
était NÉGATIVE : ce ne sont pas des noms qui attendent un seuil, ce sont des
gens sans fiche. Mais la tranche du HAUT, 0,35–0,40, est un autre cas : 1 328
visages assez proches d'une signature pour qu'on ne puisse pas les écarter
d'un chiffre. Choix de Mike (21/08) : **juger 30 propositions de cette tranche
avant de toucher au seuil.** Sans ce jugement, abaisser `CUR_ADD_SIM` est un
pari sur des noms — et un nom faux se propage.

Ce banc ne juge rien. Il TIRE l'échantillon, et plus tard il COMPTE le verdict.

LA RÈGLE VIENT DE LA PROD — ET D'UNE SEULE IMPLÉMENTATION

Tout ce qui décide est importé de `mesure_propagation_noms` : les seuils lus
dans `server.py` (analyse syntaxique, jamais `import server`), les stores
ouverts par le loader de prod, les facettes de `classifier.prototypes`, les
écarts de visages (`pas_visage`, `inconnu`, sans vecteur), la notation
(`noter_visages`). Ce banc n'a pas de règle à lui : il a des BORNES.

Les mêmes écarts humains que `build_suggestions` sont appliqués avant de
retenir une proposition : le nom déjà posé sur la photo (`deja_dit`), la clé
exclue à la main pour cette personne (`exclude`), et un seul candidat par
couple (nom, photo).

POURQUOI UN TIRAGE UNIFORME, ET PAS LES 30 MEILLEURS

Prendre les 30 meilleurs scores de la tranche mesurerait le haut de la
tranche et conclurait sur la tranche entière — l'erreur exacte du 20/08, où
deux échantillons choisis ont porté une conclusion que le banc complet a
réfutée. Le tirage est donc UNIFORME sur les candidates, graine fixe, après
tri déterministe : deux exécutions rendent le même échantillon, et l'échantillon
ne flatte pas la tranche.

LE GARDE-FOU DES CLÉS FANTÔMES, ET POURQUOI IL EST ICI

`build_suggestions` écarte une proposition dont le fichier ne se résout pas.
Sans ce filtre, on ferait juger des photos qui n'existent plus : la vignette
manquerait, et le jugement porterait sur du vide. Ce banc tourne chez Mike
(`banc_agent.py`), il a donc le NAS : un `stat` par clé candidate, et le
rapport DIT combien de fantômes il a écartés. Si la racine n'est pas joignable,
le filtre est SUSPENDU et le rapport le dit aussi — un NAS débranché ferait
passer tout le corpus pour disparu (leçon de `verifier_orphelins`).

CE QUE CE BANC NE FAIT PAS

Aucune écriture dans la base, aucun tag, aucun nom. Il produit un fichier de
travail (`_tranche_a_juger.json`) que la page `/tranche` du serveur donne à
juger. Le verdict, lui, revient ici par `--bilan`.

LE TAUX SE DIT AVEC SA MARGE

30 tirages, ce n'est pas un pourcentage : c'est un intervalle. `--bilan` rend
le score de Wilson à 95 %, parce qu'un « 80 % » nu sur 30 jugements couvre en
réalité de 63 % à 90 % — et la décision sur un seuil n'est pas la même aux deux
bouts.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_copie_base.py
    python mesure_tranche_seuil.py --base copie.db
    python mesure_tranche_seuil.py --base copie.db --min 0.30 --max 0.35 --n 30
    python mesure_tranche_seuil.py --bilan _tranche_jugements.json
"""

import argparse
import json
import math
import os
import random
import sys
from collections import Counter
from pathlib import Path

import mesure_propagation_noms as M

SORTIE_DEFAUT = '_tranche_a_juger.json'
JUGEMENTS_DEFAUT = '_tranche_jugements.json'
GRAINE_DEFAUT = 20260822
# Verdicts admis. « indecidable » n'est pas un échec du modèle : c'est un
# visage qu'un humain ne tranche pas, et le compter comme faux mentirait.
VERDICTS = ('juste', 'faux', 'indecidable')
REFS_MAX = 3        # visages de référence montrés à côté de la proposition


# ────────────────────────────── le tirage ───────────────────────────────────

def candidates(base, projet, smin, smax, fichiers=True):
    """Les propositions dont le meilleur score tombe dans [smin, smax[.

    Renvoie (liste triée, rapport). Chaque candidate porte de quoi la juger :
    le visage, le nom proposé, le score, la marge et le RIVAL — sans le rival,
    un humain ne peut pas savoir pourquoi la machine hésite.
    """
    import numpy as np
    tags, faces, people = M.ouvrir_stores(base)
    try:
        return _candidates(tags, faces, people, projet, smin, smax, fichiers, np)
    finally:
        for st in (tags, faces, people):
            try:
                st.cx.close()
            except Exception:                                  # noqa: BLE001
                pass


def _candidates(tags, faces, people, projet, smin, smax, fichiers, np):
    seuils, surcharges = M.seuils_de_server(projet)

    personnes, sans_signature = M.charger_personnes(people)
    if not personnes:
        raise SystemExit("Aucune fiche personne pourvue d'une signature : "
                         "rien à proposer.")
    Cproto, offsets, personnes = M.matrice_facettes(personnes)
    noms = [p["name"] for p in personnes]
    exclus = [p["exclude"] for p in personnes]
    refs_visages = _refs_par_personne(people, noms)

    retenus, ecartes = M.visages_utiles(faces)
    if not retenus:
        raise SystemExit("Aucun visage examinable dans cette base.")
    ptags = M.tags_personne(tags)

    E = np.stack([v for _k, _i, v in retenus]).astype(np.float32)
    cles = [k for k, _i, _v in retenus]
    idxs = [i for _k, i, _v in retenus]
    best, second, qui, rival = M.noter_visages(E, Cproto, offsets)
    marge = best - second

    sorts = Counter()
    vus, brutes = set(), []
    for n in range(len(cles)):
        k, i, j = cles[n], idxs[n], int(qui[n])
        nm = noms[j]
        b = float(best[n])
        if not (smin <= b < smax):
            sorts['hors_tranche'] += 1
            continue
        if nm in ptags.get(k, ()):
            sorts['deja_dit'] += 1
            continue
        if k in exclus[j]:
            sorts['exclu_par_un_humain'] += 1
            continue
        if (nm, k) in vus:
            sorts['doublon_meme_photo'] += 1
            continue
        vus.add((nm, k))
        sorts['candidate'] += 1
        brutes.append({
            "key": k, "i": i, "person": nm,
            "sim": round(b, 4), "margin": round(float(marge[n]), 4),
            "rival": noms[int(rival[n])] if len(noms) >= 2 else "",
            "rival_sim": round(float(second[n]), 4),
            "refs": refs_visages.get(nm, []),
        })

    # Tri déterministe AVANT le tirage : l'ordre d'un dict ne doit jamais
    # décider de ce qu'un humain va juger.
    brutes.sort(key=lambda c: (c["key"], c["i"], c["person"]))

    rap = {
        "seuils": seuils, "seuils_txt": surcharges,
        "bornes": {"min": smin, "max": smax},
        "matiere": {
            "fiches_avec_signature": len(personnes),
            "fiches_sans_signature": sans_signature,
            "visages_examines": len(retenus),
            "visages_ecartes": dict(ecartes),
            "photos_nommees": len(ptags),
        },
        "sorts": dict(sorts),
    }
    # La tranche mord-elle sur ce que la règle propose déjà ? Le dire, plutôt
    # que de laisser croire qu'on mesure l'invisible alors qu'on mesure la file.
    add_sim = float(seuils['CUR_ADD_SIM'])
    rap["sous_le_seuil_de_prod"] = smax <= add_sim
    rap["cur_add_sim"] = add_sim

    vivantes, rapf = _filtre_fichiers(brutes, projet, fichiers)
    rap["fichiers"] = rapf
    return vivantes, rap


def _refs_par_personne(people, noms):
    """Jusqu'à REFS_MAX visages déjà rattachés, par personne — l'avatar d'abord.

    C'est la matière de la comparaison : juger « est-ce Flo ? » sans voir Flo
    n'est pas juger, c'est deviner.
    """
    out = {}
    voulus = {nm.lower(): nm for nm in noms}
    for pk, pe in people.data.items():
        if not isinstance(pe, dict):
            continue
        nm = voulus.get(str(pe.get('name', pk)).lower())
        if nm is None:
            continue
        vus, liste = set(), []
        av = pe.get('avatar')
        if isinstance(av, (list, tuple)) and len(av) == 2:
            liste.append([av[0], int(av[1] or 0)])
            vus.add((av[0], int(av[1] or 0)))
        for kf in (pe.get('faces') or []):
            if len(liste) >= REFS_MAX:
                break
            if not isinstance(kf, (list, tuple)) or len(kf) != 2:
                continue
            couple = (kf[0], int(kf[1] or 0))
            if couple in vus:
                continue
            vus.add(couple)
            liste.append([couple[0], couple[1]])
        out[nm] = liste
    return out


def _filtre_fichiers(brutes, projet, actif):
    """Écarte les clés fantômes — sauf si la racine n'est pas joignable."""
    rap = {"applique": False, "raison": "desactive (--sans-fichiers)"}
    if not actif:
        return brutes, rap
    up = M.dossier_uploads(projet)
    try:
        racine_ok = Path(up).exists()
    except OSError:
        racine_ok = False
    if not racine_ok:
        rap["raison"] = (f"racine injoignable ({up}) — filtre SUSPENDU, "
                         "un NAS débranché ferait passer tout le corpus pour "
                         "disparu")
        rap["dossier_uploads"] = str(up)
        return brutes, rap
    vivantes, morts, exemples = [], 0, []
    cache = {}
    for c in brutes:
        k = c["key"]
        if k not in cache:
            try:
                cache[k] = M.resoudre(k, up).is_file()
            except OSError:
                cache[k] = False
        if cache[k]:
            vivantes.append(c)
        else:
            morts += 1
            if len(exemples) < 6:
                exemples.append(k)
    rap = {"applique": True, "dossier_uploads": str(up),
           "cles_testees": len(cache), "candidates_vivantes": len(vivantes),
           "candidates_fantomes": morts, "exemples_fantomes": exemples}
    return vivantes, rap


def tirer(vivantes, n, graine):
    """Tirage UNIFORME sans remise. Moins de candidates que demandé : on prend
    tout, et le rapport le dit — un échantillon plus petit reste un échantillon,
    un échantillon silencieusement tronqué est un mensonge."""
    rng = random.Random(graine)
    if n >= len(vivantes):
        return list(vivantes)
    return sorted(rng.sample(vivantes, n),
                  key=lambda c: (c["key"], c["i"], c["person"]))


def preparer(base, projet, smin, smax, n, graine, fichiers=True):
    vivantes, rap = candidates(base, projet, smin, smax, fichiers)
    tires = tirer(vivantes, n, graine)
    rap["tirage"] = {"graine": graine, "demande": n,
                     "reservoir": len(vivantes), "tires": len(tires),
                     "complet": len(tires) >= len(vivantes)}
    rap["items"] = tires
    return rap


# ────────────────────────────── le verdict ──────────────────────────────────

def wilson(succes, total, z=1.96):
    """Intervalle de Wilson à 95 % — l'intervalle des petits effectifs.

    L'intervalle normal (p ± z·√(p(1-p)/n)) déborde de [0, 1] et ment près des
    bords : sur 30 jugements dont 30 justes, il annonce « 100 % ± 0 ». Wilson
    rend (0,88 ; 1,00), ce qui est la vérité : 30 succès ne prouvent pas
    l'infaillibilité.
    """
    if total <= 0:
        return (0.0, 0.0)
    p = succes / total
    d = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / d
    demi = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return (max(0.0, centre - demi), min(1.0, centre + demi))


def bilan(chemin_jugements, chemin_tirage=None):
    """Compte les verdicts posés, et ce qu'ils permettent de dire.

    Le taux est calculé sur les jugements TRANCHÉS (juste + faux) :
    « indécidable » n'est ni un succès ni un échec, mais son POIDS est rendu —
    une tranche à moitié indécidable ne se règle pas par un seuil.
    """
    data = json.loads(Path(chemin_jugements).read_text(encoding='utf-8'))
    verdicts = data.get('verdicts') if isinstance(data, dict) else data
    if not isinstance(verdicts, dict):
        raise SystemExit(f"{chemin_jugements} : pas un fichier de verdicts.")
    c = Counter()
    for v in verdicts.values():
        mot = v.get('verdict') if isinstance(v, dict) else v
        c[mot if mot in VERDICTS else 'inconnu'] += 1
    tranches = c['juste'] + c['faux']
    bas, haut = wilson(c['juste'], tranches)
    rap = {"verdicts": dict(c), "juges": sum(c.values()),
           "tranches": tranches,
           "taux_juste": round(c['juste'] / tranches, 4) if tranches else None,
           "wilson95": [round(bas, 4), round(haut, 4)] if tranches else None}
    if chemin_tirage and Path(chemin_tirage).exists():
        t = json.loads(Path(chemin_tirage).read_text(encoding='utf-8'))
        rap["bornes"] = t.get("bornes")
        rap["tirage"] = t.get("tirage")
        rap["restant"] = max(0, len(t.get("items") or []) - sum(c.values()))
    return rap


# ────────────────────────────── le rapport ──────────────────────────────────

def afficher_tirage(rap):
    L = []
    b = rap["bornes"]
    L.append("=" * 78)
    L.append(f"TRANCHE À JUGER — score dans [{b['min']:.3f} ; {b['max']:.3f}[")
    L.append("=" * 78)
    s = rap["seuils"]
    L.append(f"Seuils de prod : CUR_ADD_SIM={s['CUR_ADD_SIM']} · "
             f"AUTO_ADD_SIM={s['AUTO_ADD_SIM']} · "
             f"AUTO_ADD_MARGIN={s['AUTO_ADD_MARGIN']}"
             + (f" · seuils.txt {rap['seuils_txt']}" if rap['seuils_txt'] else ""))
    if not rap["sous_le_seuil_de_prod"]:
        L.append(f"  ATTENTION : la borne haute ({b['max']}) dépasse "
                 f"CUR_ADD_SIM ({rap['cur_add_sim']}) — cette tranche contient "
                 "des propositions que la règle FAIT DÉJÀ. Ce n'est plus "
                 "l'invisible qu'on mesure.")
    m = rap["matiere"]
    L.append(f"Matière : {m['fiches_avec_signature']} fiches avec signature "
             f"({m['fiches_sans_signature']} sans) · "
             f"{m['visages_examines']} visages examinés")
    L.append("")
    L.append("Sorts des visages :")
    for nom, v in sorted(rap["sorts"].items(), key=lambda kv: -kv[1]):
        L.append(f"    {nom:<24} {v:>8}")
    f = rap["fichiers"]
    L.append("")
    if f.get("applique"):
        L.append(f"Clés fantômes : {f['candidates_fantomes']} candidate(s) "
                 f"écartée(s) sur {f['cles_testees']} clé(s) testée(s) "
                 f"→ {f['candidates_vivantes']} vivante(s)")
        if f.get("exemples_fantomes"):
            for k in f["exemples_fantomes"]:
                L.append(f"    fantôme : {k}")
    else:
        L.append(f"Clés fantômes : filtre NON appliqué — {f.get('raison')}")
    t = rap["tirage"]
    L.append("")
    L.append(f"Tirage : {t['tires']} sur {t['reservoir']} candidate(s), "
             f"graine {t['graine']}"
             + ("  (toutes : le réservoir tient dans l'échantillon)"
                if t["complet"] else "  (uniforme, sans remise)"))
    if t["tires"] < t["demande"]:
        L.append(f"    {t['demande']} demandées, {t['tires']} disponibles — "
                 "l'échantillon est plus petit que prévu, et le taux qui en "
                 "sortira sera d'autant plus large.")
    L.append("")
    L.append("  score  marge  rival            personne         photo")
    for c in rap["items"][:40]:
        L.append(f"  {c['sim']:.3f}  {c['margin']:.3f}  "
                 f"{(c['rival'] or '-')[:15]:<15}  {c['person'][:15]:<15}  "
                 f"{Path(c['key']).name[:34]}")
    if len(rap["items"]) > 40:
        L.append(f"  … {len(rap['items']) - 40} de plus dans le JSON")
    return "\n".join(L)


def afficher_bilan(rap):
    L = ["=" * 78, "BILAN DE LA TRANCHE", "=" * 78]
    if rap.get("bornes"):
        b = rap["bornes"]
        L.append(f"Tranche [{b['min']:.3f} ; {b['max']:.3f}[ · "
                 f"réservoir {rap.get('tirage', {}).get('reservoir', '?')} · "
                 f"tirés {rap.get('tirage', {}).get('tires', '?')}")
    for mot in VERDICTS + ('inconnu',):
        if rap["verdicts"].get(mot):
            L.append(f"    {mot:<14} {rap['verdicts'][mot]:>4}")
    L.append(f"    {'jugés':<14} {rap['juges']:>4}")
    if rap.get("restant"):
        L.append(f"    {'restants':<14} {rap['restant']:>4}")
    L.append("")
    if not rap["tranches"]:
        L.append("Aucun jugement tranché : pas de taux. Un banc sans verdict "
                 "n'est pas un banc.")
        return "\n".join(L)
    bas, haut = rap["wilson95"]
    L.append(f"Taux de propositions JUSTES : {rap['taux_juste'] * 100:.1f} % "
             f"sur {rap['tranches']} tranché(s)")
    L.append(f"Intervalle de Wilson à 95 % : {bas * 100:.1f} % — {haut * 100:.1f} %")
    L.append("")
    L.append("Ce que l'intervalle autorise à dire — et rien de plus :")
    if bas >= 0.90:
        L.append("  La tranche tient même par le bas. Abaisser le seuil de "
                 "PROPOSITION (CUR_ADD_SIM) y gagne des noms.")
    elif bas >= 0.70:
        L.append("  La tranche est bonne, mais pas au point d'être "
                 "automatique : elle a sa place dans la file « À vérifier », "
                 "jamais dans l'auto-ajout.")
    elif haut <= 0.50:
        L.append("  La tranche est mauvaise par le haut : y abaisser un seuil "
                 "poserait plus de faux noms que de justes.")
    else:
        L.append("  L'intervalle enjambe la décision : cet échantillon ne "
                 "tranche pas. Il en faut plus, ou la tranche est hétérogène.")
    ind = rap["verdicts"].get("indecidable", 0)
    if ind and ind >= max(1, rap["juges"] // 4):
        L.append(f"  {ind} indécidable(s) sur {rap['juges']} : un quart de la "
                 "tranche échappe au jugement humain. Un seuil ne réglera pas "
                 "ce que personne ne sait trancher.")
    return "\n".join(L)


# ─────────────────────────────────── cli ────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', help="COPIE de photos.db (mesure_copie_base.py)")
    ap.add_argument('--projet', default='.')
    ap.add_argument('--min', dest='smin', type=float, default=0.35)
    ap.add_argument('--max', dest='smax', type=float, default=0.40)
    ap.add_argument('--n', type=int, default=30)
    ap.add_argument('--graine', type=int, default=GRAINE_DEFAUT)
    ap.add_argument('--sortie', default=SORTIE_DEFAUT)
    ap.add_argument('--sans-fichiers', dest='fichiers', action='store_false',
                    help="ne teste pas l'existence des fichiers (NAS absent)")
    ap.add_argument('--bilan', nargs='?', const=JUGEMENTS_DEFAUT, default=None,
                    help="compte les verdicts au lieu de tirer")
    a = ap.parse_args(argv)

    if a.bilan:
        print(afficher_bilan(bilan(a.bilan, a.sortie)))
        return 0
    if not a.base:
        raise SystemExit("--base est requis pour tirer (ou --bilan pour compter)")
    if not (0.0 <= a.smin < a.smax <= 1.0):
        raise SystemExit(f"bornes absurdes : [{a.smin} ; {a.smax}[")
    rap = preparer(a.base, a.projet, a.smin, a.smax, a.n, a.graine, a.fichiers)
    print(afficher_tirage(rap))
    tmp = Path(a.sortie).with_suffix('.tmp')
    tmp.write_text(json.dumps(rap, ensure_ascii=False, indent=2),
                   encoding='utf-8')
    os.replace(tmp, a.sortie)
    print(f"\nÀ juger : {a.sortie}  →  page /tranche du serveur")
    return 0


if __name__ == '__main__':
    sys.exit(main())
