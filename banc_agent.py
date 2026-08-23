#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
banc_agent — faire tourner un BANC sous Windows, et en lire la sortie
──────────────────────────────────────────────────────────────────────────────

POURQUOI, ET CE QUE ÇA A COÛTÉ

Le 20/08, un banc écrit dans la sandbox n'a pas pu tourner : il interroge
`GET /api/search` — c'est le serveur qui détient SigLIP — et la VM se l'est vu
refuser par sa propre sortie réseau (`X-Proxy-Error: blocked-by-allowlist`).
Rien de cassé côté projet : la sandbox n'a simplement pas le droit d'appeler le
LAN. Le banc a donc été livré NON TOURNÉ, et c'est Mike qui l'a lancé à la
main — six espèces d'un coup, et sa sortie a REFUTÉ ce que j'avais conclu de
deux échantillons. La leçon est double : le banc avait raison d'exister, et
l'aller-retour par le clavier de Mike coûte une demi-journée.

`pilotage` a donné à la sandbox le redémarrage. `git_agent` lui a donné la
livraison. Il manquait la MESURE : pouvoir lancer un banc du projet sur la
machine où vivent la base, le NAS et le serveur, et en lire la sortie.

CE N'EST PAS UN SHELL — C'EST UNE PORTE

Un agent qui exécuterait ce qu'on lui écrit serait une porte ouverte sur la
machine de Mike, pour un gain qui ne le vaut pas. Trois barrières, dans cet
ordre :

  1. **Aucun shell.** L'ordre est découpé en arguments et passé tel quel à
     `subprocess.run([...])`. Il n'existe aucun endroit où `&&`, `|`, `>` ou
     une substitution seraient interprétés — ils ne sont pas filtrés, ils sont
     sans effet.
  2. **Une liste de FAMILLES en lecture seule.** Seuls `mesure_`, `verifier_`,
     `diagnostic_`, `comptes_`, `inventaire_`, `test_` et `eval_` peuvent être
     lancés. Ce sont, dans ce projet, les scripts qui MESURENT. Les familles
     qui ÉCRIVENT — `appliquer_`, `purger_`, `nettoyer_`, `renommage`,
     `migrate_`, `installer`, `server` — n'ont pas de mot ici, et il n'y a pas
     de `force=` pour les ouvrir : ce qui modifie le fonds reste un geste de
     Mike, comme ce qui défait reste un geste de Mike chez `git_agent`.
  3. **Le script doit exister à la RACINE du projet.** Pas de séparateur, pas
     de `..`, pas de chemin absolu : le nom est un nom de fichier, sinon rien.

Les ARGUMENTS sont contraints au même esprit : `[A-Za-z0-9_.:/=-]`, jamais
d'espace à l'intérieur, jamais de quote. C'est assez pour `--base copie.db
--exemples 14`, et trop peu pour construire quoi que ce soit.

CE QUE CETTE CONTRAINTE INTERDISAIT SANS LE VOULOIR

Un nom humain porte des accents et des espaces. Le 23/08, après que Mike a
nommé le groupe de « Stéphane Plouvin », la preuve DISQUE de son geste —
`verifier_xmp_personnes.py --nom "Stéphane Plouvin"` — s'est révélée
INLANÇABLE par ce canal. Le chiffre : **168 des 352 noms de la photothèque,
6 119 photos**, hors de portée du seul instrument qui vérifie la règle 2 dans
les fichiers. Le garde-fou ne visait pas les noms ; il les a attrapés au
passage, et il rendait muet ce qui devait témoigner.

LE JETON `b64:` — UNE VALEUR, PAS UNE PORTE PLUS LARGE

    verifier_xmp_personnes.py --nom b64:U3TDqXBoYW5lIFBsb3V2aW4

Ce qui TRANSITE reste du base64url, que `ARG_OK` admettait déjà : la porte
n'est pas desserrée d'un caractère, et les trois barrières s'appliquent
inchangées, sur la forme écrite. La valeur n'est reconstituée qu'APRÈS elles,
et seulement pour aller dans la LISTE de `subprocess.run` — là où la barrière
1 garantit que nul shell ne la relira. Un jeton illisible, vide, ou porteur
d'un caractère de contrôle est un REFUS NOMMÉ : un argument à moitié décodé
ferait mesurer autre chose que ce qu'on croit. Le nom du BANC, lui, n'est
jamais décodé — la famille se juge sur ce qui est écrit.

CE QU'IL RAPPORTE

`_banc_sortie.txt` — la sortie, telle quelle, en UTF-8, tronquée à la fin si
elle dépasse (une sortie tronquée le DIT ; une sortie silencieusement coupée
serait pire qu'absente). `_etat_banc.json` — ce qu'il a TENTÉ : l'ordre, le
code de retour, la durée, la troncature. Comme pour git, le rapport n'est pas
la preuve : la preuve, c'est la sortie.

L'ENCODAGE, PARCE QU'IL A DÉJÀ MORDU

Le sous-processus tourne avec `PYTHONIOENCODING=utf-8` et sa sortie est
décodée en UTF-8 avec `errors='replace'`. Un banc dont la sortie part dans un
TUYAU n'écrit pas dans une console : sans cela, un simple « é » tue le script
par `UnicodeEncodeError` (constaté le 15/08 sur `import server`) et on croit
que le banc a planté alors qu'il a seulement voulu s'afficher.

USAGE
    python banc_agent.py --executer   (boucle du superviseur : agit si demandé)
    python banc_agent.py --etat       (affiche le dernier rapport)
"""

import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import canal

__all__ = ['FICHIER_COMMANDE', 'FICHIER_ETAT', 'FICHIER_SORTIE', 'FICHIER_VU',
           'RIEN', 'PING', 'DEFAUT', 'PERIODE_S', 'FAMILLES', 'TIMEOUT_S',
           'SORTIE_MAX', 'JETON_B64', 'lire_commande', 'ecrire_commande',
           'decouper', 'dejeton',
           'python_du_projet',
           'motif_refus', 'ecrire_etat']

FICHIER_COMMANDE = '_commande_banc.txt'
FICHIER_ETAT = '_etat_banc.json'
FICHIER_SORTIE = '_banc_sortie.txt'
FICHIER_VU = '_agent_banc_vu.txt'

RIEN, PING = 'rien', 'ping'
DEFAUT = RIEN

# Trois secondes, comme l'agent git : un `stat` local, jamais le NAS.
PERIODE_S = 3.0

# Les familles qui MESURENT. Une famille absente d'ici n'est pas « interdite
# par oubli » : elle est hors du mandat de cet agent.
FAMILLES = ('mesure_', 'verifier_', 'diagnostic_', 'comptes_', 'inventaire_',
            'test_', 'eval_')

# Ce qu'un argument peut contenir. Assez pour `--base copie.db --seuil 0.5`,
# trop peu pour bâtir un chemin exotique ou glisser une quote.
ARG_OK = re.compile(r'^[A-Za-z0-9_.:/=-]+$')

# Le préfixe qui annonce une valeur encodée, et l'alphabet de son corps.
# Les deux tiennent DÉJÀ dans `ARG_OK` : le jeton n'élargit rien.
JETON_B64 = 'b64:'
CORPS_B64 = re.compile(r'^[A-Za-z0-9_-]+=*$')

# Dix minutes : `mesure_faits_vue` prend 3 s, `eval_tagging` peut prendre des
# heures — celui-là n'a rien à faire ici, et le plafond le dit sans discuter.
TIMEOUT_S = 600
TIMEOUT_MAX = 1800

# 400 000 caractères : quelques centaines de pages. Au-delà, un banc ne
# rapporte plus, il déverse.
SORTIE_MAX = 400_000


# ─────────────────────────────── le canal ───────────────────────────────

def lire_commande(chemin):
    """Ordre courant, tel qu'écrit (casse conservée — un chemin en dépend).

    `rien` quand le fichier est absent, vide ou illisible : le doute penche du
    côté qui NE LANCE RIEN."""
    return canal.lire_ligne(chemin, DEFAUT)


def ecrire_commande(chemin, ordre):
    """Écrit l'ordre, atomiquement, en CRLF explicite (voir `canal`)."""
    return canal.ecrire_ligne(chemin, ordre)


# ────────────────────────── lectures pures (testables) ──────────────────────

def decouper(ordre):
    """`'mesure_x.py --base copie.db'` → `['mesure_x.py', '--base', 'copie.db']`.

    Découpe sur les espaces, rien d'autre : il n'y a ni quote, ni échappement,
    ni variable. Ce qui n'est pas un argument simple sera refusé par
    `motif_refus`, pas réinterprété."""
    return [m for m in str(ordre or '').split() if m]


def dejeton(arg):
    """`'b64:QsOpYQ'` → `'Béa'` ; tout ce qui ne porte pas le jeton est rendu
    TEL QUEL — un `--base` décodé en douce serait un défaut muet.

    Le jeton n'est pas un échappement : il ne rend pas au canal ce qu'`ARG_OK`
    lui refuse, il transporte une valeur sous une forme qu'`ARG_OK` accepte
    déjà. Le décodage vient donc APRÈS les contrôles, et sa sortie ne va que
    dans la liste de `subprocess.run`.

    Lève `ValueError` sur un jeton vide, hors alphabet, qui n'est pas de
    l'UTF-8, ou qui porte un caractère de contrôle — `motif_refus` en fait un
    refus nommé plutôt qu'un argument à moitié né. Aucun nom humain ne porte
    de tabulation ; un canal qui l'accepterait accepterait qu'on lui glisse
    une ligne dans un argument."""
    if not arg.startswith(JETON_B64):
        return arg
    corps = arg[len(JETON_B64):]
    if not corps:
        raise ValueError('jeton vide')
    if not CORPS_B64.match(corps):
        raise ValueError('hors alphabet base64url')
    # Le bourrage est facultatif : sans lui le jeton est plus court, et il
    # traverse le canal aussi bien.
    brut = base64.urlsafe_b64decode(corps + '=' * (-len(corps) % 4))
    valeur = brut.decode('utf-8')          # lève sur ce qui n'est pas un texte
    if not valeur:
        raise ValueError('valeur vide')
    if any(ord(c) < 32 for c in valeur):
        raise ValueError('caractere de controle dans la valeur')
    return valeur


def motif_refus(ordre, projet):
    """Motif de refus de l'ordre, ou None s'il est lançable.

    L'ordre des contrôles suit leur coût : la forme d'abord, le disque ensuite.
    Aucun n'est contournable — cet agent n'a pas de `force=`, parce qu'il n'a
    aucun contrôle NÉGOCIABLE : il n'y a pas de bonne raison de lancer un
    script qui écrit."""
    morceaux = decouper(ordre)
    if not morceaux:
        return "ordre vide"
    nom, args = morceaux[0], morceaux[1:]

    if nom in ('/', '\\') or '/' in nom or '\\' in nom or nom.startswith('.'):
        return (f"nom de banc avec un chemin : {nom!r} — attendu un simple nom "
                "de fichier, à la racine du projet")
    if not nom.endswith('.py'):
        return f"pas un script Python : {nom!r}"
    if not nom.lower().startswith(FAMILLES):
        return (f"famille non autorisée : {nom!r} — cet agent ne lance que "
                f"{', '.join(FAMILLES)} (les scripts qui MESURENT). "
                "Ce qui écrit reste un geste de Mike.")
    for a in args:
        if not ARG_OK.match(a):
            return (f"argument refusé : {a!r} — seuls "
                    "[A-Za-z0-9_.:/=-] sont admis. Un accent ou un espace "
                    f"passe par le jeton {JETON_B64} suivi du base64url du "
                    "texte UTF-8.")
        if a.startswith(JETON_B64):
            try:
                dejeton(a)
            except ValueError as e:
                return (f"jeton {JETON_B64} illisible : {a!r} — {e}. Attendu "
                        f"{JETON_B64} suivi du base64url d'un texte UTF-8.")
    if not (Path(projet) / nom).is_file():
        return f"banc introuvable dans le projet : {nom!r}"
    return None


def ecrire_etat(chemin, rapport, garder=12):
    """`_etat_banc.json` : le dernier rapport, plus un historique court.

    Même forme que `_etat_git.json`, et pour la même raison : un rapport qui
    écrase le précédent efface la trace d'un refus qu'on n'a pas vu passer."""
    chemin = Path(chemin)
    try:
        d = json.loads(chemin.read_text(encoding='utf-8'))
        hist = d.get('historique') or []
        if d.get('dernier'):
            hist.insert(0, d['dernier'])
    except (OSError, ValueError, AttributeError):
        hist = []
    d = {'dernier': rapport, 'historique': hist[:garder]}
    tmp = chemin.with_suffix(chemin.suffix + '.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, chemin)
    return d


# ──────────────────────────────── l'action ────────────────────────────────

def python_du_projet(projet):
    """L'interpréteur du `.venv` du projet, ou celui qui nous exécute.

    Le chemin dépend du SYSTÈME, pas seulement de l'existence du fichier :
    `.venv/Scripts/python.exe` EXISTE aussi quand on regarde le dossier depuis
    la VM Linux (il est monté), mais il ne s'y exécute pas — « Exec format
    error ». Tester `is_file()` seul faisait donc échouer l'agent là où il
    aurait dû se rabattre. On choisit par plateforme, puis on vérifie."""
    projet = Path(projet)
    candidat = (projet / '.venv' / 'Scripts' / 'python.exe' if os.name == 'nt'
                else projet / '.venv' / 'bin' / 'python')
    if candidat.is_file() and os.access(str(candidat), os.X_OK):
        return candidat
    return Path(sys.executable)



def lancer(projet, ordre, timeout=TIMEOUT_S):
    """Lance le banc s'il passe la porte. Rend le dict de rapport.

    La sortie standard et la sortie d'erreur sont FUSIONNÉES : un banc qui
    meurt écrit sur stderr, et séparer les deux flux revient à cacher la cause
    dans un fichier qu'on ne lit pas."""
    projet = Path(projet)
    rap = {'quand': time.time(), 'ordre': str(ordre), 'ok': False,
           'refus': None, 'code': None, 'duree_s': 0.0, 'tronquee': False,
           'octets': 0}
    refus = motif_refus(ordre, projet)
    if refus:
        rap['refus'] = refus
        return rap

    bruts = decouper(ordre)
    # Les jetons deviennent des VALEURS ici, et pas avant : `motif_refus` a
    # jugé la forme qui a transité, pas ce qu'elle portait. Le nom du banc
    # (indice 0) n'est jamais décodé — sa famille se juge sur l'écrit.
    morceaux = bruts[:1] + [dejeton(a) for a in bruts[1:]]
    py = python_du_projet(projet)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    t0 = time.time()
    try:
        p = subprocess.run([str(py)] + morceaux, cwd=str(projet),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=min(int(timeout), TIMEOUT_MAX), env=env)
        sortie = (p.stdout or b'').decode('utf-8', errors='replace')
        rap['code'] = p.returncode
    except subprocess.TimeoutExpired as e:
        sortie = (e.stdout or b'').decode('utf-8', errors='replace')
        rap['refus'] = (f"banc interrompu après {timeout} s — il n'a pas fini. "
                        "Sa sortie partielle est dans " + FICHIER_SORTIE)
        rap['code'] = -1
    except OSError as e:
        sortie = ''
        rap['refus'] = f"lancement impossible : {e}"
        rap['code'] = -1
    rap['duree_s'] = round(time.time() - t0, 1)

    if len(sortie) > SORTIE_MAX:
        sortie = (sortie[:SORTIE_MAX] +
                  f"\n\n[... sortie tronquée à {SORTIE_MAX} caractères par "
                  "banc_agent : un banc qui déverse ne rapporte plus ...]\n")
        rap['tronquee'] = True
    rap['octets'] = len(sortie)
    # Un en-tête qui n'affiche que l'ordre brut laisserait lire
    # `b64:U3TDqXBo…` là où il faut lire un nom.
    decode = ('# décodé : ' + ' '.join(morceaux) + '\n'
              if morceaux != bruts else '')
    entete = (f"# {rap['ordre']}\n{decode}# code {rap['code']} — {rap['duree_s']} s"
              f"{' — TRONQUÉE' if rap['tronquee'] else ''}\n"
              + "-" * 74 + "\n")
    try:
        (projet / FICHIER_SORTIE).write_text(entete + sortie, encoding='utf-8')
    except OSError as e:                                      # noqa: BLE001
        rap['refus'] = rap['refus'] or f"sortie non écrite : {e}"
    rap['ok'] = rap['refus'] is None and rap['code'] == 0
    return rap


def resume(rap):
    """Une ligne pour la fenêtre du superviseur."""
    q = time.strftime('%H:%M:%S', time.localtime(rap.get('quand') or 0))
    if rap.get('refus'):
        return f"[{q}] REFUS {rap['refus']}"
    return (f"[{q}] {'OK' if rap.get('ok') else 'ECHEC'} {rap.get('ordre')} "
            f"— code {rap.get('code')}, {rap.get('duree_s')} s, "
            f"{rap.get('octets')} car. dans {FICHIER_SORTIE}")


def un_tour(projet):
    """Un passage : lit l'ordre, agit s'il y en a un, consomme, rapporte."""
    projet = Path(projet)
    fc = projet / FICHIER_COMMANDE
    ordre = lire_commande(fc)
    if ordre.lower() == RIEN:
        return None
    if ordre.lower() == PING:
        rap = {'quand': time.time(), 'ordre': PING, 'ok': True, 'refus': None,
               'code': 0, 'duree_s': 0.0, 'tronquee': False, 'octets': 0}
    else:
        rap = lancer(projet, ordre)
    # L'ordre est CONSOMMÉ dans tous les cas — y compris sur un refus. Sinon
    # l'agent rejouerait le même refus toutes les trois secondes, et le
    # rapport utile serait noyé dans sa propre répétition.
    try:
        ecrire_commande(fc, RIEN)
    except (OSError, ValueError):
        pass
    ecrire_etat(projet / FICHIER_ETAT, rap)
    return rap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    projet = Path(__file__).resolve().parent
    if '--etat' in argv:
        try:
            d = json.loads((projet / FICHIER_ETAT).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            print("Aucun rapport : l'agent n'a encore rien lancé.")
            return 0
        print(resume(d.get('dernier') or {}))
        for r in (d.get('historique') or [])[:6]:
            print("   " + resume(r))
        return 0
    if '--executer' in argv:
        rap = un_tour(projet)
        if rap:
            print(resume(rap))
        return 0
    print(__doc__.strip().splitlines()[1])
    print("  --executer | --etat")
    return 0


if __name__ == '__main__':
    sys.exit(main())
