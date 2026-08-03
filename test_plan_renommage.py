#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du generateur de plan de renommage (PUR, hors serveur/NAS/DB).

Verifie : la detection des noms bruts (vs deja dates), que le plan ne touche QUE
les bruts, qu'il porte la cle et change le nom, et que les collisions (meme
dossier, y compris contre un fichier non renomme) sont resolues par suffixe.
"""
import sys

import plan_renommage as P


def test_est_nom_brut_vrais():
    for n in ["Screenshot_20190704.png", "Screen Shot 2019-07-04.png",
              "VideoCapture_20190704.jpg", "IMG_20190704_120000.jpg",
              "IMG-20190704-WA0001.jpg", "Scan_001.jpg", "Photo0001.jpg",
              "09525e0071345f1f2239a0e6dee0c690.jpg", "hqdefault.jpg",
              "received_1234567890.jpeg"]:
        assert P.est_nom_brut(n), n


def test_est_nom_brut_faux():
    # deja dates/propres, ou nom humain explicite : on n'y touche pas
    for n in ["20190704_123045.jpg", "20190704-123045.jpg",
              "20190704_123045_01.jpg", "Luna a Bremblens.jpg",
              "Anniversaire Flo.jpg"]:
        assert not P.est_nom_brut(n), n


def test_plan_ne_touche_que_les_bruts():
    entries = [
        ("Photos/2019/Screenshot_20190704.jpg", {}),
        ("Photos/2019/20190704_123045.jpg", {}),     # propre -> laisse tel quel
        ("Photos/2019/Photo0001.jpg", {}),           # brut, date via dossier 2019
    ]
    moves, stats = P.construire_plan(entries)
    keys = {m["key"] for m in moves}
    assert "Photos/2019/20190704_123045.jpg" not in keys
    assert "Photos/2019/Screenshot_20190704.jpg" in keys
    assert "Photos/2019/Photo0001.jpg" in keys      # date = annee du dossier
    assert stats["total"] == 3
    assert stats["a_renommer"] == 2
    assert stats["laisses_tels_quels"] == 1


def test_sujet_force_le_francais():
    # description IA anglaise + mots-cles francais -> le sujet doit etre en
    # francais (kw_fr), pas les mots anglais.
    entry = {'desc': 'a serene alpine landscape with mountains',
             'kw_fr': ['montagne', 'ciel', 'lac']}
    entries = [("Photos/2019/IMG_5000.jpg", entry)]
    moves, _ = P.construire_plan(entries)
    assert len(moves) == 1
    nn = moves[0]['new_name'].lower()
    assert 'landscape' not in nn and 'serene' not in nn and 'mountain' not in nn, nn
    assert ('montagne' in nn or 'ciel' in nn or 'lac' in nn), nn


def test_sans_date_non_renomme():
    # aucune date fiable (dossier sans annee, pas de date dans le nom) : on NE
    # fabrique PAS « 00000000_... », on laisse le nom brut (choix Mike, 03/08).
    entries = [("Album/Photo0001.jpg", {})]
    moves, stats = P.construire_plan(entries)
    assert moves == []
    assert stats["sans_date_ignores"] == 1
    assert stats["a_renommer"] == 0


def test_plan_porte_la_cle_et_change_le_nom():
    entries = [("Dossier/Screenshot_20190704.jpg", {})]
    moves, _ = P.construire_plan(entries)
    assert len(moves) == 1
    m = moves[0]
    assert m["key"] == "Dossier/Screenshot_20190704.jpg"
    assert m["old_name"] == "Screenshot_20190704.jpg"
    assert m["new_name"] != m["old_name"]
    assert m["new_name"][:8] == "20190704"       # date en tete (tri chronologique)
    assert m["dossier"] == "Dossier"


def test_collision_meme_dossier_suffixe():
    # deux bruts, meme date, pas de sujet, meme ext -> meme base -> 2e suffixe
    entries = [
        ("D/Screenshot_20190704.jpg", {}),
        ("D/VideoCapture_20190704.jpg", {}),
    ]
    moves, _ = P.construire_plan(entries)
    news = [m["new_name"] for m in moves]
    assert len(moves) == 2, moves
    assert news[0] != news[1], news              # collision resolue
    assert all(n[:8] == "20190704" for n in news)


def test_collision_contre_fichier_non_renomme():
    # « 20190704.jpg » (non brut) est deja pris ; le brut doit l'EVITER, pas
    # l'ecraser -> preuve que le plan reserve les noms des fichiers non renommes.
    entries = [
        ("D/20190704.jpg", {}),                  # non brut -> reserve
        ("D/Screenshot_20190704.jpg", {}),       # proposerait « 20190704.jpg »
    ]
    moves, _ = P.construire_plan(entries)
    assert len(moves) == 1
    nn = moves[0]["new_name"]
    assert nn != "20190704.jpg", nn              # n'ecrase pas le fichier existant
    assert nn.startswith("20190704-")            # suffixe de collision


def test_annee_du_dossier_pas_du_nom():
    # « IMG_1998 » dans un dossier « 2007 » : le 1998 du NOM ne doit pas etre lu
    # comme une annee -> la date vient du DOSSIER (2007), pas de 1998. Regression
    # trouvee en verifiant le plan reel (IMG_1998.jpg -> 19980000, faux).
    entries = [("Photos/2007/IMG_1998.jpg", {})]
    moves, _ = P.construire_plan(entries)
    assert len(moves) == 1
    nn = moves[0]["new_name"]
    assert nn[:8] == "20070000", nn


TESTS = [
    ("est_nom_brut : vrais", test_est_nom_brut_vrais),
    ("est_nom_brut : faux", test_est_nom_brut_faux),
    ("plan ne touche que les bruts", test_plan_ne_touche_que_les_bruts),
    ("plan porte la cle et change le nom", test_plan_porte_la_cle_et_change_le_nom),
    ("collision meme dossier -> suffixe", test_collision_meme_dossier_suffixe),
    ("collision contre fichier non renomme", test_collision_contre_fichier_non_renomme),
    ("annee du dossier, pas du nom (IMG_1998)", test_annee_du_dossier_pas_du_nom),
    ("sans date -> non renomme (pas de 00000000)", test_sans_date_non_renomme),
    ("sujet force le francais (desc anglaise)", test_sujet_force_le_francais),
]


def main():
    ok = 0
    for nom, fn in TESTS:
        try:
            fn()
            print(f"  ok   {nom}")
            ok += 1
        except AssertionError as e:
            print(f"  FAIL {nom} : {e}")
        except Exception as e:                                # noqa: BLE001
            print(f"  ERR  {nom} : {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(TESTS)} tests verts")
    return 0 if ok == len(TESTS) else 1


if __name__ == "__main__":
    sys.exit(main())
