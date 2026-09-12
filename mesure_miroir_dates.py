#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Les deux lecteurs de date dans un NOM DE FICHIER sont-ils vraiment miroirs ?

LA QUESTION, ET POURQUOI ELLE SE POSE MAINTENANT

Apres les § 3.13, 3.17, 3.18 et 3.19 de `PERFORMANCE.md`, le plus gros theme
restant de la page `/files` est la DATE : 118 ms sur ~750, partages entre deux
chemins qui lisent les MEMES deux sources brutes.

  * `meme_jour.epoch_precis(cle, entree, server._fname_time, ...)` rend le
    MINIMUM du `taken` et de la date du NOM ;
  * `faits_vue.date_et_source(cle, entree)` rend le `taken` EN PRIORITE, et
    ne descend a la date du NOM (`faits_vue.epoch_du_nom`, qui passe par
    `renommage_facts.fname_datetime`) que si le premier manque.

Regles differentes : passer l'une a l'autre serait un defaut muet. Ce qui est
partageable, ce sont les deux LECTURES. Mais elles passent par deux portes que
les docstrings declarent miroirs -- et **<< miroir declare >> n'est pas
<< miroir mesure >>**. Ce banc mesure, avant que quiconque fusionne quoi que
ce soit.

CE QUE LA MESURE A DONNE (12/09)

0 desaccord sur les 44 966 fichiers du fonds, mais une divergence REELLE sur
les cas limites : une heure IMPOSSIBLE dans le nom (<< 250000 >>). Conclusion
appliquee le jour meme : `server._fname_time` DELEGUE a
`faits_vue.epoch_du_nom` -- une seule regle, et c'est la STRICTE qui survit
(rejeter l'heure et retomber a midi, plutot que laisser `mktime` normaliser en
silence vers un autre JOUR). Ce banc garde sa raison d'etre : il est la preuve
que la fusion n'a deplace aucune photo, et il retombera en desaccord le jour
ou quelqu'un rouvrira un second lecteur.

CE QU'IL FAIT

1. Les CONTRE-EXEMPLES construits : les cas limites ou les deux portes
   POUVAIENT diverger. Ils tournent sans le NAS, et ils sont la
   raison d'etre du banc -- un corpus qui ne contient aucun cas limite ne
   prouve rien.
2. Le CORPUS reel : chaque nom de fichier sous une racine, compare entre les
   deux portes. Nombre d'accords, de desaccords, et pour chaque desaccord le
   nom, les deux epochs, et si le JOUR (MM-JJ) differe -- c'est lui qui decide
   du bouton << Meme jour >>.

`server._fname_time` est EXTRAITE du source par l'arbre syntaxique, jamais
importee : le serveur tire torch et insightface, un banc n'a pas a payer ca.
Aucune ecriture, aucun acces reseau autre que la lecture des NOMS.

  mesure_miroir_dates.py                         (contre-exemples seuls)
  mesure_miroir_dates.py --racine b64:...        (+ le corpus reel)
  mesure_miroir_dates.py --racine ... --limite 20000
"""
import argparse
import ast
import base64
import io
import os
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
SERVER = ICI / 'server.py'

import faits_vue                                            # noqa: E402

MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff',
             '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp'}


def dejeton(v):
    """`b64:...` -> la valeur. Le canal des bancs n'accepte pas les espaces."""
    if isinstance(v, str) and v.startswith('b64:'):
        return base64.urlsafe_b64decode(v[4:] + '=' * (-len(v[4:]) % 4)).decode('utf-8')
    return v


def charger(noms):
    """Des fonctions de `server.py`, extraites du SOURCE par l'arbre
    syntaxique. Un banc qui recopierait une fonction mesurerait sa copie.

    `faits_vue` et `renommage_facts` sont dans l'espace parce que les
    fonctions extraites leur DELEGUENT (12/09). Le jour ou l'une d'elles
    retrouvera un corps a elle, elle cessera d'en avoir besoin -- et ce banc
    redeviendra une VRAIE comparaison de deux regles. C'est exactement ce
    qu'on veut qu'il soit."""
    import re                                               # noqa: F401
    import renommage_facts                                  # noqa: F401
    espace = {'re': re, 'time': time, 'faits_vue': faits_vue,
              'renommage_facts': renommage_facts,
              'ANNEE_CHEMIN_MIN': 1900, 'ANNEE_CHEMIN_MAX': 2100}
    with io.open(SERVER, encoding='utf-8') as f:
        arbre = ast.parse(f.read())
    trouves = {}
    for n in arbre.body:
        if isinstance(n, ast.FunctionDef) and n.name in noms:
            exec(compile(ast.Module(body=[n], type_ignores=[]),
                         str(SERVER), 'exec'), espace)
            trouves[n.name] = espace[n.name]
    manquants = set(noms) - set(trouves)
    if manquants:
        raise AssertionError('introuvables dans server.py : %s'
                             % sorted(manquants))
    return trouves


def jour_de(epoch):
    """« MM-JJ » local, ou None. C'est ce que la page compare."""
    if epoch is None:
        return None
    try:
        t = time.localtime(float(epoch))
    except (ValueError, OverflowError, OSError):
        return None
    return '%02d-%02d' % (t.tm_mon, t.tm_mday)


def comparer(nom, fname_time):
    """(epoch porte A, epoch porte B) pour UN nom de fichier.

    Porte A : `server._fname_time(nom)`.
    Porte B : `faits_vue.epoch_du_nom(cle)` -- qui coupe elle-meme la cle sur
    son dernier separateur, donc on lui passe le nom nu."""
    try:
        a = fname_time(nom)
    except Exception:                                        # noqa: BLE001
        a = 'LEVE'
    try:
        b = faits_vue.epoch_du_nom(nom)
    except Exception:                                        # noqa: BLE001
        b = 'LEVE'
    return a, b


# ───────────────────────── les contre-exemples ─────────────────────────
# Chacun vient d'une LECTURE du source, pas d'une intuition. La colonne
# « attendu » dit ce que la lecture predit ; le banc verifie que la prediction
# tient. Une prediction qui tombe est une lecture fausse, et c'est une
# information au moins aussi utile qu'un desaccord de corpus.
CONTRE_EXEMPLES = [
    ('20180101_120000.jpg', 'accord',
     'le cas ordinaire : date et heure valides des deux cotes'),
    ('20180101.jpg', 'accord',
     'sans heure : les deux retombent sur 12h00 (midi, pas minuit)'),
    ('IMG_20181227_093012.jpg', 'accord',
     'le prefixe ne gene ni l une ni l autre'),
    ('rien_du_tout.jpg', 'accord',
     'aucune date : None des deux cotes'),
    ('19890704_101010.jpg', 'accord',
     'sous le plancher 1990 : refuse des deux cotes (l annee, pas l heure)'),
    ('20180101_250000.jpg', 'accord',
     "HEURE INVALIDE (25h). AVANT le 12/09 : desaccord — `_fname_time` la "
     "passait a `mktime`, qui NORMALISE et faisait basculer au JOUR SUIVANT, "
     "pendant que `fname_datetime` la REJETAIT (donc midi). DEPUIS : "
     "`_fname_time` DELEGUE, et c'est la regle stricte qui survit."),
    ('20180101_126100.jpg', 'accord',
     'MINUTES INVALIDES (61) : meme mecanique, meme verdict.'),
    ('20180101_120061.jpg', 'accord',
     'SECONDES INVALIDES (61) : idem.'),
]

# Ce que la delegation a supprime : l'ecriture d'AVANT, gardee ici comme
# ORACLE HISTORIQUE. Le banc ne l'appelle plus en prod -- il montre seulement,
# sur les trois cas limites, ce que l'ancienne regle repondait. Sans cette
# trace, << 0 desaccord >> se lirait un jour comme << il n'y a jamais eu de
# difference >>, et le choix disparaitrait avec la preuve.
ANCIENNE_REGLE_HEURE = {
    '20180101_250000.jpg': 'jour 01-02 (et non 01-01) : +13 heures',
    '20180101_126100.jpg': '13h01 (et non midi)',
    '20180101_120061.jpg': "12h00'61 (et non midi pile)",
}


def verifier_contre_exemples(fname_time):
    lignes, faux = [], 0
    for nom, attendu, pourquoi in CONTRE_EXEMPLES:
        a, b = comparer(nom, fname_time)
        obtenu = 'accord' if a == b else 'desaccord'
        ok = obtenu == attendu
        faux += 0 if ok else 1
        lignes.append({'nom': nom, 'attendu': attendu, 'obtenu': obtenu,
                       'ok': ok, 'a': a, 'b': b,
                       'jour_a': jour_de(a if a != 'LEVE' else None),
                       'jour_b': jour_de(b if b != 'LEVE' else None),
                       'pourquoi': pourquoi})
    return lignes, faux


# ─────────────────────────── le corpus reel ───────────────────────────

def parcourir(racine, limite):
    """Les CHEMINS des fichiers media sous `racine`, sans suivre les
    corbeilles. Le chemin entier, pas le nom : le second couple de lecteurs
    compare les annees du DOSSIER."""
    n = 0
    for dossier, sous, fichiers in os.walk(racine):
        sous[:] = [d for d in sous if not d.startswith('.')]
        for f in fichiers:
            if Path(f).suffix.lower() in MEDIA_EXT:
                yield os.path.join(dossier, f)
                n += 1
                if limite and n >= limite:
                    return


def mesurer_corpus(racine, limite, fname_time, path_years_a=None):
    """Les DEUX couples de lecteurs, sur le meme balayage.

    Couple 1, la date du NOM : `server._fname_time` contre
    `faits_vue.epoch_du_nom`.
    Couple 2, les ANNEES du DOSSIER : `server._path_years` contre
    `renommage_facts.path_years`. Meme question, meme forme de reponse :
    deux ecritures declarees miroirs que personne n'avait comparees."""
    import renommage_facts
    accords = desaccords = sans_date = 0
    jours_differents = 0
    an_accords = an_desaccords = 0
    an_exemples = []
    exemples = []
    vus = 0
    for chemin in parcourir(racine, limite):
        vus += 1
        if path_years_a is not None:
            ya, yb = path_years_a(chemin), renommage_facts.path_years(chemin)
            if ya == yb:
                an_accords += 1
            else:
                an_desaccords += 1
                if len(an_exemples) < 20:
                    an_exemples.append({'cle': chemin, 'a': sorted(ya),
                                        'b': sorted(yb)})
        nom = os.path.basename(chemin)
        a, b = comparer(nom, fname_time)
        if a is None and b is None:
            sans_date += 1
            accords += 1
            continue
        if a == b:
            accords += 1
            continue
        desaccords += 1
        ja, jb = jour_de(a if a != 'LEVE' else None), jour_de(b if b != 'LEVE' else None)
        if ja != jb:
            jours_differents += 1
        if len(exemples) < 20:
            exemples.append({'nom': nom, 'a': a, 'b': b,
                             'jour_a': ja, 'jour_b': jb})
    return {'vus': vus, 'accords': accords, 'desaccords': desaccords,
            'sans_date': sans_date, 'jours_differents': jours_differents,
            'exemples': exemples, 'an_accords': an_accords,
            'an_desaccords': an_desaccords, 'an_exemples': an_exemples}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--racine', default=None,
                    help='racine a balayer (b64: accepte). Omise : '
                         'contre-exemples seuls.')
    ap.add_argument('--limite', type=int, default=0,
                    help='nombre max de fichiers (0 = tous)')
    a = ap.parse_args(argv)

    fns = charger(('_fname_time', '_path_years'))
    fname_time, path_years_a = fns['_fname_time'], fns['_path_years']

    print('=' * 74)
    print('LES CONTRE-EXEMPLES  (ce que la LECTURE du source predit)')
    print('=' * 74)
    lignes, faux = verifier_contre_exemples(fname_time)
    for l in lignes:
        marque = 'ok  ' if l['ok'] else 'FAUX'
        print('%s  %-26s attendu=%-9s obtenu=%s' %
              (marque, l['nom'], l['attendu'], l['obtenu']))
        if l['obtenu'] == 'desaccord':
            print('        A=%s (jour %s)   B=%s (jour %s)' %
                  (l['a'], l['jour_a'], l['b'], l['jour_b']))
        print('        %s' % l['pourquoi'])
    if faux:
        print('\n*** %d prediction(s) FAUSSE(S) : la lecture du source est a '
              'refaire avant tout chantier. ***' % faux)
    else:
        print('\nLes 8 predictions tiennent : les deux portes rendent '
              'desormais la MEME chose,')
        print('cas limites compris — `server._fname_time` delegue a '
              '`faits_vue.epoch_du_nom`')
        print('depuis le 12/09. Ce que l ANCIENNE regle d heure repondait, '
              'pour memoire :')
        for nom, dit in sorted(ANCIENNE_REGLE_HEURE.items()):
            print('    %-24s %s' % (nom, dit))
        print('  (0 desaccord sur les 44 966 fichiers du fonds : le choix '
              'n a deplace aucune photo)')

    if not a.racine:
        print('\n(pas de --racine : le corpus reel n a pas ete balaye)')
        return 0 if not faux else 1

    racine = dejeton(a.racine)
    print('\n' + '=' * 74)
    print('LE CORPUS REEL  —  %s' % racine)
    print('=' * 74)
    t0 = time.time()
    r = mesurer_corpus(racine, a.limite, fname_time, path_years_a)
    print('fichiers media vus      : %d  (%.1f s)' % (r['vus'], time.time() - t0))
    print('')
    print('COUPLE 1 — la date du NOM')
    print('  `server._fname_time` contre `faits_vue.epoch_du_nom`')
    print('  accords               : %d' % r['accords'])
    print('    dont aucune date    : %d' % r['sans_date'])
    print('  DESACCORDS            : %d' % r['desaccords'])
    print('    dont JOUR different : %d' % r['jours_differents'])
    for e in r['exemples']:
        print('    %-44s A=%s (%s)  B=%s (%s)' %
              (e['nom'][:44], e['a'], e['jour_a'], e['b'], e['jour_b']))
    if not r['desaccords']:
        print('\n  -> aucun desaccord sur la date du NOM.')
    else:
        print('\n  -> des desaccords REELS sur la date du NOM : toute fusion '
              'change la reponse')
        print('     pour ces fichiers-la. Trancher AVANT de toucher au code.')

    print('')
    print('COUPLE 2 — les ANNEES du DOSSIER')
    print('  `server._path_years` contre `renommage_facts.path_years`')
    print('  accords               : %d' % r['an_accords'])
    print('  DESACCORDS            : %d' % r['an_desaccords'])
    for e in r['an_exemples']:
        print('    %-60s A=%s  B=%s' % (e['cle'][-60:], e['a'], e['b']))
    if not r['an_desaccords']:
        print('  -> aucun desaccord sur les annees du dossier.')
    else:
        print('  -> des desaccords REELS : ne rien fusionner avant de '
              'trancher.')
    return 0 if not faux else 1


if __name__ == '__main__':
    sys.exit(main())
