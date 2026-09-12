"""La date de CREATION d'un fichier a-t-elle survecu au tagueur ?

`exiftool` est appele sans `-P` : chaque ecriture de tags reecrit la date de
MODIFICATION du fichier. Mesure du 12/09 sur `_Uploads` : les 213 images
portent toutes le 05/09 (debut de la campagne), les 35 videos le 01/09 (le
tagueur ne les touche pas).

Mais Windows tient DEUX dates : la modification et la CREATION. `exiftool`
ecrit dans un temporaire puis remplace l'original -- selon la maniere dont il
remplace, la date de creation est conservee ou refaite. Ce banc le mesure au
lieu de le supposer. C'est la question qui decide si la date de copie d'un
fichier est encore recuperable, ou perdue pour de bon.

Sous Windows, `os.stat().st_ctime` EST la date de creation (ailleurs, c'est la
date de changement d'inode : le banc le dit et s'arrete).

Rien n'est ecrit, rien n'est deplace.

  mesure_dates_fichiers.py --dossier b64:...           (un dossier)
  mesure_dates_fichiers.py --dossier ... --limite 400
"""
import argparse
import os
import sys
import time
from collections import Counter
from pathlib import Path

MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff',
             '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp'}
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff',
             '.heic', '.heif'}
SCRIPT_DIR = Path(__file__).resolve().parent


def racines():
    out, vues = [], set()
    for nom in ('dossiers_a_taguer.txt', 'dossiers_a_explorer.txt',
                'dossier_uploads.txt'):
        p = SCRIPT_DIR / nom
        if not p.is_file():
            continue
        for ligne in p.read_text(encoding='utf-8', errors='replace').splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith('#') or ligne.lower() in vues:
                continue
            vues.add(ligne.lower())
            out.append(Path(ligne))
    return out


def resoudre(arg):
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


def jour(t):
    return time.strftime('%Y-%m-%d', time.localtime(t))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dossier', required=True)
    ap.add_argument('--limite', type=int, default=400)
    a = ap.parse_args(argv)

    if os.name != 'nt':
        print("Ce banc ne veut rien dire hors de Windows : ailleurs,")
        print("st_ctime est la date de changement d inode, pas la creation.")
        return 2

    d = resoudre(a.dossier)
    if d is None:
        print("Dossier introuvable : %s" % a.dossier)
        for r in racines():
            print("  racine : %s" % r)
        return 2

    print("Dossier : %s" % d)
    fichiers = []
    for r, dirs, noms in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith(('.', '@', '#'))]
        for n in noms:
            if n.startswith(('.', '@', '#')):
                continue
            if os.path.splitext(n)[1].lower() in MEDIA_EXT:
                fichiers.append(Path(r) / n)
                if len(fichiers) >= a.limite:
                    break
        if len(fichiers) >= a.limite:
            break
    print("Examines : %d fichier(s) (limite %d)" % (len(fichiers), a.limite))
    print("")

    jours_m = {'image': Counter(), 'video': Counter()}
    jours_c = {'image': Counter(), 'video': Counter()}
    creation_plus_ancienne = 0
    egales = 0
    creation_plus_recente = 0
    exemples = []
    for f in fichiers:
        try:
            st = f.stat()
        except OSError:
            continue
        fam = 'image' if f.suffix.lower() in IMAGE_EXT else 'video'
        jours_m[fam][jour(st.st_mtime)] += 1
        jours_c[fam][jour(st.st_ctime)] += 1
        ecart = st.st_mtime - st.st_ctime
        if ecart > 2:
            creation_plus_ancienne += 1
            if len(exemples) < 5:
                exemples.append((f.name, jour(st.st_ctime), jour(st.st_mtime)))
        elif ecart < -2:
            creation_plus_recente += 1
        else:
            egales += 1

    print("CREATION plus ancienne que la modification : %d" % creation_plus_ancienne)
    print("les deux a moins de 2 s                    : %d" % egales)
    print("CREATION plus recente                      : %d" % creation_plus_recente)
    print("")
    for fam in ('image', 'video'):
        tot = sum(jours_m[fam].values())
        if not tot:
            continue
        print("-- %s (%d) --" % (fam, tot))
        print("   modification : %d jour(s) distinct(s) : %s"
              % (len(jours_m[fam]),
                 ', '.join('%s x%d' % (j, n)
                           for j, n in sorted(jours_m[fam].items())[:6])))
        print("   CREATION     : %d jour(s) distinct(s) : %s"
              % (len(jours_c[fam]),
                 ', '.join('%s x%d' % (j, n)
                           for j, n in sorted(jours_c[fam].items())[:6])))
    if exemples:
        print("")
        print("Exemples (nom, creation, modification) :")
        for e in exemples:
            print("   %-44s %s -> %s" % e)
    print("")
    print("Lecture : si la CREATION porte beaucoup de jours distincts la ou la")
    print("modification n en porte qu un ou deux, la date de copie a survecu au")
    print("tagueur et reste recuperable.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
