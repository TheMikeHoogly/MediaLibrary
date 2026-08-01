#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test end-to-end de appliquer_plan.py sur une base + un faux systeme de fichiers
TEMPORAIRES (jamais le vrai NAS, jamais la vraie photos.db).

Scenario : deux fichiers IDENTIQUES — canonique (dossier annee) et doublon
(_A TRIER). Le doublon porte un nom humain « personne:Zoe » ABSENT de la
canonique, plus un vecteur visage et un vecteur semantique. On verifie que
l'application :
  - fusionne le nom dans la canonique AVANT de retirer,
  - deplace le doublon en quarantaine (jamais de rm), avec manifeste,
  - re-cle l'index (tags + faces + semantique suivent le fichier),
  - est annulable (undo restaure le fichier et l'index).

Lance : python test_appliquer_plan.py
"""

import base64
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import appliquer_plan as A
from store_sqlite import SqliteStore
from vectors import VectorStore

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def vec_rows(cx, kind, prefix):
    return cx.execute(
        "SELECT count(*) FROM vectors WHERE kind=? AND (k=? OR (k>=? AND k<?))",
        (kind, prefix, prefix + "\x1f", prefix + "\x1f" + "￿")).fetchone()[0]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="appliquer_"))
    try:
        nas = tmp / "Photos"
        canon = nas / "2015" / "photo.jpg"
        dup = nas / "_A TRIER" / "260211_dump" / "photo.jpg"
        canon.parent.mkdir(parents=True)
        dup.parent.mkdir(parents=True)
        contenu = os.urandom(4096)
        canon.write_bytes(contenu)
        dup.write_bytes(contenu)                 # IDENTIQUE
        sha = A.sha256(dup)

        db = tmp / "photos.db"
        stores = {t: SqliteStore(db, t)
                  for t in ('tags', 'faces', 'people', 'animals', 'pets')}
        semantic = VectorStore(stores['tags'].cx)

        ck, dk = str(canon), str(dup)
        stores['tags'].set(ck, {"kw_fr": [], "desc": "poisson", "size": 4096})
        stores['tags'].set(dk, {"kw_fr": ["personne:Zoe"], "desc": "poisson",
                                "size": 4096})
        emb = base64.b64encode(os.urandom(260)).decode()
        stores['faces'].set(dk, {"faces": [{"bbox": [1, 2, 3, 4], "emb": emb}],
                                 "n": 1})
        semantic.put_b64('photo', dk, base64.b64encode(os.urandom(260)).decode())
        for s in stores.values():
            s.save()

        sha8 = sha[:8]
        dst = str(nas / ".corbeille-rangement" / sha8 / "photo.jpg")
        op = {
            'id': 'q0001', 'type': 'quarantine', 'src': dk, 'dst': dst,
            'raison': 'test', 'fusion_noms': ['personne:Zoe'],
            'preuve': {'sha256': sha, 'taille': 4096, 'canonique': ck,
                       'n_copies': 2},
            'manifeste': {'groupe': sha8, 'origine': dk, 'canonique': ck,
                          'date_plan': 't'},
        }

        print("1) DRY-RUN ne touche a rien")
        journal = {'operations': []}
        r = A.apply_quarantine(op, stores, semantic, journal, verify=True, dry=True)
        check(r == 'dry' and dup.exists() and not Path(dst).exists(),
              "dry-run : rien deplace")

        print("2) APPLICATION : fusion + deplacement + re-cle")
        journal = {'genere_le': 't', 'plan': 'test', 'operations': []}
        r = A.apply_quarantine(op, stores, semantic, journal, verify=True, dry=False)
        check(r == 'ok', "op appliquee")
        check(not dup.exists(), "source retiree de son emplacement")
        check(Path(dst).exists(), "copie presente en quarantaine")
        check((Path(dst).parent / 'manifeste.json').exists(), "manifeste ecrit")
        check(Path(dst).read_bytes() == contenu, "octets du fichier intacts")
        check('personne:Zoe' in (stores['tags'].data.get(ck, {}).get('kw_fr') or []),
              "nom fusionne dans la canonique AVANT retrait")
        check(dk not in stores['tags'].data and dst in stores['tags'].data,
              "index tags re-cle src -> dst")
        check(vec_rows(stores['faces'].cx, 'faces', dk) == 0
              and vec_rows(stores['faces'].cx, 'faces', dst) == 1,
              "vecteur visage transporte vers dst")
        check(vec_rows(semantic.cx, 'photo', dk) == 0
              and vec_rows(semantic.cx, 'photo', dst) == 1,
              "vecteur semantique (cle nue) transporte vers dst")
        check(canon.exists() and canon.read_bytes() == contenu,
              "canonique intacte")

        jp = tmp / "undo.json"
        jp.write_text(json.dumps(journal, ensure_ascii=False), encoding='utf-8')

        print("3) UNDO : restauration fichier + index")
        A.undo(str(jp), stores, semantic, dry=False)
        check(dup.exists() and not Path(dst).exists(), "fichier restaure a l'origine")
        check(dk in stores['tags'].data and dst not in stores['tags'].data,
              "index tags re-cle dst -> src")
        check(vec_rows(stores['faces'].cx, 'faces', dk) == 1
              and vec_rows(semantic.cx, 'photo', dk) == 1,
              "vecteurs revenus sous la cle d'origine")
        check('personne:Zoe' in (stores['tags'].data.get(ck, {}).get('kw_fr') or []),
              "nom fusionne CONSERVE apres undo (fusion additive, non defaite)")

        for s in stores.values():
            s.cx.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert — application reversible, sans perte de nom ni d'empreinte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
