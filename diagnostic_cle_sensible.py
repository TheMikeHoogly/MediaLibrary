#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pourquoi « Fichier introuvable » sur une photo qui EST la ?

Le 10/09, la derniere photo de l'onglet /sensibles refuse tout verdict :
« Impossible : Fichier introuvable. » Or sa VIGNETTE s'affiche -- donc le
serveur sait lire ce fichier par la meme cle. Deux chemins partent de la meme
cle et l'un des deux se perd.

Cet instrument ne repare rien. Il refait, pas a pas et en imprimant chaque
etat intermediaire, la resolution que fait `/api/files/delete` :

    cle d'index  ->  _key_to_target()  ->  (idx, rel)
                 ->  resolve_target()  ->  chemin absolu
                 ->  .exists()

et, quand ca casse, il liste le dossier parent en comparant les noms CARACTERE
PAR CARACTERE (`repr` et points de code). C'est la seule facon de voir une
difference d'unicode -- un « e » precompose contre un « e » + accent combinant
sont deux chaines differentes que le terminal dessine pareil, et SMB rend
parfois l'une quand l'index porte l'autre.

  python diagnostic_cle_sensible.py
  python diagnostic_cle_sensible.py --cle "\\\\NAS\\home\\...\\x.jpg"
"""

import argparse
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))


def _pkey(p):
    """Copie CONFORME de server._pkey. Copiee et non importee : importer
    server.py demarre les fils et les files. Si l'original bouge, ce banc
    ment -- d'ou l'impression de la definition dans le rapport."""
    return Path(p).as_posix().lower()


def _lire_dirs(fichier):
    dirs = []
    try:
        for ligne in Path(fichier).read_text(encoding='utf-8').splitlines():
            ligne = ligne.strip().strip('"')
            if not ligne or ligne.startswith('#'):
                continue
            p = Path(ligne)
            if p.is_dir():
                dirs.append(p)
            else:
                print("  ! racine configuree mais ABSENTE : %r" % ligne)
    except OSError:
        pass
    return dirs


def media_roots():
    """Copie CONFORME de server.media_roots (sans le cache)."""
    up = None
    try:
        for ligne in (RACINE / 'dossier_uploads.txt').read_text(
                encoding='utf-8').splitlines():
            ligne = ligne.strip().strip('"')
            if ligne and not ligne.startswith('#'):
                up = Path(ligne)
                break
    except OSError:
        pass
    roots = [("Uploads", up)] if up else []
    seen = {str(up).lower()} if up else set()
    for d in (_lire_dirs(RACINE / 'dossiers_a_taguer.txt')
              + _lire_dirs(RACINE / 'dossiers_a_explorer.txt')):
        k = str(d).lower()
        if k in seen:
            continue
        seen.add(k)
        roots.append((d.name or str(d), d))
    return roots


def key_to_target(key, roots):
    """Copie CONFORME de server._key_to_target, mais BAVARDE."""
    p = Path(key)
    if not p.is_absolute():
        print("    cle RELATIVE -> racine 0, rel=%r" % p.as_posix())
        return 0, p.as_posix()
    na = _pkey(p)
    best = None
    for i, (label, root) in enumerate(roots):
        rp = _pkey(Path(root)).rstrip('/')
        dedans = (na != rp and na.startswith(rp + '/'))
        print("    racine %d  %-10s %-45s -> %s"
              % (i, label, rp[:45], "CONTIENT" if dedans else "non"))
        if not dedans:
            continue
        rel = p.as_posix()[len(Path(root).as_posix()):].lstrip('/')
        if best is None or len(rp) > best[2]:
            best = (i, rel, len(rp))
    return (best[0], best[1]) if best else None


def montrer_nom(nom, marque=' '):
    """Le nom, sa forme unicode, et ses points de code s'il sort de l'ASCII."""
    nfc = unicodedata.is_normalized('NFC', nom)
    hors = [c for c in nom if ord(c) > 127]
    detail = ''
    if hors:
        detail = ('  hors-ASCII: ' +
                  ' '.join('U+%04X(%s)' % (ord(c), c) for c in hors[:8]))
    return "  %s %-52r NFC=%s%s" % (marque, nom, 'oui' if nfc else 'NON', detail)


def enqueter(cle, roots):
    print("=" * 74)
    print("  CLE : %r" % cle)
    print("  longueur : %d caracteres" % len(cle))
    hors = [c for c in cle if ord(c) > 127]
    if hors:
        print("  hors-ASCII dans la cle : %s"
              % ' '.join('U+%04X(%s)' % (ord(c), c) for c in hors[:12]))
    print("  NFC ? %s" % ('oui' if unicodedata.is_normalized('NFC', cle) else 'NON'))
    print("-" * 74)
    print("  1) _key_to_target")
    tgt = key_to_target(cle, roots)
    if not tgt:
        print("    => AUCUNE racine. Le serveur dirait « Photo introuvable")
        print("       dans les dossiers connus. » -- ce n'est PAS le message vu.")
        return
    idx, rel = tgt
    print("    => idx=%d  rel=%r" % (idx, rel))

    print("  2) resolve_target")
    try:
        root = Path(roots[idx][1]).resolve()
    except Exception as e:                                        # noqa: BLE001
        print("    => racine irresoluble : %s" % e)
        return
    parts = [s for s in rel.replace('\\', '/').split('/') if s not in ('', '.')]
    cible = root.joinpath(*parts).resolve() if parts else root
    print("    racine resolue : %r" % str(root))
    print("    cible          : %r" % str(cible))
    dedans = (cible == root or root in cible.parents)
    print("    dans la racine : %s" % ('oui' if dedans else 'NON -> refus'))

    print("  3) le verdict de l'OS")
    print("    cible.exists()      : %s" % cible.exists())
    print("    cible.is_file()     : %s" % cible.is_file())
    print("    Path(cle).exists()  : %s" % Path(cle).exists())
    print("    parent.is_dir()     : %s" % cible.parent.is_dir())

    if cible.exists():
        print("  => LE FICHIER EST LA. Si l'UI dit le contraire, ce n'est pas")
        print("     ici que ca casse : regarder _permis() et le geste exact.")
        return

    print("  4) le dossier parent, nom par nom")
    try:
        noms = sorted(x.name for x in cible.parent.iterdir())
    except OSError as e:
        print("    parent illisible : %s" % e)
        return
    cherche = cible.name
    print("    %d entree(s). On cherche :" % len(noms))
    print(montrer_nom(cherche, '?'))
    exact = [n for n in noms if n == cherche]
    casse = [n for n in noms if n.lower() == cherche.lower() and n != cherche]
    plies = [n for n in noms
             if unicodedata.normalize('NFC', n).lower()
             == unicodedata.normalize('NFC', cherche).lower() and n != cherche]
    if exact:
        print("    -> nom EXACT present, et pourtant exists() dit non :")
        print("       c'est un probleme d'ACCES, pas de nom (droits, SMB).")
    for n in casse:
        print("    -> meme nom a la CASSE pres :")
        print(montrer_nom(n, '!'))
    for n in plies:
        if n in casse:
            continue
        print("    -> meme nom apres normalisation UNICODE :")
        print(montrer_nom(n, '!'))
    if not (exact or casse or plies):
        proches = [n for n in noms if n[:8].lower() == cherche[:8].lower()]
        print("    -> aucun homonyme. Voisins par le debut du nom :")
        for n in proches[:6]:
            print(montrer_nom(n))
        if not proches:
            print("       (aucun voisin : le fichier a bel et bien bouge)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--cle', default='', help='une cle precise a enqueter')
    ap.add_argument('--toutes', action='store_true',
                    help='toutes les cles en attente de verdict')
    a = ap.parse_args(argv)

    roots = media_roots()
    print("=" * 74)
    print("  RACINES NAVIGABLES (%d)" % len(roots))
    for i, (label, r) in enumerate(roots):
        print("    %d  %-10s %r  is_dir=%s" % (i, label, str(r), Path(r).is_dir()))

    cles = []
    if a.cle:
        cles = [a.cle]
    else:
        import visibilite as vis
        from store_sqlite import open_store
        db = RACINE / 'photos.db'
        if not db.exists():
            print("  photos.db absente.")
            return 2
        st = open_store(RACINE / 'tags_index.json', RACINE, None)
        for cle, e in list(st.data.items()):
            if vis.en_attente(e):
                cles.append(cle)
        print("  EN ATTENTE DE VERDICT : %d" % len(cles))
        if not a.toutes:
            cles = cles[:5]

    if not cles:
        print("  Rien a enqueter.")
        return 0
    for cle in cles:
        enqueter(cle, roots)
    print("=" * 74)
    print("  Rien n a ete modifie. Ce banc LIT.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
