#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ce que coute UNE vignette absente du cache : le NAS, ou le decodage ?

`mesure_couverture_vignettes.py` (11/09) : **98 % des 39 999 photos n'ont pas
de vignette 512 px**. Chaque case de galerie sur une photo pas encore vue
paie donc `_serve_thumb` en entier — 28 requetes sur 35 au-dessus d'une
seconde dans le releve du matin. Avant de choisir QUI fabrique les vignettes
(le tagueur au passage ? un fil de fond ? personne ?), il faut savoir ce que
coute une fabrication, et ou part ce cout.

`_serve_thumb` fait aujourd'hui, dans cet ordre :

    Image.open(chemin) -> exif_transpose -> convert('RGB') -> thumbnail(s)

`exif_transpose` et `convert` CHARGENT l'image : une photo de 12 Mpx est
decodee en entier pour en garder 512 px. Pillow sait decoder un JPEG
directement a 1/2, 1/4 ou 1/8 de sa taille (`draft`) — c'est ce que
`thumbnail` fait tout seul quand l'image n'est pas encore chargee, avec une
marge de 2 (`reducing_gap`). L'ordre actuel l'en empeche.

Pour chaque photo, trois temps, mesures SEPAREMENT :
  1. LECTURE : les octets depuis le NAS (premiere lecture = froide) ;
  2. DECODAGE ACTUEL, depuis la memoire ;
  3. DECODAGE AVEC `draft(None, (2s, 2s))` — la marge de `thumbnail` — depuis
     la memoire ;
et l'ECART d'image entre 2 et 3 (PSNR, en dB : au-dela de ~40 dB, l'oeil ne
voit rien). Les methodes 2 et 3 sont alternees d'une photo a l'autre.

Il n'ecrit RIEN : ni cache, ni photo. Il LIT des photos d'un dossier.

  mesure_fabrication_vignette.py --dossier b64:UGhvdG9zIE1pa2UvMjAyMg --n 12
"""

import argparse
import io
import math
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

JPEG = {'.jpg', '.jpeg'}


def fabriquer_actuel(data, s):
    """L'ecriture de `_serve_thumb` au 11/09, a l'identique."""
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((s, s))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return buf.getvalue()


def fabriquer_draft(data, s, marge=2):
    """La meme chose, en demandant d'abord au decodeur JPEG une taille reduite
    (au moins `marge` x s) — ce que `thumbnail` ferait seul sur une image pas
    encore chargee."""
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data)) as im:
        im.draft(None, (s * marge, s * marge))
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((s, s))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        return buf.getvalue()


def psnr(a, b):
    """PSNR en dB entre deux JPEG (inf si identiques). Tailles differentes :
    None — c'est alors un ecart a signaler, pas a moyenner."""
    from PIL import Image, ImageChops, ImageStat
    ia = Image.open(io.BytesIO(a)).convert('RGB')
    ib = Image.open(io.BytesIO(b)).convert('RGB')
    if ia.size != ib.size:
        return None
    st = ImageStat.Stat(ImageChops.difference(ia, ib))
    mse = sum(r * r for r in st.rms) / 3.0
    return float('inf') if mse == 0 else 10 * math.log10(255.0 ** 2 / mse)


def choisir(dossier, n):
    """`n` JPEG repartis sur le dossier (tri par nom, pas regulier) — un seul
    `scandir`, pas de `stat` en plus."""
    import os
    noms = sorted(e.name for e in os.scandir(dossier)
                  if e.is_file() and Path(e.name).suffix.lower() in JPEG)
    if not noms:
        return []
    pas = max(1, len(noms) // n)
    return [dossier / x for x in noms[::pas][:n]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--dossier', required=True)
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--taille', type=int, default=512, choices=(512, 1600))
    a = ap.parse_args(argv)

    import mesure_parcours_dossier as mp
    dossier = mp.resoudre(a.dossier)
    if dossier is None or not dossier.is_dir():
        print('Dossier introuvable : %r' % a.dossier)
        return 2
    try:
        import PIL
        from PIL import Image                                    # noqa: F401
    except ImportError:
        print('Pillow absent de cet interpreteur.')
        return 2
    photos = choisir(dossier, a.n)
    if not photos:
        print('Aucun JPEG dans %s' % dossier)
        return 2
    s = a.taille
    print('Dossier : %s' % dossier)
    print('Photos  : %d JPEG, vignette %d px, Pillow %s' % (len(photos), s, PIL.__version__))
    print()
    print('  %-28s %7s %9s %9s %9s %8s %6s' % ('photo', 'Mo', 'lecture', 'actuel',
                                               'draft', 'PSNR dB', 'x'))
    print('  ' + '-' * 82)
    tot = {'lecture': 0.0, 'actuel': 0.0, 'draft': 0.0, 'octets': 0}
    ecarts, tailles_diff, echecs = [], 0, 0
    for i, p in enumerate(photos):
        try:
            t0 = time.perf_counter()
            data = p.read_bytes()
            t_lect = time.perf_counter() - t0
            ordre = [('actuel', fabriquer_actuel), ('draft', fabriquer_draft)]
            if i % 2:
                ordre.reverse()
            sorties, temps = {}, {}
            for nom, f in ordre:
                t0 = time.perf_counter()
                sorties[nom] = f(data, s)
                temps[nom] = time.perf_counter() - t0
            e = psnr(sorties['actuel'], sorties['draft'])
        except Exception as ex:                                  # noqa: BLE001
            echecs += 1
            print('  %-28s ECHEC : %s' % (p.name[:28], str(ex)[:40]))
            continue
        if e is None:
            tailles_diff += 1
        elif e != float('inf'):
            ecarts.append(e)
        tot['lecture'] += t_lect
        tot['actuel'] += temps['actuel']
        tot['draft'] += temps['draft']
        tot['octets'] += len(data)
        print('  %-28s %7.1f %7.0fms %7.0fms %7.0fms %8s %5.1f'
              % (p.name[:28], len(data) / 1048576, t_lect * 1000,
                 temps['actuel'] * 1000, temps['draft'] * 1000,
                 'taille!' if e is None else ('=' if e == float('inf') else '%.1f' % e),
                 temps['actuel'] / max(temps['draft'], 1e-9)))
    n = len(photos) - echecs
    if not n:
        return 1
    print('  ' + '-' * 82)
    print('  moyenne par photo : lecture NAS %.0f ms (%.1f Mo), decodage actuel %.0f ms,'
          % (tot['lecture'] / n * 1000, tot['octets'] / n / 1048576, tot['actuel'] / n * 1000))
    print('                      decodage draft %.0f ms  ->  x%.1f sur le decodage'
          % (tot['draft'] / n * 1000, tot['actuel'] / max(tot['draft'], 1e-9)))
    fab_act = (tot['lecture'] + tot['actuel']) / n
    fab_dr = (tot['lecture'] + tot['draft']) / n
    print('  fabrication complete : %.0f ms -> %.0f ms par vignette' % (fab_act * 1000, fab_dr * 1000))
    if ecarts:
        print('  PSNR actuel/draft : pire %.1f dB, median %.1f dB (%d photos)'
              % (min(ecarts), sorted(ecarts)[len(ecarts) // 2], len(ecarts)))
    if tailles_diff:
        print('  ATTENTION : %d vignette(s) de taille differente' % tailles_diff)
    print('  pour 39 181 vignettes absentes : %.1f h actuel, %.1f h draft (a ce rythme)'
          % (39181 * fab_act / 3600, 39181 * fab_dr / 3600))
    print()
    print('  A LIRE AVEC SA DATE : pendant la campagne de retag, le NAS et le CPU')
    print('  sont disputes — ces temps sont une BORNE HAUTE. Rien n a ete ecrit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
