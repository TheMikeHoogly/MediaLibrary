#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc de `visibilite` : la regle, la vue, le branchement au magasin.
Sortie ASCII (console cp1252). Aucun `import server` (photos.db)."""

import threading
import unittest

import visibilite as V

MIKE_PUB = r'\\NAS\home\Photos\Photos Mike\2021\a.jpg'
MIKE_PRIV = r'\\NAS\home\Photos\Photos Mike\PRIVE\2021\b.jpg'
FLO_PRIV = r'\\NAS\home\Photos\Photos Flo\prive\c.jpg'
RACINE_PRIV = r'\\NAS\home\Photos\_A TRIER\PRIVE\d.jpg'
RACINE = r'\\NAS\home\Photos\_Uploads\e.jpg'


class Regle(unittest.TestCase):
    def test_prive_se_lit_dans_le_chemin(self):
        self.assertTrue(V.est_prive(MIKE_PRIV))
        self.assertTrue(V.est_prive(FLO_PRIV))          # casse indifferente
        self.assertFalse(V.est_prive(MIKE_PUB))
        self.assertFalse(V.est_prive(r'\\NAS\Photos\Photos Mike\PRIVEE\x.jpg'))
        self.assertFalse(V.est_prive(None))

    def test_le_partage_par_dossier(self):
        for u in (None, 'Mike', 'Flo', 'Papa'):
            self.assertTrue(V.visible(MIKE_PUB, u), u)
            self.assertTrue(V.visible(RACINE, u), u)

    def test_le_prive_n_est_qu_a_son_proprietaire(self):
        self.assertTrue(V.visible(MIKE_PRIV, 'Mike'))
        self.assertFalse(V.visible(MIKE_PRIV, 'Flo'))
        self.assertTrue(V.visible(FLO_PRIV, 'Flo'))
        self.assertFalse(V.visible(FLO_PRIV, 'Mike'))    # l'admin n'est pas un passe-partout
        self.assertFalse(V.visible(FLO_PRIV, 'Papa'))

    def test_le_prive_sans_proprietaire_est_a_l_admin(self):
        self.assertTrue(V.visible(RACINE_PRIV, 'Mike'))
        self.assertFalse(V.visible(RACINE_PRIV, 'Flo'))

    def test_les_fils_de_fond_voient_tout(self):
        for c in (MIKE_PRIV, FLO_PRIV, RACINE_PRIV):
            self.assertTrue(V.visible(c, None))
        self.assertIsNone(V.filtre(None))


class Ecriture(unittest.TestCase):
    """Etape 5 : chacun n'efface (ne renomme, ne deplace) que ses photos."""

    def test_le_proprietaire_ecrit_chez_lui(self):
        self.assertTrue(V.peut_ecrire(MIKE_PUB, 'Mike'))
        self.assertTrue(V.peut_ecrire(MIKE_PRIV, 'Mike'))
        self.assertTrue(V.peut_ecrire(FLO_PRIV, 'Flo'))
        self.assertTrue(V.peut_ecrire(r'\\NAS\home\Photos\Photos Flo\2020\f.jpg', 'Flo'))

    def test_une_photo_partagee_se_voit_mais_ne_se_touche_pas(self):
        self.assertTrue(V.visible(MIKE_PUB, 'Flo'))
        self.assertFalse(V.peut_ecrire(MIKE_PUB, 'Flo'))
        self.assertFalse(V.peut_ecrire(MIKE_PUB, 'Papa'))
        code, msg = V.refus_ecriture(MIKE_PUB, 'Flo')
        self.assertEqual(code, 403)
        self.assertIn('Mike', msg)

    def test_l_admin_ecrit_partout_ou_il_voit(self):
        self.assertTrue(V.peut_ecrire(RACINE, 'Mike'))
        self.assertTrue(V.peut_ecrire(RACINE_PRIV, 'Mike'))
        self.assertTrue(V.peut_ecrire(r'\\NAS\home\Photos\Photos Flo\2020\f.jpg', 'Mike'))
        self.assertFalse(V.peut_ecrire(FLO_PRIV, 'Mike'))     # pas un passe-partout
        self.assertEqual(V.refus_ecriture(FLO_PRIV, 'Mike'), (404, 'Fichier introuvable.'))

    def test_hors_dossier_proprietaire_seul_l_admin(self):
        self.assertFalse(V.peut_ecrire(RACINE, 'Flo'))
        code, msg = V.refus_ecriture(RACINE, 'Flo')
        self.assertEqual(code, 403)
        self.assertIn('admin', msg)

    def test_l_invisible_est_introuvable_jamais_interdit(self):
        self.assertFalse(V.peut_ecrire(MIKE_PRIV, 'Flo'))
        self.assertEqual(V.refus_ecriture(MIKE_PRIV, 'Flo'), (404, 'Fichier introuvable.'))

    def test_les_fils_de_fond_ecrivent_tout(self):
        for c in (MIKE_PUB, MIKE_PRIV, FLO_PRIV, RACINE_PRIV, RACINE):
            self.assertTrue(V.peut_ecrire(c, None), c)
            self.assertIsNone(V.refus_ecriture(c, None), c)

    def test_permis_rend_none(self):
        self.assertIsNone(V.refus_ecriture(MIKE_PUB, 'Mike'))


class Vue(unittest.TestCase):
    D = {MIKE_PUB: {'kw_fr': ['personne:Flo']}, MIKE_PRIV: {'kw_fr': ['personne:Flo']},
         FLO_PRIV: {'kw_fr': ['personne:Mike']}}

    def test_un_compteur_qui_ne_fuit_pas(self):
        v = V.VueFiltree(self.D, V.filtre('Flo'))
        self.assertEqual(len(v), 2)
        self.assertEqual(set(v), {MIKE_PUB, FLO_PRIV})
        self.assertNotIn(MIKE_PRIV, v)
        self.assertIsNone(v.get(MIKE_PRIV))
        self.assertEqual(v.get(MIKE_PRIV, 'x'), 'x')
        with self.assertRaises(KeyError):
            v[MIKE_PRIV]
        self.assertEqual(len(v.items()), 2)
        self.assertEqual(len(v.values()), 2)
        self.assertEqual(sorted(v.keys()), sorted([MIKE_PUB, FLO_PRIV]))
        self.assertEqual(set(v.copy()), {MIKE_PUB, FLO_PRIV})

    def test_lecture_seule(self):
        v = V.VueFiltree(self.D, V.filtre('Flo'))
        with self.assertRaises(TypeError):
            v[MIKE_PUB] = {}

    def test_la_fiche_ne_cite_pas_l_invisible(self):
        f = {'name': 'Flo', 'faces': [[MIKE_PUB, 0], [MIKE_PRIV, 2], 'bruit'],
             'exclude': [MIKE_PRIV, RACINE], 'confirmed': [MIKE_PUB],
             'avatar': [MIKE_PRIV, 2], 'auteurs': {'faces:%s:2' % MIKE_PRIV: 'Mike'}}
        g = V.filtrer_fiche(f, V.filtre('Flo'))
        self.assertEqual(g['faces'], [[MIKE_PUB, 0], 'bruit'])
        self.assertEqual(g['exclude'], [RACINE])
        self.assertEqual(g['confirmed'], [MIKE_PUB])
        self.assertIsNone(g['avatar'])
        self.assertIs(g['auteurs'], f['auteurs'])
        # l'original n'a pas bouge
        self.assertEqual(len(f['faces']), 3)
        self.assertEqual(f['avatar'], [MIKE_PRIV, 2])
        # rien a cacher -> la meme fiche, pas une copie
        h = {'faces': [[MIKE_PUB, 0]], 'avatar': [MIKE_PUB, 0]}
        self.assertIs(V.filtrer_fiche(h, V.filtre('Flo')), h)
        self.assertEqual(V.filtrer_fiche('bruit', V.filtre('Flo')), 'bruit')

    def test_vue_par_nom(self):
        P = {'flo': {'name': 'Flo', 'faces': [[MIKE_PRIV, 1]], 'avatar': [MIKE_PRIV, 1]}}
        v = V.VueFiches(P, V.filtre('Flo'))
        self.assertEqual(len(v), 1)
        self.assertIn('flo', v)
        self.assertEqual(v['flo']['faces'], [])
        self.assertIsNone(v.get('flo')['avatar'])
        self.assertIsNone(v.get('zzz'))
        self.assertEqual([k for k, _ in v.items()], ['flo'])


class Magasin:
    """Un magasin minimal, comme `TagStore` : `.data` est un attribut."""
    def __init__(self, d):
        self.lock = threading.Lock()
        self.data = d

    def set(self, k, e):
        with self.lock:
            self.data[k] = e

    def get(self, k):
        return self.data.get(k)

    def has(self, k):
        return bool(self.data.get(k))


class MagasinPropriete:
    """Comme `SqliteStore` : `.data` est une propriete avec setter, et
    `get`/`has` lisent le dict en direct."""
    def __init__(self, d):
        self._d = d

    def get(self, k):
        return self._d.get(k)

    def has(self, k):
        return bool(self._d.get(k))

    @property
    def data(self):
        return self._d

    @data.setter
    def data(self, v):
        self._d.clear()
        self._d.update(v)


class Branchement(unittest.TestCase):
    def _cas(self, fabrique):
        courant = threading.local()
        st = fabrique({MIKE_PUB: {}, MIKE_PRIV: {}})
        V.brancher(st, lambda: getattr(courant, 'nom', None))
        # fil de fond : tout, et le vrai dict (ecriture possible)
        self.assertEqual(len(st.data), 2)
        st.data[RACINE] = {}
        self.assertEqual(len(st.data), 3)
        # admin : tout ici (rien n'est le PRIVE d'un autre), mais a travers la vue
        courant.nom = 'Mike'
        self.assertEqual(len(st.data), 3)
        self.assertNotIsInstance(st.data, dict)
        # Flo : la vue
        courant.nom = 'Flo'
        self.assertEqual(len(st.data), 2)
        self.assertNotIn(MIKE_PRIV, st.data)
        self.assertIsNone(st.data.get(MIKE_PRIV))
        self.assertEqual(set(st.data), {MIKE_PUB, RACINE})
        # l'ecriture par en dessous garde son chemin d'origine
        courant.nom = None
        st.data = {FLO_PRIV: {}}
        self.assertEqual(set(st.data), {FLO_PRIV})
        courant.nom = 'Mike'
        self.assertEqual(len(st.data), 0)     # le PRIVE de Flo : pas pour l'admin
        courant.nom = 'Flo'
        self.assertEqual(len(st.data), 1)
        # `get`/`has` suivent la vue, meme si le magasin lit son dict en direct
        courant.nom = 'Mike'
        self.assertIsNone(st.get(FLO_PRIV))
        self.assertFalse(st.has(FLO_PRIV))
        courant.nom = 'Flo'
        self.assertEqual(st.get(FLO_PRIV), {})
        courant.nom = None
        self.assertEqual(st.get(FLO_PRIV), {})

    def test_attribut(self):
        self._cas(Magasin)

    def test_propriete(self):
        self._cas(MagasinPropriete)

    def test_par_nom(self):
        courant = threading.local()
        st = V.brancher(Magasin({'flo': {'name': 'Flo', 'avatar': [MIKE_PRIV, 0],
                                         'faces': [[MIKE_PRIV, 0], [MIKE_PUB, 1]]}}),
                        lambda: getattr(courant, 'nom', None), par_nom=True)
        courant.nom = 'Papa'
        self.assertEqual(len(st.data), 1)
        self.assertEqual(st.data['flo']['faces'], [[MIKE_PUB, 1]])
        self.assertIsNone(st.data['flo']['avatar'])
        courant.nom = 'Mike'
        self.assertEqual(st.data['flo']['avatar'], [MIKE_PRIV, 0])

    def test_un_fil_ne_voit_pas_l_utilisateur_d_un_autre(self):
        courant = threading.local()
        st = V.brancher(Magasin({MIKE_PRIV: {}}), lambda: getattr(courant, 'nom', None))
        courant.nom = 'Flo'
        vu = {}

        def fond():
            vu['n'] = len(st.data)
        t = threading.Thread(target=fond); t.start(); t.join()
        self.assertEqual(vu['n'], 1)
        self.assertEqual(len(st.data), 0)


class MagasinReel(unittest.TestCase):
    """Le vrai `SqliteStore` (celui de la prod), sur une base temporaire :
    le branchement doit tenir sur SA propriete `data` et SES `get`/`has`."""

    def test_sqlite_store(self):
        import tempfile
        from pathlib import Path
        from store_sqlite import SqliteStore
        courant = threading.local()
        with tempfile.TemporaryDirectory() as tmp:
            st = SqliteStore(Path(tmp) / 'v.db', 'tags')
            try:
                self._scenario(st, courant)
            finally:
                st.close()  # Windows : une base ouverte bloque l'effacement du dossier

    def _scenario(self, st, courant):
        if True:
            st.set(MIKE_PUB, {'kw_fr': ['a']})
            st.set(MIKE_PRIV, {'kw_fr': ['b']})
            V.brancher(st, lambda: getattr(courant, 'nom', None))
            self.assertEqual(type(st).__name__, 'SqliteStore')
            self.assertEqual(len(st.data), 2)
            courant.nom = 'Flo'
            self.assertEqual(len(st.data), 1)
            self.assertIsNone(st.get(MIKE_PRIV))
            self.assertFalse(st.has(MIKE_PRIV))
            self.assertTrue(st.has(MIKE_PUB))
            # l'ecriture par `set` passe sous la vue, meme avec un utilisateur
            st.set(RACINE, {'kw_fr': ['c']})
            self.assertEqual(len(st.data), 2)
            courant.nom = None
            self.assertEqual(len(st.data), 3)
            st.remove_many([MIKE_PRIV])
            self.assertEqual(len(st.data), 2)


class LaCiblePrive(unittest.TestCase):
    """« Rendre privee, c'est deplacer » (17a) : le geste en un clic doit
    savoir OU, et le DIRE quand il n'y a pas de chez-soi."""

    def test_chez_un_proprietaire(self):
        self.assertEqual(
            V.cible_prive('Photos Mike/2016/07 Voyage/x.jpg'),
            ('Photos Mike/PRIVE', None))
        self.assertEqual(V.cible_prive('Photos Flo/Love/a.jpg')[0],
                         'Photos Flo/PRIVE')

    def test_les_deux_separateurs(self):
        self.assertEqual(
            V.cible_prive('Photos Mike\\2016\\x.jpg')[0],
            'Photos Mike/PRIVE')

    def test_deja_privee_refuse_et_dit_pourquoi(self):
        cible, raison = V.cible_prive('Photos Mike/PRIVE/a.jpg')
        self.assertIsNone(cible)
        self.assertIn('deja', raison)

    def test_hors_dossier_proprietaire_refuse(self):
        for rel in ('_A TRIER/b.jpg', '_Uploads/c.jpg', 'd.jpg', ''):
            cible, raison = V.cible_prive(rel)
            self.assertIsNone(cible, rel)
            self.assertTrue(raison)

    def test_la_cible_est_bien_privee_pour_la_regle(self):
        # la boucle se ferme : ce que le geste produit, `est_prive` le voit.
        cible, _ = V.cible_prive('Photos Mike/2016/x.jpg')
        self.assertTrue(V.est_prive(cible + '/x.jpg'))
        self.assertFalse(V.visible(cible + '/x.jpg', 'Flo'))
        self.assertTrue(V.visible(cible + '/x.jpg', 'Mike'))


if __name__ == '__main__':
    unittest.main()
