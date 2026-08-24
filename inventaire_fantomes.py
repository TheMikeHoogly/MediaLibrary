#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inventaire — les copies de travail qu'ExifTool a laissées derrière lui
──────────────────────────────────────────────────────────────────────────────

POURQUOI CET INSTRUMENT EXISTE

Avant d'écrire, ExifTool fabrique `<photo>_exiftool_tmp`, y recopie le fichier,
puis remplace l'original. Tué en route — fenêtre fermée, passe interrompue,
coupure de courant — il laisse cette copie derrière lui. Et il **REFUSE
d'écrire tant que le temporaire existe**, sans option pour l'écraser : la photo
devient définitivement non réécrivable. Silencieusement.

Le 24/08, la liste demandée à la main en a rendu **21**, datés du 06/07 au
24/08 — sept semaines. Onze bloquaient des photos que les journaux de la
réparation connaissaient ; **les dix autres bloquaient sans que rien nulle part
ne le dise**. Ce n'est pas le résidu d'un accident : c'est ce que laisse
CHAQUE écriture interrompue, et le serveur écrit tout le temps.

Un défaut que personne ne mesure grossit sans se voir. Voilà la mesure.

CE QU'IL NE FAIT PAS

Il n'efface RIEN : famille `inventaire_`, lecture seule, lançable au banc.
Effacer est un geste de Mike (`Remove-Item`), ou celui d'une passe qui vient de
lire la photo — `appliquer_xmp_personnes.py --balayer-fantomes`.

LE CAS QU'IL FAUT REGARDER

Un fantôme dont l'ORIGINAL a disparu n'est pas un déchet : c'est peut-être la
seule copie qui reste, si ExifTool est mort entre le remplacement et le
renommage. Ce rapport les compte à part et les NOMME. Ne jamais les effacer en
lot avec les autres.

USAGE
    python inventaire_fantomes.py
    python inventaire_fantomes.py --json _fantomes.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SUFFIXE = '_exiftool_tmp'

# Assez pour lire, pas assez pour déverser. Ce qui n'est pas listé est COMPTÉ :
# un plafond tu se lirait comme un fonds propre.
LISTE_MAX = 40


def racines(fichiers=None):
    """Les dossiers à balayer, lus dans les fichiers de configuration.

    Même source que le serveur (`dossiers_a_taguer.txt`, `dossier_uploads.txt`)
    pour ne pas inventer une deuxième vérité : un inventaire qui regarde
    ailleurs que là où l'on écrit ne mesure rien."""
    out = []
    for nom in (fichiers or ('dossiers_a_taguer.txt', 'dossier_uploads.txt')):
        p = RACINE / nom if not os.path.isabs(str(nom)) else Path(nom)
        try:
            lignes = p.read_text(encoding='utf-8').splitlines()
        except OSError:
            continue
        for ligne in lignes:
            ligne = ligne.strip()
            if ligne and not ligne.startswith('#') and ligne not in out:
                out.append(ligne)
    return out


def trouver(racine, marcher=None):
    """Les fantômes sous `racine`. Rend une liste de dicts.

    `marcher` : injecté par les tests (signature d'`os.walk`)."""
    marcher = marcher or os.walk
    out = []
    for dossier, _sous, fichiers in marcher(str(racine)):
        for nom in fichiers:
            # `endswith`, pas `in` : une photo qui s'appellerait
            # `mon_exiftool_tmp_backup.jpg` n'est pas un fantôme.
            if not nom.endswith(SUFFIXE):
                continue
            chemin = Path(dossier) / nom
            original = Path(dossier) / nom[:-len(SUFFIXE)]
            try:
                st = chemin.stat()
                taille, quand = st.st_size, st.st_mtime
            except OSError:
                taille, quand = -1, 0.0
            out.append({'chemin': str(chemin), 'original': str(original),
                        'original_present': original.exists(),
                        'octets': taille, 'quand': quand})
    return out


def rapport(fantomes, maintenant=None, ecrire=print):
    """Dit ce qui a été trouvé, et ce qu'il faut en faire. Rend un dict."""
    maintenant = maintenant or time.time()
    orphelins = [f for f in fantomes if not f['original_present']]
    surs = [f for f in fantomes if f['original_present']]
    octets = sum(max(0, f['octets']) for f in fantomes)
    quands = [f['quand'] for f in fantomes if f['quand']]

    ecrire("")
    ecrire("=" * 74)
    ecrire("  FANTOMES ExifTool — copies de travail restees sur le fonds")
    ecrire("=" * 74)
    ecrire("  fantomes trouves         : %d" % len(fantomes))
    ecrire("  place occupee            : %.1f Mo" % (octets / 1048576.0))
    if quands:
        vieux = (maintenant - min(quands)) / 86400.0
        recent = (maintenant - max(quands)) / 86400.0
        ecrire("  le plus ancien           : %.1f jour(s)" % vieux)
        ecrire("  le plus recent           : %.1f jour(s)" % recent)
    if surs:
        ecrire("")
        ecrire("  photos BLOQUEES en ecriture, original intact a cote : %d"
               % len(surs))
        ecrire("    -> effacables sans risque. Tant qu ils sont la, ExifTool")
        ecrire("       REFUSE de reecrire ces photos : aucun nom ne peut plus")
        ecrire("       y atterrir, et rien ne le dit.")
    if orphelins:
        ecrire("")
        ecrire("  SANS ORIGINAL A COTE : %d  <-- NE PAS EFFACER EN LOT"
               % len(orphelins))
        ecrire("    -> ExifTool est peut-etre mort entre le remplacement et le")
        ecrire("       renommage : ce temporaire est alors la SEULE copie qui")
        ecrire("       reste. Les regarder un par un.")
        for f in orphelins[:LISTE_MAX]:
            ecrire("       %s" % f['chemin'])
        if len(orphelins) > LISTE_MAX:
            ecrire("       ... et %d autre(s) non listes"
                   % (len(orphelins) - LISTE_MAX))

    if surs:
        ecrire("")
        ecrire("  LES EFFACER (geste de Mike) :")
        ecrire("    Get-ChildItem <racine> -Recurse -Filter *%s | Remove-Item"
               % SUFFIXE)
        ecrire("  OU, pendant une reparation qui vient de lire la photo :")
        ecrire("    appliquer_xmp_personnes.py --reprendre-echecs "
               "--balayer-fantomes --appliquer")
    if not fantomes:
        ecrire("")
        ecrire("  Aucun. Rien ne bloque l ecriture des XMP sur le fonds.")
    ecrire("=" * 74)
    return {'n': len(fantomes), 'octets': octets,
            'avec_original': len(surs), 'sans_original': len(orphelins),
            'fantomes': fantomes}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--racine', default='',
                    help="un dossier a balayer (defaut : ceux des fichiers de "
                         "configuration du serveur)")
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    cibles = [a.racine] if a.racine else racines()
    if not cibles:
        print("aucune racine a balayer : ni --racine, ni dossiers_a_taguer.txt")
        return 2
    print("  balayage de %d racine(s)..." % len(cibles))
    fantomes = []
    for r in cibles:
        fantomes.extend(trouver(r))
    r = rapport(fantomes)
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        print("  liste ecrite : %s" % a.sortie_json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
