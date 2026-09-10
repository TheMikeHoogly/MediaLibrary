#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bancs de `appliquer_purge_vignettes.py` (O15).

Cet outil efface pour de bon — la reversibilite est la REGENERATION, pas une
corbeille. Ce qui doit donc etre tenu par des bancs, ce n'est pas « efface-t-il
bien », c'est **quand refuse-t-il**. Les deux verrous :

  1. le TAUX DE RECONNAISSANCE — si les formules de nommage divergent de
     `server.py`, tout le cache parait orphelin ; le refus vaut mieux que le
     geste ;
  2. l'AGE PLANCHER — une formule fausse se trompe d'abord sur les vignettes
     qu'on vient de creer, celles qui servent maintenant.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import appliquer_purge_vignettes as P                             # noqa: E402


def _fichier(d, nom, octets=10, jours=0):
    p = Path(d) / (nom + '.jpg')
    p.write_bytes(b'x' * octets)
    t = time.time() - jours * 86400
    os.utime(p, (t, t))
    return p


class DepotFactice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = Path(self.tmp.name)
        for d in P.DOSSIERS:
            (self.r / d).mkdir()
        self.racine_vraie = P.RACINE
        P.RACINE = self.r

    def tearDown(self):
        P.RACINE = self.racine_vraie
        self.tmp.cleanup()

    def _vivants(self, **kw):
        """Remplace le calcul des noms vivants : ces bancs jugent le TRI, pas
        les formules de hachage (elles ont leur propre banc, cote mesure)."""
        import mesure_caches_vignettes as M
        vrai = M.noms_vivants
        M.noms_vivants = lambda *a: {d: set(kw.get(d, ())) for d in P.DOSSIERS}
        self.addCleanup(lambda: setattr(M, 'noms_vivants', vrai))
        P._index = lambda: ({}, {}, {})


class LeTriEtSesDeuxVerrous(DepotFactice):
    def test_un_orphelin_assez_vieux_part(self):
        self._vivants(photo_thumbs=['vivant'])
        _fichier(self.r / 'photo_thumbs', 'vivant', 100, jours=30)
        _fichier(self.r / 'photo_thumbs', 'mort', 500, jours=30)
        a_effacer, refus, _v = P.trier(jours=7, plancher=5.0)
        self.assertEqual(refus, [])
        self.assertEqual([Path(c).stem for c, _o, _a
                          in a_effacer['photo_thumbs']], ['mort'])

    def test_un_orphelin_TROP_JEUNE_est_epargne(self):
        """Verrou 2. Une formule fausse se trompe d'abord sur ce qu'on vient
        de creer : epargner les jeunes rend l'erreur visible avant qu'elle
        soit totale."""
        self._vivants(photo_thumbs=['vivant'])
        _fichier(self.r / 'photo_thumbs', 'vivant', 100, jours=30)
        _fichier(self.r / 'photo_thumbs', 'tout_neuf', 500, jours=1)
        a_effacer, _r, _v = P.trier(jours=7, plancher=5.0)
        self.assertEqual(a_effacer['photo_thumbs'], [])

    def test_un_dossier_QUE_L_ON_NE_RECONNAIT_PLUS_est_refuse_en_bloc(self):
        """Verrou 1, et c'est LE banc de cet outil. Si les formules divergent
        de `server.py`, tout parait orphelin — et tout effacer serait le pire
        geste possible, precisement au moment ou l'on comprend le moins."""
        self._vivants(face_thumbs=[])          # plus AUCUN nom reconnu
        for i in range(40):
            _fichier(self.r / 'face_thumbs', 'f%d' % i, 10, jours=30)
        a_effacer, refus, _v = P.trier(jours=7, plancher=5.0)
        self.assertNotIn('face_thumbs', a_effacer)
        self.assertEqual(len(refus), 1)
        self.assertIn('formule', refus[0][1])

    def test_le_plancher_se_juge_sur_TOUS_les_fichiers_pas_sur_les_vieux(self):
        """Sinon un cache recemment reconstruit — donc massivement vivant et
        jeune — se ferait juger sur sa poignee de vieux fichiers."""
        self._vivants(photo_thumbs=['v%d' % i for i in range(95)])
        for i in range(95):
            _fichier(self.r / 'photo_thumbs', 'v%d' % i, 10, jours=1)
        for i in range(5):
            _fichier(self.r / 'photo_thumbs', 'm%d' % i, 10, jours=30)
        a_effacer, refus, vus = P.trier(jours=7, plancher=5.0)
        self.assertEqual(refus, [])
        self.assertEqual(len(a_effacer['photo_thumbs']), 5)
        self.assertAlmostEqual(vus['photo_thumbs'][2], 95.0, places=1)

    def test_un_dossier_VIDE_ne_declenche_pas_le_refus(self):
        """0 sur 0 n'est pas 0 % : un cache vide est normal au premier
        demarrage, et refuser la ferait crier un outil pour rien."""
        self._vivants()
        a_effacer, refus, _v = P.trier(jours=7, plancher=5.0)
        self.assertEqual(refus, [])


class LEffacementEtSonJournal(DepotFactice):
    def test_efface_et_journalise(self):
        self._vivants(photo_thumbs=['vivant'])
        _fichier(self.r / 'photo_thumbs', 'vivant', 100, jours=30)
        mort = _fichier(self.r / 'photo_thumbs', 'mort', 500, jours=30)
        a_effacer, _r, _v = P.trier(jours=7, plancher=5.0)
        n, octets, journal = P.effacer(a_effacer, 7)
        self.assertEqual((n, octets), (1, 500))
        self.assertFalse(mort.exists())
        self.assertTrue((self.r / 'photo_thumbs' / 'vivant.jpg').exists())
        j = json.loads(journal.read_text(encoding='utf-8'))
        self.assertEqual(j['efface'][0]['fichier'], 'mort.jpg')
        self.assertIn('REGENERE', j['note'])

    def test_l_apercu_n_efface_RIEN(self):
        """Et le banc doit prouver que c'est l'APERCU qui epargne le fichier,
        pas le verrou du plancher : d'ou les vingt noms vivants. Un banc vert
        pour la mauvaise raison ne prouve rien."""
        vivants = ['x%d' % i for i in range(20)]
        self._vivants(photo_thumbs=vivants)
        for nom in vivants:
            _fichier(self.r / 'photo_thumbs', nom, 10, jours=1)
        mort = _fichier(self.r / 'photo_thumbs', 'mort', 500, jours=30)
        a_effacer, refus, _v = P.trier(jours=7, plancher=5.0)
        self.assertEqual(refus, [])                    # le plancher est passe
        self.assertEqual(len(a_effacer['photo_thumbs']), 1)   # il EST candidat
        P.main([])                                     # sans --appliquer
        self.assertTrue(mort.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
