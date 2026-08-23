#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification — l'écart entre l'index et les FICHIERS, sur TOUS les noms
──────────────────────────────────────────────────────────────────────────────

POURQUOI CE BANC EXISTE

`verifier_xmp_personnes.py` répond pour UN nom. Le 23/08 il a répondu trois
fois, et les trois réponses ne racontaient pas la même histoire :

    Ellie    342 photos → 54 dont le fichier ne porte pas le nom (15,8 %)
    Mike     200 tirées → 37                                     (18,5 %)
    Florine  200 tirées →  0
    Stéphane Plouvin 58 →  0

Les deux noms sans écart sont exactement les deux dont les fichiers ont été
RÉÉCRITS en entier (la fusion Flo → Florine, et un groupe nommé après que la
file XMP eut un journal). Ce qui s'accumule geste par geste fuyait ; ce qui est
réécrit d'un bloc, non. Trois noms ne font pas un fonds : ce banc compte sur
TOUS, pour que la réparation parte d'un chiffre et non d'une extrapolation.

CE QU'IL NE FAIT PAS

Il n'écrit rien : famille `verifier_`, lecture seule. Il n'ouvre jamais
`photos.db` — la vérité d'index est DEMANDÉE au serveur en HTTP. Réparer est un
geste de Mike (`appliquer_xmp_personnes.py`).

CE QU'IL DIT DE SES PROPRES LIMITES

Lire 36 000 fichiers sur SMB prend des heures, et le canal des bancs coupe à
600 s. Ce banc ÉCHANTILLONNE donc, et il le DIT — combien de noms sont comptés
EXACTEMENT (ceux dont toutes les photos tiennent dans la part), combien sont
ESTIMÉS, et combien de couples nom–photo n'ont pas été lus. Un plafond muet se
lit comme une exhaustivité : c'est la leçon de `/api/people/photos`, payée deux
fois le 23/08.

USAGE
    python verifier_xmp_toutes_personnes.py
    python verifier_xmp_toutes_personnes.py --par-nom 12 --budget 3000
    python verifier_xmp_toutes_personnes.py --json _xmp_fonds.json
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_xmp_personnes as V          # noqa: E402


def noms_du_serveur(serveur, timeout=60):
    """Tous les noms de PERSONNES et leur compte d'index (`/api/names`).

    La route rend `{"noms": [...]}`. Les autres clés sont acceptées par
    tolérance, mais une réponse dont on ne tire AUCUN nom lève : ce banc a
    d'abord été écrit sur la mauvaise clé (`names`) et il a rendu, sans
    broncher, « 0 nom, 0 écart, 0 à réparer » — le pire rapport possible,
    puisqu'il ressemble trait pour trait à une bonne nouvelle."""
    url = serveur.rstrip('/') + '/api/names?genre=personne'
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = json.loads(r.read().decode('utf-8'))
    items = (data if isinstance(data, list)
             else (data.get('noms') or data.get('names') or []))
    out = []
    for it in items:
        nom = (it or {}).get('nom') if isinstance(it, dict) else str(it)
        if not nom:
            continue
        out.append((nom, int((it or {}).get('n') or 0) if isinstance(it, dict) else 0))
    if not out:
        raise ValueError(
            "aucun nom tire de /api/names — la reponse a-t-elle change de "
            "forme ? Un banc qui rend 0 sur une lecture ratee ment mieux "
            "qu il ne se tait.")
    return out


def repartir(comptes, par_nom, budget):
    """Combien de photos lire pour chaque nom, sous un plafond GLOBAL.

    `comptes` : `[(nom, n)]`. Rend `{nom: part}` et le nombre de couples
    nom–photo laissés de côté. La part d'un nom ne dépasse jamais son compte —
    un nom de 3 photos est alors compté EXACTEMENT, pas estimé.

    Le plafond se répartit au prorata et JAMAIS en silence : ce que la part
    laisse dehors est rendu, pour être dit."""
    parts = {nom: min(n, par_nom) for nom, n in comptes}
    total = sum(parts.values())
    if budget and total > budget:
        f = budget / float(total)
        for nom, n in comptes:
            parts[nom] = max(1, int(parts[nom] * f)) if n else 0
    non_lus = sum(max(0, n - parts.get(nom, 0)) for nom, n in comptes)
    return parts, non_lus


def estimer(lus, manque, total):
    """Ce que l'échantillon d'un nom dit de son fonds : (exact, estime).

    Un nom entièrement lu rend un chiffre EXACT ; un nom échantillonné rend une
    projection, arrondie. Les deux ne se mélangent pas dans le rapport — un
    chiffre estimé présenté comme un compte fait prendre une décision sur du
    vent."""
    if not lus:
        return 0, 0
    if lus >= total:
        return manque, 0
    return 0, int(round(total * manque / float(lus)))


def wilson(succes, n, z=1.96):
    """Intervalle de Wilson — l'incertitude d'un taux tiré d'un échantillon."""
    if not n:
        return (0.0, 1.0)
    p = succes / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


# En dessous de tant de lectures, un TAUX par nom ne veut rien dire : 1 sur 4
# se projette en « 25 % » avec la même assurance que 250 sur 1 000. Le chiffre
# global, lui, est solide — il agrège toutes les lectures.
LUS_MIN_PAR_NOM = 8


def rapporter(lignes, non_lus, file_serveur, noms_total, ecrire=print):
    """Le tableau, puis les deux totaux qui ne se confondent pas."""
    barre = "=" * 74
    ecrire("\n" + barre)
    ecrire("  L ECART INDEX / FICHIERS, SUR TOUS LES NOMS")
    ecrire(barre)
    exact_m = sum(l['exact'] for l in lignes)
    est_m = sum(l['estime'] for l in lignes)
    lus = sum(l['lus'] for l in lignes)
    manq = sum(l['manque'] for l in lignes)
    entiers = [l for l in lignes if l['lus'] >= l['total'] and l['total']]
    partiels = [l for l in lignes if l['lus'] < l['total']]
    ecrire(f"  noms                 : {noms_total} "
           f"({len(entiers)} comptes EXACTEMENT, {len(partiels)} estimes)")
    ecrire(f"  couples nom-photo lus: {lus}")
    ecrire(f"  parmi eux, en ecart  : {manq}")
    if lus:
        b, h = wilson(manq, lus)
        ecrire(f"  taux d ecart mesure  : {100.0*manq/lus:.1f} % "
               f"(Wilson {100*b:.1f} % - {100*h:.1f} %)")
    ecrire("")
    ecrire(f"  ECART CERTAIN  (noms lus en entier) : {exact_m}")
    ecrire(f"  ECART ESTIME   (le reste, projete)  : {est_m}")
    ecrire(f"  --> a reparer, ordre de grandeur    : {exact_m + est_m}")
    ecrire("")
    ecrire(f"  NON LUS (couples nom-photo hors echantillon) : {non_lus}")
    ecrire("  Taire ce chiffre ferait lire le rapport comme une exhaustivite.")
    # Le classement PAR NOM n'a de sens que sur assez de lectures. Le premier
    # jet rangeait « Val : 602 » sur DEUX fichiers en ecart sur quatre lus :
    # un bruit de tirage presente comme une priorite de reparation.
    dignes = [l for l in lignes
              if l['lus'] >= LUS_MIN_PAR_NOM or l['lus'] >= l['total'] > 0]
    trop_maigres = sum(1 for l in lignes if l['lus'] and l not in dignes)
    pires = [l for l in sorted(dignes, key=lambda l: -(l['exact'] + l['estime']))
             if l['exact'] + l['estime']][:15]
    if pires:
        ecrire("\n  Les noms qui doivent le plus (au moins "
               f"{LUS_MIN_PAR_NOM} lectures) :")
        for l in pires:
            marque = "exact" if l['lus'] >= l['total'] else "estime"
            ecrire(f"    {l['exact']+l['estime']:5}  {l['nom']:<28} "
                   f"({l['manque']}/{l['lus']} lus, {marque}, index {l['total']})")
    if trop_maigres:
        ecrire(f"\n  {trop_maigres} nom(s) lus moins de {LUS_MIN_PAR_NOM} fois : "
               "aucun taux individuel n en sort. Relancer avec --par-nom plus "
               "haut pour les classer ; le taux GLOBAL ci-dessus, lui, tient.")
    if not pires:
        ecrire("\n  Aucun nom n a assez de lectures pour etre classe. Le seul "
               "chiffre solide de ce rapport est le taux GLOBAL.")
    if file_serveur is not None:
        ecrire(f"\n  la file du serveur annonce {file_serveur} OPERATION(S) restante(s)")
        if file_serveur:
            ecrire("  (elle tourne : une partie de l ecart est en train d etre comblee)")
    ecrire(barre + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serveur', default='http://127.0.0.1:8080')
    ap.add_argument('--par-nom', type=int, default=8,
                    help="photos lues au plus par nom (defaut 8)")
    ap.add_argument('--budget', type=int, default=2400,
                    help="plafond GLOBAL de fichiers lus (defaut 2400)")
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    exe = V.exiftool_exe()
    if not exe:
        print("  ! ExifTool introuvable — ce banc ne peut rien lire.")
        return 2
    uploads = V.dossier_uploads()

    try:
        comptes = noms_du_serveur(a.serveur)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"  ! le serveur ne repond pas ({e}) — l index est sa verite, "
              "ce banc ne l invente pas.")
        return 2
    parts, non_lus = repartir(comptes, a.par_nom, a.budget)

    print(f"  {len(comptes)} nom(s) de personne ; lecture d au plus "
          f"{sum(parts.values())} fichier(s)…")
    lignes = []
    tirages = {}                       # nom -> cles tirees
    chemins = set()
    for nom, n in comptes:
        part = parts.get(nom, 0)
        if not part:
            continue
        try:
            cles = V.cles_du_nom(nom, a.serveur)
        except (urllib.error.URLError, OSError, ValueError):
            cles = []
        tir, _ = V.echantillonner(cles, part)
        tirages[nom] = tir
        for c in tir:
            p = V.chemin_de_cle(c, uploads)
            if p is not None:
                chemins.add(p)

    tags = V.lire_tags(sorted(chemins), exe, journal=None)

    for nom, n in comptes:
        tir = tirages.get(nom) or []
        if not tir:
            lignes.append({'nom': nom, 'total': n, 'lus': 0, 'manque': 0,
                           'exact': 0, 'estime': 0, 'illisible': 0})
            continue
        res = V.comparer(tir, uploads, tags, nom)
        lus = len(res['porte']) + len(res['manque'])
        exact, est = estimer(lus, len(res['manque']), n)
        lignes.append({'nom': nom, 'total': n, 'lus': lus,
                       'manque': len(res['manque']), 'exact': exact,
                       'estime': est,
                       'illisible': len(res['illisible']) + len(res['introuvable'])})

    rapporter(lignes, non_lus, V.file_du_serveur(a.serveur), len(comptes))

    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps({'noms': lignes, 'non_lus': non_lus,
                        'par_nom': a.par_nom, 'budget': a.budget},
                       ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"  liste ecrite : {a.sortie_json}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
