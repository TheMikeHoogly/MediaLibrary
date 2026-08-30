#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — SCINDER les `kw_fr` melanges FR+EN des entrees relues depuis le XMP
──────────────────────────────────────────────────────────────────────────────

CE QUE LA MESURE DU 30/08 A TROUVE (`mesure_anglais_dans_fr.py`, puis a l'oeil
sur la copie) : les mots anglais dans `kw_fr` ne viennent PAS d'abord du
tagueur. **22 196 photos sur 42 714 (52 %) ont un `kw_en` VIDE** et un `kw_fr`
qui porte les deux langues a la suite — « chat, fenetre, ..., ciel, cat,
window, ..., sky, animal:Inti » : c'est la liste que `write_metadata` ecrit
dans le XMP (`kw_fr + kw_en`, dans CET ordre), relue telle quelle depuis le
fichier quand l'index a ete reconstruit (`pipe` absent, `at` = 11/07/2026
pour 3 147 d'entre elles). La recherche les trouve dans les deux langues ; les
puces de l'interface, elles, montrent de l'anglais. Le tagueur d'aujourd'hui
(`pipe=qwen3-vl:2b|v2ctx|kb1`, 4 804 photos) ne fuit presque pas : 11 photos
sur 4 804 pour les 25 mots testes.

LA REGLE A MESURER : puisque la liste est un bloc FRANCAIS suivi d'un bloc
ANGLAIS, il existe un point de coupure. On l'estime avec deux vocabulaires
appris sur les entrees SAINES (celles qui ont un `kw_en`) : V_fr = leurs
`kw_fr`, V_en = leurs `kw_en`, chacun avec sa frequence. Pour une liste
melangee, le score d'une coupure i = somme des votes FR du prefixe + votes EN
du suffixe (un tag connu des deux cotes vote pour le plus frequent ; un
inconnu ne vote pas ; les noms `personne:`/`animal:` restent en `kw_fr`).
La coupure retenue est celle du score maximal ; a score egal, la plus proche
du milieu (deux blocs de meme taille), et le nombre d'ex aequo est compte. La regle vit dans `scission_fr_en.py` (pure, partagee avec
`appliquer_scission_fr_en.py`). Ce banc n'ecrit rien : il compte combien
d'entrees se scindent nettement, et montre des exemples.

    mesure_scission_fr_en.py --base copie.db [--exemples 8]
"""
import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from scission_fr_en import PREFIXES_NOMS, scinder, vocabulaires, vote  # regle pure partagee


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def charger(base):
    if Path(base).name == 'photos.db':
        print('REFUS : ce banc lit une COPIE (mesure_copie_base.py), jamais photos.db')
        sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    out = {}
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if isinstance(e, dict) and not e.get('failed') and not e.get('video'):
            out[k] = e
    cx.close()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--marge', type=int, default=1, help='(garde : 1 = tout ce qui se scinde)')
    ap.add_argument('--exemples', type=int, default=8)
    a = ap.parse_args(argv)
    index = charger(a.base)
    vfr, ven = vocabulaires(index)
    print('photos taguees (copie) : %d ; vocabulaire appris sur les entrees a kw_en : FR %d tags, EN %d tags'
          % (len(index), len(vfr), len(ven)))
    cibles = {k: e for k, e in index.items() if not (e.get('kw_en') or [])}
    print('entrees a kw_en VIDE (la cible) : %d (%.1f %%)' % (len(cibles), 100.0 * len(cibles) / max(len(index), 1)))
    stats = Counter()
    marges = Counter()
    ex = []
    restes_en = Counter()
    for k, e in cibles.items():
        kw = [t for t in (e.get('kw_fr') or []) if isinstance(t, str)]
        noms = [t for t in kw if t.startswith(PREFIXES_NOMS)]
        corps = [t for t in kw if not t.startswith(PREFIXES_NOMS)]
        if not corps:
            stats['sans tag'] += 1
            continue
        fr, en, exaequo, i = scinder(corps, vfr, ven)
        marges[min(exaequo, 6)] += 1
        marge = 2 if exaequo == 1 else 1
        if not en:
            stats['deja tout francais (coupure a la fin)'] += 1
            continue
        if not fr:
            stats['tout anglais (rien a garder en FR)'] += 1
        if marge >= a.marge:
            stats['scindable, coupure UNIQUE' if exaequo == 1 else 'scindable, ex aequo tranche par le milieu'] += 1
            # ce qui resterait d anglais dans la partie FR malgre la coupure
            for t in fr:
                if vote(t, vfr, ven) < 0:
                    restes_en[t.lower()] += 1
            if len(ex) < a.exemples and (exaequo > 1 or len(ex) < a.exemples // 2):
                ex.append((k, fr, en, exaequo))
        else:
            stats['douteux'] += 1
    print('\nVERDICT :')
    for s, n in stats.most_common():
        print('  %6d  %s' % (n, s))
    print('  coupures ex aequo (1 = unique .. 6+) : %s' % ' '.join('%d:%d' % (m, marges[m]) for m in sorted(marges)))
    print('\n  tags votant ANGLAIS restes cote FR apres coupure (a regarder) : %d occurrences, top : %s'
          % (sum(restes_en.values()), ', '.join('%s(%d)' % (asc(t), c) for t, c in restes_en.most_common(15))))
    print('\nEXEMPLES :')
    for k, fr, en, marge in ex:
        print('  %s  (ex aequo %d)\n     FR: %s\n     EN: %s' % (asc(k[-70:]), marge, asc(', '.join(fr)), asc(', '.join(en))))
    print('\n(lecture seule : rien ecrit)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
