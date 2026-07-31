"""
Verification d'espece des detections d'animaux, par SigLIP 2.
──────────────────────────────────────────────────────────────────────────────

LE PROBLEME
    YOLO11 classe selon COCO, qui ne contient ni singe, ni renard, ni lama, ni
    peluche. Tout mammifere poilu tombe donc dans « cat » ou « dog ». D'ou les
    groupes de macaques presentes comme « 9 apparitions de ce chat ».

    Mesure sur le corpus : 15 % des 1 634 detections de chat sont sous 0,50 de
    confiance YOLO — c'est la que se logent ces erreurs.

LA CORRECTION
    SigLIP repond a « qu'est-ce que c'est ? » sur un vocabulaire ouvert, y
    compris singe, faune, peluche, statue. On relit les DECOUPES deja en cache
    dans animal_thumbs/ (aucun acces au NAS), et on ecrit dans chaque detection :

        sp_ia      code d'espece vu par SigLIP  (cat, dog, primate, objet...)
        sp_score   confiance
        sp_marge   ecart avec la 2e hypothese
        suspect    True si SigLIP contredit NETTEMENT YOLO

    Les detections « suspect » sont ecartees du regroupement et du nommage.
    RIEN N'EST SUPPRIME : le champ species d'origine est conserve, et les noms
    deja attribues par un humain ne sont jamais touches.

USAGE
    python verifier_especes.py                 # simulation + rapport
    python verifier_especes.py --appliquer     # ecrit sp_ia / suspect
    python verifier_especes.py --exporter 24   # echantillon pour relecture
"""

import base64
import hashlib
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

THUMB_DIR = SCRIPT_DIR / "animal_thumbs"
DB_PATH = SCRIPT_DIR / "photos.db"
EVAL_DIR = SCRIPT_DIR / "eval"
ESPECES_DIR = EVAL_DIR / "especes"

# Un desaccord ne compte que s'il est NET : sinon on laisse le benefice du
# doute a YOLO, qui a ete entraine pour la detection.
SEUIL_SUSPECT = 0.05          # score SigLIP minimal pour contredire
MARGE_SUSPECT = 0.010         # ecart minimal avec la 2e hypothese


def crop_path(cle, i, bbox):
    """Chemin de la decoupe en cache — meme calcul que server.py."""
    ck = hashlib.md5(f"a|{cle}|{i}|{bbox}".encode('utf-8', 'replace')).hexdigest()
    return THUMB_DIR / (ck + ".jpg")


def detections(cx, seulement_sans_verif=False):
    """[(cle, i, animal, chemin_decoupe)] pour les decoupes deja en cache."""
    out = []
    for cle, v in cx.execute('SELECT k, v FROM animals'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        for i, a in enumerate(e.get('animals') or []):
            # Un jugement HUMAIN prime toujours sur le modele : une detection
            # nommee, ecartee ou marquee inconnue a la main n'est jamais
            # reevaluee. Sans cette regle, un second passage effacerait le
            # travail de tri de l'utilisateur.
            if a.get('par_humain'):
                continue
            if seulement_sans_verif and a.get('sp_ia'):
                continue
            p = crop_path(cle, i, a.get('bbox', [0, 0, 0, 0]))
            if p.is_file():
                out.append((cle, i, a, p))
    return out


def ouvrir(lecture_seule=True):
    import sqlite3
    if not DB_PATH.exists():
        raise SystemExit(f"  Base introuvable : {DB_PATH}")
    if lecture_seule:
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cx = sqlite3.connect(str(DB_PATH), isolation_level=None, timeout=30.0)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.execute("PRAGMA busy_timeout=30000")
    return cx


def analyser(dets, bavard=True):
    import semantic as S
    resultats = {}
    t0 = time.time()
    lot = 64
    for debut in range(0, len(dets), lot):
        tranche = dets[debut:debut + lot]
        vus = S.verifier_especes([str(p) for _k, _i, _a, p in tranche])
        par_chemin = {c: (lib, code, sc, mg) for c, lib, code, sc, mg in vus}
        for cle, i, a, p in tranche:
            r = par_chemin.get(str(p))
            if r:
                resultats[(cle, i)] = r
        if bavard and debut:
            fait = min(debut + lot, len(dets))
            print(f"    {fait}/{len(dets)}  "
                  f"({(time.time()-t0)/fait*1000:.0f} ms/decoupe)", flush=True)
    return resultats


def rapport(dets, resultats):
    from collections import Counter
    import semantic as S
    croise = Counter()
    suspects = []
    for cle, i, a, p in dets:
        r = resultats.get((cle, i))
        if not r:
            continue
        lib, code, sc, mg = r
        yolo = a.get('species')
        croise[(yolo, code)] += 1
        if code != yolo and sc >= SEUIL_SUSPECT and mg >= MARGE_SUSPECT:
            suspects.append((cle, i, yolo, lib, code, sc, mg,
                             float(a.get('det_score') or 0), p))

    print("\n" + "=" * 70)
    print("  YOLO  ->  SigLIP   (les desaccords sont ce qui nous interesse)")
    print("=" * 70)
    for (yolo, code), n in croise.most_common(20):
        marque = "   " if yolo == code else " ! "
        print(f"  {marque}{str(yolo):<8} -> {code:<9} {n:>5}")

    print(f"\n  {len(suspects)} detection(s) suspecte(s) sur {len(resultats)} verifiees")
    nommables = sum(1 for _c, _i, y, _l, _co, _s, _m, _d, _p in suspects
                    if y in S.NOMMABLES)
    print(f"  dont {nommables} sur des especes nommables (chat/chien/cheval)")
    if suspects:
        print("\n  Echantillon :")
        for cle, i, yolo, lib, code, sc, mg, det, p in suspects[:12]:
            print(f"    {yolo:<6} -> {lib:<28} {sc:.3f} (marge {mg:.3f}, "
                  f"YOLO {det:.2f})  {Path(cle).name[:34]}")
    return suspects


def appliquer(dets, resultats):
    cx = ouvrir(lecture_seule=False)
    import semantic as S
    par_cle = {}
    for cle, i, a, p in dets:
        r = resultats.get((cle, i))
        if r:
            par_cle.setdefault(cle, []).append((i, r, a.get('species')))

    n_ecrites = n_suspects = 0
    cx.execute("BEGIN IMMEDIATE")
    try:
        for cle, maj in par_cle.items():
            ligne = cx.execute('SELECT v FROM animals WHERE k=?', (cle,)).fetchone()
            if not ligne:
                continue
            e = json.loads(ligne[0])
            animaux = e.get('animals') or []
            change = False
            for i, (lib, code, sc, mg), yolo in maj:
                if i >= len(animaux):
                    continue
                a = animaux[i]
                a['sp_ia'] = code
                a['sp_lib'] = lib
                a['sp_score'] = round(sc, 4)
                a['sp_marge'] = round(mg, 4)
                suspect = (code != yolo and sc >= SEUIL_SUSPECT
                           and mg >= MARGE_SUSPECT)
                if suspect:
                    a['suspect'] = True
                    n_suspects += 1
                else:
                    a.pop('suspect', None)
                change = True
            if change:
                cx.execute('UPDATE animals SET v=? WHERE k=?',
                           (json.dumps(e, ensure_ascii=False,
                                       separators=(',', ':')), cle))
                n_ecrites += 1
        cx.execute("COMMIT")
    except Exception:
        cx.execute("ROLLBACK")
        raise
    cx.close()
    print(f"\n  + {n_ecrites} photo(s) mises a jour, {n_suspects} detection(s)"
          " marquees suspectes")
    print("  Le champ species d'origine est CONSERVE ; aucun nom attribue")
    print("  par un humain n'a ete touche.")


def exporter(suspects, n=24):
    """Copie des decoupes suspectes pour relecture humaine (ou par Claude)."""
    import shutil
    ESPECES_DIR.mkdir(parents=True, exist_ok=True)
    for vieux in ESPECES_DIR.glob("*.jpg"):
        vieux.unlink()
    fiches = []
    for idx, (cle, i, yolo, lib, code, sc, mg, det, p) in enumerate(suspects[:n]):
        nom = f"{idx:03d}.jpg"
        shutil.copy2(p, ESPECES_DIR / nom)
        fiches.append({"fichier": nom, "cle": cle, "i": i, "yolo": yolo,
                       "siglip": lib, "code": code, "score": round(sc, 4),
                       "marge": round(mg, 4), "yolo_score": round(det, 3)})
    (EVAL_DIR / "especes.json").write_text(
        json.dumps({"suspects": fiches}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    print(f"\n  + {len(fiches)} decoupes dans {ESPECES_DIR}")
    print(f"  + {EVAL_DIR / 'especes.json'}")
    print("  Montre-les a Claude : il dira si les rejets sont justifies.")


def main():
    args = sys.argv[1:]
    print("=" * 70)
    print("  VERIFICATION D'ESPECE PAR SigLIP 2")
    print("=" * 70)
    cx = ouvrir()
    dets = detections(cx)
    cx.close()
    if not dets:
        print("  Aucune decoupe en cache dans animal_thumbs/.")
        print("  Ouvre la page Animaux une fois pour les generer.")
        return 1
    print(f"  {len(dets)} decoupes en cache a verifier "
          f"(aucun acces au NAS necessaire)\n")

    resultats = analyser(dets)
    suspects = rapport(dets, resultats)

    if '--exporter' in args:
        i = args.index('--exporter')
        n = int(args[i + 1]) if i + 1 < len(args) and args[i + 1].isdigit() else 24
        exporter(suspects, n)
    if '--appliquer' in args:
        appliquer(dets, resultats)
    else:
        print("\n  SIMULATION - rien n'a ete ecrit. Relancer avec --appliquer.")
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
