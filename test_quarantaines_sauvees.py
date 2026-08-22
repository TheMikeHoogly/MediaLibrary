#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — les quarantaines se DÉCOUVRENT, des deux côtés, et par la MÊME règle.

Pourquoi ce fichier
───────────────────
Le 22/08, `verifier_restauration.py` annonçait « Total exposé : 0 o » alors que
deux quarantaines nées le jour même — `_corbeille_recalage` (le recalage de 33
rattachements) et `_corbeille_retraits` (le retrait de 2 couples) — n'étaient
sauvegardées nulle part. Aucun défaut de calcul : le producteur
(`server.backup_artefacts`) et l'instrument lisaient chacun une LISTE EN DUR de
trois noms, écrite quand le projet n'avait que trois corbeilles. Un geste
annoncé RÉVERSIBLE dont la réversibilité tient à un dossier qu'aucune
sauvegarde n'emporte est une promesse qu'un disque mort annule en silence.

Ce que ces tests protègent, ce n'est donc pas un comportement : c'est
l'impossibilité de refaire la même erreur. La règle doit rester une
DÉCOUVERTE (un motif), et elle doit rester la MÊME des deux côtés — un
instrument qui n'applique pas la règle du producteur mesure un cousin de la
sauvegarde (`eval/METHODE.md`, 14/08).

Les tests n'impriment rien (l'agent git capture la sortie).
"""

import ast
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SERVEUR = (RACINE / "server.py").read_text(encoding="utf-8")
# Parsé UNE fois : `ast.parse` sur 12 000 lignes coûte, et le refaire à chaque
# test répéterait les avertissements du source dans une sortie que l'agent git
# capture — un test doit être lisible pour être relu.
ARBRE_SERVEUR = ast.parse(SERVEUR)

import verifier_restauration as V


def constante_du_serveur(nom):
    """Valeur d'une constante littérale de `server.py`, sans l'importer
    (`import server` ouvre `photos.db`, dont le serveur est l'écrivain unique)."""
    for n in ast.walk(ARBRE_SERVEUR):
        if isinstance(n, ast.Assign):
            for c in n.targets:
                if isinstance(c, ast.Name) and c.id == nom:
                    return ast.literal_eval(n.value)
    raise AssertionError(f"{nom} introuvable dans server.py — si la règle des "
                         "quarantaines a bouge, ce test doit etre relu.")


class TestMemeRegleDesDeuxCotes(unittest.TestCase):

    def test_le_motif_est_identique(self):
        self.assertEqual(constante_du_serveur('QUARANTAINE_MOTIF'),
                         V.QUARANTAINE_MOTIF)

    def test_les_exclusions_sont_identiques(self):
        self.assertEqual(tuple(constante_du_serveur('QUARANTAINES_NON_SAUVEES')),
                         tuple(V.QUARANTAINES_NON_SAUVEES))

    def test_le_motif_attrape_bien_toutes_les_corbeilles(self):
        self.assertTrue(V.QUARANTAINE_MOTIF.endswith('*'),
                        "un motif sans joker redevient une liste en dur")
        self.assertTrue(V.QUARANTAINE_MOTIF.startswith('_corbeille'))

    def test_plus_aucune_liste_en_dur_cote_serveur(self):
        self.assertNotIn('DOSSIERS_A_SAUVER', SERVEUR)

    def test_le_serveur_sauve_ce_qu_il_decouvre(self):
        self.assertIn('for dossier in quarantaines():', SERVEUR)


class TestDecouverte(unittest.TestCase):
    """Sur un faux dossier : ce qui entre, ce qui reste dehors, et pourquoi."""

    def dossier(self, *noms):
        import tempfile
        d = Path(tempfile.mkdtemp())
        for n in noms:
            (d / n).mkdir()
        self.addCleanup(__import__('shutil').rmtree, d, True)
        return d

    def test_une_quarantaine_NEUVE_est_prise_sans_qu_on_la_declare(self):
        # Le cœur du correctif : le chantier suivant créera `_corbeille_xyz`
        # sans penser à cette liste, et elle doit être couverte quand même.
        d = self.dossier('_corbeille_detections', '_corbeille_xyz')
        noms = [q[0] for q in V.artefacts_quarantaines(d)]
        self.assertIn('_corbeille_xyz', noms)

    def test_l_exclusion_reste_VISIBLE_au_lieu_de_disparaitre(self):
        # Une exclusion tue ne se distingue pas d'un oubli : c'est exactement
        # ce qui a caché le trou pendant que le rapport affichait « 0 o ».
        d = self.dossier('_corbeille_session')
        q = V.artefacts_quarantaines(d)
        self.assertEqual(len(q), 1)
        nom, gravite, role, _ = q[0]
        self.assertEqual(nom, '_corbeille_session')
        self.assertNotEqual(gravite, V.IRRECUPERABLE)
        self.assertIn('volontairement', role)

    def test_ce_qui_n_est_pas_une_quarantaine_n_entre_pas(self):
        d = self.dossier('_corbeille_vecteurs', 'photo_thumbs', 'docs')
        noms = [q[0] for q in V.artefacts_quarantaines(d)]
        self.assertEqual(noms, ['_corbeille_vecteurs'])

    def test_un_fichier_nomme_comme_une_corbeille_n_est_pas_un_dossier(self):
        d = self.dossier()
        (d / '_corbeille_piege.txt').write_text('x', encoding='utf-8')
        self.assertEqual(V.artefacts_quarantaines(d), ())

    def test_l_ordre_est_stable(self):
        d = self.dossier('_corbeille_vecteurs', '_corbeille_decisions',
                         '_corbeille_recalage')
        noms = [q[0] for q in V.artefacts_quarantaines(d)]
        self.assertEqual(noms, sorted(noms))

    def test_aucune_quarantaine_ne_rend_une_liste_vide(self):
        self.assertEqual(V.artefacts_quarantaines(self.dossier()), ())


class TestInventaire(unittest.TestCase):

    def test_les_quarantaines_entrent_dans_l_inventaire(self):
        import tempfile, shutil
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / '_corbeille_neuve').mkdir()
        (d / '_corbeille_neuve' / 'undo.jsonl').write_text('{}', encoding='utf-8')
        lignes = V.inventaire(racine=d, sauvegarde=d / 'nas-absent')
        ligne = [x for x in lignes if x['quoi'] == '_corbeille_neuve']
        self.assertEqual(len(ligne), 1)
        self.assertTrue(ligne[0]['present'])
        self.assertEqual(ligne[0]['copie'], 'AUCUNE COPIE')
        self.assertEqual(ligne[0]['gravite'], V.IRRECUPERABLE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
