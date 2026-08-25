#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de `verifier_photos_google.py` — sans NAS, sans Google.

Ce que ces tests tiennent
-------------------------
Cet instrument autorise une SUPPRESSION de 75 Go chez un tiers. Ce qu'il dit
ne se rattrape pas au clavier. Les tests portent donc d'abord sur ce qu'il
REFUSE d'affirmer :

1. **Un ABSENT interdit tout.** Tant qu'une seule photo n'existe que chez
   Google, le rapport dit NE RIEN EFFACER — le compte des autres ne rachete
   pas celle-la.
2. **La certitude a une definition, et une seule** : meme nom ET meme taille.
   Un nom qui correspond avec une taille differente est PROBABLE, pas certain.
3. **Le titre du sidecar prime sur le nom exporte.** Takeout tronque les noms
   longs et suffixe les collisions ; se fier au nom du fichier ferait declarer
   ABSENTES des photos que le NAS porte.
4. **Il n'efface RIEN** — famille `verifier_`.

SORTIE EN ASCII PUR (console cp1252 de l'agent git).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verifier_photos_google as G  # noqa: E402


def index(*couples):
    """(nom, octets) ou (nom, octets, chemin) -> l'index du NAS."""
    d = {}
    for c in couples:
        nom, octets = c[0], c[1]
        chemin = c[2] if len(c) > 2 else ("\\\\NAS\\Photos\\" + nom)
        d.setdefault(nom.lower(), []).append((chemin, octets))
    return d


def media(nom, octets, nom_exporte=None, quand=None):
    return {'chemin': "D:\\Takeout\\" + (nom_exporte or nom), 'nom': nom,
            'nom_exporte': nom_exporte or nom, 'octets': octets,
            'quand': quand}


class LesQuatreVerdicts(unittest.TestCase):

    def test_meme_nom_meme_taille_est_CERTAIN(self):
        v, chemin, _d = G.juger(media("IMG_1.jpg", 100),
                                index(("IMG_1.jpg", 100)))
        self.assertEqual(v, 'CERTAIN')
        self.assertIn("IMG_1.jpg", chemin)

    def test_meme_nom_taille_DIFFERENTE_est_PROBABLE_pas_certain(self):
        """Google re-encode en mode economiseur : la taille change, la photo
        est la meme. Probable n'est pas certain, et on n'efface pas dessus."""
        v, _c, detail = G.juger(media("IMG_1.jpg", 100),
                                index(("IMG_1.jpg", 82)))
        self.assertEqual(v, 'PROBABLE')
        self.assertIn("82", detail)

    def test_nom_inconnu_du_NAS_est_ABSENT(self):
        v, chemin, _d = G.juger(media("IMG_9.jpg", 100),
                                index(("IMG_1.jpg", 100)))
        self.assertEqual(v, 'ABSENT')
        self.assertIsNone(chemin)

    def test_plusieurs_copies_de_MEME_taille_restent_une_CERTITUDE(self):
        """Le NAS la porte deux fois : pour la question posee, c'est oui."""
        v, _c, detail = G.juger(
            media("IMG_1.jpg", 100),
            index(("IMG_1.jpg", 100, "\\\\NAS\\2019\\IMG_1.jpg"),
                  ("IMG_1.jpg", 100, "\\\\NAS\\2020\\IMG_1.jpg")))
        self.assertEqual(v, 'CERTAIN')
        self.assertIn("2 copies", detail)

    def test_la_casse_du_nom_ne_fait_pas_rater_une_photo(self):
        v, _c, _d = G.juger(media("img_1.JPG", 100),
                            index(("IMG_1.jpg", 100)))
        self.assertEqual(v, 'CERTAIN')


class LeTitreDuSidecarPrime(unittest.TestCase):

    def test_le_nom_tronque_par_Takeout_ne_fait_pas_declarer_ABSENT(self):
        """Takeout tronque les noms longs ; le sidecar garde le vrai."""
        m = media("un_nom_tres_long_original.jpg", 100,
                  nom_exporte="un_nom_tres_long_orig.jpg")
        v, _c, _d = G.juger(m, index(("un_nom_tres_long_original.jpg", 100)))
        self.assertEqual(v, 'CERTAIN')

    def test_a_defaut_de_titre_le_nom_exporte_sert_de_repli(self):
        m = media("IMG(1).jpg", 100, nom_exporte="IMG(1).jpg")
        v, _c, _d = G.juger(m, index(("IMG(1).jpg", 100)))
        self.assertEqual(v, 'CERTAIN')

    def test_le_sidecar_est_lu_sous_ses_DEUX_noms_connus(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_gphotos_"))
        (tmp / "a.jpg").write_bytes(b"x" * 10)
        (tmp / "a.jpg.json").write_text(
            json.dumps({'title': 'vrai_a.jpg',
                        'photoTakenTime': {'timestamp': '1600000000'}}),
            encoding='utf-8')
        (tmp / "b.jpg").write_bytes(b"x" * 10)
        (tmp / "b.jpg.supplemental-metadata.json").write_text(
            json.dumps({'title': 'vrai_b.jpg'}), encoding='utf-8')
        noms = {m['nom_exporte']: m['nom'] for m in G.inventaire_takeout(tmp)}
        self.assertEqual(noms.get("a.jpg"), "vrai_a.jpg")
        self.assertEqual(noms.get("b.jpg"), "vrai_b.jpg")

    def test_un_sidecar_illisible_ne_fait_pas_tomber_l_inventaire(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_gphotos2_"))
        (tmp / "a.jpg").write_bytes(b"x" * 10)
        (tmp / "a.jpg.json").write_text("{ pas du json", encoding='utf-8')
        m = G.inventaire_takeout(tmp)
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0]['nom'], "a.jpg")


class CeQuiNEstPasUnMedia(unittest.TestCase):

    def test_les_json_et_html_de_Takeout_ne_sont_pas_comptes(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_gphotos3_"))
        for nom in ("a.jpg", "a.jpg.json", "archive_browser.html",
                    "print-subscriptions.json"):
            (tmp / nom).write_bytes(b"x" * 5)
        self.assertEqual([m['nom'] for m in G.inventaire_takeout(tmp)],
                         ["a.jpg"])


class UnSeulABSENT_INTERDIT_TOUT(unittest.TestCase):

    def test_le_rapport_dit_NE_RIEN_EFFACER(self):
        pv = G.verifier([media("ok.jpg", 100), media("perdue.jpg", 50)],
                        index(("ok.jpg", 100)))
        dit = []
        G.rapport(pv, ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("NE RIEN EFFACER", texte)
        self.assertIn("perdue.jpg", texte)

    def test_le_code_de_sortie_le_dit_aussi(self):
        """Un banc qui rend 0 sur un fonds incomplet serait un feu vert."""
        pv = G.verifier([media("perdue.jpg", 50)], index())
        r = G.rapport(pv, ecrire=lambda *x: None)
        self.assertEqual(r['compte'].get('ABSENT'), 1)

    def test_tout_certain_autorise_et_RAPPELLE_la_corbeille(self):
        pv = G.verifier([media("ok.jpg", 100)], index(("ok.jpg", 100)))
        dit = []
        G.rapport(pv, ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("TOUT est sur le NAS", texte)
        self.assertIn("CORBEILLE", texte)
        self.assertNotIn("NE RIEN EFFACER", texte)

    def test_sans_empreinte_le_rapport_DIT_que_c_est_une_presomption(self):
        pv = G.verifier([media("ok.jpg", 100)], index(("ok.jpg", 100)))
        dit = []
        G.rapport(pv, ecrire=dit.append)
        self.assertIn("Empreintes NON calculees", "\n".join(dit))

    def test_un_export_vide_ne_se_lit_pas_comme_un_feu_vert(self):
        dit = []
        G.rapport(G.verifier([], index()), ecrire=dit.append)
        texte = "\n".join(dit)
        self.assertIn("aucun media", texte)
        self.assertNotIn("peuvent etre liberes", texte)

    def test_ce_qui_n_est_pas_liste_est_COMPTE(self):
        absents = [media("p%03d.jpg" % i, 10) for i in range(G.LISTE_MAX + 4)]
        dit = []
        G.rapport(G.verifier(absents, index()), ecrire=dit.append)
        self.assertIn("et 4 autre(s) non listees", "\n".join(dit))


class LEmpreinte(unittest.TestCase):

    def test_meme_taille_mais_octets_DIFFERENTS_devient_AMBIGU(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_gphotos4_"))
        g, n = tmp / "g.jpg", tmp / "n.jpg"
        g.write_bytes(b"a" * 10)
        n.write_bytes(b"b" * 10)
        m = {'chemin': str(g), 'nom': "x.jpg", 'nom_exporte': "x.jpg",
             'octets': 10, 'quand': None}
        v, _c, detail = G.juger(m, {"x.jpg": [(str(n), 10)]}, empreinte=True)
        self.assertEqual(v, 'AMBIGU')
        self.assertIn("empreintes differentes", detail)

    def test_memes_octets_restent_CERTAIN(self):
        tmp = Path(tempfile.mkdtemp(prefix="test_gphotos5_"))
        g, n = tmp / "g.jpg", tmp / "n.jpg"
        g.write_bytes(b"a" * 10)
        n.write_bytes(b"a" * 10)
        m = {'chemin': str(g), 'nom': "x.jpg", 'nom_exporte': "x.jpg",
             'octets': 10, 'quand': None}
        v, _c, _d = G.juger(m, {"x.jpg": [(str(n), 10)]}, empreinte=True)
        self.assertEqual(v, 'CERTAIN')


class IlNEffaceRien(unittest.TestCase):

    def test_aucune_suppression_dans_le_module(self):
        source = Path(G.__file__).read_text(encoding='utf-8')
        for interdit in ('.unlink(', 'os.remove(', 'shutil.rmtree(',
                         'os.rmdir('):
            self.assertNotIn(interdit, source, interdit + " dans une famille "
                             "verifier_ : elle est en lecture seule")


if __name__ == '__main__':
    unittest.main(verbosity=0)
