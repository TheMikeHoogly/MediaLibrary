#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rapatrier sur le NAS les photos qui n'existent QUE chez Google.
──────────────────────────────────────────────────────────────────────────────

POURQUOI

`verifier_photos_google.py` a compté, le 27/08, **3 776 médias de l'export
Takeout que le NAS ne porte pas** — 12,6 Go, dont **2 017 vidéos**,
concentrés sur 2024 (1 532), 2025 (709) et 2026 (699). Ce n'est pas un écart
d'inventaire : c'est un fonds qui n'est jamais arrivé sur le NAS, et qui ne
vit aujourd'hui qu'à UN seul endroit — chez un tiers dont le quota est à 96 %.

Tant qu'il en reste un, rien ne s'efface chez Google. Ce script est le geste
qui lève ce verrou, et c'est le seul de la chaîne Google qui ÉCRIT : il n'est
donc pas lançable au banc, il se lance par `32 - Copier les absentes de
Google.bat`.

CE QU'IL FAIT, ET DANS QUEL ORDRE

Il copie chaque ABSENTE sous `_A TRIER/<étiquette>/<année>/`, parce que c'est
là que la chaîne existante les reprend : `26 - Ranger par annee.bat` les
range, le serveur les scanne, les tague, y cherche des visages. « Laisser
faire la magie » suppose de déposer au bon endroit.

L'année vient, dans cet ordre : du `.json` que Takeout dépose à côté du média
(`photoTakenTime` — la seule date d'origine sûre), sinon du dossier
`Photos from YYYY`, sinon `_SANS_DATE`. Jamais du `mtime` : c'est la règle
du projet depuis le 15/08, et un fichier fraîchement copié a le `mtime`
d'aujourd'hui — il ferait passer toutes ces photos pour des photos de 2026.

TROIS GARDE-FOUS, ET AUCUN N'EST NÉGOCIABLE PAR DÉFAUT

1. **Rien n'est écrasé.** Un fichier déjà là à la même taille est SAUTÉ (le
   script est reprenable) ; à une taille différente, la copie prend un nom
   suffixé et le rapport la NOMME. Aucun octet du fonds existant n'est perdu.
2. **La cible doit être sous `_A TRIER`.** Écrire 12,6 Go au mauvais endroit
   d'un NAS est exactement l'erreur qu'on ne rattrape pas. `--hors-a-trier`
   lève le garde-fou, en connaissance de cause.
3. **La place est vérifiée avant le premier octet**, et chaque copie est
   RELUE : une taille qui ne correspond pas est un grief, pas un succès.

Journal d'annulation dans `_corbeille_copies/` : la liste exacte de ce qui a
été écrit. Annuler, ici, c'est effacer ces fichiers-là et rien d'autre.

CE QU'IL NE FAIT PAS

Il ne touche à rien chez Google : effacer là-bas est un geste de Mike, sur
`photos.google.com`, et seulement une fois la vérification repassée au vert.
Il ne rapatrie pas les 99 photos dont le NAS a perdu le TRAILER Samsung —
leur pixel est déjà là, les copier créerait des doublons, et la cause est en
amont (voir `QUESTIONS_MIKE.md` du 27/08).

USAGE
    python copier_absentes.py                      # a blanc, rien n ecrit
    python copier_absentes.py --copier
    python copier_absentes.py --cible "D:/ailleurs" --hors-a-trier --copier

    Sortie 0 = tout ce qui devait etre copie l est, et relu.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventaire_fonds as F                                   # noqa: E402
import verifier_photos_google as G                             # noqa: E402

RACINE = Path(__file__).resolve().parent
RAPPORT_DEFAUT = '_google.json'
ETIQUETTE_DEFAUT = 'Takeout Google'
DOSSIER_A_TRIER = '_A TRIER'
SANS_DATE = '_SANS_DATE'
LISTE_MAX = 30
MARGE_PLACE = 1.05

_RE_ANNEE_DOSSIER = re.compile(r'(?:Photos from|Photos de)\s+(\d{4})', re.I)


def annee_du_media(chemin):
    """L'année d'une photo de l'export, ou None. JAMAIS le `mtime`.

    Le `.json` de Takeout d'abord : il porte `photoTakenTime`, la seule date
    d'origine sûre — le nom exporté, lui, peut avoir été tronqué. Le dossier
    `Photos from YYYY` ensuite. Un fichier fraîchement copié a le `mtime`
    d'aujourd'hui : s'en servir ferait passer tout l'export pour 2026."""
    sc = G.sidecar(chemin)
    if sc is not None:
        _titre, quand = G.lire_sidecar(sc)
        if quand:
            try:
                return int(time.strftime('%Y', time.localtime(quand)))
            except (ValueError, OSError):
                pass
    m = _RE_ANNEE_DOSSIER.search(str(chemin))
    if m:
        return int(m.group(1))
    return None


def cible_par_defaut(etiquette=ETIQUETTE_DEFAUT):
    """`<premiere racine du fonds>/_A TRIER/<etiquette>`, ou None."""
    for r in F.racines(('dossiers_a_taguer.txt',)):
        return Path(r) / DOSSIER_A_TRIER / etiquette
    return None


def sous_a_trier(cible):
    """Vrai si un composant du chemin est « _A TRIER » (casse/espaces libres)."""
    return any(str(p).strip().upper().replace(' ', '_').strip('_')
               .startswith('A_TRIER') or str(p).strip().upper() == DOSSIER_A_TRIER
               for p in Path(cible).parts)


def absentes(rapport):
    """Les médias ABSENT d'un rapport `verifier_photos_google --json`."""
    d = json.loads(Path(rapport).read_text(encoding='utf-8'))
    return [x for x in (d.get('par_verdict', {}).get('ABSENT') or [])
            if x.get('chemin_google')]


def nom_libre(dossier, nom, octets):
    """(destination, etat) — 'neuf', 'deja' (même taille), 'suffixe'.

    Rien n'est jamais écrasé : c'est la règle 2 du projet appliquée à une
    copie. Un homonyme d'une autre taille reçoit un suffixe ET se dit."""
    dest = Path(dossier) / nom
    if not dest.exists():
        return dest, 'neuf'
    try:
        if dest.stat().st_size == octets:
            return dest, 'deja'
    except OSError:
        pass
    tige, ext = os.path.splitext(nom)
    for i in range(2, 1000):
        autre = Path(dossier) / ('%s (%d)%s' % (tige, i, ext))
        if not autre.exists():
            return autre, 'suffixe'
    return dest, 'deja'


def plan(medias, cible, etiquette=ETIQUETTE_DEFAUT):
    """[(source, destination, etat)] — pur, sans écriture."""
    out = []
    for m in medias:
        an = annee_du_media(m['chemin_google'])
        dossier = Path(cible) / (str(an) if an else SANS_DATE)
        dest, etat = nom_libre(dossier, os.path.basename(m['chemin_google']),
                               m.get('octets') or 0)
        out.append((m['chemin_google'], str(dest), etat))
    return out


def copier(travaux, ecrire=print, chaque=100):
    """Copie, RELIT chaque taille, et rend (compte, griefs, ecrits)."""
    compte = {'copie': 0, 'deja': 0, 'suffixe': 0, 'grief': 0}
    griefs, ecrits = [], []
    t0 = time.time()
    for i, (src, dst, etat) in enumerate(travaux, 1):
        if etat == 'deja':
            compte['deja'] += 1
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            attendu = os.path.getsize(src)
            vu = os.path.getsize(dst)
            if vu != attendu:
                compte['grief'] += 1
                griefs.append('%s : %d octets ecrits pour %d attendus'
                              % (dst, vu, attendu))
                continue
        except OSError as e:
            compte['grief'] += 1
            griefs.append('%s : %s' % (dst, e))
            continue
        compte['copie'] += 1
        if etat == 'suffixe':
            compte['suffixe'] += 1
        ecrits.append({'source': src, 'destination': dst, 'etat': etat})
        if chaque and i % chaque == 0:
            ecrire("    %d / %d  (%.0f s)" % (i, len(travaux),
                                              time.time() - t0))
    return compte, griefs, ecrits


def journal(ecrits, dossier=None):
    """Écrit le journal d'annulation et rend son chemin, ou None."""
    if not ecrits:
        return None
    d = Path(dossier or (RACINE / '_corbeille_copies'))
    d.mkdir(parents=True, exist_ok=True)
    p = d / ('copie_%s.jsonl' % time.strftime('%Y%m%d_%H%M%S'))
    with open(p, 'w', encoding='utf-8') as f:
        for e in ecrits:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    return str(p)


def rapport(travaux, cible, octets, libre, compte=None, griefs=(),
            hors_a_trier=False, ecrire=print):
    """True si on peut copier (avant), ou si tout s'est bien passé (après)."""
    ok = True
    a_faire = [t for t in travaux if t[2] != 'deja']
    deja = len(travaux) - len(a_faire)
    suffixes = [t for t in travaux if t[2] == 'suffixe']
    ecrire("")
    ecrire("=" * 74)
    ecrire("  RAPATRIER CE QUI N EXISTE QUE CHEZ GOOGLE")
    ecrire("=" * 74)
    ecrire("  cible : %s" % cible)
    ecrire("")
    if not travaux:
        ecrire("  Aucune photo ABSENTE dans le rapport : rien a copier.")
        ecrire("  (Si c est inattendu : le rapport est-il a jour ?)")
        return False
    if not sous_a_trier(cible) and not hors_a_trier:
        ok = False
        ecrire("  LA CIBLE N EST PAS SOUS « %s »." % DOSSIER_A_TRIER)
        ecrire("  C est la que la chaine reprend le travail : rangement par")
        ecrire("  annee, scan, tagging, visages. Ecrire 12 Go ailleurs sur un")
        ecrire("  NAS est l erreur qu on ne rattrape pas.")
        ecrire("  --hors-a-trier leve ce garde-fou, en connaissance de cause.")

    ecrire("  a copier : %d   (%s)" % (len(a_faire), G._go(octets)
                                       if hasattr(G, '_go') else octets))
    ecrire("  deja sur place, meme taille : %d" % deja)
    if suffixes:
        ecrire("")
        ecrire("  HOMONYMES d une autre taille (%d) — rien n est ecrase, la"
               % len(suffixes))
        ecrire("  copie prend un nom suffixe :")
        for _s, d, _e in suffixes[:LISTE_MAX]:
            ecrire("    %s" % os.path.basename(d)[:66])
        if len(suffixes) > LISTE_MAX:
            ecrire("    ... et %d autre(s), non listes mais COMPTES"
                   % (len(suffixes) - LISTE_MAX))

    besoin = int(octets * MARGE_PLACE)
    if libre is not None and libre >= 0:
        ecrire("")
        ecrire("  place : %.1f Go demandes, %.1f Go libres"
               % (besoin / 1024.0 ** 3, libre / 1024.0 ** 3))
        if libre < besoin:
            ok = False
            ecrire("  PAS ASSEZ DE PLACE. Rien ne sera ecrit.")
    else:
        ecrire("  place libre : non mesurable sur la cible.")

    if compte is not None:
        ecrire("")
        ecrire("  copiees %d, deja la %d, suffixees %d, griefs %d"
               % (compte['copie'], compte['deja'], compte['suffixe'],
                  compte['grief']))
        for g in list(griefs)[:LISTE_MAX]:
            ecrire("    GRIEF %s" % g[:70])
        if compte['grief']:
            ok = False
    ecrire("")
    if compte is None:
        ecrire("  A BLANC : rien n a ete ecrit. Ajouter --copier." if ok
               else "  Rien ne sera ecrit en l etat.")
    elif ok:
        ecrire("  Fait. Suite : « 26 - Ranger par annee.bat », puis laisser le")
        ecrire("  serveur scanner. Et NE RIEN EFFACER chez Google avant")
        ecrire("  d avoir relance verifier_photos_google.py.")
    ecrire("=" * 74)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Copier sous _A TRIER ce que Google seul detient.")
    ap.add_argument('--rapport', default=RAPPORT_DEFAUT)
    ap.add_argument('--cible', default=None)
    ap.add_argument('--etiquette', default=ETIQUETTE_DEFAUT)
    ap.add_argument('--copier', action='store_true',
                    help='ECRIT. Sans lui, rien n est ecrit.')
    ap.add_argument('--hors-a-trier', dest='hors_a_trier', action='store_true')
    ap.add_argument('--json', dest='sortie_json', default=None)
    a = ap.parse_args(argv)

    if not Path(a.rapport).is_file():
        print("rapport introuvable : %s" % a.rapport)
        print("(le produire : verifier_photos_google.py --takeout ... --json)")
        return 2
    cible = Path(a.cible) if a.cible else cible_par_defaut(a.etiquette)
    if cible is None:
        print("aucune racine de fonds lisible (dossiers_a_taguer.txt).")
        return 2

    medias = absentes(a.rapport)
    print("  %d media(s) ABSENT(s) du NAS dans le rapport." % len(medias))
    travaux = plan(medias, cible, a.etiquette)
    octets = sum(m.get('octets') or 0 for m, t in zip(medias, travaux)
                 if t[2] != 'deja')
    racine = cible
    while not racine.exists() and racine.parent != racine:
        racine = racine.parent
    try:
        libre = shutil.disk_usage(str(racine)).free
    except OSError:
        libre = None

    ok = rapport(travaux, cible, octets, libre, hors_a_trier=a.hors_a_trier)
    compte = griefs = None
    chemin_journal = None
    if a.copier and ok:
        print("")
        print("  COPIE vers %s" % cible)
        compte, griefs, ecrits = copier(travaux)
        chemin_journal = journal(ecrits)
        ok = rapport(travaux, cible, octets, libre, compte, griefs,
                     hors_a_trier=a.hors_a_trier)
        if chemin_journal:
            print("  journal d annulation : %s" % chemin_journal)
    elif a.copier:
        print("")
        print("  Rien n a ete ecrit : le verdict est rouge.")

    if a.sortie_json:
        Path(a.sortie_json).write_text(json.dumps(
            {'rapport': a.rapport, 'cible': str(cible),
             'absentes': len(medias), 'octets': octets,
             'compte': compte, 'griefs': list(griefs or ()),
             'journal': chemin_journal, 'ok': ok},
            indent=2, ensure_ascii=False), encoding='utf-8')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
