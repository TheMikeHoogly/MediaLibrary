#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_takeout_ouvert.py` — sans Takeout, sans reseau.

Ce que ces tests tiennent
-------------------------
1. **Le TRONQUE est la panne qui se lit comme un succes.** Bon nom, bon
   endroit, mauvaise taille. Il doit sortir rouge et NOMME.
2. **Un lot jamais ouvert ne laisse aucune trace visible dans l'arbre.** Ce
   sont les photos ABSENTES chez Google qu'on cherchera ensuite, et on
   accusera Google.
3. **Ce que le banc ne SAIT pas, il le DIT.** Ces noms de lots n'annoncent
   aucun total : un lot manquant a la FIN est invisible. Le rapport le dit au
   lieu de rendre vert en silence.
4. **Un controle interrompu ne prouve rien sur le reste.**

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dezipper_takeout as D  # noqa: E402
import verifier_takeout_ouvert as V  # noqa: E402


def source_ouverte(prefixe="test_vto_", ouvrir=True):
    d = Path(tempfile.mkdtemp(prefix=prefixe))
    with zipfile.ZipFile(d / "takeout-20260825T055303Z-1-001.zip", 'w') as z:
        z.writestr("Takeout/Google Photos/a.jpg", b"a" * 10)
        z.writestr("Takeout/Google Photos/b.jpg", b"b" * 20)
    with zipfile.ZipFile(d / "takeout-20260825T055303Z-1-002.zip", 'w') as z:
        z.writestr("Takeout/Google Photos/c.jpg", b"c" * 30)
    if ouvrir:
        D.extraire(D.lister_zips(d), d / "extrait", appliquer=True,
                   ecrire=lambda *x: None)
    return d


def lancer(d):
    lignes = []
    code = V.main(['--source', str(d)])
    return code, lignes


class LeVerdict(unittest.TestCase):

    def test_un_export_entierement_ouvert_rend_zero(self):
        d = source_ouverte()
        self.assertEqual(V.main(['--source', str(d)]), 0)

    def test_un_fichier_TRONQUE_rend_un(self):
        d = source_ouverte()
        (d / "extrait/Takeout/Google Photos/b.jpg").write_bytes(b"b" * 7)
        self.assertEqual(V.main(['--source', str(d)]), 1)

    def test_un_LOT_jamais_ouvert_rend_un(self):
        d = source_ouverte()
        (d / "extrait/Takeout/Google Photos/c.jpg").unlink()
        self.assertEqual(V.main(['--source', str(d)]), 1)

    def test_un_dossier_jamais_extrait_rend_un(self):
        d = source_ouverte(ouvrir=False)
        self.assertEqual(V.main(['--source', str(d)]), 1)

    def test_sans_aucun_lot_il_ne_rend_PAS_vert(self):
        d = Path(tempfile.mkdtemp(prefix="test_vto_vide_"))
        self.assertEqual(V.main(['--source', str(d)]), 1)


class LeRapportDitSaPortee(unittest.TestCase):

    def _dit(self, **kw):
        lignes = []
        # Une cible qui EXISTE : le rapport refuse a juste titre de juger un
        # dossier jamais extrait, et ce n'est pas ce qu'on mesure ici.
        base = dict(source='S',
                    cible=Path(tempfile.mkdtemp(prefix='test_vto_cible_')),
                    zips=[Path('t-1.zip')],
                    inv={'octets_zip': 0, 'octets_distincts': 0,
                         'fichiers_distincts': 1, 'erreurs': []},
                    manquants=[], total=None,
                    compte={e: 0 for e in D.ETATS},
                    griefs={'absent': [], 'tronque': [], 'refuse': []},
                    complet=True)
        base.update(kw)
        ok = V.rapport(ecrire=lignes.append, **base)
        return ok, lignes

    def test_sans_total_annonce_la_LIMITE_est_dite(self):
        ok, lignes = self._dit()
        self.assertTrue(ok)
        self.assertTrue(any('PORTEE' in l for l in lignes))
        self.assertTrue(any('invisible' in l for l in lignes))

    def test_avec_un_total_annonce_la_limite_ne_s_affiche_pas(self):
        _ok, lignes = self._dit(zips=[Path('t-1-of-1.zip')], total=1)
        self.assertFalse(any('PORTEE' in l for l in lignes))

    def test_le_tronque_est_nomme_pas_seulement_compte(self):
        compte = {e: 0 for e in D.ETATS}
        compte['tronque'] = 1
        ok, lignes = self._dit(compte=compte,
                               griefs={'absent': [], 'refuse': [],
                                       'tronque': ['Takeout/b.jpg']})
        self.assertFalse(ok)
        self.assertTrue(any('Takeout/b.jpg' in l for l in lignes))

    def test_ce_qui_n_est_pas_liste_est_COMPTE(self):
        compte = {e: 0 for e in D.ETATS}
        compte['absent'] = 900
        ok, lignes = self._dit(
            compte=compte,
            griefs={'absent': ['x%d' % i for i in range(V.LISTE_MAX)],
                    'tronque': [], 'refuse': []})
        self.assertFalse(ok)
        self.assertTrue(any('non listes mais COMPTES' in l for l in lignes))

    def test_un_controle_INTERROMPU_ne_prouve_rien(self):
        ok, lignes = self._dit(complet=False)
        self.assertFalse(ok)
        self.assertTrue(any('INTERROMPU' in l for l in lignes))

    def test_un_lot_illisible_rend_rouge(self):
        ok, _l = self._dit(inv={'octets_zip': 0, 'octets_distincts': 0,
                                'fichiers_distincts': 1,
                                'erreurs': [{'zip': 't-1.zip',
                                             'cause': 'not a zip'}]})
        self.assertFalse(ok)

    def test_un_trou_dans_la_numerotation_rend_rouge(self):
        ok, lignes = self._dit(manquants=[2])
        self.assertFalse(ok)
        self.assertTrue(any('MANQUANT' in l for l in lignes))


if __name__ == '__main__':
    unittest.main(verbosity=0)
