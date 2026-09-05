#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mesure la duree REELLE de detect_faces()/detect_animals() en CPU et en GPU,
sur un petit lot de photos deja utilisees pour la comparaison de modeles de
vision (mesure_modele_vision.py) -- pour chiffrer le cout d'un enchainement
"visages+animaux PUIS tagage" par photo, plutot que de le supposer.

Reimplementation AUTONOME (memes constantes que server.py : FACE_MODEL,
FACE_DET_THRESHOLD, FACE_MAX_SIDE, ANIMAL_YOLO_WEIGHTS, ANIMAL_DET_THRESHOLD,
ANIMAL_MAX_SIDE, ANIMAL_CLASSES) -- n'importe PAS server.py (qui demarrerait
des threads de fond, ouvrirait l'index en ecriture, etc.). Lecture seule sur
COPIE, jamais sur photos.db.

Usage (agent banc) :
    mesure_detection_cpu.py --base copie.db --cle b64:<...> [--cle ...]
"""
import argparse
import base64
import io
import json
import sqlite3
import time
from pathlib import Path

FACE_MODEL = "buffalo_l"
FACE_DET_THRESHOLD = 0.50
FACE_MAX_SIDE = 1600
ANIMAL_YOLO_WEIGHTS = "yolo11s.pt"
ANIMAL_DET_THRESHOLD = 0.30
ANIMAL_MAX_SIDE = 1600
ANIMAL_CLASSES = {14: 'bird', 15: 'cat', 16: 'dog', 17: 'horse'}


def dejeton(arg):
    if isinstance(arg, str) and arg.startswith('b64:'):
        corps = arg[4:]
        pad = '=' * (-len(corps) % 4)
        return base64.urlsafe_b64decode(corps + pad).decode('utf-8')
    return arg


def charger_chemins(base, cles):
    if Path(base).name == 'photos.db':
        raise SystemExit('REFUS : ce banc lit une COPIE (--base copie.db), '
                         'jamais photos.db.')
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).as_posix(), uri=True)
    out = []
    for k in cles:
        row = cx.execute('SELECT 1 FROM tags WHERE k = ?', (k,)).fetchone()
        if row is None:
            print('  ! cle absente de la base :', k)
            continue
        out.append(k)
    cx.close()
    return out


def load_bgr(path, max_side):
    from PIL import Image, ImageOps
    import numpy as np
    with open(path, 'rb') as f:
        data = f.read()
    with Image.open(io.BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        if max_side and max_side > 0:
            im.thumbnail((max_side, max_side))
        arr = np.asarray(im)[:, :, ::-1].copy()
    return arr


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--cle', action='append', required=True, dest='cles')
    a = ap.parse_args(argv)

    cles = [dejeton(c) for c in a.cles]
    chemins = charger_chemins(a.base, cles)
    print('photos retenues :', len(chemins))

    # ---- visages (InsightFace) : CPU d'abord (toujours possible) ----
    from insightface.app import FaceAnalysis
    print('=== chargement InsightFace (CPU) ===')
    t0 = time.time()
    app_cpu = FaceAnalysis(name=FACE_MODEL, providers=['CPUExecutionProvider'],
                           allowed_modules=['detection', 'recognition'])
    app_cpu.prepare(ctx_id=0, det_size=(640, 640))
    print('  charge en %.1fs (une seule fois, hors mesure par photo)' %
          (time.time() - t0))

    app_gpu = None
    try:
        print('=== tentative InsightFace (GPU/CUDA) ===')
        t0 = time.time()
        app_gpu = FaceAnalysis(name=FACE_MODEL,
                               providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
                               allowed_modules=['detection', 'recognition'])
        app_gpu.prepare(ctx_id=0, det_size=(640, 640))
        used = app_gpu.models['detection'].session.get_providers()
        if not any('CUDA' in p for p in used):
            print('  CUDA non actif sur cette session -- ignore le comparatif GPU')
            app_gpu = None
        else:
            print('  charge en %.1fs' % (time.time() - t0))
    except Exception as e:                                    # noqa: BLE001
        print('  GPU indisponible :', e)
        app_gpu = None

    resultats_visages = {}
    for k in chemins:
        arr = load_bgr(k, FACE_MAX_SIDE)
        t0 = time.time()
        faces_cpu = app_cpu.get(arr)
        d_cpu = time.time() - t0
        n_cpu = sum(1 for f in faces_cpu
                   if float(getattr(f, 'det_score', 0.0)) >= FACE_DET_THRESHOLD)
        ligne = {'cpu_s': round(d_cpu, 2), 'n_visages_cpu': n_cpu}
        if app_gpu is not None:
            t0 = time.time()
            faces_gpu = app_gpu.get(arr)
            d_gpu = time.time() - t0
            n_gpu = sum(1 for f in faces_gpu
                       if float(getattr(f, 'det_score', 0.0)) >= FACE_DET_THRESHOLD)
            ligne['gpu_s'] = round(d_gpu, 2)
            ligne['n_visages_gpu'] = n_gpu
        resultats_visages[Path(k).name] = ligne
        print('  visages %-40s cpu=%5.2fs (%d)%s' % (
            Path(k).name[:40], d_cpu, n_cpu,
            '  gpu=%.2fs (%d)' % (ligne['gpu_s'], ligne['n_visages_gpu'])
            if 'gpu_s' in ligne else ''))

    # ---- animaux (YOLO) : CPU puis GPU si possible ----
    print('=== chargement YOLO ===')
    from ultralytics import YOLO
    t0 = time.time()
    model = YOLO(ANIMAL_YOLO_WEIGHTS)
    print('  charge en %.1fs' % (time.time() - t0))

    resultats_animaux = {}
    for k in chemins:
        arr = load_bgr(k, ANIMAL_MAX_SIDE)
        t0 = time.time()
        r_cpu = model.predict(arr, conf=ANIMAL_DET_THRESHOLD,
                              classes=list(ANIMAL_CLASSES.keys()),
                              device='cpu', verbose=False)
        d_cpu = time.time() - t0
        n_cpu = sum(len(r.boxes) if r.boxes is not None else 0 for r in r_cpu)
        ligne = {'cpu_s': round(d_cpu, 2), 'n_animaux_cpu': n_cpu}
        try:
            t0 = time.time()
            r_gpu = model.predict(arr, conf=ANIMAL_DET_THRESHOLD,
                                  classes=list(ANIMAL_CLASSES.keys()),
                                  device=0, verbose=False)
            d_gpu = time.time() - t0
            n_gpu = sum(len(r.boxes) if r.boxes is not None else 0 for r in r_gpu)
            ligne['gpu_s'] = round(d_gpu, 2)
            ligne['n_animaux_gpu'] = n_gpu
        except Exception as e:                                # noqa: BLE001
            ligne['gpu_erreur'] = str(e)[:150]
        resultats_animaux[Path(k).name] = ligne
        print('  animaux %-40s cpu=%5.2fs (%d)%s' % (
            Path(k).name[:40], d_cpu, n_cpu,
            '  gpu=%.2fs (%d)' % (ligne['gpu_s'], ligne['n_animaux_gpu'])
            if 'gpu_s' in ligne else ''))

    out = Path('docs/mesure_detection_cpu.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
        'visages': resultats_visages, 'animaux': resultats_animaux},
        ensure_ascii=False, indent=1), encoding='utf-8')
    print('rapport ecrit :', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
