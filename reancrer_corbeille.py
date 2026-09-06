#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rendre a la corbeille de rangement les canoniques qu'elle a perdues de vue.

LE PROBLEME. Chaque groupe de `.corbeille-rangement/` note dans son
`manifeste.json` le chemin ABSOLU de la copie GARDEE -- la canonique. Depuis, le
fonds a ete range (bat 26, bat 39, rapatriements Google) : la photo gardee a
change de place, le chemin note ne repond plus. `purger_corbeille.py` refuse
alors de purger le groupe, et il a RAISON : sans canonique vivante, supprimer la
copie quarantinee detruirait la derniere trace de la photo.

Mesure du 06/09 (`verifier_corbeille_canoniques.py`) : 389 groupes, 15 seulement
avec leur canonique en place, 27,6 Go bloques. Sur 40 canoniques retrouvees PAR
LE NOM et verifiees au sha256, 37 etaient la bonne photo et **3 ne l'etaient
pas** -- un autre fichier occupe desormais ce nom. Le nom n'est donc pas une
preuve, a 7 % pres, et 7 % de 357 groupes ferait une vingtaine de photos
detruites sans copie.

CE QUE FAIT CET OUTIL. Il ne supprime rien, jamais. Pour chaque groupe dont la
canonique manque, il cherche le meme NOM dans l'index puis compare le SHA256 au
manifeste. Empreinte identique -> il reecrit le champ `canonique` du manifeste
vers le chemin d'aujourd'hui, et le groupe redevient purgeable par le bat 24.
Empreinte differente, ou aucun candidat -> il ne touche a rien et le dit : ces
groupes-la contiennent peut-etre la DERNIERE copie d'une photo, ce sont eux
qu'il faut regarder a la main.

REVERSIBLE. Chaque manifeste modifie garde son ancien chemin dans
`canonique_avant` et la date dans `reancre_le` ; un journal d'annulation est
ecrit dans docs/, et `--annuler <journal>` remet tout comme avant.

Usage :
    python reancrer_corbeille.py                    # apercu, rien n'est ecrit
    python reancrer_corbeille.py --appliquer
    python reancrer_corbeille.py --limite 50 --appliquer
    python reancrer_corbeille.py --annuler docs/undo_reancrage_....json
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
DOSSIER_JOURNAL = RACINE / 'docs'
DERNIER_JOURNAL = None


def sha256(path, buf=1 << 16, essais=3, pause=0.4):
    """sha256 resilient SMB (blocs 64 Ko + reprise) -- comme appliquer_plan."""
    dernier = None
    for n in range(essais):
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
            dernier = e
            if n + 1 < essais:
                time.sleep(pause * (n + 1))
    raise dernier


def lire_json(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception:
        return defaut


def index_par_nom(db_path, table='tags'):
    """{nom de fichier minuscule: [chemins]} depuis photos.db, en lecture seule.

    L'index sait ou vivent les photos AUJOURD'HUI : c'est lui qu'on interroge,
    pas le NAS. Un index vide ferait conclure « tout a disparu » -- une reponse
    fausse qui a l'air d'une reponse : l'appelant refuse ce cas.
    """
    par_nom = defaultdict(list)
    cx = sqlite3.connect('file:' + str(db_path) + '?mode=ro', uri=True,
                         timeout=30.0)
    try:
        cx.execute('PRAGMA busy_timeout=30000')
        for (cle,) in cx.execute(f'SELECT k FROM "{table}"'):
            par_nom[Path(cle).name.lower()].append(cle)
    finally:
        cx.close()
    return par_nom


def ecrire_atomique(chemin, donnees):
    """tmp + os.replace : un manifeste a moitie ecrit vaut un manifeste perdu."""
    chemin = Path(chemin)
    tmp = chemin.with_suffix(chemin.suffix + '.tmp')
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    tmp.replace(chemin)


def nouveau_journal():
    """Un nom libre, meme si deux gestes tombent dans la meme seconde.

    Sans le suffixe, le second journal ecrasait le premier et emportait avec
    lui la possibilite d'annuler le premier geste -- en silence.
    """
    global DERNIER_JOURNAL
    DOSSIER_JOURNAL.mkdir(parents=True, exist_ok=True)
    base = time.strftime('undo_reancrage_%Y%m%d_%H%M%S')
    p = DOSSIER_JOURNAL / (base + '.json')
    n = 1
    while p.exists():
        p = DOSSIER_JOURNAL / f'{base}_{n}.json'
        n += 1
    DERNIER_JOURNAL = p
    return p


def annuler(journal):
    donnees = lire_json(journal)
    if not donnees or 'gestes' not in donnees:
        print(f'Journal illisible : {journal}')
        return 1
    remis, rates = 0, 0
    for g in donnees['gestes']:
        mani_p = Path(g['manifeste'])
        mani = lire_json(mani_p)
        if not mani:
            print(f"  ! manifeste illisible : {mani_p}")
            rates += 1
            continue
        mani['canonique'] = g['avant']
        mani.pop('canonique_avant', None)
        mani.pop('reancre_le', None)
        try:
            ecrire_atomique(mani_p, mani)
            remis += 1
        except OSError as e:
            print(f'  ! {mani_p} : {e}')
            rates += 1
    print(f'{remis} manifeste(s) remis dans leur etat d origine, {rates} echec(s).')
    return 1 if rates else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true',
                    help='ecrire les manifestes (sinon : apercu seul)')
    ap.add_argument('--limite', type=int, default=0,
                    help='ne traiter que les N premiers groupes (0 = tous)')
    ap.add_argument('--annuler', metavar='JOURNAL',
                    help='remettre les manifestes du journal dans leur etat')
    a = ap.parse_args(argv)

    if a.annuler:
        return annuler(a.annuler)

    plan = lire_json(RACINE / 'docs' / 'plan_rangement.json', {})
    corbeille = plan.get('corbeille')
    if not corbeille:
        print('Corbeille inconnue (docs/plan_rangement.json).')
        return 1
    corbeille = Path(corbeille)
    if not corbeille.exists():
        print(f'Corbeille absente : {corbeille}')
        return 1

    db = RACINE / 'photos.db'
    if not db.exists():
        print(f'Index introuvable : {db} — sans lui on ne conclut rien.')
        return 1
    t0 = time.time()
    par_nom = index_par_nom(db)
    print(f'index lu : {len(par_nom)} nom(s) distinct(s) en {time.time()-t0:.0f} s')
    if not par_nom:
        print('Index VIDE : je refuse de conclure a partir de rien.')
        return 1

    stats = {'groupes': 0, 'en_place': 0, 'reancres': 0,
             'autre_contenu': 0, 'introuvable': 0, 'illisible': 0}
    gestes, a_regarder = [], []
    groupes = sorted(p for p in corbeille.iterdir() if p.is_dir())
    if a.limite:
        groupes = groupes[:a.limite]
    # DIRE OU ON EN EST. Ce passage relit chaque canonique sur le NAS : ~40
    # minutes pendant lesquelles la version muette n'affichait rien du tout.
    # Mike a du demander « est-ce ok ? » -- et il avait raison de demander :
    # rien a l'ecran ne distinguait le travail en cours d'un blocage. La regle
    # du projet vaut aussi pour les outils a la main : un travail qui ne rend
    # pas de comptes finit par ne plus travailler sans que personne le voie.
    # Mesurer l'avancement de l'exterieur coute cher (une sonde a mis 479 s a
    # relire les 389 manifestes sur un NAS occupe) : c'est au travail lui-meme
    # de parler.
    t_debut = time.time()
    n_vus = 0
    total = len(groupes)

    for groupe in groupes:
        n_vus += 1
        if n_vus % 25 == 0:
            ecoule = time.time() - t_debut
            reste = (ecoule / n_vus) * (total - n_vus)
            print(f'  … {n_vus}/{total} groupes — {stats["reancres"]} reancre(s)'
                  f' — encore ~{reste / 60:.0f} min', flush=True)
        mani_p = groupe / 'manifeste.json'
        mani = lire_json(mani_p)
        if not mani:
            continue
        stats['groupes'] += 1
        canon = mani.get('canonique') or ''
        if canon and Path(canon).exists():
            stats['en_place'] += 1
            continue
        attendu = mani.get('sha256')
        if not attendu:
            stats['illisible'] += 1
            a_regarder.append((groupe.name, 'manifeste sans sha256', canon))
            continue

        trouve = None
        for c in par_nom.get(Path(canon).name.lower(), []):
            try:
                if Path(c).exists() and sha256(c) == attendu:
                    trouve = c
                    break
            except OSError:
                continue

        if trouve is None:
            candidats = par_nom.get(Path(canon).name.lower(), [])
            if candidats:
                stats['autre_contenu'] += 1
                a_regarder.append((groupe.name,
                                   'le nom existe mais le contenu differe',
                                   canon))
            else:
                stats['introuvable'] += 1
                a_regarder.append((groupe.name, 'aucun candidat', canon))
            continue

        gestes.append({'groupe': groupe.name, 'manifeste': str(mani_p),
                       'avant': canon, 'apres': trouve})
        stats['reancres'] += 1
        if a.appliquer:
            mani['canonique_avant'] = canon
            mani['canonique'] = trouve
            mani['reancre_le'] = time.strftime('%Y-%m-%d %H:%M:%S')
            try:
                ecrire_atomique(mani_p, mani)
            except OSError as e:
                print(f'  ! {mani_p} : {e}')

    journal = None
    if a.appliquer and gestes:
        journal = nouveau_journal()
        journal.write_text(json.dumps(
            {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
             'corbeille': str(corbeille), 'gestes': gestes},
            ensure_ascii=False, indent=1), encoding='utf-8')

    print('-' * 64)
    print(f"groupes lus              : {stats['groupes']}")
    print(f"canonique deja en place  : {stats['en_place']}")
    print(f"REANCRES (sha256 egal)   : {stats['reancres']}"
          + ('' if a.appliquer else '   <- apercu, rien ecrit'))
    print(f"nom pris, autre contenu  : {stats['autre_contenu']}   <- A REGARDER")
    print(f"aucun candidat           : {stats['introuvable']}   <- A REGARDER")
    print(f"manifeste sans sha256    : {stats['illisible']}")
    for nom, pourquoi, ou in a_regarder[:20]:
        print(f'  [garde] {nom} : {pourquoi}')
        print(f'          notee : {ou}')
    if journal:
        print(f'journal d annulation : {journal}')
        print(f'  pour tout defaire : python {Path(__file__).name} '
              f'--annuler "{journal}"')
    if not a.appliquer:
        print('(apercu — ajoute --appliquer pour reecrire les manifestes.)')
    print('Ensuite : bat 24 purge ce qui a retrouve sa canonique.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
