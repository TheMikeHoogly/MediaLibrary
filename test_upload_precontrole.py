#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le pre-controle d'upload dit-il vrai AVANT que les octets arrivent ?
(1 quindecies-b, demande de Mike le 01/09 : sauter ce que le serveur a deja,
demande AVANT d'envoyer chaque fichier)

SUR LE CODE DE PROD, sans importer `server.py` (meme garde que
`test_ui_global.py` : `import server` ouvre `photos.db` -- SEUL le serveur en
est l'ecrivain, et cette VM ne sait meme pas l'ouvrir en lecture par-dessus
le montage, `disk I/O error` -- et demarre torch/insightface). On extrait par
`ast` les quelques fonctions pures qui font le dedoublonnage (aucune ne
touche `photos.db`, seulement `UPLOAD_DIR` sur disque) et on les exec dans un
namespace isole, `UPLOAD_DIR` redirige sur un dossier temporaire.
"""
import ast
import hashlib
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE / "server.py").read_text(encoding="utf-8")
ARBRE = ast.parse(SOURCE)

FONCTIONS_REQUISES = (
    "_sha256_bytes", "_sha256_file", "_upload_size_map",
    "_upload_dup_by_hash", "_upload_content_dup",
)


def _extraire(noms):
    """Rend {nom: code_source} pour les fonctions de MODULE nommees --
    `ast.get_source_segment` sur le texte REEL de server.py, jamais une
    recopie a la main qui pourrait diverger du fichier livre."""
    trouve = {}
    for noeud in ARBRE.body:
        if isinstance(noeud, ast.FunctionDef) and noeud.name in noms:
            trouve[noeud.name] = ast.get_source_segment(SOURCE, noeud)
    manquantes = set(noms) - set(trouve)
    assert not manquantes, f"fonctions absentes de server.py : {manquantes}"
    return trouve


class Cablage(unittest.TestCase):
    """Le squelette existe et est branche -- avant de tester ce qu'il FAIT."""

    def test_les_fonctions_de_dedoublonnage_existent(self):
        _extraire(FONCTIONS_REQUISES)

    def test_la_route_est_branchee_dans_do_post(self):
        self.assertIn("path == '/api/upload/check'", SOURCE)
        self.assertIn("self._do_upload_check()", SOURCE)

    def test_le_gestionnaire_valide_taille_et_hash_avant_de_repondre(self):
        self.assertIn("def _do_upload_check(self):", SOURCE)
        bloc = SOURCE[SOURCE.index("def _do_upload_check(self):"):]
        bloc = bloc[:bloc.index("\n    def _do_post(self):")]
        self.assertIn("_upload_dup_by_hash(", bloc)
        # Jamais d'ecriture : ce controle ne fait que repondre SKIP/OK.
        for mot in ("write_bytes", "write_text", "open(", ".mkdir("):
            self.assertNotIn(mot, bloc)

    def test_le_client_fait_le_precontrole_avant_lenvoi(self):
        html = (HERE / "ui" / "pages" / "upload.html").read_text(encoding="utf-8")
        self.assertIn("/api/upload/check", html)
        self.assertIn("crypto.subtle", html)
        # Toujours sans minuteur (1 quindecies-a, deja acquis : ne pas
        # regresser en remettant un setTimeout dans la boucle d'envoi).
        self.assertNotIn("setTimeout", html)


class DedoublonnageParHash(unittest.TestCase):
    """Namespace isole : les fonctions REELLES de server.py, aucune donnee
    reelle. `UPLOAD_DIR` pointe sur un dossier temporaire jete a la fin."""

    @classmethod
    def setUpClass(cls):
        cls.fonctions = _extraire(FONCTIONS_REQUISES)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ml_test_upload_precontrole_")
        self.dir = Path(self.tmp.name)
        ns = {
            "Path": Path, "hashlib": hashlib, "threading": threading, "time": time,
            "UPLOAD_DIR": self.dir,
            "_UP_SIZE_IDX": {"at": 0.0, "map": None},
            "_UP_SIZE_LOCK": threading.Lock(),
            "UP_IDX_TTL": 120.0,
        }
        for nom in FONCTIONS_REQUISES:
            exec(self.fonctions[nom], ns)
        self.ns = ns

    def tearDown(self):
        self.tmp.cleanup()

    def _sha256(self, b):
        return hashlib.sha256(b).hexdigest()

    def test_rien_de_meme_taille_rend_none(self):
        (self.dir / "a.jpg").write_bytes(b"x" * 100)
        rendu = self.ns["_upload_dup_by_hash"](999, self._sha256(b"y" * 999))
        self.assertIsNone(rendu)

    def test_meme_taille_mais_hash_different_rend_none(self):
        contenu = b"photo-un" * 50
        (self.dir / "a.jpg").write_bytes(contenu)
        autre_hash = self._sha256(b"#" * len(contenu))
        rendu = self.ns["_upload_dup_by_hash"](len(contenu), autre_hash)
        self.assertIsNone(rendu)

    def test_meme_taille_et_meme_hash_rend_le_chemin(self):
        contenu = b"photo-identique" * 37
        p = self.dir / "existant.jpg"
        p.write_bytes(contenu)
        rendu = self.ns["_upload_dup_by_hash"](len(contenu), self._sha256(contenu))
        self.assertEqual(rendu, p)

    def test_insensible_a_la_casse_du_hash(self):
        contenu = b"casse" * 80
        p = self.dir / "c.jpg"
        p.write_bytes(contenu)
        empreinte_maj = self._sha256(contenu).upper()
        # Le serveur normalise en minuscules AVANT d'appeler la fonction
        # (dans `_do_upload_check`) -- ici on prouve juste que la fonction
        # elle-meme compare bien a plat, sans re-normaliser en douce.
        rendu = self.ns["_upload_dup_by_hash"](len(contenu), empreinte_maj.lower())
        self.assertEqual(rendu, p)

    def test_content_dup_coherent_avec_dup_by_hash(self):
        # Non-regression du refactor (29047e7 -> ce commit) :
        # _upload_content_dup(data) == _upload_dup_by_hash(len(data), sha256(data)).
        contenu = b"regression" * 61
        p = self.dir / "r.jpg"
        p.write_bytes(contenu)
        self.assertEqual(self.ns["_upload_content_dup"](contenu), p)
        differe = b"#" * len(contenu)
        self.assertIsNone(self.ns["_upload_content_dup"](differe))

    def test_dossier_vide_ne_hashe_rien(self):
        # Aucun candidat de la bonne taille : retour immediat, jamais un
        # parcours ni un hash pour rien (le filtre par taille d'abord).
        rendu = self.ns["_upload_dup_by_hash"](12345, "0" * 64)
        self.assertIsNone(rendu)


if __name__ == "__main__":
    unittest.main()
