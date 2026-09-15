#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le TIRAGE EN AVEUGLE : deux modeles x deux prompts, sur les MEMES photos.

POURQUOI CE BANC EXISTE

`ROADMAP.md` § B exige, avant toute campagne : « mesure en aveugle sur un
tirage A/B -- **pas sur 8 photos choisies**, la faute nommee dans Pistes
ouvertes ». `mesure_modele_vision.py` compare deja deux modeles avec le prompt
de prod, mais il est concu pour « quelques cles precises, pas un tirage
aleatoire » : il repond donc a une autre question que celle qu'on pose ici.

Ce banc ajoute les trois choses qui manquaient :

  1. un TIRAGE reproductible -- graine fixee, cles GELEES dans
     `eval/tirage_aveugle.json` et reutilisees a l identique a chaque
     evaluation suivante. C'est l'etape 1 de la skill `vision-eval` : sans jeu
     fige, deux mesures faites a deux jours d'intervalle ne se comparent pas ;
  2. une seconde dimension, le PROMPT. Le prompt de prod exige deja des
     mots-cles generiques pour un document -- c'est ecrit dans `REGLES_JSON`,
     et c'est de la que viennent les 23 candidates du 14/09. La question de
     `ROADMAP.md` B3 n'est donc pas « faut-il en parler au modele » mais
     « **une question EXPLICITE trouve-t-elle ce que la consigne generique
     laisse passer ?** » ;
  3. la reprise. Chaque ligne est ecrite des qu'elle est produite, et un
     relancement saute ce qui est deja fait. L'agent banc coupe a 600 s ; une
     mesure de quarante minutes ne tient pas dans un appel, et une mesure qui
     recommence de zero a chaque coupure ne finit jamais.

CE QU IL MESURE, ET CE QU IL NE MESURE PAS

Sans etiquettes humaines, la JUSTESSE ne se mesure pas ici -- et ce banc ne
pretend pas la mesurer. Il produit ce qui se compte sans jugement : secondes
par photo, taux de sortie MALFORMEE (le modele n'a pas rendu le JSON demande),
nombre de mots-cles, et le signal « document sensible » de chaque bras. La
justesse se tranchera sur une page de preference EN AVEUGLE, alimentee par ce
meme fichier -- deux listes de mots-cles pour la meme photo, sans dire laquelle
vient de qui.

LECTURE SEULE : lit une COPIE de la base, lit les photos, appelle Ollama en
local. N'ecrit que son tirage et son journal de resultats.

USAGE
    python mesure_tirage_aveugle.py --n 60 --minutes 8
    python mesure_tirage_aveugle.py --etat
"""

import argparse
import base64
import io
import json
import os
import random
import sqlite3
import sys
import time
from pathlib import Path, PureWindowsPath

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import tagging_meta                                             # noqa: E402
import mesure_modele_vision as MV                               # noqa: E402

TIRAGE = ICI / 'eval' / 'tirage_aveugle.json'
JOURNAL = ICI / 'docs' / 'tirage_aveugle.jsonl'

# Les deux bras de MODELE. Le second n'est pas un challenger neuf : c'est
# l'ANCIEN modele de prod. Il repond a une question que `ROADMAP.md` B1
# declarait perdue faute d'instantane d'avant -- « ce que la campagne du 05/09
# a change ». Un challenger neuf se branche ici, sur le MEME tirage, le jour
# ou Mike en choisit un a tirer.
MODELES = ('qwen3.5:4b', 'qwen3-vl:2b')

# Les deux bras de PROMPT. `prod` est le prompt en place, mot pour mot.
PROMPTS = ('prod', 'sensible')

# La QUESTION explicite, ajoutee au prompt de prod et a rien d'autre : un
# champ de plus dans le JSON demande. Elle ne remplace pas la consigne
# generique de `REGLES_JSON`, elle s'y ajoute -- c'est l'ECART entre les deux
# qu'on mesure, pas un prompt concurrent.
QUESTION_SENSIBLE = (
    '\n\nAjoute aussi au JSON un champ "document_personnel" : true si la '
    'photo montre un document qui appartient a la vie privee de quelqu un '
    '- piece d identite, carte bancaire, releve, facture nominative, '
    'ordonnance ou document medical, bulletin de salaire, courrier '
    'administratif - false sinon. Ne transcris JAMAIS son contenu.')


def prompt_de(nom, assertions):
    base = tagging_meta.prompt_tagging(assertions)
    if nom == 'sensible':
        return base + QUESTION_SENSIBLE
    return base


def population(base):
    """Les cles IMAGES de la base, hors abimees. Les videos n'ont pas de
    tagueur ; une entree `failed` n'a pas d'image lisible."""
    cx = sqlite3.connect('file:%s?mode=ro&immutable=1' % Path(base).as_posix(),
                         uri=True)
    try:
        out = []
        for k, v in cx.execute('SELECT k, v FROM tags'):
            try:
                e = json.loads(v)
            except ValueError:
                continue
            if e.get('video') or e.get('failed'):
                continue
            if PureWindowsPath(k).suffix.lower() not in IMAGE_EXT:
                continue
            out.append(k)
        return out
    finally:
        cx.close()


IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.bmp',
             '.tiff', '.tif'}


def geler_tirage(base, n, graine, refaire=False):
    """Le jeu FIGE : tire une fois, relu ensuite a l identique.

    Un tirage refait a chaque lancement rendrait deux mesures incomparables --
    c'est l'etape 1 de `vision-eval`, et c'est la seule chose qui permette de
    rebrancher un troisieme modele dans six mois sur les MEMES photos."""
    if TIRAGE.exists() and not refaire:
        d = json.loads(TIRAGE.read_text(encoding='utf-8'))
        return d['cles'], d
    pop = population(base)
    r = random.Random(graine)
    cles = r.sample(pop, min(n, len(pop)))
    # Une cle dont le fichier a disparu fausserait le tirage en silence : on
    # la remplace ICI, une fois, et le tirage gele porte le remplacement.
    vivantes, ecartees = [], []
    for k in cles:
        (vivantes if os.path.exists(k) else ecartees).append(k)
    if ecartees:
        reste = [k for k in pop if k not in set(cles)]
        r.shuffle(reste)
        for k in reste:
            if len(vivantes) >= len(cles):
                break
            if os.path.exists(k):
                vivantes.append(k)
    d = {'genere_le': time.strftime('%Y-%m-%d %H:%M:%S'), 'graine': graine,
         'population': len(pop), 'n': len(vivantes),
         'ecartees_absentes': ecartees, 'cles': sorted(vivantes)}
    TIRAGE.parent.mkdir(exist_ok=True)
    TIRAGE.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                      encoding='utf-8')
    return d['cles'], d


def deja_faits():
    """{(cle, modele, prompt)} deja dans le journal. C'est la reprise."""
    faits = set()
    if not JOURNAL.exists():
        return faits
    with open(JOURNAL, 'r', encoding='utf-8') as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                d = json.loads(ligne)
            except ValueError:
                continue
            faits.add((d.get('cle'), d.get('modele'), d.get('prompt')))
    return faits


def etat(cles):
    faits = deja_faits()
    total = len(cles) * len(MODELES) * len(PROMPTS)
    print('tirage : %d photo(s) gelees' % len(cles))
    for m in MODELES:
        for p in PROMPTS:
            n = sum(1 for c in cles if (c, m, p) in faits)
            print('  %-14s %-9s %4d / %4d' % (m, p, n, len(cles)))
    print('TOTAL %d / %d' % (len(faits & {(c, m, p) for c in cles
                                          for m in MODELES
                                          for p in PROMPTS}), total))
    return faits, total


def bilan(cles):
    """Les chiffres du tirage, sans GPU et sans jugement.

    Ce que ce bilan NE FAIT PAS : dire quel modele tague MIEUX. Sans
    etiquettes humaines, « mieux » n'est pas une mesure -- ca se tranchera sur
    une page de preference en aveugle. Ici : la vitesse, le taux de sortie
    malformee, le volume de mots-cles, et le seul verdict que les deux bras
    de prompt permettent de comparer -- le signal « document personnel »."""
    import statistics
    import collections
    lignes = [json.loads(l) for l in
              open(JOURNAL, 'r', encoding='utf-8') if l.strip()]
    vus = {c for c in cles}
    lignes = [x for x in lignes if x['cle'] in vus]
    par = collections.defaultdict(list)
    for x in lignes:
        par[(x['modele'], x['prompt'])].append(x)

    print('=' * 70)
    print('TIRAGE EN AVEUGLE -- %d photos, %d lignes' % (len(cles), len(lignes)))
    print('=' * 70)
    print('%-14s %-9s %6s %8s %8s %7s' %
          ('modele', 'prompt', 'n', 'mediane', 'total', 'malf.'))
    for k in sorted(par):
        d = [x['duree_s'] for x in par[k]]
        print('%-14s %-9s %6d %7.1fs %7.0fs %7d'
              % (k[0], k[1], len(d), statistics.median(d), sum(d),
                 sum(1 for x in par[k] if x['malformee'])))

    print()
    print('MOTS-CLES par photo (mediane) et DESCRIPTION (mediane, caracteres)')
    for k in sorted(par):
        nk = [len(x['kw_fr']) + len(x['kw_en']) for x in par[k]]
        nd = [len(x['desc'] or '') for x in par[k]]
        print('  %-14s %-9s %4.0f mots-cles   %4.0f car.'
              % (k[0], k[1], statistics.median(nk), statistics.median(nd)))

    print()
    print('LE SIGNAL << DOCUMENT PERSONNEL >>')
    print('  filet actuel = `candidat_sensible` sur les mots-cles du bras prod')
    print('  question explicite = le champ rendu par le bras sensible')
    for m in MODELES:
        prod = {x['cle']: x for x in par.get((m, 'prod'), [])}
        sens = {x['cle']: x for x in par.get((m, 'sensible'), [])}
        filet = {k for k, x in prod.items()
                 if tagging_meta.candidat_sensible(
                     {'kw_fr': x['kw_fr'], 'kw_en': x['kw_en']})[0]}
        explicite = {k for k, x in sens.items() if x.get('document_personnel')}
        muet = sum(1 for x in sens.values()
                   if x.get('document_personnel') is None)
        print('  %-14s filet %d   explicite %d   '
              'explicite SEUL %d   filet SEUL %d   sans reponse %d'
              % (m, len(filet), len(explicite), len(explicite - filet),
                 len(filet - explicite), muet))

    a, b = MODELES[0], MODELES[1]
    ea = {x['cle'] for x in par.get((a, 'sensible'), [])
          if x.get('document_personnel')}
    eb = {x['cle'] for x in par.get((b, 'sensible'), [])
          if x.get('document_personnel')}
    print('  les DEUX modeles d accord sur : %d photo(s)' % len(ea & eb))
    print()
    print('CE QUE CE BILAN NE DIT PAS : lequel tague MIEUX. Sans etiquettes')
    print('humaines, << mieux >> n est pas une mesure -- page de preference.')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='copie.db')
    ap.add_argument('--n', type=int, default=60)
    ap.add_argument('--graine', type=int, default=20260915)
    ap.add_argument('--minutes', type=float, default=8.0,
                    help='budget de CET appel : l agent banc coupe a 600 s')
    ap.add_argument('--etat', action='store_true')
    ap.add_argument('--bilan', action='store_true',
                    help='lit le journal et rend les chiffres, sans GPU')
    ap.add_argument('--refaire-le-tirage', action='store_true')
    a = ap.parse_args(argv)

    base = ICI / a.base
    if base.name == 'photos.db':
        raise SystemExit('REFUS : une COPIE, jamais photos.db (regle 4).')
    cles, d = geler_tirage(base, a.n, a.graine, a.refaire_le_tirage)
    print('tirage gele le %s, graine %s, %d photo(s) sur %d'
          % (d['genere_le'], d['graine'], d['n'], d['population']))
    if a.etat:
        etat(cles)
        return 0
    if a.bilan:
        return bilan(cles)

    faits = deja_faits()
    # MODELE D ABORD, photo ensuite. Les 4 Go de VRAM ne tiennent pas deux
    # modeles : alterner a chaque photo fait DECHARGER et RECHARGER Ollama, et
    # le premier essai l'a paye -- 28,5 s, 16,7 s, 25,0 s la ou le modele de
    # prod est mesure a 11,3 s/photo. Un bras entier par modele : un
    # chargement au lieu de deux cent quarante, et des durees qui mesurent le
    # MODELE au lieu de mesurer le va-et-vient.
    reste = [(c, m, p) for m in MODELES for p in PROMPTS for c in cles
             if (c, m, p) not in faits]
    total = len(cles) * len(MODELES) * len(PROMPTS)
    print('a faire : %d / %d' % (len(reste), total))
    if not reste:
        print('VERDICT : le tirage est COMPLET. Lis docs/tirage_aveugle.jsonl')
        return 0

    cx = sqlite3.connect('file:%s?mode=ro&immutable=1' % base.as_posix(),
                         uri=True)
    fin = time.time() + a.minutes * 60
    n_ok = n_mal = 0
    JOURNAL.parent.mkdir(exist_ok=True)
    with open(JOURNAL, 'a', encoding='utf-8') as jf:
        for cle, modele, pr in reste:
            if time.time() > fin:
                print('budget de %g min atteint : on s arrete proprement.'
                      % a.minutes)
                break
            row = cx.execute('SELECT v FROM tags WHERE k = ?',
                             (cle,)).fetchone()
            if row is None:
                continue
            e = json.loads(row[0])
            prompt = prompt_de(pr, MV.assertions_pour(e))
            t0 = time.time()
            brut = ''
            try:
                b64 = MV.image_b64(cle)
                brut = MV.ollama_generate(modele, b64, prompt)
                kw_fr, kw_en, desc = MV.parse_tags(brut)
            except Exception as exc:                            # noqa: BLE001
                kw_fr, kw_en, desc = [], [], ''
                print('  ! %s %s %s : %s' % (modele, pr,
                                             PureWindowsPath(cle).name,
                                             str(exc)[:70]))
            # MALFORMEE : le modele n'a pas rendu le JSON demande. C'est une
            # metrique a part entiere -- un encodeur ne peut pas en produire,
            # un VLM generatif si, et `_salvage_tags` existe pour ca.
            malformee = not (kw_fr or kw_en or desc)
            sensible = None
            if pr == 'sensible':
                try:
                    sensible = bool(json.loads(brut).get('document_personnel'))
                except Exception:                               # noqa: BLE001
                    sensible = None
            jf.write(json.dumps({
                'cle': cle, 'modele': modele, 'prompt': pr,
                'kw_fr': kw_fr, 'kw_en': kw_en, 'desc': desc,
                'document_personnel': sensible,
                'malformee': malformee,
                'duree_s': round(time.time() - t0, 1),
                'at': time.time()}, ensure_ascii=False) + '\n')
            jf.flush()
            n_ok += 1
            n_mal += 1 if malformee else 0
            print('%-14s %-9s %5.1fs %s%s'
                  % (modele, pr, time.time() - t0,
                     PureWindowsPath(cle).name[:34],
                     '  MALFORMEE' if malformee else ''))
    cx.close()
    print()
    print('CET APPEL : %d ligne(s), %d malformee(s)' % (n_ok, n_mal))
    etat(cles)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
