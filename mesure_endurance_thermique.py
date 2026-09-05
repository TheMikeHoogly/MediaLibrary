#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure -- la machine tient-elle des HEURES de tagage, ou bride-t-elle ?
------------------------------------------------------------------------------

CE QU'ON CHERCHE, ET POURQUOI MAINTENANT

Le chantier 2 quater va demander au GPU cinq jours de travail d'affilee. Or
l'endurance de cette machine n'a jamais ete prouvee que par RAFALES de ~450 s
(chantier confidentialite, 04/09) -- et elle s'est deja coupee net quatre fois
sous charge (Kernel-Power 41). La question n'est donc pas "est-ce que ca marche"
mais "est-ce que ca TIENT", et elle ne se repond qu'en chargeant longtemps.

CE QUE CE BANC FAIT

Il rejoue le tagage de PRODUCTION -- meme modele (lu dans `modele.txt`), meme
prompt (`tagging_meta.prompt_tagging`), meme redimensionnement, memes options
Ollama -- sur des photos tirees de la base, et **JETTE la reponse**. Aucune
ecriture d'index, aucune ecriture de XMP, aucun fichier photo touche : la seule
chose qu'il produit, c'est de la CHALEUR et un rapport.

Entre deux photos il interroge `nvidia-smi` et retient ce que la carte AVOUE :
temperature, horloge courante contre horloge max, watts, et surtout
`clocks_throttle_reasons` -- le champ ou elle NOMME elle-meme la cause de son
ralentissement. Un bridage deduit d'un chronometre est une opinion ; celui-la
est un fait rendu par le materiel.

CE QU'IL ETABLIT, ET CE QU'IL N'ETABLIT PAS

Il etablit : la temperature atteinte sous charge reelle, l'instant du premier
bridage s'il vient, et la DERIVE du debit -- le signal du 28/08 etait une
session a 27,2 s/photo contre 9,7-22,8 s pour les autres du meme jour. Le
rapport decoupe la charge en tranches et compare la derniere a la premiere.

Il n'etablit PAS une charge parfaitement continue : le canal du banc plafonne a
600 s, donc une longue endurance se fait en tranches d'environ 450 s separees
d'une minute d'attente -- environ 85 % de service. C'est une limite REELLE et
elle est dite : un portable qui ne bride qu'apres vingt minutes ininterrompues
passerait au travers. Le rapport CUMULE les tranches (`--rapport` relu et
complete a chaque passage) pour que la question se pose sur des heures et non
sur sept minutes, mais le trou d'une minute reste dans les donnees, horodate.

Et il ne remplace pas la boucle du serveur (`thermique_loop`), qui elle tourne
PENDANT la campagne et ecrit au journal des qu'il fait chaud : ce banc dit s'il
FAUT s'inquieter, cette boucle dira QUAND.

SORTIE EN ASCII PUR (console cp1252 de l'agent).

USAGE
    mesure_endurance_thermique.py --base copie.db --budget-s 450
    mesure_endurance_thermique.py --base copie.db --budget-s 450 --reset
"""
import argparse
import base64
import io
import json
import random
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import tagging_meta

ICI = Path(__file__).resolve().parent
OLLAMA = 'http://127.0.0.1:11434/api/generate'
CHAMPS = ("utilization.gpu,temperature.gpu,clocks.sm,clocks.max.sm,"
          "power.draw,clocks_throttle_reasons.hw_thermal_slowdown,"
          "clocks_throttle_reasons.sw_thermal_slowdown")


def modele_de_prod():
    """Le modele que le serveur utilise VRAIMENT : premiere ligne utile de
    modele.txt. Mesurer un autre modele que celui qui chauffera serait mesurer
    autre chose."""
    try:
        for l in (ICI / 'modele.txt').read_text(encoding='utf-8').splitlines():
            l = l.strip()
            if l and not l.startswith('#'):
                return l
    except OSError:
        pass
    return 'qwen3-vl:2b'


def sonde():
    """Ce que la carte accepte de dire, ou None. Ne LEVE jamais : une sonde qui
    tombe ne doit pas emporter la mesure de charge avec elle."""
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=' + CHAMPS,
                            '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=5)
        lignes = (r.stdout or '').strip().splitlines()
        if r.returncode != 0 or not lignes:
            return None
        p = [x.strip() for x in lignes[0].split(',')]
        if len(p) < 7:
            return None

        def n(x, entier=True):
            try:
                return int(float(x)) if entier else round(float(x), 1)
            except (TypeError, ValueError):
                return None
        return {'util': n(p[0]), 'temp_c': n(p[1]), 'mhz': n(p[2]),
                'mhz_max': n(p[3]), 'watts': n(p[4], False),
                'bride': p[5].lower() == 'active' or p[6].lower() == 'active'}
    except Exception:
        return None


def photos_de_la_base(base, combien, deja):
    """Des cles d'index dont le FICHIER existe, tirees au hasard mais JAMAIS
    celles des tranches precedentes : deux passes sur les memes photos
    mesureraient le cache du NAS autant que le GPU."""
    if Path(base).name == 'photos.db':
        raise SystemExit('REFUS : ce banc lit une COPIE (--base copie.db), '
                         'jamais photos.db -- le serveur est l ecrivain unique.')
    import sqlite3
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).as_posix(), uri=True)
    cand = []
    for k, v in cx.execute('SELECT k, v FROM tags'):
        if k in deja:
            continue
        try:
            e = json.loads(v)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get('failed') or e.get('video'):
            continue
        if not k.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        cand.append((k, e))
    cx.close()
    random.shuffle(cand)
    return cand[:combien]


def image_b64(chemin, cote=896):
    from PIL import Image, ImageOps
    with Image.open(chemin) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((cote, cote))
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def prompt_de_prod(e):
    """Les memes assertions que mesure_modele_vision / mesure_retag_gain, pour
    que la charge du banc soit celle de la production et pas une plus legere."""
    existing = list(e.get('kw_fr') or []) + list(e.get('kw_en') or [])
    persons, animals = tagging_meta.noms_depuis_kw(existing)
    date_txt = date_src = None
    if e.get('taken'):
        date_txt, date_src = tagging_meta.format_date_fr(e['taken']), 'exif'
    plain = [str(t).lower() for t in (e.get('kw_fr') or [])
             if ':' not in str(t)]
    return tagging_meta.prompt_tagging(
        {'persons': persons, 'animals': animals, 'species': [],
         'lieu': None, 'lieu_src': None, 'date': date_txt,
         'date_src': date_src, 'tags_fr': plain[:12]})


def tagger(modele, b64, prompt):
    corps = json.dumps({
        'model': modele, 'prompt': prompt, 'images': [b64], 'stream': False,
        'format': 'json', 'think': False, 'keep_alive': '30m',
        'options': {'temperature': 0.2, 'num_predict': 256, 'num_ctx': 4096,
                    'repeat_penalty': 1.05}}).encode()
    req = urllib.request.Request(OLLAMA, data=corps,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        r.read()          # la reponse est JETEE : ce banc ne juge pas les tags


def lire_rapport(chemin):
    try:
        d = json.loads(Path(chemin).read_text(encoding='utf-8'))
        if isinstance(d, dict) and isinstance(d.get('photos'), list):
            return d
    except (OSError, ValueError):
        pass
    return {'version': 1, 'debut': None, 'modele': None, 'tranches': [],
            'photos': [], 'releves': []}


def ecrire_rapport(chemin, d):
    tmp = Path(str(chemin) + '.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    import os
    os.replace(str(tmp), str(chemin))


def resume(d):
    """Ce que la charge accumulee DIT -- ou ne dit pas encore. Toutes les
    phrases sont bornees par ce qui a ete mesure : pas de verdict sur une
    tranche qui n'a pas eu lieu."""
    ph = d['photos']
    rel = [r for r in d['releves'] if r.get('temp_c') is not None]
    charge = sum(p['s'] for p in ph)
    L = []
    L.append('charge cumulee : %.0f s (%.2f h) sur %d photo(s), %d tranche(s)'
             % (charge, charge / 3600.0, len(ph), len(d['tranches'])))
    if not ph:
        return L
    temps = sorted(p['s'] for p in ph)
    L.append('duree par photo : min %.1f s  median %.1f s  max %.1f s'
             % (temps[0], temps[len(temps) // 2], temps[-1]))
    if rel:
        t = [r['temp_c'] for r in rel]
        L.append('temperature GPU : max %d C  median %d C  (%d releve(s))'
                 % (max(t), sorted(t)[len(t) // 2], len(t)))
        brides = [r for r in rel if r.get('bride')]
        if brides:
            L.append('BRIDAGE THERMIQUE avoue par la carte : %d releve(s) sur '
                     '%d, le premier a %.0f s de charge cumulee'
                     % (len(brides), len(rel), brides[0]['charge_s']))
        else:
            L.append('bridage thermique : JAMAIS avoue sur %d releve(s)' % len(rel))
        # `utilization.gpu` est une MOYENNE glissante : un releve pris juste
        # apres une reponse d Ollama rend encore 99 % alors que l horloge est
        # deja retombee a 350 MHz et la carte a 12 W. Compter ces releves-la
        # comme un ralentissement sous charge serait inventer un probleme. On
        # exige donc aussi une consommation de travail (> 18 W) : en dessous,
        # la carte ne calcule plus, elle finit de rendre la main.
        bas = [r for r in rel if r.get('mhz') and r.get('mhz_max')
               and r['mhz'] < 0.7 * r['mhz_max'] and (r.get('util') or 0) > 90
               and (r.get('watts') or 0) > 18]
        if bas:
            L.append('horloge sous 70%% du max alors que la carte CALCULE '
                     '(util > 90%%, > 18 W) : %d releve(s) sur %d -- a regarder '
                     'meme sans aveu de bridage' % (len(bas), len(rel)))
        else:
            L.append('horloge : jamais sous 70%% du max pendant que la carte '
                     'calcule')
    # Derive : la question du 28/08. Quatre tranches d'egale population.
    if len(ph) >= 12:
        q = len(ph) // 4
        prem = sum(p['s'] for p in ph[:q]) / q
        dern = sum(p['s'] for p in ph[-q:]) / q
        L.append('debit : %.1f s/photo sur le premier quart, %.1f s/photo sur '
                 'le dernier (x%.2f)' % (prem, dern, dern / prem if prem else 0))
        if prem and dern > 1.5 * prem:
            L.append('  -> DERIVE NETTE : le debit s effondre sous la charge, '
                     'exactement la signature du 28/08. NE PAS lancer la '
                     'campagne sans avoir compris pourquoi.')
        elif prem and dern > 1.2 * prem:
            L.append('  -> derive legere : a surveiller, pas encore un refus.')
        else:
            L.append('  -> pas de derive : le debit tient sur la charge mesuree.')
    else:
        L.append('debit : moins de 12 photos, aucune derive n est calculable '
                 '(et ne PAS en conclure qu il n y en a pas).')
    L.append('LIMITE : charge en tranches d environ %d s separees d une pause '
             '(plafond 600 s du canal). Un bridage qui ne viendrait qu apres '
             'vingt minutes ininterrompues passerait au travers.'
             % (d['tranches'][-1]['budget_s'] if d['tranches'] else 450))
    return L


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--budget-s', type=int, default=450)
    ap.add_argument('--rapport', default='docs/endurance_thermique.json')
    ap.add_argument('--modele', default=None)
    ap.add_argument('--pause-releve', type=int, default=20)
    ap.add_argument('--reset', action='store_true',
                    help='repart de zero au lieu de cumuler')
    ap.add_argument('--resume-seul', action='store_true',
                    help='relit le rapport et REDIT ce qu il montre, sans '
                         'charger le GPU -- pour rejuger une mesure deja '
                         'faite quand la lecture change, jamais la mesure')
    a = ap.parse_args(argv)

    rapport = ICI / a.rapport
    rapport.parent.mkdir(parents=True, exist_ok=True)
    d = {'version': 1, 'debut': None, 'modele': None, 'tranches': [],
         'photos': [], 'releves': []} if a.reset else lire_rapport(rapport)
    modele = a.modele or modele_de_prod()
    if d['modele'] and d['modele'] != modele:
        raise SystemExit('REFUS : le rapport cumule le modele %r, on en '
                         'mesure %r. Deux modeles dans une meme courbe ne '
                         'racontent rien. Relance avec --reset.'
                         % (d['modele'], modele))
    d['modele'] = modele
    if not d['debut']:
        d['debut'] = time.strftime('%Y-%m-%d %H:%M:%S')

    if a.resume_seul:
        for l in resume(d):
            print(l)
        return 0

    deja = {p['cle'] for p in d['photos']}
    charge_avant = sum(p['s'] for p in d['photos'])
    print('modele : %s   budget : %d s   charge deja cumulee : %.0f s'
          % (modele, a.budget_s, charge_avant))
    lot = photos_de_la_base(a.base, 400, deja)
    if not lot:
        raise SystemExit('aucune photo neuve dans la base : rien a mesurer.')

    t0 = time.time()
    n = ko = 0

    # La sonde tourne dans un FIL, pas entre deux photos. Premiere version :
    # elle relevait apres chaque reponse d Ollama, donc pendant le seul instant
    # ou le GPU se repose -- elle rendait 20-40 % d utilisation et 500 MHz sur
    # 2100 alors que la carte venait de travailler a fond. La temperature s en
    # moquait (la chaleur met des minutes a redescendre), mais l horloge et le
    # bridage, non : c est EXACTEMENT ce qu on cherche, et on le mesurait au
    # mauvais moment. Un fil separe echantillonne PENDANT la generation.
    arret = threading.Event()

    def veilleuse():
        while not arret.wait(a.pause_releve):
            g = sonde()
            if not g:
                continue
            g['charge_s'] = round(charge_avant + time.time() - t0, 1)
            g['quand'] = round(time.time(), 1)
            d['releves'].append(g)
            print('   GPU %s C  %s%%  %s/%s MHz  %s W%s'
                  % (g['temp_c'], g['util'], g['mhz'], g['mhz_max'],
                     g['watts'], '  BRIDAGE THERMIQUE' if g['bride'] else ''),
                  flush=True)

    fil = threading.Thread(target=veilleuse, daemon=True)
    fil.start()
    for cle, e in lot:
        if time.time() - t0 >= a.budget_s:
            break
        chemin = Path(cle)
        if not chemin.exists():
            continue
        try:
            b64 = image_b64(chemin)
        except Exception as ex:
            ko += 1
            print('  ! image illisible (%s) : %s' % (str(ex)[:60], chemin.name))
            continue
        t1 = time.time()
        try:
            tagger(modele, b64, prompt_de_prod(e))
        except Exception as ex:
            ko += 1
            print('  ! Ollama : %s' % str(ex)[:80])
            time.sleep(2)
            continue
        s = time.time() - t1
        n += 1
        d['photos'].append({'cle': cle, 's': round(s, 2),
                            'quand': round(time.time(), 1)})
        print('  %5.1f s  %s' % (s, chemin.name[:40]), flush=True)
    arret.set()
    fil.join(timeout=a.pause_releve + 6)
    d['tranches'].append({'quand': time.strftime('%Y-%m-%d %H:%M:%S'),
                          'budget_s': a.budget_s, 'photos': n, 'echecs': ko,
                          'duree_s': round(time.time() - t0, 1)})
    ecrire_rapport(rapport, d)
    print('-' * 66)
    for l in resume(d):
        print(l)
    print('rapport cumule : %s' % a.rapport)
    return 0


if __name__ == '__main__':
    sys.exit(main())
