#!/usr/bin/env python3
"""
Test qualité du tagging IA : tague les N photos les plus récentes du dossier
Uploads, relit les métadonnées écrites dans les fichiers, et produit
tagging_report.txt. Usage : test_tagging.py [N]  (défaut 5)
NB : arrête le serveur avant de lancer ce test (accès concurrent à l'index).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
sys.argv = sys.argv[:1]  # sinon server.py prend N pour un dossier d'uploads !

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402

print(f"\n=== Test qualité tagging sur {N} photo(s), modèle {server.MODEL} ===\n")
server.EXIFTOOL = server.ensure_exiftool()

imgs = sorted(
    [f for f in server.UPLOAD_DIR.iterdir()
     if f.is_file() and f.suffix.lower() in server.IMAGE_EXT],
    key=lambda f: f.stat().st_mtime, reverse=True)[:N]

if not imgs:
    print("Aucune photo dans le dossier Uploads.")
    sys.exit(1)

report = []
for f in imgs:
    entry = {"photo": f.name, "taille": server.human_size(f.stat().st_size)}
    print(f"-> {f.name}")
    t0 = time.time()
    try:
        b64 = server.image_to_b64(f)
        raw = server.ollama_generate(b64)
        kw_fr, kw_en, desc = server.parse_tags(raw)
        merged = list(dict.fromkeys(kw_fr + kw_en))
        ok = server.write_metadata(f, merged, desc)
        entry.update({
            "duree_s": round(time.time() - t0, 1),
            "kw_fr": kw_fr,
            "kw_en": kw_en,
            "description": desc,
            "ecrit_dans_fichier": ok,
        })
        # Relecture de contrôle : ce qui est réellement DANS le fichier
        if ok and server.EXIFTOOL:
            r = server._run_exiftool(
                ["-json", "-XMP-dc:Subject", "-IPTC:Keywords",
                 "-XMP-dc:Description", "-charset", "filename=UTF8", str(f)],
                timeout=120)
            items = json.loads(r.stdout or "[]")
            entry["relecture_fichier"] = items[0] if items else "VIDE !"
        elif ok:
            # plan B : relecture via piexif (XPKeywords)
            try:
                import piexif
                back = piexif.load(str(f))
                raw_kw = back['0th'].get(piexif.ImageIFD.XPKeywords)
                if raw_kw:
                    entry["relecture_fichier"] = {
                        "XPKeywords": bytes(raw_kw).decode('utf-16le').rstrip('\x00')}
                else:
                    entry["relecture_fichier"] = "VIDE !"
            except Exception as e2:
                entry["relecture_fichier"] = f"relecture impossible: {e2}"
        # Mise à jour de l'index pour que le serveur ne re-tague pas
        server.STORE.set(f.name, {"kw_fr": kw_fr, "kw_en": kw_en, "desc": desc,
                                  "in_file": ok, "at": time.time()})
        print(f"   OK {entry['duree_s']}s -- FR: {', '.join(kw_fr)}")
        print(f"     EN: {', '.join(kw_en)}")
        print(f"     «{desc}»  (écrit dans fichier: {ok})\n")
    except Exception as e:
        entry["erreur"] = str(e)
        print(f"   ECHEC {e}\n")
    report.append(entry)

out = Path(__file__).resolve().parent / "tagging_report.txt"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Rapport écrit : {out}")
print("Envoie ce fichier à Claude pour évaluation de la qualité.")
