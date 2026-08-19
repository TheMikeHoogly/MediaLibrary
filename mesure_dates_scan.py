#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — combien de photos portent EN BASE une date de SCAN ?
──────────────────────────────────────────────────────────────────────────────

CE QU'ON MESURE, ET POURQUOI ICI

Le garde-fou du 17/08 (`renommage_facts.date_de_scan_presumee`) protège le NOM
DU FICHIER : une date EXIF précise postérieure de plus d'un an à toutes les
années du dossier n'est pas crue, on retombe sur « YYYY0000 ». Il ne touche PAS
l'index. Le champ `taken` de `photos.db` garde donc la date du scan, et c'est
lui qui alimente le tri chronologique, « même jour » et le filtre par période :
`\\…\\Photos Papa\\1990\\1990_Achumani\\…` sort au 1er mai 2007.

12 cas étaient connus — les seuls que le plan de renommage regardait, parce
qu'il ne regarde que les noms encore bruts. La PORTÉE réelle en base n'a jamais
été comptée. Ce module la compte. Il ne corrige rien : mesurer d'abord.

CE QU'IL NE FAIT PAS

- Il n'écrit RIEN, nulle part. Aucun `UPDATE`, aucun fichier touché.
- Il refuse d'ouvrir un fichier nommé `photos.db` : le serveur est l'écrivain
  unique, on mesure sur une COPIE (invariant du projet).
- Il ne RECOPIE pas le critère : il IMPORTE `renommage_facts`
  (`path_years`, `date_de_scan_presumee`, `ECART_ANNEE_TOLERE`). Un banc qui
  recopie la prod mesure autre chose qu'elle — mesure du 14/08.

LES QUATRE CAS, ET L'ASYMÉTRIE

Pour une entrée qui porte un `taken`, on compare son année à l'ENSEMBLE des
années lues dans les DOSSIERS du chemin (jamais le nom de fichier) :

  scan_presume  : année > max(dossier) + 1 an   -> date de SCAN présumée.
  anterieure    : année < min(dossier)          -> l'EXIF a RAISON contre un
                  dossier d'import (`2026\\Photos Floflo` contient de vraies
                  photos de 2014). LÉGITIME, compté à part, jamais « corrigé ».
  coherente     : dans la plage, tolérance d'un an comprise (les 139 réveillons
                  du 14/08 : « 2019 Voyage » qui contient le 1er janvier 2020).
  sans_repere   : aucune année dans le dossier -> rien à contredire, donc rien
                  à dire. Compté, pour ne pas faire passer un angle mort pour
                  un zéro.

DEUX CHEMINS, UN CHIFFRE

Chemin A — ce module : DOSSIER contre `taken`.
Chemin B — `--verifier` : la TRACE du garde-fou dans le NOM. Après les 7 058
renommages, un fichier dont le nom commence par « YYYY0000 » alors que son
`taken` est précis est exactement un fichier dont le renommage a refusé la
date. Aucune ligne de code commune avec A : A lit le dossier, B lit le nom.
Sur les fichiers renommés, les deux ensembles doivent coïncider — et l'écart,
s'il existe, est le vrai résultat de la mesure.

USAGE
    python mesure_dates_scan.py --base copie.db [--exemples 20] [--verifier]
                                [--json rapport.json]
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict

try:
    from renommage_facts import (ECART_ANNEE_TOLERE, date_de_scan_presumee,
                                 path_years)
except ImportError:                      # exécuté hors du dossier du projet
    sys.stderr.write("mesure_dates_scan : renommage_facts.py introuvable — "
                     "lancer depuis le dossier du projet.\n")
    raise


# ───────────────────────────── logique PURE ─────────────────────────────

def annee_de(epoch):
    """Année civile locale d'un epoch, ou None s'il est inexploitable.
    `taken` est un epoch local (écrit par `parse_exif_dt` via `mktime`) : on le
    relit avec `localtime`, jamais `gmtime` — un décalage d'un fuseau ferait
    basculer d'année les photos du 31 décembre au soir."""
    if not isinstance(epoch, (int, float)) or isinstance(epoch, bool):
        return None
    if epoch <= 0:
        return None
    try:
        return time.localtime(float(epoch)).tm_year
    except (ValueError, OSError, OverflowError):
        return None


def classer(cle, taken):
    """Verdict d'UNE entrée. Rend un dict :
        {'statut', 'annee': int|None, 'annees_chemin': tuple, 'ecart': int|None}

    `ecart` est signé et mesuré au bord le plus proche de la plage du dossier :
    positif = en avance sur le dossier, négatif = en retard. Il vaut 0 quand
    l'année tombe dans la plage. Il est None sans repère.

    Statuts : 'sans_taken', 'sans_repere', 'scan_presume', 'anterieure',
    'coherente'.
    """
    an = annee_de(taken)
    if an is None:
        return {'statut': 'sans_taken', 'annee': None,
                'annees_chemin': (), 'ecart': None}
    annees = path_years(cle)
    if not annees:
        return {'statut': 'sans_repere', 'annee': an,
                'annees_chemin': (), 'ecart': None}
    lo, hi = min(annees), max(annees)
    ecart = an - hi if an > hi else (an - lo if an < lo else 0)
    if date_de_scan_presumee(an, annees):
        statut = 'scan_presume'
    elif an < lo:
        statut = 'anterieure'
    else:
        statut = 'coherente'
    return {'statut': statut, 'annee': an,
            'annees_chemin': tuple(sorted(annees)), 'ecart': ecart}


def dossier_de(cle):
    """Partie DOSSIER de la clé, en « \\ », sans le nom de fichier."""
    k = str(cle).replace('/', '\\')
    return k.rsplit('\\', 1)[0] if '\\' in k else ''


def racine_lisible(cle, profondeur=6):
    """Dossier tronqué, pour ventiler un rapport sans dérouler 43 000 chemins.
    On garde les `profondeur` premiers composants APRÈS l'hôte et le partage
    d'un chemin UNC (« \\\\NAS\\home\\Photos\\Photos Papa\\1990 »)."""
    d = dossier_de(cle)
    unc = d.startswith('\\\\')
    parts = [c for c in d.split('\\') if c]
    if unc:
        parts = parts[2:]
    return '\\'.join(parts[:profondeur])


def datestamp_du_nom(cle):
    """« YYYYMMDD » de tête du NOM DE FICHIER si le renommage l'y a écrit,
    sinon None. Sert au CHEMIN B : c'est la trace laissée par le garde-fou,
    lue sans jamais regarder le dossier."""
    nom = str(cle).replace('/', '\\').split('\\')[-1]
    tete = nom[:8]
    if len(tete) == 8 and tete.isdigit() and '19' <= tete[:2] <= '21':
        return tete
    return None


def renomme_par_le_plan(cle):
    """True si le nom porte la signature du renommage (« YYYYMMDD_ » ou
    « YYYY0000_ » en tête). Le chemin B ne vaut que sur ces fichiers : un nom
    brut n'a jamais été soumis au garde-fou."""
    return datestamp_du_nom(cle) is not None


def nom_reintroduit_la_date(cle, taken):
    """Le NOM porte-t-il une date PRÉCISE de la même année que `taken` ?

    C'est la limite du garde-fou, et elle n'apparaît qu'ici : quand
    `resolve_datestamp` refuse `taken`, il ne retombe PAS directement sur
    l'année du dossier — il lit d'abord la date du NOM DE FICHIER (étape 2), qui
    n'est soumise à aucun contrôle. Si l'appareil de numérisation a nommé le
    fichier « 20150810_073417.jpg », le repli réinscrit exactement la date que
    l'étape 1 venait d'écarter.

    À n'interpréter QUE sur une entrée déjà jugée `scan_presume` : ailleurs,
    nom et `taken` qui s'accordent sont la situation normale."""
    d8 = datestamp_du_nom(cle)
    an = annee_de(taken)
    if d8 is None or an is None or d8.endswith('0000'):
        return False
    return int(d8[:4]) == an


def refuse_par_le_garde_fou(cle, taken):
    """CHEMIN B — indépendant de `classer` : le renommage a-t-il REFUSÉ la date
    précise de cette photo ? Vrai si le nom porte le repli « YYYY0000 » alors
    que `taken` existe. On ne lit ici que le NOM et `taken` ; le dossier n'est
    jamais consulté."""
    d8 = datestamp_du_nom(cle)
    if d8 is None or annee_de(taken) is None:
        return False
    return d8.endswith('0000')


# ───────────────────────────── ventilation ─────────────────────────────

def mesurer(entrees):
    """`entrees` : itérable de (cle, taken). Rend le rapport complet (dict).
    Fonction PURE : aucune I/O, testable sur des cas forgés."""
    statuts = Counter()
    par_annee = Counter()
    par_dossier = Counter()
    par_ecart = Counter()
    exemples = []
    ant_exemples = []
    # chemin B
    b_suspects = set()
    a_suspects = set()
    renommes = 0
    reintroduits = []       # le repli sur le NOM a réinscrit la date de scan
    perimes = []            # nom « YYYY0000 » alors que la date est connue depuis

    for cle, taken in entrees:
        v = classer(cle, taken)
        statuts[v['statut']] += 1
        if renomme_par_le_plan(cle):
            renommes += 1
            if refuse_par_le_garde_fou(cle, taken):
                b_suspects.add(cle)
                # Le garde-fou a refusé une date… qui est aujourd'hui COHÉRENTE
                # avec le dossier : ce n'est donc pas un scan, c'est un `taken`
                # arrivé APRÈS le renommage (tâche de fond EXIF). Le nom porte
                # « YYYY0000 » pour rien, et le plan ne regarde plus les
                # fichiers déjà renommés : il n'y reviendra pas tout seul.
                if v['statut'] != 'scan_presume':
                    perimes.append(cle)
        if v['statut'] == 'scan_presume':
            a_suspects.add(cle)
            if nom_reintroduit_la_date(cle, taken):
                reintroduits.append(cle)
            par_annee[v['annee']] += 1
            par_dossier[racine_lisible(cle)] += 1
            par_ecart[v['ecart']] += 1
            if len(exemples) < 400:
                exemples.append({'cle': cle, 'annee': v['annee'],
                                 'annees_chemin': list(v['annees_chemin']),
                                 'ecart': v['ecart'],
                                 'taken': taken})
        elif v['statut'] == 'anterieure' and len(ant_exemples) < 40:
            ant_exemples.append({'cle': cle, 'annee': v['annee'],
                                 'annees_chemin': list(v['annees_chemin']),
                                 'ecart': v['ecart']})

    # Accord des deux chemins, restreint aux fichiers RENOMMÉS (seuls ceux-là
    # ont été soumis au garde-fou : un nom brut ne prouve rien).
    a_renommes = {k for k in a_suspects if renomme_par_le_plan(k)}
    return {
        'total': sum(statuts.values()),
        'statuts': dict(statuts),
        'tolerance_ans': ECART_ANNEE_TOLERE,
        'suspects': statuts['scan_presume'],
        'par_annee_de_scan': dict(sorted(par_annee.items())),
        'par_dossier': dict(par_dossier.most_common(30)),
        'par_ecart_ans': dict(sorted(par_ecart.items())),
        'exemples': exemples,
        'exemples_anterieurs': ant_exemples,
        'accord': {
            'renommes': renommes,
            'chemin_a': len(a_renommes),
            'chemin_b': len(b_suspects),
            'communs': len(a_renommes & b_suspects),
            'a_seul': sorted(a_renommes - b_suspects)[:20],
            'b_seul': sorted(b_suspects - a_renommes)[:20],
        },
        'trou_repli_nom': sorted(reintroduits),
        'noms_perimes': sorted(perimes),
    }


# ───────────────────────────── lecture base ─────────────────────────────

def lire_entrees(db_path, table='tags'):
    """(cle, taken) depuis une COPIE de la base. Lecture seule stricte."""
    nom = os.path.basename(str(db_path))
    if nom == 'photos.db':
        raise SystemExit(
            "REFUS : le serveur est l'ecrivain unique de photos.db.\n"
            "Copiez d'abord la base (photos.db + -wal + -shm) et mesurez sur la\n"
            "copie : python mesure_dates_scan.py --base copie.db")
    cx = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        for k, v in cx.execute(f'SELECT k, v FROM "{table}"'):
            try:
                e = json.loads(v)
            except (ValueError, TypeError):
                continue
            yield k, (e.get('taken') if isinstance(e, dict) else None)
    finally:
        cx.close()


def formater(r, exemples=12):
    L = []
    A = L.append
    A("MESURE - dates de SCAN crues EN BASE")
    A("=" * 62)
    A(f"Entrees examinees                : {r['total']}")
    s = r['statuts']
    A(f"  sans taken                     : {s.get('sans_taken', 0)}")
    A(f"  sans annee dans le dossier     : {s.get('sans_repere', 0)}   (angle mort)")
    A(f"  coherente (tolerance {r['tolerance_ans']} an)    : {s.get('coherente', 0)}")
    A(f"  anterieure au dossier          : {s.get('anterieure', 0)}   (EXIF a raison, LEGITIME)")
    A(f"  DATE DE SCAN PRESUMEE          : {s.get('scan_presume', 0)}")
    A("")
    if r['suspects']:
        A("Par annee inscrite (l'annee du scan) :")
        for an, n in r['par_annee_de_scan'].items():
            A(f"    {an} : {n}")
        A("")
        A("Par ecart, en annees, au-dela du dossier :")
        for ec, n in r['par_ecart_ans'].items():
            A(f"    +{ec:>3} an(s) : {n}")
        A("")
        A("Par dossier (30 premiers) :")
        for d, n in r['par_dossier'].items():
            A(f"    {n:>5}  {d}")
        A("")
        A(f"Exemples ({min(exemples, len(r['exemples']))}) :")
        for e in r['exemples'][:exemples]:
            A(f"    {e['annee']} <- dossier {e['annees_chemin']}  {e['cle'][-88:]}")
        A("")
    ac = r['accord']
    A("ACCORD DES DEUX CHEMINS (fichiers renommes seulement)")
    A(f"    fichiers renommes            : {ac['renommes']}")
    A(f"    chemin A (dossier vs taken)  : {ac['chemin_a']}")
    A(f"    chemin B (repli YYYY0000)    : {ac['chemin_b']}")
    A(f"    communs                      : {ac['communs']}")
    if ac['a_seul']:
        A(f"    A seul ({len(ac['a_seul'])} montres) :")
        for k in ac['a_seul']:
            A(f"        {k[-88:]}")
    if ac['b_seul']:
        A(f"    B seul ({len(ac['b_seul'])} montres) :")
        for k in ac['b_seul']:
            A(f"        {k[-88:]}")
    A("")
    A("CE QUE LE DESACCORD DIT (et qu'aucun des deux chemins ne dit seul)")
    A(f"    trou du repli sur le NOM     : {len(r['trou_repli_nom'])}"
      "   (garde-fou refuse taken, le NOM le reinscrit)")
    for k in r['trou_repli_nom'][:10]:
        A(f"        {k[-88:]}")
    A(f"    noms perimes YYYY0000        : {len(r['noms_perimes'])}"
      "   (date connue DEPUIS le renommage)")
    for k in r['noms_perimes'][:10]:
        A(f"        {k[-88:]}")
    if r['exemples_anterieurs']:
        A("")
        A("Rappel de l'ASYMETRIE - dates ANTERIEURES au dossier (a NE PAS toucher) :")
        for e in r['exemples_anterieurs'][:6]:
            A(f"    {e['annee']} <- dossier {e['annees_chemin']}  {e['cle'][-80:]}")
    return '\n'.join(L)


def effet_de_la_lecture(entrees):
    """CE QUE LE GARDE-FOU CHANGE QUAND C'EST LA **LECTURE** QUI L'APPLIQUE.

    Décision du 19/08 : on n'écrit pas `taken` en base — 72 corrections face à
    1 347 dates antérieures légitimes, et un `taken` réécrit perd sa provenance
    (c'est une LECTURE de l'EXIF, pas une déduction). La correction est une VUE,
    exactement comme `faits`. Reste à savoir ce qu'elle déplace vraiment.

    Trois consommateurs lisent la date PRÉCISE : le tri de la galerie, le
    filtre par période, et « même jour ». Tous passent par `epoch_precis` —
    qui prend le MINIMUM du `taken` et de la date lue dans le NOM. Le scanner
    ayant écrit dans les deux, les deux doivent passer le garde-fou : d'où
    quatre cas, et non deux.

    Le module IMPORTE la règle (`faits_vue.date_credible`, `meme_jour`), il ne
    la recopie pas."""
    import faits_vue
    import meme_jour
    nom_time = lambda n: faits_vue.epoch_du_nom(n)             # noqa: E731
    cas = Counter()
    exemples = defaultdict(list)
    for cle, taken in entrees:
        e = {'taken': taken} if taken else {}
        avant = meme_jour.epoch_precis(cle, e, nom_time)
        apres = meme_jour.epoch_precis(cle, e, nom_time,
                                       faits_vue.date_credible)
        if avant is None and apres is None:
            cas['aucune date precise, avant comme apres'] += 1
        elif avant == apres:
            cas['date precise inchangee'] += 1
        elif apres is None:
            cas['PERD sa date precise (retombe sur l annee du dossier)'] += 1
            if len(exemples['perd']) < 8:
                exemples['perd'].append((cle, annee_de(avant)))
        else:
            cas['CHANGE de date precise (l autre source restait credible)'] += 1
            if len(exemples['change']) < 8:
                exemples['change'].append((cle, annee_de(avant), annee_de(apres)))
    return {'cas': dict(cas), 'exemples': {k: v for k, v in exemples.items()}}


def formater_lecture(r):
    L = ["", "=" * 62,
         "SI LA LECTURE APPLIQUE LE GARDE-FOU (rien n'est ecrit en base)",
         "=" * 62]
    for k, n in sorted(r['cas'].items(), key=lambda x: -x[1]):
        L.append(f"  {n:>7}  {k}")
    if r['exemples'].get('perd'):
        L.append("  Elles perdent une date PRECISE fausse et retombent sur")
        L.append("  l'annee du dossier - un fait humain, pas une invention :")
        for cle, an in r['exemples']['perd']:
            L.append(f"      {an} -> annee du dossier   {cle[-72:]}")
    if r['exemples'].get('change'):
        L.append("  Elles changent de date : le SCAN etait dans une source,")
        L.append("  l'autre restait credible.")
        for cle, av, ap in r['exemples']['change']:
            L.append(f"      {av} -> {ap}   {cle[-72:]}")
    return '\n'.join(L)


def main(argv=None):
    # Description ASCII : la sortie doit survivre a une REDIRECTION sous
    # Windows (cp1252) -- l'import mourait deja d'un UnicodeEncodeError des que
    # stdout etait un tuyau (mesure du 15/08).
    p = argparse.ArgumentParser(
        description="Compte les dates de SCAN crues en base (lecture seule).")
    p.add_argument('--base', required=True, help='COPIE de photos.db')
    p.add_argument('--table', default='tags')
    p.add_argument('--exemples', type=int, default=12)
    p.add_argument('--json', help='ecrire le rapport complet en JSON')
    p.add_argument('--lecture', action='store_true',
                   help='mesurer ce que le garde-fou change a la LECTURE')
    a = p.parse_args(argv)
    entrees = list(lire_entrees(a.base, a.table))
    r = mesurer(entrees)
    print(formater(r, a.exemples))
    if a.lecture:
        r['lecture'] = effet_de_la_lecture(entrees)
        print(formater_lecture(r['lecture']))
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
        print(f"\nrapport JSON : {a.json}")
    return 0


__all__ = ['annee_de', 'classer', 'dossier_de', 'racine_lisible',
           'datestamp_du_nom', 'renomme_par_le_plan', 'refuse_par_le_garde_fou',
           'mesurer', 'lire_entrees', 'formater', 'effet_de_la_lecture',
           'formater_lecture']


if __name__ == '__main__':
    sys.exit(main())
