#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verifier_controles -- ce qui se CLIQUE doit etre un controle.

Pourquoi cet instrument existe
------------------------------
Le plancher d'accessibilite de `photo-ui` dit, point 5 :
"<button> pour agir, <a> pour naviguer, jamais <div onclick>". La phrase est
la depuis le debut. Comme le plancher AA avant le 25/08, personne ne l'avait
COMPTEE -- et le jour ou on regarde, `gallery` fabrique ses chips de
personnes en `document.createElement('span')` + `.onclick` : pas de
`tabindex`, pas de `role`, pas d'`aria-pressed`. Le filtre le plus utilise
de la page la plus utilisee est injoignable au clavier. `subjects` ecrit
`<button class="chip" aria-pressed>` au meme endroit : correct. La
divergence n'est pas visuelle, elle est SEMANTIQUE -- donc invisible a
l'oeil, et invisible a une relecture qui ne cherche pas.

WCAG 2.1.1 (niveau A) : toute fonctionnalite doit etre operable au clavier.
Un `<span onclick>` ne recoit jamais le focus, ne repond ni a Entree ni a
Espace, et n'est annonce comme rien par un lecteur d'ecran.

Ce qu'il fait
-------------
Pour chacune des onze pages de `ui/pages/`, il apparie chaque element
CLIQUABLE a la balise qui le porte, et compte ceux qui ne sont pas des
controles. Trois sources, parce que le defaut se cache dans les trois :

  1. l'attribut `onclick=` ecrit dans le HTML ;
  2. le meme attribut ecrit dans une chaine HTML assemblee en JS
     (`innerHTML`) -- le HTML n'est pas moins du HTML pour etre passe par
     une chaine ;
  3. `X.onclick = ...` / `X.addEventListener('click', ...)` en JS, la cible
     etant remontee soit a son `document.createElement('tag')`, soit a
     l'`id` du HTML statique.

Un element non natif peut avoir ete rendu operable a la main. L'instrument
le cherche sur la MEME variable (`role`, `tabindex`, `keydown`) et le classe
a part : BRICOLE n'est pas NATIF, et ce n'est pas non plus un grief.

Ce qu'il refuse d'affirmer
--------------------------
1. **La DELEGATION.** `d1.onclick = function(ev){ if (ev.target...) }` pose
   le gestionnaire sur un conteneur : le cliquable reel est ailleurs, et
   aucune lecture statique ne dit ou. Ces cas sont NOMMES, jamais comptes
   verts d'office.
2. **Ce qu'il n'a pas su remonter.** Une cible dont la balise reste inconnue
   (variable jamais passee par `createElement`, `id` absent du HTML
   statique, `querySelector` sur un selecteur construit) est comptee dans
   les NON DECIDABLES -- et un non-decidable compte comme un grief. Rendre 0
   parce qu'on n'a pas su regarder est la troncature silencieuse deguisee en
   exhaustivite ; ce projet l'a payee une fois (`verifier_contraste`, 25/08).
3. **Les litteraux d'expression reguliere JS** (`/ab+c/`) : angle mort
   NOMME ici comme theorique, puis trouve REEL et FERME le 26/08. Le `"` de
   `/[&<>"]/g`, en tete de `subjects`, ouvrait une fausse chaine et faisait
   disparaitre un bouton ecrit cent lignes plus bas. Le scanner distingue
   desormais une regex d'une division (`_AVANT_REGEX`). Ce paragraphe reste
   pour ce qu'il enseigne : NOMMER un angle mort dit ou l'on ne voit pas, ca
   ne fait pas voir -- et une portee qui se sous-estime fait re-faire un
   correctif qui existe.
4. **Il ne juge pas la PERTINENCE du controle.** `<a href="#">` qui agit au
   lieu de naviguer est operable au clavier : ce n'est pas un grief de
   niveau A, c'est un choix semantique. Compte a part, jamais tu.
5. **Portee : le HTML de `ui/pages/`, tel qu'ecrit.** Ni ce que le serveur
   injecte, ni ce que le navigateur calcule. Un vert partiel ne se lit pas
   comme un vert general.

Ce qu'il ne fait pas
--------------------
Il ne modifie aucun fichier : famille `verifier_`, lecture seule.

Usage : python verifier_controles.py [--pages ui/pages] [--page gallery]
SORTIE EN ASCII PUR (console cp1252 de l'agent des bancs).
"""

import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# Balises qui sont des controles SANS qu'on ait rien a ajouter : elles
# recoivent le focus, repondent a Entree (et Espace pour button), et sont
# annoncees pour ce qu'elles sont.
BALISES_NATIVES = ('button', 'input', 'select', 'textarea', 'summary')
# `a` n'est un controle que s'il porte un `href` : sans lui, il sort de
# l'ordre de tabulation aussi surement qu'un `span`.
BALISE_LIEN = 'a'

# Ce qui rend un element non natif operable A LA MAIN. Les trois sont
# necessaires : `tabindex` pour l'atteindre, `role` pour l'annoncer, un
# gestionnaire clavier pour l'actionner. Deux sur trois laisse un controle
# qu'on atteint sans pouvoir s'en servir, ou qu'on actionne sans savoir ce
# que c'est.
MARQUES = ('tabindex', 'role', 'clavier')


# Ce qui peut PRECEDER un `/` qui ouvre une expression reguliere. Apres un
# identifiant, un nombre, `)` ou `]`, le meme caractere est une division.
# C'est la seule facon de lever l'ambiguite sans analyser la grammaire.
_AVANT_REGEX = re.compile(r'(?:[(,=:\[!&|?{};+\-*%~^<>]|\b(?:return|typeof|'
                          r'instanceof|in|of|new|delete|void|case|do|else|'
                          r'yield|await)\b)\s*$')


def _segments(js):
    """[(genre, debut, fin)] -- 'code', 'chaine', 'commentaire', 'regex'.

    UN seul scanner pour les deux lectures qui suivent, parce que les deux
    se trompaient au meme endroit. QUATRIEME rouge que l'instrument s'est
    donne, et le plus instructif : le docstring nommait deja les litteraux
    d'expression reguliere comme un angle mort THEORIQUE. Il est reel.
    `subjects` ecrit `esc(s).replace(/[&<>"]/g, ...)` en tete de script : le
    guillemet DANS la regex ouvrait une fausse chaine, et tout le reste du
    fichier basculait -- le bouton `<button class="btn anim">`, cent lignes
    plus bas, cessait d'exister pour l'instrument, qui rendait « la balise
    ne s'en deduit pas » au lieu de « c'est un bouton, donc c'est vert ».

    Un angle mort NOMME reste un angle mort : le nommer dit ou l'on ne voit
    pas, il ne fait pas voir. Celui-la mordait, il est ferme.
    """
    out = []
    i, n, debut_code = 0, len(js), 0
    while i < n:
        c = js[i]
        if c in '\'"`':
            j = i + 1
            while j < n:
                if js[j] == '\\':
                    j += 2
                    continue
                if js[j] == c:
                    break
                j += 1
            j = min(j + 1, n)
            out.append(('code', debut_code, i))
            out.append(('chaine', i, j))
            i = debut_code = j
            continue
        if c == '/' and i + 1 < n and js[i + 1] == '/':
            j = js.find('\n', i)
            j = n if j < 0 else j
            out.append(('code', debut_code, i))
            out.append(('commentaire', i, j))
            i = debut_code = j
            continue
        if c == '/' and i + 1 < n and js[i + 1] == '*':
            j = js.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(('code', debut_code, i))
            out.append(('commentaire', i, j))
            i = debut_code = j
            continue
        if c == '/' and _AVANT_REGEX.search(js[max(0, i - 24):i]):
            j, classe = i + 1, False
            while j < n and js[j] != '\n':
                if js[j] == '\\':
                    j += 2
                    continue
                if js[j] == '[':
                    classe = True
                elif js[j] == ']':
                    classe = False
                elif js[j] == '/' and not classe:
                    break
                j += 1
            if j < n and js[j] == '/':          # litteral bien ferme
                out.append(('code', debut_code, i))
                out.append(('regex', i, j + 1))
                i = debut_code = j + 1
                continue
        i += 1
    out.append(('code', debut_code, n))
    return [x for x in out if x[1] < x[2]]


def _blanchir(js, garder):
    """Rend le JS ou tout ce qui n'est pas `garder` devient de l'espace.

    Les positions sont conservees : un point dans le resultat se traduit en
    numero de ligne du FICHIER, pas d'un extrait.
    """
    out = ['\n' if ch == '\n' else ' ' for ch in js]
    for genre, a, b in _segments(js):
        if genre in garder:
            for k in range(a, b):
                out[k] = js[k]
    return ''.join(out)


def sans_commentaires_js(js):
    """Le JS sans ses commentaires, positions conservees.

    Un commentaire est de la PROSE, quel que soit le langage : ce projet
    l'a appris quatre fois le meme jour (25/08). Une phrase d'explication
    contenant `onclick` ferait compter un grief qui n'existe pas.
    """
    return _blanchir(js, ('code', 'chaine', 'regex'))


def chaines_seules(js):
    """Le JS ou seules les CHAINES restent.

    Deuxieme rouge que l'instrument s'est donne : en cherchant `<tag ...
    onclick=` dans le JS entier, le `<` d'une comparaison ouvrait une fausse
    balise. `(f.sim!=null?f.sim:1)<t;` puis, quatre-vingts lignes plus bas,
    un `onclick=` -- et l'instrument accusait une balise `<t>` qui n'existe
    pas. Il criait sur de l'arithmetique, et une alarme qu'on apprend a
    ignorer ne protege plus rien.

    Le HTML assemble en JS reste lu : il vit dans les chaines, et c'est
    exactement ce qui reste ici.
    """
    return _blanchir(js, ('chaine',))


def sans_commentaires_html(html):
    """Meme raison, meme methode : les positions sont conservees."""
    def blanc(m):
        return ''.join(ch if ch == '\n' else ' ' for ch in m.group(0))
    return re.sub(r'<!--.*?-->', blanc, html, flags=re.S)


_STYLE = re.compile(r'(<style\b[^>]*>)(.*?)(</style\s*>)', re.S | re.I)


def sans_le_css(html):
    """Le document avec le CONTENU des blocs <style> blanchi.

    Un commentaire est de la PROSE, quel que soit le langage -- et une
    feuille de style ne porte pas de balise. Trouve le 26/08, sur un rouge
    provoque : un commentaire CSS qui EXPLIQUE la conversion
    (<< les chips sont des <span onclick> convertis en <button> >>) etait lu
    comme un grief de niveau A. Aucune des onze pages n'en portait un avec
    `onclick=` -- mais `gallery` en portait un avec `<button>` et `<span>`,
    a une virgule pres du cas qui mord. Nommer l'angle mort ne l'aurait pas
    ferme."""
    def blanc(m):
        milieu = ''.join(c if c == '\n' else ' ' for c in m.group(2))
        return m.group(1) + milieu + m.group(3)
    return _STYLE.sub(blanc, html)


def decouper(html):
    """Rend (html_hors_script, js_avec_positions).

    Les deux gardent la longueur du document : une position dans l'un ou
    l'autre se traduit en numero de ligne du FICHIER, pas d'un extrait.
    """
    hors = list(html)
    js = [' ' if ch != '\n' else '\n' for ch in html]
    for m in re.finditer(r'<script\b[^>]*>(.*?)</script\s*>', html, re.S | re.I):
        a, b = m.start(1), m.end(1)
        for k in range(a, b):
            js[k] = html[k]
            if html[k] != '\n':
                hors[k] = ' '
    return ''.join(hors), ''.join(js)


def ligne_de(texte, pos):
    return texte.count('\n', 0, pos) + 1


# --------------------------------------------------------------------------
# Ce que le document DECLARE : les balises et leurs identifiants
# --------------------------------------------------------------------------

_BALISE_ID = re.compile(r'<([A-Za-z][\w-]*)\b([^<>]*)', re.S)


def table_des_ids(*sources):
    """{id -> (balise, attributs)} lu dans le HTML ET dans les chaines JS.

    Le HTML assemble en JS n'est pas moins du HTML : `container.querySelector
    ('#rm')` vise un bouton qui n'existe que dans une chaine. Ne lire que le
    HTML statique rendrait NON DECIDABLE la moitie des cibles reelles -- et
    un non-decidable pese autant qu'un grief.
    """
    out = {}
    for src in sources:
        for m in _BALISE_ID.finditer(src):
            attrs = m.group(2)
            t = re.search(r'\bid\s*=\s*["\']([\w-]+)["\']', attrs)
            if t and t.group(1) not in out:
                out[t.group(1)] = (m.group(1).lower(), attrs)
    return out


def table_des_classes(*sources):
    """{classe -> [(balise, attributs)]} -- pour les selecteurs de classe.

    Un nom de classe est un JETON ENTIER, pas un morceau de mot : `.n` ne
    doit pas se reconnaitre dans `class="nommer"`. Le projet a paye cette
    lecon trois fois le 25/08 (`toastP`, `vues`, `--f-donnees`).
    """
    out = {}
    for src in sources:
        for m in _BALISE_ID.finditer(src):
            attrs = m.group(2)
            t = re.search(r'\bclass\s*=\s*["\']([^"\']*)["\']', attrs)
            if not t:
                continue
            for cl in t.group(1).split():
                out.setdefault(cl, []).append((m.group(1).lower(), attrs))
    return out


def marques_de(attrs):
    """Ce qu'un element ECRIT porte pour etre operable a la main."""
    q = set()
    if re.search(r'\btabindex\s*=', attrs, re.I):
        q.add('tabindex')
    if re.search(r'\brole\s*=', attrs, re.I):
        q.add('role')
    if re.search(r'\bon(keydown|keypress|keyup)\s*=', attrs, re.I):
        q.add('clavier')
    return q


def natif(balise, attrs=''):
    """La balise suffit-elle, sans rien ajouter ?"""
    if balise in BALISES_NATIVES:
        return True
    if balise == BALISE_LIEN:
        return bool(re.search(r'\bhref\s*=', attrs, re.I))
    return False


# --------------------------------------------------------------------------
# Source 1 et 2 : l'attribut `onclick=` ecrit dans du HTML
# --------------------------------------------------------------------------

_HTML_CLIC = re.compile(
    r'<([A-Za-z][\w-]*)\b((?:[^<>"\']|"[^"]*"|\'[^\']*\')*?)\bon(?:click|mousedown)\s*=',
    re.S)


def clics_ecrits(source):
    """[(pos, balise, attrs)] pour chaque `<tag ... onclick=>` de la source."""
    return [(m.start(), m.group(1).lower(), m.group(2))
            for m in _HTML_CLIC.finditer(source)]


# --------------------------------------------------------------------------
# Source 3 : le gestionnaire pose en JS
# --------------------------------------------------------------------------

_POSE = re.compile(r'\.\s*onclick\s*=|\.\s*addEventListener\s*\(\s*[\'"]click[\'"]')
_CREE = re.compile(
    r'([A-Za-z_$][\w$]*)\s*=\s*document\s*\.\s*createElement\s*\(\s*[\'"]([\w-]+)[\'"]')
_TOUS = re.compile(
    r'([A-Za-z_$][\w$]*)\s*=\s*[^;=]*?querySelectorAll\s*\(\s*[\'"]([^\'"]+)[\'"]')
# Le motif le plus courant du projet -- 119 fois sur les onze pages : on
# range l'element dans une variable, puis on lui pose le gestionnaire plus
# bas. Sans cette table, `btnIA.addEventListener('click', ...)` tombait dans
# les NON DECIDABLES : le premier rouge que l'instrument s'est donne a
# lui-meme, et il aurait fausse le compte de toutes les pages.
# Cinquieme rouge : `querySelectorAll('.chip').forEach(function(c){ c.onclick
# = ... })`. Le parametre du rappel EST l'element, et `subjects` -- la page
# qui fait CORRECTEMENT ses chips en `<button>` -- passait ainsi pour non
# decidable. Un instrument qui ne sait pas reconnaitre le bon eleve ne peut
# pas montrer la divergence : c'etait tout l'objet de la mesure.
_PARAM = re.compile(
    r'querySelectorAll\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\s*\.\s*forEach'
    r'\s*\(\s*function\s*\(\s*([A-Za-z_$][\w$]*)')
_ALIAS = re.compile(
    r'([A-Za-z_$][\w$]*)\s*=\s*((?:document\s*\.\s*getElementById|'
    r'[\w$.]*?querySelector)\s*\(\s*[\'"][^\'"]+[\'"]\s*\))')

_FIN_EXPR = set(' \t\n\r')
_OUVRE = {')': '(', ']': '[', '}': '{'}


def expression_avant(js, pos):
    """L'expression dont on prend `.onclick`, lue a REBOURS depuis le point.

    Un scan arriere qui equilibre parentheses et crochets : il rend
    `document.getElementById('lb-del')` entier, la ou une regex avant le
    point rendrait `)` ou le dernier identifiant.
    """
    i = pos - 1
    pile = []
    fin = pos
    while i >= 0:
        c = js[i]
        if pile:
            if c in _OUVRE:
                pile.append(_OUVRE[c])
            elif c in '([{':
                if pile and pile[-1] == c:
                    pile.pop()
            elif c in '\'"':
                j = i - 1
                while j >= 0 and not (js[j] == c and js[j - 1] != '\\'):
                    j -= 1
                i = j
            i -= 1
            continue
        if c in _FIN_EXPR:
            if fin == i + 1:
                fin = i
                i -= 1
                continue
            break
        if c in _OUVRE:
            pile.append(_OUVRE[c])
            i -= 1
            continue
        if c.isalnum() or c in '_$.':
            i -= 1
            continue
        break
    return js[i + 1:fin].strip()


def derniere_avant(table, nom, pos):
    """La fabrication de `nom` la plus proche AVANT `pos`, s'il y en a une."""
    cands = [p for p in table.get(nom, []) if p[0] < pos]
    return cands[-1] if cands else None


def marques_js(js, nom):
    """Ce qu'on a ajoute A LA MAIN sur cette variable, ou que ce soit."""
    q = set()
    n = re.escape(nom)
    if re.search(n + r'\s*\.\s*(tabIndex|setAttribute\s*\(\s*[\'"]tabindex)', js):
        q.add('tabindex')
    if re.search(n + r'\s*\.\s*(role\s*=|setAttribute\s*\(\s*[\'"]role)', js):
        q.add('role')
    if re.search(n + r'\s*\.\s*(onkey(down|press|up)\s*=|addEventListener'
                 r'\s*\(\s*[\'"]key)', js):
        q.add('clavier')
    return q


def delegue(js, pos):
    """Le gestionnaire lit-il `ev.target` ? Alors le cliquable est ailleurs.

    Ni vert ni rouge : l'instrument NOMME et laisse l'oeil trancher. Compter
    vert une delegation serait un feu vert vole ; la compter rouge ferait
    crier l'instrument sur le motif le plus courant d'une liste longue.
    """
    corps = js[pos:pos + 400]
    return bool(re.search(r'\b(ev|e|event)\s*\.\s*target\b', corps))


# --------------------------------------------------------------------------
# Ce qui ne se DECIDE pas se DECLARE -- dans la source, avec sa raison
# --------------------------------------------------------------------------

# Un clic peut doubler une action DEJA offerte par un vrai controle : les
# bandes laterales d'une visionneuse a cote de ses boutons Precedent et
# Suivant, une croix de fermeture a cote de la touche Echap. L'element reste
# un `<div>`, mais plus aucune fonctionnalite n'est perdue au clavier -- et
# WCAG 2.1.1 porte sur la FONCTIONNALITE, pas sur l'element.
#
# Cette exception ne peut pas se calculer : elle demande de savoir qu'un
# AUTRE chemin existe. Elle se DECLARE donc dans la source, a cote du code
# qu'elle exempte, avec une raison obligatoire -- jamais en dur dans
# l'instrument, sinon il devient aveugle au cas suivant sans qu'on le sache.
# C'est la regle que `verifier_contraste` s'est donnee le 25/08, appliquee
# ici au meme probleme.
#
# Elle ne vaut que pour le PROCHAIN gestionnaire de clic, et le rapport les
# COMPTE toutes : une exception qui prolifere doit se voir.
# Deux formes, et une seule porte : `redondant` dit qu'un autre chemin fait
# deja la meme chose au clavier ; `natif` affirme, preuve a l'appui dans la
# raison, que la cible EST un controle que l'instrument ne sait pas remonter
# (une fonction d'aide qui recoit l'identifiant en parametre, par exemple).
# La seconde est la plus dangereuse : elle contredit l'instrument au lieu de
# le completer. Elle est donc COMPTEE a part et lisible dans le rapport --
# c'est ce qui la distingue d'un silence.
_DECLARE = re.compile(
    r'(?:/\*|//|<!--)\s*controle\s*:\s*(redondant|natif)\s*(?:--)?\s*'
    r'(.*?)(?:\*/|-->|\n)', re.S)


def declarations(source):
    """[(fin, raison)] -- lues dans le source BRUT, commentaires compris.

    Elles vivent dans des commentaires : les lire APRES les avoir retires
    reviendrait a ne jamais les lire. C'est l'exception a << retirer les
    commentaires avant de lire >>, et elle est volontaire.
    """
    out = []
    for m in _DECLARE.finditer(source):
        raison = ' '.join(m.group(2).split()).strip(' -')
        if raison:
            out.append((m.end(), m.group(1), raison))
    return out


# --------------------------------------------------------------------------
# Analyse d'une page
# --------------------------------------------------------------------------

_ID_PAR = re.compile(r'^document\s*\.\s*getElementById\s*\(\s*[\'"]([\w-]+)[\'"]\s*\)$')
_SEL_PAR = re.compile(r'querySelector\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)$')
_SIMPLE = re.compile(r'^[A-Za-z_$][\w$]*$')
_INDEX = re.compile(r'^([A-Za-z_$][\w$]*)\s*\[')


def _par_selecteur(sel, ids, classes=None):
    """Un selecteur CSS rend-il une balise connue ?"""
    sel = sel.strip()
    # `.actes .btn` : c'est le DERNIER segment qui decrit l'element vise ;
    # ce qui precede dit seulement ou il vit. Ne pas le savoir faisait
    # tomber `tranche` en non decidable sur trois boutons.
    if ' ' in sel or '>' in sel:
        sel = re.split(r'[\s>]+', sel)[-1].strip() or sel
    if sel.startswith('#'):
        e = ids.get(sel[1:])
        return e if e else (None, "id '%s' introuvable dans le document" % sel[1:])
    # `button.btn--principal` ECRIT sa balise : la lire est gratuit, et
    # l'ignorer faisait tomber en non decidable une cible qui se nomme.
    m = re.match(r'^([A-Za-z][\w-]*)(?:[.#\[:]|$)', sel)
    if m:
        return (m.group(1).lower(), '')
    # `.nommer` ne dit pas sa balise -- mais le document, lui, la dit, si
    # une seule balise porte cette classe. Deux balises differentes : on ne
    # tranche pas, on le DIT.
    m = re.match(r'^\.([\w-]+)$', sel)
    if m and classes:
        vues = classes.get(m.group(1))
        if vues and len(set(b for b, _a in vues)) == 1:
            return vues[0]
        if vues:
            return (None, "classe '%s' portee par %d balises differentes"
                    % (m.group(1), len(set(b for b, _a in vues))))
    return (None, "selecteur '%s' : la balise ne s'en deduit pas" % sel)


def resoudre_cible(expr, pos, js, ids, crees, tous, alias,
                   classes=None, vus=None):
    """Rend (balise, attrs, variable, raison) -- balise None = non decidable."""
    if expr in ('document', 'window', 'self', 'document.body'):
        return (None, '', None, '@global')
    if _SIMPLE.match(expr):
        c = derniere_avant(crees, expr, pos)
        if c:
            return (c[1], '', expr, '')
        e = ids.get(expr)
        if e:
            return (e[0], e[1], expr, '')
        t = derniere_avant(tous, expr, pos)
        if t:
            r = _par_selecteur(t[1], ids, classes)
            return (r[0], r[1], expr, '') if r[0] else (None, '', expr, r[1])
        al = derniere_avant(alias, expr, pos)
        if al:
            vus = vus or set()
            if expr in vus:                       # variable qui se pointe
                return (None, '', expr, "'%s' : alias circulaire" % expr)
            vus.add(expr)
            b, at, _v, ra = resoudre_cible(al[1], pos, js, ids, crees,
                                           tous, alias, classes, vus)
            return (b, at, expr, ra)              # la VARIABLE reste la cible
        return (None, '', expr,
                "'%s' : aucun createElement, id ni alias de ce nom avant ce"
                " point" % expr)
    m = _ID_PAR.match(expr)
    if m:
        e = ids.get(m.group(1))
        if e:
            return (e[0], e[1], None, '')
        return (None, '', None,
                "id '%s' introuvable dans le document" % m.group(1))
    m = _SEL_PAR.search(expr)
    if m:
        r = _par_selecteur(m.group(1), ids, classes)
        return (r[0], r[1], None, '') if r[0] else (None, '', None, r[1])
    m = _INDEX.match(expr)
    if m:
        base = m.group(1)
        t = derniere_avant(tous, base, pos)
        if t:
            r = _par_selecteur(t[1], ids, classes)
            return (r[0], r[1], None, '') if r[0] else (None, '', None, r[1])
        c = derniere_avant(crees, base, pos)
        if c:
            return (c[1], '', None, '')
        return (None, '', None, "'%s' : collection d'origine inconnue" % expr)
    return (None, '', None, "expression non remontee : '%s'" % expr)


def analyser(nom, brut):
    """Rend {page, natifs, bricoles, griefs, oeil, indecidables, liens, ...}."""
    html = sans_le_css(sans_commentaires_html(brut))
    hors, brut_js = decouper(html)
    js = sans_commentaires_js(brut_js)
    chaines = chaines_seules(js)
    ids = table_des_ids(hors, chaines)
    classes = table_des_classes(hors, chaines)
    crees, tous, alias = {}, {}, {}
    for m in _CREE.finditer(js):
        crees.setdefault(m.group(1), []).append((m.start(), m.group(2).lower()))
    for m in _TOUS.finditer(js):
        tous.setdefault(m.group(1), []).append((m.start(), m.group(2)))
    for m in _PARAM.finditer(js):
        tous.setdefault(m.group(2), []).append((m.start(), m.group(1)))
    for m in _ALIAS.finditer(js):
        alias.setdefault(m.group(1), []).append((m.start(), m.group(2)))

    r = {'page': nom, 'natifs': 0, 'bricoles': [], 'griefs': [], 'oeil': [],
         'indecidables': [], 'liens': [], 'declares': [], 'poses': 0}

    # Toutes les cibles d'abord, DANS L'ORDRE DU DOCUMENT : une declaration
    # couvre le prochain gestionnaire, et « prochain » n'a de sens qu'ici.
    cibles = []
    for pos, balise, attrs in clics_ecrits(hors):
        cibles.append({'pos': pos, 'balise': balise, 'attrs': attrs,
                       'var': None, 'origine': 'attribut HTML', 'note': ''})
    for pos, balise, attrs in clics_ecrits(chaines):
        cibles.append({'pos': pos, 'balise': balise, 'attrs': attrs,
                       'var': None, 'note': '',
                       'origine': 'attribut dans une chaine JS'})
    for m in _POSE.finditer(js):
        pos = m.start()
        expr = expression_avant(js, pos)
        balise, attrs, var, raison = resoudre_cible(
            expr, pos, js, ids, crees, tous, alias, classes)
        if raison == '@global':
            r['poses'] += 1                     # compte, mais rien a juger
            continue
        cibles.append({'pos': pos, 'balise': balise, 'attrs': attrs,
                       'var': var, 'origine': 'JS', 'raison': raison,
                       'note': 'delegation' if delegue(js, m.end()) else ''})
    cibles.sort(key=lambda c: c['pos'])
    r['poses'] += len(cibles)

    for fin, genre, raison in declarations(brut):
        for c in cibles:
            if c['pos'] >= fin and 'declare' not in c:
                c['declare'] = (genre, raison)
                break

    for c in cibles:
        pos, balise, attrs = c['pos'], c['balise'], c['attrs']
        lg = ligne_de(html, pos)
        # L'ordre compte : un controle deja NATIF est vert par lui-meme, et
        # une declaration posee dessus ne doit pas le faire compter comme une
        # exception -- sinon les exceptions gonflent sans qu'aucune ne serve.
        if balise is not None and natif(balise, attrs):
            if balise == BALISE_LIEN and re.search(r'href\s*=\s*["\']#', attrs):
                r['liens'].append((lg, balise, c['origine']))
            r['natifs'] += 1
            continue
        if 'declare' in c:
            # Declaree dans la source, avec sa raison. Vaut pour tout element
            # non natif -- lien sans href et cible non remontee compris : une
            # exception avec une porte derobee serait une seconde regle non
            # ecrite.
            genre, raison = c['declare']
            r['declares'].append((lg, balise or '?', c['origine'], genre, raison))
            continue
        if balise is None:
            r['indecidables'].append((lg, c.get('raison', 'cible inconnue')))
            continue
        if balise == BALISE_LIEN:
            # Troisieme rouge : `var a = createElement('a'); a.href = ...`
            # pose le href en JS, la ou `natif()` ne lit que les attributs
            # ECRITS. L'instrument declarait hors tabulation un lien qui y
            # est. Ce qu'une balise PORTE ne se lit pas qu'au meme endroit.
            if c['var'] and re.search(re.escape(c['var']) + r'\s*\.\s*(href\s*=|'
                                      r'setAttribute\s*\(\s*[\'"]href)', js):
                r['natifs'] += 1
                continue
            r['griefs'].append((lg, balise, c['origine'],
                                'lien sans href : hors tabulation', c['note']))
            continue
        q = marques_de(attrs) | (marques_js(js, c['var']) if c['var'] else set())
        manque = [x for x in MARQUES if x not in q]
        if not manque:
            r['bricoles'].append((lg, balise, c['origine']))
        elif c['note'] == 'delegation':
            r['oeil'].append((lg, balise, c['origine'], 'delegue a ev.target',
                              ', '.join(manque)))
        else:
            r['griefs'].append((lg, balise, c['origine'],
                                'manque : ' + ', '.join(manque), c['note']))
    return r


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------

def rapport(resultats, ecrire=print):
    """Rend le nombre de choses A TRAITER : griefs + a l'oeil + non decidables.

    Les trois sont dites SEPAREMENT parce qu'elles ne se corrigent pas
    pareil -- mais aucune ne se tait. Un instrument qui rendrait 0 en ayant
    laisse des cibles non remontees donnerait la permission d'aller vite la
    ou il faut aller lentement.
    """
    if not resultats:
        ecrire("aucune page lue -- rien n'a pu etre verifie, et ce n'est pas")
        ecrire("un feu vert.")
        return -1
    tot_g = tot_o = tot_i = tot_n = tot_b = tot_p = tot_d = 0
    ecrire("# verifier_controles -- WCAG 2.1.1 (niveau A) : ce qui se clique")
    ecrire("#   doit recevoir le focus, repondre au clavier, et s'annoncer.")
    ecrire("")
    ecrire("%-10s %6s %7s %8s %8s %7s %6s %6s"
           % ('page', 'poses', 'natifs', 'bricoles', 'declares', 'GRIEFS',
              'oeil', 'inconnu'))
    ecrire("-" * 70)
    for r in resultats:
        ecrire("%-10s %6d %7d %8d %8d %7d %6d %6d"
               % (r['page'], r['poses'], r['natifs'], len(r['bricoles']),
                  len(r['declares']), len(r['griefs']), len(r['oeil']),
                  len(r['indecidables'])))
        tot_p += r['poses']; tot_n += r['natifs']; tot_b += len(r['bricoles'])
        tot_g += len(r['griefs']); tot_o += len(r['oeil'])
        tot_i += len(r['indecidables']); tot_d += len(r['declares'])
    ecrire("-" * 70)
    ecrire("%-10s %6d %7d %8d %8d %7d %6d %6d"
           % ('TOTAL', tot_p, tot_n, tot_b, tot_d, tot_g, tot_o, tot_i))
    ecrire("")
    for r in resultats:
        if not r['griefs']:
            continue
        ecrire("GRIEFS -- %s (%d)" % (r['page'], len(r['griefs'])))
        for lg, balise, origine, quoi, note in r['griefs']:
            sup = "  [%s]" % note if note else ""
            ecrire("  l.%-5d <%s> %-24s %s%s" % (lg, balise, origine, quoi, sup))
        ecrire("")
    for r in resultats:
        if not r['oeil']:
            continue
        ecrire("A L'OEIL -- %s (%d) : le gestionnaire lit ev.target, donc le"
               % (r['page'], len(r['oeil'])))
        ecrire("  cliquable REEL est peut-etre ailleurs. Ni vert ni rouge :")
        ecrire("  aucune lecture statique ne tranche.")
        for lg, balise, origine, quoi, manque in r['oeil']:
            ecrire("  l.%-5d <%s> %s ; manque : %s" % (lg, balise, quoi, manque))
        ecrire("")
    for r in resultats:
        if not r['indecidables']:
            continue
        ecrire("NON DECIDABLES -- %s (%d) -- comptes, pas tus :"
               % (r['page'], len(r['indecidables'])))
        for lg, raison in r['indecidables']:
            ecrire("  l.%-5d %s" % (lg, raison))
        ecrire("")
    dec = [(r['page'], x) for r in resultats for x in r['declares']]
    if dec:
        ecrire("DECLARES DANS LA SOURCE (%d) -- REDONDANT : un autre chemin"
               % len(dec))
        ecrire("  fait deja la meme chose au clavier ; NATIF : la cible EST un")
        ecrire("  controle que l'instrument ne sait pas remonter.")
        ecrire("  La raison est ECRITE a cote du code : elle se relit et se")
        ecrire("  conteste -- et leur nombre se surveille : une exception qui")
        ecrire("  prolifere n'en est plus une.")
        for page, (lg, balise, origine, genre, raison) in dec:
            if len(raison) > 54:
                raison = raison[:54] + " [... suite dans la page]"
            ecrire("  %-8s l.%-5d %-9s <%s> %s"
                   % (page, lg, genre.upper(), balise, raison))
        ecrire("")
    liens = [(r['page'], x) for r in resultats for x in r['liens']]
    if liens:
        ecrire("SEMANTIQUE, PAS NIVEAU A (%d) : <a href=\"#\"> qui AGIT au lieu"
               % len(liens))
        ecrire("  de naviguer. Operable au clavier, donc pas un grief ; mais un")
        ecrire("  lecteur d'ecran l'annonce comme un lien.")
        for page, (lg, balise, origine) in liens:
            ecrire("  %-10s l.%-5d <%s> %s" % (page, lg, balise, origine))
        ecrire("")
    ecrire("PORTEE : les %d page(s) LUES dans ui/pages, telles qu'ecrites."
           % len(resultats))
    ecrire("Ni ce que le serveur injecte, ni ce que le navigateur calcule. Un")
    ecrire("gestionnaire pose par delegation sur un ancetre n'est pas remonte")
    ecrire("a son cliquable. Les litteraux d'expression reguliere JS, eux,")
    ecrire("sont distingues d'une division depuis le 26/08.")
    ecrire("")
    a_traiter = tot_g + tot_o + tot_i
    if not a_traiter:
        ecrire("VERDICT : les %d gestionnaires de clic des %d pages lues sont"
               % (tot_p, len(resultats)))
        ecrire("poses sur des controles -- %d natifs, %d rendus operables a la"
               % (tot_n, tot_b))
        ecrire("main, %d declares redondants, aucun non remonte." % tot_d)
    else:
        ecrire("VERDICT : %d grief(s) de niveau A, %d cas a l'oeil, %d cible(s)"
               % (tot_g, tot_o, tot_i))
        ecrire("non remontee(s) -- sur %d gestionnaires et %d pages lues."
               % (tot_p, len(resultats)))
        ecrire("Un <span onclick> ne recoit jamais le focus, ne repond ni a")
        ecrire("Entree ni a Espace, et n'est annonce comme rien.")
    return a_traiter


def pages(dossier, filtre=''):
    d = Path(dossier)
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob('*.html')):
        if filtre and filtre not in f.stem:
            continue
        out.append((f.stem, f.read_text(encoding='utf-8')))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--pages', default=str(RACINE / 'ui' / 'pages'))
    p.add_argument('--page', default='', help='ne juger que celle-la')
    a = p.parse_args(argv)
    lues = pages(a.pages, a.page)
    if not lues:
        print("aucune page dans %s -- rien n'a pu etre verifie, et ce n'est"
              " pas un feu vert." % a.pages)
        return 2
    n = rapport([analyser(nom, html) for nom, html in lues])
    return 1 if n else 0


if __name__ == '__main__':
    sys.exit(main())
