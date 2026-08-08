"""Tests de verifier_orphelins : logique PURE (detection des noms humains,
statut orphelin/present/indetermine, resolution de cle). Aucun sqlite, aucun
NAS — executable dans le bac a sable.

    python test_verifier_orphelins.py
"""
from pathlib import Path

import verifier_orphelins as vo


def _check(cond, label):
    print(("  OK  " if cond else "  ECHEC ") + label)
    return bool(cond)


def test_noms_humains():
    ok = True
    ok &= _check(vo.noms_humains(["chat", "personne:Mike"]) == {"personne"},
                 "detecte personne:")
    ok &= _check(vo.noms_humains(["animal:Luna", "jardin"]) == {"animal"},
                 "detecte animal:")
    ok &= _check(vo.noms_humains(["personne:Flo", "animal:Inti"])
                 == {"personne", "animal"}, "detecte les deux")
    ok &= _check(vo.noms_humains(["chat", "jardin"]) == set(),
                 "aucun nom -> vide")
    ok &= _check(vo.noms_humains(None) == set(), "None gere")
    # Casse : personne:Nom en casse melangee reste detecte (compare en minuscules)
    ok &= _check(vo.noms_humains(["Personne:Mike"]) == {"personne"},
                 "casse melangee detectee")
    return ok


def test_statut():
    ok = True
    ok &= _check(vo.statut(True, True) == "present", "joignable + existe -> present")
    ok &= _check(vo.statut(True, False) == "orphelin",
                 "joignable + absent -> orphelin")
    ok &= _check(vo.statut(False, False) == "indetermine",
                 "injoignable -> indetermine (jamais orphelin a tort)")
    ok &= _check(vo.statut(False, True) == "indetermine",
                 "injoignable prime, meme si existe")
    return ok


def test_resoudre():
    ok = True
    up = Path(r"\\nas\home\Uploads")
    # Cle relative -> sous Uploads
    r = vo.resoudre("ARZOPA/E41aNC-x.jpg", up)
    ok &= _check(r == up / "ARZOPA/E41aNC-x.jpg", "cle relative -> sous Uploads")
    # Cle absolue (POSIX) -> telle quelle
    ra = vo.resoudre("/mnt/photos/a.jpg", up)
    ok &= _check(ra == Path("/mnt/photos/a.jpg"), "cle absolue POSIX -> telle quelle")
    return ok


if __name__ == "__main__":
    print("== noms_humains ==")
    a = test_noms_humains()
    print("== statut ==")
    b = test_statut()
    print("== resoudre ==")
    c = test_resoudre()
    print()
    if a and b and c:
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
