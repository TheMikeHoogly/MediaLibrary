#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chantier 18 -- MESURE du detecteur de documents sensibles, sur echantillon.

AVANT tout branchement dans le tagueur (regle 18e : jeu etiquete et banc avant
tout seuil), ce banc pose la question << sensible ? >> au modele de PROD
(qwen3-vl:2b, via Ollama local) sur un echantillon du fonds :

  - des CANDIDATS probables (mots-cles/description evoquant un document,
    un recu, une capture, un formulaire...) -- la ou le rappel se joue ;
  - des TEMOINS tires au hasard (photos ordinaires) -- la ou la precision
    se joue, et le garde-fou contre un modele qui dirait << sensible >>
    partout (un score parfait est une alarme).

Sept categories (Mike : six le 30/08 soir, `administratif` ajoutee le 31/08
apres que le banc a fait passer en << non >> une lettre de la ville de
Lausanne -- juste au sens des six, et pourtant exactement ce qu'on ne veut pas
partager a vingt) : facture, paie, identite, banque, medical, message,
administratif -- sinon << non >>.

LECTURE SEULE sur le fonds ; ecrit docs/sensibles_echantillon.json (rapport)
et docs/sensibles_cache.json (reprise apres budget). Exige une COPIE de la
base (--base copie.db, jamais photos.db : le serveur est l'ecrivain unique).
Le verdict du banc n'est PAS une etiquette : c'est la liste que Mike jugera
-- rien ne bouge, rien ne s'ecrit dans l'index ni dans un XMP.

Usage (par l'agent banc) :
    mesure_sensibles.py --base copie.db [--candidats 60] [--temoins 30]
                        [--budget-s 450] [--graine 42] [--relance]
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

RACINE = Path(__file__).resolve().parent
RAPPORT = RACINE / 'docs' / 'sensibles_echantillon.json'
CACHE = RACINE / 'docs' / 'sensibles_cache.json'
OLLAMA = 'http://127.0.0.1:11434/api/generate'
MODELE = 'qwen3-vl:2b'
CATEGORIES = ('facture', 'paie', 'identite', 'banque', 'medical', 'message',
              'administratif')

# Vocabulaire des CANDIDATS : ce que le tagueur actuel pose deja sur les
# documents (il a l'instruction de rester generique : "document", "recu",
# "capture"...). Volontairement large -- un candidat de trop coute une
# question au modele, un candidat manque coute une fuite non mesuree.
VOCAB = {'document', 'documents', 'recu', 'reçu', 'facture', 'capture',
         'administratif', 'administrative', 'officiel', 'officielle',
         'screenshot', 'texte', 'text', 'receipt', 'invoice', 'papier',
         'formulaire', 'contrat', 'ticket', 'bulletin', 'carte', 'passeport',
         'ordonnance', 'certificat', 'lettre', 'courrier', 'page', 'scan',
         'ecriture', 'écriture', 'menu', 'etiquette', 'étiquette'}

PROMPT = (
    'Regarde cette photo. Est-ce un DOCUMENT PERSONNEL sensible ?\n'
    'Reponds UNIQUEMENT en JSON strict :\n'
    '{"sensible": "...", "confiance": "haute|basse"}\n'
    'Valeurs possibles pour "sensible" :\n'
    '- "facture" : facture, recu, ticket de caisse, devis\n'
    '- "paie" : fiche de salaire, decompte de paie\n'
    '- "identite" : carte d identite, passeport, permis, carte de credit\n'
    '- "banque" : releve bancaire, e-banking, IBAN visible\n'
    '- "medical" : ordonnance, resultat d analyse, document medical\n'
    '- "message" : capture d ecran de conversation (SMS, WhatsApp, email)\n'
    '- "administratif" : courrier officiel nominatif (commune, canton, '
    'assurance, impots, employeur, ecole, bail, contrat)\n'
    '- "non" : tout le reste (photo ordinaire, paysage, personnes, menu de '
    'restaurant, panneau, livre, page web publique)\n'
    'Dans le doute entre deux categories sensibles, choisis la plus proche. '
    'Ne transcris aucun texte visible.'
)


# ── regles pures (testees par test_mesure_sensibles.py) ──────────────────────

def empreinte_prompt():
    """Les 12 premiers hex du SHA-256 du prompt + des categories.

    Un verdict rendu par un AUTRE prompt n'est pas la meme mesure : le cache
    porte cette empreinte, et une passe qui trouve un cache etranger le DIT
    et repart de zero. Sans ca, ajouter une categorie (`administratif`, le
    31/08) laisserait 43 verdicts rendus par l'ancienne question se melanger
    aux nouveaux -- un banc qui ment est pire que pas de banc."""
    h = hashlib.sha256((PROMPT + '|' + '|'.join(CATEGORIES)).encode('utf-8'))
    return h.hexdigest()[:12]


def mots_de(e):
    """L'ensemble des mots (minuscules) des kw_fr + kw_en + desc d'une entree."""
    out = set()
    for t in list(e.get('kw_fr') or []) + list(e.get('kw_en') or []):
        if isinstance(t, str) and ':' not in t:
            out |= set(re.findall(r"[a-zA-ZÀ-ſ']+", t.lower()))
    out |= set(re.findall(r"[a-zA-ZÀ-ſ']+", str(e.get('desc') or '').lower()))
    return out


def est_candidat(e):
    """Vrai si l'entree evoque un document (vocabulaire ci-dessus)."""
    return bool(mots_de(e) & VOCAB)


def echantillonner(entrees, n_candidats, n_temoins, graine):
    """(candidats, temoins) : tirage DETERMINISTE (graine) -- le meme
    echantillon a chaque passe, c'est ce qui rend le banc reprenable et la
    discussion possible (<< la photo 12 >> designe toujours la meme)."""
    cand = [k for k, e in entrees if est_candidat(e)]
    autres = [k for k, e in entrees if not est_candidat(e)]
    rng = random.Random(graine)
    rng.shuffle(cand)
    rng.shuffle(autres)
    return cand[:n_candidats], autres[:n_temoins]


def lire_verdict(raw):
    """Le JSON du modele -> (categorie, confiance) ; ('illisible', '') si rien.
    Une categorie inventee vaut 'illisible' : un axe n'accepte pas de valeur
    libre (garde-fou du 26/08)."""
    raw = (raw or '').strip()
    data = None
    try:
        data = json.loads(raw)
    except ValueError:
        m = re.search(r'\{.*\}', raw, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
            except ValueError:
                data = None
    if not isinstance(data, dict):
        return 'illisible', ''
    v = str(data.get('sensible') or '').strip().lower()
    c = str(data.get('confiance') or '').strip().lower()
    if v == 'non' or v in CATEGORIES:
        return v, c
    return 'illisible', ''


# ── acces (base copiee, NAS en lecture, Ollama local) ────────────────────────

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
                and Path(k).suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}):
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


def interroger(b64):
    corps = json.dumps({'model': MODELE, 'prompt': PROMPT, 'images': [b64],
                        'stream': False, 'keep_alive': '30m',
                        'options': {'temperature': 0}}).encode()
    req = urllib.request.Request(OLLAMA, data=corps,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode()).get('response', '')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidats', type=int, default=60)
    ap.add_argument('--temoins', type=int, default=30)
    ap.add_argument('--budget-s', type=float, default=450)
    ap.add_argument('--graine', type=int, default=42)
    ap.add_argument('--relance', action='store_true',
                    help='ignore le cache (re-interroge tout)')
    ap.add_argument('--pause-s', type=float, default=0,
                    help='pause entre deux photos (menagement thermique -- '
                         'le PC a coupe deux fois le 30/08)')
    a = ap.parse_args(argv)
    fin = time.time() + a.budget_s

    entrees = charger(a.base)
    par_cle = dict(entrees)
    cand, tem = echantillonner(entrees, a.candidats, a.temoins, a.graine)
    print('fonds lisible : %d entrees ; echantillon : %d candidats + %d temoins'
          % (len(entrees), len(cand), len(tem)), flush=True)

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

    lot = [(k, 'candidat') for k in cand] + [(k, 'temoin') for k in tem]
    faits, coupe = 0, False
    for k, groupe in lot:
        if k in cache:
            continue
        if time.time() > fin:
            coupe = True
            print('budget atteint : %d question(s) cette passe, reprise au '
                  'prochain lancement (cache)' % faits, flush=True)
            break
        t0 = time.time()
        try:
            verdict, conf = lire_verdict(interroger(image_b64(k)))
        except Exception as e:                                # noqa: BLE001
            verdict, conf = 'erreur', str(e)[:80]
        cache[k] = {'groupe': groupe, 'verdict': verdict, 'confiance': conf,
                    'duree_s': round(time.time() - t0, 1)}
        faits += 1
        if a.pause_s:
            time.sleep(a.pause_s)
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(dict(cache, _prompt=emp),
                                    ensure_ascii=False, indent=1),
                         encoding='utf-8')
        print('%3d/%d  %-8s %-9s %s' % (faits, len(lot), groupe,
                                        verdict, Path(k).name[:50]), flush=True)

    # rapport : seulement l'echantillon du jour, dans l'ordre du tirage
    lignes = [{'key': k, 'groupe': g, **{x: cache[k][x] for x in
               ('verdict', 'confiance', 'duree_s')}}
              for k, g in lot if k in cache]
    RAPPORT.write_text(json.dumps({
        'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'),
        'modele': MODELE, 'graine': a.graine, 'complet': not coupe,
        'prompt': emp, 'categories': list(CATEGORIES),
        'lignes': lignes}, ensure_ascii=False, indent=1), encoding='utf-8')

    comptes = {}
    for l in lignes:
        cle = (l['groupe'], l['verdict'])
        comptes[cle] = comptes.get(cle, 0) + 1
    print('--- bilan (%d juges) ---' % len(lignes), flush=True)
    for (g, v), n in sorted(comptes.items()):
        print('  %-8s %-9s %d' % (g, v, n), flush=True)
    sensibles_temoins = sum(n for (g, v), n in comptes.items()
                            if g == 'temoin' and v in CATEGORIES)
    print('temoins juges sensibles : %d (chaque cas est a regarder a l oeil '
          '-- un temoin peut etre un VRAI document passe inapercu)'
          % sensibles_temoins, flush=True)
    print('rapport : docs/sensibles_echantillon.json -- la liste a juger par '
          'Mike, rien n a bouge', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
