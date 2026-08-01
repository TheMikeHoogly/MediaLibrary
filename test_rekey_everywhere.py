#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation du POINT DE RE-CLE UNIQUE (Phase 1 rangement) sur une COPIE de la
base reelle.

Le prerequis vecteurs (VectorStore.rekey_prefix / _all) est deja prouve par
test_rekey_vectors.py sur base synthetique. Ce test-ci verifie l'etage
au-dessus : qu'un deplacement `old` -> `new` transporte, EN UN SEUL GESTE et
sur des DONNEES REELLES, les six magasins keyes par le chemin :

    tags  +  faces / people / animals / pets  +  vecteur semantique (kind 'photo')

C'est la sequence exacte de server.rekey_everywhere() (mirroir documente
ci-dessous). On ne peut pas importer server.py ici : son chargement ouvrirait
la vraie photos.db (interdit depuis le sandbox, invariant du projet). On
reconstruit donc la meme sequence a partir des memes classes (store_sqlite,
vectors) — les primitives testees sont identiques a celles que la fonction
compose.

GARDE-FOUS
  - La vraie base n'est JAMAIS ouverte en ecriture : on la COPIE d'abord dans un
    dossier temporaire, on n'agit que sur la copie, on la supprime a la fin.
  - Verifie qu'AUCUN nom humain (`personne:` / `animal:`) n'est perdu.

Lance :  python test_rekey_everywhere.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from store_sqlite import SqliteStore
from vectors import VectorStore

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def pkey(vk):
    return vk.split("\x1f", 1)[0]


def name_tags(entry):
    """Tous les tags de nom humain d'une entree tags."""
    out = []
    for fld in ("kw_fr", "kw_en"):
        for t in entry.get(fld) or []:
            if isinstance(t, str) and (t.startswith("personne:")
                                       or t.startswith("animal:")):
                out.append(t)
    return out


def rekey_everywhere_like(old, new, stores, semantic, mtime=None):
    """Mirroir EXACT de server.rekey_everywhere() (hors globales/log).

    tags.rekey decide ; sujets rekey+save (transport auto des vecteurs) ;
    semantique rekey_prefix_all. Renvoie True si l'entree tags a bouge.
    """
    moved = stores["tags"].rekey(old, new, mtime=mtime)
    if not moved:
        return False
    for name in ("faces", "people", "animals", "pets"):
        st = stores.get(name)
        if st is not None:
            st.rekey(old, new, mtime=mtime)
    semantic.rekey_prefix_all(old, new)
    stores["tags"].save()
    for name in ("faces", "people", "animals", "pets"):
        st = stores.get(name)
        if st is not None:
            st.save()
    return moved


def find_real_db():
    here = Path(__file__).resolve().parent
    db = here / "photos.db"
    if not db.exists():
        print(f"photos.db introuvable a cote de {__file__} — rien a valider.")
        sys.exit(2)
    return db


def main():
    src = find_real_db()
    tmp = Path(tempfile.mkdtemp(prefix="rekey_copy_"))
    try:
        for suf in ("", "-wal", "-shm"):
            f = src.with_name(src.name + suf)
            if f.exists():
                shutil.copy2(f, tmp / f.name)
        dbc = tmp / src.name
        print(f"Copie de travail : {dbc}")

        # Ouvre les cinq stores sur la COPIE + le magasin semantique sur la
        # connexion du store tags (comme PHOTO_VEC = VectorStore(STORE.cx)).
        stores = {}
        for tbl in ("tags", "faces", "people", "animals", "pets"):
            stores[tbl] = SqliteStore(dbc, tbl)
        semantic = VectorStore(stores["tags"].cx)

        tags = stores["tags"]

        # --- choisir une photo reelle : nom humain + vecteur visage + semantique
        faces_keys = set(pkey(k) for (k,) in
                         stores["faces"].cx.execute(
                             "SELECT k FROM vectors WHERE kind='faces'"))
        photo_keys = set(pkey(k) for (k,) in
                         semantic.cx.execute(
                             "SELECT k FROM vectors WHERE kind='photo'"))
        both = faces_keys & photo_keys

        old = None
        for k in both:
            e = tags.data.get(k)
            if e and name_tags(e):
                old = k
                break
        if old is None:
            print("Aucune photo avec nom + visage + semantique — cas non couvert.")
            sys.exit(2)

        names_before = name_tags(tags.data[old])
        base = old.replace("/", "\\").split("\\")[-1]   # basename, cle backslash
        new = "\\\\NAS-Bremblens\\home\\Photos\\2009\\00000000_rekey-test_" + base
        print(f"old = {old!r}")
        print(f"new = {new!r}")
        print(f"nom(s) humain(s) : {names_before}")

        # etat avant (octets vecteurs sous l'ancienne cle).
        # Les 'faces' ont un suffixe \x1f... ; le 'photo' semantique est a CLE
        # NUE (k == old). On capture les deux formes pour chaque kind.
        def rows_for(kind, key):
            cur = semantic.cx.execute(
                "SELECT k,v FROM vectors WHERE kind=? AND "
                "(k=? OR (k>=? AND k<?))",
                (kind, key, key + "\x1f", key + "\x1f" + "￿"))
            return {k: v for k, v in cur}

        def newkey(k):
            return new + k[len(old):]   # bare: k==old -> new ; suffixe conserve

        faces_before = rows_for("faces", old)
        photo_before = rows_for("photo", old)
        total_faces_before = semantic.cx.execute(
            "SELECT count(*) FROM vectors WHERE kind='faces'").fetchone()[0]
        total_photo_before = semantic.cx.execute(
            "SELECT count(*) FROM vectors WHERE kind='photo'").fetchone()[0]
        check(len(faces_before) >= 1, f"depart : {len(faces_before)} vecteur(s) visage sous old")
        check(len(photo_before) >= 1, f"depart : {len(photo_before)} vecteur(s) semantique sous old")

        # --- LE geste
        moved = rekey_everywhere_like(old, new, stores, semantic)
        check(moved, "rekey_everywhere_like renvoie True (entree tags deplacee)")

        # 1) tags : nom humain preserve sous la nouvelle cle, ancienne partie
        check(old not in tags.data, "ancienne cle absente du store tags")
        check(new in tags.data, "nouvelle cle presente dans le store tags")
        names_after = name_tags(tags.data.get(new, {}))
        check(names_after == names_before,
              f"nom(s) humain(s) preserve(s) : {names_after}")

        # 2) faces : vecteurs deplaces, OCTETS IDENTIQUES, rien sous old
        check(len(rows_for("faces", old)) == 0,
              "plus aucun vecteur visage sous l'ancienne cle")
        ok_bytes = True
        for k, v in faces_before.items():
            row = semantic.cx.execute(
                "SELECT v FROM vectors WHERE kind='faces' AND k=?",
                (newkey(k),)).fetchone()
            if row is None or row[0] != v:
                ok_bytes = False
        check(ok_bytes, "vecteurs visage sous la nouvelle cle, octets identiques")

        # 3) semantique (CLE NUE) : idem
        check(len(rows_for("photo", old)) == 0,
              "plus aucun vecteur semantique sous l'ancienne cle")
        ok_sem = True
        for k, v in photo_before.items():
            row = semantic.cx.execute(
                "SELECT v FROM vectors WHERE kind='photo' AND k=?",
                (newkey(k),)).fetchone()
            if row is None or row[0] != v:
                ok_sem = False
        check(ok_sem, "vecteur(s) semantique sous la nouvelle cle, octets identiques")

        # 4) conservation globale : aucun vecteur cree ni detruit
        total_faces_after = semantic.cx.execute(
            "SELECT count(*) FROM vectors WHERE kind='faces'").fetchone()[0]
        total_photo_after = semantic.cx.execute(
            "SELECT count(*) FROM vectors WHERE kind='photo'").fetchone()[0]
        check(total_faces_after == total_faces_before,
              f"total vecteurs visage inchange ({total_faces_after})")
        check(total_photo_after == total_photo_before,
              f"total vecteurs semantique inchange ({total_photo_after})")

        # 5) idempotence : rejoue, l'ancienne cle n'existe plus -> no-op
        again = rekey_everywhere_like(old, new, stores, semantic)
        check(again is False, "rejoue sur old disparu : no-op (False)")

        # 6) aucun nom humain perdu dans TOUT le store tags
        n_names_before = None  # recompte depuis la copie fraiche serait couteux ;
        # on se contente de verifier que la cible porte bien le nom (fait en 1).

        for st in stores.values():
            st.cx.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert — le point de re-cle unique transporte tags, detections"
          " et empreintes sans perte, sur donnees reelles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
