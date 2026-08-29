#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Les ARGUMENTS d'écriture des métadonnées — module pur, testable sans serveur.

Deux façons d'écrire les mots-clés et la description dans un fichier :

- **complète** (MWG) : XMP + IPTC + EXIF (`ImageDescription`, `XPKeywords`).
  C'est la voie normale. Elle RÉÉCRIT le bloc EXIF.
- **sans EXIF** : XMP + IPTC seulement. ExifTool laisse alors le bloc EXIF tel
  quel — et avec lui tout ce qui dépend de ses offsets.

Pourquoi la seconde existe (29/08/2026, `verifier_reparation_exif.py`) : sur
un Motion Photo Samsung, ExifTool refuse la voie complète (« Error reading
OtherImageStart data in IFD0 »). Le serveur répondait par `repair_file`
(`-all=` puis recopie), qui JETTE le trailer — la vidéo embarquée, 2 à 3 Mo —
et le profil ICC. Mesuré sur une copie : la voie sans EXIF écrit les tags,
garde la vidéo, le trailer `SEFT` et l'ICC (+501 octets) ; `-all=` perd tout,
même avec `--trailer:all`. Quatorze photos de 2024 l'ont subi le 28/08.

Règle : **un rattrapage ne détruit jamais plus que ce qu'il répare.**
"""
import re

# Le refus qui signe un EXIF qu'ExifTool ne sait pas RELIRE pour le réécrire.
# D'autres formes existent (« Bad IFD0 directory », « Error reading ... ») ;
# toutes disent la même chose : ne pas réécrire l'EXIF, écrire à côté.
EXIF_ILLISIBLE = re.compile(
    r'Error reading .* in IFD\d|Bad (?:IFD|ExifIFD|MakerNotes)|'
    r'Error reading ExifIFD|Invalid .* offset', re.I)

_BASE = ["-overwrite_original", "-q", "-m",
         "-charset", "filename=UTF8", "-codedcharacterset=utf8"]


def _desc_propre(desc):
    return ' '.join(str(desc or '').split())


def args_ecriture(keywords, desc, jpeg=True, sans_exif=False):
    """Arguments ExifTool (sans le chemin) pour écrire `keywords` et `desc`.

    `sans_exif=True` : XMP-dc + IPTC seulement, pas de MWG (qui écrit aussi
    `EXIF:ImageDescription`) ni de `XPKeywords` (EXIF IFD0). Les mots-clés
    sont posés en REMPLACEMENT (`=`), comme la voie complète : l'index est la
    vérité, le fichier la reçoit."""
    kws = list(keywords or [])
    d = _desc_propre(desc)
    args = list(_BASE)
    if sans_exif:
        # `-XMP-dc:Subject=` vide puis `+=` chaque valeur : une liste propre,
        # sans doublon d'une écriture précédente.
        args += ["-XMP-dc:Subject=", "-IPTC:Keywords="]
        for k in kws:
            args += [f"-XMP-dc:Subject+={k}", f"-IPTC:Keywords+={k}"]
        if d:
            args += [f"-XMP-dc:Description={d}", f"-IPTC:Caption-Abstract={d}"]
        return args
    for k in kws:
        args.append(f"-MWG:Keywords={k}")
    if d:
        args.append(f"-MWG:Description={d}")
    if jpeg:
        args.append(f"-XPKeywords={'; '.join(kws)}")
    return args


def exif_illisible(stderr):
    """Vrai si le refus d'ExifTool est un EXIF qu'il ne sait pas relire — le cas
    où la voie sans EXIF est la bonne réponse, pas `-all=`."""
    return bool(EXIF_ILLISIBLE.search(str(stderr or '')))
