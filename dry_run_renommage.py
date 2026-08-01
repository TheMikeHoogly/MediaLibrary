#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DRY-RUN du renommage intelligent sur `_Uploads` — AUCUNE mutation.

Montre concretement quels noms le pipeline PROPOSERAIT pour les photos deja
dans l'index sous `_Uploads`, en assemblant les faits (resolveur `renommage_facts`)
et le nom (coeur `renommage`). C'est ce que Mike relira AVANT d'activer
l'application reelle (qui, elle, renomme sur le NAS + re-cle + provenance et
attend la fin du recensement).

Lecture seule : copie photos.db en /tmp, ne lit que l'index et lieux.txt.
Lance :  python dry_run_renommage.py [N]      (N = taille d'echantillon, defaut 40)
"""

import json
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

import renommage as R
import renommage_facts as RF

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def sanity_asserts():
    """Quelques verifications synthetiques du resolveur (pas de base requise)."""
    print("=== sanity resolve_facts (synthetique) ===")
    # date + HEURE dans le nom
    f = RF.resolve_facts("x/_Uploads/IMG_20190704_123045.jpg",
                         {"desc": "plage"}, lieux={})
    check(f["date8"] == "20190704-123045" and f["_date_precision"] == "exact",
          f"date+heure depuis le nom -> {f['date8']} ({f['_date_precision']})")
    check(R.propose_basename(f) == "20190704-123045_plage.jpg",
          f"nom sans lieu ni personne -> {R.propose_basename(f)}")
    # annee du dossier seule
    f = RF.resolve_facts("\\\\NAS\\Photos\\2011\\scan042.jpg", {}, lieux={})
    check(f["date8"] == "20110000" and f["_date_precision"] == "annee",
          f"annee du dossier -> {f['date8']} ({f['_date_precision']})")
    # lieu deduit du chemin + nom humain
    lieux = {"bremblens": "Bremblens"}
    f = RF.resolve_facts(
        "\\\\NAS\\Photos\\Appart Bremblens\\IMG_20190704_1.jpg",
        {"kw_fr": ["personne:Luna", "chat"]}, lieux=lieux)
    check(f["path_place"] == "Bremblens", f"lieu du chemin -> {f['path_place']}")
    check(R.propose_basename(f) == "20190704_bremblens_Luna.jpg",
          f"assemblage complet -> {R.propose_basename(f)}")
    print()


def is_upload_key(key):
    kl = key.lower()
    if "_uploads" in kl or "/uploads/" in kl.replace("\\", "/"):
        return True
    # cles relatives d'upload-dossier (point 17) : « ARZOPA/xxx.jpg », pas de
    # prefixe NAS ni de lettre de lecteur.
    return ("/" in key) and ("\\" not in key) and (":" not in key)


def main():
    n_ech = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    sanity_asserts()

    here = Path(__file__).resolve().parent
    db = here / "photos.db"
    if not db.exists():
        print("photos.db absent : dry-run reel saute (sanity seul).")
        return 1 if FAIL else 0

    tmp = Path(tempfile.mkdtemp(prefix="dry_renom_"))
    try:
        shutil.copy2(db, tmp / "photos.db")
        lieux = RF.load_lieux(here / "lieux.txt")
        print(f"=== dry-run reel : {len(lieux)} lieu(x) connus (lieux.txt) ===")
        cx = sqlite3.connect(str(tmp / "photos.db"))

        rows = []
        for k, v in cx.execute("SELECT k, v FROM tags"):
            if not is_upload_key(k):
                continue
            try:
                e = json.loads(v)
            except Exception:
                e = {}
            rows.append((k, e))
        cx.close()

        print(f"Photos sous _Uploads dans l'index : {len(rows)}")
        if not rows:
            print("(aucune — rien a proposer)")
            return 1 if FAIL else 0

        # statistiques + collisions (par dossier cible = meme prefixe de repertoire)
        prec = Counter()
        with_name = with_place = already = 0
        taken_by_dir = {}          # dir -> set(noms proposes) pour detecter collisions
        collisions = 0
        exemples = []

        for k, e in rows:
            facts = RF.resolve_facts(k, e, lieux=lieux)
            prec[facts["_date_precision"]] += 1
            if facts["names"]:
                with_name += 1
            if facts["path_place"]:
                with_place += 1
            base = _basename(k)
            if R._DATE8_RE.match(base):     # candidat « deja au format »
                already += 1
            proposed = R.propose_basename(facts)
            d = k.replace("/", "\\").rsplit("\\", 1)[0]
            taken = taken_by_dir.setdefault(d, set())
            if proposed in taken:
                collisions += 1
                proposed2 = R.propose_basename(facts, taken=taken)
                proposed = proposed2
            taken.add(proposed)
            if len(exemples) < n_ech:
                exemples.append((base, proposed, facts["_date_precision"]))

        print()
        print("--- echantillon (nom actuel  ->  nom propose  [precision date]) ---")
        for old, new, p in exemples:
            print(f"  {old}")
            print(f"    -> {new}   [{p}]")

        print()
        print("--- synthese ---")
        print(f"  total _Uploads indexes : {len(rows)}")
        print(f"  avec nom humain        : {with_name}")
        print(f"  avec lieu (chemin)     : {with_place}")
        print(f"  date : exact={prec['exact']}  annee={prec['annee']}  "
              f"aucune={prec['aucune']}")
        print(f"  deja au format ^d8_    : {already}  (candidats a sauter si "
              f"provenance)")
        print(f"  collisions de nom      : {collisions}  (resolues par suffixe "
              f"-<4hex>)")
        print()
        print("Rappel : AUCUNE ecriture. Le champ 'lieu' n'utilise pas encore le")
        print("GPS inverse ni le type SigLIP (branches cote serveur a l'application).")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return 1 if FAIL else 0


def _basename(key):
    return key.replace("/", "\\").split("\\")[-1]


if __name__ == "__main__":
    sys.exit(main())
