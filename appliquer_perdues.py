#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Applique les deux gestes des photos PERDUES — reversiblement.
------------------------------------------------------------------------------

Contexte : 942 fichiers de la phototheque sont des coquilles de 2 a 3 Mo
remplies du texte « Read error in the sector ! », sequelle de la recuperation
d un disque tombe en panne. Le registre (`docs/photos_perdues.md`) est dans
git ; la recherche d homonymes (`docs/perdues_ailleurs.json`) dit lesquelles
existent ailleurs.

DEUX GESTES, ET L ORDRE COMPTE

  --restaurer   Rapatrie les photos qui n existent QUE dans un reservoir
                exterieur (le Takeout Google) : la vraie photo prend la place
                de la coquille. A FAIRE EN PREMIER -- apres la mise en
                corbeille, la coquille n est plus la pour dire ou remettre la
                photo.
  --corbeille   Deplace les coquilles restantes vers
                `.corbeille-rangement\\perdues_<date>\\`, en gardant l
                arborescence, avec un manifeste. RIEN N EST SUPPRIME : le bat
                24 purge la corbeille quand Mike le decide.

APERCU PAR DEFAUT. Sans `--appliquer`, le script dit ce qu il ferait et ne
touche a rien. `--undo <manifeste>` remet tout en place.

CE QU IL NE FAIT PAS : ecrire dans l index. Le serveur peut rester allume — un
fichier disparu devient orphelin et sort de l index au scan suivant, par le
chemin normal (`forget_everywhere`, motif `scan:disparus`), et un fichier
RESTAURE est repris par la passe des fichiers modifies (06/09 : une entree en
echec dont le fichier a ete reecrit apres coup redevient candidate).

USAGE
    python appliquer_perdues.py --restaurer
    python appliquer_perdues.py --restaurer --appliquer
    python appliquer_perdues.py --corbeille
    python appliquer_perdues.py --corbeille --appliquer
    python appliquer_perdues.py --undo docs\\undo_perdues_AAAAMMJJ_HHMMSS.json --appliquer
"""
import argparse
import io
import json
import shutil
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
CORBEILLE = '.corbeille-rangement'


def vraie_image(chemin):
    """Le fichier porte-t-il de vrais pixels ? Meme regle que partout ailleurs."""
    import tagging_meta
    try:
        with io.open(chemin, 'rb') as f:
            tete = f.read(16)
    except OSError:
        return False
    return not tagging_meta.contenu_perdu(tagging_meta.classe_contenu(tete))


def racine_de(cle):
    """`\\\\NAS\\home\\Photos` depuis une cle `\\\\NAS\\home\\Photos\\Photos Mike\\...`.
    La corbeille vit a la racine du partage, comme celle du dedoublonnage."""
    p = Path(cle)
    parts = p.parts
    for i, seg in enumerate(parts):
        if seg.lower() == 'photos' and i > 0:
            return Path(*parts[:i + 1])
    return p.parent


def charger(registre, ailleurs):
    reg = json.loads((ICI / registre).read_text(encoding='utf-8'))
    ail = json.loads((ICI / ailleurs).read_text(encoding='utf-8'))
    exterieurs = {}
    for e in ail.get('detail', []):
        dehors = [c for c in e['candidats'] if c['ou'] != 'le NAS (index)']
        dedans = [c for c in e['candidats'] if c['ou'] == 'le NAS (index)']
        if dehors and not dedans:
            exterieurs[e['perdue']] = dehors[0]['chemin']
    return reg['photos'], exterieurs


# Ou vont les journaux d annulation. Attribut de module pour que les tests
# ecrivent dans leur arbre jouet et ne semen t pas de fichiers dans `docs/`.
DOSSIER_JOURNAL = None
DERNIER_JOURNAL = None


def journal(nom, ops):
    """Le journal d annulation. Son nom porte la SECONDE -- et deux gestes dans
    la meme seconde ecraseraient le premier journal, donc la possibilite meme
    d annuler le premier geste. Un suffixe est ajoute plutot que d ecraser :
    perdre un journal d annulation en silence est le genre de perte qui ne se
    voit que le jour ou on en a besoin."""
    global DERNIER_JOURNAL
    d = Path(DOSSIER_JOURNAL) if DOSSIER_JOURNAL else (ICI / 'docs')
    d.mkdir(parents=True, exist_ok=True)
    base = 'undo_perdues_%s' % time.strftime('%Y%m%d_%H%M%S')
    f = d / (base + '.json')
    i = 2
    while f.exists():
        f = d / ('%s_%d.json' % (base, i))
        i += 1
    f.write_text(json.dumps({'geste': nom, 'quand': time.strftime('%Y-%m-%d %H:%M:%S'),
                             'ops': ops}, ensure_ascii=False, indent=1),
                 encoding='utf-8')
    DERNIER_JOURNAL = f
    return f


def restaurer(perdues, exterieurs, appliquer):
    """La vraie photo prend la place de la coquille ; la coquille part en
    quarantaine AVANT, jamais apres : si la copie echoue a mi-chemin, on veut
    encore avoir les deux."""
    if not exterieurs:
        print('aucune photo a rapatrier : rien qui n existe QUE dehors.')
        return []
    print('%d photo(s) a rapatrier depuis un reservoir exterieur :' % len(exterieurs))
    ops = []
    for cle, source in sorted(exterieurs.items()):
        ok = vraie_image(source)
        print('  %s' % Path(cle).name)
        print('      <- %s%s' % (source, '' if ok else '   [SOURCE ILLISIBLE - SAUTEE]'))
        if not ok:
            continue
        quarantaine = (racine_de(cle) / CORBEILLE /
                       ('perdues_restaurees_%s' % time.strftime('%Y%m%d')) /
                       Path(cle).name)
        ops.append({'cle': cle, 'source': source, 'coquille': str(quarantaine)})
    if not appliquer:
        print('APERCU : rien n a bouge. --appliquer pour executer.')
        return []
    faits = []
    for op in ops:
        try:
            Path(op['coquille']).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(op['cle'], op['coquille'])
            shutil.copy2(op['source'], op['cle'])
            faits.append(op)
            print('  OK  %s' % Path(op['cle']).name)
        except OSError as e:
            print('  ECHEC %s : %s' % (Path(op['cle']).name, str(e)[:80]))
    if faits:
        print('journal : %s' % journal('restaurer', faits).name)
    return faits


def corbeille(perdues, exterieurs, appliquer, limite=0):
    """Les coquilles partent en quarantaine, arborescence gardee. Celles qui
    attendent encore un rapatriement sont SAUTEES : les mettre a la corbeille
    d abord ferait perdre l endroit ou remettre la photo."""
    cibles = [p for p in perdues if p['cle'] not in exterieurs]
    saute = len(perdues) - len(cibles)
    if limite:
        cibles = cibles[:limite]
    octets = sum(p.get('octets') or 0 for p in cibles)
    print('%d coquille(s) a mettre en quarantaine, %.2f Go'
          % (len(cibles), octets / 1e9))
    if saute:
        print('%d sautee(s) : elles attendent un rapatriement (--restaurer '
              'd abord).' % saute)
    if not cibles:
        return []
    racine = racine_de(cibles[0]['cle'])
    dest = racine / CORBEILLE / ('perdues_%s' % time.strftime('%Y%m%d_%H%M%S'))
    print('quarantaine : %s' % dest)
    for p in cibles[:10]:
        print('  %s' % p['cle'])
    if len(cibles) > 10:
        print('  ... et %d autre(s)' % (len(cibles) - 10))
    if not appliquer:
        print('APERCU : rien n a bouge. --appliquer pour executer.')
        return []
    faits = []
    for p in cibles:
        src = Path(p['cle'])
        try:
            rel = src.relative_to(racine)
        except ValueError:
            rel = Path(src.name)
        dst = dest / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            faits.append({'cle': p['cle'], 'dst': str(dst)})
        except OSError as e:
            print('  ECHEC %s : %s' % (src.name, str(e)[:80]))
    print('%d fichier(s) deplace(s).' % len(faits))
    if faits:
        f = journal('corbeille', faits)
        (dest / 'manifeste.json').write_text(
            json.dumps({'quand': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'n': len(faits), 'ops': faits}, ensure_ascii=False,
                       indent=1), encoding='utf-8')
        print('journal : %s   (manifeste aussi dans la quarantaine)' % f.name)
    return faits


def undo(chemin, appliquer):
    d = json.loads(Path(chemin).read_text(encoding='utf-8'))
    ops = d['ops']
    print('annulation de « %s » : %d operation(s)' % (d['geste'], len(ops)))
    if not appliquer:
        print('APERCU : rien n a bouge. --appliquer pour executer.')
        return
    n = 0
    for op in reversed(ops):
        try:
            if d['geste'] == 'corbeille':
                Path(op['cle']).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(op['dst'], op['cle'])
            else:
                Path(op['cle']).unlink(missing_ok=True)
                shutil.move(op['coquille'], op['cle'])
            n += 1
        except OSError as e:
            print('  ECHEC %s : %s' % (Path(op['cle']).name, str(e)[:80]))
    print('%d operation(s) annulee(s).' % n)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--registre', default='docs/photos_perdues.json')
    ap.add_argument('--ailleurs', default='docs/perdues_ailleurs.json')
    ap.add_argument('--restaurer', action='store_true')
    ap.add_argument('--corbeille', action='store_true')
    ap.add_argument('--undo', default='')
    ap.add_argument('--limite', type=int, default=0)
    ap.add_argument('--appliquer', action='store_true')
    a = ap.parse_args(argv)
    if a.undo:
        undo(a.undo, a.appliquer)
        return 0
    perdues, exterieurs = charger(a.registre, a.ailleurs)
    if a.restaurer:
        restaurer(perdues, exterieurs, a.appliquer)
    elif a.corbeille:
        corbeille(perdues, exterieurs, a.appliquer, a.limite)
    else:
        ap.error('choisir --restaurer, --corbeille ou --undo')
    return 0


if __name__ == '__main__':
    sys.exit(main())
