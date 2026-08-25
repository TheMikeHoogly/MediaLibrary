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
import sys
import urllib.error
import urllib.request

MARQUEUR = '<!--UI:components-->'
BALISE = '<style id="ui-components">'
BALISE_TOKENS = 'id="ui-shared"'

# Les pages converties le 25/08. Une page ne s'ajoute ici qu'apres la preuve
# de cascade (`verifier_css_cascade.py --page <page>.html`).
ADOPTANTES = ('/residu', '/tranche')
# Le temoin : une page qui n'a PAS adopte. Sans lui, un serveur qui injecterait
# partout passerait ce banc en vert. `/faces` et pas `/upload` : `/upload` n'est
# pas une route (la page d'envoi est servie a `/`), et le premier essai reel a
# rendu 404 -- un temoin qu'on ne peut pas lire ne temoigne de rien.
TEMOIN = '/faces'

# Ce que la feuille commune DOIT porter. Si `components.css` se vide ou se
# tronque, la page rend nue sans qu'aucune erreur ne remonte.
ATTENDU = ('.btn', '.btn--confirmer', '.btn--destructif', '.btn--discret')


def chercher(hote, port, chemin, delai=10):
    """Rend le HTML, ou leve urllib.error.URLError / OSError."""
    url = "http://%s:%d%s" % (hote, port, chemin)
    with urllib.request.urlopen(url, timeout=delai) as r:
        return r.read().decode('utf-8', errors='replace')


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
    for chemin in ADOPTANTES + (TEMOIN,):
        role = "temoin" if chemin == TEMOIN else "adoptante"
        try:
            html = chercher(hote, port, chemin)
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
        griefs = (juger_temoin if chemin == TEMOIN
                  else juger_adoptante)(chemin, html)
        if griefs:
            ecrire("%-10s (%s) : %d GRIEF(S)" % (chemin, role, len(griefs)))
            for g in griefs:
                ecrire("             - " + g)
            fautes += len(griefs)
        else:
            ecrire("%-10s (%s) : ok  (%d octets)" % (chemin, role, len(html)))
    ecrire("")
    lues = len(ADOPTANTES) + 1 - len(muettes)
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
    return fautes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--hote', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8080)
    a = p.parse_args(argv)
    return 1 if verifier(a.hote, a.port) else 0


if __name__ == '__main__':
    sys.exit(main())
