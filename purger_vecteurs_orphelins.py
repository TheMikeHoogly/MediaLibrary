"""
Purge REVERSIBLE des vecteurs semantiques orphelins (kind='photo').
──────────────────────────────────────────────────────────────────────────────

LE PROBLEME (mesure du 15/08, chantier 14a)
    `vectors` garde un vecteur `photo` pour des cles qui n'ont plus de ligne
    dans `tags`. Depuis que la recherche est la porte d'entree, `/api/search`
    les remonte : la photo sort dans les resultats mais `STORE.data.get(cle)`
    rend `{}` — resultat MUET, ni description ni mots-cles, avec une URL qui
    peut ne mener nulle part. 2 374 vecteurs, 2,6 % des resultats sur huit
    requetes ordinaires. Ventilation : 2 143 = dossier ARZOPA supprime le
    08/08, 91 en `.corbeille-rangement`, 69 cles malformees.

CE QU'IL N'EST PAS
    Ce n'est PAS un correctif de fuite : la fuite est colmatee a la source
    depuis le 08/08 — `_sync_dir` etape 4 appelle `forget_everywhere`, qui
    purge en cascade tags + visages/animaux + vecteur. Ce script traite le
    STOCK HERITE d'avant ce correctif. Il est donc ONE-SHOT, et il vit hors du
    monolithe : rien a maintenir dans `server.py`.

REVERSIBLE OU RIEN
    Chaque ligne supprimee est d'abord ecrite dans une QUARANTAINE
    `_corbeille_vecteurs/<horodatage>.jsonl` — kind, cle, dtype, ver, at, et le
    vecteur lui-meme en base64. `--restaurer <fichier>` les remet. Rien n'est
    perdu tant que le fichier de quarantaine existe.

GARDE-FOUS (chacun paye une lecon du projet)
    1. Le serveur est l'ECRIVAIN UNIQUE. Si quelque chose repond sur le port
       8080, on refuse : une ecriture concurrente laisserait en plus le cache
       matrice du serveur perime (il continuerait a servir les orphelins).
    2. RACINE INJOIGNABLE -> on ne tranche pas. NAS debranche, tout le corpus
       passerait pour disparu (lecon de `scan_uploads`).
    3. PLAFOND : au-dela de 20 % des vecteurs photo, on refuse et on affiche.
       « Un compte spectaculaire est d'abord une erreur de cle » (15/08 :
       86 181 orphelins annonces, 2 374 reels — le `kind` n'etait pas filtre).
    4. Seul `kind='photo'` est compare a `tags`. Les autres kinds portent des
       cles COMPOSEES (« <cle>\\x1ffaces\\x1f0 ») : incomparables.
    5. Une cle dont le FICHIER EXISTE ENCORE et qui est SOUS UNE RACINE
       SCANNEE est EPARGNEE : son vecteur decrit une vraie photo, le scan la
       re-taguera. La purger ferait payer un re-calcul GPU pour rien.
       Mais « le fichier existe » ne suffit pas : un fichier PRESENT mais HORS
       PORTEE du scan (hors des racines, ou sous un composant cache —
       `.corbeille-rangement`, `.thumbs`, `@eaDir`… — ou sous une cle ABSOLUE
       dans l'arbre Uploads, que seule la cle RELATIVE indexe) ne sera JAMAIS
       re-tague : il resterait muet pour toujours. Celui-la est purge.
       `--garder-hors-portee` l'epargne, `--tout` purge meme les epargnes.
    6. La cle est relue DANS la transaction d'ecriture : aucun ecart possible
       entre le diagnostic et la suppression.

USAGE (machine reelle, serveur ARRETE, NAS branche)
    .venv\\Scripts\\python.exe purger_vecteurs_orphelins.py            # BLANC
    .venv\\Scripts\\python.exe purger_vecteurs_orphelins.py --appliquer
    .venv\\Scripts\\python.exe purger_vecteurs_orphelins.py --restaurer _corbeille_vecteurs\\...jsonl

    Options : --garder-hors-portee (epargner les presents qu'aucun scan ne
              reprendra — ils resteront muets), --tout (purger AUSSI les cles
              dont le fichier sera re-tague), --port N (port a sonder),
              --sans-disque (ne rien stater : tout orphelin est traite,
              garde-fou 5 desactive).

    La logique pure est testee hors machine par
    test_purger_vecteurs_orphelins.py — sur une base jetable, jamais photos.db.
"""

import base64
import json
import socket
import sqlite3
import sys
import time
from pathlib import Path

from verifier_orphelins import (KINDS_CLE_PHOTO, _existe, _joignabilite,
                                _racine_joignable, config_racines, resoudre)

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "photos.db"
QUARANTAINE_DIR = SCRIPT_DIR / "_corbeille_vecteurs"
PORT_SERVEUR = 8080

# Part maximale des vecteurs `photo` qu'on accepte de purger d'un coup. Au-dela,
# l'hypothese « erreur de cle » est plus probable que « stock herite ».
PLAFOND = 0.20

# Replique de server.IMAGE_EXT (importer `server` couterait tout le monolithe).
# Si la liste change la-bas, elle change ici — sinon un fichier indexable
# passerait pour « hors portee » et son vecteur serait purge a tort.
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif',
             '.bmp', '.tiff', '.tif'}


# ── Logique PURE (testable sans base, sans NAS, sans serveur) ───────────────

def selection(lignes, cles_tags, kinds=KINDS_CLE_PHOTO):
    """(kind, cle) x cles de `tags` -> (orphelins, total_par_kind).

    `orphelins` : liste triee de couples (kind, cle) dont la cle est absente de
    `tags`. Seuls les `kinds` dont la cle EST une cle de photo sont examines ;
    les autres sont comptes mais jamais candidats."""
    orphelins = []
    par_kind = {}
    for kind, cle in lignes:
        par_kind[kind] = par_kind.get(kind, 0) + 1
        if kind in kinds and cle not in cles_tags:
            orphelins.append((kind, cle))
    return sorted(set(orphelins)), par_kind


def depasse_plafond(n_orphelins, n_comparables, plafond=PLAFOND):
    """Vrai si la purge mordrait une part anormale des vecteurs comparables.
    `n_comparables` = nombre de vecteurs des kinds compares (photo). Un corpus
    vide ne declenche pas le plafond (0 orphelin sur 0 n'est pas une alarme)."""
    if n_orphelins <= 0:
        return False
    if n_comparables <= 0:
        return True
    return (n_orphelins / n_comparables) > plafond


def sera_re_tague(cle, upload_dir, extra, image_ext=IMAGE_EXT):
    """Ce fichier PRESENT repassera-t-il par le scan ? Replique la selection de
    `scan_uploads` / `_sync_dir` — sans importer `server` (lourd).

    Faux (donc « hors portee ») dans quatre cas, tous vus en vrai :
      - la cle est ABSOLUE mais dans l'arbre Uploads : le scan Uploads indexe
        ces fichiers sous une cle RELATIVE, et le scan des dossiers a taguer
        exclut cet arbre par prefixe. Personne ne reprend la cle absolue ;
      - le fichier n'est sous AUCUNE racine scannee (ex. la corbeille locale
        `.corbeille-rangement`, hors Uploads et hors dossiers a taguer) ;
      - un composant du chemin est cache (`.`, `@`, `#`) : `.thumbs`, `@eaDir`,
        `#recycle`… — exclus du scan par `_is_hidden_path` ;
      - l'extension n'est pas une extension d'image indexee.

    Un fichier hors portee restera MUET dans la recherche pour toujours : son
    vecteur le fait remonter, et rien ne recreera jamais sa ligne `tags`."""
    chemin = resoudre(cle, upload_dir)
    if chemin.suffix.lower() not in image_ext:
        return False
    racines = [upload_dir] if not Path(cle).is_absolute() else list(extra)
    for r in racines:
        try:
            rel = chemin.relative_to(r)
        except ValueError:
            continue
        if any(part.startswith(('.', '@', '#')) for part in rel.parts):
            return False
        # Cle ABSOLUE dans l'arbre Uploads : indexee seulement en relatif.
        if Path(cle).is_absolute():
            try:
                chemin.relative_to(upload_dir)
                return False
            except ValueError:
                pass
        return True
    return False


def partager(orphelins, statut_de, re_tague=None):
    """Separe les orphelins selon le sort de leur FICHIER.

    `statut_de` : cle -> 'absent' | 'present' | 'indetermine' (racine
    injoignable). `re_tague` : cle -> bool, seulement pour les presents.
    Renvoie (absents, hors_portee, epargnes, indetermines) :
      - absents      : le fichier a disparu — le vecteur ne decrit plus rien ;
      - hors_portee  : le fichier est la, mais aucun scan ne le reprendra —
                       muet a vie (corbeille, dossier cache, cle absolue) ;
      - epargnes     : present ET sous une racine scannee — le scan re-taguera,
                       on ne jette pas un vecteur valide (GPU pour rien) ;
      - indetermines : racine injoignable — on ne tranche pas."""
    absents, hors, epargnes, indetermines = [], [], [], []
    for kind, cle in orphelins:
        st = statut_de(cle)
        if st == 'indetermine':
            indetermines.append((kind, cle))
        elif st == 'present':
            if re_tague is None or re_tague(cle):
                epargnes.append((kind, cle))
            else:
                hors.append((kind, cle))
        else:
            absents.append((kind, cle))
    return absents, hors, epargnes, indetermines


def ventilation(couples, n=6):
    """Repartition par premier composant de la cle (dossier de tete), du plus
    gros au plus petit. Sert a LIRE ce qu'on s'apprete a purger : « 2 143 sous
    ARZOPA » se verifie d'un coup d'oeil, un total ne se verifie pas."""
    compte = {}
    for _kind, cle in couples:
        s = str(cle).replace('\\', '/')
        tete = s.rsplit('/', 1)[0] if '/' in s else '(racine)'
        compte[tete] = compte.get(tete, 0) + 1
    return sorted(compte.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def ligne_quarantaine(kind, cle, blob, dtype, ver, at):
    """Une ligne de quarantaine : tout ce qu'il faut pour reconstruire la
    ligne SQL a l'octet pres. Le vecteur voyage en base64 (JSONL = texte)."""
    return {'kind': kind, 'k': cle, 'dtype': dtype, 'ver': ver, 'at': at,
            'v_b64': base64.b64encode(blob).decode()}


def horodatage(maintenant=None):
    """Nom de fichier de quarantaine, triable, sans caractere interdit."""
    t = time.localtime(maintenant if maintenant is not None else time.time())
    return time.strftime('vecteurs_orphelins_%Y%m%d_%H%M%S.jsonl', t)


# ── Garde-fous machine ──────────────────────────────────────────────────────

def serveur_repond(port=PORT_SERVEUR, hote='127.0.0.1', delai=0.4):
    """Le serveur ecoute-t-il ? Il est l'ecrivain unique de `photos.db` :
    ecrire derriere son dos laisse en prime son cache matrice perime — il
    continuerait a servir les orphelins qu'on vient de supprimer."""
    try:
        with socket.create_connection((hote, port), timeout=delai):
            return True
    except OSError:
        return False


def _statut_disque(upload_dir, extra):
    """cle -> 'absent' | 'present' | 'indetermine'. Un seul .exists() par
    RACINE (cache), puis un stat par cle."""
    cache = _joignabilite(upload_dir, extra)

    def statut_de(cle):
        chemin = resoudre(cle, upload_dir)
        if not _racine_joignable(cle, chemin, upload_dir, extra, cache):
            return 'indetermine'
        try:
            return 'present' if chemin.is_file() else 'absent'
        except OSError:
            return 'absent'
    return statut_de


# ── Base ────────────────────────────────────────────────────────────────────

def ouvrir_ro():
    if not DB_PATH.exists():
        raise SystemExit(f"  Base introuvable : {DB_PATH}")
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def ouvrir_rw(chemin=None):
    return sqlite3.connect(str(chemin or DB_PATH))


def ecrire_quarantaine(cx, couples, chemin):
    """Ecrit la quarantaine AVANT toute suppression. Renvoie le nombre de
    lignes ecrites — qui doit egaler le nombre de couples, sinon on s'arrete :
    supprimer ce qu'on n'a pas su sauvegarder n'est pas reversible."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(chemin, 'w', encoding='utf-8') as f:
        for kind, cle in couples:
            r = cx.execute(
                "SELECT v, dtype, ver, at FROM vectors WHERE kind=? AND k=?",
                (kind, cle)).fetchone()
            if r is None:
                continue
            f.write(json.dumps(ligne_quarantaine(kind, cle, r[0], r[1], r[2],
                                                 r[3]), ensure_ascii=False))
            f.write('\n')
            n += 1
    return n


def supprimer(cx, couples):
    """Supprime les lignes, une transaction unique. La cle est RELUE ici :
    une cle revenue dans `tags` entre le diagnostic et l'ecriture n'est pas
    touchee (elle n'est plus orpheline). Renvoie (supprimes, revenus)."""
    cx.execute("BEGIN IMMEDIATE")
    try:
        cles_tags = {k for (k,) in cx.execute('SELECT k FROM tags')}
        supprimes = revenus = 0
        for kind, cle in couples:
            if cle in cles_tags:
                revenus += 1
                continue
            supprimes += cx.execute(
                "DELETE FROM vectors WHERE kind=? AND k=?",
                (kind, cle)).rowcount
        cx.execute("COMMIT")
    except Exception:
        cx.execute("ROLLBACK")
        raise
    return supprimes, revenus


def restaurer(cx, chemin):
    """Remet en base les lignes d'un fichier de quarantaine.

    N'ECRASE JAMAIS une ligne existante (`ON CONFLICT DO NOTHING`) : si la
    photo a ete re-indexee depuis la purge, son vecteur courant est plus juste
    que celui d'hier. Renvoie (restaures, deja_presents)."""
    lignes = []
    with open(chemin, 'r', encoding='utf-8') as f:
        for l in f:
            l = l.strip()
            if l:
                lignes.append(json.loads(l))
    cx.execute("BEGIN IMMEDIATE")
    try:
        restaures = 0
        for e in lignes:
            restaures += cx.execute(
                "INSERT INTO vectors(kind,k,v,dtype,ver,at) VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(kind,k) DO NOTHING",
                (e['kind'], e['k'], base64.b64decode(e['v_b64']),
                 e.get('dtype') or 'f16', e.get('ver'), e.get('at'))).rowcount
        cx.execute("COMMIT")
    except Exception:
        cx.execute("ROLLBACK")
        raise
    return restaures, len(lignes) - restaures


# ── Programme ───────────────────────────────────────────────────────────────

def _arg(args, nom, defaut=None):
    if nom in args:
        i = args.index(nom)
        return args[i + 1] if i + 1 < len(args) else defaut
    return defaut


def main():
    args = sys.argv[1:]
    appliquer = '--appliquer' in args
    tout = '--tout' in args
    garder_hors = '--garder-hors-portee' in args
    sans_disque = '--sans-disque' in args
    port = int(_arg(args, '--port', PORT_SERVEUR))
    fichier_restaurer = _arg(args, '--restaurer')

    print("=" * 70)
    print("  VECTEURS SEMANTIQUES ORPHELINS — purge REVERSIBLE")
    print("=" * 70)

    if serveur_repond(port):
        print(f"  ARRET : quelque chose repond sur le port {port}.")
        print("  Le serveur est l'ecrivain unique de photos.db. Arrete-le")
        print("  (fenetre du serveur), relance ce script, puis redemarre-le")
        print("  avec « 0 - Demarrer le serveur.bat » — un cache matrice reste")
        print("  sinon perime et continuerait a servir les orphelins.")
        return 2

    if fichier_restaurer:
        chemin = Path(fichier_restaurer)
        if not chemin.is_absolute():
            chemin = SCRIPT_DIR / chemin
        if not chemin.exists():
            print(f"  Fichier de quarantaine introuvable : {chemin}")
            return 2
        cx = ouvrir_rw()
        try:
            restaures, deja = restaurer(cx, chemin)
        finally:
            cx.close()
        print(f"  Quarantaine : {chemin}")
        print(f"  RESTAURES : {restaures}")
        print(f"  deja presents (non ecrases) : {deja}")
        print("  Redemarre le serveur pour vider son cache matrice.")
        return 0

    cx = ouvrir_ro()
    cles_tags = {k for (k,) in cx.execute('SELECT k FROM tags')}
    orphelins, par_kind = selection(
        cx.execute('SELECT kind, k FROM vectors'), cles_tags)
    comparables = sum(par_kind.get(k, 0) for k in KINDS_CLE_PHOTO)
    print(f"  Table vectors : {sum(par_kind.values())} ligne(s), "
          f"dont {comparables} comparable(s) a tags (kind photo)")
    print(f"  Table tags    : {len(cles_tags)} cle(s)")
    print(f"  ORPHELINS     : {len(orphelins)}")

    if depasse_plafond(len(orphelins), comparables):
        print()
        print(f"  ARRET : {len(orphelins)} orphelins sur {comparables} vecteurs")
        print(f"  photo depassent le plafond de {int(PLAFOND * 100)} %.")
        print("  Un compte spectaculaire est d'abord une erreur de cle :")
        print("  verifie la convention de cle avant de purger quoi que ce soit.")
        cx.close()
        return 2

    hors = epargnes = indetermines = []
    a_purger = orphelins
    if orphelins and not sans_disque:
        upload_dir, extra = config_racines()
        print(f"  Uploads : {upload_dir}")
        print(f"  Dossiers a taguer : {len(extra)}"
              f"   (stat de {len(orphelins)} cle(s)…)")
        absents, hors, epargnes, indetermines = partager(
            orphelins, _statut_disque(upload_dir, extra),
            lambda c: sera_re_tague(c, upload_dir, extra))
        print(f"    fichier ABSENT (a purger)                  : {len(absents)}")
        print(f"    present mais HORS PORTEE du scan (muet a vie): {len(hors)}")
        print(f"    present ET sous une racine scannee (epargne) : {len(epargnes)}")
        print(f"    racine injoignable (non tranche)             : {len(indetermines)}")
        a_purger = absents if garder_hors else sorted(absents + hors)
        if garder_hors and hors:
            print("    --garder-hors-portee : les hors portee sont epargnes"
                  " (ils resteront muets).")
        if tout and epargnes:
            print("    --tout : les epargnes sont ajoutes a la purge.")
            a_purger = sorted(a_purger + epargnes)
    if indetermines:
        print("  ! Des cles sont indeterminees : relance NAS branche pour un")
        print("    compte fiable. Elles ne seront pas touchees.")

    if hors and not garder_hors:
        print("  Hors portee — echantillon (aucun scan ne les reprendra) :")
        for _kind, cle in hors[:5]:
            print(f"      {cle[:70]}")
    print("  Ventilation de la purge (dossier de tete) :")
    for tete, n in ventilation(a_purger):
        print(f"      {n:6d}  {tete[:60]}")
    print()

    if not a_purger:
        print("  Rien a purger.")
        cx.close()
        return 0

    if not appliquer:
        print(f"  BLANC : {len(a_purger)} vecteur(s) seraient mis en quarantaine")
        print("  puis supprimes. Rien n'a ete modifie.")
        print("  Pour ecrire : --appliquer  (serveur arrete, NAS branche)")
        cx.close()
        return 0

    chemin_q = QUARANTAINE_DIR / horodatage()
    n_q = ecrire_quarantaine(cx, a_purger, chemin_q)
    cx.close()
    if n_q != len(a_purger):
        print(f"  ARRET : quarantaine incomplete ({n_q}/{len(a_purger)}).")
        print("  Rien n'a ete supprime — on ne jette pas ce qu'on n'a pas sauve.")
        return 2
    print(f"  Quarantaine ecrite : {chemin_q}  ({n_q} ligne(s))")

    cx = ouvrir_rw()
    try:
        supprimes, revenus = supprimer(cx, a_purger)
        restants = cx.execute(
            "SELECT count(*) FROM vectors WHERE kind='photo' AND k NOT IN "
            "(SELECT k FROM tags)").fetchone()[0]
    finally:
        cx.close()
    print(f"  SUPPRIMES : {supprimes}")
    if revenus:
        print(f"  revenus dans tags entre-temps (epargnes) : {revenus}")
    reste = f"  orphelins restants : {restants}"
    if epargnes and not tout:
        reste += f"  (dont {len(epargnes)} epargne(s) volontairement)"
    print(reste)
    print()
    print("  REVERSIBLE : --restaurer " + str(chemin_q.relative_to(SCRIPT_DIR)))
    print("  Redemarre le serveur (« 0 - Demarrer le serveur.bat ») : son cache")
    print("  matrice est en memoire, il ne se vide qu'au demarrage.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
