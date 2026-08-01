#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scanner de conformite au design system « chambre noire ».

Scanne les constantes de page de server.py (APP_NAV_CSS, *_PAGE) et signale les
valeurs de couleur EN DUR interdites par la skill photo-ui : bleus iOS et gris
neutres froids. Les couleurs deja passees en var(--...) sont invisibles au
scanner (c'est le but). Rejouable, comme verifier_bat.py.

Usage :
    python verifier_ui_tokens.py            # rapport + code de sortie
    python verifier_ui_tokens.py --tout     # liste AUSSI les hex non bloquants

Code de sortie 1 si au moins un interdit dur subsiste (barriere CI).
"""
import re
import sys
from pathlib import Path

SRC = Path(__file__).with_name("server.py")

# Interdits DURS (photo-ui « Interdits explicites ») : bleus iOS + gris neutres
# froids reperes dans les pages historiques. En minuscules, sans '#'.
INTERDITS = {
    # bleus iOS / systeme
    "0a84ff": "bleu iOS",
    "5b9dff": "bleu iOS (accent nav)",
    "2a6df0": "bleu iOS (accent2 nav)",
    "7db4ff": "bleu iOS (dossiers)",
    "2a6df055": "bleu iOS (ombre)",
    "2a6df0": "bleu iOS",
    # gris NEUTRES froids (le noir du projet est chaud : --salle #0C0B0A)
    "0f0f0f": "gris neutre froid (fond)",
    "161616": "gris neutre froid (barre/carte)",
    "0e0e10": "gris neutre froid (fond nav)",
    "151517": "gris neutre froid",
    "1a1a1e": "gris neutre froid (carte)",
    "26262b": "gris neutre froid (ligne)",
    "9a9aa2": "gris neutre froid (texte muet)",
    "202020": "gris neutre froid",
    "555": "gris neutre (echec AA sur fond sombre)",
    "666": "gris neutre",
    "888": "gris neutre",
    "999": "gris neutre",
    "777": "gris neutre",
    "bbb": "gris neutre",
    "ccc": "gris neutre",
    "ddd": "gris neutre",
    "cbd": "gris neutre (.pchip)",
}

# Constantes a scanner : nom = """ ... """
CONST_RE = re.compile(r'^([A-Z][A-Z0-9_]*)\s*=\s*"""(.*?)"""', re.S | re.M)
# Entites HTML numeriques (&#128247;) : a retirer avant de chercher des hex.
ENTITY_RE = re.compile(r'&#x?[0-9a-fA-F]+;')
# Commentaires CSS /* ... */ et HTML <!-- ... --> : non rendus, a ignorer
# (sinon une mention « #0a84ff retire » dans un commentaire est faussement comptee).
COMMENT_RE = re.compile(r'/\*.*?\*/|<!--.*?-->', re.S)
HEX_RE = re.compile(r'#([0-9a-fA-F]{3,8})\b')
OUTLINE_NONE_RE = re.compile(r'outline\s*:\s*none')


def scan():
    txt = SRC.read_text(encoding="utf-8")
    show_all = "--tout" in sys.argv
    total_interdits = 0
    total_autres = 0
    pages = 0
    for m in CONST_RE.finditer(txt):
        name, body = m.group(1), m.group(2)
        if not (name.endswith("_PAGE") or "NAV" in name):
            continue
        pages += 1
        clean = COMMENT_RE.sub("", body)
        clean = ENTITY_RE.sub("", clean)
        interdits = []
        autres = []
        for hm in HEX_RE.finditer(clean):
            val = hm.group(1).lower()
            if val in INTERDITS:
                interdits.append(val)
            else:
                autres.append(val)
        outn = len(OUTLINE_NONE_RE.findall(clean))
        total_interdits += len(interdits)
        total_autres += len(autres)
        if interdits or outn or (show_all and autres):
            print(f"\n=== {name} ===")
            if interdits:
                from collections import Counter
                for v, c in Counter(interdits).most_common():
                    print(f"  INTERDIT x{c:<3} #{v:<8} {INTERDITS[v]}")
            if outn:
                print(f"  ATTENTION x{outn} 'outline:none' "
                      "(exige un remplacement dans la meme regle)")
            if show_all and autres:
                from collections import Counter
                autres_str = ", ".join(f"#{v}x{c}" for v, c
                                       in Counter(autres).most_common())
                print(f"  a revoir (non bloquant) : {autres_str}")
    print(f"\n{'='*52}")
    print(f"{pages} pages scannees. Interdits DURS : {total_interdits}. "
          f"Autres hex en dur : {total_autres}.")
    if total_interdits:
        print("ECHEC : des valeurs interdites subsistent (voir ci-dessus).")
        return 1
    print("OK : aucun interdit dur (bleus iOS / gris neutres) restant.")
    return 0


if __name__ == "__main__":
    sys.exit(scan())
