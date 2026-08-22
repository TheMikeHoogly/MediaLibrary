#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la regle de RETRAIT — le seul geste du projet qui EFFACE une
decision humaine au lieu de la deplacer.

Ce qui est verifie, et pourquoi ce sont ces cas-la
──────────────────────────────────────────────────
1. **Rien ne part sans un verdict EXPLICITE sur ce couple.** Un cas non juge,
   un cas « indecidable », un visage absent des candidats montres : aucun
   geste. Un doute humain n'est pas un feu vert faible, c'est un refus.
2. **Les trois populations ne se melangent jamais.** Retirer / confirmer /
   AJOUTER. Le troisieme est une attribution : le glisser dans un bouton
   nomme « retirer » poserait un nom en douce.
3. **Seul `faces` bouge.** `exclude` et `confirmed` sont keyes par PHOTO, pas
   par visage : ils ne peuvent pas porter un decalage d'index, et les toucher
   effacerait une decision que personne n'a jugee.
4. **Deux applications de suite donnent le meme etat.** Un couple deja parti
   se compte, il ne fait pas echouer le geste : sinon « Appliquer » devient un
   piege.

FUSEAU HORAIRE : sans objet.
"""

import unittest

import retrait_rattachements as R


def cas(person='Flo', key='a.jpg', cites=(0, 1), non_cites=()):
    c = [{"i": i, "sim": 0.5, "cite": True} for i in cites]
    c += [{"i": i, "sim": 0.9, "cite": False} for i in non_cites]
    return {"person": person, "key": key, "visages": 4, "pourquoi": "ambigu",
            "candidats": sorted(c, key=lambda d: d['i'])}


def verdict(k, oui, quoi='juge'):
    return {R.identite(k['key'], k['person']): {"verdict": quoi, "oui": list(oui)}}


class TestPlan(unittest.TestCase):

    def test_le_couple_cite_non_retenu_part(self):
        k = cas()
        p = R.plan_depuis_verdicts([k], verdict(k, [0]))
        self.assertEqual(p['retraits'], [{'person': 'Flo', 'key': 'a.jpg', 'i': 1}])
        self.assertEqual(p['comptes']['confirmes'], 1)

    def test_un_cas_NON_juge_ne_produit_aucun_geste(self):
        k = cas()
        p = R.plan_depuis_verdicts([k], {})
        self.assertEqual(p['retraits'], [])
        self.assertEqual(p['comptes']['non_juges'], 1)

    def test_indecidable_ne_produit_aucun_geste(self):
        """Un doute humain n'est pas un feu vert faible."""
        k = cas()
        p = R.plan_depuis_verdicts([k], verdict(k, [], 'indecidable'))
        self.assertEqual(p['retraits'], [])
        self.assertEqual(p['comptes']['indecidables'], 1)
        self.assertEqual(p['comptes']['a_retirer'], 0)

    def test_aucun_n_est_elle_retire_tous_les_cites(self):
        k = cas()
        p = R.plan_depuis_verdicts([k], verdict(k, []))
        self.assertEqual([r['i'] for r in p['retraits']], [0, 1])
        self.assertEqual(p['comptes']['photos_sans_personne'], 1)

    def test_un_visage_NON_cite_est_un_AJOUT_jamais_un_retrait(self):
        k = cas(non_cites=(7,))
        p = R.plan_depuis_verdicts([k], verdict(k, [0, 1, 7]))
        self.assertEqual(p['retraits'], [])
        self.assertEqual([a['i'] for a in p['ajouts']], [7])
        self.assertEqual(p['comptes']['a_ajouter'], 1)

    def test_un_visage_hors_des_candidats_est_ignore(self):
        """Un verdict ne porte que sur ce qui a ete MONTRE : `oui: [9]` sur un
        cas qui n'offrait que 0 et 1 ne confirme rien — donc les deux cites
        partent, et 9 n'est pas propose en ajout."""
        k = cas()
        p = R.plan_depuis_verdicts([k], verdict(k, [9]))
        self.assertEqual([r['i'] for r in p['retraits']], [0, 1])
        self.assertEqual(p['ajouts'], [])


class TestFiche(unittest.TestCase):

    def fiche(self):
        return {"name": "Flo",
                "faces": [["a.jpg", 0], ["a.jpg", 1], ["b.jpg", 2]],
                "exclude": ["c.jpg"], "confirmed": ["d.jpg"],
                "avatar": ["a.jpg", 1]}

    def test_seul_faces_bouge(self):
        f = self.fiche()
        champs, _b = R.retirer_de_la_fiche(f, [{'key': 'a.jpg', 'i': 1}])
        self.assertEqual(list(champs), ['faces'])
        self.assertEqual(champs['faces'], [["a.jpg", 0], ["b.jpg", 2]])

    def test_exclude_et_confirmed_ne_sont_JAMAIS_touches(self):
        """Ils sont keyes par PHOTO : aucun index ne peut y glisser, et les
        toucher effacerait une decision que personne n'a jugee."""
        f = self.fiche()
        champs, _b = R.retirer_de_la_fiche(f, [{'key': 'c.jpg', 'i': 0},
                                               {'key': 'd.jpg', 'i': 0}])
        self.assertEqual(champs, {})
        self.assertEqual(f['exclude'], ["c.jpg"])
        self.assertEqual(f['confirmed'], ["d.jpg"])

    def test_ne_mute_pas_la_fiche(self):
        f = self.fiche()
        R.retirer_de_la_fiche(f, [{'key': 'a.jpg', 'i': 1}])
        self.assertEqual(len(f['faces']), 3)

    def test_deux_applications_donnent_le_meme_etat(self):
        f = self.fiche()
        champs, b1 = R.retirer_de_la_fiche(f, [{'key': 'a.jpg', 'i': 1}])
        f['faces'] = champs['faces']
        champs2, b2 = R.retirer_de_la_fiche(f, [{'key': 'a.jpg', 'i': 1}])
        self.assertEqual(b1['retires'], 1)
        self.assertEqual(champs2, {})
        self.assertEqual(b2['deja_absents'], 1)

    def test_le_bon_visage_de_la_bonne_photo(self):
        """`[a.jpg, 1]` et `[b.jpg, 1]` sont deux couples differents."""
        f = {"name": "Flo", "faces": [["a.jpg", 1], ["b.jpg", 1]]}
        champs, _b = R.retirer_de_la_fiche(f, [{'key': 'b.jpg', 'i': 1}])
        self.assertEqual(champs['faces'], [["a.jpg", 1]])

    def test_une_fiche_sans_faces_ne_tombe_pas(self):
        champs, b = R.retirer_de_la_fiche({"name": "Flo"},
                                          [{'key': 'a.jpg', 'i': 0}])
        self.assertEqual(champs, {})
        self.assertEqual(b['retires'], 0)


class TestGroupement(unittest.TestCase):

    def test_par_fiche_en_minuscules(self):
        g = R.par_fiche([{'person': 'Res Jordi', 'key': 'a.jpg', 'i': 1},
                         {'person': 'Res Jordi', 'key': 'b.jpg', 'i': 2},
                         {'person': 'Flo', 'key': 'c.jpg', 'i': 0}])
        self.assertEqual(sorted(g), ['flo', 'res jordi'])
        self.assertEqual(len(g['res jordi']), 2)


if __name__ == '__main__':
    unittest.main()
