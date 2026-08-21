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

TROIS ORPHELINS, PAS UN (le troisieme trouve le 21/08)
    1. une detection dont le FICHIER a disparu (ci-dessous, un stat par cle) ;
    2. un VECTEUR dont la cle a quitte l'index (`analyser_vecteurs`) ;
    3. une DETECTION dont la cle a quitte l'index (`analyser_hors_index`).
    Le 3 manquait, et c'est lui qui a laisse 2 374 fiches de visages derriere la
    purge du 17/08 : elle n'avait traite que le 2. Aucun des deux autres
    controles ne pouvait le voir — l'un regarde le disque, l'autre la table
    `vectors`.

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
    .venv\\Scripts\\python.exe verifier_orphelins.py --sans-disque    # base contre base, 1 s
    .venv\\Scripts\\python.exe verifier_orphelins.py --sans-disque --simuler-purge

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


def basename_cle(cle):
    """Dernier composant d'une cle (nom de fichier), en minuscules. Sert a
    reconnaitre un DOUBLON malforme : deux cles qui pointent la meme photo mais
    dont une seule se resout (cas ARZOPA : « ads\\ARZOPA\\x.JPG » se resout,
    « ARZOPA/x.JPG » non — meme basename « x.jpg »)."""
    s = str(cle).replace('\\', '/').rstrip('/')
    return s.rsplit('/', 1)[-1].lower()


def est_fantome(cle, basenames_presents):
    """Un orphelin est une CLE FANTOME (doublon malforme, purge sans risque) si
    un fichier de MEME basename existe par ailleurs sous une cle qui, elle, se
    resout. Sinon c'est un vrai fichier DISPARU. `basenames_presents` = ensemble
    des basenames des cles presentes de la meme table."""
    return basename_cle(cle) in basenames_presents


def cles_fantomes_par_collision(keys, est_fichier, named=None):
    """Selection PURE et PEU COUTEUSE des cles fantomes a purger, sans stater
    tout le store. On groupe les cles par basename ; on ne considere que les
    basenames en COLLISION (>= 2 cles) — normalement rares. Dans un groupe qui
    contient a la fois des cles qui se resolvent (est_fichier vrai) ET des cles
    absentes, les absentes sont des DOUBLONS MALFORMES (la vraie donnee reste
    sous la cle presente) : on les purge, SAUF celles portant un nom humain
    (`named`). Cout : est_fichier n'est appele que sur les cles en collision.

    keys       : iterable de cles d'un store.
    est_fichier: callable cle -> bool (la cle resout-elle vers un fichier reel).
    named      : ensemble de cles a NE JAMAIS toucher (tag personne:/animal:).
    Renvoie la liste triee des cles fantomes."""
    named = named or set()
    groupes = {}
    for k in keys:
        groupes.setdefault(basename_cle(k), []).append(k)
    out = []
    for bn, ks in groupes.items():
        if len(ks) < 2:
            continue
        presents = [k for k in ks if est_fichier(k)]
        absents = [k for k in ks if not est_fichier(k)]
        if presents and absents:
            out += [k for k in absents if k not in named]
    return sorted(set(out))


# ── Vecteurs orphelins : la table `vectors` contre la table `tags` ──────────
# Un AUTRE orphelin que celui du reste de ce script. Ici la photo n'a pas
# forcement disparu du DISQUE : elle a disparu de l'INDEX (`tags`) sans que son
# vecteur semantique soit retire. Consequence visible depuis que la recherche
# est la porte d'entree (chantier 14a) : `/api/search` remonte la photo, mais
# `STORE.data.get(cle)` rend `{}` — resultat MUET, sans description ni
# mots-cles, avec une URL qui peut ne mener nulle part. Mesure du 15/08 :
# 2 374 vecteurs `photo` orphelins, soit 2,6 % des resultats sur huit requetes
# ordinaires — dont le dossier ARZOPA, celui-la meme qui a motive ce script.
#
# AUCUN acces disque : c'est une comparaison base contre base. Donc pas de
# « indetermine », pas de faux positif d'un NAS debranche — contrairement au
# reste du script, ce compte est fiable partout, y compris hors machine.

# Seul `photo` est comparable a `tags`. Les autres `kind` portent des cles
# COMPOSEES (« <cle_photo>faces0 », « <nom_de_personne>refs0 ») : les comparer
# telles quelles annonce 86 181 orphelins qui n'en sont pas. Piege verifie le
# 15/08 — un compte spectaculaire est d'abord une erreur de cle.
KINDS_CLE_PHOTO = ('photo',)


def orphelins_vecteurs(lignes, cles_tags, kinds=KINDS_CLE_PHOTO,
                       taille_echantillon=8):
    """(kind, cle) x cles de `tags` -> (par_kind, orphelins_par_kind, echantillon).

    `lignes` : iterable de couples (kind, cle) — typiquement
    `cx.execute('SELECT kind, k FROM vectors')`.
    `cles_tags` : ensemble des cles de la table `tags`.
    Ne compte que les `kinds` dont la cle EST une cle de photo.
    """
    par_kind, orphelins = {}, {}
    echantillon = []
    for kind, cle in lignes:
        par_kind[kind] = par_kind.get(kind, 0) + 1
        if kind not in kinds:
            continue
        if cle not in cles_tags:
            orphelins[kind] = orphelins.get(kind, 0) + 1
            if len(echantillon) < taille_echantillon:
                echantillon.append(cle)
    return par_kind, orphelins, echantillon


def analyser_vecteurs(cx, bavard=True):
    """Compte les vecteurs dont la cle n'existe plus dans `tags`."""
    cles_tags = {k for (k,) in cx.execute('SELECT k FROM tags')}
    par_kind, orphelins, ech = orphelins_vecteurs(
        cx.execute('SELECT kind, k FROM vectors'), cles_tags)
    if bavard:
        print("-" * 70)
        print(f"  Table vectors : {sum(par_kind.values())} ligne(s)")
        for kind in sorted(par_kind):
            marque = ''
            if kind not in KINDS_CLE_PHOTO:
                marque = '  (cle composee : non comparable a tags)'
            print(f"    {kind:10s} {par_kind[kind]:7d}{marque}")
        total = sum(orphelins.values())
        print(f"    ORPHELINS (cle absente de tags) : {total}"
              f"  sur {par_kind.get('photo', 0)} vecteurs photo")
        print("      -> resultats MUETS dans /api/search : ni description ni"
              " mots-cles.")
        if ech:
            print("    Echantillon :")
            for cle in ech:
                print(f"      {cle[:70]}")
        print()
    return par_kind, orphelins, ech


# ── Detections HORS INDEX : les tables faces/animals contre `tags` ─────────
# TROISIEME orphelin, trouve le 21/08 et invisible aux deux autres. Ici le
# fichier peut avoir disparu ou non : ce qui est certain, c'est que l'INDEX a
# oublie la cle alors que la detection de visages, elle, est restee. Ni le scan
# ni la purge par collision ne peuvent plus l'atteindre :
#   * `_sync_dir` calcule ses orphelins A PARTIR de `STORE` — une cle deja
#     absente de l'index lui est invisible ;
#   * `purge_cles_fantomes` exige un JUMEAU VIVANT de meme nom de fichier ;
#     quand les deux jumeaux sont morts, elle ne se declenche jamais.
# Mesure du 21/08 : 2 374 fiches de visages hors index, EXACTEMENT les 2 374
# cles dont la purge du 17/08 avait retire les vecteurs SigLIP. La purge avait
# traite un magasin sur deux, et rien ne le disait — parce que rien ne
# comparait ces tables-la a l'index. C'est ce trou que la fonction ci-dessous
# ferme. Base contre base : aucun acces disque, fiable NAS debranche.

def orphelins_hors_index(cles_store, cles_tags, decisions=None,
                         taille_echantillon=8):
    """(total, avec_decision_humaine, echantillon) — cles absentes de `tags`.

    `decisions` : ensemble des cles portant une decision humaine (rattachement,
    exclusion ou confirmation). Ce sont celles qu'une purge PERDRAIT : elles se
    comptent a part, toujours, parce que la regle 2 du projet interdit de les
    emporter sans les avoir vues.
    """
    decisions = decisions or set()
    total = humaines = 0
    echantillon = []
    for cle in cles_store:
        if cle in cles_tags:
            continue
        total += 1
        if cle in decisions:
            humaines += 1
        if len(echantillon) < taille_echantillon:
            echantillon.append(cle)
    return total, humaines, echantillon


def cles_hors_index_a_purger(cles_store, cles_tags, proteges,
                             est_fichier, est_cache):
    """Selection PURE des detections hors index que personne ne reprendra.

    Trois sorties, et la separation EST le garde-fou :
      * `a_purger`  : la cle a quitte l'index ET le fichier a disparu, ou son
        chemin est cache (`.corbeille-rangement`, `@eaDir`) — l'index ne la
        reprendra jamais, la detection ne peut plus rien produire ;
      * `proteges`  : la cle porte une DECISION HUMAINE. Jamais purgee, quoi
        qu'il arrive (regle 2 du projet). 120 cles le 21/08 ;
      * `en_attente`: la cle a quitte l'index mais son FICHIER existe toujours,
        sous un chemin normal. C'est le cas transitoire de `scan:modifies`, qui
        retire l'entree le temps d'un re-tagging : la purger ferait perdre des
        detections que le scan allait rendre. On la COMPTE au lieu de la
        toucher — un residu qui grossit est un signal.

    `est_fichier` / `est_cache` : callables cle -> bool, injectes par
    l'appelant (aucun acces disque ici, donc testable hors machine).
    """
    proteges_vus, a_purger, en_attente = [], [], []
    for cle in cles_store:
        if cle in cles_tags:
            continue
        if cle in proteges:
            proteges_vus.append(cle)
            continue
        if est_cache(cle) or not est_fichier(cle):
            a_purger.append(cle)
        else:
            en_attente.append(cle)
    return sorted(set(a_purger)), sorted(set(proteges_vus)), sorted(set(en_attente))


def decisions_par_cle(cx):
    """Cles portant une decision humaine, d'apres les fiches people/pets."""
    out = set()
    for table in ('people', 'pets'):
        try:
            lignes = cx.execute(f'SELECT v FROM {table}')
        except Exception:                                     # noqa: BLE001
            continue
        for (v,) in lignes:
            try:
                e = json.loads(v)
            except (ValueError, TypeError):
                continue
            if not isinstance(e, dict) or not e.get('name'):
                continue
            for kf in (e.get('faces') or []):
                if isinstance(kf, list) and len(kf) == 2:
                    out.add(kf[0])
            out.update(e.get('exclude') or [])
            out.update(e.get('confirmed') or [])
    return out


def simuler_purge(cx, upload_dir, tables=('faces', 'animals'), bavard=True):
    """DRY-RUN de `server.purge_detections_hors_index` : ce qui partirait.

    Meme selection pure que la prod, memes garde-fous, aucun retrait. Un stat
    par cle CANDIDATE seulement (pas par entree du store) : le cout est borne
    par la taille de l'anomalie. A lancer AVANT le redemarrage qui declenchera
    la vraie purge — deux chemins vers le meme nombre, ou l'ecart est le
    resultat."""
    cles_tags = {k for (k,) in cx.execute('SELECT k FROM tags')}
    proteges = decisions_par_cle(cx)

    def est_fichier(k):
        try:
            return resoudre(k, upload_dir).is_file()
        except OSError:
            return True                      # doute -> on ne purge pas

    def est_cache(k):
        try:
            return any(part.startswith(('.', '@', '#'))
                       for part in resoudre(k, upload_dir).parts)
        except OSError:
            return False

    total = {}
    if bavard:
        print("-" * 70)
        print("  SIMULATION de la purge des detections hors index (rien n'est")
        print("  retire ; c'est le serveur qui purge, au demarrage) :")
    for t in tables:
        try:
            cles = [k for (k,) in cx.execute(f'SELECT k FROM {t}')]
        except Exception:                                     # noqa: BLE001
            continue
        a_purger, prot, att = cles_hors_index_a_purger(
            cles, cles_tags, proteges, est_fichier, est_cache)
        total[t] = (a_purger, prot, att)
        if bavard:
            print(f"    {t:8s} purgerait {len(a_purger):5d}   "
                  f"protegees {len(prot):4d} (decision humaine)   "
                  f"en attente {len(att):4d} (fichier present, re-tagging)")
    if bavard:
        union = sorted({k for v in total.values() for k in v[0]})
        print(f"    UNION des cles a purger : {len(union)}")
        for k in union[:4]:
            print(f"        {k[:70]}")
        print()
    return total


def analyser_hors_index(cx, tables=('faces', 'animals'), bavard=True):
    """Compte, table par table, les detections dont la cle a quitte l'index."""
    cles_tags = {k for (k,) in cx.execute('SELECT k FROM tags')}
    decisions = decisions_par_cle(cx)
    resultats = {}
    if bavard:
        print("-" * 70)
        print("  Detections HORS INDEX (la cle a quitte `tags`) :")
    for t in tables:
        try:
            cles = [k for (k,) in cx.execute(f'SELECT k FROM {t}')]
        except Exception:                                     # noqa: BLE001
            continue
        total, humaines, ech = orphelins_hors_index(cles, cles_tags, decisions)
        resultats[t] = (total, humaines, ech)
        if bavard:
            print(f"    {t:8s} {total:6d} hors index sur {len(cles)}"
                  f"   dont {humaines} portant une DECISION HUMAINE")
            for cle in ech[:4]:
                print(f"        {cle[:70]}")
    if bavard:
        if any(h for _t, h, _e in resultats.values()):
            print("      -> NE PAS PURGER avant d'avoir traite ces decisions :")
            print("         mesure_visages_orphelins.py --base copie.db")
        print()
    return resultats


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
    # Basenames des cles PRESENTES : sert a distinguer une cle fantome (doublon
    # malforme dont la vraie photo est bien la, sous une autre cle) d'un vrai
    # fichier disparu. Passe unique : on collecte d'abord, on classe ensuite.
    basenames_presents = set()
    orphelins = []                       # (cle, nomme, par_humain)
    for cle, v in cx.execute(f'SELECT k, v FROM {table}'):
        if filtre and filtre.lower() not in cle.lower():
            continue
        total += 1
        chemin = resoudre(cle, upload_dir)
        joignable = _racine_joignable(cle, chemin, upload_dir, extra, cache)
        st = statut(joignable, _existe(chemin) and chemin.is_file())
        compte[st] += 1
        if st == 'present':
            basenames_presents.add(basename_cle(cle))
        elif st == 'orphelin':
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
            orphelins.append((cle, nomme, par_humain))
        if bavard and total % 5000 == 0:
            print(f"    {table}: {total} examinees…", flush=True)
    # Classement final orphelin : fantome (doublon d'une cle presente) vs disparu.
    orph_fantomes = 0
    for cle, nomme, par_humain in orphelins:
        fant = est_fantome(cle, basenames_presents)
        if fant:
            orph_fantomes += 1
        if len(echantillon) < 15:
            marque = []
            marque.append('FANTOME' if fant else 'disparu')
            if nomme:
                marque.append('/'.join(sorted(noms[cle])))
            if par_humain:
                marque.append('par_humain')
            echantillon.append((cle, ', '.join(marque)))
    return total, compte, orph_nommes, orph_humain, orph_fantomes, echantillon


def main():
    args = sys.argv[1:]
    filtre = None
    if '--filtre' in args:
        i = args.index('--filtre')
        filtre = args[i + 1] if i + 1 < len(args) else None
    sans_disque = '--sans-disque' in args
    simuler = '--simuler-purge' in args
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

    # Base contre base : instantane, aucun acces disque, fiable partout.
    # Passe en premier pour cette raison — le reste depend du NAS.
    if not filtre:
        analyser_vecteurs(cx)
        analyser_hors_index(cx)
        if simuler:
            simuler_purge(cx, upload_dir)
    if sans_disque:
        # Les deux controles ci-dessus comparent la base a elle-meme : ils sont
        # instantanes et fiables NAS debranche. La passe suivante, elle, fait un
        # stat par cle sur SMB — des dizaines de minutes sur 44 000 entrees.
        # `--sans-disque` s'arrete ici : c'est la forme lancable par un banc.
        cx.close()
        print("=" * 70)
        print("  --sans-disque : passe disque NON effectuee (aucun stat).")
        print("  LECTURE SEULE : rien n'a ete modifie.")
        print()
        return 0

    champ = {'faces': 'faces', 'animals': 'animals'}
    total_orph = total_nom = total_fant = 0
    for t in tables:
        total, compte, o_nom, o_hum, o_fant, ech = analyser_table(
            cx, t, champ[t], upload_dir, extra, noms, filtre)
        total_orph += compte['orphelin']
        total_nom += o_nom
        total_fant += o_fant
        print("-" * 70)
        print(f"  Table {t} : {total} entree(s)")
        print(f"    presentes    : {compte['present']}")
        print(f"    ORPHELINES   : {compte['orphelin']}"
              f"  (dont {o_nom} nommee(s), {o_hum} jugee(s) par un humain)")
        print(f"      dont FANTOMES : {o_fant}"
              f"  (doublon malforme d'une cle presente — cas ARZOPA, purge sans risque)")
        print(f"    indeterminees: {compte['indetermine']}"
              f"  (racine injoignable — NON comptees comme orphelines)")
        if ech:
            print("    Echantillon d'orphelines :")
            for cle, marque in ech:
                print(f"      [{marque:<32}] {cle[:70]}")
        print()

    cx.close()
    print("=" * 70)
    print(f"  TOTAL orphelines : {total_orph}  (dont {total_nom} nommee(s),"
          f" {total_fant} cle(s) fantome(s))")
    if compte.get('indetermine'):
        print("  ! Des entrees sont indeterminees : relance NAS branche pour un")
        print("    compte fiable avant tout nettoyage.")
    print("  LECTURE SEULE : rien n'a ete modifie. Le correctif (cascade de")
    print("  suppression preservant les fiches nommees) est l'etape suivante.")
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
