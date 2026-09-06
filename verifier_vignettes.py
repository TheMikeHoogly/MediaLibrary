#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Le chargement des vignettes est-il PARESSEUX et BORNE ?

Deux proprietes, et il faut les deux. Le 06/09, la vue Dossiers portait deja
`loading="lazy"` et cela n'a rien empeche : l'attribut natif ne borne pas le
nombre de requetes en vol. Sur un dossier de 2 139 photos, les six connexions
du navigateur sont restees prises une seconde par vignette pendant des dizaines
de minutes -- au point qu'un AUTRE onglet vers le meme serveur n'obtenait plus
de connexion. Sa requete n'apparait meme pas dans le journal du serveur.

Ce banc lit les fichiers, il n'ouvre pas de navigateur : il garde les deux
proprietes cablees. La preuve en reel (compter les requetes simultanees) se
fait au navigateur, une fois, et se note dans la ROADMAP.

Usage : python verifier_vignettes.py
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent


def lire(rel):
    return (RACINE / rel).read_text(encoding='utf-8', errors='ignore')


def main():
    fautes = []

    glob_js = lire('ui/global.js')
    serveur = lire('server.py')
    browse = lire('ui/pages/browse.html')
    galerie = lire('ui/pages/gallery.html')

    # 1) La file commune existe, et elle BORNE.
    if 'window.Vignettes' not in glob_js:
        fautes.append('ui/global.js : pas de file commune `Vignettes`.')
    m = re.search(r'EN_VOL_MAX\s*=\s*(\d+)', glob_js)
    if not m:
        fautes.append('ui/global.js : aucun plafond `EN_VOL_MAX`.')
    elif not 1 <= int(m.group(1)) <= 5:
        fautes.append(
            f'ui/global.js : EN_VOL_MAX = {m.group(1)} ; le navigateur '
            "n'ouvre que six connexions par hote, il doit en rester pour "
            'naviguer pendant qu\'une planche se remplit.')

    # 2) Un observateur, avec une marge A NOUS.
    if 'IntersectionObserver' not in glob_js:
        fautes.append('ui/global.js : pas d observateur de visibilite.')
    if 'rootMargin' not in glob_js:
        fautes.append('ui/global.js : pas de marge d avance au defilement.')

    # 3) La vue Dossiers ne pose plus de `src` en dur.
    tuile = re.search(r"<img class=\"th\"[^>]*>", serveur)
    if not tuile:
        fautes.append('server.py : tuile de la vue Dossiers introuvable.')
    else:
        t = tuile.group(0)
        if 'data-src=' not in t:
            fautes.append('server.py : la tuile ne passe pas par `data-src`.')
        if re.search(r'\ssrc=', t):
            fautes.append(
                'server.py : la tuile porte encore un `src` en dur — le '
                'navigateur chargera tout, quoi que fasse la file.')
        if 'loading="lazy"' in t:
            fautes.append(
                'server.py : `loading="lazy"` seul a deja echoue le 06/09 ; '
                "il ne borne rien. Le laisser ferait croire qu'on est protege.")

    # 4) Les deux planches branchent la file commune.
    if 'Vignettes.brancher' not in browse:
        fautes.append('ui/pages/browse.html : la planche ne branche pas la file.')
    if 'Vignettes.charger' not in galerie:
        fautes.append('ui/pages/gallery.html : la galerie ne passe pas par la file.')
    # La galerie ne doit plus poser `src` elle-meme dans son observateur, sauf
    # en REPLI explicite (navigateur sans la file).
    obs = galerie.split('new IntersectionObserver')[1].split('rootMargin')[0] \
        if 'new IntersectionObserver' in galerie else ''
    poses = [l for l in obs.splitlines()
             if 'img.src = img.dataset.src' in l and 'else' not in l]
    if poses:
        fautes.append('ui/pages/gallery.html : l observateur pose encore `src` '
                      'hors du repli — la borne ne s applique pas.')

    # 5) La tuile garde sa place avant d avoir son image.
    if 'contain-intrinsic-size' not in browse:
        fautes.append('ui/pages/browse.html : la tuile ne reserve pas sa '
                      'hauteur ; la planche sautera au defilement.')

    for f in fautes:
        print('  FAUTE :', f)
    if fautes:
        print(f'\n{len(fautes)} faute(s).')
        return 1
    print('  OK  file commune bornee (EN_VOL_MAX) + observateur avec marge')
    print('  OK  vue Dossiers : data-src, aucun src en dur, plus de lazy natif')
    print('  OK  les deux planches passent par la file commune')
    print('  OK  la tuile reserve sa place avant de charger')
    print('\nVIGNETTES : paresseuses ET bornees.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
