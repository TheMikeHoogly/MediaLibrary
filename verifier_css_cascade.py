#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vérification — hisser une règle CSS sans changer ce que le navigateur calcule
──────────────────────────────────────────────────────────────────────────────

POURQUOI CET INSTRUMENT EXISTE

Les onze pages sont sorties du monolithe avec une preuve simple et forte :
**l'octet servi est identique**. Le CSS commun ne peut pas s'appuyer dessus —
hisser une règle d'un `<style>` de page vers une feuille partagée CHANGE
l'octet servi par construction. Sans preuve de remplacement, l'extraction se
ferait à l'œil, sur onze pages dont une fait 1 594 lignes de style.

LA PREUVE : « IDENTIQUE APRÈS LA CASCADE »

Ce qu'un navigateur retient d'une feuille, ce n'est pas son texte : c'est,
pour chaque `(contexte @, sélecteur, propriété)`, **la déclaration qui
gagne** — la dernière écrite à spécificité égale. Cet instrument reconstruit
cette table AVANT et APRÈS, et exige qu'elle soit identique. Une règle peut
donc changer de fichier, de place, de voisinage : tant que la table ne bouge
pas, la page rend pareil.

CE QU'IL NE SAIT PAS DÉCIDER — ET QU'IL NOMME AU LIEU DE LE TAIRE

Un instrument qui rendrait « identique » sans dire ce qu'il n'a pas regardé
serait pire que rien : il donnerait la permission d'aller vite là où il faut
aller lentement. Les cinq angles morts sont COMPTÉS et DITS :

  1. **Les raccourcis.** `margin` et `margin-top` sont deux propriétés pour
     cet instrument, une seule pour le navigateur. Un `margin:0` qui passe
     devant un `margin-top:4px` casse la page sans que la table bouge.
  2. **`!important`.** Il renverse l'ordre ; la table le note, mais deux
     `!important` de sélecteurs différents restent hors de portée.
  3. **Deux sélecteurs qui visent les mêmes éléments sans s'écrire pareil**
     (`.a.b` et `.b.a`, `div > p` et `div>p` après normalisation partielle).
     À spécificité égale, leur ordre relatif compte — et rien ici ne sait
     qu'ils se croisent.
  4. **Les blocs opaques** — `@keyframes`, `@font-face` : comparés comme du
     TEXTE, pas comme une cascade.
  5. **Le `style=""` en ligne** dans le HTML, que cet instrument ne lit pas.

CE QU'IL NE FAIT PAS

Il ne modifie aucun fichier : famille `verifier_`, lecture seule.

USAGE
    python verifier_css_cascade.py --commun
    python verifier_css_cascade.py --avant a.css b.css --apres c.css d.css
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
PAGES_DIR = RACINE / 'ui' / 'pages'

# Ces at-règles portent un bloc qui n'est PAS une cascade : on les compare
# comme du texte normalisé, et on le dit.
OPAQUES = {'keyframes', '-webkit-keyframes', 'font-face', 'counter-style',
           'property', 'page', 'font-feature-values'}

LISTE_MAX = 40


# ─────────────────────────────── lecture ───────────────────────────────

def sans_commentaires(css):
    """Retire les `/* … */` sans toucher à ce qui vit dans une chaîne."""
    out, i, n = [], 0, len(css)
    while i < n:
        if css.startswith('/*', i):
            j = css.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        c = css[i]
        if c in '"\'':
            j, fin = i + 1, i + 1
            while j < n:
                if css[j] == '\\':
                    j += 2
                    continue
                if css[j] == c:
                    fin = j
                    break
                j += 1
            else:
                fin = n - 1
            out.append(css[i:fin + 1])
            i = fin + 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def styles_de_page(html):
    """Le contenu des blocs `<style>` d'une page, concaténé dans l'ordre."""
    bas = html.lower()
    out, i = [], 0
    while True:
        d = bas.find('<style', i)
        if d < 0:
            break
        d = bas.find('>', d)
        if d < 0:
            break
        f = bas.find('</style>', d)
        if f < 0:
            break
        out.append(html[d + 1:f])
        i = f + 8
    return '\n'.join(out)


# ─────────────────────────────── analyse ───────────────────────────────

def _fin_de_bloc(css, debut):
    """Index du `}` fermant le bloc ouvert en `debut`, en tenant les chaînes."""
    profondeur, i, n = 0, debut, len(css)
    while i < n:
        c = css[i]
        if c in '"\'':
            j = i + 1
            while j < n and css[j] != c:
                j += 2 if css[j] == '\\' else 1
            i = j + 1
            continue
        if c == '{':
            profondeur += 1
        elif c == '}':
            profondeur -= 1
            if profondeur == 0:
                return i
        i += 1
    return n


def _declarations(corps):
    """`[(propriete, valeur, important)]` d'un corps de règle."""
    out = []
    for morceau in _decouper(corps, ';'):
        morceau = morceau.strip()
        if not morceau:
            continue
        parts = _decouper(morceau, ':', 1)
        if len(parts) != 2:
            continue
        prop = parts[0].strip().lower()
        val = ' '.join(parts[1].split())
        important = val.lower().endswith('!important')
        if important:
            val = val[:-len('!important')].rstrip().rstrip('!').rstrip()
            val = ' '.join(val.split())
        if prop:
            out.append((prop, val, important))
    return out


def _decouper(texte, sep, maxi=0):
    """Découpe en ignorant ce qui est entre parenthèses ou entre quotes."""
    out, courant, prof, i, n = [], [], 0, 0, len(texte)
    while i < n:
        c = texte[i]
        if c in '"\'':
            j = i + 1
            while j < n and texte[j] != c:
                j += 2 if texte[j] == '\\' else 1
            courant.append(texte[i:j + 1])
            i = j + 1
            continue
        if c == '(':
            prof += 1
        elif c == ')':
            prof = max(0, prof - 1)
        if c == sep and prof == 0 and (not maxi or len(out) < maxi):
            out.append(''.join(courant))
            courant = []
            i += 1
            continue
        courant.append(c)
        i += 1
    out.append(''.join(courant))
    return out


_NOMBRE = re.compile(r'^([+-]?)(\d*\.?\d+)([a-z%]*)$', re.I)


def normalise_valeur(v):
    """La même valeur écrite autrement doit se comparer égale.

    Observé au premier contact réel (25/08) : six des trente-deux
    « discordances » entre pages étaient `.01ms` contre `0.01ms` — la même
    durée, deux écritures. Un instrument qui compte ça comme un écart gonfle
    ses alarmes de 19 %, et des alarmes qu'on apprend à ignorer ne protègent
    plus rien.

    Ne touche à RIEN dès qu'une chaîne est en jeu : `content: ".01"` est un
    texte, pas un nombre."""
    if '"' in v or "'" in v:
        return v
    out = []
    for tok in re.split(r'([\s,()])', v):
        m = _NOMBRE.match(tok)
        if m:
            signe, nb, unite = m.groups()
            out.append(signe + ('%g' % float(nb)) + unite.lower())
        else:
            out.append(tok)
    return ''.join(out)


def _normalise_selecteur(s):
    return ' '.join(s.split())


def analyser(css, source=''):
    """Rend `(regles, opaques, non_decidables)`.

    `regles` : [{contexte, selecteur, propriete, valeur, important, ordre,
    source}] dans l'ordre du document.
    `opaques` : [(contexte, prelude, texte normalisé)].
    `non_decidables` : [texte] — ce que l'analyse a rencontré et ne sait pas
    juger (at-règle en instruction, `@import`…)."""
    css = sans_commentaires(css)
    regles, opaques, non_dec = [], [], []
    ordre = [0]

    def bloc(texte, contexte):
        i, n, tampon = 0, len(texte), []
        while i < n:
            c = texte[i]
            if c == '{':
                prelude = ''.join(tampon).strip()
                tampon = []
                fin = _fin_de_bloc(texte, i)
                corps = texte[i + 1:fin]
                if prelude.startswith('@'):
                    nom = prelude[1:].split()[0].lower() if len(prelude) > 1 \
                        else ''
                    if nom in OPAQUES:
                        opaques.append((contexte, ' '.join(prelude.split()),
                                        ' '.join(corps.split())))
                    else:
                        sous = contexte + (' && ' if contexte else '') \
                            + ' '.join(prelude.split())
                        bloc(corps, sous)
                else:
                    for sel in _decouper(prelude, ','):
                        sel = _normalise_selecteur(sel)
                        if not sel:
                            continue
                        for prop, val, imp in _declarations(corps):
                            ordre[0] += 1
                            regles.append({
                                'contexte': contexte, 'selecteur': sel,
                                'propriete': prop, 'valeur': val,
                                'important': imp, 'ordre': ordre[0],
                                'source': source})
                i = fin + 1
                continue
            if c == ';' and ''.join(tampon).strip().startswith('@'):
                non_dec.append(' '.join(''.join(tampon).split()) + ';')
                tampon = []
                i += 1
                continue
            tampon.append(c)
            i += 1

    bloc(css, '')
    return regles, opaques, non_dec


# ─────────────────────────────── cascade ───────────────────────────────

def gagnantes(regles):
    """`(contexte, selecteur, propriete) -> (valeur, important)`.

    La dernière écrite gagne ; un `!important` bat un non-important quel que
    soit l'ordre. C'est la cascade, réduite à ce dont l'extraction peut
    changer l'issue."""
    out = {}
    for r in regles:
        cle = (r['contexte'], r['selecteur'], r['propriete'])
        vu = out.get(cle)
        if vu is None or r['important'] or not vu[1]:
            out[cle] = (normalise_valeur(r['valeur']), r['important'])
    return out


RACCOURCIS = {
    'margin': ('margin-top', 'margin-right', 'margin-bottom', 'margin-left'),
    'padding': ('padding-top', 'padding-right', 'padding-bottom',
                'padding-left'),
    'border': ('border-width', 'border-style', 'border-color'),
    'background': ('background-color', 'background-image', 'background-size',
                   'background-position', 'background-repeat'),
    'font': ('font-size', 'font-family', 'font-weight', 'line-height'),
    'flex': ('flex-grow', 'flex-shrink', 'flex-basis'),
    'grid': ('grid-template-columns', 'grid-template-rows', 'grid-auto-flow'),
    'inset': ('top', 'right', 'bottom', 'left'),
    'overflow': ('overflow-x', 'overflow-y'),
    'gap': ('row-gap', 'column-gap'),
}


def collisions_de_raccourcis(regles):
    """Les `(contexte, sélecteur)` où un raccourci et une de ses longues
    formes cohabitent. L'ordre y compte, et la table des gagnantes ne le voit
    pas : c'est l'angle mort n°1, il se COMPTE."""
    par_sel = {}
    for r in regles:
        par_sel.setdefault((r['contexte'], r['selecteur']), set()).add(
            r['propriete'])
    out = []
    for cle, props in par_sel.items():
        for court, longues in RACCOURCIS.items():
            if court in props and props.intersection(longues):
                out.append((cle[0], cle[1], court,
                            sorted(props.intersection(longues))))
    return sorted(out)


_IDENT = re.compile(r'[.#]([A-Za-z_][\w-]*)|\[\s*([A-Za-z_][\w-]*)')


_JETON = re.compile(r'[A-Za-z0-9_-]+')


def identifiants(selecteur):
    """Les classes, id et noms d'attribut qu'un sélecteur EXIGE."""
    out = set()
    for cls, attr in _IDENT.findall(selecteur):
        out.add(cls or attr)
    return out


def corpus_de_page(html):
    """La source ou l'on cherche la PREUVE qu'un element existe.

    Retire les commentaires HTML et les blocs `<style>`. Le CSS decrit ce qui
    SERAIT peint, jamais ce qui EXISTE : une classe qui n'apparait que dans
    une regle -- ou pire, dans une phrase en francais a l'interieur d'un
    commentaire CSS -- n'est portee par aucun element.

    Ce n'est pas une precaution theorique. En convertissant `subjects.html` le
    25/08, le commentaire « ... viennent de la feuille commune » a suffi pour
    que les six regles `.feuille` soient declarees ACTIVES sur une page qui
    n'en porte aucune. Six fausses alarmes nees d'un mot de prose -- et une
    alarme qu'on apprend a ignorer ne protege plus rien.

    Le JS, lui, RESTE : c'est la ou les classes se posent vraiment, et la
    limite assumee de l'instrument (`'btn--' + genre`) vit la.
    """
    sans = re.sub(r'<!--.*?-->', ' ', html, flags=re.S)
    return re.sub(r'<style\b[^>]*>.*?</style>', ' ', sans,
                  flags=re.S | re.I)


def jetons(source):
    """Les noms ENTIERS que porte une source : tout ce qui est separe par un
    caractere qu'un nom de classe CSS ne peut pas contenir.

    `class="a b"`, `className='a b'`, `classList.add("a")` donnent tous `a`.
    `toastP`, `vues`, `vue-annuaire`, `--f-donnees` n'en donnent AUCUN qui
    vaille `toast`, `vue` ou `donnee` -- et c'est le point : chercher par
    sous-chaine trouvait les trois.
    """
    return set(_JETON.findall(source))


def mord_sur(selecteur, source):
    """Ce sélecteur peut-il toucher un élément de cette page ?

    SUR-APPROXIMATION VOLONTAIRE : on répond OUI dès qu'on ne peut pas prouver
    le contraire. Adopter une feuille de composants apporte des règles que la
    page n'utilise pas — `.planche`, `.toast`, `.chip` sur une page qui n'en a
    aucun. Les compter comme des changements noierait le seul qui compte.

    La preuve du contraire est un texte : si le nom de classe n'apparaît comme
    JETON ENTIER nulle part dans le markup ou le JS de la page, aucun élément
    ne peut le porter. **Ses deux limites, mesurées** : une classe construite
    par morceaux en JavaScript (`'btn--' + genre`) est dite inerte à tort, et
    un jeton qui n'est pas une classe (`get('vue')` dans une URL) est dit
    actif à tort. La sortie les COMPTE au lieu de les taire.

    `source` accepte une chaîne (tokenisée ici) ou un ensemble déjà tokenisé —
    sur une page de 35 Ko et trois cents sélecteurs, tokeniser une fois vaut
    mieux que trois cents.
    """
    ids = identifiants(selecteur)
    if not ids:
        return True                      # sélecteur de type : toujours possible
    dispo = source if isinstance(source, (set, frozenset)) else jetons(source)
    return ids <= dispo


def comparer(avant_css, apres_css, source_page=None):
    """Rend le dict de rapport. `*_css` : liste de (nom, texte)."""
    def cumul(paquet):
        regles, opaques, non_dec = [], [], []
        for nom, texte in paquet:
            r, o, n = analyser(texte, source=nom)
            regles += r
            opaques += o
            non_dec += n
        return regles, opaques, non_dec

    ra, oa, na = cumul(avant_css)
    rb, ob, nb = cumul(apres_css)
    ga, gb = gagnantes(ra), gagnantes(rb)

    disparues = sorted(set(ga) - set(gb))
    apparues = sorted(set(gb) - set(ga))
    changees = sorted(c for c in (set(ga) & set(gb)) if ga[c] != gb[c])

    def tri(cles):
        if source_page is None:
            return list(cles), []
        act = [c for c in cles if mord_sur(c[1], source_page)]
        return act, [c for c in cles if c not in act]

    apparues_a, apparues_i = tri(apparues)
    disparues_a, disparues_i = tri(disparues)
    changees_a, changees_i = tri(changees)

    return {
        'inertes_connues': source_page is not None,
        'apparues_actives': apparues_a, 'apparues_inertes': apparues_i,
        'disparues_actives': disparues_a, 'disparues_inertes': disparues_i,
        'changees_actives': changees_a, 'changees_inertes': changees_i,
        'identique_sur_ce_qui_mord': not (apparues_a or disparues_a
                                          or changees_a),
        'declarations_avant': len(ra), 'declarations_apres': len(rb),
        'gagnantes_avant': len(ga), 'gagnantes_apres': len(gb),
        'disparues': disparues, 'apparues': apparues, 'changees': changees,
        'identique': not (disparues or apparues or changees),
        'opaques_avant': sorted(oa), 'opaques_apres': sorted(ob),
        'opaques_differents': sorted(oa) != sorted(ob),
        'importants': sum(1 for r in rb if r['important']),
        'raccourcis': collisions_de_raccourcis(rb),
        'non_decidables': sorted(set(na) | set(nb)),
    }


def rapport(r, ecrire=print):
    ecrire("")
    ecrire("=" * 74)
    ecrire("  CSS — IDENTIQUE APRES LA CASCADE ?")
    ecrire("=" * 74)
    ecrire("  declarations lues   : %d avant, %d apres"
           % (r['declarations_avant'], r['declarations_apres']))
    ecrire("  gagnantes           : %d avant, %d apres"
           % (r['gagnantes_avant'], r['gagnantes_apres']))
    ecrire("  disparues           : %d" % len(r['disparues']))
    ecrire("  apparues            : %d" % len(r['apparues']))
    ecrire("  valeurs changees    : %d" % len(r['changees']))

    if r.get('inertes_connues'):
        ecrire("")
        ecrire("  Dont INERTES sur cette page (aucun element ne peut les")
        ecrire("  porter) : %d apparues, %d disparues, %d changees."
               % (len(r['apparues_inertes']), len(r['disparues_inertes']),
                  len(r['changees_inertes'])))
        ecrire("  Une classe batie par morceaux en JS y echappe : ce compte")
        ecrire("  est un PLANCHER, pas une certitude.")

    for titre, cle in (("DISPARUES", 'disparues_actives' if
                        r.get('inertes_connues') else 'disparues'),
                       ("APPARUES", 'apparues_actives' if
                        r.get('inertes_connues') else 'apparues'),
                       ("CHANGEES", 'changees_actives' if
                        r.get('inertes_connues') else 'changees')):
        lignes = r[cle]
        if not lignes:
            continue
        ecrire("")
        ecrire("  %s (%d) :" % (titre, len(lignes)))
        for c in lignes[:LISTE_MAX]:
            ecrire("    %s%s { %s }"
                   % (("%s " % c[0]) if c[0] else "", c[1], c[2]))
        if len(lignes) > LISTE_MAX:
            ecrire("    ... et %d autre(s) non listees"
                   % (len(lignes) - LISTE_MAX))

    ecrire("")
    ecrire("  CE QUE CET INSTRUMENT NE SAIT PAS DECIDER :")
    ecrire("    raccourcis en collision : %d  (margin vs margin-top : deux"
           % len(r['raccourcis']))
    ecrire("      proprietes ici, une seule pour le navigateur)")
    ecrire("    declarations !important : %d" % r['importants'])
    ecrire("    blocs opaques           : %d %s"
           % (len(r['opaques_apres']),
              "— ET ILS DIFFERENT" if r['opaques_differents'] else "(inchanges)"))
    ecrire("    at-regles en instruction: %d" % len(r['non_decidables']))
    ecrire("    Deux selecteurs qui visent les memes elements sans s ecrire")
    ecrire("    pareil, et le style= en ligne : hors de portee, toujours.")

    ecrire("")
    vert = (r['identique'] if not r.get('inertes_connues')
            else r['identique_sur_ce_qui_mord'])
    if vert and not r['opaques_differents']:
        ecrire("  IDENTIQUE sur tout ce que cet instrument sait decider%s."
               % (" (regles inertes mises a part)"
                  if r.get('inertes_connues') else ""))
        ecrire("  Ce n est PAS un feu vert : lire les angles morts ci-dessus.")
    else:
        ecrire("  DIFFERENT. Ne pas livrer l extraction en l etat.")
    ecrire("=" * 74)
    return r


# ─────────────────────── inventaire du CSS commun ───────────────────────

def pages(dossier=None):
    """`{nom de page: texte du <style>}`."""
    d = Path(dossier or PAGES_DIR)
    out = {}
    for p in sorted(d.glob('*.html')):
        out[p.stem] = styles_de_page(p.read_text(encoding='utf-8'))
    return out


def commun(par_page):
    """Ce que les pages déclarent À L'IDENTIQUE, et ce que ça pèse.

    Une déclaration n'est hissable que si TOUTES les pages qui la déclarent
    lui donnent la même valeur — sinon la hisser en change une."""
    valeurs, presence = {}, {}
    brutes = {}
    for nom, css in par_page.items():
        regles, _o, _n = analyser(css, source=nom)
        for r in regles:
            cle = (r['contexte'], r['selecteur'], r['propriete'])
            valeurs.setdefault(cle, set()).add(normalise_valeur(r['valeur']))
            brutes.setdefault(cle, set()).add(r['valeur'])
            presence.setdefault(cle, set()).add(nom)
    partagees = {c: presence[c] for c in presence if len(presence[c]) > 1}
    unanimes = {c: p for c, p in partagees.items() if len(valeurs[c]) == 1}
    discordantes = {c: p for c, p in partagees.items() if len(valeurs[c]) > 1}
    # Écrites autrement, mais identiques : hissables, et il faut le DIRE —
    # sinon on croit à un écart de fond là où il n'y a qu'une écriture.
    formes = {c: p for c, p in unanimes.items() if len(brutes[c]) > 1}
    octets = sum(len("%s:%s;" % (c[2], sorted(valeurs[c])[0]))
                 * (len(unanimes[c]) - 1) for c in unanimes)
    return {'declarations': len(presence), 'partagees': len(partagees),
            'hissables': len(unanimes), 'discordantes': len(discordantes),
            'ecritures_differentes': len(formes),
            'octets_economises': octets,
            'par_nombre_de_pages': _histogramme(unanimes),
            'exemples_discordants': sorted(discordantes)[:LISTE_MAX],
            'exemples_ecritures': sorted(formes)[:LISTE_MAX]}


def _histogramme(unanimes):
    h = {}
    for cle, p in unanimes.items():
        h[len(p)] = h.get(len(p), 0) + 1
    return dict(sorted(h.items(), reverse=True))


def rapport_commun(r, ecrire=print):
    ecrire("")
    ecrire("=" * 74)
    ecrire("  CE QUE LES ONZE PAGES ONT EN COMMUN")
    ecrire("=" * 74)
    ecrire("  declarations distinctes      : %d" % r['declarations'])
    ecrire("  declarees par plusieurs pages: %d" % r['partagees'])
    ecrire("  dont HISSABLES (meme valeur) : %d" % r['hissables'])
    ecrire("  dont DISCORDANTES            : %d  <-- a NE PAS hisser"
           % r['discordantes'])
    ecrire("  dont ecrites AUTREMENT        : %d  (meme valeur, autre"
           % r.get('ecritures_differentes', 0))
    ecrire("     ecriture : .01ms contre 0.01ms — hissables quand meme)")
    ecrire("  octets economises (estime)   : %.1f Ko"
           % (r['octets_economises'] / 1024.0))
    ecrire("")
    ecrire("  hissables, par nombre de pages qui les partagent :")
    for n, combien in r['par_nombre_de_pages'].items():
        ecrire("    dans %2d pages : %d declaration(s)" % (n, combien))
    if r['exemples_discordants']:
        ecrire("")
        ecrire("  DISCORDANTES — meme selecteur, meme propriete, valeurs")
        ecrire("  DIFFERENTES selon la page. Les hisser en casserait une :")
        for c in r['exemples_discordants']:
            ecrire("    %s%s { %s }" % (("%s " % c[0]) if c[0] else "",
                                        c[1], c[2]))
    ecrire("=" * 74)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--commun', action='store_true',
                    help="inventaire de ce que les pages partagent")
    ap.add_argument('--avant', nargs='*', default=[])
    ap.add_argument('--apres', nargs='*', default=[])
    ap.add_argument('--page', default='',
                    help="la page HTML dont on juge : ce qui ne peut mordre "
                         "aucun de ses elements est compte a part")
    ap.add_argument('--json', dest='sortie_json', default='')
    a = ap.parse_args(argv)

    if a.commun == bool(a.avant or a.apres):
        print("il faut --commun, OU --avant … --apres … (pas les deux).")
        return 2

    if a.commun:
        r = rapport_commun(commun(pages()))
    else:
        if not a.avant or not a.apres:
            print("--avant et --apres veulent chacun au moins un fichier.")
            return 2
        def lire(noms):
            out = []
            for n in noms:
                p = Path(n)
                if not p.is_file():
                    print("fichier introuvable : %s" % n)
                    return None
                texte = p.read_text(encoding='utf-8')
                out.append((os.path.basename(n),
                            styles_de_page(texte)
                            if p.suffix.lower() in ('.html', '.htm')
                            else texte))
            return out
        av, ap_ = lire(a.avant), lire(a.apres)
        if av is None or ap_ is None:
            return 2
        src = None
        if a.page:
            if not Path(a.page).is_file():
                print("page introuvable : %s" % a.page)
                return 2
            src = jetons(corpus_de_page(
                Path(a.page).read_text(encoding='utf-8')))
        r = rapport(comparer(av, ap_, source_page=src))

    if a.sortie_json:
        Path(a.sortie_json).write_text(
            json.dumps(r, ensure_ascii=False, indent=1, default=list),
            encoding='utf-8')
        print("  ecrit : %s" % a.sortie_json)
    if r.get('inertes_connues'):
        return 0 if r.get('identique_sur_ce_qui_mord') else 1
    return 0 if r.get('identique', True) else 1


if __name__ == '__main__':
    sys.exit(main())
