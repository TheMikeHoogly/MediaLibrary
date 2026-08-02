#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de fichiers.py sur un systeme de fichiers temporaire + STORE simule.

On n'importe pas server.py (il ouvrirait la vraie base). On rejoue la meme
mecanique : un store {cle: entree} et un rekey(old,new) qui deplace l'entree —
exactement ce que fait rekey_everywhere pour la cle. On verifie qu'aucune
entree (donc aucun tag `personne:`) n'est perdue lors des operations, et que
tout est annulable.

Lance :  python test_fichiers.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

import fichiers
from fichiers import FileOps, FileOpError, key_for_new_path, sanitize_name, resolve_target

FAIL = []


def check(cond, msg):
    print(("  OK " if cond else "  ECHEC ") + msg)
    if not cond:
        FAIL.append(msg)


def make_world():
    """Cree Uploads/ + un dossier NAS + des fichiers, et un STORE simule."""
    base = Path(tempfile.mkdtemp(prefix="fichiers_test_"))
    up = base / "Uploads"
    nas = base / "NAS" / "Photos"
    (up / "Album").mkdir(parents=True)
    nas.mkdir(parents=True)
    (up / "flat.jpg").write_bytes(b"a")
    (up / "Album" / "sub.jpg").write_bytes(b"b")
    (nas / "2020").mkdir()
    (nas / "2020" / "vac.jpg").write_bytes(b"c")

    # STORE simule : cle -> entree. Cles selon la convention scan_uploads.
    store = {
        "flat.jpg": {"kw_fr": ["plage"]},
        "Album/sub.jpg": {"kw_fr": ["chat"], "tags": ["personne:Luna"]},
        str(nas / "2020" / "vac.jpg"): {"kw_fr": ["montagne"],
                                        "tags": ["personne:Mike"]},
    }
    roots = [("Uploads", up), ("Photos", nas)]

    def resolve_key(k):
        p = Path(k)
        return p if p.is_absolute() else up / k

    def rekey(old, new, mtime=None):
        if old in store:
            store[new] = store.pop(old)
            return True
        return False

    ops = FileOps(roots_fn=lambda: roots, resolve_key=resolve_key,
                  store_keys=lambda: list(store.keys()), rekey=rekey,
                  journal_path=base / "undo.json", trash_dir=base / ".corbeille-rangement")
    return base, up, nas, roots, store, ops


def names(store):
    """Ensemble de tous les tags personne: presents (pour verifier zero perte)."""
    out = set()
    for e in store.values():
        for t in e.get("tags", []):
            if t.startswith("personne:"):
                out.add(t)
    return out


def main():
    base, up, nas, roots, store, ops = make_world()
    try:
        noms0 = names(store)
        check(noms0 == {"personne:Luna", "personne:Mike"}, "verite terrain : 2 noms humains")

        # --- confinement / sanitize ---
        try:
            resolve_target(roots, 0, "../secret")
            check(False, "'..' doit etre rejete")
        except FileOpError:
            check(True, "'..' rejete (confinement)")
        check(sanitize_name(' a/b:c*.jpg ') == 'b_c_.jpg', "sanitize nom de fichier")

        # --- rename fichier a la racine Uploads (cle = nom simple) ---
        ops.rename(0, "flat.jpg", "plage2024.jpg", up)
        check((up / "plage2024.jpg").exists() and not (up / "flat.jpg").exists(),
              "rename : fichier renomme sur disque")
        check("plage2024.jpg" in store and "flat.jpg" not in store,
              "rename : cle Uploads re-clee (nom simple)")

        # --- rename fichier en sous-dossier (cle = relatif posix) ---
        ops.rename(0, "Album/sub.jpg", "luna.jpg", up)
        check("Album/luna.jpg" in store and "Album/sub.jpg" not in store,
              "rename : cle sous-dossier re-clee (relatif posix)")
        check(names(store) == noms0, "rename : aucun nom humain perdu")

        # --- move NAS -> Uploads/Album (cle absolue -> relative) ---
        old_abs = str(nas / "2020" / "vac.jpg")
        ops.move(1, "2020/vac.jpg", 0, "Album", up)
        check((up / "Album" / "vac.jpg").exists(), "move : fichier deplace sur disque")
        check("Album/vac.jpg" in store and old_abs not in store,
              "move : cle absolue NAS -> relative Uploads")
        check(names(store) == noms0, "move : nom humain Mike preserve")

        # --- undo du move ---
        ops.undo(up)
        check((nas / "2020" / "vac.jpg").exists() and not (up / "Album" / "vac.jpg").exists(),
              "undo move : fichier revenu")
        check(old_abs in store and "Album/vac.jpg" not in store,
              "undo move : cle revenue a l'absolu")
        check(names(store) == noms0, "undo move : noms intacts")

        # --- delete -> quarantaine + undo ---
        r = ops.delete(1, "2020/vac.jpg", up)
        check(not (nas / "2020" / "vac.jpg").exists() and Path(r["trash"]).exists(),
              "delete : fichier en corbeille (pas de rm)")
        check(old_abs not in store and r["trash"] in store,
              "delete : cle suivie vers la corbeille")
        check(names(store) == noms0, "delete : nom Mike toujours present (restaurable)")
        ops.undo(up)
        check((nas / "2020" / "vac.jpg").exists() and old_abs in store,
              "undo delete : fichier et cle restaures")
        check(names(store) == noms0, "undo delete : noms intacts")

        # --- mkdir + undo ---
        ops.mkdir(0, "", "Nouveau")
        check((up / "Nouveau").is_dir(), "mkdir : dossier cree")
        ops.undo(up)
        check(not (up / "Nouveau").exists(), "undo mkdir : dossier retire")

        # --- move d'un DOSSIER entier (re-cle de l'arbre) ---
        # remet un fichier tague dans Album puis deplace Album vers NAS
        ops.move(0, "Album/luna.jpg", 1, "2020", up)  # sortir luna du dossier a deplacer
        # deplace le dossier Album (contient plage2024 ? non) -> creons un cas net
        (up / "Set").mkdir()
        (up / "Set" / "x.jpg").write_bytes(b"x")
        store["Set/x.jpg"] = {"tags": ["personne:Zab"]}
        noms1 = names(store)
        ops.move(0, "Set", 1, "2020", up)  # Uploads/Set -> NAS/2020/Set
        moved_key = str(nas / "2020" / "Set" / "x.jpg")
        check((nas / "2020" / "Set" / "x.jpg").exists(), "move dossier : arbre deplace")
        check(moved_key in store and "Set/x.jpg" not in store,
              "move dossier : enfant re-cle (relatif -> absolu)")
        check(names(store) == noms1, "move dossier : nom Zab preserve")

        print()
        if FAIL:
            print(f"ECHEC : {len(FAIL)} assertion(s) — {FAIL}")
            return 1
        print("Tous les tests fichiers.py : VERTS")
        return 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
