#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pilotage — arrêter et redémarrer le serveur par un FICHIER
──────────────────────────────────────────────────────────────────────────────

POURQUOI

Sans hot-reload, toute modification de `server.py` exige un redémarrage. Tant
que ce geste appartenait à la seule machine de Mike, la sandbox livrait à
l'aveugle : elle ne pouvait pas observer ce qu'elle venait d'écrire, et
« observer sans redémarrer, c'est observer l'ancien code ». Ce module ouvre le
seul canal que la sandbox possède réellement.

LE CANAL, ET SES DEUX CONTRAINTES

La sandbox ne peut pas lancer un processus Windows, et elle ne peut pas
SUPPRIMER un fichier du dossier monté — elle ne sait qu'en ÉCRIRE. Le protocole
est donc bâti là-dessus : un fichier unique, jamais effacé, dont on réécrit le
CONTENU.

    _commande_serveur.txt   →   marche | redemarrer | arret

  · `marche`      : le serveur tourne. C'est l'état normal, et ce que le
                    serveur réécrit lui-même à chaque démarrage.
  · `redemarrer`  : le serveur sort avec le code 42 ; le superviseur relance.
  · `arret`       : le serveur sort ; le superviseur ATTEND, sans relancer.

`arret` ne coupe donc pas le superviseur — sinon la sandbox s'enfermerait
dehors : elle ne peut pas démarrer un processus, un arrêt sans retour serait un
piège, en particulier si Mike est absent. Repasser à `marche` suffit à relancer.

CE QUE CE MODULE N'EST PAS

Il ne tue rien, n'ouvre aucun port, n'exécute aucune commande : il lit et écrit
un mot dans un fichier. La décision de sortir appartient au serveur (une boucle
de veille), le redémarrage au superviseur (`superviseur.bat`). Trois pièces
séparées, chacune vérifiable seule.
"""

import os
from pathlib import Path

__all__ = ['FICHIER', 'COMMANDES', 'DEFAUT', 'CODE_REDEMARRAGE', 'PERIODE_S',
           'lire', 'ecrire', 'doit_sortir']

FICHIER = '_commande_serveur.txt'

MARCHE, REDEMARRER, ARRET = 'marche', 'redemarrer', 'arret'
COMMANDES = (MARCHE, REDEMARRER, ARRET)
DEFAUT = MARCHE

# Code de sortie que le superviseur interprète comme « relance-moi ». Distinct
# de 0 et de 1 pour qu'un ARRÊT VOULU ne ressemble pas à un plantage : le
# superviseur compte les sorties anormales et cesse de boucler après cinq.
CODE_REDEMARRAGE = 42

# Le serveur relit le fichier toutes les PERIODE_S secondes. Deux secondes :
# assez court pour que la sandbox n'attende pas, assez long pour que le coût
# soit un `stat` local toutes les deux secondes — jamais le NAS.
PERIODE_S = 2.0


def lire(chemin):
    """Commande courante, normalisée. Renvoie toujours l'une de `COMMANDES`.

    TOLÉRANT PAR CONCEPTION : le fichier est écrit tantôt par Windows
    (`echo marche` → CRLF), tantôt depuis un shell POSIX (`echo redemarrer` →
    LF), parfois avec un BOM. Un fichier absent, vide, illisible ou contenant
    n'importe quoi rend `marche` — l'état qui ne fait rien.

    C'est délibéré : un fichier de pilotage mal formé ne doit jamais pouvoir
    ARRÊTER le serveur. Le doute penche du côté qui laisse le service debout."""
    try:
        brut = Path(chemin).read_text(encoding='utf-8-sig', errors='replace')
    except (OSError, ValueError):
        return DEFAUT
    mot = brut.strip().splitlines()[0].strip().lower() if brut.strip() else ''
    return mot if mot in COMMANDES else DEFAUT


def ecrire(chemin, commande):
    """Écrit la commande, atomiquement. Refuse un mot inconnu.

    Atomique (`.tmp` puis `os.replace`) comme toute écriture d'index du projet :
    le serveur lit ce fichier toutes les deux secondes, et un fichier
    tronqué lu à mi-écriture rendrait `marche` par tolérance — donc un
    redémarrage silencieusement perdu. Mieux vaut qu'il n'existe aucun instant
    où le fichier soit à moitié écrit.

    **CRLF explicite, en octets.** L'autre lecteur de ce fichier est
    `cmd.exe` (`set /p` dans `superviseur.bat`), et il attend des fins de ligne
    Windows. Or ce module est appelé depuis les deux mondes : le serveur sous
    Windows, la sandbox depuis une VM Linux — où `write_text` laisserait un LF
    nu. On ne laisse donc pas la plateforme décider : mêmes octets partout,
    même raison que l'ASCII pur des `.bat`."""
    commande = str(commande).strip().lower()
    if commande not in COMMANDES:
        raise ValueError(f"commande inconnue : {commande!r} "
                         f"(attendu : {', '.join(COMMANDES)})")
    chemin = Path(chemin)
    tmp = chemin.with_suffix(chemin.suffix + '.tmp')
    tmp.write_bytes(commande.encode('ascii') + b'\r\n')
    os.replace(tmp, chemin)
    return commande


def doit_sortir(commande):
    """Le processus doit-il se terminer ? `redemarrer` et `arret` sortent tous
    les deux — c'est le SUPERVISEUR qui décide ensuite de relancer ou d'attendre.

    Le serveur n'a pas à connaître cette différence : il saurait s'arrêter mais
    pas se rallumer. Un processus qui déciderait de sa propre résurrection est
    précisément le nœud qu'on évite ici."""
    return commande in (REDEMARRER, ARRET)
