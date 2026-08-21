#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — fabriquer la COPIE de la base sur laquelle tous les bancs travaillent
──────────────────────────────────────────────────────────────────────────────

POURQUOI, ET CE QUE ÇA A COÛTÉ

Tous les bancs du projet exigent `--base copie.db` et REFUSENT `photos.db` :
le serveur est l'écrivain unique, et une mesure qui ouvre la base vivante finit
par la verrouiller ou par lire un état à moitié écrit. La règle est bonne. Mais
personne ne fabriquait la copie : elle traînait à la racine quand Mike l'avait
faite, et le jour où elle n'y est plus, le troisième canal — celui qui existe
pour que la sandbox mesure SANS le clavier de Mike — se rebloque sur ce même
clavier. Ce banc ferme ce trou.

POURQUOI PAS UN `copy` DE FICHIER

La base est en WAL. À un instant donné, une partie de ce qu'elle contient
n'est PAS dans `photos.db` mais dans `photos.db-wal` — ce banc l'affiche, et
le chiffre n'est jamais zéro pendant que le serveur tourne. Copier le seul
fichier `.db` rendrait une base plausible, ouvrable, et PÉRIMÉE d'autant : le
pire des trois états. Copier les trois fichiers à la main donnerait un instant
déchiré, l'écrivain n'ayant attendu personne.

L'API `backup` de SQLite lit à travers le WAL dans une transaction de lecture :
la copie est le fonds tel qu'il était à un instant PRÉCIS, cohérent. La source
est ouverte en `mode=ro` — pas par politesse, par construction : aucune écriture
n'est possible sur ce descripteur, même par erreur de programmation.

CE QU'IL NE FAIT PAS

Aucune écriture sur la source, aucun accès NAS, aucun modèle. Il refuse
d'ÉCRIRE sur un fichier nommé `photos.db` — la seule façon dont ce banc
pourrait nuire est d'écraser la base qu'il est censé préserver, et cette porte
est fermée deux fois (nom réservé, et cible distincte de la source).

CE QU'IL RAPPORTE — la copie est datée, ou elle ne vaut rien

Une copie sans son instant est un piège : on croit mesurer aujourd'hui ce qui
date d'avant-hier. La sortie donne l'instant du snapshot, la taille du WAL
absorbé, et le compte des lignes des tables principales — deux chemins vers le
même chiffre valent mieux qu'un (`eval/METHODE.md`, 15/08).

USAGE
    python mesure_copie_base.py
    python mesure_copie_base.py --vers copie.db --source photos.db
    python mesure_copie_base.py --sans-verification   (saute le quick_check)
"""

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

__all__ = ['SOURCE_DEFAUT', 'CIBLE_DEFAUT', 'SIDECARS', 'uri_lecture_seule',
           'verifier_cible', 'tailles', 'compter', 'copier', 'afficher']

SOURCE_DEFAUT = 'photos.db'
CIBLE_DEFAUT = 'copie.db'

# Ce que SQLite dépose à côté d'une base en WAL. Une cible qui garde les
# siens d'une copie PRÉCÉDENTE ferait lire un mélange de deux instants.
SIDECARS = ('-wal', '-shm')

# Le nom qu'on n'écrase jamais, quoi qu'on demande.
NOM_RESERVE = 'photos.db'


def uri_lecture_seule(chemin):
    """`file:///C:/…/photos.db?mode=ro` — un descripteur qui ne PEUT pas écrire.

    Passer par l'URI plutôt que par le chemin nu n'est pas un détail de style :
    c'est la seule façon d'obtenir de SQLite une connexion réellement en
    lecture seule."""
    return Path(chemin).resolve().as_uri() + '?mode=ro'


def verifier_cible(source, cible):
    """Refus AVANT tout travail. Rend le message, ou `None` si la cible est
    acceptable."""
    s, c = Path(source), Path(cible)
    if c.name.lower() == NOM_RESERVE:
        return ("REFUS : ce banc n'écrit jamais sur un fichier nommé "
                f"{NOM_RESERVE} — c'est la base que la copie sert à protéger.")
    if c.parent.resolve() != Path('.').resolve():
        return ("REFUS : la copie se fabrique à la RACINE du projet "
                f"(demandé : {c}).")
    try:
        meme = s.resolve() == c.resolve()
    except OSError:
        meme = False
    if meme:
        return "REFUS : la source et la cible sont le même fichier."
    if not s.exists():
        return f"Source introuvable : {s}"
    return None


def tailles(source):
    """(base, wal, shm) en octets — 0 pour un sidecar absent. Le WAL est la
    part que `copy` aurait perdue."""
    s = Path(source)
    out = [s.stat().st_size if s.exists() else 0]
    for suf in SIDECARS:
        p = Path(str(s) + suf)
        out.append(p.stat().st_size if p.exists() else 0)
    return tuple(out)


def compter(cx, tables=None):
    """{table: lignes} sur les tables réelles de la base. Sert de PREUVE que
    la copie porte le fonds, pas un fichier vide de la bonne taille."""
    noms = [n for n, in cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    if tables:
        noms = [n for n in noms if n in set(tables)]
    out = {}
    for n in noms:
        try:
            out[n] = cx.execute('SELECT COUNT(*) FROM "%s"' % n).fetchone()[0]
        except sqlite3.Error:
            out[n] = -1
    return out


def _effacer_sidecars(cible):
    """Retire les `-wal`/`-shm` d'une copie PRÉCÉDENTE. Ne touche jamais à
    ceux de la source : la cible a déjà été vérifiée distincte."""
    retires = []
    for suf in SIDECARS:
        p = Path(str(cible) + suf)
        if p.exists():
            p.unlink()
            retires.append(p.name)
    return retires


def copier(source=SOURCE_DEFAUT, cible=CIBLE_DEFAUT, verifier=True):
    """Snapshot cohérent de `source` vers `cible`. Rend le rapport."""
    refus = verifier_cible(source, cible)
    if refus:
        raise SystemExit(refus)

    o_base, o_wal, o_shm = tailles(source)
    rap = {
        'source': str(source), 'cible': str(cible),
        'source_octets': o_base, 'wal_octets': o_wal, 'shm_octets': o_shm,
        'source_modifiee_a': Path(source).stat().st_mtime,
        'sidecars_retires': _effacer_sidecars(cible),
    }

    t0 = time.time()
    src = sqlite3.connect(uri_lecture_seule(source), uri=True, timeout=60)
    try:
        rap['journal'] = src.execute('PRAGMA journal_mode').fetchone()[0]
        rap['pages'] = src.execute('PRAGMA page_count').fetchone()[0]
        rap['page_octets'] = src.execute('PRAGMA page_size').fetchone()[0]
        dst = sqlite3.connect(str(cible))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    rap['snapshot_a'] = time.time()
    rap['duree_s'] = round(rap['snapshot_a'] - t0, 1)
    rap['cible_octets'] = Path(cible).stat().st_size

    cx = sqlite3.connect(str(cible))
    try:
        rap['integrite'] = (cx.execute('PRAGMA quick_check').fetchone()[0]
                            if verifier else '(non vérifiée)')
        rap['lignes'] = compter(cx)
    finally:
        cx.close()
    return rap


def _mo(n):
    return '%.1f Mo' % (n / 1048576.0)


def _quand(t):
    return time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(t))


def afficher(rap):
    L = []
    A = L.append
    A("=" * 74)
    A("  COPIE DE LA BASE — le fonds à un instant précis")
    A("=" * 74)
    A(f"Source   : {rap['source']}  {_mo(rap['source_octets'])}"
      f"   (modifiée {_quand(rap['source_modifiee_a'])})")
    A(f"WAL      : {_mo(rap['wal_octets'])} — cette part n'est PAS dans le "
      "fichier .db")
    A(f"           un copier-coller du seul .db l'aurait perdue.")
    A(f"Journal  : {rap['journal']}   "
      f"{rap['pages']} pages de {rap['page_octets']} octets")
    if rap['sidecars_retires']:
        A(f"Retirés  : {', '.join(rap['sidecars_retires'])} "
          "(sidecars d'une copie précédente)")
    A("")
    A(f"Copie    : {rap['cible']}  {_mo(rap['cible_octets'])}"
      f"   en {rap['duree_s']} s")
    A(f"Instant  : {_quand(rap['snapshot_a'])} — "
      "toute mesure faite sur cette copie parle de CET instant.")
    A(f"Intégrité: {rap['integrite']}")
    A("")
    A("-- CE QUE LA COPIE PORTE -------------------------------------------")
    for n, c in sorted(rap['lignes'].items(), key=lambda x: -x[1]):
        A("  %-24s %10d" % (n, c))
    A("=" * 74)
    A("Les bancs peuvent tourner : mesure_x.py --base %s" % rap['cible'])
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--source', default=SOURCE_DEFAUT)
    ap.add_argument('--vers', default=CIBLE_DEFAUT,
                    help="la COPIE à fabriquer, à la racine du projet")
    ap.add_argument('--sans-verification', action='store_true',
                    dest='sans_verification',
                    help="saute le quick_check (rapide, mais on ne sait plus)")
    a = ap.parse_args(argv)
    os.chdir(Path(__file__).resolve().parent)
    rap = copier(a.source, a.vers, verifier=not a.sans_verification)
    print(afficher(rap))
    return 0 if str(rap['integrite']).lower() in ('ok', '(non vérifiée)') else 1


if __name__ == '__main__':
    sys.exit(main())
