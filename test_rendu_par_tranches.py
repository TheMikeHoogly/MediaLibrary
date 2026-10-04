#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests -- la planche ne batit que ce qui approche de l'ecran (04/10).

Mesure du 04/10 sur le fonds entier (44 430 photos) : la reponse finissait
d'arriver a 4,7 s et la page n'etait utilisable qu'a 7,5 s -- 2,8 s a batir
44 430 cases d'un coup. Rendu par tranches : 4,1-4,4 s, dont 0,2-0,6 s au
navigateur. Ce qui doit tenir :

1. **Une tranche, pas tout** : `renderGrid` ne boucle plus sur `visible`
   entier ; il pose une TRANCHE et observe une borne de fin.
2. **Rien n'est tronque** : le compteur lit `visible.length`, jamais le
   nombre de cases baties.
3. **« vers » batit jusqu'a sa case** avant de la chercher dans le DOM --
   sans quoi revenir sur une photo lointaine ne trouvait rien.
4. **La borne occupe une ligne entiere** de la grille, sinon elle prend la
   place d'une vignette.

Lit le gabarit sans navigateur. SORTIE EN ASCII PUR.
"""
import re
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent / "ui" / "pages" / "gallery.html"
SRC = PAGE.read_text(encoding="utf-8")


def _fonction(nom):
    i = SRC.index('function %s(' % nom)
    # jusqu'a la fonction de meme niveau suivante (deux espaces d'indentation)
    m = re.search(r'\n  function \w+\(', SRC[i + 10:])
    return SRC[i:i + 10 + (m.start() if m else len(SRC))]


class UneTranchePasTout(unittest.TestCase):
    def setUp(self):
        self.r = _fonction('renderGrid')

    def test_plus_de_boucle_sur_tout_visible(self):
        self.assertNotIn('visible.forEach(', self.r)

    def test_une_tranche_bornee_et_une_borne_observee(self):
        m = re.search(r'var TRANCHE = (\d+);', self.r)
        self.assertTrue(m, "TRANCHE introuvable")
        self.assertTrue(100 <= int(m.group(1)) <= 2000, m.group(1))
        self.assertIn('poserJusqua(TRANCHE)', self.r)
        self.assertIn('sentinelle.observe(borne)', self.r)
        self.assertIn('poserJusqua(rendus + TRANCHE)', self.r)

    def test_le_compteur_dit_le_total_reel(self):
        self.assertIn("var txt = visible.length + ' photo(s)'", self.r)
        self.assertNotIn('rendus + \' photo', self.r)

    def test_un_nouveau_rendu_repart_de_zero(self):
        self.assertIn('rendus = 0;', self.r)
        self.assertIn('sentinelle.disconnect()', self.r)


class VersBatitJusquASaCase(unittest.TestCase):
    def test_assurer_le_rendu_avant_de_chercher_la_case(self):
        i = SRC.index("var vers = new URLSearchParams")
        bloc = SRC[i:i + 1500]
        a = bloc.find('assurerRendu(vi)')
        b = bloc.find('.children[vi]')
        self.assertGreaterEqual(a, 0, "assurerRendu(vi) absent")
        self.assertGreater(b, a, "la case est cherchee avant d'etre batie")


class LaBorneEstUneLigne(unittest.TestCase):
    def test_css(self):
        self.assertRegex(SRC, r'\.borne-rendu\s*\{[^}]*grid-column:\s*1\s*/\s*-1')


if __name__ == '__main__':
    unittest.main()
