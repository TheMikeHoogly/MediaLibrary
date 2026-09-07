#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sortir de la corbeille de rangement les photos qui n'ont PAS de jumeau connu.

LE PROBLEME. `.corbeille-rangement/` garde des copies mises en quarantaine par
le dedoublonnage. Chaque groupe note dans son `manifeste.json` d'ou venait la
copie (`origine`) et quelle copie a ete GARDEE (`canonique`). Au 06/09 il
restait 44 groupes que `purger_corbeille.py` refusait de purger, faute de
canonique vivante -- et il avait raison de refuser.

`verifier_corbeille_par_pixels.py` les a tries en comparant les PIXELS, parce
que c'est ainsi que le bat 40 a dedoublonne -- pas au sha256, qui declarait a
tort 30 doublons reels comme « dernieres copies ». Verdict, dans
`docs/corbeille_par_pixels.json` :

  - `jumeau_pixels`      : la meme image existe ailleurs -> purgeable (bat 24) ;
  - `illisible`          : coquilles « Read error in the sector ! », rien dedans ;
  - `vraie_derniere_copie` : AUCUN jumeau connu. Purger detruirait la photo.

CET OUTIL rend au fonds les photos de la troisieme liste, et elles seules. Il
ne supprime jamais rien : il DEPLACE un fichier de la corbeille vers son
`origine`, et ecrit un journal d'annulation.

CE QU'IL REFUSE, et pourquoi il le DIT au lieu de se taire :
  - un groupe absent de `vraie_derniere_copie` : ce n'est pas a un outil de
    decider qu'une photo est la derniere de son espece ;
  - un fichier dont le sha256 ne correspond pas a son manifeste : le groupe ne
    contient plus ce qu'il annonce ;
  - une `origine` DEJA occupee : ecraser un fichier vivant pour restaurer une
    copie serait exactement la perte qu'on cherche a eviter.

DEJA FAIT N'EST PAS UN ECHEC. Un groupe deja restaure (manifeste portant
`restaure_le`, plus de photo dans le dossier) se compte comme « deja fait » et
ne fait pas rendre un code d'erreur -- deux bats du projet ont crie ECHEC a
tort sur un fonds propre, et un faux echec fait chercher une panne qui n'existe
pas.

Usage :
    python restaurer_corbeille.py                    # apercu, rien ne bouge
    python restaurer_corbeille.py --appliquer
    python restaurer_corbeille.py --annuler docs/undo_restauration_....json
"""

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
DOSSIER_JOURNAL = RACINE / 'docs'
RAPPORT = DOSSIER_JOURNAL / 'corbeille_par_pixels.json'
CLASSE = 'vraie_derniere_copie'


def sha256(path, buf=1 << 16, essais=3, pause=0.4):
    """sha256 resilient SMB (blocs 64 Ko + reprise) -- comme appliquer_plan."""
    dernier = None
    for _ in range(essais):
        h = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                while True:
                    bloc = f.read(buf)
                    if not bloc:
                        break
                    h.update(bloc)
            return h.hexdigest()
        except OSError as e:
            dernier = e
            time.sleep(pause)
    raise dernier


def lire_json(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return defaut


def ecrire_atomique(chemin, donnees):
    """tmp + replace : un manifeste a moitie ecrit vaut un manifeste perdu."""
    chemin = Path(chemin)
    tmp = chemin.with_suffix(chemin.suffix + '.tmp')
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1),
                   encoding='utf-8')
    tmp.replace(chemin)


def nouveau_journal(dossier=None):
    """Un nom libre, meme si deux gestes tombent dans la meme seconde."""
    dossier = Path(dossier or DOSSIER_JOURNAL)
    dossier.mkdir(parents=True, exist_ok=True)
    base = time.strftime('undo_restauration_%Y%m%d_%H%M%S')
    p = dossier / (base + '.json')
    n = 1
    while p.exists():
        p = dossier / f'{base}_{n}.json'
        n += 1
    return p


def deplacer(src, dst):
    """Deplacement qui traverse les volumes, et qui n'ECRASE jamais.

    `Path.rename` echoue entre deux volumes ; `shutil.move` recopie alors --
    mais il ECRASE la cible si elle existe, ce qui est exactement le geste
    interdit ici. Le controle d'existence est fait par l'appelant ET repete
    juste avant, parce qu'entre les deux il y a le NAS.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise FileExistsError(str(dst))
    shutil.move(str(src), str(dst))


def groupes_a_restaurer(rapport=None):
    """Les groupes que le rapport classe « vraie derniere copie ».

    Rend (liste, message d'erreur). La liste vient d'un JUGEMENT ecrit, jamais
    d'une heuristique de cet outil : c'est la seule facon d'etre sur qu'on ne
    restaure pas ce que quelqu'un a deja tranche autrement.
    """
    d = lire_json(rapport or RAPPORT)
    if not d:
        return [], f'Rapport introuvable ou illisible : {rapport or RAPPORT}'
    lignes = (d.get('lignes') or {}).get(CLASSE)
    if lignes is None:
        return [], f'Le rapport ne porte pas de classe « {CLASSE} ».'
    return lignes, ''


def restaurer(corbeille, lignes, appliquer, journal_dir=None):
    """Rend chaque photo de `lignes` a son `origine`. Ne supprime rien."""
    corbeille = Path(corbeille)
    stats = {'groupes': 0, 'restaures': 0, 'deja_fait': 0, 'refuses': 0}
    gestes = []
    for l in lignes:
        stats['groupes'] += 1
        gid, nom = l.get('groupe'), l.get('fichier')
        dossier = corbeille / str(gid)
        mani_p = dossier / 'manifeste.json'
        mani = lire_json(mani_p)
        if not mani:
            print(f'  [refus] {gid} : manifeste illisible — jamais a l aveugle')
            stats['refuses'] += 1
            continue
        origine = mani.get('origine')
        if not origine:
            print(f'  [refus] {gid} : le manifeste ne dit pas d ou venait la photo')
            stats['refuses'] += 1
            continue
        src = dossier / str(nom)
        if not src.exists():
            if mani.get('restaure_le'):
                print(f'  [deja fait] {gid} : {nom} -> {mani.get("restaure_vers")}')
                stats['deja_fait'] += 1
            else:
                print(f'  [refus] {gid} : {nom} absent du groupe')
                stats['refuses'] += 1
            continue
        attendu = mani.get('sha256')
        try:
            vu = sha256(src)
        except OSError as e:
            print(f'  [refus] {gid} : lecture impossible ({e})')
            stats['refuses'] += 1
            continue
        if attendu and vu != attendu:
            print(f'  [refus] {gid} : sha256 != manifeste — le groupe ne '
                  f'contient plus ce qu il annonce')
            stats['refuses'] += 1
            continue
        dst = Path(origine)
        if dst.exists():
            print(f'  [refus] {gid} : {origine} est DEJA occupe — restaurer '
                  f'par-dessus detruirait un fichier vivant')
            stats['refuses'] += 1
            continue
        print(f'  {"[restaure]" if appliquer else "[a restaurer]"} {gid} : '
              f'{nom} -> {origine}')
        if not appliquer:
            stats['restaures'] += 1
            continue
        try:
            deplacer(src, dst)
        except (OSError, FileExistsError) as e:
            print(f'  [refus] {gid} : deplacement impossible ({e})')
            stats['refuses'] += 1
            continue
        mani['restaure_le'] = time.strftime('%Y-%m-%d %H:%M:%S')
        mani['restaure_vers'] = str(dst)
        try:
            ecrire_atomique(mani_p, mani)
        except OSError as e:
            # Le fichier est deja rendu : on le DIT plutot que de le taire,
            # mais on ne le remet pas en quarantaine pour un manifeste.
            print(f'  ! {gid} : photo rendue, manifeste non mis a jour ({e})')
        gestes.append({'groupe': str(gid), 'de': str(dst), 'vers': str(src),
                       'manifeste': str(mani_p)})
        stats['restaures'] += 1

    journal = None
    if appliquer and gestes:
        journal = nouveau_journal(journal_dir)
        ecrire_atomique(journal, {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
                                  'outil': 'restaurer_corbeille',
                                  'gestes': gestes})
    return stats, journal


def annuler(journal):
    """Remet en quarantaine ce que la restauration avait rendu."""
    donnees = lire_json(journal)
    if not donnees or 'gestes' not in donnees:
        print(f'Journal illisible : {journal}')
        return 1
    remis = rates = 0
    for g in donnees['gestes']:
        try:
            deplacer(g['de'], g['vers'])
        except (OSError, FileExistsError) as e:
            print(f'  ! {g["de"]} : {e}')
            rates += 1
            continue
        mani_p = Path(g['manifeste'])
        mani = lire_json(mani_p)
        if mani:
            mani.pop('restaure_le', None)
            mani.pop('restaure_vers', None)
            try:
                ecrire_atomique(mani_p, mani)
            except OSError as e:
                print(f'  ! manifeste {mani_p} : {e}')
        remis += 1
    print(f'{remis} photo(s) remise(s) en quarantaine, {rates} echec(s).')
    return 1 if rates else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true',
                    help='deplacer pour de vrai (sinon : apercu seul)')
    ap.add_argument('--rapport', default=None,
                    help='rapport de tri (defaut : docs/corbeille_par_pixels.json)')
    ap.add_argument('--corbeille', default=None,
                    help='racine de la corbeille (defaut : docs/plan_rangement.json)')
    ap.add_argument('--annuler', metavar='JOURNAL',
                    help='remettre en quarantaine les photos du journal')
    a = ap.parse_args(argv)

    if a.annuler:
        return annuler(a.annuler)

    corbeille = a.corbeille
    if not corbeille:
        corbeille = (lire_json(RACINE / 'docs' / 'plan_rangement.json', {})
                     or {}).get('corbeille')
    if not corbeille:
        print('Corbeille inconnue (docs/plan_rangement.json).')
        return 1
    corbeille = Path(corbeille)
    if not corbeille.exists():
        print(f'Corbeille absente : {corbeille}')
        return 1

    rapport = Path(a.rapport) if a.rapport else RAPPORT
    lignes, err = groupes_a_restaurer(rapport)
    if err:
        print(err)
        return 1
    d = lire_json(rapport, {}) or {}
    print(f'Rapport du {d.get("genere_le", "?")} — {len(lignes)} photo(s) '
          f'classee(s) « {CLASSE} ».')
    if not lignes:
        print('Rien a restaurer.')
        return 0

    stats, journal = restaurer(corbeille, lignes, a.appliquer)
    print()
    print(f'{stats["groupes"]} groupe(s) | '
          f'{"restaures" if a.appliquer else "a restaurer"} : '
          f'{stats["restaures"]} | deja fait : {stats["deja_fait"]} | '
          f'refuses : {stats["refuses"]}')
    if journal:
        print(f'Annulation : python restaurer_corbeille.py --annuler "{journal}"')
    if not a.appliquer:
        print('(apercu — ajoute --appliquer pour deplacer.)')
    # Un refus est une information, pas forcement une panne : il rend 1 pour
    # que le bat s arrete et le fasse LIRE. « Deja fait », lui, ne rend rien.
    return 1 if stats['refuses'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
