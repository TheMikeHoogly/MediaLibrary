"""Tests de verifier_visages : logique PURE (chemins de cache, classement,
seuils, tableau croise). Aucun torch, aucun photos.db, aucun acces NAS — donc
executable dans le bac a sable. Les fonctions lourdes (detections/analyser/
appliquer) demandent la vraie machine et ne sont pas couvertes ici.

    python test_verifier_visages.py
"""
import hashlib

import verifier_visages as vv


def _check(cond, label):
    print(("  OK  " if cond else "  ECHEC ") + label)
    return bool(cond)


def test_crop_path():
    ok = True
    cle, i, bbox = "2021/ete/IMG_1234.jpg", 2, [10, 20, 110, 140]
    # Formule de reference = EXACTEMENT celle de server.py _serve_facecrop :
    # md5 de « cle|i|bbox », SANS prefixe. Si quelqu'un ajoutait un prefixe
    # (ex. « f| »), le cache ne correspondrait plus et ce test casserait.
    attendu = hashlib.md5(
        f"{cle}|{i}|{bbox}".encode('utf-8', 'replace')).hexdigest() + ".jpg"
    ok &= _check(vv.crop_path(cle, i, bbox).name == attendu,
                 "crop_path = md5(cle|i|bbox) sans prefixe (parite server.py)")
    # Difference avec les animaux : eux prefixent par « a| ». On verifie qu'on
    # n'a PAS ce prefixe (sinon on lirait le mauvais cache).
    anim = hashlib.md5(
        f"a|{cle}|{i}|{bbox}".encode('utf-8', 'replace')).hexdigest() + ".jpg"
    ok &= _check(vv.crop_path(cle, i, bbox).name != anim,
                 "crop_path visage != crop_path animal (pas de prefixe a|)")
    return ok


def test_classer():
    ok = True
    libelles = ["humain A", "animal B", "objet C"]
    codes = ["humain", "animal", "objet"]
    # Le 2e (animal) gagne nettement
    lib, code, sc, mg = vv.classer([0.10, 0.30, 0.05], codes, libelles)
    ok &= _check(code == "animal" and lib == "animal B", "top = plus haute similarite")
    ok &= _check(abs(sc - 0.30) < 1e-9, "score = similarite du gagnant")
    ok &= _check(abs(mg - 0.20) < 1e-9, "marge = ecart avec le 2e")
    # Egalite au sommet -> marge nulle
    _, _, _, mg2 = vv.classer([0.40, 0.40, 0.10], codes, libelles)
    ok &= _check(abs(mg2) < 1e-9, "marge nulle si egalite au sommet")
    return ok


def test_est_nonhumain():
    ok = True
    # Humain n'est JAMAIS ecarte, meme avec un score enorme
    ok &= _check(vv.est_nonhumain("humain", 0.99, 0.99) is False,
                 "un visage humain n'est jamais ecarte")
    # Animal net -> ecarte
    ok &= _check(vv.est_nonhumain("animal", 0.20, 0.05) is True,
                 "animal net -> ecarte")
    # Animal mais marge trop faible -> benefice du doute (non ecarte)
    ok &= _check(vv.est_nonhumain("animal", 0.20, 0.001) is False,
                 "marge insuffisante -> non ecarte")
    # Animal mais score trop faible -> non ecarte
    ok &= _check(vv.est_nonhumain("animal", 0.01, 0.05) is False,
                 "score insuffisant -> non ecarte")
    # Seuil personnalise (balayage) : plus strict -> non ecarte
    ok &= _check(vv.est_nonhumain("objet", 0.06, 0.02, seuil=0.12) is False,
                 "seuil eleve -> non ecarte")
    ok &= _check(vv.est_nonhumain("objet", 0.15, 0.02, seuil=0.12) is True,
                 "au-dessus du seuil eleve -> ecarte")
    return ok


def test_croise_et_suspects():
    ok = True
    # dets = [(cle, i, face, chemin)] ; face porte det_score
    dets = [
        ("a.jpg", 0, {"det_score": 0.9}, "pa"),   # humain
        ("b.jpg", 0, {"det_score": 0.8}, "pb"),   # animal net -> suspect
        ("c.jpg", 0, {"det_score": 0.7}, "pc"),   # animal marge faible -> non
        ("d.jpg", 0, {"det_score": 0.6}, "pd"),   # objet net -> suspect
    ]
    resultats = {
        ("a.jpg", 0): ("humain A", "humain", 0.30, 0.20),
        ("b.jpg", 0): ("animal B", "animal", 0.25, 0.06),
        ("c.jpg", 0): ("animal B", "animal", 0.25, 0.002),
        ("d.jpg", 0): ("objet C", "objet", 0.22, 0.05),
    }
    croise, suspects = vv._croise_et_suspects(dets, resultats)
    ok &= _check(croise["humain"] == 1 and croise["animal"] == 2
                 and croise["objet"] == 1, "tableau croise par code correct")
    cles_susp = {(c, i) for c, i, *_ in suspects}
    ok &= _check(cles_susp == {("b.jpg", 0), ("d.jpg", 0)},
                 "seuls les non-humains NETS sont suspects")
    ok &= _check(("a.jpg", 0) not in cles_susp,
                 "un humain n'est jamais suspect (cout des faux rejets)")
    # det_score reporte (8e element du tuple suspect)
    b = next(s for s in suspects if s[0] == "b.jpg")
    ok &= _check(abs(b[6] - 0.8) < 1e-9, "det_score reporte dans le suspect")
    # Un seuil plus strict reduit les suspects
    _, susp_strict = vv._croise_et_suspects(dets, resultats, seuil=0.24)
    ok &= _check(len(susp_strict) <= len(suspects),
                 "seuil plus strict -> pas plus de suspects")
    return ok


if __name__ == "__main__":
    print("== crop_path ==")
    a = test_crop_path()
    print("== classer ==")
    b = test_classer()
    print("== est_nonhumain ==")
    c = test_est_nonhumain()
    print("== _croise_et_suspects ==")
    d = test_croise_et_suspects()
    print()
    if a and b and c and d:
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
