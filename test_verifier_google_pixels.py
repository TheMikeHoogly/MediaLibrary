#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_google_pixels.py` — sans NAS, sans Google, sans PIL.

Ce que ces tests tiennent
-------------------------
1. **La metadonnee ne fait pas une image differente.** C'est toute la these :
   le NAS porte les memes pixels PLUS le XMP que la phototheque y ecrit. Une
   paire qui ne differe que par un `APPn` doit sortir MEME_IMAGE.
2. **Un vrai re-encodage doit sortir DIFFERENT.** Deux JPEG ré-encodés n'ont
   pas les memes tables de quantification : c'est ce qui separe l'hypothese
   << Google a compresse >> de l'hypothese << on a ecrit dedans >>.
3. **La preuve pas chere connait sa limite, et le test la GRAVE.** Meme cadre
   et meme longueur ne prouvent pas les memes octets. Sans `--octets`, deux
   flux de meme longueur passent pour identiques : c'est ecrit ici noir sur
   blanc, pour que personne ne prenne la tranche rapide pour la preuve.
4. **Ce qui n'est pas un JPEG est HORS PORTEE, compte et dit** — jamais vert.
5. **Une tranche ne conclut pas sur le tout.**

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_google_pixels as P  # noqa: E402


def segment(marqueur, charge):
    n = len(charge) + 2
    return bytes([0xFF, marqueur, n >> 8, n & 0xFF]) + charge


def jpeg(scan=b'\x11' * 64, dqt=b'\x00' + b'\x10' * 64, meta=None,
         bourrage=False):
    """Un JPEG minimal mais STRUCTURELLEMENT vrai : SOI, tables, cadre, SOS.

    `meta` : la charge d'un `APP1` — l'EXIF/XMP que la phototheque ecrit."""
    out = b'\xff\xd8'
    if meta is not None:
        out += segment(0xE1, meta)
    out += segment(0xDB, dqt)
    out += segment(0xC0, b'\x08\x00\x10\x00\x10\x01\x01\x11\x00')
    out += segment(0xC4, b'\x00' + b'\x01' * 28)
    if bourrage:
        out += b'\xff\xff'                 # bourrage legal avant un marqueur
    out += segment(0xDA, b'\x01\x01\x00\x00\x3f\x00')
    return out + scan + b'\xff\xd9'


def ecrire(dossier, nom, octets):
    p = Path(dossier) / nom
    p.write_bytes(octets)
    return str(p)


class LaTheseDuXMP(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="test_pix_")

    def test_meme_image_plus_une_metadonnee_est_la_MEME_IMAGE(self):
        g = ecrire(self.d, 'g.jpg', jpeg())
        n = ecrire(self.d, 'n.jpg', jpeg(meta=b'XMP' + b'\x00' * 4000))
        v, detail = P.juger_paire(g, n)
        self.assertEqual(v, 'MEME_IMAGE', detail)

    def test_l_ecart_de_taille_est_exactement_l_ecart_d_entete(self):
        # Le controle qui vaut le reste : si tout l'ecart est AVANT le flux,
        # alors ce qui differe est de la metadonnee, et rien d'autre.
        g = ecrire(self.d, 'g.jpg', jpeg())
        n = ecrire(self.d, 'n.jpg', jpeg(meta=b'X' * 4000))
        ecart_taille = Path(n).stat().st_size - Path(g).stat().st_size
        sg, sn = P.signature_jpeg(g), P.signature_jpeg(n)
        self.assertEqual(sn[1] - sg[1], ecart_taille)
        self.assertEqual(sg[2], sn[2])
        self.assertEqual((sg[3], sn[3]), (0, 0))     # aucun trailer

    def test_un_fichier_STRICTEMENT_identique_passe_aussi(self):
        g = ecrire(self.d, 'g.jpg', jpeg())
        n = ecrire(self.d, 'n.jpg', jpeg())
        self.assertEqual(P.juger_paire(g, n, octets=True)[0], 'MEME_IMAGE')

    def test_le_bourrage_FF_ne_casse_pas_la_lecture(self):
        g = ecrire(self.d, 'g.jpg', jpeg())
        n = ecrire(self.d, 'n.jpg', jpeg(bourrage=True))
        self.assertEqual(P.juger_paire(g, n)[0], 'MEME_IMAGE')


class CeQuiEstVraimentDifferent(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="test_pix2_")

    def test_des_tables_de_quantification_differentes_sont_un_RE_ENCODAGE(self):
        g = ecrire(self.d, 'g.jpg', jpeg())
        n = ecrire(self.d, 'n.jpg', jpeg(dqt=b'\x00' + b'\x40' * 64))
        v, detail = P.juger_paire(g, n)
        self.assertEqual(v, 'IMAGE_DIFFERENTE', detail)

    def test_un_flux_de_longueur_differente_est_signale(self):
        g = ecrire(self.d, 'g.jpg', jpeg(scan=b'\x11' * 64))
        n = ecrire(self.d, 'n.jpg', jpeg(scan=b'\x11' * 80))
        v, detail = P.juger_paire(g, n)
        self.assertEqual(v, 'FLUX_DIFFERENT', detail)
        self.assertIn('flux', detail)

    def test_LA_LIMITE_de_la_preuve_pas_chere_est_gravee_ici(self):
        # Meme longueur, octets differents. Sans --octets le banc dit
        # MEME_IMAGE : la tranche rapide n'est PAS la preuve, et le savoir
        # fait partie de l'instrument.
        g = ecrire(self.d, 'g.jpg', jpeg(scan=b'\x11' * 64))
        n = ecrire(self.d, 'n.jpg', jpeg(scan=b'\x22' * 64))
        self.assertEqual(P.juger_paire(g, n)[0], 'MEME_IMAGE')
        self.assertEqual(P.juger_paire(g, n, octets=True)[0], 'FLUX_DIFFERENT')


class HorsPortee(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="test_pix3_")

    def test_ce_qui_n_est_pas_un_JPEG_sort_HORS_PORTEE(self):
        g = ecrire(self.d, 'g.mp4', b'\x00\x00\x00\x18ftypmp42')
        n = ecrire(self.d, 'n.jpg', jpeg())
        v, detail = P.juger_paire(g, n)
        self.assertEqual(v, 'HORS_PORTEE')
        self.assertIn('Google', detail)

    def test_un_fichier_absent_sort_HORS_PORTEE_pas_en_erreur(self):
        n = ecrire(self.d, 'n.jpg', jpeg())
        self.assertEqual(P.juger_paire(self.d + '/rien.jpg', n)[0],
                         'HORS_PORTEE')

    def test_un_jpeg_tronque_avant_le_SOS_sort_HORS_PORTEE(self):
        g = ecrire(self.d, 'g.jpg', jpeg()[:20])
        n = ecrire(self.d, 'n.jpg', jpeg())
        self.assertEqual(P.juger_paire(g, n)[0], 'HORS_PORTEE')


class LesPaires(unittest.TestCase):

    def test_une_paire_sans_chemin_NAS_n_est_pas_jugeable(self):
        d = tempfile.mkdtemp(prefix="test_pix4_")
        r = Path(d) / 'r.json'
        r.write_text('{"par_verdict": {"PROBABLE": ['
                     '{"nom": "a.jpg", "chemin_google": "g", "chemin_nas": "n"},'
                     '{"nom": "b.jpg", "chemin_google": "g", "chemin_nas": null}'
                     ']}}', encoding='utf-8')
        self.assertEqual(len(P.paires_probables(r)), 1)

    def test_un_rapport_sans_PROBABLE_rend_une_liste_vide(self):
        d = tempfile.mkdtemp(prefix="test_pix5_")
        r = Path(d) / 'r.json'
        r.write_text('{"par_verdict": {"CERTAIN": []}}', encoding='utf-8')
        self.assertEqual(P.paires_probables(r), [])


class LeRapport(unittest.TestCase):

    def _dit(self, compte, juges, total, ecarts=()):
        lignes = []
        ok = P.rapport(compte, {}, list(ecarts), total, juges, False,
                       ecrire=lignes.append)
        return ok, lignes

    def test_tout_juge_et_tout_pareil_rend_vrai(self):
        ok, lignes = self._dit({'MEME_IMAGE': 10}, 10, 10, ecarts=[4000] * 10)
        self.assertTrue(ok)
        self.assertTrue(any('FAUSSE' in l for l in lignes))

    def test_une_TRANCHE_ne_conclut_pas_sur_le_tout(self):
        ok, lignes = self._dit({'MEME_IMAGE': 10}, 10, 100)
        self.assertFalse(ok)
        self.assertTrue(any('ne conclut pas' in l or 'PAS ete' in l
                            for l in lignes))

    def test_aucune_paire_jugee_ne_rend_PAS_vert(self):
        ok, lignes = self._dit({}, 0, 0)
        self.assertFalse(ok)
        self.assertTrue(any('ne prouve rien' in l for l in lignes))

    def test_un_HORS_PORTEE_empeche_le_vert(self):
        ok, _l = self._dit({'MEME_IMAGE': 9, 'HORS_PORTEE': 1}, 10, 10)
        self.assertFalse(ok)

    def test_l_ecart_median_est_dit_quand_il_y_en_a_un(self):
        _ok, lignes = self._dit({'MEME_IMAGE': 3}, 3, 3, ecarts=[4000, 4100, 4200])
        self.assertTrue(any('METADONNEE' in l for l in lignes))


class LaListeComplete(unittest.TestCase):
    """Un compte dit qu'il reste 215 photos ; seule la LISTE dit lesquelles."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="test_pix6_")

    def test_tout_ce_qui_n_est_pas_identique_est_LISTE_pas_seulement_compte(self):
        g = ecrire(self.d, 'g.jpg', jpeg())
        n_ok = ecrire(self.d, 'n.jpg', jpeg(meta=b'X' * 100))
        n_ko = ecrire(self.d, 'k.jpg', jpeg(dqt=b'\x00' + b'\x40' * 64))
        paires = [{'nom': 'ok.jpg', 'chemin_google': g, 'chemin_nas': n_ok}]
        paires += [{'nom': 'ko%d.jpg' % i, 'chemin_google': g,
                    'chemin_nas': n_ko} for i in range(P.LISTE_MAX + 5)]
        compte, exemples, _e, restantes = P.mesurer(
            paires, ecrire=lambda *x: None, chaque=0)
        self.assertEqual(compte['MEME_IMAGE'], 1)
        # La console est BORNEE, la liste ne l'est pas.
        self.assertEqual(len(exemples['IMAGE_DIFFERENTE']), P.LISTE_MAX)
        self.assertEqual(len(restantes), P.LISTE_MAX + 5)
        self.assertNotIn('ok.jpg', [r['nom'] for r in restantes])

    def test_chaque_restante_porte_ses_DEUX_chemins(self):
        g = ecrire(self.d, 'g.jpg', jpeg())
        n = ecrire(self.d, 'n.jpg', jpeg(scan=b'\x11' * 80))
        _c, _e, _ec, restantes = P.mesurer(
            [{'nom': 'a.jpg', 'chemin_google': g, 'chemin_nas': n}],
            ecrire=lambda *x: None, chaque=0)
        self.assertEqual(restantes[0]['verdict'], 'FLUX_DIFFERENT')
        self.assertEqual(restantes[0]['chemin_google'], g)
        self.assertEqual(restantes[0]['chemin_nas'], n)


class LeTrailerNEstPasLImage(unittest.TestCase):
    """Le rouge du 27/08, grave. 173 photos sont sorties << flux different >>
    alors qu'elles portaient TOUTES, cote Google, des octets APRES le JPEG —
    mediane 2 046, exactement l'ecart mesure. L'instrument rangeait le
    trailer dans l'image : il ne mesurait pas ce qu'il disait."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="test_pix7_")

    def test_le_trailer_est_compte_A_PART(self):
        g = ecrire(self.d, 'g.jpg', jpeg() + b'\x00' * 2046)
        s = P.signature_jpeg(g)
        self.assertEqual(s[3], 2046)

    def test_un_trailer_d_un_seul_cote_n_est_PAS_un_flux_different(self):
        g = ecrire(self.d, 'g.jpg', jpeg() + b'MOTION' * 341)
        n = ecrire(self.d, 'n.jpg', jpeg(meta=b'X' * 4000))
        v, detail = P.juger_paire(g, n)
        self.assertEqual(v, 'MEME_IMAGE_TRAILER', detail)
        self.assertIn('apres le JPEG', detail)

    def test_et_ce_n_est_pas_vert_non_plus(self):
        # Une photo animee vit dans ce trailer : le NAS l'a peut-etre perdue.
        # Ni un ecart d'image, ni un non-evenement.
        lignes = []
        ok = P.rapport({'MEME_IMAGE_TRAILER': 5}, {}, [], 5, 5, False,
                       ecrire=lignes.append)
        self.assertFalse(ok)
        self.assertTrue(any('MEME_IMAGE_TRAILER' in l for l in lignes))

    def test_un_vrai_flux_different_reste_un_flux_different(self):
        g = ecrire(self.d, 'g.jpg', jpeg(scan=b'\x11' * 64))
        n = ecrire(self.d, 'n.jpg', jpeg(scan=b'\x11' * 96))
        self.assertEqual(P.juger_paire(g, n)[0], 'FLUX_DIFFERENT')

    def test_un_JPEG_sans_EOI_sort_HORS_PORTEE(self):
        g = ecrire(self.d, 'g.jpg', jpeg()[:-2])
        n = ecrire(self.d, 'n.jpg', jpeg())
        self.assertEqual(P.juger_paire(g, n)[0], 'HORS_PORTEE')


class Reprendre(unittest.TestCase):
    """Re-juger ce qui restait, sans relire le fonds entier."""

    def test_les_restantes_d_un_rapport_se_relisent_comme_des_paires(self):
        d = tempfile.mkdtemp(prefix="test_pix8_")
        g = ecrire(d, 'g.jpg', jpeg() + b'\x00' * 100)
        n = ecrire(d, 'n.jpg', jpeg())
        r = Path(d) / 'pix.json'
        r.write_text(json.dumps({'restantes': [
            {'nom': 'a.jpg', 'verdict': 'FLUX_DIFFERENT', 'detail': '',
             'chemin_google': g, 'chemin_nas': n}]}), encoding='utf-8')
        code = P.main(['--reprendre', str(r)])
        self.assertEqual(code, 1)          # trailer : nomme, donc pas vert

    def test_l_option_se_REPETE_au_lieu_de_prendre_des_virgules(self):
        # Rouge observe au banc : le canal n'admet que [A-Za-z0-9_.:/=-], une
        # virgule y est REFUSEE. Un argument que le canal refuse n'existe pas.
        d = tempfile.mkdtemp(prefix="test_pix9_")
        g = ecrire(d, 'g.jpg', jpeg())
        n = ecrire(d, 'n.jpg', jpeg(meta=b'X' * 50))
        noms = []
        for i in (1, 2):
            r = Path(d) / ('pix%d.json' % i)
            r.write_text(json.dumps({'restantes': [
                {'nom': 'a%d.jpg' % i, 'chemin_google': g,
                 'chemin_nas': n}]}), encoding='utf-8')
            noms += ['--reprendre', str(r)]
        self.assertEqual(P.main(noms), 0)      # deux rapports, deux paires


if __name__ == '__main__':
    unittest.main(verbosity=0)
