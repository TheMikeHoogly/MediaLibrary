"""Le plancher tactile, COMPTE au lieu d'etre souhaite.

<< Cibles tactiles >= 44 px >> est ecrit dans le plancher d'accessibilite
depuis le premier jour et n'a JAMAIS ete compte. C'est exactement l'histoire
du contraste (25/08) et des controles (26/08) : deux points ecrits comme des
regles, instrumentes apres coup, et deux fois sur deux avec des manquements
reels au bout. Un cas est deja tombe par hasard le 26/08 : `browse` declare
`.fxtoast .b { min-height: 36px }`.

Ce qu'il mesure
---------------
La taille DECLAREE, dans la cascade a QUATRE etages (components.css au
marqueur -> le <style> de la page -> tokens.css -> base.css), de chaque
element interactif des pages de `ui/pages`. Il resout `var(--touch)` depuis
`:root` et compare.

Le piege qui a rendu ce banc necessaire
---------------------------------------
Une hauteur declaree n'est pas une hauteur OBTENUE. Un `<span>` est `inline`
par defaut, et un element inline NON REMPLACE ignore `min-height` : la regle
est ecrite, elle est lue, elle ne fait rien. C'est ce qui dormait dans
`gallery` -- des chips de filtre en `<span>` que le CSS croyait tenir. Un
instrument qui lirait la valeur sans lire le `display` aurait rendu VERT la
page la plus utilisee du site.

Ce qu'il refuse d'affirmer
--------------------------
1. **La taille CALCULEE.** Une boite dont la hauteur vient de son contenu
   (interligne + padding + bordure) n'est pas mesurable dans le texte : il
   faudrait le navigateur. Elle est comptee TAILLE NON DECLAREE, jamais
   verte. Rendre vert ce qu'on n'a pas pu regarder est la troncature
   silencieuse deguisee en exhaustivite (`verifier_contraste`, 25/08).
2. **La LARGEUR.** WCAG 2.5.8 porte sur les deux dimensions ; cet instrument
   ne lit que la HAUTEUR. Raison : la largeur d'un bouton vient presque
   toujours de son contenu et de son padding, donc de la mesure du texte --
   elle serait NON DECLAREE partout et le rapport ne dirait plus rien. Angle
   mort assume, pas oublie.
3. **L'ANCETRE, la ou il n'est pas ecrit.** Dans le HTML STATIQUE
   l'imbrication est lue, donc `.actbar .b` se prouve et `.fxtoast .b` se
   refute. Dans un fragment assemble en JS, le contexte n'existe pas : la
   regle a combinateur y reste CONDITIONNELLE, et supposer un ancetre serait
   inventer une preuve. Quand deux lectures possibles ne donnent pas le meme
   VERDICT, l'element est NON DECIDABLE -- et un non-decidable compte comme
   un grief.
4. **Les regles d'ETAT** (`:hover`, `:active`, `:focus`, `:disabled`) et les
   PSEUDO-ELEMENTS (`::before`) ne dimensionnent pas la cible au repos : ils
   sont ecartes du calcul, et ce retrait est dit ici.
5. **Ce que le serveur injecte a l'execution** n'est pas lu : la portee est
   le HTML tel qu'ECRIT, y compris celui qui vit dans les chaines JS.

Ce qui ne se calcule pas se DECLARE
-----------------------------------
Une cible peut etre legitimement petite. La raison ne s'invente pas depuis
le texte : elle se declare A COTE DE L'ELEMENT, dans la source --
`<!-- cible: hors-portee -- raison -->` ou `/* cible: ok -- raison */` dans
une chaine JS. JAMAIS en dur dans l'instrument, sinon il devient aveugle au
cas suivant sans qu'on le sache. Les declarations sont COMPTEES et listees :
une exception qui prolifere n'en est plus une.

Ce qu'il ne fait pas
--------------------
Il ne modifie aucun fichier : famille `verifier_`, lecture seule.

Usage : python verifier_cibles.py [--pages ui/pages] [--ui ui] [--page gallery]
SORTIE EN ASCII PUR (console cp1252 de l'agent des bancs).
"""

import argparse
import re
import sys
from pathlib import Path

import verifier_controles as vct
import verifier_css_cascade as vcc

RACINE = Path(__file__).resolve().parent

MARQUEUR = '<!--UI:components-->'

# L'ordre de la cascade a QUATRE etages (25/08). components.css vit AU
# MARQUEUR, donc AVANT le <style> de la page ; tokens.css et base.css sont
# injectes a </head>, donc APRES -- base.css gagne les egalites.
ETAGES = ('components.css', 'page', 'tokens.css', 'base.css')

# Un element inline NON REMPLACE ignore `min-height`. Un element REMPLACE
# (l'image, le champ) a une boite propre : il l'honore meme en inline.
REMPLACES = {'img', 'input', 'select', 'textarea', 'video', 'canvas',
             'iframe', 'embed', 'object', 'svg'}

# `display` par defaut, reduit a ce qui change l'issue : honore-t-il une
# hauteur ? Tout ce qui n'est pas ici est traite comme `block`.
DISPLAY_DEFAUT = {
    'a': 'inline', 'span': 'inline', 'label': 'inline', 'em': 'inline',
    'strong': 'inline', 'b': 'inline', 'i': 'inline', 'small': 'inline',
    'code': 'inline', 'kbd': 'inline', 'abbr': 'inline', 'u': 'inline',
    'button': 'inline-block', 'input': 'inline-block',
    'select': 'inline-block', 'textarea': 'inline-block',
    'img': 'inline', 'svg': 'inline',
    'summary': 'list-item',
}

ETATS = (':hover', ':active', ':focus', ':focus-visible', ':disabled',
         ':target', ':checked')

LISTE_MAX = 60


# --------------------------------------------------------------------------
# Le selecteur : son sujet, son poids, ce qu'il touche
# --------------------------------------------------------------------------

_COMBINATEURS = ('>', '+', '~')


def _hors_parentheses(sel):
    """Positions des caracteres de `sel` qui ne sont ni entre parentheses ni
    entre crochets ni dans une chaine. Un `>` dans `:not(a > b)` n'est pas un
    combinateur, et un espace dans `[alt="deux mots"]` n'en est pas un."""
    prof, quote, out = 0, '', []
    for i, c in enumerate(sel):
        if quote:
            if c == quote:
                quote = ''
            out.append(False)
            continue
        if c in '"\'':
            quote = c
            out.append(False)
            continue
        if c in '([':
            prof += 1
            out.append(False)
            continue
        if c in ')]':
            prof = max(0, prof - 1)
            out.append(False)
            continue
        out.append(prof == 0)
    return out


def composes(sel):
    """Le selecteur decoupe en composes, dans l'ordre : `.a > b .c` -> 3."""
    libre = _hors_parentheses(sel)
    morceaux, courant = [], []
    for i, c in enumerate(sel):
        if libre[i] and (c.isspace() or c in _COMBINATEURS):
            if courant:
                morceaux.append(''.join(courant))
                courant = []
            continue
        courant.append(c)
    if courant:
        morceaux.append(''.join(courant))
    return morceaux


def sujet(sel):
    """Le COMPOSE qui designe l'element style : le dernier."""
    m = composes(sel)
    return m[-1] if m else ''


_MORCEAU = re.compile(
    r'(::[\w-]+(?:\([^)]*\))?)'          # pseudo-element
    r'|(:[\w-]+(?:\([^)]*\))?)'          # pseudo-classe
    r'|(\[[^\]]*\])'                     # attribut
    r'|(\.[-\w]+)'                       # classe
    r'|(#[-\w]+)'                        # identifiant
    r'|(\*)'                             # universel
    r'|([A-Za-z][-\w]*)')                # balise


def morceaux(compose):
    """[(genre, texte)] -- genre dans 'pe','pc','attr','classe','id','univ',
    'balise'. Ce qui ne se reconnait pas remonte en ('inconnu', texte)."""
    out, i, n = [], 0, len(compose)
    while i < n:
        m = _MORCEAU.match(compose, i)
        if not m:
            out.append(('inconnu', compose[i:]))
            break
        genres = ('pe', 'pc', 'attr', 'classe', 'id', 'univ', 'balise')
        for g, t in zip(genres, m.groups()):
            if t is not None:
                out.append((g, t))
                break
        i = m.end()
    return out


def specificite(sel):
    """(a, b, c) au sens CSS, sur le selecteur ENTIER."""
    a = b = c = 0
    for comp in composes(sel):
        for genre, texte in morceaux(comp):
            if genre == 'id':
                a += 1
            elif genre in ('classe', 'attr'):
                b += 1
            elif genre == 'pc':
                nom = texte.split('(')[0]
                if nom == ':not' or nom == ':is' or nom == ':has':
                    # Le poids de `:not(X)` est celui de X.
                    dedans = texte[texte.find('(') + 1:-1] if '(' in texte \
                        else ''
                    if dedans:
                        da, db, dc = specificite(dedans)
                        a, b, c = a + da, b + db, c + dc
                elif nom in (':where',):
                    pass
                else:
                    b += 1
            elif genre == 'balise':
                c += 1
            elif genre == 'pe':
                c += 1
    return (a, b, c)


_ATTR = re.compile(r'\[\s*([-\w]+)\s*(?:([~|^$*]?=)\s*'
                   r'(?:"([^"]*)"|\'([^\']*)\'|([^\]\s]*))\s*)?\]')


def _valeur_attr(attrs, nom):
    m = re.search(r'\b%s\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))'
                  % re.escape(nom), attrs, re.I)
    if not m:
        return None
    return m.group(1) if m.group(1) is not None else \
        (m.group(2) if m.group(2) is not None else m.group(3))


def touche(compose, elem):
    """Le compose designe-t-il cet element ? Rend True / False / None.

    None = l'instrument ne sait pas trancher (pseudo-classe structurelle,
    morceau non reconnu). None n'est pas False : il ne se compte pas vert."""
    verdict = True
    for genre, texte in morceaux(compose):
        if genre == 'balise':
            if texte.lower() != elem['balise']:
                return False
        elif genre == 'classe':
            if texte[1:] not in elem['classes']:
                return False
        elif genre == 'id':
            if texte[1:] != elem['id']:
                return False
        elif genre == 'univ':
            continue
        elif genre == 'attr':
            m = _ATTR.match(texte)
            if not m:
                verdict = None
                continue
            nom, op = m.group(1), m.group(2)
            attendu = m.group(3) or m.group(4) or m.group(5) or ''
            vu = _valeur_attr(elem['attrs'], nom)
            if vu is None:
                return False
            if op == '=' and vu != attendu:
                return False
            if op == '~=' and attendu not in vu.split():
                return False
            if op == '^=' and not vu.startswith(attendu):
                return False
            if op == '$=' and not vu.endswith(attendu):
                return False
            if op == '*=' and attendu not in vu:
                return False
        elif genre == 'pc':
            nom = texte.split('(')[0]
            if nom == ':not' and '(' in texte:
                dedans = texte[texte.find('(') + 1:-1]
                d = touche(dedans, elem)
                if d is True:
                    return False
                if d is None:
                    verdict = None
            elif nom in ETATS:
                return False          # regle d'etat : hors dimensionnement
            else:
                verdict = None
        elif genre == 'pe':
            return False              # pseudo-element : autre boite
        else:
            verdict = None
    return verdict


# --------------------------------------------------------------------------
# Les valeurs : `var(--touch)` et les longueurs
# --------------------------------------------------------------------------

_VAR = re.compile(r'var\(\s*(--[-\w]+)\s*(?:,\s*([^()]*))?\)')
_PX = re.compile(r'^([+-]?\d*\.?\d+)(px)?$', re.I)


def resoudre(valeur, variables, profondeur=0):
    """`var(--touch)` -> `44px`. Rend None si la chaine ne se resout pas.

    Une variable non definie n'est pas 0 : c'est une inconnue. La rendre
    nulle ferait passer un plancher absent pour un plancher a zero, donc un
    grief pour un grief -- mais avec le mauvais motif, et le mauvais motif
    envoie chercher la panne ailleurs (lecon des 404 contre les refus de
    connexion, 25/08)."""
    if profondeur > 6:
        return None
    def rempl(m):
        nom, defaut = m.group(1), m.group(2)
        if nom in variables:
            return variables[nom]
        return defaut if defaut is not None else '\x00'
    vu = _VAR.sub(rempl, valeur)
    if '\x00' in vu:
        return None
    if vu != valeur:
        return resoudre(vu, variables, profondeur + 1)
    return vu


_CALC = re.compile(r'calc\(([^()]*)\)', re.I)


def _calc_px(dedans):
    """`calc(44px + 8px)` -> 52.0. Rend None des qu'une unite relative entre.

    Troisieme rouge observe (26/08) : `#uploadBtn` declare
    `calc(var(--touch) + var(--e-2))`. Une fois les variables resolues, c'est
    de l'arithmetique de pixels, et un instrument qui rend NON DECIDABLE une
    addition qu'il sait faire s'aveugle tout seul. Ce qui reste vraiment
    indecidable -- `calc(100% - 20px)`, `calc(2em * 3)` -- l'est encore."""
    jetons = dedans.replace('+', ' + ').replace('-', ' - ').split()
    if not jetons or len(jetons) % 2 == 0:
        return None
    total = _px_simple(jetons[0])
    if total is None:
        return None
    i = 1
    while i < len(jetons) - 1:
        op, suite = jetons[i], _px_simple(jetons[i + 1])
        if suite is None or op not in ('+', '-'):
            return None
        total = total + suite if op == '+' else total - suite
        i += 2
    return total


def _px_simple(v):
    v = v.strip().lower()
    if v in ('0', '0px'):
        return 0.0
    m = _PX.match(v)
    return float(m.group(1)) if (m and m.group(2)) else None


def longueur_px(valeur):
    """La valeur en pixels, ou None si elle n'est pas une longueur absolue.

    `calc()`, `%`, `em`, `vh` : le pixel depend du contexte ou de la police,
    donc du navigateur. Non decidable, pas zero."""
    v = valeur.strip().lower()
    m = _CALC.fullmatch(v)
    if m:
        return _calc_px(m.group(1))
    return _px_simple(v)


# --------------------------------------------------------------------------
# La cascade, appliquee a UN element
# --------------------------------------------------------------------------

def regles_de_page(html, feuilles):
    """[(etage, rang, contexte, selecteur, propriete, valeur, important)].

    `feuilles` : {nom -> texte}. components.css n'entre QUE si la page pose
    son marqueur -- c'est un opt-in, et l'ignorer ferait juger cinq pages sur
    des regles qu'elles ne recoivent pas."""
    out = []
    sources = []
    if MARQUEUR in html:
        sources.append(('components.css', feuilles.get('components.css', '')))
    sources.append(('page', vcc.styles_de_page(html)))
    sources.append(('tokens.css', feuilles.get('tokens.css', '')))
    sources.append(('base.css', feuilles.get('base.css', '')))
    for etage, (nom, css) in enumerate(sources):
        if not css:
            continue
        regles, _opaques, _nd = vcc.analyser(css, source=nom)
        for r in regles:
            out.append({'etage': etage, 'nom': nom, 'rang': r['ordre'],
                        'contexte': r['contexte'], 'selecteur': r['selecteur'],
                        'propriete': r['propriete'], 'valeur': r['valeur'],
                        'important': r['important']})
    return out


def variables_racine(regles):
    """Les customs de `:root` / `html` / `*`, cascade la plus simple : le
    dernier ecrit gagne, `!important` bat le reste."""
    out, poids = {}, {}
    for r in regles:
        if not r['propriete'].startswith('--'):
            continue
        s = r['selecteur'].strip()
        if s not in (':root', 'html', ':root,html', '*'):
            continue
        cle = r['propriete']
        p = (1 if r['important'] else 0, r['etage'], r['rang'])
        if cle not in poids or p >= poids[cle]:
            poids[cle] = p
            out[cle] = r['valeur']
    return out


VIDES = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
         'link', 'meta', 'param', 'source', 'track', 'wbr'}

_TOUTE_BALISE = re.compile(r'<(/?)([A-Za-z][\w-]*)\b([^<>]*?)(/?)>', re.S)


def _descripteur(balise, attrs):
    return {'balise': balise, 'attrs': attrs,
            'classes': set((_valeur_attr(attrs, 'class') or '').split()),
            'id': _valeur_attr(attrs, 'id') or '', 'style': ''}


def avec_ancetres(source):
    """[(pos, balise, attrs, ancetres)] -- l'imbrication du HTML STATIQUE.

    Deuxieme rouge observe (26/08), et le plus couteux : `browse` declare
    `.actbar .b { min-height: var(--touch) }` PUIS `.fxtoast .b
    { min-height: 36px }`. Juge sur le seul SUJET `.b`, l'instrument ne
    pouvait que tirer a pile ou face -- il a pris la derniere ecrite et
    accuse cinq boutons de 44 px d'en faire 36. Lire l'ancetre n'est pas un
    raffinement : sans lui, deux regles de meme poids rendent un verdict au
    hasard, et un verdict au hasard est pire qu'un aveu d'ignorance.
    """
    out, pile = [], []
    for m in _TOUTE_BALISE.finditer(source):
        fermante, balise, attrs, auto = m.groups()
        balise = balise.lower()
        if fermante:
            for k in range(len(pile) - 1, -1, -1):
                if pile[k]['balise'] == balise:
                    del pile[k:]
                    break
            continue
        out.append((m.start(), balise, attrs, list(pile)))
        if balise not in VIDES and not auto:
            pile.append(_descripteur(balise, attrs))
    return out


def _combinateurs(sel):
    """[(combinateur, compose)] de gauche a droite ; le premier est ''."""
    libre = _hors_parentheses(sel)
    out, courant, comb = [], [], ''
    i = 0
    while i < len(sel):
        c = sel[i]
        if libre[i] and (c.isspace() or c in _COMBINATEURS):
            if courant:
                out.append((comb, ''.join(courant)))
                courant, comb = [], ' '
            if c in _COMBINATEURS:
                comb = c
            i += 1
            continue
        courant.append(c)
        i += 1
    if courant:
        out.append((comb, ''.join(courant)))
    return out


def regle_touche(sel, elem):
    """True / False / None -- None = l'instrument ne sait pas.

    L'ancetre n'est lu que dans le HTML STATIQUE : un fragment assemble en
    JS ne porte pas son contexte, et supposer le sien serait inventer une
    preuve. Ces cas restent CONDITIONNELS, et se disent."""
    parts = _combinateurs(sel)
    if not parts:
        return None
    d = touche(parts[-1][1], elem)
    if d is not True:
        return d
    if len(parts) == 1:
        return True
    complete = elem.get('chaine') == 'complete'
    chaine = elem['ancetres']
    i = len(chaine) - 1
    # De droite a gauche : le combinateur qui precede le compose `k` dit
    # comment le compose `k-1` doit se placer dans la chaine d'ancetres.
    a_placer = [(parts[k][0], parts[k - 1][1])
                for k in range(len(parts) - 1, 0, -1)]
    for comb, comp in a_placer:
        if comb in ('+', '~'):
            return None
        if comb == '>':
            if i < 0:
                return False if complete else None
            t = touche(comp, chaine[i])
            if t is None:
                return None
            if t is False:
                return False if complete else None
            i -= 1
            continue
        trouve = None
        for k in range(i, -1, -1):
            t = touche(comp, chaine[k])
            if t is None:
                return None
            if t is True:
                trouve = k
                break
        if trouve is None:
            return False if complete else None
        i = trouve - 1
    return True


def _applicables(regles, elem, propriete):
    """[(poids, conditionnelle, regle)] pour cette propriete et cet element.

    `conditionnelle` : la regle a un combinateur (l'ancetre n'est pas
    prouvable) ou une pseudo-classe que l'instrument ne sait pas trancher."""
    out = []
    for r in regles:
        if r['propriete'] != propriete:
            continue
        sel = r['selecteur']
        if '::' in sel:
            continue
        d = regle_touche(sel, elem)
        if d is False:
            continue
        conditionnelle = d is None
        poids = (1 if r['important'] else 0) , specificite(sel), \
            (r['etage'], r['rang'])
        out.append((poids, conditionnelle, r))
    return out


def candidats(regles, elem, propriete):
    """[(valeur, source)] -- toutes les lectures possibles de cette propriete.

    La premiere, s'il y en a une, est la meilleure regle dont l'instrument
    PROUVE qu'elle touche cet element. Viennent ensuite toutes les regles qui
    la DEPASSENT en cascade sans etre prouvables (un ancetre inconnu, une
    pseudo-classe structurelle) : chacune pourrait etre la vraie gagnante si
    celles au-dessus d'elle ne s'appliquent pas.

    Rendre la LISTE et non le maximum est ce qui empeche le tirage a pile ou
    face : entre `.actbar .b { 44px }` et `.fxtoast .b { 36px }`, tous deux
    de poids (0,2,0), << la derniere ecrite gagne >> n'est vrai que si les
    deux s'appliquent. Quand on ne sait pas, on ne classe pas -- on garde les
    deux et on regarde si elles disent la meme chose du plancher.
    """
    if elem['style']:
        m = re.search(r'(?:^|;)\s*%s\s*:\s*([^;]+)'
                      % re.escape(propriete), elem['style'], re.I)
        if m:
            return [(m.group(1).strip(), 'style=', True)]
    cands = _applicables(regles, elem, propriete)
    if not cands:
        return []
    sures = [c for c in cands if not c[1]]
    m_sure = max(sures, key=lambda c: c[0]) if sures else None

    def dit(c, sur):
        r = c[2]
        return (r['valeur'], '%s %s' % (r['nom'], r['selecteur']), sur)

    out = [dit(m_sure, True)] if m_sure else []
    for c in cands:
        if c[1] and (m_sure is None or c[0] > m_sure[0]):
            v = dit(c, False)
            if v not in out:
                out.append(v)
    return out


def honore_la_hauteur(display, balise):
    """Un `min-height` sur cet element fait-il quelque chose ?

    C'est LA question du banc. Un element inline non remplace l'ignore --
    la regle est ecrite, elle est lue, elle ne fait rien."""
    if display == 'none':
        return None                      # pas peint : autre categorie
    if display in ('inline', 'contents'):
        return balise in REMPLACES
    return True


# --------------------------------------------------------------------------
# Les elements interactifs, tels qu'ECRITS
# --------------------------------------------------------------------------

_BALISE = re.compile(r'<([A-Za-z][\w-]*)\b([^<>]*)', re.S)

NATIVES = ('button', 'select', 'textarea', 'summary')


def genre_interactif(balise, attrs):
    """Pourquoi cet element est une cible -- ou '' s'il n'en est pas une."""
    if balise in NATIVES:
        return 'natif'
    if balise == 'input':
        t = (_valeur_attr(attrs, 'type') or 'text').lower()
        return '' if t == 'hidden' else 'natif'
    if balise == 'a' and re.search(r'\bhref\s*=', attrs, re.I):
        return 'lien'
    if balise == 'label' and re.search(r'\bfor\s*=', attrs, re.I):
        # Le vrai cliquable quand le champ est `.hors-ecran` derriere lui :
        # c'est ce motif qui cachait les deux actions principales du site.
        return 'label'
    if re.search(r'\bonclick\s*=', attrs, re.I):
        return 'clic'
    if re.search(r'\brole\s*=\s*["\']button["\']', attrs, re.I):
        return 'role'
    if re.search(r'\btabindex\s*=\s*["\']0["\']', attrs, re.I):
        return 'tabindex'
    return ''


_DECLARES = (
    re.compile(r'/\*\s*cible\s*:\s*(hors-portee|ok)\s*(?:--)?\s*(.*?)\*/',
               re.S),
    re.compile(r'<!--\s*cible\s*:\s*(hors-portee|ok)\s*(?:--)?\s*(.*?)-->',
               re.S),
    re.compile(r'//\s*cible\s*:\s*(hors-portee|ok)\s*(?:--)?\s*([^\n]*)'),
)

PORTEE_DECLARATION = 900   # octets : au-dela, << la suivante >> ne veut
                           # plus rien dire


def declarations(source):
    """[(fin, genre, raison)] triees -- lues dans le source BRUT.

    Elles vivent dans des commentaires : les lire APRES les avoir retires
    reviendrait a ne jamais les lire. C'est l'exception a << retirer les
    commentaires avant de lire >>, et elle est volontaire (25/08).

    Le commentaire de bloc se ferme sur `*/`, pas sur la premiere fin de
    ligne : une raison tient rarement sur soixante colonnes, et une raison
    tronquee est une raison qu'on ne relira pas."""
    out = []
    for motif in _DECLARES:
        for m in motif.finditer(source):
            raison = ' '.join(m.group(2).split()).strip(' -')
            if raison:
                out.append((m.end(), m.group(1), raison))
    out.sort()
    return out


def attribuer_declarations(decls, elems):
    """Chaque declaration couvre le PROCHAIN element interactif, un seul.

    Sixieme rouge observe (26/08) : liee a tout ce qui la suivait dans un
    rayon d'octets, une declaration posee sur une case a cocher exemptait
    aussi le bouton << Valider >> ecrit trois lignes plus bas. Une exception
    qui deborde n'est plus une exception, c'est un trou."""
    par_pos = sorted(elems, key=lambda e: e['pos'])
    for fin, genre, raison in decls:
        for e in par_pos:
            if e['pos'] < fin:
                continue
            if e['pos'] - fin > PORTEE_DECLARATION:
                break
            if e['declaration'] is None:
                e['declaration'] = (genre, raison)
            break


def elements(nom, brut):
    """Les cibles d'une page : le HTML statique ET celui des chaines JS.

    Le HTML assemble en JS n'est pas moins du HTML -- les chips de filtre de
    `gallery` n'existent que la. Ne lire que le statique rendrait la page la
    plus utilisee du site invisible a son propre banc.

    Ce qui les separe : le STATIQUE porte son imbrication ENTIERE, donc une
    regle a combinateur s'y prouve ET s'y refute. Un fragment JS porte la
    sienne PARTIELLEMENT -- `html += \'<label class="prop"><input ...\'` dit
    bien que l\'input est dans un `.prop`, mais rien de ce qui est au-DESSUS
    du fragment. Une regle y est donc prouvable et jamais refutable : ne pas
    trouver l\'ancetre dans le connu ne dit pas qu\'il n\'existe pas.

    Quatrieme rouge observe (26/08) : sans cette distinction, `.prop input
    { height: 18px }` -- une case a cocher posee sur une vignette -- etait
    portee au credit d\'un `<input type="number">` ecrit cent lignes plus
    loin, dans une phrase. Deux defauts opposes sous le meme verdict, et le
    mauvais motif envoie chercher la panne au mauvais endroit.
    """
    hors, js = vct.decouper(brut)
    hors = vct.sans_commentaires_html(hors)
    chaines = vct.chaines_seules(js)
    decls = declarations(brut)
    out = []

    def ajouter(source, ou, pos, balise, attrs, ancetres, chaine):
        genre = genre_interactif(balise, attrs)
        if not genre:
            return
        out.append({
            'page': nom, 'balise': balise, 'attrs': attrs,
            'classes': set((_valeur_attr(attrs, 'class') or '').split()),
            'id': _valeur_attr(attrs, 'id') or '',
            'style': _valeur_attr(attrs, 'style') or '',
            'genre': genre, 'ou': ou, 'pos': pos,
            'ancetres': ancetres, 'chaine': chaine,
            'ligne': vct.ligne_de(source, pos),
            'declaration': None,
        })

    for pos, balise, attrs, ancetres in avec_ancetres(hors):
        ajouter(hors, 'html', pos, balise, attrs, ancetres, 'complete')
    for pos, balise, attrs, ancetres in avec_ancetres(chaines):
        ajouter(chaines, 'js', pos, balise, attrs, ancetres, 'partielle')
    attribuer_declarations(decls, out)
    out.sort(key=lambda e: e['ligne'])
    return out


# --------------------------------------------------------------------------
# Le jugement
# --------------------------------------------------------------------------

def _juge_hauteur(prop, valeur, source, display, elem, plancher):
    """Le verdict d'UNE candidate. (verdict, detail)."""
    honore = honore_la_hauteur(display, elem['balise'])
    if honore is False:
        return ('INERTE', '%s: %s (%s) -- display: %s l ignore'
                % (prop, valeur, source, display))
    px = longueur_px(resoudre(valeur, plancher['variables']) or '')
    if px is None:
        return ('NON DECIDABLE', '%s: %s (%s) ne se resout pas en pixels'
                % (prop, valeur, source))
    if px + 0.001 < plancher['px']:
        return ('SOUS', '%s: %s = %gpx (%s)' % (prop, valeur, px, source))
    return ('OK', '%s: %s = %gpx (%s)' % (prop, valeur, px, source))


def juger(elem, regles, plancher):
    """(verdict, detail). Verdicts :

    OK            plancher declare et honore, >= --touch
    SOUS          plancher declare et honore, < --touch
    INERTE        plancher declare mais le `display` l'ignore
    NON DECLARE   aucune hauteur : le CONTENU decide, le texte ne sait pas
    NON DECIDABLE deux lectures possibles qui ne donnent pas le meme verdict
    HORS ECRAN    `.hors-ecran` : retire de la peinture, pas du document
    NON PEINT     `display: none`
    DECLARE       exception ecrite dans la source, avec sa raison

    Premier rouge que l'instrument s'est donne (26/08) : il comparait le
    TEXTE de deux valeurs. `.cl .row .btn { min-height: 44px }` et
    `.btn { min-height: var(--touch) }` sont la MEME hauteur ecrite de deux
    facons -- il rendait 52 non-decidables sur 192 cibles, dont aucune ne
    l'etait. Ce qui doit s'accorder n'est pas la valeur, c'est le VERDICT :
    tant que les deux lectures tombent du meme cote du plancher, savoir si
    l'ancetre est la ne change rien.
    """
    if elem['declaration']:
        genre, raison = elem['declaration']
        return ('DECLARE', '%s -- %s' % (genre, raison))
    if 'hors-ecran' in elem['classes']:
        return ('HORS ECRAN', 'retire de la peinture, le label voisin est la'
                              ' cible')

    defaut = (DISPLAY_DEFAUT.get(elem['balise'], 'block'), 'defaut')
    vus = candidats(regles, elem, 'display')
    displays = [(v.split()[0].lower(), src) for v, src, _s in vus]
    if not displays:
        displays = [defaut]
    elif not any(sur for _v, _s, sur in vus):
        # Aucune regle PROUVEE : que rien ne s'applique reste possible, et
        # alors c'est le `display` par defaut de la balise qui vaut.
        displays.append(defaut)
    if len({honore_la_hauteur(d, elem['balise']) for d, _s in displays}) > 1:
        return ('NON DECIDABLE', 'display : %s'
                % ' contre '.join('%s (%s)' % d for d in displays))
    display = displays[0][0]
    if display == 'none':
        return ('NON PEINT', 'display: none (%s)' % displays[0][1])

    cands, prouvee = [], False
    for prop in ('min-height', 'height'):
        vus = candidats(regles, elem, prop)
        if not vus:
            continue
        cands = [(prop, v, src) for v, src, _s in vus]
        prouvee = any(sur for _v, _s, sur in vus)
        break
    if not cands:
        if elem['balise'] == 'a' and display in ('inline', 'contents'):
            # WCAG 2.5.8 exempte la cible << en ligne >> : un lien dans une
            # phrase ne peut pas faire 44 px sans casser l'interligne. Mais
            # l'instrument ne sait PAS distinguer un lien dans un texte d'un
            # lien qui sert de bouton -- il ne rend donc pas vert, il rend
            # une categorie NOMMEE, comptee et listee, a relire une fois a
            # l'oeil. Meme forme que le << SEMANTIQUE, PAS NIVEAU A >> de
            # verifier_controles : ce qui echappe au grief se montre.
            return ('LIEN EN LIGNE', 'lien inline : exception WCAG 2.5.8,'
                                     ' a relire a l oeil')
        return ('NON DECLARE', 'ni min-height ni height ; le contenu decide'
                               ' (display: %s)' % display)

    juges = [_juge_hauteur(pr, v, src, display, elem, plancher)
             for pr, v, src in cands]
    if not prouvee:
        # Cinquieme rouge observe (26/08) : une SEULE regle, non prouvable,
        # etait affirmee. `.prop input { height: 18px }` -- la case a cocher
        # d'une vignette -- condamnait un `<input type="number">` ecrit dans
        # une phrase, cent lignes plus loin. Quand rien n'est prouve, que
        # RIEN ne s'applique reste une lecture possible, et elle ne dit pas
        # la meme chose : << trop petit >> et << pas de plancher >> ne se
        # reparent pas au meme endroit.
        juges.append(('NON DECLARE', 'aucune regle prouvee ; que rien ne'
                                     ' s applique reste possible'))
    if len({j[0] for j in juges}) == 1:
        return juges[0]
    tete = juges[0]
    autre = next(j for j in juges if j[0] != tete[0])
    reste = len(juges) - 2
    return ('NON DECIDABLE', '%s %s CONTRE %s %s%s'
            % (tete[0], tete[1], autre[0], autre[1],
               ' (+%d lecture(s))' % reste if reste > 0 else ''))



GRIEFS = ('SOUS', 'INERTE', 'NON DECLARE', 'NON DECIDABLE')
EXEMPTS = ('DECLARE', 'HORS ECRAN', 'NON PEINT', 'LIEN EN LIGNE')


def analyser(nom, brut, feuilles):
    regles = regles_de_page(brut, feuilles)
    variables = variables_racine(regles)
    touch = resoudre('var(--touch)', variables)
    px = longueur_px(touch or '')
    plancher = {'variables': variables, 'px': px if px is not None else 44.0,
                'connu': px is not None}
    lus = elements(nom, brut)
    juges = []
    for e in lus:
        verdict, detail = juger(e, regles, plancher)
        juges.append((e, verdict, detail))
    return {'page': nom, 'plancher': plancher, 'elements': juges,
            'composants': MARQUEUR in brut}


def rapport(resultats, ecrire=print):
    ecrire("CIBLES TACTILES -- le point 3 du plancher, COMPTE")
    ecrire("")
    planchers = set()
    for r in resultats:
        planchers.add((r['plancher']['px'], r['plancher']['connu']))
    for val, connu in sorted(planchers):
        if connu:
            ecrire("Plancher lu dans :root : --touch = %gpx" % val)
        else:
            ecrire("ATTENTION : --touch INTROUVABLE dans :root. Le banc a"
                   " suppose %gpx." % val)
            ecrire("Un plancher suppose n'est pas un plancher mesure.")
    ecrire("")
    ecrire("  %-9s %-4s %5s %5s %5s %6s %6s %6s %5s"
           % ('page', 'comp', 'cible', 'ok', 'sous', 'inerte', 'nondec',
              'indec', 'exempt'))
    tot = dict.fromkeys(('OK',) + GRIEFS + EXEMPTS, 0)
    for r in resultats:
        c = dict.fromkeys(('OK',) + GRIEFS + EXEMPTS, 0)
        for _e, v, _d in r['elements']:
            c[v] += 1
            tot[v] += 1
        ecrire("  %-9s %-4s %5d %5d %5d %6d %6d %6d %5d"
               % (r['page'], 'oui' if r['composants'] else '-',
                  len(r['elements']), c['OK'], c['SOUS'],
                  c['INERTE'], c['NON DECLARE'], c['NON DECIDABLE'],
                  sum(c[g] for g in EXEMPTS)))
    n_cibles = sum(len(r['elements']) for r in resultats)
    ecrire("  %-9s %-4s %5d %5d %5d %6d %6d %6d %5d"
           % ('TOTAL', '', n_cibles, tot['OK'], tot['SOUS'], tot['INERTE'],
              tot['NON DECLARE'], tot['NON DECIDABLE'],
              sum(tot[g] for g in EXEMPTS)))
    ecrire("")

    for genre, titre in (
            ('SOUS', "SOUS LE PLANCHER (%d) : la hauteur est declaree,"
                     " honoree, et trop petite."),
            ('INERTE', "INERTE (%d) : la hauteur est declaree et le `display`"
                       " l'IGNORE."),
            ('NON DECIDABLE', "NON DECIDABLE (%d) : l'instrument ne sait pas"
                              " trancher -- compte comme un grief."),
            ('NON DECLARE', "TAILLE NON DECLAREE (%d) : le CONTENU decide."
                            " Le texte ne peut pas le savoir.")):
        lot = [(r['page'], e, d) for r in resultats
               for e, v, d in r['elements'] if v == genre]
        if not lot:
            continue
        ecrire(titre % len(lot))
        if genre == 'INERTE':
            ecrire("  C'est le piege qui a rendu ce banc necessaire : un")
            ecrire("  element inline non remplace ignore `min-height`.")
        for page, e, d in lot[:LISTE_MAX]:
            ecrire("  %-9s l.%-5d %-8s <%s> %s"
                   % (page, e['ligne'], e['genre'], e['balise'], d))
        if len(lot) > LISTE_MAX:
            ecrire("  ... et %d de plus, non listes (plafond %d)."
                   % (len(lot) - LISTE_MAX, LISTE_MAX))
        ecrire("")

    decl = [(r['page'], e, d) for r in resultats
            for e, v, d in r['elements'] if v == 'DECLARE']
    if decl:
        ecrire("DECLAREES DANS LA SOURCE (%d) : une exception ecrite, avec sa"
               % len(decl))
        ecrire("  raison. Leur nombre se surveille -- une exception qui")
        ecrire("  prolifere n'en est plus une.")
        for page, e, d in decl[:LISTE_MAX]:
            ecrire("  %-9s l.%-5d <%s> %s"
                   % (page, e['ligne'], e['balise'],
                      d if len(d) <= 62 else d[:59] + '...'))
        ecrire("")
    for genre, titre in (('HORS ECRAN', "HORS ECRAN (%d) : le label voisin"
                                        " porte la cible."),
                         ('LIEN EN LIGNE', "LIENS EN LIGNE (%d) : exception"
                          " WCAG 2.5.8. L'instrument ne sait PAS distinguer"
                          " un lien\n  dans une phrase d'un lien qui sert de"
                          " bouton : a relire a l'oeil, une fois."),
                         ('NON PEINT', "NON PEINT (%d) : `display: none`.")):
        lot = [(r['page'], e) for r in resultats
               for e, v, _d in r['elements'] if v == genre]
        if lot:
            ecrire(titre % len(lot))
            for page, e in lot[:LISTE_MAX]:
                ecrire("  %-9s l.%-5d <%s>" % (page, e['ligne'], e['balise']))
            ecrire("")

    sans_comp = [r['page'] for r in resultats if not r['composants']]
    ecrire("PORTEE : les %d page(s) LUES dans ui/pages, telles qu'ecrites,"
           % len(resultats))
    ecrire("dans la cascade a quatre etages. components.css n'entre que la ou")
    ecrire("le marqueur est pose -- absent de : %s."
           % (', '.join(sans_comp) if sans_comp else 'aucune'))
    ecrire("La HAUTEUR DECLAREE, jamais la hauteur calculee : une boite dont")
    ecrire("la hauteur vient de son contenu est comptee NON DECLAREE, pas")
    ecrire("verte. La LARGEUR n'est pas lue (elle vient du texte, elle serait")
    ecrire("non declaree partout). Un selecteur descendant est resolu par les")
    ecrire("ANCETRES la ou le HTML est statique ; dans un fragment assemble en")
    ecrire("JS le contexte n'existe pas, la regle y reste conditionnelle, et")
    ecrire("deux lectures de verdicts differents rendent l'element non")
    ecrire("decidable. Les regles d'etat (:hover, :active, :focus, :disabled)")
    ecrire("et les pseudo-elements sont ecartes du calcul.")
    ecrire("")
    a_traiter = sum(tot[g] for g in GRIEFS)
    prouves = tot['SOUS'] + tot['INERTE']
    seuil = resultats[0]['plancher']['px']
    if not a_traiter:
        ecrire("VERDICT : les %d cibles des %d pages lues declarent une"
               % (n_cibles, len(resultats)))
        ecrire("hauteur honoree d'au moins %gpx." % seuil)
    else:
        ecrire("VERDICT, en DEUX chiffres qui ne disent pas la meme chose :")
        ecrire("  %d manquement(s) PROUVE(s) : %d sous %gpx, %d inerte(s)."
               % (prouves, tot['SOUS'], seuil, tot['INERTE']))
        ecrire("  %d cible(s) dont le plancher n'est pas DECLARE, %d non"
               % (tot['NON DECLARE'], tot['NON DECIDABLE']))
        ecrire("  decidable(s) : le contenu decide, et le texte ne sait pas.")
        ecrire("  Ce n'est pas un feu vert. C'est la ou l'instrument s'arrete")
        ecrire("  -- et, page par page, la ou components.css n'est pas adopte.")
    return a_traiter


def feuilles_ui(dossier):
    d = Path(dossier)
    out = {}
    for nom in ('components.css', 'tokens.css', 'base.css'):
        f = d / nom
        out[nom] = f.read_text(encoding='utf-8') if f.is_file() else ''
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--pages', default=str(RACINE / 'ui' / 'pages'))
    p.add_argument('--ui', default=str(RACINE / 'ui'))
    p.add_argument('--page', default='', help='ne juger que celle-la')
    a = p.parse_args(argv)
    lues = vct.pages(a.pages, a.page)
    if not lues:
        print("aucune page dans %s -- rien n'a pu etre verifie, et ce n'est"
              " pas un feu vert." % a.pages)
        return 2
    feuilles = feuilles_ui(a.ui)
    if not feuilles.get('tokens.css'):
        print("tokens.css INTROUVABLE dans %s : le plancher n'a pas de"
              " valeur." % a.ui)
        return 2
    n = rapport([analyser(nom, html, feuilles) for nom, html in lues])
    return 1 if n else 0


if __name__ == '__main__':
    sys.exit(main())
