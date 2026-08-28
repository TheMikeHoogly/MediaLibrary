"""
Tests du store SQLite — reproduit les usages RÉELS trouvés dans server.py.
──────────────────────────────────────────────────────────────────────────────
Chaque test cite la ligne de server.py dont il reproduit le motif, pour que la
couverture soit vérifiable et non déclarative.

    python test_store_sqlite.py
"""

import base64
import copy
import json
import os
import pickle
import random
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store_sqlite import SqliteStore, TABLES, open_store  # noqa: E402

ECHECS = []
RESULTATS = []


def verifie(nom, condition, detail=""):
    RESULTATS.append((nom, bool(condition), detail))
    if not condition:
        ECHECS.append(f"{nom} — {detail}")


class TagStoreJSON:
    """Copie fidèle de TagStore (server.py l. 211-312), pour comparer les
    comportements et servir de repli dans le test de open_store."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.data = {}
        try:
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            pass

    def has(self, name):
        e = self.data.get(name)
        return bool(e) and not e.get('failed')

    def get(self, name):
        return self.data.get(name)

    def set(self, name, entry, save=True):
        with self.lock:
            self.data[name] = entry
            if save:
                self._save()

    def save(self):
        with self.lock:
            self._save()

    def _save(self):
        data = json.dumps(self.data, ensure_ascii=False, indent=1)
        tmp = self.path.with_name(self.path.name + '.tmp')
        tmp.write_text(data, encoding='utf-8')
        os.replace(tmp, self.path)

    def rekey(self, old, new, mtime=None):
        with self.lock:
            e = self.data.pop(old, None)
            if e is None:
                return False
            if mtime is not None:
                e['mtime'] = mtime
            self.data[new] = e
            return True

    def remove_many(self, keys):
        with self.lock:
            n = 0
            for k in keys:
                if self.data.pop(k, None) is not None:
                    n += 1
            if n:
                self._save()
            return n

    def tagged_count(self):
        return sum(1 for e in self.data.values()
                   if not e.get('failed') and (e.get('kw_fr') or e.get('kw_en')))


def contenu_brut(db, table):
    cx = sqlite3.connect(str(db))
    d = {k: json.loads(v) for k, v in cx.execute(f'SELECT k,v FROM "{table}"')}
    cx.close()
    return d


def entree(i, avec_embedding=False):
    e = {"kw_fr": [f"tag{i}", "famille"], "kw_en": ["family"],
         "desc": f"photo {i}", "mtime": 1700000000 + i}
    if avec_embedding:
        e["faces"] = [{"emb": base64.b64encode(os.urandom(2048)).decode(),
                       "score": 0.91, "box": [10, 20, 90, 120]}]
    return e


# ══════════════════════════════════════════════════════════════════════════
def t_api_identique(tmp):
    """Surface d'API : tout ce que server.py appelle doit exister."""
    st = SqliteStore(tmp / "a.db", "tags")
    requis = ['data', 'get', 'set', 'save', '_save', 'has', 'rekey',
              'remove_many', 'tagged_count', 'lock', 'path']
    manquants = [m for m in requis if not hasattr(st, m)]
    verifie("API complète (11 membres utilisés par server.py)",
            not manquants, f"manquants : {manquants}")
    st.close()


def t_equivalence_avec_json(tmp):
    """Même séquence d'opérations sur les deux stores → même état final."""
    js = TagStoreJSON(tmp / "ref.json")
    sq = SqliteStore(tmp / "b.db", "tags")

    for s in (js, sq):
        for i in range(50):
            s.set(f"photo{i}.jpg", entree(i))
        s.set("rate.jpg", {"failed": True}, save=True)
        s.remove_many([f"photo{i}.jpg" for i in range(0, 10, 2)])
        s.rekey("photo11.jpg", "renomme.jpg", mtime=1)
        s.save()

    verifie("tagged_count identique à TagStore",
            js.tagged_count() == sq.tagged_count(),
            f"json={js.tagged_count()} sqlite={sq.tagged_count()}")
    verifie("has() identique (entrée en échec exclue)",
            js.has("rate.jpg") == sq.has("rate.jpg") is False)
    verifie("mêmes clés en mémoire",
            set(js.data) == set(sq.data),
            f"écart : {set(js.data) ^ set(sq.data)}")
    verifie("rekey : mtime réécrit",
            sq.data["renomme.jpg"]["mtime"] == 1)
    verifie("rekey : ancienne clé absente", "photo11.jpg" not in sq.data)

    attendu = {k: dict(v) for k, v in sq.data.items()}
    sq.close()
    verifie("persistance conforme à l'état mémoire",
            contenu_brut(tmp / "b.db", "tags") == attendu)


def t_mutation_imbriquee(tmp):
    """Motif dominant : e = STORE.data.get(k) ; e['x'] = … ; STORE.save()
    (server.py l. 586, 735, 1254, 4427, 4452…)"""
    db = tmp / "c.db"
    st = SqliteStore(db, "tags")
    st.set("p.jpg", entree(1))

    e = st.data.get("p.jpg")            # exactement le motif de server.py
    e['kw_fr'] = ["modifie"]
    e['gps'] = [46.52, 6.55]
    st.save()
    st.close()

    relu = contenu_brut(db, "tags")["p.jpg"]
    verifie("mutation imbiquée niveau 1 persistée (via save)",
            relu.get('kw_fr') == ["modifie"] and relu.get('gps') == [46.52, 6.55],
            f"relu={relu}")

    # Cas plus dur : mutation PROFONDE (liste dans l'entrée), puis save().
    st = SqliteStore(db, "tags")
    e = st.data.get("p.jpg")
    e['kw_fr'].append("profond")        # ne passe par aucun __setitem__ suivi
    st.save()
    st.close()
    relu = contenu_brut(db, "tags")["p.jpg"]
    verifie("mutation PROFONDE rattrapée par la réconciliation",
            "profond" in relu.get('kw_fr', []), f"relu={relu}")


def t_ecriture_incrementale(tmp):
    """Le gain réel : set() ne doit pas réécrire toutes les lignes."""
    db = tmp / "d.db"
    st = SqliteStore(db, "faces")
    for i in range(300):
        st.set(f"f{i}.jpg", entree(i, avec_embedding=True), save=False)
    st.save()

    ecritures = {"n": 0}
    vrai_ecrire = st._ecrire

    def espion(clés, supprimées):
        ecritures["n"] += len(clés) + len(supprimées)
        return vrai_ecrire(clés, supprimées)
    st._ecrire = espion

    st.set("f7.jpg", entree(7, avec_embedding=True))     # une seule photo
    verifie("set() n'écrit qu'une ligne (et non 300)",
            ecritures["n"] == 1, f"lignes écrites = {ecritures['n']}")

    ecritures["n"] = 0
    st.save()                                            # rien n'a changé
    verifie("save() sans changement n'écrit rien",
            ecritures["n"] == 0, f"lignes écrites = {ecritures['n']}")
    st.close()


def t_remplacement_global(tmp):
    """server.py l. 3822-3824 : with ANIMAL_STORE.lock: ANIMAL_STORE.data = {} ;
    ANIMAL_STORE._save()  — le RLock doit éviter l'interblocage."""
    db = tmp / "e.db"
    st = SqliteStore(db, "animals")
    for i in range(20):
        st.set(f"a{i}.jpg", {"animals": [{"cls": "cat", "conf": 0.8}]})

    fini = threading.Event()

    def bloc():
        with st.lock:                    # motif exact de server.py
            st.data = {}
            st._save()                   # _save() SOUS le lock → RLock requis
        fini.set()

    th = threading.Thread(target=bloc)
    th.start()
    th.join(timeout=5)
    verifie("pas d'interblocage sur `_save()` sous `with store.lock:`",
            fini.is_set(), "le thread est resté bloqué (Lock non réentrant ?)")
    verifie("remplacement global vidé en mémoire", len(st.data) == 0)
    st.close()
    verifie("remplacement global vidé sur disque",
            contenu_brut(db, "animals") == {})


def t_pop_direct(tmp):
    """server.py l. 4051, 4078 : PETS_STORE.data.pop(nom, None)"""
    db = tmp / "f.db"
    st = SqliteStore(db, "pets")
    st.set("luna", {"name": "Luna", "species": "cat", "refs": ["k1"]})
    st.set("inti", {"name": "Inti", "species": "cat", "refs": ["k2"]})

    ancien = st.data.pop("inti", None)
    verifie("pop() renvoie bien l'entrée", ancien and ancien.get("name") == "Inti")
    st.data["caline"] = dict(ancien, name="Caline")   # rename, motif l. 4051-4053
    st.save()
    st.close()

    relu = contenu_brut(db, "pets")
    verifie("pop() propagé en base (ligne supprimée)", "inti" not in relu)
    verifie("réinsertion sous une nouvelle clé persistée",
            relu.get("caline", {}).get("name") == "Caline", f"relu={relu}")
    verifie("les autres noms sont intacts",
            relu.get("luna", {}).get("name") == "Luna")


def t_invariant_noms_humains(tmp):
    """Invariant central : un nom attribué par un humain ne se perd jamais."""
    db = tmp / "g.db"
    st = SqliteStore(db, "people")
    noms = {"mike": "Mike", "sophie": "Sophie", "elsa": "Elsa"}
    for k, n in noms.items():
        st.set(k, {"name": n, "refs": [f"ref_{k}"], "at": time.time()})
    st.close()

    # Redémarrage complet du processus simulé : on rouvre la base.
    st2 = SqliteStore(db, "people")
    relus = {k: v.get("name") for k, v in st2.data.items()}
    verifie("les noms humains survivent au redémarrage",
            relus == noms, f"relus={relus}")
    verifie("les références de visages survivent",
            all(st2.data[k].get("refs") for k in noms))
    st2.close()


def t_concurrence(tmp):
    """ThreadingHTTPServer : plusieurs threads écrivent en même temps."""
    db = tmp / "h.db"
    st = SqliteStore(db, "tags")
    erreurs = []

    def travail(base):
        try:
            for i in range(60):
                st.set(f"t{base}_{i}.jpg", entree(i))
                if i % 20 == 0:
                    st.save()
        except Exception as e:                      # noqa: BLE001
            erreurs.append(repr(e))

    ths = [threading.Thread(target=travail, args=(b,)) for b in range(6)]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=30)

    verifie("aucune erreur en écriture concurrente", not erreurs, str(erreurs[:2]))
    verifie("les 360 entrées concurrentes sont présentes",
            len(st.data) == 360, f"len={len(st.data)}")
    st.close()
    verifie("les 360 entrées sont persistées",
            len(contenu_brut(db, "tags")) == 360)


def t_resistance_coupure(tmp):
    """Une base tuée en cours de route doit rester lisible (WAL + transaction)."""
    db = tmp / "i.db"
    st = SqliteStore(db, "tags")
    for i in range(100):
        st.set(f"p{i}.jpg", entree(i))
    st.save()
    # On simule un arrêt brutal : pas de close(), on abandonne l'objet.
    del st

    st2 = SqliteStore(db, "tags")
    verifie("base relisible après arrêt sans close()",
            len(st2.data) == 100, f"len={len(st2.data)}")
    st2.close()


def t_unicode_et_chemins_windows(tmp):
    """Clés réelles : chemins UNC, accents, espaces."""
    db = tmp / "j.db"
    st = SqliteStore(db, "tags")
    cles = [r"Photos\2024\Été à Bremblens\IMG_0421.JPG",
            r"\\NAS-Bremblens\home\Photos\Noël 2023\çà et là.jpg",
            "chat_küche_日本.jpg"]
    for i, k in enumerate(cles):
        st.set(k, {"kw_fr": ["été", "Noël", "chat"], "mtime": i})
    st.close()

    relu = contenu_brut(db, "tags")
    verifie("clés UNC / accentuées / non-latines préservées",
            set(relu) == set(cles), f"écart : {set(relu) ^ set(cles)}")
    verifie("valeurs accentuées préservées",
            all("été" in v["kw_fr"] for v in relu.values()))
    st = SqliteStore(db, "tags")
    st.close()


def t_open_store_repli(tmp):
    """Sans photos.db, on doit retomber sur le TagStore JSON, au bit près."""
    data_dir = tmp / "nas"
    data_dir.mkdir()
    js = data_dir / "tags_index.json"
    js.write_text(json.dumps({"x.jpg": {"kw_fr": ["a"]}}), encoding='utf-8')

    st = open_store(js, tmp / "vide", TagStoreJSON)
    verifie("repli sur TagStore JSON si photos.db absente",
            isinstance(st, TagStoreJSON), type(st).__name__)

    db_dir = tmp / "avecdb"
    db_dir.mkdir()
    SqliteStore(db_dir / "photos.db", "tags").close()
    st2 = open_store(js, db_dir, TagStoreJSON)
    verifie("bascule sur SqliteStore si photos.db présente",
            isinstance(st2, SqliteStore), type(st2).__name__)
    verifie("nom de table déduit du fichier JSON",
            st2.table == "tags", st2.table)
    st2.close()


def t_sauvegarde_et_export(tmp):
    """Snapshot atomique + export JSON de secours."""
    db = tmp / "k.db"
    st = SqliteStore(db, "tags")
    for i in range(40):
        st.set(f"s{i}.jpg", entree(i, avec_embedding=True))
    st.save()

    cible = tmp / "faux_nas" / "photos.db.bak"
    ok = st.backup_to(cible)
    verifie("sauvegarde créée", ok and cible.exists())
    if cible.exists():
        verifie("la sauvegarde contient les mêmes lignes",
                len(contenu_brut(cible, "tags")) == 40)
        verifie("aucun fichier temporaire laissé derrière",
                not list(cible.parent.glob("*.tmp")))

    expo = tmp / "faux_nas" / "tags_export.json"
    verifie("export JSON créé", st.export_json(expo) and expo.exists())
    if expo.exists():
        relu = json.loads(expo.read_text(encoding='utf-8'))
        verifie("export JSON relisible par TagStore", len(relu) == 40)
    st.close()


def t_cinq_stores_meme_base(tmp):
    """Configuration RÉELLE de server.py : 5 stores, une seule photos.db,
    threads concurrents (ThreadingHTTPServer)."""
    db = tmp / "photos.db"
    stores = {t: SqliteStore(db, t) for t in TABLES.values()}
    verifie("5 tables cohabitent dans une seule base", len(stores) == 5)

    erreurs = []

    def travail(nom, st):
        try:
            for i in range(40):
                st.set(f"{nom}_{i}", {"name": nom, "i": i, "kw_fr": ["x"]})
                if i % 10 == 0:
                    st.save()
        except Exception as e:                          # noqa: BLE001
            erreurs.append(f"{nom}: {e!r}")

    ths = [threading.Thread(target=travail, args=(n, s)) for n, s in stores.items()]
    for t in ths:
        t.start()
    for t in ths:
        t.join(timeout=60)

    verifie("écriture concurrente sur 5 tables sans erreur",
            not erreurs, str(erreurs[:2]))
    verifie("chaque table a bien ses 40 entrées",
            all(len(s.data) == 40 for s in stores.values()),
            {n: len(s.data) for n, s in stores.items()})

    # Sauvegarde depuis UN store : elle doit contenir les 5 tables.
    cible = tmp / "nas" / "photos.db.bak"
    for s in stores.values():
        s.save()
    ok = stores["tags"].backup_to(cible)
    verifie("sauvegarde déclenchée depuis un store", ok and cible.exists())
    if cible.exists():
        cx = sqlite3.connect(str(cible))
        tables = {r[0] for r in cx.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        cx.close()
        verifie("la sauvegarde contient les 5 tables",
                set(TABLES.values()) <= tables, tables)
        verifie("la sauvegarde contient les données des 5 tables",
                all(len(contenu_brut(cible, t)) == 40 for t in TABLES.values()))

    # Étanchéité : une clé identique dans deux tables ne doit pas se mélanger.
    stores["tags"].set("collision", {"origine": "tags"})
    stores["pets"].set("collision", {"origine": "pets"})
    for s in stores.values():
        s.close()
    verifie("pas de collision de clés entre tables",
            contenu_brut(db, "tags")["collision"]["origine"] == "tags"
            and contenu_brut(db, "pets")["collision"]["origine"] == "pets")


def t_copie_de_fiche(tmp):
    """Le motif qui a tué la fusion Flo -> Florine (server.py l. 824-905).

    `SubjectStore.rename` faisait `copy.deepcopy(self.store.data.get(old))` et
    mourait sur `cannot pickle '_thread.RLock' object`. La cause n'était dans
    aucun CHAMP de la fiche : une TrackedEntry est une sous-classe de dict, et
    `deepcopy` copie aussi l'état d'instance — donc `_store`, donc le RLock du
    SqliteStore. Ces vérifications tiennent la parade, et la DERNIÈRE prouve
    que le piège existe toujours (sans quoi elles ne prouveraient rien).
    """
    db = tmp / "fiches.db"
    st = SqliteStore(db, "people")
    st.set("flo", {"name": "Flo", "refs": ["r1"], "confirmed": ["a.jpg"],
                   "exclude": ["b.jpg"], "nomerge": ["florian"],
                   "avatar": ["c.jpg", 0], "faces": [["c.jpg", 0]],
                   "at": 1000.0})
    fiche = st.data.get("flo")

    verifie("la fiche vivante est bien une TrackedEntry",
            type(fiche).__name__ == "TrackedEntry", type(fiche).__name__)

    try:
        copie = copy.deepcopy(fiche)
        leve = None
    except Exception as e:                                    # noqa: BLE001
        copie, leve = None, repr(e)
    verifie("deepcopy d'une fiche vivante ne lève plus (motif de rename)",
            leve is None, f"a levé {leve}")

    if copie is not None:
        verifie("la copie est un dict NU, plus reliée au store",
                type(copie) is dict, type(copie).__name__)
        verifie("REGLE 2 : les décisions humaines survivent à la copie",
                (copie.get("confirmed") == ["a.jpg"]
                 and copie.get("exclude") == ["b.jpg"]
                 and copie.get("nomerge") == ["florian"]
                 and copie.get("avatar") == ["c.jpg", 0]
                 and copie.get("faces") == [["c.jpg", 0]]), f"copie={copie}")

        # PROFONDE : muter la copie ne doit toucher ni l'original ni la base.
        copie["confirmed"].append("intrus.jpg")
        st._dirty.clear()
        copie["name"] = "Intrus"
        verifie("muter la copie ne touche pas la fiche vivante",
                st.data.get("flo")["confirmed"] == ["a.jpg"]
                and st.data.get("flo")["name"] == "Flo",
                f"vivante={dict(st.data.get('flo'))}")
        verifie("muter la copie ne salit aucune clé (rien à réécrire)",
                st._dirty == set(), f"_dirty={st._dirty}")

    verifie("copy.copy d'une fiche rend un dict nu",
            type(copy.copy(fiche)) is dict, type(copy.copy(fiche)).__name__)

    try:
        rond = pickle.loads(pickle.dumps(fiche))
        verifie("pickle d'une fiche rend un dict nu et égal",
                type(rond) is dict and rond == dict(fiche), f"rond={type(rond)}")
    except Exception as e:                                    # noqa: BLE001
        verifie("pickle d'une fiche rend un dict nu et égal", False, repr(e))

    # L'index ENTIER porte le même défaut : `deepcopy(STORE.data)`.
    try:
        tout = copy.deepcopy(st.data)
        verifie("deepcopy de l'index entier rend des dicts nus",
                type(tout) is dict and type(tout["flo"]) is dict
                and tout["flo"]["name"] == "Flo", f"tout={type(tout)}")
    except Exception as e:                                    # noqa: BLE001
        verifie("deepcopy de l'index entier rend des dicts nus", False, repr(e))

    # LE PIÈGE EXISTE-T-IL ENCORE ? Si deepcopy(store) passait, c'est que le
    # verrou aurait disparu — et tous les tests ci-dessus ne prouveraient rien.
    try:
        copy.deepcopy(st)
        piege = False
    except TypeError:
        piege = True
    verifie("le verrou est toujours là (le test n'est pas vide)",
            piege, "deepcopy(SqliteStore) ne lève plus : test à revoir")

    st.close()


def t_performance(tmp):
    """Mesure indicative du gain, avec des entrées de taille réaliste."""
    N = 4000
    entrees = {f"f{i}.jpg": entree(i, avec_embedding=True) for i in range(N)}

    js_path = tmp / "perf.json"
    js = TagStoreJSON(js_path)
    js.data = dict(entrees)
    js._save()
    taille = js_path.stat().st_size

    t0 = time.perf_counter()
    for i in range(20):                       # 20 photos, motif du tagger
        js.set(f"nouveau{i}.jpg", entree(i, avec_embedding=True))
    t_json = time.perf_counter() - t0

    sq = SqliteStore(tmp / "perf.db", "faces")
    for k, v in entrees.items():
        sq.set(k, v, save=False)
    sq.save()
    t0 = time.perf_counter()
    for i in range(20):
        sq.set(f"nouveau{i}.jpg", entree(i, avec_embedding=True))
    t_sql = time.perf_counter() - t0
    sq.close()

    print(f"\n  -- Mesure indicative ({N} entrees, index de "
          f"{taille/1048576:.1f} Mo, disque LOCAL) --")
    print(f"     20 set() en JSON   : {t_json*1000:7.0f} ms "
          f"({taille*20/1048576:.0f} Mo réécrits)")
    print(f"     20 set() en SQLite : {t_sql*1000:7.0f} ms "
          f"(20 lignes écrites)")
    if t_sql > 0:
        print(f"     Gain               : ×{t_json/t_sql:.0f}")
    print("     Sur SMB, l'écart se creuse encore : c'est le volume écrit,")
    print("     et non le temps CPU, qui domine sur un partage réseau.")
    verifie("SQLite plus rapide que la réécriture JSON complète",
            t_sql < t_json, f"json={t_json:.3f}s sqlite={t_sql:.3f}s")


# ══════════════════════════════════════════════════════════════════════════
def main():
    # La console de l'agent git est en cp1252, et ce banc imprime des noms de
    # test qui contiennent du japonais -- c'est le SUJET de
    # `t_unicode_et_chemins_windows`, pas un accident. Sans cette ligne,
    # UnicodeEncodeError fait ROUGIR un banc qui passe 52/52, et la livraison
    # est refusee pour une raison qui n'existe pas. Un instrument qui ne peut
    # pas s'executer ne dit rien. `replace` degrade l'AFFICHAGE, jamais le
    # verdict : le code de sortie reste celui des tests.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(errors='replace')
        except (AttributeError, ValueError):        # flux capture, Python < 3.7
            pass
    tmp = Path(tempfile.mkdtemp(prefix="test_store_"))
    tests = [t_api_identique, t_equivalence_avec_json, t_mutation_imbriquee,
             t_ecriture_incrementale, t_remplacement_global, t_pop_direct,
             t_invariant_noms_humains, t_concurrence, t_resistance_coupure,
             t_unicode_et_chemins_windows, t_open_store_repli,
             t_sauvegarde_et_export, t_cinq_stores_meme_base,
             t_copie_de_fiche, t_performance]
    try:
        for t in tests:
            sous = tmp / t.__name__
            sous.mkdir(parents=True, exist_ok=True)
            try:
                t(sous)
            except Exception as e:                        # noqa: BLE001
                import traceback
                ECHECS.append(f"{t.__name__} a levé {e!r}")
                RESULTATS.append((t.__name__, False, repr(e)))
                traceback.print_exc()
    finally:
        pass

    print("\n" + "=" * 74)
    print("  RÉSULTATS")
    print("=" * 74)
    for nom, ok, detail in RESULTATS:
        print(f"  {'OK ' if ok else 'ECHEC'} {nom}"
              + (f"  -> {detail}" if not ok else ""))
    print("=" * 74)
    n_ok = sum(1 for _, ok, _ in RESULTATS if ok)
    print(f"  {n_ok}/{len(RESULTATS)} vérifications passées")
    if ECHECS:
        print(f"  ECHEC : {len(ECHECS)} test(s)")
    else:
        print("  OK : aucun echec")
    print("=" * 74)

    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if ECHECS else 0


if __name__ == '__main__':
    sys.exit(main())
