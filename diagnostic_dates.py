"""Diagnostic : d'ou vient la date de prise de vue, photo par photo ?

Constat qui a declenche ce script (mesure du 13/08 sur le serveur en marche,
via les pages /files?dir=...&rec=1) :

    2005 :    0 / 57    dates precises  (0 %)
    2008 :    0 / 855                   (0 %)
    2010 :   34 / 1946                  (2 %)
    2016 :  406 / 1074                  (38 %)
    2019 :  515 / 601                   (86 %)
    2021 : 1445 / 1445                  (100 %)
    2024 : 2054 / 2054                  (100 %)

Autrement dit : la moitie ancienne de la photothèque n'a AUCUNE date au jour
pres — `_best_time()` y retombe sur l'annee du dossier (1er janvier a midi).
La coupure est nette et suit l'arrivee des noms de fichiers horodates
(20210612_...), ce qui fait soupconner que la date EXIF n'est JAMAIS lue et
que tout repose sur le nom de fichier.

Ce script tranche entre les deux causes possibles, sans rien modifier :

  A. La date EXIF est absente des fichiers eux-memes  -> rien a reparer,
     le perimetre « meme jour » se limite aux photos horodatees.
  B. La date EXIF existe sur le disque mais n'est pas dans l'index -> le
     backfill est en panne ou inacheve, et le reparer rend leur date a des
     milliers de photos (tri chronologique, « meme jour », frise).

LECTURE SEULE. La base est COPIEE avant lecture (le serveur en est l'ecrivain
unique) et les fichiers ne sont ouverts qu'en lecture par ExifTool.

Usage :
    python diagnostic_dates.py            # index seul (rapide, sans NAS)
    python diagnostic_dates.py --exif 30  # + relit 30 fichiers reels
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB = SCRIPT_DIR / "photos.db"
SORTIE = SCRIPT_DIR / "diagnostic_dates.txt"

RE_ANNEE = re.compile(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)')
# Meme expression que _fname_time() dans server.py : toute divergence ici
# rendrait le diagnostic faux.
RE_NOM = re.compile(r'(19\d{2}|20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})'
                    r'(?:[-_ .T]?(\d{2})[-_.]?(\d{2})[-_.]?(\d{2}))?')

lignes = []


def dire(s=""):
    print(s)
    lignes.append(s)


def annee_du_chemin(cle):
    ans = [int(a) for a in RE_ANNEE.findall(str(cle)) if 1990 <= int(a) <= 2100]
    return min(ans) if ans else 0


def date_dans_le_nom(cle):
    m = RE_NOM.search(Path(cle).name)
    if not m:
        return False
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return 1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31


def copier_la_base():
    """Copie photos.db (+ -wal, -shm) dans un dossier temporaire.

    Le serveur ecrit dans la base pendant ce temps : on ne lit donc JAMAIS
    l'originale, conformement a la regle du projet.
    """
    if not DB.exists():
        dire("photos.db introuvable : rien a diagnostiquer.")
        sys.exit(1)
    tmp = Path(tempfile.mkdtemp(prefix="diag_dates_"))
    for suffixe in ("", "-wal", "-shm"):
        src = Path(str(DB) + suffixe)
        if src.exists():
            shutil.copy2(src, tmp / src.name)
    return tmp / DB.name


def trouver_exiftool():
    """Meme recherche que ensure_exiftool() de server.py, sans jamais RENOMMER
    ni telecharger quoi que ce soit : un diagnostic ne modifie rien."""
    w = shutil.which("exiftool")
    if w:
        return Path(w)
    try:
        hits = sorted(SCRIPT_DIR.rglob("exiftool*.exe"))
    except OSError:
        hits = []
    for h in hits:
        if h.name.lower() == "exiftool.exe":
            return h
    return hits[0] if hits else None


def relire_exif(cles, exe):
    """Relit les dates EXIF de vrais fichiers, comme le fait read_dates().

    Meme invocation que server.py (argfile UTF-8 avec BOM) : sans cela les
    chemins accentues du NAS ne survivent pas au passage des arguments, et le
    diagnostic accuserait les fichiers d'une faute qui serait la notre.
    """
    args = ["-json", "-q", "-m", "-fast2", "-charset", "filename=UTF8",
            "-DateTimeOriginal", "-CreateDate", "-ModifyDate"]
    args += [str(c) for c in cles]
    argfile = None
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.args', delete=False,
                                         encoding='utf-8-sig') as tf:
            tf.write('\n'.join(args))
            argfile = tf.name
        r = subprocess.run([str(exe), "-@", argfile], capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=300)
        return json.loads(r.stdout or "[]")
    except Exception as e:                                    # noqa: BLE001
        dire(f"  ExifTool a echoue : {str(e)[:200]}")
        return []
    finally:
        if argfile:
            try:
                Path(argfile).unlink()
            except OSError:
                pass


def main():
    n_exif = 0
    if "--exif" in sys.argv:
        i = sys.argv.index("--exif")
        n_exif = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 30

    copie = copier_la_base()
    cx = sqlite3.connect(str(copie))
    par_annee = {}
    total = dict(exif=0, nom=0, taken_null=0, taken_absent=0, aucune=0,
                 failed=0, n=0)
    sans_date = []          # candidats a la relecture ExifTool

    for cle, brut in cx.execute('SELECT k, v FROM "tags"'):
        try:
            e = json.loads(brut)
        except (ValueError, TypeError):
            continue
        if not isinstance(e, dict):
            continue
        total["n"] += 1
        if e.get("failed"):
            total["failed"] += 1
            continue
        an = annee_du_chemin(cle)
        stat = par_annee.setdefault(an, dict(n=0, exif=0, nom=0, taken_null=0,
                                             taken_absent=0, aucune=0))
        stat["n"] += 1
        t = e.get("taken")
        a_exif = isinstance(t, (int, float)) and t > 0
        a_nom = date_dans_le_nom(cle)
        if a_exif:
            stat["exif"] += 1
            total["exif"] += 1
        if a_nom:
            stat["nom"] += 1
            total["nom"] += 1
        if "taken" not in e:
            stat["taken_absent"] += 1
            total["taken_absent"] += 1
        elif t is None:
            stat["taken_null"] += 1
            total["taken_null"] += 1
        if not a_exif and not a_nom:
            stat["aucune"] += 1
            total["aucune"] += 1
            if len(sans_date) < 5000:
                sans_date.append(cle)
    cx.close()
    shutil.rmtree(copie.parent, ignore_errors=True)

    dire("=== Dates de prise de vue : d'ou viennent-elles ? ===")
    dire(f"Entrees lues : {total['n']}  (dont {total['failed']} illisibles, exclues)")
    dire("")
    dire("  annee |     n |   EXIF |    nom | ni l'un ni l'autre | 'taken' absent | 'taken' null")
    for an in sorted(par_annee):
        s = par_annee[an]
        etiq = str(an) if an else "  ?  "
        dire(f"  {etiq:>5} | {s['n']:>5} | {s['exif']:>6} | {s['nom']:>6} |"
             f" {s['aucune']:>18} | {s['taken_absent']:>14} | {s['taken_null']:>12}")
    dire("")
    n_util = total["n"] - total["failed"]
    dire(f"TOTAL : {total['exif']} avec date EXIF en base, {total['nom']} datees par leur nom,")
    dire(f"        {total['aucune']} sans aucune date au jour pres sur {n_util} "
         f"({100 * total['aucune'] // max(n_util, 1)} %).")
    dire(f"        'taken' absent de l'entree : {total['taken_absent']}  "
         f"(= le backfill n'est jamais passe dessus)")
    dire(f"        'taken' a null : {total['taken_null']}  "
         f"(= ExifTool est passe et n'a rien trouve)")
    dire("")
    if total["taken_absent"] > 100:
        dire("LECTURE : backfill INACHEVE — beaucoup d'entrees n'ont jamais ete lues.")
    elif total["exif"] == 0 and total["taken_null"] > 100:
        dire("LECTURE : le backfill est passe partout et n'a JAMAIS trouve de date."
             " Un tel resultat est plus vraisemblablement une panne de lecture"
             " qu'une absence reelle : la relecture ci-dessous tranche.")
    else:
        dire("LECTURE : le backfill a tourne et trouve des dates ; ce qui manque"
             " manque peut-etre vraiment.")
    if not n_exif:
        dire("         L'index seul ne peut pas trancher : relancer avec"
             " --exif 30 pour interroger les fichiers eux-memes.")

    if n_exif and sans_date:
        exe = trouver_exiftool()
        if not exe:
            dire("")
            dire("ExifTool introuvable : relecture impossible.")
        else:
            # On echantillonne large dans la liste plutot que ses n premiers
            # elements : les 30 premieres cles sont toutes du meme dossier, et
            # un dossier n'est pas la photothèque.
            pas = max(1, len(sans_date) // n_exif)
            echantillon = [c for c in sans_date[::pas][:n_exif]
                           if str(c).startswith("\\\\") or ":" in str(c)[:3]]
            dire("")
            dire(f"=== Relecture ExifTool de {len(echantillon)} fichiers reels "
                 f"(sur {len(sans_date)} sans date) ===")
            items = relire_exif(echantillon, exe)
            avec, sans, absents = [], 0, 0
            vus = set()
            for it in items:
                src = it.get("SourceFile", "")
                vus.add(src)
                champs = {f: it.get(f) for f in
                          ("DateTimeOriginal", "CreateDate", "ModifyDate")
                          if it.get(f)}
                if champs:
                    avec.append((src, champs))
                else:
                    sans += 1
            absents = len(echantillon) - len(vus)
            dire(f"  avec une date EXIF sur le disque : {len(avec)}")
            dire(f"  sans aucune date EXIF            : {sans}")
            dire(f"  fichiers non lus (absents ?)     : {absents}")
            for src, champs in avec[:8]:
                dire(f"    + {Path(src).name} : {champs}")
            dire("")
            if avec:
                dire("VERDICT : cause B — des dates EXIF existent sur le disque et"
                     " ne sont PAS dans l'index. Le backfill est a reparer :"
                     " le reparer rend leur date a des milliers de photos.")
            else:
                dire("VERDICT : cause A — ces fichiers n'ont vraiment pas de date"
                     " EXIF. Rien a reparer ; le perimetre « meme jour » se"
                     " limite aux photos horodatees (et s'elargira au"
                     " renommage, qui inscrit la date dans le nom).")

    SORTIE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    dire("")
    dire(f"(rapport ecrit dans {SORTIE.name})")


if __name__ == "__main__":
    main()
