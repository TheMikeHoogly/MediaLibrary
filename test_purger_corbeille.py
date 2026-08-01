#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de purger_corbeille.py sur une fausse corbeille temporaire (jamais le NAS).

Verifie les garde-fous : on ne purge QUE ce qui est assez vieux ET dont la
canonique existe encore ; dry-run inerte ; option --verifier-canon qui refuse si
le contenu de la canonique a change.
"""

import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import purger_corbeille as P

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def jadis(jours):
    return time.strftime('%Y-%m-%d %H:%M:%S',
                         time.localtime(time.time() - jours * 86400))


def groupe(corbeille, nom, date_str, canon_path, sha, avec_manifeste=True):
    g = corbeille / nom
    g.mkdir(parents=True)
    (g / f"aa11_photo_{nom}.jpg").write_bytes(b"x" * 1000)
    if avec_manifeste:
        (g / "manifeste.json").write_text(json.dumps({
            'origine': f'/nas/_A TRIER/{nom}.jpg', 'canonique': str(canon_path),
            'sha256': sha, 'groupe': nom, 'date_application': date_str},
            ensure_ascii=False), encoding='utf-8')
    return g


def main():
    tmp = Path(tempfile.mkdtemp(prefix="purge_"))
    try:
        canon_ok = tmp / "canon_ok.jpg"
        canon_ok.write_bytes(b"CANON")
        sha_ok = hashlib.sha256(b"CANON").hexdigest()
        canon_absent = tmp / "n_existe_pas.jpg"

        corb = tmp / ".corbeille-rangement"
        gA = groupe(corb, "aaaold1", jadis(35), canon_ok, sha_ok)       # vieux, canon ok -> purge
        gB = groupe(corb, "bbbnew1", jadis(5), canon_ok, sha_ok)        # recent -> garde
        gC = groupe(corb, "cccold2", jadis(40), canon_absent, sha_ok)  # canon absente -> garde
        gD = corb / "dddnoman"                                          # sans manifeste -> garde
        gD.mkdir()
        (gD / "aa11_x.jpg").write_bytes(b"y" * 500)

        print("1) DRY-RUN ne supprime rien")
        P.purge(str(corb), jours=30, appliquer=False, verifier_canon=False)
        check(all((corb / n / f).exists()
                  for n, f in [("aaaold1", "aa11_photo_aaaold1.jpg")]),
              "dry-run : le groupe vieux est intact")

        print("2) APPLICATION : seul le vieux avec canonique presente est purge")
        P.purge(str(corb), jours=30, appliquer=True, verifier_canon=False)
        check(not gA.exists(), "groupe vieux + canonique OK : purge (dossier retire)")
        check(gB.exists(), "groupe recent : garde")
        check(gC.exists(), "groupe canonique absente : GARDE (anti-perte)")
        check(gD.exists(), "groupe sans manifeste : GARDE")

        print("3) --verifier-canon refuse si le contenu de la canonique a change")
        corb2 = tmp / "corb2"
        canon_modif = tmp / "canon_modif.jpg"
        canon_modif.write_bytes(b"AVANT")
        sha_avant = hashlib.sha256(b"AVANT").hexdigest()
        gE = groupe(corb2, "eeeold3", jadis(35), canon_modif, sha_avant)
        canon_modif.write_bytes(b"APRES-modifie")     # le contenu a change depuis
        P.purge(str(corb2), jours=30, appliquer=True, verifier_canon=True)
        check(gE.exists(),
              "canonique existante mais sha != manifeste : GARDE (verif au bit pres)")

        # sans --verifier-canon, l'existence suffit : purge
        canon_modif2 = tmp / "canon2.jpg"
        canon_modif2.write_bytes(b"PEU IMPORTE")
        corb3 = tmp / "corb3"
        gF = groupe(corb3, "ffford4", jadis(35), canon_modif2,
                    "sha_qui_ne_correspond_pas")
        P.purge(str(corb3), jours=30, appliquer=True, verifier_canon=False)
        check(not gF.exists(),
              "sans --verifier-canon : existence de la canonique suffit -> purge")

        for s in (canon_ok,):
            pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert — purge prudente : delai, canonique verifiee, dry-run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
