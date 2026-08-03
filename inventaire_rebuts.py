#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventaire des rebuts attrapables PAR REGLE, sur toute la mediatheque (point 21).

Pourquoi ce script (et pas un detecteur ML) : la mesure a montre que le rebut
identifiable est attrapable par une REGLE (nom `Screenshot_`/`-WA`/`Scan_` ou
dossier `\\Screenshots\\`, `\\Scans\\`), et que le reste est subtil, non separable
par un zero-shot bon marche. Ce script chiffre et regroupe le rebut par regle,
pour dimensionner la future vue de triage — SANS GPU, SANS NAS, en LECTURE SEULE.

Il lit seulement les CLES de `photos.db` (table tags) ; il n'ouvre aucun fichier,
n'ecrit aucun tag, ne supprime rien. Le rangement par annee ayant disperse les
rebuts dates dans les dossiers `AAAA/`, on balaie tout, pas seulement `_A TRIER`.

Usage :
  python inventaire_rebuts.py            # -> docs/inventaire_rebuts.{md,json}
"""
import sys, json, sqlite3, collections
from pathlib import Path, PureWindowsPath

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import interet as I
import rangement_annee as ra

DB = SCRIPT_DIR / "photos.db"
OUT_MD = SCRIPT_DIR / "docs" / "inventaire_rebuts.md"
OUT_JSON = SCRIPT_DIR / "docs" / "inventaire_rebuts.json"
IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tif', '.tiff',
           '.heic', '.heif'}


def _emplacement(k):
    parts = PureWindowsPath(str(k)).parts
    if ra._atri_index(parts) is not None:
        return "_A TRIER"
    for p in parts:
        s = str(p)
        if len(s) == 4 and s.isdigit() and s.startswith(("19", "20")):
            return "dossier annee"
    return "ailleurs"


def main():
    if not DB.exists():
        print(f"x {DB} introuvable.")
        return 1
    cx = sqlite3.connect(str(DB), timeout=30.0)
    cx.execute("PRAGMA query_only=ON")
    cles = [k for (k,) in cx.execute("SELECT k FROM tags")]
    cx.close()
    total = len(cles)
    images = [k for k in cles if Path(str(k)).suffix.lower() in IMG_EXT]

    par_cat = collections.Counter()
    par_motif = collections.Counter()
    par_empl = collections.Counter()
    exemples = collections.defaultdict(list)
    pris = []
    for k in images:
        cat, motif = I.classer_regle(k)
        if not cat:
            continue
        pris.append({"key": k, "categorie": cat, "motif": motif,
                     "ou": _emplacement(k)})
        par_cat[cat] += 1
        # normalise le motif « dossier X » -> « dossier » pour l'agregat
        mot = motif if not (motif or "").startswith("dossier") else "dossier"
        par_motif[f"{cat}:{mot}"] += 1
        par_empl[_emplacement(k)] += 1
        if len(exemples[cat]) < 5:
            exemples[cat].append(PureWindowsPath(str(k)).name)

    n = len(pris)
    OUT_MD.parent.mkdir(exist_ok=True)
    md = ["# Inventaire des rebuts par regle — point 21", "",
          "Lecture seule (cles de `photos.db`). Aucun modele, aucun fichier ouvert.", "",
          f"- Entrees image dans l'index : **{len(images)}** (sur {total} au total)",
          f"- **Attrapables par regle : {n}** ({n/max(1,len(images))*100:.1f} % des images)",
          "", "## Par categorie", ""]
    for cat, c in par_cat.most_common():
        md.append(f"- **{cat}** : {c}  (ex. : {', '.join(exemples[cat][:3])})")
    md += ["", "## Par motif", ""]
    for mot, c in par_motif.most_common():
        md.append(f"- `{mot}` : {c}")
    md += ["", "## Ou vivent ces rebuts (le rangement les a disperses)", ""]
    for e, c in par_empl.most_common():
        md.append(f"- {e} : {c}")
    md += ["", "> Ces fichiers sont identifiables **sans detecteur**. La vue de",
           "> triage les regroupe par motif ; la suppression reste **humaine et",
           "> reversible** (`FileOps.delete` -> `.corbeille-rangement/`). Le rebut",
           "> subtil (recu photographie, photo ratee) n'est PAS ici : il releve de",
           "> la revue humaine, pas d'une regle.", ""]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(pris, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    print("=" * 66)
    print(f"  INVENTAIRE REBUTS PAR REGLE — {n} sur {len(images)} images"
          f" ({n/max(1,len(images))*100:.1f} %)")
    print("=" * 66)
    for cat, c in par_cat.most_common():
        print(f"  {cat:10s} {c:6d}   ex. {', '.join(exemples[cat][:2])}")
    print("  ou :", dict(par_empl))
    print(f"\n  Ecrit : {OUT_MD.name} + {OUT_JSON.name} (dans docs/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
