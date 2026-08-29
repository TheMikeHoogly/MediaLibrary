#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Efface les dossiers VIDES recenses par `inventaire_dossiers_vides.py`.

Lit `docs/dossiers_vides.json` (cle `vides`, du plus profond au moins profond)
et, pour chacun, RE-VERIFIE a l'instant qu'il est vide (aucune entree) avant
`os.rmdir` — qui refuse de toute facon un dossier non vide : rien ne peut etre
perdu ici, un dossier vide n'a pas de contenu a quarantiner. Les QUASI-VIDES
(scories) ne sont jamais touches. Journal `_journal_dossiers_vides.jsonl`.
Serveur allume ou non, indifferent (aucun fichier, aucune base). Sortie ASCII.

    effacer_dossiers_vides.py                 # DRY-RUN
    effacer_dossiers_vides.py --appliquer
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RAPPORT = ICI / 'docs' / 'dossiers_vides.json'
JOURNAL = ICI / '_journal_dossiers_vides.jsonl'


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true')
    a = ap.parse_args(argv)
    try:
        rap = json.loads(RAPPORT.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print('Rapport absent : lance d abord inventaire_dossiers_vides.py'); return 1
    vides = list(rap.get('vides') or [])
    print('%s : %d dossier(s) vide(s) recense(s) le %s sous %s (%d quasi-vide(s) ignores)'
          % ('APPLICATION' if a.appliquer else 'DRY-RUN', len(vides), rap.get('genere_le'),
             asc(rap.get('racine')), len(rap.get('quasi_vides') or [])))
    compte = {'ok': 0, 'skip': 0}
    vides.sort(key=lambda p: -len(p))       # profond d'abord, quoi qu'ait ecrit le rapport
    prevus = set(vides)
    for d in vides:
        try:
            entrees = os.listdir(d)
        except FileNotFoundError:
            print('  [skip] deja parti : %s' % asc(d)); compte['skip'] += 1; continue
        except OSError as e:
            print('  [skip] illisible : %s (%s)' % (asc(d), e)); compte['skip'] += 1; continue
        # en dry-run, un enfant lui-meme recense vide n'est pas un contenu
        restes = [e for e in entrees if a.appliquer or os.path.join(d, e) not in prevus]
        if restes:
            print('  [skip] PLUS VIDE (%d entree(s)) : %s' % (len(restes), asc(d))); compte['skip'] += 1; continue
        if a.appliquer:
            try:
                os.rmdir(d)
            except OSError as e:
                print('  [skip] rmdir refuse : %s (%s)' % (asc(d), e)); compte['skip'] += 1; continue
            with open(JOURNAL, 'a', encoding='utf-8') as jf:
                jf.write(json.dumps({'quand': time.strftime('%Y-%m-%d %H:%M:%S'), 'dossier': d},
                                    ensure_ascii=False) + '\n')
            print('  [ok]  %s' % asc(d))
        else:
            print('  [dry] %s' % asc(d))
        compte['ok'] += 1
    print('\nBilan : %s' % compte)
    if not a.appliquer:
        print('(dry-run - rien efface. Ajoute --appliquer.)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
