"""
Tests du magasin de vecteurs — correction, occupation disque, vitesse.

    python test_vectors.py            # donnees synthetiques
    python test_vectors.py photos.db  # + mesures sur la vraie base (lecture seule)
"""

import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vectors import VectorStore, extraire, reinjecter, VEC_SPECS  # noqa: E402

ECHECS, RESULTATS = [], []


def connecte(chemin):
    """Memes reglages que SqliteStore, pour que les tests soient representatifs.

    - isolation_level=None : autocommit. Avec le reglage par defaut de Python,
      un close() sans commit() ANNULE les insertions (tests faussement rouges).
    - WAL + synchronous=NORMAL : sans eux, chaque insertion en autocommit
      declenche un fsync et les ecritures en lot deviennent interminables.
    """
    cx = sqlite3.connect(chemin, isolation_level=None)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA synchronous=NORMAL")
    return cx


def verifie(nom, cond, detail=""):
    RESULTATS.append((nom, bool(cond), detail))
    if not cond:
        ECHECS.append(f"{nom} — {detail}")


def b64_de(vec):
    import base64
    import numpy as np
    return base64.b64encode(np.asarray(vec, dtype=np.float16).tobytes()).decode()


def t_aller_retour(tmp):
    """Les octets doivent survivre a l'aller-retour, au bit pres."""
    import numpy as np
    cx = connecte(f"{tmp}/v.db")
    vs = VectorStore(cx)
    rng = np.random.default_rng(0)
    src = {f"cle{i}": b64_de(rng.normal(size=512)) for i in range(200)}
    vs.put_many_b64('face', list(src.items()))
    relu = vs.load_all_b64('face')
    verifie("aller-retour base64 identique au bit pres", relu == src,
            f"{sum(1 for k in src if relu.get(k) != src[k])} ecarts")
    verifie("comptage correct", vs.count('face') == 200, vs.count('face'))
    cx.close()


def t_extraction_reinjection(tmp):
    """L'entree doit se reconstituer a l'identique apres extraction."""
    import copy
    cx = connecte(f"{tmp}/w.db")
    vs = VectorStore(cx)
    import numpy as np
    rng = np.random.default_rng(1)

    cas = {
        'faces': {"n": 2, "at": 1.0, "faces": [
            {"bbox": [1, 2, 3, 4], "det_score": 0.9, "emb": b64_de(rng.normal(size=512))},
            {"bbox": [5, 6, 7, 8], "det_score": 0.8, "emb": b64_de(rng.normal(size=512))}]},
        'people': {"name": "X", "at": 2.0, "avatar": ["k", 0],
                   "refs": [b64_de(rng.normal(size=512)) for _ in range(3)]},
        'animals': {"n": 1, "animals": [
            {"species": "cat", "det_score": 0.7, "emb": b64_de(rng.normal(size=768))}]},
    }
    for table, entree in cas.items():
        origine = copy.deepcopy(entree)
        allege = extraire(copy.deepcopy(entree), VEC_SPECS[table], "cle", vs, table)
        verifie(f"[{table}] l'entree source n'est pas modifiee",
                entree == origine)
        import json
        verifie(f"[{table}] le JSON allege ne contient plus de vecteur",
                len(json.dumps(allege)) < len(json.dumps(origine)) / 2,
                f"{len(json.dumps(allege))} vs {len(json.dumps(origine))}")
        rendu = reinjecter(allege, VEC_SPECS[table],
                           vs.load_all_b64(table), "cle")
        verifie(f"[{table}] reinjection identique a l'origine",
                rendu == origine)
    cx.close()


def t_champ_non_vectoriel(tmp):
    """Un champ « refs » contenant des chemins ne doit PAS etre extrait."""
    cx = connecte(f"{tmp}/x.db")
    vs = VectorStore(cx)
    e = {"name": "Y", "refs": [r"\\NAS\home\Photos\2010\DSC01507.JPG",
                               r"\\NAS\home\Photos\2010\DSC01510.JPG"]}
    import copy
    allege = extraire(copy.deepcopy(e), VEC_SPECS['people'], "cle", vs, 'people')
    verifie("les chemins courts ne sont pas pris pour des vecteurs",
            allege == e and vs.count('people') == 0,
            f"{vs.count('people')} vecteurs extraits a tort")
    cx.close()


def t_recherche(tmp):
    """Un vecteur present doit se retrouver lui-meme avec un score de 1."""
    import numpy as np
    cx = connecte(f"{tmp}/y.db")
    vs = VectorStore(cx)
    rng = np.random.default_rng(2)
    vecs = rng.normal(size=(500, 512)).astype(np.float32)
    vs.put_many_b64('face', [(f"c{i}", b64_de(vecs[i])) for i in range(500)])

    q = vecs[123] / np.linalg.norm(vecs[123])
    res = vs.search('face', q, limite=5)
    verifie("le vecteur cherche arrive en tete", res and res[0][0] == "c123",
            res[0] if res else "vide")
    verifie("son score vaut ~1.0", res and res[0][1] > 0.99,
            f"{res[0][1]:.4f}" if res else "-")
    verifie("les scores sont decroissants",
            all(res[i][1] >= res[i + 1][1] for i in range(len(res) - 1)))

    # Blocs : le decoupage ne doit pas changer le resultat.
    petit = vs.search('face', q, limite=5, bloc=37)
    verifie("resultat independant de la taille de bloc",
            [k for k, _ in petit] == [k for k, _ in res],
            f"{[k for k,_ in petit]} vs {[k for k,_ in res]}")

    seuil = vs.search('face', q, limite=1000, seuil=0.99)
    verifie("la recherche par seuil ne renvoie que les proches",
            len(seuil) == 1, len(seuil))

    vs.put_b64('face', "c123", b64_de(rng.normal(size=512)))
    r2 = vs.search('face', q, limite=1)
    verifie("le cache est invalide apres ecriture", r2[0][0] != "c123" or
            r2[0][1] < 0.99, r2[0])
    cx.close()


def t_recherche_restreinte(tmp):
    """Recherche hybride : classer par le sens A L'INTERIEUR d'un sous-ensemble
    filtre sur un tag humain (« animal:Luna »)."""
    import numpy as np
    cx = connecte(f"{tmp}/r.db")
    vs = VectorStore(cx)
    rng = np.random.default_rng(7)
    vecs = rng.normal(size=(400, 512)).astype(np.float32)
    vs.put_many_b64('photo', [(f"p{i}", b64_de(vecs[i])) for i in range(400)])

    sous_ensemble = {f"p{i}" for i in range(0, 400, 4)}      # 100 cles
    q = vecs[7] / np.linalg.norm(vecs[7])                    # p7 n'en fait PAS partie

    complet = vs.search('photo', q, limite=5)
    verifie("sans restriction, la meilleure correspondance sort",
            complet[0][0] == "p7", complet[0])

    restreint = vs.search('photo', q, limite=5, restreindre=sous_ensemble)
    verifie("la restriction exclut les cles hors sous-ensemble",
            all(k in sous_ensemble for k, _ in restreint),
            [k for k, _ in restreint])
    verifie("la restriction renvoie bien des resultats classes",
            len(restreint) == 5 and
            all(restreint[i][1] >= restreint[i + 1][1] for i in range(4)))

    dedans = vs.search('photo', vecs[8] / np.linalg.norm(vecs[8]), limite=3,
                       restreindre=sous_ensemble)
    verifie("une cle du sous-ensemble se retrouve elle-meme",
            dedans[0][0] == "p8" and dedans[0][1] > 0.99, dedans[0])

    verifie("un sous-ensemble vide ne renvoie rien",
            vs.search('photo', q, limite=5, restreindre=set()) == [])
    verifie("des cles inconnues ne renvoient rien",
            vs.search('photo', q, limite=5, restreindre={"absent"}) == [])
    cx.close()


def t_suppression(tmp):
    cx = connecte(f"{tmp}/z.db")
    vs = VectorStore(cx)
    vs.put_many_b64('face', [(f"photo.jpg\x1ffaces\x1f{i}", b64_de([0.1] * 512))
                             for i in range(3)])
    vs.put_b64('face', "autre.jpg\x1ffaces\x1f0", b64_de([0.2] * 512))
    vs.delete_prefix('face', ["photo.jpg\x1f"])
    verifie("suppression par prefixe ciblee", vs.count('face') == 1, vs.count('face'))
    cx.close()


def t_delete_all(tmp):
    """delete_all retire les DEUX formes (suffixe + cle nue) d'une photo, sans
    toucher un voisin dont la cle a la cible pour simple prefixe."""
    cx = connecte(f"{tmp}/da.db")
    vs = VectorStore(cx)
    vs.put_many_b64('face', [(f"a/p.jpg\x1ffaces\x1f{i}", b64_de([0.1] * 512))
                             for i in range(3)])            # 3 suffixe visages
    vs.put_b64('animal', "a/p.jpg\x1fanimals\x1f0", b64_de([0.2] * 768))  # suffixe animal
    vs.put_b64('photo', "a/p.jpg", b64_de([0.3] * 512))    # cle NUE semantique
    vs.put_b64('photo', "a/p.jpg2", b64_de([0.4] * 512))   # voisin (prefixe) : reste
    vs.put_b64('face', "autre.jpg\x1ffaces\x1f0", b64_de([0.5] * 512))    # autre photo
    n = vs.delete_all("a/p.jpg")
    verifie("delete_all retire les 5 vecteurs de la photo (2 formes)", n == 5, n)
    verifie("le voisin « {key}2 » (cle nue) survit",
            "a/p.jpg2" in vs.load_all_b64('photo'))
    verifie("une autre photo survit", vs.count('face') == 1, vs.count('face'))
    verifie("plus aucun vecteur de la cible",
            "a/p.jpg" not in vs.load_all_b64('photo')
            and all(not k.startswith("a/p.jpg\x1f")
                    for k in vs.load_all_b64('face')))
    verifie("idempotent (rejoue -> 0)", vs.delete_all("a/p.jpg") == 0)
    cx.close()


def t_occupation(tmp):
    """Regression : la table vectors ne doit PAS etre en WITHOUT ROWID."""
    import numpy as np
    cx = connecte(f"{tmp}/occ.db")
    vs = VectorStore(cx)
    rng = np.random.default_rng(3)
    vs.put_many_b64('face', [(f"chemin/tres/long/photo_{i}.jpg\x1ffaces\x1f0",
                              b64_de(rng.normal(size=512))) for i in range(4000)])
    cx.close()

    cx = connecte(f"{tmp}/occ.db")
    sql = cx.execute("SELECT sql FROM sqlite_master WHERE name='vectors'").fetchone()[0]
    verifie("la table vectors est a rowid (pas WITHOUT ROWID)",
            'WITHOUT ROWID' not in sql.upper(), sql[-40:])
    # Charge utile reelle : blobs + cles.
    utile = cx.execute(
        "SELECT sum(length(v)) + sum(length(k)) FROM vectors").fetchone()[0]
    try:
        pages, payload = cx.execute(
            "SELECT count(*), sum(payload) FROM dbstat WHERE name='vectors'"
        ).fetchone()
        ps = cx.execute("PRAGMA page_size").fetchone()[0]
        occ = 100 * payload / (pages * ps)
        mesure = f"dbstat : {pages * ps / 1048576:.1f} Mo de pages"
    except sqlite3.OperationalError:
        # dbstat n'est pas compile dans tous les builds SQLite (Windows
        # notamment). Repli : le fichier ne contient que cette table, donc sa
        # taille est une borne superieure directement comparable.
        cx.close()
        fichier = os.path.getsize(f"{tmp}/occ.db")
        occ = 100 * utile / fichier
        mesure = f"taille du fichier : {fichier / 1048576:.1f} Mo"
        cx = connecte(f"{tmp}/occ.db")
    verifie("occupation des pages > 70 % (regression WITHOUT ROWID)",
            occ > 70, f"{occ:.0f} %")
    print(f"\n  Occupation de la table vectors : {occ:.0f} %  "
          f"({mesure}, {utile / 1048576:.1f} Mo utiles)")
    cx.close()


def t_migration_schema_v1(tmp):
    """Une base creee avec l'ancien schema doit etre reconstruite."""
    cx = connecte(f"{tmp}/v1.db")
    cx.execute("""CREATE TABLE vectors (kind TEXT NOT NULL, k TEXT NOT NULL,
                    v BLOB NOT NULL, dtype TEXT NOT NULL DEFAULT 'f16',
                    ver TEXT, at REAL, PRIMARY KEY (kind,k)) WITHOUT ROWID""")
    cx.execute("INSERT INTO vectors VALUES('face','a',x'0102',	'f16',NULL,0)")
    cx.close()

    cx = connecte(f"{tmp}/v1.db")
    vs = VectorStore(cx)
    sql = cx.execute("SELECT sql FROM sqlite_master WHERE name='vectors'").fetchone()[0]
    verifie("ancien schema WITHOUT ROWID reconstruit",
            'WITHOUT ROWID' not in sql.upper())
    verifie("les vecteurs existants sont conserves lors de la reconstruction",
            vs.count('face') == 1, vs.count('face'))
    cx.close()


def mesures_reelles(db):
    """Mesures sur la vraie base, en lecture seule."""
    import numpy as np
    tmp = tempfile.mkdtemp()
    copie = f"{tmp}/copie.db"
    shutil.copy2(db, copie)
    cx = sqlite3.connect(f"file:{copie}?mode=ro", uri=True)
    vs = VectorStore.__new__(VectorStore)
    vs.cx = cx
    import threading
    vs.lock = threading.RLock()
    vs._cache = {}

    print("\n" + "=" * 74)
    print("  MESURES SUR LA BASE REELLE")
    print("=" * 74)
    kinds = vs.kinds()
    if not kinds:
        print("  Aucun vecteur : lance d'abord migrate_embeddings.py --appliquer")
        cx.close()
        shutil.rmtree(tmp, ignore_errors=True)
        return
    for kind, n in sorted(kinds.items()):
        t0 = time.perf_counter()
        cles, M = vs.matrice(kind, forcer=True)
        t_charge = time.perf_counter() - t0
        if not cles:
            continue
        q = M[len(cles) // 2]
        vs.search(kind, q, limite=10)                     # prechauffage
        t0 = time.perf_counter()
        for _ in range(20):
            res = vs.search(kind, q, limite=60)
        t_rech = (time.perf_counter() - t0) / 20 * 1000
        print(f"  {kind:<9} {n:>6,} vecteurs  dim {M.shape[1]:>3}  "
              f"chargement {t_charge*1000:>6.0f} ms  "
              f"recherche {t_rech:>6.1f} ms  "
              f"(top1 score {res[0][1]:.3f})".replace(',', ' '))

    # Extrapolation a 100 000 photos (recherche semantique SigLIP 2, dim 768)
    n, d = 100_000, 768
    M = np.random.default_rng(0).normal(size=(n, d)).astype(np.float32)
    M /= np.linalg.norm(M, axis=1, keepdims=True)
    q = M[0].copy()
    t0 = time.perf_counter()
    for _ in range(5):
        s = M @ q
        np.argpartition(-s, 60)[:60]
    t = (time.perf_counter() - t0) / 5 * 1000
    print(f"\n  Extrapolation : {n:,} vecteurs x {d} dim  ->  {t:.0f} ms par recherche"
          .replace(',', ' '))
    print(f"  Empreinte memoire de la matrice : {M.nbytes/1048576:.0f} Mo")
    print("  => un index approximatif (sqlite-vec, faiss, usearch) n'apporterait")
    print("     rien a cette echelle : l'exhaustif tient largement le temps reel.")
    cx.close()
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="test_vec_"))
    for t in (t_aller_retour, t_extraction_reinjection, t_champ_non_vectoriel,
              t_recherche, t_recherche_restreinte, t_suppression, t_delete_all,
              t_occupation, t_migration_schema_v1):
        sous = tmp / t.__name__
        sous.mkdir(parents=True, exist_ok=True)
        try:
            t(str(sous))
        except Exception as e:                              # noqa: BLE001
            import traceback
            traceback.print_exc()
            ECHECS.append(f"{t.__name__} a leve {e!r}")
            RESULTATS.append((t.__name__, False, repr(e)))

    print("\n" + "=" * 74)
    print("  RESULTATS")
    print("=" * 74)
    for nom, ok, detail in RESULTATS:
        print(f"  {'+' if ok else 'x'} {nom}" + (f"  -> {detail}" if not ok else ""))
    print("=" * 74)
    print(f"  {sum(1 for _, o, _ in RESULTATS if o)}/{len(RESULTATS)} verifications")
    print("  " + ("aucun echec" if not ECHECS else f"x {len(ECHECS)} echec(s)"))
    print("=" * 74)
    shutil.rmtree(tmp, ignore_errors=True)

    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        mesures_reelles(sys.argv[1])
    return 1 if ECHECS else 0


if __name__ == '__main__':
    sys.exit(main())
