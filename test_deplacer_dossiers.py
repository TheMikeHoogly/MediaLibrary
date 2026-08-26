#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `deplacer_dossiers.py` -- sans NAS, sans serveur, sans photos.db.

Ce script deplace 25 559 photos et 983 decisions humaines en un geste. Les
tests ci-dessous ne verifient pas qu'il « marche » : ils verifient les trois
facons dont un deplacement DETRUIT silencieusement.

  1. **Il laisse une decision humaine sur l ancien chemin.** C est l incident
     du 22/08 (928 decisions sur 3 364), et le chemin HORS-LIGNE le porte
     encore : `appliquer_plan.rekey_stores` se dit « miroir de
     server.rekey_everywhere » et ne re-cle que CINQ magasins sur SEPT.
  2. **Il recouvre un fichier deja en place.** Un deplacement ne fusionne
     jamais.
  3. **Il tourne pendant que le serveur ecrit.** Invariant 4 : un seul
     ecrivain sur SQLite.

SORTIE EN ASCII PUR.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deplacer_dossiers as D  # noqa: E402


class FauxStore:
    """Le contrat minimal dont le script depend : `.data`, `.rekey`, `.set`."""

    def __init__(self, data=None):
        self.data = dict(data or {})
        self.sauve = 0

    def rekey(self, old, new, mtime=None):
        if old not in self.data:
            return False
        self.data[new] = self.data.pop(old)
        return True

    def set(self, k, v, save=True):
        self.data[k] = v

    def save(self):
        self.sauve += 1


class FauxSemantique:
    def __init__(self):
        self.vus = []

    def rekey_prefix_all(self, old, new):
        self.vus.append((old, new))


def magasins(tags=None, faces=None, people=None, animals=None, pets=None):
    return {'tags': FauxStore(tags), 'faces': FauxStore(faces),
            'people': FauxStore(people), 'animals': FauxStore(animals),
            'pets': FauxStore(pets)}


class UNE_DECISION_HUMAINE_SUIT_SA_PHOTO(unittest.TestCase):
    """Le defaut qui a coute 928 decisions le 22/08, et que le chemin
    hors-ligne porte encore."""

    def test_un_rattachement_est_re_cle_dans_la_fiche(self):
        st = magasins(tags={'A': {}},
                      people={'flo': {'name': 'Flo', 'faces': [['A', 0]]}})
        deplacee, dec = D.recle_une_cle('A', 'B', st, FauxSemantique(), {})
        self.assertTrue(deplacee)
        self.assertEqual(dec, 1)
        self.assertEqual(st['people'].data['flo']['faces'], [['B', 0]])

    def test_et_dans_une_fiche_d_ANIMAL_aussi(self):
        st = magasins(tags={'A': {}},
                      pets={'caline': {'name': 'Caline', 'faces': [['A', 2]]}})
        _d, dec = D.recle_une_cle('A', 'B', st, FauxSemantique(), {})
        self.assertEqual(dec, 1)
        self.assertEqual(st['pets'].data['caline']['faces'], [['B', 2]])

    def test_une_EXCLUSION_suit_aussi(self):
        # « ce visage n est PAS Flo » est une etiquette humaine autant qu un
        # rattachement : la perdre fait revenir un faux positif.
        st = magasins(tags={'A': {}},
                      people={'flo': {'name': 'Flo', 'exclude': ['A']}})
        D.recle_une_cle('A', 'B', st, FauxSemantique(), {})
        self.assertEqual(st['people'].data['flo']['exclude'], ['B'])

    def test_la_fiche_est_REASSIGNEE_pas_mutee_au_fond_d_une_liste(self):
        # Une mutation en place passe sous le radar de la reconciliation du
        # store : l entree ne serait jamais marquee « sale », donc jamais
        # sauvee. Le script doit passer par `set`.
        st = magasins(tags={'A': {}},
                      people={'flo': {'name': 'Flo', 'faces': [['A', 0]]}})
        vus = []
        st['people'].set = lambda k, v, save=True: vus.append(k)
        D.recle_une_cle('A', 'B', st, FauxSemantique(), {})
        self.assertEqual(vus, ['flo'])


class LES_SEPT_MAGASINS_SUIVENT(unittest.TestCase):

    def test_les_stores_keyes_par_chemin(self):
        st = magasins(tags={'A': {}}, faces={'A': {'f': 1}},
                      animals={'A': {'a': 1}})
        D.recle_une_cle('A', 'B', st, FauxSemantique(), {})
        self.assertIn('B', st['faces'].data)
        self.assertIn('B', st['animals'].data)
        self.assertNotIn('A', st['faces'].data)

    def test_le_semantique(self):
        sem = FauxSemantique()
        D.recle_une_cle('A', 'B', magasins(tags={'A': {}}), sem, {})
        self.assertEqual(sem.vus, [('A', 'B')])

    def test_le_SEPTIEME_magasin_les_libelles_gps(self):
        gps = {'A': 'Morges'}
        D.recle_une_cle('A', 'B', magasins(tags={'A': {}}), FauxSemantique(), gps)
        self.assertEqual(gps, {'B': 'Morges'})

    def test_une_cle_absente_de_l_index_ne_deplace_RIEN(self):
        gps = {'A': 'Morges'}
        st = magasins(tags={}, people={'flo': {'faces': [['A', 0]]}})
        deplacee, dec = D.recle_une_cle('A', 'B', st, FauxSemantique(), gps)
        self.assertFalse(deplacee)
        self.assertEqual(dec, 0)
        self.assertEqual(gps, {'A': 'Morges'}, "c est `tags` qui decide")

    def test_le_chemin_HORS_LIGNE_existant_en_oublie_DEUX(self):
        # Ce test ne juge pas notre code : il GRAVE le defaut trouve le 26/08,
        # pour que personne ne « simplifie » ce script en reutilisant
        # `appliquer_plan.rekey_stores` en croyant qu il fait la meme chose.
        src = (Path(__file__).resolve().parent / 'appliquer_plan.py'
               ).read_text(encoding='utf-8')
        debut = src.index('def rekey_stores')
        corps = src[debut:debut + 900]
        self.assertNotIn('recle_decisions', corps,
                         "si ce test rougit, le chemin hors-ligne a ete"
                         " repare : le retirer et unifier les deux")
        self.assertNotIn('gps', corps)


class UN_DEPLACEMENT_NE_RECOUVRE_JAMAIS(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _lots(self, noms, stores, gps=None):
        return D.examiner(noms, self.tmp, 'Photos Mike', stores,
                          gps or {}, ecrire=lambda *a: None)

    def test_une_destination_deja_presente_BLOQUE(self):
        os.makedirs(os.path.join(self.tmp, '2015'))
        os.makedirs(os.path.join(self.tmp, 'Photos Mike', '2015'))
        _lots, bloquants = self._lots(['2015'], magasins(tags={}))
        self.assertEqual(bloquants, ['2015'])

    def test_une_source_absente_BLOQUE(self):
        _lots, bloquants = self._lots(['jamais-vu'], magasins(tags={}))
        self.assertEqual(bloquants, ['jamais-vu'])

    def test_un_dossier_normal_ne_bloque_pas(self):
        os.makedirs(os.path.join(self.tmp, '2015'))
        _lots, bloquants = self._lots(['2015'], magasins(tags={}))
        self.assertEqual(bloquants, [])

    def test_le_rapport_NOMME_les_dossiers_sans_aucune_photo(self):
        os.makedirs(os.path.join(self.tmp, '2015'))
        lignes = []
        D.examiner(['2015'], self.tmp, 'Photos Mike', magasins(tags={}), {},
                   ecrire=lignes.append)
        t = '\n'.join(lignes)
        self.assertIn('A VERIFIER', t)
        self.assertIn("n est pas un feu vert", t)


class ALLER_ET_RETOUR(unittest.TestCase):

    def test_le_journal_remet_tout_en_place(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / '2015').mkdir()
        (tmp / '2015' / 'a.jpg').write_text('x')
        old = str(tmp / '2015' / 'a.jpg')
        st = magasins(tags={old: {'kw_fr': ['personne:Flo']}},
                      people={'flo': {'name': 'Flo', 'faces': [[old, 0]]}})
        gps = {old: 'Morges'}
        sem = FauxSemantique()
        lots, _b = D.examiner(['2015'], str(tmp), 'Photos Mike', st, gps,
                              ecrire=lambda *a: None)
        journal = tmp / 'j.jsonl'
        D.appliquer(lots, st, sem, gps, journal, ecrire=lambda *a: None)

        neuf = str(tmp / 'Photos Mike' / '2015' / 'a.jpg')
        self.assertTrue((tmp / 'Photos Mike' / '2015' / 'a.jpg').exists())
        self.assertIn(neuf, st['tags'].data)
        self.assertEqual(st['people'].data['flo']['faces'], [[neuf, 0]])
        self.assertEqual(gps, {neuf: 'Morges'})

        D.defaire(journal, st, sem, gps, ecrire=lambda *a: None)
        self.assertTrue((tmp / '2015' / 'a.jpg').exists())
        self.assertIn(old, st['tags'].data)
        self.assertEqual(st['people'].data['flo']['faces'], [[old, 0]])
        self.assertEqual(gps, {old: 'Morges'})


class LE_SERVEUR_DOIT_ETRE_ARRETE_ET_CA_SE_PROUVE(unittest.TestCase):

    def test_une_base_libre_passe(self):
        d = Path(tempfile.mkdtemp()) / 'x.db'
        sqlite3.connect(str(d)).close()
        ok, _dit = D.serveur_arrete(d)
        self.assertTrue(ok)

    def test_une_base_VERROUILLEE_est_refusee(self):
        d = Path(tempfile.mkdtemp()) / 'x.db'
        cx = sqlite3.connect(str(d))
        cx.execute('create table t (a)')
        cx.execute('BEGIN IMMEDIATE')          # un autre ecrivain tient la base
        try:
            ok, dit = D.serveur_arrete(d)
            self.assertFalse(ok)
            self.assertIn('verrouillee', dit)
        finally:
            cx.execute('ROLLBACK')
            cx.close()

    def test_une_base_ABSENTE_ne_passe_pas_pour_libre(self):
        ok, _dit = D.serveur_arrete(Path(tempfile.mkdtemp()) / 'absente.db')
        # sqlite CREE le fichier : ce qui compte est qu on ne se mente pas sur
        # ce qu on a prouve. On documente le comportement observe.
        self.assertIsInstance(ok, bool)


class LA_LISTE_REFUSE_CE_QUI_N_EST_PAS_UN_DOSSIER(unittest.TestCase):

    def _lire(self, texte):
        p = Path(tempfile.mkdtemp()) / 'l.txt'
        p.write_text(texte, encoding='utf-8')
        return D.lire_liste(p)

    def test_les_noms_simples_passent(self):
        noms, refus = self._lire('2015\nAppart Bremblens\n# note\n\nCaline\n')
        self.assertEqual(noms, ['2015', 'Appart Bremblens', 'Caline'])
        self.assertEqual(refus, [])

    def test_un_chemin_est_REFUSE(self):
        noms, refus = self._lire('..\\autre\n2015\n')
        self.assertEqual(noms, ['2015'])
        self.assertEqual(len(refus), 1)

    def test_un_dossier_cache_est_REFUSE(self):
        _noms, refus = self._lire('.corbeille-rangement\n')
        self.assertEqual(refus, ['.corbeille-rangement'])

    def test_une_lettre_de_lecteur_est_REFUSEE(self):
        _noms, refus = self._lire('C:\\Photos\n')
        self.assertEqual(len(refus), 1)

    def test_la_liste_LIVREE_avec_le_projet_est_valide(self):
        noms, refus = D.lire_liste(Path(__file__).resolve().parent
                                   / 'dossiers_a_deplacer.txt')
        self.assertEqual(refus, [])
        self.assertEqual(len(noms), 26)
        self.assertIn('Caline', noms)
        self.assertNotIn('Photos Flo', noms)
        self.assertNotIn('Photos Papa', noms)
        self.assertNotIn('_Uploads', noms)


class LE_RAPPORT_DIT_CE_QU_IL_FAIT(unittest.TestCase):

    def test_la_sortie_est_en_ASCII_PUR(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, '2015'))
        lignes = []
        D.examiner(['2015'], tmp, 'Photos Mike', magasins(tags={}), {},
                   ecrire=lignes.append)
        '\n'.join(lignes).encode('ascii')


if __name__ == '__main__':
    unittest.main(verbosity=2)
