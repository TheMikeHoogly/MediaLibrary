#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banc du CABLAGE du partage (chantier 19, brique 5) -- sur le TEXTE de
`server.py`, sans l'importer (torch, insightface, et photos.db que la VM ne
sait pas ouvrir).

La regle pure est prouvee dans `test_visibilite.LePartageEstUneRelationEntreComptes`,
les trois etats dans `test_comptes.Partage`. Ici on prouve ce que le CABLAGE
peut perdre en silence :

1. **Les cinq magasins recoivent l'ensemble.** Pas seulement l'index : les
   visages et les animaux sont keyes par le chemin de la photo, et une fiche
   PEOPLE cite des chemins (avatar, faces). Un avatar pris sur une photo non
   partagee serait une vignette qui fuit -- le point 17b, encore.
2. **L'ensemble est un APPELABLE, relu a chaque lecture** : une vue qui
   garderait celui d'hier montrerait ce que quelqu'un vient de fermer.
3. **Le fichier des comptes est relu s'il a change** avant d'etre interroge :
   sinon un partage regle a l'instant ne vaudrait qu'au prochain redemarrage.
4. **Chacun ne regle que SA liste** : la route ne lit aucun nom de compte dans
   le corps de la requete -- pas d'exception admin, ni en lecture ni en
   ecriture (choix de Mike, 18/09).
5. **La reponse ne dit rien des listes des AUTRES** : les NOMS des comptes en
   sortent (ce sont les dossiers `Photos <Nom>`, deja publics), leurs choix
   jamais.

Sortie ASCII (console cp1252).
"""

import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)
DEBUT = "for _st in (STORE, FACE_STORE, ANIMAL_STORE):"
FIN = "─── Les COMPTES (chantier 17"


def _noeud(nom):
    for n in ast.walk(ARBRE):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom:
            return n
    raise AssertionError(nom + " introuvable dans server.py")


def _corps(nom):
    """La fonction SANS sa docstring : un banc juge du CODE, pas d'une prose
    (lecon de `test_sensibles`, repayee deux fois dans ce projet)."""
    n = _noeud(nom)
    corps = n.body[1:] if (n.body and isinstance(n.body[0], ast.Expr)
                           and isinstance(n.body[0].value, ast.Constant)
                           and isinstance(n.body[0].value.value, str)) else n.body
    return "\n".join(ast.get_source_segment(SOURCE, x) or "" for x in corps)


def _bloc_branchement():
    return SOURCE[SOURCE.index(DEBUT):SOURCE.index(FIN)]


class LesCinqMagasinsRecoiventLEnsemble(unittest.TestCase):
    def test_les_cinq(self):
        bloc = _bloc_branchement()
        self.assertEqual(bloc.count("fermes=fermes_du_compte"), 2)
        self.assertIn("PEOPLE_STORE, PETS_STORE", bloc)

    def test_c_est_un_appelable_pas_un_ensemble_fige(self):
        """Passer `COMPTES.fermes_pour(u)` ici serait un instantane du
        DEMARRAGE : la vue doit pouvoir rappeler la question."""
        bloc = _bloc_branchement()
        self.assertNotIn("fermes=fermes_du_compte(", bloc)
        self.assertNotIn("fermes=frozenset", bloc)

    def test_l_ensemble_relit_le_fichier_des_comptes(self):
        c = _corps("fermes_du_compte")
        self.assertIn("recharger_si_change", c)
        self.assertIn("fermes_pour", c)
        self.assertIn("frozenset()", c)


class LaRECONNAISSANCEEstBrancheeEtBornee(unittest.TestCase):
    """Chantier 19, brique 4 : etre sur une photo la rouvre -- d'un cran, et
    d'un seul."""

    def test_les_cinq_magasins_recoivent_le_predicat(self):
        bloc = _bloc_branchement()
        self.assertEqual(bloc.count("reconnu=reconnu_sur"), 2)

    def test_il_lit_l_index_BRUT(self):
        c = _corps("reconnu_sur")
        self.assertIn("INDEX_BRUT", c)
        self.assertNotIn("STORE.data", c)

    def test_il_passe_par_personnes_de_et_ne_recopie_pas_la_lecture(self):
        c = _corps("reconnu_sur")
        self.assertIn("personnes_de(", c)
        self.assertNotIn("kw_fr", c)          # la lecture des tags vit AILLEURS
        self.assertIn("lower()", c)           # la casse ne decide pas d'un droit


class ChacunNeRegleQueSaListe(unittest.TestCase):
    def test_la_route_ne_lit_aucun_nom_de_compte_dans_le_corps(self):
        c = _corps("_do_partage_post")
        self.assertIn("utilisateur_vu()", c)
        self.assertIn("definir_partage(u", c)
        for exception in ("d.get('nom')", 'd.get("nom")', "est_admin"):
            self.assertNotIn(exception, c, exception)

    def test_la_lecture_non_plus(self):
        c = _corps("_serve_partage")
        self.assertIn("utilisateur_vu()", c)
        self.assertIn("partage_de(u)", c)
        self.assertNotIn("est_admin", c)

    def test_la_reponse_ne_porte_pas_les_listes_des_autres(self):
        c = _corps("_serve_partage")
        self.assertIn("COMPTES.noms()", c)
        self.assertNotIn("partage_de(n)", c)
        self.assertNotIn("fermes_pour", c)

    def test_les_deux_routes_sont_branchees(self):
        self.assertIn("'/api/partage'", _corps("_do_get"))
        self.assertIn("self._serve_partage()", _corps("_do_get"))
        self.assertIn("'/api/partage'", _corps("_do_post"))
        self.assertIn("self._do_partage_post()", _corps("_do_post"))


class LesTroisEtatsMontentJusquALEcran(unittest.TestCase):
    """Aplatir `null` et `[]` cote serveur recreerait l'ambiguite que le champ
    existe pour eviter."""

    def test_la_route_rend_le_champ_tel_quel(self):
        c = _corps("_serve_partage")
        self.assertIn("COMPTES.partage_de(u)", c)
        self.assertNotIn("or []", c)
        self.assertNotIn("or ()", c)

    def test_le_None_traverse_la_POST(self):
        self.assertIn("liste is not None", _corps("_do_partage_post"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
