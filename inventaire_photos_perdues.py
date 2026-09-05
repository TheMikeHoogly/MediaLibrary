#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inventaire — le REGISTRE des photos dont le contenu est perdu.
------------------------------------------------------------------------------

POURQUOI CE FICHIER DOIT EXISTER AVANT TOUT GESTE

941 fichiers de la phototheque sont des coquilles : 2 a 3 Mo remplis du texte
« Read error in the sector ! », sequelle de la recuperation d un vieux disque
tombe en panne. Ils ne redeviendront pas des photos. Le reflexe est de les
mettre a la corbeille -- et la corbeille du projet se purge toute seule au bout
de 180 jours.

Or ce qui reste de ces photos n est PAS le fichier : c est son NOM, son
DOSSIER et sa DATE. « Il y avait une photo appelee DSC00551.JPG, en aout 2008,
dans Sanetsch. » C est ce qui permettra, un jour, de reconnaitre une copie qui
resurgit -- le CD d un ami, une vieille sauvegarde, la meme sortie photographiee
par quelqu un d autre -- ou de savoir quoi chercher si le disque d origine est
repasse en recuperation. Trois giga-octets ne sont pas urgents ; cette trace-la
est irremplacable.

Le registre la met dans git, ou elle survit a la corbeille, au NAS et au
disque. APRES quoi, mettre les fichiers a la corbeille ne coute plus rien.

CE QUE CE SCRIPT LIT, ET N ECRIT PAS
    - `docs/images_illisibles.json` : le classement deja mesure (les octets).
    - une COPIE de la base (`--base copie.db`) : la date et la taille.
Il n ouvre aucune photo, ne touche ni l index ni le NAS, et n ecrit que ses
deux sorties : `docs/photos_perdues.md` (lisible) et `.json` (relisible).

USAGE
    inventaire_photos_perdues.py --base copie.db
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ICI = Path(__file__).resolve().parent
MOIS = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet',
        'aout', 'septembre', 'octobre', 'novembre', 'decembre']


def date_lisible(epoch):
    if not epoch:
        return ''
    try:
        t = time.localtime(float(epoch))
        return '%04d-%02d-%02d' % (t.tm_year, t.tm_mon, t.tm_mday)
    except (ValueError, TypeError, OverflowError, OSError):
        return ''


AN_RE = re.compile(r'(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)')


def annee_du_chemin(cle):
    """L annee lue dans le CHEMIN (« Photos Mike\\2008\\08 Aout\\... »).

    C est souvent la SEULE date qui reste : une entree marquee en echec ne
    garde ni `taken` ni `mtime` -- `_marquer_echec` remplace l entree entiere,
    et c est voulu pour une photo neuve qui echoue. Ici, la consequence est
    qu on ne sait plus QUAND la photo perdue a ete prise. Le dossier, lui, le
    dit encore. On prend la DERNIERE annee plausible du chemin : le nom de
    fichier (`13122010376.jpg`) est moins fiable que le dossier qui le porte,
    et le dossier vient en premier dans le chemin."""
    ans = AN_RE.findall(str(Path(cle).parent))
    return ans[-1] if ans else ''


def mtime_du_fichier(cle):
    """La date d ecriture du fichier, si le NAS repond. Elle peut avoir ete
    reecrite par la recuperation -- on la donne donc a titre indicatif, jamais
    contre l annee du dossier."""
    try:
        return Path(cle).stat().st_mtime
    except OSError:
        return None


def dates_depuis_base(base, cles):
    """{cle: (taken, mtime, size)} — lecture seule sur une COPIE."""
    if Path(base).name == 'photos.db':
        raise SystemExit('REFUS : ce script lit une COPIE (--base copie.db).')
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).as_posix(), uri=True)
    voulu, out = set(cles), {}
    for k, v in cx.execute('SELECT k, v FROM tags'):
        if k not in voulu:
            continue
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if isinstance(e, dict):
            out[k] = (e.get('taken'), e.get('mtime'), e.get('size'))
    cx.close()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--source', default='docs/images_illisibles.json')
    ap.add_argument('--md', default='docs/photos_perdues.md')
    ap.add_argument('--json', dest='sortie', default='docs/photos_perdues.json')
    a = ap.parse_args(argv)

    src = json.loads((ICI / a.source).read_text(encoding='utf-8'))
    perdues = [d for d in src.get('detail', [])
               if str(d.get('classe', '')).startswith('perdu-')]
    if not perdues:
        raise SystemExit('aucune entree perdue dans %s : rien a inventorier.'
                         % a.source)
    infos = dates_depuis_base(a.base, [d['cle'] for d in perdues])

    lignes, par_annee, par_dossier, octets = [], Counter(), Counter(), 0
    for d in sorted(perdues, key=lambda x: x['cle']):
        cle = d['cle']
        taken, mtime, size = infos.get(cle, (None, None, None))
        quand = date_lisible(taken) or date_lisible(mtime)
        annee = annee_du_chemin(cle)
        if not quand:
            # L entree en echec n a garde aucune date : on retombe sur le
            # dossier, puis sur le fichier. Sans ca, le registre aurait rendu
            # « ???? » pour les 942 -- une liste sans dates ne sert a
            # reconnaitre personne.
            quand = annee or date_lisible(mtime_du_fichier(cle))
        p = Path(cle)
        dossier = str(p.parent)
        o = d.get('octets') or size or 0
        octets += o
        par_annee[(annee or quand or '????')[:4]] += 1
        par_dossier[dossier] += 1
        lignes.append({'cle': cle, 'nom': p.name, 'dossier': dossier,
                       'date': quand, 'octets': o, 'classe': d['classe']})

    (ICI / a.sortie).write_text(json.dumps(
        {'quand': time.strftime('%Y-%m-%d %H:%M:%S'), 'n': len(lignes),
         'octets': octets, 'photos': lignes}, ensure_ascii=False, indent=1),
        encoding='utf-8')

    md = []
    md.append('# Registre des photos perdues\n')
    md.append('> Etabli le %s. **%d photos**, %.1f Go de fichiers qui n en '
              'portent plus une seule.\n' % (time.strftime('%d/%m/%Y'),
                                             len(lignes), octets / 1e9))
    md.append('Ces fichiers sont la, a la bonne taille, et entierement remplis '
              'du texte `Read error in the sector !` — sequelle de la '
              'recuperation d un disque tombe en panne. Le fichier ne vaut '
              'plus rien ; **son nom, son dossier et sa date, si**. C est ce '
              'qui permettra de reconnaitre une copie qui resurgit, ou de '
              'savoir quoi chercher si le disque d origine repasse un jour en '
              'recuperation. Ce registre est dans git : il survit a la '
              'corbeille, au NAS et au disque.\n')
    md.append('## Par annee\n')
    for an in sorted(par_annee):
        md.append('- **%s** : %d' % (an, par_annee[an]))
    md.append('\n## Les dossiers les plus touches\n')
    for dos, n in par_dossier.most_common(25):
        md.append('- %d — `%s`' % (n, dos))
    md.append('\n## La liste\n')
    md.append('| date | nom | dossier |')
    md.append('|---|---|---|')
    for l in lignes:
        md.append('| %s | `%s` | `%s` |' % (l['date'] or '?', l['nom'],
                                            l['dossier']))
    (ICI / a.md).write_text('\n'.join(md) + '\n', encoding='utf-8')

    print('%d photo(s) perdue(s), %.1f Go' % (len(lignes), octets / 1e9))
    print('par annee : ' + ', '.join('%s:%d' % (a_, n)
                                     for a_, n in sorted(par_annee.items())))
    print('registre : %s (lisible) et %s' % (a.md, a.sortie))
    return 0


if __name__ == '__main__':
    sys.exit(main())
