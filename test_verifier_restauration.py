#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_restauration` — les trois pannes du 22/08, sur pièces.

Pourquoi ce fichier
───────────────────
Le premier essai réel de la répétition (22/08, 20:21) n'a rien prouvé, et
l'instrument n'a pas dit qu'il ne prouvait rien. Trois défauts, tous du même
genre : **des refus et des zéros qui se lisaient comme des succès.**

1. **Le garde-fou visait le NOM du fichier.** « Ne jamais ouvrir `photos.db` »
   protège la base VIVANTE, dont le serveur est l'écrivain unique. Mais dans un
   dossier restauré, la base s'appelle forcément `photos.db` — le refus la
   frappait donc elle aussi, et par `SystemExit`, ce qui TUAIT le programme.
   La comparaison nom par nom, seul juge du chantier 12, n'avait jamais pu
   tourner une seule fois depuis que l'instrument existe.
2. **« Total exposé : 0 o » sur un dossier ENTIÈREMENT VIDE.** Le compte porte
   sur ce qui est présent SANS copie : quand rien n'est présent, il vaut zéro.
   Une restauration ratée se lisait comme une réussite.
3. **Aucun verdict.** Le rapport listait des chiffres justes sans jamais dire
   si la répétition avait réussi.

Ces tests ne protègent pas un comportement : ils protègent contre le retour de
trois silences. Aucun n'ouvre de vraie base — chacun fabrique la sienne.
"""

import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import verifier_restauration as V


def fabriquer_base(chemin, personnes):
    """Une base minuscule au schéma du projet : `people` keyée par nom."""
    cx = sqlite3.connect(str(chemin))
    for table in V.TABLES:
        cx.execute(f'CREATE TABLE IF NOT EXISTS "{table}" (k TEXT PRIMARY KEY, v TEXT)')
    for nom, d in personnes.items():
        cx.execute('INSERT INTO people (k, v) VALUES (?, ?)',
                   (nom.lower(), json.dumps({'name': nom, **d})))
    cx.commit()
    cx.close()


class TestGardeFou(unittest.TestCase):
    """Il doit viser LA base vivante — pas tout fichier qui en porte le nom."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_un_photos_db_AILLEURS_est_lisible(self):
        # Le cas exact du 22/08 : la base restaurée s'appelle `photos.db`.
        ailleurs = self.d / 'photos.db'
        fabriquer_base(ailleurs, {'Flo': {'faces': [['a', 0]]}})
        lu, err = V.decisions_de_la_base(ailleurs)
        self.assertIsNone(err, err)
        self.assertEqual(lu['par_nom']['Flo']['rattachements'], 1)

    def test_la_base_vivante_du_projet_reste_refusee(self):
        self.assertTrue(V.est_la_base_vivante(V.RACINE / 'photos.db'))
        _, err = V.decisions_de_la_base(V.RACINE / 'photos.db')
        self.assertIsNotNone(err)
        self.assertIn('VIVANTE', err)

    def test_le_refus_NE_TUE_PLUS_le_programme(self):
        # `SystemExit` emportait le rapport entier, y compris le `--json`.
        try:
            r, err = V.decisions_de_la_base(V.RACINE / 'photos.db')
        except SystemExit:                       # pragma: no cover
            self.fail("le refus leve encore SystemExit")
        self.assertIsNone(r)

    def test_une_base_absente_se_dit_sans_confusion(self):
        _, err = V.decisions_de_la_base(self.d / 'nulle-part.db')
        self.assertIn('absente', err)


class TestInventaireDuCoteRESTAURE(unittest.TestCase):
    """Un dossier vide ne dit pas « rien ne manque » : il ne dit RIEN."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def rapport(self, restaure=True):
        return V.afficher_inventaire(V.inventaire(self.d, None), self.d,
                                     None, restaure=restaure)

    def test_dossier_vide_le_DIT_au_lieu_d_annoncer_zero(self):
        txt = self.rapport()
        self.assertIn("RIEN N'A ÉTÉ RESTAURÉ", txt)
        self.assertNotIn('Total exposé', txt)

    def test_un_artefact_irrecuperable_manquant_est_nomme(self):
        (self.d / 'lieux.txt').write_text('x', encoding='utf-8')
        txt = self.rapport()
        self.assertIn('MANQUENT', txt)
        self.assertIn('photos.db', txt)
        self.assertIn('Revenus : 1 /', txt)

    def test_le_cote_VIVANT_garde_sa_lecture_d_origine(self):
        # L'inversion ne vaut que pour le dossier restauré : sur le PC, la
        # question reste « qu'est-ce qui n'a pas de copie ? ».
        txt = self.rapport(restaure=False)
        self.assertIn('Total exposé', txt)
        self.assertIn("DISQUE MORT", txt)


class TestVerdict(unittest.TestCase):
    """Le rapport doit conclure — et ne conclure QUE si tout concorde."""

    def base(self, r):
        r.setdefault('tables', {'vivant': {t: 1 for t in V.TABLES},
                                'restaure': {t: 1 for t in V.TABLES}})
        r.setdefault('integrite_restauree', 'ok')
        r.setdefault('noms_vivant', 3)
        r.setdefault('noms_restaure', 3)
        r.setdefault('ecarts', [])
        return r

    def test_tout_concorde_le_dit(self):
        self.assertIn('RÉPÉTITION RÉUSSIE',
                      V.afficher_comparaison(self.base({})))

    def test_un_ecart_de_decision_interdit_le_verdict(self):
        r = self.base({'ecarts': [{'nom': 'Flo',
                                   'vivant': {'rattachements': 2},
                                   'restaure': {'rattachements': 1}}]})
        txt = V.afficher_comparaison(r)
        self.assertNotIn('RÉUSSIE', txt)
        self.assertIn('Flo', txt)

    def test_une_base_non_integre_interdit_le_verdict(self):
        txt = V.afficher_comparaison(self.base({'integrite_restauree': 'corrompue'}))
        self.assertNotIn('RÉPÉTITION RÉUSSIE', txt)
        self.assertIn('⚠', txt)

    def test_des_tables_qui_different_interdisent_le_verdict(self):
        r = self.base({})
        r['tables']['restaure']['tags'] = 0
        self.assertNotIn('RÉPÉTITION RÉUSSIE', V.afficher_comparaison(r))

    def test_deux_bases_VIDES_ne_sont_pas_une_reussite(self):
        # Zéro nom des deux côtés : aucun écart, et pourtant rien n'est prouvé.
        r = self.base({'noms_vivant': 0, 'noms_restaure': 0})
        self.assertNotIn('RÉPÉTITION RÉUSSIE', V.afficher_comparaison(r))


class TestComparaisonBoutABout(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_une_decision_perdue_est_nommee(self):
        a = self.d / 'copie.db'
        b = self.d / 'restaure' / 'photos.db'
        b.parent.mkdir()
        fabriquer_base(a, {'Flo': {'faces': [['x', 0], ['y', 1]], 'exclude': ['z']},
                           'Mike': {'faces': [['w', 0]]}})
        fabriquer_base(b, {'Flo': {'faces': [['x', 0]], 'exclude': ['z']},
                           'Mike': {'faces': [['w', 0]]}})
        r, err = V.comparer(a, b)
        self.assertIsNone(err, err)
        self.assertEqual([e['nom'] for e in r['ecarts']], ['Flo'])
        self.assertEqual(r['ecarts'][0]['vivant']['rattachements'], 2)
        self.assertEqual(r['ecarts'][0]['restaure']['rattachements'], 1)

    def test_deux_bases_identiques_ne_rendent_aucun_ecart(self):
        a = self.d / 'copie.db'
        b = self.d / 'restaure' / 'photos.db'
        b.parent.mkdir()
        for chemin in (a, b):
            fabriquer_base(chemin, {'Flo': {'faces': [['x', 0]], 'confirmed': ['q']}})
        r, err = V.comparer(a, b)
        self.assertIsNone(err, err)
        self.assertEqual(r['ecarts'], [])
        self.assertIn('RÉPÉTITION RÉUSSIE', V.afficher_comparaison(r))


if __name__ == '__main__':
    unittest.main(verbosity=2)
