#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purger les `*.jpg_original` laisses par le strip — l'etape (2) de 1 septies
──────────────────────────────────────────────────────────────────────────────

Apres le strip (bat 42), chaque Motion Photo strippee laisse
`photo.jpg_original` : sa version COMPLETE, l'undo. Une fois les stills
verifies a l'oeil (decision du 29/08), ces versions completes sont le poids a
retirer — ~8,6 Go pour 2 441 fichiers.

RIEN N'EST SUPPRIME : les `_original` sont DEPLACES vers
`<racine>\\.corbeille-rangement\\strip_motionphoto_<date>\\` avec un manifeste,
comme les autres quarantaines du projet — le bat 24 les purgera avec le reste,
et d'ici la tout se remet en place a la main.

Sources, deux et seulement deux :
  - le manifeste du strip (`docs/strip_motionphoto_manifeste.json`) ;
  - avec `--aussi-racine b64:<dossier>`, les `*.jpg_original` TROUVES sous ce
    dossier (les 125 de `_A TRIER`, decision du 29/08 : ils sont l'etat (1)
    de l'ancien `repair_file`, leur purge est l'etape (2)). Jamais de
    balayage par defaut.

APERCU par defaut ; `--appliquer` pour deplacer. Serveur : indifferent (aucun
`.jpg` ni la base ne sont touches — on ne deplace que des `_original`).

    appliquer_purge_motionphoto.py [--appliquer] [--aussi-racine b64:...]
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
MANIFESTE = RACINE / 'docs' / 'strip_motionphoto_manifeste.json'


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def deb64(v):
    if str(v).startswith('b64:'):
        s = str(v)[4:]
        return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode('utf-8')
    return str(v)


def originaux_du_manifeste():
    try:
        d = json.loads(MANIFESTE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return sorted(e.get('original') for e in d.get('faits', {}).values()
                  if isinstance(e, dict) and e.get('original'))


def originaux_sous(racine):
    """Les `*.jpg_original` sous `racine` — jamais dans un dossier cache."""
    out = []
    for dirpath, dirnames, filenames in os.walk(racine):
        dirnames[:] = [d for d in dirnames if not d.startswith(('.', '@', '#'))]
        for f in filenames:
            if f.lower().endswith(('.jpg_original', '.jpeg_original')):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def racine_photos(chemin):
    """La racine du fonds pour un chemin donne : le dossier qui contient
    `.corbeille-rangement`, sinon le parent le plus haut qui s'appelle
    `Photos` ; a defaut, le dossier du fichier."""
    p = Path(chemin)
    for parent in p.parents:
        if (parent / '.corbeille-rangement').exists():
            return parent
    for parent in p.parents:
        if parent.name.lower() == 'photos':
            return parent
    return p.parent


def destination(chemin, corbeille, racine):
    try:
        rel = Path(chemin).relative_to(racine)
    except ValueError:
        rel = Path(Path(chemin).name)
    return corbeille / rel


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('--appliquer', action='store_true')
    ap.add_argument('--aussi-racine', default='',
                    help='b64:<dossier> — y ramasser aussi les *.jpg_original')
    a = ap.parse_args(argv)

    sources = [('manifeste', c) for c in originaux_du_manifeste()]
    if a.aussi_racine:
        rac = deb64(a.aussi_racine)
        if not os.path.isdir(rac):
            print('racine introuvable : %s' % asc(rac))
            return 2
        vus = {c for _, c in sources}
        sources += [('racine', c) for c in originaux_sous(rac) if c not in vus]

    presents = [(o, c) for o, c in sources if os.path.exists(c)]
    octets = sum(os.path.getsize(c) for _, c in presents)
    print('originaux au manifeste : %d   via --aussi-racine : %d   presents : %d'
          % (sum(1 for o, _ in sources if o == 'manifeste'),
             sum(1 for o, _ in sources if o == 'racine'), len(presents)))
    print('poids a mettre en quarantaine : %.2f Go' % (octets / 1073741824.0))
    if not presents:
        print('rien a purger')
        return 0

    rac = racine_photos(presents[0][1])
    corbeille = rac / '.corbeille-rangement' / ('strip_motionphoto_' + time.strftime('%Y%m%d_%H%M%S'))
    print('quarantaine : %s' % asc(corbeille))

    if not a.appliquer:
        for _, c in presents[:10]:
            print('  %s' % asc(Path(c).name))
        print('APERCU : rien n est deplace. --appliquer pour executer.')
        return 0

    deplaces, rates = 0, 0
    manifeste_q = []
    for _, c in presents:
        dst = destination(c, corbeille, rac)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(c, dst)
            manifeste_q.append({'de': str(c), 'vers': str(dst)})
            deplaces += 1
        except OSError as e:
            print('  RATE %s : %s' % (asc(Path(c).name), asc(e)), flush=True)
            rates += 1
    corbeille.mkdir(parents=True, exist_ok=True)
    (corbeille / 'manifeste.json').write_text(
        json.dumps({'quand': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'deplacements': manifeste_q}, ensure_ascii=True, indent=0),
        encoding='utf-8')
    print('=' * 74)
    print('PURGE : %d deplaces, %d rates, %.2f Go en quarantaine'
          % (deplaces, rates, octets / 1073741824.0))
    print('reversible : manifeste.json dans le dossier de quarantaine')
    return 0 if rates == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
