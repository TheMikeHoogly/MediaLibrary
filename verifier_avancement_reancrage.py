#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ou en est le bat 46 ? Une sonde, pas un travail.

`reancrer_corbeille.py` ne dit rien pendant les ~40 minutes ou il relit chaque
canonique sur le NAS : il ecrit chaque manifeste au fur et a mesure, mais ne
l annonce pas. Cette sonde compte, sans rien modifier, les manifestes qui
portent deja `canonique_avant` -- la marque du reancrage.
"""
import json, sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
plan = json.loads((RACINE / 'docs' / 'plan_rangement.json').read_text(encoding='utf-8'))
corb = Path(plan['corbeille'])
if not corb.exists():
    print('Corbeille absente.'); sys.exit(1)

total = faits = en_place = 0
for g in sorted(p for p in corb.iterdir() if p.is_dir()):
    m = g / 'manifeste.json'
    if not m.exists():
        continue
    total += 1
    try:
        d = json.loads(m.read_text(encoding='utf-8'))
    except Exception:
        continue
    if d.get('canonique_avant'):
        faits += 1
    elif d.get('canonique') and Path(d['canonique']).exists():
        en_place += 1

reste = total - faits - en_place
print(f'groupes                : {total}')
print(f'REANCRES (deja ecrits) : {faits}')
print(f'canonique deja en place: {en_place}')
print(f'restants a examiner    : {reste}')
if faits:
    print(f'avancement             : {100.0 * faits / max(1, total - en_place):.0f} %')
