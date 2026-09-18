#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banc du CABLAGE du masque personnel (chantier 19, brique 3) -- sur le TEXTE de
`server.py`, sans l'importer (torch, insightface, et photos.db que la VM ne
sait pas ouvrir).

La regle pure et la vue sont prouvees dans `test_visibilite.py`
(`LeMasqueDUnePersonneReconnue`). Ici on prouve ce que le CABLAGE peut perdre
en silence, et qui coute une fuite :

1. **Les cinq magasins recoivent le predicat.** Pas seulement l'index : les
   visages et les animaux sont keyes par le chemin de la photo, et une fiche
   PEOPLE cite des chemins (avatar, faces). Un avatar pris sur une photo
   masquee serait une vignette qui fuit -- le point 17b, une fois de plus.
2. **Le masque se lit dans l'index BRUT**, jamais a travers la vue : la vue
   appelle ce predicat pour decider, et une photo deja masquee y serait
   introuvable, donc jugee « pas masquee » et servie.
3. **Il ne part JAMAIS dans le XMP.** Un masque pose par un TIERS ne se grave
   pas dans le fichier de quelqu'un d'autre : ici la regle 18c compte double,
   parce que le fichier n'appartient pas a qui masque.
4. **La VISIBILITE se teste EN PREMIER** (regle n. 10) : a qui ne voit pas la
   photo on repond « introuvable », jamais un refus exact qui confirmerait
   qu'elle existe.
5. **La reponse ne dit rien des AUTRES** : ni qui a masque, ni combien.
6. **Poser demande d'etre RECONNU** sur la photo, lever n'appartient qu'a qui
   a pose -- les deux passent par `visibilite`, jamais par une regle recopiee.

Sortie ASCII (console cp1252).
"""

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py")


def _corps(nom):
    """La fonction SANS sa docstring : un banc juge du CODE, pas d'une prose.
    Celles d'ici NOMMENT le XMP et les autres masques pour dire pourquoi ils
    n'y sont pas -- une assertion sur le texte entier se mesurerait elle-meme
    (lecon de `test_sensibles`, repayee deux fois dans ce projet)."""
    n = _noeud(nom)
    corps = n.body[1:] if (n.body and isinstance(n.body[0], ast.Expr)
                           and isinstance(n.body[0].value, ast.Constant)
                           and isinstance(n.body[0].value.value, str)) else n.body
    return "\n".join(ast.get_source_segment(SOURCE, x) or "" for x in corps)


class LesMagasinsRecoiventLePredicat(unittest.TestCase):
    def test_les_cinq_magasins(self):
        bloc = SOURCE[SOURCE.index("for _st in (STORE, FACE_STORE, ANIMAL_STORE):"):
                      SOURCE.index("# ─── Les COMPTES (chantier 17")]
        self.assertEqual(bloc.count("masques=masques_du_chemin"), 2)
        self.assertIn("PEOPLE_STORE, PETS_STORE", bloc)
        self.assertIn("par_nom=True", bloc)

    def test_le_masque_se_lit_dans_l_index_BRUT(self):
        c = _corps("masques_du_chemin")
        self.assertIn("INDEX_BRUT", c)
        self.assertNotIn("STORE.data", c)
        self.assertNotIn(".get(cle) or STORE", c)


class LeChampNePartJamaisDansLeFichier(unittest.TestCase):
    """18c, en double : ce n'est meme pas le fichier de qui masque."""

    def test_aucun_ecrivain_de_fichier_dans_la_route(self):
        c = _corps("_do_masque_post")
        for interdit in ("exiftool", "ecriture_meta", "write_tags", "piexif",
                         "shutil", "os.replace", "rename", "unlink"):
            self.assertNotIn(interdit, c, interdit)
        # ce qu'elle DOIT faire : ecrire dans l'index, et rien d'autre
        self.assertIn("STORE.set(cle, neuf)", c)

    def test_le_champ_ne_voyage_pas_vers_les_tags(self):
        """`masque_par` ne doit apparaitre nulle part pres d'une liste de
        mots-cles : il n'est pas un tag, il est un etat."""
        for nom in ("personnes_de",):
            self.assertNotIn("masque", _corps(nom))


class LOrdreDesRefus(unittest.TestCase):
    """Regle n. 10 : un refus exact confirme une existence. La visibilite
    d'abord, toujours -- corollaire attrape par un banc le 10/09."""

    def _index_de(self, corps, *motifs):
        for m in motifs:
            if m in corps:
                return corps.index(m)
        raise AssertionError("aucun de " + repr(motifs) + " dans le corps")

    def test_la_GET_repond_introuvable_avant_tout_le_reste(self):
        c = _corps("_serve_masque")
        i_vu = self._index_de(c, "not vu")
        i_peut = self._index_de(c, "peut_masquer")
        self.assertLess(i_vu, i_peut)
        self.assertIn("Fichier introuvable.", c)

    def test_la_POST_aussi(self):
        c = _corps("_do_masque_post")
        i_vu = self._index_de(c, "not vu")
        for apres in ("peut_masquer", "peut_lever", "STORE.set"):
            self.assertLess(i_vu, c.index(apres), apres)

    def test_la_visibilite_est_celle_du_module_pas_une_recopie(self):
        c = _corps("_etat_masque")
        self.assertIn("_visibilite.visible(", c)
        self.assertIn("INDEX_BRUT", c)


class LaReponseNeParleQueDeMoi(unittest.TestCase):
    """Savoir qu'une photo porte le masque de quelqu'un est deja un
    renseignement SUR quelqu'un. La reponse ne dit ni qui, ni combien."""

    def test_aucun_nom_d_autrui_ni_compte_dans_la_reponse(self):
        for nom in ("_serve_masque", "_do_masque_post"):
            c = _corps(nom)
            i = c.index("'ok'")
            fin = c[i:]
            self.assertNotIn("'masques'", fin, nom)
            self.assertNotIn("'qui'", fin, nom)
            self.assertNotIn("len(m", fin, nom)
            for champ in ("'mien'", "'peut_poser'", "'peut_lever'"):
                self.assertIn(champ, fin, nom + " " + champ)


class LesDroitsViennentDeVisibilite(unittest.TestCase):
    def test_poser_et_lever_ne_sont_pas_recopies(self):
        c = _corps("_do_masque_post")
        self.assertIn("_visibilite.peut_masquer(", c)
        self.assertIn("_visibilite.peut_lever(", c)
        # aucune regle de droit ecrite a la main dans la route
        for recopie in ("== ADMIN", "proprietaire_de(", "chez_soi("):
            self.assertNotIn(recopie, c, recopie)

    def test_les_noms_reconnus_viennent_des_tags_personne(self):
        c = _corps("personnes_de")
        self.assertIn("kw_fr", c)
        self.assertIn("'personne:'", c)

    def test_les_deux_routes_sont_branchees(self):
        get = _corps("_do_get")
        post = _corps("_do_post")
        self.assertIn("'/api/masque'", get)
        self.assertIn("self._serve_masque()", get)
        self.assertIn("'/api/masque'", post)
        self.assertIn("self._do_masque_post()", post)


if __name__ == "__main__":
    unittest.main(verbosity=2)
