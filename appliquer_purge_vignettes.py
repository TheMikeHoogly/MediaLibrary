#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purger les vignettes ORPHELINES — point d'audit O15.

Mesure du 10/09 (`mesure_caches_vignettes.py`, sur la vraie machine) :

    photo_thumbs    7 737 fichiers  450,7 Mo   dont  4 315 orphelins  313,8 Mo
    face_thumbs    34 771 fichiers  224,1 Mo   dont 28 880 orphelins  192,9 Mo
    animal_thumbs   4 819 fichiers   47,2 Mo   dont  3 578 orphelins   34,7 Mo
    TOTAL          47 327 fichiers  722,1 Mo   dont 36 773 orphelins  541,4 Mo

**Ce que « reversible » veut dire ici, et pourquoi ce n'est pas une corbeille.**
La regle du projet est qu'un geste destructif est reversible ou n'est pas. Une
vignette n'est pas une donnee : c'est un CALCUL mis de cote. Elle se refait a
la premiere demande, en lisant l'original sur le NAS. Deplacer 541 Mo vers une
corbeille ne rendrait donc rien de plus qu'une suppression — cela occuperait
la place deux fois en attendant qu'on l'oublie. **La reversibilite est la
regeneration**, et le journal dit ce qui est parti.

**LE GARDE-FOU, ET C'EST LE COEUR DE CET OUTIL.** Les noms vivants sont
RECALCULES ici, avec les memes formules que `server.py`. Si l'une d'elles
change la-bas sans changer ici, ce script croira que TOUT le cache est orphelin
et proposera de tout effacer. Deux verrous contre ca :

  1. **Le taux de reconnaissance.** Si moins de `--plancher` % des fichiers
     d'un dossier correspondent a un nom vivant, le dossier est REFUSE en
     bloc : ce n'est pas un cache perime, c'est une formule qui ne parle plus
     la meme langue.
  2. **L'age plancher.** Rien de plus jeune que `--jours` n'est touche. Une
     formule fausse se trompe d'abord sur les vignettes qu'on vient de creer,
     c'est-a-dire celles qui servent maintenant : les epargner rend l'erreur
     visible avant qu'elle soit totale.

  python appliquer_purge_vignettes.py                 # APERCU, n'efface rien
  python appliquer_purge_vignettes.py --appliquer
  python appliquer_purge_vignettes.py --jours 30 --appliquer
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

DOSSIERS = ('photo_thumbs', 'face_thumbs', 'animal_thumbs')

# Les caches dont la cle ne porte PAS le mtime — donc les seuls dont l'age
# reste lisible pendant une campagne de retag. Voir `trier`.
SANS_MTIME = ('face_thumbs', 'animal_thumbs')
PLANCHER_RECONNU = 5.0      # % de fichiers vivants en dessous duquel on refuse
JOURS_PAR_DEFAUT = 7


def _index():
    from store_sqlite import open_store
    if not (RACINE / 'photos.db').exists():
        raise SystemExit('  photos.db absente.')
    return (open_store(RACINE / 'tags_index.json', RACINE, None).data,
            open_store(RACINE / 'faces_index.json', RACINE, None).data,
            open_store(RACINE / 'animals_index.json', RACINE, None).data)


def trier(jours, plancher, dossiers=None):
    """(a_effacer, refus) — a_effacer : {dossier: [(chemin, octets, jours)]}.

    `dossiers` restreint le travail. Un seul appelant s'en sert et sa raison
    vaut d'etre lue : `photo_thumbs` est nomme `md5(cle|taille|MTIME)`, et la
    campagne de retag reecrit les XMP donc le mtime. Tant qu'elle tourne, ce
    cache se perime plus vite qu'il ne se remplit et **on ne sait plus lire son
    age** — 16 % seulement de ses vignettes les plus JEUNES sont reconnues
    (mesure du 10/09), ce qui ressemble a une derive de formule sans en etre
    une (2 563 noms reconnus prouvent le contraire : on ne tombe pas par
    accident sur des milliers de md5 justes). Les deux autres caches sont
    nommes sur la BBOX, que rien ne reecrit en ce moment : leurs 50 plus jeunes
    sont reconnues a 100 %. **On purge donc ce qu'on sait lire, et on attend
    pour le reste.**"""
    import mesure_caches_vignettes as M
    vivants = M.noms_vivants(*_index())
    maintenant = time.time()
    a_effacer, refus, vus = {}, [], {}
    for d in (dossiers or DOSSIERS):
        dossier = RACINE / d
        if not dossier.is_dir():
            continue
        vs = vivants[d]
        n = reconnus = 0
        morts = []
        with os.scandir(dossier) as it:
            for x in it:
                if not x.is_file():
                    continue
                n += 1
                if Path(x.name).stem in vs:
                    reconnus += 1
                    continue
                st = x.stat()
                age = (maintenant - st.st_mtime) / 86400
                if age < jours:
                    continue
                morts.append((x.path, st.st_size, age))
        taux = (100.0 * reconnus / n) if n else 100.0
        vus[d] = (n, reconnus, taux)
        # VERROU 1 : une formule qui ne reconnait plus rien n'a pas trouve un
        # cache perime, elle a cesse de parler la meme langue que server.py.
        if n and taux < plancher:
            refus.append((d, "seulement %.1f %% des %d fichiers correspondent "
                              "a un nom vivant (plancher %.1f %%) — la formule "
                              "de nommage a probablement change dans server.py"
                          % (taux, n, plancher)))
            continue
        a_effacer[d] = sorted(morts, key=lambda t: -t[1])
    return a_effacer, refus, vus


def effacer(a_effacer, jours):
    """Efface, et journalise ce qui est parti. Rend (n, octets, journal)."""
    faits, octets, lignes = 0, 0, []
    for d, morts in a_effacer.items():
        for chemin, taille, age in morts:
            try:
                os.remove(chemin)
            except OSError as e:                                  # noqa: PERF203
                lignes.append({'dossier': d, 'fichier': Path(chemin).name,
                               'octets': taille, 'echec': str(e)})
                continue
            faits += 1
            octets += taille
            lignes.append({'dossier': d, 'fichier': Path(chemin).name,
                           'octets': taille, 'jours': round(age, 1)})
    journal = RACINE / 'docs' / ('undo_vignettes_%s.json'
                                 % time.strftime('%Y%m%d_%H%M%S'))
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text(json.dumps(
        {'quand': time.time(), 'jours_plancher': jours,
         'note': ("Une vignette se REGENERE a la premiere demande : ce journal "
                  "dit ce qui est parti, il n'a pas a le rendre."),
         'efface': lignes}, indent=1, ensure_ascii=False), encoding='utf-8')
    return faits, octets, journal


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--appliquer', action='store_true')
    ap.add_argument('--jours', type=int, default=JOURS_PAR_DEFAUT,
                    help="ne rien toucher de plus jeune que N jours")
    ap.add_argument('--plancher', type=float, default=PLANCHER_RECONNU)
    ap.add_argument('--dossiers', default=','.join(SANS_MTIME),
                    help='les caches a traiter (defaut : ceux qu on sait lire '
                         'pendant la campagne)')
    a = ap.parse_args(argv)

    choisis = [d.strip() for d in a.dossiers.split(',') if d.strip()]
    inconnus = [d for d in choisis if d not in DOSSIERS]
    if inconnus:
        print('  dossier inconnu : %s' % ', '.join(inconnus))
        return 2
    a_effacer, refus, vus = trier(a.jours, a.plancher, choisis)

    print('=' * 74)
    print('  O15 — PURGE DES VIGNETTES ORPHELINES')
    print('=' * 74)
    print("  Rien de plus jeune que %d jours n'est touche." % a.jours)
    print('-' * 74)
    total_n = total_o = 0
    ecartes = [d for d in DOSSIERS if d not in choisis]
    if ecartes:
        print('  ECARTES de cette purge : %s' % ', '.join(ecartes))
        print('     leur nom porte le MTIME, que la campagne de retag reecrit :')
        print('     tant qu elle tourne, leur age ne dit plus rien. On purge')
        print('     ce qu on sait lire, et on attend pour le reste.')
        print('-' * 74)
    for d in choisis:
        if d in dict(refus):
            continue
        n, reconnus, taux = vus.get(d, (0, 0, 100.0))
        morts = a_effacer.get(d, [])
        o = sum(t[1] for t in morts)
        total_n += len(morts)
        total_o += o
        print('  %-14s %5d fichier(s), %.1f %% reconnus vivants' % (d, n, taux))
        print('     a effacer : %5d   %8.1f Mo' % (len(morts), o / 1048576))
    if refus:
        print('-' * 74)
        print('  DOSSIERS REFUSES — et le refus vaut mieux que le geste :')
        for d, pourquoi in refus:
            print('    %s : %s' % (d, pourquoi))
    print('-' * 74)
    print('  TOTAL a effacer : %d fichier(s), %.1f Mo' % (total_n, total_o / 1048576))
    print('=' * 74)

    if not a.appliquer:
        print("  APERCU — rien n'a bouge. Ajoute --appliquer pour effacer.")
        print('  Une vignette effacee se refait a la premiere demande, en')
        print("  lisant l'original sur le NAS : la reversibilite, ici, c'est")
        print('  la regeneration.')
        return 0
    if not total_n:
        print('  Rien a effacer.')
        return 0
    faits, octets, journal = effacer(a_effacer, a.jours)
    print('  %d fichier(s) efface(s), %.1f Mo rendus.' % (faits, octets / 1048576))
    print('  journal : %s' % journal)
    return 0


if __name__ == '__main__':
    sys.exit(main())
