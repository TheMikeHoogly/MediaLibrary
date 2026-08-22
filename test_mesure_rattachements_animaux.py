#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du banc des rattachements d'ANIMAUX.

Sur des magasins fabriques : chaque verdict du banc doit tomber sur un cas
construit pour lui, et le banc ne doit RIEN ecrire.

N'IMPRIME RIEN, jamais : l'agent git capture la sortie des tests, et sous
Windows un `print` part dans un tuyau ou l'encodage local reprend la main —
le premier accent tue le test par UnicodeEncodeError (`eval/METHODE.md`).
"""

import base64
import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

import mesure_rattachements_animaux as A

SERVER_FACTICE = (
    "ANIMAL_PIPELINE_VERSION = \"yolo11s|det0.30|dinov2_base\"\n"
    "ANIMAL_NAMEABLE = {'cat', 'dog', 'horse'}\n"
    "PET_CLUSTER_SIM = 0.60\n"
    "PET_MATCH_SIM = 0.55\n"
)

DIM = 8


class FauxStore:
    """Un magasin reduit a ce que le banc lui demande : `.data`."""

    def __init__(self, data):
        self.data = data


def b64(vec):
    v = np.asarray(vec, dtype=np.float16)
    return base64.b64encode(v.tobytes()).decode('ascii')


def vecteur(graine, dim=DIM):
    r = np.random.RandomState(graine)
    v = r.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def detection(vec, species='cat', **kw):
    d = {"species": species, "bbox": [0, 0, 10, 10]}
    if vec is not None:
        d["emb"] = b64(vec)
    d.update(kw)
    return d


class Bati:
    """Constructeur de scenario : tags, animals, pets."""

    def __init__(self):
        self.tags, self.animaux, self.pets = {}, {}, {}

    def photo(self, cle, detections, tags_kw=(), dans_index=True):
        # `kw_fr` : le champ de la PROD (`server._kw_has`). Un test qui
        # fabriquerait `kw` validerait l'erreur du banc au lieu de l'attraper —
        # c'est exactement ce qui est arrive le 22/08.
        if dans_index:
            self.tags[cle] = {"kw_fr": list(tags_kw)}
        self.animaux[cle] = {"animals": list(detections), "n": len(detections)}
        return self

    def fiche(self, nom, refs, couples, species='cat'):
        self.pets[nom.lower()] = {"name": nom, "species": species,
                                  "refs": [b64(v) for v in refs],
                                  "faces": [list(x) for x in couples]}
        return self

    def mesurer(self, projet, ecart=0.10, exemples=12, a_juger=False):
        return A._mesurer(FauxStore(self.tags), FauxStore(self.animaux),
                          FauxStore(self.pets), projet, ecart, exemples,
                          a_juger)


class BancTest(unittest.TestCase):

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.projet = self._tmp.name
        (Path(self.projet) / 'server.py').write_text(SERVER_FACTICE,
                                                     encoding='utf-8')
        self.addCleanup(self._tmp.cleanup)

    # ── la matiere de base ────────────────────────────────────────────────
    def test_un_couple_juste_est_mesurable_et_juste(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)]).fiche('Inti', [v], [('a.jpg', 0)])
        c = b.mesurer(self.projet)["comptes"]
        self.assertEqual(c['mesurables'], 1)
        self.assertEqual(c.get('decale', 0), 0)
        self.assertEqual(c['seul_candidat_de_la_photo'], 1)

    def test_le_banc_n_ecrit_rien(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)]).fiche('Inti', [v], [('a.jpg', 0)])
        avant = copy.deepcopy((b.tags, b.animaux, b.pets))
        b.mesurer(self.projet)
        self.assertEqual(avant, (b.tags, b.animaux, b.pets))

    # ── H2 : le mensonge muet ─────────────────────────────────────────────
    def test_index_hors_bornes_est_compte_et_donne_en_exemple(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)]).fiche('Inti', [v], [('a.jpg', 3)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"]['index_hors_bornes'], 1)
        self.assertEqual(r["comptes"].get('mesurables', 0), 0)
        self.assertEqual(r["exemples_hors_bornes"][0]['i'], 3)

    # ── H3 : les cles mortes ──────────────────────────────────────────────
    def test_une_cle_hors_index_est_nommee_pas_silencieuse(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)], dans_index=False)
        b.fiche('Inti', [v], [('a.jpg', 0)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"]['cle_absente_de_l_index'], 1)
        self.assertEqual(r["par_fiche"]['Inti']['cle_morte'], 1)

    # ── H4 : l'espece tranche sans seuil ──────────────────────────────────
    def test_espece_incoherente_est_fausse_sans_regarder_le_score(self):
        v = vecteur(1)
        # Le vecteur est PARFAIT : seule l'espece condamne le couple.
        b = Bati().photo('a.jpg', [detection(v, species='dog')])
        b.fiche('Inti', [v], [('a.jpg', 0)], species='cat')
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"]['espece_incoherente'], 1)
        self.assertEqual(r["comptes"].get('mesurables', 0), 0)

    def test_une_detection_contredite_par_siglip_n_est_pas_un_sujet(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v, suspect=True)])
        b.fiche('Inti', [v], [('a.jpg', 0)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"]['detection_non_nommable'], 1)

    # ── H1 : le decalage ──────────────────────────────────────────────────
    def test_un_autre_animal_de_la_meme_photo_qui_ressemble_plus(self):
        bon, autre = vecteur(1), vecteur(2)
        b = Bati().photo('a.jpg', [detection(autre), detection(bon)])
        b.fiche('Inti', [bon], [('a.jpg', 0)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"]['decale'], 1)
        self.assertEqual(r["exemples_decales"][0]['mieux'], 1)
        self.assertEqual(r["comptes"]['decale_photo_citee_une_fois'], 1)

    def test_le_decalage_dit_si_la_photo_est_citee_plusieurs_fois(self):
        """Un fichier n'est pas une scene : deux couples sur la meme image
        viennent du nommage d'un groupe, pas d'un index qui a glisse."""
        bon, autre = vecteur(1), vecteur(2)
        b = Bati().photo('a.jpg', [detection(bon), detection(autre)])
        b.fiche('Inti', [bon], [('a.jpg', 0), ('a.jpg', 1)])
        c = b.mesurer(self.projet)["comptes"]
        self.assertEqual(c['decale'], 1)
        self.assertEqual(c['decale_photo_citee_plusieurs_fois'], 1)
        self.assertEqual(c.get('decale_photo_citee_une_fois', 0), 0)

    def test_un_animal_d_une_AUTRE_espece_n_est_pas_un_candidat_au_decalage(self):
        """Un mouton qui « ressemble » plus au chien ne le remplace pas."""
        bon, autre = vecteur(1), vecteur(2)
        b = Bati().photo('a.jpg', [detection(bon), detection(autre, species='dog')])
        b.fiche('Inti', [bon], [('a.jpg', 0)], species='cat')
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"].get('decale', 0), 0)
        self.assertEqual(r["comptes"]['seul_candidat_de_la_photo'], 1)

    # ── H5 : un score bas est une cecite, et il est compte a part ─────────
    def test_sous_le_seuil_est_compte_separement_et_reste_mesurable(self):
        bon, loin = vecteur(1), vecteur(7)
        b = Bati().photo('a.jpg', [detection(loin)]).fiche('Inti', [bon],
                                                           [('a.jpg', 0)])
        r = b.mesurer(self.projet)
        c = r["comptes"]
        self.assertEqual(c['mesurables'], 1)
        self.assertEqual(c['sous_le_seuil_de_match'], 1)
        # Une cecite n'est pas un decalage : rien d'autre ne s'allume.
        self.assertEqual(c.get('decale', 0), 0)

    # ── H6 : la dimension ─────────────────────────────────────────────────
    def test_une_empreinte_d_une_autre_dimension_est_comptee_pas_ignoree(self):
        bon = vecteur(1)
        b = Bati().photo('a.jpg', [detection(vecteur(1, dim=DIM * 2))])
        b.fiche('Inti', [bon], [('a.jpg', 0)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"]['dimension_incompatible'], 1)

    def test_signature_ecarte_les_refs_perimees_et_les_compte(self):
        pe = {"refs": [b64(vecteur(1)), b64(vecteur(2)),
                       b64(vecteur(3, dim=DIM * 2))]}
        P, hors = A.signature(pe)
        self.assertEqual(P.shape[0], DIM)
        self.assertEqual(hors, 1)

    def test_signature_absente_rend_none(self):
        P, hors = A.signature({"refs": []})
        self.assertIsNone(P)
        self.assertEqual(hors, 0)

    # ── ce qui est ECARTE doit etre NOMME ─────────────────────────────────
    def test_une_fiche_sans_signature_est_nommee_avec_ses_couples(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)])
        b.fiche('Puma', [], [('a.jpg', 0)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["ecartes"]['fiche_sans_signature'], 1)
        self.assertEqual(r["comptes"]['couples_de_fiche_sans_signature'], 1)
        self.assertEqual(r["comptes"].get('couples', 0), 0)

    def test_une_fiche_sans_rattachement_est_nommee(self):
        b = Bati().fiche('Kevin', [vecteur(1)], [])
        r = b.mesurer(self.projet)
        self.assertEqual(r["ecartes"]['fiche_sans_rattachement'], 1)

    def test_un_couple_cite_deux_fois_n_est_compte_qu_une_fois(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)])
        b.fiche('Inti', [v], [('a.jpg', 0), ('a.jpg', 0)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["comptes"]['couple_cite_deux_fois'], 1)
        self.assertEqual(r["comptes"]['couples'], 1)

    # ── le deuxieme chemin ────────────────────────────────────────────────
    def test_le_croisement_par_le_tag_separe_les_deux_sens(self):
        v = vecteur(1)
        b = Bati()
        b.photo('a.jpg', [detection(v)], tags_kw=['animal:Inti'])
        b.photo('b.jpg', [detection(v)], tags_kw=[])           # citee, pas taguee
        b.photo('c.jpg', [detection(v)], tags_kw=['animal:Inti'])  # taguee, pas citee
        b.fiche('Inti', [v], [('a.jpg', 0), ('b.jpg', 0)])
        cr = b.mesurer(self.projet)["croisement_tag"]['Inti']
        self.assertEqual(cr['photos_citees_par_la_fiche'], 2)
        self.assertEqual(cr['photos_portant_le_tag'], 2)
        self.assertEqual(cr['citees_sans_le_tag'], 1)
        self.assertEqual(cr['taguees_sans_couple'], 1)

    def test_le_tag_se_lit_dans_kw_fr_et_sans_egard_a_la_casse(self):
        """Le zero parfait du 22/08 : le banc lisait `kw`, la prod ecrit
        `kw_fr`, et `_kw_has` compare en minuscules. Douze fiches a zero photo
        taguee etaient une alarme sur l'instrument, pas une mesure du fonds."""
        v = vecteur(1)
        b = Bati()
        b.photo('a.jpg', [detection(v)], tags_kw=['ANIMAL:inti'])
        b.tags['b.jpg'] = {"kw": ['animal:Inti']}   # l'ancien champ : ignore
        b.fiche('Inti', [v], [('a.jpg', 0)])
        cr = b.mesurer(self.projet)["croisement_tag"]['Inti']
        self.assertEqual(cr['photos_portant_le_tag'], 1)
        self.assertEqual(cr['citees_sans_le_tag'], 0)

    # ── la regle vient de la prod ─────────────────────────────────────────
    def test_une_constante_disparue_arrete_le_banc(self):
        """Mieux vaut ne rien mesurer que mesurer avec une valeur inventee."""
        tronque = SERVER_FACTICE.replace("PET_MATCH_SIM = 0.55\n", "")
        (Path(self.projet) / 'server.py').write_text(tronque, encoding='utf-8')
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)]).fiche('Inti', [v],
                                                        [('a.jpg', 0)])
        with self.assertRaises(SystemExit):
            b.mesurer(self.projet)

    def test_seuils_txt_surcharge_le_seuil_comme_la_prod(self):
        (Path(self.projet) / 'seuils.txt').write_text(
            "PET_MATCH_SIM = 0.90\n", encoding='utf-8')
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)]).fiche('Inti', [v],
                                                        [('a.jpg', 0)])
        r = b.mesurer(self.projet)
        self.assertEqual(r["constantes"]['PET_MATCH_SIM'], 0.90)
        self.assertEqual(r["surcharges"], {'PET_MATCH_SIM': 0.90})

    def test_le_rapport_s_affiche_sans_exploser(self):
        v = vecteur(1)
        b = Bati().photo('a.jpg', [detection(v)]).fiche('Inti', [v],
                                                        [('a.jpg', 0)])
        texte = A.afficher(b.mesurer(self.projet))
        self.assertIn('RATTACHEMENTS ANIMAUX', texte)
        self.assertIn('PAR FICHE', texte)


class AJugerTest(unittest.TestCase):
    """Le mode `--a-juger` : la contrepartie d'un couple, et rien de plus.

    Chaque verdict a son cas, et deux tests portent sur ce que l'instrument
    REFUSE de conclure — c'est la moitie qui compte.
    """

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.projet = self._tmp.name
        (Path(self.projet) / 'server.py').write_text(SERVER_FACTICE,
                                                     encoding='utf-8')
        self.addCleanup(self._tmp.cleanup)

    def journal(self, ancienne, nouvelle):
        d = Path(self.projet) / 'docs'
        d.mkdir(exist_ok=True)
        (d / 'undo_rangement_1.json').write_text(
            json.dumps({"operations": [{"old_key": ancienne,
                                        "new_key": nouvelle}]}),
            encoding='utf-8')

    def morte(self, r):
        return r["a_juger"]["cles_mortes"][0]

    # ── la preuve FORTE : le geste, ecrit par le programme qui l'a fait ────
    def test_le_journal_donne_la_contrepartie_et_l_index_est_conserve(self):
        v = vecteur(1)
        b = (Bati()
             .photo('neuf/a.jpg', [detection(v)], tags_kw=['animal:Inti'])
             .fiche('Inti', [v], [('vieux/a.jpg', 0), ('neuf/a.jpg', 0)]))
        b.animaux['vieux/a.jpg'] = {"animals": [], "n": 0}
        self.journal('vieux/a.jpg', 'neuf/a.jpg')
        cas = self.morte(b.mesurer(self.projet, a_juger=True))
        self.assertEqual(cas['verdict'], 'recle_par_journal')
        self.assertEqual(cas['cible'], 'neuf/a.jpg')
        self.assertEqual(cas['i'], 0)

    # ── la preuve FAIBLE : elle n'est retenue que corroboree deux fois ─────
    def test_le_meme_nom_corrobore_deux_fois_suffit(self):
        v = vecteur(1)
        b = (Bati()
             .photo('vivant/a.jpg', [detection(v)], tags_kw=['animal:Inti'])
             .fiche('Inti', [v], [('mort/a.jpg', 0), ('vivant/a.jpg', 0)]))
        cas = self.morte(b.mesurer(self.projet, a_juger=True))
        self.assertEqual(cas['verdict'], 'recle_par_meme_nom')
        self.assertEqual(cas['preuve'], A.PREUVE_MEME_NOM)

    def test_le_meme_nom_sans_le_tag_reste_a_l_oeil(self):
        v = vecteur(1)
        b = (Bati()
             .photo('vivant/a.jpg', [detection(v)])
             .fiche('Inti', [v], [('mort/a.jpg', 0), ('vivant/a.jpg', 0)]))
        cas = self.morte(b.mesurer(self.projet, a_juger=True))
        self.assertEqual(cas['verdict'], 'a_l_oeil')
        self.assertIn('pas_de_tag', cas['contre'])

    def test_un_index_absent_chez_la_cible_interdit_la_recle(self):
        """Re-cler la-dessus fabriquerait le mensonge muet de
        `_serve_animalcrop` : un index hors bornes qui sert l'animal 0."""
        v = vecteur(1)
        b = (Bati()
             .photo('vivant/a.jpg', [detection(v)], tags_kw=['animal:Inti'])
             .fiche('Inti', [v], [('mort/a.jpg', 5), ('vivant/a.jpg', 0)]))
        cas = self.morte(b.mesurer(self.projet, a_juger=True))
        self.assertEqual(cas['verdict'], 'a_l_oeil')
        self.assertIn('index_absent_chez_la_cible', cas['contre'])

    def test_deux_candidates_de_meme_nom_ne_sont_pas_une_preuve(self):
        v = vecteur(1)
        b = (Bati()
             .photo('x/a.jpg', [detection(v)], tags_kw=['animal:Inti'])
             .photo('y/a.jpg', [detection(v)], tags_kw=['animal:Inti'])
             .fiche('Inti', [v], [('mort/a.jpg', 0), ('x/a.jpg', 0)]))
        cas = self.morte(b.mesurer(self.projet, a_juger=True))
        self.assertEqual(cas['verdict'], 'sans_contrepartie')
        self.assertIsNone(cas['cible'])

    def test_sans_contrepartie_rien_n_est_propose(self):
        v = vecteur(1)
        b = (Bati().photo('vivant/b.jpg', [detection(v)])
             .fiche('Inti', [v], [('mort/a.jpg', 0), ('vivant/b.jpg', 0)]))
        cas = self.morte(b.mesurer(self.projet, a_juger=True))
        self.assertEqual(cas['verdict'], 'sans_contrepartie')
        self.assertEqual(cas['pour'], [])

    # ── l'espece : un recalage, pas un retrait ────────────────────────────
    def test_une_seule_detection_de_la_bonne_espece_nomme_l_index_a_viser(self):
        v = vecteur(1)
        b = (Bati()
             .photo('a.jpg', [detection(v, species='dog'), detection(v)])
             .fiche('Inti', [v], [('a.jpg', 0)], species='cat'))
        cas = b.mesurer(self.projet, a_juger=True)["a_juger"]["especes"][0]
        self.assertEqual(cas['verdict'], 'recalage_evident')
        self.assertEqual([x['i'] for x in cas['candidats']], [1])
        self.assertIsNotNone(cas['candidats'][0]['sim'])

    def test_deux_detections_de_la_bonne_espece_partent_a_l_oeil(self):
        v = vecteur(1)
        b = (Bati()
             .photo('a.jpg', [detection(v, species='dog'), detection(v),
                              detection(vecteur(2))])
             .fiche('Inti', [v], [('a.jpg', 0)], species='cat'))
        cas = b.mesurer(self.projet, a_juger=True)["a_juger"]["especes"][0]
        self.assertEqual(cas['verdict'], 'a_l_oeil_plusieurs')

    def test_le_score_du_designe_departage_les_deux_lectures(self):
        """Un `dog` qui ressemble au chat de la fiche est un chat mal
        ETIQUETE ; sans ce chiffre, H4 se croit sur parole."""
        v = vecteur(1)
        b = (Bati()
             .photo('a.jpg', [detection(v, species='dog')])
             .fiche('Inti', [v], [('a.jpg', 0)], species='cat'))
        cas = b.mesurer(self.projet, a_juger=True)["a_juger"]["especes"][0]
        self.assertGreater(cas['sim_designe'], 0.9)
        self.assertEqual(cas['detections'], 1)

    def test_un_designe_sans_vecteur_ne_fabrique_pas_de_score(self):
        v = vecteur(1)
        b = (Bati()
             .photo('a.jpg', [detection(None, species='dog')])
             .fiche('Inti', [v], [('a.jpg', 0)], species='cat'))
        cas = b.mesurer(self.projet, a_juger=True)["a_juger"]["especes"][0]
        self.assertIsNone(cas['sim_designe'])

    def test_une_cle_morte_dit_si_ses_detections_ont_survecu(self):
        v = vecteur(1)
        b = (Bati().photo('vivant.jpg', [detection(v)])
             .fiche('Inti', [v], [('mort/a.jpg', 0), ('vivant.jpg', 0)]))
        b.animaux['mort/a.jpg'] = {"animals": [detection(v)], "n": 1}
        cas = self.morte(b.mesurer(self.projet, a_juger=True))
        self.assertEqual(cas['detections_restantes'], 1)

    def test_aucune_detection_de_l_espece_ne_propose_aucun_recalage(self):
        v = vecteur(1)
        b = (Bati()
             .photo('a.jpg', [detection(v, species='dog')])
             .fiche('Inti', [v], [('a.jpg', 0)], species='cat'))
        cas = b.mesurer(self.projet, a_juger=True)["a_juger"]["especes"][0]
        self.assertEqual(cas['verdict'], 'aucune_detection_de_l_espece')
        self.assertEqual(cas['candidats'], [])

    def test_une_detection_non_nommable_n_est_pas_un_candidat(self):
        v = vecteur(1)
        b = (Bati()
             .photo('a.jpg', [detection(v, species='dog'),
                              detection(v, suspect=True)])
             .fiche('Inti', [v], [('a.jpg', 0)], species='cat'))
        cas = b.mesurer(self.projet, a_juger=True)["a_juger"]["especes"][0]
        self.assertEqual(cas['verdict'], 'aucune_detection_de_l_espece')

    # ── ce que le plafond coupe se COMPTE ─────────────────────────────────
    def test_le_plafond_ne_coupe_jamais_en_silence(self):
        v = vecteur(1)
        couples = [(f'mort/{i}.jpg', 0) for i in range(4)]
        b = (Bati().photo('vivant.jpg', [detection(v)])
             .fiche('Inti', [v], couples + [('vivant.jpg', 0)]))
        ancien = A.PLAFOND_A_JUGER
        A.PLAFOND_A_JUGER = 2
        try:
            r = b.mesurer(self.projet, a_juger=True)
        finally:
            A.PLAFOND_A_JUGER = ancien
        self.assertEqual(len(r["a_juger"]["cles_mortes"]), 2)
        self.assertEqual(r["comptes"]['cles_mortes_non_listees'], 2)

    # ── l'instrument reste un instrument ──────────────────────────────────
    def test_a_juger_n_ecrit_rien(self):
        v = vecteur(1)
        b = (Bati().photo('vivant/a.jpg', [detection(v)], tags_kw=['animal:Inti'])
             .fiche('Inti', [v], [('mort/a.jpg', 0), ('vivant/a.jpg', 0)]))
        avant = copy.deepcopy((b.tags, b.animaux, b.pets))
        b.mesurer(self.projet, a_juger=True)
        self.assertEqual(avant, (b.tags, b.animaux, b.pets))

    def test_sans_le_drapeau_le_dossier_n_existe_pas(self):
        v = vecteur(1)
        b = (Bati().photo('a.jpg', [detection(v)])
             .fiche('Inti', [v], [('a.jpg', 0)]))
        self.assertNotIn('a_juger', b.mesurer(self.projet))

    def test_le_rapport_nomme_chaque_cas_et_son_verdict(self):
        v = vecteur(1)
        b = (Bati()
             .photo('vivant/a.jpg', [detection(v, species='dog')],
                    tags_kw=['animal:Inti'])
             .fiche('Inti', [v], [('mort/a.jpg', 0), ('vivant/a.jpg', 0)],
                    species='cat'))
        texte = A.afficher(b.mesurer(self.projet, a_juger=True))
        self.assertIn('LES COUPLES A TRANCHER', texte)
        self.assertIn('a_l_oeil', texte)
        self.assertIn('a.jpg', texte)
        self.assertIn('VERDICTS', texte)


if __name__ == '__main__':
    unittest.main()
