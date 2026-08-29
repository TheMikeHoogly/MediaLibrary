#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Doublons de `_A TRIER` DEJA RANGES dans le fonds — par IMAGE, pas par octet.

Un fichier de `_A TRIER` dont l'image (pixels) existe deja dans le fonds
(`Photos <Nom>\\<annee>`) est un doublon a retirer : la copie du fonds est la
canonique. On matche par `exiftool -ImageDataHash` (les pixels seuls), pas par
sha256 : deux copies de la meme photo different de quelques centaines d'octets
de tags, donc un sha256 dirait « pas doublon » a tort.

LECTURE SEULE. N'ecrit que ses rapports (`docs/doublons_atrier.{json,md}`), ne
touche ni un fichier photo, ni `photos.db`, ni le NAS. Sortie ASCII.

Preserve la regle « aucun nom perdu » : si `--db` est donne, une copie a
retirer qui porte un `personne:`/`animal:` ABSENT de la canonique est marquee
REVUE et EXCLUE du retrait automatique (a fusionner d'abord, cf. appliquer_plan).

    # cible (rapide, pour un premier chiffre) :
    verifier_doublons_atrier.py --atrier b64:<dossier _A TRIER> --fonds b64:<dossier fonds>
    # complet (lit la config, tout le fonds vs tout _A TRIER) :
    verifier_doublons_atrier.py [--db b64:<copie de photos.db>]
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif',
             '.bmp', '.tiff', '.tif'}
ATRI_RE = re.compile(r'^_?a[ _]tri', re.I)


def deb64(v):
    return base64.urlsafe_b64decode(v[4:] + '=' * (-len(v[4:]) % 4)).decode('utf-8') if str(v).startswith('b64:') else v


def exiftool():
    for c in sorted(ICI.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return p
    return None


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def _read_config_lines(name):
    out = []
    try:
        for line in (ICI / name).read_text(encoding='utf-8').splitlines():
            line = line.strip().strip('"')
            if line and not line.startswith('#'):
                out.append(line)
    except OSError:
        pass
    return out


def racines_config():
    """Racines du fonds, depuis la meme config que le serveur."""
    out = []
    for name in ('dossiers_a_taguer.txt', 'dossier_uploads.txt'):
        for l in _read_config_lines(name):
            if l not in out:
                out.append(l)
    return out


def est_atri(chemin):
    return any(ATRI_RE.match(str(p).strip()) for p in Path(chemin).parts)


def enum_media(dossier):
    """(chemins media sous `dossier`, recursif, hors caches)."""
    out = []
    for r, dirs, files in os.walk(dossier):
        dirs[:] = [d for d in dirs if not d[:1] in ('.', '@', '#')]
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXT:
                out.append(os.path.join(r, f))
    return out


def image_hashes(exe, chemins, log=lambda *_: None):
    """{chemin -> ImageDataHash} par lots exiftool (les pixels seuls)."""
    res = {}
    CH = 80
    for i in range(0, len(chemins), CH):
        lot = chemins[i:i + CH]
        args = [str(exe), '-api', 'RequestAll=3', '-ImageDataHash', '-s3',
                '-q', '-q', '-j', '-charset', 'filename=UTF8'] + [str(p) for p in lot]
        try:
            r = subprocess.run(args, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=600)
            for item in json.loads(r.stdout or '[]'):
                sf = item.get('SourceFile', '')
                h = item.get('ImageDataHash')
                if sf and h:
                    res[os.path.normcase(os.path.normpath(sf))] = h
        except Exception as e:  # noqa: BLE001
            log('  lot hash en erreur (%d..): %s' % (i, str(e)[:80]))
        log('  hash %d/%d' % (min(i + CH, len(chemins)), len(chemins)))
    return res


def load_names(db_copy):
    import sqlite3
    out = {}
    try:
        cx = sqlite3.connect(str(db_copy))
        for k, v in cx.execute("SELECT k, v FROM tags"):
            try:
                e = json.loads(v)
            except Exception:
                continue
            noms = [t for fld in ('kw_fr', 'kw_en') for t in (e.get(fld) or [])
                    if isinstance(t, str) and (t.startswith('personne:') or t.startswith('animal:'))]
            if noms:
                out[os.path.normcase(os.path.normpath(k))] = set(noms)
        cx.close()
    except Exception as e:  # noqa: BLE001
        print('  (index illisible, controle des noms desactive : %s)' % str(e)[:80])
    return out


def hkey(p):
    return os.path.normcase(os.path.normpath(str(p)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--atrier', default='')
    ap.add_argument('--fonds', action='append', default=[])
    ap.add_argument('--db', default='')
    ap.add_argument('--limite', type=int, default=0, help='ne tester que les N premiers _A TRIER (validation rapide)')
    a = ap.parse_args(argv)
    exe = exiftool()
    if not exe:
        print('exiftool ABSENT'); return 2
    log = lambda m: print(m, flush=True)

    if a.atrier:
        atrier_files = enum_media(deb64(a.atrier))
        fonds_files = []
        for f in a.fonds:
            fonds_files += enum_media(deb64(f))
    else:
        atrier_files, fonds_files = [], []
        for rac in racines_config():
            for p in enum_media(rac):
                (atrier_files if est_atri(p) else fonds_files).append(p)
    log('_A TRIER : %d media | fonds : %d media' % (len(atrier_files), len(fonds_files)))

    # index du fonds par basename minuscule
    fonds_par_nom = defaultdict(list)
    for p in fonds_files:
        fonds_par_nom[os.path.basename(p).lower()].append(p)

    if a.limite:
        atrier_files = atrier_files[:a.limite]
    # ne garder que les _A TRIER qui ont un HOMONYME dans le fonds
    a_tester, sans_homonyme = [], []
    for p in atrier_files:
        if fonds_par_nom.get(os.path.basename(p).lower()):
            a_tester.append(p)
        else:
            sans_homonyme.append(p)
    # jumeaux du fonds a hasher (uniquement ceux qui servent)
    jumeaux = []
    for p in a_tester:
        jumeaux += fonds_par_nom[os.path.basename(p).lower()]
    log('homonymes a comparer : %d (+ %d jumeaux fonds a hasher)' % (len(a_tester), len(set(jumeaux))))

    H = image_hashes(exe, a_tester + list(set(jumeaux)), log)
    noms = load_names(Path(deb64(a.db))) if a.db else {}

    confirmes, revue, image_differente = [], [], []
    for p in a_tester:
        ph = H.get(hkey(p))
        cand = fonds_par_nom[os.path.basename(p).lower()]
        canon = next((c for c in cand if ph and H.get(hkey(c)) == ph), None)
        if not canon:
            image_differente.append(p)
            continue
        # regle des noms : le doublon ne doit pas porter un nom absent de la canonique
        if noms:
            manque = noms.get(hkey(p), set()) - noms.get(hkey(canon), set())
            if manque:
                revue.append((p, canon, sorted(manque)))
                continue
        confirmes.append((p, canon))

    octets = 0
    for p, _ in confirmes:
        try:
            octets += os.path.getsize(p)
        except OSError:
            pass

    print('=' * 74)
    print('DOUBLONS _A TRIER deja ranges (meme IMAGE) :')
    print('  confirmes (retirables)         : %d  (%.2f Go liberables)' % (len(confirmes), octets / 1e9))
    print('  a REVUE (nom absent canonique) : %d  (a fusionner d abord)' % len(revue))
    print('  homonyme mais IMAGE differente : %d  (a garder, ce n est pas un doublon)' % len(image_differente))
    print('  sans homonyme dans le fonds    : %d  (a ranger normalement)' % len(sans_homonyme))
    for p, c in confirmes[:8]:
        print('   dup : %s' % asc(p))
        print('     -> canonique : %s' % asc(c))
    for p, c, m in revue[:6]:
        print('   REVUE : %s  (noms manquants: %s)' % (asc(os.path.basename(p)), asc(', '.join(m))))

    rapport = {
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
        'confirmes': [{'dup': p, 'canonique': c} for p, c in confirmes],
        'revue': [{'dup': p, 'canonique': c, 'noms_manquants': m} for p, c, m in revue],
        'image_differente': image_differente,
        'sans_homonyme': sans_homonyme,
        'octets_liberables': octets,
    }
    docs = ICI / 'docs'
    try:
        docs.mkdir(exist_ok=True)
    except OSError:
        pass
    (docs / 'doublons_atrier.json').write_text(
        json.dumps(rapport, ensure_ascii=False, indent=1), encoding='utf-8')
    print('liste ecrite : docs/doublons_atrier.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
