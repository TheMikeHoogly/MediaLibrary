#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du re-clage de l'echantillon fige (banc 3b). Pur : ni base, ni serveur.

Style aligne sur test_verifier_orphelins.py : un compteur, pas de framework.
"""
import recler_echantillon as re_


def _check(cond, label):
    print(f"  {'OK ' if cond else 'ECHEC'} {label}")
    return bool(cond)


AVANT = "\\\\NAS\\home\\Photos\\_A TRIER\\250914_Samsung\\20250730_151021.jpg"
APRES = "\\\\NAS\\home\\Photos\\2025\\20250730_151021.jpg"


def test_nom_de_fichier():
    ok = True
    ok &= _check(re_.nom_de_fichier(AVANT) == "20250730_151021.jpg",
                 "antislashs Windows")
    ok &= _check(re_.nom_de_fichier("ARZOPA/a.JPG") == "a.jpg",
                 "slashs et minuscules")
    ok &= _check(re_.nom_de_fichier("seul.jpg") == "seul.jpg",
                 "nom sans dossier")
    return ok


def test_recle_le_jumeau_unique():
    ech = {AVANT: "riche"}
    nouveau, rap = re_.recler(ech, [APRES, "\\\\NAS\\autre.jpg"])
    ok = _check(nouveau == {APRES: "riche"}, "cle suivie, STRATE conservee")
    ok &= _check(rap["reclees"] == [(AVANT, APRES)], "rapport de re-cle")
    ok &= _check(not rap["ambigues"] and not rap["perdues"], "rien d autre")
    return ok


def test_cle_encore_valide_intacte():
    ech = {APRES: "piege"}
    nouveau, rap = re_.recler(ech, [APRES])
    ok = _check(nouveau == ech, "une cle vivante n est pas touchee")
    ok &= _check(rap["vivantes"] == [APRES] and not rap["reclees"],
                 "comptee comme vivante, pas comme re-clee")
    return ok


def test_jumeaux_multiples_jamais_devines():
    """LE point du script. Deux candidats -> on ne choisit pas.

    Un nom de fichier en double dans deux dossiers est frequent ici (chantier
    « doublons proches »). En prendre un au hasard mettrait une AUTRE photo
    dans l'echantillon : on mesurerait autre chose en croyant reparer.
    """
    a = "\\\\NAS\\Photos\\2025\\20250922_135602.jpg"
    b = "\\\\NAS\\Photos\\2026\\Camera\\20250922_135602.jpg"
    mort = "\\\\NAS\\Photos\\_A TRIER\\x\\20250922_135602.jpg"
    nouveau, rap = re_.recler({mort: "riche"}, [a, b])
    ok = _check(nouveau == {mort: "riche"}, "la cle morte reste, non devinee")
    ok &= _check(len(rap["ambigues"]) == 1, "signalee comme ambigue")
    ok &= _check(rap["ambigues"][0][1] == sorted([a, b]),
                 "les deux candidats sont montres, tries")
    ok &= _check(not rap["reclees"], "aucune re-cle silencieuse")
    return ok


def test_photo_vraiment_disparue():
    mort = "\\\\NAS\\Photos\\_A TRIER\\x\\disparue.jpg"
    nouveau, rap = re_.recler({mort: "pauvre"}, ["\\\\NAS\\Photos\\autre.jpg"])
    ok = _check(rap["perdues"] == [mort], "comptee comme perdue")
    ok &= _check(nouveau == {mort: "pauvre"},
                 "gardee dans l echantillon : retirer le trou le masquerait")
    return ok


def test_aucune_collision_entre_deux_recles():
    """Deux photos deplacees vers le meme dossier gardent chacune leur strate."""
    a1 = "\\\\NAS\\Photos\\_A TRIER\\x\\a.jpg"
    b1 = "\\\\NAS\\Photos\\_A TRIER\\y\\b.jpg"
    a2 = "\\\\NAS\\Photos\\2025\\a.jpg"
    b2 = "\\\\NAS\\Photos\\2025\\b.jpg"
    nouveau, rap = re_.recler({a1: "riche", b1: "piege"}, [a2, b2])
    ok = _check(nouveau == {a2: "riche", b2: "piege"}, "chaque strate suit sa photo")
    ok &= _check(len(nouveau) == 2, "aucune perte par ecrasement")
    return ok


def test_taille_conservee():
    """Un re-clage ne doit jamais CHANGER le nombre de photos du banc.

    C'est l'invariant qui distingue « suivre un renommage » de « regenerer
    l'echantillon » — ce que le protocole 3b interdit.
    """
    ech = {AVANT: "riche", APRES.replace("2025", "2024"): "pauvre",
           "\\\\NAS\\Photos\\_A TRIER\\z\\perdue.jpg": "piege"}
    nouveau, _ = re_.recler(ech, [APRES])
    return _check(len(nouveau) == len(ech), "meme nombre de photos qu avant")


def test_taux_de_cles_mortes():
    ok = True
    ech = {"a": "riche", "b": "riche", "c": "riche", "d": "riche"}
    ok &= _check(re_.taux_de_cles_mortes(ech, ["a", "b", "c", "d"]) == 0.0,
                 "aucune morte -> 0 %")
    ok &= _check(re_.taux_de_cles_mortes(ech, ["a"]) == 75.0, "3 sur 4 -> 75 %")
    ok &= _check(re_.taux_de_cles_mortes(ech, []) == 100.0, "index vide -> 100 %")
    ok &= _check(re_.taux_de_cles_mortes({}, ["a"]) == 0.0,
                 "echantillon vide -> 0 %, pas une division par zero")
    # Le cas reel du 15/08 : 65 mortes sur 150 = 43,3 %, tres au-dessus des 15 %.
    reel = {f"k{i}": "riche" for i in range(150)}
    taux = re_.taux_de_cles_mortes(reel, [f"k{i}" for i in range(85)])
    ok &= _check(abs(taux - 43.333) < 0.01, "le cas du 15/08 : 43,3 %")
    return ok


if __name__ == "__main__":
    resultats = []
    for nom, fn in [
        ("nom_de_fichier", test_nom_de_fichier),
        ("recle du jumeau unique", test_recle_le_jumeau_unique),
        ("cle encore valide", test_cle_encore_valide_intacte),
        ("jumeaux multiples", test_jumeaux_multiples_jamais_devines),
        ("photo disparue", test_photo_vraiment_disparue),
        ("pas de collision", test_aucune_collision_entre_deux_recles),
        ("taille conservee", test_taille_conservee),
        ("taux de cles mortes", test_taux_de_cles_mortes),
    ]:
        print(f"== {nom} ==")
        resultats.append(fn())
    print()
    if all(resultats):
        print("TOUS LES TESTS PASSENT")
        raise SystemExit(0)
    print("DES TESTS ONT ECHOUE")
    raise SystemExit(1)
