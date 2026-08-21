#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — que propose DÉJÀ la propagation des noms, et où sont les visages muets ?
──────────────────────────────────────────────────────────────────────────────

LA QUESTION, ET POURQUOI C'EST CELLE-LÀ

Le chantier 16 dit : « la médiathèque s'améliore à chaque information humaine ».
Le cas de Mike : une photo porte Florine et Caline ; quand Flora devient
identifiable, sa présence s'ajoute. La tentation est d'écrire un mécanisme.
Or **le mécanisme existe** : `build_suggestions()` cherche en continu « visage
non attribué proche d'une signature », `AUTO_ADD` rattache tout seul au-dessus
de 0,40 avec une marge nette, et `curator_loop()` repasse sur TOUT le fonds
toutes les 240 s. Avant d'ajouter quoi que ce soit, il faut savoir ce que ce
mécanisme rend aujourd'hui — sinon on construit à côté de ce qui tourne déjà.

Ce banc pose donc quatre questions, dans l'ordre où elles décident :

  Q1  Sur les visages sans nom, que ferait la règle MAINTENANT ?
      Quatre sorts, et un seul est un gain : `auto` (rattaché sans validation),
      `file` (carte « À vérifier »), `sous_seuil` (jamais proposé, invisible),
      `deja_dit` (le nom est déjà sur la photo — rien à gagner).
  Q2  La file les MONTRE-t-elle ? Le tri place `remove` puis `merge` AVANT les
      `add`, et le plafond est de 400. Si les retraits saturent la file, aucun
      ajout n'atteint l'écran : le chantier serait dans le plafond, pas dans le
      modèle.
  Q3  Où sont les visages muets ? Distribution du meilleur score, tranche par
      tranche, et ce que chaque seuil candidat gagnerait EN PHOTOS. Un visage
      sous 0,40 n'est pas forcément un raté du seuil : ce peut être quelqu'un
      qui n'a AUCUNE fiche — et une propagation ne propage pas un nom qui
      n'existe pas. Les deux cas se distinguent ici.
  Q4  Le cas de Mike, isolé : les photos qui portent déjà un nom ET gardent un
      visage non couvert. Combien gagneraient un nom NOUVEAU.

Q5 — « repasse-t-il quand une fiche gagne un visage ? » — n'est pas mesurée
ici : elle se lit dans le code (`curator_loop`, recalcul intégral toutes les
240 s, aucun cache par visage) et se VÉRIFIE sur le serveur vivant
(`GET /api/curator/list` : `at`, `count`, la bande `auto`). Un banc ne peut pas
répondre à la place du serveur.

LA RÈGLE VIENT DE LA PROD, PAS D'UN SOUVENIR (`eval/METHODE.md`, 14/08)

  * les VECTEURS sont relus par le loader de prod (`store_sqlite.SqliteStore`),
    qui réinjecte les BLOB exactement comme `server.py` les reçoit ;
  * les FACETTES viennent de `classifier.prototypes` — le même code, donc les
    mêmes prototypes (k-moyennes de graine 0, déterministe) ;
  * les SEUILS sont LUS dans `server.py` (analyse syntaxique, sans import : un
    import ouvrirait `photos.db`, dont le serveur est l'écrivain unique), puis
    `seuils.txt` est appliqué par-dessus, comme le fait la prod. Ils sont
    affichés dans le rapport : un seuil recopié en silence est un banc qui
    dérive.

Ce qui n'est PAS répliqué, et il faut le savoir en lisant les chiffres :

  * le garde-fou « clés fantômes » (`_resolve_key(...).is_file()`) — il ne fait
    qu'ÉCARTER des propositions : les comptes d'ajout sont donc une BORNE
    HAUTE ;
  * l'écriture. Aucun `UPDATE`, aucun accès NAS, aucun modèle chargé.

DEUX MESURES NE DOIVENT JAMAIS PORTER LE MÊME NOM (`eval/METHODE.md`, 21/08)

« Visage sans nom » est ambigu, et l'ambiguïté a déjà coûté une priorité. Ce
banc compte les deux séparément :
  * `visage_non_rattache` : le couple [clé, index] n'apparaît dans les `faces`
    d'aucune fiche — la définition des 1 196 / 71 868 ;
  * `visage_sur_photo_muette` : la photo ne porte AUCUN tag `personne:`.
Le premier est ce dont un ALGORITHME a besoin, le second ce que le PRODUIT
montre. Le chantier 16 parle du second.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_propagation_noms.py --base copie.db
    python mesure_propagation_noms.py --base copie.db --exemples 12 --json r.json
"""

import argparse
import ast
import base64
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Seuils lus dans server.py — noms EXACTS de la prod. Si l'un disparaît, le
# banc s'arrête au lieu de mesurer avec une valeur inventée.
SEUILS_ATTENDUS = ('CUR_ADD_SIM', 'CUR_ADD_STRONG', 'CUR_FP_SIM', 'CUR_FP_STRONG',
                   'CUR_MERGE_SIM', 'CUR_MAX_SUGGEST', 'AUTO_ADD_ENABLE',
                   'AUTO_ADD_SIM', 'AUTO_ADD_MARGIN', 'CURATOR_INTERVAL')
# Seuils que `seuils.txt` peut redéfinir (liste de la prod, server.py).
SEUILS_REGLABLES = ('AUTO_ADD_SIM', 'AUTO_ADD_MARGIN', 'FACE_MATCH_SIM',
                    'CAT_AUTO_SIM', 'CAT_AUTO_MARGIN', 'PET_CLUSTER_SIM',
                    'PET_MATCH_SIM', 'FACE_CLUSTER_SIM')
# Seuils candidats de Q3 : ce qu'un abaissement ouvrirait, en PHOTOS.
CANDIDATS = (0.40, 0.375, 0.35, 0.325, 0.30, 0.25)
TRANCHE = 0.05


# ─────────────────────────── lire la prod sans l'exécuter ───────────────────

def seuils_de_server(projet):
    """Valeurs des seuils du curateur, lues dans le source de `server.py`.

    Analyse syntaxique, jamais `import server` : importer ouvrirait
    `photos.db` en écriture alors que le serveur tourne (règle 4 du projet).
    `seuils.txt` est ensuite appliqué comme le fait la prod.
    """
    src = (Path(projet) / 'server.py').read_text(encoding='utf-8', errors='replace')
    arbre = ast.parse(src)
    vals = {}
    for noeud in arbre.body:
        if not isinstance(noeud, ast.Assign):
            continue
        for cible in noeud.targets:
            if isinstance(cible, ast.Name) and cible.id in SEUILS_ATTENDUS:
                try:
                    vals[cible.id] = ast.literal_eval(noeud.value)
                except ValueError:
                    pass
    manquants = [n for n in SEUILS_ATTENDUS if n not in vals]
    if manquants:
        raise SystemExit("Seuils introuvables dans server.py : "
                         + ', '.join(manquants)
                         + " — la règle a bougé, le banc doit être relu avant "
                           "de produire un chiffre.")
    surcharges = {}
    try:
        brut = (Path(projet) / 'seuils.txt').read_text(encoding='utf-8')
    except OSError:
        brut = ''
    for ligne in brut.splitlines():
        ligne = ligne.split('#')[0].strip()
        if '=' not in ligne:
            continue
        nom, val = (x.strip() for x in ligne.split('=', 1))
        if nom in SEUILS_REGLABLES:
            try:
                vals[nom] = float(val)
                surcharges[nom] = float(val)
            except ValueError:
                pass
    return vals, surcharges


def ouvrir_stores(base):
    """Ouvre la COPIE avec le loader de PROD (vecteurs BLOB réinjectés).

    Refuse `photos.db` : le serveur en est l'écrivain unique.
    """
    p = Path(base)
    if p.name.lower() == 'photos.db':
        raise SystemExit("REFUS : ne jamais mesurer sur photos.db. "
                         "Fabrique la copie (mesure_copie_base.py), "
                         "puis --base copie.db")
    if not p.exists():
        raise SystemExit(f"Base introuvable : {p}")
    from store_sqlite import SqliteStore
    return (SqliteStore(p, 'tags'), SqliteStore(p, 'faces'),
            SqliteStore(p, 'people'))


def dossier_uploads(projet):
    """UPLOAD_DIR, lu comme le fait `server.py` : première ligne utile de
    `dossier_uploads.txt`, sinon le dossier du projet."""
    try:
        for ligne in (Path(projet) / 'dossier_uploads.txt').read_text(
                encoding='utf-8').splitlines():
            ligne = ligne.strip().strip('"')
            if ligne and not ligne.startswith('#'):
                return Path(ligne)
    except OSError:
        pass
    return Path(projet)


def resoudre(cle, upload_dir):
    """Réplique de `server._resolve_key` : clé absolue = elle-même,
    clé relative = sous le dossier des uploads. Deux lignes, sans état."""
    p = Path(cle)
    return p if p.is_absolute() else upload_dir / cle


def emb_de_b64(s):
    """Décode un embedding base64/float16 et le normalise.

    Réplique de `server._emb_from_b64` (trois lignes, sans état). Recopiée et
    non importée pour la même raison que les seuils : importer `server`
    ouvrirait la base de production.
    """
    import numpy as np
    v = np.frombuffer(base64.b64decode(s), dtype=np.float16).astype(np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n else v


# ──────────────────────────────── la matière ────────────────────────────────

def charger_personnes(people):
    """Fiches personnes pourvues d'une signature — miroir de `build_suggestions`.

    Renvoie (personnes, sans_signature). Chaque personne porte ses FACETTES
    (`P`), sa première facette (`c`, ce que la prod appelle son centroïde pour
    la fusion) et ses ensembles de décisions humaines.
    """
    from classifier import prototypes
    personnes, sans_signature = [], 0
    for pk, pe in people.data.items():
        if not isinstance(pe, dict):
            continue
        vs = []
        for s in (pe.get('refs') or []):
            try:
                vs.append(emb_de_b64(s))
            except Exception:                                  # noqa: BLE001
                pass
        P = prototypes(vs) if vs else None
        if P is None or not len(P):
            if pe.get('name'):
                sans_signature += 1
            continue
        personnes.append({"name": pe.get('name', pk), "c": P[0], "P": P,
                          "exclude": set(pe.get('exclude') or []),
                          "confirmed": set(pe.get('confirmed') or []),
                          "nomerge": set(pe.get('nomerge') or []),
                          "refs": len(vs)})
    return personnes, sans_signature


def matrice_facettes(personnes):
    """(Cproto, offsets, gardees) — les facettes empilées, groupées par personne.

    Les lignes d'une même personne sont CONTIGUËS : le maximum par personne se
    calcule alors par `np.maximum.reduceat`, exactement le même maximum que la
    boucle `np.maximum.at` de la prod, sans la boucle.
    """
    import numpy as np
    dim = personnes[0]["P"].shape[1]
    lignes, offsets, gardees = [], [], []
    for p in personnes:
        if p["P"].shape[1] != dim:      # même écart que la prod : on saute
            continue
        offsets.append(len(lignes))
        gardees.append(p)
        for row in p["P"]:
            lignes.append(row)
    return np.stack(lignes), np.asarray(offsets), gardees


def visages_utiles(faces):
    """Visages examinables — mêmes écarts que `build_suggestions`.

    Renvoie (liste de (clé, index, vecteur), comptes des écartés).
    """
    retenus = []
    ecartes = Counter()
    for k, e in faces.data.items():
        if not isinstance(e, dict):
            continue
        if e.get('failed'):
            ecartes['fiche_en_echec'] += 1
            continue
        for i, f in enumerate(e.get('faces') or []):
            if not isinstance(f, dict):
                ecartes['visage_illisible'] += 1
                continue
            if f.get('pas_visage'):
                ecartes['pas_un_visage'] += 1
                continue
            if f.get('inconnu'):
                ecartes['archive_inconnu'] += 1
                continue
            s = f.get('emb')
            if not s:
                ecartes['sans_vecteur'] += 1
                continue
            try:
                retenus.append((k, i, emb_de_b64(s)))
            except Exception:                                  # noqa: BLE001
                ecartes['vecteur_illisible'] += 1
    return retenus, ecartes


def tags_personne(tags):
    """{clé: {nom}} — les `personne:` BRUTS de l'index.

    C'est bien l'index brut qu'il faut lire ici, et non `_autorite_des_noms` :
    `build_suggestions` teste `nm in ptags` sur `kw_fr`, et c'est ce test-là
    qu'on mesure. (L'autorité des noms gouverne l'AFFICHAGE et le FILTRE ;
    le curateur, lui, honore `exclude` par un chemin séparé.)
    """
    out = {}
    for k, se in tags.data.items():
        if not isinstance(se, dict):
            continue
        noms = {kw[9:] for kw in (se.get('kw_fr') or [])
                if isinstance(kw, str) and kw.startswith('personne:')}
        if noms:
            out[k] = noms
    return out


def couples_rattaches(people):
    """{(clé, index)} rattachés par une fiche — la définition des « 1 196 »."""
    out = set()
    for pe in people.data.values():
        if not isinstance(pe, dict) or not pe.get('name'):
            continue
        for kf in (pe.get('faces') or []):
            if isinstance(kf, (list, tuple)) and len(kf) == 2:
                out.add((kf[0], int(kf[1] or 0)))
    return out


# ──────────────────────────────── la mesure ─────────────────────────────────

def mesurer(base, projet, exemples, graine, fichiers=0):
    """Le rapport complet. Ferme la base avant de rendre la main : une
    connexion SQLite laissee ouverte empeche Windows d'effacer le fichier —
    c'est ce qui a fait echouer les tests le 21/08 alors qu'ils passaient
    sous Linux."""
    tags, faces, people = ouvrir_stores(base)
    try:
        return _mesurer(tags, faces, people, projet, exemples, graine, fichiers)
    finally:
        for st in (tags, faces, people):
            try:
                st.cx.close()
            except Exception:                                  # noqa: BLE001
                pass


def _mesurer(tags, faces, people, projet, exemples, graine, fichiers):
    import numpy as np
    seuils, surcharges = seuils_de_server(projet)

    personnes, sans_signature = charger_personnes(people)
    if not personnes:
        raise SystemExit("Aucune fiche personne pourvue d'une signature : "
                         "rien à propager.")
    Cproto, offsets, personnes = matrice_facettes(personnes)
    noms = [p["name"] for p in personnes]
    exclus = [p["exclude"] for p in personnes]

    retenus, ecartes = visages_utiles(faces)
    ptags = tags_personne(tags)
    rattaches = couples_rattaches(people)

    rap = {
        "seuils": seuils, "seuils_txt": surcharges,
        "matiere": {
            "fiches_avec_signature": len(personnes),
            "fiches_sans_signature": sans_signature,
            "facettes": int(Cproto.shape[0]),
            "dimension": int(Cproto.shape[1]),
            "entrees_index": len(tags.data),
            "photos_a_visage": len(faces.data),
            "visages_examines": len(retenus),
            "visages_ecartes": dict(ecartes),
            "photos_nommees": len(ptags),
            "couples_rattaches": len(rattaches),
            # Une fiche de visages dont la clé n'est plus dans l'index : le
            # scan a oublié la photo, le magasin de visages l'a gardée. Elle
            # ne peut plus rien produire — le curateur la repasse quand même.
            "fiches_visages_hors_index": sum(1 for k in faces.data
                                             if k not in tags.data),
        },
    }

    # ── Q1 : le sort de chaque visage, sous la règle d'aujourd'hui ──────────
    E = np.stack([v for _k, _i, v in retenus]).astype(np.float32)
    cles = [k for k, _i, _v in retenus]
    idxs = [i for _k, i, _v in retenus]
    retenus = [(k, i) for k, i, _v in retenus]      # les vecteurs vivent dans E

    best = np.empty(len(retenus), dtype=np.float32)
    second = np.empty(len(retenus), dtype=np.float32)
    qui = np.empty(len(retenus), dtype=np.int32)
    rival = np.empty(len(retenus), dtype=np.int32)
    PAS = 4096
    for d in range(0, len(retenus), PAS):
        B = E[d:d + PAS]
        brut = B @ Cproto.T                                  # (b, facettes)
        sims = np.maximum.reduceat(brut, offsets, axis=1)    # (b, personnes)
        ordre = np.argsort(sims, axis=1)
        j = ordre[:, -1]
        r = ordre[:, -2] if sims.shape[1] >= 2 else j
        lig = np.arange(sims.shape[0])
        best[d:d + PAS] = sims[lig, j]
        second[d:d + PAS] = sims[lig, r] if sims.shape[1] >= 2 else -1.0
        qui[d:d + PAS] = j
        rival[d:d + PAS] = r

    marge = best - second
    add_sim = float(seuils['CUR_ADD_SIM'])
    auto_on = bool(seuils['AUTO_ADD_ENABLE'])
    auto_sim = float(seuils['AUTO_ADD_SIM'])
    auto_marge = float(seuils['AUTO_ADD_MARGIN'])

    sorts = Counter()
    gagnants = defaultdict(set)       # clé → {nom} qu'un ajout poserait
    file_add, file_auto, vus = [], [], set()
    reservoir = []                    # (best, marge, clé, i, nom) sous le seuil
    for n in range(len(retenus)):
        k, i, j = cles[n], idxs[n], int(qui[n])
        nm = noms[j]
        if nm in ptags.get(k, ()):
            sorts['deja_dit'] += 1
            continue
        if k in exclus[j]:
            sorts['exclu_par_un_humain'] += 1
            continue
        b = float(best[n])
        if b < add_sim:
            sorts['sous_seuil'] += 1
            reservoir.append((b, float(marge[n]), k, i, nm))
            continue
        if (nm, k) in vus:
            sorts['doublon_meme_photo'] += 1
            continue
        vus.add((nm, k))
        if auto_on and b >= auto_sim and float(marge[n]) >= auto_marge:
            sorts['auto'] += 1
            gagnants[k].add(nm)
            file_auto.append({"person": nm, "key": k, "i": i, "sim": round(b, 3),
                              "margin": round(float(marge[n]), 3)})
            continue
        sorts['file'] += 1
        gagnants[k].add(nm)
        file_add.append({"person": nm, "key": k, "i": i, "sim": round(b, 3),
                         "margin": round(float(marge[n]), 3),
                         "rival": noms[int(rival[n])],
                         "rival_sim": round(float(second[n]), 3)})

    rap["q1_sorts"] = dict(sorts)
    rap["q1_photos_qui_gagnent_un_nom"] = len(gagnants)
    rap["q1_noms_poses"] = sum(len(v) for v in gagnants.values())

    # ── Le garde-fou des clés fantômes, applique a TOUTES les candidates ────
    # `build_suggestions` ecarte une proposition dont le fichier ne se resout
    # pas. Sans ce filtre, tout ce qui suit compte des photos qui n'existent
    # plus — et le 21/08 a montre que c'est 99,6 % du volume. Un `stat` par
    # cle candidate, une seule fois, puis TOUS les comptes s'y appuient.
    vivantes = None
    if fichiers:
        up = dossier_uploads(projet)
        a_tester = list(set(gagnants) | {k for _b, _m, k, _i, _nm in reservoir})
        a_tester.sort()
        if fichiers < len(a_tester):
            a_tester = a_tester[:fichiers]
        vivantes = set()
        morts = 0
        for k in a_tester:
            try:
                if resoudre(k, up).is_file():
                    vivantes.add(k)
                else:
                    morts += 1
            except OSError:
                morts += 1
        rap["fichiers"] = {
            "dossier_uploads": str(up),
            "cles_candidates_testees": len(a_tester),
            "fichier_present": len(vivantes),
            "cle_fantome": morts,
            "fantomes_dans_l_index": sum(
                1 for k in a_tester if k not in vivantes and k in tags.data),
            "exemples_fantomes": [k for k in a_tester if k not in vivantes][:6],
        }
        gagnants_vivants = {k: v for k, v in gagnants.items() if k in vivantes}
        rap["q1_photos_qui_gagnent_un_nom_REELLES"] = len(gagnants_vivants)
        rap["q1_noms_poses_REELS"] = sum(len(v) for v in gagnants_vivants.values())
        rap["q1_auto_reels"] = sum(1 for e in file_auto if e["key"] in vivantes)
        rap["q1_file_reels"] = sum(1 for e in file_add if e["key"] in vivantes)

    # ── Q2 : la file les montre-t-elle ? ────────────────────────────────────
    fp_sim = float(seuils['CUR_FP_SIM'])
    merge_sim = float(seuils['CUR_MERGE_SIM'])
    pidx = {nm: n for n, nm in enumerate(noms)}
    fvecs_par_cle = defaultdict(list)
    for n in range(len(retenus)):
        fvecs_par_cle[cles[n]].append((idxs[n], E[n]))

    removes, soignes = 0, 0
    rm_vus = set()
    for k, nms in ptags.items():
        fv = fvecs_par_cle.get(k)
        if not fv:
            continue
        for nm in nms:
            j = pidx.get(nm)
            if j is None:
                continue
            p = personnes[j]
            if k in p["confirmed"]:
                continue
            if k in p["exclude"]:
                soignes += 1          # tag erroné que la prod re-retire
                continue
            meilleur = max(float(np.max(p["P"] @ v)) for _i, v in fv)
            if meilleur < fp_sim and (nm, k) not in rm_vus:
                rm_vus.add((nm, k))
                removes += 1

    merges = 0
    C = np.stack([p["c"] for p in personnes])
    S = C @ C.T
    for a in range(len(personnes)):
        for b in range(a + 1, len(personnes)):
            if noms[b] in personnes[a]["nomerge"]:
                continue
            if float(S[a, b]) >= merge_sim:
                merges += 1

    plafond = int(seuils['CUR_MAX_SUGGEST'])
    adds = len(file_add)
    place = max(0, plafond - removes - merges)
    rap["q2_file"] = {
        "remove": removes, "merge": merges, "add": adds,
        "faux_positifs_re_retires": soignes,
        "plafond": plafond,
        "add_visibles": min(adds, place),
        "add_caches_par_le_plafond": max(0, adds - place),
    }

    # ── Q3 : le réservoir sous le seuil ─────────────────────────────────────
    hist = Counter()
    for b, _m, _k, _i, _nm in reservoir:
        hist[round((b // TRANCHE) * TRANCHE, 3)] += 1
    rap["q3_tranches_sous_seuil"] = dict(sorted(hist.items(), reverse=True))

    par_seuil = {}
    for seuil in CANDIDATS:
        photos, serres = set(), 0
        for b, m, k, _i, _nm in reservoir:
            if b < seuil or (vivantes is not None and k not in vivantes):
                continue
            photos.add(k)
            if m < auto_marge:
                serres += 1
        # au seuil actuel, ce que la règle rend déjà s'ajoute
        for k in gagnants:
            if vivantes is None or k in vivantes:
                photos.add(k)
        par_seuil[f"{seuil:.3f}"] = {"photos_gagnees": len(photos),
                                     "dont_marge_serree": serres}
    rap["q3_par_seuil"] = par_seuil
    rap["q3_sur_cles_vivantes"] = vivantes is not None

    # Un visage muet : sous le seuil parce que le seuil est trop haut, ou parce
    # que personne ne lui ressemble ? Le score du meilleur voisin le dit.
    if reservoir:
        b_res = np.asarray([b for b, _m, _k, _i, _nm in reservoir], dtype=np.float32)
        rap["q3_reservoir"] = {
            "visages": len(reservoir),
            "best_median": round(float(np.median(b_res)), 3),
            "best_p90": round(float(np.percentile(b_res, 90)), 3),
            "best_max": round(float(b_res.max()), 3),
        }

    # ── Q4 : le cas de Mike ─────────────────────────────────────────────────
    photos_cas, cas_qui_gagnent = set(), set()
    for k, fv in fvecs_par_cle.items():
        if k not in ptags:
            continue
        if all((k, i) in rattaches for i, _v in fv):
            continue
        if vivantes is not None and k not in vivantes and k in gagnants:
            continue
        photos_cas.add(k)
        if k in gagnants and (vivantes is None or k in vivantes):
            cas_qui_gagnent.add(k)
    rap["q4_cas_de_mike"] = {
        "photos_nommees_a_visage_non_couvert": len(photos_cas),
        "qui_gagneraient_un_nom": len(cas_qui_gagnent),
    }

    # Les deux définitions de « visage sans nom », côte à côte
    muets_photo = sum(1 for n in range(len(retenus)) if cles[n] not in ptags)
    non_rattaches = sum(1 for n in range(len(retenus))
                        if (cles[n], idxs[n]) not in rattaches)
    rap["deux_mesures"] = {
        "visage_non_rattache": non_rattaches,
        "visage_sur_photo_muette": muets_photo,
        "total_visages_examines": len(retenus),
    }

    # ── échantillon à juger ─────────────────────────────────────────────────
    rnd = random.Random(graine)
    par_personne = Counter(e["person"] for e in file_auto)
    rap["q1_auto_par_personne"] = dict(par_personne.most_common(12))
    # Forme des clés : une clé RELATIVE passe par la racine des uploads, une
    # clé absolue par sa propre racine. Le garde-fou des clés fantômes ne
    # traite pas les deux pareil — savoir laquelle domine oriente l'enquête.
    rap["q1_auto_formes_de_cle"] = dict(Counter(
        'UNC' if e["key"].startswith('\\\\') else
        ('absolue' if (len(e["key"]) > 2 and e["key"][1] == ':') else 'relative')
        for e in file_auto))
    rap["echantillon_auto"] = rnd.sample(file_auto, min(exemples, len(file_auto)))

    file_add.sort(key=lambda x: x["margin"])
    rap["echantillon_file"] = rnd.sample(file_add, min(exemples, len(file_add)))
    haut = sorted(reservoir, reverse=True)[:max(exemples * 4, 40)]
    rap["echantillon_reservoir"] = [
        {"person": nm, "key": k, "i": i, "sim": round(b, 3), "margin": round(m, 3)}
        for b, m, k, i, nm in rnd.sample(haut, min(exemples, len(haut)))]
    return rap


# ──────────────────────────────── le rapport ────────────────────────────────

def pourcent(x, n):
    return f"{100.0 * x / n:.1f} %" if n else "—"


def afficher(r):
    s, m = r["seuils"], r["matiere"]
    L = []
    A = L.append
    A("MESURE — LA PROPAGATION DES NOMS : QUE PROPOSE-T-ELLE DEJA ?")
    A("=" * 78)
    A("")
    A(f"Seuils lus dans server.py : ajout >= {s['CUR_ADD_SIM']}, "
      f"auto >= {s['AUTO_ADD_SIM']} avec marge >= {s['AUTO_ADD_MARGIN']} "
      f"(auto {'ACTIF' if s['AUTO_ADD_ENABLE'] else 'INACTIF'}), "
      f"faux positif < {s['CUR_FP_SIM']}, fusion >= {s['CUR_MERGE_SIM']}, "
      f"plafond {s['CUR_MAX_SUGGEST']}, passe toutes les {s['CURATOR_INTERVAL']} s.")
    if r["seuils_txt"]:
        A(f"  seuils.txt surcharge : {r['seuils_txt']}")
    A("")
    A(f"Matiere : {m['fiches_avec_signature']} fiches avec signature "
      f"({m['facettes']} facettes, {m['dimension']}-d), "
      f"{m['fiches_sans_signature']} nommees SANS signature.")
    A(f"          {m['visages_examines']} visages examines sur "
      f"{m['photos_a_visage']} photos a visage ; "
      f"{m['photos_nommees']} photos portent un nom ; "
      f"{m['couples_rattaches']} couples [cle, index] rattaches.")
    A(f"          ecartes : {m['visages_ecartes']}")
    A(f"          fiches de visages dont la cle n'est PLUS dans l'index : "
      f"{m['fiches_visages_hors_index']}")
    A("")
    d = r["deux_mesures"]
    A("DEUX MESURES, DEUX QUESTIONS (ne jamais les confondre) :")
    A(f"  visage NON RATTACHE a une fiche  : {d['visage_non_rattache']} "
      f"({pourcent(d['visage_non_rattache'], d['total_visages_examines'])}) "
      "— ce dont un ALGORITHME a besoin")
    A(f"  visage sur une photo SANS NOM    : {d['visage_sur_photo_muette']} "
      f"({pourcent(d['visage_sur_photo_muette'], d['total_visages_examines'])}) "
      "— ce que le PRODUIT montre")
    A("")
    A("-" * 78)
    A("Q1 — LE SORT DE CHAQUE VISAGE SOUS LA REGLE D'AUJOURD'HUI")
    A("-" * 78)
    q1 = r["q1_sorts"]
    tot = sum(q1.values()) or 1
    for cle in ('deja_dit', 'exclu_par_un_humain', 'sous_seuil',
                'doublon_meme_photo', 'auto', 'file'):
        if cle in q1:
            A(f"  {cle:<22} {q1[cle]:>7}  ({pourcent(q1[cle], tot)})")
    A("")
    A(f"  >>> PHOTOS qui gagneraient un nom NOUVEAU : "
      f"{r['q1_photos_qui_gagnent_un_nom']}  "
      f"({r['q1_noms_poses']} noms poses)")
    A("")
    A("-" * 78)
    A("Q2 — LA FILE LES MONTRE-T-ELLE ?  (tri : remove, puis merge, puis add)")
    A("-" * 78)
    q2 = r["q2_file"]
    A(f"  remove {q2['remove']}   merge {q2['merge']}   add {q2['add']}   "
      f"plafond {q2['plafond']}")
    A(f"  add VISIBLES : {q2['add_visibles']}   "
      f"caches par le plafond : {q2['add_caches_par_le_plafond']}")
    A(f"  faux positifs que la prod re-retire a chaque passe : "
      f"{q2['faux_positifs_re_retires']}")
    A("")
    A("-" * 78)
    A("Q3 — OU SONT LES VISAGES MUETS ?")
    A("-" * 78)
    if "q3_reservoir" in r:
        q3 = r["q3_reservoir"]
        A(f"  {q3['visages']} visages sous le seuil — meilleur voisin : "
          f"median {q3['best_median']}, p90 {q3['best_p90']}, "
          f"max {q3['best_max']}")
    A("  tranches (meilleur score) :")
    for t, n in r["q3_tranches_sous_seuil"].items():
        t = float(t)
        A(f"    {t:>6.2f} .. {t + TRANCHE:>5.2f}  {n:>7}  "
          f"{'#' * min(60, n // 200)}")
    A("")
    A("  si le seuil d'ajout descendait a :")
    for seuil, v in r["q3_par_seuil"].items():
        A(f"    {seuil}  ->  {v['photos_gagnees']:>6} photos "
          f"(dont {v['dont_marge_serree']} visages a marge serree, "
          "donc a juger a la main)")
    A("")
    if "fichiers" in r:
        f = r["fichiers"]
        A("-" * 78)
        A(f"LE GARDE-FOU DES CLES FANTOMES (uploads : {f['dossier_uploads']})")
        A("-" * 78)
        A(f"  {f['cles_candidates_testees']} cles candidates testees -> "
          f"{f['fichier_present']} fichiers presents, "
          f"{f['cle_fantome']} FANTOMES "
          f"({pourcent(f['cle_fantome'], f['cles_candidates_testees'])})")
        A(f"  fantomes presentes AUSSI dans l'index : "
          f"{f['fantomes_dans_l_index']} — le reste ne vit que dans le "
          "magasin de visages")
        for ex in f["exemples_fantomes"][:4]:
            A(f"        {ex}")
        A(f"  >>> ce que la regle rattacherait VRAIMENT : "
          f"{r['q1_auto_reels']} en automatique, {r['q1_file_reels']} en file, "
          f"sur {r['q1_photos_qui_gagnent_un_nom_REELLES']} photos "
          f"({r['q1_noms_poses_REELS']} noms)")
        A("")
    A("-" * 78)
    A("Q4 — LE CAS DE MIKE : un nom pose, un visage non couvert")
    A("-" * 78)
    q4 = r["q4_cas_de_mike"]
    A(f"  photos concernees : {q4['photos_nommees_a_visage_non_couvert']}")
    A(f"  dont la regle en sortirait un nom NOUVEAU : "
      f"{q4['qui_gagneraient_un_nom']}")
    A("")
    A("-" * 78)
    A("ECHANTILLONS A JUGER (graine fixe — rejouables)")
    A("-" * 78)
    A("  auto (ce que la regle rattacherait SANS validation) :")
    for e in r.get("echantillon_auto", []):
        A(f"    {e['sim']:.3f} marge {e['margin']:.3f}  {e['person']:<16} "
          f"{e['key']}#{e['i']}")
    A(f"  formes de cle des candidats auto : {r.get('q1_auto_formes_de_cle')}")
    A(f"  auto par personne (12 premieres) : {r.get('q1_auto_par_personne')}")
    A("  file « A verifier » :")
    for e in r["echantillon_file"]:
        A(f"    {e['sim']:.3f} marge {e['margin']:.3f}  {e['person']:<16} "
          f"contre {e['rival']:<16} {e['key']}#{e['i']}")
    A("  reservoir (les meilleurs scores SOUS le seuil) :")
    for e in r["echantillon_reservoir"]:
        A(f"    {e['sim']:.3f} marge {e['margin']:.3f}  {e['person']:<16} "
          f"{e['key']}#{e['i']}")
    A("")
    if "fichiers" in r:
        A("LIMITES DECLAREES : le garde-fou des cles fantomes EST applique "
          "(un stat par cle candidate, seul acces NAS du banc) ; les comptes "
          "marques REELLES ne portent que sur des fichiers presents. Aucune "
          "ecriture, aucun modele charge.")
    else:
        A("LIMITES DECLAREES : sans --fichiers, le garde-fou des cles "
          "fantomes n'est PAS applique — les comptes d'ajout sont une BORNE "
          "HAUTE, et le 21/08 a montre qu'elle est 100 fois trop haute. "
          "Aucune ecriture, aucun acces NAS, aucun modele charge.")
    A("Q5 (la repasse) se verifie sur le serveur vivant, pas ici : "
      "GET /api/curator/list.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', required=True, help="COPIE de photos.db")
    ap.add_argument('--projet', default='.')
    ap.add_argument('--exemples', type=int, default=12)
    ap.add_argument('--graine', type=int, default=20260821)
    ap.add_argument('--fichiers', type=int, default=0,
                    help="teste l'existence de N cles par classe (stat NAS)")
    ap.add_argument('--json', dest='sortie_json')
    a = ap.parse_args(argv)
    rap = mesurer(a.base, a.projet, a.exemples, a.graine, a.fichiers)
    print(afficher(rap))
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\nJSON : {a.sortie_json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
