#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc de `auteurs` : regle pure, sans store ni base. Sortie ASCII (console cp1252)."""

import unittest

import auteurs as A

P_MIKE = r'\\NAS\home\Photos\Photos Mike\2021\a.jpg'
P_FLO = r'\\NAS\home\Photos\Photos Flo\2021\b.jpg'
P_RACINE = r'\\NAS\home\Photos\_A TRIER\dump\c.jpg'


class Proprietaire(unittest.TestCase):
    def test_dossier_proprietaire(self):
        self.assertEqual(A.proprietaire_de(P_MIKE), 'Mike')
        self.assertEqual(A.proprietaire_de(P_FLO), 'Flo')
        self.assertEqual(A.proprietaire_de('/nas/Photos/Photos Papa/2005/x.jpg'), 'Papa')

    def test_hors_dossier(self):
        self.assertIsNone(A.proprietaire_de(P_RACINE))
        self.assertIsNone(A.proprietaire_de(r'\\NAS\home\Photos\2021\x.jpg'))
        self.assertIsNone(A.proprietaire_de('photos.jpg'))
        self.assertIsNone(A.proprietaire_de(None))


class Idents(unittest.TestCase):
    def test_aller_retour(self):
        for champ, cle, i in (('faces', P_MIKE, 3), ('exclude', P_FLO, None),
                              ('confirmed', 'a:b:c', None), ('faces', 'x:y', 0)):
            k = A.ident(champ, cle, i)
            c2, cle2, i2, ct = A.lire_ident(k)
            self.assertEqual((c2, cle2, i2 if champ == 'faces' else None, ct),
                             (champ, cle, i if champ == 'faces' else None, False))
        c, cle, i, ct = A.lire_ident(A.ident('exclude', P_FLO) + A.CONTESTE)
        self.assertEqual((c, cle, i, ct), ('exclude', P_FLO, None, True))

    def test_decisions_de(self):
        f = {'faces': [[P_MIKE, 2], ['mal', 'x'], 'bruit'], 'exclude': [P_FLO],
             'confirmed': [P_RACINE, 7]}
        self.assertEqual(A.decisions_de(f), {A.ident('faces', P_MIKE, 2),
                                             A.ident('exclude', P_FLO),
                                             A.ident('confirmed', P_RACINE)})
        self.assertEqual(A.decisions_de(None), set())


class Arbitre(unittest.TestCase):
    def test_le_proprietaire_l_emporte(self):
        self.assertEqual(A.arbitre('Flo', 'Flo', 'Mike'), 'Flo')
        self.assertEqual(A.arbitre('Flo', 'Mike', 'Flo'), 'Flo')

    def test_l_admin_ailleurs(self):
        self.assertEqual(A.arbitre(None, 'Flo', 'Mike'), 'Mike')
        self.assertEqual(A.arbitre('Papa', 'Mike', 'Flo'), 'Mike')

    def test_sinon_l_ancien_reste(self):
        self.assertEqual(A.arbitre(None, 'Flo', 'Papa'), 'Flo')


class Reconcilier(unittest.TestCase):
    def test_migration_tout_a_mike(self):
        f = {'name': 'Zoe', 'faces': [[P_MIKE, 1]], 'exclude': [P_FLO], 'confirmed': []}
        ch = A.reconcilier(f, A.ADMIN)
        self.assertEqual(set(ch), {'auteurs'})
        self.assertEqual(ch['auteurs'], {A.ident('faces', P_MIKE, 1): 'Mike',
                                         A.ident('exclude', P_FLO): 'Mike'})

    def test_idempotent(self):
        f = {'faces': [[P_MIKE, 1]], 'exclude': [P_FLO]}
        f.update(A.reconcilier(f, 'Mike'))
        self.assertEqual(A.reconcilier(f, 'Mike'), {})
        self.assertEqual(A.reconcilier(f, 'Flo'), {}, "un autre auteur ne re-attribue rien")

    def test_decision_annulee_perd_son_auteur(self):
        f = {'exclude': [P_FLO], 'auteurs': {A.ident('exclude', P_FLO): 'Flo',
                                             A.ident('confirmed', P_MIKE): 'Mike'}}
        ch = A.reconcilier(f, 'Mike')
        self.assertEqual(ch['auteurs'], {A.ident('exclude', P_FLO): 'Flo'})

    def test_conteste_survit_a_l_annulation(self):
        f = {'exclude': [], 'auteurs': {A.ident('exclude', P_FLO) + A.CONTESTE: 'Flo'}}
        self.assertEqual(A.reconcilier(f, 'Mike'), {})

    def test_conflit_sur_la_photo_du_proprietaire(self):
        # Flo a exclu SA photo ; Mike la confirme : Flo l'emporte, Mike est conteste.
        f = {'exclude': [P_FLO], 'confirmed': [P_FLO],
             'auteurs': {A.ident('exclude', P_FLO): 'Flo'}}
        ch = A.reconcilier(f, 'Mike')
        self.assertEqual(ch['confirmed'], [])
        self.assertNotIn('exclude', ch)
        self.assertEqual(ch['auteurs'], {A.ident('exclude', P_FLO): 'Flo',
                                         A.ident('confirmed', P_FLO) + A.CONTESTE: 'Mike'})

    def test_conflit_l_admin_gagne_hors_dossier(self):
        # Flo a exclu une photo de la racine ; Mike confirme : l'admin arbitre.
        f = {'exclude': [P_RACINE], 'confirmed': [P_RACINE],
             'auteurs': {A.ident('exclude', P_RACINE): 'Flo'}}
        ch = A.reconcilier(f, 'Mike')
        self.assertEqual(ch['exclude'], [])
        self.assertNotIn('confirmed', ch)
        self.assertEqual(ch['auteurs'], {A.ident('confirmed', P_RACINE): 'Mike',
                                         A.ident('exclude', P_RACINE) + A.CONTESTE: 'Flo'})

    def test_meme_auteur_qui_se_contredit_n_est_pas_un_conflit(self):
        f = {'exclude': [P_FLO], 'confirmed': [P_FLO],
             'auteurs': {A.ident('exclude', P_FLO): 'Mike'}}
        ch = A.reconcilier(f, 'Mike')
        self.assertEqual(set(ch), {'auteurs'})
        self.assertEqual(ch['auteurs'][A.ident('confirmed', P_FLO)], 'Mike')

    def test_ne_mute_pas(self):
        f = {'exclude': [P_FLO], 'confirmed': [P_FLO],
             'auteurs': {A.ident('exclude', P_FLO): 'Flo'}}
        avant = repr(f)
        A.reconcilier(f, 'Mike')
        self.assertEqual(repr(f), avant)

    def test_fiche_non_dict(self):
        self.assertEqual(A.reconcilier(None, 'Mike'), {})
        self.assertEqual(A.reconcilier('x', 'Mike'), {})


class Recler(unittest.TestCase):
    def test_recle_toutes_les_formes(self):
        old, new = P_RACINE, P_MIKE
        a = {A.ident('faces', old, 2): 'Mike', A.ident('exclude', old): 'Flo',
             A.ident('confirmed', old) + A.CONTESTE: 'Papa', A.ident('exclude', P_FLO): 'Flo'}
        out = A.recler(a, old, new)
        self.assertEqual(out, {A.ident('faces', new, 2): 'Mike', A.ident('exclude', new): 'Flo',
                               A.ident('confirmed', new) + A.CONTESTE: 'Papa',
                               A.ident('exclude', P_FLO): 'Flo'})

    def test_rien_a_recler(self):
        self.assertIsNone(A.recler({A.ident('exclude', P_FLO): 'Flo'}, P_MIKE, P_RACINE))
        self.assertIsNone(A.recler({}, 'a', 'b'))
        self.assertIsNone(A.recler(None, 'a', 'b'))
        self.assertIsNone(A.recler({'exclude:a': 'x'}, 'a', 'a'))

    def test_cible_deja_presente_non_ecrasee(self):
        a = {A.ident('exclude', 'a'): 'Flo', A.ident('exclude', 'b'): 'Mike'}
        self.assertEqual(A.recler(a, 'a', 'b'), {A.ident('exclude', 'b'): 'Mike'})


class Garnir(unittest.TestCase):
    class Magasin:
        def __init__(self):
            self.data, self.appels = {}, []

        def set(self, name, entry, save=True):
            self.data[name] = entry
            self.appels.append((name, save))

    def test_le_goulot_attribue(self):
        st = A.garnir(self.Magasin(), lambda: 'Flo')
        pe = {'exclude': [P_FLO]}
        st.set('zoe', pe, save=False)
        self.assertEqual(st.data['zoe']['auteurs'], {A.ident('exclude', P_FLO): 'Flo'})
        self.assertEqual(st.appels, [('zoe', False)])

    def test_le_goulot_arbitre(self):
        st = A.garnir(self.Magasin(), lambda: 'Mike')
        pe = {'exclude': [P_FLO], 'confirmed': [P_FLO],
              'auteurs': {A.ident('exclude', P_FLO): 'Flo'}}
        st.set('zoe', pe)
        self.assertEqual(pe['confirmed'], [], "la photo est a Flo : Mike perd")
        self.assertEqual(pe['auteurs'][A.ident('confirmed', P_FLO) + A.CONTESTE], 'Mike')

    def test_entree_non_dict_passe_telle_quelle(self):
        st = A.garnir(self.Magasin(), lambda: 'Mike')
        st.set('x', 'brut')
        self.assertEqual(st.data['x'], 'brut')


if __name__ == '__main__':
    unittest.main(verbosity=1)
