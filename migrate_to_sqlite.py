"""
Migration des index JSON vers SQLite — vérifiable et réversible.
──────────────────────────────────────────────────────────────────────────────

CE QUE FAIT CE SCRIPT
    Lit les 5 index JSON sur le NAS, écrit photos.db sur le DISQUE LOCAL, puis
    vérifie clé par clé que rien n'a été perdu ni altéré.

CE QU'IL NE FAIT PAS
    Il ne touche JAMAIS aux fichiers JSON d'origine. Ils restent en place, et
    server.py y revient automatiquement si photos.db est supprimée.
    Le retour arrière consiste donc à supprimer un fichier.

USAGE
    python migrate_to_sqlite.py              # simulation : lit, vérifie, n'écrit rien
    python migrate_to_sqlite.py --appliquer  # écrit photos.db puis vérifie
    python migrate_to_sqlite.py --verifier   # compare une base existante aux JSON
"""

import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store_sqlite import DB_NAME, TABLES, SqliteStore, _empreinte  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent

# ── Emplacements : même logique que server.py ────────────────────────────────
DATA_DIR = Path(r"\\nas-bremblens\home\Uploads")
try:
    for _l in (SCRIPT_DIR / "data_dir.txt").read_text(encoding='utf-8').splitlines():
        _l = _l.strip()
        if _l and not _l.startswith('#'):
            DATA_DIR = Path(_l)
            break
except OSError:
    pass

# La base vit en LOCAL (SQLite sur SMB = verrouillage non fiable, pas de WAL).
DB_DIR = SCRIPT_DIR
DB_PATH = DB_DIR / DB_NAME
# La sauvegarde, elle, part sur le NAS (volume sauvegardé).
BACKUP_PATH = DATA_DIR / "photos.db.bak"


def humain(n):
    for u in ('o', 'Ko', 'Mo', 'Go'):
        if n < 1024 or u == 'Go':
            return f"{n:.0f} {u}" if u == 'o' else f"{n:.1f} {u}"
        n /= 1024


def lire_json(chemin):
    """Lit un index JSON. Renvoie (données, erreur)."""
    if not chemin.exists():
        return {}, "absent"
    try:
        brut = chemin.read_text(encoding='utf-8')
    except OSError as e:
        return None, f"illisible : {e}"
    if not brut.strip():
        return {}, "vide"
    try:
        d = json.loads(brut)
    except ValueError as e:
        return None, f"JSON invalide : {e}"
    if not isinstance(d, dict):
        return None, f"type inattendu : {type(d).__name__}"
    return d, None


def etat_des_lieux():
    print("═" * 74)
    print("  ÉTAT DES LIEUX")
    print("═" * 74)
    print(f"  Index JSON  : {DATA_DIR}")
    print(f"  Base SQLite : {DB_PATH}  (disque local — voulu)")
    print(f"  Sauvegarde  : {BACKUP_PATH}")
    print()

    total_octets = 0
    sources = {}
    ok = True
    for nom, table in TABLES.items():
        chemin = DATA_DIR / nom
        taille = chemin.stat().st_size if chemin.exists() else 0
        total_octets += taille
        d, err = lire_json(chemin)
        if d is None:
            print(f"  ✗ {nom:<20} {humain(taille):>10}   {err}")
            ok = False
            continue
        sources[nom] = (table, d)
        marque = "·" if err else "✓"
        detail = err or f"{len(d):>7,} entrées".replace(',', ' ')
        print(f"  {marque} {nom:<20} {humain(taille):>10}   {detail}")

    print()
    print(f"  Total réécrit à CHAQUE set() aujourd'hui : {humain(total_octets)}")
    print(f"  Après migration                          : une ligne par photo")
    print()
    return sources, ok


def migrer(sources, appliquer):
    if not appliquer:
        print("  SIMULATION — aucune écriture. Relancer avec --appliquer.")
        print()
        return None

    if DB_PATH.exists():
        secours = DB_PATH.with_suffix(f".db.avant-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.move(str(DB_PATH), str(secours))
        print(f"  Base existante mise de côté : {secours.name}")
    for suffixe in ('-wal', '-shm'):
        reste = Path(str(DB_PATH) + suffixe)
        if reste.exists():
            reste.unlink()

    print("═" * 74)
    print("  MIGRATION")
    print("═" * 74)
    stores = {}
    for nom, (table, d) in sources.items():
        t0 = time.time()
        st = SqliteStore(DB_PATH, table, legacy_path=DATA_DIR / nom)
        # Insertion en masse : une seule transaction pour toute la table.
        st.cx.execute("BEGIN IMMEDIATE")
        try:
            st.cx.executemany(
                f'INSERT INTO "{table}"(k,v) VALUES(?,?) '
                'ON CONFLICT(k) DO UPDATE SET v=excluded.v',
                [(k, json.dumps(v, ensure_ascii=False, separators=(',', ':')))
                 for k, v in d.items()])
            st.cx.execute("COMMIT")
        except Exception:
            st.cx.execute("ROLLBACK")
            raise
        stores[nom] = st
        print(f"  ✓ {table:<10} {len(d):>7,} lignes  en {time.time()-t0:5.1f} s"
              .replace(',', ' '))
    for st in stores.values():
        st.close()
    print()
    return DB_PATH


def verifier(sources):
    """Compare la base aux JSON, entrée par entrée, par empreinte de contenu."""
    print("═" * 74)
    print("  VÉRIFICATION")
    print("═" * 74)
    if not DB_PATH.exists():
        print("  ✗ Aucune base à vérifier.")
        return False

    cx = sqlite3.connect(str(DB_PATH))
    tout_bon = True
    for nom, (table, attendu) in sources.items():
        try:
            lignes = dict(cx.execute(f'SELECT k, v FROM "{table}"'))
        except sqlite3.Error as e:
            print(f"  ✗ {table:<10} table illisible : {e}")
            tout_bon = False
            continue

        manquantes = set(attendu) - set(lignes)
        en_trop = set(lignes) - set(attendu)
        alterees = []
        for k, v in attendu.items():
            if k in lignes:
                try:
                    relu = json.loads(lignes[k])
                except ValueError:
                    alterees.append(k)
                    continue
                if _empreinte(relu) != _empreinte(v):
                    alterees.append(k)

        if manquantes or en_trop or alterees:
            tout_bon = False
            print(f"  ✗ {table:<10} {len(manquantes)} manquantes, "
                  f"{len(en_trop)} en trop, {len(alterees)} altérées")
            for k in list(manquantes)[:3]:
                print(f"      manquante : {k}")
            for k in alterees[:3]:
                print(f"      altérée   : {k}")
        else:
            print(f"  ✓ {table:<10} {len(attendu):>7,} entrées identiques"
                  .replace(',', ' '))
    cx.close()

    # Les noms attribués par un humain : invariant central du projet.
    print()
    print("  Contrôle de l'invariant « les noms humains survivent » :")
    for nom, cle in (("people.json", "personnes nommées"),
                     ("pets.json", "animaux nommés")):
        if nom in sources:
            _, d = sources[nom]
            noms = sorted({(v.get('name') or k) for k, v in d.items()})
            print(f"    {cle:<20} {len(noms):>3}  {', '.join(noms[:8])}"
                  + (" …" if len(noms) > 8 else ""))
    print()
    return tout_bon


def sauvegarder():
    if not DB_PATH.exists():
        return
    print("═" * 74)
    print("  SAUVEGARDE VERS LE NAS")
    print("═" * 74)
    st = SqliteStore(DB_PATH, "tags", legacy_path=DATA_DIR / "tags_index.json")
    t0 = time.time()
    ok = st.backup_to(BACKUP_PATH)
    st.close()
    if ok:
        taille = BACKUP_PATH.stat().st_size
        print(f"  ✓ {BACKUP_PATH.name} — {humain(taille)} en {time.time()-t0:.1f} s")
    print()


def main():
    args = set(sys.argv[1:])
    appliquer = '--appliquer' in args
    seule_verif = '--verifier' in args

    sources, lecture_ok = etat_des_lieux()
    if not lecture_ok:
        print("  ✗ Des index sont illisibles. Migration interrompue — "
              "corrige-les d'abord, aucune donnée n'a été touchée.")
        return 1
    if not sources:
        print("  Aucun index à migrer.")
        return 0

    if not seule_verif:
        migrer(sources, appliquer)

    if appliquer or seule_verif:
        if not verifier(sources):
            print("  ✗ VÉRIFICATION ÉCHOUÉE — ne supprime pas les JSON.")
            print("    Supprime photos.db pour revenir à l'état d'origine.")
            return 1
        sauvegarder()
        print("═" * 74)
        print("  ✓ MIGRATION VÉRIFIÉE")
        print("═" * 74)
        print("  Les JSON d'origine sont INTACTS sur le NAS.")
        print("  server.py utilisera photos.db au prochain démarrage.")
        print("  Retour arrière : supprimer photos.db (et les -wal/-shm).")
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
