#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tire (telecharge) un modele Ollama nomme explicitement -- equivalent a
`ollama pull <modele>` depuis un terminal. Sert a preparer une comparaison
de modeles de vision (voir mesure_modele_vision.py) sans main humaine sur
le clavier.

N'ecrit rien dans l'index ni dans les photos : agit uniquement sur le cache
local d'Ollama. Idempotent -- si le modele est deja complet, `ollama pull`
le confirme en quelques secondes sans re-telecharger.

Usage (par l'agent banc) :
    diagnostic_tirer_modele.py --modele qwen3.5:4b
"""
import argparse
import subprocess


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--modele', required=True,
                    help='nom exact du modele Ollama a tirer')
    ap.add_argument('--timeout-s', type=int, default=560)
    a = ap.parse_args(argv)

    print('=== ollama pull', a.modele, '===')
    try:
        r = subprocess.run(['ollama', 'pull', a.modele], capture_output=True,
                           text=True, timeout=a.timeout_s)
        print(r.stdout or '')
        if r.stderr:
            print(r.stderr)
        if r.returncode != 0:
            print('  ! echec (code', r.returncode, ')')
            return 1
        print('  ok :', a.modele)
        return 0
    except subprocess.TimeoutExpired as e:
        print((e.stdout or b'').decode('utf-8', errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or ''))
        print('  ! timeout apres', a.timeout_s, 's -- relancer le meme ordre '
              'reprendra le telechargement la ou il en etait (blobs Ollama '
              'deja ecrits sur disque).')
        return 1
    except Exception as e:                                    # noqa: BLE001
        print('  ! exception :', e)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
