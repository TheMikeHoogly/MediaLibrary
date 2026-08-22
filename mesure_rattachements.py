#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — un rattachement désigne-t-il encore LE BON VISAGE ?
──────────────────────────────────────────────────────────────────────────────

D'OÙ VIENT LA QUESTION

Le 22/08, en jugeant la tranche 0,35–0,40, Mike a vu une planche de « visages
déjà confirmés de Didier » contenant Laura Waller, et une planche de Mathieu
contenant Mathilde. Deux sur deux : ce n'est pas une erreur humaine dispersée.

Un rattachement est un couple `[photo, index du visage]`. L'index désigne une
POSITION dans `FACE_STORE[photo]['faces']` — une liste que le ré-embedding
REMPLACE (`e['faces'] = newfaces`, `reembed_one_batch`). Ordre et nombre
changent. Le couple survit, sa cible non : sur une photo de couple, l'index de
Didier finit par désigner Laura, qui est sur la même photo. Le code CONNAÎT le
danger — le commentaire de `reembed_one_batch` le nomme, et un garde-fou
(`assigned_keys`) saute désormais les photos attribuées. Mais un garde-fou
protège l'AVENIR ; il ne répare pas ce qui a été ré-embarqué avant lui. Et il
ne lit que `PEOPLE_STORE` : `PETS_STORE` n'y est pas.

Ce banc ne suppose rien de tout cela. Il MESURE.

CE QU'IL COMPTE, ET POURQUOI C'EST DÉCISIF

  A. **Hors bornes** — `i >= len(faces)`. `_serve_facecrop` retombe alors sur
     le visage 0 EN SILENCE (« index périmé → visage principal ») : la planche
     montre quelqu'un d'autre sans jamais le dire.
  B. **Le score du visage désigné** contre la signature de la personne. Un
     couple juste est proche ; un couple décalé est loin. La distribution vaut
     mieux que deux exemples — leçon du 20/08.
  C. **Le décalage, et c'est LA preuve** : un AUTRE visage de la MÊME photo
     ressemble-t-il nettement plus à la personne ? Si oui, le couple ne
     désigne pas le bon visage, et il désigne quelqu'un qui est sur la photo —
     exactement ce que Mike a vu. Un score bas tout seul ne distingue pas
     « index décalé » de « photo difficile » ; le meilleur voisin DANS la même
     photo, si.
  D. **La cause présumée, croisée** : les couples décalés sont-ils concentrés
     sur les photos RÉELLEMENT re-détectées ? Le marqueur n'est pas `reemb` —
     mesuré le 22/08, **100 % du fonds le porte**, parce qu'il est aussi posé
     sur les photos seulement EXAMINÉES (« rien à améliorer → on marque »).
     Un drapeau que tout le monde porte ne croise rien : c'était un instrument
     mort, et son 100 % l'a dit. `reemb_ms` n'est écrit que dans la branche qui
     appelle vraiment `detect_faces` — c'est lui qui discrimine.
  E. **Ce que la planche MONTRE**, poste par poste. La page `/tranche` affiche
     l'avatar puis les premiers couples de la fiche : si le décalage se
     concentre sur ces postes-là, la planche est trompeuse même quand le fonds
     va bien. C'est la question que posent les deux captures du 22/08.

CE QUE LE CHIFFRE NE PEUT PAS DIRE, ET IL FAUT LE SAVOIR

La signature (`refs`) est faite d'empreintes ajoutées lors des confirmations
humaines. Si un visage FAUX a été confirmé, son empreinte pollue la signature
et rend son propre couple « juste ». Le banc mesure donc une BORNE BASSE du
décalage : il en trouve au moins tant, jamais moins.

Aucune écriture : ni base, ni tag, ni fichier. Lecture seule sur COPIE.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_copie_base.py
    python mesure_rattachements.py --base copie.db
    python mesure_rattachements.py --base copie.db --ecart 0.05 --exemples 20
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import mesure_propagation_noms as M
import recale_rattachements as recale

# Un autre visage de la même photo doit dépasser le désigné d'AU MOINS ça pour
# qu'on parle de décalage. Deux visages proches (frère et sœur, même personne
# détectée deux fois) ne doivent pas compter comme une erreur.
ECART_DEFAUT = 0.10


def _fiches(store):
    """(nom, prototypes, couples) des fiches pourvues d'une signature."""
    from classifier import prototypes
    out, sans = [], 0
    for pk, pe in store.data.items():
        if not isinstance(pe, dict):
            continue
        nom = pe.get('name', pk)
        couples = [(kf[0], int(kf[1] or 0)) for kf in (pe.get('faces') or [])
                   if isinstance(kf, (list, tuple)) and len(kf) == 2]
        if not couples:
            continue
        vs = []
        for s in (pe.get('refs') or []):
            try:
                vs.append(M.emb_de_b64(s))
            except Exception:                                  # noqa: BLE001
                pass
        P = prototypes(vs) if vs else None
        if P is None or not len(P):
            sans += 1
            continue
        out.append((nom, P, couples, pe))
    return out, sans


def mesurer(base, projet, ecart, exemples):
    tags, faces, people = M.ouvrir_stores(base)
    try:
        return _mesurer(faces, people, projet, ecart, exemples)
    finally:
        for st in (tags, faces, people):
            try:
                st.cx.close()
            except Exception:                                  # noqa: BLE001
                pass


def _mesurer(faces, people, projet, ecart, exemples):
    import numpy as np
    seuils, _surcharges = M.seuils_de_server(projet)
    fp_sim = float(seuils['CUR_FP_SIM'])

    fiches, sans_signature = _fiches(people)
    if not fiches:
        raise SystemExit("Aucune fiche pourvue d'une signature ET d'un "
                         "rattachement : rien à vérifier.")

    # Les visages d'une photo, décodés une seule fois — plusieurs fiches
    # peuvent désigner la même photo.
    cache = {}

    def visages_de(cle):
        if cle not in cache:
            e = faces.data.get(cle)
            liste, reemb = [], None
            if isinstance(e, dict):
                # `reemb` seul ne discrimine pas (100 % du fonds le porte) :
                # c'est `reemb_ms` qui marque une re-detection REELLE.
                reemb = e.get('reemb_ms') is not None
                for f in (e.get('faces') or []):
                    v = None
                    if isinstance(f, dict) and f.get('emb'):
                        try:
                            v = M.emb_de_b64(f['emb'])
                        except Exception:                      # noqa: BLE001
                            v = None
                    liste.append(v)
            cache[cle] = (liste, reemb, isinstance(e, dict))
        return cache[cle]

    c = Counter()
    scores, decales, exemples_hb = [], [], []
    # D : le croisement avec la cause presumee.
    croise = Counter()
    # E : le verdict par POSTE dans la liste de la fiche. La planche montre les
    # premiers : un decalage concentre la rend trompeuse meme si le fonds va bien.
    postes = {}

    def poste(n, verdict):
        cle_p = '0' if n == 0 else ('1' if n == 1 else ('2' if n == 2 else '3+'))
        postes.setdefault(cle_p, Counter())[verdict] += 1

    # Le PLAN de reparation, calcule par la regle de prod elle-meme : le banc
    # ne redit pas ce que `recale_rattachements` decide, il l'appelle. Sinon on
    # mesurerait une reparation qui n'est pas celle qui sera appliquee.
    pris = recale.rattachements_pris(f for _n, _P, _c, f in fiches)
    plan = Counter()
    exemples_plan, exemples_refus = [], []

    for nom, P, couples, pe in fiches:
        scores_fiche = {}
        for rang, (cle, i) in enumerate(couples):
            c['couples'] += 1
            liste, reemb, presente = visages_de(cle)
            if not presente:
                c['photo_sans_fiche_de_visages'] += 1
                poste(rang, 'sans_matiere')
                continue
            if not liste:
                c['photo_sans_visage'] += 1
                poste(rang, 'sans_matiere')
                continue
            if i >= len(liste) or i < 0:
                if cle not in scores_fiche:
                    scores_fiche[cle] = [
                        float(np.max(P @ v)) if v is not None else None
                        for v in liste]
                c['index_hors_bornes'] += 1
                if len(exemples_hb) < exemples:
                    exemples_hb.append({"person": nom, "key": cle, "i": i,
                                        "visages": len(liste), "reemb": reemb})
                croise['hors_bornes_reemb' if reemb else 'hors_bornes_sans_reemb'] += 1
                poste(rang, 'hors_bornes')
                continue
            # Score de CHAQUE visage de la photo contre la signature.
            par_visage = scores_fiche.get(cle)
            if par_visage is None:
                par_visage = [float(np.max(P @ v)) if v is not None else None
                              for v in liste]
                scores_fiche[cle] = par_visage
            s_i = par_visage[i]
            if s_i is None:
                c['visage_designe_sans_vecteur'] += 1
                poste(rang, 'sans_matiere')
                continue
            c['mesurables'] += 1
            scores.append(s_i)
            if s_i < fp_sim:
                c['sous_le_seuil_de_faux_positif'] += 1
            # C : un autre visage de la MÊME photo fait-il nettement mieux ?
            autres = [(s, j) for j, s in enumerate(par_visage)
                      if s is not None and j != i]
            if not autres:
                c['seul_visage_de_la_photo'] += 1
                croise['un_seul_visage'] += 1
                poste(rang, 'faux' if s_i < fp_sim else 'juste')
                continue
            s_best, j_best = max(autres)
            if s_best - s_i >= ecart:
                c['decale'] += 1
                croise['decale_reemb' if reemb else 'decale_sans_reemb'] += 1
                poste(rang, 'decale')
                if len(decales) < exemples:
                    decales.append({"person": nom, "key": cle, "i": i,
                                    "sim": round(s_i, 3), "mieux": j_best,
                                    "sim_mieux": round(s_best, 3),
                                    "visages": len(liste), "reemb": reemb})
            else:
                c['designe_le_meilleur_ou_presque'] += 1
                croise['juste_reemb' if reemb else 'juste_sans_reemb'] += 1
                poste(rang, 'juste')

        _champs, recalages, refus = recale.recaler_fiche(
            pe, scores_fiche, ecart=ecart, deja_pris=pris)
        for r in recalages:
            plan['recale_hors_bornes' if r.get('hors_bornes') else 'recale'] += 1
            if r.get('fusion'):
                plan['dont_fusion'] += 1
            if len(exemples_plan) < exemples:
                exemples_plan.append(dict(r, person=nom))
        for r in refus:
            plan['refus_' + r['pourquoi']] += 1
            if len(exemples_refus) < exemples:
                exemples_refus.append(dict(r, person=nom))

    rap = {"seuils": {"CUR_FP_SIM": fp_sim, "ecart": ecart},
           "fiches": {"avec_signature_et_couples": len(fiches),
                      "avec_couples_sans_signature": sans_signature},
           "comptes": dict(c), "croisement_reemb": dict(croise),
           "par_poste": {k: dict(v) for k, v in sorted(postes.items())},
           "exemples_decales": decales, "exemples_hors_bornes": exemples_hb,
           "plan": dict(plan), "exemples_plan": exemples_plan,
           "exemples_refus": exemples_refus}
    if scores:
        a = np.asarray(scores, dtype=np.float32)
        rap["scores"] = {"n": len(scores),
                         "median": round(float(np.median(a)), 3),
                         "p10": round(float(np.percentile(a, 10)), 3),
                         "p90": round(float(np.percentile(a, 90)), 3),
                         "min": round(float(a.min()), 3)}
    # Les photos ré-embarquées, dans l'absolu : sans ce dénominateur, un
    # « 80 % des décalés sont reemb » ne veut rien dire si 80 % du fonds l'est.
    tot = sum(1 for e in faces.data.values() if isinstance(e, dict))
    rap["fonds"] = {"photos_a_visages": tot,
                    "dont_marquees_reemb": sum(
                        1 for e in faces.data.values()
                        if isinstance(e, dict) and e.get('reemb')),
                    "dont_reembarquees": sum(
                        1 for e in faces.data.values()
                        if isinstance(e, dict) and e.get('reemb_ms') is not None)}
    return rap


def part(a, b):
    return f"{100.0 * a / b:.1f} %" if b else "—"


def afficher(r):
    c = r["comptes"]
    n = c.get('couples', 0)
    L = ["=" * 78,
         "RATTACHEMENTS — le couple [photo, visage] designe-t-il le bon visage ?",
         "=" * 78,
         f"Fiches avec signature ET rattachements : {r['fiches']['avec_signature_et_couples']}"
         f"  (sans signature : {r['fiches']['avec_couples_sans_signature']})",
         f"Couples examines : {n}", ""]
    for cle in ('mesurables', 'index_hors_bornes', 'photo_sans_fiche_de_visages',
                'photo_sans_visage', 'visage_designe_sans_vecteur'):
        if c.get(cle):
            L.append(f"    {cle:<32} {c[cle]:>7}   {part(c[cle], n)}")
    m = c.get('mesurables', 0)
    L.append("")
    L.append("Sur les couples mesurables :")
    for cle in ('designe_le_meilleur_ou_presque', 'decale',
                'seul_visage_de_la_photo', 'sous_le_seuil_de_faux_positif'):
        if c.get(cle):
            L.append(f"    {cle:<32} {c[cle]:>7}   {part(c[cle], m)}")
    s = r.get("scores")
    if s:
        L.append("")
        L.append(f"Score du visage designe : median {s['median']}  "
                 f"p10 {s['p10']}  p90 {s['p90']}  min {s['min']}")
    pp = r.get("par_poste") or {}
    if pp:
        L.append("")
        L.append("Par POSTE dans la fiche — c'est ce que la planche montre :")
        L.append("    poste     juste   decale   faux  hors_b  sans_mat   part decalee")
        for k in ('0', '1', '2', '3+'):
            v = pp.get(k)
            if not v:
                continue
            tot_p = sum(v.values())
            L.append(f"    {k:<8} {v.get('juste', 0):>6} {v.get('decale', 0):>8} "
                     f"{v.get('faux', 0):>6} {v.get('hors_bornes', 0):>7} "
                     f"{v.get('sans_matiere', 0):>9}   {part(v.get('decale', 0), tot_p)}")
        L.append("    Si le poste 0 se distingue, la planche trompe meme quand le")
        L.append("    fonds va bien — et c'est la planche qu'il faut corriger.")
    L.append("")
    L.append("Croisement avec la cause presumee (photo REELLEMENT re-detectee) :")
    cr = r["croisement_reemb"]
    f = r["fonds"]
    L.append(f"    fonds : {f['dont_reembarquees']} photos re-detectees sur "
             f"{f['photos_a_visages']}  ({part(f['dont_reembarquees'], f['photos_a_visages'])})")
    L.append(f"            {f.get('dont_marquees_reemb', 0)} portent le drapeau "
             f"`reemb` — un drapeau que tout le monde porte ne croise rien.")
    for cle in ('decale_reemb', 'decale_sans_reemb', 'juste_reemb',
                'juste_sans_reemb', 'hors_bornes_reemb', 'hors_bornes_sans_reemb'):
        if cr.get(cle):
            L.append(f"    {cle:<26} {cr[cle]:>7}")
    dr, ds = cr.get('decale_reemb', 0), cr.get('decale_sans_reemb', 0)
    jr, js = cr.get('juste_reemb', 0), cr.get('juste_sans_reemb', 0)
    if (dr + jr) and (ds + js):
        L.append("")
        L.append(f"    taux de decalage SUR les photos re-embarquees   : "
                 f"{part(dr, dr + jr)}")
        L.append(f"    taux de decalage sur les AUTRES                 : "
                 f"{part(ds, ds + js)}")
        L.append("    Si le premier ecrase le second, le re-embedding est nomme")
        L.append("    par le chiffre. Sinon l'hypothese tombe, et c'est le but.")
    if r["exemples_hors_bornes"]:
        L.append("")
        L.append("Hors bornes (la planche montre le visage 0 SANS le dire) :")
        for e in r["exemples_hors_bornes"]:
            L.append(f"    {e['person'][:18]:<18} i={e['i']} sur {e['visages']} "
                     f"visage(s)  reemb={e['reemb']}  {Path(e['key']).name[:34]}")
    if r["exemples_decales"]:
        L.append("")
        L.append("Decales (un autre visage de la MEME photo ressemble plus) :")
        for e in r["exemples_decales"]:
            L.append(f"    {e['person'][:18]:<18} i={e['i']} ({e['sim']}) -> "
                     f"i={e['mieux']} ({e['sim_mieux']}) sur {e['visages']} "
                     f"visage(s)  reemb={e['reemb']}  {Path(e['key']).name[:30]}")
    pl = r.get("plan") or {}
    L.append("")
    L.append("CE QUE LA REPARATION FERAIT (regle de prod, appelee telle quelle) :")
    if not pl:
        L.append("    rien a recaler")
    for cle in sorted(pl):
        L.append(f"    {cle:<32} {pl[cle]:>7}")
    for e in (r.get("exemples_plan") or []):
        L.append(f"    recale : {e['person'][:16]:<16} i={e['de']} -> i={e['vers']}"
                 f"  ({e['sim']} -> {e['sim_vers']})  {Path(e['key']).name[:30]}")
    for e in (r.get("exemples_refus") or []):
        L.append(f"    refus  : {e['person'][:16]:<16} i={e['i']}  "
                 f"{e['pourquoi']}  {Path(e['key']).name[:30]}")
    L.append("")
    L.append("BORNE BASSE : une empreinte faussement confirmee est entree dans la")
    L.append("signature et rend son propre couple « juste ». Il y en a au moins")
    L.append("tant, jamais moins.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', required=True, help="COPIE de photos.db")
    ap.add_argument('--projet', default='.')
    ap.add_argument('--ecart', type=float, default=ECART_DEFAUT)
    ap.add_argument('--exemples', type=int, default=12)
    ap.add_argument('--json', dest='sortie_json')
    a = ap.parse_args(argv)
    rap = mesurer(a.base, a.projet, a.ecart, a.exemples)
    print(afficher(rap))
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
