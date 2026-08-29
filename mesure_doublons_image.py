#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — les DOUBLONS que le hachage de FICHIER ne voit pas (ROADMAP 1 decies)
─────────────────────────────────────────────────────────────────────────────

Le dedoublonnage du 23/08 comparait des sha256 de FICHIERS : 0 groupe restant.
Or deux copies d'une meme photo, taguees SEPAREMENT, ont un XMP qui a diverge
de quelques centaines d'octets — memes pixels, autre fichier. Mesure sur une
copie de l'index (29/08) : 2 921 groupes « meme seconde de prise + meme nom »,
27 seulement au meme octet. Ce banc compare l'IMAGE (ExifTool `ImageDataHash`,
les pixels seuls), comme `verifier_doublons_atrier`.

LECTURE SEULE : n'ecrit que `docs/doublons_image.json` (rapport + cache des
hachages, ce qui le rend REPRENABLE : le canal du banc plafonne a 600 s, le
fonds demande plusieurs passes — relancer jusqu'a « termine »).

CANDIDATS (depuis la COPIE de la base, jamais photos.db) : les cles absolues
(NAS) qui partagent la meme seconde de prise (`taken`) ET le meme nom de
fichier. Les groupes « meme seconde, autre nom » sont COMPTES, pas haches.

VERDICT par groupe : IDENTIQUE (memes pixels partout), DIFFERENTE (au moins
une image differe), INCONNU (un hachage manque : fichier absent, illisible).
Pour un groupe IDENTIQUE, la CANONIQUE suit la regle tranchee par Mike
(29/08) : la copie de `Photos Mike` par defaut ; chez un meme proprietaire, la
copie rangee par ANNEE (`Photos X\\AAAA\\…`) avant un dossier thematique. Et
pour chaque copie a retirer, ce qu'elle porte que la canonique n'a PAS —
noms (`personne:`/`animal:`), GPS — pour que l'applicateur le recopie (regle
2 : rien ne se perd). Ce banc ne deplace RIEN.

    mesure_doublons_image.py --base copie.db [--budget-s 540] [--limite N]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'doublons_image.json'
ADMIN = 'Mike'


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def exiftool():
    """Comme `verifier_doublons_atrier` : `exiftool*/exiftool.exe` dans le
    projet, sinon le PATH."""
    for c in sorted(RACINE.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return str(p)
    import shutil
    return shutil.which('exiftool')


def nk(p):
    return os.path.normcase(os.path.normpath(str(p)))


def proprietaire(cle):
    for seg in str(cle).replace('\\', '/').split('/'):
        m = re.match(r'^photos\s+(\S.*)$', seg.strip(), re.I)
        if m:
            return m.group(1).strip()
    return None


def par_annee(cle):
    """`Photos X\\AAAA\\…` : le segment qui suit le dossier proprietaire est une annee."""
    segs = [s for s in str(cle).replace('\\', '/').split('/') if s]
    for i, seg in enumerate(segs):
        if re.match(r'^photos\s+\S', seg, re.I):
            return i + 1 < len(segs) and bool(re.match(r'^(19|20)\d\d$', segs[i + 1]))
    return False


def est_cache(cle):
    return any(part.startswith(('.', '@', '#')) for part in str(cle).replace('\\', '/').split('/'))


def rang_canonique(cle):
    """Plus petit = plus canonique. Mike d'abord, puis le rangement par annee,
    puis PRIVE apres le partage (une copie privee ne remplace pas une publique),
    puis le chemin le plus court (le moins de sous-dossiers)."""
    p = proprietaire(cle)
    return (0 if p == ADMIN else (1 if p else 2),
            0 if par_annee(cle) else 1,
            1 if 'PRIVE' in str(cle).upper().split('\\') else 0,
            str(cle).count('\\'), str(cle).lower())


def noms_de(e):
    return sorted(t for fld in ('kw_fr', 'kw_en') for t in (e.get(fld) or [])
                  if isinstance(t, str) and (t.startswith('personne:') or t.startswith('animal:')))


def charger_index(base):
    import sqlite3
    if Path(base).name == 'photos.db':
        print('REFUS : ce banc lit une COPIE (mesure_copie_base.py), jamais photos.db')
        sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    out = {}
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(e, dict) or e.get('failed'):
            continue
        out[k] = e
    cx.close()
    return out


def candidats(index):
    par = defaultdict(list)
    autres = defaultdict(list)
    for k, e in index.items():
        t = e.get('taken')
        if not t or not Path(k).is_absolute() or est_cache(k):
            continue
        par[(round(float(t)), os.path.basename(k).lower())].append(k)
        autres[round(float(t))].append(k)
    groupes = [sorted(v) for v in par.values() if len(v) > 1]
    groupes.sort(key=lambda g: g[0].lower())
    # meme seconde, autre nom : comptes seulement
    noms_diff = sum(1 for v in autres.values()
                    if len(v) > 1 and len({os.path.basename(k).lower() for k in v}) > 1)
    return groupes, noms_diff


def hacher(exe, chemins, cache, budget_fin, log):
    CH = 60
    a_faire = [c for c in chemins if nk(c) not in cache]
    for i in range(0, len(a_faire), CH):
        if time.time() > budget_fin:
            log('  budget atteint : %d/%d haches cette passe' % (i, len(a_faire)))
            return False
        lot = a_faire[i:i + CH]
        # Argfile UTF-8 avec BOM, comme `server._run_exiftool` : sous Windows
        # un chemin accentue passe en ligne de commande arrive faux a ExifTool
        # (36 « INCONNU » sur 80 au premier essai, tous avec un accent).
        args = ['-api', 'RequestAll=3', '-ImageDataHash', '-FileSize#', '-s3', '-q', '-q', '-j',
                '-charset', 'filename=UTF8'] + lot
        import tempfile
        argfile = None
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                             encoding='utf-8-sig') as tf:
                tf.write('\n'.join(args))
                argfile = tf.name
            r = subprocess.run([exe, '-@', argfile], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=300)
            vus = set()
            for item in json.loads(r.stdout or '[]'):
                sf = item.get('SourceFile', '')
                if sf:
                    vus.add(nk(sf))
                    cache[nk(sf)] = {'h': item.get('ImageDataHash') or None,
                                     'octets': item.get('FileSize')}
            for c in lot:
                if nk(c) not in vus:
                    cache[nk(c)] = {'h': None, 'octets': None, 'absent': not os.path.exists(c)}
        except Exception as e:  # noqa: BLE001
            log('  lot en erreur (%d..) : %s' % (i, asc(str(e))[:80]))
            for c in lot:
                cache.setdefault(nk(c), {'h': None, 'octets': None, 'erreur': True})
        finally:
            if argfile:
                try:
                    os.unlink(argfile)
                except OSError:
                    pass
        log('  hash %d/%d' % (min(i + CH, len(a_faire)), len(a_faire)))
    return True


def juger(groupes, index, cache):
    verdicts = []
    for g in groupes:
        hs = [(cache.get(nk(k)) or {}).get('h') for k in g]
        if any(h is None for h in hs):
            verdict = 'INCONNU'
        elif len(set(hs)) == 1:
            verdict = 'IDENTIQUE'
        else:
            verdict = 'DIFFERENTE'
        rec = {'verdict': verdict, 'cles': g, 'hachages': hs,
               'octets': [(cache.get(nk(k)) or {}).get('octets') for k in g]}
        if verdict == 'IDENTIQUE':
            ordre = sorted(g, key=rang_canonique)
            canon, retraits = ordre[0], ordre[1:]
            ec = index.get(canon) or {}
            noms_c, gps_c = set(noms_de(ec)), bool(ec.get('gps'))
            rec['canonique'] = canon
            rec['retraits'] = []
            for r in retraits:
                er = index.get(r) or {}
                rec['retraits'].append({
                    'cle': r,
                    'noms_a_recopier': sorted(set(noms_de(er)) - noms_c),
                    'gps_a_recopier': bool(er.get('gps')) and not gps_c,
                    'proprietaire': proprietaire(r)})
            rec['entre_proprietaires'] = len({proprietaire(k) for k in g}) > 1
        verdicts.append(rec)
    return verdicts


def resume(verdicts, noms_diff, groupes, termine):
    n = defaultdict(int)
    octets = 0
    entre, noms, gps, chez = 0, 0, 0, defaultdict(int)
    for v in verdicts:
        n[v['verdict']] += 1
        if v['verdict'] == 'IDENTIQUE':
            for r in v['retraits']:
                oc = (v['octets'][v['cles'].index(r['cle'])] or 0)
                octets += oc if isinstance(oc, (int, float)) else 0
                noms += bool(r['noms_a_recopier'])
                gps += bool(r['gps_a_recopier'])
            entre += v['entre_proprietaires']
            chez[tuple(sorted({proprietaire(k) or '(racine)' for k in v['cles']}))] += 1
    lignes = [
        'DOUBLONS PAR L IMAGE : %d groupe(s) candidats (meme seconde + meme nom), %s' % (
            len(groupes), 'TERMINE' if termine else 'PASSE PARTIELLE - relancer'),
        '  IDENTIQUE : %d   DIFFERENTE : %d   INCONNU : %d   (non haches : %d)' % (
            n['IDENTIQUE'], n['DIFFERENTE'], n['INCONNU'], len(groupes) - len(verdicts)),
        '  retraits proposes : %d fichier(s), %.2f Go ; entre proprietaires : %d groupe(s)' % (
            sum(len(v['retraits']) for v in verdicts if v['verdict'] == 'IDENTIQUE'), octets / 1e9, entre),
        '  a recopier avant retrait : noms sur %d copie(s), GPS sur %d' % (noms, gps),
        '  meme seconde mais AUTRE nom (non haches, a regarder ensuite) : %d groupe(s)' % noms_diff,
    ]
    for cle, nb in sorted(chez.items(), key=lambda kv: -kv[1])[:8]:
        lignes.append('    %5d  %s' % (nb, ' + '.join(cle)))
    return lignes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True, help='COPIE de photos.db')
    ap.add_argument('--budget-s', type=int, default=540)
    ap.add_argument('--limite', type=int, default=0, help='ne juger que les N premiers groupes')
    a = ap.parse_args(argv)
    log = lambda m: print(asc(m), flush=True)  # noqa: E731
    t0 = time.time()
    exe = exiftool()
    if not exe:
        log('exiftool ABSENT'); return 2
    index = charger_index(a.base)
    groupes, noms_diff = candidats(index)
    if a.limite:
        groupes = groupes[:a.limite]
    log('index : %d entrees ; candidats : %d groupe(s), %d cle(s) ; autre nom : %d' % (
        len(index), len(groupes), sum(len(g) for g in groupes), noms_diff))
    cache = {}
    if RAPPORT.exists():
        try:
            cache = json.loads(RAPPORT.read_text(encoding='utf-8')).get('cache') or {}
        except Exception:  # noqa: BLE001
            cache = {}
    log('cache : %d hachage(s) deja connus' % len(cache))
    chemins = [k for g in groupes for k in g]
    termine = hacher(exe, chemins, cache, t0 + a.budget_s, log)
    juges = [g for g in groupes if all(nk(k) in cache for k in g)]
    verdicts = juger(juges, index, cache)
    lignes = resume(verdicts, noms_diff, groupes, termine)
    RAPPORT.parent.mkdir(exist_ok=True)
    tmp = RAPPORT.with_suffix('.tmp')
    tmp.write_text(json.dumps({
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'), 'base': str(a.base), 'termine': termine,
        'regle_canonique': 'Photos Mike par defaut ; puis rangement par annee ; PRIVE apres partage',
        'candidats': len(groupes), 'autre_nom_meme_seconde': noms_diff,
        'resume': lignes, 'groupes': verdicts, 'cache': cache},
        ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(RAPPORT)
    for l in lignes:
        log(l)
    log('rapport : %s (%.0f s)' % (RAPPORT.relative_to(RACINE), time.time() - t0))
    return 0 if termine else 3


if __name__ == '__main__':
    sys.exit(main())
