#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Une COLLISION n est pas une permission d effacer.

CE QUI MANQUAIT

`appliquer_plan_annee.py` refuse d ecraser et ecrit « [skip] destination deja
prise ». La regle est bonne ; le message laisse devant une question a laquelle
l outil ne repondait pas -- **le meme nom porte-t-il la meme photo ?** Les
deux cas demandent des gestes opposes : un doublon part a la corbeille
reversible, deux photos distinctes se renomment. Mike a pose exactement cette
question le 14/09 : « est-ce que ca veut dire que je peux les effacer ? »

CE QUE CES BANCS TIENNENT

  - les quatre verdicts, et surtout le troisieme : **VOISIN**. Le premier jet
    classait « deux videos distinctes » quatre fichiers qui ont la MEME duree
    a la centieme de seconde et 0,5 % d ecart de taille -- une conclusion que
    la mesure ne portait pas. Un instrument qui tranche au-dela de ce qu il
    mesure est pire qu un instrument muet ;
  - la regle n. 2 : un doublon qui porte un NOM HUMAIN absent de sa cible
    n est jamais « retirable », il passe en REVUE ;
  - le fait que rien ne s ecrit sur les fichiers ni sur `photos.db`.

Les durees et les empreintes sont INJECTEES : ce banc tient la REGLE. Que la
LECTURE marche pour de vrai, c est `mesure_duree_video.py` qui le dit -- et
c est en allant la chercher qu on a trouve le defaut des chemins accentues.

USAGE
    python test_verifier_plan_annee.py
"""

import ast
import json
import os
import tempfile
import unittest
from pathlib import Path

import verifier_doublons_atrier as V
import verifier_plan_annee as P

ICI = Path(__file__).resolve().parent


def ecrire(chemin, debut, milieu, taille):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    corps = bytearray(b'\0' * taille)
    corps[0:len(debut)] = debut
    m = taille // 2
    corps[m:m + len(milieu)] = milieu
    chemin.write_bytes(bytes(corps))
    return str(chemin)


class LesQuatreVerdicts(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.bloc, V.BLOC = V.BLOC, 64
        self.D = {}

    def tearDown(self):
        V.BLOC = self.bloc
        self.tmp.cleanup()

    def duree(self, c, s):
        self.D[V.hkey(c)] = (s, '1920x1080')

    def juger(self, src, dst, hashes=None, noms=None):
        return P.comparer(src, dst, 'exiftool', hashes or {}, self.D,
                          noms or {})

    def test_meme_flux_c_est_un_DOUBLON(self):
        a = ecrire(self.d / 'a' / 'v.mp4', b'D', b'M', 1000)
        b = ecrire(self.d / 'b' / 'v.mp4', b'D', b'M', 1000)
        self.duree(a, 12.0); self.duree(b, 12.0)
        v, _ = self.juger(a, b)
        self.assertEqual(v, P.DOUBLON)

    def test_durees_differentes_c_est_DIFFERENT_et_ca_le_DIT(self):
        a = ecrire(self.d / 'a' / 'v.mp4', b'D', b'M', 1000)
        b = ecrire(self.d / 'b' / 'v.mp4', b'X', b'Y', 1400)
        self.duree(a, 35.81); self.duree(b, 37.24)
        v, pourquoi = self.juger(a, b)
        self.assertEqual(v, P.DIFFERENT)
        self.assertIn('35.81', pourquoi)
        self.assertIn('37.24', pourquoi)

    def test_MEME_duree_et_taille_proche_c_est_VOISIN_pas_different(self):
        """Le garde-fou qui compte. Quatre fichiers du plan reel ont la MEME
        duree a la centieme et 0,5 % d ecart : conclure « deux videos
        distinctes » dessus, c est trancher au-dela de la mesure."""
        a = ecrire(self.d / 'a' / 'v.mp4', b'DEBUT', b'M', 1000)
        b = ecrire(self.d / 'b' / 'v.mp4', b'AUTRE', b'Z', 1004)
        self.duree(a, 66.36); self.duree(b, 66.36)
        v, pourquoi = self.juger(a, b)
        self.assertEqual(v, P.VOISIN)
        self.assertIn('MEME DUREE', pourquoi)

    def test_meme_duree_mais_taille_TRES_differente_reste_DIFFERENT(self):
        """Le voisinage a une borne : 5 % de taille. Au-dela, deux fichiers
        de meme duree ne sont plus le meme film reencapsule."""
        a = ecrire(self.d / 'a' / 'v.mp4', b'DEBUT', b'M', 1000)
        b = ecrire(self.d / 'b' / 'v.mp4', b'AUTRE', b'Z', 2000)
        self.duree(a, 66.36); self.duree(b, 66.36)
        self.assertEqual(self.juger(a, b)[0], P.DIFFERENT)

    def test_une_duree_INCONNUE_ne_fabrique_pas_un_voisin(self):
        """Deux durees a zero sont EGALES : sans ce garde-fou, deux fichiers
        qu exiftool n a pas su lire deviendraient « le meme film »."""
        a = ecrire(self.d / 'a' / 'v.mp4', b'DEBUT', b'M', 1000)
        b = ecrire(self.d / 'b' / 'v.mp4', b'AUTRE', b'Z', 1004)
        self.assertEqual(self.juger(a, b)[0], P.DIFFERENT)

    def test_pixels_differents_c_est_DIFFERENT(self):
        a = ecrire(self.d / 'a' / 'p.jpg', b'D', b'M', 1000)
        b = ecrire(self.d / 'b' / 'p.jpg', b'D', b'M', 1000)
        v, _ = self.juger(a, b, {V.hkey(a): 'h1', V.hkey(b): 'h2'})
        self.assertEqual(v, P.DIFFERENT)

    def test_memes_pixels_c_est_un_DOUBLON_meme_si_les_octets_different(self):
        """C est tout le motif d `ImageDataHash` : la remorque de
        metadonnees ne fait pas deux photos."""
        a = ecrire(self.d / 'a' / 'p.jpg', b'D', b'M', 1000)
        b = ecrire(self.d / 'b' / 'p.jpg', b'X', b'Y', 1800)
        v, _ = self.juger(a, b, {V.hkey(a): 'h', V.hkey(b): 'h'})
        self.assertEqual(v, P.DOUBLON)

    def test_un_NOM_HUMAIN_absent_de_la_cible_passe_en_REVUE(self):
        """CLAUDE.md n. 2. La regle valait deja pour le bat 36 ; elle vaut
        ici, ou le verdict autorise un retrait."""
        a = ecrire(self.d / 'a' / 'p.jpg', b'D', b'M', 1000)
        b = ecrire(self.d / 'b' / 'p.jpg', b'X', b'Y', 1800)
        noms = {V.hkey(a): {'personne:Florine'}, V.hkey(b): set()}
        v, pourquoi = self.juger(a, b, {V.hkey(a): 'h', V.hkey(b): 'h'}, noms)
        self.assertEqual(v, P.REVUE)
        self.assertIn('Florine', pourquoi)

    def test_une_source_disparue_ne_leve_pas(self):
        b = ecrire(self.d / 'b' / 'p.jpg', b'D', b'M', 1000)
        self.assertEqual(self.juger(str(self.d / 'pas_la.jpg'), b)[0],
                         P.ABSENT)

    def test_une_extension_inconnue_est_ILLISIBLE_pas_un_doublon(self):
        a = ecrire(self.d / 'a' / 'x.txt', b'D', b'M', 100)
        b = ecrire(self.d / 'b' / 'x.txt', b'D', b'M', 100)
        self.assertEqual(self.juger(a, b)[0], P.ILLISIBLE)


class ElleNEcritQueSonRapport(unittest.TestCase):

    def test_aucune_ecriture_sur_les_fichiers_ni_sur_la_base(self):
        src = (ICI / 'verifier_plan_annee.py').read_text(encoding='utf-8')
        arbre = ast.parse(src)
        interdits = set()
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call):
                f = n.func
                a = f.attr if isinstance(f, ast.Attribute) else getattr(
                    f, 'id', '')
                if a in ('remove', 'unlink', 'rename', 'replace', 'rmtree',
                         'move', 'copy', 'copy2', 'execute', 'commit'):
                    interdits.add(a)
        self.assertEqual(interdits, set(), interdits)

    def test_elle_REFUSE_la_base_vivante(self):
        with self.assertRaises(SystemExit):
            P.noms_humains(ICI / 'photos.db')

    def test_un_seul_rapport_et_il_est_dans_docs(self):
        self.assertEqual(P.RAPPORT.parent.name, 'docs')
        self.assertEqual(P.RAPPORT.name, 'plan_annee_collisions.json')


class LeBat26LeLANCE(unittest.TestCase):
    """Un controle que le bat n appelle pas est un controle qui n existe
    pas : c est la lecon du banc reste rouge une livraison entiere."""

    def setUp(self):
        self.bat = (ICI / '26 - Ranger par annee.bat').read_bytes()

    def test_le_bat_appelle_le_controle_AVANT_l_apercu(self):
        t = self.bat.decode('ascii')
        self.assertIn('verifier_plan_annee.py', t)
        self.assertLess(t.index('verifier_plan_annee.py'),
                        t.index('appliquer_plan_annee.py'))

    def test_le_bat_dit_qu_une_collision_n_autorise_pas_un_effacement(self):
        t = self.bat.decode('ascii')
        self.assertIn("n'est PAS une permission d'effacer", t)

    def test_le_bat_reste_en_ASCII_PUR_et_en_CRLF(self):
        """La regle n. 1 du projet, et elle a deja ete cassee trois fois."""
        self.assertTrue(all(c < 128 for c in self.bat))
        self.assertNotIn(b'\n', self.bat.replace(b'\r\n', b''))

    def test_aucun_bloc_parenthese(self):
        """Une parenthese dans un echo A L INTERIEUR d un bloc ferme le bloc.
        Ce bat n a aucun bloc : que des `goto`."""
        t = self.bat.decode('ascii')
        for ligne in t.splitlines():
            l = ligne.strip()
            if l.startswith('if ') or l.startswith('for '):
                self.assertFalse(l.endswith('('), ligne)


class RienNePeutBouger(unittest.TestCase):
    """16/09 : 19 cibles prises sur 19, et le bat 26 coupait quand meme le
    serveur. Le code RIEN (3) le fait s'arreter avant."""

    def _plan(self, d, moves):
        p = Path(d) / 'plan.json'
        p.write_text(json.dumps({'moves': moves}), encoding='utf-8')
        return str(p)

    def test_plan_vide(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(P.main(['--plan', self._plan(d, [])]), P.RIEN)

    def test_toutes_prises_sans_exiftool(self):
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'pris.jpg'
            dst.write_bytes(b'x')
            vrai = P.V.exiftool
            P.V.exiftool = lambda: None
            try:
                code = P.main(['--plan', self._plan(d, [{'src': str(Path(d) / 's.jpg'),
                                                         'dst': str(dst)}])])
            finally:
                P.V.exiftool = vrai
            self.assertEqual(code, P.RIEN)

    def test_une_libre_sans_exiftool_reste_2(self):
        with tempfile.TemporaryDirectory() as d:
            dst = Path(d) / 'pris.jpg'
            dst.write_bytes(b'x')
            vrai = P.V.exiftool
            P.V.exiftool = lambda: None
            try:
                code = P.main(['--plan', self._plan(d, [
                    {'src': 'a.jpg', 'dst': str(dst)},
                    {'src': 'b.jpg', 'dst': str(Path(d) / 'libre.jpg')}])])
            finally:
                P.V.exiftool = vrai
            self.assertEqual(code, 2)

    def test_aucune_collision_zero(self):
        with tempfile.TemporaryDirectory() as d:
            ancien = P.RAPPORT
            P.RAPPORT = Path(d) / 'r.json'
            try:
                code = P.main(['--plan', self._plan(d, [
                    {'src': 'a.jpg', 'dst': str(Path(d) / 'libre.jpg')}])])
            finally:
                P.RAPPORT = ancien
            self.assertEqual(code, 0)

    def test_le_bat_lit_3_AVANT_2(self):
        bat = (Path(__file__).resolve().parent / '26 - Ranger par annee.bat'
               ).read_text(encoding='ascii')
        self.assertLess(bat.index('if errorlevel 3 goto RIEN_A_RANGER'),
                        bat.index('if errorlevel 2 goto SANS_VERDICT'))
        rien = bat[bat.index(':RIEN_A_RANGER'):bat.index(':SANS_VERDICT')]
        self.assertIn('goto FIN', rien)
        self.assertNotIn('commande_serveur', rien)


if __name__ == '__main__':
    unittest.main(verbosity=2)
