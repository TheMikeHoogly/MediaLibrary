"""
Controle des fichiers .bat : ASCII pur, pas de BOM.

POURQUOI
    cmd.exe relit le fichier de commandes par DECALAGE D'OCTETS apres chaque
    commande executee. Un seul caractere UTF-8 multi-octets desaligne son
    curseur : il atterrit au milieu des lignes suivantes et execute des
    fragments. Le script parait tourner mais SAUTE DES ETAPES en silence,
    y compris des etapes de verification.

USAGE
    python verifier_bat.py                 # controle tous les .bat du dossier
    python verifier_bat.py "mon fichier.bat"

    Sortie 0 = tout est propre, 1 = au moins un probleme.

    Sert aussi de hook PostToolUse (voir .claude/settings.json) : appele avec
    --hook, il lit le JSON de l'outil sur l'entree standard et sort en code 2
    pour bloquer une ecriture invalide.
"""

import json
import sys
from pathlib import Path

# Caracteres non-ASCII les plus souvent introduits, avec leur remplacement.
REMPLACEMENTS = {
    '«': '"', '»': '"', '’': "'", '‘': "'", '“': '"', '”': '"',
    '—': '-', '–': '-', '…': '...', ' ': ' ',
    '─': '-', '═': '=', '│': '|', '•': '*', '→': '->', '←': '<-',
    '✓': '+', '✗': 'x', '⚠': '!', '♻': '~', '💾': '', '🗄': '',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a', 'â': 'a',
    'ù': 'u', 'û': 'u', 'ô': 'o', 'î': 'i', 'ï': 'i', 'ç': 'c',
    'É': 'E', 'È': 'E', 'À': 'A', 'Ô': 'O', 'Ç': 'C',
}


def controler(chemin):
    """Renvoie une liste de problemes (vide si le fichier est bon)."""
    chemin = Path(chemin)
    problemes = []
    brut = chemin.read_bytes()

    if brut.startswith(b'\xef\xbb\xbf'):
        problemes.append("BOM UTF-8 en tete : cmd.exe le prend pour une commande")

    # Fins de ligne : cmd.exe exige CRLF. Un .bat en LF pur (ecrit depuis un
    # editeur/sandbox Unix) desaligne le parseur sur les blocs multi-lignes
    # (if (...), choice suivi de if errorlevel) et fait echouer le script avec
    # "qui etait inattendu". Meme classe de bug que le non-ASCII : silencieux.
    n_lf = brut.count(b'\n')
    n_crlf = brut.count(b'\r\n')
    if n_lf and n_crlf != n_lf:
        manque = n_lf - n_crlf
        problemes.append(
            f"fins de ligne : {manque} ligne(s) en LF au lieu de CRLF"
            "   -> convertir en CRLF (cmd.exe deraille sur les blocs "
            "multi-lignes : \"qui etait inattendu\")")

    texte = brut.decode('utf-8', errors='replace')
    for num, ligne in enumerate(texte.splitlines(), 1):
        fautifs = sorted({c for c in ligne if ord(c) > 127})
        if fautifs:
            suggest = ''.join(REMPLACEMENTS.get(c, '?') for c in fautifs)
            problemes.append(
                f"l.{num} : {' '.join(repr(c) for c in fautifs)}"
                f"   -> remplacer par {suggest!r}"
                f"\n         {ligne.strip()[:70]}")
    return problemes


def rapport(fichiers):
    total = 0
    for f in fichiers:
        pbs = controler(f)
        if pbs:
            total += len(pbs)
            print(f"  x {Path(f).name}")
            for p in pbs:
                print(f"      {p}")
        else:
            print(f"  + {Path(f).name}")
    print()
    if total:
        print(f"  {total} probleme(s). Un .bat non-ASCII saute des etapes")
        print("  en silence : corrige avant de le lancer.")
    else:
        print("  Tous les .bat sont en ASCII pur.")
    return 1 if total else 0


def mode_hook():
    """Hook PostToolUse : bloque l'ecriture d'un .bat invalide."""
    try:
        charge = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    chemin = (charge.get('tool_input') or {}).get('file_path') or ''
    if not chemin.lower().endswith('.bat'):
        return 0
    p = Path(chemin)
    if not p.exists():
        return 0
    pbs = controler(p)
    if not pbs:
        return 0
    print(f"REGLE PROJET VIOLEE — {p.name} contient des caracteres non-ASCII.\n"
          "cmd.exe relit les .bat par decalage d'octets : ces caracteres vont\n"
          "desaligner son parseur, qui executera des fragments de lignes et\n"
          "SAUTERA des etapes en silence (y compris les verifications).\n"
          "Corrige le fichier maintenant :\n\n"
          + "\n".join("  " + x for x in pbs), file=sys.stderr)
    return 2                       # 2 = bloquant, le message remonte a Claude


def main():
    if '--hook' in sys.argv:
        return mode_hook()
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    fichiers = ([Path(a) for a in args] if args
                else sorted(Path(__file__).resolve().parent.glob('*.bat')))
    if not fichiers:
        print("  Aucun fichier .bat trouve.")
        return 0
    print(f"  Controle de {len(fichiers)} fichier(s) .bat")
    print("  " + "-" * 56)
    return rapport(fichiers)


if __name__ == '__main__':
    sys.exit(main())
