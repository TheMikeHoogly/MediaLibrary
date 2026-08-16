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


def test_basename_cle():
    ok = True
    ok &= _check(vo.basename_cle("ads\\ARZOPA\\5bBcn6-x.JPG") == "5bbcn6-x.jpg",
                 "antislash Windows + minuscules")
    ok &= _check(vo.basename_cle("ARZOPA/5bBcn6-x.JPG") == "5bbcn6-x.jpg",
                 "slash avant + minuscules (meme basename que la vraie cle)")
    ok &= _check(vo.basename_cle("photo.png") == "photo.png", "nom simple")
    ok &= _check(vo.basename_cle("dossier/") == "dossier",
                 "slash final ignore")
    return ok


def test_est_fantome():
    ok = True
    # La vraie cle « ads\ARZOPA\5bBcn6-x.JPG » est presente -> son basename l'est.
    presents = {"5bbcn6-x.jpg", "autre.png"}
    # La cle malformee « ARZOPA/5bBcn6-x.JPG » est orpheline MAIS fantome : meme
    # basename qu'un present -> purge sans risque (la photo existe ailleurs).
    ok &= _check(vo.est_fantome("ARZOPA/5bBcn6-x.JPG", presents) is True,
                 "doublon malforme d'une cle presente -> FANTOME")
    # Un fichier vraiment disparu : aucun present ne partage son basename.
    ok &= _check(vo.est_fantome("ads\\VieuxDossier\\disparu.jpg", presents) is False,
                 "aucun sibling present -> vrai disparu")
    ok &= _check(vo.est_fantome("x.jpg", set()) is False,
                 "ensemble vide -> jamais fantome")
    return ok


def test_cles_fantomes_par_collision():
    ok = True
    # Cas ARZOPA : la vraie cle se resout, la malformee non, meme basename.
    keys = [
        "ads\\ARZOPA\\5bBcn6-x.JPG",   # presente
        "ARZOPA/5bBcn6-x.JPG",          # FANTOME (meme basename, absente)
        "ads\\autre\\photo.png",       # presente, unique -> ignoree
    ]
    present = {"ads\\ARZOPA\\5bBcn6-x.JPG", "ads\\autre\\photo.png"}
    est_fichier = lambda k: k in present
    r = vo.cles_fantomes_par_collision(keys, est_fichier)
    ok &= _check(r == ["ARZOPA/5bBcn6-x.JPG"], "isole le doublon malforme absent")

    # Garde-fou : une cle nommee n'est jamais purgee, meme fantome.
    r2 = vo.cles_fantomes_par_collision(keys, est_fichier,
                                        named={"ARZOPA/5bBcn6-x.JPG"})
    ok &= _check(r2 == [], "cle nommee jamais purgee")

    # Basename unique (pas de collision) -> jamais fantome, meme si absent.
    r3 = vo.cles_fantomes_par_collision(["seul/absent.jpg"], lambda k: False)
    ok &= _check(r3 == [], "sans collision -> rien (vrai disparu, pas fantome)")

    # Collision mais TOUTES absentes -> aucune n'est presente -> rien a purger
    # (on ne sait pas laquelle est la bonne : ce sont des disparus, pas des doublons).
    r4 = vo.cles_fantomes_par_collision(["a/x.jpg", "b/x.jpg"], lambda k: False)
    ok &= _check(r4 == [], "collision toutes absentes -> rien (prudence)")
    return ok


def test_orphelins_vecteurs():
    ok = True
    lignes = [
        ("photo", "a.jpg"), ("photo", "b.jpg"), ("photo", "disparue.jpg"),
        ("faces", "a.jpgfaces0"), ("faces", "b.jpgfaces1"),
        ("people", "Mikerefs0"),
    ]
    tags = {"a.jpg", "b.jpg"}
    par_kind, orph, ech = vo.orphelins_vecteurs(lignes, tags)

    ok &= _check(par_kind == {"photo": 3, "faces": 2, "people": 1},
                 "compte par kind")
    ok &= _check(orph == {"photo": 1}, "seul le kind photo est compare")
    ok &= _check(ech == ["disparue.jpg"], "echantillon = la cle absente")

    # LE piege : comparer TOUS les kinds annonce des orphelins qui n'en sont
    # pas. Les cles faces/people sont COMPOSEES, elles ne sont pas des cles de
    # photo. Verifie le 15/08 : 86 181 faux orphelins sur la vraie base.
    _, faux, _ = vo.orphelins_vecteurs(
        lignes, tags, kinds=("photo", "faces", "people"))
    ok &= _check(sum(faux.values()) == 4,
                 "sans le garde de kind : 3 faux orphelins de plus")

    # Base vide de vecteurs : aucun orphelin, pas une exception.
    ok &= _check(vo.orphelins_vecteurs([], tags) == ({}, {}, []),
                 "aucun vecteur -> aucun orphelin")

    # Aucune cle dans tags (base neuve) : tous les vecteurs photo sont
    # orphelins — c'est vrai, et c'est ce qu'il faut dire.
    _, tous, _ = vo.orphelins_vecteurs(lignes, set())
    ok &= _check(tous == {"photo": 3}, "tags vide -> tous les photo orphelins")

    # L'echantillon est BORNE : un diagnostic ne deverse pas 2 374 lignes.
    beaucoup = [("photo", f"x{i}.jpg") for i in range(50)]
    _, _, e2 = vo.orphelins_vecteurs(beaucoup, set(), taille_echantillon=3)
    ok &= _check(len(e2) == 3, "echantillon borne")
    return ok


if __name__ == "__main__":
    print("== noms_humains ==")
    a = test_noms_humains()
    print("== statut ==")
    b = test_statut()
    print("== resoudre ==")
    c = test_resoudre()
    print("== basename_cle ==")
    d = test_basename_cle()
    print("== est_fantome ==")
    e = test_est_fantome()
    print("== cles_fantomes_par_collision ==")
    f = test_cles_fantomes_par_collision()
    print("== orphelins_vecteurs ==")
    g = test_orphelins_vecteurs()
    print()
    if a and b and c and d and e and f and g:
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
