#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de interet.py — la logique PURE du triage des rebuts (point 21).

Tout tourne sans NAS, sans GPU, sans base : heuristique de nom, score de flou
sur images synthetiques, assemblage des signaux, metriques et balayage de seuil.
Le banc eval_interet.py (corpus + SigLIP) n'est PAS teste ici — il exige la
machine reelle ; ce fichier valide les briques qu'il assemble.
"""
import sys
import numpy as np

import interet as I


def _ck(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ─────────────────────────── Heuristique de nom ───────────────────────────────

def test_indice_nom_captures():
    cas = [
        ("Screenshot_20230101_120000.png", "capture"),
        ("Screen Shot 2022-05-05.png", "capture"),
        ("Capture d'ecran 2021.png", "capture"),
        ("VideoCapture_20200101.jpg", "capture"),
        ("IMG-20210101-WA0001.jpg", "capture"),          # WhatsApp
        ("FB_IMG_1600000000000.jpg", "capture"),
        ("Snapchat-123456789.jpg", "capture"),
    ]
    for nom, attendu in cas:
        cat, motif = I.indice_nom(nom)
        _ck(cat == attendu, f"{nom!r} -> {cat!r}, attendu {attendu!r}")
        _ck(motif, f"{nom!r} : motif vide")


def test_indice_nom_docs_factures():
    _ck(I.indice_nom("Scan_2023_04.pdf")[0] == "document", "Scan_ non reconnu")
    _ck(I.indice_nom("numerisation0001.jpg")[0] == "document", "numerisation")
    _ck(I.indice_nom("facture_edf_2024.jpg")[0] == "facture", "facture")
    _ck(I.indice_nom("receipt-2023.png")[0] == "facture", "receipt")
    _ck(I.indice_nom("ticket_caisse.jpg")[0] == "facture", "ticket")


def test_indice_nom_photos_normales():
    for nom in ("IMG_1234.jpg", "DSC00042.JPG", "P1010101.jpg",
                "20180715_familiale.jpg", "luna_canape.jpg"):
        cat, motif = I.indice_nom(nom)
        _ck(cat is None, f"{nom!r} faussement classe {cat!r}")


def test_indice_nom_ignore_le_chemin():
    # Un dossier nomme « Screenshots » ne doit pas contaminer une vraie photo.
    cat, _ = I.indice_nom("C:/Photos/Screenshots/IMG_4242.jpg")
    _ck(cat is None, "le chemin a contamine la decision (doit ignorer le dossier)")


# ─────────────────────────── Score de flou ────────────────────────────────────

def _damier(n=256, case=8):
    y, x = np.mgrid[0:n, 0:n]
    return (((x // case) + (y // case)) % 2 * 255).astype("uint8")


def _flou_gaussien(img, k=9):
    import cv2
    return cv2.GaussianBlur(img, (k, k), 0)


def test_variance_laplacien_net_vs_flou():
    net = _damier()
    flou = _flou_gaussien(net, 15)
    v_net = I.variance_laplacien(net)
    v_flou = I.variance_laplacien(flou)
    _ck(v_net > v_flou * 3,
        f"net={v_net:.0f} devrait tres largement depasser flou={v_flou:.0f}")


def test_variance_laplacien_repli_numpy(monkeypatch=None):
    # Force le repli pur numpy en cachant cv2 dans la fonction.
    import builtins
    reel = builtins.__import__

    def faux_import(nom, *a, **k):
        if nom == "cv2":
            raise ImportError("cv2 masque pour le test")
        return reel(nom, *a, **k)

    builtins.__import__ = faux_import
    try:
        net = _damier()
        flou = _flou_gaussien(net, 15) if False else net  # pas besoin de cv2 ici
        v = I.variance_laplacien(net)
        _ck(v > 0, "le repli numpy doit produire une variance positive")
    finally:
        builtins.__import__ = reel


def test_score_flou_fichier(tmp=None):
    import cv2, tempfile, os
    net = _damier()
    flou = _flou_gaussien(net, 21)
    d = tempfile.mkdtemp()
    pn, pf = os.path.join(d, "net.png"), os.path.join(d, "flou.png")
    cv2.imwrite(pn, net)
    cv2.imwrite(pf, flou)
    sn, sf = I.score_flou(pn), I.score_flou(pf)
    _ck(sn is not None and sf is not None, "score_flou renvoie None sur fichier valide")
    _ck(sn > sf, f"net={sn:.0f} doit depasser flou={sf:.0f}")
    _ck(I.score_flou(os.path.join(d, "absent.png")) is None,
        "fichier absent doit donner None")


# ─────────────────────── Assemblage des signaux ───────────────────────────────

def test_proposer_rien():
    r = I.proposer()
    _ck(r["rebut"] is False and r["sources"] == [], "aucun signal -> pas rebut")


def test_proposer_nom_prioritaire():
    r = I.proposer(indice_nom_cat="capture", siglip_cat="document",
                   siglip_score=0.9, seuil_siglip=0.1)
    _ck(r["rebut"] and r["categorie"] == "capture",
        f"le nom doit primer, obtenu {r['categorie']!r}")


def test_proposer_flou_sous_seuil():
    # flou franchi
    r = I.proposer(flou=50.0, seuil_flou=100.0)
    _ck(r["rebut"] and r["categorie"] == "flou", "flou sous seuil -> rebut flou")
    # flou non franchi
    r2 = I.proposer(flou=200.0, seuil_flou=100.0)
    _ck(r2["rebut"] is False, "flou au-dessus du seuil -> pas rebut")


def test_proposer_siglip_seuil():
    r = I.proposer(siglip_cat="facture", siglip_score=0.30, seuil_siglip=0.20)
    _ck(r["rebut"] and r["categorie"] == "facture", "siglip au-dessus du seuil")
    r2 = I.proposer(siglip_cat="facture", siglip_score=0.10, seuil_siglip=0.20)
    _ck(r2["rebut"] is False, "siglip sous le seuil -> pas rebut")


# ─────────────────────────── Metriques ────────────────────────────────────────

def test_metriques_binaire_compte():
    #        y:   R  R  R  G  G
    verites = [True, True, True, False, False]
    preds =   [True, False, True, True, False]   # vp=2 fn=1 fp=1 vn=1
    m = I.metriques_binaire(verites, preds)
    _ck((m["vp"], m["fn"], m["fp"], m["vn"]) == (2, 1, 1, 1), f"comptes: {m}")
    _ck(abs(m["precision"] - 2/3) < 1e-9, m["precision"])
    _ck(abs(m["rappel"] - 2/3) < 1e-9, m["rappel"])


def test_metriques_longueurs():
    try:
        I.metriques_binaire([True], [True, False])
    except ValueError:
        return
    raise AssertionError("longueurs differentes doivent lever ValueError")


def test_balayage_sup_et_inf():
    scores = [0.1, 0.4, 0.6, 0.9]
    verites = [False, False, True, True]
    b = I.balayage_seuil(scores, verites, [0.5], sens="sup")[0]
    _ck((b["vp"], b["fp"]) == (2, 0), f"sup 0.5: {b}")
    # flou : rebut si score < seuil
    scf = [10.0, 30.0, 200.0, 400.0]
    vf = [True, True, False, False]
    bf = I.balayage_seuil(scf, vf, [100.0], sens="inf")[0]
    _ck((bf["vp"], bf["fp"]) == (2, 0), f"inf 100: {bf}")


def test_meilleur_seuil_borne_fp():
    scores = [0.1, 0.2, 0.55, 0.6, 0.9]
    verites = [False, True, True, True, True]     # un vrai rebut a score 0.2
    seuils = [0.15, 0.3, 0.5, 0.7]
    bal = I.balayage_seuil(scores, verites, seuils, sens="sup")
    # fp_max=0 : interdit toute bonne photo signalee
    best = I.meilleur_seuil(bal, fp_max=0)
    _ck(best is not None, "un seuil a fp=0 doit exister")
    _ck(best["fp"] == 0, f"fp doit etre 0, obtenu {best['fp']}")
    # borne impossible -> None
    impossible = I.meilleur_seuil(
        [{"f1": 0.5, "rappel": 0.5, "fp": 3}], fp_max=0)
    _ck(impossible is None, "aucun seuil sous la borne -> None")


# ─────────────────────────── Runner ───────────────────────────────────────────

def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    ok = 0
    for t in tests:
        try:
            t()
            ok += 1
            print(f"  ok   {t.__name__}")
        except Exception as e:                    # noqa: BLE001
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{ok}/{len(tests)} tests verts")
    return 0 if ok == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
