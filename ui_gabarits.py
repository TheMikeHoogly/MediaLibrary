#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_gabarits — où vivent les pages, pour ceux qui les relisent
──────────────────────────────────────────────────────────────────────────────

Les gabarits HTML ont quitté `server.py` pour `ui/pages/` (point 7). Plusieurs
bancs et tests les relisaient DANS le source du serveur, par l'AST
(`test_gallery_placeholders`, `test_tranche_jugements`, `test_residu_jugements`) :
c'est ainsi qu'ils vérifient qu'un marqueur `__ROWS__` existe encore, ou qu'une
page dit « introuvable » plutôt que de rester vide.

Ce module leur donne UNE façon de trouver un gabarit, pour qu'il n'y en ait pas
trois. Il est PUR : aucune I/O hors lecture, aucun import lourd, aucun accès à
la base. La correspondance ci-dessous est la seule chose à tenir à jour quand
une page sort du monolithe.

Il ne connaît pas de repli sur le source de `server.py` : un gabarit qui n'est
plus là DOIT faire échouer bruyamment. Un test qui se rabat en silence sur une
copie périmée ne mesure plus rien — il rassure.
"""

from pathlib import Path

RACINE = Path(__file__).resolve().parent
PAGES_DIR = RACINE / 'ui' / 'pages'

# Ancien nom de constante -> nom de fichier. L'ancien nom reste la clé parce
# que c'est sous ce nom que les tests, les commentaires et la mémoire du projet
# désignent chaque page.
GABARITS = {
    'HTML_PAGE': 'upload',
    'GALLERY_PAGE': 'gallery',
    'BROWSE_PAGE': 'browse',
    'REGLAGES_PAGE': 'reglages',
    'MAP_PAGE': 'map',
    'PETS_PAGE': 'pets',
    'FACES_PAGE': 'faces',
    'TRANCHE_PAGE': 'tranche',
    'RESIDU_PAGE': 'residu',
    'SUBJECTS_PAGE': 'subjects',
    'PEOPLE_PAGE': 'people',
}


def fichier(nom):
    """Chemin du gabarit, que le nom soit `GALLERY_PAGE` ou `gallery`."""
    return PAGES_DIR / f"{GABARITS.get(nom, nom)}.html"


def gabarit(nom):
    """Texte du gabarit. Lève si le fichier manque — voir l'en-tête."""
    p = fichier(nom)
    try:
        return p.read_text(encoding='utf-8')
    except OSError as e:
        raise AssertionError(
            f"gabarit introuvable : {p} ({e}). Si la page a ete renommee ou "
            "remise dans server.py, mettre a jour ui_gabarits.GABARITS — ne "
            "pas contourner ce test.") from e


def tous():
    """{ancien nom de constante: texte} pour les gabarits PRÉSENTS."""
    return {const: fichier(const).read_text(encoding='utf-8')
            for const in GABARITS if fichier(const).is_file()}
