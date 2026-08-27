#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le re-cle HORS LIGNE transporte-t-il les decisions humaines ?

Ce que ce test tient, et pourquoi il n'existait pas
---------------------------------------------------
`appliquer_plan.rekey_stores` se disait << miroir de server.rekey_everywhere >>
dans son docstring. Elle ne l'etait pas : elle bouclait sur les quatre magasins
de sujets en appelant `store.rekey(ancien_chemin, nouveau_chemin)`, or `people`
et `pets` sont keyes par NOM -- leurs chemins vivent DANS la fiche. `rekey` y
cherche une entree dont la cle serait un chemin, n'en trouve jamais, renvoie
faux, et la boucle ne regardait meme pas le retour. Deux magasins sur quatre,
en silence.

Le correctif (`recle_decisions.recler_fiche`) etait branche dans `server.py`
le 22/08 et NULLE PART AILLEURS. Le rangement par annee et le dedoublonnage
decrochaient donc encore des decisions le 27/08 -- 928 en avaient deja fait les
frais.

**Un docstring qui dit << miroir de >> n'est pas une preuve.** Voici le test
qui manquait : il ROUGIT sur l'ancien code et VERDIT sur le neuf.

Ce qui se perdait n'etait jamais le NOM (il vit dans `tags` et dans le XMP,
regle 2 tenue) : c'etait la VERITE TERRAIN -- quel visage est qui, quelles
photos ont ete ecartees d'un nom, lesquelles ont ete confirmees.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appliquer_plan as A  # noqa: E402

MORTE = 'http://127.0.0.1:1/api/serveur'   # personne n ecoute la
ANCIEN = r'X:\Photos\_A TRIER\lot\20210726_145915.jpg'
NEUF = r'X:\Photos\2021\20210726_145915.jpg'


def base_de_travail():
    """Une base NEUVE, jamais `photos.db` : le serveur en est l ecrivain unique."""
    d = Path(tempfile.mkdtemp(prefix="test_recle_hl_"))
    stores, semantic = A.open_stores(str(d / 'copie.db'))
    stores['tags'].set(ANCIEN, {'kw_fr': ['personne:Florine', 'plage']})
    stores['faces'].set(ANCIEN, {'faces': [{'box': [0, 0, 1, 1]}]})
    stores['people'].set('Florine', {
        'name': 'Florine',
        'faces': [[ANCIEN, 0], [r'X:\autre.jpg', 1]],   # 1 rattachement concerne
        'exclude': [ANCIEN],                            # 1 exclusion
        'confirmed': [ANCIEN],                          # 1 confirmation
        # L'avatar est une PAIRE [chemin, index], pas un chemin nu -- mon
        # premier jeu d'essai l'avait ecrit en chaine et c'est LE TEST qui
        # etait faux, pas l'instrument.
        'avatar': [ANCIEN, 0],                          # DERIVE : pas un jugement
    })
    return stores, semantic, d


class LesDecisionsSuiventLaPhoto(unittest.TestCase):

    def setUp(self):
        self.stores, self.semantic, self.d = base_de_travail()

    def fiche(self):
        return self.stores['people'].data.get('Florine')

    def test_LE_defaut_du_22_08_rattachement_exclusion_confirmation(self):
        # Rouge sur l'ancien code : les trois restaient sur l'ancien chemin.
        compte = {}
        self.assertTrue(A.rekey_stores(ANCIEN, NEUF, self.stores,
                                       self.semantic, compte=compte))
        f = self.fiche()
        self.assertIn([NEUF, 0], [list(x) for x in f['faces']])
        self.assertNotIn(ANCIEN, [x[0] for x in f['faces']])
        self.assertEqual(f['exclude'], [NEUF])
        self.assertEqual(f['confirmed'], [NEUF])

    def test_les_decisions_re_clees_sont_COMPTEES(self):
        # Ce qui n'est pas compte n'est pas diagnosticable apres coup.
        compte = {}
        A.rekey_stores(ANCIEN, NEUF, self.stores, self.semantic, compte=compte)
        self.assertEqual(compte.get('decisions'), 3)   # avatar exclu : derive

    def test_l_avatar_suit_MAIS_ne_compte_pas_pour_un_jugement(self):
        A.rekey_stores(ANCIEN, NEUF, self.stores, self.semantic)
        self.assertEqual(list(self.fiche()['avatar']), [NEUF, 0])

    def test_ce_qui_ne_concerne_PAS_la_photo_ne_bouge_pas(self):
        A.rekey_stores(ANCIEN, NEUF, self.stores, self.semantic)
        self.assertIn([r'X:\autre.jpg', 1],
                      [list(x) for x in self.fiche()['faces']])

    def test_le_NOM_survit_de_toute_facon(self):
        # La regle 2 tenait deja : le tag vit dans l'index et dans le XMP.
        A.rekey_stores(ANCIEN, NEUF, self.stores, self.semantic)
        self.assertIn('personne:Florine',
                      self.stores['tags'].data[NEUF]['kw_fr'])

    def test_le_retour_en_arriere_ramene_les_decisions(self):
        # L'undo du rangement par annee re-appelle rekey_stores en sens
        # inverse : il doit ramener ce qu'il avait emporte.
        A.rekey_stores(ANCIEN, NEUF, self.stores, self.semantic)
        compte = {}
        A.rekey_stores(NEUF, ANCIEN, self.stores, self.semantic, compte=compte)
        self.assertEqual(self.fiche()['exclude'], [ANCIEN])
        self.assertEqual(compte.get('decisions'), 3)

    def test_une_photo_hors_index_ne_declenche_rien(self):
        compte = {}
        self.assertFalse(A.rekey_stores(r'X:\inconnue.jpg', NEUF, self.stores,
                                        self.semantic, compte=compte))
        self.assertEqual(compte, {})
        self.assertEqual(self.fiche()['exclude'], [ANCIEN])

    def test_la_fonction_seule_est_utilisable_et_rend_son_compte(self):
        n = A.recler_decisions_humaines(ANCIEN, NEUF, self.stores)
        self.assertEqual(n, 3)

    def test_un_magasin_absent_ne_fait_pas_tomber(self):
        stores = {k: v for k, v in self.stores.items() if k != 'pets'}
        self.assertEqual(A.recler_decisions_humaines(ANCIEN, NEUF, stores), 3)


class LeRougeQuOnAObserve(unittest.TestCase):
    """L'ANCIEN comportement, grave : sans le re-cle des fiches, les trois
    decisions restaient sur l'ancien chemin -- et personne ne le disait."""

    def test_la_boucle_des_quatre_magasins_en_couvrait_DEUX(self):
        stores, _sem, _d = base_de_travail()
        for t in A.SUBJECT_TABLES:                 # exactement l'ancien code
            stores[t].rekey(ANCIEN, NEUF)
        f = stores['people'].data.get('Florine')
        # Rien n'a bouge, et `rekey` n'a leve aucune erreur : le silence est
        # tout le defaut.
        self.assertEqual(f['exclude'], [ANCIEN])
        self.assertEqual(f['confirmed'], [ANCIEN])
        self.assertEqual([x[0] for x in f['faces']][0], ANCIEN)

    def test_rekey_sur_un_magasin_par_NOM_renvoie_faux_sans_rien_dire(self):
        stores, _sem, _d = base_de_travail()
        self.assertFalse(stores['people'].rekey(ANCIEN, NEUF))


class LaBaseDoitAvoirUnSEUL_ECRIVAIN(unittest.TestCase):
    """L'en-tete disait << A LANCER SERVEUR ARRETE >> et ne le verifiait pas.

    Le 27/08, le rangement par annee a failli partir sur une base que le
    serveur tenait ouverte. Demander dans un en-tete n'a jamais arrete
    personne : on le PROUVE."""

    def setUp(self):
        import appliquer_plan_annee as AA
        self.AA = AA
        self.stores, _sem, self.d = base_de_travail()
        self.db = str(self.d / 'copie.db')

    def test_un_dry_run_ne_demande_aucun_verrou(self):
        # Il n'ecrit rien : exiger le verrou empecherait de REGARDER.
        self.assertIsNone(self.AA.refus_d_ecriture(self.db, dry=True, url=MORTE))

    def test_base_libre_donc_on_ecrit(self):
        self.assertIsNone(self.AA.refus_d_ecriture(self.db, dry=False, url=MORTE))

    def test_un_AUTRE_ecrivain_fait_REFUSER(self):
        import sqlite3
        cx = sqlite3.connect(self.db, timeout=1.0)
        cx.execute('BEGIN IMMEDIATE')              # le << serveur >> tient la base
        try:
            refus = self.AA.refus_d_ecriture(self.db, dry=False, url=MORTE)
        finally:
            cx.execute('ROLLBACK')
            cx.close()
        self.assertIsNotNone(refus)
        self.assertIn('ECRIVAIN UNIQUE', refus)

    def test_forcer_passe_outre_explicitement(self):
        import sqlite3
        cx = sqlite3.connect(self.db, timeout=1.0)
        cx.execute('BEGIN IMMEDIATE')
        try:
            self.assertIsNone(self.AA.refus_d_ecriture(
                self.db, dry=False, forcer=True, url=MORTE))
        finally:
            cx.execute('ROLLBACK')
            cx.close()

    def test_une_base_ABSENTE_ne_bloque_pas(self):
        # Deplacement seul, index non re-cle : c'est un cas prevu du script.
        self.assertIsNone(self.AA.refus_d_ecriture(
            str(self.d / 'nexistepas.db'), dry=False, url=MORTE))


class LeSERVEUR_QUI_REPOND_SUFFIT_A_REFUSER(unittest.TestCase):
    """Le verrou seul ne prouve rien en mode WAL.

    La base est en WAL : un lecteur n'y bloque pas un ecrivain, et le serveur
    ne tient le verrou d'ecriture que PENDANT ses transactions. `BEGIN
    IMMEDIATE` peut donc l'obtenir alors que le serveur est bel et bien
    vivant. Demander au serveur s'il est la ne depend pas de l'instant."""

    def setUp(self):
        import appliquer_plan_annee as AA
        self.AA = AA
        _s, _sem, self.d = base_de_travail()
        self.db = str(self.d / 'copie.db')

    def _petit_serveur(self):
        import http.server
        import threading
        srv = http.server.HTTPServer(('127.0.0.1', 0), _Muet)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv, 'http://127.0.0.1:%d/api/serveur' % srv.server_address[1]

    def test_un_serveur_VIVANT_fait_refuser_meme_si_le_verrou_est_libre(self):
        srv, url = self._petit_serveur()
        try:
            refus = self.AA.refus_d_ecriture(self.db, dry=False, url=url)
        finally:
            srv.shutdown()
        self.assertIsNotNone(refus)
        self.assertIn('REPOND', refus)

    def test_un_dry_run_n_interroge_meme_pas_le_serveur(self):
        srv, url = self._petit_serveur()
        try:
            self.assertIsNone(self.AA.refus_d_ecriture(self.db, dry=True,
                                                       url=url))
        finally:
            srv.shutdown()


class _Muet(__import__('http.server', fromlist=['x']).BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"pid": 1}')

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    unittest.main(verbosity=0)
