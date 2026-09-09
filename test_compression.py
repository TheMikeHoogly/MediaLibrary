#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banc de la compression HTTP (O11 de l'audit interne) -- sur le TEXTE de
`server.py`, sans l'importer (torch, insightface, photos.db).

Ce que ces tests protegent, et c'est plus etroit qu'il n'y parait : la
compression n'est pas dangereuse en soi, mais elle touche le `Content-Length`,
et un `Content-Length` faux coupe la reponse au milieu SANS erreur visible --
le navigateur affiche une page tronquee et personne ne sait pourquoi. Les
quatre proprietes ci-dessous sont exactement celles dont l'oubli produit ce
symptome-la.

Lance : python test_compression.py
"""

import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "server.py").read_text(encoding="utf-8")


def _corps(nom):
    m = re.search(r"\n    def %s\(self.*?(?=\n    def |\n\nclass |\nclass )"
                  % re.escape(nom), SOURCE, re.S)
    if not m:
        raise AssertionError(nom + " introuvable dans server.py")
    return m.group(0)


class UnSeulEndroitCompresse(unittest.TestCase):
    def test_les_deux_sorties_passent_par_le_meme_chemin(self):
        # `_send` (151 appels, les JSON d'API) et `_send_html` (les pages).
        # Deux endroits qui ecrivent le Content-Length finiraient par ne plus
        # dire la meme chose.
        self.assertIn("self._repondre(", _corps("_send"))
        self.assertIn("self._repondre(", _corps("_send_html"))

    def test_les_medias_ne_passent_PAS_par_la(self):
        # Vignettes et fichiers : deja compresses, et servis par blocs. Les
        # gzipper brulerait du CPU pour grossir la reponse.
        self.assertNotIn("_repondre", _corps("_send_file"))


class LeContentLengthDitLaVERITE(unittest.TestCase):
    def test_il_est_calcule_APRES_la_compression(self):
        # Sur l'APPEL, pas sur le mot : la docstring de `_repondre` contient
        # « Content-Length » et le premier jet de ce test l'a trouve la,
        # rouge sur un code juste. Un banc qui lit les commentaires ne mesure
        # pas le code.
        c = _corps("_repondre")
        i_gzip = c.index("gzip.compress")
        i_len = c.index("send_header('Content-Length'")
        self.assertLess(i_gzip, i_len,
                        "un Content-Length calcule avant la compression coupe "
                        "la reponse au milieu, sans erreur visible")

    def test_la_compression_n_est_gardee_que_si_elle_GAGNE(self):
        c = _corps("_repondre")
        self.assertIn("len(comprime) < len(body)", c)


class LesGardes(unittest.TestCase):
    def test_le_client_doit_l_avoir_demande(self):
        self.assertIn("Accept-Encoding", _corps("_vaut_le_gzip"))

    def test_un_seuil_et_une_liste_de_types(self):
        self.assertIn("GZIP_MINIMUM = 4096", SOURCE)
        for t in ("application/json", "text/html", "text/css"):
            self.assertIn(t, SOURCE, t)
        # Ce qui est deja compresse n'a rien a faire dans la liste.
        i = SOURCE.index("GZIP_TYPES")
        bloc = SOURCE[i:i + 300]
        for t in ("image/jpeg", "video/", "image/png"):
            self.assertNotIn(t, bloc, t)

    def test_VARY_est_envoye_MEME_sans_compression(self):
        # La panne classique de la compression conditionnelle : sans `Vary`,
        # un cache sert la version compressee a un client qui n'en veut pas.
        # Elle ne se voit qu'a travers un cache, donc jamais en developpement.
        c = _corps("_repondre")
        i_vary = c.index("Vary")
        i_if = c.index("if self._vaut_le_gzip")
        i_fin_if = c.index("self.send_response")
        self.assertTrue(i_vary > i_fin_if,
                        "`Vary` doit etre HORS du bloc conditionnel")
        self.assertLess(i_if, i_fin_if)


if __name__ == "__main__":
    unittest.main(verbosity=0)
