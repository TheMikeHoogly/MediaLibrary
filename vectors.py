"""
Magasin de vecteurs — sortie des embeddings hors des index JSON.
──────────────────────────────────────────────────────────────────────────────

CONSTAT MESURÉ sur la base réelle (30 juillet 2026) :

    table     vecteurs   base64    part du JSON
    faces        7 531    9.8 Mo       95 %
    people       8 730   11.4 Mo       99 %   (champ « refs »)
    animals      1 634    3.2 Mo       67 %

24,4 Mo de vecteurs encodés en base64 À L'INTÉRIEUR du JSON. Les sortir en
BLOB divise par dix le poids des lignes, donc le coût de sérialisation, de
relecture au démarrage et d'empreinte.

PRINCIPE : LES OCTETS SONT PRÉSERVÉS À L'IDENTIQUE
    Les embeddings sont stockés tels quels — float16, exactement les mêmes
    octets que dans le base64 d'origine. Aucune requantification, aucune perte.
    Conséquence : les regroupements, les scores de similarité et les seuils
    (FACE_CLUSTER_SIM, PET_CLUSTER_SIM, FACE_MATCH_SIM…) donnent des résultats
    IDENTIQUES au bit près. Rien à recalibrer, rien à ré-embedder.

REPRÉSENTATION EN MÉMOIRE : INCHANGÉE
    server.py continue de lire e['faces'][i]['emb'] comme aujourd'hui. Les
    vecteurs sont réinjectés dans les entrées au chargement et retirés juste
    avant l'écriture. Aucun des sites d'appel existants n'est modifié.

RECHERCHE
    Recherche cosinus exhaustive par blocs (numpy, déjà installé). À l'échelle
    du projet — quelques dizaines de milliers de vecteurs — l'exhaustif est de
    l'ordre de la dizaine de millisecondes : un index approximatif (sqlite-vec,
    faiss, usearch) n'apporterait rien et ajouterait une dépendance. Voir le
    banc d'essai dans test_vectors.py.
"""

import base64
import sqlite3
import threading
import time

# ── Où trouver les vecteurs dans chaque type d'entrée ────────────────────────
# (champ_liste, sous_champ)  ; sous_champ=None → l'élément EST le vecteur.
VEC_SPECS = {
    'faces':   [('faces',   'emb')],     # e['faces'][i]['emb']      512×f16
    'animals': [('animals', 'emb')],     # e['animals'][i]['emb']    768×f16
    'people':  [('refs',    None)],      # e['refs'][i]             512×f16
    'pets':    [('refs',    None)],      # e['refs'][i]             768×f16
}

# Longueur base64 minimale pour qu'une chaîne soit considérée comme un vecteur.
# Protège contre l'extraction accidentelle d'un champ « refs » contenant des
# chemins de fichiers plutôt que des embeddings.
MIN_B64 = 200


def _est_vecteur(s):
    return isinstance(s, str) and len(s) >= MIN_B64


class VectorStore:
    """Table BLOB partagée par tous les types de vecteurs."""

    def __init__(self, cx):
        self.cx = cx
        self.lock = threading.RLock()
        self._cache = {}                 # kind -> (clés, matrice float32)
        self._init_schema()

    def _init_schema(self):
        # Table à rowid, PAS « WITHOUT ROWID ».
        # Une table WITHOUT ROWID range les lignes dans l'arbre d'index, où la
        # charge utile locale maximale est d'environ 1 000 octets sur des pages
        # de 4 Ko. Un vecteur de 1 024 octets la dépasse : chaque ligne partait
        # alors sur sa propre page de débordement et gaspillait ~3 Ko.
        # Mesuré sur la base réelle : 79,7 Mo de pages pour 19,9 Mo de données,
        # soit 25 % d'occupation. Une table à rowid loge la ligne entière dans
        # la page (limite ~4 060 octets) et remonte l'occupation au-delà de 90 %.
        anc = self.cx.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='vectors'"
        ).fetchone()
        if anc and 'WITHOUT ROWID' in (anc[0] or '').upper():
            self._reconstruire_sans_rowid()
            return
        self.cx.execute("""CREATE TABLE IF NOT EXISTS vectors (
                             kind TEXT NOT NULL,
                             k    TEXT NOT NULL,
                             v    BLOB NOT NULL,
                             dtype TEXT NOT NULL DEFAULT 'f16',
                             ver  TEXT,
                             at   REAL
                           )""")
        self.cx.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_vectors_kind_k "
                        "ON vectors(kind, k)")
        # Index sur k SEUL (audit O10) : rekey_prefix_all/delete_all filtrent
        # « k>=? AND k<? » sans kind — l'index (kind,k) ne sert alors à rien et
        # chaque photo renommée balayait les ~130 000 lignes deux fois. Avec le
        # plan de 2114 renommages : ~850 k lignes lues par lot. Coût : ~quelques
        # Mo, création unique au démarrage.
        self.cx.execute("CREATE INDEX IF NOT EXISTS ix_vectors_k ON vectors(k)")

    def _reconstruire_sans_rowid(self):
        """Reprend une table `vectors` créée en WITHOUT ROWID (schéma v1)."""
        cx = self.cx
        cx.execute("BEGIN IMMEDIATE")
        try:
            cx.execute("""CREATE TABLE vectors_v2 (
                            kind TEXT NOT NULL, k TEXT NOT NULL, v BLOB NOT NULL,
                            dtype TEXT NOT NULL DEFAULT 'f16', ver TEXT, at REAL)""")
            cx.execute("INSERT INTO vectors_v2(kind,k,v,dtype,ver,at) "
                       "SELECT kind,k,v,dtype,ver,at FROM vectors")
            cx.execute("DROP TABLE vectors")
            cx.execute("ALTER TABLE vectors_v2 RENAME TO vectors")
            cx.execute("CREATE UNIQUE INDEX ix_vectors_kind_k ON vectors(kind, k)")
            cx.execute("CREATE INDEX ix_vectors_k ON vectors(k)")
            cx.execute("COMMIT")
        except Exception:
            cx.execute("ROLLBACK")
            raise
        print("  ♻ Table « vectors » reconstruite (WITHOUT ROWID → rowid)")

    # ─────────────────────── écriture / lecture ───────────────────────

    def put_b64(self, kind, k, b64, ver=None):
        """Stocke un vecteur fourni en base64, sans le décoder ni le convertir."""
        self.cx.execute(
            "INSERT INTO vectors(kind,k,v,dtype,ver,at) VALUES(?,?,?,'f16',?,?) "
            "ON CONFLICT(kind,k) DO UPDATE SET v=excluded.v, ver=excluded.ver, "
            "at=excluded.at",
            (kind, k, base64.b64decode(b64), ver, time.time()))
        self._cache.pop(kind, None)

    def put_many_b64(self, kind, items, ver=None):
        maintenant = time.time()
        self.cx.executemany(
            "INSERT INTO vectors(kind,k,v,dtype,ver,at) VALUES(?,?,?,'f16',?,?) "
            "ON CONFLICT(kind,k) DO UPDATE SET v=excluded.v, ver=excluded.ver, "
            "at=excluded.at",
            [(kind, k, base64.b64decode(b), ver, maintenant) for k, b in items])
        self._cache.pop(kind, None)

    def get_b64(self, kind, k):
        r = self.cx.execute("SELECT v FROM vectors WHERE kind=? AND k=?",
                            (kind, k)).fetchone()
        return base64.b64encode(r[0]).decode() if r else None

    def prefix_b64(self, kind, prefixe):
        """Tous les vecteurs d'une entrée : {clé_complète: base64}."""
        cur = self.cx.execute(
            "SELECT k, v FROM vectors WHERE kind=? AND k>=? AND k<?",
            (kind, prefixe, prefixe + '￿'))
        return {k: base64.b64encode(v).decode() for k, v in cur}

    def load_all_b64(self, kind):
        cur = self.cx.execute("SELECT k, v FROM vectors WHERE kind=?", (kind,))
        return {k: base64.b64encode(v).decode() for k, v in cur}

    def delete_prefix(self, kind, prefixes):
        self.cx.executemany(
            "DELETE FROM vectors WHERE kind=? AND k>=? AND k<?",
            [(kind, p, p + '￿') for p in prefixes])
        self._cache.pop(kind, None)

    def rekey_prefix(self, kind, old, new):
        """Re-clé les vecteurs d'une entrée quand sa CLÉ PHOTO passe de `old` à
        `new` (déplacement / renommage). Les clés vecteurs valent
        « {clé_photo}\\x1f{champ}\\x1f{index} » : on ne réécrit QUE le préfixe
        « {clé_photo} », le suffixe (champ, index) est préservé à l'octet près —
        donc AUCUNE empreinte n'est perdue ni recalculée.

        Sans cette méthode, un déplacement de masse orienterait les empreintes
        vers le vide : c'est le prérequis bloquant de la Phase 1 du rangement
        (voir docs/RANGEMENT_2026.md).

        La borne est prise sur « old + '\\x1f' » — le séparateur EXACT que
        `_ecrire` utilise déjà pour purger (`f"{k}\\x1f"`). Contrairement à
        `delete_prefix` (préfixe lâche), on exige donc le séparateur : on ne
        touche jamais les vecteurs d'une AUTRE photo dont la clé aurait `old`
        pour simple préfixe (« a/b.jpg » ne doit pas emporter « a/b.jpg2 »).

        Renvoie le nombre de lignes re-clées. Idempotent : rejoué, il ne trouve
        plus l'ancien préfixe et renvoie 0. En cas de collision avec des clés
        déjà présentes sous `new` (index UNIQUE (kind,k)), SQLite lève et
        annule l'UPDATE en entier — échec bruyant, pas de corruption partielle.
        """
        lo = old + '\x1f'
        hi = old + '\x1f' + '￿'
        n = self.cx.execute(
            "UPDATE vectors SET k = ? || substr(k, ?) "
            "WHERE kind=? AND k>=? AND k<?",
            (new, len(old) + 1, kind, lo, hi)).rowcount
        if n:
            self._cache.pop(kind, None)
        return n

    def rekey_prefix_all(self, old, new):
        """Re-clé TOUS les vecteurs appartenant à la photo `old`, quel que soit
        le `kind`, quand son chemin passe à `new`. Deux formes de clé coexistent
        dans la table et doivent TOUTES DEUX suivre :

          - clés à suffixe « {chemin}\\x1f{champ}\\x1f{i} » (visages, animaux,
            refs personnes/animaux) — on réécrit le seul préfixe, suffixe
            préservé à l'octet près ;
          - clé NUE « {chemin} » sans séparateur — c'est la forme du magasin
            SÉMANTIQUE (`kind='photo'`), un unique vecteur par photo keyé par
            son seul chemin. La borne `old + '\\x1f'` de la première forme
            l'EXCLUT ; sans le second UPDATE ci-dessous, le vecteur sémantique
            resterait orphelin sous l'ancienne clé (bug attrapé par
            test_rekey_everywhere.py sur données réelles).

        Les deux réécritures sont faites dans une même transaction : une
        collision sur l'index UNIQUE(kind,k) annule l'ensemble — échec bruyant,
        jamais de corruption partielle. La clé nue est appariée à l'identique
        (`k = old`), donc un voisin « {old}2 » n'est jamais touché.

        Renvoie le nombre total de lignes re-clées. Idempotent (rejoué → 0)."""
        lo = old + '\x1f'
        hi = old + '\x1f' + '￿'
        cx = self.cx
        cx.execute("BEGIN IMMEDIATE")
        try:
            n = cx.execute(
                "UPDATE vectors SET k = ? || substr(k, ?) WHERE k>=? AND k<?",
                (new, len(old) + 1, lo, hi)).rowcount
            n += cx.execute(
                "UPDATE vectors SET k = ? WHERE k = ?", (new, old)).rowcount
            cx.execute("COMMIT")
        except Exception:
            cx.execute("ROLLBACK")
            raise
        if n:
            self._cache.clear()
        return n

    def delete_all(self, key):
        """Supprime TOUS les vecteurs de la photo `key`, quel que soit le `kind`.
        Miroir de `rekey_prefix_all` pour la SUPPRESSION (fichier disparu) : les
        deux formes de cle doivent partir —
          - suffixe « {key}\\x1f{champ}\\x1f{i} » (visages/animaux/refs) ;
          - cle NUE « {key} » (magasin semantique, kind='photo').
        La cle nue est appariee a l'identique (`k = key`) : un voisin « {key}2 »
        n'est jamais touche. Une seule transaction ; en cas d'echec, ROLLBACK
        complet (pas de suppression partielle). Renvoie le nombre de lignes
        supprimees. Idempotent (rejoue -> 0)."""
        lo = key + '\x1f'
        hi = key + '\x1f' + '￿'
        cx = self.cx
        cx.execute("BEGIN IMMEDIATE")
        try:
            n = cx.execute(
                "DELETE FROM vectors WHERE k>=? AND k<?", (lo, hi)).rowcount
            n += cx.execute(
                "DELETE FROM vectors WHERE k = ?", (key,)).rowcount
            cx.execute("COMMIT")
        except Exception:
            cx.execute("ROLLBACK")
            raise
        if n:
            self._cache.clear()
        return n

    def count(self, kind=None):
        if kind:
            return self.cx.execute("SELECT count(*) FROM vectors WHERE kind=?",
                                   (kind,)).fetchone()[0]
        return self.cx.execute("SELECT count(*) FROM vectors").fetchone()[0]

    def kinds(self):
        return {k: n for k, n in self.cx.execute(
            "SELECT kind, count(*) FROM vectors GROUP BY kind")}

    # ─────────────────────────── recherche ───────────────────────────

    def matrice(self, kind, forcer=False):
        """Matrice float32 normalisée (n, d) + liste des clés, mise en cache."""
        import numpy as np
        with self.lock:
            if not forcer and kind in self._cache:
                return self._cache[kind]
            cles, blobs = [], []
            for k, v in self.cx.execute(
                    "SELECT k, v FROM vectors WHERE kind=? ORDER BY k", (kind,)):
                cles.append(k)
                blobs.append(v)
            if not cles:
                vide = ([], np.zeros((0, 0), dtype=np.float32))
                self._cache[kind] = vide
                return vide
            d = len(blobs[0]) // 2                      # float16 → 2 octets
            M = np.empty((len(blobs), d), dtype=np.float32)
            for i, b in enumerate(blobs):
                if len(b) // 2 != d:                    # dimension hétérogène
                    M[i] = 0.0
                    continue
                M[i] = np.frombuffer(b, dtype=np.float16).astype(np.float32)
            n = np.linalg.norm(M, axis=1, keepdims=True)
            n[n == 0] = 1.0
            M /= n
            self._cache[kind] = (cles, M)
            return self._cache[kind]

    def search(self, kind, q, limite=60, seuil=None, bloc=8192,
               restreindre=None):
        """Recherche cosinus exhaustive. Renvoie [(clé, score)] décroissant.

        `restreindre` : ensemble de clés auxquelles limiter la recherche. Sert
        à la recherche hybride — d'abord filtrer sur un tag humain
        (« animal:Luna »), puis classer ce sous-ensemble par le sens.
        """
        import numpy as np
        cles, M = self.matrice(kind)
        if not cles:
            return []
        if restreindre is not None:
            pos = [i for i, k in enumerate(cles) if k in restreindre]
            if not pos:
                return []
            idx = np.asarray(pos)
            cles = [cles[i] for i in pos]
            M = M[idx]
        q = np.asarray(q, dtype=np.float32).ravel()
        if q.shape[0] != M.shape[1]:
            raise ValueError(f"dimension {q.shape[0]} ≠ {M.shape[1]} pour « {kind} »")
        nq = float(np.linalg.norm(q))
        if nq:
            q = q / nq
        # Par blocs : la mémoire temporaire reste bornée quelle que soit la taille.
        meilleurs = []
        for début in range(0, M.shape[0], bloc):
            s = M[début:début + bloc] @ q
            if seuil is not None:
                idx = np.nonzero(s >= seuil)[0]
            else:
                k = min(limite, s.shape[0])
                idx = np.argpartition(-s, k - 1)[:k] if k < s.shape[0] else \
                    np.arange(s.shape[0])
            meilleurs.extend((cles[début + int(i)], float(s[int(i)])) for i in idx)
        meilleurs.sort(key=lambda t: -t[1])
        return meilleurs[:limite]

    def invalider(self, kind=None):
        with self.lock:
            if kind:
                self._cache.pop(kind, None)
            else:
                self._cache.clear()


# ─────────────── extraction / réinjection dans les entrées ───────────────

def extraire(entry, spec, cle, vecstore, kind, ver=None):
    """Retire les vecteurs de `entry` (copie) et les range dans le magasin.

    Renvoie une COPIE allégée de l'entrée. L'entrée d'origine, celle qui vit en
    mémoire dans server.py, n'est jamais modifiée.
    """
    if not spec:
        return entry
    allege = dict(entry)
    lots = []
    for champ, sous in spec:
        liste = entry.get(champ)
        if not isinstance(liste, list) or not liste:
            continue
        neuve = []
        change = False
        for i, it in enumerate(liste):
            vk = f"{cle}\x1f{champ}\x1f{i}"
            if sous is None:
                if _est_vecteur(it):
                    lots.append((vk, it))
                    neuve.append(None)          # place tenue, réinjectée au chargement
                    change = True
                else:
                    neuve.append(it)
            elif isinstance(it, dict) and _est_vecteur(it.get(sous)):
                lots.append((vk, it[sous]))
                copie = dict(it)
                copie.pop(sous, None)
                neuve.append(copie)
                change = True
            else:
                neuve.append(it)
        if change:
            allege[champ] = neuve
    if lots:
        vecstore.put_many_b64(kind, lots, ver=ver)
    return allege


def reinjecter(entry, spec, vecteurs, cle):
    """Remet les vecteurs dans l'entrée relue. `vecteurs` = {clé_vec: base64}."""
    if not spec or not vecteurs:
        return entry
    for champ, sous in spec:
        liste = entry.get(champ)
        if not isinstance(liste, list):
            continue
        for i, it in enumerate(liste):
            b64 = vecteurs.get(f"{cle}\x1f{champ}\x1f{i}")
            if b64 is None:
                continue
            if sous is None:
                liste[i] = b64
            elif isinstance(it, dict):
                it[sous] = b64
    return entry
