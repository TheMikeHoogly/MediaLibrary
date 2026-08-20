#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
canal — un fichier, deux mondes : lire et écrire un ORDRE sans se tromper d'octets
──────────────────────────────────────────────────────────────────────────────

POURQUOI CE MODULE EXISTE

La sandbox ne peut ni lancer un processus Windows, ni supprimer un fichier du
dossier monté : elle ne sait qu'ÉCRIRE. Tout ce qu'elle commande passe donc par
un fichier dont on réécrit le contenu, qu'un programme Windows relit en boucle.
Il y a désormais trois canaux de cette forme :

    _commande_serveur.txt  →  `pilotage`     (marche / redemarrer / arret)
    _commande_git.txt      →  `git_agent`    (rien / ping / commit / livrer)
    _commande_banc.txt     →  `banc_agent`   (rien / ping / <banc à lancer>)

Les MOTS diffèrent, et c'est chaque agent qui décide des siens — un canal qui
accepterait n'importe quoi ne serait plus une porte. Ce qui ne diffère pas,
c'est la manière de lire et d'écrire, et elle avait déjà été recopiée DEUX fois
à l'identique. Une troisième copie, et la règle cesse d'exister : il y a des
règles qui se ressemblent, elles finissent par diverger, et c'est toujours le
cas rare qui paie (`eval/METHODE.md`).

LES DEUX RÈGLES, ET CE QU'ELLES ONT COÛTÉ

**Lire avec tolérance.** Le fichier est écrit tantôt par Windows (CRLF), tantôt
depuis la VM Linux (LF nu), parfois avec un BOM. Absent, vide, illisible :
`defaut`. Le doute penche toujours du côté qui N'AGIT PAS — laisser le serveur
debout, ne pas toucher au dépôt, ne rien lancer.

**Écrire atomiquement, en CRLF explicite.** Atomique parce que le lecteur
relit toutes les deux ou trois secondes : un fichier surpris à mi-écriture se
lirait `defaut`, c'est-à-dire un ordre silencieusement perdu. CRLF en OCTETS
parce que l'autre lecteur est parfois `cmd.exe` (`set /p`), et parce que ce
module est appelé depuis les deux mondes — on ne laisse pas la plateforme
décider des fins de ligne, même raison que l'ASCII pur des `.bat`.

CE QU'IL NE FAIT PAS

Aucune validation de contenu : il ne sait pas ce qu'est une commande valable,
et c'est voulu. `pilotage`, `git_agent` et `banc_agent` gardent chacun leur
vocabulaire et leur porte ; ils partagent seulement les octets.
"""

import os
from pathlib import Path

__all__ = ['lire_ligne', 'ecrire_ligne']


def lire_ligne(chemin, defaut=''):
    """Première ligne utile du fichier, espaces retirés — ou `defaut`.

    Ne met RIEN en minuscules : un canal peut transporter un chemin
    (`--base copie.db`), et une casse écrasée casserait l'argument. C'est
    l'appelant qui normalise selon son vocabulaire."""
    try:
        brut = Path(chemin).read_text(encoding='utf-8-sig', errors='replace')
    except (OSError, ValueError):
        return defaut
    if not brut.strip():
        return defaut
    return brut.strip().splitlines()[0].strip() or defaut


def ecrire_ligne(chemin, ligne):
    """Écrit une ligne, atomiquement, terminée par un CRLF explicite.

    ASCII imposé : ces fichiers sont relus par `cmd.exe`, qui compte en
    octets. Un accent y désaligne un `set /p` aussi sûrement que dans un
    `.bat`. Un ordre ne contient jamais d'accent ; s'il en contient, c'est
    l'ordre qui est faux."""
    ligne = str(ligne).strip()
    try:
        octets = ligne.encode('ascii')
    except UnicodeEncodeError:
        raise ValueError(
            f"ordre non ASCII : {ligne!r} — le canal est relu par cmd.exe, "
            "qui compte en octets (même règle que les .bat)")
    chemin = Path(chemin)
    tmp = chemin.with_suffix(chemin.suffix + '.tmp')
    tmp.write_bytes(octets + b'\r\n')
    os.replace(tmp, chemin)
    return ligne
