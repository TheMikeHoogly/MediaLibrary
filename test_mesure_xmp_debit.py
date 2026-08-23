#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests — le banc qui mesure le coût d'une invocation ExifTool.

Pourquoi ce fichier
───────────────────
Ce banc doit décider si le mode `-stay_open` vaut son risque (un processus
ExifTool qui vit longtemps, tient le NAS, et qu'il faudra savoir relancer).
Une décision se prend sur un chiffre — encore faut-il que le chiffre soit
mesuré, et pas produit par un pilote qui se trompe de protocole.

Le protocole `-stay_open` est la seule vraie difficulté : les ordres arrivent
un par ligne sur l'entrée standard, `-execute` déclenche, et le processus
répond `{ready}`. Un pilote qui ne lit pas `{ready}` croit avoir fini avant
l'heure — et rendrait un temps flatteur pour rien. C'est ce que ces tests
tiennent, avec un FAUX ExifTool qui parle le vrai protocole.

Aucun binaire installé n'est requis, aucun fichier du fonds n'est touché.
"""

import subprocess
import sys
import time
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mesure_xmp_debit as M                                   # noqa: E402


FAUX = textwrap.dedent('''
    """Un faux ExifTool : il parle le protocole, il n'ouvre aucune photo."""
    import os
    import sys

    def repondre(args):
        """Comme le vrai en `-json` : UN enregistrement par photo."""
        # Un fichier existant, pas « ce qui ne commence pas par - » : la
        # valeur d'une option (`-charset` puis `filename=UTF8`) n'est pas une
        # photo, et la compter en gonflerait le debit.
        vus = [a for a in args if not a.startswith('-') and os.path.exists(a)]
        print('[')
        for a in vus:
            print('  { "SourceFile": "%s", "Subject": "personne:Flo" },' % a)
        print(']')
        sys.stdout.flush()

    args = sys.argv[1:]
    if '-stay_open' in args and 'True' in args:
        lot = []
        for ligne in sys.stdin:
            ligne = ligne.strip()
            if ligne == '-execute':
                repondre(lot)
                lot = []
                print('{ready}')
                sys.stdout.flush()
            elif ligne == 'False':
                break
            elif ligne != '-stay_open':
                lot.append(ligne)
        sys.exit(0)

    if '-@' in args:
        fichier = args[args.index('-@') + 1]
        with open(fichier, encoding='utf-8-sig') as f:
            repondre([l.strip() for l in f if l.strip()])
    sys.exit(0)
''')


class Banc(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        faux = self.tmp / 'faux_exiftool.py'
        faux.write_text(FAUX, encoding='utf-8')
        self.exe = [sys.executable, str(faux)]
        self.photos = []
        for i in range(5):
            p = self.tmp / f'photo{i}.jpg'
            p.write_bytes(b'jpeg')
            self.photos.append(p)


class LesTroisRegimes(Banc):

    def test_stay_open_traite_TOUTES_les_photos(self):
        """Le piège : ne pas attendre `{ready}` fait croire à un régime rapide
        qui, en vrai, n'a rien traité."""
        s, n = M.regime_stay_open(self.exe, self.photos)
        self.assertEqual(n, len(self.photos))
        self.assertGreater(s, 0)

    def test_stay_open_referme_son_processus(self):
        """Un processus laissé vivant tiendrait le NAS jusqu'au redémarrage :
        c'est le risque même que ce banc doit peser, pas créer."""
        avant = M.regime_stay_open(self.exe, self.photos)
        self.assertEqual(avant[1], len(self.photos))
        # Un second passage ne pourrait pas aboutir si le premier avait laissé
        # son entrée standard ouverte sur un processus mort.
        self.assertEqual(M.regime_stay_open(self.exe, self.photos)[1],
                         len(self.photos))

    def test_un_par_photo_lance_bien_une_invocation_PAR_photo(self):
        s, n = M.regime_un_par_photo(self.exe, self.photos)
        self.assertEqual(n, len(self.photos))

    def test_le_lot_unique_lit_tout_le_lot(self):
        s, n = M.regime_un_seul_lot(self.exe, self.photos)
        self.assertEqual(n, len(self.photos))

    def test_un_exiftool_MUET_ne_fige_pas_le_banc(self):
        """Le 23/08, une variante d'arguments a rendu ExifTool muet en
        `-stay_open` : le banc a attendu `{ready}` pour toujours, et la fenetre
        des bancs avec lui. Un banc doit ECHOUER, jamais se figer."""
        muet = [sys.executable, '-c',
                'import sys; [None for _ in sys.stdin]']
        debut = time.time()
        s, n = M.regime_stay_open(muet, self.photos, delai=1.0)
        self.assertEqual(n, 0)
        self.assertLess(time.time() - debut, 20,
                        "le banc a attendu bien plus que son delai")

    def test_un_exiftool_mort_ne_fait_pas_tomber_le_banc(self):
        """Mesurer, c'est aussi encaisser l'echec de ce qu'on mesure."""
        s, n = M.regime_stay_open([sys.executable, '-c', 'raise SystemExit(1)'],
                                  self.photos)
        self.assertEqual(n, 0)


class LeComptage(Banc):

    def test_une_photo_a_DEUX_champs_ne_compte_que_pour_une(self):
        """Le defaut du premier jet : `-s3` rend une ligne par CHAMP, et le
        banc comptait des lignes. Une photo portant Subject et Keywords valait
        deux photos — le debit annonce etait faux d'un facteur variable."""
        for regime in (M.regime_un_seul_lot, M.regime_un_par_photo,
                       M.regime_stay_open):
            with self.subTest(regime=regime.__name__):
                self.assertEqual(regime(self.exe, self.photos)[1],
                                 len(self.photos))


class L_arithmetique(unittest.TestCase):

    def test_le_cout_par_photo_et_la_projection(self):
        self.assertAlmostEqual(M.par_photo(10.0, 5), 2.0)
        self.assertAlmostEqual(M.projeter(2.0, 1800), 1.0)

    def test_zero_photo_ne_divise_pas_par_zero(self):
        self.assertNotEqual(M.par_photo(3.0, 0), M.par_photo(3.0, 0))  # NaN

    def test_le_rapport_NOMME_la_gene_de_la_file(self):
        """Taire que la file tournait pendant la mesure rendrait les temps
        absolus trompeurs sans que personne puisse le savoir."""
        txt = M.rapport({'A': (10.0, 5), 'B': (2.0, 5), 'C': (3.0, 5)},
                        5907, gene=9000)
        self.assertIn('9000', txt)
        self.assertIn('borne HAUTE', txt)
        self.assertIn('2.00 s/photo', txt)

    def test_la_decision_n_applique_que_le_DEMARRAGE_a_l_ecriture(self):
        """Le piege de cadrage : la lecture va 15x plus vite avec -stay_open,
        mais une ECRITURE garde sa reecriture SMB. Seul l'ecart A - C se
        transpose ; annoncer 15x sur la file serait un mensonge."""
        txt = M.decision({'A': (10.0, 10), 'B': (1.0, 10), 'C': (2.0, 10)},
                         ecriture=3.0, photos_du_fonds=3600)
        self.assertIn('0.80 s', txt)          # 1.00 - 0.20 = le demarrage
        self.assertIn('2.20 s/op', txt)       # 3.00 - 0.80
        self.assertIn('27 %', txt)

    def test_la_decision_ne_promet_jamais_un_cout_negatif(self):
        """Une ecriture moins chere que le demarrage mesure (NAS rapide, cache)
        ne doit pas produire un gain imaginaire."""
        txt = M.decision({'A': (10.0, 10), 'B': (1.0, 10), 'C': (1.0, 10)},
                         ecriture=0.2, photos_du_fonds=100)
        self.assertIn('0.00 s/op', txt)
        self.assertNotIn('-', txt.split('retire QUE le demarrage')[1][:40])

    def test_sans_cout_d_ecriture_connu_le_rapport_ne_conclut_PAS(self):
        txt = M.rapport({'A': (10.0, 5), 'B': (2.0, 5), 'C': (3.0, 5)}, 5907)
        self.assertNotIn("POUR L'ECRITURE", txt)

    def test_le_rapport_tient_sans_gene_connue(self):
        txt = M.rapport({'A': (10.0, 5), 'B': (2.0, 5), 'C': (3.0, 5)}, 5907)
        self.assertNotIn('operation(s) en attente', txt)


class L_echantillon(Banc):

    def test_le_tirage_est_reproductible(self):
        """Graine fixe : deux passages comparent le MEME echantillon, sinon on
        mesure le tirage et pas le remede."""
        a = M.photos_du_dossier(self.tmp, 3)
        b = M.photos_du_dossier(self.tmp, 3)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 3)

    def test_seuls_les_fichiers_photo_sont_tires(self):
        (self.tmp / 'notes.txt').write_text('rien', encoding='utf-8')
        tires = M.photos_du_dossier(self.tmp, 50)
        self.assertTrue(all(p.suffix.lower() == '.jpg' for p in tires))
        self.assertEqual(len(tires), 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
