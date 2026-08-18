"""
Persistance SQLite des index — remplacement compatible de TagStore.
──────────────────────────────────────────────────────────────────────────────

POURQUOI
    TagStore charge tout le JSON en mémoire et RÉÉCRIT LE FICHIER ENTIER à
    chaque set(). Avec 16 000 visages et leurs embeddings en base64, cela fait
    ~43 Mo réécrits sur un partage SMB à chaque photo traitée.

    SqliteStore garde le dictionnaire en mémoire (donc les 99 accès à `.data`
    dans server.py continuent de fonctionner à l'identique) mais n'écrit plus
    que les LIGNES MODIFIÉES.

OÙ VIT LA BASE
    Sur le DISQUE LOCAL, jamais sur le NAS : SQLite sur SMB a un verrouillage
    de fichier non fiable et le mode WAL y est indisponible — c'est le scénario
    de corruption classique. La sécurité des données est assurée autrement, par
    snapshot atomique vers le NAS (voir backup_to()).

COMPATIBILITÉ
    API identique à TagStore : data, get, set, save, _save, has, rekey,
    remove_many, tagged_count, lock, path.
    Le verrou est un RLock (et non un Lock) car server.py appelle _save()
    à l'intérieur de `with STORE.lock:` (l. 584-593, 733-743, 3822-3831, 4543).

COMPTES (17/08/2026 → 18/08)
    `TrackedDict` est le GOULOT par lequel passe toute clé qui entre ou sort de
    l'index EN MÉMOIRE. Un `RegistreOublis` (module `comptes_index.py`) peut y
    être branché après construction (`brancher_registre`) : il compte alors les
    ajouts et les retraits, avec le motif déclaré par l'appelant. Sans registre
    branché, le comportement est inchangé au bit près (un test `is None`).

CONVERGENCE
    Les mutations imbriquées d'un niveau (`e = STORE.data.get(k); e['x'] = 1`)
    sont détectées automatiquement : les entrées sont des TrackedEntry qui
    signalent leur propre clé. Pour les mutations plus profondes
    (`e['refs'].append(...)`), save() et _save() font une réconciliation
    complète par empreinte — la convergence est donc garantie à chaque fin de
    lot, sans coût d'écriture réseau.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

try:
    from vectors import VEC_SPECS, VectorStore, extraire, reinjecter
except ImportError:                     # module absent → stockage tout-JSON
    VEC_SPECS = {}
    VectorStore = None

SCHEMA_VERSION = 2


def _empreinte(entry):
    """Empreinte stable du contenu d'une entrée (détection de changement)."""
    blob = json.dumps(entry, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')
    return hashlib.blake2b(blob, digest_size=16).digest()


class TrackedEntry(dict):
    """Entrée d'index qui signale au store toute mutation de premier niveau."""

    __slots__ = ('_store', '_key')

    def __init__(self, store, key, data=None):
        super().__init__(data or {})
        self._store = store
        self._key = key

    def _touch(self):
        st = self._store
        if st is not None:
            st._dirty.add(self._key)

    def __setitem__(self, k, v):
        super().__setitem__(k, v)
        self._touch()

    def __delitem__(self, k):
        super().__delitem__(k)
        self._touch()

    def pop(self, *a):
        r = super().pop(*a)
        self._touch()
        return r

    def popitem(self):
        r = super().popitem()
        self._touch()
        return r

    def clear(self):
        super().clear()
        self._touch()

    def update(self, *a, **kw):
        super().update(*a, **kw)
        self._touch()

    def setdefault(self, k, d=None):
        avant = k in self
        r = super().setdefault(k, d)
        if not avant:
            self._touch()
        return r


class TrackedDict(dict):
    """Index qui signale les ajouts/suppressions de clés.

    GOULOT DES COMPTES : toute clé qui entre ou sort de l'index en mémoire passe
    ici. Si un `RegistreOublis` est branché sur le store, il est notifié — c'est
    ce qui rend « ce que le scan oublie » comptable (cf. comptes_index.py).
    Seules les variations de TAILLE sont signalées : réécrire une clé existante
    n'est ni un ajout ni un retrait.
    """

    __slots__ = ('_store',)

    def __init__(self, store):
        super().__init__()
        self._store = store

    def _wrap(self, k, v):
        if isinstance(v, TrackedEntry) and v._key == k and v._store is self._store:
            return v
        return TrackedEntry(self._store, k, v if isinstance(v, dict) else {})

    def _reg(self):
        """Registre branché, ou None. Jamais d'exception : un instrument ne doit
        pas casser le programme qu'il observe."""
        return getattr(self._store, '_registre', None)

    def __setitem__(self, k, v):
        neuve = k not in self
        super().__setitem__(k, self._wrap(k, v))
        self._store._dirty.add(k)
        if neuve:
            r = self._reg()
            if r is not None:
                r.cle_ajoutee(k)

    def __delitem__(self, k):
        super().__delitem__(k)
        self._store._supprimes.add(k)
        self._store._dirty.discard(k)
        r = self._reg()
        if r is not None:
            r.cle_retiree(k)

    def pop(self, k, *d):
        présent = k in self
        r = super().pop(k, *d)
        if présent:
            self._store._supprimes.add(k)
            self._store._dirty.discard(k)
            reg = self._reg()
            if reg is not None:
                reg.cle_retiree(k)
        return r

    def popitem(self):
        k, v = super().popitem()
        self._store._supprimes.add(k)
        self._store._dirty.discard(k)
        reg = self._reg()
        if reg is not None:
            reg.cle_retiree(k)
        return k, v

    def clear(self):
        cles = list(self.keys())
        self._store._supprimes.update(cles)
        self._store._dirty.clear()
        super().clear()
        reg = self._reg()
        if reg is not None:
            reg.cles_retirees(cles)

    def update(self, *a, **kw):
        for k, v in dict(*a, **kw).items():
            self[k] = v

    def setdefault(self, k, d=None):
        if k not in self:
            self[k] = d if d is not None else {}
        return self[k]


class SqliteStore:
    """Remplacement de TagStore : même API, persistance incrémentale."""

    def __init__(self, db_path, table, legacy_path=None):
        self.db_path = Path(db_path)
        self.table = table
        # `path` reste exposé pour les messages d'erreur de server.py
        self.path = Path(legacy_path) if legacy_path else self.db_path
        self.lock = threading.RLock()          # RLock : _save() est appelé sous lock
        self._dirty = set()
        self._supprimes = set()
        # Carnet de comptes des ajouts/retraits de cles (comptes_index.py).
        # None = non branche -> aucun cout, comportement historique.
        self._registre = None
        self._hash = {}                        # clé -> empreinte persistée
        self._d = TrackedDict(self)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(str(self.db_path), check_same_thread=False,
                                  timeout=30.0, isolation_level=None)
        self._init_schema()
        # Sortie des embeddings hors du JSON (voir vectors.py). Les octets
        # float16 sont conservés à l'identique : aucun seuil à recalibrer.
        self.vec_spec = VEC_SPECS.get(table)
        self.vec = VectorStore(self.cx) if (VectorStore and self.vec_spec) else None
        self._charger()

    # ─────────────────────────── interne ───────────────────────────

    def _init_schema(self):
        cx = self.cx
        cx.execute("PRAGMA journal_mode=WAL")      # possible car disque LOCAL
        cx.execute("PRAGMA synchronous=NORMAL")
        cx.execute("PRAGMA busy_timeout=30000")
        cx.execute(f"""CREATE TABLE IF NOT EXISTS "{self.table}" (
                          k TEXT PRIMARY KEY,
                          v TEXT NOT NULL
                       ) WITHOUT ROWID""")
        cx.execute("""CREATE TABLE IF NOT EXISTS _meta (
                         k TEXT PRIMARY KEY, v TEXT)""")
        cx.execute("INSERT OR IGNORE INTO _meta(k,v) VALUES('schema',?)",
                   (str(SCHEMA_VERSION),))

    def _charger(self):
        # Les vecteurs sont relus en un seul balayage puis réinjectés dans les
        # entrées : la représentation en mémoire redevient exactement celle
        # qu'attend server.py (e['faces'][i]['emb'], e['refs'][i]…).
        vecteurs = self.vec.load_all_b64(self.table) if self.vec else None
        cur = self.cx.execute(f'SELECT k, v FROM "{self.table}"')
        d = dict.__setitem__
        for k, v in cur:
            try:
                e = json.loads(v)
            except (ValueError, TypeError):
                continue
            if vecteurs:
                e = reinjecter(e, self.vec_spec, vecteurs, k)
            d(self._d, k, TrackedEntry(self, k, e))
            self._hash[k] = _empreinte(e)
        self._dirty.clear()
        self._supprimes.clear()

    def _ecrire(self, clés, supprimées):
        """Écrit les lignes indiquées en une seule transaction."""
        cx = self.cx
        cx.execute("BEGIN IMMEDIATE")
        try:
            if supprimées:
                cx.executemany(f'DELETE FROM "{self.table}" WHERE k=?',
                               [(k,) for k in supprimées])
                if self.vec:
                    self.vec.delete_prefix(self.table,
                                           [f"{k}\x1f" for k in supprimées])
            if self.vec and clés:
                # Purge des anciens vecteurs EN UN SEUL APPEL. Le faire clé par
                # clé transformait un lot de 4 000 lignes en 4 000 requêtes :
                # mesuré à plus de 40 s contre moins d'une seconde ici.
                self.vec.delete_prefix(self.table, [f"{k}\x1f" for k in clés])
            lignes = []
            for k in clés:
                e = self._d.get(k)
                if e is None:
                    continue
                brut = dict(e)
                if self.vec:
                    # Les vecteurs partent en BLOB ; la ligne JSON ne garde que
                    # les métadonnées. L'entrée en mémoire n'est pas touchée.
                    brut = extraire(brut, self.vec_spec, k, self.vec, self.table)
                lignes.append((k, json.dumps(brut, ensure_ascii=False,
                                             separators=(',', ':'))))
            if lignes:
                cx.executemany(
                    f'INSERT INTO "{self.table}"(k,v) VALUES(?,?) '
                    'ON CONFLICT(k) DO UPDATE SET v=excluded.v', lignes)
            cx.execute("COMMIT")
        except Exception:
            cx.execute("ROLLBACK")
            raise
        for k in supprimées:
            self._hash.pop(k, None)
        for k in clés:
            e = self._d.get(k)
            if e is not None:
                self._hash[k] = _empreinte(dict(e))

    def _flush_rapide(self):
        """Chemin chaud (set) : n'écrit que ce qui a été signalé."""
        clés = {k for k in self._dirty if k in self._d}
        supprimées = set(self._supprimes)
        self._dirty.clear()
        self._supprimes.clear()
        if clés or supprimées:
            self._ecrire(clés, supprimées)
        return len(clés) + len(supprimées)

    def _reconcilier(self):
        """Fin de lot : garantit la convergence, y compris mutations profondes."""
        clés = set()
        for k, e in self._d.items():
            h = _empreinte(dict(e))
            if self._hash.get(k) != h:
                clés.add(k)
        supprimées = set(self._supprimes) | (set(self._hash) - set(self._d))
        self._dirty.clear()
        self._supprimes.clear()
        if clés or supprimées:
            self._ecrire(clés, supprimées)
        return len(clés) + len(supprimées)

    # ─────────────────────── API TagStore ───────────────────────

    @property
    def data(self):
        return self._d

    @data.setter
    def data(self, valeur):
        """Remplacement global (server.py : ANIMAL_STORE.data = {}).

        Ce chemin vide le dict PAR EN DESSOUS (`dict.clear`) : il court-circuite
        `TrackedDict.clear` et donc le goulot des comptes. Il DÉCLARE donc
        lui-même ses retraits — sans quoi la réconciliation les prendrait pour
        un écart inexpliqué, c'est-à-dire un faux positif sur le seul chiffre
        qui doit rester digne de foi.
        """
        with self.lock:
            anciennes = list(self._d.keys())
            self._supprimes.update(anciennes)
            dict.clear(self._d)
            if self._registre is not None and anciennes:
                self._registre.cles_retirees(anciennes)
            for k, v in (valeur or {}).items():
                self._d[k] = v

    def brancher_registre(self, registre):
        """Branche (ou débranche avec None) le carnet de comptes.

        À appeler APRÈS construction : `_charger()` remplit le dict par en
        dessous (`dict.__setitem__`), donc le chargement initial n'est pas
        compté — ce qui est voulu : le point de départ de la réconciliation est
        `len(store.data)` au premier cycle, pas un cumul d'ajouts fictifs.
        """
        with self.lock:
            self._registre = registre
        return registre

    def has(self, name):
        e = self._d.get(name)
        return bool(e) and not e.get('failed')

    def get(self, name):
        return self._d.get(name)

    def set(self, name, entry, save=True):
        with self.lock:
            self._d[name] = entry
            if save:
                self._flush_rapide()

    def save(self):
        with self.lock:
            self._reconcilier()

    def _save(self):
        """Appelé par server.py DÉJÀ sous `with STORE.lock:` — ne reverrouille pas
        (le RLock rendrait la chose inoffensive, mais on reste fidèle à TagStore)."""
        self._reconcilier()

    def rekey(self, old, new, mtime=None):
        with self.lock:
            e = self._d.pop(old, None)
            if e is None:
                return False
            plain = dict(e)
            if mtime is not None:
                plain['mtime'] = mtime
            self._d[new] = plain
            return True

    def remove_many(self, keys):
        with self.lock:
            n = 0
            for k in keys:
                if self._d.pop(k, None) is not None:
                    n += 1
            if n:
                self._flush_rapide()
            return n

    def tagged_count(self):
        return sum(1 for e in self._d.values()
                   if not e.get('failed') and (e.get('kw_fr') or e.get('kw_en')))

    # ─────────────────────── sauvegarde NAS ───────────────────────

    def backup_to(self, cible):
        """Snapshot atomique de la base vers le NAS.

        VACUUM INTO produit un fichier cohérent même pendant l'écriture. On
        écrit d'abord en local, on copie, puis on renomme SUR LA CIBLE : le
        fichier de sauvegarde n'est donc jamais vu à moitié écrit.
        """
        cible = Path(cible)
        tmp_local = self.db_path.with_suffix('.snapshot.tmp')
        tmp_cible = cible.with_suffix(cible.suffix + '.tmp')
        try:
            if tmp_local.exists():
                tmp_local.unlink()
            with self.lock:
                self._reconcilier()
                self.cx.execute("VACUUM INTO ?", (str(tmp_local),))
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp_local, tmp_cible)
            os.replace(tmp_cible, cible)          # atomique côté NAS
            return True
        except (sqlite3.Error, OSError) as e:
            print(f"  ⚠ Sauvegarde de {cible.name} impossible : {e}")
            return False
        finally:
            try:
                tmp_local.unlink()
            except OSError:
                pass

    def export_json(self, cible):
        """Export lisible, en filet de sécurité (relisible par TagStore)."""
        cible = Path(cible)
        tmp = cible.with_name(cible.name + '.tmp')
        try:
            with self.lock:
                brut = {k: dict(v) for k, v in self._d.items()}
            tmp.write_text(json.dumps(brut, ensure_ascii=False, indent=1),
                           encoding='utf-8')
            os.replace(tmp, cible)
            return True
        except OSError as e:
            print(f"  ⚠ Export JSON de {cible.name} impossible : {e}")
            return False

    def close(self):
        with self.lock:
            try:
                self._reconcilier()
            finally:
                self.cx.close()

    def stats(self):
        return {'table': self.table, 'lignes': len(self._d),
                'db': str(self.db_path),
                'taille_db': self.db_path.stat().st_size
                             if self.db_path.exists() else 0}


# ─────────────────────────── fabrique ───────────────────────────

DB_NAME = "photos.db"

# Nom de table par fichier JSON historique.
TABLES = {
    "tags_index.json":    "tags",
    "animals_index.json": "animals",
    "faces_index.json":   "faces",
    "people.json":        "people",
    "pets.json":          "pets",
}


def open_store(legacy_json_path, db_dir, fallback_cls):
    """Ouvre le store SQLite si la base existe, sinon le TagStore JSON.

    Aucune migration implicite : tant que `photos.db` n'a pas été créée par
    `migrate_to_sqlite.py`, le comportement historique est conservé au bit près.
    Supprimer photos.db suffit à revenir au JSON — le retour arrière est trivial.
    """
    legacy_json_path = Path(legacy_json_path)
    db = Path(db_dir) / DB_NAME
    table = TABLES.get(legacy_json_path.name)
    if table is None or not db.exists():
        return fallback_cls(legacy_json_path)
    return SqliteStore(db, table, legacy_path=legacy_json_path)
