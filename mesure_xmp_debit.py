#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — ce que coûte vraiment une invocation d'ExifTool
──────────────────────────────────────────────────────────────────────────────

POURQUOI CE BANC EXISTE

`person_writer` écrivait les noms dans les fichiers à **0,38 op/s** : la fusion
Flo → Florine du 23/08 a demandé onze heures. Le diagnostic écrit dans la
ROADMAP est qu'il lance **un processus ExifTool par geste**, et que le coût
dominant n'est pas l'écriture mais le DÉMARRAGE du processus. Deux remèdes en
découlent, dans cet ordre :

  (a) grouper les gestes d'une même photo en UNE invocation — fait le 23/08,
      ÷2 quand une photo est renommée ;
  (b) le mode `-stay_open` : un seul processus qui reste vivant et reçoit ses
      ordres un à un, le coût de démarrage n'étant plus payé qu'une fois.

(b) est plus lourd et plus risqué que (a) : un processus long qui tient le NAS,
une reprise à écrire quand il meurt. **Avant de l'écrire, on veut le CHIFFRE**
— c'est ce que fait ce banc. Il compare, sur de vraies photos du fonds :

  A. un processus par photo          (ce que fait le serveur aujourd'hui)
  B. un processus pour tout le lot   (la borne basse, inatteignable en écriture)
  C. `-stay_open`, un ordre par photo (ce que (b) donnerait)

CE QU'IL MESURE, ET CE QU'IL NE MESURE PAS

Il **LIT** les mots-clés, il n'écrit rien : famille `verifier_`/`mesure_`,
lecture seule — et surtout, on ne mesure pas un remède en abîmant le fonds.
Donc le gain qu'il annonce pour (b) est une **borne HAUTE** : une écriture
ajoute la réécriture du fichier sur SMB, que `-stay_open` ne supprime pas.
Ce que le banc isole proprement, c'est le terme « démarrage de processus » —
celui qui, seul, décide si (b) vaut son risque.

Il tourne pendant que la file travaille : ses lectures partagent le NAS avec
l'écrivain. Les trois régimes subissent la même gêne, la COMPARAISON tient ;
les temps absolus, non. Le banc le dit dans sa sortie plutôt que de le taire.

USAGE
    python mesure_xmp_debit.py --nom Florine
    python mesure_xmp_debit.py --nom Florine --n 60
    python mesure_xmp_debit.py --dossier "D:/Photos" --n 40
"""

import argparse
import json
import os
import queue as file_attente
import random
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))

from verifier_xmp_personnes import (          # noqa: E402  (même dossier)
    chemin_de_cle, cles_du_nom, dossier_uploads, exiftool_exe, file_du_serveur)

PHOTOS = ('.jpg', '.jpeg', '.png', '.heic', '.webp', '.tif', '.tiff')
# `-json` plutôt que `-s3` : une photo rend UN enregistrement, quel que soit
# le nombre de champs trouvés. Avec `-s3`, une photo qui porte Subject ET
# Keywords rend deux lignes — et un banc qui compte des lignes pour des photos
# annonce un débit qu'il n'a pas mesuré.
CHAMPS = ['-json', '-m', '-charset', 'filename=UTF8',
          '-XMP-dc:Subject', '-IPTC:Keywords']
MARQUE = '"SourceFile"'          # une occurrence = une photo lue
# PAS de `-q` : en `-stay_open`, il emporte le `{ready}` que le pilote attend.
# Mesuré le 23/08 — le regime C a attendu 600 s, et la fenetre des bancs avec
# lui, avant que l'agent ne le tue. C'est ce jour-la qu'un delai par ordre est
# entre dans `regime_stay_open` : un banc doit ECHOUER, jamais se figer.


# ────────────────────────────── Les échantillons ─────────────────────────────

def photos_du_serveur(nom, serveur, n, graine=12345):
    """N photos tirées au hasard (graine fixe) parmi celles que l'INDEX dit
    taguées `personne:Nom`. Graine fixe : deux passages comparent le même
    échantillon, sinon on mesure le tirage."""
    uploads = dossier_uploads()
    chemins = []
    for cle in cles_du_nom(nom, serveur):
        p = chemin_de_cle(cle, uploads)
        if p is not None:
            chemins.append(p)
    random.Random(graine).shuffle(chemins)
    return [p for p in chemins if _lisible(p)][:n]


def photos_du_dossier(dossier, n, graine=12345):
    """Repli quand le serveur ne répond pas : des photos prises sur le disque."""
    trouve = []
    for racine, _, fichiers in os.walk(dossier):
        for f in fichiers:
            if f.lower().endswith(PHOTOS):
                trouve.append(Path(racine) / f)
        if len(trouve) > max(n * 20, 400):
            break
    random.Random(graine).shuffle(trouve)
    return trouve[:n]


def _lisible(p):
    try:
        return p.is_file()
    except OSError:
        return False


# ──────────────────────────── Les trois régimes ──────────────────────────────

def _argfile(args):
    """Argfile UTF-8 AVEC BOM — sous Windows, c'est ce qui fait survivre les
    accents des chemins (même motif que `_run_exiftool` dans server.py)."""
    with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                     encoding='utf-8-sig') as tf:
        tf.write('\n'.join(args))
        return tf.name


def _commande(exe):
    """ExifTool, en liste d'arguments. Une LISTE est acceptee telle quelle :
    c'est ce qui permet aux verifications de brancher un faux ExifTool
    (`[python, faux.py]`) sans dependre d'un binaire installe."""
    return [str(x) for x in exe] if isinstance(exe, (list, tuple)) else [str(exe)]


def _oublier(chemin):
    try:
        os.unlink(chemin)
    except OSError:
        pass


def regime_un_par_photo(exe, photos, timeout=180):
    """A — un processus par photo. Ce que fait `person_writer` aujourd'hui."""
    lus = 0
    debut = time.time()
    for p in photos:
        f = _argfile(CHAMPS + [str(p)])
        try:
            r = subprocess.run(_commande(exe) + ['-@', f],
                               capture_output=True, text=True,
                               encoding='utf-8', errors='replace',
                               timeout=timeout)
            lus += (r.stdout or '').count(MARQUE)
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            _oublier(f)
    return time.time() - debut, lus


def regime_un_seul_lot(exe, photos, timeout=600):
    """B — un processus pour tout le lot. Borne basse : inatteignable pour une
    écriture, qui doit rester ordonnée photo par photo."""
    f = _argfile(CHAMPS + [str(p) for p in photos])
    debut = time.time()
    try:
        r = subprocess.run(_commande(exe) + ['-@', f], capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=timeout)
        lus = (r.stdout or '').count(MARQUE)
    except (OSError, subprocess.SubprocessError):
        lus = 0
    finally:
        _oublier(f)
    return time.time() - debut, lus


def _lecteur(flux, boite):
    """Lit la sortie du processus dans son coin. Un `readline()` direct sur un
    ExifTool muet BLOQUE POUR TOUJOURS — et un banc qui se fige fige aussi
    l'agent qui l'a lancé : c'est arrivé le 23/08, la fenêtre des bancs est
    restée sourde jusqu'à son propre délai. Un banc doit pouvoir échouer."""
    try:
        for ligne in flux:
            boite.put(ligne)
    except (OSError, ValueError):
        pass
    boite.put(None)


def regime_stay_open(exe, photos, timeout=180, delai=30.0):
    """C — UN processus, un ordre par photo. C'est le remède (b), mesuré.

    Le protocole d'ExifTool : les arguments arrivent un par ligne sur l'entrée
    standard, `-execute` déclenche, et le processus répond `{ready}` quand il a
    fini. Tant qu'on n'a pas lu `{ready}`, l'ordre suivant attend — l'ordre des
    écritures serait donc préservé, ce qui compte pour un fonds.

    Rien ici n'attend sans fin : la sortie est lue par un fil à part et chaque
    ordre a un délai. Un ExifTool muet fait ÉCHOUER le régime, il ne fige pas
    le banc — ni la fenêtre qui l'a lancé."""
    debut = time.time()
    proc = None
    lecteur = None
    lus = 0
    try:
        proc = subprocess.Popen(
            _commande(exe) + ['-stay_open', 'True', '-@', '-'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
            errors='replace', bufsize=1)
        boite = file_attente.Queue()
        lecteur = threading.Thread(target=_lecteur, args=(proc.stdout, boite),
                                   daemon=True)
        lecteur.start()
        for p in photos:
            proc.stdin.write('\n'.join(CHAMPS + [str(p), '-execute']) + '\n')
            proc.stdin.flush()
            fin = time.time() + delai
            while True:
                reste = fin - time.time()
                if reste <= 0:
                    raise TimeoutError(
                        f"pas de {{ready}} apres {delai:.0f} s : ExifTool ne "
                        "parle pas ce protocole ici")
                try:
                    ligne = boite.get(timeout=reste)
                except file_attente.Empty:
                    continue
                if ligne is None:
                    raise OSError("exiftool -stay_open a ferme sa sortie")
                if ligne.strip() == '{ready}':
                    break
                lus += ligne.count(MARQUE)
    except (OSError, ValueError, TimeoutError,
            subprocess.SubprocessError) as e:
        print(f"  ! regime -stay_open interrompu : {e}")
    finally:
        _refermer(proc, lecteur, timeout)
    return time.time() - debut, lus


def _refermer(proc, lecteur, timeout=20):
    """Referme le processif et ses tuyaux, dans le SEUL ordre qui ne bloque pas.

    Fermer `stdout` pendant que le fil lecteur y est bloqué interbloque les
    deux — ils se disputent le verrou du tampon. Donc : on demande poliment,
    on ferme l'entrée (ce qui suffit à faire sortir un processus sage), on tue
    ce qui reste, on attend le fil, et SEULEMENT ensuite on ferme."""
    if proc is None:
        return
    try:
        if proc.poll() is None and proc.stdin and not proc.stdin.closed:
            proc.stdin.write('-stay_open\nFalse\n-execute\n')
            proc.stdin.flush()
    except (OSError, ValueError):
        pass
    for tuyau in (proc.stdin,):
        try:
            if tuyau and not tuyau.closed:
                tuyau.close()
        except (OSError, ValueError):
            pass
    try:
        proc.wait(timeout=min(timeout, 10))
    except subprocess.SubprocessError:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.SubprocessError:
            pass
    if lecteur is not None:
        lecteur.join(timeout=5)
    try:
        if proc.stdout and not proc.stdout.closed:
            proc.stdout.close()
    except (OSError, ValueError):
        pass


# ─────────────────────────────── L'arithmétique ──────────────────────────────

def par_photo(secondes, n):
    return (secondes / n) if n else float('nan')


def projeter(secondes_par_photo, photos):
    """Heures qu'il faudrait pour `photos` photos à ce rythme."""
    return secondes_par_photo * photos / 3600.0


def decision(mesures, ecriture, photos_du_fonds=5907):
    """Ce que la mesure dit du REMÈDE, pas seulement de la lecture.

    La lecture isole le seul terme qui nous intéresse : le DÉMARRAGE du
    processus, c'est-à-dire l'écart entre « un processus par photo » et « un
    processus pour toutes ». `-stay_open` ne retire que celui-là. Le reste
    d'une écriture — réécrire le fichier sur SMB — lui survit intact. Comparer
    directement les 15× de la lecture à la file d'écriture serait un mensonge
    par cadrage."""
    a = par_photo(*mesures.get('A', (0.0, 0)))
    c = par_photo(*mesures.get('C', (0.0, 0)))
    demarrage = max(a - c, 0.0)
    apres = max(ecriture - demarrage, 0.0)
    lignes = [
        "",
        f"  CE QUE CA VEUT DIRE POUR L'ECRITURE",
        f"  Le demarrage du processus, isole (A - C)  : {demarrage:.2f} s",
        f"  Une ECRITURE reelle, mesuree sur la file  : {ecriture:.2f} s/op",
        f"  -stay_open n'en retire QUE le demarrage   : {apres:.2f} s/op",
    ]
    if ecriture > 0:
        lignes.append(f"  soit {100 * (1 - apres / ecriture):.0f} % de moins, "
                      f"et {projeter(ecriture, photos_du_fonds):.1f} h -> "
                      f"{projeter(apres, photos_du_fonds):.1f} h "
                      f"pour {photos_du_fonds} photos.")
    lignes.append("  (Le groupement des deux gestes d'un renommage, lui, est")
    lignes.append("   deja acquis et vaut un facteur 2 : il economise une")
    lignes.append("   ECRITURE entiere, pas seulement un demarrage.)")
    return '\n'.join(lignes)


def rapport(mesures, photos_du_fonds=5907, gene=None, ecriture=0.0):
    """Le texte du banc. `mesures` : {'A': (s, n), 'B': …, 'C': …}."""
    lignes = ["", "=" * 74, "  COUT D'UNE INVOCATION EXIFTOOL", "=" * 74]
    if gene is not None:
        lignes.append(f"  La file du serveur travaille pendant la mesure "
                      f"({gene} operation(s) en attente) : les temps ABSOLUS")
        lignes.append("  sont donc pessimistes. La comparaison, elle, tient.")
        lignes.append("")
    noms = {'A': "un processus par photo (le serveur aujourd'hui)",
            'B': "un seul processus pour tout le lot (borne basse)",
            'C': "-stay_open, un ordre par photo (le remede propose)"}
    base = None
    for cle in ('A', 'B', 'C'):
        s, n = mesures.get(cle, (0.0, 0))
        pp = par_photo(s, n)
        if cle == 'A':
            base = pp
        gain = ("" if cle == 'A' or not base or pp != pp
                else f"   ({base / pp:.1f}x)" if pp else "")
        lignes.append(f"  {cle}. {noms[cle]}")
        lignes.append(f"     {n} photo(s) en {s:.1f} s  ->  {pp:.2f} s/photo"
                      f"{gain}")
        lignes.append(f"     soit {projeter(pp, photos_du_fonds):.1f} h pour "
                      f"{photos_du_fonds} photos")
    if ecriture > 0:
        lignes.append(decision(mesures, ecriture, photos_du_fonds))
    lignes += ["", "  Lecture seule : une ECRITURE ajoute la reecriture du",
               "  fichier sur SMB, que -stay_open ne supprime pas. Le gain",
               "  annonce pour C est donc une borne HAUTE.", "=" * 74, ""]
    return '\n'.join(lignes)


# ───────────────────────────────── Le banc ───────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--nom', default='Florine',
                    help="le nom dont on tire l'echantillon (via l'index)")
    ap.add_argument('--dossier', default='',
                    help="repli : tirer les photos d'un dossier, sans serveur")
    ap.add_argument('--n', type=int, default=40,
                    help="nombre de photos (defaut 40)")
    ap.add_argument('--serveur', default='http://127.0.0.1:8080')
    ap.add_argument('--fonds', type=int, default=5907,
                    help="taille du fonds pour la projection")
    ap.add_argument('--ecriture', type=float, default=2.91,
                    help="cout mesure d'une ECRITURE de la file, en s/op "
                         "(defaut : 2,91 s, mesure le 23/08 sur 5 844 s de "
                         "file vivante)")
    a = ap.parse_args(argv)

    exe = exiftool_exe()
    if not exe:
        print("ExifTool introuvable : rien a mesurer.")
        return 2

    if a.dossier:
        photos = photos_du_dossier(a.dossier, a.n)
    else:
        try:
            photos = photos_du_serveur(a.nom, a.serveur, a.n)
        except Exception as e:                                # noqa: BLE001
            print(f"le serveur ne repond pas ({e}) : utiliser --dossier.")
            return 2
    if len(photos) < 3:
        print(f"echantillon trop maigre ({len(photos)} photo(s)) : "
              "rien de mesurable.")
        return 2

    gene = file_du_serveur(a.serveur)
    print(f"  {len(photos)} photo(s), ExifTool : {exe}")
    mesures = {}
    for cle, fn in (('A', regime_un_par_photo), ('B', regime_un_seul_lot),
                    ('C', regime_stay_open)):
        print(f"  regime {cle}...", flush=True)
        mesures[cle] = fn(exe, photos)
    print(rapport(mesures, a.fonds, gene, a.ecriture))
    return 0


if __name__ == '__main__':
    sys.exit(main())
