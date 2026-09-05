#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic en lecture seule : quels modeles Ollama sont deja tires en
local, et combien de VRAM le GPU expose au total (nvidia-smi). Sert a
chiffrer si un modele de vision plus gros que qwen3-vl:2b tiendrait dans le
budget VRAM arbitre (4096 Mo, voir ordonnanceur.py) avant de proposer d'en
changer. N'ecrit rien, ne lance aucun tagging."""
import json
import subprocess
import urllib.request


def main():
    print('=== ollama list (modeles deja tires) ===')
    try:
        r = subprocess.run(['ollama', 'list'], capture_output=True,
                           text=True, timeout=20)
        print(r.stdout or r.stderr)
    except Exception as e:                                    # noqa: BLE001
        print('echec ollama list :', e)

    print('=== GPU total (nvidia-smi) ===')
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,'
             'memory.free', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=10)
        print(r.stdout or r.stderr)
    except Exception as e:                                    # noqa: BLE001
        print('echec nvidia-smi :', e)

    print('=== /api/tags Ollama (detail) ===')
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',
                                    timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for m in data.get('models', []):
            print(' -', m.get('name'), '|', m.get('size'),
                  'octets |', (m.get('details') or {}).get('parameter_size'),
                  '|', (m.get('details') or {}).get('quantization_level'))
    except Exception as e:                                    # noqa: BLE001
        print('echec /api/tags :', e)


if __name__ == '__main__':
    main()
