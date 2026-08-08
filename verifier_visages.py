"""
Garde humain / animal des detections de visages, par SigLIP 2 (BANC DE MESURE).
──────────────────────────────────────────────────────────────────────────────

LE PROBLEME
    Le pipeline visages (InsightFace) n'a AUCUN garde humain/animal : il accepte
    toute detection de score >= FACE_DET_THRESHOLD (0.50, volontairement bas pour
    capter profils, petits visages, flous). Une face canine frontale passe donc :
    le chien Mutz (cocker) forme un groupe de 25 « visages » sur /people alors
    qu'il est deja, correctement, dans Animaux.

    Miroir exact du probleme resolu cote animaux par verifier_especes.py (YOLO/COCO
    classait tout mammifere poilu en cat/dog). Ici, InsightFace « voit » un visage
    la ou il n'y a pas d'humain.

CE QUE FAIT CE BANC (et ce qu'il NE fait PAS)
    Il relit les DECOUPES deja en cache dans face_thumbs/ (aucun acces au NAS) et
    demande a SigLIP, sur un vocabulaire ouvert : est-ce un visage HUMAIN, un
    ANIMAL, ou un OBJET (statue, peluche, reflet) ? Il en tire :

        vis_ia     code vu par SigLIP     (humain, animal, objet)
        vis_score  confiance
        vis_marge  ecart avec la 2e hypothese
        nonhumain  True si SigLIP contredit NETTEMENT « visage humain »

    DISCIPLINE vision-eval : ce script MESURE, il n'ACTIVE rien. Le serveur
    n'honore pas encore `nonhumain` (le cablage cote /people est une etape
    SEPAREE, a faire APRES la decision ecrite dans eval/DECISIONS.md). Tant que
    ce cablage n'existe pas, meme `--appliquer` est inoffensif : il ne fait
    qu'annoter, sans rien retirer du pipeline. Un jugement HUMAIN
    (par_humain / pas_visage / non_group) n'est JAMAIS reevalue.

    La metrique qui tranche n'est pas la justesse moyenne mais le COUT DES FAUX
    REJETS : combien de VRAIS visages humains seraient signales a tort (un vrai
    visage ecarte coute plus cher qu'une face de chien manquee). On mesure aussi
    le PIC VRAM : sur 4 Go partages avec Ollama resident, un encodeur qui frole
    le plafond est rejete (cf. eval/DECISIONS.md, triage a 3878 Mo).

USAGE (machine reelle, DANS le .venv — sinon open_clip/torch manquent)
    .venv\\Scripts\\python.exe verifier_visages.py                # simulation + rapport
    .venv\\Scripts\\python.exe verifier_visages.py --exporter 40  # echantillon a etiqueter
    .venv\\Scripts\\python.exe verifier_visages.py --appliquer     # ecrit vis_ia / nonhumain

    La logique pure (chemins, classement, seuils) est testee hors machine par
    test_verifier_visages.py (aucun torch requis).
"""

import hashlib
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

THUMB_DIR = SCRIPT_DIR / "face_thumbs"
DB_PATH = SCRIPT_DIR / "photos.db"
EVAL_DIR = SCRIPT_DIR / "eval"
VISAGES_DIR = EVAL_DIR / "visages"

# Un desaccord ne compte que s'il est NET : sinon on laisse le benefice du doute
# a InsightFace, entraine pour la detection de visages. Ces seuils sont un POINT
# DE DEPART ; la decision finale balaie plusieurs seuils SOUS une borne de faux
# rejets, une fois l'echantillon etiquete a la main (cf. eval/DECISIONS.md).
SEUIL_NONHUMAIN = 0.05        # score SigLIP minimal pour contredire « humain »
MARGE_NONHUMAIN = 0.010       # ecart minimal avec la 2e hypothese

# FACE_DET_THRESHOLD du serveur : on ne teste que les visages que le pipeline
# considere comme exploitables (donc reellement concernes par une garde amont).
FACE_DET_THRESHOLD = 0.50

# Vocabulaire de la garde. Plusieurs formulations par classe (le zero-shot est
# sensible au gabarit) ; toutes retombent sur trois CODES. Vocabulaire LOCAL :
# on ne touche pas vocabulaire_tags.txt.
VOCAB_VISAGES = [
    ("a photo of a human face",          "humain"),
    ("a close-up of a person's face",    "humain"),
    ("a human face",                     "humain"),
    ("a baby's face",                    "humain"),
    ("the face of a dog",                "animal"),
    ("the face of a cat",                "animal"),
    ("an animal's face",                 "animal"),
    ("a dog",                            "animal"),
    ("a cat",                            "animal"),
    ("a statue or sculpture",            "objet"),
    ("a toy or stuffed animal",          "objet"),
    ("a drawing or painting of a face",  "objet"),
    ("a pattern, texture or object",     "objet"),
]

CODE_ATTENDU = "humain"     # ce qu'un vrai visage nommable doit etre


def crop_path(cle, i, bbox):
    """Chemin de la decoupe de visage en cache — MEME calcul que server.py
    (_serve_facecrop) : md5 de « cle|i|bbox », SANS prefixe (les animaux, eux,
    prefixent par « a| »)."""
    ck = hashlib.md5(f"{cle}|{i}|{bbox}".encode('utf-8', 'replace')).hexdigest()
    return THUMB_DIR / (ck + ".jpg")


def classer(sims, codes, libelles):
    """Depuis un vecteur de similarites (1 par libelle), renvoie
    (libelle, code, score, marge). Logique PURE, testable sans torch."""
    ordre = sorted(range(len(sims)), key=lambda j: sims[j], reverse=True)
    j = ordre[0]
    marge = float(sims[j] - sims[ordre[1]]) if len(ordre) > 1 else 1.0
    return libelles[j], codes[j], float(sims[j]), marge


def est_nonhumain(code, score, marge,
                  seuil=SEUIL_NONHUMAIN, marge_min=MARGE_NONHUMAIN):
    """Vrai si SigLIP contredit NETTEMENT « visage humain ». Logique PURE."""
    return code != CODE_ATTENDU and score >= seuil and marge >= marge_min


def detections(cx):
    """[(cle, i, face, chemin_decoupe)] pour les visages exploitables dont la
    decoupe est deja en cache. On saute les jugements HUMAINS (jamais reevalues)
    et les visages sous le seuil de detection (hors pipeline nommable)."""
    out = []
    for cle, v in cx.execute('SELECT k, v FROM faces'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        for i, f in enumerate(e.get('faces') or []):
            if f.get('par_humain') or f.get('pas_visage') or f.get('non_group'):
                continue
            if float(f.get('det_score') or 0.0) < FACE_DET_THRESHOLD:
                continue
            p = crop_path(cle, i, f.get('bbox', [0, 0, 0, 0]))
            if p.is_file():
                out.append((cle, i, f, p))
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


def _vram_free_mb():
    try:
        import torch
        if not torch.cuda.is_available():
            return None, None
        libre, total = torch.cuda.mem_get_info()
        return libre / 1048576, total / 1048576
    except Exception:                                        # noqa: BLE001
        return None, None


def analyser(dets, bavard=True):
    """Encode les decoupes par SigLIP et renvoie
    (resultats {(cle,i):(lib,code,score,marge)}, mesure_vram).
    mesure_vram = (pic_utilise_mb, total_mb) ou (None, None) hors GPU."""
    import numpy as np
    import semantic as S
    libelles = [l for l, _ in VOCAB_VISAGES]
    codes = [c for _, c in VOCAB_VISAGES]
    M = S.encoder_textes(libelles)          # (n_lib, d), normalise

    resultats = {}
    min_free, total = None, None
    t0 = time.time()
    lot = 64
    for debut in range(0, len(dets), lot):
        tranche = dets[debut:debut + lot]
        chemins = [str(p) for _k, _i, _f, p in tranche]
        par_chemin = {}
        for chemin, vec in S.encoder_images(chemins):
            sims = (M @ vec).tolist()
            par_chemin[chemin] = classer(sims, codes, libelles)
        for cle, i, f, p in tranche:
            r = par_chemin.get(str(p))
            if r:
                resultats[(cle, i)] = r
        libre, tot = _vram_free_mb()
        if libre is not None:
            total = tot
            min_free = libre if min_free is None else min(min_free, libre)
        if bavard and debut:
            fait = min(debut + lot, len(dets))
            print(f"    {fait}/{len(dets)}  "
                  f"({(time.time()-t0)/fait*1000:.0f} ms/decoupe)", flush=True)
    pic = (total - min_free) if (min_free is not None and total is not None) else None
    return resultats, (pic, total)


def _croise_et_suspects(dets, resultats, seuil=SEUIL_NONHUMAIN,
                        marge_min=MARGE_NONHUMAIN):
    """Assemble le tableau croise (code -> compte) et la liste des suspects.
    Logique PURE (aucun torch) : c'est le coeur teste hors machine."""
    from collections import Counter
    croise = Counter()
    suspects = []
    for cle, i, f, p in dets:
        r = resultats.get((cle, i))
        if not r:
            continue
        lib, code, sc, mg = r
        croise[code] += 1
        if est_nonhumain(code, sc, mg, seuil, marge_min):
            suspects.append((cle, i, lib, code, sc, mg,
                             float(f.get('det_score') or 0.0), p))
    return croise, suspects


def rapport(dets, resultats):
    croise, suspects = _croise_et_suspects(dets, resultats)
    n = len(resultats)
    print("\n" + "=" * 70)
    print("  SigLIP sur les decoupes de visages : humain / animal / objet")
    print("=" * 70)
    for code, c in croise.most_common():
        marque = "   " if code == CODE_ATTENDU else " ! "
        pct = (100.0 * c / n) if n else 0.0
        print(f"  {marque}{code:<8} {c:>6}  ({pct:4.1f} %)")

    print(f"\n  {len(suspects)} visage(s) juge(s) NON HUMAIN sur {n} verifies"
          f" (seuil {SEUIL_NONHUMAIN}, marge {MARGE_NONHUMAIN})")
    print("  -> ce sont les detections que la garde ECARTERAIT du nommage.")

    # Balayage de seuil : montre l'agressivite. Le vrai taux de FAUX REJETS exige
    # l'etiquetage humain de l'echantillon exporte (cf. eval/DECISIONS.md).
    print("\n  Balayage de seuil (nb ecarte) — a confronter aux vrais visages :")
    for s in (0.03, 0.05, 0.08, 0.12, 0.18):
        _, susp = _croise_et_suspects(dets, resultats, seuil=s)
        print(f"    seuil {s:.2f} : {len(susp):>5} ecarte(s)")

    if suspects:
        print("\n  Echantillon d'ecartes (a verifier a l'oeil) :")
        for cle, i, lib, code, sc, mg, det, p in suspects[:12]:
            print(f"    {code:<7} {lib:<30} {sc:.3f} (marge {mg:.3f}, "
                  f"det {det:.2f})  {Path(cle).name[:32]}")
    return suspects


def exporter(suspects, n=40):
    """Copie des decoupes ecartees pour relecture humaine : Mike etiquette
    ensuite lesquelles sont de VRAIS visages humains (= faux rejets)."""
    import shutil
    VISAGES_DIR.mkdir(parents=True, exist_ok=True)
    for vieux in VISAGES_DIR.glob("*.jpg"):
        vieux.unlink()
    fiches = []
    for idx, (cle, i, lib, code, sc, mg, det, p) in enumerate(suspects[:n]):
        nom = f"{idx:03d}.jpg"
        shutil.copy2(p, VISAGES_DIR / nom)
        fiches.append({"fichier": nom, "cle": cle, "i": i, "siglip": lib,
                       "code": code, "score": round(sc, 4), "marge": round(mg, 4),
                       "det_score": round(det, 3),
                       "vrai_humain": None})     # a remplir : True/False a la main
    (EVAL_DIR / "visages.json").write_text(
        json.dumps({"ecartes": fiches}, ensure_ascii=False, indent=1),
        encoding='utf-8')
    print(f"\n  + {len(fiches)} decoupes dans {VISAGES_DIR}")
    print(f"  + {EVAL_DIR / 'visages.json'} (remplir 'vrai_humain': true/false)")
    print("  Un seul VRAI visage humain marque 'vrai_humain: true' est un FAUX")
    print("  REJET : c'est la mesure qui autorise ou non l'activation.")


def appliquer(dets, resultats):
    """Ecrit les annotations vis_ia/vis_score/vis_marge/nonhumain dans la table
    faces. NON DESTRUCTIF : n'ecrit pas pas_visage, ne retire rien du pipeline
    (le serveur n'honore pas encore `nonhumain`). Jugements humains preserves."""
    cx = ouvrir(lecture_seule=False)
    par_cle = {}
    for cle, i, f, p in dets:
        r = resultats.get((cle, i))
        if r:
            par_cle.setdefault(cle, []).append((i, r))
    n_ecrites = n_nonhumain = 0
    cx.execute("BEGIN IMMEDIATE")
    try:
        for cle, maj in par_cle.items():
            ligne = cx.execute('SELECT v FROM faces WHERE k=?', (cle,)).fetchone()
            if not ligne:
                continue
            e = json.loads(ligne[0])
            faces = e.get('faces') or []
            change = False
            for i, (lib, code, sc, mg) in maj:
                if i >= len(faces):
                    continue
                f = faces[i]
                if f.get('par_humain'):        # jamais reevalue
                    continue
                f['vis_ia'] = code
                f['vis_lib'] = lib
                f['vis_score'] = round(sc, 4)
                f['vis_marge'] = round(mg, 4)
                if est_nonhumain(code, sc, mg):
                    f['nonhumain'] = True
                    n_nonhumain += 1
                else:
                    f.pop('nonhumain', None)
                change = True
            if change:
                cx.execute('UPDATE faces SET v=? WHERE k=?',
                           (json.dumps(e, ensure_ascii=False,
                                       separators=(',', ':')), cle))
                n_ecrites += 1
        cx.execute("COMMIT")
    except Exception:
        cx.execute("ROLLBACK")
        raise
    cx.close()
    print(f"\n  + {n_ecrites} photo(s) mises a jour, {n_nonhumain} visage(s)"
          " annote(s) nonhumain")
    print("  Annotations SEULEMENT : rien n'est retire du pipeline visages tant")
    print("  que le serveur n'honore pas `nonhumain` (cablage = etape separee,")
    print("  APRES decision ecrite). Aucun nom humain touche.")


def main():
    args = sys.argv[1:]
    print("=" * 70)
    print("  GARDE HUMAIN / ANIMAL DES VISAGES — BANC SigLIP 2")
    print("=" * 70)
    cx = ouvrir()
    dets = detections(cx)
    cx.close()
    if not dets:
        print("  Aucune decoupe de visage en cache dans face_thumbs/.")
        print("  Ouvre la page Personnes une fois pour les generer.")
        return 1
    print(f"  {len(dets)} decoupes en cache a verifier "
          f"(aucun acces au NAS necessaire)\n")

    resultats, (pic, total) = analyser(dets)
    suspects = rapport(dets, resultats)

    if pic is not None:
        etat = "OK" if pic < 3600 else "! proche du plafond 4 Go"
        print(f"\n  Pic VRAM estime : {pic:.0f} Mo / {total:.0f} Mo  [{etat}]")
        print("  (rejeter si le pic frole 4 Go avec Ollama resident — invariant"
              " VRAM)")
    else:
        print("\n  VRAM : encodage sur CPU (pas de mesure GPU).")

    if '--exporter' in args:
        idx = args.index('--exporter')
        n = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 40
        exporter(suspects, n)
    if '--appliquer' in args:
        appliquer(dets, resultats)
    else:
        print("\n  SIMULATION - rien n'a ete ecrit. Relancer avec --appliquer.")
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
