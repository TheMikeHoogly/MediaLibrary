#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare DEUX modeles Ollama (vision) sur le MEME petit lot de photos, avec
le MEME prompt de prod (tagging_meta.prompt_tagging) et les MEMES assertions
(reconstruites depuis copie.db, comme mesure_retag_gain.py).

Sert a decider si un modele plus gros que qwen3-vl:2b (ex. qwen3-vl:4b, deja
tire en local -- voir diagnostic_ollama_modeles.py) ameliore reellement la
justesse du tagage, AVANT de rebrancher le pipeline de prod dessus. Conçu
pour un tres petit lot cible (quelques cles precises, pas un tirage aleatoire)
-- typiquement des photos deja identifiees comme mal taguees par une
verification visuelle humaine.

LECTURE SEULE. Aucune ecriture dans l'index ni dans un fichier.

Usage (par l'agent banc) :
    mesure_modele_vision.py --base copie.db
        --modele qwen3-vl:2b --modele qwen3-vl:4b
        --cle b64:<cle en base64url> [--cle b64:<...> ...]
"""
import argparse
import base64
import io
import json
import re
import sqlite3
import time
import urllib.request
from pathlib import Path

import tagging_meta

OLLAMA = 'http://127.0.0.1:11434/api/generate'


def dejeton(arg):
    """`'b64:QsOpYQ'` -> chaine decodee ; sinon la valeur telle quelle
    (memes conventions que banc_agent.dejeton, pour les cles a espaces /
    antislashs qu'un shell n'accepte pas telles quelles)."""
    if isinstance(arg, str) and arg.startswith('b64:'):
        corps = arg[4:]
        pad = '=' * (-len(corps) % 4)
        return base64.urlsafe_b64decode(corps + pad).decode('utf-8')
    return arg


def charger_cles(base, cles):
    if Path(base).name == 'photos.db':
        raise SystemExit('REFUS : ce banc lit une COPIE (--base copie.db), '
                         'jamais photos.db -- le serveur est l ecrivain unique.')
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).as_posix(), uri=True)
    out = {}
    for k in cles:
        row = cx.execute('SELECT v FROM tags WHERE k = ?', (k,)).fetchone()
        if row is None:
            print('  ! cle absente de la base :', k)
            continue
        try:
            out[k] = json.loads(row[0])
        except ValueError:
            print('  ! entree illisible pour :', k)
    cx.close()
    return out


def plain_kw(kw):
    out = []
    for t in (kw or []):
        s = str(t)
        low = s.lower()
        if not (low.startswith('personne:') or low.startswith('animal:')):
            out.append(low)
    return out


def assertions_pour(e):
    """Copie de mesure_retag_gain.assertions_pour (meme simplification
    documentee : lieu/species omis, symetrique entre les modeles compares)."""
    existing = list(e.get('kw_fr') or []) + list(e.get('kw_en') or [])
    persons, animals = tagging_meta.noms_depuis_kw(existing)
    date_txt = date_src = None
    taken = e.get('taken')
    if taken:
        date_txt, date_src = tagging_meta.format_date_fr(taken), 'exif'
    return {'persons': persons, 'animals': animals, 'species': [],
            'lieu': None, 'lieu_src': None,
            'date': date_txt, 'date_src': date_src,
            'tags_fr': plain_kw(e.get('kw_fr'))[:12]}


def image_b64(chemin, cote=896):
    from PIL import Image, ImageOps
    with Image.open(chemin) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((cote, cote))
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def ollama_generate(modele, b64, prompt):
    corps = json.dumps({
        'model': modele, 'prompt': prompt, 'images': [b64], 'stream': False,
        'format': 'json', 'think': False, 'keep_alive': '30m',
        'options': {'temperature': 0.2, 'num_predict': 256, 'num_ctx': 4096,
                    'repeat_penalty': 1.05}}).encode()
    req = urllib.request.Request(OLLAMA, data=corps,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode())
    return data.get('response') or data.get('thinking') or ''


def parse_tags(raw):
    raw = (raw or '').strip()
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except ValueError:
            m = re.search(r'\{.*\}', raw, re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                except ValueError:
                    data = None
    if isinstance(data, dict):
        kw_en = data.get('keywords_en') or []
        kw_fr = data.get('keywords_fr') or []
        desc = str(data.get('description_fr') or '').strip()[:300]
        return kw_fr, kw_en, desc
    return [], [], ''


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--modele', action='append', required=True,
                    help='repetable : au moins deux modeles a comparer')
    ap.add_argument('--cle', action='append', required=True, dest='cles',
                    help='repetable : b64:<cle en base64url>, ou la cle telle quelle')
    a = ap.parse_args(argv)

    cles = [dejeton(c) for c in a.cles]
    entrees = charger_cles(a.base, cles)
    resultats = {}
    for k, e in entrees.items():
        prompt = tagging_meta.prompt_tagging(assertions_pour(e))
        b64 = image_b64(k)
        anciens = plain_kw(list(e.get('kw_fr') or []) + list(e.get('kw_en') or []))
        ligne = {'ancien_kw': anciens}
        for modele in a.modele:
            t0 = time.time()
            try:
                raw = ollama_generate(modele, b64, prompt)
                kw_fr, kw_en, desc = parse_tags(raw)
            except Exception as exc:                            # noqa: BLE001
                kw_fr, kw_en, desc = [], [], ''
                print('  ! echec', modele, 'sur', Path(k).name, ':', exc)
            ligne[modele] = {'kw_fr': kw_fr, 'kw_en': kw_en, 'desc': desc,
                             'duree_s': round(time.time() - t0, 1)}
            print('%-14s %5.1fs  %s' % (modele, ligne[modele]['duree_s'],
                                        Path(k).name[:40]))
        resultats[k] = ligne

    out = Path('docs/comparaison_modeles_vision.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
        'modeles': a.modele, 'resultats': resultats},
        ensure_ascii=False, indent=1), encoding='utf-8')
    print('rapport ecrit :', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
