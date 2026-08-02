#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc d'eval : detecteurs de rebut pour le triage des images sans interet (point 21).

MESURER AVANT DE BATIR (discipline vision-eval). Ce banc ne construit PAS la vue
de triage ni la suppression : il mesure, sur un jeu FIGE etiquete a la main, si
les trois signaux gratuits distinguent un rebut d'une bonne photo, et a quel seuil.

Trois signaux (aucun modele lourd nouveau) :
  - NOM de fichier      (interet.indice_nom : Screenshot_, -WA####, facture...)
  - FLOU                (interet.score_flou : variance du Laplacien, CPU)
  - ZERO-SHOT SigLIP    (libelles rebut, reutilise l'encodeur de semantic.py)

Le banc ne fait que LIRE l'index et les fichiers ; il n'ecrit aucun tag, ne
supprime rien.

Usage (sur la machine reelle, NAS monte) :
  python eval_interet.py --echantillon 200   # tire l'echantillon FIGE sous _A TRIER
                                              # + genere la page d'etiquetage HTML
  #  ... Mike etiquette dans eval/interet_etiquetage.html, telecharge
  #      interet_labels.json et le depose dans eval/ ...
  python eval_interet.py --mesurer            # SigLIP + flou + nom, metriques + VRAM
  python eval_interet.py --mesurer --limit 40 # passe rapide

Sorties (dans eval/) :
  interet_v1.json            echantillon FIGE (liste de cles), reutilise tel quel
  interet_etiquetage.html    page d'etiquetage a la main (vignettes inline)
  interet_labels.json        etiquettes humaines {cle: garder|document|...}
  interet_results.json       scores bruts par photo + metriques + VRAM (re-analysable)
"""
import sys, os, io, json, time, base64, argparse, subprocess, threading
from pathlib import Path

import server as s          # sur : aucun thread ne demarre a l'import (garde __main__)
import interet as I
import rangement_annee as ra

EVAL_DIR = s.SCRIPT_DIR / "eval"
SAMPLE_FILE = EVAL_DIR / "interet_v1.json"
LABELS_FILE = EVAL_DIR / "interet_labels.json"
RESULTS_FILE = EVAL_DIR / "interet_results.json"
LABEL_HTML = EVAL_DIR / "interet_etiquetage.html"

N_DEFAUT = 200
IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tif', '.tiff',
           '.heic', '.heif'}
TOUTES_CLASSES = (I.GARDER,) + I.CATEGORIES


# ─────────────────────────── Echantillon figé ─────────────────────────────────

def _bucket(key):
    import hashlib
    h = hashlib.sha1(key.encode('utf-8', 'ignore')).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _resoudre(k):
    try:
        return s._resolve_key(k)
    except Exception:                     # noqa: BLE001
        return Path(k)


def cles_a_trier():
    """Cles image, non `failed`, dont le chemin resolu est sous « _A TRIER »."""
    out = []
    for k, e in s.STORE.data.items():
        if not isinstance(e, dict) or e.get('failed'):
            continue
        if Path(k).suffix.lower() not in IMG_EXT:
            continue
        p = _resoudre(k)
        if ra._atri_index(Path(p).parts) is None:
            continue
        out.append(k)
    return out


def construire_echantillon(n):
    if SAMPLE_FILE.exists():
        return json.loads(SAMPLE_FILE.read_text(encoding='utf-8'))
    cles = cles_a_trier()
    cles.sort(key=_bucket)
    ech = cles[:n]
    EVAL_DIR.mkdir(exist_ok=True)
    SAMPLE_FILE.write_text(json.dumps(ech, ensure_ascii=False, indent=1),
                           encoding='utf-8')
    return ech


# ─────────────────────────── Vignettes + page d'etiquetage ────────────────────

def _miniature_b64(chemin, cote=320):
    try:
        import cv2, numpy as np
        data = np.fromfile(str(chemin), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        f = cote / max(h, w)
        if f < 1:
            img = cv2.resize(img, (max(1, int(w * f)), max(1, int(h * f))),
                             interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 78])
        return base64.b64encode(buf).decode('ascii') if ok else None
    except Exception:                     # noqa: BLE001
        return None


_HTML_TETE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Etiquetage — triage des rebuts</title>
<style>
 :root{color-scheme:dark}
 body{background:#14110f;color:#e8e2d8;font:15px/1.5 system-ui,sans-serif;margin:0;padding:1rem}
 h1{font-size:1.1rem} .sub{color:#a99;margin:.2rem 0 1rem}
 .bar{position:sticky;top:0;background:#14110f;padding:.6rem 0;border-bottom:1px solid #3a322c;z-index:5}
 button{font:inherit;padding:.5rem .9rem;border-radius:.4rem;border:1px solid #5a4c3f;background:#26201b;color:#e8e2d8;cursor:pointer}
 button.dl{background:#c8892e;color:#14110f;border:0;font-weight:600}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:1rem;margin-top:1rem}
 .card{background:#1d1814;border:1px solid #3a322c;border-radius:.5rem;overflow:hidden}
 .card img{width:100%;height:200px;object-fit:contain;background:#000;display:block}
 .nom{font-size:.72rem;color:#a99;padding:.3rem .5rem;word-break:break-all}
 .opts{display:flex;flex-wrap:wrap;gap:.2rem;padding:.4rem}
 .opts label{font-size:.75rem;padding:.2rem .4rem;border-radius:.3rem;border:1px solid #4a3f34;cursor:pointer}
 .opts input{display:none}
 .opts input:checked + span{color:#14110f}
 .opts label:has(input:checked){background:#c8892e;border-color:#c8892e}
 .g:has(input:checked){background:#3a7a3a;border-color:#3a7a3a}
 .hint{outline:2px solid #6a5a3a}
 .count{color:#c8892e;font-weight:600}
</style></head><body>
<div class="bar">
 <h1>Etiquetage du triage — <span class="count" id="n">0</span> photos</h1>
 <div class="sub">Choisis pour chaque photo : <b>garder</b> (bonne photo) ou la
   categorie de rebut. Le liseré indique la suggestion de l'heuristique de nom
   (indice, pas verdict). Termine par « Telecharger » et depose le fichier dans
   <code>eval/interet_labels.json</code>.</div>
 <button class="dl" onclick="tele()">Telecharger interet_labels.json</button>
 <span id="reste" class="sub"></span>
</div>
<div class="grid" id="grid"></div>
<script>
const DATA = __DATA__;
const CLASSES = __CLASSES__;
const etat = {};
const grid = document.getElementById('grid');
document.getElementById('n').textContent = DATA.length;
for (const it of DATA){
  etat[it.key] = 'garder';
  const c = document.createElement('div'); c.className='card'+(it.hint?' hint':'');
  const img = it.thumb ? `<img src="data:image/jpeg;base64,${it.thumb}">`
                       : `<img alt="(vignette indisponible)">`;
  let opts = '';
  for (const cl of CLASSES){
    const g = cl==='garder' ? ' g' : '';
    const checked = cl==='garder' ? 'checked' : '';
    opts += `<label class="${g}"><input type="radio" name="r_${it.i}" value="${cl}" ${checked}
              onchange="pick('${it.key.replace(/'/g,"\\'")}','${cl}')"><span>${cl}</span></label>`;
  }
  const h = it.hint ? ` · indice: ${it.hint}` : '';
  c.innerHTML = img + `<div class="nom">${it.nom}${h}</div><div class="opts">${opts}</div>`;
  grid.appendChild(c);
}
function pick(k,v){ etat[k]=v; maj(); }
function maj(){
  let r=0; for(const k in etat) if(etat[k]!=='garder') r++;
  document.getElementById('reste').textContent = r+' marquees rebut';
}
function tele(){
  const blob = new Blob([JSON.stringify(etat,null,1)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='interet_labels.json'; a.click();
}
maj();
</script></body></html>
"""


def cmd_echantillon(n):
    print("=" * 70)
    print(f"  ECHANTILLON DE VALIDATION — {n} photos sous « _A TRIER »")
    print("=" * 70)
    ech = construire_echantillon(n)
    print(f"  {len(ech)} cles figees dans {SAMPLE_FILE.name}")
    print("  Generation des vignettes (lecture NAS)...")
    items, manquants = [], 0
    for i, k in enumerate(ech):
        p = _resoudre(k)
        thumb = _miniature_b64(p) if p.exists() else None
        if thumb is None:
            manquants += 1
        cat, motif = I.indice_nom(k)
        items.append({"i": i, "key": k, "nom": Path(k).name,
                      "thumb": thumb, "hint": motif or ""})
        if (i + 1) % 25 == 0:
            print(f"    {i+1}/{len(ech)}")
    html = (_HTML_TETE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__CLASSES__", json.dumps(list(TOUTES_CLASSES))))
    LABEL_HTML.write_text(html, encoding='utf-8')
    print(f"\n  Page d'etiquetage : {LABEL_HTML}")
    if manquants:
        print(f"  ! {manquants} vignettes indisponibles (fichier introuvable / NAS).")
    print("\n  Ouvre la page, etiquette, telecharge interet_labels.json,")
    print(f"  depose-le dans {EVAL_DIR}, puis lance :  python eval_interet.py --mesurer")
    return 0


# ─────────────────────────── VRAM ─────────────────────────────────────────────

def _vram_used_mb():
    try:
        out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.used',
             '--format=csv,noheader,nounits'], text=True, timeout=5)
        return max(int(x) for x in out.split() if x.strip())
    except Exception:                     # noqa: BLE001
        return 0


class _PicVram:
    def __init__(self):
        self.pic = 0
        self._on = False
        self._t = None

    def __enter__(self):
        self._on = True
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def _loop(self):
        while self._on:
            self.pic = max(self.pic, _vram_used_mb())
            time.sleep(0.2)

    def __exit__(self, *a):
        self._on = False
        if self._t:
            self._t.join(timeout=1)


# ─────────────────────────── Mesure ───────────────────────────────────────────

def _seuils(valeurs, k=21):
    vals = [v for v in valeurs if v is not None]
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return [lo]
    return [lo + (hi - lo) * j / (k - 1) for j in range(k)]


def cmd_mesurer(limit=None):
    import numpy as np
    if not SAMPLE_FILE.exists():
        print(f"  x {SAMPLE_FILE.name} absent — lance d'abord --echantillon N")
        return 1
    if not LABELS_FILE.exists():
        print(f"  x {LABELS_FILE.name} absent — etiquette via {LABEL_HTML.name}")
        return 1
    ech = json.loads(SAMPLE_FILE.read_text(encoding='utf-8'))
    labels = json.loads(LABELS_FILE.read_text(encoding='utf-8'))
    cles = [k for k in ech if k in labels]
    if limit:
        cles = cles[:limit]
    if not cles:
        print("  x aucune cle etiquetee en commun avec l'echantillon")
        return 1

    verite = {k: labels[k] for k in cles}
    rebut_vrai = {k: (verite[k] != I.GARDER) for k in cles}
    n_rebut = sum(rebut_vrai.values())
    print("=" * 70)
    print(f"  MESURE — {len(cles)} photos etiquetees "
          f"({n_rebut} rebut, {len(cles)-n_rebut} a garder)")
    print("=" * 70)
    repart = {c: sum(1 for k in cles if verite[k] == c) for c in TOUTES_CLASSES}
    print("  Repartition : " + ", ".join(f"{c}={repart[c]}" for c in TOUTES_CLASSES))

    # ── Signal NOM (gratuit, aucune lecture d'octet) ──
    nom_cat = {k: I.indice_nom(k)[0] for k in cles}

    # ── Signal FLOU (CPU) ──
    print("\n  Score de flou (variance du Laplacien)...")
    flou = {}
    t0 = time.perf_counter()
    for i, k in enumerate(cles):
        flou[k] = I.score_flou(_resoudre(k))
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(cles)}")
    dt_flou = time.perf_counter() - t0

    # ── Signal SigLIP zero-shot (GPU/CPU selon VRAM) ──
    print("\n  Zero-shot SigLIP sur les libelles rebut...")
    import semantic
    libs, cat_of = [], []
    for cat, lst in I.LIBELLES_SIGLIP.items():
        for lib in lst:
            libs.append(semantic.GABARIT.format(lib))
            cat_of.append(cat)
    cat_uniques = list(dict.fromkeys(cat_of))
    dev, libre = semantic._device_cible()
    print(f"    VRAM libre avant : {libre:.0f} Mo -> cible {dev}")
    sig = {k: {c: None for c in cat_uniques} for k in cles}
    dt_sig = 0.0
    pic = 0
    with _PicVram() as pv:
        M = semantic.encoder_textes(libs)            # (L, d)
        chemins = [_resoudre(k) for k in cles]
        # map chemin resolu -> cle (encoder_images renvoie (chemin, vecteur))
        par_chemin = {str(_resoudre(k)): k for k in cles}
        t0 = time.perf_counter()
        for chemin, v in semantic.encoder_images([p for p in chemins if p.exists()]):
            k = par_chemin.get(str(chemin))
            if k is None:
                continue
            sc = M @ np.asarray(v)
            for c in cat_uniques:
                idx = [j for j, cc in enumerate(cat_of) if cc == c]
                sig[k][c] = float(max(sc[j] for j in idx))
        dt_sig = time.perf_counter() - t0
        pic = pv.pic
    print(f"    pic VRAM pendant l'encodage : {pic} Mo")

    # ── Metriques ──
    res = {"n": len(cles), "n_rebut": n_rebut, "repartition": repart,
           "vram_pic_mb": pic, "vram_libre_avant_mb": round(libre),
           "temps": {"flou_s": round(dt_flou, 1), "siglip_s": round(dt_sig, 1),
                     "flou_ms_img": round(dt_flou / len(cles) * 1000, 1),
                     "siglip_ms_img": round(dt_sig / max(1, len(cles)) * 1000, 1)},
           "seuils_pipeline": {"FACE_GPU_MIN_FREE_MB": 1200,
                               "ANIMAL_GPU_MIN_FREE_MB": 1600,
                               "PET_GPU_MIN_FREE_MB": 1800},
           "signaux": {}, "detail": {}}

    verites_rebut = [rebut_vrai[k] for k in cles]

    # NOM : detecteur binaire (rebut si un motif matche)
    pred_nom = [nom_cat[k] is not None for k in cles]
    m_nom = I.metriques_binaire(verites_rebut, pred_nom)
    res["signaux"]["nom"] = m_nom
    print("\n" + "-" * 70)
    print("  SIGNAL NOM (gratuit)")
    print(f"    precision {m_nom['precision']:.0%}  rappel {m_nom['rappel']:.0%}"
          f"  F1 {m_nom['f1']:.0%}  |  faux positifs (bonnes photos) : {m_nom['fp']}")

    # FLOU : balayage (rebut si variance < seuil), vs la classe 'flou'
    ver_flou = [verite[k] == 'flou' for k in cles]
    sc_flou = [flou[k] for k in cles]
    bal_flou = I.balayage_seuil(sc_flou, ver_flou, _seuils(sc_flou), sens='inf')
    # cout FP mesure contre les BONNES photos (garder), pas contre les autres rebuts
    ver_garder = [verite[k] == I.GARDER for k in cles]
    for l in bal_flou:
        preds = [(flou[k] is not None and flou[k] < l['seuil']) for k in cles]
        l['fp_bonnes'] = sum(1 for p, g in zip(preds, ver_garder) if p and g)
    best_flou = I.meilleur_seuil(bal_flou, fp_max=max(1, len(cles) // 50))
    res["signaux"]["flou"] = {"balayage": bal_flou, "meilleur": best_flou,
                              "n_flou_vrai": sum(ver_flou)}
    print("\n  SIGNAL FLOU (variance du Laplacien, CPU)")
    print(f"    {sum(ver_flou)} photos etiquetees 'flou'.")
    if best_flou:
        print(f"    meilleur seuil {best_flou['seuil']:.0f} : precision "
              f"{best_flou['precision']:.0%} rappel {best_flou['rappel']:.0%}"
              f"  bonnes photos flouement signalees : {best_flou.get('fp_bonnes','?')}")
    else:
        print("    aucun seuil ne tient la borne de faux positifs — signal a NE PAS"
              " activer seul.")

    # SigLIP : balayage par categorie (rebut si score >= seuil)
    res["signaux"]["siglip"] = {}
    print("\n  SIGNAL SigLIP zero-shot (par categorie)")
    for c in cat_uniques:
        ver_c = [verite[k] == c for k in cles]
        if sum(ver_c) == 0:
            continue
        sc_c = [sig[k][c] for k in cles]
        bal = I.balayage_seuil(sc_c, ver_c, _seuils(sc_c), sens='sup')
        for l in bal:
            preds = [(sig[k][c] is not None and sig[k][c] >= l['seuil']) for k in cles]
            l['fp_bonnes'] = sum(1 for p, g in zip(preds, ver_garder) if p and g)
        best = I.meilleur_seuil(bal, fp_max=max(1, len(cles) // 50))
        res["signaux"]["siglip"][c] = {"balayage": bal, "meilleur": best,
                                       "n_vrai": sum(ver_c)}
        if best:
            print(f"    {c:9s} ({sum(ver_c)} vrais) seuil {best['seuil']:.3f} : "
                  f"prec {best['precision']:.0%} rap {best['rappel']:.0%} "
                  f"fp_bonnes {best.get('fp_bonnes','?')}")
        else:
            print(f"    {c:9s} ({sum(ver_c)} vrais) : aucun seuil sous la borne FP")

    # detail brut par photo (re-analysable sans relancer)
    res["detail"] = {k: {"verite": verite[k], "nom_cat": nom_cat[k],
                         "flou": flou[k], "siglip": sig[k]} for k in cles}
    EVAL_DIR.mkdir(exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(res, ensure_ascii=False, indent=1),
                            encoding='utf-8')
    print("\n" + "=" * 70)
    print(f"  Ecrit : {RESULTS_FILE.name}")
    print(f"  Temps : flou {dt_flou:.1f}s ({dt_flou/len(cles)*1000:.0f} ms/img), "
          f"SigLIP {dt_sig:.1f}s ({dt_sig/max(1,len(cles))*1000:.0f} ms/img)")
    print(f"  VRAM pic {pic} Mo (rejet si > seuil du pipeline le plus serre = 1200 Mo"
          " libre exige cote visages)")
    print("  -> Reporte la conclusion dans eval/DECISIONS.md (adopte/rejete + raison).")
    return 0


# ─────────────────────────── CLI ──────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--echantillon', type=int, metavar='N',
                    help="tire N photos sous _A TRIER + genere la page d'etiquetage")
    ap.add_argument('--mesurer', action='store_true',
                    help="mesure les 3 signaux contre interet_labels.json")
    ap.add_argument('--limit', type=int, default=None,
                    help="limite le nombre de photos mesurees (passe rapide)")
    a = ap.parse_args(argv)
    if a.echantillon:
        return cmd_echantillon(a.echantillon)
    if a.mesurer:
        return cmd_mesurer(a.limit)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
