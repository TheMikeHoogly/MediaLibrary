#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Retire les doublons `_A TRIER` confirmes vers `.corbeille-rangement/`.

Lit `docs/doublons_atrier.json` (produit par `verifier_doublons_atrier.py`) et,
pour chaque doublon CONFIRME (meme image qu'une copie du fonds), DEPLACE la
copie `_A TRIER` vers `.corbeille-rangement/<groupe>/`, avec un `manifeste.json`
au format que `purger_corbeille.py` (bat 24) sait purger apres 30 jours.

SERVEUR ALLUME. Cet outil ne touche JAMAIS `photos.db` : il ne fait que
deplacer des fichiers. Le scan du serveur voit la copie `_A TRIER` disparaitre
et purge son entree d'index tout seul (`forget_everywhere`) ; la corbeille est
cachee (prefixe `.`), donc jamais re-indexee. Les fiches de noms (par nom)
survivent. Reversible : journal `_corbeille_doublons_atrier.jsonl` (undo), et la
corbeille se vide toute seule au bat 24. Les entrees `revue` du rapport sont
IGNOREES ici (un nom absent de la canonique — a fusionner d'abord). Sortie ASCII.

    deplacer_doublons_atrier.py                 # DRY-RUN
    deplacer_doublons_atrier.py --appliquer
    deplacer_doublons_atrier.py --undo          # remet la derniere fournee
    deplacer_doublons_atrier.py --homonymes-differents [--appliquer]

`--homonymes-differents` retire AUSSI les copies `_A TRIER` dont l'homonyme du
fonds n'a PAS la meme image (re-encodage Google, `homonymes_differents` du
rapport). Ce n'est pas un doublon au sens du hachage : c'est une DECISION
HUMAINE (Mike, 29/08 : la version du NAS reste, ses XMP et son GPS avec), d'ou
l'option explicite, jamais par defaut. La regle des noms tient : une copie qui
porte un nom absent de l'homonyme est sautee (`noms_manquants`).
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RAPPORT = ICI / 'docs' / 'doublons_atrier.json'
JOURNAL = ICI / '_corbeille_doublons_atrier.jsonl'


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def sha256(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(buf), b''):
            h.update(chunk)
    return h.hexdigest()


def racine_photos(canon):
    """`.corbeille-rangement/` a la racine du fonds (le dossier qui contient
    « Photos <Nom> »), deduit d'un chemin canonique."""
    p = Path(canon)
    for i, part in enumerate(p.parts):
        if part.lower().startswith('photos ') or part == 'Photos':
            return Path(*p.parts[:i]) if part.lower().startswith('photos ') else Path(*p.parts[:i + 1])
    return p.parent.parent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true')
    ap.add_argument('--undo', action='store_true')
    ap.add_argument('--homonymes-differents', action='store_true',
                    help='retire aussi les homonymes a image differente (decision humaine)')
    a = ap.parse_args(argv)

    if a.undo:
        return undo()

    try:
        rap = json.loads(RAPPORT.read_text(encoding='utf-8'))
    except OSError:
        print('Rapport absent : lance d abord verifier_doublons_atrier.py'); return 1
    confirmes = list(rap.get('confirmes', []))
    print('%s : %d doublon(s) confirme(s) a retirer (%s revue ignoree(s))'
          % ('APPLICATION' if a.appliquer else 'DRY-RUN', len(confirmes), len(rap.get('revue', []))))
    if a.homonymes_differents:
        hd = rap.get('homonymes_differents')
        if hd is None:
            print('Le rapport ne connait pas les homonymes differents : relance verifier_doublons_atrier.py')
            return 1
        gardes = [e for e in hd if e.get('noms_manquants')]
        for e in gardes:
            print('  [skip] homonyme different GARDE, il porte un nom absent du fonds : %s (%s)'
                  % (asc(e['dup']), asc(', '.join(e['noms_manquants']))))
        pris = [{'dup': e['dup'], 'canonique': e['homonyme'], 'motif': 'homonyme a image differente'}
                for e in hd if not e.get('noms_manquants')]
        print('+ %d homonyme(s) a image differente (decision humaine, --homonymes-differents)' % len(pris))
        confirmes += pris
    if not confirmes:
        return 0

    # corbeille = a la racine du fonds, deduite de la 1re canonique
    trash = racine_photos(confirmes[0]['canonique']) / '.corbeille-rangement'
    stamp = time.strftime('%Y%m%d-%H%M%S')
    fournee = 'dedup_atrier_' + stamp
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    compte = {'ok': 0, 'skip': 0}
    sha_canon = {}  # cache: canonique -> sha256

    for e in confirmes:
        src, canon = e['dup'], e['canonique']
        p_src, p_canon = Path(src), Path(canon)
        if not p_src.exists():
            print('  [skip] source absente : %s' % asc(src)); compte['skip'] += 1; continue
        if not p_canon.exists():
            print('  [skip] canonique absente, on ne retire pas : %s' % asc(canon)); compte['skip'] += 1; continue
        groupe = hashlib.sha1(str(p_canon).encode('utf-8')).hexdigest()[:8]
        bucket = trash / fournee / groupe
        if a.appliquer:
            bucket.mkdir(parents=True, exist_ok=True)
            mani = bucket / 'manifeste.json'
            if not mani.exists():
                if canon not in sha_canon:
                    try:
                        sha_canon[canon] = sha256(p_canon)
                    except OSError:
                        sha_canon[canon] = ''
                mani.write_text(json.dumps({
                    'origine': src, 'canonique': canon, 'sha256': sha_canon[canon],
                    'groupe': groupe, 'date_application': now,
                    'motif': e.get('motif', 'meme image'),
                }, ensure_ascii=False, indent=1), encoding='utf-8')
            tag = hashlib.sha1(str(p_src).encode('utf-8')).hexdigest()[:4]
            dst = bucket / ('%s_%s' % (tag, p_src.name))
            try:
                shutil.move(str(p_src), str(dst))
            except OSError as ex:
                print('  [skip] deplacement impossible (verrou serveur ?) : %s (%s)' % (asc(src), ex))
                compte['skip'] += 1
                continue
            with open(JOURNAL, 'a', encoding='utf-8') as jf:
                jf.write(json.dumps({'src': src, 'dst': str(dst), 'canonique': canon,
                                     'fournee': fournee}, ensure_ascii=False) + '\n')
            print('  [ok]  %s\n        -> corbeille (%s)' % (asc(p_src.name), groupe))
        else:
            print('  [dry] %s  (canonique: %s)' % (asc(src), asc(canon)))
        compte['ok'] += 1

    print('\nBilan : %s' % compte)
    if a.appliquer:
        print('Corbeille : %s' % asc(trash / fournee))
        print('Reversible : deplacer_doublons_atrier.py --undo  (ou le bat 24 la videra apres 30 j).')
        print('Le serveur (allume) purge les entrees d index disparues au prochain scan.')
    else:
        print('(dry-run — rien deplace. Ajoute --appliquer, serveur ALLUME.)')
    return 0


def undo():
    if not JOURNAL.exists():
        print('Rien a annuler.'); return 0
    lignes = [json.loads(l) for l in JOURNAL.read_text(encoding='utf-8').splitlines() if l.strip()]
    if not lignes:
        print('Rien a annuler.'); return 0
    derniere = lignes[-1]['fournee']
    areverser = [l for l in lignes if l['fournee'] == derniere]
    print('Undo de la fournee %s : %d fichier(s)' % (derniere, len(areverser)))
    n = 0
    for l in reversed(areverser):
        src, dst = Path(l['src']), Path(l['dst'])
        if not dst.exists():
            print('  [skip] corbeille absente : %s' % asc(dst)); continue
        if src.exists():
            print('  [skip] origine deja la : %s' % asc(src)); continue
        try:
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))
            n += 1
        except OSError as ex:
            print('  [skip] restauration impossible : %s (%s)' % (asc(dst), ex))
    # retire les lignes annulees du journal
    reste = [l for l in lignes if l['fournee'] != derniere]
    JOURNAL.write_text(''.join(json.dumps(l, ensure_ascii=False) + '\n' for l in reste), encoding='utf-8')
    print('Restaure : %d. Le serveur re-indexera au prochain scan.' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
