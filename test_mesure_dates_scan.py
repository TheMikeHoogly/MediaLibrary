#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_dates_scan` — cas FORGES, aucune base, aucun fichier.

Ce qu'ils protegent, dans l'ordre de ce qui a deja coute cher au projet :
  - l'ASYMETRIE (une date anterieure au dossier est legitime, mesure du 17/08) ;
  - la TOLERANCE d'un an (les 139 reveillons du 14/08) ;
  - le fait que le nom de fichier n'est JAMAIS lu comme une annee de dossier
    (« 119-1908_IMG.JPG » reculait une photo de 94 ans, 14/08) ;
  - l'INDEPENDANCE des deux chemins de mesure (A lit le dossier, B lit le nom).
"""
import time
import unittest

import mesure_dates_scan as M


def epoch(y, mo=6, d=15, h=12):
    return time.mktime((y, mo, d, h, 0, 0, 0, 0, -1))


P = '\\\\NAS-Bremblens\\home\\Photos'


class TestAnnee(unittest.TestCase):

    def test_epoch_valide(self):
        self.assertEqual(M.annee_de(epoch(2007)), 2007)

    def test_absent_zero_negatif_bool(self):
        for v in (None, 0, -1, '', 'x', True, False, []):
            self.assertIsNone(M.annee_de(v), repr(v))

    def test_31_decembre_au_soir_reste_dans_son_annee(self):
        # localtime, jamais gmtime : un fuseau ferait basculer d'annee.
        self.assertEqual(M.annee_de(epoch(2019, 12, 31, 23)), 2019)


class TestClasser(unittest.TestCase):

    def test_scan_presume_le_cas_reel(self):
        k = P + '\\Photos Papa\\1990\\1990_Achumani\\19900000_achumani_Markus.jpg'
        v = M.classer(k, epoch(2007, 5, 1))
        self.assertEqual(v['statut'], 'scan_presume')
        self.assertEqual(v['annee'], 2007)
        self.assertEqual(v['ecart'], 17)
        self.assertIn(1990, v['annees_chemin'])

    def test_anterieure_est_legitime_asymetrie(self):
        # « 2026\\Photos Floflo » contient de vraies photos de 2014 : l'EXIF a
        # raison contre le dossier d'import. Un garde-fou symetrique aurait
        # detruit ces 20 corrections en sauvant les 12 mauvaises.
        k = P + '\\2026\\Photos Floflo\\IMG_0042.jpg'
        v = M.classer(k, epoch(2014))
        self.assertEqual(v['statut'], 'anterieure')
        self.assertEqual(v['ecart'], -12)

    def test_tolerance_un_an_le_reveillon(self):
        k = P + '\\2019\\2019 Voyage\\IMG_1.jpg'
        self.assertEqual(M.classer(k, epoch(2020, 1, 1))['statut'], 'coherente')

    def test_deux_ans_au_dela_bascule(self):
        k = P + '\\2019\\2019 Voyage\\IMG_1.jpg'
        self.assertEqual(M.classer(k, epoch(2021, 1, 1))['statut'], 'scan_presume')

    def test_plage_de_dossiers_compare_au_MAX(self):
        # « Photos 2005-2010\\2008 » : comparer a la seule plus ancienne
        # ferait reculer la photo de trois ans.
        k = P + '\\Photos 2005-2010\\2008\\IMG_1.jpg'
        self.assertEqual(M.classer(k, epoch(2010))['statut'], 'coherente')
        self.assertEqual(M.classer(k, epoch(2005))['statut'], 'coherente')

    def test_sans_annee_dans_le_dossier_est_un_angle_mort_pas_un_zero(self):
        self.assertEqual(M.classer(P + '\\Divers\\a.jpg', epoch(2007))['statut'],
                         'sans_repere')

    def test_sans_taken(self):
        k = P + '\\1990\\a.jpg'
        self.assertEqual(M.classer(k, None)['statut'], 'sans_taken')

    def test_le_NOM_de_fichier_n_est_pas_une_annee_de_dossier(self):
        # « 119-1908_IMG.JPG » dans un dossier 2002 : sans cette regle, min()
        # reculait la photo de 94 ans (mesure du 14/08).
        k = P + '\\2002\\119-1908_IMG.JPG'
        v = M.classer(k, epoch(2002))
        self.assertEqual(v['annees_chemin'], (2002,))
        self.assertEqual(v['statut'], 'coherente')

    def test_cle_nue_sans_dossier(self):
        self.assertEqual(M.classer('1000142356_2026.jpg', epoch(2026))['statut'],
                         'sans_repere')


class TestCheminB(unittest.TestCase):
    """B ne lit QUE le nom et `taken` — jamais le dossier."""

    def test_repli_YYYY0000_avec_taken_est_un_refus(self):
        k = P + '\\Photos Papa\\1990\\1990_Achumani\\19900000_achumani_Markus.jpg'
        self.assertTrue(M.refuse_par_le_garde_fou(k, epoch(2007)))

    def test_date_precise_dans_le_nom_n_est_pas_un_refus(self):
        k = P + '\\2019\\20190614_120000_lausanne.jpg'
        self.assertFalse(M.refuse_par_le_garde_fou(k, epoch(2019)))

    def test_repli_SANS_taken_n_est_pas_un_refus(self):
        # « YYYY0000 » sans date EXIF = simplement une photo sans date : le
        # garde-fou n'a rien refuse, il n'y avait rien a refuser.
        k = P + '\\1990\\19900000_a.jpg'
        self.assertFalse(M.refuse_par_le_garde_fou(k, None))

    def test_nom_brut_n_a_jamais_ete_soumis_au_garde_fou(self):
        k = P + '\\1990\\HK03.jpg'
        self.assertFalse(M.renomme_par_le_plan(k))
        self.assertFalse(M.refuse_par_le_garde_fou(k, epoch(2007)))

    def test_B_ignore_le_dossier(self):
        # meme nom, dossier different : B rend le meme verdict.
        n = '19900000_x.jpg'
        self.assertTrue(M.refuse_par_le_garde_fou(P + '\\1990\\' + n, epoch(2007)))
        self.assertTrue(M.refuse_par_le_garde_fou(P + '\\Divers\\' + n, epoch(2007)))


class TestTrouDuRepliSurLeNom(unittest.TestCase):
    """La limite du garde-fou, trouvee par le DESACCORD des deux chemins :
    quand l'etape 1 refuse `taken`, l'etape 2 lit le NOM de fichier, qui n'est
    soumis a aucun controle. Un scanner qui nomme « 20150810_073417.jpg »
    reinscrit la date que l'etape 1 venait d'ecarter."""

    def test_le_nom_reinscrit_la_meme_annee(self):
        k = P + '\\Photos Papa\\1983\\20150810_073417.jpg'
        self.assertEqual(M.classer(k, epoch(2015, 8, 10))['statut'], 'scan_presume')
        self.assertTrue(M.nom_reintroduit_la_date(k, epoch(2015, 8, 10)))

    def test_un_nom_COHERENT_avec_le_dossier_n_est_pas_le_trou(self):
        # « 19900101 Markus… » dans un dossier 1990 : le garde-fou a refuse le
        # taken de 2008 et le nom a corrige. C'est le repli qui MARCHE.
        k = P + '\\Photos Papa\\1990\\19900101 Markus en el Illimani 1990.jpg'
        self.assertEqual(M.classer(k, epoch(2008))['statut'], 'scan_presume')
        self.assertFalse(M.nom_reintroduit_la_date(k, epoch(2008)))

    def test_un_repli_YYYY0000_n_est_pas_le_trou(self):
        k = P + '\\Photos Papa\\1990\\1990_Achumani\\19900000_a.jpg'
        self.assertFalse(M.nom_reintroduit_la_date(k, epoch(2007)))

    def test_sans_nom_date_ni_taken(self):
        self.assertFalse(M.nom_reintroduit_la_date(P + '\\1990\\HK03.jpg', epoch(2007)))
        self.assertFalse(M.nom_reintroduit_la_date(P + '\\1990\\20070501_a.jpg', None))

    def test_compte_dans_le_rapport(self):
        e = [(P + '\\Photos Papa\\1983\\20150810_073417.jpg', epoch(2015, 8, 10)),
             (P + '\\Photos Papa\\1990\\19900101 x.jpg', epoch(2008))]
        r = M.mesurer(e)
        self.assertEqual(r['suspects'], 2)
        self.assertEqual(len(r['trou_repli_nom']), 1)


class TestNomsPerimes(unittest.TestCase):
    """L'autre bord du desaccord : un nom « YYYY0000 » alors que `taken` est
    aujourd'hui PRECIS et COHERENT. Le garde-fou n'a rien a voir la-dedans --
    la date est arrivee APRES le renommage (tache de fond EXIF), et le plan ne
    regarde plus les fichiers deja renommes."""

    def test_date_arrivee_apres_le_renommage(self):
        k = P + '\\2006\\Cernie aout 2006\\20060000_Mike.jpg'
        r = M.mesurer([(k, epoch(2006, 8, 12))])
        self.assertEqual(r['statuts']['coherente'], 1)
        self.assertEqual(r['noms_perimes'], [k])

    def test_un_VRAI_refus_du_garde_fou_n_est_pas_perime(self):
        k = P + '\\Photos Papa\\1990\\1990_Achumani\\19900000_a.jpg'
        r = M.mesurer([(k, epoch(2007, 5, 1))])
        self.assertEqual(r['suspects'], 1)
        self.assertEqual(r['noms_perimes'], [])

    def test_YYYY0000_SANS_taken_n_est_pas_perime(self):
        # Rien n'est connu : le nom dit la verite disponible.
        r = M.mesurer([(P + '\\1990\\19900000_a.jpg', None)])
        self.assertEqual(r['noms_perimes'], [])


class TestMesurer(unittest.TestCase):

    def setUp(self):
        self.entrees = [
            # 3 scans presumes, renommes, tous vus par A ET par B
            (P + '\\Photos Papa\\1990\\1990_Achumani\\19900000_a.jpg', epoch(2007, 5, 1)),
            (P + '\\Photos Papa\\1990\\1990_Achumani\\19900000_b.jpg', epoch(2007, 5, 1)),
            (P + '\\Photos Papa\\1993\\19930000_c.jpg', epoch(2007, 5, 1)),
            # legitime : anterieure
            (P + '\\2026\\Photos Floflo\\20140101_d.jpg', epoch(2014)),
            # coherente
            (P + '\\2019\\20190614_e.jpg', epoch(2019)),
            # sans repere
            ('nue.jpg', epoch(2026)),
            # sans taken
            (P + '\\1990\\HK03.jpg', None),
        ]

    def test_comptes(self):
        r = M.mesurer(self.entrees)
        self.assertEqual(r['total'], 7)
        self.assertEqual(r['suspects'], 3)
        self.assertEqual(r['statuts']['anterieure'], 1)
        self.assertEqual(r['statuts']['coherente'], 1)
        self.assertEqual(r['statuts']['sans_repere'], 1)
        self.assertEqual(r['statuts']['sans_taken'], 1)

    def test_les_deux_chemins_tombent_sur_le_meme_ensemble(self):
        ac = M.mesurer(self.entrees)['accord']
        self.assertEqual(ac['chemin_a'], 3)
        self.assertEqual(ac['chemin_b'], 3)
        self.assertEqual(ac['communs'], 3)
        self.assertEqual(ac['a_seul'], [])
        self.assertEqual(ac['b_seul'], [])

    def test_un_desaccord_est_VISIBLE_et_non_lisse(self):
        # Un fichier renomme en date PRECISE alors que le dossier le contredit :
        # A le voit, B non. Le rapport doit le montrer, pas l'absorber.
        e = self.entrees + [(P + '\\1990\\20070501_zz.jpg', epoch(2007, 5, 1))]
        ac = M.mesurer(e)['accord']
        self.assertEqual(ac['chemin_a'], 4)
        self.assertEqual(ac['chemin_b'], 3)
        self.assertEqual(len(ac['a_seul']), 1)

    def test_ventilations(self):
        r = M.mesurer(self.entrees)
        self.assertEqual(r['par_annee_de_scan'], {2007: 3})
        self.assertEqual(sum(r['par_ecart_ans'].values()), 3)
        self.assertTrue(all(e > 0 for e in r['par_ecart_ans']))

    def test_rapport_formatable_en_ascii_pur(self):
        txt = M.formater(M.mesurer(self.entrees))
        txt.encode('ascii')          # leve si un caractere multi-octets passe
        self.assertIn('DATE DE SCAN PRESUMEE', txt)

    def test_aucune_mutation_des_entrees(self):
        avant = list(self.entrees)
        M.mesurer(self.entrees)
        self.assertEqual(avant, self.entrees)


class TestRefusDeLaBaseVivante(unittest.TestCase):

    def test_photos_db_est_refuse(self):
        # Invariant du projet : le serveur est l'ecrivain unique.
        with self.assertRaises(SystemExit):
            list(M.lire_entrees('/un/dossier/photos.db'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
