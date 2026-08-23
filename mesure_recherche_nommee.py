#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesure — ce que coûte VRAIMENT une recherche par nom (audit O7)
──────────────────────────────────────────────────────────────────────────────

CE QU'ON MESURE, ET POURQUOI

L'audit interne dit d'O7 : « `_cles_portant` scanne 64 676 entrées en
`lower()` par requête ». C'est vrai, et ce n'est pas une décision. Un balayage
de 43 000 entrées peut coûter 20 ms comme 900 ms, et seul le second justifie
un index inversé — lequel apporte une invalidation, donc une classe de bugs
que le projet n'a pas aujourd'hui (« la fraîcheur est gratuite », `_cles_de_l_espece`).
Ce module donne le chiffre AVANT le code.

COMMENT ON ISOLE LE BALAYAGE SANS TOUCHER AU SERVEUR

On ne recopie pas `_cles_portant` : un banc qui recopie la prod mesure autre
chose qu'elle (leçon du 14/08). On l'isole par SOUSTRACTION, avec le paramètre
`n` de `/api/search` qui plafonne le RENDU sans toucher au filtre :

    plancher   `/api/serveur`              : HTTP + routeur, rien d'autre
    rare  n=1  `/api/search?q=<nom rare>`  : + extraction du nom, autorité des
                                             noms, BALAYAGE COMPLET, rendu ~0
    rare  n=1500                           : le rendu d'un nom rare (~rien)
    gros  n=1  `/api/search?q=<nom lourd>` : + le TRI de milliers de candidats
    gros  n=1500                           : ce que l'utilisateur attend vraiment

    coût FIXE du filtre nommé  =  med(rare n=1)  -  med(plancher)
    coût du TRI des candidats  =  med(gros n=1)  -  med(rare n=1)
    coût du RENDU              =  med(gros n=1500) - med(gros n=1)

CE QUI CONTRÔLE LE MODÈLE, ET SANS QUOI IL NE VAUDRAIT RIEN

`_cles_portant` fait UN balayage pour TOUS les noms demandés. Donc une requête
à DEUX noms doit coûter le même prix qu'à un seul. Le banc le vérifie
(`deux n=1`) : si ce contrôle tombe, la soustraction ci-dessus mesure autre
chose que ce qu'elle annonce, et le rapport le DIT au lieu de conclure.

Un score parfait est une alarme, pas un succès (méthode du projet) : un coût
fixe mesuré à ~0 ms voudrait dire que 43 000 entrées se balaient gratuitement.
Le rapport le signale plutôt que de le célébrer.

`/api/names` est mesuré au passage, sans être l'objet : il balaie le MÊME
index, plus `parse_tag_nomme` sur chaque mot-clé, et l'autocomplétion l'appelle
au chargement de chaque page. S'il coûte plus qu'O7, c'est lui le sujet — et il
reçoit son propre verdict, au même seuil.

CE QUE LA PREMIÈRE MESURE A TROUVÉ EN CHEMIN (23/08)

La colonne « total » reste vide, et ce n'est pas un trou du banc : `/api/search`
CALCULE `detail['total']` et `detail['tronque']` puis ne les met pas dans sa
réponse. Seule la page `/files?q=` les reçoit. Un consommateur de l'API — le
MCP, un banc, un futur client — voit donc 1 500 photos sans savoir qu'il y en
avait 5 832 : le plafond SILENCIEUX corrigé pour la page le 22/08 et pour le
MCP le 23/08 est toujours là, dans la route elle-même.

CE QU'IL NE FAIT PAS

- Il n'écrit RIEN, nulle part : sept requêtes GET, et un rapport sur la sortie.
- Il n'ouvre aucune base : le serveur est l'écrivain unique (règle 4).
- Il ne touche pas au NAS. `/api/search` appelle `media_roots()`, qui fait des
  stats SMB (c'est l'audit O3) : une par requête, pas une par photo — c'est
  dans le plancher de TOUTES les mesures nommées, donc pas dans les
  différences. Le rapport le rappelle.
- **Il ne conclut pas seul.** Le seuil de décision est écrit ci-dessous, AVANT
  la mesure : un critère décidé après coup n'est pas un critère.

LE SEUIL, ÉCRIT D'AVANCE

  coût fixe < 50 ms   : O7 ne vaut pas de code — le classer, avec le chiffre.
  50 à 200 ms         : réel mais mineur ; à peser contre le reste de la liste.
  > 200 ms            : le chantier est justifié.

LE BRUIT — À DÉCLARER, JAMAIS À CACHER

Le tagueur et les files du serveur tournent pendant la mesure. Ils prennent du
CPU. C'est pourquoi le banc rend la MÉDIANE **et le MINIMUM** : le minimum est
le tour le moins pollué, la médiane ce que l'utilisateur ressent quand la
machine travaille. Un écart énorme entre les deux est une information, pas un
défaut de la mesure.

USAGE
    python mesure_recherche_nommee.py [--url http://127.0.0.1:8080]
                                      [--tours 7] [--json rapport.json]
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Seuils de décision — écrits AVANT la mesure (voir l'en-tête).
SEUIL_NEGLIGEABLE_MS = 50.0
SEUIL_JUSTIFIE_MS = 200.0

# Un tour qui se fige tuerait la fenêtre des bancs, comme le `{ready}` avalé
# par `-q` le 23/08. Un banc doit ÉCHOUER, jamais attendre sans fin.
TIMEOUT_S = 30.0

URL_DEFAUT = 'http://127.0.0.1:8080'


# ─────────────────────────── les outils purs ───────────────────────────

def resume(durees_ms):
    """min / médiane / max d'une série, en ms. Série vide : tout à None."""
    xs = [float(x) for x in durees_ms]
    if not xs:
        return {'n': 0, 'min': None, 'med': None, 'max': None}
    return {'n': len(xs), 'min': min(xs), 'max': max(xs),
            'med': statistics.median(xs)}


def choisir_noms(noms):
    """(le nom le plus LOURD, un nom RARE mais réel) parmi `/api/names`.

    Le lourd fait voir le tri et le rendu ; le rare isole le balayage, qui a
    lieu de toute façon. Un nom à ZÉRO photo ne convient pas : `_extraire_noms`
    le reconnaîtrait, mais la requête ne ressemblerait à rien de réel.
    Rend (lourd, rare, autre_rare) — `autre_rare` sert au contrôle à deux noms.
    Un nom manquant vaut None ; l'appelant ne doit pas deviner à sa place."""
    utiles = [n for n in noms
              if isinstance(n, dict) and (n.get('nom') or '').strip()
              and int(n.get('n') or 0) > 0]
    if not utiles:
        return None, None, None
    par_volume = sorted(utiles, key=lambda n: int(n.get('n') or 0))
    lourd = par_volume[-1]
    rares = [n for n in par_volume if n is not lourd]
    rare = rares[0] if rares else None
    autre = rares[1] if len(rares) > 1 else None
    return lourd, rare, autre


def attribuer(mes):
    """Décompose ce que coûte une recherche nommée, à partir des résumés.

    `mes` : {etape: resume(...)}. Rend un dict de différences en ms, avec None
    partout où une étape manque — jamais un zéro, qui se lirait « gratuit »."""
    def med(nom):
        r = mes.get(nom) or {}
        return r.get('med')

    def diff(a, b):
        x, y = med(a), med(b)
        return None if x is None or y is None else x - y

    return {
        'fixe_filtre_nomme': diff('rare_n1', 'plancher'),
        'tri_des_candidats': diff('gros_n1', 'rare_n1'),
        'rendu_1500': diff('gros_n1500', 'gros_n1'),
        'total_utilisateur': med('gros_n1500'),
        'noms_autocompletion': diff('noms', 'plancher'),
    }


def controle_du_modele(mes, tolerance=0.35):
    """Un balayage UNIQUE pour tous les noms : deux noms ≈ un seul.

    Rend (tenu, phrase). `tenu` est None quand la mesure manque — l'ignorance
    n'est pas un accord."""
    un, deux = (mes.get('rare_n1') or {}).get('med'), \
               (mes.get('deux_n1') or {}).get('med')
    if un is None or deux is None:
        return None, "contrôle impossible : une des deux mesures manque"
    if un <= 0:
        return None, "contrôle impossible : la mesure à un nom est nulle"
    ecart = abs(deux - un) / un
    if ecart <= tolerance:
        return True, ("deux noms coûtent %.0f ms contre %.0f pour un seul "
                      "(%.0f %%) : le balayage est bien UNIQUE"
                      % (deux, un, 100 * ecart))
    return False, ("deux noms coûtent %.0f ms contre %.0f pour un seul "
                   "(%.0f %%) : le balayage n'est PAS unique, la soustraction "
                   "de ce banc ne mesure pas ce qu'elle annonce"
                   % (deux, un, 100 * ecart))


def verdict(fixe_ms):
    """La phrase de décision, selon le seuil écrit AVANT la mesure."""
    if fixe_ms is None:
        return 'inconnu', "le coût fixe n'a pas pu être mesuré"
    if fixe_ms < 1.0:
        return 'suspect', (
            "coût fixe mesuré à %.1f ms : 43 000 entrées ne se balaient pas "
            "pour rien. Un score parfait est une ALARME — la requête n'est "
            "probablement pas passée par le filtre nommé." % fixe_ms)
    if fixe_ms < SEUIL_NEGLIGEABLE_MS:
        return 'classer', (
            "coût fixe %.0f ms < %.0f : O7 ne vaut pas de code. Le classer "
            "avec le chiffre." % (fixe_ms, SEUIL_NEGLIGEABLE_MS))
    if fixe_ms < SEUIL_JUSTIFIE_MS:
        return 'mineur', (
            "coût fixe %.0f ms : réel mais mineur — à peser contre le reste "
            "de la feuille, pas à traiter par réflexe." % fixe_ms)
    return 'justifie', (
        "coût fixe %.0f ms > %.0f : le chantier O7 est justifié."
        % (fixe_ms, SEUIL_JUSTIFIE_MS))


# ─────────────────────────── le monde extérieur ───────────────────────────

def appeler(url, timeout=TIMEOUT_S):
    """(durée en ms, objet JSON). Lève si le serveur ne répond pas : un banc
    qui avale l'erreur rendrait un chiffre sans savoir de quoi."""
    t0 = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as r:
        brut = r.read()
    ms = (time.perf_counter() - t0) * 1000.0
    try:
        return ms, json.loads(brut.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return ms, None


def lien(base, chemin, **params):
    q = urllib.parse.urlencode(params) if params else ''
    return base.rstrip('/') + chemin + (('?' + q) if q else '')


def serie(url, tours):
    """`tours` appels, la première réponse gardée. Rend (durées, reponse)."""
    durees, reponse = [], None
    for i in range(tours):
        ms, obj = appeler(url)
        durees.append(ms)
        if i == 0:
            reponse = obj
    return durees, reponse


def mesurer(base, tours):
    """Les sept étapes. Rend le rapport complet, prêt à imprimer."""
    rap = {'quand': time.time(), 'url': base, 'tours': tours,
           'mesures': {}, 'noms': {}, 'totaux': {}, 'erreurs': []}

    # 0. le serveur est-il là, et à quel code tourne-t-il ?
    _, etat = appeler(lien(base, '/api/serveur'))
    rap['serveur'] = {k: (etat or {}).get(k)
                      for k in ('demarre_a', 'code_a_jour', 'uptime_s')}

    # 1. le plancher : une route qui ne balaie rien.
    d, _ = serie(lien(base, '/api/serveur'), tours)
    rap['mesures']['plancher'] = resume(d)

    # 2. l'autocomplétion — même index, autre balayage.
    d, rep = serie(lien(base, '/api/names'), tours)
    rap['mesures']['noms'] = resume(d)
    noms = (rep or {}).get('noms') or []
    rap['noms']['connus'] = len(noms)

    lourd, rare, autre = choisir_noms(noms)
    if not lourd or not rare:
        rap['erreurs'].append(
            "aucun nom exploitable dans /api/names : la mesure s'arrête ici")
        return rap
    rap['noms']['lourd'] = {'nom': lourd['nom'], 'n': lourd.get('n')}
    rap['noms']['rare'] = {'nom': rare['nom'], 'n': rare.get('n')}
    if autre:
        rap['noms']['autre_rare'] = {'nom': autre['nom'], 'n': autre.get('n')}

    def cherche(etape, requete, n):
        d, rep = serie(lien(base, '/api/search', q=requete, n=n), tours)
        rap['mesures'][etape] = resume(d)
        rap['totaux'][etape] = {
            'noms_lus': (rep or {}).get('noms'),
            'total': (rep or {}).get('total'),
            'rendus': len((rep or {}).get('results') or []),
        }

    cherche('rare_n1', rare['nom'], 1)
    cherche('rare_n1500', rare['nom'], 1500)
    cherche('gros_n1', lourd['nom'], 1)
    cherche('gros_n1500', lourd['nom'], 1500)
    if autre:
        cherche('deux_n1', rare['nom'] + ' ' + autre['nom'], 1)

    rap['attribution'] = attribuer(rap['mesures'])
    tenu, phrase = controle_du_modele(rap['mesures'])
    rap['controle'] = {'tenu': tenu, 'dit': phrase}
    v, dit = verdict(rap['attribution'].get('fixe_filtre_nomme'))
    rap['verdict'] = {'code': v, 'dit': dit}
    vn, dn = verdict(rap['attribution'].get('noms_autocompletion'))
    rap['verdict_noms'] = {'code': vn, 'dit': dn}
    return rap


# ─────────────────────────────── le rapport ───────────────────────────────

def _ms(x):
    return '  —  ' if x is None else '%6.0f' % x


def imprimer(rap, sortie=sys.stdout):
    e = sortie.write
    e('=' * 74 + '\n')
    e('  RECHERCHE NOMMEE — ce que coute le filtre (audit O7)\n')
    e('=' * 74 + '\n')
    s = rap.get('serveur') or {}
    e('  serveur     : code_a_jour=%s  uptime=%ss\n'
      % (s.get('code_a_jour'), int(s.get('uptime_s') or 0)))
    e('  tours       : %d par etape (mediane ET minimum)\n' % rap['tours'])
    n = rap.get('noms') or {}
    e('  noms connus : %s\n' % n.get('connus'))
    for cle, quoi in (('lourd', 'le plus lourd'), ('rare', 'le rare'),
                      ('autre_rare', 'le second rare')):
        if n.get(cle):
            e('  %-12s: %s (%s photos)\n'
              % (quoi, n[cle]['nom'], n[cle].get('n')))
    for msg in rap.get('erreurs') or []:
        e('  ! %s\n' % msg)
    if not rap.get('attribution'):
        return

    e('\n  ETAPES                        min      med      max\n')
    e('  ' + '-' * 70 + '\n')
    for cle, quoi in (('plancher', '/api/serveur'),
                      ('noms', '/api/names'),
                      ('rare_n1', 'rare      n=1'),
                      ('rare_n1500', 'rare      n=1500'),
                      ('gros_n1', 'lourd     n=1'),
                      ('gros_n1500', 'lourd     n=1500'),
                      ('deux_n1', 'deux noms n=1')):
        m = rap['mesures'].get(cle)
        if not m:
            continue
        t = rap.get('totaux', {}).get(cle) or {}
        detail = ('' if not t else '   %s rendus' % t.get('rendus'))
        e('  %-24s %s ms %s ms %s ms%s\n'
          % (quoi, _ms(m['min']), _ms(m['med']), _ms(m['max']), detail))

    a = rap['attribution']
    e('\n  DECOMPOSITION (medianes)\n')
    e('  ' + '-' * 70 + '\n')
    e('  cout FIXE du filtre nomme        %s ms   <- O7\n'
      % _ms(a['fixe_filtre_nomme']))
    e('  tri des candidats                %s ms\n' % _ms(a['tri_des_candidats']))
    e('  rendu de 1500 photos             %s ms\n' % _ms(a['rendu_1500']))
    e('  ce que l utilisateur attend      %s ms\n' % _ms(a['total_utilisateur']))
    e('  /api/names (autocompletion)      %s ms\n'
      % _ms(a['noms_autocompletion']))

    c = rap.get('controle') or {}
    e('\n  CONTROLE DU MODELE : %s\n'
      % {True: 'TENU', False: 'TOMBE', None: 'IMPOSSIBLE'}[c.get('tenu')])
    e('    %s\n' % c.get('dit'))

    v = rap.get('verdict') or {}
    e('\n  VERDICT O7 [%s]\n' % v.get('code'))
    e('    %s\n' % v.get('dit'))
    vn = rap.get('verdict_noms') or {}
    if vn:
        e('\n  VERDICT /api/names [%s]\n' % vn.get('code'))
        e('    %s\n' % vn.get('dit'))
        e('    (appele au chargement de CHAQUE page, pour l autocompletion)\n')
    e('\n  NOTE : la colonne « total » n existe pas — /api/search calcule\n')
    e('  detail[total] et detail[tronque] et ne les rend PAS. Un consommateur\n')
    e('  de l API voit son plafond sans savoir qu il en est un.\n')
    if c.get('tenu') is not True:
        e('    ATTENTION : le controle du modele n a pas tenu — le verdict\n')
        e('    ci-dessus porte sur une soustraction non validee.\n')
    e('=' * 74 + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--url', default=URL_DEFAUT)
    ap.add_argument('--tours', type=int, default=7)
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    if a.tours < 3:
        sys.stderr.write('mesure_recherche_nommee : --tours 3 au minimum '
                         '(une mediane sur deux tours ne dit rien).\n')
        return 2
    try:
        rap = mesurer(a.url, a.tours)
    except (urllib.error.URLError, OSError) as exc:
        sys.stderr.write('mesure_recherche_nommee : le serveur ne repond pas '
                         '(%s) — la VM n atteint pas le LAN, ce banc ne tourne '
                         'que par le canal des bancs.\n' % exc)
        return 3
    imprimer(rap)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(rap, f, ensure_ascii=False, indent=1)
    return 0 if not rap.get('erreurs') else 1


if __name__ == '__main__':
    sys.exit(main())
