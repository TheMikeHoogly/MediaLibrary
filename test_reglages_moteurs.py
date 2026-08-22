#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests des correctifs d'audit I4, I5, I6 et I8 — SUR LE CODE DE PROD.

Pourquoi ce fichier
───────────────────
Les quatre défauts corrigés le 22/08 ont une chose en commun : **ils ne
cassaient rien**. Un libellé qui affirme « CPU » quand le GPU travaille, un
arbitre de VRAM que l'écran d'état ne montre pas, deux routes que plus aucune
page n'appelle, soixante lignes de code mort sous un en-tête élogieux — rien
de tout cela ne fait tomber un test, et c'est précisément pourquoi ça revient.
Ce fichier est le garde : il relit le SOURCE et refuse le retour en arrière.

Comme `test_recalage_serveur` et `test_gallery_placeholders`, il lit
`server.py` sans l'importer (`import server` ouvre `photos.db`, dont le serveur
est l'écrivain unique).

Les tests n'impriment rien (l'agent git capture la sortie).
"""

import ast
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SOURCE = (RACINE / "server.py").read_text(encoding="utf-8")
# Depuis le 22/08, les pages ne vivent plus dans le monolithe : ce qui relève
# de l'AFFICHAGE se relit dans son gabarit, pas dans `server.py`. Le test
# CHANGE de source, il ne baisse pas son exigence.
from ui_gabarits import gabarit                       # noqa: E402
REGLAGES = gabarit('REGLAGES_PAGE')
CLASSIFIER = (RACINE / "classifier.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def noeud_de(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    raise AssertionError(f"{nom} introuvable dans server.py — ce test doit "
                         "etre relu, pas contourne.")


def source_de(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return ast.get_source_segment(SOURCE, n) or ""
    raise AssertionError(f"{nom} introuvable dans server.py — ce test doit "
                         "etre relu, pas contourne.")


class TestI5MoteurDesVisages(unittest.TestCase):
    """Le moteur ne s'AFFIRME plus, il se DIT."""

    def test_la_phrase_en_dur_a_disparu(self):
        self.assertNotIn("seul Ollama utilise le GPU", SOURCE)
        self.assertNotIn("seul Ollama utilise le GPU", REGLAGES)

    def test_la_page_a_un_emplacement_qui_se_remplit(self):
        self.assertIn('id="moteurs"', REGLAGES)

    def test_le_serveur_publie_le_dernier_moteur_utilise(self):
        st = source_de('_serve_maint_status')
        self.assertIn("'moteurs'", st)
        self.assertIn("FACE_LAST_ENGINE", st)

    def test_l_etat_ne_charge_jamais_insightface_pour_le_dire(self):
        # Un écran d'état qui monte un modèle de 300 Mo pour annoncer s'il est
        # monté serait le contraire d'un instrument (invariant 3). Cherché sur
        # les APPELS de l'arbre, jamais sur le texte : interdire un MOT
        # interdirait aussi d'écrire pourquoi il ne faut pas l'appeler.
        appels = {n.func.id for n in ast.walk(noeud_de('_serve_maint_status'))
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertNotIn('get_face_app', appels)


class TestI6ArbitreVisible(unittest.TestCase):
    """Baux, refus et évictions vivaient hors de la page qui montre l'état."""

    def test_le_serveur_publie_l_arbitre_et_l_ordonnanceur(self):
        st = source_de('_serve_maint_status')
        self.assertIn("'gpu'", st)
        self.assertIn("'ordonnanceur'", st)

    def test_la_page_sait_afficher_l_absence_du_module(self):
        # Sans `ordonnanceur.py`, chaque pipeline décide seul : la carte doit
        # le DIRE. Une carte vide se lirait « aucun bail », c'est-à-dire un
        # arbitre au repos — l'inverse de la vérité.
        self.assertIn("gpuCard", REGLAGES)
        self.assertIn("Module ordonnanceur absent", REGLAGES)

    def test_la_carte_montre_refus_et_evictions(self):
        i = REGLAGES.index("function gpuCard")
        bloc = REGLAGES[i:i + 1400]
        self.assertIn("refus", bloc)
        self.assertIn("eviction", bloc)


class TestI8RoutesOrphelines(unittest.TestCase):
    """Deux routes sans aucun client, retirées — et deux voisines gardées."""

    def test_les_routes_orphelines_ont_disparu(self):
        for mort in ("'/api/pets/name'", "name_pet_cluster",
                     "'/api/hardware'", "_serve_hardware"):
            self.assertNotIn(mort, SOURCE, mort)

    def test_le_chemin_vivant_des_personnes_est_intact(self):
        # `/api/people/name` a un client (page /people, nommage d'un groupe) :
        # le supprimer « par symétrie » casserait un geste humain.
        self.assertIn("'/api/people/name'", SOURCE)
        self.assertIn("def name_cluster", SOURCE)

    def test_les_autres_routes_animaux_sont_intactes(self):
        for vivante in ("'/api/pets/find'", "'/api/pets/confirm'",
                        "'/api/assign'"):
            self.assertIn(vivante, SOURCE, vivante)

    def test_l_etat_materiel_reste_lisible_ailleurs(self):
        # `/api/hardware` partait, pas l'information : `hw_state()` continue
        # d'être publié là où une page le lit vraiment.
        self.assertIn("'hw': hw_state()", SOURCE)


class TestI4CodeMort(unittest.TestCase):
    """Le module ne documente plus une correction qu'il n'applique pas."""

    def test_les_classes_rejetees_ont_disparu(self):
        arbre = ast.parse(CLASSIFIER)
        classes = {n.name for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)}
        self.assertFalse(classes & {'Modele', 'Banque'}, classes)
        noms = {c.id for n in ast.walk(arbre) if isinstance(n, ast.Assign)
                for c in n.targets if isinstance(c, ast.Name)}
        self.assertNotIn('MARGE_NEGATIVE', noms)

    def test_l_entete_dit_le_rejet_au_lieu_de_le_taire(self):
        self.assertIn("REJETE", CLASSIFIER.upper())

    def test_ce_que_le_serveur_importe_est_toujours_la(self):
        self.assertIn("def prototypes", CLASSIFIER)
        self.assertIn("from classifier import prototypes", SOURCE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
