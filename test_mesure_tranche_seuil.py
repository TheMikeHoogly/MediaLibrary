#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_tranche_seuil.py`.

Ce banc décide de ce qu'un humain va juger : s'il tire mal, le chiffre qui en
sortira sera faux sans que rien ne le signale. Ces cas fixent donc les quatre
choses qui peuvent le fausser en silence — les BORNES de la tranche, les
garde-fous humains (`exclude`, nom déjà posé), le caractère UNIFORME et
REPRODUCTIBLE du tirage, et le refus de mesurer sur `photos.db`. Plus la
lecture du verdict : un taux nu sur 30 jugements est une erreur en soi.

La base d'essai est fabriquée avec le loader de PROD (`store_sqlite`), comme
pour `test_mesure_propagation_noms` dont ce fichier réutilise les fabriques.
"""

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import mesure_tranche_seuil as T
from test_mesure_propagation_noms import SERVER_FACTICE, Base, b64, vecteur


@contextlib.contextmanager
def sans_bruit():
    """Avale la sortie standard de `main()` — et ce n'est pas du confort.

    Le 22/08, l'agent git a refuse deux fois la livraison sur
    « FAILED (errors=2) » alors que le banc rendait 25 verts. Meme
    interpreteur, meme dossier, meme commande : la seule difference est que
    l'agent CAPTURE la sortie. Un `print` part alors dans un TUYAU et non dans
    une console, Windows retombe sur son encodage local, et le premier « é » de
    « TRANCHE À JUGER » tue le test par `UnicodeEncodeError`. Deux tests
    appellent `main()`, deux erreurs — le compte tombait juste.
    (Le projet connaissait deja le piege : `banc_agent.py` impose
    `PYTHONIOENCODING=utf-8` pour cette raison, depuis le 15/08.)

    Un test n'a rien a imprimer : ce qu'il verifie, il l'assertionne. Ce qui
    est teste ici reste `afficher_tirage`, dont la CHAINE est lue, jamais
    l'ecriture sur un flux qui ne nous appartient pas.
    """
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        yield tampon


def a_pour_score(cible, ref, graine):
    """Un vecteur dont le cosinus avec `ref` vaut ~`cible`.

    Construit dans le plan (ref, orthogonal) : cos·ref + sin·perp. Le passage
    en float16 du stockage rabote la 3ᵉ décimale, d'où les marges des tests.
    """
    rng = np.random.default_rng(graine)
    w = rng.normal(size=len(ref)).astype(np.float32)
    perp = w - float(w @ ref) * ref
    perp = perp / np.linalg.norm(perp)
    v = cible * ref + float(np.sqrt(max(0.0, 1 - cible * cible))) * perp
    return (v / np.linalg.norm(v)).astype(np.float32)


class Fixture:
    """Une personne (Flo) et N visages aux scores choisis."""

    def __init__(self, d, scores, noms_photo=(), exclude=(), server=SERVER_FACTICE):
        self.b = Base(d, server_src=server)
        self.ref = vecteur(1)
        self.b.personne('Flo', [self.ref], exclude=list(exclude),
                        faces=[['ref/flo1.jpg', 0], ['ref/flo2.jpg', 1]],
                        avatar=['ref/avatar.jpg', 3])
        # Une 2e personne, loin : sans concurrent il n'y a pas de marge, et
        # c'est la marge qui explique l'hésitation à un humain.
        self.b.personne('Zoe', [vecteur(99)])
        for n, sc in enumerate(scores):
            cle = f'p{n:03d}.jpg'
            v = a_pour_score(sc, self.ref, 1000 + n)
            self.b.photo(cle, [{"emb": b64(v)}], noms=noms_photo)
        self.b.fermer()
        self.dir = Path(d)


class TestBornes(unittest.TestCase):

    def test_ne_retient_que_la_tranche_demandee(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.20, 0.36, 0.38, 0.45, 0.60])
            vives, rap = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=False)
            self.assertEqual(len(vives), 2)
            for c in vives:
                self.assertGreaterEqual(c["sim"], 0.35)
                self.assertLess(c["sim"], 0.40)
            self.assertEqual(rap["sorts"]["hors_tranche"], 3)

    def test_borne_haute_exclue_borne_basse_incluse(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.3502, 0.3998])
            vives, _ = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=False)
            self.assertEqual(len(vives), 2)
            vives, _ = T.candidates(f.b.db, d, 0.36, 0.3998, fichiers=False)
            self.assertEqual(len(vives), 0)

    def test_dit_quand_la_tranche_mord_sur_ce_que_la_prod_propose(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.37])
            _, rap = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=False)
            self.assertTrue(rap["sous_le_seuil_de_prod"])
            _, rap = T.candidates(f.b.db, d, 0.35, 0.50, fichiers=False)
            self.assertFalse(rap["sous_le_seuil_de_prod"])
            self.assertIn("DÉJÀ", T.afficher_tirage(
                T.preparer(f.b.db, d, 0.35, 0.50, 5, 1, fichiers=False)))


class TestGardeFousHumains(unittest.TestCase):

    def test_le_nom_deja_pose_sur_la_photo_n_est_pas_repropose(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.37, 0.38], noms_photo=('Flo',))
            vives, rap = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=False)
            self.assertEqual(vives, [])
            self.assertEqual(rap["sorts"]["deja_dit"], 2)

    def test_une_exclusion_humaine_ecarte_la_proposition(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.37, 0.38], exclude=('p000.jpg',))
            vives, rap = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=False)
            self.assertEqual([c["key"] for c in vives], ['p001.jpg'])
            self.assertEqual(rap["sorts"]["exclu_par_un_humain"], 1)

    def test_un_visage_marque_pas_un_visage_est_ecarte(self):
        with TemporaryDirectory() as d:
            b = Base(d)
            ref = vecteur(1)
            b.personne('Flo', [ref])
            b.personne('Zoe', [vecteur(99)])
            v = b64(a_pour_score(0.37, ref, 7))
            b.photo('a.jpg', [{"emb": v, "pas_visage": True}])
            b.photo('b.jpg', [{"emb": v, "inconnu": True}])
            b.photo('c.jpg', [{"emb": v}])
            b.fermer()
            vives, _ = T.candidates(b.db, d, 0.35, 0.40, fichiers=False)
            self.assertEqual([c["key"] for c in vives], ['c.jpg'])


class TestCandidate(unittest.TestCase):

    def test_porte_le_rival_et_la_marge(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.37])
            vives, _ = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=False)
            c = vives[0]
            self.assertEqual(c["person"], 'Flo')
            self.assertEqual(c["rival"], 'Zoe')
            self.assertAlmostEqual(c["margin"], c["sim"] - c["rival_sim"], 3)

    def test_le_tirage_ne_porte_aucune_reference(self):
        """La planche appartient a la PAGE, pas au tirage.

        Le 22/08 elle etait figee ici : tiree a 21:26, elle montrait encore
        les couples d'avant le recalage de 22:19. Une reference qui voyage
        avec l'echantillon vieillit avec lui — et elle vieillit exactement la
        ou une reparation vient de passer. `server._tranche_refs_vivantes` la
        relit dans la fiche a chaque affichage."""
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.37])
            vives, _ = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=False)
            self.assertNotIn("refs", vives[0])


class TestTirage(unittest.TestCase):

    def setUp(self):
        self.pop = [{"key": f'p{n:03d}.jpg', "i": 0, "person": 'Flo',
                     "sim": 0.35 + n / 1000, "margin": 0.01,
                     "rival": 'Zoe', "rival_sim": 0.1}
                    for n in range(200)]

    def test_reproductible_a_graine_egale(self):
        a = T.tirer(self.pop, 30, 20260822)
        b = T.tirer(self.pop, 30, 20260822)
        self.assertEqual([c["key"] for c in a], [c["key"] for c in b])
        self.assertEqual(len(a), 30)

    def test_graine_differente_donne_un_autre_echantillon(self):
        a = T.tirer(self.pop, 30, 1)
        b = T.tirer(self.pop, 30, 2)
        self.assertNotEqual([c["key"] for c in a], [c["key"] for c in b])

    def test_le_tirage_n_est_pas_le_haut_de_la_tranche(self):
        """Le piège du 20/08 : prendre les meilleurs et conclure sur tout."""
        tires = T.tirer(self.pop, 30, 20260822)
        meilleurs = {c["key"] for c in sorted(
            self.pop, key=lambda c: -c["sim"])[:30]}
        self.assertNotEqual({c["key"] for c in tires}, meilleurs)
        moyen = sum(c["sim"] for c in tires) / len(tires)
        # Un tirage uniforme se tient autour du milieu de la tranche, pas en haut.
        self.assertLess(moyen, 0.35 + 0.150)

    def test_moins_de_candidates_que_demande_prend_tout_et_le_dit(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.36, 0.37, 0.38])
            rap = T.preparer(f.b.db, d, 0.35, 0.40, 30, 1, fichiers=False)
            self.assertEqual(rap["tirage"]["tires"], 3)
            self.assertTrue(rap["tirage"]["complet"])
            self.assertIn("3 disponibles", T.afficher_tirage(rap))


class TestFichiers(unittest.TestCase):

    def test_ecarte_les_cles_fantomes_quand_la_racine_est_joignable(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.36, 0.37])
            (f.dir / 'dossier_uploads.txt').write_text(d, encoding='utf-8')
            (f.dir / 'p000.jpg').write_bytes(b'x')       # une seule existe
            vives, rap = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=True)
            self.assertTrue(rap["fichiers"]["applique"])
            self.assertEqual([c["key"] for c in vives], ['p000.jpg'])
            self.assertEqual(rap["fichiers"]["candidates_fantomes"], 1)

    def test_racine_injoignable_suspend_le_filtre_et_le_dit(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.36, 0.37])
            (f.dir / 'dossier_uploads.txt').write_text(
                str(Path(d) / 'nas_debranche'), encoding='utf-8')
            vives, rap = T.candidates(f.b.db, d, 0.35, 0.40, fichiers=True)
            self.assertFalse(rap["fichiers"]["applique"])
            self.assertIn("SUSPENDU", rap["fichiers"]["raison"])
            self.assertEqual(len(vives), 2)
            self.assertIn("NON appliqué", T.afficher_tirage(
                T.preparer(f.b.db, d, 0.35, 0.40, 5, 1, fichiers=True)))


class TestRefus(unittest.TestCase):

    def test_refuse_photos_db(self):
        with self.assertRaises(SystemExit) as e:
            T.candidates('photos.db', '.', 0.35, 0.40)
        self.assertIn('photos.db', str(e.exception))

    def test_bornes_absurdes(self):
        with self.assertRaises(SystemExit):
            T.main(['--base', 'copie.db', '--min', '0.5', '--max', '0.4'])


class TestSortie(unittest.TestCase):

    def test_ecrit_le_fichier_a_juger(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.36, 0.37, 0.38])
            sortie = f.dir / 'tranche.json'
            with sans_bruit():
                T.main(['--base', str(f.b.db), '--projet', d, '--n', '2',
                        '--sortie', str(sortie), '--sans-fichiers'])
            data = json.loads(sortie.read_text(encoding='utf-8'))
            self.assertEqual(len(data["items"]), 2)
            self.assertEqual(data["bornes"], {"min": 0.35, "max": 0.40})
            self.assertIn("CUR_ADD_SIM", data["seuils"])
            self.assertFalse((f.dir / 'tranche.tmp').exists())


class TestWilson(unittest.TestCase):

    def test_trente_sur_trente_ne_vaut_pas_infaillible(self):
        bas, haut = T.wilson(30, 30)
        self.assertLess(bas, 0.90)
        self.assertGreater(bas, 0.85)
        self.assertEqual(round(haut, 3), 1.0)

    def test_encadre_la_proportion(self):
        bas, haut = T.wilson(24, 30)
        self.assertLess(bas, 0.80)
        self.assertGreater(haut, 0.80)

    def test_sans_jugement_pas_d_intervalle(self):
        self.assertEqual(T.wilson(0, 0), (0.0, 0.0))


class TestBilan(unittest.TestCase):

    def ecrire(self, d, verdicts):
        p = Path(d) / 'jug.json'
        p.write_text(json.dumps({"verdicts": verdicts}), encoding='utf-8')
        return p

    def test_indecidable_ne_compte_ni_juste_ni_faux(self):
        with TemporaryDirectory() as d:
            p = self.ecrire(d, {
                "a": {"verdict": "juste"}, "b": {"verdict": "juste"},
                "c": {"verdict": "faux"}, "e": {"verdict": "indecidable"}})
            r = T.bilan(p)
            self.assertEqual(r["juges"], 4)
            self.assertEqual(r["tranches"], 3)
            self.assertAlmostEqual(r["taux_juste"], 2 / 3, 3)

    def test_sans_verdict_tranche_pas_de_taux(self):
        with TemporaryDirectory() as d:
            p = self.ecrire(d, {"a": {"verdict": "indecidable"}})
            r = T.bilan(p)
            self.assertIsNone(r["taux_juste"])
            self.assertIn("pas de taux", T.afficher_bilan(r))

    def test_le_bilan_dit_ce_que_l_intervalle_autorise(self):
        with TemporaryDirectory() as d:
            haut = T.afficher_bilan(T.bilan(self.ekrire_ok(d, 60, 0)))
            self.assertIn("tient même par le bas", haut)
            bas = T.afficher_bilan(T.bilan(self.ekrire_ok(d, 2, 28)))
            self.assertIn("mauvaise par le haut", bas)
            flou = T.afficher_bilan(T.bilan(self.ekrire_ok(d, 6, 4)))
            self.assertIn("enjambe la décision", flou)

    def ekrire_ok(self, d, justes, faux):
        v = {}
        for n in range(justes):
            v[f'j{n}'] = {"verdict": "juste"}
        for n in range(faux):
            v[f'f{n}'] = {"verdict": "faux"}
        return self.ecrire(d, v)

    def test_signale_une_tranche_massivement_indecidable(self):
        with TemporaryDirectory() as d:
            v = {f'j{n}': {"verdict": "juste"} for n in range(8)}
            v.update({f'i{n}': {"verdict": "indecidable"} for n in range(8)})
            txt = T.afficher_bilan(T.bilan(self.ecrire(d, v)))
            self.assertIn("échappe au jugement humain", txt)

    def test_compte_le_restant_a_juger(self):
        with TemporaryDirectory() as d:
            f = Fixture(d, [0.36, 0.37, 0.38])
            sortie = f.dir / 'tranche.json'
            with sans_bruit():
                T.main(['--base', str(f.b.db), '--projet', d, '--n', '3',
                        '--sortie', str(sortie), '--sans-fichiers'])
            p = self.ecrire(d, {"a": {"verdict": "juste"}})
            r = T.bilan(p, sortie)
            self.assertEqual(r["restant"], 2)


if __name__ == '__main__':
    unittest.main()
