#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dézippage d'un export Google Takeout — inventaire d'abord, écriture ensuite.
──────────────────────────────────────────────────────────────────────────────

POURQUOI CET INSTRUMENT EXISTE

Le Takeout arrive en une DIZAINE de `.zip` numérotés qui, une fois ouverts
dans le même dossier, reconstituent un seul arbre `Takeout/Google Photos/…`.
Trois choses tournent mal, et toutes les trois sont SILENCIEUSES :

1. **Un lot manquant.** Google numérote `-1-of-24` (ou `-001`) : un
   téléchargement interrompu laisse un trou. Dézipper les 23 autres donne un
   arbre qui a l'air complet — et `verifier_photos_google.py` déclarerait
   ABSENTES des photos que Google détient bel et bien, ou pire, rendrait un
   feu vert sur un inventaire tronqué.
2. **La place.** 75 Go compressés en demandent autant une fois ouverts.
   Un disque plein en cours de route laisse un fichier tronqué qui a la
   bonne taille pour personne et le bon nom pour tout le monde.
3. **Les chemins longs.** Les noms d'albums de Takeout dépassent
   couramment les 260 caractères de l'API Windows historique. `Expand-Archive`
   s'arrête dessus ; ici on écrit par `\\?\`.

D'où l'ordre : **compter d'abord, écrire ensuite**, et ne rien écrire tant
qu'un lot manque ou que la place n'y est pas.

CE QU'IL FAIT

- Il liste les `.zip`, LIT LEUR SOMMAIRE sans les ouvrir en entier, et dit :
  combien de lots, combien de fichiers, combien d'octets une fois ouverts.
- Il cherche les TROUS dans la numérotation, et refuse d'écrire s'il en voit.
- Il compare la place demandée à la place libre sur le disque de la cible.
- Il repère les CONFLITS : un même chemin présent dans deux lots avec deux
  tailles différentes (deux exports mélangés dans le même dossier).
- Il est REPRENABLE : un fichier déjà écrit à la bonne taille est sauté.
  Relancer après une coupure ne recommence pas tout — c'est le sens du
  « si nécessaire » : sur un dossier déjà ouvert, il ne fait rien.
- Il refuse tout membre dont le chemin sortirait de la cible (zip slip).

CE QU'IL NE FAIT PAS

Il n'efface aucun `.zip`, ne touche ni à la base, ni au NAS, ni à Google.
Sans `--extraire` il n'écrit rien du tout. Sa sortie est en ASCII pur
(console cp1252 de l'agent).

USAGE
    python dezipper_takeout.py                        # inventaire seul
    python dezipper_takeout.py --extraire             # ecrit dans <source>\\extrait
    python dezipper_takeout.py --source "C:\\GOOGLE PHOTOS" --cible "D:\\Takeout"
    python dezipper_takeout.py --tester               # CRC de chaque lot (LENT)
    python dezipper_takeout.py --json _takeout.json

    Sortie 0 = tout est propre. 1 = un lot manque, un zip est illisible,
    la place n'y est pas, ou un conflit n'est pas tranche.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

SOURCE_DEFAUT = r"C:\GOOGLE PHOTOS"
MARGE_PLACE = 1.05          # 5 % de marge : on n'ecrit pas sur le dernier octet
LISTE_MAX = 40              # ce qui n'est pas liste est COMPTE, jamais tu
TAMPON = 1024 * 1024

# takeout-20260826T101500Z-1-of-24.zip   |   ...-001.zip   |   ...-1.zip
_RE_SUR = re.compile(r'-(\d+)-of-(\d+)\.zip$', re.I)
_RE_NUM = re.compile(r'-(\d+)\.zip$')


# ─────────────────────────────────────────────────────── les lots ────────────

def numero_de_lot(nom):
    """(index, total) — `total` None si le nom ne l'annonce pas.

    None si le nom ne porte aucun numero : un `.zip` etranger au Takeout
    depose dans le meme dossier ne doit pas creuser un faux trou."""
    m = _RE_SUR.search(nom)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _RE_NUM.search(nom)
    if m:
        return int(m.group(1)), None
    return None


def _cle_tri(p):
    n = numero_de_lot(p.name)
    return (0, n[0], p.name.lower()) if n else (1, 0, p.name.lower())


def lister_zips(source):
    source = Path(source)
    if not source.is_dir():
        return []
    return sorted((p for p in source.iterdir()
                   if p.is_file() and p.suffix.lower() == '.zip'),
                  key=_cle_tri)


def trous(zips):
    """([numeros manquants], total annonce ou None).

    Le total annonce prime sur le plus grand numero vu : c'est lui qui dit
    qu'il manque la FIN de la serie, ce que la serie elle-meme ne peut pas
    dire."""
    nums, total = [], None
    for p in zips:
        n = numero_de_lot(getattr(p, 'name', str(p)))
        if not n:
            continue
        nums.append(n[0])
        if n[1]:
            total = max(total or 0, n[1])
    if not nums:
        return [], total
    haut = max(total or 0, max(nums))
    vus = set(nums)
    return [i for i in range(min(nums), haut + 1) if i not in vus], total


# ────────────────────────────────────────────────── ce que les zips disent ───

def inventaire(zips):
    """Lit le SOMMAIRE de chaque zip (pas les octets) et compte."""
    par_zip, erreurs, conflits = [], [], []
    membres = {}                        # chemin -> (taille, zip)
    for p in zips:
        p = Path(p)
        try:
            with zipfile.ZipFile(p) as zf:
                infos = zf.infolist()
        except Exception as e:                          # noqa: BLE001
            erreurs.append({'zip': p.name, 'cause': str(e)})
            continue
        n_f, oct_ = 0, 0
        for i in infos:
            if i.is_dir():
                continue
            n_f += 1
            oct_ += i.file_size
            vu = membres.get(i.filename)
            if vu is None:
                membres[i.filename] = (i.file_size, p.name)
            elif vu[0] != i.file_size:
                conflits.append({'chemin': i.filename,
                                 'zip_a': vu[1], 'taille_a': vu[0],
                                 'zip_b': p.name, 'taille_b': i.file_size})
        try:
            octets_zip = p.stat().st_size
        except OSError:
            octets_zip = 0
        par_zip.append({'zip': p.name, 'octets_zip': octets_zip,
                        'fichiers': n_f, 'octets_ouverts': oct_})
    return {
        'par_zip': par_zip,
        'erreurs': erreurs,
        'conflits': conflits,
        'fichiers_distincts': len(membres),
        'octets_distincts': sum(t for t, _z in membres.values()),
        'octets_ouverts': sum(z['octets_ouverts'] for z in par_zip),
        'octets_zip': sum(z['octets_zip'] for z in par_zip),
    }


def tester(zips, ecrire=print):
    """CRC complet de chaque lot. LENT : il lit tous les octets."""
    mauvais = []
    for p in zips:
        p = Path(p)
        t0 = time.time()
        try:
            with zipfile.ZipFile(p) as zf:
                premier = zf.testzip()
        except Exception as e:                          # noqa: BLE001
            mauvais.append({'zip': p.name, 'cause': str(e)})
            ecrire("  %-44s ILLISIBLE : %s" % (p.name[:44], e))
            continue
        if premier:
            mauvais.append({'zip': p.name, 'cause': 'CRC: ' + premier})
            ecrire("  %-44s CRC FAUX sur %s" % (p.name[:44], premier))
        else:
            ecrire("  %-44s ok  (%.0f s)" % (p.name[:44], time.time() - t0))
    return mauvais


# ────────────────────────────────────────────────────────── ecriture ─────────

def _long(p):
    """Chemin utilisable par l'API Windows au-dela de 260 caracteres."""
    s = str(p)
    if os.name == 'nt' and not s.startswith('\\\\?\\'):
        s = '\\\\?\\' + os.path.abspath(s)
    return s


def _existe(p):
    return os.path.exists(_long(p))


def _taille(p):
    try:
        return os.path.getsize(_long(p))
    except OSError:
        return -1


def chemin_sur(cible, nom):
    """Destination d'un membre, ou None s'il sortirait de la cible.

    Un `.zip` est une donnee, pas une instruction : `..`, un chemin absolu
    ou une lettre de lecteur dans un nom de membre ecrirait AILLEURS."""
    cible = Path(cible)
    parts = [x for x in str(nom).replace('\\', '/').split('/')
             if x not in ('', '.')]
    if not parts:
        return None
    if any(x == '..' or ':' in x for x in parts):
        return None
    dest = cible.joinpath(*parts)
    try:
        # `resolve()` accepte un chemin qui n'existe pas encore.
        dest.resolve().relative_to(cible.resolve())
    except ValueError:
        return None
    return dest


def extraire_un(zf, info, cible, appliquer=True):
    """('ecrit'|'saute'|'a_ecrire'|'refuse', destination|None)."""
    dest = chemin_sur(cible, info.filename)
    if dest is None:
        return 'refuse', None
    if _taille(dest) == info.file_size:
        return 'saute', dest
    if not appliquer:
        return 'a_ecrire', dest
    os.makedirs(_long(dest.parent), exist_ok=True)
    with zf.open(info) as src, open(_long(dest), 'wb') as out:
        shutil.copyfileobj(src, out, TAMPON)
    try:
        horodate = time.mktime(tuple(info.date_time) + (0, 0, -1))
        os.utime(_long(dest), (horodate, horodate))
    except (OverflowError, OSError, ValueError):
        pass                       # une date de zip fantaisiste ne bloque rien
    return 'ecrit', dest


def extraire(zips, cible, appliquer=False, ecrire=print):
    """Ouvre chaque lot dans `cible`. Reprenable : ce qui est deja la est saute."""
    compte = {'ecrit': 0, 'saute': 0, 'a_ecrire': 0, 'refuse': 0}
    octets = 0
    refuses = []
    for p in zips:
        p = Path(p)
        t0 = time.time()
        avant = dict(compte)
        try:
            with zipfile.ZipFile(p) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    etat, _dest = extraire_un(zf, info, cible, appliquer)
                    compte[etat] += 1
                    if etat == 'ecrit':
                        octets += info.file_size
                    elif etat == 'refuse':
                        refuses.append(info.filename)
        except Exception as e:                          # noqa: BLE001
            ecrire("  %-40s INTERROMPU : %s" % (p.name[:40], e))
            return compte, octets, refuses, False
        ecrire("  %-40s +%-7d =%-7d  (%.0f s)"
               % (p.name[:40],
                  compte['ecrit'] - avant['ecrit'] + compte['a_ecrire'] - avant['a_ecrire'],
                  compte['saute'] - avant['saute'],
                  time.time() - t0))
    return compte, octets, refuses, True


# ──────────────────────────────────────────────────────── le rapport ─────────

def go(n):
    return "%.1f Go" % (n / (1024.0 ** 3))


def trouver_google_photos(cible):
    """Le dossier a passer a verifier_photos_google.py, s'il est deja la."""
    cible = Path(cible)
    if not cible.is_dir():
        return None
    for prof in range(4):
        motif = '/'.join(['*'] * prof + ['Google Photos']) if prof else 'Google Photos'
        for p in cible.glob(motif):
            if p.is_dir():
                return p
    for prof in range(4):
        motif = '/'.join(['*'] * prof + ['Takeout']) if prof else 'Takeout'
        for p in cible.glob(motif):
            if p.is_dir():
                return p
    return None


def rapport(source, cible, zips, inv, manquants, total_annonce, ecrire=print):
    """Le verdict AVANT toute ecriture. True = on peut extraire."""
    ok = True
    ecrire("")
    ecrire("=" * 70)
    ecrire("  TAKEOUT GOOGLE - INVENTAIRE DES LOTS")
    ecrire("=" * 70)
    ecrire("  source : %s" % source)
    ecrire("  cible  : %s" % cible)
    ecrire("")

    if not zips:
        ecrire("  AUCUN .zip dans le dossier source. Rien a faire.")
        ecrire("  (Verifie le chemin, ou attends la fin du telechargement.)")
        return False

    ecrire("  %d lot(s), %s compresses" % (len(zips), go(inv['octets_zip'])))
    if total_annonce:
        ecrire("  les noms annoncent une serie de %d lots" % total_annonce)
    ecrire("  %d fichiers distincts, %s une fois ouverts"
           % (inv['fichiers_distincts'], go(inv['octets_distincts'])))
    ecrire("")

    if inv['erreurs']:
        ok = False
        ecrire("  ILLISIBLES (%d) - un zip tronque ne s'ouvre pas a moitie :"
               % len(inv['erreurs']))
        for e in inv['erreurs'][:LISTE_MAX]:
            ecrire("    %-46s %s" % (e['zip'][:46], e['cause'][:60]))
        ecrire("")

    if manquants:
        ok = False
        ecrire("  LOT(S) MANQUANT(S) : %s"
               % ', '.join(str(i) for i in manquants[:LISTE_MAX]))
        if len(manquants) > LISTE_MAX:
            ecrire("    ... et %d autre(s)" % (len(manquants) - LISTE_MAX))
        ecrire("  Un export incomplet ferait declarer ABSENTES des photos que")
        ecrire("  Google detient. Retelecharge les lots manquants d'abord.")
        ecrire("")
    else:
        ecrire("  Numerotation : aucun trou.")

    if inv['conflits']:
        ok = False
        ecrire("")
        ecrire("  CONFLITS (%d) - meme chemin, deux tailles : deux exports"
               % len(inv['conflits']))
        ecrire("  melanges dans le meme dossier. A trancher a la main.")
        for c in inv['conflits'][:LISTE_MAX]:
            ecrire("    %s" % c['chemin'][:64])
            ecrire("      %s : %d o  |  %s : %d o"
                   % (c['zip_a'][:28], c['taille_a'], c['zip_b'][:28], c['taille_b']))
        if len(inv['conflits']) > LISTE_MAX:
            ecrire("    ... et %d autre(s)" % (len(inv['conflits']) - LISTE_MAX))

    # La place, avant d'ecrire le premier octet.
    besoin = int(inv['octets_distincts'] * MARGE_PLACE)
    racine = Path(cible)
    while not racine.exists() and racine.parent != racine:
        racine = racine.parent
    try:
        libre = shutil.disk_usage(str(racine)).free
    except OSError:
        libre = -1
    if libre < 0:
        ecrire("  Place libre : non mesurable sur %s" % racine)
    else:
        ecrire("  Place : %s demandes (marge comprise), %s libres sur %s"
               % (go(besoin), go(libre), racine))
        if libre < besoin:
            ok = False
            ecrire("  PAS ASSEZ DE PLACE. Un disque plein en cours de route")
            ecrire("  laisse un fichier tronque qui porte le bon nom.")

    ecrire("")
    ecrire("  VERDICT : %s" % ("on peut extraire." if ok
                               else "NE PAS EXTRAIRE en l'etat."))
    ecrire("=" * 70)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Dezippe un export Google Takeout, apres inventaire.")
    ap.add_argument('--source', default=SOURCE_DEFAUT,
                    help='dossier des .zip (defaut : %s)' % SOURCE_DEFAUT)
    ap.add_argument('--cible', default=None,
                    help='ou ouvrir (defaut : <source>\\extrait)')
    ap.add_argument('--extraire', action='store_true',
                    help='ECRIT. Sans lui, rien n est ecrit.')
    ap.add_argument('--tester', action='store_true',
                    help='CRC complet de chaque lot (LENT)')
    ap.add_argument('--forcer', action='store_true',
                    help='extraire malgre un verdict rouge (a ses risques)')
    ap.add_argument('--json', default=None, help='ecrit le rapport en JSON')
    a = ap.parse_args(argv)

    source = Path(a.source)
    cible = Path(a.cible) if a.cible else source / 'extrait'

    zips = lister_zips(source)
    inv = inventaire(zips)
    manquants, total = trous(zips)
    ok = rapport(source, cible, zips, inv, manquants, total)

    mauvais = []
    if a.tester and zips:
        print("")
        print("  CRC complet (lecture de tous les octets) :")
        mauvais = tester(zips)
        if mauvais:
            ok = False

    resultat = {'source': str(source), 'cible': str(cible),
                'lots': len(zips), 'total_annonce': total,
                'manquants': manquants, 'crc_mauvais': mauvais,
                'verdict_avant_extraction': ok}
    resultat.update({k: v for k, v in inv.items() if k != 'par_zip'})
    resultat['par_zip'] = inv['par_zip']

    if a.extraire and zips and (ok or a.forcer):
        print("")
        print("  EXTRACTION vers %s" % cible)
        print("  (deja ecrit a la bonne taille = saute ; relancer reprend)")
        os.makedirs(_long(cible), exist_ok=True)
        compte, octets, refuses, complet = extraire(zips, cible, appliquer=True)
        print("")
        print("  ecrits %d (%s), sautes %d, refuses %d"
              % (compte['ecrit'], go(octets), compte['saute'], compte['refuse']))
        if refuses:
            print("  REFUSES (chemin sortant de la cible) :")
            for r in refuses[:LISTE_MAX]:
                print("    %s" % r[:66])
        resultat['extraction'] = {'compte': compte, 'octets_ecrits': octets,
                                  'refuses': refuses[:LISTE_MAX],
                                  'complete': complet}
        ok = ok and complet
    elif a.extraire and not ok:
        print("")
        print("  Rien n'a ete ecrit : le verdict est rouge.")
        print("  (--forcer passe outre, en connaissance de cause.)")

    if a.extraire or trouver_google_photos(cible):
        gp = trouver_google_photos(cible)
        print("")
        if gp:
            print("  Prochaine etape :")
            print('    .venv\\Scripts\\python.exe verifier_photos_google.py '
                  '--takeout "%s"' % gp)
            resultat['dossier_google_photos'] = str(gp)
        else:
            print("  Dossier 'Google Photos' introuvable sous la cible :")
            print("  passe le bon chemin a verifier_photos_google.py --takeout")

    if a.json:
        Path(a.json).write_text(json.dumps(resultat, indent=2,
                                           ensure_ascii=False),
                                encoding='utf-8')
        print("  rapport JSON : %s" % a.json)

    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
