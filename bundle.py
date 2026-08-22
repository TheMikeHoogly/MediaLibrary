#!/usr/bin/env python3
"""bundle.py — cuit les assets ui/ dans une copie mono-fichier du serveur.

Le serveur lit ui/tokens.css + ui/base.css au demarrage et les injecte sur
chaque page (voir server.ui_shared_css / _send_html). Deployer suppose donc de
copier server.py ET le dossier ui/. Pour garder la promesse « un seul fichier a
deployer, zero build », ce script produit dist/server.py dont le cache CSS est
DEJA REMPLI : il sert le design system meme sans dossier ui/.

Mecanisme (volontairement local et sans magie de texte sur les pages) : on
remplace la ligne d'initialisation « _UI_CACHE = {"css": None, "sig": None} »
par un cache pre-rempli, associe a la signature que _ui_signature() renvoie
quand ui/ est ABSENT (mtimes/tailles a zero). Consequence :

  - deploiement SANS ui/  -> la signature correspond -> CSS cuit servi ;
  - deploiement AVEC ui/  -> la signature differe    -> fichiers ui/ relus
                                                          (le bundle reste a jour).

Usage : python bundle.py [--sortie dist/server.py]
"""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
UI_DIR = SCRIPT_DIR / "ui"
UI_GLOBAL_FILES = ("tokens.css", "base.css")   # DOIT refleter server._UI_GLOBAL_FILES
MARQUEUR = '_UI_CACHE = {"css": None, "sig": None}'
# Gabarits de pages sortis du monolithe (point 7). Meme principe que le CSS :
# le dist embarque ce que ui/pages/ contient, donc il se deploie seul.
UI_PAGES_DIR = UI_DIR / "pages"
MARQUEUR_PAGES = '_UI_PAGES_CUIT = {}             # rempli par bundle.py — NE PAS renommer'


def construire_css():
    """Reproduit exactement le bloc que server.ui_shared_css() assemble."""
    parts = []
    for name in UI_GLOBAL_FILES:
        txt = (UI_DIR / name).read_text(encoding="utf-8")
        if txt.strip():
            parts.append(f"/* {name} */\n{txt}")
    if not parts:
        return ""
    return '<style id="ui-shared">\n' + "\n".join(parts) + "\n</style>"


def signature_absente():
    """Signature renvoyee par server._ui_signature() quand ui/ est absent."""
    return tuple((name, 0, 0) for name in UI_GLOBAL_FILES)


def cuire_les_pages():
    """{nom: gabarit} pour tout ui/pages/*.html. Vide si le dossier est absent."""
    pages = {}
    if UI_PAGES_DIR.is_dir():
        for f in sorted(UI_PAGES_DIR.glob("*.html")):
            pages[f.stem] = f.read_text(encoding="utf-8")
    return pages


def main(argv):
    sortie = Path("dist/server.py")
    if "--sortie" in argv:
        sortie = Path(argv[argv.index("--sortie") + 1])

    src = (SCRIPT_DIR / "server.py").read_text(encoding="utf-8")
    if MARQUEUR not in src:
        print("ERREUR : marqueur de cache introuvable dans server.py.")
        print(f"  Attendu : {MARQUEUR}")
        print("  (server.py a-t-il change ? mettre a jour bundle.py.)")
        return 2

    css = construire_css()
    if not css:
        print("ERREUR : aucun CSS lu dans ui/ (tokens.css / base.css).")
        return 2

    remplacement = f'_UI_CACHE = {{"css": {css!r}, "sig": {signature_absente()!r}}}'
    out = src.replace(MARQUEUR, remplacement, 1)

    # Les gabarits : sans eux, un dist sans ui/ servirait « Gabarit
    # introuvable » a la place des pages extraites.
    pages = cuire_les_pages()
    if pages:
        if MARQUEUR_PAGES not in out:
            print("ERREUR : marqueur des gabarits introuvable dans server.py.")
            print(f"  Attendu : {MARQUEUR_PAGES}")
            return 2
        out = out.replace(MARQUEUR_PAGES, f'_UI_PAGES_CUIT = {pages!r}', 1)

    dst = (SCRIPT_DIR / sortie) if not sortie.is_absolute() else sortie
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8")
    print(f"OK : {dst}")
    print(f"  CSS cuit : {len(css)} caracteres depuis {', '.join(UI_GLOBAL_FILES)}")
    if pages:
        print(f"  Gabarits cuits : {len(pages)} page(s) — "
              + ", ".join(sorted(pages)))
    else:
        print("  Gabarits cuits : aucun (ui/pages/ absent ou vide).")
    print("  Ce fichier sert le design system meme sans dossier ui/.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
