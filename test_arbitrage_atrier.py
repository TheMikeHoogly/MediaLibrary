#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La SALLE D'ARBITRAGE ne se range pas et ne se dedoublonne pas toute seule.

CE QUI S'EST PASSE, ET QUE CES BANCS EMPECHENT DE REFAIRE

Le bat 33 rapatrie sous `_A TRIER\\Google porte mieux\\<annee>` les photos que
Google detient en meilleure version que le NAS -- « un dossier a part, pour
qu'on sache qu'ils attendent un arbitrage », dit le bat lui-meme. Le 13/09 le
bat 36 est passe : pour lui, tout ce qui est sous `_A TRIER` est du materiel a
dedoublonner. Il a donc TRANCHE TOUT SEUL l'arbitrage de photos que Mike
n'avait pas regardees -- releve dans le rapport du 13/09 a 21 h 12 : 106
retraits confirmes, dont **68 sous « Google porte mieux »**. Le plan d'annee,
lui, les aurait classees le jour ou une cible se serait liberee.

Deux outils, un meme dossier, deux idees de ce qu'il est. La regle vit
desormais dans `rangement_annee` et le bat 36 la LIT.

CE QUI EST TENU ICI

  - la regle elle-meme, sur des chemins REELS de l'incident et sur les formes
    voisines qui doivent, elles, continuer de passer ;
  - l'ANCRAGE (CLAUDE.md n. 7) : la protection nomme la PLACE, pas le nom --
    un « Google porte mieux » range ailleurs dans le fonds n'est pas une
    salle, et un elagage compare a un nom NU frapperait les deux ;
  - le fait que les DEUX consommateurs lisent la meme regle, sur l'arbre et
    non sur le texte ;
  - le COMPTEUR : ce qui est ecarte est compte, sinon la regle est un voeu
    (CLAUDE.md n. 8).

Les chemins sont des LITTERAUX. Lire `docs/doublons_atrier.json` ferait juger
l'outil par son propre rapport (CLAUDE.md n. 6).

USAGE
    python test_arbitrage_atrier.py
"""

import ast
import unittest
from datetime import datetime
from pathlib import Path, PureWindowsPath

import rangement_annee as ra

# Les chemins du fonds sont des UNC Windows, et `Path(r'\\\\NAS\\x.jpg')` n'a
# QU'UN segment sous Linux : un banc qui laisse `Path` tel quel mesurerait la
# PLATEFORME au lieu de la regle (meme piege que `test_galerie_enrichissement`,
# PERFORMANCE.md). On rend donc au module le `Path` de Windows -- ces fonctions
# sont pures, elles ne touchent jamais au disque.
ra.Path = PureWindowsPath

ICI = Path(__file__).resolve().parent
NAS = r'\\NAS-Bremblens\home\Photos'

# Trois chemins de l'incident du 13/09, tels qu'ils sont dans le fonds.
SALLE = NAS + r'\_A TRIER\Google porte mieux\2024\20240712_180245.jpg'
SALLE_SANS_ANNEE = NAS + r'\_A TRIER\Google porte mieux\20260601_152532.jpg'
# Et un retrait du MEME rapport qui, lui, etait legitime : il n'est pas dans
# la salle. La regle doit faire la difference, sinon elle protege tout.
ATRI_NU = NAS + r'\_A TRIER\20260601_152532.jpg'


def ts(y):
    return datetime(y, 6, 1, 12, 0).timestamp()


class LaRegle(unittest.TestCase):

    def test_la_salle_est_reconnue(self):
        self.assertTrue(ra.est_arbitrage(SALLE))
        self.assertTrue(ra.est_arbitrage(SALLE_SANS_ANNEE))

    def test_le_reste_de_A_TRIER_passe_toujours(self):
        """Une regle qui protege tout ne protege rien : les 38 autres
        retraits du 13/09 etaient justes."""
        self.assertFalse(ra.est_arbitrage(ATRI_NU))

    def test_le_depot_ordinaire_du_bat_32_n_est_PAS_une_salle(self):
        """`Takeout Google` est l'autre depot, et il est different : ce sont
        des photos ABSENTES du fonds, qui doivent bien etre rangees. Les
        confondre gelerait un import entier."""
        self.assertFalse(
            ra.est_arbitrage(NAS + r'\_A TRIER\Takeout Google\2019\x.jpg'))

    def test_l_ANCRAGE_le_nom_seul_ne_suffit_pas(self):
        """CLAUDE.md n. 7. Un dossier « Google porte mieux » range dans le
        fonds est une photo comme une autre -- la salle n'existe que sous une
        boite de reception."""
        self.assertFalse(
            ra.est_arbitrage(NAS + r'\Photos Mike\Google porte mieux\x.jpg'))
        self.assertFalse(
            ra.est_arbitrage(NAS + r'\Google porte mieux\x.jpg'))

    def test_la_salle_d_un_PROPRIETAIRE_compte_aussi(self):
        """La boite de reception n'est plus seulement celle de la racine."""
        self.assertTrue(ra.est_arbitrage(
            NAS + r'\Photos Flo\_A TRIER\Google porte mieux\x.jpg'))

    def test_la_casse_et_les_separateurs_ne_decident_pas(self):
        for v in ('_A TRIER/google porte mieux/x.jpg',
                  'A TRIER/GOOGLE PORTE MIEUX/x.jpg',
                  '_A_TRIER/Google Porte Mieux/x.jpg'):
            self.assertTrue(ra.est_arbitrage(NAS + '\\' + v.replace('/', '\\')),
                            v)

    def test_un_nom_qui_COMMENCE_pareil_n_est_pas_la_salle(self):
        """`startswith` aurait dit oui a « Google porte mieux que rien » :
        la comparaison est une EGALITE de segment."""
        self.assertFalse(ra.est_arbitrage(
            NAS + r'\_A TRIER\Google porte mieux que rien\x.jpg'))

    def test_hors_de_toute_boite_c_est_non(self):
        self.assertFalse(ra.est_arbitrage(NAS + r'\Photos Mike\2020\x.jpg'))
        self.assertFalse(ra.est_arbitrage(''))


class LePlanDAnneeLaLAISSE(unittest.TestCase):

    def test_cible_rend_None_dans_la_salle(self):
        self.assertIsNone(ra.cible(SALLE, ts(2024)))

    def test_cible_range_toujours_le_reste(self):
        r = ra.cible(ATRI_NU, ts(2026))
        self.assertIsNotNone(r)
        self.assertEqual(Path(r[1]).parent.name, '2026')

    def test_le_plan_ne_la_deplace_pas_et_le_COMPTE(self):
        items = [('k1', SALLE, ts(2024)),
                 ('k2', SALLE_SANS_ANNEE, ts(2026)),
                 ('k3', ATRI_NU, ts(2026))]
        p = ra.construire_plan(items)
        self.assertEqual(p['arbitrage'], 2)
        self.assertEqual([m['key'] for m in p['moves']], ['k3'])

    def test_un_plan_sans_salle_annonce_ZERO_et_non_rien(self):
        """Un compteur absent se lit « pas de probleme » ; un zero se lit
        « regarde, et il n'y en avait pas »."""
        p = ra.construire_plan([('k', ATRI_NU, ts(2026))])
        self.assertEqual(p['arbitrage'], 0)


class LesDeuxOutilsLisentLaMEMERegle(unittest.TestCase):
    """C'est le fond de l'affaire : la regle etait RECOPIEE dans le bat 36.
    Mesure sur l'ARBRE -- un texte dirait une orthographe."""

    def setUp(self):
        self.src = (ICI / 'verifier_doublons_atrier.py').read_text(
            encoding='utf-8')
        self.arbre = ast.parse(self.src)

    def test_le_bat_36_appelle_la_regle_partagee(self):
        appels = [ast.unparse(n.func) for n in ast.walk(self.arbre)
                  if isinstance(n, ast.Call)]
        self.assertIn('_ra.est_arbitrage', appels)

    def test_le_bat_36_ne_REFABRIQUE_plus_le_motif_A_TRIER(self):
        """Il recopiait `re.compile(r'^_?a[ _]tri', re.I)`. Deux copies d'une
        regle finissent toujours par diverger -- c'est ce qui est arrive."""
        self.assertNotIn("re.compile(r'^_?a[ _]tri'", self.src)
        self.assertIn('ATRI_RE = _ra.ATRI_RE', self.src)

    def test_le_bat_36_ECARTE_des_DEUX_cotes(self):
        """Laissee dans le fonds, une photo de la salle deviendrait la
        « canonique » d'un autre doublon ; laissee dans `_A TRIER`, elle
        serait retiree sans verdict. Les deux branches d'enumeration doivent
        donc passer par le tri."""
        fn = [n for n in ast.walk(self.arbre)
              if isinstance(n, ast.FunctionDef) and n.name == 'main'][0]
        textes = [ast.unparse(n) for n in ast.walk(fn)]
        self.assertTrue(any('trier_arbitrage' in t for t in textes))
        self.assertTrue(any('_ra.est_arbitrage' in t for t in textes))

    def test_le_bat_36_COMPTE_ce_qu_il_laisse(self):
        self.assertIn('arbitrage_laisse', self.src)
        self.assertIn('LAISSES en arbitrage', self.src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
