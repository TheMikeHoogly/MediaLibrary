"""
Tests de `purger_vecteurs_orphelins` — logique pure + aller-retour SQL sur une
base JETABLE (tempfile). `photos.db` n'est jamais ouverte : le serveur en est
l'ecrivain unique.

    python test_purger_vecteurs_orphelins.py
"""

import base64
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import purger_vecteurs_orphelins as P

OK = []
KO = []


def verifier(nom, condition, detail=''):
    (OK if condition else KO).append(nom)
    marque = 'ok  ' if condition else 'ECHEC'
    print(f"  [{marque}] {nom}" + (f" — {detail}" if detail and not condition
                                   else ''))


# ── Base jetable ────────────────────────────────────────────────────────────

def base_jetable(tags, vecteurs):
    """tags : liste de cles. vecteurs : liste de (kind, cle, octets)."""
    f = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    f.close()
    cx = sqlite3.connect(f.name)
    cx.execute("CREATE TABLE tags (k TEXT PRIMARY KEY, v TEXT)")
    cx.execute("""CREATE TABLE vectors (kind TEXT NOT NULL, k TEXT NOT NULL,
                    v BLOB NOT NULL, dtype TEXT NOT NULL DEFAULT 'f16',
                    ver TEXT, at REAL)""")
    cx.execute("CREATE UNIQUE INDEX ix_vectors_kind_k ON vectors(kind, k)")
    cx.executemany("INSERT INTO tags(k,v) VALUES(?,'{}')", [(k,) for k in tags])
    cx.executemany("INSERT INTO vectors(kind,k,v,dtype,ver,at) "
                   "VALUES(?,?,?,'f16','v1',1.0)", vecteurs)
    cx.commit()
    return cx, Path(f.name)


# ── 1. Selection ────────────────────────────────────────────────────────────

lignes = [('photo', 'a.jpg'), ('photo', 'perdu.jpg'),
          ('faces', 'a.jpg\x1ffaces\x1f0'), ('refs', 'mike\x1frefs\x1f0')]
orph, par_kind = P.selection(lignes, {'a.jpg'})
verifier("selection ne retient que kind=photo absent de tags",
         orph == [('photo', 'perdu.jpg')], str(orph))
verifier("selection compte tous les kinds",
         par_kind == {'photo': 2, 'faces': 1, 'refs': 1}, str(par_kind))
verifier("selection ne compare JAMAIS une cle composee",
         all(k == 'photo' for k, _ in orph))
verifier("selection dedoublonne et trie",
         P.selection([('photo', 'b'), ('photo', 'b'), ('photo', 'a')],
                     set())[0] == [('photo', 'a'), ('photo', 'b')])
verifier("une cle presente dans tags n'est jamais orpheline",
         P.selection([('photo', 'a.jpg')], {'a.jpg'})[0] == [])

# ── 2. Plafond ──────────────────────────────────────────────────────────────

verifier("plafond : 2 374 sur 91 000 passe",
         not P.depasse_plafond(2374, 91000))
verifier("plafond : 86 181 sur 91 000 refuse",
         P.depasse_plafond(86181, 91000))
verifier("plafond : exactement 20 % passe", not P.depasse_plafond(20, 100))
verifier("plafond : 21 % refuse", P.depasse_plafond(21, 100))
verifier("plafond : 0 orphelin ne declenche rien",
         not P.depasse_plafond(0, 0))
verifier("plafond : des orphelins sans comparable est une alarme",
         P.depasse_plafond(3, 0))

# ── 3. Partage selon le fichier ─────────────────────────────────────────────

sorts = {'absent.jpg': 'absent', 'la.jpg': 'present', 'nas.jpg': 'indetermine',
         'muet.jpg': 'present'}
absents, hors, epargnes, indets = P.partager(
    [('photo', 'absent.jpg'), ('photo', 'la.jpg'), ('photo', 'nas.jpg'),
     ('photo', 'muet.jpg')],
    lambda c: sorts[c], lambda c: c == 'la.jpg')
verifier("partage : fichier absent -> purge", absents == [('photo', 'absent.jpg')])
verifier("partage : present ET re-tague -> EPARGNE",
         epargnes == [('photo', 'la.jpg')])
verifier("partage : present mais hors portee -> purge (muet a vie)",
         hors == [('photo', 'muet.jpg')])
verifier("partage : racine injoignable -> on ne tranche pas",
         indets == [('photo', 'nas.jpg')])
verifier("partage : aucune cle perdue en route",
         len(absents) + len(hors) + len(epargnes) + len(indets) == 4)

# ── 3b. Portee du scan (replique de scan_uploads) ───────────────────────────

UP = Path(r'\\nas\home\Photos\_Uploads') if sys.platform == 'win32' \
    else Path('/nas/Photos/_Uploads')
EXTRA = [UP.parent]

verifier("portee : cle relative sous Uploads -> re-taguee",
         P.sera_re_tague('vacances/a.jpg', UP, EXTRA))
verifier("portee : cle relative dans un dossier CACHE -> hors portee",
         not P.sera_re_tague('.thumbs/a.jpg', UP, EXTRA))
verifier("portee : @eaDir (NAS) -> hors portee",
         not P.sera_re_tague('@eaDir/a.jpg', UP, EXTRA))
verifier("portee : extension non indexee -> hors portee",
         not P.sera_re_tague('notes/a.txt', UP, EXTRA))
verifier("portee : cle ABSOLUE sous un dossier a taguer -> re-taguee",
         P.sera_re_tague(str(UP.parent / '2019' / 'a.jpg'), UP, EXTRA))
verifier("portee : cle ABSOLUE dans l'arbre Uploads -> hors portee "
         "(seule la cle relative est indexee)",
         not P.sera_re_tague(str(UP / 'a.jpg'), UP, EXTRA))
verifier("portee : cle ABSOLUE hors de toute racine -> hors portee",
         not P.sera_re_tague(str(UP.parent.parent / 'ailleurs' / 'a.jpg'),
                             UP, [UP.parent / '2019']))
verifier("portee : corbeille de rangement (composant cache) -> hors portee",
         not P.sera_re_tague(
             str(UP.parent / '.corbeille-rangement' / 'a.jpg'), UP, EXTRA))

# ── 3c. Ventilation ─────────────────────────────────────────────────────────

v = P.ventilation([('photo', 'ads/ARZOPA/1.jpg'), ('photo', 'ads/ARZOPA/2.jpg'),
                   ('photo', 'seul.jpg')])
verifier("ventilation : le plus gros dossier en tete",
         v[0] == ('ads/ARZOPA', 2), str(v))
verifier("ventilation : une cle a plat est rangee sous (racine)",
         ('(racine)', 1) in v, str(v))

# ── 4. Quarantaine (forme) ──────────────────────────────────────────────────

l = P.ligne_quarantaine('photo', 'x.jpg', b'\x01\x02', 'f16', 'v1', 12.5)
verifier("quarantaine : le vecteur voyage en base64 sans perte",
         base64.b64decode(l['v_b64']) == b'\x01\x02')
verifier("quarantaine : dtype/ver/at conserves",
         (l['dtype'], l['ver'], l['at']) == ('f16', 'v1', 12.5))
verifier("horodatage : nom triable et sans caractere interdit",
         P.horodatage(0).startswith('vecteurs_orphelins_')
         and P.horodatage(0).endswith('.jsonl'))

# ── 5. Aller-retour purge / restauration sur base jetable ───────────────────

cx, chemin_db = base_jetable(
    tags=['garde.jpg'],
    vecteurs=[('photo', 'garde.jpg', b'\xaa' * 8),
              ('photo', 'perdu.jpg', b'\xbb' * 8),
              ('faces', 'garde.jpg\x1ffaces\x1f0', b'\xcc' * 8)])
orph, _ = P.selection(cx.execute('SELECT kind, k FROM vectors'), {'garde.jpg'})
q = Path(tempfile.mkdtemp()) / 'q.jsonl'
n_q = P.ecrire_quarantaine(cx, orph, q)
verifier("quarantaine ecrite pour chaque orphelin", n_q == len(orph) == 1)
supprimes, revenus = P.supprimer(cx, orph)
verifier("suppression : 1 ligne", supprimes == 1 and revenus == 0)
reste = {(k, c) for k, c in cx.execute('SELECT kind, k FROM vectors')}
verifier("la photo INDEXEE est intacte", ('photo', 'garde.jpg') in reste)
verifier("le vecteur de VISAGE (cle composee) est intact",
         ('faces', 'garde.jpg\x1ffaces\x1f0') in reste)
verifier("l'orphelin est parti", ('photo', 'perdu.jpg') not in reste)

restaures, deja = P.restaurer(cx, q)
verifier("restauration : la ligne revient", restaures == 1 and deja == 0)
r = cx.execute("SELECT v, dtype, ver, at FROM vectors WHERE kind='photo' "
               "AND k='perdu.jpg'").fetchone()
verifier("restauration : vecteur identique a l'octet pres", r[0] == b'\xbb' * 8)
verifier("restauration : dtype/ver/at identiques",
         (r[1], r[2], r[3]) == ('f16', 'v1', 1.0))

restaures2, deja2 = P.restaurer(cx, q)
verifier("restauration rejouee : idempotente, n'ecrase rien",
         restaures2 == 0 and deja2 == 1)

# une ligne re-indexee depuis la purge ne doit pas etre ecrasee
cx.execute("UPDATE vectors SET v=? WHERE kind='photo' AND k='perdu.jpg'",
           (b'\x99' * 8,))
cx.commit()
P.restaurer(cx, q)
verifier("restauration n'ecrase pas un vecteur plus recent",
         cx.execute("SELECT v FROM vectors WHERE kind='photo' AND "
                    "k='perdu.jpg'").fetchone()[0] == b'\x99' * 8)

# ── 6. Cle revenue dans tags entre le diagnostic et l'ecriture ──────────────

cx2, chemin_db2 = base_jetable(
    tags=[], vecteurs=[('photo', 'revenue.jpg', b'\xdd' * 8)])
candidats = [('photo', 'revenue.jpg')]
cx2.execute("INSERT INTO tags(k,v) VALUES('revenue.jpg','{}')")
cx2.commit()
supprimes2, revenus2 = P.supprimer(cx2, candidats)
verifier("une cle revenue dans tags n'est PAS supprimee",
         supprimes2 == 0 and revenus2 == 1)
verifier("son vecteur est toujours la",
         cx2.execute("SELECT count(*) FROM vectors WHERE k='revenue.jpg'"
                     ).fetchone()[0] == 1)

# ── 7. Quarantaine incomplete : rien ne part ────────────────────────────────

n = P.ecrire_quarantaine(cx2, [('photo', 'jamais_vue.jpg')],
                         Path(tempfile.mkdtemp()) / 'vide.jsonl')
verifier("quarantaine d'une cle absente : 0 ligne (le main s'arrete alors)",
         n == 0)

# ── 8. Garde-fou serveur ────────────────────────────────────────────────────

verifier("serveur_repond : port ferme -> faux",
         not P.serveur_repond(port=9, hote='127.0.0.1', delai=0.2))

import socket as _s
srv = _s.socket()
srv.bind(('127.0.0.1', 0))
srv.listen(1)
verifier("serveur_repond : port ouvert -> vrai",
         P.serveur_repond(port=srv.getsockname()[1], hote='127.0.0.1'))
srv.close()

cx.close()
cx2.close()
for p in (chemin_db, chemin_db2):
    try:
        p.unlink()
    except OSError:
        pass

print()
print(f"  {len(OK)} verification(s) OK, {len(KO)} echec(s)")
if KO:
    for nom in KO:
        print(f"    ECHEC : {nom}")
sys.exit(1 if KO else 0)
