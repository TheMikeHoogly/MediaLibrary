#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — combien de MOTION PHOTOS dans le fonds, et combien d'octets a reprendre
────────────────────────────────────────────────────────────────────────────────

Regle du projet (eval/DECISIONS.md, 29/08) : une Motion Photo ne garde que son
IMAGE ; la video embarquee (trailer Samsung `SEFT` / `MotionPhoto` Google) est
jetee — deliberement, par un outil dedie, reversiblement. La ROADMAP (1 septies)
exige de COMPTER AVANT le strip : ce banc est ce compte. Il ne modifie RIEN.

CANDIDATS : les cles `.jpg`/`.jpeg` de la COPIE de la base (jamais `photos.db`),
dossiers caches (`.`, `@`, `#`) exclus. Le Takeout `C:\\GOOGLE PHOTOS` n'est pas
dans l'index : hors perimetre par construction.

DETECTION, deux lectures LEGERES par fichier (SMB oblige) :
  - TETE (256 Ko) : le XMP Google — `MotionPhoto=1` / `MicroVideo=1` — et,
    quand il la donne, la TAILLE exacte de la video (`MicroVideoOffset`, ou
    l'`Item:Length` du `video/mp4` dans le Container v2) ;
  - QUEUE (64 Ko) : le marqueur Samsung `SEFT` (le trailer SEF finit par lui).
Un fichier detecte SANS taille XMP passe par une FENETRE de queue (8 Mo par
defaut) : premier `ftyp` (debut du MP4), remonte au `FF D9` (fin du still) —
comme `verifier_strip_motionphoto.offset_video`, sans lire le fichier entier.

REPRENABLE : cache par fichier (re-sonder un fichier MODIFIE = supprimer
le rapport) dans `docs/motion_photos.json` —
le canal du banc tue a 600 s, relancer jusqu'a « TERMINE ». `--pause-s` menage
la machine (surchauffe du 30-31/08).

    mesure_motion_photos.py --base copie.db [--budget-s 450] [--pause-s 0.05]
                            [--limite N] [--fenetre-mo 8] [--exemples 10]
"""
import argparse
import json
import concurrent.futures as cf
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'motion_photos.json'
VERSION = 1  # une detection qui change invalide le cache

TETE_O = 256 * 1024
QUEUE_O = 64 * 1024

# Le XMP declare la Motion Photo en attribut (`MotionPhoto="1"`) ou en element
# (`>1<`). Les deux formes existent dans le fonds ; ne parier sur aucune.
RX_MOTION = re.compile(rb'(?:GCamera:)?MotionPhoto\s*(?:=\s*["\']1["\']|>\s*1\s*<)')
RX_MICRO = re.compile(rb'(?:GCamera:)?MicroVideo\s*(?:=\s*["\']1["\']|>\s*1\s*<)')
RX_MICRO_OFF = re.compile(rb'MicroVideoOffset\s*(?:=\s*["\'](\d+)["\']|>\s*(\d+)\s*<)')
RX_ITEM = re.compile(rb'Item:(Mime|Length)\s*=\s*["\']([^"\']+)["\']')


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def nk(p):
    return os.path.normcase(os.path.normpath(str(p)))


def est_cache(cle):
    return any(part.startswith(('.', '@', '#'))
               for part in str(cle).replace('\\', '/').split('/'))


def proprietaire(cle):
    for seg in str(cle).replace('\\', '/').split('/'):
        m = re.match(r'^photos\s+(\S.*)$', seg.strip(), re.I)
        if m:
            return m.group(1).strip()
    return None


def annee_de(cle):
    m = re.search(r'[\\/]((?:19|20)\d\d)[\\/]', str(cle))
    if m:
        return m.group(1)
    nom = str(cle).replace('\\', '/').rsplit('/', 1)[-1]
    m = re.match(r'((?:19|20)\d\d)\D', nom)
    return m.group(1) if m else '????'


def genre_effectif(ent):
    """Le genre au moment du COMPTE : un `SEFT` sans mp4 trouve n'est pas une
    Motion Photo — c'est un trailer SEF de metadonnees Samsung (568 vus chez
    Flo, 2017). On le compte a part, sans re-sonder le fonds."""
    g = ent.get('g')
    if g == 'samsung' and not ent.get('v'):
        return 'sef-sans-video'
    return g


def taille_video_xmp(tete):
    """Octets de video d'apres le XMP de la TETE, ou None.

    v1 : `MicroVideoOffset` = octets entre la fin du still et la fin du
    fichier — c'est la taille du trailer. v2 : dans le Container:Directory,
    l'`Item:Length` de l'item `video/mp4` (le still, lui, a Length 0)."""
    m = RX_MICRO_OFF.search(tete)
    if m:
        try:
            v = int(m.group(1) or m.group(2))
            if v > 0:
                return v
        except ValueError:
            pass
    mime_vu = False
    for cle, val in RX_ITEM.findall(tete):
        if cle == b'Mime':
            mime_vu = val.strip().lower() == b'video/mp4'
        elif cle == b'Length' and mime_vu:
            try:
                v = int(val)
                if v > 0:
                    return v
            except ValueError:
                pass
            mime_vu = False
    return None


def detecter(tete, queue):
    """('samsung'|'google'|'les-deux'|None, taille video XMP ou None)."""
    samsung = b'SEFT' in queue
    google = bool(RX_MOTION.search(tete) or RX_MICRO.search(tete))
    genre = ('les-deux' if samsung and google
             else 'samsung' if samsung else 'google' if google else None)
    return genre, (taille_video_xmp(tete) if google else None)


def _ftyp_plausible(fen, i):
    """`ftyp` a l'octet `i` : est-ce une VRAIE boite MP4 ? Quatre octets de
    ftyp tombent aussi dans les donnees compressees d'un JPEG (vu 3 fois sur
    les 3 premieres Motion reelles : video estimee = 100 % du fichier). Une
    vraie boite a une TAILLE big-endian plausible juste avant, et un BRAND
    lisible juste apres (mp42, isom, avc1...)."""
    if i < 4:
        return False
    t = int.from_bytes(fen[i - 4:i], 'big')
    brand = fen[i + 4:i + 8]
    return (16 <= t <= (1 << 20) and len(brand) == 4
            and all(48 <= b <= 122 and (b <= 57 or 97 <= b or 65 <= b <= 90) or b == 32
                    for b in brand))


def taille_video_fenetre(fen, base, taille):
    """Octets du trailer d'apres une FENETRE de queue (`fen` lue depuis l'octet
    `base` d'un fichier de `taille` octets), ou None si aucune boite `ftyp`
    PLAUSIBLE dedans.

    Premiere boite `ftyp` plausible = debut du MP4 (elle commence 4 octets
    avant le mot) ; le `FF D9` qui la precede est la fin du still : le trailer
    commence apres."""
    i = -1
    while True:
        i = fen.find(b'ftyp', i + 1)
        if i < 0:
            return None
        if _ftyp_plausible(fen, i):
            break
    debut_boite = base + i - 4
    j = fen.rfind(b'\xff\xd9', 0, i - 4)
    debut_trailer = base + j + 2 if j >= 0 else debut_boite
    return taille - debut_trailer


def sonder(chemin, fenetre_o):
    """Une entree de cache pour `chemin`, sans jamais lire le fichier entier."""
    st = os.stat(chemin)
    taille = st.st_size
    with open(chemin, 'rb') as f:
        tete = f.read(min(TETE_O, taille))
        if taille > len(tete):
            f.seek(max(len(tete), taille - QUEUE_O))
            queue = f.read()
        else:
            queue = tete
        genre, video_o = detecter(tete, queue)
        methode = 'xmp' if video_o else None
        if genre and video_o is None:
            if (genre == 'samsung' and b'SEFH' in queue
                    and b'MotionPhoto_Data' not in queue):
                pass  # l'annuaire SEF est la, sans bloc video : rien a lire
            else:
                base = max(0, taille - fenetre_o)
                f.seek(base)
                video_o = taille_video_fenetre(f.read(), base, taille)
                methode = 'fenetre' if video_o else None
        suspect = (genre is None and queue[-2:] != b'\xff\xd9'
                   and b'ftyp' in queue)
    ent = {'t': taille, 'm': int(st.st_mtime), 'g': genre}
    if video_o:
        ent['v'] = int(video_o)
        ent['me'] = methode
        if methode == 'fenetre':
            ent['fv'] = 2  # version du durcissement ftyp
    if suspect:
        ent['s'] = 1
    return ent


def charger_cles(base):
    import sqlite3
    if Path(base).name == 'photos.db':
        print('REFUS : ce banc lit une COPIE (mesure_copie_base.py), jamais photos.db')
        sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    cles = []
    for (k,) in cx.execute('SELECT k FROM tags'):
        if str(k).lower().endswith(('.jpg', '.jpeg')) and not est_cache(k):
            cles.append(str(k))
    cx.close()
    return sorted(cles)


def charger_cache():
    try:
        d = json.loads(RAPPORT.read_text(encoding='utf-8'))
        if d.get('version') == VERSION and isinstance(d.get('fichiers'), dict):
            return {k: e for k, e in d['fichiers'].items()
                    if not (isinstance(e, dict) and e.get('me') == 'fenetre'
                            and e.get('fv') != 2)}
    except (OSError, ValueError):
        pass
    return {}


def ecrire_cache(fichiers, resume):
    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = RAPPORT.with_suffix('.tmp')
    tmp.write_text(json.dumps({'version': VERSION, 'quand': time.strftime('%Y-%m-%d %H:%M:%S'),
                               'resume': resume, 'fichiers': fichiers},
                              ensure_ascii=True, indent=0), encoding='utf-8')
    os.replace(tmp, RAPPORT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[2])
    ap.add_argument('--base', required=True)
    ap.add_argument('--budget-s', type=float, default=450.0)
    ap.add_argument('--pause-s', type=float, default=0.0)
    ap.add_argument('--limite', type=int, default=0, help='0 = tout')
    ap.add_argument('--fenetre-mo', type=int, default=8)
    ap.add_argument('--exemples', type=int, default=10)
    ap.add_argument('--fils', type=int, default=1)
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    fenetre_o = a.fenetre_mo * (1 << 20)

    cles = charger_cles(a.base)
    print('candidats JPEG (copie de la base) : %d' % len(cles), flush=True)
    fichiers = charger_cache()
    if fichiers:
        print('cache : %d entrees reprises (%s)' % (len(fichiers), RAPPORT.name), flush=True)

    a_faire = [c for c in cles if fichiers.get(nk(c)) is None]
    faits, absents, erreurs = 0, 0, 0
    interrompu = False

    def une(cle):
        if a.pause_s:
            time.sleep(a.pause_s)
        try:
            return cle, sonder(cle, fenetre_o)
        except FileNotFoundError:
            return cle, None  # pas mis en cache : le fichier peut revenir
        except OSError as e:
            # CACHE : une erreur persistante ne doit pas interdire TERMINE ;
            # supprimer le rapport re-sonde tout.
            return cle, {'err': asc(e), 'nom': asc(Path(cle).name)}

    it = iter(a_faire)
    with cf.ThreadPoolExecutor(max_workers=max(1, a.fils)) as ex:
        encours = {ex.submit(une, c) for _, c in zip(range(a.fils * 2), it)}
        while encours:
            fini, encours = cf.wait(encours, return_when=cf.FIRST_COMPLETED)
            for fut in fini:
                cle, ent = fut.result()
                if ent is None:
                    absents += 1
                    continue
                fichiers[nk(cle)] = ent
                if 'err' in ent:
                    erreurs += 1
                    if erreurs <= 8:
                        print('  erreur %s : %s' % (ent['nom'], ent['err']), flush=True)
                    continue
                faits += 1
                if faits % 500 == 0:
                    print('  ... %d sondes cette passe (%.0f s)' % (faits, time.monotonic() - t0), flush=True)
            if time.monotonic() - t0 > a.budget_s or (a.limite and faits >= a.limite):
                interrompu = True
                for fut in encours:
                    fut.cancel()
                cf.wait(encours)
                encours = set()
                continue
            for _, c in zip(range(len(fini)), it):
                encours.add(ex.submit(une, c))

    # ── le compte, sur tout ce que le cache sait ────────────────────────────
    vus = {nk(c): c for c in cles}
    genres = Counter()
    octets_video, octets_fichiers, sans_taille, suspects = 0, 0, 0, 0
    par_prop = defaultdict(lambda: [0, 0])
    par_annee = defaultdict(lambda: [0, 0])
    exemples = []
    couverts = 0
    en_erreur = 0
    for k, ent in fichiers.items():
        cle = vus.get(k)
        if cle is None:
            continue  # entree d'un fichier sorti de l'index
        couverts += 1
        if 'err' in ent:
            en_erreur += 1
            continue
        if ent.get('s'):
            suspects += 1
        g = genre_effectif(ent)
        if not g:
            continue
        genres[g] += 1
        if g == 'sef-sans-video':
            continue  # compte a part : pas une Motion Photo
        octets_fichiers += ent.get('t', 0)
        v = ent.get('v', 0)
        if v:
            octets_video += v
        else:
            sans_taille += 1
        p = proprietaire(cle) or '(hors Photos X)'
        par_prop[p][0] += 1
        par_prop[p][1] += v
        an = annee_de(cle)
        par_annee[an][0] += 1
        par_annee[an][1] += v
        if len(exemples) < a.exemples:
            exemples.append('%s  %s  %.1f Mo dont video %.1f Mo (%s)'
                            % (g, asc(Path(cle).name), ent.get('t', 0) / 1048576.0,
                               v / 1048576.0, ent.get('me') or 'taille inconnue'))

    n_motion = sum(n for g, n in genres.items() if g != 'sef-sans-video')
    resume = {'candidats': len(cles), 'couverts': couverts,
              'motion': n_motion, 'genres': dict(genres),
              'octets_video': octets_video, 'octets_fichiers': octets_fichiers,
              'sans_taille': sans_taille, 'suspects': suspects,
              'termine': not interrompu}
    ecrire_cache(fichiers, resume)

    print('=' * 74, flush=True)
    print('sondes cette passe : %d  (absents %d, erreurs %d)' % (faits, absents, erreurs))
    print('couverture : %d / %d candidats (dont %d en erreur, cachees)'
          % (couverts, len(cles), en_erreur))
    print('MOTION PHOTOS : %d' % n_motion)
    for g in sorted(genres):
        print('  %-9s %d' % (g, genres[g]))
    print('octets de VIDEO a reprendre : %.2f Go (%d fichiers sans taille estimee)'
          % (octets_video / 1073741824.0, sans_taille))
    print('poids total des fichiers touches : %.2f Go' % (octets_fichiers / 1073741824.0))
    if suspects:
        print('suspects (queue sans FFD9 + ftyp, non declares) : %d -- a regarder' % suspects)
    if par_prop:
        print('par proprietaire :')
        for p in sorted(par_prop, key=lambda x: -par_prop[x][0]):
            n, v = par_prop[p]
            print('  %-24s %5d  %.2f Go' % (asc(p)[:24], n, v / 1073741824.0))
        print('par annee :')
        for an in sorted(par_annee):
            n, v = par_annee[an]
            print('  %s  %5d  %.2f Go' % (an, n, v / 1073741824.0))
    if exemples:
        print('exemples :')
        for e in exemples:
            print('  ' + e)
    print('rapport : docs/motion_photos.json')
    if interrompu:
        print('PASSE INTERROMPUE (budget/limite) -- cache ecrit, RELANCER le meme ordre')
    else:
        print('TERMINE -- le fonds est couvert')
    return 0


if __name__ == '__main__':
    sys.exit(main())
