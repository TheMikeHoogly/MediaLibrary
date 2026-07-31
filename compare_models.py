#!/usr/bin/env python3
"""
Compare la qualité de tagging de deux modèles sur les MÊMES photos.
Ne modifie ni les fichiers ni l'index — pur test de qualité.
Arrête le serveur avant (sinon les deux se battent pour le GPU).
Usage : compare_models.py [N]  (défaut 5)
"""

import json
import sys
import time
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
MODELS = ["qwen3-vl:2b", "qwen3-vl:4b"]

sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402

imgs = sorted([f for f in server.UPLOAD_DIR.iterdir()
               if f.is_file() and f.suffix.lower() in server.IMAGE_EXT
               and not f.name.startswith(('.', '@', '#'))],
              key=lambda f: f.stat().st_mtime, reverse=True)[:N]
if not imgs:
    print("Aucune photo dans Uploads.")
    sys.exit(1)

print(f"\n=== Comparaison {' vs '.join(MODELS)} sur {len(imgs)} photo(s) ===")
results = {m: [] for m in MODELS}
for m in MODELS:
    server.MODEL = m
    print(f"\n───── {m} ─────")
    for f in imgs:
        t0 = time.time()
        try:
            raw = server.ollama_generate(server.image_to_b64(f))
            kw_fr, kw_en, desc = server.parse_tags(raw)
            dur = round(time.time() - t0, 1)
            results[m].append({"photo": f.name, "duree_s": dur,
                               "kw_fr": kw_fr, "kw_en": kw_en,
                               "description": desc})
            print(f"  {f.name} — {dur}s")
            print(f"    FR : {', '.join(kw_fr)}")
            print(f"    «{desc}»")
        except Exception as e:
            results[m].append({"photo": f.name, "erreur": str(e)})
            print(f"  {f.name} — ERREUR : {e}")

out = Path(__file__).resolve().parent / "compare_report.txt"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
               encoding="utf-8")
print(f"\nRapport : {out}")
print("Envoie ce fichier à Claude pour l'analyse comparative.")
