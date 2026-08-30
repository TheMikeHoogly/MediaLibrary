#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test de la regle pure d'elargissement FR->EN (co-occurrence du tagueur).
Lance : python test_elargissement_fr_en.py"""
import sys

import elargissement_fr_en as E

FAIL = []


def check(cond, msg):
    print(("  OK  " if cond else "  FAIL") + " " + msg)
    if not cond:
        FAIL.append(msg)


def main():
    photos = []
    for _ in range(5):
        photos.append({"kw_fr": ["ours en peluche", "enfant", "chambre"], "kw_en": ["teddy bear", "child", "bedroom"]})
    for _ in range(4):
        photos.append({"kw_fr": ["chat", "canapé", "table"], "kw_en": ["cat", "sofa", "table"]})
    photos.append({"kw_fr": ["chat", "roche"], "kw_en": ["cat", "rock", "outdoor"]})
    photos.append({"kw_fr": ["chat", "jardin"], "kw_en": ["cat", "garden", "outdoor"]})
    photos.append({"kw_fr": ["sol"], "kw_en": ["ground"]})           # une seule fois : sous le minimum
    photos.append({"failed": True, "kw_fr": ["x"], "kw_en": ["y"]})
    photos.append({"kw_fr": ["personne:Mike", "plage"], "kw_en": ["beach"]})
    photos.append({"kw_fr": ["personne:Mike", "plage"], "kw_en": ["beach"]})
    photos.append({"kw_fr": ["personne:Mike", "plage"], "kw_en": ["beach"]})
    d = E.Dictionnaire(photos)
    check(d.n_photos == 15, "photos apprises : les entrees a deux langues, sans la ratee")
    check(d.fr_en.get("ours en peluche") == "teddy bear" and d.fr_en.get("chat") == "cat"
          and d.fr_en.get("canapé") == "sofa" and d.fr_en.get("plage") == "beach",
          "paires serrees apprises")
    check("table" not in d.fr_en, "un mot identique dans les deux langues n est pas une traduction")
    check("sol" not in d.fr_en and "roche" not in d.fr_en, "sous le minimum d occurrences : rien d appris")
    check("personne:mike" not in d.fr_en, "les noms ne sont jamais appris")
    check(d.traduire("ours en peluche") == "teddy bear", "phrase entiere")
    check(d.traduire("Ours en Peluche ") == "teddy bear", "insensible a la casse et aux espaces")
    check(d.traduire("chat sur un canapé") == "cat sur un sofa", "mot a mot : les inconnus et les mots-outils restent")
    check(d.traduire("montagne") is None, "rien de connu : None (l appelant encode la requete seule)")
    check(d.traduire("table") is None, "un mot identique des deux cotes ne s elargit pas")
    check(d.traduire("") is None and d.traduire("   ") is None, "vide : None")
    check(E.formes(d, "chat") == ["chat", "cat"] and E.formes(d, "montagne") == ["montagne"]
          and E.formes(None, "chat") == ["chat"], "formes : [fr, en] ou [fr] ; sans dictionnaire, [fr]")
    d2 = E.Dictionnaire({"a": photos[0], "b": photos[1]}, minimum=1)
    check(d2.traduire("enfant") == "child", "un dict {cle: entree} s apprend aussi")
    print()
    if FAIL:
        print("ECHEC : %d assertion(s) fausse(s)" % len(FAIL))
        return 1
    print("Tout est vert - l elargissement FR->EN est une regle pure et sobre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
