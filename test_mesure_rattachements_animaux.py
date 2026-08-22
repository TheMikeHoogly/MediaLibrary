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

    def mesurer(self, projet, ecart=0.10, exemples=12):
        return A._mesurer(FauxStore(self.tags), FauxStore(self.animaux),
                          FauxStore(self.pets), projet, ecart, exemples)


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


if __name__ == '__main__':
    unittest.main()
