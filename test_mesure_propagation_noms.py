#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_propagation_noms.py`.

Un banc qui n'a pas de test dit ce qu'il veut : ces cas-ci fixent les quatre
sorts d'un visage, les deux garde-fous humains (`exclude`, « pas un visage »),
le plafond de la file et le REFUS de mesurer sur `photos.db`.

La base d'essai est fabriquée avec le loader de PROD (`store_sqlite`) : le
banc est donc éprouvé sur le même chemin de lecture que la mesure réelle,
vecteurs sortis en BLOB compris.
"""

import base64
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import mesure_propagation_noms as M

DIM = 512

SERVER_FACTICE = """\
CUR_ADD_SIM = 0.40
CUR_ADD_STRONG = 0.55
CUR_FP_SIM = 0.30
CUR_FP_STRONG = 0.20
CUR_MERGE_SIM = 0.55
CUR_MAX_SUGGEST = 400
AUTO_ADD_ENABLE = True
AUTO_ADD_SIM = 0.40
AUTO_ADD_MARGIN = 0.10
CURATOR_INTERVAL = 240
"""


def vecteur(graine, bruit=0.0, base=None):
    """Vecteur 512-d normalisé, reproductible."""
    rng = np.random.default_rng(graine)
    v = rng.normal(size=DIM).astype(np.float32) if base is None else base.copy()
    if bruit:
        v = v + rng.normal(size=DIM).astype(np.float32) * bruit
    return v / np.linalg.norm(v)


def b64(v):
    return base64.b64encode(v.astype(np.float16).tobytes()).decode()


class Base:
    """Fabrique une base d'essai et le `server.py` factice qui la gouverne."""

    def __init__(self, dossier, server_src=SERVER_FACTICE, seuils_txt=None):
        self.dir = Path(dossier)
        (self.dir / 'server.py').write_text(server_src, encoding='utf-8')
        if seuils_txt is not None:
            (self.dir / 'seuils.txt').write_text(seuils_txt, encoding='utf-8')
        self.db = self.dir / 'copie.db'
        from store_sqlite import SqliteStore
        self.tags = SqliteStore(self.db, 'tags')
        self.faces = SqliteStore(self.db, 'faces')
        self.people = SqliteStore(self.db, 'people')

    def personne(self, nom, refs, **extra):
        e = {"name": nom, "refs": [b64(v) for v in refs]}
        e.update(extra)
        self.people.set(nom.lower(), e)

    def photo(self, cle, visages, noms=()):
        self.faces.set(cle, {"faces": visages})
        self.tags.set(cle, {"kw_fr": [f"personne:{n}" for n in noms]})

    def fermer(self):
        """Ecrit ET ferme : sous Windows, un handle SQLite ouvert empeche
        d'effacer le dossier temporaire (13 erreurs le 21/08)."""
        for st in (self.tags, self.faces, self.people):
            st.save()
            st.cx.close()


class TestSeuils(unittest.TestCase):

    def test_lit_les_seuils_sans_importer_server(self):
        with TemporaryDirectory() as d:
            (Path(d) / 'server.py').write_text(SERVER_FACTICE, encoding='utf-8')
            vals, surcharges = M.seuils_de_server(d)
            self.assertEqual(vals['CUR_ADD_SIM'], 0.40)
            self.assertEqual(vals['CUR_MAX_SUGGEST'], 400)
            self.assertTrue(vals['AUTO_ADD_ENABLE'])
            self.assertEqual(surcharges, {})

    def test_seuils_txt_surcharge_comme_la_prod(self):
        with TemporaryDirectory() as d:
            (Path(d) / 'server.py').write_text(SERVER_FACTICE, encoding='utf-8')
            (Path(d) / 'seuils.txt').write_text(
                "# essai\nAUTO_ADD_MARGIN = 0.05\nPAS_UN_SEUIL = 9\n",
                encoding='utf-8')
            vals, surcharges = M.seuils_de_server(d)
            self.assertEqual(vals['AUTO_ADD_MARGIN'], 0.05)
            self.assertEqual(surcharges, {'AUTO_ADD_MARGIN': 0.05})
            self.assertNotIn('PAS_UN_SEUIL', vals)

    def test_un_seuil_disparu_arrete_le_banc(self):
        """Mieux vaut ne rien mesurer que mesurer avec une valeur inventée."""
        with TemporaryDirectory() as d:
            tronque = SERVER_FACTICE.replace("AUTO_ADD_SIM = 0.40\n", "")
            (Path(d) / 'server.py').write_text(tronque, encoding='utf-8')
            with self.assertRaises(SystemExit):
                M.seuils_de_server(d)


class TestRefus(unittest.TestCase):

    def test_refuse_photos_db(self):
        with self.assertRaises(SystemExit):
            M.ouvrir_stores('photos.db')

    def test_base_absente(self):
        with self.assertRaises(SystemExit):
            M.ouvrir_stores('/introuvable/copie.db')


class TestSorts(unittest.TestCase):
    """Les quatre sorts d'un visage, plus les deux garde-fous humains."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        d = self._tmp.name
        self.base = Base(d)
        alice = vecteur(1)
        self.alice = alice
        # Douze références serrées : la signature d'Alice.
        self.base.personne('Alice', [vecteur(100 + i, 0.05, alice) for i in range(12)],
                           exclude=['photo_exclue'])
        proche = vecteur(2, 0.35, alice)          # un sosie : marges serrées
        self.base.personne('Bob', [vecteur(200 + i, 0.05, proche) for i in range(12)])

        v_alice = lambda g: b64(vecteur(g, 0.05, alice))    # noqa: E731
        self.base.photo('photo_gain', [{"emb": v_alice(300)}])
        self.base.photo('photo_deja', [{"emb": v_alice(301)}], noms=['Alice'])
        self.base.photo('photo_exclue', [{"emb": v_alice(302)}])
        self.base.photo('photo_loin', [{"emb": b64(vecteur(999))}])
        self.base.photo('photo_pas_visage',
                        [{"emb": v_alice(303), "pas_visage": True}])
        self.base.photo('photo_inconnu',
                        [{"emb": v_alice(304), "inconnu": True}])
        self.base.photo('photo_sans_vecteur', [{}])
        self.base.fermer()
        self.rap = M.mesurer(str(self.base.db), d, exemples=3, graine=1)

    def tearDown(self):
        self._tmp.cleanup()

    def test_un_visage_franc_est_rattache_tout_seul(self):
        self.assertEqual(self.rap['q1_sorts'].get('auto'), 1)
        self.assertEqual(self.rap['q1_photos_qui_gagnent_un_nom'], 1)

    def test_le_nom_deja_pose_ne_gagne_rien(self):
        self.assertEqual(self.rap['q1_sorts'].get('deja_dit'), 1)

    def test_une_exclusion_humaine_fait_autorite(self):
        self.assertEqual(self.rap['q1_sorts'].get('exclu_par_un_humain'), 1)

    def test_un_visage_sans_voisin_reste_sous_le_seuil(self):
        self.assertEqual(self.rap['q1_sorts'].get('sous_seuil'), 1)

    def test_pas_un_visage_et_inconnu_sont_ecartes(self):
        e = self.rap['matiere']['visages_ecartes']
        self.assertEqual(e.get('pas_un_visage'), 1)
        self.assertEqual(e.get('archive_inconnu'), 1)
        self.assertEqual(e.get('sans_vecteur'), 1)

    def test_les_deux_mesures_ne_portent_pas_le_meme_nom(self):
        d = self.rap['deux_mesures']
        self.assertEqual(d['visage_non_rattache'], d['total_visages_examines'])
        self.assertLess(d['visage_sur_photo_muette'], d['total_visages_examines'])


class TestFile(unittest.TestCase):
    """Marge serrée → la carte va dans la file, pas en automatique."""

    def _mesurer(self, server_src=SERVER_FACTICE):
        d = self._tmp.name
        base = Base(d, server_src=server_src)
        socle = vecteur(1)
        base.personne('Alice', [vecteur(100 + i, 0.05, socle) for i in range(12)])
        # Clara partage EXACTEMENT le socle d'Alice : tout visage proche du
        # socle les départage d'un cheveu — c'est le cas « Ellie / Liam Guhl ».
        base.personne('Clara', [vecteur(100 + i, 0.05, socle) for i in range(12)])
        for n in range(6):
            base.photo(f'p{n}', [{"emb": b64(vecteur(400 + n, 0.05, socle))}])
        base.fermer()
        return M.mesurer(str(base.db), d, exemples=3, graine=1)

    def setUp(self):
        self._tmp = TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_marge_serree_va_dans_la_file(self):
        rap = self._mesurer()
        self.assertEqual(rap['q1_sorts'].get('file'), 6)
        self.assertNotIn('auto', rap['q1_sorts'])
        self.assertEqual(rap['q2_file']['add'], 6)
        self.assertEqual(rap['q2_file']['add_caches_par_le_plafond'], 0)

    def test_deux_signatures_jumelles_proposent_une_fusion(self):
        rap = self._mesurer()
        self.assertEqual(rap['q2_file']['merge'], 1)

    def test_le_plafond_cache_les_ajouts(self):
        """Le tri met `remove` et `merge` AVANT `add` : un plafond bas les mange."""
        rap = self._mesurer(SERVER_FACTICE.replace('CUR_MAX_SUGGEST = 400',
                                                   'CUR_MAX_SUGGEST = 3'))
        q2 = rap['q2_file']
        self.assertEqual(q2['plafond'], 3)
        self.assertEqual(q2['add_visibles'], 3 - q2['merge'])
        self.assertEqual(q2['add_caches_par_le_plafond'],
                         q2['add'] - q2['add_visibles'])


class TestFauxPositif(unittest.TestCase):

    def setUp(self):
        self._tmp = TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_un_nom_pose_sur_un_visage_lointain_est_un_retrait(self):
        d = self._tmp.name
        base = Base(d)
        socle = vecteur(1)
        base.personne('Alice', [vecteur(100 + i, 0.05, socle) for i in range(12)])
        base.photo('faux', [{"emb": b64(vecteur(777))}], noms=['Alice'])
        base.fermer()
        rap = M.mesurer(str(base.db), d, exemples=1, graine=1)
        self.assertEqual(rap['q2_file']['remove'], 1)

    def test_confirme_par_un_humain_ne_revient_jamais(self):
        d = self._tmp.name
        base = Base(d)
        socle = vecteur(1)
        base.personne('Alice', [vecteur(100 + i, 0.05, socle) for i in range(12)],
                      confirmed=['faux'])
        base.photo('faux', [{"emb": b64(vecteur(777))}], noms=['Alice'])
        base.fermer()
        rap = M.mesurer(str(base.db), d, exemples=1, graine=1)
        self.assertEqual(rap['q2_file']['remove'], 0)


class TestCasDeMike(unittest.TestCase):
    """Une photo nommée qui garde un visage non couvert — le cas du chantier 16."""

    def test_le_second_visage_apporte_un_nom_neuf(self):
        with TemporaryDirectory() as d:
            base = Base(d)
            a, b = vecteur(1), vecteur(2)
            base.personne('Florine', [vecteur(100 + i, 0.05, a) for i in range(12)],
                          faces=[['duo', 0]])
            base.personne('Flora', [vecteur(200 + i, 0.05, b) for i in range(12)])
            base.photo('duo', [{"emb": b64(vecteur(300, 0.05, a))},
                               {"emb": b64(vecteur(301, 0.05, b))}],
                       noms=['Florine'])
            base.fermer()
            rap = M.mesurer(str(base.db), d, exemples=1, graine=1)
            q4 = rap['q4_cas_de_mike']
            self.assertEqual(q4['photos_nommees_a_visage_non_couvert'], 1)
            self.assertEqual(q4['qui_gagneraient_un_nom'], 1)
            # UN seul nom neuf posé, et il vient du second visage : Florine
            # est déjà dite (`deja_dit`), donc le gain ne peut être que Flora.
            self.assertEqual(rap['q1_noms_poses'], 1)
            self.assertEqual(rap['q1_sorts'].get('deja_dit'), 1)


class TestRapport(unittest.TestCase):

    def test_le_rapport_s_affiche_sans_exception(self):
        with TemporaryDirectory() as d:
            base = Base(d)
            socle = vecteur(1)
            base.personne('Alice', [vecteur(100 + i, 0.05, socle) for i in range(12)])
            base.photo('p', [{"emb": b64(vecteur(300, 0.05, socle))}])
            base.photo('loin', [{"emb": b64(vecteur(900))}])
            base.fermer()
            texte = M.afficher(M.mesurer(str(base.db), d, exemples=2, graine=1))
            self.assertIn('Q1', texte)
            self.assertIn('Q4', texte)
            self.assertIn('LIMITES DECLAREES', texte)


if __name__ == '__main__':
    unittest.main(verbosity=2)


class TestClesFantomes(unittest.TestCase):
    """Le garde-fou de `build_suggestions` : une proposition dont le fichier
    n'existe pas est ecartee — c'est le cas ARZOPA."""

    def test_resoudre_absolu_et_relatif(self):
        up = Path('/uploads')
        self.assertEqual(M.resoudre('/tmp/x.jpg', up), Path('/tmp/x.jpg'))
        self.assertEqual(M.resoudre('ARZOPA/x.jpg', up), up / 'ARZOPA/x.jpg')

    def test_dossier_uploads_lu_comme_la_prod(self):
        with TemporaryDirectory() as d:
            (Path(d) / 'dossier_uploads.txt').write_text(
                '# commentaire\n"/mnt/photos"\n', encoding='utf-8')
            self.assertEqual(M.dossier_uploads(d), Path('/mnt/photos'))

    def test_sans_fichier_de_config_on_retombe_sur_le_projet(self):
        with TemporaryDirectory() as d:
            self.assertEqual(M.dossier_uploads(d), Path(d))

    def test_une_cle_fantome_ne_gagne_plus_de_photo(self):
        """Le meme fonds, mesure sans puis avec le garde-fou : le gain tombe.

        C'est le resultat du 21/08 en miniature — 3 684 des 3 698 candidats
        pointaient vers un fichier disparu."""
        with TemporaryDirectory() as d:
            base = Base(d)
            socle = vecteur(1)
            base.personne('Alice',
                          [vecteur(100 + i, 0.05, socle) for i in range(12)])
            (Path(d) / 'dossier_uploads.txt').write_text(d, encoding='utf-8')
            (Path(d) / 'vivante.jpg').write_bytes(b'x')
            base.photo('vivante.jpg', [{"emb": b64(vecteur(300, 0.05, socle))}])
            base.photo('fantome.jpg', [{"emb": b64(vecteur(301, 0.05, socle))}])
            base.fermer()
            sans = M.mesurer(str(base.db), d, exemples=2, graine=1)
            avec = M.mesurer(str(base.db), d, exemples=2, graine=1, fichiers=99)
            self.assertEqual(sans['q1_photos_qui_gagnent_un_nom'], 2)
            self.assertEqual(avec['q1_photos_qui_gagnent_un_nom_REELLES'], 1)
            self.assertEqual(avec['fichiers']['cle_fantome'], 1)
            self.assertEqual(avec['fichiers']['fantomes_dans_l_index'], 1)
            self.assertTrue(avec['q3_sur_cles_vivantes'])
