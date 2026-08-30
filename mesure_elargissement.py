#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — l'elargissement FR->EN tel que le SERVEUR le fera (ROADMAP 1 nonies)
──────────────────────────────────────────────────────────────────────────────

`mesure_requete_fr_en.py` a mesure l'elargissement IDEAL (la paire fr/en la
plus sure, connue d'avance) : fr 0,583 -> fr+en 0,663. Ce banc mesure ce que
la PRODUCTION fera : le dictionnaire `elargissement_fr_en.Dictionnaire`,
appris sur la copie comme le serveur l'apprend sur l'index, traduit lui-meme
la requete (phrase entiere, sinon mot a mot), et l'on compare, sur les memes
paires et la meme copie :

    fr           la requete seule (aujourd'hui)
    fr+dico      la requete + sa traduction par le dictionnaire (demain)
    fr+ideal     la paire du banc (le plafond)

Et il montre ce que le dictionnaire fait des requetes que Mike tape vraiment
(`--requete`, repetable), pour les observer ensuite en reel.
Lecture seule (copie de la base ; encodeur sur CPU). Sortie ASCII.

    mesure_elargissement.py --base copie.db [--paires 40] [--requete "ours en peluche"]...
"""
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))
import mesure_requete_fr_en as B                       # noqa: E402  charger, paires
import elargissement_fr_en as E                        # noqa: E402

REQUETES = ['ours en peluche', 'sol', 'roche', 'chat sur un canapé', 'coucher de soleil',
            'gâteau d anniversaire', 'plage', 'montagne enneigée', 'vélo', 'chien qui court']


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--paires', type=int, default=40)
    ap.add_argument('--min', type=int, default=40)
    ap.add_argument('--requete', action='append', default=[])
    ap.add_argument('--sans-mesure', action='store_true', help='dictionnaire et traductions seulement')
    ap.add_argument('--via-store', action='store_true', help='apprendre sur SqliteStore.data, comme le serveur')
    a = ap.parse_args(argv)
    log = lambda m: print(asc(m), flush=True)  # noqa: E731
    t0 = time.time()
    cx, tags = B.charger(a.base)
    if a.via_store:
        # EXACTEMENT le chemin du serveur : le TrackedDict d'un SqliteStore.
        from store_sqlite import SqliteStore
        st = SqliteStore(a.base, 'tags')
        dico = E.Dictionnaire(st.data)
        log('via SqliteStore.data : %d entree(s) lues' % len(st.data))
    else:
        entrees = [{'kw_fr': fr, 'kw_en': en} for fr, en in tags.values()]
        dico = E.Dictionnaire(entrees)
    log('index : %d photos taguees ; dictionnaire : %d entrees fr->en apprises sur %d photos a deux langues (%.1f s)'
        % (len(tags), len(dico), dico.n_photos, time.time() - t0))
    log('\nTRADUCTIONS (ce que le serveur encodera en plus de la requete) :')
    for q in (a.requete or REQUETES):
        log('  %-28s -> %s' % (q, dico.traduire(q) or '(rien : requete seule)'))
    if a.sans_mesure:
        return 0
    P = B.paires(tags, a.paires, a.min)
    import numpy as np
    import semantic
    from vectors import VectorStore
    modele, _, _, device = semantic.encodeur(forcer_device='cpu')
    if modele is None:
        log('SigLIP absent : ' + str(semantic._ETAT.get('erreur'))); return 2
    vs = VectorStore(cx)
    cles, M = vs.matrice(semantic.KIND)
    pos = {k: i for i, k in enumerate(cles)}
    K = 200
    somme = defaultdict(float)
    n = memes = 0
    gagne = 0
    log('\nPAIRES (rappel@%d) :' % K)
    for f, e, nf, ne, ce in P:
        verite = {k for k, (fr, en) in tags.items() if (f in fr or e in en) and k in pos}
        if not verite:
            continue
        tr = dico.traduire(f)
        memes += (tr == e)
        formes = {'fr': [f], 'fr+dico': E.formes(dico, f), 'fr+ideal': [f, e]}
        r = {}
        for nom, textes in formes.items():
            V = semantic.encoder_textes(textes)
            q = V.mean(axis=0)
            q = q / (np.linalg.norm(q) or 1.0)
            ordre = np.argsort(-(M @ q))
            top = {cles[i] for i in ordre[:K]}
            r[nom] = len(top & verite) / min(len(verite), K)
            somme[nom] += r[nom]
        n += 1
        gagne += r['fr+dico'] > r['fr']
        log('  %-24s dico: %-20s | fr %.2f  fr+dico %.2f  fr+ideal %.2f' % (
            f[:24], (tr or '-')[:20], r['fr'], r['fr+dico'], r['fr+ideal']))
    log('\nMOYENNES sur %d paires : fr %.3f   fr+dico %.3f   fr+ideal %.3f' % (
        n, somme['fr'] / n, somme['fr+dico'] / n, somme['fr+ideal'] / n))
    log('  le dictionnaire retrouve la paire ideale sur %d/%d ; fr+dico bat fr sur %d/%d' % (memes, n, gagne, n))
    log('(lecture seule, %.0f s)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
