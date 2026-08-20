#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nettoyage de fin de session — MediaLibrary.

Deux volets, tous deux SURS :

1. Quarantaine REVERSIBLE des repertoires/fichiers de travail ephemeres a la
   RACINE du projet. Rien n'est supprime : les elements sont DEPLACES dans
   `_corbeille_session/AAAA-MM-JJ/` avec un `manifest.json` qui note leur
   origine (pour tout remettre). Mike vide la corbeille quand il veut.

   Liste BLANCHE stricte (seul ce qui matche part) — a la racine uniquement :
     - dossiers dont le nom commence par `--`  (arguments CLI mal parses en chemin)
     - dossiers `__pycache__`                   (regenerables)
     - dossiers vides de la liste EXTRA         (before, 5, ... — si vides)
     - fichiers `.fuse_hidden*`                 (restes FUSE/SMB de fichiers ouverts)
     - fichiers `*.pyc`                         (regenerables)
   Tout le reste est PRESERVE. En particulier : _bat_archive, recuperees,
   *_thumbs, .git, .venv, docs, ui, eval, uploads, dist, exiftool-*, et tous
   les fichiers source/donnees.

2. Lint de COHERENCE des fichiers de suivi *.md (references orphelines, bloat,
   fraicheur des dates). Purement informatif : n'ecrit rien, code de sortie 0.

Usage :
    python nettoyer_session.py            # rapport a blanc (ne deplace rien)
    python nettoyer_session.py --appliquer   # applique la quarantaine
    python nettoyer_session.py --lint-only   # seulement le lint *.md

Aucune dependance externe (stdlib pure), aucun import du serveur.
"""

import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
QUARANTINE_ROOT = SCRIPT_DIR / "_corbeille_session"

# --- Volet 1 : quarantaine -------------------------------------------------

# Dossiers ephemeres connus a deplacer UNIQUEMENT s'ils sont vides (evite de
# happer un vrai dossier qui porterait ce nom par hasard).
EXTRA_EMPTY_DIRS = {"before", "5"}

# Jamais toucher, meme si une regle matchait (garde-fou dur).
NEVER = {".git", ".venv", "_corbeille_session"}


def _dir_size(p: Path) -> int:
    total = 0
    try:
        for f in p.rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


def _is_empty_dir(p: Path) -> bool:
    try:
        next(p.iterdir())
        return False
    except StopIteration:
        return True
    except OSError:
        return False


def _human(n: int) -> str:
    units = ["o", "Ko", "Mo", "Go", "To"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024
        i += 1
    return (f"{f:.1f} {units[i]}") if i else (f"{n} o")


def collect_candidates():
    """Retourne la liste des chemins racine a mettre en quarantaine, avec un
    motif lisible. Racine du projet uniquement."""
    out = []
    for child in sorted(SCRIPT_DIR.iterdir(), key=lambda p: p.name.lower()):
        name = child.name
        if name in NEVER:
            continue
        if child.is_dir():
            if name.startswith("--"):
                out.append((child, "dossier d'argument CLI mal parse (--...)"))
            elif name == "__pycache__":
                out.append((child, "cache Python (regenerable)"))
            elif name in EXTRA_EMPTY_DIRS and _is_empty_dir(child):
                out.append((child, "dossier de travail vide"))
        elif child.is_file():
            if name.startswith(".fuse_hidden"):
                out.append((child, "reste FUSE/SMB (fichier ouvert supprime)"))
            elif name.endswith(".pyc"):
                out.append((child, "bytecode Python (regenerable)"))
    return out


def report_quarantine(cands):
    if not cands:
        print("  (rien a nettoyer — racine propre)")
        return
    total = 0
    for p, why in cands:
        size = _dir_size(p) if p.is_dir() else (p.stat().st_size if p.exists() else 0)
        total += size
        kind = "DIR " if p.is_dir() else "FILE"
        print(f"  {kind} {p.name:<28} {_human(size):>10}   {why}")
    print(f"  --> {len(cands)} element(s), {_human(total)} au total.")


def apply_quarantine(cands):
    if not cands:
        print("  (rien a deplacer)")
        return
    dest = QUARANTINE_ROOT / date.today().isoformat()
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = dest / "manifest.json"
    manifest = []
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = []
    moved = 0
    for p, why in cands:
        if not p.exists():
            continue
        target = dest / p.name
        # collision : suffixe numerique
        n = 1
        while target.exists():
            target = dest / f"{p.name}.{n}"
            n += 1
        try:
            shutil.move(str(p), str(target))
            manifest.append({
                "origine": str(p),
                "quarantaine": str(target),
                "motif": why,
                "a": datetime.now().isoformat(timespec="seconds"),
            })
            moved += 1
            print(f"  deplace : {p.name}  ->  {target.relative_to(SCRIPT_DIR)}")
        except OSError as e:
            print(f"  ECHEC   : {p.name}  ({e})")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  --> {moved} element(s) en quarantaine dans "
          f"{dest.relative_to(SCRIPT_DIR)}")
    print("      Reversible : contenu deplace, origine notee dans manifest.json.")


# --- Volet 2 : lint des *.md de suivi --------------------------------------

# Docs de suivi + seuil de bloat (octets). None = pas de seuil (juste refs/dates).
TRACKING_MD = {
    # 8 000 → 8 500 le 20/08 : le troisième canal (les bancs) a ajouté une
    # ligne au tableau des fichiers et un paragraphe au protocole. Le seuil
    # reste SERRÉ, et volontairement loin des 50 000 de DECISIONS : ce
    # fichier-ci est relu à CHAQUE session, il coûte des tokens à chaque fois
    # et il rivalise avec le reste pour l'attention. Un budget large ici
    # rendrait le brief bavard, et un brief bavard n'est plus lu.
    "CLAUDE.md": 8500,
    "ROADMAP.md": 12000,
    "PROMPT_NOUVELLE_SESSION.md": 4000,
    # 9 000 → 12 000 le 19/08, puis 50 000 le 20/08 — deux décisions de Mike,
    # même raison : chaque session ajoute des verdicts qu'aucune ne peut
    # retirer, c'est la raison d'être du fichier, et condenser rongeait la
    # PRÉCISION des raisons, ce que le seuil était censé protéger.
    # À 50 000 le seuil ne protège plus contre le RÉCIT — il ne rattrape
    # qu'un emballement franc. Ce qui protège du récit est la FORME : un
    # tableau, une ligne par verdict, un chiffre dans chaque raison.
    "eval/DECISIONS.md": 50000,
    # Sorti de DECISIONS.md le 20/08 : découpage par DOMAINE, non par statut
    # (l'archive par âge avait été rejetée la veille — elle obligeait à relire
    # les deux fichiers). Ici l'outillage : les trois canaux, le pilotage, la
    # livraison git. Qui travaille la recherche n'a jamais besoin de savoir
    # pourquoi `taskkill` a échoué.
    "docs/DECISIONS_OUTILLAGE.md": 50000,
    # Sorti de DECISIONS.md le 16/08 : « ce qui a ete tranche » d'un cote,
    # « comment on tranche » de l'autre. Budget propre pour que le corpus de
    # methode soit GOUVERNE et non pas soustrait au lint.
    "eval/METHODE.md": 6000,
    "README.md": None,
    "INSTALLATION.md": None,
}

# Reference a un autre .md : capture les chemins type docs/x.md, eval/x.md, x.md
MD_REF = re.compile(r"`?([\w./-]+\.md)`?")
DATE_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "aout": 8, "août": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}
DATE_TXT = re.compile(r"\b(\d{1,2})\s+([A-Za-zéûôça]+)\s+(\d{4})\b")


def _dates_in(text):
    found = []
    for d, m, y in DATE_DMY.findall(text):
        try:
            found.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for d, mname, y in DATE_TXT.findall(text):
        mi = MONTHS.get(mname.lower())
        if mi:
            try:
                found.append(date(int(y), mi, int(d)))
            except ValueError:
                pass
    return found


def _known_md_names():
    """Noms de base de tous les .md du projet (racine + eval + docs), pour
    tolerer les raccourcis (ex. `DECISIONS.md` pour `eval/DECISIONS.md`)."""
    names = set()
    for d in (SCRIPT_DIR, SCRIPT_DIR / "eval", SCRIPT_DIR / "docs"):
        try:
            for p in d.glob("*.md"):
                names.add(p.name)
        except OSError:
            pass
    return names


def lint_md():
    warns = []
    today = date.today()
    known = _known_md_names()
    for rel, budget in TRACKING_MD.items():
        p = SCRIPT_DIR / rel
        if not p.exists():
            if rel in ("CLAUDE.md", "ROADMAP.md", "PROMPT_NOUVELLE_SESSION.md",
                       "eval/DECISIONS.md", "docs/DECISIONS_OUTILLAGE.md"):
                warns.append(f"MANQUANT  {rel} — doc de suivi attendu, absent.")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        size = p.stat().st_size

        # bloat
        if budget is not None and size > budget:
            warns.append(f"BLOAT     {rel} — {_human(size)} > seuil "
                         f"{_human(budget)} : a condenser "
                         f"(le detail vit dans git).")

        # references orphelines
        for ref in sorted(set(MD_REF.findall(text))):
            if ref.lower().startswith("http") or "://" in ref:
                continue
            # resout relativement a la racine ET au dossier du doc
            cand1 = SCRIPT_DIR / ref
            cand2 = (p.parent / ref)
            # Raccourci tolere : un nom de base qui existe ailleurs dans le
            # projet (racine/eval/docs) n'est pas orphelin.
            if (not cand1.exists() and not cand2.exists()
                    and Path(ref).name not in known):
                warns.append(f"REF-ORPHE {rel} cite `{ref}` — introuvable.")

        # fraicheur : date la plus recente citee dans le doc
        ds = _dates_in(text)
        if rel in ("ROADMAP.md", "PROMPT_NOUVELLE_SESSION.md") and ds:
            newest = max(ds)
            age = (today - newest).days
            if age > 21:
                warns.append(f"DATE-VIEIL {rel} — date la plus recente "
                             f"{newest.isoformat()} ({age} j) : l'etat semble "
                             f"perime, verifier.")

    if not warns:
        print("  (docs de suivi coherents : pas de reference orpheline, "
              "pas de bloat, dates fraiches)")
    else:
        for w in warns:
            print("  " + w)
    return warns


# --- Entree ----------------------------------------------------------------

def main(argv):
    apply = "--appliquer" in argv
    lint_only = "--lint-only" in argv

    if not lint_only:
        print("== Nettoyage des repertoires de travail "
              "(quarantaine reversible) ==")
        cands = collect_candidates()
        if apply:
            apply_quarantine(cands)
        else:
            report_quarantine(cands)
            if cands:
                print("      (rapport a blanc — relance avec --appliquer "
                      "pour deplacer)")
        print()

    print("== Lint de coherence des fichiers de suivi *.md ==")
    lint_md()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
