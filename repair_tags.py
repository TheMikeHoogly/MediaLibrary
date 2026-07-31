#!/usr/bin/env python3
"""
Marque tous les tags de l'index comme « à réécrire dans les fichiers ».
Au prochain démarrage du serveur, la boucle de maintenance réécrira les
métadonnées de chaque photo avec l'encodage corrigé (accents).
À lancer serveur arrêté.
"""

import json
import sys

sys.argv = sys.argv[:1]
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402

n = 0
for e in server.STORE.data.values():
    if not e.get('failed'):
        e['in_file'] = False
        n += 1

server.INDEX_FILE.write_text(
    json.dumps(server.STORE.data, ensure_ascii=False, indent=1),
    encoding='utf-8')

print(f"{n} photo(s) marquée(s) : leurs tags seront réécrits dans les fichiers")
print("au prochain démarrage du serveur (boucle de maintenance).")
