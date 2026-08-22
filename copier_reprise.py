#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copier un GROS fichier depuis un partage qui coupe — en REPRENANT
──────────────────────────────────────────────────────────────────────────────

POURQUOI, ET CE QUE ÇA A COÛTÉ

Le 22/08, la répétition de restauration (chantier 12) a buté quatre fois de
suite sur `ERREUR 59 — erreur réseau inattendue`, toujours après ~72 secondes,
toujours sur les 250 Mo de `photos.db.bak`. Le petit journal (23 Ko) passait
sans broncher. Ni `robocopy /J` (non bufferisé), ni l'arrêt du serveur, ni
quatre tentatives n'y ont rien changé : **la session SMB tombe pendant un
transfert long, et robocopy RECOMMENCE du début à chaque essai.**

Recommencer 250 Mo dans un tuyau qui coupe à 72 s, c'est une boucle qui ne
converge jamais. Ce script fait l'inverse : il copie par blocs et, quand la
source lâche, il **rouvre et repart de l'octet où il en était**. Une coupure
coûte alors un bloc, pas un fichier.

Ce n'est pas un contournement : un PC neuf, le jour où il faudra vraiment
restaurer, sera devant le même réseau. Une procédure de restauration qui
suppose un transfert parfait n'est pas une procédure de restauration.

LA REPRISE NE DOIT JAMAIS COLLER DEUX FICHIERS DIFFÉRENTS

Reprendre un fichier à moitié copié suppose que la source n'a pas bougé
entre-temps — or `backup_db()` REMPLACE `photos.db.bak` toutes les heures
(`os.replace` atomique côté NAS). Coller la fin d'une base sur le début d'une
autre donnerait un fichier de la bonne TAILLE et au contenu incohérent : le
pire résultat possible pour une sauvegarde. D'où le témoin `.reprise` écrit à
côté de la destination : taille et date de la source. S'il ne correspond plus,
la copie **repart de zéro** et le dit.

USAGE
    python copier_reprise.py "\\\\nas\\home\\Uploads\\photos.db.bak" "D:\\essai\\photos.db"
    python copier_reprise.py SOURCE CIBLE --bloc 4 --tentatives 30
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

BLOC_DEFAUT_MO = 4
TENTATIVES_DEFAUT = 30
PAUSE_S = 3.0


def _info_source(src):
    st = os.stat(src)
    return {'taille': st.st_size, 'mtime': int(st.st_mtime)}


def _lire_temoin(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _ecrire_temoin(chemin, info):
    try:
        Path(chemin).write_text(json.dumps(info), encoding='utf-8')
    except OSError:
        pass


def reprise_possible(src_info, temoin, deja):
    """Peut-on reprendre à l'octet `deja` ?

    Non si rien n'a été copié, si le témoin manque, s'il ne décrit pas CETTE
    source, ou si la destination est plus longue que la source (incohérent).
    """
    if deja <= 0 or not temoin:
        return False
    if temoin.get('taille') != src_info['taille']:
        return False
    if temoin.get('mtime') != src_info['mtime']:
        return False
    return deja < src_info['taille']


def copier(src, dst, bloc_mo=BLOC_DEFAUT_MO, tentatives=TENTATIVES_DEFAUT,
           journal=print, pause_s=PAUSE_S):
    """Copie `src` vers `dst` en reprenant après une coupure.

    Renvoie (ok, octets_copiés, nombre_de_reprises)."""
    src, dst = Path(src), Path(dst)
    bloc = max(64 * 1024, int(bloc_mo * 1024 * 1024))
    info = _info_source(src)
    temoin_path = dst.with_suffix(dst.suffix + '.reprise')
    dst.parent.mkdir(parents=True, exist_ok=True)

    deja = dst.stat().st_size if dst.exists() else 0
    temoin = _lire_temoin(temoin_path)
    if deja and not reprise_possible(info, temoin, deja):
        journal("  La copie partielle ne correspond pas a CETTE source "
                "(taille ou date differente) : on repart de zero.")
        deja = 0
    _ecrire_temoin(temoin_path, info)

    total = info['taille']
    reprises = 0
    dernier_dit = 0.0
    t0 = time.time()

    while deja < total:
        essai_debut = deja
        try:
            with open(src, 'rb') as f, open(dst, 'r+b' if deja else 'wb') as g:
                f.seek(deja)
                g.seek(deja)
                while True:
                    morceau = f.read(bloc)
                    if not morceau:
                        break
                    g.write(morceau)
                    deja += len(morceau)
                    maintenant = time.time()
                    if maintenant - dernier_dit >= 5.0:
                        dernier_dit = maintenant
                        pct = 100.0 * deja / total if total else 100.0
                        deb = deja / max(0.001, maintenant - t0) / 1048576
                        journal("  %5.1f%%  %6.1f Mo / %.1f Mo   %4.1f Mo/s"
                                % (pct, deja / 1048576, total / 1048576, deb))
                g.flush()
                os.fsync(g.fileno())
        except OSError as e:
            reprises += 1
            avance = deja - essai_debut
            if reprises > tentatives:
                journal("  ABANDON apres %d reprises : %s" % (reprises - 1, e))
                return False, deja, reprises - 1
            journal("  Coupure a %.1f Mo (%s). Reprise %d/%d dans %.0f s — "
                    "l'essai precedent a avance de %.1f Mo."
                    % (deja / 1048576, getattr(e, 'winerror', None) or e.errno,
                       reprises, tentatives, pause_s, avance / 1048576))
            if avance <= 0 and reprises >= 3:
                journal("  Trois reprises sans avancer : le partage ne rend "
                        "plus rien. Verifie le reseau avant d'insister.")
            time.sleep(pause_s)
            # La source a-t-elle change sous nos pieds ? Si oui, tout est
            # a refaire — mieux vaut le dire que produire un fichier hybride.
            try:
                neuf = _info_source(src)
            except OSError:
                continue
            if neuf != info:
                journal("  La SOURCE a change pendant la copie (sauvegarde "
                        "horaire ?). On repart de zero avec la nouvelle.")
                info = neuf
                total = info['taille']
                deja = 0
                _ecrire_temoin(temoin_path, info)
            continue

    fini = dst.stat().st_size
    if fini != total:
        journal("  TAILLE FINALE INCOHERENTE : %d octets au lieu de %d."
                % (fini, total))
        return False, fini, reprises
    try:
        os.utime(dst, (info['mtime'], info['mtime']))
        temoin_path.unlink()
    except OSError:
        pass
    journal("  Copie complete : %.1f Mo en %.0f s, %d reprise(s)."
            % (total / 1048576, time.time() - t0, reprises))
    return True, total, reprises


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('source')
    ap.add_argument('cible')
    ap.add_argument('--bloc', type=float, default=BLOC_DEFAUT_MO,
                    help="taille des blocs en Mo (defaut 4)")
    ap.add_argument('--tentatives', type=int, default=TENTATIVES_DEFAUT)
    a = ap.parse_args(argv)
    try:
        ok, _, reprises = copier(a.source, a.cible, a.bloc, a.tentatives)
    except OSError as e:
        print("  Copie impossible : %s" % e)
        return 1
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
