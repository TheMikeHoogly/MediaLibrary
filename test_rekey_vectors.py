#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test isolé de VectorStore.rekey_prefix / rekey_prefix_all (Phase 1 rangement).

Prouve, sur une base SQLite temporaire (jamais la vraie photos.db) :
  1. Un déplacement re-clé les vecteurs et PRÉSERVE les octets à l'identique.
  2. La borne '\\x1f' n'emporte pas les vecteurs d'une autre photo dont la clé
     a le même préfixe (« a/b/old.jpg » ne touche pas « a/b/old.jpg2 »).
  3. Idempotence : rejoué, renvoie 0 et ne change rien.
  4. rekey_prefix_all déplace tous les kinds en une fois.
  5. Une collision sur l'index UNIQUE échoue bruyamment, sans corruption.

Aucun import lourd (numpy n'est pas requis pour rekey). Lance :
    python test_rekey_vectors.py
"""

import base64
import os
import sqlite3
import sys
import tempfile

from vectors import VectorStore

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def vkey(photo, champ, i):
    return f"{photo}\x1f{champ}\x1f{i}"


def main():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cx = sqlite3.connect(path, isolation_level=None)
    vs = VectorStore(cx)

    old = "Uploads/2019/_A TRIER/IMG_1234.jpg"
    new = "Uploads/2019/IMG_1234.jpg"
    decoy = old + "2"                 # meme prefixe lache, doit rester intact
    other = "Uploads/2020/autre.jpg"

    # deux vecteurs faces + un semantique pour la photo a deplacer
    blobs = {
        vkey(old, "faces", 0): b"\x01\x02" * 130,
        vkey(old, "faces", 1): b"\x03\x04" * 130,
    }
    for k, b in blobs.items():
        vs.put_b64("faces", k, base64.b64encode(b).decode())
    vs.put_b64("semantic", vkey(old, "clip", 0),
               base64.b64encode(b"\x09\x09" * 200).decode())
    # decoys / voisins qui NE doivent PAS bouger
    vs.put_b64("faces", vkey(decoy, "faces", 0),
               base64.b64encode(b"\xAA\xBB" * 130).decode())
    vs.put_b64("faces", vkey(other, "faces", 0),
               base64.b64encode(b"\xCC\xDD" * 130).decode())

    print("1) Re-cle des faces + preservation des octets")
    moved = vs.rekey_prefix("faces", old, new)
    check(moved == 2, f"2 lignes faces re-clees (obtenu {moved})")
    check(vs.get_b64("faces", vkey(old, "faces", 0)) is None,
          "ancienne cle faces#0 absente")
    got0 = vs.get_b64("faces", vkey(new, "faces", 0))
    check(got0 is not None and base64.b64decode(got0) == blobs[vkey(old, "faces", 0)],
          "nouvelle cle faces#0 presente, octets identiques")
    got1 = vs.get_b64("faces", vkey(new, "faces", 1))
    check(got1 is not None and base64.b64decode(got1) == blobs[vkey(old, "faces", 1)],
          "nouvelle cle faces#1 presente, octets identiques")

    print("2) Borne '\\x1f' : le voisin de meme prefixe reste intact")
    check(vs.get_b64("faces", vkey(decoy, "faces", 0)) is not None,
          "IMG_1234.jpg2 NON touche par le deplacement de IMG_1234.jpg")
    check(vs.get_b64("faces", vkey(other, "faces", 0)) is not None,
          "autre.jpg intact")

    print("3) Idempotence")
    again = vs.rekey_prefix("faces", old, new)
    check(again == 0, f"rejoue renvoie 0 (obtenu {again})")

    print("4) rekey_prefix_all deplace tous les kinds")
    # le semantique est encore sous `old`
    total = vs.rekey_prefix_all(old, new)
    check(total == 1, f"1 ligne semantique re-clee par _all (obtenu {total})")
    check(vs.get_b64("semantic", vkey(new, "clip", 0)) is not None,
          "cle semantique deplacee sous le nouveau prefixe")

    print("5) Collision sur l'index UNIQUE -> echec bruyant, sans corruption")
    # prepare une collision : un vecteur existe deja a la cible
    src = "Uploads/src.jpg"
    dst = "Uploads/dst.jpg"
    vs.put_b64("faces", vkey(src, "faces", 0),
               base64.b64encode(b"\x11" * 260).decode())
    vs.put_b64("faces", vkey(dst, "faces", 0),
               base64.b64encode(b"\x22" * 260).decode())
    raised = False
    try:
        vs.rekey_prefix("faces", src, dst)
    except sqlite3.IntegrityError:
        raised = True
    check(raised, "collision leve IntegrityError")
    check(vs.get_b64("faces", vkey(src, "faces", 0)) is not None,
          "apres echec, la source est intacte (pas de corruption partielle)")
    check(vs.get_b64("faces", vkey(dst, "faces", 0)) is not None,
          "apres echec, la cible est intacte")

    cx.close()
    os.unlink(path)

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
