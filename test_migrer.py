#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test aller-retour de migrer.py (export -> import) sur des dossiers temporaires."""

import shutil
import sys
import tempfile
from pathlib import Path

import migrer as MG

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="migr_"))
    try:
        old = tmp / "ancien"
        new = tmp / "nouveau"
        old.mkdir()
        new.mkdir()
        # etat simule sur l'ancien PC
        (old / "photos.db").write_bytes(b"DB" * 1000)
        (old / "photos.db-wal").write_bytes(b"WAL" * 10)
        (old / "photos.db-shm").write_bytes(b"SHM")
        (old / "lieux.txt").write_text("Bremblens\n", encoding='utf-8')
        (old / "dossiers_a_taguer.txt").write_text("\\\\NAS\\Photos\n", encoding='utf-8')
        (old / "vocabulaire_tags.txt").write_text("chat\nchien\n", encoding='utf-8')
        # un cache (ignore par defaut)
        (old / "face_thumbs").mkdir()
        (old / "face_thumbs" / "a.jpg").write_bytes(b"x" * 50)
        # un fichier NON-etat qui ne doit PAS partir
        (old / "server.py").write_text("code", encoding='utf-8')

        print("1) export (sans caches par defaut)")
        zp = MG.exporter(old, tmp / "mig", avec_caches=False)
        import zipfile
        with zipfile.ZipFile(zp) as z:
            noms = set(z.namelist())
        check('photos.db' in noms and 'photos.db-wal' in noms
              and 'photos.db-shm' in noms, "base + wal + shm dans l'archive")
        check('lieux.txt' in noms and 'vocabulaire_tags.txt' in noms
              and 'dossiers_a_taguer.txt' in noms, "configs dans l'archive")
        check('server.py' not in noms, "le CODE n'est PAS dans l'archive (git s'en charge)")
        check(not any(n.startswith('face_thumbs') for n in noms),
              "caches exclus par defaut")

        print("2) import sur un PC vierge")
        rc = MG.importer(new, zp, force=False)
        check(rc == 0, "import reussi (aucun conflit sur PC vierge)")
        check((new / "photos.db").read_bytes() == (old / "photos.db").read_bytes(),
              "photos.db restauree a l'identique")
        check((new / "lieux.txt").read_text(encoding='utf-8') == "Bremblens\n",
              "lieux.txt restauree")
        check(not (new / "server.py").exists(), "le code n'a pas ete restaure par migrer")

        print("3) import refuse d'ecraser sans --force")
        rc2 = MG.importer(new, zp, force=False)
        check(rc2 == 1, "conflit detecte -> refus sans --force")
        rc3 = MG.importer(new, zp, force=True)
        check(rc3 == 0, "--force autorise l'ecrasement")

        print("4) export avec caches")
        zp2 = MG.exporter(old, tmp / "mig2", avec_caches=True)
        with zipfile.ZipFile(zp2) as z:
            noms2 = set(z.namelist())
        check(any(n.startswith('face_thumbs') for n in noms2),
              "--avec-caches inclut les vignettes")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert — migration de l'etat fidele et sure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
