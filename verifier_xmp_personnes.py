#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification — ce que la file XMP doit encore au fonds
──────────────────────────────────────────────────────────────────────────────

POURQUOI CE BANC EXISTE

Les noms attribués vivent dans les XMP des FICHIERS : c'est ce qui les fait
survivre à la base (règle 2). Entre le moment où l'index reçoit un nom et celui
où le fichier le porte, il y a `PERSON_QUEUE` — et cette file n'est qu'un
`queue.Queue()` EN MÉMOIRE. Le 23/08, la fusion Flo → Florine y a laissé
~11 800 opérations à 0,28 op/s, soit onze heures pendant lesquelles un
redémarrage, une coupure de courant ou un plantage effaçait le travail restant
SANS LAISSER DE TRACE. Pire : l'index, lui, dirait `Florine` — et des milliers
de fichiers garderaient `Flo`. C'est exactement la façon dont naît un nom
fantôme, et personne ne saurait lesquels réparer.

Ce banc rend l'accident RÉPARABLE. Il ne lit pas la file (elle est en mémoire,
donc invisible de l'extérieur) : il compare deux choses qui SURVIVENT — ce que
l'index dit, et ce que les fichiers portent — et il NOMME les photos en écart.
La file cesse d'être un pari : ce qu'elle doit encore se recompte, à tout
moment, depuis le disque.

CE QU'IL NE FAIT PAS

Il n'écrit RIEN, ni dans les fichiers ni dans la base : famille `verifier_`,
lecture seule (cf. `banc_agent.py`). Réparer est un geste de Mike, et il aura
sous les yeux la liste que ce banc écrit (`--json`).
Il n'ouvre jamais `photos.db` : le serveur en est l'écrivain unique. La vérité
d'index est DEMANDÉE au serveur en HTTP.

CE QU'IL DIT QUAND IL NE SAIT PAS

Un fichier absent, illisible ou hors du fonds n'est pas un écart : il est
COMPTÉ À PART et nommé. Un banc qui range l'inconnu avec le connu ment.

DEUX CHIFFRES INDÉPENDANTS

Si le serveur répond, le banc affiche aussi `queues.personnes`. Les deux
nombres ne mesurent pas la même chose — la file compte des OPÉRATIONS (une
photo renommée en demande deux, et une même photo peut y figurer plusieurs
fois), le fonds compte des PHOTOS en écart. Les voir côte à côte est ce qui
permet de dire si la file travaille ou si elle se répète.

USAGE
    python verifier_xmp_personnes.py --nom Florine
    python verifier_xmp_personnes.py --nom Florine --absent Flo
    python verifier_xmp_personnes.py --nom Florine --echantillon 300
    python verifier_xmp_personnes.py --nom Florine --json _xmp_florine.json
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent
PREFIXE = "personne"
LOT = 300                      # fichiers par invocation d'ExifTool


# ────────────────────────────── Les chemins ──────────────────────────────

def dossier_uploads(racine=None):
    """UPLOAD_DIR, lu comme le lit `server.py` (l. 107-120) : première ligne
    non commentée de `dossier_uploads.txt`."""
    racine = Path(racine or RACINE)
    try:
        for ligne in (racine / "dossier_uploads.txt").read_text(
                encoding='utf-8').splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith('#'):
                return Path(ligne)
    except OSError:
        pass
    return None


def chemin_de_cle(cle, uploads):
    """Clé d'index → chemin, comme `_resolve_key` (server.py l. 2142) : une clé
    absolue est un chemin, une clé simple vit sous UPLOAD_DIR."""
    p = Path(cle)
    if p.is_absolute():
        return p
    return (Path(uploads) / cle) if uploads else None


def exiftool_exe(racine=None):
    """ExifTool, sans jamais rien renommer (`ensure_exiftool` le fait, pas nous :
    un banc de mesure ne modifie pas l'installation qu'il mesure)."""
    w = shutil.which("exiftool")
    if w:
        return Path(w)
    racine = Path(racine or RACINE)
    for motif in ("exiftool.exe", "exiftool-*/exiftool.exe",
                  "Image-ExifTool-*/exiftool"):
        for c in sorted(racine.glob(motif)):
            if c.is_file():
                return c
    return None


# ─────────────────────────── La vérité d'index ───────────────────────────

def cles_du_nom(nom, serveur, timeout=120, essais=3):
    """Les clés que l'INDEX dit taguées `personne:Nom` (`/api/people/photos`).

    `light=1` : on ne veut que des clés, pas des vignettes ni des dates.

    ELLE RÉESSAIE, et ça n'est pas de la coquetterie. Le 23/08, le premier
    balayage des 352 noms en a perdu deux — « Remote end closed connection
    without response » : le serveur ferme la connexion quand on l'enchaîne
    trois cent cinquante fois. L'un des deux était **Val, 1 205 photos**. Un
    nom perdu ici, c'est un nom que la réparation ne verra jamais, alors même
    que ses photos seront marquées faites parce qu'elles en portent un autre.
    Trois essais, pause qui double. Ce qui échoue quand même LÈVE — l'appelant
    doit pouvoir le nommer, pas recevoir une liste vide qui ressemble à un nom
    sans photo."""
    url = (serveur.rstrip('/') + '/api/people/photos?'
           + urllib.parse.urlencode({'name': nom, 'limit': 50000,
                                     'light': 1, 'order': 'best'}))
    dernier = None
    for i in range(max(1, essais)):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                data = json.loads(r.read().decode('utf-8'))
            return [p.get('key') for p in (data.get('photos') or [])
                    if p.get('key')]
        except (OSError, ValueError) as e:                    # noqa: PERF203
            dernier = e
            if i + 1 < max(1, essais):
                time.sleep(0.5 * (2 ** i))
    raise dernier


def file_du_serveur(serveur, timeout=20):
    """`queues.personnes`, ou None si le serveur ne répond pas."""
    try:
        url = serveur.rstrip('/') + '/api/maint/status'
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return (json.loads(r.read().decode('utf-8'))
                    .get('queues', {}).get('personnes'))
    except (urllib.error.URLError, OSError, ValueError):
        return None


# ──────────────────────── Ce que portent les fichiers ────────────────────────

def _normalise(chemin):
    return str(chemin).replace('\\', '/').lower()


def _mots(valeur):
    """XMP:Subject et IPTC:Keywords rendent tantôt une chaîne, tantôt une liste."""
    if valeur is None:
        return []
    if isinstance(valeur, (list, tuple)):
        return [str(x) for x in valeur]
    return [str(valeur)]


def lire_tags(chemins, exe, lot=LOT, journal=None):
    """{chemin normalisé → ensemble de mots-clés en minuscules} pour les fichiers
    qu'ExifTool a su lire. Les autres ne figurent tout simplement pas.

    Une seule invocation par LOT : le coût d'ExifTool est son démarrage, et
    c'est justement ce que `person_writer` paye 11 800 fois."""
    vus = {}
    chemins = list(chemins)
    for debut in range(0, len(chemins), lot):
        tranche = chemins[debut:debut + lot]
        args = ['-json', '-m', '-q', '-charset', 'filename=UTF8',
                '-XMP-dc:Subject', '-IPTC:Keywords'] + [str(p) for p in tranche]
        argfile = None
        try:
            # argfile UTF-8 AVEC BOM : sous Windows, c'est ce qui fait survivre
            # les accents des chemins (même motif que `_run_exiftool`).
            with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                             encoding='utf-8-sig') as tf:
                tf.write('\n'.join(args))
                argfile = tf.name
            r = subprocess.run([str(exe), '-@', argfile], capture_output=True,
                               text=True, encoding='utf-8', errors='replace',
                               timeout=600)
            for enr in json.loads(r.stdout or '[]'):
                src = enr.get('SourceFile')
                if not src:
                    continue
                mots = _mots(enr.get('Subject')) + _mots(enr.get('Keywords'))
                vus[_normalise(src)] = {m.strip().lower() for m in mots}
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            if journal:
                journal("  lot %d-%d illisible : %s" % (debut,
                                                        debut + len(tranche), e))
        finally:
            if argfile:
                try:
                    os.unlink(argfile)
                except OSError:
                    pass
    return vus


# ─────────────────────────────── L'arithmétique ───────────────────────────────

def comparer(cles, uploads, tags_par_chemin, nom, absent=''):
    """Range chaque clé dans UNE case, et une seule.

    porte      : le fichier porte bien `personne:Nom`
    manque     : l'index le dit, le fichier ne le porte pas → la file le doit
    fantome    : le fichier porte encore `personne:Absent` (l'ancien nom)
    introuvable: aucun chemin (clé hors fonds) ou fichier absent du disque
    illisible  : ExifTool n'a rien rendu pour ce fichier
    Un « manque » peut être aussi « fantome » : les deux listes se recoupent
    volontairement, elles ne répondent pas à la même question.
    """
    attendu = ("%s:%s" % (PREFIXE, nom)).lower()
    ancien = ("%s:%s" % (PREFIXE, absent)).lower() if absent else None
    res = {'porte': [], 'manque': [], 'fantome': [], 'introuvable': [],
           'illisible': []}
    for cle in cles:
        chemin = chemin_de_cle(cle, uploads)
        if chemin is None:
            res['introuvable'].append(cle)
            continue
        mots = tags_par_chemin.get(_normalise(chemin))
        if mots is None:
            res['illisible'].append(cle)
            continue
        (res['porte'] if attendu in mots else res['manque']).append(cle)
        if ancien and ancien in mots:
            res['fantome'].append(cle)
    return res


def echantillonner(cles, taille, graine=1789):
    """Sous-ensemble REPRODUCTIBLE (graine fixe) : deux passages du banc sur le
    même fonds doivent pouvoir être comparés."""
    if not taille or taille >= len(cles):
        return list(cles), False
    rnd = random.Random(graine)
    return sorted(rnd.sample(list(cles), taille)), True


# ──────────────────────────────── Le rapport ────────────────────────────────

def rapporter(res, nom, absent, total, echantillon, file_serveur, ecrire=print):
    vus = len(res['porte']) + len(res['manque'])
    ecrire("")
    ecrire("=" * 74)
    ecrire("  CE QUE LA FILE XMP DOIT ENCORE — personne:%s" % nom)
    ecrire("=" * 74)
    ecrire("  index      : %d photo(s) taguee(s) %s" % (total, nom))
    if echantillon:
        ecrire("  echantillon: %d fichier(s) lu(s) (graine fixe, reproductible)"
               % len(res['porte'] + res['manque'] + res['illisible']
                     + res['introuvable']))
    ecrire("  fichiers   : %d lu(s) par ExifTool" % vus)
    ecrire("")
    ecrire("  porte le nom      : %d" % len(res['porte']))
    ecrire("  MANQUE (la file le doit) : %d" % len(res['manque']))
    if absent:
        ecrire("  porte encore %-8s: %d" % (absent, len(res['fantome'])))
    ecrire("")
    ecrire("  NON VERIFIE (ni ecart, ni conformite) :")
    ecrire("    introuvable sur le disque : %d" % len(res['introuvable']))
    ecrire("    illisible par ExifTool    : %d" % len(res['illisible']))
    if file_serveur is not None:
        ecrire("")
        ecrire("  la file du serveur annonce %d OPERATION(S) restante(s)"
               % file_serveur)
        ecrire("  (operations, pas photos : un renommage en demande deux)")
    ecrire("=" * 74)
    if res['manque'] or res['fantome']:
        ecrire("  Un ecart n'est pas forcement un defaut : tant que la file")
        ecrire("  tourne, elle est en train de le combler. Relancer ce banc")
        ecrire("  plus tard dit si elle avance.")
    else:
        ecrire("  Aucun ecart : le fonds porte ce que l'index dit.")
    ecrire("=" * 74)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--nom', required=True,
                    help="le nom attendu dans les XMP (ex. Florine)")
    ap.add_argument('--absent', default='',
                    help="un nom qui ne doit PLUS y etre (ex. Flo)")
    ap.add_argument('--serveur', default='http://127.0.0.1:8080')
    ap.add_argument('--echantillon', type=int, default=0,
                    help="ne lire que N fichiers (0 = tous)")
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    exe = exiftool_exe()
    if exe is None:
        print("ExifTool introuvable : ce banc lit les fichiers, il ne peut "
              "rien conclure sans lui.")
        return 2
    try:
        cles = cles_du_nom(a.nom, a.serveur)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print("le serveur ne repond pas (%s) : la verite d'index vient de lui, "
              "ce banc ne l'invente pas." % e)
        return 2
    if not cles:
        print("l'index ne tague aucune photo personne:%s." % a.nom)
        return 0

    total = len(cles)
    lues, echantillon = echantillonner(cles, a.echantillon)
    uploads = dossier_uploads()
    chemins = [c for c in (chemin_de_cle(k, uploads) for k in lues)
               if c is not None]
    tags = lire_tags(chemins, exe, journal=print)
    res = comparer(lues, uploads, tags, a.nom, a.absent)
    rapporter(res, a.nom, a.absent, total, echantillon,
              file_du_serveur(a.serveur))

    if a.sortie_json:
        Path(a.sortie_json).write_text(json.dumps(
            {'nom': a.nom, 'absent': a.absent, 'index_total': total,
             'echantillon': bool(echantillon), 'lues': len(lues),
             'manque': res['manque'], 'fantome': res['fantome'],
             'introuvable': res['introuvable'], 'illisible': res['illisible'],
             'porte': len(res['porte'])},
            ensure_ascii=False, indent=1), encoding='utf-8')
        print("  ecart nomme dans %s" % a.sortie_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
