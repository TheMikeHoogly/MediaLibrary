#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verifier_pages_composants -- la feuille commune arrive-t-elle VRAIMENT ?

Pourquoi ce banc existe
-----------------------
`test_ui_composants.py` prouve le MECANISME : une fonction `_send_html` lue
par AST, un faux handler, une feuille factice. C'est une preuve de code.
Elle ne dit rien de la chaine reelle -- `ui/components.css` present a cote du
serveur, lu, mis en cache, insere dans la page que le navigateur recoit.

Entre les deux il y a tout ce que ce projet paye d'habitude : un fichier
absent, un chemin relatif au dossier courant, un cache jamais invalide, une
page qui porte le marqueur mais que le serveur ne fait pas passer par
`_send_html`. Un chantier de convergence qui casse ainsi ne se voit pas
dans les tests : il se voit sur l'ecran de Mike, et seulement la.

Ce banc interroge le serveur VIVANT. Il ne modifie rien -- famille
`verifier_`.

Ce qu'il refuse d'affirmer
--------------------------
1. **Un serveur injoignable n'est pas un succes.** Il rend 1 et le dit.
   Un banc qui rendrait 0 parce qu'il n'a rien pu verifier serait un feu vert.
2. **Le marqueur restant est une panne, pas un detail.** `<!--UI:components-->`
   dans la sortie veut dire que la page a demande la feuille et ne l'a pas eue.
3. **La page doit garder le DERNIER MOT.** Si la feuille commune arrivait
   apres le `<style>` de la page, la page perdrait la cascade au moment meme
   ou elle converge.
4. **Une page non convertie doit rester intacte.** C'est ce qui separe un
   opt-in d'une injection globale, et c'est la seule raison pour laquelle les
   neuf autres pages peuvent attendre leur tour sans risque.

Usage :
    python verifier_pages_composants.py [--hote 127.0.0.1] [--port 8080]

SORTIE EN ASCII PUR (console cp1252 de l'agent).
"""

import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

MARQUEUR = '<!--UI:components-->'
BALISE = '<style id="ui-components">'
BALISE_TOKENS = 'id="ui-shared"'

# Les pages converties le 25/08. Une page ne s'ajoute ici qu'apres la preuve
# de cascade (`verifier_css_cascade.py --page <page>.html`).
ADOPTANTES = ('/residu', '/tranche', '/sujets', '/people', '/pets')
# Le temoin : une page qui n'a PAS adopte. Sans lui, un serveur qui injecterait
# partout passerait ce banc en vert. Deux temoins ont ete essayes et ecartes,
# chacun par un essai REEL : `/upload` n'est pas une route (404, la page d'envoi
# est servie a `/`), et `/faces` repond 302 vers `/people` -- le banc lisait
# `/people` en croyant lire `/faces`. Un temoin qu'on ne peut pas lire, ou
# qu'on lit ailleurs, ne temoigne de rien. `/map` se sert elle-meme.
TEMOIN = '/map'

# Les autres pages servies, celles qui n'ont PAS adopte. Les trois
# universelles ne sont pas un opt-in : elles ont quitte les ONZE `<style>` a
# la fois, donc c'est sur les onze qu'il faut les revoir arriver -- pas
# seulement sur celles qui ont adopte les composants.
# `/faces` n'y est pas : la page a ete retiree, la route repond 302 vers
# `/people`. Un chemin qu'on ne peut pas lire chez lui ne temoigne de rien.
AUTRES = ('/', '/files', '/browse', '/reglages')

# Ce que la feuille commune DOIT porter. Si `components.css` se vide ou se
# tronque, la page rend nue sans qu'aucune erreur ne remonte.
ATTENDU = ('.btn', '.btn--confirmer', '.btn--destructif', '.btn--discret')

# Les trois declarations que les onze pages ecrivaient a l'identique et qui
# vivent desormais dans `ui/base.css` seul (25/08). Elles ne sont PAS un
# opt-in : elles valent pour les onze, converties ou non, et c'est pour ca que
# le temoin les subit comme les autres.
UNIVERSELLES = ('background', 'color', 'font-family')


def chercher(hote, port, chemin, delai=10):
    """Rend `(html, chemin REELLEMENT servi)`, ou leve URLError / OSError.

    Le chemin d'arrivee n'est pas un detail : urllib suit les redirections
    sans rien dire. `/faces` repond 302 vers `/people` sur ce serveur, et le
    banc a un jour ecrit « la page temoin (/faces) reste intacte » apres avoir
    lu `/people`. Nommer une page et en juger une autre, c'est exactement le
    genre de vert qui ne vaut rien.
    """
    url = "http://%s:%d%s" % (hote, port, chemin)
    with urllib.request.urlopen(url, timeout=delai) as r:
        arrivee = urllib.parse.urlsplit(r.geturl()).path or chemin
        return r.read().decode('utf-8', errors='replace'), arrivee


def style_de_la_page(html):
    """Position du premier `<style>` SANS id -- celui que la page ecrit.

    Les feuilles injectees portent toutes un id (`ui-components`,
    `ui-shared`, `appnav-css`). Le `<style>` nu est donc celui de la page,
    et c'est lui qui doit avoir le dernier mot.
    """
    i = html.find('<style>')
    return i if i >= 0 else None


def juger_adoptante(chemin, html):
    """Rend la liste des griefs. Vide = la page est bonne."""
    griefs = []
    if MARQUEUR in html:
        griefs.append("le marqueur est encore la : la page a demande la "
                      "feuille et ne l'a pas recue (ui/components.css "
                      "manquant ou illisible ?)")
        return griefs          # inutile de chercher plus loin
    i_feuille = html.find(BALISE)
    if i_feuille < 0:
        griefs.append("pas de " + BALISE + " : ni marqueur ni feuille, la "
                      "page ne passe peut-etre pas par _send_html")
        return griefs
    fin = html.find('</style>', i_feuille)
    corps = html[i_feuille:fin if fin > 0 else len(html)]
    for regle in ATTENDU:
        if regle + ' ' not in corps and regle + '{' not in corps:
            griefs.append("la feuille servie ne porte pas " + regle)
    i_page = style_de_la_page(html)
    if i_page is None:
        griefs.append("la page n'a plus de <style> a elle -- attendu tant "
                      "que la migration n'est pas finie ; a relire")
    elif i_feuille > i_page:
        griefs.append("la feuille commune arrive APRES le <style> de la "
                      "page : la page perd la cascade au moment ou elle "
                      "converge")
    if BALISE_TOKENS not in html:
        griefs.append("pas de " + BALISE_TOKENS + " : components.css utilise "
                      "var(--touch), var(--salle-3)... sans tokens il rend "
                      "des valeurs vides")
    return griefs


def universelles(html):
    """Les trois declarations arrivent-elles d'un seul endroit ?

    Deux griefs distincts : la feuille partagee ne les porte pas (elles sont
    perdues), ou une page les redeclare (deux sources pour une decision --
    et comme `base.css` est injecte a `</head>`, c'est la PAGE qui perd,
    silencieusement).
    """
    griefs = []
    i = html.find(BALISE_TOKENS)
    part = html[i:html.find('</style>', i)] if i >= 0 else ''
    manquantes = [p for p in UNIVERSELLES
                  if ('body' not in part or (p + ':') not in part
                      and (p + ' :') not in part)]
    if manquantes:
        griefs.append("la feuille partagee ne porte pas les universelles : "
                      + ", ".join(manquantes))
    for bloc in re.findall(r'<style>(.*?)</style>', html, re.S):
        for regle in re.findall(r'(?<![\w-])body\s*\{([^}]*)\}', bloc, re.S):
            redites = [p for p in UNIVERSELLES if p in regle]
            if redites:
                griefs.append("la page redeclare " + ", ".join(redites)
                              + " sur body : deux sources pour une decision, "
                              "et c'est la page qui perd (base.css est injecte "
                              "a </head>)")
    return griefs


def juger_temoin(chemin, html):
    griefs = []
    if BALISE in html:
        griefs.append("une page NON convertie recoit la feuille commune : "
                      "ce n'est plus un opt-in, les neuf pages restantes "
                      "sont exposees")
    if MARQUEUR in html:
        griefs.append("le marqueur traine dans une page non convertie")
    return griefs


def verifier(hote, port, ecrire=print, chercher=chercher):
    """Rend le nombre de fautes. 0 = l'adoption tient en reel.

    Deux facons de ne pas savoir, et elles ne se disent pas pareil : le
    serveur qui ne repond pas, et la route qui n'existe pas. Le premier essai
    reel de ce banc les a confondues et a ecrit "rien n'a pu etre verifie"
    alors que deux pages sur trois venaient d'etre lues et jugees bonnes. Un
    banc qui se trompe sur ce qu'il a vu ne vaut pas mieux que pas de banc.
    """
    ecrire("# verifier_pages_composants -- http://%s:%d" % (hote, port))
    ecrire("")
    fautes = 0
    muettes = []
    for chemin in ADOPTANTES + (TEMOIN,) + AUTRES:
        role = ("temoin" if chemin == TEMOIN
                else "adoptante" if chemin in ADOPTANTES else "autre")
        try:
            html, arrivee = chercher(hote, port, chemin)
        except urllib.error.HTTPError as e:
            ecrire("%-10s (%s) : ROUTE MUETTE -- HTTP %s" % (chemin, role,
                                                             e.code))
            muettes.append((chemin, "HTTP %s" % e.code))
            fautes += 1
            continue
        except (urllib.error.URLError, OSError) as e:
            ecrire("%-10s (%s) : SERVEUR MUET -- %s" % (chemin, role, e))
            muettes.append((chemin, "serveur injoignable"))
            fautes += 1
            continue
        if arrivee != chemin:
            ecrire("%-10s (%s) : REPOND AILLEURS -- servie depuis %s"
                   % (chemin, role, arrivee))
            ecrire("             une page nommee ici et lue la-bas ne prouve "
                   "rien : le verdict ne peut pas parler d'elle")
            fautes += 1
            continue
        griefs = (juger_adoptante(chemin, html)
                  if chemin in ADOPTANTES else juger_temoin(chemin, html))
        griefs += universelles(html)
        if griefs:
            ecrire("%-10s (%s) : %d GRIEF(S)" % (chemin, role, len(griefs)))
            for g in griefs:
                ecrire("             - " + g)
            fautes += len(griefs)
        else:
            ecrire("%-10s (%s) : ok  (%d octets)" % (chemin, role, len(html)))
    ecrire("")
    lues = len(ADOPTANTES) + 1 + len(AUTRES) - len(muettes)
    if muettes:
        ecrire("VERDICT : %d page(s) lue(s), %d NON REGARDEE(S) :"
               % (lues, len(muettes)))
        for chemin, pourquoi in muettes:
            ecrire("          %-10s %s" % (chemin, pourquoi))
        ecrire("Sur celles-la il n'y a pas de faute : il n'y a pas de preuve.")
    elif fautes:
        ecrire("VERDICT : %d grief(s). L'adoption ne tient pas en reel."
               % fautes)
    else:
        ecrire("VERDICT : les %d pages converties recoivent la feuille "
               "commune," % len(ADOPTANTES))
        ecrire("          elles gardent le dernier mot, et la page temoin "
               "(%s) reste intacte." % TEMOIN)
        ecrire("          Les trois universelles arrivent d'un seul endroit "
               "sur les %d pages lues." % (len(ADOPTANTES) + 1 + len(AUTRES)))
    return fautes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--hote', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8080)
    a = p.parse_args(argv)
    return 1 if verifier(a.hote, a.port) else 0


if __name__ == '__main__':
    sys.exit(main())
