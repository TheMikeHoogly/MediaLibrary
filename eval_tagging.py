#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc d'éval : assertions vs pixels pour le tagging (voir
eval/PLAN_assertions_vs_pixels.md).

Compare trois façons de produire les tags/description d'une photo, à schéma
JSON identique :

  V0     image seule + PROMPT actuel     (référence = pipeline en place)
  V1     assertions seules, SANS image   (le LLM met en langage des faits)
  V2     assertions + image, IMPÉRATIF de noms   (historique, retiré de la prod)
  V2CTX  assertions + image, prompt de PRODUCTION verbatim (tagging_meta)

Banc 3b (docs/PROTOCOLE_3B_TAGGING.md) : c'est **V0 contre V2CTX**, sur les 150
photos de l'échantillon figé, notation à l'aveugle des 150 paires. Le 25-15 sur
40 du 12/08 donne p = 0,15 : pas de quoi engager 50 h de GPU.

Le modèle est FIGÉ (qwen3-vl:2b) pour cette passe : on compare des variantes,
pas des modèles. Le banc ne fait que LIRE la base ; il n'écrit aucun tag XMP.

Sorties (dans eval/) :
  tagging_v1.json      échantillon FIGÉ (clé -> catégorie), réutilisé tel quel
  tagging_results.json réponses + tags + temps par variante, + proxies + VRAM
  rating.html          notation humaine à l'aveugle (images inline)
  rating_map.json      correspondance A/B/C -> variante (pour dépouiller)

Usage :
  python eval_tagging.py --dry            # bâtit l'échantillon + montre 3 blocs
                                          # d'assertions, SANS appeler Ollama
  python eval_tagging.py                  # banc 3b : V0 vs V2CTX (Ollama requis)
  python eval_tagging.py --limit 20       # passe rapide sur 20 photos
  python eval_tagging.py --depouiller     # dépouille eval/notes.json (critère 3b)
  python eval_tagging.py --depouiller _v2sans   # dépouille une notation passée
"""
import sys, os, io, json, time, hashlib, argparse, threading, subprocess, random
from pathlib import Path
from datetime import datetime

import server as s   # sûr : aucun thread ne démarre à l'import (garde __main__)
import tagging_meta  # PROD : prompt et faits. Le banc ne les réécrit plus.

EVAL_DIR = s.SCRIPT_DIR / "eval"
SAMPLE_FILE = EVAL_DIR / "tagging_v1.json"
RESULTS_FILE = EVAL_DIR / "tagging_results.json"
RATING_HTML = EVAL_DIR / "rating.html"
RATING_MAP = EVAL_DIR / "rating_map.json"

N_RICHE, N_PAUVRE, N_PIEGE, N_INCERTAIN = 50, 50, 30, 20
# Nb de photos notées à l'aveugle. 40 était trop peu : le 25-15 du 12/08 donne
# p = 0,15 — un écart réel mais NON DÉMONTRÉ, sur lequel reposait une dépense de
# 50 h GPU. Il faut ~123 paires pour trancher une préférence de 62,5 % à 80 % de
# puissance (docs/PROTOCOLE_3B_TAGGING.md). 0 = toutes les photos éligibles.
RATING_SUBSET = 0
MODEL_FIXE = "qwen3-vl:2b"   # figé pour cette passe

# Variantes connues. V2CTX est le prompt de PRODUCTION (tagging_meta) : c'est
# lui qu'on départage de V0 (protocole 3b). V1/V2 restent pour l'historique.
VARIANTES = ('V0', 'V1', 'V2', 'V2CTX')

IMG_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.tif', '.tiff',
           '.heic', '.heif'}


# ─────────────────────────── Échantillon figé ───────────────────────────

def _bucket(key):
    """Empreinte stable de la clé -> [0,1). Même corpus, même échantillon."""
    h = hashlib.sha1(key.encode('utf-8', 'ignore')).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _categorie(k):
    e = s.STORE.data.get(k) or {}
    kw = [str(x).lower() for x in (e.get('kw_fr') or [])]
    a_noms = [t for t in kw if t.startswith('personne:') or t.startswith('animal:')]
    plain = [t for t in kw if not (t.startswith('personne:') or t.startswith('animal:'))]
    doc = any(w in plain for w in ('document', 'reçu', 'recu', 'capture',
                                   'screenshot', 'texte', 'ticket'))
    # visage faible = incertitude (au sens de _face_is_poor si dispo)
    incertain = False
    fe = s.FACE_STORE.data.get(k)
    if isinstance(fe, dict):
        for f in (fe.get('faces') or []):
            try:
                if s._face_is_poor(f):
                    incertain = True
                    break
            except Exception:
                pass
    if doc:
        return 'piege'
    if incertain and a_noms:
        return 'incertain'
    if a_noms:
        return 'riche'
    return 'pauvre'


def construire_echantillon():
    if SAMPLE_FILE.exists():
        return json.loads(SAMPLE_FILE.read_text(encoding='utf-8'))
    quotas = {'riche': N_RICHE, 'pauvre': N_PAUVRE,
              'piege': N_PIEGE, 'incertain': N_INCERTAIN}
    pris = {c: [] for c in quotas}
    # ordre déterministe par empreinte, puis remplissage des quotas
    cles = [k for k, e in s.STORE.data.items()
            if isinstance(e, dict) and not e.get('failed')
            and Path(k).suffix.lower() in IMG_EXT]
    cles.sort(key=_bucket)
    for k in cles:
        c = _categorie(k)
        if len(pris[c]) < quotas[c]:
            pris[c].append(k)
        if all(len(pris[c]) >= quotas[c] for c in quotas):
            break
    ech = {k: c for c, ks in pris.items() for k in ks}
    EVAL_DIR.mkdir(exist_ok=True)
    SAMPLE_FILE.write_text(json.dumps(ech, ensure_ascii=False, indent=1),
                           encoding='utf-8')
    return ech


# ──────────────── Knowledge Builder : on APPELLE la prod, on ne la copie pas ───
#
# Trois fois le banc a mesuré autre chose que la production parce qu'il
# recopiait sa logique (mesure du 14/08, docs/PROTOCOLE_3B_TAGGING.md) :
#   - `_fmt_date` faisait `strftime('%-d %B %Y')`, invalide sous Windows : les
#     150 photos de `tagging_results.json` ont reçu « Date : 1230807600.0
#     (EXIF) ». Le correctif vivait déjà en prod (`format_date_fr`).
#   - `_lieu` retombait sur la déduction par dossiers quand `lieux.txt` manquait
#     et affirmait « TRIER », « Calinous », « Visite » sous une provenance
#     inventée. 118 des 150 lieux étaient faux.
#   - `bloc_assertions` écrivait « (EXIF) » et « (chemin du dossier) » en dur,
#     quelle que soit la vraie source.
# Désormais tout passe par `server._assertions_pour` et `tagging_meta` : si la
# prod change, le banc change avec elle ou casse bruyamment.


def assertions(k):
    """Faits connus sur la photo — EXACTEMENT ceux que le worker de tagging
    assemblerait (`server._assertions_pour`), sources comprises. Aucun GPU,
    aucune lecture NAS : les mots-clés viennent de l'entrée d'index et la date
    de `taken` (celle qu'ExifTool a déjà écrite), comme en production."""
    e = s.STORE.data.get(k) or {}
    existing_kw = [str(x) for x in (e.get('kw_fr') or [])]
    a = s._assertions_pour(k, existing_kw, e.get('taken'))
    a['desc'] = e.get('desc')
    return a


def bloc_assertions(a):
    """Rendu texte des assertions — celui de la PROD, provenance vraie."""
    return tagging_meta.bloc_assertions(a)


# ─────────────────────────── Prompts par variante ───────────────────────────

REGLES_JSON = (
    'Retourne UNIQUEMENT du JSON strict, rien d autre :\n'
    '{"keywords_en": ["..."], "keywords_fr": ["..."], "description_fr": "..."}\n'
    'Regles : 6-10 mots-cles par langue, minuscules, 1-2 mots chacun ; '
    'espaces entre les mots, jamais de soulignes ; keywords_fr en vrai '
    'francais ; description_fr = une phrase courte en francais. '
    'Ne transcris jamais un texte, prix, recu ou panneau visible ; '
    'pour un document/recu/capture, utilise des mots generiques '
    '("document", "recu", "capture").'
)


def prompt_v1(a):
    return ('Des modeles specialises ont etabli les faits ci-dessous sur une '
            'photo (tu ne vois PAS l image).\n'
            'N invente aucun fait absent de cette liste.\n\n'
            + bloc_assertions(a) + '\n\n' + REGLES_JSON)


def prompt_v2ctx(a):
    """Prompt de PRODUCTION, verbatim (`tagging_meta.prompt_tagging`) : assertions
    en contexte, SANS impératif de noms. C'est la variante à départager de V0 —
    celle notée le 12/08 n'a jamais été écrite dans un fichier de résultats, donc
    n'était pas reproductible."""
    return tagging_meta.prompt_tagging(a)


def prompt_v2(a):
    # HISTORIQUE (adopte le 31/07, remplace par v2ctx le 12/08) : garde le bloc
    # IMPERATIF, que la prod a retire. Conserve pour comparaison, pas pour decider.
    # v2 : le premier essai ignorait les noms injectes (3 % d ancrage) car le
    # prompt ne les reclamait jamais. On EXIGE desormais que chaque nom/espece
    # asserte apparaisse dans la sortie -- sinon on ne teste pas l hypothese.
    noms = list(a.get('persons') or []) + list(a.get('animals') or [])
    exig = ''
    if noms:
        exig = ('IMPERATIF sur l identite : les personnes et animaux nommes '
                'ci-dessus sont identifies de facon certaine par reconnaissance. '
                'Tu DOIS employer chaque nom exact (' + ', '.join(noms) + ') '
                'dans description_fr a la place de "un homme", "une femme", '
                '"un chat" etc., ET ajouter chaque nom tel quel dans '
                'keywords_fr. N emploie ces noms que pour les sujets asserted.\n')
    elif a.get('species'):
        exig = ('IMPERATIF : ajoute l espece asserted ('
                + ', '.join(a['species']) + ') dans keywords_fr.\n')
    return ('Analyse cette photo. Des modeles specialises ont deja etabli les '
            'faits ci-dessous : traite-les comme la verite (noms, especes, '
            'lieu, date) et complete avec ce que tu VOIS en plus.\n\n'
            + bloc_assertions(a) + '\n\n' + exig + REGLES_JSON)


# ─────────────────────────────── Ollama ───────────────────────────────

def ollama_call(prompt, b64=None, model=MODEL_FIXE, timeout=600):
    import urllib.request, urllib.error
    payload = {
        "model": model, "prompt": prompt, "stream": False, "format": "json",
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 256,
                    "num_ctx": 4096, "repeat_penalty": 1.05},
        "keep_alive": "30m",
    }
    if b64:
        payload["images"] = [b64]
    req = urllib.request.Request(
        s.OLLAMA_URL + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    dt = time.time() - t0
    resp = (out.get("response") or out.get("thinking") or "").strip()
    return resp, dt


def _malforme(resp):
    try:
        json.loads(resp)
        return False
    except Exception:
        return True


def _tags_dict(resp):
    """parse_tags() renvoie un tuple (kw_fr, kw_en, desc) et lève TagError si
    rien n'est exploitable. Le banc veut toujours un dict au schéma commun
    (keywords_fr/keywords_en/description_fr), consommé par proxies() et
    generer_rating()."""
    try:
        kw_fr, kw_en, desc = s.parse_tags(resp)
    except Exception:
        return {}
    return {'keywords_fr': kw_fr, 'keywords_en': kw_en, 'description_fr': desc}


def _thumb_b64(path, side):
    from PIL import Image, ImageOps
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((side, side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
    return __import__('base64').b64encode(buf.getvalue()).decode()


# ─────────────────────────── VRAM (best-effort) ───────────────────────────

class VramSampler:
    def __init__(self):
        self.peak = 0
        self._stop = threading.Event()
        self._th = None

    def _run(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5)
                mb = int(out.stdout.strip().splitlines()[0])
                self.peak = max(self.peak, mb)
            except Exception:
                pass
            self._stop.wait(1.0)

    def __enter__(self):
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()
        return self

    def __exit__(self, *a):
        self._stop.set()


# ─────────────────────────── Proxies automatiques ───────────────────────────

def _jaccard(x, y):
    x, y = set(x), set(y)
    return len(x & y) / len(x | y) if (x or y) else 1.0


def proxies(results):
    """Vitesse, taux de JSON malformé, cohérence intra-scène (dossier+jour)."""
    out = {}
    for v in VARIANTES:
        temps = [r[v]['dt'] for r in results if r.get(v)]
        malf = [r[v]['malforme'] for r in results if r.get(v)]
        out[v] = {
            's_par_photo': round(sum(temps) / len(temps), 2) if temps else None,
            'malforme_pct': round(100 * sum(malf) / len(malf), 1) if malf else None,
        }
    # cohérence : grouper par (dossier, jour), mesurer Jaccard moyen des kw_fr
    groupes = {}
    for r in results:
        k = r['key']
        e = s.STORE.data.get(k) or {}
        jour = (r['assert'].get('date') or '?')
        gid = (str(Path(k).parent), jour)
        groupes.setdefault(gid, []).append(r)
    for v in VARIANTES:
        js = []
        for g in groupes.values():
            if len(g) < 2:
                continue
            kws = [r[v]['tags'].get('keywords_fr', []) for r in g if r.get(v)]
            for i in range(len(kws)):
                for j in range(i + 1, len(kws)):
                    js.append(_jaccard(kws[i], kws[j]))
        out[v]['coherence'] = round(sum(js) / len(js), 3) if js else None
    return out


# ─────────────────────────── Page de notation ───────────────────────────

def generer_rating(results, rating_html=RATING_HTML, rating_map=RATING_MAP):
    # « pauvre » (contexte = date seule) EST notée : c'est la strate qui dit si le
    # gain vient des faits ou du prompt. L'exclure revenait a ne mesurer que la
    # moitie riche, puis a extrapoler a 42 000 photos dont 35 % sont pauvres.
    sub = [r for r in results
           if r['cat'] in ('riche', 'pauvre', 'piege', 'incertain')]
    random.Random(42).shuffle(sub)
    if RATING_SUBSET:
        sub = sub[:RATING_SUBSET]
    # Variantes présentes dans TOUTES les cartes notées. Une notation à l'aveugle
    # A/B/C n'a de sens qu'à partir de 2 variantes — un comparatif de modèles en
    # V0 seul ne génère pas de page (on compare alors entre fichiers de modèles).
    present = [v for v in VARIANTES if sub and all(r.get(v) for r in sub)]
    if len(present) < 2:
        print(f"  (notation ignoree : {len(present)} variante(s) — comparer entre "
              f"fichiers de modeles)")
        return
    lettres_all = ['A', 'B', 'C', 'D']
    rows, mapping = [], {}
    for idx, r in enumerate(sub):
        variantes = [(v, r[v]) for v in present]
        random.Random(1000 + idx).shuffle(variantes)
        lettres = lettres_all[:len(variantes)]
        mapping[str(idx)] = {L: v for L, (v, _d) in zip(lettres, variantes)}
        # Traçabilité du dépouillement : quelle photo, quelle strate. Préfixées
        # « _ » pour ne jamais être confondues avec une lettre notée.
        mapping[str(idx)]['_key'] = r['key']
        mapping[str(idx)]['_cat'] = r['cat']
        try:
            img = _thumb_b64(s._resolve_key(r['key']), 520)
            imgtag = f'<img src="data:image/jpeg;base64,{img}">'
        except Exception:
            imgtag = '<div class="noimg">image indisponible</div>'
        blocs = ''
        for L, (v, _d) in zip(lettres, variantes):
            desc = (r[v]['tags'].get('description_fr') or '(vide)')
            kws = ', '.join(r[v]['tags'].get('keywords_fr', [])[:10])
            blocs += (f'<div class=opt><label><input type=radio '
                      f'name="best{idx}" value="{L}"> <b>{L}</b></label> '
                      f'<label class=hl><input type=checkbox '
                      f'name="hl{idx}_{L}"> hallucination</label>'
                      f'<div class=d>{desc}</div>'
                      f'<div class=k>{kws}</div></div>')
        rows.append(f'<div class=card><div class=n>#{idx+1} '
                    f'<span class=cat>{r["cat"]}</span></div>{imgtag}{blocs}</div>')
    html = RATING_TMPL.replace('__CARDS__', '\n'.join(rows))
    rating_html.write_text(html, encoding='utf-8')
    rating_map.write_text(json.dumps(mapping, ensure_ascii=False, indent=1),
                          encoding='utf-8')


RATING_TMPL = """<!doctype html><html lang=fr><meta charset=utf-8>
<title>Notation a l aveugle - tagging</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:820px;margin:auto;padding:16px;
   background:#111;color:#eee}
 .card{border:1px solid #333;border-radius:10px;padding:14px;margin:18px 0;background:#181818}
 .n{font-weight:700;margin-bottom:8px}.cat{color:#888;font-weight:400;font-size:.85em}
 img{max-width:100%;border-radius:8px;display:block;margin:6px 0}
 .noimg{padding:40px;text-align:center;color:#777;border:1px dashed #444}
 .opt{border-top:1px solid #2a2a2a;padding:8px 0}
 .opt label{cursor:pointer}.hl{margin-left:14px;color:#e8a}
 .d{margin:4px 0}.k{color:#8ab;font-size:.9em}
 button{position:sticky;bottom:10px;font-size:1.1em;padding:12px 20px;
   border-radius:8px;border:0;background:#3a6;color:#fff;cursor:pointer}
 .intro{color:#aaa}
</style>
<h1>Notation a l aveugle</h1>
<p class=intro>Pour chaque photo : coche la <b>meilleure</b> description (A/B/C),
et coche "hallucination" pour toute variante qui invente ou se trompe.
A la fin, clique pour telecharger tes notes, puis renvoie le fichier.</p>
__CARDS__
<button onclick="dl()">Telecharger mes notes (notes.json)</button>
<script>
function dl(){
 var out={};
 document.querySelectorAll('.card').forEach(function(c,i){
  var b=c.querySelector('input[name="best'+i+'"]:checked');
  var hl=[];['A','B','C'].forEach(function(L){
    var x=c.querySelector('input[name="hl'+i+'_'+L+'"]');if(x&&x.checked)hl.push(L);});
  out[i]={best:b?b.value:null,halluc:hl};
 });
 var blob=new Blob([JSON.stringify(out,null,1)],{type:'application/json'});
 var a=document.createElement('a');a.href=URL.createObjectURL(blob);
 a.download='notes.json';a.click();
}
</script></html>"""


# ─────────────────────────────── Main ───────────────────────────────

def _slug(modele):
    return ''.join(c if c.isalnum() else '_' for c in modele).strip('_')


def _paths(modele):
    """Chemins de sortie propres au modèle : le modèle par défaut garde les noms
    historiques ; tout autre modèle est suffixé pour ne pas écraser un run
    (comparatif de modèles → un jeu de fichiers par modèle)."""
    if modele == MODEL_FIXE:
        return RESULTS_FILE, RATING_HTML, RATING_MAP
    suf = '__' + _slug(modele)
    return (EVAL_DIR / f'tagging_results{suf}.json',
            EVAL_DIR / f'rating{suf}.html',
            EVAL_DIR / f'rating_map{suf}.json')


def finaliser(results, vram_peak, modele=MODEL_FIXE, paths=None):
    """Écrit les résultats bruts, puis proxies et page de notation (sous garde).
    Le brut est sauvé AVANT tout post-traitement : la passe Ollama est le coût
    majeur, on ne la reperd jamais sur un bug de proxies/notation."""
    results_file, rating_html, rating_map = paths or (RESULTS_FILE, RATING_HTML, RATING_MAP)
    report = {'n': len(results), 'model': modele,
              'vram_peak_mb': vram_peak, 'proxies': None, 'results': results}
    results_file.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                            encoding='utf-8')
    print(f"Résultats bruts sauvés : {results_file.name}")

    pr = None
    try:
        pr = proxies(results)
        report['proxies'] = pr
        results_file.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                encoding='utf-8')
    except Exception as e:
        print(f"  ! proxies() a échoué ({e}) — résultats bruts conservés")
    try:
        generer_rating(results, rating_html, rating_map)
    except Exception as e:
        print(f"  ! génération de rating.html a échoué ({e})")

    if pr:
        print(f"\n===== PROXIES (auto) — modele {modele} =====")
        for v in VARIANTES:
            p = pr[v]
            if p.get('s_par_photo') is None:
                continue
            print(f"  {v} : {p['s_par_photo']} s/photo | JSON malforme "
                  f"{p['malforme_pct']}% | coherence {p['coherence']}")
    print(f"  VRAM pic : {vram_peak} Mo")
    print(f"\nÉcrit : {results_file.name}")
    if rating_html.exists():
        print(f"Ouvre {rating_html.name}, note a l aveugle, renvoie notes.json.")


def _img_b64_retry(key, tries=3, pause=0.6):
    """Lit et encode l'image, en réessayant sur erreur de lecture. Un partage
    SMB lève parfois un [Errno 22] transitoire ; une brève pause suffit. On ne
    veut pas qu'un hoquet réseau laisse une photo sur son ancien prompt."""
    last = None
    for i in range(tries):
        try:
            return s.image_to_b64(s._resolve_key(key))
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(pause)
    raise last


def rerun_v2():
    """Rejoue UNIQUEMENT la variante V2 (nouveau prompt) sur les résultats déjà
    calculés, en réutilisant V0/V1 tels quels — on ne redépense pas le GPU sur
    les deux autres variantes. Sauvegarde d'abord l'ancien fichier."""
    if not RESULTS_FILE.exists():
        print("Aucun tagging_results.json : lance d'abord la passe complète.")
        return
    old = json.loads(RESULTS_FILE.read_text(encoding='utf-8'))
    results = old['results']
    backup = RESULTS_FILE.with_suffix('.v2avant.json')
    backup.write_text(json.dumps(old, ensure_ascii=False, indent=1),
                      encoding='utf-8')
    print(f"Sauvegarde de l'ancien : {backup.name}")
    print(f"Rejoue V2 (prompt exigeant les noms) sur {len(results)} photos…")
    echecs = []
    with VramSampler() as vram:
        for n, row in enumerate(results, 1):
            # Les assertions se RECALCULENT : reprendre `row['assert']` est ce
            # qui a fait entrer les dates-epoch de juillet dans la mesure du
            # 12/08 (docs/PROTOCOLE_3B_TAGGING.md). On réécrit aussi la ligne.
            a = assertions(row['key'])
            row['assert'] = a
            try:
                b64 = _img_b64_retry(row['key'])
                resp, dt = ollama_call(prompt_v2(a), b64)
                row['V2'] = {'resp': resp, 'dt': round(dt, 2),
                             'malforme': _malforme(resp),
                             'tags': _tags_dict(resp)}
                row.pop('V2_stale', None)
            except Exception as e:
                echecs.append(row['key'])
                row['V2_stale'] = True   # V2 reste sur l'ancien prompt : à exclure
                print(f"  [{n}/{len(results)}] {row['key']} : V2 échoué ({e}) — "
                      f"ancienne V2 conservée (marquée V2_stale)")
            if n % 10 == 0:
                print(f"  [{n}/{len(results)}] fait")
    if echecs:
        print(f"\n! {len(echecs)} photo(s) toujours illisibles apres reessais — "
              f"leur V2 reste sur l'ancien prompt (V2_stale=true, a exclure de "
              f"l'analyse V2) :")
        for k in echecs:
            print(f"    {k}")
    else:
        print("\nToutes les photos rejouees en V2 (aucun echec de lecture).")
    finaliser(results, vram.peak)


# ─────────────────────────── Dépouillement (3b) ───────────────────────────

def compter(notes, mapping, cats=None):
    """Compte les préférences et les hallucinations PAR VARIANTE, à partir des
    notes (index -> {best, halluc}) et du mapping (index -> {lettre: variante}).
    Logique pure : aucun accès disque, aucun store. `cats` = index -> catégorie,
    pour la ventilation par strate."""
    pref, halluc, vus, par_cat = {}, {}, {}, {}
    for i, n in (notes or {}).items():
        brut = (mapping or {}).get(str(i)) or {}
        # les cles techniques (« _key », « _cat ») ne sont pas des lettres
        paire = {L: v for L, v in brut.items() if not str(L).startswith('_')}
        for lettre, v in paire.items():
            vus[v] = vus.get(v, 0) + 1
        best = paire.get(n.get('best'))
        if best:
            pref[best] = pref.get(best, 0) + 1
            c = (cats or {}).get(str(i)) or brut.get('_cat') or '?'
            par_cat.setdefault(c, {})
            par_cat[c][best] = par_cat[c].get(best, 0) + 1
        for h in (n.get('halluc') or []):
            if paire.get(h):
                halluc[paire[h]] = halluc.get(paire[h], 0) + 1
    return {'pref': pref, 'halluc': halluc, 'vus': vus, 'par_cat': par_cat}


def _binom_p(k, n):
    """p bilatérale d'un signe-test à p=0,5 (au moins k succès sur n)."""
    from math import comb
    if not n:
        return 1.0
    k = max(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def depouiller(suffixe=''):
    """Applique le critère de décision de docs/PROTOCOLE_3B_TAGGING.md."""
    notes_f = EVAL_DIR / f"notes{suffixe}.json"
    map_f = EVAL_DIR / f"rating_map{suffixe}.json"
    if not (notes_f.exists() and map_f.exists()):
        print(f"Manque {notes_f.name} ou {map_f.name} — note d'abord la page HTML.")
        return
    notes = json.loads(notes_f.read_text(encoding='utf-8'))
    mapping = json.loads(map_f.read_text(encoding='utf-8'))
    # Strates : « _cat » du mapping si présent (pages générées après le 14/08),
    # sinon reconstruit depuis l'échantillon figé via « _key ».
    cats = {}
    try:
        ech = json.loads(SAMPLE_FILE.read_text(encoding='utf-8'))
        cats = {i: ech.get(m.get('_key')) for i, m in mapping.items()
                if isinstance(m, dict) and m.get('_key')}
    except Exception:
        cats = {}
    st = compter(notes, mapping, {i: c for i, c in cats.items() if c})
    n = sum(st['pref'].values())
    print(f"\n== Depouillement {notes_f.name} — {n} paires notees ==")
    for v, k in sorted(st['pref'].items(), key=lambda x: -x[1]):
        print(f"   {v:<6} prefere {k:>4} fois  ({100.0 * k / n:.1f} %)")
    print(f"   hallucinations : {st['halluc'] or 'aucune'} "
          f"(descriptions vues : {st['vus']})")
    if st['par_cat']:
        print("   par strate :")
        for c, d in sorted(st['par_cat'].items()):
            print(f"      {c:<10} {d}")
    if len(st['pref']) == 2:
        (v1, k1), (_v2, _k2) = sorted(st['pref'].items(), key=lambda x: -x[1])
        p = _binom_p(k1, n)
        print(f"\n   {v1} en tete : {k1}/{n}, p = {p:.4f}")
        # Critere ecrit d'avance (protocole 3b) : significatif ET pas plus
        # d'hallucinations que la reference.
        if p < 0.05:
            print("   -> ECART DEMONTRE. Verifier les hallucinations, puis "
                  "choisir la strate (ROADMAP 3c).")
        else:
            print("   -> NON DEMONTRE. La re-passe ne se fait pas. "
                  "Consigner la decision dans eval/DECISIONS.md.")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true',
                    help="bâtit l'échantillon + montre des assertions, sans Ollama")
    ap.add_argument('--limit', type=int, default=0,
                    help="limiter le nombre de photos (test rapide)")
    ap.add_argument('--rerun-v2', action='store_true',
                    help="rejoue SEULEMENT V2 (nouveau prompt) sur les résultats existants")
    ap.add_argument('--modele', default=MODEL_FIXE,
                    help="modèle Ollama à tester (défaut qwen3-vl:2b). Ex : gemma4:e2b")
    ap.add_argument('--variantes', default='V0,V2CTX',
                    help="variantes à produire (défaut : le banc 3b, V0 vs prompt de prod). "
                         "Ex : V0 pour un comparatif de modèles économe")
    ap.add_argument('--depouiller', nargs='?', const='', metavar='SUFFIXE',
                    help="dépouille une notation déjà faite (eval/notes<SUFFIXE>.json "
                         "x rating_map<SUFFIXE>.json) et applique le critere 3b")
    args = ap.parse_args()

    if args.depouiller is not None:
        depouiller(args.depouiller)
        return

    if args.rerun_v2:
        rerun_v2()
        return

    modele = args.modele
    vs = [v.strip().upper() for v in args.variantes.split(',') if v.strip()]
    inconnu = [v for v in vs if v not in VARIANTES]
    if inconnu:
        print(f"Variante(s) inconnue(s) : {inconnu}. Attendu : {', '.join(VARIANTES)}.")
        return
    paths = _paths(modele)

    ech = construire_echantillon()
    cles = list(ech.keys())
    if args.limit:
        cles = cles[:args.limit]
    from collections import Counter
    print(f"Échantillon : {len(ech)} photos  {dict(Counter(ech.values()))}")
    print(f"Modèle : {modele} | variantes : {','.join(vs)}")

    if args.dry:
        for k in cles[:3]:
            print("\n" + "=" * 60 + f"\n{k}  [{ech[k]}]")
            print(bloc_assertions(assertions(k)))
        print("\n--dry : OK (aucun appel Ollama).")
        return

    results = []
    with VramSampler() as vram:
        for n, k in enumerate(cles, 1):
            a = assertions(k)
            try:
                p = s._resolve_key(k)
                b64 = s.image_to_b64(p)
            except Exception as e:
                print(f"  [{n}/{len(cles)}] {k} : image illisible ({e}) — sautée")
                continue
            row = {'key': k, 'cat': ech[k], 'assert': a}
            src = {'V0': (s.PROMPT, b64), 'V1': (prompt_v1(a), None),
                   'V2': (prompt_v2(a), b64), 'V2CTX': (prompt_v2ctx(a), b64)}
            try:
                for v in vs:
                    prompt, img = src[v]
                    resp, dt = ollama_call(prompt, img, model=modele)
                    row[v] = {'resp': resp, 'dt': round(dt, 2),
                              'malforme': _malforme(resp),
                              'tags': _tags_dict(resp)}
            except Exception as e:
                print(f"  [{n}/{len(cles)}] {k} : erreur Ollama ({e}) — sautée")
                continue
            results.append(row)
            if n % 10 == 0:
                print(f"  [{n}/{len(cles)}] fait")

    finaliser(results, vram.peak, modele, paths)


if __name__ == '__main__':
    main()
