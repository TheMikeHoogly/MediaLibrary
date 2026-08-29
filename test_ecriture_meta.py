#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `ecriture_meta` : la voie sans EXIF ne touche pas a l'EXIF, et le
refus d'ExifTool est reconnu. Module pur, aucun fichier, aucune base."""
import sys

import ecriture_meta as em

FAIL = []


def check(cond, msg):
    print(("  OK " if cond else "  ECHEC ") + msg)
    if not cond:
        FAIL.append(msg)


def main():
    print("=== ecriture_meta ===")
    a = em.args_ecriture(['chien', 'plage'], ' une  description \n', jpeg=True)
    check('-MWG:Keywords=chien' in a and '-MWG:Keywords=plage' in a,
          "voie complete : MWG:Keywords par mot-cle")
    check('-MWG:Description=une description' in a, "voie complete : description normalisee")
    check('-XPKeywords=chien; plage' in a, "voie complete : XPKeywords sur un JPEG")
    check('-XPKeywords=chien; plage' not in em.args_ecriture(['chien', 'plage'], '', jpeg=False),
          "voie complete : pas de XPKeywords hors JPEG")

    s = em.args_ecriture(['chien', 'plage'], 'desc', jpeg=True, sans_exif=True)
    check(not any(x.startswith(('-MWG:', '-XPKeywords', '-EXIF:', '-IFD0:')) for x in s),
          "sans EXIF : aucun argument MWG / XPKeywords / EXIF / IFD0")
    check(s.index('-XMP-dc:Subject=') < s.index('-XMP-dc:Subject+=chien'),
          "sans EXIF : la liste est videe AVANT d'etre remplie (pas de doublon)")
    check('-IPTC:Keywords+=plage' in s and '-XMP-dc:Subject+=plage' in s,
          "sans EXIF : chaque mot-cle en XMP-dc ET en IPTC")
    check('-XMP-dc:Description=desc' in s and '-IPTC:Caption-Abstract=desc' in s,
          "sans EXIF : description en XMP-dc et IPTC")
    check('-overwrite_original' in s and '-codedcharacterset=utf8' in s,
          "sans EXIF : memes options de base (overwrite, utf8)")
    v = em.args_ecriture([], '', sans_exif=True)
    check('-XMP-dc:Subject=' in v and not any('+=' in x for x in v),
          "sans EXIF, liste vide : on vide, on n'ajoute rien")

    check(em.exif_illisible('Error: Error reading OtherImageStart data in IFD0 - x.jpg'),
          "refus reconnu : OtherImageStart dans IFD0 (le Motion Photo du 28/08)")
    check(em.exif_illisible('Warning: Bad IFD0 directory'), "refus reconnu : Bad IFD0")
    check(not em.exif_illisible('Error: File not found - x.jpg'),
          "un fichier absent n'est PAS un EXIF illisible")
    check(not em.exif_illisible(''), "chaine vide : non")

    print()
    if FAIL:
        print(f"ECHEC : {len(FAIL)} assertion(s) — {FAIL}")
        return 1
    print("Tous les tests ecriture_meta.py : VERTS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
