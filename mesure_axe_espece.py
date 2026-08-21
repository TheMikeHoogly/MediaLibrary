#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — que rendrait le jeton `espece:`, et surtout qu'AJOUTE-t-il ?
──────────────────────────────────────────────────────────────────────────────

LA QUESTION, ET POURQUOI CE N'EST PAS CELLE DU 20/08

Le 20/08, `mesure_espece_recherche.py` a demandé : « SigLIP retrouve-t-il ce
que YOLO a vu ? » Réponse : la moitié. Puis la CONCORDANCE YOLO ∧ tagueur a
été retenue comme matière du 5ᵉ axe (forme A, choix de Mike).

Ce banc-ci pose la question suivante, la seule qui décide du câblage :
**qu'est-ce que le jeton AJOUTE à ce qu'un humain obtient déjà en tapant le
mot ?** Un axe qui ressort ce que la page montre déjà coûte un jeton, une
ligne d'explication, du code dans le routeur — et ne rend rien.

  AJOUT(espèce) = CONCORDANCE \\ (ce que `q=<mot>` rend aujourd'hui)

Le reste du rapport sert à ne pas lire ce chiffre de travers : de quoi est
faite la concordance, ce que le mot rend AUJOURD'HUI et que le jeton ne
rendrait pas, et le sort des photos que le filtre déterministe n'atteint pas.

LA RÈGLE DE CONCORDANCE EST ICI, PAS DANS UN SOUVENIR

Les chiffres du 20/08 (chat 2 316, 3 065 en tout) ont été produits par un
calcul qui n'a jamais été mis en code : seuls leurs RÉSULTATS sont écrits dans
`eval/DECISIONS.md`. Ce banc écrit la règle noir sur blanc — deux regards
indépendants disent la même espèce :

  * YOLO  : une détection de l'espèce dans `animals` (le `det_score` n'entre
    PAS : le 20/08 a montré qu'il dit « il y a un animal », jamais laquelle) ;
  * tagueur : le mot français, en MOT ENTIER, dans `kw_fr` ou dans `desc`.

Et il affiche l'écart avec les nombres publiés au lieu de le taire. Un chiffre
qu'on ne sait pas reproduire n'est pas une mesure (`eval/METHODE.md`) : soit
la règle d'aujourd'hui est meilleure et l'écart s'explique, soit elle diffère
et il faut le savoir AVANT de graver un axe dessus.

Les 82 photos taguées DEPUIS l'injection des faits dans le prompt sont
écartées de la concordance : on leur a soufflé l'espèce détectée, leur accord
avec YOLO ne prouve rien (`pipe` non vide).

DEUX RÈGLES, PAS UNE — parce que « poney » est un cheval

La règle STRICTE ne connaît que le mot et son pluriel. La règle ÉLARGIE ajoute
les mots qu'un humain emploierait pour la même bête (poney, brebis, chaton,
veau…). Les deux sont mesurées côte à côte : élargir gagne du rappel et peut
coûter de la précision, et ce n'est pas à un principe de trancher.

CE QU'IL NE FAIT PAS

Aucun `UPDATE`, aucun accès NAS, aucun modèle chargé. Lecture seule sur une
COPIE (`mesure_copie_base.py` la fabrique). Le seul appel réseau est
`GET /api/search` sur le serveur LOCAL — c'est lui qui détient SigLIP, et
l'INTERROGER est plus honnête que de recopier son pipeline.

FUSEAU HORAIRE : sans objet, aucune date n'est lue.

USAGE
    python mesure_axe_espece.py --base copie.db
    python mesure_axe_espece.py --base copie.db --exemples 8 --json r.json
"""

import argparse
import json
import random
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import faits_vue
import mesure_faits_vue as MFV

# Le vocabulaire et la règle STRICTE viennent de `faits_vue` — le banc IMPORTE
# la prod, il ne la recopie pas (`eval/METHODE.md`, 14/08). C'est ce qui rend
# ce banc capable de mesurer ce que le FILTRE fera vraiment : une copie de la
# règle mesurerait un cousin du filtre, jamais le filtre.
MOTS = faits_vue.ESPECES_MOTS
STRICTES = faits_vue.ESPECES_FORMES

# Formes ÉLARGIES : ce qu'un humain écrit pour la MÊME bête. Le petit
# (chaton, agneau) et la variété (poney) comptent ; le genre aussi (jument).
ELARGIES = {
    'chat': ('chaton', 'chatons', 'chatte', 'chattes'),
    'chien': ('chiot', 'chiots', 'chienne', 'chiennes'),
    'oiseau': ('oisillon', 'oisillons'),
    'vache': ('bovin', 'bovins', 'taureau', 'taureaux', 'veau', 'veaux',
              'genisse', 'genisses'),
    'cheval': ('chevaux', 'poney', 'poneys', 'jument', 'juments',
               'poulain', 'poulains'),
    'mouton': ('moutons', 'brebis', 'agneau', 'agneaux', 'belier', 'beliers'),
}

# Ce que le 20/08 a publié — pour AFFICHER l'écart, jamais pour s'y aligner.
PUBLIE_20_08 = {'chat': 2316, 'chien': 356, 'oiseau': 195, 'cheval': 114,
                'mouton': 61, 'vache': 43}
PUBLIE_UNION = 3065

API = 'http://127.0.0.1:8080/api/search'
PLAFOND_PAGE = 1500          # `/files?q=` et `/api/search?n=` s'arrêtent là

_SPLIT = re.compile(r'[^a-z0-9]+')


def norm(s):
    """Minuscules sans accents — la recherche compare ainsi partout."""
    s = unicodedata.normalize('NFD', str(s).lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def mots_de(entree):
    """Mots ENTIERS dits par le tagueur : `kw_fr` et `desc`, découpés.

    Mot entier et non sous-chaîne : « chat » ne doit pas sortir de
    « château » — la leçon du 19/08 sur « Ins » dans « Cousins »."""
    fr = set()
    for m in (entree.get('kw_fr') or []):
        fr |= set(_SPLIT.split(norm(m)))
    de = set(_SPLIT.split(norm(entree.get('desc') or '')))
    return fr - {''}, de - {''}


def formes(mot, elargie=False):
    """Les mots qui, sous la plume du tagueur, désignent CETTE espèce."""
    f = set(STRICTES[mot])
    return f | set(ELARGIES[mot]) if elargie else f


def dit_l_espece(entree, mot, elargie=False):
    """(dans kw_fr, dans desc) — le tagueur dit-il l'espèce, en MOT ENTIER ?

    La règle STRICTE est celle de la PROD (`faits_vue.dit_l_espece`) : le banc
    l'appelle au lieu de la refaire, sinon il mesurerait un cousin du filtre.
    La règle ÉLARGIE, elle, n'existe que dans ce banc — c'est la variante
    qu'il sert à juger, et elle a été rejetée le 21/08 (+43 photos sur 3 134).

    Deux sources séparées parce qu'on veut SAVOIR laquelle porte la
    concordance : si `desc` la portait seule, la règle dépendrait d'un texte
    libre plutôt que de mots-clés, et ce serait à dire avant de graver."""
    if not elargie:
        return faits_vue.dit_l_espece(entree, mot)
    fr, de = mots_de(entree)
    f = formes(mot, elargie)
    return bool(f & fr), bool(f & de)


def interroger(mot, api=API, n=PLAFOND_PAGE):
    """Clés rendues par le serveur VIVANT pour `q=<mot>`, dans l'ordre."""
    url = f"{api}?q={urllib.parse.quote(mot)}&n={n}"
    try:
        with urllib.request.urlopen(url, timeout=180) as r:
            d = json.loads(r.read().decode('utf-8'))
    except Exception as e:                                    # noqa: BLE001
        raise SystemExit(
            f"Le serveur ne répond pas ({e}). Il détient SigLIP : sans lui ce "
            "banc ne mesure rien. Lancer « 0 - Démarrer le serveur.bat ».")
    return ([x['key'] for x in d.get('results', [])],
            d.get('noms') or [], d.get('lieux') or [])


def lire_le_fonds(base, projet):
    """Un seul passage sur l'index. Rend ce dont tout le reste dépend."""
    cx = MFV.ouvrir(base)
    esp = MFV.especes_par_cle(cx)
    gps = {}
    try:
        g = json.loads((Path(projet) / 'gps_places.json').read_text(encoding='utf-8'))
        gps = g if isinstance(g, dict) else {}
    except (OSError, ValueError):
        pass
    lieux = MFV.load_lieux(Path(projet) / 'lieux.txt')
    racines = MFV.racines_media(projet)
    attribues, exclus, _ = MFV.autorite_des_noms(cx)

    fonds = {}
    yolo = defaultdict(set)
    dit = {'stricte': defaultdict(set), 'elargie': defaultdict(set)}
    ou = defaultdict(lambda: [0, 0, 0])     # espèce → [kw_fr seul, desc seul, deux]
    pipes = set()
    n_lues = 0

    for cle, v in cx.execute('SELECT k, v FROM tags'):
        e = MFV.lire_json(v)
        if not isinstance(e, dict) or e.get('failed'):
            continue
        n_lues += 1
        na = MFV.noms_attendus(cle, e, attribues, exclus)
        a = faits_vue.assertions(cle, e, especes=esp.get(cle),
                                 gps_place=gps.get(cle), lieux=lieux,
                                 racines=racines, noms_attendus=na)
        fonds[cle] = (bool(a['persons'] or a['animals']), bool(a['lieu']),
                      bool(a['species']))
        if e.get('pipe'):
            pipes.add(cle)
        for s in (esp.get(cle) or ()):
            yolo[s].add(cle)

        for esp_coco, mot in MOTS.items():
            in_fr, in_de = dit_l_espece(e, mot)
            if in_fr or in_de:
                dit['stricte'][esp_coco].add(cle)
                ou[mot][0 if (in_fr and not in_de) else
                        (1 if (in_de and not in_fr) else 2)] += 1
            if any(dit_l_espece(e, mot, elargie=True)):
                dit['elargie'][esp_coco].add(cle)
    cx.close()
    return fonds, yolo, dit, ou, pipes, n_lues


def mesurer(base, projet, exemples, graine, api=API):
    t0 = time.perf_counter()
    fonds, yolo, dit, ou, pipes, n_lues = lire_le_fonds(base, projet)
    rnd = random.Random(graine)
    t_lecture = round(time.perf_counter() - t0, 1)

    # Les populations du filtre déterministe (rappel du 20/08 : 30 122 / 2 186).
    non_date = {k for k, (n, l, s) in fonds.items() if n or l or s}
    atteintes = {k for k in non_date if fonds[k][0] or fonds[k][1]}
    espece_seule = non_date - atteintes

    rap = {'base': str(base), 'photos_lues': n_lues, 'lecture_s': t_lecture,
           'taguees_avec_les_faits': len(pipes),
           'fait_non_date': len(non_date),
           'atteintes_nom_ou_lieu': len(atteintes),
           'espece_seule': len(espece_seule),
           'especes': [], 'regle': {}}

    union = {'stricte': set(), 'elargie': set()}
    rendus_tous = set()
    for esp_coco, mot in sorted(MOTS.items(), key=lambda x: -len(yolo.get(x[0], ()))):
        rendus, noms, lieux_pris = interroger(mot, api)
        S = set(rendus)
        rendus_tous |= S
        Y = yolo.get(esp_coco, set())
        ligne = {'espece': esp_coco, 'mot': mot,
                 'yolo': len(Y), 'rendus_par_le_mot': len(rendus),
                 'mot_mange_par': {'noms': noms, 'lieux': lieux_pris},
                 'ou_le_tagueur_le_dit': ou[mot], 'variantes': {}}
        for regle in ('stricte', 'elargie'):
            T = dit[regle].get(esp_coco, set())
            C = (Y & T) - pipes
            union[regle] |= C
            ajout = C - S
            ligne['variantes'][regle] = {
                'tagueur': len(T - pipes),
                'concordance': len(C),
                'deja_rendu': len(C & S),
                'ajout': len(ajout),
                'tagueur_seul': len(T - pipes - Y),
                'yolo_seul': len(Y - pipes - T),
                'ajout_espece_seule': len(ajout & espece_seule),
                'rendu_hors_concordance': len(S - C),
            }
            if regle == 'stricte':
                ech = rnd.sample(sorted(ajout), min(exemples, len(ajout)))
                ligne['exemples_ajout'] = ech
                ligne['exemples_hors'] = rnd.sample(
                    sorted(S - C), min(exemples, len(S - C)))
        ligne['publie_20_08'] = PUBLIE_20_08.get(mot)
        rap['especes'].append(ligne)

    for regle in ('stricte', 'elargie'):
        U = union[regle]
        rap['regle'][regle] = {
            'union': len(U),
            'ajout': len(U - rendus_tous),
            'espece_seule_atteinte': len(U & espece_seule),
            'espece_seule_atteinte_par_le_seul_jeton':
                len((U & espece_seule) - rendus_tous),
        }
    rap['publie_20_08_union'] = PUBLIE_UNION
    rap['duree_s'] = round(time.perf_counter() - t0, 1)
    return rap


def afficher(rap):
    L = []
    A = L.append
    A("=" * 78)
    A("  QUE RENDRAIT LE JETON `espece:` — ET QU'AJOUTE-T-IL ?")
    A("=" * 78)
    A(f"Base {rap['base']} — {rap['photos_lues']} photos lues en "
      f"{rap['lecture_s']} s ; {rap['taguees_avec_les_faits']} taguées AVEC "
      "les faits, écartées de la concordance (elles récitent).")
    A("")
    A("-- LA MATIÈRE, ET L'ÉCART AVEC LE 20/08 ------------------------------")
    A("%-8s %7s %8s %8s %8s %9s" %
      ('mot', 'yolo', 'tagueur', 'CONCORD', 'publié', 'écart'))
    for e in rap['especes']:
        s = e['variantes']['stricte']
        p = e['publie_20_08']
        A("%-8s %7d %8d %8d %8s %9s" %
          (e['mot'], e['yolo'], s['tagueur'], s['concordance'],
           p if p else '-', ('%+d' % (s['concordance'] - p)) if p else '-'))
    r = rap['regle']
    A("%-8s %7s %8s %8d %8d %9s" %
      ('UNION', '', '', r['stricte']['union'], rap['publie_20_08_union'],
       '%+d' % (r['stricte']['union'] - rap['publie_20_08_union'])))
    A("  (union = PHOTOS ; une photo qui porte deux espèces n'est comptée")
    A("   qu'une fois — d'où une union plus petite que la somme des lignes.)")
    A("")
    A("-- CE QUE LE JETON AJOUTE À CE QU'ON OBTIENT DÉJÀ EN TAPANT LE MOT ---")
    A("%-8s %8s %9s %9s %8s %10s" %
      ('mot', 'concord', 'deja vu', 'AJOUT', '%', 'hors conc.'))
    for e in rap['especes']:
        s = e['variantes']['stricte']
        pct = 100.0 * s['ajout'] / max(1, s['concordance'])
        A("%-8s %8d %9d %9d %7.1f %% %10d" %
          (e['mot'], s['concordance'], s['deja_rendu'], s['ajout'], pct,
           s['rendu_hors_concordance']))
        mm = e['mot_mange_par']
        if mm['noms'] or mm['lieux']:
            A("        ATTENTION : le mot a été pris pour un nom/lieu "
              f"{mm} — ce que rend `q={e['mot']}` n'est pas SigLIP seul.")
    A(f"  UNION : le jeton sortirait {r['stricte']['union']} photos, dont "
      f"**{r['stricte']['ajout']}** qu'aucun des six mots ne rend aujourd'hui.")
    A("")
    A("-- LES PHOTOS QUE LE FILTRE DÉTERMINISTE N'ATTEINT PAS ---------------")
    A(f"  fait NON-date : {rap['fait_non_date']} — nom ou lieu en atteint "
      f"{rap['atteintes_nom_ou_lieu']}, il reste "
      f"{rap['espece_seule']} photos à ESPÈCE SEULE.")
    A(f"  le jeton en atteint {r['stricte']['espece_seule_atteinte']}, dont "
      f"**{r['stricte']['espece_seule_atteinte_par_le_seul_jeton']}** que rien "
      "d'autre ne sort aujourd'hui.")
    A("")
    A("-- STRICTE (mot + pluriel) CONTRE ÉLARGIE (poney, brebis, chaton…) ---")
    A("%-8s %10s %8s %10s %8s" %
      ('mot', 'concord.S', 'ajout.S', 'concord.E', 'ajout.E'))
    for e in rap['especes']:
        s, g = e['variantes']['stricte'], e['variantes']['elargie']
        A("%-8s %10d %8d %10d %8d" %
          (e['mot'], s['concordance'], s['ajout'], g['concordance'], g['ajout']))
    A("%-8s %10d %8d %10d %8d" %
      ('UNION', r['stricte']['union'], r['stricte']['ajout'],
       r['elargie']['union'], r['elargie']['ajout']))
    A("")
    A("-- OÙ LE TAGUEUR DIT L'ESPÈCE (kw_fr seul / desc seul / les deux) ----")
    for e in rap['especes']:
        A("  %-8s %s" % (e['mot'], e['ou_le_tagueur_le_dit']))
    A("")
    A("-- À REGARDER, PAS À CROIRE ------------------------------------------")
    for e in rap['especes']:
        A(f"  {e['mot']} — l'AJOUT (le jeton les sort, `q={e['mot']}` non) :")
        for k in e['exemples_ajout']:
            A("      + %s" % k[-70:])
        A(f"  {e['mot']} — rendus par le mot HORS concordance "
          "(le jeton ne les sortirait pas) :")
        for k in e['exemples_hors']:
            A("      - %s" % k[-70:])
    A("=" * 78)
    A(f"Durée totale : {rap['duree_s']} s")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--base', required=True, help="COPIE de photos.db")
    ap.add_argument('--projet', default='.')
    ap.add_argument('--exemples', type=int, default=6)
    ap.add_argument('--graine', type=int, default=20260821)
    ap.add_argument('--api', default=API)
    ap.add_argument('--json', dest='sortie_json')
    a = ap.parse_args(argv)
    rap = mesurer(a.base, a.projet, a.exemples, a.graine, a.api)
    print(afficher(rap))
    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(rap, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\nJSON : {a.sortie_json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
