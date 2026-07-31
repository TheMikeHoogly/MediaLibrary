"""
Banc d'essai : DINOv2 contre MegaDescriptor pour la re-identification animale.
──────────────────────────────────────────────────────────────────────────────

POURQUOI
    Le pipeline distingue Caline, Inti et Luna avec `vit_base_patch14_dinov2`,
    un encodeur GENERALISTE. MegaDescriptor est entraine specifiquement pour
    la re-identification d'individus animaux. L'audit le recommandait des le
    depart ; il n'avait jamais ete mesure.

PROTOCOLE — re-identification, pas classification
    Pour chaque animal nomme, ses detections sont coupees en deux par empreinte
    stable de la cle : moitie GALERIE (les references connues), moitie REQUETE
    (ce qu'on cherche a identifier). Aucun chevauchement, donc aucune fuite.

    Deux mesures :
      rang-1  la plus proche voisine dans la galerie est-elle le bon animal ?
      mAP     qualite du classement complet, pas seulement du premier resultat

    On rapporte aussi la MATRICE DE CONFUSION : une moyenne peut progresser
    sans rien regler si l'erreur porte toujours sur la meme paire d'animaux.

TOUT EST LOCAL
    Les decoupes sont deja en cache dans animal_thumbs/ : aucun acces au NAS,
    le banc tourne en quelques minutes.

USAGE
    python eval_animaux.py                      # DINOv2 seul (rien a telecharger)
    python eval_animaux.py --megadescriptor     # + MegaDescriptor-T-224
    python eval_animaux.py --modeles T-224,L-224
"""

import base64
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

DB = SCRIPT_DIR / "photos.db"
THUMBS = SCRIPT_DIR / "animal_thumbs"
MIN_PAR_ANIMAL = 6          # en deca, galerie et requete sont trop maigres


def _upload_dir():
    try:
        for l in (SCRIPT_DIR / "dossier_uploads.txt").read_text(
                encoding='utf-8').splitlines():
            l = l.strip()
            if l and not l.startswith('#'):
                return Path(l)
    except OSError:
        pass
    return SCRIPT_DIR


def resoudre(cle):
    p = Path(cle)
    return p if p.is_absolute() else _upload_dir() / cle


def crop_path(cle, i, bbox):
    ck = hashlib.md5(f"a|{cle}|{i}|{bbox}".encode('utf-8', 'replace')).hexdigest()
    return THUMBS / (ck + ".jpg")


def _cle_stable(cle, i):
    return hashlib.blake2b(f"{cle}|{i}".encode('utf-8', 'replace'),
                           digest_size=8).digest()


def charger():
    """{nom: [(cle, i, chemin_decoupe, embedding_dino)]} pour les animaux nommes."""
    if not DB.exists():
        raise SystemExit(f"  Base introuvable : {DB}")
    cx = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    noms = {}
    for k, v in cx.execute('SELECT k, v FROM tags'):
        for kw in (json.loads(v).get('kw_fr') or []):
            if isinstance(kw, str) and kw.startswith('animal:'):
                noms.setdefault(k, set()).add(kw[7:])

    par_animal = defaultdict(list)
    sans_crop = 0
    for k, v in cx.execute('SELECT k, v FROM animals'):
        etiquettes = noms.get(k)
        if not etiquettes or len(etiquettes) != 1:
            continue                       # ambigu : deux animaux sur la photo
        nom = next(iter(etiquettes))
        e = json.loads(v)
        for i, a in enumerate(e.get('animals') or []):
            if a.get('suspect') or a.get('inconnu'):
                continue
            p = crop_path(k, i, a.get('bbox', [0, 0, 0, 0]))
            if not p.is_file():
                sans_crop += 1
                continue
            par_animal[nom].append((k, i, p, a.get('emb'),
                                    a.get('bbox', [0, 0, 0, 0])))
    # les embeddings sont peut-etre sortis en table BLOB
    try:
        vect = {}
        for kk, v in cx.execute(
                "SELECT k, v FROM vectors WHERE kind='animals'"):
            vect[kk] = base64.b64encode(v).decode()
        for nom, lst in par_animal.items():
            for idx, t in enumerate(lst):
                if t[3] is None:
                    lst[idx] = (t[0], t[1], t[2],
                                vect.get(f"{t[0]}\x1fanimals\x1f{t[1]}"), t[4])
    except sqlite3.Error:
        pass
    cx.close()
    return par_animal, sans_crop


def separer(lst):
    """Galerie / requete, decoupe reproductible."""
    ordonne = sorted(lst, key=lambda t: _cle_stable(t[0], t[1]))
    moitie = len(ordonne) // 2
    return ordonne[:moitie], ordonne[moitie:]


def emb_dino(b64):
    import numpy as np
    if not b64:
        return None
    v = np.frombuffer(base64.b64decode(b64), dtype=np.float16).astype(np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def decouper(cle, i, bbox, cote, dossier, marge=0.0):
    """Refabrique une decoupe depuis l'original.

    GEOMETRIE : par defaut AUCUNE marge, comme le fait embed_cats_one_batch()
    dans server.py — c'est la geometrie du calcul d'empreinte. La vignette
    d'affichage, elle, ajoute 15 % : la confondre avec l'autre fausse toute
    comparaison.

    `cote` = 0 signifie PLEINE RESOLUTION, ce que recoit reellement le modele
    de production.
    """
    from PIL import Image, ImageOps
    cible = dossier / (hashlib.md5(
        ("%s|%s|%s|%s" % (cle, i, cote, marge)).encode('utf-8', 'replace')
    ).hexdigest() + ".jpg")
    if cible.is_file():
        return cible
    src = resoudre(cle)
    try:
        x1, y1, x2, y2 = bbox
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im).convert('RGB')
            w, h = im.size
            mw, mh = int((x2 - x1) * marge), int((y2 - y1) * marge)
            crop = im.crop((max(0, int(x1) - mw), max(0, int(y1) - mh),
                            min(w, int(x2) + mw), min(h, int(y2) + mh)))
            if crop.width < 8 or crop.height < 8:
                return None
            if cote:
                crop.thumbnail((cote, cote))
            crop.save(cible, 'JPEG', quality=90)
        return cible
    except Exception:                                        # noqa: BLE001
        return None


def encoder_dino(chemins, lot=16):
    """Encode avec le modele DE PRODUCTION, pour que la comparaison de
    resolutions ne fasse varier que la resolution."""
    import numpy as np
    import timm
    import torch
    from PIL import Image

    modele = timm.create_model('vit_base_patch14_dinov2.lvd142m',
                               pretrained=True, num_classes=0).eval()
    cfg = timm.data.resolve_data_config({}, model=modele)
    tf = timm.data.create_transform(**cfg)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    modele = modele.to(device)
    if device == 'cuda':
        modele = modele.half()
    out = {}
    t0 = time.time()
    for debut in range(0, len(chemins), lot):
        tenseurs, gardes = [], []
        for p in chemins[debut:debut + lot]:
            try:
                with Image.open(p) as im:
                    tenseurs.append(tf(im.convert('RGB')))
                gardes.append(p)
            except Exception:                                # noqa: BLE001
                continue
        if not tenseurs:
            continue
        with torch.no_grad():
            x = torch.stack(tenseurs).to(device)
            if device == 'cuda':
                x = x.half()
            v = modele(x).float()
            v = v / v.norm(dim=-1, keepdim=True)
        for p, vec in zip(gardes, v.cpu().numpy().astype(np.float32)):
            out[p] = vec
    print(f"    {len(out)} decoupes encodees en {time.time()-t0:.0f} s")
    return out


def encoder_megadescriptor(chemins, variante="T-224", lot=32):
    """Encode des decoupes avec MegaDescriptor (timm + hf-hub)."""
    import numpy as np
    import timm
    import torch
    from PIL import Image

    nom = f"hf-hub:BVRA/MegaDescriptor-{variante}"
    t0 = time.time()
    modele = timm.create_model(nom, pretrained=True, num_classes=0)
    modele.eval()
    cfg = timm.data.resolve_data_config({}, model=modele)
    tf = timm.data.create_transform(**cfg)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    modele = modele.to(device)
    if device == 'cuda':
        modele = modele.half()
    print(f"    modele charge en {time.time()-t0:.0f} s sur {device}"
          f"  (entree {cfg.get('input_size')})")

    out = {}
    t0 = time.time()
    for debut in range(0, len(chemins), lot):
        tranche = chemins[debut:debut + lot]
        tenseurs, gardes = [], []
        for p in tranche:
            try:
                with Image.open(p) as im:
                    tenseurs.append(tf(im.convert('RGB')))
                gardes.append(p)
            except Exception:                                # noqa: BLE001
                continue
        if not tenseurs:
            continue
        with torch.no_grad():
            x = torch.stack(tenseurs).to(device)
            if device == 'cuda':
                x = x.half()
            v = modele(x).float()
            v = v / v.norm(dim=-1, keepdim=True)
        for p, vec in zip(gardes, v.cpu().numpy().astype(np.float32)):
            out[p] = vec
    print(f"    {len(out)} decoupes encodees en {time.time()-t0:.0f} s "
          f"({(time.time()-t0)/max(len(out),1)*1000:.0f} ms/decoupe)")
    return out


def mesurer(galerie, requete):
    """galerie/requete : [(nom, vecteur)]. Renvoie rang-1, mAP, confusions."""
    import numpy as np
    if not galerie or not requete:
        return None
    G = np.stack([v for _n, v in galerie])
    noms_g = [n for n, _v in galerie]
    bon = 0
    aps = []
    confus = Counter()
    for vrai, q in requete:
        s = G @ q
        ordre = np.argsort(-s)
        pred = noms_g[int(ordre[0])]
        if pred == vrai:
            bon += 1
        else:
            confus[(vrai, pred)] += 1
        pertinents = np.array([noms_g[int(j)] == vrai for j in ordre])
        if pertinents.any():
            rangs = np.nonzero(pertinents)[0] + 1
            precisions = np.arange(1, len(rangs) + 1) / rangs
            aps.append(float(precisions.mean()))
    return {"rang1": bon / len(requete), "map": float(np.mean(aps)) if aps else 0.0,
            "n": len(requete), "confus": confus}


def rapport(titre, r):
    if not r:
        print(f"  {titre:<26} (pas assez de donnees)")
        return
    print(f"  {titre:<26} rang-1 {100*r['rang1']:5.1f} %    "
          f"mAP {100*r['map']:5.1f} %    ({r['n']} requetes)")


def main():
    args = sys.argv[1:]
    variantes = []
    if '--megadescriptor' in args:
        variantes = ["T-224"]
    if '--modeles' in args:
        i = args.index('--modeles')
        if i + 1 < len(args):
            variantes = [x.strip() for x in args[i + 1].split(',') if x.strip()]

    print("=" * 74)
    print("  RE-IDENTIFICATION ANIMALE — DINOv2 contre MegaDescriptor")
    print("=" * 74)
    par_animal, sans_crop = charger()
    par_animal = {n: l for n, l in par_animal.items() if len(l) >= MIN_PAR_ANIMAL}
    if not par_animal:
        print("  Pas assez de detections nommees avec decoupe en cache.")
        print("  Ouvre la page Animaux pour generer les vignettes.")
        return 1
    total = sum(len(l) for l in par_animal.values())
    print(f"  {len(par_animal)} animaux, {total} detections avec decoupe locale"
          + (f" ({sans_crop} sans vignette, ignorees)" if sans_crop else ""))
    for n, l in sorted(par_animal.items(), key=lambda kv: -len(kv[1])):
        print(f"    {n:<24} {len(l):>4}")
    print()

    galerie, requete = [], []
    for nom, lst in par_animal.items():
        g, q = separer(lst)
        galerie += [(nom, x) for x in g]
        requete += [(nom, x) for x in q]
    print(f"  galerie {len(galerie)} / requetes {len(requete)}"
          "   (decoupe reproductible, aucun chevauchement)\n")

    resultats = {}

    # ── DINOv2 : les empreintes existent deja
    gd = [(n, emb_dino(x[3])) for n, x in galerie if x[3]]
    qd = [(n, emb_dino(x[3])) for n, x in requete if x[3]]
    gd = [(n, v) for n, v in gd if v is not None]
    qd = [(n, v) for n, v in qd if v is not None]
    if gd and qd:
        dim = len(gd[0][1])
        gd = [(n, v) for n, v in gd if len(v) == dim]
        qd = [(n, v) for n, v in qd if len(v) == dim]
        resultats['DINOv2 (en place)'] = mesurer(gd, qd)
    rapport('DINOv2 (en place)', resultats.get('DINOv2 (en place)'))

    # ── Comparaison EQUITABLE : tous les modeles sur les MEMES decoupes
    # Le premier banc etait biaise : DINOv2 utilisait ses empreintes de
    # production, calculees sur la decoupe PLEINE RESOLUTION sans marge, tandis
    # que MegaDescriptor recevait les vignettes d'affichage de 256 px avec 15 %
    # de marge. On refabrique donc des decoupes identiques pour tout le monde.
    if '--equitable' in args or '--resolutions' in args:
        cotes = [0]
        if '--resolutions' in args:
            i = args.index('--resolutions')
            if i + 1 < len(args):
                cotes = [int(x) for x in args[i+1].split(',') if x.strip().isdigit()]
        cache = SCRIPT_DIR / "eval" / "crops_res"
        cache.mkdir(parents=True, exist_ok=True)
        print("\n  Refabrication des decoupes depuis les originaux")
        print("  (sans marge, comme le calcul d'empreinte du serveur).")
        for cote in cotes:
            lib = "pleine resolution" if not cote else f"{cote} px"
            print(f"\n  ── decoupes en {lib} ──")
            t0 = time.time()
            paires = []
            total = len(galerie) + len(requete)
            for idx, (n, x) in enumerate(galerie + requete, 1):
                p = decouper(x[0], x[1], x[4], cote, cache)
                if p:
                    paires.append((n, p, idx <= len(galerie)))
                if idx % 100 == 0:
                    print(f"    {idx}/{total} decoupes  ({time.time()-t0:.0f} s)",
                          flush=True)
            print(f"    {len(paires)}/{total} pretes en {time.time()-t0:.0f} s")
            if len(paires) < 40:
                print("    x trop peu de decoupes : NAS inaccessible ?")
                continue
            chemins = [p for _n, p, _g in paires]
            encodeurs = [("DINOv2", lambda c: encoder_dino(c))]
            for var in variantes:
                encodeurs.append((f"MegaDescriptor-{var}",
                                  lambda c, v=var: encoder_megadescriptor(c, v)))
            for nom_mod, fn in encodeurs:
                print(f"    {nom_mod} :")
                try:
                    vecs = fn(chemins)
                except Exception as e:                       # noqa: BLE001
                    print(f"      x {e}")
                    continue
                g = [(n, vecs[p]) for n, p, est_g in paires if est_g and p in vecs]
                q = [(n, vecs[p]) for n, p, est_g in paires if not est_g and p in vecs]
                resultats[f'{nom_mod} @ {lib}'] = mesurer(g, q)
        variantes = []          # deja traites ci-dessus, en conditions equitables

    # ── MegaDescriptor
    for var in variantes:
        print(f"\n  MegaDescriptor-{var} :")
        chemins = [x[2] for _n, x in galerie] + [x[2] for _n, x in requete]
        try:
            vecs = encoder_megadescriptor(chemins, var)
        except Exception as e:                               # noqa: BLE001
            print(f"    x chargement impossible : {e}")
            continue
        g = [(n, vecs[x[2]]) for n, x in galerie if x[2] in vecs]
        q = [(n, vecs[x[2]]) for n, x in requete if x[2] in vecs]
        resultats[f'MegaDescriptor-{var}'] = mesurer(g, q)

    print("\n" + "=" * 74)
    print("  RESULTATS")
    print("=" * 74)
    for nom, r in resultats.items():
        rapport(nom, r)

    print("\n  ── confusions au rang 1 (une moyenne peut cacher UNE paire) ──")
    for nom, r in resultats.items():
        if not r or not r["confus"]:
            print(f"    {nom:<26} aucune")
            continue
        detail = ", ".join(f"{a}→{b} ×{n}" for (a, b), n in r["confus"].most_common(4))
        print(f"    {nom:<26} {detail}")

    # Une mesure qui ne vit que dans un terminal n'est pas une mesure :
    # on ne peut ni la relire, ni la comparer six mois plus tard.
    RAPPORT = SCRIPT_DIR / "eval" / "animaux.json"
    RAPPORT.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text(json.dumps({
        "date": time.strftime('%Y-%m-%d %H:%M'),
        "animaux": {n: len(l) for n, l in par_animal.items()},
        "galerie": len(galerie), "requetes": len(requete),
        "resultats": {nom: {"rang1": r["rang1"], "map": r["map"], "n": r["n"],
                            "confusions": {f"{a}->{b}": c
                                           for (a, b), c in r["confus"].items()}}
                      for nom, r in resultats.items() if r},
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"\n  + resultats ecrits dans {RAPPORT}")

    if len(resultats) > 1:
        base = resultats.get('DINOv2 (en place)')
        meilleur = max((r for r in resultats.values() if r), key=lambda r: r["rang1"])
        nom_meilleur = [k for k, v in resultats.items() if v is meilleur][0]
        print()
        # Un ecart de quelques photos n'est PAS un resultat. Sur 267 requetes,
        # une photo vaut 0,37 point : annoncer un vainqueur a +0,4 point revient
        # a commenter du bruit. On exige un ecart d'au moins 5 photos.
        n = max(base["n"] if base else 1, 1)
        ecart_photos = round((meilleur["rang1"] - base["rang1"]) * n) if base else 0
        if base and meilleur is not base and ecart_photos >= 5:
            print(f"  {nom_meilleur} gagne {ecart_photos} photos "
                  f"({100*(meilleur['rang1']-base['rang1']):+.1f} points).")
            print("  Consigne le resultat dans eval/DECISIONS.md AVANT de migrer,")
            print("  puis bump ANIMAL_PIPELINE_VERSION : les noms sont preserves.")
        elif base and ecart_photos > 0:
            print(f"  Ecart maximal : {ecart_photos} photo(s) sur {n} — trop peu")
            print("  pour conclure. Ne rien changer.")
        else:
            print("  DINOv2 reste le meilleur : ne pas migrer.")
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
