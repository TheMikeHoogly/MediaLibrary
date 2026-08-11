#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Éval INT8 des vecteurs stockés — protocole vision-eval (11/08/2026).

HYPOTHÈSE (écrite avant mesure) : quantifier les embeddings STOCKÉS
(aujourd'hui float16, voir vectors.py) en INT8 symétrique par vecteur divise
le stockage par ~2 — pas 4 : la base est déjà en f16 — SANS changer aucune
décision aux seuils de production (FACE_MATCH_SIM=0.42, FACE_CLUSTER_SIM=0.50,
PET_CLUSTER_SIM=0.60) et sans dégrader l'ordre des voisins sémantiques
(recall@10 ≥ 0,999).

JEU : la table `vectors` d'une COPIE de la base réelle (jamais photos.db en
direct — le serveur est l'écrivain unique). VRAM : N/A (stockage, calcul CPU).

RÉSULTAT MESURÉ (11/08/2026, copie de la base réelle, 130 576 vecteurs) :

    kind        n     dim   f16→int8      |Δcos|max   bascules de seuil
    faces    71 846   512   73,6→37,1 Mo   0,0028     0,42: 1486/86,2M (0,0017 %)
                                                      0,50: 1536/86,2M (0,0018 %)
    people    9 201   512    9,4→ 4,7 Mo   0,0027     0,42:  112/27,6M (0,0004 %)
    animals   4 826   768    7,4→ 3,7 Mo   0,0029     0,60: 1454/23,3M (0,0062 %)
    pets        272   768    0,4→ 0,2 Mo   0,0019     0,60:    0
    photo    44 431   768   68,2→34,3 Mo   0,0073     recall@10 = 0,9685

    Total : 159 → 80 Mo (×2), sur une base LOCALE de 275 Mo (le NAS ne reçoit
    que des snapshots — la prémisse « moins de SMB » ne s'applique pas).

DÉCISION : REJETÉ (consigné dans eval/DECISIONS.md).
  - recall@10 sémantique 0,9685 : ~3 % des voisins top-10 changent — l'hypothèse
    « sans perte » est réfutée (les vecteurs SigLIP ont des dimensions extrêmes
    qui souffrent de l'échelle symétrique par vecteur : |Δcos| 2,6× pire) ;
  - bascules non nulles à tous les seuils (paires à ~1e-6 du seuil : décisions
    déjà arbitraires en f16, mais non reproductibles après migration) ;
  - perte de l'invariant central de vectors.py : « les octets sont préservés à
    l'identique → résultats identiques au bit près, rien à recalibrer » ;
  - gain réel : ~79 Mo locaux. Ne paie ni la migration ni la perte de garantie.

Usage :
    python eval_int8_vectors.py CHEMIN_VERS_COPIE.db
"""
import json
import sqlite3
import sys

import numpy as np

SEUILS = {'faces': [0.42, 0.50], 'people': [0.42], 'animals': [0.60],
          'pets': [0.60], 'photo': []}
# Requêtes échantillonnées (graine figée → mesures comparables entre runs).
N_Q = {'faces': 1200, 'people': 3000, 'animals': 5000, 'pets': 500, 'photo': 600}


def normalise(X):
    X = X.astype(np.float32)
    n = np.linalg.norm(X, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return X / n


def quantifie_int8(M16):
    """INT8 symétrique par vecteur : s = max|x|/127, q = round(x/s) — puis
    déquantifié pour mesurer ce que verrait la recherche cosinus."""
    X = M16.astype(np.float32)
    s = np.abs(X).max(axis=1, keepdims=True) / 127.0
    s[s == 0] = 1.0
    q = np.clip(np.rint(X / s), -127, 127).astype(np.int8)
    return q.astype(np.float32) * s


def evalue(cx, kind):
    rng = np.random.default_rng(42)
    blobs = [v for (v,) in cx.execute(
        "SELECT v FROM vectors WHERE kind=?", (kind,))]
    if not blobs:
        return None
    dims = {}
    for b in blobs:
        dims[len(b) // 2] = dims.get(len(b) // 2, 0) + 1
    d = max(dims, key=dims.get)
    M16 = np.stack([np.frombuffer(b, np.float16)
                    for b in blobs if len(b) // 2 == d])
    n = M16.shape[0]
    A = normalise(M16)                    # référence : pipeline en place (f16)
    B = normalise(quantifie_int8(M16))    # candidat : int8 déquantifié

    nq = min(N_Q[kind], n)
    qi = rng.choice(n, nq, replace=False)
    dmax, tot = 0.0, 0
    flips = {t: 0 for t in SEUILS[kind]}
    marge = {t: 1.0 for t in SEUILS[kind]}
    rec10 = []
    for deb in range(0, nq, 250):
        idx = qi[deb:deb + 250]
        Sa, Sb = A[idx] @ A.T, B[idx] @ B.T
        for j, i in enumerate(idx):       # exclure la paire (i,i)
            Sa[j, i] = -2
            Sb[j, i] = -2
        dmax = max(dmax, float(np.abs(Sa - Sb).max()))
        tot += Sa.shape[0] * (n - 1)
        for t in SEUILS[kind]:
            f = (Sa >= t) != (Sb >= t)
            nf = int(f.sum())
            flips[t] += nf
            if nf:
                marge[t] = min(marge[t], float(np.abs(Sa[f] - t).min()))
        if kind == 'photo':               # ordre des voisins sémantiques
            ta = np.argpartition(-Sa, 10, axis=1)[:, :10]
            tb = np.argpartition(-Sb, 10, axis=1)[:, :10]
            for j in range(Sa.shape[0]):
                rec10.append(len(set(ta[j]) & set(tb[j])) / 10.0)
    return {'kind': kind, 'n': n, 'dim': d,
            'f16_Mo': round(n * d * 2 / 1e6, 2),
            'int8_Mo': round(n * (d + 4) / 1e6, 2),
            'paires': tot, 'dcos_max': round(dmax, 5),
            'flips': {str(t): flips[t] for t in SEUILS[kind]},
            'marge_min': {str(t): marge[t] for t in SEUILS[kind]},
            'recall10': round(float(np.mean(rec10)), 4) if rec10 else None}


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage : python eval_int8_vectors.py CHEMIN_VERS_COPIE.db "
                 "(jamais photos.db en direct)")
    if sys.argv[1].endswith('photos.db'):
        sys.exit("Refus : travaille sur une COPIE de la base (cf. CLAUDE.md).")
    cx = sqlite3.connect(sys.argv[1])
    for kind in ('faces', 'people', 'animals', 'pets', 'photo'):
        r = evalue(cx, kind)
        if r:
            print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()
