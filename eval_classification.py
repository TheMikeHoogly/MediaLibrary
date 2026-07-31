"""
Banc d'essai : centroide unique contre prototypes multiples + contre-exemples.
──────────────────────────────────────────────────────────────────────────────

PROTOCOLE
    Verite terrain = les photos portant EXACTEMENT UN tag « personne: » et
    contenant EXACTEMENT UN visage. L'association visage -> personne y est
    donc sans ambiguite.

    Les references de chaque fiche sont RETIREES du jeu de test : sans cela,
    on evaluerait le modele sur ses propres exemples et tout paraitrait
    parfait. C'est la fuite de donnees la plus courante dans ce genre de
    mesure.

LIMITE A CONNAITRE
    Une partie de ces tags a ete posee par l'auto-attribution du systeme
    lui-meme. La verite n'est donc pas totalement independante : elle mesure
    la COHERENCE avec les decisions passees autant que la justesse absolue.
    Les fiches nommees a la main (celles ayant des exclusions) sont plus
    fiables — le rapport les isole.

USAGE
    python eval_classification.py [chemin_photos.db]
"""

import base64
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classifier as C  # noqa: E402

DB = Path(sys.argv[1] if len(sys.argv) > 1
          else Path(__file__).resolve().parent / "photos.db")

SEUIL = 0.40          # AUTO_ADD_SIM
MARGE = 0.10          # AUTO_ADD_MARGIN


def emb(s):
    import numpy as np
    v = np.frombuffer(base64.b64decode(s), dtype=np.float16).astype(np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


def _vecteurs(cx, kind):
    """Vecteurs sortis en table BLOB : {cle_vecteur: base64}.

    Depuis la migration des embeddings, les references et les visages ne sont
    plus inline dans le JSON. Un banc qui lit l'ancien format ne trouve plus
    rien et ne mesure donc plus rien — silencieusement.
    """
    try:
        return {k: base64.b64encode(v).decode()
                for k, v in cx.execute(
                    "SELECT k, v FROM vectors WHERE kind=?", (kind,))}
    except sqlite3.Error:
        return {}


def charger():
    cx = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    v_people = _vecteurs(cx, 'people')
    v_faces = _vecteurs(cx, 'faces')

    fiches = {}
    for k, v in cx.execute('SELECT k, v FROM people'):
        pe = json.loads(v)
        nom = (pe.get('name') or '').strip()
        refs = [r for r in (pe.get('refs') or [])
                if isinstance(r, str) and len(r) > 200]
        if not refs:                       # format actuel : vecteurs en BLOB
            i = 0
            while True:
                b = v_people.get("%s\x1frefs\x1f%d" % (k, i))
                if b is None:
                    break
                refs.append(b)
                i += 1
        if nom and refs:
            fiches[nom] = {"refs": refs,
                           "exclude": set(pe.get('exclude') or []),
                           "confirmed": set(pe.get('confirmed') or [])}

    tags = {}
    for k, v in cx.execute('SELECT k, v FROM tags'):
        p = [kw[9:] for kw in (json.loads(v).get('kw_fr') or [])
             if isinstance(kw, str) and kw.startswith('personne:')]
        if p:
            tags[k] = p

    visages = {}
    for k, v in cx.execute('SELECT k, v FROM faces'):
        lst = json.loads(v).get('faces') or []
        f = []
        for i, x in enumerate(lst):
            emb = x.get('emb') or v_faces.get("%s\x1ffaces\x1f%d" % (k, i))
            if emb:
                f.append(dict(x, emb=emb))
        if f:
            visages[k] = f
    cx.close()
    if not fiches or not visages:
        raise SystemExit("  Aucun vecteur trouve : le format de la base a-t-il "
                         "change ? (banc a adapter avant de conclure quoi que ce soit)")
    return fiches, tags, visages


def jeu_de_test(fiches, tags, visages, humain_seulement=True):
    """[(vecteur, nom_vrai, cle)] — sans fuite, et sans circularite.

    DEUX pieges, pas un seul :

    1. FUITE — un visage qui EST une reference : le modele le reconnaitrait
       par construction. On l'exclut.

    2. CIRCULARITE — la majorite des tags `personne:` ont ete poses par
       l'auto-attribution du systeme. Les prendre pour verite terrain revient
       a demander au modele s'il est d'accord avec lui-meme : on mesure 100 %
       et on n'apprend rien. Mesure sur ce corpus : 91 photos confirmees a la
       main sur 12 072 taguees, soit 0,8 %.

       Par defaut on ne retient donc que les photos CONFIRMEES par un humain
       (`confirmed`). Le jeu est petit, mais il mesure quelque chose.
    """
    refs_connues = set()
    confirmees = {}
    for nom, f in fiches.items():
        refs_connues.update(f["refs"])
        for k in f.get("confirmed") or ():
            confirmees[k] = nom
    jeu = []
    source = confirmees.items() if humain_seulement else (
        (k, n[0]) for k, n in tags.items() if len(n) == 1)
    for k, nom in source:
        if nom not in fiches:
            continue
        vis = visages.get(k) or []
        if len(vis) != 1:
            continue                      # une seule personne, un seul visage
        e = vis[0]['emb']
        if e in refs_connues:
            continue                      # fuite : c'est une reference
        jeu.append((emb(e), nom, k))
    return jeu


def construire(fiches, visages, avec_negatifs, multi):
    """Banque de modeles selon la variante evaluee."""
    import numpy as np
    modeles = []
    for nom, f in fiches.items():
        pos = [emb(r) for r in f["refs"]]
        neg = []
        if avec_negatifs:
            for k in f["exclude"]:
                for x in (visages.get(k) or []):
                    if x.get('emb'):
                        neg.append(emb(x['emb']))
        if multi:
            m = C.Modele(nom, pos, neg)
        else:
            # Variante actuelle : un centroide unique.
            m = C.Modele.__new__(C.Modele)
            m.nom = nom
            X = np.stack(pos)
            c = X.mean(axis=0)
            nrm = np.linalg.norm(c)
            m.P = (c / nrm if nrm else c).reshape(1, -1)
            m.N = None
            if neg:
                N = np.stack(neg)
                nn = np.linalg.norm(N, axis=1, keepdims=True)
                nn[nn == 0] = 1.0
                m.N = N / nn
        modeles.append(m)
    return C.Banque(modeles)


def mesurer(banque, jeu, marge_neg):
    t0 = time.time()
    bon = auto_bon = auto_total = 0
    for v, vrai, _k in jeu:
        r = banque.classer(v, marge_negative=marge_neg)
        if not r:
            continue
        pred, sc = r[0]
        marge = sc - (r[1][1] if len(r) > 1 else -1.0)
        if pred == vrai:
            bon += 1
        if sc >= SEUIL and marge >= MARGE:      # ce qui partirait en auto
            auto_total += 1
            if pred == vrai:
                auto_bon += 1
    return {"n": len(jeu), "top1": bon, "auto": auto_total, "auto_bon": auto_bon,
            "ms": (time.time() - t0) / max(len(jeu), 1) * 1000}


def ligne(nom, r):
    n = max(r["n"], 1)
    prec = 100 * r["auto_bon"] / max(r["auto"], 1)
    print(f"  {nom:<34} {100*r['top1']/n:5.1f} %   "
          f"{r['auto']:>5}   {prec:5.1f} %   {r['ms']:5.2f} ms")


def main():
    if not DB.exists():
        print(f"  Base introuvable : {DB}")
        return 1
    print("=" * 78)
    print("  BANC D'ESSAI DE CLASSIFICATION")
    print("=" * 78)
    fiches, tags, visages = charger()
    humain = '--tous' not in sys.argv
    jeu = jeu_de_test(fiches, tags, visages, humain_seulement=humain)
    n_excl = sum(1 for f in fiches.values() if f["exclude"])
    n_conf = sum(len(f["confirmed"]) for f in fiches.values())
    print(f"  {len(fiches)} fiches, {n_excl} avec exclusions, "
          f"{n_conf} photos confirmees a la main")
    if humain:
        print(f"  Jeu de test : {len(jeu)} visages CONFIRMES PAR UN HUMAIN.")
        print("  (--tous pour inclure les tags poses par l'auto-attribution,")
        print("   mais la mesure devient circulaire : voir jeu_de_test.)\n")
    else:
        print(f"  Jeu de test : {len(jeu)} visages, auto-attribution INCLUSE.")
        print("  ATTENTION : mesure circulaire, le resultat sera proche de 100 %.\n")
    if len(jeu) < 20:
        print("  Trop peu de visages confirmes pour conclure quoi que ce soit.")
        print("  Confirme des propositions dans l'interface pour etoffer le jeu.\n")
    print(f"  {'variante':<34} {'top-1':>7}   {'auto':>5}   {'prec.':>7}   "
          f"{'temps':>8}")
    print("  " + "-" * 74)

    variantes = [
        ("centroide unique (actuel)",        False, False),
        ("+ contre-exemples",                True,  False),
        ("prototypes multiples",             False, True),
        ("prototypes + contre-exemples",     True,  True),
    ]
    res = {}
    for nom, neg, multi in variantes:
        b = construire(fiches, visages, neg, multi)
        marge_neg = C.MARGE_NEGATIVE if neg else 99.0
        r = mesurer(b, jeu, -99.0 if not neg else marge_neg)
        res[nom] = r
        ligne(nom, r)

    print()
    base = res["centroide unique (actuel)"]
    best = max(res.items(), key=lambda kv: kv[1]["top1"])
    gain = best[1]["top1"] - base["top1"]
    print(f"  Meilleure variante : {best[0]}")
    print(f"  Gain top-1 : {gain:+d} visages sur {len(jeu)} "
          f"({100*gain/max(len(jeu),1):+.1f} points)")
    print()
    print("  « auto » = visages qui partiraient en attribution automatique")
    print("  (score >= 0.40 et marge >= 0.10) ; « prec. » = leur justesse.")
    print("  C'est cette colonne qui compte : une erreur automatique ecrit un")
    print("  tag dans les metadonnees d'un fichier.")
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
