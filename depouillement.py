#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dépouillement du banc 3b — logique PURE, testable hors serveur.

Sorti de `eval_tagging.py` le 16/08/2026 parce que l'outil n'appliquait que la
MOITIÉ de son propre critère. `docs/PROTOCOLE_3B_TAGGING.md` dit :

    « v2ctx gagne si la préférence atteint le seuil **et** que son taux
      d'hallucination n'est pas supérieur à celui de V0 »
    « ≤ 75, **ou hallucinations en hausse** → la re-passe est close »

`depouiller` testait la préférence, puis imprimait « vérifier les
hallucinations » — c'est-à-dire qu'il laissait le bras le plus coûteux du
critère à la bonne volonté du lecteur. Un critère écrit d'avance que l'outil
n'applique pas n'est pas un critère, c'est une intention.

Deux ajouts, tirés du dépouillement réel du 16/08 :

- **Les pièges se dépouillent à part** — le protocole le disait déjà en prose.
  Sur les vraies photos la préférence tombait de 63,9 % à 59,0 % (non démontré) ;
  tout l'écart venait des 30 documents/reçus/captures.
- **Les hallucinations se comparent PAR PAIRE**, pas en totaux. Les deux
  variantes voient la même photo : ce qui compte est le nombre de photos où
  l'une hallucine et pas l'autre (McNemar). En totaux 24 contre 13 ; en paires
  15 contre 4, p = 0,019.
"""

from math import comb


def binom_p(k, n):
    """p bilatérale d'un signe-test à p = 0,5 (au moins k succès sur n)."""
    if not n:
        return 1.0
    k = max(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def seuil_significatif(n, alpha=0.05):
    """Plus petit k tel que `binom_p(k, n) < alpha`. None si n est trop petit.

    C'est ce qui rend le critère TRANSPOSABLE : l'échantillon a perdu 3 photos
    (150 → 147), le seuil suit (88 → 86) et se calcule au lieu de se négocier
    après coup.
    """
    for k in range(n // 2, n + 1):
        if binom_p(k, n) < alpha:
            return k
    return None


def paires(notes, mapping):
    """(notes, mapping) → [{cat, best, halluc:set}] — une entrée par carte notée.

    Ignore les clés techniques du mapping (« _key », « _cat ») et les cartes
    sans choix : une carte non notée n'est pas un match nul, elle n'existe pas.
    """
    out = []
    for i, n in (notes or {}).items():
        brut = (mapping or {}).get(str(i)) or {}
        paire = {L: v for L, v in brut.items() if not str(L).startswith('_')}
        best = paire.get((n or {}).get('best'))
        if not best:
            continue
        out.append({
            'cat': brut.get('_cat') or '?',
            'best': best,
            'halluc': {paire[L] for L in (n.get('halluc') or []) if L in paire},
        })
    return out


def preference(lignes, variante):
    """(k, n, p, seuil, atteint) pour une variante sur ces lignes."""
    n = len(lignes)
    k = sum(1 for r in lignes if r['best'] == variante)
    s = seuil_significatif(n)
    return {'k': k, 'n': n, 'pct': (100.0 * k / n) if n else 0.0,
            'p': binom_p(k, n), 'seuil': s,
            'atteint': bool(s is not None and k >= s)}


def hallucinations_appariees(lignes, variante, reference):
    """McNemar : compare les hallucinations PHOTO PAR PHOTO.

    Les deux variantes décrivent la même image ; comparer deux totaux jette
    l'appariement, qui est précisément ce qui donne de la puissance ici.
    Renvoie les discordantes, leur p, et le verdict `en_hausse`.
    """
    seule_v = sum(1 for r in lignes
                  if variante in r['halluc'] and reference not in r['halluc'])
    seule_r = sum(1 for r in lignes
                  if reference in r['halluc'] and variante not in r['halluc'])
    les_deux = sum(1 for r in lignes
                   if variante in r['halluc'] and reference in r['halluc'])
    disc = seule_v + seule_r
    p = binom_p(max(seule_v, seule_r), disc)
    return {'seule_variante': seule_v, 'seule_reference': seule_r,
            'les_deux': les_deux, 'discordantes': disc, 'p': p,
            'total_variante': sum(1 for r in lignes if variante in r['halluc']),
            'total_reference': sum(1 for r in lignes if reference in r['halluc']),
            # « en hausse » au sens du protocole : plus d'hallucinations, point.
            # La significativité est rendue à côté pour que la décision soit
            # informée — elle ne relâche pas le critère.
            'en_hausse': seule_v > seule_r,
            'demontre': p < 0.05}


def verdict_3b(lignes, variante='V2CTX', reference='V0'):
    """Applique le critère ENTIER de docs/PROTOCOLE_3B_TAGGING.md.

    Rend un dict avec `decision` ∈ {'justifiee', 'non_demontree', 'close'} et
    de quoi l'écrire dans `eval/DECISIONS.md` sans rien recalculer à la main.
    """
    hors_piege = [r for r in lignes if r['cat'] != 'piege']
    res = {
        'global': preference(lignes, variante),
        'hors_pieges': preference(hors_piege, variante),
        'par_strate': {},
        'halluc': hallucinations_appariees(lignes, variante, reference),
    }
    for c in sorted({r['cat'] for r in lignes}):
        res['par_strate'][c] = preference([r for r in lignes if r['cat'] == c],
                                          variante)

    h = res['halluc']
    g = res['global']
    if h['en_hausse']:
        # Branche explicite du protocole : « ≤ 75, OU hallucinations en hausse ».
        res['decision'] = 'close'
        res['motif'] = (
            f"hallucinations en hausse ({h['total_variante']} contre "
            f"{h['total_reference']} ; appariées {h['seule_variante']} contre "
            f"{h['seule_reference']}, p = {h['p']:.4f})")
    elif g['atteint']:
        res['decision'] = 'justifiee'
        res['motif'] = (f"préférence {g['k']}/{g['n']} ≥ seuil {g['seuil']} "
                        f"(p = {g['p']:.4f}) et hallucinations pas en hausse")
    else:
        res['decision'] = 'non_demontree'
        res['motif'] = (f"préférence {g['k']}/{g['n']} sous le seuil "
                        f"{g['seuil']} (p = {g['p']:.4f})")
    return res


def lignes_de_verdict(res, variante='V2CTX', reference='V0'):
    """Le verdict en texte, prêt pour la console et pour DECISIONS.md."""
    g, hp, h = res['global'], res['hors_pieges'], res['halluc']
    out = [
        f"   {variante} préféré {g['k']}/{g['n']} ({g['pct']:.1f} %) "
        f"— p = {g['p']:.4f}, seuil {g['seuil']}",
        f"   hors pièges     {hp['k']}/{hp['n']} ({hp['pct']:.1f} %) "
        f"— p = {hp['p']:.4f}, seuil {hp['seuil']}"
        f"  -> {'au-dessus' if hp['atteint'] else 'SOUS LE SEUIL'}",
        "   par strate :",
    ]
    for c, s in res['par_strate'].items():
        out.append(f"      {c:<10} {s['k']:>3}/{s['n']:<3} ({s['pct']:5.1f} %) "
                   f"p = {s['p']:.4f}"
                   f"{'  <- au-dessus du seuil' if s['atteint'] else ''}")
    out += [
        f"   hallucinations : {variante} {h['total_variante']} contre "
        f"{reference} {h['total_reference']}",
        f"      appariées : {variante} seul {h['seule_variante']}, "
        f"{reference} seul {h['seule_reference']}, les deux {h['les_deux']}"
        f" — p = {h['p']:.4f}"
        f" ({'écart démontré' if h['demontre'] else 'non démontré'})",
        "",
        f"   -> DÉCISION : {res['decision'].upper()} — {res['motif']}",
    ]
    return out
