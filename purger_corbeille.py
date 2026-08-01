#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3b — PURGE de .corbeille-rangement/ apres le delai de retention.

C'est le SEUL endroit du chantier ou une suppression DEFINITIVE a lieu. Tout le
reste (dedoublonnage, application) est reversible ; la purge est le maillon final
qui recupere reellement l'espace, une fois passe le delai ou l'utilisateur aurait
pu annuler. Elle est donc la plus prudente :

  - **Delai** : ne supprime qu'un groupe dont le `manifeste.json` date de plus de
    N jours (defaut 30). En-deca, on garde (fenetre d'annulation encore ouverte).
  - **Filet anti-perte** : avant de supprimer une copie quarantinee, on verifie
    que sa CANONIQUE (la copie gardee, notee dans le manifeste) existe TOUJOURS.
    Si la canonique a disparu depuis, on NE purge PAS — sinon on perdrait le
    contenu. Option `--verifier-canon` : re-hash la canonique (sha256 du
    manifeste) pour une certitude au bit pres, pas seulement l'existence.
  - **Dry-run par defaut** : rien n'est supprime sans `--appliquer`.
  - **Idempotente** : rejouable a l'infini (planifiable la nuit).

Un groupe sans `manifeste.json`, ou dont la canonique manque, est SAUTE (jamais
de suppression a l'aveugle).

Usage :
    python purger_corbeille.py                     # dry-run, 30 jours
    python purger_corbeille.py --appliquer
    python purger_corbeille.py --jours 30 --appliquer
    python purger_corbeille.py --verifier-canon --appliquer   # re-hash canonique
Options : --corbeille <chemin> (sinon lu depuis docs/plan_rangement.json),
          --plan <chemin>.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent


def sha256(path, buf=1 << 16, tries=3, pause=0.4):
    """sha256 resilient SMB (blocs 64 Ko + retry) — comme appliquer_plan."""
    last = None
    for attempt in range(tries):
        h = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                while True:
                    b = f.read(buf)
                    if not b:
                        break
                    h.update(b)
            return h.hexdigest()
        except OSError as e:
            last = e
            if attempt + 1 < tries:
                time.sleep(pause * (attempt + 1))
    raise last


def age_jours(date_str):
    """Age en jours d'une date « %Y-%m-%d %H:%M:%S ». None si illisible."""
    try:
        t = time.mktime(time.strptime(date_str, '%Y-%m-%d %H:%M:%S'))
    except (ValueError, TypeError):
        return None
    return (time.time() - t) / 86400.0


def corbeille_par_defaut(plan_path):
    try:
        plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
        return plan.get('corbeille')
    except Exception:
        return None


def purge(corbeille, jours, appliquer, verifier_canon):
    corbeille = Path(corbeille)
    if not corbeille.exists():
        print(f"Corbeille absente : {corbeille} (rien a purger).")
        return 0

    stats = {'purges': 0, 'octets': 0, 'trop_recents': 0, 'canon_manquante': 0,
             'sans_manifeste': 0, 'groupes': 0}
    for groupe in sorted(p for p in corbeille.iterdir() if p.is_dir()):
        stats['groupes'] += 1
        mani_p = groupe / 'manifeste.json'
        if not mani_p.exists():
            print(f"  [garde] {groupe.name} : pas de manifeste — jamais a l'aveugle")
            stats['sans_manifeste'] += 1
            continue
        try:
            mani = json.loads(mani_p.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"  [garde] {groupe.name} : manifeste illisible ({e})")
            stats['sans_manifeste'] += 1
            continue

        age = age_jours(mani.get('date_application', ''))
        if age is None:
            print(f"  [garde] {groupe.name} : date d'application illisible")
            stats['sans_manifeste'] += 1
            continue
        if age < jours:
            stats['trop_recents'] += 1
            continue

        canon = mani.get('canonique')
        p_canon = Path(canon) if canon else None
        if not (p_canon and p_canon.exists()):
            print(f"  [GARDE] {groupe.name} : CANONIQUE ABSENTE ({canon}) — "
                  "purge refusee pour ne pas perdre le contenu")
            stats['canon_manquante'] += 1
            continue
        if verifier_canon:
            try:
                if sha256(p_canon) != mani.get('sha256'):
                    print(f"  [GARDE] {groupe.name} : sha256 canonique != manifeste "
                          "— purge refusee")
                    stats['canon_manquante'] += 1
                    continue
            except OSError as e:
                print(f"  [GARDE] {groupe.name} : canonique illisible ({e}) — purge refusee")
                stats['canon_manquante'] += 1
                continue

        fichiers = [f for f in groupe.iterdir() if f.name != 'manifeste.json']
        for f in fichiers:
            taille = f.stat().st_size if f.exists() else 0
            if appliquer:
                try:
                    f.unlink()
                except OSError as e:
                    print(f"    ! suppression impossible {f.name} : {e}")
                    continue
            print(f"  [{'purge' if appliquer else 'dry'}] {groupe.name}/{f.name} "
                  f"({taille/1e6:.1f} Mo, {age:.0f} j)")
            stats['purges'] += 1
            stats['octets'] += taille
        if appliquer:
            try:
                mani_p.unlink()
                groupe.rmdir()
            except OSError:
                pass

    print(f"\n{'PURGE' if appliquer else 'DRY-RUN'} — {stats['purges']} fichier(s), "
          f"{stats['octets']/1024**3:.2f} Go | trop recents (<{jours} j) : "
          f"{stats['trop_recents']} | canonique manquante : {stats['canon_manquante']} "
          f"| sans manifeste : {stats['sans_manifeste']}")
    if not appliquer:
        print("(dry-run — rien supprime. Ajoute --appliquer pour purger.)")
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true')
    ap.add_argument('--jours', type=int, default=30)
    ap.add_argument('--verifier-canon', action='store_true',
                    help='re-hash la canonique (certitude au bit pres)')
    ap.add_argument('--corbeille', default=None)
    ap.add_argument('--plan', default=str(RACINE / 'docs' / 'plan_rangement.json'))
    args = ap.parse_args()

    corbeille = args.corbeille or corbeille_par_defaut(args.plan)
    if not corbeille:
        print("Corbeille inconnue : passe --corbeille <chemin> "
              "(ou garde docs/plan_rangement.json qui la contient).")
        return 2
    purge(corbeille, args.jours, args.appliquer, args.verifier_canon)
    return 0


if __name__ == '__main__':
    sys.exit(main())
