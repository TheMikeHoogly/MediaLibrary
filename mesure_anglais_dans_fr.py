#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — les mots ANGLAIS qui fuient dans le texte FRANCAIS du tagueur
──────────────────────────────────────────────────────────────────────────────

Mike, 30/08, sur cinq copies d'une photo de Caline : « chat calico assis sur
un canape » — « calico » ne veut rien dire en francais (c'est « tricolore »,
« ecaille de tortue »). Le tagueur ecrit `keywords_fr` et `description_fr` en
francais directement (`tagging_meta.REGLES_JSON`), et un mot anglais passe
parfois tel quel. AVANT de corriger (glossaire de post-traitement, re-tagging),
compter : combien de textes FR en portent, et LESQUELS.

METHODE (lecture seule, COPIE de la base, jamais photos.db) : pour chaque mot
(minuscule, sans ponctuation, 3 lettres et plus), sa frequence dans les textes
ANGLAIS du fonds (`kw_en`, en nombre de photos) et dans les textes FRANCAIS
(`kw_fr` + `desc`). Un mot legitime dans les deux langues (« table »,
« portrait », « orange ») est frequent des deux cotes ; un mot anglais qui
FUIT est frequent en anglais et RARE en francais. On classe donc par
f_en / f_fr, et on imprime les candidats pour un OEIL : ce banc ne decide
pas qu'un mot est anglais, il montre ou regarder. `--mot calico` donne le
detail d'un mot (photos touchees, exemples).

    mesure_anglais_dans_fr.py --base copie.db [--min-fr 3] [--ratio 2.0]
                              [--top 60] [--mot calico]
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

MOT_RE = re.compile(r"[a-zà-ÿ]{3,}", re.I)
# Mots-outils francais et anglais, jamais candidats.
OUTILS = set('''une des les sur dans avec pour par est sont sous entre chez qui que
the and with for from over under this that are was near beside next into onto
son ses leur leurs cette ces aux mais pas plus tres deux trois'''.split())


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def mots(texte):
    return {m.lower() for m in MOT_RE.findall(texte or '') if m.lower() not in OUTILS}


def charger(base):
    if Path(base).name == 'photos.db':
        print('REFUS : ce banc lit une COPIE (mesure_copie_base.py), jamais photos.db')
        sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if isinstance(e, dict) and not e.get('failed') and not e.get('video'):
            yield k, e
    cx.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--min-fr', type=int, default=3, help='present dans au moins N textes FR')
    ap.add_argument('--ratio', type=float, default=2.0, help='f_en / f_fr minimal')
    ap.add_argument('--top', type=int, default=60)
    ap.add_argument('--mot', help='detail d un mot')
    a = ap.parse_args(argv)
    f_en, f_fr = defaultdict(int), defaultdict(int)
    exemples = defaultdict(list)
    n = 0
    for k, e in charger(a.base):
        n += 1
        en = set()
        for t in e.get('kw_en') or []:
            if isinstance(t, str) and ':' not in t:
                en |= mots(t)
        fr = set()
        for t in e.get('kw_fr') or []:
            if isinstance(t, str) and ':' not in t:
                fr |= mots(t)
        fr |= mots(e.get('desc') or '')
        for m in en:
            f_en[m] += 1
        for m in fr:
            f_fr[m] += 1
            if a.mot and m == a.mot.lower() and len(exemples[m]) < 12:
                exemples[m].append((k, e.get('desc') or '', [t for t in (e.get('kw_fr') or []) if a.mot.lower() in str(t).lower()]))
    print('photos taguees (copie) : %d ; mots EN distincts : %d ; mots FR distincts : %d' % (n, len(f_en), len(f_fr)))
    if a.mot:
        m = a.mot.lower()
        print('\n"%s" : dans %d texte(s) FR, %d texte(s) EN' % (m, f_fr.get(m, 0), f_en.get(m, 0)))
        for k, d, kws in exemples[m]:
            print('  %s\n     desc: %s\n     kw_fr: %s' % (asc(k), asc(d[:110]), asc(', '.join(kws))))
        return 0
    cands = []
    for m, ffr in f_fr.items():
        fen = f_en.get(m, 0)
        if ffr >= a.min_fr and fen >= a.ratio * ffr:
            cands.append((fen / ffr, m, ffr, fen))
    cands.sort(key=lambda x: (-x[2], -x[0]))
    print('\nCANDIDATS (mot present dans >= %d textes FR et >= %.1f x plus souvent en anglais) : %d' % (a.min_fr, a.ratio, len(cands)))
    print('  %-22s %8s %8s %7s' % ('mot', 'FR', 'EN', 'EN/FR'))
    for r, m, ffr, fen in cands[:a.top]:
        print('  %-22s %8d %8d %7.1f' % (asc(m), ffr, fen, r))
    total_fr = sum(ffr for _, _, ffr, _ in cands)
    print('\n  somme des occurrences FR des candidats : %d (une photo peut en porter plusieurs)' % total_fr)
    # Second regard, au niveau du TAG entier : un `kw_fr` qui est, mot pour mot,
    # l'un des `kw_en` de la MEME photo et dont tous les mots sont candidats.
    # C'est la fuite la plus sure a nommer (« living room » recopie tel quel),
    # et c'est elle qu'un glossaire EN->FR corrigerait en post-traitement.
    cand = {m for _, m, _, _ in cands}
    photos, tags, stricts = 0, defaultdict(int), defaultdict(int)
    for k, e in charger(a.base):
        en = {t.strip().lower() for t in (e.get('kw_en') or []) if isinstance(t, str)}
        touche = False
        for t in e.get('kw_fr') or []:
            if not isinstance(t, str) or ':' in t:
                continue
            tl = t.strip().lower()
            ms = mots(tl)
            if ms and ms <= cand:
                tags[tl] += 1
                touche = True
                stricts[tl] += (tl in en)
        photos += touche
    print('\nTAGS FR dont TOUS les mots sont candidats (un tag entier, ex. "living room") :')
    print('  photos touchees : %d sur %d (%.1f %%) ; tags distincts : %d ; occurrences : %d ; dont recopies mot pour mot d un kw_en de la meme photo : %d' % (
        photos, n, 100.0 * photos / max(n, 1), len(tags), sum(tags.values()), sum(stricts.values())))
    for t, c in sorted(tags.items(), key=lambda kv: -kv[1])[:a.top]:
        print('  %6d  %s' % (c, asc(t)))
    print('  (lecture seule : rien ecrit ; un candidat n est pas une faute, c est un endroit ou regarder)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
