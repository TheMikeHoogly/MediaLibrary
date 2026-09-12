"""Le dossier est-il enumere DEUX fois par page /files en mode recursif ?

L'horloge de phases dit que `parcours` coute 660 a 800 ms sur les 1,5 a 1,9 s
de `GET /files` pour 2 519 photos -- et seulement 15,6 ms de CPU. C'est donc
de l'ATTENTE, pas du calcul : le partage SMB repond, on attend.

En lisant `_lister_dossier(rec=True)` on voit deux enumerations du MEME
dossier de tete :

  1. `os.walk(dossier)` -- qui commence par un `scandir` du dossier de tete,
     et dont le PREMIER tuple porte deja la liste de ses sous-dossiers ;
  2. `os.scandir(dossier)` juste apres, pour fabriquer cette meme liste.

La seconde ne rend rien que la premiere n'ait deja vu. Ce banc mesure ce
qu'elle coute, et PROUVE que la variante qui s'en passe rend exactement les
memes fichiers et les memes sous-dossiers.

Trois variantes, tours alternes (A B A B ...) pour que le cache du partage ne
favorise pas celle qui passe en premier :

  A   l'ecriture actuelle  : os.walk + os.scandir
  B   une seule passe      : os.walk, sous-dossiers pris dans le 1er tuple
  C   la seconde passe seule (ce qu'on espere economiser)

Rien n'est ecrit, rien n'est deplace : ce banc LIT un dossier.

  mesure_enumeration_dossier.py --dossier "Photos Mike/2022"
  mesure_enumeration_dossier.py --dossier "Photos Papa" --tours 5
"""
import argparse
import os
import statistics
import sys
import time
from pathlib import Path

MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff',
             '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp'}
SCRIPT_DIR = Path(__file__).resolve().parent


def racines():
    """Les racines navigables, lues comme le serveur les lit."""
    out, vues = [], set()
    for nom in ('dossiers_a_taguer.txt', 'dossiers_a_explorer.txt'):
        p = SCRIPT_DIR / nom
        if not p.is_file():
            continue
        for ligne in p.read_text(encoding='utf-8', errors='replace').splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith('#'):
                continue
            if ligne.lower() in vues:
                continue
            vues.add(ligne.lower())
            out.append(Path(ligne))
    return out


def resoudre(arg):
    """Un chemin absolu, ou un chemin relatif a une racine navigable."""
    p = Path(arg)
    if p.is_absolute() and p.is_dir():
        return p
    for r in racines():
        c = r / arg
        if c.is_dir():
            return c
        if r.name.lower() == arg.split('/')[0].lower():
            c = r.parent / arg
            if c.is_dir():
                return c
    return None


# --------------------------- les trois variantes ---------------------------

def variante_a(dossier):
    """L'ecriture actuelle de `_lister_dossier(rec=True)`, a l'identique."""
    fichiers, sous = [], []
    for racine, dirs, noms in os.walk(dossier):
        dirs[:] = [d for d in dirs if not d.startswith(('.', '@', '#'))]
        rp = Path(racine)
        for n in noms:
            if n.startswith(('.', '@', '#')):
                continue
            if os.path.splitext(n)[1].lower() in MEDIA_EXT:
                fichiers.append(rp / n)
    with os.scandir(dossier) as it:
        for e in it:
            if not e.name.startswith(('.', '@', '#')) and e.is_dir():
                sous.append(Path(e.path))
    sous.sort(key=lambda x: x.name.lower())
    return fichiers, sous


def variante_b(dossier):
    """Une seule enumeration : les sous-dossiers viennent du 1er tuple.

    `os.walk` descend en TETE (top-down) : son premier tuple est celui du
    dossier demande, et son `dirs` -- deja elague -- EST la liste cherchee.
    Le `premier` garde la trace du passage : si `os.walk` n'a rien rendu
    (dossier illisible, qu'il avale en silence), on refait le `scandir` pour
    lever la MEME erreur que l'ecriture actuelle, au lieu de rendre une page
    vide."""
    fichiers, sous = [], []
    premier = True
    for racine, dirs, noms in os.walk(dossier):
        dirs[:] = [d for d in dirs if not d.startswith(('.', '@', '#'))]
        rp = Path(racine)
        if premier:
            sous = [rp / d for d in dirs]
            premier = False
        for n in noms:
            if n.startswith(('.', '@', '#')):
                continue
            if os.path.splitext(n)[1].lower() in MEDIA_EXT:
                fichiers.append(rp / n)
    if premier:
        with os.scandir(dossier) as it:
            for e in it:
                if not e.name.startswith(('.', '@', '#')) and e.is_dir():
                    sous.append(Path(e.path))
    sous.sort(key=lambda x: x.name.lower())
    return fichiers, sous


def variante_c(dossier):
    """La seconde passe SEULE : ce que la variante B economise."""
    sous = []
    with os.scandir(dossier) as it:
        for e in it:
            if not e.name.startswith(('.', '@', '#')) and e.is_dir():
                sous.append(Path(e.path))
    sous.sort(key=lambda x: x.name.lower())
    return [], sous


def chrono(fn, dossier):
    t0 = time.perf_counter()
    c0 = time.process_time()
    fichiers, sous = fn(dossier)
    return ((time.perf_counter() - t0) * 1000.0,
            (time.process_time() - c0) * 1000.0, fichiers, sous)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dossier', required=True)
    ap.add_argument('--tours', type=int, default=4)
    a = ap.parse_args(argv)

    dossier = resoudre(a.dossier)
    if dossier is None:
        print("Dossier introuvable : %s" % a.dossier)
        print("Racines connues :")
        for r in racines():
            print("  %s" % r)
        return 2

    print("Dossier : %s" % dossier)
    print("Tours   : %d, alternes A B C" % a.tours)
    print("")

    mesures = {'A': [], 'B': [], 'C': []}
    cpus = {'A': [], 'B': [], 'C': []}
    ref_f = ref_s = None
    ecarts = []

    for tour in range(1, a.tours + 1):
        for nom, fn in (('A', variante_a), ('B', variante_b), ('C', variante_c)):
            ms, cpu, fichiers, sous = chrono(fn, dossier)
            mesures[nom].append(ms)
            cpus[nom].append(cpu)
            if nom == 'A':
                if ref_f is None:
                    ref_f = sorted(str(p) for p in fichiers)
                    ref_s = sorted(str(p) for p in sous)
                print("  tour %d  A %8.1f ms (%6.1f ms CPU)  %5d fichiers, "
                      "%d sous-dossiers" % (tour, ms, cpu, len(fichiers), len(sous)))
            elif nom == 'B':
                gf = sorted(str(p) for p in fichiers)
                gs = sorted(str(p) for p in sous)
                if gf != ref_f:
                    ecarts.append("tour %d : B ne rend pas les memes fichiers "
                                  "(%d contre %d)" % (tour, len(gf), len(ref_f)))
                if gs != ref_s:
                    ecarts.append("tour %d : B ne rend pas les memes "
                                  "sous-dossiers (%r contre %r)" % (tour, gs, ref_s))
                print("  tour %d  B %8.1f ms (%6.1f ms CPU)  %5d fichiers, "
                      "%d sous-dossiers" % (tour, ms, cpu, len(gf), len(gs)))
            else:
                print("  tour %d  C %8.1f ms (%6.1f ms CPU)  la 2e passe seule"
                      % (tour, ms, cpu))
        print("")

    def med(v):
        return statistics.median(v)

    print("--------------------------------------------------------------")
    print("                  mediane        min        max     CPU median")
    for nom, libelle in (('A', 'A actuelle  '), ('B', 'B une passe '),
                         ('C', 'C 2e passe  ')):
        v = mesures[nom]
        print("%s %9.1f ms %8.1f %10.1f %10.1f ms"
              % (libelle, med(v), min(v), max(v), med(cpus[nom])))
    print("")
    ga = med(mesures['A'])
    gb = med(mesures['B'])
    print("Economie mesuree : %.1f ms par page (%.0f %% du parcours), et la "
          "2e passe" % (ga - gb, 100.0 * (ga - gb) / ga if ga else 0.0))
    print("seule pese %.1f ms." % med(mesures['C']))
    print("")
    if ecarts:
        print("ECART -- la variante B ne rend PAS la meme chose :")
        for e in ecarts:
            print("  %s" % e)
        return 1
    print("Identite verifiee : sur %d tours, B rend exactement les memes "
          "fichiers" % a.tours)
    print("et les memes sous-dossiers que A, chemin par chemin.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
