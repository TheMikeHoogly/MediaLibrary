"""
Diagnostic READ-ONLY des entrees orphelines (fichier disparu).
──────────────────────────────────────────────────────────────────────────────

LE PROBLEME (constate le 08/08, cas « ARZOPA »)
    Quand un fichier disparait, `scan_uploads` -> `_sync_dir` etape 4 ne purge
    que le TagStore (`STORE.remove_many`). Les detections de VISAGES (table
    faces) et d'ANIMAUX (table animals), ainsi que les vecteurs semantiques, NE
    sont PAS retires. Un dossier supprime (ex. « ARZOPA ») laisse donc des
    detections orphelines qui gonflent les compteurs et peuvent etre proposees
    au nommage alors que la photo n'existe plus.

CE QUE FAIT CE SCRIPT (et RIEN d'autre)
    Il resout chaque cle des tables faces/animals vers son chemin, et compte les
    ORPHELINS (fichier absent). Garde-fou anti-faux-positif : un orphelin n'est
    compte que si sa RACINE est joignable (sinon « indetermine » — un NAS
    deconnecte ferait passer tout le corpus pour disparu). Il distingue les
    orphelins NOMMES (photo portant `personne:`/`animal:`) et ceux juges par un
    humain (`par_humain`) — les cas a manier avec le plus de soin.

    LECTURE SEULE : ouvre photos.db en mode=ro, n'ecrit jamais. C'est le
    diagnostic qui precede le correctif de cascade (forget_everywhere).

USAGE (machine reelle, NAS joignable pour un compte fiable)
    .venv\\Scripts\\python.exe verifier_orphelins.py                 # faces + animals
    .venv\\Scripts\\python.exe verifier_orphelins.py --filtre ARZOPA # cible rapide
    .venv\\Scripts\\python.exe verifier_orphelins.py --table faces --echantillon 30

    Note : sans filtre, ce script fait un stat par fichier (lent sur SMB pour des
    dizaines de milliers d'entrees). --filtre restreint aux cles contenant un
    texte (ex. un dossier), quasi instantane.

    La logique pure (noms_humains / statut / resoudre) est testee hors machine
    par test_verifier_orphelins.py.
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "photos.db"
DEFAUT_DATA_DIR = r"\\nas-bremblens\home\Uploads"


# ── Logique PURE (testable sans base ni NAS) ────────────────────────────────

def noms_humains(kw):
    """Prefixes de noms humains presents dans une liste de mots-cles.
    Renvoie un sous-ensemble de {'personne', 'animal'}."""
    out = set()
    for t in kw or []:
        s = str(t).lower()
        if s.startswith('personne:'):
            out.add('personne')
        elif s.startswith('animal:'):
            out.add('animal')
    return out


def statut(joignable, existe):
    """'indetermine' si la racine est injoignable (on ne tranche pas), sinon
    'present' ou 'orphelin'. Ne jamais declarer orphelin un fichier dont la
    racine n'a pas pu etre listee : c'est la lecon du nettoyage de scan_uploads."""
    if not joignable:
        return 'indetermine'
    return 'present' if existe else 'orphelin'


def resoudre(cle, upload_dir):
    """Cle d'index -> chemin. Meme regle que server._resolve_key : chemin absolu
    tel quel, sinon relatif au dossier Uploads."""
    p = Path(cle)
    return p if p.is_absolute() else Path(upload_dir) / cle


# ── Configuration (repliquee, SANS importer server.py) ──────────────────────

def _premiere_ligne(nom):
    try:
        for l in (SCRIPT_DIR / nom).read_text(encoding='utf-8').splitlines():
            l = l.strip()
            if l and not l.startswith('#'):
                return l
    except OSError:
        pass
    return None


def _lignes(nom):
    out = []
    try:
        for l in (SCRIPT_DIR / nom).read_text(encoding='utf-8').splitlines():
            l = l.strip()
            if l and not l.startswith('#'):
                out.append(l)
    except OSError:
        pass
    return out


def config_racines():
    data_dir = Path(_premiere_ligne("data_dir.txt") or DEFAUT_DATA_DIR)
    upload_dir = Path(_premiere_ligne("dossier_uploads.txt") or str(data_dir))
    extra = [Path(l) for l in _lignes("dossiers_a_taguer.txt")]
    return upload_dir, extra


def _joignabilite(upload_dir, extra):
    """{racine -> bool joignable}. Un seul .exists() par racine, pas par fichier."""
    racines = [upload_dir] + list(extra)
    return {str(r): _existe(r) for r in racines}


def _existe(p):
    try:
        return Path(p).exists()
    except OSError:
        return False


def _racine_joignable(cle, chemin, upload_dir, extra, cache):
    """La racine dont depend cette cle est-elle joignable ? (evite les faux
    orphelins quand le NAS est deconnecte)."""
    if not Path(cle).is_absolute():
        return cache.get(str(upload_dir), _existe(upload_dir))
    for r in extra:
        try:
            chemin.relative_to(r)
            return cache.get(str(r), _existe(r))
        except ValueError:
            continue
    # Racine non configuree : on teste l'ancre (\\serveur\partage\ ou X:\).
    anc = Path(chemin.anchor) if chemin.anchor else None
    return _existe(anc) if anc else False


# ── Diagnostic (lecture seule) ──────────────────────────────────────────────

def ouvrir_ro():
    import sqlite3
    if not DB_PATH.exists():
        raise SystemExit(f"  Base introuvable : {DB_PATH}")
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def charger_noms(cx):
    """{cle -> set(prefixes)} depuis la table tags (kw_fr + kw_en)."""
    noms = {}
    try:
        for cle, v in cx.execute('SELECT k, v FROM tags'):
            try:
                e = json.loads(v)
            except ValueError:
                continue
            kw = (e.get('kw_fr') or []) + (e.get('kw_en') or [])
            h = noms_humains(kw)
            if h:
                noms[cle] = h
    except Exception:                                        # noqa: BLE001
        pass
    return noms


def analyser_table(cx, table, det_field, upload_dir, extra, noms,
                   filtre=None, bavard=True):
    cache = _joignabilite(upload_dir, extra)
    total = 0
    compte = {'present': 0, 'orphelin': 0, 'indetermine': 0}
    orph_nommes = 0
    orph_humain = 0
    echantillon = []
    for cle, v in cx.execute(f'SELECT k, v FROM {table}'):
        if filtre and filtre.lower() not in cle.lower():
            continue
        total += 1
        chemin = resoudre(cle, upload_dir)
        joignable = _racine_joignable(cle, chemin, upload_dir, extra, cache)
        st = statut(joignable, _existe(chemin) and chemin.is_file())
        compte[st] += 1
        if st == 'orphelin':
            nomme = cle in noms
            par_humain = False
            try:
                e = json.loads(v)
                items = e.get(det_field) or []
                par_humain = any(it.get('par_humain') for it in items)
            except ValueError:
                pass
            if nomme:
                orph_nommes += 1
            if par_humain:
                orph_humain += 1
            if len(echantillon) < 15:
                marque = []
                if nomme:
                    marque.append('/'.join(sorted(noms[cle])))
                if par_humain:
                    marque.append('par_humain')
                echantillon.append((cle, ', '.join(marque) or 'anonyme'))
        if bavard and total % 5000 == 0:
            print(f"    {table}: {total} examinees…", flush=True)
    return total, compte, orph_nommes, orph_humain, echantillon


def main():
    args = sys.argv[1:]
    filtre = None
    if '--filtre' in args:
        i = args.index('--filtre')
        filtre = args[i + 1] if i + 1 < len(args) else None
    tables = ['faces', 'animals']
    if '--table' in args:
        i = args.index('--table')
        choix = args[i + 1] if i + 1 < len(args) else 'tous'
        if choix in ('faces', 'animals'):
            tables = [choix]

    print("=" * 70)
    print("  DIAGNOSTIC DES ENTREES ORPHELINES (fichier disparu) — LECTURE SEULE")
    print("=" * 70)
    upload_dir, extra = config_racines()
    print(f"  Uploads : {upload_dir}")
    print(f"  Dossiers a taguer : {len(extra)}")
    if filtre:
        print(f"  Filtre : cles contenant « {filtre} »")
    print()

    cx = ouvrir_ro()
    noms = charger_noms(cx)
    print(f"  {len(noms)} photo(s) portant un nom humain (personne:/animal:)\n")

    champ = {'faces': 'faces', 'animals': 'animals'}
    total_orph = total_nom = 0
    for t in tables:
        total, compte, o_nom, o_hum, ech = analyser_table(
            cx, t, champ[t], upload_dir, extra, noms, filtre)
        total_orph += compte['orphelin']
        total_nom += o_nom
        print("-" * 70)
        print(f"  Table {t} : {total} entree(s)")
        print(f"    presentes    : {compte['present']}")
        print(f"    ORPHELINES   : {compte['orphelin']}"
              f"  (dont {o_nom} nommee(s), {o_hum} jugee(s) par un humain)")
        print(f"    indeterminees: {compte['indetermine']}"
              f"  (racine injoignable — NON comptees comme orphelines)")
        if ech:
            print("    Echantillon d'orphelines :")
            for cle, marque in ech:
                print(f"      [{marque:<18}] {cle[:70]}")
        print()

    cx.close()
    print("=" * 70)
    print(f"  TOTAL orphelines : {total_orph}  (dont {total_nom} nommee(s))")
    if compte.get('indetermine'):
        print("  ! Des entrees sont indeterminees : relance NAS branche pour un")
        print("    compte fiable avant tout nettoyage.")
    print("  LECTURE SEULE : rien n'a ete modifie. Le correctif (cascade de")
    print("  suppression preservant les fiches nommees) est l'etape suivante.")
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
