#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les fichiers au CONTENU PERDU existent-ils encore dans le Takeout ?
==============================================================================

CE QUI EST PERDU, ET POURQUOI ON CHERCHE AILLEURS

942 fichiers du fonds portent 2 a 3 Mo remplis d'un message d'outil de
recuperation de disque : pas des images abimees, plus d'images du tout
(`tagging_meta.classe_contenu` -> `perdu-texte` / `perdu-vide`). Ils sont
dates de 2008 a 2015 et ils sont passes inapercus PARCE QU'ILS SONT LA, a la
bonne taille : tout controle qui verifie la presence ou le poids les compte
comme sains.

Le Takeout Google est la derniere copie connue d'avant l'incident. S'ils y
sont, ce n'est pas une perte, c'est une RESTAURATION.

CE QUE CE BANC FAIT, ET SURTOUT CE QU'IL NE FAIT PAS

Il COMPARE, il ne restaure rien, il n'ecrit dans aucun fichier du fonds. Il
lit une COPIE de la base (jamais `photos.db` : le serveur en est l'ecrivain
unique) et l'arbre du Takeout, et il dit qui pourrait revenir.

TROIS VERDICTS, ET LEUR NUANCE

  RETROUVE   le nom existe dans le Takeout ET la copie Google est PLUS GROSSE
             que le residu du fonds. C'est le cas qui rend une restauration
             plausible : le fichier perdu pese le message d'erreur, pas la
             photo.
  DOUTEUX    le nom existe mais la copie Google pese autant ou moins. Google
             ne peut pas avoir un fichier plus petit qu'une vraie photo ET
             etre la bonne source -- sauf si le residu est gros. A REGARDER,
             jamais a restaurer en masse.
  ABSENT     le nom n'est pas dans le Takeout. Perdu pour de bon, ici.

POURQUOI LE NOM SEUL, ET PAS UNE EMPREINTE. Il n'y a rien a comparer : le
fichier du fonds ne contient plus l'image. Une empreinte dirait seulement que
les deux different, ce qu'on sait deja. Le NOM est le seul lien qui subsiste,
et c'est pour ca que le verdict RETROUVE est une PISTE et pas une preuve --
un homonyme reste possible, et le rapport le dit au lieu de le taire.

    python mesure_copie_base.py --vers copie.db --source photos.db
    python verifier_perdus_dans_takeout.py --base copie.db

Sortie ASCII pure : la console de Mike est en cp1252, et un banc qui imprime
un caractere qu'elle ne sait pas rendre fait REFUSER la livraison.
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import tagging_meta as TM

TAKEOUT_DEFAUT = r"C:\GOOGLE PHOTOS\extrait"
MEDIA = {'.jpg', '.jpeg', '.png', '.gif', '.heic', '.mp4', '.mov', '.avi',
         '.3gp', '.m4v', '.mpg', '.webp', '.tif', '.tiff'}


def perdus_de_la_base(base):
    """Les entrees dont le CONTENU ne reviendra pas, telles que le serveur
    les classe -- la meme fonction, pas une seconde regle qui divergerait."""
    if Path(base).name == 'photos.db':
        print("REFUS : ce banc lit une COPIE (mesure_copie_base.py),"
              " jamais photos.db")
        sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(),
                         uri=True)
    out = []
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if not isinstance(e, dict) or not e.get('failed'):
            continue
        if TM.contenu_perdu(e.get('classe') or ''):
            out.append((k, Path(k).name, e.get('size') or 0,
                        e.get('classe') or ''))
    cx.close()
    return out


def diagnostic(base):
    """CE QUE LA BASE PORTE VRAIMENT, quand la recherche ne trouve rien.

    Un zero qui ne sait pas distinguer « il n y a rien » de « j ai cherche au
    mauvais endroit » est le defaut le plus cher de ce projet -- il a coute
    deux fois : `retenter_tmp_orphelins` regardait `retag_fail` quand les
    photos etaient fermees par `file_error`, et le banc etait vert sur 14 vrais
    fichiers. Ici, la meme prudence : si la moisson est vide, on DIT ou on a
    regarde et ce qu on y a vu."""
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(),
                         uri=True)
    tables = [r[0] for r in cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    total = echecs = avec_classe = 0
    classes, champs_echec = {}, {}
    for _k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        total += 1
        for champ in ('failed', 'file_error', 'retag_error', 'retag_fail',
                      'write_fails'):
            if e.get(champ):
                champs_echec[champ] = champs_echec.get(champ, 0) + 1
        if e.get('failed'):
            echecs += 1
        c = e.get('classe')
        if c:
            avec_classe += 1
            classes[c] = classes.get(c, 0) + 1
    cx.close()
    print()
    print("  -- DIAGNOSTIC : pourquoi la moisson est vide ------------------")
    print("     tables            : %s" % ', '.join(sorted(tables)))
    print("     entrees `tags`    : %d" % total)
    print("     portant `failed`  : %d" % echecs)
    print("     portant `classe`  : %d" % avec_classe)
    if champs_echec:
        print("     champs d echec vus : %s"
              % ', '.join('%s=%d' % kv for kv in sorted(champs_echec.items())))
    if classes:
        print("     classes vues :")
        for c, n in sorted(classes.items(), key=lambda x: -x[1])[:12]:
            marque = "  <- contenu perdu" if TM.contenu_perdu(c) else ""
            print("       %-16s %6d%s" % (c, n, marque))
    else:
        print("     AUCUNE entree ne porte de `classe`.")
    print("  ---------------------------------------------------------------")


def index_takeout(racine):
    """{nom en minuscules -> [(chemin, taille), ...]}.

    Un dict de LISTES et non de chemins : le Takeout range par album, le meme
    nom peut donc apparaitre plusieurs fois. Ecraser silencieusement en
    garderait un au hasard -- et c'est justement le plus gros qui interesse."""
    par_nom = {}
    for dossier, _sd, fichiers in os.walk(racine, onerror=lambda e: None):
        for f in fichiers:
            if Path(f).suffix.lower() not in MEDIA:
                continue
            p = os.path.join(dossier, f)
            try:
                t = os.path.getsize(p)
            except OSError:
                continue
            par_nom.setdefault(f.lower(), []).append((p, t))
    return par_nom


def go(n):
    return n / 1_000_000_000.0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Les fichiers au contenu perdu sont-ils dans le Takeout ?")
    ap.add_argument('--base', default='copie.db')
    # LES COQUILLES NE SONT PLUS DANS L INDEX. Mesure du 08/09 : la base ne
    # porte plus AUCUNE entree `perdu-texte`/`perdu-vide` -- 8 `failed` en
    # tout, et deux classes seulement (`tronquee` 39, `image` 8). Normal : le
    # bat 45 les a mises en quarantaine le 06/09 et `scan:disparus` les a
    # sorties de l index. Elles se cherchent donc SUR LE DISQUE, la ou elles
    # sont : `--dossier <quarantaine>`, repetable.
    ap.add_argument('--dossier', action='append', default=[],
                    help='quarantaine a lire au lieu de la base (repetable)')
    ap.add_argument('--takeout', default=TAKEOUT_DEFAUT)
    ap.add_argument('--json', dest='sortie_json', default=None)
    ap.add_argument('--montrer', type=int, default=12)
    a = ap.parse_args(argv)

    racine = Path(a.takeout)
    if not racine.is_dir():
        print("REFUS : Takeout introuvable : %s" % racine)
        return 2

    if a.dossier:
        perdus = []
        for d in a.dossier:
            racine_q = Path(d)
            if not racine_q.is_dir():
                print("REFUS : quarantaine introuvable : %s" % racine_q)
                return 2
            for f in racine_q.rglob('*'):
                if f.is_file() and f.suffix.lower() in MEDIA:
                    try:
                        perdus.append((str(f), f.name, f.stat().st_size,
                                       'quarantaine'))
                    except OSError:
                        pass
        print("  source : %d quarantaine(s) sur le disque, pas l index."
              % len(a.dossier))
    else:
        perdus = perdus_de_la_base(a.base)
    print("  %d fichier(s) au contenu perdu dans la base." % len(perdus))
    if not perdus:
        print("  Rien a chercher -- et ca demande une explication, pas un OK.")
        diagnostic(a.base)
        return 0
    print("  indexation du Takeout par nom...")
    par_nom = index_takeout(racine)
    print("  %d nom(s) de media distincts dans le Takeout." % len(par_nom))
    print()

    retrouves, douteux, absents = [], [], []
    for cle, nom, taille, classe in perdus:
        cands = par_nom.get(nom.lower())
        if not cands:
            absents.append({'cle': cle, 'nom': nom, 'residu': taille,
                            'classe': classe})
            continue
        chemin, t = max(cands, key=lambda c: c[1])
        fiche = {'cle': cle, 'nom': nom, 'residu': taille, 'classe': classe,
                 'google': chemin, 'google_octets': t,
                 'exemplaires': len(cands)}
        (retrouves if t > taille else douteux).append(fiche)

    retrouves.sort(key=lambda f: -f['google_octets'])
    douteux.sort(key=lambda f: -f['google_octets'])

    print("=" * 74)
    print("  LES FICHIERS AU CONTENU PERDU SONT-ILS DANS LE TAKEOUT ?")
    print("=" * 74)
    print("  base    : %s" % a.base)
    print("  takeout : %s" % racine)
    print()
    print("  cherches   : %d" % len(perdus))
    print("  RETROUVES  : %-6d  (%.2f Go a recuperer chez Google)"
          % (len(retrouves), go(sum(f['google_octets'] for f in retrouves))))
    print("  DOUTEUX    : %-6d  (nom present, copie Google pas plus grosse)"
          % len(douteux))
    print("  ABSENTS    : %-6d" % len(absents))
    print()
    if retrouves:
        print("  Les plus gros RETROUVES :")
        for f in retrouves[:a.montrer]:
            print("    %-42s residu %6.2f Mo -> Google %7.2f Mo%s"
                  % (f['nom'][:42], f['residu'] / 1e6,
                     f['google_octets'] / 1e6,
                     "  (%d exemplaires)" % f['exemplaires']
                     if f['exemplaires'] > 1 else ""))
        print()
    if douteux:
        # LES DOUTEUX SE SONDENT. Ils sont peu nombreux et la question tient en
        # deux octets : `FF D8` = un vrai JPEG, autre chose = la meme coquille
        # que le fonds, montee chez Google avant qu on s en apercoive. Une
        # taille identique a l octet le SUGGERE ; l en-tete le PROUVE, et c est
        # le meme controle qui a valide les 4 rapatriees le 06/09.
        print("  Les DOUTEUX, SONDES (les 2 premiers octets tranchent) :")
        vrais = 0
        for f in douteux:
            try:
                with open(f['google'], 'rb') as fh:
                    tete = fh.read(4)
            except OSError:
                tete = b''
            jpeg = tete[:2] == b'\xff\xd8'
            mp4 = tete[:4] in (b'\x00\x00\x00\x18', b'\x00\x00\x00\x20')
            f['google_tete'] = tete.hex()
            f['google_est_media'] = bool(jpeg or mp4)
            vrais += 1 if (jpeg or mp4) else 0
            print("    %-38s residu %6.2f Mo = Google %6.2f Mo   tete %-8s %s"
                  % (f['nom'][:38], f['residu'] / 1e6,
                     f['google_octets'] / 1e6, tete.hex() or '(vide)',
                     "VRAIE PHOTO" if (jpeg or mp4) else "meme coquille"))
        print()
        if vrais:
            print("  --> %d a RECUPERER chez Google malgre la taille egale." % vrais)
        else:
            print("  --> AUCUN : Google porte la MEME coquille. La corruption")
            print("      est donc anterieure a l envoi chez Google, et il n y a")
            print("      rien a y chercher pour ces fichiers-la.")
        print()
    print("  PORTEE : la comparaison est faite sur le NOM et la TAILLE. Le")
    print("  fichier du fonds ne contient plus l image : il n y a aucune")
    print("  empreinte a comparer. Un RETROUVE est donc une PISTE tres forte,")
    print("  pas une preuve -- un homonyme reste possible. Regarder quelques")
    print("  photos avant d en restaurer neuf cents.")
    print()
    print("  RIEN N A ETE COPIE NI MODIFIE. Ce banc compare, il ne restaure pas.")
    print("=" * 74)

    if a.sortie_json:
        Path(a.sortie_json).write_text(json.dumps(
            {'takeout': str(racine), 'base': a.base,
             'cherches': len(perdus), 'retrouves': retrouves,
             'douteux': douteux, 'absents': absents},
            indent=2, ensure_ascii=False), encoding='utf-8')
        print("  rapport JSON : %s" % a.sortie_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
