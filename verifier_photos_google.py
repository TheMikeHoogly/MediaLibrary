#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification — le NAS porte-t-il vraiment ce que Google Photos garde ?
──────────────────────────────────────────────────────────────────────────────

POURQUOI CET INSTRUMENT EXISTE

Le 25/08, le compte Google est à **96,23 Go sur 100** — 3,8 Go de la panne, et
quand le quota est plein **Gmail cesse de RECEVOIR**. Les **75 Go de Google
Photos** sont, selon toute vraisemblance, un doublon de ce que le NAS reçoit
déjà par `_Uploads`. Les libérer réglerait le problème pour des années.

« Selon toute vraisemblance » n'est pas une preuve, et ce qu'on efface chez
Google ne revient pas. Cet instrument transforme la vraisemblance en compte :
pour chaque photo que Google détient, il dit si le NAS la porte, et **avec
quel degré de certitude**.

POURQUOI UN EXPORT TAKEOUT, ET PAS L'API

Depuis le **31 mars 2025**, l'API Google Photos ne laisse plus une application
tierce voir que ce qu'elle a elle-même envoyé (rclone le dit noir sur blanc
dans sa documentation). Aucun outil ne peut donc énumérer la photothèque à
distance. Le seul inventaire complet est un export **Google Takeout**, qui
dépose à côté de chaque média un `.json` portant son NOM D'ORIGINE et sa DATE
DE PRISE DE VUE — deux choses que le nom de fichier exporté, lui, peut avoir
perdues (Takeout tronque les noms longs et suffixe les collisions).

LES TROIS VERDICTS, ET LE SEUL QUI AUTORISE UNE SUPPRESSION

  CERTAIN   même nom, même TAILLE exacte → c'est le même fichier.
  PROBABLE  même nom, taille différente → Google a probablement ré-encodé
            (mode « économiseur de stockage »). À REGARDER, pas à effacer.
  AMBIGU    plusieurs fichiers de ce nom sur le NAS, aucun de la bonne
            taille. Nommé, jamais tranché à la place de quelqu'un.
  ABSENT    le NAS ne connaît pas ce nom. **Rien ne s'efface tant qu'il en
            reste un.**

CE QU'IL NE VOIT PAS, ET QUI COMPTE

- Une photo arrivée chez Google par un autre chemin — album partagé,
  WhatsApp, le téléphone de quelqu'un d'autre — n'a aucune raison d'être sur
  le NAS. Elle sortira ABSENTE, et c'est un ordre de COPIE, pas un écart à
  écarter.
- L'export est un instantané : ce qui est arrivé chez Google après lui n'y
  est pas.
- Sans `--empreinte`, la taille tient lieu de preuve. Deux fichiers de même
  nom et même taille sont le même fichier dans tous les cas réels, mais c'est
  une présomption, et le rapport le DIT.

CE QU'IL NE FAIT PAS

Il n'efface rien, nulle part : famille `verifier_`, lecture seule. Effacer
chez Google est un geste de Mike, sur `photos.google.com` — et le quota ne se
libère qu'une fois la CORBEILLE Google vidée.

USAGE
    python verifier_photos_google.py --takeout "D:\\Takeout\\Google Photos"
    python verifier_photos_google.py --takeout ... --empreinte --json _google.json
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventaire_fonds as F                                    # noqa: E402

RACINE = Path(__file__).resolve().parent

# Ce que Takeout dépose À CÔTÉ des médias et qui n'est pas un média.
PAS_UN_MEDIA = {'.json', '.html', '.htm', '.txt', '.csv', '.pdf'}

LISTE_MAX = 60          # ce qui n'est pas listé est COMPTÉ, jamais tu


def est_un_media(nom):
    return os.path.splitext(nom)[1].lower() not in PAS_UN_MEDIA


def sidecar(chemin):
    """Le `.json` que Takeout dépose à côté d'un média, s'il existe.

    Google a changé ce nom en cours de route : `photo.jpg.json` d'abord,
    `photo.jpg.supplemental-metadata.json` ensuite, et il tronque les noms
    longs. On essaie les formes connues, on ne devine pas au-delà."""
    for suffixe in ('.json', '.supplemental-metadata.json',
                    '.supplemental-meta.json'):
        p = Path(str(chemin) + suffixe)
        if p.is_file():
            return p
    return None


def lire_sidecar(p):
    """(titre d'origine, epoch de prise de vue) — (None, None) si illisible.

    Le TITRE prime sur le nom du fichier exporté : Takeout tronque les noms
    longs et suffixe les collisions (`IMG(1).jpg`), le titre non."""
    try:
        d = json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None, None
    titre = (d.get('title') or '').strip() or None
    quand = None
    pris = d.get('photoTakenTime') or d.get('creationTime') or {}
    try:
        quand = int(pris.get('timestamp'))
    except (TypeError, ValueError):
        quand = None
    return titre, quand


def inventaire_takeout(dossier, parcours=None):
    """Les médias de l'export. Liste de dicts {chemin, nom, octets, quand}."""
    out = []
    for chemin, octets in (parcours or F.parcourir)(dossier):
        nom = os.path.basename(chemin)
        if not est_un_media(nom) or octets is None:
            continue
        titre, quand = (None, None)
        sc = sidecar(chemin)
        if sc is not None:
            titre, quand = lire_sidecar(sc)
        out.append({'chemin': str(chemin), 'nom': titre or nom,
                    'nom_exporte': nom, 'octets': octets, 'quand': quand})
    return out


def index_du_nas(racines=None, parcours=None):
    """`nom minusculé -> [(chemin, octets)]`.

    Par NOM et non par chemin : le fonds est rangé par année, l'export par
    album ou par mois, et les deux arborescences n'ont aucune raison de se
    ressembler. C'est le nom qui traverse."""
    index = {}
    for r in (racines if racines is not None else F.racines()):
        for chemin, octets in (parcours or F.parcourir)(r):
            if octets is None:
                continue
            index.setdefault(os.path.basename(chemin).lower(), []).append(
                (str(chemin), octets))
    return index


def _sha256(chemin, morceau=1 << 20):
    h = hashlib.sha256()
    try:
        with open(chemin, 'rb') as f:
            while True:
                b = f.read(morceau)
                if not b:
                    break
                h.update(b)
    except OSError:
        return None
    return h.hexdigest()


def juger(media, index, empreinte=False):
    """Le verdict d'UNE photo. Rend (verdict, chemin_nas_ou_None, detail)."""
    candidats = index.get(media['nom'].lower())
    if not candidats and media['nom_exporte'] != media['nom']:
        # Le titre d'origine n'a rien donné : le nom exporté, à défaut.
        candidats = index.get(media['nom_exporte'].lower())
    if not candidats:
        return 'ABSENT', None, ''

    memes = [c for c in candidats if c[1] == media['octets']]
    if len(memes) == 1:
        chemin = memes[0][0]
        if empreinte:
            a, b = _sha256(media['chemin']), _sha256(chemin)
            if a is None or b is None:
                return 'AMBIGU', chemin, 'empreinte illisible'
            if a != b:
                return 'AMBIGU', chemin, 'meme taille, empreintes differentes'
        return 'CERTAIN', chemin, ''
    if len(memes) > 1:
        # Plusieurs fichiers identiques en nom ET en taille : le NAS la porte,
        # en double. C'est une CERTITUDE pour la question posée.
        return 'CERTAIN', memes[0][0], '%d copies sur le NAS' % len(memes)
    return ('PROBABLE', candidats[0][0],
            'taille %d chez Google, %d sur le NAS'
            % (media['octets'], candidats[0][1]))


def verifier(medias, index, empreinte=False):
    """Rend {verdict: [ligne, ...]}."""
    par_verdict = {}
    for m in medias:
        v, chemin, detail = juger(m, index, empreinte=empreinte)
        par_verdict.setdefault(v, []).append(
            {'nom': m['nom'], 'chemin_google': m['chemin'],
             'chemin_nas': chemin, 'octets': m['octets'], 'detail': detail})
    return par_verdict


def _go(octets):
    return octets / (1024.0 ** 3)


def rapport(par_verdict, empreinte=False, ecrire=print):
    """Dit ce qui est prouvé, ce qui ne l'est pas, et ce qu'on peut effacer."""
    n = {v: len(l) for v, l in par_verdict.items()}
    total = sum(n.values())
    octets_surs = sum(x['octets'] for x in par_verdict.get('CERTAIN', []))

    ecrire("")
    ecrire("=" * 74)
    ecrire("  GOOGLE PHOTOS vs LE NAS")
    ecrire("=" * 74)
    ecrire("  photos dans l export        : %d" % total)
    ecrire("  CERTAIN  (nom + taille)     : %d   %.1f Go"
           % (n.get('CERTAIN', 0), _go(octets_surs)))
    ecrire("  PROBABLE (taille differente): %d" % n.get('PROBABLE', 0))
    ecrire("  AMBIGU                      : %d" % n.get('AMBIGU', 0))
    ecrire("  ABSENT   (pas sur le NAS)   : %d" % n.get('ABSENT', 0))
    if not empreinte:
        ecrire("")
        ecrire("  Empreintes NON calculees : la taille tient lieu de preuve.")
        ecrire("  Relancer avec --empreinte pour comparer les octets.")

    for verdict, titre, quoi in (
            ('ABSENT', 'ABSENTES DU NAS', "a COPIER sur le NAS avant tout"),
            ('AMBIGU', 'AMBIGUES', "a regarder une par une"),
            ('PROBABLE', 'PROBABLES', "meme nom, taille differente")):
        lignes = par_verdict.get(verdict) or []
        if not lignes:
            continue
        ecrire("")
        ecrire("  %s (%d) — %s :" % (titre, len(lignes), quoi))
        for x in lignes[:LISTE_MAX]:
            ecrire("    %s%s" % (x['nom'],
                                 ("  [%s]" % x['detail']) if x['detail'] else ""))
        if len(lignes) > LISTE_MAX:
            ecrire("    ... et %d autre(s) non listees"
                   % (len(lignes) - LISTE_MAX))

    ecrire("")
    if n.get('ABSENT'):
        ecrire("  NE RIEN EFFACER CHEZ GOOGLE.")
        ecrire("  %d photo(s) n existent QUE la-bas. Les copier sur le NAS,"
               % n['ABSENT'])
        ecrire("  relancer cette verification, et seulement alors effacer.")
    elif total and n.get('CERTAIN') == total:
        ecrire("  TOUT est sur le NAS. Les %.1f Go peuvent etre liberes chez"
               % _go(octets_surs))
        ecrire("  Google — et le quota ne bouge qu une fois la CORBEILLE videe.")
    elif total:
        ecrire("  Ce qui est CERTAIN peut etre efface : %.1f Go."
               % _go(octets_surs))
        ecrire("  Le reste attend d etre tranche.")
    else:
        ecrire("  L export ne contient aucun media : mauvais dossier ?")
    ecrire("=" * 74)
    return {'total': total, 'compte': n, 'octets_surs': octets_surs,
            'empreinte': bool(empreinte), 'par_verdict': par_verdict}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--takeout', required=True,
                    help="le dossier « Google Photos » de l export Takeout")
    ap.add_argument('--empreinte', action='store_true',
                    help="comparer les octets (lent : lit tout le fonds)")
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    if not Path(a.takeout).is_dir():
        print("dossier introuvable : %s" % a.takeout)
        return 2
    print("  lecture de l export...")
    medias = inventaire_takeout(a.takeout)
    print("  %d media(s) dans l export ; index du NAS..." % len(medias))
    index = index_du_nas()
    print("  %d nom(s) distincts sur le NAS." % len(index))
    r = rapport(verifier(medias, index, empreinte=a.empreinte),
                empreinte=a.empreinte)
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        print("  liste ecrite : %s" % a.sortie_json)
    return 1 if r['compte'].get('ABSENT') else 0


if __name__ == '__main__':
    sys.exit(main())
