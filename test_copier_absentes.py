#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `copier_absentes.py` — sans NAS, sans Google, sans reseau.

Ce que ces tests tiennent
-------------------------
1. **Rien n'est jamais ECRASE.** Un homonyme de meme taille est saute (le
   script est reprenable) ; d'une autre taille, la copie prend un nom
   suffixe et se DIT. C'est la regle 2 du projet appliquee a une copie :
   aucun octet du fonds existant ne se perd.
2. **L'annee ne vient JAMAIS du `mtime`.** Un fichier copie aujourd'hui a le
   `mtime` d'aujourd'hui : s'en servir ferait passer tout l'export pour 2026.
   Le `.json` de Takeout d'abord, le dossier `Photos from YYYY` ensuite.
3. **La cible doit etre sous `_A TRIER`,** parce que c'est la que la chaine
   reprend. Ecrire 12 Go ailleurs sur un NAS ne se rattrape pas.
4. **Chaque copie est RELUE.** Une taille qui ne correspond pas est un
   grief, pas un succes.
5. **Sans `--copier`, le disque reste intact.**

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import copier_absentes as C  # noqa: E402


def export(base, fichiers, sidecars=None):
    """Un mini-export Takeout : {chemin relatif: octets}."""
    base = Path(base)
    for rel, n in fichiers.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x' * n)
    for rel, epoch in (sidecars or {}).items():
        p = base / (rel + '.json')
        p.write_text(json.dumps({'title': os.path.basename(rel),
                                 'photoTakenTime': {'timestamp': str(epoch)}}),
                     encoding='utf-8')
    return base


def rapport_google(chemin, medias):
    Path(chemin).write_text(json.dumps(
        {'par_verdict': {'ABSENT': medias}}), encoding='utf-8')
    return str(chemin)


class LAnnee(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="test_cop_"))

    def test_le_sidecar_de_Takeout_fait_foi(self):
        export(self.d, {'Photos from 2026/a.jpg': 10},
               {'Photos from 2026/a.jpg': 1104537600})     # 2005
        an = C.annee_du_media(str(self.d / 'Photos from 2026/a.jpg'))
        self.assertEqual(an, 2005)          # le sidecar gagne sur le dossier

    def test_a_defaut_le_dossier_Photos_from_YYYY(self):
        export(self.d, {'Photos from 2019/b.jpg': 10})
        self.assertEqual(
            C.annee_du_media(str(self.d / 'Photos from 2019/b.jpg')), 2019)

    def test_sans_rien_l_annee_est_INCONNUE_pas_celle_du_mtime(self):
        # Le piege : un fichier copie aujourd'hui a le mtime d'aujourd'hui.
        export(self.d, {'Album de Carl/c.jpg': 10})
        self.assertIsNone(C.annee_du_media(str(self.d / 'Album de Carl/c.jpg')))


class RienNEstEcrase(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="test_cop2_"))
        self.cible = self.d / '_A TRIER' / 'Takeout Google'

    def test_un_homonyme_de_MEME_taille_est_saute(self):
        (self.cible / '2019').mkdir(parents=True)
        (self.cible / '2019' / 'a.jpg').write_bytes(b'x' * 10)
        export(self.d, {'Photos from 2019/a.jpg': 10})
        t = C.plan([{'chemin_google': str(self.d / 'Photos from 2019/a.jpg'),
                     'octets': 10}], self.cible)
        self.assertEqual(t[0][2], 'deja')

    def test_un_homonyme_d_une_AUTRE_taille_prend_un_suffixe(self):
        (self.cible / '2019').mkdir(parents=True)
        (self.cible / '2019' / 'a.jpg').write_bytes(b'x' * 7)
        export(self.d, {'Photos from 2019/a.jpg': 10})
        t = C.plan([{'chemin_google': str(self.d / 'Photos from 2019/a.jpg'),
                     'octets': 10}], self.cible)
        self.assertEqual(t[0][2], 'suffixe')
        self.assertTrue(t[0][1].endswith('a (2).jpg'), t[0][1])
        # ... et l'original est INTACT.
        self.assertEqual((self.cible / '2019' / 'a.jpg').stat().st_size, 7)

    def test_la_copie_reprend_sans_tout_refaire(self):
        export(self.d, {'Photos from 2019/a.jpg': 10,
                        'Photos from 2019/b.jpg': 20})
        medias = [{'chemin_google': str(self.d / 'Photos from 2019' / n),
                   'octets': o} for n, o in (('a.jpg', 10), ('b.jpg', 20))]
        C.copier(C.plan(medias, self.cible), ecrire=lambda *x: None)
        compte, _g, ecrits = C.copier(C.plan(medias, self.cible),
                                      ecrire=lambda *x: None)
        self.assertEqual(compte['copie'], 0)
        self.assertEqual(compte['deja'], 2)
        self.assertEqual(ecrits, [])


class LaCopie(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="test_cop3_"))
        self.cible = self.d / '_A TRIER' / 'Takeout Google'

    def test_les_fichiers_atterrissent_dans_leur_ANNEE(self):
        export(self.d, {'Photos from 2024/a.jpg': 10,
                        'Photos from 2005/b.jpg': 20})
        medias = [{'chemin_google': str(self.d / 'Photos from 2024/a.jpg'),
                   'octets': 10},
                  {'chemin_google': str(self.d / 'Photos from 2005/b.jpg'),
                   'octets': 20}]
        compte, _g, ecrits = C.copier(C.plan(medias, self.cible),
                                      ecrire=lambda *x: None)
        self.assertEqual(compte['copie'], 2)
        self.assertTrue((self.cible / '2024' / 'a.jpg').is_file())
        self.assertTrue((self.cible / '2005' / 'b.jpg').is_file())
        self.assertEqual(len(ecrits), 2)

    def test_sans_annee_le_fichier_va_dans_SANS_DATE(self):
        export(self.d, {'Album/c.jpg': 5})
        C.copier(C.plan([{'chemin_google': str(self.d / 'Album/c.jpg'),
                          'octets': 5}], self.cible),
                 ecrire=lambda *x: None)
        self.assertTrue((self.cible / C.SANS_DATE / 'c.jpg').is_file())

    def test_une_source_disparue_est_un_GRIEF_pas_un_silence(self):
        compte, griefs, _e = C.copier(
            [(str(self.d / 'nexistepas.jpg'),
              str(self.cible / '2024' / 'x.jpg'), 'neuf')],
            ecrire=lambda *x: None)
        self.assertEqual(compte['grief'], 1)
        self.assertTrue(griefs)

    def test_le_journal_d_annulation_liste_ce_qui_a_ete_ecrit(self):
        export(self.d, {'Photos from 2024/a.jpg': 10})
        _c, _g, ecrits = C.copier(
            C.plan([{'chemin_google': str(self.d / 'Photos from 2024/a.jpg'),
                     'octets': 10}], self.cible), ecrire=lambda *x: None)
        p = C.journal(ecrits, dossier=self.d / '_corbeille_copies')
        lignes = Path(p).read_text(encoding='utf-8').strip().splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertIn('destination', json.loads(lignes[0]))

    def test_sans_rien_a_ecrire_il_n_y_a_pas_de_journal(self):
        self.assertIsNone(C.journal([], dossier=self.d / '_c'))


class LesGardeFous(unittest.TestCase):

    def _dit(self, **kw):
        lignes = []
        base = dict(travaux=[('s', 'd', 'neuf')],
                    cible=Path('/nas/_A TRIER/Takeout Google'),
                    octets=100, libre=10 ** 9)
        base.update(kw)
        ok = C.rapport(ecrire=lignes.append, **base)
        return ok, lignes

    def test_une_cible_hors_A_TRIER_ne_passe_PAS(self):
        ok, lignes = self._dit(cible=Path('/nas/Photos/ailleurs'))
        self.assertFalse(ok)
        self.assertTrue(any('N EST PAS SOUS' in l for l in lignes))

    def test_le_garde_fou_se_leve_explicitement(self):
        ok, _l = self._dit(cible=Path('/nas/Photos/ailleurs'),
                           hors_a_trier=True)
        self.assertTrue(ok)

    def test_A_TRIER_est_reconnu_dans_le_chemin(self):
        self.assertTrue(C.sous_a_trier('/nas/home/Photos/_A TRIER/x/2024'))
        self.assertTrue(C.sous_a_trier('/nas/home/Photos/_A_TRIER/x'))
        self.assertFalse(C.sous_a_trier('/nas/home/Photos/Photos Mike'))

    def test_la_place_manquante_ne_passe_pas(self):
        ok, lignes = self._dit(octets=10 ** 9, libre=10)
        self.assertFalse(ok)
        self.assertTrue(any('PAS ASSEZ DE PLACE' in l for l in lignes))

    def test_aucune_absente_ne_rend_PAS_vert(self):
        # Un rapport vide peut vouloir dire << tout est copie >> comme
        # << mauvais rapport >>. On ne conclut pas a la place de l'humain.
        ok, lignes = self._dit(travaux=[])
        self.assertFalse(ok)
        self.assertTrue(any('rien a copier' in l for l in lignes))

    def test_un_grief_de_copie_rend_rouge(self):
        ok, _l = self._dit(compte={'copie': 1, 'deja': 0, 'suffixe': 0,
                                   'grief': 1}, griefs=['x'])
        self.assertFalse(ok)


class LaLigneDeCommande(unittest.TestCase):

    def test_sans_copier_le_disque_reste_INTACT(self):
        d = Path(tempfile.mkdtemp(prefix="test_cop4_"))
        export(d, {'Photos from 2024/a.jpg': 10})
        r = rapport_google(d / 'r.json', [
            {'nom': 'a.jpg', 'octets': 10,
             'chemin_google': str(d / 'Photos from 2024/a.jpg')}])
        cible = d / '_A TRIER' / 'T'
        code = C.main(['--rapport', r, '--cible', str(cible)])
        self.assertEqual(code, 0)
        self.assertFalse(cible.exists())

    def test_avec_copier_le_fichier_arrive(self):
        d = Path(tempfile.mkdtemp(prefix="test_cop5_"))
        export(d, {'Photos from 2024/a.jpg': 10})
        r = rapport_google(d / 'r.json', [
            {'nom': 'a.jpg', 'octets': 10,
             'chemin_google': str(d / 'Photos from 2024/a.jpg')}])
        cible = d / '_A TRIER' / 'T'
        code = C.main(['--rapport', r, '--cible', str(cible), '--copier',
                       '--json', str(d / 'sortie.json')])
        self.assertEqual(code, 0)
        self.assertTrue((cible / '2024' / 'a.jpg').is_file())
        s = json.loads((d / 'sortie.json').read_text(encoding='utf-8'))
        self.assertEqual(s['compte']['copie'], 1)
        self.assertTrue(s['journal'])

    def test_un_rapport_introuvable_ne_tombe_pas(self):
        self.assertEqual(C.main(['--rapport', '/nexistepas.json']), 2)


if __name__ == '__main__':
    unittest.main(verbosity=0)
