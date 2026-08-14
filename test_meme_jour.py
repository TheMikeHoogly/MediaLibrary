#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de meme_jour.py — moteur « meme jour, autres annees ».

On n'importe pas server.py (il ouvrirait la vraie base) : le lecteur de date de
nom de fichier est INJECTE, comme dans le serveur. Le test qui compte est le
premier : une photo sans date PRECISE (repli « annee du dossier ») ne doit
apparaitre dans AUCUN jour — sinon des milliers de photos se rangent sous un
1er janvier qui n'a jamais existe.

Lance :  python test_meme_jour.py
"""
import re
import sys
import time

from meme_jour import (annee_de, cle_jour, construire_index, epoch_precis,
                       grouper_par_annee, jour_demande, libelle_jour,
                       photos_du_jour)

FAIL = []
NB = [0]


def check(cond, msg):
    NB[0] += 1
    print(("  OK   " if cond else "  ECHEC ") + msg)
    if not cond:
        FAIL.append(msg)


def ep(y, mo, d, hh=12, mm=0, ss=0):
    """Epoch LOCAL, comme tout le projet (time.mktime)."""
    return time.mktime((y, mo, d, hh, mm, ss, 0, 0, -1))


# Miroir minimal de server._fname_time (meme regex, meme garde d'annee).
_RE_FN = re.compile(r'(19\d{2}|20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})'
                    r'(?:[-_ .T]?(\d{2})[-_.]?(\d{2})[-_.]?(\d{2}))?')


def fname_time(name):
    m = _RE_FN.search(name)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
        return None
    hh, mi, ss = int(m.group(4) or 12), int(m.group(5) or 0), int(m.group(6) or 0)
    try:
        return time.mktime((y, mo, d, hh, mi, ss, 0, 0, -1))
    except (ValueError, OverflowError):
        return None


def t_dates_imprecises_exclues():
    print("\n[1] Une date IMPRECISE n'entre jamais dans l'index")
    # Le repli « annee du dossier » de _best_time : 1er janvier a midi. Ces
    # entrees n'ont ni `taken` ni date dans le nom : elles doivent disparaitre.
    entrees = [
        (r'\\NAS\Photos\2008\scan001.jpg', {'kw_fr': ['plage']}),
        (r'\\NAS\Photos\2008\scan002.jpg', {'kw_fr': ['plage']}),
        (r'\\NAS\Photos\2008\scan003.jpg', {'taken': 0}),
        (r'\\NAS\Photos\2008\scan004.jpg', {'taken': None}),
    ]
    idx = construire_index(entrees, fname_time)
    check(idx == {}, "4 photos sans date precise -> index vide (pas de 01-01)")

    check(epoch_precis(r'\\NAS\2008\a.jpg', {}, fname_time) is None,
          "epoch_precis : aucune source -> None")
    check(epoch_precis(r'\\NAS\2008\a.jpg', {'taken': 0}, fname_time) is None,
          "epoch_precis : taken=0 -> None (0 n'est pas une date)")
    check(epoch_precis(r'\\NAS\a.jpg', {'taken': False}, fname_time) is None,
          "epoch_precis : taken=False -> None (bool n'est pas une date)")
    # Le CHEMIN porte 2008, mais rien de precis : l'annee du dossier ne compte pas.
    check(epoch_precis(r'\\NAS\Photos 2008\vacances\img.jpg', {}, fname_time) is None,
          "epoch_precis : annee dans le CHEMIN -> toujours None")


def t_sources_precises():
    print("\n[2] Les deux sources precises, et la plus ancienne gagne")
    e = ep(2011, 8, 14, 18, 30)
    check(epoch_precis('a.jpg', {'taken': e}, fname_time) == e,
          "taken EXIF seul")
    check(epoch_precis('IMG_20110814_183000.jpg', {}, fname_time)
          == ep(2011, 8, 14, 18, 30), "date dans le nom seule")
    # taken faux (date de MODIFICATION posterieure) + nom juste -> le nom gagne
    tard = ep(2019, 3, 2, 9, 0)
    got = epoch_precis('IMG_20110814_183000.jpg', {'taken': tard}, fname_time)
    check(got == ep(2011, 8, 14, 18, 30),
          "taken posterieur au nom -> on garde la PLUS ANCIENNE")
    check(cle_jour(got) == '08-14', "-> jour 08-14, pas 03-02")


def t_index_et_jour():
    print("\n[3] Index, selection du jour, exclusion de la reference")
    entrees = [
        ('a2008.jpg', {'taken': ep(2008, 8, 14, 9, 0)}),
        ('b2011.jpg', {'taken': ep(2011, 8, 14, 18, 0)}),
        ('c2011.jpg', {'taken': ep(2011, 8, 14, 20, 0)}),
        ('d2019.jpg', {'taken': ep(2019, 8, 14, 7, 0)}),
        ('autre.jpg', {'taken': ep(2011, 8, 15, 7, 0)}),
        ('casse.jpg', {'taken': ep(2011, 8, 14, 8, 0), 'failed': True}),
        ('sansdate.jpg', {'kw_fr': ['chat']}),
    ]
    idx = construire_index(entrees, fname_time)
    check(sorted(idx) == ['08-14', '08-15'], "deux jours seulement")
    check(len(idx['08-14']) == 4, "08-14 : 4 photos (failed et sans date exclues)")
    check([c for _e, c in idx['08-14']]
          == ['a2008.jpg', 'b2011.jpg', 'c2011.jpg', 'd2019.jpg'],
          "tri chronologique du plus ancien au plus recent")

    tout = photos_du_jour(idx, '08-14')
    check(len(tout) == 4, "photos_du_jour sans exclusion : 4")
    sans_ref = photos_du_jour(idx, '08-14', exclure='b2011.jpg')
    check([c for _e, c in sans_ref] == ['a2008.jpg', 'c2011.jpg', 'd2019.jpg'],
          "la photo de reference est retiree, sa MEME ANNEE est gardee")
    check(photos_du_jour(idx, '12-25') == [], "jour sans photo -> liste vide")


def t_groupes_par_annee():
    print("\n[4] Groupement par annee, ordre croissant")
    entrees = [
        ('d2019.jpg', {'taken': ep(2019, 8, 14, 7, 0)}),
        ('a2008.jpg', {'taken': ep(2008, 8, 14, 9, 0)}),
        ('b2011.jpg', {'taken': ep(2011, 8, 14, 18, 0)}),
        ('c2011.jpg', {'taken': ep(2011, 8, 14, 20, 0)}),
    ]
    idx = construire_index(entrees, fname_time)
    grp = grouper_par_annee(photos_du_jour(idx, '08-14'))
    check([an for an, _ in grp] == [2008, 2011, 2019], "annees croissantes")
    check([len(v) for _an, v in grp] == [1, 2, 1], "effectifs par annee")
    check([c for _e, c in grp[1][1]] == ['b2011.jpg', 'c2011.jpg'],
          "dans une annee, ordre chronologique conserve")
    check(grouper_par_annee([]) == [], "aucune photo -> aucun groupe")


def t_parametre_jour():
    print("\n[5] Parametre ?jour= : ce qui est un jour, ce qui n'en est pas")
    check(jour_demande('08-14') == '08-14', "08-14")
    check(jour_demande(' 08-14 ') == '08-14', "espaces tolerees")
    check(jour_demande('02-29') == '02-29', "29 fevrier accepte (annees bissextiles)")
    check(jour_demande('02-30') is None, "02-30 refuse (n'existe jamais)")
    check(jour_demande('13-01') is None, "mois 13 refuse")
    check(jour_demande('00-10') is None, "mois 00 refuse")
    check(jour_demande('08-00') is None, "jour 00 refuse")
    check(jour_demande('8-14') is None, "format non zero-pade refuse")
    # Le cas qui compte : une CLE de photo ne doit jamais passer pour un jour.
    check(jour_demande(r'\\NAS-Bremblens\Photos\2011\IMG_20110814.jpg') is None,
          "une cle de photo n'est pas un jour")
    check(jour_demande('') is None and jour_demande(None) is None,
          "vide / None")


def t_libelles_et_localtime():
    print("\n[6] Libelles humains et heure LOCALE")
    check(libelle_jour('08-14') == '14 août', "08-14 -> « 14 août »")
    check(libelle_jour('01-01') == '1 janvier', "pas de zero de tete")
    check(libelle_jour('12-25') == '25 décembre', "12-25 -> « 25 décembre »")
    check(libelle_jour('02-30') == '', "jour invalide -> libelle vide")
    # localtime, pas gmtime : une photo prise a 00h30 reste le 14.
    check(cle_jour(ep(2011, 8, 14, 0, 30)) == '08-14',
          "00h30 le 14 aout reste au 14 (heure locale)")
    check(cle_jour(ep(2011, 8, 14, 23, 45)) == '08-14',
          "23h45 le 14 aout reste au 14")
    check(annee_de(ep(2011, 8, 14)) == 2011, "annee_de")
    check(cle_jour(0) is None, "epoch 0 -> None (annee 1970 hors bornes)")
    check(cle_jour(None) is None and cle_jour('x') is None,
          "epoch inexploitable -> None")


def t_volume():
    print("\n[7] Volume : 40 000 entrees, construction rapide")
    entrees = []
    for i in range(40000):
        an = 2000 + (i % 20)
        mo = 1 + (i % 12)
        jr = 1 + (i % 28)
        entrees.append(('p%05d.jpg' % i, {'taken': ep(an, mo, jr, 10, 0)}))
    t0 = time.perf_counter()
    idx = construire_index(entrees, fname_time)
    dt = time.perf_counter() - t0
    total = sum(len(v) for v in idx.values())
    check(total == 40000, "les 40 000 entrees sont indexees")
    check(dt < 3.0, "construction en %.2f s (< 3 s)" % dt)


for f in (t_dates_imprecises_exclues, t_sources_precises, t_index_et_jour,
          t_groupes_par_annee, t_parametre_jour, t_libelles_et_localtime,
          t_volume):
    f()

print("\n%d verifications, %d echec(s)." % (NB[0], len(FAIL)))
if FAIL:
    for m in FAIL:
        print("  - " + m)
    sys.exit(1)
print("Tout est vert.")
