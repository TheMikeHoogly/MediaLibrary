#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quelle methode retire la VIDEO d'une Motion Photo sans toucher a l'IMAGE ?

Regle du projet (eval/DECISIONS.md, 29/08) : une Motion Photo ne garde que son
image fixe ; la video embarquee (trailer Samsung `SEFT` / `MotionPhoto` Google,
un MP4 `ftyp` colle derriere le JPEG) est jetee. Ce banc teste plusieurs
methodes sur une COPIE et MESURE, pour chacune :
  - taille avant/apres et octets economises ;
  - le JPEG reste-t-il VALIDE (se termine par FF D9, se decode) ;
  - le trailer a-t-il DISPARU (plus de `SEFT`, plus de `ftyp`) ;
  - l'IMAGE est-elle INTACTE au pixel pres (decodage compare a la source).

Ne touche JAMAIS au fichier source. Sortie ASCII (console cp1252 de l'agent).

    verifier_strip_motionphoto.py --source b64:<chemin d'une Motion Photo complete>
"""
import argparse
import base64
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent

try:
    from PIL import Image
    HAS_PIL = True
except Exception:  # noqa: BLE001
    HAS_PIL = False


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


def lire(chemin, n=None):
    with open(chemin, 'rb') as f:
        return f.read() if n is None else f.read(n)


def signatures(chemin):
    """(taille, finit par FFD9, contient SEFT, nb de 'ftyp')."""
    taille = os.path.getsize(chemin)
    data = lire(chemin)
    return taille, data[-2:] == b'\xff\xd9', (b'SEFT' in data[-4 << 20:]), data.count(b'ftyp')


def pixels_hash(chemin):
    """SHA1 des pixels decodes, ou None si PIL absent / decodage impossible.
    PIL ne lit que la portion JPEG : le trailer video est ignore, donc la
    source et un strip correct doivent rendre le MEME hash."""
    if not HAS_PIL:
        return None
    try:
        with Image.open(chemin) as im:
            im = im.convert('RGB')
            return hashlib.sha1(im.tobytes()).hexdigest()
    except Exception:  # noqa: BLE001
        return 'illisible'


def offset_video(data):
    """Debut du MP4 colle derriere le JPEG : l'octet du champ TAILLE (4 o) qui
    precede le premier `ftyp`. Le still JPEG n'a aucune raison de contenir un
    `....ftyp` a une frontiere de boite ; on prend le premier apres un SOI."""
    i = data.find(b'ftyp')
    if i < 8:
        return None
    return i - 4  # la boite ftyp commence par sa taille sur 4 octets


# ── methodes candidates ──────────────────────────────────────────────────────
def m_exiftool_trailer(exe, chemin):
    """exiftool -trailer:all= : retire le trailer si la version le supporte."""
    r = subprocess.run([str(exe), '-trailer:all=', '-overwrite_original',
                        '-q', '-q', str(chemin)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=120)
    return r.returncode == 0, (r.stderr or '').strip()[:120]


def m_troncature(exe, chemin):
    """Troncature sans perte au debut du MP4 (octets du still conserves tels
    quels : ni re-encodage, ni reecriture des metadonnees)."""
    data = lire(chemin)
    off = offset_video(data)
    if off is None:
        return False, 'pas de ftyp trouve'
    with open(chemin, 'r+b') as f:
        f.truncate(off)
    return True, 'tronque a %d' % off


def m_pillow(exe, chemin):
    """Dernier recours : re-encodage PIL (PERD un peu de qualite)."""
    if not HAS_PIL:
        return False, 'PIL absent'
    with Image.open(chemin) as im:
        im = im.convert('RGB')
        im.save(chemin, 'JPEG', quality=95)
    return True, 're-encode q95 (avec perte)'


CANDIDATS = [
    ('A. exiftool -trailer:all=', m_exiftool_trailer),
    ('B. troncature sans perte au ftyp', m_troncature),
    ('C. re-encode PIL q95 (temoin avec perte)', m_pillow),
]


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    a = ap.parse_args(argv)
    src = Path(deb64(a.source))
    exe = exiftool()
    print('exiftool : %s' % (exe or 'ABSENT'))
    print('PIL      : %s' % ('oui' if HAS_PIL else 'NON (pas de comparaison pixel)'))
    print('source   : %s' % asc(src.name))
    if not src.exists():
        print('  source introuvable'); return 2
    t0, ok0, seft0, ftyp0 = signatures(src)
    ref_px = pixels_hash(src)
    print('reference: %d o  finitFFD9=%s SEFT=%s ftyp=%s  pixels=%s'
          % (t0, ok0, seft0, ftyp0, (ref_px or 'n/a')[:12]))
    print('=' * 74)
    tmp = Path(tempfile.mkdtemp(prefix='banc_mp_'))
    verdicts = []
    try:
        for nom, fn in CANDIDATS:
            c = tmp / src.name
            shutil.copy2(src, c)
            print(nom)
            ok, dit = fn(exe, c)
            print('   execution : %s  %s' % ('OK' if ok else 'ECHEC', asc(dit)))
            t1, ok1, seft1, ftyp1 = signatures(c)
            px1 = pixels_hash(c)
            image_intacte = (ref_px is not None and px1 == ref_px)
            trailer_parti = (not seft1) and ftyp1 == 0
            verdict = ('PARFAIT : image intacte, video partie' if ok and image_intacte and trailer_parti and ok1
                       else 'trailer parti mais image DECODE differente' if trailer_parti and not image_intacte
                       else 'trailer PAS parti' if not trailer_parti
                       else 'JPEG invalide' if not ok1
                       else 'a examiner')
            eco = t0 - t1
            print('   apres : %d o (%+d, -%.0f%%)  finitFFD9=%s SEFT=%s ftyp=%s  pixels=%s'
                  % (t1, -eco, 100.0 * eco / t0 if t0 else 0, ok1, seft1, ftyp1, (px1 or 'n/a')[:12]))
            print('   image intacte : %s' % ('OUI' if image_intacte else ('? (pas de PIL)' if ref_px is None else 'NON')))
            print('   => %s' % verdict)
            print('-' * 74)
            verdicts.append((nom[:2], verdict))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('VERDICTS')
    for k, v in verdicts:
        print('  %s %s' % (k, v))
    return 0


if __name__ == '__main__':
    sys.exit(main())
