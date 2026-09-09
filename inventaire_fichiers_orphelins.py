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
cinq familles :

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
  python inventaire_fichiers_orphelins.py --famille "LU PAR CONVENTION"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# ── Les elagages, et POURQUOI ils sont ancres ──────────────────────────────
#
# **La troisieme porte de l'angle mort du 09/09, et de loin la plus large.**
# Ces noms etaient dans un seul ensemble, compare au nom NU de chaque dossier
# rencontre, a n'importe quelle profondeur. `_corbeille_session` designait la
# corbeille VIVANTE, a la racine -- mais il faisait aussi taire
# `_to_delete/corbeilles_avant_25-08/_corbeille_session/`, une corbeille MORTE
# archivee dans la quarantaine. Mesure : sur les 800 fichiers de
# `_to_delete/`, 579 etaient elagues par ce seul nom, 3 par
# `_corbeille_copies`, et 218 seulement etaient parcourus.
#
# Une protection qui vise un dossier PARTICULIER doit nommer sa PLACE, pas
# seulement son nom : sinon elle protege aussi ses homonymes, y compris ceux
# qu'on vient de mettre a la poubelle.
#
# Elagues partout : ils s'imbriquent par nature et ne sont jamais du contenu
# de projet.
IGNORES_PARTOUT = {'.git', '.venv', 'node_modules'}

# Elagues UNIQUEMENT a la racine du depot : ce sont des meubles de ce
# projet-ci. Un dossier du meme nom trouve ailleurs est du contenu ordinaire,
# et doit etre juge comme tel.
IGNORES_RACINE = {'exiftool-13.59_64', 'photo_thumbs', 'face_thumbs',
                  'animal_thumbs', 'dist', 'OLD', '_corbeille_copies',
                  '_corbeille_session', 'recuperees', 'uploads', '.claude',
                  '_bat_archive',
                  # Ce que le menage vient de sortir du depot. Le parcourir
                  # rejuge ce qui est deja juge, et son `_manifeste.json`
                  # CITE les 506 fichiers deplaces : mesure du 09/09, la
                  # famille `CITE EN DOC SEUL` passe de 97 a 635 d'un coup,
                  # parce que le proces-verbal du menage temoigne de ses
                  # propres victimes.
                  '_corbeille_menage'}

# Dossiers PARCOURUS, mais dont rien ne peut servir de LECTEUR : des artefacts
# de construction.
#
# **La derniere moitie de l'angle mort du 09/09, et la plus instructive.**
# Ouvrir le parcours aux binaires (voir `_tous_les_fichiers`) n'a rendu que 217
# des 800 fichiers de `_to_delete/` : les 583 autres sont des `.pyc` ranges
# dans des `__pycache__`, et `__pycache__` etait ici, dans IGNORES. La cecite
# avait DEUX portes -- un filtre d'EXTENSION et un elagage de DOSSIER -- et
# reparer la premiere laissait la seconde grande ouverte. **Quand on corrige un
# angle mort, on cherche ses autres portes avant de se declarer content.**
#
# Un `.pyc` est regenerable par construction : personne ne le cite, et c'est
# normal. L'inventaire le dit ORPHELIN, ce qui est la verite ; c'est la
# POLITIQUE d'`appliquer_menage.py` qui decide OU on a le droit d'en tirer une
# consequence -- aujourd'hui `_to_delete/` seul. Juger et effacer restent deux
# gestes separes.
ARTEFACTS = {'__pycache__'}

# CE QUI NE COMPTE PAS COMME LECTEUR. Second faux verdict de cet instrument
# sur lui-meme (09/09) : sa propre sortie `_orphelins.json` cite TOUS les
# fichiers du depot, et `_banc_sortie.txt` recopie ce qu'il vient d'imprimer.
# Chaque fichier devenait donc « cite quelque part » -- par le rapport qui
# venait de le declarer orphelin. Un instrument qui se lit lui-meme se donne
# toujours raison.
PAS_DES_LECTEURS = {'_orphelins.json', '_banc_sortie.txt', '_etat_banc.json',
                    '_etat_git.json', '_journal_serveur.log',
                    '_journal_serveur.log.1',
                    # LA MEME PATHOLOGIE, UN CRAN PLUS HAUT (09/09 au soir).
                    # `appliquer_menage.py` porte la POLITIQUE : une liste de
                    # motifs de fichiers A JETER. Comptee comme lecture, elle
                    # PROTEGE exactement ce qu'elle designe -- mesure :
                    # `_rapport_perdus_takeout.json` etait retenu par le veto
                    # parce que le nettoyeur le nommait comme cible. Son banc
                    # fait pareil avec ses fixtures (`_rapport_sef_avant.json`).
                    # Nommer une chose pour l'effacer n'est pas la lire.
                    'appliquer_menage.py', 'test_appliquer_menage.py',
                    # ET LE QUATRIEME CAS, QUE J'AI FABRIQUE MOI-MEME EN
                    # DOCUMENTANT LES TROIS PREMIERS (09/09, mesure).
                    # Ce fichier-ci et son banc citent en clair, dans leurs
                    # commentaires et leurs bancs, chaque fichier sur lequel
                    # l'instrument s'est trompe : `_rapport_google_apres2.json`,
                    # `_rapport_perdus_takeout.json`, `_rapport_sef_avant.json`.
                    # Resultat mesure : au passage suivant, ces fichiers etaient
                    # de nouveau `LU PAR DU CODE` -- **lus par l'instrument qui
                    # venait d'expliquer pourquoi personne ne les lisait**.
                    # Ecrire l'histoire d'une erreur la refaisait.
                    #
                    # La regle, une bonne fois : **rien de la chaine de menage
                    # n'est un lecteur** -- ni l'instrument, ni son banc, ni le
                    # nettoyeur, ni le sien, ni leurs rapports, ni leurs
                    # manifestes. Un outil qui juge ne temoigne pas.
                    'inventaire_fichiers_orphelins.py',
                    'test_inventaire_fichiers_orphelins.py'}

# Fichiers dont l'absence de citation ne veut RIEN dire : ils sont lus par le
# systeme, pas par le projet. **Ancre a la racine** (voir `protege_par_nom`) :
# une COPIE de `photos.db` archivee dans `_to_delete/` n'est pas la base
# vivante, et la proteger sous pretexte qu'elle porte le meme nom cache 283 Mo
# a l'inventaire sans que personne l'ait decide.
JAMAIS_ORPHELIN = {
    '.gitignore', '.gitattributes', 'requirements.txt', 'CLAUDE.md',
    'README.md', 'INSTALLATION.md', 'ROADMAP.md', 'PROMPT_NOUVELLE_SESSION.md',
    'QUESTIONS_MIKE.md', 'MARCHE_A_SUIVRE.md', 'server.py',
    'photos.db', 'copie.db',
}


def protege_par_nom(p, racine):
    """Ce fichier est-il un meuble du depot, protege par son nom ?

    A LA RACINE seulement. Ailleurs, un fichier qui porte le nom d'un meuble
    est un homonyme, et un homonyme se juge."""
    return p.parent == racine and p.name in JAMAIS_ORPHELIN


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
    aurait proposé d'effacer toute la suite de tests.

    Les trois dernières règles sont arrivées le 09/09 avec l'ouverture de
    l'inventaire aux fichiers BINAIRES (voir `_tous_les_fichiers`). Tant que
    l'instrument ne voyait que du texte, elles n'avaient pas lieu d'être ;
    dès qu'il a vu le dépôt entier, `photos.db-wal` et `yolo11s.pt` sont
    devenus des candidats que personne ne cite par leur nom. **Élargir le
    champ d'un instrument crée des angles morts neufs : les chercher fait
    partie de l'élargissement.**"""
    n = p.name
    nl = n.lower()
    sfx = p.suffix.lower()
    if n.startswith('test_') and p.suffix == '.py':
        return "banc : trouve par le lanceur de tests, jamais cite"
    if sfx == '.bat' and p.parent == racine:
        return "porte d entree de Mike : un .bat se lance au double-clic"
    if p.parent.name == 'pages' and sfx == '.html':
        return "page servie par chemin CALCULE (ui/pages/<nom>.html)"
    if sfx == '.md' and p.parent.name in ('docs', 'eval'):
        return "carnet : lu par un humain, pas par le code"
    # Annexe SQLite : `-wal` et `-shm` ne sont JAMAIS cites, et separer un WAL
    # de sa base pendant que le serveur ecrit dedans corrompt la base.
    if re.search(r'\.db-(wal|shm|journal)$', nl):
        return "annexe SQLite : appartient a la base, jamais separable"
    # Poids de modele : charges par une constante ou un nom construit, lourds
    # a re-telecharger, et hors de portee d'une recherche par nom si le code
    # ecrit `MODELE = 'yolo11' + taille + '.pt'`.
    if sfx in ('.pt', '.onnx', '.gguf', '.safetensors', '.bin', '.pth'):
        return "poids de modele : couteux a perdre, souvent nomme par calcul"
    # Un __init__.py vide n'est jamais cite : c'est le paquet qui l'est.
    if n == '__init__.py':
        return "marqueur de paquet : c est le dossier qui est importe"
    return None


# Ce qu'on regarde comme "du code qui lit".
EXT_LECTEURS = {'.py', '.bat', '.txt', '.md', '.json', '.css', '.html', '.js',
                '.jsonl', '.cfg', '.ini', '.yml', '.yaml', '.toml'}
EXT_CODE = {'.py', '.bat'}

# Au-dela, on ne charge pas le fichier en memoire pour y chercher des noms.
# `cities1000.txt` fait 31 Mo a lui seul. Le plafond est un choix de cout, PAS
# un jugement : un lecteur ecarte pour sa taille est COMPTE et affiche dans le
# resume, sinon il redevient un angle mort silencieux.
PLAFOND_LECTURE = 3_000_000


def _tous_les_fichiers(racine, elagues=None):
    """Le vivier des CANDIDATS : tout fichier du depot. Aucun filtre d'extension.

    **Troisieme faux verdict de cet instrument sur lui-meme (09/09), et le
    plus couteux.** L'ancienne version ne rendait ici que les fichiers dont
    l'extension etait dans EXT_LECTEURS : j'avais confondu « peut lire » et
    « peut etre lu ». Mesure sur `_to_delete/` apres le bat 50 : 800 fichiers,
    dont 609 jamais parcourus (560 .pyc, 24 .jsonl, 9 .jpg, 8 .b64). Absents
    de l'inventaire, donc « non vus » pour le veto d'`appliquer_menage.py`,
    donc tous retenus. J'ai lu les 810 retenus du bat 50 comme de la prudence :
    c'etait une cecite, et le veto m'a rattrape a ma place.

    Un `.pyc` ne peut pas etre un LECTEUR -- on n'y cherche pas de citation.
    Il est parfaitement un CANDIDAT. Les deux questions sont maintenant
    posees separement : ici « quels fichiers existent », dans `_peut_lire`
    « lesquels savent citer un nom »."""
    for d, sousd, noms in os.walk(racine):
        ici = Path(d)
        a_la_racine = (ici == Path(racine))
        gardes = []
        for s in sousd:
            if s in IGNORES_PARTOUT or s.startswith('.'):
                motif = 'partout'
            elif a_la_racine and s in IGNORES_RACINE:
                motif = 'meuble du depot'
            else:
                gardes.append(s)
                continue
            if elagues is not None:
                elagues.append((str((ici / s).relative_to(racine)), motif))
        sousd[:] = gardes
        for n in noms:
            yield ici / n


def _peut_lire(p):
    """Ce fichier peut-il CITER le nom d'un autre ? Seul du texte le peut."""
    if p.name in PAS_DES_LECTEURS:
        return False
    if any(d in ARTEFACTS for d in p.parts[:-1]):
        return False
    return p.suffix.lower() in EXT_LECTEURS or p.suffix == ''


def _lire(p, plafond=PLAFOND_LECTURE):
    """Le texte du fichier, ou None s'il n'a PAS ete lu.

    La distinction compte : `''` disait « lu, et vide », `None` dit « pas
    lu ». L'ancienne version rendait `''` dans les deux cas, et un lecteur
    ecarte pour sa taille disparaissait sans laisser de trace."""
    try:
        if p.stat().st_size > plafond:
            return None
        return p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None


# Les lignes d'un .bat qui PARLENT au lieu d'AGIR : un commentaire `REM` ou
# `::`, et un `echo` qui n'ecrit nulle part. Le `(?!...)` epargne
# `echo livrer > _commande_git.txt` : un echo REDIRIGE ecrit un fichier pour
# de bon, et c'est meme le canal de commande de tout ce projet.
_BAVARDAGE_BAT = re.compile(r'(?im)^[ \t]*(?:rem\b|::|echo(?![^\r\n]*[>|])).*$')


def sans_bavardage(texte, suffixe):
    """Le texte d'un .bat prive de ce qui parle sans agir.

    Sert UNIQUEMENT a SIGNALER qu'une citation est peut-etre memorielle -- pas
    a changer de famille. Un bat qui ecrit « REM lit _google.json » a presque
    toujours la vraie lecture deux lignes plus bas ; degrader la famille sur
    ce seul indice effacerait des entrees vivantes. L'instrument signale et
    l'humain tranche.

    Les deux cas mesures le 09/09 : le bat 33 dit en `REM` qu'il lisait
    `_rapport_google_apres2.json` **et a cesse de le faire** -- le commentaire
    dit le contraire de ce que la recherche par nom en conclut ; et sa ligne
    105 `echo` la commande d'exemple qui nomme `_rapport_google_apres.json`,
    du texte a l'ecran, pas un fichier ouvert."""
    if suffixe.lower() != '.bat':
        return texte
    return _BAVARDAGE_BAT.sub('', texte)


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


def inventorier(racine=RACINE, bilan=None):
    """La liste des candidats et leur famille.

    `bilan`, si un dict est passe, est REMPLI avec ce que la liste ne dit pas :
    combien de fichiers ont ete parcourus, combien pouvaient servir de lecteur,
    et combien de lecteurs ont ete ecartes faute d'etre lisibles. Le contrat de
    retour ne bouge pas -- `appliquer_menage.py` appelle `inventorier(RACINE)`
    et attend une liste."""
    elagues = []
    candidats = sorted(_tous_les_fichiers(racine, elagues))

    textes = {}
    lecteurs_potentiels = 0
    ecartes_taille, ecartes_illisibles = [], []
    for p in candidats:
        if not _peut_lire(p):
            continue
        lecteurs_potentiels += 1
        t = _lire(p)
        if t is None:
            try:
                gros = p.stat().st_size > PLAFOND_LECTURE
            except OSError:
                gros = False
            (ecartes_taille if gros else ecartes_illisibles).append(
                str(p.relative_to(racine)))
            continue
        textes[p] = t

    codes = [t for p, t in textes.items() if p.suffix.lower() in EXT_CODE]
    motifs = motifs_du_code(codes)

    out = []
    for p in candidats:
        nom = p.name
        if protege_par_nom(p, racine):
            continue
        tige = p.stem
        lecteurs_code, lecteurs_doc = [], []
        code_hors_bavardage = False
        for q, t in textes.items():
            if q == p:
                continue
            if not (nom in t or (len(tige) > 6 and tige in t)):
                continue
            rel = str(q.relative_to(racine))
            if q.suffix.lower() in EXT_CODE:
                lecteurs_code.append(rel)
                vif = sans_bavardage(t, q.suffix)
                if nom in vif or (len(tige) > 6 and tige in vif):
                    code_hors_bavardage = True
            else:
                lecteurs_doc.append(rel)

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
                    'texte': p in textes,
                    'citation_bavarde': bool(lecteurs_code)
                                         and not code_hors_bavardage,
                    'lecteurs_code': sorted(lecteurs_code)[:4],
                    'lecteurs_doc': sorted(lecteurs_doc)[:3]})

    if bilan is not None:
        bilan.update({
            'parcourus': len(candidats),
            'juges': len(out),
            'proteges_par_nom': len(candidats) - len(out),
            'lecteurs_potentiels': lecteurs_potentiels,
            'lecteurs_lus': len(textes),
            'ecartes_taille': ecartes_taille,
            'ecartes_illisibles': ecartes_illisibles,
            'elagues': sorted(elagues),
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--json', dest='sortie_json', default='')
    ap.add_argument('--famille', default='',
                    help='n afficher qu une famille (ORPHELIN, ...)')
    a = ap.parse_args(argv)

    bilan = {}
    lignes = inventorier(RACINE, bilan)
    par_fam = {}
    for l in lignes:
        par_fam.setdefault(l['famille'], []).append(l)

    print('=' * 74)
    print('  QUI LIT CE FICHIER ? -- %d fichiers juges' % len(lignes))
    print('=' * 74)
    # LE COMPTE D'ABORD. Un angle mort qui ne se compte pas ne se voit jamais :
    # c'est exactement ce qui a fait passer 609 binaires pour de la prudence.
    print('  parcourus dans le depot        : %4d' % bilan['parcourus'])
    print('  proteges par leur nom          : %4d  (JAMAIS_ORPHELIN)'
          % bilan['proteges_par_nom'])
    print('  dont lisibles comme LECTEURS   : %4d sur %4d candidats textuels'
          % (bilan['lecteurs_lus'], bilan['lecteurs_potentiels']))
    ecartes = bilan['ecartes_taille'] + bilan['ecartes_illisibles']
    print('  lecteurs ecartes (taille/lect.): %4d%s'
          % (len(ecartes), ('  -> ' + ', '.join(ecartes[:3])) if ecartes else ''))
    # Les dossiers elagues sont LE point aveugle restant, et le seul moyen
    # qu'il ne redevienne pas invisible est de l'imprimer a chaque passage.
    print('  dossiers elagues (non parcourus): %4d%s'
          % (len(bilan['elagues']),
             ('  -> ' + ', '.join(e for e, _ in bilan['elagues'][:4]))
             if bilan['elagues'] else ''))
    print('-' * 74)
    for fam in ('LU PAR DU CODE', 'LU PAR CONVENTION', 'LU PAR UN MOTIF',
                'CITE EN DOC SEUL', 'ORPHELIN'):
        l = par_fam.get(fam, [])
        poids = sum(x['octets'] for x in l)
        print('  %-17s %4d fichier(s)  %10.1f Mo'
              % (fam, len(l), poids / 1048576))
    doute = [x for x in lignes if x['citation_bavarde']]
    if doute:
        print('-' * 74)
        print('  A RELIRE : %d fichier(s) dont TOUTE citation en .bat est un'
              % len(doute))
        print('  commentaire (REM / ::) ou un echo non redirige -- du texte,')
        print('  pas une lecture. Famille laissee a LU PAR DU CODE : c est')
        print('  un doute a trancher par un humain, pas par l instrument.')
        for x in doute[:8]:
            print('    %s  <- %s' % (x['fichier'], ', '.join(x['lecteurs_code'])))
    print('-' * 74)

    montrer = a.famille.upper() or 'ORPHELIN'
    l = sorted(par_fam.get(montrer, []), key=lambda x: -x['octets'])
    print('  %s -- le detail (%d) :' % (montrer, len(l)))
    for x in l[:80]:
        print('    %8.1f Ko  %s' % (x['octets'] / 1024, x['fichier']))
        if x['lecteurs_doc']:
            print('                 cite dans : %s'
                  % ', '.join(x['lecteurs_doc']))
    if len(l) > 80:
        print('    ... et %d autres (voir le --json)' % (len(l) - 80))
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
