"""Ou part le temps d'une page /files ? Le NAS, ou le Python ?

L'horloge des routes a dit QUELLE route coute (GET /files : 31,4 s au pire
le 10/09). Elle ne dit pas OU. Ce banc mesure les deux suspects, separement,
sans toucher au serveur qui tourne :

  1. LE PARCOURS DU DOSSIER. `_serve_gallery` liste le dossier avec
     `folder.iterdir()` puis interroge CHAQUE entree par `f.is_file()`, et
     recommence pour `e.is_dir()`. Sur un partage SMB, chaque `is_file()` est
     un aller-retour reseau : un dossier de 2 000 photos coute 2 000 requetes
     la ou `os.scandir()` en coute UNE -- Windows livre le type et la taille
     avec la ligne du repertoire. C'est l'hypothese n° 1, et elle se mesure.

  2. LE BALAYAGE DE L'INDEX. `_index_entries_under` parcourt les ~43 000
     entrees de l'index a CHAQUE requete, en construisant un objet `Path` par
     cle (`_pkey`). Le cout ne depend pas du dossier demande : le meme prix
     pour un dossier de 3 photos que pour un de 3 000.

Rien n'est ecrit, rien n'est deplace : ce banc LIT un dossier et une COPIE de
la base (`copie.db` par defaut, jamais `photos.db` -- la base vivante est
ouverte par le serveur, et un banc n'a pas a s'y appuyer).

  mesure_parcours_dossier.py --dossier "Photos Mike/2022"
  mesure_parcours_dossier.py --dossier "Photos Flo" --tours 3
  mesure_parcours_dossier.py --sans-index          (parcours seulement)
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff',
             '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp'}
SCRIPT_DIR = Path(__file__).resolve().parent


# ───────────────────────────── racines ──────────────────────────────────────

def racines():
    """Les racines navigables, lues comme le serveur les lit."""
    out = []
    vues = set()
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
    """`--dossier` : chemin absolu, ou relatif a la premiere racine."""
    if not arg:
        rs = racines()
        return rs[0] if rs else None
    p = Path(arg)
    if p.is_absolute() or str(p).startswith('\\\\'):
        return p
    for r in racines():
        c = r / arg
        if c.is_dir():
            return c
    return None


# ─────────────────────── 1. le parcours du dossier ──────────────────────────

def par_iterdir(dossier):
    """Ce que fait `_serve_gallery` aujourd'hui : deux passes, un `is_*()` par
    entree. Chaque `is_file()` est un `stat()` -- reseau sur un partage SMB."""
    fichiers = [f for f in dossier.iterdir()
                if f.is_file() and f.suffix.lower() in MEDIA_EXT
                and not f.name.startswith(('.', '@', '#'))]
    sous = sorted([e for e in dossier.iterdir() if e.is_dir()
                   and not e.name.startswith(('.', '@', '#'))],
                  key=lambda x: x.name.lower())
    return len(fichiers), len(sous)


def par_scandir(dossier):
    """La meme reponse en UNE passe, sans un seul stat() supplementaire :
    `os.scandir` porte le type dans la ligne du repertoire."""
    fichiers, sous = [], []
    with os.scandir(dossier) as it:
        for e in it:
            if e.name.startswith(('.', '@', '#')):
                continue
            if e.is_file():
                if os.path.splitext(e.name)[1].lower() in MEDIA_EXT:
                    fichiers.append(e.name)
            elif e.is_dir():
                sous.append(e.name)
    sous.sort(key=str.lower)
    return len(fichiers), len(sous)


def par_scandir_stat(dossier):
    """`os.scandir` + `entry.stat()` : le type ET la taille ET la date. Sous
    Windows ces trois champs viennent de la MEME ligne de repertoire, donc
    `stat()` ne coute rien de plus -- c'est ce qui permettrait de servir une
    photo pas encore indexee sans un aller-retour par fichier."""
    n = octets = 0
    sous = 0
    with os.scandir(dossier) as it:
        for e in it:
            if e.name.startswith(('.', '@', '#')):
                continue
            if e.is_file():
                if os.path.splitext(e.name)[1].lower() in MEDIA_EXT:
                    n += 1
                    octets += e.stat().st_size
            elif e.is_dir():
                sous += 1
    return n, sous


def mesurer_parcours(dossier, tours):
    """Alterne les methodes pour que le cache SMB ne favorise pas la seconde.

    L'ordre compte : mesurer A puis B donne a B un repertoire deja chaud dans
    le cache du client SMB, et B parait meilleur qu'il n'est. On alterne donc,
    et on rapporte le PREMIER tour (froid) et le MEILLEUR (chaud) : le premier
    est ce que vit Mike quand il ouvre un dossier qu'il n'a pas vu depuis une
    heure, le meilleur est le plancher de la methode."""
    methodes = [('iterdir + is_file (actuel)', par_iterdir),
                ('os.scandir', par_scandir),
                ('os.scandir + stat', par_scandir_stat)]
    releves = {nom: [] for nom, _ in methodes}
    compte = {}
    for tour in range(tours):
        for nom, f in methodes:
            t0 = time.perf_counter()
            try:
                n, s = f(dossier)
            except OSError as e:
                print(f'  ECHEC {nom} : {e}')
                return None
            releves[nom].append(time.perf_counter() - t0)
            compte[nom] = (n, s)
    return releves, compte


# ──────────────────── 2. le balayage de l'index ─────────────────────────────

def _pkey_path(p):
    """`_pkey` tel qu'il est ecrit dans server.py."""
    return Path(p).as_posix().lower()


def _pkey_str(p):
    """Le meme resultat sans construire d'objet Path."""
    return str(p).replace('\\', '/').lower()


def lire_cles(base):
    """Les cles de l'index, depuis une COPIE de la base. On demande a SQLite
    quelles tables existent plutot que d'en supposer le nom : ce banc doit
    survivre a un renommage de table."""
    cx = sqlite3.connect(f'file:{base}?mode=ro', uri=True)
    try:
        tables = [r[0] for r in cx.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        # la table de l'index est la plus peuplee des tables a colonnes (k, v)
        best, best_n = None, -1
        for t in tables:
            cols = [r[1] for r in cx.execute(f'PRAGMA table_info("{t}")')]
            if cols[:2] != ['k', 'v']:
                continue
            n = cx.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            if n > best_n:
                best, best_n = t, n
        if best is None:
            return [], None
        return [r[0] for r in cx.execute(f'SELECT k FROM "{best}"')], best
    finally:
        cx.close()


def mesurer_index(cles, dossier):
    """Le cout du balayage complet, tel qu'il est paye a chaque /files."""
    pref = _pkey_str(dossier) + '/'

    t0 = time.perf_counter()
    n1 = sum(1 for k in cles if _pkey_path(k).startswith(pref))
    d_actuel = time.perf_counter() - t0

    t0 = time.perf_counter()
    n2 = sum(1 for k in cles if _pkey_str(k).startswith(pref))
    d_str = time.perf_counter() - t0

    # Ce que couterait la meme reponse si les cles normalisees etaient gardees
    # a cote de l'index (une carte batie a la meme cadence que `_key_index`).
    t0 = time.perf_counter()
    carte = [(_pkey_str(k), k) for k in cles]
    d_carte = time.perf_counter() - t0
    t0 = time.perf_counter()
    n3 = sum(1 for pk, _k in carte if pk.startswith(pref))
    d_prete = time.perf_counter() - t0

    return {'n': len(cles), 'trouvees': n1, 'accord': n1 == n2 == n3,
            'actuel_ms': d_actuel * 1000, 'str_ms': d_str * 1000,
            'carte_ms': d_carte * 1000, 'prete_ms': d_prete * 1000}


# ────────────────────────────── rapport ─────────────────────────────────────

def ms(x):
    return f'{x * 1000:9.1f} ms' if x < 1 else f'{x:9.2f} s '


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dossier', default='',
                    help='chemin absolu, ou relatif a une racine navigable')
    ap.add_argument('--tours', type=int, default=3)
    ap.add_argument('--base', default='copie.db',
                    help='copie de la base (jamais photos.db)')
    ap.add_argument('--sans-index', action='store_true')
    ap.add_argument('--json', default='',
                    help='ecrire le releve dans ce fichier')
    a = ap.parse_args(argv)

    dossier = resoudre(a.dossier)
    if dossier is None or not dossier.is_dir():
        print(f'Dossier introuvable : {a.dossier!r}')
        print('Racines connues :')
        for r in racines():
            print(f'  {r}')
        return 2

    print(f'Dossier   : {dossier}')
    print(f'Tours     : {a.tours}  (methodes alternees, cache SMB neutralise)')
    print()

    res = mesurer_parcours(dossier, a.tours)
    if res is None:
        return 1
    releves, compte = res

    print('1. PARCOURS DU DOSSIER')
    print('   ' + '-' * 68)
    ref_froid = ref_chaud = None
    lignes = []
    for nom, t in releves.items():
        n, s = compte[nom]
        froid, chaud = t[0], min(t)
        if ref_froid is None:
            ref_froid, ref_chaud = froid, chaud
        gain = f'x{ref_chaud / chaud:5.1f}' if chaud > 0 else '    -'
        lignes.append({'methode': nom, 'froid_s': froid, 'chaud_s': chaud,
                       'fichiers': n, 'sous_dossiers': s})
        print(f'   {nom:28s} froid {ms(froid)}  meilleur {ms(chaud)}  {gain}')
    n0, s0 = compte['iterdir + is_file (actuel)']
    print(f'   -> {n0} fichiers media, {s0} sous-dossiers')
    accord = len({v[0] for v in compte.values()}) == 1
    print(f'   -> les trois methodes comptent{"" if accord else " DIFFEREMMENT"}'
          f' le meme nombre de fichiers : {"oui" if accord else "NON"}')
    if not accord:
        print('      ATTENTION : un ecart de comptage invalide la comparaison.')
        for nom, (n, s) in compte.items():
            print(f'        {nom:28s} {n} fichiers / {s} dossiers')
    print()
    # `_serve_gallery` fait DEUX passes iterdir : le cout reel de la page est
    # celui qu'on vient de mesurer, deja compris dans `par_iterdir`.
    par_fichier = (releves['iterdir + is_file (actuel)'][0] / n0 * 1000
                   if n0 else 0)
    print(f'   Cout par fichier, methode actuelle, a froid : {par_fichier:.2f} ms')
    print('   (un aller-retour SMB coute typiquement 0,3 a 2 ms ; au-dela,')
    print('    c est le nombre d appels qui parle, pas la latence du reseau)')
    print()

    bilan = {'dossier': str(dossier), 'tours': a.tours, 'parcours': lignes}

    if not a.sans_index:
        base = Path(a.base)
        if not base.is_absolute():
            base = SCRIPT_DIR / base
        print('2. BALAYAGE DE L INDEX (a chaque requete, tout l index)')
        print('   ' + '-' * 68)
        if not base.is_file():
            print(f'   {base.name} absent : mesure sautee.')
            print('   (ce banc ne lit JAMAIS photos.db -- le serveur l a ouverte)')
        else:
            cles, table = lire_cles(base)
            if not cles:
                print(f'   Aucune table (k, v) peuplee dans {base.name}.')
            else:
                r = mesurer_index(cles, dossier)
                print(f'   Base      : {base.name}, table "{table}", '
                      f'{r["n"]} cles')
                print(f'   Sous ce dossier : {r["trouvees"]} entrees')
                print(f'   Les trois variantes s accordent : '
                      f'{"oui" if r["accord"] else "NON"}')
                print()
                print(f'   _pkey actuel (Path par cle)   {r["actuel_ms"]:8.1f} ms')
                print(f'   sans construire de Path       {r["str_ms"]:8.1f} ms'
                      f'   x{r["actuel_ms"] / max(r["str_ms"], 1e-9):.1f}')
                print(f'   carte deja normalisee         {r["prete_ms"]:8.1f} ms'
                      f'   x{r["actuel_ms"] / max(r["prete_ms"], 1e-9):.1f}')
                print(f'   (batir cette carte une fois : {r["carte_ms"]:.1f} ms)')
                bilan['index'] = r
        print()

    print('CE QUE CELA DIT')
    print('-' * 74)
    p_froid = releves['iterdir + is_file (actuel)'][0]
    s_froid = releves['os.scandir'][0]
    idx = bilan.get('index', {}).get('actuel_ms', 0) / 1000
    total = p_froid + idx
    if total > 0:
        print(f'   Parcours du dossier : {ms(p_froid)}  ({p_froid / total:5.1%})')
        print(f'   Balayage de l index : {ms(idx)}  ({idx / total:5.1%})')
    if s_froid > 0 and p_froid / s_froid > 2:
        print(f'   os.scandir rend la meme reponse {p_froid / s_froid:.0f} fois'
              ' plus vite, a froid.')
    print()

    if a.json:
        Path(a.json).write_text(json.dumps(bilan, ensure_ascii=False, indent=1),
                                encoding='utf-8')
        print(f'Releve ecrit dans {a.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
