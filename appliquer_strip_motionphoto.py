#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Appliquer la regle 1 septies : retirer la VIDEO des Motion Photos comptees
──────────────────────────────────────────────────────────────────────────────

La regle (eval/DECISIONS.md, 29/08) : une Motion Photo ne garde que son image ;
la video embarquee est jetee — deliberement, REVERSIBLEMENT. La methode
(`verifier_strip_motionphoto.py`, banc du 29/08) : `exiftool -trailer:all=`,
image identique au pixel, JPEG valide, -61 % mesure.

CE QUE CE SCRIPT FAIT
  - lit `docs/motion_photos.json` (le compte TERMINE de `mesure_motion_photos`,
    01/09 : 2 441 Motion Photos, 8,64 Go de video) ;
  - retient les VRAIES Motion (`genre_effectif` : jamais les `sef-sans-video`) ;
  - passe `exiftool -trailer:all=` par LOTS via argfile UTF-8 BOM (les accents
    des chemins, comme `server._run_exiftool`) ; chaque fichier modifie laisse
    `photo.jpg_original` — la version complete, c'est l'UNDO ;
  - VERIFIE chaque fichier apres coup (existe, finit FF D9, a maigri,
    `_original` present, pas de `_exiftool_tmp` reste) ;
  - ecrit le manifeste `docs/strip_motionphoto_manifeste.json` (REPRENABLE :
    un fichier deja au manifeste, ou dont l'`_original` existe deja, est saute).

APERCU par defaut : rien n'est ecrit sans `--appliquer`. Et `--appliquer`
exige le serveur ARRETE (`appliquer_plan_annee.refus_d_ecriture`) — pas pour
`photos.db`, que ce script ne touche pas, mais parce que le serveur TAGUE :
deux ecrivains sur le MEME JPEG, c'est le fichier perdu.

UNDO : remettre `photo.jpg_original` a la place de `photo.jpg` (le manifeste
liste les paires) ; la purge des `_original` est un AUTRE geste, bat 43,
apres verification des stills (decision du 29/08).

    appliquer_strip_motionphoto.py [--appliquer] [--limite N] [--forcer]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import mesure_motion_photos as MM

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'motion_photos.json'
MANIFESTE = RACINE / 'docs' / 'strip_motionphoto_manifeste.json'
DB = RACINE / 'photos.db'
LOT = 100


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def exiftool():
    for c in sorted(RACINE.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return str(p)
    import shutil
    return shutil.which('exiftool')


def candidats(rapport):
    """[(chemin, entree)] des vraies Motion du compte, tries — jamais les
    `sef-sans-video`, jamais un fichier deja accompagne de son `_original`
    (etat (1) deja atteint, par ce script ou par l'ancien `repair_file`)."""
    out = []
    for k, ent in sorted(rapport.get('fichiers', {}).items()):
        if not isinstance(ent, dict) or 'err' in ent:
            continue
        if MM.genre_effectif(ent) in (None, 'sef-sans-video'):
            continue
        out.append((k, ent))
    return out


def deja_fait(chemin, manifeste):
    if chemin in manifeste.get('faits', {}):
        return 'au manifeste'
    if os.path.exists(str(chemin) + '_original'):
        return '_original deja present'
    return None


def strip_exiftool(exe, chemins):
    """Un lot par argfile UTF-8 BOM. Rend (code, stderr[:200])."""
    import tempfile
    args = ['-trailer:all='] + [str(c) for c in chemins]
    argfile = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                         encoding='utf-8-sig') as tf:
            tf.write('\n'.join(args))
            argfile = tf.name
        r = subprocess.run([str(exe), '-@', argfile], capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=1800)
        return r.returncode, (r.stderr or '').strip()[:200]
    finally:
        if argfile:
            try:
                os.unlink(argfile)
            except OSError:
                pass


def verifier_apres(chemin, avant):
    """None si tout va bien, sinon le grief. Ne repare rien."""
    try:
        apres = os.path.getsize(chemin)
    except OSError:
        return 'DISPARU'
    if os.path.exists(str(chemin) + '_exiftool_tmp'):
        return '_exiftool_tmp reste (fichier condamne sans intervention)'
    if not os.path.exists(str(chemin) + '_original'):
        return 'pas de _original : exiftool n a rien change'
    if apres >= avant:
        return 'pas plus petit (%d -> %d)' % (avant, apres)
    with open(chemin, 'rb') as f:
        f.seek(max(0, apres - 2))
        fin = f.read()
    if fin[-2:] != b'\xff\xd9':
        return 'ne finit pas par FF D9'
    return None


def charger_manifeste():
    try:
        d = json.loads(MANIFESTE.read_text(encoding='utf-8'))
        if isinstance(d.get('faits'), dict):
            return d
    except (OSError, ValueError):
        pass
    return {'faits': {}, 'rates': {}}


def ecrire_manifeste(m):
    MANIFESTE.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFESTE.with_suffix('.tmp')
    m['quand'] = time.strftime('%Y-%m-%d %H:%M:%S')
    tmp.write_text(json.dumps(m, ensure_ascii=True, indent=0), encoding='utf-8')
    os.replace(tmp, MANIFESTE)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('--appliquer', action='store_true')
    ap.add_argument('--limite', type=int, default=0, help='0 = tout')
    ap.add_argument('--forcer', action='store_true',
                    help='ecrire meme si le serveur semble vivant')
    a = ap.parse_args(argv)

    try:
        rapport = json.loads(RAPPORT.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        print('rapport illisible (%s) : lancer mesure_motion_photos d abord' % asc(e))
        return 2
    if not rapport.get('resume', {}).get('termine'):
        print('le compte n est pas TERMINE : relancer mesure_motion_photos jusqu au bout')
        return 2

    cands = candidats(rapport)
    manifeste = charger_manifeste()
    a_faire, sautes = [], 0
    for k, ent in cands:
        if deja_fait(k, manifeste):
            sautes += 1
            continue
        a_faire.append((k, ent))
    if a.limite:
        a_faire = a_faire[:a.limite]

    total_o = sum(e.get('t', 0) for _, e in a_faire)
    video_o = sum(e.get('v', 0) for _, e in a_faire)
    print('motion au compte : %d   deja faits/sautes : %d   a stripper : %d'
          % (len(cands), sautes, len(a_faire)))
    print('poids concerne : %.2f Go   video attendue : %.2f Go'
          % (total_o / 1073741824.0, video_o / 1073741824.0))

    if not a.appliquer:
        for k, ent in a_faire[:10]:
            print('  %s  %.1f Mo' % (asc(Path(k).name), ent.get('t', 0) / 1048576.0))
        print('APERCU : rien n est ecrit. --appliquer pour executer, serveur ARRETE.')
        return 0

    from appliquer_plan_annee import refus_d_ecriture  # paresseux : regle 3
    refus = refus_d_ecriture(DB, dry=False, forcer=a.forcer)
    if refus:
        print(refus)
        return 2
    exe = exiftool()
    if not exe:
        print('exiftool ABSENT')
        return 2

    faits, rates, recuperes = 0, 0, 0
    for i in range(0, len(a_faire), LOT):
        lot = a_faire[i:i + LOT]
        presents = [(k, e) for k, e in lot if os.path.exists(k)]
        if len(presents) < len(lot):
            for k, _ in lot:
                if not os.path.exists(k):
                    manifeste['rates'][k] = 'absent au moment du strip'
                    rates += 1
        if presents:
            code, err = strip_exiftool(exe, [k for k, _ in presents])
            if err:
                print('  exiftool (code %d) : %s' % (code, asc(err)), flush=True)
            for k, ent in presents:
                avant = ent.get('t', 0)
                grief = verifier_apres(k, avant)
                if grief:
                    manifeste['rates'][k] = grief
                    rates += 1
                    print('  RATE %s : %s' % (asc(Path(k).name), asc(grief)), flush=True)
                else:
                    apres = os.path.getsize(k)
                    manifeste['faits'][k] = {'avant': avant, 'apres': apres,
                                             'original': str(k) + '_original'}
                    faits += 1
                    recuperes += avant - apres
        ecrire_manifeste(manifeste)
        print('  ... %d strippes, %d rates, %.2f Go rendus'
              % (faits, rates, recuperes / 1073741824.0), flush=True)

    print('=' * 74)
    print('STRIP : %d faits, %d rates, %.2f Go rendus (les _original restent)'
          % (faits, rates, recuperes / 1073741824.0))
    print('manifeste : docs/strip_motionphoto_manifeste.json')
    print('la purge des _original est le bat 43, APRES verification des stills')
    return 0 if rates == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
