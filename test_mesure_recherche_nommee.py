#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_recherche_nommee` — l'ARITHMÉTIQUE du banc, pas le serveur.

Ce qui se teste ici, c'est ce qui pourrait mentir sans qu'on le voie : une
soustraction qui rend 0 au lieu de « je ne sais pas », un contrôle de modèle
qui approuve une mesure absente, un verdict qui change de bord parce que le
seuil a bougé après coup. Les requêtes, elles, ne se testent pas en bocal :
c'est le serveur vivant qui en juge, par le canal des bancs.
"""
import io
import unittest

import mesure_recherche_nommee as m


class TestResume(unittest.TestCase):
    def test_serie_vide_ne_rend_pas_des_zeros(self):
        """Zéro se lit « instantané ». L'absence doit se lire « inconnu »."""
        r = m.resume([])
        self.assertEqual(r['n'], 0)
        self.assertIsNone(r['min'])
        self.assertIsNone(r['med'])

    def test_min_med_max(self):
        r = m.resume([10, 30, 20, 100, 20])
        self.assertEqual((r['n'], r['min'], r['med'], r['max']),
                         (5, 10.0, 20.0, 100.0))


class TestChoisirNoms(unittest.TestCase):
    NOMS = [{'nom': 'Florine', 'n': 5909}, {'nom': 'Mike', 'n': 5566},
            {'nom': 'Mathilde', 'n': 110}, {'nom': 'Inti', 'n': 3},
            {'nom': 'Fantome', 'n': 0}]

    def test_prend_le_plus_lourd_et_les_deux_plus_rares(self):
        lourd, rare, autre = m.choisir_noms(self.NOMS)
        self.assertEqual(lourd['nom'], 'Florine')
        self.assertEqual(rare['nom'], 'Inti')
        self.assertEqual(autre['nom'], 'Mathilde')

    def test_un_nom_a_zero_photo_est_ecarte(self):
        """Il passerait `_extraire_noms`, mais la requête ne ressemblerait à
        rien de réel — et le rare sert à mesurer une VRAIE recherche."""
        _, rare, autre = m.choisir_noms(self.NOMS)
        self.assertNotEqual(rare['nom'], 'Fantome')
        self.assertNotEqual(autre['nom'], 'Fantome')

    def test_liste_vide_ou_inutilisable(self):
        self.assertEqual(m.choisir_noms([]), (None, None, None))
        self.assertEqual(m.choisir_noms([{'nom': '', 'n': 9},
                                         {'nom': 'X', 'n': 0}]),
                         (None, None, None))

    def test_un_seul_nom_utile_ne_fabrique_pas_de_second(self):
        lourd, rare, autre = m.choisir_noms([{'nom': 'Seul', 'n': 4}])
        self.assertEqual(lourd['nom'], 'Seul')
        self.assertIsNone(rare)
        self.assertIsNone(autre)


class TestAttribuer(unittest.TestCase):
    def _mes(self, **kw):
        return {k: {'med': v} for k, v in kw.items()}

    def test_les_trois_differences(self):
        a = m.attribuer(self._mes(plancher=5, rare_n1=105, gros_n1=180,
                                  gros_n1500=430, noms=95))
        self.assertAlmostEqual(a['fixe_filtre_nomme'], 100)
        self.assertAlmostEqual(a['tri_des_candidats'], 75)
        self.assertAlmostEqual(a['rendu_1500'], 250)
        self.assertAlmostEqual(a['total_utilisateur'], 430)
        self.assertAlmostEqual(a['noms_autocompletion'], 90)

    def test_une_etape_manquante_rend_None_jamais_zero(self):
        """Un 0 dans un rapport se lit « gratuit », et c'est un mensonge."""
        a = m.attribuer(self._mes(plancher=5))
        self.assertIsNone(a['fixe_filtre_nomme'])
        self.assertIsNone(a['tri_des_candidats'])


class TestControleDuModele(unittest.TestCase):
    def test_deux_noms_au_meme_prix_valident_le_balayage_unique(self):
        tenu, dit = m.controle_du_modele({'rare_n1': {'med': 100},
                                          'deux_n1': {'med': 108}})
        self.assertTrue(tenu)
        self.assertIn('UNIQUE', dit)

    def test_deux_noms_deux_fois_plus_chers_font_tomber_le_modele(self):
        tenu, dit = m.controle_du_modele({'rare_n1': {'med': 100},
                                          'deux_n1': {'med': 205}})
        self.assertFalse(tenu)
        self.assertIn('PAS unique', dit)

    def test_une_mesure_absente_n_est_pas_un_accord(self):
        """L'ignorance doit se lire « je ne sais pas », jamais « c'est bon »."""
        tenu, _ = m.controle_du_modele({'rare_n1': {'med': 100}})
        self.assertIsNone(tenu)
        tenu, _ = m.controle_du_modele({})
        self.assertIsNone(tenu)

    def test_un_denominateur_nul_ne_fait_pas_exploser_le_banc(self):
        tenu, dit = m.controle_du_modele({'rare_n1': {'med': 0},
                                          'deux_n1': {'med': 0}})
        self.assertIsNone(tenu)
        self.assertIn('impossible', dit)


class TestVerdict(unittest.TestCase):
    def test_les_quatre_bords_du_seuil_ecrit_d_avance(self):
        self.assertEqual(m.verdict(None)[0], 'inconnu')
        self.assertEqual(m.verdict(0.2)[0], 'suspect')
        self.assertEqual(m.verdict(m.SEUIL_NEGLIGEABLE_MS - 1)[0], 'classer')
        self.assertEqual(m.verdict(m.SEUIL_NEGLIGEABLE_MS)[0], 'mineur')
        self.assertEqual(m.verdict(m.SEUIL_JUSTIFIE_MS - 1)[0], 'mineur')
        self.assertEqual(m.verdict(m.SEUIL_JUSTIFIE_MS)[0], 'justifie')

    def test_un_cout_quasi_nul_est_une_ALARME_pas_un_succes(self):
        """Méthode du projet : deux bancs ne mesuraient pas ce qu'ils
        prétendaient, et c'est leur score parfait qui l'a révélé."""
        code, dit = m.verdict(0.4)
        self.assertEqual(code, 'suspect')
        self.assertIn('ALARME', dit)

    def test_le_seuil_est_une_CONSTANTE_du_module(self):
        """Un seuil qu'on choisit après avoir vu le chiffre n'est pas un
        seuil. Il est lisible, donc opposable."""
        self.assertEqual((m.SEUIL_NEGLIGEABLE_MS, m.SEUIL_JUSTIFIE_MS),
                         (50.0, 200.0))



class TestVerdictAutocompletion(unittest.TestCase):
    """`/api/names` est mis en cache depuis le 24/08 : son coût n'est plus un
    seul nombre. Un banc qui n'en mesure qu'un se trompe deux fois — il crie
    à l'alarme sur un chiffre expliqué, et il tait le prix réellement payé
    quand le cache vient d'expirer."""

    def test_chaud_quasi_nul_avec_un_froid_REEL_est_explique_pas_suspect(self):
        code, dit = m.verdict_autocompletion(290.0, 2.0)
        self.assertEqual(code, 'classer')
        self.assertIn('cache', dit)

    def test_un_FROID_quasi_nul_reste_une_ALARME(self):
        """43 000 entrees ne se balaient pas pour rien, meme une fois."""
        code, dit = m.verdict_autocompletion(0.3, 0.2)
        self.assertEqual(code, 'suspect')
        self.assertIn('ALARME', dit)

    def test_les_deux_chers_restent_un_chantier(self):
        code, _dit = m.verdict_autocompletion(360.0, 355.0)
        self.assertEqual(code, 'justifie')

    def test_une_mesure_absente_n_est_pas_un_accord(self):
        self.assertEqual(m.verdict_autocompletion(None, 2.0)[0], 'inconnu')
        self.assertEqual(m.verdict_autocompletion(290.0, None)[0], 'inconnu')

    def test_le_prix_du_premier_appel_est_DIT_pas_seulement_le_chaud(self):
        """Ce qui est payé après chaque expiration ne doit pas disparaître
        derrière la médiane."""
        _code, dit = m.verdict_autocompletion(290.0, 2.0)
        self.assertIn('290', dit)
        self.assertIn('2', dit)


class TestAttribuerFroidEtChaud(unittest.TestCase):

    def test_le_premier_appel_et_les_suivants_sont_SEPARES(self):
        a = m.attribuer({'plancher': {'med': 1.0},
                         'noms': {'med': 3.0},
                         'noms_froid': {'med': 291.0},
                         'noms_chaud': {'med': 3.0}})
        self.assertAlmostEqual(a['noms_premier_appel'], 290.0)
        self.assertAlmostEqual(a['noms_autocompletion'], 2.0)

    def test_sans_les_deux_series_on_ne_devine_pas(self):
        a = m.attribuer({'plancher': {'med': 1.0}, 'noms': {'med': 3.0}})
        self.assertIsNone(a['noms_premier_appel'])


class TestLien(unittest.TestCase):
    def test_un_nom_a_espace_ou_accent_est_encode(self):
        u = m.lien('http://127.0.0.1:8080', '/api/search',
                   q='Stéphane Plouvin', n=1)
        self.assertIn('q=St%C3%A9phane+Plouvin', u)
        self.assertIn('n=1', u)

    def test_sans_parametre(self):
        self.assertEqual(m.lien('http://x:8080/', '/api/serveur'),
                         'http://x:8080/api/serveur')


class TestRapport(unittest.TestCase):
    def test_un_rapport_incomplet_s_imprime_sans_tomber(self):
        s = io.StringIO()
        m.imprimer({'tours': 3, 'mesures': {}, 'serveur': {},
                    'noms': {'connus': 0},
                    'erreurs': ['aucun nom exploitable']}, s)
        self.assertIn('aucun nom exploitable', s.getvalue())

    def test_le_rapport_DIT_quand_le_controle_est_tombe(self):
        """Un verdict posé sur une soustraction non validée doit porter son
        avertissement, sinon il se lit comme une conclusion."""
        s = io.StringIO()
        m.imprimer({'tours': 5, 'serveur': {}, 'noms': {'connus': 3},
                    'mesures': {'plancher': m.resume([5, 5, 5])},
                    'totaux': {},
                    'attribution': {'fixe_filtre_nomme': 300,
                                    'tri_des_candidats': None,
                                    'rendu_1500': None,
                                    'total_utilisateur': None,
                                    'noms_autocompletion': None},
                    'controle': {'tenu': False, 'dit': 'pas unique'},
                    'verdict': {'code': 'justifie', 'dit': 'chantier'}}, s)
        texte = s.getvalue()
        self.assertIn('TOMBE', texte)
        self.assertIn('non validee', texte)

    def test_une_valeur_absente_s_imprime_en_tiret_pas_en_zero(self):
        s = io.StringIO()
        m.imprimer({'tours': 3, 'serveur': {}, 'noms': {'connus': 1},
                    'mesures': {'plancher': m.resume([1, 2, 3])}, 'totaux': {},
                    'attribution': {'fixe_filtre_nomme': None,
                                    'tri_des_candidats': None,
                                    'rendu_1500': None,
                                    'total_utilisateur': None,
                                    'noms_autocompletion': None},
                    'controle': {'tenu': None, 'dit': 'x'},
                    'verdict': {'code': 'inconnu', 'dit': 'y'}}, s)
        self.assertIn('—', s.getvalue())
        self.assertNotIn('     0 ms', s.getvalue())


class TestMain(unittest.TestCase):
    def test_moins_de_trois_tours_est_refuse(self):
        """Une médiane sur deux tours n'est pas une médiane."""
        err = io.StringIO()
        vrai = m.sys.stderr
        m.sys.stderr = err
        try:
            code = m.main(['--tours', '2'])
        finally:
            m.sys.stderr = vrai
        self.assertEqual(code, 2)
        self.assertIn('3 au minimum', err.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
