#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de rangement_annee.py (plan par annee, pur, sans serveur).

Lance :  python test_rangement_annee.py
"""
import sys
from datetime import datetime

import rangement_annee as ra

FAIL = []


def check(cond, msg):
    print(("  OK " if cond else "  ECHEC ") + msg)
    if not cond:
        FAIL.append(msg)


def ts(y, m=6, d=1):
    return datetime(y, m, d, 12, 0).timestamp()


def main():
    items = [
        ('k1', '/nas/Photos/_A TRIER/img1.jpg', ts(2020)),
        ('k2', '/nas/Photos/_A TRIER/sub/img2.jpg', ts(2019)),     # aplati
        ('k3', '/nas/Photos/_A TRIER/nodate.jpg', 0),              # sans date
        ('k4', '/nas/Photos/2020/deja_range.jpg', ts(2020)),       # PAS sous _A TRIER
        ('k5', '/nas/Photos/A TRIER/variant.jpg', ts(2018)),       # tolerance casse/sep
        ('k6', '/nas/Photos/_A TRIER/dup.jpg', ts(2020)),
        ('k7', '/nas/Photos/_A TRIER/other/dup.jpg', ts(2020)),    # collision de plan
    ]
    p = ra.construire_plan(items)
    dsts = {m['key']: m['dst'] for m in p['moves']}

    check(dsts.get('k1', '').replace('\\', '/') == '/nas/Photos/2020/img1.jpg',
          "range vers <base>/AAAA/ (2020)")
    check(dsts.get('k2', '').replace('\\', '/') == '/nas/Photos/2019/img2.jpg',
          "aplati : sous-dossier de _A TRIER -> annee directe")
    check(dsts.get('k3', '').replace('\\', '/') == '/nas/Photos/_SANS_DATE/nodate.jpg',
          "sans date fiable -> _SANS_DATE (jamais devine)")
    check('k4' not in dsts, "fichier hors _A TRIER : ignore")
    check(dsts.get('k5', '').replace('\\', '/') == '/nas/Photos/2018/variant.jpg',
          "tolerance « A TRIER » (sans underscore)")
    check(any(c['key'] == 'k7' for c in p['conflits']),
          "collision de plan (meme nom, meme annee) -> conflit, pas ecrasement")
    check(p['sans_date'] == 1, "compteur sans_date")
    check(p['par_annee'].get(2020) == 2 and p['par_annee'].get(2019) == 1
          and p['par_annee'].get(2018) == 1, "repartition par annee (k1+k6 en 2020, k7 en conflit)")
    check(p['total_a_ranger'] == len(p['moves']), "total coherent")
    # aucune cle inventee, aucune perte : chaque move a src+dst+annee
    check(all(m.get('src') and m.get('dst') and m.get('annee') for m in p['moves']),
          "chaque move a provenance complete (src, dst, annee)")

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) — {FAIL}")
        return 1
    print("Tous les tests rangement_annee.py : VERTS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
