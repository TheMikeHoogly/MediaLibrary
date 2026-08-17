#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du generateur de plan de renommage (PUR, hors serveur/NAS/DB).

Verifie : la detection des noms bruts (vs deja dates), que le plan ne touche QUE
les bruts, qu'il porte la cle et change le nom, et que les collisions (meme
dossier, y compris contre un fichier non renomme) sont resolues par suffixe.
"""
import sys

import plan_renommage as P
import renommage_facts as RF


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
    # collision resolue par compteur LISIBLE (-2), pas un hash
    assert "20190704.jpg" in news and "20190704-2.jpg" in news, news


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
    assert nn == "20190704-2.jpg", nn            # evite l'existant, compteur lisible


def test_annee_du_dossier_pas_du_nom():
    # « IMG_1998 » dans un dossier « 2007 » : le 1998 du NOM ne doit pas etre lu
    # comme une annee -> la date vient du DOSSIER (2007), pas de 1998. Regression
    # trouvee en verifiant le plan reel (IMG_1998.jpg -> 19980000, faux).
    entries = [("Photos/2007/IMG_1998.jpg", {})]
    moves, _ = P.construire_plan(entries)
    assert len(moves) == 1
    nn = moves[0]["new_name"]
    assert nn[:8] == "20070000", nn


def test_annee_dossier_pre_1990():
    # Un dossier « 1986 » porte son annee en clair, mais le plancher a 1990 la
    # jetait : les 714 photos des annees 80 de « Photos Papa » partaient en
    # « sans date » au renommage (mesure du 14/08). Elles doivent desormais
    # etre datees par leur dossier, comme n'importe quelle autre annee.
    entries = [("Photos/Photos Papa/1986/Scan_001.jpg", {})]
    moves, stats = P.construire_plan(entries)
    assert len(moves) == 1, stats
    assert moves[0]["new_name"][:8] == "19860000", moves[0]["new_name"]


def test_annee_dossier_pre_1990_ignore_le_nom():
    # Le plancher descend, mais le nom de fichier reste EXCLU : un « 1975 » de
    # numero de sequence ne doit pas passer devant le dossier (meme garde-fou
    # que IMG_1998, verifie sur la plage nouvellement ouverte).
    entries = [("Photos/Photos Papa/1986/Scan_1975.jpg", {})]
    moves, _ = P.construire_plan(entries)
    assert len(moves) == 1
    assert moves[0]["new_name"][:8] == "19860000", moves[0]["new_name"]



# ── Garde-fou SCAN (17/08) ────────────────────────────────────────────────────
# Un tirage numerise porte souvent la date du SCAN dans DateTimeOriginal ;
# `tagging_meta.date_fiable` ne garde que ModifyDate. Sans ce garde-fou, 12
# photos de « Photos Papa » rangees sous 1990/1993/2003 partaient en 2007.
_SCAN_2007 = 1183892222        # 08/07/2007, milieu de journee
_PRISE_2014 = 1401368781       # 29/05/2014


def test_date_posterieure_au_dossier_refusee():
    """Dossier 1990 + EXIF 2007 -> l'annee du DOSSIER gagne (statu quo)."""
    key = r"\\NAS\home\Photos\Photos Papa\1990\1990_Achumani\IMG_1307.jpg"
    d, prec = RF.resolve_datestamp(key, {'taken': _SCAN_2007})
    assert d == '19900000', d
    assert prec == 'annee', prec


def test_date_anterieure_au_dossier_gardee():
    """Dossier d'IMPORT 2026 + EXIF 2014 -> l'EXIF a raison, on le garde."""
    key = r"\\NAS\home\Photos\2026\Photos Floflo\Miki\IMG_5387.JPG"
    d, prec = RF.resolve_datestamp(key, {'taken': _PRISE_2014})
    assert d.startswith('20140529'), d
    assert prec == 'exact', prec


def test_reveillon_tolere():
    """Un an d'ecart = debordement legitime (139 mesures le 14/08), pas un scan."""
    key = r"\\NAS\home\Photos\2019 Voyage\IMG_0001.jpg"
    d, _ = RF.resolve_datestamp(key, {'taken': 1577840000})   # 01/01/2020
    assert d.startswith('2020'), d


def test_chemin_sans_annee_ne_contredit_rien():
    key = r"\\NAS\home\Photos\Divers\IMG_0002.jpg"
    d, prec = RF.resolve_datestamp(key, {'taken': _SCAN_2007})
    assert d.startswith('20070708'), d
    assert prec == 'exact', prec


def test_plage_de_dossier_compare_au_MAX():
    """« 2005-2010\\2008 » : une photo de 2010 n'est pas un scan."""
    key = r"\\NAS\home\Photos\Photos 2005-2010\2008\IMG_0003.jpg"
    d, _ = RF.resolve_datestamp(key, {'taken': 1275000000})   # 28/05/2010
    assert d.startswith('2010'), d


def test_scan_refuse_laisse_le_nom_de_fichier_parler():
    """Le repli n'est pas « annee du dossier » d'office : le nom de fichier
    reste prioritaire sur lui (ordre inchange)."""
    key = r"\\NAS\home\Photos\Photos Papa\1993\IMG_19930712_101500.jpg"
    d, prec = RF.resolve_datestamp(key, {'taken': _SCAN_2007})
    assert d == '19930712-101500', d
    assert prec == 'exact', prec


TESTS = [
    ("est_nom_brut : vrais", test_est_nom_brut_vrais),
    ("est_nom_brut : faux", test_est_nom_brut_faux),
    ("plan ne touche que les bruts", test_plan_ne_touche_que_les_bruts),
    ("plan porte la cle et change le nom", test_plan_porte_la_cle_et_change_le_nom),
    ("collision meme dossier -> suffixe", test_collision_meme_dossier_suffixe),
    ("collision contre fichier non renomme", test_collision_contre_fichier_non_renomme),
    ("annee du dossier, pas du nom (IMG_1998)", test_annee_du_dossier_pas_du_nom),
    ("annee du dossier pre-1990 (1986)", test_annee_dossier_pre_1990),
    ("pre-1990 : le nom reste exclu (Scan_1975)", test_annee_dossier_pre_1990_ignore_le_nom),
    ("sans date -> non renomme (pas de 00000000)", test_sans_date_non_renomme),
    ("sujet force le francais (desc anglaise)", test_sujet_force_le_francais),
    ("garde-fou scan : EXIF 2007 sous dossier 1990 refuse", test_date_posterieure_au_dossier_refusee),
    ("EXIF 2014 sous dossier d'import 2026 garde", test_date_anterieure_au_dossier_gardee),
    ("reveillon : un an d'ecart tolere", test_reveillon_tolere),
    ("chemin sans annee : rien a contredire", test_chemin_sans_annee_ne_contredit_rien),
    ("plage de dossier : comparaison au MAX", test_plage_de_dossier_compare_au_MAX),
    ("scan refuse : le nom de fichier reste prioritaire", test_scan_refuse_laisse_le_nom_de_fichier_parler),
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
