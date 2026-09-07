#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banc du CABLAGE de l'axe `sensible` (chantier 18, etape a) -- sur le TEXTE de
`server.py`, sans l'importer (torch, insightface, et photos.db que la VM ne
sait pas ouvrir).

La regle pure et la vue sont prouvees dans `test_visibilite.py`. Ici on prouve
les quatre choses que le CABLAGE peut perdre en silence, et qui coutent une
fuite :

1. **La visibilite ne se decide plus sur le seul CHEMIN.** Les cinq magasins
   recoivent le predicat d'etat -- pas seulement l'index : les visages et les
   animaux sont keyes par le chemin de la photo, et une fiche PEOPLE cite des
   chemins (avatar, faces). Un avatar pris sur une photo masquee serait une
   vignette qui fuit, exactement le point 17b.
2. **Le garde des OCTETS lit l'etat.** Une photo que la galerie ne cite plus
   mais dont l'URL de vignette rend les pixels n'est pas masquee du tout.
3. **L'etat se lit dans l'index BRUT, jamais a travers la vue.** La vue appelle
   ce predicat pour decider : le lire a travers elle tournerait en rond, et
   une photo DEJA masquee y serait introuvable, donc jugee « pas sensible »
   et servie -- le trou se refermerait sur lui-meme.
4. **L'axe ne part JAMAIS dans le XMP** (18c). Un verdict de machine qui se
   trompe une fois sur trois ne se grave pas dans le fichier de quelqu'un.
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


def _src(nom):
    return ast.get_source_segment(SOURCE, _noeud(nom)) or ""


def _corps(nom):
    """La fonction SANS sa docstring. Un banc juge du CODE, pas d'une prose :
    la docstring de `_key_index` explique pourquoi elle ne lit plus `STORE.data`
    et le cite donc forcement, et celle de `_do_sensibles_post` renvoie aux deux
    autres gestes en les nommant. Les deux assertions sont tombees dessus au
    premier passage -- la lecon etait deja ecrite dans `test_retag_campagne`,
    et elle a ete repayee ici."""
    n = _noeud(nom)
    corps = n.body[1:] if (n.body and isinstance(n.body[0], ast.Expr)
                           and isinstance(n.body[0].value, ast.Constant)
                           and isinstance(n.body[0].value.value, str)) else n.body
    return "\n".join(ast.get_source_segment(SOURCE, x) or "" for x in corps)


class LesCinqMagasinsRecoiventLEtat(unittest.TestCase):
    def test_les_trois_magasins_par_chemin(self):
        self.assertIn("_visibilite.brancher(_st, utilisateur_vu, "
                      "sensible=sensible_en_attente)", SOURCE)

    def test_les_deux_magasins_par_nom(self):
        # Une fiche cite des chemins : l'avatar d'une photo masquee est une
        # vignette qui fuit.
        bloc = SOURCE.split("for _st in (PEOPLE_STORE, PETS_STORE):")[1][:300]
        self.assertIn("par_nom=True", bloc)
        self.assertIn("sensible=sensible_en_attente", bloc)

    def test_aucun_branchement_sans_etat(self):
        # Un magasin oublie serait un magasin qui montre ce que les autres
        # cachent -- et personne ne le verrait.
        for ligne in SOURCE.splitlines():
            if "_visibilite.brancher(" in ligne or "sensible=sensible_en_attente" in ligne:
                continue
            self.assertNotIn("brancher(_st", ligne)
        self.assertEqual(SOURCE.count("_visibilite.brancher("), 2)


class LeGardeDesOctetsLitLEtat(unittest.TestCase):
    def test_chemin_visible_passe_l_etat(self):
        s = _corps("chemin_visible")
        self.assertIn("sensible_du_chemin(chemin)", s)
        self.assertIn("_visibilite.visible(", s)

    def test_un_fil_de_fond_ne_paie_pas_la_carte(self):
        # `chemin_visible` est appele pour CHAQUE vignette : sans la sortie
        # anticipee, chaque appel irait chercher la carte chemin -> cle.
        s = _corps("chemin_visible")
        self.assertLess(s.index("if u is None:"), s.index("sensible_du_chemin"))


class LEtatSeLitDansLIndexBrut(unittest.TestCase):
    def test_l_index_brut_est_capture_avant_la_vue(self):
        i_brut = SOURCE.index("INDEX_BRUT = STORE.data")
        i_branche = SOURCE.index("_visibilite.brancher(_st, utilisateur_vu,")
        self.assertLess(i_brut, i_branche,
                        "capturer l'index APRES le branchement rendrait la VUE")

    def test_les_deux_predicats_lisent_le_brut(self):
        for nom in ("sensible_en_attente", "sensible_du_chemin"):
            s = _corps(nom)
            self.assertIn("INDEX_BRUT", s, nom)
            self.assertNotIn("STORE.data", s, nom)
            self.assertNotIn("STORE.get(", s, nom)

    def test_la_carte_chemin_cle_se_batit_sur_le_brut(self):
        s = _corps("_key_index")
        self.assertIn("len(INDEX_BRUT)", s)
        self.assertIn("list(INDEX_BRUT.keys())", s)
        self.assertNotIn("STORE.data", s)

    def test_la_route_de_liste_lit_le_brut(self):
        # Batie sur la vue, elle serait VIDE par construction : ces photos
        # sont precisement celles que la vue cache.
        s = _corps("_serve_sensibles")
        self.assertIn("INDEX_BRUT.items()", s)
        self.assertNotIn("STORE.data", s)


class LaRouteDEtat(unittest.TestCase):
    def setUp(self):
        self.s = _corps("_do_sensibles_post")

    def test_trois_valeurs_admises_dont_la_levee(self):
        self.assertIn("SENSIBLE_ETATS = ('', _visibilite.SENSIBLE_EN_ATTENTE, "
                      "_visibilite.SENSIBLE_NON)", SOURCE)
        self.assertIn("if etat not in SENSIBLE_ETATS:", self.s)

    def test_juger_c_est_pouvoir_lever(self):
        # `peut_juger`, pas `chez_soi` : l'admin doit pouvoir defaire un faux
        # positif, sinon une photo d'un dossier sans compte serait masquee
        # pour toujours (tranche par Mike le 07/09).
        self.assertIn("_visibilite.peut_juger(cle, u)", self.s)
        self.assertNotIn("chez_soi", self.s)
        self.assertNotIn("chez_soi", _corps("_serve_sensibles"))
        self.assertIn("_visibilite.peut_juger(cle, u)", _corps("_serve_sensibles"))

    def test_un_refus_est_nomme_par_cle(self):
        # Un lot qui echoue a moitie en silence est pire qu'un lot qui echoue.
        self.assertIn("refuses.append(", self.s)
        self.assertIn("'pourquoi'", self.s)

    def test_la_levee_efface_les_quatre_champs(self):
        # Laisser `sensible_le` derriere ferait une photo « pas sensible »
        # qui porte encore la date ou on l'a crue sensible.
        for champ in ('sensible', 'sensible_le', 'sensible_par', 'sensible_motif'):
            self.assertIn(f"'{champ}'", self.s)
        self.assertIn("neuf.pop(champ, None)", self.s)

    def test_une_seule_ecriture_de_base_pour_le_lot(self):
        self.assertIn("STORE.set(cle, neuf, save=False)", self.s)
        self.assertIn("STORE.save()", self.s)

    def test_les_deux_autres_gestes_gardent_leurs_routes(self):
        # « Rendre privee » DEPLACE (17a) et la corbeille EFFACE : les
        # refaire ici ferait deux chemins pour un meme geste, et ils
        # finiraient par diverger.
        self.assertNotIn("ops.move", self.s)
        self.assertNotIn("corbeille", self.s)


class LAxeNeVaJamaisDansLeFichier(unittest.TestCase):
    """18c : l'etat vit en BASE, jamais dans le XMP."""

    def test_aucune_ecriture_de_metadonnees_ne_cite_l_axe(self):
        for nom in ("write_metadata", "retro_write_metadata"):
            try:
                s = _src(nom)
            except AssertionError:
                continue
            self.assertNotIn("sensible", _corps(nom), nom)

    def test_l_axe_n_est_pas_un_tag(self):
        # Un tag `sensible:` partirait dans les mots-cles, donc dans le XMP
        # par le chemin normal, sans que personne l'ait voulu.
        self.assertNotIn("'sensible:'", SOURCE)
        self.assertNotIn('"sensible:"', SOURCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
