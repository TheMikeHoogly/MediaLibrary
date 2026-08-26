#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Contrôle NÉGATIF des filtres — une valeur inventée doit rendre ZÉRO.
──────────────────────────────────────────────────────────────────────────────

POURQUOI CET INSTRUMENT EXISTE

Le 26/08, `/files?q=animal:Zzzznexistepas` rendait **1 500 photos**, et la page
les annonçait comme le résultat d'un FILTRE. Le jeton ne ressemblait à aucun
nom NU — `_extraire_noms` ne connaît aucun préfixe — il partait donc en
recherche sémantique, qui classe TOUT le fonds et ne rend jamais vide. Le même
défaut avait été corrigé le 21/08 pour `espece:licorne` et oublié sur les
quatre autres axes.

Ce qui rend ce défaut cher n'est pas le chiffre : c'est qu'un filtre muet se
lit comme un ACCORD. « Caline n'a aucune photo » a été conclu d'une recherche
qui, en réalité, ne cherchait rien — sur une chatte qui a vécu seize ans dans
cette maison.

**Un nom inventé doit rendre ZÉRO.** Le contrôle coûte une requête et vaut un
verdict. C'est le test qui manquait, et il manquait sur les cinq axes à la
fois : voilà pourquoi il est ici, une fois, pour tous.

CE QU'IL VÉRIFIE — DANS LES DEUX SENS

  NÉGATIF   `animal:Zzz…`, `personne:Zzz…`, `lieu:Zzz…`, `espece:licorne`,
            `couleur:rouge` (axe inconnu) → zéro photo, ET le refus est NOMMÉ
            dans la décomposition. Rendre zéro sans le dire serait un fonds
            pauvre ; le dire est ce qui distingue « ce nom n'existe pas » de
            « ce nom n'a pas de photo ».

  POSITIF   le nom le plus photographié de chaque magasin, un lieu réel,
            `espece:chat` → au moins une photo. **Sans ces contrôles-là, un
            moteur qui rendrait zéro pour TOUT serait vert** — le mode de
            panne des deux bancs que ce projet a déjà démasqués.

  FAUX      « <nom> : la chatte » et « 18:30 » ne sont PAS des filtres. Un
  POSITIF   garde-fou qui refuse une phrase ponctuée coûterait plus qu'il ne
            rapporte.

  CANAL     la page `/files?q=` autant que `/api/search` : le mensonge a été
            observé sur la PAGE, et les deux chemins doivent dire la même
            chose. C'est la divergence de canal du 15/08, en sens inverse.

CE QU'IL NE VOIT PAS

Il interroge un serveur VIVANT : il mesure le code qui TOURNE, pas celui qui
est sur le disque. Il lit `/api/serveur` d'abord et refuse de conclure si
`code_a_jour` est faux — une mesure sur l'ancien code est pire qu'aucune.
La VM de la sandbox n'atteint pas le LAN : ce banc ne tourne QUE sous Windows,
par `_commande_banc.txt`.

Il n'écrit rien, nulle part : famille `verifier_`, lecture seule.

USAGE
    python verifier_filtre_negatif.py
    python verifier_filtre_negatif.py --serveur=http://192.168.0.13:8080
    python verifier_filtre_negatif.py --json=_filtre_negatif.json

    Sortie 0 = tous les contrôles passent. 1 = au moins un manquement,
    ou une portée si réduite qu'elle ne prouve rien.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SERVEUR_DEFAUT = 'http://192.168.0.13:8080'
RACINE = Path(__file__).resolve().parent
LIEUX_FICHIER = RACINE / 'lieux.txt'

# Une valeur que personne ne portera jamais, et qui n'est pas non plus un mot
# de la langue : SigLIP ne doit pas pouvoir la « comprendre » par accident.
INVENTE = 'Zzzznexistepas'
AXE_INVENTE = 'couleur'

DELAI_S = 60          # une recherche sur 43 000 entrées, sur un NAS occupé


# ────────────────────────────────────────────────────── le plan (pur) ────────

def plan_des_controles(nom_personne, nom_animal, lieu):
    """La liste des contrôles, d'après ce que le fonds porte VRAIMENT.

    Les valeurs positives ne sont pas en dur : un banc qui teste « Luna » sur
    un fonds où Luna n'existe plus rendrait rouge sans qu'aucun code n'ait
    bougé. Ce qui n'a pas pu être trouvé n'est pas testé, et le rapport le
    DIT — un banc qui ne SAIT pas ne rend pas vert.
    """
    plan = [
        {'titre': 'animal inconnu', 'q': 'animal:' + INVENTE,
         'attente': 'zero_nomme', 'liste': 'noms_inconnus'},
        {'titre': 'personne inconnue', 'q': 'personne:' + INVENTE,
         'attente': 'zero_nomme', 'liste': 'noms_inconnus'},
        {'titre': 'lieu inconnu', 'q': 'lieu:' + INVENTE,
         'attente': 'zero_nomme', 'liste': 'noms_inconnus'},
        {'titre': 'espece inconnue', 'q': 'espece:licorne',
         'attente': 'zero_nomme', 'liste': 'especes_inconnues',
         'valeur': 'licorne'},
        {'titre': 'axe inconnu', 'q': AXE_INVENTE + ':rouge',
         'attente': 'zero_nomme', 'liste': 'axes_inconnus',
         'valeur': AXE_INVENTE},
        {'titre': 'espece connue', 'q': 'espece:chat',
         'attente': 'au_moins_un'},
        {'titre': 'heure, pas un axe', 'q': 'photos de 18:30',
         'attente': 'pas_de_refus'},
    ]
    if nom_animal:
        plan += [
            {'titre': 'animal connu, jeton', 'q': 'animal:' + nom_animal,
             'attente': 'au_moins_un'},
            {'titre': 'animal connu, nom nu', 'q': nom_animal,
             'attente': 'au_moins_un'},
            {'titre': 'un jeton faux empoisonne la requete',
             'q': 'animal:' + nom_animal + ' animal:' + INVENTE,
             'attente': 'zero_nomme', 'liste': 'noms_inconnus'},
            {'titre': 'phrase ponctuee, pas un filtre',
             'q': nom_animal + ' : la chatte', 'attente': 'pas_de_refus'},
        ]
    if nom_personne:
        plan += [
            {'titre': 'personne connue, jeton', 'q': 'personne:' + nom_personne,
             'attente': 'au_moins_un'},
        ]
    if lieu:
        plan += [
            {'titre': 'lieu connu, jeton', 'q': 'lieu:' + lieu,
             'attente': 'au_moins_un'},
        ]
    return plan


def verdict(controle, reponse):
    """(ok, motif) — pur : ce qu'on lit dans la réponse, rien d'autre."""
    if reponse is None:
        return False, "pas de reponse du serveur"
    if reponse.get('error'):
        return False, "erreur du serveur : " + str(reponse['error'])[:80]
    n = len(reponse.get('results') or [])
    refus = {c: list(reponse.get(c) or ())
             for c in ('noms_inconnus', 'axes_inconnus', 'especes_inconnues')}
    tous = [v for liste in refus.values() for v in liste]

    if controle['attente'] == 'zero_nomme':
        if n:
            return False, ("%d photo(s) rendues pour une valeur inventee "
                           "-- le filtre part en recherche semantique" % n)
        attendue = controle.get('valeur', INVENTE).lower()
        dans = [v for v in refus[controle['liste']] if attendue in v.lower()]
        if not dans:
            return False, ("zero photo, mais le refus n'est pas NOMME dans "
                           "%s : %r -- un fonds pauvre et un filtre "
                           "impossible se liraient pareil"
                           % (controle['liste'], refus[controle['liste']]))
        return True, "zero photo, refus nomme : " + dans[0]

    if controle['attente'] == 'au_moins_un':
        if tous:
            return False, ("une valeur REELLE a ete refusee : %s -- le "
                           "garde-fou mord ce qu'il devait proteger" % tous)
        if not n:
            return False, ("zero photo pour une valeur reelle -- un banc qui "
                           "rend zero partout serait vert pour rien")
        return True, "%d photo(s)" % n

    if controle['attente'] == 'pas_de_refus':
        if tous:
            return False, ("refuse a tort : %s -- une phrase ponctuee n'est "
                           "pas un filtre" % tous)
        return True, "aucun refus (%d photo(s))" % n

    return False, "attente inconnue : " + str(controle['attente'])


def valeur_js(html, marqueur):
    """La valeur JSON qui suit `marqueur` dans la page, ou None.

    On relit la page telle qu'elle est SERVIE : elle porte sa propre copie du
    résultat et de la décomposition. Croire qu'elle dit la même chose que
    `/api/search` est précisément ce qui a laissé la divergence de canal vivre
    du 15 au 22/08."""
    i = html.find(marqueur)
    if i < 0:
        return None
    try:
        valeur, _fin = json.JSONDecoder().raw_decode(html, i + len(marqueur))
    except ValueError:
        return None
    return valeur


def meta_de_la_page(html):
    """Ce que la PAGE a compris de la requête (`var SEARCHMETA = …`).

    Zéro photo ne suffit pas : sans cette décomposition, la page affiche un
    fonds vide au lieu de dire « je ne connais pas ce nom »."""
    v = valeur_js(html, 'var SEARCHMETA = ')
    return v if isinstance(v, dict) else None


def files_de_la_page(html):
    """Les photos que la PAGE `/files?q=` a mises sous les yeux.

    Le mensonge a été observé là, pas dans l'API : la page porte sa propre
    copie du résultat (`var FILES = …`). On la relit telle qu'elle est servie,
    au lieu de croire qu'elle dit la même chose que `/api/search`."""
    valeur = valeur_js(html, 'var FILES = ')
    return valeur if isinstance(valeur, list) else None


# ─────────────────────────────────────────────────────────── le réseau ───────

def demander(base, chemin, delai=DELAI_S):
    with urllib.request.urlopen(base.rstrip('/') + chemin, timeout=delai) as r:
        return r.read().decode('utf-8', errors='replace')


def demander_json(base, chemin, delai=DELAI_S):
    try:
        return json.loads(demander(base, chemin, delai))
    except Exception:                                         # noqa: BLE001
        return None


def chercher(base, requete, delai=DELAI_S):
    return demander_json(base, '/api/search?n=1500&q='
                         + urllib.parse.quote(requete), delai)


def noms_du_fonds(base):
    """(personne la plus photographiée, animal le plus photographié).

    `/api/names` trie déjà par volume. On exige `n > 0` : un nom de fiche sans
    photo ferait échouer le contrôle POSITIF pour une raison qui n'a rien à
    voir avec le filtre."""
    d = demander_json(base, '/api/names') or {}
    personne = animal = None
    for e in (d.get('noms') or []):
        if not (e.get('n') or 0) > 0:
            continue
        if e.get('genre') == 'personne' and personne is None:
            personne = e.get('nom')
        elif e.get('genre') == 'animal' and animal is None:
            animal = e.get('nom')
    return personne, animal


def premier_lieu():
    """Le premier lieu de `lieux.txt` — la même source que `lieux_connus()`."""
    try:
        for ligne in LIEUX_FICHIER.read_text(encoding='utf-8').splitlines():
            ligne = ligne.split('#')[0].strip()
            if ligne:
                return ligne
    except OSError:
        pass
    return None


# ────────────────────────────────────────────────────────── le rapport ───────

def rapport(resultats, portee, ecrire=print):
    """True si tout passe ET si la portée prouve quelque chose."""
    ecrire("")
    ecrire("=" * 70)
    ecrire("  CONTROLE NEGATIF DES FILTRES - une valeur inventee rend ZERO")
    ecrire("=" * 70)
    for r in resultats:
        ecrire("  %-4s %-34s %s" % ('OK' if r['ok'] else 'GRIEF',
                                    r['titre'][:34], r['motif'][:96]))
        if not r['ok']:
            ecrire("       requete : %s" % r['q'])
    griefs = [r for r in resultats if not r['ok']]
    ecrire("")
    ecrire("  PORTEE : %d controle(s) sur %d axes."
           % (len(resultats), portee.get('axes', 0)))
    for manque in portee.get('non_testes', []):
        ecrire("    NON TESTE : %s" % manque)
    ecrire("  %d grief(s)." % len(griefs))
    assez = portee.get('axes', 0) >= 4 and not portee.get('code_perime')
    if portee.get('code_perime'):
        ecrire("  Le serveur ne fait pas tourner le server.py du disque")
        ecrire("  (code_a_jour faux) : la mesure porte sur l'ANCIEN code.")
    if not assez:
        ecrire("  Portee insuffisante : ce banc ne rend pas vert sur si peu.")
    ecrire("=" * 70)
    return not griefs and assez


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Une valeur inventee doit rendre zero photo.")
    ap.add_argument('--serveur', default=SERVEUR_DEFAUT)
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    base = a.serveur

    etat = demander_json(base, '/api/serveur')
    if etat is None:
        print("  Serveur injoignable : %s" % base)
        print("  Ce banc interroge un serveur VIVANT ; la VM n'atteint pas le")
        print("  LAN. Il ne tourne que sous Windows, par _commande_banc.txt.")
        return 1
    code_perime = etat.get('code_a_jour') is False
    print("  serveur : pid %s, demarre il y a %s s, code_a_jour=%s"
          % (etat.get('pid'), etat.get('uptime_s'), etat.get('code_a_jour')))

    personne, animal = noms_du_fonds(base)
    lieu = premier_lieu()
    non_testes = []
    if not personne:
        non_testes.append("aucune personne photographiee trouvee "
                          "(/api/names) : axe personne sans controle POSITIF")
    if not animal:
        non_testes.append("aucun animal photographie trouve (/api/names) : "
                          "axe animal sans controle POSITIF")
    if not lieu:
        non_testes.append("lieux.txt illisible : axe lieu sans controle "
                          "POSITIF")

    plan = plan_des_controles(personne, animal, lieu)
    resultats = []
    for c in plan:
        reponse = chercher(base, c['q'])
        ok, motif = verdict(c, reponse)
        resultats.append({'titre': c['titre'], 'q': c['q'], 'ok': ok,
                          'motif': motif})

    # Le CANAL de la page : c'est la qu'on a vu 1 500 photos pour un nom
    # invente. L'API peut avoir raison pendant que la page ment.
    html = None
    try:
        html = demander(base, '/files?q='
                        + urllib.parse.quote('animal:' + INVENTE))
    except Exception as e:                                    # noqa: BLE001
        resultats.append({'titre': 'page /files?q=', 'q': 'animal:' + INVENTE,
                          'ok': False, 'motif': 'page injoignable : %s' % e})
    if html is not None:
        files = files_de_la_page(html)
        if files is None:
            resultats.append({'titre': 'page /files?q=',
                              'q': 'animal:' + INVENTE, 'ok': False,
                              'motif': "var FILES illisible dans la page"})
        else:
            resultats.append({'titre': 'page /files?q=',
                              'q': 'animal:' + INVENTE, 'ok': not files,
                              'motif': ("%d photo(s) sous les yeux" % len(files))
                              if files else "aucune photo affichee"})
        # ... et la page doit le DIRE. Une grille vide sans un mot se lit
        # comme un fonds pauvre : c'est la moitie du defaut, pas un detail.
        meta = meta_de_la_page(html)
        dit = list((meta or {}).get('noms_inconnus') or ())
        resultats.append({
            'titre': 'page /files?q= le DIT', 'q': 'animal:' + INVENTE,
            'ok': any(INVENTE.lower() in str(v).lower() for v in dit),
            'motif': ('la page annonce : ' + ', '.join(dit)) if dit else
                     ("la page ne dit rien du refus (SEARCHMETA=%s)"
                      % ('absent' if meta is None else 'sans noms_inconnus'))})

    portee = {'axes': 5, 'non_testes': non_testes, 'code_perime': code_perime}
    ok = rapport(resultats, portee)

    if a.json:
        Path(a.json).write_text(json.dumps(
            {'serveur': base, 'etat': etat, 'personne': personne,
             'animal': animal, 'lieu': lieu, 'portee': portee,
             'resultats': resultats, 'ok': ok},
            indent=2, ensure_ascii=False), encoding='utf-8')
        print("  rapport JSON : %s" % a.json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
