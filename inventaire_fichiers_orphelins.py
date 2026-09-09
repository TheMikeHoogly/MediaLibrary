#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qui LIT ce fichier ? -- l'inventaire des fichiers du dépôt que plus rien ne cite.

Ce banc existe à cause d'une bêtise du 08/09 : j'ai déplacé `_google.json` dans
`_to_delete/` parce qu'il commençait par un souligné, et j'ai cassé le bat 32
qui le lisait en entrée. Le `.gitignore` du projet le dit depuis :
**« c'est le RÔLE qui décide, pas le préfixe »**. Un nom ne dit pas si un
fichier sert ; ses LECTEURS le disent.

Ce que l'instrument fait, et rien d'autre : pour chaque fichier du dépôt, il
cherche son nom dans tous les autres fichiers texte, et range le résultat en
quatre familles :

  LU PAR DU CODE   -- cité par un .py, un .bat, un .txt de configuration.
                      Ne pas toucher.
  LU PAR CONVENTION-- personne ne le cite, et personne n'a besoin de le citer :
                      un `test_*.py` est trouve par le lanceur de tests, un
                      `.bat` est lance au double-clic par Mike, une page est
                      lue par un chemin calcule. **Cette famille manquait au
                      premier jet, et son absence rangeait la suite de tests
                      entiere en ORPHELIN.**
  LU PAR UN MOTIF  -- personne ne le cite par son nom, mais du code lit un
                      MOTIF qui l'attrape (`undo_*.json`, `copie_*.jsonl`).
                      **C'est le piège principal de cet exercice** : une
                      recherche par nom déclare ces fichiers orphelins alors
                      qu'ils sont lus à chaque exécution.
  CITÉ EN DOC SEUL -- aucun code ne le lit, mais un carnet en parle. C'est du
                      code mort DONT ON A ÉCRIT L'HISTOIRE : le supprimer
                      demande de corriger le carnet, pas seulement le dossier.
  ORPHELIN         -- personne, nulle part. Candidat au nettoyage.

Il n'efface RIEN et ne propose rien : il rend une liste, et le jugement reste
humain. Un fichier orphelin peut très bien être une pièce que Mike garde
exprès.

  python inventaire_fichiers_orphelins.py
  python inventaire_fichiers_orphelins.py --json _orphelins.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# Dossiers jamais parcourus : ni comme candidats, ni comme lecteurs.
IGNORES = {'.git', '.venv', '__pycache__', 'node_modules', 'exiftool-13.59_64',
           'photo_thumbs', 'face_thumbs', 'animal_thumbs', 'dist', 'OLD',
           '_corbeille_copies', '_corbeille_session', 'recuperees', 'uploads',
           '.claude', '_bat_archive'}

# CE QUI NE COMPTE PAS COMME LECTEUR. Second faux verdict de cet instrument
# sur lui-meme (09/09) : sa propre sortie `_orphelins.json` cite TOUS les
# fichiers du depot, et `_banc_sortie.txt` recopie ce qu'il vient d'imprimer.
# Chaque fichier devenait donc « cite quelque part » -- par le rapport qui
# venait de le declarer orphelin. Un instrument qui se lit lui-meme se donne
# toujours raison.
PAS_DES_LECTEURS = {'_orphelins.json', '_banc_sortie.txt', '_etat_banc.json',
                    '_etat_git.json', '_journal_serveur.log',
                    '_journal_serveur.log.1'}

# Fichiers dont l'absence de citation ne veut RIEN dire : ils sont lus par le
# systeme, pas par le projet.
JAMAIS_ORPHELIN = {
    '.gitignore', '.gitattributes', 'requirements.txt', 'CLAUDE.md',
    'README.md', 'INSTALLATION.md', 'ROADMAP.md', 'PROMPT_NOUVELLE_SESSION.md',
    'QUESTIONS_MIKE.md', 'server.py', 'photos.db', 'copie.db',
}

def lecteur_par_convention(p, racine):
    """Le lecteur qui ne CITE pas -- il trouve par convention.

    **Ce bloc est né d'un faux verdict de cet instrument lui-même.** Sa
    première exécution, le 09/09, a rangé en ORPHELIN cinquante-cinq
    `test_*.py`, vingt et un `.bat` et la page `/aide` : aucun n'est cité par
    son nom nulle part, et tous ont pourtant un lecteur. « Cité par un nom »
    n'est donc PAS la même chose que « a un lecteur » -- un lanceur de tests
    trouve par motif, un `.bat` se lance au double-clic par un humain, et une
    page est lue par un chemin CALCULÉ (`_gabarit(nom)` ouvre
    `ui/pages/<nom>.html`, vérifié dans `server.py`). Livrer cette liste-là
    aurait proposé d'effacer toute la suite de tests."""
    n = p.name
    if n.startswith('test_') and p.suffix == '.py':
        return "banc : trouve par le lanceur de tests, jamais cite"
    if p.suffix.lower() == '.bat' and p.parent == racine:
        return "porte d entree de Mike : un .bat se lance au double-clic"
    if p.parent.name == 'pages' and p.suffix.lower() == '.html':
        return "page servie par chemin CALCULE (ui/pages/<nom>.html)"
    if p.suffix.lower() == '.md' and p.parent.name in ('docs', 'eval'):
        return "carnet : lu par un humain, pas par le code"
    return None


# Ce qu'on regarde comme "du code qui lit".
EXT_LECTEURS = {'.py', '.bat', '.txt', '.md', '.json', '.css', '.html', '.js'}
EXT_CODE = {'.py', '.bat'}


def _fichiers(racine):
    for d, sousd, noms in os.walk(racine):
        sousd[:] = [s for s in sousd if s not in IGNORES and not s.startswith('.')]
        for n in noms:
            p = Path(d) / n
            if p.suffix.lower() in EXT_LECTEURS or p.suffix == '':
                yield p


def _lire(p, plafond=3_000_000):
    try:
        if p.stat().st_size > plafond:
            return ''
        return p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def motifs_du_code(textes_code):
    """Les MOTIFS de nom construits par le code : `undo_` + date + `.json`.

    On repere les prefixes litteraux colles a une variable ou a un joker --
    `f"undo_annee_{...}"`, `'copie_%s.jsonl' % ...`, `glob('undo_*.json')`.
    C'est approximatif par construction, et c'est voulu : mieux vaut declarer
    « lu par un motif » un fichier qui ne l'est pas que l'inverse. Se tromper
    ici dans l'autre sens efface une entree de bat."""
    motifs = set()
    for t in textes_code:
        for m in re.finditer(r'''["']([A-Za-z0-9_\-]{3,})[_\-]?(?:\{|%s|\*|\$)''', t):
            motifs.add(m.group(1).lower())
        for m in re.finditer(r'''glob\(\s*["']([A-Za-z0-9_\-]{3,})''', t):
            motifs.add(m.group(1).lower())
    return motifs


def inventorier(racine=RACINE):
    fichiers = sorted(_fichiers(racine))
    textes = {}
    for p in fichiers:
        textes[p] = _lire(p)
    codes = [t for p, t in textes.items() if p.suffix.lower() in EXT_CODE]
    motifs = motifs_du_code(codes)

    out = []
    for p in fichiers:
        nom = p.name
        if nom in JAMAIS_ORPHELIN:
            continue
        tige = p.stem
        lecteurs_code, lecteurs_doc = [], []
        for q, t in textes.items():
            if q == p or not t or q.name in PAS_DES_LECTEURS:
                continue
            if nom in t or (len(tige) > 6 and tige in t):
                rel = str(q.relative_to(racine))
                (lecteurs_code if q.suffix.lower() in EXT_CODE
                 else lecteurs_doc).append(rel)
        conv = lecteur_par_convention(p, racine)
        if lecteurs_code:
            fam = 'LU PAR DU CODE'
        elif conv:
            fam = 'LU PAR CONVENTION'
        elif any(tige.lower().startswith(m) or m in tige.lower() for m in motifs):
            fam = 'LU PAR UN MOTIF'
        elif lecteurs_doc:
            fam = 'CITE EN DOC SEUL'
        else:
            fam = 'ORPHELIN'
        try:
            octets = p.stat().st_size
        except OSError:
            octets = 0
        out.append({'fichier': str(p.relative_to(racine)), 'famille': fam,
                    'octets': octets, 'convention': conv or '',
                    'lecteurs_code': sorted(lecteurs_code)[:4],
                    'lecteurs_doc': sorted(lecteurs_doc)[:3]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--json', dest='sortie_json', default='')
    ap.add_argument('--famille', default='',
                    help='n afficher qu une famille (ORPHELIN, ...)')
    a = ap.parse_args(argv)

    lignes = inventorier()
    par_fam = {}
    for l in lignes:
        par_fam.setdefault(l['famille'], []).append(l)

    print('=' * 74)
    print('  QUI LIT CE FICHIER ? -- %d fichiers examines' % len(lignes))
    print('=' * 74)
    for fam in ('LU PAR DU CODE', 'LU PAR CONVENTION', 'LU PAR UN MOTIF',
                'CITE EN DOC SEUL', 'ORPHELIN'):
        l = par_fam.get(fam, [])
        poids = sum(x['octets'] for x in l)
        print('  %-17s %4d fichier(s)  %8.1f Ko' % (fam, len(l), poids / 1024))
    print('-' * 74)

    montrer = a.famille.upper() or 'ORPHELIN'
    l = sorted(par_fam.get(montrer, []), key=lambda x: -x['octets'])
    print('  %s -- le detail (%d) :' % (montrer, len(l)))
    for x in l:
        print('    %8.1f Ko  %s' % (x['octets'] / 1024, x['fichier']))
        if x['lecteurs_doc']:
            print('                 cite dans : %s'
                  % ', '.join(x['lecteurs_doc']))
    print('=' * 74)
    print('  Rien n a ete efface. Un orphelin peut etre une piece gardee')
    print('  expres : c est une liste a LIRE, pas une liste a executer.')

    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(lignes, indent=1, ensure_ascii=False), encoding='utf-8')
        print('  liste ecrite : %s' % a.sortie_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
