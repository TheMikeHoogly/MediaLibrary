#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure -- ce que coute la passe ADD du curateur, et ce qu'un calcul en bloc
rendrait (point d'audit O8, `docs/AUDIT_INTERNE_2026-08.md`)
------------------------------------------------------------------------------

`build_suggestions()` tourne toutes les 240 s (`CURATOR_INTERVAL`). Sa boucle
ADD fait, POUR CHAQUE visage : un decodage base64 + float16, un `Cproto @ v`,
un `np.maximum.at`, un `argmax` et un `partition`. L'audit estimait « des
minutes » ; ce banc remplace l'estimation par un chiffre, sur le fonds reel.

Il REJOUE le calcul sur une COPIE de la base (jamais `photos.db`) :
  - les prototypes de chaque personne, par `classifier.prototypes`, depuis ses
    references (`vectors`, kind `people`) -- comme `person_prototypes` ;
  - chaque visage (kind `faces`) re-encode en base64 float16, la forme exacte
    sous laquelle `FACE_STORE` le garde en memoire.
Puis deux chemins :
  (A) la boucle d'aujourd'hui, visage par visage ;
  (B) le bloc : un decodage par visage, UNE matrice, `F @ Cproto.T` par
      tranches, le max par personne en `maximum.reduceat`.
Et il JUGE (B) contre (A) : meme meilleure personne, meme score, meme second,
sur TOUS les visages. Un (B) plus rapide mais different est un (B) faux.

Ce que ce banc ne mesure PAS : le filtrage (`pas_visage`, clés fantomes, tags
deja poses), la passe REMOVE, et le tour de GIL rendu aux requetes. Il chiffre
le noyau que l'audit designait, pas la passe entiere.

    python mesure_curateur.py --base copie.db [--limite N] [--tranche 4096]
"""
import argparse
import base64
import sys
import time
from collections import defaultdict
from pathlib import Path

SEP = '\x1f'


def charger(base, limite=0):
    import sqlite3
    import numpy as np
    if Path(base).name == 'photos.db':
        print('REFUS : ce banc lit une COPIE (mesure_copie_base.py), jamais photos.db')
        sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    refs = defaultdict(list)
    for k, v, dt in cx.execute("SELECT k, v, dtype FROM vectors WHERE kind='people'"):
        refs[k.split(SEP, 1)[0]].append(np.frombuffer(v, dtype=np.float16 if dt == 'f16' else np.float32))
    faces = []
    q = "SELECT v, dtype FROM vectors WHERE kind='faces'"
    if limite:
        q += ' LIMIT %d' % int(limite)
    for v, dt in cx.execute(q):
        a = np.frombuffer(v, dtype=np.float16 if dt == 'f16' else np.float32).astype(np.float16)
        faces.append(base64.b64encode(a.tobytes()).decode('ascii'))
    cx.close()
    return refs, faces


def dec(s):
    import numpy as np
    v = np.frombuffer(base64.b64decode(s), dtype=np.float16).astype(np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n else v


def construire(refs):
    import numpy as np
    from classifier import prototypes
    lignes, proprio, n_pers = [], [], 0
    for nom in sorted(refs):
        vs = [dec(base64.b64encode(r.astype(np.float16).tobytes())) for r in refs[nom]]
        P = prototypes(vs)
        if P is None or not len(P):
            continue
        for row in P:
            lignes.append(row)
            proprio.append(n_pers)
        n_pers += 1
    return np.stack(lignes).astype(np.float32), np.asarray(proprio), n_pers


def chemin_a(faces, Cproto, proprio, n_pers):
    import numpy as np
    out = np.empty((len(faces), 3), dtype=np.float64)
    for n, s in enumerate(faces):
        v = dec(s)
        brut = Cproto @ v
        sims = np.full(n_pers, -2.0, dtype=np.float32)
        np.maximum.at(sims, proprio, brut)
        j = int(np.argmax(sims))
        second = float(np.partition(sims, -2)[-2]) if n_pers >= 2 else -1.0
        out[n] = (j, float(sims[j]), second)
    return out


def chemin_b(faces, Cproto, proprio, n_pers, tranche):
    import numpy as np
    # proprio est TRIE par construction (les lignes d'une personne se suivent)
    assert np.all(np.diff(proprio) >= 0)
    debuts = np.flatnonzero(np.r_[True, np.diff(proprio) > 0])
    F = np.stack([dec(s) for s in faces]) if faces else np.zeros((0, Cproto.shape[1]), np.float32)
    out = np.empty((len(faces), 3), dtype=np.float64)
    for a in range(0, len(faces), tranche):
        brut = F[a:a + tranche] @ Cproto.T
        sims = np.maximum.reduceat(brut, debuts, axis=1)
        j = np.argmax(sims, axis=1)
        best = sims[np.arange(len(j)), j]
        second = np.partition(sims, -2, axis=1)[:, -2] if n_pers >= 2 else np.full(len(j), -1.0)
        out[a:a + len(j), 0] = j
        out[a:a + len(j), 1] = best
        out[a:a + len(j), 2] = second
    return out


def main(argv=None):
    import numpy as np
    ap = argparse.ArgumentParser(description='cout de la passe ADD du curateur (O8)')
    ap.add_argument('--base', required=True)
    ap.add_argument('--limite', type=int, default=0)
    ap.add_argument('--tranche', type=int, default=4096)
    a = ap.parse_args(argv)
    t = time.perf_counter()
    refs, faces = charger(a.base, a.limite)
    t_charge = time.perf_counter() - t
    t = time.perf_counter()
    Cproto, proprio, n_pers = construire(refs)
    t_proto = time.perf_counter() - t
    print('personnes : %d  (references %d, prototypes %d)  visages : %d'
          % (n_pers, sum(len(v) for v in refs.values()), len(Cproto), len(faces)))
    print('chargement %.1f s, prototypes %.1f s (hors mesure)' % (t_charge, t_proto))
    t = time.perf_counter()
    A = chemin_a(faces, Cproto, proprio, n_pers)
    ta = time.perf_counter() - t
    t = time.perf_counter()
    B = chemin_b(faces, Cproto, proprio, n_pers, a.tranche)
    tb = time.perf_counter() - t
    meme_j = int(np.sum(A[:, 0] == B[:, 0]))
    ecart = float(np.max(np.abs(A[:, 1:] - B[:, 1:]))) if len(A) else 0.0
    print('=' * 74)
    print('(A) boucle par visage : %6.2f s   (%.1f us/visage)' % (ta, 1e6 * ta / max(1, len(faces))))
    print('(B) calcul en bloc    : %6.2f s   (x%.1f)' % (tb, ta / tb if tb else 0))
    print('juge : meme personne %d / %d, ecart max des scores %.2e' % (meme_j, len(faces), ecart))
    ok = meme_j == len(faces) and ecart < 1e-4
    print('VERDICT : %s' % ('B == A' if ok else 'B DIFFERE DE A -- ne pas adopter'))
    print('par heure (1 passe / 240 s) : A %.0f s, B %.0f s de CPU' % (ta * 15, tb * 15))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
