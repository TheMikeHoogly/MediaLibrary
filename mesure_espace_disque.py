# -*- coding: utf-8 -*-
"""mesure_espace_disque -- ce qui pese, et ce qui est REGENERABLE.

POURQUOI UN INSTRUMENT, ET PAS UN `du` DEPUIS LA VM. Le pont vers le poste de
Mike lit environ 110 fichiers par seconde : marcher `photo_thumbs/` (un fichier
par photo consultee) y prendrait des heures, et le NAS serait pire. Ce script
tourne cote WINDOWS, lance par l'agent des bancs, ou l'acces disque est natif.

CE QU'IL FAIT : il COMPTE. Il n'efface rien, ne deplace rien, n'ecrit rien
ailleurs que sur sa sortie standard. Le tri entre « regenerable » et « unique »
est une ETIQUETTE, pas une action -- c'est Mike qui tranche ensuite.

Trois zones, une par argument, parce qu'un NAS ne se mesure pas au meme rythme
qu'un disque local :

    python mesure_espace_disque.py --ou depot     # le dossier du projet
    python mesure_espace_disque.py --ou takeout   # C:\\GOOGLE PHOTOS
    python mesure_espace_disque.py --ou nas       # le fonds, premier niveau
    python mesure_espace_disque.py --ou corbeilles  # les quarantaines + leur age

Sortie ASCII pure : la console de Mike est en cp1252, et un banc qui imprime un
caractere qu'elle ne sait pas rendre fait REFUSER la livraison (paye le 07/09).
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
NAS = r"\\NAS-Bremblens\home\Photos"
TAKEOUT = r"C:\GOOGLE PHOTOS"

# Ce que le projet FABRIQUE et sait refabriquer. L'etiquette dit d'ou vient la
# certitude : un cache se refait tout seul, une quarantaine est un filet de
# securite qui a fait son temps, un rapport se refait en relancant son banc.
REGENERABLE = {
    "photo_thumbs": "cache des vignettes /api/thumb -- refait a la demande",
    "face_thumbs": "decoupes de visages -- refaites par le pipeline",
    "animal_thumbs": "decoupes d'animaux -- refaites par le pipeline",
    "dist": "bundle mono-fichier -- refait par `python bundle.py`",
    "__pycache__": "bytecode Python",
    ".venv": "environnement Python -- refait par le bat 1",
}
QUARANTAINE = "quarantaine reversible -- son role est d'etre videe"
ARCHIVE = "archive locale, jamais versionnee"


def poids(chemin, limite_s=None, t0=None):
    """(octets, fichiers, complet). Marche l'arbre en s'arretant si le temps
    imparti est depasse -- une mesure incomplete se DIT, elle ne se devine
    pas (« un plafond lu comme un resultat » a deja coute deux fois ici)."""
    o = n = 0
    complet = True
    for racine, _dirs, fichiers in os.walk(chemin, onerror=lambda e: None):
        for f in fichiers:
            try:
                o += os.path.getsize(os.path.join(racine, f))
                n += 1
            except OSError:
                pass
        if limite_s is not None and time.time() - t0 > limite_s:
            complet = False
            break
    return o, n, complet


def go(octets):
    return octets / 1_000_000_000.0


def ligne(nom, octets, n, complet, note):
    marque = "" if complet else "  (INCOMPLET)"
    print("  %-26s %9.2f Go  %8d fic.  %s%s"
          % (nom[:26], go(octets), n, note, marque))


def libre(chemin, nom):
    try:
        u = shutil.disk_usage(chemin)
        print("  %-12s total %7.1f Go   utilise %7.1f Go   LIBRE %7.1f Go  (%.0f%%)"
              % (nom, go(u.total), go(u.used), go(u.free),
                 100.0 * u.used / u.total if u.total else 0))
    except OSError as e:
        print("  %-12s illisible : %s" % (nom, e))


def zone_depot(t0):
    print("== DOSSIER DU PROJET : %s ==" % ICI)
    print()
    total_regen = total_quar = 0
    for d in sorted(p.name for p in ICI.iterdir() if p.is_dir()):
        if d == ".git":
            note = "l'historique -- JAMAIS efface"
        elif d in REGENERABLE:
            note = REGENERABLE[d]
        elif d.startswith("_corbeille") or d.startswith("_to_delete") \
                or d.startswith("_avant_"):
            note = QUARANTAINE
        elif d in ("OLD", "_bat_archive"):
            note = ARCHIVE
        elif d in ("uploads", "recuperees"):
            note = "PHOTOS -- verifier qu'elles sont au NAS avant de toucher"
        else:
            note = "source"
        o, n, c = poids(ICI / d, 220, t0)
        if o > 1_000_000 or not c:
            ligne(d, o, n, c, note)
        if d in REGENERABLE:
            total_regen += o
        elif note in (QUARANTAINE, ARCHIVE):
            total_quar += o
    print()
    print("  --> regenerable  : %.2f Go" % go(total_regen))
    print("  --> quarantaines : %.2f Go" % go(total_quar))
    print()
    # Les rapports en vrac a la racine : chacun est petit, le tas ne l'est pas.
    vrac = []
    for p in ICI.iterdir():
        if p.is_file() and p.name.startswith("_") and \
                p.suffix in (".json", ".jsonl", ".txt", ".log", ".csv", ".html"):
            try:
                vrac.append((p.stat().st_size, p.name))
            except OSError:
                pass
    vrac.sort(reverse=True)
    print("  Rapports et journaux a la racine : %d fichiers, %.1f Mo"
          % (len(vrac), sum(v[0] for v in vrac) / 1e6))
    for taille, nom in vrac[:8]:
        print("    %8.1f Mo  %s" % (taille / 1e6, nom))
    print()
    print("== ESPACE LIBRE ==")
    libre(str(ICI), "disque C:")


def zone_takeout(t0):
    print("== SAUVEGARDE GOOGLE TAKEOUT ==")
    print()
    base = Path(TAKEOUT)
    if not base.exists():
        print("  %s : ABSENT (rien a recuperer ici)" % TAKEOUT)
        return
    o, n, c = poids(base, 480, t0)
    ligne(base.name, o, n, c, "Takeout complet")
    print()
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        oo, nn, cc = poids(d, 120, t0)
        ligne(d.name, oo, nn, cc, "")
    print()
    # DE QUOI est fait l'extrait : un Takeout livre un `.json` par photo. Sans
    # ce compte, « 25 864 fichiers » se lit comme « 25 864 photos » -- et la
    # question « faut-il verser ca dans le fonds ? » se pose alors sur un
    # chiffre faux.
    exts = {}
    for f in (base / "extrait").rglob("*"):
        if f.is_file():
            e = f.suffix.lower() or "(sans)"
            o2, n2 = exts.get(e, (0, 0))
            try:
                exts[e] = (o2 + f.stat().st_size, n2 + 1)
            except OSError:
                exts[e] = (o2, n2 + 1)
    print("  De quoi l'extrait est fait :")
    for e, (o2, n2) in sorted(exts.items(), key=lambda x: -x[1][1])[:10]:
        print("    %-10s %7d fichiers  %8.2f Go" % (e, n2, go(o2)))
    print()

    zips = [p for p in base.rglob("*.zip")]
    if zips:
        oz = sum(p.stat().st_size for p in zips)
        print("  dont %d .zip = %.2f Go (les archives d'origine, si l'extrait"
              " est complet elles font double emploi)" % (len(zips), go(oz)))
    print()
    libre(TAKEOUT, "son disque")


def zone_nas(t0):
    print("== LE FONDS, AU NAS : %s ==" % NAS)
    print()
    base = Path(NAS)
    if not base.exists():
        print("  injoignable (NAS eteint ou partage non monte)")
        return
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        o, n, c = poids(d, 150, t0)
        ligne(d.name, o, n, c, "")
    print()
    libre(NAS, "le NAS")


def zone_corbeilles(t0):
    """Les quarantaines du NAS, lot par lot, avec leur AGE.

    Pourquoi l'age : `purger_corbeille.py` (bat 24) ne touche que ce qui a
    plus de N jours, et son defaut est 30. Un lot de 25 jours pese autant
    qu'un lot de 40 et ne serait PAS purge -- savoir lequel est lequel evite
    de lancer une purge qui ne rendra rien, et de croire qu'elle a echoue."""
    print("== QUARANTAINES DU NAS, LOT PAR LOT ==")
    print()
    maintenant = time.time()
    for corb in (".corbeille-rangement", ".corbeille-effacements"):
        base = Path(NAS) / corb
        if not base.exists():
            print("  %s : absent" % corb)
            continue
        print("  %s" % corb)
        total = 0
        lots = []
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            o, n, c = poids(d, 100, t0)
            try:
                age = (maintenant - d.stat().st_mtime) / 86400.0
            except OSError:
                age = -1
            lots.append((o, n, age, d.name, c))
            total += o
        for o, n, age, nom, c in sorted(lots, reverse=True):
            print("    %-34s %8.2f Go  %7d fic.  %5.0f jours%s"
                  % (nom[:34], go(o), n, age, "" if c else "  (INCOMPLET)"))
        print("    TOTAL %s : %.2f Go" % (corb, go(total)))
        vieux = sum(o for o, _n, age, _nom, _c in lots if age >= 30)
        print("    dont plus de 30 jours (ce que le bat 24 purgerait) : %.2f Go"
              % go(vieux))
        print()
    libre(NAS, "le NAS")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ou", choices=("depot", "takeout", "nas", "corbeilles"),
                    default="depot")
    a = ap.parse_args(argv)
    t0 = time.time()
    print("# mesure_espace_disque -- LECTURE SEULE, rien n'est efface")
    print()
    {"depot": zone_depot, "takeout": zone_takeout, "nas": zone_nas,
     "corbeilles": zone_corbeilles}[a.ou](t0)
    print()
    print("(%.0f s)" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
