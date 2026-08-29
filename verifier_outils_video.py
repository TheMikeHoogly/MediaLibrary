#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier videos, phases 1+ : les OUTILS sont-ils la ? (ffmpeg, ffprobe,
exiftool). LECTURE SEULE, sortie ASCII. Un plan de phase 1 (image-cle par
ffmpeg) qui ne sait pas si ffmpeg existe est un plan en l'air."""
import shutil
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent


def version(exe):
    try:
        r = subprocess.run([exe, '-version'], capture_output=True, timeout=20)
        return (r.stdout or r.stderr).decode('utf-8', 'replace').splitlines()[0][:100]
    except (OSError, subprocess.TimeoutExpired, IndexError) as e:
        return 'erreur : %s' % e


def main():
    for nom in ('ffmpeg', 'ffprobe'):
        p = shutil.which(nom)
        locaux = [str(x) for x in ICI.glob('ffmpeg*/**/%s.exe' % nom)]
        print('%-8s PATH : %s' % (nom, p or 'ABSENT'))
        if p:
            print('         %s' % version(p))
        for l in locaux:
            print('         local : %s' % l)
    ex = [str(x) for x in ICI.glob('exiftool*/exiftool.exe')] + [str(x) for x in ICI.glob('exiftool*.exe')]
    print('exiftool local : %s' % (ex[0] if ex else 'ABSENT'))
    if ex:
        print('         %s' % version(ex[0]).replace('\n', ' '))
    return 0


if __name__ == '__main__':
    sys.exit(main())
