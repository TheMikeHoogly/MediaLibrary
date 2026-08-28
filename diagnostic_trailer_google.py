#!/usr/bin/env python3
"""Ce que perd une photo entre Google et le NAS : le TRAILER.

Le 29/08, `verifier_photos_google` comptait 199 fichiers ou le NAS est PLUS
PETIT que Google — tous sous `_A TRIER\\Google porte mieux`, c'est-a-dire des
copies FAITES depuis Google. Une copie ne retrecit pas toute seule : c'est
notre ecriture XMP (exiftool) qui a rogne le fichier apres coup.

Ce banc MESURE, pour les N plus gros deficits du rapport JSON :
  - la taille chez Google, sur le NAS, et le deficit ;
  - si un `nom.jpg_original` (sauvegarde de `repair_file`) existe a cote, et
    sa taille — c'est lui qui porte l'octet perdu, si quelqu'un le porte ;
  - la signature du trailer Samsung (`SEFT` en fin de fichier) et la presence
    d'une video embarquee (`ftyp` MP4, photo animee) des deux cotes ;
  - la difference de tags exiftool (groupes:noms) entre les deux fichiers.

Lecture seule. Ne touche a rien. Sortie ASCII (console cp1252 de l'agent).

    diagnostic_trailer_google.py --rapport=_rapport_google_final.json --n=12
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RX = re.compile(r'taille (\d+) chez Google, (\d+) sur le NAS')


def exiftool():
    for c in sorted(ICI.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return p
    return None


def signatures(chemin, queue=64 << 20):
    """(taille, SEFT en fin de fichier, nb de 'ftyp' dans la queue)."""
    try:
        taille = os.path.getsize(chemin)
        with open(chemin, 'rb') as f:
            f.seek(max(0, taille - queue))
            data = f.read()
    except OSError as e:
        return None, None, None, str(e)
    return taille, data.endswith(b'SEFT'), data.count(b'ftyp'), ''


def tags(exe, chemin):
    """Ensemble 'Groupe1:Nom' + avertissements, via exiftool -j."""
    if not exe:
        return set(), ['(exiftool absent)']
    try:
        r = subprocess.run([str(exe), '-j', '-G1', '-s', '-a', '-q', '-q',
                            '-charset', 'filename=UTF8', str(chemin)],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=120)
        d = json.loads(r.stdout or '[{}]')[0]
    except Exception as e:  # noqa: BLE001 - un banc rend, il ne meurt pas
        return set(), ['erreur exiftool: %s' % str(e)[:120]]
    noms = {k for k in d if ':' in k}
    warn = [str(v) for k, v in d.items() if k.endswith(':Warning')]
    return noms, warn


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--rapport', default='_rapport_google_final.json')
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--petits', type=int, default=4,
                    help='en plus des N plus gros, ce nombre parmi les PETITS deficits')
    a = ap.parse_args(argv)

    d = json.load(open(ICI / a.rapport, encoding='utf-8'))
    petits = []
    for e in d['par_verdict'].get('PROBABLE', []):
        m = RX.search(e.get('detail', ''))
        if not m:
            continue
        g, n = int(m.group(1)), int(m.group(2))
        if n < g:
            petits.append((g - n, e))
    petits.sort(key=lambda x: -x[0])
    print('NAS plus petit que Google : %d fichier(s) dans %s' % (len(petits), a.rapport))
    choix = petits[:a.n] + petits[-a.petits:] if len(petits) > a.n else petits
    exe = exiftool()
    print('exiftool : %s' % (exe or 'ABSENT'))
    print('=' * 74)
    orig_vus = orig_portent = 0
    for deficit, e in choix:
        cg, cn = e['chemin_google'], e['chemin_nas']
        tg, seft_g, ftyp_g, err_g = signatures(cg)
        tn, seft_n, ftyp_n, err_n = signatures(cn)
        print(asc(e['nom']))
        print('  Google : %s o  SEFT=%s ftyp=%s %s' % (tg, seft_g, ftyp_g, err_g))
        print('  NAS    : %s o  SEFT=%s ftyp=%s %s  (deficit %s o)'
              % (tn, seft_n, ftyp_n, err_n, deficit))
        orig = cn + '_original'
        if os.path.exists(orig):
            orig_vus += 1
            to = os.path.getsize(orig)
            porte = (to == tg)
            orig_portent += porte
            print('  _original : %s o  %s' % (to, 'IDENTIQUE a Google en taille' if porte else 'taille differente de Google'))
        else:
            print('  _original : aucun')
        sg, wg = tags(exe, cg)
        sn, wn = tags(exe, cn)
        seul_g = sorted(sg - sn)
        seul_n = sorted(sn - sg)
        print('  tags seulement chez Google (%d) : %s' % (len(seul_g), asc(', '.join(seul_g[:14]))))
        print('  tags seulement sur le NAS (%d)  : %s' % (len(seul_n), asc(', '.join(seul_n[:14]))))
        for w in wg:
            print('  avert. Google : %s' % asc(w)[:110])
        for w in wn:
            print('  avert. NAS    : %s' % asc(w)[:110])
        print('-' * 74)
    print('sauvegardes _original trouvees : %d, dont %d de la taille de Google'
          % (orig_vus, orig_portent))
    return 0


if __name__ == '__main__':
    sys.exit(main())
