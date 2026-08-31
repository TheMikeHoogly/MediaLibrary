#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verifier_raccourcis -- le pense-bete `?` dit-il la VERITE ?

Point 6 du plancher d'accessibilite : « documente les raccourcis dans
l'interface elle-meme ». Le panneau `?` est pose (30/08) et il lit
`docs/RACCOURCIS.md`. Restait l'INSTRUMENT : sans lui, une touche ajoutee
dans une page ne serait documentee nulle part, et une touche retiree
laisserait la doc promettre un geste qui ne repond plus. Une doc ecrite a la
main derive le jour meme ou personne ne la relit.

Il RELEVE dans `ui/pages/*.html` et `ui/global.js` ce que le code ecoute
vraiment, il LIT ce que le releve promet, et il rend DEUX chiffres qui ne
disent pas la meme chose :

  - les touches ECOUTEES et non documentees  -- le vrai grief : un raccourci
    qu'on ne peut pas connaitre est un raccourci qui n'existe pas ;
  - les touches DOCUMENTEES et plus ecoutees -- la doc qui ment, plus grave
    encore : elle promet un geste qui ne repond pas.

PORTEE, et elle compte : cet instrument lit le TEXTE des pages. Il voit
`e.key === '...'`, la plage `/^[a-z]$/` et l'indexation d'une constante de
lettres. Il ne voit ni `keyCode`, ni un ecouteur assemble a l'execution, ni
ce que `server.py` injecte. Zero grief ne veut donc pas dire zero raccourci
inconnu -- ca veut dire que rien de ce QU'IL SAIT LIRE ne manque.

Lecture seule. Usage :
    verifier_raccourcis.py [--pages ui/pages] [--doc docs/RACCOURCIS.md] [--page gallery]
"""
import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent

# Le vocabulaire CANONIQUE : le code parle « Escape », la doc ecrit
# « Echap ». Sans table, les deux ne se rencontrent jamais. Les fleches
# deviennent des mots : la console de l'agent est en cp1252, une fleche s y
# imprime en point d interrogation et le rapport devient illisible.
CANON = {
    ' ': 'Espace', 'Enter': 'Entree', 'Escape': 'Echap', 'Delete': 'Suppr',
    'ArrowLeft': 'Gauche', 'ArrowRight': 'Droite', 'Tab': 'Tab',
    'Espace': 'Espace', 'Entrée': 'Entree', 'Échap': 'Echap',
    'Echap': 'Echap', 'Suppr': 'Suppr', '←': 'Gauche', '→': 'Droite',
    'lettre': 'lettre',
}
# Une plage de lettres (a-z dans le code, « A-Z » dans la doc) est UNE entree
# du vocabulaire : la documenter touche par touche serait illisible.
PLAGE_LETTRE = 'lettre'


def canon(t):
    """La forme canonique d'une touche, cote code comme cote doc.

    L'espace se traite AVANT tout nettoyage : `t.strip()` le reduit a la
    chaine vide, et la touche la plus utilisee du projet (« Espace », qui
    juge une carte) disparaissait du releve en silence. Trouve au premier
    lancement de cet instrument -- un instrument aveugle a une touche rend
    un vert qui ne vaut rien."""
    if t == ' ':
        return 'Espace'
    t = (t or '').strip()
    if not t:
        return ''
    if t in CANON:
        return CANON[t]
    if len(t) == 1:
        return t.upper()
    return t


# ── ce que le CODE ecoute ────────────────────────────────────────────────────

RE_EGAL = re.compile(r"""\.key\s*===\s*(['"])(.*?)\1""")
RE_DIFF = re.compile(r"""\.key\s*!==\s*(['"])(.*?)\1""")
RE_PLAGE = re.compile(r"/\^\[a-zA-Z\]\$/\s*\.test\s*\(\s*\w+\.key\s*\)")
RE_CONST_LETTRES = re.compile(r"""(\w+)\s*=\s*(['"])([A-Z]{2,})\2""")
RE_INDEXOF_KEY = re.compile(r"""(\w+)\.indexOf\(\s*\(?\s*\w+\.key""")


def touches_ecoutees(src):
    """L'ensemble canonique des touches qu'une source ECOUTE vraiment.

    `!==` compte autant que `===` : `if (ev.key !== '/') return;` est la
    forme la plus courante d'un raccourci a UNE touche (la brique commune
    l'emploie pour `/` et `?`). L'ignorer aurait rendu l'instrument aveugle
    a la seule famille de raccourcis presente sur TOUTES les pages."""
    out = set()
    for rx in (RE_EGAL, RE_DIFF):
        for _, t in rx.findall(src):
            c = canon(t)
            if c:
                out.add(c)
    if RE_PLAGE.search(src):
        out.add(PLAGE_LETTRE)
    # `LETTRES.indexOf(e.key.toUpperCase())` : la constante EST la liste des
    # touches. On ne la devine pas, on la lit.
    consts = {n: v for n, _, v in RE_CONST_LETTRES.findall(src)}
    for nom in RE_INDEXOF_KEY.findall(src):
        for lettre in consts.get(nom, ''):
            out.add(canon(lettre))
    return out


# ── ce que la DOC promet ─────────────────────────────────────────────────────

RE_LIGNE_TABLE = re.compile(r'^\|(.+?)\|', re.M)
RE_BACKTICK = re.compile(r'`([^`]+)`')
MARQUEUR_FIN = '<!-- panneau: fin -->'


def touches_documentees(md):
    """Les touches citees dans la PREMIERE colonne des tableaux du releve --
    jusqu'au marqueur de fin, exactement ce que le panneau `?` montre. Une
    touche citee dans une phrase ou dans la colonne « Effet » ne compte pas :
    elle n'est pas presentee comme un raccourci."""
    fin = md.find(MARQUEUR_FIN)
    if fin >= 0:
        md = md[:fin]
    out = set()
    for cellule in RE_LIGNE_TABLE.findall(md):
        if set(cellule.strip()) <= set('-: '):
            continue                       # ligne de separation d'un tableau
        for t in RE_BACKTICK.findall(cellule):
            t = t.strip()
            if t.lower().startswith('a') and '–' in t:
                out.add(PLAGE_LETTRE if t.upper().endswith('Z') else canon(t))
                continue
            c = canon(t)
            if c:
                out.add(c)
    return out


# Au-dela de cette etendue, une plage de lettres n'est plus une liste de
# raccourcis : c'est « n'importe quelle lettre ». `A`-`H` (/residu) se
# developpe en huit touches reelles ; `A`-`Z` (/sujets) est la PLAGE, et la
# developper fabriquait seize faux griefs -- I, J, K... « promises et plus
# ecoutees ». Vu au premier lancement.
PLAGE_MAX = 12


def lettres_de_plage(md):
    """Les plages « `A`-`H` » du releve, developpees ; une plage large rend
    la marque `lettre`. Sinon `A` et `H` passeraient pour deux raccourcis
    isoles et les six du milieu pour des touches non documentees."""
    out = set()
    for m in re.finditer(r'`([A-Z])`\s*[–-]\s*`([A-Z])`', md):
        a, b = m.group(1), m.group(2)
        if a >= b:
            continue
        if ord(b) - ord(a) + 1 > PLAGE_MAX:
            out.add(PLAGE_LETTRE)
        else:
            out |= {chr(c) for c in range(ord(a), ord(b) + 1)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', default='ui/pages')
    ap.add_argument('--doc', default='docs/RACCOURCIS.md')
    ap.add_argument('--page', help='ne lire qu une page (sans .html)')
    a = ap.parse_args(argv)

    dossier = (RACINE / a.pages) if not Path(a.pages).is_absolute() else Path(a.pages)
    chemin_doc = (RACINE / a.doc) if not Path(a.doc).is_absolute() else Path(a.doc)
    if not dossier.is_dir():
        print('ERREUR : dossier des pages introuvable : %s' % dossier)
        return 2
    if not chemin_doc.is_file():
        print('ERREUR : releve introuvable : %s' % chemin_doc)
        return 2

    sources = sorted(dossier.glob('%s.html' % (a.page or '*')))
    commune = dossier.parent / 'global.js'
    if commune.is_file() and not a.page:
        sources.append(commune)
    if not sources:
        print('ERREUR : aucune page lue (--page %s ?)' % a.page)
        return 2

    md = chemin_doc.read_text(encoding='utf-8')
    documentees = touches_documentees(md) | lettres_de_plage(md)

    par_page, ecoutees = {}, set()
    for f in sources:
        t = touches_ecoutees(f.read_text(encoding='utf-8'))
        if t:
            par_page[f.stem] = t
            ecoutees |= t

    print('# verifier_raccourcis -- le panneau `?` dit-il la verite ?')
    print()
    print('%-14s %s' % ('page', 'touches ecoutees'))
    print('-' * 74)
    for nom in sorted(par_page):
        print('%-14s %s' % (nom, ' '.join(sorted(par_page[nom]))))
    print('-' * 74)
    print('%-14s %d touche(s) distincte(s) sur %d source(s)'
          % ('TOTAL', len(ecoutees), len(sources)))
    print()

    muettes = sorted(ecoutees - documentees)
    fantomes = sorted(documentees - ecoutees)
    if muettes:
        print('ECOUTEES ET NON DOCUMENTEES (%d) -- on ne peut pas les deviner :'
              % len(muettes))
        for t in muettes:
            ou = [p for p in sorted(par_page) if t in par_page[p]]
            print('  %-8s ecoutee par : %s' % (t, ', '.join(ou)))
        print()
    if fantomes:
        print('DOCUMENTEES ET PLUS ECOUTEES (%d) -- la doc promet un geste '
              'qui ne repond pas :' % len(fantomes))
        for t in fantomes:
            print('  %s' % t)
        print()

    print('PORTEE : le TEXTE des pages lues. `e.key === ...` et `!== ...`, la')
    print('plage /^[a-zA-Z]$/, et l indexation d une constante de lettres.')
    print('Ni keyCode, ni ecouteur assemble a l execution, ni ce que server.py')
    print('injecte. Une plage de lettres compte pour UNE entree (« lettre ») :')
    print('la documenter touche par touche serait illisible.')
    print()
    print('VERDICT, en DEUX chiffres qui ne disent pas la meme chose :')
    print('  %d touche(s) ecoutee(s) que le panneau ne montre pas,' % len(muettes))
    print('  %d touche(s) promise(s) que plus personne n ecoute.' % len(fantomes))
    if not ecoutees:
        print('  ZERO touche relevee : ce n est pas un feu vert, c est un')
        print('  instrument qui n a rien vu -- verifier --pages.')
        return 1
    if not muettes and not fantomes:
        print('  Le releve et le code disent la meme chose, sur ce que cet')
        print('  instrument sait lire.')
    return 1 if (muettes or fantomes) else 0


if __name__ == '__main__':
    sys.exit(main())
