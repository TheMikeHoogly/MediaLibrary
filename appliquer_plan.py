#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3 — APPLIQUE le plan de rangement (dedoublonnage), de facon REVERSIBLE.

Lit `docs/plan_rangement.json` (produit par plan_rangement.py) et, pour chaque
operation `quarantine`, retire une copie EXACTE en la deplacant vers
`.corbeille-rangement/` (JAMAIS de `rm`), en gardant l'index et les noms humains
coherents. Tout est annulable (`--undo`).

A LANCER SERVEUR ARRETE (ecrivain unique de photos.db), comme les scripts
`migrate_*`. Le NAS doit etre accessible (les fichiers a deplacer y sont).

Sequence par operation (ordre = securite) :
  1. RE-VERIFIE le contenu : sha256(src) et sha256(canonique) doivent tous deux
     valoir le sha256 du plan. Sinon on SAUTE l'op (le fichier a change depuis le
     recensement) — on ne retire jamais sur une preuve perimee.
  2. FUSIONNE d'abord : les noms humains de `fusion_noms` (presents sur la copie,
     absents de la canonique) sont ecrits dans la canonique — index ET XMP
     (exiftool si dispo). « Sans perte » = fusionner AVANT de retirer.
  3. DEPLACE src -> dst sous `.corbeille-rangement/<sha8>/`, ecrit un manifeste.
  4. RE-CLE l'index : `rekey` tags + faces/people/animals/pets + semantique
     (memes primitives que server.rekey_everywhere), pour que l'index suive le
     fichier a la corbeille sans perdre tags/detections/empreintes.
  5. Journalise l'op (undo).

Modes :
    python appliquer_plan.py                 # DRY-RUN : dit ce qu'il ferait
    python appliquer_plan.py --appliquer     # execute
    python appliquer_plan.py --appliquer --limite 5   # petit lot d'abord
    python appliquer_plan.py --undo docs/undo_rangement_XXXX.json
Options : --sans-verif (ne pas re-hasher, plus rapide, moins sur),
          --plan <chemin>, --db <chemin>.
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SUBJECT_TABLES = ('faces', 'people', 'animals', 'pets')


# ── index : mêmes primitives que server.rekey_everywhere ─────────────────────

def open_stores(db_path):
    from store_sqlite import SqliteStore
    from vectors import VectorStore
    stores = {t: SqliteStore(db_path, t)
              for t in ('tags', 'faces', 'people', 'animals', 'pets')}
    semantic = VectorStore(stores['tags'].cx)     # comme PHOTO_VEC(STORE.cx)
    return stores, semantic


def rekey_stores(old, new, stores, semantic):
    """Miroir de server.rekey_everywhere : tags decide, sujets rekey+save
    (transport auto des vecteurs), semantique rekey_prefix_all."""
    moved = stores['tags'].rekey(old, new)
    if not moved:
        return False
    for t in SUBJECT_TABLES:
        try:
            stores[t].rekey(old, new)
        except Exception as e:
            print(f"    ! rekey {t} {old} -> {new} : {e}")
    try:
        semantic.rekey_prefix_all(old, new)
    except Exception as e:
        print(f"    ! rekey semantique : {e}")
    stores['tags'].save()
    for t in SUBJECT_TABLES:
        stores[t].save()
    return True


def entry_names(stores, key):
    e = stores['tags'].data.get(key) or {}
    out = []
    for fld in ('kw_fr', 'kw_en'):
        for tag in e.get(fld) or []:
            if isinstance(tag, str) and (tag.startswith('personne:')
                                         or tag.startswith('animal:')):
                out.append(tag)
    return out


def merge_names(stores, canonical, noms):
    """Ajoute `noms` a la canonique dans l'INDEX (kw_fr) s'ils manquent. Renvoie
    la liste effectivement ajoutee. (Le XMP est ecrit a part, via exiftool.)"""
    if not noms:
        return []
    e = stores['tags'].data.get(canonical)
    if e is None:
        print(f"    ! canonique absente de l'index, fusion index sautee : {canonical}")
        return []
    kw = list(e.get('kw_fr') or [])
    ajoutes = [n for n in noms if n not in kw and n not in (e.get('kw_en') or [])]
    if ajoutes:
        e['kw_fr'] = kw + ajoutes
        stores['tags'].set(canonical, dict(e))       # marque + persistera au save
    return ajoutes


def xmp_merge(canonical_path, noms):
    """Ecrit les noms dans le XMP de la canonique via exiftool (best-effort).
    N'est appelee que si des noms doivent reellement etre fusionnes."""
    import shutil as _sh
    import subprocess
    if not noms or not _sh.which('exiftool'):
        if noms:
            print("    ! exiftool absent : fusion XMP a refaire "
                  "(reconcile_named_tags cote serveur).")
        return
    args = ['exiftool', '-overwrite_original', '-P']
    for n in noms:
        args.append(f'-XMP-dc:Subject+={n}')
    args.append(str(canonical_path))
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=60)
    except Exception as e:
        print(f"    ! exiftool a echoue ({e}) — fusion XMP a refaire cote serveur.")


# ── hash ─────────────────────────────────────────────────────────────────────

def sha256(path, buf=1 << 16, tries=3, pause=0.4):
    """sha256 d'un fichier, RESILIENT au hoquet SMB. Lit par blocs de 64 Ko —
    un `read` trop gros sur un partage SMB leve « [Errno 22] Invalid argument »,
    surtout sur les grosses videos — et reprend depuis le debut sur erreur d'I/O
    (meme esprit que server._read_bytes_retry). Leve la derniere OSError si les
    reprises echouent (l'appelant SAUTE alors l'operation, sans rien retirer)."""
    import time as _t
    last = None
    for attempt in range(tries):
        h = hashlib.sha256()
        try:
            with open(path, 'rb') as f:
                while True:
                    b = f.read(buf)
                    if not b:
                        break
                    h.update(b)
            return h.hexdigest()
        except OSError as e:
            last = e
            if attempt + 1 < tries:
                _t.sleep(pause * (attempt + 1))
    raise last


# ── application ──────────────────────────────────────────────────────────────

def win_to_local(p):
    """Chemin du plan (\\\\NAS\\...) -> Path utilisable. Sous Windows, les UNC
    fonctionnent tels quels. Ailleurs (test), on reste en Path brut."""
    return Path(p)


def apply_quarantine(op, stores, semantic, journal, verify=True, dry=True):
    src = op['src']
    dst = op['dst']
    canon = op['preuve']['canonique']
    sha = op['preuve']['sha256']
    p_src, p_dst, p_canon = win_to_local(src), win_to_local(dst), win_to_local(canon)

    if not p_src.exists():
        print(f"  [skip] source absente : {src}")
        return 'skip'
    if not p_canon.exists():
        print(f"  [skip] canonique absente : {canon}")
        return 'skip'
    if p_dst.exists():
        print(f"  [skip] destination deja prise : {dst}")
        return 'skip'

    noms = op.get('fusion_noms') or []

    # DRY-RUN : apercu seul, on ne LIT jamais le contenu (pas de hash SMB).
    if dry:
        extra = f"  + fusion noms {noms}" if noms else ""
        print(f"  [dry] quarantaine {src}\n        -> {dst}{extra}")
        return 'dry'

    # Re-verification du contenu AVANT tout retrait (sauf --sans-verif). Une
    # lecture SMB durablement fautive fait SAUTER l'op : on ne retire jamais un
    # fichier qu'on n'a pas pu confirmer identique a la canonique.
    if verify:
        try:
            if sha256(p_src) != sha:
                print(f"  [skip] sha256 de la source != plan (fichier change) : {src}")
                return 'skip'
            if sha256(p_canon) != sha:
                print(f"  [skip] sha256 de la canonique != plan : {canon}")
                return 'skip'
        except OSError as e:
            print(f"  [skip] lecture impossible (SMB ?), op non appliquee : {src} ({e})")
            return 'skip'

    # 2) fusion AVANT retrait
    if noms:
        ajoutes = merge_names(stores, canon, noms)
        if ajoutes:
            xmp_merge(p_canon, ajoutes)

    # 3) deplacement reversible
    p_dst.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'origine': src, 'canonique': canon, 'sha256': sha,
                'groupe': op['manifeste']['groupe'],
                'date_application': time.strftime('%Y-%m-%d %H:%M:%S')}
    (p_dst.parent / 'manifeste.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    shutil.move(str(p_src), str(p_dst))

    # 4) re-cle de l'index (le fichier vit maintenant a dst)
    rekeyed = False
    if stores is not None:
        rekeyed = rekey_stores(src, dst, stores, semantic)

    # 5) journal undo
    journal['operations'].append(
        {'src': src, 'dst': dst, 'canonique': canon,
         'noms_fusionnes': noms, 'index_rekey': rekeyed})
    print(f"  [ok]  {src}\n        -> {dst}"
          + (f"  (index re-cle)" if rekeyed else "  (hors index)"))
    return 'ok'


def undo(journal_path, stores, semantic, dry=True):
    j = json.loads(Path(journal_path).read_text(encoding='utf-8'))
    ops = list(reversed(j.get('operations', [])))
    print(f"Undo : {len(ops)} operation(s) a inverser depuis {journal_path}")
    n = 0
    for op in ops:
        src, dst = op['src'], op['dst']
        p_src, p_dst = win_to_local(src), win_to_local(dst)
        if not p_dst.exists():
            print(f"  [skip] a la corbeille, introuvable : {dst}")
            continue
        if p_src.exists():
            print(f"  [skip] l'origine existe deja : {src}")
            continue
        if dry:
            print(f"  [dry] restaure {dst} -> {src}")
            continue
        p_src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p_dst), str(p_src))
        if op.get('index_rekey') and stores is not None:
            rekey_stores(dst, src, stores, semantic)
        # nettoie le manifeste + dossier de groupe s'il est vide
        mani = p_dst.parent / 'manifeste.json'
        if mani.exists():
            try:
                mani.unlink()
            except OSError:
                pass
        try:
            p_dst.parent.rmdir()
        except OSError:
            pass
        print(f"  [ok]  {dst} -> {src}")
        n += 1
    # NB : les noms fusionnes dans la canonique NE sont PAS retires (fusion
    # additive et sans risque ; les defaire serait plus dangereux qu'utile).
    if not dry:
        print(f"Undo termine : {n} fichier(s) restaure(s). Noms fusionnes conserves.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--appliquer', action='store_true', help='executer (sinon dry-run)')
    ap.add_argument('--limite', type=int, default=0, help='n quarantaines max')
    ap.add_argument('--sans-verif', action='store_true', help='ne pas re-hasher')
    ap.add_argument('--undo', metavar='JOURNAL', help='inverser une application')
    ap.add_argument('--plan', default=str(RACINE / 'docs' / 'plan_rangement.json'))
    ap.add_argument('--db', default=str(RACINE / 'photos.db'))
    args = ap.parse_args()

    dry = not args.appliquer and not args.undo or (args.undo and not args.appliquer)
    # undo respecte aussi --appliquer pour executer
    if args.undo:
        dry = not args.appliquer
        stores = semantic = None
        if Path(args.db).exists():
            stores, semantic = open_stores(args.db)
        undo(args.undo, stores, semantic, dry=dry)
        return 0

    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    qu = [o for o in plan['operations'] if o['type'] == 'quarantine']
    if args.limite:
        qu = qu[:args.limite]
    dry = not args.appliquer
    print(f"{'DRY-RUN' if dry else 'APPLICATION'} : {len(qu)} quarantaine(s)"
          f"{' (re-hash actif)' if not args.sans_verif else ''}")

    stores = semantic = None
    if not dry and Path(args.db).exists():
        stores, semantic = open_stores(args.db)
    elif not dry:
        print("  ! photos.db absent : deplacement seul, index non re-cle.")

    journal = {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
               'plan': str(args.plan), 'operations': []}
    compte = {'ok': 0, 'dry': 0, 'skip': 0}
    for op in qu:
        r = apply_quarantine(op, stores, semantic, journal,
                             verify=not args.sans_verif, dry=dry)
        compte[r] = compte.get(r, 0) + 1

    if not dry and journal['operations']:
        jp = RACINE / 'docs' / f"undo_rangement_{time.strftime('%Y%m%d_%H%M%S')}.json"
        jp.write_text(json.dumps(journal, ensure_ascii=False, indent=1),
                      encoding='utf-8')
        print(f"\nJournal undo : {jp}")
    print(f"\nBilan : {compte}")
    if dry:
        print("(dry-run — rien deplace. Ajoute --appliquer, et --limite N pour un "
              "petit lot d'abord.)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
