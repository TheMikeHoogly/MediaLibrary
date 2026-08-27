#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Les 9 017 « PROBABLE » sont-elles la MÊME image ?
──────────────────────────────────────────────────────────────────────────────

CE QUE LA MESURE DU 27/08 A RENVERSÉ

`verifier_photos_google.py` classe PROBABLE une photo de même nom et de taille
différente, avec une hypothèse écrite dans sa documentation : « Google a
probablement ré-encodé en mode économiseur de stockage ». Le premier passage
sur le vrai export dit le contraire, et il le dit fort :

    NAS plus gros : 8 741   ·   Google plus gros : 276
    ratio NAS/Google — médian 1,001, p10 1,000, p90 1,003
    PROBABLE : 8 996 `.jpg` · CERTAIN : 1 087 `.mp4`

Un ré-encodage « économiseur » divise le poids ; ici l'écart est de **quelques
kilo-octets, toujours du même côté**, et il ne touche QUE les JPEG. Les vidéos,
elles, tombent exactes au bit près. Or ce projet écrit ses noms
(`personne:Nom`, `animal:Nom`) dans les **XMP des fichiers**, à l'exiftool, et
seulement dans les images. L'hypothèse qui reste : **c'est la même photo, plus
la métadonnée que la photothèque y a écrite.**

« Il ne reste que cette hypothèse » n'est pas une preuve, et 75 Go chez un
tiers ne s'effacent pas sur une hypothèse. Cet instrument la transforme en
compte.

COMMENT — ET POURQUOI PAS UN sha256 DU FICHIER

Un sha256 du fichier entier dirait « différents » et n'apprendrait rien : on
SAIT que les octets diffèrent. Ce qu'on veut savoir, c'est si l'IMAGE est la
même. Un JPEG est une suite de segments ; la métadonnée vit dans les segments
`APPn` (EXIF, XMP, IPTC) et `COM`, jamais dans le flux compressé. On compare
donc :

  1. les TABLES et le CADRE — quantification (DQT), Huffman (DHT), dimensions
     et composantes (SOFn), redémarrage (DRI), en-tête de balayage (SOS).
     Deux JPEG ré-encodés n'ont jamais les mêmes tables ;
  2. la LONGUEUR du flux compressé — l'octet près ;
  3. avec `--octets`, le flux compressé lui-même, haché. C'est la preuve
     complète, et elle coûte la lecture du fonds : elle se prend par tranches
     (`--depuis`, `--limite`).

Et un contrôle qui vaut le reste : quand l'image est la même, **l'écart de
taille doit être exactement l'écart d'en-tête**. Si les deux nombres tombent
ensemble, tout ce qui diffère est AVANT le flux — c'est-à-dire la métadonnée.
S'ils divergent, l'explication est ailleurs et il faut la chercher.

CE QU'IL NE FAIT PAS

Il ne juge que les paires PROBABLE d'un rapport `verifier_photos_google.py
--json`. Il ne regarde ni les ABSENTES (rien à comparer) ni les CERTAINES
(déjà prouvées). Ce qui n'est pas un JPEG des deux côtés sort HORS PORTEE,
compté et dit — jamais rendu vert par défaut.

Il n'efface rien, nulle part : famille `verifier_`, lecture seule.

USAGE
    python verifier_google_pixels.py --rapport=_google.json
    python verifier_google_pixels.py --octets --limite=1500
    python verifier_google_pixels.py --octets --depuis=1500 --limite=1500

    Sortie 0 = toutes les paires jugées sont la même image.
    1 = au moins une paire diffère, ou la portée ne prouve rien.
"""

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

RAPPORT_DEFAUT = '_google.json'
LISTE_MAX = 25

# Marqueurs sans charge utile : ils ne portent pas de longueur.
SANS_CHARGE = {0xD8, 0xD9, 0x01} | set(range(0xD0, 0xD8))
# La MÉTADONNÉE : EXIF, XMP, IPTC, ICC, commentaires. Tout ce que ce projet
# écrit dans un fichier passe par là — et rien de ce qui fait l'image.
METADONNEE = set(range(0xE0, 0xF0)) | {0xFE}


def _marqueur(f):
    """Le prochain marqueur, ou None. Tolère le bourrage `0xFF`."""
    c = f.read(1)
    while c and c != b'\xff':
        c = f.read(1)                       # resynchronisation
    while c == b'\xff':
        c = f.read(1)
        if not c:
            return None
        if c != b'\xff':
            return c[0]
    return None


def fin_du_flux(f, taille, fenetre=1 << 16, plafond=1 << 25):
    """Position juste APRÈS le dernier `EOI` (FF D9), ou None.

    Cherche à reculons, par fenêtres élargies : dans un JPEG normal l'`EOI`
    est les deux derniers octets et la première fenêtre suffit. Ce qui vient
    APRÈS lui n'est pas l'image — un téléphone Samsung y colle sa
    « photo animée », d'autres y laissent une vignette ou un bloc XMP.

    Un `FF D9` ne peut pas apparaître par hasard dans le flux compressé (un
    `FF` de données y est doublé `FF 00`) ; il peut en revanche s'en trouver
    un DANS un trailer qui contient lui-même un JPEG. La recherche à reculons
    prendrait alors le mauvais — et le verdict sortirait FLUX_DIFFERENT,
    c'est-à-dire ROUGE. L'erreur possible va du côté prudent."""
    while True:
        debut = max(0, taille - fenetre)
        f.seek(debut)
        bloc = f.read(taille - debut)
        i = bloc.rfind(b'\xff\xd9')
        if i >= 0:
            return debut + i + 2
        if debut == 0 or fenetre >= plafond:
            return None
        fenetre *= 8


def signature_jpeg(chemin):
    """(empreinte des tables et du cadre, début du flux, longueur du flux,
    longueur du TRAILER).

    Le trailer est ce qui suit l'`EOI` : compté à part depuis le 27/08, parce
    que le confondre avec le flux a fait sortir **173 photos** en
    « flux différent » alors qu'elles portaient toutes, côté Google, des
    octets APRÈS le JPEG — médiane 2 046, exactement l'écart mesuré. Un
    instrument qui range un trailer dans l'image ne mesure pas ce qu'il dit.

    None si ce n'est pas un JPEG lisible — un `.gif`, un `.mp4`, un fichier
    tronqué. L'appelant en fait un HORS PORTEE, jamais un vert."""
    try:
        with open(chemin, 'rb') as f:
            taille = os.fstat(f.fileno()).st_size
            if f.read(2) != b'\xff\xd8':
                return None
            h = hashlib.sha256()
            while True:
                m = _marqueur(f)
                if m is None:
                    return None
                if m in SANS_CHARGE:
                    continue
                brut = f.read(2)
                if len(brut) < 2:
                    return None
                n = (brut[0] << 8 | brut[1]) - 2
                if n < 0:
                    return None
                if m == 0xDA:                       # SOS : le flux suit
                    h.update(bytes([m]))
                    h.update(f.read(n))
                    debut = f.tell()
                    fin = fin_du_flux(f, taille)
                    if fin is None or fin <= debut:
                        return None                 # pas d'EOI : tronque
                    return h.hexdigest(), debut, fin - debut, taille - fin
                if m in METADONNEE:
                    f.seek(n, 1)                    # sautée, jamais hachée
                else:
                    h.update(bytes([m]))
                    h.update(f.read(n))
    except OSError:
        return None


def empreinte_du_flux(chemin, debut, longueur, morceau=1 << 20):
    """sha256 du flux compressé SEUL. None si la lecture échoue."""
    h = hashlib.sha256()
    reste = longueur
    try:
        with open(chemin, 'rb') as f:
            f.seek(debut)
            while reste > 0:
                bloc = f.read(min(morceau, reste))
                if not bloc:
                    return None
                h.update(bloc)
                reste -= len(bloc)
    except OSError:
        return None
    return h.hexdigest()


def juger_paire(google, nas, octets=False):
    """(verdict, detail) pour UNE paire.

    MEME_IMAGE · MEME_IMAGE_TRAILER · FLUX_DIFFERENT · IMAGE_DIFFERENTE ·
    HORS_PORTEE.

    `MEME_IMAGE_TRAILER` : même image, mais l'un des deux porte des octets de
    plus APRÈS le JPEG. Ce n'est pas rien — une « photo animée » de téléphone
    vit là — donc ce n'est pas vert : c'est nommé, compté, et laissé au
    jugement.
    """
    sg, sn = signature_jpeg(google), signature_jpeg(nas)
    if sg is None or sn is None:
        quoi = ('les deux' if sg is None and sn is None
                else ('Google' if sg is None else 'le NAS'))
        return 'HORS_PORTEE', 'pas un JPEG lisible : %s' % quoi
    if sg[0] != sn[0]:
        return 'IMAGE_DIFFERENTE', 'tables ou cadre differents (re-encodage)'
    if sg[2] != sn[2]:
        return ('FLUX_DIFFERENT',
                'meme cadre, flux de %d octets chez Google et %d sur le NAS'
                % (sg[2], sn[2]))
    if octets:
        eg = empreinte_du_flux(google, sg[1], sg[2])
        en = empreinte_du_flux(nas, sn[1], sn[2])
        if eg is None or en is None:
            return 'HORS_PORTEE', 'flux illisible'
        if eg != en:
            return 'FLUX_DIFFERENT', 'meme longueur, octets differents'
    if sg[3] != sn[3]:
        return ('MEME_IMAGE_TRAILER',
                'meme image ; apres le JPEG : %d octets chez Google, %d sur '
                'le NAS' % (sg[3], sn[3]))
    # L'écart de TAILLE doit être exactement l'écart d'EN-TÊTE : alors tout ce
    # qui diffère est avant le flux, donc de la métadonnée.
    ecart_entete = sn[1] - sg[1]
    return 'MEME_IMAGE', ('flux identique a l octet pres' if octets
                          else 'meme cadre, meme longueur, en-tete +%d'
                          % ecart_entete)


def paires_probables(rapport):
    """Les paires PROBABLE d'un rapport `verifier_photos_google --json`."""
    d = json.loads(Path(rapport).read_text(encoding='utf-8'))
    return [x for x in (d.get('par_verdict', {}).get('PROBABLE') or [])
            if x.get('chemin_google') and x.get('chemin_nas')]


def mesurer(paires, octets=False, ecrire=print, chaque=500):
    """Rend (compte, exemples, ecarts, restantes).

    `exemples` : ce que la CONSOLE montre, borné. `restantes` : la liste
    COMPLÈTE de ce qui n'est pas la même image — c'est elle qui sert à
    quelque chose. Un compte dit qu'il reste 215 photos à regarder ; seule la
    liste dit LESQUELLES, et sans elle personne ne peut agir."""
    compte, exemples, ecarts, restantes = {}, {}, [], []
    t0 = time.time()
    for i, x in enumerate(paires, 1):
        v, detail = juger_paire(x['chemin_google'], x['chemin_nas'],
                                octets=octets)
        compte[v] = compte.get(v, 0) + 1
        if v != 'MEME_IMAGE':
            restantes.append({'nom': x['nom'], 'verdict': v, 'detail': detail,
                              'chemin_google': x['chemin_google'],
                              'chemin_nas': x['chemin_nas']})
            if len(exemples.setdefault(v, [])) < LISTE_MAX:
                exemples[v].append('%s  [%s]' % (x['nom'], detail))
        if v == 'MEME_IMAGE':
            try:
                ecarts.append(os.path.getsize(x['chemin_nas'])
                              - os.path.getsize(x['chemin_google']))
            except OSError:
                pass
        if chaque and i % chaque == 0:
            ecrire("    %d / %d  (%.0f s)" % (i, len(paires), time.time() - t0))
    return compte, exemples, ecarts, restantes


def rapport(compte, exemples, ecarts, total_probables, juges, octets,
            ecrire=print):
    """True si toutes les paires JUGÉES sont la même image, et qu'il y en a."""
    ecrire("")
    ecrire("=" * 74)
    ecrire("  LES PROBABLE SONT-ELLES LA MEME IMAGE ?")
    ecrire("=" * 74)
    ecrire("  paires PROBABLE du rapport : %d" % total_probables)
    ecrire("  paires jugees ici          : %d" % juges)
    ecrire("  preuve                     : %s"
           % ("flux compresse HACHE (octet pres)" if octets
              else "tables, cadre et LONGUEUR du flux"))
    ecrire("")
    for v in ('MEME_IMAGE', 'MEME_IMAGE_TRAILER', 'FLUX_DIFFERENT',
              'IMAGE_DIFFERENTE', 'HORS_PORTEE'):
        ecrire("  %-18s : %d" % (v, compte.get(v, 0)))
    if ecarts:
        ecrire("")
        ecrire("  Ecart de taille NAS moins Google, sur les MEME_IMAGE :")
        ecrire("    median %d o, min %d, max %d"
               % (statistics.median(ecarts), min(ecarts), max(ecarts)))
        ecrire("    C'est de la METADONNEE : l image, elle, est la meme.")
    for v in ('IMAGE_DIFFERENTE', 'FLUX_DIFFERENT', 'MEME_IMAGE_TRAILER',
              'HORS_PORTEE'):
        lignes = exemples.get(v) or []
        if not lignes:
            continue
        ecrire("")
        ecrire("  %s — %d liste(s) :" % (v, len(lignes)))
        for l in lignes:
            ecrire("    %s" % l[:70])
        if compte.get(v, 0) > len(lignes):
            ecrire("    ... et %d autre(s), non listes mais COMPTES"
                   % (compte[v] - len(lignes)))

    ecrire("")
    if not juges:
        ecrire("  AUCUNE paire jugee : ce rapport ne prouve rien.")
        ecrire("=" * 74)
        return False
    propre = (compte.get('MEME_IMAGE', 0) == juges)
    if propre and juges == total_probables:
        ecrire("  TOUTES les PROBABLE sont la meme image. L hypothese du")
        ecrire("  re-encodage Google est FAUSSE : c est la metadonnee que la")
        ecrire("  photothèque a ecrite dans SES fichiers.")
        ecrire("  Ce qui reste a trancher : les ABSENTES.")
    elif propre:
        ecrire("  Les %d paires jugees sont la meme image — mais %d ne l ont"
               % (juges, total_probables - juges))
        ecrire("  PAS ete. Une tranche ne conclut pas sur le tout : relancer")
        ecrire("  avec --depuis pour la suivante.")
    else:
        ecrire("  DES PAIRES DIFFERENT. Ne rien effacer sur ce rapport.")
    ecrire("=" * 74)
    return propre and juges == total_probables


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Les PROBABLE sont-elles la meme image ?")
    ap.add_argument('--rapport', default=RAPPORT_DEFAUT)
    # RÉPÉTABLE, et pas une liste séparée par des virgules : le canal du
    # banc n'admet que [A-Za-z0-9_.:/=-] — une virgule y est refusée, et un
    # argument que le canal refuse est un argument qui n'existe pas.
    ap.add_argument('--reprendre', action='append', default=None,
                    help='ne juger que les « restantes » de CE rapport ; '
                         'répéter l option pour plusieurs — re-juger avec '
                         'une preuve plus fine sans relire le fonds')
    ap.add_argument('--octets', action='store_true',
                    help="hacher le flux compresse (LENT : lit le fonds)")
    ap.add_argument('--depuis', type=int, default=0)
    ap.add_argument('--limite', type=int, default=0)
    ap.add_argument('--json', dest='sortie_json', default=None)
    a = ap.parse_args(argv)

    if not a.reprendre and not Path(a.rapport).is_file():
        print("rapport introuvable : %s" % a.rapport)
        print("(le produire : verifier_photos_google.py --takeout ... --json)")
        return 2
    if a.reprendre:
        toutes = []
        for nom in a.reprendre:
            d = json.loads(Path(nom.strip()).read_text(encoding='utf-8'))
            toutes += (d.get('restantes') or [])
    else:
        toutes = paires_probables(a.rapport)
    tranche = toutes[a.depuis:]
    if a.limite:
        tranche = tranche[:a.limite]
    print("  %d paire(s) PROBABLE ; %d jugee(s) ici." % (len(toutes),
                                                         len(tranche)))
    compte, exemples, ecarts, restantes = mesurer(tranche,
                                                  octets=a.octets)
    ok = rapport(compte, exemples, ecarts, len(toutes), len(tranche),
                 a.octets)
    if a.sortie_json:
        Path(a.sortie_json).write_text(json.dumps(
            {'rapport': a.rapport, 'octets': a.octets, 'depuis': a.depuis,
             'limite': a.limite, 'total_probables': len(toutes),
             'juges': len(tranche), 'compte': compte, 'exemples': exemples,
             # La liste COMPLETE de ce qui reste a regarder : le compte dit
             # combien, la liste dit lesquelles. Sans elle, un rapport se
             # lit et ne s'utilise pas.
             'restantes': restantes,
             'ecart_median': statistics.median(ecarts) if ecarts else None,
             'ecart_min': min(ecarts) if ecarts else None,
             'ecart_max': max(ecarts) if ecarts else None,
             'ok': ok}, indent=2, ensure_ascii=False), encoding='utf-8')
        print("  rapport JSON : %s" % a.sortie_json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
