#!/usr/bin/env python3
"""
Audit d'intégrité de toutes les photos du dossier Uploads :
- lecture complète des pixels (détecte fichiers illisibles ou tronqués)
- validation des métadonnées via ExifTool (détecte EXIF endommagé)
Produit photos_report.txt avec la liste des fichiers à supprimer si besoin.
Peut tourner pendant que le serveur est actif (lecture seule).
"""

import json
import sys
from pathlib import Path

sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402

server.EXIFTOOL = server.ensure_exiftool()

try:
    from PIL import Image
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    PIL_OK = True
except ImportError:
    PIL_OK = False
    print("⚠ Pillow absent : test de lecture des pixels impossible")

imgs = sorted([f for f in server.UPLOAD_DIR.iterdir()
               if f.is_file() and f.suffix.lower() in server.IMAGE_EXT
               and not f.name.startswith(('.', '@', '#'))])
print(f"\n=== Audit de {len(imgs)} photo(s) dans {server.UPLOAD_DIR} ===\n")

unreadable = []   # pixels illisibles / fichier tronqué
bad_meta = []     # image OK mais métadonnées endommagées
ok = 0

# 1) lecture des pixels
readable = []
for f in imgs:
    if not PIL_OK:
        readable.append(f)
        continue
    try:
        with Image.open(f) as im:
            im.verify()
        with Image.open(f) as im:
            im.load()   # lecture complète : détecte les fichiers tronqués
        readable.append(f)
    except Exception as e:
        unreadable.append((f.name, str(e)[:150]))
        print(f"  ✗ ILLISIBLE : {f.name} — {str(e)[:80]}")

# 2) validation des métadonnées (exiftool -validate)
if server.EXIFTOOL:
    for i in range(0, len(readable), 40):
        chunk = readable[i:i + 40]
        args = ["-json", "-q", "-m", "-validate", "-warning", "-error",
                "-charset", "filename=UTF8"] + [str(p) for p in chunk]
        try:
            r = server._run_exiftool(args, timeout=600)
            for item in json.loads(r.stdout or "[]"):
                name = Path(item.get("SourceFile", "")).name
                errs = []
                for key in ("Error", "Warning"):
                    v = item.get(key)
                    if isinstance(v, list):
                        errs += [str(x) for x in v]
                    elif v:
                        errs.append(str(v))
                serious = [x for x in errs
                           if 'error' in x.lower() or 'bad' in x.lower()
                           or 'corrupt' in x.lower() or 'invalid' in x.lower()
                           or 'truncated' in x.lower()]
                if serious:
                    bad_meta.append((name, '; '.join(serious)[:200]))
                    print(f"  ⚠ EXIF endommagé : {name} — {serious[0][:80]}")
        except Exception as e:
            print(f"  ⚠ Validation exiftool échouée: {e}")
else:
    print("⚠ ExifTool absent : validation des métadonnées sautée")

ok = len(imgs) - len(unreadable) - len(bad_meta)

lines = []
lines.append("RAPPORT D'INTÉGRITÉ DES PHOTOS")
lines.append(f"Dossier : {server.UPLOAD_DIR}")
lines.append(f"Total : {len(imgs)} — OK : {ok} — Illisibles : {len(unreadable)}"
             f" — EXIF endommagé : {len(bad_meta)}")
lines.append("")
if unreadable:
    lines.append("=== PHOTOS ILLISIBLES (endommagées, candidates à la suppression) ===")
    for name, err in unreadable:
        lines.append(f"{server.UPLOAD_DIR / name}")
        lines.append(f"    → {err}")
    lines.append("")
if bad_meta:
    lines.append("=== IMAGE VISIBLE MAIS MÉTADONNÉES ENDOMMAGÉES ===")
    lines.append("(la photo s'affiche ; ses métadonnées EXIF sont corrompues —")
    lines.append(" suppression facultative, les tags restent dans la galerie)")
    for name, err in bad_meta:
        lines.append(f"{server.UPLOAD_DIR / name}")
        lines.append(f"    → {err}")
    lines.append("")
if not unreadable and not bad_meta:
    lines.append("Aucun fichier à problème 🎉")

out = Path(__file__).resolve().parent / "photos_report.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"\n{len(unreadable)} illisible(s), {len(bad_meta)} EXIF endommagé(s), {ok} OK")
print(f"Rapport : {out}")
