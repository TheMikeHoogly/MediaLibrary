#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `mesure_rattachements.py`.

Ce banc va servir a decider si les 1 576 rattachements de la verite terrain
sont fiables. S'il compte mal, il condamnera ou blanchira a tort. Ces cas
fixent donc les trois verdicts qu'il rend — DESIGNE LE MEILLEUR, DECALE, HORS
BORNES — et le garde-fou qui les separe : deux visages proches ne sont pas un
decalage, sinon toute photo de fratrie serait une erreur.

Les tests n'IMPRIMENT rien : l'agent git capture la sortie, et un « é » parti
dans un tuyau tue le test sous Windows (constate le 22/08, deux fois).
"""

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import mesure_rattachements as R
from test_mesure_propagation_noms import SERVER_FACTICE, Base, b64, vecteur


class Fabrique:
    """Une fiche (Flo) et des photos dont on choisit les visages."""

    def __init__(self, d):
        self.b = Base(d)
        self.flo = vecteur(1)
        self.autre = vecteur(77)          # quelqu'un d'autre, loin de Flo

    def fiche(self, couples, refs=None):
        self.b.personne('Flo', refs if refs is not None else [self.flo],
                        faces=[list(c) for c in couples])

    def photo(self, cle, vecteurs, redetectee=False, examinee=False):
        """`examinee` pose le drapeau `reemb` SANS re-detection ; `redetectee`
        pose en plus `reemb_ms`. La prod fait exactement cette difference, et
        c'est elle qui distingue un croisement vivant d'un croisement mort."""
        e = {"faces": [({"emb": b64(v)} if v is not None else {})
                       for v in vecteurs]}
        if examinee or redetectee:
            e["reemb"] = 1
        if redetectee:
            e["reemb_ms"] = 1600
        self.b.faces.set(cle, e)
        self.b.tags.set(cle, {"kw_fr": []})

    def fermer(self):
        self.b.fermer()
        return self.b.db


def mesurer(d, f, ecart=R.ECART_DEFAUT):
    with contextlib.redirect_stdout(io.StringIO()):
        return R.mesurer(f.fermer(), d, ecart, 12)


class TestVerdicts(unittest.TestCase):

    def test_un_couple_qui_designe_le_bon_visage_est_juste(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.flo, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["comptes"]["designe_le_meilleur_ou_presque"], 1)
            self.assertNotIn("decale", r["comptes"])

    def test_un_index_decale_vers_l_autre_personne_est_vu(self):
        """Le cas de Mike : Didier designe le visage de Laura, sur la meme photo."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 1)])           # designe « l'autre »
            f.photo('a.jpg', [f.flo, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["comptes"]["decale"], 1)
            e = r["exemples_decales"][0]
            self.assertEqual((e["i"], e["mieux"]), (1, 0))
            self.assertGreater(e["sim_mieux"], e["sim"])

    def test_un_index_hors_bornes_est_compte_a_part(self):
        """`_serve_facecrop` retombe alors sur le visage 0 EN SILENCE : ce cas
        ne doit jamais etre noye dans « decale », il se repare autrement."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 5)])
            f.photo('a.jpg', [f.flo, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["comptes"]["index_hors_bornes"], 1)
            self.assertEqual(r["comptes"].get("mesurables", 0), 0)
            self.assertEqual(r["exemples_hors_bornes"][0]["visages"], 2)

    def test_deux_visages_proches_ne_sont_pas_un_decalage(self):
        """Sinon toute photo ou quelqu'un est detecte deux fois, ou toute
        fratrie, passerait pour une erreur."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            presque = f.flo + 0.02 * vecteur(5)
            presque = presque / np.linalg.norm(presque)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.flo, presque])
            r = mesurer(d, f)
            self.assertEqual(r["comptes"]["designe_le_meilleur_ou_presque"], 1)
            self.assertNotIn("decale", r["comptes"])

    def test_l_ecart_est_reglable_et_change_le_verdict(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            moyen = f.flo + 0.35 * vecteur(5)
            moyen = moyen / np.linalg.norm(moyen)
            f.fiche([('a.jpg', 1)])
            f.photo('a.jpg', [f.flo, moyen])
            self.assertEqual(mesurer(d, f, ecart=0.01)["comptes"].get("decale"), 1)

    def test_une_photo_a_un_seul_visage_ne_peut_pas_etre_decalee(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.autre])       # mauvais visage, mais seul
            r = mesurer(d, f)
            self.assertEqual(r["comptes"]["seul_visage_de_la_photo"], 1)
            self.assertNotIn("decale", r["comptes"])
            self.assertEqual(r["comptes"]["sous_le_seuil_de_faux_positif"], 1)


class TestMatiereAbsente(unittest.TestCase):

    def test_photo_sans_fiche_de_visages(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('fantome.jpg', 0)])
            f.photo('a.jpg', [f.flo])
            r = mesurer(d, f)
            self.assertEqual(r["comptes"]["photo_sans_fiche_de_visages"], 1)

    def test_visage_sans_vecteur(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [None, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["comptes"]["visage_designe_sans_vecteur"], 1)

    def test_une_fiche_sans_signature_est_comptee_et_non_mesuree(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)], refs=[])
            f.photo('a.jpg', [f.flo])
            with self.assertRaises(SystemExit):
                mesurer(d, f)


class TestCroisement(unittest.TestCase):

    def test_le_decalage_est_croise_avec_le_re_embedding(self):
        """La cause presumee doit etre NOMMEE par le chiffre, pas par le
        raisonnement — c'est tout l'interet du croisement."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 1), ('b.jpg', 1)])
            f.photo('a.jpg', [f.flo, f.autre], redetectee=True)
            f.photo('b.jpg', [f.flo, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["croisement_reemb"]["decale_reemb"], 1)
            self.assertEqual(r["croisement_reemb"]["decale_sans_reemb"], 1)
            self.assertEqual(r["fonds"]["dont_reembarquees"], 1)
            self.assertEqual(r["fonds"]["photos_a_visages"], 2)

    def test_le_drapeau_reemb_seul_ne_vaut_pas_re_detection(self):
        """Le 22/08, le premier croisement a rendu 100 % — instrument mort :
        `reemb` est aussi pose sur les photos seulement EXAMINEES. Seul
        `reemb_ms` marque un appel reel a `detect_faces`."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 1)])
            f.photo('a.jpg', [f.flo, f.autre], examinee=True)
            r = mesurer(d, f)
            self.assertEqual(r["fonds"]["dont_marquees_reemb"], 1)
            self.assertEqual(r["fonds"]["dont_reembarquees"], 0)
            self.assertEqual(r["croisement_reemb"]["decale_sans_reemb"], 1)

    def test_le_verdict_est_rendu_poste_par_poste(self):
        """La planche montre les premiers couples : leur sort doit se lire
        separement, sinon un fonds sain masque une planche trompeuse."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 1), ('b.jpg', 0)])   # poste 0 faux, poste 1 juste
            f.photo('a.jpg', [f.flo, f.autre])
            f.photo('b.jpg', [f.flo, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["par_poste"]["0"]["decale"], 1)
            self.assertEqual(r["par_poste"]["1"]["juste"], 1)
            self.assertIn("Par POSTE", R.afficher(r))

    def test_le_denominateur_du_fonds_est_rendu(self):
        """« 80 % des decales sont reemb » ne veut rien dire si 80 % du fonds
        l'est : sans denominateur, le croisement ment."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.flo, f.autre], redetectee=True)
            f.photo('c.jpg', [f.autre], redetectee=True)
            r = mesurer(d, f)
            self.assertEqual(r["fonds"]["dont_reembarquees"], 2)


class TestPlan(unittest.TestCase):
    """Le banc n'invente pas la reparation : il APPELLE la regle de prod."""

    def test_le_plan_recale_le_couple_decale(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 1)])
            f.photo('a.jpg', [f.flo, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["plan"]["recale"], 1)
            e = r["exemples_plan"][0]
            self.assertEqual((e["de"], e["vers"]), (1, 0))
            self.assertIn("REPARATION", R.afficher(r))

    def test_le_plan_refuse_ce_que_la_regle_refuse(self):
        """Un couple decale n'est pas forcement reparable : si le meilleur
        visage de la photo ne ressemble a personne, on ne deplace rien."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            faible = f.flo * 0.15 + f.autre * 0.99
            faible = faible / np.linalg.norm(faible)
            f.fiche([('a.jpg', 1)])
            f.photo('a.jpg', [faible, f.autre])
            r = mesurer(d, f)
            self.assertNotIn("recale", r["plan"])
            self.assertTrue(any(k.startswith("refus_") for k in r["plan"]))

    def test_deux_personnes_qui_ont_echange_leurs_visages_sont_REFUSEES(self):
        """La limite de la regle, et il faut la connaitre AVANT d'appliquer.

        Sur une photo de deux personnes, un decalage d'index les PERMUTE :
        Flo designe le visage de Laura et Laura celui de Flo. Chacune veut
        alors le visage que l'autre possede deja, et la regle refuse des deux
        cotes — « deja pris ». C'est le comportement voulu : echanger deux
        decisions humaines d'un geste automatique demande plus qu'un score, et
        un conflit muet vaut moins qu'un decalage visible. Mais cela veut dire
        que ce cas-la n'est pas reparable ainsi : le chiffre du plan doit se
        lire avec ca en tete.
        """
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 1)])                                 # Flo -> Laura
            f.b.personne('Laura', [f.autre], faces=[['a.jpg', 0]])  # Laura -> Flo
            f.photo('a.jpg', [f.flo, f.autre])
            r = mesurer(d, f)
            self.assertEqual(r["plan"].get("refus_deja_pris"), 2)
            self.assertNotIn("recale", r["plan"])


class TestRefus(unittest.TestCase):

    def test_refuse_photos_db(self):
        with self.assertRaises(SystemExit) as e:
            R.mesurer('photos.db', '.', 0.1, 3)
        self.assertIn('photos.db', str(e.exception))


class TestRapport(unittest.TestCase):

    def test_le_rapport_dit_que_le_chiffre_est_une_borne_basse(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 1)])
            f.photo('a.jpg', [f.flo, f.autre])
            txt = R.afficher(mesurer(d, f))
            self.assertIn("BORNE BASSE", txt)
            self.assertIn("decale", txt)


class TestVerifierRecalages(unittest.TestCase):
    """Un recalage applique a-t-il REPARE (l'ancien visage etait un inconnu)
    ou REBRASSE (les deux sont la personne, page d'album ou montage) ?"""

    def journal(self, dossier, avant, apres, fiche='flo'):
        d = Path(dossier) / '_corbeille_recalage'
        d.mkdir(exist_ok=True)
        (d / 'recalage_20260822_000000.jsonl').write_text(
            json.dumps({"at": 0, "recalages": 1}) + "\n"
            + json.dumps({"magasin": "people", "fiche": fiche,
                          "avant": {"faces": avant},
                          "apres": {"faces": apres}}) + "\n",
            encoding='utf-8')
        return str(d)

    def test_sans_journal_il_le_DIT_au_lieu_de_conclure(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.flo])
            base = f.fermer()
            with self.assertRaises(SystemExit) as e:
                R.verifier_recalages(base, d, str(Path(d) / 'vide'))
            self.assertIn('Aucun journal', str(e.exception))

    def test_ancien_visage_inconnu_compte_comme_REPARATION(self):
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.flo, f.autre])
            base = f.fermer()
            dossier = self.journal(d, [['a.jpg', 1]], [['a.jpg', 0]])
            txt = R.verifier_recalages(base, d, dossier)
            self.assertIn('REPARATION', txt)
            self.assertNotIn('rebrassage  flo', txt)

    def test_deux_visages_de_la_personne_comptent_comme_rebrassage(self):
        """Le cas de la page d'album : l'ancien index designait deja Flo,
        ailleurs dans le meme fichier. Rien n'a ete repare."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.flo, f.flo])
            base = f.fermer()
            dossier = self.journal(d, [['a.jpg', 1]], [['a.jpg', 0]])
            txt = R.verifier_recalages(base, d, dossier)
            self.assertIn('rebrassage', txt)
            ligne = [x for x in txt.split('\n') if 'rebrassage  (' in x][0]
            self.assertIn('1', ligne)
            self.assertIn('100.0 %', ligne)

    def test_une_fusion_est_ECARTEE_et_NOMMEE(self):
        """Les listes n'ont plus la meme longueur : les apparier position par
        position serait deviner. Une population ecartee doit etre nommee."""
        with TemporaryDirectory() as d:
            f = Fabrique(d)
            f.fiche([('a.jpg', 0)])
            f.photo('a.jpg', [f.flo, f.autre])
            base = f.fermer()
            dossier = self.journal(d, [['a.jpg', 1], ['a.jpg', 0]],
                                   [['a.jpg', 0]])
            txt = R.verifier_recalages(base, d, dossier)
            self.assertIn('ECARTES', txt)
            self.assertIn('fusion', txt)


class TestBilanResidu(unittest.TestCase):
    """Le banc CONCLUT sur les jugements de la page /residu.

    Trois populations qui ne se melangent pas : ce qu'on retire (cite, juge
    pas elle), ce qu'on confirme, et ce qu'on AJOUTERAIT (juge elle, non cite)
    — ce dernier est une attribution, un autre geste, et le confondre avec un
    retrait ferait poser un nom sous couvert de reparation.
    """

    CAS = [{"key": r"\\NAS\p\a.jpg", "person": 'Didier', "visages": 12,
            "pourquoi": 'ambigu',
            "candidats": [{"i": 1, "sim": 0.9, "cite": True},
                          {"i": 8, "sim": 0.7, "cite": True},
                          {"i": 3, "sim": 0.8, "cite": False}]},
           {"key": r"\\NAS\p\b.jpg", "person": 'Flo', "visages": 4,
            "pourquoi": 'ambigu',
            "candidats": [{"i": 0, "sim": 0.8, "cite": True},
                          {"i": 2, "sim": 0.7, "cite": True}]}]

    def bilan(self, dossier, verdicts):
        cas = Path(dossier) / 'cas.json'
        jug = Path(dossier) / 'jug.json'
        cas.write_text(json.dumps({"cas": self.CAS}), encoding='utf-8')
        jug.write_text(json.dumps({"verdicts": verdicts}), encoding='utf-8')
        return R.bilan_residu(str(cas), str(jug))

    def verdict(self, cas, oui, verdict='juge'):
        return {f"{cas['key']}|{cas['person']}":
                {"verdict": verdict, "oui": oui}}

    def test_sans_verdict_le_bilan_le_DIT_au_lieu_de_conclure(self):
        with TemporaryDirectory() as d:
            txt = self.bilan(d, {})
            self.assertIn("Aucun cas juge", txt)
            self.assertNotIn("a retirer (cite", txt)

    def test_le_couple_cite_non_retenu_part_au_retrait(self):
        with TemporaryDirectory() as d:
            txt = self.bilan(d, self.verdict(self.CAS[0], [1]))
            self.assertIn("a retirer (cite, juge PAS elle)          1", txt)
            self.assertIn("confirme  (cite, juge bien elle)         1", txt)

    def test_un_visage_NON_cite_juge_elle_est_un_AJOUT_pas_un_retrait(self):
        with TemporaryDirectory() as d:
            txt = self.bilan(d, self.verdict(self.CAS[0], [1, 3]))
            self.assertIn("a AJOUTER (juge elle, NON cite)          1", txt)
            self.assertIn("attribution, autre geste", txt)

    def test_aucun_n_est_elle_retire_tous_les_couples_cites(self):
        with TemporaryDirectory() as d:
            txt = self.bilan(d, self.verdict(self.CAS[1], []))
            self.assertIn("a retirer (cite, juge PAS elle)          2", txt)
            self.assertIn("photos ou aucun visage n'est elle        1", txt)

    def test_un_indecidable_ne_compte_ni_dans_l_un_ni_dans_l_autre(self):
        with TemporaryDirectory() as d:
            txt = self.bilan(d, self.verdict(self.CAS[0], [], 'indecidable'))
            self.assertIn("indecidables 1", txt)
            self.assertIn("Aucun cas juge", txt)

    def test_les_cas_non_juges_sont_comptes_a_part(self):
        with TemporaryDirectory() as d:
            txt = self.bilan(d, self.verdict(self.CAS[0], [1]))
            self.assertIn("non juges 1", txt)

    def test_le_bilan_rappelle_que_le_retrait_est_un_geste_humain(self):
        with TemporaryDirectory() as d:
            txt = self.bilan(d, self.verdict(self.CAS[0], [1]))
            self.assertIn("geste de Mike", txt)


if __name__ == '__main__':
    unittest.main()
