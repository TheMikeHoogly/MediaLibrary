#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qui est `llama-server.exe`, et pourquoi tient-il 13,7 Go ?

`mesure_memoire.py` (11/09 au soir, campagne en cours) : la machine a 0,8 Go
disponible sur 15,7, 5 Go dans le fichier d'echange, des centaines de pages
relues du disque par seconde — et UN processus, `llama-server.exe`, porte
**13,68 Go prives dont 7,54 hors de la RAM**, pour un modele annonce a 3,4 Go
(`modele.txt`, qwen3.5:4b) et un contexte demande de 4 096 jetons
(`ollama_generate`). Le serveur de la phototheque, lui, a 44 % de sa memoire
privee hors RAM : chaque parcours de l'index la relit sur le disque.

Ce diagnostic dit, sans rien changer :
  1. ce qu'Ollama declare avoir charge (`/api/ps` : taille, part en VRAM,
     contexte, expiration) et sa version ;
  2. chaque processus `llama-server` / `ollama` : son PARENT (qui l'a lance),
     depuis quand il tourne, sa memoire, ses fils — et, de sa ligne de
     commande, les SEULS drapeaux qui dimensionnent la memoire (contexte,
     paralleles, couches GPU, mmap, lot), jamais un chemin ;
  3. les variables `OLLAMA_*` vues par ce processus (nom=valeur, sauf ce qui
     ressemble a un secret).

  python diagnostic_ollama_memoire.py
"""

import json
import os
import sys
import time
import urllib.request

Go = 1024 ** 3

# Les drapeaux de llama.cpp / du runner d'Ollama qui DIMENSIONNENT la memoire.
DRAPEAUX = ('--ctx-size', '-c', '--parallel', '-np', '--n-gpu-layers', '-ngl',
            '--batch-size', '-b', '--ubatch-size', '-ub', '--no-mmap', '--mlock',
            '--cache-type-k', '-ctk', '--cache-type-v', '-ctv', '--flash-attn', '-fa',
            '--threads', '-t', '--kv-unified', '--ctx-size-draft', '--port',
            '--num-ctx', '--num-parallel', '--n-ctx', '--mmproj-offload',
            '--no-mmproj-offload', '--ollama-engine', 'runner')


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except Exception as e:                                        # noqa: BLE001
        return {'_erreur': f'{type(e).__name__}: {str(e)[:120]}'}


def ollama():
    print('== OLLAMA ==')
    v = _get('http://127.0.0.1:11434/api/version')
    print('  version :', v.get('version', v))
    ps = _get('http://127.0.0.1:11434/api/ps')
    if '_erreur' in ps:
        print('  /api/ps :', ps['_erreur'])
    for m in ps.get('models', []) or []:
        taille = m.get('size') or 0
        vram = m.get('size_vram') or 0
        print(f"  charge : {m.get('name')}  total {taille / Go:.2f} Go, "
              f"VRAM {vram / Go:.2f} Go, hors VRAM {(taille - vram) / Go:.2f} Go, "
              f"contexte {m.get('context_length')}, expire {m.get('expires_at')}")
        det = m.get('details') or {}
        print(f"           famille {det.get('family')} {det.get('parameter_size')} "
              f"{det.get('quantization_level')}")
    if not (ps.get('models') or []) and '_erreur' not in ps:
        print('  aucun modele charge')
    print()


def _drapeaux(cmd):
    garde = []
    for i, a in enumerate(cmd):
        cle = a.split('=', 1)[0]
        if cle in DRAPEAUX:
            if '=' in a:
                garde.append(a)
            elif i + 1 < len(cmd) and not cmd[i + 1].startswith('-') \
                    and not any(s in cmd[i + 1] for s in ('\\', '/', ':')):
                garde.append(f'{a} {cmd[i + 1]}')
            else:
                garde.append(a)
    return garde


def processus():
    try:
        import psutil
    except ImportError:
        print('psutil absent.')
        return
    print('== PROCESSUS llama / ollama ==')
    vus = 0
    for p in psutil.process_iter(['name']):
        nom = (p.info.get('name') or '').lower()
        if 'llama' not in nom and 'ollama' not in nom:
            continue
        vus += 1
        try:
            mi = p.memory_info()
            parent = p.parent()
            pnom = parent.name() if parent else '(aucun)'
            gp = parent.parent() if parent else None
            gpnom = gp.name() if gp else '(aucun)'
            age_h = (time.time() - p.create_time()) / 3600
            fils = p.num_threads()
            try:
                cmd = p.cmdline()
            except Exception:                                     # noqa: BLE001
                cmd = []
        except Exception as e:                                    # noqa: BLE001
            print(f'  {nom} (pid {p.pid}) : illisible ({type(e).__name__})')
            continue
        prive = getattr(mi, 'private', mi.vms)
        wset = getattr(mi, 'wset', mi.rss)
        print(f'  {nom} pid {p.pid} — lance par {pnom} (lui-meme par {gpnom}), '
              f'depuis {age_h:.1f} h, {fils} fils')
        print(f'      prive {prive / Go:.2f} Go, en RAM {wset / Go:.2f} Go, '
              f'pic en RAM {getattr(mi, "peak_wset", 0) / Go:.2f} Go, '
              f'fichier d echange {getattr(mi, "pagefile", 0) / Go:.2f} Go')
        print(f'      drapeaux : {" ".join(_drapeaux(cmd)) or "(aucun des drapeaux suivis)"}'
              f'  [{len(cmd)} arguments]')
        try:
            env = p.environ()
            vars_ = [f'{k}={v}' for k, v in sorted(env.items())
                     if k.upper().startswith(('OLLAMA', 'GGML', 'LLAMA'))
                     and not any(x in k.upper() for x in ('KEY', 'TOKEN', 'SECRET', 'PASS'))]
            print(f'      variables : {" ".join(vars_) or "(aucune OLLAMA_/GGML_/LLAMA_)"}')
        except Exception as e:                                    # noqa: BLE001
            print(f'      variables : illisibles ({type(e).__name__})')
    if not vus:
        print('  aucun')
    print()


def environnement():
    print('== VARIABLES OLLAMA_* vues par ce processus ==')
    n = 0
    for k, v in sorted(os.environ.items()):
        if not k.upper().startswith('OLLAMA'):
            continue
        n += 1
        secret = any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'PASS'))
        print(f'  {k}={"(masque)" if secret else v}')
    if not n:
        print('  aucune (Ollama tourne avec ses valeurs par defaut, ou les tient ailleurs)')
    print()


def main():
    ollama()
    processus()
    environnement()
    print('Ce diagnostic n ecrit rien et ne charge aucun modele.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
