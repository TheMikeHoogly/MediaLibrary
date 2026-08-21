#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du décomposeur déterministe de requêtes (chantier 14a).

Pur : ni serveur, ni base, ni GPU, ni NAS. Les dates de référence sont
INJECTÉES — un test qui dépend du calendrier ment un 1ᵉʳ janvier.
"""
import time
import unittest

from geocode import sans_accents
import recherche as r


def _epoch(an, mois=1, jour=1, h=12):
    """Epoch LOCAL, comme tous les epochs du projet (`time.mktime`)."""
    return time.mktime((an, mois, jour, h, 0, 0, 0, 0, -1))


class TestExtractionAnnees(unittest.TestCase):

    def test_annee_seule(self):
        p, reste = r.extraire_periode("photos de 2015")
        self.assertEqual((p.an_min, p.an_max), (2015, 2015))
        self.assertEqual(reste, "photos")

    def test_la_preposition_part_avec_la_date(self):
        """« en 2012 » ne doit pas laisser « en » polluer SigLIP."""
        _, reste = r.extraire_periode("Mike au bord du lac en 2012")
        self.assertEqual(reste, "Mike au bord du lac")

    def test_intervalle_entre_et(self):
        p, reste = r.extraire_periode("entre 2010 et 2015 en montagne")
        self.assertEqual((p.an_min, p.an_max), (2010, 2015))
        self.assertEqual(reste, "montagne")

    def test_intervalle_tiret(self):
        p, _ = r.extraire_periode("2010-2015")
        self.assertEqual((p.an_min, p.an_max), (2010, 2015))

    def test_intervalle_a_lenvers(self):
        """« entre 2015 et 2010 » : on ne renvoie pas un intervalle vide."""
        p, _ = r.extraire_periode("entre 2015 et 2010")
        self.assertEqual((p.an_min, p.an_max), (2010, 2015))

    def test_bornes_ouvertes(self):
        for requete, attendu in [("avant 2000", (None, 1999)),
                                 ("apres 2010", (2011, None)),
                                 ("après 2010", (2011, None)),
                                 ("depuis 2015", (2015, None)),
                                 ("jusqu en 2005", (None, 2005))]:
            with self.subTest(requete):
                p, _ = r.extraire_periode(requete)
                self.assertEqual((p.an_min, p.an_max), attendu)

    def test_deux_annees_donnent_leur_enveloppe(self):
        p, reste = r.extraire_periode("Luna en 2015 et 2018")
        self.assertEqual((p.an_min, p.an_max), (2015, 2018))
        self.assertEqual(reste, "Luna", "le « et » orphelin doit disparaitre")

    def test_un_nombre_qui_nest_pas_une_annee(self):
        """1000 marches n'est pas une date : hors bornes, on n'y touche pas."""
        p, reste = r.extraire_periode("les 1000 marches")
        self.assertIsNone(p)
        self.assertEqual(reste, "les 1000 marches")

    def test_le_plancher_est_1900_pas_1990(self):
        """Le plancher 1990 a deja coute 716 photos des annees 80."""
        p, _ = r.extraire_periode("photos de 1985")
        self.assertEqual((p.an_min, p.an_max), (1985, 1985))


class TestExtractionDecennies(unittest.TestCase):

    def test_annees_deux_chiffres(self):
        p, _ = r.extraire_periode("annees 80")
        self.assertEqual((p.an_min, p.an_max), (1980, 1989))

    def test_annees_quatre_chiffres(self):
        p, _ = r.extraire_periode("les années 1990")
        self.assertEqual((p.an_min, p.an_max), (1990, 1999))

    def test_annees_2000(self):
        p, _ = r.extraire_periode("annees 2000")
        self.assertEqual((p.an_min, p.an_max), (2000, 2009))


class TestExtractionMoisSaisonsFetes(unittest.TestCase):

    def test_mois_et_annee(self):
        p, reste = r.extraire_periode("Luna a Sion en decembre 2015")
        self.assertEqual((p.an_min, p.an_max), (2015, 2015))
        self.assertEqual(p.mois, frozenset({12}))
        self.assertEqual(reste, "Luna a Sion")

    def test_mois_accentue(self):
        p, _ = r.extraire_periode("décembre 2018")
        self.assertEqual(p.mois, frozenset({12}))

    def test_mois_seul_toutes_annees(self):
        p, _ = r.extraire_periode("en juillet")
        self.assertEqual(p.mois, frozenset({7}))
        self.assertIsNone(p.an_min)
        self.assertIsNone(p.an_max)

    def test_saison(self):
        p, _ = r.extraire_periode("ete 2015")
        self.assertEqual(p.mois, frozenset({6, 7, 8}))
        self.assertEqual((p.an_min, p.an_max), (2015, 2015))

    def test_hiver_est_a_cheval_et_assume(self):
        p, _ = r.extraire_periode("en hiver")
        self.assertEqual(p.mois, frozenset({12, 1, 2}))

    def test_ete_participe_passe_nest_pas_une_saison(self):
        """« la photo a été prise à Sion » ne parle pas de la saison."""
        p, reste = r.extraire_periode("la photo a ete prise a Sion")
        self.assertIsNone(p)
        self.assertEqual(reste, "la photo a ete prise a Sion")

    def test_jour_et_mois(self):
        p, _ = r.extraire_periode("le 14 aout")
        self.assertEqual(p.jours, frozenset({"08-14"}))

    def test_jour_mois_annee(self):
        p, reste = r.extraire_periode("le 14 aout 2015")
        self.assertEqual(p.jours, frozenset({"08-14"}))
        self.assertEqual((p.an_min, p.an_max), (2015, 2015))
        self.assertEqual(reste, "")

    def test_jour_impossible_retombe_sur_le_mois(self):
        """« 31 fevrier » : aucun jour valide, on garde au moins le mois."""
        p, _ = r.extraire_periode("31 fevrier")
        self.assertEqual(p.mois, frozenset({2}))
        self.assertEqual(p.jours, frozenset())

    def test_noel(self):
        p, reste = r.extraire_periode("photos de Noel a Bremblens")
        self.assertEqual(p.jours, frozenset({"12-24", "12-25"}))
        self.assertEqual(reste, "photos Bremblens")

    def test_noel_avec_annee(self):
        p, _ = r.extraire_periode("Noel 2015")
        self.assertEqual((p.an_min, p.an_max), (2015, 2015))
        self.assertEqual(p.jours, frozenset({"12-24", "12-25"}))

    def test_reveillon_couvre_les_deux_jours(self):
        p, _ = r.extraire_periode("le reveillon")
        self.assertEqual(p.jours, frozenset({"12-31", "01-01"}))


class TestFormulesRelatives(unittest.TestCase):
    """Injectées : un test du calendrier se périme tout seul."""

    def test_cette_annee(self):
        p, _ = r.extraire_periode("cette annee", annee_ref=2026)
        self.assertEqual((p.an_min, p.an_max), (2026, 2026))

    def test_annee_derniere(self):
        p, _ = r.extraire_periode("l annee derniere", annee_ref=2026)
        self.assertEqual((p.an_min, p.an_max), (2025, 2025))

    def test_il_y_a_n_ans(self):
        p, _ = r.extraire_periode("il y a 10 ans", annee_ref=2026)
        self.assertEqual((p.an_min, p.an_max), (2016, 2016))

    def test_il_y_a_trop_dannees(self):
        p, _ = r.extraire_periode("il y a 900 ans", annee_ref=2026)
        self.assertIsNone(p)


class TestAucuneDate(unittest.TestCase):

    def test_requete_sans_date_rendue_intacte(self):
        for requete in ["Luna endormie sur le canape", "vacances",
                        "noir et blanc", "chien qui court"]:
            with self.subTest(requete):
                p, reste = r.extraire_periode(requete)
                self.assertIsNone(p)
                self.assertEqual(reste, requete,
                                 "la requete part ENTIERE a SigLIP")

    def test_requete_vide(self):
        p, reste = r.extraire_periode("")
        self.assertIsNone(p)
        self.assertEqual(reste, "")

    def test_connecteur_loin_dune_date_est_conserve(self):
        """Le nettoyage est chirurgical : « chien et chat » garde son « et »."""
        _, reste = r.extraire_periode("chien et chat en 2015")
        self.assertEqual(reste, "chien et chat")


class TestNormalisation(unittest.TestCase):

    ECHANTILLON = ["Bremblens", "décembre 2015", "été", "İstanbul", "ŒUF",
                   "Noël", "naïve", "çà et là", "", " ", "MAI", "éte"]

    def test_parite_avec_geocode_sans_accents(self):
        """Une seule cle de comparaison dans le projet, verifiee."""
        for s in self.ECHANTILLON:
            with self.subTest(s):
                self.assertEqual(r._normaliser_avec_positions(s)[0],
                                 sans_accents(s))

    def test_positions_valides_meme_quand_la_longueur_change(self):
        """« e + accent combinant » (2 car.) et « İ » (1 → 2) : la carte tient.

        C'est le pari que font `_extraire_noms`/`_extraire_lieux` (longueur
        conservee) ; ici on ne le fait pas — un decalage d'un caractere couperait
        un mot au lieu de lever une erreur.
        """
        for s in self.ECHANTILLON:
            with self.subTest(s):
                norm, position = r._normaliser_avec_positions(s)
                self.assertEqual(len(norm), len(position))
                for i in position:
                    self.assertTrue(0 <= i < len(s))

    def test_date_extraite_dun_texte_a_accent_combinant(self):
        p, reste = r.extraire_periode("éte 2015")
        self.assertEqual((p.an_min, p.an_max), (2015, 2015))
        self.assertEqual(p.mois, frozenset({6, 7, 8}))
        self.assertEqual(reste, "")


class TestPeriode(unittest.TestCase):

    def test_exige_date_precise(self):
        self.assertFalse(r.Periode(2015, 2015).exige_date_precise())
        self.assertTrue(r.Periode(mois=(12,)).exige_date_precise())
        self.assertTrue(r.Periode(jours=("12-25",)).exige_date_precise())

    def test_contient_annee(self):
        p = r.Periode(2010, 2015)
        self.assertTrue(p.contient_annee(2012))
        self.assertFalse(p.contient_annee(2009))
        self.assertFalse(p.contient_annee(2016))
        self.assertFalse(p.contient_annee(0), "0 = annee inconnue, jamais dedans")

    def test_contient_epoch_mois(self):
        p = r.Periode(mois=(12,))
        self.assertTrue(p.contient_epoch(_epoch(1998, 12, 25)))
        self.assertFalse(p.contient_epoch(_epoch(1998, 11, 30)))

    def test_contient_epoch_jour_et_annee(self):
        p = r.Periode(2015, 2015, jours=("08-14",))
        self.assertTrue(p.contient_epoch(_epoch(2015, 8, 14)))
        self.assertFalse(p.contient_epoch(_epoch(2016, 8, 14)))
        self.assertFalse(p.contient_epoch(_epoch(2015, 8, 15)))

    def test_epoch_illisible(self):
        for mauvais in [None, "", "abc", float('nan')]:
            with self.subTest(mauvais):
                self.assertFalse(r.Periode(2015, 2015).contient_epoch(mauvais))


class TestFiltrage(unittest.TestCase):

    def setUp(self):
        # 3 photos precises, 2 datees par le seul DOSSIER, 1 ratee.
        self.entrees = [
            ("a.jpg", {"taken": _epoch(2015, 12, 25)}),
            ("b.jpg", {"taken": _epoch(2015, 7, 4)}),
            ("c.jpg", {"taken": _epoch(2018, 12, 25)}),
            ("d.jpg", {}),                       # annee du dossier = 2015
            ("e.jpg", {}),                       # annee du dossier = 2019
            ("f.jpg", {"failed": True}),
        ]
        self.dossiers = {"d.jpg": 2015, "e.jpg": 2019}
        self.precis = lambda cle, e: e.get("taken")
        self.annee = r.annee_fiable_depuis(
            self.precis, lambda cle: self.dossiers.get(cle, 0))

    def test_annee_inclut_les_photos_datees_par_le_dossier(self):
        """C'est tout l'interet de la precision « annee » : ~29 % du fonds."""
        cles, sans_date = r.filtrer_periode(
            self.entrees, r.Periode(2015, 2015), self.precis, self.annee)
        self.assertEqual(cles, {"a.jpg", "b.jpg", "d.jpg"})
        self.assertEqual(sans_date, 0)

    def test_mois_ecarte_les_photos_sans_date_precise_ET_LES_COMPTE(self):
        """« 2 resultats » ne doit pas se lire « il n'y a que 2 photos »."""
        cles, sans_date = r.filtrer_periode(
            self.entrees, r.Periode(mois=(12,)), self.precis, self.annee)
        self.assertEqual(cles, {"a.jpg", "c.jpg"})
        self.assertEqual(sans_date, 2, "d.jpg et e.jpg n'ont pas de mois")

    def test_entree_ratee_ignoree_sans_etre_comptee(self):
        _, sans_date = r.filtrer_periode(
            self.entrees, r.Periode(2015, 2015), self.precis, self.annee)
        self.assertEqual(sans_date, 0, "une entree `failed` n'est pas une "
                                       "photo sans date")

    def test_jour_precis(self):
        cles, _ = r.filtrer_periode(
            self.entrees, r.Periode(jours=("12-25",)), self.precis, self.annee)
        self.assertEqual(cles, {"a.jpg", "c.jpg"})


class TestAnneeFiable(unittest.TestCase):

    def test_la_date_precise_prime(self):
        lire = r.annee_fiable_depuis(lambda c, e: e.get("taken"),
                                     lambda c: 2020)
        self.assertEqual(lire("x.jpg", {"taken": _epoch(1998, 5, 4)}), 1998)

    def test_repli_sur_lannee_du_dossier(self):
        lire = r.annee_fiable_depuis(lambda c, e: None, lambda c: 2003)
        self.assertEqual(lire("x.jpg", {}), 2003)

    def test_mtime_jamais(self):
        """Le tagging de 2026 reecrit une photo de 1998 : `mtime` ment.

        Si un jour quelqu'un branche `_best_time` ici, ce test tombe.
        """
        lire = r.annee_fiable_depuis(lambda c, e: None, lambda c: 0)
        self.assertEqual(lire("x.jpg", {"mtime": _epoch(2026, 8, 15)}), 0)



class TestTriChronologique(unittest.TestCase):
    """Le tri du cas « aucun mot pour SigLIP » — meme regle de date que le
    FILTRE. Avant le 19/08 il passait par `_best_time`, dont la branche 3 est
    le `mtime` : la photo dont la date est certainement fausse s'affichait en
    TETE."""

    def setUp(self):
        self.dossiers = {"d.jpg": 2015, "e.jpg": 2019}
        self.precis = lambda cle, e: e.get("taken")
        self.annee = r.annee_fiable_depuis(
            self.precis, lambda cle: self.dossiers.get(cle, 0))

    def _trier(self, entrees):
        return r.trier_chronologique(entrees, self.precis, self.annee)

    def test_le_plus_recent_dabord(self):
        cles, _ = self._trier([("a.jpg", {"taken": _epoch(2015, 7, 4)}),
                               ("c.jpg", {"taken": _epoch(2018, 12, 25)}),
                               ("b.jpg", {"taken": _epoch(2015, 12, 25)})])
        self.assertEqual(cles, ["c.jpg", "b.jpg", "a.jpg"])

    def test_une_annee_de_dossier_plus_recente_passe_devant(self):
        """L'annee du dossier CLASSE : elle ne relegue pas la photo."""
        cles, _ = self._trier([("a.jpg", {"taken": _epoch(2015, 12, 25)}),
                               ("e.jpg", {})])           # dossier 2019
        self.assertEqual(cles, ["e.jpg", "a.jpg"])

    def test_a_annee_egale_la_date_precise_passe_devant(self):
        """On ne fabrique pas un 1er janvier : il ferait passer la photo
        devant un 1er janvier REEL (refus du 15/08)."""
        cles, _ = self._trier([("d.jpg", {}),             # dossier 2015 seul
                               ("a.jpg", {"taken": _epoch(2015, 1, 1)})])
        self.assertEqual(cles, ["a.jpg", "d.jpg"])

    def test_mtime_jamais_ET_LA_PHOTO_MUETTE_FINIT_DERNIERE(self):
        """Le defaut corrige : `_best_time` aurait rendu ["z.jpg", ...].

        Si un jour quelqu'un rebranche `_best_time` ici, ce test tombe.
        """
        entrees = [("z.jpg", {"mtime": _epoch(2026, 8, 19)}),   # aucune date
                   ("a.jpg", {"taken": _epoch(2015, 12, 25)}),
                   ("e.jpg", {})]                               # dossier 2019
        cles, sans_date = self._trier(entrees)
        self.assertEqual(cles, ["e.jpg", "a.jpg", "z.jpg"])
        self.assertEqual(sans_date, 1)

    def test_les_sans_date_sont_COMPTES(self):
        """Une protection qui s'annule doit se compter."""
        _, sans_date = self._trier([("y.jpg", {}), ("z.jpg", {}),
                                    ("a.jpg", {"taken": _epoch(2015, 5, 5)})])
        self.assertEqual(sans_date, 2)

    def test_ex_aequo_gardent_lordre_recu(self):
        """Deux fois la meme requete, deux fois la meme page."""
        entrees = [("m.jpg", {}), ("n.jpg", {}), ("o.jpg", {})]
        self.assertEqual(self._trier(entrees)[0], ["m.jpg", "n.jpg", "o.jpg"])
        self.assertEqual(self._trier(entrees[::-1])[0],
                         ["o.jpg", "n.jpg", "m.jpg"])

    def test_aucun_melange_de_types_meme_sans_date(self):
        """`sorted(key=lambda k: _best_time(...) or '')` melangeait `float` et
        `str` : une seule photo sans date faisait tomber la recherche en 500.
        """
        cles, _ = self._trier([("z.jpg", {}),
                               ("a.jpg", {"taken": _epoch(2015, 5, 5)})])
        self.assertEqual(cles, ["a.jpg", "z.jpg"])

    def test_epoch_illisible_retombe_sur_lannee_du_dossier(self):
        cles, sans_date = r.trier_chronologique(
            [("d.jpg", {"taken": "pas un epoch"})],
            lambda c, e: e.get("taken"), self.annee)
        self.assertEqual((cles, sans_date), (["d.jpg"], 0))

    def test_entree_non_dict_toleree(self):
        cles, sans_date = self._trier([("x.jpg", None)])
        self.assertEqual((cles, sans_date), (["x.jpg"], 1))

    def test_le_tri_ne_jette_rien_pas_meme_une_entree_ratee(self):
        """Filtrer est le travail de `filtrer_periode` ; ranger est le sien."""
        cles, _ = self._trier([("f.jpg", {"failed": True}),
                               ("a.jpg", {"taken": _epoch(2015, 5, 5)})])
        self.assertEqual(cles, ["a.jpg", "f.jpg"])


class TestOrdreImpose(unittest.TestCase):
    """Les noms passent AVANT les dates — sinon un prenom se fait manger."""

    def test_un_prenom_mois_survit_sil_est_retire_avant(self):
        # Ce que fait le serveur : _extraire_noms consomme « Mai », et c'est
        # le RESTE qui arrive ici.
        reste_apres_noms = "sur le canape"
        p, reste = r.extraire_periode(reste_apres_noms)
        self.assertIsNone(p)
        self.assertEqual(reste, reste_apres_noms)

    def test_sans_cet_ordre_le_prenom_serait_mange(self):
        """Le danger est REEL — on le documente au lieu de l'oublier."""
        p, _ = r.extraire_periode("Mai sur le canape")
        self.assertEqual(p.mois, frozenset({5}))



class TestJetonEspece(unittest.TestCase):
    """Le 5ᵉ axe est EXPLICITE (forme A) : un jeton, jamais une promotion
    silencieuse d'un mot de la phrase. Le vocabulaire est INJECTÉ — le module
    ne connaît pas les espèces, il reçoit la fonction qui les canonise."""

    @staticmethod
    def canonique(mot):
        return {'chat': 'chat', 'chats': 'chat',
                'mouton': 'mouton'}.get(sans_accents(mot.lower()))

    def test_le_jeton_est_detache_et_le_reste_rendu(self):
        esp, inc, reste = r.extraire_especes('Luna espece:chat en 2015',
                                             self.canonique)
        self.assertEqual((esp, inc, reste), (['chat'], [], 'Luna en 2015'))

    def test_pluriel_accent_et_casse(self):
        for q in ('espèce:Chats', 'especes:CHAT', 'espece : chats'):
            esp, inc, _ = r.extraire_especes(q, self.canonique)
            self.assertEqual((esp, inc), (['chat'], []), q)

    def test_un_mot_nu_reste_du_SENS(self):
        # « chat » tapé seul part à SigLIP : c'est tout l'intérêt de la forme A.
        self.assertEqual(r.extraire_especes('un chat sur le canape',
                                            self.canonique),
                         ([], [], 'un chat sur le canape'))

    def test_espece_inconnue_est_RENDUE_pas_ignoree(self):
        # L'ignorer rendrait tout le fonds, et l'utilisateur lirait ce silence
        # comme un accord.
        esp, inc, reste = r.extraire_especes('espece:licorne au bord',
                                             self.canonique)
        self.assertEqual((esp, inc, reste), ([], ['licorne'], 'au bord'))

    def test_deux_jetons_sans_doublon(self):
        esp, _, reste = r.extraire_especes(
            'espece:chat espece:mouton espece:chats', self.canonique)
        self.assertEqual((esp, reste), (['chat', 'mouton'], ''))

    def test_le_jeton_ne_mange_pas_la_date(self):
        esp, _, reste = r.extraire_especes('espece:chat en juin 2018',
                                           self.canonique)
        p, reste2 = r.extraire_periode(reste)
        self.assertEqual(esp, ['chat'])
        self.assertEqual((p.an_min, p.an_max), (2018, 2018))
        self.assertEqual(p.mois, frozenset({6}))
        self.assertEqual(reste2, '')


if __name__ == "__main__":
    unittest.main(verbosity=2)
