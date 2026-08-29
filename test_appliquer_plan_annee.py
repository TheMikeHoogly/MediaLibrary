#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test end-to-end de appliquer_plan_annee.py sur une base + un faux systeme de
fichiers TEMPORAIRES (jamais le vrai NAS, jamais la vraie photos.db).

Scenario : un fichier sous « _A TRIER/dump/ » porte un nom humain
« personne:Zoe », un vecteur visage et un vecteur semantique. Le plan le range
vers « <base>/2015/ ». On verifie que l'application :
  - deplace le fichier vers son dossier annee (le cree au besoin),
  - re-cle l'index (tags + faces + semantique suivent le fichier) : aucun nom perdu,
  - REFUSE une collision (dst deja present) sans toucher a la source,
  - est annulable (undo restaure le fichier et l'index),
  - est idempotente (re-appliquer quand src == dst ne casse rien).

Lance : python test_appliquer_plan_annee.py
"""

import base64
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import appliquer_plan_annee as A
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
    tmp = Path(tempfile.mkdtemp(prefix="appliquer_annee_"))
    try:
        nas = tmp / "Photos"
        src = nas / "_A TRIER" / "260211_dump" / "photo.jpg"
        dst = nas / "2015" / "photo.jpg"          # <base=Photos>/2015/
        src.parent.mkdir(parents=True)
        contenu = os.urandom(4096)
        src.write_bytes(contenu)

        db = tmp / "photos.db"
        stores = {t: SqliteStore(db, t)
                  for t in ('tags', 'faces', 'people', 'animals', 'pets')}
        semantic = VectorStore(stores['tags'].cx)

        sk, dk = str(src), str(dst)               # « _A TRIER » = NAS -> cle absolue
        stores['tags'].set(sk, {"kw_fr": ["personne:Zoe"], "desc": "chat", "size": 4096})
        emb = base64.b64encode(os.urandom(260)).decode()
        stores['faces'].set(sk, {"faces": [{"bbox": [1, 2, 3, 4], "emb": emb}], "n": 1})
        semantic.put_b64('photo', sk, base64.b64encode(os.urandom(260)).decode())
        for s in stores.values():
            s.save()

        # move tel que le produirait le generateur (avec new_key correct)
        op = {'key': sk, 'src': sk, 'dst': dk, 'annee': 2015, 'new_key': dk}

        print("1) DRY-RUN ne touche a rien")
        journal = {'operations': []}
        r = A.apply_move(op, stores, semantic, journal, dry=True)
        check(r == 'dry' and src.exists() and not dst.exists(),
              "dry-run : rien deplace")

        print("2) APPLICATION : deplacement + re-cle")
        journal = {'genere_le': 't', 'plan': 'test', 'operations': []}
        gps = {sk: 'Bremblens', 'autre': 'Lausanne'}     # le 7e magasin
        r = A.apply_move(op, stores, semantic, journal, dry=False, gps=gps)
        check(r == 'ok', "op appliquee")
        check(gps.get(dk) == 'Bremblens' and sk not in gps and gps['autre'] == 'Lausanne',
              "libelle de lieu (gps_places) transporte vers dst, les autres intacts")
        check(not src.exists(), "source retiree de _A TRIER")
        check(dst.exists() and dst.read_bytes() == contenu, "fichier dans le dossier annee, octets intacts")
        check(dk in stores['tags'].data and sk not in stores['tags'].data,
              "index tags re-cle src -> dst")
        check('personne:Zoe' in (stores['tags'].data.get(dk, {}).get('kw_fr') or []),
              "nom humain preserve sous la nouvelle cle")
        check(vec_rows(stores['faces'].cx, 'faces', sk) == 0
              and vec_rows(stores['faces'].cx, 'faces', dk) == 1,
              "vecteur visage transporte vers dst")
        check(vec_rows(semantic.cx, 'photo', sk) == 0
              and vec_rows(semantic.cx, 'photo', dk) == 1,
              "vecteur semantique (cle nue) transporte vers dst")

        print("3) COLLISION : dst deja present -> refuse, source intacte")
        src2 = nas / "_A TRIER" / "260211_dump" / "autre.jpg"
        src2.write_bytes(os.urandom(2048))
        occupe = nas / "2016" / "autre.jpg"
        occupe.parent.mkdir(parents=True)
        occupe.write_bytes(os.urandom(2048))       # deja en place, contenu different
        op2 = {'key': str(src2), 'src': str(src2), 'dst': str(occupe),
               'annee': 2016, 'new_key': str(occupe)}
        journal2 = {'operations': []}
        r = A.apply_move(op2, stores, semantic, journal2, dry=False)
        check(r == 'skip' and src2.exists() and not journal2['operations'],
              "collision refusee : source non deplacee, rien journalise")

        print("4) UNDO : restauration fichier + index")
        jp = tmp / "undo.json"
        jp.write_text(json.dumps(journal, ensure_ascii=False), encoding='utf-8')
        A.undo(str(jp), stores, semantic, dry=False, gps=gps)
        check(src.exists() and not dst.exists(), "fichier restaure sous _A TRIER")
        check(gps.get(sk) == 'Bremblens' and dk not in gps,
              "libelle de lieu revenu sous la cle d'origine")
        check(sk in stores['tags'].data and dk not in stores['tags'].data,
              "index tags re-cle dst -> src")
        check(vec_rows(stores['faces'].cx, 'faces', sk) == 1
              and vec_rows(semantic.cx, 'photo', sk) == 1,
              "vecteurs revenus sous la cle d'origine")
        check('personne:Zoe' in (stores['tags'].data.get(sk, {}).get('kw_fr') or []),
              "nom humain conserve apres undo")

        print("5) REPLI new_key absent + idempotence")
        # vieux plan sans new_key : retombe sur str(dst) (== la cle NAS attendue)
        op3 = dict(op)
        op3.pop('new_key')
        journal3 = {'operations': []}
        r = A.apply_move(op3, stores, semantic, journal3, dry=False)
        check(r == 'ok' and dk in stores['tags'].data,
              "sans new_key : re-cle sur str(dst)")
        # re-appliquer le meme op : src a disparu -> skip, aucun degat
        r = A.apply_move(op3, stores, semantic, {'operations': []}, dry=False)
        check(r == 'skip', "re-application : source absente -> skip (idempotent)")

        for s in stores.values():
            s.cx.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("6) GARDE anti-plan-perime : refus d'un plan qui vise la racine")
    # parent du dossier annee
    check(A.parent_du_dossier_annee(r'\\NAS\home\Photos\Photos Mike\2005\x.jpg') == 'Photos Mike',
          "parent : sain (Windows) -> Photos Mike")
    check(A.parent_du_dossier_annee('/nas/Photos/Photos Mike/2005/x.jpg') == 'Photos Mike',
          "parent : sain (Linux) -> Photos Mike")
    check(A.parent_du_dossier_annee(r'\\NAS\home\Photos\2005\x.jpg') == 'Photos',
          "parent : perime -> Photos (racine)")
    sain = [{'dst': r'\\NAS\home\Photos\Photos Mike\2005\x.jpg'},
            {'dst': r'\\NAS\home\Photos\Photos Papa\_SANS_DATE\y.jpg'}]
    perime = [{'dst': r'\\NAS\home\Photos\Photos Mike\2005\x.jpg'},
              {'dst': r'\\NAS\home\Photos\2022\z.jpg'}]
    check(A.plan_vise_la_racine(sain) is None, "plan sain : accepte")
    bad = A.plan_vise_la_racine(perime)
    check(bad and bad.endswith('2022\\z.jpg'), "plan perime : refuse, pointe le fautif")

    print("7) GARDE anti-plan-perime : refus d'un plan plus vieux que le dernier demarrage")
    tmp = Path(tempfile.mkdtemp(prefix='plan_annee_journal_'))
    try:
        j = tmp / 'journal.log'
        j.write_text("bruit\n===== DEMARRAGE 2026-08-29 08:48:05 pid 1 =====\n"
                     "  ligne\n===== DEMARRAGE 2026-08-29 10:51:59 pid 2 =====\n"
                     "  encore\n", encoding='utf-8')
        d = A.dernier_demarrage(j)
        check(d is not None and time.localtime(d)[:6] == (2026, 8, 29, 10, 51, 59),
              "derniere banniere lue (pas la premiere)")
        check(A.plan_perime(d - 1, d), "plan d'avant le demarrage : perime")
        check(not A.plan_perime(d + 1, d), "plan d'apres le demarrage : accepte")
        check(A.dernier_demarrage(tmp / 'absent.log') is None, "journal absent -> None")
        check(not A.plan_perime(0, None), "sans journal : on laisse passer")
        (tmp / 'vide.log').write_text("rien\n", encoding='utf-8')
        check(A.dernier_demarrage(tmp / 'vide.log') is None, "journal sans banniere -> None")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert — rangement par annee reversible, sans perte de nom ni d'empreinte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
