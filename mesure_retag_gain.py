#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier 2 bis -- CHIFFRER le gain d'un re-tagging avant de payer les 26 h
de GPU (question de Mike, 31/08 ; ROADMAP.md).

22 196 entrees (52 % du fonds) portent des mots-cles herites d'un XMP relu
(reconstruction de l'index du 11/07), PAS du tagueur actuel (`v2ctx`, adopte
le 12/08). Avant de retagger tout ce sous-ensemble (~4,3 s/photo mesure =
~26 h de GPU, sur une machine qui a coupe quatre fois en trois jours), ce
banc REJOUE le tagueur de PROD sur un echantillon deja tague des deux
generations et mesure a quel point les mots-cles changent :

  - groupe "v0"    : entrees sans `pipe` (XMP relu, 11/07) -- la ou un gain
                      est plausible ;
  - groupe "v2ctx"  : entrees deja taguees par le pipeline actuel -- le
                      PLANCHER DE BRUIT (le modele n'est pas deterministe a
                      temperature > 0 ; deux passes du MEME pipeline sur la
                      MEME photo ne rendent pas exactement les memes mots).

Si le groupe "v0" diverge nettement PLUS que le groupe "v2ctx", le gain est
reel et mesure. S'ils divergent pareil, re-tagger le fonds ne ferait que
rejouer le bruit du modele -- pas justifier 26 h de GPU.

Suit la meme discipline que `mesure_sensibles.py` (chantier 18) :
LECTURE SEULE sur le fonds, `--base copie.db` exigee (jamais `photos.db` :
le serveur est l'ecrivain unique), cache reprenable, `--budget-s`, rapport
`docs/*_echantillon.json` explicitement pour le JUGEMENT de Mike -- rien ne
bouge, rien ne s'ecrit dans l'index ni dans un XMP.

Reprend le prompt de PROD tel quel (`tagging_meta.prompt_tagging`), SANS
`import server` (dangereux hors serveur : `STORE = make_store(...)` s'execute
a l'import, ouvrirait `photos.db` -- meme regle que `mesure_sensibles.py`).

Simplification DOCUMENTEE, appliquee IDENTIQUEMENT aux deux groupes (donc
neutre pour la comparaison) : les assertions `lieu`/`species` de
`server._assertions_pour` dependent de stores en memoire (cache de
geocodage, ANIMAL_STORE) indisponibles hors serveur -- omises ici. `persons`/
`animals`/`tags_fr`/`date` sont reconstruits depuis les propres champs deja
persistes de l'entree dans `copie.db` (`kw_fr`/`kw_en`/`taken`), qui sont
precisement ce qu'une relecture ExifTool du fichier rendrait aujourd'hui
(c'est ce que `write_metadata` y a ecrit a la derniere passe de tagging --
voir server.tagger_worker).

Usage (par l'agent banc) :
    mesure_retag_gain.py --base copie.db [--v0 50] [--v2ctx 50]
                         [--budget-s 450] [--graine 42] [--relance] [--dry]
"""
import argparse
import base64
import hashlib
import io
import json
import random
import re
import sqlite3
import time
import urllib.request
from pathlib import Path

import tagging_meta

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'retag_gain_echantillon.json'
CACHE = RACINE / 'docs' / 'retag_gain_cache.json'
OLLAMA = 'http://127.0.0.1:11434/api/generate'
MODELE = 'qwen3-vl:2b'


# ── regles pures (testees par test_mesure_retag_gain.py) ────────────────────

def empreinte_prompt():
    """12 hex du SHA-256 du texte du prompt de PROD (`tagging_meta`), pour que
    le cache se sache perime si `bloc_assertions`/`prompt_tagging`/
    `REGLES_JSON` changent -- meme garde-fou que `mesure_sensibles.empreinte_
    prompt` : un verdict rendu par une AUTRE question n'est pas la meme
    mesure."""
    exemple = tagging_meta.prompt_tagging({
        'persons': ['X'], 'animals': ['Y'], 'species': ['z'],
        'lieu': 'l', 'lieu_src': 'chemin', 'date': 'd', 'date_src': 'exif',
        'tags_fr': ['a', 'b']})
    h = hashlib.sha256(exemple.encode('utf-8'))
    return h.hexdigest()[:12]


def generation(e):
    """« v0 » (XMP relu, sans estampille) ou la valeur de `pipe` sinon --
    identique a `server._tagging_pipe_counts` : `e.get('pipe') or 'v0'`."""
    return e.get('pipe') or 'v0'


def plain_kw(kw):
    """Mots-cles LIBRES d'une liste (sans les tags nommes personne:/animal:,
    prefixe insensible a la casse) -- exclus de la mesure de divergence :
    `merge_named_tags` les fait TOUJOURS survivre a un re-tagging, un ecart
    dessus ne mesurerait rien sur le tagueur, seulement une fusion deja
    prouvee ailleurs (tagging_meta)."""
    out = []
    for t in (kw or []):
        s = str(t)
        low = s.lower()
        if not (low.startswith('personne:') or low.startswith('animal:')):
            out.append(low)
    return out


def assertions_pour(e):
    """Equivalent auto-suffisant de `server._assertions_pour`, batie
    uniquement depuis les champs deja persistes d'une entree de `copie.db` --
    voir la simplification documentee en tete de fichier (lieu/species omis,
    identiquement pour les deux groupes)."""
    existing = list(e.get('kw_fr') or []) + list(e.get('kw_en') or [])
    persons, animals = tagging_meta.noms_depuis_kw(existing)
    date_txt = date_src = None
    taken = e.get('taken')
    if taken:
        date_txt, date_src = tagging_meta.format_date_fr(taken), 'exif'
    return {'persons': persons, 'animals': animals, 'species': [],
            'lieu': None, 'lieu_src': None,
            'date': date_txt, 'date_src': date_src,
            'tags_fr': plain_kw(e.get('kw_fr'))[:12]}


def jaccard(a, b):
    """Similarite de Jaccard entre deux ensembles de mots-cles libres ; 1.0 si
    les deux sont vides (rien a comparer -> pas de divergence)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 1.0


def divergence(anciens_kw, nouveaux_kw_fr, nouveaux_kw_en):
    """Un point de mesure pour UNE photo : (jaccard, ajoutes, retires).
    `anciens_kw` = mots-cles libres deja persistes (les deux langues,
    l'entree de `copie.db` ne les distingue plus une fois fusionnes en
    `merged` cote serveur) ; on compare a l'union kw_fr+kw_en de la NOUVELLE
    reponse pour rester symetrique."""
    anc = set(plain_kw(anciens_kw))
    nouv = set(plain_kw(list(nouveaux_kw_fr or []) + list(nouveaux_kw_en or [])))
    return {'jaccard': round(jaccard(anc, nouv), 3),
            'ajoutes': sorted(nouv - anc), 'retires': sorted(anc - nouv)}


def echantillonner(entrees, n_v0, n_v2ctx, graine):
    """(v0, v2ctx) : tirage DETERMINISTE (graine), meme discipline que
    `mesure_sensibles.echantillonner` -- reprenable, discutable (<< la photo
    12 >> designe toujours la meme)."""
    v0 = [k for k, e in entrees if generation(e) == 'v0']
    v2 = [k for k, e in entrees if generation(e) != 'v0']
    rng = random.Random(graine)
    rng.shuffle(v0)
    rng.shuffle(v2)
    return v0[:n_v0], v2[:n_v2ctx]


def resume_groupe(lignes):
    """Moyenne de jaccard + moyenne d'ajouts/retraits pour un groupe -- vide
    si aucune ligne (budget coupe avant d'atteindre le groupe)."""
    if not lignes:
        return {'n': 0, 'jaccard_moyen': None, 'ajoutes_moyen': None,
                'retires_moyen': None}
    n = len(lignes)
    return {'n': n,
            'jaccard_moyen': round(sum(l['jaccard'] for l in lignes) / n, 3),
            'ajoutes_moyen': round(sum(len(l['ajoutes']) for l in lignes) / n, 2),
            'retires_moyen': round(sum(len(l['retires']) for l in lignes) / n, 2)}


# ── acces (base copiee, NAS en lecture, Ollama local) ───────────────────────

def charger(base):
    if Path(base).name == 'photos.db':
        raise SystemExit('REFUS : ce banc lit une COPIE (--base copie.db), '
                         'jamais photos.db -- le serveur est l ecrivain unique.')
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).as_posix(), uri=True)
    out = []
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if (isinstance(e, dict) and not e.get('failed') and not e.get('video')
                and Path(k).suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}
                and (e.get('kw_fr') or e.get('kw_en'))):
            out.append((k, e))
    cx.close()
    out.sort()                      # ordre stable avant tirage seede
    return out


def image_b64(chemin, cote=896):
    from PIL import Image, ImageOps      # paresseux : le test n'en a pas besoin
    with Image.open(chemin) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((cote, cote))
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def ollama_generate(b64, prompt):
    """Meme forme de requete que `server.ollama_generate` (temperature/
    num_predict/num_ctx/repeat_penalty/keep_alive identiques) -- une reponse
    obtenue autrement ne mesurerait pas le tagueur de PROD."""
    corps = json.dumps({
        'model': MODELE, 'prompt': prompt, 'images': [b64], 'stream': False,
        'format': 'json', 'think': False, 'keep_alive': '30m',
        'options': {'temperature': 0.2, 'num_predict': 256, 'num_ctx': 4096,
                    'repeat_penalty': 1.05}}).encode()
    req = urllib.request.Request(OLLAMA, data=corps,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    return data.get('response') or data.get('thinking') or ''


def parse_tags(raw):
    """Copie du chemin json -> regex -> salvage de `server.parse_tags` /
    `_norm_keywords` / `_salvage_tags`, simplifiee (pas de plafond 12/40 : ce
    banc mesure ce que le modele rend, pas ce que le serveur en garderait)."""
    raw = (raw or '').strip()
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except ValueError:
            m = re.search(r'\{.*\}', raw, re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                except ValueError:
                    data = None
    if isinstance(data, dict):
        kw_en = data.get('keywords_en') or []
        kw_fr = data.get('keywords_fr') or []
        desc = str(data.get('description_fr') or '').strip()[:300]
        return kw_fr, kw_en, desc
    # reponse tronquee : recupere ce qui est exploitable (chaines completes)
    def arr(key):
        m = re.search(r'"' + key + r'"\s*:\s*\[(.*?)(?:\]|$)', raw, re.S)
        return re.findall(r'"([^"]+)"', m.group(1)) if m else []
    kw_fr, kw_en = arr('keywords_fr'), arr('keywords_en')
    dm = re.search(r'"description_fr"\s*:\s*"([^"]*)"', raw)
    desc = (dm.group(1) if dm else '').strip()[:300]
    return kw_fr, kw_en, desc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--v0', type=int, default=50)
    ap.add_argument('--v2ctx', type=int, default=50)
    ap.add_argument('--budget-s', type=float, default=450)
    ap.add_argument('--graine', type=int, default=42)
    ap.add_argument('--relance', action='store_true',
                    help='ignore le cache (re-interroge tout)')
    ap.add_argument('--pause-s', type=float, default=0,
                    help='pause entre deux photos (menagement thermique)')
    ap.add_argument('--dry', action='store_true',
                    help='affiche le tirage et sort, aucun appel Ollama')
    a = ap.parse_args(argv)
    fin = time.time() + a.budget_s

    entrees = charger(a.base)
    v0, v2 = echantillonner(entrees, a.v0, a.v2ctx, a.graine)
    print('fonds lisible (deja tague) : %d entrees ; echantillon : '
          '%d v0 + %d v2ctx' % (len(entrees), len(v0), len(v2)), flush=True)
    if a.dry:
        print('DRY-RUN -- tirage seulement, aucun appel Ollama.')
        print('v0    :', [Path(k).name for k in v0[:5]], '...')
        print('v2ctx :', [Path(k).name for k in v2[:5]], '...')
        return 0

    par_cle = dict(entrees)
    emp = empreinte_prompt()
    cache = {}
    if CACHE.is_file() and not a.relance:
        try:
            brut = json.loads(CACHE.read_text(encoding='utf-8'))
        except ValueError:
            brut = {}
        vue = brut.pop('_prompt', None)
        if vue == emp:
            cache = brut
        elif brut:
            print('cache IGNORE : rendu par un autre prompt (%s != %s) -- '
                  '%d verdict(s) ecartes, la question a change'
                  % (vue, emp, len(brut)), flush=True)
    print('empreinte du prompt : %s' % emp, flush=True)

    lot = [(k, 'v0') for k in v0] + [(k, 'v2ctx') for k in v2]
    faits, coupe = 0, False
    for k, groupe in lot:
        if k in cache:
            continue
        if time.time() > fin:
            coupe = True
            print('budget atteint : %d question(s) cette passe, reprise au '
                  'prochain lancement (cache)' % faits, flush=True)
            break
        e = par_cle[k]
        t0 = time.time()
        try:
            prompt = tagging_meta.prompt_tagging(assertions_pour(e))
            raw = ollama_generate(image_b64(k), prompt)
            kw_fr, kw_en, desc = parse_tags(raw)
            div = divergence(list(e.get('kw_fr') or []) + list(e.get('kw_en') or []),
                             kw_fr, kw_en)
            cache[k] = {'groupe': groupe, 'jaccard': div['jaccard'],
                        'ajoutes': div['ajoutes'], 'retires': div['retires'],
                        'duree_s': round(time.time() - t0, 1)}
        except Exception as exc:                                  # noqa: BLE001
            cache[k] = {'groupe': groupe, 'jaccard': None, 'erreur': str(exc)[:120],
                        'duree_s': round(time.time() - t0, 1)}
        faits += 1
        if a.pause_s:
            time.sleep(a.pause_s)
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(dict(cache, _prompt=emp),
                                    ensure_ascii=False, indent=1),
                         encoding='utf-8')
        j = cache[k].get('jaccard')
        print('%3d/%d  %-6s jaccard=%s  %s'
              % (faits, len(lot), groupe, j, Path(k).name[:50]), flush=True)

    lignes = [{'key': k, **cache[k]} for k, g in lot if k in cache]
    v0_lignes = [l for l in lignes if l['groupe'] == 'v0' and l.get('jaccard') is not None]
    v2_lignes = [l for l in lignes if l['groupe'] == 'v2ctx' and l.get('jaccard') is not None]
    resume = {'v0': resume_groupe(v0_lignes), 'v2ctx': resume_groupe(v2_lignes)}
    if resume['v0']['jaccard_moyen'] is not None and resume['v2ctx']['jaccard_moyen'] is not None:
        # divergence = 1 - jaccard ; le "gain" est l'ecart de divergence entre
        # les deux groupes, PAS une verite : une liste a JUGER par Mike.
        resume['ecart_divergence_v0_moins_v2ctx'] = round(
            (1 - resume['v0']['jaccard_moyen']) - (1 - resume['v2ctx']['jaccard_moyen']), 3)
    RAPPORT.write_text(json.dumps({
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
        'modele': MODELE, 'graine': a.graine, 'complet': not coupe,
        'prompt': emp, 'resume': resume, 'lignes': lignes},
        ensure_ascii=False, indent=1), encoding='utf-8')
    print('rapport ecrit :', RAPPORT, '-- resume :', json.dumps(resume, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
