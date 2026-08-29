#!/usr/bin/env python3
"""Quelle reparation EXIF ne jette PAS le trailer Samsung ?

Constat du 29/08 : sur un Motion Photo Samsung, ExifTool refuse l'ecriture
(« Error reading OtherImageStart data in IFD0 »), `server.repair_file` fait
alors `-all= -tagsfromfile @ -all:all -unsafe` — et le fichier perd son
trailer : la video embarquee (2 a 3 Mo) et le profil ICC. 14 photos de 2024
l'ont subi le 28/08 (le `_original` est intact a cote), et les originaux de
`Photos Mike\\2024` bien avant.

Ce banc COPIE un Motion Photo du Takeout dans %TEMP%, y applique chaque
commande candidate, puis mesure ce qui reste : taille, `SEFT` en fin de
fichier, `ftyp` (video), profil ICC, nombre de tags, et si les mots-cles de
test ont atterri. Il ne touche JAMAIS au fichier source. Sortie ASCII.

    verifier_reparation_exif.py --source b64:<chemin du Motion Photo>
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
MOTS = ['banc_a', 'banc_b']
DESC = 'description de banc'


def exiftool():
    for c in sorted(ICI.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return p
    return None


def deb64(v):
    if v.startswith('b64:'):
        return base64.urlsafe_b64decode(v[4:] + '=' * (-len(v[4:]) % 4)).decode('utf-8')
    return v


def run(exe, args, timeout=180):
    with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                     encoding='utf-8-sig') as tf:
        tf.write('\n'.join(args))
        af = tf.name
    try:
        return subprocess.run([str(exe), '-@', af], capture_output=True,
                              text=True, encoding='utf-8', errors='replace',
                              timeout=timeout)
    finally:
        os.unlink(af)


def mesure(exe, chemin):
    taille = os.path.getsize(chemin)
    with open(chemin, 'rb') as f:
        f.seek(max(0, taille - (16 << 20)))
        q = f.read()
    r = run(exe, ['-j', '-G1', '-s', '-a', '-q', '-q', '-charset',
                  'filename=UTF8', str(chemin)])
    try:
        d = json.loads(r.stdout or '[{}]')[0]
    except ValueError:
        d = {}
    noms = {k for k in d if ':' in k}
    subj = str(d.get('XMP-dc:Subject', '')) + str(d.get('IPTC:Keywords', ''))
    return {
        'taille': taille,
        'SEFT': q.endswith(b'SEFT'),
        'ftyp': q.count(b'ftyp'),
        'ICC': any(k.startswith('ICC') for k in noms),
        'MotionPhotoVideo': 'Google:MotionPhotoVideo' in noms
                            or 'Samsung:EmbeddedVideoFile' in noms
                            or 'Trailer:Samsung' in str(d.get('ExifTool:Warning', '')),
        'tags': len(noms),
        'mots_ok': all(m in subj for m in MOTS),
        'avert': str(d.get('ExifTool:Warning', ''))[:90],
    }


# ── les candidats ───────────────────────────────────────────────────────────
# Chaque candidat est une liste d'ETAPES ; une etape = liste d'arguments
# exiftool (le chemin est ajoute a la fin). L'ecriture des tags de banc est
# l'etape ECRIRE, identique a `server.write_metadata`.
ECRIRE = ['-overwrite_original', '-q', '-m', '-charset', 'filename=UTF8',
          '-codedcharacterset=utf8'] + ['-MWG:Keywords=%s' % m for m in MOTS] \
         + ['-MWG:Description=' + DESC, '-XPKeywords=' + '; '.join(MOTS)]
ECRIRE_SANS_EXIF = ['-overwrite_original', '-q', '-m', '-charset',
                    'filename=UTF8', '-codedcharacterset=utf8'] \
    + ['-XMP-dc:Subject+=%s' % m for m in MOTS] \
    + ['-IPTC:Keywords+=%s' % m for m in MOTS] \
    + ['-XMP-dc:Description=' + DESC, '-IPTC:Caption-Abstract=' + DESC]

CANDIDATS = [
    ('0. ecriture normale (temoin : doit ECHOUER sur ce fichier)',
     [ECRIRE]),
    ('A. reparation ACTUELLE : -all= -tagsfromfile @ -all:all -unsafe, puis ecrire',
     [['-all=', '-tagsfromfile', '@', '-all:all', '-unsafe', '-charset', 'filename=UTF8'],
      ECRIRE]),
    ('B. reparation en GARDANT le trailer : -all= --trailer:all ..., puis ecrire',
     [['-all=', '--trailer:all', '-tagsfromfile', '@', '-all:all', '-unsafe',
       '-charset', 'filename=UTF8'], ECRIRE]),
    ('C. pas de reparation : ecrire XMP+IPTC seulement (l EXIF n est pas reecrit)',
     [ECRIRE_SANS_EXIF]),
    ('D. ecriture normale avec -F (recalage des offsets EXIF)',
     [['-F'] + ECRIRE]),
    ('E. retirer les deux tags fautifs, puis ecrire',
     [['-overwrite_original', '-q', '-m', '-charset', 'filename=UTF8',
       '-IFD0:OtherImageStart=', '-IFD0:OtherImageLength='], ECRIRE]),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    a = ap.parse_args(argv)
    src = Path(deb64(a.source))
    exe = exiftool()
    print('exiftool : %s' % (exe or 'ABSENT'))
    print('source   : %s' % src.name)
    if not exe or not src.exists():
        print('  banc impossible : exiftool ou source absent')
        return 2
    ref = mesure(exe, src)
    print('reference: %s' % ref)
    print('=' * 74)
    tmp = Path(tempfile.mkdtemp(prefix='banc_repar_'))
    verdicts = []
    try:
        for i, (nom, etapes) in enumerate(CANDIDATS):
            c = tmp / ('%d_%s' % (i, src.name))
            shutil.copy2(src, c)
            print(nom)
            ok = True
            for et in etapes:
                r = run(exe, et + [str(c)])
                err = (r.stderr or '').strip().replace('\n', ' | ')[:160]
                print('   code %d %s' % (r.returncode, err))
                if r.returncode != 0:
                    ok = False
            m = mesure(exe, c)
            garde = m['SEFT'] and m['ftyp'] >= ref['ftyp'] and m['ICC'] == ref['ICC']
            verdict = ('GARDE TOUT + tags ecrits' if ok and garde and m['mots_ok']
                       else 'garde tout, tags NON ecrits' if garde and not m['mots_ok']
                       else 'PERD le trailer/ICC, tags ecrits' if m['mots_ok']
                       else 'perd et n ecrit pas')
            verdicts.append((nom[:2], verdict))
            print('   apres : taille %d (%+d)  SEFT=%s ftyp=%s ICC=%s tags=%d mots=%s'
                  % (m['taille'], m['taille'] - ref['taille'], m['SEFT'], m['ftyp'],
                     m['ICC'], m['tags'], m['mots_ok']))
            if m['avert']:
                print('   avert : %s' % m['avert'])
            print('   => %s' % verdict)
            print('-' * 74)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('VERDICTS')
    for k, v in verdicts:
        print('  %s %s' % (k, v))
    return 0


if __name__ == '__main__':
    sys.exit(main())
