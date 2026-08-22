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
    python mesure_rattachements.py --base copie.db --residu
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

# Le RÉSIDU : ce que la règle de recalage REFUSE de réparer, et qui ne se
# départage donc qu'à l'œil. `--residu` l'écrit ici, la page `/residu` le
# donne à juger. Le banc PRODUIT la matière, la page COLLECTE, le geste de
# retrait reste humain — même partage que la tranche.
RESIDU_DEFAUT = '_residu_a_juger.json'
RESIDU_JUGEMENTS_DEFAUT = '_residu_jugements.json'


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
    faux_positifs = []
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
    residu = []

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
                # LE vrai defaut : le visage designe ne ressemble a PERSONNE.
                # A distinguer du « decalage », qui n'est qu'un ECART de score
                # — sur une page d'album ou un montage, un ecart separe deux
                # apparitions de la MEME personne, pas deux personnes.
                c['sous_le_seuil_de_faux_positif'] += 1
                if len(faux_positifs) < exemples:
                    faux_positifs.append({"person": nom, "key": cle, "i": i,
                                          "sim": round(s_i, 3),
                                          "visages": len(liste)})
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
        par_photo = {}
        for r in refus:
            plan['refus_' + r['pourquoi']] += 1
            if len(exemples_refus) < exemples:
                exemples_refus.append(dict(r, person=nom))
            if r['pourquoi'] == 'ambigu':
                par_photo.setdefault(r['key'], []).append(int(r['i']))

        # Un cas AMBIGU = une photo que la fiche cite plusieurs fois. Soit la
        # personne y est vraiment detectee deux fois, soit un index egare
        # designe son voisin — le score ne le dit pas, et c'est pour ca que la
        # regle refuse. Un humain le voit d'un coup d'oeil.
        for cle, idx in par_photo.items():
            par_visage = scores_fiche.get(cle) or []
            if not par_visage:
                continue
            liste, _reemb, _presente = visages_de(cle)
            cites = sorted(set(idx))
            candidats = []
            for j in cites:
                sj = par_visage[j] if 0 <= j < len(par_visage) else None
                candidats.append({"i": j, "sim": None if sj is None else round(sj, 3),
                                  "cite": True})
            connus = {cnd['i'] for cnd in candidats}
            autres = [(sj, j) for j, sj in enumerate(par_visage)
                      if sj is not None and j not in connus]
            # Le meilleur visage NON cite n'est montre que s'il est un vrai
            # PRETENDANT : au-dessus du plus faible des couples cites. En
            # dessous, ce n'est pas un candidat, c'est une vignette de plus a
            # regarder — et sur une page de jugement, l'attention est la
            # ressource rare.
            faibles = [d['sim'] for d in candidats if d['sim'] is not None]
            if autres and faibles:
                s_best, j_best = max(autres)
                if s_best > min(faibles):
                    candidats.append({"i": j_best, "sim": round(s_best, 3),
                                      "cite": False})
            residu.append({"person": nom, "key": cle, "visages": len(liste),
                           "pourquoi": "ambigu",
                           "candidats": sorted(candidats, key=lambda d: d['i'])})

    rap = {"seuils": {"CUR_FP_SIM": fp_sim, "ecart": ecart},
           "fiches": {"avec_signature_et_couples": len(fiches),
                      "avec_couples_sans_signature": sans_signature},
           "comptes": dict(c), "croisement_reemb": dict(croise),
           "par_poste": {k: dict(v) for k, v in sorted(postes.items())},
           "exemples_decales": decales, "exemples_hors_bornes": exemples_hb,
           "exemples_faux_positifs": faux_positifs,
           "plan": dict(plan), "exemples_plan": exemples_plan,
           "exemples_refus": exemples_refus,
           "residu": {
               "cas": residu,
               "couples_cites": sum(
                   1 for c_ in residu for d in c_['candidats'] if d['cite']),
               "fiches": len({c_['person'] for c_ in residu}),
               # Nommer ce qui n'est PAS dedans : un refus « deja_pris » est une
               # PERMUTATION entre deux fiches, une autre question (« a qui est
               # ce visage ? ») ; « ecart_insuffisant » et « sous_le_plancher »
               # ne citent pas deux fois la meme photo et ne se tranchent pas de
               # la meme facon. Une population ecartee sans etre nommee devient
               # une conclusion.
               "ecartes": {k[len('refus_'):]: v for k, v in plan.items()
                           if k.startswith('refus_') and k != 'refus_ambigu'},
           }}
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
    if r.get("exemples_faux_positifs"):
        L.append("")
        L.append("SOUS LE SEUIL DE FAUX POSITIF — le visage designe ne ressemble")
        L.append("a personne. C'est le defaut REEL ; le decalage n'est qu'un ecart.")
        for e in r["exemples_faux_positifs"]:
            L.append(f"    {e['person'][:18]:<18} i={e['i']} ({e['sim']}) sur "
                     f"{e['visages']} visage(s)  {Path(e['key']).name[:34]}")
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
    res = r.get("residu") or {}
    if res.get("cas"):
        L.append("")
        L.append("LE RESIDU, A JUGER A L'OEIL (--residu pour l'ecrire) :")
        L.append(f"    {len(res['cas'])} cas sur {res['fiches']} fiche(s), "
                 f"{res['couples_cites']} couples cites")
        L.append("    Un cas = une photo que la fiche cite plusieurs fois. Le")
        L.append("    score ne tranche pas ; un humain, oui.")
        par_fiche = Counter(c_['person'] for c_ in res['cas'])
        for nom, n in par_fiche.most_common():
            L.append(f"      {nom[:22]:<22} {n} cas")
        ec = res.get("ecartes") or {}
        L.append("    ECARTES de ce compte (autres refus, autres questions) : "
                 + (", ".join(f"{k} {v}" for k, v in sorted(ec.items()))
                    if ec else "aucun"))
    L.append("")
    L.append("BORNE BASSE : une empreinte faussement confirmee est entree dans la")
    L.append("signature et rend son propre couple « juste ». Il y en a au moins")
    L.append("tant, jamais moins.")
    return "\n".join(L)


def verifier_recalages(base, projet, dossier=None, exemples=40):
    """Les recalages DEJA APPLIQUES ont-ils repare, ou rebrasse ?

    LA QUESTION, ET POURQUOI ELLE SE POSE APRES COUP

    Le critere qui a designe 42 couples le 22/08 est un ECART de score : un
    autre visage de la meme photo depasse le designe d'au moins 0,10. Ce
    critere ne dit pas que le visage designe etait FAUX — seulement qu'un
    autre faisait mieux. Or un fichier n'est pas toujours une scene : les
    pages d'album photographiees, les montages et les flyers portent la MEME
    personne plusieurs fois, a des endroits differents. La, l'ecart separe
    deux apparitions d'elle, et le « recalage » n'a rien repare : il a deplace
    un couple juste vers un autre couple juste.

    La mesure qui tranche est le score de l'ANCIEN index :

      * sous `CUR_FP_SIM` — l'ancien visage ne ressemblait a personne : le
        recalage a bien REPARE une erreur.
      * au-dessus — les deux visages ressemblent a la personne : c'est un
        REBRASSAGE, sans gain de verite terrain, et le titre « 42
        rattachements designaient le mauvais visage » est a corriger.

    Lecture seule, sur COPIE. Les journaux de quarantaine disent ce qui a
    bouge — c'est le programme qui l'a fait qui les a ecrits.
    """
    import numpy as np
    d = Path(dossier or '_corbeille_recalage')
    journaux = sorted(d.glob('recalage_*.jsonl'))
    if not journaux:
        raise SystemExit(f"Aucun journal de recalage dans {d} : rien a "
                         "verifier. Un recalage non applique n'a rien a dire.")

    def paire(x):
        if isinstance(x, (list, tuple)) and len(x) == 2:
            try:
                return (x[0], int(x[1] or 0))
            except (TypeError, ValueError):
                return None
        return None

    bouges, longueurs = [], 0
    for j in journaux:
        for ligne in j.read_text(encoding='utf-8').splitlines():
            try:
                o = json.loads(ligne)
            except ValueError:
                continue
            if 'fiche' not in o:
                continue
            av = [paire(x) for x in (o.get('avant', {}).get('faces') or [])]
            ap = [paire(x) for x in (o.get('apres', {}).get('faces') or [])]
            if len(av) != len(ap):
                # Une fusion a raccourci la liste : l'appariement position par
                # position ne tient plus, et deviner serait pire que compter.
                longueurs += 1
                continue
            for a, b in zip(av, ap):
                if a and b and a != b:
                    bouges.append({"fiche": o['fiche'], "key": a[0],
                                   "avant": a[1], "apres": b[1]})

    seuils, _s = M.seuils_de_server(projet)
    fp_sim = float(seuils['CUR_FP_SIM'])
    tags, faces, people = M.ouvrir_stores(base)
    try:
        fiches, _sans = _fiches(people)
        par_nom = {str(n).lower(): P for n, P, _c, _pe in fiches}
        c = Counter()
        lignes = []
        for b in bouges:
            P = par_nom.get(str(b['fiche']).lower())
            e = faces.data.get(b['key'])
            liste = (e.get('faces') or []) if isinstance(e, dict) else []
            if P is None or not liste:
                c['sans_matiere'] += 1
                continue
            def score(i):
                if not (0 <= i < len(liste)):
                    return None
                f = liste[i]
                if not (isinstance(f, dict) and f.get('emb')):
                    return None
                try:
                    return float(np.max(P @ M.emb_de_b64(f['emb'])))
                except Exception:                              # noqa: BLE001
                    return None
            s_av, s_ap = score(b['avant']), score(b['apres'])
            if s_av is None or s_ap is None:
                c['sans_matiere'] += 1
                continue
            c['mesurables'] += 1
            reparation = s_av < fp_sim
            c['reparation' if reparation else 'rebrassage'] += 1
            if len(lignes) < exemples:
                lignes.append({"fiche": b['fiche'], "key": b['key'],
                               "avant": b['avant'], "apres": b['apres'],
                               "s_av": round(s_av, 3), "s_ap": round(s_ap, 3),
                               "quoi": 'REPARATION' if reparation else 'rebrassage'})
    finally:
        for st in (tags, faces, people):
            try:
                st.cx.close()
            except Exception:                                  # noqa: BLE001
                pass

    L = ["=" * 78,
         "LES RECALAGES APPLIQUES ONT-ILS REPARE, OU REBRASSE ?",
         "=" * 78,
         f"Journaux lus : {len(journaux)}   couples deplacees : {len(bouges)}"
         f"   mesurables : {c['mesurables']}"]
    if longueurs:
        L.append(f"   ECARTES : {longueurs} fiche(s) dont la liste a change de "
                 "longueur (fusion) — non appariables.")
    if c['sans_matiere']:
        L.append(f"   ECARTES : {c['sans_matiere']} sans signature ou sans "
                 "vecteur.")
    if not c['mesurables']:
        L.append("")
        L.append("Rien de mesurable : pas de conclusion.")
        return "\n".join(L)
    L += ["",
          f"    REPARATION (ancien visage sous {fp_sim:.2f}, un inconnu) "
          f"{c['reparation']:>5}   {part(c['reparation'], c['mesurables'])}",
          f"    rebrassage  (les deux ressemblent a la personne)  "
          f"{c['rebrassage']:>5}   {part(c['rebrassage'], c['mesurables'])}",
          "",
          "Si le rebrassage domine, le critere d'ECART a nomme des apparitions",
          "multiples d'une meme personne (page d'album, montage, flyer) et non",
          "des erreurs : le chiffre publie doit etre corrige, pas le fonds.",
          ""]
    for x in lignes:
        L.append(f"    {x['quoi']:<11} {x['fiche'][:18]:<18} "
                 f"i={x['avant']}({x['s_av']}) -> i={x['apres']}({x['s_ap']})  "
                 f"{Path(x['key']).name[:30]}")
    return "\n".join(L)


def bilan_residu(fichier_cas, fichier_jugements):
    """Ce que les jugements humains AUTORISENT — pas ce qu'on fera.

    Un cas jugé dit, pour une photo et une personne, quels visages SONT elle.
    Trois populations en sortent, et elles ne se mélangent pas :

      * **à retirer** — cité par la fiche, jugé « ce n'est pas elle ». C'est le
        geste que le recalage n'a pas su faire, et il est destructif : il
        supprime une décision humaine périmée, donc quarantaine réversible et
        main de Mike.
      * **confirmé** — cité et jugé « c'est elle ». Rien à faire, et c'est le
        résultat le plus utile : il transforme un rattachement douteux en
        vérité terrain.
      * **à ajouter** — jugé « c'est elle » mais PAS cité. C'est une
        ATTRIBUTION, une autre question et un autre geste ; le compte est
        rendu à part et n'entre dans aucun plan de retrait.

    Aucune écriture. Le banc conclut, il n'agit pas.
    """
    cas = json.loads(Path(fichier_cas).read_text(encoding='utf-8'))['cas']
    try:
        brut = json.loads(Path(fichier_jugements).read_text(encoding='utf-8'))
        verdicts = brut.get('verdicts') or {}
    except (OSError, ValueError):
        verdicts = {}

    c = Counter()
    retraits, ajouts = [], []
    for k in cas:
        ident = f"{k['key']}|{k['person']}"
        v = verdicts.get(ident)
        if not v:
            c['non_juges'] += 1
            continue
        if v.get('verdict') != 'juge':
            c['indecidables'] += 1
            continue
        c['juges'] += 1
        oui = set(int(x) for x in (v.get('oui') or []))
        cites = {int(d['i']) for d in k['candidats'] if d.get('cite')}
        for i in sorted(cites - oui):
            c['a_retirer'] += 1
            retraits.append({"person": k['person'], "key": k['key'], "i": i})
        c['confirmes'] += len(cites & oui)
        for i in sorted(oui - cites):
            c['a_ajouter'] += 1
            ajouts.append({"person": k['person'], "key": k['key'], "i": i})
        if not (cites & oui):
            c['photos_ou_personne_n_est_pas'] += 1

    L = ["=" * 78,
         "BILAN DU RESIDU — ce que le jugement humain autorise",
         "=" * 78,
         f"Cas : {len(cas)}   juges {c['juges']}   "
         f"indecidables {c['indecidables']}   non juges {c['non_juges']}"]
    if not c['juges']:
        L.append("")
        L.append("Aucun cas juge : un bilan sans verdict n'est pas un bilan.")
        L.append("La page /residu est la pour ca.")
        return "\n".join(L)
    L += ["",
          f"    a retirer (cite, juge PAS elle)      {c['a_retirer']:>5}",
          f"    confirme  (cite, juge bien elle)     {c['confirmes']:>5}",
          f"    a AJOUTER (juge elle, NON cite)      {c['a_ajouter']:>5}"
          "   <- attribution, autre geste",
          f"    photos ou aucun visage n'est elle    "
          f"{c['photos_ou_personne_n_est_pas']:>5}",
          "",
          "Le retrait est DESTRUCTIF (il supprime une decision humaine devenue",
          "fausse) : quarantaine reversible et geste de Mike, jamais la sandbox."]
    if retraits:
        L.append("")
        L.append("A retirer :")
        for r in retraits:
            L.append(f"    {r['person'][:20]:<20} i={r['i']:<3} "
                     f"{Path(r['key']).name[:34]}")
    if ajouts:
        L.append("")
        L.append("A ajouter (hors plan de retrait) :")
        for r in ajouts:
            L.append(f"    {r['person'][:20]:<20} i={r['i']:<3} "
                     f"{Path(r['key']).name[:34]}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', help="COPIE de photos.db")
    ap.add_argument('--projet', default='.')
    ap.add_argument('--ecart', type=float, default=ECART_DEFAUT)
    ap.add_argument('--exemples', type=int, default=12)
    ap.add_argument('--json', dest='sortie_json')
    ap.add_argument('--residu', nargs='?', const=RESIDU_DEFAUT, default=None,
                    help="ecrit le residu a juger (defaut : "
                         + RESIDU_DEFAUT + ")")
    ap.add_argument('--bilan-residu', dest='bilan_residu', nargs='?',
                    const=RESIDU_JUGEMENTS_DEFAUT, default=None,
                    help="conclut sur les jugements de la page /residu")
    ap.add_argument('--verifier-recalages', dest='verif', action='store_true',
                    help="les recalages appliques ont-ils repare ou rebrasse ?")
    a = ap.parse_args(argv)
    if a.verif:
        if not a.base:
            ap.error("--base est requis (une COPIE : mesure_copie_base.py)")
        print(verifier_recalages(a.base, a.projet))
        return 0
    if a.bilan_residu:
        print(bilan_residu(a.residu or RESIDU_DEFAUT, a.bilan_residu))
        return 0
    if not a.base:
        ap.error("--base est requis (une COPIE : mesure_copie_base.py)")
    rap = mesurer(a.base, a.projet, a.ecart, a.exemples)
    print(afficher(rap))
    if a.residu:
        r = rap['residu']
        Path(a.residu).write_text(json.dumps(
            {"seuils": rap['seuils'], "cas": r['cas'], "ecartes": r['ecartes']},
            ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"\n{len(r['cas'])} cas ecrits dans {a.residu} "
              f"({r['couples_cites']} couples cites, {r['fiches']} fiche(s)).")
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
