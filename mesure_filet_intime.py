#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — le filet « photo intime », en zero-shot sur les vecteurs DEJA calcules
──────────────────────────────────────────────────────────────────────────────

POURQUOI (17/09, demande de Flo, relayee par Mike)

La phototheque s'ouvre a la famille. Le filet du chantier 18 ne connait que les
DOCUMENTS (mots-cles imposes par le prompt). Il ne voit ni une photo peu
habillee, ni une capture de conversation. Ce banc MESURE ce qu'un filet
zero-shot SigLIP saurait attraper -- il ne masque RIEN, il ne touche a rien.

CE QU'IL FAIT, ET CE QU'IL NE FAIT PAS

  - Il lit une COPIE de la base (`mesure_copie_base.py`), jamais `photos.db`.
  - Il encode quelques PHRASES avec la tour texte de SigLIP (le seul calcul :
    une poignee de phrases), puis compare aux 40 000 vecteurs image DEJA en
    base. Aucune image n'est relue, aucun NAS, pas de campagne.
  - Il rend une DISTRIBUTION et des COMPTES par seuil, plus, si on le demande,
    la liste des cles au-dessus d'un seuil (`--liste fichier.json`).
  - Il n'OUVRE aucune photo et n'en montre aucune : le regard humain se fait
    dans l'onglet Sensibles, par la personne concernee. Un banc qui afficherait
    ces images serait exactement ce qu'on essaie d'empecher.

LA MARGE, C'EST LE SUJET

Un seuil ne se choisit pas sur une moyenne : ce qui compte est ce qu'il LAISSE
PASSER. Le banc affiche donc, pour chaque seuil, combien de photos passent, et
l'ecart entre le score des phrases « intimes » et celui des phrases TEMOINS
(plage, sport, piscine) -- une photo de plage doit scorer haut sur « maillot de
bain » sans etre intime. C'est cet ECART, pas le score brut, qui fait le filet.

  python mesure_copie_base.py
  python mesure_filet_intime.py --base copie.db
  python mesure_filet_intime.py --base copie.db --seuil 0.12 --liste docs/filet_intime.json
"""

import argparse
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
KIND = 'photo'

# Les phrases INTIMES : ce qu'on cherche a mettre a l'abri. Formulees comme des
# descriptions de scene, pas comme des jugements -- SigLIP compare une image a
# une legende plausible, pas a une categorie morale.
PHRASES_INTIMES = [
    "une personne en sous-vetements",
    "une personne nue",
    "un selfie dans un miroir de salle de bain, peu vetu",
    "une personne torse nu dans une chambre",
    "une photo intime dans un lit",
]
# Les phrases TEMOINS : des scenes qui ressemblent aux precedentes mais qu'il
# ne faut PAS masquer. Sans elles, le filet attrape toutes les vacances.
PHRASES_TEMOINS = [
    "une personne en maillot de bain a la plage",
    "des gens qui nagent dans une piscine",
    "une personne qui fait du sport en short",
    "un bebe dans son bain",
    "une photo de famille a table",
]
# Les captures d'ecran et conversations, deuxieme demande de Flo.
PHRASES_CAPTURES = [
    "une capture d'ecran d'une conversation de messagerie",
    "une capture d'ecran d'un telephone",
    "une page de texte affichee sur un ecran",
]

SEUILS = (0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20)


def lire_vecteurs(base):
    import sqlite3
    import numpy as np
    if Path(base).name == 'photos.db':
        print('REFUS : ce banc lit une COPIE (mesure_copie_base.py), jamais photos.db')
        sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    try:
        cles, blobs = [], []
        for k, v in cx.execute("SELECT k, v FROM vectors WHERE kind=? ORDER BY k", (KIND,)):
            cles.append(k)
            blobs.append(v)
    finally:
        cx.close()
    if not cles:
        print('Aucun vecteur `photo` dans cette copie.')
        sys.exit(2)
    d = len(blobs[0]) // 2
    M = np.empty((len(blobs), d), dtype=np.float32)
    for i, b in enumerate(blobs):
        M[i] = (np.frombuffer(b, dtype=np.float16).astype(np.float32)
                if len(b) // 2 == d else 0.0)
    n = np.linalg.norm(M, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return cles, M / n


def quantiles(v, points=(0.5, 0.9, 0.99, 0.999, 1.0)):
    import numpy as np
    return {f'p{int(p*1000)/10:g}': round(float(np.quantile(v, p)), 4) for p in points}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--seuil', type=float, default=0.10,
                    help="marge intime - temoin au-dela de laquelle on liste")
    ap.add_argument('--liste', default='',
                    help='fichier JSON ou ecrire la file de revue '
                         '(recommande : _filet_intime.json, hors git)')
    ap.add_argument('--top', type=int, default=0,
                    help='ne garder que les N plus fortes marges (0 = toutes '
                         'celles au-dessus du seuil). La file de revue est '
                         'faite pour etre REGARDEE : une liste sans plafond '
                         'n est pas une file, c est un tas.')
    ap.add_argument('--exemples', type=int, default=12,
                    help='nombre de cles montrees a l ecran (chemins seuls)')
    a = ap.parse_args()

    import numpy as np
    import semantic

    cles, M = lire_vecteurs(a.base)
    print(f"Vecteurs lus : {len(cles)} (copie : {a.base})")

    tous = PHRASES_INTIMES + PHRASES_TEMOINS + PHRASES_CAPTURES
    T = semantic.encoder_textes([semantic.GABARIT.format(p) if False else p
                                 for p in tous])
    S = M @ T.T                                  # (n, phrases)
    ni, nt = len(PHRASES_INTIMES), len(PHRASES_TEMOINS)
    intime = S[:, :ni].max(axis=1)
    temoin = S[:, ni:ni + nt].max(axis=1)
    capture = S[:, ni + nt:].max(axis=1)
    marge = intime - temoin

    print("\n-- Distribution (cosinus) --")
    for nom, v in (('intime', intime), ('temoin', temoin),
                   ('capture', capture), ('marge intime-temoin', marge)):
        print(f"  {nom:<22} {quantiles(v)}")

    print("\n-- Combien de photos au-dessus de chaque seuil --")
    print(f"  {'seuil':>6} | {'marge intime':>13} | {'capture':>9}")
    for s in SEUILS:
        print(f"  {s:>6.2f} | {int((marge >= s).sum()):>13} | {int((capture >= s).sum()):>9}")

    idx = np.argsort(-marge)[:max(0, a.exemples)]
    print(f"\n-- Les {len(idx)} plus fortes marges (CHEMINS seuls, aucune image) --")
    for i in idx:
        print(f"  {marge[i]:+.3f}  {cles[i]}")

    if a.liste:
        sel = [i for i in np.argsort(-marge) if marge[i] >= a.seuil]
        if a.top:
            sel = sel[:a.top]
        out = {'quand': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
               'base': str(a.base), 'seuil': a.seuil,
               'modele': semantic.VERSION,
               'phrases_intimes': PHRASES_INTIMES,
               'phrases_temoins': PHRASES_TEMOINS,
               'phrases_captures': PHRASES_CAPTURES,
               'n_vecteurs': len(cles), 'n_retenues': len(sel),
               'top': a.top,
               # Ce fichier est une FILE DE REVUE, pas un verdict : le modele
               # ne sait pas separer l'intime de la plage (mesure du 17/09).
               # Il classe, un humain tranche.
               'verdict': False,
               'photos': [{'cle': cles[i], 'marge': round(float(marge[i]), 4),
                           'intime': round(float(intime[i]), 4),
                           'temoin': round(float(temoin[i]), 4),
                           'capture': round(float(capture[i]), 4)} for i in sel]}
        Path(a.liste).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                 encoding='utf-8')
        print(f"\nListe ecrite : {a.liste} — {len(sel)} photo(s) au-dessus de {a.seuil}")
    print("\nCE BANC NE MASQUE RIEN. Le masquage est un geste separe, et le")
    print("verdict reste humain, dans l'onglet Sensibles.")


if __name__ == '__main__':
    main()
