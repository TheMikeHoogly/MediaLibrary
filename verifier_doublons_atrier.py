#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Doublons de `_A TRIER` DEJA RANGES dans le fonds — par IMAGE, pas par octet.

Un fichier de `_A TRIER` dont l'image (pixels) existe deja dans le fonds
(`Photos <Nom>\\<annee>`) est un doublon a retirer : la copie du fonds est la
canonique. On matche par `exiftool -ImageDataHash` (les pixels seuls), pas par
sha256 : deux copies de la meme photo different de quelques centaines d'octets
de tags, donc un sha256 dirait « pas doublon » a tort.

LECTURE SEULE. N'ecrit que ses rapports (`docs/doublons_atrier.{json,md}`), ne
touche ni un fichier photo, ni `photos.db`, ni le NAS. Sortie ASCII.

Preserve la regle « aucun nom perdu » : si `--db` est donne, une copie a
retirer qui porte un `personne:`/`animal:` ABSENT de la canonique est marquee
REVUE et EXCLUE du retrait automatique (a fusionner d'abord, cf. appliquer_plan).

    # cible (rapide, pour un premier chiffre) :
    verifier_doublons_atrier.py --atrier b64:<dossier _A TRIER> --fonds b64:<dossier fonds>
    # complet (lit la config, tout le fonds vs tout _A TRIER) :
    verifier_doublons_atrier.py [--db b64:<copie de photos.db>]
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import rangement_annee as _ra                                   # noqa: E402

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif',
             '.bmp', '.tiff', '.tif'}
# Les VIDEOS etaient invisibles a cet outil : `ImageDataHash` ne lit que des
# pixels, donc les 19 doublons video de la racine de `_A TRIER` etaient
# INCREVABLES -- ils y resteraient tant que personne ne les efface a la main
# (ROADMAP A7). Qualifies a la main le 13/09 : 14 ont la meme taille que leur
# homonyme du fonds, tete et milieu identiques, seule la remorque de
# metadonnees differe ; les 5 autres ont le fonds PLUS LONG (+4 ms a +1,43 s),
# meme codec, meme resolution -- la copie d'`_A TRIER` est tronquee.
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.mts', '.wmv'}

# Un Mo lu au DEBUT et un Mo au MILIEU. Deux copies d'une meme video partagent
# leur flux et different par la remorque : comparer le fichier ENTIER dirait
# « pas doublon » a tort, exactement comme sha256 le dit des images. Et lire
# 2 Mo par fichier sur SMB reste un cout tenable, la ou un hash complet de
# 4 Go ne l'est pas.
BLOC = 1 << 20
# La regle de « qu'est-ce qu'un _A TRIER » et celle de « qu'est-ce qu'une
# salle d'arbitrage » viennent de `rangement_annee` -- le meme module que le
# plan d'annee. Elles etaient recopiees ici, et c'est exactement le genre de
# copie qui finit par diverger : le 13/09 cet outil a tranche tout seul
# l'arbitrage de 68 photos que le bat 33 avait mises a part, parce que pour
# lui `Google porte mieux` n'etait qu'un sous-dossier de `_A TRIER` de plus.
ATRI_RE = _ra.ATRI_RE


def deb64(v):
    return base64.urlsafe_b64decode(v[4:] + '=' * (-len(v[4:]) % 4)).decode('utf-8') if str(v).startswith('b64:') else v


def exiftool():
    for c in sorted(ICI.glob('exiftool*')):
        p = c / 'exiftool.exe' if c.is_dir() else c
        if p.name.lower() == 'exiftool.exe' and p.exists():
            return p
    return None


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def _read_config_lines(name):
    out = []
    try:
        for line in (ICI / name).read_text(encoding='utf-8').splitlines():
            line = line.strip().strip('"')
            if line and not line.startswith('#'):
                out.append(line)
    except OSError:
        pass
    return out


def racines_config():
    """Racines du fonds, depuis la meme config que le serveur."""
    out = []
    for name in ('dossiers_a_taguer.txt', 'dossier_uploads.txt'):
        for l in _read_config_lines(name):
            if l not in out:
                out.append(l)
    return out


def est_atri(chemin):
    return any(ATRI_RE.match(str(p).strip()) for p in Path(chemin).parts)


def enum_media(dossier):
    """(chemins media sous `dossier`, recursif, hors caches)."""
    out = []
    for r, dirs, files in os.walk(dossier):
        dirs[:] = [d for d in dirs if not d[:1] in ('.', '@', '#')]
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXT:
                out.append(os.path.join(r, f))
    return out


def exiftool_json(exe, options, chemins, log=lambda *_: None):
    """exiftool sur un lot, par FICHIER D'ARGUMENTS. Rend la liste JSON.

    POURQUOI UN FICHIER D'ARGUMENTS, ET PAS LA LIGNE DE COMMANDE

    Un chemin accentue passe en ligne de commande arrive MUTILE chez exiftool,
    qui repond « File not found » et n'est PAS compte comme une erreur : le
    lot rend simplement une entree de moins, et l'appelant lit un dictionnaire
    ou le fichier manque. MESURE le 14/09 sur
    `Photos Flo\2016 Indonesie\Voyage Indonesie (2).mp4` : Python voit le
    fichier (`exists()` vrai), exiftool repond
    « Error: File not found - .../Voyage Indon?sie (2).mp4 » -- l'accent est
    tombe en route, code 1, stdout vide.

    La consequence etait muette et elle depassait les videos : sans hash, une
    photo accentuee ne trouve jamais sa canonique et tombe dans
    `homonymes_differents`, la liste que `--homonymes-differents` peut
    RETIRER. Un fichier qu'on n'a pas su comparer s'y donnait pour un fichier
    compare et juge different.

    `-@ <fichier>` avec `-charset filename=UTF8` : exiftool lit le fichier en
    UTF-8, la ligne de commande ne porte plus aucun chemin."""
    lignes = list(options) + ['-charset', 'filename=UTF8'] \
        + [str(p) for p in chemins]
    fd, argfile = tempfile.mkstemp(suffix='.args', text=False)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lignes) + '\n')
        r = subprocess.run([str(exe), '-@', argfile], capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=600)
        manque = [l for l in (r.stderr or '').splitlines()
                  if 'File not found' in l]
        if manque:
            # Ne JAMAIS avaler ce cas : c'est celui qui etait muet.
            log('  exiftool : %d fichier(s) INTROUVABLE(S), ex. %s'
                % (len(manque), asc(manque[0][:120])))
        sortie = json.loads(r.stdout or '[]')
        # Un fichier lu mais ILLISIBLE (« File format error ») n'est pas non
        # plus un silence acceptable : sans duree ni empreinte, il ne sera
        # jamais compare, et personne ne saurait pourquoi. Trouve le 14/09 :
        # `Voyage Indonesie (2).mp4`, 42 Mio ronds, transfert tronque.
        casses = [i for i in sortie if isinstance(i, dict) and i.get('Error')]
        if casses:
            log('  exiftool : %d fichier(s) ILLISIBLE(S), ex. %s -- %s'
                % (len(casses), asc(os.path.basename(casses[0].get(
                    'SourceFile', '?'))), asc(casses[0]['Error'])))
        return sortie
    finally:
        try:
            os.unlink(argfile)
        except OSError:
            pass


def image_hashes(exe, chemins, log=lambda *_: None):
    """{chemin -> ImageDataHash} par lots exiftool (les pixels seuls)."""
    res = {}
    CH = 80
    for i in range(0, len(chemins), CH):
        lot = chemins[i:i + CH]
        try:
            for item in exiftool_json(
                    exe, ['-api', 'RequestAll=3', '-ImageDataHash', '-s3',
                          '-q', '-q', '-j'], lot, log):
                sf = item.get('SourceFile', '')
                h = item.get('ImageDataHash')
                if sf and h:
                    res[os.path.normcase(os.path.normpath(sf))] = h
        except Exception as e:  # noqa: BLE001
            log('  lot hash en erreur (%d..): %s' % (i, str(e)[:80]))
        log('  hash %d/%d' % (min(i + CH, len(chemins)), len(chemins)))
    # Un fichier sans hash n'est PAS un fichier « a image differente » : il
    # n'a pas ete compare. L'appelant doit pouvoir faire la difference.
    absents = [p for p in chemins if hkey(p) not in res]
    if absents:
        log('  %d fichier(s) SANS empreinte (non compares), ex. %s'
            % (len(absents), asc(os.path.basename(absents[0]))))
    return res


def load_names(db_copy):
    import sqlite3
    out = {}
    try:
        cx = sqlite3.connect(str(db_copy))
        for k, v in cx.execute("SELECT k, v FROM tags"):
            try:
                e = json.loads(v)
            except Exception:
                continue
            noms = [t for fld in ('kw_fr', 'kw_en') for t in (e.get(fld) or [])
                    if isinstance(t, str) and (t.startswith('personne:') or t.startswith('animal:'))]
            if noms:
                out[os.path.normcase(os.path.normpath(k))] = set(noms)
        cx.close()
    except Exception as e:  # noqa: BLE001
        print('  (index illisible, controle des noms desactive : %s)' % str(e)[:80])
    return out


def hkey(p):
    return os.path.normcase(os.path.normpath(str(p)))


def enum_videos(dossier):
    """(chemins VIDEO sous `dossier`, recursif, hors caches)."""
    out = []
    for r, dirs, files in os.walk(dossier):
        dirs[:] = [d for d in dirs if not d[:1] in ('.', '@', '#')]
        for f in files:
            if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                out.append(os.path.join(r, f))
    return out


def empreinte_flux(chemin):
    """(taille, sha256 du debut + du milieu) d'un fichier, ou None.

    Ce n'est PAS une empreinte du contenu entier, et c'est voulu : elle doit
    rester la meme quand seule la remorque de metadonnees change."""
    import hashlib
    try:
        taille = os.path.getsize(chemin)
        h = hashlib.sha256()
        with open(chemin, 'rb') as f:
            h.update(f.read(BLOC))
            if taille > 3 * BLOC:
                f.seek(taille // 2)
                h.update(f.read(BLOC))
        return taille, h.hexdigest()
    except OSError:
        return None


def durees(exe, chemins, log=lambda *_: None):
    """{chemin -> (duree_s, resolution)} par lots exiftool.

    La duree tranche le cas ou les deux copies ne font pas la meme taille :
    la plus LONGUE porte plus de video, l'autre est tronquee. La resolution
    l'accompagne parce qu'une duree egale sur deux definitions differentes
    n'est pas le meme fichier."""
    res = {}
    CH = 80
    for i in range(0, len(chemins), CH):
        lot = chemins[i:i + CH]
        try:
            for item in exiftool_json(
                    exe, ['-Duration#', '-ImageSize', '-s3', '-q', '-q', '-j'],
                    lot, log):
                sf = item.get('SourceFile', '')
                if sf:
                    try:
                        d = float(item.get('Duration') or 0)
                    except (TypeError, ValueError):
                        d = 0.0
                    res[hkey(sf)] = (d, str(item.get('ImageSize') or ''))
        except Exception as e:  # noqa: BLE001
            log('  lot duree en erreur (%d..): %s' % (i, str(e)[:80]))
        log('  duree %d/%d' % (min(i + CH, len(chemins)), len(chemins)))
    return res


def comparer_videos(exe, atrier, fonds, noms, log=lambda *_: None):
    """(confirmes, tronquees, gardees) pour les VIDEOS de `_A TRIER`.

    - confirmes : meme taille ET meme empreinte de flux que l'homonyme du
      fonds -- un doublon a l'octet pres, la remorque exceptee.
    - tronquees : meme debut, mais le FONDS est plus long. La copie d'ici est
      tronquee et la bonne version est dans le fonds -- c'est ce que la
      qualification a la main du 13/09 a trouve cinq fois. Ce verdict N'EST
      PAS applique tout seul : il attend un geste explicite, comme
      `homonymes_differents`. Un outil qui tranche un arbitrage, c'est ce qui
      a coute 68 photos le 13/09.
    - gardees : tout le reste. Dans le doute on garde."""
    par_nom = {}
    for f in fonds:
        par_nom.setdefault(os.path.basename(f).lower(), []).append(f)
    a_tester = [p for p in atrier if par_nom.get(os.path.basename(p).lower())]
    log('videos : %d dans _A TRIER, %d avec un homonyme dans le fonds'
        % (len(atrier), len(a_tester)))
    if not a_tester:
        return [], [], []
    jumeaux = []
    for p in a_tester:
        jumeaux += par_nom[os.path.basename(p).lower()]
    D = durees(exe, a_tester + list(set(jumeaux)), log)
    confirmes, tronquees, gardees = [], [], []
    for p in a_tester:
        ep = empreinte_flux(p)
        if ep is None:
            gardees.append({'dup': p, 'pourquoi': 'illisible'})
            continue
        dp, _rp = D.get(hkey(p), (0.0, ''))
        choisi = None
        for c in par_nom[os.path.basename(p).lower()]:
            ec = empreinte_flux(c)
            if ec is None:
                continue
            dc, _rc = D.get(hkey(c), (0.0, ''))
            if ec == ep:
                choisi = ('confirme', c, dp, dc)
                break
            if ec[1] == ep[1] and dc > dp:
                choisi = ('tronquee', c, dp, dc)
        if choisi is None:
            gardees.append({'dup': p, 'pourquoi': 'flux different'})
            continue
        quoi, canon, dp, dc = choisi
        # MEME regle des noms que pour les images : un doublon qui porte un
        # nom humain absent de la canonique ne part pas (CLAUDE.md n. 2).
        if noms and (noms.get(hkey(p), set()) - noms.get(hkey(canon), set())):
            gardees.append({'dup': p, 'pourquoi': 'nom absent de la canonique'})
            continue
        e = {'dup': p, 'canonique': canon,
             'duree_dup': round(dp, 3), 'duree_canonique': round(dc, 3)}
        (confirmes if quoi == 'confirme' else tronquees).append(e)
    return confirmes, tronquees, gardees


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--atrier', default='')
    ap.add_argument('--fonds', action='append', default=[])
    ap.add_argument('--db', default='')
    ap.add_argument('--limite', type=int, default=0, help='ne tester que les N premiers _A TRIER (validation rapide)')
    a = ap.parse_args(argv)
    exe = exiftool()
    if not exe:
        print('exiftool ABSENT'); return 2
    log = lambda m: print(m, flush=True)

    # Les salles d'arbitrage sont ECARTEES des DEUX cotes, et c'est le point :
    # laissees dans le fonds elles deviendraient la « canonique » d'un autre
    # doublon, laissees dans `_A TRIER` elles seraient retirees sans verdict.
    arbitrage = []

    def trier_arbitrage(chemins):
        """Les chemins hors salle d'arbitrage ; les autres sont NOTES."""
        gardes = []
        for p in chemins:
            if _ra.est_arbitrage(p):
                arbitrage.append(p)
            else:
                gardes.append(p)
        return gardes

    atrier_videos, fonds_videos = [], []
    if a.atrier:
        atrier_files = trier_arbitrage(enum_media(deb64(a.atrier)))
        atrier_videos = trier_arbitrage(enum_videos(deb64(a.atrier)))
        fonds_files = []
        for f in a.fonds:
            fonds_files += trier_arbitrage(enum_media(deb64(f)))
            fonds_videos += trier_arbitrage(enum_videos(deb64(f)))
    else:
        atrier_files, fonds_files = [], []
        for rac in racines_config():
            for p in enum_media(rac):
                if _ra.est_arbitrage(p):
                    arbitrage.append(p)
                    continue
                (atrier_files if est_atri(p) else fonds_files).append(p)
            for p in enum_videos(rac):
                if _ra.est_arbitrage(p):
                    arbitrage.append(p)
                    continue
                (atrier_videos if est_atri(p) else fonds_videos).append(p)
    log('_A TRIER : %d media | fonds : %d media | arbitrage LAISSE : %d'
        % (len(atrier_files), len(fonds_files), len(arbitrage)))
    if arbitrage:
        log('  (ces fichiers attendent un verdict humain : ni doublon, ni'
            ' canonique -- %s)' % asc(', '.join(sorted(_ra.SALLES_ARBITRAGE))))

    # index du fonds par basename minuscule
    fonds_par_nom = defaultdict(list)
    for p in fonds_files:
        fonds_par_nom[os.path.basename(p).lower()].append(p)

    if a.limite:
        atrier_files = atrier_files[:a.limite]
    # ne garder que les _A TRIER qui ont un HOMONYME dans le fonds
    a_tester, sans_homonyme = [], []
    for p in atrier_files:
        if fonds_par_nom.get(os.path.basename(p).lower()):
            a_tester.append(p)
        else:
            sans_homonyme.append(p)
    # jumeaux du fonds a hasher (uniquement ceux qui servent)
    jumeaux = []
    for p in a_tester:
        jumeaux += fonds_par_nom[os.path.basename(p).lower()]
    log('homonymes a comparer : %d (+ %d jumeaux fonds a hasher)' % (len(a_tester), len(set(jumeaux))))

    H = image_hashes(exe, a_tester + list(set(jumeaux)), log)
    noms = load_names(Path(deb64(a.db))) if a.db else {}
    v_confirmes, v_tronquees, v_gardees = comparer_videos(
        exe, atrier_videos, fonds_videos, noms, log)

    confirmes, revue, image_differente, homonymes_differents = [], [], [], []
    for p in a_tester:
        ph = H.get(hkey(p))
        cand = fonds_par_nom[os.path.basename(p).lower()]
        canon = next((c for c in cand if ph and H.get(hkey(c)) == ph), None)
        if not canon:
            # Homonyme sans image identique (re-encodage Google, par exemple) :
            # ce n'est PAS un doublon, mais on NOTE l'homonyme et les noms que
            # la copie porterait en plus, pour que `deplacer_doublons_atrier
            # --homonymes-differents` (decision humaine explicite) sache quoi
            # retirer sans jamais perdre un nom.
            manque = sorted(noms.get(hkey(p), set()) - noms.get(hkey(cand[0]), set())) if noms else []
            image_differente.append(p)
            homonymes_differents.append({'dup': p, 'homonyme': cand[0], 'noms_manquants': manque})
            continue
        # regle des noms : le doublon ne doit pas porter un nom absent de la canonique
        if noms:
            manque = noms.get(hkey(p), set()) - noms.get(hkey(canon), set())
            if manque:
                revue.append((p, canon, sorted(manque)))
                continue
        confirmes.append((p, canon))

    octets = 0
    for p, _ in confirmes:
        try:
            octets += os.path.getsize(p)
        except OSError:
            pass

    print('=' * 74)
    print('DOUBLONS _A TRIER deja ranges (meme IMAGE) :')
    print('  confirmes (retirables)         : %d  (%.2f Go liberables)' % (len(confirmes), octets / 1e9))
    print('  a REVUE (nom absent canonique) : %d  (a fusionner d abord)' % len(revue))
    print('  homonyme mais IMAGE differente : %d  (a garder, ce n est pas un doublon)' % len(image_differente))
    print('  sans homonyme dans le fonds    : %d  (a ranger normalement)' % len(sans_homonyme))
    print('  LAISSES en arbitrage           : %d  (verdict humain attendu)' % len(arbitrage))
    print('VIDEOS de _A TRIER (flux, pas pixels) :')
    print('  confirmes (meme flux)          : %d  (retirables)' % len(v_confirmes))
    print('  fonds PLUS LONG (ici tronquee) : %d  (geste explicite : --videos-tronquees)' % len(v_tronquees))
    print('  gardees                        : %d' % len(v_gardees))
    for e in v_tronquees[:6]:
        print('   TRONQUEE : %s  (%.3fs ici, %.3fs dans le fonds)'
              % (asc(os.path.basename(e['dup'])), e['duree_dup'], e['duree_canonique']))
    for p, c in confirmes[:8]:
        print('   dup : %s' % asc(p))
        print('     -> canonique : %s' % asc(c))
    for p, c, m in revue[:6]:
        print('   REVUE : %s  (noms manquants: %s)' % (asc(os.path.basename(p)), asc(', '.join(m))))

    rapport = {
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
        'confirmes': [{'dup': p, 'canonique': c} for p, c in confirmes],
        'revue': [{'dup': p, 'canonique': c, 'noms_manquants': m} for p, c, m in revue],
        'image_differente': image_differente,
        'homonymes_differents': homonymes_differents,
        'sans_homonyme': sans_homonyme,
        'arbitrage_laisse': arbitrage,
        # Les videos ont leurs propres cles : `videos_confirmes` rejoint le
        # retrait ordinaire, `videos_tronquees` attend un geste explicite.
        'videos_confirmes': v_confirmes,
        'videos_tronquees': v_tronquees,
        'videos_gardees': v_gardees,
        'octets_liberables': octets,
    }
    docs = ICI / 'docs'
    try:
        docs.mkdir(exist_ok=True)
    except OSError:
        pass
    (docs / 'doublons_atrier.json').write_text(
        json.dumps(rapport, ensure_ascii=False, indent=1), encoding='utf-8')
    print('liste ecrite : docs/doublons_atrier.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
