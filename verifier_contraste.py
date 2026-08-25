#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verifier_contraste -- le plancher AA, mesure au lieu d'etre suppose.

Pourquoi ce banc existe
-----------------------
Le systeme `photo-ui` ecrit, dans son plancher d'accessibilite : 
    Contraste
AA : 4,5:1 texte, 3:1 gros titres et bordures porteuses. **Toute nouvelle
couleur verifiee.** " La phrase etait la depuis le debut. Personne ne l'avait
calculee -- et le jour ou on l'a fait, DEUX composants canoniques etaient
sous le seuil, dont le bouton qui confirme.

Une regle qu'on ne mesure pas n'est pas un plancher, c'est un voeu. Ce banc
la mesure, sur les tokens et les composants REELS, a chaque fois qu'on le
lui demande.

Ce qu'il fait
-------------
Il lit `ui/tokens.css` (les couleurs) et `ui/components.css` (qui pose quoi
sur quoi), resout les `var(--...)`, et calcule le ratio WCAG 2.1 de chaque
couple `color` / `background` qu'un composant declare vraiment. Pas de
couples inventes : ce qui n'est pas ecrit n'est pas juge.

Ce qu'il refuse d'affirmer
--------------------------
1. **Un fond `transparent` n'a pas de contraste**, il en herite. Le banc ne
   devine pas : il teste le texte contre TOUTES les surfaces sombres du
   systeme et retient la PIRE. Un bouton a contour peut vivre sur n'importe
   laquelle.
2. **Il ne juge que ce qu'il resout.** Un `var()` inconnu, une couleur en
   `rgb()` ou en `color-mix()` sont COMPTES a part, jamais tus -- un couple
   silencieusement saute serait un feu vert vole.
3. **Il n'efface et ne corrige rien** -- famille `verifier_`. Changer un token
   ripple sur onze pages : c'est une decision, pas un correctif.

Usage : python verifier_contraste.py [--ui ui]
SORTIE EN ASCII PUR (console cp1252 de l'agent).
"""

import argparse
import re
import sys
from pathlib import Path

SEUIL_TEXTE = 4.5
SEUIL_GROS = 3.0

# Les surfaces sur lesquelles un composant a fond transparent peut se poser.
# Le pire cas fait foi : un bouton a contour ne choisit pas son voisinage.
SURFACES_SOMBRES = ('--salle', '--salle-2', '--salle-3', '--salle-4')
SURFACES_CLAIRES = ('--papier', '--papier-2')

_HEX = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_VAR = re.compile(r'^var\(\s*(--[\w-]+)\s*\)$')
_DECL = re.compile(r'([-\w]+)\s*:\s*([^;}]+)')


def _canal(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hexa):
    h = hexa.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def contraste(a, b):
    la, lb = luminance(a), luminance(b)
    haut, bas = max(la, lb), min(la, lb)
    return (haut + 0.05) / (bas + 0.05)


def sans_commentaires(css):
    return re.sub(r'/\*.*?\*/', ' ', css, flags=re.S)


def lire_tokens(texte):
    """{'--salle': '#0C0B0A', ...} -- seulement ce qui est une COULEUR hex.

    Les commentaires partent AVANT la lecture. Sans ca, une phrase comme
    "en bordure sur --salle : 4,33:1" est lue comme une declaration, et le
    `[^;]+` avale tout jusqu'au premier `;` -- donc le token qui SUIT le
    commentaire. Observe le 25/08 : `--fixateur` a disparu de la table, ses
    trois couples sont tombes dans les non-decidables, et le banc est passe
    au vert.
    """
    texte = sans_commentaires(texte)
    out = {}
    for nom, val in re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', texte):
        v = val.strip()
        if _HEX.match(v):
            out[nom] = v
    return out


def resoudre(valeur, tokens, vus=None):
    """Rend '#rrggbb', 'transparent', ou None si l'instrument ne sait pas."""
    v = (valeur or '').strip().lower()
    if v in ('transparent', 'inherit', 'currentcolor', 'none'):
        return v
    if v == '#fff' or v == 'white':
        return '#ffffff'
    if v == '#000' or v == 'black':
        return '#000000'
    if _HEX.match(v):
        return v
    m = _VAR.match(v)
    if m:
        vus = vus or set()
        if m.group(1) in vus:
            return None                      # var qui se pointe elle-meme
        vus.add(m.group(1))
        cible = tokens.get(m.group(1))
        return resoudre(cible, tokens, vus) if cible else None
    return None


# Une regle peut DECLARER que son contraste ne se calcule pas -- typiquement
# un texte pose sur une PHOTO, dont le fond n'est pas une couleur. La
# declaration porte sa raison, elle se relit et se conteste. Elle ne vaut que
# pour la regle qui la SUIT immediatement, et seulement si le couple est
# vraiment irresoluble : declarer hors portee ce qui se calcule serait une
# porte de sortie pour tout.
_HORS = re.compile(r'/\*\s*contraste\s*:\s*hors-portee\s*(.*?)\*/', re.S)


def exemptions(css):
    """{selecteur -> raison} pour les regles precedees d'une declaration."""
    out = {}
    for m in _HORS.finditer(css):
        raison = ' '.join(m.group(1).split()).lstrip('- ').strip()
        suite = css[m.end():]
        t = re.match(r'\s*([^{}]+)\{', suite)
        if t and raison:
            out[' '.join(t.group(1).split())] = raison
    return out


def regles(css):
    """[(selecteur, {prop: valeur})] -- a plat, at-regles comprises."""
    css = sans_commentaires(css)
    out = []
    for sel, corps in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        sel = ' '.join(sel.split())
        if not sel or sel.startswith('@'):
            continue
        d = {}
        for prop, val in _DECL.findall(corps):
            d[prop.strip().lower()] = val.strip()
        if d:
            out.append((sel, d))
    return out


def couples(css, tokens):
    """Les (selecteur, texte, fond) qu'un composant declare VRAIMENT.

    Le fond d'un selecteur peut venir d'une regle precedente (`.btn` pose le
    fond, `.btn--destructif` pose la couleur). On accumule donc par selecteur
    de base, comme le navigateur le fait -- en restant sur le cas simple
    qu'on sait tenir : meme selecteur, ou variante d'un selecteur deja vu.
    """
    etat, out, indecis = {}, [], []
    for sel, d in regles(css):
        base = sel.split(':')[0].split(' ')[0]
        herite = dict(etat.get(base.split('--')[0], {}))
        herite.update(etat.get(base, {}))
        for p in ('color', 'background', 'background-color'):
            if p in d:
                herite['background' if p.startswith('background') else p] = d[p]
        etat[base] = herite
        if 'color' not in herite:
            continue
        fg = resoudre(herite.get('color'), tokens)
        bg = resoudre(herite.get('background'), tokens)
        if fg is None or bg is None:
            indecis.append((sel, herite.get('color'), herite.get('background')))
            continue
        out.append((sel, fg, bg, herite.get('color')))
    # dedoublonne en gardant l'ordre
    vu, net = set(), []
    for c in out:
        if c not in vu:
            vu.add(c)
            net.append(c)
    return net, indecis


def famille(fg_brut):
    """Sur quelle famille de surfaces ce texte vit-il ?

    On ne le DEVINE pas a la luminance -- `--encre` est sombre et vit
    pourtant sur le noir. On le lit dans le NOM du token, qui le dit :
    `--texte-papier` et `--graphite-p` nomment leur surface, `--texte` et
    `--graphite` sont documentes « sur --salle ». Un token qui ne nomme rien
    (`--encre`, `--veilleuse`) peut vivre partout : on ne tranche pas, on
    prend le pire des deux mondes et on le DIT.
    """
    b = (fg_brut or '').lower()
    if 'papier' in b or re.search(r'--graphite-p\b', b):
        return SURFACES_CLAIRES, False
    if '--texte' in b or '--graphite' in b:
        return SURFACES_SOMBRES, False
    return SURFACES_SOMBRES + SURFACES_CLAIRES, True


def juger(sel, fg, bg, tokens, fg_brut=None):
    """Rend (ratio, surface_retenue, indetermine).

    Un fond `transparent` n'a pas de contraste : il en herite. Le pire cas
    fait foi -- un bouton a contour ne choisit pas son voisinage.
    """
    if bg in ('transparent', 'inherit', 'none'):
        noms, indetermine = famille(fg_brut if fg_brut is not None else fg)
        pires = [(contraste(fg, tokens[n]), n) for n in noms if n in tokens]
        if not pires:
            return None, None, False
        r, n = min(pires)
        return r, n, indetermine
    return contraste(fg, bg), None, False


def verifier(ui, ecrire=print):
    tokens = lire_tokens((ui / 'tokens.css').read_text(encoding='utf-8'))
    css = (ui / 'components.css').read_text(encoding='utf-8')
    return verifier_css(css, tokens, ecrire)


def verifier_css(css, tokens, ecrire=print):
    """Rend le nombre de GRIEFS : sous le seuil + non mesures.

    Un couple non mesure compte comme un grief. Le contraire -- rendre 0
    parce qu'on n'a pas su decider -- est la troncature silencieuse deguisee
    en exhaustivite, et ce banc l'a faite une fois.
    """
    cps, indecis = couples(css, tokens)
    exempt = exemptions(css)
    hors = [(sel, exempt[sel]) for sel, _f, _b in indecis if sel in exempt]
    indecis = [x for x in indecis if x[0] not in exempt]
    ecrire("# verifier_contraste -- %d tokens couleur, %d couples declares"
           % (len(tokens), len(cps)))
    ecrire("")
    sous, ok = [], 0
    for sel, fg, bg, fg_brut in cps:
        r, surface, indetermine = juger(sel, fg, bg, tokens, fg_brut)
        if r is None:
            indecis.append((sel, fg, bg))
            continue
        ou = ""
        if surface:
            ou = " sur %s (pire cas%s)" % (
                surface, ", surface INDETERMINEE" if indetermine else "")
        if r < SEUIL_TEXTE:
            sous.append((sel, fg, bg, r, ou))
            ecrire("  %-24s %5.2f:1  SOUS %.1f   %s sur %s%s"
                   % (sel, r, SEUIL_TEXTE, fg, bg, ou))
        else:
            ok += 1
    if not sous:
        ecrire("  Les %d couples mesures tiennent le seuil AA de %.1f:1."
               % (ok, SEUIL_TEXTE))
    ecrire("")
    if hors:
        ecrire("HORS PORTEE, DECLARE dans le CSS (%d) :" % len(hors))
        for sel, raison in hors:
            # Coupee pour la lisibilite -- et la coupe SE VOIT. La raison
            # entiere vit dans le CSS, a cote de la regle qu'elle exempte.
            if len(raison) > 96:
                raison = raison[:96] + " [... suite dans components.css]"
            ecrire("  %-24s %s" % (sel, raison))
        ecrire("")
    if indecis:
        ecrire("NON DECIDABLES (%d) -- comptes, pas tus :" % len(indecis))
        for sel, fg, bg in indecis:
            ecrire("  %-24s color=%s background=%s" % (sel, fg, bg))
        ecrire("")
    ecrire("PORTEE : tokens.css et components.css. Les couleurs ecrites dans")
    ecrire("les <style> des onze pages ne sont PAS jugees ici -- un vert")
    ecrire("partiel ne doit pas se lire comme un vert general.")
    ecrire("")
    if sous:
        ecrire("VERDICT : %d couple(s) sous le plancher, %d au-dessus, %d non"
               " mesure(s)." % (len(sous), ok, len(indecis)))
        ecrire("Le plancher dit : toute nouvelle couleur verifiee. Changer un")
        ecrire("token ripple sur les onze pages : c'est une DECISION, pas un")
        ecrire("correctif.")
    elif indecis:
        ecrire("VERDICT : rien sous le plancher PARMI LES %d COUPLES MESURES,"
               " mais" % ok)
        ecrire("%d n'ont pas pu l'etre. Ce n'est pas un plancher tenu, c'est"
               " un" % len(indecis))
        ecrire("plancher partiellement regarde.")
    else:
        ecrire("VERDICT : le plancher AA tient sur les %d couples declares,"
               " tous mesures." % ok)
    return len(sous) + len(indecis)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--ui', default='ui')
    a = p.parse_args(argv)
    ui = Path(a.ui)
    if not (ui / 'tokens.css').is_file():
        print("pas de %s/tokens.css -- rien n'a pu etre mesure, et ce n'est"
              " pas un feu vert." % ui)
        return 2
    return 1 if verifier(ui) else 0


if __name__ == '__main__':
    sys.exit(main())
