#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `copier_reprise` — ce qu'une coupure ne doit JAMAIS produire.

Pourquoi ce fichier
───────────────────
Un copieur qui reprend au milieu d'un fichier peut échouer d'une façon bien
pire que d'échouer : rendre un fichier de la BONNE TAILLE et au contenu
incohérent. C'est exactement ce qui arriverait ici si la source changeait
pendant la copie — `backup_db()` remplace `photos.db.bak` toutes les heures.
Une sauvegarde à moitié d'hier et à moitié d'aujourd'hui passerait tous les
contrôles de taille et ne se verrait qu'au moment de restaurer.

Ces tests fixent donc deux choses : que la reprise REPREND (sinon le script ne
sert à rien face au réseau du 22/08), et qu'elle refuse de coller deux sources
différentes.

Aucun accès réseau : les coupures sont simulées.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import copier_reprise as C


class SourceQuiCoupe:
    """Un `open` qui lève une OSError après N octets lus, une fois par essai."""

    def __init__(self, apres_octets, fois=1):
        self.apres, self.fois, self.vrai = apres_octets, fois, open

    def __call__(self, chemin, mode='rb', *a, **kw):
        f = self.vrai(chemin, mode, *a, **kw)
        if 'r' not in mode or 'b' not in mode or self.fois <= 0:
            return f
        return self._enrobe(f)

    def _enrobe(self, f):
        etat = {'lus': 0}
        vrai_read = f.read
        sac = self

        def read(n=-1):
            if etat['lus'] >= sac.apres and sac.fois > 0:
                sac.fois -= 1
                raise OSError(59, "Erreur reseau inattendue (simulee)")
            d = vrai_read(n)
            etat['lus'] += len(d)
            return d

        f.read = read
        return f


class Base(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.src = self.d / 'source.bin'
        self.dst = self.d / 'cible.bin'
        self.contenu = bytes(range(256)) * 4000        # ~1 Mo, motif verifiable
        self.src.write_bytes(self.contenu)
        self.dits = []

    def journal(self, *a):
        self.dits.append(' '.join(str(x) for x in a))


class TestCopieSimple(Base):

    def test_une_copie_sans_incident(self):
        ok, n, reprises = C.copier(self.src, self.dst, bloc_mo=0.1,
                                   journal=self.journal)
        self.assertTrue(ok)
        self.assertEqual(reprises, 0)
        self.assertEqual(self.dst.read_bytes(), self.contenu)

    def test_la_date_de_la_source_est_reportee(self):
        C.copier(self.src, self.dst, bloc_mo=0.1, journal=self.journal)
        self.assertEqual(int(self.dst.stat().st_mtime),
                         int(self.src.stat().st_mtime))

    def test_le_temoin_de_reprise_ne_survit_pas_au_succes(self):
        C.copier(self.src, self.dst, bloc_mo=0.1, journal=self.journal)
        self.assertFalse(self.dst.with_suffix('.bin.reprise').exists())


class TestReprise(Base):
    """Le cœur : une coupure coûte un bloc, pas le fichier."""

    def test_la_copie_reprend_et_le_contenu_est_JUSTE(self):
        vrai_open = C.open if hasattr(C, 'open') else open
        C.open = SourceQuiCoupe(300_000, fois=1)
        try:
            ok, n, reprises = C.copier(self.src, self.dst, bloc_mo=0.05,
                                       journal=self.journal, pause_s=0)
        finally:
            C.open = vrai_open
        self.assertTrue(ok, self.dits)
        self.assertEqual(reprises, 1)
        self.assertEqual(self.dst.read_bytes(), self.contenu)

    def test_plusieurs_coupures_de_suite(self):
        vrai_open = C.open if hasattr(C, 'open') else open
        C.open = SourceQuiCoupe(200_000, fois=3)
        try:
            ok, _, reprises = C.copier(self.src, self.dst, bloc_mo=0.05,
                                       journal=self.journal, pause_s=0)
        finally:
            C.open = vrai_open
        self.assertTrue(ok, self.dits)
        self.assertEqual(reprises, 3)
        self.assertEqual(self.dst.read_bytes(), self.contenu)

    def test_au_dela_du_plafond_il_ABANDONNE_au_lieu_de_boucler(self):
        vrai_open = C.open if hasattr(C, 'open') else open
        C.open = SourceQuiCoupe(100_000, fois=99)
        try:
            ok, _, _ = C.copier(self.src, self.dst, bloc_mo=0.05, tentatives=2,
                                journal=self.journal, pause_s=0)
        finally:
            C.open = vrai_open
        self.assertFalse(ok)
        self.assertTrue(any('ABANDON' in x for x in self.dits))


class TestJamaisDeuxSourcesCollees(Base):
    """Un fichier de la bonne taille au contenu hybride serait le pire cas."""

    def temoin(self, taille, mtime):
        p = self.dst.with_suffix('.bin.reprise')
        p.write_text('{"taille": %d, "mtime": %d}' % (taille, mtime),
                     encoding='utf-8')

    def test_reprise_refusee_si_la_taille_a_change(self):
        info = {'taille': len(self.contenu), 'mtime': 111}
        self.assertFalse(C.reprise_possible(info, {'taille': 999, 'mtime': 111},
                                            500))

    def test_reprise_refusee_si_la_date_a_change(self):
        info = {'taille': len(self.contenu), 'mtime': 222}
        self.assertFalse(C.reprise_possible(info,
                                            {'taille': info['taille'],
                                             'mtime': 111}, 500))

    def test_reprise_refusee_sans_temoin(self):
        info = {'taille': 10, 'mtime': 1}
        self.assertFalse(C.reprise_possible(info, None, 5))

    def test_reprise_acceptee_quand_tout_concorde(self):
        info = {'taille': 10, 'mtime': 1}
        self.assertTrue(C.reprise_possible(info, dict(info), 5))

    def test_une_copie_partielle_ETRANGERE_est_jetee(self):
        # Cas réel : un essai précédent, puis la sauvegarde horaire a remplacé
        # la source. Le début appartient à l'ancienne base.
        self.dst.write_bytes(b'\xff' * 400_000)
        self.temoin(len(self.contenu) + 12345, 42)
        ok, _, _ = C.copier(self.src, self.dst, bloc_mo=0.1,
                            journal=self.journal, pause_s=0)
        self.assertTrue(ok)
        self.assertEqual(self.dst.read_bytes(), self.contenu)
        self.assertTrue(any('repart de zero' in x for x in self.dits))


if __name__ == '__main__':
    unittest.main(verbosity=2)
