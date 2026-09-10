#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ce que coute `_reconcilier()` — point d'audit O14, mesure du 10/09/2026.

Le soupcon : `SqliteStore.save()` appelle `_reconcilier()`, qui RE-EMPREINTE
l'index ENTIER — `dict(e)`, `json.dumps`, `blake2b` sur chaque entree — sous
le verrou du magasin, pour trouver ce qui a change. Avec ~40 600 entrees et
soixante-quatre appels a `save()` dans `server.py`, dont certains sur le chemin
chaud du tagging, la question n'est pas « est-ce elegant » mais « combien de
millisecondes, et combien de fois ».

**Ce banc ne juge pas, il chiffre.** Il compare les deux chemins qui existent
deja cote a cote dans le magasin :

  `_flush_rapide()`  -- n'ecrit que ce que `TrackedEntry` a SIGNALE. Cout
                        proportionnel au nombre de MUTATIONS.
  `_reconcilier()`   -- relit tout et compare les empreintes. Cout
                        proportionnel a la TAILLE DE L'INDEX, meme quand rien
                        n'a bouge.

Le second existe pour une bonne raison : une mutation PROFONDE (`e['faits']
['lieu'] = ...`) ne passe pas par `__setitem__` de premier niveau et n'est donc
jamais signalee. La question n'est donc pas de le supprimer, mais de savoir ce
qu'il coute quand il ne trouve RIEN — le cas de loin le plus frequent.

**Sur une COPIE de la base, jamais sur `photos.db`** : le serveur en est
l'ecrivain unique (CLAUDE.md, regle 4). Le banc REFUSE de travailler sur la
base vivante.

  python mesure_reconciliation.py
  python mesure_reconciliation.py --base copie.db --table tags
"""

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))


def _chrono(fn, tours):
    """(secondes par tour, retour du dernier tour). Le plus court, pas la
    moyenne : la moyenne mesure aussi ce que Windows faisait a cote."""
    meilleur, dernier = None, None
    for _ in range(tours):
        t = time.perf_counter()
        dernier = fn()
        d = time.perf_counter() - t
        meilleur = d if meilleur is None else min(meilleur, d)
    return meilleur, dernier


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', default='copie.db',
                    help='la COPIE a mesurer (jamais photos.db)')
    ap.add_argument('--table', default='tags')
    ap.add_argument('--tours', type=int, default=5)
    a = ap.parse_args(argv)

    if Path(a.base).name.lower() == 'photos.db':
        print("  REFUS : photos.db est la base VIVANTE, le serveur en est")
        print("  l'ecrivain unique. Mesurer dessus, c'est ecrire dedans.")
        print("  Donne une copie : --base copie.db")
        return 2

    src = RACINE / a.base
    if not src.exists():
        print("  copie introuvable : %s" % src)
        print("  (le depot en porte une : copie.db)")
        return 2

    # Une copie DE LA COPIE, **HORS DU DEPOT** : ce banc ecrit, et `copie.db`
    # sert a d'autres.
    #
    # Le premier jet la posait a la racine du projet, sous
    # `_mesure_reconciliation.db`. L'agent git a refuse la livraison :
    # « extension .db interdite dans le depot ». **Il avait raison, et pas
    # seulement sur la regle** : un banc qui laisse 300 Mo de binaire dans
    # l'arbre de travail a chaque passage n'est pas un banc propre, et le
    # `.gitignore` n'aurait fait que cacher le desordre. Le fichier de travail
    # vit maintenant dans le dossier temporaire du systeme et disparait avec
    # lui.
    tmp = Path(tempfile.mkdtemp(prefix='mesure_o14_'))
    travail = tmp / 'travail.db'
    for suff in ('', '-wal', '-shm'):
        q = Path(str(src) + suff)
        if q.exists():
            shutil.copy2(q, str(travail) + suff)

    from store_sqlite import SqliteStore
    st = SqliteStore(travail, a.table)
    n = len(st.data)

    print('=' * 74)
    print('  O14 — CE QUE COUTE `_reconcilier()`')
    print('=' * 74)
    print('  base mesuree   : %s (copie de %s)' % (travail.name, src.name))
    print('  table          : %s' % a.table)
    print('  entrees        : %d' % n)
    print('  tours          : %d (on garde le MEILLEUR, pas la moyenne)' % a.tours)
    print('-' * 74)

    # 1. Le cas de loin le plus frequent : RIEN n'a change.
    st._reconcilier()                       # amorce : empreintes a jour
    t_vide, faits_vide = _chrono(st._reconcilier, a.tours)
    print('  reconciliation A VIDE (rien n a change)')
    print('     %8.1f ms   %d ecriture(s)' % (t_vide * 1000, faits_vide))
    print('     soit %.1f us par entree, payes pour ne rien trouver'
          % (t_vide * 1e6 / max(n, 1)))

    # 2. Le meme travail utile, par le chemin qui SIGNALE.
    cles = list(st.data.keys())[:1]
    if cles:
        k = cles[0]
        def une_mutation_puis_flush():
            e = st.data[k]
            e['_mesure_o14'] = time.time()   # passe par TrackedEntry
            return st._flush_rapide()
        t_flush, faits_flush = _chrono(une_mutation_puis_flush, a.tours)
        print('-' * 74)
        print('  flush RAPIDE apres UNE mutation signalee')
        print('     %8.1f ms   %d ecriture(s)' % (t_flush * 1000, faits_flush))
        if t_flush > 0:
            print('     la reconciliation a vide coute %.0f x ce flush'
                  % (t_vide / t_flush))

    # 3. Ce que ca fait a l'echelle de la journee.
    print('-' * 74)
    print('  A L ECHELLE : `save()` est appele depuis ~64 endroits de')
    print('  server.py. Sur une campagne de retag a ~190 photos/heure :')
    for par_photo in (1, 2, 3):
        par_h = 190 * par_photo
        print('     %d save() par photo -> %5d/h -> %6.1f s/h sous verrou'
              % (par_photo, par_h, par_h * t_vide))
    print('=' * 74)
    print('  Ce banc n a touche ni photos.db ni copie.db, et il n a rien')
    print('  laisse dans le depot.')
    try:
        st.cx.close()
    except Exception:                                             # noqa: BLE001
        pass
    shutil.rmtree(tmp, ignore_errors=True)
    print('  Copie de travail effacee : %s' % tmp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
