#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests du coeur deterministe de renommage (renommage.py). Stdlib pure, aucune
mutation. Lance :  python test_renommage.py

Couvre : repli ASCII (accents, ligatures œ/æ/ø/ß), slug (chars interdits,
ponctuation, tirets), champs (date, lieu/type par confiance, sujet noms
multiples / description), assemblage (format, champs vides, plafond + troncature
sur frontiere de mot, nom reserve Windows, extension), suffixe de collision,
idempotence, et les deux exemples de la spec. En bonus, si photos.db est present
a cote, un dry-run verifie que de VRAIS noms humains accentues produisent des
slugs ASCII surs (aucune ecriture)."""

import re
import sys
from pathlib import Path

import renommage as R

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def eq(got, want, msg):
    check(got == want, f"{msg} -> {got!r} (attendu {want!r})")


def main():
    print("1) repli ASCII")
    eq(R.to_ascii("Dévi"), "Devi", "accent simple")
    eq(R.to_ascii("Zürich"), "Zurich", "trema")
    eq(R.to_ascii("cœur"), "coeur", "ligature oe")
    eq(R.to_ascii("æther"), "aether", "ligature ae")
    eq(R.to_ascii("Smørrebrød"), "Smorrebrod", "o barre")
    eq(R.to_ascii("Straße"), "Strasse", "eszett")

    print("2) slug_field")
    eq(R.slug_field("Claudia Binaki"), "Claudia-Binaki", "espace -> tiret")
    eq(R.slug_field('a/b:c*?d"e'), "a-b-c-d-e", "chars Windows interdits")
    eq(R.slug_field("  trop   d'espaces  "), "trop-d-espaces", "espaces multiples")
    eq(R.slug_field("Lac au Couchant", lower=True), "lac-au-couchant", "minuscule")
    eq(R.slug_field("---bord---"), "bord", "pas de tiret en bord")
    eq(R.slug_field(""), "", "vide")
    eq(R.slug_field("café-crème"), "cafe-creme", "accents + tiret conserve")

    print("3) field_date")
    eq(R.field_date("20190704"), "20190704", "8 chiffres")
    eq(R.field_date("2019"), "00000000", "trop court -> zeros")
    eq(R.field_date(None), "00000000", "None -> zeros")
    eq(R.field_date("2019-07-04"), "00000000", "non purement numerique -> zeros")

    print("4) field_place_or_type (ordre de confiance, minuscule)")
    eq(R.field_place_or_type(gps_place="Bremblens", path_place="Lausanne"),
       "bremblens", "GPS prioritaire sur chemin")
    eq(R.field_place_or_type(path_place="Chez Mamie", human_place="Ici"),
       "chez-mamie", "chemin prioritaire sur tag humain")
    eq(R.field_place_or_type(image_type="Paysage"), "paysage", "type en repli")
    eq(R.field_place_or_type(), "", "rien -> vide")

    print("5) field_subject")
    eq(R.field_subject(names=["Luna"]), "Luna", "un nom, casse conservee")
    eq(R.field_subject(names=["Mike", "Flo"]), "Flo-et-Mike",
       "deux noms : tries + -et- (determinisme ; spec illustrait Mike-et-Flo)")
    eq(R.field_subject(names=["Luna", "luna", "LUNA"]), "Luna", "doublons casse-insensibles")
    eq(R.field_subject(names=["A", "B", "C", "D"]), "A-et-B-et-C-et-et-al",
       "plus de 3 noms -> et-al")
    eq(R.field_subject(description="Un lac au couchant"), "un-lac-au-couchant",
       "repli description en minuscule")
    eq(R.field_subject(names=["Luna"], description="ignore"), "Luna",
       "les noms priment sur la description")

    print("6) assemble (format, champs vides, extension)")
    eq(R.assemble("20190704", "bremblens", "Luna", "JPG"),
       "20190704_bremblens_Luna.jpg", "format complet + ext normalisee")
    eq(R.assemble("20190704", "", "Luna", "jpg"), "20190704_Luna.jpg",
       "lieu vide : pas de double underscore")
    eq(R.assemble("00000000", "", "", "jpg"), "00000000.jpg",
       "ni lieu ni sujet : au moins la date")
    eq(R.assemble("bad", "paysage", "x", "png"), "00000000_paysage_x.png",
       "date invalide -> 00000000")

    print("7) plafond + troncature sur frontiere de mot")
    long_sujet = "-".join(["mot"] * 60)          # 240 caracteres
    out = R.assemble("20190704", "lieu", long_sujet, "jpg", max_len=120)
    check(len(out) <= 120, f"nom <= 120 ({len(out)})")
    check(out.startswith("20190704_lieu_"), "date + lieu preserves")
    check(out.endswith(".jpg"), "extension preservee")
    check("-mot-mot.jpg" not in out or out.count("mot") < 60, "sujet tronque")
    check(not out[:-4].endswith("-"), "pas de tiret en fin de radical (frontiere de mot)")

    print("8) nom reserve Windows neutralise")
    eq(R._avoid_reserved("CON"), "_CON", "CON prefixe")
    eq(R._avoid_reserved("com1"), "_com1", "com1 (insensible casse)")
    eq(R._avoid_reserved("Console"), "Console", "Console non reserve")

    print("9) suffixe de collision (stable, avant l'extension)")
    a = R.collision_suffix("20190704_bremblens_Luna.jpg", seed="/chemin/a.jpg")
    b = R.collision_suffix("20190704_bremblens_Luna.jpg", seed="/chemin/a.jpg")
    c = R.collision_suffix("20190704_bremblens_Luna.jpg", seed="/chemin/b.jpg")
    eq(a, b, "meme graine -> meme suffixe (deterministe)")
    check(a != c, "graine differente -> suffixe different")
    check(re.fullmatch(r"20190704_bremblens_Luna-[0-9a-f]{4}\.jpg", a) is not None,
          f"forme -<4 hex> avant ext ({a})")

    print("10) idempotence")
    check(R.is_already_renamed("20190704_bremblens_Luna.jpg", provenance_seen=True),
          "deja au format + provenance -> True")
    check(not R.is_already_renamed("20190704_bremblens_Luna.jpg", provenance_seen=False),
          "format seul sans provenance -> False (photo appareil 20190704_...)")
    check(not R.is_already_renamed("IMG_1234.jpg", provenance_seen=True),
          "pas au format -> False")

    print("11) propose_basename : exemples de la spec")
    ex1 = R.propose_basename({
        "date8": "20190704", "gps_place": "Bremblens",
        "names": ["personne:Luna"], "ext": "jpg"})
    eq(ex1, "20190704_bremblens_Luna.jpg", "Luna a Bremblens")
    ex2 = R.propose_basename({
        "date8": "20190704", "image_type": "paysage",
        "description": "lac au couchant", "ext": "jpg"})
    eq(ex2, "20190704_paysage_lac-au-couchant.jpg", "paysage sans nom")
    # prefixe personne:/animal: depouille + collision
    taken = {"20190704_bremblens_Luna.jpg"}
    ex3 = R.propose_basename({
        "date8": "20190704", "gps_place": "Bremblens",
        "names": ["animal:Luna"], "ext": "jpg", "seed": "/NAS/vieux/IMG.jpg"},
        taken=taken)
    check(ex3 != "20190704_bremblens_Luna.jpg" and ex3.startswith("20190704_bremblens_Luna-"),
          f"collision -> suffixe ({ex3})")

    print("12) jamais de nom vide")
    ex4 = R.propose_basename({"ext": "mov"})   # aucun fait
    eq(ex4, "00000000.mov", "sans aucun fait : date zero + ext")

    dry_run_real()

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) fausse(s)")
        return 1
    print("Tout est vert — le coeur de renommage assemble et assainit correctement.")
    return 0


def dry_run_real():
    """Bonus : slugs de VRAIS noms humains de la base (aucune ecriture)."""
    db = Path(__file__).resolve().parent / "photos.db"
    if not db.exists():
        print("13) dry-run reel : photos.db absent, saute.")
        return
    import json
    import shutil
    import sqlite3
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="renom_dry_"))
    try:
        shutil.copy2(db, tmp / "photos.db")
        cx = sqlite3.connect(str(tmp / "photos.db"))
        noms = set()
        for (v,) in cx.execute("SELECT v FROM tags LIMIT 4000"):
            try:
                e = json.loads(v)
            except Exception:
                continue
            for fld in ("kw_fr", "kw_en"):
                for t in e.get(fld) or []:
                    if isinstance(t, str) and (t.startswith("personne:")
                                               or t.startswith("animal:")):
                        noms.add(t)
        cx.close()
        print(f"13) dry-run reel : {len(noms)} nom(s) humain(s) distincts (echantillon)")
        bad = 0
        exemples = []
        for t in sorted(noms):
            brut = t.split(":", 1)[1]
            sl = R.slug_field(brut, lower=False)
            safe = sl.isascii() and not (set(sl) & R._FORBIDDEN) and "  " not in sl
            if not safe:
                bad += 1
            if brut != sl and len(exemples) < 8:
                exemples.append(f"{brut!r}->{sl!r}")
        for ex in exemples:
            print("     " + ex)
        check(bad == 0, f"tous les slugs de noms reels sont ASCII et surs ({len(noms)} testes)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
