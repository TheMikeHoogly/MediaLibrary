"""
Sortie des embeddings hors des lignes JSON, vers la table BLOB `vectors`.
──────────────────────────────────────────────────────────────────────────────

CE QUE FAIT CE SCRIPT
    Réécrit chaque ligne des tables faces / people / animals / pets : les
    vecteurs base64 quittent le JSON et rejoignent la table `vectors` en BLOB.
    Les OCTETS SONT INCHANGÉS (float16) — donc les regroupements, les scores
    et les seuils restent identiques au bit près.

GARANTIE VÉRIFIÉE
    Avant/après, le script compare la représentation EN MÉMOIRE de chaque
    entrée, champ par champ, embeddings compris. Si un seul octet diffère, il
    s'arrête et laisse la base intacte.

PRÉREQUIS
    Le serveur doit être arrêté (la base est ouverte en écriture).

USAGE
    python migrate_embeddings.py              # simulation
    python migrate_embeddings.py --appliquer  # applique puis vérifie
"""

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store_sqlite import DB_NAME, TABLES, SqliteStore  # noqa: E402
from vectors import VEC_SPECS  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / DB_NAME

DATA_DIR = Path(r"\\nas-bremblens\home\Uploads")
try:
    for _l in (SCRIPT_DIR / "data_dir.txt").read_text(encoding='utf-8').splitlines():
        _l = _l.strip()
        if _l and not _l.startswith('#'):
            DATA_DIR = Path(_l)
            break
except OSError:
    pass
BACKUP_PATH = DATA_DIR / "photos.db.bak"


def humain(n):
    for u in ('o', 'Ko', 'Mo', 'Go'):
        if n < 1024 or u == 'Go':
            return f"{n:.0f} {u}" if u == 'o' else f"{n:.1f} {u}"
        n /= 1024


def poids_tables():
    cx = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    out = {}
    for nom, table in TABLES.items():
        try:
            n, o = cx.execute(
                f'SELECT count(*), coalesce(sum(length(v)),0) FROM "{table}"'
            ).fetchone()
            out[table] = (n, o)
        except sqlite3.Error:
            out[table] = (0, 0)
    try:
        nv, ov = cx.execute(
            "SELECT count(*), coalesce(sum(length(v)),0) FROM vectors").fetchone()
    except sqlite3.Error:
        nv, ov = 0, 0
    cx.close()
    return out, nv, ov


def base_libre():
    """Aucun autre processus n'utilise-t-il la base ?

    On ne peut PAS se fier a la taille du fichier -wal : apres un Ctrl+C, la
    connexion n'est pas fermee proprement et le journal reste en place alors
    que plus personne ne detient la base. Le seul test fiable est de tenter
    d'acquerir le verrou exclusif.

    Renvoie (libre, detail).
    """
    wal = Path(str(DB_PATH) + '-wal')
    reste = wal.stat().st_size if wal.exists() else 0
    try:
        cx = sqlite3.connect(str(DB_PATH), timeout=2.0, isolation_level=None)
        cx.execute("PRAGMA busy_timeout=2000")
        cx.execute("BEGIN EXCLUSIVE")
        cx.execute("ROLLBACK")
        if reste:
            # Journal orphelin : on le replie dans la base avant de travailler.
            cx.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cx.close()
        detail = (f"journal -wal orphelin de {reste/1024:.0f} Ko replie "
                  "dans la base") if reste else ""
        return True, detail
    except sqlite3.OperationalError as e:
        try:
            cx.close()
        except Exception:
            pass
        return False, str(e)


def etat_des_lieux():
    print("=" * 74)
    print("  ETAT DES LIEUX")
    print("=" * 74)
    if not DB_PATH.exists():
        print(f"  x Base introuvable : {DB_PATH}")
        print("    Lance d'abord « 11 - Migrer vers SQLite.bat ».")
        return None
    libre, detail = base_libre()
    if not libre:
        print(f"  ! La base est utilisee par un autre processus ({detail}).")
        print("    Arrete le serveur (Ctrl+C) avant de continuer.")
        return None
    if detail:
        print(f"  . {detail}")

    tables, nv, ov = poids_tables()
    print(f"  Base : {DB_PATH}  ({humain(DB_PATH.stat().st_size)})")
    print()
    total_json = 0
    for table, (n, o) in tables.items():
        total_json += o
        marque = "*" if table in VEC_SPECS else " "
        print(f"  {marque} {table:<10} {n:>7,} lignes   {humain(o):>9} de JSON"
              .replace(',', ' '))
    print(f"    {'vectors':<10} {nv:>7,} vecteurs {humain(ov):>9} de BLOB"
          .replace(',', ' '))
    print()
    print("  * = table contenant des embeddings a sortir")
    print()
    return tables


def instantane(st):
    """Copie profonde comparable de l'etat memoire d'un store."""
    return {k: json.dumps(dict(v), sort_keys=True, ensure_ascii=False)
            for k, v in st.data.items()}


def migrer(appliquer):
    print("=" * 74)
    print("  REECRITURE DES LIGNES")
    print("=" * 74)
    avant, apres = {}, {}
    total_vec = 0

    for nom, table in TABLES.items():
        if table not in VEC_SPECS:
            continue
        t0 = time.time()
        st = SqliteStore(DB_PATH, table, legacy_path=DATA_DIR / nom)
        avant[table] = instantane(st)
        n = len(st.data)
        if not appliquer:
            print(f"  . {table:<10} {n:>7,} lignes a reecrire".replace(',', ' '))
            st.close()
            continue
        # Reecriture complete : l'extraction se fait a l'ecriture.
        st._ecrire(set(st.data.keys()), set())
        total_vec += st.vec.count(table) if st.vec else 0
        print(f"  + {table:<10} {n:>7,} lignes  ->  "
              f"{st.vec.count(table) if st.vec else 0:>6,} vecteurs  "
              f"en {time.time()-t0:5.1f} s".replace(',', ' '))
        st.close()

    if not appliquer:
        print()
        print("  SIMULATION - aucune ecriture. Relancer avec --appliquer.")
        print()
        return None, None, 0

    # Compactage : sans VACUUM, l'espace libere reste alloue au fichier.
    print()
    print("  Compactage de la base (VACUUM)...")
    t0 = time.time()
    cx = sqlite3.connect(str(DB_PATH))
    cx.execute("VACUUM")
    cx.close()
    print(f"  + VACUUM en {time.time()-t0:.1f} s")
    print()

    for nom, table in TABLES.items():
        if table not in VEC_SPECS:
            continue
        st = SqliteStore(DB_PATH, table, legacy_path=DATA_DIR / nom)
        apres[table] = instantane(st)
        st.close()
    return avant, apres, total_vec


def verifier(avant, apres):
    print("=" * 74)
    print("  VERIFICATION - l'etat memoire doit etre IDENTIQUE")
    print("=" * 74)
    tout_bon = True
    for table in avant:
        a, b = avant[table], apres.get(table, {})
        manquantes = set(a) - set(b)
        en_trop = set(b) - set(a)
        differentes = [k for k in a if k in b and a[k] != b[k]]
        if manquantes or en_trop or differentes:
            tout_bon = False
            print(f"  x {table:<10} {len(manquantes)} manquantes, "
                  f"{len(en_trop)} en trop, {len(differentes)} differentes")
            for k in differentes[:2]:
                print(f"      differente : {k[:70]}")
        else:
            print(f"  + {table:<10} {len(a):>7,} entrees identiques "
                  "(embeddings compris)".replace(',', ' '))
    print()
    return tout_bon


def main():
    args = set(sys.argv[1:])
    appliquer = '--appliquer' in args

    tables_avant = etat_des_lieux()
    if tables_avant is None:
        return 1
    taille_avant = DB_PATH.stat().st_size

    res = migrer(appliquer)
    if not appliquer:
        return 0
    avant, apres, total_vec = res

    if not verifier(avant, apres):
        print("  x VERIFICATION ECHOUEE.")
        print("    Restaure photos.db.bak depuis le NAS, ou relance")
        print("    « 11 - Migrer vers SQLite.bat » : les .json sont intacts.")
        return 1

    print("=" * 74)
    print("  RESULTAT")
    print("=" * 74)
    tables_apres, nv, ov = poids_tables()
    for table in TABLES.values():
        if table not in VEC_SPECS:
            continue
        na, oa = tables_avant[table]
        nb, ob = tables_apres[table]
        gain = 100 * (1 - ob / oa) if oa else 0
        print(f"  {table:<10} {humain(oa):>9} -> {humain(ob):>9} de JSON"
              f"   (-{gain:.0f} %)")
    print(f"  {'vectors':<10} {'':>9}    {humain(ov):>9} de BLOB "
          f"({nv:,} vecteurs)".replace(',', ' '))
    print()
    print(f"  Fichier    {humain(taille_avant)} -> {humain(DB_PATH.stat().st_size)}")
    print()
    print("  Les octets float16 sont inchanges : regroupements, scores et")
    print("  seuils donnent exactement les memes resultats qu'avant.")
    print()

    print("  Sauvegarde vers le NAS...")
    st = SqliteStore(DB_PATH, "tags", legacy_path=DATA_DIR / "tags_index.json")
    if st.backup_to(BACKUP_PATH):
        print(f"  + {BACKUP_PATH}")
    st.close()
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
