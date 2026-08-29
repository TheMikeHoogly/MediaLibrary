#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APPLIQUE le plan de rangement par ANNEE, de facon REVERSIBLE.

Lit `docs/plan_rangement_annee.json` (produit par server.generer_plan_annee via
rangement_annee.py) et, pour chaque `move`, deplace le fichier de « _A TRIER »
vers son dossier annee `<base>/AAAA/` (ou `<base>/_SANS_DATE/` sans date fiable),
en gardant l'index et les noms humains coherents. Tout est annulable (`--undo`).

A LANCER SERVEUR ARRETE (ecrivain unique de photos.db), comme appliquer_plan.py
-- et depuis le 27/08 le script le PROUVE (`BEGIN IMMEDIATE`) au lieu de le
demander : l'en-tete ne l'avait jamais arrete personne.
et les scripts migrate_*. Le NAS doit etre accessible (les fichiers y sont).

Un `move` du plan porte : {key, src, dst, annee, new_key?}. `key`/`new_key`
sont les cles d'index (avant/apres) ; `new_key` est calcule cote serveur ou les
racines sont connues. S'il manque (vieux plan), on retombe sur str(dst) — correct
pour un « _A TRIER » sur le NAS (cle = chemin absolu).

Securite (ordre = garantie « aucune info perdue ») :
  1. src doit exister ; sinon on SAUTE.
  2. dst ne doit PAS exister : un deplacement ne RECOUVRE jamais un fichier deja
     en place (collision disque). Sinon on SAUTE — a l'humain de trancher (le
     dedoublonnage est un geste separe, deja applique).
  3. Deplacement src -> dst (mkdir du dossier annee au besoin).
  4. RE-CLE l'index : rekey tags + faces/people/animals/pets + semantique (memes
     primitives que server.rekey_everywhere, via appliquer_plan.rekey_stores),
     pour que tags/detections/empreintes suivent le fichier — aucun nom perdu.
     Et depuis le 29/08 le 7e magasin, `gps_places.json` (libelles de lieu).
  5. Journalise l'op (undo).

Le rangement ne FUSIONNE aucun nom (contrairement au dedoublonnage) : c'est un
simple deplacement 1:1, le fichier reste unique.

Modes :
    python appliquer_plan_annee.py                 # DRY-RUN : dit ce qu'il ferait
    python appliquer_plan_annee.py --appliquer     # execute
    python appliquer_plan_annee.py --appliquer --limite 20   # petit lot d'abord
    python appliquer_plan_annee.py --undo docs/undo_annee_XXXX.json --appliquer
Options : --plan <chemin>, --db <chemin>.
"""

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

# Reutilise les primitives d'index deja testees du dedoublonnage : rekey_stores
# est le miroir EXACT de server.rekey_everywhere (tags + sujets + semantique).
from appliquer_plan import open_stores, rekey_stores
import rangement_annee as _ra  # PROPRIETAIRE_RE : garde anti-plan-perime

RACINE = Path(__file__).resolve().parent
# Le 7e magasin : les libelles de geocodage, keyes par CHEMIN de photo. Ni
# `rekey_stores` ni le serveur hors-ligne ne le transportaient ; une photo
# rangee perdait son « Bremblens » et le redemandait au geocodeur.
GPS = RACINE / 'gps_places.json'
# Le journal du serveur : sa derniere banniere DEMARRAGE date l'index que le
# plan doit refleter (journal_serveur.BANNIERE).
JOURNAL = RACINE / '_journal_serveur.log'
BANNIERE_RE = re.compile(r'^===== DEMARRAGE (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')


def charger_gps(chemin=None):
    """Le dictionnaire des libelles, ou {} s'il n'existe pas / est illisible."""
    try:
        return json.loads(Path(chemin or GPS).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def recler_gps(gps, old, new):
    """Transporte le libelle de `old` vers `new`. Rend vrai s'il y en avait un."""
    if gps is None or old not in gps:
        return False
    gps[new] = gps.pop(old)
    return True


def ecrire_gps(gps, chemin=None):
    Path(chemin or GPS).write_text(json.dumps(gps, ensure_ascii=False, indent=1),
                                   encoding='utf-8')


def _new_key(op):
    """Cle d'index cible : le champ `new_key` du plan, ou str(dst) en repli
    (cas « _A TRIER » sur NAS ou la cle est le chemin absolu)."""
    nk = op.get('new_key')
    return nk if nk else str(Path(op['dst']))


def apply_move(op, stores, semantic, journal, dry=True, compte=None, gps=None):
    src, dst = op['src'], op['dst']
    old_key = op['key']
    new_key = _new_key(op)
    p_src, p_dst = Path(src), Path(dst)

    if not p_src.exists():
        print(f"  [skip] source absente : {src}")
        return 'skip'
    if p_dst.exists():
        print(f"  [skip] destination deja prise (collision) : {dst}")
        return 'skip'

    if dry:
        print(f"  [dry] {src}\n        -> {dst}")
        return 'dry'

    # 3) deplacement (le dossier annee est cree au besoin)
    try:
        p_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p_src), str(p_dst))
    except OSError as e:
        print(f"  [skip] deplacement impossible (SMB ?), op non appliquee : {src} ({e})")
        return 'skip'

    # 4) re-cle de l'index (le fichier vit maintenant a dst)
    rekeyed = False
    if stores is not None:
        try:
            rekeyed = rekey_stores(old_key, new_key, stores, semantic,
                                   compte=compte)
        except Exception as e:                                    # noqa: BLE001
            print(f"    ! re-cle index {old_key} -> {new_key} : {e}")
    if rekeyed and recler_gps(gps, old_key, new_key) and compte is not None:
        compte['gps'] = compte.get('gps', 0) + 1

    # 5) journal undo
    journal['operations'].append(
        {'src': src, 'dst': dst, 'old_key': old_key, 'new_key': new_key,
         'index_rekey': rekeyed})
    print(f"  [ok]  {src}\n        -> {dst}"
          + ("  (index re-cle)" if rekeyed else "  (hors index)"))
    return 'ok'


def undo(journal_path, stores, semantic, dry=True, compte=None, gps=None):
    j = json.loads(Path(journal_path).read_text(encoding='utf-8'))
    ops = list(reversed(j.get('operations', [])))
    print(f"Undo : {len(ops)} operation(s) a inverser depuis {journal_path}")
    n = 0
    for op in ops:
        src, dst = op['src'], op['dst']
        p_src, p_dst = Path(src), Path(dst)
        if not p_dst.exists():
            print(f"  [skip] cible introuvable : {dst}")
            continue
        if p_src.exists():
            print(f"  [skip] l'origine existe deja : {src}")
            continue
        if dry:
            print(f"  [dry] restaure {dst} -> {src}")
            continue
        try:
            p_src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p_dst), str(p_src))
        except OSError as e:
            print(f"  [skip] restauration impossible : {dst} ({e})")
            continue
        if op.get('index_rekey') and stores is not None:
            try:
                rekey_stores(op['new_key'], op['old_key'], stores, semantic,
                             compte=compte)
                recler_gps(gps, op['new_key'], op['old_key'])
            except Exception as e:                                # noqa: BLE001
                print(f"    ! re-cle d'annulation : {e}")
        # nettoie le dossier annee s'il est devenu vide
        try:
            p_dst.parent.rmdir()
        except OSError:
            pass
        print(f"  [ok]  {dst} -> {src}")
        n += 1
    if not dry:
        print(f"Undo termine : {n} fichier(s) restaure(s).")


def serveur_arrete(db):
    """(vrai/faux, ce qu'on a observe) — la MEME regle que `deplacer_dossiers`.

    L'en-tete de ce script disait << A LANCER SERVEUR ARRETE >> depuis le
    debut, et ne le verifiait pas. Le 27/08, le rangement par annee a failli
    partir sur une base que le serveur tenait ouverte : deux ecrivains sur
    SQLite, c'est l'invariant 4 du projet, et le DEMANDER dans un en-tete n'a
    jamais arrete personne. `BEGIN IMMEDIATE` prend le verrou d'ecriture ; si
    le serveur vit, il est deja pris."""
    import sqlite3
    try:
        cx = sqlite3.connect(str(db), timeout=1.0)
        try:
            cx.execute('BEGIN IMMEDIATE')
            cx.execute('ROLLBACK')
            return True, 'verrou d ecriture obtenu'
        finally:
            cx.close()
    except sqlite3.OperationalError as e:
        return False, 'base verrouillee (%s)' % str(e)[:60]
    except Exception as e:                                    # noqa: BLE001
        return False, 'base illisible (%s)' % str(e)[:60]


SERVEUR_URL = 'http://127.0.0.1:8080/api/serveur'


def serveur_repond(url=SERVEUR_URL, timeout=1.0):
    """Le serveur repond-il ? (vrai/faux, ce qu'on a observe).

    LE VERROU SEUL NE SUFFIT PAS, et c'est important : la base est en mode
    WAL. Un lecteur n'y bloque pas un ecrivain, et le serveur ne tient le
    verrou d'ecriture que PENDANT ses transactions -- quelques millisecondes
    a la fois. `BEGIN IMMEDIATE` peut donc l'obtenir alors que le serveur est
    bel et bien vivant, et rendre un feu vert qui ne prouve rien.

    Demander au serveur s'il est la, c'est une preuve d'une autre nature :
    elle ne depend pas de l'instant. Les deux ensemble valent mieux que
    chacune. Une absence de reponse n'est pas non plus une preuve d'arret
    (un serveur peut etre fige) -- d'ou les DEUX."""
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return (r.status == 200), 'le serveur repond sur %s' % url
    except Exception as e:                                    # noqa: BLE001
        return False, 'pas de reponse (%s)' % str(e)[:50]


def refus_d_ecriture(db, dry, forcer=False, url=SERVEUR_URL):
    """Le message de refus, ou None si on peut ecrire. Pur, testable."""
    if dry or forcer:
        return None
    vivant, vu_http = serveur_repond(url)
    if vivant:
        return (
            "  REFUS : le serveur REPOND (%s).\n"
            "  Il est l ECRIVAIN UNIQUE de photos.db (invariant 4). Deux\n"
            "  ecrivains, c est une base corrompue et des decisions perdues.\n"
            "  Arrete-le (fenetre << MediaLibrary - Serveur >>, ou ecris\n"
            "  << arret >> dans _commande_serveur.txt), relance ce script,\n"
            "  puis redemarre-le. --forcer passe outre, a tes risques."
            % vu_http)
    if not Path(db).exists():
        return None
    ok, vu = serveur_arrete(db)
    if ok:
        return None
    return (
        "  REFUS : le verrou d ecriture de photos.db est deja pris (%s).\n"
        "  Le serveur est l ECRIVAIN UNIQUE de cette base (invariant 4).\n"
        "  Deux ecrivains, c est une base corrompue et des decisions perdues.\n"
        "  Arrete le serveur (fenetre << MediaLibrary - Serveur >>, ou\n"
        "  ecris << arret >> dans _commande_serveur.txt), relance ce script,\n"
        "  puis redemarre-le. --forcer passe outre, a tes risques." % vu)


# Ancien nom, garde pour ne casser aucun appelant.
refus_du_verrou = refus_d_ecriture


def parent_du_dossier_annee(dst):
    """Nom du dossier qui CONTIENT le dossier <annee> d'un `dst`.

    `...\\Photos\\Photos Mike\\2005\\x.jpg` -> `Photos Mike`. Robuste aux deux
    separateurs : le plan porte des chemins Windows (`\\`), le test tourne sous
    Linux (`/`) ; `Path` ne coupe pas `\\` sous Linux, donc on normalise a la
    main plutot que de s'y fier."""
    parts = str(dst).replace('\\', '/').rstrip('/').split('/')
    return parts[-3] if len(parts) >= 3 else ''


def plan_vise_la_racine(moves):
    """Le premier `dst` qui range dans un `<annee>` a la RACINE (dont le parent
    n'est PAS un dossier proprietaire `Photos <Nom>`), ou None si le plan est
    sain. C'est le defaut du 28/08 : `cible()` visait `Photos\\<annee>` au lieu
    de `Photos\\Photos Mike\\<annee>`, et un plan PERIME (calcule avant le
    correctif) re-semait le desordre a chaque `bat 26`. On refuse de l'appliquer
    et on dit de le REGENERER, plutot que de deplacer 1 200 photos au mauvais
    endroit en silence."""
    for op in moves:
        parent = parent_du_dossier_annee(op.get('dst', ''))
        if parent and not _ra.PROPRIETAIRE_RE.match(parent):
            return op.get('dst', '')
    return None


def dernier_demarrage(journal=JOURNAL):
    """Instant (epoch, heure locale) de la DERNIERE banniere DEMARRAGE du
    journal du serveur, ou None si le journal manque ou n'en porte aucune."""
    quand = None
    try:
        with open(journal, 'r', encoding='utf-8', errors='replace') as f:
            for ligne in f:
                m = BANNIERE_RE.match(ligne)
                if m:
                    quand = m.group(1)
    except OSError:
        return None
    if not quand:
        return None
    return time.mktime(time.strptime(quand, '%Y-%m-%d %H:%M:%S'))


def plan_perime(plan_mtime, demarrage):
    """True si le plan a ete CALCULE AVANT le dernier demarrage du serveur :
    il decrit un index d'avant, pas celui qu'on vient d'arreter. Second etage
    du garde-fou du 29/08 : le serveur regenere le plan a chaque demarrage
    (server._run_plan_annee), et si ce recalcul a echoue, on le voit ICI au
    lieu de ranger sur un plan de la veille. Sans journal (None) : on ne sait
    pas, on laisse passer."""
    return demarrage is not None and plan_mtime < demarrage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true', help='executer (sinon dry-run)')
    ap.add_argument('--limite', type=int, default=0, help='n deplacements max')
    ap.add_argument('--undo', metavar='JOURNAL', help='inverser une application')
    ap.add_argument('--plan', default=str(RACINE / 'docs' / 'plan_rangement_annee.json'))
    ap.add_argument('--db', default=str(RACINE / 'photos.db'))
    ap.add_argument('--forcer', action='store_true',
                    help='ecrire meme si le verrou de photos.db est pris')
    args = ap.parse_args()

    if args.undo:
        dry = not args.appliquer
        refus = refus_d_ecriture(args.db, dry, args.forcer)
        if refus:
            print(refus)
            return 1
        stores = semantic = None
        if Path(args.db).exists():
            stores, semantic = open_stores(args.db)
        gps = charger_gps() if not dry else None
        undo(args.undo, stores, semantic, dry=dry, gps=gps)
        if gps is not None:
            ecrire_gps(gps)
        return 0

    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    moves = list(plan.get('moves', []))
    if args.limite:
        moves = moves[:args.limite]
    dry = not args.appliquer
    racine = plan_vise_la_racine(moves)
    if racine and not args.forcer:
        print("  REFUS : ce plan range a la RACINE de Photos, pas sous un")
        print("  dossier proprietaire. Exemple : " + str(racine))
        print("  C'est un plan PERIME (calcule avant le correctif de cible()).")
        print("  Regenere-le (Reglages -> \"Plan de rangement par annee\", ou")
        print("  POST /api/maint/plan-annee) AVANT de ranger. --forcer passe")
        print("  outre, a tes risques.")
        return 1
    if plan_perime(Path(args.plan).stat().st_mtime, dernier_demarrage()) \
            and not args.forcer:
        print("  REFUS : ce plan est PLUS VIEUX que le dernier demarrage du")
        print("  serveur (banniere DEMARRAGE de _journal_serveur.log) : il")
        print("  decrit un index d'avant. Le serveur le regenere au demarrage ;")
        print("  s'il ne l'a pas fait, lis son journal, puis Reglages ->")
        print("  \"Plan de rangement par annee\". --forcer passe outre.")
        return 1
    conflits = len(plan.get('conflits', []))
    print(f"{'DRY-RUN' if dry else 'APPLICATION'} : {len(moves)} deplacement(s)"
          + (f" — {conflits} conflit(s) de plan ignore(s)" if conflits else ""))

    refus = refus_d_ecriture(args.db, dry, args.forcer)
    if refus:
        print(refus)
        return 1

    stores = semantic = None
    if not dry and Path(args.db).exists():
        stores, semantic = open_stores(args.db)
    elif not dry:
        print("  ! photos.db absent : deplacement seul, index non re-cle.")

    journal = {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
               'plan': str(args.plan), 'operations': []}
    compte = {'ok': 0, 'dry': 0, 'skip': 0}
    gps = charger_gps() if not dry else None
    for op in moves:
        r = apply_move(op, stores, semantic, journal, dry=dry,
                       compte=compte, gps=gps)
        compte[r] = compte.get(r, 0) + 1
    if gps is not None and compte.get('gps'):
        ecrire_gps(gps)

    if not dry and journal['operations']:
        jp = RACINE / 'docs' / f"undo_annee_{time.strftime('%Y%m%d_%H%M%S')}.json"
        jp.write_text(json.dumps(journal, ensure_ascii=False, indent=1),
                      encoding='utf-8')
        print(f"\nJournal undo : {jp}")
    print(f"\nBilan : {compte}")
    # Les DECISIONS humaines re-clees, comptees a part : elles vivent DANS les
    # fiches personnes/animaux, la ou `store.rekey(chemin)` ne va pas. Zero
    # ici, sur un lot qui en portait, serait le defaut du 22/08 revenu.
    if compte.get('decisions'):
        print(f"  dont {compte['decisions']} decision(s) humaine(s) re-clee(s) "
              "dans les fiches personnes/animaux.")
    if dry:
        print("(dry-run — rien deplace. Ajoute --appliquer, et --limite N pour un "
              "petit lot d'abord.)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
