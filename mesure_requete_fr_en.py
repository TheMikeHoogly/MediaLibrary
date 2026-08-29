#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — la recherche IA comprend-elle le FRANCAIS aussi bien que l'anglais ?
(ROADMAP 1 nonies : « ameliorer l'intelligence de la recherche IA »)

SigLIP 2 a surtout lu de l'anglais. Avant de coder une traduction ou un
elargissement de requete, mesurer : pour un meme concept, la requete
francaise retrouve-t-elle autant de photos que l'anglaise ?

VERITE TERRAIN SANS RIEN ANNOTER : le tagueur ecrit pour chaque photo des
mots-cles en francais ET en anglais (`kw_fr`, `kw_en`). Une paire (fr, en) qui
co-occurre massivement — « peinture »/« painting », « ours en peluche »/
« teddy bear » — nomme le meme concept ; les photos qui portent l'un OU
l'autre sont la verite pour ce concept. C'est une verite « soufflee » par le
tagueur (un autre regard que SigLIP, ce qui est le point : deux regards
independants, cf. eval/DECISIONS.md 20/08).

CE QU'ON MESURE, par paire, avec les vecteurs de la COPIE de la base et le
texte encode ici (CPU, jamais la VRAM du serveur) :
    rappel@K de   fr        (la requete telle que l'utilisateur la tape)
                  en        (la traduction ideale)
                  fr + en   (l'elargissement : les deux, moyenne des vecteurs)
                  gabarit   (« une photo de <fr> », le prompt zero-shot)
K = le plafond de page (1 500) et K = 200 (ce que /api/search rend d'abord).

Lecture seule ; ecrit docs/requete_fr_en.json. Sortie ASCII.

    mesure_requete_fr_en.py --base copie.db [--paires 40] [--min 40]
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))
RAPPORT = RACINE / 'docs' / 'requete_fr_en.json'
STOP = {'personne:', 'animal:', 'espece:'}


def asc(s):
    return str(s).encode('ascii', 'replace').decode('ascii')


def charger(base):
    import sqlite3
    if Path(base).name == 'photos.db':
        print('REFUS : une COPIE (mesure_copie_base.py), jamais photos.db'); sys.exit(2)
    cx = sqlite3.connect('file:%s?mode=ro' % Path(base).resolve().as_posix(), uri=True)
    tags = {}
    for k, v in cx.execute('SELECT k, v FROM tags'):
        try:
            e = json.loads(v)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(e, dict) and not e.get('failed'):
            fr = [t.lower() for t in (e.get('kw_fr') or []) if isinstance(t, str) and ':' not in t]
            en = [t.lower() for t in (e.get('kw_en') or []) if isinstance(t, str) and ':' not in t]
            if fr or en:
                tags[k] = (set(fr), set(en))
    return cx, tags


def paires(tags, n, minimum):
    """Les paires (fr, en) les plus sures : `en` est le mot anglais qui
    co-occurre le plus avec `fr`, ET reciproquement, et fr != en (un mot
    identique dans les deux langues ne mesure rien)."""
    co = defaultdict(Counter)
    oc = defaultdict(Counter)
    nfr, nen = Counter(), Counter()
    for fr, en in tags.values():
        for f in fr:
            nfr[f] += 1
            for e in en:
                co[f][e] += 1
        for e in en:
            nen[e] += 1
            for f in fr:
                oc[e][f] += 1
    out = []
    for f, c in nfr.most_common():
        if c < minimum or not co[f]:
            continue
        e, ce = co[f].most_common(1)[0]
        if e == f or oc[e].most_common(1)[0][0] != f:
            continue
        # la paire doit etre serree : l'un accompagne l'autre dans >= 60 % des cas
        if ce < 0.6 * min(nfr[f], nen[e]):
            continue
        out.append((f, e, nfr[f], nen[e], ce))
        if len(out) >= n:
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--paires', type=int, default=40)
    ap.add_argument('--min', type=int, default=40, help='occurrences minimales du mot francais')
    a = ap.parse_args(argv)
    log = lambda m: print(asc(m), flush=True)  # noqa: E731
    t0 = time.time()
    cx, tags = charger(a.base)
    P = paires(tags, a.paires, a.min)
    log('index : %d photos taguees ; %d paires fr/en retenues' % (len(tags), len(P)))
    if not P:
        return 2

    import numpy as np
    import semantic
    from vectors import VectorStore
    modele, _, _, device = semantic.encodeur(forcer_device='cpu')
    if modele is None:
        log('SigLIP absent : ' + str(semantic._ETAT.get('erreur'))); return 2
    vs = VectorStore(cx)
    cles, M = vs.matrice(semantic.KIND)
    pos = {k: i for i, k in enumerate(cles)}
    log('vecteurs : %d photos, encodeur sur %s (%.0f s)' % (len(cles), device, time.time() - t0))

    K1, K2 = 200, 1500
    resultats, somme = [], defaultdict(float)
    for f, e, nf, ne, ce in P:
        verite = {k for k, (fr, en) in tags.items() if (f in fr or e in en) and k in pos}
        if not verite:
            continue
        formes = {'fr': [f], 'en': [e], 'fr+en': [f, e], 'gabarit': [semantic.GABARIT.format(f)]}
        ligne = {'fr': f, 'en': e, 'verite': len(verite), 'n_fr': nf, 'n_en': ne, 'co': ce}
        for nom, textes in formes.items():
            V = semantic.encoder_textes(textes)
            q = V.mean(axis=0)
            q = q / (np.linalg.norm(q) or 1.0)
            s = M @ q
            ordre = np.argsort(-s)
            top1 = {cles[i] for i in ordre[:K1]}
            top2 = {cles[i] for i in ordre[:K2]}
            r1 = len(top1 & verite) / min(len(verite), K1)
            r2 = len(top2 & verite) / min(len(verite), K2)
            p1 = len(top1 & verite) / K1
            ligne[nom] = {'rappel200': round(r1, 3), 'rappel1500': round(r2, 3), 'precision200': round(p1, 3)}
            somme[nom + ':r200'] += r1
            somme[nom + ':r1500'] += r2
            somme[nom + ':p200'] += p1
        resultats.append(ligne)
        log('  %-28s %-24s verite %5d | fr r200 %.2f  en %.2f  fr+en %.2f  gabarit %.2f' % (
            f[:28], e[:24], len(verite), ligne['fr']['rappel200'], ligne['en']['rappel200'],
            ligne['fr+en']['rappel200'], ligne['gabarit']['rappel200']))
    n = len(resultats)
    moy = {k: round(v / n, 3) for k, v in somme.items()}
    lignes = ['REQUETE FR / EN sur %d paires (verite = tags du tagueur, fr OU en) :' % n]
    for nom in ('fr', 'en', 'fr+en', 'gabarit'):
        lignes.append('  %-8s rappel@200 %.3f   rappel@1500 %.3f   precision@200 %.3f' % (
            nom, moy[nom + ':r200'], moy[nom + ':r1500'], moy[nom + ':p200']))
    gagne = sum(1 for r in resultats if r['en']['rappel200'] > r['fr']['rappel200'])
    elargi = sum(1 for r in resultats if r['fr+en']['rappel200'] > r['fr']['rappel200'])
    lignes.append('  l anglais bat le francais sur %d/%d paires ; fr+en bat fr sur %d/%d' % (gagne, n, elargi, n))
    RAPPORT.parent.mkdir(exist_ok=True)
    RAPPORT.write_text(json.dumps({'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'), 'base': a.base,
                                   'K': [K1, K2], 'moyennes': moy, 'resume': lignes, 'paires': resultats},
                                  ensure_ascii=False, indent=1), encoding='utf-8')
    for l in lignes:
        log(l)
    log('rapport : docs/requete_fr_en.json (%.0f s)' % (time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
