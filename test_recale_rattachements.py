#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `recale_rattachements.py`.

Cette regle DEPLACE des decisions humaines. Ce qu'elle refuse compte donc
autant que ce qu'elle repare : les cas ci-dessous fixent les quatre refus
(ecart insuffisant, sous le plancher, deja pris, ambigu), la fusion sans
doublon, et le fait qu'un couple deja juste n'est JAMAIS touche.

Regle pure : ni store, ni base, ni numpy — des scores, une fiche.
Les tests n'impriment rien (l'agent git capture la sortie, 22/08).
"""

import unittest

import recale_rattachements as R


def fiche(faces, nom='Flo', **extra):
    e = {"name": nom, "faces": [list(c) for c in faces]}
    e.update(extra)
    return e


class TestMeilleurVisage(unittest.TestCase):

    def test_rend_l_index_du_meilleur(self):
        self.assertEqual(R.meilleur_visage([0.1, 0.9, 0.4]), (1, 0.9))

    def test_saute_les_visages_sans_vecteur(self):
        self.assertEqual(R.meilleur_visage([None, 0.5]), (1, 0.5))

    def test_aucun_vecteur_ne_designe_personne(self):
        self.assertEqual(R.meilleur_visage([None, None]), (None, None))
        self.assertEqual(R.meilleur_visage([]), (None, None))


class TestRecalage(unittest.TestCase):

    def test_recale_vers_le_visage_de_la_meme_photo(self):
        """Le cas de Mike : Didier designe Laura, sur la meme photo."""
        f = fiche([('a.jpg', 1)])
        champs, rec, refus = R.recaler_fiche(f, {'a.jpg': [0.82, 0.05]})
        self.assertEqual(champs['faces'], [['a.jpg', 0]])
        self.assertEqual((rec[0]["de"], rec[0]["vers"]), (1, 0))
        self.assertEqual(refus, [])
        self.assertEqual(f["faces"], [['a.jpg', 1]])      # rien n'est mute

    def test_un_couple_deja_juste_n_est_pas_touche(self):
        f = fiche([('a.jpg', 0)])
        champs, rec, refus = R.recaler_fiche(f, {'a.jpg': [0.82, 0.05]})
        self.assertEqual(champs, {})
        self.assertEqual((rec, refus), ([], []))

    def test_un_index_hors_bornes_est_recale_et_signale(self):
        f = fiche([('a.jpg', 7)])
        _champs, rec, _ = R.recaler_fiche(f, {'a.jpg': [0.82, 0.05]})
        self.assertEqual(rec[0]["vers"], 0)
        self.assertTrue(rec[0]["hors_bornes"])
        self.assertIsNone(rec[0]["sim"])

    def test_une_photo_inconnue_n_est_jamais_touchee(self):
        """Absente des scores = photo qu'on ne sait pas juger. Ne rien savoir
        n'autorise pas a bouger une decision humaine."""
        f = fiche([('inconnue.jpg', 3)])
        champs, rec, refus = R.recaler_fiche(f, {'a.jpg': [0.9]})
        self.assertEqual((champs, rec, refus), ({}, [], []))

    def test_applique_mute_la_fiche(self):
        f = fiche([('a.jpg', 1)])
        rec, _refus = R.appliquer(f, {'a.jpg': [0.82, 0.05]})
        self.assertEqual(f["faces"], [['a.jpg', 0]])
        self.assertEqual(len(rec), 1)


class TestRefus(unittest.TestCase):

    def test_ecart_insuffisant(self):
        """Deux visages proches ne prouvent rien : trancher au hasard serait
        pire que ne rien faire."""
        f = fiche([('a.jpg', 1)])
        champs, rec, refus = R.recaler_fiche(f, {'a.jpg': [0.80, 0.75]})
        self.assertEqual((champs, rec), ({}, []))
        self.assertEqual(refus[0]["pourquoi"], "ecart_insuffisant")

    def test_sous_le_plancher(self):
        """Le meilleur visage de la photo ne ressemble a personne : ce couple
        releve d'un retrait, pas d'un recalage."""
        f = fiche([('a.jpg', 1)])
        champs, rec, refus = R.recaler_fiche(f, {'a.jpg': [0.22, 0.01]})
        self.assertEqual((champs, rec), ({}, []))
        self.assertEqual(refus[0]["pourquoi"], "sous_le_plancher")

    def test_deja_pris_par_quelqu_un_d_autre(self):
        """Recaler la ferait deux personnes sur un seul visage : un conflit
        muet vaut moins qu'un decalage visible."""
        f = fiche([('a.jpg', 1)])
        champs, rec, refus = R.recaler_fiche(
            f, {'a.jpg': [0.82, 0.05]}, deja_pris={('a.jpg', 0): 'Laura'})
        self.assertEqual((champs, rec), ({}, []))
        self.assertEqual(refus[0]["pourquoi"], "deja_pris")
        self.assertEqual(refus[0]["par"], 'Laura')

    def test_deja_pris_par_soi_meme_n_empeche_rien(self):
        f = fiche([('a.jpg', 1)])
        _champs, rec, _refus = R.recaler_fiche(
            f, {'a.jpg': [0.82, 0.05]}, deja_pris={('a.jpg', 0): 'flo'})
        self.assertEqual(len(rec), 1)

    def test_ambigu_quand_la_fiche_cite_deux_fois_la_photo(self):
        """La personne est detectee deux fois : recaler les deux couples vers
        le meme meilleur visage les ecraserait."""
        f = fiche([('a.jpg', 1), ('a.jpg', 2)])
        champs, rec, refus = R.recaler_fiche(f, {'a.jpg': [0.82, 0.05, 0.06]})
        self.assertEqual((champs, rec), ({}, []))
        self.assertEqual({r["pourquoi"] for r in refus}, {"ambigu"})
        self.assertEqual(len(refus), 2)

    def test_l_ecart_et_le_plancher_sont_reglables(self):
        f = fiche([('a.jpg', 1)])
        _c, rec, _r = R.recaler_fiche(f, {'a.jpg': [0.80, 0.75]}, ecart=0.01)
        self.assertEqual(len(rec), 1)
        _c, rec, _r = R.recaler_fiche(f, {'a.jpg': [0.22, 0.01]}, plancher=0.1)
        self.assertEqual(len(rec), 1)


class TestDoublons(unittest.TestCase):

    def test_le_recalage_qui_tombe_sur_une_entree_existante_fusionne(self):
        """Sinon chaque recalage gonflerait la verite terrain d'un doublon,
        et le compte mentirait dans le sens flatteur."""
        f = fiche([('a.jpg', 0), ('a.jpg', 1)])
        # Deux couples sur la meme photo => ambigu, donc on force un cas net :
        f = {"name": 'Flo', "faces": [['a.jpg', 0], ['b.jpg', 1]]}
        champs, rec, _refus = R.recaler_fiche(
            f, {'b.jpg': [0.05, 0.02, 0.9]})
        self.assertEqual(champs['faces'], [['a.jpg', 0], ['b.jpg', 2]])
        self.assertEqual(rec[0]["vers"], 2)

    def test_fusion_quand_la_cible_est_deja_citee(self):
        f = {"name": 'Flo', "faces": [['b.jpg', 2], ['b.jpg', 1]]}
        # combien['b.jpg'] == 2 => ambigu : la regle refuse, et c'est voulu.
        champs, rec, refus = R.recaler_fiche(f, {'b.jpg': [0.0, 0.1, 0.9]})
        self.assertEqual((champs, rec), ({}, []))
        self.assertEqual({r["pourquoi"] for r in refus}, {"ambigu"})

    def test_un_doublon_preexistant_est_laisse_tel_quel(self):
        """Le retirer ici ferait maigrir la verite terrain sans que ce soit un
        recalage, et le compte mentirait."""
        f = {"name": 'Flo', "faces": [['a.jpg', 0], ['a.jpg', 0]]}
        champs, rec, refus = R.recaler_fiche(f, {'a.jpg': [0.9, 0.1]})
        self.assertEqual((champs, rec, refus), ({}, [], []))


class TestAvatar(unittest.TestCase):

    def test_l_avatar_decale_est_recale(self):
        """Il est DERIVE, mais un avatar decale se VOIT dans /people et dans
        la planche de /tranche."""
        f = fiche([], avatar=['a.jpg', 1])
        champs, _rec, _refus = R.recaler_fiche(f, {'a.jpg': [0.9, 0.05]})
        self.assertEqual(champs['avatar'], ['a.jpg', 0])

    def test_l_avatar_juste_n_est_pas_touche(self):
        f = fiche([], avatar=['a.jpg', 0])
        champs, _rec, _refus = R.recaler_fiche(f, {'a.jpg': [0.9, 0.05]})
        self.assertNotIn('avatar', champs)

    def test_l_avatar_ne_descend_pas_sous_le_plancher(self):
        f = fiche([], avatar=['a.jpg', 1])
        champs, _rec, _refus = R.recaler_fiche(f, {'a.jpg': [0.2, 0.01]})
        self.assertNotIn('avatar', champs)

    def test_l_avatar_ne_compte_pas_comme_une_decision(self):
        f = fiche([], avatar=['a.jpg', 1])
        _champs, rec, _refus = R.recaler_fiche(f, {'a.jpg': [0.9, 0.05]})
        self.assertEqual(rec, [])


class TestFicheAbimee(unittest.TestCase):

    def test_une_fiche_qui_n_en_est_pas_une(self):
        self.assertEqual(R.recaler_fiche(None, {}), ({}, [], []))
        self.assertEqual(R.recaler_fiche({"name": 'Flo'}, {}), ({}, [], []))

    def test_une_entree_illisible_est_recopiee_sans_etre_jugee(self):
        f = {"name": 'Flo', "faces": [['a.jpg', 1], "n importe quoi", None]}
        champs, rec, _refus = R.recaler_fiche(f, {'a.jpg': [0.9, 0.05]})
        self.assertEqual(champs['faces'],
                         [['a.jpg', 0], "n importe quoi", None])
        self.assertEqual(len(rec), 1)


class TestRattachementsPris(unittest.TestCase):

    def test_recense_qui_possede_quel_visage(self):
        pris = R.rattachements_pris([
            {"name": 'Flo', "faces": [['a.jpg', 0]]},
            {"name": 'Laura', "faces": [['a.jpg', 1], ['b.jpg', 0]]},
            {"faces": [['c.jpg', 0]]},                 # sans nom : ignoree
        ])
        self.assertEqual(pris[('a.jpg', 0)], 'Flo')
        self.assertEqual(pris[('a.jpg', 1)], 'Laura')
        self.assertNotIn(('c.jpg', 0), pris)

    def test_le_premier_arrive_garde_le_visage(self):
        pris = R.rattachements_pris([
            {"name": 'Flo', "faces": [['a.jpg', 0]]},
            {"name": 'Laura', "faces": [['a.jpg', 0]]},
        ])
        self.assertEqual(pris[('a.jpg', 0)], 'Flo')


if __name__ == '__main__':
    unittest.main()


class TestPhotosCitees(unittest.TestCase):

    def test_rend_les_photos_de_faces_et_de_l_avatar(self):
        f = fiche([('a.jpg', 0), ('b.jpg', 2)], avatar=['c.jpg', 1])
        self.assertEqual(R.photos_citees(f), {'a.jpg', 'b.jpg', 'c.jpg'})

    def test_une_fiche_vide_ne_cite_rien(self):
        self.assertEqual(R.photos_citees({}), set())
        self.assertEqual(R.photos_citees(None), set())
